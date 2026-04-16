#!/usr/bin/env python3
"""
Telegram Bot — General Technical Process Assistant
עוזר טכני לתהליך דרך Telegram

Setup:
  1. Create a bot via @BotFather on Telegram → get TELEGRAM_BOT_TOKEN
  2. export TELEGRAM_BOT_TOKEN="your-token"
  3. export ANTHROPIC_API_KEY="your-key"
  4. pip install anthropic "python-telegram-bot>=20.0"
  5. python3 bot.py
"""

import io
import logging
import os
from typing import Any

import anthropic
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from agent import SYSTEM_PROMPT, TOOLS, build_user_content, save_session

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

async_client = anthropic.AsyncAnthropic()

# Per-user state: {user_id: {"messages": [...], "pending_file_id": str | None}}
sessions: dict[int, dict[str, Any]] = {}

SUPPORTED_EXTENSIONS = (".csv", ".xlsx", ".xls", ".txt")


def get_session(user_id: int) -> dict:
    if user_id not in sessions:
        sessions[user_id] = {"messages": [], "pending_file_id": None}
    return sessions[user_id]


def split_text(text: str, limit: int = 4000) -> list[str]:
    """Split long text into Telegram-compatible chunks at newline boundaries."""
    if len(text) <= limit:
        return [text]
    chunks = []
    while text:
        if len(text) <= limit:
            chunks.append(text)
            break
        split_at = text.rfind("\n", 0, limit)
        if split_at == -1:
            split_at = limit
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    return chunks


async def agent_response(messages: list, status_msg) -> str:
    """
    Run the agentic loop and return the full text response.
    Progressively edits status_msg to show tool activity and partial output.
    """
    text_buffer: list[str] = []

    while True:
        async with async_client.messages.stream(
            model="claude-opus-4-7",
            max_tokens=8000,
            thinking={"type": "adaptive"},
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
            extra_headers={"anthropic-beta": "files-api-2025-04-14"},
        ) as stream:
            last_edit_len = 0

            async for event in stream:
                if event.type == "content_block_start":
                    if getattr(event.content_block, "type", "") == "server_tool_use":
                        name = getattr(event.content_block, "name", "")
                        indicator = {
                            "web_search": "🔍 מחפש מידע טכני...",
                            "web_fetch":   "🌐 טוען דף...",
                            "code_execution": "⚙️ מנתח נתונים...",
                        }.get(name, "⚙️ עובד...")
                        try:
                            await status_msg.edit_text(indicator)
                        except Exception:
                            pass

                elif event.type == "content_block_delta":
                    if event.delta.type == "text_delta":
                        text_buffer.append(event.delta.text)
                        current = "".join(text_buffer)
                        # Edit message every ~300 new chars (only while short enough)
                        if len(current) - last_edit_len >= 300 and len(current) < 3600:
                            try:
                                await status_msg.edit_text(current + " ✍️")
                                last_edit_len = len(current)
                            except Exception:
                                pass

            response = await stream.get_final_message()

        messages.append({"role": "assistant", "content": response.content})
        if response.stop_reason != "pause_turn":
            break
        try:
            await status_msg.edit_text("⏳ ממשיך חיפוש...")
        except Exception:
            pass

    return "".join(text_buffer)


# ── Command handlers ──────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "👋 שלום! אני עוזר טכני לתהליכי אריזת שבבים ואינספקציה אופטית.\n\n"
        "אפשר לשאול שאלות טכניות, לשלוח קובץ CSV/Excel לניתוח, ועוד.\n"
        "הקלד /help לרשימת פקודות."
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "פקודות:\n"
        "/start  — ברוך הבא\n"
        "/help   — עזרה זו\n"
        "/save   — שמור שיחה כ-Markdown\n"
        "/clear  — מחק היסטוריית שיחה\n\n"
        "שלח קובץ CSV/Excel ואז שאל מה לנתח.\n\n"
        "דוגמאות:\n"
        "• מה ה-CPK המינימלי לפי IPC-7095?\n"
        "• איך לפתור בעיית missing bumps?\n"
        "• [שלח קובץ] ← חשב CPK ו-SPC chart"
    )


async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    session = get_session(update.effective_user.id)
    session["messages"].clear()
    session["pending_file_id"] = None
    await update.message.reply_text("✅ היסטוריית השיחה נמחקה.")


async def cmd_save(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    session = get_session(update.effective_user.id)
    if not session["messages"]:
        await update.message.reply_text("אין שיחה לשמירה.")
        return
    filename = save_session(session["messages"])
    await update.message.reply_text(f"✅ השיחה נשמרה בשרת: {filename}")


# ── Message handlers ──────────────────────────────────────────────────────────

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Download a user-sent file, upload to Files API, store file_id for next message."""
    doc = update.message.document
    name = doc.file_name or "file"

    if not any(name.lower().endswith(ext) for ext in SUPPORTED_EXTENSIONS):
        await update.message.reply_text(
            f"⚠️ קבצים נתמכים: {', '.join(SUPPORTED_EXTENSIONS)}"
        )
        return

    status = await update.message.reply_text(f"📤 מעלה קובץ: {name} ...")
    await context.bot.send_chat_action(update.effective_chat.id, ChatAction.UPLOAD_DOCUMENT)

    try:
        tg_file = await doc.get_file()
        buf = io.BytesIO()
        await tg_file.download_to_memory(buf)
        buf.seek(0)

        meta = await async_client.beta.files.upload(file=(name, buf))
        get_session(update.effective_user.id)["pending_file_id"] = meta.id

        await status.edit_text(
            f"✅ הקובץ הועלה: {name}\n"
            "עכשיו שאל מה לנתח — לדוגמה:\n"
            "• חשב CPK ו-SPC chart\n"
            "• הצג histogram של הגבהים\n"
            "• זהה outliers"
        )
    except Exception as e:
        logger.exception("File upload failed")
        await status.edit_text(f"❌ שגיאה בהעלאת הקובץ: {e}")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle a regular text message — run the agent and reply."""
    session = get_session(update.effective_user.id)
    user_text = update.message.text

    await context.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)
    status = await update.message.reply_text("⌛ חושב...")

    content = build_user_content(user_text, session["pending_file_id"])
    session["pending_file_id"] = None
    session["messages"].append({"role": "user", "content": content})

    try:
        full_text = await agent_response(session["messages"], status)
        await status.delete()

        for chunk in split_text(full_text):
            await update.message.reply_text(chunk)

    except Exception as e:
        logger.exception("Agent error")
        await status.edit_text(f"❌ שגיאה: {e}")


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit(
            "❌ חסר TELEGRAM_BOT_TOKEN\n"
            "קבל אסימון מ-@BotFather ב-Telegram והגדר:\n"
            "  export TELEGRAM_BOT_TOKEN='your-token'"
        )

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help",  cmd_help))
    app.add_handler(CommandHandler("clear", cmd_clear))
    app.add_handler(CommandHandler("save",  cmd_save))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("🤖 Bot is running... Press Ctrl+C to stop.")
    app.run_polling()


if __name__ == "__main__":
    main()
