"""Cooper's Row, round 7 (Joost, 24 Oct): the row grows to THIRTEEN vessels and stays as narrow as round 1 (3.58 m): the vessels
stand staggered, om en om voor en achter, soort van schuin: seven in a front row, six in a back row, each back vessel in the gap
between two front ones (a zigzag), so more fit in the width; the depth grows (~1.3 m). Kinds (13, vessel = compartment, left to right):
0 Tar, 1 Resin, 2 Sap, 3 Guck, 4 Eitr, 5 Ooze, 6 RoyalJelly (r6's seven, slimmer to fit the stagger), then 7 Honey (liquid, amber, a
tapered stave pail), 8 CharcoalResin (lumps like Resin, a riveted iron cauldron), 9 OozeMork (jelly, murky teal, a charred stave tub),
10 HatefulBlood (liquid, dark red, an oxblood-glazed crock), 11 Voidplasm (liquid, deep violet, a slate-violet amphora), 12 BlobVial (its
own item model, a heap of vials in a wicker basket). Front vessels are the even compartments, back vessels the odd ones; the back
ones a little taller so their rims and contents show over the front row. Liquids and jellies: Sap, Tar, Guck, Ooze, RoyalJelly, Honey,
HatefulBlood, Voidplasm, OozeMork; solids: Resin and CharcoalResin (lumps), BlobVial (vials), Eitr (orbs). Neutral vessels as r6: EVERY
vessel x EVERY liquid has a column (13 x 9 = 117 Liquid_<c>_<Item>.obj, 5 mm inside the walls). Units: 64 over 13 (5 each, Voidplasm 4,
the rarest). Labels: one per vessel, each at its vessel's x on the deck's front zone in two staggered rows: the front vessels' labels
in the outer row, the back vessels' labels in the inner row in front of the gaps between the front vessels. The sight slots face
front; the back vessels' slots are only partly seen through the gaps between the front vessels (their rims, contents and labels show).
unit.position z is 0 as in r6 (the copies' offsets carry the real depth, so ByGroup tells the vessels apart by x only); each
vessel's real depth is in anchors "compartments" (centre_z_unity). The BlobVial vessel's own copies are vials (simulated with the
vial model); every other vessel's lumps are Resin rocks (CharcoalResin: the same mesh; Eitr: orbs at the same poses). The atlas is
128 x 208 (r5's 128 rows untouched; rows 128-159 r6's honey-jar clay; rows 160-191 iron cauldron, oxblood glaze, violet glaze, charred
timber; rows 192-207 four more liquid tiles). Checks as r6 plus coplanar_frame (no two same-facing overlapping faces in one plane,
report_coplanar as in fletcher_r2). The missing item models (Honey, CharcoalResin, OozeMork, HatefulBlood, Voidplasm, BlobVial) were
ripped into ValheimRip/items with items_extract.extract (a wrapper for the six names; the shared script is untouched).
Run: blender -b -P coopersrow_r7.py -- [--out DIR] [--assets DIR] [--quick] [--no-render] [--views a,b] [--cap N]
Round 6's notes follow:
Cooper's Row, round 6 (Joost, 24 Oct): r5 plus a SEVENTH vessel for Royal Jelly (thick, sticky, stacks of 50 - it belongs here,
not in the Apothecary). The six vessels, their homes, liquids and labels are r5's; the new one is a wide-mouthed honey jar in a
warm glazed clay (own tile "hclay"), rolled lip, root-lashed neck, three gauge bars; it stands at the right end (its label to its left). Royal Jelly is a liquid like Sap/Tar/Guck/Ooze: a new muted tile, pale
translucent gold with a lighter top; EVERY vessel x EVERY liquid has a column (neutral vessels; 7 x 5 = 35). Eitr stays out of the
liquids (glowing orbs; the mod draws the game's Eitr model on its units). 64 units over 7: Tar 9, Resin 12, Sap 8, Guck 9, Eitr 9,
Ooze 8, RoyalJelly 9. The skid grows with the row (L computed, ~4.8 m) at the same depth (1.24) and height. The atlas is 128 x 160
(r5's 128 rows untouched, the new clay tile in the added rows: every UV is built in r5's 128-row space and mapped once at the end,
v' = 1 - (1 - v) * 128/160, so every texel stays where it was).
(A lid for the jar was tried and dropped: leaning on the back rail it is hidden behind the jar and the rail from every side.)
Run: blender -b -P coopersrow_r6.py -- [--out DIR] [--assets DIR] [--quick] [--no-render] [--views a,b] [--cap N]
Round 5's notes follow (compartment 0-5 are r5's vessels, 6 = Royal Jelly):
Cooper's Row, round 5 (Joost): show ONLY what is stored, and the semi-liquids as liquid or jelly.
- Liquids: Sap (light green), Tar (thick black, a little gloss), Guck (green jelly), Ooze (murky brown-green jelly), Eitr (pale
  blue). Solid: Resin (lumps). The vessels are neutral: any vessel holds any of the six (a store of only sap shows six vessels
  of green sap); the homes (unit "item") still send each item to its own vessel first.
- For every vessel x every liquid item a liquid column (Liquid_<compartment>_<Item>.obj: a closed prism of height 1, the
  vessel's own face count and angles, the vessel's narrowest inside over the liquid's range 5 mm in) on that item's tile
  (five new muted liquid tiles, each with a lighter top); anchors "liquids": one entry per (vessel, item).
- "labels": per vessel a spot on the skid in front, off the slot's axis, where the mod stands ONE copy of whatever the vessel
  holds (fit_longest_m 0.22, upright, turned 18 degrees); every one of the six item models is checked there against the frame
  (0 clipping, on the deck). The skid is 1.24 m deep (round 4: 1.10) so a label fits in front of the Resin pot; the vessels
  keep their places.
- Units: every vessel's units carry Resin lumps (the solid fallback: the mod draws lumps only for an item with no liquid entry
  for that vessel); round 4's sap keg on unit 5 is gone (the label replaces it).
Round 4's notes (shapes, slots, gauges and the liquid schema still hold):
Cooper's Row, round 4 (Joost on round 3): Sap goes back into round 2's birch-bark tub (the big vat, the jug and the dipper
are gone); the liquid is the Sap item's own light green (sampled from the ripped YggdrasilSap texture: mean of its green
texels sRGB 0.31/0.70/0.28, muted per STYLE.md, a slightly lighter top); Liquid_Sap.obj follows the tub's narrowest inside
(its 16 faces at the tub's own angles, 5 mm in), so it never touches a wall at any fill. In front of the tub stands the real
Sap item (the small glowing keg) as its label: one copy on the sap group's FIRST unit (the mod draws a liquid unit's copies
too), the other sap units have none. The tub keeps round 3's slot on the row, so the other five vessels and their contents
are round 3's (same positions, same simulation).
Round 3's notes (the liquid schema still holds):
Cooper's Row, round 3: Sap is a LIQUID (Joost). Its vessel is now one big hooped sap vat (straight staves, 16 of them, the
sight slot with its hoops and gauge bar kept) that fills with liquid: the mod draws Liquid_Sap.obj, a closed 16-sided cylinder
of height 1 that follows the vat's inner staves 5 mm inside, scaled to the stock (anchors "liquids": floor + top_y, drawn as
T(floor) * S(1, (top_y - floor.y) * fill, 1) with the frame's material). The Sap group keeps 9 units, each "item": "Sap",
kind "liquid", with no copies. Decor: a clay jug with sap in it on the skid in front, between the vat and the Guck barrel,
and a wooden dipper hanging on an iron hook on the vat's front-left. The atlas gains two sap tiles (side, lighter top).
The other five vessels are round 2's (same sizes, compartments, order and item fields); the row grows to 4.12 m.
Round 2's notes, still true for the other five:
Cooper's Row, round 2: round 1 grown into the family's scale (coordinator, 23 Oct: next to the bunker and the Ore Bin the
round 1 vessels (rim 0.76 m) read small and the 0.15 m lumps like toy contents beside 0.33 m ore). Round 2: vessels about
0.95 m to the rim (the clay pots and the half barrel a little lower), widths scaled to match (row 4.0 x 1.1 m), item lumps
0.25-0.27 m on their longest side (LONGS per item); fewer copies, still crowned over the rim when full. Everything else as
round 1: sight slots, gauges, 64 units (Resin 16), compartments 0-5 in the same order, the same anchors schema, every unit
names its item ("item", the mod's homes), STYLE.md.
Round 1's notes, still true:
Six vessels for sticky goods on one timber skid (concept: scratchpad sketch7/barrels, Joost liked it).
Left to right as seen from the front: Tar (oiled barrel), Resin (clay pot), Sap (birch-bark tub), Guck (half barrel),
Eitr (cask), Ooze (dark clay pot). One item kind per vessel (the mod's ByGroup, group key "compartment" = vessel 0-5).
Run: blender -b -P coopersrow_r5.py -- [--out DIR] [--assets DIR] [--quick] [--no-render] [--views a,b] [--cap N]

Fullness reads through the copies themselves (the mod only places item copies at anchors, it cannot draw a fill column):
every vessel has a sight slot in its front (two staves / two clay faces left out from just over the floor to under the top
band), the item's own lumps heap up inside and crown over the rim when full. The slot shows the heap's level from a standing
player's eye; barrels carry iron hoops at the slot's quarter heights and an iron gauge bar at the half, the clay pots and the
birch tub three riveted gauge bars (1/4, 1/2, 3/4).

Contents: 64 units (an 8 x 8 container grid): Tar 10, Resin 16 (the most stock on the server: 1,429), Sap 9, Guck 10,
Eitr 10, Ooze 9. Each vessel is filled copy by copy (Blender rigid bodies / Bullet, convex hulls, friction 0.75,
restitution 0; every copy is dropped onto the frozen earlier ones at the spot of 16 that lies furthest under the target
surface and frozen when it has settled) until its target surface is covered: from the rim's inside (EDGE under it) rising
inward at CROWN, at most CAPOVER over the rim. The invisible collider is the vessel's inner wall pulled in by WALLGAP (and
closes the slot), extended straight up over the rim; a copy that leans on that extension (over the rim, within 2 cm of it),
leaves the collider or touches the frame is taken out and dropped again elsewhere. The copy sequence is then cut into the
vessel's units in drop order, so any prefix of units (and any prefix of a unit's copies) only rests on what is shown.
Eitr: its prefab uses a built-in Unity mesh the extractor cannot read, so its vessel is laid out with Resin lumps at Resin's
size (fit_longest_m); at runtime the mod draws the game's own Eitr model at that longest size.
unit.position: x = centre of the unit's copies, y = one height for every unit, z = 0 (vessel axis line), so the mod's
ByGroup sees the six vessels only by x (left to right); unit.box.y reaches from the lowest rotated-bounds corner of any copy
(the mod's never-below-the-floor lift never moves a settled copy) up to the highest copy, box.z is the chord a divider board
may take inside the round vessel (70% of its inner diameter).
Atlas (128 px, point filtered, 48 px per metre): timber, end grain and iron rows from assets/bunker_r4, the dark oiled timber
and the wear swatch (worn timber / worn iron for chamfers and rivet heads) from assets/metalpallet_r3; new: clay, dark clay,
birch bark, root lashing.
Files: assets/coopersrow_r6/{CoopersRow.obj, Liquid_<c>_<Item>.obj x 35, coopersrow_atlas.png, coopersrow_anchors.json}, the json written last
(temp file + rename). Renders and simlog in --out (default: the scratchpad coopersrow1 folder).
"""
import bpy, bmesh, sys, os, math, json, random, time
import numpy as np
from mathutils import Vector, Matrix, Euler, Quaternion
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, ".."))
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
def arg(k, d=None): return argv[argv.index(k) + 1] if k in argv else d
SCR = "C:/Users/joost/AppData/Local/Temp/claude/C--Users-joost--pai/5e4bc60b-cdfe-4638-8e29-2e507fa13cf9/scratchpad/coopersrow_r7"
OUTA = arg("--assets", os.path.join(REPO, "assets", "coopersrow_r7"))
OUT = arg("--out", SCR)
QUICK = "--quick" in argv
NORENDER = "--no-render" in argv
VIEWSEL = arg("--views").split(",") if "--views" in argv else None
CAP = int(arg("--cap", 90))                 # most copies per vessel
ITEMS_DIR = "C:/Users/joost/ValheimRip/items"
sys.path.append(ITEMS_DIR)
from load_item import load_item
os.makedirs(OUTA, exist_ok=True); os.makedirs(OUT, exist_ok=True)
rng = random.Random(17)        # frame
crng = random.Random(int(arg("--cseed", 32)))   # contents

TEX, DENS = 128, 48.0
TH = 208                       # atlas height (r6: 160; r7: 48 rows added: four new tiles + four more liquid tiles)
KV = TEX / TH
FPS = 24
MARGIN = 0.003
# longest side of the lumps per item (m), in the family range (ore bin ~0.33): the kinds with many units a little smaller so
# every unit still gets at least one copy (Resin 16 units, Sap 9, Eitr 10 in their vessels)
LONGS = {"Tar": 0.2, "Resin": 0.17, "Sap": 0.2, "Guck": 0.2, "Eitr": 0.2, "Ooze": 0.2, "RoyalJelly": 0.2, "Honey": 0.2,
         "CharcoalResin": 0.20, "OozeMork": 0.2, "HatefulBlood": 0.2, "Voidplasm": 0.2, "BlobVial": 0.21}
# r7: the slimmer vessels take smaller rocks (r6: 0.25); only Resin's and the vials' sizes are laid out, the others are drawn at the lumps' size
WALLGAP = 0.012                # collider inside the inner wall
EDGE, CROWN, CAPOVER = 0.04, 0.85, 0.18
COVER_TOL = 0.06
LIQUID = ["Sap", "Tar", "Guck", "Ooze", "RoyalJelly", "Honey", "HatefulBlood", "Voidplasm", "OozeMork"]   # drawn as liquid columns by the mod in any vessel
# Joost, 24 Oct: refined eitr is glowing orbs, not a liquid: Eitr is not in LIQUID (r6); the mod draws the game's Eitr model.
LUMP = "Resin"                 # the solid fallback every vessel's units carry
ITEMS13 = ["Tar", "Resin", "Sap", "Guck", "Eitr", "Ooze", "RoyalJelly", "Honey", "CharcoalResin", "OozeMork", "HatefulBlood", "Voidplasm", "BlobVial"]
SOLID = {"BlobVial": "BlobVial"}   # r7: the vessels whose own lumps are not Resin rocks (the vial basket is laid out with vials)
LABEL_LONG, LABEL_YAW, LABEL_R = 0.20, 18.0, 0.14   # the label copy: longest side, turn, the radius any of the six needs on the deck
LIQ_INSET, LIQ_FLOOR, LIQ_FREEBOARD = 0.005, 0.003, 0.07   # inside the staves, over the inner floor, under the rim when full
GRID = 0.03

