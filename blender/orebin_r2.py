"""Ore Bin round 2. Our own furniture mesh and own 128x128 atlas; the CONTENTS are the game's own item models.
Run: blender -b -P orebin_r2.py -- [--out DIR] [--tag NAME] [--no-ref] [--quick] [--views fills,close,alt]

Furniture: timber-framed bin, solid rough stone-block walls (back and sides), low sloped plank front, iron rim. 2.8 x 1.8 m.
Contents: 80 piles (one pile = one full stack of one ore/scrap), each pile = 5-7 copies of that item's real model packed
into the unit box. The mod places the real item models at the anchors in orebin_anchors.json. The ripped item models
under ValheimRip/items are used for the renders only and are never exported.

Atlas 128x128, point-filtered, strips tile along u (v rows count from the bottom):
  rows 96-127 hewn timber side grain   rows 64-95 end grain (4 ring tiles)
  rows 32-63  stone blocks (4 tiles, one tile = one block face)   rows 0-31 iron
Unity prefab space: ux = -bx, uy = bz, uz = -by (Blender z-up, -y front). OBJ export forward NEGATIVE_Z, up Y gives
(bx, bz, -by); Unity's importer negates x, which is the same mapping.
"""
import bpy, bmesh, sys, os, math, json, random
import numpy as np
from mathutils import Vector, Matrix, Euler
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
OUTA = os.path.normpath(os.path.join(HERE, "..", "assets", "orebin_r2"))
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = argv[argv.index("--out") + 1] if "--out" in argv else OUTA
TAG = argv[argv.index("--tag") + 1] if "--tag" in argv else "orebin"
QUICK = "--quick" in argv
VIEWSEL = argv[argv.index("--views") + 1].split(",") if "--views" in argv else None
RIP = "C:/Users/joost/ValheimRip/chests/piece_chest_wood"
ITEMS_DIR = "C:/Users/joost/ValheimRip/items"
sys.path.append(ITEMS_DIR)
from load_item import load_item
os.makedirs(OUTA, exist_ok=True); os.makedirs(OUT, exist_ok=True)
rng = random.Random(21)

TW = TH = 128
DENS = 48.0
STRIP = {"hewn": 0.75, "end": 0.50, "stone": 0.25, "iron": 0.0}

# ---------- texture ----------
def srgb(c): return np.array(c, dtype=np.float32)
WOOD, WOOD_D = srgb((0.38, 0.29, 0.18)), srgb((0.21, 0.16, 0.10))
END, END_D = srgb((0.55, 0.45, 0.31)), srgb((0.35, 0.27, 0.17))
IRON, IRON_D = srgb((0.22, 0.21, 0.20)), srgb((0.09, 0.09, 0.09))
STONES = [srgb(c) for c in ((0.47, 0.44, 0.38), (0.40, 0.38, 0.34), (0.50, 0.46, 0.38), (0.36, 0.35, 0.33))]
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
    # stone blocks: four tiles, each a whole block face: mottled body, dark chiselled rim, lit top-left edge, a little lichen
    xx, yy = np.meshgrid(np.arange(32), np.arange(32))
    edge = np.minimum(np.minimum(xx, 31 - xx), np.minimum(yy, 31 - yy))
    for k in range(4):
        base = STONES[k]
        t = blocky(32, 32, 8) * 0.38 + blocky(32, 32, 4) * 0.32 + blocky(32, 32, 2) * 0.16 + nr.random((32, 32)) * 0.14
        t = np.clip(t, 0, 1)
        tile_img = (base * 0.62) * (1 - t[..., None]) + np.clip(base * 1.12, 0, 1) * t[..., None]
        lm = (blocky(32, 32, 2) > 0.90)[..., None]
        tile_img = np.where(lm, tile_img * 0.55 + LICHEN * 0.45, tile_img)
        lit = ((yy >= 29) | (xx <= 2)) & (edge >= 2)          # chisel highlight (v up = row up)
        tile_img = np.where(lit[..., None], np.clip(tile_img * 1.18, 0, 1), tile_img)
        tile_img = np.where((edge <= 1)[..., None], tile_img * 0.42, tile_img)
        tile_img = np.where((edge == 2)[..., None] & ~lit[..., None], tile_img * 0.80, tile_img)
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

