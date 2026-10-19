"""Step 3: the brass case on the chest — pillars, cornice, arch, base,
hourglass with its frame and sand, and the clock with its hands.

Measured from the front view (it wins over the close-ups where they differ).
"""
import math

import bmesh
import bpy
from mathutils import Matrix

from . import geo

REPLACES = [
    "case_base", "case_cornice", "case_arch", "case_pendant", "case_backplate", "hourglass_glass",
    "clock_hood", "clock_face", "clock_bezel", "clock_dome", "clock_finial",
    *[f"{n}.{s}" for n in ("case_pillar", "case_capital", "case_pedestal", "case_finial_low",
                           "clock_tower", "cornice_orb") for s in "LR"],
]

CASE_Y = -0.60      # front frame centre depth
GLASS_Y = -0.55     # hourglass axis depth
PX = 0.54           # pillar centre x
FRONT = -0.69       # front face of the pillars

# Hourglass glass profile (radius, z), bottom to top.
GLASS = [(0.0, 1.24), (0.17, 1.245), (0.25, 1.27), (0.30, 1.32), (0.325, 1.40), (0.33, 1.50),
         (0.32, 1.60), (0.29, 1.68), (0.22, 1.76), (0.12, 1.83), (0.05, 1.87), (0.03, 1.89),
         (0.05, 1.91), (0.12, 1.95), (0.22, 2.02), (0.29, 2.10), (0.32, 2.18), (0.33, 2.28),
         (0.325, 2.38), (0.30, 2.46), (0.25, 2.51), (0.17, 2.535), (0.0, 2.54)]

CLOCK_Z = 3.04
CLOCK_FACE_Y = -0.60


def _r_at(z):
    for (r0, z0), (r1, z1) in zip(GLASS, GLASS[1:]):
        if z0 <= z <= z1:
            return r0 + (r1 - r0) * (z - z0) / (z1 - z0)
    return 0.0


def _sub_profile(z0, z1, scale, steps=10):
    zs = sorted({z0, z1, *[z for _, z in GLASS if z0 < z < z1]})
    return [(_r_at(z) * scale, z) for z in zs]


def _disc_uv(name, center, radius, material, segments=32):
    """Disc facing -Y with planar UVs (for the clock face texture)."""
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    cx, cy, cz = center
    c = bm.verts.new(center)
    ring = [bm.verts.new((cx + radius * math.cos(a), cy, cz + radius * math.sin(a)))
            for a in (2 * math.pi * i / segments for i in range(segments))]
    for i in range(segments):
        f = bm.faces.new((c, ring[(i + 1) % segments], ring[i]))
        for loop in f.loops:
            x, z = loop.vert.co.x - cx, loop.vert.co.z - cz
            loop[uv].uv = (0.5 + x / (2 * radius), 0.5 + z / (2 * radius))
    return geo._link(name, bm, material)


def _hand(name, length, width, tail, angle_deg, material):
    """Clock hand pointing up in local space, rotated about the face axis."""
    w = width
    poly = [(0, -tail), (w * 0.6, 0), (w, length * 0.35), (w * 0.35, length * 0.75),
            (w * 1.4, length * 0.82), (0, length), (-w * 1.4, length * 0.82), (-w * 0.35, length * 0.75),
            (-w, length * 0.35), (-w * 0.6, 0)]
    ob = geo.extrude_xz(name, poly, -0.006, 0.006, material)
    ob.location = (0, CLOCK_FACE_Y - 0.02, CLOCK_Z)
    ob.rotation_euler = (0, math.radians(angle_deg), 0)
    return ob


def _medallion(name, center, r, br, dark):
    """Round boss with an X, as on the pillar capitals."""
    x, y, z = center
    parts = [geo.torus(name + "_ring", (x, y, z), (0, -1, 0), r, r * 0.22, br, 16, 6),
             geo.cylinder(name + "_disc", (x, y + 0.01, z), (x, y - 0.012, z), r * 0.85, dark, 16)]
    for k, a in enumerate((45, -45)):
        bar = geo.box(f"{name}_x{k}", (0, 0, 0), (r * 1.5, 0.02, r * 0.28), br)
        bar.location = (x, y - 0.018, z)
        bar.rotation_euler = (0, math.radians(a), 0)
        parts.append(bar)
    return parts


