"""Produce Crates (was the Root Bin; slug and folders stay rootbin), round 6: a FULL crate LOOKS full, for every crop.

Joost, in game at 72/72: "this chest is full, but the carrots look almost empty". Round 5 settled one copy per stack for most
crops (8 loose carrots in a full crate). Round 6 keeps round 5's method (rigid body / Bullet, convex hulls, every copy frozen
after it settles, stack k dropped onto stacks 0..k-1, a try re-dropped when a body floats over 5 mm or a vertex leaves the
cavity) and round 5's scales, and changes:
- copies per stack are found per crop: every crop's 8-stack crate is filled until its heap surface (rays from above onto the
  DRAWN meshes, mean over the crate floor) reaches the onion crate's (Joost: "onions look right"), capped by a triangle budget
  per crate; the onion and the generic fallback (eggs, Joost: "eggs look good") keep round 5's copies;
- carrot and turnip are drawn without their greens since 0.3.1 (ItemVisual.Topless), so they collide, are checked and are
  judged by the ROOT alone (the greens may overlap anything; they are never drawn);
- whole-plant crops (barley, flax, thistle, dandelion, fiddlehead: one alpha-clipped material, no body) collide with a CORE: the
  convex hull pulled in towards the long axis (round ones: towards the centre), so stalks and leaves interleave like a real
  bundle instead of resting on each other's airy hulls; the cores obey the round-5 rules (interpenetration, float, floor);
- half first: stacks 0..3 settle in one half of the crate (Blender -x = the mod's left, +x), behind a virtual divider that
  stands 4 cm off the middle and leans back 15 degrees, stacks 4..7 fill the other half and crown the heap. A crate shared by
  two crops (the mod's divider board) then shows each crop's first four stacks in its own half; at 4 stacks a single-crop crate
  is visibly half full. Lying crops too long to lie front to back in that half were scaled down (at most 15%) until they fit.
The frame and atlas are round 5's (copied byte-identical); the anchors schema, units and crate_floor_centres are round 5's.
Output: assets/rootbin_r6/{RootBin.obj, rootbin_atlas.png, rootbin_anchors.json}; the json is written last (temp + rename).
Run: blender -b -P rootbin_r6.py -- [--out DIR] [--crops Carrot,Raspberry] [--probe] [--no-render] [--passes N]
"""
import bpy, bmesh, sys, os, math, json, random, time, shutil, subprocess, copy
import numpy as np
from mathutils import Vector, Matrix, Euler, Quaternion
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
R5 = os.path.normpath(os.path.join(HERE, "..", "assets", "rootbin_r5"))
OUTA = os.path.normpath(os.path.join(HERE, "..", "assets", "rootbin_r6"))
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
SCR = "C:/Users/joost/AppData/Local/Temp/claude/C--Users-joost--pai/5e4bc60b-cdfe-4638-8e29-2e507fa13cf9/scratchpad/rootbin6"
OUT = argv[argv.index("--out") + 1] if "--out" in argv else SCR
ITEMS = "C:/Users/joost/ValheimRip/items"
sys.path.append(ITEMS)
from load_item import load_item
os.makedirs(OUT, exist_ok=True)
def arg(name, default, typ=float): return typ(argv[argv.index(name) + 1]) if name in argv else default

# ---------- crops ----------
R5DOC = json.load(open(os.path.join(R5, "rootbin_anchors.json")))
R5LAY = R5DOC["crop_layouts"]
# name: (mode, copies in a FULL crate (8 stacks) to start from; spread over the stacks, earlier stacks first). mode: long = lies (across, or front to back), any roll; round = tilted up to
# TILT degrees; tumble = any orientation; flat = seed bag, nearly flat. Scales are round 5's (R5LAY) unless SCALE_HALF says.
CROPS = {
    "Carrot": ("long", 120), "Turnip": ("round", 62), "Onion": ("round", 16), "Barley": ("long", 16), "Flax": ("long", 16),
    "Mushroom": ("round", 10), "MushroomYellow": ("round", 16), "MushroomBlue": ("round", 16),
    "MushroomJotunPuffs": ("long", 12), "MushroomMagecap": ("long", 20),
    "Raspberry": ("tumble", 30), "Blueberries": ("tumble", 18), "Cloudberry": ("tumble", 24),
    "Thistle": ("long", 24), "Dandelion": ("long", 16), "Fiddleheadfern": ("round", 13),
    "CarrotSeeds": ("flat", 40), "TurnipSeeds": ("flat", 24), "OnionSeeds": ("flat", 40),
    "_generic": ("tumble", 40),
}
FIXED = {"Onion", "_generic"}             # Joost: onions look right (the reference), eggs on _generic look good
ROOT_ONLY = {"Carrot", "Turnip"}          # drawn without their greens (Storehouse.cs ItemVisual.Topless)
CORE = {"Barley": 0.8, "Flax": 0.8, "Thistle": 0.55, "Dandelion": 0.6, "Fiddleheadfern": 0.8}   # whole-plant collision cores
# Jotun puffs, the red mushroom and thistle: a full crate is physically full (drops at the crown) below the onion fill at round
# 5's scale (puffs 8-10 copies, red mushroom 9, thistle 14), so they are 13% smaller (the brief allows up to 15% where a crop
# cannot reach the rim otherwise). Thistle cannot lie front to back in half A even 15% smaller, so it fills the whole crate
# from the first stack (not half-first).
SCALE_FILL = {"MushroomJotunPuffs": 0.87, "Mushroom": 0.87, "Thistle": 0.87}
NO_HALF = {"Thistle"}
CORE_FLOOR = 0.03                         # a core crop's leaves may reach 3 cm into the straw
LEAF_FLOOR = 0.06                         # a leaf (not drawn for carrot/turnip) may sink 6 cm into the straw and slats
TILT = {"round": 40, "flat": 14, "upright": 12}
TRI_BUDGET_CRATE = 245000 // 9            # a full store of the heaviest crop stays under ~250k item triangles
for spec in [a for a in argv if a.startswith("--n:")]:          # --n:Carrot=100 overrides the full crate's copies
    k, v = spec[4:].split("="); CROPS[k] = (CROPS[k][0], int(v))
WANT = argv[argv.index("--crops") + 1].split(",") if "--crops" in argv else list(CROPS)
if "Onion" not in WANT: WANT = WANT + ["Onion"]                 # the fill reference always runs
NAMES = [n for n in CROPS if n in WANT and (n == "_generic" or os.path.exists(f"{ITEMS}/{n}/info.json"))]
print("R6 crops", NAMES, "missing", [n for n in CROPS if n in WANT and n not in NAMES], flush=True)

# ---------- frame (round 4, rebuilt with the same seed for the clip check and the renders; never exported here) ----------
rng = random.Random(7)
TEX = 128; DENS = 48.0
STRIP = {"hewn": (0.75, 32), "end": (0.5, 32), "dark": (0.375, 16), "iron": (0.25, 16), "straw": (0.125, 16)}
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

BAYS = [-0.6, 0.0, 0.6]
TIERS = [("A", 0.18, -0.60), ("B", 0.74, -0.30), ("C", 1.30, 0.00)]
CAV_HW = 0.265
CAV_Y0, CAV_Y1 = 0.020, 0.470
CEIL = {"A": 0.43, "B": 0.43, "C": 0.57}
XLINES = [(-0.93, 0.12), (-0.30, 0.09), (0.30, 0.09), (0.93, 0.12)]
SIDE_X = [-0.895, -0.30, 0.30, 0.895]

