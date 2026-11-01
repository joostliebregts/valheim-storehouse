"""Emergency Shelf round 2: a stackable wall-shelf MODULE (2 m and 1 m), our own mesh + own 128 px atlas.
Run: blender -b -P emergencyshelf_r2.py -- [--out DIR] [--tag NAME] [--views fills,close,alt,angle]
The contents are NOT in our model: the mod puts each stored item's own game model on the content ANCHORS
(assets/emergencyshelf_r2/emergencyshelf_r2.json). For the renders the real item models from the local rip
(C:/Users/joost/ValheimRip/items, reference only, never exported) are placed on exactly those anchors.

Module local space (Blender, z up, -y front): wall plane y=0, x centred, plank UNDERSIDE at z=0, plank top z=0.07.
Stack pitch 0.6 m (modules snap at k*0.6 m). Depth 0.45 m. Slots: 16 (2 m: 8 columns x back/front row), 8 (1 m).
Conversion to Unity prefab space (used for all numbers in the JSON): ux=-bx, uy=bz, uz=-by (front -y -> +z).
Yaw about Blender z = -yaw about Unity y (checked in code). The OBJ frame is exported like round 1
(forward NEGATIVE_Z, up Y, triangulated, no materials).

Atlas (128x128, v=0 bottom): v 0.75-1.00 hewn timber, v 0.50-0.75 weathered timber, v 0.25-0.50 end grain, v 0-0.25 iron.
"""
import bpy, bmesh, sys, os, math, json, random
import numpy as np
from mathutils import Vector, Matrix, Euler, Quaternion
from mathutils.bvhtree import BVHTree
sys.path.append("C:/Users/joost/ValheimRip/items")
from load_item import load_item

HERE = os.path.dirname(os.path.abspath(__file__))
OUTA = os.path.normpath(os.path.join(HERE, "..", "assets", "emergencyshelf_r2"))
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = argv[argv.index("--out") + 1] if "--out" in argv else OUTA
TAG = argv[argv.index("--tag") + 1] if "--tag" in argv else "emergencyshelf"
os.makedirs(OUTA, exist_ok=True); os.makedirs(OUT, exist_ok=True)
rng = random.Random(11)
ITEMROOT = "C:/Users/joost/ValheimRip/items"

TEX = 128; DENS = 48.0
STRIP = {"hewn": 0.75, "hewn2": 0.50, "end": 0.25, "iron": 0.0}
PITCH = 0.6            # stack pitch
DEPTH = 0.45
PLANK_T = 0.07

# ---------- texture ----------
def srgb(c): return np.array(c, dtype=np.float32)
WOOD, WOOD_D = srgb((0.38, 0.29, 0.18)), srgb((0.21, 0.16, 0.10))
WOOD2, WOOD2_D = srgb((0.33, 0.27, 0.19)), srgb((0.19, 0.155, 0.11))
END, END_D = srgb((0.55, 0.45, 0.31)), srgb((0.35, 0.27, 0.17))
IRON, IRON_D = srgb((0.22, 0.21, 0.20)), srgb((0.09, 0.09, 0.09))

