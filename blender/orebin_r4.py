"""Ore Bin round 4: bunker-sized (3.85 x 1.95 m incl. iron bands, back posts 1.65 m), ore at about half true size. Our own furniture mesh and own
128x128 atlas; the CONTENTS are the game's own item models, PHYSICALLY SETTLED with Blender rigid bodies (convex-hull items
dropped stack by stack in fill order into six stone-lined compartments, one item type per compartment).
Run: blender -b -P orebin_r4.py -- [--out DIR] [--assets DIR] [--tag NAME] [--quick] [--no-render] [--views a,b] [--frame-only]
     [--nc CopperOre:3/2,TinOre:2,...]   copies per stack override, cycled per stack (tuning)   [--cseed N] contents seed
Renders (in --out): fills (empty / 50% / full + 1.8 m post), empty, half, full, top, bunker (beside the Coal & Stone Bunker
round 3), r3 (beside Ore Bin round 3), scale (1.8 m post at the full bin). The bunker and r3 rows, and the r4 bin beside
them, are replayed from their EXPORTED OBJ + anchors files (the mod's path: unit.position + copy.offset).

Why round 4: next to the Coal & Stone Bunker (3.94 x 1.89 x 1.86 m, lumps at 0.40-0.60 of their true size) round 3 was small
(2.2 x 1.6 x 1.1 m) and its ore was 0.15-0.30 of true size. Round 4 matches the bunker's footprint and its lump size.

Furniture: a stepped, open-top bin, deliberately lower than the bunker (1.6 m at the back posts, 0.78 m front lip) because
you shovel ore in from the front and should see every heap from where you stand. Three columns x two rows of compartments.
The front row sits on the floor (0.14 m), the back row on a raised plank deck (0.30 m) behind a four-course stone cross wall,
so its heaps show over the front row. The side walls and dividers step up course by course towards the back (0.76 -> 0.96 ->
1.17 -> 1.37 m of stone), the bunker's rising silhouette in masonry. Heavy timber posts on every bay line, rough stone-block
lining, sloped plank front with iron straps, timber caps, iron rim on the back and outer walls, iron bands and post caps.
Contents: 80 units (one unit = one full stack of one ore/scrap), each unit = 1-3 copies of that item's real model (NCOPY: as
many as the compartment holds below its walls). One scale per item type (SCALE below, 0.36-0.50 of true size, longest side
0.29-0.33 m; the bunker's coal/stone/flint are at 0.40-0.60, 0.23-0.35 m). Heaps: each copy is dropped on the lowest of 16
random spots (a shovel thrown into the low spot); a stack that ends up leaning above a visible wall top is dropped again.
The mod places the real item models at the anchors in orebin_anchors.json. The ripped item models under ValheimRip/items
are used for the renders only and are never exported.

Atlas 128x128, point-filtered, strips tile along u (v rows count from the bottom):
  rows 96-127 hewn timber side grain   rows 64-95 end grain (4 ring tiles)
  rows 32-63  stone blocks (4 tiles, one tile = one block face)   rows 0-31 iron
Unity prefab space: ux = -bx, uy = bz, uz = -by (Blender z-up, -y front). OBJ export forward NEGATIVE_Z, up Y gives
(bx, bz, -by); Unity's importer negates x, which is the same mapping.
Files are written atlas -> OBJ -> anchors (anchors last, via a temp file and a rename, so the mod's live reload never sees a
half-written round).
"""
import bpy, bmesh, sys, os, math, json, random, time
import numpy as np
from mathutils import Vector, Matrix, Euler, Quaternion
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, ".."))
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUTA = argv[argv.index("--assets") + 1] if "--assets" in argv else os.path.join(REPO, "assets", "orebin_r4")
OUT = argv[argv.index("--out") + 1] if "--out" in argv else OUTA
TAG = argv[argv.index("--tag") + 1] if "--tag" in argv else "orebin4"
QUICK = "--quick" in argv
NORENDER = "--no-render" in argv
FRAME_ONLY = "--frame-only" in argv
VIEWSEL = argv[argv.index("--views") + 1].split(",") if "--views" in argv else None
RIP = "C:/Users/joost/ValheimRip/chests/piece_chest_wood"
ITEMS_DIR = "C:/Users/joost/ValheimRip/items"
sys.path.append(ITEMS_DIR)
from load_item import load_item
os.makedirs(OUTA, exist_ok=True); os.makedirs(OUT, exist_ok=True)
rng = random.Random(31)       # frame
CSEED = int(argv[argv.index("--cseed") + 1]) if "--cseed" in argv else 41
crng = random.Random(CSEED)   # contents (own stream, so frame edits never reshuffle the heaps)

TW = TH = 128
DENS = 48.0
STRIP = {"hewn": 0.75, "end": 0.50, "stone": 0.25, "iron": 0.0}

# ---------- texture (same atlas recipe as round 3) ----------
def srgb(c): return np.array(c, dtype=np.float32)
WOOD, WOOD_D = srgb((0.38, 0.29, 0.18)), srgb((0.21, 0.16, 0.10))
END, END_D = srgb((0.55, 0.45, 0.31)), srgb((0.35, 0.27, 0.17))
IRON, IRON_D = srgb((0.22, 0.21, 0.20)), srgb((0.09, 0.09, 0.09))
STONES = [srgb(c) for c in ((0.38, 0.35, 0.31), (0.30, 0.29, 0.27), (0.41, 0.37, 0.31), (0.27, 0.27, 0.26))]
LICHEN = srgb((0.33, 0.36, 0.22))

