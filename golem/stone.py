"""Step 4: cracked stone plates over a dark rock core (shoulders and gauntlets).

Method: the blockout volumes are unioned into one smooth carrier surface
(voxel remesh).  The surface is split into Voronoi cells; each cell becomes
a plate — flattened towards its own plane for the faceted look, thickened,
softly bevelled and slightly tilted.  Some cells are left out so the rock
underneath shows.  The rock core is the carrier pushed inwards and covered
with lumpy cobbles.  Everything is driven by one random seed.
"""
import math
import random

import bmesh
import bpy
from mathutils import Matrix, Vector, kdtree, noise

from . import geo


def _ellipsoid_bm(bm, center, radii, squareness=2.0, segs=32, rings=20):
    tmp = bmesh.new()
    bmesh.ops.create_uvsphere(tmp, u_segments=segs, v_segments=rings, radius=1.0)
    if squareness != 2.0:
        for v in tmp.verts:
            n = sum(abs(c) ** squareness for c in v.co) ** (1 / squareness)
            v.co /= n
    tmp.transform(Matrix.Translation(center) @ Matrix.Diagonal((*radii, 1.0)))
    me = bpy.data.meshes.new("tmp")
    tmp.to_mesh(me)
    tmp.free()
    bm.from_mesh(me)
    bpy.data.meshes.remove(me)


def carrier(name, volumes, voxel=0.024, smooth=6):
    """Union of ellipsoids (center, radii, squareness) as one smooth surface."""
    bm = bmesh.new()
    for c, r, sq in volumes:
        _ellipsoid_bm(bm, c, r, sq)
    me = bpy.data.meshes.new(name + "_raw")
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    rm = ob.modifiers.new("remesh", "REMESH")
    rm.mode = "VOXEL"
    rm.voxel_size = voxel
    sm = ob.modifiers.new("smooth", "SMOOTH")
    sm.iterations = smooth
    sm.factor = 0.5
    dg = bpy.context.evaluated_depsgraph_get()
    new = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    ob.modifiers.clear()
    bm = bmesh.new()
    bm.from_mesh(new)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)  # outwards
    bm.to_mesh(new)
    bm.free()
    ob.data = new
    bpy.data.meshes.remove(me)
    return ob


def _seeds(bm, cell, rng, keep=None):
    """Roughly even seed points on the surface (dart throwing + 2 Lloyd steps)."""
    faces = [f for f in bm.faces if keep is None or keep(f.calc_center_median())]
    centers = [f.calc_center_median() for f in faces]
    area = sum(f.calc_area() for f in faces)
    n = max(4, int(area / (cell * cell * 0.85)))
    order = list(range(len(faces)))
    rng.shuffle(order)
    seeds = []
    tree = kdtree.KDTree(n * 4 + 1)
    for i in order:
        c = centers[i]
        if seeds:
            tree.balance()
            _, _, d = tree.find(c)
            if d < cell * rng.uniform(0.6, 1.05):
                continue
        seeds.append(c.copy())
        tree.insert(c, len(seeds) - 1)
        if len(seeds) >= n:
            break
    for _ in range(2):
        t = kdtree.KDTree(len(seeds))
        for i, s in enumerate(seeds):
            t.insert(s, i)
        t.balance()
        acc = [[Vector(), 0] for _ in seeds]
        for c in centers:
            _, i, _ = t.find(c)
            acc[i][0] += c
            acc[i][1] += 1
        moved = [a / k if k else s for (a, k), s in zip(acc, seeds)]
        # snap back onto the surface
        ft = kdtree.KDTree(len(centers))
        for i, c in enumerate(centers):
            ft.insert(c, i)
        ft.balance()
        seeds = [ft.find(m)[0].copy() for m in moved]
    return seeds


