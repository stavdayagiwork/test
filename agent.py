#!/usr/bin/env python3
"""
General Technical Process Assistant — Semiconductor Packaging & Inspection
עוזר טכני כללי לתהליך — אריזת שבבים ואינספקציה
"""

import os
import re
from datetime import datetime

import anthropic

client = anthropic.Anthropic()

SYSTEM_PROMPT = """You are an expert Technical Process Assistant for semiconductor packaging and inspection. \
You assist systems engineers with all stages of the process, in both Hebrew and English.

## Bump Technology & Optical Inspection (core expertise)
- Bump types: BGA (Ball Grid Array), flip-chip bumps, copper pillars, micro-bumps, solder bumps (SnAg, SnAgCu)
- Optical inspection: AOI, white-light interferometry, confocal microscopy, structured light, 3D metrology, SEM
- Bump defects: missing bumps, collapsed bumps, co-planarity, bridging/shorting, oxidation, voids, IMC issues
- Inspection vendors: KLA, Onto Innovation (Rudolph), Camtek, Koh Young, Mirtec, ICOS, Viscom, Saki

## Fabrication & Assembly Process
- UBM (Under-Bump Metallurgy): Ti/Cu/Ni/Au stack, deposition methods, adhesion issues
- Electroplating: Cu/Sn/Ag plating, bath chemistry, current density, thickness uniformity
- Solder paste printing (SPI): stencil design, paste rheology, aperture ratio, bridging
- Reflow: profile design (ramp/soak/peak/cool), flux activation, voiding mechanisms, tombstoning
- Flux chemistry: no-clean vs. water-soluble, activity levels (ROL0/ROL1), residue impact on AOI

## Design & Layout
- Bump design rules: pitch, diameter, height, land size, solder mask opening (SMO vs. NSMD)
- Co-planarity specs: JEDEC/IPC requirements, impact of substrate warpage
- DRC/DFM for flip-chip and BGA packages

## Failure Analysis
- Cross-section preparation, polishing, etching
- EDX / EDS for elemental analysis, IMC characterization (Cu3Sn, Cu6Sn5)
- FIB (Focused Ion Beam), EBSD, TEM for advanced characterization
- X-ray (2D/3D CT): void detection, joint quality, bridging

## Reliability & Qualification
- Thermal cycling (TC), drop test (JEDEC JESD22-B111), HTSL, HAST, electromigration
- Weibull analysis, characteristic life (η), shape parameter (β)
- AEC-Q100/Q101 (automotive), MIL-STD-883, IPC-9701

## Industry Standards
- IPC-7095 (BGA design & assembly), IPC-A-610 (acceptability), IPC-7711/7721 (rework)
- JEDEC standards (JESD22, JESD47, JESD94)
- IPC-2221/2222 (PCB design), J-STD-001/020

## Quality & Statistics
- SPC: Xbar-R/S charts, IMR charts, control limits (UCL/LCL), out-of-control rules (Nelson/Western Electric)
- Process capability: Cp, Cpk, Pp, Ppk — interpretation and improvement strategies
- Gage R&R: %GRR, discrimination ratio, crossed vs. nested study
- DOE: full factorial, fractional factorial (Taguchi), ANOVA, response surface
- FMEA (PFMEA/DFMEA): RPN, severity/occurrence/detection ratings
- Root cause analysis: 8D, Ishikawa fishbone, 5-Why, Is/Is-Not analysis
- Yield analysis: Poisson model, defect density, Pareto, defect mapping, lot traceability

## Data Analysis (when code execution is available)
- If the user uploads a CSV/Excel file, analyze it automatically
- Calculate CPK, SPC charts, histograms, scatter plots, control charts
- Use pandas, numpy, scipy, matplotlib, seaborn for analysis
- Save generated plots as PNG files and report file names

## Guidelines
- Respond in the same language the user writes in (Hebrew or English)
- Be precise with technical terminology; cite standards when relevant
- Provide actionable, concrete recommendations with quantitative targets where possible
- Help interpret measurement data, identify root causes, and suggest corrective actions
- Assist with writing technical reports, work instructions, and engineering specifications
"""

TOOLS = [
    {"type": "web_search_20260209", "name": "web_search"},
    {"type": "web_fetch_20260209", "name": "web_fetch"},
    {"type": "code_execution_20260120", "name": "code_execution"},
]

HELP_TEXT = """
פקודות זמינות / Available commands:
  /file <path>  — טעינת קובץ CSV/Excel לניתוח | Load a data file for analysis
  /save         — שמירת השיחה כ-Markdown       | Save conversation as Markdown
  /help         — הצגת עזרה זו                 | Show this help
  יציאה / exit  — סיום                          | Quit

דוגמאות שימוש / Usage examples:
  /file ./measurements.csv
  חשב CPK ובצע SPC chart
  מה ה-CPK המינימלי לפי IPC-7095?
  איך לפתור בעיית missing bumps בתהליך reflow?
"""


