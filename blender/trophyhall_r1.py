"""Trophy Hall round 1 (ITEMS.md section 2, #1): a free-standing wall of trophy boards, 10 columns x 8 rows = 80 boards, one board per trophy.
A NEW piece (SPEC.md "Released pieces stay"): about 4.1 m wide x 2.4 m tall, a trophy sticks out up to 0.34 m in front of its board. A 2 m / 40-slot
half is the same script with --cols 5 (and --assets to keep it apart): 5 x 8 = 40 boards.

DISPLAY store, like the Larder Hutch and the Shelf: one model per stack (a stack of 20 Neck trophies shows one Neck trophy on its board), 80 plain units
(no group key), one unit per board, listed in grid order (index = row * NCOL + column, row 0 the top, column 0 the left as seen from the front), so the
mod can mirror the container grid exactly: a 10 x 8 container is the wall. An empty board stands empty (plaque only: the model has no trophy in it).
The trophy models are the game's own (ripped by assets/trophyhall_r1/rip_trophies.py: 71 of the 72 Trophy* prefabs; TrophyForestTroll has no mesh in the bundle).

How a trophy is placed on a board (the mod's own display rule, simulated here for the renders and the clip check):
  unit "position" = the hang point: the centre of the board's FRONT face (Unity prefab space, +z front). unit "box_size" = the fit box.
  the copy: "fit_box" [0.316, 0.227, 0.28] (x width, y height, z depth), "anchor" "back", "offset" [0, 0, 0.018], rotation 0.
  s = min(DisplaySize x RootScale (0.7 x 1), 1.15 x min(box.x / size.x, box.y / size.y, box.z / size.z))      (Storehouse.Place, display = true)
  centred in x and y on the hang point; with "anchor" "back" its back plane (the least-z face of its bounds) sits 0.018 m in front of the board.
  The 1.15 is the mod's own tolerance, so a trophy never exceeds 1.15 x box = [0.363, 0.261, 0.322]: inside its cell (pitch 0.375 x 0.2725) in x and y,
  whatever its shape, and at most 0.322 m deep. A Fader or Moder head (3-5 m in the game files) is shrunk to the box, a Ghost or Surtling (0.25-0.37 m) shows
  at 0.7 of its true size, like every display item.
  "anchor":"back" is NEW: Storehouse.Place knows "bottom" (item stands on the unit's plane) but not "back" (item hangs on it). Without it the item is centred on the
  hang point and sinks half its depth into the board; see "placement" in the anchors file for the three-line change. The file is safe to load as it is (an
  unknown anchor word reads as not-bottom).

Frame (Blender x lateral centred, y: front = -y, the footprint centred on y = 0, z = 0 the floor):
  two posts 0.15 x 0.20, a 0.14 m header (beam + overhanging cap, the trophies' roof), a 0.08 sill, 15 hewn back planks, 80 plaques (0.345 x 0.245 x 0.035, two iron
  bands with a rivet each), two sled runners under the posts (1.0 m long) with a diagonal back strut each, two back rails. Nothing stands in front of a board's
  face except 8 mm of iron: every trophy's bounding box stays inside its own cell and 18 mm clear of the face, so a trophy cannot clip the board, the
  neighbours, the posts, the header or the sill (checked on the real meshes below, for every ripped kind, on five boards).
Atlas: bunker_r4's, byte-identical (hewn timber, end grain, dark iron); no new colour.
Run: "C:/Program Files/Blender Foundation/Blender 4.5/blender.exe" -b -P trophyhall_r1.py -- [--out DIR] [--assets DIR] [--no-render] [--no-export] [--cols N] [--quick]
Files (assets/trophyhall_r1/): TrophyHall.obj (frame only), trophyhall_atlas.png, trophyhall_anchors.json (last, temp + rename), rip_trophies.py (not a Blender script).
Unity prefab space: ux = -bx, uy = bz, uz = -by (OBJ exported forward -Z, up Y, like every store).
"""
import bpy, bmesh, sys, os, math, json, random, time, re, shutil
import numpy as np
from mathutils import Vector, Matrix, Euler
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, ".."))
OUTA = os.path.join(REPO, "assets", "trophyhall_r1")
BUNKER = os.path.join(REPO, "assets", "bunker_r4")
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
def arg(k, d=None): return argv[argv.index(k) + 1] if k in argv else d
OUT = arg("--out", "C:/Users/joost/AppData/Local/Temp/claude/C--Users-joost--pai/5e4bc60b-cdfe-4638-8e29-2e507fa13cf9/scratchpad/trophyhall_r1")
RENDER = "--no-render" not in argv
QUICK = "--quick" in argv
EXPORT = "--no-export" not in argv
ITEMS_DIR = "C:/Users/joost/ValheimRip/items"
TROPHY_DIR = "C:/Users/joost/ValheimRip/trophies"
sys.path.append(ITEMS_DIR)
import load_item as LI
LI.ROOT = TROPHY_DIR
OUTA = arg("--assets", OUTA)
os.makedirs(OUTA, exist_ok=True); os.makedirs(OUT, exist_ok=True)

