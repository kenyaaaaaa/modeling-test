"""Build the full golem and export it for Godot: one skinned mesh, armature,
idle animation, ink lines in the vertex colour.

    .venv/bin/python scripts/export_godot.py --out godot/golem
"""
import argparse
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import bpy  # noqa: E402
import yaml  # noqa: E402

from golem import blockout, case, geo, limbs, materials, rig, stone, textures  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="godot/golem")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    spec = yaml.safe_load(open("spec/golem.yaml", encoding="utf-8"))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    tex_path = os.path.abspath(os.path.join(args.out, "clock_face.png"))
    tex = {"clock_face": textures.clock_face(tex_path, 1024, spec["palette"])}
    mats = materials.make_materials(spec["palette"], tex)
    seed = spec.get("stone_seed", 1)
    blockout.build(mats)
    case.build(mats)
    stone.build(mats, seed)
    limbs.build(mats, seed)

    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    names = sorted(o.name for o in meshes)
    tris = geo.triangle_count(meshes)
    body = rig.join_skinned(meshes)
    arm = rig.armature()
    rig.bind(body, arm)
    rig.idle(arm)

    glb = os.path.abspath(os.path.join(args.out, "golem.glb"))
    bpy.ops.export_scene.gltf(filepath=glb, export_format="GLB", export_skins=True, export_animations=True,
                              export_animation_mode="ACTIONS", export_vertex_color="ACTIVE",
                              export_all_vertex_colors=False, export_yup=True, export_apply=False)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath("out/golem_rigged.blend"))
    info = {"triangles": tris, "parts_joined": len(names), "bones": len(arm.data.bones),
            "materials": [m.name for m in body.data.materials], "glb_bytes": os.path.getsize(glb)}
    with open(os.path.join(args.out, "export_report.json"), "w", encoding="utf-8") as f:
        json.dump(info, f, indent=1)
    print(json.dumps(info, indent=1))


if __name__ == "__main__":
    main()
