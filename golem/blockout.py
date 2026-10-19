"""Step 2: blockout — rough volumes that match the sheet's silhouettes.

Positions are read off the metric grids (tools/ref_grid.py) and corrected with
the per-height extents from tools/profile_diff.py.  Only the left side (+X) is
built; the right side is a mirror copy.  Part names stay the same in later
steps, which replace each volume with the detailed part.
"""
import math

from mathutils import Euler, Vector

from . import geo

CASE_Y = -0.60          # centre depth of the front frame
GLASS_Y = -0.55         # hourglass axis depth
CASE_HALF_W = 0.80      # outer half width of cornice and base
PILLAR_X = 0.58
HOURGLASS_Z = (1.25, 2.52)


def build(mats):
    st, br, rk, rkd = mats["stone"], mats["brass"], mats["rock"], mats["rock_dark"]
    left = []   # parts to mirror
    centre = []

    # --- Front case ------------------------------------------------------
    centre.append(geo.box("case_base", (0, CASE_Y + 0.05, 1.12), (1.5, 0.56, 0.26), br))
    centre.append(geo.box("case_cornice", (0, CASE_Y, 2.57), (2 * CASE_HALF_W, 0.62, 0.18), br))
    centre.append(geo.box("case_arch", (0, CASE_Y + 0.02, 2.70), (0.95, 0.4, 0.10), br))
    left.append(geo.cylinder("case_pillar.L", (PILLAR_X, CASE_Y - 0.04, 1.25), (PILLAR_X, CASE_Y - 0.04, 2.48), 0.08, br, 12))
    left.append(geo.box("case_capital.L", (PILLAR_X + 0.05, CASE_Y - 0.04, 2.25), (0.26, 0.2, 0.24), br))
    left.append(geo.box("case_pedestal.L", (PILLAR_X, CASE_Y - 0.04, 0.92), (0.2, 0.2, 0.14), br))
    left.append(geo.cylinder("case_finial_low.L", (PILLAR_X, CASE_Y - 0.04, 0.85), (PILLAR_X, CASE_Y - 0.04, 0.48), 0.06, br, 8, radius_b=0.0))
    centre.append(geo.cylinder("case_pendant", (0, CASE_Y, 0.99), (0, CASE_Y, 0.60), 0.07, br, 8, radius_b=0.0))
    centre.append(geo.box("case_backplate", (0, CASE_Y + 0.3, 1.88), (1.1, 0.06, 1.3), br))

    # Hourglass: glass bulbs revolved around Z.
    z0, z1 = HOURGLASS_Z
    prof = [(0.0, z0), (0.22, z0 + 0.02), (0.33, 1.52), (0.30, 1.72), (0.06, 1.86), (0.03, 1.89),
            (0.06, 1.92), (0.30, 2.06), (0.33, 2.22), (0.22, z1 - 0.02), (0.0, z1)]
    centre.append(geo.lathe("hourglass_glass", prof, 24, mats["glass"],
                            matrix=geo.axis_matrix((0, GLASS_Y, 0), (0, 0, 1))))

    # Clock hood above the cornice, dome roof and finial.
    centre.append(geo.box("clock_hood", (0, -0.36, 2.95), (0.66, 0.50, 0.55), br))
    centre.append(geo.cylinder("clock_face", (0, -0.60, 2.98), (0, -0.62, 2.98), 0.29, mats["clock_face"], 32))
    centre.append(geo.cylinder("clock_bezel", (0, -0.58, 2.98), (0, -0.61, 2.98), 0.32, br, 32))
    centre.append(geo.ellipsoid("clock_dome", (0, -0.3, 3.2), (0.34, 0.26, 0.14), br, 16, 8))
    centre.append(geo.lathe("clock_finial", [(0.06, 3.27), (0.12, 3.33), (0.05, 3.38), (0.05, 3.43), (0.0, 3.5)],
                            8, br, matrix=geo.axis_matrix((0, -0.23, 0), (0, 0, 1))))
    left.append(geo.cylinder("clock_tower.L", (0.42, -0.52, 2.66), (0.42, -0.52, 3.12), 0.06, br, 8))
    left.append(geo.ellipsoid("cornice_orb.L", (0.6, -0.6, 2.78), (0.08, 0.08, 0.1), br, 10, 6))

    # --- Stone shoulders (one dome behind the clock) -----------------------
    centre.append(geo.ellipsoid("shoulder_mass", (0, 0.05, 2.82), (0.95, 0.5, 0.5), st, 20, 12, squareness=2.4))
    left.append(geo.ellipsoid("shoulder.L", (0.9, 0.1, 2.62), (0.6, 0.53, 0.55), st, 20, 12))
    # dark rock core of the torso
    centre.append(geo.ellipsoid("torso_core", (0, 0.0, 1.75), (0.75, 0.5, 0.8), rk, 16, 10))
    centre.append(geo.ellipsoid("pelvis", (0, 0.0, 0.98), (0.62, 0.3, 0.22), rk, 16, 8))

    # --- Back mechanism ----------------------------------------------------
    centre.append(geo.cylinder("back_wheel", (0, 0.55, 2.72), (0, 0.64, 2.72), 0.42, br, 32))
    centre.append(geo.box("back_frame", (0, 0.40, 1.75), (1.3, 0.12, 1.0), br))

    # --- Arms ------------------------------------------------------------
    left.append(geo.cylinder("upperarm.L", (1.0, 0.08, 2.35), (1.25, 0.08, 1.9), 0.25, rk, 12, radius_b=0.27))
    left.append(geo.ellipsoid("gauntlet.L", (1.37, 0.07, 1.74), (0.42, 0.38, 0.5), st, 16, 10, squareness=2.6))
    tilt = Euler((0, math.radians(90), math.radians(-35)))
    left.append(geo.lathe("gear_big.L", [(0.0, -0.04), (0.27, -0.04), (0.27, 0.04), (0.0, 0.04)], 24, br,
                          matrix=geo.axis_matrix((1.70, -0.08, 1.68), tilt.to_matrix() @ Vector((0, 0, 1)))))
    left.append(geo.lathe("gear_small.L", [(0.0, -0.03), (0.1, -0.03), (0.1, 0.03), (0.0, 0.03)], 16, br,
                          matrix=geo.axis_matrix((1.12, -0.30, 1.86), (0, -1, 0))))
    left.append(geo.ellipsoid("hand.L", (1.27, 0.1, 1.03), (0.33, 0.27, 0.28), rkd, 12, 8, squareness=2.4))
    # three hanging weights under each hand: (x, top z, bottom z)
    for i, (x, zt, zb) in enumerate(((1.03, 0.85, 0.50), (1.25, 0.85, 0.13), (1.43, 0.85, 0.50))):
        left.append(geo.lathe(f"weight_{i}.L", [(0.0, zb), (0.06, zb + 0.12), (0.03, zb + 0.18), (0.015, zt)],
                              8, br, matrix=geo.axis_matrix((x, 0.18, 0), (0, 0, 1))))

    # --- Legs ------------------------------------------------------------
    left.append(geo.cylinder("leg.L", (0.44, -0.08, 0.1), (0.44, 0.0, 0.95), 0.16, rk, 12, radius_b=0.22))
    left.append(geo.ellipsoid("foot.L", (0.6, -0.13, 0.06), (0.39, 0.44, 0.1), rkd, 16, 8))

    for ob in list(left):
        geo.mirror_x(ob, ob.name[:-2] + ".R")
    return centre, left
