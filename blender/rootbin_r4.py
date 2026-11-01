"""Root Bin, round 4: as round 3 (contents SETTLED by a rigid body simulation, item models dropped stack by stack) but
(1) the collision body is only the item BODY (alpha-clipped leaf material excluded, leaves ride along), (2) item sizes as round 3 (per-crate fit rules, the mod's own; Joost: mass storage keeps the layouts' sizes), (3) a float check (<= 5 mm to the nearest support) and a leaf-aware cavity check.
Our own furniture mesh + own 128 px point-filtered atlas. The CONTENTS are NOT modelled here: the mod places the game's
own item models at the anchors this script exports (rootbin_anchors.json). For the renders the extracted item models
from C:/Users/joost/ValheimRip/items are used (local reference only, never exported).
Run: blender -b -P rootbin_r4.py -- [--out DIR] [--tag NAME] [--no-ref] [--crates 1,0] [--views carrots] 

Writes into assets/rootbin_r4/: RootBin.obj (frame only, forward -Z, up Y, triangulated, no materials),
rootbin_atlas.png (128x128), rootbin_anchors.json (content anchors in fill order, Unity prefab space).

Atlas (v from the bottom, strips tile along u): v 0.75-1 hewn timber, 0.5-0.75 end grain (4 ring tiles),
0.375-0.5 weathered plank, 0.25-0.375 iron, 0.125-0.25 straw liner, 0-0.125 dark filler.

Frame space (Blender, metres): origin on the floor under the middle of the stand, x across (-1..1), -y = front, z up.
Terraces (floor top z / front edge y): A 0.18 / -0.60, B 0.74 / -0.30, C 1.30 / 0.00. Each has 3 crates (centres x -0.6, 0, 0.6).
Every crate holds 8 unit anchors: layer 1 (front row left,right, back row left,right) then layer 2 the same.
"""
import bpy, bmesh, sys, os, math, json, random
import numpy as np
from mathutils import Vector, Matrix, Euler, Quaternion

HERE = os.path.dirname(os.path.abspath(__file__))
OUTA = os.path.normpath(os.path.join(HERE, "..", "assets", "rootbin_r4"))
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
SCR = "C:/Users/joost/AppData/Local/Temp/claude/C--Users-joost--pai/5e4bc60b-cdfe-4638-8e29-2e507fa13cf9/scratchpad/proto4/rootbin"
OUT = argv[argv.index("--out") + 1] if "--out" in argv else SCR
TAG = argv[argv.index("--tag") + 1] if "--tag" in argv else "rootbin"
RIP = "C:/Users/joost/ValheimRip/chests/piece_chest_wood"
sys.path.append("C:/Users/joost/ValheimRip/items")
from load_item import load_item
os.makedirs(OUTA, exist_ok=True); os.makedirs(OUT, exist_ok=True)
rng = random.Random(7)

TEX = 128
DENS = 48.0
STRIP = {"hewn": (0.75, 32), "end": (0.5, 32), "dark": (0.375, 16), "iron": (0.25, 16), "straw": (0.125, 16)}

# ---------- texture ----------
def srgb(c): return np.array(c, dtype=np.float32)
WOOD, WOOD_D = srgb((0.38, 0.29, 0.18)), srgb((0.21, 0.16, 0.10))
WOODW, WOODW_D = srgb((0.31, 0.26, 0.19)), srgb((0.16, 0.13, 0.09))
END, END_D = srgb((0.55, 0.45, 0.31)), srgb((0.35, 0.27, 0.17))
IRON, IRON_D = srgb((0.22, 0.21, 0.20)), srgb((0.09, 0.09, 0.09))
STRAW, STRAW_D = srgb((0.50, 0.43, 0.26)), srgb((0.30, 0.25, 0.15))

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
    img = np.zeros((TEX, TEX, 3), np.float32)
    img[:] = WOODW_D
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
    # straw liner: short chaff strokes
    x = np.arange(TEX)[None, :].repeat(16, 0).astype(np.float32)
    y = np.arange(16)[:, None].repeat(TEX, 1).astype(np.float32)
    g = np.sin(x * 0.9 + 2.0 * np.sin(y * 0.8 + x * 0.1)) * 0.5 + 0.5
    t = g * 0.6 + nr.random((16, TEX)) * 0.4
    img[16:32] = STRAW * (1 - t[..., None]) + STRAW_D * t[..., None]
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
    if kind not in ("iron", "straw") and ax == long_axis:
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

def timber(name, size, pos, kind="hewn", rot=(0, 0, 0), jitter=0.012, bevel=0.010):
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

# ---- layout constants ----
BAYS = [-0.6, 0.0, 0.6]                 # crate centres along x
TIERS = [("A", 0.18, -0.60), ("B", 0.74, -0.30), ("C", 1.30, 0.00)]   # name, floor top z, front y
CAV_HW = 0.265                           # clear half width of a crate cavity
CAV_Y0, CAV_Y1 = 0.020, 0.470            # cavity y range, relative to the tier front y
CEIL = {"A": 0.43, "B": 0.43, "C": 0.57} # cavity ceiling above the floor top
XLINES = [(-0.93, 0.12), (-0.30, 0.09), (0.30, 0.09), (0.93, 0.12)]   # post lines (x, section)
SIDE_X = [-0.895, -0.30, 0.30, 0.895]    # side boards (0.05 thick)

