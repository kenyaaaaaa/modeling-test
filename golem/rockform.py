"""Solid rock forms with a broken, faceted surface (replaces stacked pieces).

The sheet draws the body as one trunk-like mass of rock whose surface is
split into irregular facets — some jut out to a point, some are chipped in —
with crack lines on part of the borders.  The white stone is a thick crust on
top of that rock, cracked the same way and torn away in irregular patches.

    faceted(ob, ...)   reshape a smooth carrier mesh in place
    crust(...)         thick shell with torn holes, from a carrier
"""
import math
import random

import bmesh
import bpy
from mathutils import Matrix, Vector, kdtree, noise
from mathutils.bvhtree import BVHTree

from . import geo, stone


def _variable_seeds(bm, rng, size_range):
    """Seed points on the surface with random spacing (cells of mixed sizes)."""
    verts = list(bm.verts)
    order = list(range(len(verts)))
    rng.shuffle(order)
    seeds, sizes = [], []
    tree = None
    pending = []
    for idx in order:
        p = verts[idx].co
        want = rng.uniform(*size_range)
        if tree is not None:
            _, j, d = tree.find(p)
            if d < (want + sizes[j]) * 0.5:
                continue
        for q, _ in pending:
            if (q - p).length < want * 0.5:
                break
        else:
            seeds.append(p.copy())
            sizes.append(want)
            pending.append((p.copy(), want))
            if len(pending) > 64:
                tree = kdtree.KDTree(len(seeds))
                for i, s in enumerate(seeds):
                    tree.insert(s, i)
                tree.balance()
                pending = []
    return seeds, sizes


def faceted(ob, seed, size_range=(0.10, 0.30), relief=0.035, tilt_deg=14, flatten=0.85,
            crack_p=0.55, crack_w=0.018, crack_d=0.016, crease_w=0.06,
            spike_p=0.12, spike_h=0.07, dent_p=0.12, dent_d=0.035, warp=0.06, warp_freq=4.0, smooth=2,
            ink="cracks"):
    """Break a smooth surface into irregular facets, spikes, dents and cracks.

    ink: which cell borders get a Freestyle edge mark (the sheet's ink lines):
    "cracks", "all" or None.
    """
    rng = random.Random(seed)
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.normal_update()
    seeds, sizes = _variable_seeds(bm, rng, size_range)
    tree = kdtree.KDTree(len(seeds))
    for i, s in enumerate(seeds):
        tree.insert(s, i)
    tree.balance()
    vtree = kdtree.KDTree(len(bm.verts))
    for v in bm.verts:
        vtree.insert(v.co, v.index)
    vtree.balance()
    vn = {v.index: v.normal.copy() for v in bm.verts}
    planes = []
    for s, size in zip(seeds, sizes):
        _, vi, _ = vtree.find(s)
        n = vn[vi]
        axis = n.cross(Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1)))).normalized()
        n = (Matrix.Rotation(math.radians(rng.uniform(0, tilt_deg)), 3, axis) @ n).normalized()
        kind = rng.random()
        h = rng.uniform(-relief * 0.4, relief)
        if kind < spike_p:
            planes.append(("spike", s + vn[vi] * h, n, size, spike_h * rng.uniform(0.6, 1.3)))
        elif kind < spike_p + dent_p:
            planes.append(("dent", s + vn[vi] * (h - dent_d * rng.uniform(0.6, 1.3)), n, size, 0.0))
        else:
            planes.append(("flat", s + vn[vi] * h, n, size, 0.0))
    cracks = {}

    def crack(i, j):
        k = (min(i, j), max(i, j))
        if k not in cracks:
            cracks[k] = rng.random() < crack_p
        return cracks[k]

    def offset(i, v, nv):
        kind, c, n, size, peak = planes[i]
        den = nv.dot(n)
        if abs(den) < 0.2:
            den = 0.2 if den >= 0 else -0.2
        t = (c - v).dot(n) / den * flatten
        if kind == "spike":
            r = (v - c).length / size
            t += peak * max(0.0, 1.0 - 2.2 * r)
        return max(-0.12, min(0.16, t))

    woff = Vector((rng.uniform(0, 99), rng.uniform(0, 99), rng.uniform(0, 99)))
    disp = {}
    cell = {}
    for v in bm.verts:
        nv = vn[v.index]
        # warp the lookup point so cell borders wander instead of running straight
        q = v.co + Vector((noise.noise(v.co * warp_freq + woff), noise.noise(v.co * warp_freq - woff),
                           noise.noise(v.co * warp_freq + woff * 0.37))) * warp
        (_, i, d1), (_, j, d2) = tree.find_n(q, 2)
        cell[v.index] = i
        e = (d2 - d1) * 0.5
        t = offset(i, v.co, nv)
        if e < crease_w:
            # meet the neighbour facet along a crease instead of a step
            tj = offset(j, v.co, nv)
            w = 0.5 * (1 - e / crease_w)
            t = t * (1 - w) + tj * w
        if e < crack_w and crack(i, j):
            t -= crack_d * (1 - e / crack_w) ** 1.5
        disp[v] = t
    # relax the displacement a little: removes voxel stair-steps along borders
    for _ in range(smooth):
        new = {}
        for v, t in disp.items():
            nb = [disp[e.other_vert(v)] for e in v.link_edges]
            new[v] = 0.5 * t + 0.5 * sum(nb) / len(nb) if nb else t
        disp = new
    for v, t in disp.items():
        v.co += vn[v.index] * t
    bm.to_mesh(ob.data)
    bm.free()
    me = ob.data
    if ink:
        attr = me.attributes.get("freestyle_edge") or me.attributes.new("freestyle_edge", "BOOLEAN", "EDGE")
        # border vertices: which other cells each vertex touches
        others = {}
        for e in me.edges:
            u, w = e.vertices
            if cell[u] != cell[w]:
                others.setdefault(u, set()).add(cell[w])
                others.setdefault(w, set()).add(cell[u])
        marks = [False] * len(me.edges)
        for k, e in enumerate(me.edges):
            u, w = e.vertices
            a = cell[u]
            if cell[w] != a or u not in others or w not in others:
                continue
            # an edge running along the border, drawn from the lower-numbered side only
            for b in others[u] & others[w]:
                if a < b and (ink == "all" or crack(a, b)):
                    marks[k] = True
                    break
        attr.data.foreach_set("value", marks)
    me.update()
    return ob


