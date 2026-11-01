"""Root Bin: three slatted crates in a low timber frame, with rising heaps of produce. Our own mesh, our own texture.
Run: blender -b -P rootbin.py -- --out DIR [--tag NAME] [--no-ref]
Writes into assets/rootbin/: RootBin.obj (frame), RootBinItems.obj (12 fill steps, one object each, item_000..item_011
in fill order), rootbin_atlas.png (128x128, point filtered) and rootbin.json. Then renders to --out beside the vanilla
wood chest (local rip, reference only, never exported).

Atlas (v from the bottom, strips tile along u):
  v 0.75-1.00 hewn timber   v 0.50-0.75 end grain (4 ring tiles)   v 0.375-0.50 weathered plank   v 0.25-0.375 iron
  v 0.00-0.25 SWATCHES: 16 cells of 8 px, each a vertical gradient (bottom colour -> top colour), speckled.
     cells 0-11 = primary item colours (the mod re-points these per stored item), cells 12-15 = fixed accents.
Contents: five shapes (bulb, carrot, mushroom, berries, sheaf) x the primary colours. Fill order: crate by crate
(left to right), inside a crate heap step by heap step (4 terraces, each a lumpy mound plus items on its rim).
"""
import bpy, bmesh, sys, os, math, json, random
import numpy as np
from mathutils import Vector, Matrix, Euler
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
OUTA = os.path.normpath(os.path.join(HERE, "..", "assets", "rootbin"))
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = argv[argv.index("--out") + 1] if "--out" in argv else OUTA
TAG = argv[argv.index("--tag") + 1] if "--tag" in argv else "rootbin"
RIP = "C:/Users/joost/ValheimRip/chests/piece_chest_wood"
os.makedirs(OUTA, exist_ok=True); os.makedirs(OUT, exist_ok=True)
rng = random.Random(7)

TEX = 128
DENS = 48.0
# strip: (v base, rows)
STRIP = {"hewn": (0.75, 32), "end": (0.5, 32), "dark": (0.375, 16), "iron": (0.25, 16)}
CELL = 8

# ---------- texture ----------
def srgb(c): return np.array(c, dtype=np.float32)
WOOD, WOOD_D = srgb((0.38, 0.29, 0.18)), srgb((0.21, 0.16, 0.10))
WOODW, WOODW_D = srgb((0.31, 0.26, 0.19)), srgb((0.16, 0.13, 0.09))
END, END_D = srgb((0.55, 0.45, 0.31)), srgb((0.35, 0.27, 0.17))
IRON, IRON_D = srgb((0.22, 0.21, 0.20)), srgb((0.09, 0.09, 0.09))

# (name, top colour, bottom colour). Cells 0-11 primary (re-pointable per item), 12-15 fixed accents.
SWATCH = [
    ("turnip",     (0.52, 0.30, 0.44), (0.77, 0.71, 0.58)),
    ("onion",      (0.60, 0.46, 0.22), (0.46, 0.31, 0.15)),
    ("beet",       (0.44, 0.15, 0.22), (0.27, 0.08, 0.13)),
    ("carrot",     (0.76, 0.43, 0.15), (0.60, 0.30, 0.10)),
    ("red_cap",    (0.62, 0.20, 0.14), (0.42, 0.11, 0.09)),
    ("tan_cap",    (0.60, 0.48, 0.27), (0.43, 0.33, 0.18)),
    ("blue_cap",   (0.26, 0.40, 0.58), (0.13, 0.22, 0.38)),
    ("blueberry",  (0.30, 0.32, 0.57), (0.14, 0.15, 0.34)),
    ("raspberry",  (0.70, 0.23, 0.28), (0.48, 0.11, 0.17)),
    ("cloudberry", (0.80, 0.56, 0.20), (0.60, 0.38, 0.12)),
    ("straw",      (0.76, 0.66, 0.33), (0.56, 0.46, 0.21)),
    ("flax",       (0.48, 0.56, 0.42), (0.30, 0.38, 0.27)),
    ("stem",       (0.72, 0.66, 0.52), (0.52, 0.46, 0.34)),
    ("leaf",       (0.32, 0.42, 0.19), (0.20, 0.28, 0.12)),
    ("soil",       (0.42, 0.32, 0.20), (0.26, 0.19, 0.12)),
    ("dark",       (0.18, 0.15, 0.11), (0.10, 0.08, 0.06)),
]
NPRIMARY = 12