def build_atlas():
    nr = np.random.default_rng(5)
    img = np.zeros((TH, TW, 3), np.float32)
    blocky = lambda h, w, s: np.kron(nr.random((h // s, w // s)), np.ones((s, s), np.float32))
    x = np.arange(TW)[None, :].repeat(32, 0).astype(np.float32)
    y = np.arange(32)[:, None].repeat(TW, 1).astype(np.float32)
    tile = lambda k: 2 * math.pi * k / TW
    g = np.sin(y * 1.25 + 1.6 * np.sin(x * tile(2) + y * 0.15) + 0.7 * np.sin(x * tile(5)))
    t = np.clip((g - 0.55) * 2.5, 0, 1) * 0.65 + nr.random((32, TW)) * 0.18
    t += np.clip(1 - np.minimum(y, 31 - y) / 3.0, 0, 1) * 0.35
    img[96:128] = WOOD * (1 - t[..., None]) + WOOD_D * t[..., None]
    for k in range(4):
        cx, cy = 15.5 + nr.uniform(-2, 2), 15.5 + nr.uniform(-2, 2)
        xx, yy = np.meshgrid(np.arange(32), np.arange(32))
        d = np.hypot(xx - cx, yy - cy) + 0.6 * np.sin(np.arctan2(yy - cy, xx - cx) * 3 + k)
        t = (np.sin(d * 1.5) * 0.5 + 0.5) * 0.45 + nr.random((32, 32)) * 0.15
        t = np.where(d > 13.5, 0.95, t)
        img[64:96, 32 * k:32 * k + 32] = END * (1 - t[..., None]) + END_D * t[..., None]
    xx, yy = np.meshgrid(np.arange(32), np.arange(32))
    edge = np.minimum(np.minimum(xx, 31 - xx), np.minimum(yy, 31 - yy))
    for k in range(4):
        base = STONES[k]
        t = blocky(32, 32, 8) * 0.40 + blocky(32, 32, 4) * 0.34 + blocky(32, 32, 2) * 0.18 + nr.random((32, 32)) * 0.14
        t = np.clip(t, 0, 1)
        tile_img = (base * 0.50) * (1 - t[..., None]) + np.clip(base * 1.20, 0, 1) * t[..., None]
        lm = (blocky(32, 32, 2) > 0.96)[..., None]
        tile_img = np.where(lm, tile_img * 0.55 + LICHEN * 0.45, tile_img)
        lit = ((yy >= 28) | (xx <= 3)) & (edge >= 3)
        tile_img = np.where(lit[..., None], np.clip(tile_img * 1.08, 0, 1), tile_img)
        tile_img = np.where((edge <= 2)[..., None], tile_img * 0.36, tile_img)
        tile_img = np.where((edge == 3)[..., None] & ~lit[..., None], tile_img * 0.75, tile_img)
        img[32:64, 32 * k:32 * k + 32] = tile_img
    t = nr.random((32, TW)) * 0.4 + np.clip(1 - np.minimum(y, 31 - y) / 4.0, 0, 1) * 0.5
    img[0:32] = IRON * (1 - t[..., None]) + IRON_D * t[..., None]
    im = bpy.data.images.new("orebin_atlas", TW, TH, alpha=False)
    px = np.concatenate([np.clip(img, 0, 1), np.ones((TH, TW, 1), np.float32)], 2)
    im.pixels.foreach_set(px.ravel())
    im.filepath_raw = os.path.join(OUTA, "orebin_atlas.png"); im.file_format = "PNG"; im.save()
    return im

# ---------- frame geometry ----------
PARTS = []

def uv_face(f, kind, long_axis, seed):
    n = f.normal
    ax = max(range(3), key=lambda i: abs(n[i]))
    tang = [i for i in range(3) if i != ax]
    cs = [l.vert.co for l in f.loops]
    if kind == "stone" or (kind == "hewn" and ax == long_axis):     # whole-tile mapping
        k = seed % 4
        c = sum(cs, Vector()) / len(cs)
        ext = max(max(abs(v[tang[0]] - c[tang[0]]), abs(v[tang[1]] - c[tang[1]])) for v in cs) or 1
        base = STRIP["stone"] if kind == "stone" else STRIP["end"]
        amp = 0.47 if kind == "stone" else 0.45
        for l in f.loops:
            a = (l.vert.co[tang[0]] - c[tang[0]]) / ext; b = (l.vert.co[tang[1]] - c[tang[1]]) / ext
            l[UV].uv = ((k + 0.5 + a * amp) / 4, base + (0.5 + b * amp) * 32 / TH)
        return
    spans = [max(v[i] for v in cs) - min(v[i] for v in cs) for i in tang]
    if kind == "hewn" and long_axis in tang: ua = long_axis
    else: ua = tang[0] if spans[0] >= spans[1] else tang[1]
    va = tang[1] if ua == tang[0] else tang[0]
    off = (seed * 0.37) % 1
    vmin = min(v[va] for v in cs); span = max(max(v[va] for v in cs) - vmin, 1e-4)
    vscale = min(1.0, (30 / DENS) / span)
    used = span * vscale * DENS
    shift = ((seed * 13) % 100) / 100 * max(0.0, 30 - used) if kind == "hewn" else 0.0
    base = STRIP[kind]
    for l in f.loops:
        u = l.vert.co[ua] * DENS / TW + off
        v = base + (1 + shift + (l.vert.co[va] - vmin) * vscale * DENS) / TH
        l[UV].uv = (u, v)

def box(name, size, pos, kind="hewn", rot=(0, 0, 0), jitter=0.02, bevel=0.02, rough=False):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2]))
    long_axis = max(range(3), key=lambda i: size[i])
    for v in bm.verts:
        for i in range(3):
            if rough or i != long_axis: v.co[i] += rng.uniform(-jitter, jitter)
    if bevel > 0:
        bmesh.ops.bevel(bm, geom=bm.edges[:], offset=bevel, segments=1, affect="EDGES")
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    bm.normal_update()
    global UV
    UV = bm.loops.layers.uv.verify()
    seed = rng.randrange(1000)
    for f in bm.faces: uv_face(f, kind, long_axis, seed)
    bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Euler([math.radians(a) for a in rot]).to_matrix())
    bmesh.ops.translate(bm, verts=bm.verts, vec=Vector(pos))
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = False
    ob = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(ob)
    ob.data.materials.append(MAT); PARTS.append(ob)

# ---- layout (Blender metres, z up, -y = front) ----
FLOOR = 0.14                             # front row floor (plank tops)
BACK_FLOOR = 0.30                        # back row: a raised plank deck, so its heaps show over the cross wall
ROWFLOOR = {0: FLOOR, 1: BACK_FLOOR}
HX, HY, PS = 1.90, 0.95, 0.22            # outer half sizes (3.80 x 1.90 m), post section
LIMX, LIMY = HX - PS, HY - PS            # interior half sizes 1.68 x 0.73
TWL = 0.20                               # outer stone wall thickness
COURSE = 0.205                           # one stone course
def LEV(n): return FLOOR + COURSE * n    # top of course n: 0.755, 0.96, 1.165, 1.37 for n = 3..6
DIVT = 0.12                              # stone dividers between the columns
CT = 0.16                                # stone cross wall between the rows
YC = -0.06                               # cross wall centre line
CELLW = (2 * LIMX - 2 * DIVT) / 3        # 1.04
DIVX = (-LIMX + CELLW + DIVT / 2, LIMX - CELLW - DIVT / 2)
POSTX = (-HX + PS / 2, DIVX[0], DIVX[1], HX - PS / 2)
YMIDSTEP = -0.40                         # side walls and dividers: course 3 starts here (rear half of the front row)
YSTEP5 = YC + 0.30                       # course 5 starts here (rear half of the back row)
# course c of the side walls and dividers runs from YSTART[c] to the back wall: a stair rising to the back
YSTART = [-LIMY, -LIMY, -LIMY, YMIDSTEP, YC - CT / 2, YSTEP5]
CAPH = 0.08
FRONT_TH = 8.0                           # front boards lean out by this many degrees
FRONT_RAIL_TOP = 0.785

def side_top(y):
    """stone top of a side wall / divider at y"""
    n = max(c for c in range(6) if y >= YSTART[c] - 1e-6) + 1
    return LEV(n)

def stone_run(a0, a1, cross, axis, zc, t, jit, name="stone"):
    """one course of rough blocks from a0 to a1 along axis ('x' or 'y'), centre line cross, course centre height zc"""
    a = a0 - rng.uniform(0.0, 0.25)
    while a < a1 - 0.03:
        w = rng.uniform(0.42, 0.70)
        lo, hi = max(a, a0), min(a + w, a1)
        if a1 - hi < 0.24: hi = a1
        if hi - lo > 0.12:
            zz = zc + rng.uniform(-0.006, 0.006)
            if axis == "x": box(name, (hi - lo - 0.02, t, COURSE - 0.02), ((lo + hi) / 2, cross, zz), kind="stone", jitter=jit, bevel=0.014, rough=True)
            else: box(name, (t, hi - lo - 0.02, COURSE - 0.02), (cross, (lo + hi) / 2, zz), kind="stone", jitter=jit, bevel=0.014, rough=True)
        a = hi if hi > a + 0.05 else a + w