def build_atlas():
    nr = np.random.default_rng(5)
    img = np.zeros((TEX, TEX, 3), np.float32)
    x = np.arange(TEX)[None, :].repeat(32, 0).astype(np.float32)
    y = np.arange(32)[:, None].repeat(TEX, 1).astype(np.float32)
    tile = lambda k: 2 * math.pi * k / TEX
    for base, (c0, c1), ph in ((96, (WOOD, WOOD_D), 0.0), (64, (WOOD2, WOOD2_D), 1.3)):
        g = np.sin(y * 1.25 + 1.6 * np.sin(x * tile(2) + y * 0.15 + ph) + 0.7 * np.sin(x * tile(5) + ph))
        t = np.clip((g - 0.55) * 2.5, 0, 1) * 0.65 + nr.random((32, TEX)) * 0.18
        t += np.clip(1 - np.minimum(y, 31 - y) / 3.0, 0, 1) * 0.35
        img[base:base + 32] = c0 * (1 - t[..., None]) + c1 * t[..., None]
    for k in range(4):
        cx, cy = 15.5 + nr.uniform(-2, 2), 15.5 + nr.uniform(-2, 2)
        xx, yy = np.meshgrid(np.arange(32), np.arange(32))
        d = np.hypot(xx - cx, yy - cy) + 0.6 * np.sin(np.arctan2(yy - cy, xx - cx) * 3 + k)
        t = (np.sin(d * 1.5) * 0.5 + 0.5) * 0.45 + nr.random((32, 32)) * 0.15
        t = np.where(d > 13.5, 0.95, t)
        img[32:64, 32 * k:32 * k + 32] = END * (1 - t[..., None]) + END_D * t[..., None]
    t = nr.random((32, TEX)) * 0.4 + np.clip(1 - np.minimum(y, 31 - y) / 4.0, 0, 1) * 0.5
    img[0:32] = IRON * (1 - t[..., None]) + IRON_D * t[..., None]
    im = bpy.data.images.new("emergencyshelf_r2_atlas", TEX, TEX, alpha=False)
    px = np.concatenate([np.clip(img, 0, 1), np.ones((TEX, TEX, 1), np.float32)], 2)
    im.pixels.foreach_set(px.ravel())
    im.filepath_raw = os.path.join(OUTA, "emergencyshelf_r2_atlas.png"); im.file_format = "PNG"; im.save()
    return im

# ---------- frame geometry ----------
CUR = []
def wood_uv(kind, long_axis, seed):
    def fn(f, uvl):
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
                l[uvl].uv = ((k + 0.5 + a * 0.45) / 4, STRIP["end"] + (0.5 + b * 0.45) / 4)
            return
        ua = long_axis if long_axis in tang else tang[0]
        va = tang[1] if ua == tang[0] else tang[0]
        off = (seed * 0.37) % 1
        vs = [l.vert.co[va] for l in f.loops]
        vmin, span = min(vs), max(max(vs) - min(vs), 1e-4)
        vscale = min(1.0, (32 / DENS) / span)
        base = STRIP[kind]
        for l in f.loops:
            l[uvl].uv = (l.vert.co[ua] * DENS / TEX + off, base + ((l.vert.co[va] - vmin) * vscale * DENS / TEX) * 0.94 + 0.0075)
    return fn

def commit(bm, name, uvfun, pos=(0, 0, 0), rot=(0, 0, 0), target=None):
    bm.normal_update()
    uvl = bm.loops.layers.uv.verify()
    for f in bm.faces: uvfun(f, uvl)
    if any(rot):
        bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Euler([math.radians(a) for a in rot]).to_matrix())
    bmesh.ops.translate(bm, verts=bm.verts, vec=Vector(pos))
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = False
    ob = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(ob)
    ob.data.materials.append(MAT)
    (CUR if target is None else target).append(ob)
    return ob

def timber(name, size, pos, kind="hewn", rot=(0, 0, 0), jitter=0.008, bevel=0.012, target=None):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts: v.co = Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2]))
    long_axis = max(range(3), key=lambda i: size[i])
    for v in bm.verts:
        for i in range(3):
            if i != long_axis: v.co[i] += rng.uniform(-jitter, jitter)
    if bevel > 0:
        bmesh.ops.bevel(bm, geom=bm.edges[:], offset=bevel, segments=1, affect="EDGES")
    return commit(bm, name, wood_uv(kind, long_axis, rng.randrange(1000)), pos, rot, target)