def solid(name, volumes, material, seed, voxel=0.013, **kw):
    """One continuous rock mass from volumes, with a faceted broken surface."""
    ob = stone.carrier(name, volumes, voxel=voxel, smooth=5)
    ob.data.materials.append(material)
    return faceted(ob, seed, **kw)


def _blob(bm_out, center, normal, size, rng, jag=0.25, min_depth=0.0):
    """Irregular cutter: a squashed sphere with noisy, jagged surface."""
    tmp = bmesh.new()
    bmesh.ops.create_icosphere(tmp, subdivisions=3, radius=1.0)
    off = Vector((rng.uniform(0, 99), rng.uniform(0, 99), rng.uniform(0, 99)))
    for v in tmp.verts:
        d = v.co.normalized()
        r = 1.0 + jag * noise.noise(d * 1.7 + off) + jag * 0.5 * noise.noise(d * 5.0 + off * 1.3)
        v.co = d * max(0.35, r)
    sx, sy, sz = rng.uniform(0.7, 1.3), rng.uniform(0.7, 1.3), rng.uniform(0.9, 1.4)
    rot = Vector((0, 0, 1)).rotation_difference(normal).to_matrix().to_4x4()
    spin = Matrix.Rotation(rng.uniform(0, 6.28), 4, "Z")
    depth = max(size * 0.6 * sz, min_depth)
    tmp.transform(Matrix.Translation(center) @ rot @ spin @ Matrix.Diagonal((size * sx, size * sy, depth, 1)))
    me = bpy.data.meshes.new("blob")
    tmp.to_mesh(me)
    tmp.free()
    bm_out.from_mesh(me)
    bpy.data.meshes.remove(me)


