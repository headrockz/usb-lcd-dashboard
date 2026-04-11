#!/usr/bin/env python3
"""Web controller for Zima Screens — serves on port 9595.

Manages which screen is active on the USB LCD.
Runs as the main process: starts/stops screen scripts as subprocesses.
"""

import os, sys, signal, subprocess, json, time
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs
from datetime import datetime

# Load .env file if present
_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(_env_path):
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip())

PORT = 9595
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

SCREENS = {
    "zima_monitor":    {"name": "Zima Monitor",    "icon": "🖥",  "desc": "CPU, MEM, disco e rede do ZimaBoard e ZimaCube", "script": "zima_monitor.py"},
    "discord_monitor": {"name": "Discord Monitor", "icon": "💬",  "desc": "Mensagens recentes e atividade do servidor Discord", "script": "discord_monitor.py"},
    "channel_pulse":   {"name": "Channel Pulse",   "icon": "📊",  "desc": "Inscritos, views/hora e vídeos recentes do YouTube", "script": "channel_pulse.py"},
    "pomodoro":        {"name": "Pomodoro Timer",   "icon": "🍅",  "desc": "Timer de foco com ciclos de trabalho e descanso", "script": "pomodoro.py"},
    "steam_random":    {"name": "Steam Discovery",  "icon": "🎮",  "desc": "Jogo aleatório da Steam a cada 5 minutos", "script": "steam_random.py"},
}

# ── Process management ────────────────────────────────────────

active_screen = None   # key from SCREENS
active_proc = None     # subprocess.Popen
started_at = None


def stop_active():
    global active_screen, active_proc, started_at
    if active_proc and active_proc.poll() is None:
        active_proc.terminate()
        try:
            active_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            active_proc.kill()
    active_screen = None
    active_proc = None
    started_at = None


def _play_transition(screen_name):
    """Play 8-bit boot animation before starting a new screen."""
    try:
        from transition import play_transition
        from shared import Screen as _Screen
        scr = _Screen()
        play_transition(scr, screen_name, frames=3)
        scr.close()
    except Exception as e:
        print(f"Transition skipped: {e}")


def start_screen(key, extra_args=None):
    global active_screen, active_proc, started_at
    stop_active()
    info = SCREENS.get(key)
    if not info:
        return False
    # Play boot animation
    _play_transition(info["name"].upper())
    # Start the actual screen
    script = os.path.join(SCRIPT_DIR, info["script"])
    cmd = [sys.executable, script]
    if extra_args:
        cmd.extend(extra_args)
    active_proc = subprocess.Popen(cmd, cwd=SCRIPT_DIR)
    active_screen = key
    started_at = datetime.now()
    return True


def get_status():
    running = active_proc is not None and active_proc.poll() is None
    return {
        "active": active_screen if running else None,
        "running": running,
        "started_at": started_at.isoformat() if started_at and running else None,
        "pid": active_proc.pid if active_proc and running else None,
    }


# ── HTML template ─────────────────────────────────────────────