# ---------- layout (Blender metres, z up, -y = front) ----------
# item, kind, rim height (world), outer profile shape [(r, z/h)] (round 1's), units, widest outer radius (the shape is scaled to it)
_V = [
    # compartment i: even = front row, odd = back row (a little taller). Last number: the widest outer radius the shape is scaled to
    ("Tar",   "barrel", 0.88, [(0.225, 0), (0.25, 0.12), (0.27, 0.5), (0.25, 0.88), (0.23, 1.0)], 5, 0.205),
    ("Resin", "clay",   0.92, [(0.19, 0), (0.26, 0.15), (0.30, 0.45), (0.285, 0.72), (0.25, 0.88), (0.272, 0.93), (0.272, 1.0)], 5, 0.225),
    ("Sap",   "bark",   0.80, [(0.24, 0), (0.255, 0.5), (0.27, 1.0)], 5, 0.205),
    ("Guck",  "half",   0.86, [(0.25, 0), (0.27, 0.3), (0.285, 0.7), (0.29, 1.0)], 5, 0.225),
    ("Eitr",  "cask",   0.88, [(0.20, 0), (0.235, 0.14), (0.25, 0.5), (0.235, 0.86), (0.205, 1.0)], 5, 0.205),
    ("Ooze",  "dclay",  0.90, [(0.17, 0), (0.23, 0.15), (0.26, 0.45), (0.245, 0.72), (0.215, 0.88), (0.235, 0.93), (0.235, 1.0)], 5, 0.225),
    ("RoyalJelly", "jar", 0.76, [(0.20, 0), (0.27, 0.12), (0.305, 0.40), (0.305, 0.65), (0.28, 0.84), (0.30, 0.92), (0.30, 1.0)], 5, 0.21),
    # r7: the new six. Honey: a tapered stave pail (wider at the top); CharcoalResin: a riveted iron cauldron; OozeMork: a charred stave
    # tub; HatefulBlood: an oxblood-glazed crock; Voidplasm: a slate-violet amphora; BlobVial: a hooped wicker basket
    ("Honey", "pail",   0.88, [(0.74, 0), (0.88, 0.5), (1.0, 1.0)], 5, 0.225),
    ("CharcoalResin", "pot", 0.70, [(0.58, 0), (0.82, 0.16), (1.0, 0.5), (0.97, 0.78), (0.92, 0.88), (1.0, 0.93), (1.0, 1.0)], 5, 0.21),
    ("OozeMork", "char", 0.82, [(0.88, 0), (1.0, 0.45), (0.94, 1.0)], 5, 0.225),
    ("HatefulBlood", "crock", 0.76, [(0.55, 0), (0.85, 0.15), (1.0, 0.45), (0.95, 0.72), (0.85, 0.88), (0.92, 0.93), (0.92, 1.0)], 5, 0.205),
    ("Voidplasm", "amph", 1.00, [(0.45, 0), (0.80, 0.18), (1.0, 0.42), (0.92, 0.66), (0.80, 0.86), (0.88, 0.92), (0.88, 1.0)], 4, 0.225),
    ("BlobVial", "basket", 0.68, [(0.70, 0), (0.88, 0.35), (1.0, 0.72), (1.0, 1.0)], 5, 0.205),
]
VESSELS = [(it, k, rim, [(r * R / max(a for a, _ in pr), z) for r, z in pr], nu) for it, k, rim, pr, nu, R in _V]
NUNITS = sum(v[4] for v in VESSELS)
assert NUNITS == 64
NV = len(VESSELS)
NSEG = {"jar": 16, "vat": 16, "barrel": 14, "half": 14, "cask": 12, "clay": 16, "dclay": 16, "bark": 16,
        "pail": 14, "pot": 16, "char": 12, "crock": 16, "amph": 16, "basket": 16}
NW = 2                          # faces left out for the slot
WALLT = {"jar": 0.035, "vat": 0.04, "barrel": 0.04, "half": 0.04, "cask": 0.04, "clay": 0.035, "dclay": 0.035, "bark": 0.03,
         "pail": 0.035, "pot": 0.025, "char": 0.04, "crock": 0.035, "amph": 0.03, "basket": 0.03}
HOOPOUT = 0.012
GAP = 0.012
SKID_PAD = 0.03
# r7 stagger: seven vessels in a front row, six in a back row each in the gap between two front ones; the skid is round 1's length
L = 3.58
VR = [R + HOOPOUT + 0.003 for *_x, R in _V]              # the radius each vessel needs (widest outer + hoops)
FRONT = [i for i in range(NV) if i % 2 == 0]; BACK = [i for i in range(NV) if i % 2 == 1]
_span = L - 2 * SKID_PAD
FGAP = (_span - sum(2 * VR[i] for i in FRONT)) / (len(FRONT) - 1)
assert FGAP > 0.06, FGAP
xs = [0.0] * NV; cur = 0.0
for i in FRONT:
    xs[i] = cur + VR[i]; cur += 2 * VR[i] + FGAP
for i in BACK: xs[i] = (xs[i - 1] + xs[i + 1]) / 2
xs = [x - _span / 2 for x in xs]
for a_, b_ in zip(BACK, BACK[1:]): assert xs[b_] - xs[a_] - VR[a_] - VR[b_] >= 0.02, ("back vessels touch", a_, b_)
CLEAR = 0.02
DYB = max(math.sqrt(max(0.0, (VR[i] + VR[n] + CLEAR) ** 2 - (xs[i] - xs[n]) ** 2)) for i in BACK for n in (i - 1, i + 1))
# the labels: front vessels' labels in front of them; back vessels' labels in front of the gaps (nearer the vessels), clear of
# the front vessels; the two rows far enough apart that neighbouring labels do not touch
_LB = min(-math.sqrt(max(0.0, (VR[n] + 0.015 + LABEL_R) ** 2 - (xs[i] - xs[n]) ** 2)) for i in BACK for n in (i - 1, i + 1))
_dxl = min(abs(xs[i] - xs[n]) for i in BACK for n in (i - 1, i + 1))
_LF = min(min(-(VR[i] + 0.015 + LABEL_R) for i in FRONT), _LB - math.sqrt(max(0.0, (2 * LABEL_R + 0.012) ** 2 - _dxl ** 2)))
_y_front_edge = _LF - LABEL_R - 0.012
_y_back_edge = DYB + max(VR[i] for i in BACK) + 0.03 + 0.11          # + the back rail's face (0.11 in from the deck's back edge)
D = _y_back_edge - _y_front_edge                                    # skid depth
_shift = -(_y_front_edge + D / 2)                                   # centre the deck on y = 0
ys = [(DYB if i in BACK else 0.0) + _shift for i in range(NV)]
LAB_Y = {i: (_LB if i in BACK else _LF) + _shift for i in range(NV)}
print("PLAN L", L, "D", round(D, 3), "front gap", round(FGAP, 3), "back dy", round(DYB, 3), "xs", [round(x, 3) for x in xs], "ys", [round(y, 3) for y in ys],
      "label rows", round(LAB_Y[0], 3), round(LAB_Y[1], 3), flush=True)
SLEEPER_H, PLANK_T = 0.10, 0.05
DECK = SLEEPER_H + PLANK_T     # 0.15: deck top, vessel bottoms
FLREL = 0.06                   # inner floor over the vessel bottom
FL = DECK + FLREL


# ---------- atlas ----------
TILES = {"hewn": (0, 0, 128, 32), "end0": (0, 32, 32, 32), "end1": (32, 32, 32, 32), "dark": (64, 32, 32, 32),
         "wearw": (96, 32, 32, 16), "weari": (96, 48, 32, 16), "iron": (0, 64, 128, 16),
         "clay": (0, 80, 32, 32), "dclay": (32, 80, 32, 32), "bark": (64, 80, 32, 32), "root": (96, 80, 32, 32),
         "iron2": (120, 112, 8, 16), "hclay": (0, 128, 32, 32),
         "ironp": (0, 160, 32, 32), "rclay": (32, 160, 32, 32), "vclay": (64, 160, 32, 32), "char": (96, 160, 32, 32)}
for _i, _it in enumerate(LIQUID):          # round 5: per liquid a 16x16 side tile and an 8x16 top tile, 24 px apart (r7: the 6th on in rows 192-207)
    _y0, _x0 = (112, 24 * _i) if _i < 5 else (192, 24 * (_i - 5))
    TILES[_it + "_side"] = (_x0, _y0, 16, 16); TILES[_it + "_top"] = (_x0 + 16, _y0, 8, 16)

def load_px(path):
    im = bpy.data.images.load(path)
    w, h = im.size
    a = np.array(im.pixels[:], np.float32).reshape(h, w, 4)[::-1, :, :3]     # top-down
    bpy.data.images.remove(im)
    return a

def mix(a, b, t): t = np.clip(t, 0, 1)[..., None]; return a * (1 - t) + b * t
def srgb(c): return np.array(c, np.float32)

