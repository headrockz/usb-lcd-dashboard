#!/usr/bin/env python3
"""Dual Zima monitor — landscape, big and minimal. Side-by-side panels."""

import sys, os, time, argparse, logging, subprocess
from collections import deque
from datetime import datetime

from PIL import ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shared import *

REMOTE_IP       = os.environ.get("REMOTE_IP", "")
REMOTE_API_PORT = int(os.environ.get("REMOTE_API_PORT", "8080"))
REMOTE_USER     = os.environ.get("REMOTE_USER", "")
REMOTE_PASS     = os.environ.get("REMOTE_PASS", "")
REMOTE_SSH_USER = os.environ.get("REMOTE_SSH_USER", "")

REFRESH_INTERVAL = 1
REMOTE_INTERVAL  = 30
HISTORY_LEN      = 40

log = logging.getLogger("zima_monitor")
logging.basicConfig(level=logging.WARNING)
_warned = False

# ── Local stats ──────────────────────────────────────────────

def get_local_stats():
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=0)
        mem = psutil.virtual_memory()
        temp = 0.0
        try:
            temps = psutil.sensors_temperatures()
            for n in ("coretemp", "cpu_thermal", "k10temp", "soc_dts0"):
                if n in temps and temps[n]:
                    temp = temps[n][0].current; break
            if temp == 0 and temps:
                temp = next(iter(temps.values()))[0].current
        except Exception: pass
        disk_pct = 0.0
        for m in ("/DATA", "/"):
            try: d = psutil.disk_usage(m); disk_pct = d.percent; break
            except: continue
        return {"cpu": cpu, "mem_pct": mem.percent, "temp": temp, "disk_pct": disk_pct,
                "net_sent": psutil.net_io_counters().bytes_sent,
                "net_recv": psutil.net_io_counters().bytes_recv,
                "uptime": time.time() - psutil.boot_time()}
    except ImportError:
        # /proc fallback
        stats = {"cpu": 0, "mem_pct": 0, "temp": 0, "disk_pct": 0, "net_sent": 0, "net_recv": 0, "uptime": 0}
        try:
            p = open("/proc/stat").readline().split()
            t = sum(int(x) for x in p[1:]); stats["cpu"] = round((1 - int(p[4]) / max(t, 1)) * 100, 1)
        except: pass
        try:
            mi = {}
            for line in open("/proc/meminfo"):
                k, v = line.split(":"); mi[k.strip()] = int(v.strip().split()[0])
            t = mi.get("MemTotal", 0); a = mi.get("MemAvailable", 0)
            stats["mem_pct"] = round((t - a) / max(t, 1) * 100, 1)
        except: pass
        try: stats["temp"] = int(open("/sys/class/thermal/thermal_zone0/temp").read()) / 1000
        except: pass
        try:
            s = os.statvfs("/DATA" if os.path.exists("/DATA") else "/")
            stats["disk_pct"] = round((1 - s.f_bfree / max(s.f_blocks, 1)) * 100, 1)
        except: pass
        try: stats["uptime"] = float(open("/proc/uptime").read().split()[0])
        except: pass
        return stats

# ── Remote stats ─────────────────────────────────────────────

_jwt_token = None; _jwt_time = 0

def _api_get(path):
    import urllib.request, json as _j
    global _jwt_token, _jwt_time
    base = f"http://{REMOTE_IP}:{REMOTE_API_PORT}"
    now = time.time()
    if _jwt_token is None or (now - _jwt_time) > 3500:
        try:
            req = urllib.request.Request(f"{base}/v1/users/login",
                data=_j.dumps({"username": REMOTE_USER, "password": REMOTE_PASS}).encode(),
                headers={"Content-Type": "application/json"}, method="POST")
            body = _j.loads(urllib.request.urlopen(req, timeout=5).read())
            _jwt_token = body.get("data", {}).get("token") or body.get("token")
            _jwt_time = now
            if not _jwt_token: return None
        except: return None
    try:
        req = urllib.request.Request(f"{base}{path}", headers={"Authorization": f"Bearer {_jwt_token}"})
        return _j.loads(urllib.request.urlopen(req, timeout=5).read())
    except: return None

def _remote_api():
    if not REMOTE_PASS: return None
    cpu = _api_get("/v1/sys/cpu")
    mem = _api_get("/v1/sys/mem")
    if not cpu: return None
    def v(r, *ks):
        d = (r or {}).get("data", r or {})
        for k in ks: d = d.get(k, 0) if isinstance(d, dict) else 0
        return d
    return {"cpu": v(cpu, "percent") or v(cpu, "usage"),
            "mem_pct": v(mem, "percent") or v(mem, "usedPercent"),
            "temp": v(cpu, "temperature") or v(cpu, "temp"),
            "disk_pct": 0, "net_sent": 0, "net_recv": 0}