def crust(name, volumes, material, rock_material, seed, voxel=0.011, thickness=0.085, holes=18,
          hole_size=(0.13, 0.32), keep=None, extra_cuts=(), **kw):
    """White crust over rock, faceted and cracked, torn open in patches.

    The faceted solid is cut with irregular blobs (Boolean).  Cut faces get
    the rock material where they lie deeper than the crust thickness (the
    rock showing through) and stay white nearer the surface (the crust's
    broken edge).  The hole floors are roughened.
    """
    rng = random.Random(seed * 7 + 3)
    outer = stone.carrier(name, volumes, voxel=voxel, smooth=6)
    outer.data.materials.append(material)
    outer.data.materials.append(rock_material)
    faceted(outer, seed, size_range=(0.25, 0.7), relief=0.016, tilt_deg=6, flatten=0.85, crack_p=0.6,
            crack_w=0.016, crack_d=0.035, crease_w=0.12, spike_p=0.0, dent_p=0.06, dent_d=0.02, warp=0.08,
            smooth=1, **kw)
    surface = BVHTree.FromObject(outer, bpy.context.evaluated_depsgraph_get())
    pts = [v.co.copy() for v in outer.data.vertices]
    nrm = [v.normal.copy() for v in outer.data.vertices]
    cut = bmesh.new()
    placed = []
    tries = 0
    while len(placed) < holes and tries < 4000:
        tries += 1
        i = rng.randrange(len(pts))
        p = pts[i]
        if keep is not None and not keep(p):
            continue
        size = rng.uniform(*hole_size)
        if any((p - q).length < (size + r) * 0.9 for q, r in placed):
            continue
        placed.append((p, size))
        _blob(cut, p, nrm[i], size, rng, jag=0.16, min_depth=thickness * 1.8)
    for c, r in extra_cuts:   # fixed openings, e.g. where the back wheel sits
        tmp = bmesh.new()
        bmesh.ops.create_icosphere(tmp, subdivisions=3, radius=1.0)
        off = Vector((rng.uniform(0, 99), rng.uniform(0, 99), rng.uniform(0, 99)))
        for v in tmp.verts:
            d = v.co.normalized()
            v.co = d * (1.0 + 0.12 * noise.noise(d * 3.0 + off))
        tmp.transform(Matrix.Translation(c) @ Matrix.Diagonal((*r, 1.0)))
        me = bpy.data.meshes.new("cut_tmp")
        tmp.to_mesh(me)
        tmp.free()
        cut.from_mesh(me)
        bpy.data.meshes.remove(me)
        placed.append((Vector(c), max(r)))
    if not placed:
        cut.free()
        return outer
    cme = bpy.data.meshes.new(name + "_cut")
    cut.to_mesh(cme)
    cut.free()
    cme.materials.append(rock_material)
    cutter = bpy.data.objects.new(name + "_cut", cme)
    bpy.context.scene.collection.objects.link(cutter)
    mod = outer.modifiers.new("holes", "BOOLEAN")
    mod.operation = "DIFFERENCE"
    mod.solver = "EXACT"
    mod.use_self = True  # the blobs overlap each other
    mod.object = cutter
    dg = bpy.context.evaluated_depsgraph_get()
    new = bpy.data.meshes.new_from_object(outer.evaluated_get(dg))
    outer.modifiers.clear()
    old = outer.data
    outer.data = new
    bpy.data.meshes.remove(old)
    bpy.data.objects.remove(cutter, do_unlink=True)
    # material by depth, and roughen the rock floors
    me = outer.data
    rock_idx = [i for i, m in enumerate(me.materials) if m == rock_material][0]
    white_idx = [i for i, m in enumerate(me.materials) if m == material][0]
    off = Vector((seed * 1.3, seed * 2.1, seed * 0.7))
    floor_verts = set()
    for poly in me.polygons:
        if poly.material_index != rock_idx:
            continue
        c = poly.center
        loc, _, _, dist = surface.find_nearest(c)
        if dist is not None and dist < thickness:
            poly.material_index = white_idx
        else:
            floor_verts.update(poly.vertices)
    for vi in floor_verts:
        v = me.vertices[vi]
        b = 1.0 - abs(noise.noise(v.co * 9 + off))
        v.co += v.normal * (0.03 * b * b - 0.01)
    me.update()
    return outer


def bark_flap(name, center, radius, a0, a1, z_top, length, peel, material, seed, thickness=0.04, curl=0.05,
              drip=False):
    """One weathered brown flap of the wrist cuff: hugs the wrist at the top,
    peels outwards, flares, and rolls into a lip at a ragged bottom edge."""
    rng = random.Random(seed)
    cx, cy = center
    cols, rows = 16, 14
    off = rng.uniform(0, 50)
    bm = bmesh.new()
    grid = []
    for r in range(rows + 1):
        t = r / rows
        row = []
        for c in range(cols + 1):
            u = c / cols
            a = a0 + (a1 - a0) * u
            edge = 1.0 - 0.22 * (0.5 + 0.5 * noise.noise(Vector((u * 3 + off, 0, 1))))
            side = math.sin(math.pi * u) ** 0.35        # sides shorter than the middle
            tt = t * edge * (0.75 + 0.25 * side)
            z = z_top - length * tt
            rad = radius + peel * tt ** 1.6
            if tt > 0.8:                                  # roll the lip outwards and up
                q = (tt - 0.8) / 0.2
                rad += curl * math.sin(q * math.pi * 0.5)
                z += curl * 0.8 * q * q
            rad += 0.01 * noise.noise(Vector((u * 5 + off, tt * 5, 2)))
            row.append(bm.verts.new((cx + rad * math.cos(a), cy + rad * math.sin(a), z)))
        grid.append(row)
    for r in range(rows):
        for c in range(cols):
            bm.faces.new((grid[r][c], grid[r + 1][c], grid[r + 1][c + 1], grid[r][c + 1]))
    bm.normal_update()
    bmesh.ops.solidify(bm, geom=list(bm.faces), thickness=thickness)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    parts = [geo._link(name, bm, material)]
    if drip:
        am = (a0 + a1) * 0.5 + (a1 - a0) * 0.2
        rb = radius + peel + curl
        x, y, z = cx + rb * math.cos(am), cy + rb * math.sin(am), z_top - length * 0.92
        pts = geo.catmull_rom([(x, y, z), (x, y, z - 0.06), (x + 0.005, y, z - 0.12)], 3)
        rad = [0.022 * (1 - i / (len(pts) - 1)) ** 0.6 + 0.004 for i in range(len(pts))]
        parts.append(geo.tube(name + "_drip", pts, rad, material, 8))
    return parts