def build_frame():
    j = lambda a: rng.uniform(-a, a)
    for tn, zT, y0 in TIERS:
        # side boards (also the stringers the floor rests on): z from 0.10 below the floor to 0.24 above
        for x in SIDE_X:
            timber("side", (0.05, 0.56, 0.34), (x, y0 + 0.25, zT + 0.07), kind="dark", bevel=0.008, jitter=0.004)
        # floor: slats front to back on two cross bearers, straw liner on top
        for yb in (0.12, 0.38):
            timber("bearer", (1.84, 0.08, 0.07), (0, y0 + yb, zT - 0.082), kind="dark", bevel=0, jitter=0.004)
        for bx in BAYS:
            for dx in (-0.2, -0.067, 0.067, 0.2):
                timber("floor", (0.12, 0.54, 0.035), (bx + dx, y0 + 0.24, zT - 0.0295), kind="dark", bevel=0, jitter=0.003)
            timber("straw", (0.52, 0.47, 0.014), (bx, y0 + 0.2435, zT - 0.004), kind="straw", bevel=0, jitter=0.002)
        # back boards, three per bay (four on the top terrace), a finger of gap between
        zs = (0.06, 0.205, 0.35) if tn != "C" else (0.06, 0.205, 0.35, 0.495)
        for bx in BAYS:
            for z in zs:
                timber("back", (0.55, 0.04, 0.135), (bx, y0 + 0.50, zT + z + j(0.004)), rot=(j(1.0), 0, j(0.7)),
                       bevel=0.007, jitter=0.004)
        # front plank leaning out, iron straps
        for bx in BAYS:
            timber("front", (0.55, 0.04, 0.10), (bx, y0 - 0.02, zT + 0.06 + j(0.003)), rot=(10 + j(1.2), 0, j(0.6)),
                   kind="dark", bevel=0.007, jitter=0.004)
            for dx in (-0.19, 0.19):
                timber("strap", (0.04, 0.014, 0.15), (bx + dx, y0 - 0.047, zT + 0.058), rot=(10, 0, 0), kind="iron",
                       jitter=0.002, bevel=0.004)
    # posts: three per line, one behind each terrace
    for x, sec in XLINES:
        for (tn, zT, y0), top in zip(TIERS, (0.64, 1.20, 2.0 if sec > 0.1 else 1.90)):
            yc = y0 + (0.545 if sec > 0.1 else 0.53)
            hh = top + j(0.01)
            timber("post", (sec, sec, hh), (x, yc, hh / 2), rot=(j(0.5), j(0.5), 0), bevel=0.014)
    # ground sills under the lowest terrace
    for y in (-0.52, -0.16):
        timber("sill", (1.99, 0.12, 0.08), (0, y, 0.04), bevel=0.012)
    # end skirts: closed stair-step planks on the outside of both ends
    for sx in (-1, 1):
        for y0s, y1s, ztop in ((-0.08, 0.20, 0.64), (0.31, 0.60, 1.20)):
            n = int(ztop / 0.155)
            for i in range(n):
                timber("skirt", (0.03, y1s - y0s + j(0.01), 0.14), (sx * 0.955, (y0s + y1s) / 2, 0.075 + i * 0.155 + j(0.003)),
                       kind="dark", bevel=0.006, jitter=0.003)
    # canopy: front and back beam, two rafters, front end posts
    for sx in (-1, 1):
        timber("fpost", (0.10, 0.10, 0.86), (sx * 0.93, -0.01, 1.14 + 0.43), rot=(j(0.4), j(0.4), 0), bevel=0.012)
    timber("beam", (1.98, 0.10, 0.10), (0, -0.01, 1.93), rot=(0, 0, j(0.2)), bevel=0.012)
    timber("beam", (1.98, 0.10, 0.10), (0, 0.55, 1.95), rot=(0, 0, j(0.2)), bevel=0.012)
    for x in (-0.60, 0.0, 0.60):
        timber("rafter", (0.09, 0.62, 0.06), (x, 0.27, 1.935), bevel=0.008, jitter=0.004)
    # iron bands round the end post tops
    for sx in (-1, 1):
        timber("band", (0.155, 0.155, 0.05), (sx * 0.93, 0.545, 1.95), kind="iron", jitter=0.003, bevel=0.006)
        timber("band", (0.155, 0.155, 0.05), (sx * 0.93, 0.245, 1.17), kind="iron", jitter=0.003, bevel=0.006)
        timber("band", (0.155, 0.155, 0.05), (sx * 0.93, -0.055, 0.61), kind="iron", jitter=0.003, bevel=0.006)

# ---------- unit anchors (as round 3: per-crate item sizes, the mod's own fit rules apply) ----------
def arg(name, default, typ=float): return typ(argv[argv.index(name) + 1]) if name in argv else default
ONLY = [int(x) for x in argv[argv.index("--crates") + 1].split(",")] if "--crates" in argv else list(range(9))
PARTIAL = len(ONLY) < 9
# ---------- unit anchors ----------
UW, UD, UH = 0.262, 0.222, 0.20           # layer-1 unit box
L2 = {"w": 0.250, "d": 0.216, "h": 0.20}   # layer-2 unit box
L2Z = 0.19
CLASSES = ["pile", "bundle", "sheaf", "row", "pile", "sheaf", "pile", "bundle", "row"]
CRATE_ITEMS = [["Turnip"] * 8, ["Carrot"] * 8, ["Barley"] * 8, ["Mushroom"] * 8,
               ["Blueberries", "Raspberry", "Cloudberry", "Blueberries", "Raspberry", "Cloudberry", "Blueberries", "Raspberry"],
               ["Flax"] * 8, ["Onion"] * 8, ["Thistle", "Dandelion"] * 4, ["MushroomYellow", "MushroomBlue"] * 4]
CRATE_LABEL = ["turnips", "carrots", "barley", "mushrooms", "berries", "flax", "onions", "herbs", "more mushrooms"]

def C(pos, euler=(0, 0, 0), fit=(0.1, 0.1, 0.1), anchor="bottom", align="up"):
    return dict(pos=list(pos), euler=list(euler), fit=list(fit), anchor=anchor, align=align)

def layout_pile(r, box):
    """6 in a 3x2 grid on the floor, 3 nested on top; tilted and yawed like a heap."""
    sx = (box[0] - 0.102) / 2; sy = (box[1] - 0.102) / 2
    out = []
    for iy, yy in enumerate((-sy, sy)):
        for xx in (-sx, 0, sx):
            f = r.uniform(0.94, 1.06)
            out.append(C((xx + r.uniform(-.006, .006), yy + r.uniform(-.006, .006), r.uniform(0, .008)),
                         (r.uniform(-14, 14), r.uniform(-14, 14), r.uniform(0, 360)), (0.106 * f, 0.106 * f, 0.15 * f)))
    for xx, yy in ((-0.066, -0.026), (0.0, 0.034), (0.066, -0.026)):
        f = r.uniform(0.92, 1.0)
        out.append(C((xx + r.uniform(-.006, .006), yy, 0.060 + r.uniform(0, .008)),
                     (r.uniform(-18, 18), r.uniform(-18, 18), r.uniform(0, 360)), (0.10 * f, 0.10 * f, 0.138 * f)))
    return out

def layout_row(r, box):
    """3x2 upright grid (a tray of caps) with 3 more tucked on top."""
    sx = (box[0] - 0.088) / 2; sy = (box[1] - 0.094) / 2
    out = []
    for yy in (-sy, sy):
        for xx in (-sx, 0, sx):
            f = r.uniform(0.95, 1.05)
            out.append(C((xx, yy, 0), (r.uniform(-7, 7), r.uniform(-7, 7), r.uniform(0, 360)), (0.088 * f, 0.094 * f, 0.095 * f)))
    for xx in (-sx * 0.5, sx * 0.5, 0):
        yy = 0.0 if xx else sy * 0.2
        out.append(C((xx, yy, 0.075), (r.uniform(-9, 9), r.uniform(-9, 9), r.uniform(0, 360)), (0.080, 0.085, 0.085)))
    return out

def layout_bundle(r, box):
    """8 lying side by side in a 3-2-3 hex nest, heads alternating, tied bundle."""
    out = []
    w = 0.077
    rows = [(0.040, (-0.077, 0.0, 0.077), 0), (0.100, (-0.0385, 0.0385), 180), (0.160, (-0.077, 0.0, 0.077), 0)]
    for z, ys, flip in rows:
        for yy in ys:
            out.append(C((r.uniform(-.012, .012), yy, z),
                         (r.uniform(-8, 8), r.uniform(-3, 3), flip + r.uniform(-5, 5)), (0.25, w, w), "center", "long_x"))
    return out

def layout_sheaf(r, box):
    """lying sheaf: 8 stalks, heads fanned out at +x, a little tilt."""
    out = []
    w = 0.082
    rows = [(0.041, (-0.077, 0.0, 0.077)), (0.103, (-0.0385, 0.0385)), (0.160, (-0.077, 0.0, 0.077))]
    for z, ys in rows:
        for yy in ys:
            out.append(C((r.uniform(-.01, .01), yy * 1.04, z), (r.uniform(-5, 5), r.uniform(-6, 6), r.uniform(-7, 7)),
                         (0.26, w, w), "center", "long_x"))
    return out

