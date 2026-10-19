"""Per-height outer extents (metres) of reference vs model silhouettes."""
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, "tools")
sys.path.insert(0, ".")
import ref_mask as R  # noqa: E402
from golem.views import ANCHOR_COL  # noqa: E402


def extents(mask, view, z):
    row = int(round(R.GROUND_Y - R.VIEWS[view][1] - z / R.M_PER_PX))
    xs = np.nonzero(mask[row])[0]
    if not len(xs):
        return None
    c = ANCHOR_COL[view]
    # split into runs so gaps (between legs / arms) show up
    runs, start = [], xs[0]
    for a, b in zip(xs, xs[1:]):
        if b - a > 3:
            runs.append((start, a)); start = b
    runs.append((start, xs[-1]))
    return " ".join(f"[{(a - c) * R.M_PER_PX:+.2f},{(b - c) * R.M_PER_PX:+.2f}]" for a, b in runs)


view = sys.argv[1]
out = sys.argv[2] if len(sys.argv) > 2 else "out"
ref = R.silhouette(view)
model = np.asarray(Image.open(f"{out}/sil_{view}.png"))[..., 3] > 127
for z in np.arange(3.45, 0.0, -0.1):
    print(f"z={z:.2f} ref {extents(ref, view, z)}\n       mdl {extents(model, view, z)}")