# usable zone for contents (module space)
Y_BACK, Y_FRONT = -0.055, -0.41
Y_SPLIT = -0.255
def build_frame(W, bx):
    """one module, plank underside z=0."""
    timber("ledger", (W - 0.04, 0.05, 0.15), (0, -0.025, 0.075), kind="hewn2", jitter=0.003, bevel=0.01, rot=(0, 0, rng.uniform(-0.2, 0.2)))
    for (y0, y1) in ((-0.052, -0.252), (-0.258, -0.45)):
        timber("plank", (W, abs(y1 - y0), PLANK_T), (0, (y0 + y1) / 2, PLANK_T / 2), jitter=0.0, bevel=0.01, rot=(0, 0, rng.uniform(-0.3, 0.3)))
    timber("lip", (W - 0.03, 0.035, 0.045), (0, -0.4325, 0.0925), kind="hewn2", jitter=0.002, bevel=0.0, rot=(0, 0, rng.uniform(-0.3, 0.3)))
    for xb in bx:
        timber("plate", (0.08, 0.04, 0.20), (xb, -0.02, -0.10), jitter=0.003, bevel=0.0)
        timber("arm", (0.08, 0.38, 0.06), (xb, -0.23, -0.03), jitter=0.003, bevel=0.0)
        dy, dz = -0.30, 0.14
        L = math.hypot(dy, dz)
        timber("brace", (0.06, L, 0.055), (xb, -0.04 + dy / 2, -0.19 + dz / 2), rot=(math.degrees(math.atan2(dz, dy)), 0, 0), jitter=0.002, bevel=0.008)
        for zz in (-0.05, -0.15):
            timber("bolt", (0.028, 0.02, 0.028), (xb + rng.uniform(-.006, .006), -0.045, zz), kind="iron", jitter=0.0, bevel=0.0)
        timber("strap", (0.05, 0.04, 0.056), (xb, -0.4325, 0.0975), kind="iron", jitter=0.0, bevel=0.003)

PIECES = {"2m": dict(W=2.0, cols=8, bx=(-0.8, 0.0, 0.8)), "1m": dict(W=1.0, cols=4, bx=(-0.36, 0.36))}

# ---------- items ----------
PROTO, INFO = {}, {}
def proto(name):
    if name not in PROTO:
        objs = load_item(name)
        for o in objs:
            for c in list(o.users_collection): c.objects.unlink(o)
        PROTO[name] = objs
        INFO[name] = json.load(open(f"{ITEMROOT}/{name}/info.json"))["size"]
    return PROTO[name]

def eff(name, yaw90):
    proto(name)
    sx, sy, sz = INFO[name]
    return (sy, sx, sz) if yaw90 else (sx, sy, sz)

VERTS = {}
def refine(cp, hx, hy):
    """shrink uniformly so the rotated, scaled item stays inside its cell (half sizes hx, hy around the offset)."""
    name = cp["item"]
    if name not in VERTS:
        proto(name); VERTS[name] = np.array([[v.co.x, v.co.y, v.co.z] for o in PROTO[name] for v in o.data.vertices])
    V = VERTS[name]; a = math.radians(cp["yaw"]); c, si = math.cos(a), math.sin(a)
    X = (V[:, 0] * c - V[:, 1] * si) * cp["s"]; Y = (V[:, 0] * si + V[:, 1] * c) * cp["s"]
    f = min(1.0, hx / max(abs(X).max(), 1e-6), hy / max(abs(Y).max(), 1e-6))
    cp["s"] *= f; cp["h"] *= f
    return cp

def spawn(name, loc, yaw, s, tag):
    made = []
    for o in proto(name):
        c = o.copy(); bpy.context.scene.collection.objects.link(c)
        c.location = Vector(loc); c.rotation_euler = (0, 0, math.radians(yaw)); c.scale = (s, s, s)
        c["unit"] = tag
        made.append(c)
    return made