def build_atlas():
    B = load_px(os.path.join(REPO, "assets", "bunker_r4", "bunker_atlas.png"))
    P = load_px(os.path.join(REPO, "assets", "metalpallet_r3", "metalpallet_atlas.png"))
    A = np.zeros((TH, TEX, 3), np.float32)
    A[0:32] = B[0:32]                       # bunker hewn timber
    A[32:64, 0:64] = B[32:64, 0:64]         # bunker end grain, rings 0 and 1
    A[32:64, 64:96] = P[0:32, 0:32]         # pallet dark oiled hewn timber
    A[32:64, 96:128] = P[32:64, 96:128]     # pallet wear swatch: worn timber (top), worn iron (bottom)
    A[64:80] = B[64:80]                     # bunker iron
    A[112:128] = B[64:80]                   # (spare) bunker iron again; round 3 paints sap into x 0-63
    nr = np.random.default_rng(41)
    yy, xx = np.meshgrid(np.arange(32), np.arange(32), indexing="ij")
    blocky = lambda s: np.kron(nr.random((32 // s, 32 // s)), np.ones((s, s), np.float32))
    edge = np.minimum(np.minimum(xx, 31 - xx), np.minimum(yy, 31 - yy))
    def clay(base, dark, light):
        t = blocky(8) * 0.22 + blocky(4) * 0.22 + blocky(2) * 0.14 + nr.random((32, 32)) * 0.14
        rings = 0.5 + 0.5 * np.sin(yy * 1.1 + 0.6 * np.sin(xx * 0.35 + 1.0))          # throwing rings, horizontal
        t += np.clip(rings - 0.7, 0, 1) * 1.1
        t += ((yy % 9) == 4) * 0.25                                                     # a crevice every few rings
        img = mix(base, dark, t)
        worn = (nr.random((32, 32)) < 0.05) & (t < 0.45)
        img[worn] = mix(img[worn], np.broadcast_to(light, img[worn].shape), np.full(worn.sum(), 0.6))
        return img
    A[80:112, 0:32] = clay(srgb((0.45, 0.31, 0.22)), srgb((0.27, 0.17, 0.12)), srgb((0.58, 0.45, 0.34)))
    A[80:112, 32:64] = clay(srgb((0.29, 0.24, 0.19)), srgb((0.14, 0.115, 0.09)), srgb((0.42, 0.36, 0.29)))
    # birch bark: muted off-white, dark horizontal lenticels, a few peeled warm patches, darker crevices
    base, dark, warm = srgb((0.64, 0.61, 0.54)), srgb((0.19, 0.16, 0.13)), srgb((0.47, 0.35, 0.24))
    t = blocky(4) * 0.18 + nr.random((32, 32)) * 0.12
    img = mix(base, dark, t)
    peel = (blocky(8) > 0.88) & (blocky(2) > 0.5)
    img[peel] = mix(img[peel], np.broadcast_to(warm, img[peel].shape), np.full(peel.sum(), 0.55))
    for _ in range(22):
        y, x, n = nr.integers(0, 32), nr.integers(0, 32), nr.integers(2, 6)
        for k in range(n): img[y, (x + k) % 32] = mix(img[y, (x + k) % 32][None], dark[None], np.array([0.6]))[0]
    img = mix(img, np.broadcast_to(dark, img.shape), (edge <= 0) * 0.25)
    A[80:112, 64:96] = img
    # root lashing: twisted withies, diagonal strands with dark gaps
    base, dark, light = srgb((0.40, 0.31, 0.19)), srgb((0.17, 0.12, 0.075)), srgb((0.53, 0.43, 0.29))
    s = (xx + yy * 0.8) % 7
    t = (s < 1.2) * 0.85 + nr.random((32, 32)) * 0.2 + ((yy % 8) == 0) * 0.5
    img = mix(base, dark, t)
    hl = (s > 3.0) & (s < 4.2)
    img[hl] = mix(img[hl], np.broadcast_to(light, img[hl].shape), np.full(hl.sum(), 0.45))
    A[80:112, 96:128] = img
    # r6: honey-jar clay (rows 128-159): a warm ochre-tan glaze, throwing rings, a few darker drips running down from the lip
    t = blocky(8) * 0.18 + blocky(4) * 0.2 + blocky(2) * 0.12 + nr.random((32, 32)) * 0.12
    rings = 0.5 + 0.5 * np.sin(yy * 1.1 + 0.6 * np.sin(xx * 0.35 + 1.0))
    t += np.clip(rings - 0.72, 0, 1) * 1.4 + ((yy % 9) == 4) * 0.35
    img = mix(srgb((0.72, 0.58, 0.34)), srgb((0.42, 0.29, 0.15)), t)
    for cx in (4, 12, 19, 27):                      # drips
        ln = int(nr.integers(8, 20))
        img[0:ln, cx] = mix(img[0:ln, cx], np.broadcast_to(srgb((0.36, 0.22, 0.10)), (ln, 3)), np.full(ln, 0.6))
    worn = (nr.random((32, 32)) < 0.05) & (t < 0.45)
    img[worn] = mix(img[worn], np.broadcast_to(srgb((0.76, 0.64, 0.42)), img[worn].shape), np.full(worn.sum(), 0.6))
    A[128:160, 0:32] = img
    # r7: four new 32x32 tiles from their own generator (r5's and r6's pixels do not change)
    nr2 = np.random.default_rng(77)
    blocky2 = lambda s: np.kron(nr2.random((32 // s, 32 // s)), np.ones((s, s), np.float32))
    def glaze(base, dark, light):
        t = blocky2(8) * 0.2 + blocky2(4) * 0.2 + blocky2(2) * 0.12 + nr2.random((32, 32)) * 0.12
        rings = 0.5 + 0.5 * np.sin(yy * 1.1 + 0.6 * np.sin(xx * 0.35 + 1.0))
        t += np.clip(rings - 0.72, 0, 1) * 1.2 + ((yy % 9) == 4) * 0.3
        img = mix(base, dark, t)
        worn = (nr2.random((32, 32)) < 0.05) & (t < 0.45)
        img[worn] = mix(img[worn], np.broadcast_to(light, img[worn].shape), np.full(worn.sum(), 0.6))
        return img
    # riveted iron plate: dark scaled iron, horizontal and (staggered) vertical seams, light rivet heads, a little warm rust
    t = nr2.random((32, 32)) * 0.3 + blocky2(8) * 0.25 + blocky2(4) * 0.15
    img = mix(srgb((0.19, 0.18, 0.17)), srgb((0.075, 0.075, 0.08)), t)
    seam = ((yy % 11) == 0) | (((xx + (yy // 11) * 7) % 16) == 0)
    img[seam] = mix(img[seam], np.broadcast_to(srgb((0.04, 0.04, 0.045)), img[seam].shape), np.full(seam.sum(), 0.8))
    riv = ((yy % 11) == 5) & ((xx % 8) == 3)
    img[riv] = mix(img[riv], np.broadcast_to(srgb((0.40, 0.38, 0.35)), img[riv].shape), np.full(riv.sum(), 0.85))
    rust = (nr2.random((32, 32)) < 0.07) & (t > 0.3)
    img[rust] = mix(img[rust], np.broadcast_to(srgb((0.33, 0.19, 0.10)), img[rust].shape), np.full(rust.sum(), 0.55))
    A[160:192, 0:32] = img
    A[160:192, 32:64] = glaze(srgb((0.36, 0.14, 0.11)), srgb((0.16, 0.06, 0.05)), srgb((0.52, 0.26, 0.20)))       # oxblood glaze
    A[160:192, 64:96] = glaze(srgb((0.27, 0.21, 0.36)), srgb((0.12, 0.09, 0.19)), srgb((0.42, 0.36, 0.52)))       # slate-violet glaze
    # charred timber: near-black staves, grain along u, grey ash patches, a few dull ember cracks
    row = np.repeat(nr2.random((32, 1)), 32, axis=1)
    t = row * 0.5 + blocky2(4) * 0.2 + nr2.random((32, 32)) * 0.15
    img = mix(srgb((0.14, 0.115, 0.095)), srgb((0.045, 0.038, 0.034)), t)
    ash = (blocky2(8) > 0.82) & (blocky2(2) > 0.4)
    img[ash] = mix(img[ash], np.broadcast_to(srgb((0.34, 0.32, 0.30)), img[ash].shape), np.full(ash.sum(), 0.5))
    for _ in range(9):
        y, x, n = int(nr2.integers(0, 32)), int(nr2.integers(0, 32)), int(nr2.integers(3, 9))
        for k in range(n): img[y, (x + k) % 32] = mix(img[y, (x + k) % 32][None], srgb((0.45, 0.19, 0.07))[None], np.array([0.6]))[0]
    A[160:192, 96:128] = img
    # round 5: five liquids, muted per STYLE.md: side (16x16, darker; liquids with faint vertical streaks the mod stretches with
    # the fill, jellies with blobs and trapped bubbles) and top (8x16, lighter, a few glints). Sap: the Sap item's green
    # (YggdrasilSap_d.png green texels ~0.31/0.70/0.28, muted, as round 4).
    LIQ_COL = {   # side base, dark, light; top base, dark, light; kind
        "Sap":  ((0.30, 0.48, 0.25), (0.19, 0.33, 0.15), (0.44, 0.62, 0.36), (0.40, 0.58, 0.32), (0.28, 0.44, 0.22), (0.58, 0.74, 0.47), "liquid"),
        "Tar":  ((0.075, 0.07, 0.065), (0.03, 0.03, 0.03), (0.21, 0.21, 0.23), (0.11, 0.105, 0.10), (0.05, 0.05, 0.05), (0.32, 0.32, 0.35), "liquid"),
        # Guck (coordinator: it read like Sap): darker, olive and murky, towards the Guck item's own colour (its rock texture x the
        # item tint 0/1/0.255: mean 0/0.45/0.09, a green with almost no blue), a cloudy jelly with a slightly lighter top
        "Guck": ((0.19, 0.23, 0.085), (0.09, 0.115, 0.04), (0.29, 0.33, 0.14), (0.25, 0.30, 0.11), (0.16, 0.20, 0.07), (0.36, 0.41, 0.18), "jelly"),
        "Ooze": ((0.31, 0.30, 0.19), (0.18, 0.18, 0.10), (0.44, 0.42, 0.28), (0.38, 0.37, 0.24), (0.25, 0.24, 0.15), (0.52, 0.50, 0.34), "jelly"),
        # Royal Jelly (r6, Joost: pale translucent gold, a lighter top; clearly apart from Sap's green, Guck's olive and Ooze's murk):
        # royal jelly is a pale cream-gold; muted per STYLE.md but clearly yellow, a soft cloudy jelly with a few trapped bubbles
        "RoyalJelly": ((0.82, 0.67, 0.30), (0.64, 0.48, 0.17), (0.94, 0.84, 0.52), (0.90, 0.79, 0.42), (0.76, 0.62, 0.27), (0.99, 0.93, 0.68), "jelly"),
        # r7 (Joost: Honey golden and thick, HatefulBlood dark red, Voidplasm deep violet; OozeMork a jelly like Ooze): Honey a deeper
        # amber than Royal Jelly's pale gold; the blood a dark clotted red with a gloss; the plasm deep violet with faint glints;
        # Ooze (Mork): the item's own cyan tint over the rock texture (0.30/0.45/0.33) pushed to a murky teal-grey, apart from Sap
        "Honey": ((0.70, 0.42, 0.09), (0.50, 0.27, 0.05), (0.86, 0.58, 0.18), (0.80, 0.52, 0.13), (0.62, 0.36, 0.07), (0.95, 0.72, 0.30), "liquid"),
        "HatefulBlood": ((0.30, 0.045, 0.045), (0.15, 0.02, 0.025), (0.50, 0.12, 0.10), (0.40, 0.06, 0.055), (0.22, 0.03, 0.03), (0.62, 0.18, 0.15), "liquid"),
        "Voidplasm": ((0.20, 0.09, 0.34), (0.09, 0.04, 0.17), (0.40, 0.22, 0.58), (0.28, 0.13, 0.45), (0.14, 0.06, 0.25), (0.52, 0.32, 0.72), "liquid"),
        "OozeMork": ((0.17, 0.33, 0.31), (0.08, 0.18, 0.17), (0.30, 0.48, 0.45), (0.24, 0.42, 0.39), (0.14, 0.28, 0.26), (0.40, 0.58, 0.54), "jelly"),
    }
    yy16, xx16 = np.meshgrid(np.arange(16), np.arange(16), indexing="ij")
    for i, it in enumerate(LIQUID):
        rr = nr if i < 5 else nr2
        y0, x0 = (112, 24 * i) if i < 5 else (192, 24 * (i - 5))
        sb, sd, sl, tb, td, tl, kind = [srgb(c) if not isinstance(c, str) else c for c in LIQ_COL[it]]
        if kind == "liquid":
            t = 0.35 + 0.25 * np.sin(xx16 * 1.3 + 1.3 * np.sin(xx16 * 0.4 + i)) + rr.random((16, 16)) * 0.15
            side = mix(mix(sb, sd, t), np.broadcast_to(sl, (16, 16, 3)), (rr.random((16, 16)) < 0.05) * 0.6)
        else:
            blob = np.kron(rr.random((4, 4)), np.ones((4, 4), np.float32)) * 0.35 + np.kron(rr.random((8, 8)), np.ones((2, 2), np.float32)) * 0.3
            side = mix(sb, sd, blob + rr.random((16, 16)) * 0.12)
            bub = rr.random((16, 16)) < 0.07
            side[bub] = mix(side[bub], np.broadcast_to(sl, side[bub].shape), np.full(bub.sum(), 0.75))
        A[y0:y0 + 16, x0:x0 + 16] = side
        t = rr.random((16, 8)) * 0.25 + 0.15 * np.sin(np.arange(8)[None, :] * 0.8 + np.arange(16)[:, None] * 0.7)
        top = mix(tb, td, t)
        gl = rr.random((16, 8)) < (0.08 if kind == "liquid" else 0.05)
        top[gl] = mix(top[gl], np.broadcast_to(tl, top[gl].shape), np.full(gl.sum(), 0.85))
        A[y0:y0 + 16, x0 + 16:x0 + 24] = top
    A[112:128, 120:128] = B[64:80, 0:8]
    im = bpy.data.images.new("coopersrow_atlas", TEX, TH, alpha=False)
    px = np.concatenate([np.clip(A[::-1], 0, 1), np.ones((TH, TEX, 1), np.float32)], 2)
    im.pixels.foreach_set(px.ravel())
    im.filepath_raw = os.path.join(OUTA, "coopersrow_atlas.png"); im.file_format = "PNG"; im.save()
    return im

def remap_uv(me):
    """r6: every UV is built in r5's 128-row space; the atlas has 160 rows (the new tile below r5's): v' = 1 - (1 - v) * 128/160"""
    for l in me.uv_layers[0].data: l.uv = (l.uv[0], 1.0 - (1.0 - l.uv[1]) * KV)

def tuv(tile, px, py):
    x0, y0, w, h = TILES[tile]
    return ((x0 + px) / TEX, 1 - (y0 + py) / TEX)

def texel(tile, r):
    x0, y0, w, h = TILES[tile]
    return tuv(tile, 1.5 + r.randrange(w - 3), 1.5 + r.randrange(h - 3))

# ---------- frame geometry ----------
PARTS = []
MAT = None

def new_obj(name, bm):
    bm.normal_update()
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = False
    ob = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(ob)
    ob.data.materials.append(MAT); PARTS.append(ob)
    return ob

# box timbers: bunker_r4's mapping (hewn strip v 0.75, end grain v 0.5 two rings, iron v 0.375), chamfers -> wear swatch
STRIP = {"hewn": 0.75, "end": 0.50, "iron": 0.375}
STRIPH = {"hewn": 32, "iron": 16}
def uv_box_face(f, uvl, kind, long_axis, seed):
    n = f.normal
    r = random.Random(seed * 7919 + f.index)
    if kind == "rivet" or max(abs(n[0]), abs(n[1]), abs(n[2])) < 0.98:
        uv = texel("weari" if kind in ("iron", "rivet") else "wearw", r)
        for l in f.loops: l[uvl].uv = uv
        return
    ax = max(range(3), key=lambda i: abs(n[i]))
    tang = [i for i in range(3) if i != ax]
    if kind != "iron" and ax == long_axis:
        k = seed % 2
        cs = [l.vert.co for l in f.loops]
        c = sum(cs, Vector()) / len(cs)
        ext = max(max(abs(v[tang[0]] - c[tang[0]]), abs(v[tang[1]] - c[tang[1]])) for v in cs) or 1
        for l in f.loops:
            a = (l.vert.co[tang[0]] - c[tang[0]]) / ext; b = (l.vert.co[tang[1]] - c[tang[1]]) / ext
            l[uvl].uv = ((k + 0.5 + a * 0.45) / 4, STRIP["end"] + (0.5 + b * 0.45) / 4)
        return
    ua = long_axis if long_axis in tang else tang[0]
    va = tang[1] if ua == tang[0] else tang[0]
    off = (seed * 0.37) % 1
    vs = [l.vert.co[va] for l in f.loops]
    vmin, span = min(vs), max(max(vs) - min(vs), 1e-4)
    hpx = STRIPH[kind]
    vscale = min(1.0, (hpx / DENS) / span)
    room = max(hpx / TEX - span * vscale * DENS / TEX * 0.94 - 0.012, 0)
    voff = ((seed * 0.618) % 1) * room
    for l in f.loops:
        u = l.vert.co[ua] * DENS / TEX + off
        v = STRIP[kind] + ((l.vert.co[va] - vmin) * vscale * DENS / TEX) * 0.94 + 0.0075 + voff
        l[uvl].uv = (u, v)

def timber(name, size, pos, kind="hewn", rot=(0, 0, 0), jitter=0.012, bevel=0.016):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts: v.co = Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2]))
    long_axis = max(range(3), key=lambda i: size[i])
    for v in bm.verts:
        for i in range(3):
            if i != long_axis: v.co[i] += rng.uniform(-jitter, jitter)
    if bevel > 0: bmesh.ops.bevel(bm, geom=bm.edges[:], offset=bevel, segments=1, affect="EDGES")
    bm.normal_update()
    uvl = bm.loops.layers.uv.verify()
    seed = rng.randrange(1000)
    for f in bm.faces: uv_box_face(f, uvl, kind, long_axis, seed + f.index % 2)
    bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Euler([math.radians(a) for a in rot]).to_matrix())
    bmesh.ops.translate(bm, verts=bm.verts, vec=Vector(pos))
    return new_obj(name, bm)

def iron(name, size, pos, rot=(0, 0, 0)):
    return timber(name, size, pos, kind="iron", rot=rot, jitter=0.0015, bevel=0)

def rivet(pos, normal, s=0.024, h=0.008):
    """square iron rivet head standing h off a face with this outward normal (a unit axis vector or a horizontal direction)"""
    n = Vector(normal).normalized()
    yaw = math.degrees(math.atan2(n.y, n.x)) if abs(n.z) < 0.5 else 0
    size = (h, s, s) if abs(n.z) < 0.5 else (s, s, h)
    p = Vector(pos) + n * (h / 2)
    timber("rivet", size, tuple(p), kind="rivet", rot=(0, 0, yaw), jitter=0, bevel=0)

def lerp_prof(prof, z):
    for (r0, h0), (r1, h1) in zip(prof, prof[1:]):
        if h0 <= z <= h1 + 1e-9 and h1 > h0: return r0 + (r1 - r0) * (z - h0) / (h1 - h0)
    return prof[-1][0] if z > prof[-1][1] else prof[0][0]

def vessel(vi):
    item, kind, rimz, prof_n, _nu = VESSELS[vi]
    x = xs[vi]; yc = ys[vi]
    h = rimz - DECK
    prof = [(r, f * h) for r, f in prof_n]
    clayish = kind in ("clay", "dclay", "jar", "pot", "crock", "amph")
    core = prof[:-2] + [(prof[-3][0], h)] if clayish else prof        # inner reference: without the rolled lip
    N = NSEG[kind]; T = WALLT[kind]
    phase = -math.pi / 2 - NW * math.pi / N                            # faces 0..NW-1 = the slot, centred on the front (-y)
    ang = [phase + 2 * math.pi * i / N for i in range(N + 1)]
    rin = lambda z: lerp_prof(core, z) - T
    rout = lambda z: lerp_prof(prof, z)
    wlo, whi = FLREL + 0.035, h - 0.13                                 # the slot, vessel-relative heights
    # profile rows: profile points, every ~0.08 m, the slot's ends
    zs = sorted(set([round(z, 5) for _r, z in prof] + [round(z, 5) for z in np.linspace(0, h, max(2, round(h / 0.08)) + 1)]
                    + [round(wlo, 5), round(whi, 5), round(FLREL, 5)]))
    zs = [z for z in zs if 0 <= z <= h + 1e-9]
    bm = bmesh.new(); uvl = bm.loops.layers.uv.verify()
    def P(r, a, z): return Vector((x + r * math.cos(a), yc + r * math.sin(a), DECK + z))
    def face(pts, uvs):
        try: f = bm.faces.new([bm.verts.new(p) for p in pts])
        except ValueError: return
        for l, uv in zip(f.loops, uvs): l[uvl].uv = uv
    r_ = random.Random(100 + vi)
    staves = kind in ("barrel", "half", "cask", "vat", "pail", "char")
    otile = {"vat": "hewn", "barrel": "dark", "half": "hewn", "cask": "hewn", "clay": "clay", "dclay": "dclay", "bark": "bark", "jar": "hclay",
             "pail": "hewn", "char": "char", "pot": "ironp", "crock": "rclay", "amph": "vclay", "basket": "root"}[kind]
    itile = {"vat": "dark", "barrel": "dark", "half": "dark", "cask": "dark", "clay": "dclay", "dclay": "dclay", "bark": "dark", "jar": "dclay",
             "pail": "dark", "char": "dark", "pot": "ironp", "crock": "dclay", "amph": "dclay", "basket": "dark"}[kind]
    in_slot = lambda i, z0, z1: i < NW and z0 >= wlo - 1e-6 and z1 <= whi + 1e-6
    for i in range(N):
        a0, a1 = ang[i], ang[i + 1]
        cu = r_.uniform(0.5, 128) if otile == "hewn" else r_.uniform(0.5, max(0.6, 32 - h * DENS - 0.5))
        top_edge = r_.random() < 0.5
        cu_in = r_.uniform(0.5, max(0.6, 32 - h * DENS - 0.5))
        def stave_uv(tile, cu_, z, arc, width):
            py = 0.5 + arc * DENS if top_edge else 32 - 0.5 - (width - arc) * DENS
            # round 4 fix: a 32 px tile (dark timber) holds the whole stave height; rounds 2-3 ran into the wear swatch at the top
            return tuv(tile, cu_ + z * (DENS if tile == "hewn" else min(DENS, 30.5 / h)), py)
        def col_uv(tile, cu_, z, arc):     # clay/bark: rings follow z
            # round 4 fix: kept inside the 32 px tile on tall vessels (rounds 2-3 ran past it at the foot of the pots)
            return tuv(tile, min(cu_ + arc * DENS, 31.5), 0.5 + (h - z) * min(DENS * 0.97, 30.5 / h))
        for k in range(len(zs) - 1):
            z0, z1 = zs[k], zs[k + 1]
            if in_slot(i, z0, z1): continue
            r0, r1 = rout(z0), rout(z1)
            if staves:
                c = 0.007
                d0, d1 = 0.012 / r0, 0.012 / r1
                cols = [(a0, -c), (a0 + d0, 0), (a1 - d0, 0), (a1, -c)]
                cols1 = [(a0, -c), (a0 + d1, 0), (a1 - d1, 0), (a1, -c)]
                for j in range(3):
                    pts = [P(r0 + cols[j][1], cols[j][0], z0), P(r0 + cols[j + 1][1], cols[j + 1][0], z0),
                           P(r1 + cols1[j + 1][1], cols1[j + 1][0], z1), P(r1 + cols1[j][1], cols1[j][0], z1)]
                    if j == 1:
                        w0, w1 = r0 * (a1 - a0), r1 * (a1 - a0)
                        uvs = [stave_uv(otile, cu, z0, d0 * r0, w0), stave_uv(otile, cu, z0, (a1 - d0 - a0) * r0, w0),
                               stave_uv(otile, cu, z1, (a1 - d1 - a0) * r1, w1), stave_uv(otile, cu, z1, d1 * r1, w1)]
                    else:
                        uvs = [texel("wearw", r_)] * 4
                    face(pts, uvs)
            else:
                pts = [P(r0, a0, z0), P(r0, a1, z0), P(r1, a1, z1), P(r1, a0, z1)]
                face(pts, [col_uv(otile, cu, z0, 0), col_uv(otile, cu, z0, r0 * (a1 - a0)),
                           col_uv(otile, cu, z1, r1 * (a1 - a0)), col_uv(otile, cu, z1, 0)])
            if z1 > FLREL + 1e-6:      # inner wall (seen from inside)
                zi0 = max(z0, FLREL)
                q0, q1 = rin(zi0), rin(z1)
                pts = [P(q0, a1, zi0), P(q0, a0, zi0), P(q1, a0, z1), P(q1, a1, z1)]
                if staves:
                    w0, w1 = q0 * (a1 - a0), q1 * (a1 - a0)
                    uvs = [stave_uv(itile, cu_in, zi0, w0 * 0.98, w0), stave_uv(itile, cu_in, zi0, 0.0, w0),
                           stave_uv(itile, cu_in, z1, 0.0, w1), stave_uv(itile, cu_in, z1, w1 * 0.98, w1)]
                else:
                    uvs = [col_uv(itile, cu_in, zi0, q0 * (a1 - a0)), col_uv(itile, cu_in, zi0, 0),
                           col_uv(itile, cu_in, z1, 0), col_uv(itile, cu_in, z1, q1 * (a1 - a0))]
                face(pts, uvs)
        # top of the wall: end grain (staves) / clay or bark (pots, tub)
        ro, ri = rout(h), rin(h)
        if staves:
            c = 0.007; d = 0.012 / ro
            pts = [P(ri, a0, h), P(ri, a1, h), P(ro - c, a1, h), P(ro, a1 - d, h), P(ro, a0 + d, h), P(ro - c, a0, h)][::-1]
            et = "end0" if r_.random() < 0.5 else "end1"; cx_, cy_ = r_.uniform(9, 23), r_.uniform(9, 23)
            mid = (P(ri, (a0 + a1) / 2, h) + P(ro, (a0 + a1) / 2, h)) / 2
            face(pts, [tuv(et, cx_ + (p.x - mid.x) * DENS, cy_ + (p.y - mid.y) * DENS) for p in pts])
        else:
            pts = [P(ri, a0, h), P(ri, a1, h), P(ro, a1, h), P(ro, a0, h)]
            uvs = [col_uv(otile, cu, h - (ro - ri), 0), col_uv(otile, cu, h - (ro - ri), ri * (a1 - a0)),
                   col_uv(otile, cu, h, ro * (a1 - a0)), col_uv(otile, cu, h, 0)]
            face(pts[::-1], uvs[::-1])
    # slot: cut ends (horizontal) and reveals (the neighbouring walls' cut sides)
    a0, a1 = ang[0], ang[NW]
    for zc, up in ((wlo, True), (whi, False)):
        ro, ri = rout(zc), rin(zc)
        for i in range(NW):
            b0, b1 = ang[i], ang[i + 1]
            pts = [P(ri, b0, zc), P(ri, b1, zc), P(ro, b1, zc), P(ro, b0, zc)]
            if up: pts = pts[::-1]                  # top of the part below the slot faces up, bottom of the part above down
            if staves:
                et = "end0" if r_.random() < 0.5 else "end1"
                mid = sum(pts, Vector()) / 4
                face(pts, [tuv(et, 16 + (p.x - mid.x) * DENS, 16 + (p.y - mid.y) * DENS) for p in pts])
            else:
                face(pts, [tuv(otile, 4 + (p.x - pts[0].x) * DENS * 0.7 + 8, 3 + abs(p.y - pts[0].y) * DENS) for p in pts])
    srows = [z for z in zs if wlo - 1e-6 <= z <= whi + 1e-6]
    for a, side in ((a0, 1), (a1, -1)):
        for z0, z1 in zip(srows, srows[1:]):
            pts = [P(rin(z0), a, z0), P(rout(z0), a, z0), P(rout(z1), a, z1), P(rin(z1), a, z1)]
            tile = "hewn" if otile == "hewn" else ("dark" if staves else otile)
            uvs = [tuv(tile, 4 + ((z0 if j in (0, 1) else z1) - wlo) * DENS * 0.9, 2 + (rout(z0) - rin(z0)) * DENS * (1 if j in (1, 2) else 0)) for j in range(4)]
            if side > 0: pts = [pts[1], pts[0], pts[3], pts[2]]; uvs = [uvs[1], uvs[0], uvs[3], uvs[2]]
            face(pts, uvs)
    # inner floor
    fr = rin(FLREL)
    pts = [P(fr, ang[i], FLREL) for i in range(N)]
    ft = "ironp" if kind == "pot" else ("dark" if not clayish else "dclay")
    face(pts, [tuv(ft, 16 + (p.x - x) * DENS * 0.6, 16 + (p.y - yc) * DENS * 0.6) for p in pts])
    ob = new_obj(f"vessel_{item}", bm)

    # ---- bands: iron hoops (barrels), root lashing + bent-wood rim (tub) ----
    def band(z0, z1, tile, out=HOOPOUT, inner_over_slot=True, name="hoop"):
        b = bmesh.new(); ul = b.loops.layers.uv.verify()
        bo = random.Random(rng.randrange(10 ** 6)).uniform(0, 128)
        def F(pts, uvs):
            f = b.faces.new([b.verts.new(p) for p in pts])
            for l, uv in zip(f.loops, uvs): l[ul].uv = uv
        circ = 0.0
        for i in range(N):
            c0, c1 = ang[i], ang[i + 1]
            r00, r01 = rout(z0) + out, rout(z1) + out
            arc = r00 * (c1 - c0)
            if tile in ("iron",):
                uvs = [tuv(tile, bo + circ * DENS, 14.5), tuv(tile, bo + (circ + arc) * DENS, 14.5),
                       tuv(tile, bo + (circ + arc) * DENS, 1.5), tuv(tile, bo + circ * DENS, 1.5)]
            elif tile == "hewn":
                uvs = [tuv(tile, bo + circ * DENS, 30.5), tuv(tile, bo + (circ + arc) * DENS, 30.5),
                       tuv(tile, bo + (circ + arc) * DENS, 30.5 - (z1 - z0) * DENS), tuv(tile, bo + circ * DENS, 30.5 - (z1 - z0) * DENS)]
            else:
                q = (circ * DENS) % 24
                uvs = [tuv(tile, q, 4 + (z1 - z0) * DENS), tuv(tile, q + arc * DENS, 4 + (z1 - z0) * DENS), tuv(tile, q + arc * DENS, 4), tuv(tile, q, 4)]
            circ += arc
            F([P(r00, c0, z0), P(r00, c1, z0), P(r01, c1, z1), P(r01, c0, z1)], uvs)
            wt = "weari" if tile == "iron" else "wearw"
            F([P(rout(z1), c0, z1), P(r01, c0, z1), P(r01, c1, z1), P(rout(z1), c1, z1)], [texel(wt, rng)] * 4)
            F([P(rout(z0), c1, z0), P(r00, c1, z0), P(r00, c0, z0), P(rout(z0), c0, z0)], [texel(wt, rng)] * 4)
            if i < NW and inner_over_slot and z0 >= wlo - 1e-6 and z1 <= whi + 1e-6:     # its inner side, over the slot
                F([P(rout(z0), c1, z0), P(rout(z0), c0, z0), P(rout(z1), c0, z1), P(rout(z1), c1, z1)], uvs[::-1])
        return new_obj(name, b)
    slot_q = lambda f: wlo + f * (whi - wlo)
    def slot_rivets(zc, out):
        for a in (a0 - 0.035 / rout(zc), a1 + 0.035 / rout(zc)):
            r = rout(zc) + out
            rivet((x + r * math.cos(a), yc + r * math.sin(a), DECK + zc), (math.cos(a), math.sin(a), 0), s=0.02, h=0.007)
    def gauge_bar(f):
        zc = slot_q(f)
        ro = rout(zc)
        half = ro * math.sin(NW * math.pi / N) + 0.045
        yb = yc - ro * math.cos(NW * math.pi / N) - 0.004
        iron("gauge", (2 * half, 0.012, 0.034), (x, yb - 0.006, DECK + zc))
        for sx in (-1, 1): rivet((x + sx * (half - 0.018), yb - 0.012, DECK + zc), (0, -1, 0), s=0.02, h=0.007)
    if staves:
        hw = 0.055
        for zc in (0.065, h - 0.075, slot_q(0.25), slot_q(0.75)):
            band(zc - hw / 2, zc + hw / 2, "iron")
        for zc in (slot_q(0.25), slot_q(0.75)): slot_rivets(zc, HOOPOUT)
        gauge_bar(0.5)
    else:
        for f in (0.25, 0.5, 0.75): gauge_bar(f)
    if kind == "jar":
        band(h - 0.135, h - 0.075, "root", out=0.012, name="lashing")      # the neck, under the rolled lip
    if kind == "basket":                                                    # r7: a hooped wicker basket: a foot ring and a bent-wood rim
        band(0.005, 0.07, "hewn", out=0.014, name="rim")
        band(h - 0.075, h, "hewn", out=0.02, name="rim")
    if kind == "pot":                                                       # r7: the cauldron's rolled iron rim hoop under the lip
        band(h - 0.10, h - 0.055, "iron", out=0.012, name="hoop")
    if kind == "bark":
        band(0.05, 0.11, "root", out=0.012, name="lashing")
        band(h - 0.125, h - 0.07, "root", out=0.012, name="lashing")
        band(h - 0.06, h, "hewn", out=0.02, name="rim")
    return {"item": item, "kind": kind, "x": x, "y": yc, "h": h, "rim": rimz, "prof": prof, "core": core, "N": N, "T": T, "ang": ang,
            "rin": rin, "rout": rout, "wlo": wlo, "whi": whi}

LABEL_CLIP = {}
def build_labels(VS):
    """r7: per vessel one spot on the deck's front zone at the vessel's own x: the front vessels' labels in the outer row, the back
    vessels' labels in the inner row (in front of the gap between two front vessels), planned in the layout (LAB_Y). position = the
    bottom centre of the item's rotated bounds on the deck (prefab space); rot_quat_xyzw = a turn about up, in the copies' convention.
    Every one of the 13 item models (Eitr: Resin's lump as its stand-in) is placed there at LABEL_LONG and checked against the frame."""
    docs = []
    R = Matrix.Rotation(math.radians(LABEL_YAW), 3, "Z")
    Rn = np.array(R)
    for vi, V in enumerate(VS):
        pos = Vector((V["x"], LAB_Y[vi], DECK + 0.004))      # the plank tops: DECK + at most 3 mm of jitter (their faces have no vertices mid-span)
        res = {}
        for it in ITEMS13:
            T = TEMPL[it]
            f = LABEL_LONG / (T["s"] * max(T["size"]))
            W = (T["V"] * f) @ Rn.T
            W = W + np.array([pos.x, pos.y, pos.z - float(W[:, 2].min())])
            hits = len(fbvh.overlap(BVHTree.FromPolygons([Vector(tuple(float(a) for a in w)) for w in W], T["tris"])))
            off = bool((np.abs(W[:, 1]) > D / 2).any() or (np.abs(W[:, 0]) > L / 2).any())
            res[it] = hits + (1000 if off else 0)
        LABEL_CLIP[V["item"]] = res
        eul, quat, err = rot_to_unity(R)
        docs.append({"compartment": vi, "position": [round(a, 4) for a in b2u_vec(pos)], "rot_quat_xyzw": quat, "fit_longest_m": LABEL_LONG})
        print("LABEL", json.dumps(docs[-1]), "row", "back" if vi in BACK else "front", "clip per item", {k: v for k, v in res.items() if v}, flush=True)
    return docs

def build_liquids(VS):
    """every vessel x every liquid item: a closed prism of height 1 from the floor point, the vessel's own face count and angles,
    its narrowest inside over the liquid's range 5 mm in, on the item's tiles; returns the anchors entries and the objects"""
    docs, obs = [], []
    for vi, V in enumerate(VS):
        N = V["N"]; ang = V["ang"]
        top_rel = V["h"] - LIQ_FREEBOARD
        r = min(V["rin"](z) for z in np.linspace(FLREL, top_rel, 40)) - LIQ_INSET
        floor = (V["x"], V["y"], FL + LIQ_FLOOR)
        top_y = DECK + top_rel
        me = None
        for it in LIQUID:
            bm = bmesh.new(); uvl = bm.loops.layers.uv.verify()
            bot = [bm.verts.new((r * math.cos(a), r * math.sin(a), 0.0)) for a in ang[:N]]
            top = [bm.verts.new((r * math.cos(a), r * math.sin(a), 1.0)) for a in ang[:N]]
            for i in range(N):
                j = (i + 1) % N
                f = bm.faces.new((bot[i], bot[j], top[j], top[i]))
                u0 = 0.5 + (i % 3) * 5
                for l, (pu, pv) in zip(f.loops, ((u0, 15.5), (u0 + 5, 15.5), (u0 + 5, 0.5), (u0, 0.5))): l[uvl].uv = tuv(it + "_side", pu, pv)
            f = bm.faces.new(top)
            for l, v in zip(f.loops, top): l[uvl].uv = tuv(it + "_top", 4 + v.co.x * DENS * 0.15, 8 + v.co.y * DENS * 0.3)
            f = bm.faces.new(bot[::-1])
            for l in f.loops: l[uvl].uv = tuv(it + "_side", 8, 8)
            bm.normal_update()
            name = f"Liquid_{vi}_{it}"
            me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
            for p in me.polygons: p.use_smooth = False
            ob = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(ob); ob.data.materials.append(MAT)
            obs.append((ob, name + ".obj"))
            docs.append({"compartment": vi, "item": it, "obj": name + ".obj", "floor": [round(a, 4) for a in b2u_vec(floor)],
                         "top_y": round(top_y, 4), "radius": round(r, 4), "sides": N})
        # clipping: the column at a few fills against the frame (the same prism for every item)
        tr = [(p.vertices[0], p.vertices[i], p.vertices[i + 1]) for p in me.polygons for i in range(1, len(p.vertices) - 1)]
        for fill in (0.05, 0.25, 0.5, 0.75, 1.0):
            pts = [Vector((floor[0] + v.co.x, floor[1] + v.co.y, floor[2] + v.co.z * (top_y - floor[2]) * fill)) for v in me.vertices]
            LIQ_CLIP.append((V["item"], fill, len(fbvh.overlap(BVHTree.FromPolygons(pts, tr)))))
        print("LIQUIDS vessel", vi, V["kind"], "radius", round(r, 4), "sides", N, "top_y", round(top_y, 3), "clip", LIQ_CLIP[-5:], flush=True)
    return docs, obs
LIQ_CLIP = []

def build_skid():
    hl = L / 2
    XE = hl - 0.07                                             # r6: the end sleepers/straps follow the length (r5: 1.92 of 2.06)
    for xsl in (-XE, -XE / 3, XE / 3, XE):                     # sleepers 0.14 x 0.10, the outer ones under the deck ends
        timber("sleeper", (0.14, D, SLEEPER_H), (xsl, 0, SLEEPER_H / 2), bevel=0.014, jitter=0.006)
    n = 5; w = D / n
    for k in range(n):                                         # deck planks 0.05 thick
        timber("plank", (L, w - 0.006, PLANK_T), (rng.uniform(-0.01, 0.01), -D / 2 + w / 2 + k * w, SLEEPER_H + PLANK_T / 2),
               bevel=0.010, jitter=0.003)
    for sx in (-1, 1):                                         # iron straps over the deck ends, folded down front and back
        xe = sx * XE                                           # over the end sleeper, folded down its ends to the ground
        iron("strap", (0.07, D, 0.006), (xe, 0, DECK + 0.003))
        for sy in (-1, 1):
            iron("strap", (0.07, 0.006, DECK - 0.01 + 0.009), (xe, sy * (D / 2 + 0.003), 0.01 + (DECK - 0.01 + 0.009) / 2))   # r7: 3 mm over the strap top, so the two top faces are not in one plane
            for zr_ in (0.05, DECK - 0.025): rivet((xe, sy * (D / 2 + 0.006), zr_), (0, sy, 0))
        for k in range(n): rivet((xe, -D / 2 + w / 2 + k * w, DECK + 0.006), (0, 0, 1), s=0.022, h=0.006)
    # back: two corner posts and a rail behind the vessels, iron brackets with rivets where they meet
    PH, PS = 0.80, 0.14
    yp = D / 2 - PS / 2
    for sx in (-1, 1):
        timber("post", (PS, PS, PH - DECK - 0.004), (sx * (hl - PS / 2), yp, DECK + 0.004 + (PH - DECK - 0.004) / 2), bevel=0.016, jitter=0.006)   # r7: 4 mm over the deck, not in the end strap's underside plane
    zr = 0.64; RH, RD = 0.12, 0.10
    timber("rail", (L - 2 * PS + 0.01, RD, RH), (0, yp + 0.01, zr), bevel=0.016, jitter=0.006)
    for sx in (-1, 1):
        xp = sx * (hl - PS / 2)
        yf = yp + 0.01 - RD / 2 - 0.003
        iron("bracket", (0.05, 0.006, 0.20), (xp - sx * 0.035, yf - 0.012, zr - 0.02))      # down the post
        iron("bracket", (0.20, 0.006, 0.05), (xp - sx * 0.14, yf + 0.0, zr))                 # along the rail
        rivet((xp - sx * 0.035, yf - 0.015, zr - 0.09), (0, -1, 0))
        rivet((xp - sx * 0.21, yf - 0.003, zr), (0, -1, 0))
        rivet((xp - sx * 0.035, yf - 0.015, zr + 0.05), (0, -1, 0))

def join(obs, name):
    bpy.ops.object.select_all(action="DESELECT")
    for o in obs: o.select_set(True)
    bpy.context.view_layer.objects.active = obs[0]
    bpy.ops.object.join(); ob = bpy.context.active_object; ob.name = name
    return ob

def tri_list(me):
    V = [v.co.copy() for v in me.vertices]
    T = [(p.vertices[0], p.vertices[i], p.vertices[i + 1]) for p in me.polygons for i in range(1, len(p.vertices) - 1)]
    return V, T

# ---------- items ----------
TEMPL = {}
def load_templates():
    for item, *_ in VESSELS:
        src = "Resin" if item == "Eitr" else item
        ob = load_item(src, anchor="center")[0]
        info = json.load(open(f"{ITEMS_DIR}/{src}/info.json"))
        bmin, bmax = Vector(info["bounds_min"]), Vector(info["bounds_max"])
        size = bmax - bmin
        s = LONGS[item] / max(size)
        ob.data.transform(Matrix.Diagonal((s, s, s, 1))); ob.data.update()
        ob.location = (0, 0, -50); ob.hide_render = True; ob.name = "templ_" + item
        V = np.array([tuple(v.co) for v in ob.data.vertices], np.float32)
        bm = bmesh.new(); bm.from_mesh(ob.data)
        hull = bmesh.ops.convex_hull(bm, input=bm.verts)
        planes = []
        for f in [g for g in hull["geom"] if isinstance(g, bmesh.types.BMFace)]:
            n = f.normal.copy(); planes.append((n.x, n.y, n.z, n.dot(f.verts[0].co)))
        hv = np.array(sorted({tuple(round(c, 5) for c in v.co) for v in hull["geom"] if isinstance(v, bmesh.types.BMVert)}), np.float32)
        bm.free()
        TEMPL[item] = {"obj": ob, "mesh": ob.data, "V": V, "s": float(s), "size": tuple(size), "center": tuple((bmin + bmax) / 2),
                       "planes": np.array(planes, np.float32), "hv": hv, "radius": float(np.linalg.norm(V, axis=1).max()),
                       "he": (V.max(0) - V.min(0)) / 2, "mid": (V.max(0) + V.min(0)) / 2, "src": src,
                       "tris": [(p.vertices[0], p.vertices[i], p.vertices[i + 1]) for p in ob.data.polygons for i in range(1, len(p.vertices) - 1)]}

def world_verts(item, M):
    Mn = np.array(M); return TEMPL[item]["V"] @ Mn[:3, :3].T + Mn[:3, 3]

def add_rb(ob, kind, shape, mass=1.0, damp=(0.25, 0.45)):
    for o in bpy.context.view_layer.objects: o.select_set(False)
    ob.select_set(True); bpy.context.view_layer.objects.active = ob
    bpy.ops.rigidbody.object_add(type=kind)
    rb = ob.rigid_body
    rb.collision_shape = shape; rb.friction = 0.75; rb.restitution = 0.0
    rb.use_margin = True; rb.collision_margin = MARGIN
    if shape == "MESH": rb.mesh_source = "BASE"
    if kind == "ACTIVE":
        rb.mass = mass; rb.linear_damping, rb.angular_damping = damp
        rb.use_deactivation = False

def rcol(V, z):
    """collider radius (polygon vertex radius) at world height z; straight up over the rim"""
    zr = min(max(z - DECK, FLREL), V["h"])
    return V["rin"](zr) - WALLGAP / math.cos(math.pi / V["N"])

def collider(V):
    N = V["N"]; ang = V["ang"]
    zs = sorted(set([FLREL + 0.004] + [z for _r, z in V["core"] if z > FLREL] + list(np.linspace(FLREL + 0.004, V["h"], 7))))
    rings = [(rcol(V, DECK + z), DECK + z) for z in zs] + [(rcol(V, DECK + V["h"]), DECK + V["h"] + 1.2)]
    bm = bmesh.new()
    R = [[bm.verts.new((V["x"] + r * math.cos(ang[i]), V["y"] + r * math.sin(ang[i]), z)) for i in range(N)] for r, z in rings]
    for a, b in zip(R, R[1:]):
        for i in range(N): bm.faces.new((a[i], a[(i + 1) % N], b[(i + 1) % N], b[i]))
    bm.faces.new(R[0][::-1])
    me = bpy.data.meshes.new("col"); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(f"col_{V['item']}", me); bpy.context.scene.collection.objects.link(ob)
    add_rb(ob, "PASSIVE", "MESH"); ob.hide_render = True
    return ob

def target(V, X, Y):
    r = np.hypot(X - V["x"], Y - V["y"])
    Rm = rcol(V, V["rim"])
    return np.minimum(V["rim"] - EDGE + CROWN * (Rm - r), V["rim"] + CAPOVER)

def surface(V, HV):
    Rb = max(rcol(V, DECK + z) for z in np.linspace(FLREL, V["h"], 20))
    n = int(math.ceil(2 * Rb / GRID))
    g = V["x"] - Rb + (np.arange(n) + 0.5) * GRID; gy = V["y"] - Rb + (np.arange(n) + 0.5) * GRID
    X, Y = np.meshgrid(g, gy, indexing="ij")
    H = np.full((n, n), FL, np.float64)
    if len(HV):
        ix = np.clip(((HV[:, 0] - (V["x"] - Rb)) / GRID).astype(int), 0, n - 1); iy = np.clip(((HV[:, 1] - V["y"] + Rb) / GRID).astype(int), 0, n - 1)
        np.maximum.at(H, (ix, iy), HV[:, 2])
        P = np.pad(H, 1, mode="edge")
        H = np.max([P[i:i + n, j:j + n] for i in range(3) for j in range(3)], axis=0)
    mouth = np.hypot(X - V["x"], Y - V["y"]) < rcol(V, V["rim"]) - 0.03
    return X, Y, H, target(V, X, Y), mouth

def check_copy(V, item, M):
    W = world_verts(item, M)
    r = np.hypot(W[:, 0] - V["x"], W[:, 1] - V["y"])
    rc = np.array([rcol(V, z) for z in W[:, 2]])                 # the collider's corner radius
    escaped = bool((r > rc + 0.004).any() or (W[:, 2] < FL - 0.006).any())
    # leaning on the invisible extension over the rim: a vertex over the rim within 4 mm of its faces
    lean = bool(((W[:, 2] > V["rim"] - 0.005) & (r > rcol(V, V["rim"]) * math.cos(math.pi / V["N"]) - 0.004)).any())
    clip = fbvh.overlap(BVHTree.FromPolygons([Vector(tuple(float(a) for a in w)) for w in W], TEMPL[item]["tris"]))
    return escaped, lean, bool(clip)

SIMLOG = {"vessels": {}, "frames": [], "retries": 0, "unsettled": 0, "resid": []}
def simulate_vessel(V):
    sc = bpy.context.scene
    rbw = sc.rigidbody_world
    coll = bpy.data.collections.new(f"rb_{V['item']}")
    rbw.collection = coll
    col = collider(V)
    home = V["item"]; item = SOLID.get(home, LUMP); T_ = TEMPL[item]; R = T_["radius"]     # round 5: Resin lumps in every vessel (r7: vials in the vial basket)
    HV = np.zeros((0, 3), np.float32)
    copies = []
    fails = 0; t0 = time.time()
    Rm = rcol(V, V["rim"])
    while len(copies) < CAP and fails < 6:
        X, Y, H, Tg, mouth = surface(V, HV)
        cover = float(((Tg - H)[mouth] < COVER_TOL).mean())
        if cover >= 0.92: break
        deficit = Tg - H
        placed = False
        # round 2: drop spots over the vessel's width at the heap's current level (the belly, not just the mouth), so big
        # lumps fill the floor and the belly before they pile up in the middle
        level = float(np.median(H[mouth]))
        rlev = min(rcol(V, z) for z in np.linspace(level, level + 2 * R, 6)) * math.cos(math.pi / V["N"])
        for attempt in range(6):
            inset = R * 0.55 + 0.01 + 0.015 * attempt
            rr = max(0.02, rlev - inset)
            best = None
            for _c in range(16):
                a = crng.uniform(0, math.tau); d = rr * math.sqrt(crng.random())
                px, py = V["x"] + d * math.cos(a), V["y"] + d * math.sin(a)
                i = min(max(int((px - X[0, 0] + GRID / 2) / GRID), 0), X.shape[0] - 1)
                j = min(max(int((py - Y[0, 0] + GRID / 2) / GRID), 0), X.shape[1] - 1)
                sc_ = -float(deficit[i, j]) + crng.uniform(0, 0.02 + 0.01 * attempt)
                if best is None or sc_ < best[0]: best = (sc_, px, py)
            _s, px, py = best
            m = (HV[:, 0] - px) ** 2 + (HV[:, 1] - py) ** 2 < (R + 0.06) ** 2 if len(HV) else None
            lt = float(HV[m, 2].max()) if m is not None and m.any() else FL
            ob = bpy.data.objects.new(f"c_{item}_{len(copies)}_{attempt}", T_["mesh"]); sc.collection.objects.link(ob)
            ob.rotation_euler = Euler((crng.uniform(0, math.tau), crng.uniform(0, math.tau), crng.uniform(0, math.tau)), "XYZ")
            ob.location = (px, py, lt + 0.02 + R)
            add_rb(ob, "ACTIVE", "CONVEX_HULL", mass=0.4)
            bpy.context.view_layer.update()
            sc.frame_set(1)
            prev = None; still = 0; f = 1; dp = dr = 0.0
            while f < 300:
                f += 1; sc.frame_set(f)
                cur = (ob.matrix_world.translation.copy(), ob.matrix_world.to_quaternion())
                if prev:
                    dp = (cur[0] - prev[0]).length; dr = cur[1].rotation_difference(prev[1]).angle
                    still = still + 1 if (dp < 2e-4 and dr < 4e-3 and f > 8) else 0
                    if still >= 3: break
                prev = cur
            M = ob.matrix_world.copy()
            esc, lean, clip = check_copy(V, item, M)
            # round 2: no towers (big lumps balanced on each other in the middle): nothing higher than the crown cap + 6 cm
            tall = float(world_verts(item, M)[:, 2].max()) > V["rim"] + CAPOVER + 0.06
            if esc or lean or clip or tall or still < 3:
                bpy.data.objects.remove(ob, do_unlink=True); SIMLOG["retries"] += 1
                if still < 3: SIMLOG["unsettled"] += 1
                continue
            SIMLOG["frames"].append(f); SIMLOG["resid"].append((round(dp * 1000, 3), round(dr, 4)))
            ob.rigid_body.type = "PASSIVE"
            ob.matrix_world = M
            bpy.context.view_layer.update()
            sc.frame_set(1)
            copies.append({"item": item, "M": M.copy(), "obj": ob})
            Mn = np.array(M)
            HV = np.concatenate([HV, (T_["hv"] @ Mn[:3, :3].T + Mn[:3, 3]).astype(np.float32)])
            placed = True
            break
        fails = 0 if placed else fails + 1
    X, Y, H, Tg, mouth = surface(V, HV)
    cover = float(((Tg - H)[mouth] < COVER_TOL).mean())
    SIMLOG["vessels"][home] = {"copies": len(copies), "cover_6cm": round(cover, 3), "peak": round(float(HV[:, 2].max()), 3) if len(HV) else None,
                               "rim": V["rim"], "seconds": round(time.time() - t0, 1)}
    print("VESSEL", home, json.dumps(SIMLOG["vessels"][home]), flush=True)
    bpy.data.objects.remove(col, do_unlink=True)
    return copies

# ---------- checks ----------
def interpenetration(cps):
    P = np.array([np.array(cp["M"])[:3, 3] for cp in cps]); R = np.array([TEMPL[cp["item"]]["radius"] for cp in cps])
    worst = 0.0; npairs = 0; over = []
    for i in range(len(cps)):
        d = np.linalg.norm(P - P[i], axis=1)
        for j in np.nonzero((d < R + R[i]) & (np.arange(len(cps)) > i))[0]:
            npairs += 1
            for a, b in ((i, int(j)), (int(j), i)):
                Ma, Mb = np.array(cps[a]["M"]), np.array(cps[b]["M"])
                Ta, Tb = TEMPL[cps[a]["item"]], TEMPL[cps[b]["item"]]
                x = Ta["hv"] @ Ma[:3, :3].T + Ma[:3, 3]
                xb = (x - Mb[:3, 3]) @ Mb[:3, :3]
                pl = Tb["planes"]
                m = float((pl[:, 3][None, :] - xb @ pl[:, :3].T).min(axis=1).max())
                if m > 0: over.append(m)
                worst = max(worst, m)
    return worst, npairs, over

# ---------- anchors (Unity prefab space: ux=-bx, uy=bz, uz=-by) ----------
CB2U = Matrix(((-1, 0, 0), (0, 0, 1), (0, -1, 0)))
def b2u_vec(v): return (-v[0], v[2], -v[1])
def rot_to_unity(R):
    Ru = CB2U @ R @ CB2U.transposed()
    q = Ru.to_quaternion()
    e = Ru.to_euler("ZXY")
    ex = Matrix.Rotation(e.x, 3, "X"); ey = Matrix.Rotation(e.y, 3, "Y"); ez = Matrix.Rotation(e.z, 3, "Z")
    err = max(abs(a - b) for ra, rb in zip((ey @ ex @ ez), Ru) for a, b in zip(ra, rb))
    return [round(math.degrees(e.x), 3), round(math.degrees(e.y), 3), round(math.degrees(e.z), 3)], [round(q.x, 5), round(q.y, 5), round(q.z, 5), round(q.w, 5)], err

def bounds_low(cp):
    M = np.array(cp["M"]); T = TEMPL[cp["item"]]
    c = M[:3, :3] @ T["mid"] + M[:3, 3]
    return float(c[2] - np.abs(M[2, :3]) @ T["he"])

def bounds_high(cp):
    M = np.array(cp["M"]); T = TEMPL[cp["item"]]
    c = M[:3, :3] @ T["mid"] + M[:3, 3]
    return float(c[2] + np.abs(M[2, :3]) @ T["he"])

def build_units(VS, seqs):
    """cut each vessel's copy sequence into its units (drop order), then interleave the 64 units by fill fraction"""
    units = []
    for vi, (V, seq) in enumerate(zip(VS, seqs)):
        nu = VESSELS[vi][4]; C = len(seq)
        if C < nu: print("WARNING fewer copies than units", V["item"], C, nu, flush=True)
        for k in range(nu):
            # round 2: unit 0 gets the first copy, the rest spread evenly over units 1..n-1 with the last unit taking the last copy
            # (with fewer copies than units the copy-less units fall in between, so the crown only shows at full)
            a = 0 if k == 0 else 1 + (k - 1) * (C - 1) // (nu - 1)
            b = 1 if k == 0 else 1 + k * (C - 1) // (nu - 1)
            cps = seq[a:b]
            units.append({"vessel": vi, "item": V["item"], "k": k, "frac": (k + 0.5) / nu + crng.uniform(-0.01, 0.01), "copies": cps})
    units.sort(key=lambda u: (u["frac"], u["vessel"]))
    for n, u in enumerate(units): u["index"] = n; u["step"] = n * 8 // NUNITS
    return units

def build_anchors(VS, units, frame_info, checks):
    allc = [cp for u in units for cp in u["copies"]]
    floor = min(bounds_low(cp) for cp in allc) - 0.002
    top = max(bounds_high(cp) for cp in allc)
    H0 = (floor + top) / 2
    maxerr = 0; out = []
    for u in units:
        V = VS[u["vessel"]]
        if u["copies"]:
            W = np.concatenate([world_verts(cp["item"], cp["M"]) for cp in u["copies"]])
        else:      # a unit without a copy (a vessel with fewer copies than units): the vessel's axis, its inner width
            rw = max(V["rin"](z) for z in np.linspace(FLREL, V["h"], 20)); W = np.array([[V["x"] - rw, V["y"], FL], [V["x"] + rw, V["y"], FL]])
        cx = float((W[:, 0].min() + W[:, 0].max()) / 2)
        c = Vector((cx, 0.0, H0))
        cps = []
        for cp in u["copies"]:
            M = cp["M"]; eul, quat, err = rot_to_unity(M.to_3x3().normalized()); maxerr = max(maxerr, err)
            T = TEMPL[cp["item"]]
            cps.append({"item": cp["item"], "offset": [round(a, 4) for a in b2u_vec(M.translation - c)], "euler": eul, "quat_xyzw": quat,
                        "scale": round(T["s"], 5), "fit_longest_m": LONGS[cp["item"]], "world_position": [round(a, 4) for a in b2u_vec(M.translation)]})
        rin_max = max(V["rin"](z) for z in np.linspace(FLREL, V["h"], 20))
        out.append({"index": u["index"], "step": u["step"], "kind": "heap_step", "item": u["item"], "compartment": u["vessel"],
                    "position": [round(a, 4) for a in b2u_vec(c)], "rotation": [0, 0, 0],
                    "box": [round(float(W[:, 0].max() - W[:, 0].min()), 4), round(2 * (H0 - floor), 4), round(1.4 * rin_max, 4)],
                    "layer": 0, "copies": cps})
    vessels = []
    for vi, V in enumerate(VS):
        us = [u for u in units if u["vessel"] == vi]
        rin_max = max(V["rin"](z) for z in np.linspace(FLREL, V["h"], 20))
        vessels.append({"compartment": vi, "item": V["item"], "vessel": V["kind"], "units": len(us), "copies": sum(len(u["copies"]) for u in us),
                        "copies_per_unit": [len(u["copies"]) for u in sorted(us, key=lambda u: u["k"])],
                        "row": "back" if vi in BACK else "front", "centre_x": round(-V["x"], 4), "centre_z_unity": round(-V["y"], 4), "outer_radius_m": round(VR[vi], 3), "rim_y": V["rim"], "floor_y": round(FL, 3), "inner_radius_max": round(rin_max, 4),
                        "slot_y": [round(DECK + V["wlo"], 3), round(DECK + V["whi"], 3)],
                        "heap_peak_y": SIMLOG["vessels"].get(V["item"], {}).get("peak"), "cover_6cm": SIMLOG["vessels"].get(V["item"], {}).get("cover_6cm")})
    items = {}
    for it, *_ in VESSELS:
        T = TEMPL[it]
        items[it] = {"model": T["src"], "bounds_size_unity": [round(T["size"][0], 4), round(T["size"][2], 4), round(T["size"][1], 4)],
                     "bounds_center_unity": [round(a, 4) for a in b2u_vec(T["center"])], "scale_used": round(T["s"], 5), "fit_longest_m": LONGS[it]}
    items["Eitr"]["note"] = ("Eitr's prefab uses a built-in Unity mesh the extractor cannot read: this vessel was laid out with Resin lumps at "
                             "Resin's size; the mod draws the game's own Eitr model with its longest side at fit_longest_m.")
    doc = {
        "store": "Cooper's Row round 7 (13 neutral vessels in a staggered front/back zigzag, 3.58 m wide: any vessel holds any of the 13; Sap, Tar, Guck, Ooze, Royal Jelly, Honey, Hateful Blood, Voidplasm and Ooze (Mork) as liquid or jelly columns, Resin, Charcoal Resin and Blob Vial as lumps/vials, Eitr as orbs (no liquid entry); a label copy of what is stored in front of each vessel; homes: 0 Tar barrel, 1 Resin clay pot, 2 Sap birch-bark tub, "
                 "3 Guck half barrel, 4 Eitr cask, 5 Ooze dark clay pot, 6 Royal Jelly honey jar, 7 Honey stave pail, 8 Charcoal Resin iron cauldron, 9 Ooze (Mork) charred tub, 10 Hateful Blood oxblood crock, 11 Voidplasm violet amphora, 12 Blob Vial wicker basket; even compartments stand in the front row, odd ones in the back row), one kind per vessel, heaped and crowned over the rim when full",
        "slots": NUNITS, "units": len(out), "steps": 8, "stack_per_unit": 1, "frame": frame_info,
        "space": "Unity prefab space, origin = skid footprint centre on the ground. Blender z-up/-y front -> Unity y-up/+z front: ux=-bx, uy=bz, uz=-by. "
                 "OBJ export (forward NEGATIVE_Z, up Y) writes (bx, bz, -by); Unity's importer negates x, same mapping.",
        "unit_semantics": "SETTLED: every copy has an explicit final pose from a rigid-body simulation (convex-hull items, friction 0.75, restitution 0, "
                          "damping 0.25/0.45), dropped one copy at a time onto the frozen earlier ones; each vessel's copy sequence is cut into its "
                          "units in drop order. Each copy: the item's bounds centre at unit.position + copy.offset (= copy.world_position), rotated by "
                          "copy.quat_xyzw (or copy.euler, Unity ZXY), longest side fit_longest_m. unit.position: x = centre of the unit's copies, "
                          "y = one height for all units, z = 0, so ByGroup tells the vessels apart by x only (left to right). unit.box: x = the copies' "
                          "width, y = from the lowest rotated-bounds corner of any copy in the store to the highest (the never-below-the-floor lift "
                          "leaves every settled copy alone), z = the chord a divider board may take inside the round vessel (70% of its inner diameter).",
        "fill_order": "units are listed in fill order (interleaved over the vessels); within a vessel its units fill bottom up. Show the first n "
                      "copies of a unit for a partial stack. Later copies rest on earlier ones, earlier ones never move. One item kind per vessel "
                      "(compartment = vessel 0-12, left to right as seen from the front; even = front row, odd = back row).",
        "liquids": LIQUIDS_DOC,
        "liquids_doc": "one entry per (vessel, liquid item): obj = a closed prism of height 1 (y 0..1) in this folder, drawn with the "
                       "frame's material as T(floor) * S(1, (top_y - floor.y) * fill, 1); floor = bottom centre of the liquid (prefab space), "
                       "top_y = its surface when full. An item with an entry for its vessel is drawn as liquid there, any other item as the "
                       "units' lumps.",
        "labels": LABELS_DOC,
        "labels_doc": "one per vessel: where ONE copy of whatever the vessel holds stands on the skid in front of it. position = the bottom "
                      "centre of the item's rotated bounds, on the deck (prefab space); rot_quat_xyzw = a turn about up in the copies' "
                      "convention; the item scaled so its longest side is fit_longest_m. Checked with all 13 item models (the 13 kinds of this store): 0 clipping; the labels stand in two staggered rows (front vessels' labels outer, back vessels' inner).",
        "lumps_doc": "every vessel's units carry Resin lumps (fit_longest_m 0.17, physics-settled as before; CharcoalResin is the same mesh, Eitr orbs are drawn at the same poses): the solid fallback for Resin or "
                     "any item without a liquid entry for that vessel; the Blob Vial basket (compartment 12) carries its own vials (fit_longest_m 0.21); each unit's item is its vessel's home. unit.position z is 0 for every unit (as r6): the copies' offsets carry each vessel's real depth.",
        "compartments": vessels, "items": items, "checks": checks, "rotation_convert_max_err": maxerr, "units_list": out}
    return doc

# ---------- coplanar check (round 2): faces that face the same way, lie in one plane and overlap z-fight in the game ----------
def _clip_area(subj, clipper):
    """Area of the intersection of two convex 2D polygons (Sutherland-Hodgman); both counter-clockwise or both clockwise."""
    def orient(poly): return sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1] for i in range(len(poly)))
    sg = 1.0 if orient(clipper) >= 0 else -1.0
    out = list(subj)
    for i in range(len(clipper)):
        a, b = clipper[i], clipper[(i + 1) % len(clipper)]
        inp, out = out, []
        if not inp: break
        def side(p): return sg * ((b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0]))
        for k in range(len(inp)):
            p, q = inp[k], inp[(k + 1) % len(inp)]
            sp, sq = side(p), side(q)
            if sp >= 0: out.append(p)
            if (sp >= 0) != (sq >= 0):
                t = sp / (sp - sq); out.append((p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])))
    return abs(orient(out)) / 2 if len(out) >= 3 else 0.0

def coplanar_overlaps(parts, tol=0.002, min_area=2e-7, facing=1):
    """parts: [(name, mesh)] in world space. Every pair of triangles that (facing=1) face the same way or (facing=-1) face
    each other, whose planes are within tol (m) of each other and whose projections overlap by more than min_area (m2).
    Returns [(area, name_a, name_b, centre, normal, gap)] sorted by area, largest first."""
    P, Tn, own = [], [], []
    for nm, me in parts:
        V = np.array([tuple(v.co) for v in me.vertices], float)
        for pl in me.polygons:
            vs = list(pl.vertices)
            for i in range(1, len(vs) - 1): P.append(V[[vs[0], vs[i], vs[i + 1]]]); own.append(nm)
    P = np.array(P)
    N = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0]); A = np.linalg.norm(N, axis=1) / 2
    ok = A > 1e-9
    N = N / np.where(ok, 2 * A, 1)[:, None]
    res = []
    for i in np.nonzero(ok)[0]:
        j = np.arange(i + 1, len(P))
        j = j[ok[j]]
        j = j[(N[j] @ N[i]) * facing > 0.9995]
        if not len(j): continue
        dist = np.einsum("jkc,c->jk", P[j] - P[i][0], N[i])
        near = (np.abs(dist).max(1) <= tol) if facing > 0 else (np.abs(dist).max(1) <= tol)
        for jj in j[near]:
            n = N[i]; ax = int(np.argmax(np.abs(n))); keep = [a for a in range(3) if a != ax]
            a2 = [tuple(q[keep]) for q in P[i]]; b2 = [tuple(q[keep]) for q in P[jj]]
            ar = _clip_area(a2, b2)
            if ar > min_area:
                gap = float(np.mean(np.einsum("kc,c->k", P[jj] - P[i][0], n)))
                res.append((ar, own[i], own[jj], ((P[i].mean(0) + P[jj].mean(0)) / 2).round(3).tolist(), n.round(2).tolist(), round(gap, 4)))
    res.sort(key=lambda r: -r[0])
    return res

