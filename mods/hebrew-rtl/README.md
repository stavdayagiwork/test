# hebrew-rtl

A Claude Code mod (function-hooks plugin) that fixes how Hebrew is displayed and keeps Claude's Hebrew output clean.

## What it does

| Surface | Problem | What the mod does |
| --- | --- | --- |
| Terminal without bidi (VS Code integrated terminal, Windows Terminal) | Hebrew letters reversed, word order wrong, left-aligned | Wraps each paragraph to the width, runs a reduced Unicode Bidi Algorithm per line, mirrors brackets, right-aligns RTL rows. Code fences, tables (per cell) and English paragraphs still go through the normal Markdown renderer. |
| Desktop app, VS Code extension | Mixed Hebrew/English in the wrong order | Wraps every Hebrew line in `RLM + RLI ... PDI` after its markdown marker, so the order inside is right whatever direction the container has. |
| Claude app (cloud sessions), any host that draws the conversation itself | The bubble is drawn left to right: `אני עושה טסט ל VSCODE לטקסט` comes out with its parts in the wrong order | These hosts never call the engine's drawing hooks (checked: `session.surfaces()` is empty, no `ui.render` call arrives). So the mod writes `RLM + RLI ... PDI` into the text itself: your prompt at `prompt.submit`, each reply at `session.append`. |
| All | The model writes direction marks, `dir="rtl"` HTML, em dashes | Strips them from what is drawn (outside code), and adds short Hebrew-writing rules to the system prompt. |

The drawing hooks change the display only. `textMarks` (on by default) does change the stored text: it adds invisible direction marks to Hebrew lines of your prompts and Claude's replies.

## Limits

- Desktop / VS Code extension: alignment is CSS and a plugin cannot set `dir`. The RLM helps only when the container uses `dir="auto"`. Order is fixed, right alignment is not guaranteed.
- Terminal: text copied from the terminal is in visual (reversed) order.
- Desktop / VS Code extension: text copied from a Hebrew line carries the invisible RLM/RLI/PDI marks the mod added. Set `richMode: off` if you paste Claude's output into mail or documents often.
- Terminal: rows are cut (not re-wrapped) at the viewport width minus 4 cells. If the transcript is narrower (a docked pane), the end of a row can be cut. The engine's reply bullet is not drawn on rows the mod draws itself.
- Verified by `claude plugin test` (20 tests) against the engine's test kit. The text-marks path is the one that reaches the Claude app; the display paths are verified by tests only.
- Terminals that already do bidi (GNOME Terminal, Konsole, mlterm) need `terminalMode: off`. Otherwise the text is reversed twice.
- The prompt box you type into is not covered: it belongs to the app or VS Code. On Windows, Ctrl + Right Shift in a Chromium text box (Claude app, VS Code) switches it to right-to-left, and Ctrl + Left Shift switches it back. Your prompt is fixed once it shows in the transcript.
- On the terminal the mod draws Hebrew paragraphs itself: inline bold, inline code and links are kept, italics are not.
- Direction is decided by words: 2 or more Hebrew words, or at least as many Hebrew as Latin words, makes the line RTL.

## Options (`/config`, or `pluginConfigs["hebrew-rtl"].options` in settings)

- `terminalMode`: `visual` (default) or `off`
- `richMode`: `isolate` (default) or `off`
- `textMarks`: `true` (default) or `false`
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