rng = random.Random(7)
TEX = 128
DENS = 48.0
STRIP = {"hewn": 0.75, "end": 0.50, "iron": 0.375}
STRIPH = {"hewn": 32, "iron": 16}

# ---------- layout ----------
NCOL = int(arg("--cols", 10)); NROW = 8
NUNITS = NCOL * NROW
PITCH_X, PITCH_Y = 0.375, 0.2725
PS_X, PS_Y = 0.15, 0.20                     # post section
XIN = NCOL * PITCH_X / 2                    # inner face of the posts (1.875)
PX = XIN + PS_X / 2                         # post centre x
Z_SILL = 0.08                               # sill top = first row's floor
Z_TOP = Z_SILL + NROW * PITCH_Y             # the header's underside (2.26)
H = 2.40
YW = -0.10                                  # mid plane of the back wall; the footprint (runners) is y -0.5..0.5
WALL_T = 0.06
BOARD_T = 0.035
YF = YW - WALL_T / 2 - BOARD_T              # a board's front face (-0.165)
HANG_CLEAR = 0.018                          # a trophy's back plane stands this far in front of the face (iron fittings stand out 13 mm)
DISPLAY = 0.7                               # the mod's "Display item size"
TOL = 1.15                                  # Storehouse.Place: display size capped at 1.15 x the slot fit
BOX = ((PITCH_X - 0.012) / TOL, (PITCH_Y - 0.012) / TOL, 0.28)     # fit box x (width), y (height), z (depth); x 0.316, y 0.2265, z 0.28
BOARD_W, BOARD_H = 0.345, 0.245
def col_x(c): return (c - (NCOL - 1) / 2) * PITCH_X
def row_z(r): return Z_TOP - (r + 0.5) * PITCH_Y

# ---------- atlas ----------
def build_atlas():
    shutil.copyfile(os.path.join(BUNKER, "bunker_atlas.png"), os.path.join(OUTA, "trophyhall_atlas.png"))   # byte-identical to bunker_r4's
    return bpy.data.images.load(os.path.join(OUTA, "trophyhall_atlas.png"))

# ---------- geometry helpers (bunker_r4's / the Apothecary's) ----------
PARTS = []
UV = None

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
            l[UV].uv = ((k + 0.5 + a * 0.45) / 4, STRIP["end"] + (0.5 + b * 0.45) / 4)
        return
    ua = long_axis if long_axis in tang else tang[0]
    va = tang[1] if ua == tang[0] else tang[0]
    off = (seed * 0.37) % 1
    vs = [l.vert.co[va] for l in f.loops]
    vmin, span = min(vs), max(max(vs) - min(vs), 1e-4)
    hpx = STRIPH[kind]
    vscale = min(1.0, (hpx / DENS) / span)
    room = max(hpx / TEX - span * vscale * DENS / TEX * 0.94 - 0.012, 0)
    voff = ((seed * 0.618) % 1) * room
    for l in f.loops:
        u = l.vert.co[ua] * DENS / TEX + off
        v = STRIP[kind] + ((l.vert.co[va] - vmin) * vscale * DENS / TEX) * 0.94 + 0.0075 + voff
        l[UV].uv = (u, v)

def link(bm, name):
    bm.normal_update()
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = False
    ob = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(ob)
    ob.data.materials.append(MAT); PARTS.append(ob)
    return ob

def timber(name, size, pos, kind="hewn", rot=(0, 0, 0), jitter=0.022, bevel=0.022):
    global UV
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
    bm.normal_update()
    UV = bm.loops.layers.uv.verify()
    seed = rng.randrange(1000)
    for f in bm.faces: uv_face(f, kind, long_axis, seed + f.index % 2)
    bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Euler([math.radians(a) for a in rot]).to_matrix())
    bmesh.ops.translate(bm, verts=bm.verts, vec=Vector(pos))
    return link(bm, name)

def plank(name, size, pos, rot=(0, 0, 0), kind="hewn", jitter=0.006, bevel=0.008):
    return timber(name, size, pos, kind=kind, rot=rot, jitter=jitter, bevel=bevel)