def build_frame():
    j = lambda a: rng.uniform(-a, a)
    for tn, zT, y0 in TIERS:
        for x in SIDE_X:
            timber("side", (0.05, 0.56, 0.34), (x, y0 + 0.25, zT + 0.07), kind="dark", bevel=0.008, jitter=0.004)
        for yb in (0.12, 0.38):
            timber("bearer", (1.84, 0.08, 0.07), (0, y0 + yb, zT - 0.082), kind="dark", bevel=0, jitter=0.004)
        for bx in BAYS:
            for dx in (-0.2, -0.067, 0.067, 0.2):
                timber("floor", (0.12, 0.54, 0.035), (bx + dx, y0 + 0.24, zT - 0.0295), kind="dark", bevel=0, jitter=0.003)
            timber("straw", (0.52, 0.47, 0.014), (bx, y0 + 0.2435, zT - 0.004), kind="straw", bevel=0, jitter=0.002)
        zs = (0.06, 0.205, 0.35) if tn != "C" else (0.06, 0.205, 0.35, 0.495)
        for bx in BAYS:
            for z in zs:
                timber("back", (0.55, 0.04, 0.135), (bx, y0 + 0.50, zT + z + j(0.004)), rot=(j(1.0), 0, j(0.7)),
                       bevel=0.007, jitter=0.004)
        for bx in BAYS:
            timber("front", (0.55, 0.04, 0.10), (bx, y0 - 0.02, zT + 0.06 + j(0.003)), rot=(10 + j(1.2), 0, j(0.6)),
                   kind="dark", bevel=0.007, jitter=0.004)
            for dx in (-0.19, 0.19):
                timber("strap", (0.04, 0.014, 0.15), (bx + dx, y0 - 0.047, zT + 0.058), rot=(10, 0, 0), kind="iron",
                       jitter=0.002, bevel=0.004)
    for x, sec in XLINES:
        for (tn, zT, y0), top in zip(TIERS, (0.64, 1.20, 2.0 if sec > 0.1 else 1.90)):
            yc = y0 + (0.545 if sec > 0.1 else 0.53)
            hh = top + j(0.01)
            timber("post", (sec, sec, hh), (x, yc, hh / 2), rot=(j(0.5), j(0.5), 0), bevel=0.014)
    for y in (-0.52, -0.16):
        timber("sill", (1.99, 0.12, 0.08), (0, y, 0.04), bevel=0.012)
    for sx in (-1, 1):
        for y0s, y1s, ztop in ((-0.08, 0.20, 0.64), (0.31, 0.60, 1.20)):
            n = int(ztop / 0.155)
            for i in range(n):
                timber("skirt", (0.03, y1s - y0s + j(0.01), 0.14), (sx * 0.955, (y0s + y1s) / 2, 0.075 + i * 0.155 + j(0.003)),
                       kind="dark", bevel=0.006, jitter=0.003)
    for sx in (-1, 1):
        timber("fpost", (0.10, 0.10, 0.86), (sx * 0.93, -0.01, 1.14 + 0.43), rot=(j(0.4), j(0.4), 0), bevel=0.012)
    timber("beam", (1.98, 0.10, 0.10), (0, -0.01, 1.93), rot=(0, 0, j(0.2)), bevel=0.012)
    timber("beam", (1.98, 0.10, 0.10), (0, 0.55, 1.95), rot=(0, 0, j(0.2)), bevel=0.012)
    for x in (-0.60, 0.0, 0.60):
        timber("rafter", (0.09, 0.62, 0.06), (x, 0.27, 1.935), bevel=0.008, jitter=0.004)
    for sx in (-1, 1):
        timber("band", (0.155, 0.155, 0.05), (sx * 0.93, 0.545, 1.95), kind="iron", jitter=0.003, bevel=0.006)
        timber("band", (0.155, 0.155, 0.05), (sx * 0.93, 0.245, 1.17), kind="iron", jitter=0.003, bevel=0.006)
        timber("band", (0.155, 0.155, 0.05), (sx * 0.93, -0.055, 0.61), kind="iron", jitter=0.003, bevel=0.006)

