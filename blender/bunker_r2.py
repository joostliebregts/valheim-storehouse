"""Coal & Stone Bunker, round 2: our own frame mesh and atlas; contents are REAL Valheim item models placed at ANCHORS.
Run: blender -b -P bunker_r2.py -- [--out DIR] [--tag NAME] [--no-ref]
Writes into assets/bunker_r2/: Bunker.obj (frame only, forward -Z, up Y, triangulated, no materials),
bunker_atlas.png (128x128, point filtered) and bunker_anchors.json (content anchors in fill order).
Renders three bunkers (10/50/100 %) beside the vanilla wood chest and a 1.8 m post (local rips, reference only,
never exported). The item models come from C:/Users/joost/ValheimRip/items and are NOT part of any exported file.

Atlas 128x128 (horizontal strips that tile along u):
  v 0.75-1.00 hewn timber side grain (32 px)   v 0.50-0.75 end grain (4 ring tiles of 32 px)
  v 0.375-0.5 iron (16 px)                     v 0.00-0.375 unused (reserved)

ANCHOR CONVENTION. Blender (z up, -y front) -> Unity prefab space (y up, +z front):  ux=-bx, uy=bz, uz=-by.
As a matrix C = [[-1,0,0],[0,0,1],[0,-1,0]]. Rotations: R_unity = C R_blender C^-1, written as quaternion (x,y,z,w) and as
Unity euler degrees (Unity order Z, X, Y = Ry*Rx*Rz). Units are not rotated (box axis aligned, rot 0). Copy offsets are
relative to the unit position (= box centre), in the same Unity axes, and locate the item's BOUNDS CENTRE; the copy's
scale is a multiplier on the item's natural prefab scale (1.0 = the item as it lies in the world).
"""
import bpy, bmesh, sys, os, math, json, random
import numpy as np
from mathutils import Vector, Matrix, Euler, Quaternion
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
OUTA = os.path.normpath(os.path.join(HERE, "..", "assets", "bunker_r2"))
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = argv[argv.index("--out") + 1] if "--out" in argv else OUTA
TAG = argv[argv.index("--tag") + 1] if "--tag" in argv else "bunker"
RIP = "C:/Users/joost/ValheimRip/chests/piece_chest_wood"
ITEMS_DIR = "C:/Users/joost/ValheimRip/items"
os.makedirs(OUTA, exist_ok=True); os.makedirs(OUT, exist_ok=True)
sys.path.append(ITEMS_DIR)
from load_item import load_item
rng = random.Random(7)      # frame
crng = random.Random(23)    # contents (own stream so the frame never shifts)

TEX = 128
DENS = 48.0                                                    # px per metre, vanilla wood is 47-57
STRIP = {"hewn": 0.75, "end": 0.50, "iron": 0.375}
STRIPH = {"hewn": 32, "iron": 16}

# ---------- texture ----------
def srgb(c): return np.array(c, dtype=np.float32)
# calmer, slightly greyer wood than round 1; iron unchanged
WOOD, WOOD_D = srgb((0.36, 0.29, 0.20)), srgb((0.20, 0.16, 0.11))
END, END_D = srgb((0.50, 0.42, 0.31)), srgb((0.33, 0.27, 0.19))
IRON, IRON_D = srgb((0.22, 0.21, 0.20)), srgb((0.09, 0.09, 0.09))

def build_atlas():
    nr = np.random.default_rng(3)
    img = np.full((TEX, TEX, 3), 0.5, np.float32)          # row 0 = v 0 (bottom); lower part unused
    x = np.arange(TEX)[None, :].repeat(32, 0).astype(np.float32)
    y = np.arange(32)[:, None].repeat(TEX, 1).astype(np.float32)
    tile = lambda k: 2 * math.pi * k / TEX
    g = np.sin(y * 1.25 + 1.6 * np.sin(x * tile(2) + y * 0.15) + 0.7 * np.sin(x * tile(5)))
    t = np.clip((g - 0.55) * 2.5, 0, 1) * 0.65 + nr.random((32, TEX)) * 0.18
    t += np.clip(1 - np.minimum(y, 31 - y) / 3.0, 0, 1) * 0.35
    img[96:128] = WOOD * (1 - t[..., None]) + WOOD_D * t[..., None]
    for k in range(4):
        cx, cy = 15.5 + nr.uniform(-2, 2), 15.5 + nr.uniform(-2, 2)
        xx, yy = np.meshgrid(np.arange(32), np.arange(32))
        d = np.hypot(xx - cx, yy - cy) + 0.6 * np.sin(np.arctan2(yy - cy, xx - cx) * 3 + k)
        t = (np.sin(d * 1.5) * 0.5 + 0.5) * 0.45 + nr.random((32, 32)) * 0.15
        t = np.where(d > 13.5, 0.95, t)
        img[64:96, 32 * k:32 * k + 32] = END * (1 - t[..., None]) + END_D * t[..., None]
    yi = np.arange(16)[:, None].repeat(TEX, 1).astype(np.float32)
    t = nr.random((16, TEX)) * 0.4 + np.clip(1 - np.minimum(yi, 15 - yi) / 3.0, 0, 1) * 0.5
    img[48:64] = IRON * (1 - t[..., None]) + IRON_D * t[..., None]
    im = bpy.data.images.new("bunker_atlas", TEX, TEX, alpha=False)
    px = np.concatenate([np.clip(img, 0, 1), np.ones((TEX, TEX, 1), np.float32)], 2)
    im.pixels.foreach_set(px.ravel())
    im.filepath_raw = os.path.join(OUTA, "bunker_atlas.png"); im.file_format = "PNG"; im.save()
    return im

