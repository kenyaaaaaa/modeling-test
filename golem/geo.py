"""Mesh helpers built on bmesh.  Units are metres, Z up, the character faces -Y."""
import math

import bmesh
import bpy
from mathutils import Matrix, Vector


def _link(name, bm, material=None, collection=None):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    (collection or bpy.context.scene.collection).objects.link(ob)
    if material is not None:
        me.materials.append(material)
    return ob


def lathe(name, profile, segments=24, material=None, matrix=None, cap=True):
    """Revolve a profile of (radius, z) points around the local Z axis.

    The profile runs bottom to top.  Points with radius 0 become poles.
    """
    bm = bmesh.new()
    rings = []
    for r, z in profile:
        if r <= 1e-6:
            rings.append([bm.verts.new((0.0, 0.0, z))])
            continue
        ring = []
        for i in range(segments):
            a = 2 * math.pi * i / segments
            ring.append(bm.verts.new((r * math.cos(a), r * math.sin(a), z)))
        rings.append(ring)
    for lo, hi in zip(rings, rings[1:]):
        if len(lo) == 1 and len(hi) == 1:
            continue
        if len(lo) == 1:
            for i in range(segments):
                bm.faces.new((lo[0], hi[i], hi[(i + 1) % segments]))
        elif len(hi) == 1:
            for i in range(segments):
                bm.faces.new((lo[i], hi[0], lo[(i + 1) % segments]))
        else:
            for i in range(segments):
                j = (i + 1) % segments
                bm.faces.new((lo[i], lo[j], hi[j], hi[i]))
    if cap:
        if len(rings[0]) > 1:
            bm.faces.new(list(reversed(rings[0])))
        if len(rings[-1]) > 1:
            bm.faces.new(rings[-1])
    if matrix is not None:
        bm.transform(matrix)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return _link(name, bm, material)


def box(name, center, size, material=None, bevel=0.0):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bm.transform(Matrix.Translation(center) @ Matrix.Diagonal((*size, 1.0)))
    if bevel > 0:
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=bevel, segments=1, affect="EDGES")
    return _link(name, bm, material)


def ellipsoid(name, center, radii, material=None, segments=16, rings=10, rotation=None, squareness=2.0):
    """Ellipsoid; squareness > 2 pushes it towards a rounded box (superellipsoid)."""
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segments, v_segments=rings, radius=1.0)
    if squareness != 2.0:
        p = squareness
        for v in bm.verts:
            n = (abs(v.co.x) ** p + abs(v.co.y) ** p + abs(v.co.z) ** p) ** (1 / p)
            v.co /= n
    m = Matrix.Diagonal((*radii, 1.0))
    if rotation is not None:
        m = rotation.to_matrix().to_4x4() @ m
    bm.transform(Matrix.Translation(center) @ m)
    return _link(name, bm, material)


def cylinder(name, a, b, radius, material=None, segments=16, radius_b=None):
    """Cylinder (or cone) from point a to point b."""
    a, b = Vector(a), Vector(b)
    d = b - a
    rot = Vector((0, 0, 1)).rotation_difference(d.normalized()).to_matrix().to_4x4()
    m = Matrix.Translation(a) @ rot
    rb = radius if radius_b is None else radius_b
    return lathe(name, [(radius, 0.0), (rb, d.length)], segments, material, matrix=m)


def axis_matrix(origin, axis):
    """Matrix that maps local +Z onto `axis` at `origin`."""
    rot = Vector((0, 0, 1)).rotation_difference(Vector(axis).normalized())
    return Matrix.Translation(origin) @ rot.to_matrix().to_4x4()


