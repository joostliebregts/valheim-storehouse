"""Larder Hutch, round 5: 64 units that mirror the container grid (8 columns x 8 rows), like the Mead Rack.
Our own furniture mesh + own atlas; the CONTENTS in the renders are the game's own item models (local reference rip,
never exported), placed by the same rule the mod uses (Display item size 0.7, capped at 1.15 x the unit-box fit).
Run: blender -b -P larder_r5.py -- [--out DIR] [--views a,b]
Writes assets/larder_r5/{LarderFrame.obj, larder_atlas.png, LarderAnchors.json} (anchors LAST, each file via a temp name
and an atomic rename, because the mod live-reloads this folder) and renders previews to --out.

Hutch: 2.0 m wide, 2.0 m tall (horns included), ~0.79 m deep (with the drawers ajar).
  grid rows 0-4 (top to bottom) = five open shelves, 8 units per shelf (box 0.22 w x 0.24 h x 0.40 d)
  grid rows 5-7               = three rows of four drawers, standing ajar (pulled out 8.5 cm of 45 cm, ~19%);
                                two units side by side per drawer (box 0.185 w x 0.085 h x 0.18 d), low and at the
                                front of the drawer so the dishes peek out over the low drawer front.
The mod maps grid (column, row) to units by height (rows of 8, highest first), then left to right seen from the front
(Unity x descending). Every grid row has its own height; the units are listed in grid order (index = row * 8 + column).

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
OUTA = os.path.normpath(os.path.join(HERE, "..", "assets", SLUG + "_r5"))
SCRATCH = "C:/Users/joost/AppData/Local/Temp/claude/C--Users-joost--pai/5e4bc60b-cdfe-4638-8e29-2e507fa13cf9/scratchpad/larder5"
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = argv[argv.index("--out") + 1] if "--out" in argv else SCRATCH
TAG = SLUG + "5"
ITEMS_DIR = "C:/Users/joost/ValheimRip/items"
os.makedirs(OUTA, exist_ok=True); os.makedirs(OUT, exist_ok=True)
rng = random.Random(7)
CLOTH_DZ = 0.025

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
    tmp = os.path.join(OUTA, "_atlas.part"); im.filepath_raw = tmp; im.file_format = "PNG"; im.save()
    os.replace(tmp, os.path.join(OUTA, "larder_atlas.png"))
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

#----CLOTH
def build_cloth():
    path = [(y, z + CLOTH_DZ) for y, z in [(0.05, 1.966), (-0.34, 1.966), (-0.388, 1.945), (-0.392, 1.90), (-0.372, 1.866), (-0.352, 1.83)]]
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
# ---------- layout constants (Blender space: x right seen from the front, -y front, z up) ----------
SHELVES = (0.49, 0.775, 1.06, 1.345, 1.63)    # shelf top heights, bottom shelf first, pitch 0.285
BOARD = 0.04
CROWN_U = 1.885                               # crown underside
SH_W, SH_D, SH_H = 0.22, 0.40, 0.24           # shelf unit box: width, depth, height
SH_X = [(-3.5 + c) * 0.225 for c in range(8)]
SH_Y = 0.02
BASE_TOP = SHELVES[0] - BOARD                  # 0.45: top of the drawer base = underside of the lowest shelf
FACE = -0.30                                   # front plane of the carcass
ROW_ZB = [0.05 + r * 0.14 for r in range(3)]   # drawer openings, bottom row first: opening bottoms
OPEN_H, RAIL = 0.12, 0.02                      # opening height, rail / dust board between drawer rows
DR_X = [-0.675, -0.225, 0.225, 0.675]          # drawer centres, left to right
DR_W, DR_DEPTH, DR_OPEN = 0.41, 0.45, 0.085    # drawer outer width, outer depth, how far it stands out (19%)
DR_FT, DR_WT, DR_BT = 0.02, 0.015, 0.012       # front, wall and bottom thickness
DR_LIFT = 0.003                                # drawer bottom above its dust board
DR_FRONT_H, DR_SIDE_H = 0.07, 0.05             # low front panel; sides above the drawer floor
DR_Y0 = FACE - DR_OPEN                         # outer face of a drawer front
DU_W, DU_D, DU_H = 0.17, 0.17, 0.085           # drawer unit box: width, depth, height (the mod may scale up to 1.15x)
DU_DX = 0.0955                                 # unit centre offset from the drawer centre
DU_Y = DR_Y0 + DR_FT + 0.014 + DU_D / 2        # boxes sit at the FRONT of the drawer
DU_Z = DR_LIFT + DR_BT + 0.002                 # unit bottom above the opening bottom
assert abs(ROW_ZB[2] + OPEN_H - BASE_TOP) < 1e-9
assert abs(ROW_ZB[1] - RAIL - ROW_ZB[0] - OPEN_H) < 1e-9

def build_frame():
    PX, PY = 0.95, 0.31
    for sx in (-1, 1):
        for sy in (-1, 1):
            timber("foot", (0.13, 0.14, 0.05), (sx * 0.945, sy * PY, 0.025), jitter=0.004, bevel=0.008)
            timber("post", (0.1, 0.1, 1.86), (sx * PX, sy * PY, 0.98), jitter=0.006,
                   rot=(rng.uniform(-.3, .3), rng.uniform(-.3, .3), 0))
    # plank back, ledgers
    for i in range(11):
        timber("back", (0.19, 0.035, 1.83), (-0.9 + i * 0.18, 0.335 + 0.004 * (i % 2), 0.97), jitter=0.003, bevel=0.01,
               rot=(rng.uniform(-.3, .3), 0, rng.uniform(-.6, .6)))
    for z in (0.5, 1.5):
        timber("ledger", (1.9, 0.03, 0.09), (0, 0.368, z), jitter=0.003, bevel=0.008)
    # sides: closed base panel, a rail under each upper shelf, crown rail
    for sx in (-1, 1):
        x = sx * 0.945
        timber("sidebase", (0.035, 0.6, BASE_TOP - 0.05), (x, 0.0, (BASE_TOP + 0.05) / 2), jitter=0.003, bevel=0.008)
        for top in SHELVES[1:]:
            timber("siderail", (0.035, 0.6, 0.1), (x, 0.0, top - BOARD - 0.05), jitter=0.003, bevel=0.008)
        timber("siderail", (0.035, 0.6, 0.1), (x, 0.0, CROWN_U - 0.05), jitter=0.003, bevel=0.008)
    # shelves: pale boards with a low front lip
    for top in SHELVES:
        timber("shelf", (1.86, 0.62, BOARD), (0, 0.02, top - BOARD / 2), kind="pale", jitter=0.004, jz=0.0, bevel=0.01)
        timber("lip", (1.80, 0.03, 0.03), (0, -0.275, top + 0.015), kind="pale", jitter=0.002, jz=0.0, bevel=0.006)
    # base: bottom board, plinth, dust boards + front rails between the drawer rows, stiles between the drawers
    timber("bottom", (1.86, 0.62, 0.02), (0, 0.02, ROW_ZB[0] - 0.01), kind="pale", jitter=0.003, jz=0.0, bevel=0.006)
    timber("plinth", (1.80, 0.03, ROW_ZB[0]), (0, FACE + 0.02, ROW_ZB[0] / 2), jitter=0.002, jz=0.0, bevel=0.006)
    for zb in ROW_ZB[1:]:
        timber("dust", (1.84, 0.58, RAIL), (0, 0.03, zb - RAIL / 2), kind="pale", jitter=0.002, jz=0.0, bevel=0.004)
        timber("rail", (1.80, 0.035, RAIL), (0, FACE + 0.0175, zb - RAIL / 2), jitter=0.002, jz=0.0, bevel=0.005)
    for x in (-0.45, 0.0, 0.45):
        timber("stile", (0.03, 0.035, BASE_TOP - ROW_ZB[0]), (x, FACE + 0.0175, (BASE_TOP + ROW_ZB[0]) / 2), jitter=0.0015, bevel=0.006)
    # drawers, standing ajar: low front, low sides, iron pull
    for zb in ROW_ZB:
        z0 = zb + DR_LIFT
        for x in DR_X:
            inner_d = DR_DEPTH - DR_FT
            timber("dfront", (DR_W, DR_FT, DR_FRONT_H), (x, DR_Y0 + DR_FT / 2, z0 + DR_FRONT_H / 2), kind="pale",
                   jitter=0.0015, jz=0.0, bevel=0.006)
            timber("dbottom", (DR_W, inner_d, DR_BT), (x, DR_Y0 + DR_FT + inner_d / 2, z0 + DR_BT / 2), kind="pale",
                   jitter=0.0, jz=0.0, bevel=0.003)
            for sx in (-1, 1):
                timber("dside", (DR_WT, inner_d, DR_BT + DR_SIDE_H), (x + sx * (DR_W / 2 - DR_WT / 2), DR_Y0 + DR_FT + inner_d / 2,
                       z0 + (DR_BT + DR_SIDE_H) / 2), kind="pale", jitter=0.001, jz=0.0, bevel=0.004)
            timber("dback", (DR_W - 2 * DR_WT, DR_WT, DR_BT + DR_SIDE_H), (x, DR_Y0 + DR_DEPTH - DR_WT / 2, z0 + (DR_BT + DR_SIDE_H) / 2),
                   kind="pale", jitter=0.001, jz=0.0, bevel=0.004)
            timber("pull", (0.11, 0.025, 0.03), (x, DR_Y0 - 0.0125, z0 + DR_FRONT_H * 0.55), kind="iron", jitter=0.002, bevel=0)
    # carved crown: frieze, teeth, two crown boards, horns
    timber("frieze", (1.86, 0.04, 0.09), (0, -0.318, CROWN_U - 0.045), jitter=0.003, bevel=0.01)
    for i in range(9):
        x = -0.1 + i * 0.1
        timber("tooth", (0.07, 0.02, 0.05 + 0.015 * (i % 2)), (x, -0.348, CROWN_U - 0.045), jitter=0.003, bevel=0, rot=(0, 0, rng.uniform(-2, 2)))
    timber("crown", (2.0, 0.76, 0.06), (0, 0, CROWN_U + 0.03), jitter=0.004, jz=0.0, bevel=0.012)
    timber("crown", (1.92, 0.68, 0.04), (0, 0, CROWN_U + 0.08), jitter=0.004, jz=0.0, bevel=0.008)
    for sx in (-1, 1):
        timber("horn", (0.06, 0.06, 0.12), (sx * 0.93, -0.3, 1.94), jitter=0.002, bevel=0.007, rot=(0, sx * 10, 0), taper=0.45)
    build_cloth()

# ---------- items (render only; the mod puts the stored item there) ----------
MEALS = ["CarrotSoup", "SerpentStew", "TurnipStew", "MushroomOmelette", "LoxPie", "BloodPudding", "CookedDeerMeat",
         "HoneyGlazedChicken", "MeatPlatter", "Bread", "Sausages", "FishCooked", "CookedMeat", "QueensJam", "FishWraps",
         "FishAndBread"]
DISPLAY, CAP = 0.7, 1.15          # the mod's "Display item size" and its cap at the unit-box fit

def item_bounds(name):
    info = json.load(open(f"{ITEMS_DIR}/{name}/info.json", encoding="utf-8"))
    return Vector(info["bounds_max"]) - Vector(info["bounds_min"])

def rot_aabb(size, rot_deg):
    R = Euler([math.radians(a) for a in rot_deg]).to_matrix()
    cs = [R @ Vector((sx * size.x / 2, sy * size.y / 2, z * size.z)) for sx in (-1, 1) for sy in (-1, 1) for z in (0, 1)]
    mn = Vector((min(c[i] for c in cs) for i in range(3))); mx = Vector((max(c[i] for c in cs) for i in range(3)))
    return mn, mx

def plan_units():
    """64 units in grid order (row 0 = top shelf, column 0 = leftmost seen from the front). Pure data."""
    r2 = random.Random(5)
    names = [n for n in MEALS for _ in range(4)]
    for _ in range(5000):
        r2.shuffle(names)
        if all(not ((k % 8 and names[k] == names[k - 1]) or (k >= 8 and names[k] == names[k - 8])) for k in range(64)): break
    units = []
    for g in range(8):
        for c in range(8):
            k = g * 8 + c
            if g < 5:
                shelf = 4 - g
                u = dict(place="shelf", shelf=shelf, origin=(SH_X[c], SH_Y, SHELVES[shelf] + 0.002), box=(SH_W, SH_D, SH_H),
                         cav=(-0.90, 0.90, -0.26, 0.31, SHELVES[shelf], SHELVES[shelf + 1] - BOARD if shelf < 4 else CROWN_U))
            else:
                r = 7 - g; d, side = divmod(c, 2)
                x = DR_X[d] + (DU_DX if side else -DU_DX)
                zb = ROW_ZB[r]
                u = dict(place="drawer", drawer_row=r, drawer=d, origin=(x, DU_Y, zb + DU_Z), box=(DU_W, DU_D, DU_H),
                         cav=(DR_X[d] - DR_W / 2 + DR_WT, DR_X[d] + DR_W / 2 - DR_WT, DR_Y0 + DR_FT, DR_Y0 + DR_DEPTH - DR_WT,
                              zb + DR_LIFT + DR_BT, zb + OPEN_H))
            name = names[k]
            rot = (0.0, 0.0, round(r2.uniform(-7, 7), 1))
            mn, mx = rot_aabb(item_bounds(name), rot)
            dim = mx - mn
            bx, by, bz = u["box"]
            fit = min(bx * 0.96 / dim.x, by * 0.96 / dim.y, bz / dim.z)
            u.update(index=k, grid_row=g, grid_col=c, item=name, rot=rot, aabb=(mn, mx), fit=fit, scale=min(DISPLAY, fit * CAP))
            units.append(u)
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
    mn, mx = u["aabb"]
    ctr = Vector(((mn.x + mx.x) / 2, (mn.y + mx.y) / 2, mn.z)) * u["scale"]
    loc = Vector(u["origin"]) - ctr + Vector((dx, 0, 0))
    for t in template(u["item"]):
        o = t.copy(); bpy.context.scene.collection.objects.link(o)
        o.hide_render = False; o.hide_set(False)
        o.rotation_euler = tuple(math.radians(a) for a in u["rot"]); o.scale = (u["scale"],) * 3
        o.location = loc; o.name = f"item{u['index']:02d}_{u['item']}"
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
        base = len(V); V += [o.matrix_world @ v.co for v in o.data.vertices]
        P += [[base + i for i in p.vertices] for p in o.data.polygons]
    return BVHTree.FromPolygons(V, P, all_triangles=False)

def box_tree(o, b):
    x0, x1 = o[0] - b[0] / 2, o[0] + b[0] / 2; y0, y1 = o[1] - b[1] / 2, o[1] + b[1] / 2; z0, z1 = o[2], o[2] + b[2]
    V = [Vector((x, y, z)) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]
    F = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    return BVHTree.FromPolygons(V, F, all_triangles=False), (x0, x1, y0, y1, z0, z1)

# ---- unity conversion
C = Matrix(((-1, 0, 0), (0, 0, 1), (0, -1, 0)))
def to_unity_vec(v): return [round(-v[0], 4), round(v[2], 4), round(-v[1], 4)]
def to_unity_euler(rot_deg):
    Rb = Euler([math.radians(a) for a in rot_deg]).to_matrix()
    Ru = C @ Rb @ C.transposed()
    sx = max(-1.0, min(1.0, -Ru[1][2]))
    x = math.asin(sx); z = math.atan2(Ru[1][0], Ru[1][1]); y = math.atan2(Ru[0][2], Ru[2][2])
    return [round(math.degrees(a), 2) + 0.0 for a in (x, y, z)]

UNITS = plan_units()
rng.seed(7); PARTS.clear()
build_frame()
FRAME_TRIS = tris(PARTS)
ftree = bvh(PARTS)

# ---- 1. grid mapping, exactly as the mod does it: rows of 8 by height (desc), each row by Unity x desc, then z desc
U = [dict(u, upos=to_unity_vec(u["origin"])) for u in UNITS]
by_h = sorted(range(64), key=lambda i: -U[i]["upos"][1])
order = []
for r in range(8):
    order += sorted(by_h[r * 8:(r + 1) * 8], key=lambda i: (-U[i]["upos"][0], -U[i]["upos"][2]))
row_h = [sorted({U[i]["upos"][1] for i in by_h[r * 8:(r + 1) * 8]}) for r in range(8)]
gaps = [round(min(row_h[r]) - max(row_h[r + 1]), 3) for r in range(7)]
print("GRID order matches index:", order == list(range(64)), "row heights", [h[0] for h in row_h], "min gap between rows", min(gaps))

# ---- 2. unit boxes: inside their cavity, not touching the frame, not touching each other
bad_cav, bad_frame, boxes = [], [], []
for u in UNITS:
    t, (x0, x1, y0, y1, z0, z1) = box_tree(u["origin"], u["box"])
    cx0, cx1, cy0, cy1, cz0, cz1 = u["cav"]
    if not (cx0 < x0 and x1 < cx1 and cy0 < y0 and y1 < cy1 and cz0 < z0 and z1 < cz1):
        bad_cav.append(u["index"]); print("  cavity", u["index"], (x0, x1, y0, y1, z0, z1), u["cav"])
    if ftree.overlap(t): bad_frame.append(u["index"])
    boxes.append((x0, x1, y0, y1, z0, z1))
box_ov = [(i, j) for i in range(64) for j in range(i + 1, 64)
          if all(boxes[i][2 * a] < boxes[j][2 * a + 1] and boxes[j][2 * a] < boxes[i][2 * a + 1] for a in range(3))]
print("BOX CHECK outside cavity", len(bad_cav), bad_cav, "| box-frame overlaps", len(bad_frame), bad_frame,
      "| box-box overlaps", len(box_ov), box_ov)
clearance = min(min(b[0] - u["cav"][0], u["cav"][1] - b[1], b[2] - u["cav"][2], u["cav"][3] - b[3], b[4] - u["cav"][4], u["cav"][5] - b[5])
                for u, b in zip(UNITS, boxes))
print("BOX min clearance to cavity walls (m)", round(clearance, 4))

# ---- 3. meals at 100% at the mod's display size
placed = {u["index"]: place_unit(u) for u in UNITS}
bpy.context.view_layer.update()
item_tris = 0; hit_frame = []; over_box = []
PART_TREES = [(o.name.split('.')[0], bvh([o])) for o in PARTS]
for u in UNITS:
    ox, oy, oz = u["origin"]; bx, by, bz = u["box"]
    for o in placed[u["index"]]:
        item_tris += len(o.data.polygons)
        wv = world_verts(o)
        tr = BVHTree.FromPolygons(wv, [list(p.vertices) for p in o.data.polygons], all_triangles=False)
        if ftree.overlap(tr):
            hit_frame.append((u["index"], u["item"], u["place"], sorted({n for n, pt in PART_TREES if pt.overlap(tr)})))
        ex = max(max(abs(c.x - ox) - bx / 2, abs(c.y - oy) - by / 2, c.z - oz - bz) for c in wv)
        if ex > 0.004: over_box.append((u["index"], u["item"], round(ex, 3)))
print("ITEMS at display size: touching the frame", len(hit_frame), hit_frame)
print("ITEMS sticking out of their own box (>4 mm, from the 1.15 cap)", len(over_box), over_box)
print("SCALES shelf", round(min(u["scale"] for u in UNITS if u["place"] == "shelf"), 3), "-",
      round(max(u["scale"] for u in UNITS if u["place"] == "shelf"), 3), "| drawer",
      round(min(u["scale"] for u in UNITS if u["place"] == "drawer"), 3), "-", round(max(u["scale"] for u in UNITS if u["place"] == "drawer"), 3))

# ---- 4. can a standing player see into the drawers? eye 1.6 m, 2 m in front of the drawer fronts
dg = bpy.context.evaluated_depsgraph_get()
VIS = {}
for ex in (-0.9, 0.0, 0.9):
    eye = Vector((ex, DR_Y0 - 2.0, 1.6))
    rows = {0: [], 1: [], 2: []}
    for u in UNITS:
        if u["place"] != "drawer": continue
        seen = tot = 0
        for o in placed[u["index"]]:
            wv = world_verts(o)
            step = max(1, len(wv) // 80)
            for v in wv[::step]:
                d = v - eye; L = d.length
                ok, loc, nrm, idx, hob, mtx = sc.ray_cast(dg, eye, d.normalized(), distance=L + 0.02)
                tot += 1
                if ok and hob.name == o.name: seen += 1
        rows[u["drawer_row"]].append(seen / max(tot, 1))
    VIS[ex] = {r: (sum(1 for f in v if f > 0.05), round(sum(v) / len(v), 2)) for r, v in rows.items()}
    print("VISIBILITY eye x", ex, "per drawer row (bottom=0): units with >5% of samples seen of 8, mean fraction seen", VIS[ex])

# ---- 5. exports: frame OBJ, then the anchors LAST (atlas was written at start). Each via temp name + atomic rename.
bpy.ops.object.select_all(action="DESELECT")
for o in PARTS: o.select_set(True)
tmp = os.path.join(OUTA, "_frame.part")
bpy.ops.wm.obj_export(filepath=tmp, export_selected_objects=True, export_materials=False,
                      export_triangulated_mesh=True, forward_axis="NEGATIVE_Z", up_axis="Y")
if not os.path.exists(tmp) and os.path.exists(tmp + ".obj"): tmp = tmp + ".obj"
os.replace(tmp, os.path.join(OUTA, "LarderFrame.obj"))

anchors = []
for u in UNITS:
    a = {"index": u["index"], "kind": "single", "place": u["place"], "grid_row": u["grid_row"], "grid_col": u["grid_col"]}
    if u["place"] == "shelf": a["shelf"] = u["shelf"]
    else: a["drawer_row"] = u["drawer_row"]; a["drawer"] = u["drawer"]
    bx, by, bz = u["box"]
    a.update({"row": "single", "position": to_unity_vec(u["origin"]), "rotation": [0.0, 0.0, 0.0],
              "box_size": [bx, bz, by],
              "layout": {"cols": 1, "rows": 1, "layers": 1, "pitch_frac": 1.0},
              "example_item": u["item"], "example_scale": round(u["fit"], 4),
              "copies": [{"layer": 0, "row": 0, "col": 0, "offset": [0.0, 0.0, 0.0], "rotation": to_unity_euler(u["rot"])}]})
    anchors.append(a)
doc = {"schema": "storehouse-anchors/1", "furniture": "Larder Hutch", "units": len(anchors), "slots_designed_for": 64,
       "stack_per_unit": True,
       "space": {"unity": "prefab space, origin on the floor at the centre of the footprint, +z front, +y up, +x to the "
                          "furniture's left when seen from the front",
                 "from_blender": "ux=-bx, uy=bz, uz=-by; rotations R_u = C R_b C^T (C=[[-1,0,0],[0,0,1],[0,-1,0]]), "
                                 "Unity Euler order Ry*Rx*Rz"},
       "fill_order": "grid order, mirroring the 8 x 8 container grid: index = grid_row * 8 + grid_col; grid rows top to "
                     "bottom (rows 0-4 = the five shelves from the top, rows 5-7 = the three drawer rows from the top), each "
                     "row left to right seen from the front. Every grid row has its own height, so rows of 8 by position.y "
                     "descending, each sorted by position.x descending, give the same order",
       "position": "unit position = bottom centre of its box. box_size = [x, y, z] in Unity axes",
       "copy_rule": "One copy per unit at offset 0: the stored item's bounds, turned by the copy rotation, are fitted "
                    "uniformly into box_x*0.96 x box_y x box_z*0.96 and stand on the unit position (bottom centre).",
       "note": "r5 (Joost, 22 Oct): 64 units like the Mead Rack, mirroring the chest grid: 5 shelves of 8, then 3 rows of 4 "
               "drawers standing ajar (8.5 cm of 45 cm), 2 units per drawer, low and at the front of the drawer",
       "units_data": anchors}
tmp = os.path.join(OUTA, "_anchors.part")
with open(tmp, "w", encoding="utf-8") as f: json.dump(doc, f, indent=1)
os.replace(tmp, os.path.join(OUTA, "LarderAnchors.json"))
print("LARDER", {"frame_tris": FRAME_TRIS, "units": len(UNITS), "item_tris_at_100": item_tris})

# ---------- renders ----------
full = join(PARTS, "larder_full")
EMPTY_X = -2.5
rng.seed(7); PARTS.clear(); build_frame()
empty = join(PARTS, "larder_empty"); empty.location.x = EMPTY_X
items_all = sum(placed.values(), [])

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
EYE_Y = DR_Y0 - 2.0
# name: (eye, target, horizontal fov deg, show empty)
VIEWS = {
    "pair":     (Vector((-1.25, -6.2, 2.0)), Vector((-1.25, 0, 0.95)), 50, True),
    "full34":   (Vector((1.6, -3.4, 1.75)), Vector((0, 0, 0.95)), 50, False),
    "empty34":  (Vector((EMPTY_X - 1.6, -3.4, 1.75)), Vector((EMPTY_X, 0, 0.95)), 50, True),
    "player":   (Vector((0, EYE_Y, 1.6)), Vector((0, 0, 0.9)), 75, False),
    "player_drawers": (Vector((0, EYE_Y, 1.6)), Vector((0, -0.3, 0.25)), 38, False),
    "player_left":    (Vector((-0.9, EYE_Y, 1.6)), Vector((0.1, -0.3, 0.25)), 38, False),
    "drawer_close":   (Vector((0.55, -1.25, 0.95)), Vector((0.3, -0.3, 0.25)), 40, False),
}
only = argv[argv.index("--views") + 1].split(",") if "--views" in argv else list(VIEWS)
for vn, (eye, tgt, fov, show_empty) in VIEWS.items():
    if vn not in only: continue
    empty.hide_render = not show_empty
    cam.location = eye; cam.rotation_euler = (tgt - eye).to_track_quat("-Z", "Y").to_euler()
    cam.data.angle = math.radians(fov)
    sc.render.filepath = os.path.join(OUT, f"{TAG}-{vn}.png")
    bpy.ops.render.render(write_still=True)
print("DONE")
