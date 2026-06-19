"""
UI drawing helpers, fonts and frame layouts.
"""

import os
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from lcd.constants import (
    W, H, BG, PURPLE, GREEN, PURPLE_DIM, GREEN_DIM,
    BORDER, GREEN_DARK, BORDER_HI, BG_PANEL
)
from lcd.helpers import truncate

# ── Font loading ───────────────────────────────────────────────
_package_dir = os.path.dirname(os.path.abspath(__file__))
_root_dir = os.path.dirname(_package_dir)

def load_font(size):
    candidates = [
        os.path.join(_root_dir, "JetBrainsMono.ttf"),
        "/usr/share/fonts/truetype/jetbrains-mono/JetBrainsMono-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        os.path.expanduser("~/Library/Fonts/JetBrainsMono[wght].ttf"),
        "/System/Library/Fonts/SFNSMono.ttf",
        "/System/Library/Fonts/Menlo.ttc",
    ]
    for p in candidates:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()

FONT_HEADER = load_font(15)
FONT_TITLE  = load_font(11)
FONT_DATA   = load_font(11)
FONT_BIG    = load_font(22)
FONT_HUGE   = load_font(48)
FONT_SMALL  = load_font(11)
FONT_TINY   = load_font(10)
FONT_MED    = load_font(13)
FONT_MEGA   = load_font(36)

# ── Drawing helpers ────────────────────────────────────────────
def new_frame():
    """Create a new frame with background and scanlines."""
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    for sy in range(0, H, 3):
        draw.line([(0, sy), (W, sy)], fill=(255, 255, 255), width=1)
    bg_over = Image.new("RGB", (W, H), BG)
    img = Image.blend(img, bg_over, 0.92)
    return img

def draw_header(draw, title, subtitle=None):
    """Draw standard header with purple bar and title."""
    x1 = W - 9
    y = 8
    draw.rectangle([8, y, x1, y + 2], fill=PURPLE)
    y += 6
    draw.text((10, y), title, fill=PURPLE, font=FONT_BIG)
    if subtitle:
        tx = 10 + draw.textlength(title, font=FONT_BIG) + 10
        draw.text((tx, y + 4), subtitle, fill=GREEN, font=FONT_HEADER)
    y += 26
    draw.rectangle([8, y, x1, y + 1], fill=PURPLE_DIM)
    y += 4
    now = datetime.now()
    draw.text((10, y), f"▌{now.strftime('%H:%M:%S')}", fill=GREEN_DIM, font=FONT_TINY)
    draw.text((100, y), "◆ ONLINE", fill=GREEN, font=FONT_TINY)
    draw.text((170, y), f"▌{now.strftime('%Y-%m-%d')}", fill=GREEN_DIM, font=FONT_TINY)
    return y + 14  # next available y

def draw_footer(draw):
    """Draw standard footer with clock and heartbeat."""
    now = datetime.now()
    x1 = W - 9
    fy = H - 22
    draw.rectangle([8, fy, x1, fy + 1], fill=BORDER)
    fy += 5
    beat = "●" if now.second % 2 == 0 else "○"
    draw.text((10, fy), beat, fill=GREEN if now.second % 2 == 0 else GREEN_DARK, font=FONT_SMALL)
    draw.text((22, fy), now.strftime("%H:%M:%S"), fill=GREEN, font=FONT_DATA)
    draw.text((105, fy), now.strftime("%a %Y-%m-%d"), fill=PURPLE_DIM, font=FONT_DATA)

def draw_corners(draw, w=None, h=None):
    """Draw decorative corner accents. Uses W/H by default."""
    cw = w if w is not None else W
    ch = h if h is not None else H
    for (cx, cy, col) in [(0, 0, PURPLE), (cw-1, 0, PURPLE), (0, ch-1, GREEN), (cw-1, ch-1, GREEN)]:
        dx = 1 if cx == 0 else -1
        dy = 1 if cy == 0 else -1
        draw.line([(cx, cy), (cx + 6*dx, cy)], fill=col, width=2)
        draw.line([(cx, cy), (cx, cy + 6*dy)], fill=col, width=2)

def draw_panel(draw, y0, y1, title="", accent=GREEN):
    """Draw a bordered panel with accent corners and optional title."""
    x0, x1 = 8, W - 9
    draw.rectangle([x0, y0, x1, y1], outline=BORDER, width=1)
    draw.line([(x0, y0), (x0 + 16, y0)], fill=accent, width=2)
    draw.line([(x0, y0), (x0, y0 + 8)], fill=accent, width=2)
    draw.line([(x1 - 16, y1), (x1, y1)], fill=accent, width=2)
    draw.line([(x1, y1 - 8), (x1, y1)], fill=accent, width=2)
    if title:
        tw = draw.textlength(title, font=FONT_TITLE)
        tx = x0 + 22
        draw.rectangle([tx - 4, y0 - 1, tx + tw + 4, y0 + 1], fill=BG)
        draw.text((tx, y0 - 7), title, fill=accent, font=FONT_TITLE)

def draw_bar(draw, x, y, w, h, pct, color=GREEN):
    """Draw a progress bar."""
    draw.rectangle([x, y, x + w, y + h], fill=GREEN_DARK)
    fill_w = int(w * min(pct, 100) / 100)
    if fill_w > 0:
        draw.rectangle([x, y, x + fill_w, y + h], fill=color)
        if fill_w > 2:
            tip = tuple(min(255, c + 60) for c in color)
            draw.line([(x + fill_w - 1, y), (x + fill_w - 1, y + h)], fill=tip)
    draw.rectangle([x, y, x + w, y + h], outline=BORDER_HI, width=1)

def draw_sparkline(draw, x, y, w, h, data, color=GREEN):
    """Draw a mini sparkline chart."""
    if not data or len(data) < 2:
        return
    draw.rectangle([x, y, x + w, y + h], fill=BG_PANEL)
    n = len(data)
    mn, mx = min(data), max(data)
    rng = mx - mn if mx != mn else 1
    step = w / (n - 1)
    points = [(x + i * step, y + h - ((v - mn) / rng) * h) for i, v in enumerate(data)]
    fill_pts = points + [(x + w, y + h), (x, y + h)]
    draw.polygon(fill_pts, fill=tuple(c // 6 for c in color))
    draw.line(points, fill=color, width=1)