def cav(ci):
    tn, zT, y0 = TIERS[ci // 3]; bx = BAYS[ci % 3]
    return (bx - CAV_HW, bx + CAV_HW, y0 + CAV_Y0, y0 + CAV_Y1, zT + 0.006, zT + CEIL[tn])

def floor_centre(ci):
    """Blender position of crate ci's floor centre (= round 4's crates[].floor_centre)."""
    tn, zT, y0 = TIERS[ci // 3]; bx = BAYS[ci % 3]
    return np.array((bx, y0 + (CAV_Y0 + CAV_Y1) / 2, zT + 0.003))

# the generic cavity, relative to a crate's floor centre: the common part of all nine crates (A/B ceiling, the lower one)
GEN = (-CAV_HW, CAV_HW, -(CAV_Y1 - CAV_Y0) / 2, (CAV_Y1 - CAV_Y0) / 2, 0.003, CEIL["A"] - 0.003)
SIM_DX = 1.0                     # crop i simulates in a generic crate at x = i * SIM_DX
# half first: stacks 0..3 in half A (Blender -x = Unity +x, the mod's left), back before front, behind a virtual divider;
# stacks 4..7 in half B, then crowning. Stack targets are crate-floor-centre local (Blender).
DIV_X = -0.01                    # the divider's foot, crate local: 1 cm off the middle (half A as large as half B)
DIV_K = math.tan(math.radians(4))    # it leans back a little into half A: x <= DIV_X - (z - floor) * DIV_K
NHALF = 4
A_CAP = 0.33                     # half A's heap (stacks 0..3) stays under 33 cm; what does not fit there moves to stacks 4..7
HEAP_CAP = 0.40                  # the full heap's crown: 40 cm over the floor at most (the shelf above is at 43 cm)
STACK_XY = [(-0.15, 0.11), (-0.15, -0.11), (-0.15, 0.11), (-0.15, -0.11), (0.13, 0.11), (0.13, -0.11), (0.0, 0.11), (0.0, -0.11)]

# ---------- scene ----------
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
atlas = bpy.data.images.load(os.path.join(R5, "rootbin_atlas.png"))
MAT = bpy.data.materials.new("rootbin"); MAT.use_nodes = True
nt = MAT.node_tree; bsdf = nt.nodes["Principled BSDF"]
ti = nt.nodes.new("ShaderNodeTexImage"); ti.image = atlas; ti.interpolation = "Closest"
nt.links.new(ti.outputs["Color"], bsdf.inputs["Base Color"])
bsdf.inputs["Roughness"].default_value = 0.8

def join(obs, name):
    bpy.ops.object.select_all(action="DESELECT")
    for o in obs: o.select_set(True)
    bpy.context.view_layer.objects.active = obs[0]
    bpy.ops.object.join(); ob = bpy.context.active_object; ob.name = name
    return ob

# ---------- item templates ----------
TPL = {}
def lump_mesh():
    """the generic fallback: a neutral round lump, ~0.12 m."""
    bm = bmesh.new(); bmesh.ops.create_icosphere(bm, subdivisions=2, radius=0.5)
    r = random.Random(3)
    for v in bm.verts:
        f = 1 + 0.07 * math.sin(3 * v.co.x + 2 * v.co.y) + r.uniform(-0.025, 0.025)
        v.co = Vector((v.co.x * 0.12 * f, v.co.y * 0.108 * f, v.co.z * 0.096 * f))
    me = bpy.data.meshes.new("_generic"); bm.to_mesh(me); bm.free()
    m = bpy.data.materials.new("VH__generic_lump"); m.use_nodes = True
    m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.42, 0.36, 0.26, 1)
    me.materials.append(m)
    return me

def tpl(name):
    if name in TPL: return TPL[name]
    if name == "_generic":
        datas = [lump_mesh()]
    else:
        objs = [o for o in load_item(name, anchor="center") if o.type == "MESH"]
        datas = [o.data for o in objs]
        for o in objs: bpy.data.objects.remove(o)
    allv = np.array([v.co[:] for d in datas for v in d.vertices])
    mn, mx = allv.min(0), allv.max(0); c = (mn + mx) / 2
    for d in datas: d.transform(Matrix.Translation(-Vector(c)))
    TPL[name] = dict(datas=datas, size=mx - mn, verts=allv - c)
    return TPL[name]

def align_matrix(size):
    ax = int(np.argmax(size)); v = Vector([1.0 if i == ax else 0.0 for i in range(3)])
    return v.rotation_difference(Vector((1, 0, 0))).to_matrix()

def leaf_materials(item):
    """alpha-clipped materials are the leaves, but only when the item also has an opaque material (the body)."""
    if item == "_generic": return set()
    mats = json.load(open(f"{ITEMS}/{item}/info.json"))["materials"]
    if any(v.get("alpha_mode") != "clip" for v in mats.values()):
        return {k for k, v in mats.items() if v.get("alpha_mode") == "clip"}
    return set()

MERGED = {}
def merged(item):
    """the visible mesh (all parts, centred on the bounds, native orientation) and the collision body: convex hull of the
    NON-leaf vertices, origin at the body centre."""
    if item in MERGED: return MERGED[item]
    t = tpl(item)
    obs = []
    for d in t["datas"]:
        o = bpy.data.objects.new("m", d.copy()); sc.collection.objects.link(o); obs.append(o)
    ob = join(obs, "mrg") if len(obs) > 1 else obs[0]
    me = ob.data; me.name = item
    leafm = leaf_materials(item)
    names = [(mt.name[len(f"VH_{item}_"):] if mt else "") for mt in me.materials]
    body_v = set(); leaf_v = set()
    for p in me.polygons:
        (leaf_v if names[p.material_index] in leafm else body_v).update(p.vertices)
    leaf_only = leaf_v - body_v
    bpy.data.objects.remove(ob)
    verts = np.array([v.co[:] for v in me.vertices])
    leafmask = np.zeros(len(verts), bool); leafmask[list(leaf_only)] = True
    # drawn: what the mod shows (carrot and turnip without their greens); tolerance: how far a drawn vertex may go below the floor
    drawn = ~leafmask if item in ROOT_ONLY else np.ones(len(verts), bool)
    tol = np.where(leafmask, LEAF_FLOOR, 0.002)
    if item in CORE: tol[:] = CORE_FLOOR
    dtris = sum(len(p.vertices) - 2 for p in me.polygons if item not in ROOT_ONLY or names[p.material_index] not in leafm)
    bv = verts[sorted(body_v)]
    cb = (bv.min(0) + bv.max(0)) / 2
    cpts = bv
    if item in CORE:
        # a whole-plant crop collides with a core: its hull pulled in towards the long axis (round crops: the centre)
        ax = int(np.argmax(t["size"])); q = bv - cb
        if CROPS[item][0] == "long":
            perp = np.ones(3, bool); perp[ax] = False; q[:, perp] *= CORE[item]
        else:
            q *= CORE[item]
        cpts = cb + q
    bm = bmesh.new()
    for v in cpts - cb: bm.verts.new(v)
    res = bmesh.ops.convex_hull(bm, input=bm.verts[:])
    for g in res["geom_interior"] + res["geom_unused"]:
        if isinstance(g, bmesh.types.BMVert) and g.is_valid and not g.link_faces: bm.verts.remove(g)
    fs = [f for f in bm.faces if f.is_valid]
    bmesh.ops.triangulate(bm, faces=fs)
    bm.normal_update(); bm.verts.index_update()
    vol = bm.calc_volume()
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
        if n @ cen > d0: n = -n; d0 = -d0
        N.append(n); D.append(d0)
    bm.free()
    pm = bpy.data.meshes.new(f"prox_{item}"); pm.from_pydata([tuple(v) for v in hv], [], [tuple(int(i) for i in f) for f in F]); pm.update()
    edges = sorted({tuple(sorted((int(f[a]), int(f[(a + 1) % 3])))) for f in F for a in range(3)})
    dv = verts[drawn]
    # the visible mesh the mod draws (renders, the fill metric): carrot and turnip without their greens
    if item in ROOT_ONLY:
        dm = me.copy(); dm.name = item + "_drawn"
        bmd = bmesh.new(); bmd.from_mesh(dm)
        kill = [f for f in bmd.faces if names[f.material_index] in leafm]
        bmesh.ops.delete(bmd, geom=kill, context="FACES"); bmd.to_mesh(dm); bmd.free()
    else:
        dm = me
    MERGED[item] = dict(mesh=dm, fullmesh=me, verts=verts, leafmask=leafmask, drawn=drawn, tol=tol, dtris=dtris, cb=cb, hullV=hv,
                        hullF=F, hullN=np.array(N), hullD=np.array(D), hullE=edges, prox=pm, size=np.array(t["size"]), vol=abs(vol),
                        bodysize=bv.max(0) - bv.min(0), drawnsize=dv.max(0) - dv.min(0))
    return MERGED[item]

def pose_matrix(c, R3, s):
    return Matrix.Translation(Vector(c)) @ Matrix(R3).to_4x4() @ Matrix.Diagonal((s, s, s, 1))
def world_pts(P, M): return P @ M[:3, :3].T + M[:3, 3]

def rec_world(m, Mp, s):
    M = Mp.copy(); M[:3, 3] = Mp[:3, 3] - Mp[:3, :3] @ m["cb"]      # visible item matrix (origin = item bounds centre)
    hv = world_pts(m["hullV"], Mp)
    Rw = Mp[:3, :3] / s
    N = m["hullN"] @ Rw.T; D = m["hullD"] * s + N @ Mp[:3, 3]
    return dict(M=M, Mp=Mp, s=s, hv=hv, N=N, D=D, lo=hv.min(0), hi=hv.max(0), F=m["hullF"], E=m["hullE"])

CELL = 0.02
class Crate:
    def __init__(self, b):
        self.b = b; self.bodies = []
        self.nx = int(math.ceil((b[1] - b[0]) / CELL)); self.ny = int(math.ceil((b[3] - b[2]) / CELL))
        self.hf = np.full((self.nx, self.ny), b[4])
    def add_hull(self, N, D, lo, hi):
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
        self.hf[I.ravel(), J.ravel()] = np.maximum(self.hf[I.ravel(), J.ravel()], zt)
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
    best = (1e9, None)
    bb = _bvh(B)
    for p in _samples(A):
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
    """distance (m) from the body to its nearest support: the crate floor, or an earlier body touching it from below."""
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

# ---------- per-crop setup ----------
CROP = {}
SPAWN_MG = 0.012
SPAWN_OVER = 0.04                # a drop may start up to 4 cm above the cavity top (the walls reach 6 cm higher); it must settle below it
def plan_room(): return (GEN[1] - GEN[0]) - 2 * SPAWN_MG - 0.006
def room_y(): return (GEN[3] - GEN[2]) - 2 * SPAWN_MG - 0.006
def room_half(): return (DIV_X - 0.004 - GEN[0]) - SPAWN_MG          # half A at the floor: wall margin, divider check margin
def yaw_set(L, W, rx, ry):
    """yaws (degrees from the crate's x axis, 0..179) at which a lying item L long and W wide fits an rx x ry floor."""
    out = []
    for a in range(180):
        c, sn = abs(math.cos(math.radians(a))), abs(math.sin(math.radians(a)))
        if L * c + W * sn <= rx and L * sn + W * c <= ry: out.append(float(a))
    return out
SCALE_HALF = {}                  # scale lowered so a lying crop fits front to back in half A (stacks 0..3)
for i, name in enumerate(NAMES):
    mode, n = CROPS[name]
    m = merged(name)
    size = m["size"]
    s = 1.0 if name == "_generic" else float(R5LAY[name]["scale"])
    sr5 = s; s = s * SCALE_FILL.get(name, 1.0)
    yaw_full, yaw_half = [], []
    if mode == "long":
        ax = int(np.argmax(size)); ds = m["drawnsize"]
        perp = sorted(float(ds[j]) for j in range(3) if j != ax)
        s0 = s
        while name not in NO_HALF:
            L = float(ds[ax]) * s; W = perp[1] * s       # cross section ~ the larger perpendicular side (any roll)
            yaw_full = yaw_set(L, W, plan_room(), room_y()); yaw_half = yaw_set(L, W, room_half(), room_y())
            if len(yaw_half) >= 5 or s < 0.85 * sr5 + 1e-9: break
            s *= 0.99
        if len(yaw_half) < 5 or name in NO_HALF:          # cannot lie in half A even 15% smaller: keep the start scale
            s = s0; L = float(ds[ax]) * s; W = perp[1] * s
            yaw_full = yaw_set(L, W, plan_room(), room_y()); yaw_half = []
        elif s < s0 - 1e-9:
            SCALE_HALF[name] = (round(sr5, 4), round(s, 4))
    if name in SCALE_FILL and name not in SCALE_HALF: SCALE_HALF[name] = (round(sr5, 4), round(s, 4))
    b = (i * SIM_DX + GEN[0], i * SIM_DX + GEN[1], GEN[2], GEN[3], GEN[4], GEN[5])
    cap = max(8, TRI_BUDGET_CRATE // m["dtris"])
    CROP[name] = dict(i=i, name=name, mode=mode, n=min(n, cap), cap=cap, s=s, yaw_full=yaw_full, yaw_half=yaw_half, b=b,
                      half=(name not in NO_HALF and (mode != "long" or bool(yaw_half))),
                      wall_in=float(((m["drawnsize"] - (m["hullV"].max(0) - m["hullV"].min(0))) / 2).max()) * s if name in CORE else 0.0,
                      origin=np.array((i * SIM_DX, 0.0, 0.0)), crate=Crate(b))
    print("R6 crop %-18s mode %-6s scale %.4f (r5 %s) drawn@s %s hull@s %s hullvol@s %.5f m3 copies/stack %d cap %d drawn tris %d yaws full %d half %d"
          % (name, mode, s, R5LAY.get(name, {}).get("scale"), np.round(m["drawnsize"] * s, 3), np.round((m["hullV"].max(0) - m["hullV"].min(0)) * s, 3),
             m["vol"] * s ** 3, CROP[name]["n"], cap, m["dtris"], len(yaw_full), len(yaw_half)), flush=True)
print("R6 half-fit scale changes", SCALE_HALF, flush=True)
if "--probe" in argv:
    print("DONE probe"); sys.exit(0)

# ---------- simulation (round 4's method, generic cavities side by side, one per crop) ----------
MAXF = arg("--maxf", 140); MINF = 16
VW = arg("--vw", 0.2)
DAMP_L = 0.5; DAMP_A = 0.95
NTRY = arg("--ntry", 30, int)
MARGIN = 0.0015
FLOAT_MAX = 0.005
DEBUG = "--debug" in argv

def rand_rot(rr):
    q = Quaternion([rr.gauss(0, 1) for _ in range(4)]); q.normalize(); return q.to_matrix()

def simulate(crops, seed):
    rr = random.Random(seed)
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
            rb.use_deactivation = True; rb.deactivate_linear_velocity = 0.08; rb.deactivate_angular_velocity = 0.4
        return rb
    def add_box(lo, hi):
        me = bpy.data.meshes.new("col")
        bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0); bm.to_mesh(me); bm.free()
        ob = bpy.data.objects.new("col", me); sc.collection.objects.link(ob)
        ob.scale = [hi[i] - lo[i] for i in range(3)]; ob.location = [(hi[i] + lo[i]) / 2 for i in range(3)]
        rb = set_rb(ob, "PASSIVE", 1.0); rb.collision_shape = "BOX"; rb.use_margin = True; rb.collision_margin = 0.0
    T = 0.03
    for c in crops:
        x0, x1, y0, y1, z0, z1 = c["b"]; H = z1 - z0 + 0.06
        inset = 0.002 + c["wall_in"]            # a core crop's walls stand in by its leaves' overhang, so the leaves stay inside
        add_box((x0 - T, y0 - T, z0 - 0.1), (x1 + T, y1 + T, z0))
        add_box((x0 - T, y0 - T, z0 - 0.1), (x0 + inset, y1 + T, z0 + H))
        add_box((x1 - inset, y0 - T, z0 - 0.1), (x1 + T, y1 + T, z0 + H))
        add_box((x0 - T, y0 - T, z0 - 0.1), (x1 + T, y0 + inset, z0 + H))
        add_box((x0 - T, y1 - inset, z0 - 0.1), (x1 + T, y1 + T, z0 + H))
    def add_divider(c):
        """half A's virtual divider: a passive slab whose -x face is the plane x = DIV_X - (z - z0) * DIV_K (crate local)."""
        x0, x1, y0, y1, z0, z1 = c["b"]; ox = c["origin"][0]
        me = bpy.data.meshes.new("div")
        bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0); bm.to_mesh(me); bm.free()
        ob = bpy.data.objects.new("div", me); sc.collection.objects.link(ob)
        Tk, hh = 0.04, 0.9; phi = math.atan(DIV_K)
        u = np.array((-math.sin(phi), 0, math.cos(phi))); nn = np.array((math.cos(phi), 0, math.sin(phi)))
        P = np.array((ox + DIV_X - c["wall_in"], 0.0, z0)) + u * (hh / 2 - 0.1) + nn * (Tk / 2)
        ob.scale = (Tk, (y1 - y0) + 0.06, hh); ob.rotation_euler = (0, -phi, 0); ob.location = P.tolist()
        rb = set_rb(ob, "PASSIVE", 1.0); rb.collision_shape = "BOX"; rb.use_margin = True; rb.collision_margin = 0.0
        return ob
    dividers = [add_divider(c) for c in crops if c["half"]]
    st = dict(frames=0, drops=0, tries=0, rej=dict(), unsettled=0)
    allr = []
    PROBE = np.array([[1, 0, 0], [-1, 0, 0], [0, 1, 0], [0, -1, 0], [0, 0, 1], [0, 0, -1]], float)
    frz = [0]

    def orient(w, c, m, half):
        if c["mode"] == "long":
            ys = c["yaw_half"] if half else c["yaw_full"]
            yaw = rr.choice(ys) + rr.uniform(-0.5, 0.5) + (180 if rr.random() < 0.5 else 0)
            return Rz(yaw) @ Ry(rr.uniform(-6, 6)) @ Rx(rr.uniform(0, 360)) @ align_matrix(m["size"])
        if c["mode"] == "tumble":
            return rand_rot(rr)
        t = TILT[c["mode"]]
        return Rz(rr.uniform(0, 360)) @ Rx(rr.uniform(-t, t)) @ Ry(rr.uniform(-t, t))

    def spawn(w):
        c, k = w["c"], w["k"]; cr = c["crate"]; m = merged(c["name"]); s = c["s"]; w["s"] = s
        half = w["stack"] < NHALF and c["half"]
        x0, x1, y0, y1, z0, z1 = cr.b; mg = SPAWN_MG; ox = c["origin"][0]
        ex = w.setdefault("extra", np.zeros(5))
        # an orientation that fits the floor it may use (half A for stacks 0..3): up to 16 samples
        for _ in range(16):
            Rc = orient(w, c, m, half); Rn = np.array(Rc)
            HV = (m["hullV"] @ Rn.T) * s
            AV = ((m["verts"][m["drawn"]] - m["cb"]) @ Rn.T) * s          # what the mod draws
            lo = np.minimum(AV.min(0), HV.min(0)); hi = np.maximum(AV.max(0), HV.max(0))
            gplane = float((AV[:, 0] + AV[:, 2] * DIV_K).max()) if half else 0.0
            xr = (x0 - lo[0] + mg + ex[0], x1 - hi[0] - mg - ex[1]); yr = (y0 - lo[1] + mg + ex[2], y1 - hi[1] - mg - ex[3])
            if half: xr = (xr[0], min(xr[1], ox + DIV_X - 0.004 - gplane))
            if xr[0] <= xr[1] and yr[0] <= yr[1]: break
        else:
            return False, "plan"
        low = -HV[:, 2].min()
        ux, uy = c["origin"][0] + STACK_XY[w["stack"]][0], STACK_XY[w["stack"]][1]
        Nr = m["hullN"] @ Rn.T; Dr = m["hullD"] * s
        dn = Nr[:, 2] < -1e-6; up = Nr[:, 2] > 1e-6
        kx = np.arange(int(math.floor(HV[:, 0].min() / CELL)), int(math.ceil(HV[:, 0].max() / CELL)) + 1)
        ky = np.arange(int(math.floor(HV[:, 1].min() / CELL)), int(math.ceil(HV[:, 1].max() / CELL)) + 1)
        KX, KY = np.meshgrid(kx, ky, indexing="ij"); PX = KX.ravel() * CELL; PY = KY.ravel() * CELL
        P = Nr[:, 0:1] * PX[None, :] + Nr[:, 1:2] * PY[None, :]
        zb = ((Dr[dn, None] - P[dn]) / Nr[dn, 2][:, None]).max(0); zt = ((Dr[up, None] - P[up]) / Nr[up, 2][:, None]).min(0)
        okc = zt > zb
        if not okc.any(): okc[:] = True; zb[:] = -low
        KXo, KYo, ZB = KX.ravel()[okc], KY.ravel()[okc], zb[okc]
        icand = [i for i in range(cr.nx) if xr[0] - 1e-9 <= x0 + (i + 0.5) * CELL <= xr[1] + 1e-9] or [int(((xr[0] + xr[1]) / 2 - x0) / CELL)]
        jcand = [j for j in range(cr.ny) if yr[0] - 1e-9 <= y0 + (j + 0.5) * CELL <= yr[1] + 1e-9] or [int(((yr[0] + yr[1]) / 2 - y0) / CELL)]
        clear = 0.012
        hf = cr.tmp                                   # the heap plus this batch's copies already placed
        def drop_z(i, j):
            ii = i + KXo; jj = j + KYo
            v = (ii >= 0) & (ii < cr.nx) & (jj >= 0) & (jj < cr.ny)
            return float((hf[ii[v], jj[v]] - ZB[v]).max()) if v.any() else z0 + low
        best = None
        for i in icand:
            for j in jcand:
                xx = min(max(x0 + (i + 0.5) * CELL, xr[0]), xr[1]); yy = min(max(y0 + (j + 0.5) * CELL, yr[0]), yr[1])
                zc = max(drop_z(i, j), z0 + low) + clear
                if zc + hi[2] > z1 + SPAWN_OVER - ex[4]: continue
                if zc - clear + hi[2] > z0 + (c["acap"] if half else HEAP_CAP): continue
                if half and xx - ox + gplane + (zc - z0) * DIV_K > DIV_X - 0.004: continue
                cost = zc + VW * math.hypot(xx - ux, yy - uy) + rr.uniform(0, 0.006)
                if best is None or cost < best[0]: best = (cost, xx, yy, zc)
        if best is None:
            return False, "ceiling"
        x, y, zc = best[1], best[2], best[3]
        # this batch's later copies of the crop keep clear of this one (its box, raised over its footprint)
        i0 = max(0, int((x + lo[0] - x0) / CELL)); i1 = min(cr.nx - 1, int((x + hi[0] - x0) / CELL))
        j0 = max(0, int((y + lo[1] - y0) / CELL)); j1 = min(cr.ny - 1, int((y + hi[1] - y0) / CELL))
        cr.tmp[i0:i1 + 1, j0:j1 + 1] = np.maximum(cr.tmp[i0:i1 + 1, j0:j1 + 1], zc + hi[2] + 0.005)
        ob = bpy.data.objects.new(c["name"], m["prox"]); sc.collection.objects.link(ob)
        ob.matrix_world = pose_matrix((x, y, zc), Rc, s)
        ext = HV.max(0) - HV.min(0)
        rb = set_rb(ob, "ACTIVE", max(0.02, float(np.prod(ext)) * 600))
        rb.collision_shape = "CONVEX_HULL"; rb.mesh_source = "BASE"; rb.use_margin = True; rb.collision_margin = MARGIN
        w.update(ob=ob, m=m, probe=PROBE * 0.5 * ext, half=half)
        return True, ""

    def evaluate(w):
        m = w["m"]; c = w["c"]; cr = c["crate"]
        r = rec_world(m, w["Mp"], w["s"])
        r.update(name=c["name"], stack=w["stack"], k=w["k"], s=w["s"])
        V = world_pts(m["verts"], r["M"]); dr = m["drawn"]; Vd = V[dr]
        x0, x1, y0, y1, z0, z1 = cr.b; e = 0.0005
        bad = []
        if (Vd[:, 2] < z0 - m["tol"][dr]).any(): bad.append("below floor")
        walls = (Vd[:, 0].min() < x0 + e) or (Vd[:, 0].max() > x1 - e) or (Vd[:, 1].min() < y0 + e) or (Vd[:, 1].max() > y1 - e)
        if walls: bad.append("outside walls")
        ceil = Vd[:, 2].max() > z1 - e
        if ceil: bad.append("above ceiling")
        if w.get("half") and ((Vd[:, 0] - c["origin"][0]) + (Vd[:, 2] - z0) * DIV_K > DIV_X + 0.001).any(): bad.append("over divider")
        if walls or ceil:
            w["extra"] = w.get("extra", np.zeros(5)) + np.maximum(0, [x0 - Vd[:, 0].min() + 0.003, Vd[:, 0].max() - x1 + 0.003,
                y0 - Vd[:, 1].min() + 0.003, Vd[:, 1].max() - y1 + 0.003, Vd[:, 2].max() - z1 + 0.003]) * np.array([walls] * 4 + [ceil], float)
            w["extra"] = np.minimum(w["extra"], 0.04)
        gap, what = support_gap(r, z0, cr.bodies)
        r["gap"] = gap; r["support"] = what
        if gap > FLOAT_MAX: bad.append("floats %.1f mm" % (gap * 1000))
        return (not bad), ",".join(bad), r

    def freeze_into_world(r, ob, c):
        sc.frame_set(1)
        ob.matrix_world = Matrix(r["Mp"].tolist()); ob.rigid_body.type = "PASSIVE"
        ob.rigid_body.use_margin = True; ob.rigid_body.collision_margin = MARGIN
        r["id"] = frz[0]; frz[0] += 1                 # freeze order: a body only ever rests on bodies frozen before it
        c["crate"].bodies.append(r)
        c["crate"].add_hull(r["N"], r["D"], r["lo"], r["hi"])

    def attempt(pending):
        sc.frame_set(1)
        for c in {id(w["c"]): w["c"] for w in pending}.values(): c["crate"].tmp = c["crate"].hf.copy()
        ok = []
        for w in pending:
            good, why = spawn(w)
            if good: ok.append(w)
            else:
                w["why"] = why; st["rej"][why] = st["rej"].get(why, 0) + 1
                w["c"].setdefault("rej", {}); w["c"]["rej"][why] = w["c"]["rej"].get(why, 0) + 1
        if not ok: return [], 0
        bpy.context.view_layer.update()
        prev = {}; f = 1
        for f in range(2, MAXF + 2):
            sc.frame_set(f); st["frames"] += 1
            if f >= MINF and f % 3 == 0:
                dg = bpy.context.evaluated_depsgraph_get(); mx = 0.0
                for w in ok:
                    pts = world_pts(w["probe"], np.array(w["ob"].evaluated_get(dg).matrix_world))
                    if w["uid"] in prev: mx = max(mx, float(np.abs(pts - prev[w["uid"]]).max()))
                    prev[w["uid"]] = pts
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
            # half A is full: a copy that found no room there three times moves to stacks 4..7
            for w in failed:
                if w["stack"] < NHALF and w.get("why") in ("ceiling", "plan"):
                    w["roomfails"] = w.get("roomfails", 0) + 1
            for w in [w for w in failed if w.get("roomfails", 0) >= 3 and w["k"] > 0]:     # every stack keeps its first copy
                w["c"].setdefault("carry", []).append(w); failed.remove(w)
            accepted = []
            for w in ok:
                good, why, r = evaluate(w)
                if good:
                    r["unsettled"] = f >= MAXF + 1; accepted.append((w, r))
                else:
                    key = "".join(ch for ch in why.split(",")[0] if not (ch.isdigit() or ch == ".")).strip(" ")
                    w["why"] = why; st["rej"][key] = st["rej"].get(key, 0) + 1
                    w["c"].setdefault("rej", {}); w["c"]["rej"][key] = w["c"]["rej"].get(key, 0) + 1
                    failed.append(w)
            for w in ok:
                if w in failed: bpy.data.objects.remove(w["ob"])
            sc.frame_set(1)
            for w, r in accepted:
                freeze_into_world(r, w["ob"], w["c"]); allr.append(r)
                if r["unsettled"]: st["unsettled"] += 1
            pending = failed
        st["drops"] += len(pending)
        for w in pending:
            w["c"].setdefault("dropped", []).append((w["stack"], w["k"], w.get("why")))
        if pending and DEBUG: print("R6 dropped", [(w["c"]["name"], w["stack"], w["k"], w.get("why")) for w in pending], flush=True)

    uid = 0; tstart = time.time()
    for c in crops:
        c["carry"] = []
        if not c["half"]: c["nk"] = spread(c["n"], 8)
        else:
            qa = c.get("qa") or spread(math.ceil(c["n"] / 2))
            c["nk"] = list(qa) + spread(c["n"] - sum(qa))
    for stack in range(8):
        if stack == NHALF:
            sc.frame_set(1)
            for o in dividers: bpy.data.objects.remove(o)
            dividers.clear()
            for c in crops:                      # what half A could not take is spread over stacks 4..7
                e = spread(len(c["carry"]))
                c["nk"] = [c["nk"][k] - sum(1 for w in c["carry"] if w["stack"] == k) for k in range(NHALF)] +                     [c["nk"][NHALF + j] + e[j] for j in range(4)]
        # a crop's copies of this stack in chunks of up to 4 dropped together; batch j = every crop's chunk j
        chunks = {}
        for c in crops:
            nn = c["nk"][stack]; per = max(1, min(4, math.ceil(nn / 3)))
            chunks[c["name"]] = [list(range(a, min(nn, a + per))) for a in range(0, nn, per)]
        for j in range(max(len(v) for v in chunks.values())):
            batch = []
            for c in crops:
                if j < len(chunks[c["name"]]):
                    for kk in chunks[c["name"]][j]:
                        batch.append(dict(c=c, stack=stack, k=kk, uid=uid)); uid += 1
            run_batch(batch)
        if stack == NHALF - 1:
            for c in crops: c["hf_half"] = c["crate"].hf.copy()
        print("R6 stack", stack, "bodies", len(allr), "frames", st["frames"], "tries", st["tries"], "dropped", st["drops"],
              "t=%.0fs" % (time.time() - tstart), flush=True)
    for o in [o for o in bpy.data.objects if o.rigid_body is not None]: bpy.data.objects.remove(o)
    bpy.ops.rigidbody.world_remove()
    sc.frame_set(1)
    return allr, dict(frames=st["frames"], tries=st["tries"], dropped=st["drops"], unsettled=st["unsettled"], rejections=st["rej"])

