"""Bomb Crate, round 1 (prototype, Joost 24 Oct): a store for bombs only, one straw-bedded compartment per bomb kind, in a
sturdy iron-cornered crate with a lid propped open and warning paint. Fletcher's Barrels r2 keeps its own bomb crate; this is
the separate bomb store that came out of "Still being worked on" in SPEC.md. New files only: nothing is wired into the mod.
Run: blender -b -P bombcrate_r1.py -- [--out DIR] [--rip DIR] [--quick] [--views a,b] [--no-render] [--frame-only] [--pack-only] [--cell M] [--per N]
Writes into assets/bombcrate_r1/: BombCrate.obj (frame only, forward -Z, up Y, triangulated, no materials), bombcrate_atlas.png
(128x128, point filtered) and bombcrate_anchors.json (written last, temp + rename: the mod live-reloads).
Reuses fletcher_r2.py for the item maths (the mod's placement: place_u, world, K3/B3) and its straw bed, stave and hoop pieces.

THE BOMBS (every item prefab whose name starts with Bomb, read from the game files with UnityPy, bundle c4210710, Valheim 1.0.20,
and checked against the Jotunn item list https://valheim-modding.github.io/Jotunn/data/objects/item-list.html). Twelve, all
ObjectDB items, all stack 50, weight 0.3: BombBile (Bile Bomb), BombLava (Basalt Bomb), BombOoze (Ooze Bomb), BombSmoke (Smoke
Bomb), BombDynamite (Ember Charge), BombSiege (Explosive Payload: a Material, catapult ammunition, 0.86 x 1.2 x 1.2 m at true
size), and six Blob Bombs: BombBlob_Frost, _Lava, _Morkhalla (Pulp), _Poison, _PoisonElite, _Tar (glass vials, 0.29 x 0.46 x
0.28 m). No bomb among the modded items (Player.log "Added item": ValheimArmory and the rest add arrows, bolts, weapons, no
bombs; the logged "Item model" lines for bombs are these twelve). StaffClusterbomb and DvergerStaffFire_clusterbomb are staffs.
Item bounds as the mod measures them (ItemVisual: every LOD0 mesh renderer's local AABB in prefab root space, turned half about
up, times root scale 1): reproduced to 4 decimals for BombBile, BombLava, BombDynamite and the blob vials against Player.log, so
MODB below holds for the six I could not check in the log. The models were ripped with ValheimRip/scripts/items_extract.extract.
The six vials share two meshes (Frost has its own, the other five are one mesh with other textures), so the checks run on the
eight different shapes and the report lists all twelve prefabs.

SIZE. Bombs at fit_longest_m 0.22 like Fletcher's crate (0.66x bile, 0.83x lava, 0.48x a vial): one layout holds any bomb kind,
so a kind that fills its compartment can take an empty one without a copy touching another or the frame (every shape checked).

FRAME 4.19 W x 1.39 D x 0.76 H (1.51 D x 1.28 H with the lids open; Blender x, y, z, -y = front), 7 x 2 compartments, 0.52 x 0.52
inside, rim 0.30 over the floor; the back row's floor is 0.20 higher so both rows show:
  base      six skids, eight deck planks along x (deck top 0.145), four-board floors (front 0.185, back 0.385)
  walls     front wall, mid wall (one plank pair from the deck to the back rim, so the back row's front face stands 0.20 over the
            front rim), back wall, two end walls (low front half, high back half): 0.05 planks in two courses; 12 dividers 0.045
  posts     four 0.13 corner posts with iron bands flush with the bounds (front 0.56, back 0.76), riveted corner plates, iron straps
            on the front and back faces at every divider
  lids      two 2 m lids hinged on the back wall, held open at 105 degrees by iron stays: the open face carries the warning paint
            (a skull on one, a flame on the other, hazard stripes along the top edge, exclamation signs); battens and strap hinges
            on the other face. They cover the back row only (hinged at the back rim, the free end rests on the mid wall).
  paint     every compartment: a painted slab on the rim and a band on its front face, in the kind's colour (anchors 'band')
  bucket    the seventh front place is no compartment: a hooped bucket of sand with a bail, as an explosives store would have one
Compartments (group key 'compartment', left to right seen from the front): back row 0 BombBile, 1 BombLava, 2 BombOoze,
3 BombSmoke, 4 BombDynamite, 5 BombSiege, 6 spare (no home: any bomb kind); front row 7 BombBlob_Frost, 8 _Lava, 9 _Morkhalla,
10 _Poison, 11 _PoisonElite, 12 _Tar. Units 13 x 3 = 39 (five rows of eight, 40 slots), 3 bombs per unit, 9 per compartment:
dropped one at a time and settled (each drop tries 30 spots and spins and keeps the one that ends lowest), so the heap fills the
floor first, then rises 0.18 m over the rim when full (the tallest copy). Tried and dropped:
4 per unit (12 bombs) makes towers 0.33 over the rim; 0.54 inside gave a heap that read half full (9 bombs, 0.13 over).
Atlas 128x128 point: the Metal Pallet r3 atlas (hewn timber v 96-127, end grain v 64-95, iron v 0-31, plank v 48-63) with v 32-47
repainted: straw (u 0-31), hemp (u 32-63), 16 paint swatches of 4 x 4 px (u 64-127, v 32-35 fresh, v 36-39 worn), and eight 8 x 8
warning and material tiles (u 64-127, v 40-47: hazard stripes, skull, flame, exclamation, sand).
"""
import os, sys, math, json, random, hashlib, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.append(HERE)
import numpy as np
import bpy, bmesh
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
import metalrack_r1 as base
from metalrack_r1 import (box, join, tris, tri_list, export_obj, write_json_atomic, make_material, setup_scene, references,
                          lights_and_render, argv, arg, TW, TH)
import fletcher_r2 as F
import load_item as LI

ASSETS = os.path.normpath(os.path.join(HERE, "..", "assets"))
OUTA = os.path.join(ASSETS, "bombcrate_r1")
SCR = "C:/Users/joost/AppData/Local/Temp/claude/C--Users-joost--pai/5e4bc60b-cdfe-4638-8e29-2e507fa13cf9/scratchpad/bombcrate_r1"
OUT = arg("--out", SCR)
RIP = arg("--rip", os.path.join(SCR, "rip"))
rng = random.Random(41)
F.ITEMS_DIR = RIP                          # all twelve models come from the rip folder
F.RIP2 = RIP