def iron(name, size, pos, rot=(0, 0, 0)):
    return timber(name, size, pos, kind="iron", rot=rot, jitter=0.0015, bevel=0)

def rivet(pos, size=0.03, depth=0.012, face=(1, -1)):
    s = [size, size, size]; s[face[0]] = depth
    p = list(pos); p[face[0]] += face[1] * depth / 2
    iron("rivet", s, p)

def strut(name, p0, p1, sec, kind="hewn"):
    """a timber of section sec x sec between two points"""
    p0, p1 = Vector(p0), Vector(p1)
    d = p1 - p0
    e = Vector((0, 0, 1)).rotation_difference(d.normalized()).to_euler()
    return timber(name, (sec, sec, d.length), (p0 + p1) / 2, kind=kind, rot=[math.degrees(a) for a in e], jitter=0.004, bevel=0.012)

# ---------- the frame ----------
def build_frame():
    j = lambda a: rng.uniform(-a, a)
    W = 2 * XIN + 2 * PS_X
    for sx in (-1, 1):
        timber("post", (PS_X, PS_Y, Z_TOP - Z_SILL + 0.02), (sx * PX, YW, (Z_TOP + Z_SILL) / 2 + 0.01), rot=(j(0.2), j(0.2), 0), jitter=0.006, bevel=0.018)
    # sill and header: through the posts
    timber("sill", (W + 0.04, 0.30, Z_SILL), (0, YW - 0.05, Z_SILL / 2), rot=(0, 0, j(0.15)), jitter=0.004, bevel=0.012)
    timber("header", (W, 0.30, 0.10), (0, YW - 0.05, Z_TOP + 0.05), rot=(0, 0, j(0.12)), jitter=0.004, bevel=0.014)
    timber("cap", (W + 0.10, 0.40, 0.04), (0, YW - 0.08, H - 0.02), rot=(0, 0, j(0.1)), jitter=0.003, bevel=0.008)
    # back wall: vertical hewn planks between the posts, 60 mm
    n = max(2, round(2 * XIN / 0.25)); pw = (2 * XIN + 0.04) / n
    for i in range(n):
        x = -XIN - 0.02 + (i + 0.5) * pw
        plank("wall", (pw + 0.004, WALL_T, Z_TOP - Z_SILL + 0.04), (x, YW + j(0.002), (Z_TOP + Z_SILL) / 2), rot=(j(0.25), 0, 0), jitter=0.002)
    # back rails, a diagonal back strut per post, and the sled runners
    for z in (0.55, 1.75):
        timber("rail", (2 * XIN + 0.04, 0.06, 0.12), (0, YW + WALL_T / 2 + 0.03, z), jitter=0.003, bevel=0.012)
    for sx in (-1, 1):
        timber("runner", (0.14, 1.0, 0.10), (sx * (PX + 0.01), 0.0, 0.05), rot=(0, 0, j(0.2)), jitter=0.004, bevel=0.016)
        strut("strut", (sx * (PX + 0.01), YW + PS_Y / 2 - 0.02, 1.55), (sx * (PX + 0.01), 0.40, 0.09), 0.10)
        strut("strut", (sx * (PX + 0.01), YW - PS_Y / 2 + 0.02, 1.35), (sx * (PX + 0.01), -0.38, 0.09), 0.09)     # a shorter toe in front
    # plaques: one board per trophy, two vertical iron bands, a rivet on each
    for r in range(NROW):
        for c in range(NCOL):
            x, z = col_x(c), row_z(r)
            plank("board", (BOARD_W, BOARD_T, BOARD_H), (x + j(0.002), YF + BOARD_T / 2, z + j(0.002)), rot=(0, 0, j(0.35)), jitter=0.0025, bevel=0.007)
            for dx in (-0.14, 0.14):
                iron("band", (0.02, 0.008, BOARD_H + 0.012), (x + dx, YF - 0.004, z))
                rivet((x + dx, YF - 0.008, z + 0.07), size=0.014, depth=0.005)
    # iron at the posts and under the header
    for sx in (-1, 1):
        yfp = YW - PS_Y / 2
        iron("bracket", (0.12, 0.016, 0.26), (sx * PX, yfp - 0.008, Z_TOP - 0.13))
        iron("bracket", (0.22, 0.016, 0.07), (sx * (PX - 0.06), YW - 0.20 - 0.008, Z_TOP + 0.05))
        for dz in (-0.07, -0.19): rivet((sx * PX, yfp - 0.016, Z_TOP + dz), size=0.026, depth=0.010)
        iron("strap", (PS_X + 0.04, 0.016, 0.12), (sx * PX, yfp - 0.008, 0.38))
        for dx in (-0.045, 0.045): rivet((sx * PX + dx, yfp - 0.016, 0.38), size=0.026, depth=0.010)