def _remote_ssh():
    cmd = "head -1 /proc/stat; echo '---'; head -3 /proc/meminfo; echo '---'; cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null || echo 0; echo '---'; df -P /DATA 2>/dev/null || df -P /; echo '---'; cat /proc/net/dev 2>/dev/null"
    try:
        r = subprocess.run(["ssh", "-o", "ConnectTimeout=3", "-o", "StrictHostKeyChecking=no",
                            f"{REMOTE_SSH_USER}@{REMOTE_IP}", cmd], capture_output=True, text=True, timeout=8)
        if r.returncode != 0: return None
        secs = r.stdout.split("---")
        if len(secs) < 3: return None
        stats = {"cpu": 0, "mem_pct": 0, "temp": 0, "disk_pct": 0, "net_sent": 0, "net_recv": 0}
        p = secs[0].strip().split()
        if len(p) > 4:
            t = sum(int(x) for x in p[1:]); stats["cpu"] = round((1 - int(p[4]) / max(t, 1)) * 100, 1)
        mi = {}
        for line in secs[1].strip().splitlines():
            if ":" in line: k, v = line.split(":"); mi[k.strip()] = int(v.strip().split()[0])
        t = mi.get("MemTotal", 0); a = mi.get("MemAvailable", 0)
        stats["mem_pct"] = round((t - a) / max(t, 1) * 100, 1)
        try: stats["temp"] = int(secs[2].strip()) / 1000
        except: pass
        if len(secs) > 3:
            for line in secs[3].strip().splitlines():
                parts = line.split()
                if len(parts) >= 5 and parts[0] != "Filesystem":
                    try: stats["disk_pct"] = float(parts[4].rstrip("%"))
                    except: pass
        if len(secs) > 4:
            for line in secs[4].strip().splitlines():
                if ":" in line and "lo:" not in line:
                    parts = line.split(":")[1].split()
                    if len(parts) >= 9:
                        try:
                            stats["net_recv"] += int(parts[0])
                            stats["net_sent"] += int(parts[8])
                        except: pass
        return stats
    except: return None

def get_remote_stats():
    global _warned
    r = _remote_api()
    if r: return r
    if not _warned: log.warning("API unavailable, trying SSH"); _warned = True
    return _remote_ssh()

# ── Helpers ──────────────────────────────────────────────────

def fmt_uptime(s):
    d, s = int(s) // 86400, int(s) % 86400
    return f"{d}d {s // 3600}h" if d else f"{s // 3600}h {(s % 3600) // 60}m"

def net_speed(prev, curr, dt):
    if prev is None or dt <= 0: return 0
    return max(0, curr - prev) / 1048576 / dt

# ── Drawing ──────────────────────────────────────────────────

def draw_device(draw, x0, x1, y0, y1, title, accent, stats, net_hist=None, online=True):
    """Draw one device panel — CPU%, MEM%, TEMP, DISK%, NET sparkline."""
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

    if not online or stats is None:
        draw.text((x0 + 30, y0 + 60), "OFFLINE", fill=RED, font=FONT_BIG)
        return

    px = x0 + 10
    pw = x1 - x0 - 20
    y = y0 + 12

    # CPU — big percentage
    cpu = stats.get("cpu", 0)
    cc = usage_color(cpu)
    draw.text((px, y), "CPU", fill=WHITE_DIM, font=FONT_SMALL)
    cpu_str = f"{cpu:.0f}%"
    cw = draw.textlength(cpu_str, font=FONT_MEGA)
    draw.text((x1 - 10 - cw, y - 6), cpu_str, fill=cc, font=FONT_MEGA)
    y += 36
    draw_bar(draw, px, y, pw, 8, cpu, cc)
    y += 14

    # MEM — big percentage
    mem = stats.get("mem_pct", 0)
    mc = usage_color(mem)
    draw.text((px, y), "MEM", fill=WHITE_DIM, font=FONT_SMALL)
    mem_str = f"{mem:.0f}%"
    mw = draw.textlength(mem_str, font=FONT_MEGA)
    draw.text((x1 - 10 - mw, y - 6), mem_str, fill=mc, font=FONT_MEGA)
    y += 36
    draw_bar(draw, px, y, pw, 8, mem, mc)
    y += 14

    # TEMP
    temp = stats.get("temp", 0)
    tc = temp_color(temp)
    draw.text((px, y), "TEMP", fill=WHITE_DIM, font=FONT_SMALL)
    temp_str = f"{temp:.0f}°C"
    tempw = draw.textlength(temp_str, font=FONT_BIG)
    draw.text((x1 - 10 - tempw, y - 2), temp_str, fill=tc, font=FONT_BIG)
    y += 28

    # DISK
    disk = stats.get("disk_pct", 0)
    dc = usage_color(disk)
    draw.text((px, y), "DISK", fill=WHITE_DIM, font=FONT_SMALL)
    disk_str = f"{disk:.0f}%"
    diskw = draw.textlength(disk_str, font=FONT_BIG)
    draw.text((x1 - 10 - diskw, y - 2), disk_str, fill=dc, font=FONT_BIG)
    y += 22
    draw_bar(draw, px, y, pw, 6, disk, dc)
    y += 12

    # NET sparkline
    draw.text((px, y), "NET", fill=WHITE_DIM, font=FONT_SMALL)
    if net_hist and len(net_hist) >= 2:
        speed = net_hist[-1]
        speed_str = f"{speed:.1f} MB/s"
        sw = draw.textlength(speed_str, font=FONT_TINY)
        draw.text((x1 - 10 - sw, y), speed_str, fill=CYAN, font=FONT_TINY)
    y += 12
    sh = min(y1 - y - 4, 40)
    if net_hist and len(net_hist) >= 2 and sh > 10:
        draw_sparkline(draw, px, y, pw, sh, list(net_hist), CYAN)
    elif sh > 10:
        draw.rectangle([px, y, px + pw, y + sh], fill=BG_PANEL)

