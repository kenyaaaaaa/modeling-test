"""Write the Godot 2D scene (godot2d/golem2d.tscn) from parts.json.

    python -m golem2d.scene --project godot2d

Every part becomes a Node2D at its pivot holding a Sprite2D, nested like the
parts ride on each other. Animations are held poses (MapleStory-style): every
key is discrete, so they can be retimed or re-posed key by key in Godot.

  idle    2.4 s loop, a pose every 0.2 s (two breaths; chips bob once)
  attack  ground slam (golem2d/attack.py); calls _on_attack_hit on the hit
  RESET   the rest pose
"""
import argparse
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image

from . import attack

IDLE_FRAMES = 12
IDLE_STEP = 0.2


def camel(name):
    return "".join(s.capitalize() for s in name.split("_"))


def deg(d):
    return math.radians(d)


# --- idle: a function of the frame number, held for IDLE_STEP each ----------------------------

def idle_tracks(parts):
    s = parts["_scale"]
    breath = lambda k: (1 - math.cos(math.tau * k / 6)) / 2  # two breaths per loop
    tr = {"Body:scale": lambda k: ("v2", 1 + 0.008 * breath(k), 1 + 0.02 * breath(k)),
          "Body/Glow:modulate": lambda k: ("col", 0.05 + 0.25 * breath(k)),
          "Body/WeightC:rotation": lambda k: ("f", deg(6.0) * math.sin(math.tau * (k - 1) / 6))}
    for side, sign in (("l", 1), ("r", -1)):
        arm = f"Body/Arm{side.upper()}"
        tr[f"{arm}:rotation"] = lambda k, sg=sign: ("f", sg * deg(2.5) * breath(k - 1))  # a frame behind
        for i, (amp, lag) in enumerate(((9.0, 2), (7.0, 2.5), (9.0, 2)), start=1):
            tr[f"{arm}/Weight{side.upper()}{i}:rotation"] = lambda k, sg=sign, a=amp, l=lag: (
                "f", sg * deg(a) * math.sin(math.tau * (k - l) / 6))
    for k, name in enumerate(sorted(n for n in parts if n.startswith("chip_"))):
        node = f"Chips/{parts[name]['_node']}"
        bx, by = parts[name]["_pos"]
        ph = k * 2.3
        tr[f"{node}:position"] = lambda f, bx=bx, by=by, p=ph: (
            "v2", bx, round(by - 12 * s * math.sin(math.tau * f / IDLE_FRAMES + p), 2))
        tr[f"{node}:rotation"] = lambda f, p=ph: ("f", deg(14) * math.sin(math.tau * f / IDLE_FRAMES + p + 1))
    return {path: [(k * IDLE_STEP, fn(k)) for k in range(IDLE_FRAMES)] for path, fn in tr.items()}


def rest_tracks(parts, fx):
    """Rest values of everything the animations move (one key each)."""
    tr = {"Body:position": ("v2", *parts["body"]["_pos"]), "Body:scale": ("v2", 1, 1), "Legs:scale": ("v2", 1, 1),
          "Body/Glow:modulate": ("col", 0.05), "Body/WeightC:rotation": ("f", 0.0)}
    for side in ("l", "r"):
        arm = f"Body/Arm{side.upper()}"
        tr[f"{arm}:rotation"] = ("f", 0.0)
        tr[f"{arm}/Sprite:texture"] = ("tex", f"arm_{side}")
        tr[f"{arm}/Sprite:offset"] = ("v2", *parts[f"arm_{side}"]["_offset"])
        for i in (1, 2, 3):
            tr[f"{arm}/Weight{side.upper()}{i}:rotation"] = ("f", 0.0)
            tr[f"{arm}/Weight{side.upper()}{i}:position"] = ("v2", *parts[f"weight_{side}{i}"]["_pos"])
    for node in ("Shockwave", "DustL", "DustR"):
        tr[f"{node}:visible"] = ("bool", False)
        tr[f"{node}:frame"] = ("int", 0)
    for k in range(parts["_shards"]):
        tr[f"Shards/Shard{k}:visible"] = ("bool", False)
    for name in (n for n in parts if n.startswith("chip_")):
        tr[f"Chips/{parts[name]['_node']}:position"] = ("v2", *parts[name]["_pos"])
        tr[f"Chips/{parts[name]['_node']}:rotation"] = ("f", 0.0)
    return tr


# --- writing the .tscn -----------------------------------------------------------------------

