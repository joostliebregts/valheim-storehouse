"""Meat Rack, ROUND 2: mass storage. Our own frame mesh and atlas (no vanilla geometry or texture in the exported files);
the contents are the game's own item models, placed at exported ANCHORS (JSON) by the mod.
Run: blender -b -P meatrack_r2.py -- [--out DIR] [--tag NAME] [--no-ref]
Writes into assets/meatrack_r2/:  MeatRack.obj (frame only, forward -Z, up Y, triangulated, no materials),
  meatrack_atlas.png (128x128, point-filtered), MeatRackAnchors.json (units in fill order), meatrack.json (stats).

Atlas 128x128, four 32 px strips (v from the top): 0.75-1.0 hewn timber | 0.5-0.75 end grain (4 tiles) |
  0.25-0.5 salted/stained wood (tray, bins) | 0.0-0.25 left half iron, right half hemp cord.

Layout (2.0 m wide, 1.97 m high, A-frame kept): ridge row (8 meat strings) + upper rail each side (8 fish bundles each)
+ lower rail each side (8 bundles each) = 40 hung stacks; a drip tray on the floor holds 6 open salting bins with
6 piles each = 36 piled stacks. 76 stacks in total (a black metal chest holds 32).

Coordinates: scene is Blender z-up, front = -y, floor z=0, rack centred on x=y=0. The anchors JSON is in Unity prefab
space with the SAME origin: ux = -bx, uy = bz, uz = -by (vectors the same; rotation matrices R_u = M R_b M^T, M the same map).
"""
import bpy, bmesh, sys, os, math, json, random
import numpy as np
from mathutils import Vector, Matrix, Euler, Quaternion
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
OUTA = os.path.normpath(os.path.join(HERE, "..", "assets", "meatrack_r2"))
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = argv[argv.index("--out") + 1] if "--out" in argv else \
    "C:/Users/joost/AppData/Local/Temp/claude/C--Users-joost--pai/5e4bc60b-cdfe-4638-8e29-2e507fa13cf9/scratchpad/proto2/meatrack"
TAG = argv[argv.index("--tag") + 1] if "--tag" in argv else "meatrack"
RIP = "C:/Users/joost/ValheimRip/chests/piece_chest_wood"
ITEMS_DIR = "C:/Users/joost/ValheimRip/items"
sys.path.append(ITEMS_DIR)
from load_item import load_item
os.makedirs(OUTA, exist_ok=True); os.makedirs(OUT, exist_ok=True)
rng = random.Random(7)

TEXW = TEXH = 128
DENS = 48.0
SH = 32.0 / TEXH
STRIP = {"hewn": 0.75, "end": 0.5, "stain": 0.25, "misc": 0.0}

# ---------- texture ----------
def srgb(c): return np.array(c, dtype=np.float32)
WOOD, WOOD_D = srgb((0.38, 0.29, 0.18)), srgb((0.21, 0.16, 0.10))
STAIN, STAIN_D = srgb((0.28, 0.22, 0.15)), srgb((0.14, 0.11, 0.08))
END, END_D = srgb((0.55, 0.45, 0.31)), srgb((0.35, 0.27, 0.17))
IRON, IRON_D = srgb((0.22, 0.21, 0.20)), srgb((0.09, 0.09, 0.09))
HEMP, HEMP_D = srgb((0.46, 0.38, 0.25)), srgb((0.30, 0.24, 0.15))

def build_atlas():
    nr = np.random.default_rng(3)
    img = np.zeros((TEXH, TEXW, 3), np.float32)          # row 0 = v 0 (bottom)
    x = np.arange(TEXW)[None, :].repeat(32, 0).astype(np.float32)
    y = np.arange(32)[:, None].repeat(TEXW, 1).astype(np.float32)
    tile = lambda k: 2 * math.pi * k / TEXW

    def grain(c1, c2, rows, salt=0.0):
        g = np.sin(y * 1.25 + 1.6 * np.sin(x * tile(2) + y * 0.15) + 0.7 * np.sin(x * tile(5)))
        t = np.clip((g - 0.55) * 2.5, 0, 1) * 0.65 + nr.random((32, TEXW)) * 0.18
        t += np.clip(1 - np.minimum(y, 31 - y) / 3.0, 0, 1) * 0.35
        col = c1 * (1 - t[..., None]) + c2 * t[..., None]
        if salt:
            sp = (nr.random((32, TEXW)) < salt)[..., None]
            col = np.where(sp, col * 0.5 + srgb((0.72, 0.70, 0.64)) * 0.5, col)     # faint salt crust
        img[rows] = col
    grain(WOOD, WOOD_D, slice(96, 128))
    for k in range(4):
        cx, cy = 15.5 + nr.uniform(-2, 2), 15.5 + nr.uniform(-2, 2)
        xx, yy = np.meshgrid(np.arange(32), np.arange(32))
        d = np.hypot(xx - cx, yy - cy) + 0.6 * np.sin(np.arctan2(yy - cy, xx - cx) * 3 + k)
        t = (np.sin(d * 1.5) * 0.5 + 0.5) * 0.45 + nr.random((32, 32)) * 0.15
        t = np.where(d > 13.5, 0.95, t)
        img[64:96, 32 * k:32 * k + 32] = END * (1 - t[..., None]) + END_D * t[..., None]
    grain(STAIN, STAIN_D, slice(32, 64), salt=0.035)
    t = nr.random((32, 64)) * 0.4 + np.clip(1 - np.minimum(y[:, :64], 31 - y[:, :64]) / 4.0, 0, 1) * 0.5
    img[0:32, 0:64] = IRON * (1 - t[..., None]) + IRON_D * t[..., None]
    yy, xx = np.mgrid[0:32, 0:64].astype(np.float32)
    nz = nr.random((32, 64))
    rope = np.where(((xx + yy * 0.5) % 6) < 3, 1.0, 0.78)
    img[0:32, 64:128] = (HEMP * (0.86 + 0.28 * nz[..., None])) * rope[..., None]
    im = bpy.data.images.new("meatrack_atlas", TEXW, TEXH, alpha=False)
    px = np.concatenate([np.clip(img, 0, 1), np.ones((TEXH, TEXW, 1), np.float32)], 2)
    im.pixels.foreach_set(px.ravel())
    im.filepath_raw = os.path.join(OUTA, "meatrack_atlas.png"); im.file_format = "PNG"; im.save()
    return im

