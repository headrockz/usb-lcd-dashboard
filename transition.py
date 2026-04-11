#!/usr/bin/env python3
"""8-bit console boot transition animation for the USB LCD screen."""

import sys, os, time, random
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shared import *

# 8-bit console palette
C_BLACK = (0, 0, 0)
C_DARK  = (16, 8, 32)
C_BG    = (8, 2, 20)

def play_transition(screen, screen_name="LOADING", frames=3):
    """Play an 8-bit console boot animation on the USB screen."""
    total_frames = frames

    # 3 frames: static → boot text complete → loading bar full
    phases = [
        lambda d: _draw_static(d, 0.8),
        lambda d: _draw_boot_text(d, 1.0, screen_name),
        lambda d: _draw_loading_bar(d, 1.0, screen_name),
    ]
    for i in range(min(total_frames, len(phases))):
        img = Image.new("RGB", (W, H), C_BLACK)
        draw = ImageDraw.Draw(img)
        phases[i](draw)
        screen.show(img)


def _draw_static(draw, p):
    """TV static noise effect — power on."""
    intensity = int(p * 80)
    block = 4
    for y in range(0, H, block):
        for x in range(0, W, block):
            if random.random() < 0.3 * p:
                v = random.randint(0, intensity)
                c = (v, v // 2, v + random.randint(0, 20))
                draw.rectangle([x, y, x + block - 1, y + block - 1], fill=c)
    # CRT border glow
    if p > 0.5:
        g = int((p - 0.5) * 2 * 40)
        for i in range(3):
            draw.rectangle([i, i, W - 1 - i, H - 1 - i],
                           outline=(g // 3, 0, g))


def _draw_scanline_sweep(draw, p):
    """Scanlines sweep from top to bottom."""
    sweep_y = int(p * H)
    # Dark background with scanlines above sweep
    for y in range(0, sweep_y, 2):
        brightness = max(0, 20 - abs(y - sweep_y) // 4)
        draw.line([(0, y), (W, y)], fill=(0, brightness // 2, brightness))
    # Bright sweep line
    if sweep_y < H:
        for dy in range(-2, 3):
            yy = sweep_y + dy
            if 0 <= yy < H:
                v = 80 - abs(dy) * 20
                draw.line([(0, yy), (W, yy)], fill=(0, v, v))
    # Above sweep: subtle purple bg
    if sweep_y > 10:
        draw.rectangle([0, 0, W, min(sweep_y - 5, H)], fill=C_DARK)
        for y in range(0, min(sweep_y - 5, H), 3):
            draw.line([(0, y), (W, y)], fill=(12, 4, 28))


def _draw_boot_text(draw, p, name):
    """Console boot text appearing line by line."""
    draw.rectangle([0, 0, W, H], fill=C_DARK)
    # Scanlines
    for y in range(0, H, 3):
        draw.line([(0, y), (W, y)], fill=(16, 8, 32))

    lines = [
        ("ZIMA SYSTEM", PURPLE),
        ("", None),
        ("Initializing display...", GREEN_DIM),
        ("Screen: 320x480 IPS [OK]", GREEN_DIM),
        ("Serial: USB35INCHIPSV2 [OK]", GREEN_DIM),
        ("Protocol: Turing Rev.A [OK]", GREEN_DIM),
        ("", None),
        (f"Loading: {name}", GREEN),
    ]

    visible = int(p * len(lines)) + 1
    y = 20
    for i, (text, color) in enumerate(lines[:visible]):
        if not text:
            y += 8
            continue
        # Typing effect for last visible line
        if i == visible - 1 and p < 0.95:
            frac = (p * len(lines)) - i
            chars = int(frac * len(text))
            text = text[:chars]
            # Cursor blink
            if int(time.time() * 4) % 2 == 0:
                text += "█"
        draw.text((14, y), text, fill=color, font=FONT_SMALL)
        y += 14

    # Blinking cursor at bottom
    if p > 0.7:
        draw.text((14, y + 8), "> _" if int(time.time() * 3) % 2 == 0 else ">", fill=GREEN, font=FONT_SMALL)


def _draw_loading_bar(draw, p, name):
    """Loading bar with percentage."""
    draw.rectangle([0, 0, W, H], fill=C_DARK)
    for y in range(0, H, 3):
        draw.line([(0, y), (W, y)], fill=(12, 4, 28))

    # Boot text (all complete)
    lines = ["ZIMA SYSTEM", "", "Initializing display...", "Screen: 320x480 IPS [OK]",
             "Serial: USB35INCHIPSV2 [OK]", "Protocol: Turing Rev.A [OK]", "", f"Loading: {name}"]
    y = 20
    for text in lines:
        if not text: y += 8; continue
        draw.text((14, y), text, fill=GREEN_DIM, font=FONT_SMALL)
        y += 14

    y += 16

    # Progress bar
    bar_w = W - 60
    bar_x = 30
    pct = min(p, 1.0)
    draw.rectangle([bar_x, y, bar_x + bar_w, y + 14], outline=PURPLE_DIM, width=1)
    fill_w = int(bar_w * pct)
    if fill_w > 0:
        # Pixel-art style segmented bar
        seg_w = 6
        for sx in range(bar_x + 1, bar_x + fill_w, seg_w + 1):
            end_x = min(sx + seg_w - 1, bar_x + fill_w)
            draw.rectangle([sx, y + 1, end_x, y + 13], fill=GREEN)

    # Percentage
    pct_str = f"{int(pct * 100)}%"
    pw = draw.textlength(pct_str, font=FONT_DATA)
    draw.text(((W - pw) / 2, y + 18), pct_str, fill=GREEN, font=FONT_DATA)


def _draw_fadeout(draw, p, name):
    """Fade to the target screen's background."""
    # Blend from console to target BG
    r = int(C_DARK[0] * (1 - p) + BG[0] * p)
    g = int(C_DARK[1] * (1 - p) + BG[1] * p)
    b = int(C_DARK[2] * (1 - p) + BG[2] * p)
    draw.rectangle([0, 0, W, H], fill=(r, g, b))

    # Fading "READY" text
    if p < 0.6:
        alpha = int((1 - p / 0.6) * 255)
        col = (0, min(255, alpha), int(alpha * 0.25))
        rw = draw.textlength("READY", font=FONT_BIG)
        draw.text(((W - rw) / 2, H // 2 - 12), "READY", fill=col, font=FONT_BIG)


def preview():
    """Save transition frames as preview images."""
    import os
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "transition_preview")
    os.makedirs(out_dir, exist_ok=True)

    fps = 15
    duration = 2.0
    total = int(duration * fps)
    for frame in range(total):
        t = frame / total
        img = Image.new("RGB", (W, H), C_BLACK)
        draw = ImageDraw.Draw(img)

        if t < 0.15: _draw_static(draw, t / 0.15)
        elif t < 0.35: _draw_scanline_sweep(draw, (t - 0.15) / 0.2)
        elif t < 0.6: _draw_boot_text(draw, (t - 0.35) / 0.25, "ZIMA MONITOR")
        elif t < 0.8: _draw_loading_bar(draw, (t - 0.6) / 0.2, "ZIMA MONITOR")
        else: _draw_fadeout(draw, (t - 0.8) / 0.2, "ZIMA MONITOR")

        img.save(os.path.join(out_dir, f"frame_{frame:03d}.png"))

    # Save a few key frames as regular previews
    for i, t in enumerate([0.05, 0.25, 0.45, 0.7, 0.9]):
        frame = int(t * total)
        img = Image.open(os.path.join(out_dir, f"frame_{frame:03d}.png"))
        img.save(os.path.join(os.path.dirname(os.path.abspath(__file__)), f"transition_{i}.png"))

    print(f"Saved {total} frames to {out_dir}/")


if __name__ == "__main__":
    preview()
