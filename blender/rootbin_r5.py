"""Root Bin, round 5: physics-settled heaps PER CROP.

The mod puts one item TYPE per crate (whatever the player stores), so a crate's layout must belong to the crop, not to the
crate. Round 4 settled every crate with one specific crop at a per-crate size; raspberries landing in the carrot crate got
carrot positions and sizes (tiny and lined up). Round 5 settles, for EACH crop, one full crate (8 stacks, a handful of copies
per stack) in a generic crate cavity at ONE scale, 0.55 x the item's true size (the extracted model at scale 1), with the
round-4 method: rigid body (Bullet), collision = convex hull of the item BODY (alpha-clipped leaf material excluded, leaves
ride along), every copy frozen after it settles, stacks dropped in fill order (stack k onto stacks 0..k-1), a try re-dropped
when a body floats more than 5 mm above its support or any vertex (leaves included) leaves the cavity.
Exceptions to 0.55: a lying item too long for the 0.53 m crate (with 8 degrees of yaw play), an upright one too tall for the
0.424 m ceiling, and a crop whose full crate does not fit (it is settled again on its own at 6% less scale until it does).

The frame and atlas are round 4's (copied); the 72 units of round 4 are kept so the current mod still loads the file.
Output: assets/rootbin_r5/{RootBin.obj, rootbin_atlas.png, rootbin_anchors.json (+ crop_layouts)}; the json is written last
(temp file + rename) because the mod live-reloads model files.
Run: blender -b -P rootbin_r5.py -- [--out DIR] [--crops Carrot,Raspberry] [--probe] [--no-render]
"""
import bpy, bmesh, sys, os, math, json, random, time, shutil, subprocess, copy
import numpy as np
from mathutils import Vector, Matrix, Euler, Quaternion
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
R4 = os.path.normpath(os.path.join(HERE, "..", "assets", "rootbin_r4"))
OUTA = os.path.normpath(os.path.join(HERE, "..", "assets", "rootbin_r5"))
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
SCR = "C:/Users/joost/AppData/Local/Temp/claude/C--Users-joost--pai/5e4bc60b-cdfe-4638-8e29-2e507fa13cf9/scratchpad/rootbin5"
OUT = argv[argv.index("--out") + 1] if "--out" in argv else SCR
ITEMS = "C:/Users/joost/ValheimRip/items"
sys.path.append(ITEMS)
from load_item import load_item
os.makedirs(OUTA, exist_ok=True); os.makedirs(OUT, exist_ok=True)
def arg(name, default, typ=float): return typ(argv[argv.index(name) + 1]) if name in argv else default

# ---------- crops ----------
SCALE = 0.55
# name: (mode, copies per stack). mode: long = lies with its longest axis across the crate, any roll; round = tilted up to
# TILT degrees; tumble = any orientation; flat = seed bag, nearly flat.
CROPS = {
    "Carrot": ("long", 1), "Turnip": ("upright", 1), "Onion": ("round", 2), "Barley": ("long", 1), "Flax": ("long", 1),
    "Mushroom": ("round", 1), "MushroomYellow": ("round", 2), "MushroomBlue": ("round", 2),
    "MushroomJotunPuffs": ("long", 1), "MushroomMagecap": ("long", 2),
    "Raspberry": ("tumble", 4), "Blueberries": ("tumble", 2), "Cloudberry": ("tumble", 3),
    "Thistle": ("long", 1), "Dandelion": ("long", 1), "Fiddleheadfern": ("round", 1),
    "CarrotSeeds": ("flat", 2), "TurnipSeeds": ("flat", 2), "OnionSeeds": ("flat", 2),
    "_generic": ("tumble", 5),
}
TILT = {"round": 40, "flat": 14, "upright": 12}
# hand-set start scales (none: the automatic retries find them)
SCALE_OVERRIDE = {}
LEAF_R = 0.65
for spec in [a for a in argv if a.startswith("--n:")]:          # --n:Carrot=4 overrides copies per stack
    k, v = spec[4:].split("="); CROPS[k] = (CROPS[k][0], int(v))
