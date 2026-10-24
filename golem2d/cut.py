"""Cut the front concept into layered parts for 2D cutout animation.

    python -m golem2d.cut --out godot2d/parts --scale 0.36

Writes one PNG per part (cropped to its pixels) and parts.json with where
each one sits, the point it turns around and the part it rides on. Parts are
cut at the size of the concept and shrunk at the end; before that the ink
lines are thickened so they still read at boss size (MapleStory-like).
Also writes the swap images for poses the cut parts can't reach by turning.
"""
import argparse
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

from . import parts as P
from .parts import INK
from . import fx, swaps

H_INK = 60  # outline darkness used to un-blend anti-aliased edges from the white paper
INK_LUM = 55  # darker than this counts as an ink line


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


def boost_lines(rgb, radius):
    """Thicken the dark ink lines by `radius` px (each pixel near ink takes the darkest
    colour around it), so they survive shrinking."""
    if radius <= 0:
        return rgb
    lum = rgb.astype(np.float32) @ np.array([0.299, 0.587, 0.114], np.float32)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * radius + 1, 2 * radius + 1))
    thick = cv2.dilate((lum < INK_LUM).astype(np.uint8), k) > 0
    return np.where(thick[..., None], cv2.erode(rgb, k), rgb)


def mirror_fill(rgb, rest, hole):
    """Paint `hole` with the parent's own rock: each pixel takes the colour mirrored
    across the nearest edge of `rest`, so cracks and lines carry on into it."""
    _, (iy, ix) = ndimage.distance_transform_edt(~rest, return_indices=True)
    yy, xx = np.nonzero(hole)
    my = np.clip(2 * iy[yy, xx] - yy, 0, rgb.shape[0] - 1)
    mx = np.clip(2 * ix[yy, xx] - xx, 0, rgb.shape[1] - 1)
    ok = rest[my, mx]
    out = rgb.copy()
    out[yy, xx] = np.where(ok[:, None], rgb[my, mx], rgb[iy[yy, xx], ix[yy, xx]])
    return out


def shrink(rgb, a, scale):
    """Shrink a whole-canvas layer (premultiplied, area filter)."""
    if scale == 1:
        return rgb, a
    pre = np.dstack([rgb * a[..., None], a])
    small = cv2.resize(pre, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    sa = small[..., 3]
    srgb = np.where(sa[..., None] > 1e-4, small[..., :3] / np.maximum(sa, 1e-4)[..., None], 0)
    return srgb, sa


def save(layer_rgb, layer_a, path, scale):
    rgb, a = shrink(layer_rgb.astype(np.float32), layer_a.astype(np.float32), scale)
    ys, xs = np.nonzero(a > 0.004)
    x0, y0, x1, y1 = xs.min(), ys.min(), xs.max() + 1, ys.max() + 1
    rgba = np.dstack([rgb[y0:y1, x0:x1], a[y0:y1, x0:x1, None] * 255])
    Image.fromarray(rgba.round().clip(0, 255).astype(np.uint8), "RGBA").save(path, optimize=True)
    return [int(x0), int(y0)], [int(x1 - x0), int(y1 - y0)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="godot2d/parts")
    ap.add_argument("--scale", type=float, default=0.36, help="output size (0.36: about 350 px tall)")
    ap.add_argument("--boost", type=int, default=1, help="px to thicken ink lines by before shrinking")
    ap.add_argument("--debug", help="write a colour map of the parts here")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    src = boost_lines(np.asarray(Image.open(P.SRC).convert("RGB")), args.boost)
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
        if r >= 99:  # wholly inside the parent (clock hands on the dial)
            hole = layer["mask"]
            pl["rgb"] = np.where(hole[..., None], inpaint(pl["rgb"], hole, 5), pl["rgb"])
        else:
            # carry the parent's rock on into the band and close it with an outline,
            # so it reads as rock when the part swings away
            # only where the parent's outline dips in under the part, not past its outline
            k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (4 * r + 1, 4 * r + 1))
            closed = cv2.morphologyEx(rest.astype(np.uint8), cv2.MORPH_CLOSE, k) > 0
            hole = layer["mask"] & ndimage.binary_dilation(rest, iterations=r) & closed
            edge = hole & ~ndimage.binary_erosion(hole | rest, iterations=3)
            pl["rgb"] = mirror_fill(pl["rgb"], rest, hole)
            pl["rgb"][edge] = INK
        pl["a"] = np.where(hole, 1.0, pl["a"])

    # hourglass glow: the bright part of the upper bulb, for an additive pulse
    gx0, gy0, gx1, gy1 = P.GLOW
    lum = src.astype(np.float32).mean(2)
    glow_a = np.zeros((h, w), np.float32)
    glow_a[gy0:gy1, gx0:gx1] = np.clip((lum[gy0:gy1, gx0:gx1] - 170) / 70, 0, 1)
    glow_rgb = np.broadcast_to(np.array([255, 236, 150], np.float32), (h, w, 3))
    layers["glow"] = {"rgb": glow_rgb, "a": glow_a, "pivot": P.BODY_PIVOT, "parent": "body"}

    # swap images: the arms in poses turning alone can't give
    for side in ("l", "r"):
        arm = layers[f"arm_{side}"]
        for kind in P.SWAPS:
            rgb_s, a_s = swaps.arm_swap(arm["rgb"], arm["a"], arm["pivot"], kind, 1 if side == "l" else -1)
            layers[f"arm_{side}_{kind}"] = {"rgb": rgb_s, "a": a_s, "pivot": arm["pivot"], "parent": "body",
                                            "swap_of": f"arm_{side}"}

    S = args.scale
    sc = lambda v: [round(x * S, 2) for x in v]
    meta = {"scale": S, "origin": sc(P.ORIGIN), "size": [round(w * S), round(h * S)], "parts": {},
            "stream": sc(P.STREAM), "top_sand": sc(P.TOP_SAND), "bottom_sand": sc(P.BOTTOM_SAND)}
    for name, layer in layers.items():
        pos, size = save(layer["rgb"], layer["a"], out / f"{name}.png", S)
        meta["parts"][name] = {"file": f"{name}.png", "pos": pos, "size": size, "pivot": sc(layer["pivot"]),
                               "parent": layer["parent"], "swap_of": layer.get("swap_of")}
    meta["fx"] = fx.make_all(out, S)
    (out / "parts.json").write_text(json.dumps(meta, indent=1))
    print(f"{len(layers)} parts ({len(chips)} chips) -> {out}")

    if args.debug:
        rng = np.random.default_rng(3)
        dbg = np.full((h, w, 3), 255.0)
        for name, layer in layers.items():
            if name == "glow" or layer.get("swap_of"):
                continue
            col = rng.integers(40, 230, 3)
            a = (layer["a"] > 0.5)[..., None]
            dbg = np.where(a, dbg * 0.4 + col * 0.6, dbg)
        Image.fromarray(dbg.astype(np.uint8)).save(args.debug)


if __name__ == "__main__":
    main()