# ---------- frame geometry ----------
PARTS = []
UV = None

def uv_face(f, kind, long_axis, seed):
    n = f.normal
    ax = max(range(3), key=lambda i: abs(n[i]))
    tang = [i for i in range(3) if i != ax]
    if kind in ("iron", "hemp"):
        u0 = 0.02 if kind == "iron" else 0.52
        ou, ov = rng.uniform(0, 0.18), rng.uniform(0, 0.10)
        cmin = [min(l.vert.co[t] for l in f.loops) for t in tang]
        for l in f.loops:
            a = (l.vert.co[tang[0]] - cmin[0]) * DENS / TEXW
            b = (l.vert.co[tang[1]] - cmin[1]) * DENS / TEXH
            l[UV].uv = (u0 + ou + min(a, 0.24), 0.02 + ov + min(b, 0.10))
        return
    if ax == long_axis:
        k = seed % 4
        cs = [l.vert.co for l in f.loops]
        c = sum(cs, Vector()) / len(cs)
        ext = max(max(abs(v[tang[0]] - c[tang[0]]), abs(v[tang[1]] - c[tang[1]])) for v in cs) or 1
        for l in f.loops:
            a = (l.vert.co[tang[0]] - c[tang[0]]) / ext; b = (l.vert.co[tang[1]] - c[tang[1]]) / ext
            l[UV].uv = ((k + 0.5 + a * 0.45) / 4, STRIP["end"] + (0.5 + b * 0.45) * SH)
        return
    ua = long_axis if long_axis in tang else tang[0]
    va = tang[1] if ua == tang[0] else tang[0]
    off = (seed * 0.37) % 1
    vs = [l.vert.co[va] for l in f.loops]
    vmin, span = min(vs), max(max(vs) - min(vs), 1e-4)
    vscale = min(1.0, (32 / DENS) / span)
    base = STRIP[kind]
    for l in f.loops:
        u = l.vert.co[ua] * DENS / TEXW + off
        v = base + ((l.vert.co[va] - vmin) * vscale * DENS / TEXH) * 0.94 + 0.004
        l[UV].uv = (u, v)

def timber(name, size, pos, kind="hewn", rot=(0, 0, 0), jitter=0.02, bevel=0.02):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2]))
    long_axis = max(range(3), key=lambda i: size[i])
    for v in bm.verts:
        for i in range(3):
            if i != long_axis: v.co[i] += rng.uniform(-jitter, jitter)
    if bevel > 0:
        bmesh.ops.bevel(bm, geom=bm.edges[:], offset=bevel, segments=1, affect="EDGES")
    finish(bm, name, kind, long_axis, pos, rot)

def finish(bm, name, kind, long_axis, pos, rot):
    global UV
    bm.normal_update()
    UV = bm.loops.layers.uv.verify()
    seed = rng.randrange(1000)
    for f in bm.faces: uv_face(f, kind, long_axis, seed + f.index % 2)
    bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Euler([math.radians(a) for a in rot]).to_matrix())
    bmesh.ops.translate(bm, verts=bm.verts, vec=Vector(pos))
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = False
    ob = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(ob)
    ob.data.materials.append(MAT); PARTS.append(ob)
    return ob