# ---------- geometry helpers ----------
PARTS = []     # frame objects

def uv_face(f, kind, long_axis, seed):
    n = f.normal
    ax = max(range(3), key=lambda i: abs(n[i]))
    tang = [i for i in range(3) if i != ax]
    if kind != "iron" and ax == long_axis:          # cut end of a timber
        k = seed % 4
        cs = [l.vert.co for l in f.loops]
        c = sum(cs, Vector()) / len(cs)
        ext = max(max(abs(v[tang[0]] - c[tang[0]]), abs(v[tang[1]] - c[tang[1]])) for v in cs) or 1
        for l in f.loops:
            a = (l.vert.co[tang[0]] - c[tang[0]]) / ext; b = (l.vert.co[tang[1]] - c[tang[1]]) / ext
            l[UV].uv = ((k + 0.5 + a * 0.45) / 4, STRIP["end"] + (0.5 + b * 0.45) / 4)
        return
    ua = long_axis if long_axis in tang else tang[0]
    va = tang[1] if ua == tang[0] else tang[0]
    off = (seed * 0.37) % 1
    vs = [l.vert.co[va] for l in f.loops]
    vmin, span = min(vs), max(max(vs) - min(vs), 1e-4)
    hpx = STRIPH[kind]
    vscale = min(1.0, (hpx / DENS) / span)
    used = span * vscale * DENS / TEX * 0.94
    room = max(hpx / TEX - used - 0.012, 0)
    voff = ((seed * 0.618) % 1) * room
    for l in f.loops:
        u = l.vert.co[ua] * DENS / TEX + off
        v = STRIP[kind] + ((l.vert.co[va] - vmin) * vscale * DENS / TEX) * 0.94 + 0.0075 + voff
        l[UV].uv = (u, v)

def timber(name, size, pos, kind="hewn", rot=(0, 0, 0), jitter=0.022, bevel=0.022):
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

# ---------- layout ----------
BW = 1.20                      # bay pitch (post centre to post centre); three bays
PXS = [-1.5 * BW, -0.5 * BW, 0.5 * BW, 1.5 * BW]
P = 0.20                       # posts are P x P
YF, YB = -0.70, 0.70           # front post centre y, back post base centre y
T = math.radians(8.0)          # back wall lean (top moves back)
sT, cT = math.sin(T), math.cos(T)
HF = 1.15                      # front post height
HB = 1.72                      # back post length along its axis
PITCH, PH = 0.22, 0.20         # plank pitch / height
NPL = 7
BAYS = [(PXS[i] + 0.135, PXS[i + 1] - 0.135) for i in range(3)]     # contents x bounds per bay
YF_IN = YF + 0.15              # contents front bound (boards and cleats lie in front of it)
Z_FLOOR = 0.14                 # contents floor (slat tops are 0.11 + jitter)
N_MAX = -0.13                  # contents back bound in the leaning back wall's normal coordinate

def tilt_pt(s, n):
    """Point on the back wall: s along the lean, n along its outward normal (post axis n=0). Returns (y, z)."""
    return YB + s * sT + n * cT, s * cT - n * sT