def stone_wall(starts, a1, cross, axis, t, jit=0.012):
    """courses c = 0.. len(starts)-1, course c from starts[c] to a1. A dark core slab per course keeps the joints solid."""
    for c, a0 in enumerate(starts):
        zc = FLOOR + COURSE * (c + 0.5)
        if axis == "x": box("stonecore", (a1 - a0, t * 0.7, COURSE), ((a0 + a1) / 2, cross, zc), kind="stone", jitter=0.0, bevel=0)
        else: box("stonecore", (t * 0.7, a1 - a0, COURSE), (cross, (a0 + a1) / 2, zc), kind="stone", jitter=0.0, bevel=0)
        stone_run(a0, a1, cross, axis, zc, t, jit)

def stepped_caps(x, t, iron):
    """flat timber caps on every step of a side wall / divider, an iron strip on top for the outer walls"""
    bounds = [YSTART[3], YSTART[4], YSTART[5], LIMY]
    segs = [(-LIMY, bounds[0]), (bounds[0], bounds[1]), (bounds[1], bounds[2]), (bounds[2], LIMY + (TWL if iron else 0.0))]
    for y0, y1 in segs:
        top = side_top((y0 + y1) / 2 if y1 < LIMY else LIMY - 0.01)
        box("cap", (t + 0.04, y1 - y0 + 0.02, CAPH), (x, (y0 + y1) / 2, top + CAPH / 2), rot=(0, 0, rng.uniform(-0.3, 0.3)), jitter=0.004, bevel=0.008)
        if iron:
            box("rim", (t + 0.03, y1 - y0, 0.035), (x, (y0 + y1) / 2, top + CAPH + 0.0175), kind="iron", jitter=0.002, bevel=0.006)
            for yy in np.arange(y0 + 0.12, y1 - 0.08, 0.30):
                box("rivet", (0.04, 0.04, 0.03), (x, yy, top + CAPH + 0.045), kind="iron", jitter=0, bevel=0)

def build_frame():
    # posts: four on the front (low), four on the back (tall), two at the ends of the cross wall
    for x in POSTX:
        h = 1.00 + rng.uniform(-0.015, 0.015)
        box("post", (PS, PS, h), (x, -HY + PS / 2, h / 2), rot=(rng.uniform(-0.6, 0.6), rng.uniform(-0.6, 0.6), 0))
        box("postcap", (PS + 0.03, PS + 0.03, 0.04), (x, -HY + PS / 2, h + 0.01), kind="iron", jitter=0.002, bevel=0.005)
        box("band", (PS + 0.04, PS + 0.04, 0.08), (x, -HY + PS / 2, 0.42), kind="iron", jitter=0.003, bevel=0.006)
        h = 1.60 + rng.uniform(-0.015, 0.015)
        box("post", (PS, PS, h), (x, HY - PS / 2, h / 2), rot=(rng.uniform(-0.5, 0.5), rng.uniform(-0.5, 0.5), 0))
        box("postcap", (PS + 0.03, PS + 0.03, 0.04), (x, HY - PS / 2, h + 0.01), kind="iron", jitter=0.002, bevel=0.005)
        box("band", (PS + 0.04, PS + 0.04, 0.08), (x, HY - PS / 2, 0.42), kind="iron", jitter=0.003, bevel=0.006)
        box("band", (PS + 0.04, PS + 0.04, 0.08), (x, HY - PS / 2, 1.30), kind="iron", jitter=0.003, bevel=0.006)
    for sx in (-1, 1):
        x = sx * (HX - PS / 2); h = 1.22
        box("post", (PS, PS, h), (x, YC, h / 2), rot=(rng.uniform(-0.5, 0.5), rng.uniform(-0.5, 0.5), 0))
        box("postcap", (PS + 0.03, PS + 0.03, 0.04), (x, YC, h + 0.01), kind="iron", jitter=0.002, bevel=0.005)
        box("band", (PS + 0.04, PS + 0.04, 0.08), (x, YC, 0.42), kind="iron", jitter=0.003, bevel=0.006)
    # sills and floor planks
    for y in (-HY + 0.10, YC, HY - 0.10):
        box("sill", (2 * HX - 0.04, 0.20, 0.11), (0, y, 0.055), rot=(0, 0, rng.uniform(-0.3, 0.3)), jitter=0.006)
    for x in POSTX:
        box("sill", (0.20, 2 * HY - 0.40, 0.11), (x, 0, 0.055), rot=(0, 0, rng.uniform(-0.3, 0.3)), jitter=0.006)
    n = 16
    pw = (2 * LIMX + 0.04) / n
    for i in range(n):
        box("plank", (pw - 0.012, 2 * LIMY + 0.04, 0.05), (-LIMX - 0.02 + pw * (i + 0.5), 0, FLOOR - 0.025), jitter=0.004, bevel=0)
    yd0, yd1 = YC + CT / 2 - 0.02, LIMY + 0.02          # raised deck of the back row (planks run across, on the cross wall and the back wall)
    nd = 4
    for i in range(nd):
        w = (yd1 - yd0) / nd
        box("deck", (2 * LIMX + 0.04, w - 0.012, 0.05), (0, yd0 + w * (i + 0.5), BACK_FLOOR - 0.025), jitter=0.004, bevel=0)
    # stone lining: back wall full height, side walls and dividers stepped, cross wall four courses
    stone_wall([-LIMX] * 6, LIMX, HY - TWL / 2, "x", TWL)
    for sx in (-1, 1):
        stone_wall(YSTART, LIMY, sx * (HX - TWL / 2), "y", TWL)
    for dx in DIVX:
        stone_wall(YSTART, LIMY, dx, "y", DIVT, jit=0.008)
    stone_wall([-LIMX] * 4, LIMX, YC, "x", CT, jit=0.008)
    # caps: stepped on the side walls and dividers, straight on the cross wall and the back wall
    for sx in (-1, 1): stepped_caps(sx * (HX - TWL / 2), TWL, True)
    for dx in DIVX: stepped_caps(dx, DIVT, False)
    box("crosscap", (2 * LIMX, CT + 0.04, CAPH), (0, YC, LEV(4) + CAPH / 2), rot=(0, 0, rng.uniform(-0.2, 0.2)), jitter=0.004, bevel=0.008)
    zt = LEV(6)
    box("cap", (2 * HX, TWL + 0.04, CAPH), (0, HY - TWL / 2 - 0.02, zt + CAPH / 2), rot=(0, 0, rng.uniform(-0.2, 0.2)), jitter=0.004, bevel=0.008)
    box("rim", (2 * HX - 0.02, TWL + 0.03, 0.035), (0, HY - TWL / 2 - 0.02, zt + CAPH + 0.0175), kind="iron", jitter=0.002, bevel=0.007)
    for x in np.arange(-HX + 0.25, HX - 0.1, 0.36):
        box("rivet", (0.04, 0.04, 0.03), (x, HY - TWL / 2, zt + CAPH + 0.045), kind="iron", jitter=0, bevel=0)
    # sloped plank front, one set of boards per bay between the posts, iron straps, a heavy front rail
    tn = math.tan(math.radians(FRONT_TH))
    for i in range(3):
        xa, xb = POSTX[i] + PS / 2, POSTX[i + 1] - PS / 2
        bx = (xa + xb) / 2
        for z in (0.24, 0.43, 0.62):
            y = -HY + 0.13 - (z - FLOOR) * tn
            box("frontboard", (xb - xa + 0.06, 0.06, 0.19), (bx, y, z), rot=(FRONT_TH, 0, rng.uniform(-0.4, 0.4)), bevel=0.014)
        for sx in (bx - 0.30, bx + 0.30):
            z = 0.43; y = -HY + 0.13 - (z - FLOOR) * tn - 0.04
            box("strap", (0.08, 0.02, 0.60), (sx, y, z), kind="iron", rot=(FRONT_TH, 0, 0), jitter=0.003, bevel=0.004)
    box("frontrail", (2 * HX - 0.02, 0.16, 0.10), (0, -HY + 0.10, FRONT_RAIL_TOP - 0.05), rot=(0, 0, rng.uniform(-0.2, 0.2)))

