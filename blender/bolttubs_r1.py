"""Bolt Crate (bolttubs_r1), round 1 (prototype, Joost 24 Oct): a store for crossbow bolts only, one square cell per bolt kind,
in a stepped timber crate of the Fletcher family. Fletcher's Barrels r2 keeps its own two bolt tubs; this is the separate bolt
store out of "Still being worked on" in SPEC.md ("bolts deserve the same attention as arrows"). New files only: nothing is wired
into the mod. Reuses fletcher_r2.py for the item maths (the mod's placement: place_u, world, K3/B3, visible_mesh, report_coplanar).
Run: blender -b -P bolttubs_r1.py -- [--out DIR] [--quick] [--views a,b] [--no-render] [--frame-only] [--pack-only]
Writes into assets/bolttubs_r1/: BoltTubs.obj (frame only, forward -Z, up Y, triangulated, no materials), bolttubs_atlas.png
(128x128, point filtered) and bolttubs_anchors.json (written last, temp + rename: the mod live-reloads).

THE BOLTS (14 kinds, Joost 24 Oct). Vanilla BoltBone, BoltIron, BoltBlackmetal, BoltCarapace, BoltCharred (item models: the game's
bundle c4210710 via ValheimRip / the Fletcher r1 rip; ItemVisual bounds = F.MODB, read from the game files). ValheimArmory
(MidnightMods 1.36.1) VABoltWood, VABoltCoreWood, VABoltNeedle, VAbolt_bronze, VAbolt_poison, VAbolt_frost, VAFireBolt,
VASurtlingBolt, VAObsidianBolt: ripped from the asset bundle embedded in ValheimArmory.dll with UnityPy (the same extractor as the
vanilla items; scratchpad/bolttubs_r1/rip_va.py), bounds computed as ItemVisual does (the formula reproduces the vanilla table to
4 decimals): c_unity = (-cbx, cbz, -cby), s_unity = (sbx, sbz, sby) from the rip's bounds, root scale baked in (VABoltNeedle's root
is 0.5). Not verified against a Player.log line (none on this machine has them). VABoltNeedle is a shaft plus two crossed Quad
feathers (Unity's built-in Quad, a blend material with a glowing 32 px feather texture, 22 % opaque): for the packing checks a
feather counts where its texture alpha is above 0.5, like the alpha-cut fletchings of the arrows.
True sizes are 0.48-1.08 m long; every kind is drawn at fit_longest_m 0.32 (the Fletcher tubs' size), so the long VASurtlingBolt
(0.74 m) stands at 0.43x and the short VAbolt_poison/frost (0.48 m) at 0.67x.

FRAME. 4 x 4 square cells (0.34 inside, 0.05 dividers), stepped like terraces: each row's floor 0.12 above the one in front, rim
0.20 over its floor, so every row shows from the front and every cell's painted band stays visible.
  base      five skids, eight 0.045 deck planks along x (deck top 0.145), iron caps with rivets on the skid ends
  walls     front wall, three row walls (each stands up to the next row's rim), back wall, stepped end walls: 0.05 planks in
            courses; 12 column dividers; four-board floors raised row by row (hidden risers: the row walls run from the deck)
  posts     six 0.13 posts (four corners, one at each side's middle) with iron bands flush with the bounds
  iron      riveted plates on the end walls and an iron strap at every column divider on the front and back faces
  paint     per cell a painted slab on the rim of its front wall and a painted band on that wall's face (anchors 'band')
  straw     every cell is packed with straw to 0.11 over its floor, the straw surface cut away wherever any bolt of any kind passes
Cells: group key 'compartment' g = 4 * row + column, row 0 = front, column 0 = left seen from the front; g 0-13 the 14 kinds
(row 0 the vanilla four, then the wooden and metal ones, row 3 obsidian and needle), g 14 and 15 spare (no home, chalk bands).
Units: 16 x 4 = 64 (eight chest rows of eight); 4 bolts per unit, 16 per cell. One layout for all sixteen cells (turned by a
multiple of 90 degrees per cell), packed mesh against mesh against ALL 14 bolt models at once, so any kind may stand in any cell
(a kind that fills its home takes an empty cell) without a copy touching another or the frame. Each unit is a bundle (no cord):
the four shafts pass the gather height within 7 cm of the bundle centre and lean a few degrees apart there; bundle 0 is the
core, so one stack stands in the middle and the rest stand round it. Bolts stand with their feet 0 .. 0.08 m over the floor in the
straw (neighbouring fletchings and heads at different heights); whole bolts stay inside their cell up to 0.33 over the floor
(the row behind has a taller wall), above that 2 cm of lean over the divider is allowed.
Atlas 128x128 point: the Metal Pallet r3 atlas (hewn timber v 96-127, end grain v 64-95, iron v 0-31, plank v 48-63) with v 32-47
repainted: straw (u 0-31), hemp (u 32-63), sixteen paint swatches of 4 x 4 px (u 64-127, v 32-35 fresh, v 36-39 worn).
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
OUTA = os.path.join(ASSETS, "bolttubs_r1")
SCRATCH = "C:/Users/joost/AppData/Local/Temp/claude/C--Users-joost--pai/5e4bc60b-cdfe-4638-8e29-2e507fa13cf9/scratchpad"
SCR = SCRATCH + "/bolttubs_r1"
OUT = arg("--out", SCR)
RIPS = [F.ITEMS_DIR, SCRATCH + "/fletcher1/rip", SCR + "/rip"]       # vanilla (BoltCarapace, BoltCharred), vanilla rip, ValheimArmory rip
rng = random.Random(53)

# ---------- the 14 kinds ----------
# (compartment g, home prefab or None, paint swatch); g = 4 * row + column, row 0 = front
CELLS = [(0, "BoltBone", 0), (1, "BoltIron", 1), (2, "BoltBlackmetal", 2), (3, "BoltCarapace", 3),
         (4, "BoltCharred", 4), (5, "VABoltWood", 5), (6, "VABoltCoreWood", 6), (7, "VAbolt_bronze", 8),
         (8, "VAbolt_poison", 9), (9, "VAbolt_frost", 10), (10, "VAFireBolt", 11), (11, "VASurtlingBolt", 12),
         (12, "VAObsidianBolt", 13), (13, "VABoltNeedle", 7), (14, None, 14), (15, None, 15)]
KINDS = [h for _, h, _ in CELLS if h]
NAMES = {"BoltBone": "Bone Bolt", "BoltIron": "Iron Bolt", "BoltBlackmetal": "Blackmetal Bolt", "BoltCarapace": "Carapace Bolt",
         "BoltCharred": "Charred Bolt", "VABoltWood": "ValheimArmory wood bolt", "VABoltCoreWood": "ValheimArmory core wood bolt",
         "VABoltNeedle": "ValheimArmory needle bolt", "VAbolt_bronze": "ValheimArmory bronze bolt", "VAbolt_poison": "ValheimArmory poison bolt",
         "VAbolt_frost": "ValheimArmory frost bolt", "VAFireBolt": "ValheimArmory fire bolt", "VASurtlingBolt": "ValheimArmory surtling bolt",
         "VAObsidianBolt": "ValheimArmory obsidian bolt"}
PAINTS = [(0.62, 0.59, 0.52), (0.33, 0.38, 0.47), (0.11, 0.10, 0.095), (0.20, 0.45, 0.42), (0.31, 0.20, 0.14), (0.72, 0.62, 0.36),
          (0.31, 0.38, 0.17), (0.25, 0.66, 0.57), (0.62, 0.40, 0.18), (0.46, 0.66, 0.16), (0.55, 0.75, 0.86), (0.86, 0.43, 0.10),
          (0.62, 0.16, 0.10), (0.30, 0.20, 0.42), (0.74, 0.72, 0.64), (0.52, 0.54, 0.58)]
PAINT_NAMES = ["bone white", "iron slate blue", "black metal char", "carapace verdigris", "soot brown", "birch tan", "core wood moss",
               "needle glow teal", "bronze", "poison green", "frost blue", "flame orange", "surtling ember red", "obsidian violet",
               "spare chalk", "spare silver grey"]
NCOL, NROW = 4, 4
N_UNITS, PER_UNIT = 4, 4                       # units per cell, bolts per unit (16 per cell when full)
LONG = F.LONG["bolt"]                          # 0.32

# ---------- dimensions (Blender: x right, -y front, z up) ----------
CELL, DV, WT = 0.34, 0.05, 0.05
IW = NCOL * CELL + (NCOL - 1) * DV             # 1.51
HIW = HID = IW / 2
PS, INS = 0.13, 0.004
BX = BY = HIW + INS + PS + INS                 # 0.893: bounds half size (bands flush)
SK_H, SK_W, DT = 0.10, 0.14, 0.045
DECK = SK_H + DT                               # 0.145
FT, STEP, RIMH = 0.04, 0.12, 0.20
STRAW_IN = 0.11                                # straw packing over a cell's floor
KISS, EMB, FE, RV = 0.002, 0.0015, 0.008, 0.005
def FL(j): return DECK + FT + j * STEP         # floor top of row j
def RIM(j): return FL(j) + RIMH
def YR(j): return -HID + j * (CELL + DV)       # front edge (y) of row j's cells
CX = [-HIW + CELL / 2 + i * (CELL + DV) for i in range(NCOL)]
CY = [YR(j) + CELL / 2 for j in range(NROW)]
STRICT = 0.33                                  # whole bolts inside the cell below this height over the floor (the back wall is that high)
LIM = 0.02                                     # above that, lean over the divider
FOOT_LEVELS = (0.0, 0.03, 0.055, 0.08)
GATHER = 0.25

# ---------- atlas ----------
def build_atlas():
    src = bpy.data.images.load(os.path.join(ASSETS, "metalpallet_r3", "metalpallet_atlas.png"))
    px = np.array(src.pixels[:], np.float32).reshape(TH, TW, 4)
    img = px[..., :3].copy()
    nr = np.random.default_rng(43)
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
    im = bpy.data.images.new("bolttubs_atlas", TW, TH, alpha=False)
    im.pixels.foreach_set(np.concatenate([np.clip(img, 0, 1), np.ones((TH, TW, 1), np.float32)], 2).ravel())
    return im

def my_uv(f, kind, long_axis, seed):
    if kind.startswith("paint"):
        k = int(kind[5:]); r = random.Random(seed * 31 + f.index)
        F.planar(f, 64 + 4 * k + r.randrange(2) + 0.5, 32 + r.randrange(2) + 0.5, 1.5, 1.5, dens=60); return
    F.my_uv(f, kind, long_axis, seed)

# ---------- frame ----------
def part(name, size, pos, kind="plank", jitter=0.001, bevel=0.006, rot=(0, 0, 0)):
    return box(name, size, pos, kind=kind, jitter=jitter, bevel=bevel, rot=rot)

def courses(name, size_x, y0, y1, z0, z1, xc=0.0, sep=0.13):
    """A wall of planks in courses: x length size_x centred at xc, y from y0 to y1, z from z0 to z1."""
    n = max(2, round((z1 - z0) / sep))
    h = (z1 - z0) / n
    for c in range(n):
        part(name, (size_x, y1 - y0, h - 0.004), (xc, (y0 + y1) / 2, z0 + h * (c + 0.5)))

def build_frame():
    # ---- base: skids front to back, deck planks along x, iron caps on the skid ends ----
    for x in (-0.65, -0.325, 0.0, 0.325, 0.65):
        box("skid", (SK_W, 2 * BY, SK_H + KISS), (x, 0, (SK_H + KISS) / 2), jitter=0.003, bevel=0.014)
        for sg in (-1, 1):
            F.plate_y(x - 0.05, x + 0.05, 0.012, SK_H - 0.012, sg * BY, sg, rivets=[(x, SK_H / 2)])
    nb, gap = 8, 0.007
    bw = (2 * BY - (nb - 1) * gap) / nb
    for i in range(nb):
        box("deck", (2 * (HIW + INS) + 2 * KISS, bw, DT), (0, -BY + bw / 2 + i * (bw + gap), SK_H + DT / 2), kind="plank", jitter=0.0, bevel=0.008)
    # ---- six posts: corners (front low, back tall) and one at the middle of each side, iron bands flush with the bounds ----
    PXc = HIW + INS + PS / 2
    for sx in (-1, 1):
        for yc, h, bands in ((-PXc, 0.50, [(0.02, 0.08), (0.30, 0.08), (0.50 - 0.10 - 0.004, 0.10)]),
                             (0.0, 0.72, [(0.02, 0.08), (0.36, 0.08), (0.72 - 0.10 - 0.004, 0.10)]),
                             (PXc, 0.86, [(0.02, 0.08), (0.42, 0.08), (0.86 - 0.10 - 0.004, 0.10)])):
            box("post", (PS, PS, h), (sx * PXc, yc, h / 2), jitter=0.002, bevel=0.012)
            for z0, bh in bands:
                box("band", (PS + 2 * INS, PS + 2 * INS, bh), (sx * PXc, yc, z0 + bh / 2), kind="iron", jitter=0, bevel=0)
    # ---- floors: three boards per row (the row walls hide the risers) ----
    for j in range(NROW):
        w = CELL / 3
        for k in range(3):
            part("floor", (2 * HIW + 2 * KISS, w - 0.004 + (KISS if k in (0, 2) else 0.0) * 2,
                           FT + KISS), (0, YR(j) + w * (k + 0.5), FL(j) - FT / 2 - KISS / 2), jitter=0, bevel=0.004)
    # ---- walls along x: front, three row walls (each up to the next row's rim), back ----
    xw = 2 * (HIW + INS + KISS)
    courses("front", xw, -HID - WT, -HID, DECK - KISS, RIM(0))
    for j in range(NROW - 1):
        courses("rowwall", xw, YR(j + 1) - DV, YR(j + 1), DECK - KISS, RIM(j + 1))
    courses("back", xw, HID, HID + WT, DECK - KISS, RIM(NROW - 1))
    # ---- end walls: stepped, one segment per row (a little lower than the row walls: no shared top plane), stopping at the posts ----
    for sx in (-1, 1):
        for j in range(NROW):
            y0 = YR(j) - DV / 2 if j > 0 else -HID - INS - KISS
            y1 = YR(j) + CELL + DV / 2 if j < NROW - 1 else HID + INS + KISS
            if j == 0: y0 = -HID - INS - KISS
            if j == 1: y1 = -PS / 2 + KISS
            if j == 2: y0 = PS / 2 - KISS
            top = RIM(j) - 0.003
            n = max(2, round((top - (DECK - KISS)) / 0.13)); h = (top - (DECK - KISS)) / n
            for c in range(n):
                part("end", (WT, y1 - y0, h - 0.004), (sx * (HIW + WT / 2), (y0 + y1) / 2, DECK - KISS + h * (c + 0.5)))
    # ---- column dividers: three per row, standing on the row's floor, a little lower than the walls ----
    for j in range(NROW):
        for i in range(NCOL - 1):
            xd = -HIW + (i + 1) * CELL + i * DV + DV / 2
            zt = RIM(j) - 0.003
            part("div", (DV, CELL + 2 * KISS, zt - FL(j) + KISS), (xd, CY[j], (FL(j) + zt) / 2 - KISS / 2))
    # ---- iron: plates on the end walls, a strap at every divider on the front and back faces ----
    for sx in (-1, 1):
        xo = sx * (HIW + WT)
        for j in range(NROW):
            yc = CY[j] if j not in (1, 2) else CY[j] + (-0.10 if j == 1 else 0.10)
            F.plate_x(yc - 0.085, yc + 0.085, FL(j) + 0.03, RIM(j) - 0.04, xo, sx,
                      rivets=[(yc + dy, zz) for dy in (-0.045, 0.045) for zz in (FL(j) + 0.065, RIM(j) - 0.075)])
    for i in range(NCOL - 1):
        xd = -HIW + (i + 1) * CELL + i * DV + DV / 2
        F.plate_y(xd - 0.03, xd + 0.03, FL(0) + 0.02, RIM(0) - 0.03, -HID - WT, -1, rivets=[(xd, FL(0) + 0.06), (xd, RIM(0) - 0.07)])
        F.plate_y(xd - 0.03, xd + 0.03, DECK + 0.06, RIM(NROW - 1) - 0.04, HID + WT, 1, rivets=[(xd, DECK + 0.10), (xd, RIM(NROW - 1) - 0.08)])
    # ---- paint: per cell a slab on the rim of its front wall and a band on that wall's face ----
    for g, home, pk in CELLS:
        j, i = divmod(g, NCOL)
        cx = CX[i]
        yw = (-HID - WT / 2) if j == 0 else (YR(j) - DV / 2)               # centre of the cell's front wall
        yface = yw - (WT if j == 0 else DV) / 2
        box("rimpaint", (CELL - 0.10, 0.030, 0.008), (cx, yw, RIM(j) + 0.004 - EMB), kind=f"paint{pk}", jitter=0, bevel=0)
        zb = (FL(0) + 0.11) if j == 0 else (RIM(j - 1) + 0.06)
        box("facepaint", (CELL - 0.16, 0.004, 0.075), (cx, yface - 0.002 + EMB, zb), kind=f"paint{pk}", jitter=0, bevel=0)

# ---------- items ----------
def kind_dir(name):
    for d in RIPS:
        if os.path.isdir(os.path.join(d, name)): return d
    raise FileNotFoundError(name)

def load_tpl(name):
    d = kind_dir(name)
    info = json.load(open(os.path.join(d, name, "info.json")))
    bmin, bmax = np.array(info["bounds_min"]), np.array(info["bounds_max"])
    cb, sb = (bmin + bmax) / 2, bmax - bmin
    if name not in F.MODB:
        F.MODB[name] = ([float(-cb[0]), float(cb[2]), float(-cb[1])], [float(sb[0]), float(sb[2]), float(sb[1])])
    LI.ROOT = d
    obs = LI.load_item(name, anchor="origin")
    LI.ROOT = F.ITEMS_DIR
    ob = obs[0]
    for o in obs[1:]: bpy.data.objects.remove(o, do_unlink=True)
    me = ob.data; me.transform(ob.matrix_world); me.use_fake_user = True
    bpy.data.objects.remove(ob, do_unlink=True)
    Vb, T, frac = F.visible_mesh(os.path.join(d, name))
    c, s = F.MODB[name]
    F.TPL[name] = {"mesh": me, "Vi": Vb @ F.K3.T, "T": T, "c": np.array(c), "s": np.array(s), "dir": d, "opaque": frac,
                   "tris": info["triangles"]}

def try_copy(placed, off, R, ax, az):
    """One copy at Unity cell offset off (x, foot height, z), rotation R: lifted until the lowest vertex of every model clears
    the floor; every model of the 14 must stay inside the cell (less 4 mm) below STRICT over the floor and within LIM of it above,
    and touch no copy already standing."""
    off = np.array(off, float)
    c = F.copy_dict("bolt", off, R)
    Ws = {k: F.world(k, F.place_u((0, 0, 0), c, k)) for k in KINDS}
    lv = off[1] - 0.001
    need = max(0.002 + lv - Ws[k][:, 2].min() for k in KINDS)
    if need > 0:
        off[1] += need
        for k in KINDS: Ws[k][:, 2] += need
    for k in KINDS:
        Wv = Ws[k]; low = Wv[:, 2] < STRICT
        if (np.abs(Wv[low, 0]) > ax - 0.004).any() or (np.abs(Wv[low, 1]) > az - 0.004).any(): return None
        if (np.abs(Wv[:, 0]) > ax + LIM).any() or (np.abs(Wv[:, 1]) > az + LIM).any(): return None
    mine = {}
    for k in KINDS:
        Wv = Ws[k]; lo, hi = Wv.min(0), Wv.max(0)
        near = [o for _, _, o in placed if (lo <= o[k][3]).all() and (o[k][2] <= hi).all()]
        bv = F.bvh(k, Wv)
        if any(bv.overlap(o[k][1]) for o in near): return None
        mine[k] = (Wv, bv, lo, hi)
    return off, mine

def pack_cell(seed, ax, az, rho_max=0.07, sep=0.09, edge=0.03, tilt=(1.0, 5.0), pool=60, tries=80, rho_min=0.011):
    """N_UNITS bundles of PER_UNIT bolts, core bundle first (at the cell centre), each later bundle at least sep from the others'
    centres: the shafts pass GATHER over the floor within rho_max of the bundle centre and lean tilt degrees apart (a straight shaft
    that leans out above the gather height leans in below it, so a bundle crosses there), the foot one of FOOT_LEVELS."""
    rnd = random.Random(seed); placed, cents = [], []
    for u in range(N_UNITS):
        cs = []
        for _ in range(tries):
            if u == 0 and not cs: cs.append((0.0, 0.0)); continue
            cs.append((rnd.uniform(-(ax - edge), ax - edge), rnd.uniform(-(az - edge), az - edge)))
        cs.sort(key=lambda c: math.hypot(*c))
        done = False
        for cx, cz in cs:
            if any(math.hypot(cx - ox, cz - oz) < sep for ox, oz in cents): continue
            mark = len(placed); ok = True
            for m in range(PER_UNIT):
                cand = []
                for _ in range(pool):
                    rho = 0.0 if m == 0 else rnd.uniform(rho_min, rho_max); al = rnd.uniform(0, 2 * math.pi)
                    bx, bz = cx + rho * math.cos(al), cz + rho * math.sin(al)
                    if m == 0: phi = (math.atan2(cz, cx) if math.hypot(cx, cz) > 0.03 else rnd.uniform(0, 2 * math.pi)) + rnd.uniform(-0.9, 0.9)
                    else: phi = al + rnd.uniform(-0.5, 0.5)
                    th = math.radians(rnd.uniform(*tilt)); lv = rnd.choice(FOOT_LEVELS)
                    sh = (GATHER - lv) * math.tan(th)
                    R = F.Rlean(phi, th) @ F.Ry(rnd.uniform(0, 2 * math.pi))
                    cand.append((rho, (bx - sh * math.cos(phi), 0.001 + lv, bz - sh * math.sin(phi)), R))
                cand.sort(key=lambda c: c[0]); got = None
                for rho, off, R in cand:
                    got = try_copy(placed, off, R, ax, az)
                    if got: break
                if not got: ok = False; break
                placed.append((got[0], R, got[1]))
            if ok: cents.append((cx, cz)); done = True; break
            del placed[mark:]
        if not done:
            print(f"PACK bolt: bundle {u} found no room", flush=True); break
    print(f"PACK bolt: seed {seed}: {len(placed)} copies in {len(cents)} bundles", flush=True)
    return [(p[0], p[1]) for p in placed]

def get_layout(seeds=(1, 4, 7, 9, 10, 11, 12, 13)):
    ax = az = CELL / 2
    key = hashlib.md5(json.dumps([ax, STRICT, LIM, FOOT_LEVELS, GATHER, KINDS, LONG, N_UNITS, PER_UNIT, sorted(F.MODB.items())],
                                  sort_keys=True).encode()).hexdigest()[:10]
    path = os.path.join(SCR, f"layout_{key}.json")
    if os.path.exists(path):
        print("PACK bolt: layout from", path, flush=True)
        return [(np.array(o), np.array(R)) for o, R in json.load(open(path))["copies"]]
    best = []
    for sd in seeds:
        lay = pack_cell(sd, ax, az)
        if len(lay) > len(best): best = lay
        if len(best) == N_UNITS * PER_UNIT: break
    json.dump({"copies": [(o.tolist(), R.tolist()) for o, R in best]}, open(path, "w"))
    return best

# ---------- units ----------
def make_units(lay):
    units = []
    for g, home, pk in CELLS:
        j, i = divmod(g, NCOL)
        bx, by = CX[i], CY[j]
        Rh = F.Ry(math.radians(90 * ((g * 3 + i) % 4)))
        cu = np.array([-bx, FL(j), -by])
        abs_copies = [(cu + Rh @ off, Rh @ R) for off, R in lay]
        for k in range(N_UNITS):
            mine = abs_copies[k * PER_UNIT:(k + 1) * PER_UNIT]
            if not mine: continue
            P = np.array([o for o, _ in mine])
            upos = np.array([P[:, 0].mean(), FL(j), P[:, 2].mean()])
            u = {"index": len(units), "compartment": g, "holder": "cell", "kind": "bolt", "step": k, "paint": PAINT_NAMES[pk],
                 "position": [round(float(a), 5) for a in upos], "rotation": [0.0, 0.0, 0.0],
                 "box": [round(float(np.ptp(P[:, 0])) + 0.06, 3), LONG, round(float(np.ptp(P[:, 2])) + 0.06, 3)]}
            if home: u["item"] = home
            else: u["example_item"] = "BoltIron"
            u["copies"] = [F.copy_dict("bolt", o - upos, R) for o, R in mine]
            units.append(u)
    return units

def unit_worlds(u, name): return [F.world(name, F.place_u(u["position"], c, name)) for c in u["copies"]]

# ---------- straw: a rectangular packing per cell, cut away wherever any bolt of any kind passes ----------
def straw_cell(cx, cy, ax, z, cut, n=13, seed=0):
    pr = random.Random(seed)
    P = []
    for jy in range(n):
        for ix in range(n):
            x = cx - ax + (2 * ax) * ix / (n - 1); y = cy - ax + (2 * ax) * jy / (n - 1)
            edge = ix in (0, n - 1) or jy in (0, n - 1)
            P.append((x, y, z + (-0.004 if edge else pr.uniform(-0.008, 0.008))))
    T = []
    for jy in range(n - 1):
        for ix in range(n - 1):
            a, b, c, d = jy * n + ix, jy * n + ix + 1, (jy + 1) * n + ix + 1, (jy + 1) * n + ix
            T.append((a, b, c)); T.append((a, c, d))
    tree = BVHTree.FromPolygons(P, T, all_triangles=True)
    hit = set()
    for b in cut:
        for i, _ in tree.overlap(b): hit.add(i)
    bm = bmesh.new(); uvl = bm.loops.layers.uv.verify()
    vs = [bm.verts.new(p) for p in P]
    for ti, t in enumerate(T):
        if ti in hit: continue
        f = bm.faces.new([vs[i] for i in t]); f.normal_update()
        if f.normal.z < 0: f.normal_flip()
        u0, v0 = 1 + pr.randrange(22), 33 + pr.randrange(8)
        for l, (du, dv) in zip(f.loops, ((0, 0), (4, 0), (2, 5))): l[uvl].uv = ((u0 + du) / TW, (v0 + dv) / TH)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    return F.mesh_part("straw", bm), len(hit)

# ---------- checks ----------
def run_checks(units, frame):
    V, T = tri_list(frame.data)
    fbvh = BVHTree.FromPolygons(V, T, all_triangles=True)
    res = {}
    for k in KINDS:
        clip, over, n = 0, 0, 0
        for g, *_ in CELLS:
            Ws = [w for u in units if u["compartment"] == g for w in unit_worlds(u, k)]
            B = [F.bvh(k, w) for w in Ws]
            n += len(Ws)
            clip += sum(1 for b in B if fbvh.overlap(b))
            for a in range(len(B)):
                for b in range(a + 1, len(B)):
                    if B[a].overlap(B[b]): over += 1
        res[k] = {"copies": n, "frame_clipping": clip, "copy_overlaps": over}
    print("CHECK", json.dumps(res), flush=True)
    return res

def cross_check(units, fill, frame, fbvh=None):
    """fill: compartment -> kind. Every copy against the frame and against every copy of every other compartment."""
    if fbvh is None:
        V, T = tri_list(frame.data); fbvh = BVHTree.FromPolygons(V, T, all_triangles=True)
    items = []
    for u in units:
        k = fill.get(u["compartment"])
        if not k: continue
        for w in unit_worlds(u, k): items.append((u["compartment"], k, w, F.bvh(k, w), w.min(0), w.max(0)))
    clip = sum(1 for it in items if fbvh.overlap(it[3]))
    cross = 0
    for a in range(len(items)):
        for b in range(a + 1, len(items)):
            p, q = items[a], items[b]
            if p[0] == q[0] or not ((p[4] <= q[5]).all() and (q[4] <= p[5]).all()): continue
            if p[3].overlap(q[3]): cross += 1
    top = max(float(it[2][:, 2].max()) for it in items) if items else 0.0
    return {"copies": len(items), "frame_clipping": clip, "between_compartments": cross, "contents_top_z": round(top, 3)}

# ---------- main ----------
if __name__ == "__main__":
    t0 = time.time()
    os.makedirs(OUTA, exist_ok=True); os.makedirs(OUT, exist_ok=True)
    setup_scene()
    atlas = build_atlas()
    base.MAT = make_material("bolttubs", atlas)
    base.PARTS.clear()
    base.uv_face = my_uv
    F.LONG["bolt"] = LONG
    for k in KINDS: load_tpl(k)
    print("VISIBLE", {k: (len(t["T"]), round(t["opaque"], 3)) for k, t in F.TPL.items() if k in KINDS}, flush=True)
    lay = get_layout()
    print(f"LAYOUT {len(lay)} copies  ({time.time() - t0:.0f}s)", flush=True)
    if "--pack-only" in argv: sys.exit(0)
    build_frame()
    units = make_units(lay)
    # straw per cell, cut by every copy of every kind
    straw_cut = {}
    for g, home, pk in CELLS:
        j, i = divmod(g, NCOL)
        bvs = [F.bvh(k, w) for u in units if u["compartment"] == g for k in KINDS for w in unit_worlds(u, k)]
        _, nh = straw_cell(CX[i], CY[j], CELL / 2 - 0.002, FL(j) + STRAW_IN, bvs, seed=g + 1)
        straw_cut[g] = nh
    print("STRAW holes (triangles left out) per cell", straw_cut, flush=True)
    cop = F.report_coplanar([(o.name, o.data) for o in base.PARTS], "frame")
    if "--frame-only" in argv: sys.exit(0)
    frame = join(list(base.PARTS), "BoltTubs")
    ftris = tris(frame)
    bb = np.array([tuple(v.co) for v in frame.data.vertices])
    print(f"FRAME tris {ftris} bounds {bb.min(0).round(4)} {bb.max(0).round(4)}", flush=True)
    chk = run_checks(units, frame)
    V, T = tri_list(frame.data); fbvh = BVHTree.FromPolygons(V, T, all_triangles=True)
    homes = {g: h for g, h, _ in CELLS}
    fill_full = {g: (h or ("BoltIron" if g == 14 else "BoltBone")) for g, h in homes.items()}      # the spares hold overflow of two kinds
    xc = cross_check(units, fill_full, frame, fbvh)
    print("CROSS full", json.dumps(xc), flush=True)
    xs = {}
    for k in KINDS:
        fill = {g: kk for g, kk in fill_full.items()}; fill[14] = k; fill[15] = k
        xs[k] = cross_check(units, fill, frame, fbvh)
    print("CROSS spares hold each kind", json.dumps({k: (v["frame_clipping"], v["between_compartments"]) for k, v in xs.items()}), flush=True)
    # a kind in every cell at once (each kind in turn): the worst case an overflowing kind can make
    xe = {}
    for k in KINDS:
        xe[k] = cross_check(units, {g: k for g, *_ in CELLS}, frame, fbvh)
    print("CROSS each kind in all sixteen cells", json.dumps({k: (v["frame_clipping"], v["between_compartments"]) for k, v in xe.items()}), flush=True)
    tri_of = {k: F.TPL[k]["tris"] for k in KINDS}
    ctri = {k: tri_of[k] * N_UNITS * PER_UNIT for k in KINDS}
    full_tris = sum(ctri[fill_full[g]] for g in fill_full)
    print("TRIS frame", ftris, "contents full", full_tris, "total", ftris + full_tris, flush=True)
    # which end of each model stands up (Align.Axes turns the item's +long axis to up): the end with the wider spread of vertices is the fletching
    heads = {}
    c0 = F.copy_dict("bolt", [0, 0.001, 0], np.eye(3))
    for k in KINDS:
        Wv = F.world(k, F.place_u((0, 0, 0), c0, k)); z = Wv[:, 2]; ctr = Wv[(z > 0.12) & (z < 0.2)][:, :2].mean(0) if ((z > 0.12) & (z < 0.2)).any() else np.zeros(2)
        r = np.hypot(*(Wv[:, :2] - ctr).T)
        top = float(r[z > z.max() - 0.07].max()); bot = float(r[z < z.min() + 0.07].max())
        heads[k] = {"spread_top_m": round(top, 3), "spread_bottom_m": round(bot, 3)}
    print("ENDS", json.dumps(heads), flush=True)

    base.save_atlas(atlas, os.path.join(OUTA, "bolttubs_atlas.png"))
    export_obj(frame, os.path.join(OUTA, "BoltTubs.obj"))
    band = {h: PAINT_NAMES[pk] for g, h, pk in CELLS if h}
    band["spare"] = [PAINT_NAMES[14], PAINT_NAMES[15]]
    n_copies = sum(len(u["copies"]) for u in units)
    doc = {
        "schema": "storehouse-anchors/1", "furniture": "Bolt Crate", "slug": "bolttubs", "round": 1, "placement": "ground",
        "unit_count": len(units), "slots_designed_for": 64, "stack_per_unit": True, "mirror": False, "heap": False, "homes": True,
        "frame": {"obj": "BoltTubs.obj", "atlas": "bolttubs_atlas.png 128x128 point", "tris": ftris,
                  "size_m": [round(float(bb[:, 0].max() - bb[:, 0].min()), 3), round(float(bb[:, 2].max()), 3), round(float(bb[:, 1].max() - bb[:, 1].min()), 3)],
                  "size_note": "[x, y (up), z] Unity",
                  "bounds_unity": {"min": [round(-float(bb[:, 0].max()), 3), 0.0, round(-float(bb[:, 1].max()), 3)],
                                   "max": [round(-float(bb[:, 0].min()), 3), round(float(bb[:, 2].max()), 3), round(-float(bb[:, 1].min()), 3)]},
                  "contents_top_y_full": xc["contents_top_z"],
                  "stacking": "not stackable: stepped terraces, the bolts stand above the rims"},
        "space": {"unity": "prefab space, origin on the floor at the centre of the footprint, +z front, +y up, +x to the furniture's left seen from the front",
                  "from_blender": "ux=-bx, uy=bz, uz=-by"},
        "groups": {"key": "compartment", "rows": "g = 4 * row + column; row 0 is the front, column 0 the left seen from the front; "
                   "each row stands 0.12 m higher than the one in front",
                   "homes": {str(g): (h or "spare: any bolt kind") for g, h, _ in CELLS},
                   "rule": "Homes store: each group's units carry 'item', the bolt kind its cell is for (the two spares have none, only "
                           "'example_item'). One layout serves all sixteen cells, packed against all 14 models, so a kind that "
                           "fills its home may take an empty cell (the spares first) without a copy touching another or the frame."},
        "band": band,
        "band_note": "paint colour per kind: a painted slab on the rim of the cell's front wall and a band on that wall's face; "
                     "paint swatches 0-15 in the atlas (u 64 + 4 k, v 32); the spares are chalk white and silver grey",
        "fill_order": "units are listed cell by cell; step 0 is the core bundle (the middle of the cell), steps 1-3 stand round it",
        "position": "unit position = mean of its copies' feet, on the floor of its cell (row j: y %s); box informational" % [round(FL(j), 3) for j in range(NROW)],
        "copy_rule": "bolts: align (long axis -> up, thin axis -> x), then_rotate = a lean of 1-5 degrees times a spin about the shaft, "
                     "fit_longest_m 0.32, anchor bottom, offset.y = the foot height in the straw (0 .. 0.08 in steps) plus the lift a "
                     "lean needs (a leaning copy dips below its bounds)",
        "straw": "every cell is packed with straw to %.2f m over its floor; the straw surface is part of the frame, each triangle that "
                 "any copy of any model touches cut away" % STRAW_IN,
        "heads": {"note": "Align.Axes turns the item's +long axis to up and the models differ in sign, so the end that stands up is per "
                          "model; spread = the widest radius of the top and bottom 7 cm of the standing bolt (the wide end is the fletching)",
                  "ends": heads},
        "layout": {"cells": NCOL * NROW, "columns": NCOL, "rows": NROW, "units_each": N_UNITS, "copies_per_unit": PER_UNIT,
                   "copies_full": n_copies, "cell_inner_m": CELL, "divider_m": DV, "rim_over_floor_m": RIMH, "row_step_m": STEP,
                   "floor_tops_y": [round(FL(j), 3) for j in range(NROW)], "x_blender": CX, "y_blender": CY,
                   "foot_levels_m": list(FOOT_LEVELS), "gather_height_m": GATHER, "straw_over_floor_m": STRAW_IN,
                   "one layout": "the same sixteen copies in every cell, turned by a multiple of 90 degrees per cell"},
        "items": {"found": {k: {"name": NAMES[k], "item_bounds_centre": [round(a, 4) for a in F.MODB[k][0]],
                                 "item_bounds_size": [round(a, 4) for a in F.MODB[k][1]],
                                 "x_fit": round(LONG / max(F.MODB[k][1]), 3), "triangles": tri_of[k],
                                 "source": "game files" if k in ("BoltBone", "BoltIron", "BoltBlackmetal", "BoltCarapace", "BoltCharred") else "ValheimArmory 1.36.1 bundle (computed)"}
                          for k in KINDS},
                  "checked_models": KINDS,
                  "needle": "VABoltNeedle's two blend feather quads count where their texture alpha is above 0.5 in the checks"},
        "checks": {"coplanar_frame": cop, "per_model": chk, "full_store": xc,
                   "spares_hold_each_kind": {k: [v["frame_clipping"], v["between_compartments"]] for k, v in xs.items()},
                   "each_kind_in_all_cells": {k: [v["frame_clipping"], v["between_compartments"]] for k, v in xe.items()},
                   "method": "mesh against mesh (BVH): every copy of every one of the 14 models against the frame (straw included) and "
                             "against every other copy in its cell; the full fill also across cells, the spares holding each kind "
                             "in turn, and each kind in all sixteen cells at once."},
        "triangles": {"frame": ftris, "contents_full": full_tris, "total_full": ftris + full_tris, "per_prefab_full_cell": ctri},
        "units_data": units}
    write_json_atomic(doc, os.path.join(OUTA, "bolttubs_anchors.json"))     # last: the mod live-reloads
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
    X_EMPTY, X_HALF, X_FULL = -7.2, -3.6, 0.0
    half_show = {g: k for g, k in fill_full.items() if g < 14}
    spawn(X_EMPTY, {}); spawn(X_HALF, half_show, count=2); spawn(X_FULL, fill_full)
    frame.hide_render = True
    beside = {}
    xnext = BX + 0.75
    for slug, objname, atlasname in (("fletcher_r2", "Fletcher.obj", "fletcher_atlas.png"), ("bunker_r4", "Bunker.obj", "bunker_atlas.png")):
        before = set(bpy.data.objects)
        bpy.ops.wm.obj_import(filepath=os.path.join(ASSETS, slug, objname), forward_axis="NEGATIVE_Z", up_axis="Y",
                              use_split_objects=False, use_split_groups=False)
        ob = [o for o in bpy.data.objects if o not in before][0]
        xx = xnext + ob.dimensions.x / 2; ob.location.x = xx; xnext = xx + ob.dimensions.x / 2 + 0.75
        beside[slug] = (xx, [round(a, 3) for a in ob.dimensions])
        img = bpy.data.images.load(os.path.join(ASSETS, slug, atlasname))
        ob.data.materials.clear(); ob.data.materials.append(make_material(slug, img))
    print("BESIDE (x centre, dimensions)", beside, flush=True)
    references(chest_x=xnext + 0.6, post_x=xnext - 0.1)
    xmid = (X_FULL + xnext) / 2
    views = {"empty": (-26, 24, 7.6, (X_EMPTY, 0, 0.35), 58),
             "half": (-24, 24, 7.6, (X_HALF, 0, 0.4), 58),
             "full": (-26, 24, 7.6, (X_FULL, 0, 0.4), 58),
             "beside": (-12, 13, max(14.5, xnext * 1.45), (xmid - 0.3, 0, 0.7), 42),
             "front": (0, 14, 7.2, (X_FULL, 0, 0.45), 58),
             "top": (-6, 62, 6.4, (X_FULL, 0, 0.3), 58),
             "back": (150, 22, 7.6, (X_FULL, 0, 0.45), 58),
             "close": (-22, 30, 3.4, (-0.4, -0.3, 0.45), 60),
             "close_back": (-14, 38, 3.2, (0.3, 0.45, 0.65), 60)}
    lights_and_render(OUT, "bolttubs1", views)
    print("DONE", f"{time.time() - t0:.0f}s", flush=True)