def build_frame():
    WID = PXS[-1] - PXS[0]
    # ---- posts: 4 front (straight), 4 back (leaning)
    for sx in PXS:
        h = HF + rng.uniform(-0.02, 0.03)
        timber("post", (P, P, h), (sx, YF, h / 2), rot=(rng.uniform(-1, 1), rng.uniform(-1, 1), 0))
        y, z = tilt_pt(HB / 2, 0)
        timber("post", (P, P, HB), (sx, y, z), rot=(-math.degrees(T) + rng.uniform(-0.8, 0.8), rng.uniform(-1, 1), 0))
    # ---- sills
    timber("sill", (WID + 0.34, 0.22, 0.18), (0, YF, 0.09), rot=(0, 0, rng.uniform(-0.5, 0.5)), bevel=0)
    timber("sill", (WID + 0.34, 0.22, 0.18), (0, YB + 0.04, 0.09), rot=(0, 0, rng.uniform(-0.5, 0.5)), bevel=0)
    for sx in PXS:
        timber("sill", (0.22, 1.62, 0.16), (sx, 0.02, 0.08), bevel=0)
    # ---- floor slats under each bay (run front-back)
    for (xl, xr) in BAYS:
        n = 5
        for k in range(n):
            xs = xl + (k + 0.5) * (xr - xl) / n
            timber("slat", (0.17, 1.26, 0.10), (xs, 0.03, 0.06), bevel=0)
    # ---- back wall: leaning planks flush with the post inner side
    for i in range(NPL):
        s = 0.11 + PITCH * i
        y, z = tilt_pt(s, -0.04)
        timber("backplank", (WID + 0.24, 0.10, PH), (0, y, z),
               rot=(-math.degrees(T) + rng.uniform(-0.6, 0.6), 0, rng.uniform(-0.4, 0.4)))
    y, z = tilt_pt(HB - 0.02, 0.0)
    timber("backcap", (WID + 0.34, 0.20, 0.11), (0, y, z), rot=(-math.degrees(T), 0, rng.uniform(-0.3, 0.3)))
    # ---- side walls and dividers: planks run front-back, top edge steps up to the back
    slope = (tilt_pt(HB, 0)[1] + 0.05 - (HF + 0.05)) / (tilt_pt(HB, 0)[0] - YF)
    walls = [(PXS[0] + 0.04, 0.10), (PXS[1], 0.16), (PXS[2], 0.16), (PXS[3] - 0.04, 0.10)]
    for sx, th in walls:
        for i in range(NPL):
            zc = 0.11 + PITCH * i
            top = zc + PH / 2
            y0 = YF if top <= HF else YF + (top - HF) / slope
            y1 = YB + zc * math.tan(T) + 0.06
            if y1 - y0 < 0.12: continue
            timber("sideplank", (th, y1 - y0, PH), (sx, (y0 + y1) / 2, zc), rot=(0, rng.uniform(-0.4, 0.4), 0))
    # sloped cap beams over the four walls
    ay, az = YF, HF + 0.05
    by, bz = tilt_pt(HB, 0)
    bz += 0.05
    ang = math.degrees(math.atan2(bz - az, by - ay))
    ln = math.hypot(by - ay, bz - az) + 0.14
    for sx in PXS:
        timber("cap", (P + 0.04, ln, 0.11), (sx, (ay + by) / 2, (az + bz) / 2), rot=(ang, 0, rng.uniform(-0.3, 0.3)))
    # ---- front board slots: two cleats on each bay-facing post side, boards slide in between
    for i in range(3):
        xa, xb = PXS[i], PXS[i + 1]
        for cx in (xa + P / 2 + 0.02, xb - P / 2 - 0.02):
            for dy in (-0.06, 0.06):
                timber("cleat", (0.04, 0.04, 0.88), (cx, YF + dy, 0.55), jitter=0.004, bevel=0)
        bx = (xa + xb) / 2
        lift = 0.15 if i == 2 else 0.0         # right bay: top board pulled half out of its slot
        for j in range(3):
            zc = 0.11 + 0.22 * j + 0.1 + (lift if j == 2 else 0)
            timber("board", (BW - P + 0.03, 0.08, PH), (bx, YF, zc), jitter=0.012, bevel=0.016,
                   rot=(0, rng.uniform(-0.3, 0.3), rng.uniform(-0.5, 0.5) + (2.5 if (j == 2 and lift) else 0)))
            if j == 2:
                timber("pull", (0.10, 0.025, 0.06), (bx, YF - 0.055, zc), kind="iron", jitter=0.002, bevel=0)
    # ---- iron: a band round every post top, a strap low on each front post, rivets
    for sx in PXS:
        timber("band", (P + 0.04, P + 0.04, 0.08), (sx, YF, HF - 0.03), kind="iron", jitter=0.003, bevel=0.006)
        y, z = tilt_pt(HB - 0.07, 0)
        timber("band", (P + 0.04, P + 0.04, 0.08), (sx, y, z), kind="iron", jitter=0.003, bevel=0.006,
               rot=(-math.degrees(T), 0, 0))
        timber("strap", (P + 0.05, 0.02, 0.14), (sx, YF - P / 2 - 0.008, 0.30), kind="iron", jitter=0.003, bevel=0)
        timber("strap", (P + 0.05, 0.02, 0.14), (sx, YF - P / 2 - 0.008, 0.80), kind="iron", jitter=0.003, bevel=0)
        for dx in (-0.06, 0.06):
            timber("rivet", (0.035, 0.03, 0.035), (sx + dx, YF - P / 2 - 0.022, 0.30), kind="iron", jitter=0, bevel=0)
    # long iron straps over the back wall planks (one per bay centre)
    for sx in [(PXS[i] + PXS[i + 1]) / 2 for i in range(3)]:
        y, z = tilt_pt(0.65, 0.07)
        timber("backstrap", (0.10, 0.02, 1.0), (sx, y, z), kind="iron", jitter=0.003, bevel=0,
               rot=(-math.degrees(T), 0, 0))