# ---------- the bombs (game files): ItemVisual bounds (centre, size) in the mod's item space ----------
MODB = {
    "BombBile": ([-0.0016, 0.0261, -0.0043], [0.3069, 0.3339, 0.2994]),
    "BombLava": ([-0.001, 0.0697, -0.0278], [0.2356, 0.2503, 0.2647]),
    "BombOoze": ([-0.0236, 0.0665, 0.0044], [0.2542, 0.3016, 0.2787]),
    "BombSmoke": ([-0.0185, 0.0579, -0.0278], [0.2928, 0.2079, 0.2931]),
    "BombSiege": ([-0.0017, 0.1912, 0.0116], [0.8591, 1.2153, 1.2211]),
    "BombDynamite": ([-0.0006, 0.0181, 0.0044], [0.1687, 0.2596, 0.1776]),
    "BombBlob_Frost": ([-0.001, 0.231, -0.0065], [0.286, 0.4605, 0.2812]),
    "BombBlob_Lava": ([-0.001, 0.231, -0.0065], [0.286, 0.4605, 0.2812]),
    "BombBlob_Morkhalla": ([-0.001, 0.231, -0.0065], [0.286, 0.4605, 0.2812]),
    "BombBlob_Poison": ([-0.001, 0.231, -0.0065], [0.286, 0.4605, 0.2812]),
    "BombBlob_PoisonElite": ([-0.001, 0.231, -0.0065], [0.286, 0.4605, 0.2812]),
    "BombBlob_Tar": ([-0.001, 0.231, -0.0065], [0.286, 0.4605, 0.2812]),
}
ITEM_NAMES = {"BombBile": "Bile Bomb", "BombLava": "Basalt Bomb", "BombOoze": "Ooze Bomb", "BombSmoke": "Smoke Bomb",
              "BombDynamite": "Ember Charge", "BombSiege": "Explosive Payload", "BombBlob_Frost": "Blob Bomb: Frost",
              "BombBlob_Lava": "Blob Bomb: Lava", "BombBlob_Morkhalla": "Blob Bomb: Pulp", "BombBlob_Poison": "Blob Bomb: Poison",
              "BombBlob_PoisonElite": "Blob Bomb: Elite Poison", "BombBlob_Tar": "Blob Bomb: Tar"}
ALL = list(MODB)
SHAPES = ["BombBile", "BombLava", "BombOoze", "BombSmoke", "BombSiege", "BombDynamite", "BombBlob_Frost", "BombBlob_Lava"]
for k, v in MODB.items(): F.MODB[k] = v
F.FAM["bomb"] = SHAPES                      # the shapes the packing tests every copy against
LONG = F.LONG["bomb"]                       # 0.22

# ---------- the compartments ----------
# (group, home prefab or None, paint swatch, row, column); paint names below
COMPARTMENTS = [(0, "BombBile", 0, "back", 0), (1, "BombLava", 1, "back", 1), (2, "BombOoze", 2, "back", 2), (3, "BombSmoke", 3, "back", 3),
                (4, "BombDynamite", 4, "back", 4), (5, "BombSiege", 5, "back", 5), (6, None, 6, "back", 6),
                (7, "BombBlob_Frost", 7, "front", 0), (8, "BombBlob_Lava", 8, "front", 1), (9, "BombBlob_Morkhalla", 9, "front", 2),
                (10, "BombBlob_Poison", 10, "front", 3), (11, "BombBlob_PoisonElite", 11, "front", 4), (12, "BombBlob_Tar", 12, "front", 5)]
PAINTS = [(0.58, 0.58, 0.18), (0.27, 0.29, 0.33), (0.66, 0.58, 0.36), (0.62, 0.62, 0.60), (0.55, 0.20, 0.10), (0.52, 0.28, 0.12),
          (0.74, 0.72, 0.64), (0.42, 0.60, 0.70), (0.85, 0.42, 0.10), (0.43, 0.40, 0.18), (0.28, 0.55, 0.22), (0.40, 0.24, 0.50),
          (0.10, 0.09, 0.08), (0.80, 0.66, 0.12), (0.62, 0.14, 0.10), (0.72, 0.70, 0.62)]
PAINT_NAMES = ["bile yellow-green", "basalt slate", "ooze cream", "smoke ash", "ember red", "payload rust", "spare chalk", "frost blue",
               "magma orange", "pulp olive", "poison green", "elite violet", "tar black", "hazard yellow", "warning red", "bone white"]
NCOL = 7
N_UNITS, PER_UNIT = 3, int(arg("--per", 3))                    # units per compartment, copies per unit (9 bombs when full)

# ---------- dimensions (Blender: x right, -y front, z up) ----------
CELL, DV, MW, WT = float(arg("--cell", 0.52)), 0.045, 0.05, 0.05
IW = NCOL * CELL + (NCOL - 1) * DV           # 4.05
HIW = IW / 2
HID = (2 * CELL + MW) / 2                    # 0.565
PS, INS = 0.13, 0.004
BX, BY = HIW + INS + PS + INS, HID + INS + PS + INS          # bounds half sizes (bands flush)
SK_H, SK_W, DT = 0.10, 0.14, 0.045
DECK = SK_H + DT                             # 0.145
FT = 0.04                                    # floor boards
FF = DECK + FT                               # 0.185 front floor top
STEP = 0.20
FB = FF + STEP                               # 0.385 back floor top
RIMH = 0.30
RF, RB = FF + RIMH, FB + RIMH                # rims 0.485, 0.685
PEAK = 0.034                                 # straw peaks over the floor
FZ = {"front": FF + PEAK, "back": FB + PEAK}
KISS, EMB, FE, RV = 0.002, 0.0015, 0.008, 0.005
CX = [-HIW + CELL / 2 + i * (CELL + DV) for i in range(NCOL)]
CY = {"front": -(MW / 2 + CELL / 2), "back": MW / 2 + CELL / 2}
PIVOT = (HID + WT, RB)                       # lid hinge line (y, z)
LID_W, LID_D, LID_T, LID_OPEN = HIW - 0.02, 0.62, 0.05, -105.0