# ---------- rack dimensions ----------
FOOT_Y, APEX_Y, APEX_Z, FOOT_Z = 0.65, 0.07, 1.84, 0.05
LEG_X = 0.88
THETA = math.degrees(math.atan2(FOOT_Y - APEX_Y, APEX_Z - FOOT_Z))
def leg_y(z): return FOOT_Y - (FOOT_Y - APEX_Y) * (z - FOOT_Z) / (APEX_Z - FOOT_Z)
RIDGE_Z = 1.90
UP_Z, LO_Z = 1.64, 1.34                      # rail heights
def rail_y(z): return leg_y(z) + 0.062 + 0.045 - 0.008
XS = [-0.7 + 0.2 * i for i in range(8)]      # hook grid
BUNDLE_H = 0.48
BINX = (-0.5, 0.0, 0.5)
BINY = (-0.30, 0.30)
BIN_FLOOR_TOP, BIN_RIM = 0.16, 0.32
KNOT_DROP = 0.19                              # beam bottom -> top of the unit box

HOOKS = []   # (row, i, x, y_cord, zb)

def hook(row, i, x, y_rail, zb, y_cord):
    zp = zb - 0.075
    timber("hook", (0.022, 0.022, 0.09), (x, y_rail, zb - 0.035), kind="iron", jitter=0.001, bevel=0)
    dy = y_cord - y_rail
    timber("hook", (0.022, abs(dy) + 0.022, 0.022), (x, y_rail + dy / 2, zp), kind="iron", jitter=0.001, bevel=0)
    timber("cord", (0.016, 0.016, 0.07), (x, y_cord, zp - 0.015 - 0.035), kind="hemp", jitter=0.0008, bevel=0)
    timber("knot", (0.035, 0.035, 0.035), (x, y_cord, zb - 0.17), kind="hemp", jitter=0.0015, bevel=0.003)
    HOOKS.append((row, i, x, y_cord, zb))

def build_rack():
    PARTS.clear(); HOOKS.clear()
    for sx in (-1, 1):
        X = sx * LEG_X
        for sy in (-1, 1):
            timber("leg", (0.13, 0.12, math.hypot(FOOT_Y - APEX_Y, APEX_Z - FOOT_Z)),
                   (X, sy * (FOOT_Y + APEX_Y) / 2, (APEX_Z + FOOT_Z) / 2), rot=(sy * THETA, 0, 0))
        timber("sill", (0.15, 1.36, 0.09), (X, 0, 0.045), rot=(0, 0, rng.uniform(-1, 1)))
        for z, th in ((0.32, 0.09), (0.80, 0.08)):
            timber("tie", (0.10, 2 * leg_y(z) + 0.06, th), (X, 0, z))
        timber("band", (0.06, 0.17, 0.17), (X, 0, RIDGE_Z), kind="iron", jitter=0.002, bevel=0)
        for sy in (-1, 1):
            for z in (UP_Z, LO_Z):
                timber("clamp", (0.06, 0.105, 0.105), (X, sy * rail_y(z), z), kind="iron", jitter=0.002, bevel=0)
    timber("ridge", (1.98, 0.14, 0.14), (0, 0, RIDGE_Z), rot=(0, rng.uniform(-0.3, 0.3), 0), jitter=0.01)
    for sy in (-1, 1):
        for z in (UP_Z, LO_Z):
            timber("rail", (1.94, 0.09, 0.09), (0, sy * rail_y(z), z), rot=(0, rng.uniform(-0.3, 0.3), 0), jitter=0.01)
    # drip tray
    timber("tray", (1.58, 1.24, 0.04), (0, 0, 0.11), kind="stain", bevel=0.008, jitter=0.006)
    for sy in (-1, 1): timber("trayside", (1.58, 0.045, 0.08), (0, sy * 0.60, 0.15), kind="stain", bevel=0.008, jitter=0.004)
    for sx in (-1, 1): timber("trayend", (0.045, 1.2, 0.08), (sx * 0.77, 0, 0.15), kind="stain", bevel=0.008, jitter=0.004)
    # six salting bins
    for cx in BINX:
        for cy in BINY:
            timber("binfloor", (0.48, 0.50, 0.03), (cx, cy, 0.145), kind="stain", bevel=0.005, jitter=0.003)
            for sy in (-1, 1):
                timber("binwall", (0.48, 0.04, 0.16), (cx, cy + sy * 0.23, 0.24), bevel=0.006, jitter=0.003)
                timber("binstrap", (0.50, 0.012, 0.04), (cx, cy + sy * 0.256, 0.21), kind="iron", jitter=0.001, bevel=0)
            for sx in (-1, 1):
                timber("binwall", (0.04, 0.42, 0.16), (cx + sx * 0.22, cy, 0.24), bevel=0.006, jitter=0.003)
                for sy in (-1, 1):
                    timber("binpost", (0.055, 0.055, 0.18), (cx + sx * 0.215, cy + sy * 0.225, 0.25), bevel=0.006, jitter=0.002)
    # hooks with a hemp cord each
    ridge_x = XS
    for i, x in enumerate(ridge_x):
        s = -1 if i % 2 == 0 else 1
        hook("ridge", i, x, 0.0, RIDGE_Z - 0.07, s * 0.09)
    for sy, nm in ((-1, "uf"), (1, "ub")):
        for i, x in enumerate(XS):
            hook(nm, i, x, sy * rail_y(UP_Z), UP_Z - 0.045, sy * 0.215)
    for sy, nm in ((-1, "lf"), (1, "lb")):
        for i, x in enumerate(XS):
            hook(nm, i, x, sy * rail_y(LO_Z), LO_Z - 0.045, sy * (rail_y(LO_Z) + 0.07))

