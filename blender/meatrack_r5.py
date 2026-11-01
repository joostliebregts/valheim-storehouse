"""Meat Rack, round 5: the bins' heaps PER ITEM at near true size, physics-settled. The hooks stay as in round 4.

Joost (22 Oct): "the lox meat is way too small, but it looks cute as hell"; the fish in the bins are tiny too. Round 4 settled
every bin pile with eight NeckTail copies of 0.14-0.15 m, and every item stored in a bin got that pile at that size (a 0.85 m
lox at 0.17x). Round 5 does for the six salting bins what rootbin_r5 did for the Root Bin: for EACH meat, fish, egg and
animal part the rack takes, one full bin (4 stacks, 1-3 copies per stack) is settled at one scale, x the item's TRUE size
(the game's model at scale 1: every one of these prefabs has root scale 1, read from the game files and the mod's own log),
aiming at 0.6x and less only where the bin is too small: a lying item must fit the 0.39 m bin floor (8 degrees of yaw play),
and a bin whose 4 stacks do not settle under the heap ceiling is settled again at 6% less scale until they do.

Method (round 4's, via rootbin_r5): Blender rigid body (Bullet), items = active convex hulls, settled one copy per item per
batch and frozen, stacks dropped in fill order (stack k onto stacks 0..k-1), a try re-dropped when a body floats more than
5 mm above its support or leaves the cavity. Cavity = a bin's inside (0.392 x 0.412, walls and corner posts as colliders,
floor at the highest floor-board jitter), heap ceiling 0.30 m over the floor (z 0.46): the lowest hung piece of
meatbundles_r2 ends at z 0.55. Checked afterwards against the real round-3 frame (MeatRack.obj, every loose part) in all six bins.

The mod (no code change): a store's anchors file may carry crop_layouts + crate_floor_centres (StoreModel.Load ->
Anchors.ParseCrops, read for every store); a bin unit (group 0-5 < 6 floor centres) holding an item WITH a layout shows that
item's stacks[k] at its k-th stack in that bin, scaled by `scale` (x true size) and placed by its ItemVisual bounds centre.
Hook units (groups 6-10) are past the floor list and keep MeatBundles. Items WITHOUT a layout (blood clot, blood bag, modded
meat) use the bin units' own copies, re-settled here (round-4 schema) with RawMeat as the demo item at 0.4x (longest 0.25 m,
2 per pile) instead of eight NeckTail copies at 0.15 m.

Item rips: C:/Users/joost/ValheimRip/items, and the ones it lacks (cooked meats, Fish7-12, bonemaw, bjorn, eggs, blubber,
freeze gland, entrails) from --rip DIR (made with ValheimRip/scripts/items_extract.py into the scratchpad, read-only on the
game). Coordinates: Blender z up, -y front; Unity ux=-bx, uy=bz, uz=-by. The rack is centred on x=y=0, floor z=0.
Output: assets/meatrack_r5/MeatRackAnchors.json (frame and atlas stay meatrack_r3's: the mod picks the newest round per file).
Run: blender -b -P meatrack_r5.py -- [--out DIR] [--rip DIR] [--items A,B] [--no-render]
"""
import bpy, bmesh, sys, os, math, json, random, time, copy, subprocess
import numpy as np
from mathutils import Vector, Matrix, Euler, Quaternion
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
R3 = os.path.normpath(os.path.join(HERE, "..", "assets", "meatrack_r3"))
R4 = os.path.normpath(os.path.join(HERE, "..", "assets", "meatrack_r4"))
OUTA = os.path.normpath(os.path.join(HERE, "..", "assets", "meatrack_r5"))
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
SCR = "C:/Users/joost/AppData/Local/Temp/claude/C--Users-joost--pai/5e4bc60b-cdfe-4638-8e29-2e507fa13cf9/scratchpad/meat2"
OUT = argv[argv.index("--out") + 1] if "--out" in argv else os.path.join(SCR, "r5")
EXTRA = argv[argv.index("--rip") + 1] if "--rip" in argv else os.path.join(SCR, "rip")
ITEMS = "C:/Users/joost/ValheimRip/items"
sys.path.append(ITEMS)
import load_item as LI
os.makedirs(OUTA, exist_ok=True); os.makedirs(OUT, exist_ok=True)
def arg(name, default, typ=float): return typ(argv[argv.index(name) + 1]) if name in argv else default