def interpenetration(res):
    lo = np.array([r["lo"] for r in res]); hi = np.array([r["hi"] for r in res])
    worst = 0.0; deps = []
    for i, a in enumerate(res):
        ov = np.where(((lo <= a["hi"]) & (hi >= a["lo"])).all(1))[0]
        for j in ov:
            if j == i: continue
            b = res[j]
            d = b["D"][None, :] - a["hv"] @ b["N"].T
            ins = (d > 0).all(1)
            if ins.any():
                dep = float(d[ins].min(1).max()); deps.append(dep); worst = max(worst, dep)
    return worst, len(deps)

def float_check(res):
    """every body vs the bodies of the same crop dropped BEFORE it (what exists when only earlier stacks are shown)."""
    by = {}; out = []
    for r in sorted(res, key=lambda r: r["id"]):
        earlier = by.setdefault(r["name"], [])
        g, what = support_gap(r, GEN[4], earlier)
        out.append((g, what, r["name"], r["stack"], r["k"])); earlier.append(r)
    out.sort(key=lambda x: -x[0])
    return out

def local_M(r):
    """the settled visible-item matrix, relative to the crop's crate floor centre (Blender)."""
    M = r["M"].copy(); M[:3, 3] -= CROP[r["name"]]["origin"]; return M