def bark_block(name, center, angle, radius, z_top, z_bot, material, seed):
    """Chunky carved block on the inner side of the wrist, with a notch and
    a scroll at its foot (the right-hand wrist piece in the front view)."""
    rng = random.Random(seed)
    cx, cy = center
    d = Vector((math.cos(angle), math.sin(angle), 0))
    side = Vector((-d.y, d.x, 0))
    c = Vector((cx, cy, 0)) + d * (radius + 0.04)
    h = z_top - z_bot
    # profile in the (outward, z) plane, extruded sideways
    prof = [(-0.06, z_top), (0.05, z_top - 0.01), (0.07, z_top - h * 0.3), (0.035, z_top - h * 0.38),
            (0.06, z_top - h * 0.48), (0.09, z_top - h * 0.8), (0.06, z_bot), (-0.04, z_bot + 0.02)]
    bm = bmesh.new()
    w = 0.08 + rng.uniform(0, 0.03)
    loops = [[bm.verts.new(c + d * u + side * s + Vector((0, 0, z))) for u, z in prof] for s in (-w, w)]
    geo._bridge_loops(bm, loops, False, True)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = geo._link(name, bm, material)
    geo.bevel_all(ob, 0.012, 2, 30)
    parts = [ob]
    foot = c + d * 0.07 + Vector((0, 0, z_bot + 0.03))
    sp = geo.spiral((0.0, 0.0), 0.04, 0.012, 1.0, a0=math.pi, n=24)
    pts = [tuple(foot + d * x + Vector((0, 0, z))) for x, z in sp]
    rad = [0.02 * (1 - 0.6 * i / (len(pts) - 1)) for i in range(len(pts))]
    parts.append(geo.tube(name + "_scroll", pts, rad, material, 8))
    return parts


def wrist_pieces(name, center, radius, z_top, material, seed, outward=0.0):
    """The wrist pieces as the front view draws them: a big curling flap on
    the outer side, a carved block on the inner side, shorter flaps between."""
    o = outward
    parts = []
    parts += bark_flap(name + "_outer", center, radius, o - 0.6, o + 0.6, z_top, 0.32, 0.1, material, seed,
                       curl=0.06, drip=True)
    parts += bark_flap(name + "_rear", center, radius, o + 1.7, o + 2.3, z_top - 0.04, 0.2, 0.05, material,
                       seed + 2, curl=0.03)
    # the block sits front-inner: mirror of the outer flap across the arm's front axis
    parts += bark_block(name + "_block", center, math.pi - o, radius, z_top - 0.02, z_top - 0.3, material, seed + 3)
    return parts


def fluted_drum(name, center, z_top, z_bot, r_top, r_bot, material, flutes=12, segs=96, rings=8):
    """Round fluted piece (the brown pedestal the lantern hangs from)."""
    cx, cy = center
    bm = bmesh.new()
    loops = []
    for i in range(rings + 1):
        t = i / rings
        z = z_top + (z_bot - z_top) * t
        r0 = r_top + (r_bot - r_top) * t
        ring = []
        for k in range(segs):
            a = 2 * math.pi * k / segs
            r = r0 * (1 - 0.07 * max(0.0, math.cos(flutes * a)) ** 2)
            ring.append(bm.verts.new((cx + r * math.cos(a), cy + r * math.sin(a), z)))
        loops.append(ring)
    geo._bridge_loops(bm, loops, False, True)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return geo._link(name, bm, material)


def remove_objects(obs):
    for ob in obs:
        bpy.data.objects.remove(ob, do_unlink=True)