# patterns for the front (food) row: layers of (dx, dy) cells, per-copy fit box, alignment
PAT = {
  "loaves": dict(kind="stack", align="x", fit=(0.23, 0.145, 0.09), layers=[[(0, 0)], [(0, 0)]], yawj=5),
  "legs":   dict(kind="pile",  align="x", fit=(0.22, 0.076, 0.08), layers=[[(0, -0.039), (0, 0.039)], [(0, 0)]], yawj=5),
  "bundles":dict(kind="bundle",align="x", fit=(0.22, 0.15, 0.06), layers=[[(0, 0)]] * 3, yawj=10),
  "plates": dict(kind="stack", align="x", fit=(0.23, 0.15, 0.06), layers=[[(0, 0)]] * 3, yawj=8),
  "slabs":  dict(kind="stack", align="x", fit=(0.22, 0.15, 0.08), layers=[[(0, 0)]] * 2, yawj=6),
  "bowls":  dict(kind="stack", align="up", fit=(0.113, 0.113, 0.08), layers=[[(-0.058, 0), (0.058, 0)]] * 2, yawj=180),
  "jars":   dict(kind="row",   align="up", fit=(0.074, 0.074, 0.13), layers=[[(-0.078, -0.039), (0, -0.039), (0.078, -0.039), (-0.078, 0.039), (0, 0.039), (0.078, 0.039)]], yawj=180),
  "wraps":  dict(kind="stack", align="x", fit=(0.22, 0.145, 0.08), layers=[[(0, 0)]] * 2, yawj=8),
}
BOT_H = (0.27, 0.29, 0.26, 0.30)
def unit_box(row, colw):
    if row == "back": return (colw, Y_BACK - Y_SPLIT, 0.30)
    return (colw, Y_SPLIT - Y_FRONT, 0.18)

def bottles(name, colw, k, r):
    """6 bottles: 3 across x 2 deep, one full stack of mead."""
    proto(name)
    fx, fy = colw / 3 * 1.06, 0.2 / 2 * 1.0
    H = BOT_H[k % 4]
    copies = []
    sx, sy, sz = INFO[name]
    s0 = min(H / sz, fx / sx, fy / sy); s90 = min(H / sz, fx / sy, fy / sx)
    y90 = s90 > s0 * 1.15
    s = max(s0, s90)
    for j, dy in enumerate((-0.05, 0.05)):
        for i, dx in enumerate((-colw / 3, 0.0, colw / 3)):
            copies.append(refine(dict(item=name, off=(dx, dy, 0.0), yaw=(90 if y90 else 0) + r.uniform(-12, 12), s=s, h=sz * s, layer=0,
                               fit=(fx, fy, H), align="upright"), fx / 2, fy / 2))
    return "row", copies

def food(name, pat, colw, r):
    proto(name)
    P = PAT[pat]; copies = []; z = 0.0
    for li, cells in enumerate(P["layers"]):
        hmax = 0
        for (dx, dy) in cells:
            sx, sy, sz = INFO[name]
            y90 = P["align"] == "x" and sx < sy
            e = eff(name, y90)
            s = min(P["fit"][0] / e[0], P["fit"][1] / e[1], P["fit"][2] / e[2])
            yaw = (90 if y90 else 0) + r.uniform(-P["yawj"], P["yawj"])
            if P["align"] == "up": yaw = r.uniform(-180, 180)
            ox = dx + (r.uniform(-0.008, 0.008) if P["align"] == "x" else 0)
            cp = refine(dict(item=name, off=(ox, dy, z), yaw=yaw, s=s, h=e[2] * s, layer=li, fit=P["fit"], align="long_axis_x" if P["align"] == "x" else "upright"),
                        P["fit"][0] / 2, P["fit"][1] / 2)
            copies.append(cp)
            hmax = max(hmax, cp["h"])
        z += hmax * 0.93
    return P["kind"], copies

ASSORT = [
  dict(back=["MeadHealthMinor", "MeadStaminaMinor", "MeadPoisonResist", "MeadHealthMedium", "MeadStaminaMedium", "MeadEitrMinor", "MeadStaminaLingering", "MeadHealthLingering"],
       front=[("Bread", "loaves"), ("CookedMeat", "legs"), ("Sausages", "bundles"), ("QueensJam", "jars"),
              ("MeatPlatter", "plates"), ("BloodPudding", "slabs"), ("CookedDeerMeat", "slabs"), ("Bread", "loaves")]),
  dict(back=["MeadStaminaMedium", "MeadHealthMedium", "MeadFrostResist", "MeadHealthMinor", "MeadTasty", "MeadPoisonResist", "MeadEitrMinor", "MeadStaminaMinor"],
       front=[("CarrotSoup", "bowls"), ("Bread", "loaves"), ("TurnipStew", "bowls"), ("MushroomOmelette", "plates"),
              ("FishWraps", "wraps"), ("Sausages", "bundles"), ("QueensJam", "jars"), ("CookedMeat", "legs")]),
  dict(back=["MeadHealthLingering", "MeadStaminaLingering", "MeadHealthMinor", "MeadStaminaMinor", "MeadEitrMinor", "MeadHealthMedium", "MeadPoisonResist", "MeadStaminaMedium"],
       front=[("QueensJam", "jars"), ("CookedDeerMeat", "slabs"), ("Bread", "loaves"), ("MeatPlatter", "plates"),
              ("Sausages", "bundles"), ("SerpentStew", "bowls"), ("CookedMeat", "legs"), ("FishWraps", "wraps")]),
]

