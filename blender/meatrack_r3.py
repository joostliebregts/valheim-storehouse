"""Meat Rack, ROUND 3: mass storage, contents PHYSICALLY SETTLED (rigid body simulation). Our own frame mesh and atlas (no vanilla geometry or texture in the exported files);
the contents are the game's own item models, placed at exported ANCHORS (JSON) by the mod.
Run: blender -b -P meatrack_r3.py -- [--out DIR] [--tag NAME] [--no-ref]
Writes into assets/meatrack_r3/:  MeatRack.obj (frame only, forward -Z, up Y, triangulated, no materials),
  meatrack_atlas.png (128x128, point-filtered), MeatRackAnchors.json (units in fill order), meatrack.json (stats).

Atlas 128x128, four 32 px strips (v from the top): 0.75-1.0 hewn timber | 0.5-0.75 end grain (4 tiles) |
  0.25-0.5 salted/stained wood (tray, bins) | 0.0-0.25 left half iron, right half hemp cord.

Layout (2.0 m wide, 1.97 m high, A-frame kept): ridge row (8 meat strings) + upper rail each side (8 fish bundles each)
+ lower rail each side (8 bundles each) = 40 hung stacks; a drip tray on the floor holds 6 open salting bins with
6 piles each = 36 piled stacks. 76 stacks in total (a black metal chest holds 32).

Coordinates: scene is Blender z-up, front = -y, floor z=0, rack centred on x=y=0. The anchors JSON is in Unity prefab
space with the SAME origin: ux = -bx, uy = bz, uz = -by (vectors the same; rotation matrices R_u = M R_b M^T, M the same map).
"""
import bpy, bmesh, sys, os, math, json, random, time
import numpy as np
from mathutils import Vector, Matrix, Euler, Quaternion
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
OUTA = os.path.normpath(os.path.join(HERE, "..", "assets", "meatrack_r3"))
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = argv[argv.index("--out") + 1] if "--out" in argv else \
    "C:/Users/joost/AppData/Local/Temp/claude/C--Users-joost--pai/5e4bc60b-cdfe-4638-8e29-2e507fa13cf9/scratchpad/proto3/meatrack"
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

# ROUND 3 grouping (calms the colour clash): one item type per hook row and per bin
ROW_ITEMS = {
    "ridge": ["RawMeat"] * 8, "uf": ["Fish2"] * 8, "ub": ["Fish3"] * 8,
    "lf": ["DeerMeat"] * 8, "lb": ["WolfMeat"] * 8,
}
BIN_ITEMS = [["RawMeat"] * 6, ["DeerMeat"] * 6, ["WolfMeat"] * 6, ["ChickenMeat"] * 6, ["FishRaw"] * 6, ["NeckTail"] * 6]
PILE_GRID = [(0, 1), (1, 1), (0, 0), (1, 2), (1, 0), (0, 2)]     # (col, row) in the fill order

VLOC = {}     # prefab -> Nx3 numpy of template vertices (object space, centre-anchored)
def vloc(prefab):
    if prefab not in VLOC:
        VLOC[prefab] = np.array([[*(t.matrix_world @ v.co)] for t in TPL[prefab] for v in t.data.vertices], dtype=np.float64)
    return VLOC[prefab]

def world_rel(prefab, R, s):
    """vertices of a copy relative to its centre (numpy Nx3)"""
    return s * (vloc(prefab) @ np.array(R).T)