def clip_check(res):
    """every crop's layout put into each of the nine real crates (translation only): a copy clips if a vertex leaves that
    crate's cavity (leaves may sink LEAF_FLOOR into the straw and slats) or a vertex near a wall/ceiling/floor lies inside a
    frame part."""
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
    bad = {}; maxout = -9
    for r in res:
        m = merged(r["name"]); dr = m["drawn"]; lm = m["leafmask"][dr] | (m["tol"][dr] > 0.0021)
        Vl = world_pts(m["verts"][dr], local_M(r))
        for ci in range(9):
            V = Vl + floor_centre(ci)
            cx0, cx1, cy0, cy1, cz0, cz1 = cav(ci); why = None
            zlim = cz0 - m["tol"][dr]
            over = max(cx0 - V[:, 0].min(), V[:, 0].max() - cx1, cy0 - V[:, 1].min(), V[:, 1].max() - cy1, float((zlim - V[:, 2]).max()), V[:, 2].max() - cz1)
            maxout = max(maxout, over)
            if over > 0: why = "outside cavity by %.4f" % over
            else:
                near = (V[:, 0] - cx0 < 0.03) | (cx1 - V[:, 0] < 0.03) | (V[:, 1] - cy0 < 0.03) | (cy1 - V[:, 1] < 0.03) | (cz1 - V[:, 2] < 0.03)
                near |= (V[:, 2] - cz0 < 0.01) & (~lm)
                near &= ~(lm & (V[:, 2] < cz0))
                for q in V[near]:
                    for c in np.where(((q >= LO) & (q <= HI)).all(1))[0]:
                        if inside_p(parts[c][2], Vector(q)): why = "inside frame part %s at %s" % (PARTS[c].name, np.round(q, 3)); break
                    if why: break
            if why: bad.setdefault(r["name"], []).append((ci, r["stack"], r["k"], why))
    n = sum(len(v) for v in bad.values())
    print("R6 CLIPPING", n, {k: len(v) for k, v in bad.items()}, [v[:2] for v in bad.values()][:4], "max outside %.4f" % maxout, flush=True)
    return n, bad