def wood_strip(img, r0, rows, a, b, nr):
    x = np.arange(TEX)[None, :].repeat(rows, 0).astype(np.float32)
    y = np.arange(rows)[:, None].repeat(TEX, 1).astype(np.float32)
    tile = lambda k: 2 * math.pi * k / TEX
    g = np.sin(y * 1.25 + 1.6 * np.sin(x * tile(2) + y * 0.15) + 0.7 * np.sin(x * tile(5)))
    t = np.clip((g - 0.55) * 2.5, 0, 1) * 0.65 + nr.random((rows, TEX)) * 0.18
    t += np.clip(1 - np.minimum(y, rows - 1 - y) / 3.0, 0, 1) * 0.35
    img[r0:r0 + rows] = a * (1 - t[..., None]) + b * t[..., None]

def build_atlas():
    nr = np.random.default_rng(3)
    img = np.zeros((TEX, TEX, 3), np.float32)          # row 0 = v 0 (bottom)
    wood_strip(img, 96, 32, WOOD, WOOD_D, nr)
    wood_strip(img, 48, 16, WOODW, WOODW_D, nr)
    for k in range(4):
        cx, cy = 15.5 + nr.uniform(-2, 2), 15.5 + nr.uniform(-2, 2)
        xx, yy = np.meshgrid(np.arange(32), np.arange(32))
        d = np.hypot(xx - cx, yy - cy) + 0.6 * np.sin(np.arctan2(yy - cy, xx - cx) * 3 + k)
        t = (np.sin(d * 1.5) * 0.5 + 0.5) * 0.45 + nr.random((32, 32)) * 0.15
        t = np.where(d > 13.5, 0.95, t)
        img[64:96, 32 * k:32 * k + 32] = END * (1 - t[..., None]) + END_D * t[..., None]
    y = np.arange(16)[:, None].repeat(TEX, 1).astype(np.float32)
    t = nr.random((16, TEX)) * 0.4 + np.clip(1 - np.minimum(y, 15 - y) / 3.0, 0, 1) * 0.5
    img[32:48] = IRON * (1 - t[..., None]) + IRON_D * t[..., None]
    # swatches: bottom colour at row 0, top colour at row 31, speckled
    for i, (_, top, bot) in enumerate(SWATCH):
        top, bot = srgb(top), srgb(bot)
        top, bot = [c.mean() + (c - c.mean()) * 0.88 for c in (top, bot)]
        tt = (np.arange(32, dtype=np.float32) / 31.0)[:, None, None]
        cell = bot * (1 - tt) + top * tt
        cell = cell.repeat(CELL, 1)
        cell = cell * (1 + (nr.random((32, CELL, 1)) - 0.5) * 0.16)
        img[0:32, i * CELL:(i + 1) * CELL] = cell
    im = bpy.data.images.new("rootbin_atlas", TEX, TEX, alpha=False)
    px = np.concatenate([np.clip(img, 0, 1), np.ones((TEX, TEX, 1), np.float32)], 2)
    im.pixels.foreach_set(px.ravel())
    im.filepath_raw = os.path.join(OUTA, "rootbin_atlas.png"); im.file_format = "PNG"; im.save()
    return im

# ---------- frame geometry ----------
PARTS = []

def uv_face(f, kind, long_axis, seed):
    n = f.normal
    ax = max(range(3), key=lambda i: abs(n[i]))
    tang = [i for i in range(3) if i != ax]
    if kind != "iron" and ax == long_axis:
        k = seed % 4
        cs = [l.vert.co for l in f.loops]
        c = sum(cs, Vector()) / len(cs)
        ext = max(max(abs(v[tang[0]] - c[tang[0]]), abs(v[tang[1]] - c[tang[1]])) for v in cs) or 1
        for l in f.loops:
            a = (l.vert.co[tang[0]] - c[tang[0]]) / ext; b = (l.vert.co[tang[1]] - c[tang[1]]) / ext
            l[UV].uv = ((k + 0.5 + a * 0.45) / 4, STRIP["end"][0] + (0.5 + b * 0.45) / 4)
        return
    ua = long_axis if long_axis in tang else tang[0]
    va = tang[1] if ua == tang[0] else tang[0]
    off = (seed * 0.37) % 1
    vs = [l.vert.co[va] for l in f.loops]
    vmin, span = min(vs), max(max(vs) - min(vs), 1e-4)
    base, rows = STRIP[kind]
    vscale = min(1.0, (rows / DENS) / span)
    for l in f.loops:
        u = l.vert.co[ua] * DENS / TEX + off
        v = base + ((l.vert.co[va] - vmin) * vscale * DENS / TEX) * 0.94 + 0.0075
        l[UV].uv = (u, v)