# ---------- item models and the unit generator ----------
M_B2U = Matrix(((-1, 0, 0), (0, 0, 1), (0, -1, 0)))
def to_unity_vec(v): return [round(-v.x, 4), round(v.z, 4), round(-v.y, 4)]
def to_unity_R(R): return M_B2U @ R @ M_B2U.transposed()
def uq(R):
    q = to_unity_R(R).to_quaternion()
    return [round(q.x, 4), round(q.y, 4), round(q.z, 4), round(q.w, 4)]
def ueuler(R):
    e = to_unity_R(R).to_euler("ZXY")
    return [round(math.degrees(e.x), 2), round(math.degrees(e.y), 2), round(math.degrees(e.z), 2)]

INFO = {}
def info(prefab):
    if prefab not in INFO:
        d = json.load(open(f"{ITEMS_DIR}/{prefab}/info.json", encoding="utf-8"))
        INFO[prefab] = Vector([d["bounds_max"][i] - d["bounds_min"][i] for i in range(3)])
    return INFO[prefab]

def align_R(size, long_dir, thin_dir):
    ax = sorted(range(3), key=lambda i: size[i])
    thin, mid, long = ax
    wl, wt = Vector(long_dir).normalized(), Vector(thin_dir).normalized()
    wm = wt.cross(wl).normalized()
    for flip in (1, -1):
        cols = [None] * 3; cols[long] = wl; cols[mid] = wm * flip; cols[thin] = wt
        R = Matrix(((cols[0].x, cols[1].x, cols[2].x), (cols[0].y, cols[1].y, cols[2].y), (cols[0].z, cols[1].z, cols[2].z)))
        if R.determinant() > 0: return R
def Rx(a): return Matrix.Rotation(math.radians(a), 3, "X")
def Ry(a): return Matrix.Rotation(math.radians(a), 3, "Y")
def Rz(a): return Matrix.Rotation(math.radians(a), 3, "Z")

def aabb_half(R, size, s):
    return Vector(sum(abs(R[i][j]) * size[j] * s / 2 for j in range(3)) for i in range(3))

def fit_copy(prefab, longest, R, c, bhalf, shrink_log):
    """Scale so the longest bounds side == longest, then shrink until the rotated bounds fit the box; clamp the centre."""
    size = info(prefab)
    s = longest / max(size)
    for _ in range(24):
        h = aabb_half(R, size, s)
        if all(h[i] <= bhalf[i] + 1e-6 for i in range(3)): break
        s *= 0.95
        shrink_log.append(prefab)
    h = aabb_half(R, size, s)
    c = Vector([max(-(bhalf[i] - h[i]), min(bhalf[i] - h[i], c[i])) for i in range(3)])
    return s, c

# prefab -> (mode, copies, longest m)
PROFILE = {
    "Fish1": ("fan", 5, 0.42), "Fish2": ("fan", 5, 0.42), "Fish3": ("fan", 5, 0.40), "Fish5": ("fan", 5, 0.38),
    "Fish6": ("fan", 5, 0.38), "FishRaw": ("fan", 6, 0.30), "Fish4_cave": ("fan", 5, 0.34),
    "RawMeat": ("string", 5, 0.20), "WolfMeat": ("string", 5, 0.22), "LoxMeat": ("string", 4, 0.22),
    "DeerMeat": ("string", 5, 0.20), "NeckTail": ("string", 5, 0.20), "ChickenMeat": ("string", 5, 0.20),
    "HareMeat": ("string", 3, 0.32), "AsksvinMeat": ("string", 4, 0.24),
}
PILE_LONGEST = {"HareMeat": 0.20, "SerpentMeat": 0.17, "ChickenMeat": 0.17, "DeerMeat": 0.17, "LoxMeat": 0.17,
                "FishRaw": 0.16, "AsksvinMeat": 0.17, "WolfMeat": 0.17}

