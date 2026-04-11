#!/usr/bin/env python3
"""Random Steam game — landscape, big image and title."""

import sys, time, random, json, io, textwrap, argparse, re
from urllib.request import Request, urlopen
from PIL import Image, ImageDraw

sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
from shared import *

UA = "ZimaScreen/1.0"
INTERVAL = 120

def api_get(url, timeout=15):
    with urlopen(Request(url, headers={"User-Agent": UA}), timeout=timeout) as r:
        return json.loads(r.read().decode())

def fetch_image(url, timeout=10):
    with urlopen(Request(url, headers={"User-Agent": UA}), timeout=timeout) as r:
        return Image.open(io.BytesIO(r.read())).convert("RGB")

def load_app_list():
    for url in ["https://api.steampowered.com/ISteamApps/GetAppList/v0002/",
                 "https://api.steampowered.com/ISteamApps/GetAppList/v2/"]:
        try:
            data = api_get(url, timeout=30)
            ids = [a["appid"] for a in data.get("applist", {}).get("apps", []) if a.get("name")]
            if ids: return ids
        except: pass
    # Fallback: featured + random
    ids = set()
    for url in ["https://store.steampowered.com/api/featured/",
                 "https://store.steampowered.com/api/featuredcategories/"]:
        try:
            data = api_get(url, timeout=15)
            for key in ("featured_win", "featured_mac", "featured_linux"):
                for g in data.get(key, []): ids.add(g.get("id", 0))
            for cat in ("specials", "top_sellers", "new_releases"):
                for g in data.get(cat, {}).get("items", []): ids.add(g.get("id", 0))
        except: pass
    for _ in range(500): ids.add(random.randint(200, 2800000))
    ids.discard(0)
    return list(ids)

def fetch_game(app_id):
    data = api_get(f"https://store.steampowered.com/api/appdetails?appids={app_id}")
    entry = data.get(str(app_id), {})
    if not entry.get("success"): return None
    info = entry["data"]
    if info.get("type") != "game": return None
    price = "Free" if info.get("is_free") else (info.get("price_overview", {}).get("final_formatted", "N/A"))
    genres = ", ".join(g["description"] for g in info.get("genres", [])[:3])
    meta = info.get("metacritic", {})
    return {"name": info.get("name", "?"), "header_image": info.get("header_image", ""),
            "short_description": re.sub(r"<[^>]+>", "", info.get("short_description", "")),
            "price": price, "genres": genres, "release_date": info.get("release_date", {}).get("date", "?"),
            "metacritic": meta.get("score")}

def pick_game(app_ids, retries=20):
    for _ in range(retries):
        try:
            game = fetch_game(random.choice(app_ids))
            if game: return game
        except: pass
    return None

def render(game, countdown):
    img = new_frame()
    draw = ImageDraw.Draw(img)

    # ── Fullscreen image — fit, centered ──
    if game.get("_thumb"):
        src = game["_thumb"]
        # Fit image to canvas preserving aspect ratio
        scale = min(W / src.width, H / src.height)
        new_w = int(src.width * scale)
        new_h = int(src.height * scale)
        thumb = src.resize((new_w, new_h), Image.LANCZOS)
        # Center on canvas
        px = (W - new_w) // 2
        py = (H - new_h) // 2
        img.paste(thumb, (px, py))
        draw = ImageDraw.Draw(img)  # refresh draw after paste
    else:
        draw.rectangle([0, 0, W, H], fill=BG_PANEL)
        draw.text((W // 2 - 30, H // 2 - 6), "No image", fill=GRAY, font=FONT_DATA)

    # ── Lower third overlay ──
    lt_h = 80
    lt_y = H - lt_h
    # Semi-transparent dark gradient (draw dark rectangles with decreasing opacity)
    for i in range(20):
        alpha_y = lt_y - 20 + i
        if 0 <= alpha_y < H:
            v = int(i / 20 * 200)
            draw.line([(0, alpha_y), (W, alpha_y)], fill=(BG[0], BG[1], BG[2]))
    draw.rectangle([0, lt_y, W, H], fill=BG)

    # Title — centered, big
    title = truncate(game["name"], FONT_BIG, W - 24, draw)
    tw = draw.textlength(title, font=FONT_BIG)
    draw.text(((W - tw) / 2, lt_y + 4), title, fill=GREEN, font=FONT_BIG)

    # Genre + Price — centered
    info_parts = []
    if game["genres"]:
        info_parts.append(game["genres"])
    info_parts.append(game["price"])
    info_str = "  ·  ".join(info_parts)
    info_str = truncate(info_str, FONT_MED, W - 24, draw)
    iw = draw.textlength(info_str, font=FONT_MED)
    draw.text(((W - iw) / 2, lt_y + 30), info_str, fill=YELLOW, font=FONT_MED)

    # Metacritic + countdown — bottom line
    bottom_y = lt_y + 52
    mins, secs = divmod(max(countdown, 0), 60)
    draw.text((12, bottom_y), f"Next: {mins}:{secs:02d}", fill=GREEN_DIM, font=FONT_SMALL)

    if game["metacritic"] is not None:
        sc = game["metacritic"]
        sc_col = GREEN if sc >= 75 else (ORANGE if sc >= 50 else RED)
        sc_str = f"MC {sc}"
        sw = draw.textlength(sc_str, font=FONT_MED)
        draw.text((W - 12 - sw, bottom_y - 2), sc_str, fill=sc_col, font=FONT_MED)

    draw.text((W // 2 - 18, bottom_y), "STEAM", fill=PURPLE_DIM, font=FONT_TINY)

    draw_corners(draw)
    return img

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--preview", action="store_true")
    args = parser.parse_args()

    print("Loading Steam games...")
    app_ids = load_app_list()
    print(f"Pool: {len(app_ids)} games")

    screen = None
    if not args.preview: screen = Screen()

    current = None; next_pick = 0

    try:
        while True:
            now = time.time()
            if now >= next_pick:
                print("Picking game...")
                game = pick_game(app_ids)
                if game:
                    try: game["_thumb"] = fetch_image(game["header_image"])
                    except: game["_thumb"] = None
                    current = game
                    print(f"  -> {game['name']}")
                next_pick = now + INTERVAL

            if not current: time.sleep(1); continue

            img = render(current, int(next_pick - time.time()))
            if args.preview:
                img.save("/tmp/zima-screens/steam_random_preview.png")
                print("Saved preview"); return
            screen.show(img)
            time.sleep(1)
    except KeyboardInterrupt: pass
    finally:
        if screen: screen.close()

if __name__ == "__main__":
    main()