FLOOR = 0.14
HX, HY, PS = 1.08, 0.78, 0.18            # outer half sizes, post section
PX, PY = HX - PS / 2, HY - PS / 2
LIMX, LIMY = HX - PS, HY - PS            # interior half sizes 1.05 x 0.60
TWL = 0.16                               # stone wall thickness
COURSE, NCOURSE = 0.18, 3
WALLTOP = FLOOR + COURSE * NCOURSE       # 0.74
POSTH = 1.05

def stone_wall(a0, a1, cross, axis):
    """Courses of rough blocks from a0 to a1 along `axis` ('x' or 'y'), wall centre line at `cross`. A dark core slab
    behind the blocks keeps the wall solid wherever the blocks have joints."""
    L = a1 - a0
    mid = (a0 + a1) / 2
    zc0 = FLOOR + COURSE * NCOURSE / 2
    if axis == "x": box("stonecore", (L, TWL * 0.7, COURSE * NCOURSE - 0.01), (mid, cross, zc0), kind="stone", jitter=0.0, bevel=0)
    else: box("stonecore", (TWL * 0.7, L, COURSE * NCOURSE - 0.01), (cross, mid, zc0), kind="stone", jitter=0.0, bevel=0)
    for c in range(NCOURSE):
        zc = FLOOR + COURSE * (c + 0.5)
        a = a0 - (0.0 if c % 2 == 0 else 0.17)
        while a < a1 - 0.03:
            w = rng.uniform(0.30, 0.52)
            lo, hi = max(a, a0), min(a + w, a1)
            if a1 - hi < 0.22: hi = a1
            if hi - lo > 0.12:
                zz = zc + rng.uniform(-0.006, 0.006)
                if axis == "x": box("stone", (hi - lo - 0.02, TWL, COURSE - 0.02), ((lo + hi) / 2, cross, zz), kind="stone", jitter=0.022, bevel=0.012, rough=True)
                else: box("stone", (TWL, hi - lo - 0.02, COURSE - 0.02), (cross, (lo + hi) / 2, zz), kind="stone", jitter=0.022, bevel=0.012, rough=True)
            a = hi if hi > a + 0.05 else a + w

