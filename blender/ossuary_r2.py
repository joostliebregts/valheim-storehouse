"""Ossuary Bin, round 2 (Joost, 24 Oct, in game, 128/128 full with about the same amount of each kind: the bin takes SEVEN
kinds in six bays; r1 gave BoneFragments 48 units, CharredBone 24, four others 14 and BonemawSerpentTooth no home, so with
equal stock three bays looked half empty and the seventh kind was squeezed into another's bay. His rule: plan for the full
list). Same stone-footed timber outbuilding bin as r1 (concept: scratchpad sketch7/bones), same size and style, new plan:
  back row (raised floor):  WitheredBone | THE SHARED BAY: Charredskull | plank | AsksvinCarrionSkull | HardAntler
  front row (low wall):     CharredBone | BoneFragments | BonemawSerpentTooth        (left to right as seen from the front)
Seven kinds in six bays: the BIGGEST bay (back middle, 1.30 x 0.83 m) holds the two skulls, which belong together, with a
fixed divider built into the model: a thick hewn plank (0.12 m, 1.00 m tall = as tall as the heap) standing on the floor,
iron-strapped on both faces, with a post at each end where it meets the cross wall and the back wall. Every other kind has a
bay of its own. The anchors say per unit which skull it is for (unit.item); the mod fills each side only with its own kind
and draws no board of its own.
Units (128 = the 8 x 16 grid, split about evenly over the 7 kinds): BoneFragments 19, CharredBone 19, WitheredBone 18,
HardAntler 18, BonemawSerpentTooth 18, Charredskull 18 + AsksvinCarrionSkull 18 (the shared bay 36). Each unit carries about
the same share of its bay's copies, so with equal stock every bay is full at its unit count and, with unequal stock, a bay
fills from its back wall in unit steps.
Bay sizes (inner): back singles 0.67 x 0.83, the shared bay 1.30 x 0.83 (two halves of 0.59 x 0.83 either side of the 0.12
plank), front 0.88 x 0.59 each: all about 0.5 m2 per kind. Overall footprint 3.20 x 1.84 m as in r1.
Run: blender -b -P ossuary_r2.py -- [--out DIR] [--assets DIR] [--quick] [--no-render] [--views a,b] [--cseed N]
     [--fit Item:longest_m,...] [--cap Item:n,...]

Frame as r1: front wall 0.55 m, cross wall 0.72 m, back wall 1.05 m, back posts and tie beam 1.42 m, gable apex 1.92 m,
crossed ridge-beam tips 2.08 m. Stone footing to 0.30 m under every wall; flagstone floors at 0.12 m (front row) and 0.30 m
(back row). Hewn beam courses 0.12 thick above the stone, posts 0.14, gable planks 0.05. The back row's dividers stand at
x = +-0.72 and the front row's at x = +-0.51 (the rows have different bay widths); the shared bay's plank is at x = 0.

Contents: each bay is filled copy by copy (Blender rigid bodies / Bullet, convex hulls, friction 0.75, restitution 0, every
copy dropped onto the frozen earlier ones at the spot of 16 that lies furthest under the target surface, with a pull
towards the bay's back wall, and frozen when it has settled) until its target surface is covered: from every wall's visible
top (EDGE under it) rising inward at CROWN, never more than CAPOVER over the bay's lower side wall. The shared bay's halves
are two simulations, each with the plank as its tall side wall (top 1.00 m; the heap itself crowns at about 0.95 m).
The invisible colliders are the bay's inner faces pulled in by WALLGAP and extended straight up; a copy that leans on that
extension (over a wall top, within 2 cm of its face), leaves the bay, touches the frame or does not settle is taken out
and dropped again elsewhere. The copy sequence is then cut into the bay's units in drop order, so any prefix of units (and
any prefix of a unit's copies) only rests on what is shown.
Item sizes (longest side, fit_longest_m): as r1 (about 0.47-0.55 of true size) except WitheredBone 0.40 (its model is 1.98 m
long) and BonemawSerpentTooth 0.40 (new; a 0.84 m tooth at about half size).
unit.position: x = centre of the unit's copies, y = the bay's mid height, z = the bay's centre; unit.box: x = the copies'
width, y = from the bay's lowest rotated-bounds corner to its highest copy, z = 90% of the bay's inner depth. unit.bay = the
group (0-5: back row left to right, then the front row); unit.cell = [column, row] of the bay or half (back row columns 0-3
with 1 and 2 the two skull halves, front row 0-2); unit.item = the kind the unit is for.
Atlas (128 px, point filtered, 48 px per metre): as r1.
Files: assets/ossuary_r2/{Ossuary.obj, ossuary_atlas.png, ossuary_anchors.json}, the json written last (temp file +
rename). Renders and simlog in --out (default: the scratchpad ossuary_r2 folder).
"""
import bpy, bmesh, sys, os, math, json, random, time
import numpy as np
from mathutils import Vector, Matrix, Euler, Quaternion
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, ".."))
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
def arg(k, d=None): return argv[argv.index(k) + 1] if k in argv else d
SCR = "C:/Users/joost/AppData/Local/Temp/claude/C--Users-joost--pai/5e4bc60b-cdfe-4638-8e29-2e507fa13cf9/scratchpad/ossuary_r2"
OUTA = arg("--assets", os.path.join(REPO, "assets", "ossuary_r2"))
OUT = arg("--out", SCR)
QUICK = "--quick" in argv
NORENDER = "--no-render" in argv
VIEWSEL = arg("--views").split(",") if "--views" in argv else None
ITEMS_DIR = "C:/Users/joost/ValheimRip/items"
sys.path.append(ITEMS_DIR)
from load_item import load_item
os.makedirs(OUTA, exist_ok=True); os.makedirs(OUT, exist_ok=True)
rng = random.Random(23)                         # frame
crng = random.Random(int(arg("--cseed", 37)))   # contents

TEX, DENS = 128, 48.0
FPS = 24
MARGIN = 0.003
WALLGAP = 0.015                # colliders inside the bay's inner faces
EDGE, CROWN = 0.02, 0.85
GRID = 0.03
BACKW = 0.12                   # pull towards the bay's back wall (m of target deficit)

# ---------- layout (Blender metres, z up, -y = front, origin = footprint centre on the ground) ----------
HX, HY = 1.60, 0.92            # outer half extents
WT = 0.14                      # wall thickness (stone footing); beam courses above it are BT thick, flush with the bay side
BT = 0.12
STONE_TOP = 0.30
FLF, FLB = 0.12, 0.30          # flagstone floor tops: front row, back row
DXB, DXF = 0.72, 0.51          # divider centre lines (x = +-): back row, front row
DT = 0.12                      # the shared bay's divider plank (x = 0): thickness
DIVTOP = 1.00                  # ... and top (as tall as the heap)
YC = -0.12                     # cross wall centre line
IX, IY = HX - WT, HY - WT      # inner faces of the end walls / front and back walls
TOPS = {"front": 0.55, "cross": 0.72, "back": 1.05, "side_f": 0.62, "side_b": 0.85}
POST = 0.14
CAPOVER = {0: 0.12, 1: 0.10}   # a full heap crowns at most this over the row's lower side wall
ROWFLOOR = {0: FLF, 1: FLB}
YB = {0: (-IY, YC - WT / 2), 1: (YC + WT / 2, IY)}
# back row: single | shared bay (columns 1 and 2 = its halves either side of the plank) | single; front row: three singles
XBB = [(-IX, -DXB - WT / 2), (-DXB + WT / 2, -DT / 2), (DT / 2, DXB - WT / 2), (DXB + WT / 2, IX)]
XBF = [(-IX, -DXF - WT / 2), (-DXF + WT / 2, DXF - WT / 2), (DXF + WT / 2, IX)]
CELLS = {}                     # (col, row) -> bounds and the visible tops of the four walls around it
for _c, (_x0, _x1) in enumerate(XBB):
    _tl = DIVTOP if _c == 2 else TOPS["side_b"]; _tr = DIVTOP if _c == 1 else TOPS["side_b"]
    CELLS[(_c, 1)] = {"b": (_x0, _x1) + YB[1], "tops": (TOPS["cross"], TOPS["back"], _tl, _tr)}
for _c, (_x0, _x1) in enumerate(XBF):
    CELLS[(_c, 0)] = {"b": (_x0, _x1) + YB[0], "tops": (TOPS["front"], TOPS["cross"], TOPS["side_f"], TOPS["side_f"])}

# item: (cell (col, row), longest side in the store (m), mode, units, copy cap)
ITEMS = {
    "WitheredBone":        ((0, 1), 0.40, "long",   18, 160),
    "Charredskull":        ((1, 1), 0.20, "tumble", 18, 160),
    "AsksvinCarrionSkull": ((2, 1), 0.27, "tumble", 18, 160),
    "HardAntler":          ((3, 1), 0.24, "tumble", 18, 160),
    "CharredBone":         ((0, 0), 0.36, "long",   19, 160),
    "BoneFragments":       ((1, 0), 0.30, "flat",   19, 110),
    "BonemawSerpentTooth": ((2, 0), 0.40, "long",   18, 160),
}
if "--fit" in argv:
    for kv in arg("--fit").split(","):
        k, v = kv.split(":"); b, _f, m, u, c = ITEMS[k]; ITEMS[k] = (b, float(v), m, u, c)
if "--cap" in argv:
    for kv in arg("--cap").split(","):
        k, v = kv.split(":"); b, f, m, u, _c = ITEMS[k]; ITEMS[k] = (b, f, m, u, int(v))
BAYS = sorted(ITEMS, key=lambda it: (-ITEMS[it][0][1], ITEMS[it][0][0]))     # the 7 kinds: back row L->R, then front row L->R
GROUPS = [["WitheredBone"], ["Charredskull", "AsksvinCarrionSkull"], ["HardAntler"], ["CharredBone"], ["BoneFragments"], ["BonemawSerpentTooth"]]
GROUP = {it: g for g, its in enumerate(GROUPS) for it in its}                  # the mod's group key "bay"
assert sorted(BAYS) == sorted(it for g in GROUPS for it in g)
NUNITS = sum(v[3] for v in ITEMS.values())
assert NUNITS == 128, NUNITS
FILTER = ["BoneFragments", "CharredBone", "WitheredBone", "Charredskull", "HardAntler", "AsksvinCarrionSkull", "BonemawSerpentTooth"]