# ---------- fill metric: how full a crate LOOKS ----------
FILL_STEP = 0.02
_DM = {}
def drawn_tris(name):
    """the drawn mesh (carrot/turnip: root only) as vertex array + triangle index array, item-local (bounds centre origin)."""
    if name not in _DM:
        me = merged(name)["mesh"]; me.calc_loop_triangles()
        _DM[name] = (np.array([v.co[:] for v in me.vertices]), np.array([lt.vertices[:] for lt in me.loop_triangles]))
    return _DM[name]

def fill_metric(name, rs, nstacks=8):
    """rays straight down onto the drawn copies of stacks 0..nstacks-1, on a 2 cm grid over the crate floor: the heap surface's
    mean height above the floor (no hit = 0), over the whole crate, half A (x < DIV_X) and half B (x > 0); and the floor cover."""
    V0, T0 = drawn_tris(name); vs = []; ts = []; off = 0
    for r in rs:
        if r["stack"] >= nstacks: continue
        vs.append(world_pts(V0, local_M(r))); ts.append(T0 + off); off += len(V0)
    xs = np.arange(GEN[0] + FILL_STEP / 2, GEN[1], FILL_STEP); ys = np.arange(GEN[2] + FILL_STEP / 2, GEN[3], FILL_STEP)
    H = np.zeros((len(xs), len(ys)))
    if vs:
        V = np.vstack(vs); T = np.vstack(ts)
        bvh = BVHTree.FromPolygons([Vector(v) for v in V], [tuple(int(i) for i in t) for t in T])
        down = Vector((0, 0, -1))
        for i, x in enumerate(xs):
            for j, y in enumerate(ys):
                hit = bvh.ray_cast(Vector((x, y, 2.0)), down)
                if hit[0] is not None: H[i, j] = max(0.0, hit[0].z - GEN[4])
    A = xs < DIV_X; B = xs > 0
    return dict(mean=float(H.mean()), cover=float((H > 0.02).mean()), meanA=float(H[A].mean()), meanB=float(H[B].mean()),
                p90=float(np.percentile(H, 90)))

# ---------- run: copies per stack found per crop ----------
t0 = time.time()
# Every crop's crate is filled until its 8-stack heap surface reaches the onion crate's (Joost: "onions look right"). A crop
# with dropped copies (the crate cannot take that many) or a heap far over the onion's is settled again with fewer.
PASSES = arg("--passes", 10, int)
def acceptable(t):
    """a settled crate is usable when every stack has a copy and at most 12% of the copies found no room (the crate is full:
    the last stacks then hold fewer)."""
    by = [sum(1 for r in t["rs"] if r["stack"] == k) for k in range(8)]
    return min(by) >= 1 and t["dropped"] <= 0.12 * t["n"]
