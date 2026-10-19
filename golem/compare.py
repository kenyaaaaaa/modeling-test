"""Silhouette comparison against the reference sheet."""
import numpy as np
from PIL import Image

from .views import R


def iou(model, ref):
    inter = np.logical_and(model, ref).sum()
    union = np.logical_or(model, ref).sum()
    return float(inter / union) if union else 0.0


def diff_image(model, ref, view, path):
    """Reference faded underneath; green = both, red = missing, blue = extra."""
    x0, y0, x1, y1 = R.VIEWS[view]
    base = np.asarray(Image.open(R.SHEET).convert("L").crop((x0, y0, x1, y1))).astype(float)
    out = np.stack([base] * 3, -1) * 0.35 + 255 * 0.65
    both = model & ref
    out[both] = out[both] * 0.5 + np.array([60, 200, 60]) * 0.5
    out[ref & ~model] = [230, 40, 40]
    out[model & ~ref] = [40, 90, 230]
    Image.fromarray(out.astype(np.uint8)).save(path)


def side_by_side(paths, out, height=600):
    ims = [Image.open(p).convert("RGB") for p in paths]
    ims = [im.resize((round(im.width * height / im.height), height)) for im in ims]
    w = sum(im.width for im in ims) + 10 * (len(ims) - 1)
    sheet = Image.new("RGB", (w, height), "white")
    x = 0
    for im in ims:
        sheet.paste(im, (x, 0))
        x += im.width + 10
    sheet.save(out)