CORD_T = 0.016
def gen_bundle(prefab, bw, bd, H, r, shrink_log):
    """Hung bundle. ROUND 3: every item is pinned onto the cord (fan: tails gathered at the cord axis, string: the cord
    runs through the pieces) and the unit gets an explicit cord + lashing, so nothing floats apart."""
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
            s = lg / max(size)
            for _ in range(20):
                V = world_rel(prefab, R, s)
                zt = V[:, 2].max()
                sel = V[:, 2] > zt - 0.045
                txy = V[sel, :2].mean(0)
                cx_, cy_ = -txy[0] + r.uniform(-0.004, 0.004), -txy[1] + r.uniform(-0.004, 0.004)
                cz_ = H / 2 - zt - (j % 2) * 0.035
                lo = V + np.array([cx_, cy_, cz_])
                if all(np.abs(lo[:, i]).max() <= bhalf[i] + 0.002 for i in range(3)): break
                s *= 0.95; shrink_log.append(prefab)
            c = Vector((cx_, cy_, cz_))
        else:
            post = Rz(r.uniform(-35, 35)) @ Ry(r.uniform(-6, 6))
            R = post @ Ral
            lg = longest * r.uniform(0.92, 1.05)
            s, c = fit_copy(prefab, lg, R, Vector((r.uniform(-0.004, 0.004), r.uniform(-0.004, 0.004), 0)), bhalf, shrink_log)
            h = aabb_half(R, size, s)
            top = H / 2 - h.z; bot = -H / 2 + h.z
            c.z = top if n == 1 else top + (bot - top) * j / (n - 1)
        copies.append({"prefab": prefab, "c": c, "R": R, "s": s, "post": post,
                       "long_dir": (0, 0, down), "thin_dir": tuple(thin)})
    # cord + lashing, positions relative to the unit centre (cord axis = unit centre xy)
    lows = [(world_rel(c_["prefab"], c_["R"], c_["s"])[:, 2] + c_["c"].z).min() for c_ in copies]
    tops = H / 2
    if mode == "fan":
        bot = tops - 0.12
        knots = [(tops - 0.07, 0.042, 0.03)]                       # lashing round the gathered tails
    else:
        bot = min(lows) + 0.03
        knots = [(bot, 0.032, 0.032)]                               # end knot inside the last piece
    cord = {"top": tops + 0.012, "bottom": bot, "knots": knots}
    return copies, cord

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
        u["copies"], u["cord"] = gen_bundle(prefab, bw, bd, BUNDLE_H, r, shrink)
        groups.setdefault(row, []).append(u)
    bw, bd, bh = 0.18, 0.12, 0.30
    bins = [(cx, cy) for cy in BINY for cx in BINX]
    for b, (cx, cy) in enumerate(bins):
        for p, (col, row) in enumerate(PILE_GRID):
            prefab = BIN_ITEMS[b][p]
            pos = Vector((cx + (-0.0925 if col == 0 else 0.0925), cy + (row - 1) * 0.13, BIN_FLOOR_TOP + 0.002 + bh / 2))
            u = {"kind": "pile", "group": "bin", "slot": b * 6 + p, "bin": b, "pile": p, "prefab": prefab,
                 "box": (bw, bd, bh), "pos": pos}
            u["copies"] = []      # ROUND 3: filled by the rigid body settling
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

# templates for every prefab used
tcoll = bpy.data.collections.new("templates"); sc.collection.children.link(tcoll)
TPL = {}
for pf in sorted({p for v in ROW_ITEMS.values() for p in v} | {p for v in BIN_ITEMS for p in v}):
    objs = load_item(pf, anchor="center", collection=tcoll)
    TPL[pf] = [o for o in objs if o.type == "MESH"]
    for o in TPL[pf]: o.hide_render = True; o.hide_viewport = True
print("PREFABS", sorted(TPL))

shrink_log = build_units()
print("UNITS", len(UNITS), "shrink steps", len(shrink_log), {p: shrink_log.count(p) for p in sorted(set(shrink_log))})

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

# ---------- ROUND 3: rigid body settling of the bin contents ----------
# Frame parts of tray and bins are passive colliders (their real, convex meshes). Items are dropped one by one in FILL
# ORDER (unit by unit, copy by copy) from just above the heap surface with random tilt/yaw/jitter, simulated until at
# rest, then frozen as passive (triangle-mesh shape) so the next item lands on the earlier ones and nothing ever moves
# when more is added. Active shape: convex hull, margin 2 mm, friction 0.8, restitution 0, high damping.
SIM_FPS = 60
MARGIN = 0.002
PILE_N = int(argv[argv.index("--pile-n") + 1]) if "--pile-n" in argv else 8      # items per pile unit (stack)
PILE_SCALE = float(argv[argv.index("--pile-scale") + 1]) if "--pile-scale" in argv else 0.85   # real items would heap far above the rim at 1.0
ONLY_BIN = int(argv[argv.index("--only-bin") + 1]) if "--only-bin" in argv else None
VERBOSE = "--verbose" in argv
SIM_STATS = {"items": 0, "frames": 0, "max_frames": 0, "escaped": 0, "not_settled": 0, "retried": 0}

def rb_add(ob, typ, shape, mass=1.0):
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True); bpy.context.view_layer.objects.active = ob
    bpy.ops.rigidbody.object_add(type=typ)
    rb = ob.rigid_body
    rb.collision_shape = shape; rb.mass = mass
    rb.friction = 0.8; rb.restitution = 0.0
    rb.use_margin = True; rb.collision_margin = MARGIN
    rb.linear_damping = 0.8; rb.angular_damping = 0.95