# ---------- contents: real item models, settled by rigid-body physics ----------
ITEMS = [("CopperOre", "copper ore", False), ("TinOre", "tin ore", False), ("IronScrap", "iron scrap", True),
         ("SilverOre", "silver ore", False), ("BlackMetalScrap", "black metal scrap", True), ("FlametalOreNew", "flametal ore", False)]
# ONE scale per item type, relative to the item's own (true) prefab size. True CopperOre = 0.52 x 0.42 x 0.73 m.
# The bunker shows Coal at 0.46-0.56, Stone at 0.40-0.49, Flint at 0.49-0.60 of true size (longest side 0.23-0.35 m).
# Ore and scrap here: 0.45-0.50 of true size, longest side 0.29-0.33 m. FlametalOreNew's own model is 0.92 m long,
# so it gets 0.36 to land in the same 0.33 m family instead of reading as boulders.
SCALE = {"CopperOre": 0.45, "TinOre": 0.48, "IronScrap": 0.50, "SilverOre": 0.45, "BlackMetalScrap": 0.50, "FlametalOreNew": 0.36}
QUOTA = {"CopperOre": 12, "TinOre": 15, "IronScrap": 14, "SilverOre": 14, "BlackMetalScrap": 15, "FlametalOreNew": 10}   # 80 stacks
NCOPY = {"CopperOre": (3, 2), "TinOre": (2, 1), "IronScrap": (3,), "SilverOre": (3, 2), "BlackMetalScrap": (3, 3, 2), "FlametalOreNew": (2, 2, 1)}   # copies per stack, cycled
if "--nc" in argv:
    for kv in argv[argv.index("--nc") + 1].split(","):
        k, v = kv.split(":"); NCOPY[k] = tuple(int(a) for a in v.split("/"))
# compartment layout: 3 columns (x) x front/back rows (y); (col, row) -> prefab. Back row = the bulky ores (deep, tall walls),
# front row = tin and the flat scrap (shallow, low front for shovelling). Same assignment as round 3.
LAYOUT = {(0, 1): "CopperOre", (1, 1): "FlametalOreNew", (2, 1): "SilverOre",
          (0, 0): "TinOre", (1, 0): "BlackMetalScrap", (2, 0): "IronScrap"}
NUNITS = 80
MARGIN = 0.003
FPS = 24

def cell_bounds(col, row):
    x0 = -LIMX + col * (CELLW + DIVT); x1 = x0 + CELLW
    # colliders sit clear of the rough stone (jitter 8-12 mm), of the caps (overhang 2 cm) and of the posts
    ix0 = 0.025 if col == 0 else 0.03; ix1 = 0.025 if col == 2 else 0.03
    if row == 0: y0, y1 = -LIMY + 0.025, YC - CT / 2 - 0.03
    else: y0, y1 = YC + CT / 2 + 0.03, LIMY - 0.01
    return (x0 + ix0, x1 - ix1, y0, y1)

def wall_top(col, row, side, y=None):
    """visible top (stone + cap) of the wall behind a cell boundary"""
    if side == "y0": return FRONT_RAIL_TOP if row == 0 else LEV(4) + CAPH
    if side == "y1": return LEV(4) + CAPH if row == 0 else LEV(6) + CAPH
    return side_top(y) + CAPH

TEMPL = {}
def load_templates():
    for pf, _lab, _flat in ITEMS:
        objs = load_item(pf, anchor="center")
        ob = objs[0]
        info = json.load(open(f"{ITEMS_DIR}/{pf}/info.json"))
        bmin, bmax = Vector(info["bounds_min"]), Vector(info["bounds_max"])
        size = bmax - bmin
        s = SCALE[pf]
        ob.data.transform(Matrix.Diagonal((s, s, s, 1)))
        ob.data.update()
        ob.location = (0, 0, 0); ob.scale = (1, 1, 1)
        if pf == "TinOre":                  # blown-out white crystals -> pale grey (render only)
            for m in ob.data.materials:
                b = m.node_tree.nodes.get("Principled BSDF")
                if b and not any(n.type == "TEX_IMAGE" for n in m.node_tree.nodes): b.inputs["Base Color"].default_value = (0.62, 0.64, 0.68, 1)
        if pf == "BlackMetalScrap":         # the ripped tint is a vivid green; render it as dark metal (render only)
            for m in ob.data.materials:
                for n in m.node_tree.nodes:
                    if n.type == "MIX": n.inputs["B"].default_value = (0.20, 0.22, 0.27, 1)
        for m in ob.data.materials:
            b = m.node_tree.nodes.get("Principled BSDF")
            if b: b.inputs["Specular IOR Level"].default_value = 0.1; b.inputs["Roughness"].default_value = 0.95
        ob.hide_render = True; ob.hide_viewport = True
        ob.location = (0, 0, -50)
        V = np.array([tuple(v.co) for v in ob.data.vertices], np.float32)
        bm = bmesh.new(); bm.from_mesh(ob.data)
        hull = bmesh.ops.convex_hull(bm, input=bm.verts)
        planes = []
        for f in [g for g in hull["geom"] if isinstance(g, bmesh.types.BMFace)]:
            n = f.normal.copy()
            planes.append((n.x, n.y, n.z, n.dot(f.verts[0].co)))
        hv = np.array(sorted({tuple(round(c, 5) for c in v.co) for v in hull["geom"] if isinstance(v, bmesh.types.BMVert)}), np.float32)
        bm.free()
        TEMPL[pf] = {"obj": ob, "mesh": ob.data, "V": V, "s": float(s), "size": tuple(size), "center": tuple((bmin + bmax) / 2),
                     "planes": np.array(planes, np.float32), "hv": hv, "radius": float(np.linalg.norm(V, axis=1).max()),
                     "vol": float(size.x * size.y * size.z * s ** 3),
                     "tris": [(p.vertices[0], p.vertices[i], p.vertices[i + 1]) for p in ob.data.polygons for i in range(1, len(p.vertices) - 1)]}

def build_order():
    """80 stacks, interleaved over the six compartments by quota so every prefix is a whole, spread-out fill."""
    seq = []
    for (col, row), pf in LAYOUT.items():
        q = QUOTA[pf]
        for k in range(q):
            seq.append(((k + 0.5) / q + crng.uniform(-0.01, 0.01), col, row, pf, k))
    seq.sort(key=lambda t: t[0])
    units = []
    for n, (_sc, col, row, pf, k) in enumerate(seq[:NUNITS]):
        units.append({"index": n, "step": n * 8 // NUNITS, "col": col, "row": row, "item": pf, "k": k, "ncopy": NCOPY[pf][k % len(NCOPY[pf])], "copies": []})
    return units

# ---------- rigid-body simulation (as round 3: per compartment, stack by stack, earlier stacks frozen) ----------
def make_box_mesh(name, size):
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts: v.co = Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2]))
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    return me

