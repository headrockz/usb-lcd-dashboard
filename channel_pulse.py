#!/usr/bin/env python3
"""YouTube Channel Pulse — landscape, thumbnails, big fonts."""

import sys, os, time, json, argparse, io, textwrap
import xml.etree.ElementTree as ET
from datetime import datetime
from urllib.request import Request, urlopen

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shared import *

CHANNEL_ID = os.environ.get("YOUTUBE_CHANNEL", "")
API_KEY = os.environ.get("YOUTUBE_API_KEY", "")
REFRESH_INTERVAL = 3600
SCREEN_REFRESH = 1
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pulse_state.json")
UA = "ZimaScreen/1.0"


def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f: return json.load(f)
        except: pass
    return {"view_history": []}


def save_state(st):
    with open(STATE_FILE, "w") as f: json.dump(st, f)


def http_get(url, timeout=15):
    with urlopen(Request(url, headers={"User-Agent": UA}), timeout=timeout) as r:
        return r.read().decode()


def fetch_image(url, timeout=10):
    with urlopen(Request(url, headers={"User-Agent": UA}), timeout=timeout) as r:
        return Image.open(io.BytesIO(r.read())).convert("RGB")


def fetch_channel_avatar():
    """Get channel avatar from channel page og:image (no API key needed)."""
    import re
    try:
        url = f"https://www.youtube.com/channel/{CHANNEL_ID}"
        html = http_get(url)
        match = re.search(r'<meta property="og:image" content="([^"]+)"', html)
        if match:
            return fetch_image(match.group(1))
    except Exception as e:
        print(f"  Avatar fetch error: {e}")
    return None


def fetch_rss():
    xml_text = http_get(f"https://www.youtube.com/feeds/videos.xml?channel_id={CHANNEL_ID}")
    root = ET.fromstring(xml_text)
    ns = {
        "atom": "http://www.w3.org/2005/Atom",
        "media": "http://search.yahoo.com/mrss/",
        "yt": "http://www.youtube.com/xml/schemas/2015",
    }

    channel_title = root.findtext("atom:title", "", ns)

    videos = []
    for entry in root.findall("atom:entry", ns)[:5]:
        title = entry.findtext("atom:title", "", ns)
        published = entry.findtext("atom:published", "", ns)
        video_id = entry.findtext("yt:videoId", "", ns)
        views_el = entry.find("media:group/media:community/media:statistics", ns)
        views = int(views_el.get("views", 0)) if views_el is not None else 0
        thumb_el = entry.find("media:group/media:thumbnail", ns)
        thumb_url = thumb_el.get("url", "") if thumb_el is not None else ""
        if not thumb_url and video_id:
            thumb_url = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
        date_str = ""
        if published:
            try:
                dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
                date_str = dt.strftime("%d/%m")
            except: pass
        videos.append({"title": title, "views": views, "date": date_str,
                        "video_id": video_id, "thumb_url": thumb_url})
    return channel_title, videos


def fetch_api_subs():
    if not API_KEY: return 0
    try:
        data = json.loads(http_get(
            f"https://www.googleapis.com/youtube/v3/channels?part=statistics&id={CHANNEL_ID}&key={API_KEY}"))
        return int(data["items"][0]["statistics"].get("subscriberCount", 0))
    except: return 0


def fetch_all_data(state):
    channel_title, videos = "", []
    try:
        channel_title, videos = fetch_rss()
    except Exception as e:
        print(f"  RSS error: {e}")

    subs = fetch_api_subs()
    total_views = sum(v["views"] for v in videos)

    # Fetch thumbnails
    for vid in videos:
        if vid.get("thumb_url"):
            try: vid["_thumb"] = fetch_image(vid["thumb_url"])
            except: vid["_thumb"] = None
        else:
            vid["_thumb"] = None

    # Fetch channel avatar
    avatar = None
    try: avatar = fetch_channel_avatar()
    except: pass

    # Track total for delta
    now = time.time()
    vh = state.get("view_history", [])
    if total_views > 0:
        vh.append({"time": now, "views": total_views})
        vh = [h for h in vh if h["time"] > now - 172800]
        state["view_history"] = vh

    delta = 0
    if len(vh) >= 2:
        prev = vh[-2]
        delta = max(0, total_views - prev["views"])

    return {
        "channel": channel_title,
        "videos": videos,
        "total": total_views,
        "subs": subs,
        "delta": delta,
        "avatar": avatar,
    }