def report_coplanar(parts, label):
    same = coplanar_overlaps(parts, facing=1)
    back = coplanar_overlaps(parts, facing=-1)
    print(f"COPLANAR {label}: same-facing overlapping pairs {len(same)} (0 expected); back-to-back pairs {len(back)} (hidden, informational)", flush=True)
    import re, collections
    agg = collections.OrderedDict()
    for r in same:
        key = (re.sub(r"\.\d+$", "", r[1]), re.sub(r"\.\d+$", "", r[2]), tuple(int(round(a)) for a in r[4]), round(r[5] * 1000, 1))
        e = agg.setdefault(key, [0, 0.0, r[3]]); e[0] += 1; e[1] += r[0]
    for key, (n, ar, c) in sorted(agg.items(), key=lambda kv: -kv[1][1]):
        print("  SAME", key[0], "x", key[1], "normal", key[2], "gap_mm", key[3], "pairs", n, f"area {ar * 1e4:.1f}cm2", "e.g. at", c, flush=True)
    agg = collections.OrderedDict()
    for r in back:
        key = (re.sub(r"\.\d+$", "", r[1]), re.sub(r"\.\d+$", "", r[2]), tuple(abs(int(round(a))) for a in r[4]))
        e = agg.setdefault(key, [0, 0.0, r[3]]); e[0] += 1; e[1] += r[0]
    for key, (n, ar, c) in sorted(agg.items(), key=lambda kv: -kv[1][1]):
        print("  BACK", key[0], "x", key[1], "axis", key[2], "pairs", n, f"area {ar * 1e4:.1f}cm2", "e.g. at", c, flush=True)
    return {"same_facing_overlaps": len(same), "back_to_back": len(back), "tolerance_mm": 2.0, "min_area_cm2": 0.002}