# ---------- real item models (render only; never exported) ----------
ITEM_NAMES = ["Coal", "Stone", "Flint", "Grausten", "Obsidian"]
BBOX_VOL = {"Coal": 0.0075, "Stone": 0.0075, "Flint": 0.0065, "Grausten": 0.0085, "Obsidian": 0.0068}   # bbox volume at unit scale target (m3)
TPL = {}

def load_templates():
    for nm in ITEM_NAMES:
        objs = [o for o in load_item(nm, anchor="center") if o.type == "MESH"]
        o = objs[0]
        V = np.array([v.co[:] for v in o.data.vertices], dtype=np.float64)
        ctr = (V.min(0) + V.max(0)) / 2
        o.data.transform(Matrix.Translation(-Vector(ctr)))          # exact bounds centre at the origin
        V = V - ctr
        size = V.max(0) - V.min(0)
        base = (BBOX_VOL[nm] / float(np.prod(size))) ** (1 / 3)      # natural-size multiplier for one stack member
        TPL[nm] = dict(mesh=o.data, V=V, size=size, base=base)
        for x in objs: bpy.data.objects.remove(x, do_unlink=True)

def rot_ext(V, R, s):
    """half extents of the rotated, scaled vertex cloud along world axes"""
    W = (V @ R.T) * s
    return np.abs(W).max(0)

# ---------- unit generation ----------
SLOPE = 0.85
PEAK = [0.42, 0.68, 0.94, 1.20, 1.42]
PLAT = [0.22, 0.18, 0.20, 0.24, 0.28]
BAY_PEAK_ADJ = [0.0, 0.0, 0.0]
NCOL, NROW = 3, 3
MINH, MAXH = 0.215, 0.48
MIX = [
    [("Coal", 62), ("Obsidian", 14), ("Flint", 14), ("Stone", 10)],
    [("Stone", 38), ("Grausten", 36), ("Flint", 10), ("Obsidian", 6), ("Coal", 10)],
    [("Flint", 30), ("Stone", 24), ("Coal", 22), ("Grausten", 14), ("Obsidian", 10)],
]
def yb_at(z): return YB + (N_MAX + z * sT) / cT - 0.004        # y of the contents back bound at height z
def nrm(y, z): return (y - YB) * cT - z * sT

def heap_h(bay, step, d, x):
    xl, xr = BAYS[bay]
    u = (x - (xl + xr) / 2) / ((xr - xl) / 2)
    h = PEAK[step] + BAY_PEAK_ADJ[bay] - SLOPE * max(0.0, d - PLAT[step])
    return h

def pick_item(bay, rr):
    tot = sum(w for _, w in MIX[bay]); a = rr.uniform(0, tot)
    for nm, w in MIX[bay]:
        a -= w
        if a <= 0: return nm
    return MIX[bay][0][0]