def timber(name, size, pos, kind="hewn", rot=(0, 0, 0), jitter=0.015, bevel=0.012):
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

FLOOR = 0.30                       # top of the floor slats
BAYS = [-0.6135, 0.0, 0.6135]      # crate centres along x
HALF_W = 0.2465                    # clear half width of a crate (face of the posts)
IN_Y = 0.36                        # clear half depth
EX_X = 0.93                        # end posts

def build_frame():
    j = lambda a: rng.uniform(-a, a)
    # posts: tall at the back, short at the front, so you look into the crates
    for sx in (-1, 1):
        for sy, h in ((1, 1.10), (-1, 0.70)):
            hh = h + j(0.02)
            timber("post", (0.14, 0.14, hh), (sx * EX_X, sy * 0.44, hh / 2), rot=(j(0.8), j(0.8), 0), bevel=0.016)
    for sx in (-1, 1):
        for sy, h in ((1, 1.0), (-1, 0.64)):
            hh = h + j(0.02)
            timber("dpost", (0.12, 0.12, hh), (sx * 0.307, sy * 0.44, hh / 2), rot=(j(0.8), j(0.8), 0), bevel=0.014)
    # sills on the ground, bearers under the floor
    for sy in (-1, 1):
        timber("sill", (2.08, 0.14, 0.14), (0, sy * 0.44, 0.07), rot=(0, 0, j(0.4)), bevel=0.016)
        timber("bearer", (1.86, 0.09, 0.10), (0, sy * 0.30, 0.22), kind="dark", bevel=0, jitter=0.006)
    # floor slats, 4 per crate, running front to back
    for bx in BAYS:
        for dx in (-0.185, -0.062, 0.062, 0.185):
            timber("floor", (0.108, 0.84, 0.04), (bx + dx + j(0.004), 0, FLOOR - 0.02 + j(0.004)), kind="dark",
                   bevel=0, jitter=0.004)
    # back boards, 4 per crate, a finger of gap between
    for bx in BAYS:
        for z in (0.43, 0.65, 0.87):
            timber("back", (0.50, 0.045, 0.15), (bx, 0.41, z + j(0.006)), rot=(j(1.2), 0, j(0.9)), bevel=0.008, jitter=0.006)
    timber("toprail", (1.84, 0.12, 0.10), (0, 0.44, 1.05), rot=(0, 0, j(0.3)), bevel=0.014)
    # front planks lean outwards (display bin), two per crate
    for bx in BAYS:
        for z in (0.37, 0.50):
            timber("front", (0.50, 0.045, 0.11), (bx, -0.405, z + j(0.004)), rot=(12 + j(1.5), 0, j(0.8)),
                   kind="dark", bevel=0.008, jitter=0.005)
    # sloped side boards between the posts: 4 walls x 2 boards
    for x in (-EX_X, -0.307, 0.307, EX_X):
        for zc in (0.74, 0.50):
            ang = math.degrees(math.atan2(0.30, 0.84))
            timber("side", (0.045, math.hypot(0.30, 0.84) + 0.06, 0.12), (x, 0.0, zc + j(0.005)),
                   rot=(ang + j(1.0), 0, 0), kind="dark", bevel=0.008, jitter=0.004)
    # iron: a band round every post top, two straps over the front planks of every crate
    for sx in (-1, 1):
        for sy, h, w, px in ((1, 1.10, 0.14, EX_X), (-1, 0.70, 0.14, EX_X), (1, 1.0, 0.12, 0.307), (-1, 0.64, 0.12, 0.307)):
            if sy == 1 and px == 0.307:
                continue                                  # divider back posts carry the top rail
            timber("band", (w + 0.035, w + 0.035, 0.05), (sx * px, sy * 0.44, h - 0.05), kind="iron", jitter=0.003, bevel=0.006)
    for bx in BAYS:
        for dx in (-0.17, 0.17):
            timber("strap", (0.045, 0.014, 0.27), (bx + dx, -0.433, 0.44), rot=(12, 0, 0), kind="iron", jitter=0.002, bevel=0.004)