# ---------- scene + frame ----------
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
atlas = build_atlas()
MAT = bpy.data.materials.new("coopersrow"); MAT.use_nodes = True
_b = MAT.node_tree.nodes["Principled BSDF"]
_t = MAT.node_tree.nodes.new("ShaderNodeTexImage"); _t.image = atlas; _t.interpolation = "Closest"
MAT.node_tree.links.new(_t.outputs["Color"], _b.inputs["Base Color"])
_b.inputs["Roughness"].default_value = 1.0; _b.inputs["Specular IOR Level"].default_value = 0.0

build_skid()
VS = [vessel(i) for i in range(len(VESSELS))]
COP = report_coplanar([(o.name, o.data) for o in PARTS], "frame")
frame = join(list(PARTS), "CoopersRow")
FV_, FT_ = tri_list(frame.data)
frame_tris = len(FT_)
fbvh = BVHTree.FromPolygons(FV_, FT_, all_triangles=True)
FVn = np.array([tuple(v) for v in FV_])
frame_size = (float(FVn[:, 0].max() - FVn[:, 0].min()), float(FVn[:, 2].max()), float(FVn[:, 1].max() - FVn[:, 1].min()))
print("FRAME tris", frame_tris, "size W H D", [round(a, 3) for a in frame_size], "x range", round(FVn[:, 0].min(), 3), round(FVn[:, 0].max(), 3),
      "y range", round(FVn[:, 1].min(), 3), round(FVn[:, 1].max(), 3), flush=True)