# ---------- atlas ----------
def build_atlas():
    src = bpy.data.images.load(os.path.join(ASSETS, "metalpallet_r3", "metalpallet_atlas.png"))
    px = np.array(src.pixels[:], np.float32).reshape(TH, TW, 4)
    img = px[..., :3].copy()
    nr = np.random.default_rng(37)
    x = np.arange(32)[None, :].repeat(16, 0).astype(np.float32)
    y = np.arange(16)[:, None].repeat(32, 1).astype(np.float32)
    t = 0.5 + 0.5 * np.sin(y * 2.6 + 0.9 * np.sin(x * 0.45 + y))
    t = t * 0.55 + nr.random((16, 32)) * 0.35
    t += (nr.random((16, 32)) < 0.06) * 0.4
    img[32:48, 0:32] = F.STRAW * (1 - np.clip(t, 0, 1)[..., None]) + F.STRAW_D * np.clip(t, 0, 1)[..., None]
    t = 0.5 + 0.5 * np.sin((x + y * 1.4) * 1.1)
    t = np.clip(t * 0.7 + nr.random((16, 32)) * 0.25, 0, 1)
    img[32:48, 32:64] = F.HEMP * (1 - t[..., None]) + F.HEMP_D * t[..., None]
    img[32:48, 64:128] = F.WOOD_L * 0.6
    for row, wear in ((0, 0.04), (1, 0.16)):                       # paint swatches, 4 x 4 px
        for k, c in enumerate(PAINTS):
            c = np.array(c, np.float32)
            blk = c * (0.86 + 0.14 * nr.random((4, 4)))[..., None]
            blk[[0, 3], :] *= 0.80; blk[:, [0, 3]] *= 0.80
            worn = nr.random((4, 4)) < wear
            blk[worn] = blk[worn] * 0.45 + F.WOOD_L * 0.55
            img[32 + 4 * row:36 + 4 * row, 64 + 4 * k:68 + 4 * k] = blk
    def tile(k, rows, cols_map, noise=0.10):
        out = np.zeros((8, 8, 3), np.float32)
        for r, line in enumerate(rows):
            for c, ch in enumerate(line):
                out[r, c] = np.array(cols_map[ch], np.float32)
        out *= (1 - noise + noise * 2 * nr.random((8, 8)))[..., None]
        img[40:48, 64 + 8 * k:72 + 8 * k] = out[::-1]               # rows are written top to bottom, v grows upwards
    Y, K, W, R, O = (0.80, 0.66, 0.12), (0.10, 0.09, 0.08), (0.74, 0.70, 0.56), (0.62, 0.14, 0.10), (0.85, 0.42, 0.10)
    tile(0, ["xxoo..xx", "xoo..xxo", "oo..xxoo", "o..xxoo.", "..xxoo..", ".xxoo..x", "xxoo..xx", "xoo..xxo"], {"x": Y, "o": K, ".": Y})
    tile(1, ["..wwww..", ".wwwwww.", ".w.ww.w.", ".wwwwww.", "..wwww..", "..wwww..", "..w.w.w.", "........"], {"w": W, ".": K})
    tile(2, ["...r....", "...rr...", "..rrr...", ".rrrrr..", ".rrrrrr.", ".rrorrr.", ".rrooro.", "..rrrr.."], {"r": R, "o": O, ".": W})
    tile(3, ["yyyyyyyy", "yykkkkyy", "yyykkyyy", "yyykkyyy", "yyykkyyy", "yyyyyyyy", "yyykkyyy", "yyyyyyyy"], {"y": Y, "k": K})
    tile(6, ["ssssssss"] * 8, {"s": (0.62, 0.54, 0.36)}, noise=0.22)
    tile(7, ["rrrrrrrr"] * 8, {"r": R})
    im = bpy.data.images.new("bombcrate_atlas", TW, TH, alpha=False)
    im.pixels.foreach_set(np.concatenate([np.clip(img, 0, 1), np.ones((TH, TW, 1), np.float32)], 2).ravel())
    return im

def my_uv(f, kind, long_axis, seed):
    if kind.startswith("paint"):
        k = int(kind[5:]); r = random.Random(seed * 31 + f.index)
        F.planar(f, 64 + 4 * k + r.randrange(2) + 0.5, 32 + r.randrange(2) + 0.5, 1.5, 1.5, dens=60); return
    if kind.startswith("warn"):
        k = int(kind[4:]); F.planar(f, 64 + 8 * k + 0.5, 40.5, 7, 7, dens=60); return
    F.my_uv(f, kind, long_axis, seed)

# ---------- frame pieces ----------
def part(name, size, pos, kind="plank", jitter=0.001, bevel=0.006, rot=(0, 0, 0)):
    return box(name, size, pos, kind=kind, jitter=jitter, bevel=bevel, rot=rot)

def xspan(a, b): return (a + b) / 2, abs(b - a)

def wall_x(y0, y1, z0, z1, courses, name="wall"):
    """A wall along x between the end walls (x +-(HIW + KISS)): `courses` planks stacked from z0 to z1."""
    h = (z1 - z0) / courses
    for c in range(courses):
        part(name, (2 * (HIW + INS + KISS), y1 - y0, h - 0.004), (0, (y0 + y1) / 2, z0 + h * (c + 0.5)), jitter=0.001, bevel=0.006)

