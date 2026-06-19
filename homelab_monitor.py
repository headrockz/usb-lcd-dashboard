#!/usr/bin/env python3
"""Homelab Monitor — dual server dashboard for USB LCD."""

import sys, os, time, argparse, logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dotenv

from lcd.constants import W, H, SCREEN_W, SCREEN_H
from lcd.screen import Screen
from homelab_monitor.stats import get_local_stats, get_docker_stats
from homelab_monitor.remote import get_remote_stats
from homelab_monitor.ui import render_frame

# ── Configuration ────────────────────────────────────────────

dotenv.load_dotenv()

MONITOR_TEXT    = os.getenv("MONITOR_TEXT", "HOMELAB MONITOR")
SERVER_1_TITLE  = os.getenv("SERVER_1_TITLE", "FALCON")
SERVER_2_TITLE  = os.getenv("SERVER_2_TITLE", "TIE")

ORIENTATION = os.getenv("MONITOR_ORIENTATION", "landscape").lower().strip()
IS_PORTRAIT = ORIENTATION == "portrait"
CW = SCREEN_W if IS_PORTRAIT else W
CH = SCREEN_H if IS_PORTRAIT else H

REMOTE_IP       = os.environ.get("REMOTE_IP", "")
REMOTE_SSH_USER = os.environ.get("REMOTE_SSH_USER", "")

REFRESH_INTERVAL = 1
REMOTE_INTERVAL  = 30

USAGE_RED    = int(os.getenv("USAGE_RED",    "80"))
USAGE_ORANGE = int(os.getenv("USAGE_ORANGE", "60"))
TEMP_RED     = int(os.getenv("TEMP_RED",     "75"))
TEMP_ORANGE  = int(os.getenv("TEMP_ORANGE",  "60"))
CPU_BAR_RED    = int(os.getenv("CPU_BAR_RED",    "70"))
CPU_BAR_ORANGE = int(os.getenv("CPU_BAR_ORANGE", "55"))

logging.basicConfig(level=logging.WARNING)

# ── Main ─────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--preview", action="store_true")
    args = parser.parse_args()

    screen = None
    if not args.preview:
        try:
            screen = Screen()
        except Exception as e:
            print(f"Screen not found: {e}")
            sys.exit(1)

    config = {
        "cw": CW,
        "ch": CH,
        "is_portrait": IS_PORTRAIT,
        "monitor_text": MONITOR_TEXT,
        "server_1_title": SERVER_1_TITLE,
        "server_2_title": SERVER_2_TITLE,
        "thresholds": {
            "usage_red": USAGE_RED,
            "usage_orange": USAGE_ORANGE,
            "temp_red": TEMP_RED,
            "temp_orange": TEMP_ORANGE,
            "cpu_bar_red": CPU_BAR_RED,
            "cpu_bar_orange": CPU_BAR_ORANGE,
        },
    }

    remote_stats = None
    last_remote = 0.0
    last_docker = 0.0

    print(f"Homelab Monitor | remote={REMOTE_IP}")

    try:
        while True:
            now_t = time.time()
            local = None
            try:
                local = get_local_stats()
            except:
                pass

            # Docker stats (local) — every 30s
            if local and (now_t - last_docker) >= REMOTE_INTERVAL:
                last_docker = now_t
                dr, ds = get_docker_stats()
                local["docker_running"] = dr
                local["docker_stopped"] = ds

            # Remote stats — every 30s
            if (now_t - last_remote) >= REMOTE_INTERVAL:
                last_remote = now_t
                try:
                    r = get_remote_stats(REMOTE_IP, REMOTE_SSH_USER)
                    if r:
                        remote_stats = r
                except:
                    pass

            img = render_frame(local, remote_stats, config)

            if args.preview:
                img.save(os.path.join(
                    os.path.dirname(os.path.abspath(__file__)),
                    "homelab_monitor_preview.png",
                ))
                print("Saved preview")
                break

            screen.show(img)
            time.sleep(REFRESH_INTERVAL)
    except KeyboardInterrupt:
        pass
    finally:
        if screen:
            screen.close()


if __name__ == "__main__":
    main()
