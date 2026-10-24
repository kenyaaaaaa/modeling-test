"""Hit effects drawn in the concept's style: flat cel shading with an ink outline.

Each effect is a horizontal sprite sheet (one frame per cell) at the final size.
They are drawn 4x larger and shrunk, like the parts.
"""
import math

import cv2
import numpy as np
from PIL import Image

from .parts import INK

UP = 4  # drawn this many times larger
DUST = {"shadow": (150, 134, 118), "base": (198, 184, 162), "light": (228, 219, 199)}
WAVE = (246, 238, 208)
ROCK = {"shadow": (62, 56, 78), "base": (92, 84, 108), "light": (128, 120, 140)}


def disc(mask, cx, cy, r):
    cv2.circle(mask, (int(cx), int(cy)), max(int(r), 1), 1, -1, lineType=cv2.LINE_8)


def cel(mask, colours, ink_px, shade=0.3, light=0.12):
    """Fill a 0/1 mask in three tones (shadow at the bottom of each bump, light at
    the top) and ring it with ink. Returns RGBA float (premultiplied=no)."""
    h, w = mask.shape
    m = mask > 0
    dy = max(int(shade * h * 0.25), 1)
    ly = max(int(light * h * 0.25), 1)
    below = np.zeros_like(m)
    below[:-dy] = m[dy:]
    above = np.zeros_like(m)
    above[ly:] = m[:-ly]
    rgb = np.zeros((h, w, 3), np.float32)
    rgb[m] = colours["base"]
    rgb[m & ~below] = colours["shadow"]
    rgb[m & ~above] = colours["light"]
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * ink_px + 1, 2 * ink_px + 1))
    ring = (cv2.dilate(m.astype(np.uint8), k) > 0) & ~m
    rgb[ring] = INK
    a = (m | ring).astype(np.float32)
    return rgb, a


def shrink(rgb, a):
    pre = np.dstack([rgb * a[..., None], a])
    small = cv2.resize(pre, None, fx=1 / UP, fy=1 / UP, interpolation=cv2.INTER_AREA)
    sa = small[..., 3]
    srgb = small[..., :3] / np.maximum(sa, 1e-4)[..., None]
    return np.dstack([srgb, sa * 255])


def sheet(frames, path):
    out = np.concatenate(frames, 1)
    Image.fromarray(out.round().clip(0, 255).astype(np.uint8), "RGBA").save(path, optimize=True)
    return frames[0].shape[1], frames[0].shape[0]


def dust(path, w, h, n=6, seed=4):
    """A cloud kicked up from the ground: bursts out, billows, breaks up."""
    rng = np.random.default_rng(seed)
    W, H = w * UP, h * UP
    puffs = [(rng.uniform(-1, 1), rng.uniform(0.2, 1), rng.uniform(0.6, 1.0)) for _ in range(9)]
    frames = []
    for f in range(n):
        g = 1 - (1 - (f + 1) / n) ** 2  # how far out
        size = 0.4 + 0.6 * math.sin(math.pi * min((f + 0.6) / (n - 0.5), 1)) ** 0.6
        mask = np.zeros((H, W), np.uint8)
        for i, (sx, rise, r0) in enumerate(puffs):
            if f >= n - 2 and i % 2:
                continue  # breaking up
            cx = W / 2 + sx * W * 0.38 * (0.35 + 0.65 * g)
            cy = H * 0.86 - rise * H * 0.45 * g
            disc(mask, cx, cy, r0 * H * 0.22 * size)
        rgb, a = cel(mask, DUST, ink_px=2 * UP // 2)
        if f >= n - 2:
            a *= 0.75
        frames.append(shrink(rgb, a))
    return sheet(frames, path)


def shockwave(path, w, h, n=5):
    """A flat ring racing out along the ground."""
    W, H = w * UP, h * UP
    frames = []
    for f in range(n):
        g = (f + 1) / n
        rx = W * 0.5 * (0.25 + 0.72 * g)
        ry = rx * 0.17
        thick = max(int((1 - g) * 9 * UP + 2 * UP), 2)
        mask = np.zeros((H, W), np.uint8)
        cv2.ellipse(mask, (W // 2, H // 2), (int(rx), int(ry)), 0, 0, 360, 1, thick)
        rgb, a = cel(mask, {"shadow": WAVE, "base": WAVE, "light": (255, 252, 236)}, ink_px=UP)
        a *= 1.0 if f < n - 1 else 0.6
        frames.append(shrink(rgb, a))
    return sheet(frames, path)


def shards(path, size, n=3, seed=9):
    """Broken rock bits, one per frame (pick one with `frame`)."""
    rng = np.random.default_rng(seed)
    S = size * UP
    frames = []
    for _ in range(n):
        pts = []
        k = rng.integers(5, 7)
        for j in range(k):
            ang = j / k * math.tau + rng.uniform(-0.3, 0.3)
            rad = S * 0.4 * rng.uniform(0.55, 1.0)
            pts.append((S / 2 + rad * math.cos(ang), S / 2 + rad * math.sin(ang)))
        mask = np.zeros((S, S), np.uint8)
        cv2.fillPoly(mask, [np.int32(pts)], 1)
        rgb, a = cel(mask, ROCK, ink_px=UP, shade=0.8, light=0.5)
        frames.append(shrink(rgb, a))
    return sheet(frames, path)


def make_all(out, scale):
    """Sizes follow the golem: about the width of an arm for the dust, wider than
    the golem for the ring."""
    k = scale / 0.36
    return {
        "fx_dust": {"file": "fx_dust.png", "frames": 6, "cell": dust(out / "fx_dust.png", int(120 * k), int(70 * k))},
        "fx_wave": {"file": "fx_wave.png", "frames": 5, "cell": shockwave(out / "fx_wave.png", int(460 * k), int(90 * k))},
        "fx_shard": {"file": "fx_shard.png", "frames": 3, "cell": shards(out / "fx_shard.png", int(12 * k))},
    }
