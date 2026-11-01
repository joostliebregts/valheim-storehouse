"""Arrow Tubes, round 1: a store for arrows only, one tube for every arrow kind (a new piece beside Fletcher's Barrels).

Joost, 24 Oct: Fletcher's Barrels has fewer barrels than arrow kinds and draws only 2 arrows per stack of 100, so it looks
sparse and mixed. This piece is an arrow store of its own: a stepped stand of 20 stave tubes (7 in front, 6 in the middle,
7 at the back, each row one step higher), a tube for every arrow kind (17: the 12 vanilla kinds and the 5 ValheimArmory
ones) and 3 spare tubes (an unpainted rope band) for the arrows of other mods. Every tube has its own painted band, so you
know where fire, frost or poison go. Each stack (unit) is a dense gathered bundle of 13 arrows, no cord, 4 bundles to a
tube, so a full tube is packed.
Run: blender -b -P arrowtubes_r1.py -- [--out DIR] [--rip DIR] [--quick] [--views a,b] [--no-render] [--frame-only] [--repack]
Writes into assets/arrowtubes_r1/: ArrowTubes.obj (frame only, forward -Z, up Y, triangulated, no materials),
arrowtubes_atlas.png (128x128, point filtered) and arrowtubes_anchors.json (written last, temp + rename: the mod live-reloads).

It reuses fletcher_r2.py's machinery (atlas, hewn staves, iron plates, the game's own arrow size and placement, the mesh-
against-mesh packer and clip checks); everything that depends on the layout of THIS piece is here. See fletcher_r2.py's
docstring for ARROW SIZE: arrows are fitted to 0.86 m (0.47x flint), the layouts are packed against EVERY ripped arrow model
at once (11 of them), so no kind clips another or the tube. Not ripped (not checked, same fitted size): ArrowNeedle (two Quads
from Unity's built-in resources) and the five ValheimArmory arrows (mod asset bundles; assumed to be vanilla-sized arrows).

Frame 2.60 W x 1.22 D x 1.17 H (Blender x, y, z; -y = front).
  base      five 0.14 x 0.10 skids with riveted iron caps; three tiers whose decks (0.045 planks along x) top at 0.145, 0.385
            and 0.625; two risers of two hewn planks (iron straps, rivets) between the tiers; a 0.09 sill beam in front
  sides     stepped cheeks 0.10 thick with a cap beam on each tier, riveted plates; four posts with iron bands (front 0.50,
            back 1.17), a back top beam, mid rail and three studs, a knee brace from each back post onto the top tier's cap beam
  tubes     20 x (8 staves 0.032 thick and 0.50 high, outer apothem 0.155; hoops at both ends and a painted band 0.08 high;
            a straw bed 0.10 under the rim, cut away where any arrow passes), pitch 0.332, rows y -0.34, 0, +0.34
Atlas 128x128 point: fletcher_r2's (= the Metal Pallet r3 atlas with straw and hemp), with the painted swatches (v 32-47,
u 64-127) redone as 4 x 4 px blocks, 17 colours in a fresh and a worn variant.

Units: 20 tubes x 4 bundles = 80 (UNITS_PER; 3 would give 60), group key "compartment" 0-19; unit "item" = the arrow kind of
its tube (spare tubes: no item). Each unit is one stack: 13 arrows (PER), 52 to a full tube. The 4 bundles of a tube stand
side by side round the axis (fill order: opposite pairs, so a half-full tube is balanced). A bundle is a cone: all 13 shafts
pass one apex under the straw (hidden), each leaning from the vertical by its place in a 4.5 degree cone (a golden-angle spiral),
feet 0 to 0.30 m up in the straw, so a bundle is tight at the straw and opens up to its heads and fletchings.

DENSITY (measured, see pack_tube): 52 arrows of 0.86 m cannot stand in a tube this size without touching. Packed mesh against
mesh with no touching at all (fletcher_r2's rule, all 11 ripped models at once) 7 arrows fit inner radius 0.123 and 20 fit
fletcher_r2's barrel radius 0.19, so a "dense gathered bundle" has to interleave the way a real one does. The rules:
(1) no arrow touches the frame, a tube or the straw, anywhere (0, checked by BVH, straw triangles cut away); (2) arrows may
touch each other; each copy is placed where its fletching and head (triangles farther than 1.8 cm from the shaft, above the
straw surface) touch the fewest neighbours; the count is in the anchors (layouts) and the log, the full triangle-pair count in
checks.per_model.

Unity prefab space: ux = -bx, uy = bz, uz = -by (as fletcher_r2).
"""
import os, sys, math, json, random, time
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import bpy, bmesh
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
import metalrack_r1 as base
from metalrack_r1 import (box, join, tris, tri_list, export_obj, write_json_atomic, make_material, setup_scene, references,
                          lights_and_render, argv, arg, TW, TH)
import fletcher_r2 as F

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.normpath(os.path.join(HERE, "..", "assets"))
OUTA = os.path.join(ASSETS, "arrowtubes_r1")
SCRATCH = "C:/Users/joost/AppData/Local/Temp/claude/C--Users-joost--pai/5e4bc60b-cdfe-4638-8e29-2e507fa13cf9/scratchpad/arrowtubes_r1"
OUT = arg("--out", SCRATCH)
CACHE = os.path.join(SCRATCH, "layouts_r1.json")
rng = F.rng

# ---------- the tubes ----------
NS = 8                                     # staves per tube (flats face x and y)
TA, TT, TH_ = 0.155, 0.032, 0.50           # outer apothem, stave thickness, stave height
HOOP_T = 0.007
PITCH = 0.332
HEAD_Z0, HEAD_T = 0.03, 0.04
FLOOR_OFF = HEAD_Z0 + HEAD_T               # 0.07: the tube head over the deck (under the straw)
STRAW_OFF = TH_ - 0.10                     # the straw surface over the deck
R_IN = TA - TT                             # 0.123
R_LIM = PITCH / 2 - 0.0125                 # no arrow leaves this cylinder: neighbours can never touch
RIM_H = TH_ - FLOOR_OFF                    # the rim over the head
LEVELS = (0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30)
PER, UNITS_PER = 13, 4
TOUCH_OK = 10**9
KISS, EMB, FE, RV = F.KISS, F.EMB, F.FE, F.RV