# ---------- scene ----------
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
ATLAS = build_atlas()
MAT = bpy.data.materials.new("trophyhall"); MAT.use_nodes = True
nt = MAT.node_tree; bsdf = nt.nodes["Principled BSDF"]
ti = nt.nodes.new("ShaderNodeTexImage"); ti.image = ATLAS; ti.interpolation = "Closest"
nt.links.new(ti.outputs["Color"], bsdf.inputs["Base Color"])
bsdf.inputs["Roughness"].default_value = 0.8
def tris(obs): return sum(len(p.vertices) - 2 for o in obs for p in o.data.polygons)
t0 = time.time()

def obj_export(obs, path):
    bpy.ops.object.select_all(action="DESELECT")
    for o in obs: o.select_set(True)
    bpy.context.view_layer.objects.active = obs[0]
    bpy.ops.wm.obj_export(filepath=path, export_selected_objects=True, export_materials=False, export_triangulated_mesh=True,
                          forward_axis="NEGATIVE_Z", up_axis="Y")

rng.seed(11); build_frame()
FRAME_PARTS = list(PARTS)
FRAME_TRIS = tris(FRAME_PARTS)
print("TROPHY frame tris", FRAME_TRIS, "parts", len(FRAME_PARTS), flush=True)
# bounds of the whole frame and of the footprint
allv = np.array([[*o.data.vertices[i].co] for o in FRAME_PARTS for i in range(len(o.data.vertices))])
FLO, FHI = allv.min(0), allv.max(0)
print("TROPHY frame bounds x %.3f..%.3f y %.3f..%.3f z %.3f..%.3f  size %.3f x %.3f x %.3f" % (FLO[0], FHI[0], FLO[1], FHI[1], FLO[2], FHI[2], *(FHI - FLO)), flush=True)
# frame BVH (world space) for the clip checks
fv, fp = [], []
for o in FRAME_PARTS:
    base = len(fv); fv += [v.co.copy() for v in o.data.vertices]; fp += [tuple(base + i for i in p.vertices) for p in o.data.polygons]
FRAME_BVH = BVHTree.FromPolygons(fv, fp)
if EXPORT:
    for o in FRAME_PARTS: o.select_set(False)
    bpy.ops.object.select_all(action="DESELECT")
    for o in FRAME_PARTS: o.select_set(True)
    bpy.context.view_layer.objects.active = FRAME_PARTS[0]
    bpy.ops.object.join(); jo = bpy.context.active_object; jo.name = "TrophyHall"
    obj_export([jo], os.path.join(OUTA, "TrophyHall.obj"))
    FRAME_TRIS = tris([jo])
    bpy.data.objects.remove(jo)
    FRAME_OBJS = []
else:
    for o in FRAME_PARTS: bpy.data.objects.remove(o)
    FRAME_OBJS = []
print("TROPHY frame exported tris", FRAME_TRIS, flush=True)

# ---------- the trophies (the game's own models; render and checks only, never exported) ----------
names = sorted(n for n in os.listdir(TROPHY_DIR) if os.path.exists(os.path.join(TROPHY_DIR, n, "info.json")))
if QUICK: names = [n for n in names if n in ("TrophyGhost", "TrophyNeck", "TrophyBoar", "TrophyFader", "TrophyBonemass", "TrophyGoblinKing", "TrophyEikthyr", "TrophySurtling")]
TR = {}
for nm in names:
    info = json.load(open(os.path.join(TROPHY_DIR, nm, "info.json")))
    objs = [o for o in LI.load_item(nm, anchor="origin") if o.type == "MESH"]
    o = objs[0]
    V = np.array([v.co[:] for v in o.data.vertices], dtype=np.float64)
    F = [tuple(p.vertices) for p in o.data.polygons]
    bmin, bmax = np.array(info["bounds_min"]), np.array(info["bounds_max"])
    TR[nm] = dict(obj=o, mesh=o.data, V=V, F=F, bmin=bmin, bmax=bmax, size=bmax - bmin, tris=info["triangles"], root=1.0)
    for x in objs[1:]: bpy.data.objects.remove(x, do_unlink=True)
    o.hide_render = True; o.hide_viewport = True
print("TROPHY loaded %d models" % len(TR), flush=True)

