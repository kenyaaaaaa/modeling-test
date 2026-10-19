"""Build the stone stage with several seeds and lay the results side by side.

    .venv/bin/python scripts/variants.py 1 2 3 4
"""
import os
import subprocess
import sys

from PIL import Image, ImageDraw

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
seeds = [int(a) for a in sys.argv[1:]] or [1, 2, 3, 4]
tiles = []
for s in seeds:
    out = os.path.join(ROOT, "out", "variants", f"s{s}")
    subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "build.py"), "--stage", "stone", "--seed", str(s),
                    "--out", out, "--review", out], check=False, cwd=ROOT,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    a = Image.open(os.path.join(out, "stone", "three_quarter_case.png")).crop((0, 200, 900, 900))
    b = Image.open(os.path.join(out, "detail_stone_front.png"))
    b = b.resize((900, round(b.height * 900 / b.width)))
    tile = Image.new("RGB", (900, a.height + b.height + 40), "white")
    tile.paste(a, (0, 40))
    tile.paste(b, (0, 40 + a.height))
    ImageDraw.Draw(tile).text((10, 8), f"seed {s}", fill=(0, 0, 0), font_size=28)
    tiles.append(tile)
sheet = Image.new("RGB", (900 * len(tiles) + 10 * (len(tiles) - 1), tiles[0].height), "white")
for i, t in enumerate(tiles):
    sheet.paste(t, (i * 910, 0))
os.makedirs(os.path.join(ROOT, "review", "stone"), exist_ok=True)
sheet.save(os.path.join(ROOT, "review", "stone", "variants.png"))
print("review/stone/variants.png")