ROW_ITEMS = {
    "ridge": ["WolfMeat", "RawMeat", "LoxMeat", "DeerMeat", "NeckTail", "RawMeat", "WolfMeat", "DeerMeat"],
    "uf": ["Fish1", "Fish2", "Fish6", "Fish3", "Fish5", "Fish2", "Fish1", "Fish3"],
    "ub": ["Fish5", "Fish3", "Fish2", "Fish1", "Fish6", "Fish3", "Fish5", "Fish2"],
    "lf": ["DeerMeat", "NeckTail", "HareMeat", "FishRaw", "AsksvinMeat", "RawMeat", "HareMeat", "NeckTail"],
    "lb": ["RawMeat", "HareMeat", "WolfMeat", "FishRaw", "NeckTail", "HareMeat", "DeerMeat", "AsksvinMeat"],
}
BIN_ITEMS = [   # per bin (cx order, front then back), per pile (grid order)
    ["RawMeat", "DeerMeat", "NeckTail", "RawMeat", "WolfMeat", "DeerMeat"],
    ["ChickenMeat", "HareMeat", "ChickenMeat", "FishRaw", "HareMeat", "FishRaw"],
    ["WolfMeat", "RawMeat", "AsksvinMeat", "NeckTail", "RawMeat", "LoxMeat"],
    ["DeerMeat", "NeckTail", "RawMeat", "DeerMeat", "WolfMeat", "RawMeat"],
    ["SerpentMeat", "FishRaw", "HareMeat", "AsksvinMeat", "ChickenMeat", "NeckTail"],
    ["LoxMeat", "RawMeat", "WolfMeat", "DeerMeat", "NeckTail", "RawMeat"],
]
PILE_GRID = [(0, 1), (1, 1), (0, 0), (1, 2), (1, 0), (0, 2)]     # (col, row) in the fill order

def gen_bundle(prefab, bw, bd, H, r, shrink_log):
    mode, n, longest = PROFILE[prefab]
    n = max(4, min(6, n)) if mode == "fan" else n
    bhalf = Vector((bw / 2, bd / 2, H / 2))
    copies = []
    size = info(prefab)
    for j in range(n):
        down = r.choice((-1, 1)) if mode == "fan" else -1
        thin = Vector((0, r.choice((-1, 1)), 0))
        Ral = align_R(size, (0, 0, down), thin)
        if mode == "fan":
            k = j - (n - 1) / 2
            post = Ry(k * 5.0 + r.uniform(-2, 2)) @ Rz(r.uniform(-20, 20))
            R = post @ Ral
            lg = longest * r.uniform(0.9, 1.05)
            s, c = fit_copy(prefab, lg, R, Vector((k * 0.03, r.uniform(-0.01, 0.01), 0)), bhalf, shrink_log)
            h = aabb_half(R, size, s)
            c.z = H / 2 - h.z - (j % 2) * 0.035
            c.z = max(-(H / 2 - h.z), c.z)
        else:
            post = Rz(r.uniform(-35, 35)) @ Ry(r.uniform(-6, 6))
            R = post @ Ral
            lg = longest * r.uniform(0.92, 1.05)
            s, c = fit_copy(prefab, lg, R, Vector(((-1) ** j * 0.025, r.uniform(-0.01, 0.01), 0)), bhalf, shrink_log)
            h = aabb_half(R, size, s)
            top = H / 2 - h.z; bot = -H / 2 + h.z
            c.z = top if n == 1 else top + (bot - top) * j / (n - 1)
        copies.append({"prefab": prefab, "c": c, "R": R, "s": s, "post": post,
                       "long_dir": (0, 0, down), "thin_dir": tuple(thin)})
    return copies

def gen_pile(prefab, bw, bd, bh, r, shrink_log):
    size = info(prefab)
    lg0 = PILE_LONGEST.get(prefab, 0.17)
    bhalf = Vector((bw / 2, bd / 2, bh / 2))
    layers = [2, 2, 2, 2, 1]
    ysets = [(-0.032, 0.032), (-0.02, 0.026), (-0.03, 0.03), (-0.018, 0.022), (0.0,)]
    copies = []
    for layer, cnt in enumerate(layers):
        for q in range(cnt):
            sgn = r.choice((-1, 1))
            Ral = align_R(size, (sgn, 0, 0), (0, 0, 1))
            post = Rz(r.uniform(-25, 25)) @ Rx(r.uniform(-10, 10)) @ Ry(r.uniform(-10, 10))
            R = post @ Ral
            lg = lg0 * r.uniform(0.92, 1.08)
            cx = r.uniform(-0.012, 0.012)
            cy = ysets[layer][q] + r.uniform(-0.006, 0.006)
            s, c = fit_copy(prefab, lg, R, Vector((cx, cy, 0)), bhalf, shrink_log)
            h = aabb_half(R, size, s)
            c.z = -bh / 2 + h.z + layer * 0.052 + 0.002
            c.z = min(c.z, bh / 2 - h.z)
            copies.append({"prefab": prefab, "c": c, "R": R, "s": s, "post": post, "long_dir": (sgn, 0, 0), "thin_dir": (0, 0, 1)})
    return copies

