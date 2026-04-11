#!/usr/bin/env python3
"""Discord server monitor — landscape, big and minimal."""

import sys, os, time, json, argparse, re, textwrap
from datetime import datetime, timezone, timedelta
from urllib.request import Request, urlopen

from PIL import ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shared import *

GUILD_ID = os.environ.get("GUILD_ID", "")
REFRESH_INTERVAL = 3600
SCREEN_REFRESH = 1

CHANNEL_NAME = os.environ.get("DISCORD_CHANNEL", "general")

def _load_token():
    token = os.environ.get("DISCORD_TOKEN")
    if token: return token
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                if line.strip().startswith("DISCORD_TOKEN="):
                    return line.strip().split("=", 1)[1].strip().strip('"').strip("'")
    return None

TOKEN = _load_token()

def discord_get(path, timeout=10):
    if not TOKEN: return None
    try:
        req = Request(f"https://discord.com/api/v10{path}",
                      headers={"Authorization": f"Bot {TOKEN}", "User-Agent": "ZimaScreen/1.0"})
        with urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print(f"Discord API: {e}")
        return None

def find_channel():
    channels = discord_get(f"/guilds/{GUILD_ID}/channels")
    if not channels: return None
    for ch in channels:
        name = ch.get("name", "")
        if name == CHANNEL_NAME or name.endswith(CHANNEL_NAME):
            return ch["id"]
    return None

def snowflake_from_time(dt):
    epoch = datetime(2015, 1, 1, tzinfo=timezone.utc)
    return str(int((dt - epoch).total_seconds() * 1000) << 22)

def fetch_recent_messages(channel_id, limit=3):
    msgs = discord_get(f"/channels/{channel_id}/messages?limit={limit}")
    if not msgs: return []
    result = []
    for m in msgs:
        author = m.get("author", {}).get("global_name") or m.get("author", {}).get("username", "?")
        content = re.sub(r"<@!?\d+>", "@user", m.get("content", ""))
        content = re.sub(r"<#\d+>", "#ch", content)
        content = re.sub(r"<a?:\w+:\d+>", "", content)
        if not content:
            content = "[media]" if m.get("attachments") or m.get("embeds") else "[...]"
        result.append({"author": author, "content": content})
    return result

def fetch_all_data():
    cid = find_channel()
    data = {"messages": [], "online": 0, "members": 0, "hour_count": 0}
    guild = discord_get(f"/guilds/{GUILD_ID}?with_counts=true")
    if guild:
        data["members"] = guild.get("approximate_member_count", 0)
        data["online"] = guild.get("approximate_presence_count", 0)
    if cid:
        data["messages"] = fetch_recent_messages(cid, 3)
        one_h = datetime.now(timezone.utc) - timedelta(hours=1)
        hour_msgs = discord_get(f"/channels/{cid}/messages?after={snowflake_from_time(one_h)}&limit=100")
        data["hour_count"] = len(hour_msgs) if hour_msgs else 0
    return data

def render_frame(data):
    img = new_frame()
    draw = ImageDraw.Draw(img)

    # Header
    draw.rectangle([8, 6, W - 9, 8], fill=PURPLE)
    draw.text((10, 10), "DISCORD", fill=PURPLE, font=FONT_BIG)
    label = f"#{CHANNEL_NAME.upper()}"
    draw.text((90, 14), label, fill=GREEN, font=FONT_MED)
    if data:
        on_str = f"{data.get('online', 0)} online"
        ow = draw.textlength(on_str, font=FONT_SMALL)
        draw.text((W - 10 - ow, 14), on_str, fill=GREEN, font=FONT_SMALL)
        hr_str = f"{data.get('hour_count', 0)} msgs/h"
        hw = draw.textlength(hr_str, font=FONT_SMALL)
        draw.text((W - 10 - hw, 26), hr_str, fill=YELLOW, font=FONT_SMALL)
    draw.rectangle([8, 36, W - 9, 37], fill=PURPLE_DIM)

    if not TOKEN:
        draw.text((20, 100), "TOKEN NOT SET", fill=RED, font=FONT_MEGA)
        draw_corners(draw); return img

    if not data:
        draw.text((20, 100), "LOADING...", fill=GREEN_DIM, font=FONT_BIG)
        draw_corners(draw); return img

    messages = data.get("messages", [])
    if not messages:
        draw.text((20, 100), "No messages", fill=GRAY, font=FONT_BIG)
        draw_corners(draw); return img

    # 3 message rows — big fonts
    row_h = 86
    y0 = 42
    accents = [GREEN, CYAN, ORANGE]
    for i, msg in enumerate(messages[:3]):
        ry = y0 + i * (row_h + 2)

        # Row border
        draw.rectangle([8, ry, W - 9, ry + row_h], outline=BORDER, width=1)
        accent = accents[i % len(accents)]
        draw.line([(8, ry), (24, ry)], fill=accent, width=2)
        draw.line([(8, ry), (8, ry + 8)], fill=accent, width=2)

        # Author — medium
        author = truncate(msg["author"], FONT_MED, W - 36, draw)
        draw.text((14, ry + 4), author, fill=accent, font=FONT_MED)

        # Message — BIG, up to 3 lines
        content = msg["content"]
        lines = textwrap.wrap(content, width=28)[:3]
        iy = ry + 22
        for line in lines:
            t = truncate(line, FONT_BIG, W - 36, draw)
            draw.text((14, iy), t, fill=WHITE_DIM, font=FONT_BIG)
            iy += 22

    # Clock
    now = datetime.now()
    draw.text((10, H - 14), now.strftime("%H:%M:%S"), fill=GREEN_DIM, font=FONT_TINY)
    draw_corners(draw)
    return img

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--preview", action="store_true")
    args = parser.parse_args()

    screen = None
    if not args.preview:
        try: screen = Screen()
        except Exception as e: print(f"Screen not found: {e}"); sys.exit(1)

    data = None; last_fetch = 0
    print(f"Discord Monitor | token={'set' if TOKEN else 'MISSING'}")

    try:
        while True:
            now = time.time()
            if now - last_fetch >= REFRESH_INTERVAL or data is None:
                print("Fetching Discord data...")
                try: data = fetch_all_data(); print(f"  msgs/h: {data.get('total_hour', 0)}")
                except Exception as e: print(f"  Error: {e}")
                last_fetch = now
            img = render_frame(data)
            if args.preview:
                img.save(os.path.join(os.path.dirname(os.path.abspath(__file__)), "discord_preview.png"))
                print("Saved preview"); return
            screen.show(img)
            time.sleep(SCREEN_REFRESH)
    except KeyboardInterrupt: pass
    finally:
        if screen: screen.close()

if __name__ == "__main__":
    main()