def add_rb(ob, kind, shape, mass=1.0, damp=(0.25, 0.45)):   # bunker-like damping: lumps roll off peaks, heaps spread
    for o in bpy.context.view_layer.objects: o.select_set(False)
    ob.select_set(True); bpy.context.view_layer.objects.active = ob
    bpy.ops.rigidbody.object_add(type=kind)
    rb = ob.rigid_body
    rb.collision_shape = shape; rb.friction = 0.75; rb.restitution = 0.0
    rb.use_margin = True; rb.collision_margin = MARGIN
    if kind == "ACTIVE":
        rb.mass = mass; rb.linear_damping, rb.angular_damping = damp
        rb.use_deactivation = False

def euler_rand(flat):
    if flat:
        return Euler((math.radians(crng.uniform(-14, 14)), math.radians(crng.uniform(-14, 14)), crng.uniform(0, math.tau)), "XYZ")
    return Euler((crng.uniform(0, math.tau), crng.uniform(0, math.tau), crng.uniform(0, math.tau)), "XYZ")

def world_verts(pf, M):
    Mn = np.array(M)
    return TEMPL[pf]["V"] @ Mn[:3, :3].T + Mn[:3, 3]

def inside(W, col, row):
    x0, x1, y0, y1 = cell_bounds(col, row)
    return not ((W[:, 0] < x0 - 0.006).any() or (W[:, 0] > x1 + 0.006).any() or (W[:, 1] < y0 - 0.006).any()
                or (W[:, 1] > y1 + 0.006).any() or (W[:, 2] < ROWFLOOR[row] - 0.006).any())

def lean_over(W, col, row):
    """how far a copy rises above the visible wall top where it is within 2 cm of a compartment boundary (<= 0: fine)"""
    x0, x1, y0, y1 = cell_bounds(col, row)
    over = -1.0
    for side, d in (("x0", W[:, 0] - x0), ("x1", x1 - W[:, 0]), ("y0", W[:, 1] - y0), ("y1", y1 - W[:, 1])):
        near = d < 0.02
        if not near.any(): continue
        for w in W[near]:
            over = max(over, float(w[2]) - wall_top(col, row, side, float(w[1])))
    return over

SIMLOG = {"frames": [], "wall": 0.0, "unsettled": 0, "resid": []}
def simulate_all(units):
    sc = bpy.context.scene
    sc.render.fps = FPS
    bpy.ops.rigidbody.world_add()
    rbw = sc.rigidbody_world
    rbw.substeps_per_frame = 20; rbw.solver_iterations = 40; rbw.time_scale = 1.0
    rbw.point_cache.frame_start = 1; rbw.point_cache.frame_end = 400
    sc.frame_start = 1; sc.frame_end = 400
    t0 = time.time()
    cells = {}
    for (col, row), pf in LAYOUT.items():
        coll = bpy.data.collections.new(f"rb_{col}{row}")
        rbw.collection = coll
        x0, x1, y0, y1 = cell_bounds(col, row)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        T = 0.3; H = 5.0
        FL = ROWFLOOR[row]
        walls = [("floor", (x1 - x0 + 2 * T, y1 - y0 + 2 * T, T), (cx, cy, FL + 0.006 - T / 2)),
                 ("wx0", (T, y1 - y0 + 2 * T, H), (x0 - T / 2, cy, FLOOR + H / 2)), ("wx1", (T, y1 - y0 + 2 * T, H), (x1 + T / 2, cy, FLOOR + H / 2)),
                 ("wy0", (x1 - x0, T, H), (cx, y0 - T / 2, FLOOR + H / 2)), ("wy1", (x1 - x0, T, H), (cx, y1 + T / 2, FLOOR + H / 2))]
        for nm, sz, pos in walls:
            ob = bpy.data.objects.new(f"col_{col}{row}_{nm}", make_box_mesh(nm, sz)); ob.location = pos
            sc.collection.objects.link(ob); add_rb(ob, "PASSIVE", "BOX"); ob.hide_render = True
        sc.frame_set(1)
        top = FL
        flat = next(i[2] for i in ITEMS if i[0] == pf)
        T_ = TEMPL[pf]
        R = T_["radius"]
        sx = max(0.02, (x1 - x0) / 2 - R - 0.02)
        # back row: drop towards the back wall so the heap leans back like the bunker's; front row: anywhere
        if row == 1: dy0, dy1 = max(y0 + R + 0.02, cy - 0.05), y1 - R - 0.02
        else: dy0, dy1 = y0 + R + 0.02, y1 - R - 0.02
        if dy1 < dy0: dy0 = dy1 = cy
        HV = np.zeros((0, 3), np.float32)           # hull vertices of the frozen copies in this compartment
        def height(x, y):
            if not len(HV): return FL
            m = (HV[:, 0] - x) ** 2 + (HV[:, 1] - y) ** 2 < 0.15 ** 2
            return float(HV[m, 2].max()) if m.any() else FL
        for u in [u for u in units if u["col"] == col and u["row"] == row]:
            gap = 1.0 * max(T_["size"]) * T_["s"] * (0.7 if flat else 1.0)
            for attempt in range(8):
                obs = []; spots = []
                for k in range(u["ncopy"]):
                    ob = bpy.data.objects.new(f"u{u['index']:03d}_{k}", T_["mesh"]); sc.collection.objects.link(ob)
                    ob.rotation_euler = euler_rand(flat)
                    # shovel into the low spot: of 16 random spots take the lowest, with a pull towards the back (taller
                    # walls there) and away from the spots this stack already took
                    best = None
                    for _c in range(16):
                        px = cx + crng.uniform(-sx, sx); py = crng.uniform(dy0, dy1)
                        fb = (py - dy0) / max(dy1 - dy0, 1e-3)
                        sc_ = height(px, py) - (0.15 if row == 1 else 0.10) * fb + crng.uniform(0, 0.04 + 0.03 * attempt)
                        sc_ += sum(0.3 for (qx, qy) in spots if (qx - px) ** 2 + (qy - py) ** 2 < 0.25 ** 2)
                        if best is None or sc_ < best[0]: best = (sc_, px, py)
                    _s, px, py = best; spots.append((px, py))
                    ob.location = (px, py, top + 0.06 + R + gap * k)
                    add_rb(ob, "ACTIVE", "CONVEX_HULL", mass=max(0.05, T_["vol"] * 700))
                    obs.append(ob)
                sc.frame_set(1)
                prev = None; still = 0; f = 1; dp = dr = 0.0
                while f < 360:
                    f += 1; sc.frame_set(f)
                    cur = [(o.matrix_world.translation.copy(), o.matrix_world.to_quaternion()) for o in obs]
                    if prev:
                        dp = max((a[0] - b[0]).length for a, b in zip(cur, prev))
                        dr = max(a[1].rotation_difference(b[1]).angle for a, b in zip(cur, prev))
                        still = still + 1 if (dp < 2e-4 and dr < 4e-3 and f > 8) else 0
                        if still >= 3: break
                    prev = cur
                Ms = [o.matrix_world.copy() for o in obs]
                # a stack whose copy ends up leaning on an invisible collider above a visible wall top (or out of its
                # compartment) is dropped again from other spots
                worst = max(max(lean_over(world_verts(pf, M), col, row), 0.0 if inside(world_verts(pf, M), col, row) else 1.0) for M in Ms)
                if worst <= 0.0 or attempt == 7: break
                SIMLOG["retries"] = SIMLOG.get("retries", 0) + 1
                for o in obs: bpy.data.objects.remove(o, do_unlink=True)
                sc.frame_set(1)
            SIMLOG["resid"].append((round(dp * 1000, 3), round(dr, 4)))
            if still < 3: SIMLOG["unsettled"] += 1
            SIMLOG["frames"].append(f)
            for o in obs: o.rigid_body.type = "PASSIVE"
            for o, M in zip(obs, Ms): o.matrix_world = M
            bpy.context.view_layer.update()
            sc.frame_set(1)
            for o, M in zip(obs, Ms):
                u["copies"].append({"item": u["item"], "M": M.copy(), "obj": o})
            for M in Ms:
                Mn = np.array(M)
                HV = np.concatenate([HV, (T_["hv"] @ Mn[:3, :3].T + Mn[:3, 3]).astype(np.float32)])
            top = max(top, float(HV[:, 2].max()))
        cells[(col, row)] = top
        print("CELL", col, row, pf, "copies", sum(len(u["copies"]) for u in units if u["col"] == col and u["row"] == row),
              "heap top", round(top, 3), "median copy top", round(float(np.median([max((c["M"] @ Vector(tuple(map(float, v)))).z for v in T_["hv"][::3]) for u in units if u["col"] == col and u["row"] == row for c in u["copies"]])), 3), "elapsed", round(time.time() - t0, 1), flush=True)
    SIMLOG["wall"] = time.time() - t0
    SIMLOG["tops"] = {f"{k[0]}{k[1]}": round(v, 3) for k, v in cells.items()}

