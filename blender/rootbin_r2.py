"""Root Bin, round 2: a 2 m wide, 2 m tall stepped produce stand, nine slatted crates in three terraces, 72 slots.
Our own furniture mesh + own 128 px point-filtered atlas. The CONTENTS are NOT modelled here: the mod places the game's
own item models at the anchors this script exports (rootbin_anchors.json). For the renders the extracted item models
from C:/Users/joost/ValheimRip/items are used (local reference only, never exported).
Run: blender -b -P rootbin_r2.py -- [--out DIR] [--tag NAME] [--no-ref]

Writes into assets/rootbin_r2/: RootBin.obj (frame only, forward -Z, up Y, triangulated, no materials),
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
OUTA = os.path.normpath(os.path.join(HERE, "..", "assets", "rootbin_r2"))
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
SCR = "C:/Users/joost/AppData/Local/Temp/claude/C--Users-joost--pai/5e4bc60b-cdfe-4638-8e29-2e507fa13cf9/scratchpad/proto2/rootbin"
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

def instance_unit(u, offset, cache):
    """link one object per mesh of the item, per copy; returns the world-ish vertex arrays (local coords) for checking."""
    pw = []
    for cp in u["copies"]:
        R, s, cen, asz = place(u["item"], cp)
        t = tpl(u["item"])
        M = Matrix.Translation(Vector(u["pos"]) + cen + Vector(offset)) @ R.to_4x4() @ Matrix.Diagonal((s, s, s, 1))
        for d in t["datas"]:
            ob = bpy.data.objects.new(u["item"], d); sc.collection.objects.link(ob); ob.matrix_world = M
        Rn = np.array(R); V = (t["verts"] * s) @ Rn.T + np.array(u["pos"] + np.zeros(3)) + np.array(cen)
        pw.append(V)
    return pw

def cavity(u):
    tn, zT, y0 = TIERS[u["crate"] // 3]; bx = BAYS[u["crate"] % 3]
    return (bx - CAV_HW, bx + CAV_HW, y0 + CAV_Y0, y0 + CAV_Y1, zT + 0.003, zT + CEIL[tn])

def clip_check(units, perunit):
    """A unit clips if its box leaves the crate cavity, an item vertex leaves the cavity, or a vertex near the cavity wall
    lies inside a frame part (ray parity on that part). Items must also stay inside their unit box (tolerance 12 mm)."""
    from mathutils.bvhtree import BVHTree
    parts = []
    for o in PARTS:
        vs = [v.co.copy() for v in o.data.vertices]
        bvh = BVHTree.FromPolygons(vs, [tuple(p.vertices) for p in o.data.polygons])
        a = np.array([v[:] for v in vs]); parts.append((a.min(0), a.max(0), bvh))
    d = Vector((0.267, 0.534, 0.802)).normalized()
    def inside(bvh, p):
        o = p.copy(); n = 0
        while True:
            hit = bvh.ray_cast(o, d)
            if hit[0] is None: break
            n += 1; o = hit[0] + d * 1e-4
        return n % 2 == 1
    bad = []; notes = []
    for u, pw in zip(units, perunit):
        cx0, cx1, cy0, cy1, cz0, cz1 = cavity(u)
        px, py, pz = u["pos"]; w, dd, h = u["box"]
        why = None
        if px - w / 2 < cx0 or px + w / 2 > cx1 or py - dd / 2 < cy0 or py + dd / 2 > cy1 or pz < cz0 or pz + h > cz1:
            why = "box outside cavity"
        else:
            for V in pw:
                if (V[:, 0].min() < cx0 or V[:, 0].max() > cx1 or V[:, 1].min() < cy0 or V[:, 1].max() > cy1
                        or V[:, 2].min() < cz0 or V[:, 2].max() > cz1):
                    why = "item outside cavity x%+.3f/%+.3f y%+.3f/%+.3f z%+.3f/%+.3f" % (
                        V[:, 0].min() - cx0, cx1 - V[:, 0].max(), V[:, 1].min() - cy0, cy1 - V[:, 1].max(), V[:, 2].min() - cz0, cz1 - V[:, 2].max()); break
                if (V[:, 0].min() < px - w / 2 - 0.012 or V[:, 0].max() > px + w / 2 + 0.012 or V[:, 1].min() < py - dd / 2 - 0.012
                        or V[:, 1].max() > py + dd / 2 + 0.012 or V[:, 2].max() > pz + h + 0.012 or V[:, 2].min() < pz - 0.012):
                    why = "item outside unit box x%+.3f/%+.3f y%+.3f/%+.3f z%+.3f/%+.3f" % (
                        V[:, 0].min() - (px - w / 2), px + w / 2 - V[:, 0].max(), V[:, 1].min() - (py - dd / 2), py + dd / 2 - V[:, 1].max(),
                        V[:, 2].min() - pz, pz + h - V[:, 2].max()); break
                near = V[(V[:, 0] - cx0 < 0.03) | (cx1 - V[:, 0] < 0.03) | (V[:, 1] - cy0 < 0.03) | (cy1 - V[:, 1] < 0.03)
                         | (V[:, 2] - cz0 < 0.03) | (cz1 - V[:, 2] < 0.03)]
                for q in near:
                    for lo, hi, bvh in parts:
                        if (q >= lo).all() and (q <= hi).all() and inside(bvh, Vector(q)):
                            why = "inside frame part"; break
                    if why: break
                if why: break
        if why: bad.append(u["index"]); notes.append((u["index"], u["item"], why))
    print("CLIPPING", len(bad), "of", len(units), notes)
    return len(bad)

# --- Unity conversion: Blender z-up/-y front -> Unity y-up/+z front: ux=-bx, uy=bz, uz=-by ---
MC = Matrix(((-1, 0, 0), (0, 0, 1), (0, -1, 0)))
def uvec(v): return [round(-v[0], 4), round(v[2], 4), round(-v[1], 4)]
def urot(Rb):
    Ru = MC @ Rb @ MC.transposed()
    x = math.asin(max(-1, min(1, -Ru[1][2]))); y = math.atan2(Ru[0][2], Ru[2][2]); z = math.atan2(Ru[1][0], Ru[1][1])
    q = Ru.to_quaternion()
    return [round(math.degrees(a), 2) for a in (x, y, z)], [round(c, 5) for c in (q.x, q.y, q.z, q.w)]

def export_anchors(units, stats):
    out_units = []
    for u in units:
        cps = []
        for cp in u["copies"]:
            Rc = Euler([math.radians(a) for a in cp["euler"]], "XYZ").to_matrix()
            eu, q = urot(Rc)
            fx, fy, fz = cp["fit"]
            cps.append({"offset": uvec(cp["pos"]), "rot_euler_deg": eu, "rot_quat_xyzw": q, "fit_box": [fx, fz, fy],
                        "anchor": cp["anchor"], "align": cp["align"]})
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
    doc = {"slug": "rootbin", "round": 2, "frame_obj": "RootBin.obj", "atlas": "rootbin_atlas.png",
           "slots": len(units), "units": out_units, "crates": crates,
           "conversion": {"blender": "z-up, -y front, metres", "unity": "y-up, +z front",
                          "position": "ux=-bx, uy=bz, uz=-by", "rotation": "Ru = M Rb M^T with M rows (-1,0,0),(0,0,1),(0,-1,0); euler order Unity ZXY (Quaternion.Euler)",
                          "frame_obj_export": "forward NEGATIVE_Z, up Y, Blender obj exporter, Unity import flips x"},
           "placement_rule": {
               "unit": "position = bottom-centre of the box in prefab space; rotation_euler_deg is the unit rotation (all 0). box_size = (x width, y height, z depth) metres, the space the unit may fill.",
               "copy": ("per copy, in unit-local space: scale the item's own model uniformly so its renderer bounds, after the alignment, fit inside fit_box (x,y,z) "
                        "(contain-fit). align 'up' = item as it comes; align 'long_x' = first rotate the item so its longest bounds axis lies along the unit's width axis "
                        "(item +long axis -> Blender +x = Unity -x). Then rotate by rot_euler_deg about the bounds centre. anchor 'bottom': the bottom-centre of the "
                        "(aligned, unrotated) scaled bounds sits at offset; anchor 'center': the bounds centre sits at offset."),
               "fill": "units are listed in fill order, crate by crate. Crate-wise fill: a crate holding n stacks shows its first n units (slot_in_crate 0..7); global fill: the first round(f * slots) units. One unit = one full stack of one item type.",
               "classes": "a crate has one class (pile / bundle / sheaf / row): put an item in a crate of its shape class (round or leafy, long, tied plant, cap)."},
           "stats": stats}
    json.dump(doc, open(os.path.join(OUTA, "rootbin_anchors.json"), "w"), indent=1)

SPACING = 2.75
units = unit_list()
for u in units: settle(u)
for k, fill in enumerate(reversed(FILLS)):
    rng.seed(7); PARTS.clear()
    build_frame()
    xoff = (len(FILLS) - 1 - k) * SPACING - SPACING
    if k == 0:
        # clip check needs per-copy vertices in frame space; instance at offset 0 later is the same geometry
        perunit = []
        for u in units:
            pw = []
            for cp in u["copies"]:
                R, s, cen, asz = place(u["item"], cp); t = tpl(u["item"])
                pw.append((t["verts"] * s) @ np.array(R).T + np.array(u["pos"]) + np.array(cen))
            perunit.append(pw)
        nclip = clip_check(units, perunit)
        copies = sum(len(u["copies"]) for u in units)
        ftris = tris(PARTS)
        stats = {"frame_tris": ftris, "slots": len(units), "copies_total": copies, "clipping": nclip}
        bpy.ops.object.select_all(action="DESELECT")
        for o in PARTS: o.select_set(True)
        bpy.ops.wm.obj_export(filepath=os.path.join(OUTA, "RootBin.obj"), export_selected_objects=True, export_materials=False,
                              export_triangulated_mesh=True, forward_axis="NEGATIVE_Z", up_axis="Y")
        export_anchors(units, stats)
        print("ROOTBIN", stats)
    ob = join(PARTS, f"rootbin_{int(fill * 100)}"); ob.location.x = xoff
    nper = round(fill * 8)          # every crate at the same fraction of its own 8 stacks, in the crate's own order
    for u in units:
        if u['index'] % 8 < nper: instance_unit(u, (xoff, 0, 0), None)

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
VIEWS = {"fills": (-3, 12, 12.2, (-1.45, 0, 0.95)), "close": (-22, 24, 5.7, (SPACING, 0, 1.0)),
         "alt": (50, 30, 6.2, (SPACING, 0, 1.0))}
for vn, (yaw, pitch, dist, tgt) in VIEWS.items():
    t = Vector(tgt)
    d = Vector((math.cos(math.radians(pitch)) * math.sin(math.radians(yaw)),
                -math.cos(math.radians(pitch)) * math.cos(math.radians(yaw)), math.sin(math.radians(pitch))))
    cam.location = t + d * dist; cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    sc.render.resolution_y = 640 if vn == "fills" else 900
    sc.render.filepath = os.path.join(OUT, f"{TAG}-{vn}.png")
    bpy.ops.render.render(write_still=True)
print("DONE")