def fill_unit(item, box, rr):
    """Place 5-8 copies of one item inside box (x0,x1,y0,y1,z0,z1). Returns list of (pos Vector, Euler, scale)."""
    x0, x1, y0, y1, z0, z1 = box
    bs = np.array([x1 - x0, y1 - y0, z1 - z0])
    tp = TPL[item]; V = tp["V"]
    vol = float(np.prod(bs))
    s0 = tp["base"] * rr.uniform(0.96, 1.04)
    bboxv = float(np.prod(tp["size"])) * s0 ** 3
    n = int(min(8, max(5, round(1.5 * vol / bboxv))))
    # scale so n copies fit at ~1.25 bbox-overlap; never below 0.85 of the natural stack scale
    sc = min(s0, s0 * (1.5 * vol / (n * bboxv)) ** (1 / 3)) if vol < n * bboxv / 1.5 else s0
    sc = max(sc, s0 * 0.85)
    cop = []
    for i in range(n):
        placed = None
        s = sc * rr.uniform(0.97, 1.03)
        for attempt in range(14):
            tilt = 28 if attempt < 6 else (12 if attempt < 10 else 0)
            e = Euler((math.radians(rr.uniform(-tilt, tilt)), math.radians(rr.uniform(-tilt, tilt)),
                       math.radians(rr.uniform(0, 360))), "XYZ")
            R = np.array(e.to_matrix())
            ext = rot_ext(V, R, s)
            if np.all(ext * 2 <= bs - 1e-4):
                placed = (e, ext, s); break
        if placed is None:
            e = Euler((0, 0, math.radians(rr.uniform(0, 360))), "XYZ")
            R = np.array(e.to_matrix())
            while True:
                s *= 0.94
                ext = rot_ext(V, R, s)
                if np.all(ext * 2 <= bs - 1e-4): break
            placed = (e, ext, s)
        cop.append(placed)
    # jittered start positions, then relax overlaps (ellipsoid metric), staying inside the box
    lo = np.array([[x0, y0, z0]] * n) + np.array([c[1] for c in cop])
    hi = np.array([[x1, y1, z1]] * n) - np.array([c[1] for c in cop])
    P_ = np.array([[rr.uniform(lo[i][k], hi[i][k]) for k in range(3)] for i in range(n)])
    rad = np.array([c[1] * 0.68 for c in cop])
    for it in range(80):
        moved = False
        for i in range(n):
            for j in range(i + 1, n):
                d = P_[i] - P_[j]
                m = rad[i] + rad[j]
                q = math.sqrt(float(np.sum((d / m) ** 2)))
                if q < 1.0:
                    if q < 1e-6: d = np.array([rr.uniform(-1, 1) * 0.01, rr.uniform(-1, 1) * 0.01, 0.002]); q = 1e-3
                    push = d / q * (1.0 - q) * 0.5 * np.mean(m) * 0.9
                    P_[i] += push; P_[j] -= push; moved = True
        P_ = np.clip(P_, lo, hi)
        if not moved: break
    return [(Vector(P_[i]), cop[i][0], cop[i][2]) for i in range(n)]

def build_units():
    rr = crng
    units = []
    for bay in range(3):
        xl, xr = BAYS[bay]
        cw = (xr - xl) / NCOL
        for row in range(NROW):
            # step boundaries per (bay,row), identical for every column so the columns stay level
            cur = Z_FLOOR; zs = []
            for step in range(len(PEAK)):
                rowd = (yb_at(cur) - YF_IN) / NROW
                d = (row + 0.5) * rowd
                h = heap_h(bay, step, d, 0)
                if h - cur < MINH: continue
                nsplit = 1 if h - cur <= MAXH else 2
                for sp in range(nsplit):
                    zs.append((step, sp, cur + (h - cur) * sp / nsplit, cur + (h - cur) * (sp + 1) / nsplit))
                cur = h
            for col in range(NCOL):
                xa, xb = xl + col * cw, xl + (col + 1) * cw
                u = ((xa + xb) / 2 - (xl + xr) / 2) / ((xr - xl) / 2)
                dome = 0.045 * (1 - u * u) + rr.uniform(-0.015, 0.015)
                lastz = Z_FLOOR
                for k, (step, sp, z0, z1) in enumerate(zs):
                    z0 = lastz
                    z1 = z1 + dome if k == len(zs) - 1 else z1 + rr.uniform(-0.01, 0.01)
                    z1 = max(z1, z0 + MINH * 0.9)
                    rowd = (yb_at(z0) - YF_IN) / NROW
                    y1 = yb_at(z0) - row * rowd; y0 = max(YF_IN, y1 - rowd)
                    units.append(dict(bay=bay, col=col, row=row, step=step, sub=sp, box=(xa, xb, y0, y1, z0, z1)))
                    lastz = z1
    units.sort(key=lambda u: (u["step"], u["sub"], u["row"], u["bay"], u["col"]))
    for i, u in enumerate(units):
        u["index"] = i
        u["item"] = pick_item(u["bay"], rr)
        u["copies"] = fill_unit(u["item"], u["box"], rr)
    return units

# ---------- anchor export (Unity space) ----------
C = Matrix(((-1, 0, 0), (0, 0, 1), (0, -1, 0)))
Cinv = C.inverted()
def u_vec(v): return [round(-v.x, 4), round(v.z, 4), round(-v.y, 4)]
def u_rot(e):
    Ru = C @ e.to_matrix() @ Cinv
    q = Ru.to_quaternion()
    eu = Ru.to_euler("ZXY")      # matrix = Ry(eu.y) * Rx(eu.x) * Rz(eu.z), the Unity euler order
    return [round(math.degrees(eu.x), 2), round(math.degrees(eu.y), 2), round(math.degrees(eu.z), 2)], \
           [round(q.x, 5), round(q.y, 5), round(q.z, 5), round(q.w, 5)]