def make_units(size, ai):
    cfg = PIECES[size]; W = cfg["W"]; cols = cfg["cols"]
    colw = (W - 0.1) / cols
    r = random.Random(40 + ai)
    A = ASSORT[ai % 3]
    units = []
    for c in range(cols):
        cx = -W / 2 + 0.05 + colw * (c + 0.5)
        for row in ("back", "front"):
            w, d, h = unit_box(row, colw)
            yc = (Y_BACK + Y_SPLIT) / 2 if row == "back" else (Y_SPLIT + Y_FRONT) / 2
            if row == "back": kind, copies = bottles(A["back"][c], colw, c, r)
            else: kind, copies = food(A["front"][c][0], A["front"][c][1], colw, r)
            top = max(cp["off"][2] + cp["h"] for cp in copies)
            if row == "front": h = max(h, top)
            units.append(dict(index=len(units), kind=kind, col=c, row=row, pos=(cx, yc, PLANK_T), box=(w, d, max(h, top)), copies=copies))
    return units

def place_units(units, origin, k):
    objs = []
    for u in units[:k]:
        for cp in u["copies"]:
            loc = (origin[0] + u["pos"][0] + cp["off"][0], origin[1] + u["pos"][1] + cp["off"][1],
                   origin[2] + u["pos"][2] + cp["off"][2] - 0.002)
            objs += spawn(cp["item"], loc, cp["yaw"], cp["s"], u["index"])
    return objs

# ---------- clip check ----------
def tri_list(ob):
    verts = [v.co.copy() for v in ob.data.vertices]; t = []
    for p in ob.data.polygons:
        idx = list(p.vertices)
        for k in range(1, len(idx) - 1): t.append((idx[0], idx[k], idx[k + 1]))
    return verts, t
def tris(obs): return sum(len(p.vertices) - 2 for o in obs for p in o.data.polygons)
RAYD = Vector((0.31, 0.52, 0.79)).normalized()
def inside_depth(tree, p):
    n, o = 0, p.copy()
    while n < 30:
        h = tree.ray_cast(o, RAYD)
        if h[0] is None: break
        n += 1; o = h[0] + RAYD * 1e-5
    if n % 2 == 0: return 0.0
    return tree.find_nearest(p)[3]