def animation(rid, name, length, trs, tex_id, loop=False, methods=()):
    def fmt(v):
        kind, *x = v
        return {"f": lambda: f"{x[0]:.6g}",
                "v2": lambda: f"Vector2({x[0]:.6g}, {x[1]:.6g})",
                "col": lambda: f"Color(1, 1, 1, {x[0]:.4g})",
                "tex": lambda: f'ExtResource("{tex_id[x[0]]}")',
                "bool": lambda: "true" if x[0] else "false",
                "int": lambda: str(int(x[0]))}[kind]()

    out = [f'[sub_resource type="Animation" id="{rid}"]', f'resource_name = "{name}"', f"length = {length:g}"]
    if loop:
        out.append("loop_mode = 1")
    i = -1
    for i, (path, keys) in enumerate(trs.items()):
        out += [f'tracks/{i}/type = "value"', f"tracks/{i}/imported = false", f"tracks/{i}/enabled = true",
                f'tracks/{i}/path = NodePath("{path}")', f"tracks/{i}/interp = 0", f"tracks/{i}/loop_wrap = true",
                f"tracks/{i}/keys = {{",
                f'"times": PackedFloat32Array({", ".join(f"{t:.4g}" for t, _ in keys)}),',
                f'"transitions": PackedFloat32Array({", ".join("1" for _ in keys)}),',
                '"update": 1,',
                f'"values": [{", ".join(fmt(v) for _, v in keys)}]',
                "}"]
    for j, (t, method) in enumerate(methods, start=i + 1):
        out += [f'tracks/{j}/type = "method"', f"tracks/{j}/imported = false", f"tracks/{j}/enabled = true",
                f'tracks/{j}/path = NodePath(".")', f"tracks/{j}/interp = 1", f"tracks/{j}/loop_wrap = true",
                f"tracks/{j}/keys = {{", f'"times": PackedFloat32Array({t:g}),',
                '"transitions": PackedFloat32Array(1),',
                f'"values": [{{\n"args": [],\n"method": &"{method}"\n}}]', "}"]
    return "\n".join(out)