class Heap:
    CELL = 0.012
    def __init__(self, base): self.h = {}; self.base = base
    def top(self, x0, x1, y0, y1):
        c = self.CELL; m = self.base
        for ix in range(int(math.floor(x0 / c)), int(math.floor(x1 / c)) + 1):
            for iy in range(int(math.floor(y0 / c)), int(math.floor(y1 / c)) + 1):
                m = max(m, self.h.get((ix, iy), 0.0))
        return m
    def add(self, pts):
        c = self.CELL
        for p in pts:
            k = (int(math.floor(p[0] / c)), int(math.floor(p[1] / c)))
            if p[2] > self.h.get(k, 0.0): self.h[k] = p[2]

def world_pts(ob):
    M = ob.matrix_world
    pts = [M @ v.co for v in ob.data.vertices] + [M @ p.center for p in ob.data.polygons]
    return pts

def bin_of(u): return BINS[u["bin"]]

def run_sim():
    global BINS
    BINS = [(cx, cy) for cy in BINY for cx in BINX]
    bpy.ops.rigidbody.world_add()
    rbw = sc.rigidbody_world
    rbw.substeps_per_frame = 14; rbw.solver_iterations = 40
    rbw.point_cache.frame_start = 1; rbw.point_cache.frame_end = 3000
    sc.render.fps = SIM_FPS; sc.gravity = (0, 0, -9.81)
    colliders = [o for o in PARTS if o.name.startswith(("bin", "tray")) and "strap" not in o.name]
    for o in colliders: rb_add(o, "PASSIVE", "CONVEX_HULL")
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, -0.5)); g = bpy.context.active_object
    g.scale = (30, 30, 1); g.name = "simground"; g.hide_render = True
    rb_add(g, "PASSIVE", "BOX")
    heaps = [Heap(BIN_FLOOR_TOP) for _ in BINS]
    sims = []      # every dropped item, for metrics
    r = random.Random(23)
    t0 = time.time()
    for u in UNITS:
        if u["kind"] != "pile" or (ONLY_BIN is not None and u["bin"] != ONLY_BIN): continue
        cx, cy = bin_of(u)
        pf = u["prefab"]; size = info(pf); heap = heaps[u["bin"]]
        for q in range(PILE_N):
            for attempt in range(10):
                sgn = r.choice((-1, 1))
                Ral = align_R(size, (sgn, 0, 0), (0, 0, 1))
                post = Rz(r.uniform(-45, 45)) @ Rx(r.uniform(-14, 14)) @ Ry(r.uniform(-14, 14))
                R = post @ Ral
                s = PILE_LONGEST.get(pf, 0.17) * PILE_SCALE * r.uniform(0.92, 1.08) / max(size)
                h = aabb_half(R, size, s)
                lx, ly = max(0.0, 0.195 - h.x), max(0.0, 0.205 - h.y)
                best = None
                for _ in range(10):            # candidate spots in/near the unit's cell; take the lowest (valleys first)
                    x = u["pos"].x + r.uniform(-0.09, 0.09); y = u["pos"].y + r.uniform(-0.07, 0.07)
                    x = cx + max(-lx, min(lx, x - cx)); y = cy + max(-ly, min(ly, y - cy))
                    t = heap.top(x - h.x, x + h.x, y - h.y, y + h.y)
                    if best is None or t < best[0]: best = (t, x, y)
                z = best[0] + h.z + 0.03
                x, y = best[1], best[2]
                ob = bpy.data.objects.new("sim_" + pf, TPL[pf][0].data)
                sc.collection.objects.link(ob)
                ob.rotation_euler = R.to_euler("XYZ"); ob.scale = (s,) * 3; ob.location = (x, y, z)
                vol = size.x * size.y * size.z * s ** 3
                rb_add(ob, "ACTIVE", "CONVEX_HULL", mass=max(0.05, 600.0 * vol * 0.5))
                sc.frame_set(1)
                prev = None; calm = 0; fr = 0; done = False
                for f in range(2, 300):
                    sc.frame_set(f); fr = f
                    M = ob.matrix_world.copy()
                    if prev is not None:
                        dq = M.to_quaternion().rotation_difference(prev.to_quaternion()).angle
                        dt = (M.translation - prev.translation).length
                        calm = calm + 1 if (dt < 3.0e-4 and dq < 2.5e-3) else 0
                        if calm >= 5: done = True; break
                    prev = M
                M = ob.matrix_world.copy()
                loc = M.translation.copy(); Rm = M.to_3x3().normalized()
                SIM_STATS["frames"] += fr; SIM_STATS["max_frames"] = max(SIM_STATS["max_frames"], fr)
                out = abs(loc.x - cx) > 0.20 or abs(loc.y - cy) > 0.21 or loc.z < BIN_FLOOR_TOP - 0.01
                if out and attempt < 9:
                    SIM_STATS["retried"] += 1
                    bpy.ops.object.select_all(action="DESELECT"); ob.select_set(True); bpy.context.view_layer.objects.active = ob
                    bpy.ops.rigidbody.object_remove(); bpy.data.objects.remove(ob, do_unlink=True)
                    continue
                break
            SIM_STATS["items"] += 1
            if VERBOSE: print("    item", pf, "frames", fr, "done", done, "z %.3f" % loc.z, "retry", attempt)
            if not done: SIM_STATS["not_settled"] += 1
            if out: SIM_STATS["escaped"] += 1; print("  ESCAPED", u["index"], pf, [round(v, 3) for v in loc])
            ob.location = loc; ob.rotation_euler = Rm.to_euler("XYZ")
            ob.rigid_body.type = "PASSIVE"; ob.rigid_body.collision_shape = "MESH"
            heap.add(world_pts(ob))
            u["copies"].append({"prefab": pf, "c": loc - u["pos"], "R": Rm, "s": s, "post": Matrix.Identity(3),
                                "long_dir": None, "thin_dir": None, "sim_ob": ob, "settle_frames": fr})
        print("  unit", u["index"], "bin", u["bin"], "pile", u["pile"], "%.0fs" % (time.time() - t0), flush=True)
    return sims

