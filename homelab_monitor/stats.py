"""Local system stats and Docker container counts."""

import os, time, subprocess


def get_local_stats():
    """Collect CPU, memory, temp, disk, and uptime from the local machine."""
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=0.2)
        mem = psutil.virtual_memory()
        temp = 0.0
        try:
            temps = psutil.sensors_temperatures()
            for n in ("coretemp", "cpu_thermal", "k10temp", "soc_dts0"):
                if n in temps and temps[n]:
                    temp = temps[n][0].current
                    break
            if temp == 0 and temps:
                temp = next(iter(temps.values()))[0].current
        except Exception:
            pass
        disk_pct = 0.0
        disk_total_gb = 0.0
        disk_used_gb = 0.0
        for m in ("/DATA", "/"):
            try:
                d = psutil.disk_usage(m)
                disk_pct = d.percent
                disk_total_gb = d.total / 1_073_741_824
                disk_used_gb = d.used / 1_073_741_824
                break
            except:
                continue
        return {
            "cpu": cpu,
            "mem_pct": mem.percent,
            "mem_total_gb": mem.total / 1_073_741_824,
            "mem_used_gb": mem.used / 1_073_741_824,
            "temp": temp,
            "disk_pct": disk_pct,
            "disk_total_gb": disk_total_gb,
            "disk_used_gb": disk_used_gb,
            "docker_running": 0,
            "docker_stopped": 0,
            "uptime": time.time() - psutil.boot_time(),
        }
    except ImportError:
        return _proc_fallback()


def _proc_fallback():
    """Collect stats from /proc when psutil is unavailable (Debian/OMV)."""
    stats = {
        "cpu": 0, "mem_pct": 0, "mem_total_gb": 0, "mem_used_gb": 0,
        "temp": 0, "disk_pct": 0, "disk_total_gb": 0, "disk_used_gb": 0,
        "docker_running": 0, "docker_stopped": 0, "uptime": 0,
    }
    # CPU — two samples for accurate delta
    try:
        def _read_cpu():
            p = open("/proc/stat").readline().split()
            vals = [int(x) for x in p[1:]]
            return sum(vals), vals[3]  # total, idle

        t1, i1 = _read_cpu()
        time.sleep(0.2)
        t2, i2 = _read_cpu()
        dt, di = t2 - t1, i2 - i1
        stats["cpu"] = round((1 - di / max(dt, 1)) * 100, 1) if dt > 0 else 0
    except:
        pass
    # Memory
    try:
        mi = {}
        for line in open("/proc/meminfo"):
            k, v = line.split(":")
            mi[k.strip()] = int(v.strip().split()[0])
        t = mi.get("MemTotal", 0)
        a = mi.get("MemAvailable", 0)
        stats["mem_pct"] = round((t - a) / max(t, 1) * 100, 1)
        stats["mem_total_gb"] = (t * 1024) / 1_073_741_824
        stats["mem_used_gb"] = ((t - a) * 1024) / 1_073_741_824
    except:
        pass
    # Temperature
    try:
        stats["temp"] = int(open("/sys/class/thermal/thermal_zone0/temp").read()) / 1000
    except:
        pass
    # Disk
    try:
        s = os.statvfs("/DATA" if os.path.exists("/DATA") else "/")
        stats["disk_pct"] = round((1 - s.f_bfree / max(s.f_blocks, 1)) * 100, 1)
        stats["disk_total_gb"] = (s.f_blocks * s.f_frsize) / 1_073_741_824
        stats["disk_used_gb"] = ((s.f_blocks - s.f_bfree) * s.f_frsize) / 1_073_741_824
    except:
        pass
    # Uptime
    try:
        stats["uptime"] = float(open("/proc/uptime").read().split()[0])
    except:
        pass
    return stats


def get_docker_stats():
    """Get local docker container counts (running, stopped)."""
    running = stopped = 0
    try:
        r = subprocess.run(["docker", "ps", "-q"], capture_output=True, text=True, timeout=5)
        if r.returncode == 0:
            running = len(r.stdout.strip().splitlines()) if r.stdout.strip() else 0
    except:
        pass
    try:
        r = subprocess.run(
            ["docker", "ps", "-q", "--filter", "status=exited"],
            capture_output=True, text=True, timeout=5,
        )
        if r.returncode == 0:
            stopped = len(r.stdout.strip().splitlines()) if r.stdout.strip() else 0
    except:
        pass
    return running, stopped
