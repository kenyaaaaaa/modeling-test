"""Orthographic cameras that line up pixel for pixel with the reference views."""
import math
import os
import sys

import bpy
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import ref_mask as R  # noqa: E402

# Pixel column (inside each crop) where the model's lateral 0 sits, and the
# image-right direction.  Side view: model y = 0 is the leg centre line.
ANCHOR_COL = {"front": 326 - 40, "side": 784.7 - 630, "back": 1223 - 950}
ROTATION = {"front": (90, 0, 0), "side": (90, 0, 90), "back": (90, 0, 180)}


def setup_camera(view):
    x0, y0, x1, y1 = R.VIEWS[view]
    w, h = x1 - x0, y1 - y0
    m = R.M_PER_PX
    u = (w / 2 - ANCHOR_COL[view]) * m
    z = (R.GROUND_Y - y0 - h / 2) * m
    pos = {"front": (u, -20, z), "side": (20, u, z), "back": (-u, 20, z)}[view]
    cam = bpy.data.objects.get("ViewCam")
    if cam is None:
        cam = bpy.data.objects.new("ViewCam", bpy.data.cameras.new("ViewCam"))
        bpy.context.scene.collection.objects.link(cam)
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = max(w, h) * m
    cam.data.clip_end = 100
    cam.location = pos
    cam.rotation_euler = [math.radians(a) for a in ROTATION[view]]
    sc = bpy.context.scene
    sc.camera = cam
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.render.resolution_percentage = 100
    return cam


def _render(path):
    sc = bpy.context.scene
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)


def render_silhouette(view, path):
    sc = bpy.context.scene
    setup_camera(view)
    sc.render.engine = "BLENDER_WORKBENCH"
    sh = sc.display.shading
    sh.light = "FLAT"
    sh.color_type = "SINGLE"
    sh.single_color = (1, 1, 1)
    sh.show_object_outline = False
    sh.show_cavity = False
    sc.render.film_transparent = True
    sc.render.image_settings.color_mode = "RGBA"
    _render(path)
    from PIL import Image
    return np.asarray(Image.open(path))[..., 3] > 127


def render_preview(view, path, scale=2):
    sc = bpy.context.scene
    setup_camera(view)
    sc.render.resolution_percentage = 100 * scale
    sc.render.engine = "BLENDER_WORKBENCH"
    sh = sc.display.shading
    sh.light = "STUDIO"
    sh.color_type = "TEXTURE"
    sh.show_object_outline = True
    sh.object_outline_color = (0.07, 0.05, 0.05)
    sh.show_cavity = True
    sh.cavity_type = "WORLD"
    sc.render.film_transparent = False
    sc.world = sc.world or bpy.data.worlds.new("World")
    sc.world.color = (1, 1, 1)
    sc.render.image_settings.color_mode = "RGB"
    _render(path)


def render_three_quarter(path, yaw_deg=-35, size=(900, 1000), target_z=1.75, dist=11.0, lens=50,
                         target=(0.0, 0.0), ortho_scale=None):
    """Perspective view from the front-left (character's right) for a 3D impression."""
    from mathutils import Vector
    sc = bpy.context.scene
    cam = bpy.data.objects.get("ThreeQuarterCam")
    if cam is None:
        cam = bpy.data.objects.new("ThreeQuarterCam", bpy.data.cameras.new("ThreeQuarterCam"))
        sc.collection.objects.link(cam)
    a = math.radians(yaw_deg)
    t = Vector((target[0], target[1], target_z))
    cam.location = t + Vector((math.sin(a) * dist, -math.cos(a) * dist, dist * 0.18))
    cam.rotation_euler = (t - cam.location).to_track_quat("-Z", "Y").to_euler()
    cam.data.type = "ORTHO" if ortho_scale else "PERSP"
    if ortho_scale:
        cam.data.ortho_scale = ortho_scale
    cam.data.lens = lens
    sc.camera = cam
    sc.render.resolution_x, sc.render.resolution_y = size
    sc.render.resolution_percentage = 100
    sc.render.engine = "BLENDER_WORKBENCH"
    sh = sc.display.shading
    sh.light = "STUDIO"
    sh.color_type = "TEXTURE"
    sh.show_object_outline = True
    sh.show_cavity = True
    sc.render.film_transparent = False
    sc.world = sc.world or bpy.data.worlds.new("World")
    sc.world.color = (1, 1, 1)
    sc.render.image_settings.color_mode = "RGB"
    _render(path)


# --- toon preview (looks like the sheet: flat bands of shade and ink lines) --

LIGHT_DIR = (0.45, -0.55, 0.70)   # from the upper front-left, like the sheet