def clip_check(W, units, part_sets):
    """part_sets: frame parts (world == module space) of this module and its stack neighbours."""
    trees = []
    for parts in part_sets:
        for ob in parts:
            vs, ts = tri_list(ob)
            vs = [ob.matrix_world @ v for v in vs]
            bb = [min(v[i] for v in vs) for i in range(3)] + [max(v[i] for v in vs) for i in range(3)]
            trees.append((BVHTree.FromPolygons(vs, ts), bb))
    bad_items = []; bad_units = []; n_items = 0
    cache = {}
    for u in units:
        ux, uy, uz = u["pos"]; w, d, h = u["box"]
        if not (abs(ux) + w / 2 <= W / 2 - 0.03 + 1e-6 and uy - d / 2 >= Y_FRONT - 1e-6 and uy + d / 2 <= Y_BACK + 1e-6 and uz + h <= PITCH - 0.22 + 1e-6):
            bad_units.append(u["index"])
        for cp in u["copies"]:
            n_items += 1; why = None
            proto(cp["item"]); o0 = PROTO[cp["item"]][0]
            M = Matrix.Translation((ux + cp["off"][0], uy + cp["off"][1], uz + cp["off"][2] - 0.002)) @ \
                Matrix.Rotation(math.radians(cp["yaw"]), 4, "Z") @ Matrix.Scale(cp["s"], 4)
            if cp["item"] not in cache: cache[cp["item"]] = [v.co.copy() for v in o0.data.vertices]
            for v in cache[cp["item"]]:
                p = M @ v
                if abs(p.x) > W / 2 - 0.03: why = "x"
                elif not (Y_FRONT - 0.002 <= p.y <= Y_BACK + 0.002): why = "y"
                elif p.z > PITCH - 0.22 + 0.003: why = "z-top"
                else:
                    for (t, bb) in trees:
                        if all(bb[i] - 0.01 <= p[i] <= bb[i + 3] + 0.01 for i in range(3)):
                            if inside_depth(t, p) > 0.006: why = "inside frame"; break
                if why: break
            if why: bad_items.append((u["index"], cp["item"], why))
    return bad_items, bad_units, n_items

# ---------- unity conversion ----------
MB2U = Matrix(((-1, 0, 0), (0, 0, 1), (0, -1, 0)))
def u_vec(v): return [round(-v[0], 4), round(v[2], 4), round(-v[1], 4)]
def u_euler(yaw_deg, tilt=(0, 0)):
    Rb = Euler((math.radians(tilt[0]), math.radians(tilt[1]), math.radians(yaw_deg)), "XYZ").to_matrix()
    Ru = MB2U @ Rb @ MB2U.transposed()
    e = Ru.to_euler("ZXY")   # Unity applies Z, then X, then Y
    return [round(math.degrees(e.x), 2), round(math.degrees(e.y), 2), round(math.degrees(e.z), 2)]
assert abs(u_euler(30)[1] + 30) < 0.01, u_euler(30)   # Blender yaw +30 -> Unity yaw -30

# ---------- scene ----------
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
atlas = build_atlas()
MAT = bpy.data.materials.new("emergencyshelf"); MAT.use_nodes = True
nt = MAT.node_tree; bsdf = nt.nodes["Principled BSDF"]
ti = nt.nodes.new("ShaderNodeTexImage"); ti.image = atlas; ti.interpolation = "Closest"
nt.links.new(ti.outputs["Color"], bsdf.inputs["Base Color"]); bsdf.inputs["Roughness"].default_value = 0.8
POSTMAT = bpy.data.materials.new("post"); POSTMAT.use_nodes = True
POSTMAT.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.55, 0.58, 0.62, 1)
WALLMAT = bpy.data.materials.new("wall"); WALLMAT.use_nodes = True
wn = WALLMAT.node_tree; wt = wn.nodes.new("ShaderNodeTexImage"); wt.image = atlas; wt.interpolation = "Closest"
wm = wn.nodes.new("ShaderNodeMixRGB"); wm.blend_type = "MULTIPLY"; wm.inputs[0].default_value = 1.0
wm.inputs[2].default_value = (0.82, 0.80, 0.78, 1)
wn.links.new(wt.outputs["Color"], wm.inputs[1]); wn.links.new(wm.outputs["Color"], wn.nodes["Principled BSDF"].inputs["Base Color"])
wn.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.85

def join(obs, name):
    bpy.ops.object.select_all(action="DESELECT")
    for o in obs: o.select_set(True)
    bpy.context.view_layer.objects.active = obs[0]
    bpy.ops.object.join(); ob = bpy.context.active_object; ob.name = name
    return ob

def frame_at(size, origin, seed=11):
    rng.seed(seed); CUR.clear()
    build_frame(PIECES[size]["W"], PIECES[size]["bx"])
    parts = list(CUR)
    for o in parts: o.location = Vector(origin)
    bpy.context.view_layer.update()
    return parts