# ItemVisual.Bounds per item as the mod measures it (renderer mesh AABB turned by the part matrix, encapsulated; Unity item
# root space BEFORE the mod's half turn; root scale 1 for all): (centre, size). From the game files with UnityPy; the sizes
# equal the mod's own log lines ("Item model 'LoxMeat': ... size (0.500, 0.543, 0.892), root scale (1.000, 1.000, 1.000)").
BOUNDS = {
    'RawMeat': ([0.02647, 0.05, 0.14337], [0.28452, 0.25956, 0.61564]),
    'LoxMeat': ([0.00898, 0.00556, -0.12184], [0.49988, 0.54343, 0.89244]),
    'DeerMeat': ([0.00286, 0.05966, -0.04012], [0.2802, 0.09375, 0.43045]),
    'NeckTail': ([0.0, 0.03445, -0.05081], [0.21921, 0.26992, 0.65004]),
    'WolfMeat': ([0.04038, 0.08457, 0.20138], [0.38881, 0.24471, 0.95677]),
    'AsksvinMeat': ([0.0, 0.28366, 0.00746], [0.37173, 0.58022, 0.85431]),
    'BugMeat': ([0.03973, 0.20794, 0.0], [1.28115, 0.40853, 0.44648]),
    'ChickenMeat': ([-0.01674, 0.05889, -0.00053], [0.42921, 0.12039, 0.28717]),
    'HareMeat': ([0.02659, 0.07315, 0.0], [1.32339, 0.15066, 0.61961]),
    'VoltureMeat': ([0.0, 0.23307, -0.10536], [0.80025, 0.50139, 1.11809]),
    'SerpentMeat': ([-0.00879, 0.25411, 0.03687], [1.25106, 0.75199, 1.33556]),
    'BoneMawSerpentMeat': ([0.0, 0.21341, 0.05086], [0.95855, 0.65105, 1.42915]),
    'BjornMeat': ([-0.0025, 0.00932, -0.01407], [0.7448, 0.26294, 0.40245]),
    'FishRaw': ([0.05041, 0.06784, 0.11696], [0.31522, 0.35479, 0.59091]),
    'Fish1': ([0.07067, -0.03915, -0.01894], [0.14133, 0.46041, 1.02637]),
    'Fish2': ([0.09422, -0.02553, -0.07491], [0.18844, 0.61388, 1.71062]),
    'Fish3': ([0.1656, -0.03019, -0.08728], [0.3312, 0.7171, 1.74083]),
    'Fish4_cave': ([0.0778, 0.00669, -0.05047], [0.30459, 0.31835, 0.88832]),
    'Fish5': ([0.0, 0.16319, -0.17459], [0.39536, 0.41193, 1.41187]),
    'Fish6': ([0.063, -0.07246, -0.05496], [0.22133, 0.39712, 0.91769]),
    'Fish7': ([0.046, -0.07116, -0.00525], [0.26882, 0.46158, 1.15393]),
    'Fish8': ([0.054, -0.01831, -0.0826], [0.27661, 0.52084, 1.40507]),
    'Fish9': ([0.00181, -0.01245, -0.1191], [0.69743, 0.7542, 0.92916]),
    'Fish10': ([0.0, 0.01395, -0.05309], [0.35329, 0.75369, 1.89634]),
    'Fish11': ([0.006, 0.1114, -0.02865], [0.2418, 0.48625, 0.80225]),
    'Fish12': ([0.04167, 0.08162, -0.05217], [0.61649, 0.63492, 0.54341]),
    'CookedMeat': ([0.02647, 0.05, 0.09337], [0.28452, 0.25956, 0.61564]),
    'CookedLoxMeat': ([0.00898, 0.05556, -0.02184], [0.49988, 0.54343, 0.89244]),
    'CookedDeerMeat': ([0.00286, 0.05966, -0.04012], [0.2802, 0.09375, 0.43045]),
    'CookedWolfMeat': ([0.04974, 0.08299, 0.20307], [0.38884, 0.24472, 0.95682]),
    'CookedChickenMeat': ([-0.01674, 0.05889, -0.00053], [0.42921, 0.12039, 0.28717]),
    'CookedHareMeat': ([0.02659, 0.07315, 0.0], [1.32339, 0.15066, 0.61961]),
    'CookedBugMeat': ([0.03973, 0.20794, 0.0], [1.28115, 0.40853, 0.44648]),
    'CookedAsksvinMeat': ([0.0, 0.28366, 0.00746], [0.37173, 0.58022, 0.85431]),
    'CookedVoltureMeat': ([0.0, 0.23307, -0.10536], [0.80025, 0.50139, 1.11809]),
    'SerpentMeatCooked': ([-0.00879, 0.21611, 0.33687], [1.25106, 0.75199, 1.33556]),
    'CookedBoneMawSerpentMeat': ([0.0, 0.17541, 0.05086], [0.95855, 0.65105, 1.42915]),
    'CookedBjornMeat': ([-0.0025, 0.00932, -0.01407], [0.7448, 0.26294, 0.40245]),
    'FishCooked': ([0.05041, 0.06784, 0.11696], [0.31522, 0.35479, 0.59091]),
    'NeckTailGrilled': ([0.0, 0.06445, -0.05081], [0.21921, 0.26992, 0.65004]),
    'Entrails': ([0.0028, 0.09787, 0.03254], [0.59294, 0.25245, 0.58803]),
    'ChickenEgg': ([0.0, 0.11095, 0.02], [0.18306, 0.22166, 0.21138]),
    'CookedEgg': ([-0.00086, 0.03148, 0.00236], [0.57253, 0.06375, 0.43702]),
    'SealBlubber': ([0.01224, 0.06385, 0.00663], [0.34426, 0.17604, 0.53758]),
    'CookedSealBlubber': ([0.01224, 0.06385, 0.00663], [0.34426, 0.17604, 0.53758]),
    'FreezeGland': ([0.006, 0.10009, 0.01066], [0.52121, 0.2429, 0.55482]),
}

def item_dir(name):
    for d in (ITEMS, EXTRA):
        if os.path.exists(f"{d}/{name}/info.json"): return d
    return None

def load(name, **kw):
    d = item_dir(name); old = LI.ROOT; LI.ROOT = d
    try: return LI.load_item(name, **kw)
    finally: LI.ROOT = old

# ---------- items: mode, copies per stack ----------
# long = lies with its longest axis across the bin, any roll; flatlong = the same, flat side down; flat = flat side down,
# any quarter turn; tumble = any orientation. "_units" is the demo item of the bin units' own copies (round-4 schema).
SCALE = 0.6
LONG1 = ("LoxMeat CookedLoxMeat WolfMeat CookedWolfMeat AsksvinMeat CookedAsksvinMeat BugMeat CookedBugMeat NeckTail NeckTailGrilled "
         "RawMeat CookedMeat BjornMeat CookedBjornMeat")