WANT = argv[argv.index("--crops") + 1].split(",") if "--crops" in argv else list(CROPS)
NAMES = [n for n in CROPS if n in WANT and (n == "_generic" or os.path.exists(f"{ITEMS}/{n}/info.json"))]
print("R5 crops", NAMES, "missing", [n for n in CROPS if n in WANT and n not in NAMES], flush=True)

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
# stack targets (crate-floor-centre local, Blender): back row first (visible over the empty front), then front; layer 2 same
QUAD = [(-0.1325, 0.1125), (0.1325, 0.1125), (-0.1325, -0.1125), (0.1325, -0.1125)]
STACK_XY = QUAD + QUAD

# ---------- scene ----------
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
atlas = bpy.data.images.load(os.path.join(R4, "rootbin_atlas.png"))
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
    bv = verts[sorted(body_v)]
    cb = (bv.min(0) + bv.max(0)) / 2
    cpts = bv
    if leaf_only and CROPS.get(item, ("",))[0] == "long":
        # a lying leafy crop (carrot, turnip) rests partly on its leaves: they join the collision hull pulled LEAF_R of the way
        # in towards the long axis, so the rest sinks into the straw at most a few cm instead of a decimetre
        ax = int(np.argmax(t["size"])); q = verts[sorted(leaf_only)] - cb
        perp = np.ones(3, bool); perp[ax] = False
        q[:, perp] *= LEAF_R
        cpts = np.vstack([bv, cb + q])
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
    MERGED[item] = dict(mesh=me, verts=verts, leafmask=leafmask, cb=cb, hullV=hv, hullF=F, hullN=np.array(N), hullD=np.array(D),
                        hullE=edges, prox=pm, size=np.array(t["size"]), vol=abs(vol), bodysize=bv.max(0) - bv.min(0))
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
for i, name in enumerate(NAMES):
    mode, n = CROPS[name]
    m = merged(name)
    size = m["size"]
    s = 1.0 if name == "_generic" else SCALE
    L = float(size.max()) * s
    if mode == "long":                 # the largest scale that still lies across the crate with 8 degrees of yaw play
        srt = np.sort(size)
        s = min(s, (plan_room() - 0.004) / (srt[2] * math.cos(math.radians(8)) + srt[1] * math.sin(math.radians(8))))
    if mode in ("round", "tumble", "flat", "upright") and float(size.max()) * s > GEN[5] - GEN[4] - 0.03:
        s = (GEN[5] - GEN[4] - 0.03) / float(size.max())
    if name in SCALE_OVERRIDE: s = min(s, SCALE_OVERRIDE[name])
    ymax = 0.0
    if mode == "long":
        Ls = float(size.max()) * s; Ws = float(np.sort(size)[1]) * s          # cross section ~ the middle side (any roll)
        for a in np.arange(0, 40.01, 0.5):
            if Ls * math.cos(math.radians(a)) + Ws * math.sin(math.radians(a)) <= plan_room(): ymax = float(a)
    b = (i * SIM_DX + GEN[0], i * SIM_DX + GEN[1], GEN[2], GEN[3], GEN[4], GEN[5])
    CROP[name] = dict(i=i, name=name, mode=mode, n=n, s=s, ymax=ymax, b=b, origin=np.array((i * SIM_DX, 0.0, 0.0)), crate=Crate(b))
    vs = m["vol"] * s ** 3
    sugg = 0.30 * (GEN[1] - GEN[0]) * (GEN[3] - GEN[2]) * (GEN[5] - GEN[4]) / (8 * vs)
    print("R5 crop %-18s mode %-6s scale %.3f size@s %s body@s %s hullvol@s %.5f m3 copies/stack %d (fill-30%% suggests %.1f) yaw +-%.1f leaf-only verts %d"
          % (name, mode, s, np.round(size * s, 3), np.round(m["bodysize"] * s, 3), vs, n, sugg, ymax, int(m["leafmask"].sum())), flush=True)
if "--probe" in argv:
    print("DONE probe"); sys.exit(0)

