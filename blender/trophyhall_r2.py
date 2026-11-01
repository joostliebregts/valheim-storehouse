"""Trophy Hall round 2 (ITEMS.md section 2, #1): r1's wall (frame, 80 boards 10 x 8, display store, fit 0.316 x 0.227 x 0.28) with every trophy MOUNTED right.
Joost (24 Oct): "some trophies look upward instead of forward, many of the heads; tune them so they face more down/forward."
Cause (measured on the ripped models, C:/Users/joost/ValheimRip/trophies): the game's trophy models are authored lying face up (+y in the game's item space: the face looks at the
sky, the muzzle toward the front, the back of the head toward the back), so r1's rotation 0 hung most heads looking up. Fix: one mounting rotation per trophy KIND, because
the boards are generic (any trophy can land on any board) it cannot live in a board or copy: it is a table in the anchors file, "item_rotation": {prefab: [x, y, z]},
Unity euler degrees (Quaternion.Euler: z, then x, then y), applied to the ITEM before the copy's own rotation. 0 = the model as ripped. For a head the table's x turns the face
from straight up to 'out of the wall and ~15 degrees down' (x about 105 for a face that looks straight up; less for a head whose face already looks forward in its model;
a long muzzle (deer, wolf) is set by its muzzle, not by the face plane). Things with no face (skeleton limbs, crystal, broom, slabs, mosquito, wing) are hung upright/flat
(x 90) or as ripped. Every value was picked by eye from side views of the real mesh at 15 degree steps against a 15-degree-down guide, then checked in front, side and 3/4 renders.
Axes: the ripped model is Blender (x right, y depth with the face at -y, z up); the mod's item space is ux = -bx, uy = bz, uz = -by. A turn about Blender x by t is exactly Unity euler (t, 0, 0).

The mod applies it in StoreModel.Place (see "placement.item_rotation" in the anchors file, 6 lines): item turn first, then Aligned, then the copy's rotation; the fit box and the
'back' anchor use the box of the TURNED item (Turned(align, size), the mod's own rule, which is the turned bounding box, so the mesh sits at or just in front of the plane, never behind).
This script simulates exactly that rule for the renders and the clip checks (the mesh itself is rotated, the plane/scale come from the rotated box).

Everything below is r1's text, still true except where it says rotation 0:
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
Frame change vs r1 (z-fighting check, report_coplanar as in fletcher_r2.py): the board rivets are 10 mm instead of 14 mm so their side faces no longer lie within 2 mm of the 20 mm band's (r1: 8 same-facing
overlapping pairs, r2: 0; the rest of the frame is r1's, same seed).
Atlas: bunker_r4's, byte-identical (hewn timber, end grain, dark iron); no new colour.
Run: "C:/Program Files/Blender Foundation/Blender 4.5/blender.exe" -b -P trophyhall_r2.py -- [--out DIR] [--assets DIR] [--no-render] [--no-export] [--cols N] [--quick]
Files (assets/trophyhall_r2/): TrophyHall.obj (frame only), trophyhall_atlas.png, trophyhall_anchors.json (last, temp + rename), rip_trophies.py (not a Blender script).
Unity prefab space: ux = -bx, uy = bz, uz = -by (OBJ exported forward -Z, up Y, like every store).
"""
import bpy, bmesh, sys, os, math, json, random, time, re, shutil
import numpy as np
from mathutils import Vector, Matrix, Euler
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, ".."))
OUTA = os.path.join(REPO, "assets", "trophyhall_r2")
BUNKER = os.path.join(REPO, "assets", "bunker_r4")
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
def arg(k, d=None): return argv[argv.index(k) + 1] if k in argv else d
OUT = arg("--out", "C:/Users/joost/AppData/Local/Temp/claude/C--Users-joost--pai/5e4bc60b-cdfe-4638-8e29-2e507fa13cf9/scratchpad/trophyhall_r2")
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
                rivet((x + dx, YF - 0.008, z + 0.07), size=0.010, depth=0.005)      # 10 mm: its sides stay clear of the 20 mm band's (r1: 14 mm, 8 same-facing pairs within 2 mm of the band)
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

