"""Generates icon.ico at the repository root (a green mirrored katakana on black).

Dev-only: needs Pillow and the MS Gothic font.  Usage: <venv python> tools/build/make_icon.py
"""

import os
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SIZE = 256
BACKGROUND = (0, 8, 2)
GLYPH_COLOUR = (0, 255, 70)
FONT_PATH = r"C:\Windows\Fonts\msgothic.ttc"
FONT_PX = 190
ICON_SIZES = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def main():
    img = Image.new("RGB", (SIZE, SIZE), BACKGROUND)
    font = ImageFont.truetype(FONT_PATH, FONT_PX)
    glyph = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(glyph).text((SIZE // 2, SIZE // 2), "ｦ", font=font, fill=255, anchor="mm")
    glyph = glyph.transpose(Image.FLIP_LEFT_RIGHT)
    img.paste(GLYPH_COLOUR, mask=glyph)
    img.save(os.path.join(ROOT, "icon.ico"), sizes=ICON_SIZES)
    return 0


if __name__ == "__main__":
    sys.exit(main())
