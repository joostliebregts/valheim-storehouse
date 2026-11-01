"""Larder Hutch, our own mesh and our own texture (no vanilla geometry or texture in it).
Run: blender -b -P larder.py -- [--out DIR] [--no-ref]
Writes assets/larder/{LarderFrame.obj, LarderItems.obj, larder_atlas.png, larder.json} and renders previews.

A tall open cupboard: plank back, closed base with two doors, three open shelves, carved top board, a cloth draped
over the front of the top board. The contents are single food objects (bowl, plate with roast, loaf, pie, crock,
skewer) in fill order: shelf by shelf from the bottom, each shelf from the middle out, front row before back row.

Atlas 128x128, point filtered, horizontal strips (v from the bottom):
  v 0.750-1.000 hewn timber side grain (32 px)     v 0.625-0.750 end grain, 8 tiles of 16x16
  v 0.500-0.625 cloth, red hem at the bottom       v 0.375-0.500 FOOD swatches, 16 cells of 8x16
  v 0.250-0.375 WARE (bowl, plate, pot) swatches, 16 cells of 8x16      v 0.000-0.250 iron (32 px)
A content piece picks a swatch by shifting its u by cell/16, so the mod can recolour one mesh per item.
"""
import bpy, bmesh, sys, os, math, json, random
import numpy as np
from mathutils import Vector, Matrix, Euler
from mathutils.bvhtree import BVHTree

SLUG = "larder"
HERE = os.path.dirname(os.path.abspath(__file__))
OUTA = os.path.normpath(os.path.join(HERE, "..", "assets", SLUG))
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = argv[argv.index("--out") + 1] if "--out" in argv else OUTA
TAG = SLUG
RIP = "C:/Users/joost/ValheimRip/chests/piece_chest_wood"
os.makedirs(OUTA, exist_ok=True); os.makedirs(OUT, exist_ok=True)
rng = random.Random(7)

TEX = 128
DENS = 48.0                      # px per metre, vanilla wood is 47-57
STRIP = {"hewn": 0.75, "end": 0.625, "cloth": 0.5, "food": 0.375, "ware": 0.25, "iron": 0.0}

def srgb(c): return np.array(c, dtype=np.float32)
WOOD, WOOD_D = srgb((0.38, 0.29, 0.18)), srgb((0.21, 0.16, 0.10))
END, END_D = srgb((0.55, 0.45, 0.31)), srgb((0.35, 0.27, 0.17))
IRON, IRON_D = srgb((0.22, 0.21, 0.20)), srgb((0.09, 0.09, 0.09))
LINEN, LINEN_D = srgb((0.52, 0.46, 0.34)), srgb((0.38, 0.32, 0.23))
HEM, STRIPE = srgb((0.40, 0.18, 0.13)), srgb((0.26, 0.31, 0.36))

# 16 food colours, muted, small accents allowed on contents
FOOD = [("stew brown", (0.34, 0.20, 0.10)), ("tomato red", (0.52, 0.20, 0.12)), ("carrot orange", (0.62, 0.36, 0.12)),
        ("bread crust", (0.60, 0.42, 0.20)), ("herb green", (0.30, 0.40, 0.15)), ("cream", (0.72, 0.64, 0.45)),
        ("roast brown", (0.40, 0.22, 0.12)), ("pale fish", (0.68, 0.45, 0.35)), ("berry", (0.35, 0.15, 0.25)),
        ("mushroom", (0.45, 0.38, 0.30)), ("pie gold", (0.66, 0.50, 0.28)), ("blood red", (0.45, 0.10, 0.10)),
        ("honey", (0.72, 0.55, 0.15)), ("char", (0.15, 0.10, 0.07)), ("blue", (0.30, 0.38, 0.45)),
        ("turnip", (0.70, 0.60, 0.58))]