def build_frame():
    # ---- base: skids front to back, deck planks along x ----
    for x in [sg * (HIW - 0.10 - 0.74 * i) for i in range(3) for sg in (-1, 1)]:
        box("skid", (SK_W, 2 * BY, SK_H + KISS), (x, 0, (SK_H + KISS) / 2), jitter=0.003, bevel=0.014)
        for sg in (-1, 1):
            F.plate_y(x - 0.05, x + 0.05, 0.012, SK_H - 0.012, sg * BY, sg, rivets=[(x, SK_H / 2)])
    nb, gap = 8, 0.007
    bw = (2 * BY - (nb - 1) * gap) / nb
    for i in range(nb):
        box("deck", (2 * (HIW + INS) + 2 * KISS, bw, DT), (0, -BY + bw / 2 + i * (bw + gap), SK_H + DT / 2), kind="plank", jitter=0.0, bevel=0.008)
    # ---- corner posts with iron bands flush with the bounds ----
    PXc, PYc = HIW + INS + PS / 2, HID + INS + PS / 2
    for sx in (-1, 1):
        for sy, h, bands in ((-1, 0.56, [(0.02, 0.08), (0.30, 0.08), (0.456, 0.10)]), (1, 0.76, [(0.02, 0.08), (0.40, 0.08), (0.656, 0.10)])):
            box("post", (PS, PS, h), (sx * PXc, sy * PYc, h / 2), jitter=0.002, bevel=0.012)
            for z0, bh in bands:
                box("band", (PS + 2 * INS, PS + 2 * INS, bh), (sx * PXc, sy * PYc, z0 + bh / 2), kind="iron", jitter=0, bevel=0)
    # ---- floors: four boards per row; the back row stands on two hidden bearers ----
    for k in range(4):
        w = (HID - MW / 2) / 4
        for sgn, z0, z1 in ((-1, DECK, FF), (1, FB - FT, FB)):
            yc = sgn * (MW / 2 + w * (k + 0.5))
            part("floor", (2 * HIW + 2 * KISS, w - 0.004, z1 - z0 + KISS), (0, yc, (z0 + z1) / 2 - KISS / 2), kind="plank", jitter=0, bevel=0.004)
    for yb in (0.18, 0.42):
        box("bearer", (2 * HIW - 0.1, 0.10, STEP - FT + 2 * KISS), (0, yb, (DECK + FB - FT) / 2), jitter=0.002, bevel=0.01)
    # ---- walls: front, mid (one plank pair up to the back rim), back; end walls low in front, high behind ----
    wall_x(-HID - WT, -HID, DECK - KISS, RF, 2, "front")
    wall_x(-MW / 2, MW / 2, DECK - KISS, RB, 2, "mid")
    wall_x(HID, HID + WT, DECK - KISS, RB, 2, "back")
    for sx in (-1, 1):
        for y0, y1, top in ((-HID - INS - KISS, 0.0, RF - 0.003), (0.0, HID + INS + KISS, RB - 0.003)):
            h = (top - (DECK - KISS)) / 2
            for c in range(2):
                part("end", (WT, y1 - y0, h - 0.004), (sx * (HIW + WT / 2), (y0 + y1) / 2, DECK - KISS + h * (c + 0.5)), jitter=0.001, bevel=0.006)
    # ---- dividers (x boundaries between the seven columns), one per boundary and row ----
    for i in range(NCOL - 1):
        xd = -HIW + (i + 1) * CELL + i * DV + DV / 2
        for row, (y0, y1, zf, zt) in {"front": (-HID, -MW / 2, FF, RF), "back": (MW / 2, HID, FB, RB)}.items():
            part("div", (DV, y1 - y0 + 2 * KISS, zt - zf + KISS), (xd, (y0 + y1) / 2, (zf + zt) / 2 - KISS / 2), jitter=0.001, bevel=0.006)
    # ---- iron: corner plates on the end walls and the front and back faces, straps at every divider, rim straps ----
    for sx in (-1, 1):
        xo = sx * (HIW + WT)
        for (y0, y1, z0, z1) in ((-HID, -HID + 0.17, 0.20, RF - 0.03), (HID - 0.17, HID, 0.20, RB - 0.04), (-0.085, 0.085, 0.30, 0.46)):
            F.plate_x(y0, y1, z0, z1, xo, sx, rivets=[((y0 + y1) / 2 + dy, zz) for dy in (-0.045, 0.045) for zz in (z0 + 0.05, z1 - 0.05)])
    for i in range(NCOL - 1):
        xd = -HIW + (i + 1) * CELL + i * DV + DV / 2
        F.plate_y(xd - 0.03, xd + 0.03, FF + 0.02, RF - 0.03, -HID - WT, -1, rivets=[(xd, FF + 0.06), (xd, RF - 0.07)])
        F.plate_y(xd - 0.03, xd + 0.03, DECK + 0.06, RB - 0.04, HID + WT, 1, rivets=[(xd, DECK + 0.10), (xd, RB - 0.08)])
    for sgn, yf, zr in ((-1, -HID - WT, RF), (1, HID + WT, RB)):          # a strap along each outer rim, in three runs
        for xa, xb in ((-HIW + 0.04, -0.69), (-0.64, 0.64), (0.69, HIW - 0.04)):
            xm, L = xspan(xa, xb)
            box("rimstrap", (L, 0.034, 0.008), (xm, sgn * (HID + WT / 2), zr + 0.004 - EMB), kind="iron", jitter=0, bevel=0.002)
    # ---- paint: per compartment a slab on the rim and a band on the front face ----
    for g, home, pk, row, col in COMPARTMENTS:
        cx = CX[col]
        if row == "front":
            box("rimpaint", (CELL - 0.10, 0.030, 0.005), (cx, -HID - WT / 2, RF + 0.0065 + 0.0025), kind=f"paint{pk}", jitter=0, bevel=0)
            box("facepaint", (CELL - 0.16, 0.006, 0.075), (cx, -HID - WT - 0.003 + EMB, FF + 0.12), kind=f"paint{pk}", jitter=0, bevel=0)
        else:
            box("rimpaint", (CELL - 0.10, 0.030, 0.005), (cx, 0, RB + 0.0065 + 0.0025 - 0.004), kind=f"paint{pk}", jitter=0, bevel=0)
            box("facepaint", (CELL - 0.16, 0.006, 0.075), (cx, -MW / 2 - 0.003 + EMB, RF + 0.105), kind=f"paint{pk}", jitter=0, bevel=0)
        # the stack's straw bed
        F.straw_bed(cx - CELL / 2 + 0.003, cx + CELL / 2 - 0.003, CY[row] - CELL / 2 + 0.003, CY[row] + CELL / 2 - 0.003,
                    FF if row == "front" else FB, FZ[row])
    # ---- warning plates: exclamation on the front posts, skulls and flames on the end walls ----
    for sx in (-1, 1):
        box("sign", (0.11, 0.004, 0.11), (sx * PXc, -(HID + INS + PS) - 0.002 + EMB, 0.24), kind="warn3", jitter=0, bevel=0)
        box("sign", (0.20, 0.004, 0.20), (sx * (HIW + WT + 0.002 - EMB), 0.25, 0.50), kind=("warn1" if sx < 0 else "warn2"), jitter=0, bevel=0, rot=(0, 0, 90))
        box("sign", (0.11, 0.004, 0.11), (sx * (HIW + WT + 0.002 - EMB), -0.30, 0.30), kind="warn3", jitter=0, bevel=0, rot=(0, 0, 90))
    bucket()
    lids()