FISH = "Fish1 Fish2 Fish3 Fish4_cave Fish5 Fish6 Fish7 Fish8 Fish10 Fish11 FishRaw FishCooked"
MODES = {n: ("long", 1) for n in LONG1.split()}
MODES.update({n: ("flatlong", 1) for n in FISH.split()})
MODES.update({"HareMeat": ("flatlong", 1), "CookedHareMeat": ("flatlong", 1), "DeerMeat": ("flatlong", 2), "CookedDeerMeat": ("flatlong", 2),
              "ChickenMeat": ("flatlong", 2), "CookedChickenMeat": ("flatlong", 2), "SealBlubber": ("flatlong", 1), "CookedSealBlubber": ("flatlong", 1),
              "SerpentMeat": ("flat", 1), "SerpentMeatCooked": ("flat", 1), "BoneMawSerpentMeat": ("flat", 1), "CookedBoneMawSerpentMeat": ("flat", 1),
              "VoltureMeat": ("flat", 1), "CookedVoltureMeat": ("flat", 1), "CookedEgg": ("flat", 2), "Entrails": ("flat", 1),
              "FreezeGland": ("flat", 1), "Fish9": ("tumble", 1), "Fish12": ("tumble", 1), "ChickenEgg": ("tumble", 3),
              "_units": ("long", 2)})
UNITS_DEMO, UNITS_SCALE = "RawMeat", 0.40
WANT = argv[argv.index("--items") + 1].split(",") if "--items" in argv else list(MODES)
NAMES = [n for n in MODES if n in WANT and item_dir(UNITS_DEMO if n == "_units" else n) and (n == "_units" or n in BOUNDS)]
print("R5 items", len(NAMES), "missing", [n for n in MODES if n in WANT and n not in NAMES], flush=True)

# ---------- the bins (meatrack_r3: floor board top 0.16, walls 0.16 high to 0.32, corner posts to 0.34) ----------
FLOOR_Z = 0.16
# the generic cavity relative to a bin's floor centre (Blender): inner wall faces x +-0.200 / y +-0.210 less their 3 mm jitter,
# floor at the highest floor-board jitter (+3.5 mm), heap ceiling 0.30 over the floor; posts fill the corners from x 0.1855 / y 0.1955
GEN = (-0.196, 0.196, -0.206, 0.206, 0.0035, 0.30)
POST = (0.1855, 0.1955)
SIM_DX = 1.0
# stack targets (bin-floor-centre local, Blender): back-left, front-right, back-right, front-left (+y = towards the back)
STACK_XY = [(-0.095, 0.10), (0.095, -0.10), (0.095, 0.10), (-0.095, -0.10)]
NSTACK = 4

anc4 = json.load(open(os.path.join(R4, "MeatRackAnchors.json"), encoding="utf-8"))
BIN_UNITS = {}
for u in anc4["units"]:
    if u["kind"] == "pile": BIN_UNITS.setdefault(u["bin"], []).append(u)
NBIN = len(BIN_UNITS)
def floor_centre_u(b):
    us = BIN_UNITS[b]
    return [round(sum(u["position"][0] for u in us) / len(us), 4), FLOOR_Z, round(sum(u["position"][2] for u in us) / len(us), 4)]
def floor_centre(b):
    """Blender position of bin b's floor centre."""
    c = floor_centre_u(b); return np.array((-c[0], -c[2], c[1]))

# ---------- scene ----------
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene

def join(obs, name):
    bpy.ops.object.select_all(action="DESELECT")
    for o in obs: o.select_set(True)
    bpy.context.view_layer.objects.active = obs[0]
    bpy.ops.object.join(); ob = bpy.context.active_object; ob.name = name
    return ob

# ---------- item templates (mesh centred on its vertex bounds; root_shift = that centre in the item's root space) ----------
TPL = {}
def tpl(name):
    if name in TPL: return TPL[name]
    src = UNITS_DEMO if name == "_units" else name
    objs = [o for o in load(src, anchor="center") if o.type == "MESH"]
    info = json.load(open(f"{item_dir(src)}/{src}/info.json"))
    pivot = (np.array(info["bounds_min"]) + np.array(info["bounds_max"])) / 2
    datas = [o.data for o in objs]
    for o in objs: bpy.data.objects.remove(o)
    allv = np.array([v.co[:] for d in datas for v in d.vertices])
    mn, mx = allv.min(0), allv.max(0); c = (mn + mx) / 2
    for d in datas: d.transform(Matrix.Translation(-Vector(c)))
    TPL[name] = dict(datas=datas, size=mx - mn, verts=allv - c, root_shift=pivot + c, src=src)
    return TPL[name]

def align_matrix(size, thin_to_z=False):
    """longest axis onto x; with thin_to_z also the thinnest onto z (a turn about x)."""
    order = np.argsort(size); ax, th = int(order[2]), int(order[0])
    R = Vector([1.0 if i == ax else 0.0 for i in range(3)]).rotation_difference(Vector((1, 0, 0))).to_matrix()
    if thin_to_z:
        t = R @ Vector([1.0 if i == th else 0.0 for i in range(3)])
        R = Matrix.Rotation(-math.atan2(t.y, t.z), 3, "X") @ R
    return R

MERGED = {}
def merged(item):
    """visible mesh (bounds-centred) and its collision body: the convex hull of all vertices."""
    if item in MERGED: return MERGED[item]
    t = tpl(item)
    obs = []
    for d in t["datas"]:
        o = bpy.data.objects.new("m", d.copy()); sc.collection.objects.link(o); obs.append(o)
    ob = join(obs, "mrg") if len(obs) > 1 else obs[0]
    me = ob.data; me.name = item
    bpy.data.objects.remove(ob)
    verts = np.array([v.co[:] for v in me.vertices])
    cb = (verts.min(0) + verts.max(0)) / 2
    bm = bmesh.new()
    for v in verts - cb: bm.verts.new(v)
    res = bmesh.ops.convex_hull(bm, input=bm.verts[:])
    for g in res["geom_interior"] + res["geom_unused"]:
        if isinstance(g, bmesh.types.BMVert) and g.is_valid and not g.link_faces: bm.verts.remove(g)
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if f.is_valid])
    bm.normal_update(); bm.verts.index_update()
    vol = bm.calc_volume()
    tf = [f for f in bm.faces if f.is_valid]
    used = sorted({v.index for f in tf for v in f.verts})
    remap = {o: n for n, o in enumerate(used)}
    bm.verts.ensure_lookup_table()
    hv = np.array([bm.verts[i].co[:] for i in used])
    F = np.array([[remap[v.index] for v in f.verts] for f in tf])
    cen = hv.mean(0); N = []; D = []
    for f in tf:
        n = np.array(f.normal[:]); d0 = n @ np.array(f.verts[0].co[:])
        if n @ cen > d0: n = -n; d0 = -d0
        N.append(n); D.append(d0)
    bm.free()
    pm = bpy.data.meshes.new(f"prox_{item}"); pm.from_pydata([tuple(v) for v in hv], [], [tuple(int(i) for i in f) for f in F]); pm.update()
    edges = sorted({tuple(sorted((int(f[a]), int(f[(a + 1) % 3])))) for f in F for a in range(3)})
    MERGED[item] = dict(mesh=me, verts=verts, cb=cb, hullV=hv, hullF=F, hullN=np.array(N), hullD=np.array(D), hullE=edges, prox=pm,
                        size=np.array(t["size"]), vol=abs(vol))
    return MERGED[item]