def bay_bounds(col, row):
    return CELLS[(col, row)]["b"]

def wall_tops(col, row):
    """visible tops of the walls around a cell: y0 (front side), y1 (back side), x0 side, x1 side"""
    return CELLS[(col, row)]["tops"]

def crown_cap(col, row):
    ty0, ty1, tl, tr = wall_tops(col, row)
    return min(tl, tr) + CAPOVER[row]

def target(col, row, X, Y):
    x0, x1, y0, y1 = bay_bounds(col, row)
    ty0, ty1, tl, tr = wall_tops(col, row)
    t = np.minimum.reduce([tl - EDGE + CROWN * (X - x0), tr - EDGE + CROWN * (x1 - X),
                           ty0 - EDGE + CROWN * (Y - y0), ty1 - EDGE + CROWN * (y1 - Y)])
    return np.minimum(t, crown_cap(col, row))

# ---------- atlas ----------
TILES = {"hewn": (0, 0, 128, 32), "end0": (0, 32, 32, 32), "end1": (32, 32, 32, 32), "dark": (64, 32, 32, 32),
         "wearw": (96, 32, 32, 16), "weari": (96, 48, 32, 16), "iron": (0, 64, 128, 16),
         "stone0": (0, 80, 32, 32), "stone1": (32, 80, 32, 32), "stone2": (64, 80, 32, 32), "stone3": (96, 80, 32, 32),
         "bone": (0, 112, 32, 16), "socket": (32, 112, 32, 16), "antler": (64, 112, 32, 16), "iron2": (96, 112, 32, 16)}

def load_px(path):
    im = bpy.data.images.load(path)
    w, h = im.size
    a = np.array(im.pixels[:], np.float32).reshape(h, w, 4)[::-1, :, :3]     # top-down
    bpy.data.images.remove(im)
    return a

def mix(a, b, t): t = np.clip(t, 0, 1)[..., None]; return a * (1 - t) + b * t
def srgb(c): return np.array(c, np.float32)

def build_atlas():
    B = load_px(os.path.join(REPO, "assets", "bunker_r4", "bunker_atlas.png"))
    P = load_px(os.path.join(REPO, "assets", "metalpallet_r3", "metalpallet_atlas.png"))
    O = load_px(os.path.join(REPO, "assets", "orebin_r5", "orebin_atlas.png"))
    A = np.zeros((TEX, TEX, 3), np.float32)
    A[0:32] = B[0:32]                       # bunker hewn timber
    A[32:64, 0:64] = B[32:64, 0:64]         # bunker end grain, rings 0 and 1
    A[32:64, 64:96] = P[0:32, 0:32]         # pallet dark oiled hewn timber
    A[32:64, 96:128] = P[32:64, 96:128]     # pallet wear swatch: worn timber (top), worn iron (bottom)
    A[64:80] = B[64:80]                     # bunker iron
    A[80:112] = O[64:96]                    # ore bin stone blocks, four tiles
    A[112:128, 96:128] = B[64:80, 0:32]     # (spare) bunker iron
    nr = np.random.default_rng(53)
    yy, xx = np.meshgrid(np.arange(16), np.arange(32), indexing="ij")
    blocky = lambda s: np.kron(nr.random((16 // s, 32 // s)), np.ones((s, s), np.float32))
    # bone: muted aged ivory, grey-brown stains, a few hairline cracks, darker crevices, light worn spots
    base, dark, light = srgb((0.58, 0.54, 0.45)), srgb((0.27, 0.24, 0.19)), srgb((0.70, 0.67, 0.58))
    t = blocky(8) * 0.20 + blocky(4) * 0.16 + blocky(2) * 0.10 + nr.random((16, 32)) * 0.10
    img = mix(base, dark, t)
    for _ in range(5):                       # hairline cracks
        y, x = int(nr.integers(1, 15)), int(nr.integers(0, 32))
        for k in range(int(nr.integers(3, 8))):
            img[y, (x + k) % 32] = mix(img[y, (x + k) % 32][None], dark[None], np.array([0.7]))[0]
            y = int(np.clip(y + nr.integers(-1, 2), 0, 15))
    worn = (nr.random((16, 32)) < 0.07) & (t < 0.25)
    img[worn] = mix(img[worn], np.broadcast_to(light, img[worn].shape), np.full(worn.sum(), 0.6))
    A[112:128, 0:32] = img
    # socket: the dark of an eye socket, nose or mouth (near-black umber, not black)
    s0, s1 = srgb((0.10, 0.085, 0.07)), srgb((0.045, 0.04, 0.035))
    A[112:128, 32:64] = mix(s0, s1, nr.random((16, 32)) * 0.6 + blocky(4) * 0.4)
    # antler: grey-brown, lengthwise furrows (along u), lighter worn ridges
    base, dark, light = srgb((0.45, 0.39, 0.31)), srgb((0.22, 0.18, 0.14)), srgb((0.60, 0.55, 0.46))
    f = 0.5 + 0.5 * np.sin(yy * 1.9 + 0.8 * np.sin(xx * 0.3))
    t = np.clip(f - 0.55, 0, 1) * 1.4 + nr.random((16, 32)) * 0.15 + blocky(4) * 0.1
    img = mix(base, dark, t)
    ridge = (f < 0.15) & (nr.random((16, 32)) < 0.5)
    img[ridge] = mix(img[ridge], np.broadcast_to(light, img[ridge].shape), np.full(ridge.sum(), 0.5))
    A[112:128, 64:96] = img
    im = bpy.data.images.new("ossuary_atlas", TEX, TEX, alpha=False)
    px = np.concatenate([np.clip(A[::-1], 0, 1), np.ones((TEX, TEX, 1), np.float32)], 2)
    im.pixels.foreach_set(px.ravel())
    im.filepath_raw = os.path.join(OUTA, "ossuary_atlas.png"); im.file_format = "PNG"; im.save()
    return im

def tuv(tile, px, py):
    x0, y0, w, h = TILES[tile]
    return ((x0 + px) / TEX, 1 - (y0 + py) / TEX)

def texel(tile, r):
    x0, y0, w, h = TILES[tile]
    return tuv(tile, 1.5 + r.randrange(w - 3), 1.5 + r.randrange(h - 3))

# ---------- frame geometry ----------
PARTS = []
MAT = None

def new_obj(name, bm):
    bm.normal_update()
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = False
    ob = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(ob)
    ob.data.materials.append(MAT); PARTS.append(ob)
    return ob

# box timbers: bunker_r4's mapping (hewn strip v 0.75, end grain v 0.5 two rings, iron v 0.375), chamfers -> wear swatch;
# "dark" = the pallet's dark oiled timber tile (32 px: parts up to 0.6 m long), stone = one whole tile per block face
STRIP = {"hewn": 0.75, "end": 0.50, "iron": 0.375}
STRIPH = {"hewn": 32, "iron": 16}
def uv_box_face(f, uvl, kind, long_axis, seed):
    n = f.normal
    r = random.Random(seed * 7919 + f.index)
    axial = max(abs(n[0]), abs(n[1]), abs(n[2])) >= 0.98
    if kind.startswith("stone"):
        if not axial:
            uv = tuv(kind, 1.0, 1.0 + r.random())          # bevels: the tile's dark joint
            for l in f.loops: l[uvl].uv = uv
            return
        ax = max(range(3), key=lambda i: abs(n[i]))
        tang = [i for i in range(3) if i != ax]
        cs = [l.vert.co for l in f.loops]; c = sum(cs, Vector()) / len(cs)
        e = [max(abs(v[t] - c[t]) for v in cs) or 1 for t in tang]
        for l in f.loops:
            a = (l.vert.co[tang[0]] - c[tang[0]]) / e[0]; b = (l.vert.co[tang[1]] - c[tang[1]]) / e[1]
            l[uvl].uv = tuv(kind, 16 + a * 12.5, 16 - b * 12.5)
        return
    if kind == "rivet" or not axial:
        uv = texel("weari" if kind in ("iron", "rivet") else "wearw", r)
        for l in f.loops: l[uvl].uv = uv
        return
    ax = max(range(3), key=lambda i: abs(n[i]))
    tang = [i for i in range(3) if i != ax]
    if kind != "iron" and ax == long_axis:
        k = seed % 2
        cs = [l.vert.co for l in f.loops]
        c = sum(cs, Vector()) / len(cs)
        ext = max(max(abs(v[tang[0]] - c[tang[0]]), abs(v[tang[1]] - c[tang[1]])) for v in cs) or 1
        for l in f.loops:
            a = (l.vert.co[tang[0]] - c[tang[0]]) / ext; b = (l.vert.co[tang[1]] - c[tang[1]]) / ext
            l[uvl].uv = ((k + 0.5 + a * 0.45) / 4, STRIP["end"] + (0.5 + b * 0.45) / 4)
        return
    ua = long_axis if long_axis in tang else tang[0]
    va = tang[1] if ua == tang[0] else tang[0]
    us = [l.vert.co[ua] for l in f.loops]; vs = [l.vert.co[va] for l in f.loops]
    umin, uspan = min(us), max(max(us) - min(us), 1e-4)
    vmin, span = min(vs), max(max(vs) - min(vs), 1e-4)
    if kind == "dark":
        us_ = min(1.0, 30.0 / (uspan * DENS)); vs_ = min(1.0, 30.0 / (span * DENS))
        ou = r.uniform(0.5, max(0.6, 31.5 - uspan * DENS * us_)); ov = r.uniform(0.5, max(0.6, 31.5 - span * DENS * vs_))
        for l in f.loops:
            l[uvl].uv = tuv("dark", ou + (l.vert.co[ua] - umin) * DENS * us_, ov + (l.vert.co[va] - vmin) * DENS * vs_)
        return
    off = (seed * 0.37) % 1
    hpx = STRIPH[kind]
    vscale = min(1.0, (hpx / DENS) / span)
    room = max(hpx / TEX - span * vscale * DENS / TEX * 0.94 - 0.012, 0)
    voff = ((seed * 0.618) % 1) * room
    for l in f.loops:
        u = l.vert.co[ua] * DENS / TEX + off
        v = STRIP[kind] + ((l.vert.co[va] - vmin) * vscale * DENS / TEX) * 0.94 + 0.0075 + voff
        l[uvl].uv = (u, v)

def timber(name, size, pos, kind="hewn", rot=(0, 0, 0), jitter=0.004, bevel=0.014):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts: v.co = Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2]))
    long_axis = max(range(3), key=lambda i: size[i])
    for v in bm.verts:
        for i in range(3):
            if i != long_axis: v.co[i] += rng.uniform(-jitter, jitter)
    if bevel > 0: bmesh.ops.bevel(bm, geom=bm.edges[:], offset=bevel, segments=1, affect="EDGES")
    bm.normal_update()
    uvl = bm.loops.layers.uv.verify()
    seed = rng.randrange(1000)
    for f in bm.faces: uv_box_face(f, uvl, kind, long_axis, seed + f.index % 2)
    bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Euler([math.radians(a) for a in rot]).to_matrix())
    bmesh.ops.translate(bm, verts=bm.verts, vec=Vector(pos))
    return new_obj(name, bm)

