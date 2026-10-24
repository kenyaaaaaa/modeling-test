"""Cut the front concept into layered parts for 2D cutout animation.

    python -m golem2d.cut --out godot2d/parts

Writes one PNG per part (cropped to its pixels) and parts.json with where
each one sits, the point it turns around and the part it rides on.
"""
import argparse
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

from . import parts as P

H_INK = 60  # outline darkness used to un-blend anti-aliased edges from the white paper


def shape_mask(size, part, key="poly"):
    w, h = size
    im = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(im)
    if key == "poly" and "rect" in part:
        x0, y0, x1, y1 = part["rect"]
        d.rectangle((x0, y0, x1 - 1, y1 - 1), fill=255)
    elif key == "poly" and "circle" in part:
        cx, cy, r = part["circle"]
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=255)
    elif key in part:
        d.polygon(part[key], fill=255)
    return np.asarray(im) > 0


def rect_mask(shape, rects):
    m = np.zeros(shape, bool)
    for x0, y0, x1, y1 in rects:
        m[y0:y1, x0:x1] = True
    return m


def matte(rgb):
    """Alpha from the white paper: the background is the near-white area reached
    from the border, plus large pure-white pockets; edges are un-blended."""
    lo = rgb.min(2)
    white = lo >= 240
    lab, _ = ndimage.label(white)
    border = np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))
    bg = np.isin(lab, border[border > 0])
    pure, n = ndimage.label((lo >= 250) & ~bg)
    sizes = ndimage.sum(np.ones_like(lo), pure, range(1, n + 1))
    bg |= np.isin(pure, 1 + np.flatnonzero(sizes >= 150))

    alpha = (~bg).astype(np.float32)
    band = ndimage.binary_dilation(bg, iterations=2) & ndimage.binary_dilation(~bg, iterations=2)
    mean = rgb.mean(2)
    a = np.clip((255 - mean) / (255 - H_INK), 0, 1)
    alpha[band] = np.where(a[band] > 0.9, 1.0, a[band])
    out = rgb.astype(np.float32)
    soft = band & (alpha > 0) & (alpha < 1)
    out[soft] = np.clip((out[soft] - (1 - alpha[soft, None]) * 255) / alpha[soft, None], 0, 255)
    return out, alpha


def inpaint(rgb, mask, radius=5):
    m = (mask * 255).astype(np.uint8)
    return cv2.inpaint(rgb.clip(0, 255).astype(np.uint8), m, radius, cv2.INPAINT_TELEA).astype(np.float32)


