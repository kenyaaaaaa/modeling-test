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

from golem import blockout, compare, geo, materials, views  # noqa: E402
from golem.views import R  # noqa: E402

VIEWS = ("front", "side", "back")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", default="blockout", choices=["blockout"])
    ap.add_argument("--out", default="out")
    ap.add_argument("--review", default="review", help="folder for the committed review images")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    review = os.path.join(args.review, args.stage)
    os.makedirs(review, exist_ok=True)

    spec = yaml.safe_load(open("spec/golem.yaml", encoding="utf-8"))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    mats = materials.make_materials(spec["palette"])
    blockout.build(mats)

    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    report = {"stage": args.stage, "objects": len(meshes), "triangles": geo.triangle_count(meshes), "views": {}}
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
        views.render_preview(v, prev)
        x0, y0, x1, y1 = R.VIEWS[v]
        refcrop = os.path.join(args.out, f"ref_{v}.png")
        Image.open(R.SHEET).crop((x0, y0, x1, y1)).save(refcrop)
        compare.side_by_side([refcrop, prev, os.path.join(review, f"diff_{v}.png")],
                             os.path.join(review, f"compare_{v}.png"))

    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(os.path.join(args.out, f"golem_{args.stage}.blend")))
    with open(os.path.join(review, "report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=1)
    print(json.dumps(report, indent=1))
    target = spec["blockout_iou_target"]
    low = {v: r["iou"] for v, r in report["views"].items() if r["iou"] < target}
    if low:
        sys.exit(f"silhouette IoU below {target}: {low}")


if __name__ == "__main__":
    main()
