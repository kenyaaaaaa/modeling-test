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
