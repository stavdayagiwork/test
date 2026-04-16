#!/usr/bin/env python3
"""
Process Engineering Assistant — Optical Bump Inspection
עוזר תהליכי לאינג'נר מערכת — אינספקציה אופטית של באמפים על צ'יפים
"""

import anthropic

client = anthropic.Anthropic()

SYSTEM_PROMPT = """You are an expert Process Engineering Assistant specializing in optical bump inspection \
for semiconductor packaging. You assist systems engineers with technical questions in both Hebrew and English.

Your expertise covers:
- Bump types: BGA (Ball Grid Array), flip-chip bumps, copper pillars, micro-bumps, solder bumps (SnAg, SnAgCu)
- Optical inspection systems: AOI (Automated Optical Inspection), white-light interferometry, \
  confocal microscopy, structured light, 3D metrology, SEM
- Bump defect classification: missing bumps, collapsed bumps, co-planarity issues (tombstoning), \
  bridging/shorting, oxidation, voids, pad damage, IMC (intermetallic compound) issues
- Industry standards: IPC-7095 (BGA design & assembly), IPC-A-610, JEDEC standards, \
  AEC-Q100/Q101 (automotive), MIL-STD-883
- Statistical process control: CPK, Cp, SPC control charts, Gage R&R, yield analysis, \
  DOE (Design of Experiments), FMEA
- Process parameters: reflow profiles, flux chemistry & residue, under-bump metallurgy (UBM), \
  electroplating parameters, bump height & diameter control
- Inspection equipment vendors: KLA, Rudolph Technologies (Onto Innovation), Camtek, \
  Koh Young, Mirtec, ICOS, Viscom, Saki
- Root cause analysis: 8D, Ishikawa fishbone, 5-Why methodology
- Yield improvement: Pareto analysis, defect mapping, lot traceability

Guidelines:
- Always respond in the same language the user writes in (Hebrew or English)
- Be precise and use correct technical terminology
- Reference relevant standards when applicable
- Provide actionable, concrete recommendations
- Help interpret measurement data and identify root causes
- Assist with writing technical reports and procedures
- When searching for information, prefer recent technical sources and standards
"""

TOOLS = [
    {"type": "web_search_20260209", "name": "web_search"},
    {"type": "web_fetch_20260209", "name": "web_fetch"},
]


def stream_response(messages: list) -> anthropic.types.Message:
    """Stream a response and print text as it arrives. Returns the final message."""
    searching = False

    with client.messages.stream(
        model="claude-opus-4-7",
        max_tokens=8000,
        thinking={"type": "adaptive"},
        system=SYSTEM_PROMPT,
        tools=TOOLS,
        messages=messages,
    ) as stream:
        for event in stream:
            if event.type == "content_block_start":
                block_type = event.content_block.type
                if block_type == "server_tool_use" and not searching:
                    print("\n🔍 מחפש מידע טכני...", flush=True)
                    searching = True

            elif event.type == "content_block_stop":
                searching = False

            elif event.type == "content_block_delta":
                delta = event.delta
                if delta.type == "text_delta":
                    if searching:
                        print()
                        searching = False
                    print(delta.text, end="", flush=True)

        return stream.get_final_message()


def run():
    print("=" * 62)
    print("🔬  עוזר תהליכי — אינספקציה אופטית של באמפים")
    print("    Process Engineering Assistant — Bump Inspection")
    print("=" * 62)
    print("כלים: חיפוש web בזמן אמת | תשובות טכניות | ניתוח תהליך")
    print("הקלד 'יציאה' או 'exit' לסיום\n")

    messages = []

    while True:
        try:
            user_input = input("👤 שאלה: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nשלום!")
            break

        if not user_input:
            continue
        if user_input.lower() in ("יציאה", "exit", "quit", "bye"):
            print("שלום! Goodbye!")
            break

        messages.append({"role": "user", "content": user_input})
        print("\n🤖 ", end="", flush=True)

        # Agentic loop — handles pause_turn when server-side tools hit iteration limit
        while True:
            response = stream_response(messages)
            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason != "pause_turn":
                break

            print("\n⏳ ממשיך חיפוש...", end="", flush=True)

        print("\n")


if __name__ == "__main__":
    run()
