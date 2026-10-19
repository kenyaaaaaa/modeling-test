"""Build the golem, render the review images and check it against the sheet.

    .venv/bin/python scripts/build.py --stage blockout --out out
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
from PIL import Image  # noqa: E402

from golem import blockout, case, compare, geo, limbs, materials, stone, textures, views  # noqa: E402
from golem.views import R  # noqa: E402

VIEWS = ("front", "side", "back")
# Budget groups (spec/golem.yaml) by object-name prefix.
GROUPS = {
    "hourglass": ("hourglass_", "sand_"),
    "case_and_clock": ("case_", "capital_", "cornice_", "orb_", "clock_"),
    "stone_plates": ("shoulder", "gauntlet"),
    "gears_and_weights": ("gear_", "weight_", "lantern", "bell_", "socket_", "wrist_"),
    "back_mechanism": ("back_",),
}
# Each stage replaces some blockout volumes with detailed parts.
STAGES = {
    "blockout": [],
    "case": [case.build],
    "stone": [case.build, lambda mats, seed: stone.build(mats, seed)],
    "limbs": [case.build, lambda mats, seed: stone.build(mats, seed), lambda mats, seed: limbs.build(mats, seed)],
}
# Close-up crops (sheet pixels) rendered for each stage, compared with the sheet.
DETAILS = {
    "case": [("front", (200, 40, 460, 400), "case_front"), ("side", (650, 40, 800, 400), "case_side")],
    "stone": [("front", (60, 40, 600, 340), "stone_front"), ("back", (960, 40, 1500, 340), "stone_back")],
    "limbs": [("front", (40, 230, 250, 535), "arm_front"), ("front", (200, 380, 460, 535), "legs_front"),
              ("back", (950, 40, 1520, 535), "back"), ("side", (630, 40, 930, 535), "side")],
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", default="blockout", choices=list(STAGES))
    ap.add_argument("--out", default="out")
    ap.add_argument("--review", default="review", help="folder for the committed review images")
    ap.add_argument("--seed", type=int, default=None, help="stone/rock seed (default: spec stone_seed)")
    ap.add_argument("--flat", dest="toon", action="store_false",
                    help="quick grey Workbench previews instead of the toon look")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    review = os.path.join(args.review, args.stage)
    os.makedirs(review, exist_ok=True)

    spec = yaml.safe_load(open("spec/golem.yaml", encoding="utf-8"))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    tex_dir = os.path.abspath(os.path.join(args.out, "tex"))
    os.makedirs(tex_dir, exist_ok=True)
    tex = {"clock_face": textures.clock_face(os.path.join(tex_dir, "clock_face.png"), 1024, spec["palette"])}
    mats = materials.make_materials(spec["palette"], tex)
    blockout.build(mats)
    seed = args.seed if args.seed is not None else spec.get("stone_seed", 1)
    for step in STAGES[args.stage]:
        if step.__code__.co_argcount == 2:
            step(mats, seed)
        else:
            step(mats)

    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    report = {"stage": args.stage, "objects": len(meshes), "triangles": geo.triangle_count(meshes), "views": {}}
    groups = {}
    for o in meshes:
        g = next((k for k, pre in GROUPS.items() if o.name.startswith(pre)), "rock_body_limbs")
        groups[g] = groups.get(g, 0) + geo.triangle_count([o])
    report["triangles_by_group"] = dict(sorted(groups.items()))
    xs = [(o.matrix_world @ geo.Vector(c)) for o in meshes for c in o.bound_box]
    report["size_m"] = {
        "width_x": round(max(v.x for v in xs) - min(v.x for v in xs), 3),
        "depth_y": round(max(v.y for v in xs) - min(v.y for v in xs), 3),
        "height_z": round(max(v.z for v in xs) - min(v.z for v in xs), 3),
    }

    for v in VIEWS:
        sil_path = os.path.join(args.out, f"sil_{v}.png")
        model = views.render_silhouette(v, sil_path)
        ref = R.silhouette(v)
        report["views"][v] = {"iou": round(compare.iou(model, ref), 3)}
        compare.diff_image(model, ref, v, os.path.join(review, f"diff_{v}.png"))
        prev = os.path.join(args.out, f"preview_{v}.png")
        if args.toon:
            views.render_toon_view(v, prev, scale=3)
        else:
            views.render_preview(v, prev, scale=3)
        x0, y0, x1, y1 = R.VIEWS[v]
        refcrop = os.path.join(args.out, f"ref_{v}.png")
        Image.open(R.SHEET).crop((x0, y0, x1, y1)).save(refcrop)
        compare.side_by_side([refcrop, prev, os.path.join(review, f"diff_{v}.png")],
                             os.path.join(review, f"compare_{v}.png"))

    for v, (cx0, cy0, cx1, cy1), name in DETAILS.get(args.stage, []):
        x0, y0, _, _ = R.VIEWS[v]
        k = 3
        prev = Image.open(os.path.join(args.out, f"preview_{v}.png"))
        crop = prev.crop(((cx0 - x0) * k, (cy0 - y0) * k, (cx1 - x0) * k, (cy1 - y0) * k))
        mine = os.path.join(args.out, f"detail_{name}.png")
        crop.save(mine)
        refd = os.path.join(args.out, f"ref_detail_{name}.png")
        Image.open(R.SHEET).crop((cx0, cy0, cx1, cy1)).save(refd)
        compare.side_by_side([refd, mine], os.path.join(review, f"detail_{name}.png"), height=900)

    three_q = views.render_toon_three_quarter if args.toon else views.render_three_quarter
    three_q(os.path.join(review, "three_quarter.png"))
    if args.stage in ("case", "stone", "limbs"):
        three_q(os.path.join(review, "three_quarter_case.png"), yaw_deg=-30, size=(900, 1100),
                target_z=2.2, target=(0.0, -0.6), dist=6.0)

    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(os.path.join(args.out, f"golem_{args.stage}.blend")))
    with open(os.path.join(review, "report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=1)
    print(json.dumps(report, indent=1))
    target = spec["blockout_iou_target"] if args.stage == "blockout" else spec["detail_iou_target"]
    low = {v: r["iou"] for v, r in report["views"].items() if r["iou"] < target}
    if low:
        sys.exit(f"silhouette IoU below {target}: {low}")


if __name__ == "__main__":
    main()