# ---------- frame trees ----------
fv, fp = polys(PARTS)
ftree = BVHTree.FromPolygons(fv, fp)
parttrees = [BVHTree.FromPolygons(*polys([o])) for o in PARTS]

# ---------- settle the bins (rigid bodies), then measure ----------
t_sim = time.time()
run_sim()
bpy.context.view_layer.update()
print("SIM done in %.0fs" % (time.time() - t_sim), SIM_STATS,
      "avg settle frames %.1f (%.2fs at %d fps)" % (SIM_STATS["frames"] / max(1, SIM_STATS["items"]),
                                                    SIM_STATS["frames"] / max(1, SIM_STATS["items"]) / SIM_FPS, SIM_FPS))

def mesh_tree(ob):
    V = [ob.matrix_world @ v.co for v in ob.data.vertices]
    P = [list(p.vertices) for p in ob.data.polygons]
    return V, P, BVHTree.FromPolygons(V, P)

def side_depth(X, Y):
    """how far polygon X reaches through the plane of polygon Y (the smaller of its two sides)"""
    n = (Y[1] - Y[0]).cross(Y[2] - Y[0])
    if n.length < 1e-12: return 0.0
    n.normalize()
    ds = [(x - Y[0]).dot(n) for x in X]
    return min(max(0.0, max(-d for d in ds)), max(0.0, max(ds)))

def overlap_depth(A, B):
    """largest estimated penetration over all intersecting polygon pairs of two meshes (V, P, tree)"""
    d = 0.0
    for ia, ib in A[2].overlap(B[2]):
        pa = [A[0][i] for i in A[1][ia]]; pb = [B[0][i] for i in B[1][ib]]
        d = max(d, side_depth(pa, pb), side_depth(pb, pa))
    return d