def trophy_scale(size):
    """Storehouse.Place with display = true and a fit box: size = the item's bounds in Blender axes (x width, y DEPTH, z height)"""
    sx, sy, sz = size
    s_fit = min(BOX[0] / sx, BOX[1] / sz, BOX[2] / sy)          # box x = width, y = height, z = depth
    return min(DISPLAY * 1.0, s_fit * TOL)

def placement(nm, c, r):
    """matrix (4x4 numpy, item root space -> world) of trophy nm on board (column c, row r)"""
    t = TR[nm]; s = trophy_scale(t["size"])
    cen = (t["bmin"] + t["bmax"]) / 2
    back_y = YF - HANG_CLEAR                                     # the least-z (Unity) = greatest-y (Blender) face of the bounds
    pos = np.array([col_x(c) - s * cen[0], back_y - s * t["bmax"][1], row_z(r) - s * cen[2]])
    M = np.eye(4); M[:3, :3] *= s; M[:3, 3] = pos
    return M, s

def world_vertices(nm, M):
    V = TR[nm]["V"]
    return (V @ M[:3, :3].T + M[:3, 3])

# ---------- checks ----------
CHECK = {}
def bvh_world(nm, M):
    W = world_vertices(nm, M)
    return BVHTree.FromPolygons([Vector(v) for v in W], TR[nm]["F"]), W

