#!/usr/bin/env python3
"""
Discord Bot — General Technical Process Assistant
עוזר טכני לתהליך דרך Discord

הפעלה — ראה README בתחתית הקובץ.
"""

import io
import logging
import os
from typing import Any

import anthropic
import discord
from discord.ext import commands

from agent import SYSTEM_PROMPT, TOOLS, build_user_content, save_session

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

async_client = anthropic.AsyncAnthropic()

SUPPORTED_EXTENSIONS = (".csv", ".xlsx", ".xls", ".txt")
MAX_MSG_LEN = 1900  # Discord limit is 2000 — leave margin

# Per-user state: {user_id: {"messages": [...], "pending_file_id": str | None}}
sessions: dict[int, dict[str, Any]] = {}

intents = discord.Intents.default()
intents.message_content = True  # Requires enabling in Developer Portal

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_session(user_id: int) -> dict:
    if user_id not in sessions:
        sessions[user_id] = {"messages": [], "pending_file_id": None}
    return sessions[user_id]


def split_text(text: str, limit: int = MAX_MSG_LEN) -> list[str]:
    """Split long text into Discord-compatible chunks at newline boundaries."""
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


async def agent_response(messages: list, status_msg: discord.Message) -> str:
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
                            "web_search":     "🔍 מחפש מידע טכני...",
                            "web_fetch":      "🌐 טוען דף...",
                            "code_execution": "⚙️ מנתח נתונים...",
                        }.get(name, "⚙️ עובד...")
                        try:
                            await status_msg.edit(content=indicator)
                        except Exception:
                            pass

                elif event.type == "content_block_delta":
                    if event.delta.type == "text_delta":
                        text_buffer.append(event.delta.text)
                        current = "".join(text_buffer)
                        # Progressive edit every ~300 new chars (only while short enough)
                        if len(current) - last_edit_len >= 300 and len(current) < 1700:
                            try:
                                await status_msg.edit(content=current + " ✍️")
                                last_edit_len = len(current)
                            except Exception:
                                pass

            response = await stream.get_final_message()

        messages.append({"role": "assistant", "content": response.content})
        if response.stop_reason != "pause_turn":
            break
        try:
            await status_msg.edit(content="⏳ ממשיך חיפוש...")
        except Exception:
            pass

    return "".join(text_buffer)


# ── Events ────────────────────────────────────────────────────────────────────

@bot.event
async def on_ready() -> None:
    print(f"🤖 Bot online: {bot.user}  |  Servers: {len(bot.guilds)}")
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.listening,
            name="שאלות טכניות | !help",
        )
    )


@bot.event
async def on_message(message: discord.Message) -> None:
    if message.author == bot.user:
        return

    # Let command handlers run first
    await bot.process_commands(message)
    if message.content.startswith("!"):
        return

    if not message.content and not message.attachments:
        return

    session = get_session(message.author.id)

    # ── File attachments ──
    file_uploaded = False
    for attachment in message.attachments:
        name = attachment.filename
        if not any(name.lower().endswith(ext) for ext in SUPPORTED_EXTENSIONS):
            await message.channel.send(
                f"⚠️ קבצים נתמכים: {', '.join(SUPPORTED_EXTENSIONS)}"
            )
            continue

        status = await message.channel.send(f"📤 מעלה קובץ: `{name}` ...")
        try:
            buf = io.BytesIO(await attachment.read())
            meta = await async_client.beta.files.upload(file=(name, buf))
            session["pending_file_id"] = meta.id
            await status.edit(
                content=(
                    f"✅ הקובץ הועלה: `{name}`\n"
                    "עכשיו כתוב מה לנתח — לדוגמה:\n"
                    "• חשב CPK ו-SPC chart\n"
                    "• הצג histogram\n"
                    "• זהה outliers"
                )
            )
            file_uploaded = True
        except Exception as e:
            logger.exception("File upload failed")
            await status.edit(content=f"❌ שגיאה בהעלאת הקובץ: {e}")

    # If only a file was sent (no text) — wait for the follow-up question
    if not message.content:
        return

    # ── Text message → agent ──
    async with message.channel.typing():
        status = await message.channel.send("⌛ חושב...")

    content = build_user_content(message.content, session["pending_file_id"])
    session["pending_file_id"] = None
    session["messages"].append({"role": "user", "content": content})

    try:
        full_text = await agent_response(session["messages"], status)
        await status.delete()

        for chunk in split_text(full_text):
            await message.channel.send(chunk)

    except Exception as e:
        logger.exception("Agent error")
        await status.edit(content=f"❌ שגיאה: {e}")