def iron(name, size, pos, rot=(0, 0, 0)):
    return timber(name, size, pos, kind="iron", rot=rot, jitter=0.0, bevel=0)

def stone(size, pos):
    return timber("stone", size, pos, kind="stone%d" % rng.randrange(4), jitter=0.0, bevel=0.018)

def rivet(pos, normal, s=0.024, h=0.008):
    """square iron rivet head standing h off a face with this outward normal"""
    n = Vector(normal).normalized()
    yaw = math.degrees(math.atan2(n.y, n.x)) if abs(n.z) < 0.5 else 0
    size = (h, s, s) if abs(n.z) < 0.5 else (s, s, h)
    p = Vector(pos) + n * (h / 2)
    timber("rivet", size, tuple(p), kind="rivet", rot=(0, 0, yaw), jitter=0, bevel=0)

def stone_run(a0, a1, cross, axis, z0, z1, t):
    """two courses of stone blocks along x (axis 'x', at y = cross) or y, from a0 to a1, z0..z1, t thick (3 mm shy of
    both faces, so the bay sides stay flat)"""
    L = a1 - a0
    ch = (z1 - z0) / 2
    for course in range(2):
        cuts = [0.0]
        while cuts[-1] < L - 1e-6:
            step = rng.uniform(0.34, 0.52) if course == 0 or len(cuts) > 1 else rng.uniform(0.17, 0.30)
            cuts.append(min(L, cuts[-1] + step))
        if L - cuts[-2] < 0.15 and len(cuts) > 2: cuts.pop(-2)
        zc = z0 + ch * (course + 0.5)
        for a, b in zip(cuts, cuts[1:]):
            ln = b - a - 0.012; h = ch - 0.012 - rng.uniform(0, 0.01)
            mid = a0 + (a + b) / 2
            if axis == "x": stone((ln, t - 0.006, h), (mid, cross, zc))
            else: stone((t - 0.006, ln, h), (cross, mid, zc))

def courses(a0, a1, cross, axis, z0, top, face_sign, t=BT, kind="hewn"):
    """hewn beam courses (about 0.125 tall) from z0 to top along a wall line; face_sign -1/+1 puts them flush with the
    wall's -/+ side (3 mm shy of it), 0 centres them"""
    n = max(1, round((top - z0) / 0.125)); h = (top - z0) / n
    off = 0.0 if face_sign == 0 else face_sign * (WT / 2 - t / 2 - 0.003)
    for i in range(n):
        zc = z0 + h * (i + 0.5)
        if axis == "x": timber("course", (a1 - a0, t, h - 0.008), ((a0 + a1) / 2, cross + off, zc), kind=kind, bevel=0.012)
        else: timber("course", (t, a1 - a0, h - 0.008), (cross + off, (a0 + a1) / 2, zc), kind=kind, bevel=0.012)

def post(x, y, top, bands=(0.40,), name="post"):
    timber(name, (POST, POST, top), (x, y, top / 2), jitter=0.003, bevel=0.016)
    for zb in bands:                                  # iron band round the post, two rivets on its front and side faces
        iron("band", (POST + 0.016, POST + 0.016, 0.045), (x, y, zb))
        rivet((x, y - POST / 2 - 0.008, zb), (0, -1, 0), s=0.02, h=0.007)
        rivet((x + math.copysign(POST / 2 + 0.008, x if abs(x) > 1e-3 else 1), y, zb), (math.copysign(1, x if abs(x) > 1e-3 else 1), 0, 0), s=0.02, h=0.007)

# ---------- our own decor: skull, antler (bone / socket / antler tiles) ----------
def uv_planar(bm, uvl, tile, faces=None, r=None):
    r = r or random.Random(rng.randrange(10 ** 6))
    x0, y0, w, h = TILES[tile]
    for f in (faces if faces is not None else bm.faces):
        n = f.normal; ax = max(range(3), key=lambda i: abs(n[i])); tang = [i for i in range(3) if i != ax]
        cs = [l.vert.co for l in f.loops]
        mn = [min(c[t] for c in cs) for t in tang]; mx = [max(c[t] for c in cs) for t in tang]
        sc = min(1.0, (w - 2) / max((mx[0] - mn[0]) * DENS, 1e-4), (h - 2) / max((mx[1] - mn[1]) * DENS, 1e-4))
        ou = r.uniform(1, max(1.1, w - 1 - (mx[0] - mn[0]) * DENS * sc)); ov = r.uniform(1, max(1.1, h - 1 - (mx[1] - mn[1]) * DENS * sc))
        for l in f.loops:
            l[uvl].uv = tuv(tile, ou + (l.vert.co[tang[0]] - mn[0]) * DENS * sc, ov + (mx[1] - l.vert.co[tang[1]]) * DENS * sc)

def part_mesh(bm_fn, tile, M):
    bm = bmesh.new(); bm_fn(bm)
    bm.normal_update(); uvl = bm.loops.layers.uv.verify(); uv_planar(bm, uvl, tile)
    bmesh.ops.transform(bm, matrix=M, verts=bm.verts)
    return new_obj("decor", bm)

def cube_fn(size, at, bevel=0.0):
    def fn(bm):
        g = bmesh.ops.create_cube(bm, size=1.0)
        for v in g["verts"]: v.co = Vector((v.co.x * size[0] + at[0], v.co.y * size[1] + at[1], v.co.z * size[2] + at[2]))
        if bevel: bmesh.ops.bevel(bm, geom=bm.edges[:], offset=bevel, segments=1, affect="EDGES")
    return fn

def disc_fn(r, at, n=6, rot=0.0, sy=1.0):
    """a flat n-sided plate facing -y (an eye socket, the nose)"""
    def fn(bm):
        vs = [bm.verts.new(Vector((at[0] + r * math.cos(rot + 2 * math.pi * k / n), at[1], at[2] + sy * r * math.sin(rot + 2 * math.pi * k / n)))) for k in range(n)]
        bm.faces.new(vs)
    return fn

def skull(at, s=1.0, yaw=0.0, tilt=0.0):
    """a low-poly skull (about 0.15 m wide at s = 1), facing -y: cranium, brow, face block, cheekbones, jaw with a tooth
    row; eye sockets and nose as dark plates 1 mm proud of the bone, the gap between the teeth a dark line"""
    M = Matrix.Translation(Vector(at)) @ Matrix.Rotation(math.radians(yaw), 4, "Z") @ Matrix.Rotation(math.radians(tilt), 4, "X") @ Matrix.Diagonal((s, s, s, 1))
    def cranium(bm):
        bmesh.ops.create_uvsphere(bm, u_segments=10, v_segments=7, radius=0.5)
        for v in bm.verts: v.co = Vector((v.co.x * 0.15, v.co.y * 0.185, v.co.z * 0.15)) + Vector((0, 0.022, 0.042))
    part_mesh(cranium, "bone", M)
    part_mesh(cube_fn((0.098, 0.06, 0.07), (0, -0.068, -0.018), 0.016), "bone", M)        # face
    part_mesh(cube_fn((0.118, 0.03, 0.022), (0, -0.084, 0.03), 0.008), "bone", M)          # brow ridge
    for sx in (-1, 1):
        part_mesh(cube_fn((0.026, 0.05, 0.022), (sx * 0.056, -0.056, -0.008), 0.007), "bone", M)    # cheekbones
    part_mesh(cube_fn((0.082, 0.056, 0.024), (0, -0.064, -0.071), 0.008), "bone", M)       # jaw
    part_mesh(cube_fn((0.056, 0.01, 0.017), (0, -0.0955, -0.053), 0.0), "bone", M)         # tooth row
    part_mesh(cube_fn((0.058, 0.004, 0.004), (0, -0.1012, -0.0515), 0.0), "socket", M)    # the gap between the teeth
    for sx in (-1, 1):
        part_mesh(disc_fn(0.0175, (sx * 0.026, -0.0995, 0.008), n=6, rot=math.pi / 6, sy=0.95), "socket", M)   # eye sockets
    part_mesh(disc_fn(0.011, (0, -0.0995, -0.022), n=3, rot=-math.pi / 2, sy=1.3), "socket", M)              # nose

def tube(bm, p0, p1, r0, r1, nseg=6):
    """a tapered nseg-sided tube from p0 to p1 with end caps"""
    d = (Vector(p1) - Vector(p0)).normalized()
    a = d.orthogonal().normalized(); b = d.cross(a)
    ring = lambda p, r: [bm.verts.new(Vector(p) + (a * math.cos(2 * math.pi * k / nseg) + b * math.sin(2 * math.pi * k / nseg)) * r) for k in range(nseg)]
    R0, R1 = ring(p0, r0), ring(p1, r1)
    for k in range(nseg): bm.faces.new((R0[k], R0[(k + 1) % nseg], R1[(k + 1) % nseg], R1[k]))
    bm.faces.new(R0[::-1]); bm.faces.new(R1)

