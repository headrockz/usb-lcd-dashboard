"""
Screen, palette and protocol constants.
"""

# ── Screen dimensions ──────────────────────────────────────────
# Canvas (what you see — landscape)
W, H = 480, 320
# Physical screen pixels (portrait native)
SCREEN_W, SCREEN_H = 320, 480
BAUD = 115200

# ── Palette ────────────────────────────────────────────────────
BG           = (8, 2, 20)
BG_PANEL     = (14, 6, 32)
BORDER       = (40, 20, 80)
BORDER_HI    = (90, 45, 160)
GREEN        = (0, 255, 65)
GREEN_DIM    = (0, 140, 36)
GREEN_DARK   = (0, 60, 16)
PURPLE       = (140, 60, 220)
PURPLE_DIM   = (80, 35, 130)
ORANGE       = (255, 120, 0)
RED          = (255, 40, 40)
WHITE_DIM    = (140, 130, 160)
YELLOW       = (255, 230, 0)
CYAN         = (0, 220, 255)
GRAY         = (50, 40, 70)

# ── Protocol Commands ──────────────────────────────────────────
CMD_DISPLAY_BITMAP = 197
CMD_HELLO = 69
CMD_SET_BRIGHTNESS = 110