UNITS = []
def build_units():
    UNITS.clear()
    shrink = []
    r = random.Random(11)
    box_w = {"ridge": (0.20, 0.13), "uf": (0.19, 0.11), "ub": (0.19, 0.11), "lf": (0.19, 0.11), "lb": (0.19, 0.11)}
    groups = {}
    for (row, i, x, ycord, zb) in HOOKS:
        bw, bd = box_w[row]
        prefab = ROW_ITEMS[row][i]
        top = zb - KNOT_DROP
        u = {"kind": "bundle", "group": row, "slot": i, "prefab": prefab, "box": (bw, bd, BUNDLE_H),
             "pos": Vector((x, ycord, top - BUNDLE_H / 2))}
        u["copies"] = gen_bundle(prefab, bw, bd, BUNDLE_H, r, shrink)
        groups.setdefault(row, []).append(u)
    bw, bd, bh = 0.18, 0.12, 0.30
    bins = [(cx, cy) for cy in BINY for cx in BINX]
    for b, (cx, cy) in enumerate(bins):
        for p, (col, row) in enumerate(PILE_GRID):
            prefab = BIN_ITEMS[b][p]
            pos = Vector((cx + (-0.0925 if col == 0 else 0.0925), cy + (row - 1) * 0.13, BIN_FLOOR_TOP + 0.002 + bh / 2))
            u = {"kind": "pile", "group": "bin", "slot": b * 6 + p, "bin": b, "pile": p, "prefab": prefab,
                 "box": (bw, bd, bh), "pos": pos}
            u["copies"] = gen_pile(prefab, bw, bd, bh, r, shrink)
            groups.setdefault("bin", []).append(u)
    # fill order: hung rows centre-out, bins pile-major, everything merged by relative position in its group
    def centre_out(us): return sorted(us, key=lambda u: (abs(u["pos"].x), u["pos"].y))
    keyed = []
    for g, us in groups.items():
        if g == "bin":
            bin_seq = [(0.0, -1), (0.0, 1), (-0.5, -1), (0.5, 1), (0.5, -1), (-0.5, 1)]
            order = sorted(us, key=lambda u: (u["pile"], bin_seq.index((bins[u["bin"]][0], 1 if bins[u["bin"]][1] > 0 else -1))))
        else:
            order = centre_out(us)
        n = len(order)
        for k, u in enumerate(order):
            keyed.append(((k + 0.5) / n + r.uniform(-0.004, 0.004), u))
    keyed.sort(key=lambda t: t[0])
    for idx, (_, u) in enumerate(keyed):
        u["index"] = idx
        UNITS.append(u)
    return shrink

# ---------- scene helpers ----------
def tris(obs): return sum(len(p.vertices) - 2 for o in obs for p in o.data.polygons)
def join(obs, name):
    bpy.ops.object.select_all(action="DESELECT")
    for o in obs: o.select_set(True)
    bpy.context.view_layer.objects.active = obs[0]
    bpy.ops.object.join(); ob = bpy.context.active_object; ob.name = name
    return ob
def polys(obs):
    V, P = [], []
    for o in obs:
        b = len(V); V += [o.matrix_world @ v.co for v in o.data.vertices]
        P += [[b + i for i in p.vertices] for p in o.data.polygons]
    return V, P

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
atlas = build_atlas()
MAT = bpy.data.materials.new("meatrack"); MAT.use_nodes = True
nt = MAT.node_tree; bsdf = nt.nodes["Principled BSDF"]
ti = nt.nodes.new("ShaderNodeTexImage"); ti.image = atlas; ti.interpolation = "Closest"
nt.links.new(ti.outputs["Color"], bsdf.inputs["Base Color"])
bsdf.inputs["Roughness"].default_value = 0.8

rng.seed(7)
build_rack()
shrink_log = build_units()
print("UNITS", len(UNITS), "shrink steps", len(shrink_log), {p: shrink_log.count(p) for p in sorted(set(shrink_log))})
for pf in sorted({c["prefab"] for u in UNITS for c in u["copies"]}):
    ls = [c["s"] * max(info(pf)) for u in UNITS for c in u["copies"] if c["prefab"] == pf]
    print("  longest", pf, "min %.3f max %.3f" % (min(ls), max(ls)), "size", [round(v, 2) for v in info(pf)])

# templates for every prefab used
tcoll = bpy.data.collections.new("templates"); sc.collection.children.link(tcoll)
TPL = {}
for pf in sorted({c["prefab"] for u in UNITS for c in u["copies"]}):
    objs = load_item(pf, anchor="center", collection=tcoll)
    TPL[pf] = [o for o in objs if o.type == "MESH"]
    for o in TPL[pf]: o.hide_render = True; o.hide_viewport = True
print("PREFABS", sorted(TPL))

def place(u, c, xoff):
    out = []
    p = u["pos"] + c["c"]
    for t in TPL[c["prefab"]]:
        ob = t.copy(); sc.collection.objects.link(ob)
        ob.hide_render = False; ob.hide_viewport = False
        ob.rotation_euler = c["R"].to_euler("XYZ"); ob.scale = (c["s"],) * 3
        ob.location = (p.x + xoff, p.y, p.z)
        out.append(ob)
    return out