def antler(root, side, length=0.42, r0=0.034):
    """an antler (OUR geometry): a heavy main beam curving out, a little back and up from root (side = -1 left, +1 right)
    in 4 tapered six-sided segments, with three stout tines rising from it"""
    bm = bmesh.new()
    pts = [Vector(root)]
    for k in range(1, 5):
        t = k / 4
        pts.append(Vector(root) + Vector((side * length * (0.50 * t + 0.08 * t * t), length * 0.12 * t, length * (0.42 * t + 0.40 * t * t))))
    rad = [r0 * (1 - 0.62 * k / 4) for k in range(5)]
    for k in range(4): tube(bm, pts[k], pts[k + 1], rad[k], rad[k + 1])
    for k, (up, out, ln) in zip((0, 1, 2), ((1.0, -0.25, 0.13), (1.0, 0.05, 0.16), (0.9, 0.30, 0.12))):
        base = pts[k] + (pts[k + 1] - pts[k]) * 0.55
        tip = base + Vector((side * out * ln, -0.05 * ln, up * ln))
        rt = rad[k + 1] * 0.85
        tube(bm, base, tip, rt, rt * 0.3)
    bm.normal_update(); uvl = bm.loops.layers.uv.verify(); uv_planar(bm, uvl, "antler")
    return new_obj("antler", bm)

# ---------- the bin ----------
def build_frame():
    # stone footing under every wall line, flagstone floors
    ox, oy = HX - WT / 2, HY - WT / 2
    stone_run(-HX, HX, -oy, "x", 0.0, STONE_TOP, WT)                       # front
    stone_run(-HX, HX, oy, "x", 0.0, STONE_TOP, WT)                        # back
    for sx in (-1, 1):
        stone_run(-HY + WT, HY - WT, sx * ox, "y", 0.0, STONE_TOP, WT)     # ends
        stone_run(-HY + WT, YC, sx * DXF, "y", 0.0, STONE_TOP, WT)         # front row dividers
        stone_run(YC, HY - WT, sx * DXB, "y", 0.0, STONE_TOP, WT)          # back row dividers
    stone_run(-IX, IX, YC, "x", 0.0, STONE_TOP, WT)                        # cross wall (it carries the back floor's front edge)
    spans = {0: [bay_bounds(c, 0) for c in range(3)],
             1: [bay_bounds(0, 1), (bay_bounds(1, 1)[0], bay_bounds(2, 1)[1]) + YB[1], bay_bounds(3, 1)]}      # the shared bay's floor runs under its plank
    for row, fl in ROWFLOOR.items():
        for x0, x1, y0, y1 in spans[row]:
            under = fl - 0.06
            if under > 0.005: timber("rubble", (x1 - x0 - 0.01, y1 - y0 - 0.01, under), ((x0 + x1) / 2, (y0 + y1) / 2, under / 2), kind="stone0", jitter=0, bevel=0)
            nxs = max(2, round((x1 - x0) / 0.33))
            xs = np.linspace(x0, x1, nxs + 1); ys = np.linspace(y0, y1, 3)
            for i in range(nxs):
                for j in range(2):
                    jx = rng.uniform(-0.03, 0.03) if 0 < i < nxs else 0.0
                    a0 = xs[i] + (0 if i == 0 else jx); a1 = xs[i + 1]
                    timber("flag", (a1 - a0 - 0.012, ys[j + 1] - ys[j] - 0.012, 0.06), ((a0 + a1) / 2, (ys[j] + ys[j + 1]) / 2, fl - 0.03),
                           kind="stone%d" % rng.randrange(4), jitter=0, bevel=0.0)
    # hewn beam courses above the stone, flush with the bay side
    for x0, x1 in XBF:
        courses(x0, x1, -HY + WT / 2, "x", STONE_TOP, TOPS["front"], +1)
    for x0, x1 in (XBB[0], (XBB[1][0], XBB[2][1]), XBB[3]):
        courses(x0, x1, HY - WT / 2, "x", STONE_TOP, TOPS["back"], -1)
    for x0, x1 in ((-IX, -DXB - POST / 2), (-DXB + POST / 2, -POST / 2), (POST / 2, DXB - POST / 2), (DXB + POST / 2, IX)):
        courses(x0, x1, YC, "x", STONE_TOP, TOPS["cross"], 0)
    for sx in (-1, 1):
        x = sx * (HX - WT / 2)
        courses(-IY, YC - WT / 2 - 0.0, x, "y", STONE_TOP, TOPS["side_f"], -sx)
        courses(YC - WT / 2, IY, x, "y", STONE_TOP, TOPS["side_b"], -sx)
        courses(-IY, YC - WT / 2, sx * DXF, "y", STONE_TOP, TOPS["side_f"], 0)
        courses(YC + WT / 2, IY, sx * DXB, "y", STONE_TOP, TOPS["side_b"], 0)
    # caps: a hewn cap beam over the front wall's top course, flush with its top, overhanging 2 cm out front
    for x0, x1 in XBF:
        timber("cap", (x1 - x0 + 0.004, 0.06, 0.05), ((x0 + x1) / 2, -HY + 0.005, TOPS["front"] - 0.03), kind="dark", bevel=0.01)
    # posts: front corners and dividers (skull-capped), cross wall line, back (carry the tie beam)
    PF, PC, PB = 0.68, 0.95, 1.28
    yf, yb = -HY + WT / 2, HY - WT / 2
    for sx in (-1, 1):
        post(sx * (HX - WT / 2), yf, PF, bands=(0.22, PF - 0.12))
        post(sx * DXF, yf, PF, bands=(0.22, PF - 0.12))
        post(sx * (HX - WT / 2), YC, PC, bands=(0.40, PC - 0.12))
        post(sx * DXB, YC, PC, bands=(0.40, PC - 0.12))
        post(sx * (HX - WT / 2), yb, PB, bands=(0.40, 1.02))
        post(sx * DXB, yb, PB, bands=(0.40, 1.02))
        timber("ptop", (POST + 0.01, POST + 0.01, 0.03), (sx * (HX - WT / 2), yf, PF + 0.015), kind="dark", bevel=0.008)
        iron("cap", (0.12, 0.12, 0.012), (sx * DXF, yf, PF + 0.006))
    # the shared bay's divider: a thick hewn plank standing on the floor (1.00 m = as tall as the heap), a dark oiled cap on it,
    # iron straps with rivets on both faces, a post at each end where it meets the cross wall and the back wall
    yd0, yd1 = YC + WT / 2, IY
    zf = FLB - 0.01
    PDV = 1.06
    timber("divider", (DT, yd1 - yd0, DIVTOP - 0.04 - zf), (0, (yd0 + yd1) / 2, zf + (DIVTOP - 0.04 - zf) / 2), bevel=0.016, jitter=0.002)
    timber("divcap", (DT + 0.03, yd1 - yd0 - 0.02, 0.04), (0, (yd0 + yd1) / 2, DIVTOP - 0.02), kind="dark", bevel=0.01, jitter=0.002)
    for yy in (yd0 + 0.13, (yd0 + yd1) / 2, yd1 - 0.13):
        for sx in (-1, 1):
            iron("dstrap", (0.006, 0.05, DIVTOP - 0.04 - zf - 0.04), (sx * (DT / 2 + 0.002), yy, zf + (DIVTOP - 0.04 - zf) / 2))
            for zr_ in (zf + 0.07, DIVTOP - 0.04 - 0.07): rivet((sx * (DT / 2 + 0.005), yy, zr_), (sx, 0, 0), s=0.02, h=0.007)
    post(0.0, YC, PDV, bands=(0.45, PDV - 0.12))
    post(0.0, yb, PB, bands=(0.40, 1.02))
    # tie beam over the back posts, T-brackets at the posts
    TB = 0.14
    timber("tie", (2 * HX + 0.06, 0.15, TB), (0, yb, PB + TB / 2), bevel=0.016)
    for x in (-(HX - WT / 2), -DXB, 0.0, DXB, HX - WT / 2):
        iron("tbrk", (0.05, 0.006, 0.20), (x, yb - 0.075 - 0.003, PB - 0.04))
        iron("tbrk", (0.20 if abs(x) < 1 else 0.12, 0.006, 0.05), (x if abs(x) < 1 else x - math.copysign(0.04, x), yb - 0.075 - 0.003, PB + 0.06))
        rivet((x, yb - 0.081, PB - 0.10), (0, -1, 0)); rivet((x, yb - 0.081, PB + 0.06), (0, -1, 0))
    # gable board: vertical planks on the tie beam, stepped to a 35 degree gable, apex 1.92 m
    zt = PB + TB
    APEX, HALF = 1.92, 0.72
    n = 11; w = 2 * HALF / n
    for i in range(n):
        x = -HALF + w * (i + 0.5)
        top = zt + (APEX - zt) * (1 - abs(x) / HALF) + 0.04
        h = top - zt
        timber("gable", (w - 0.008, 0.05, h), (x, yb + 0.03, zt + h / 2), kind="dark" if i % 2 else "hewn", bevel=0.01, jitter=0.002)
    iron("gstrap", (2 * HALF - 0.1, 0.006, 0.04), (0, yb + 0.002, zt + 0.10))
    for x in (-0.5, 0.0, 0.5): rivet((x, yb - 0.001, zt + 0.10), (0, -1, 0), s=0.018, h=0.006)
    # crossed ridge beams on the gable's slopes, crossing over the apex, an iron band where they cross
    ang = math.degrees(math.atan2(APEX - zt, HALF))
    L = math.hypot(HALF, APEX - zt) + 0.16
    for s_ in (-1, 1):
        cx = s_ * (-HALF / 2 + 0.04); cz = zt + (APEX - zt) / 2 + 0.06
        timber("horn", (L, 0.09, 0.08), (cx, yb - 0.02, cz), rot=(0, s_ * ang, 0), bevel=0.014, jitter=0.002)
    iron("hplate", (0.08, 0.008, 0.08), (0, yb - 0.069, APEX + 0.04), rot=(0, 45, 0))   # a diamond plate where they cross
    rivet((0, yb - 0.073, APEX + 0.04), (0, -1, 0), s=0.02, h=0.007)
    # the skull with antlers, sitting on the tie beam in front of the gable
    sk = (0.0, yb - 0.13, zt + 0.12)
    skull(sk, s=1.75)
    for side in (-1, 1):
        antler((sk[0] + side * 0.10, sk[1] + 0.04, sk[2] + 0.10), side, length=0.40, r0=0.034)
    # skull-capped front dividers
    for sx in (-1, 1):
        skull((sx * DXF, yf - 0.005, PF + 0.012 + 0.10), s=1.0, yaw=sx * -8, tilt=-6)
    # iron straps down the front wall at the divider and corner posts' sides, riveted to the courses
    for x0, x1 in XBF:
        for xx in (x0 + 0.10, x1 - 0.10):
            iron("strap", (0.05, 0.006, TOPS["front"] - STONE_TOP + 0.02), (xx, -HY - 0.003, (STONE_TOP + TOPS["front"]) / 2))
            for zr_ in (STONE_TOP + 0.05, TOPS["front"] - 0.06): rivet((xx, -HY - 0.006, zr_), (0, -1, 0), s=0.02, h=0.007)

