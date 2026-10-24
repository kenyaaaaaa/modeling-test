"""Attack 1: ground slam, as held poses (MapleStory-style, no in-betweens).

Wind up with both arms raised (swap image), shake while holding, one smear
frame on the way down (swap image), then the slam: body drops, legs squash,
dust, a shockwave, rock shards and the floating chips jump. The hit frame
calls _on_attack_hit on the golem.

All lengths here are in pixels of the concept image; they are scaled with the
parts. Weights are swung by a damped pendulum driven by where their hanging
point goes, then sampled at FPS like the rest.
"""
import math

import numpy as np

from . import parts as P

FPS = 15  # rate for the sampled tracks (weights, chips, shards)
HIT = 0.72
LENGTH = 1.62

# time, body drop (+ = down), body scale, arms out (deg), arm image, legs scale, glow, shake x
FRAMES = [
    (0.00, 4, (1.01, 0.98), -3, "", (1, 1), 0.10, 0),
    (0.12, -6, (0.99, 1.03), 14, "raise", (1, 1), 0.30, 0),
    (0.24, -12, (0.985, 1.05), 28, "raise", (1, 1), 0.60, 0),
    (0.42, -12, (0.985, 1.05), 30, "raise", (1, 1), 0.80, 3),
    (0.54, -13, (0.985, 1.05), 30, "raise", (1, 1), 0.90, -3),
    (0.66, 6, (1.0, 0.99), 12, "smear", (1, 1), 1.00, 0),
    (HIT, 22, (1.035, 0.93), -4, "", (1.015, 0.965), 1.00, 0),
    (0.96, 16, (1.02, 0.96), -2, "", (1.01, 0.975), 0.60, 0),
    (1.14, 8, (1.01, 0.98), -1, "", (1.0, 0.99), 0.35, 0),
    (1.32, 3, (1.0, 0.99), 0, "", (1, 1), 0.15, 0),
    (1.50, 0, (1, 1), 0, "", (1, 1), 0.05, 0),
]


def lerp_pose(t):
    """Frame values blended linearly (only to drive the pendulums)."""
    if t <= FRAMES[0][0]:
        return FRAMES[0]
    for a, b in zip(FRAMES, FRAMES[1:]):
        if t <= b[0]:
            k = (t - a[0]) / (b[0] - a[0])
            mix = lambda x, y: tuple(p + (q - p) * k for p, q in zip(x, y)) if isinstance(x, tuple) else x + (y - x) * k
            return (t, mix(a[1], b[1]), mix(a[2], b[2]), mix(a[3], b[3]), a[4], a[5], a[6], a[7])
    return FRAMES[-1]


def frame_at(t):
    return [f for f in FRAMES if f[0] <= t + 1e-9][-1]


def swap_scale(image):
    return P.SWAPS[image]["scale"] if image else (1.0, 1.0)


def body_point(t, rel, body_pos, s):
    """Where a point given relative to the body pivot is (Godot units, root space)."""
    _, drop, (sx, sy), *_ = lerp_pose(t)
    return body_pos[0] + rel[0] * sx, body_pos[1] + drop * s + rel[1] * sy


def arm_point(t, arm_rel, w_rel, sign, body_pos, s):
    pose = lerp_pose(t)
    r = math.radians(sign * pose[3])
    ssx, ssy = swap_scale(frame_at(t)[4])
    x, y = w_rel[0] * ssx, w_rel[1] * ssy
    rx, ry = x * math.cos(r) - y * math.sin(r), x * math.sin(r) + y * math.cos(r)
    return body_point(t, (arm_rel[0] + rx, arm_rel[1] + ry), body_pos, s)


def pendulum(hang, length, base_rot, g, damp=2.8):
    """Godot rotation (relative to whatever it hangs on) of a weight under hang(t),
    sampled at FPS from 0 to LENGTH, easing back to 0 at the end."""
    sub = 16
    dt = 1 / (FPS * sub)
    a = w = 0.0  # angle from straight down; + swings the bottom right
    prev = [hang(0.0), hang(0.0)]
    out = []
    for step in range(int(round(LENGTH * FPS)) * sub + 1):
        t = step * dt
        p = hang(t)
        ax = (p[0] - 2 * prev[1][0] + prev[0][0]) / dt ** 2
        ay = (p[1] - 2 * prev[1][1] + prev[0][1]) / dt ** 2
        ax, ay = np.clip(ax, -6 * g, 6 * g), np.clip(ay, -6 * g, 6 * g)
        prev = [prev[1], p]
        w += ((-ax * math.cos(a) - (g - ay) * math.sin(a)) / length - damp * w) * dt
        a += w * dt
        if step % sub == 0:
            out.append((t, -a - base_rot(t)))  # Godot's + turns the bottom left
    for i, (t, v) in enumerate(out):
        k = min(max((t - (LENGTH - 0.35)) / 0.35, 0), 1)
        out[i] = (t, v * (1 - k * k * (3 - 2 * k)))
    return out


