#!/usr/bin/env python3
"""Pomodoro timer — landscape, big and minimal."""

import sys, os, json, time, argparse
from datetime import datetime
from PIL import ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shared import *

STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pomodoro_state.json")

DEFAULT_FOCUS = 25
DEFAULT_SHORT_BREAK = 5
DEFAULT_LONG_BREAK = 15
POMOS_PER_SET = 4
LONG_BREAK_EVERY = 4

FOCUS_MIN = DEFAULT_FOCUS
SHORT_BREAK_MIN = DEFAULT_SHORT_BREAK
LONG_BREAK_MIN = DEFAULT_LONG_BREAK

def load_state():
    today = datetime.now().strftime("%Y-%m-%d")
    default = {"phase": "FOCUS", "remaining": FOCUS_MIN * 60,
               "completed": 0, "focus_secs_today": 0, "date": today}
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                st = json.load(f)
            if st.get("date") != today:
                st["focus_secs_today"] = 0
                st["completed"] = 0
                st["date"] = today
            return st
        except Exception:
            pass
    return default

def save_state(st):
    st["date"] = datetime.now().strftime("%Y-%m-%d")
    with open(STATE_FILE, "w") as f:
        json.dump(st, f)

def phase_duration(phase, completed):
    if phase == "FOCUS":
        return FOCUS_MIN * 60
    if completed > 0 and completed % LONG_BREAK_EVERY == 0:
        return LONG_BREAK_MIN * 60
    return SHORT_BREAK_MIN * 60

def advance_phase(st):
    if st["phase"] == "FOCUS":
        st["completed"] += 1
        st["phase"] = "BREAK"
    else:
        st["phase"] = "FOCUS"
    st["remaining"] = phase_duration(st["phase"], st["completed"])

def render_frame(st):
    img = new_frame()
    draw = ImageDraw.Draw(img)

    phase = st["phase"]
    remaining = max(0, int(st["remaining"]))
    total = phase_duration(phase, st["completed"])
    elapsed = total - remaining
    pct = (elapsed / total * 100) if total > 0 else 0
    accent = GREEN if phase == "FOCUS" else ORANGE

    # Phase label — top left
    label = "FOCUS" if phase == "FOCUS" else "BREAK"
    draw.text((14, 10), label, fill=accent, font=FONT_MEGA)

    # Pomodoro dots — top right
    completed = st["completed"] % POMOS_PER_SET
    dot_x = W - 14 - POMOS_PER_SET * 30
    for i in range(POMOS_PER_SET):
        sym = "●" if i < completed else "○"
        col = accent if i < completed else GRAY
        draw.text((dot_x + i * 30, 16), sym, fill=col, font=FONT_BIG)

    # Giant timer — centered
    mins, secs = divmod(remaining, 60)
    timer_str = f"{mins:02d}:{secs:02d}"
    tw = draw.textlength(timer_str, font=FONT_HUGE)
    tx = (W - tw) / 2
    ty = 70
    # Glow effect
    for offset in [3, 2, 1]:
        g = tuple(c // (offset + 1) for c in accent)
        for dx, dy in [(-offset, 0), (offset, 0), (0, -offset), (0, offset)]:
            draw.text((tx + dx, ty + dy), timer_str, fill=g, font=FONT_HUGE)
    draw.text((tx, ty), timer_str, fill=accent, font=FONT_HUGE)

    # Progress bar — wide
    bar_y = 140
    draw_bar(draw, 14, bar_y, W - 28, 16, pct, accent)

    # Bottom info: today's focus + session count
    by = 170
    total_focus = st["focus_secs_today"]
    fh = total_focus // 3600
    fm = (total_focus % 3600) // 60
    focus_str = f"{fh}h {fm}m" if fh > 0 else f"{fm}m focused"
    draw.text((14, by), focus_str, fill=GREEN_DIM, font=FONT_MED)

    # Session count
    sess_str = f"#{st['completed']}"
    sw = draw.textlength(sess_str, font=FONT_MED)
    draw.text((W - 14 - sw, by), sess_str, fill=WHITE_DIM, font=FONT_MED)

    # Next phase hint
    by += 18
    if phase == "FOCUS":
        draw.text((14, by), f"then {SHORT_BREAK_MIN}min break", fill=GRAY, font=FONT_TINY)
    else:
        draw.text((14, by), f"then {FOCUS_MIN}min focus", fill=GRAY, font=FONT_TINY)

    # Heartbeat
    now = datetime.now()
    beat = "●" if now.second % 2 == 0 else "○"
    draw.text((14, H - 18), beat, fill=accent if now.second % 2 == 0 else GRAY, font=FONT_SMALL)
    draw.text((26, H - 18), now.strftime("%H:%M:%S"), fill=GREEN_DIM, font=FONT_SMALL)

    draw_corners(draw)
    return img

def main():
    global FOCUS_MIN, SHORT_BREAK_MIN, LONG_BREAK_MIN

    parser = argparse.ArgumentParser(description="Pomodoro Timer")
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--work", type=int, default=DEFAULT_FOCUS)
    parser.add_argument("--break", type=int, dest="short_break", default=DEFAULT_SHORT_BREAK)
    parser.add_argument("--long-break", type=int, default=DEFAULT_LONG_BREAK)
    args = parser.parse_args()

    FOCUS_MIN = args.work
    SHORT_BREAK_MIN = args.short_break
    LONG_BREAK_MIN = args.long_break

    st = load_state()
    if st["phase"] == "FOCUS" and st["remaining"] > FOCUS_MIN * 60:
        st["remaining"] = FOCUS_MIN * 60

    screen = None
    if not args.preview:
        try:
            screen = Screen()
        except Exception as e:
            print(f"Screen not found: {e}"); sys.exit(1)

    print(f"Pomodoro: work={FOCUS_MIN}m break={SHORT_BREAK_MIN}m")
    last_tick = time.time()

    try:
        while True:
            now = time.time()
            dt = now - last_tick
            last_tick = now
            if st["phase"] == "FOCUS":
                st["focus_secs_today"] += dt
            st["remaining"] -= dt
            if st["remaining"] <= 0:
                advance_phase(st)
                print(f"Phase: {st['phase']}")
            img = render_frame(st)
            if args.preview:
                img.save(os.path.join(os.path.dirname(os.path.abspath(__file__)), "pomodoro_preview.png"))
                print("Saved pomodoro_preview.png"); save_state(st); break
            screen.show(img)
            save_state(st)
            time.sleep(1)
    except KeyboardInterrupt:
        save_state(st)
    finally:
        if screen: screen.close()

if __name__ == "__main__":
    main()