def build_frame():
    for sx in (-1, 1):
        for sy in (-1, 1):
            h = POSTH + rng.uniform(-0.02, 0.02)
            box("post", (PS, PS, h), (sx * PX, sy * PY, h / 2), rot=(rng.uniform(-0.8, 0.8), rng.uniform(-0.8, 0.8), 0))
    for sy in (-1, 1):
        box("sill", (2 * HX + 0.1, 0.18, 0.11), (0, sy * (HY - 0.09), 0.055), rot=(0, 0, rng.uniform(-0.5, 0.5)), jitter=0.006)
    for sx in (-1, 1):
        box("sill", (0.18, 2 * HY - 0.4, 0.11), (sx * (HX - 0.09), 0, 0.055), rot=(0, 0, rng.uniform(-0.5, 0.5)), jitter=0.006)
    n = 9
    pw = (2 * LIMX + 0.04) / n
    for i in range(n):
        box("plank", (pw - 0.01, 2 * LIMY + 0.04, 0.05), (-LIMX - 0.02 + pw * (i + 0.5), 0, FLOOR - 0.025), jitter=0.004, bevel=0)
    stone_wall(-LIMX, LIMX, HY - TWL / 2, "x")
    for sx in (-1, 1):
        stone_wall(-LIMY, LIMY, sx * (HX - TWL / 2), "y")
    zc = WALLTOP + 0.05
    box("cap", (2 * LIMX, 0.18, 0.1), (0, HY - 0.09, zc), rot=(0, 0, rng.uniform(-0.4, 0.4)), jitter=0.005)
    for sx in (-1, 1):
        box("cap", (0.18, 2 * LIMY, 0.1), (sx * (HX - 0.09), 0, zc), rot=(0, 0, rng.uniform(-0.4, 0.4)), jitter=0.005)
    zr = WALLTOP + 0.1 + 0.0225
    box("rim", (2 * HX, 0.18, 0.045), (0, HY - 0.09, zr), kind="iron", jitter=0.003, bevel=0.007)
    for sx in (-1, 1):
        box("rim", (0.18, 2 * HY, 0.045), (sx * (HX - 0.09), 0, zr), kind="iron", jitter=0.003, bevel=0.007)
    for x in (-0.6, -0.3, 0.0, 0.3, 0.6):
        box("rivet", (0.04, 0.04, 0.035), (x, HY - 0.095, zr + 0.035), kind="iron", jitter=0, bevel=0)
    for sx in (-1, 1):
        for y in (-0.3, 0.0, 0.3):
            box("rivet", (0.04, 0.04, 0.035), (sx * (HX - 0.095), y, zr + 0.035), kind="iron", jitter=0, bevel=0)
    th = 12.0
    for z in (0.24, 0.42):
        y = -HY + 0.10 - (z - FLOOR) * math.tan(math.radians(th))
        box("frontboard", (2 * LIMX - 0.02, 0.06, 0.2), (0, y, z), rot=(th, 0, rng.uniform(-0.4, 0.4)), bevel=0.014)
    for sx in (-0.6, 0.0, 0.6):
        z = 0.33; y = -HY + 0.10 - (z - FLOOR) * math.tan(math.radians(th)) - 0.04
        box("strap", (0.09, 0.02, 0.46), (sx, y, z), kind="iron", rot=(th, 0, 0), jitter=0.003, bevel=0.004)
    box("frontrail", (2 * LIMX, 0.14, 0.09), (0, -HY + 0.09, 0.545), rot=(0, 0, rng.uniform(-0.4, 0.4)))
    for sx in (-1, 1):
        for sy in (-1, 1):
            box("band", (PS + 0.04, PS + 0.04, 0.08), (sx * PX, sy * PY, 0.40), kind="iron", jitter=0.003, bevel=0.006)
            box("postcap", (PS + 0.03, PS + 0.03, 0.04), (sx * PX, sy * PY, POSTH + 0.015), kind="iron", jitter=0.002, bevel=0.005)

# ---------- contents: real item models packed in unit boxes ----------
ITEMS = [  # prefab, label, weight, flat? (flat = scrap, lies with small tilt)
    ("CopperOre", "copper ore", 0.20, False), ("TinOre", "tin ore", 0.15, False), ("IronScrap", "iron scrap", 0.15, True),
    ("SilverOre", "silver ore", 0.10, False), ("BlackMetalScrap", "black metal scrap", 0.14, True),
    ("FlametalOreNew", "flametal ore", 0.08, False), ("Coal", "coal", 0.10, False), ("IronOre", "iron ore", 0.08, False)]
NX, NY, BZ = 6, 4, 0.20
BXW, BYD = 2 * LIMX / NX, 2 * LIMY / NY          # 0.30 x 0.30 pitch
BOXS = (BXW - 0.02, BYD - 0.02, BZ - 0.004)    # unit box (Blender axes)
NLAYER, NUNITS = 5, 80
STAGGER_B = 0.45