# ---------- contents ----------
STEPS = []          # step objects in fill order
DOME_H = [0.19, 0.17, 0.15, 0.13]
DOME_RATIO = 0.78   # radius of the next step against this one
R0 = (0.215, 0.315)
SHOULDER = (0.92, 0.75)   # profile: base ring (1, 0), shoulder ring (0.92, 0.75 h), apex (0, h)

def lathe(profile, n):
    V, R = [], []
    for r, z in profile:
        if r <= 1e-6:
            R.append([len(V)]); V.append(Vector((0, 0, z)))
        else:
            ring = []
            for i in range(n):
                a = 2 * math.pi * i / n
                ring.append(len(V)); V.append(Vector((r * math.cos(a), r * math.sin(a), z)))
            R.append(ring)
    F = []
    for a, b in zip(R, R[1:]):
        if len(a) == 1 and len(b) == 1: continue
        if len(a) == 1:
            for i in range(n): F.append([a[0], b[(i + 1) % n], b[i]])
        elif len(b) == 1:
            for i in range(n): F.append([a[i], a[(i + 1) % n], b[0]])
        else:
            for i in range(n): F.append([a[i], a[(i + 1) % n], b[(i + 1) % n], b[i]])
    return V, F

def uvx(sw, x):
    """u inside swatch cell sw, with a little per-vertex speckle."""
    return (sw * CELL + CELL / 2 + (math.sin(x * 977.0) * 2.4)) / TEX

def add_part(bm, V, F, sw, M, uvl, vmode=(0.0, 1.0), jit=0.0):
    zs = [v.z for v in V]; z0, z1 = min(zs), max(zs); span = max(z1 - z0, 1e-6)
    bv = []; lz = {}
    for v in V:
        p = Vector(v)
        if jit: p += Vector((rng.uniform(-jit, jit), rng.uniform(-jit, jit), rng.uniform(-jit, jit)))
        b = bm.verts.new(M @ p); bv.append(b); lz[b] = v.z
    faces = []
    for f in F:
        try: face = bm.faces.new([bv[i] for i in f])
        except ValueError: continue
        face.smooth = False; faces.append(face)
        for l in face.loops:
            fr = (lz[l.vert] - z0) / span
            fr = vmode[0] + fr * (vmode[1] - vmode[0])
            l[uvl].uv = (uvx(sw, l.vert.co.x + l.vert.co.y), (1.5 + fr * 29.0) / TEX)
    # outward winding: faces must look away from the part's centre
    bm.normal_update()
    c = sum((b.co for b in bv), Vector()) / len(bv)
    score = sum(f.normal.dot(f.calc_center_median() - c) * f.calc_area() for f in faces)
    if score < 0:
        for f in faces: f.normal_flip()
    return [b.co for b in bv]

def rotz(a): return Matrix.Rotation(a, 4, "Z")
def aim(d):   # local +Z -> direction d
    return d.normalized().to_track_quat("Z", "Y").to_matrix().to_4x4()

def item_parts(shape, sw, rng_):
    """list of (V, F, swatch, sub-matrix, vmode)"""
    I = Matrix.Identity(4)
    if shape == "bulb":
        style = rng_.choice((0, 1))
        pr = [(0, -0.09), (0.076, -0.012), (0.05, 0.03), (0, 0.042)] if style == 0 else [(0, -0.075), (0.07, -0.005), (0.042, 0.04), (0, 0.06)]
        V, F = lathe(pr, 5)
        stub = lathe([(0.014, 0.0), (0, 0.05)], 3)
        return [(V, F, sw, I, (0, 1)), (stub[0], stub[1], 13, Matrix.Translation((0, 0, 0.045)), (0, 1))]
    if shape == "carrot":
        V, F = lathe([(0, -0.10), (0.034, 0.09), (0, 0.095)], 5)
        t = lathe([(0.02, 0.0), (0, 0.08)], 3)
        return [(V, F, sw, I, (0, 1)),
                (t[0], t[1], 13, Matrix.Translation((0.008, 0, 0.09)) @ Euler((0.5, 0.2, 0)).to_matrix().to_4x4(), (0, 1)),
                (t[0], t[1], 13, Matrix.Translation((-0.008, 0, 0.09)) @ Euler((-0.4, -0.3, 0)).to_matrix().to_4x4(), (0, 1))]
    if shape == "mush":
        sk = lathe([(0.018, -0.05), (0.066, 0.0)], 5)
        cap = lathe([(0.066, 0.0), (0.046, 0.03), (0, 0.044)], 5)
        return [(sk[0], sk[1], 12, I, (0, 1)), (cap[0], cap[1], sw, I, (0, 1))]
    if shape == "berry":
        out = []
        for (x, y, z, r) in ((0, 0, 0, 0.040), (0.058, 0.018, -0.004, 0.034), (0.02, -0.055, 0.0, 0.036)):
            V, F = lathe([(0, -r), (r, 0), (0, r)], 4)
            out.append((V, F, sw, Matrix.Translation((x - 0.02, y + 0.012, z)) @ rotz(rng_.uniform(0, 1.5)), (0, 1)))
        return out
    if shape == "sheaf":
        out = []
        for ang, off in ((0.10, 0.012), (-0.12, -0.012)):
            V, F = lathe([(0, -0.125), (0.034, -0.03), (0, 0.125)], 4)
            out.append((V, F, sw, Matrix.Translation((off, 0, 0)) @ Euler((0, ang, 0)).to_matrix().to_4x4(), (0, 1)))
        return out
    raise ValueError(shape)