def bucket():
    """The seventh front place: a hooped bucket of sand with a bail (not a compartment)."""
    cx, cy = CX[6], CY["front"]
    apo = 0.20
    F.DECK = FF                              # fletcher's stave ring stands on F.DECK: here the floor boards
    F.stave_ring(cx, cy, apo, 0.28)
    F.DECK = DECK
    for z0, z1 in ((0.04, 0.09), (0.19, 0.24)):
        F.ring("hoop", cx, cy, F.NST, apo + 0.001, F.HOOP_T, FF + z0, FF + z1, "iron")
    sand_mound(cx, cy, apo - F.BAR_T - 0.002, FF + 0.215, 0.075)
    r = apo + 0.01
    pts = [(cx + r * math.cos(math.pi * (1 - k / 8)), FF + 0.28 + r * math.sin(math.pi * (1 - k / 8))) for k in range(9)]
    for a, b in zip(pts[:-1], pts[1:]):
        base.strap("bail", a, b, "xz", cy, width=0.016, thick=0.016)

def sand_mound(cx, cy, R, z, h, rings=(0.04, 0.08, 0.12, 0.155), sectors=24):
    pr = random.Random(5)
    P = [(cx, cy, z + h)]
    for i, r in enumerate(list(rings) + [R]):
        for k in range(sectors):
            a = 2 * math.pi * (k + 0.5 * (i % 2)) / sectors
            P.append((cx + r * math.cos(a), cy + r * math.sin(a), z + h * max(0.0, 1 - (r / R) ** 2) + 0.0))
    T = [(0, 1 + k, 1 + (k + 1) % sectors) for k in range(sectors)]
    for i in range(len(rings)):
        a0, b0 = 1 + i * sectors, 1 + (i + 1) * sectors
        for k in range(sectors):
            k1 = (k + 1) % sectors
            T.append((a0 + k, b0 + k, a0 + k1)); T.append((a0 + k1, b0 + k, b0 + k1))
    bm = bmesh.new(); uvl = bm.loops.layers.uv.verify()
    vs = [bm.verts.new(p) for p in P]
    for t in T:
        f = bm.faces.new([vs[i] for i in t]); f.normal_update()
        if f.normal.z < 0: f.normal_flip()
        u0, v0 = 112 + pr.randrange(5), 40 + pr.randrange(5)
        for l, (du, dv) in zip(f.loops, ((0, 0), (3, 0), (1.5, 3))): l[uvl].uv = ((u0 + du) / TW, (v0 + dv) / TH)
    return F.mesh_part("sand", bm)

def lids():
    """Two lids hinged on the back wall, open at 105 degrees (leaning back), held by iron stays at their outer ends."""
    phi = math.radians(LID_OPEN)
    cs, sn = math.cos(phi), math.sin(phi)
    def to_world(x, ly, lz): return (x, PIVOT[0] + ly * cs - lz * sn, PIVOT[1] + ly * sn + lz * cs)
    M = Matrix.Translation((0, PIVOT[0], PIVOT[1])) @ Matrix.Rotation(phi, 4, "X")
    for side in (-1, 1):
        n0 = len(base.PARTS)
        xa, xb = (-LID_W, -0.012) if side < 0 else (0.012, LID_W)
        xc, w = (xa + xb) / 2, xb - xa
        npl = 5
        pw = (w - (npl - 1) * 0.004) / npl
        for i in range(npl):
            part("lid", (pw, LID_D, LID_T), (xa + pw / 2 + i * (pw + 0.004), -LID_D / 2, LID_T / 2), jitter=0.001, bevel=0.005)
        for ly in (-0.12, -0.50):                                   # battens on the outer face
            part("batten", (w - 0.08, 0.09, 0.04), (xc, ly, LID_T + 0.02 - 0.006), kind="hewn", jitter=0.002, bevel=0.01)
        for hx in (xa + 0.25, xc, xb - 0.25):                       # strap hinges: straps along the lid, riveted
            box("hinge", (0.05, 0.30, 0.008), (hx, -0.15, LID_T + 0.004 - EMB), kind="iron", jitter=0, bevel=0.002)
            for ry in (-0.06, -0.24): F.rivet(hx, ry, LID_T + 0.008 - EMB + RV / 2, "z")
        # warning paint on the face that looks at the viewer when open (local z < 0): skull or flame, exclamation signs, hazard stripes
        em = "warn1" if side < 0 else "warn2"
        box("emblem", (0.32, 0.32, 0.006), (xc, -0.31, -(0.003 - EMB)), kind=em, jitter=0, bevel=0)
        for ex in (xa + 0.20, xb - 0.20):
            box("sign", (0.17, 0.17, 0.006), (ex, -0.31, -(0.003 - EMB)), kind="warn3", jitter=0, bevel=0)
        for k in range(int(w / 0.14)):
            hxk = xa + 0.07 + k * 0.14
            box("hazard", (0.14, 0.07, 0.006), (hxk, -LID_D + 0.05, -(0.003 - EMB)), kind="warn0", jitter=0, bevel=0)
            box("hazard", (0.14, 0.07, 0.006), (hxk, -0.045, -(0.003 - EMB)), kind="warn0", jitter=0, bevel=0)
        for ob in base.PARTS[n0:]:
            ob.data.transform(M); ob.data.update()
        # iron stay at the outer end: from the lid's end face down to a bracket block on the back post
        xs = side * (LID_W + 0.0035)
        a = to_world(xs, -0.50, LID_T / 2)
        bz, by_ = RB - 0.07, HID + WT + 0.04
        base.strap("stay", (a[1], a[2]), (by_, bz), "yz", xs, width=0.04, thick=0.006)
        box("bracket", (0.020, 0.09, 0.09), (side * (HIW + INS - 0.010), by_, bz), kind="iron", jitter=0, bevel=0.002)