def pose_matrix(c, R3, s):
    return Matrix.Translation(Vector(c)) @ Matrix(R3).to_4x4() @ Matrix.Diagonal((s, s, s, 1))
def world_pts(P, M): return P @ M[:3, :3].T + M[:3, 3]

def rec_world(m, Mp, s):
    M = Mp.copy(); M[:3, 3] = Mp[:3, 3] - Mp[:3, :3] @ m["cb"]      # visible item matrix (origin = vertex bounds centre)
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
        ox = (b[0] + b[1]) / 2           # the corner posts stand from the floor up: never a drop spot
        for i in range(self.nx):
            for j in range(self.ny):
                x = b[0] + (i + 0.5) * CELL - ox; y = b[2] + (j + 0.5) * CELL
                if abs(x) > POST[0] - 0.01 and abs(y) > POST[1] - 0.01: self.hf[i, j] = b[5]
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

def support_gap(r, floor_z, earlier, walls=None):
    """distance (m) from the body to its nearest support: the bin floor, a wall it leans on, or an earlier body under it."""
    zmin, zmax = r["lo"][2], r["hi"][2]
    gap = max(0.0, zmin - floor_z); what = "floor"
    if gap <= 0.0015: return gap, what
    span = max(zmax - zmin, 1e-6)
    for q in earlier:
        if (q["lo"] > r["hi"] + 0.02).any() or (q["hi"] < r["lo"] - 0.02).any(): continue
        d, pt = hull_dist(r, q)
        if pt is None or d >= gap: continue
        if pt[2] - zmin <= 0.35 * span + 1e-6: gap = d; what = "body"
    if walls is not None and gap > 0.0015:
        x0, x1, y0, y1 = walls      # leaning on a wall with the low end on the floor or on a body counts as resting
        wd = min(r["lo"][0] - x0, x1 - r["hi"][0], r["lo"][1] - y0, y1 - r["hi"][1])
        if wd <= 0.0025 and gap <= 0.03: gap = max(0.0, wd); what = "wall"
    return gap, what

# ---------- per-item setup ----------
ITEM = {}
SPAWN_MG = 0.010
SPAWN_OVER = 0.04
def plan_room(): return (GEN[1] - GEN[0]) - 2 * SPAWN_MG - 0.006
for i, name in enumerate(NAMES):
    mode, n = MODES[name]
    m = merged(name)
    size = m["size"]; srt = np.sort(size)
    s = UNITS_SCALE if name == "_units" else SCALE
    if mode in ("long", "flatlong", "flat"):     # the largest scale that lies across the bin with 8 degrees of yaw play
        s = min(s, (plan_room() - 0.004) / (srt[2] * math.cos(math.radians(8)) + srt[1] * math.sin(math.radians(8))))
    if mode == "tumble": s = min(s, (GEN[5] - GEN[4] - 0.05) / float(srt[2]), (plan_room() - 0.004) / float(srt[2]))
    ymax = 0.0
    if mode in ("long", "flatlong", "flat"):
        Ls = float(srt[2]) * s; Ws = float(srt[1]) * s
        for a in np.arange(0, 40.01, 0.5):
            if Ls * math.cos(math.radians(a)) + Ws * math.sin(math.radians(a)) <= plan_room(): ymax = float(a)
    b = (i * SIM_DX + GEN[0], i * SIM_DX + GEN[1], GEN[2], GEN[3], GEN[4], GEN[5])
    ITEM[name] = dict(i=i, name=name, mode=mode, n=n, s=s, ymax=ymax, b=b, origin=np.array((i * SIM_DX, 0.0, 0.0)), crate=Crate(b))
    print("R5 item %-24s mode %-8s scale %.3f size@s %s copies/stack %d yaw +-%.1f" % (name, mode, s, np.round(size * s, 3), n, ymax), flush=True)
if "--probe" in argv:
    print("DONE probe"); sys.exit(0)

# ---------- simulation (rootbin_r5's, one generic bin per item side by side) ----------
MAXF = arg("--maxf", 140); MINF = 16
VW = arg("--vw", 0.2)
DAMP_L = 0.5; DAMP_A = 0.95
NTRY = arg("--ntry", 30, int)
MARGIN = 0.0015
FLOAT_MAX = 0.005

def rand_rot(rr):
    q = Quaternion([rr.gauss(0, 1) for _ in range(4)]); q.normalize(); return q.to_matrix()