LAYOUT = {"pile": layout_pile, "row": layout_row, "bundle": layout_bundle, "sheaf": layout_sheaf}

def unit_list():
    """All 72 unit anchors in fill order, in Blender frame space."""
    units = []
    r = random.Random(11)
    for ci in range(9):
        tn, zT, y0 = TIERS[ci // 3]; bx = BAYS[ci % 3]
        cy0 = y0 + CAV_Y0; cd = (CAV_Y1 - CAV_Y0) / 2
        for layer in range(2):
            for row in range(2):
                for col in range(2):
                    idx = ci * 8 + layer * 4 + row * 2 + col
                    box = (UW, UD, UH) if layer == 0 else (L2["w"], L2["d"], L2["h"])
                    pos = (bx + (col - 0.5) * 0.265, cy0 + cd * (row + 0.5), zT + 0.004 + (0 if layer == 0 else L2Z))
                    kind = CLASSES[ci]
                    units.append(dict(index=idx, kind=kind, crate=ci, tier=tn, layer=layer, pos=pos, box=box,
                                      copies=LAYOUT[kind](r, box), item=CRATE_ITEMS[ci][layer * 4 + row * 2 + col]))
    return units

# ---------- item templates (render only) ----------
TPL = {}
def tpl(name):
    if name in TPL: return TPL[name]
    objs = [o for o in load_item(name, anchor="center") if o.type == "MESH"]
    allv = np.array([v.co[:] for o in objs for v in o.data.vertices])
    mn, mx = allv.min(0), allv.max(0); c = (mn + mx) / 2
    for o in objs:
        o.data.transform(Matrix.Translation(-Vector(c)))
        o.hide_render = True; o.hide_viewport = True
    allv = allv - c
    TPL[name] = dict(datas=[o.data for o in objs], size=mx - mn, verts=allv, objs=objs)
    return TPL[name]

def align_matrix(size):
    ax = int(np.argmax(size)); v = Vector([1.0 if i == ax else 0.0 for i in range(3)])
    return v.rotation_difference(Vector((1, 0, 0))).to_matrix()

def place(item, cp):
    """-> (R 3x3, scale, centre vector in unit-local space). Contain-fit, then rotate about the bounds centre."""
    t = tpl(item); size = t["size"]
    R0 = align_matrix(size) if cp["align"] == "long_x" else Matrix.Identity(3)
    asz = [abs(x) for x in (R0 @ Vector(size))]
    s = min(cp["fit"][i] / asz[i] for i in range(3) if asz[i] > 1e-6)
    Rc = Euler([math.radians(a) for a in cp["euler"]], "XYZ").to_matrix()
    R = Rc @ R0
    pos = Vector(cp["pos"])
    cen = pos + Vector((0, 0, s * asz[2] / 2)) if cp["anchor"] == "bottom" else pos
    return R, s, cen, asz

def settle(u):
    """Nudge / shrink every copy so the example item sits inside its unit box (4 mm inner margin)."""
    w, dd, h = u["box"]; m = 0.004
    lim = [(-w / 2 + m, w / 2 - m), (-dd / 2 + m, dd / 2 - m), (0.002, h)]
    t = tpl(u["item"])
    for cp in u["copies"]:
        for _ in range(8):
            R, s, cen, asz = place(u["item"], cp)
            V = (t["verts"] * s) @ np.array(R).T + np.array(cen)
            lo, hi = V.min(0), V.max(0); f = 1.0
            for i in range(3):
                span = hi[i] - lo[i]; room = lim[i][1] - lim[i][0]
                if span > room: f = min(f, room / span * 0.99)
            if f < 1.0:
                cp["fit"] = [x * f for x in cp["fit"]]; continue
            for i in range(3):
                if lo[i] < lim[i][0]: cp["pos"][i] += lim[i][0] - lo[i]
                elif hi[i] > lim[i][1]: cp["pos"][i] -= hi[i] - lim[i][1]
            break

SHRINK = {0: 0.93, 1: 0.85, 2: 0.91, 5: 0.91}

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

# ---------- round 4: body-only collision ----------
import time
ITEMS = "C:/Users/joost/ValheimRip/items"
def leaf_materials(item):
    """alpha-clipped materials are the leaves, but only when the item also has an opaque material (the body)."""
    mats = json.load(open(f"{ITEMS}/{item}/info.json"))["materials"]
    if any(v.get("alpha_mode") != "clip" for v in mats.values()):
        return {k for k, v in mats.items() if v.get("alpha_mode") == "clip"}
    return set()

def cav(ci):
    tn, zT, y0 = TIERS[ci // 3]; bx = BAYS[ci % 3]
    return (bx - CAV_HW, bx + CAV_HW, y0 + CAV_Y0, y0 + CAV_Y1, zT + 0.006, zT + CEIL[tn])

MERGED = {}
def merged(item, align):
    """per item+alignment: the visible mesh (all parts, centred on the bounds, aligned), and the collision body:
    convex hull of the NON-leaf vertices only, with its origin at the body centre (so the centre of mass is in the body)."""
    key = (item, align)
    if key in MERGED: return MERGED[key]
    t = tpl(item)
    R0 = align_matrix(t["size"]) if align == "long_x" else Matrix.Identity(3)
    obs = []
    for d in t["datas"]:
        o = bpy.data.objects.new("m", d.copy()); sc.collection.objects.link(o); obs.append(o)
    ob = join(obs, "mrg") if len(obs) > 1 else obs[0]
    me = ob.data; me.name = f"{item}_{align}"
    me.transform(R0.to_4x4())
    leafm = leaf_materials(item)
    names = [(mt.name[len(f"VH_{item}_"):] if mt else "") for mt in me.materials]
    body_v = set(); leaf_v = set()
    for p in me.polygons:
        (leaf_v if names[p.material_index] in leafm else body_v).update(p.vertices)
    leaf_only = leaf_v - body_v
    bpy.data.objects.remove(ob)
    verts = np.array([v.co[:] for v in me.vertices])
    leafmask = np.zeros(len(verts), bool); leafmask[list(leaf_only)] = True
    bidx = sorted(body_v)
    bv = verts[bidx]
    cb = (bv.min(0) + bv.max(0)) / 2
    bm = bmesh.new()
    for v in bv - cb: bm.verts.new(v)
    res = bmesh.ops.convex_hull(bm, input=bm.verts[:])
    fs = [f for f in res["geom"] if isinstance(f, bmesh.types.BMFace)]
    bmesh.ops.triangulate(bm, faces=fs)
    bm.normal_update(); bm.verts.index_update()
    tf = [f for f in bm.faces if f.is_valid]
    used = sorted({v.index for f in tf for v in f.verts})
    remap = {o: n for n, o in enumerate(used)}
    bm.verts.ensure_lookup_table()
    hv = np.array([bm.verts[i].co[:] for i in used])
    F = np.array([[remap[v.index] for v in f.verts] for f in tf])
    cen = hv.mean(0)
    N = []; D = []
    for f in tf:
        n = np.array(f.normal[:]); d0 = n @ np.array(f.verts[0].co[:])
        if n @ cen > d0: n = -n; d0 = -d0                          # make sure it points outward
        N.append(n); D.append(d0)
    N = np.array(N); D = np.array(D)
    bm.free()
    pm = bpy.data.meshes.new(f"prox_{item}_{align}"); pm.from_pydata([tuple(v) for v in hv], [], [tuple(int(i) for i in f) for f in F]); pm.update()
    edges = sorted({tuple(sorted((int(f[a]), int(f[(a + 1) % 3])))) for f in F for a in range(3)})
    MERGED[key] = dict(mesh=me, verts=verts, leafmask=leafmask, R0=R0, cb=cb, hullV=hv, hullF=F, hullN=N, hullD=D, hullE=edges, prox=pm,
                       size=np.array(t["size"]), nleaf=int(leafmask.sum()), nbody=len(bidx))
    print("R4 item", item, align, "body verts", len(bidx), "leaf-only verts", int(leafmask.sum()), "hull verts", len(hv),
          "body size", np.round(bv.max(0) - bv.min(0), 3), flush=True)
    return MERGED[key]

def pose_matrix(c, R3, s):
    return Matrix.Translation(Vector(c)) @ Matrix(R3).to_4x4() @ Matrix.Diagonal((s, s, s, 1))

def world_pts(P, M): return P @ M[:3, :3].T + M[:3, 3]

def rec_world(m, Mp, s):
    """world data of a settled body from its proxy matrix Mp (origin = body centre)."""
    M = Mp.copy(); M[:3, 3] = Mp[:3, 3] - Mp[:3, :3] @ m["cb"]      # visible item matrix (origin = item bounds centre)
    hv = world_pts(m["hullV"], Mp)
    Rw = Mp[:3, :3] / s
    N = m["hullN"] @ Rw.T; D = m["hullD"] * s + N @ Mp[:3, 3]
    return dict(M=M, Mp=Mp, s=s, hv=hv, N=N, D=D, lo=hv.min(0), hi=hv.max(0), F=m["hullF"], E=m["hullE"])

CELL = 0.02
class Crate:
    def __init__(self, ci):
        self.ci = ci; self.b = cav(ci); self.bodies = []
        self.nx = int(math.ceil((self.b[1] - self.b[0]) / CELL)); self.ny = int(math.ceil((self.b[3] - self.b[2]) / CELL))
        self.hf = np.full((self.nx, self.ny), self.b[4])
    def add_hull(self, N, D, lo, hi):
        """upper surface of a convex hull (planes N.p <= D) rasterised into the height field at the cell centres."""
        i0 = max(0, int((lo[0] - self.b[0]) / CELL)); i1 = min(self.nx - 1, int((hi[0] - self.b[0]) / CELL))
        j0 = max(0, int((lo[1] - self.b[2]) / CELL)); j1 = min(self.ny - 1, int((hi[1] - self.b[2]) / CELL))
        if i1 < i0 or j1 < j0: return
        I, J = np.meshgrid(np.arange(i0, i1 + 1), np.arange(j0, j1 + 1), indexing="ij")
        X = (I.ravel() + 0.5) * CELL + self.b[0]; Y = (J.ravel() + 0.5) * CELL + self.b[2]
        P = N[:, 0:1] * X[None, :] + N[:, 1:2] * Y[None, :]
        up = N[:, 2] > 1e-6; dn = N[:, 2] < -1e-6; ve = ~(up | dn)
        if not up.any() or not dn.any(): return
        zt = ((D[up, None] - P[up]) / N[up, 2][:, None]).min(0)
        zb = ((D[dn, None] - P[dn]) / N[dn, 2][:, None]).max(0)
        ok = zt > zb
        if ve.any(): ok &= (P[ve] <= D[ve, None]).all(0)
        zt = np.where(ok, zt, -9.0)
        cur = self.hf[I.ravel(), J.ravel()]
        self.hf[I.ravel(), J.ravel()] = np.maximum(cur, zt)
    def add_pts(self, P):
        ix = np.clip(((P[:, 0] - self.b[0]) / CELL).astype(int), 0, self.nx - 1)
        iy = np.clip(((P[:, 1] - self.b[2]) / CELL).astype(int), 0, self.ny - 1)
        np.maximum.at(self.hf, (ix, iy), P[:, 2])
    def win(self, x, y, rx, ry):
        i0 = max(0, int((x - rx - self.b[0]) / CELL)); i1 = min(self.nx - 1, int((x + rx - self.b[0]) / CELL))
        j0 = max(0, int((y - ry - self.b[2]) / CELL)); j1 = min(self.ny - 1, int((y + ry - self.b[2]) / CELL))
        return self.hf[i0:i1 + 1, j0:j1 + 1]
    def top(self, x, y, rx, ry): return float(self.win(x, y, rx, ry).max())
    def mean(self, x, y, rx, ry):
        w = self.win(x, y, rx, ry); return 0.5 * float(w.mean()) + 0.5 * float(w.max())

def Rz(a): return Euler((0, 0, math.radians(a))).to_matrix()
def Ry(a): return Euler((0, math.radians(a), 0)).to_matrix()
def Rx(a): return Euler((math.radians(a), 0, 0)).to_matrix()

# ---- support / float geometry: distance between two convex bodies (hull surfaces, edge-sampled) ----
from mathutils.bvhtree import BVHTree
def _bvh(r):
    if "bvh" not in r: r["bvh"] = BVHTree.FromPolygons([Vector(v) for v in r["hv"]], [tuple(int(i) for i in f) for f in r["F"]])
    return r["bvh"]
def _samples(r, step=0.006):
    if "smp" not in r:
        hv = r["hv"]; pts = [hv]
        for a, b in r["E"]:
            L = float(np.linalg.norm(hv[a] - hv[b])); n = int(L / step)
            if n >= 1:
                t = (np.arange(1, n + 1) / (n + 1))[:, None]; pts.append(hv[a] * (1 - t) + hv[b] * t)
        r["smp"] = np.vstack(pts)
    return r["smp"]
def inside(r, p, eps=0.0): return bool(((r["N"] @ p) - r["D"] <= eps).all())

def hull_dist(A, B):
    """(distance between the two convex hull surfaces, the contact point on A). 0 when they overlap."""
    best = (1e9, None)
    SA = _samples(A); bb = _bvh(B)
    for p in SA:
        if inside(B, p): return 0.0, p
        loc, nrm, idx, dist = bb.find_nearest(Vector(p))
        if loc is not None and dist < best[0]: best = (dist, p)
    ba = _bvh(A)
    for p in _samples(B):
        if inside(A, p): return 0.0, p
        loc, nrm, idx, dist = ba.find_nearest(Vector(p))
        if loc is not None and dist < best[0]: best = (dist, np.array(loc[:]))
    return best

def support_gap(r, floor_z, earlier):
    """distance (m) from the body to its nearest support: the crate floor, or an earlier body touching it from below
    (the contact point lies in the lower 35% of this body's height). -> (gap, 'floor'|'body k')"""
    zmin, zmax = r["lo"][2], r["hi"][2]
    gap = max(0.0, zmin - floor_z); what = "floor"
    if gap <= 0.0015: return gap, what
    span = max(zmax - zmin, 1e-6)
    for q in earlier:
        if (q["lo"] > r["hi"] + 0.02).any() or (q["hi"] < r["lo"] - 0.02).any(): continue
        d, pt = hull_dist(r, q)
        if pt is None or d >= gap: continue
        if pt[2] - zmin <= 0.35 * span + 1e-6: gap = d; what = "body"
    return gap, what

MAXF = arg("--maxf", 140); MINF = 16
VW = arg("--vw", 0.2)
DAMP_L = arg("--dl", 0.5); DAMP_A = arg("--da", 0.95)
DEBUG = '--debug' in argv
STAGES = 8
NTRY = arg("--ntry", 14, int)
MARGIN = 0.0015                              # collision margin: 1.5 mm to the floor/walls, 3 mm between two bodies
LEAF_FLOOR = 0.06                            # leaves may reach this far below the floor top (into straw + slats, never visible)
FLOAT_MAX = 0.005
SPAWN_MG = arg('--mg', 0.012)
TILT = {"pile": 35, "row": 55}

def simulate(units):
    rr = random.Random(arg("--seed", 5, int))
    bpy.ops.rigidbody.world_add()
    rbw = sc.rigidbody_world
    sc.frame_start = 1; sc.frame_end = 900
    rbw.point_cache.frame_start = 1; rbw.point_cache.frame_end = 900
    rbw.substeps_per_frame = 20; rbw.solver_iterations = 40
    def set_rb(ob, typ, mass):
        with bpy.context.temp_override(object=ob, active_object=ob, selected_objects=[ob], selected_editable_objects=[ob]):
            bpy.ops.rigidbody.object_add(type=typ)
        rb = ob.rigid_body
        rb.friction = 0.8; rb.restitution = 0.0; rb.mass = mass
        rb.linear_damping = DAMP_L; rb.angular_damping = DAMP_A
        if typ == "ACTIVE":
            rb.use_deactivation = True; rb.deactivate_linear_velocity = arg("--sl", 0.08); rb.deactivate_angular_velocity = arg("--sa", 0.4)
        return rb
    def add_box(lo, hi):
        me = bpy.data.meshes.new("col")
        bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0); bm.to_mesh(me); bm.free()
        ob = bpy.data.objects.new("col", me); sc.collection.objects.link(ob)
        ob.scale = [hi[i] - lo[i] for i in range(3)]; ob.location = [(hi[i] + lo[i]) / 2 for i in range(3)]
        rb = set_rb(ob, "PASSIVE", 1.0); rb.collision_shape = "BOX"; rb.use_margin = True; rb.collision_margin = 0.0
        return ob
    inset = 0.002; T = 0.03
    crates = {}
    for ci in range(9):
        x0, x1, y0, y1, z0, z1 = cav(ci); crates[ci] = Crate(ci)
        if ci not in ONLY: continue
        H = z1 - z0 + 0.06
        add_box((x0 - T, y0 - T, z0 - 0.1), (x1 + T, y1 + T, z0))
        add_box((x0 - T, y0 - T, z0 - 0.1), (x0 + inset, y1 + T, z0 + H))
        add_box((x1 - inset, y0 - T, z0 - 0.1), (x1 + T, y1 + T, z0 + H))
        add_box((x0 - T, y0 - T, z0 - 0.1), (x1 + T, y0 + inset, z0 + H))
        add_box((x0 - T, y1 - inset, z0 - 0.1), (x1 + T, y1 + T, z0 + H))
    st = dict(frames=0, drops=0, tries=0, rej=dict(), unsettled=0)
    allr = []
    PROBE = np.array([[1, 0, 0], [-1, 0, 0], [0, 1, 0], [0, -1, 0], [0, 0, 1], [0, 0, -1]], float)

    def spawn(w):
        """pick an orientation, then the lowest feasible spot (leaves must fit under the ceiling and inside the walls)."""
        u, cp, k = w["u"], w["cp"], w["k"]; cr = crates[u["crate"]]
        m = merged(u["item"], cp["align"]); s = place(u["item"], cp)[1]; w["s"] = s
        if cp["align"] == "long_x":
            if u["kind"] == "bundle":
                yaw = rr.uniform(-14, 14) + (180 if k % 2 else 0); Rc = Rz(yaw) @ Ry(rr.uniform(-4, 4)) @ Rx(rr.uniform(-25, 25))
            else:
                yaw = rr.uniform(-12, 12) + (180 if k % 2 else 0); Rc = Rz(yaw) @ Ry(rr.uniform(-5, 5)) @ Rx(rr.uniform(-20, 20))
        else:
            t = TILT.get(u["kind"], 30)
            Rc = Rz(rr.uniform(0, 360)) @ Rx(rr.uniform(-t, t)) @ Ry(rr.uniform(-t, t))
        Rn = np.array(Rc)
        HV = (m["hullV"] @ Rn.T) * s
        AV = ((m["verts"] - m["cb"]) @ Rn.T) * s
        lo, hi = AV.min(0), AV.max(0)
        low = -HV[:, 2].min()
        x0, x1, y0, y1, z0, z1 = cr.b; mg = SPAWN_MG
        ex = w.setdefault("extra", np.zeros(5))        # grows by what a failed try overshot: the pile slopes the same way next time
        xr = (x0 - lo[0] + mg + ex[0], x1 - hi[0] - mg - ex[1]); yr = (y0 - lo[1] + mg + ex[2], y1 - hi[1] - mg - ex[3])
        if xr[0] > xr[1] or yr[0] > yr[1]: return False, "plan"
        rx = (HV[:, 0].max() - HV[:, 0].min()) / 2; ry = (HV[:, 1].max() - HV[:, 1].min()) / 2
        ux, uy, uz = u["pos"]
        xs = np.arange(xr[0], xr[1] + 1e-9, CELL) if xr[1] - xr[0] > CELL else np.array([(xr[0] + xr[1]) / 2])
        ys = np.arange(yr[0], yr[1] + 1e-9, CELL) if yr[1] - yr[0] > CELL else np.array([(yr[0] + yr[1]) / 2])
        clear = 0.02 if u["kind"] == "pile" else 0.012
        best = None
        for xx in xs:
            for yy in ys:
                zc = cr.top(xx, yy, max(rx, 0.03) + CELL, max(ry, 0.03) + CELL) + low + clear
                if zc + hi[2] > z1 - mg - ex[4]: continue
                cost = cr.mean(xx, yy, rx, ry) + VW * math.hypot(xx - ux, yy - uy) + rr.uniform(0, 0.006)
                if best is None or cost < best[0]: best = (cost, xx, yy)
        if best is None: return False, "ceiling"
        x = min(max(best[1] + rr.uniform(-0.004, 0.004), xr[0]), xr[1]); y = min(max(best[2] + rr.uniform(-0.004, 0.004), yr[0]), yr[1])
        zc = cr.top(x, y, max(rx, 0.03) + CELL, max(ry, 0.03) + CELL) + low + clear
        ob = bpy.data.objects.new(u["item"], m["prox"]); sc.collection.objects.link(ob)
        ob.matrix_world = pose_matrix((x, y, zc), Rc, s)
        ext = HV.max(0) - HV.min(0)
        rb = set_rb(ob, "ACTIVE", max(0.02, float(np.prod(ext)) * 600))
        rb.collision_shape = "CONVEX_HULL"; rb.mesh_source = "BASE"; rb.use_margin = True; rb.collision_margin = MARGIN
        w.update(ob=ob, m=m, start=[round(v, 3) for v in (x, y, zc)], probe=PROBE * 0.5 * ext)
        return True, ""

    def evaluate(w):
        """body-only support + cavity test of a settled try. -> (ok, why, rec)"""
        m = w["m"]; ci = w["u"]["crate"]; cr = crates[ci]
        r = rec_world(m, w["Mp"], w["s"])
        r.update(ci=ci, u=w["u"], k=w["k"], item=w["u"]["item"], align=w["cp"]["align"], s=w["s"], id=w["id"])
        V = world_pts(m["verts"], r["M"]); lm = m["leafmask"]
        x0, x1, y0, y1, z0, z1 = cr.b; e = 0.0005
        bad = []
        if (V[~lm][:, 2] < z0 - 0.002).any(): bad.append("body below floor")
        if lm.any() and (V[lm][:, 2] < z0 - LEAF_FLOOR).any(): bad.append("leaf deep in floor")
        if (V[:, 0].min() < x0 + e) or (V[:, 0].max() > x1 - e) or (V[:, 1].min() < y0 + e) or (V[:, 1].max() > y1 - e): bad.append("outside walls")
        if V[:, 2].max() > z1 - e: bad.append("above ceiling")
        if bad:
            w["extra"] = w.get("extra", np.zeros(5)) + np.maximum(0, [x0 - V[:, 0].min() + 0.003, V[:, 0].max() - x1 + 0.003, y0 - V[:, 1].min() + 0.003, V[:, 1].max() - y1 + 0.003, V[:, 2].max() - z1 + 0.003]) * np.array(
                [("outside walls" in bad[0] or "outside walls" in ",".join(bad)) and 1 or 0] * 4 + [("above ceiling" in ",".join(bad)) and 1 or 0])
        if DEBUG and bad: print("R4 dbg", w["u"]["item"], bad, "start", w["start"], "end", np.round(w["Mp"][:3, 3], 3), "V x %.3f..%.3f y %.3f..%.3f z..%.3f" % (V[:, 0].min(), V[:, 0].max(), V[:, 1].min(), V[:, 1].max(), V[:, 2].max()), "cav", np.round(cr.b, 3), flush=True)
        gap, what = support_gap(r, z0, cr.bodies)
        r["gap"] = gap; r["support"] = what
        if gap > FLOAT_MAX: bad.append("floats %.1f mm" % (gap * 1000))
        return (not bad), ",".join(bad), r

    def freeze_into_world(r, ob):
        sc.frame_set(1)
        ob.matrix_world = Matrix(r["Mp"].tolist()); ob.rigid_body.type = "PASSIVE"
        ob.rigid_body.use_margin = True; ob.rigid_body.collision_margin = MARGIN
        crates[r["ci"]].bodies.append(r)
        crates[r["ci"]].add_hull(r["N"], r["D"], r["lo"], r["hi"])

    def attempt(pending):
        sc.frame_set(1)
        ok = []
        for w in pending:
            good, why = spawn(w)
            if good: ok.append(w)
            else:
                w["why"] = why; st["rej"][why] = st["rej"].get(why, 0) + 1
        if not ok: return [], 0
        bpy.context.view_layer.update()
        prev = {}; f = 1
        for f in range(2, MAXF + 2):
            sc.frame_set(f); st["frames"] += 1
            if f >= MINF and f % 3 == 0:
                dg = bpy.context.evaluated_depsgraph_get(); mx = 0.0
                for w in ok:
                    pts = world_pts(w["probe"], np.array(w["ob"].evaluated_get(dg).matrix_world))
                    if w["id"] in prev: mx = max(mx, float(np.abs(pts - prev[w["id"]]).max()))
                    prev[w["id"]] = pts
                if mx < 6e-4 and f > MINF + 3: break
        dg = bpy.context.evaluated_depsgraph_get()
        for w in ok: w["Mp"] = np.array(w["ob"].evaluated_get(dg).matrix_world)
        return ok, f

    def run_batch(batch):
        pending = list(batch); tries = 0
        while pending and tries < NTRY:
            tries += 1; st["tries"] += 1
            ok, f = attempt(pending)
            failed = [w for w in pending if w not in ok]
            accepted = []
            for w in ok:
                good, why, r = evaluate(w)
                if good:
                    r["unsettled"] = f >= MAXF + 1
                    accepted.append((w, r))
                else:
                    key = "".join(ch for ch in why.split(",")[0] if not (ch.isdigit() or ch == ".")).strip(" ")
                    w["why"] = why; st["rej"][key] = st["rej"].get(key, 0) + 1
                    failed.append(w)
            for w in ok:                                  # remove every try object, then re-add the accepted ones as frozen bodies
                if w in failed: bpy.data.objects.remove(w["ob"])
            sc.frame_set(1)
            for w, r in accepted:
                freeze_into_world(r, w["ob"]); allr.append(r)
                if r["unsettled"]: st["unsettled"] += 1
            pending = failed
        st["drops"] += len(pending)
        if pending and DEBUG: print("R4 dropped", [(w["u"]["item"], w["u"]["crate"], w["k"], w.get("why")) for w in pending], flush=True)

    uid = 0; tstart = time.time()
    for stage in range(STAGES):
        sel = [u for u in units if u["index"] % 8 == stage and u["copies"]]
        if not sel: continue
        nmax = max(len(u["copies"]) for u in sel)
        for sb in range(nmax):
            batch = []
            for u in sel:
                if sb < len(u["copies"]): batch.append(dict(u=u, cp=u["copies"][sb], k=sb, id=uid)); uid += 1
            run_batch(batch)
        print("R4 stage", stage, "bodies", len(allr), "frames", st["frames"], "tries", st["tries"], "dropped", st["drops"], "t=%.0fs" % (time.time() - tstart), flush=True)
    res = list(allr)
    for o in [o for o in bpy.data.objects if o.rigid_body is not None]: bpy.data.objects.remove(o)
    bpy.ops.rigidbody.world_remove()
    sc.frame_set(1)
    return res, dict(frames=st["frames"], tries=st["tries"], dropped=st["drops"], unsettled=st["unsettled"], rejections=st["rej"])

def interpenetration(res):
    """largest depth (m) of a hull vertex of one body inside the hull of another."""
    lo = np.array([r["lo"] for r in res]); hi = np.array([r["hi"] for r in res])
    worst = 0.0; wp = None; deps = []
    for i, a in enumerate(res):
        ov = np.where(((lo <= a["hi"]) & (hi >= a["lo"])).all(1))[0]
        for j in ov:
            if j == i: continue
            b = res[j]
            d = b["D"][None, :] - a["hv"] @ b["N"].T
            ins = (d > 0).all(1)
            if ins.any():
                dep = float(d[ins].min(1).max()); deps.append(dep)
                if dep > worst: worst = dep; wp = (a["item"], b["item"])
    return worst, (float(np.mean(deps)) if deps else 0.0), len(deps), wp

def float_check(res):
    """every body vs the bodies dropped BEFORE it (what exists when only earlier stacks are shown)."""
    by = {}
    out = []
    for r in sorted(res, key=lambda r: r["id"]):
        cr = cav(r["ci"]); earlier = by.setdefault(r["ci"], [])
        g, what = support_gap(r, cr[4], earlier)
        out.append((g, what, r["item"], r["ci"], r["k"], r["u"]["index"]))
        earlier.append(r)
    out.sort(key=lambda x: -x[0])
    n_over = sum(1 for o in out if o[0] > FLOAT_MAX)
    print("FLOAT worst 5 (mm to nearest support):", [(round(o[0] * 1000, 2), o[1], o[2], "crate %d stack %d copy %d" % (o[3], o[5] % 8, o[4])) for o in out[:5]])
    print("FLOAT over %.0f mm:" % (FLOAT_MAX * 1000), n_over, "of", len(out), "; mean gap %.2f mm" % (1000 * np.mean([o[0] for o in out])))
    return out, n_over

def clip_check(res):
    """A copy clips if a vertex leaves the crate cavity (ceiling included) or a vertex near a wall/ceiling/floor lies inside a frame part.
    Leaves (alpha cards) may reach LEAF_FLOOR below the floor top (inside straw + slats, hidden); walls and ceiling are strict for all verts."""
    parts = []
    for o in PARTS:
        vs = [v.co.copy() for v in o.data.vertices]
        bvh = BVHTree.FromPolygons(vs, [tuple(p.vertices) for p in o.data.polygons])
        a = np.array([v[:] for v in vs]); parts.append((a.min(0), a.max(0), bvh))
    LO = np.array([p[0] for p in parts]); HI = np.array([p[1] for p in parts])
    d = Vector((0.267, 0.534, 0.802)).normalized()
    def inside_p(bvh, p):
        o = p.copy(); n = 0
        while True:
            hit = bvh.ray_cast(o, d)
            if hit[0] is None: break
            n += 1; o = hit[0] + d * 1e-4
        return n % 2 == 1
    bad = []; notes = []; maxtop = -9; maxout = 0; leaf_under = 0.0
    for r in res:
        m = merged(r["item"], r["align"]); V = world_pts(m["verts"], r["M"]); lm = m["leafmask"]
        cx0, cx1, cy0, cy1, cz0, cz1 = cav(r["ci"]); why = None
        zlim = np.where(lm, cz0 - LEAF_FLOOR, cz0)
        over = max(cx0 - V[:, 0].min(), V[:, 0].max() - cx1, cy0 - V[:, 1].min(), V[:, 1].max() - cy1, float((zlim - V[:, 2]).max()), V[:, 2].max() - cz1)
        maxtop = max(maxtop, V[:, 2].max() - cz1); maxout = max(maxout, over)
        if lm.any(): leaf_under = max(leaf_under, cz0 - V[lm][:, 2].min())
        if over > 0:
            why = "outside cavity by %.3f (top vs ceiling %+.3f)" % (over, V[:, 2].max() - cz1)
        else:
            nearw = (V[:, 0] - cx0 < 0.03) | (cx1 - V[:, 0] < 0.03) | (V[:, 1] - cy0 < 0.03) | (cy1 - V[:, 1] < 0.03) | (cz1 - V[:, 2] < 0.03)
            nearf = (V[:, 2] - cz0 < 0.01) & (~lm)
            nearw &= ~(lm & (V[:, 2] < cz0))      # leaf verts inside the floor are the allowed, hidden ones
            for q in V[nearw | nearf]:
                cand = np.where(((q >= LO) & (q <= HI)).all(1))[0]
                for c in cand:
                    if inside_p(parts[c][2], Vector(q)):
                        why = "inside frame part %s leaf=%s at %s (cavity x %.2f..%.2f y %.2f..%.2f z %.2f..%.2f)" % (PARTS[c].name, bool(lm[np.where((V == q).all(1))[0][0]]), np.round(q, 3), cx0, cx1, cy0, cy1, cz0, cz1); break
                if why: break
        if why: bad.append((r["u"]["index"], r["k"])); notes.append((r["u"]["index"], r["k"], r["item"], why))
    from collections import Counter
    print("CLIPPING by crate", dict(Counter(r[0] // 8 for r in bad)))
    print("CLIPPING", len(bad), "of", len(res), notes[:8], "highest top vs ceiling %+.3f" % maxtop, "max outside %.4f" % maxout,
          "deepest leaf under floor top %.3f" % leaf_under)
    return len(bad)

# --- Unity conversion: Blender z-up/-y front -> Unity y-up/+z front: ux=-bx, uy=bz, uz=-by ---
MC = Matrix(((-1, 0, 0), (0, 0, 1), (0, -1, 0)))
def uvec(v): return [round(-v[0], 4), round(v[2], 4), round(-v[1], 4)]
def urot(Rb):
    Ru = MC @ Rb @ MC.transposed()
    x = math.asin(max(-1, min(1, -Ru[1][2]))); y = math.atan2(Ru[0][2], Ru[2][2]); z = math.atan2(Ru[1][0], Ru[1][1])
    q = Ru.to_quaternion()
    return [round(math.degrees(a), 2) for a in (x, y, z)], [round(c, 5) for c in (q.x, q.y, q.z, q.w)]

def export_anchors(units, res, stats):
    by = {}
    for r in res: by.setdefault(r["u"]["index"], []).append(r)
    out_units = []
    for u in units:
        cps = []
        for r in sorted(by.get(u["index"], []), key=lambda r: r["k"]):
            m = merged(r["item"], r["align"]); M = r["M"]; s = r["s"]
            Rw = Matrix((M[:3, :3] / s).tolist()); Rc = Rw @ m["R0"].inverted()
            eu, q = urot(Rc)
            asz = [abs(x) for x in (m["R0"] @ Vector(m["size"]))]
            c = Vector(M[:3, 3].tolist()) - Vector(u["pos"])
            fx, fy, fz = [round(a * s, 6) + 1e-6 for a in asz]
            cps.append({"offset": uvec(c), "rot_euler_deg": eu, "rot_quat_xyzw": q, "fit_box": [fx, fz, fy], "anchor": "center", "align": r["align"],
                        "order": r["k"], "body_gap_mm": round(r["gap"] * 1000, 2)})
        w, dd, h = u["box"]
        out_units.append({"index": u["index"], "kind": u["kind"], "crate": u["crate"], "slot_in_crate": u["index"] % 8, "tier": u["tier"], "layer": u["layer"],
                          "position": uvec(u["pos"]), "rotation_euler_deg": [0, 0, 0], "box_size": [w, h, dd],
                          "example_item": u["item"], "copies": cps})
    crates = []
    for ci in range(9):
        tn, zT, y0 = TIERS[ci // 3]; bx = BAYS[ci % 3]
        crates.append({"crate": ci, "tier": tn, "class": CLASSES[ci], "label": CRATE_LABEL[ci],
                       "floor_centre": uvec((bx, y0 + (CAV_Y0 + CAV_Y1) / 2, zT + 0.003)),
                       "cavity_size": [CAV_HW * 2, CEIL[tn] - 0.003, CAV_Y1 - CAV_Y0]})
    doc = {"slug": "rootbin", "round": 4, "frame_obj": "RootBin.obj", "atlas": "rootbin_atlas.png",
           "slots": len(units), "units": out_units, "crates": crates,
           "conversion": {"blender": "z-up, -y front, metres", "unity": "y-up, +z front",
                          "position": "ux=-bx, uy=bz, uz=-by", "rotation": "Ru = M Rb M^T with M rows (-1,0,0),(0,0,1),(0,-1,0); euler order Unity ZXY (Quaternion.Euler)",
                          "frame_obj_export": "forward NEGATIVE_Z, up Y, Blender obj exporter, Unity import flips x"},
           "placement_rule": {
               "unit": "position = bottom-centre of the nominal box in prefab space; rotation_euler_deg is the unit rotation (all 0). The box is only nominal: settled copies lie where physics put them and may leave it; the crate cavity is the real container.",
               "copy": ("SETTLED transform, in unit-local space. Scale the item's own model uniformly so its renderer bounds, after the alignment, fit inside fit_box (contain-fit; fit_box IS the aligned scaled bounds, so the scale is exact; it differs per crate, mass storage keeps the layouts' own item sizes). align 'up' = item as it comes; align 'long_x' = first rotate the item so its longest bounds axis lies along "
                        "the unit's width axis (item +long axis -> Blender +x = Unity -x). Then rotate by rot_euler_deg about the bounds centre. anchor 'center': the bounds centre (leaves included) of the (aligned, unrotated) "
                        "scaled item sits at offset, then the rotation applies about that centre. Copies are listed in drop order (order)."),
               "fill": "units are listed in fill order, crate by crate. Crate-wise fill: a crate holding n stacks shows its first n units (slot_in_crate 0..7); global fill: the first round(f * slots) units. One unit = one full stack of one item type. Stack k was dropped onto stacks 0..k-1 after those were frozen, so adding stacks never moves earlier ones.",
               "classes": "a crate has one class (pile / bundle / sheaf / row): put an item in a crate of its shape class (round or leafy, long, tied plant, cap)."},
           "physics": {"method": "Blender rigid body (Bullet): crate floor and walls = passive boxes, items = active convex hulls of the item BODY only (alpha-clipped leaf material excluded; leaves ride along with no collision), "
                                 "friction 0.8, restitution 0, damping %.2f/%.2f, margin %.1f mm, substeps 20, solver iterations 40; one stack's copy per crate settled and frozen before the next. A try is rejected and re-dropped if a body is farther than %.0f mm from its support (floor or an earlier body below), or any vertex (leaves included) leaves the cavity (leaves may sink into the floor)." % (DAMP_L, DAMP_A, MARGIN * 1000, FLOAT_MAX * 1000)},
           "stats": stats}
    json.dump(doc, open(os.path.join(OUTA, "rootbin_anchors.json" if not PARTIAL else "rootbin_anchors_partial.json"), "w"), indent=1)

SPACING = 2.75
units = unit_list()
for u in units:
    if u["crate"] not in ONLY: u["copies"] = []; continue
    settle(u)
    for cp in u["copies"]: cp["fit"] = [x * SHRINK.get(u["crate"], 1.0) for x in cp["fit"]]
t0 = time.time()
res, sstats = simulate(units)
print("R4 SIM done", {k: v for k, v in sstats.items()}, "%.0fs" % (time.time() - t0), flush=True)
pen, penmean, npairs, wp = interpenetration(res)
print("R4 INTERPEN max %.2f mm mean %.2f mm over %d touching pairs" % (pen * 1000, penmean * 1000, npairs), wp)
fl, n_over = float_check(res)
for ci in ONLY:
    gs = [o[0] for o in fl if o[3] == ci]
    print("   crate", ci, CRATE_LABEL[ci], "copies", len(gs), "max gap %.2f mm" % (1000 * max(gs) if gs else 0))

for k, fill in enumerate(reversed(FILLS)):
    rng.seed(7); PARTS.clear()
    build_frame()
    xoff = (len(FILLS) - 1 - k) * SPACING - SPACING
    if k == 0:
        nclip = clip_check(res)
        stats = {"frame_tris": tris(PARTS), "slots": len(units), "copies_total": len(res), "clipping": nclip,
                 "dropped_copies": sstats["dropped"], "max_interpenetration_mm": round(pen * 1000, 2),
                 "mean_interpenetration_mm": round(penmean * 1000, 2), "sim_frames": sstats["frames"], "unsettled_bodies": sstats["unsettled"],
                 "float_over_5mm": n_over, "float_worst_mm": round(fl[0][0] * 1000, 2) if fl else 0}
        if not PARTIAL:
            bpy.ops.object.select_all(action="DESELECT")
            for o in PARTS: o.select_set(True)
            bpy.ops.wm.obj_export(filepath=os.path.join(OUTA, "RootBin.obj"), export_selected_objects=True, export_materials=False,
                                  export_triangulated_mesh=True, forward_axis="NEGATIVE_Z", up_axis="Y")
        export_anchors(units, res, stats)
        print("ROOTBIN", stats)
    ob = join(PARTS, f"rootbin_{int(fill * 100)}"); ob.location.x = xoff
    nper = round(fill * 8)
    for r in res:
        if r["u"]["index"] % 8 < nper:
            m = merged(r["item"], r["align"])
            io = bpy.data.objects.new(r["item"], m["mesh"]); sc.collection.objects.link(io)
            io.matrix_world = Matrix.Translation((xoff, 0, 0)) @ Matrix(r["M"].tolist())

# player-height marker (plain 1.8 m post) and the vanilla wood chest, for scale (reference only, never exported)
pm = bpy.data.materials.new("marker"); pm.use_nodes = True
pm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.55, 0.55, 0.57, 1)
bpy.ops.mesh.primitive_cube_add(size=1.0); post = bpy.context.active_object
post.scale = (0.10, 0.10, 1.8); post.location = (-6.2, 0, 0.9); post.data.materials.append(pm)
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
        verts = [Vector((-v.x - 5.0, -v.z, v.y)) for v in verts]
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
cam.data.lens = 38
sc.render.engine = "BLENDER_EEVEE_NEXT"
sc.render.resolution_x, sc.render.resolution_y = 1600, 900
sc.view_settings.view_transform = "Standard"
def crate_tgt(ci, xo=SPACING):
    tn, zT, y0 = TIERS[ci // 3]; return (xo + BAYS[ci % 3], y0 + (CAV_Y0 + CAV_Y1) / 2, zT + 0.12)
VIEWS = {"fills": (-3, 12, 12.2, (-1.45, 0, 0.95)), "close": (-22, 24, 5.7, (SPACING, 0, 1.0)),
         "alt": (50, 30, 6.2, (SPACING, 0, 1.0)),
         "carrots": (-6, 52, 1.15, crate_tgt(1)), "carrots_side": (-30, 28, 1.05, crate_tgt(1)),
         "turnips": (-6, 52, 1.15, crate_tgt(0)), "onions": (-6, 50, 1.25, crate_tgt(6))}
want = argv[argv.index("--views") + 1].split(",") if "--views" in argv else list(VIEWS)
for vn, (yaw, pitch, dist, tgt) in VIEWS.items():
    if vn not in want: continue
    t = Vector(tgt)
    d = Vector((math.cos(math.radians(pitch)) * math.sin(math.radians(yaw)),
                -math.cos(math.radians(pitch)) * math.cos(math.radians(yaw)), math.sin(math.radians(pitch))))
    cam.location = t + d * dist; cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    sc.render.resolution_y = 640 if vn == "fills" else 900
    sc.render.filepath = os.path.join(OUT, f"{TAG}-{vn}.png")
    bpy.ops.render.render(write_still=True)
print("DONE")