# ---------- clip check (frame vs unit boxes and real item meshes) ----------
fv, fp = polys(PARTS)
ftree = BVHTree.FromPolygons(fv, fp)
def box_tree(u):
    hx, hy, hz = [d / 2 - 0.0005 for d in u["box"]]
    c = u["pos"]
    V = [Vector((c.x + sx * hx, c.y + sy * hy, c.z + sz * hz)) for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]
    P = [[0, 1, 3, 2], [4, 6, 7, 5], [0, 4, 5, 1], [2, 3, 7, 6], [0, 2, 6, 4], [1, 5, 7, 3]]
    return BVHTree.FromPolygons(V, P)
parttrees = [BVHTree.FromPolygons(*polys([o])) for o in PARTS]
clip_units, outside = [], 0
box_overlap = 0
boxtrees = [box_tree(u) for u in UNITS]
for u, bt in zip(UNITS, boxtrees):
    bad = bool(ftree.overlap(bt))
    if bad:
        hit = [o.name for o, pt in zip(PARTS, parttrees) if pt.overlap(bt)]
        print("  box clips", u["index"], u["group"], u["slot"], hit[:3])
    obs = []
    for c in u["copies"]: obs += place(u, c, 0.0)
    bpy.context.view_layer.update()
    for o in obs:
        V = [o.matrix_world @ v.co for v in o.data.vertices]
        P = [list(p.vertices) for p in o.data.polygons]
        if ftree.overlap(BVHTree.FromPolygons(V, P)):
            bad = True
            print("  item clips", u["index"], u["group"], u["slot"], o.name, [pn.name for pn, pt in zip(PARTS, parttrees) if pt.overlap(BVHTree.FromPolygons(V, P))][:3])
        hx, hy, hz = [d / 2 + 0.002 for d in u["box"]]
        if any(abs(v.x - u["pos"].x) > hx or abs(v.y - u["pos"].y) > hy or abs(v.z - u["pos"].z) > hz for v in V): outside += 1
    for o in obs: bpy.data.objects.remove(o, do_unlink=True)
    if bad: clip_units.append(u["index"])
for i in range(len(UNITS)):
    for j in range(i + 1, len(UNITS)):
        if boxtrees[i].overlap(boxtrees[j]): box_overlap += 1
print("CLIPPING", len(clip_units), "of", len(UNITS), clip_units, "| item meshes outside own box:", outside,
      "| unit-box/unit-box overlaps:", box_overlap)

# ---------- export: frame obj, anchors json, stats ----------
ALLV = fv
bb = [(min(v[i] for v in ALLV), max(v[i] for v in ALLV)) for i in range(3)]
print("FRAME BBOX m: x %.2f y %.2f z %.2f" % tuple(b[1] - b[0] for b in bb), "z max %.3f" % bb[2][1])
bpy.ops.object.select_all(action="DESELECT")
for o in PARTS: o.select_set(True)
bpy.ops.wm.obj_export(filepath=os.path.join(OUTA, "MeatRack.obj"), export_selected_objects=True, export_materials=False,
                      export_triangulated_mesh=True, forward_axis="NEGATIVE_Z", up_axis="Y")

def unit_json(u):
    R0 = Matrix.Identity(3)
    return {
        "index": u["index"], "kind": u["kind"], "group": u["group"], "slot_in_group": u["slot"],
        "position": to_unity_vec(u["pos"]), "rotation_euler": [0.0, 0.0, 0.0],
        "box_size": [round(u["box"][0], 3), round(u["box"][2], 3), round(u["box"][1], 3)],
        "render_item": u["prefab"],
        "copies": [{
            "offset": to_unity_vec(c["c"]),
            "longest_m": round(c["s"] * max(info(c["prefab"])), 4),
            "align": {"long_axis_to": [float(x) for x in to_unity_vec(Vector(c["long_dir"]))],
                      "thin_axis_to": [float(x) for x in to_unity_vec(Vector(c["thin_dir"]))],
                      "then_rotate_euler_zxy": ueuler(c["post"]), "then_rotate_quat_xyzw": uq(c["post"])},
            "rendered_rotation_euler_zxy": ueuler(c["R"]), "rendered_rotation_quat_xyzw": uq(c["R"]),
        } for c in u["copies"]],
    }
