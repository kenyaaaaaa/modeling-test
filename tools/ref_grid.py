"""Draw a metric grid over a reference view (for reading landmark positions)."""
import sys

from PIL import Image, ImageDraw

import ref_mask as R


def grid(view, cx_sheet, out, scale=2):
    x0, y0, x1, y1 = R.VIEWS[view]
    im = Image.open(R.SHEET).convert("RGB").crop((x0, y0, x1, y1))
    im = im.resize((im.width * scale, im.height * scale), Image.LANCZOS)
    d = ImageDraw.Draw(im)
    px = 1 / R.M_PER_PX * scale
    gy = (R.GROUND_Y - y0) * scale
    cx = (cx_sheet - x0) * scale
    for i in range(0, 37):
        y = gy - i * 0.1 * px
        d.line([(0, y), (im.width, y)], fill=(255, 0, 0) if i % 5 == 0 else (255, 170, 170), width=1)
        if i % 5 == 0:
            d.text((2, y - 12), f"{i/10:.1f}", fill=(255, 0, 0))
    for i in range(-20, 21):
        x = cx + i * 0.1 * px
        d.line([(x, 0), (x, im.height)], fill=(0, 0, 255) if i % 5 == 0 else (170, 170, 255), width=1)
        if i % 5 == 0:
            d.text((x + 2, 2), f"{i/10:.1f}", fill=(0, 0, 255))
    im.save(out)


if __name__ == "__main__":
    grid(sys.argv[1], float(sys.argv[2]), sys.argv[3])