STATS = {}; JS = {}
def export_piece(size):
    cfg = PIECES[size]; W = cfg["W"]
    units = make_units(size, 0)
    parts = frame_at(size, (0, 0, 0))
    up = frame_at(size, (0, 0, PITCH)); dn = frame_at(size, (0, 0, -PITCH))
    bad_i, bad_u, n = clip_check(W, units, [parts, up, dn])
    print(f"CLIPPING {len(bad_i)} of {n}", bad_i, "UNIT BOXES BAD", bad_u, "of", len(units), "size", size)
    for o in up + dn: bpy.data.objects.remove(o, do_unlink=True)
    ft = tris(parts)
    frame = join(parts, f"EmergencyShelfModule{size}")
    bpy.ops.object.select_all(action="DESELECT"); frame.select_set(True)
    bpy.ops.wm.obj_export(filepath=os.path.join(OUTA, f"EmergencyShelfModule{size}.obj"), export_selected_objects=True,
                          export_materials=False, export_triangulated_mesh=True, forward_axis="NEGATIVE_Z", up_axis="Y")
    bpy.data.objects.remove(frame, do_unlink=True)
    ju = []
    for u in units:
        w, d, h = u["box"]
        pos = u["pos"]
        ju.append(dict(index=u["index"], kind=u["kind"], column=u["col"], row=u["row"],
                       position=u_vec((pos[0], pos[1], pos[2])), rotation=[0, 0, 0],
                       box_size=[round(w, 4), round(h, 4), round(d, 4)],
                       copies=[dict(offset=u_vec(cp["off"]), euler=u_euler(cp["yaw"]), fit_box=[round(cp["fit"][0], 4), round(cp["fit"][2], 4), round(cp["fit"][1], 4)],
                                    align=cp["align"], layer=cp["layer"], layer_pitch_hint=round(cp["fit"][2] * 0.93, 4),
                                    demo_item=cp["item"], demo_scale=round(cp["s"], 4)) for cp in u["copies"]]))
    JS[size] = dict(frame_obj=f"EmergencyShelfModule{size}.obj", frame_tris=ft, slots=len(units), units_at_100=len(units),
                    width=W, depth=DEPTH, stack_pitch=PITCH, clipping=len(bad_i), unit_boxes_bad=len(bad_u),
                    items_checked=n, units=ju)
    STATS[size] = (ft, len(units), len(bad_i), n)

def wall_panel(ox, h=2.0):
    wall = []
    rng.seed(5)
    for k in range(8):
        hh = h + rng.uniform(-0.015, 0.015)
        timber("wall", (0.248, 0.07, hh), (ox - 0.875 + k * 0.25, 0.04, hh / 2), jitter=0.004, bevel=0.01,
               rot=(0, rng.uniform(-0.3, 0.3), rng.uniform(-0.4, 0.4)), target=wall)
    for o in wall: o.data.materials[0] = WALLMAT

def post_at(x, y):
    post = bpy.data.objects.new("post", bpy.data.meshes.new("post"))
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts: v.co = Vector((v.co.x * 0.1, v.co.y * 0.1, v.co.z * 1.8 + 0.9))
    bm.to_mesh(post.data); bm.free()
    for p in post.data.polygons: p.use_smooth = False
    post.data.materials.append(POSTMAT); post.location = (x, y, 0)
    bpy.context.scene.collection.objects.link(post)

def vanilla_chest(ox, oy):
    RIP = "C:/Users/joost/ValheimRip/chests/piece_chest_wood"
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
        M = Matrix.Translation(Vector(node["pos"])) @ Quaternion((q[3], q[0], q[1], q[2])).to_matrix().to_4x4() @ Matrix.Diagonal((*node["scale"], 1))
        verts = [M @ v for v in V]
        verts = [Vector((-v.x + ox, -v.z + oy, v.y)) for v in verts]
        F = [list(reversed(f)) for f in F]
        me = bpy.data.meshes.new("ref"); me.from_pydata(verts, [], [[c[0] for c in f] for f in F])
        uvl = me.uv_layers.new(); i = 0
        for f in F:
            for c in f: uvl.data[i].uv = T[c[1]]; i += 1
        ob = bpy.data.objects.new("ref", me); sc.collection.objects.link(ob); ob.data.materials.append(vm)