ROTERR = [0.0]
def anchors_json(units):
    out = []
    for u in units:
        x0, x1, y0, y1, z0, z1 = u["box"]
        ctr = Vector(((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2))
        cps = []
        for (p, e, s) in u["copies"]:
            eu, q = u_rot(e)
            Ru = C @ e.to_matrix() @ Cinv
            rec = Matrix.Rotation(math.radians(eu[1]), 3, "Y") @ Matrix.Rotation(math.radians(eu[0]), 3, "X") @ Matrix.Rotation(math.radians(eu[2]), 3, "Z")
            ROTERR[0] = max(ROTERR[0], max(abs(Ru[i][j] - rec[i][j]) for i in range(3) for j in range(3)))
            cps.append(dict(offset=u_vec(p - ctr), rot_euler=eu, rot_quat=q, scale=round(s, 4)))
        out.append(dict(index=u["index"], kind="heap_step", bay=u["bay"], row_from_back=u["row"], col=u["col"],
                        step=u["step"], position=u_vec(ctr), rotation=[0, 0, 0],
                        box=[round(x1 - x0, 4), round(z1 - z0, 4), round(y1 - y0, 4)],
                        render_item=u["item"], copies=cps))
    return out

# ---------- scene ----------
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
atlas = build_atlas()
MAT = bpy.data.materials.new("bunker"); MAT.use_nodes = True
nt = MAT.node_tree; bsdf = nt.nodes["Principled BSDF"]
ti = nt.nodes.new("ShaderNodeTexImage"); ti.image = atlas; ti.interpolation = "Closest"
nt.links.new(ti.outputs["Color"], bsdf.inputs["Base Color"])
bsdf.inputs["Roughness"].default_value = 0.8
load_templates()
FILLS = (0.1, 0.5, 1.0)
SPACE = 4.9
def tris(obs): return sum(len(p.vertices) - 2 for o in obs for p in o.data.polygons)

def join(obs, name):
    bpy.ops.object.select_all(action="DESELECT")
    for o in obs: o.select_set(True)
    bpy.context.view_layer.objects.active = obs[0]
    bpy.ops.object.join(); ob = bpy.context.active_object; ob.name = name
    return ob

def bvh_of_mesh_list(items):
    """items: list of (verts list, polys list)"""
    V, F, owner = [], [], []
    for k, (vs, ps) in enumerate(items):
        base = len(V)
        V += vs
        for p in ps:
            F.append(tuple(base + i for i in p)); owner.append(k)
    return BVHTree.FromPolygons(V, F), owner

def inside(bvh, p):
    votes = 0
    for dv in (Vector((0.31, 0.47, 0.83)), Vector((-0.52, 0.21, 0.71)), Vector((0.12, -0.63, 0.55))):
        d = dv.normalized(); n = 0; o = p.copy()
        while True:
            h = bvh.ray_cast(o, d)
            if h[0] is None: break
            n += 1; o = h[0] + d * 1e-4
        votes += n % 2
    return votes >= 2

def spawn(u, dx):
    obs = []
    for (p, e, s) in u["copies"]:
        ob = bpy.data.objects.new(u["item"], TPL[u["item"]]["mesh"])
        ob.location = p + Vector((dx, 0, 0)); ob.rotation_euler = e; ob.scale = (s, s, s)
        sc.collection.objects.link(ob); obs.append(ob)
    return obs

units = None
copies = []
for k, fill in enumerate(reversed(FILLS)):
    rng.seed(7); PARTS.clear()
    build_frame()
    dx = k * SPACE - SPACE if False else (len(FILLS) - 1 - k) * SPACE - SPACE
    if units is None:
        crng.seed(23)
        units = build_units()
        N = len(units)
        # ---- clip check against the frame (round-1 rules) ----
        fb, _ = bvh_of_mesh_list([([v.co.copy() for v in o.data.vertices], [tuple(p.vertices) for p in o.data.polygons])
                                  for o in PARTS])
        bad_items, bad_boxes, m_items = [], [], 0
        for u in units:
            x0, x1, y0, y1, z0, z1 = u["box"]
            bxv = [Vector((x, y, z)) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]
            oob = any(v.x < BAYS[u["bay"]][0] - 1e-4 or v.x > BAYS[u["bay"]][1] + 1e-4 or v.y < YF_IN - 1e-4 or
                      v.z < Z_FLOOR - 1e-4 or nrm(v.y, v.z) > N_MAX + 1e-4 for v in bxv)
            boxpoly = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
            bb, _ = bvh_of_mesh_list([(bxv, boxpoly)])
            ov = len(fb.overlap(bb)) > 0
            if oob or ov: bad_boxes.append((u["index"], oob, ov))
            for ci, (p, e, s) in enumerate(u["copies"]):
                m_items += 1
                M = Matrix.Translation(p) @ e.to_matrix().to_4x4() @ Matrix.Diagonal((s, s, s, 1))
                tp = TPL[u["item"]]
                W = [M @ Vector(v) for v in tp["V"]]
                fpoly = [tuple(q.vertices) for q in tp["mesh"].polygons]
                ib, _ = bvh_of_mesh_list([(W, fpoly)])
                ov2 = len(fb.overlap(ib)) > 0
                leave = any(w.x < x0 - 1e-4 or w.x > x1 + 1e-4 or w.y < y0 - 1e-4 or w.y > y1 + 1e-4 or
                            w.z < z0 - 1e-4 or w.z > z1 + 1e-4 for w in W)
                oob2 = any(w.x < BAYS[u["bay"]][0] - 1e-4 or w.x > BAYS[u["bay"]][1] + 1e-4 or w.y < YF_IN - 1e-4 or
                           w.z < Z_FLOOR - 1e-4 or nrm(w.y, w.z) > N_MAX + 1e-4 for w in W)
                ins = inside(fb, sum(W, Vector()) / len(W))
                if ov2 or leave or oob2 or ins: bad_items.append((u["index"], ci, ov2, leave, oob2, ins))
        nbad = len(bad_items) + len(bad_boxes)
        print("CLIPPING", nbad, "of", m_items + N, "(items", len(bad_items), "of", m_items, "boxes", len(bad_boxes), "of", N, ")",
              bad_items[:4], bad_boxes[:4])
        for bi in bad_boxes[:8]: print("BADBOX", bi, [round(v, 3) for v in units[bi[0]]["box"]], units[bi[0]]["bay"], units[bi[0]]["row"], units[bi[0]]["step"])
        for bi in bad_items[:8]: print("BADITEM", bi, [round(v, 3) for v in units[bi[0]]["box"]], units[bi[0]]["bay"], units[bi[0]]["row"], units[bi[0]]["item"])
        ncop = sum(len(u["copies"]) for u in units)
        from collections import Counter
        print("UNITS", N, "copies", ncop, "per step", dict(Counter(u["step"] for u in units)),
              "per bay", dict(Counter(u["bay"] for u in units)), "items", dict(Counter(u["item"] for u in units)),
              "copies/unit", dict(Counter(len(u["copies"]) for u in units)))
        # ---- exports ----
        meta = dict(round=2, slots_designed_for=N, unit="one unit = one full stack",
                    convention="Blender z-up/-y front -> Unity y-up/+z front: ux=-bx, uy=bz, uz=-by; rotations R_u=C R_b C^-1",
                    frame_obj="Bunker.obj (forward -Z, up Y, triangulated, no materials)",
                    fill_order="units[] is in fill order: step (heap layer) ascending, then sub, row from back, bay, col",
                    pivot="copy offset locates the item's bounds centre; scale multiplies the item's natural prefab scale",
                    item_hint="render_item is only the item used in the preview; the mod places whatever item the stack holds",
                    frame_tris=tris(PARTS), clipping=nbad,
                    bay_bounds_x=[list(b) for b in BAYS],
                    bay_bounds_unity_x=[[round(-b[1], 4), round(-b[0], 4)] for b in BAYS])
        aj = anchors_json(units)
        print("ROTCHECK max euler-vs-matrix error %.5f" % ROTERR[0])
        json.dump(dict(meta=meta, units=aj), open(os.path.join(OUTA, "bunker_anchors.json"), "w"), indent=1)
        bpy.ops.object.select_all(action="DESELECT")
        for o in PARTS: o.select_set(True)
        bpy.ops.wm.obj_export(filepath=os.path.join(OUTA, "Bunker.obj"), export_selected_objects=True, export_materials=False,
                              export_triangulated_mesh=True, forward_axis="NEGATIVE_Z", up_axis="Y")
        ct = Counter()
        for o in PARTS: ct[o.name.split(".")[0]] += tris([o])
        print("TRIS", dict(ct))
        print("BUNKER frame_tris", tris(PARTS))
        xs = [v.co.x for o in PARTS for v in o.data.vertices]; ys = [v.co.y for o in PARTS for v in o.data.vertices]
        zs = [v.co.z for o in PARTS for v in o.data.vertices]
        print("BOUNDS x %.2f..%.2f y %.2f..%.2f z %.2f..%.2f" % (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)))
    shown = units[:round(fill * len(units))]
    ob = join(list(PARTS), f"bunker_{int(fill * 100)}")
    ob.location.x = dx
    for u in shown: spawn(u, dx)
    print("FILL", fill, "units", len(shown))