# ---------- checks ----------
def copy_world_verts(cp):
    M = np.array(cp["M"])
    V = TEMPL[cp["item"]]["V"]
    return V @ M[:3, :3].T + M[:3, 3]

def clip_check(units, frame_bvh):
    bad = []
    for u in units:
        for k, cp in enumerate(u["copies"]):
            W = copy_world_verts(cp)
            bt = BVHTree.FromPolygons([Vector(tuple(float(a) for a in w)) for w in W], TEMPL[cp["item"]]["tris"])
            if frame_bvh.overlap(bt): bad.append((u["index"], k, cp["item"])); print("clip", u["index"], k, cp["item"], "cell", (u["col"], u["row"]))
    return bad

def containment(units):
    """every vertex inside its compartment, and nothing leaning on an invisible collider above a visible wall top:
    a vertex within 2 cm of a compartment boundary must lie below the wall top behind that boundary"""
    escaped, leaning, worst = [], [], 0.0
    for u in units:
        for k, cp in enumerate(u["copies"]):
            W = copy_world_verts(cp)
            if not inside(W, u["col"], u["row"]): escaped.append((u["index"], k))
            over = lean_over(W, u["col"], u["row"])
            if over > 0: leaning.append((u["index"], k, round(over, 3)))
            worst = max(worst, over)
    return escaped, leaning, worst

def interpenetration(units):
    """Deepest vertex-in-hull penetration between any two copies (hull vertices of A inside the convex hull of B), per item."""
    cps = [cp for u in units for cp in u["copies"]]
    P = np.array([np.array(cp["M"])[:3, 3] for cp in cps]); R = np.array([TEMPL[cp["item"]]["radius"] for cp in cps])
    worst = (0.0, None); best = [-9.0]; npairs = 0; over = []
    per_item = {pf: 0.0 for pf, *_ in ITEMS}
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
                sd = pl[:, 3][None, :] - xb @ pl[:, :3].T
                dep = sd.min(axis=1)
                m = float(dep.max())
                best[0] = max(best[0], m)
                if m > 0: over.append(m)
                if m > worst[0]: worst = (m, (a, b))
                per_item[cps[a]["item"]] = max(per_item[cps[a]["item"]], max(m, 0.0))
    return worst[0], npairs, over, worst[1], best[0], per_item

# ---------- anchors export (Unity prefab space, same schema as round 3) ----------
CB2U = Matrix(((-1, 0, 0), (0, 0, 1), (0, -1, 0)))
def b2u_vec(v): return (-v[0], v[2], -v[1])
def rot_to_unity(R):
    Ru = CB2U @ R @ CB2U.transposed()
    q = Ru.to_quaternion()
    e = Ru.to_euler("ZXY")
    ex = Matrix.Rotation(e.x, 3, "X"); ey = Matrix.Rotation(e.y, 3, "Y"); ez = Matrix.Rotation(e.z, 3, "Z")
    err = max(abs(a - b) for ra, rb in zip((ey @ ex @ ez), Ru) for a, b in zip(ra, rb))
    return [round(math.degrees(e.x), 3), round(math.degrees(e.y), 3), round(math.degrees(e.z), 3)], [round(q.x, 5), round(q.y, 5), round(q.z, 5), round(q.w, 5)], err

def build_anchors(units, frame_tris, frame_size, clip_bad, ncop, pen, per_item_checks):
    maxerr = 0
    out_units = []
    for u in units:
        pos = [cp["M"].translation for cp in u["copies"]]
        c = sum(pos, Vector()) / len(pos)
        cps = []
        lo = Vector((1e9,) * 3); hi = Vector((-1e9,) * 3)
        for cp in u["copies"]:
            M = cp["M"]; R = M.to_3x3().normalized()
            eul, quat, err = rot_to_unity(R); maxerr = max(maxerr, err)
            T = TEMPL[cp["item"]]
            W = copy_world_verts(cp)
            lo = Vector(tuple(min(lo[i], float(W[:, i].min())) for i in range(3))); hi = Vector(tuple(max(hi[i], float(W[:, i].max())) for i in range(3)))
            cps.append({"item": cp["item"], "offset": [round(a, 4) for a in b2u_vec(M.translation - c)], "euler": eul, "quat_xyzw": quat,
                        "scale": round(T["s"], 4), "fit_longest_m": round(T["s"] * max(T["size"]), 3),
                        "world_position": [round(a, 4) for a in b2u_vec(M.translation)]})
        out_units.append({"index": u["index"], "step": u["step"], "kind": "heap_step", "item": u["item"], "compartment": [u["col"], u["row"]],
                           "position": [round(a, 4) for a in b2u_vec(c)], "rotation": [0, 0, 0],
                           "box": [round(hi.x - lo.x, 4), round(hi.z - lo.z, 4), round(hi.y - lo.y, 4)], "layer": 0, "copies": cps})
    items = {}
    for pf, *_ in ITEMS:
        T = TEMPL[pf]
        items[pf] = {"bounds_size_unity": [round(T["size"][0], 4), round(T["size"][2], 4), round(T["size"][1], 4)],
                     "bounds_center_unity": [round(a, 4) for a in b2u_vec(T["center"])], "scale_used": round(T["s"], 4)}
    comps = []
    for (col, row), pf in LAYOUT.items():
        x0, x1, y0, y1 = cell_bounds(col, row)
        comps.append({"compartment": [col, row], "item": pf, "stacks": QUOTA[pf],
                      "x": [round(-x1, 4), round(-x0, 4)], "z": [round(-y1, 4), round(-y0, 4)], "floor_y": ROWFLOOR[row]})
    doc = {
        "bin": "OreBin round 4 (bunker-sized, physically settled)", "slots": NUNITS, "units": len(out_units), "steps": 8, "stack_per_unit": 1,
        "frame": {"obj": "OreBin.obj", "tris": frame_tris, "size_m": [round(a, 3) for a in frame_size], "atlas": "orebin_atlas.png 128x128"},
        "space": "Unity prefab space, origin = bin footprint centre on the ground. Blender z-up/-y front -> Unity y-up/+z front: ux=-bx, uy=bz, uz=-by. "
                 "OBJ export (forward NEGATIVE_Z, up Y) writes (bx, bz, -by); Unity's importer negates x, same mapping.",
        "unit_semantics": "SETTLED: every copy has an explicit final pose from a rigid-body simulation (convex-hull items, friction 0.75, restitution 0, damping 0.25/0.45, "
                          "dropped stack by stack in fill order, earlier stacks frozen). unit.position = mean of the copy centres; each copy: place the "
                          "item's prefab so that its BOUNDS CENTRE sits at unit.position + copy.offset (= copy.world_position, prefab space), rotated by copy.euler "
                          "(Unity Quaternion.Euler, ZXY) or copy.quat_xyzw, uniform scale copy.scale relative to the item prefab's native size. "
                          "Item root = bounds centre - R * (scale * item.bounds_center_unity). unit.box = bounding box of the unit's copies (informational).",
        "fill_order": "units are listed in fill order; show the first n. Later stacks lie on earlier ones, earlier stacks never move. "
                      "Each compartment holds one item type (compartments[]); unit.item is its type, copies keep it.",
        "compartments": comps, "items": items, "clip_check": {"clipping": len(clip_bad), "of_copies": ncop},
        "interpenetration_max_m": round(pen, 5), "rotation_convert_max_err": maxerr,
        "checks_per_item": per_item_checks, "units_list": out_units}
    return doc, maxerr