def _fluted_shaft(name, z0, z1, hw, hd, material, flutes=3, depth=0.012):
    """Square pilaster with `flutes` grooves on each face."""
    pts = []
    # walk the four faces counter-clockwise; each face gets notches
    corners = [(hw, -hd), (hw, hd), (-hw, hd), (-hw, -hd)]
    for k in range(4):
        (ax, ay), (bx, by) = corners[k], corners[(k + 1) % 4]
        nx, ny = (by - ay), -(bx - ax)
        ln = math.hypot(nx, ny)
        nx, ny = nx / ln, ny / ln
        pts.append((ax, ay))
        n = 2 * flutes + 1
        for i in range(1, n):
            t = i / n
            px, py = ax + (bx - ax) * t, ay + (by - ay) * t
            inset = depth if i % 2 == 1 else 0.0
            # each groove: two points at the groove floor
            t2 = (i + 1) / n
            qx, qy = ax + (bx - ax) * t2, ay + (by - ay) * t2
            if inset:
                pts.append((px, py))
                pts.append((px - nx * inset, py - ny * inset))
                pts.append((qx - nx * inset, qy - ny * inset))
                pts.append((qx, qy))
    return geo.prism(name, pts, z0, z1, (PX, CASE_Y, 0), material)


def build(mats):
    geo.remove(REPLACES)
    br, glass, face = mats["brass"], mats["glass"], mats["clock_face"]
    dark = mats["brass_dark"]
    left, centre = [], []

    # --- Pillars -----------------------------------------------------------
    left.append(_fluted_shaft("case_pillar.L", 1.33, 2.08, 0.095, 0.085, br))
    left.append(geo.square_lathe("case_pillar_base.L", [(0.13, 1.25), (0.13, 1.28), (0.115, 1.30), (0.105, 1.33)],
                                 (PX, CASE_Y), (1.0, 0.95), br))
    left.append(geo.square_lathe("case_capital.L", [(0.105, 2.08), (0.13, 2.10), (0.13, 2.13), (0.115, 2.14),
                                                    (0.115, 2.44), (0.14, 2.46), (0.14, 2.48)],
                                 (PX, CASE_Y), (1.0, 0.9), br))
    left += _medallion("capital_boss.L", (PX, CASE_Y - 0.115 * 0.9 - 0.005, 2.33), 0.055, br, dark)
    left.append(geo.box("capital_plaque.L", (PX, CASE_Y - 0.11, 2.18), (0.13, 0.02, 0.06), dark, bevel=0.006))
    left.append(geo.square_lathe("case_entablature.L", [(0.15, 2.48), (0.19, 2.51), (0.19, 2.55), (0.215, 2.59),
                                                        (0.215, 2.65), (0.20, 2.69)],
                                 (PX, CASE_Y - 0.01), (1.0, 1.4), br))
    left.append(geo.square_lathe("orb_stand.L", [(0.075, 2.69), (0.05, 2.72), (0.045, 2.76), (0.06, 2.78)],
                                 (PX - 0.02, CASE_Y - 0.05), (1.0, 1.0), br))
    left.append(geo.lathe("cornice_orb.L", [(0.0, 2.77), (0.06, 2.785), (0.085, 2.83), (0.085, 2.87),
                                            (0.06, 2.915), (0.02, 2.93), (0.015, 2.96), (0.0, 2.97)],
                          12, br, matrix=geo.axis_matrix((PX - 0.02, CASE_Y - 0.05, 0), (0, 0, 1))))

    # --- Base ----------------------------------------------------------------
    left.append(geo.square_lathe("case_plinth.L", [(0.13, 1.00), (0.155, 1.04), (0.155, 1.10), (0.13, 1.12),
                                                   (0.13, 1.20), (0.16, 1.23), (0.16, 1.30), (0.14, 1.32)],
                                 (PX, CASE_Y + 0.02), (1.0, 1.4), br))
    left.append(geo.square_lathe("case_pedestal.L", [(0.06, 0.86), (0.10, 0.90), (0.125, 0.96), (0.13, 1.00)],
                                 (PX, CASE_Y), (1.0, 1.0), br))
    left.append(geo.lathe("case_finial_low.L", [(0.0, 0.60), (0.03, 0.68), (0.05, 0.72), (0.02, 0.745), (0.04, 0.765),
                                                (0.06, 0.79), (0.035, 0.82), (0.065, 0.86)],
                          10, br, matrix=geo.axis_matrix((PX, CASE_Y, 0), (0, 0, 1))))

    def base_band(x0, top, bot, curve_top, curve_bot, steps=12):
        poly = []
        for i in range(steps + 1):
            x = -x0 + 2 * x0 * i / steps
            poly.append((x, bot + curve_bot * (x / x0) ** 2))
        for i in range(steps, -1, -1):
            x = -x0 + 2 * x0 * i / steps
            poly.append((x, top + curve_top * (x / x0) ** 2))
        return poly

    centre.append(geo.extrude_xz("case_base", base_band(0.44, 1.25, 1.04, 0.05, 0.10), -0.80, -0.36, br))
    centre.append(geo.extrude_xz("case_base_trim", base_band(0.44, 1.12, 1.07, 0.09, 0.09), -0.83, -0.79, dark))
    centre.append(geo.lathe("case_pendant", [(0.0, 0.62), (0.03, 0.70), (0.05, 0.74), (0.025, 0.77), (0.05, 0.80),
                                             (0.06, 0.86), (0.03, 0.90), (0.04, 0.96), (0.07, 1.06)],
                            10, br, matrix=geo.axis_matrix((0, CASE_Y - 0.02, 0), (0, 0, 1))))

    # --- Arch over the hourglass ------------------------------------------
    def arch(x0, top, rise_top, bot, rise_bot, steps=14):
        poly = []
        for i in range(steps + 1):
            x = -x0 + 2 * x0 * i / steps
            poly.append((x, bot + rise_bot * (1 - (x / x0) ** 2)))
        for i in range(steps, -1, -1):
            x = -x0 + 2 * x0 * i / steps
            poly.append((x, top + rise_top * (1 - (x / x0) ** 2)))
        return poly

    centre.append(geo.box("case_lintel", (0, CASE_Y, 2.56), (0.82, 0.34, 0.14), br, bevel=0.01))
    centre.append(geo.extrude_xz("case_arch", arch(0.46, 2.72, 0.14, 2.55, 0.10), -0.78, -0.42, br))
    centre.append(geo.extrude_xz("case_arch_trim", arch(0.42, 2.80, 0.12, 2.73, 0.12), -0.80, -0.77, br))

    # --- Hourglass ---------------------------------------------------------
    centre.append(geo.lathe("hourglass_glass", GLASS, 24, glass, matrix=geo.axis_matrix((0, GLASS_Y, 0), (0, 0, 1))))
    outline = [(_r_at(z) + 0.025, z) for _, z in GLASS[1:-1]]
    path = [(r, z) for r, z in outline] + [(-r, z) for r, z in reversed(outline)]
    centre.append(geo.sweep_xz("hourglass_frame", path, 0.04, 0.09, GLASS_Y, br))
    # brass wings either side of the neck
    wing = [(0.06, 1.89), (0.19, 1.76), (0.27, 1.80), (0.27, 1.98), (0.19, 2.02)]
    left.append(geo.extrude_xz("hourglass_wing.L", wing, GLASS_Y - 0.03, GLASS_Y + 0.03, br))
    for nm, z0, z1 in (("hourglass_cap_low", 1.21, 1.26), ("hourglass_cap_top", 2.52, 2.57)):
        centre.append(geo.cylinder(nm, (0, GLASS_Y, z0), (0, GLASS_Y, z1), 0.24, br, 16))
    sand = mats["sand_dark"]
    low = [(0.0, 1.26)] + _sub_profile(1.27, 1.68, 0.93) + [(0.15, 1.71), (0.0, 1.73)]
    centre.append(geo.lathe("sand_bottom", low, 20, sand, matrix=geo.axis_matrix((0, GLASS_Y, 0), (0, 0, 1))))
    top = [(0.0, 1.89)] + _sub_profile(1.90, 2.28, 0.93) + [(0.25, 2.29), (0.0, 2.27)]
    centre.append(geo.lathe("sand_top", top, 20, sand, matrix=geo.axis_matrix((0, GLASS_Y, 0), (0, 0, 1))))
    glow = [(0.0, 2.285)] + _sub_profile(2.29, 2.50, 0.88) + [(0.0, 2.51)]
    centre.append(geo.lathe("sand_glow", glow, 20, mats["sand_glow"], matrix=geo.axis_matrix((0, GLASS_Y, 0), (0, 0, 1))))
    centre.append(geo.cylinder("sand_stream", (0, GLASS_Y, 1.70), (0, GLASS_Y, 1.90), 0.012, mats["sand_glow"], 6))
    centre.append(geo.box("case_backplate", (0, -0.27, 1.9), (0.9, 0.05, 1.3), dark))

    # --- Clock ---------------------------------------------------------------
    centre.append(_disc_uv("clock_face", (0, CLOCK_FACE_Y, CLOCK_Z), 0.235, face))
    centre.append(geo.torus("clock_bezel", (0, CLOCK_FACE_Y - 0.005, CLOCK_Z), (0, -1, 0), 0.255, 0.028, br, 40, 8))
    centre.append(geo.torus("clock_bezel_outer", (0, CLOCK_FACE_Y + 0.03, CLOCK_Z), (0, -1, 0), 0.29, 0.02, br, 40, 6))
    centre.append(geo.cylinder("clock_drum", (0, CLOCK_FACE_Y + 0.01, CLOCK_Z), (0, -0.25, CLOCK_Z), 0.30, br, 32))
    centre.append(_hand("clock_hand_hour", 0.13, 0.014, 0.03, -60, mats["ink"]))
    centre.append(_hand("clock_hand_minute", 0.19, 0.011, 0.04, 62, mats["ink"]))
    centre.append(geo.ellipsoid("clock_hub", (0, CLOCK_FACE_Y - 0.03, CLOCK_Z), (0.022, 0.015, 0.022), br, 10, 6))
    # crest above the clock and the finial
    # ogee hood framing the clock: outer outline down to the arch
    crest = [(-0.34, 2.80), (-0.35, 3.05), (-0.31, 3.18), (-0.22, 3.26), (-0.10, 3.30), (-0.04, 3.33), (0.0, 3.37),
             (0.04, 3.33), (0.10, 3.30), (0.22, 3.26), (0.31, 3.18), (0.35, 3.05), (0.34, 2.80)]
    centre.append(geo.extrude_xz("clock_crest", crest, -0.58, -0.28, br))
    centre.append(geo.lathe("clock_finial", [(0.07, 3.30), (0.05, 3.33), (0.035, 3.35), (0.06, 3.37), (0.06, 3.39),
                                             (0.03, 3.41), (0.035, 3.44), (0.012, 3.46), (0.0, 3.50)],
                            10, br, matrix=geo.axis_matrix((0, -0.43, 0), (0, 0, 1))))
    left.append(geo.lathe("clock_tower.L", [(0.065, 2.70), (0.065, 2.78), (0.04, 2.81), (0.04, 2.97), (0.06, 2.99),
                                            (0.06, 3.12), (0.03, 3.14), (0.04, 3.17), (0.015, 3.20), (0.0, 3.23)],
                          12, br, matrix=geo.axis_matrix((0.40, -0.52, 0), (0, 0, 1))))
    left.append(geo.torus("clock_tower_eye.L", (0.40, -0.59, 3.06), (0, -1, 0), 0.04, 0.012, br, 12, 6))
    left.append(geo.ellipsoid("clock_tower_knob.L", (0.40, -0.58, 2.90), (0.035, 0.03, 0.035), br, 10, 6))

    for ob in left + centre:
        geo.shade(ob)
    for ob in list(left):
        geo.mirror_x(ob, ob.name[:-2] + ".R")
    return centre, left