for sz in ("2m", "1m"): export_piece(sz)
json.dump(dict(atlas="emergencyshelf_r2_atlas.png",
               conversion="Blender z-up/-y front -> Unity y-up/+z front: ux=-bx, uy=bz, uz=-by. Euler = Unity (x,y,z) applied Z, X, Y. Module origin: wall plane, centred in x, plank underside = y 0 (plank top y 0.07).",
               how_to_use="For each unit i < filled slots: place the stored item's own model at each copy: bottom-centre at unit.position+copy.offset, rotate by copy.euler, then scale the model UNIFORMLY to fit copy.fit_box (Unity axes x,y,z). align=long_axis_x: first yaw the model so its longest horizontal extent lies along x. layer>0: raise by layer * fitted-height*0.93 of the layer below (layer_pitch_hint is the nominal value). Units fill in index order.",
               kinds="row = standing items in rows; stack = layered flat items; bundle = layered flat bunches; pile = pyramid",
               pieces=JS), open(os.path.join(OUTA, "emergencyshelf_r2.json"), "w"), indent=1)
print("STATS", STATS)

# ----- render scenes -----
ZB = 0.35
def module(size, origin, ai, fill):
    frame_at(size, origin)
    units = make_units(size, ai)
    k = max(1, round(fill * len(units)))
    place_units(units, origin, k)
    return k

SX = [-4.4, 0.0, 4.4]
for si, x in enumerate(SX):                       # stacks of 1, 2, 3 modules
    wall_panel(x)
    for m in range(si + 1): module("2m", (x, 0, ZB + PITCH * m), m, 1.0)
LX = 30.0
for li, (x, f) in enumerate(zip(SX, (0.1, 0.5, 1.0))):    # one module at 10/50/100
    wall_panel(LX + x)
    module("2m", (LX + x, 0, 0.95), 0, f)
vanilla_chest(-2.2, -0.3); post_at(2.2, -0.4)
vanilla_chest(LX - 2.2, -0.3); post_at(LX + 2.2, -0.4)

world = bpy.data.worlds.new("w"); sc.world = world; world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.42, 0.45, 0.5, 1)
world.node_tree.nodes["Background"].inputs[1].default_value = 0.9
sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN")); sun.data.energy = 3.2
sun.rotation_euler = (math.radians(50), 0, math.radians(35)); sc.collection.objects.link(sun)
bpy.ops.mesh.primitive_plane_add(size=120, location=(15, 0, 0))
gm = bpy.data.materials.new("ground"); gm.use_nodes = True
gm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.16, 0.14, 0.11, 1)
bpy.context.active_object.data.materials.append(gm)
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam); sc.camera = cam
sc.render.engine = "BLENDER_EEVEE_NEXT"
sc.view_settings.view_transform = "Standard"
VIEWS = {"fills": (0, 9, 12.0, (0, 0, 1.0), 35, (3600, 1200)),
         "alt": (0, 9, 12.0, (LX, 0, 1.0), 35, (3600, 1200)),
         "close": (-16, 22, 3.7, (LX + 4.4, 0, 1.0), 50, (1800, 1000)),
         "angle": (-40, 16, 6.5, (4.4, 0, 1.1), 50, (1800, 1000))}
only = argv[argv.index("--views") + 1].split(",") if "--views" in argv else list(VIEWS)
for vn in only:
    yaw, pitch, dist, tgt, lens, res = VIEWS[vn]
    sc.render.resolution_x, sc.render.resolution_y = res
    cam.data.lens = lens; t = Vector(tgt)
    d = Vector((math.cos(math.radians(pitch)) * math.sin(math.radians(yaw)),
                -math.cos(math.radians(pitch)) * math.cos(math.radians(yaw)), math.sin(math.radians(pitch))))
    cam.location = t + d * dist; cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    sc.render.filepath = os.path.join(OUT, f"{TAG}-{vn}.png")
    bpy.ops.render.render(write_still=True)
print("DONE")
