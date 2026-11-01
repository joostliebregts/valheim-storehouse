"""Larder Hutch, round 2: mass storage for cooked meals. Our own furniture mesh + own atlas; the CONTENTS are the game's
own item models (local reference rip, never exported), placed on anchors the mod reads from LarderAnchors.json.
Run: blender -b -P larder_r2.py -- [--out DIR] [--no-ref]
Writes assets/larder_r2/{LarderFrame.obj, LarderAnchors.json, larder_atlas.png} and renders previews.

Hutch: 2.0 m wide, 2.0 m tall (horns included), 0.76 m deep. Closed base with four drawers, five open shelves, carved
crown with a cloth runner. Every shelf holds 14 units (7 across, front row + a raised back row) = 70 units = 70 stacks.
A unit is ONE full stack of ONE item: a nested pile of bowls, a bundle of fish, a pile of loaves, a tray of jars.

Atlas 128x128, point filtered, horizontal strips (v from the bottom):
  v 0.750-1.000 hewn timber side grain (32 px)   v 0.625-0.750 end grain, 8 tiles of 16x16
  v 0.500-0.625 cloth, hem at the bottom         v 0.250-0.500 pale hewn timber (32 px)     v 0.000-0.250 iron (32 px)

Coordinates: Blender z-up, -y front. Unity prefab space (what LarderAnchors.json uses): ux=-bx, uy=bz, uz=-by
(front = +z). Rotations are converted as R_u = C R_b C^T with C = [[-1,0,0],[0,0,1],[0,-1,0]] and decomposed to Unity
Euler order (Ry * Rx * Rz).
"""
import bpy, bmesh, sys, os, math, json, random
import numpy as np
from mathutils import Vector, Matrix, Euler
from mathutils.bvhtree import BVHTree
sys.path.append("C:/Users/joost/ValheimRip/items")
from load_item import load_item

SLUG = "larder"
HERE = os.path.dirname(os.path.abspath(__file__))
OUTA = os.path.normpath(os.path.join(HERE, "..", "assets", SLUG + "_r2"))
SCRATCH = "C:/Users/joost/AppData/Local/Temp/claude/C--Users-joost--pai/5e4bc60b-cdfe-4638-8e29-2e507fa13cf9/scratchpad/proto2/larder"
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = argv[argv.index("--out") + 1] if "--out" in argv else SCRATCH
TAG = SLUG
RIP = "C:/Users/joost/ValheimRip/chests/piece_chest_wood"
ITEMS_DIR = "C:/Users/joost/ValheimRip/items"
os.makedirs(OUTA, exist_ok=True); os.makedirs(OUT, exist_ok=True)
rng = random.Random(7)

TEX = 128
DENS = 48.0
STRIP = {"hewn": 0.75, "end": 0.625, "cloth": 0.5, "pale": 0.25, "iron": 0.0}

def srgb(c): return np.array(c, dtype=np.float32)
WOOD, WOOD_D = srgb((0.38, 0.29, 0.18)), srgb((0.21, 0.16, 0.10))
PALE, PALE_D = srgb((0.46, 0.37, 0.25)), srgb((0.27, 0.20, 0.13))
END, END_D = srgb((0.55, 0.45, 0.31)), srgb((0.35, 0.27, 0.17))
IRON, IRON_D = srgb((0.22, 0.21, 0.20)), srgb((0.09, 0.09, 0.09))
LINEN, LINEN_D = srgb((0.50, 0.45, 0.34)), srgb((0.37, 0.32, 0.24))
HEM, STRIPE = srgb((0.36, 0.20, 0.15)), srgb((0.31, 0.33, 0.34))