# vanilla wood chest + a plain 1.8 m post, for scale (reference only, never exported)
CH_X = -(SPACE + 3.6)
if "--no-ref" not in argv:
    rep = json.load(open("C:/Users/joost/ValheimRip/chests/report.json"))["piece_chest_wood"]["nodes"]
    vimg = bpy.data.images.load(f"{RIP}/woodchest_d.png")
    vm = bpy.data.materials.new("ref"); vm.use_nodes = True
    vt = vm.node_tree.nodes.new("ShaderNodeTexImage"); vt.image = vimg; vt.interpolation = "Closest"
    vm.node_tree.links.new(vt.outputs["Color"], vm.node_tree.nodes["Principled BSDF"].inputs["Base Color"])
    for node in rep:
        if not node["path"].endswith(("/woodchest", "/woodchesttop_closed")): continue
        V, T_, F = [], [], []
        for l in open(node["mesh"]["obj"]):
            p = l.split()
            if not p: continue
            if p[0] == "v": V.append(Vector((-float(p[1]), float(p[2]), float(p[3]))))
            elif p[0] == "vt": T_.append((float(p[1]), float(p[2])))
            elif p[0] == "f": F.append([tuple(int(x) - 1 for x in q.split("/")[:2]) for q in reversed(p[1:])])
        q = node["rot"]
        M = Matrix.Translation(Vector(node["pos"])) @ Quaternion((q[3], q[0], q[1], q[2])).to_matrix().to_4x4() \
            @ Matrix.Diagonal((*node["scale"], 1))
        verts = [M @ v for v in V]
        verts = [Vector((-v.x + CH_X + 5.9 - 5.9, -v.z - 0.3, v.y)) for v in verts]
        F = [list(reversed(f)) for f in F]
        me = bpy.data.meshes.new("ref"); me.from_pydata(verts, [], [[c[0] for c in f] for f in F])
        uvl = me.uv_layers.new(); i = 0
        for f in F:
            for c in f: uvl.data[i].uv = T_[c[1]]; i += 1
        ob = bpy.data.objects.new("ref", me); sc.collection.objects.link(ob); ob.data.materials.append(vm)
    # plain 1.8 m player-height post
    pm = bpy.data.materials.new("post"); pm.use_nodes = True
    pm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.30, 0.30, 0.29, 1)
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(CH_X - 1.3, -0.3, 0.9))
    pst = bpy.context.active_object; pst.scale = (0.14, 0.14, 1.8); pst.data.materials.append(pm); pst.name = "post_1.8m"