def plates(name, carrier_ob, material, seed, cell=0.38, gap=0.010, missing=0.27, thickness=(0.11, 0.16),
           flatten=0.8, keep=None, bevel=0.025, centers=None):
    """Split the carrier into thick faceted plates.  Returns (plate object, labels of missing cells)."""
    rng = random.Random(seed)
    src = bmesh.new()
    src.from_mesh(carrier_ob.data)
    src.faces.ensure_lookup_table()
    seeds = _seeds(src, cell, rng, keep)
    tree = kdtree.KDTree(len(seeds))
    for i, s in enumerate(seeds):
        tree.insert(s, i)
    tree.balance()
    gone = {i for i in range(len(seeds)) if rng.random() < missing}
    cells = {}
    for f in src.faces:
        c = f.calc_center_median()
        if keep is not None and not keep(c):
            continue
        near = tree.find_n(c, 2)
        (_, i, d1), (_, _, d2) = near[0], near[1]
        if (d2 - d1) * 0.5 < gap * 0.5 or i in gone:
            continue
        cells.setdefault(i, []).append(f)

    out = bmesh.new()
    for i, faces in cells.items():
        if len(faces) < 6:
            continue
        pb = bmesh.new()
        vmap = {}
        for f in faces:
            vs = []
            for v in f.verts:
                if v.index not in vmap:
                    vmap[v.index] = pb.verts.new(v.co)
                vs.append(vmap[v.index])
            try:
                pb.faces.new(vs)
            except ValueError:
                pass
        _shape_plate(pb, rng, thickness, flatten, bevel, centers)
        me = bpy.data.meshes.new("plate_tmp")
        pb.to_mesh(me)
        pb.free()
        out.from_mesh(me)
        bpy.data.meshes.remove(me)
    src.free()
    ob = geo._link(name, out, material)
    return ob, seeds, gone


def _shape_plate(pb, rng, thickness, flatten, bevel, centers=None):
    # drop slivers: keep the largest connected island
    pb.verts.ensure_lookup_table()
    boundary = lambda: [v for v in pb.verts if any(e.is_boundary for e in v.link_edges)]  # noqa: E731
    # smooth the jagged Voronoi outline
    for _ in range(2):
        bnd = boundary()
        new = {}
        for v in bnd:
            nb = [e.other_vert(v) for e in v.link_edges if e.is_boundary]
            if len(nb) == 2:
                new[v] = v.co * 0.4 + (nb[0].co + nb[1].co) * 0.3
        for v, co in new.items():
            v.co = co
    pb.normal_update()
    centre = sum((v.co for v in pb.verts), Vector()) / len(pb.verts)
    normal = sum((f.normal * f.calc_area() for f in pb.faces), Vector())
    if normal.length < 1e-6:
        return
    normal.normalize()
    if centers:
        inner = min(centers, key=lambda c: (Vector(c) - centre).length)
        if normal.dot(centre - Vector(inner)) < 0:
            normal = -normal
    # flatten onto the plane through the outermost point, so the plate stands proud
    radius = max((v.co - centre).length for v in pb.verts)
    top_d = max((v.co - centre).dot(normal) for v in pb.verts)
    for v in pb.verts:
        d = (v.co - centre).dot(normal)
        r = (v.co - centre).length / radius
        v.co += normal * ((top_d - d) * flatten)
        v.co += normal * 0.012 * (1 - r * r)
    # random tilt and lift so neighbours do not line up
    axis = normal.cross(Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1)))).normalized()
    rot = Matrix.Rotation(math.radians(rng.uniform(2, 6)), 4, axis)
    lift = normal * rng.uniform(0.0, 0.04)
    for v in pb.verts:
        v.co = (rot @ (v.co - centre)) + centre + lift
    # thicken inwards
    t = rng.uniform(*thickness)
    top = list(pb.faces)
    res = bmesh.ops.extrude_face_region(pb, geom=top)
    new_verts = [g for g in res["geom"] if isinstance(g, bmesh.types.BMVert)]
    for v in new_verts:
        v.co -= normal * t
    bmesh.ops.recalc_face_normals(pb, faces=pb.faces)
    # soften the top rim
    rim = [e for e in pb.edges if e.calc_face_angle(0) > math.radians(50)]
    if rim:
        bmesh.ops.bevel(pb, geom=rim, offset=bevel, segments=3 if bevel >= 0.03 else 2, affect="EDGES",
                        clamp_overlap=True)
    # chipped surface
    s = rng.uniform(0, 100)
    for v in pb.verts:
        v.co += normal * 0.006 * noise.noise(v.co * 9 + Vector((s, s, s)))