for V in VS: print("VESSEL GEOM", V["item"], V["kind"], "x", round(V["x"], 3), "rim", V["rim"], "slot", round(DECK + V["wlo"], 3), round(DECK + V["whi"], 3),
                   "inner r at rim", round(V["rin"](V["h"]), 3))

load_templates()
sc.render.fps = FPS
bpy.ops.rigidbody.world_add()
rbw = sc.rigidbody_world
rbw.substeps_per_frame = 20; rbw.solver_iterations = 40; rbw.time_scale = 1.0
rbw.point_cache.frame_start = 1; rbw.point_cache.frame_end = 400
sc.frame_start = 1; sc.frame_end = 400
t0 = time.time()
seqs = [simulate_vessel(V) for V in VS]
LIQUIDS_DOC, LIQ_OBS = build_liquids(VS)
print("SIM seconds", round(time.time() - t0, 1), "retries", SIMLOG["retries"], "unsettled tries", SIMLOG["unsettled"], flush=True)
allc = [cp for s in seqs for cp in s]
_chk = [check_copy(V, cp["item"], cp["M"]) for V, sq in zip(VS, seqs) for cp in sq]
clip = [c for c in _chk if c[2]]; esc = [c for c in _chk if c[0]]; lean = [c for c in _chk if c[1]]
pen, npairs, over = interpenetration(allc)
print("CLIPPING", len(clip), "of", len(allc), "; ESCAPED", len(esc), "; LEANING over the rim", len(lean))
print("INTERPENETRATION max", round(pen * 1000, 2), "mm over", npairs, "near pairs;", len(over), "pairs penetrate, median",
      round(float(np.median(over)) * 1000, 2) if over else 0, "mm")