def render_html():
    status = get_status()
    active = status["active"]

    cards = ""
    for key, info in SCREENS.items():
        is_active = key == active
        border = "border-color: #00ff41; box-shadow: 0 0 15px rgba(0,255,65,0.3);" if is_active else ""
        btn_class = "btn-stop" if is_active else "btn-start"
        btn_text = "Parar" if is_active else "Ativar"
        status_dot = '<span class="dot active"></span> Rodando' if is_active else '<span class="dot"></span> Inativo'

        extra_fields = ""
        if key == "pomodoro" and not is_active:
            extra_fields = """
            <div class="pomo-config">
                <label>Trabalho <input type="number" name="work" value="25" min="1" max="120"> min</label>
                <label>Descanso <input type="number" name="break" value="5" min="1" max="60"> min</label>
            </div>"""

        cards += f"""
        <div class="card" style="{border}">
            <div class="card-header">
                <span class="card-icon">{info['icon']}</span>
                <span class="card-title">{info['name']}</span>
                <span class="status">{status_dot}</span>
            </div>
            <p class="card-desc">{info['desc']}</p>
            {extra_fields}
            <form method="POST" action="/api/screen">
                <input type="hidden" name="screen" value="{key}">
                <input type="hidden" name="action" value="{'stop' if is_active else 'start'}">
                <button type="submit" class="{btn_class}">{btn_text}</button>
            </form>
        </div>"""

    uptime_info = ""
    if active and status.get("started_at"):
        uptime_info = f'<p class="uptime">Ativo desde {status["started_at"][:19].replace("T", " ")}</p>'

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Zima Screens</title>
<style>
  :root {{
    --bg: #080214;
    --bg2: #0e0620;
    --green: #00ff41;
    --green-dim: #008c24;
    --purple: #8c3cdc;
    --purple-dim: #502382;
    --border: #281450;
    --text: #c8c0d4;
    --text-dim: #6e6480;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: var(--bg);
    color: var(--text);
    font-family: 'JetBrains Mono', 'SF Mono', 'Fira Code', monospace;
    min-height: 100vh;
    padding: 20px;
  }}
  .header {{
    text-align: center;
    margin-bottom: 30px;
    border-bottom: 2px solid var(--purple);
    padding-bottom: 16px;
  }}
  .header h1 {{
    color: var(--purple);
    font-size: 1.8em;
    letter-spacing: 4px;
    text-transform: uppercase;
  }}
  .header h1 span {{
    color: var(--green);
  }}
  .header p {{
    color: var(--text-dim);
    font-size: 0.75em;
    margin-top: 6px;
  }}
  .uptime {{
    text-align: center;
    color: var(--green-dim);
    font-size: 0.7em;
    margin-bottom: 16px;
  }}
  .grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 16px;
    max-width: 900px;
    margin: 0 auto;
  }}
  .card {{
    background: var(--bg2);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 16px;
    transition: border-color 0.3s, box-shadow 0.3s;
    overflow: hidden;
  }}
  .card:hover {{
    border-color: var(--purple-dim);
  }}
  .card-header {{
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 8px;
  }}
  .card-icon {{
    font-size: 1.4em;
  }}
  .card-title {{
    color: var(--green);
    font-size: 0.95em;
    font-weight: bold;
    flex: 1;
  }}
  .status {{
    font-size: 0.7em;
    color: var(--text-dim);
    display: flex;
    align-items: center;
    gap: 4px;
  }}
  .dot {{
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--text-dim);
    display: inline-block;
  }}
  .dot.active {{
    background: var(--green);
    box-shadow: 0 0 6px var(--green);
  }}
  .card-desc {{
    color: var(--text-dim);
    font-size: 0.72em;
    margin-bottom: 12px;
    line-height: 1.4;
  }}
  .pomo-config {{
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    margin-bottom: 10px;
    max-width: 100%;
  }}
  .pomo-config label {{
    color: var(--text-dim);
    font-size: 0.7em;
    display: flex;
    align-items: center;
    gap: 6px;
    min-width: 0;
    white-space: nowrap;
  }}
  .pomo-config input {{
    width: 50px;
    min-width: 0;
    max-width: 60px;
    background: var(--bg);
    border: 1px solid var(--border);
    color: var(--green);
    padding: 4px 6px;
    border-radius: 4px;
    font-family: inherit;
    font-size: 1em;
    text-align: center;
    box-sizing: border-box;
  }}
  button {{
    width: 100%;
    padding: 10px;
    border: 1px solid;
    border-radius: 6px;
    font-family: inherit;
    font-size: 0.8em;
    font-weight: bold;
    cursor: pointer;
    text-transform: uppercase;
    letter-spacing: 2px;
    transition: all 0.2s;
  }}
  .btn-start {{
    background: transparent;
    border-color: var(--green-dim);
    color: var(--green);
  }}
  .btn-start:hover {{
    background: rgba(0, 255, 65, 0.1);
    border-color: var(--green);
    box-shadow: 0 0 10px rgba(0, 255, 65, 0.2);
  }}
  .btn-stop {{
    background: rgba(255, 40, 40, 0.1);
    border-color: #ff2828;
    color: #ff2828;
  }}
  .btn-stop:hover {{
    background: rgba(255, 40, 40, 0.2);
    box-shadow: 0 0 10px rgba(255, 40, 40, 0.3);
  }}
  .footer {{
    text-align: center;
    margin-top: 30px;
    padding-top: 16px;
    border-top: 1px solid var(--border);
    color: var(--text-dim);
    font-size: 0.65em;
  }}
  .preview-container {{
    text-align: center;
    margin-bottom: 24px;
  }}
  .preview-img {{
    max-width: 480px;
    width: 100%;
    border: 2px solid var(--purple);
    border-radius: 8px;
    box-shadow: 0 0 20px rgba(140, 60, 220, 0.3);
    image-rendering: pixelated;
  }}
  .preview-label {{
    color: var(--green-dim);
    font-size: 0.65em;
    margin-top: 6px;
    letter-spacing: 3px;
  }}
  .scanlines {{
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    pointer-events: none;
    background: repeating-linear-gradient(
      0deg,
      transparent,
      transparent 2px,
      rgba(255,255,255,0.015) 2px,
      rgba(255,255,255,0.015) 3px
    );
    z-index: 999;
  }}