def join(obs, name):
    bpy.ops.object.select_all(action="DESELECT")
    for o in obs: o.select_set(True)
    bpy.context.view_layer.objects.active = obs[0]
    bpy.ops.object.join(); ob = bpy.context.active_object; ob.name = name
    return ob

def tri_list(me):
    V = [v.co.copy() for v in me.vertices]
    T = [(p.vertices[0], p.vertices[i], p.vertices[i + 1]) for p in me.polygons for i in range(1, len(p.vertices) - 1)]
    return V, T

# ---------- items ----------
TEMPL = {}
def load_templates():
    for item, (bay, longest, mode, _u, _c) in ITEMS.items():
        ob = load_item(item, anchor="center")[0]
        info = json.load(open(f"{ITEMS_DIR}/{item}/info.json"))
        bmin, bmax = Vector(info["bounds_min"]), Vector(info["bounds_max"])
        size = bmax - bmin
        s = longest / max(size)
        ob.data.transform(Matrix.Diagonal((s, s, s, 1))); ob.data.update()
        ob.location = (0, 0, -50); ob.hide_render = True; ob.name = "templ_" + item
        V = np.array([tuple(v.co) for v in ob.data.vertices], np.float32)
        bm = bmesh.new(); bm.from_mesh(ob.data)
        hull = bmesh.ops.convex_hull(bm, input=bm.verts)
        planes = []
        for f in [g for g in hull["geom"] if isinstance(g, bmesh.types.BMFace)]:
            n = f.normal.copy(); planes.append((n.x, n.y, n.z, n.dot(f.verts[0].co)))
        hv = np.array(sorted({tuple(round(c, 5) for c in v.co) for v in hull["geom"] if isinstance(v, bmesh.types.BMVert)}), np.float32)
        bm.free()
        TEMPL[item] = {"obj": ob, "mesh": ob.data, "V": V, "s": float(s), "size": tuple(size), "center": tuple((bmin + bmax) / 2),
                       "planes": np.array(planes, np.float32), "hv": hv, "radius": float(np.linalg.norm(V, axis=1).max()),
                       "he": (V.max(0) - V.min(0)) / 2, "mid": (V.max(0) + V.min(0)) / 2, "mode": mode,
                       "long": int(np.argmax(np.array(size))), "vol": float(np.prod(V.max(0) - V.min(0))),
                       "tris": [(p.vertices[0], p.vertices[i], p.vertices[i + 1]) for p in ob.data.polygons for i in range(1, len(p.vertices) - 1)]}

def orient(T_):
    if T_["mode"] == "flat":
        return Euler((math.radians(crng.uniform(-14, 14)), math.radians(crng.uniform(-14, 14)), crng.uniform(0, math.tau)), "XYZ").to_matrix()
    if T_["mode"] == "long":           # lying: the longest axis horizontal (a little tilt), any roll and yaw
        ax = T_["long"]; v = Vector([1.0 if i == ax else 0.0 for i in range(3)])
        A = v.rotation_difference(Vector((1, 0, 0))).to_matrix()
        return (Euler((0, 0, crng.uniform(0, math.tau))).to_matrix() @ Euler((0, math.radians(crng.uniform(-12, 12)), 0)).to_matrix()
                @ Euler((crng.uniform(0, math.tau), 0, 0)).to_matrix() @ A)
    q = Quaternion([crng.gauss(0, 1) for _ in range(4)]); q.normalize(); return q.to_matrix()

def world_verts(item, M):
    Mn = np.array(M); return TEMPL[item]["V"] @ Mn[:3, :3].T + Mn[:3, 3]

def add_rb(ob, kind, shape, mass=1.0, damp=(0.25, 0.45)):
    for o in bpy.context.view_layer.objects: o.select_set(False)
    ob.select_set(True); bpy.context.view_layer.objects.active = ob
    bpy.ops.rigidbody.object_add(type=kind)
    rb = ob.rigid_body
    rb.collision_shape = shape; rb.friction = 0.75; rb.restitution = 0.0
    rb.use_margin = True; rb.collision_margin = MARGIN
    if shape == "MESH": rb.mesh_source = "BASE"
    if kind == "ACTIVE":
        rb.mass = mass; rb.linear_damping, rb.angular_damping = damp
        rb.use_deactivation = False

def make_box_mesh(name, size):
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts: v.co = Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2]))
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    return me

def colliders(col, row):
    x0, x1, y0, y1 = bay_bounds(col, row)
    x0 += WALLGAP; x1 -= WALLGAP; y0 += WALLGAP; y1 -= WALLGAP
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2; T = 0.3; H = 5.0; FL = ROWFLOOR[row]
    obs = []
    for nm, sz, pos in [("floor", (x1 - x0 + 2 * T, y1 - y0 + 2 * T, T), (cx, cy, FL + 0.004 - T / 2)),
                        ("wx0", (T, y1 - y0 + 2 * T, H), (x0 - T / 2, cy, H / 2)), ("wx1", (T, y1 - y0 + 2 * T, H), (x1 + T / 2, cy, H / 2)),
                        ("wy0", (x1 - x0, T, H), (cx, y0 - T / 2, H / 2)), ("wy1", (x1 - x0, T, H), (cx, y1 + T / 2, H / 2))]:
        ob = bpy.data.objects.new(f"col_{col}{row}_{nm}", make_box_mesh(nm, sz)); ob.location = pos
        bpy.context.scene.collection.objects.link(ob); add_rb(ob, "PASSIVE", "BOX"); ob.hide_render = True; obs.append(ob)
    return obs

def surface(col, row, HV):
    x0, x1, y0, y1 = bay_bounds(col, row)
    nx, ny = int(math.ceil((x1 - x0) / GRID)), int(math.ceil((y1 - y0) / GRID))
    H = np.full((nx, ny), ROWFLOOR[row], np.float64)
    if len(HV):
        ix = np.clip(((HV[:, 0] - x0) / GRID).astype(int), 0, nx - 1); iy = np.clip(((HV[:, 1] - y0) / GRID).astype(int), 0, ny - 1)
        np.maximum.at(H, (ix, iy), HV[:, 2])
        P = np.pad(H, 1, mode="edge")
        H = np.max([P[i:i + nx, j:j + ny] for i in range(3) for j in range(3)], axis=0)
    gx = x0 + (np.arange(nx) + 0.5) * GRID; gy = y0 + (np.arange(ny) + 0.5) * GRID
    X, Y = np.meshgrid(gx, gy, indexing="ij")
    inner = (X - x0 > 0.04) & (x1 - X > 0.04) & (Y - y0 > 0.04) & (y1 - Y > 0.04)
    return X, Y, H, target(col, row, X, Y), inner

def check_copy(col, row, item, M):
    """escaped (out of the bay prism or under its floor), leaning (a vertex over a wall top within 2 cm of that wall's
    face), clipping (any triangle touches the frame)"""
    W = world_verts(item, M)
    x0, x1, y0, y1 = bay_bounds(col, row)
    e = WALLGAP - 0.006
    escaped = bool((W[:, 0] < x0 + e).any() or (W[:, 0] > x1 - e).any() or (W[:, 1] < y0 + e).any() or (W[:, 1] > y1 - e).any()
                   or (W[:, 2] < ROWFLOOR[row] - 0.004).any())
    ty0, ty1, tl, tr = wall_tops(col, row)
    lean = False
    for d, top in ((W[:, 0] - x0, tl), (x1 - W[:, 0], tr), (W[:, 1] - y0, ty0), (y1 - W[:, 1], ty1)):
        if ((d < WALLGAP + 0.02) & (W[:, 2] > top - 0.005)).any(): lean = True
    clip = fbvh.overlap(BVHTree.FromPolygons([Vector(tuple(float(a) for a in w)) for w in W], TEMPL[item]["tris"]))
    return escaped, lean, bool(clip)