# recipe per crate and heap step: shape, colour choices (swatch cells), mound colour, item count
RECIPE = [
    [dict(shape="bulb", sw=[0, 0, 1], mound=0, n=7), dict(shape="bulb", sw=[1, 1, 0], mound=1, n=5),
     dict(shape="bulb", sw=[2, 2, 1], mound=2, n=4), dict(shape="bulb", sw=[0, 2, 1], mound=2, n=3)],
    [dict(shape="carrot", sw=[3], mound=3, n=7), dict(shape="carrot", sw=[3], mound=3, n=5),
     dict(shape="mush", sw=[4, 4, 5], mound=14, n=5), dict(shape="mush", sw=[5, 6, 4], mound=14, n=4)],
    [dict(shape="sheaf", sw=[10], mound=10, n=8), dict(shape="sheaf", sw=[11, 10], mound=11, n=6),
     dict(shape="berry", sw=[7, 8], mound=13, n=4), dict(shape="berry", sw=[9, 8, 7], mound=13, n=4)],
]
LIFT = {"bulb": 0.022, "carrot": 0.026, "mush": 0.034, "berry": 0.020, "sheaf": 0.022}

def dome_geom(k):
    h = DOME_H[k]; rx, ry = R0[0] * DOME_RATIO ** k, R0[1] * DOME_RATIO ** k
    zb = FLOOR + 0.010
    for i in range(k):
        zb += DOME_H[i] * (1 - 0.25 * DOME_RATIO / SHOULDER[0]) - 0.01
    return rx, ry, zb, h

def surf_z(k, s):
    rx, ry, zb, h = dome_geom(k)
    return zb + h * (1 - 0.25 * min(s, SHOULDER[0]) / SHOULDER[0])

