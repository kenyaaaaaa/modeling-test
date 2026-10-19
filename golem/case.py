"""Step 3: the brass case on the chest — pillars, cornice, arch, base,
hourglass with its frame and sand, and the clock with its hands.

Measured from the front view (it wins over the close-ups where they differ).
Detail level is set for a 100k-triangle character: mouldings have rounded
corners, edges carry small bevels and frames are round beads.
"""
import math

import bmesh

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
SEG = 48            # segments of large round parts
SEG_S = 24          # segments of small round parts

# Hourglass glass profile (radius, z), bottom to top; smoothed below.
GLASS_KEYS = [(0.0, 1.24), (0.17, 1.245), (0.25, 1.27), (0.30, 1.32), (0.325, 1.40), (0.33, 1.50),
              (0.32, 1.60), (0.29, 1.68), (0.22, 1.76), (0.12, 1.83), (0.05, 1.87), (0.03, 1.89),
              (0.05, 1.91), (0.12, 1.95), (0.22, 2.02), (0.29, 2.10), (0.32, 2.18), (0.33, 2.28),
              (0.325, 2.38), (0.30, 2.46), (0.25, 2.51), (0.17, 2.535), (0.0, 2.54)]
GLASS = geo.catmull_rom(GLASS_KEYS, 3)

CLOCK_Z = 3.04
CLOCK_FACE_Y = -0.60


def _r_at(z):
    for (r0, z0), (r1, z1) in zip(GLASS, GLASS[1:]):
        if z0 <= z <= z1 and z1 > z0:
            return r0 + (r1 - r0) * (z - z0) / (z1 - z0)
    return 0.0


def _sub_profile(z0, z1, scale, n=16):
    return [(_r_at(z0 + (z1 - z0) * i / n) * scale, z0 + (z1 - z0) * i / n) for i in range(n + 1)]


def _up(x, y):
    return geo.axis_matrix((x, y, 0), (0, 0, 1))


def _disc_uv(name, center, radius, material, segments=64):
    """Disc facing -Y with planar UVs (for the clock face texture)."""
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    cx, cy, cz = center
    c = bm.verts.new(center)
    ring = [bm.verts.new((cx + radius * math.cos(a), cy, cz + radius * math.sin(a)))
            for a in (2 * math.pi * i / segments for i in range(segments))]
    for i in range(segments):
        f = bm.faces.new((c, ring[i], ring[(i + 1) % segments]))   # normal -Y (towards the viewer)
        for loop in f.loops:
            x, z = loop.vert.co.x - cx, loop.vert.co.z - cz
            loop[uv].uv = (0.5 + x / (2 * radius), 0.5 + z / (2 * radius))
    return geo._link(name, bm, material)


def _hand(name, length, width, tail, angle_deg, material):
    """Spade clock hand pointing up in local space, rotated about the face axis."""
    w, L = width, length
    half = [(0.0, -tail), (w * 0.9, -tail * 0.8), (w * 1.2, -tail * 0.3), (w * 0.7, 0.0), (w * 0.8, L * 0.12),
            (w * 0.55, L * 0.55), (w * 0.4, L * 0.66), (w * 1.6, L * 0.74), (w * 1.9, L * 0.8),
            (w * 1.2, L * 0.86), (w * 0.4, L * 0.93), (0.0, L)]
    poly = half + [(-x, z) for x, z in reversed(half[1:-1])]
    ob = geo.extrude_xz(name, poly, -0.006, 0.006, material)
    ob.location = (0, CLOCK_FACE_Y - 0.03, CLOCK_Z)
    ob.rotation_euler = (0, math.radians(angle_deg), 0)
    return ob