SIMLOG = {"bays": {}, "frames": [], "retries": 0, "unsettled": 0, "why": {}}
def simulate_bay(item):
    (col, row), _l, _m, nunits, cap = ITEMS[item]
    sc = bpy.context.scene
    coll = bpy.data.collections.new(f"rb_{item}")
    sc.rigidbody_world.collection = coll
    cols_ = colliders(col, row)
    T_ = TEMPL[item]; R = T_["radius"]
    x0, x1, y0, y1 = bay_bounds(col, row)
    HV = np.zeros((0, 3), np.float32)
    copies = []; fails = 0; t0 = time.time()
    while len(copies) < cap and fails < 30:
        X, Y, H, Tg, inner = surface(col, row, HV)
        cover = float(((Tg - H)[inner] < 0.05).mean())
        if cover >= 0.93: break
        deficit = Tg - H
        placed = False
        for attempt in range(10):
            inset = WALLGAP + R * (0.5 if T_["mode"] != "long" else 0.35) + 0.01 + 0.02 * attempt
            sx_, sy_ = max(0.02, (x1 - x0) / 2 - inset), max(0.02, (y1 - y0) / 2 - inset)
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            best = None
            for _c in range(16):
                px, py = cx + crng.uniform(-sx_, sx_), cy + crng.uniform(-sy_, sy_)
                i = min(max(int((px - x0) / GRID), 0), X.shape[0] - 1); j = min(max(int((py - y0) / GRID), 0), X.shape[1] - 1)
                dfc = float(deficit[i, j])
                sc_ = -dfc + BACKW * (y1 - py) / (y1 - y0) + crng.uniform(0, 0.02 + 0.01 * attempt) + (1.0 if dfc < 0.02 else 0.0)
                if best is None or sc_ < best[0]: best = (sc_, px, py, dfc)
            _s, px, py, dfc = best
            if dfc < 0.02:                      # every candidate already reaches the target surface: no drop
                SIMLOG["why"]["no open spot"] = SIMLOG["why"].get("no open spot", 0) + 1
                continue
            m = (HV[:, 0] - px) ** 2 + (HV[:, 1] - py) ** 2 < (R + 0.06) ** 2 if len(HV) else None
            lt = float(HV[m, 2].max()) if m is not None and m.any() else ROWFLOOR[row]
            ob = bpy.data.objects.new(f"c_{item}_{len(copies)}_{attempt}", T_["mesh"]); sc.collection.objects.link(ob)
            ob.matrix_world = Matrix.Translation(Vector((px, py, lt + 0.02 + R))) @ orient(T_).to_4x4()
            add_rb(ob, "ACTIVE", "CONVEX_HULL", mass=max(0.05, T_["vol"] * 700))
            bpy.context.view_layer.update()
            sc.frame_set(1)
            prev = None; still = 0; f = 1; dp = dr = 0.0
            while f < 300:
                f += 1; sc.frame_set(f)
                cur = (ob.matrix_world.translation.copy(), ob.matrix_world.to_quaternion())
                if prev:
                    dp = (cur[0] - prev[0]).length; dr = cur[1].rotation_difference(prev[1]).angle
                    still = still + 1 if (dp < 2e-4 and dr < 4e-3 and f > 8) else 0
                    if still >= 3: break
                prev = cur
            M = ob.matrix_world.copy()
            esc, lean, clip = check_copy(col, row, item, M)
            over = float(world_verts(item, M)[:, 2].max()) > crown_cap(col, row) + 0.05
            if esc or lean or clip or over or still < 3:
                why = "escaped" if esc else "leaning" if lean else "clipping" if clip else "over the crown" if over else "unsettled"
                SIMLOG["why"][why] = SIMLOG["why"].get(why, 0) + 1
                bpy.data.objects.remove(ob, do_unlink=True); SIMLOG["retries"] += 1
                if still < 3: SIMLOG["unsettled"] += 1
                continue
            SIMLOG["frames"].append(f)
            ob.rigid_body.type = "PASSIVE"
            ob.matrix_world = M
            bpy.context.view_layer.update()
            sc.frame_set(1)
            copies.append({"item": item, "M": M.copy(), "obj": ob})
            Mn = np.array(M)
            HV = np.concatenate([HV, (T_["hv"] @ Mn[:3, :3].T + Mn[:3, 3]).astype(np.float32)])
            placed = True
            break
        fails = 0 if placed else fails + 1
    X, Y, H, Tg, inner = surface(col, row, HV)
    cover = float(((Tg - H)[inner] < 0.05).mean())
    ty0, ty1, tl, tr = wall_tops(col, row)
    SIMLOG["bays"][item] = {"copies": len(copies), "units": nunits, "cover_5cm": round(cover, 3),
                            "peak": round(float(HV[:, 2].max()), 3) if len(HV) else None, "front_wall_top": ty0, "side_wall_tops": [tl, tr],
                            "floor": ROWFLOOR[row], "tris": len(copies) * len(T_["tris"]), "seconds": round(time.time() - t0, 1)}
    print("BAY", item, json.dumps(SIMLOG["bays"][item]), flush=True)
    for o in cols_: bpy.data.objects.remove(o, do_unlink=True)
    return copies

# ---------- checks ----------
def interpenetration(cps):
    P = np.array([np.array(cp["M"])[:3, 3] for cp in cps]); R = np.array([TEMPL[cp["item"]]["radius"] for cp in cps])
    worst = 0.0; npairs = 0; over = []
    for i in range(len(cps)):
        d = np.linalg.norm(P - P[i], axis=1)
        for j in np.nonzero((d < R + R[i]) & (np.arange(len(cps)) > i))[0]:
            npairs += 1
            for a, b in ((i, int(j)), (int(j), i)):
                Ma, Mb = np.array(cps[a]["M"]), np.array(cps[b]["M"])
                Ta, Tb = TEMPL[cps[a]["item"]], TEMPL[cps[b]["item"]]
                x = Ta["hv"] @ Ma[:3, :3].T + Ma[:3, 3]
                xb = (x - Mb[:3, 3]) @ Mb[:3, :3]
                pl = Tb["planes"]
                m = float((pl[:, 3][None, :] - xb @ pl[:, :3].T).min(axis=1).max())
                if m > 0: over.append(m)
                worst = max(worst, m)
    return worst, npairs, over

# ---------- anchors (Unity prefab space: ux=-bx, uy=bz, uz=-by) ----------
CB2U = Matrix(((-1, 0, 0), (0, 0, 1), (0, -1, 0)))
def b2u_vec(v): return (-v[0], v[2], -v[1])
def rot_to_unity(R):
    Ru = CB2U @ R @ CB2U.transposed()
    q = Ru.to_quaternion()
    e = Ru.to_euler("ZXY")
    ex = Matrix.Rotation(e.x, 3, "X"); ey = Matrix.Rotation(e.y, 3, "Y"); ez = Matrix.Rotation(e.z, 3, "Z")
    err = max(abs(a - b) for ra, rb in zip((ey @ ex @ ez), Ru) for a, b in zip(ra, rb))
    return [round(math.degrees(e.x), 3), round(math.degrees(e.y), 3), round(math.degrees(e.z), 3)], [round(q.x, 5), round(q.y, 5), round(q.z, 5), round(q.w, 5)], err

def bounds_low(cp):
    M = np.array(cp["M"]); T = TEMPL[cp["item"]]
    c = M[:3, :3] @ T["mid"] + M[:3, 3]
    return float(c[2] - np.abs(M[2, :3]) @ T["he"])

def bounds_high(cp):
    M = np.array(cp["M"]); T = TEMPL[cp["item"]]
    c = M[:3, :3] @ T["mid"] + M[:3, 3]
    return float(c[2] + np.abs(M[2, :3]) @ T["he"])

def build_units(seqs):
    """cut each bay's copy sequence into its units (drop order), then interleave the 128 units by fill fraction"""
    units = []
    for item, seq in seqs.items():
        nu = ITEMS[item][3]; C = len(seq)
        assert C >= nu, (item, C, nu)
        for k in range(nu):
            a, b = round(k * C / nu), round((k + 1) * C / nu)
            units.append({"bay": GROUP[item], "item": item, "k": k, "frac": (k + 0.5) / nu + crng.uniform(-0.01, 0.01), "copies": seq[a:b]})
    units.sort(key=lambda u: (u["frac"], BAYS.index(u["item"])))
    for n, u in enumerate(units): u["index"] = n; u["step"] = n * 8 // NUNITS
    return units

