"""Write the Godot 2D scene (godot2d/golem2d.tscn) from parts.json.

    python -m golem2d.scene --project godot2d

Every part becomes a Node2D at its pivot holding a Sprite2D, nested like the
parts ride on each other. The 6 s idle loop is baked into an AnimationPlayer
as keys every 0.25 s, so it can be retimed in the Godot editor.
"""
import argparse
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image

LENGTH = 6.0
STEP = 0.25
W = math.tau / LENGTH  # one cycle per loop


def camel(name):
    return "".join(s.capitalize() for s in name.split("_"))


def deg(d):
    return math.radians(d)


def breath(t):
    """0 at rest, 1 fully breathed in (t = 3 s)."""
    return (1 - math.cos(W * t)) / 2


# --- the idle loop: property -> function of time -------------------------------------------

def tracks(parts):
    tr = {}
    tr["Body:scale"] = lambda t: ("v2", 1 + 0.008 * breath(t), 1 + 0.02 * breath(t))
    for side, sign in (("l", 1), ("r", -1)):
        arm = f"Body/Arm{side.upper()}"
        tr[f"{arm}:rotation"] = lambda t, s=sign: ("f", s * deg(2.5) * breath(t - 0.35))
        for i, phase in ((1, 0.9), (2, 1.4), (3, 1.1)):
            path = f"{arm}/Weight{side.upper()}{i}:rotation"
            tr[path] = lambda t, s=sign, p=phase, i=i: (
                "f", s * (deg(7.0 if i == 2 else 9.0) * math.sin(W * t - p) + deg(2.0) * math.sin(2 * W * t - p)))
    tr["Body/WeightC:rotation"] = lambda t: ("f", deg(6.0) * math.sin(W * t - 0.6))
    tr["Body/Glow:modulate"] = lambda t: ("col", 0.05 + 0.25 * (0.5 - 0.5 * math.cos(2 * W * t)))
    chips = sorted(n for n in parts if n.startswith("chip_"))
    for k, name in enumerate(chips):
        node = f"Chips/{camel(name)}"
        base = parts[name]["_pos"]
        phase = k * 2.3
        freq = 2 if k % 3 == 0 else 1
        tr[f"{node}:position"] = lambda t, b=base, p=phase, f=freq: (
            "v2", b[0], b[1] - 12 * math.sin(f * W * t + p))
        tr[f"{node}:rotation"] = lambda t, p=phase: ("f", deg(14) * math.sin(W * t + p + 1))
    return tr


def fmt(v):
    kind, *x = v
    if kind == "f":
        return f"{x[0]:.6g}"
    if kind == "v2":
        return f"Vector2({x[0]:.6g}, {x[1]:.6g})"
    if kind == "col":
        return f"Color(1, 1, 1, {x[0]:.4g})"


def animation(rid, name, trs, rest=None):
    at_rest = rest is not None
    times = [0.0] if at_rest else list(np.arange(0, LENGTH + 1e-6, STEP))
    out = [f'[sub_resource type="Animation" id="{rid}"]', f'resource_name = "{name}"',
           f"length = {0.001 if at_rest else LENGTH}"]
    if not at_rest:
        out.append("loop_mode = 1")
    for i, (path, fn) in enumerate(trs.items()):
        vals = [fn(0.0 if at_rest else t) for t in times]
        if at_rest:  # rest pose: no breath, no swing
            vals = [rest.get(path, vals[0])]
        out += [f'tracks/{i}/type = "value"', f"tracks/{i}/imported = false", f"tracks/{i}/enabled = true",
                f'tracks/{i}/path = NodePath("{path}")', f"tracks/{i}/interp = 2", f"tracks/{i}/loop_wrap = true",
                f"tracks/{i}/keys = {{",
                f'"times": PackedFloat32Array({", ".join(f"{t:g}" for t in times)}),',
                f'"transitions": PackedFloat32Array({", ".join("1" for _ in times)}),',
                '"update": 0,',
                f'"values": [{", ".join(fmt(v) for v in vals)}]',
                "}"]
    return "\n".join(out)