def build_atlas():
    nr = np.random.default_rng(3)
    img = np.zeros((TEX, TEX, 3), np.float32)
    x = np.arange(TEX)[None, :].repeat(32, 0).astype(np.float32)
    y = np.arange(32)[:, None].repeat(TEX, 1).astype(np.float32)
    tile = lambda k: 2 * math.pi * k / TEX
    def hewn(c, cd, phase):
        g = np.sin(y * 1.25 + 1.6 * np.sin(x * tile(2) + y * 0.15 + phase) + 0.7 * np.sin(x * tile(5) + phase))
        t = np.clip((g - 0.55) * 2.5, 0, 1) * 0.65 + nr.random((32, TEX)) * 0.18
        t += np.clip(1 - np.minimum(y, 31 - y) / 3.0, 0, 1) * 0.35
        return c * (1 - t[..., None]) + cd * t[..., None]
    img[96:128] = hewn(WOOD, WOOD_D, 0.0)
    img[32:64] = hewn(PALE, PALE_D, 1.7)
    for k in range(8):
        cx, cy = 7.5 + nr.uniform(-1.2, 1.2), 7.5 + nr.uniform(-1.2, 1.2)
        xx, yy = np.meshgrid(np.arange(16), np.arange(16))
        d = np.hypot(xx - cx, yy - cy) + 0.5 * np.sin(np.arctan2(yy - cy, xx - cx) * 3 + k)
        t = (np.sin(d * 1.8) * 0.5 + 0.5) * 0.45 + nr.random((16, 16)) * 0.15
        t = np.where(d > 7.0, 0.9, t)
        img[80:96, 16 * k:16 * k + 16] = END * (1 - t[..., None]) + END_D * t[..., None]
    xc = np.arange(TEX)[None, :].repeat(16, 0); yc = np.arange(16)[:, None].repeat(TEX, 1)
    t = 0.12 * ((xc + yc) % 2) + 0.10 * (((xc // 3) + (yc // 3)) % 2) + nr.random((16, TEX)) * 0.16
    c = LINEN * (1 - t[..., None]) + LINEN_D * t[..., None]
    c[0:4] = HEM * (1 - t[0:4, :, None] * 0.6)
    c[4] = LINEN_D * 0.55
    c[9] = STRIPE * (1 - t[9, :, None] * 0.5)
    img[64:80] = c
    img[48:64] = img[64:80]            # unused strip, keeps the layout tidy
    t = nr.random((32, TEX)) * 0.4 + np.clip(1 - np.minimum(y, 31 - y) / 4.0, 0, 1) * 0.5
    img[0:32] = IRON * (1 - t[..., None]) + IRON_D * t[..., None]
    img[32:48] = img[32:48]
    im = bpy.data.images.new("larder_atlas", TEX, TEX, alpha=False)
    px = np.concatenate([np.clip(img, 0, 1), np.ones((TEX, TEX, 1), np.float32)], 2)
    im.pixels.foreach_set(px.ravel())
    im.filepath_raw = os.path.join(OUTA, "larder_atlas.png"); im.file_format = "PNG"; im.save()
    return im

# ---------- geometry helpers ----------
PARTS = []

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
    if kind != "iron" and ax == long_axis:
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

# ---------- layout constants ----------
SHELVES = (0.42, 0.71, 1.00, 1.29, 1.58)      # shelf top heights, pitch 0.29
BOARD = 0.055
BAY_X, BAY_Y0, BAY_Y1 = 0.90, -0.25, 0.30      # inner limits of the bays
RISER = 0.02                                  # back row stands on a low step
BOXW, BOXD = 0.24, 0.255
BOXH = (0.20, 0.205)                           # front row, back row
COL_X = [(-3 + c) * 0.25 for c in range(7)]
ROW_Y = (-0.1175, 0.1425)
COL_ORDER = [3, 2, 4, 1, 5, 0, 6]              # middle out
CEIL_TOP = 1.85                                # crown underside is 1.86
CEIL = [SHELVES[i + 1] - BOARD for i in range(4)] + [CEIL_TOP]

def build_cloth():
    path = [(0.05, 1.966), (-0.34, 1.966), (-0.388, 1.945), (-0.392, 1.90), (-0.372, 1.866), (-0.352, 1.83)]
    nr, nc = len(path), 9
    x0, x1 = -0.95, -0.28
    segn = []
    for i in range(nr - 1):
        dy, dz = path[i + 1][0] - path[i][0], path[i + 1][1] - path[i][1]
        L = math.hypot(dy, dz); segn.append((dz / L, -dy / L))
    nrm = []
    for i in range(nr):
        a = segn[max(i - 1, 0)]; b = segn[min(i, nr - 2)]
        m = (a[0] + b[0], a[1] + b[1]); l = math.hypot(*m); nrm.append((m[0] / l, m[1] / l))
    s_at = [0.0] * nr
    for i in range(nr - 2, -1, -1):
        s_at[i] = s_at[i + 1] + math.hypot(path[i + 1][0] - path[i][0], path[i + 1][1] - path[i][1])
    bm = bmesh.new(); uvinfo = {}; grid = {}
    for layer, off in (("o", 0.006), ("i", -0.006)):
        for i in range(nr):
            for j in range(nc):
                x = x0 + (x1 - x0) * j / (nc - 1)
                fold = (math.sin(j * 1.35 + 0.6) * 0.5 + 0.5) * 0.012 * (max(i - 1, 0) / 4.0)
                y, z = path[i]; n = nrm[i]
                if i == nr - 1: z -= 0.03 * (math.sin(j * 2.1 + 1.0) * 0.5 + 0.5)
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
    for i in range(nr - 1):
        for j in (0, nc - 1):
            quad(grid[("o", i, j)], grid[("o", i + 1, j)], grid[("i", i + 1, j)], grid[("i", i, j)])
    for j in range(nc - 1):
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
    PX, PY = 0.95, 0.31
    for sx in (-1, 1):
        for sy in (-1, 1):
            timber("foot", (0.12, 0.13, 0.14), (sx * 0.94, sy * PY, 0.07), jitter=0.006)
            timber("post", (0.1, 0.1, 1.78), (sx * PX, sy * PY, 1.01), jitter=0.006,
                   rot=(rng.uniform(-.3, .3), rng.uniform(-.3, .3), 0))
    # plank back, ledgers
    for i in range(11):
        timber("back", (0.19, 0.035, 1.76), (-0.9 + i * 0.18, 0.335 + 0.004 * (i % 2), 1.0), jitter=0.003, bevel=0.01,
               rot=(rng.uniform(-.3, .3), 0, rng.uniform(-.6, .6)))
    for z in (0.5, 1.5):
        timber("ledger", (1.9, 0.03, 0.09), (0, 0.368, z), jitter=0.003, bevel=0.008)
    # sides: base panel, a rail under each shelf, crown rail
    for sx in (-1, 1):
        x = sx * 0.945
        timber("sidebase", (0.035, 0.6, 0.30), (x, 0.0, 0.27), jitter=0.003, bevel=0.008)
        for top in SHELVES[1:]:
            timber("siderail", (0.035, 0.6, 0.1), (x, 0.0, top - BOARD - 0.05), jitter=0.003, bevel=0.008)
        timber("siderail", (0.035, 0.6, 0.1), (x, 0.0, 1.83), jitter=0.003, bevel=0.008)
    # shelves: pale boards, front lip, a low step for the back row
    for top in SHELVES:
        timber("shelf", (1.86, 0.62, BOARD), (0, 0.02, top - BOARD / 2), kind="pale", jitter=0.004, jz=0.0, bevel=0.01)
        timber("lip", (1.80, 0.03, 0.05), (0, -0.265, top + 0.025), kind="pale", jitter=0.002, jz=0.0, bevel=0.006)
        timber("step", (1.80, 0.285, RISER), (0, 0.1575, top + RISER / 2), jitter=0.002, jz=0.0, bevel=0.004)
    # closed base: four drawers, iron pulls and straps
    timber("basefront", (1.86, 0.04, 0.05), (0, -0.30, 0.14), jitter=0.003, bevel=0.008)
    for i in range(4):
        x = -0.69 + i * 0.46
        timber("drawer", (0.445, 0.035, 0.21), (x, -0.30, 0.255), kind="pale", jitter=0.004, jz=0.003, bevel=0.01)
        timber("pull", (0.11, 0.025, 0.035), (x, -0.322, 0.265), kind="iron", jitter=0.002, bevel=0)
        for dx in (-0.17, 0.17):
            timber("strap", (0.035, 0.014, 0.19), (x + dx, -0.3205, 0.255), kind="iron", jitter=0.002, bevel=0)
    # carved crown: frieze, studs, two crown boards, horns
    timber("frieze", (1.86, 0.04, 0.09), (0, -0.318, 1.835), jitter=0.003, bevel=0.01)
    for i in range(9):
        x = -0.1 + i * 0.1
        timber("tooth", (0.07, 0.02, 0.05 + 0.015 * (i % 2)), (x, -0.348, 1.835), jitter=0.003, bevel=0, rot=(0, 0, rng.uniform(-2, 2)))
    timber("crown", (2.0, 0.76, 0.06), (0, 0, 1.89), jitter=0.004, jz=0.002, bevel=0.012)
    timber("crown", (1.92, 0.68, 0.04), (0, 0, 1.94), jitter=0.004, jz=0.002, bevel=0.008)
    for sx in (-1, 1):
        timber("horn", (0.06, 0.06, 0.12), (sx * 0.93, -0.3, 1.94), jitter=0.002, bevel=0.007, rot=(0, sx * 10, 0), taper=0.45)
    build_cloth()

# ---------- items ----------
# kind, cols, rows, layers, pitch_frac (layer pitch as a fraction of the scaled item height), base rotation (deg)
REC = {
    "CarrotSoup":         ("stack", 1, 1, 4, 0.20, (0, 0, 0)),
    "SerpentStew":        ("stack", 1, 1, 6, 0.20, (0, 0, 0)),
    "TurnipStew":         ("stack", 1, 1, 6, 0.20, (0, 0, 0)),
    "MushroomOmelette":   ("stack", 1, 1, 6, 0.35, (0, 0, 0)),
    "LoxPie":             ("stack", 1, 1, 4, 0.30, (0, 0, 0)),
    "BloodPudding":       ("stack", 1, 1, 4, 0.45, (0, 0, 0)),
    "CookedDeerMeat":     ("stack", 1, 1, 4, 0.90, (0, 0, 0)),
    "HoneyGlazedChicken": ("pile", 1, 1, 2, 0.95, (0, 0, 0)),
    "MeatPlatter":        ("pile", 1, 2, 4, 0.95, (0, 0, 0)),
    "Bread":              ("pile", 1, 2, 3, 0.95, (0, 0, 90)),
    "Sausages":           ("bundle", 1, 1, 5, 0.90, (0, 0, 0)),
    "FishCooked":         ("bundle", 3, 1, 2, 0.55, (0, 0, 0)),
    "CookedMeat":         ("bundle", 2, 1, 2, 0.60, (0, 0, 0)),
    "QueensJam":          ("row", 2, 2, 2, 1.00, (0, 0, 0)),
    "FishWraps":          ("row", 2, 1, 3, 0.95, (0, 0, 0)),
    "FishAndBread":       ("row", 2, 2, 1, 1.00, (0, 0, 0)),
}
COUNTS = {"CarrotSoup": 5, "SerpentStew": 5, "TurnipStew": 5, "MushroomOmelette": 4, "LoxPie": 5, "BloodPudding": 4,
          "CookedDeerMeat": 4, "HoneyGlazedChicken": 4, "MeatPlatter": 4, "Bread": 5, "Sausages": 4, "FishCooked": 5,
          "CookedMeat": 5, "QueensJam": 4, "FishWraps": 4, "FishAndBread": 3}
assert sum(COUNTS.values()) == 70

def item_bounds(name):
    info = json.load(open(f"{ITEMS_DIR}/{name}/info.json", encoding="utf-8"))
    mn, mx = Vector(info["bounds_min"]), Vector(info["bounds_max"])
    s = mx - mn
    return s   # local box after load_item(anchor=bottom): x,y in [-s/2, s/2], z in [0, s.z]

def rot_aabb(size, rot_deg):
    R = Euler([math.radians(a) for a in rot_deg]).to_matrix()
    cs = [R @ Vector((sx * size.x / 2, sy * size.y / 2, z * size.z)) for sx in (-1, 1) for sy in (-1, 1) for z in (0, 1)]
    mn = Vector((min(c[i] for c in cs) for i in range(3))); mx = Vector((max(c[i] for c in cs) for i in range(3)))
    return mn, mx

def plan_units():
    """70 units in fill order, with copy layouts. Pure data (no Blender objects)."""
    r2 = random.Random(21)
    names = [n for n, c in COUNTS.items() for _ in range(c)]
    for _ in range(2000):
        r2.shuffle(names)
        ok = True
        for k in range(70):
            row = k % 14 // 7
            prev_in_row = names[k - 1] if (k % 7) else None
            above = names[k - 14] if k >= 14 else None
            # neighbours in the fill order are neighbours on the shelf only roughly (middle out), so also check +-2
            near = [names[k - 1], names[k - 2]] if k % 7 >= 2 else ([names[k - 1]] if k % 7 == 1 else [])
            if names[k] in near or names[k] == above: ok = False; break
        if ok: break
    units = []
    for k in range(70):
        shelf, j = divmod(k, 14); row, ci = divmod(j, 7)
        col = COL_ORDER[ci]
        name = names[k]
        kind, cols, rows, layers, pf, base_rot = REC[name]
        boxh = BOXH[row]
        size = item_bounds(name)
        cw, cd = BOXW / cols * 0.96, BOXD / rows * 0.96
        copies = []
        for l in range(layers):
            for r in range(rows):
                for c in range(cols):
                    jit = r2.uniform(-7, 7) if kind != "bundle" else r2.uniform(-5, 5)
                    rot = (base_rot[0], base_rot[1], base_rot[2] + jit + (180 if r2.random() < 0.5 and kind == "stack" else 0))
                    mn, mx = rot_aabb(size, rot)
                    copies.append(dict(layer=l, row=r, col=c, rot=rot, dims=(mx - mn), aabb=(mn, mx)))
        s = min(min(cw / cp["dims"].x, cd / cp["dims"].y, boxh / (cp["dims"].z * (1 + (layers - 1) * pf))) for cp in copies)
        for cp in copies:
            mn, mx = cp["aabb"]
            # bottom-centre of the unit's box is the origin; cell centres, layers stacked on pitch
            cx = -BOXW / 2 + (cp["col"] + 0.5) * BOXW / cols + r2.uniform(-0.004, 0.004)
            cy = -BOXD / 2 + (cp["row"] + 0.5) * BOXD / rows + r2.uniform(-0.004, 0.004)
            cz = cp["layer"] * pf * cp["dims"].z * s
            cp["offset"] = (cx, cy, cz)
        units.append(dict(index=k, shelf=shelf, rowi=row, col=col, item=name, kind=kind, layers=layers, cols=cols, rows=rows,
                          pf=pf, scale=s, copies=copies, boxh=boxh,
                          origin=(COL_X[col], ROW_Y[row], SHELVES[shelf] + 0.002 + (RISER if row else 0.0))))
    return units

TEMPLATES = {}
def template(name):
    if name not in TEMPLATES:
        objs = load_item(name, location=(0, 0, -50))
        for o in objs: o.hide_render = True; o.hide_set(True)
        TEMPLATES[name] = objs
    return TEMPLATES[name]

def place_unit(u, dx=0.0):
    out = []
    size = item_bounds(u["item"])
    for cp in u["copies"]:
        mn, mx = cp["aabb"]
        ctr = Vector(((mn.x + mx.x) / 2, (mn.y + mx.y) / 2, mn.z)) * u["scale"]
        loc = Vector(u["origin"]) + Vector(cp["offset"]) - ctr + Vector((dx, 0, 0))
        for t in template(u["item"]):
            o = t.copy(); bpy.context.scene.collection.objects.link(o)
            o.hide_render = False; o.hide_set(False)
            o.rotation_euler = tuple(math.radians(a) for a in cp["rot"]); o.scale = (u["scale"],) * 3
            o.location = loc
            out.append(o)
    return out

def world_verts(o):
    M = o.matrix_world
    return [M @ v.co for v in o.data.vertices]

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
SPACING = 2.6
def tris(obs): return sum(len(p.vertices) - 2 for o in obs for p in o.data.polygons)

def join(obs, name):
    bpy.ops.object.select_all(action="DESELECT")
    for o in obs: o.select_set(True)
    bpy.context.view_layer.objects.active = obs[0]
    bpy.ops.object.join(); ob = bpy.context.active_object; ob.name = name; ob.data.name = name
    return ob

def bvh_from(verts, polys): return BVHTree.FromPolygons(verts, polys, all_triangles=False)
def bvh(obs):
    V, P = [], []
    for o in obs:
        base = len(V); V += [v.co.copy() for v in o.data.vertices]
        P += [[base + i for i in p.vertices] for p in o.data.polygons]
    return BVHTree.FromPolygons(V, P, all_triangles=False)

# ---- unity conversion
C = Matrix(((-1, 0, 0), (0, 0, 1), (0, -1, 0)))
def to_unity_vec(v): return [round(-v[0], 4), round(v[2], 4), round(-v[1], 4)]
def to_unity_euler(rot_deg):
    Rb = Euler([math.radians(a) for a in rot_deg]).to_matrix()
    Ru = C @ Rb @ C.transposed()
    sx = max(-1.0, min(1.0, -Ru[1][2]))
    x = math.asin(sx); z = math.atan2(Ru[1][0], Ru[1][1]); y = math.atan2(Ru[0][2], Ru[2][2])
    return [round(math.degrees(a), 2) for a in (x, y, z)]
def unity_euler_matrix(e):   # Ry * Rx * Rz, as Unity composes it
    x, y, z = [math.radians(a) for a in e]
    Rx = Matrix(((1, 0, 0), (0, math.cos(x), -math.sin(x)), (0, math.sin(x), math.cos(x))))
    Ry = Matrix(((math.cos(y), 0, math.sin(y)), (0, 1, 0), (-math.sin(y), 0, math.cos(y))))
    Rz = Matrix(((math.cos(z), -math.sin(z), 0), (math.sin(z), math.cos(z), 0), (0, 0, 1)))
    return Ry @ Rx @ Rz

UNITS = plan_units()
rects = []

for k, fill in enumerate(reversed(FILLS)):
    rng.seed(7); PARTS.clear()
    build_frame()
    n_show = round(fill * len(UNITS))
    dx = (1 - k) * SPACING
    if k == 0:
        # ---- full furniture first: clip check at dx = 0, anchors, export
        placed = {u["index"]: place_unit(u, 0.0) for u in UNITS}
        bpy.context.view_layer.update()
        ftree = bvh(PARTS)
        bad = {}
        item_tris = 0
        for u in UNITS:
            sh, rw = u["shelf"], u["rowi"]
            top = SHELVES[sh]; ceil = CEIL[sh]
            for o in placed[u["index"]]:
                wv = world_verts(o)
                item_tris += sum(len(p.vertices) - 2 for p in o.data.polygons)
                tr = bvh_from(wv, [list(p.vertices) for p in o.data.polygons])
                msg = None
                if any(not (-BAY_X < c.x < BAY_X and BAY_Y0 < c.y < BAY_Y1 and top + 0.0005 <= c.z < ceil - 0.004) for c in wv):
                    c = next(c for c in wv if not (-BAY_X < c.x < BAY_X and BAY_Y0 < c.y < BAY_Y1 and top + 0.0005 <= c.z < ceil - 0.004))
                    print("  slab", u["index"], u["item"], u["rowi"], tuple(round(a, 3) for a in c), "top", top, "ceil", ceil)
                    bad[u["index"]] = "slab"; break
                if ftree.overlap(tr): bad[u["index"]] = "frame"; break
        print("CLIPPING", len(bad), "of", len(UNITS), {k_: v for k_, v in bad.items()})
        # unit boxes must not collide with each other
        bx = []
        for u in UNITS:
            ox, oy, oz = u["origin"]
            bx.append((ox - BOXW / 2, ox + BOXW / 2, oy - BOXD / 2, oy + BOXD / 2, oz, oz + u["boxh"], u["shelf"]))
        bo = [(i, j) for i in range(70) for j in range(i + 1, 70)
              if bx[i][6] == bx[j][6] and bx[i][0] < bx[j][1] and bx[j][0] < bx[i][1] and bx[i][2] < bx[j][3] and bx[j][2] < bx[i][3]
              and bx[i][4] < bx[j][5] and bx[j][4] < bx[i][5]]
        print("BOX OVERLAP", len(bo), bo)
        # items must stay inside their own unit box
        outside = []
        for u in UNITS:
            ox, oy, oz = u["origin"]
            for o in placed[u["index"]]:
                if any(not (ox - BOXW / 2 - 0.004 <= c.x <= ox + BOXW / 2 + 0.004 and oy - BOXD / 2 - 0.004 <= c.y <= oy + BOXD / 2 + 0.004
                            and oz - 0.003 <= c.z <= oz + u["boxh"] + 0.004) for c in world_verts(o)):
                    outside.append(u["index"]); break
        print("ITEM OUTSIDE OWN BOX", len(outside), outside)
        # anchors
        anchors = []
        for u in UNITS:
            ox, oy, oz = u["origin"]
            copies = []
            for cp in u["copies"]:
                copies.append({"layer": cp["layer"], "row": cp["row"], "col": cp["col"],
                               "offset": to_unity_vec(cp["offset"]), "rotation": to_unity_euler(cp["rot"])})
            anchors.append({"index": u["index"], "kind": u["kind"], "shelf": u["shelf"], "row": "back" if u["rowi"] else "front",
                            "position": to_unity_vec((ox, oy, oz)), "rotation": [0.0, 0.0, 0.0],
                            "box_size": [BOXW, u["boxh"], BOXD],
                            "layout": {"cols": u["cols"], "rows": u["rows"], "layers": u["layers"], "pitch_frac": u["pf"]},
                            "example_item": u["item"], "example_scale": round(u["scale"], 4), "copies": copies})
        doc = {"schema": "storehouse-anchors/1", "furniture": "Larder Hutch", "units": len(anchors), "slots_designed_for": len(anchors),
               "stack_per_unit": True,
               "space": {"unity": "prefab space, origin on the floor at the centre of the footprint, +z front, +y up, +x to the "
                                  "furniture's left when seen from the front",
                         "from_blender": "ux=-bx, uy=bz, uz=-by; rotations R_u = C R_b C^T (C=[[-1,0,0],[0,0,1],[0,-1,0]]), "
                                         "Unity Euler order Ry*Rx*Rz"},
               "fill_order": "unit index ascending: shelf by shelf from the bottom; per shelf the front row first, then the back row; "
                             "each row from the middle outwards. k of 70 units visible = k/70 full",
               "position": "unit position = bottom centre of its box. box_size = [x, y, z] in Unity axes",
               "copy_rule": "Each copy has a local offset (bottom centre of the item's rotated bounding box, relative to the unit position) and a "
                            "rotation (Unity euler). To place an arbitrary item: take its mesh bounds, apply the copy rotation, call the result "
                            "dim (x,y,z in Unity axes). uniform scale = min(cell_x/dim.x, cell_z/dim.z, box_y/(dim.y*(1+(layers-1)*pitch_frac))) "
                            "with cell_x = box_x/cols*0.96 and cell_z = box_z/rows*0.96. Use the given offset.x and offset.z; offset.y = "
                            "layer*pitch_frac*dim.y*scale (the given offset.y is that value for example_item). example_scale is the rule's result "
                            "for example_item. Items are rest-on-shelf (bottom of rotated bounds at offset.y).",
               "units_data": anchors}
        json.dump(doc, open(os.path.join(OUTA, "LarderAnchors.json"), "w"), indent=1)
        stats = {"frame_tris": tris(PARTS), "units": len(UNITS), "item_tris_at_100": item_tris}
        print("LARDER", stats)
        # exact check of the unity euler conversion on a few copies
        err = 0.0
        for u in UNITS[:20]:
            for cp in u["copies"][:2]:
                Rb = Euler([math.radians(a) for a in cp["rot"]]).to_matrix()
                Ru = unity_euler_matrix(to_unity_euler(cp["rot"]))
                v = Vector((0.3, 0.5, 0.7)); err = max(err, ((Ru @ (C @ v)) - (C @ (Rb @ v))).length)
        print("EULER CHECK max err", round(err, 4))
        # frame export
        bpy.ops.object.select_all(action="DESELECT")
        for o in PARTS: o.select_set(True)
        bpy.ops.wm.obj_export(filepath=os.path.join(OUTA, "LarderFrame.obj"), export_selected_objects=True, export_materials=False,
                              export_triangulated_mesh=True, forward_axis="NEGATIVE_Z", up_axis="Y")
        shown = {u["index"] for u in UNITS}
        for o in sum(placed.values(), []): o.location.x += dx
    else:
        for u in UNITS[:n_show]: place_unit(u, dx)
    ob = join(PARTS, f"larder_{int(fill * 100)}")
    ob.location.x = dx
    rects.append(ob)

# reference: 1.8 m plain post and the vanilla wood chest (local rip, reference only)
post = timber("post180", (0.12, 0.12, 1.8), (SPACING + 1.35, -0.1, 0.9), jitter=0.0, bevel=0.01)
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
        verts = [Vector((-v.x + SPACING + 2.3, -v.z - 0.1, v.y)) for v in verts]
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
VIEWS = {"fills": (-3, 6, 13.6, (0.75, 0, 1.0)), "close": (-14, 8, 5.6, (SPACING, 0, 1.05)),
         "alt": (46, 18, 6.2, (SPACING, 0, 1.0)), "shelf": (-6, 4, 3.4, (SPACING, 0, 0.8))}
only = argv[argv.index("--views") + 1].split(",") if "--views" in argv else list(VIEWS)
for vn, (yaw, pitch, dist, tgt) in VIEWS.items():
    if vn not in only: continue
    t = Vector(tgt)
    d = Vector((math.cos(math.radians(pitch)) * math.sin(math.radians(yaw)),
                -math.cos(math.radians(pitch)) * math.cos(math.radians(yaw)), math.sin(math.radians(pitch))))
    cam.location = t + d * dist; cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    sc.render.filepath = os.path.join(OUT, f"{TAG}-{vn}.png")
    bpy.ops.render.render(write_still=True)
print("DONE")