# ---------- items: placement, packing ----------
def pack_heap(ax, az, n, seed, k_cand=30):
    """n bombs in one compartment (Unity holder space, floor = the straw peaks at y 0): dropped one by one and settled. Each drop
    tries k_cand random spots and spins and keeps the one that ends lowest (lowering it until a lower bomb or the floor is
    touched), tested for every one of the eight shapes at once, so the heap fills the floor first, then the hollows, then rises."""
    rnd = random.Random(seed)
    kinds = SHAPES
    placed = []
    def clear(Ws):
        for k in kinds:
            Wv = Ws[k]
            if (np.abs(Wv[:, 0]) > ax - 0.004).any() or (np.abs(Wv[:, 1]) > az - 0.004).any() or Wv[:, 2].min() < -1e-4: return None
        mine = {}
        for k in kinds:
            Wv = Ws[k]; lo, hi = Wv.min(0), Wv.max(0); bv = F.bvh(k, Wv)
            for _, _, other in placed:
                olo, ohi, obv = other[k][2], other[k][3], other[k][1]
                if (lo <= ohi).all() and (olo <= hi).all() and bv.overlap(obv): return None
            mine[k] = (Wv, bv, lo, hi)
        return mine
    def shifted(Ws, dz): return {k: Wv + np.array([0, 0, dz]) for k, Wv in Ws.items()}
    for j in range(n):
        best = None
        for _ in range(k_cand):
            cx = rnd.uniform(-ax + 0.09, ax - 0.09); cz = rnd.uniform(-az + 0.09, az - 0.09)
            R = F.Rlean(rnd.uniform(0, 2 * math.pi), math.radians(rnd.uniform(0, 10))) @ F.Ry(rnd.uniform(0, 2 * math.pi))
            off = np.array([-cx, 0.0, -cz])
            c = F.copy_dict("bomb", off, R)
            Ws = {k: F.world(k, F.place_u((0, 0, 0), c, k)) for k in kinds}
            need = max(0.001 - Ws[k][:, 2].min() for k in kinds)
            Ws = shifted(Ws, need)
            if clear(shifted(Ws, 0.60)) is None: continue
            lift = 0.60
            while lift > 0.0:
                nxt = max(lift - 0.02, 0.0)
                if clear(shifted(Ws, nxt)) is None: break
                lift = nxt
            if lift > 0:
                lo_bad = max(lift - 0.02, 0.0); st = lift
                while st - 0.004 >= lo_bad - 1e-9 and clear(shifted(Ws, st - 0.004)) is not None: st -= 0.004
                lift = st
            final = need + lift
            if best is None or final < best[0]: best = (final, off, R, lift, Ws)
        if best is None:
            print("PACK bomb: no spot for bomb", j, flush=True); break
        final, off, R, lift, Ws = best
        mine = clear(shifted(Ws, lift))
        off = off.copy(); off[1] = final
        placed.append((off, R, mine))
    top = max(float(max(o[2][k][3][2] for k in kinds)) for o in placed)
    print(f"PACK bomb: {len(placed)} copies, top {top:.3f} over the straw peaks", flush=True)
    return [(p[0], p[1]) for p in placed], top

def get_layout(ax, az, n, seed):
    key = hashlib.md5(json.dumps([ax, az, n, seed, SHAPES, LONG, sorted(MODB.items())], sort_keys=True).encode()).hexdigest()[:10]
    path = os.path.join(SCR, f"layout_{key}.json")
    if os.path.exists(path):
        d = json.load(open(path)); print("PACK bomb: layout from", path, flush=True)
        return [(np.array(o), np.array(R)) for o, R in d["copies"]], d["top"]
    lay, top = pack_heap(ax, az, n, seed)
    json.dump({"copies": [(o.tolist(), R.tolist()) for o, R in lay], "top": top}, open(path, "w"))
    return lay, top

def make_units(lay):
    units = []
    for g, home, pk, row, col in COMPARTMENTS:
        bx, by = CX[col], CY[row]
        Rh = F.Ry(math.radians(90 * ((g * 3 + col) % 4)))
        cu = np.array([-bx, FZ[row], -by])
        abs_copies = [(cu + Rh @ off, Rh @ R) for off, R in lay]
        for k in range(N_UNITS):
            mine = abs_copies[k * PER_UNIT:(k + 1) * PER_UNIT]
            if not mine: continue
            P = np.array([o for o, _ in mine])
            upos = np.array([P[:, 0].mean(), FZ[row], P[:, 2].mean()])
            u = {"index": len(units), "compartment": g, "holder": "compartment", "kind": "bomb", "step": k, "paint": PAINT_NAMES[pk],
                 "position": [round(float(a), 5) for a in upos], "rotation": [0.0, 0.0, 0.0],
                 "box": [round(float(np.ptp(P[:, 0])) + 0.06, 3), F.LONG["bomb"], round(float(np.ptp(P[:, 2])) + 0.06, 3)]}
            if home: u["item"] = home
            else: u["example_item"] = "BombBile"
            u["copies"] = [F.copy_dict("bomb", o - upos, R) for o, R in mine]
            units.append(u)
    return units

# ---------- checks ----------
def unit_worlds(u, name): return [F.world(name, F.place_u(u["position"], c, name)) for c in u["copies"]]

def run_checks(units, frame):
    V, T = tri_list(frame.data)
    fbvh = BVHTree.FromPolygons(V, T, all_triangles=True)
    res = {}
    for k in ALL:
        clip, over, n = 0, 0, 0
        for g, *_ in COMPARTMENTS:
            Ws = [w for u in units if u["compartment"] == g for w in unit_worlds(u, k)]
            B = [F.bvh(k, w) for w in Ws]
            n += len(Ws)
            clip += sum(1 for b in B if fbvh.overlap(b))
            for i in range(len(B)):
                for j in range(i + 1, len(B)):
                    if B[i].overlap(B[j]): over += 1
        res[k] = {"copies": n, "frame_clipping": clip, "copy_overlaps": over}
    print("CHECK", json.dumps(res), flush=True)
    return res