world = bpy.data.worlds.new("w"); sc.world = world; world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.42, 0.45, 0.5, 1)
world.node_tree.nodes["Background"].inputs[1].default_value = 0.9
sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN")); sun.data.energy = 3.2
sun.rotation_euler = (math.radians(50), 0, math.radians(35)); sc.collection.objects.link(sun)
bpy.ops.mesh.primitive_plane_add(size=120)
gm = bpy.data.materials.new("ground"); gm.use_nodes = True
gm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.16, 0.14, 0.11, 1)
bpy.context.active_object.data.materials.append(gm)
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam); sc.camera = cam
sc.render.engine = "BLENDER_EEVEE_NEXT"
sc.render.resolution_x, sc.render.resolution_y = 1600, 900
sc.view_settings.view_transform = "Standard"
VIEWS = {"fills": (-8, 27, 24.5, (-1.9, 0, 0.5)), "close": (-28, 30, 8.6, (SPACE, 0, 0.65)),
         "alt": (35, 48, 8.4, (SPACE, 0.1, 0.6))}
for vn, (yaw, pitch, dist, tgt) in VIEWS.items():
    t = Vector(tgt)
    d = Vector((math.cos(math.radians(pitch)) * math.sin(math.radians(yaw)),
                -math.cos(math.radians(pitch)) * math.cos(math.radians(yaw)), math.sin(math.radians(pitch))))
    cam.location = t + d * dist; cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    sc.render.filepath = os.path.join(OUT, f"{TAG}-{vn}.png")
    bpy.ops.render.render(write_still=True)
print("DONE")