def render_frame(local, remote, uptime, local_net_hist=None, remote_net_hist=None):
    img = new_frame()
    draw = ImageDraw.Draw(img)

    # Minimal header
    draw.rectangle([8, 6, W - 9, 8], fill=PURPLE)
    draw.text((10, 10), "ZIMA", fill=PURPLE, font=FONT_BIG)
    draw.text((70, 14), "MONITOR", fill=GREEN, font=FONT_HEADER)
    if uptime:
        up_str = f"UP {fmt_uptime(uptime)}"
        uw = draw.textlength(up_str, font=FONT_TINY)
        draw.text((W - 10 - uw, 14), up_str, fill=GREEN_DIM, font=FONT_TINY)
    draw.rectangle([8, 34, W - 9, 35], fill=PURPLE_DIM)

    # Two panels side by side
    y0, y1 = 42, H - 16
    mid = W // 2
    draw_device(draw, 8, mid - 4, y0, y1, "ZIMABOARD", GREEN, local, local_net_hist, local is not None)
    draw_device(draw, mid + 4, W - 9, y0, y1, "ZIMACUBE", PURPLE, remote, remote_net_hist, remote is not None)

    # Clock bottom-right
    now = datetime.now()
    ts = now.strftime("%H:%M:%S")
    tw = draw.textlength(ts, font=FONT_TINY)
    draw.text((W - 10 - tw, H - 14), ts, fill=GREEN_DIM, font=FONT_TINY)

    draw_corners(draw)
    return img

# ── Main ─────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--preview", action="store_true")
    args = parser.parse_args()

    screen = None
    if not args.preview:
        try: screen = Screen()
        except Exception as e: print(f"Screen not found: {e}"); sys.exit(1)

    remote_stats = None
    last_remote = 0.0

    # Network speed history
    local_net_hist = deque(maxlen=HISTORY_LEN)
    remote_net_hist = deque(maxlen=HISTORY_LEN)
    prev_local_net = None
    prev_local_time = None
    prev_remote_net = None
    prev_remote_time = None

    print(f"Zima Monitor | remote={REMOTE_IP}")

    try:
        while True:
            now_t = time.time()
            local = None
            try: local = get_local_stats()
            except: pass

            # Track local network speed
            if local:
                net_total = local.get("net_sent", 0) + local.get("net_recv", 0)
                if prev_local_net is not None and prev_local_time is not None:
                    dt = now_t - prev_local_time
                    if dt > 0:
                        speed = (net_total - prev_local_net) / 1048576 / dt
                        local_net_hist.append(max(0, speed))
                prev_local_net = net_total
                prev_local_time = now_t

            if (now_t - last_remote) >= REMOTE_INTERVAL:
                last_remote = now_t
                try:
                    r = get_remote_stats()
                    if r:
                        # Track remote network speed
                        rnet = r.get("net_sent", 0) + r.get("net_recv", 0)
                        if prev_remote_net is not None and prev_remote_time is not None:
                            dt = now_t - prev_remote_time
                            if dt > 0 and rnet > 0:
                                speed = (rnet - prev_remote_net) / 1048576 / dt
                                remote_net_hist.append(max(0, speed))
                        prev_remote_net = rnet
                        prev_remote_time = now_t
                        remote_stats = r
                except: pass

            uptime = local.get("uptime", 0) if local else 0
            img = render_frame(local, remote_stats, uptime, local_net_hist, remote_net_hist)

            if args.preview:
                img.save(os.path.join(os.path.dirname(os.path.abspath(__file__)), "zima_monitor_preview.png"))
                print("Saved preview"); break

            screen.show(img)
            time.sleep(REFRESH_INTERVAL)
    except KeyboardInterrupt: pass
    finally:
        if screen: screen.close()

if __name__ == "__main__":
    main()