def simulate(items, seed):
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
    for c in items:
        x0, x1, y0, y1, z0, z1 = c["b"]; H = z1 - z0 + 0.06; ox = c["origin"][0]
        add_box((x0 - T, y0 - T, z0 - 0.1), (x1 + T, y1 + T, z0))
        add_box((x0 - T, y0 - T, z0 - 0.1), (x0 + inset, y1 + T, z0 + H))
        add_box((x1 - inset, y0 - T, z0 - 0.1), (x1 + T, y1 + T, z0 + H))
        add_box((x0 - T, y0 - T, z0 - 0.1), (x1 + T, y0 + inset, z0 + H))
        add_box((x0 - T, y1 - inset, z0 - 0.1), (x1 + T, y1 + T, z0 + H))
        for sx in (-1, 1):
            for sy in (-1, 1):
                xa, xb = sorted((ox + sx * POST[0], ox + sx * (POST[0] + 0.05)))
                ya, yb = sorted((sy * POST[1], sy * (POST[1] + 0.05)))
                add_box((xa, ya, z0 - 0.1), (xb, yb, z0 + H))
    st = dict(frames=0, drops=0, tries=0, rej=dict(), unsettled=0)
    allr = []
    PROBE = np.array([[1, 0, 0], [-1, 0, 0], [0, 1, 0], [0, -1, 0], [0, 0, 1], [0, 0, -1]], float)

    def spawn(w):
        c, k = w["c"], w["k"]; cr = c["crate"]; m = merged(c["name"]); s = c["s"]; w["s"] = s
        mode = c["mode"]
        if mode == "long":
            yaw = rr.uniform(-c["ymax"], c["ymax"]) + (180 if (k + w["stack"]) % 2 else 0)
            Rc = Rz(yaw) @ Ry(rr.uniform(-6, 6)) @ Rx(rr.uniform(0, 360)) @ align_matrix(m["size"])
        elif mode == "flatlong":
            yaw = rr.uniform(-c["ymax"], c["ymax"]) + (180 if (k + w["stack"]) % 2 else 0)
            Rc = Rz(yaw) @ Ry(rr.uniform(-5, 5)) @ Rx(rr.choice((0, 180)) + rr.uniform(-8, 8)) @ align_matrix(m["size"], thin_to_z=True)
        elif mode == "flat":
            yaw = rr.uniform(-c["ymax"], c["ymax"]) + rr.choice((0, 90, 180, 270))
            Rc = Rz(yaw) @ Ry(rr.uniform(-6, 6)) @ Rx(rr.choice((0, 180)) + rr.uniform(-6, 6)) @ align_matrix(m["size"], thin_to_z=True)
        else:
            Rc = rand_rot(rr)
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
        if best is None: return False, "ceiling"
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
        V = world_pts(m["verts"], r["M"])
        x0, x1, y0, y1, z0, z1 = cr.b; e = 0.0005; ox = c["origin"][0]
        bad = []
        if (V[:, 2] < z0 - 0.002).any(): bad.append("below floor")
        walls = (V[:, 0].min() < x0 + e) or (V[:, 0].max() > x1 - e) or (V[:, 1].min() < y0 + e) or (V[:, 1].max() > y1 - e)
        posts = bool(((np.abs(V[:, 0] - ox) > POST[0] - e) & (np.abs(V[:, 1]) > POST[1] - e)).any())
        if walls or posts: bad.append("outside walls")
        ceil = V[:, 2].max() > z1 - e
        if ceil: bad.append("above ceiling")
        if walls or ceil:
            w["extra"] = w.get("extra", np.zeros(5)) + np.maximum(0, [x0 - V[:, 0].min() + 0.003, V[:, 0].max() - x1 + 0.003,
                y0 - V[:, 1].min() + 0.003, V[:, 1].max() - y1 + 0.003, V[:, 2].max() - z1 + 0.003]) * np.array([walls] * 4 + [ceil], float)
            w["extra"] = np.minimum(w["extra"], 0.04)
        gap, what = support_gap(r, z0, cr.bodies, (x0, x1, y0, y1))
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
    for stack in range(NSTACK):
        nmax = max(c["n"] for c in items)
        for k in range(nmax):
            batch = []
            for c in items:
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
    """every body vs the bodies of the same item dropped BEFORE it (what exists when only earlier stacks are shown)."""
    by = {}; out = []
    for r in sorted(res, key=lambda r: r["id"]):
        earlier = by.setdefault(r["name"], [])
        c = ITEM[r["name"]]
        g, what = support_gap(r, GEN[4], earlier, c["b"][:4])
        out.append((g, what, r["name"], r["stack"], r["k"])); earlier.append(r)
    out.sort(key=lambda x: -x[0])
    return out

def local_M(r):
    """the settled visible-item matrix, relative to the item's bin floor centre (Blender)."""
    M = r["M"].copy(); M[:3, 3] -= ITEM[r["name"]]["origin"]; return M

# ---------- the real frame: MeatRack.obj (round 3), every loose part a closed box ----------
def frame_parts():
    bpy.ops.wm.obj_import(filepath=os.path.join(R3, "MeatRack.obj"), forward_axis="NEGATIVE_Z", up_axis="Y",
                          use_split_objects=False, use_split_groups=False)
    ob = bpy.context.selected_objects[0]
    bm = bmesh.new(); bm.from_mesh(ob.data); bm.transform(ob.matrix_world)     # the importer turns the object, not the mesh
    bm.verts.ensure_lookup_table(); bm.faces.ensure_lookup_table()
    comp_of = [-1] * len(bm.verts); parts = []
    for v in bm.verts:
        if comp_of[v.index] >= 0: continue
        cid = len(parts); stack = [v]; comp = []
        while stack:
            x = stack.pop()
            if comp_of[x.index] >= 0: continue
            comp_of[x.index] = cid; comp.append(x.index)
            for e in x.link_edges: stack.append(e.other_vert(x))
        parts.append(comp)
    faces = [[] for _ in parts]
    for f in bm.faces: faces[comp_of[f.verts[0].index]].append([l.index for l in f.verts])
    out = []
    for cid, comp in enumerate(parts):
        idx = {o: n for n, o in enumerate(comp)}
        vs = [bm.verts[i].co.copy() for i in comp]
        a = np.array([p[:] for p in vs])
        out.append((a.min(0), a.max(0), BVHTree.FromPolygons(vs, [[idx[i] for i in f] for f in faces[cid]])))
    bm.free(); bpy.data.objects.remove(ob)
    return out

