"""
LCD hardware driver, palette, fonts, and drawing helpers.

Modules:
    constants — screen dimensions, color palette, protocol commands
    screen    — Screen class (serial driver for Turing Smart Screen)
    drawing   — UI drawing primitives (bars, sparklines, panels, fonts)
    helpers   — formatting and color utility functions
"""

from lcd.constants import *
from lcd.helpers import *
from lcd.drawing import *
from lcd.screen import *