def sparkle_texture(path, r=3):
    """A small soft four-pointed star."""
    n = 2 * r + 1
    y, x = np.mgrid[-r:r + 1, -r:r + 1].astype(float)
    star = np.maximum(np.clip(1 - np.abs(x) / 1.1, 0, 1) * np.clip(1 - np.abs(y) / r, 0, 1),
                      np.clip(1 - np.abs(y) / 1.1, 0, 1) * np.clip(1 - np.abs(x) / r, 0, 1))
    core = np.clip(1 - np.hypot(x, y) / 1.8, 0, 1)
    rgba = np.zeros((n, n, 4), np.uint8)
    rgba[..., :3] = 255
    rgba[..., 3] = (np.clip(np.maximum(star, core), 0, 1) * 255).round()
    Image.fromarray(rgba, "RGBA").save(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default="godot2d")
    args = ap.parse_args()
    proj = Path(args.project)
    meta = json.loads((proj / "parts" / "parts.json").read_text())
    parts, fx = meta["parts"], meta["fx"]
    s = meta["scale"]
    ox, oy = meta["origin"]
    sparkle_texture(proj / "parts" / "sparkle.png")

    def pivot(name):
        return parts[name]["pivot"] if name else [ox, oy]

    ext, sub, nodes = [], [], []
    tex_id = {}
    for i, name in enumerate(list(parts) + list(fx) + ["sparkle"], start=1):
        tex_id[name] = f"{i}_tex"
        file = parts[name]["file"] if name in parts else fx[name]["file"] if name in fx else "sparkle.png"
        ext.append(f'[ext_resource type="Texture2D" path="res://parts/{file}" id="{i}_tex"]')
    ext.append('[ext_resource type="Script" path="res://golem2d.gd" id="script"]')

    def node(name, typ, parent, **props):
        head = f'[node name="{name}" type="{typ}"' + (f' parent="{parent}"' if parent is not None else "") + "]"
        nodes.append("\n".join([head] + [f"{k} = {v}" for k, v in props.items()]))

    def v2(x, y):
        return f"Vector2({x:.6g}, {y:.6g})"

    def offset(name, piv_name=None):
        px, py = pivot(piv_name or name)
        x, y = parts[name]["pos"]
        return x - px, y - py

    def holder(name, parent_path, parent_name):
        """Node2D at the part's pivot with its sprite inside."""
        px, py = pivot(name)
        qx, qy = pivot(parent_name)
        parts[name]["_node"] = camel(name)
        parts[name]["_pos"] = (round(px - qx, 3), round(py - qy, 3))
        parts[name]["_offset"] = offset(name)
        node(camel(name), "Node2D", parent_path, position=v2(*parts[name]["_pos"]))
        here = f"{parent_path}/{camel(name)}" if parent_path != "." else camel(name)
        node("Sprite", "Sprite2D", here, texture=f'ExtResource("{tex_id[name]}")', centered="false",
             offset=v2(*parts[name]["_offset"]))
        return here

    for name, p in parts.items():  # swap images hang on their arm's pivot
        if p.get("swap_of"):
            p["_offset"] = offset(name, p["swap_of"])
    parts["_scale"] = s
    parts["_shards"] = 8

    node("Golem2D", "Node2D", None, script='ExtResource("script")')
    node("Shockwave", "Sprite2D", ".", visible="false", position=v2(0, -2 * s / 0.36),
         texture=f'ExtResource("{tex_id["fx_wave"]}")', hframes=fx["fx_wave"]["frames"])
    holder("legs", ".", None)
    body = holder("body", ".", None)
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
         material='SubResource("add")', amount=14, lifetime=0.62, preprocess=1.0,
         emission_shape=3, emission_rect_extents=v2(0.5, 0.5), direction=v2(0, 1), spread=0.0,
         gravity=v2(0, 260 * s), initial_velocity_min=150.0 * s, initial_velocity_max=170.0 * s,
         scale_amount_min=1.0, scale_amount_max=1.0, color_ramp='SubResource("fade")')
    for nm, key, amount, size in (("GlintsTop", "top_sand", 8, 0.8), ("GlintsBottom", "bottom_sand", 9, 0.6)):
        x0, y0, x1, y1 = meta[key]
        node(nm, "CPUParticles2D", body, position=v2((x0 + x1) / 2 - bx, (y0 + y1) / 2 - by),
             material='SubResource("add")', texture=f'ExtResource("{tex_id["sparkle"]}")', amount=amount,
             lifetime=1.6, preprocess=2.0, emission_shape=3, emission_rect_extents=v2((x1 - x0) / 2, (y1 - y0) / 2),
             gravity=v2(0, 0), initial_velocity_min=0.0, initial_velocity_max=1.5,
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

    # dust where the arms land, shards thrown from there
    dcell = fx["fx_dust"]["cell"]
    parts["_dust_x"] = [round(parts[f"weight_{sd}2"]["pivot"][0] - ox, 2) for sd in ("l", "r")]
    for nm, x in zip(("DustL", "DustR"), parts["_dust_x"]):
        node(nm, "Sprite2D", ".", visible="false", position=v2(x, -dcell[1] / 2 + 3 * s / 0.36),
             texture=f'ExtResource("{tex_id["fx_dust"]}")', hframes=fx["fx_dust"]["frames"])
    node("Shards", "Node2D", ".")
    for k in range(parts["_shards"]):
        node(f"Shard{k}", "Sprite2D", "Shards", visible="false",
             texture=f'ExtResource("{tex_id["fx_shard"]}")', hframes=fx["fx_shard"]["frames"],
             frame=k % fx["fx_shard"]["frames"])
    node("Chips", "Node2D", ".")
    for name in sorted(n for n in parts if n.startswith("chip_")):
        holder(name, "Chips", None)

    rest = rest_tracks(parts, fx)
    idle = idle_tracks(parts)
    for path, v in rest.items():  # anything idle doesn't move is put back to rest when it starts
        idle.setdefault(path, [(0.0, v)])
    sub.append(animation("idle", "idle", IDLE_FRAMES * IDLE_STEP, idle, tex_id, loop=True))
    sub.append(animation("attack", "attack", attack.LENGTH, attack.tracks(parts, fx), tex_id,
                         methods=[(attack.HIT, "_on_attack_hit")]))
    sub.append(animation("reset", "RESET", 0.001, {p: [(0.0, v)] for p, v in rest.items()}, tex_id))
    sub.append('[sub_resource type="AnimationLibrary" id="lib"]\n_data = {\n'
               '&"RESET": SubResource("reset"),\n&"attack": SubResource("attack"),\n&"idle": SubResource("idle")\n}')
    node("AnimationPlayer", "AnimationPlayer", ".", libraries='{\n&"": SubResource("lib")\n}', autoplay='&"idle"')

    text = (f'[gd_scene load_steps={len(ext) + len(sub) + 1} format=3]\n\n' + "\n\n".join(ext) + "\n\n"
            + "\n\n".join(sub) + "\n\n" + "\n\n".join(nodes) + "\n")
    (proj / "golem2d.tscn").write_text(text)
    print(f"{proj / 'golem2d.tscn'}: {len(parts) - 4} parts, idle {len(idle)} tracks")


if __name__ == "__main__":
    main()