TEMPL = {}          # prefab -> object + vertices centred on the bounds centre
def load_templates():
    for pf, *_ in ITEMS:
        objs = load_item(pf, anchor="center")
        ob = objs[0]
        info = json.load(open(f"{ITEMS_DIR}/{pf}/info.json"))
        bmin, bmax = Vector(info["bounds_min"]), Vector(info["bounds_max"])
        V = np.array([tuple(v.co) for v in ob.data.vertices], np.float32)
        ob.hide_render = True; ob.hide_viewport = True
        ob.location = (0, 0, -50)
        TEMPL[pf] = {"obj": ob, "V": V, "size": tuple(bmax - bmin), "center": tuple((bmin + bmax) / 2)}

def layer_cells():
    """All lattice cells with a fill score. Layers alternate the half-pitch stagger; higher layers score later; a cell never
    comes before the cells it rests on. Sorted by score = fill order, so every prefix is a whole, supported heap."""
    cells = {}
    for l in range(NLAYER):
        nx, ny = (NX - 1, NY - 1) if l % 2 else (NX, NY)
        for i in range(nx):
            for j in range(ny):
                u = (i - (nx - 1) / 2) * BXW; v = (j - (ny - 1) / 2) * BYD
                rho = (abs(u / LIMX) ** 2.6 + abs(v / LIMY) ** 2.6) ** (1 / 2.6)
                cells[(l, i, j)] = {"l": l, "x": u, "y": v, "score": rho + STAGGER_B * l + rng.uniform(-0.03, 0.03)}
    for l in range(1, NLAYER):
        for key, c in cells.items():
            if key[0] != l: continue
            sup = [d["score"] for k, d in cells.items() if k[0] == l - 1 and abs(d["x"] - c["x"]) < BXW * 0.9 and abs(d["y"] - c["y"]) < BYD * 0.9]
            if sup: c["score"] = max(c["score"], max(sup) + 0.002)
    order = sorted(cells.values(), key=lambda c: c["score"])
    return order[:NUNITS]

def rand_rot(flat):
    if flat:
        e = Euler((math.radians(rng.uniform(-22, 22)), math.radians(rng.uniform(-22, 22)), rng.uniform(0, math.tau)), "XYZ")
        return e.to_matrix()
    e = Euler((math.radians(rng.choice((0, 90, 90, 180, 270)) + rng.uniform(-25, 25)), math.radians(rng.uniform(-30, 30)),
              rng.uniform(0, math.tau)), "XYZ")
    return e.to_matrix()

def pack_unit(pf):
    """5-7 copies of one item inside the unit box. Cells overlap a little, so the pile reads as one dense clump."""
    T = TEMPL[pf]; V = T["V"]
    bx, by, bz = BOXS
    flat = next(i[3] for i in ITEMS if i[0] == pf)
    cells = []
    hw, hd, hh = bx * 0.80, by * 0.80, bz * 0.74
    for sx in (-1, 1):
        for sy in (-1, 1):
            cells.append(((sx * bx * 0.09, sy * by * 0.09, -bz / 2 + hh / 2), (hw, hd, hh)))
    ntop = rng.choice((2, 3, 3))
    th = bz * 0.70
    if ntop == 2: tops = [(-bx * 0.2, rng.uniform(-0.02, 0.02), bx * 0.58, by * 0.9), (bx * 0.2, rng.uniform(-0.02, 0.02), bx * 0.58, by * 0.9)]
    else: tops = [(-bx * 0.24, -by * 0.2, bx * 0.5, by * 0.6), (bx * 0.24, -by * 0.2, bx * 0.5, by * 0.6), (0.0, by * 0.22, bx * 0.6, by * 0.5)]
    for tx, ty, w, d in tops:
        cells.append(((tx, ty, bz / 2 - th / 2), (w, d, th)))
    copies = []
    for (cc, cs) in cells:
        R = rand_rot(flat)
        Vr = V @ np.array(R).T
        mn, mx = Vr.min(0), Vr.max(0)
        ext = mx - mn
        s = min(cs[i] / ext[i] for i in range(3))
        cen = (mn + mx) / 2
        pos = Vector(cc) - Vector(tuple(float(a) for a in cen)) * s
        copies.append({"item": pf, "pos": pos, "R": R, "s": float(s), "fit": float(s * max(T["size"]))})
    return copies