sim_items = [(u, c) for u in UNITS if u["kind"] == "pile" for c in u["copies"]]
PRINT_HEIGHTS = [round(max(c["c"].z + u2["pos"].z for u2, c in sim_items if u2["bin"] == b), 3) for b in range(6) if any(u2["bin"] == b for u2, c in sim_items)]
print("TOP OF HEAP per bin (max item centre z):", PRINT_HEIGHTS)
trees = {id(c): mesh_tree(c["sim_ob"]) for u, c in sim_items}
bb_of = {id(c): ([min(v[i] for v in trees[id(c)][0]) for i in range(3)], [max(v[i] for v in trees[id(c)][0]) for i in range(3)]) for u, c in sim_items}
FR = (fv, fp, ftree)
max_pen_items, max_pen_frame, pairs_checked, tri_overlap_pairs = 0.0, 0.0, 0, 0
by_bin = {}
for u, c in sim_items: by_bin.setdefault(u["bin"], []).append(c)
for b, cs in by_bin.items():
    for i, a in enumerate(cs):
        max_pen_frame = max(max_pen_frame, overlap_depth(trees[id(a)], FR))
        for bcp in cs[i + 1:]:
            A, B = bb_of[id(a)], bb_of[id(bcp)]
            if any(A[0][k] > B[1][k] or B[0][k] > A[1][k] for k in range(3)): continue
            pairs_checked += 1
            dd = overlap_depth(trees[id(a)], trees[id(bcp)])
            if dd > 0: tri_overlap_pairs += 1
            max_pen_items = max(max_pen_items, dd)
# resting check: how far is each item from the nearest thing under/next to it (items of its bin, tray frame)?
def min_gap(a, others):
    g = 9.0
    A = trees[id(a)]
    for o_ in others:
        B = trees[id(o_)] if not isinstance(o_, tuple) else o_
        for V, T in ((A[0], B[2]), (B[0], A[2])):
            for p in V:
                res = T.find_nearest(p, 0.03)
                if res[0] is not None: g = min(g, res[3])
    return g
gaps = []
for b, cs in by_bin.items():
    for a in cs:
        near = [o_ for o_ in cs if o_ is not a and not any(bb_of[id(a)][0][k] - 0.03 > bb_of[id(o_)][1][k] or bb_of[id(o_)][0][k] - 0.03 > bb_of[id(a)][1][k] for k in range(3))]
        gaps.append(min_gap(a, near + [FR]))