def save(layer_rgb, layer_a, path):
    ys, xs = np.nonzero(layer_a > 0.004)
    x0, y0, x1, y1 = xs.min(), ys.min(), xs.max() + 1, ys.max() + 1
    rgba = np.dstack([layer_rgb[y0:y1, x0:x1], layer_a[y0:y1, x0:x1, None] * 255])
    Image.fromarray(rgba.round().clip(0, 255).astype(np.uint8), "RGBA").save(path, optimize=True)
    return [int(x0), int(y0)], [int(x1 - x0), int(y1 - y0)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="godot2d/parts")
    ap.add_argument("--debug", help="write a colour map of the parts here")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    src = np.asarray(Image.open(P.SRC).convert("RGB"))
    h, w = src.shape[:2]
    rgb, alpha = matte(src)
    fg = alpha > 0
    taken = np.zeros((h, w), bool)
    layers = {}  # name -> dict(rgb, a, pivot, parent)

    # floating chips: small pieces not joined to the golem and not inside a part's shape
    lab, n = ndimage.label(alpha > 0.5, structure=np.ones((3, 3)))
    sizes = ndimage.sum(np.ones((h, w)), lab, range(1, n + 1))
    centres = ndimage.center_of_mass(np.ones((h, w)), lab, range(1, n + 1))
    inside_parts = np.zeros((h, w), bool)
    for part in P.PARTS:
        if part["name"] != "legs" and not part["name"].startswith("arm"):
            inside_parts |= shape_mask((w, h), part)
    chips = []
    for i, (size, (cy, cx)) in enumerate(zip(sizes, centres), start=1):
        if size > P.DEBRIS_MAX_AREA or cy > P.DEBRIS_GROUND_Y or inside_parts[int(cy), int(cx)]:
            continue
        m = ndimage.binary_dilation(lab == i, iterations=2) & fg & ~taken
        chips.append((m, (cx, cy)))
        taken |= m
    chips.sort(key=lambda c: (c[1][1], c[1][0]))
    for k, (m, (cx, cy)) in enumerate(chips):
        layers[f"chip_{k:02d}"] = {"rgb": rgb, "a": alpha * m, "pivot": (cx, cy), "parent": None, "chip": True}

    for part in P.PARTS:
        m = shape_mask((w, h), part)
        if "poly2" in part:
            m |= shape_mask((w, h), part, "poly2")
        if "minus" in part:
            m &= ~rect_mask((h, w), part["minus"])
        m &= fg
        if part.get("keep_under"):
            layers[part["name"]] = {"rgb": rgb, "a": alpha * m, "pivot": part["pivot"], "parent": part["parent"]}
            continue
        m &= ~taken
        layer = {"rgb": rgb, "a": alpha * m, "pivot": part["pivot"], "parent": part["parent"], "fill": part.get("fill", 0)}
        if part["name"] == "legs":
            # under the pillar finials (which stay with the body) paint the leg rock in
            fin = rect_mask((h, w), part["minus"]) & fg & ~taken
            fin &= ndimage.binary_dilation(m, iterations=25)
            layer["rgb"] = inpaint(rgb, fin, 6)
            layer["a"] = alpha * (m | fin)
            # where the body overlaps the legs it fades out, so breathing leaves no seam
            t0, t1 = part["feather_top"]
            ramp = np.clip((np.arange(h) - t0) / (t1 - t0), 0, 1)[:, None]
            layer["body_fade"] = m * ramp  # the finials stay solid on the body
            m = m & (np.arange(h)[:, None] >= t1)  # only the legs below the fade leave the body
        taken |= m
        layer["mask"] = m
        layers[part["name"]] = layer

    # the body is everything left
    body_a = alpha * ~taken
    body_rgb = rgb.copy()
    if "body_fade" in layers["legs"]:
        body_a = body_a * (1 - layers["legs"].pop("body_fade"))
    layers["body"] = {"rgb": body_rgb, "a": body_a, "pivot": P.BODY_PIVOT, "parent": None}

    # fill each parent under its moving children where they meet the rest of the parent
    for name, layer in list(layers.items()):
        r = layer.get("fill", 0)
        par = layer["parent"]
        if not r or not par:
            continue
        pl = layers[par]
        rest = pl["a"] > 0.5
        hole = layer["mask"] if r >= 99 else layer["mask"] & ndimage.binary_dilation(rest, iterations=r)
        pl["rgb"] = np.where(hole[..., None], inpaint(pl["rgb"], hole, 5), pl["rgb"])
        pl["a"] = np.where(hole, 1.0, pl["a"])

    # hourglass glow: the bright part of the upper bulb, for an additive pulse
    gx0, gy0, gx1, gy1 = P.GLOW
    lum = src.astype(np.float32).mean(2)
    glow_a = np.zeros((h, w), np.float32)
    glow_a[gy0:gy1, gx0:gx1] = np.clip((lum[gy0:gy1, gx0:gx1] - 170) / 70, 0, 1)
    glow_rgb = np.broadcast_to(np.array([255, 236, 150], np.float32), (h, w, 3))
    layers["glow"] = {"rgb": glow_rgb, "a": glow_a, "pivot": P.BODY_PIVOT, "parent": "body"}

    meta = {"origin": P.ORIGIN, "size": [w, h], "parts": {}, "stream": P.STREAM,
            "top_sand": P.TOP_SAND, "bottom_sand": P.BOTTOM_SAND}
    for name, layer in layers.items():
        pos, size = save(layer["rgb"], layer["a"], out / f"{name}.png")
        meta["parts"][name] = {"file": f"{name}.png", "pos": pos, "size": size,
                               "pivot": [round(float(v), 1) for v in layer["pivot"]], "parent": layer["parent"]}
    (out / "parts.json").write_text(json.dumps(meta, indent=1))
    print(f"{len(layers)} parts ({len(chips)} chips) -> {out}")

    if args.debug:
        rng = np.random.default_rng(3)
        dbg = np.full((h, w, 3), 255.0)
        for name, layer in layers.items():
            if name == "glow":
                continue
            col = rng.integers(40, 230, 3)
            a = (layer["a"] > 0.5)[..., None]
            dbg = np.where(a, dbg * 0.4 + col * 0.6, dbg)
        Image.fromarray(dbg.astype(np.uint8)).save(args.debug)


if __name__ == "__main__":
    main()
