"""Where the front concept is cut into moving parts (pixels of reference/concept_front.png).

Each part takes the opaque pixels inside its shape that no earlier part took.
`pivot` is the point it turns around; `parent` is the part it rides on.
`fill` (px): the parent's pixels under this part that border the rest of the
parent are filled in, so a hole does not show when the part moves.
"""

SRC = "reference/concept_front.png"
INK = (34, 30, 42)  # outline colour for anything drawn in (filled-in areas, effects)
ORIGIN = (765, 1000)  # feet centre on the ground: (0, 0) in Godot

# Taken first, in this order. Shapes are polygons [(x, y), ...] or rects (x0, y0, x1, y1).
PARTS = [
    # wrist weights: hang on short chains under the lanterns
    {"name": "weight_l1", "parent": "arm_l", "rect": (372, 821, 418, 896), "pivot": (395, 821)},
    {"name": "weight_l2", "parent": "arm_l", "rect": (410, 879, 476, 980), "pivot": (440, 879)},
    {"name": "weight_l3", "parent": "arm_l", "rect": (477, 838, 506, 896), "pivot": (496, 838)},
    {"name": "weight_r1", "parent": "arm_r", "rect": (1029, 840, 1067, 896), "pivot": (1047, 840)},
    {"name": "weight_r2", "parent": "arm_r", "rect": (1074, 879, 1133, 980), "pivot": (1103, 879)},
    {"name": "weight_r3", "parent": "arm_r", "rect": (1133, 815, 1168, 892), "pivot": (1150, 815)},
    # the finial under the case
    {"name": "weight_c", "parent": "body", "fill": 10,
     "poly": [(745, 778), (785, 778), (790, 800), (782, 865), (748, 865), (740, 800)], "pivot": (765, 778)},
    # arms hang from the shoulder rock; the cut runs along the top of the upper-arm stone
    {"name": "arm_l", "parent": "body", "fill": 22, "pivot": (430, 445),
     "poly": [(262, 450), (300, 418), (332, 400), (366, 402), (384, 424), (404, 440), (440, 443),
              (470, 446), (500, 451), (522, 461), (548, 472), (548, 985), (262, 985)]},
    {"name": "arm_r", "parent": "body", "fill": 22, "pivot": (1100, 445),
     "poly": [(1268, 450), (1230, 418), (1198, 400), (1164, 402), (1146, 424), (1126, 440), (1090, 443),
              (1060, 446), (1030, 451), (1008, 461), (982, 472), (982, 985), (1268, 985)]},
    # clock hands (the hub stays on top of them)
    {"name": "hand_hour", "parent": "body", "fill": 99, "pivot": (766, 190),
     "poly": [(757, 152), (775, 152), (776, 184), (756, 184)]},
    {"name": "hand_minute", "parent": "body", "fill": 99, "pivot": (766, 190),
     "poly": [(771, 181), (799, 162), (805, 166), (804, 171), (776, 194)]},
    {"name": "hub", "parent": "body", "circle": (766, 190, 9), "pivot": (766, 190), "keep_under": True},
    # legs stand still; the body above breathes. The pillar finials stay with the body.
    {"name": "legs", "parent": None, "pivot": ORIGIN, "feather_top": (762, 800),
     "poly": [(560, 735), (720, 735), (720, 985), (1250, 985), (1250, 1024), (280, 1024), (280, 985),
              (560, 985)],
     "poly2": [(810, 735), (975, 735), (975, 985), (810, 985)],
     "minus": [(593, 750, 642, 866), (893, 750, 944, 866)]},
]

# The rest is the body; it turns around the waist.
BODY_PIVOT = (765, 790)

# Floating rock chips (anything small not joined to the golem) bob in the air,
# except the ones lying on the ground.
DEBRIS_MAX_AREA = 2500
DEBRIS_GROUND_Y = 960

# Hourglass: where the sand stream runs and the glowing top half sits.
STREAM = (762, 470, 771, 612)
GLOW = (684, 312, 848, 404)
TOP_SAND = (690, 315, 840, 400)
BOTTOM_SAND = (700, 500, 830, 640)

# Swap images for the arms (in the arm's own frame, around its pivot):
#   raise: swung up towards the viewer, so shorter and a little wider
#   smear: the downswing frame, stretched, with fading copies trailing above
SWAPS = {
    "raise": {"scale": (1.04, 0.9)},
    "smear": {"scale": (1.0, 1.1), "ghosts": [(8, 0.8), (16, 0.5), (24, 0.25)]},
}