# ---------- coplanar check (round 2): faces that face the same way, lie in one plane and overlap z-fight in the game ----------
def _clip_area(subj, clipper):
    """Area of the intersection of two convex 2D polygons (Sutherland-Hodgman); both counter-clockwise or both clockwise."""
    def orient(poly): return sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1] for i in range(len(poly)))
    sg = 1.0 if orient(clipper) >= 0 else -1.0
    out = list(subj)
    for i in range(len(clipper)):
        a, b = clipper[i], clipper[(i + 1) % len(clipper)]
        inp, out = out, []
        if not inp: break
        def side(p): return sg * ((b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0]))
        for k in range(len(inp)):
            p, q = inp[k], inp[(k + 1) % len(inp)]
            sp, sq = side(p), side(q)
            if sp >= 0: out.append(p)
            if (sp >= 0) != (sq >= 0):
                t = sp / (sp - sq); out.append((p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])))
    return abs(orient(out)) / 2 if len(out) >= 3 else 0.0

def coplanar_overlaps(parts, tol=0.002, min_area=2e-7, facing=1):
    """parts: [(name, mesh)] in world space. Every pair of triangles that (facing=1) face the same way or (facing=-1) face
    each other, whose planes are within tol (m) of each other and whose projections overlap by more than min_area (m2).
    Returns [(area, name_a, name_b, centre, normal, gap)] sorted by area, largest first."""
    P, Tn, own = [], [], []
    for nm, me in parts:
        V = np.array([tuple(v.co) for v in me.vertices], float)
        for pl in me.polygons:
            vs = list(pl.vertices)
            for i in range(1, len(vs) - 1): P.append(V[[vs[0], vs[i], vs[i + 1]]]); own.append(nm)
    P = np.array(P)
    N = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0]); A = np.linalg.norm(N, axis=1) / 2
    ok = A > 1e-9
    N = N / np.where(ok, 2 * A, 1)[:, None]
    res = []
    for i in np.nonzero(ok)[0]:
        j = np.arange(i + 1, len(P))
        j = j[ok[j]]
        j = j[(N[j] @ N[i]) * facing > 0.9995]
        if not len(j): continue
        dist = np.einsum("jkc,c->jk", P[j] - P[i][0], N[i])
        near = (np.abs(dist).max(1) <= tol) if facing > 0 else (np.abs(dist).max(1) <= tol)
        for jj in j[near]:
            n = N[i]; ax = int(np.argmax(np.abs(n))); keep = [a for a in range(3) if a != ax]
            a2 = [tuple(q[keep]) for q in P[i]]; b2 = [tuple(q[keep]) for q in P[jj]]
            ar = _clip_area(a2, b2)
            if ar > min_area:
                gap = float(np.mean(np.einsum("kc,c->k", P[jj] - P[i][0], n)))
                res.append((ar, own[i], own[jj], ((P[i].mean(0) + P[jj].mean(0)) / 2).round(3).tolist(), n.round(2).tolist(), round(gap, 4)))
    res.sort(key=lambda r: -r[0])
    return res

def report_coplanar(parts, label):
    same = coplanar_overlaps(parts, facing=1)
    back = coplanar_overlaps(parts, facing=-1)
    print(f"COPLANAR {label}: same-facing overlapping pairs {len(same)} (0 expected); back-to-back pairs {len(back)} (hidden, informational)", flush=True)
    import re, collections
    agg = collections.OrderedDict()
    for r in same:
        key = (re.sub(r"\.\d+$", "", r[1]), re.sub(r"\.\d+$", "", r[2]), tuple(int(round(a)) for a in r[4]), round(r[5] * 1000, 1))
        e = agg.setdefault(key, [0, 0.0, r[3]]); e[0] += 1; e[1] += r[0]
    for key, (n, ar, c) in sorted(agg.items(), key=lambda kv: -kv[1][1]):
        print("  SAME", key[0], "x", key[1], "normal", key[2], "gap_mm", key[3], "pairs", n, f"area {ar * 1e4:.1f}cm2", "e.g. at", c, flush=True)
    agg = collections.OrderedDict()
    for r in back:
        key = (re.sub(r"\.\d+$", "", r[1]), re.sub(r"\.\d+$", "", r[2]), tuple(abs(int(round(a))) for a in r[4]))
        e = agg.setdefault(key, [0, 0.0, r[3]]); e[0] += 1; e[1] += r[0]
    for key, (n, ar, c) in sorted(agg.items(), key=lambda kv: -kv[1][1]):
        print("  BACK", key[0], "x", key[1], "axis", key[2], "pairs", n, f"area {ar * 1e4:.1f}cm2", "e.g. at", c, flush=True)
    return {"same_facing_overlaps": len(same), "back_to_back": len(back), "tolerance_mm": 2.0, "min_area_cm2": 0.002}