def unit_blender_pose(cell):
    return Vector((cell["x"], cell["y"], FLOOR + cell["l"] * BZ + BZ / 2 + 0.002))

def tri_list(me):
    V = [v.co.copy() for v in me.vertices]; T = []
    for p in me.polygons:
        vs = list(p.vertices)
        for i in range(1, len(vs) - 1): T.append((vs[0], vs[i], vs[i + 1]))
    return V, T

def box_bvh(c, size):
    hx, hy, hz = (s / 2 for s in size)
    V = [Vector((c.x + sx * hx, c.y + sy * hy, c.z + sz * hz)) for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]
    T = [(0, 1, 3), (0, 3, 2), (4, 6, 7), (4, 7, 5), (0, 4, 5), (0, 5, 1), (2, 3, 7), (2, 7, 6), (0, 2, 6), (0, 6, 4), (1, 5, 7), (1, 7, 3)]
    return BVHTree.FromPolygons(V, T)

def world_verts(copy, centre):
    T = TEMPL[copy["item"]]
    M = np.array(copy["R"]) * copy["s"]
    return T["V"] @ M.T + np.array(tuple(centre + copy["pos"]))

TRIS = {}
def item_tris(pf):
    if pf not in TRIS:
        me = TEMPL[pf]["obj"].data
        TRIS[pf] = [(p.vertices[0], p.vertices[i], p.vertices[i + 1]) for p in me.polygons for i in range(1, len(p.vertices) - 1)]
    return TRIS[pf]

REASON = [""]
def clip_check(units, frame_bvh):
    bad = []
    for u in units:
        c = unit_blender_pose(u["cell"]); ok = True
        h = Vector(BOXS) / 2
        REASON[0] = ""
        if abs(c.x) + h.x > LIMX or abs(c.y) + h.y > LIMY or c.z - h.z < FLOOR - 1e-6: ok = False; REASON[0] = "limits"
        if frame_bvh.overlap(box_bvh(c, BOXS)): ok = False; REASON[0] += " boxXframe"
        for cp in u["copies"]:
            W = world_verts(cp, c) - np.array(tuple(c))
            if (np.abs(W[:, 0]) > h.x + 1e-3).any() or (np.abs(W[:, 1]) > h.y + 1e-3).any() or (np.abs(W[:, 2]) > h.z + 1e-3).any():
                ok = False; REASON[0] += " chunk-out-of-box"; break
        if ok:
            for cp in u["copies"]:
                W = world_verts(cp, c)
                if frame_bvh.overlap(BVHTree.FromPolygons([Vector(tuple(float(a) for a in w)) for w in W], item_tris(cp["item"]))):
                    ok = False; REASON[0] = "chunkXframe"; break
        if not ok: bad.append(u["index"]); print("clip", u["index"], u["cell"]["l"], round(u["cell"]["x"],2), round(u["cell"]["y"],2), REASON[0])
    # unit boxes must not overlap one another either
    for a in range(len(units)):
        ca = unit_blender_pose(units[a]["cell"])
        for b in range(a + 1, len(units)):
            cb = unit_blender_pose(units[b]["cell"])
            if abs(ca.x - cb.x) < BOXS[0] - 1e-4 and abs(ca.y - cb.y) < BOXS[1] - 1e-4 and abs(ca.z - cb.z) < BOXS[2] - 1e-4:
                bad += [a, b]
    return sorted(set(bad))

