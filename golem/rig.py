"""Steps 6-8 for the game mesh: ink lines as vertex colour, one skinned mesh,
an armature and the idle loop.

Every object gets bone weights from its name (rigid parts follow one bone,
the rock trunks blend along the limb), then all objects are joined.
"""
import math

import bpy
from mathutils import Vector

# name, head, tail, parent  (left side; mirrored for .R)
BONES = [
    ("root", (0, 0, 0), (0, 0, 0.3), None),
    ("hips", (0, 0, 0.95), (0, 0, 1.35), "root"),
    ("spine", (0, 0, 1.35), (0, 0, 1.9), "hips"),
    ("chest", (0, 0, 1.9), (0, 0, 2.7), "spine"),
    ("clock_minute", (0, -0.63, 3.04), (0, -0.63, 3.20), "chest"),
    ("clock_hour", (0, -0.62, 3.04), (0, -0.62, 3.15), "chest"),
    ("upperarm.L", (1.0, 0.08, 2.35), (1.33, 0.05, 1.45), "chest"),
    ("forearm.L", (1.33, 0.05, 1.45), (1.28, 0.0, 1.0), "upperarm.L"),
    ("hand.L", (1.28, 0.0, 1.0), (1.28, 0.0, 0.86), "forearm.L"),
    ("lantern.L", (1.27, 0.0, 0.86), (1.27, 0.0, 0.13), "hand.L"),
    ("weight_0.L", (1.03, -0.02, 0.86), (1.03, -0.02, 0.48), "hand.L"),
    ("weight_1.L", (1.50, -0.02, 0.86), (1.50, -0.02, 0.48), "hand.L"),
    ("thigh.L", (0.44, -0.05, 1.0), (0.44, -0.08, 0.55), "hips"),
    ("shin.L", (0.44, -0.08, 0.55), (0.44, -0.1, 0.08), "thigh.L"),
    ("back_pend_0", (-0.22, 0.40, 2.26), (-0.22, 0.40, 1.6), "chest"),
    ("back_pend_1", (0.0, 0.40, 2.26), (0.0, 0.40, 1.35), "chest"),
    ("back_pend_2", (0.22, 0.40, 2.26), (0.22, 0.40, 1.6), "chest"),
]


def _all_bones():
    out = []
    for name, h, t, p in BONES:
        out.append((name, h, t, p))
        if name.endswith(".L"):
            m = lambda v: (-v[0], v[1], v[2])  # noqa: E731
            out.append((name[:-2] + ".R", m(h), m(t), p[:-2] + ".R" if p and p.endswith(".L") else p))
    return out


def _ramp(z, z0, z1):
    """0 below z0, 1 above z1, linear between."""
    return max(0.0, min(1.0, (z - z0) / (z1 - z0)))


def _side(name):
    # mirrored copies end in ".R"; left parts carry ".L" somewhere in the name
    if name.endswith(".R"):
        return ".R"
    return ".L" if ".L" in name else ""


def weights_for(name, co):
    """Bone weights for one vertex of the object called `name` (world co)."""
    s = _side(name)
    z = co.z
    if name.startswith("rock_torso"):
        c = _ramp(z, 1.65, 2.05)
        h = 1 - _ramp(z, 1.05, 1.4)
        return {"chest": c, "hips": h, "spine": max(0.0, 1 - c - h)}
    if name.startswith("rock_arm"):
        ch = _ramp(z, 2.15, 2.4)
        fo = 1 - _ramp(z, 1.3, 1.6)
        return {"chest": ch, f"forearm{s}": fo, f"upperarm{s}": max(0.0, 1 - ch - fo)}
    if name.startswith(("rock_leg", "bell_", "knee_cuff")):
        th = _ramp(z, 0.45, 0.65)
        return {f"thigh{s}": th, f"shin{s}": 1 - th}
    if name.startswith(("gauntlet", "gear_")):
        return {f"upperarm{s}": 1.0}
    if name.startswith(("cuff", "wrist_drum")):
        return {f"hand{s}": 1.0}
    if name.startswith("lantern"):
        return {f"lantern{s}": 1.0}
    if name.startswith("weight_"):
        return {f"weight_{name[7]}{s}": 1.0}
    if name.startswith("clock_hand_minute"):
        return {"clock_minute": 1.0}
    if name.startswith("clock_hand_hour"):
        return {"clock_hour": 1.0}
    if name.startswith(("back_rod", "back_bob", "back_lantern")):
        if name.startswith("back_lantern"):
            return {"back_pend_1": 1.0}
        k = name[len("back_rod"):][0] if name.startswith("back_rod") else name[len("back_bob"):][0]
        return {f"back_pend_{k}": 1.0}
    if name.startswith("drip"):
        return {"chest": 1.0}
    return {"chest": 1.0}