rng.seed(11); build_frame()
FRAME_PARTS = list(PARTS)
COP = report_coplanar([(o.name, o.data) for o in FRAME_PARTS], "frame")
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


# ---------- the mounting rotation per trophy kind (Unity euler degrees [x, y, z]; the item turned about its bounds centre, before everything else) ----------
# Picked from side views at 15-degree steps: the face (or the muzzle of a long snout) ends up pointing out of the wall and ~15 degrees down.
ITEM_ROT = {
    "TrophyAbomination": [90, 0, 0], "TrophyAsksvin": [50, 0, 0], "TrophyBarka": [60, 0, 0], "TrophyBjorn": [60, 0, 0], "TrophyBjornUndead": [15, 0, 0],
    "TrophyBlob": [100, 0, 0], "TrophyBlob_Frost": [90, 0, 0], "TrophyBlob_Lava": [90, 0, 0], "TrophyBlob_Morkhalla": [90, 0, 0], "TrophyBoar": [70, 0, 0],
    "TrophyBonemass": [90, 0, 0], "TrophyBonemawSerpent": [100, 0, 0], "TrophyCharredArcher": [90, 0, 0], "TrophyCharredMage": [90, 0, 0], "TrophyCharredMelee": [100, 0, 0],
    "TrophyCultist": [95, 0, 0], "TrophyCultist_Hildir": [95, 0, 0], "TrophyDeathsquito": [100, 0, 0], "TrophyDeer": [62, 0, 0], "TrophyDeerWhite": [62, 0, 0],
    "TrophyDragonQueen": [90, 0, 0], "TrophyDraugr": [95, 0, 0], "TrophyDraugrElite": [95, 0, 0], "TrophyDraugrFem": [95, 0, 0], "TrophyDvergr": [90, 0, 0],
    "TrophyEikthyr": [70, 0, 0], "TrophyElaking": [20, 0, 0], "TrophyFader": [40, 0, 0], "TrophyFallenValkyrie": [30, 0, 0], "TrophyFenring": [90, 0, 0],
    "TrophyForestTroll": [20, 0, 0], "TrophyFrostTroll": [20, 0, 0], "TrophyGhost": [75, 0, 0], "TrophyGjall": [90, 0, 0], "TrophyGoblin": [90, 0, 0],
    "TrophyGoblinBrute": [40, 0, 0], "TrophyGoblinBruteBrosBrute": [40, 0, 0], "TrophyGoblinBruteBrosShaman": [55, 0, 0], "TrophyGoblinKing": [35, 0, 0], "TrophyGoblinShaman": [90, 0, 0],
    "TrophyGreydwarf": [60, 0, 0], "TrophyGreydwarfBrute": [60, 0, 0], "TrophyGreydwarfShaman": [60, 0, 0], "TrophyGrowth": [90, 0, 0], "TrophyHare": [30, 0, 0],
    "TrophyHatchling": [15, 0, 0], "TrophyJotunWarrior": [20, 0, 0], "TrophyJotunWitch": [30, 0, 0], "TrophyKvastur": [90, 0, 0], "TrophyLeech": [60, 0, 0],
    "TrophyLox": [80, 0, 0], "TrophyMole": [90, 0, 0], "TrophyMoose": [40, 0, 0], "TrophyMorgen": [75, 0, 0], "TrophyNeck": [40, 0, 0],
    "TrophySGolem": [0, 0, 0], "TrophySeal": [40, 0, 0], "TrophySeeker": [90, 0, 0], "TrophySeekerBrute": [45, 0, 0], "TrophySeekerQueen": [10, 0, 0],
    "TrophySerpent": [45, 0, 0], "TrophySkeleton": [70, 0, 0], "TrophySkeletonHildir": [70, 0, 0], "TrophySkeletonPoison": [70, 0, 0], "TrophySurtling": [75, 0, 0],
    "TrophyTheElder": [45, 0, 0], "TrophyTick": [90, 0, 0], "TrophyUlv": [90, 0, 0], "TrophyVolture": [45, 0, 0], "TrophyWolf": [85, 0, 0],
    "TrophyWraith": [90, 0, 0], "TrophyWrithan": [90, 0, 0],
}
if "--rot-file" in argv: ITEM_ROT.update(json.load(open(arg("--rot-file"))))
USE_ROT = "--r1-rotation" not in argv          # --r1-rotation: every trophy as ripped (the r1 look), for the 'before' renders
def unity_quat_matrix(e):
    """Quaternion.Euler(x, y, z) as a 3x3 (Unity order: z, then x, then y) in UNITY axes"""
    x, y, z = [math.radians(a) for a in e]
    cx, sx, cy, sy, cz, sz = math.cos(x), math.sin(x), math.cos(y), math.sin(y), math.cos(z), math.sin(z)
    Rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]]); Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]]); Rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return Ry @ Rx @ Rz