def tri_list(me):
    V = [v.co.copy() for v in me.vertices]; T = []
    for p in me.polygons:
        vs = list(p.vertices)
        for i in range(1, len(vs) - 1): T.append((vs[0], vs[i], vs[i + 1]))
    return V, T

# ---------- scene ----------
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
atlas = build_atlas()
MAT = bpy.data.materials.new("orebin"); MAT.use_nodes = True
nt = MAT.node_tree; bsdf = nt.nodes["Principled BSDF"]
ti = nt.nodes.new("ShaderNodeTexImage"); ti.image = atlas; ti.interpolation = "Closest"
nt.links.new(ti.outputs["Color"], bsdf.inputs["Base Color"])
bsdf.inputs["Roughness"].default_value = 1.0
bsdf.inputs["Specular IOR Level"].default_value = 0.0

def tris(obs): return sum(len(p.vertices) - 2 for o in obs for p in o.data.polygons)
def join(obs, name):
    bpy.ops.object.select_all(action="DESELECT")
    for o in obs: o.select_set(True)
    bpy.context.view_layer.objects.active = obs[0]
    bpy.ops.object.join(); ob = bpy.context.active_object; ob.name = name
    return ob

load_templates()
PARTS.clear()
build_frame()
frame = join(list(PARTS), "OreBin")
frame_tris = tris([frame])
V, T = tri_list(frame.data)
fbvh = BVHTree.FromPolygons(V, T, all_triangles=True)
FV = np.array([tuple(v) for v in V])
frame_size = (float(FV[:, 0].max() - FV[:, 0].min()), float(FV[:, 2].max()), float(FV[:, 1].max() - FV[:, 1].min()))   # W, H, D
print("FRAME tris", frame_tris, "size W x H x D", [round(a, 3) for a in frame_size])
for pf, *_ in ITEMS:
    T_ = TEMPL[pf]
    print("ITEM", pf, "scale", T_["s"], "longest m", round(T_["s"] * max(T_["size"]), 3), "dims", [round(T_["s"] * a, 3) for a in T_["size"]])
units = []
doc = None
if not FRAME_ONLY:
    units = build_order()
    simulate_all(units)
    ncop = sum(len(u["copies"]) for u in units)
    print("SIM wall", round(SIMLOG["wall"], 1), "s; frames per stack: mean", round(sum(SIMLOG["frames"]) / len(SIMLOG["frames"]), 1),
          "max", max(SIMLOG["frames"]), "(at", FPS, "fps); unsettled stacks", SIMLOG["unsettled"], "; re-dropped stacks", SIMLOG.get("retries", 0), "; heap tops", SIMLOG["tops"])
    bad = clip_check(units, fbvh)
    print("CLIPPING", len(bad), "of", ncop, "copies", bad)
    esc, lean, lworst = containment(units)
    print("CONTAIN escaped", len(esc), esc[:10], "; leaning above a visible wall top", len(lean), lean[:12], "worst", round(lworst, 3), "m")
    pen, npairs, over, wp, best, per_item = interpenetration(units)
    print("INTERPENETRATION max", round(pen * 1000, 2), "mm over", npairs, "near pairs;", len(over), "pairs penetrate, median",
          round(float(np.median(over)) * 1000, 2) if over else 0, "mm; closest hull-vertex approach", round(best * 1000, 2), "mm (negative = clear); margin", MARGIN * 1000, "mm")
    print("INTERP per item (mm)", {k: round(v * 1000, 2) for k, v in per_item.items()})
    print("residual per-frame move at freeze (mm, rad): worst", max(SIMLOG["resid"]), "; unsettled-flagged", SIMLOG["unsettled"])
    checks = {}
    for pf, *_ in ITEMS:
        n = sum(len(u["copies"]) for u in units if u["item"] == pf)
        checks[pf] = {"copies": n, "copies_per_stack": list(NCOPY[pf]), "clipping": sum(1 for b in bad if b[2] == pf),
                      "interpenetration_max_m": round(per_item[pf], 5),
                      "escaped": sum(1 for (i, k) in esc if units[i]["item"] == pf),
                      "leaning_above_wall": sum(1 for (i, k, o) in lean if units[i]["item"] == pf),
                      "longest_m": round(TEMPL[pf]["s"] * max(TEMPL[pf]["size"]), 3)}
    print("CHECKS", json.dumps(checks))
    doc, err = build_anchors(units, frame_tris, frame_size, bad, ncop, pen, checks)
    print("rotation convert err", err)
    json.dump({"frames": SIMLOG["frames"], "tops": SIMLOG["tops"]}, open(os.path.join(OUT, "simlog.json"), "w"))
    for u in units:
        for cp in u["copies"]: bpy.data.objects.remove(cp["obj"], do_unlink=True)
    for o in [o for o in bpy.data.objects if o.name.startswith("col_")]: bpy.data.objects.remove(o, do_unlink=True)
    bpy.ops.rigidbody.world_remove()
# files: atlas (already saved) -> OBJ -> anchors last, through a temp file outside the folder and a rename
bpy.ops.object.select_all(action="DESELECT"); frame.select_set(True)
bpy.ops.wm.obj_export(filepath=os.path.join(OUTA, "OreBin.obj"), export_selected_objects=True, export_materials=False,
                      export_triangulated_mesh=True, forward_axis="NEGATIVE_Z", up_axis="Y")
if doc is not None:
    tmp = os.path.join(OUT, "orebin_anchors.json.tmp")
    json.dump(doc, open(tmp, "w"), indent=1)
    os.replace(tmp, os.path.join(OUTA, "orebin_anchors.json"))
print("OREBIN frame tris", frame_tris, "item tris (100%)", sum(len(TEMPL[cp["item"]]["tris"]) for u in units for cp in u["copies"]),
      "copies", sum(len(u["copies"]) for u in units))
if NORENDER:
    print("DONE"); sys.exit(0)

# ---------- render scene: r4 at three fills, beside the bunker, beside round 3, a 1.8 m post ----------
C = Matrix(((-1, 0, 0), (0, 0, 1), (0, -1, 0)))
def u2b_pos(p): return Vector((-p[0], -p[2], p[1]))
def u2b_rot(q): return C.transposed() @ Quaternion((q[3], q[0], q[1], q[2])).to_matrix() @ C