def upload_file(path: str) -> str:
    """Upload a local file to the Anthropic Files API and return its file_id."""
    with open(path, "rb") as f:
        meta = client.beta.files.upload(file=f)
    return meta.id


def build_user_content(text: str, file_id: str | None) -> list | str:
    """Build message content, attaching a file to the code execution container if provided."""
    if not file_id:
        return text
    return [
        {"type": "text", "text": text},
        {"type": "container_upload", "file_id": file_id},
    ]


def save_session(messages: list) -> str:
    """Save the conversation history to a Markdown file."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"session_{timestamp}.md"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(f"# Technical Process Assistant — Session {timestamp}\n\n")
        for msg in messages:
            role_label = "**👤 שאלה**" if msg["role"] == "user" else "**🤖 עוזר**"
            content = msg["content"]
            if isinstance(content, list):
                text_parts = [b["text"] for b in content if isinstance(b, dict) and b.get("type") == "text"]
                content = " ".join(text_parts)
            elif not isinstance(content, str):
                # assistant content blocks
                text_parts = []
                for block in content:
                    if hasattr(block, "type") and block.type == "text":
                        text_parts.append(block.text)
                content = " ".join(text_parts)
            f.write(f"{role_label}\n\n{content}\n\n---\n\n")
    return filename


def stream_response(messages: list) -> anthropic.types.Message:
    """Stream a response and print text as it arrives. Returns the final message."""
    tool_active = False

    with client.messages.stream(
        model="claude-opus-4-7",
        max_tokens=8000,
        thinking={"type": "adaptive"},
        system=SYSTEM_PROMPT,
        tools=TOOLS,
        messages=messages,
        extra_headers={"anthropic-beta": "files-api-2025-04-14"},
    ) as stream:
        for event in stream:
            if event.type == "content_block_start":
                block_type = event.content_block.type
                if block_type == "server_tool_use" and not tool_active:
                    name = getattr(event.content_block, "name", "")
                    if name == "web_search":
                        print("\n🔍 מחפש מידע טכני...", flush=True)
                    elif name == "web_fetch":
                        print("\n🌐 טוען דף...", flush=True)
                    elif name == "code_execution":
                        print("\n⚙️  מריץ קוד לניתוח נתונים...", flush=True)
                    tool_active = True

            elif event.type == "content_block_stop":
                tool_active = False

            elif event.type == "content_block_delta":
                delta = event.delta
                if delta.type == "text_delta":
                    if tool_active:
                        print()
                        tool_active = False
                    print(delta.text, end="", flush=True)

        return stream.get_final_message()


def run():
    print("=" * 64)
    print("⚙️   עוזר טכני כללי לתהליך — אריזת שבבים ואינספקציה")
    print("    General Technical Process Assistant")
    print("=" * 64)
    print("כלים: חיפוש web | הרצת קוד | ניתוח קבצי נתונים")
    print("הקלד /help לרשימת פקודות | 'יציאה' לסיום\n")

    messages = []
    pending_file_id: str | None = None

    while True:
        try:
            user_input = input("👤 שאלה: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nשלום!")
            break

        if not user_input:
            continue

        # Built-in commands
        if user_input.lower() in ("יציאה", "exit", "quit", "bye"):
            print("שלום! Goodbye!")
            break

        if user_input.lower() in ("/help", "עזרה"):
            print(HELP_TEXT)
            continue

        if user_input.lower() == "/save":
            if not messages:
                print("אין שיחה לשמירה.\n")
                continue
            saved = save_session(messages)
            print(f"✅ השיחה נשמרה: {saved}\n")
            continue

        # /file <path>
        file_match = re.match(r"^/file\s+(.+)$", user_input)
        if file_match:
            path = file_match.group(1).strip()
            if not os.path.isfile(path):
                print(f"❌ קובץ לא נמצא: {path}\n")
                continue
            try:
                print(f"📤 מעלה קובץ: {os.path.basename(path)} ...", flush=True)
                pending_file_id = upload_file(path)
                print(f"✅ הקובץ הועלה בהצלחה. כעת שאל מה לנתח.\n")
            except Exception as e:
                print(f"❌ שגיאה בהעלאת הקובץ: {e}\n")
            continue

        # Build content — attach file if pending
        content = build_user_content(user_input, pending_file_id)
        pending_file_id = None

        messages.append({"role": "user", "content": content})
        print("\n🤖 ", end="", flush=True)

        # Agentic loop — handles pause_turn when server-side tools hit iteration limit
        while True:
            response = stream_response(messages)
            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason != "pause_turn":
                break

            print("\n⏳ ממשיך...", end="", flush=True)

        print("\n")


if __name__ == "__main__":
    run()