</style>
</head>
<body>
<div class="scanlines"></div>
<div class="header">
  <h1>ZIMA <span>SCREENS</span></h1>
  <p>USB LCD Controller &bull; {datetime.now().strftime('%H:%M:%S')}</p>
</div>
{uptime_info}
{'<div class="preview-container"><img src="/preview.png?t=' + str(int(time.time())) + '" alt="Screen preview" class="preview-img" id="previewImg"><p class="preview-label">LIVE PREVIEW</p></div>' if active else ''}
<div class="grid">
{cards}
</div>
<div class="footer">
  zimaboard:9595 &bull; 480x320 USB IPS
</div>
<script>
  // Auto-refresh preview every 3 seconds
  const img = document.getElementById('previewImg');
  if (img) {{
    setInterval(() => {{
      img.src = '/preview.png?t=' + Date.now();
    }}, 3000);
  }}
</script>
</body>
</html>"""


# ── HTTP Handler ──────────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {fmt % args}")

    def do_GET(self):
        if self.path == "/api/status":
            self._json_response(get_status())
        elif self.path.startswith("/preview.png"):
            self._serve_preview()
        else:
            html = render_html()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode())

    def _serve_preview(self):
        preview_path = os.path.join(SCRIPT_DIR, "current_frame.png")
        if os.path.exists(preview_path):
            with open(preview_path, "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Cache-Control", "no-cache, no-store")
            self.end_headers()
            self.wfile.write(data)
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode()

        content_type = self.headers.get("Content-Type", "")
        if "json" in content_type:
            params = json.loads(body)
        else:
            params = {k: v[0] for k, v in parse_qs(body).items()}

        screen = params.get("screen", "")
        action = params.get("action", "start")

        if action == "stop":
            stop_active()
        elif action == "start" and screen in SCREENS:
            extra = []
            if screen == "pomodoro":
                work = params.get("work", "25")
                brk = params.get("break", "5")
                extra = ["--work", str(work), "--break", str(brk)]
            start_screen(screen, extra)

        # Redirect back to main page (PRG pattern)
        if "json" in content_type:
            self._json_response(get_status())
        else:
            self.send_response(303)
            self.send_header("Location", "/")
            self.end_headers()

    def _json_response(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())


# ── Main ──────────────────────────────────────────────────────

def main():
    def cleanup(sig, frame):
        print("\nShutting down...")
        stop_active()
        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    server = HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Zima Screens controller running at http://0.0.0.0:{PORT}")
    print(f"Screens dir: {SCRIPT_DIR}")
    server.serve_forever()


if __name__ == "__main__":
    main()