RAW = {}
def raw_mesh(pf):
    """the item's mesh at its true size, bounds centre at the origin (for replaying anchors files)"""
    if pf not in RAW:
        ob = load_item(pf, anchor="center")[0]
        RAW[pf] = ob.data
        bpy.data.objects.remove(ob, do_unlink=True)
    return RAW[pf]

def place(pf, Mb, name="item"):
    ob = bpy.data.objects.new(name, raw_mesh(pf)); sc.collection.objects.link(ob)
    ob.matrix_world = Mb
    return ob

def spawn_r4(fill, dx, dy):
    fr = frame.copy(); sc.collection.objects.link(fr)
    fr.location = (dx, dy, 0)
    n = round(fill * len(units))
    for u in units[:n]:
        for k, cp in enumerate(u["copies"]):
            ob = bpy.data.objects.new(f"u{u['index']:03d}_{k}", TEMPL[cp["item"]]["mesh"]); sc.collection.objects.link(ob)
            ob.matrix_world = Matrix.Translation((dx, dy, 0)) @ cp["M"]

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
    m = atlas_mat(png, os.path.basename(png))
    for o in new:
        o.data.materials.clear(); o.data.materials.append(m)
        o.location = (dx, dy, 0)
    return new

def spawn_bunker(dx, dy):
    d = os.path.join(REPO, "assets", "bunker_r3")
    import_frame(os.path.join(d, "Bunker.obj"), os.path.join(d, "bunker_atlas.png"), dx, dy)
    doc_b = json.load(open(os.path.join(d, "bunker_anchors.json")))
    for u in doc_b["units"]:
        for cp in u["copies"]:
            p = u2b_pos([a + b for a, b in zip(u["position"], cp["offset"])])
            Mb = Matrix.Translation(p + Vector((dx, dy, 0))) @ u2b_rot(cp["rot_quat"]).to_4x4() @ Matrix.Diagonal((cp["scale"],) * 3 + (1,))
            place(u["render_item"], Mb, "bunker_item")

def spawn_r3(dx, dy):
    d = os.path.join(REPO, "assets", "orebin_r3")
    import_frame(os.path.join(d, "OreBin.obj"), os.path.join(d, "orebin_atlas.png"), dx, dy)
    doc3 = json.load(open(os.path.join(d, "orebin_anchors.json")))
    for u in doc3["units_list"]:
        for cp in u["copies"]:
            p = u2b_pos(cp["world_position"])
            Mb = Matrix.Translation(p + Vector((dx, dy, 0))) @ u2b_rot(cp["quat_xyzw"]).to_4x4() @ Matrix.Diagonal((cp["scale"],) * 3 + (1,))
            place(cp["item"], Mb, "r3_item")

def spawn_r4_file(dx, dy):
    """round 4 replayed from the EXPORTED files (OBJ + anchors, unit.position + copy.offset, the mod's own path)"""
    import_frame(os.path.join(OUTA, "OreBin.obj"), os.path.join(OUTA, "orebin_atlas.png"), dx, dy)
    d4 = json.load(open(os.path.join(OUTA, "orebin_anchors.json")))
    for u in d4["units_list"]:
        for cp in u["copies"]:
            p = u2b_pos([a + b for a, b in zip(u["position"], cp["offset"])])
            Mb = Matrix.Translation(p + Vector((dx, dy, 0))) @ u2b_rot(cp["quat_xyzw"]).to_4x4() @ Matrix.Diagonal((cp["scale"],) * 3 + (1,))
            place(cp["item"], Mb, "r4_item")

pm = bpy.data.materials.new("plain"); pm.use_nodes = True
pm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.55, 0.52, 0.46, 1)
def post(x, y):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(x, y, 0.9)); p = bpy.context.active_object
    p.scale = (0.14, 0.14, 1.8); p.data.materials.append(pm); p.name = "post_1.8m"

ROWS = {"fills": 0.0, "bunker": 10.0, "r3": 20.0}
GAP = 4.6
spawn_r4(0.0, -GAP, ROWS["fills"]); spawn_r4(0.5, 0.0, ROWS["fills"]); spawn_r4(1.0, GAP, ROWS["fills"])
post(-GAP - 2.5, ROWS["fills"] - 0.6); post(GAP + 2.4, ROWS["fills"] - 0.7)
r4row = spawn_r4_file if (doc is not None and os.path.exists(os.path.join(OUTA, "orebin_anchors.json"))) else (lambda dx, dy: spawn_r4(1.0, dx, dy))
r4row(-2.25, ROWS["bunker"]); spawn_bunker(2.25, ROWS["bunker"]); post(0.0, ROWS["bunker"] - 1.4)
r4row(-1.95, ROWS["r3"]); spawn_r3(1.75, ROWS["r3"]); post(-0.05, ROWS["r3"] - 1.4)
frame.hide_render = True       # the original stays at the origin, unused in the shots

world = bpy.data.worlds.new("w"); sc.world = world; world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.42, 0.45, 0.5, 1)
world.node_tree.nodes["Background"].inputs[1].default_value = 0.9
sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN")); sun.data.energy = 3.2
sun.rotation_euler = (math.radians(50), 0, math.radians(35)); sc.collection.objects.link(sun)
bpy.ops.mesh.primitive_plane_add(size=80, location=(0, 10, 0))
gm = bpy.data.materials.new("ground"); gm.use_nodes = True
gm.node_tree.nodes["Background" if False else "Principled BSDF"].inputs["Base Color"].default_value = (0.16, 0.14, 0.11, 1)
bpy.context.active_object.data.materials.append(gm)
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam); sc.camera = cam
sc.render.engine = "BLENDER_EEVEE_NEXT"
sc.render.resolution_x, sc.render.resolution_y = (1000, 562) if QUICK else (1600, 900)
sc.view_settings.view_transform = "Standard"
F = ROWS["fills"]
VIEWS = {  # name: (yaw, pitch, dist, target, lens)
    "fills": (-4, 28, 22.5, (-0.5, F, 0.6), 50),
    "empty": (-30, 30, 8.6, (-GAP, F, 0.6), 50),
    "half": (-30, 34, 8.6, (0.0, F, 0.55), 50),
    "full": (-30, 34, 8.6, (GAP, F, 0.55), 50),
    "top": (-12, 58, 6.6, (GAP, F, 0.5), 50),
    "bunker": (-14, 24, 15.5, (0.0, ROWS["bunker"], 0.75), 50),
    "r3": (-14, 26, 12.0, (-0.1, ROWS["r3"], 0.6), 50),
    "scale": (38, 9, 9.5, (GAP + 0.7, F - 0.2, 0.8), 50),
}
for vn, (yaw, pitch, dist, tgt, lens) in VIEWS.items():
    if VIEWSEL and vn not in VIEWSEL: continue
    t = Vector(tgt)
    d = Vector((math.cos(math.radians(pitch)) * math.sin(math.radians(yaw)),
                -math.cos(math.radians(pitch)) * math.cos(math.radians(yaw)), math.sin(math.radians(pitch))))
    cam.location = t + d * dist; cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler(); cam.data.lens = lens
    sc.render.filepath = os.path.join(OUT, f"{TAG}-{vn}.png")
    bpy.ops.render.render(write_still=True)
    print("RENDER", vn, flush=True)
print("DONE")