def mirror_x(ob, name):
    """Copy an object mirrored across X=0 (for .L -> .R parts)."""
    bpy.context.view_layer.update()  # matrix_world of freshly placed objects
    me = ob.data.copy()
    me.name = name
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.transform(Matrix.Diagonal((-1, 1, 1, 1)) @ ob.matrix_world)
    bmesh.ops.reverse_faces(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    new = bpy.data.objects.new(name, me)
    for c in ob.users_collection:
        c.objects.link(new)
    return new


def triangle_count(objects):
    n = 0
    for ob in objects:
        if ob.type != "MESH":
            continue
        dg = bpy.context.evaluated_depsgraph_get()
        me = ob.evaluated_get(dg).to_mesh()
        n += sum(len(p.vertices) - 2 for p in me.polygons)
        ob.evaluated_get(dg).to_mesh_clear()
    return n


def square_lathe(name, profile, center=(0.0, 0.0), aspect=(1.0, 1.0), material=None):
    """Stack of square rings: profile is (half_width, z) bottom to top.

    Used for mouldings, plinths and capitals.  `aspect` stretches X/Y.
    """
    s2 = math.sqrt(2.0)
    m = (Matrix.Translation((center[0], center[1], 0.0))
         @ Matrix.Diagonal((aspect[0], aspect[1], 1.0, 1.0))
         @ Matrix.Rotation(math.pi / 4, 4, "Z"))
    prof = [(hw * s2, z) for hw, z in profile]
    return lathe(name, prof, 4, material, matrix=m)


def _bridge_loops(bm, loops, closed, cap):
    n = len(loops[0])
    for lo, hi in zip(loops, loops[1:] + ([loops[0]] if closed else [])):
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((lo[i], lo[j], hi[j], hi[i]))
    if cap and not closed:
        bm.faces.new(list(reversed(loops[0])))
        bm.faces.new(loops[-1])


def prism(name, poly, z0, z1, center=(0.0, 0.0, 0.0), material=None, top_scale=1.0):
    """Extrude a closed 2D polygon (XY) from z0 to z1 (optionally tapered)."""
    bm = bmesh.new()
    cx, cy, cz = center
    loops = [[bm.verts.new((cx + x * k, cy + y * k, cz + z)) for x, y in poly] for z, k in ((z0, 1.0), (z1, top_scale))]
    _bridge_loops(bm, loops, False, True)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return _link(name, bm, material)


def extrude_xz(name, poly, y0, y1, material=None):
    """Front-view shape: closed polygon of (x, z) extruded along Y."""
    bm = bmesh.new()
    loops = [[bm.verts.new((x, y, z)) for x, z in poly] for y in (y0, y1)]
    _bridge_loops(bm, loops, False, True)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return _link(name, bm, material)


def sweep_xz(name, path, width, depth, y_center, material=None, closed=True):
    """Band of rectangular section following a path of (x, z) points.

    The band is `width` wide in the XZ plane (outwards from the path) and
    `depth` deep along Y.  Used for frames that hug an outline.
    """
    bm = bmesh.new()
    n = len(path)
    loops = []
    for i, (x, z) in enumerate(path):
        p0 = Vector(path[(i - 1) % n] if closed or i > 0 else path[i])
        p1 = Vector(path[(i + 1) % n] if closed or i < n - 1 else path[i])
        t = (p1 - p0).normalized()
        nrm = Vector((t.y, -t.x))  # outward for a counter-clockwise path
        a = Vector((x, z)) - nrm * width / 2
        b = Vector((x, z)) + nrm * width / 2
        y0, y1 = y_center - depth / 2, y_center + depth / 2
        loops.append([bm.verts.new((a.x, y0, a.y)), bm.verts.new((b.x, y0, b.y)),
                      bm.verts.new((b.x, y1, b.y)), bm.verts.new((a.x, y1, a.y))])
    # bridge consecutive rectangles
    for k in range(n if closed else n - 1):
        lo, hi = loops[k], loops[(k + 1) % n]
        for i in range(4):
            j = (i + 1) % 4
            bm.faces.new((lo[i], lo[j], hi[j], hi[i]))
    if not closed:
        bm.faces.new(list(reversed(loops[0])))
        bm.faces.new(loops[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return _link(name, bm, material)


def torus(name, origin, axis, radius, minor, material=None, segments=32, minor_segments=8):
    prof = [(radius + minor * math.cos(a), minor * math.sin(a))
            for a in (2 * math.pi * i / minor_segments for i in range(minor_segments))]
    bm = bmesh.new()
    rings = []
    for r, z in prof:
        rings.append([bm.verts.new((r * math.cos(2 * math.pi * i / segments),
                                    r * math.sin(2 * math.pi * i / segments), z)) for i in range(segments)])
    _bridge_loops(bm, rings, True, False)
    bm.transform(axis_matrix(origin, axis))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return _link(name, bm, material)


def bevel_edges(ob, offset, segments=1, angle_deg=30):
    """Bevel the sharp edges of a mesh (catches highlights in toon shading)."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    edges = [e for e in bm.edges if e.calc_face_angle(0) > math.radians(angle_deg)]
    bmesh.ops.bevel(bm, geom=edges, offset=offset, segments=segments, affect="EDGES", clamp_overlap=True)
    bm.to_mesh(ob.data)
    bm.free()
    return ob


def shade(ob, angle_deg=35):
    """Smooth shading with sharp edges above the angle."""
    me = ob.data
    for p in me.polygons:
        p.use_smooth = True
    me.set_sharp_from_angle(angle=math.radians(angle_deg))
    return ob


def remove(names):
    for n in names:
        ob = bpy.data.objects.get(n)
        if ob is not None:
            bpy.data.objects.remove(ob, do_unlink=True)


# --- detail helpers ---------------------------------------------------------

def catmull_rom(points, samples=6, closed=False):
    """Smooth a polyline of 2D/3D tuples through its points."""
    pts = [Vector(p) for p in points]
    n = len(pts)
    out = []
    last = n if closed else n - 1
    for i in range(last):
        p0 = pts[(i - 1) % n] if (closed or i > 0) else pts[i]
        p1, p2 = pts[i], pts[(i + 1) % n]
        p3 = pts[(i + 2) % n] if (closed or i + 2 < n) else pts[(i + 1) % n]
        for s in range(samples):
            t = s / samples
            t2, t3 = t * t, t * t * t
            v = 0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3)
            out.append(tuple(v))
    if not closed:
        out.append(tuple(pts[-1]))
    return out


def rounded_rect(hx, hy, r, segs=3):
    """Counter-clockwise rounded rectangle (XY) centred on the origin."""
    r = min(r, 0.45 * min(hx, hy))
    pts = []
    for cx, cy, a0 in ((hx - r, -hy + r, -90), (hx - r, hy - r, 0), (-hx + r, hy - r, 90), (-hx + r, -hy + r, 180)):
        for k in range(segs + 1):
            a = math.radians(a0 + 90 * k / segs)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def ring_lathe(name, profile, center=(0.0, 0.0), aspect=(1.0, 1.0), corner=0.012, corner_segs=3, material=None):
    """Stack of rounded-rectangle rings; profile is (half_width, z) bottom to top.

    Mouldings, plinths and capitals with softened corners.
    """
    bm = bmesh.new()
    loops = []
    for hw, z in profile:
        ring = rounded_rect(hw * aspect[0], hw * aspect[1], corner, corner_segs)
        loops.append([bm.verts.new((center[0] + x, center[1] + y, z)) for x, y in ring])
    _bridge_loops(bm, loops, False, True)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return _link(name, bm, material)


def ellipse_section(u, v, segs=10):
    return [(u * math.cos(2 * math.pi * i / segs), v * math.sin(2 * math.pi * i / segs)) for i in range(segs)]


def sweep_section_xz(name, path, section, y_center, material=None, closed=False):
    """Sweep a 2D section along a path of (x, z) points in the plane y = y_center.

    Section points are (u, v): u along the in-plane normal (outwards for a
    counter-clockwise path), v along +Y.
    """
    bm = bmesh.new()
    n = len(path)
    loops = []
    for i, (x, z) in enumerate(path):
        prev = path[(i - 1) % n] if (closed or i > 0) else path[i]
        nxt = path[(i + 1) % n] if (closed or i < n - 1) else path[i]
        tx, tz = nxt[0] - prev[0], nxt[1] - prev[1]
        ln = math.hypot(tx, tz) or 1.0
        nx, nz = tz / ln, -tx / ln
        loops.append([bm.verts.new((x + nx * u, y_center + v, z + nz * u)) for u, v in section])
    _bridge_loops(bm, loops, closed, not closed)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return _link(name, bm, material)


def bevel_all(ob, offset, segments=2, angle_deg=40):
    return bevel_edges(ob, offset, segments, angle_deg)


def displace(ob, fn):
    """Move each vertex: fn(Vector) -> Vector."""
    for v in ob.data.vertices:
        v.co = fn(v.co.copy())
    ob.data.update()
    return ob
