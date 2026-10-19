"""Foreground silhouettes of the reference sheet views.

The sheet is drawn on white with light-blue guide lines; the character's
silhouette is everything that is neither.  Small enclosed holes (glass
highlights, bright stone) are filled; large ones (the gap between the legs)
are kept.
"""
import numpy as np
from PIL import Image
from scipy import ndimage as nd

SHEET = "reference/turnaround_sheet.png"

# Crop boxes (x0, y0, x1, y1) in sheet pixels.  Each view stands on the ground
# line at y=529; the finial tip is at y=43.  Height 486 px = 3.5 m.
VIEWS = {
    "front": (40, 40, 620, 535),
    "side": (630, 40, 930, 535),
    "back": (950, 40, 1520, 535),
}
GROUND_Y = 529
TOP_Y = 43
HEIGHT_M = 3.5
M_PER_PX = HEIGHT_M / (GROUND_Y - TOP_Y)


def raw_mask(rgb):
    a = rgb.astype(np.int16)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    not_white = (255 * 3 - (r + g + b)) > 60
    bluish = (b - r > 12) & (b > 150)
    return not_white & ~bluish


def silhouette(view, max_hole=2500):
    x0, y0, x1, y1 = VIEWS[view]
    im = np.asarray(Image.open(SHEET).convert("RGB"))[y0:y1, x0:x1]
    m = raw_mask(im)
    # The ground shadow would close the gap between the legs: cut it off.
    m[GROUND_Y - y0 - 2:, :] = False
    m = nd.binary_opening(m, iterations=1)
    m = nd.binary_closing(m, iterations=2)
    holes = nd.binary_fill_holes(m) & ~m
    lab, n = nd.label(holes)
    if n:
        sizes = nd.sum(holes, lab, range(1, n + 1))
        m |= np.isin(lab, 1 + np.nonzero(sizes < max_hole)[0])
    lab, n = nd.label(m)
    sizes = nd.sum(m, lab, range(1, n + 1))
    return np.isin(lab, 1 + np.nonzero(sizes > 800)[0])


if __name__ == "__main__":
    import sys
    out = sys.argv[1] if len(sys.argv) > 1 else "."
    for v in VIEWS:
        s = silhouette(v)
        Image.fromarray((s * 255).astype(np.uint8)).save(f"{out}/sil_{v}.png")
        ys, xs = np.nonzero(s)
        print(v, "x", xs.min() + VIEWS[v][0], xs.max() + VIEWS[v][0], "w_m", round((xs.max() - xs.min()) * M_PER_PX, 2))