P_UB = np.array([[-1, 0, 0], [0, 0, 1], [0, -1, 0]], dtype=float)     # Blender -> Unity axes: ux = -bx, uy = bz, uz = -by
def item_turn(nm):
    """the item's turn as a matrix in BLENDER axes (conjugated from the Unity euler)"""
    if not USE_ROT or nm not in ITEM_ROT: return np.eye(3)
    return P_UB.T @ unity_quat_matrix(ITEM_ROT[nm]) @ P_UB

def turned_size(nm):
    """Storehouse.Place: d = Turned(align, size), the axis-aligned box around the turned bounds box (Blender axes: x width, y depth, z height)"""
    return np.abs(item_turn(nm)) @ TR[nm]["size"]

def trophy_scale(nm):
    """Storehouse.Place with display = true and a fit box, on the TURNED box"""
    sx, sy, sz = turned_size(nm)
    s_fit = min(BOX[0] / sx, BOX[1] / sz, BOX[2] / sy)          # box x = width, y = height, z = depth
    return min(DISPLAY * 1.0, s_fit * TOL)

def placement(nm, c, r):
    """matrix (4x4 numpy, item root space -> world) of trophy nm on board (column c, row r): the mod's rule, pos = centre - r * (s * bounds.center)"""
    t = TR[nm]; s = trophy_scale(nm); R = item_turn(nm)
    d = turned_size(nm)
    cen = (t["bmin"] + t["bmax"]) / 2
    centre = np.array([col_x(c), YF - HANG_CLEAR - s * d[1] / 2, row_z(r)])      # the turned box: its back plane (greatest y) HANG_CLEAR in front of the face, centred in x and z
    pos = centre - R @ (s * cen)
    M = np.eye(4); M[:3, :3] = s * R; M[:3, 3] = pos
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
    t = TR[nm]; s = trophy_scale(nm)
    shown = turned_size(nm) * s
    pairs = 0; out_cell = 0.0; gap = 0.0
    for (c, r) in cells:
        M, _ = placement(nm, c, r)
        bvh, W = bvh_world(nm, M)
        pairs += len(bvh.overlap(FRAME_BVH))
        lo, hi = W.min(0), W.max(0)
        gap = max(gap, (YF - HANG_CLEAR) - hi[1])      # how far the mesh's back-most point stands in front of the plane (the turned box is conservative)
        # inside the cell (pitch minus 12 mm) in x and z, behind the front of the depth box and not behind its back plane
        out_cell = max(out_cell, (col_x(c) - PITCH_X / 2 + 0.006) - lo[0], hi[0] - (col_x(c) + PITCH_X / 2 - 0.006),
                       (row_z(r) - PITCH_Y / 2 + 0.006) - lo[2], hi[2] - (row_z(r) + PITCH_Y / 2 - 0.006),
                       hi[1] - (YF - HANG_CLEAR) - 1e-6, (YF - HANG_CLEAR - BOX[2] * TOL) - lo[1])
    CHECK[nm] = dict(scale=round(float(s), 4), shown_w=round(float(shown[0]), 3), shown_h=round(float(shown[2]), 3), shown_d=round(float(shown[1]), 3),
                     true_size=[round(float(x), 3) for x in t["size"]], tris=t["tris"], clip_pairs=pairs, outside_cell_mm=round(out_cell * 1000, 2),
                     item_rotation=ITEM_ROT.get(nm) if USE_ROT else None, back_gap_mm=round(gap * 1000, 1))
    clip_pairs += pairs; worst = max(worst, out_cell)
