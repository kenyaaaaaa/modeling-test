"""Materials.  One flat colour each for now; toon shading comes in step 7."""
import bpy


def hex_to_linear(h):
    h = h.lstrip("#")
    srgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb] + [1.0]


def make_materials(palette):
    mats = {}
    for name in ("stone", "brass", "rock", "rock_dark", "sand_dark", "sand_glow", "glass", "clock_face"):
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        col = hex_to_linear(palette[name])
        bsdf = m.node_tree.nodes["Principled BSDF"]
        bsdf.inputs["Base Color"].default_value = col
        bsdf.inputs["Roughness"].default_value = 0.6
        if name == "brass":
            bsdf.inputs["Metallic"].default_value = 0.6
            bsdf.inputs["Roughness"].default_value = 0.35
        m.diffuse_color = col  # Workbench uses this
        mats[name] = m
    return mats