def _medallion(name, center, r, br, dark):
    """Round boss with an X, as on the pillar capitals."""
    x, y, z = center
    parts = [geo.torus(name + "_ring", (x, y, z), (0, -1, 0), r, r * 0.2, br, 32, 8),
             geo.lathe(name + "_disc", [(r * 0.85, 0.0), (r * 0.85, 0.008), (r * 0.6, 0.014), (0.0, 0.016)], 32, dark,
                       matrix=geo.axis_matrix((x, y + 0.006, z), (0, -1, 0)))]
    for k, a in enumerate((45, -45)):
        bar = geo.box(f"{name}_x{k}", (0, 0, 0), (r * 1.55, 0.018, r * 0.26), br)
        geo.bevel_all(bar, 0.003, 1)
        bar.location = (x, y - 0.014, z)
        bar.rotation_euler = (0, math.radians(a), 0)
        parts.append(bar)
    parts.append(geo.ellipsoid(name + "_knob", (x, y - 0.022, z), (r * 0.22, r * 0.15, r * 0.22), br, 12, 6))
    return parts


def _fluted_shaft(name, z0, z1, hw, hd, material, flutes=3, depth=0.011, groove_pts=5, center=(PX, CASE_Y)):
    """Square pilaster with rounded grooves on each face, slightly tapered."""
    pts = []
    corners = [(hw, -hd), (hw, hd), (-hw, hd), (-hw, -hd)]
    for k in range(4):
        (ax, ay), (bx, by) = corners[k], corners[(k + 1) % 4]
        ex, ey = bx - ax, by - ay
        ln = math.hypot(ex, ey)
        nx, ny = ey / ln, -ex / ln   # outward
        pts.append((ax, ay))
        n = 2 * flutes + 1
        for i in range(1, n, 2):
            t0, t1 = i / n, (i + 1) / n
            for g in range(groove_pts + 1):
                t = t0 + (t1 - t0) * g / groove_pts
                d = depth * math.sin(math.pi * g / groove_pts)
                pts.append((ax + ex * t - nx * d, ay + ey * t - ny * d))
    return geo.prism(name, pts, z0, z1, (center[0], center[1], 0), material, top_scale=0.96)


def _arch_curve(x0, base, rise, n=24):
    return [(-x0 + 2 * x0 * i / n, base + rise * (1 - ((-x0 + 2 * x0 * i / n) / x0) ** 2)) for i in range(n + 1)]


def _band(top, bot):
    """Closed polygon between two curves of equal sampling (x, z)."""
    return bot + list(reversed(top))