# ---------- the stand ----------
SK_H, SK_W, DT = 0.10, 0.14, 0.045
RISE = 0.24
DECK = [SK_H + DT + k * RISE for k in range(3)]       # 0.145, 0.385, 0.625
XI = 1.17                                             # inner faces of cheeks and posts
CK_T, PS = 0.10, 0.13
Y_F, Y_B = -0.62, 0.625
YB1, YB2 = -0.178, 0.178                              # tier boundaries
ROWS = [(-0.35, 7), (0.0, 6), (0.35, 7)]
INS = 0.004
W = 2 * (XI + PS)
D = Y_B - Y_F
H_BACK, H_FRONT = 1.17, 0.50

def tube_centres():
    t = []
    for r, (y, n) in enumerate(ROWS):
        for i in range(n):
            t.append((r, (i - (n - 1) / 2) * PITCH, y, DECK[r]))
    return t
TUBES = tube_centres()
NT = len(TUBES)

# kinds: front row ordinary shafts, middle row the special ones, back row the late and the mod's; spare = None
KIND_OF = ["ArrowWood", "ArrowFlint", "VAArrowBone", "ArrowBronze", "ArrowIron", "ArrowObsidian", None,
           "ArrowFire", "VAarrow_surtling_fire", "ArrowPoison", "ArrowFrost", "ArrowSilver", "ArrowNeedle",
           "ArrowCarapace", "VAChitinArrow", "ArrowCharred", "VAArrowGreenMetal", "VAArrowAncient", None, None]
assert len(KIND_OF) == NT
BAND = {   # kind: (colour name, sRGB)
    "ArrowWood": ("ochre yellow", (0.66, 0.52, 0.18)), "ArrowFlint": ("stone tan", (0.55, 0.50, 0.40)),
    "VAArrowBone": ("bone ivory", (0.76, 0.72, 0.60)), "ArrowBronze": ("copper brown", (0.50, 0.29, 0.13)),
    "ArrowIron": ("slate blue", (0.30, 0.36, 0.47)), "ArrowObsidian": ("obsidian black", (0.10, 0.09, 0.09)),
    "ArrowFire": ("rust orange", (0.68, 0.32, 0.10)), "VAarrow_surtling_fire": ("ember red", (0.56, 0.13, 0.10)),
    "ArrowPoison": ("lime green", (0.42, 0.50, 0.13)), "ArrowFrost": ("pale ice blue", (0.56, 0.70, 0.78)),
    "ArrowSilver": ("silver white", (0.84, 0.85, 0.84)), "ArrowNeedle": ("plum purple", (0.40, 0.22, 0.42)),
    "ArrowCarapace": ("verdigris", (0.18, 0.42, 0.38)), "VAChitinArrow": ("chitin rose", (0.64, 0.36, 0.44)),
    "ArrowCharred": ("ash grey", (0.27, 0.26, 0.26)), "VAArrowGreenMetal": ("jade green", (0.15, 0.52, 0.32)),
    "VAArrowAncient": ("ancient indigo", (0.22, 0.20, 0.52)),
}
KINDS = [k for k in KIND_OF if k]
PAINT_IDX = {k: i for i, k in enumerate(KINDS)}
# the render stand-ins for the kinds that are not ripped (looks only; the checks cover every ripped model)
STAND_IN = {"ArrowNeedle": "ArrowWood", "VAArrowBone": "ArrowFlint", "VAarrow_surtling_fire": "ArrowFire",
            "VAArrowGreenMetal": "ArrowPoison", "VAChitinArrow": "ArrowCarapace", "VAArrowAncient": "ArrowSilver"}
def model_of(k): return STAND_IN.get(k, k)