def build_contents(meta=None):
    j = lambda a: rng.uniform(-a, a)
    idx = 0
    for b, bx in enumerate(BAYS):
        for k in range(4):
            rc = RECIPE[b][k]
            rx, ry, zb, h = dome_geom(k)
            bm = bmesh.new(); uvl = bm.loops.layers.uv.verify()
            V, F = lathe([(1.0, 0.0), (SHOULDER[0], SHOULDER[1]), (0, 1.0)], 7)
            for v in V:
                if v.x or v.y: v.x *= 1 + j(0.06); v.y *= 1 + j(0.06)
                v.z = max(0, v.z + (j(0.07) if v.z > 0.01 else 0))
            Md = Matrix.Translation((bx + j(0.004), j(0.004), zb)) @ rotz(j(0.3)) @ Matrix.Diagonal((rx, ry, h, 1))
            add_part(bm, V, F, rc["mound"], Md, uvl, vmode=(0.0, 0.32))
            n = rc["n"]; top = (k == 3)
            th0 = rng.uniform(0, 6.28)
            for q in range(n):
                sw = rc["sw"][q % len(rc["sw"])]
                if top:
                    if q == 0: s, th = 0.0, 0.0
                    else: s, th = rng.uniform(0.45, 0.62), th0 + 2 * math.pi * (q - 1) / max(1, n - 1)
                else:
                    th = th0 + 2 * math.pi * (q + rng.uniform(-0.18, 0.18)) / n
                    s = rng.uniform(0.80, 0.90)
                px = bx + s * rx * math.cos(th); py = s * ry * math.sin(th)
                pz = surf_z(k, s) + LIFT[rc["shape"]]
                sc = rng.uniform(1.15, 1.38)
                if rc["shape"] in ("carrot", "sheaf"):
                    phi = th + (j(0.5) if rc["shape"] == "carrot" else 1.57 + j(0.4))
                    el = math.radians(rng.uniform(8, 28) if rc["shape"] == "carrot" else rng.uniform(0, 12))
                    d = Vector((math.cos(phi) * math.cos(el), math.sin(phi) * math.cos(el), math.sin(el)))
                    R = aim(d)
                else:
                    tilt = Euler((math.radians(j(18)), math.radians(j(18)), rng.uniform(0, 6.28))).to_matrix().to_4x4()
                    R = tilt
                S = Matrix.Diagonal((sc, sc, sc, 1))
                parts = item_parts(rc["shape"], sw, rng)
                # keep inside the crate: slide the whole item in x/y if it pokes out, and above the floor
                Mi = Matrix.Translation((px, py, pz)) @ R @ S
                wv = [Mi @ sm @ v for (V_, F_, s_, sm, vm) in parts for v in V_]
                dx = dy = dz = 0.0
                if max(v.x for v in wv) > bx + HALF_W - 0.012: dx = bx + HALF_W - 0.012 - max(v.x for v in wv)
                if min(v.x for v in wv) < bx - HALF_W + 0.012: dx = bx - HALF_W + 0.012 - min(v.x for v in wv)
                if max(v.y for v in wv) > IN_Y - 0.012: dy = IN_Y - 0.012 - max(v.y for v in wv)
                if min(v.y for v in wv) < -IN_Y + 0.012: dy = -IN_Y + 0.012 - min(v.y for v in wv)
                if min(v.z for v in wv) < FLOOR + 0.012: dz = FLOOR + 0.012 - min(v.z for v in wv)
                Mi = Matrix.Translation((dx, dy, dz)) @ Mi
                for (V_, F_, s_, sm, vm) in parts:
                    sw_ = s_ if s_ >= NPRIMARY else sw
                    add_part(bm, V_, F_, sw_, Mi @ sm, uvl, vmode=vm, jit=0.004)
            me = bpy.data.meshes.new(f"item_{idx:03d}"); bm.to_mesh(me); bm.free()
            for p in me.polygons: p.use_smooth = False
            ob = bpy.data.objects.new(f"item_{idx:03d}", me); bpy.context.scene.collection.objects.link(ob)
            ob.data.materials.append(MAT); STEPS.append(ob)
            if meta is not None:
                meta.append({"name": ob.name, "crate": b, "step": k, "shape": rc["shape"], "swatches": sorted(set(rc["sw"])),
                             "mound": rc["mound"], "items": n})
            idx += 1

# ---------- scene ----------
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
atlas = build_atlas()
MAT = bpy.data.materials.new("rootbin"); MAT.use_nodes = True
nt = MAT.node_tree; bsdf = nt.nodes["Principled BSDF"]
ti = nt.nodes.new("ShaderNodeTexImage"); ti.image = atlas; ti.interpolation = "Closest"
nt.links.new(ti.outputs["Color"], bsdf.inputs["Base Color"])
bsdf.inputs["Roughness"].default_value = 0.8
FILLS = (0.1, 0.5, 1.0)
def tris(obs): return sum(len(p.vertices) - 2 for o in obs for p in o.data.polygons)

def join(obs, name):
    bpy.ops.object.select_all(action="DESELECT")
    for o in obs: o.select_set(True)
    bpy.context.view_layer.objects.active = obs[0]
    bpy.ops.object.join(); ob = bpy.context.active_object; ob.name = name
    return ob

def inside_any(bvhs, p):
    d = Vector((0.267, 0.534, 0.802)).normalized()
    for bvh in bvhs:
        o = p.copy(); n = 0
        while True:
            hit = bvh.ray_cast(o, d)
            if hit[0] is None: break
            n += 1; o = hit[0] + d * 1e-4
        if n % 2 == 1: return True
    return False