def cross_check(units, fill, frame):
    """fill: compartment -> kind. Every copy against the frame and against every copy of every other compartment."""
    V, T = tri_list(frame.data)
    fbvh = BVHTree.FromPolygons(V, T, all_triangles=True)
    items = []
    for u in units:
        k = fill.get(u["compartment"])
        if not k: continue
        for w in unit_worlds(u, k): items.append((u["compartment"], k, w, F.bvh(k, w), w.min(0), w.max(0)))
    clip = sum(1 for it in items if fbvh.overlap(it[3]))
    cross = 0
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            a, b = items[i], items[j]
            if a[0] == b[0] or not ((a[4] <= b[5]).all() and (b[4] <= a[5]).all()): continue
            if a[3].overlap(b[3]): cross += 1
    top = max(float(it[2][:, 2].max()) for it in items) if items else 0.0
    return {"copies": len(items), "frame_clipping": clip, "between_compartments": cross, "contents_top_z": round(top, 3)}

# ---------- main ----------
if __name__ == "__main__":
    t0 = time.time()
    os.makedirs(OUTA, exist_ok=True); os.makedirs(OUT, exist_ok=True)
    setup_scene()
    atlas = build_atlas()
    base.MAT = make_material("bombcrate", atlas)
    base.PARTS.clear()
    base.uv_face = my_uv
    for k in ALL: F.load_tpl(k)
    print("VISIBLE", {k: len(t["T"]) for k, t in F.TPL.items()}, flush=True)
    lay, heap_top = get_layout(CELL / 2 - 0.003, CELL / 2 - 0.003, N_UNITS * PER_UNIT, seed=3)
    if "--pack-only" in argv: sys.exit(0)
    build_frame()
    cop = F.report_coplanar([(o.name, o.data) for o in base.PARTS], "frame")
    if "--frame-only" in argv: sys.exit(0)
    frame = join(list(base.PARTS), "BombCrate")
    for v in frame.data.vertices: v.co.z = max(v.co.z, 0.0)         # skid bottoms jitter a few mm under the floor
    frame.data.update()
    ftris = tris(frame)
    bb = np.array([tuple(v.co) for v in frame.data.vertices])
    print(f"FRAME tris {ftris} bounds {bb.min(0).round(4)} {bb.max(0).round(4)}", flush=True)
    units = make_units(lay)
    chk = run_checks(units, frame)
    homes = {g: h for g, h, *_ in COMPARTMENTS}
    fill_full = {g: (h or "BombSiege") for g, h in homes.items()}
    xc = cross_check(units, fill_full, frame)
    print("CROSS full", json.dumps(xc), flush=True)
    # every kind in the spare and in a compartment next to a full neighbour: the worst case a kind that overflows can make
    xs = {}
    for k in ALL:
        fill = dict(fill_full); fill[6] = k
        xs[k] = cross_check(units, fill, frame)
    print("CROSS spare holds each kind", json.dumps({k: (v["frame_clipping"], v["between_compartments"]) for k, v in xs.items()}), flush=True)
    tri_of = {k: len(F.TPL[k]["T"]) for k in ALL}
    ctri = {k: tri_of[k] * N_UNITS * PER_UNIT for k in ALL}
    full_tris = sum(ctri[fill_full[g]] for g in fill_full)
    print("TRIS frame", ftris, "contents full", full_tris, flush=True)

    base.save_atlas(atlas, os.path.join(OUTA, "bombcrate_atlas.png"))
    export_obj(frame, os.path.join(OUTA, "BombCrate.obj"))
    band = {h: PAINT_NAMES[pk] for g, h, pk, *_ in COMPARTMENTS if h}
    band["spare"] = PAINT_NAMES[6]
    doc = {
        "schema": "storehouse-anchors/1", "furniture": "Bomb Crate", "slug": "bombcrate", "round": 1, "placement": "ground",
        "unit_count": len(units), "slots_designed_for": 40, "stack_per_unit": True, "mirror": False, "heap": False, "homes": True,
        "slots_note": "13 compartments x 3 units = 39 stacks of up to 50 bombs (1950 bombs); five chest rows of eight = 40 slots",
        "frame": {"obj": "BombCrate.obj", "atlas": "bombcrate_atlas.png 128x128 point", "tris": ftris,
                  "size_m": [round(float(bb[:, 0].max() - bb[:, 0].min()), 3), round(float(bb[:, 2].max()), 3), round(float(bb[:, 1].max() - bb[:, 1].min()), 3)],
                  "size_note": "[x, y (up), z] Unity",
                  "bounds_unity": {"min": [round(-float(bb[:, 0].max()), 3), 0.0, round(-float(bb[:, 1].max()), 3)],
                                   "max": [round(-float(bb[:, 0].min()), 3), round(float(bb[:, 2].max()), 3), round(-float(bb[:, 1].min()), 3)]},
                  "contents_top_y_full": xc["contents_top_z"],
                  "stacking": "not stackable (open lids, heaped contents)"},
        "space": {"unity": "prefab space, origin on the floor at the centre of the footprint, +z front, +y up, +x to the furniture's left seen from the front",
                  "from_blender": "ux=-bx, uy=bz, uz=-by"},
        "groups": {"key": "compartment", "rows": "back row (raised floor) groups 0-6, front row groups 7-12, left to right seen from the front",
                   "homes": {str(g): (h or "spare: any bomb kind") for g, h, *_ in COMPARTMENTS},
                   "rule": "Homes store: each group's units carry 'item', the bomb kind its compartment is for (the spare has none, only "
                           "'example_item'). Group 6 is the spare. A kind that fills its compartment takes an empty one; every layout is "
                           "packed against all eight bomb shapes, so any kind may lie in any compartment without a copy touching another."},
        "band": band,
        "band_note": "paint mark colour per kind: a painted slab on the compartment's rim and a band on its front face; the spare is chalk white",
        "extra_place": "front place 7 (right end) is a bucket of sand, not a compartment: no group, no units",
        "fill_order": "units are listed compartment by compartment; step 0 is the bottom of the heap (the floor), step 2 the crown",
        "position": "unit position = mean of its copies' feet, on the straw peaks of its compartment (front row y %.3f, back row y %.3f); box informational" % (FZ["front"], FZ["back"]),
        "copy_rule": "bombs, no align: rot_quat_xyzw (any spin, up to 10 degrees of tilt), fit_longest_m %.2f, anchor bottom, offset.y = the "
                     "height the settled copy rests at (0 .. %.2f over the straw peaks)." % (F.LONG["bomb"], heap_top),
        "layout": {"compartments": 13, "units_each": N_UNITS, "copies_per_unit": PER_UNIT, "copies_full": N_UNITS * PER_UNIT * 13,
                   "cell_inner_m": CELL, "rim_over_floor_m": RIMH, "rim_over_straw_peaks_m": round(RIMH - PEAK, 3), "heap_top_over_straw_peaks_m": round(heap_top, 3),
                   "rows": {"front": {"floor_top": FF, "rim": RF, "y_blender": CY["front"]}, "back": {"floor_top": FB, "rim": RB, "y_blender": CY["back"]}},
                   "x_blender": CX, "one layout": "the same nine settled copies in every compartment, turned by a multiple of 90 degrees per compartment"},
        "items": {"found": {k: {"name": ITEM_NAMES[k], "item_bounds_centre": MODB[k][0], "item_bounds_size": MODB[k][1],
                                 "x_fit": round(F.LONG["bomb"] / max(MODB[k][1]), 3), "triangles": tri_of[k]} for k in ALL},
                  "checked_shapes": SHAPES, "same_mesh_as": {"BombBlob_Morkhalla": "BombBlob_Lava", "BombBlob_Poison": "BombBlob_Lava",
                                                              "BombBlob_PoisonElite": "BombBlob_Lava", "BombBlob_Tar": "BombBlob_Lava"},
                  "not_in_game": ["Dynamite (the mod's Fletcher list names it; the item is BombDynamite)"],
                  "modded": "none found in Player.log"},
        "checks": {"coplanar_frame": cop, "per_model": chk, "full_store": xc, "spare_holds_each_kind": {k: [v["frame_clipping"], v["between_compartments"]] for k, v in xs.items()},
                   "method": "mesh against mesh (BVH): every copy of every one of the twelve bomb prefabs against the frame and against every "
                             "other copy in its compartment; the full fill also across compartments, and the spare holding each kind in turn."},
        "triangles": {"frame": ftris, "contents_full_each_kind_in_its_home": full_tris, "per_prefab_full_compartment": ctri},
        "units_data": units}
    write_json_atomic(doc, os.path.join(OUTA, "bombcrate_anchors.json"))     # last: the mod live-reloads
    print("WROTE", OUTA, f"{time.time() - t0:.0f}s", flush=True)
    if "--no-render" in argv: sys.exit(0)

    # ---------------- renders ----------------
    def spawn(dx, fill, count=N_UNITS):
        fr = frame.copy(); bpy.context.scene.collection.objects.link(fr); fr.hide_render = False; fr.location = (dx, 0, 0)
        for g, k in fill.items():
            for u in [u for u in units if u["compartment"] == g][:count]:
                for c in u["copies"]:
                    ob = bpy.data.objects.new(k, F.TPL[k]["mesh"]); bpy.context.scene.collection.objects.link(ob)
                    ob.matrix_world = Matrix.Translation((dx, 0, 0)) @ Matrix((F.B4 @ F.place_u(u["position"], c, k) @ F.K4).tolist())
    X_EMPTY, X_HALF, X_FULL, X_FLET, X_BUNK = -10.6, -5.3, 0.0, 5.6, 10.2
    full_show = dict(fill_full); full_show[6] = "BombBile"
    half_show = {g: k for g, k in full_show.items() if g not in (2, 7, 11)}
    spawn(X_EMPTY, {}); spawn(X_HALF, half_show, count=2); spawn(X_FULL, full_show)
    frame.hide_render = True
    for slug, objname, atlasname, xx in (("fletcher_r2", "Fletcher.obj", "fletcher_atlas.png", X_FLET), ("bunker_r4", "Bunker.obj", "bunker_atlas.png", X_BUNK)):
        before = set(bpy.data.objects)
        bpy.ops.wm.obj_import(filepath=os.path.join(ASSETS, slug, objname), forward_axis="NEGATIVE_Z", up_axis="Y",
                              use_split_objects=False, use_split_groups=False)
        ob = [o for o in bpy.data.objects if o not in before][0]; ob.location.x = xx
        img = bpy.data.images.load(os.path.join(ASSETS, slug, atlasname))
        ob.data.materials.clear(); ob.data.materials.append(make_material(slug, img))
    references(chest_x=3.05, post_x=2.5)
    views = {"empty": (-26, 22, 8.4, (X_EMPTY, 0, 0.45), 40),
             "half": (-24, 22, 8.4, (X_HALF, 0, 0.45), 40),
             "full": (-26, 20, 8.6, (X_FULL, 0, 0.55), 40),
             "beside": (-14, 14, 17.0, ((X_FULL + X_BUNK) / 2 - 0.1, 0, 0.5), 36),
             "front": (0, 12, 8.2, (X_FULL, 0, 0.55), 40),
             "emptytop": (-8, 56, 7.0, (X_EMPTY, 0, 0.4), 40),
             "top": (-6, 58, 7.0, (X_FULL, 0, 0.4), 40),
             "back": (150, 20, 8.0, (X_FULL, 0, 0.7), 40),
             "backrow": (-14, 34, 3.2, (-1.4, 0.3, 0.45), 45),
             "frontrow": (14, 34, 3.2, (1.2, -0.3, 0.3), 45),
             "bucket": (24, 30, 2.4, (CX[6], CY["front"], 0.3), 45)}
    lights_and_render(OUT, "bombcrate1", views)
    print("DONE", flush=True)
