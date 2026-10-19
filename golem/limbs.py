"""Step 5: rock body and limbs, gauntlet gears, hands with claws, lanterns and
weights, leg bells, shoulder sockets and drips, and the back mechanism.

Front view wins where the sheet's views disagree.  Left side (+X) is built
and mirrored.
"""
import math
import random

import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

from . import geo, rockform, stone

REPLACES = [
    "torso_core", "pelvis", "back_wheel", "back_frame",
    *[f"{n}.{s}" for n in ("upperarm", "gear_big", "gear_small", "hand", "weight_0", "weight_1", "weight_2",
                           "leg", "foot") for s in "LR"],
]

SEG = 32


def _capsule(a, b, ra, rb, step=0.5):
    """Spheres along a segment (volumes for stone.carrier)."""
    a, b = Vector(a), Vector(b)
    n = max(2, int((b - a).length / (min(ra, rb) * step)) + 1)
    out = []
    for i in range(n):
        t = i / (n - 1)
        r = ra + (rb - ra) * t
        out.append((tuple(a.lerp(b, t)), (r, r, r), 2.0))
    return out


def _frame(axis):
    axis = Vector(axis).normalized()
    ref = Vector((0, 0, 1)) if abs(axis.z) < 0.9 else Vector((1, 0, 0))
    u = axis.cross(ref).normalized()
    return axis, u, axis.cross(u)


def ship_wheel(name, origin, axis, radius, mats, spokes=8, teeth=24, depth=0.045):
    """Brass wheel: toothed rim, inner ring, spokes, hub and a pale jewel."""
    br, dark = mats["brass"], mats["brass_dark"]
    o = Vector(origin)
    ax, u, v = _frame(axis)
    parts = [geo.gear(name + "_rim", o, ax, radius, teeth, depth, br, tooth=0.14, hole=0.8),
             geo.torus(name + "_ring", o + ax * depth * 0.5, ax, radius * 0.84, radius * 0.05, br, 48, 8),
             geo.torus(name + "_inner", o + ax * depth * 0.5, ax, radius * 0.34, radius * 0.04, br, 32, 6)]
    for k in range(spokes):
        a = 2 * math.pi * k / spokes
        d = u * math.cos(a) + v * math.sin(a)
        parts.append(geo.cylinder(f"{name}_spoke{k}", o + d * radius * 0.3 + ax * depth * 0.3,
                                  o + d * radius * 0.86 + ax * depth * 0.3, radius * 0.075, br, 10,
                                  radius_b=radius * 0.05))
    hub = geo.catmull_rom([(radius * 0.22, 0.0), (radius * 0.22, depth * 0.6), (radius * 0.17, depth * 1.0),
                           (radius * 0.1, depth * 1.2), (0.0, depth * 1.25)], 2)
    parts.append(geo.lathe(name + "_hub", hub, 32, br, matrix=geo.axis_matrix(o, ax)))
    parts.append(geo.ellipsoid(name + "_jewel", tuple(o + ax * depth * 1.3), (radius * 0.07,) * 3, mats["stone"], 12, 8))
    return parts


def small_gear(name, origin, axis, radius, mats, teeth=12):
    br = mats["brass"]
    o = Vector(origin)
    ax = Vector(axis).normalized()
    return [geo.gear(name, o, ax, radius, teeth, 0.035, br, tooth=0.35),
            geo.torus(name + "_ring", o + ax * 0.02, ax, radius * 0.6, radius * 0.08, br, 24, 6),
            geo.lathe(name + "_hub", [(radius * 0.3, 0.0), (radius * 0.28, 0.03), (radius * 0.15, 0.045), (0.0, 0.05)],
                      24, br, matrix=geo.axis_matrix(o, ax))]


def finial_weight(name, x, y, z_top, z_bot, mats, scale=1.0):
    """Hanging brass drop with a dark bulb (the sheet's 装飾パーツ)."""
    L = z_top - z_bot
    keys = [(0.0, 0.0), (0.012, 0.06), (0.03, 0.16), (0.045, 0.26), (0.05, 0.29), (0.035, 0.32), (0.02, 0.35),
            (0.035, 0.40), (0.04, 0.45), (0.02, 0.5), (0.01, 0.62), (0.01, 0.9), (0.02, 1.0)]
    prof = [(r * scale, z_bot + f * L) for r, f in geo.catmull_rom(keys, 2)]
    parts = [geo.lathe(name, prof, 24, mats["brass"], matrix=geo.axis_matrix((x, y, 0), (0, 0, 1)))]
    parts.append(geo.ellipsoid(name + "_bulb", (x, y, z_bot + 0.405 * L), (0.03 * scale, 0.03 * scale, 0.04 * scale),
                               mats["brass_dark"], 14, 8))
    return parts