def _neutral_clip():
    """BlobVial (at the lumps' size) and CharcoalResin drawn at the Resin lump poses of every other vessel: copies touching the frame"""
    out = {}
    for it in ("BlobVial", "CharcoalResin"):
        T = TEMPL[it]; n = 0; tot = 0
        for V, sq in zip(VS, seqs):
            if SOLID.get(V["item"]) == it or not sq: continue
            for cp in sq:
                if cp["item"] != LUMP: continue
                Mn = np.array(cp["M"]); Vv = T["V"] * (LONGS[LUMP] / LONGS[it])      # drawn with its longest side = the lump's fit_longest_m
                W = Vv @ Mn[:3, :3].T + Mn[:3, 3]
                tot += 1
                n += bool(len(fbvh.overlap(BVHTree.FromPolygons([Vector(tuple(float(a) for a in w)) for w in W], T["tris"]))))
        out[it] = {"copies_checked": tot, "touching_frame": n}
    return out
NEUTRAL_CLIP = _neutral_clip()
print("NEUTRAL SOLIDS", NEUTRAL_CLIP, flush=True)
LABELS_DOC = build_labels(VS)
_lp = [(l["position"][0], l["position"][2]) for l in LABELS_DOC]
LABEL_MIN_GAP = min(math.hypot(a[0] - b[0], a[1] - b[1]) for i, a in enumerate(_lp) for b in _lp[i + 1:])
print("LABEL min centre distance", round(LABEL_MIN_GAP, 3), "(two labels need 2 x", LABEL_R, ")", flush=True)
units = build_units(VS, seqs)
tris_full = sum(len(TEMPL[cp["item"]]["tris"]) for cp in allc)
checks = {"clipping": len(clip), "label_clipping_per_vessel_and_item": LABEL_CLIP, "liquid_clipping": sum(c for _i, _f, c in LIQ_CLIP), "liquid_clipping_fills": [0.05, 0.25, 0.5, 0.75, 1.0], "label_min_centre_distance_m": round(LABEL_MIN_GAP, 3), "of_copies": len(allc), "escaped": len(esc), "leaning_over_rim": len(lean),
          "interpenetration_max_m": round(max(pen, 0.0), 5), "retries": SIMLOG["retries"],
          "contents_tris_full_ripped_models": tris_full,
          "coplanar_frame": COP, "neutral_solid_clipping": NEUTRAL_CLIP, "per_vessel": SIMLOG["vessels"]}
frame_info = {"obj": "CoopersRow.obj", "tris": frame_tris, "size_m": [round(a, 3) for a in frame_size], "atlas": "coopersrow_atlas.png 128x208",
              "atlas_sources": "rows 0-31 hewn timber, 32-63 x0-63 end grain, 64-79 iron: assets/bunker_r4; 32-63 x64-95 dark oiled timber, "
                               "x96-127 wear swatch: assets/metalpallet_r3; 80-111: clay, dark clay, birch bark, root lashing (r5); 112-127 liquid tiles (5); 128-159: honey-jar clay (r6); 160-191: iron cauldron, oxblood glaze, violet glaze, charred timber (new in r7); 192-207: four more liquid tiles (new in r7)"}
doc = build_anchors(VS, units, frame_info, checks)
print("UNITS", len(units), "copies per vessel", {V["item"]: len(s) for V, s in zip(VS, seqs)}, "rot err", doc["rotation_convert_max_err"])
json.dump(SIMLOG, open(os.path.join(OUT, "simlog.json"), "w"), indent=1)
for cp in allc: bpy.data.objects.remove(cp["obj"], do_unlink=True)
bpy.ops.rigidbody.world_remove()
# files: atlas (saved) -> OBJ -> anchors last (temp file + rename)
remap_uv(frame.data)
for lo, _fn in LIQ_OBS: remap_uv(lo.data)
bpy.ops.object.select_all(action="DESELECT"); frame.select_set(True); bpy.context.view_layer.objects.active = frame
bpy.ops.wm.obj_export(filepath=os.path.join(OUTA, "CoopersRow.obj"), export_selected_objects=True, export_materials=False,
                      export_triangulated_mesh=True, forward_axis="NEGATIVE_Z", up_axis="Y")
for lo, fn in LIQ_OBS:
    bpy.ops.object.select_all(action="DESELECT"); lo.select_set(True); bpy.context.view_layer.objects.active = lo
    bpy.ops.wm.obj_export(filepath=os.path.join(OUTA, fn), export_selected_objects=True, export_materials=False,
                          export_triangulated_mesh=True, forward_axis="NEGATIVE_Z", up_axis="Y")
tmp = os.path.join(OUT, "coopersrow_anchors.json.tmp")
json.dump(doc, open(tmp, "w"), indent=1)
os.replace(tmp, os.path.join(OUTA, "coopersrow_anchors.json"))
print("COOPERSROW frame tris", frame_tris, "copies", len(allc), "contents tris full", tris_full, flush=True)
if NORENDER:
    print("DONE"); sys.exit(0)