gaps_sorted = sorted(gaps)
print("RESTING GAP (nearest surface under/next to each item): median %.4f max %.4f m, items with gap > 6 mm: %d of %d" %
      (gaps_sorted[len(gaps) // 2], gaps_sorted[-1], sum(1 for g in gaps if g > 0.006), len(gaps)))
print("INTERPENETRATION max item-item %.4f m, item-frame %.4f m (%d touching pairs checked, %d with mesh contact)" %
      (max_pen_items, max_pen_frame, pairs_checked, tri_overlap_pairs))
RAW_STATS = {"max_item_item_penetration_m": round(max_pen_items, 4), "max_item_frame_penetration_m": round(max_pen_frame, 4),
             "pairs_with_mesh_contact": tri_overlap_pairs, "bbox_touching_pairs": pairs_checked,
             "resting_gap_median_m": round(gaps_sorted[len(gaps) // 2], 4), "resting_gap_max_m": round(gaps_sorted[-1], 4)}

# tidy: drop the simulation, keep the settled transforms
for u, c in sim_items:
    bpy.data.objects.remove(c.pop("sim_ob"), do_unlink=True)
for o in PARTS:
    if o.rigid_body: 
        bpy.ops.object.select_all(action="DESELECT"); o.select_set(True); bpy.context.view_layer.objects.active = o
        bpy.ops.rigidbody.object_remove()
bpy.data.objects.remove(bpy.data.objects["simground"], do_unlink=True)
bpy.ops.rigidbody.world_remove()
sc.frame_set(1)

# ---------- clip check (frame vs unit boxes and real item meshes) ----------
def box_tree(u):
    hx, hy, hz = [d / 2 - 0.0005 for d in u["box"]]
    c = u["pos"]
    V = [Vector((c.x + sx * hx, c.y + sy * hy, c.z + sz * hz)) for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]
    P = [[0, 1, 3, 2], [4, 6, 7, 5], [0, 4, 5, 1], [2, 3, 7, 6], [0, 2, 6, 4], [1, 5, 7, 3]]
    return BVHTree.FromPolygons(V, P)
clip_units, outside = [], 0
box_overlap = 0
hung = [u for u in UNITS if u["kind"] == "bundle"]
boxtrees = {u["index"]: box_tree(u) for u in hung}
for u in UNITS:
    bad = False
    if u["kind"] == "bundle":
        bt = boxtrees[u["index"]]
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
        if u["kind"] == "bundle":
            hx, hy, hz = [d / 2 + 0.002 for d in u["box"]]
            if any(abs(v.x - u["pos"].x) > hx or abs(v.y - u["pos"].y) > hy or abs(v.z - u["pos"].z) > hz for v in V): outside += 1
    for o in obs: bpy.data.objects.remove(o, do_unlink=True)
    if bad: clip_units.append(u["index"])
for i in range(len(hung)):
    for j in range(i + 1, len(hung)):
        if boxtrees[hung[i]["index"]].overlap(boxtrees[hung[j]["index"]]): box_overlap += 1
print("CLIPPING", len(clip_units), "of", len(UNITS), clip_units, "| hung item meshes outside own box:", outside,
      "| hung unit-box overlaps:", box_overlap)

# ---------- export: frame obj, anchors json, stats ----------
ALLV = fv
bb = [(min(v[i] for v in ALLV), max(v[i] for v in ALLV)) for i in range(3)]
print("FRAME BBOX m: x %.2f y %.2f z %.2f" % tuple(b[1] - b[0] for b in bb), "z max %.3f" % bb[2][1])
bpy.ops.object.select_all(action="DESELECT")
for o in PARTS: o.select_set(True)
bpy.ops.wm.obj_export(filepath=os.path.join(OUTA, "MeatRack.obj"), export_selected_objects=True, export_materials=False,
                      export_triangulated_mesh=True, forward_axis="NEGATIVE_Z", up_axis="Y")

def align_from_R(prefab, R):
    """exact align for a settled copy: long/thin bounds axes of the model mapped through the final rotation R"""
    ax = sorted(range(3), key=lambda i: info(prefab)[i])
    thin, mid, long = ax
    col = lambda i: Vector((R[0][i], R[1][i], R[2][i]))
    return col(long), col(thin)

def copy_json(c):
    if c["long_dir"] is None:                  # settled copy: align carries the whole rotation, then_rotate = identity
        ld, td = align_from_R(c["prefab"], c["R"])
        post = Matrix.Identity(3)
    else:
        ld, td, post = Vector(c["long_dir"]), Vector(c["thin_dir"]), c["post"]
    return {
        "offset": to_unity_vec(c["c"]),
        "longest_m": round(c["s"] * max(info(c["prefab"])), 4),
        "align": {"long_axis_to": [float(x) for x in to_unity_vec(ld)],
                  "thin_axis_to": [float(x) for x in to_unity_vec(td)],
                  "then_rotate_euler_zxy": ueuler(post), "then_rotate_quat_xyzw": uq(post)},
        "rendered_rotation_euler_zxy": ueuler(c["R"]), "rendered_rotation_quat_xyzw": uq(c["R"]),
    }

def unit_extent(u):
    lo = Vector((9, 9, 9)); hi = Vector((-9, -9, -9))
    for c in u["copies"]:
        V = world_rel(c["prefab"], c["R"], c["s"]) + np.array(c["c"])
        for i in range(3): lo[i] = min(lo[i], V[:, i].min()); hi[i] = max(hi[i], V[:, i].max())
    return lo, hi

def unit_json(u):
    d = {
        "index": u["index"], "kind": u["kind"], "group": u["group"], "slot_in_group": u["slot"],
        "position": to_unity_vec(u["pos"]), "rotation_euler": [0.0, 0.0, 0.0],
        "box_size": [round(u["box"][0], 3), round(u["box"][2], 3), round(u["box"][1], 3)],
        "render_item": u["prefab"],
        "copies": [copy_json(c) for c in u["copies"]],
    }
    lo, hi = unit_extent(u)
    ua_, ub_ = to_unity_vec(lo), to_unity_vec(hi)
    d["settled_extent_min"] = [min(a_, b_) for a_, b_ in zip(ua_, ub_)]; d["settled_extent_max"] = [max(a_, b_) for a_, b_ in zip(ua_, ub_)]
    if "cord" in u:
        cd = u["cord"]
        d["cord"] = {"offset": to_unity_vec(Vector((0, 0, (cd["top"] + cd["bottom"]) / 2))),
                     "length_m": round(cd["top"] - cd["bottom"], 4), "thickness_m": CORD_T,
                     "note": "hemp cord from the hook knot down through the bundle (vertical box, unit-centre xy)",
                     "knots": [{"offset": to_unity_vec(Vector((0, 0, kz))), "size_m": [ks, ks, kh]} for kz, ks, kh in cd["knots"]]}
    return d
anchors = {
    "slug": "meatrack", "round": 3, "physics": "bin piles are rigid-body settled (Blender Bullet), copies carry final transforms; hung bundles pinned on a cord", "slots_designed": len(UNITS), "units_at_100": len(UNITS),
    "coordinates": "Unity prefab space, same origin as MeatRack.obj. From Blender (z-up, -y front): ux=-bx, uy=bz, uz=-by. "
                   "box_size is (x, y, z) in Unity axes. Rotation matrices convert as R_u = M R_b M^T with M the same map; "
                   "euler values are Unity order (Z, then X, then Y).",
    "placing_an_item": "For every copy: scale the stored item's model uniformly so the longest side of its renderer bounds equals "
                       "longest_m; rotate it with align (turn its longest bounds axis to long_axis_to and its thinnest bounds axis "
                       "to thin_axis_to, middle axis follows right-handed), then apply then_rotate (about the unit centre axes); "
                       "put the centre of its bounds at unit.position + copy.offset. rendered_rotation_* is the finished rotation for "
                       "the item used in the render (render_item) and can be used directly for items with a similar shape. ROUND 3: pile units (bins) hold "
                       "SETTLED copies from a rigid body simulation: their then_rotate is identity and align alone gives the final "
                       "rotation, offset is the final resting position (items touch, nothing floats); fill is cumulative, so copies "
                       "already settled never move when more units are shown. Within a unit the copies are in drop order. Bundle units "
                       "also carry a cord (hemp box from the hook knot down through the bundle) with knots; the items touch it.",
    "fill_order": "units are sorted in fill order: show the first k units for k stacks in use (one stack per unit, stack holding the "
                  "same item for all copies of a unit).",
    "units": [unit_json(u) for u in UNITS],
}
json.dump(anchors, open(os.path.join(OUTA, "MeatRackAnchors.json"), "w"), indent=1)
stats = {"frame_tris": tris(PARTS), "units": len(UNITS), "hung_units": sum(1 for u in UNITS if u["kind"] == "bundle"),
         "pile_units": sum(1 for u in UNITS if u["kind"] == "pile"), "frame_bbox_m": [round(b[1] - b[0], 2) for b in bb],
         "height_max_m": round(bb[2][1], 3), "atlas": "meatrack_atlas.png 128x128, Closest",
         "item_copies_at_100": sum(len(u["copies"]) for u in UNITS), "sim": SIM_STATS, "penetration": RAW_STATS}
json.dump(stats, open(os.path.join(OUTA, "meatrack.json"), "w"), indent=1)
print("MEATRACK", stats)

# ---------- render scene: three racks (10 / 50 / 100 %), post, chest ----------
frame = join(PARTS, "rack")
def place_cord(u, xo):
    cd = u["cord"]; L = cd["top"] - cd["bottom"]
    x, y, z0 = u["pos"].x + xo, u["pos"].y, u["pos"].z
    timber("ucord", (CORD_T, CORD_T, L), (x, y, z0 + (cd["top"] + cd["bottom"]) / 2), kind="hemp", jitter=0.0008, bevel=0)
    for kz, ks, kh in cd["knots"]:
        timber("uknot", (ks, ks, kh), (x, y, z0 + kz), kind="hemp", jitter=0.0015, bevel=0.003)

SPACING = 2.7
racks = [(frame.copy(), -SPACING, 0.1), (frame, 0.0, 0.5), (frame.copy(), SPACING, 1.0)]
for ob, xo, fill in racks:
    if ob.name != frame.name: sc.collection.objects.link(ob)
    ob.location.x = xo
    k = max(1, round(fill * len(UNITS)))
    for u in UNITS[:k]:
        for c in u["copies"]: place(u, c, xo)
        if "cord" in u: place_cord(u, xo)
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
         "alt": (48, 21, 5.6, (SPACING, 0, 0.95)), "bins": (8, 48, 3.3, (SPACING, 0, 0.25)), "hung": (-24, 10, 3.4, (SPACING, 0, 1.2))}
for vn, (yaw, pitch, dist, tgt) in VIEWS.items():
    t = Vector(tgt)
    d = Vector((math.cos(math.radians(pitch)) * math.sin(math.radians(yaw)),
                -math.cos(math.radians(pitch)) * math.cos(math.radians(yaw)), math.sin(math.radians(pitch))))
    cam.location = t + d * dist; cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    sc.render.resolution_y = 700 if vn == "fills" else 900
    sc.render.filepath = os.path.join(OUT, f"{TAG}-{vn}.png")
    bpy.ops.render.render(write_still=True)
print("DONE")