def _toon_material(m):
    """Replace a material's surface with banded light (Cycles emission)."""
    nt = m.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    base = tuple(bsdf.inputs["Base Color"].default_value) if bsdf else tuple(m.diffuse_color)
    tex = next((n for n in nt.nodes if n.type == "TEX_IMAGE"), None)
    tex_name = tex.name if tex else None
    for n in list(nt.nodes):
        if n.name != tex_name:
            nt.nodes.remove(n)
    tex = nt.nodes.get(tex_name) if tex_name else None
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    geo_n = nt.nodes.new("ShaderNodeNewGeometry")
    light = nt.nodes.new("ShaderNodeCombineXYZ")
    for i, v in enumerate(LIGHT_DIR):
        light.inputs[i].default_value = v
    norm = nt.nodes.new("ShaderNodeVectorMath")
    norm.operation = "NORMALIZE"
    nt.links.new(light.outputs[0], norm.inputs[0])
    dot = nt.nodes.new("ShaderNodeVectorMath")
    dot.operation = "DOT_PRODUCT"
    nt.links.new(geo_n.outputs["Normal"], dot.inputs[0])
    nt.links.new(norm.outputs[0], dot.inputs[1])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "CONSTANT"
    els = ramp.color_ramp.elements
    els[0].position, els[0].color = 0.0, (0.52, 0.52, 0.56, 1)
    els[1].position, els[1].color = 0.45, (0.78, 0.78, 0.8, 1)
    e = els.new(0.62)
    e.color = (1.0, 1.0, 1.0, 1)
    remap = nt.nodes.new("ShaderNodeMapRange")
    remap.inputs["From Min"].default_value = -1.0
    nt.links.new(dot.outputs["Value"], remap.inputs["Value"])
    nt.links.new(remap.outputs["Result"], ramp.inputs["Fac"])
    mul = nt.nodes.new("ShaderNodeMix")
    mul.data_type = "RGBA"
    mul.blend_type = "MULTIPLY"
    mul.inputs["Factor"].default_value = 1.0
    if tex is not None:
        nt.links.new(tex.outputs["Color"], mul.inputs["A"])
    else:
        mul.inputs["A"].default_value = base
    nt.links.new(ramp.outputs["Color"], mul.inputs["B"])
    emit = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(mul.outputs["Result"], emit.inputs["Color"])
    shader = emit.outputs[0]
    if m.name.startswith("brass"):
        # a bright rim band on metal
        lw = nt.nodes.new("ShaderNodeLayerWeight")
        lw.inputs["Blend"].default_value = 0.3
        step = nt.nodes.new("ShaderNodeMath")
        step.operation = "GREATER_THAN"
        step.inputs[1].default_value = 0.55
        nt.links.new(lw.outputs["Facing"], step.inputs[0])
        rim = nt.nodes.new("ShaderNodeEmission")
        rim.inputs["Color"].default_value = (1.0, 0.93, 0.7, 1)
        mix = nt.nodes.new("ShaderNodeMixShader")
        nt.links.new(step.outputs[0], mix.inputs["Fac"])
        nt.links.new(emit.outputs[0], mix.inputs[1])
        nt.links.new(rim.outputs[0], mix.inputs[2])
        shader = mix.outputs[0]
    if m.name.startswith("glass"):
        tr = nt.nodes.new("ShaderNodeBsdfTransparent")
        mix = nt.nodes.new("ShaderNodeMixShader")
        mix.inputs["Fac"].default_value = 0.35
        nt.links.new(tr.outputs[0], mix.inputs[1])
        nt.links.new(shader, mix.inputs[2])
        shader = mix.outputs[0]
    if m.name.startswith("sand_glow"):
        emit.inputs["Strength"].default_value = 1.6
    nt.links.new(shader, out.inputs["Surface"])


def setup_toon(line_px=1.25):
    sc = bpy.context.scene
    for m in bpy.data.materials:
        if m.use_nodes and not m.get("toon"):
            _toon_material(m)
            m["toon"] = True
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 4
    sc.cycles.use_denoising = False
    sc.cycles.max_bounces = 0
    sc.view_settings.view_transform = "Standard"
    sc.world = sc.world or bpy.data.worlds.new("World")
    sc.world.use_nodes = False
    sc.world.color = (1, 1, 1)
    sc.render.film_transparent = False
    sc.render.use_freestyle = True
    sc.render.line_thickness_mode = "ABSOLUTE"   # scales with resolution percentage
    sc.render.line_thickness = 1.0
    vl = sc.view_layers[0]
    vl.use_freestyle = True
    fs = vl.freestyle_settings
    fs.crease_angle = math.radians(120)
    ls = fs.linesets[0] if fs.linesets else fs.linesets.new("ink")
    ls.select_by_visibility = True
    ls.select_silhouette = True
    ls.select_border = True
    ls.select_crease = True
    ls.select_external_contour = True
    ls.select_edge_mark = True
    if ls.linestyle is None:
        ls.linestyle = bpy.data.linestyles.new("ink")
    ls.linestyle.color = (0.04, 0.03, 0.03)
    ls.linestyle.thickness = line_px


def _render_on_white(path):
    from PIL import Image
    sc = bpy.context.scene
    sc.render.film_transparent = True
    sc.render.image_settings.color_mode = "RGBA"
    _render(path)
    im = Image.open(path).convert("RGBA")
    bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
    Image.alpha_composite(bg, im).convert("RGB").save(path)


def render_toon_view(view, path, scale=3):
    setup_camera(view)
    setup_toon()
    bpy.context.scene.render.resolution_percentage = 100 * scale
    _render_on_white(path)


def render_toon_three_quarter(path, **kw):
    """Same camera as render_three_quarter, toon shaded."""
    _orig = globals()["_render"]
    try:
        globals()["_render"] = lambda p: None
        render_three_quarter(path, **kw)
    finally:
        globals()["_render"] = _orig
    setup_toon()
    _render_on_white(path)