def rock_core(name, volumes, material, seed, inset=0.085, cobble=0.13, height=0.055, voxel=0.022, ratio=1.0):
    """Dark rock under the plates: a coarser carrier covered in rounded cobbles."""
    ob = carrier(name, volumes, voxel=voxel, smooth=4)
    ob.data.materials.append(material)
    rng = random.Random(seed * 31 + 7)
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    seeds = _seeds(bm, cobble, rng)
    tree = kdtree.KDTree(len(seeds))
    for i, p in enumerate(seeds):
        tree.insert(p, i)
    tree.balance()
    bm.normal_update()
    for v in bm.verts:
        (_, _, d1), (_, _, d2) = tree.find_n(v.co, 2)
        edge = min(1.0, (d2 - d1) / (cobble * 0.45))
        h = height * (1 - (1 - edge) ** 2.5) - inset
        v.co += v.normal * h
    bm.to_mesh(ob.data)
    bm.free()
    return decimate(ob, ratio)


def decimate(ob, ratio):
    if ratio >= 1.0:
        return ob
    dec = ob.modifiers.new("dec", "DECIMATE")
    dec.ratio = ratio
    dg = bpy.context.evaluated_depsgraph_get()
    new = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    ob.modifiers.clear()
    old = ob.data
    ob.data = new
    bpy.data.meshes.remove(old)
    return ob


REPLACES = ["shoulder_mass", "shoulder.L", "shoulder.R", "gauntlet.L", "gauntlet.R"]

SHOULDER_VOLUMES = [
    ((0, 0.05, 2.82), (0.95, 0.5, 0.5), 2.4),
    ((0.9, 0.1, 2.62), (0.6, 0.53, 0.55), 2.0),
    ((-0.9, 0.1, 2.62), (0.6, 0.53, 0.55), 2.0),
]


def _shrunk(volumes, d):
    return [(c, tuple(max(0.05, x - d) for x in r), sq) for c, r, sq in volumes]


def build(mats, seed=1):
    geo.remove(REPLACES)
    st, rk = mats["stone"], mats["rock"]
    car = carrier("shoulder_carrier", _shrunk(SHOULDER_VOLUMES, 0.035))
    # no plates where the clock case sits in front
    def keep(c):
        front_case = abs(c.x) < 0.55 and c.y < -0.25 and c.z < 3.2
        back_wheel = abs(c.x) < 0.5 and c.y > 0.25 and 2.22 < c.z < 3.14
        return not (front_case or back_wheel)
    sh, _, _ = plates("shoulder_plates", car, st, seed, keep=keep, centers=[v[0] for v in SHOULDER_VOLUMES])
    # no polygon cap (2026-10-19): plates and rock keep their full density
    core = cobbles("rock_shoulders", _shrunk(SHOULDER_VOLUMES, 0.07), mats, seed + 40)
    bpy.data.objects.remove(car, do_unlink=True)

    parts = [sh, *core]
    for side, sx in (("L", 1), ("R", -1)):
        vol = [((1.37 * sx, 0.07, 1.74), (0.42, 0.38, 0.5), 2.6)]
        g = carrier(f"gauntlet_carrier.{side}", _shrunk(vol, 0.04), voxel=0.02)
        gp, _, _ = plates(f"gauntlet_plates.{side}", g, st, seed + (7 if sx > 0 else 13), cell=0.3, missing=0.2,
                          centers=[vol[0][0]])
        pass
        gr = cobbles(f"rock_gauntlet.{side}", _shrunk(vol, 0.08), mats, seed + 5, cell=0.13)
        bpy.data.objects.remove(g, do_unlink=True)
        parts += [gp, *gr]
    for ob in parts:
        geo.shade(ob, 40)
    return parts


def cobbles(name, volumes, mats, seed, cell=0.15, voxel=0.022, material="rock", core="rock_dark"):
    """Rock mass built like the sheet draws it: stacked rounded stones with
    thin dark cracks, over a darker smooth core that fills the gaps."""
    base, side = (name[:-2], name[-2:]) if name[-2:] in (".L", ".R") else (name, "")
    car = carrier(base + "_carrier" + side, volumes, voxel=voxel)
    centers = [v[0] for v in volumes]
    ob, _, _ = plates(name, car, mats[material], seed, cell=cell, gap=0.012, missing=0.0,
                      thickness=(0.05, 0.09), flatten=0.45, bevel=0.03, centers=centers)
    bpy.data.objects.remove(car, do_unlink=True)
    filler = carrier(base + "_core" + side, _shrunk(volumes, 0.03), voxel=voxel * 1.6, smooth=4)
    filler.data.materials.append(mats[core])
    return [ob, filler]
