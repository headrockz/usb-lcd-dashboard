"""Drawing / rendering for the Zima Monitor dashboard."""

from datetime import datetime
from PIL import Image, ImageDraw

from lcd.constants import (
    W, H, SCREEN_W, SCREEN_H, BG,
    GREEN, GREEN_DIM, PURPLE, PURPLE_DIM,
    BORDER, WHITE_DIM, CYAN, RED, ORANGE,
)
from lcd.drawing import (
    draw_bar, draw_corners,
    FONT_SMALL, FONT_TINY, FONT_BIG, FONT_MEGA, FONT_HEADER, FONT_DATA,
)


# ── Helpers ──────────────────────────────────────────────────

def fmt_uptime(s):
    d, rem = int(s) // 86400, int(s) % 86400
    return f"{d}d {rem // 3600}h" if d else f"{rem // 3600}h {(rem % 3600) // 60}m"


def usage_color(pct, red_threshold, orange_threshold):
    """Return color based on usage percentage."""
    if pct >= red_threshold:
        return RED
    if pct >= orange_threshold:
        return ORANGE
    return GREEN


def temp_color(t, red_threshold, orange_threshold):
    """Return color based on temperature in °C."""
    if t >= red_threshold:
        return RED
    if t >= orange_threshold:
        return ORANGE
    return CYAN


# ── Device panel ─────────────────────────────────────────────

