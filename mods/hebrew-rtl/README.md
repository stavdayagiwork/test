# hebrew-rtl

A Claude Code mod (function-hooks plugin) that fixes how Hebrew is displayed and keeps Claude's Hebrew output clean.

## What it does

| Surface | Problem | What the mod does |
| --- | --- | --- |
| Terminal without bidi (VS Code integrated terminal, Windows Terminal) | Hebrew letters reversed, word order wrong, left-aligned | Wraps each paragraph to the width, runs a reduced Unicode Bidi Algorithm per line, mirrors brackets, right-aligns RTL rows. Code fences, tables (per cell) and English paragraphs still go through the normal Markdown renderer. |
| Desktop app, VS Code extension | Mixed Hebrew/English in the wrong order | Wraps every Hebrew line in `RLM + RLI ... PDI` after its markdown marker, so the order inside is right whatever direction the container has. |
| All | The model writes direction marks, `dir="rtl"` HTML, em dashes | Strips them from what is drawn (outside code), and adds short Hebrew-writing rules to the system prompt. |

Display only: the stored conversation and what the model reads are not changed.

## Limits

- Desktop / VS Code extension: alignment is CSS and a plugin cannot set `dir`. The RLM helps only when the container uses `dir="auto"`. Order is fixed, right alignment is not guaranteed.
- Terminal: text copied from the terminal is in visual (reversed) order.
- Desktop / VS Code extension: text copied from a Hebrew line carries the invisible RLM/RLI/PDI marks the mod added. Set `richMode: off` if you paste Claude's output into mail or documents often.
- Terminal: rows are cut (not re-wrapped) at the viewport width minus 4 cells. If the transcript is narrower (a docked pane), the end of a row can be cut. The engine's reply bullet is not drawn on rows the mod draws itself.
- Verified by `claude plugin test` (18 tests) against the engine's test kit, not yet visually in every terminal.
- Terminals that already do bidi (GNOME Terminal, Konsole, mlterm) need `terminalMode: off`. Otherwise the text is reversed twice.
- The prompt box you type into is not covered. Your prompt is fixed once it shows in the transcript.
- On the terminal the mod draws Hebrew paragraphs itself: inline bold, inline code and links are kept, italics are not.
- Direction is decided by words: 2 or more Hebrew words, or at least as many Hebrew as Latin words, makes the line RTL.

## Options (`/config`, or `pluginConfigs["hebrew-rtl"].options` in settings)

- `terminalMode`: `visual` (default) or `off`
- `richMode`: `isolate` (default) or `off`
- `promptRules`: `true` (default) or `false`

## Install

Copy this folder to your machine, then:

- Terminal: `claude --plugin-dir /path/to/hebrew-rtl`
- VS Code extension / desktop app: add to `~/.claude/settings.json`:
  `{ "env": { "CLAUDE_CODE_PLUGIN_DIRS": "/path/to/hebrew-rtl" } }` (absolute path; on Windows e.g. `C:\\Users\\you\\mods\\hebrew-rtl`)

## Check

```
claude plugin validate mods/hebrew-rtl
claude plugin test mods/hebrew-rtl
```