cells = [(0, 0), (NCOL - 1, 0), (0, NROW - 1), (NCOL - 1, NROW - 1), (NCOL // 2, NROW // 2)]    # the four corners (posts, header, sill) and the middle
worst = 0; clip_pairs = 0
for nm in names:
    t = TR[nm]; s = trophy_scale(t["size"])
    shown = t["size"] * np.array([1, 1, 1]) * s
    pairs = 0; out_cell = 0.0
    for (c, r) in cells:
        M, _ = placement(nm, c, r)
        bvh, W = bvh_world(nm, M)
        pairs += len(bvh.overlap(FRAME_BVH))
        lo, hi = W.min(0), W.max(0)
        # inside the cell (pitch minus 12 mm) in x and z, behind the front of the depth box and not behind its back plane
        out_cell = max(out_cell, (col_x(c) - PITCH_X / 2 + 0.006) - lo[0], hi[0] - (col_x(c) + PITCH_X / 2 - 0.006),
                       (row_z(r) - PITCH_Y / 2 + 0.006) - lo[2], hi[2] - (row_z(r) + PITCH_Y / 2 - 0.006),
                       hi[1] - (YF - HANG_CLEAR) - 1e-6, (YF - HANG_CLEAR - BOX[2] * TOL) - lo[1])
    CHECK[nm] = dict(scale=round(float(s), 4), shown_w=round(float(shown[0]), 3), shown_h=round(float(shown[2]), 3), shown_d=round(float(shown[1]), 3),
                     true_size=[round(float(x), 3) for x in t["size"]], tris=t["tris"], clip_pairs=pairs, outside_cell_mm=round(out_cell * 1000, 2))
    clip_pairs += pairs; worst = max(worst, out_cell)
print("TROPHY CHECK kinds %d  frame clipping pairs (5 boards each) %d  worst overshoot of a cell %.2f mm" % (len(names), clip_pairs, worst * 1000), flush=True)
by_big = sorted(names, key=lambda n: -float(TR[n]["size"].max())); by_small = sorted(names, key=lambda n: float(TR[n]["size"].max()))
for nm in by_big[:4] + by_small[:4]:
    c = CHECK[nm]; print("  %-24s true %s -> shown %.3f x %.3f x %.3f (scale %.3f)  clip pairs %d" % (nm, c["true_size"], c["shown_w"], c["shown_h"], c["shown_d"], c["scale"], c["clip_pairs"]), flush=True)
tris_all = sum(TR[n]["tris"] for n in names)
heaviest = sorted(names, key=lambda n: -TR[n]["tris"])
print("TROPHY tris: frame %d, all %d kinds once %d, full store %d; heaviest %s" % (FRAME_TRIS, len(names), tris_all, FRAME_TRIS + tris_all, [(n, TR[n]["tris"]) for n in heaviest[:4]]), flush=True)

# ---------- demo order: bosses first (the top row), then by biome, then by name ----------
BIOME_ORDER = ["Meadows", "Black Forest", "Swamp", "Mountain", "Plains", "Mistlands", "Ashlands", "Deep North", "Ocean"]
def biome_rank(nm):
    b = BIOMES.get(nm, "")
    for i, k in enumerate(BIOME_ORDER):
        if b.startswith(k): return i
    return 5.5
BIOMES = {}
try:
    for line in open(os.path.join(REPO, "ITEMS.md"), encoding="utf-8"):
        m = re.match(r"\| `(Trophy\w+)` \| [^|]+\| Trophy \| ([^|]+)\|", line)
        if m: BIOMES[m.group(1)] = m.group(2).strip()
except Exception as e:
    print("no ITEMS.md biome column", e)
def is_boss(nm): return "(boss)" in BIOMES.get(nm, "")
ORDER = sorted(names, key=lambda n: (0 if is_boss(n) else 1, biome_rank(n), n))
REPEAT = [n for n in ("TrophyBoar", "TrophyDeer", "TrophyNeck", "TrophyWolf", "TrophyGreydwarf", "TrophyDraugr", "TrophyGoblin", "TrophySkeleton", "TrophyGhost", "TrophyHare") if n in TR]
DEMO = ORDER + [REPEAT[i % len(REPEAT)] for i in range(max(0, NUNITS - len(ORDER)))]
DEMO = DEMO[:NUNITS]
print("TROPHY demo order:", DEMO[:12], "...", flush=True)

# ---------- anchors ----------
def ub(p): return [round(-p[0], 4), round(p[2], 4), round(-p[1], 4)]           # Blender -> Unity prefab space
units = []
for r in range(NROW):
    for c in range(NCOL):
        i = r * NCOL + c
        demo = DEMO[i] if i < len(DEMO) else None
        u = dict(index=i, kind="board", place="board", grid_row=r, grid_col=c, row="board",
                 position=ub((col_x(c), YF, row_z(r))), rotation=[0.0, 0.0, 0.0],
                 box_size=[round(BOX[0], 4), round(BOX[1], 4), round(BOX[2], 4)],
                 example_item=demo,
                 example_scale=CHECK[demo]["scale"] if demo in CHECK else None,
                 copies=[dict(layer=0, row=0, col=0, offset=[0.0, 0.0, HANG_CLEAR], rotation=[0.0, 0.0, 0.0],
                              fit_box=[round(BOX[0], 4), round(BOX[1], 4), round(BOX[2], 4)], anchor="back")])
        if u["example_item"] is None: del u["example_item"]; del u["example_scale"]
        units.append(u)
# round trip of the Unity <-> Blender mapping on a unit (position)
rt = max(abs(np.array(ub((col_x(c), YF, row_z(r)))) - np.array([-col_x(c), row_z(r), -YF])).max() for r in range(NROW) for c in range(NCOL))
doc = {
    "schema": "storehouse-anchors/1",
    "furniture": "Trophy Hall" if NCOL == 10 else "Trophy Hall (half)",
    "units": NUNITS, "slots_designed_for": NUNITS, "stack_per_unit": True,
    "grid": {"columns": NCOL, "rows": NROW, "doc": "container width x height = %d x %d: the wall itself. index = row * %d + column, row 0 the top row, column 0 the left as seen from the front." % (NCOL, NROW, NCOL)},
    "space": {"unity": "prefab space, origin on the floor at the centre of the footprint (the runners), +z front, +y up, +x to the furniture's left when seen from the front",
              "from_blender": "ux=-bx, uy=bz, uz=-by"},
    "frame": {"obj": "TrophyHall.obj", "atlas": "trophyhall_atlas.png",
              "size_m": [round(float(FHI[0] - FLO[0]), 3), round(float(FHI[1] - FLO[1]), 3), round(float(FHI[2] - FLO[2]), 3)],
              "size_doc": "width (x) x depth of the frame incl. the 1.0 m runners and the header cap (y) x height (z). Trophies add up to 0.34 m in front of the board face (YF)."},
    "fill_order": "grid order, mirroring the %d x %d container grid: index = grid_row * %d + grid_col; rows top to bottom, each row left to right seen from the front. Every row has its own height, so rows of %d by position.y descending, each by position.x descending, give the same order." % (NCOL, NROW, NCOL, NCOL),
    "position": "unit position = the hang point: the centre of the board's FRONT face. box_size = the fit box [x width, y height, z depth] in Unity axes.",
    "copy_rule": ("One copy per unit. The stored trophy is scaled uniformly to s = min(DisplaySize x RootScale, 1.15 x min(box.x / size.x, box.y / size.y, box.z / size.z)) (Storehouse.Place, display = true, fit_box), "
                  "centred in x and y on the hang point, and (anchor 'back') hung so that the back plane of its bounds (least z) is offset.z = %.3f m in front of the board face. Rotation 0: the item's front looks out of the wall." % HANG_CLEAR),
    "placement": {
        "anchor_back": "NEW. 'anchor': 'back' = the item's bounds hang on the unit's plane instead of standing on it. In Storehouse.cs: StoreCopy gets 'public bool Back;'; Copy(): "
                       "'if (S(cd, \"anchor\") is { } anchor) { c.Bottom = anchor.StartsWith(\"bottom\", StringComparison.Ordinal); c.Back = anchor.StartsWith(\"back\", StringComparison.Ordinal); }'; "
                       "Place(): after 'if (c.Bottom) centre.y += s * d.y * 0.5f;' add 'if (c.Back) centre.z += s * d.z * 0.5f;'. Nothing else changes (offset.z then adds the 18 mm clearance).",
        "without_it": "Without the change the trophy is centred on the hang point, half its depth inside the board (up to 0.16 m): the file still loads, it just looks sunk.",
        "kind": "board (every unit): display store, mirror = true, container %d x %d, one trophy per stack; the stack count does not matter (one model per stack)." % (NCOL, NROW),
        "demo": "example_item / example_scale per unit = the trophy in the full render (bosses first, then by biome)."},
    "box": {"fit_box_xyz_m": [round(BOX[0], 4), round(BOX[1], 4), round(BOX[2], 4)], "max_shown_xyz_m": [round(BOX[0] * TOL, 4), round(BOX[1] * TOL, 4), round(BOX[2] * TOL, 4)],
            "cell_pitch_xy_m": [PITCH_X, PITCH_Y], "back_clearance_m": HANG_CLEAR, "display_size": DISPLAY, "tolerance": TOL},
    "note": ("r1 (Joost, 24 Oct): the Trophy Hall, 80 boards (10 x 8) for ItemType.Trophy. Every board is the same size; the trophy is fitted to it per its own bounds (a Fader head shrinks, a Surtling shows at 0.7). "
             "The half (2 m, 40 boards) is the same script with --cols 5. Heaviest models: %s." % ", ".join("%s %d" % (n, TR[n]["tris"]) for n in heaviest[:3])),
    "checks": {"kinds_checked": len(names), "boards_per_kind": len(cells), "frame_clip_pairs": clip_pairs, "worst_cell_overshoot_mm": round(worst * 1000, 2),
               "doc": "every ripped trophy, placed by the rule above on the four corner boards and the middle one, against the whole frame (BVH overlap of the real triangles): clip_pairs 0; its bounds stay inside its cell"},
    "tris": {"frame": FRAME_TRIS, "all_kinds_once": tris_all, "full_store_all_kinds_once": FRAME_TRIS + tris_all,
             "heaviest": {n: TR[n]["tris"] for n in heaviest[:5]},
             "worst_case_80_of_the_heaviest": FRAME_TRIS + NUNITS * TR[heaviest[0]]["tris"]},
    "kinds": CHECK,
    "kinds_missing": {"TrophyForestTroll": "no mesh in the game bundle (null MeshFilter mesh); the mod measures the real prefab at run time, the fit rule is the same"},
    "units_data": units,
}
if EXPORT:
    out = os.path.join(OUTA, "trophyhall_anchors.json"); tmp = out + ".tmp"
    with open(tmp, "w") as fh: json.dump(doc, fh, indent=1)
    os.replace(tmp, out)
    print("TROPHY wrote", out, flush=True)
print("TROPHY STATS frame %d tris, %d units, full(all kinds once) %d, roundtrip %.2g" % (FRAME_TRIS, NUNITS, FRAME_TRIS + tris_all, rt), flush=True)

# ---------- renders ----------
if RENDER:
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
    sc.view_settings.view_transform = "Standard"
    def look(yaw, pitch, dist, tgt):
        t = Vector(tgt)
        d = Vector((math.cos(math.radians(pitch)) * math.sin(math.radians(yaw)),
                    -math.cos(math.radians(pitch)) * math.cos(math.radians(yaw)), math.sin(math.radians(pitch))))
        cam.location = t + d * dist; cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    def render(fn, rx=1600, ry=1000):
        sc.render.resolution_x, sc.render.resolution_y = rx, ry
        sc.render.filepath = os.path.join(OUT, fn); bpy.ops.render.render(write_still=True); return sc.render.filepath
    def import_obj(path):
        before = set(bpy.data.objects)
        bpy.ops.wm.obj_import(filepath=path, forward_axis="NEGATIVE_Z", up_axis="Y")
        return [o for o in bpy.data.objects if o not in before]
    shown = []
    def put_frame(off=(0, 0, 0)):
        obs = import_obj(os.path.join(OUTA, "TrophyHall.obj")) if EXPORT else []
        for o in obs:
            o.data.materials.clear(); o.data.materials.append(MAT); o.location = off; shown.append(o)
    def put_trophy(nm, c, r, off=(0, 0, 0)):
        M, _ = placement(nm, c, r)
        io = bpy.data.objects.new(nm, TR[nm]["mesh"]); sc.collection.objects.link(io)
        Mo = np.array(M); Mo[:3, 3] += np.array(off)
        io.matrix_world = Matrix(Mo.tolist()); shown.append(io)
    def fill(assign, off=(0, 0, 0)):
        for i, nm in enumerate(assign):
            if nm is None or nm not in TR: continue
            put_trophy(nm, i % NCOL, i // NCOL, off)
    def clear():
        for o in shown: bpy.data.objects.remove(o)
        shown.clear()
    def shipped(folder, obj, atlas, loc):
        obs = import_obj(os.path.join(folder, obj))
        mt = bpy.data.materials.new(obj); mt.use_nodes = True
        tt = mt.node_tree.nodes.new("ShaderNodeTexImage"); tt.image = bpy.data.images.load(os.path.join(folder, atlas)); tt.interpolation = "Closest"
        mt.node_tree.links.new(tt.outputs["Color"], mt.node_tree.nodes["Principled BSDF"].inputs["Base Color"])
        mt.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.8
        for o in obs: o.data.materials.clear(); o.data.materials.append(mt); o.location = loc
        return obs
    ALL = list(DEMO)
    HALF = list(DEMO[:NUNITS // 2]) + [None] * (NUNITS - NUNITS // 2)
    # the wall alone: 3/4, front, back, side
    BX = 0.0
    TGT = (0, -0.2, 1.2)
    put_frame(); fill(ALL)
    look(-22, 8, 7.2 if NCOL == 10 else 4.6, TGT); render("trophyhall-full-34.png")
    look(0, 3, 7.4 if NCOL == 10 else 4.8, TGT); render("trophyhall-full-front.png", 2000, 1000)
    look(-70, 8, 6.0 if NCOL == 10 else 4.0, (0, -0.2, 1.1)); render("trophyhall-full-side.png")
    look(158, 12, 8.5 if NCOL == 10 else 5.4, (0, 0.0, 1.2)); render("trophyhall-full-back.png")
    # close-ups: the top row (bosses), the bottom row, a middle block with the biggest and the smallest
    look(-10, 5, 3.2, (col_x(2), YF - 0.2, row_z(0))); render("trophyhall-closeup-top-left.png")
    look(-10, 5, 3.2, (col_x(NCOL - 3), YF - 0.2, row_z(NROW - 1))); render("trophyhall-closeup-bottom-right.png")
    look(-30, 6, 3.4, (col_x(NCOL // 2), YF - 0.2, row_z(3))); render("trophyhall-closeup-middle.png")
    clear()
    # a person for scale: the 1.8 m post of the other stores' renders
    put_frame(); fill(ALL)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0.8, -1.0, 0.9)); post = bpy.context.active_object; post.scale = (0.1, 0.1, 1.8)
    pm = bpy.data.materials.new("post"); pm.use_nodes = True
    pm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.85, 0.85, 0.88, 1); post.data.materials.append(pm)
    look(-18, 5, 6.5 if NCOL == 10 else 4.4, TGT); render("trophyhall-post-1.8m.png")
    bpy.data.objects.remove(post); clear()
    # beside bunker_r4 (as shipped), same scale, same ground
    BUNKER_AT = (FHI[0] + 2.4, -0.12, 0)
    for nm, asg in (("full", ALL), ("half", HALF), ("empty", [])):
        shipped(BUNKER, "Bunker.obj", "bunker_atlas.png", BUNKER_AT)
        put_frame(); fill(asg)
        look(-24, 6, 14.5 if NCOL == 10 else 11.0, (BUNKER_AT[0] / 2, -0.4, 1.1)); render("trophyhall-%s-beside-bunker_r4.png" % nm, 2400, 1000)
        look(-4, 3, 14.0 if NCOL == 10 else 10.5, (BUNKER_AT[0] / 2, -0.4, 1.1)); render("trophyhall-%s-beside-bunker_r4-front.png" % nm, 2400, 1000)
        clear()
        for o in [o for o in bpy.data.objects if o.name.startswith("Bunker")]: bpy.data.objects.remove(o)
    put_frame(); look(-30, 8, 7.2 if NCOL == 10 else 4.6, TGT); render("trophyhall-empty-34.png"); look(158, 12, 8.5 if NCOL == 10 else 5.4, (0, 0.0, 1.2)); render("trophyhall-empty-back.png"); clear()
print("DONE %.0fs" % (time.time() - t0))