# ---------- renders: replayed from the EXPORTED files the mod's way ----------
for o in list(bpy.data.objects): bpy.data.objects.remove(o, do_unlink=True)
C = Matrix(((-1, 0, 0), (0, 0, 1), (0, -1, 0)))
def u2b_pos(p): return Vector((-p[0], -p[2], p[1]))
def u2b_rot(q): return C.transposed() @ Quaternion((q[3], q[0], q[1], q[2])).to_matrix() @ C

def atlas_mat(png, name):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    t = m.node_tree.nodes.new("ShaderNodeTexImage"); t.image = bpy.data.images.load(png); t.interpolation = "Closest"
    m.node_tree.links.new(t.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 1.0; b.inputs["Specular IOR Level"].default_value = 0.0
    return m

def import_frame(objpath, png, dx, dy):
    before = set(bpy.data.objects)
    bpy.ops.wm.obj_import(filepath=objpath, forward_axis="NEGATIVE_Z", up_axis="Y")
    new = [o for o in bpy.data.objects if o not in before]
    m = atlas_mat(png, os.path.basename(png) + str(dx))
    for o in new:
        o.data.materials.clear(); o.data.materials.append(m); o.location = (dx, dy, 0)
    return new

RAW = {}
def raw_mesh(item):
    if item not in RAW:
        src = "Resin" if item == "Eitr" else item
        ob = load_item(src, anchor="center")[0]
        info = json.load(open(f"{ITEMS_DIR}/{src}/info.json"))
        for m in ob.data.materials:
            b = m.node_tree.nodes.get("Principled BSDF")
            if not b: continue
            b.inputs["Specular IOR Level"].default_value = 0.25
            b.inputs["Roughness"].default_value = 0.35 if item in ("Tar", "Resin", "Guck", "Sap", "Eitr") else 0.7
        if item == "Eitr":       # stand-in look: Resin's lump tinted blue-violet, glowing a little (render only)
            me = ob.data.copy(); ob.data = me
            for i, m in enumerate(me.materials):
                m2 = m.copy(); me.materials[i] = m2
                for n in m2.node_tree.nodes:
                    if n.type == "MIX": n.inputs["B"].default_value = (0.30, 0.42, 1.0, 1)
                b = m2.node_tree.nodes.get("Principled BSDF")
                b.inputs["Emission Color"].default_value = (0.25, 0.35, 1.0, 1); b.inputs["Emission Strength"].default_value = 0.6
        if item == "Tar":
            for m in ob.data.materials:
                b = m.node_tree.nodes.get("Principled BSDF")
                if b: b.inputs["Base Color"].default_value = (0.03, 0.03, 0.035, 1)
        RAW[item] = (ob.data, np.array([tuple(v.co) for v in ob.data.vertices], np.float32), max(Vector(info["bounds_max"]) - Vector(info["bounds_min"])))
        bpy.data.objects.remove(ob, do_unlink=True)
    return RAW[item]

LIFTS = {}
def spawn_file(folder, obj, png, anchors, fill, dx, dy, tag, grouped=True):
    """a store replayed from its files: per group (vessel / compartment) its first fill x units in list order, a partial last unit,
    copies at unit.position + copy.offset, longest side fit_longest_m (or copy.scale), the mod's never-below-the-floor lift"""
    import_frame(os.path.join(folder, obj), os.path.join(folder, png), dx, dy)
    if fill <= 0: return
    d = json.load(open(os.path.join(folder, anchors)))
    for lq in d.get("liquids", []):          # the mod's liquid: T(floor) * S(1, (top_y - floor.y) * fill, 1)
        lob = import_frame(os.path.join(folder, lq["obj"]), os.path.join(folder, png), 0, 0)[0]
        bpy.ops.object.select_all(action="DESELECT"); lob.select_set(True); bpy.context.view_layer.objects.active = lob
        lob.location = (0, 0, 0); bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)   # the importer's axis turn into the mesh
        lob.location = u2b_pos(lq["floor"]) + Vector((dx, dy, 0))
        lob.scale = (1, 1, (lq["top_y"] - lq["floor"][1]) * fill)
    ul = d["units_list"]
    groups = {}
    for u in ul: groups.setdefault(json.dumps(u.get("compartment")), []).append(u)
    lifts = 0
    for g, us in groups.items():
        exact = fill * len(us); n = int(math.floor(exact + 1e-9)); part = exact - n
        for ui, u in enumerate(us[:n + (1 if part > 1e-6 else 0)]):
            cps = u["copies"] if ui < n else u["copies"][:max(1, math.ceil(len(u["copies"]) * part))]
            floor = u["position"][1] - u["box"][1] / 2
            for cp in cps:
                mesh, Vv, longest = raw_mesh(cp["item"])
                s = cp["fit_longest_m"] / longest if "fit_longest_m" in cp else cp["scale"]
                Rb = u2b_rot(cp["quat_xyzw"])
                p = u2b_pos([a + b for a, b in zip(u["position"], cp["offset"])])
                he = (Vv.max(0) - Vv.min(0)) / 2 * s; mid = (Vv.max(0) + Vv.min(0)) / 2 * s
                Rn = np.array(Rb)
                low = float((Rn @ mid)[2] + p.z - np.abs(Rn[2]) @ he)
                if low < floor - 1e-4: p.z += floor - low; lifts += 1
                ob = bpy.data.objects.new(f"{tag}_item", mesh); sc.collection.objects.link(ob)
                ob.matrix_world = Matrix.Translation(p + Vector((dx, dy, 0))) @ Rb.to_4x4() @ Matrix.Diagonal((s,) * 3 + (1,))
    LIFTS[f"{tag}@{fill}"] = lifts

pm = bpy.data.materials.new("plain"); pm.use_nodes = True
pm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.62, 0.60, 0.55, 1)
def post(x, y):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(x, y, 0.9)); p = bpy.context.active_object
    p.scale = (0.12, 0.12, 1.8); p.data.materials.append(pm); p.name = "post_1.8m"

def pack(folder):
    LQ = json.load(open(os.path.join(folder, "coopersrow_anchors.json")))
    return {"dir": folder, "png": os.path.join(folder, "coopersrow_atlas.png"), "LQ": LQ,
            "LIQS": {(e["compartment"], e["item"]): e for e in LQ["liquids"]}, "LABS": {e["compartment"]: e for e in LQ["labels"]}}
PK7 = pack(OUTA)
PKS = [("r5", pack(os.path.join(REPO, "assets", "coopersrow_r5"))), ("r6", pack(os.path.join(REPO, "assets", "coopersrow_r6"))), ("r7", PK7)]
_r8 = os.path.join(REPO, "assets", "coopersrow_r8")
if os.path.exists(os.path.join(_r8, "coopersrow_anchors.json")): PKS.append(("r8", pack(_r8)))

def liquid_obj(PK, e, fill, dx, dy):
    lob = import_frame(os.path.join(PK["dir"], e["obj"]), PK["png"], 0, 0)[0]
    bpy.ops.object.select_all(action="DESELECT"); lob.select_set(True); bpy.context.view_layer.objects.active = lob
    lob.location = (0, 0, 0); bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    lob.location = u2b_pos(e["floor"]) + Vector((dx, dy, 0))
    lob.scale = (1, 1, (e["top_y"] - e["floor"][1]) * fill)

def label_obj(item, lab, dx, dy):
    mesh, Vv, longest = raw_mesh(item)
    s_ = lab["fit_longest_m"] / longest
    Rb = u2b_rot(lab["rot_quat_xyzw"])
    low = float(((Vv * s_) @ np.array(Rb).T)[:, 2].min())
    p = u2b_pos(lab["position"]) + Vector((dx, dy, -low))
    ob = bpy.data.objects.new("label_" + item, mesh); sc.collection.objects.link(ob)
    ob.matrix_world = Matrix.Translation(p) @ Rb.to_4x4() @ Matrix.Diagonal((s_,) * 3 + (1,))

def spawn_r5(contents, dx, dy, tag, PK=None):
    """the store as the mod draws it: per vessel (item, fill): the label copy; a liquid column when the item has an entry for that
    vessel, else the vessel's first fill x units of lumps (in list order, a partial last unit) drawn with the item's own model"""
    PK = PK or PK7
    LIQS, LABS = PK["LIQS"], PK["LABS"]
    import_frame(os.path.join(PK["dir"], "CoopersRow.obj"), PK["png"], dx, dy)
    groups = {}
    for u in PK["LQ"]["units_list"]: groups.setdefault(u["compartment"], []).append(u)
    for c, (item, fill) in enumerate(contents):
        if not item or fill <= 0: continue
        label_obj(item, LABS[c], dx, dy)
        if (c, item) in LIQS: liquid_obj(PK, LIQS[(c, item)], fill, dx, dy); continue
        us = groups[c]; exact = fill * len(us); n = int(math.floor(exact + 1e-9)); part = exact - n
        for ui, u in enumerate(us[:n + (1 if part > 1e-6 else 0)]):
            cps = u["copies"] if ui < n else u["copies"][:max(1, math.ceil(len(u["copies"]) * part))]
            for cp in cps:
                mesh, Vv, longest = raw_mesh(item)
                s_ = cp["fit_longest_m"] / longest
                Rb = u2b_rot(cp["quat_xyzw"])
                p = u2b_pos([a + b for a, b in zip(u["position"], cp["offset"])])
                ob = bpy.data.objects.new(f"{tag}_item", mesh); sc.collection.objects.link(ob)
                ob.matrix_world = Matrix.Translation(p + Vector((dx, dy, 0))) @ Rb.to_4x4() @ Matrix.Diagonal((s_,) * 3 + (1,))

def homes(PK): return [c["item"] for c in PK["LQ"]["compartments"]]
FULL7 = [(it, 1.0) for it in homes(PK7)]
ROWS = {"full": 0.0, "half": 16.0, "fam": 60.0, "cmp": 90.0, "mix": 34.0}
spawn_r5(FULL7, 0.0, ROWS["full"], "mf")
spawn_r5([(it, 0.5) for it in homes(PK7)], 0.0, ROWS["half"], "mh")
# a mixed state: every vessel shows a different fill, a few holding an item that is not its home (neutral vessels)
_mixed = [("Tar", 1.0), ("Eitr", 0.6), ("Resin", 0.3), ("Honey", 0.8), ("Guck", 0.8), ("BlobVial", 0.5), ("RoyalJelly", 0.7), ("Resin", 1.0),
          ("CharcoalResin", 0.9), ("OozeMork", 0.4), ("HatefulBlood", 0.75), ("Voidplasm", 0.55), ("BlobVial", 1.0)]
spawn_r5(_mixed, 0.0, ROWS["mix"], "mx")
post(2.2, ROWS["full"] + 0.2)
# family: r7 full beside r6 full and bunker_r4 (same scale)
spawn_r5(FULL7, 0.0, ROWS["fam"], "fam")
_p6 = dict(PKS)["r6"]; spawn_r5(homes(_p6) and [(it, 1.0) for it in homes(_p6)], 4.35, ROWS["fam"], "fam6", _p6)
import_frame(os.path.join(REPO, "assets", "bunker_r4", "Bunker.obj"), os.path.join(REPO, "assets", "bunker_r4", "bunker_atlas.png"), -4.4, ROWS["fam"] + 0.5)
# compare: r5, r6, r7 (and r8 if it exists), all full, one line at the same scale
CMP_X = []
_cx = 0.0
for nm, PK in PKS:
    w = PK["LQ"]["frame"]["size_m"][0]; CMP_X.append((nm, _cx + w / 2, w)); _cx += w + 0.9
_off = _cx / 2 - 0.45
for (nm, cx, w), (_n, PK) in zip(CMP_X, PKS):
    spawn_r5([(it, 1.0) for it in homes(PK)], cx - _off, ROWS["cmp"], "cmp" + nm, PK)
print("COMPARE", CMP_X, flush=True)

world = bpy.data.worlds.new("w"); sc.world = world; world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.42, 0.45, 0.5, 1)
world.node_tree.nodes["Background"].inputs[1].default_value = 0.9
sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN")); sun.data.energy = 3.2
sun.rotation_euler = (math.radians(50), 0, math.radians(35)); sc.collection.objects.link(sun)
bpy.ops.mesh.primitive_plane_add(size=300, location=(0, 40, 0))
gm = bpy.data.materials.new("ground"); gm.use_nodes = True
gm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.16, 0.14, 0.11, 1)
bpy.context.active_object.data.materials.append(gm)
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam); sc.camera = cam
sc.render.engine = "BLENDER_EEVEE_NEXT"
sc.view_settings.view_transform = "Standard"
EYE = 1.75
YM = ys[7]
XH = xs[7]
VIEWS = {  # name: (yaw deg, horizontal distance, eye height, target, lens, size)
    "full34": (-30, 5.0, EYE, (0.0, ROWS["full"], 0.5), 35, None),
    "fullstanding": (0, 3.4, EYE, (0.0, ROWS["full"], 0.55), 30, None),
    "half34": (-30, 5.0, EYE, (0.0, ROWS["half"], 0.5), 35, None),
    "mixedstanding": (0, 3.4, EYE, (0.0, ROWS["mix"], 0.55), 30, None),
    "top": ("top", 0, 0, (0.0, ROWS["full"], 0.0), 0, None),
    "tophalf": ("top", 0, 0, (0.0, ROWS["half"], 0.0), 0, None),
    "close": (-18, 2.3, 1.45, (XH, ROWS["full"], 0.5), 32, None),
    "backview": (160, 4.2, 1.7, (0.0, ROWS["full"], 0.5), 32, None),
    "family": (-8, 15.0, 3.0, (0.0, ROWS["fam"] + 0.4, 0.8), 30, None),
    "compare": (-12, 19.5, 2.2, (0.0, ROWS["cmp"] + 0.4, 0.75), 30, (2400, 700)),
}
for vn, (yaw, dist, hgt, tgt, lens, size) in VIEWS.items():
    if VIEWSEL and vn not in VIEWSEL: continue
    sc.render.resolution_x, sc.render.resolution_y = size or ((1000, 562) if QUICK else (1600, 900))
    t = Vector(tgt)
    if yaw == "top":
        cam.data.type = "ORTHO"; cam.data.ortho_scale = 4.3
        cam.location = t + Vector((0, 0, 8)); cam.rotation_euler = (0, 0, 0)
    else:
        cam.data.type = "PERSP"
        cam.location = t + Vector((math.sin(math.radians(yaw)) * dist, -math.cos(math.radians(yaw)) * dist, hgt - t.z))
        cam.rotation_euler = (t - cam.location).to_track_quat("-Z", "Y").to_euler(); cam.data.lens = lens
    sc.render.filepath = os.path.join(OUT, f"coopersrow7-{vn}.png")
    bpy.ops.render.render(write_still=True)
    print("RENDER", vn, flush=True)
print("DONE")