# ── Commands ──────────────────────────────────────────────────────────────────

@bot.command(name="help")
async def cmd_help(ctx: commands.Context) -> None:
    await ctx.send(
        "**⚙️ עוזר טכני לתהליך — פקודות**\n"
        "`!help`  — עזרה זו\n"
        "`!clear` — מחק היסטוריית שיחה\n"
        "`!save`  — שמור שיחה כ-Markdown\n\n"
        "**שימוש:**\n"
        "• כתוב שאלה טכנית ישירות בערוץ\n"
        "• שלח קובץ CSV/Excel ואז כתוב מה לנתח\n\n"
        "**דוגמאות:**\n"
        "• מה ה-CPK המינימלי לפי IPC-7095?\n"
        "• איך לפתור בעיית missing bumps?\n"
        "• [שלח קובץ] ← חשב CPK ו-SPC chart"
    )


@bot.command(name="clear")
async def cmd_clear(ctx: commands.Context) -> None:
    session = get_session(ctx.author.id)
    session["messages"].clear()
    session["pending_file_id"] = None
    await ctx.send("✅ היסטוריית השיחה נמחקה.")


@bot.command(name="save")
async def cmd_save(ctx: commands.Context) -> None:
    session = get_session(ctx.author.id)
    if not session["messages"]:
        await ctx.send("אין שיחה לשמירה.")
        return
    filename = save_session(session["messages"])
    await ctx.send(f"✅ השיחה נשמרה: `{filename}`")


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    token = os.environ.get("DISCORD_BOT_TOKEN")
    if not token:
        raise SystemExit(
            "❌ חסר DISCORD_BOT_TOKEN\n"
            "ראה הוראות הגדרה בקובץ discord_bot.py"
        )
    bot.run(token)


if __name__ == "__main__":
    main()


# ══════════════════════════════════════════════════════════════════════════════
# הוראות הפעלה / Setup Instructions
# ══════════════════════════════════════════════════════════════════════════════
#
# שלב 1 — צור Application ב-Discord Developer Portal
#   https://discord.com/developers/applications
#   לחץ "New Application" → תן שם → לחץ "Bot" בתפריט השמאלי → "Add Bot"
#
# שלב 2 — העתק את ה-Token
#   Bot → "Reset Token" → העתק ושמור בצד
#
# שלב 3 — הפעל Privileged Intents
#   Bot → גלול למטה → "Privileged Gateway Intents"
#   הפעל:  ✅ SERVER MEMBERS INTENT
#           ✅ MESSAGE CONTENT INTENT
#   לחץ "Save Changes"
#
# שלב 4 — הזמן את ה-Bot לשרת שלך
#   OAuth2 → URL Generator
#   Scopes:  ✅ bot
#   Permissions: ✅ Send Messages  ✅ Read Message History  ✅ Attach Files
#   העתק את ה-URL שנוצר → פתח בדפדפן → בחר שרת → Authorize
#
# שלב 5 — הרץ
#   pip install anthropic "discord.py>=2.0"
#   export ANTHROPIC_API_KEY="your-key"
#   export DISCORD_BOT_TOKEN="your-token"
#   python3 discord_bot.py
#
# ══════════════════════════════════════════════════════════════════════════════