# ---------- atlas ----------
def sw(i): return 64 + 4 * (i % 16), 32 + 4 * (i // 16)       # fresh swatch i (0-16), worn i + 17
def build_atlas():
    im = F.build_atlas()
    px = np.array(im.pixels[:], np.float32).reshape(TH, TW, 4)
    nr = np.random.default_rng(41)
    px[32:48, 64:128, :3] = F.WOOD_L
    for i, k in enumerate(KINDS):
        c = np.array(BAND[k][1], np.float32)
        for wear, idx in ((0.04, i), (0.20, i + 17)):
            u0, v0 = sw(idx)
            blk = c * (0.86 + 0.14 * nr.random((4, 4)))[..., None]
            blk[[0, 3], :] *= 0.80; blk[:, [0, 3]] *= 0.80
            worn = nr.random((4, 4)) < wear
            blk[worn] = blk[worn] * 0.45 + F.WOOD_L * 0.55
            px[v0:v0 + 4, u0:u0 + 4, :3] = blk
    im.pixels.foreach_set(px.ravel())
    return im

def paint_uv(f, kind, long_axis, seed):
    """Kinds 'pnt<i>' map to the band swatches (a point inside the 4 px block, fresh or worn at random)."""
    i = int(kind[3:]) + (17 if rng.random() < 0.22 else 0)
    u0, v0 = sw(i)
    u, v = u0 + 1.0 + rng.random() * 2.0, v0 + 1.0 + rng.random() * 2.0
    for l in f.loops: l[base.UV].uv = (u / TW, v / TH)

def my_uv(f, kind, long_axis, seed):
    if kind.startswith("pnt"): return paint_uv(f, kind, long_axis, seed)
    return F.my_uv(f, kind, long_axis, seed)

# ---------- parts ----------
def ring2(name, cx, cy, n, apo, thick, z0, z1, kind):
    """A hoop (kind 'iron'), painted band ('pnt<i>') or rope band ('hemp') of n flat segments round (cx, cy), inner apothem apo."""
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.verify()
    rc_i, rc_o = apo / math.cos(math.pi / n), (apo + thick) / math.cos(math.pi / n)
    corners = [2 * math.pi * k / n - math.pi / n for k in range(n)]
    def V(r, a, z): return bm.verts.new((cx + r * math.cos(a), cy + r * math.sin(a), z))
    ib = [V(rc_i, a, z0) for a in corners]; it = [V(rc_i, a, z1) for a in corners]
    ob = [V(rc_o, a, z0) for a in corners]; ot = [V(rc_o, a, z1) for a in corners]
    seg = 2 * (apo + thick) * math.tan(math.pi / n)
    for k in range(n):
        j = (k + 1) % n
        for fv, part in (((ob[k], ob[j], ot[j], ot[k]), "out"), ((ot[k], ot[j], it[j], it[k]), "top"), ((ib[k], ib[j], ob[j], ob[k]), "bot")):
            f = bm.faces.new(fv)
            if kind.startswith("pnt"):
                i = int(kind[3:]) + (17 if rng.random() < 0.22 else 0)
                u0, v0 = sw(i)
                cu, cv = u0 + 1.0 + rng.random() * 2.0, v0 + 1.0 + rng.random() * 2.0
                uvs = [(cu, cv)] * 4
            elif kind == "hemp":
                cu, cv = 33 + rng.random() * 24, 34 + rng.random() * 8
                uvs = [(cu, cv), (cu + 3, cv), (cu + 3, cv + 3), (cu, cv + 3)]
            elif part == "out":
                u0 = k * seg * F.DENS + 7
                h = (z1 - z0) * F.DENS
                uvs = [(u0, 2), (u0 + seg * F.DENS, 2), (u0 + seg * F.DENS, 2 + h), (u0, 2 + h)]
            else:
                u = F.SWATCH_U + 1 + rng.randrange(28); v = 65 + rng.randrange(12)
                uvs = [(u, v), (u + 1, v), (u + 1, v + 1), (u, v + 1)]
            for l, (u, v) in zip(f.loops, uvs): l[uvl].uv = (u / TW, v / TH)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    return F.mesh_part(name, bm)

def tube(cx, cy, zb, paint):
    """A stave tube standing on a deck at height zb: staves, a hoop at each end, the painted band (paint = swatch index or
    'hemp' for a spare tube)."""
    rm = TA - TT / 2
    w = 2 * rm * math.tan(math.pi / NS) - 0.003
    for k in range(NS):
        a = 2 * math.pi * k / NS
        dz = -0.001 - (0.004 if k % 2 else 0.0)          # alternate staves 4 mm lower: no coplanar tops (as fletcher_r2)
        F.stave((w, TT, TH_ + 0.002), (cx + rm * math.cos(a), cy + rm * math.sin(a), zb + TH_ / 2 + dz), math.degrees(a) - 90)
    for z0, z1 in ((0.03, 0.09), (TH_ - 0.07, TH_ - 0.01)):
        ring2("hoop", cx, cy, NS, TA + 0.001, HOOP_T, zb + z0, zb + z1, "iron")
    ring2("band", cx, cy, NS, TA + 0.001, 0.006, zb + 0.30, zb + 0.38, "hemp" if paint == "hemp" else f"pnt{paint}")

def straw_disc(cx, cy, z, copies_bvh, rings=(0.04, 0.08, 0.115), sectors=16):
    """The straw bed seen from above: a polar grid out to the staves at height z, tufted +-7 mm, every triangle any arrow
    would touch left out."""
    pr = random.Random(int(cx * 1000 + cy * 100) + 7)
    rad = list(rings)
    def edge_r(a):
        da = (a + math.pi / NS) % (2 * math.pi / NS) - math.pi / NS
        return (R_IN - 0.002) / math.cos(da)
    P = [(cx, cy, z + 0.006)]
    for i, r in enumerate(rad + [None]):
        for k in range(sectors):
            a = 2 * math.pi * (k + 0.5 * (i % 2)) / sectors
            rr = edge_r(a) if r is None else r
            P.append((cx + rr * math.cos(a), cy + rr * math.sin(a), z + (0.0 if r is None else pr.uniform(-0.007, 0.007))))
    T = []
    for k in range(sectors): T.append((0, 1 + k, 1 + (k + 1) % sectors))
    for i in range(len(rad)):
        a0, b0 = 1 + i * sectors, 1 + (i + 1) * sectors
        for k in range(sectors):
            k1 = (k + 1) % sectors
            T.append((a0 + k, b0 + k, a0 + k1)); T.append((a0 + k1, b0 + k, b0 + k1))
    tree = BVHTree.FromPolygons(P, T, all_triangles=True)
    hit = set()
    for b in copies_bvh:
        for i, _ in tree.overlap(b): hit.add(i)
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.verify()
    vs = [bm.verts.new(p) for p in P]
    for ti, t in enumerate(T):
        if ti in hit: continue
        f = bm.faces.new([vs[i] for i in t])
        f.normal_update()
        if f.normal.z < 0: f.normal_flip()
        u0, v0 = 1 + pr.randrange(22), 33 + pr.randrange(8)
        for l, (du, dv) in zip(f.loops, ((0, 0), (4, 0), (2, 5))): l[uvl].uv = ((u0 + du) / TW, (v0 + dv) / TH)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    return F.mesh_part("straw", bm), len(hit)

def bx(name, x0, x1, y0, y1, z0, z1, kind="hewn", jitter=0.003, bevel=0.012, rot=(0, 0, 0)):
    return box(name, (x1 - x0, y1 - y0, z1 - z0), ((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2), kind=kind, rot=rot, jitter=jitter, bevel=bevel)

def build_frame():
    # ---- base: five skids front to back, iron caps on both ends ----
    for x in (-1.0, -0.5, 0.0, 0.5, 1.0):
        bx("skid", x - SK_W / 2, x + SK_W / 2, Y_F, Y_B, 0.0, SK_H + KISS, jitter=0.003, bevel=0.014)
        for yf, sg in ((Y_F, -1), (Y_B, 1)):
            F.plate_y(x - 0.05, x + 0.05, 0.012, SK_H - 0.012, yf, sg, rivets=[(x, SK_H / 2)])
    # ---- decks: planks along x on each tier ----
    def deck(y0, y1, k, n):
        gap = 0.004
        bw = ((y1 - y0) - (n - 1) * gap) / n
        for i in range(n):
            ya = y0 + i * (bw + gap)
            bx("deck", -XI - KISS, XI + KISS, ya, ya + bw, DECK[k] - DT, DECK[k], kind="plank", jitter=0.0, bevel=0.008)
    deck(Y_F, YB1 + KISS, 0, 5)
    deck(YB1, YB2 + KISS, 1, 4)
    deck(YB2, Y_B - 0.06 + KISS, 2, 4)
    # ---- risers: two hewn planks between the tiers (front faces at the tier boundaries), iron straps with rivets ----
    for k, yb in ((1, YB1), (2, YB2)):
        z0, z1 = DECK[k - 1], DECK[k] - DT
        zm = (z0 + z1) / 2
        bx("riser", -XI - KISS, XI + KISS, yb, yb + 0.045, z0 - KISS, zm, kind="hewn", jitter=0.0, bevel=0.010)
        bx("riser", -XI - KISS, XI + KISS, yb, yb + 0.045, zm, z1 + KISS, kind="hewn", jitter=0.0, bevel=0.010)
        for x in (-0.9, -0.45, 0.0, 0.45, 0.9):
            F.plate_y(x - 0.05, x + 0.05, z0 + 0.03, z1 - 0.03, yb, -1, rivets=[(x, z0 + 0.075), (x, z1 - 0.075)])
    # ---- front sill beam on the lowest deck, with iron straps ----
    bx("sill", -XI - KISS, XI + KISS, Y_F, Y_F + 0.09, DECK[0] - KISS, DECK[0] + 0.10, jitter=0.003, bevel=0.012)
    for x in (-1.0, -0.5, 0.0, 0.5, 1.0):
        F.plate_y(x - 0.05, x + 0.05, DECK[0] + 0.012, DECK[0] + 0.088, Y_F, -1, rivets=[(x, DECK[0] + 0.05)])
    # ---- the sides: stepped cheeks, a cap beam on each tier ----
    ys = [(Y_F + PS, YB1), (YB1, YB2), (YB2, Y_B - PS)]
    for sx in (-1, 1):
        xa, xb = sorted((sx * XI, sx * (XI + CK_T)))
        for k, (y0, y1) in enumerate(ys):
            ya = y0 - (KISS if k == 0 else 0.0); yb = y1 + (KISS if k == 2 else 0.0)
            bx("cheek", xa, xb, ya, yb, 0.0, DECK[k], jitter=0.002, bevel=0.012)
            xca, xcb = sorted((sx * (XI - 0.004), sx * (XI + CK_T + 0.006)))
            bx("cap", xca, xcb, ya, yb, DECK[k], DECK[k] + 0.10, jitter=0.002, bevel=0.012)
            xo = sx * (XI + CK_T + 0.006)
            ym = (y0 + y1) / 2
            F.plate_x(ym - 0.09, ym + 0.09, DECK[k] + 0.012, DECK[k] + 0.088, xo, sx, rivets=[(ym + dy, DECK[k] + 0.05) for dy in (-0.05, 0.05)])
            if k:
                F.plate_x(ym - 0.09, ym + 0.09, 0.03, DECK[k] - 0.03, sx * (XI + CK_T), sx,
                          rivets=[(ym + dy, (0.03 + DECK[k] - 0.03) / 2) for dy in (-0.05, 0.05)])
    # ---- four posts with iron bands, flush with the bounds ----
    for sx in (-1, 1):
        xa, xb = sorted((sx * XI, sx * (XI + PS)))
        for (ya, yb, h, bands) in ((Y_F, Y_F + PS, H_FRONT, [(0.02, 0.08), (H_FRONT - 0.10 - 0.004, 0.10)]),
                                   (Y_B - PS, Y_B, H_BACK, [(0.02, 0.08), (0.62, 0.08), (H_BACK - 0.10 - 0.004, 0.10)])):
            bx("post", xa, xb, ya, yb, 0.0, h, jitter=0.002, bevel=0.012)
            for z0, bh in bands:
                bx("band", xa - INS, xb + INS, ya - INS, yb + INS, z0, z0 + bh, kind="iron", jitter=0.0, bevel=0.0)
    # ---- the back: top beam, mid rail, three studs, riveted plates; knee braces from the back posts onto the top cap beams ----
    yb0, yb1 = Y_B - 0.10, Y_B
    zs = [SK_H - KISS, SK_H + (DECK[2] - SK_H) / 3, SK_H + 2 * (DECK[2] - SK_H) / 3, DECK[2]]
    for a, b in zip(zs[:-1], zs[1:]):
        bx("skirt", -XI - KISS, XI + KISS, Y_B - 0.06, Y_B, a, b, kind="hewn", jitter=0.0, bevel=0.010)
    bx("topbeam", -XI - KISS, XI + KISS, yb0, yb1, H_BACK - 0.12, H_BACK, jitter=0.003, bevel=0.014)
    bx("midrail", -XI - KISS, XI + KISS, yb0, yb1, 0.83, 0.93, jitter=0.003, bevel=0.012)
    for x in (-0.55, 0.0, 0.55):
        bx("stud", x - 0.05, x + 0.05, yb0, yb1, DECK[2] - KISS, 0.83 + KISS, jitter=0.002, bevel=0.012)
        bx("stud", x - 0.05, x + 0.05, yb0, yb1, 0.93 - KISS, H_BACK - 0.12 + KISS, jitter=0.002, bevel=0.012)
        for z0, z1 in ((0.835, 0.925),):
            F.plate_y(x - 0.09, x + 0.09, z0, z1, yb1, 1, rivets=[(x + dx, (z0 + z1) / 2) for dx in (-0.05, 0.05)])
        F.plate_y(x - 0.09, x + 0.09, H_BACK - 0.115, H_BACK - 0.005, yb1, 1, rivets=[(x + dx, H_BACK - 0.06) for dx in (-0.05, 0.05)])
    for sx in (-1, 1):
        xc = sx * (XI + CK_T / 2 + 0.003)
        a, b = (Y_B - PS, 0.98), (YB2 + 0.04, DECK[2] + 0.10)
        L = math.hypot(a[0] - b[0], a[1] - b[1]); ang = math.degrees(math.atan2(a[1] - b[1], a[0] - b[0]))
        box("brace", (CK_T - 0.02, L + 0.05, 0.09), (xc, (a[0] + b[0]) / 2, (a[1] + b[1]) / 2), rot=(ang, 0, 0), jitter=0.002, bevel=0.012)

def build_tubes(hits_fn):
    """The 20 tubes; hits_fn(i) -> list of BVHs of the arrows standing in tube i (cut out of the straw)."""
    cut = {}
    for i, (r, cx, cy, zb) in enumerate(TUBES):
        k = KIND_OF[i]
        tube(cx, cy, zb, PAINT_IDX[k] if k else "hemp")
        _, nhit = straw_disc(cx, cy, zb + STRAW_OFF, hits_fn(i))
        cut[i] = nhit
    return cut

# ---------- packing: one layout of 4 bundles x PER arrows, packed against every ripped arrow model at once ----------
# Joost wants dense bundles (13 arrows a stack, 52 a tube). Packed mesh against mesh with no touching at all, a tube of this size
# holds 7 of these arrows (R 0.123) or 20 (R 0.19), as in fletcher_r2. So the arrows of a bundle interleave the way a real bundle does,
# and the rule is: (1) no arrow touches the frame, a tube or the straw, anywhere; (2) no arrow touches a neighbour in the part you
# can see (above the straw surface; below it everything is hidden in the tube); (3) a copy that cannot be placed without
# touching is allowed to touch at most CAP neighbours, tightest first. The result is counted and reported.
BUNDLE_R = 0.056                                       # bundle centres' distance from the tube axis
BUNDLE_ANG = [0.0, math.pi, math.pi / 2, 3 * math.pi / 2]       # fill order: opposite pairs
ZCUT = STRAW_OFF - FLOOR_OFF                           # the straw surface over the tube head: below it nothing is seen
TPLT = {}

FAT_R = 0.018                                          # beyond this distance from the shaft (m, fitted size) a triangle is fletching or head

def fat_mask(name):
    """Which triangles of the visible mesh are fletching or head (farther than FAT_R from the shaft axis) rather than shaft."""
    t = F.TPL[name]
    Vi = t["Vi"]; size = t["s"]
    il = int(np.argmax(size)); tr = [i for i in range(3) if i != il]
    med = np.median(Vi[:, tr], axis=0)
    r = np.hypot(Vi[:, tr[0]] - med[0], Vi[:, tr[1]] - med[1]) * (F.LONG["arrow"] / size.max())
    T = np.array(t["T"])
    return (r[T] > FAT_R).any(1)

def vis_bvh(name, Wv):
    """The part of an arrow that can touch a neighbour visibly: fletching and head triangles above the straw surface."""
    if name not in TPLT: TPLT[name] = (np.array(F.TPL[name]["T"]), fat_mask(name))
    T, fat = TPLT[name]
    keep = fat & (Wv[T, 2].max(1) > ZCUT)
    if not keep.any(): keep = Wv[T, 2].max(1) > ZCUT
    return BVHTree.FromPolygons(Wv.tolist(), T[keep].tolist(), all_triangles=True)

APEX_Z = 0.32                                          # over the tube head: every arrow of a bundle passes this point (just under the straw)
ALPHA = 4.5                                            # half angle (degrees) of a bundle's cone
HALF = 0.43                                            # half the fitted arrow length: the arrow turns about its centre

def cone_copy(cx, cz, m, rnd, lv, alpha, beta, out_phi, jit):
    """Copy m of a bundle: a shaft through the bundle's apex (cx, APEX_Z, cz), lv metres up from its foot, leaning from the
    vertical by the bundle's outward tilt beta plus its place in the cone (a golden-angle spiral over the cone half angle alpha).
    Returns (off, R) in Unity holder space (off = where F.place_u wants the foot: the arrow turns about its centre)."""
    psi = m * 2.399963 + jit * rnd.uniform(-0.5, 0.5)
    th = math.radians(alpha) * math.sqrt((m + 0.5) / PER) * (1 + jit * rnd.uniform(-0.2, 0.2))
    hx = math.tan(math.radians(beta)) * math.cos(out_phi) + math.tan(th) * math.cos(psi)
    hz = math.tan(math.radians(beta)) * math.sin(out_phi) + math.tan(th) * math.sin(psi)
    phi = math.atan2(hz, hx); tt = math.atan(math.hypot(hx, hz))
    R = F.Rlean(phi, tt) @ F.Ry(rnd.uniform(0, 2 * math.pi))
    d = R @ np.array([0.0, 1.0, 0.0])
    apex = np.array([cx, APEX_Z, cz])
    C = apex + (HALF - lv) * d
    return np.array([C[0], C[1] - HALF, C[2]]), R

def try_copy3(placed, off, R, cap, kinds):
    off = np.array(off, float)
    c = F.copy_dict("arrow", off, R)
    Ws = {k: F.world(k, F.place_u((0, 0, 0), c, k)) for k in kinds}
    low = min(Ws[k][:, 2].min() for k in kinds)
    if low < 0.002:
        off[1] += 0.002 - low
        for k in kinds: Ws[k][:, 2] += 0.002 - low
    for k in kinds:
        Wv = Ws[k]; dd = np.hypot(Wv[:, 0], Wv[:, 1])
        if (dd[Wv[:, 2] < RIM_H + 0.01] > R_IN - 0.004).any() or (dd > R_LIM).any(): return None
    mine, worst = {}, 0
    for k in kinds:
        Wv = Ws[k]; lo, hi = Wv[Wv[:, 2] > ZCUT].min(0), Wv.max(0)
        bv = vis_bvh(k, Wv)
        n = 0
        for _, _, o in placed:
            if (lo <= o[k][3]).all() and (o[k][2] <= hi).all() and bv.overlap(o[k][1]): n += 1
        worst = max(worst, n)
        if worst > cap: return None
        mine[k] = (Wv, bv, lo, hi)
    return off, mine, worst

def pack_tube(seed, alpha=None, beta=0.0, pool=60, cap_max=40, ang0=0.0, levels=LEVELS, bundle_r=None):
    rnd = random.Random(seed)
    alpha = ALPHA if alpha is None else alpha
    bundle_r = BUNDLE_R if bundle_r is None else bundle_r
    kinds = F.FAM["arrow"]
    placed = []
    angs = [a + ang0 for a in BUNDLE_ANG[:UNITS_PER]]
    centres = [(bundle_r * math.cos(a), bundle_r * math.sin(a)) for a in angs]
    lost, touches = 0, 0
    bucket = {u: [] for u in range(UNITS_PER)}
    lvl = list(levels)
    for m in range(PER):                                   # one arrow of every bundle at a time
        for u in range(UNITS_PER):
            cx, cz = centres[u]
            got = None
            for cap in range(cap_max + 1):
                # the first `pool` candidates that fit with at most cap touches; of the passing ones the fewest touches wins
                tried = 0
                for _ in range(pool):
                    lv = rnd.choice(lvl)
                    off, R = cone_copy(cx, cz, m, rnd, lv, alpha, beta, angs[u], 1.0)
                    g = try_copy3(placed, off, R, cap, kinds)
                    if g and (got is None or g[2] < got[2]): got, gR = g, R
                    if got and got[2] == 0: break
                if got: R = gR; break
            if not got:
                lost += 1; continue
            touches += got[2]
            placed.append((got[0], R, got[1])); bucket[u].append((got[0], R))
    return bucket, lost, touches

def best_layout(seed0, tries=3):
    best = None
    for t in range(tries):
        t0 = time.time()
        b, lost, touches = pack_tube(seed0 + t * 17, ang0=random.Random(seed0 + t).uniform(0, 1.2))
        print(f"PACK seed {seed0 + t * 17}: lost {lost} of {PER * UNITS_PER}, neighbour contacts placed {touches} ({time.time() - t0:.0f}s)", flush=True)
        if best is None or (lost, touches) < (best[1], best[2]): best = (b, lost, touches)
    return best

LAY_STATS = []
def load_or_pack(n_lay, repack):
    if os.path.exists(CACHE) and not repack:
        d = json.load(open(CACHE))
        if d.get("per") == PER and d.get("units") == UNITS_PER and len(d["layouts"]) >= n_lay:
            print("LAYOUTS from cache", CACHE, flush=True)
            LAY_STATS[:] = d.get("stats", [])
            return [[[(np.array(o), np.array(R)) for o, R in bu] for bu in lay] for lay in d["layouts"][:n_lay]]
    lays = []
    LAY_STATS.clear()
    for li in range(n_lay):
        b, lost, touches = best_layout(100 + 31 * li)
        LAY_STATS.append({"lost": lost, "visible_fletching_head_contacts": touches})
        if lost: print("WARNING layout", li, "lost", lost, flush=True)
        lays.append([b[u] for u in range(UNITS_PER)])
    os.makedirs(SCRATCH, exist_ok=True)
    json.dump({"per": PER, "units": UNITS_PER, "stats": LAY_STATS, "layouts": [[[(o.tolist(), R.tolist()) for o, R in bu] for bu in lay] for lay in lays]}, open(CACHE, "w"))
    return lays

# ---------- units ----------
def make_units(lays):
    units = []
    for ti, (r, cx, cy, zb) in enumerate(TUBES):
        lay = lays[ti % len(lays)]
        fz = zb + FLOOR_OFF
        Rh = F.Ry(ti * 1.3 + 0.4)
        cu = np.array([-cx, fz, -cy])
        k = KIND_OF[ti]
        for u in range(UNITS_PER):
            mine = [(cu + Rh @ off, Rh @ R) for off, R in lay[u]]
            if not mine: continue
            P = np.array([o for o, _ in mine])
            upos = np.array([P[:, 0].mean(), fz, P[:, 2].mean()])
            units.append({"index": len(units), "compartment": ti, "item": k, "kind": "arrow", "step": u, "band": BAND[k][0] if k else "hemp rope (spare)",
                          "position": [round(float(a), 5) for a in upos], "rotation": [0.0, 0.0, 0.0],
                          "box": [round(float(np.ptp(P[:, 0])) + 0.06, 3), F.LONG["arrow"], round(float(np.ptp(P[:, 2])) + 0.06, 3)],
                          "render_item": k or "ArrowFlint", "copies": [F.copy_dict("arrow", o - upos, R) for o, R in mine]})
    return units

# ---------- checks ----------
def run_checks(units, frame):
    V, T = tri_list(frame.data)
    fbvh = BVHTree.FromPolygons(V, T, all_triangles=True)
    res = {}
    byg = {}
    for u in units: byg.setdefault(u["compartment"], []).append(u)
    for k in F.FAM["arrow"]:
        clip, over, n = 0, 0, 0
        for g, us in byg.items():
            Ws = [w for u in us for w in F.unit_worlds(u, k)]
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
    """A filled store (fill: unit index -> kind): every copy against the frame and against every copy of every other tube."""
    V, T = tri_list(frame.data)
    fbvh = BVHTree.FromPolygons(V, T, all_triangles=True)
    items = []
    for i, k in fill.items():
        u = units[i]
        for w in F.unit_worlds(u, k): items.append((u["compartment"], k, w, F.bvh(k, w), w.min(0), w.max(0)))
    clip = sum(1 for it in items if fbvh.overlap(it[3]))
    cross = 0
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            a, b = items[i], items[j]
            if a[0] == b[0] or not ((a[4] <= b[5]).all() and (b[4] <= a[5]).all()): continue
            if a[3].overlap(b[3]): cross += 1
    top = max(float(it[2][:, 2].max()) for it in items) if items else 0.0
    return {"copies": len(items), "frame_clipping": clip, "between_tubes": cross, "contents_top_z": round(top, 3)}

def mesh_tris(me): return sum(len(p.vertices) - 2 for p in me.polygons)

# ---------- main ----------
if __name__ == "__main__":
    os.makedirs(OUTA, exist_ok=True); os.makedirs(OUT, exist_ok=True); os.makedirs(SCRATCH, exist_ok=True)
    setup_scene()
    atlas = build_atlas()
    base.MAT = make_material("arrowtubes", atlas)
    base.PARTS.clear()
    base.uv_face = my_uv
    t0 = time.time()
    for k in F.FAM["arrow"]: F.load_tpl(k)
    print("MODELS loaded", round(time.time() - t0), "s; triangles per model", {k: mesh_tris(F.TPL[k]["mesh"]) for k in F.FAM["arrow"]}, flush=True)
    N_LAY = int(arg("--layouts", 2))
    lays = load_or_pack(N_LAY, "--repack" in argv)
    units = make_units(lays)
    byt = {}
    for u in units: byt.setdefault(u["compartment"], []).append(u)
    def hits(i):
        return [F.bvh(k, w) for u in byt[i] for k in F.FAM["arrow"] for w in F.unit_worlds(u, k)]
    build_frame()
    straw_cut = build_tubes(hits)
    print("STRAW holes (triangles left out) per tube", straw_cut, flush=True)
    cop = F.report_coplanar([(o.name, o.data) for o in base.PARTS], "frame")
    if "--frame-only" in argv: sys.exit(0)
    frame = join(list(base.PARTS), "ArrowTubes")
    ftris = tris(frame)
    bb = np.array([tuple(v.co) for v in frame.data.vertices])
    print(f"FRAME tris {ftris} bounds {bb.min(0).round(4)} {bb.max(0).round(4)}", flush=True)
    chk = run_checks(units, frame)

    fill_full = {u["index"]: model_of(u["item"]) for u in units if u["item"]}
    xc = cross_check(units, fill_full, frame)
    print("CROSS full", json.dumps(xc), flush=True)
    HALF_N = {0: 2, 1: 3, 2: 1}
    fill_half = {u["index"]: model_of(u["item"]) for u in units if u["item"] and u["step"] < HALF_N[u["compartment"] % 3]}
    contents_tris = sum(mesh_tris(F.TPL[k]["mesh"]) * len(units[i]["copies"]) for i, k in fill_full.items())
    print("CONTENTS full (arrows drawn):", sum(len(units[i]["copies"]) for i in fill_full), "tris", contents_tris, "frame+contents", ftris + contents_tris, flush=True)

    base.save_atlas(atlas, os.path.join(OUTA, "arrowtubes_atlas.png"))
    export_obj(frame, os.path.join(OUTA, "ArrowTubes.obj"))
    doc = {
        "schema": "storehouse-anchors/1", "furniture": "Arrow Tubes", "slug": "arrowtubes", "round": 1, "placement": "ground",
        "unit_count": len(units), "slots_designed_for": len(units), "stack_per_unit": True, "mirror": False, "heap": False,
        "frame": {"obj": "ArrowTubes.obj", "atlas": "arrowtubes_atlas.png 128x128 point", "tris": ftris, "size_m": [round(W, 3), H_BACK, round(D, 3)],
                  "bounds_unity": {"min": [-W / 2, 0.0, -Y_B], "max": [W / 2, H_BACK, -Y_F]}, "contents_top_y_full": xc["contents_top_z"],
                  "tris_full_contents": contents_tris,
                  "stacking": "not stackable: a stepped ground store whose arrows stand above the frame (to ~1.9 m)."},
        "space": {"unity": "prefab space, origin on the floor at the centre of the footprint, +z front, +y up, +x to the furniture's left seen from the front",
                  "from_blender": "ux=-bx, uy=bz, uz=-by"},
        "groups": {"key": "compartment", "0-6": "front row (lowest step), left to right seen from the front: ordinary arrows; tube 6 is a spare",
                   "7-12": "middle row: fire, surtling fire, poison, frost, silver, needle",
                   "13-19": "back row (highest step): carapace, chitin, charred, green metal, ancient; tubes 18 and 19 are spares",
                   "rule": "one arrow kind per tube (unit 'item' = the kind; the 3 spare tubes have no item and take any other arrow in a "
                           "ByGroup store). Units are listed tube by tube, 4 per tube, in fill order."},
        "homes": [{"compartment": i, "item": KIND_OF[i], "row": TUBES[i][0], "band": BAND[KIND_OF[i]][0] if KIND_OF[i] else "hemp rope (spare)"}
                  for i in range(NT)],
        "band": {k: BAND[k][0] for k in KINDS},
        "band_spare": "hemp rope (unpainted) on the 3 spare tubes",
        "fill_order": "each tube's 4 units (bundles) in order: opposite pairs (a half-full tube is balanced); each is one stack of %d arrows." % PER,
        "position": "unit position = mean of its copies' feet, on the floor of its tube (the tube head, deck + 0.07). box = [x, y, z] Unity, informational.",
        "copy_rule": "align (long axis -> up, thin axis -> x), then_rotate = a lean of 1-4 degrees times a spin about the shaft, fit_longest_m 0.86, "
                     "anchor bottom, offset.y = the foot height in the straw (0 .. 0.30 in steps of 0.05) plus the lift a lean needs. The same "
                     "layout (two of them, spun by a different angle per tube) serves every arrow kind.",
        "straw": "each tube holds a straw bed 0.10 under its rim; the surface is part of the frame with each triangle any arrow of any ripped model touches cut away.",
        "heads": {**F.HEADS, "why": "as fletcher_r2: Align.Axes turns the item's +long axis to up and the models differ in sign; the ValheimArmory arrows and ArrowNeedle are unripped, their head direction is not known."},
        "items": {"arrow_size": "fitted to 0.86 m like fletcher_r2 (an arrow item is 1.63-1.84 m in the game, 0.47x flint)",
                  "checked_models": F.FAM["arrow"],
                  "not_checked": {"ArrowNeedle": "built-in Quads, not ripped", "VAArrowBone/VAarrow_surtling_fire/VAArrowGreenMetal/VAChitinArrow/VAArrowAncient":
                                  "ValheimArmory asset bundles, not ripped; the renders use stand-ins " + json.dumps(STAND_IN)}},
        "layout": {"tubes": NT, "rows": [{"y_blender": y, "tubes": n, "deck_z": DECK[i]} for i, (y, n) in enumerate(ROWS)],
                   "pitch_m": PITCH, "stave_apothem_outer_m": TA, "stave_height_m": TH_, "inner_radius_m": round(R_IN, 3), "arrows_per_unit": PER,
                   "units_per_tube": UNITS_PER, "foot_levels_m": list(LEVELS), "bundle_apex_height_m": APEX_Z, "bundle_cone_half_angle_deg": ALPHA,
                   "copies_full": len(units) * PER, "layouts": LAY_STATS,
                   "density": "52 arrows of 0.86 m do not fit a tube of inner radius %.3f without touching: packed mesh against mesh with no touching at all, "
                              "fletcher_r2's rule, 7 fit at this radius and 20 at r2's barrel radius 0.19 (measured, all 11 models at once). So the bundles "
                              "interleave like real ones: no arrow touches the frame, a tube or the straw (0, checked); arrows of one bundle touch each other "
                              "(the layouts count the visible fletching and head contacts above the straw, 'layouts'; checks.per_model counts every triangle "
                              "pair incl. shafts)." % R_IN},
        "checks": {"coplanar_frame": cop, "per_model": chk, "full_store": xc, "method": "mesh against mesh (BVH): every copy of every ripped arrow model against the frame and every other copy in its tube; the full fill also across tubes."},
        "units_data": units}
    write_json_atomic(doc, os.path.join(OUTA, "arrowtubes_anchors.json"))     # last: the mod live-reloads
    print("WROTE", OUTA, flush=True)
    if "--no-render" in argv: sys.exit(0)

    # ---------------- renders: arrow tubes (empty, half, full) beside fletcher_r2 (its barrels full) and bunker_r4 ----------------
    def spawn(dx, fill):
        fr = frame.copy(); bpy.context.scene.collection.objects.link(fr); fr.hide_render = False; fr.location = (dx, 0, 0)
        for i, k in fill.items():
            for c in units[i]["copies"]:
                ob = bpy.data.objects.new(k, F.TPL[k]["mesh"]); bpy.context.scene.collection.objects.link(ob)
                ob.matrix_world = Matrix.Translation((dx, 0, 0)) @ Matrix((F.B4 @ F.place_u(units[i]["position"], c, k) @ F.K4).tolist())
    X_EMPTY, X_HALF, X_FULL, X_FL, X_BUNK = -8.4, -4.2, 0.0, 5.8, 11.4
    spawn(X_EMPTY, {}); spawn(X_HALF, fill_half); spawn(X_FULL, fill_full)
    frame.hide_render = True
    # fletcher_r2 beside, with the arrows of its full render
    before = set(bpy.data.objects)
    bpy.ops.wm.obj_import(filepath=os.path.join(ASSETS, "fletcher_r2", "Fletcher.obj"), forward_axis="NEGATIVE_Z", up_axis="Y",
                          use_split_objects=False, use_split_groups=False)
    fl = [o for o in bpy.data.objects if o not in before][0]; fl.location.x = X_FL
    fimg = bpy.data.images.load(os.path.join(ASSETS, "fletcher_r2", "fletcher_atlas.png"))
    fl.data.materials.clear(); fl.data.materials.append(make_material("fletcher", fimg))
    fa = json.load(open(os.path.join(ASSETS, "fletcher_r2", "fletcher_anchors.json")))
    FL_FILL = {0: "ArrowFlint", 1: "ArrowFlint", 2: "ArrowPoison", 3: "ArrowIron", 4: "ArrowFire", 5: "ArrowCarapace"}
    for u in fa["units_data"]:
        k = FL_FILL.get(u["crate"])
        if not k: continue
        for c in u["copies"]:
            ob = bpy.data.objects.new(k, F.TPL[k]["mesh"]); bpy.context.scene.collection.objects.link(ob)
            ob.matrix_world = Matrix.Translation((X_FL, 0, 0)) @ Matrix((F.B4 @ F.place_u(u["position"], c, k) @ F.K4).tolist())
    # bunker r4 beside, same scale (its own atlas)
    before = set(bpy.data.objects)
    bpy.ops.wm.obj_import(filepath=os.path.join(ASSETS, "bunker_r4", "Bunker.obj"), forward_axis="NEGATIVE_Z", up_axis="Y",
                          use_split_objects=False, use_split_groups=False)
    bk = [o for o in bpy.data.objects if o not in before][0]; bk.location.x = X_BUNK
    bimg = bpy.data.images.load(os.path.join(ASSETS, "bunker_r4", "bunker_atlas.png"))
    bk.data.materials.clear(); bk.data.materials.append(make_material("bunker", bimg))
    references(chest_x=X_FULL + 2.55, post_x=X_FULL - 1.9)
    views = {"empty": (-24, 18, 7.2, (X_EMPTY, 0, 0.55), 40),
             "half": (-24, 18, 7.2, (X_HALF, 0, 0.8), 40),
             "full": (-24, 18, 7.2, (X_FULL, 0, 0.85), 40),
             "compare": (-12, 14, 17.0, ((X_FULL + X_BUNK) / 2 - 0.2, 0, 0.8), 30),
             "front": (0, 8, 6.6, (X_FULL, 0, 0.85), 40),
             "top": (-6, 58, 5.2, (X_FULL, 0, 0.7), 40),
             "bands": (-14, 28, 3.3, (X_FULL - 0.2, -0.2, 0.55), 45),
             "bundles": (-10, 36, 1.6, (X_FULL - 0.6, -0.34, 0.75), 45),
             "back": (150, 20, 6.6, (X_FULL, 0, 0.85), 40),
             "side": (-90, 8, 6.6, (X_FULL, 0, 0.85), 40)}
    lights_and_render(OUT, "arrowtubes", views)
    print("DONE", flush=True)