def tracks(parts, fx):
    """path -> list of (time, value); every track is held (discrete)."""
    s = parts["_scale"]
    g = 1600 * s
    times = [f[0] for f in FRAMES]
    tr = {}
    bx, by = parts["body"]["_pos"]
    tr["Body:position"] = [(f[0], ("v2", bx + f[7] * s, by + f[1] * s)) for f in FRAMES]
    tr["Body:scale"] = [(f[0], ("v2", *f[2])) for f in FRAMES]
    tr["Legs:scale"] = [(f[0], ("v2", *f[5])) for f in FRAMES]
    tr["Body/Glow:modulate"] = [(f[0], ("col", f[6])) for f in FRAMES]
    for side, sign in (("l", 1), ("r", -1)):
        arm = f"Body/Arm{side.upper()}"
        base = f"arm_{side}"
        tr[f"{arm}:rotation"] = [(f[0], ("f", math.radians(sign * f[3]))) for f in FRAMES]
        tr[f"{arm}/Sprite:texture"] = [(f[0], ("tex", f"{base}_{f[4]}" if f[4] else base)) for f in FRAMES]
        tr[f"{arm}/Sprite:offset"] = [(f[0], ("v2", *parts[f"{base}_{f[4]}" if f[4] else base]["_offset"]))
                                      for f in FRAMES]
        arm_rel = parts[base]["_pos"]
        for i in (1, 2, 3):
            name = f"weight_{side}{i}"
            w_rel = parts[name]["_pos"]
            tr[f"{arm}/Weight{side.upper()}{i}:position"] = [
                (f[0], ("v2", w_rel[0] * swap_scale(f[4])[0], w_rel[1] * swap_scale(f[4])[1])) for f in FRAMES]
            hang = lambda t, w_rel=w_rel, sign=sign, arm_rel=arm_rel: arm_point(t, arm_rel, w_rel, sign, (bx, by), s)
            base_rot = lambda t, sign=sign: math.radians(sign * lerp_pose(t)[3])
            tr[f"{arm}/Weight{side.upper()}{i}:rotation"] = [
                (t, ("f", v)) for t, v in pendulum(hang, parts[name]["size"][1] * 0.6, base_rot, g)]
    c_rel = parts["weight_c"]["_pos"]
    tr["Body/WeightC:rotation"] = [
        (t, ("f", v)) for t, v in pendulum(lambda t: body_point(t, c_rel, (bx, by), s),
                                           parts["weight_c"]["size"][1] * 0.6, lambda t: 0.0, g)]

    # effects: shockwave and dust play their frames from the hit, then hide
    fx_keys = {"Shockwave": (fx["fx_wave"]["frames"], 0.06), "DustL": (fx["fx_dust"]["frames"], 0.07),
               "DustR": (fx["fx_dust"]["frames"], 0.07)}
    for node, (n, step) in fx_keys.items():
        tr[f"{node}:visible"] = [(0, ("bool", False)), (HIT, ("bool", True)), (HIT + n * step, ("bool", False))]
        tr[f"{node}:frame"] = [(0, ("int", 0))] + [(HIT + k * step, ("int", k)) for k in range(n)]

    # rock shards thrown up from where the arms land
    rng = np.random.default_rng(7)
    for k in range(parts["_shards"]):
        node = f"Shards/Shard{k}"
        x0, y0 = parts["_dust_x"][k % 2], -4 * s / 0.36
        vx = (1 if k % 2 else -1) * rng.uniform(40, 110) * s / 0.36 * (1 if rng.random() < 0.7 else -0.5)
        vy = -rng.uniform(170, 280) * s / 0.36
        gy = 900 * s / 0.36
        keys, vis = [], [(0, ("bool", False)), (HIT, ("bool", True))]
        t = HIT
        while True:
            u = t - HIT
            y = y0 + vy * u + 0.5 * gy * u * u
            if y > 0 and u > 0.1:
                vis.append((round(t, 4), ("bool", False)))
                break
            keys.append((round(t, 4), ("v2", x0 + vx * u, y)))
            t += 1 / FPS
        tr[f"{node}:position"] = [(0, keys[0][1])] + keys
        tr[f"{node}:rotation"] = [(kt, ("f", (kt - HIT) * rng.choice([-9, 9]))) for kt, _ in keys]
        tr[f"{node}:visible"] = vis

    # floating chips jump at the hit and settle back
    for k, name in enumerate(sorted(n for n in parts if n.startswith("chip_"))):
        x, y = parts[name]["_pos"]
        hop = (18 + 6 * (k % 3)) * s
        keys = []
        for f in range(int(LENGTH * FPS) + 1):
            t = f / FPS
            u = t - HIT - 0.03 * k
            lift = hop * math.exp(-3.0 * u) * abs(math.sin(5.0 * u)) if u > 0 else 0.0
            keys.append((t, ("v2", x, round(y - lift, 2))))
        tr[f"Chips/{parts[name]['_node']}:position"] = keys
    return tr