QUOTA = {"CopperOre": 16, "TinOre": 12, "IronScrap": 12, "SilverOre": 9, "BlackMetalScrap": 11, "FlametalOreNew": 7, "Coal": 8, "IronOre": 5}
def build_units():
    cells = layer_cells()
    units, placed = [], []
    left = dict(QUOTA)
    for n, cell in enumerate(cells):
        near = [p for p in placed if math.hypot(p[0] - cell["x"], p[1] - cell["y"]) < 0.5 and left[p[2]] > 0]
        if near and rng.random() < 0.45: pf = min(near, key=lambda p: math.hypot(p[0] - cell["x"], p[1] - cell["y"]))[2]
        else:
            opts = [k for k, v in left.items() if v > 0]
            pf = rng.choices(opts, weights=[left[k] for k in opts])[0]
        left[pf] -= 1
        placed.append((cell["x"], cell["y"], pf))
        units.append({"index": n, "step": n * 8 // NUNITS, "cell": cell, "item": pf, "copies": pack_unit(pf)})
    return units

# ---------- anchors export (Unity prefab space) ----------
CB2U = Matrix(((-1, 0, 0), (0, 0, 1), (0, -1, 0)))
def b2u_vec(v): return (-v[0], v[2], -v[1])
def rot_to_unity(R):
    Ru = CB2U @ R @ CB2U.transposed()
    q = Ru.to_quaternion()
    e = Ru.to_euler("ZXY")
    ex = Matrix.Rotation(e.x, 3, "X"); ey = Matrix.Rotation(e.y, 3, "Y"); ez = Matrix.Rotation(e.z, 3, "Z")
    err = max(abs(a - b) for ra, rb in zip((ey @ ex @ ez), Ru) for a, b in zip(ra, rb))
    return [round(math.degrees(e.x), 3), round(math.degrees(e.y), 3), round(math.degrees(e.z), 3)], [round(q.x, 5), round(q.y, 5), round(q.z, 5), round(q.w, 5)], err

def export_anchors(units, frame_tris, clip_bad):
    maxerr = 0
    out_units = []
    for u in units:
        c = unit_blender_pose(u["cell"])
        cps = []
        for cp in u["copies"]:
            eul, quat, err = rot_to_unity(cp["R"]); maxerr = max(maxerr, err)
            cps.append({"item": cp["item"], "offset": [round(a, 4) for a in b2u_vec(cp["pos"])], "euler": eul, "quat_xyzw": quat,
                        "scale": round(cp["s"], 4), "fit_longest_m": round(cp["fit"], 3)})
        out_units.append({"index": u["index"], "step": u["step"], "kind": "heap_step", "item": u["item"],
                          "position": [round(a, 4) for a in b2u_vec(c)], "rotation": [0, 0, 0],
                          "box": [round(BOXS[0], 4), round(BOXS[2], 4), round(BOXS[1], 4)], "layer": u["cell"]["l"], "copies": cps})
    items = {}
    for pf, *_ in ITEMS:
        T = TEMPL[pf]
        items[pf] = {"bounds_size_unity": [round(T["size"][0], 4), round(T["size"][2], 4), round(T["size"][1], 4)],
                     "bounds_center_unity": [round(a, 4) for a in b2u_vec(T["center"])]}
    doc = {
        "bin": "OreBin round 2", "slots": NUNITS, "units": len(out_units), "steps": 8, "stack_per_unit": 1,
        "frame": {"obj": "OreBin.obj", "tris": frame_tris, "size_m": [2 * HX, POSTH, 2 * HY], "atlas": "orebin_atlas.png 128x128"},
        "space": "Unity prefab space, origin = bin footprint centre on the ground. Blender z-up/-y front -> Unity y-up/+z front: ux=-bx, uy=bz, uz=-by. "
                 "OBJ export (forward NEGATIVE_Z, up Y) writes (bx, bz, -by); Unity's importer negates x, same mapping.",
        "unit_semantics": "unit.position = centre of the unit box; unit.box = the space the unit may fill (x, y, z in Unity axes). "
                          "Each copy: place the item's prefab so that its BOUNDS CENTRE sits at unit.position + copy.offset, rotated by copy.euler "
                          "(Unity Quaternion.Euler, ZXY) or copy.quat_xyzw, uniform scale copy.scale relative to the item prefab's native size. "
                          "Item root = bounds centre - R * (scale * item.bounds_center_unity). Every copy is inside the box (checked).",
        "fill_order": "units are listed in fill order; show the first n. Hand units out to stored items one stack each; the demo item per "
                      "unit is only a placeholder, copies must be re-pointed to the real item (scale = fit_longest_m / item longest bound).",
        "items": items, "clip_check": {"clipping": len(clip_bad), "of": len(out_units)},
        "rotation_convert_max_err": maxerr, "units_list": out_units}
    json.dump(doc, open(os.path.join(OUTA, "orebin_anchors.json"), "w"), indent=1)
    return maxerr

# ---------- scene ----------
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
atlas = build_atlas()
MAT = bpy.data.materials.new("orebin"); MAT.use_nodes = True
nt = MAT.node_tree; bsdf = nt.nodes["Principled BSDF"]
ti = nt.nodes.new("ShaderNodeTexImage"); ti.image = atlas; ti.interpolation = "Closest"
nt.links.new(ti.outputs["Color"], bsdf.inputs["Base Color"])
bsdf.inputs["Roughness"].default_value = 0.8

def tris(obs): return sum(len(p.vertices) - 2 for o in obs for p in o.data.polygons)
def join(obs, name):
    bpy.ops.object.select_all(action="DESELECT")
    for o in obs: o.select_set(True)
    bpy.context.view_layer.objects.active = obs[0]
    bpy.ops.object.join(); ob = bpy.context.active_object; ob.name = name
    return ob

load_templates()
rng.seed(21); PARTS.clear()
build_frame()
frame = join(list(PARTS), "OreBin")
frame_tris = tris([frame])
V, T = tri_list(frame.data)
fbvh = BVHTree.FromPolygons(V, T, all_triangles=True)
units = build_units()
bad = clip_check(units, fbvh)
print("CLIPPING", len(bad), "of", len(units), bad)
lc = {}
for u in units: lc[u["cell"]["l"]] = lc.get(u["cell"]["l"], 0) + 1
print("layers", lc, "items", {pf: sum(1 for u in units if u["item"] == pf) for pf, *_ in ITEMS})
err = export_anchors(units, frame_tris, bad)
print("rotation convert err", err)
bpy.ops.object.select_all(action="DESELECT"); frame.select_set(True)
bpy.ops.wm.obj_export(filepath=os.path.join(OUTA, "OreBin.obj"), export_selected_objects=True, export_materials=False,
                      export_triangulated_mesh=True, forward_axis="NEGATIVE_Z", up_axis="Y")
print("OREBIN frame tris", frame_tris, "item tris (100%)", sum(len(item_tris(cp["item"])) for u in units for cp in u["copies"]),
      "copies", sum(len(u["copies"]) for u in units))

FILLS = (0.1, 0.5, 1.0)
SPACE = 3.0
bins_x = {0.1: -SPACE, 0.5: 0.0, 1.0: SPACE}
def spawn_bin(fill, dx):
    fr = frame if fill == 1.0 else frame.copy()
    if fill != 1.0: sc.collection.objects.link(fr)
    fr.location.x = dx
    n = round(fill * len(units))
    for u in units[:n]:
        c = unit_blender_pose(u["cell"])
        for k, cp in enumerate(u["copies"]):
            ob = bpy.data.objects.new(f"u{u['index']:03d}_{k}", TEMPL[cp["item"]]["obj"].data)
            sc.collection.objects.link(ob)
            ob.matrix_world = Matrix.Translation(Vector((dx, 0, 0)) + c + cp["pos"]) @ cp["R"].to_4x4() @ Matrix.Diagonal((cp["s"],) * 3 + (1,))
for f in FILLS: spawn_bin(f, bins_x[f])

# player-height marker (plain 1.8 m post) and the vanilla wood chest, reference only (never exported)
pm = bpy.data.materials.new("plain"); pm.use_nodes = True
pm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.55, 0.52, 0.46, 1)
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(-6.2, -0.6, 0.9)); pst = bpy.context.active_object
pst.scale = (0.14, 0.14, 1.8); pst.data.materials.append(pm); pst.name = "post_1.8m"
if "--no-ref" not in argv:
    rep = json.load(open("C:/Users/joost/ValheimRip/chests/report.json"))["piece_chest_wood"]["nodes"]
    vimg = bpy.data.images.load(f"{RIP}/woodchest_d.png")
    vm = bpy.data.materials.new("ref"); vm.use_nodes = True
    vt = vm.node_tree.nodes.new("ShaderNodeTexImage"); vt.image = vimg; vt.interpolation = "Closest"
    vm.node_tree.links.new(vt.outputs["Color"], vm.node_tree.nodes["Principled BSDF"].inputs["Base Color"])
    for node in rep:
        if not node["path"].endswith(("/woodchest", "/woodchesttop_closed")): continue
        Vv, Tt, F = [], [], []
        for l in open(node["mesh"]["obj"]):
            p = l.split()
            if not p: continue
            if p[0] == "v": Vv.append(Vector((-float(p[1]), float(p[2]), float(p[3]))))
            elif p[0] == "vt": Tt.append((float(p[1]), float(p[2])))
            elif p[0] == "f": F.append([tuple(int(x) - 1 for x in q.split("/")[:2]) for q in reversed(p[1:])])
        q = node["rot"]; from mathutils import Quaternion
        M = Matrix.Translation(Vector(node["pos"])) @ Quaternion((q[3], q[0], q[1], q[2])).to_matrix().to_4x4() \
            @ Matrix.Diagonal((*node["scale"], 1))
        verts = [M @ v for v in Vv]
        verts = [Vector((-v.x - 5.1, -v.z, v.y)) for v in verts]
        F = [list(reversed(f)) for f in F]
        me = bpy.data.meshes.new("ref"); me.from_pydata(verts, [], [[c[0] for c in f] for f in F])
        uvl = me.uv_layers.new(); i = 0
        for f in F:
            for c in f: uvl.data[i].uv = Tt[c[1]]; i += 1
        ob = bpy.data.objects.new("ref", me); sc.collection.objects.link(ob); ob.data.materials.append(vm)