def build_anchors(units, seqs, frame_info, checks):
    maxerr = 0; out = []
    bayinfo = {}
    for item, seq in seqs.items():
        (col, row) = ITEMS[item][0]
        x0, x1, y0, y1 = bay_bounds(col, row)
        floor = min(bounds_low(cp) for cp in seq) - 0.002
        top = max(bounds_high(cp) for cp in seq)
        bayinfo[item] = (floor, top, (y0 + y1) / 2, y1 - y0, x0, x1)
    for u in units:
        floor, top, ycen, depth, x0, x1 = bayinfo[u["item"]]
        W = np.concatenate([world_verts(cp["item"], cp["M"]) for cp in u["copies"]])
        cx = float((W[:, 0].min() + W[:, 0].max()) / 2)
        c = Vector((cx, ycen, (floor + top) / 2))
        cps = []
        for cp in u["copies"]:
            M = cp["M"]; eul, quat, err = rot_to_unity(M.to_3x3().normalized()); maxerr = max(maxerr, err)
            T = TEMPL[cp["item"]]
            cps.append({"item": cp["item"], "offset": [round(a, 4) for a in b2u_vec(M.translation - c)], "euler": eul, "quat_xyzw": quat,
                        "fit_longest_m": ITEMS[cp["item"]][1], "scale_of_true_size": round(T["s"], 4),
                        "world_position": [round(a, 4) for a in b2u_vec(M.translation)]})
        (col, row) = ITEMS[u["item"]][0]
        out.append({"index": u["index"], "step": u["step"], "kind": "heap_step", "item": u["item"], "bay": u["bay"], "cell": [col, row],
                    "position": [round(a, 4) for a in b2u_vec(c)], "rotation": [0, 0, 0],
                    "box": [round(max(0.05, float(W[:, 0].max() - W[:, 0].min())), 4), round(top - floor, 4), round(0.9 * depth, 4)],
                    "copies": cps})
    bays = []
    for g, its in enumerate(GROUPS):
        cells = []
        for item in its:
            (col, row), longest, mode, nu, _cap = ITEMS[item]
            us = [u for u in units if u["item"] == item]
            x0, x1, y0, y1 = bay_bounds(col, row)
            ty0, ty1, tl, tr = wall_tops(col, row)
            cells.append({"item": item, "cell": [col, row], "units": nu, "copies": len(seqs[item]),
                          "copies_per_unit": [len(u["copies"]) for u in sorted(us, key=lambda u: u["k"])],
                          "inner_x_unity": [round(-x1, 3), round(-x0, 3)], "inner_z_unity": [round(-y1, 3), round(-y0, 3)],
                          "floor_y": ROWFLOOR[row], "wall_tops_y": {"front": ty0, "back": ty1, "x0_side": tl, "x1_side": tr},
                          "heap_peak_y": SIMLOG["bays"][item]["peak"], "cover_5cm": SIMLOG["bays"][item]["cover_5cm"],
                          "tris_full": SIMLOG["bays"][item]["tris"]})
        row = ITEMS[its[0]][0][1]
        e = {"bay": g, "row": "back" if row else "front", "items": its, "units": sum(c["units"] for c in cells),
             "shared": len(its) > 1, "cells": cells}
        if len(its) > 1:
            e["divider"] = {"kind": "hewn plank, built into the model", "x_blender": 0.0, "thickness_m": DT, "top_y": DIVTOP,
                            "side_of_item_unity_x": {c["item"]: ("minus" if (-(bay_bounds(*c["cell"])[0] + bay_bounds(*c["cell"])[1]) / 2) < 0 else "plus") for c in cells}}
        else:
            e["item"] = its[0]; e["cell"] = cells[0]["cell"]
        bays.append(e)
    items = {}
    for it in ITEMS:
        T = TEMPL[it]
        items[it] = {"bounds_size_unity": [round(T["size"][0], 4), round(T["size"][2], 4), round(T["size"][1], 4)],
                     "bounds_center_unity": [round(a, 4) for a in b2u_vec(T["center"])], "scale_of_true_size": round(T["s"], 4),
                     "fit_longest_m": ITEMS[it][1], "mode": ITEMS[it][2], "tris_per_copy": len(T["tris"])}
    doc = {
        "store": "Ossuary Bin round 2: a stone-footed timber outbuilding bin with a gable, six bays for seven kinds of bone: one kind per bay, "
                 "except the biggest bay (back middle), which holds the two skulls either side of a built-in divider plank; heaped and crowned over the walls when full",
        "slots": NUNITS, "units": len(out), "steps": 8, "stack_per_unit": 1, "frame": frame_info, "placement": "ground",
        "filter_prefabs": FILTER,
        "space": "Unity prefab space, origin = footprint centre on the ground. Blender z-up/-y front -> Unity y-up/+z front: ux=-bx, uy=bz, uz=-by. "
                 "OBJ export (forward NEGATIVE_Z, up Y) writes (bx, bz, -by); Unity's importer negates x, same mapping.",
        "unit_semantics": "SETTLED: every copy has an explicit final pose from a rigid-body simulation (convex-hull items, friction 0.75, restitution 0, "
                          "damping 0.25/0.45), dropped one copy at a time onto the frozen earlier ones; each bay's copy sequence is cut into its "
                          "units in drop order. Each copy: the item's bounds centre at unit.position + copy.offset (= copy.world_position), rotated by "
                          "copy.quat_xyzw (or copy.euler, Unity ZXY), longest side fit_longest_m. unit.position: x = centre of the unit's copies, "
                          "y = the bay's mid height, z = the bay's centre. unit.box: x = the copies' width, y = the bay's lowest rotated-bounds "
                          "corner to its highest copy (the never-below-the-floor lift leaves every settled copy alone), z = 90% of the bay's inner depth.",
        "fill_order": "units are listed in fill order (interleaved over the bays); within a bay its units fill in drop order (a heap against the "
                      "bay's back wall first, crowned over the walls last). Show the first n copies of a unit for a partial stack. Later copies rest "
                      "on earlier ones, earlier ones never move. One item kind per bay except group 1 (the shared bay, two kinds, "
                      "each on its own units: unit.item says which; the model carries the divider plank, the mod draws no board there). Groups 0-2 = back row, "
                      "3-5 = front row, left to right as seen from the front; cell = [column, row], row 1 = back, back-row columns 1 and 2 = the shared bay's halves.",
        "bays": bays, "items": items, "checks": checks, "rotation_convert_max_err": maxerr, "units_list": out}
    return doc

# ---------- scene + frame ----------
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
atlas = build_atlas()
MAT = bpy.data.materials.new("ossuary"); MAT.use_nodes = True
_b = MAT.node_tree.nodes["Principled BSDF"]
_t = MAT.node_tree.nodes.new("ShaderNodeTexImage"); _t.image = atlas; _t.interpolation = "Closest"
MAT.node_tree.links.new(_t.outputs["Color"], _b.inputs["Base Color"])
_b.inputs["Roughness"].default_value = 1.0; _b.inputs["Specular IOR Level"].default_value = 0.0

build_frame()
frame = join(list(PARTS), "Ossuary")
FV_, FT_ = tri_list(frame.data)
frame_tris = len(FT_)
fbvh = BVHTree.FromPolygons(FV_, FT_, all_triangles=True)
FVn = np.array([tuple(v) for v in FV_])
frame_size = (float(FVn[:, 0].max() - FVn[:, 0].min()), float(FVn[:, 2].max()), float(FVn[:, 1].max() - FVn[:, 1].min()))
print("FRAME tris", frame_tris, "size W H D", [round(a, 3) for a in frame_size], "x", round(FVn[:, 0].min(), 3), round(FVn[:, 0].max(), 3),
      "y", round(FVn[:, 1].min(), 3), round(FVn[:, 1].max(), 3), "z", round(FVn[:, 2].min(), 3), round(FVn[:, 2].max(), 3), flush=True)
for it in BAYS: print("BAY GEOM", GROUP[it], it, ITEMS[it][0], [round(a, 3) for a in bay_bounds(*ITEMS[it][0])], flush=True)

load_templates()
for it, T in TEMPL.items(): print("ITEM", it, "scale of true size", round(T["s"], 4), "longest", ITEMS[it][1], "tris", len(T["tris"]), "radius", round(T["radius"], 3))
if "--probe" in argv:
    print("DONE probe"); sys.exit(0)
FRAMEONLY = "--frame-only" in argv          # look at the frame: export the OBJ, render without contents
if FRAMEONLY:
    bpy.ops.object.select_all(action="DESELECT"); frame.select_set(True); bpy.context.view_layer.objects.active = frame
    bpy.ops.wm.obj_export(filepath=os.path.join(OUTA, "Ossuary.obj"), export_selected_objects=True, export_materials=False,
                          export_triangulated_mesh=True, forward_axis="NEGATIVE_Z", up_axis="Y")
RENDERONLY = "--render-only" in argv          # replay the files already in the assets folder
if not FRAMEONLY and not RENDERONLY:
  sc.render.fps = FPS
  bpy.ops.rigidbody.world_add()
  rbw = sc.rigidbody_world
  rbw.substeps_per_frame = 20; rbw.solver_iterations = 40; rbw.time_scale = 1.0
  rbw.point_cache.frame_start = 1; rbw.point_cache.frame_end = 400
  sc.frame_start = 1; sc.frame_end = 400
  t0 = time.time()
  seqs = {it: simulate_bay(it) for it in BAYS}
  print("SIM seconds", round(time.time() - t0, 1), "retries", SIMLOG["retries"], SIMLOG["why"], "unsettled tries", SIMLOG["unsettled"], flush=True)
  allc = [cp for it in BAYS for cp in seqs[it]]
  res = [(cp, check_copy(*ITEMS[cp["item"]][0], cp["item"], cp["M"])) for cp in allc]
  clip = [cp for cp, r in res if r[2]]; esc = [cp for cp, r in res if r[0]]; lean = [cp for cp, r in res if r[1]]
  pen, npairs, over = interpenetration(allc)
  print("CLIPPING", len(clip), "of", len(allc), "; ESCAPED", len(esc), "; LEANING over a wall top", len(lean))
  print("INTERPENETRATION max", round(pen * 1000, 2), "mm over", npairs, "near pairs;", len(over), "pairs penetrate, median",
        round(float(np.median(over)) * 1000, 2) if over else 0, "mm")
  short = {it: (len(seqs[it]), ITEMS[it][3]) for it in BAYS if len(seqs[it]) < ITEMS[it][3]}
  if short:
      print("TOO FEW COPIES for the units", short, flush=True); sys.exit(1)
  units = build_units(seqs)
  tris_full = sum(len(TEMPL[cp["item"]]["tris"]) for cp in allc)
  checks = {"clipping": len(clip), "of_copies": len(allc), "escaped": len(esc), "leaning_over_wall_top": len(lean),
            "interpenetration_max_m": round(max(pen, 0.0), 5), "retries": SIMLOG["retries"], "retry_reasons": SIMLOG["why"],
            "contents_tris_full_ripped_models": tris_full, "frame_tris": frame_tris, "store_tris_full": tris_full + frame_tris,
            "per_bay": SIMLOG["bays"]}
  frame_info = {"obj": "Ossuary.obj", "tris": frame_tris, "size_m": [round(a, 3) for a in frame_size], "atlas": "ossuary_atlas.png 128x128",
                "atlas_sources": "rows 0-31 hewn timber, 32-63 x0-63 end grain, 64-79 iron, 112-127 x96-127 iron (spare): assets/bunker_r4; 32-63 "
                                 "x64-95 dark oiled timber, x96-127 wear swatch: assets/metalpallet_r3; 80-111 four stone-block tiles: assets/orebin_r5; "
                                 "112-127 x0-95: bone, dark socket, antler (new, for the skull and antler decor)"}
  doc = build_anchors(units, seqs, frame_info, checks)
  print("UNITS", len(units), "copies per bay", {it: len(seqs[it]) for it in BAYS}, "rot err", doc["rotation_convert_max_err"])
  print("TRIS frame", frame_tris, "contents full", tris_full, "store full", tris_full + frame_tris, flush=True)
  json.dump(SIMLOG, open(os.path.join(OUT, "simlog.json"), "w"), indent=1)
  for cp in allc: bpy.data.objects.remove(cp["obj"], do_unlink=True)
  bpy.ops.rigidbody.world_remove()
  # files: atlas (saved) -> OBJ -> anchors last (temp file + rename)
  bpy.ops.object.select_all(action="DESELECT"); frame.select_set(True); bpy.context.view_layer.objects.active = frame
  bpy.ops.wm.obj_export(filepath=os.path.join(OUTA, "Ossuary.obj"), export_selected_objects=True, export_materials=False,
                        export_triangulated_mesh=True, forward_axis="NEGATIVE_Z", up_axis="Y")
  tmp = os.path.join(OUT, "ossuary_anchors.json.tmp")
  json.dump(doc, open(tmp, "w"), indent=1)
  os.replace(tmp, os.path.join(OUTA, "ossuary_anchors.json"))
  print("OSSUARY written", OUTA, flush=True)