print("TROPHY max back gap %.1f mm (%s)" % (max(CHECK[n]["back_gap_mm"] for n in names), max(names, key=lambda n: CHECK[n]["back_gap_mm"])), flush=True)
print("TROPHY CHECK kinds %d  frame clipping pairs (5 boards each) %d  worst overshoot of a cell %.2f mm" % (len(names), clip_pairs, worst * 1000), flush=True)
by_big = sorted(names, key=lambda n: -float(TR[n]["size"].max())); by_small = sorted(names, key=lambda n: float(TR[n]["size"].max()))
for nm in by_big[:4] + by_small[:4]:
    c = CHECK[nm]; print("  %-24s true %s -> shown %.3f x %.3f x %.3f (scale %.3f)  clip pairs %d  rot %s  back gap %.1f mm" % (nm, c["true_size"], c["shown_w"], c["shown_h"], c["shown_d"], c["scale"], c["clip_pairs"], c["item_rotation"], c["back_gap_mm"]), flush=True)
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
                  "centred in x and y on the hang point, and (anchor 'back') hung so that the back plane of its bounds (least z) is offset.z = %.3f m in front of the board face. Rotation 0 = the board's own; the trophy's mounting turn is item_rotation[prefab] (below), applied to the item first, and the fit and the back plane use the turned box." % HANG_CLEAR),
    "item_rotation": {k: v for k, v in sorted(ITEM_ROT.items())} if USE_ROT else {},
    "item_rotation_doc": "NEW in r2. Top-level, per trophy prefab name, Unity euler degrees (Quaternion.Euler) of the mounting turn: the item turned about its bounds centre BEFORE Aligned and the copy's rotation, so the face (or muzzle) looks out of the wall (+z) and ~15 degrees down. 0 = as ripped (the game's models lie face up, so most heads need x 15..105). A kind missing from the table is unturned.",
    "placement": {
        "anchor_back": "NEW. 'anchor': 'back' = the item's bounds hang on the unit's plane instead of standing on it. In Storehouse.cs: StoreCopy gets 'public bool Back;'; Copy(): "
                       "'if (S(cd, \"anchor\") is { } anchor) { c.Bottom = anchor.StartsWith(\"bottom\", StringComparison.Ordinal); c.Back = anchor.StartsWith(\"back\", StringComparison.Ordinal); }'; "
                       "Place(): after 'if (c.Bottom) centre.y += s * d.y * 0.5f;' add 'if (c.Back) centre.z += s * d.z * 0.5f;'. Nothing else changes (offset.z then adds the 18 mm clearance).",
        "without_it": "Without the change the trophy is centred on the hang point, half its depth inside the board (up to 0.16 m): the file still loads, it just looks sunk.",
        "kind": "board (every unit): display store, mirror = true, container %d x %d, one trophy per stack; the stack count does not matter (one model per stack)." % (NCOL, NROW),
        "demo": "example_item / example_scale per unit = the trophy in the full render (bosses first, then by biome).",
        "item_rotation": "NEW in r2, Storehouse.cs, 4 small edits. (1) StoreUnit: 'public Dictionary<string, Quaternion> ItemRot;'. (2) ItemVisual: 'public string PrefabName => prefabName;'. "
                         "(3) Anchors.Parse: before the unit loop 'var itemRot = ItemRotations(doc);', in the StoreUnit initializer 'ItemRot = itemRot,', and the helper "
                         "'static Dictionary<string, Quaternion> ItemRotations(Dictionary<string, object> doc) { if (Json.Obj(doc, \"item_rotation\") is not { } t) return null; var d = new Dictionary<string, Quaternion>(); foreach (var kv in t) if (V(t, kv.Key) is { } e) d[kv.Key] = Quaternion.Euler(e); return d; }'. "
                         "(4) StoreModel.Place: right after 'var align = Aligned(c, size);' add 'if (u.ItemRot != null && item.PrefabName != null && u.ItemRot.TryGetValue(item.PrefabName, out var turn)) align *= turn;'. "
                         "Nothing else: r = c.Rot * align and d = Turned(align, size) then include the item turn, so the fit box, the 'back' anchor and the turn about the bounds centre follow by themselves."},
    "box": {"fit_box_xyz_m": [round(BOX[0], 4), round(BOX[1], 4), round(BOX[2], 4)], "max_shown_xyz_m": [round(BOX[0] * TOL, 4), round(BOX[1] * TOL, 4), round(BOX[2] * TOL, 4)],
            "cell_pitch_xy_m": [PITCH_X, PITCH_Y], "back_clearance_m": HANG_CLEAR, "display_size": DISPLAY, "tolerance": TOL},
    "note": ("r2 (Joost, 24 Oct: heads looked upward): r1 plus item_rotation, a mounting turn per trophy kind (face out of the wall, ~15 degrees down). r1: the Trophy Hall, 80 boards (10 x 8) for ItemType.Trophy. Every board is the same size; the trophy is fitted to it per its own bounds (a Fader head shrinks, a Surtling shows at 0.7). "
             "The half (2 m, 40 boards) is the same script with --cols 5. Heaviest models: %s." % ", ".join("%s %d" % (n, TR[n]["tris"]) for n in heaviest[:3])),
    "checks": {"kinds_checked": len(names), "boards_per_kind": len(cells), "frame_clip_pairs": clip_pairs, "worst_cell_overshoot_mm": round(worst * 1000, 2),
               "coplanar_frame": COP, "max_back_gap_mm": round(max(CHECK[n]["back_gap_mm"] for n in names), 1), "item_rotation_applied": USE_ROT,
               "doc": "every ripped trophy, TURNED by its item_rotation and placed by the mod rule above on the four corner boards and the middle one, against the whole frame (BVH overlap of the real triangles): clip_pairs 0; its bounds stay inside its cell. back_gap_mm = how far the turned mesh stands in front of the back plane (the mod uses the turned bounds BOX, which is conservative: never behind, up to this far in front)."},
    "tris": {"frame": FRAME_TRIS, "all_kinds_once": tris_all, "full_store_all_kinds_once": FRAME_TRIS + tris_all,
             "heaviest": {n: TR[n]["tris"] for n in heaviest[:5]},
             "worst_case_80_of_the_heaviest": FRAME_TRIS + NUNITS * TR[heaviest[0]]["tris"]},
    "kinds": CHECK,
    "kinds_missing": {"TrophyForestTroll": "no mesh in the game bundle (null MeshFilter mesh); the mod measures the real prefab at run time, the fit rule is the same. Its item_rotation entry [20, 0, 0] is copied from TrophyFrostTroll (same troll head model family) and NOT verified on a mesh."},
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
    TAG = arg("--tag", "after" if USE_ROT else "before")
    TGT = (0, -0.2, 1.2)
    put_frame(); fill(ALL)
    look(0, 3, 7.4 if NCOL == 10 else 4.8, TGT); render("full-front-%s.png" % TAG, 2000, 1000)
    look(-22, 8, 7.2 if NCOL == 10 else 4.6, TGT); render("full-34-%s.png" % TAG)
    look(-70, 8, 6.0 if NCOL == 10 else 4.0, (0, -0.2, 1.1)); render("full-side-%s.png" % TAG)
    # a row of the heads Joost named, each close up on its own board, three views: front, 3/4, side (the side shows the tilt)
    clear()
    HEADS = ["TrophyEikthyr", "TrophyTheElder", "TrophyDragonQueen", "TrophyGoblinKing", "TrophySeekerQueen", "TrophyFrostTroll", "TrophyWolf", "TrophyLox",
             "TrophyBoar", "TrophyDeer", "TrophyGoblin", "TrophyNeck"]
    for nm in HEADS:
        if nm not in TR: continue
        put_frame(); put_trophy(nm, NCOL // 2, 3)
        tg = (col_x(NCOL // 2), YF - 0.14, row_z(3))
        look(-6, 4, 0.62, tg); render("head-%s-%s-front.png" % (nm[6:], TAG), 700, 560)
        look(-38, 12, 0.62, tg); render("head-%s-%s-34.png" % (nm[6:], TAG), 700, 560)
        look(-90, 0, 0.62, tg); render("head-%s-%s-side.png" % (nm[6:], TAG), 700, 560)
        clear()
print("DONE %.0fs" % (time.time() - t0))
