"""
Hardware driver for the Turing Smart Screen Rev A.
"""

import serial
import serial.tools.list_ports
import time
import os
import numpy as np
import dotenv
from lcd.constants import (
    BAUD, W, H, SCREEN_W, SCREEN_H, CMD_DISPLAY_BITMAP, CMD_HELLO, CMD_SET_BRIGHTNESS
)

def load_env():
    # Load .env file relative to the project root (parent of shared/)
    _package_dir = os.path.dirname(os.path.abspath(__file__))
    _root_dir = os.path.dirname(_package_dir)
    _env_path = os.path.join(_root_dir, ".env")
    dotenv.load_dotenv(dotenv_path=_env_path)

load_env()

def build_cmd(x, y, ex, ey, cmd):
    buf = bytearray(6)
    buf[0] = (x >> 2) & 0xFF
    buf[1] = (((x & 3) << 6) + (y >> 4)) & 0xFF
    buf[2] = (((y & 15) << 4) + (ex >> 6)) & 0xFF
    buf[3] = (((ex & 63) << 2) + (ey >> 8)) & 0xFF
    buf[4] = ey & 0xFF
    buf[5] = cmd
    return bytes(buf)

def find_serial_port():
    override = os.environ.get("SERIAL_PORT")
    if override:
        return override
    for p in serial.tools.list_ports.comports():
        if p.serial_number and "USB35INCH" in p.serial_number:
            return p.device
    for candidate in ["/dev/ttyACM0", "/dev/ttyACM1", "/dev/ttyUSB0"]:
        if os.path.exists(candidate):
            return candidate
    return None

class Screen:
    def __init__(self, port=None):
        port = port or find_serial_port()
        if not port:
            raise RuntimeError("USB monitor not found")
        self.ser = serial.Serial(port, BAUD, timeout=2, rtscts=True)
        time.sleep(0.1)
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()
        self.ser.write(bytes([CMD_HELLO] * 6))
        self.ser.flush()
        time.sleep(0.5)
        self.ser.read(6)
        self.ser.reset_input_buffer()
        level = 255 - int(0.88 * 255)
        self.ser.write(build_cmd(level, 0, 0, 0, CMD_SET_BRIGHTNESS))
        self.ser.flush()

    def show(self, img):
        # Save preview for web UI (landscape, before rotation)
        try:
            # Save to root dir of the project (parent of shared/)
            _package_dir = os.path.dirname(os.path.abspath(__file__))
            _root_dir = os.path.dirname(_package_dir)
            preview_path = os.path.join(_root_dir, "current_frame.png")
            img.save(preview_path)
        except Exception:
            pass
        # Rotate landscape canvas to portrait for the physical screen.
        # Portrait canvases (SCREEN_W x SCREEN_H) are sent as-is.
        if img.size == (W, H):
            img = img.rotate(90, expand=True)
        if img.size != (SCREEN_W, SCREEN_H):
            img = img.resize((SCREEN_W, SCREEN_H))
        img = img.convert("RGB")
        px = np.asarray(img).reshape(-1, 3).astype(np.uint16)
        rgb565 = ((px[:, 0] >> 3) << 11) | ((px[:, 1] >> 2) << 5) | (px[:, 2] >> 3)
        data = rgb565.astype('<u2').tobytes()
        self.ser.write(build_cmd(0, 0, SCREEN_W - 1, SCREEN_H - 1, CMD_DISPLAY_BITMAP))
        self.ser.flush()
        chunk = SCREEN_W * 8
        for i in range(0, len(data), chunk):
            self.ser.write(data[i:i + chunk])
            self.ser.flush()

    def close(self):
        self.ser.close()