world = bpy.data.worlds.new("w"); sc.world = world; world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.42, 0.45, 0.5, 1)
world.node_tree.nodes["Background"].inputs[1].default_value = 0.9
sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN")); sun.data.energy = 3.2
sun.rotation_euler = (math.radians(50), 0, math.radians(35)); sc.collection.objects.link(sun)
bpy.ops.mesh.primitive_plane_add(size=40)
gm = bpy.data.materials.new("ground"); gm.use_nodes = True
gm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.16, 0.14, 0.11, 1)
bpy.context.active_object.data.materials.append(gm)
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam); sc.camera = cam
sc.render.engine = "BLENDER_EEVEE_NEXT"
sc.render.resolution_x, sc.render.resolution_y = (1000, 562) if QUICK else (1600, 900)
sc.view_settings.view_transform = "Standard"
VIEWS = {"fills": (-6, 28, 17.0, (-1.5, 0, 0.5)), "close": (-26, 30, 5.2, (SPACE, 0, 0.5)),
         "alt": (62, 36, 6.4, (SPACE, 0, 0.45))}
for vn, (yaw, pitch, dist, tgt) in VIEWS.items():
    if VIEWSEL and vn not in VIEWSEL: continue
    t = Vector(tgt)
    d = Vector((math.cos(math.radians(pitch)) * math.sin(math.radians(yaw)),
                -math.cos(math.radians(pitch)) * math.cos(math.radians(yaw)), math.sin(math.radians(pitch))))
    cam.location = t + d * dist; cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    sc.render.filepath = os.path.join(OUT, f"{TAG}-{vn}.png")
    bpy.ops.render.render(write_still=True)
print("DONE")