def lantern(name, x, y, mats):
    br, glass = mats["brass"], mats["glass"]
    parts = []
    top = geo.catmull_rom([(0.0, 0.86), (0.03, 0.855), (0.07, 0.84), (0.082, 0.825), (0.08, 0.81),
                           (0.065, 0.80), (0.0, 0.80)], 2)
    parts.append(geo.lathe(name + "_cap", top, SEG, br, matrix=geo.axis_matrix((x, y, 0), (0, 0, 1))))
    bot = geo.catmull_rom([(0.0, 0.58), (0.05, 0.585), (0.075, 0.6), (0.078, 0.615), (0.065, 0.625), (0.0, 0.625)], 2)
    parts.append(geo.lathe(name + "_base", bot, SEG, br, matrix=geo.axis_matrix((x, y, 0), (0, 0, 1))))
    parts.append(geo.cylinder(name + "_glass", (x, y, 0.62), (x, y, 0.805), 0.058, glass, SEG))
    parts.append(geo.cylinder(name + "_light", (x, y, 0.64), (x, y, 0.78), 0.03, mats["sand_glow"], 16))
    for k in range(4):
        a = math.pi / 4 + k * math.pi / 2
        px, py = x + 0.064 * math.cos(a), y + 0.064 * math.sin(a)
        parts.append(geo.cylinder(f"{name}_bar{k}", (px, py, 0.615), (px, py, 0.81), 0.007, br, 6))
    parts.append(geo.cylinder(name + "_chain", (x, y, 0.45), (x, y, 0.585), 0.008, br, 6))
    parts += finial_weight(name + "_drop", x, y, 0.47, 0.13, mats, scale=1.25)
    return parts


def claws(name, cx, cy, z, ring, mats, seed, n=7):
    rng = random.Random(seed)
    parts = []
    for k in range(n):
        a = 2 * math.pi * (k + 0.5) / n + rng.uniform(-0.15, 0.15)
        d = Vector((math.cos(a), math.sin(a), 0))
        c = Vector((cx, cy, z))
        L = rng.uniform(0.18, 0.25)
        pts = [c + d * ring, c + d * (ring + 0.05) - Vector((0, 0, L * 0.35)),
               c + d * (ring + 0.04) - Vector((0, 0, L * 0.7)), c + d * (ring - 0.02) - Vector((0, 0, L))]
        pts = geo.catmull_rom([tuple(p) for p in pts], 4)
        m = len(pts)
        radii = [0.095 * (1 - i / (m - 1)) ** 0.5 + 0.025 for i in range(m)]
        parts.append(geo.tube(f"{name}_{k}", pts, radii, mats["rock_light"], 6))
    return parts


def rock(name, volumes, mats, seed, cobble=0.15, material="rock", spikes=0.12, **_):
    """One solid rock mass with a broken, faceted surface; returns [mass]."""
    lo, hi = cobble, cobble * 2.7
    return [rockform.solid(name, volumes, mats[material], seed, size_range=(lo, hi), spike_p=spikes * 0.6,
                           relief=0.05, tilt_deg=18, flatten=0.95, crack_p=0.8, crack_w=0.018, crack_d=0.035,
                           crease_w=0.03, smooth=0, warp=0.04, ink="all")]


def _surface_points(target, dirs_from, rng=None):
    """Ray-cast onto an object from outside: [(point, normal)]."""
    dg = bpy.context.evaluated_depsgraph_get()
    tree = BVHTree.FromObject(target, dg)
    out = []
    for c, d in dirs_from:
        c, d = Vector(c), Vector(d).normalized()
        hit = tree.ray_cast(c + d * 3, -d)
        if hit[0] is not None:
            out.append((hit[0], hit[1]))
    return out


def sockets(target, specs, mats, side):
    parts = []
    for i, (p, n) in enumerate(_surface_points(target, specs)):
        parts.append(geo.lathe(f"socket_{i}.{side}", [(0.085, 0.0), (0.09, 0.02), (0.07, 0.03), (0.0, 0.0)], 24,
                               mats["rock_dark"], matrix=geo.axis_matrix(p - n * 0.01, n)))
        parts.append(geo.torus(f"socket_ring_{i}.{side}", p + n * 0.018, n, 0.05, 0.012, mats["brass"], 24, 6))
        parts.append(geo.ellipsoid(f"socket_knob_{i}.{side}", tuple(p + n * 0.02), (0.028,) * 3, mats["brass"], 12, 8))
    return parts