# ---------- simulation (round 4's method, generic cavities side by side, one per crop) ----------
MAXF = arg("--maxf", 140); MINF = 16
VW = arg("--vw", 0.2)
DAMP_L = 0.5; DAMP_A = 0.95
NTRY = arg("--ntry", 30, int)
MARGIN = 0.0015
LEAF_FLOOR = 0.06
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
    inset = 0.002; T = 0.03
    for c in crops:
        x0, x1, y0, y1, z0, z1 = c["b"]; H = z1 - z0 + 0.06
        add_box((x0 - T, y0 - T, z0 - 0.1), (x1 + T, y1 + T, z0))
        add_box((x0 - T, y0 - T, z0 - 0.1), (x0 + inset, y1 + T, z0 + H))
        add_box((x1 - inset, y0 - T, z0 - 0.1), (x1 + T, y1 + T, z0 + H))
        add_box((x0 - T, y0 - T, z0 - 0.1), (x1 + T, y0 + inset, z0 + H))
        add_box((x0 - T, y1 - inset, z0 - 0.1), (x1 + T, y1 + T, z0 + H))
    st = dict(frames=0, drops=0, tries=0, rej=dict(), unsettled=0)
    allr = []
    PROBE = np.array([[1, 0, 0], [-1, 0, 0], [0, 1, 0], [0, -1, 0], [0, 0, 1], [0, 0, -1]], float)

    def spawn(w):
        c, k = w["c"], w["k"]; cr = c["crate"]; m = merged(c["name"]); s = c["s"]; w["s"] = s
        if c["mode"] == "long":
            yaw = rr.uniform(-c["ymax"], c["ymax"]) + (180 if (k + w["stack"]) % 2 else 0)
            Rc = Rz(yaw) @ Ry(rr.uniform(-6, 6)) @ Rx(rr.uniform(0, 360)) @ align_matrix(m["size"])
        elif c["mode"] == "tumble":
            Rc = rand_rot(rr)
        else:
            t = TILT[c["mode"]]
            Rc = Rz(rr.uniform(0, 360)) @ Rx(rr.uniform(-t, t)) @ Ry(rr.uniform(-t, t))
        Rn = np.array(Rc)
        HV = (m["hullV"] @ Rn.T) * s
        AV = ((m["verts"] - m["cb"]) @ Rn.T) * s
        lo, hi = AV.min(0), AV.max(0)
        low = -HV[:, 2].min()
        x0, x1, y0, y1, z0, z1 = cr.b; mg = SPAWN_MG
        ex = w.setdefault("extra", np.zeros(5))
        xr = (x0 - lo[0] + mg + ex[0], x1 - hi[0] - mg - ex[1]); yr = (y0 - lo[1] + mg + ex[2], y1 - hi[1] - mg - ex[3])
        if xr[0] > xr[1] or yr[0] > yr[1]: return False, "plan"
        ux, uy = c["origin"][0] + STACK_XY[w["stack"]][0], STACK_XY[w["stack"]][1]
        # the item's own lower surface, sampled on the crate's cell grid (offsets from the centre): a drop spot's height is
        # the highest (heap top - item bottom) over the cells the item covers, so a long item settles INTO a heap's hollows
        # instead of being held above the heap's highest point anywhere under its footprint
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
        def drop_z(i, j):
            ii = i + KXo; jj = j + KYo
            v = (ii >= 0) & (ii < cr.nx) & (jj >= 0) & (jj < cr.ny)
            return float((cr.hf[ii[v], jj[v]] - ZB[v]).max()) if v.any() else z0 + low
        best = None
        for i in icand:
            for j in jcand:
                xx = min(max(x0 + (i + 0.5) * CELL, xr[0]), xr[1]); yy = min(max(y0 + (j + 0.5) * CELL, yr[0]), yr[1])
                zc = max(drop_z(i, j), z0 + low) + clear
                if zc + hi[2] > z1 + SPAWN_OVER - ex[4]: continue
                cost = zc + VW * math.hypot(xx - ux, yy - uy) + rr.uniform(0, 0.006)
                if best is None or cost < best[0]: best = (cost, xx, yy, zc)
        if best is None:
            if DEBUG:
                zs = [max(drop_z(i, j), z0 + low) + clear for i in icand for j in jcand]
                print("R5 dbg ceiling", c["name"], "min drop zc %.3f low %.3f hi %.3f z1 %.3f ex %s ncand %d hfmax %.3f ZBmin %.3f" % (min(zs), low, hi[2], z1, np.round(ex, 3), len(zs), cr.hf.max(), ZB.min()), flush=True)
            return False, "ceiling"
        x, y, zc = best[1], best[2], best[3]
        ob = bpy.data.objects.new(c["name"], m["prox"]); sc.collection.objects.link(ob)
        ob.matrix_world = pose_matrix((x, y, zc), Rc, s)
        ext = HV.max(0) - HV.min(0)
        rb = set_rb(ob, "ACTIVE", max(0.02, float(np.prod(ext)) * 600))
        rb.collision_shape = "CONVEX_HULL"; rb.mesh_source = "BASE"; rb.use_margin = True; rb.collision_margin = MARGIN
        w.update(ob=ob, m=m, probe=PROBE * 0.5 * ext)
        return True, ""

    def evaluate(w):
        m = w["m"]; c = w["c"]; cr = c["crate"]
        r = rec_world(m, w["Mp"], w["s"])
        r.update(name=c["name"], stack=w["stack"], k=w["k"], s=w["s"], id=w["id"])
        V = world_pts(m["verts"], r["M"]); lm = m["leafmask"]
        x0, x1, y0, y1, z0, z1 = cr.b; e = 0.0005
        bad = []
        if (V[~lm][:, 2] < z0 - 0.002).any(): bad.append("body below floor")
        if lm.any() and (V[lm][:, 2] < z0 - LEAF_FLOOR).any(): bad.append("leaf deep in floor")
        if DEBUG and bad: print("R5 dbg", c["name"], bad, "body zmin %.3f leaf zmin %.3f z0 %.3f" % (V[~lm][:, 2].min() - z0, (V[lm][:, 2].min() - z0) if lm.any() else 0, z0),
                                "x %.3f..%.3f (cav %.3f..%.3f) top %.3f" % (V[:, 0].min(), V[:, 0].max(), x0, x1, V[:, 2].max()), flush=True)
        walls = (V[:, 0].min() < x0 + e) or (V[:, 0].max() > x1 - e) or (V[:, 1].min() < y0 + e) or (V[:, 1].max() > y1 - e)
        if walls: bad.append("outside walls")
        ceil = V[:, 2].max() > z1 - e
        if ceil: bad.append("above ceiling")
        if walls or ceil:
            w["extra"] = w.get("extra", np.zeros(5)) + np.maximum(0, [x0 - V[:, 0].min() + 0.003, V[:, 0].max() - x1 + 0.003,
                y0 - V[:, 1].min() + 0.003, V[:, 1].max() - y1 + 0.003, V[:, 2].max() - z1 + 0.003]) * np.array([walls] * 4 + [ceil], float)
            w["extra"] = np.minimum(w["extra"], 0.04)        # an item that tipped up must not close the crate for the next tries
        gap, what = support_gap(r, z0, cr.bodies)
        r["gap"] = gap; r["support"] = what
        if gap > FLOAT_MAX: bad.append("floats %.1f mm" % (gap * 1000))
        return (not bad), ",".join(bad), r

    def freeze_into_world(r, ob, c):
        sc.frame_set(1)
        ob.matrix_world = Matrix(r["Mp"].tolist()); ob.rigid_body.type = "PASSIVE"
        ob.rigid_body.use_margin = True; ob.rigid_body.collision_margin = MARGIN
        c["crate"].bodies.append(r)
        c["crate"].add_hull(r["N"], r["D"], r["lo"], r["hi"])

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
                    r["unsettled"] = f >= MAXF + 1; accepted.append((w, r))
                else:
                    key = "".join(ch for ch in why.split(",")[0] if not (ch.isdigit() or ch == ".")).strip(" ")
                    w["why"] = why; st["rej"][key] = st["rej"].get(key, 0) + 1
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
        if pending: print("R5 dropped", [(w["c"]["name"], w["stack"], w["k"], w.get("why")) for w in pending], flush=True)

    uid = 0; tstart = time.time()
    for stack in range(8):
        nmax = max(c["n"] for c in crops)
        for k in range(nmax):
            batch = []
            for c in crops:
                if k < c["n"]: batch.append(dict(c=c, stack=stack, k=k, id=uid)); uid += 1
            run_batch(batch)
        print("R5 stack", stack, "bodies", len(allr), "frames", st["frames"], "tries", st["tries"], "dropped", st["drops"],
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
        m = merged(r["name"]); lm = m["leafmask"]
        Vl = world_pts(m["verts"], local_M(r))
        for ci in range(9):
            V = Vl + floor_centre(ci)
            cx0, cx1, cy0, cy1, cz0, cz1 = cav(ci); why = None
            zlim = np.where(lm, cz0 - LEAF_FLOOR, cz0 - 0.002)
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
    print("R5 CLIPPING", n, {k: len(v) for k, v in bad.items()}, [v[:2] for v in bad.values()][:4], "max outside %.4f" % maxout, flush=True)
    return n, bad

# ---------- run ----------
t0 = time.time()
# pass 1 settles every crop; a crop that could not place all its copies (a full crate does not fit) is settled again on its own
# at 6% less scale, until it fits (crates are independent, so a re-run never touches the other crops)
todo = list(CROP.values()); res = []; sstats = None; history = {}
for p in range(8):
    for c in todo:
        c["crate"] = Crate(c["b"]); c["dropped"] = []
    r, st = simulate(todo, arg("--seed", 5, int) + p)
    if sstats is None: sstats = st
    else:
        for k in ("frames", "tries", "unsettled"): sstats[k] += st[k]
    bad = [c for c in todo if c["dropped"]]; badn = {c["name"] for c in bad}
    res += [x for x in r if x["name"] not in badn]
    print("R5 PASS", p, "settled", [c["name"] for c in todo if c["name"] not in badn], "retry", [(c["name"], round(c["s"], 3), len(c["dropped"])) for c in bad], flush=True)
    for c in bad:
        history.setdefault(c["name"], []).append(round(c["s"], 4)); c["s"] *= 0.94
    todo = bad
    if not todo: break
sstats["dropped"] = sum(len(c["dropped"]) for c in todo)
for c in todo: res += [x for x in r if x["name"] == c["name"]]
for c in CROP.values():
    used = [x["s"] for x in res if x["name"] == c["name"]]
    if used: c["s"] = used[0]
print("R5 scale retries", history, flush=True)
print("R5 SIM done", sstats, "%.0fs" % (time.time() - t0), flush=True)
pen, npairs = interpenetration(res)
print("R5 INTERPEN max %.2f mm over %d touching pairs" % (pen * 1000, npairs), flush=True)
fl = float_check(res)
n_over = sum(1 for o in fl if o[0] > FLOAT_MAX)
print("R5 FLOAT worst 5 (mm):", [(round(o[0] * 1000, 2), o[1], o[2], "stack %d copy %d" % (o[3], o[4])) for o in fl[:5]], "over 5 mm:", n_over, "of", len(fl), flush=True)
rng.seed(7); PARTS.clear(); build_frame()
ntris = sum(len(p.vertices) - 2 for o in PARTS for p in o.data.polygons)
r4doc = json.load(open(os.path.join(R4, "rootbin_anchors.json")))
print("R5 frame tris", ntris, "(round 4:", r4doc["stats"]["frame_tris"], ")", flush=True)
nclip, clipnotes = clip_check(res)

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
    m = merged(name)
    stacks = []
    for sidx in range(8):
        cps = []
        for r in sorted([r for r in rs if r["stack"] == sidx], key=lambda r: r["k"]):
            M = local_M(r); Rw = Matrix((M[:3, :3] / r["s"]).tolist())
            cps.append({"offset": uvec(M[:3, 3]), "rot_quat_xyzw": uquat(Rw)})
        stacks.append(cps)
    gaps = [o[0] for o in fl if o[2] == name]
    tops = [float(world_pts(m["verts"], local_M(r))[:, 2].max()) for r in rs]
    sz = m["size"]
    ent = {"scale": round(c["s"], 4), "true_size_m": [round(float(sz[0]), 4), round(float(sz[2]), 4), round(float(sz[1]), 4)],
           "mode": c["mode"], "copies_per_stack": c["n"], "stacks": stacks,
           "check": {"copies": len(rs), "dropped": len(c.get("dropped", [])), "float_worst_mm": round(1000 * max(gaps), 2) if gaps else 0,
                     "clipping_in_9_crates": len(clipnotes.get(name, [])), "heap_top_m": round(max(tops), 3) if tops else 0}}
    if name == "_generic":
        ent["scale"] = None; ent["fit_longest_m"] = round(float(sz.max()), 4); ent["true_size_m"] = None
        ent["note"] = "fallback for unknown (modded) crops: settled with a neutral round lump of this longest side; scale the item uniformly so its longest bounds side is fit_longest_m."
    layouts[name] = ent

doc = copy.deepcopy(r4doc)
doc["round"] = 5
doc["crop_layouts"] = layouts
doc["crate_floor_centres"] = [c["floor_centre"] for c in r4doc["crates"]]
doc["crop_layouts_doc"] = (
    "crop_layouts: one physics-settled full crate per crop (item prefab name; '_generic' for any other item). A crate holding n stacks "
    "of an item shows stacks[0..n-1] of that item's layout (all of a stack's copies), so filling never moves earlier copies "
    "(stack k was dropped onto stacks 0..k-1 after they were frozen). Per copy: start from the item's model in the mod's item "
    "space (ItemVisual: prefab root space without the root's own scale, turned 180 degrees about up, exactly as round 4), scale it "
    "uniformly by 'scale' (= x the item's true size; 0.55 for all crops, less only where noted below; RootScale NOT applied), rotate it "
    "by rot_quat_xyzw about its bounds centre, and put that bounds centre at crate_floor_centres[crate] + offset (prefab space, Unity "
    "y-up/+z front; offset is crate-floor-centre local, the store's unit rotation is identity). Same as round 4's copies with anchor "
    "'center', align 'up', no fit (Place: pos = centre - r * (s * Bounds.center)). The layouts were settled in one generic cavity "
    "(0.53 wide x 0.45 deep x 0.424 high above the floor centre, the lowest common crate) and checked in all nine crates. "
    "'_generic' has scale null: scale the item so its longest bounds side is fit_longest_m. "
    "Per crop also: true_size_m (bounds at scale 1, Unity x,y,z), mode (long = lying across the crate; upright; round = up to 40 degrees tilt; tumble = any; flat), "
    "copies_per_stack, check (copies, dropped, float_worst_mm, clipping_in_9_crates, heap_top_m above the floor centre). "
    "crate_floor_centres = crates[].floor_centre, by crate index. units[] (round 4, per-crate example items) are kept for the current mod.")
reduced = {n: round(c["s"], 4) for n, c in CROP.items() if n != "_generic" and abs(c["s"] - SCALE) > 1e-6}
doc["crop_layouts_scale_exceptions"] = {
    "rule": ("scale 0.55 x true size for every crop, except: (1) a lying (long) crop gets the largest scale that lies across the 0.53 m crate "
             "with 8 degrees of yaw play; an upright crop (turnip: its leaves stand up) the largest that stands under the 0.424 m ceiling; "
             "(2) a crop whose full crate (8 stacks x copies_per_stack) did not fit was settled again at 6%% less scale until it did."),
    "reduced": reduced, "failed_scales": history}
doc["physics_r5"] = ("Blender rigid body (Bullet), round 4's settings: items = active convex hulls of the item BODY (alpha-clipped leaf material excluded "
                     "when the item also has an opaque material), friction 0.8, restitution 0, damping %.2f/%.2f, margin %.1f mm, substeps 20, iterations 40; one copy per crop "
                     "per batch, settled then frozen; stack order: back-left, back-right, front-left, front-right, then the same again on top. A try is re-dropped "
                     "when a body is farther than %.0f mm from its support or any vertex leaves the cavity (leaves may sink %.0f mm into the floor). "
                     "Lying leafy crops (carrot) also collide with their leaves pulled %.0f%% of the way in to the long axis, so they rest partly on them." % (DAMP_L, DAMP_A, MARGIN * 1000, FLOAT_MAX * 1000, LEAF_FLOOR * 1000, LEAF_R * 100))
doc["stats_r5"] = {"crops": len(CROP), "copies_total": len(res), "dropped_copies": sstats["dropped"], "clipping": nclip,
                   "float_over_5mm": n_over, "float_worst_mm": round(fl[0][0] * 1000, 2) if fl else 0,
                   "max_interpenetration_mm": round(pen * 1000, 2), "sim_frames": sstats["frames"], "unsettled_bodies": sstats["unsettled"]}
print("R5 STATS", doc["stats_r5"], flush=True)
for n, e in layouts.items(): print("R5 LAYOUT %-18s scale %s copies %s %s" % (n, e["scale"], e["copies_per_stack"], e["check"]), flush=True)

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
    def show(name, ci, nstacks=8):
        for r in res:
            if r["name"] == name and r["stack"] < nstacks:
                io = bpy.data.objects.new(name, merged(name)["mesh"]); sc.collection.objects.link(io)
                io.matrix_world = Matrix.Translation(Vector(floor_centre(ci))) @ Matrix(local_M(r).tolist()); shown.append(io)
    def clear():
        for o in shown: bpy.data.objects.remove(o)
        shown.clear()
    # one crop at a time in the middle crate of the middle tier
    tiles = []
    sc.render.resolution_x, sc.render.resolution_y = 560, 420
    fc = floor_centre(4)
    for name in CROP:
        clear(); show(name, 4)
        look(-8, 50, 1.05, (fc[0], fc[1] + 0.02, fc[2] + 0.10))
        fn = os.path.join(OUT, f"crop-{name}.png"); sc.render.filepath = fn
        bpy.ops.render.render(write_still=True); tiles.append((name, fn))
    clear()
    # the whole bin with a realistic mix (crate: item, stacks shown)
    MIX = [("Turnip", 5), ("Carrot", 8), ("Onion", 3), ("Mushroom", 6), ("MushroomYellow", 2), ("Barley", 8),
           ("Raspberry", 8), ("Blueberries", 4), ("Cloudberry", 7)]
    for ci, (name, ns) in enumerate(MIX):
        if name in CROP: show(name, ci, ns)
    sc.render.resolution_x, sc.render.resolution_y = 1600, 1000
    for vn, v in {"mix": (-18, 26, 4.2, (0, 0, 0.95)), "mix_top": (-10, 48, 3.4, (0, 0, 0.85))}.items():
        look(*v); sc.render.filepath = os.path.join(OUT, f"rootbin5-{vn}.png"); bpy.ops.render.render(write_still=True)
    # contact sheet (system Python + PIL)
    lab = {n: "%s  x%s  %dx8" % (n, layouts[n]["scale"] if layouts[n]["scale"] is not None else "fit 0.12m", layouts[n]["copies_per_stack"]) for n, _ in tiles}
    code = ("import sys,json;from PIL import Image,ImageDraw\n"
            "t=json.loads(sys.argv[1]);out=sys.argv[2];cols=5;W,H=560,420;rows=(len(t)+cols-1)//cols\n"
            "S=Image.new('RGB',(cols*W,rows*H),(30,30,30));d=ImageDraw.Draw(S)\n"
            "for i,(n,f,l) in enumerate(t):\n"
            " x,y=(i%cols)*W,(i//cols)*H;S.paste(Image.open(f).convert('RGB'),(x,y));d.rectangle((x,y,x+W,y+22),fill=(0,0,0));d.text((x+6,y+5),l,fill=(255,255,255))\n"
            "S.save(out)\n")
    sheet = os.path.join(OUT, "rootbin5-crops-sheet.png")
    subprocess.run(["python", "-c", code, json.dumps([(n, f, lab[n]) for n, f in tiles]), sheet], check=False)

# ---------- assets: frame + atlas copied from round 4, then the json (temp file + rename) last ----------
if "--crops" not in argv:
    for f in ("RootBin.obj", "rootbin_atlas.png"):
        shutil.copyfile(os.path.join(R4, f), os.path.join(OUTA, f))
    out = os.path.join(OUTA, "rootbin_anchors.json"); tmp = out + ".tmp"
    with open(tmp, "w") as fh: json.dump(doc, fh, indent=1)
    os.replace(tmp, out)
    print("R5 wrote", out, flush=True)
else:
    json.dump(doc, open(os.path.join(OUT, "rootbin_anchors_partial.json"), "w"), indent=1)
print("DONE")
