#!/usr/bin/env python3
"""
אג'נט מעקב מחירי דירות - טירת הכרמל
Real estate price tracking agent for Tirat HaCarmel.

Usage:
  python agent.py

Requires ANTHROPIC_API_KEY environment variable.
"""
import json
import os
import sys
from datetime import date

import anthropic
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt

from config import APARTMENT, CLAUDE_MODEL
from storage.data_manager import (
    load_all_snapshots,
    load_latest_listings,
    load_price_history,
    load_transactions,
    save_listings_snapshot,
    append_transactions,
    update_price_history,
)

console = Console()

# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

def _tool_collect_fresh_data(params: dict) -> dict:
    console.print("[dim]אוסף נתונים מיד2...[/dim]")
    from collectors.yad2 import fetch_listings as yad2_listings
    yad2 = yad2_listings()

    console.print("[dim]אוסף נתונים ממדלן...[/dim]")
    from collectors.madlan import fetch_listings as madlan_listings
    madlan = madlan_listings()

    console.print("[dim]אוסף עסקאות ממס שבח (gov.il)...[/dim]")
    from collectors.govil import fetch_transactions
    transactions = fetch_transactions(months_back=24)

    all_listings = yad2 + madlan
    snapshot_path = save_listings_snapshot(all_listings)
    append_transactions(transactions)

    # Update price history if we have data
    if all_listings:
        prices = [l["price"] for l in all_listings if l.get("price")]
        sqm_prices = [
            l["price"] / l["sqm"]
            for l in all_listings
            if l.get("price") and l.get("sqm") and l["sqm"] > 0
        ]
        if prices and sqm_prices:
            from statistics import mean, median
            update_price_history(
                avg_price=mean(prices),
                avg_price_per_sqm=mean(sqm_prices),
                listing_count=len(all_listings),
                median_price=median(prices),
            )

    return {
        "yad2_listings": len(yad2),
        "madlan_listings": len(madlan),
        "total_listings": len(all_listings),
        "new_transactions": len(transactions),
        "snapshot_saved": str(snapshot_path),
        "date": date.today().isoformat(),
        "note": (
            "הנתונים נשמרו בהצלחה."
            if all_listings
            else "לא נמצאו מודעות - ייתכן שהאתרים חסמו את הגישה. נסה להפעיל עם Playwright."
        ),
    }


def _tool_get_market_overview(params: dict) -> dict:
    from analysis.market import get_market_overview
    listings = load_latest_listings()
    transactions = load_transactions()
    if not listings and not transactions:
        return {"error": "אין נתונים. הרץ collect_fresh_data תחילה."}
    return get_market_overview(listings, transactions)


def _tool_get_price_history(params: dict) -> dict:
    from analysis.market import get_price_trend
    history = load_price_history()
    if not history:
        return {"error": "אין היסטוריית מחירים. יש לאסוף נתונים מספר פעמים כדי לבנות היסטוריה."}
    return get_price_trend(history)


def _tool_compare_my_apartment(params: dict) -> dict:
    from analysis.comparables import find_comparables, estimate_value
    listings = load_latest_listings()
    if not listings:
        return {"error": "אין נתוני מודעות. הרץ collect_fresh_data תחילה."}
    comps = find_comparables(listings, top_n=10)
    estimation = estimate_value(comps)
    return {
        "subject_apartment": APARTMENT,
        "estimation": estimation,
        "top_comparables": [
            {
                "price": c.get("price"),
                "sqm": c.get("sqm"),
                "rooms": c.get("rooms"),
                "floor": c.get("floor"),
                "address": c.get("address"),
                "elevator": c.get("elevator"),
                "source": c.get("source"),
                "similarity_score": c.get("_similarity"),
                "url": c.get("url"),
            }
            for c in comps[:5]
        ],
    }


def _tool_get_demand_signals(params: dict) -> dict:
    from analysis.market import get_demand_signals, get_transaction_velocity
    snapshots = load_all_snapshots()
    transactions = load_transactions()
    demand = get_demand_signals(snapshots)
    velocity = get_transaction_velocity(transactions)
    return {"demand_signals": demand, "transaction_velocity": velocity}


def _tool_get_recent_transactions(params: dict) -> dict:
    transactions = load_transactions()
    if not transactions:
        return {"error": "אין עסקאות. הרץ collect_fresh_data תחילה."}

    # Sort newest first
    sorted_tx = sorted(transactions, key=lambda x: x.get("date", ""), reverse=True)
    recent = sorted_tx[:20]

    prices = [float(t["price"]) for t in sorted_tx if t.get("price")]
    ppsqm = [float(t["price_per_sqm"]) for t in sorted_tx if t.get("price_per_sqm")]

    from statistics import mean
    return {
        "total_transactions": len(transactions),
        "avg_transaction_price": round(mean(prices)) if prices else None,
        "avg_price_per_sqm": round(mean(ppsqm)) if ppsqm else None,
        "recent_20_transactions": recent,
    }


TOOL_HANDLERS = {
    "collect_fresh_data": _tool_collect_fresh_data,
    "get_market_overview": _tool_get_market_overview,
    "get_price_history": _tool_get_price_history,
    "compare_my_apartment": _tool_compare_my_apartment,
    "get_demand_signals": _tool_get_demand_signals,
    "get_recent_transactions": _tool_get_recent_transactions,
}

