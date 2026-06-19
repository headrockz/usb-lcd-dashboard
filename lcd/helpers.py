"""
Formatting and logical color helper utilities.
"""

from lcd.constants import GREEN, ORANGE, RED

def usage_color(pct):
    if pct >= 90:
        return RED
    if pct >= 75:
        return ORANGE
    return GREEN

def temp_color(t):
    if t >= 70:
        return RED
    if t >= 55:
        return ORANGE
    return GREEN

def fmt_bytes(mb):
    return f"{mb / 1000:.1f}G" if mb >= 1000 else f"{mb}M"

def fmt_views(n):
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1000:
        return f"{n / 1000:.1f}K"
    return str(n)

def truncate(text, font, max_width, draw):
    """Truncate text with ellipsis to fit max_width."""
    if draw.textlength(text, font=font) <= max_width:
        return text
    while len(text) > 1 and draw.textlength(text + "…", font=font) > max_width:
        text = text[:-1]
    return text + "…"