def clip_check(res):
    """every item's layout put into each of the six real bins (translation only): a copy clips if any vertex lies inside a
    frame part (ray parity, per closed part: floor boards, walls, posts, straps, tray) or below the floor board top."""
    parts = frame_parts()
    LO = np.array([p[0] for p in parts]); HI = np.array([p[1] for p in parts])
    d = Vector((0.267, 0.534, 0.802)).normalized()
    def inside_p(bvh, p):
        o = p.copy(); n = 0
        while True:
            hit = bvh.ray_cast(o, d)
            if hit[0] is None: break
            n += 1; o = hit[0] + d * 1e-4
        return n % 2 == 1
    bad = {}; low = 9.0
    for r in res:
        m = merged(r["name"])
        Vl = world_pts(m["verts"], local_M(r))
        low = min(low, float(Vl[:, 2].min()))
        for b in range(NBIN):
            V = Vl + floor_centre(b); why = None
            cand = np.where(((V[:, None, :] >= LO[None] - 1e-4) & (V[:, None, :] <= HI[None] + 1e-4)).all(2))
            for vi, c in zip(*cand):
                if inside_p(parts[c][2], Vector(V[vi])): why = "inside frame part at %s" % np.round(V[vi], 3); break
            if why: bad.setdefault(r["name"], []).append((b, r["stack"], r["k"], why))
    n = sum(len(v) for v in bad.values())
    print("R5 CLIPPING", n, {k: len(v) for k, v in bad.items()}, [v[:2] for v in bad.values()][:4],
          "lowest vertex %.4f m over the floor centre" % low, flush=True)
    return n, bad

# ---------- run ----------
t0 = time.time()
todo = list(ITEM.values()); res = []; sstats = None; history = {}
for p in range(10):
    for c in todo:
        c["crate"] = Crate(c["b"]); c["dropped"] = []
    r, st = simulate(todo, arg("--seed", 5, int) + p)
    if sstats is None: sstats = st
    else:
        for k in ("frames", "tries", "unsettled"): sstats[k] += st[k]
    bad = [c for c in todo if c["dropped"]]; badn = {c["name"] for c in bad}
    res += [x for x in r if x["name"] not in badn]
    print("R5 PASS", p, "settled", len(todo) - len(bad), "retry", [(c["name"], round(c["s"], 3), len(c["dropped"])) for c in bad], flush=True)
    for o in [o for o in bpy.data.objects if o.type == "MESH"]: bpy.data.objects.remove(o)
    if not bad: break
    if p == 9:
        res += [x for x in r if x["name"] in badn]; break
    for c in bad:
        history.setdefault(c["name"], []).append(round(c["s"], 4)); c["s"] *= 0.94
    todo = bad
sstats["dropped"] = sum(len(c["dropped"]) for c in ITEM.values())
for c in ITEM.values():
    used = [x["s"] for x in res if x["name"] == c["name"]]
    if used: c["s"] = used[0]
print("R5 scale retries", history, flush=True)
print("R5 SIM done", sstats, "%.0fs" % (time.time() - t0), flush=True)
pen, npairs = interpenetration(res)
print("R5 INTERPEN max %.2f mm over %d touching pairs" % (pen * 1000, npairs), flush=True)
fl = float_check(res)
n_over = sum(1 for o in fl if o[0] > FLOAT_MAX)
print("R5 FLOAT worst 5 (mm):", [(round(o[0] * 1000, 2), o[1], o[2], "stack %d copy %d" % (o[3], o[4])) for o in fl[:5]], "over 5 mm:", n_over, "of", len(fl), flush=True)
nclip, clipnotes = clip_check(res)

# ---------- export ----------
MC = Matrix(((-1, 0, 0), (0, 0, 1), (0, -1, 0)))
def uvec(v): return [round(-float(v[0]), 4), round(float(v[2]), 4), round(-float(v[1]), 4)]
def uquat(Rb):
    q = (MC @ Rb @ MC.transposed()).to_quaternion(); q.normalize()
    if q.w < 0: q = -q
    return [round(c, 5) for c in (q.x, q.y, q.z, q.w)]
def bc_rip(name):
    """ItemVisual's bounds centre in the rip's (Blender) item root space: Unity (x, y, z) -> (x, z, y)."""
    c = BOUNDS[UNITS_DEMO if name == "_units" else name][0]; return np.array((c[0], c[2], c[1]))
def item_space_bounds(name):
    c, s = BOUNDS[UNITS_DEMO if name == "_units" else name]
    return {"center": [round(-c[0], 5), round(c[1], 5), round(-c[2], 5)], "size": [round(x, 5) for x in s]}

def copy_pose(r):
    """(centre of ItemVisual's bounds, rotation) of a settled copy, Blender, bin-floor-centre local."""
    M = local_M(r); Rw = M[:3, :3] / r["s"]
    t = tpl(r["name"])
    root = M[:3, 3] - M[:3, :3] @ t["root_shift"]          # the item root (the mesh was centred on its vertex bounds)
    return root + M[:3, :3] @ bc_rip(r["name"]), Rw

layouts = {}
for name, c in ITEM.items():
    if name == "_units": continue
    rs = [r for r in res if r["name"] == name]
    m = merged(name)
    stacks = []
    for sidx in range(NSTACK):
        cps = []
        for r in sorted([r for r in rs if r["stack"] == sidx], key=lambda r: r["k"]):
            cen, Rw = copy_pose(r)
            cps.append({"offset": uvec(cen), "rot_quat_xyzw": uquat(Matrix(Rw.tolist()))})
        stacks.append(cps)
    gaps = [o[0] for o in fl if o[2] == name]
    tops = [float(world_pts(m["verts"], local_M(r))[:, 2].max()) for r in rs]
    sz = m["size"]
    layouts[name] = {"scale": round(c["s"], 4), "true_size_m": [round(float(sz[0]), 4), round(float(sz[2]), 4), round(float(sz[1]), 4)],
                     "true_longest_m": round(float(sz.max()), 4), "item_bounds": item_space_bounds(name),
                     "mode": c["mode"], "copies_per_stack": c["n"], "stacks": stacks,
                     "check": {"copies": len(rs), "dropped": len(c.get("dropped", [])), "float_worst_mm": round(1000 * max(gaps), 2) if gaps else 0,
                               "clipping_in_6_bins": len(clipnotes.get(name, [])), "heap_top_m": round(max(tops), 3) if tops else 0}}