def render_frame(data):
    img = new_frame()
    draw = ImageDraw.Draw(img)

    if not data or not data.get("videos"):
        draw.text((20, 80), "LOADING...", fill=GREEN_DIM, font=FONT_BIG)
        draw_corners(draw); return img

    videos = data["videos"]
    total = data["total"]

    # ── Header: avatar + channel name + subs ──
    draw.rectangle([8, 6, W - 9, 8], fill=PURPLE)
    ax = 10
    ay = 10
    avatar = data.get("avatar")
    if avatar:
        av = avatar.resize((28, 28), Image.LANCZOS)
        img.paste(av, (ax, ay))
        draw = ImageDraw.Draw(img)
        ax += 34

    ch_name = data.get("channel", "")
    if ch_name:
        ch_name = truncate(ch_name, FONT_MED, 200, draw)
        draw.text((ax, ay + 4), ch_name, fill=PURPLE, font=FONT_MED)

    if data.get("subs"):
        sub_str = f"{fmt_views(data['subs'])} subs"
        sw = draw.textlength(sub_str, font=FONT_MED)
        draw.text((W - 10 - sw, ay + 4), sub_str, fill=GREEN, font=FONT_MED)

    draw.text((W - 110, ay + 20), "CHANNEL PULSE", fill=GREEN_DIM, font=FONT_TINY)
    draw.rectangle([8, 40, W - 9, 41], fill=PURPLE_DIM)

    # ── Hero: latest video with thumbnail ──
    latest = videos[0]
    hero_y = 46
    thumb_w = 190

    if latest.get("_thumb"):
        src = latest["_thumb"]
        # Preserve aspect ratio: scale width to thumb_w, compute height
        scale = thumb_w / src.width
        thumb_h = int(src.height * scale)
        th = src.resize((thumb_w, thumb_h), Image.LANCZOS)
        img.paste(th, (10, hero_y))
        draw = ImageDraw.Draw(img)
    else:
        thumb_h = 107
        draw.rectangle([10, hero_y, 10 + thumb_w, hero_y + thumb_h], fill=BG_PANEL)
        draw.text((60, hero_y + 40), "No thumb", fill=GRAY, font=FONT_SMALL)

    # Title + views on the right
    rx = 10 + thumb_w + 10
    rw = W - rx - 10

    title_lines = textwrap.wrap(latest["title"], width=22)[:3]
    ty = hero_y + 2
    for line in title_lines:
        line = truncate(line, FONT_MED, rw, draw)
        draw.text((rx, ty), line, fill=GREEN, font=FONT_MED)
        ty += 16

    views_str = fmt_views(latest["views"])
    draw.text((rx, ty + 4), views_str, fill=GREEN, font=FONT_HUGE)
    vw = draw.textlength(views_str, font=FONT_HUGE)
    draw.text((rx + vw + 6, ty + 28), "views", fill=GREEN_DIM, font=FONT_SMALL)

    if latest["date"]:
        draw.text((rx + vw + 6, ty + 12), latest["date"], fill=GRAY, font=FONT_TINY)

    hero_end = hero_y + thumb_h + 4
    draw.rectangle([10, hero_end, W - 10, hero_end + 1], fill=BORDER)
    y = hero_end + 6

    # ── Other videos ──
    for vid in videos[1:]:
        if y > H - 30: break
        v_str = fmt_views(vid["views"])
        draw.text((12, y), v_str, fill=YELLOW, font=FONT_MED)
        vw = draw.textlength(v_str, font=FONT_MED)
        title = truncate(vid["title"], FONT_SMALL, W - vw - 40, draw)
        draw.text((vw + 22, y + 2), title, fill=WHITE_DIM, font=FONT_SMALL)
        y += 20

    # ── Bottom bar ──
    by = H - 16
    total_str = f"Total: {fmt_views(total)}"
    draw.text((10, by), total_str, fill=GRAY, font=FONT_TINY)

    if data.get("delta", 0) > 0:
        d_str = f"+{fmt_views(data['delta'])}"
        dw = draw.textlength(d_str, font=FONT_TINY)
        draw.text((W - 10 - dw, by), d_str, fill=GREEN, font=FONT_TINY)

    draw.text((W // 2 - 20, by), datetime.now().strftime("%H:%M"), fill=GREEN_DIM, font=FONT_TINY)

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

    state = load_state(); data = None; last_fetch = 0
    print(f"Channel Pulse | mode={'API' if API_KEY else 'RSS'}")

    try:
        while True:
            now = time.time()
            if now - last_fetch >= REFRESH_INTERVAL or data is None:
                print("Fetching YouTube data...")
                try: data = fetch_all_data(state); save_state(state)
                except Exception as e: print(f"  Error: {e}")
                last_fetch = now
            img = render_frame(data)
            if args.preview:
                img.save(os.path.join(os.path.dirname(os.path.abspath(__file__)), "channel_pulse_preview.png"))
                print("Saved preview"); return
            screen.show(img)
            time.sleep(SCREEN_REFRESH)
    except KeyboardInterrupt: save_state(state)
    finally:
        if screen: screen.close()


if __name__ == "__main__":
    main()