if NORENDER:
    print("DONE"); sys.exit(0)

# ---------- renders: replayed from the EXPORTED files the mod's way ----------
for o in list(bpy.data.objects): bpy.data.objects.remove(o, do_unlink=True)
C = Matrix(((-1, 0, 0), (0, 0, 1), (0, -1, 0)))
def u2b_pos(p): return Vector((-p[0], -p[2], p[1]))
def u2b_rot(q): return C.transposed() @ Quaternion((q[3], q[0], q[1], q[2])).to_matrix() @ C

def atlas_mat(png, name):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    t = m.node_tree.nodes.new("ShaderNodeTexImage"); t.image = bpy.data.images.load(png); t.interpolation = "Closest"
    m.node_tree.links.new(t.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 1.0; b.inputs["Specular IOR Level"].default_value = 0.0
    return m

def import_frame(objpath, png, dx, dy):
    before = set(bpy.data.objects)
    bpy.ops.wm.obj_import(filepath=objpath, forward_axis="NEGATIVE_Z", up_axis="Y")
    new = [o for o in bpy.data.objects if o not in before]
    m = atlas_mat(png, os.path.basename(png) + str(dx))
    for o in new:
        o.data.materials.clear(); o.data.materials.append(m); o.location = (dx, dy, 0)
    return new

RAW = {}
def raw_mesh(item):
    if item not in RAW:
        ob = load_item(item, anchor="center")[0]
        info = json.load(open(f"{ITEMS_DIR}/{item}/info.json"))
        for m in ob.data.materials:
            b = m.node_tree.nodes.get("Principled BSDF")
            if b: b.inputs["Specular IOR Level"].default_value = 0.1; b.inputs["Roughness"].default_value = 0.9
            if item == "HardAntler" and b:      # render only: the ripped antler UVs land on red patches of Eikthyr's body
                nt = m.node_tree                # texture; the game's hard antler reads as pale grey bone, so desaturate it
                lk = [l for l in nt.links if l.to_node == b and l.to_socket.name == "Base Color"]
                if lk:
                    hs = nt.nodes.new("ShaderNodeHueSaturation"); hs.inputs["Saturation"].default_value = 0.15
                    src = lk[0].from_socket; nt.links.remove(lk[0])
                    nt.links.new(src, hs.inputs["Color"]); nt.links.new(hs.outputs["Color"], b.inputs["Base Color"])
        RAW[item] = (ob.data, np.array([tuple(v.co) for v in ob.data.vertices], np.float32), max(Vector(info["bounds_max"]) - Vector(info["bounds_min"])))
        bpy.data.objects.remove(ob, do_unlink=True)
    return RAW[item]

LIFTS = {}
def spawn_file(folder, obj, png, anchors, fill, dx, dy, tag):
    """the store replayed from its files: per bay its first fill x units in list order, a partial last unit, copies at
    unit.position + copy.offset, longest side fit_longest_m, the mod's never-below-the-floor lift"""
    import_frame(os.path.join(folder, obj), os.path.join(folder, png), dx, dy)
    if fill <= 0: return
    d = json.load(open(os.path.join(folder, anchors)))
    groups = {}
    for u in d["units_list"]: groups.setdefault(u["bay"], []).append(u)
    lifts = 0
    for g, us in groups.items():
        exact = fill * len(us); n = int(math.floor(exact + 1e-9)); part = exact - n
        for ui, u in enumerate(us[:n + (1 if part > 1e-6 else 0)]):
            cps = u["copies"] if ui < n else u["copies"][:max(1, math.ceil(len(u["copies"]) * part))]
            floor = u["position"][1] - u["box"][1] / 2
            for cp in cps:
                mesh, Vv, longest = raw_mesh(cp["item"])
                s = cp["fit_longest_m"] / longest
                Rb = u2b_rot(cp["quat_xyzw"])
                p = u2b_pos([a + b for a, b in zip(u["position"], cp["offset"])])
                he = (Vv.max(0) - Vv.min(0)) / 2 * s; mid = (Vv.max(0) + Vv.min(0)) / 2 * s
                Rn = np.array(Rb)
                low = float((Rn @ mid)[2] + p.z - np.abs(Rn[2]) @ he)
                if low < floor - 1e-4: p.z += floor - low; lifts += 1
                ob = bpy.data.objects.new(f"{tag}_item", mesh); sc.collection.objects.link(ob)
                ob.matrix_world = Matrix.Translation(p + Vector((dx, dy, 0))) @ Rb.to_4x4() @ Matrix.Diagonal((s,) * 3 + (1,))
    LIFTS[f"{tag}@{fill}"] = lifts

pm = bpy.data.materials.new("plain"); pm.use_nodes = True
pm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.62, 0.60, 0.55, 1)
def post18(x, y):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(x, y, 0.9)); p = bpy.context.active_object
    p.scale = (0.12, 0.12, 1.8); p.data.materials.append(pm); p.name = "post_1.8m"

A_ = (OUTA, "Ossuary.obj", "ossuary_atlas.png", "ossuary_anchors.json")
FULL = 0.0 if FRAMEONLY else 1.0
ROWS = {"empty": 0.0, "half": 8.0, "full": 16.0, "fam": 34.0}
spawn_file(*A_, 0.0, 0.0, ROWS["empty"], "e")
spawn_file(*A_, 0.5 * FULL, 0.0, ROWS["half"], "h")
spawn_file(*A_, FULL, 0.0, ROWS["full"], "f")
post18(-2.05, ROWS["full"] - 0.5)
# family: r2 in the middle, the bunker_r4 frame at the same scale on the left, r1 on the right (both full), a 1.8 m post between r2 and the bunker
spawn_file(*A_, FULL, 0.0, ROWS["fam"], "fam")
import_frame(os.path.join(REPO, "assets", "bunker_r4", "Bunker.obj"), os.path.join(REPO, "assets", "bunker_r4", "bunker_atlas.png"), -4.0, ROWS["fam"])
R1_ = os.path.join(REPO, "assets", "ossuary_r1")
spawn_file(R1_, "Ossuary.obj", "ossuary_atlas.png", "ossuary_anchors.json", FULL, 4.2, ROWS["fam"], "r1")
post18(-1.85, ROWS["fam"] - 1.0)
print("MOD FLOOR LIFTS", LIFTS, flush=True)

world = bpy.data.worlds.new("w"); sc.world = world; world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.42, 0.45, 0.5, 1)
world.node_tree.nodes["Background"].inputs[1].default_value = 0.9
sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN")); sun.data.energy = 3.2
sun.rotation_euler = (math.radians(50), 0, math.radians(35)); sc.collection.objects.link(sun)
bpy.ops.mesh.primitive_plane_add(size=160, location=(0, 12, 0))
gm = bpy.data.materials.new("ground"); gm.use_nodes = True
gm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.16, 0.14, 0.11, 1)
bpy.context.active_object.data.materials.append(gm)
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam); sc.camera = cam
sc.render.engine = "BLENDER_EEVEE_NEXT"
sc.render.resolution_x, sc.render.resolution_y = (1000, 562) if QUICK else (1600, 900)
sc.view_settings.view_transform = "Standard"
EYE = 1.75
VIEWS = {  # name: (yaw deg, horizontal distance, eye height, target, lens)
    "empty": (-30, 5.6, 2.3, (0.0, ROWS["empty"], 0.7), 35),
    "half": (-30, 5.6, 2.3, (0.0, ROWS["half"], 0.7), 35),
    "full": (-30, 5.6, 2.3, (0.0, ROWS["full"], 0.7), 35),
    "standing-half": (0, 2.9, EYE, (0.0, ROWS["half"], 0.45), 30),
    "standing-full": (0, 2.9, EYE, (0.0, ROWS["full"], 0.45), 30),
    "post": (-22, 5.4, 1.5, (-0.3, ROWS["full"], 0.85), 35),
    "family": (-6, 13.0, 3.2, (0.1, ROWS["fam"], 0.8), 35),
    "bunker": (-8, 9.0, 2.4, (-1.9, ROWS["fam"], 0.9), 35),
    "shared": (-12, 2.4, 1.8, (0.0, ROWS["full"] + 0.1, 0.7), 35),
    "shared-top": (0, 1.6, 2.4, (0.0, ROWS["full"] + 0.25, 0.55), 35),
    "decor": (-18, 2.4, 1.6, (0.0, ROWS["empty"] + 0.6, 1.45), 35),
}
for vn, (yaw, dist, hgt, tgt, lens) in VIEWS.items():
    if VIEWSEL and vn not in VIEWSEL: continue
    t = Vector(tgt)
    cam.location = t + Vector((math.sin(math.radians(yaw)) * dist, -math.cos(math.radians(yaw)) * dist, hgt - t.z))
    cam.rotation_euler = (t - cam.location).to_track_quat("-Z", "Y").to_euler(); cam.data.lens = lens
    sc.render.filepath = os.path.join(OUT, f"ossuary2-{vn}.png")
    bpy.ops.render.render(write_still=True)
    print("RENDER", vn, flush=True)
print("DONE")