# the bin units' own copies (round-4 schema), settled with the demo item: for items without a layout
UNITS = []
ui = ITEM.get("_units")
AX = [Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))]
bsz = np.array(BOUNDS[UNITS_DEMO][1]); il, it = int(np.argmax(bsz)), int(np.argmin(bsz))
urs = [r for r in res if r["name"] == "_units"]
for u4 in anc4["units"]:
    u = copy.deepcopy(u4)
    if u["kind"] == "pile" and ui:
        b = u["bin"]; pile = [x["index"] for x in BIN_UNITS[b]].index(u["index"])
        fc = np.array(floor_centre_u(b)); up = np.array(u["position"])
        cps = []; ext_lo = np.full(3, 9.0); ext_hi = np.full(3, -9.0)
        for r in sorted([r for r in urs if r["stack"] == pile], key=lambda r: r["k"]):
            cen, Rw = copy_pose(r)
            Ru = MC @ Matrix(Rw.tolist()) @ MC.transposed()
            off = np.array(uvec(cen)) + fc - up
            q = Ru.to_quaternion(); q.normalize()
            if q.w < 0: q = -q
            e = Ru.to_euler("ZXY")
            cps.append({"offset": [round(float(x), 4) for x in off], "longest_m": round(float(r["s"] * bsz.max()), 4),
                        "align": {"long_axis_to": [round(x, 4) for x in (Ru @ AX[il])], "thin_axis_to": [round(x, 4) for x in (Ru @ AX[it])],
                                  "then_rotate_euler_zxy": [0.0, 0.0, 0.0], "then_rotate_quat_xyzw": [0.0, 0.0, 0.0, 1.0]},
                        "rendered_rotation_euler_zxy": [round(math.degrees(e.x), 2), round(math.degrees(e.y), 2), round(math.degrees(e.z), 2)],
                        "rendered_rotation_quat_xyzw": [round(q.x, 4), round(q.y, 4), round(q.z, 4), round(q.w, 4)]})
            V = world_pts(merged("_units")["verts"], local_M(r))
            Vu = np.array([uvec(v) for v in V]) + fc - up
            ext_lo = np.minimum(ext_lo, Vu.min(0)); ext_hi = np.maximum(ext_hi, Vu.max(0))
        u["copies"] = cps; u["render_item"] = UNITS_DEMO
        u["settled_extent_min"] = [round(float(x), 4) for x in ext_lo]; u["settled_extent_max"] = [round(float(x), 4) for x in ext_hi]
    UNITS.append(u)

doc = {k: v for k, v in anc4.items() if k != "units"}
doc["round"] = 5
doc["units"] = UNITS
doc["crop_layouts"] = layouts
doc["crate_floor_centres"] = [floor_centre_u(b) for b in range(NBIN)]
doc["note"] = ("r5 (Joost, 22 Oct: 'the lox meat is way too small'): the 40 hook units are round 4's unchanged; the 24 bin units are "
               "re-settled with %s at %.2fx true size (longest %.3f m, %d per pile) instead of eight NeckTail copies at 0.15 m; "
               "crop_layouts put every known meat, fish, egg and animal part in the bins near true size (meatrack_r5.py)." %
               (UNITS_DEMO, ITEM["_units"]["s"] if ui else 0, (ITEM["_units"]["s"] * float(bsz.max())) if ui else 0, MODES["_units"][1]))
doc["crop_layouts_doc"] = (
    "crop_layouts: one physics-settled full bin per item (item prefab name). A bin holding n stacks of an item shows stacks[0..n-1] "
    "of that item's layout (all of a stack's copies), so filling never moves earlier copies (stack k was dropped onto stacks "
    "0..k-1 after they were frozen). Per copy: the item's model in the mod's item space (ItemVisual: prefab root space without "
    "the root's own scale, which is 1 for every one of these items, turned 180 degrees about up), scaled uniformly by 'scale' "
    "(= x the item's true size), rotated by rot_quat_xyzw about its ItemVisual bounds centre, that centre put at "
    "crate_floor_centres[bin] + offset (prefab space, Unity y-up/+z front; offset is bin-floor-centre local). Exactly the mod's "
    "crop path (pos = centre - r * (s * Bounds.center)); item_bounds is the Bounds the mod measures (centre and size in "
    "item space), used for the offsets. Settled in one generic bin (0.392 x 0.412 inside, corner posts, heap ceiling 0.30 m "
    "over the floor) and checked against the real frame in all six bins. Per item also: true_size_m (Unity x, y, z at scale 1), "
    "true_longest_m, mode, copies_per_stack, check (copies, dropped, float_worst_mm, clipping_in_6_bins, heap_top_m above the "
    "floor). crate_floor_centres: by bin index (the units' 'bin' field). No '_generic' layout on purpose: an item without one "
    "(blood clot, blood bag, modded) takes the bin units' own copies, whose align/longest_m turn it like the demo item and "
    "whose floor rule keeps it out of the floor.")
reduced = {n: round(c["s"], 4) for n, c in ITEM.items() if n != "_units" and abs(c["s"] - SCALE) > 1e-6}
doc["crop_layouts_scale_exceptions"] = {
    "rule": ("%.2f x true size for every item, except: (1) a lying item gets the largest scale that lies across the 0.39 m bin with "
             "8 degrees of yaw play, a tumbled one the largest that fits the bin and the heap ceiling; (2) an item whose full bin "
             "(4 stacks x copies_per_stack) did not settle was settled again at 6%% less scale until it did." % SCALE),
    "reduced": reduced, "failed_scales": history}