def ink_colours(ob, strength=0.85):
    """Vertex colour: dark on the Freestyle-marked crack/border edges."""
    me = ob.data
    n = len(me.vertices)
    ink = [0.0] * n
    attr = me.attributes.get("freestyle_edge")
    if attr is not None:
        marks = [False] * len(me.edges)
        attr.data.foreach_get("value", marks)
        for e, m in zip(me.edges, marks):
            if m:
                ink[e.vertices[0]] = ink[e.vertices[1]] = 1.0
    col = me.color_attributes.get("Col") or me.color_attributes.new("Col", "FLOAT_COLOR", "POINT")
    flat = []
    for k in ink:
        v = 1.0 - strength * k
        flat += [v, v, v, 1.0]
    col.data.foreach_set("color", flat)
    me.color_attributes.active_color = col


def join_skinned(objects, name="golem"):
    """Give each object its vertex groups, then join them into one mesh."""
    bpy.context.view_layer.update()
    for ob in objects:
        mw = ob.matrix_world
        groups = {}
        for v in ob.data.vertices:
            for bone, w in weights_for(ob.name, mw @ v.co).items():
                if w <= 1e-4:
                    continue
                g = groups.get(bone) or ob.vertex_groups.get(bone) or ob.vertex_groups.new(name=bone)
                groups[bone] = g
                g.add([v.index], w, "REPLACE")
        ink_colours(ob)
    active = objects[0]
    with bpy.context.temp_override(active_object=active, object=active, selected_objects=objects,
                                   selected_editable_objects=objects):
        bpy.ops.object.join()
    active.name = name
    active.data.name = name
    return active


def armature(name="golem_rig"):
    arm = bpy.data.armatures.new(name)
    ob = bpy.data.objects.new(name, arm)
    bpy.context.scene.collection.objects.link(ob)
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    for bname, h, t, _ in _all_bones():
        b = arm.edit_bones.new(bname)
        b.head, b.tail = Vector(h), Vector(t)
    for bname, _, _, parent in _all_bones():
        if parent:
            arm.edit_bones[bname].parent = arm.edit_bones[parent]
    bpy.ops.object.mode_set(mode="OBJECT")
    return ob


def bind(mesh_ob, rig_ob):
    mesh_ob.parent = rig_ob
    mod = mesh_ob.modifiers.new("rig", "ARMATURE")
    mod.object = rig_ob


def idle(rig_ob, seconds=6.0, fps=30):
    """A slow breathing loop: chest rises, arms sway, hangings lag behind,
    the minute hand goes round once."""
    sc = bpy.context.scene
    sc.render.fps = fps
    n = int(seconds * fps)
    sc.frame_start, sc.frame_end = 0, n
    pb = rig_ob.pose.bones
    for b in pb:
        b.rotation_mode = "XYZ"
    keys = 24
    for k in range(keys + 1):
        f = n * k / keys
        a = 2 * math.pi * k / keys
        pb["hips"].location = (0, 0.012 * math.sin(a), 0)          # bone-local Y runs up the bone
        pb["spine"].rotation_euler = (math.radians(1.0) * math.sin(a), 0, 0)
        pb["chest"].rotation_euler = (math.radians(1.5) * math.sin(a - 0.4), math.radians(0.8) * math.sin(a * 0.5), 0)
        for s, sign in ((".L", 1), (".R", -1)):
            pb["upperarm" + s].rotation_euler = (math.radians(2.5) * math.sin(a - 0.8), 0, sign * math.radians(1.5) * math.sin(a))
            pb["forearm" + s].rotation_euler = (math.radians(3.0) * math.sin(a - 1.3), 0, 0)
            for hang, amp, lag in (("lantern", 5.0, 1.9), ("weight_0", 6.0, 2.2), ("weight_1", 6.0, 2.0)):
                pb[hang + s].rotation_euler = (math.radians(amp) * math.sin(a - lag), 0, math.radians(amp * 0.4) * math.cos(a - lag))
        for i in range(3):
            pb[f"back_pend_{i}"].rotation_euler = (math.radians(4.0) * math.sin(a - 1.5 - i * 0.6), 0, 0)
        # bone-local Z is the face axis (world -Y): negative turns clockwise seen from the front
        pb["clock_minute"].rotation_euler = (0, 0, -2 * math.pi * k / keys)
        for b in pb:
            b.keyframe_insert("rotation_euler", frame=f)
            if b.name == "hips":
                b.keyframe_insert("location", frame=f)
    act = rig_ob.animation_data.action
    act.name = "idle"
    # linear minute hand so it turns at an even speed
    for fc in getattr(act, "fcurves", []):
        if "clock_minute" in fc.data_path:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"
    return act
