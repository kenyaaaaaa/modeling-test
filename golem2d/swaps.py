"""Swap images: arm drawings for poses that turning the cut part can't give."""
import cv2
import numpy as np

from . import parts as P

GHOST = np.array([236, 230, 208], np.float32)  # the pale stone, flat


def warp(img, m, size):
    return cv2.warpAffine(img, m, size, flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)


def scale_about(pivot, sx, sy):
    px, py = pivot
    return np.float32([[sx, 0, px * (1 - sx)], [0, sy, py * (1 - sy)]])


def arm_swap(rgb, a, pivot, kind, sign):
    """The arm layer redrawn for a swap pose. `sign` is +1 for the left arm
    (outward = clockwise on screen) and -1 for the right."""
    spec = P.SWAPS[kind]
    h, w = a.shape
    m = scale_about(pivot, *spec["scale"])
    rgb_s = warp(rgb.astype(np.float32), m, (w, h))
    a_s = warp(a.astype(np.float32), m, (w, h))
    out_rgb = np.zeros_like(rgb_s)
    out_a = np.zeros_like(a_s)
    # trailing copies: where the arm just was (further out), flat pale stone
    for deg, strength in reversed(spec.get("ghosts", [])):
        # cv2 angles turn anticlockwise on screen; Godot's + is clockwise
        r = cv2.getRotationMatrix2D(tuple(float(v) for v in pivot), -sign * deg, 1.0)
        ga = warp(a_s, r.astype(np.float32), (w, h)) * strength
        out_rgb = GHOST * ga[..., None] + out_rgb * (1 - ga[..., None])
        out_a = ga + out_a * (1 - ga)
    out_rgb = rgb_s * a_s[..., None] + out_rgb * (1 - a_s[..., None])
    out_a = a_s + out_a * (1 - a_s)
    # out_rgb is premultiplied so far
    out_rgb = np.where(out_a[..., None] > 1e-4, out_rgb / np.maximum(out_a, 1e-4)[..., None], 0)
    return out_rgb, out_a