def drips(name, mats, seed):
    """Dark rock drips hanging under the left shoulder."""
    rng = random.Random(seed)
    c, r = Vector((0.9, 0.1, 2.62)), Vector((0.6, 0.53, 0.55))
    parts = []
    for k in range(9):
        for _ in range(20):
            x, y = rng.uniform(0.45, 1.35), rng.uniform(-0.3, 0.45)
            q = 1 - ((x - c.x) / r.x) ** 2 - ((y - c.y) / r.y) ** 2
            if q > 0.15:
                break
        z = c.z - r.z * math.sqrt(q) + 0.04
        L = rng.uniform(0.08, 0.2)
        pts = geo.catmull_rom([(x, y, z), (x + rng.uniform(-0.02, 0.02), y, z - L * 0.5), (x, y, z - L)], 3)
        m = len(pts)
        radii = [rng.uniform(0.04, 0.06) * (1 - i / (m - 1)) ** 0.7 + 0.003 for i in range(m)]
        parts.append(geo.tube(f"{name}_{k}", pts, radii, mats["rock"], 8))
    return parts


def back_mechanism(mats):
    br, dark = mats["brass"], mats["brass_dark"]
    parts = ship_wheel("back_wheel", (0, 0.57, 2.68), (0, 1, 0), 0.38, mats, spokes=8, teeth=36, depth=0.06)
    parts.append(geo.torus("back_wheel_outer", (0, 0.55, 2.68), (0, 1, 0), 0.425, 0.022, br, 64, 8))
    for k in range(12):
        a = 2 * math.pi * k / 12
        parts.append(geo.ellipsoid(f"back_wheel_knob{k}", (0.425 * math.cos(a), 0.57, 2.68 + 0.425 * math.sin(a)),
                                   (0.025, 0.025, 0.025), br, 10, 6))
    # crest above the wheel
    parts.append(geo.lathe("back_crest", geo.catmull_rom([(0.07, 3.17), (0.05, 3.21), (0.03, 3.24), (0.045, 3.27),
                                                         (0.02, 3.30), (0.0, 3.33)], 2), 20, br,
                           matrix=geo.axis_matrix((0, 0.52, 0), (0, 0, 1))))
    # frame: fluted pillars like the front case, curved base band, band under the wheel
    from . import case
    py = 0.34
    for sx in (1, -1):
        x = 0.55 * sx
        s = "L" if sx > 0 else "R"
        parts.append(case._fluted_shaft(f"back_pillar.{s}", 1.30, 2.10, 0.085, 0.075, br, center=(x, py)))
        parts.append(geo.ring_lathe(f"back_pillar_base.{s}", [(0.12, 1.22), (0.12, 1.25), (0.11, 1.27), (0.1, 1.30)],
                                    (x, py), (1.0, 0.9), 0.012, 3, br))
        parts.append(geo.ring_lathe(f"back_capital.{s}", [(0.09, 2.10), (0.115, 2.12), (0.115, 2.30), (0.13, 2.32),
                                                          (0.14, 2.35), (0.14, 2.40)], (x, py), (1.0, 0.9), 0.012, 3, br))
        parts += case._medallion(f"back_boss.{s}", (x, py + 0.11, 2.21), 0.045, br, dark)
        bpy.context.view_layer.update()
        for ob in parts[-5:]:
            ob.data.transform(ob.matrix_world)  # bake the bars' placement first
            ob.matrix_world = Matrix.Identity(4)
            for v in ob.data.vertices:  # medallion faces +Y here
                v.co.y = 2 * (py + 0.11) - v.co.y
            ob.data.flip_normals()
        parts.append(geo.ring_lathe(f"back_plinth.{s}", [(0.11, 0.98), (0.14, 1.0), (0.14, 1.08), (0.12, 1.10),
                                                         (0.12, 1.16), (0.14, 1.18), (0.14, 1.22)],
                                    (x, py - 0.03), (1.0, 0.7), 0.014, 3, br))
        parts += finial_weight(f"back_finial.{s}", x, py - 0.04, 0.98, 0.66, mats)
        # scrollwork either side of the wheel
        lo = geo.catmull_rom([(0.40 * sx, 2.30), (0.52 * sx, 2.38), (0.58 * sx, 2.52)], 4) + \
            geo.spiral((0.53 * sx, 2.56), 0.05, 0.012, 1.1, a0=0.0 if sx > 0 else math.pi, flip=sx)[1:]
        parts.append(geo.scroll_xz(f"back_scroll_lo.{s}", lo, 0.55, 0.02, br))
        hi = geo.catmull_rom([(0.30 * sx, 3.06), (0.44 * sx, 3.0), (0.52 * sx, 2.88)], 4) + \
            geo.spiral((0.47 * sx, 2.85), 0.05, 0.012, 1.1, a0=0.0 if sx > 0 else math.pi, flip=-sx)[1:]
        parts.append(geo.scroll_xz(f"back_scroll_hi.{s}", hi, 0.55, 0.02, br))
        top = geo.catmull_rom([(0.0, 3.16), (0.1 * sx, 3.13), (0.2 * sx, 3.06)], 4) + \
            geo.spiral((0.17 * sx, 3.02), 0.04, 0.01, 1.0, a0=0.3 if sx > 0 else math.pi - 0.3, flip=-sx)[1:]
        parts.append(geo.scroll_xz(f"back_scroll_top.{s}", top, 0.56, 0.018, br))
    shield = geo.catmull_rom([(-0.50, 2.30), (-0.56, 2.55), (-0.54, 2.85), (-0.44, 3.05), (-0.25, 3.17),
                              (-0.08, 3.22), (0.0, 3.27), (0.08, 3.22), (0.25, 3.17), (0.44, 3.05), (0.54, 2.85),
                              (0.56, 2.55), (0.50, 2.30)], 3)
    housing = geo.extrude_xz("back_housing", shield, 0.44, 0.50, br)
    geo.bevel_all(housing, 0.015, 2)
    parts.append(housing)
    rim = geo.sweep_section_xz("back_housing_bead", list(reversed(shield)), geo.ellipse_section(0.016, 0.016, 10), 0.505)
    rim.data.materials.append(br)
    parts.append(rim)
    band_t = [(x, 2.36 + 0.06 * (1 - (x / 0.62) ** 2)) for x in [-0.62 + 1.24 * i / 24 for i in range(25)]]
    band_b = [(x, 2.24 + 0.08 * (1 - (x / 0.62) ** 2)) for x in [-0.62 + 1.24 * i / 24 for i in range(25)]]
    band = geo.extrude_xz("back_band", band_b + list(reversed(band_t)), py - 0.05, py + 0.12, br)
    geo.bevel_all(band, 0.014, 2)
    parts.append(band)
    base_t = [(x, 1.24 - 0.04 * (x / 0.55) ** 2) for x in [-0.55 + 1.1 * i / 24 for i in range(25)]]
    base_b = [(x, 1.02 + 0.08 * (x / 0.55) ** 2) for x in [-0.55 + 1.1 * i / 24 for i in range(25)]]
    base = geo.extrude_xz("back_base", base_b + list(reversed(base_t)), py - 0.12, py + 0.04, br)
    geo.bevel_all(base, 0.016, 2)
    parts.append(base)
    bead = geo.ellipse_section(0.013, 0.013, 10)
    for nm, curve in (("back_base_bead", base_b), ("back_band_bead", band_t)):
        ob = geo.sweep_section_xz(nm, curve if nm == "back_base_bead" else list(reversed(curve)), bead,
                                  py + (0.045 if nm == "back_base_bead" else 0.125))
        ob.data.materials.append(br)
        parts.append(ob)
    parts += finial_weight("back_pendant", 0.0, py - 0.04, 1.02, 0.62, mats, scale=1.2)
    # three pendulums
    for k, x in enumerate((-0.22, 0.0, 0.22)):
        top = 2.26
        bottom = 1.35 if k == 1 else 1.6
        parts.append(geo.cylinder(f"back_rod{k}", (x, 0.40, bottom + 0.3), (x, 0.40, top), 0.01, br, 8))
        parts += finial_weight(f"back_bob{k}", x, 0.40, bottom + 0.32, bottom, mats, scale=1.3 if k == 1 else 1.0)
    hang = lantern("back_lantern", 0.0, 0.41, mats)
    for ob in hang:
        ob.location.z += 1.20
    return parts + hang