def build(mats):
    geo.remove(REPLACES)
    br, glass, face = mats["brass"], mats["glass"], mats["clock_face"]
    dark = mats["brass_dark"]
    left, centre = [], []
    bead = geo.ellipse_section(0.014, 0.014, 10)

    # --- Pillars -----------------------------------------------------------
    left.append(_fluted_shaft("case_pillar.L", 1.345, 2.065, 0.093, 0.083, br))
    left.append(geo.ring_lathe("case_pillar_base.L",
                               [(0.135, 1.25), (0.135, 1.27), (0.128, 1.278), (0.12, 1.29), (0.124, 1.30),
                                (0.124, 1.31), (0.114, 1.32), (0.104, 1.333), (0.098, 1.345)],
                               (PX, CASE_Y), (1.0, 0.92), 0.012, 3, br))
    left.append(geo.ring_lathe("case_pillar_astragal.L",
                               [(0.09, 2.055), (0.102, 2.062), (0.104, 2.07), (0.102, 2.078), (0.096, 2.085)],
                               (PX, CASE_Y), (1.0, 0.92), 0.01, 3, br))
    left.append(geo.ring_lathe("case_capital.L",
                               [(0.1, 2.085), (0.12, 2.095), (0.128, 2.108), (0.128, 2.128), (0.118, 2.14),
                                (0.118, 2.43), (0.126, 2.438), (0.134, 2.448), (0.142, 2.462), (0.142, 2.48)],
                               (PX, CASE_Y), (1.0, 0.9), 0.012, 3, br))
    cap_front = CASE_Y - 0.118 * 0.9
    panel = geo.catmull_rom([(PX + x, z) for x, z in geo.rounded_rect(0.088, 0.13, 0.02, 2)], 1, closed=True)
    panel = [(x, z + 2.29) for x, z in panel]
    left.append(geo.sweep_section_xz("capital_panel.L", panel, geo.ellipse_section(0.007, 0.007, 6),
                                     cap_front - 0.004, br, closed=True))
    left += _medallion("capital_boss.L", (PX, cap_front - 0.006, 2.335), 0.055, br, dark)
    plaque = geo.box("capital_plaque.L", (PX, cap_front - 0.006, 2.205), (0.12, 0.016, 0.055), br)
    geo.bevel_all(plaque, 0.006, 2)
    left.append(plaque)
    left.append(geo.sweep_section_xz("capital_scroll.L",
                                     geo.catmull_rom([(PX - 0.045, 2.19), (PX - 0.025, 2.22), (PX, 2.2),
                                                      (PX + 0.025, 2.22), (PX + 0.045, 2.19)], 4),
                                     geo.ellipse_section(0.006, 0.006, 6), cap_front - 0.016, br))
    left.append(geo.ring_lathe("case_entablature.L",
                               [(0.15, 2.48), (0.168, 2.488), (0.188, 2.503), (0.19, 2.53), (0.18, 2.54),
                                (0.196, 2.552), (0.212, 2.57), (0.222, 2.592), (0.222, 2.645), (0.214, 2.658),
                                (0.205, 2.672), (0.205, 2.69)],
                               (PX, CASE_Y - 0.01), (1.0, 1.4), 0.016, 3, br))
    left.append(geo.lathe("orb_stand.L", [(0.075, 2.69), (0.07, 2.70), (0.05, 2.712), (0.042, 2.73), (0.046, 2.75),
                                          (0.058, 2.76), (0.062, 2.775), (0.0, 2.775)],
                          SEG_S, br, matrix=_up(PX - 0.02, CASE_Y - 0.05)))
    orb = geo.catmull_rom([(0.0, 2.775), (0.05, 2.785), (0.08, 2.81), (0.088, 2.85), (0.08, 2.89), (0.055, 2.915),
                           (0.022, 2.93), (0.018, 2.945), (0.026, 2.955), (0.012, 2.97), (0.0, 2.975)], 2)
    left.append(geo.lathe("cornice_orb.L", orb, SEG_S, br, matrix=_up(PX - 0.02, CASE_Y - 0.05)))
    left.append(geo.torus("cornice_orb_band.L", (PX - 0.02, CASE_Y - 0.05, 2.85), (0, 0, 1), 0.089, 0.008, br, SEG_S, 6))

    # --- Base ----------------------------------------------------------------
    left.append(geo.ring_lathe("case_plinth.L",
                               [(0.12, 0.99), (0.14, 1.0), (0.155, 1.02), (0.158, 1.04), (0.158, 1.10),
                                (0.145, 1.11), (0.132, 1.122), (0.132, 1.195), (0.146, 1.205), (0.16, 1.225),
                                (0.162, 1.29), (0.152, 1.305), (0.14, 1.32)],
                               (PX, CASE_Y + 0.02), (1.0, 1.4), 0.016, 3, br))
    left.append(geo.ring_lathe("case_pedestal.L",
                               [(0.05, 0.855), (0.07, 0.865), (0.09, 0.88), (0.11, 0.91), (0.125, 0.95),
                                (0.13, 0.975), (0.13, 0.99)],
                               (PX, CASE_Y), (1.0, 1.0), 0.012, 3, br))
    finial = geo.catmull_rom([(0.0, 0.60), (0.012, 0.63), (0.03, 0.68), (0.045, 0.712), (0.05, 0.725),
                              (0.036, 0.736), (0.026, 0.746), (0.04, 0.756), (0.045, 0.766), (0.03, 0.776),
                              (0.05, 0.79), (0.062, 0.81), (0.06, 0.83), (0.04, 0.845), (0.065, 0.86)], 2)
    left.append(geo.lathe("case_finial_low.L", finial, SEG_S, br, matrix=_up(PX, CASE_Y)))

    x0 = 0.44
    top = [(x, z + 0.05 * (x / x0) ** 2) for x, z in _arch_curve(x0, 1.25, 0.0)]
    bot = [(x, z + 0.10 * (x / x0) ** 2) for x, z in _arch_curve(x0, 1.04, 0.0)]
    base = geo.extrude_xz("case_base", _band(top, bot), -0.80, -0.36, br)
    geo.bevel_all(base, 0.014, 2)
    centre.append(base)
    trim_t = [(x, z + 0.09 * (x / x0) ** 2) for x, z in _arch_curve(x0 - 0.02, 1.12, 0.0)]
    trim_b = [(x, z + 0.09 * (x / x0) ** 2) for x, z in _arch_curve(x0 - 0.02, 1.075, 0.0)]
    trim = geo.extrude_xz("case_base_trim", _band(trim_t, trim_b), -0.815, -0.79, br)
    geo.bevel_all(trim, 0.006, 1)
    centre.append(trim)
    centre.append(geo.sweep_section_xz("case_base_bead_top", list(reversed(top)), bead, -0.80))
    centre.append(geo.sweep_section_xz("case_base_bead_bot", bot, bead, -0.80))
    for ob in centre[-2:]:
        ob.data.materials.append(br)
    pendant = geo.catmull_rom([(0.0, 0.62), (0.015, 0.65), (0.03, 0.70), (0.05, 0.74), (0.025, 0.77),
                               (0.05, 0.80), (0.06, 0.86), (0.03, 0.90), (0.04, 0.96), (0.07, 1.06)], 2)
    centre.append(geo.lathe("case_pendant", pendant, SEG_S, br, matrix=_up(0, CASE_Y - 0.02)))

    # --- Arch over the hourglass ------------------------------------------
    lintel = geo.box("case_lintel", (0, CASE_Y + 0.17, 2.6), (0.82, 0.3, 0.14), br)
    geo.bevel_all(lintel, 0.012, 2)
    centre.append(lintel)
    a_top, a_bot = _arch_curve(0.46, 2.72, 0.14), _arch_curve(0.46, 2.55, 0.10)
    arch = geo.extrude_xz("case_arch", _band(a_top, a_bot), -0.78, -0.42, br)
    geo.bevel_all(arch, 0.016, 2)
    centre.append(arch)
    t_top, t_bot = _arch_curve(0.42, 2.80, 0.12), _arch_curve(0.42, 2.73, 0.12)
    arch_trim = geo.extrude_xz("case_arch_trim", _band(t_top, t_bot), -0.80, -0.76, br)
    geo.bevel_all(arch_trim, 0.01, 2)
    centre.append(arch_trim)
    for nm, curve, y in (("case_arch_bead", a_top, -0.785), ("case_arch_bead_low", a_bot, -0.785)):
        ob = geo.sweep_section_xz(nm, list(reversed(curve)) if nm.endswith("bead") else curve, bead, y)
        ob.data.materials.append(br)
        centre.append(ob)
    left.append(geo.torus("case_arch_scroll.L", (0.45, -0.80, 2.70), (0, -1, 0), 0.03, 0.011, br, SEG_S, 8))

    # --- Hourglass ---------------------------------------------------------
    centre.append(geo.lathe("hourglass_glass", GLASS, SEG, glass, matrix=_up(0, GLASS_Y)))
    inner = [(r, z) for r, z in GLASS if 0 < r][1:-1]
    outline = [(_r_at(z) + 0.034, z) for _, z in inner]
    path = [(r, z) for r, z in outline] + [(-r, z) for r, z in reversed(outline)]
    centre.append(geo.sweep_section_xz("hourglass_frame", path, geo.ellipse_section(0.03, 0.04, 14), GLASS_Y,
                                       br, closed=True))
    thin = [(_r_at(z) + 0.004, z) for _, z in inner]
    thin = thin[::2]
    path2 = [(r, z) for r, z in thin] + [(-r, z) for r, z in reversed(thin)]
    centre.append(geo.sweep_section_xz("hourglass_frame_inner", path2, geo.ellipse_section(0.006, 0.01, 6),
                                       GLASS_Y - 0.035, br, closed=True))
    # brass wings either side of the neck, following the bulbs
    lower = [(_r_at(z) + 0.02, z) for z in (1.89, 1.87, 1.845, 1.82, 1.79, 1.765)]
    upper = [(_r_at(z) + 0.02, z) for z in (2.02, 1.99, 1.96, 1.935, 1.91, 1.89)]
    wing = lower + [(0.30, 1.78), (0.31, 1.89), (0.30, 2.0)] + upper[:-1]
    w = geo.extrude_xz("hourglass_wing.L", wing, GLASS_Y + 0.0, GLASS_Y + 0.05, br)
    geo.bevel_all(w, 0.008, 2)
    left.append(w)
    cap = geo.catmull_rom([(0.0, 1.19), (0.215, 1.19), (0.245, 1.198), (0.255, 1.212), (0.248, 1.226),
                           (0.232, 1.234), (0.24, 1.248), (0.22, 1.262), (0.19, 1.27), (0.0, 1.27)], 1)
    centre.append(geo.lathe("hourglass_cap_low", cap, SEG, br, matrix=_up(0, GLASS_Y)))
    cap_top = [(r, 3.78 - z) for r, z in reversed(cap)]
    centre.append(geo.lathe("hourglass_cap_top", cap_top, SEG, br, matrix=_up(0, GLASS_Y)))
    sand = mats["sand_dark"]
    low = [(0.0, 1.255)] + _sub_profile(1.26, 1.79, 0.94) + [(0.06, 1.81), (0.0, 1.815)]
    centre.append(geo.lathe("sand_bottom", low, 32, sand, matrix=_up(0, GLASS_Y)))
    top_sand = [(0.0, 1.89)] + _sub_profile(1.895, 2.27, 0.94) + [(0.24, 2.285), (0.12, 2.28), (0.0, 2.27)]
    ob = geo.lathe("sand_top", top_sand, 32, sand, matrix=_up(0, GLASS_Y))

    def wave(co):
        if co.z > 2.25:
            r = math.hypot(co.x, co.y - GLASS_Y)
            co.z += 0.014 * math.sin(3 * math.atan2(co.y - GLASS_Y, co.x)) * min(1.0, r / 0.25)
        return co
    centre.append(geo.displace(ob, wave))
    glow = [(0.0, 2.29)] + _sub_profile(2.30, 2.50, 0.88) + [(0.0, 2.51)]
    centre.append(geo.lathe("sand_glow", glow, 32, mats["sand_glow"], matrix=_up(0, GLASS_Y)))
    centre.append(geo.cylinder("sand_stream", (0, GLASS_Y, 1.80), (0, GLASS_Y, 1.90), 0.012, mats["sand_glow"], 8))
    back = geo.box("case_backplate", (0, -0.27, 1.9), (0.9, 0.05, 1.3), dark)
    geo.bevel_all(back, 0.01, 1)
    centre.append(back)

    # --- Clock ---------------------------------------------------------------
    centre.append(_disc_uv("clock_face", (0, CLOCK_FACE_Y, CLOCK_Z), 0.235, face))
    centre.append(geo.torus("clock_bezel", (0, CLOCK_FACE_Y - 0.005, CLOCK_Z), (0, -1, 0), 0.256, 0.026, br, 64, 12))
    centre.append(geo.torus("clock_bezel_inner", (0, CLOCK_FACE_Y - 0.004, CLOCK_Z), (0, -1, 0), 0.234, 0.007, br, 64, 6))
    centre.append(geo.torus("clock_bezel_outer", (0, CLOCK_FACE_Y + 0.03, CLOCK_Z), (0, -1, 0), 0.292, 0.02, br, 64, 8))
    for i in range(12):
        a = 2 * math.pi * i / 12
        centre.append(geo.ellipsoid(f"clock_stud_{i:02d}", (0.292 * math.sin(a), CLOCK_FACE_Y + 0.01,
                                                             CLOCK_Z + 0.292 * math.cos(a)),
                                    (0.012, 0.01, 0.012), br, 8, 5))
    centre.append(geo.cylinder("clock_drum", (0, CLOCK_FACE_Y + 0.03, CLOCK_Z), (0, -0.25, CLOCK_Z), 0.30, br, SEG))
    centre.append(_hand("clock_hand_hour", 0.14, 0.012, 0.035, -60, mats["ink"]))
    centre.append(_hand("clock_hand_minute", 0.20, 0.009, 0.045, 62, mats["ink"]))
    centre.append(geo.lathe("clock_hub", [(0.026, 0.0), (0.026, 0.012), (0.016, 0.022), (0.0, 0.026)], SEG_S, br,
                            matrix=geo.axis_matrix((0, CLOCK_FACE_Y - 0.032, CLOCK_Z), (0, -1, 0))))
    # ogee hood framing the clock: backing plate and a round bead on its edge
    crest = geo.catmull_rom([(-0.34, 2.80), (-0.35, 3.05), (-0.31, 3.18), (-0.22, 3.26), (-0.10, 3.30),
                             (-0.04, 3.33), (0.0, 3.37), (0.04, 3.33), (0.10, 3.30), (0.22, 3.26), (0.31, 3.18),
                             (0.35, 3.05), (0.34, 2.80)], 3)
    plate = geo.extrude_xz("clock_crest", crest, -0.56, -0.28, br)
    geo.bevel_all(plate, 0.012, 2)
    centre.append(plate)
    edge = geo.sweep_section_xz("clock_crest_bead", list(reversed(crest)), geo.ellipse_section(0.016, 0.016, 10), -0.565)
    edge.data.materials.append(br)
    centre.append(edge)
    dome = geo.ellipsoid("clock_dome", (0, -0.22, 3.18), (0.3, 0.24, 0.17), br, SEG, 16)
    centre.append(dome)
    finial_top = geo.catmull_rom([(0.075, 3.30), (0.06, 3.325), (0.04, 3.345), (0.035, 3.355), (0.058, 3.37),
                                  (0.062, 3.385), (0.05, 3.40), (0.03, 3.41), (0.036, 3.43), (0.02, 3.45),
                                  (0.01, 3.475), (0.0, 3.50)], 2)
    centre.append(geo.lathe("clock_finial", finial_top, SEG_S, br, matrix=_up(0, -0.43)))
    tower = geo.catmull_rom([(0.068, 2.70), (0.068, 2.78), (0.055, 2.795), (0.04, 2.81), (0.04, 2.97),
                             (0.052, 2.98), (0.062, 2.995), (0.062, 3.115), (0.045, 3.13), (0.03, 3.14),
                             (0.04, 3.165), (0.03, 3.19), (0.012, 3.21), (0.0, 3.235)], 2)
    left.append(geo.lathe("clock_tower.L", tower, SEG_S, br, matrix=_up(0.40, -0.52)))
    left.append(geo.torus("clock_tower_eye.L", (0.40, -0.585, 3.055), (0, -1, 0), 0.04, 0.012, br, SEG_S, 8))
    left.append(geo.lathe("clock_tower_lens.L", [(0.03, 0.0), (0.02, 0.008), (0.0, 0.012)], SEG_S, dark,
                          matrix=geo.axis_matrix((0.40, -0.58, 3.055), (0, -1, 0))))
    left.append(geo.ellipsoid("clock_tower_knob.L", (0.40, -0.575, 2.90), (0.035, 0.03, 0.035), br, 16, 8))

    for ob in left + centre:
        geo.shade(ob)
    for ob in list(left):
        geo.mirror_x(ob, ob.name[:-2] + ".R")
    return centre, left