todo = list(CROP.values()); tried = {c["name"]: [] for c in CROP.values()}; sstats = None; TREF = None
# the onion goes first, on its own, until its crate is settled (its fill is the reference for every other crop)
todo = [CROP["Onion"]]
def spread(total, k=NHALF):
    return [total // k + (1 if i < total % k else 0) for i in range(k)]
for c in CROP.values(): c["qa"] = None; c["capA"] = 0; c["acap"] = A_CAP
for p in range(PASSES):
    for c in todo:
        c["crate"] = Crate(c["b"]); c["dropped"] = []; c["rej"] = {}
    r, st = simulate(todo, arg("--seed", 5, int) + 11 * p)
    if sstats is None: sstats = dict(st)
    else:
        for k in ("frames", "tries", "unsettled"): sstats[k] += st[k]
    for c in todo:
        rs = [x for x in r if x["name"] == c["name"]]
        f8 = fill_metric(c["name"], rs); f4 = fill_metric(c["name"], rs, NHALF)
        tried[c["name"]].append(dict(n=c["n"], half=c["half"], qa=c["qa"], acap=c["acap"], rs=rs, f8=f8, f4=f4, dropped=len(c["dropped"]),
                                     dropnotes=list(c["dropped"]), rej=dict(c["rej"]), nk=list(c["nk"]), carried=len(c["carry"]),
                                     top=max(float(x["hi"][2]) for x in rs) - GEN[4] if rs else 0))
    ok_on = [t for t in tried["Onion"] if acceptable(t)]
    TREF = (ok_on or tried["Onion"])[-1]["f8"]["mean"]
    if todo == [CROP["Onion"]] and (ok_on or p >= 2):
        print("R6 PASS", p, "onion reference %.3f" % TREF, flush=True)
        todo = [c for c in CROP.values() if c["name"] != "Onion"]; continue
    nxt = []
    for c in todo:
        t = tried[c["name"]][-1]; n = c["n"]; mean = t["f8"]["mean"]
        done = {(x["n"], x["half"], tuple(x["qa"] or ()), x["acap"]) for x in tried[c["name"]]}
        # half A full (copies moved on, or a stack's first copy found no room there): learn how many it takes
        a_full = c["half"] and (t["carried"] or any(d[0] < NHALF for d in t["dropnotes"]))
        if a_full:
            c["capA"] = max(c["capA"], sum(1 for x in t["rs"] if x["stack"] < NHALF))
            if c["capA"] < NHALF and c["acap"] < HEAP_CAP:
                c["acap"] = HEAP_CAP; c["capA"] = 0; c["qa"] = spread(NHALF)   # a big crop: half A may heap as high as the crown
            elif c["capA"] < NHALF:
                c["half"] = False; c["qa"] = None                # half A cannot take one copy per stack: no half-first
            else:
                c["qa"] = spread(min(c["capA"], math.ceil(n / 2)))
            if (n, c["half"], tuple(c["qa"] or ()), c["acap"]) not in done and not acceptable(t):
                nxt.append(c); continue
        if c["name"] in FIXED: continue
        if not acceptable(t):
            nn = max(8, n - max(1, round(0.08 * n)))
        elif mean > 1.3 * TREF and n > 8:
            nn = max(8, math.floor(n * TREF / mean * 1.1))
        elif t["dropped"]:
            continue                                    # the crate is full: the last stacks took what fitted
        elif mean < 0.95 * TREF and n < c["cap"]:
            nn = min(c["cap"], max(n + 1, math.ceil(n * TREF / max(mean, 1e-3) * 1.03)))
        else:
            continue
        if c["qa"] is not None: c["qa"] = spread(max(NHALF, min(c["capA"] or NHALF, math.ceil(nn / 2))))
        if (nn, c["half"], tuple(c["qa"] or ()), c["acap"]) in done: continue
        c["n"] = nn; nxt.append(c)
    print("R6 PASS", p, "ref onion mean %.3f" % TREF, "results",
          [(c["name"], tried[c["name"]][-1]["n"], tried[c["name"]][-1]["nk"], round(tried[c["name"]][-1]["f8"]["mean"], 3), tried[c["name"]][-1]["dropped"],
            sorted({d[0] for d in tried[c["name"]][-1]["dropnotes"]}), tried[c["name"]][-1]["rej"]) for c in todo],
          "next", [(c["name"], c["n"], c["half"], c["qa"]) for c in nxt], "t=%.0fs" % (time.time() - t0), flush=True)
    todo = nxt
    if not todo: break

def pick(name):
    ts = tried[name]; ok = [t for t in ts if acceptable(t)]
    if not ok: return min(ts, key=lambda t: t["dropped"])
    if name in FIXED: return ok[-1]
    full = [t for t in ok if t["f8"]["mean"] >= 0.95 * TREF]
    if full: return min(full, key=lambda t: (round(t["f8"]["mean"] / TREF, 1), t["n"]))   # the least over-full that looks full
    return max(ok, key=lambda t: t["f8"]["mean"])
CHOSEN = {}
res = []
for name, c in CROP.items():
    t = pick(name); CHOSEN[name] = t; c["n"] = t["n"]; c["nk"] = t["nk"]; c["half"] = t["half"]; c["dropped"] = t["dropped"]; res += t["rs"]
sstats["dropped"] = sum(t["dropped"] for t in CHOSEN.values())
print("R6 SIM done", sstats, "%.0fs" % (time.time() - t0), flush=True)
for name, t in CHOSEN.items():
    print("R6 CHOSEN %-18s nk %s unsettled %d half %s" % (name, t["nk"], sum(1 for r in t["rs"] if r.get("unsettled")), t["half"]))
    print("R6 CHOSEN %-18s n %2d mean8 %.3f (ref %.3f) cover8 %.2f p90 %.3f | at 4: A %.3f B %.3f | top %.3f dropped %d tried %s"
          % (name, t["n"], t["f8"]["mean"], TREF, t["f8"]["cover"], t["f8"]["p90"], t["f4"]["meanA"], t["f4"]["meanB"], t["top"], t["dropped"],
             [(x["n"], round(x["f8"]["mean"], 3), x["dropped"]) for x in tried[name]]), flush=True)
pen, npairs = interpenetration(res)
print("R6 INTERPEN max %.2f mm over %d touching pairs" % (pen * 1000, npairs), flush=True)
fl = float_check(res)
n_over = sum(1 for o in fl if o[0] > FLOAT_MAX)
print("R6 FLOAT worst 5 (mm):", [(round(o[0] * 1000, 2), o[1], o[2], "stack %d copy %d" % (o[3], o[4])) for o in fl[:5]], "over 5 mm:", n_over, "of", len(fl), flush=True)
rng.seed(7); PARTS.clear(); build_frame()
ntris = sum(len(p.vertices) - 2 for o in PARTS for p in o.data.polygons)
print("R6 frame tris", ntris, "(round 5 file:", R5DOC["stats"]["frame_tris"], ")", flush=True)
nclip, clipnotes = clip_check(res)
# a split crate: half A's stacks (0..3) never reach over the divider line, in the generic cavity (drawn vertices)
over_div = 0
for r in res:
    if r["stack"] >= NHALF or not CROP[r["name"]]["half"]: continue
    m = merged(r["name"]); V = world_pts(m["verts"][m["drawn"]], local_M(r))
    if (V[:, 0] + (V[:, 2] - GEN[4]) * DIV_K > DIV_X + 0.0015).any(): over_div += 1
print("R6 HALF copies over the divider line:", over_div, "| crops not half-first:", [n for n, c in CROP.items() if not c["half"]], flush=True)
TRIS = {n: sum(1 for r in res if r["name"] == n) * merged(n)["dtris"] for n in CROP}
worst = max(TRIS, key=TRIS.get)
print("R6 TRIS per full crate", TRIS, "worst", worst, "full store of it: items %d + frame %d = %d" % (9 * TRIS[worst], ntris, 9 * TRIS[worst] + ntris), flush=True)

# ---------- export ----------
MC = Matrix(((-1, 0, 0), (0, 0, 1), (0, -1, 0)))
def uvec(v): return [round(-v[0], 4), round(v[2], 4), round(-v[1], 4)]
def uquat(Rb):
    q = (MC @ Rb @ MC.transposed()).to_quaternion(); q.normalize()
    if q.w < 0: q = -q
    return [round(c, 5) for c in (q.x, q.y, q.z, q.w)]

layouts = {}
for name, c in CROP.items():
    rs = [r for r in res if r["name"] == name]
    m = merged(name); t = CHOSEN[name]
    stacks = []
    for sidx in range(8):
        cps = []
        for r in sorted([r for r in rs if r["stack"] == sidx], key=lambda r: r["k"]):
            M = local_M(r); Rw = Matrix((M[:3, :3] / r["s"]).tolist())
            cps.append({"offset": uvec(M[:3, 3]), "rot_quat_xyzw": uquat(Rw)})
        stacks.append(cps)
    gaps = [o[0] for o in fl if o[2] == name]
    tops = [float(world_pts(m["verts"][m["drawn"]], local_M(r))[:, 2].max()) for r in rs]
    sz = m["size"]
    ent = {"scale": round(c["s"], 4), "true_size_m": [round(float(sz[0]), 4), round(float(sz[2]), 4), round(float(sz[1]), 4)],
           "mode": c["mode"], "copies_per_stack": round(sum(len(x) for x in stacks) / 8, 2), "copies_by_stack": [len(x) for x in stacks], "stacks": stacks,
           "check": {"copies": len(rs), "dropped": c["dropped"], "float_worst_mm": round(1000 * max(gaps), 2) if gaps else 0,
                     "clipping_in_9_crates": len(clipnotes.get(name, [])), "heap_top_m": round(max(tops), 3) if tops else 0,
                     "fill_mean_m": round(t["f8"]["mean"], 3), "fill_cover": round(t["f8"]["cover"], 3),
                     "fill_at_4_stacks_half_a_m": round(t["f4"]["meanA"], 3), "fill_at_4_stacks_half_b_m": round(t["f4"]["meanB"], 3),
                     "half_first": c["half"], "drawn_tris_per_copy": m["dtris"], "tris_full_crate": TRIS[name]}}
    if name == "_generic":
        ent["scale"] = None; ent["fit_longest_m"] = round(float(sz.max()), 4); ent["true_size_m"] = None
        ent["note"] = "fallback for unknown (modded) crops and the eggs: settled with a neutral round lump of this longest side; scale the item uniformly so its longest bounds side is fit_longest_m."
    layouts[name] = ent

doc = copy.deepcopy(R5DOC)
doc["round"] = 6
doc["crop_layouts"] = layouts
doc["crop_layouts_doc"] = (
    "crop_layouts: one physics-settled full crate per crop (item prefab name; '_generic' for any other item, the eggs included). A crate "
    "holding n stacks of an item shows stacks[0..n-1] of that item's layout (all of a stack's copies), so filling never moves earlier "
    "copies (stack k was dropped onto stacks 0..k-1 after they were frozen). Round 6: stacks 0..3 lie in the crate's +x half (Unity; "
    "the mod's left), all drawn vertices at least 4 cm off the middle (a divider leaning back 15 degrees), stacks 4..7 fill the -x half "
    "and crown the heap. Per copy: start from the item's model in the mod's item space (ItemVisual: prefab root space without the "
    "root's own scale, turned 180 degrees about up, exactly as round 4), scale it uniformly by 'scale' (= x the item's true size; round "
    "5's scales; RootScale NOT applied), rotate it by rot_quat_xyzw about its bounds centre (the WHOLE item's bounds, greens included), "
    "and put that bounds centre at crate_floor_centres[crate] + offset (prefab space, Unity y-up/+z front; offset is crate-floor-centre "
    "local, the store's unit rotation is identity). Carrot and Turnip were settled and checked without their greens (the mod draws them "
    "Topless); their greens may overlap anything. The layouts were settled in one generic cavity (0.53 wide x 0.45 deep x 0.424 high "
    "above the floor centre, the lowest common crate) and checked in all nine crates. '_generic' has scale null: scale the item so its "
    "longest bounds side is fit_longest_m. Per crop also: true_size_m (bounds at scale 1, Unity x,y,z), mode (long = lying; round = up "
    "to 40 degrees tilt; tumble = any; flat), copies_per_stack, check (copies, dropped, float_worst_mm, clipping_in_9_crates, heap_top_m "
    "above the floor centre, fill_mean_m = mean heap surface over the crate floor by rays from above onto the drawn copies, fill_cover, "
    "the same per half at 4 stacks, half_first, drawn_tris_per_copy, tris_full_crate). crate_floor_centres = crates[].floor_centre, by "
    "crate index. units[] (round 4, per-crate example items) are kept for the current mod.")
doc["crop_layouts_scale_exceptions"] = {
    "rule": ("round 5's scale per crop, except (1) a lying crop too long to lie front to back in half A (stacks 0..3): lowered in 1% steps, at most "
             "15%, until it does; (2) Jotun puffs: 13% smaller, because a full crate held only 8-10 at round 5's scale (no room to reach the rim). "
             "Thistle keeps round 5's scale and is not half-first (it cannot lie in half A even 15% smaller)."),
    "reduced": {n: v[1] for n, v in SCALE_HALF.items()}, "from_round_5": {n: v[0] for n, v in SCALE_HALF.items()}}
for k in ("physics_r5", "stats_r5"): doc.pop(k, None)
doc["physics_r6"] = ("Blender rigid body (Bullet), round 5's settings: items = active convex hulls (carrot, turnip: the root alone; barley, flax, thistle, dandelion, "
                     "fiddlehead: a core, the hull pulled in %s towards the long axis or the centre, so stalks and leaves interleave), friction 0.8, restitution 0, "
                     "damping %.2f/%.2f, margin %.1f mm, substeps 20, iterations 40; up to 4 copies of a crop per batch at separate spots, settled then frozen; "
                     "stacks 0..3 behind a virtual divider in half A, stacks 4..7 after it is removed. A try is re-dropped when a body is farther than %.0f mm "
                     "from a support frozen before it, a drawn vertex leaves the cavity or crosses the divider (leaves may sink %.0f mm into the floor, core "
                     "crops %.0f mm). Copies per stack: raised until the 8-stack heap surface reaches the onion crate's (%.3f m mean), capped at %d item "
                     "triangles per crate." % (CORE, DAMP_L, DAMP_A, MARGIN * 1000, FLOAT_MAX * 1000, LEAF_FLOOR * 1000, CORE_FLOOR * 1000, TREF, TRI_BUDGET_CRATE))
doc["stats_r6"] = {"crops": len(CROP), "copies_total": len(res), "dropped_copies": sstats["dropped"], "clipping": nclip,
                   "float_over_5mm": n_over, "float_worst_mm": round(fl[0][0] * 1000, 2) if fl else 0,
                   "max_interpenetration_mm": round(pen * 1000, 2), "half_copies_over_divider": over_div, "fill_reference_onion_m": round(TREF, 3),
                   "worst_crop": worst, "tris_full_store_worst": 9 * TRIS[worst] + ntris, "frame_tris": ntris,
                   "sim_frames": sstats["frames"], "unsettled_bodies": sstats["unsettled"]}
print("R6 STATS", doc["stats_r6"], flush=True)
for n, e in layouts.items(): print("R6 LAYOUT %-18s scale %s copies %s %s" % (n, e["scale"], e["copies_per_stack"], e["check"]), flush=True)

# ---------- renders ----------
RENDER = "--no-render" not in argv
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
    shown = []
    def put(mesh, ci, M):
        io = bpy.data.objects.new(mesh.name, mesh); sc.collection.objects.link(io)
        io.matrix_world = Matrix.Translation(Vector(floor_centre(ci))) @ Matrix(M.tolist()); shown.append(io)
    def show(name, ci, nstacks=8):
        for r in res:
            if r["name"] == name and r["stack"] < nstacks: put(merged(name)["mesh"], ci, local_M(r))
    def show_r5(name, ci):
        """round 5's layout of a crop as the mod draws it today (carrot/turnip without greens)."""
        lay = R5LAY[name]; s5 = lay["scale"]
        for st5 in lay["stacks"]:
            for cp in st5:
                ux, uy, uz = cp["offset"]; qx, qy, qz, qw = cp["rot_quat_xyzw"]
                Ru = Quaternion((qw, qx, qy, qz)).to_matrix()
                Rb = MC.transposed() @ Ru @ MC
                M = np.array(Matrix.Translation(Vector((-ux, -uz, uy))) @ Rb.to_4x4() @ Matrix.Diagonal((s5, s5, s5, 1)))
                put(merged(name)["mesh"], ci, M)
    def clear():
        for o in shown: bpy.data.objects.remove(o)
        shown.clear()
    def render(fn):
        sc.render.filepath = fn; bpy.ops.render.render(write_still=True); return fn
    def sheet(tiles, out, cols=5, W=560, H=420):
        code = ("import sys,json;from PIL import Image,ImageDraw\n"
                "t=json.loads(sys.argv[1]);out=sys.argv[2];cols=int(sys.argv[3]);W,H=int(sys.argv[4]),int(sys.argv[5]);rows=(len(t)+cols-1)//cols\n"
                "S=Image.new('RGB',(cols*W,rows*H),(30,30,30));d=ImageDraw.Draw(S)\n"
                "for i,(f,l) in enumerate(t):\n"
                " x,y=(i%cols)*W,(i//cols)*H;S.paste(Image.open(f).convert('RGB').resize((W,H)),(x,y));d.rectangle((x,y,x+W,y+22),fill=(0,0,0));d.text((x+6,y+5),l,fill=(255,255,255))\n"
                "S.save(out)\n")
        subprocess.run(["python", "-c", code, json.dumps(tiles), out, str(cols), str(W), str(H)], check=False)
    os.makedirs(os.path.join(OUT, "tiles"), exist_ok=True)
    sc.render.resolution_x, sc.render.resolution_y = 560, 420
    fc = floor_centre(4)
    TILE = (-8, 50, 1.05, (fc[0], fc[1] + 0.02, fc[2] + 0.10))
    full, half = [], []
    for name in CROP:
        lab = "%s  x%s  %d copies (%s/stack)  fill %.0f%% of onion" % (name, layouts[name]["scale"] if layouts[name]["scale"] is not None else "fit 0.12m",
                                                      layouts[name]["check"]["copies"], layouts[name]["copies_per_stack"], 100 * CHOSEN[name]["f8"]["mean"] / TREF)
        clear(); show(name, 4); look(*TILE); full.append((render(os.path.join(OUT, "tiles", f"full-{name}.png")), lab))
        clear(); show(name, 4, NHALF); look(*TILE); half.append((render(os.path.join(OUT, "tiles", f"half-{name}.png")), name + "  4 of 8 stacks"))
    clear()
    sheet(full, os.path.join(OUT, "rootbin6-crops-full.png"))
    sheet(half, os.path.join(OUT, "rootbin6-crops-4stacks.png"))
    # r5 vs r6 carrots, same crate, same camera
    if "Carrot" in CROP and "Carrot" in R5LAY:
        clear(); show_r5("Carrot", 4); look(*TILE); a5 = render(os.path.join(OUT, "tiles", "carrot-r5.png"))
        clear(); show("Carrot", 4); look(*TILE); a6 = render(os.path.join(OUT, "tiles", "carrot-r6.png"))
        clear()
        sheet([(a5, "round 5: Carrot x%s, 1 per stack (8 in a full crate), drawn without greens" % R5LAY["Carrot"]["scale"]),
               (a6, "round 6: Carrot x%s, %s per stack (%d in a full crate)" % (layouts["Carrot"]["scale"], layouts["Carrot"]["copies_per_stack"], layouts["Carrot"]["check"]["copies"]))],
              os.path.join(OUT, "rootbin6-carrots-r5-vs-r6.png"), cols=2, W=840, H=630)
    # the whole store full, a mixed fill, from a standing three-quarter view (eye 1.7 m)
    MIX = ["Turnip", "Carrot", "Onion", "Barley", "Raspberry", "Mushroom", "Flax", "Blueberries", "Dandelion"]
    for ci, name in enumerate(MIX):
        if name in CROP: show(name, ci)
    sc.render.resolution_x, sc.render.resolution_y = 1600, 1000
    look(-35, math.degrees(math.asin(0.7 / 4.2)), 4.2, (0, 0.1, 1.0)); render(os.path.join(OUT, "rootbin6-store-mix-standing.png"))
    look(-10, 48, 3.4, (0, 0, 0.85)); render(os.path.join(OUT, "rootbin6-store-mix-top.png"))
    clear()

# ---------- assets: frame + atlas copied from round 5 (byte-identical), then the json (temp file + rename) last ----------
if "--crops" not in argv:
    os.makedirs(OUTA, exist_ok=True)
    for f in ("RootBin.obj", "rootbin_atlas.png"):
        shutil.copyfile(os.path.join(R5, f), os.path.join(OUTA, f))
    out = os.path.join(OUTA, "rootbin_anchors.json"); tmp = out + ".tmp"
    with open(tmp, "w") as fh: json.dump(doc, fh, indent=1)
    os.replace(tmp, out)
    print("R6 wrote", out, flush=True)
else:
    json.dump(doc, open(os.path.join(OUT, "rootbin_anchors_partial.json"), "w"), indent=1)
print("DONE")