anchors = {
    "slug": "meatrack", "round": 2, "slots_designed": len(UNITS), "units_at_100": len(UNITS),
    "coordinates": "Unity prefab space, same origin as MeatRack.obj. From Blender (z-up, -y front): ux=-bx, uy=bz, uz=-by. "
                   "box_size is (x, y, z) in Unity axes. Rotation matrices convert as R_u = M R_b M^T with M the same map; "
                   "euler values are Unity order (Z, then X, then Y).",
    "placing_an_item": "For every copy: scale the stored item's model uniformly so the longest side of its renderer bounds equals "
                       "longest_m; rotate it with align (turn its longest bounds axis to long_axis_to and its thinnest bounds axis "
                       "to thin_axis_to, middle axis follows right-handed), then apply then_rotate (about the unit centre axes); "
                       "put the centre of its bounds at unit.position + copy.offset. rendered_rotation_* is the finished rotation for "
                       "the item used in the render (render_item) and can be used directly for items with a similar shape.",
    "fill_order": "units are sorted in fill order: show the first k units for k stacks in use (one stack per unit, stack holding the "
                  "same item for all copies of a unit).",
    "units": [unit_json(u) for u in UNITS],
}
json.dump(anchors, open(os.path.join(OUTA, "MeatRackAnchors.json"), "w"), indent=1)
stats = {"frame_tris": tris(PARTS), "units": len(UNITS), "hung_units": sum(1 for u in UNITS if u["kind"] == "bundle"),
         "pile_units": sum(1 for u in UNITS if u["kind"] == "pile"), "frame_bbox_m": [round(b[1] - b[0], 2) for b in bb],
         "height_max_m": round(bb[2][1], 3), "atlas": "meatrack_atlas.png 128x128, Closest",
         "item_copies_at_100": sum(len(u["copies"]) for u in UNITS)}
json.dump(stats, open(os.path.join(OUTA, "meatrack.json"), "w"), indent=1)
print("MEATRACK", stats)

# ---------- render scene: three racks (10 / 50 / 100 %), post, chest ----------
frame = join(PARTS, "rack")
SPACING = 2.7
racks = [(frame.copy(), -SPACING, 0.1), (frame, 0.0, 0.5), (frame.copy(), SPACING, 1.0)]
for ob, xo, fill in racks:
    if ob.name != frame.name: sc.collection.objects.link(ob)
    ob.location.x = xo
    k = max(1, round(fill * len(UNITS)))
    for u in UNITS[:k]:
        for c in u["copies"]: place(u, c, xo)
    print("fill", fill, "units", k)

# plain 1.8 m post as player-height marker
pm = bpy.data.materials.new("post"); pm.use_nodes = True
pm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.42, 0.40, 0.37, 1)
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(-4.4, 0, 0.9))
post = bpy.context.active_object; post.scale = (0.12, 0.12, 1.8); post.data.materials.append(pm)

if "--no-ref" not in argv:
    rep = json.load(open("C:/Users/joost/ValheimRip/chests/report.json"))["piece_chest_wood"]["nodes"]
    vimg = bpy.data.images.load(f"{RIP}/woodchest_d.png")
    vm = bpy.data.materials.new("ref"); vm.use_nodes = True
    vt = vm.node_tree.nodes.new("ShaderNodeTexImage"); vt.image = vimg; vt.interpolation = "Closest"
    vm.node_tree.links.new(vt.outputs["Color"], vm.node_tree.nodes["Principled BSDF"].inputs["Base Color"])
    for node in rep:
        if not node["path"].endswith(("/woodchest", "/woodchesttop_closed")): continue
        V, T, F = [], [], []
        for l in open(node["mesh"]["obj"]):
            p = l.split()
            if not p: continue
            if p[0] == "v": V.append(Vector((-float(p[1]), float(p[2]), float(p[3]))))
            elif p[0] == "vt": T.append((float(p[1]), float(p[2])))
            elif p[0] == "f": F.append([tuple(int(x) - 1 for x in q.split("/")[:2]) for q in reversed(p[1:])])
        q = node["rot"]
        M = Matrix.Translation(Vector(node["pos"])) @ Quaternion((q[3], q[0], q[1], q[2])).to_matrix().to_4x4() \
            @ Matrix.Diagonal((*node["scale"], 1))
        verts = [M @ v for v in V]
        verts = [Vector((-v.x - 5.5, -v.z, v.y)) for v in verts]
        F = [list(reversed(f)) for f in F]
        me = bpy.data.meshes.new("ref"); me.from_pydata(verts, [], [[c[0] for c in f] for f in F])
        uvl = me.uv_layers.new(); i = 0
        for f in F:
            for c in f: uvl.data[i].uv = T[c[1]]; i += 1
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
sc.render.resolution_x, sc.render.resolution_y = 1600, 900
sc.view_settings.view_transform = "Standard"
VIEWS = {"fills": (0, 9, 14.6, (-1.25, 0, 1.1)), "close": (-22, 19, 5.4, (SPACING, 0, 0.95)),
         "alt": (48, 21, 5.6, (SPACING, 0, 0.95))}
for vn, (yaw, pitch, dist, tgt) in VIEWS.items():
    t = Vector(tgt)
    d = Vector((math.cos(math.radians(pitch)) * math.sin(math.radians(yaw)),
                -math.cos(math.radians(pitch)) * math.cos(math.radians(yaw)), math.sin(math.radians(pitch))))
    cam.location = t + d * dist; cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    sc.render.resolution_y = 700 if vn == "fills" else 900
    sc.render.filepath = os.path.join(OUT, f"{TAG}-{vn}.png")
    bpy.ops.render.render(write_still=True)
print("DONE")
