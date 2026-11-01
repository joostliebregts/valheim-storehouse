"""Ore Bin round 3. Our own furniture mesh and own 128x128 atlas; the CONTENTS are the game's own item models, now PHYSICALLY
SETTLED with Blender rigid bodies (convex-hull items dropped in fill order into six stone/timber compartments).
Run: blender -b -P orebin_r3.py -- [--out DIR] [--tag NAME] [--no-ref] [--quick] [--views fills,close,alt] [--frame-only] [--scale F]

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
OUTA = os.path.normpath(os.path.join(HERE, "..", "assets", "orebin_r3"))
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = argv[argv.index("--out") + 1] if "--out" in argv else OUTA
TAG = argv[argv.index("--tag") + 1] if "--tag" in argv else "orebin"
QUICK = "--quick" in argv
FRAME_ONLY = "--frame-only" in argv
ISC = float(argv[argv.index("--scale") + 1]) if "--scale" in argv else 0.87
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
STONES = [srgb(c) for c in ((0.38, 0.35, 0.31), (0.30, 0.29, 0.27), (0.41, 0.37, 0.31), (0.27, 0.27, 0.26))]   # darker than r2: sunlit lining no longer washes out to pale
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
        t = blocky(32, 32, 8) * 0.40 + blocky(32, 32, 4) * 0.34 + blocky(32, 32, 2) * 0.18 + nr.random((32, 32)) * 0.14
        t = np.clip(t, 0, 1)
        tile_img = (base * 0.50) * (1 - t[..., None]) + np.clip(base * 1.20, 0, 1) * t[..., None]
        lm = (blocky(32, 32, 2) > 0.96)[..., None]
        tile_img = np.where(lm, tile_img * 0.55 + LICHEN * 0.45, tile_img)
        lit = ((yy >= 28) | (xx <= 3)) & (edge >= 3)          # chisel highlight (v up = row up)
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

FLOOR = 0.14
HX, HY, PS = 1.08, 0.78, 0.18            # outer half sizes, post section
PX, PY = HX - PS / 2, HY - PS / 2
LIMX, LIMY = HX - PS, HY - PS            # interior half sizes 1.05 x 0.60
TWL = 0.16                               # stone wall thickness
COURSE, NCOURSE = 0.18, 3
WALLTOP = FLOOR + COURSE * NCOURSE       # 0.74
POSTH = 1.05
DIVT = 0.08                              # stone divider thickness (x), timber cross divider thickness 0.06 (y)
CELLW = (2 * LIMX - 2 * DIVT) / 3        # three compartments across
DIVX = (-LIMX + CELLW + DIVT / 2, LIMX - CELLW - DIVT / 2)

def stone_wall(a0, a1, cross, axis, t=None, jit=0.012):
    """Courses of rough blocks from a0 to a1 along `axis` ('x' or 'y'), wall centre line at `cross`, thickness t. A dark core
    slab behind the blocks keeps the wall solid wherever the blocks have joints."""
    t = TWL if t is None else t
    L = a1 - a0
    mid = (a0 + a1) / 2
    zc0 = FLOOR + COURSE * NCOURSE / 2
    if axis == "x": box("stonecore", (L, t * 0.7, COURSE * NCOURSE - 0.01), (mid, cross, zc0), kind="stone", jitter=0.0, bevel=0)
    else: box("stonecore", (t * 0.7, L, COURSE * NCOURSE - 0.01), (cross, mid, zc0), kind="stone", jitter=0.0, bevel=0)
    for c in range(NCOURSE):
        zc = FLOOR + COURSE * (c + 0.5)
        a = a0 - (0.0 if c % 2 == 0 else 0.17)
        while a < a1 - 0.03:
            w = rng.uniform(0.30, 0.52)
            lo, hi = max(a, a0), min(a + w, a1)
            if a1 - hi < 0.22: hi = a1
            if hi - lo > 0.12:
                zz = zc + rng.uniform(-0.006, 0.006)
                if axis == "x": box("stone", (hi - lo - 0.02, t, COURSE - 0.02), ((lo + hi) / 2, cross, zz), kind="stone", jitter=jit, bevel=0.012, rough=True)
                else: box("stone", (t, hi - lo - 0.02, COURSE - 0.02), (cross, (lo + hi) / 2, zz), kind="stone", jitter=jit, bevel=0.012, rough=True)
            a = hi if hi > a + 0.05 else a + w
    return

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
    for dx in DIVX:                                          # stone dividers between the three compartments
        stone_wall(-LIMY, LIMY, dx, "y", t=DIVT, jit=0.008)
        box("divcap", (0.12, 2 * LIMY, 0.04), (dx, 0, WALLTOP + 0.02), rot=(0, 0, rng.uniform(-0.3, 0.3)), jitter=0.004, bevel=0.006)
    box("crossdiv", (2 * LIMX, 0.06, WALLTOP - FLOOR), (0, 0, FLOOR + (WALLTOP - FLOOR) / 2), jitter=0.004, bevel=0.008)   # timber, splits each into front/back
    box("crosscap", (2 * LIMX, 0.10, 0.04), (0, 0, WALLTOP + 0.02), jitter=0.004, bevel=0.006)
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

# ---------- contents: real item models, settled by rigid-body physics ----------
ITEMS = [  # prefab, label, longest side in metres at 100% scale (round-2 mean), flat? (thin scrap sheet)
    ("CopperOre", "copper ore", 0.174, False), ("TinOre", "tin ore", 0.157, False), ("IronScrap", "iron scrap", 0.215, True),
    ("SilverOre", "silver ore", 0.170, False), ("BlackMetalScrap", "black metal scrap", 0.212, True),
    ("FlametalOreNew", "flametal ore", 0.164, False)]
QUOTA = {"CopperOre": 12, "TinOre": 15, "IronScrap": 14, "SilverOre": 14, "BlackMetalScrap": 15, "FlametalOreNew": 10}   # 80 stacks
# compartment layout: 3 columns (x) x front/back rows (y); (col, row) -> prefab
LAYOUT = {(0, 1): "CopperOre", (1, 1): "FlametalOreNew", (2, 1): "SilverOre",
          (0, 0): "TinOre", (1, 0): "BlackMetalScrap", (2, 0): "IronScrap"}
NUNITS = 80
SAFE = 0.012          # collider sits this far inside the nominal inner face, jitter of the rough blocks included
MARGIN = 0.003
FPS = 24

def cell_bounds(col, row):
    x0 = -LIMX + col * (CELLW + DIVT); x1 = x0 + CELLW
    y0, y1 = (-LIMY, -0.03) if row == 0 else (0.03, LIMY)
    # colliders sit clear of the rough stone, of the divider caps (they overhang 2 cm) and of the vertical rail face in front
    ix0 = 0.025 if col == 0 else 0.03; ix1 = 0.025 if col == 2 else 0.03
    iy0 = 0.025 if row == 0 else 0.045; iy1 = 0.045 if row == 0 else 0.03
    return (x0 + ix0, x1 - ix1, y0 + iy0, y1 - iy1)

TEMPL = {}          # prefab -> {mesh (scaled, centred on bounds centre), s, size, center, V, hull}
def load_templates():
    for pf, _lab, fit, _flat in ITEMS:
        objs = load_item(pf, anchor="center")
        ob = objs[0]
        info = json.load(open(f"{ITEMS_DIR}/{pf}/info.json"))
        bmin, bmax = Vector(info["bounds_min"]), Vector(info["bounds_max"])
        size = bmax - bmin
        s = fit * ISC / max(size)
        ob.data.transform(Matrix.Diagonal((s, s, s, 1)))
        ob.data.update()
        ob.location = (0, 0, 0); ob.scale = (1, 1, 1)
        if pf == "TinOre":                  # blown-out white crystals -> pale grey
            for m in ob.data.materials:
                b = m.node_tree.nodes.get("Principled BSDF")
                if b and not any(n.type == "TEX_IMAGE" for n in m.node_tree.nodes): b.inputs["Base Color"].default_value = (0.62, 0.64, 0.68, 1)
        if pf == "BlackMetalScrap":     # the ripped tint is a vivid green (reads as leaves); render it as dark metal instead
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
            seq.append(((k + 0.5) / q + rng.uniform(-0.01, 0.01), col, row, pf, k))
    seq.sort(key=lambda t: t[0])
    units = []
    for n, (_sc, col, row, pf, k) in enumerate(seq[:NUNITS]):
        units.append({"index": n, "step": n * 8 // NUNITS, "col": col, "row": row, "item": pf, "k": k, "ncopy": rng.choice((5, 6, 6, 7)), "copies": []})
    return units

# ---------- rigid-body simulation ----------
def make_box_mesh(name, size):
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts: v.co = Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2]))
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    return me

def add_rb(ob, kind, shape, mass=1.0, damp=(0.85, 0.95)):
    for o in bpy.context.view_layer.objects: o.select_set(False)
    ob.select_set(True); bpy.context.view_layer.objects.active = ob
    bpy.ops.rigidbody.object_add(type=kind)
    rb = ob.rigid_body
    rb.collision_shape = shape; rb.friction = 0.8; rb.restitution = 0.0
    rb.use_margin = True; rb.collision_margin = MARGIN
    if kind == "ACTIVE":
        rb.mass = mass; rb.linear_damping, rb.angular_damping = damp
        rb.use_deactivation = False

def euler_rand(flat):
    if flat:
        return Euler((math.radians(rng.uniform(-12, 12)), math.radians(rng.uniform(-12, 12)), rng.uniform(0, math.tau)), "XYZ")
    return Euler((rng.uniform(0, math.tau), rng.uniform(0, math.tau), rng.uniform(0, math.tau)), "XYZ")

SIMLOG = {"frames": [], "wall": 0.0, "unsettled": 0, "resid": []}
def simulate_all(units):
    import time
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
        T = 0.2
        walls = [("floor", (x1 - x0 + 2 * T, y1 - y0 + 2 * T, T), (cx, cy, FLOOR + 0.006 - T / 2)),
                 ("wx0", (T, y1 - y0 + 2 * T, 2.0), (x0 - T / 2, cy, FLOOR + 1.0)), ("wx1", (T, y1 - y0 + 2 * T, 2.0), (x1 + T / 2, cy, FLOOR + 1.0)),
                 ("wy0", (x1 - x0, T, 2.0), (cx, y0 - T / 2, FLOOR + 1.0)), ("wy1", (x1 - x0, T, 2.0), (cx, y1 + T / 2, FLOOR + 1.0))]
        for nm, sz, pos in walls:
            ob = bpy.data.objects.new(f"col_{col}{row}_{nm}", make_box_mesh(nm, sz)); ob.location = pos
            sc.collection.objects.link(ob); add_rb(ob, "PASSIVE", "BOX"); ob.hide_render = True
        sc.frame_set(1)
        top = FLOOR
        for u in [u for u in units if u["col"] == col and u["row"] == row]:
            T_ = TEMPL[u["item"]]
            flat = next(i[3] for i in ITEMS if i[0] == u["item"])
            obs = []
            gap = 0.9 * max(T_["size"]) * T_["s"] * (0.8 if flat else 1.0)
            for k in range(u["ncopy"]):
                ob = bpy.data.objects.new(f"u{u['index']:03d}_{k}", T_["mesh"]); sc.collection.objects.link(ob)
                ob.rotation_euler = euler_rand(flat)
                ob.location = (cx + rng.uniform(-0.09, 0.09), cy + rng.uniform(-0.09, 0.09), top + 0.06 + gap * (k + 0.6))
                add_rb(ob, "ACTIVE", "CONVEX_HULL", mass=max(0.05, T_["vol"] * 700))
                obs.append(ob)
            sc.frame_set(1)
            prev = None; still = 0; f = 1; dp = dr = 0.0
            while f < 300:
                f += 1; sc.frame_set(f)
                cur = [(o.matrix_world.translation.copy(), o.matrix_world.to_quaternion()) for o in obs]
                if prev:
                    dp = max((a[0] - b[0]).length for a, b in zip(cur, prev))
                    dr = max(a[1].rotation_difference(b[1]).angle for a, b in zip(cur, prev))
                    still = still + 1 if (dp < 2e-4 and dr < 4e-3 and f > 8) else 0
                    if still >= 3: break
                prev = cur
            SIMLOG["resid"].append((round(dp * 1000, 3), round(dr, 4)))
            if still < 3: SIMLOG["unsettled"] += 1
            SIMLOG["frames"].append(f)
            Ms = [o.matrix_world.copy() for o in obs]
            for o in obs: o.rigid_body.type = "PASSIVE"
            for o, M in zip(obs, Ms): o.matrix_world = M
            bpy.context.view_layer.update()
            sc.frame_set(1)
            for o, M in zip(obs, Ms):
                u["copies"].append({"item": u["item"], "M": M.copy(), "obj": o})
            zt = max(float(max((M @ Vector(tuple(map(float, v)))).z for v in T_["hv"][::3])) for M in Ms)
            top = max(top, zt)
        cells[(col, row)] = top
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
            if frame_bvh.overlap(bt): bad.append((u["index"], k)); print("clip", u["index"], k, cp["item"], "cell", (u["col"], u["row"]), "min", [round(float(W[:, i].min()), 3) for i in range(3)], "max", [round(float(W[:, i].max()), 3) for i in range(3)])
    return bad

def interpenetration(units):
    """Deepest vertex-in-hull penetration between any two copies (hull vertices of A inside the convex hull of B)."""
    cps = [cp for u in units for cp in u["copies"]]
    P = np.array([np.array(cp["M"])[:3, 3] for cp in cps]); R = np.array([TEMPL[cp["item"]]["radius"] for cp in cps])
    worst = (0.0, None)
    best = [-9.0]
    npairs = 0
    over = []
    for i in range(len(cps)):
        d = np.linalg.norm(P - P[i], axis=1)
        for j in np.nonzero((d < R + R[i]) & (np.arange(len(cps)) > i))[0]:
            npairs += 1
            for a, b in ((i, int(j)), (int(j), i)):
                Ma, Mb = np.array(cps[a]["M"]), np.array(cps[b]["M"])
                Ta, Tb = TEMPL[cps[a]["item"]], TEMPL[cps[b]["item"]]
                x = Ta["hv"] @ Ma[:3, :3].T + Ma[:3, 3]
                xb = (x - Mb[:3, 3]) @ Mb[:3, :3]            # into B local (rotation orthogonal)
                pl = Tb["planes"]
                sd = pl[:, 3][None, :] - xb @ pl[:, :3].T        # distance inside each plane
                dep = sd.min(axis=1)
                m = float(dep.max())
                best[0] = max(best[0], m)
                if m > 0: over.append(m)
                if m > worst[0]: worst = (m, (a, b))
    return worst[0], npairs, over, worst[1], best[0]

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

def export_anchors(units, frame_tris, clip_bad, ncop, pen):
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
                      "x": [round(-x1, 4), round(-x0, 4)], "z": [round(-y1, 4), round(-y0, 4)], "floor_y": FLOOR})
    doc = {
        "bin": "OreBin round 3 (physically settled)", "slots": NUNITS, "units": len(out_units), "steps": 8, "stack_per_unit": 1,
        "frame": {"obj": "OreBin.obj", "tris": frame_tris, "size_m": [2 * HX, POSTH, 2 * HY], "atlas": "orebin_atlas.png 128x128"},
        "space": "Unity prefab space, origin = bin footprint centre on the ground. Blender z-up/-y front -> Unity y-up/+z front: ux=-bx, uy=bz, uz=-by. "
                 "OBJ export (forward NEGATIVE_Z, up Y) writes (bx, bz, -by); Unity's importer negates x, same mapping.",
        "unit_semantics": "SETTLED: every copy has an explicit final pose from a rigid-body simulation (convex-hull items, friction 0.8, restitution 0, "
                          "dropped stack by stack in fill order, earlier stacks frozen). unit.position = mean of the copy centres; each copy: place the "
                          "item's prefab so that its BOUNDS CENTRE sits at unit.position + copy.offset (= copy.world_position, prefab space), rotated by copy.euler "
                          "(Unity Quaternion.Euler, ZXY) or copy.quat_xyzw, uniform scale copy.scale relative to the item prefab's native size. "
                          "Item root = bounds centre - R * (scale * item.bounds_center_unity). unit.box = bounding box of the unit's copies (informational).",
        "fill_order": "units are listed in fill order; show the first n. Later stacks lie on earlier ones, earlier stacks never move. "
                      "Each compartment holds one item type (compartments[]); unit.item is its type, copies keep it.",
        "compartments": comps, "items": items, "clip_check": {"clipping": len(clip_bad), "of_copies": ncop},
        "interpenetration_max_m": round(pen, 5), "rotation_convert_max_err": maxerr, "units_list": out_units}
    json.dump(doc, open(os.path.join(OUTA, "orebin_anchors.json"), "w"), indent=1)
    return maxerr

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
bsdf.inputs["Specular IOR Level"].default_value = 0.0      # no grazing-angle sheen: the old lining read as glass

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
units = []
if not FRAME_ONLY:
    units = build_order()
    simulate_all(units)
    ncop = sum(len(u["copies"]) for u in units)
    print("SIM wall", round(SIMLOG["wall"], 1), "s; frames per stack: mean", round(sum(SIMLOG["frames"]) / len(SIMLOG["frames"]), 1),
          "max", max(SIMLOG["frames"]), "(at", FPS, "fps); unsettled stacks", SIMLOG["unsettled"], "; heap tops", SIMLOG["tops"])
    bad = clip_check(units, fbvh)
    print("CLIPPING", len(bad), "of", ncop, "copies", bad)
    pen, npairs, over, wp, best = interpenetration(units)
    print("INTERPENETRATION max", round(pen * 1000, 2), "mm over", npairs, "near pairs;", len(over), "pairs penetrate, median",
          round(float(np.median(over)) * 1000, 2) if over else 0, "mm; closest hull-vertex approach", round(best * 1000, 2), "mm (negative = clear); margin", MARGIN * 1000, "mm")
    print("residual per-frame move at freeze (mm, rad): worst", max(SIMLOG["resid"]), "; unsettled-flagged", SIMLOG["unsettled"])
    err = export_anchors(units, frame_tris, bad, ncop, pen)
    print("rotation convert err", err)
    json.dump({"frames": SIMLOG["frames"]}, open(os.path.join(OUT, "simlog.json"), "w"))
    # drop the simulation objects; the fills are re-spawned from the settled poses
    for u in units:
        for cp in u["copies"]: bpy.data.objects.remove(cp["obj"], do_unlink=True)
    for o in [o for o in bpy.data.objects if o.name.startswith("col_")]: bpy.data.objects.remove(o, do_unlink=True)
    bpy.ops.rigidbody.world_remove()
bpy.ops.object.select_all(action="DESELECT"); frame.select_set(True)
bpy.ops.wm.obj_export(filepath=os.path.join(OUTA, "OreBin.obj"), export_selected_objects=True, export_materials=False,
                      export_triangulated_mesh=True, forward_axis="NEGATIVE_Z", up_axis="Y")
print("OREBIN frame tris", frame_tris, "item tris (100%)", sum(len(TEMPL[cp["item"]]["tris"]) for u in units for cp in u["copies"]),
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
        for k, cp in enumerate(u["copies"]):
            ob = bpy.data.objects.new(f"u{u['index']:03d}_{k}", TEMPL[cp["item"]]["mesh"])
            sc.collection.objects.link(ob)
            ob.matrix_world = Matrix.Translation((dx, 0, 0)) @ cp["M"]
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
VIEWS = {"fills": (-6, 44, 16.0, (-1.5, 0, 0.3)), "close": (-26, 30, 5.2, (SPACE, 0, 0.5)),
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