def build(mats, seed=1):
    geo.remove(REPLACES)
    left, centre = [], []

    # torso core and pelvis
    centre += (rock("rock_torso", [((0, 0.0, 1.75), (0.58, 0.33, 0.8), 2.0), ((0, 0.0, 0.98), (0.55, 0.28, 0.22), 2.0)],
                       mats, seed + 20, cobble=0.17))

    # arm: one rock trunk from the shoulder to the wrist (the gauntlet crust sits on it)
    arm = (_capsule((1.0, 0.08, 2.32), (1.25, 0.07, 1.95), 0.25, 0.27)
           + [((1.37, 0.07, 1.74), (0.36, 0.32, 0.44), 2.4)]
           + _capsule((1.36, 0.05, 1.40), (1.28, 0.0, 1.08), 0.25, 0.18)
           + [((1.28, 0.0, 0.99), (0.19, 0.18, 0.11), 2.2)])
    left += rock("rock_arm.L", arm, mats, seed + 21, cobble=0.13)
    # wrist: brown weathered cuff peeling open, fluted pedestal, lantern and drops
    left += rockform.wrist_pieces("cuff.L", (1.28, 0.0), 0.23, 1.10, mats["rock_light"], seed + 23, outward=-0.65)
    left.append(rockform.fluted_drum("wrist_drum.L", (1.27, 0.0), 0.96, 0.86, 0.13, 0.095, mats["rock_light"]))
    left += lantern("lantern.L", 1.27, 0.0, mats)
    for k, x in enumerate((1.03, 1.50)):
        left += finial_weight(f"weight_{k}.L", x, -0.02, 0.80, 0.48, mats)
    left += ship_wheel("gear_big.L", (1.68, -0.20, 1.66), (0.6, -0.8, 0.0), 0.27, mats)
    left += small_gear("gear_small.L", (1.12, -0.33, 1.86), (0, -1, 0), 0.1, mats)
    left += small_gear("gear_back.L", (1.37, 0.44, 1.80), (0, 1, 0), 0.09, mats)

    # leg: one rock mass from hip to the broad, jagged foot, with brass bells at the knee
    leg = ([((0.44, -0.10, 0.82), (0.22, 0.27, 0.18), 2.0), ((0.44, -0.05, 0.96), (0.2, 0.2, 0.12), 2.0)]
           + _capsule((0.44, -0.06, 0.70), (0.44, -0.10, 0.2), 0.11, 0.13)
           + [((0.6, -0.13, 0.065), (0.34, 0.42, 0.08), 2.2), ((0.48, -0.12, 0.13), (0.17, 0.18, 0.07), 2.0)])
    left += rock("rock_leg.L", leg, mats, seed + 24, cobble=0.12, spikes=0.07)
    left += rockform.bark_flap("knee_cuff.L", (0.44, -0.08), 0.2, -2.3, -0.9, 0.93, 0.2, 0.05, mats["rock_light"],
                               seed + 27, curl=0.03)
    for k, (x, y_b) in enumerate(((0.66, -0.2), (0.2, -0.1))):
        bell = geo.catmull_rom([(0.0, 0.66), (0.01, 0.70), (0.03, 0.74), (0.07, 0.77), (0.078, 0.79), (0.05, 0.82),
                                (0.035, 0.85), (0.042, 0.87), (0.02, 0.9), (0.0, 0.92)], 2)
        left.append(geo.lathe(f"bell_{k}.L", bell, 24, mats["brass"], matrix=geo.axis_matrix((x, y_b, 0), (0, 0, 1))))
        left.append(geo.cylinder(f"bell_arm_{k}.L", (x, y_b, 0.83), (0.44 + (x - 0.44) * 0.4, -0.08, 0.83), 0.02,
                                 mats["brass"], 8))

    # shoulder sockets and drips
    plates = bpy.data.objects.get("shoulder_crust")
    if plates is not None:
        specs = [((0.9, 0.1, 2.62), (0.7, -0.6, 0.4)), ((0.9, 0.1, 2.62), (1.0, 0.0, -0.2)),
                 ((0.9, 0.1, 2.62), (0.2, 0.6, 0.6)), ((0.0, 0.05, 2.82), (0.55, -0.3, 1.0))]
        centre += sockets(plates, specs, mats, "L")
        mirrored = [((-c[0], c[1], c[2]), (-d[0], d[1], d[2])) for c, d in specs]
        centre += sockets(plates, mirrored, mats, "R")
    left += drips("drip.L", mats, seed + 26)

    centre += back_mechanism(mats)

    for ob in left + centre:
        geo.shade(ob, 40)
    for ob in list(left):
        geo.mirror_x(ob, ob.name[:-2] + ".R")
    return centre, left