def clip_check():
    bvhs = [BVHTree.FromPolygons([v.co.copy() for v in o.data.vertices], [tuple(p.vertices) for p in o.data.polygons])
            for o in PARTS]
    bad_obj, bad_v, total_v = [], 0, 0
    for ob in STEPS:
        b = int(ob.name.split("_")[1]) // 4
        bx = BAYS[b]; hit = 0
        for v in ob.data.vertices:
            p = v.co; total_v += 1
            out = abs(p.x - bx) > HALF_W or abs(p.y) > IN_Y or p.z < FLOOR - 0.012
            if out or inside_any(bvhs, p):
                hit += 1; print("  clip vert", ob.name, tuple(round(c, 3) for c in p), "out" if out else "inside frame part")
        if hit: bad_obj.append(ob.name); bad_v += hit
    print("CLIPPING", len(bad_obj), "of", len(STEPS), f"(verts {bad_v} of {total_v})", bad_obj)
    return len(bad_obj)

SPACING = 2.9
bins = []
for k, fill in enumerate(reversed(FILLS)):
    rng.seed(7); PARTS.clear(); STEPS.clear()
    meta = [] if k == 0 else None
    build_frame(); build_contents(meta)
    if k == 0:
        nclip = clip_check()
        stats = {"frame_tris": tris(PARTS), "step_objects": len(STEPS), "items_tris": tris(STEPS),
                 "clipping": nclip,
                 "mapping_note": ("shape = hash(prefab name) among the bin's shapes; colour = nearest primary swatch cell (0-11) in Lab "
                                  "to the mean colour of the item's inventory icon (opaque, saturated pixels). The mod rewrites u of every "
                                  "vertex whose u lies in a primary cell to the chosen cell; accent cells 12-15 stay. Each step object is "
                                  "one item type in one crate; crate = k-th most numerous stored item, steps = its share of the crate."), "primary_swatch_cells": list(range(NPRIMARY)),
                 "swatches": [{"cell": i, "name": s[0]} for i, s in enumerate(SWATCH)], "steps": meta}
        for obs, fn in ((PARTS, "RootBin.obj"), (STEPS, "RootBinItems.obj")):
            bpy.ops.object.select_all(action="DESELECT")
            for o in obs: o.select_set(True)
            bpy.ops.wm.obj_export(filepath=os.path.join(OUTA, fn), export_selected_objects=True, export_materials=False,
                                  export_triangulated_mesh=True, forward_axis="NEGATIVE_Z", up_axis="Y")
        json.dump(stats, open(os.path.join(OUTA, "rootbin.json"), "w"), indent=1)
        print("ROOTBIN", {k_: v for k_, v in stats.items() if k_ not in ("steps", "swatches")})
    shown = STEPS[:round(fill * len(STEPS))]
    for o in STEPS[len(shown):]: bpy.data.objects.remove(o, do_unlink=True)
    ob = join(PARTS + shown, f"rootbin_{int(fill * 100)}")
    ob.location.x = (len(FILLS) - 1 - k) * SPACING - SPACING
    bins.append(ob)

# vanilla wood chest beside it, for scale and palette (reference only, never exported)
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
        q = node["rot"]; from mathutils import Quaternion
        M = Matrix.Translation(Vector(node["pos"])) @ Quaternion((q[3], q[0], q[1], q[2])).to_matrix().to_4x4() \
            @ Matrix.Diagonal((*node["scale"], 1))
        verts = [M @ v for v in V]
        verts = [Vector((-v.x - 5.4, -v.z, v.y)) for v in verts]
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
bpy.ops.mesh.primitive_plane_add(size=30)
gm = bpy.data.materials.new("ground"); gm.use_nodes = True
gm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.16, 0.14, 0.11, 1)
bpy.context.active_object.data.materials.append(gm)
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam); sc.camera = cam
sc.render.engine = "BLENDER_EEVEE_NEXT"
sc.render.resolution_x, sc.render.resolution_y = 1600, 900
sc.view_settings.view_transform = "Standard"
VIEWS = {"fills": (-6, 25, 15.4, (-1.4, 0, 0.45)), "close": (-20, 33, 4.3, (SPACING, 0, 0.55)),
         "alt": (52, 36, 4.6, (SPACING, 0, 0.55))}
for vn, (yaw, pitch, dist, tgt) in VIEWS.items():
    t = Vector(tgt)
    d = Vector((math.cos(math.radians(pitch)) * math.sin(math.radians(yaw)),
                -math.cos(math.radians(pitch)) * math.cos(math.radians(yaw)), math.sin(math.radians(pitch))))
    cam.location = t + d * dist; cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    sc.render.filepath = os.path.join(OUT, f"{TAG}-{vn}.png")
    bpy.ops.render.render(write_still=True)
print("DONE")
