"""Remote server stats via SSH."""

import subprocess, logging

log = logging.getLogger("homelab_monitor")


def _remote_ssh(remote_ip, remote_ssh_user):
    """Fetch stats over SSH by reading /proc and running docker commands."""
    cmd = (
        "head -1 /proc/stat; sleep 0.5; echo '---'; "
        "head -1 /proc/stat; echo '---'; "
        "head -3 /proc/meminfo; echo '---'; "
        "cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null || echo 0; echo '---'; "
        "df -P /DATA 2>/dev/null || df -P /; echo '---'; "
        "cat /proc/uptime 2>/dev/null || echo 0; echo '---'; "
        "docker ps -q 2>/dev/null | wc -l; echo '---'; "
        "docker ps -q --filter status=exited 2>/dev/null | wc -l"
    )
    try:
        r = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=3", "-o", "StrictHostKeyChecking=no",
             f"{remote_ssh_user}@{remote_ip}", cmd],
            capture_output=True, text=True, timeout=8,
        )
        if r.returncode != 0:
            return None
        secs = r.stdout.split("---")
        if len(secs) < 4:
            return None
    except:
        return None

    stats = {
        "cpu": 0, "mem_pct": 0, "mem_total_gb": 0, "mem_used_gb": 0,
        "temp": 0, "disk_pct": 0, "disk_total_gb": 0, "disk_used_gb": 0,
        "docker_running": 0, "docker_stopped": 0, "uptime": 0,
    }

    # CPU — two samples (secs[0] and secs[1])
    try:
        p1 = secs[0].strip().split()
        p2 = secs[1].strip().split()
        if len(p1) > 4 and len(p2) > 4:
            vals1 = [int(x) for x in p1[1:]]
            vals2 = [int(x) for x in p2[1:]]
            t1, i1 = sum(vals1), vals1[3]
            t2, i2 = sum(vals2), vals2[3]
            dt, di = t2 - t1, i2 - i1
            if dt > 0:
                stats["cpu"] = round((1 - di / dt) * 100, 1)
    except:
        pass

    # Memory
    mi = {}
    for line in secs[2].strip().splitlines():
        if ":" in line:
            k, v_ = line.split(":")
            mi[k.strip()] = int(v_.strip().split()[0])
    t = mi.get("MemTotal", 0)
    a = mi.get("MemAvailable", 0)
    stats["mem_pct"] = round((t - a) / max(t, 1) * 100, 1)
    stats["mem_total_gb"] = (t * 1024) / 1_073_741_824
    stats["mem_used_gb"] = ((t - a) * 1024) / 1_073_741_824

    # Temperature
    try:
        stats["temp"] = int(secs[3].strip()) / 1000
    except:
        pass

    # Disk
    if len(secs) > 4:
        for line in secs[4].strip().splitlines():
            parts = line.split()
            if len(parts) >= 5 and parts[0] != "Filesystem":
                try:
                    stats["disk_pct"] = float(parts[4].rstrip("%"))
                    stats["disk_total_gb"] = float(parts[1]) * 1024 / 1_073_741_824
                    stats["disk_used_gb"] = float(parts[2]) * 1024 / 1_073_741_824
                except:
                    pass

    # Uptime
    if len(secs) > 5:
        try:
            stats["uptime"] = float(secs[5].strip().split()[0])
        except:
            pass

    # Docker
    if len(secs) > 6:
        try:
            stats["docker_running"] = int(secs[6].strip())
        except:
            pass
    if len(secs) > 7:
        try:
            stats["docker_stopped"] = int(secs[7].strip())
        except:
            pass

    return stats


def get_remote_stats(remote_ip, remote_ssh_user):
    """Fetch remote server stats over SSH."""
    return _remote_ssh(remote_ip, remote_ssh_user)
