# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Dashboard screens for a 3.5" USB IPS LCD (320×480, Turing Smart Screen Rev A protocol) driven over serial. Five screens (system monitor, Discord, YouTube, Pomodoro, Steam discovery) managed by a web controller. Built for ZimaBoard but works on any Linux/macOS machine with a compatible USB screen.

## Running

```bash
# Install (Python 3.8+, venv recommended)
pip install -r requirements.txt

# Start web controller (manages all screens, serves on port 9595)
python3 web_controller.py

# Run a single screen directly
python3 steam_random.py
python3 pomodoro.py --work 25 --break 5

# Preview mode — saves PNG instead of sending to screen (no hardware needed)
python3 steam_random.py --preview
```

There are no tests, linter, or build system. The project is plain Python scripts with no package structure.

## Architecture

**Canvas model**: All drawing happens on a 480×320 landscape `Image`. `shared.Screen.show()` rotates it 90° to portrait (320×480), converts to RGB565, and streams over serial in chunks. Full refresh ≈ 1–2 seconds.

**shared.py** is the foundation — every screen imports `from shared import *`. It provides:
- `Screen` class (serial driver: handshake, brightness, bitmap send)
- `new_frame()` creates a scanline-textured background
- Drawing helpers: `draw_header`, `draw_footer`, `draw_corners`, `draw_panel`, `draw_bar`, `draw_sparkline`, `truncate`
- Color palette constants (`BG`, `GREEN`, `PURPLE`, `ORANGE`, etc.) and pre-loaded font objects (`FONT_BIG`, `FONT_HUGE`, etc.)
- Canvas dimensions: `W=480, H=320` (landscape), `SCREEN_W=320, SCREEN_H=480` (physical)

**Screen scripts** all follow the same pattern:
1. Parse args (including `--preview`)
2. Open `Screen()` (or skip if preview)
3. Fetch data, render with Pillow, call `screen.show(img)` in a loop
4. `screen.show()` also saves `current_frame.png` for the web UI live preview

**web_controller.py** runs on port 9595 (stdlib `http.server`, no framework). It launches screen scripts as subprocesses, plays a boot transition animation between switches, and serves an inline HTML/CSS/JS dashboard. Environment is loaded from `.env` with a manual parser (not python-dotenv).

**transition.py** draws an 8-bit boot animation (static noise → console text → segmented loading bar) directly on the screen hardware.

**State files** (gitignored): `pomodoro_state.json` (timer state, resets daily), `pulse_state.json` (YouTube view history for delta tracking).

## Environment variables

Configured via `.env` (see `.env.example`). Most screens work without config:
- Pomodoro and Steam Discovery need zero config
- Zima Monitor works in local-only mode without `REMOTE_IP`
- Channel Pulse works without API key (uses YouTube RSS)
- Discord Monitor requires `DISCORD_TOKEN` and `GUILD_ID`

## Key constraints

- The screen is ≈1–2 FPS. Layouts are static dashboards, not animations.
- All rendering is Pillow `ImageDraw` — no HTML/CSS on the LCD, just pixel-level drawing.
- Font: JetBrains Mono (`JetBrainsMono.ttf` in project dir or system fonts). All text is drawn in monospace at specific pixel sizes.
- Web UI descriptions are in Portuguese (pt-BR). Screen rendering is in English.
