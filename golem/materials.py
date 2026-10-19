"""Materials.  One flat colour each for now; toon shading comes in step 7."""
import bpy


def hex_to_linear(h):
    h = h.lstrip("#")
    srgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb] + [1.0]


# material name -> palette key
COLOURS = {
    "stone": "stone", "brass": "brass", "brass_dark": "brass_shadow", "rock": "rock", "rock_dark": "rock_dark",
    "sand_dark": "sand_dark", "sand_glow": "sand_glow", "glass": "glass", "clock_face": "clock_face", "ink": "outline",
}


def make_materials(palette, textures=None):
    """textures: material name -> image path (base colour)."""
    textures = textures or {}
    mats = {}
    for name, key in COLOURS.items():
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        col = hex_to_linear(palette[key])
        bsdf = m.node_tree.nodes["Principled BSDF"]
        bsdf.inputs["Base Color"].default_value = col
        bsdf.inputs["Roughness"].default_value = 0.6
        if name == "brass":
            bsdf.inputs["Metallic"].default_value = 0.6
            bsdf.inputs["Roughness"].default_value = 0.35
        if name == "sand_glow":
            bsdf.inputs["Emission Color"].default_value = col
            bsdf.inputs["Emission Strength"].default_value = 2.0
        if name in textures:
            tex = m.node_tree.nodes.new("ShaderNodeTexImage")
            tex.image = bpy.data.images.load(textures[name])
            m.node_tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
            m.node_tree.nodes.active = tex
        m.diffuse_color = col  # Workbench uses this
        if name == "glass":
            m.diffuse_color = col[:3] + [0.22]
            bsdf.inputs["Alpha"].default_value = 0.25
        mats[name] = m
    return mats