def sparkle_texture(path, r=4):
    """A small soft four-pointed star."""
    n = 2 * r + 1
    y, x = np.mgrid[-r:r + 1, -r:r + 1].astype(float)
    star = np.maximum(np.clip(1 - np.abs(x) / 1.2, 0, 1) * np.clip(1 - np.abs(y) / r, 0, 1),
                      np.clip(1 - np.abs(y) / 1.2, 0, 1) * np.clip(1 - np.abs(x) / r, 0, 1))
    core = np.clip(1 - np.hypot(x, y) / 2.2, 0, 1)
    a = np.clip(np.maximum(star, core), 0, 1)
    rgba = np.zeros((n, n, 4), np.uint8)
    rgba[..., :3] = 255
    rgba[..., 3] = (a * 255).round()
    Image.fromarray(rgba, "RGBA").save(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default="godot2d")
    args = ap.parse_args()
    proj = Path(args.project)
    meta = json.loads((proj / "parts" / "parts.json").read_text())
    parts = meta["parts"]
    ox, oy = meta["origin"]
    sparkle_texture(proj / "parts" / "sparkle.png")

    def pivot(name):
        return parts[name]["pivot"] if name else [ox, oy]

    ext, sub, nodes = [], [], []
    tex_id = {}
    for i, name in enumerate(parts, start=1):
        tex_id[name] = f"{i}_tex"
        ext.append(f'[ext_resource type="Texture2D" path="res://parts/{parts[name]["file"]}" id="{i}_tex"]')
    ext.append('[ext_resource type="Script" path="res://golem2d.gd" id="script"]')
    ext.append('[ext_resource type="Texture2D" path="res://parts/sparkle.png" id="sparkle"]')

    def node(name, typ, parent, **props):
        head = f'[node name="{name}" type="{typ}"' + (f' parent="{parent}"' if parent is not None else "") + "]"
        body = [f"{k} = {v}" for k, v in props.items()]
        nodes.append("\n".join([head] + body))

    def v2(x, y):
        return f"Vector2({x:.6g}, {y:.6g})"

    def holder(name, parent_path, parent_name, z=None):
        """Node2D at the part's pivot with its sprite inside."""
        px, py = pivot(name)
        qx, qy = pivot(parent_name)
        node(camel(name), "Node2D", parent_path, position=v2(px - qx, py - qy))
        here = f"{parent_path}/{camel(name)}" if parent_path != "." else camel(name)
        x, y = parts[name]["pos"]
        props = {"texture": f'ExtResource("{tex_id[name]}")', "centered": "false", "offset": v2(x - px, y - py)}
        node("Sprite", "Sprite2D", here, **props)
        parts[name]["_pos"] = (px - qx, py - qy)
        return here

    node("Golem2D", "Node2D", None, script='ExtResource("script")')
    holder("legs", ".", None)
    body = holder("body", ".", None)
    # glow over the upper bulb of the hourglass
    sub.append('[sub_resource type="CanvasItemMaterial" id="add"]\nblend_mode = 1')
    holder("glow", body, "body")
    nodes[-1] += '\nmaterial = SubResource("add")'
    bx, by = pivot("body")

    # sand: grains falling down the stream, and glints in both bulbs
    sx0, sy0, sx1, sy1 = meta["stream"]
    sub.append('[sub_resource type="Gradient" id="fade"]\n'
               'offsets = PackedFloat32Array(0, 0.25, 0.75, 1)\n'
               'colors = PackedColorArray(1, 0.95, 0.7, 0, 1, 0.95, 0.7, 1, 1, 0.95, 0.7, 1, 1, 0.95, 0.7, 0)')
    sub.append('[sub_resource type="Curve" id="twinkle"]\n'
               '_data = [Vector2(0, 0), 0.0, 0.0, 0, 0, Vector2(0.5, 1), 0.0, 0.0, 0, 0, Vector2(1, 0), 0.0, 0.0, 0, 0]\n'
               'point_count = 3')
    node("SandStream", "CPUParticles2D", body, position=v2((sx0 + sx1) / 2 - bx, sy0 - by),
         material='SubResource("add")', amount=22, lifetime=0.62, preprocess=1.0,
         emission_shape=3, emission_rect_extents=v2(1, 1), direction=v2(0, 1), spread=0.0,
         gravity=v2(0, 260), initial_velocity_min=150.0, initial_velocity_max=170.0,
         scale_amount_min=1.2, scale_amount_max=2.0, color_ramp='SubResource("fade")')
    for nm, key, amount, size in (("GlintsTop", "top_sand", 10, 0.9), ("GlintsBottom", "bottom_sand", 12, 0.7)):
        x0, y0, x1, y1 = meta[key]
        node(nm, "CPUParticles2D", body, position=v2((x0 + x1) / 2 - bx, (y0 + y1) / 2 - by),
             material='SubResource("add")', texture='ExtResource("sparkle")', amount=amount, lifetime=1.6,
             preprocess=2.0, emission_shape=3, emission_rect_extents=v2((x1 - x0) / 2, (y1 - y0) / 2),
             gravity=v2(0, 0), initial_velocity_min=0.0, initial_velocity_max=4.0,
             scale_amount_min=size * 0.6, scale_amount_max=size, scale_amount_curve='SubResource("twinkle")',
             color="Color(1, 0.96, 0.75, 0.9)")

    holder("hand_hour", body, "body")
    holder("hand_minute", body, "body")
    holder("hub", body, "body")
    holder("weight_c", body, "body")
    for side in ("l", "r"):
        arm = holder(f"arm_{side}", body, "body")
        for i in (1, 2, 3):
            holder(f"weight_{side}{i}", arm, f"arm_{side}")
    node("Chips", "Node2D", ".")
    for name in sorted(n for n in parts if n.startswith("chip_")):
        holder(name, "Chips", None)

    trs = tracks(parts)
    rest = {"Body:scale": ("v2", 1.0, 1.0)}
    for path in trs:
        if path.endswith(":rotation"):
            rest[path] = ("f", 0.0)
        elif path.endswith(":modulate"):
            rest[path] = ("col", 0.05)
    sub.append(animation("idle", "idle", trs))
    sub.append(animation("reset", "RESET", trs, rest))
    sub.append('[sub_resource type="AnimationLibrary" id="lib"]\n_data = {\n'
               '&"RESET": SubResource("reset"),\n&"idle": SubResource("idle")\n}')
    node("AnimationPlayer", "AnimationPlayer", ".", libraries='{\n&"": SubResource("lib")\n}', autoplay='&"idle"')

    text = (f'[gd_scene load_steps={len(ext) + len(sub) + 1} format=3]\n\n' + "\n\n".join(ext) + "\n\n"
            + "\n\n".join(sub) + "\n\n" + "\n\n".join(nodes) + "\n")
    (proj / "golem2d.tscn").write_text(text)
    print(f"{proj / 'golem2d.tscn'}: {len(parts)} parts, {len(trs)} tracks")


if __name__ == "__main__":
    main()