WARE = [("birch", (0.58, 0.47, 0.32)), ("oak", (0.38, 0.29, 0.18)), ("dark oak", (0.24, 0.17, 0.11)),
        ("ash grey", (0.45, 0.40, 0.34)), ("red clay", (0.46, 0.24, 0.16)), ("cream ceramic", (0.62, 0.56, 0.45)),
        ("grey clay", (0.38, 0.36, 0.33)), ("blue glaze", (0.25, 0.32, 0.38)), ("pewter", (0.45, 0.45, 0.44)),
        ("black iron", (0.20, 0.20, 0.20)), ("sand", (0.52, 0.45, 0.34)), ("moss glaze", (0.28, 0.34, 0.22)),
        ("ochre clay", (0.55, 0.38, 0.18)), ("walnut", (0.30, 0.22, 0.15)), ("bone", (0.66, 0.60, 0.50)),
        ("rust", (0.40, 0.22, 0.14))]

def build_atlas():
    nr = np.random.default_rng(3)
    img = np.zeros((TEX, TEX, 3), np.float32)          # row 0 = v 0 (bottom)
    x = np.arange(TEX)[None, :].repeat(32, 0).astype(np.float32)
    y = np.arange(32)[:, None].repeat(TEX, 1).astype(np.float32)
    tile = lambda k: 2 * math.pi * k / TEX
    g = np.sin(y * 1.25 + 1.6 * np.sin(x * tile(2) + y * 0.15) + 0.7 * np.sin(x * tile(5)))
    t = np.clip((g - 0.55) * 2.5, 0, 1) * 0.65 + nr.random((32, TEX)) * 0.18
    t += np.clip(1 - np.minimum(y, 31 - y) / 3.0, 0, 1) * 0.35
    img[96:128] = WOOD * (1 - t[..., None]) + WOOD_D * t[..., None]
    # end grain: eight 16x16 ring tiles
    for k in range(8):
        cx, cy = 7.5 + nr.uniform(-1.2, 1.2), 7.5 + nr.uniform(-1.2, 1.2)
        xx, yy = np.meshgrid(np.arange(16), np.arange(16))
        d = np.hypot(xx - cx, yy - cy) + 0.5 * np.sin(np.arctan2(yy - cy, xx - cx) * 3 + k)
        t = (np.sin(d * 1.8) * 0.5 + 0.5) * 0.45 + nr.random((16, 16)) * 0.15
        t = np.where(d > 7.0, 0.9, t)
        img[80:96, 16 * k:16 * k + 16] = END * (1 - t[..., None]) + END_D * t[..., None]
    # cloth: linen weave, a dull red hem (rows 0-3), thin blue pin stripe (row 9)
    xc = np.arange(TEX)[None, :].repeat(16, 0); yc = np.arange(16)[:, None].repeat(TEX, 1)
    t = 0.12 * ((xc + yc) % 2) + 0.10 * (((xc // 3) + (yc // 3)) % 2) + nr.random((16, TEX)) * 0.16
    c = LINEN * (1 - t[..., None]) + LINEN_D * t[..., None]
    c[0:4] = HEM * (1 - t[0:4, :, None] * 0.6) + 0.0
    c[4] = LINEN_D * 0.55
    c[9] = STRIPE * (1 - t[9, :, None] * 0.5)
    img[64:80] = c
    # swatches: 8x16 cell, dark at the bottom (down-facing) to light at the top, speckle
    def swatches(pal, y0, wood):
        for k, (_, col) in enumerate(pal):
            yy = np.arange(16)[:, None].repeat(8, 1).astype(np.float32)
            lum = 0.62 + 0.52 * (yy / 15.0) + (nr.random((16, 8)) - 0.5) * 0.14
            if wood and k < 4: lum += 0.05 * np.sin(yy * 2.2)
            img[y0:y0 + 16, 8 * k:8 * k + 8] = np.clip(srgb(col) * lum[..., None], 0, 1)
    swatches(FOOD, 48, False); swatches(WARE, 32, True)
    # iron
    t = nr.random((32, TEX)) * 0.4 + np.clip(1 - np.minimum(y, 31 - y) / 4.0, 0, 1) * 0.5
    img[0:32] = IRON * (1 - t[..., None]) + IRON_D * t[..., None]
    im = bpy.data.images.new("larder_atlas", TEX, TEX, alpha=False)
    px = np.concatenate([np.clip(img, 0, 1), np.ones((TEX, TEX, 1), np.float32)], 2)
    im.pixels.foreach_set(px.ravel())
    im.filepath_raw = os.path.join(OUTA, "larder_atlas.png"); im.file_format = "PNG"; im.save()
    return im

# ---------- geometry helpers ----------
PARTS, ITEMS = [], []

def make_obj(bm, name, target):
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = False
    ob = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(ob)
    ob.data.materials.append(MAT); target.append(ob)
    return ob

def uv_face(f, UV, kind, long_axis, seed):
    n = f.normal
    ax = max(range(3), key=lambda i: abs(n[i]))
    tang = [i for i in range(3) if i != ax]
    if kind != "iron" and ax == long_axis:                      # cut end of a timber
        k = seed % 8
        cs = [l.vert.co for l in f.loops]
        c = sum(cs, Vector()) / len(cs)
        ext = max(max(abs(v[tang[0]] - c[tang[0]]), abs(v[tang[1]] - c[tang[1]])) for v in cs) or 1
        for l in f.loops:
            a = (l.vert.co[tang[0]] - c[tang[0]]) / ext; b = (l.vert.co[tang[1]] - c[tang[1]]) / ext
            l[UV].uv = ((k + 0.5 + a * 0.45) / 8, STRIP["end"] + (0.5 + b * 0.45) * 0.125)
        return
    ua = long_axis if long_axis in tang else tang[0]
    va = tang[1] if ua == tang[0] else tang[0]
    off = (seed * 0.37) % 1
    vs = [l.vert.co[va] for l in f.loops]
    vmin, span = min(vs), max(max(vs) - min(vs), 1e-4)
    vscale = min(1.0, (32 / DENS) / span)
    base = STRIP[kind]
    for l in f.loops:
        u = l.vert.co[ua] * DENS / TEX + off
        v = base + ((l.vert.co[va] - vmin) * vscale * DENS / TEX) * 0.94 + 0.0075
        l[UV].uv = (u, v)

def finish_xf(bm, pos, rot):
    bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Euler([math.radians(a) for a in rot]).to_matrix())
    bmesh.ops.translate(bm, verts=bm.verts, vec=Vector(pos))

def timber(name, size, pos, kind="hewn", rot=(0, 0, 0), jitter=0.012, bevel=0.012, jz=None, taper=1.0):
    """Hewn box (or iron strap): size along x,y,z; long axis = largest. jz = z jitter (None = same as jitter)."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts: v.co = Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2]))
    la = max(range(3), key=lambda i: size[i])
    for v in bm.verts:
        for i in range(3):
            if i != la: v.co[i] += rng.uniform(-1, 1) * (jz if (i == 2 and jz is not None) else jitter)
    if taper != 1.0:
        for v in bm.verts:
            if v.co.z > 0: v.co.x *= taper; v.co.y *= taper
    if bevel > 0: bmesh.ops.bevel(bm, geom=bm.edges[:], offset=bevel, segments=1, affect="EDGES")
    bm.normal_update()
    UV = bm.loops.layers.uv.verify()
    seed = rng.randrange(1000)
    for f in bm.faces: uv_face(f, UV, kind, la, seed + f.index % 2)
    finish_xf(bm, pos, rot)
    return make_obj(bm, name, PARTS)

# ---------- the hutch ----------
SHELVES = (0.45, 0.95, 1.45)           # shelf top heights
FRONT_Y, BACK_Y, SIDE_X = -0.23, 0.25, 0.60     # inner limits of the shelf bays

def build_cloth():
    path = [(0.06, 2.014), (-0.28, 2.014), (-0.335, 1.99), (-0.35, 1.93), (-0.355, 1.84), (-0.35, 1.75)]
    nr, nc = len(path), 9
    x0, x1 = -0.62, 0.08
    # outward normals per path vertex
    segn = []
    for i in range(nr - 1):
        dy, dz = path[i + 1][0] - path[i][0], path[i + 1][1] - path[i][1]
        L = math.hypot(dy, dz); segn.append((dz / L, -dy / L))
    nrm = []
    for i in range(nr):
        a = segn[max(i - 1, 0)]; b = segn[min(i, nr - 2)]
        m = (a[0] + b[0], a[1] + b[1]); l = math.hypot(*m); nrm.append((m[0] / l, m[1] / l))
    s_at = [0.0] * nr                                   # path length from the hem upwards
    for i in range(nr - 2, -1, -1):
        s_at[i] = s_at[i + 1] + math.hypot(path[i + 1][0] - path[i][0], path[i + 1][1] - path[i][1])
    bm = bmesh.new(); uvinfo = {}
    grid = {}
    for layer, off in (("o", 0.006), ("i", -0.006)):
        for i in range(nr):
            for j in range(nc):
                x = x0 + (x1 - x0) * j / (nc - 1)
                fold = (math.sin(j * 1.35 + 0.6) * 0.5 + 0.5) * 0.014 * (max(i - 1, 0) / 4.0)
                y, z = path[i]
                n = nrm[i]
                if i == nr - 1: z -= 0.035 * (math.sin(j * 2.1 + 1.0) * 0.5 + 0.5)
                px = x + rng.uniform(-0.004, 0.004)
                v = bm.verts.new((px, y + n[0] * (off + fold), z + n[1] * (off + fold)))
                grid[(layer, i, j)] = v; uvinfo[v] = (x, s_at[i])
    def quad(a, b, c, d):
        try: bm.faces.new((a, b, c, d))
        except ValueError: pass
    for lay in ("o", "i"):
        for i in range(nr - 1):
            for j in range(nc - 1):
                quad(grid[(lay, i, j)], grid[(lay, i, j + 1)], grid[(lay, i + 1, j + 1)], grid[(lay, i + 1, j)])
    for i in range(nr - 1):      # close the two side edges
        for j in (0, nc - 1):
            quad(grid[("o", i, j)], grid[("o", i + 1, j)], grid[("i", i + 1, j)], grid[("i", i, j)])
    for j in range(nc - 1):      # close top and hem edges
        for i in (0, nr - 1):
            quad(grid[("o", i, j)], grid[("o", i, j + 1)], grid[("i", i, j + 1)], grid[("i", i, j)])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    UV = bm.loops.layers.uv.verify()
    for f in bm.faces:
        for l in f.loops:
            x, s = uvinfo[l.vert]
            l[UV].uv = (x * DENS / TEX, STRIP["cloth"] + 0.004 + min(s * DENS, 14.2) / TEX)
    make_obj(bm, "cloth", PARTS)

def build_frame():
    for sx in (-1, 1):
        for sy in (-1, 1):
            timber("foot", (0.13, 0.13, 0.14), (sx * 0.65, sy * 0.25, 0.07), jitter=0.008)
            timber("post", (0.1, 0.1, 1.78), (sx * 0.65, sy * 0.25, 1.01), jitter=0.008,
                   rot=(rng.uniform(-.4, .4), rng.uniform(-.4, .4), 0))
    # plank back + two ledgers
    for i in range(7):
        timber("back", (0.192, 0.035, 1.76), (-0.54 + i * 0.18, 0.27 + 0.005 * (i % 2), 1.0), jitter=0.004, bevel=0.01,
               rot=(rng.uniform(-.4, .4), 0, rng.uniform(-.7, .7)))
    for z in (0.52, 1.5):
        timber("ledger", (1.3, 0.03, 0.09), (0, 0.303, z), jitter=0.004, bevel=0.008)
    # sides: base panel, rails under shelves 2 and 3, a rail under the crown
    for sx in (-1, 1):
        x = sx * 0.655
        timber("sidebase", (0.035, 0.46, 0.27), (x, 0, 0.265), jitter=0.004, bevel=0.008)
        for z, h in ((SHELVES[1] - 0.09, 0.11), (SHELVES[2] - 0.09, 0.11), (1.82, 0.1)):
            timber("siderail", (0.035, 0.46, h), (x, 0, z), jitter=0.004, bevel=0.008)
    # shelves with a low lip at the front
    for top in SHELVES:
        timber("shelf", (1.24, 0.52, 0.05), (0, 0, top - 0.025), jitter=0.008, jz=0.0, bevel=0.01)
        timber("lip", (1.2, 0.03, 0.05), (0, -0.245, top + 0.025), jitter=0.003, jz=0.0, bevel=0.006)
    # closed base: two plank doors, iron straps, handles
    for sx in (-1, 1):
        timber("door", (0.585, 0.035, 0.275), (sx * 0.298, -0.272, 0.265), jitter=0.005, bevel=0.01)
        for z in (0.2, 0.33):
            timber("strap", (0.34, 0.014, 0.04), (sx * 0.33, -0.297, z), kind="iron", jitter=0.002, bevel=0)
        timber("handle", (0.035, 0.03, 0.06), (sx * 0.045, -0.298, 0.265), kind="iron", jitter=0.002, bevel=0)
    # carved top: frieze with teeth, two crown boards, small horns
    timber("frieze", (1.24, 0.04, 0.12), (0, -0.298, 1.84), jitter=0.004, bevel=0.01)
    for i in range(9):
        timber("tooth", (0.08, 0.03, 0.05 + 0.02 * (i % 2)), (-0.56 + i * 0.14, -0.305, 1.775 - 0.01 * (i % 2)),
               jitter=0.004, bevel=0, rot=(0, 0, rng.uniform(-2, 2)))
    timber("crown", (1.56, 0.66, 0.06), (0, 0, 1.93), jitter=0.004, jz=0.002, bevel=0.012)
    timber("crown", (1.48, 0.58, 0.04), (0, 0, 1.98), jitter=0.004, jz=0.002, bevel=0.008)
    for sx in (-1, 1):
        timber("horn", (0.06, 0.06, 0.16), (sx * 0.69, -0.2, 2.07), jitter=0.003, bevel=0.007, rot=(0, sx * 12, 0), taper=0.45)
    build_cloth()

# ---------- contents ----------
def painted(bm, row, cell):
    UV = bm.loops.layers.uv.verify()
    for f in bm.faces:
        up = f.normal.z * 0.5 + 0.5
        u = (cell + 0.5 + rng.uniform(-0.3, 0.3)) / 16
        v = STRIP[row] + (0.18 + 0.64 * up) * 0.125
        for l in f.loops: l[UV].uv = (u, v)

def frustum(r1, r2, h, z0=0.0, sides=8, cap=True, wob=0.004, bottom=False):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=cap, cap_tris=False, segments=sides, radius1=r1, radius2=r2, depth=h)
    if cap and not bottom:       # the underside is never seen: no bottom face
        bm.normal_update()
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.normal.z < -0.9], context="FACES_ONLY")
    for v in bm.verts:
        v.co.x += rng.uniform(-wob, wob); v.co.y += rng.uniform(-wob, wob); v.co.z += z0 + h / 2
    return bm

def box(size, pos=(0, 0, 0), rot=(0, 0, 0), wob=0.003):
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * size[0] + rng.uniform(-wob, wob), v.co.y * size[1] + rng.uniform(-wob, wob),
                       v.co.z * size[2] + rng.uniform(-wob, wob)))
    finish_xf(bm, pos, rot)
    return bm

def blob(size, pos=(0, 0, 0), rot=(0, 0, 0), wob=0.1):
    bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=6, v_segments=4, radius=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * size[0] * (1 + rng.uniform(-wob, wob)), v.co.y * size[1] * (1 + rng.uniform(-wob, wob)),
                       v.co.z * size[2] * (1 + rng.uniform(-wob, wob))))
    finish_xf(bm, pos, rot)
    return bm

# each shape returns [(bmesh, row, which)] in item space, base at z=0; which: "w" ware, "f" food, "a" accent
def s_bowl():
    h = 0.07
    return [(frustum(0.062, 0.098, h), "ware", "w"), (frustum(0.088, 0.066, 0.034, z0=h - 0.006), "food", "f"),
            (box((0.034, 0.032, 0.024), (0.02, 0.012, h + 0.03), (rng.uniform(-9, 9), rng.uniform(-9, 9), rng.uniform(0, 60))), "food", "a"),
            (box((0.024, 0.026, 0.018), (-0.026, -0.014, h + 0.026), (0, rng.uniform(-9, 9), rng.uniform(0, 60))), "food", "f")]

def s_plate():
    return [(frustum(0.075, 0.115, 0.022), "ware", "w"), (blob((0.075, 0.05, 0.036), (-0.005, 0, 0.048)), "food", "f"),
            (box((0.07, 0.014, 0.014), (0.085, 0.0, 0.052), (0, -14, 10)), "food", "a")]

def s_loaf():
    return [(box((0.2, 0.12, 0.016), (0, 0, 0.008), wob=0.002), "ware", "w"), (blob((0.088, 0.046, 0.042), (0, 0, 0.05)), "food", "f"),
            (box((0.012, 0.046, 0.01), (-0.028, 0, 0.088), (0, 0, 14)), "food", "a"),
            (box((0.012, 0.046, 0.01), (0.03, 0, 0.088), (0, 0, 14)), "food", "a")]

def s_pie():
    return [(frustum(0.07, 0.098, 0.034), "ware", "w"), (frustum(0.098, 0.082, 0.03, z0=0.034), "food", "f"),
            (box((0.16, 0.014, 0.01), (0, 0, 0.068), (0, 0, 45)), "food", "a"),
            (box((0.16, 0.014, 0.01), (0, 0, 0.068), (0, 0, -45)), "food", "a")]

def s_crock():
    return [(frustum(0.058, 0.082, 0.09, cap=False), "ware", "w"), (frustum(0.082, 0.06, 0.07, z0=0.09), "ware", "w"),
            (frustum(0.066, 0.046, 0.028, z0=0.158), "food", "f"), (box((0.03, 0.03, 0.02), (0, 0, 0.196), (0, 0, 20)), "food", "a")]

def s_skewer():
    return [(box((0.25, 0.08, 0.022), (0, 0, 0.011), wob=0.002), "ware", "w"), (box((0.31, 0.011, 0.011), (0, 0, 0.05), wob=0.001), "ware", "w2"),
            (box((0.056, 0.05, 0.05), (-0.082, 0, 0.05), (rng.uniform(-12, 12), 0, rng.uniform(0, 40))), "food", "f"),
            (box((0.056, 0.05, 0.05), (0.0, 0, 0.05), (rng.uniform(-12, 12), 0, rng.uniform(0, 40))), "food", "a"),
            (box((0.056, 0.05, 0.05), (0.082, 0, 0.05), (rng.uniform(-12, 12), 0, rng.uniform(0, 40))), "food", "f")]

SCALE = {"bowl": 1.15, "plate": 1.1, "loaf": 1.15, "pie": 1.12, "crock": 1.05, "skewer": 1.08}
SHAPES = {"bowl": s_bowl, "plate": s_plate, "loaf": s_loaf, "pie": s_pie, "crock": s_crock, "skewer": s_skewer}

# (shape, ware cell, food cell, accent cell). Slots per shelf, in fill order:
#  front mid-left, front mid-right, front outer-left, front outer-right, back left, back mid, back right
SPECS = [
    # shelf 1
    ("bowl", 1, 0, 4), ("pie", 6, 10, 3), ("plate", 0, 6, 4), ("skewer", 3, 11, 9), ("crock", 4, 12, 3), ("bowl", 5, 5, 8), ("loaf", 2, 3, 6),
    # shelf 2
    ("bowl", 2, 1, 4), ("loaf", 1, 10, 3), ("plate", 7, 7, 14), ("skewer", 0, 2, 6), ("crock", 5, 8, 5), ("pie", 4, 3, 6), ("bowl", 4, 9, 15),
    # shelf 3
    ("pie", 3, 8, 10), ("plate", 0, 15, 4), ("bowl", 1, 4, 5), ("skewer", 2, 7, 6), ("crock", 8, 14, 14), ("loaf", 0, 3, 10), ("bowl", 6, 0, 12),
]
FRONT_X = (-0.14, 0.14, -0.42, 0.42)   # outer-right is the skewer slot (tray runs along x)
BACK_X = (-0.28, 0.28, 0.0)
SLOT_XY = [(x, -0.095) for x in FRONT_X] + [(BACK_X[0], 0.12), (BACK_X[2], 0.12), (BACK_X[1], 0.12)]

def build_items(n_items):
    for k in range(n_items):
        shelf, slot = divmod(k, 7)
        shape, w, f, a = SPECS[k]
        parts = []
        yaw = rng.uniform(-5, 5) if shape == "skewer" else rng.uniform(-14, 14)
        x, y = SLOT_XY[slot]
        pos = (x + rng.uniform(-0.01, 0.01), y + rng.uniform(-0.01, 0.01), SHELVES[shelf] + 0.003)
        cells = {"w": w, "f": f, "a": a, "w2": (w + 1) % 8 if w != 2 else 9}
        for bm, row, which in SHAPES[shape]():
            bmesh.ops.scale(bm, vec=(SCALE[shape],) * 3, verts=bm.verts)
            bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Euler((0, 0, math.radians(yaw))).to_matrix())
            bmesh.ops.translate(bm, verts=bm.verts, vec=Vector(pos))
            bm.normal_update()
            painted(bm, row, cells[which])
            make_obj(bm, f"p{k}", parts)
        ITEMS.append((join(parts, f"item_{k:03d}"), shelf))

# ---------- scene ----------
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
atlas = build_atlas()
MAT = bpy.data.materials.new("larder"); MAT.use_nodes = True
nt = MAT.node_tree; bsdf = nt.nodes["Principled BSDF"]
ti = nt.nodes.new("ShaderNodeTexImage"); ti.image = atlas; ti.interpolation = "Closest"
nt.links.new(ti.outputs["Color"], bsdf.inputs["Base Color"])
bsdf.inputs["Roughness"].default_value = 0.8
FILLS = (0.1, 0.5, 1.0)
SPACING = 2.4
def tris(obs): return sum(len(p.vertices) - 2 for o in obs for p in o.data.polygons)

def join(obs, name):
    bpy.ops.object.select_all(action="DESELECT")
    for o in obs: o.select_set(True)
    bpy.context.view_layer.objects.active = obs[0]
    bpy.ops.object.join(); ob = bpy.context.active_object; ob.name = name; ob.data.name = name
    return ob

def bvh(obs):
    V, P = [], []
    for o in obs:
        base = len(V); V += [v.co.copy() for v in o.data.vertices]
        P += [[base + i for i in p.vertices] for p in o.data.polygons]
    return BVHTree.FromPolygons(V, P, all_triangles=False)

N_ITEMS = int(argv[argv.index("--items") + 1]) if "--items" in argv else len(SPECS)
rects = []
copies = []
for k, fill in enumerate(reversed(FILLS)):
    rng.seed(7); PARTS.clear(); ITEMS.clear()
    build_frame(); build_items(N_ITEMS)
    obs = [o for o, _ in ITEMS]
    if k == 0:
        # clip check: slab limits of each shelf bay, plus real triangle overlap with the frame and between items
        ftree = bvh(PARTS); trees = [bvh([o]) for o in obs]
        bad = set()
        for i, (o, sh) in enumerate(ITEMS):
            top = SHELVES[sh]
            ceil = 1.70 if sh == 2 else SHELVES[sh + 1] - 0.05
            for v in o.data.vertices:
                c = v.co
                if not (-SIDE_X < c.x < SIDE_X and FRONT_Y < c.y < BACK_Y and top - 0.002 <= c.z < ceil - 0.01):
                    bad.add(i); print("  slab", i, SPECS[i][0], tuple(round(a, 3) for a in c)); break
            if ftree.overlap(trees[i]): bad.add(i); print("  frame overlap", i, SPECS[i][0])
        print("CLIPPING", len(bad), "of", len(obs), sorted(bad))
        ov = [(i, j) for i in range(len(obs)) for j in range(i + 1, len(obs)) if trees[i].overlap(trees[j])]
        print("ITEM OVERLAP", len(ov), ov)
        stats = {"frame_tris": tris(PARTS), "item_count": len(obs), "items_tris": tris(obs),
                 "per_item_tris": [tris([o]) for o in obs], "shelves": len(SHELVES), "slots_per_shelf": 7,
                 "specs": [dict(shape=s, ware=w, food=f, accent=a) for s, w, f, a in SPECS[:len(obs)]],
                 "food_swatches": [n for n, _ in FOOD], "ware_swatches": [n for n, _ in WARE],
                 "atlas": {"size": [TEX, TEX], "swatch_cell_px": [8, 16], "food_v0": STRIP["food"], "ware_v0": STRIP["ware"],
                           "note": "item mesh is authored on cell 0 of each row for the colour in its spec; to recolour, shift u by (newcell-oldcell)/16"}}
        for obset, fn in ((PARTS, "LarderFrame.obj"), (obs, "LarderItems.obj")):
            bpy.ops.object.select_all(action="DESELECT")
            for o in obset: o.select_set(True)
            bpy.ops.wm.obj_export(filepath=os.path.join(OUTA, fn), export_selected_objects=True, export_materials=False,
                                  export_triangulated_mesh=True, forward_axis="NEGATIVE_Z", up_axis="Y")
        json.dump(stats, open(os.path.join(OUTA, "larder.json"), "w"), indent=1); print("LARDER", {k: stats[k] for k in ("frame_tris", "item_count", "items_tris")})
    shown = obs[:round(fill * len(obs))]
    for o in obs[len(shown):]: bpy.data.objects.remove(o, do_unlink=True)
    ob = join(PARTS + shown, f"larder_{int(fill * 100)}")
    ob.location.x = (1 - k) * SPACING
    copies.append(ob)

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
        verts = [Vector((-v.x - 4.3, -v.z, v.y)) for v in verts]
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
VIEWS = {"fills": (-6, 12, 12.0, (-0.9, 0, 1.0)), "close": (-22, 10, 6.0, (SPACING, 0, 1.1)),
         "alt": (52, 24, 6.2, (SPACING, 0, 1.1)), "shelves": (-4, 6, 2.6, (SPACING, 0, 0.95))}
for vn, (yaw, pitch, dist, tgt) in VIEWS.items():
    t = Vector(tgt)
    d = Vector((math.cos(math.radians(pitch)) * math.sin(math.radians(yaw)),
                -math.cos(math.radians(pitch)) * math.cos(math.radians(yaw)), math.sin(math.radians(pitch))))
    cam.location = t + d * dist; cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    sc.render.filepath = os.path.join(OUT, f"{TAG}-{vn}.png")
    bpy.ops.render.render(write_still=True)
print("DONE")