doc["physics_r5"] = ("Blender rigid body (Bullet), rootbin_r5's settings: items = active convex hulls of the item, friction 0.8, restitution 0, "
                     "damping %.2f/%.2f, margin %.1f mm, substeps 20, iterations 40; one copy per item per batch, settled then frozen; "
                     "stack order back-left, front-right, back-right, front-left. A try is re-dropped when a body is farther than %.0f mm "
                     "from its support (floor, an earlier copy, or a wall it leans on) or any vertex leaves the cavity or rises over the ceiling."
                     % (DAMP_L, DAMP_A, MARGIN * 1000, FLOAT_MAX * 1000))
doc["stats_r5"] = {"items": len(layouts), "copies_total": len(res), "dropped_copies": sstats["dropped"], "clipping": nclip,
                   "float_over_5mm": n_over, "float_worst_mm": round(fl[0][0] * 1000, 2) if fl else 0,
                   "max_interpenetration_mm": round(pen * 1000, 2),
                   "heap_top_max_z_m": round(FLOOR_Z + max([l["check"]["heap_top_m"] for l in layouts.values()] + [0]), 3),
                   "sim_frames": sstats["frames"], "unsettled_bodies": sstats["unsettled"]}
print("R5 STATS", doc["stats_r5"], flush=True)
for n, e in layouts.items():
    print("R5 LAYOUT %-24s scale %s x true (%.3f m long) copies %s %s" % (n, e["scale"], e["scale"] * e["true_longest_m"], e["copies_per_stack"], e["check"]), flush=True)

# ---------- contact sheet: every item's full bin, in the middle front bin of the real frame ----------
if "--no-render" not in argv:
    world = bpy.data.worlds.new("w"); sc.world = world; world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.42, 0.45, 0.5, 1)
    world.node_tree.nodes["Background"].inputs[1].default_value = 0.9
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN")); sun.data.energy = 3.2
    sun.rotation_euler = (math.radians(50), 0, math.radians(35)); sc.collection.objects.link(sun)
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam); sc.camera = cam
    cam.data.lens = 40
    sc.render.engine = "BLENDER_EEVEE_NEXT"; sc.view_settings.view_transform = "Standard"
    bpy.ops.wm.obj_import(filepath=os.path.join(R3, "MeatRack.obj"), forward_axis="NEGATIVE_Z", up_axis="Y", use_split_objects=False, use_split_groups=False)
    rack = bpy.context.selected_objects[0]
    rm = bpy.data.materials.new("rack"); rm.use_nodes = True
    rt = rm.node_tree.nodes.new("ShaderNodeTexImage"); rt.image = bpy.data.images.load(os.path.join(R3, "meatrack_atlas.png")); rt.interpolation = "Closest"
    rm.node_tree.links.new(rt.outputs["Color"], rm.node_tree.nodes["Principled BSDF"].inputs["Base Color"])
    rack.data.materials.clear(); rack.data.materials.append(rm)
    shown = []
    def show(name, b):
        for r in res:
            if r["name"] == name:
                io = bpy.data.objects.new(name, merged(name)["mesh"]); sc.collection.objects.link(io)
                io.matrix_world = Matrix.Translation(Vector(floor_centre(b))) @ Matrix(local_M(r).tolist()); shown.append(io)
    def look(yaw, pitch, dist, tgt):
        t = Vector(tgt)
        d = Vector((math.cos(math.radians(pitch)) * math.sin(math.radians(yaw)),
                    -math.cos(math.radians(pitch)) * math.cos(math.radians(yaw)), math.sin(math.radians(pitch))))
        cam.location = t + d * dist; cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    fb = sorted([bb for bb in range(NBIN) if floor_centre(bb)[1] < 0], key=lambda bb: abs(floor_centre(bb)[0]))[0]
    fc = floor_centre(fb)
    sc.render.resolution_x, sc.render.resolution_y = 480, 360
    tiles = []
    for name in ITEM:
        for o in shown: bpy.data.objects.remove(o)
        shown.clear(); show(name, fb)
        look(-10, 52, 1.0, (fc[0], fc[1], fc[2] + 0.12))
        fn = os.path.join(OUT, f"bin-{name}.png"); sc.render.filepath = fn
        bpy.ops.render.render(write_still=True); tiles.append((name, fn))
    lab = {n: "%s  x%.2f (%.2f m)  %dx4" % (n, ITEM[n]["s"], ITEM[n]["s"] * float(merged(n)["size"].max()), ITEM[n]["n"]) for n, _ in tiles}
    code = ("import sys,json;from PIL import Image,ImageDraw\n"
            "t=json.loads(sys.argv[1]);out=sys.argv[2];cols=7;W,H=480,360;rows=(len(t)+cols-1)//cols\n"
            "S=Image.new('RGB',(cols*W,rows*H),(30,30,30));d=ImageDraw.Draw(S)\n"
            "for i,(n,f,l) in enumerate(t):\n"
            " x,y=(i%cols)*W,(i//cols)*H;S.paste(Image.open(f).convert('RGB'),(x,y));d.rectangle((x,y,x+W,y+22),fill=(0,0,0));d.text((x+6,y+5),l,fill=(255,255,255))\n"
            "S.save(out)\n")
    subprocess.run(["python", "-c", code, json.dumps([(n, f, lab[n]) for n, f in tiles]), os.path.join(OUT, "bins-sheet.png")], check=False)

# ---------- the anchors json last (temp + rename: the mod live-reloads) ----------
if "--items" not in argv:
    out = os.path.join(OUTA, "MeatRackAnchors.json"); tmp = out + ".tmp"
    with open(tmp, "w") as fh: json.dump(doc, fh, indent=1)
    os.replace(tmp, out)
    print("R5 wrote", out, flush=True)
else:
    json.dump(doc, open(os.path.join(OUT, "meatrack_r5_partial.json"), "w"), indent=1)
print("DONE")
