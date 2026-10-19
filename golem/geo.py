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
    me = ob.data.copy()
    me.name = name
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.transform(Matrix.Diagonal((-1, 1, 1, 1)))
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