def draw_device(draw, x0, x1, y0, y1, title, accent, stats, thresholds, online=True):
    """Draw one device panel — CPU%, MEM%, TEMP, DISK%, Docker containers."""
    usage_red = thresholds["usage_red"]
    usage_orange = thresholds["usage_orange"]
    temp_red = thresholds["temp_red"]
    temp_orange = thresholds["temp_orange"]

    # Panel border
    draw.rectangle([x0, y0, x1, y1], outline=BORDER, width=1)
    draw.line([(x0, y0), (x0 + 16, y0)], fill=accent, width=2)
    draw.line([(x0, y0), (x0, y0 + 8)], fill=accent, width=2)
    draw.line([(x1 - 16, y1), (x1, y1)], fill=accent, width=2)
    draw.line([(x1, y1 - 8), (x1, y1)], fill=accent, width=2)

    # Title
    tw = draw.textlength(title, font=FONT_DATA)
    draw.rectangle([x0 + 14, y0 - 1, x0 + 18 + tw + 4, y0 + 1], fill=BG)
    draw.text((x0 + 18, y0 - 7), title, fill=accent, font=FONT_DATA)

    # Uptime on the right of the title line
    if online and stats and stats.get("uptime", 0) > 0:
        up_str = f"UP: {fmt_uptime(stats['uptime'])}"
        uw = draw.textlength(up_str, font=FONT_SMALL)
        draw.text((x1 - 10 - uw, y0 - 6), up_str, fill=GREEN_DIM, font=FONT_SMALL)

    if not online or stats is None:
        draw.text((x0 + 30, y0 + 60), "OFFLINE", fill=RED, font=FONT_BIG)
        return

    cpu_bar_red = thresholds.get("cpu_bar_red", 70)
    cpu_bar_orange = thresholds.get("cpu_bar_orange", 55)

    px = x0 + 10
    pw = x1 - x0 - 20
    y = y0 + 12

    # CPU — two sub-panels side by side (load + temp)
    cpu = stats.get("cpu", 0)
    temp = stats.get("temp", 0)
    panel_gap = 6
    panel_w = (pw - panel_gap) // 2

    # Left panel — CPU Load
    lx0, lx1 = px, px + panel_w
    ly0, ly1 = y, y + 52
    draw.rectangle([lx0, ly0, lx1, ly1], outline=BORDER, width=1)
    draw.text((lx0 + 6, ly0 + 3), "CPU LOAD", fill=WHITE_DIM, font=FONT_TINY)
    cpu_str = f"{cpu:.0f}%"
    csw = draw.textlength(cpu_str, font=FONT_BIG)
    cc = usage_color(cpu, cpu_bar_red, cpu_bar_orange)
    draw.text((lx0 + (panel_w - csw) // 2, ly0 + 14), cpu_str, fill=cc, font=FONT_BIG)
    draw_bar(draw, lx0 + 4, ly1 - 12, panel_w - 8, 6, cpu, cc)

    # Right panel — CPU Temp
    rx0, rx1 = lx1 + panel_gap, px + pw
    draw.rectangle([rx0, ly0, rx1, ly1], outline=BORDER, width=1)
    draw.text((rx0 + 6, ly0 + 3), "CPU TEMP", fill=WHITE_DIM, font=FONT_TINY)
    temp_str = f"{temp:.0f}\u00b0C"
    tsw = draw.textlength(temp_str, font=FONT_BIG)
    tc = temp_color(temp, cpu_bar_red, cpu_bar_orange)
    draw.text((rx0 + (rx1 - rx0 - tsw) // 2, ly0 + 14), temp_str, fill=tc, font=FONT_BIG)
    temp_pct = min(temp, 100)
    draw_bar(draw, rx0 + 4, ly1 - 12, (rx1 - rx0) - 8, 6, temp_pct, tc)

    y = ly1 + 6

    # MEM
    mem = stats.get("mem_pct", 0)
    mc = usage_color(mem, usage_red, usage_orange)
    draw.text((px, y), "MEM", fill=WHITE_DIM, font=FONT_SMALL)
    mem_used = stats.get("mem_used_gb", 0)
    mem_total = stats.get("mem_total_gb", 0)
    mem_detail = f"{mem_used:.0f}/{mem_total:.0f}GB"
    draw.text((px + 30, y + 1), mem_detail, fill=GREEN, font=FONT_TINY)
    mem_str = f"{mem:.0f}%"
    mw = draw.textlength(mem_str, font=FONT_MEGA)
    draw.text((x1 - 10 - mw, y - 2), mem_str, fill=mc, font=FONT_MEGA)
    y += 26
    draw_bar(draw, px, y, pw, 8, mem, mc)
    y += 14

    # DISK
    disk = stats.get("disk_pct", 0)
    dc = usage_color(disk, usage_red, usage_orange)
    draw.text((px, y), "DISK", fill=WHITE_DIM, font=FONT_SMALL)
    disk_used = stats.get("disk_used_gb", 0)
    disk_total = stats.get("disk_total_gb", 0)
    disk_detail = f"{disk_used:.0f}/{disk_total:.0f}GB"
    draw.text((px + 30, y + 1), disk_detail, fill=GREEN, font=FONT_TINY)
    disk_str = f"{disk:.0f}%"
    diskw = draw.textlength(disk_str, font=FONT_MEGA)
    draw.text((x1 - 10 - diskw, y - 2), disk_str, fill=dc, font=FONT_MEGA)
    y += 22
    draw_bar(draw, px, y, pw, 6, disk, dc)
    y += 12

    # DOCKER containers — two sub-panels side by side
    docker_running = stats.get("docker_running", 0)
    docker_stopped = stats.get("docker_stopped", 0)
    panel_gap = 6
    panel_w = (pw - panel_gap) // 2

    # Left panel — Running
    lx0, lx1 = px, px + panel_w
    ly0, ly1 = y, y1 - 4
    draw.rectangle([lx0, ly0, lx1, ly1], outline=BORDER, width=1)
    draw.text((lx0 + 6, ly0 + 3), "\u25b6 RUNNING", fill=GREEN, font=FONT_TINY)
    run_str = str(docker_running)
    rw = draw.textlength(run_str, font=FONT_BIG)
    draw.text((lx0 + (panel_w - rw) // 2, ly0 + 14), run_str, fill=GREEN, font=FONT_BIG)

    # Right panel — Stopped
    rx0, rx1 = lx1 + panel_gap, px + pw
    draw.rectangle([rx0, ly0, rx1, ly1], outline=BORDER, width=1)
    draw.text((rx0 + 6, ly0 + 3), "\u25a0 STOPPED", fill=RED, font=FONT_TINY)
    stop_str = str(docker_stopped)
    sw = draw.textlength(stop_str, font=FONT_BIG)
    draw.text((rx0 + (rx1 - rx0 - sw) // 2, ly0 + 14), stop_str, fill=RED, font=FONT_BIG)


# ── Frame composition ────────────────────────────────────────

def _make_canvas(cw, ch):
    """Create a blank canvas with scanline texture."""
    img = Image.new("RGB", (cw, ch), BG)
    draw = ImageDraw.Draw(img)
    for sy in range(0, ch, 3):
        draw.line([(0, sy), (cw, sy)], fill=(255, 255, 255), width=1)
    bg_over = Image.new("RGB", (cw, ch), BG)
    return Image.blend(img, bg_over, 0.92)


def _draw_header(draw, cw, monitor_text):
    """Draw the title bar and return the y coordinate right below it."""
    draw.rectangle([8, 6, cw - 9, 8], fill=PURPLE)
    words = monitor_text.split()
    first_word = words[0] if words else ""
    rest_words = " ".join(words[1:]) if len(words) > 1 else ""
    draw.text((10, 10), first_word, fill=PURPLE, font=FONT_BIG)
    if rest_words:
        fw = draw.textlength(first_word, font=FONT_BIG)
        draw.text((10 + fw + 6, 14), rest_words, fill=GREEN, font=FONT_HEADER)
    draw.rectangle([8, 34, cw - 9, 35], fill=PURPLE_DIM)
    return 42


def render_frame(local, remote, config):
    """Render a complete frame and return the PIL Image."""
    cw = config["cw"]
    ch = config["ch"]
    is_portrait = config["is_portrait"]
    monitor_text = config["monitor_text"]
    server_1_title = config["server_1_title"]
    server_2_title = config["server_2_title"]
    thresholds = config["thresholds"]

    img = _make_canvas(cw, ch)
    draw = ImageDraw.Draw(img)

    y0 = _draw_header(draw, cw, monitor_text)

    if is_portrait:
        mid_y = y0 + (ch - y0 - 16) // 2
        draw_device(draw, 8, cw - 9, y0, mid_y - 4,
                    server_1_title, GREEN, local, thresholds, local is not None)
        draw_device(draw, 8, cw - 9, mid_y + 4, ch - 16,
                    server_2_title, PURPLE, remote, thresholds, remote is not None)
    else:
        mid_x = cw // 2
        draw_device(draw, 8, mid_x - 4, y0, ch - 16,
                    server_1_title, GREEN, local, thresholds, local is not None)
        draw_device(draw, mid_x + 4, cw - 9, y0, ch - 16,
                    server_2_title, PURPLE, remote, thresholds, remote is not None)

    # Clock bottom-right
    now = datetime.now()
    ts = now.strftime("%H:%M:%S")
    tw = draw.textlength(ts, font=FONT_TINY)
    draw.text((cw - 10 - tw, ch - 14), ts, fill=GREEN_DIM, font=FONT_TINY)

    draw_corners(draw, cw, ch)
    return img