# ---------------------------------------------------------------------------
# Claude tool definitions
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "collect_fresh_data",
        "description": (
            "אסוף נתונים עדכניים מיד2, מדלן, ומשרד המשפטים (מס שבח) ושמור אותם לדיסק. "
            "קרא לכלי זה כשהמשתמש מבקש עדכון נתונים או כשהנתונים ישנים."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_market_overview",
        "description": (
            "קבל סקירת שוק נוכחית: ממוצע מחירים, מספר מודעות, מחיר חציוני, "
            "מחיר למ\"ר, עסקאות אחרונות. משתמש בנתונים הקיימים בדיסק."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_price_history",
        "description": (
            "קבל מגמת מחירים לאורך זמן: שינוי % ב-30 יום, 90 יום, 180 יום, שנה. "
            "דורש היסטוריה שנאספה לאורך זמן."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "compare_my_apartment",
        "description": (
            "השווה את הדירה בביאליק 21 (60 מ\"ר, 3 חדרים, קומה 3, ללא מעלית) "
            "לדירות דומות בשוק. מחזיר הערכת שווי וטבלת דירות דומות."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_demand_signals",
        "description": (
            "קבל אינדיקטורי ביקוש: האם מודעות נעלמות מהר? האם כמות המודעות ירדה? "
            "מהירות עסקאות לאורך זמן. מזהיר אם יש ביקוש גבוה."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_recent_transactions",
        "description": (
            "קבל עסקאות סגורות אחרונות ממס שבח בטירת הכרמל (3 חדרים). "
            "כולל מחיר, שטח, קומה, כתובת ותאריך עסקה."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
]

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = f"""אתה אג'נט מומחה נדל"ן המתמחה בשוק הדיור של טירת הכרמל.
אתה עוזר לבעל דירה לעקוב אחרי שווי הדירה שלו ומצב השוק.

**פרטי הדירה של המשתמש:**
- כתובת: {APARTMENT['address']}
- חדרים: {APARTMENT['rooms']}
- שטח: {APARTMENT['sqm']} מ"ר
- קומה: {APARTMENT['floor']} (ללא מעלית)
- ללא עמודים (דירה פתוחה)

**הנחיות:**
- ענה תמיד בעברית, בצורה תמציתית וברורה
- השתמש בכלים לאיסוף וניתוח נתונים לפני שאתה נותן מידע
- אחרי כל ניתוח, הצע לפחות שאלה אחת נוספת שכדאי לבדוק
- אם הנתונים ישנים (יותר מ-3 ימים), המלץ לרענן עם collect_fresh_data
- הצג מחירים בפורמט קריא: 1,850,000 ₪ (לא 1850000)
- כשמציג שינוי מחיר, הסבר תמיד את הסיבות האפשריות
- התרא על סיגנלים חריגים (ביקוש גבוה, ירידת מחירים, עלייה חדה)

**נתונים זמינים:**
- מודעות פעילות מיד2 ומדלן
- עסקאות סגורות ממס שבח (gov.il)
- היסטוריית מחירים מצטברת מסריקות קודמות
"""

# ---------------------------------------------------------------------------
# Main agent loop
# ---------------------------------------------------------------------------

def run_agent():
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        console.print("[red]שגיאה: ANTHROPIC_API_KEY לא מוגדר. הוסף לקובץ .env או לסביבה.[/red]")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)
    conversation: list[dict] = []

    console.print(Panel(
        "[bold cyan]🏠 אג'נט מעקב מחירי דירות - טירת הכרמל[/bold cyan]\n"
        f"[dim]דירה: {APARTMENT['address']} | {APARTMENT['rooms']} חדרים | {APARTMENT['sqm']} מ\"ר[/dim]\n\n"
        "הקלד שאלה בעברית או באנגלית. לצאת: [bold]exit[/bold] / [bold]quit[/bold]",
        border_style="cyan",
    ))

    while True:
        try:
            user_input = Prompt.ask("\n[bold green]אתה[/bold green]")
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]להתראות![/dim]")
            break

        if user_input.strip().lower() in ("exit", "quit", "יציאה"):
            console.print("[dim]להתראות![/dim]")
            break
        if not user_input.strip():
            continue

        conversation.append({"role": "user", "content": user_input})

        # Agentic loop: keep calling until no more tool use
        while True:
            response = client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=4096,
                system=[
                    {
                        "type": "text",
                        "text": SYSTEM_PROMPT,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                tools=TOOLS,
                messages=conversation,
            )

            # Collect text output and tool uses from this response
            tool_uses = []
            text_parts = []

            for block in response.content:
                if block.type == "text":
                    text_parts.append(block.text)
                elif block.type == "tool_use":
                    tool_uses.append(block)

            # Add assistant response to history
            conversation.append({"role": "assistant", "content": response.content})

            # Print any text so far
            if text_parts:
                combined = "\n".join(text_parts)
                console.print(f"\n[bold blue]אג'נט:[/bold blue]")
                console.print(Markdown(combined))

            # Execute tool calls if any
            if response.stop_reason == "tool_use" and tool_uses:
                tool_results = []
                for tool_use in tool_uses:
                    tool_name = tool_use.name
                    console.print(f"[dim]⚙️  מריץ: {tool_name}...[/dim]")
                    handler = TOOL_HANDLERS.get(tool_name)
                    if handler:
                        try:
                            result = handler(tool_use.input or {})
                        except Exception as e:
                            result = {"error": str(e)}
                    else:
                        result = {"error": f"כלי לא מוכר: {tool_name}"}

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": json.dumps(result, ensure_ascii=False),
                    })

                conversation.append({"role": "user", "content": tool_results})
                # Continue loop to let Claude process results
            else:
                # End of this turn
                break


if __name__ == "__main__":
    run_agent()
