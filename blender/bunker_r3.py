"""Coal & Stone Bunker, round 3: contents are SETTLED with a Blender rigid body simulation (gravity-stacked, one material per bay).
Run: blender -b -P bunker_r3.py -- [--out DIR] [--tag NAME] [--no-ref] [--rounds N] [--seed N]
Writes into assets/bunker_r3/: Bunker.obj (frame only, forward -Z, up Y, triangulated, no materials),
bunker_atlas.png (128x128, point filtered) and bunker_anchors.json (explicit settled pose of every lump, in fill order).
Bay 0 coal, bay 1 stone, bay 2 grausten. The item models come from C:/Users/joost/ValheimRip/items and are NOT part of any exported file.

Atlas 128x128 (horizontal strips that tile along u):
  v 0.75-1.00 hewn timber side grain (32 px)   v 0.50-0.75 end grain (4 ring tiles of 32 px)
  v 0.375-0.5 iron (16 px)                     v 0.00-0.375 unused (reserved)

ANCHOR CONVENTION (unchanged from round 2). Blender (z up, -y front) -> Unity prefab space (y up, +z front):  ux=-bx, uy=bz, uz=-by.
As a matrix C = [[-1,0,0],[0,0,1],[0,-1,0]]. Rotations: R_unity = C R_blender C^-1, written as quaternion (x,y,z,w) and as
Unity euler degrees (Unity order Z, X, Y = Ry*Rx*Rz). Copy offsets are relative to the unit position (= bounds centre of the
unit's copies) and locate each item's BOUNDS CENTRE; scale multiplies the item's natural prefab scale.
"""
import bpy, bmesh, sys, os, math, json, random
import numpy as np
from mathutils import Vector, Matrix, Euler, Quaternion
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUTA = argv[argv.index("--assets") + 1] if "--assets" in argv else os.path.normpath(os.path.join(HERE, "..", "assets", "bunker_r3"))
OUT = argv[argv.index("--out") + 1] if "--out" in argv else OUTA
TAG = argv[argv.index("--tag") + 1] if "--tag" in argv else "bunker"
RIP = "C:/Users/joost/ValheimRip/chests/piece_chest_wood"
ITEMS_DIR = "C:/Users/joost/ValheimRip/items"
os.makedirs(OUTA, exist_ok=True); os.makedirs(OUT, exist_ok=True)
sys.path.append(ITEMS_DIR)
from load_item import load_item
rng = random.Random(7)      # frame
crng = random.Random(23)    # contents (own stream so the frame never shifts)

TEX = 128
DENS = 48.0                                                    # px per metre, vanilla wood is 47-57
STRIP = {"hewn": 0.75, "end": 0.50, "iron": 0.375}
STRIPH = {"hewn": 32, "iron": 16}

# ---------- texture ----------
def srgb(c): return np.array(c, dtype=np.float32)
# calmer, slightly greyer wood than round 1; iron unchanged
WOOD, WOOD_D = srgb((0.36, 0.29, 0.20)), srgb((0.20, 0.16, 0.11))
END, END_D = srgb((0.50, 0.42, 0.31)), srgb((0.33, 0.27, 0.19))
IRON, IRON_D = srgb((0.22, 0.21, 0.20)), srgb((0.09, 0.09, 0.09))

def build_atlas():
    nr = np.random.default_rng(3)
    img = np.full((TEX, TEX, 3), 0.5, np.float32)          # row 0 = v 0 (bottom); lower part unused
    x = np.arange(TEX)[None, :].repeat(32, 0).astype(np.float32)
    y = np.arange(32)[:, None].repeat(TEX, 1).astype(np.float32)
    tile = lambda k: 2 * math.pi * k / TEX
    g = np.sin(y * 1.25 + 1.6 * np.sin(x * tile(2) + y * 0.15) + 0.7 * np.sin(x * tile(5)))
    t = np.clip((g - 0.55) * 2.5, 0, 1) * 0.65 + nr.random((32, TEX)) * 0.18
    t += np.clip(1 - np.minimum(y, 31 - y) / 3.0, 0, 1) * 0.35
    img[96:128] = WOOD * (1 - t[..., None]) + WOOD_D * t[..., None]
    for k in range(4):
        cx, cy = 15.5 + nr.uniform(-2, 2), 15.5 + nr.uniform(-2, 2)
        xx, yy = np.meshgrid(np.arange(32), np.arange(32))
        d = np.hypot(xx - cx, yy - cy) + 0.6 * np.sin(np.arctan2(yy - cy, xx - cx) * 3 + k)
        t = (np.sin(d * 1.5) * 0.5 + 0.5) * 0.45 + nr.random((32, 32)) * 0.15
        t = np.where(d > 13.5, 0.95, t)
        img[64:96, 32 * k:32 * k + 32] = END * (1 - t[..., None]) + END_D * t[..., None]
    yi = np.arange(16)[:, None].repeat(TEX, 1).astype(np.float32)
    t = nr.random((16, TEX)) * 0.4 + np.clip(1 - np.minimum(yi, 15 - yi) / 3.0, 0, 1) * 0.5
    img[48:64] = IRON * (1 - t[..., None]) + IRON_D * t[..., None]
    im = bpy.data.images.new("bunker_atlas", TEX, TEX, alpha=False)
    px = np.concatenate([np.clip(img, 0, 1), np.ones((TEX, TEX, 1), np.float32)], 2)
    im.pixels.foreach_set(px.ravel())
    im.filepath_raw = os.path.join(OUTA, "bunker_atlas.png"); im.file_format = "PNG"; im.save()
    return im

# ---------- geometry helpers ----------
PARTS = []     # frame objects

def uv_face(f, kind, long_axis, seed):
    n = f.normal
    ax = max(range(3), key=lambda i: abs(n[i]))
    tang = [i for i in range(3) if i != ax]
    if kind != "iron" and ax == long_axis:          # cut end of a timber
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
    used = span * vscale * DENS / TEX * 0.94
    room = max(hpx / TEX - used - 0.012, 0)
    voff = ((seed * 0.618) % 1) * room
    for l in f.loops:
        u = l.vert.co[ua] * DENS / TEX + off
        v = STRIP[kind] + ((l.vert.co[va] - vmin) * vscale * DENS / TEX) * 0.94 + 0.0075 + voff
        l[UV].uv = (u, v)

def timber(name, size, pos, kind="hewn", rot=(0, 0, 0), jitter=0.022, bevel=0.022):
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

# ---------- layout ----------
BW = 1.20                      # bay pitch (post centre to post centre); three bays
PXS = [-1.5 * BW, -0.5 * BW, 0.5 * BW, 1.5 * BW]
P = 0.20                       # posts are P x P
YF, YB = -0.70, 0.70           # front post centre y, back post base centre y
T = math.radians(8.0)          # back wall lean (top moves back)
sT, cT = math.sin(T), math.cos(T)
HF = 1.15                      # front post height
HB = 1.72                      # back post length along its axis
PITCH, PH = 0.22, 0.20         # plank pitch / height
NPL = 7
BAYS = [(PXS[i] + 0.135, PXS[i + 1] - 0.135) for i in range(3)]     # contents x bounds per bay
YF_IN = YF + 0.15              # contents front bound (boards and cleats lie in front of it)
Z_FLOOR_FRAME = 0.118; FLOOR_COLL = 0.118; Z_FLOOR = 0.14                 # contents floor (slat tops are 0.11 + jitter)
N_MAX = -0.115                 # contents back bound in the leaning back wall's normal coordinate

def tilt_pt(s, n):
    """Point on the back wall: s along the lean, n along its outward normal (post axis n=0). Returns (y, z)."""
    return YB + s * sT + n * cT, s * cT - n * sT

def build_frame():
    WID = PXS[-1] - PXS[0]
    # ---- posts: 4 front (straight), 4 back (leaning)
    for sx in PXS:
        h = HF + rng.uniform(-0.02, 0.03)
        timber("post", (P, P, h), (sx, YF, h / 2), rot=(rng.uniform(-1, 1), rng.uniform(-1, 1), 0))
        y, z = tilt_pt(HB / 2, 0)
        timber("post", (P, P, HB), (sx, y, z), rot=(-math.degrees(T) + rng.uniform(-0.8, 0.8), rng.uniform(-1, 1), 0))
    # ---- sills
    timber("sill", (WID + 0.34, 0.22, 0.18), (0, YF, 0.09), rot=(0, 0, rng.uniform(-0.5, 0.5)), bevel=0)
    timber("sill", (WID + 0.34, 0.22, 0.18), (0, YB + 0.04, 0.09), rot=(0, 0, rng.uniform(-0.5, 0.5)), bevel=0)
    for sx in PXS:
        timber("sill", (0.22, 1.62, 0.16), (sx, 0.02, 0.08), bevel=0)
    # ---- floor slats under each bay (run front-back)
    for (xl, xr) in BAYS:
        n = 5
        for k in range(n):
            xs = xl + (k + 0.5) * (xr - xl) / n
            timber("slat", (0.17, 1.26, 0.10), (xs, 0.03, 0.06), bevel=0, jitter=0.006)
    # ---- back wall: leaning planks flush with the post inner side
    for i in range(NPL):
        s = 0.11 + PITCH * i
        y, z = tilt_pt(s, -0.04)
        timber("backplank", (WID + 0.24, 0.10, PH), (0, y, z),
               rot=(-math.degrees(T) + rng.uniform(-0.6, 0.6), 0, rng.uniform(-0.4, 0.4)))
    y, z = tilt_pt(HB - 0.02, 0.0)
    timber("backcap", (WID + 0.34, 0.20, 0.11), (0, y, z), rot=(-math.degrees(T), 0, rng.uniform(-0.3, 0.3)))
    # ---- side walls and dividers: planks run front-back, top edge steps up to the back
    slope = (tilt_pt(HB, 0)[1] + 0.05 - (HF + 0.05)) / (tilt_pt(HB, 0)[0] - YF)
    walls = [(PXS[0] + 0.04, 0.10), (PXS[1], 0.16), (PXS[2], 0.16), (PXS[3] - 0.04, 0.10)]
    for sx, th in walls:
        for i in range(NPL):
            zc = 0.11 + PITCH * i
            top = zc + PH / 2
            y0 = YF if top <= HF else YF + (top - HF) / slope
            y1 = YB + zc * math.tan(T) + 0.06
            if y1 - y0 < 0.12: continue
            timber("sideplank", (th, y1 - y0, PH), (sx, (y0 + y1) / 2, zc), rot=(0, rng.uniform(-0.4, 0.4), 0))
    # sloped cap beams over the four walls
    ay, az = YF, HF + 0.05
    by, bz = tilt_pt(HB, 0)
    bz += 0.05
    ang = math.degrees(math.atan2(bz - az, by - ay))
    ln = math.hypot(by - ay, bz - az) + 0.14
    for sx in PXS:
        timber("cap", (P + 0.04, ln, 0.11), (sx, (ay + by) / 2, (az + bz) / 2), rot=(ang, 0, rng.uniform(-0.3, 0.3)))
    # ---- front board slots: two cleats on each bay-facing post side, boards slide in between
    for i in range(3):
        xa, xb = PXS[i], PXS[i + 1]
        for cx in (xa + P / 2 + 0.02, xb - P / 2 - 0.02):
            for dy in (-0.06, 0.06):
                timber("cleat", (0.04, 0.04, 0.88), (cx, YF + dy, 0.55), jitter=0.004, bevel=0)
        bx = (xa + xb) / 2
        lift = 0.15 if i == 2 else 0.0         # right bay: top board pulled half out of its slot
        for j in range(3):
            zc = 0.11 + 0.22 * j + 0.1 + (lift if j == 2 else 0)
            timber("board", (BW - P + 0.03, 0.08, PH), (bx, YF, zc), jitter=0.012, bevel=0.016,
                   rot=(0, rng.uniform(-0.3, 0.3), rng.uniform(-0.5, 0.5) + (2.5 if (j == 2 and lift) else 0)))
            if j == 2:
                timber("pull", (0.10, 0.025, 0.06), (bx, YF - 0.055, zc), kind="iron", jitter=0.002, bevel=0)
    # ---- iron: a band round every post top, a strap low on each front post, rivets
    for sx in PXS:
        timber("band", (P + 0.04, P + 0.04, 0.08), (sx, YF, HF - 0.03), kind="iron", jitter=0.003, bevel=0.006)
        y, z = tilt_pt(HB - 0.07, 0)
        timber("band", (P + 0.04, P + 0.04, 0.08), (sx, y, z), kind="iron", jitter=0.003, bevel=0.006,
               rot=(-math.degrees(T), 0, 0))
        timber("strap", (P + 0.05, 0.02, 0.14), (sx, YF - P / 2 - 0.008, 0.30), kind="iron", jitter=0.003, bevel=0)
        timber("strap", (P + 0.05, 0.02, 0.14), (sx, YF - P / 2 - 0.008, 0.80), kind="iron", jitter=0.003, bevel=0)
        for dx in (-0.06, 0.06):
            timber("rivet", (0.035, 0.03, 0.035), (sx + dx, YF - P / 2 - 0.022, 0.30), kind="iron", jitter=0, bevel=0)
    # long iron straps over the back wall planks (one per bay centre)
    for sx in [(PXS[i] + PXS[i + 1]) / 2 for i in range(3)]:
        y, z = tilt_pt(0.65, 0.07)
        timber("backstrap", (0.10, 0.02, 1.0), (sx, y, z), kind="iron", jitter=0.003, bevel=0,
               rot=(-math.degrees(T), 0, 0))


# ---------- real item models (render only; never exported) ----------
BAY_ITEM = ["Coal", "Stone", "Flint"]        # ONE material per bay
BBOX_VOL = {"Coal": 0.0075, "Stone": 0.0075, "Flint": 0.0065, "Grausten": 0.0085}   # bbox volume of one lump at natural stack scale (m3), as round 2
TPL = {}

def load_templates():
    for nm in sorted(set(BAY_ITEM)):
        objs = [o for o in load_item(nm, anchor="center") if o.type == "MESH"]
        o = objs[0]
        V = np.array([v.co[:] for v in o.data.vertices], dtype=np.float64)
        ctr = (V.min(0) + V.max(0)) / 2
        o.data.transform(Matrix.Translation(-Vector(ctr)))          # exact bounds centre at the origin
        V = V - ctr
        size = V.max(0) - V.min(0)
        base = (BBOX_VOL[nm] / float(np.prod(size))) ** (1 / 3)
        F = [tuple(p.vertices) for p in o.data.polygons]
        TPL[nm] = dict(mesh=o.data, V=V, F=F, size=size, base=base)
        for x in objs: bpy.data.objects.remove(x, do_unlink=True)

# ---------- anchor export (Unity space) ----------
C = Matrix(((-1, 0, 0), (0, 0, 1), (0, -1, 0)))
Cinv = C.inverted()
def u_vec(v): return [round(-v.x, 4), round(v.z, 4), round(-v.y, 4)]
ROTERR = [0.0]
def u_rot(Rb):
    Ru = C @ Rb @ Cinv
    q = Ru.to_quaternion()
    eu = Ru.to_euler("ZXY")      # matrix = Ry(eu.y) * Rx(eu.x) * Rz(eu.z), the Unity euler order
    rec = Matrix.Rotation(eu.y, 3, "Y") @ Matrix.Rotation(eu.x, 3, "X") @ Matrix.Rotation(eu.z, 3, "Z")
    ROTERR[0] = max(ROTERR[0], max(abs(Ru[i][j] - rec[i][j]) for i in range(3) for j in range(3)))
    return [round(math.degrees(eu.x), 2), round(math.degrees(eu.y), 2), round(math.degrees(eu.z), 2)], \
           [round(q.x, 5), round(q.y, 5), round(q.z, 5), round(q.w, 5)]

# ---------- geometry of the contents volume ----------
def yb_at(z): return YB + (N_MAX + z * sT) / cT        # y of the contents back bound at height z
def nrm(y, z): return (y - YB) * cT - z * sT
def lump_world(L):
    tp = TPL[L["item"]]
    M = Matrix.Translation(L["loc"]) @ L["rot"].to_4x4() @ Matrix.Diagonal((L["s"],) * 3 + (1,))
    return M, [M @ Vector(v) for v in tp["V"]]

# ---------- rigid body simulation ----------
SIM_SUBSTEPS, SIM_ITERS = 20, 30
MAXF = 260
UNIT_N = 6                                                   # lumps per unit (one stack)
ROUNDS = int(argv[argv.index("--rounds") + 1]) if "--rounds" in argv else 18
def argf(n, d): return float(argv[argv.index(n) + 1]) if n in argv else d
FRIC, LDAMP, ADAMP = argf("--fric", 0.7), argf("--lin", 0.2), argf("--ang", 0.4)
DW0, DW1 = argf("--dw0", 0.20), argf("--dw1", 0.70)
DEBUG = '--debug' in argv
SEED = int(argv[argv.index("--seed") + 1]) if "--seed" in argv else 11
drng = random.Random(SEED)

def rb_add(ob, typ, shape, margin, mass=1.0):
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True); bpy.context.view_layer.objects.active = ob
    bpy.ops.rigidbody.object_add(type=typ)
    rb = ob.rigid_body
    rb.collision_shape = shape
    rb.friction = FRIC; rb.restitution = 0.0
    rb.use_margin = True; rb.collision_margin = margin
    if typ == "ACTIVE":
        rb.mass = mass; rb.linear_damping = LDAMP; rb.angular_damping = ADAMP
        rb.use_deactivation = True; rb.deactivate_linear_velocity = 0.08; rb.deactivate_angular_velocity = 0.3
    if shape in ("MESH", "CONVEX_HULL"): rb.mesh_source = "BASE"

COLL = []
def box_collider(name, lo, hi, rot=None, centre=None, dims=None):
    """axis aligned slab between lo and hi, or an oriented slab (centre, dims, rot euler)"""
    if centre is None:
        centre = [(lo[i] + hi[i]) / 2 for i in range(3)]; dims = [hi[i] - lo[i] for i in range(3)]
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=centre)
    ob = bpy.context.active_object; ob.name = name; ob.scale = dims
    if rot: ob.rotation_euler = rot
    rb_add(ob, "PASSIVE", "BOX", 0.0005)
    COLL.append(ob); return ob

def build_colliders():
    BIG = 0.6
    XL, XR = BAYS[0][0], BAYS[2][1]
    ZF = FLOOR_COLL
    box_collider("c_floor", (XL - BIG, YF_IN - BIG, ZF - BIG), (XR + BIG, 1.6, ZF))
    box_collider("c_front", (XL - BIG, YF_IN - BIG, ZF - 0.2), (XR + BIG, YF_IN, 3.0))
    box_collider("c_wall_l", (XL - BIG, YF_IN - 0.2, ZF - 0.2), (XL, 1.6, 3.0))
    box_collider("c_wall_r", (XR, YF_IN - 0.2, ZF - 0.2), (XR + BIG, 1.6, 3.0))
    for i in range(2):
        box_collider("c_div%d" % i, (BAYS[i][1], YF_IN - 0.2, ZF - 0.2), (BAYS[i + 1][0], 1.6, 3.0))
    # leaning back wall: slab whose inner face is the plane n = N_MAX
    thick, s_len, s_c = 0.8, 4.0, 1.0
    y, z = YB + s_c * sT + (N_MAX + thick / 2) * cT, s_c * cT - (N_MAX + thick / 2) * sT
    box_collider("c_back", None, None, rot=(-T, 0, 0), centre=(0, y, z), dims=(XR - XL + 2 * BIG, thick, s_len))

def mesh_bvh(lumps):
    V, F = [], []
    for L in lumps:
        tp = TPL[L["item"]]; _, W = lump_world(L)
        base = len(V); V += W
        for p in tp["F"]: F.append(tuple(base + i for i in p))
    return BVHTree.FromPolygons(V, F) if F else None

def top_z(bvh, x, y):
    if bvh is None: return FLOOR_COLL
    h = bvh.ray_cast(Vector((x, y, 3.0)), Vector((0, 0, -1)))
    return max(FLOOR_COLL, h[0].z if h[0] is not None else FLOOR_COLL)

def plan_drop(bay, rnd, lumps, bvh):
    """6 drop poses for this unit: near the back wall, random rotation, xy jitter, dropped from just above the heap"""
    xl, xr = BAYS[bay]
    item = BAY_ITEM[bay]; tp = TPL[item]
    xm = 0.15
    cx = xl + xm + ((rnd * 0.6180339 + bay * 0.37) % 1.0) * (xr - xl - 2 * xm)
    dwall = drng.uniform(DW0, DW1)
    chosen = []
    for k in range(UNIT_N):
        for attempt in range(60):
            x = min(max(cx + drng.gauss(0, 0.20), xl + xm), xr - xm)
            zt = top_z(bvh, x, yb_at(1.0) - 0.45)
            y = yb_at(zt + 0.4) - max(0.19, dwall + drng.gauss(0, 0.12))
            if all((x - a) ** 2 + (y - b) ** 2 > 0.30 ** 2 for a, b, _ in chosen): break
        zt = top_z(bvh, x, y)
        chosen.append((x, y, zt))
    order = sorted(range(UNIT_N), key=lambda i: chosen[i][2])
    zmax = max(c[2] for c in chosen)
    out = []
    for rank, i in enumerate(order):
        x, y, zt = chosen[i]
        s0 = tp["base"] * drng.uniform(0.90, 1.10)
        e = Euler((drng.uniform(0, 6.283), drng.uniform(0, 6.283), drng.uniform(0, 6.283)), "XYZ")
        z = max(zt, zmax - 0.1) + 0.17 + 0.05 * rank
        out.append(dict(item=item, loc=Vector((x, y, z)), rot=e.to_matrix(), s=s0, bay=bay))
    # never start inside the settled heap or inside a sibling: lift until the real meshes are clear of each other
    done = []
    for L in out:
        for _ in range(60):
            _, W = lump_world(L)
            lb = BVHTree.FromPolygons([tuple(w) for w in W], tp["F"])
            if (bvh is not None and len(lb.overlap(bvh)) > 0) or any(len(lb.overlap(o)) > 0 for o in done): L["loc"].z += 0.03
            else: break
        L["loc"].z += 0.01
        _, W = lump_world(L)
        done.append(BVHTree.FromPolygons([tuple(w) for w in W], tp["F"]))
    return out

SIMOBJ = []
FINAL = []
def clear_sim():
    for ob in SIMOBJ:
        me = ob.data
        bpy.data.objects.remove(ob, do_unlink=True)
        if me.users == 0 and me.name.startswith("simp"): bpy.data.meshes.remove(me)
    SIMOBJ.clear()

def passive_object(bay, lumps):
    V, F = [], []
    for L in lumps:
        tp = TPL[L["item"]]; _, W = lump_world(L)
        base = len(V); V += [tuple(w) for w in W]
        for p in tp["F"]: F.append(tuple(base + i for i in p))
    me = bpy.data.meshes.new("simp"); me.from_pydata(V, [], F); me.update()
    ob = bpy.data.objects.new("pass%d" % bay, me); sc.collection.objects.link(ob)
    rb_add(ob, "PASSIVE", "MESH", 0.002)
    SIMOBJ.append(ob); return ob

def simulate(newl, settled):
    """newl: bay -> poses (active, convex hull). settled: bay -> frozen lumps (one passive mesh per bay)."""
    clear_sim()
    for b in range(3):
        if settled[b]: passive_object(b, settled[b])
    act = []
    for b in range(3):
        for L in newl[b]:
            ob = bpy.data.objects.new("act", TPL[L["item"]]["mesh"]); sc.collection.objects.link(ob)
            ob.location = L["loc"]; ob.rotation_euler = L["rot"].to_euler(); ob.scale = (L["s"],) * 3
            rb_add(ob, "ACTIVE", "CONVEX_HULL", 0.003, mass=1.0)
            SIMOBJ.append(ob); act.append((L, ob))
    sc.frame_set(1)
    prev = None; still = 0; used = MAXF; fin = (0, 0)
    for f in range(2, MAXF):
        sc.frame_set(f)
        dg = bpy.context.evaluated_depsgraph_get()
        cur = [ob.evaluated_get(dg).matrix_world.copy() for _, ob in act]
        if prev is not None:
            dpos = max((a.translation - b.translation).length for a, b in zip(cur, prev))
            drot = max((a.to_3x3().normalized() @ b.to_3x3().normalized().inverted()).to_quaternion().angle for a, b in zip(cur, prev))
            fin = (dpos, drot)
            if dpos < 3e-4 and drot < 3e-3: still += 1
            else: still = 0
            if DEBUG and f % 20 == 0: print('  f', f, 'dpos %.5f drot %.4f' % (dpos, drot))
            if still >= 6 and f > 12: used = f; break
        prev = cur
    dg = bpy.context.evaluated_depsgraph_get()
    res = []
    for L, ob in act:
        M = ob.evaluated_get(dg).matrix_world.copy()
        res.append(dict(item=L["item"], loc=M.translation.copy(), rot=M.to_3x3().normalized(), s=L["s"], bay=L["bay"]))
    FINAL.append(fin)
    return res, used

def ok_lump(L):
    _, W = lump_world(L)
    xl, xr = BAYS[L["bay"]]
    return all(xl - 5e-3 <= w.x <= xr + 5e-3 and w.y >= YF_IN - 5e-3 and w.z >= FLOOR_COLL - 5e-3 and nrm(w.y, w.z) <= N_MAX + 5e-3 for w in W)

def run_all():
    settled = {0: [], 1: [], 2: []}
    bvh = {0: None, 1: None, 2: None}
    units = []; frames = []; retries = 0
    for rnd in range(ROUNDS):
        for attempt in range(6):
            newl = {b: plan_drop(b, rnd + attempt * 101, settled[b], bvh[b]) for b in range(3)}
            res, used = simulate(newl, settled)
            if all(ok_lump(L) for L in res): break
            retries += 1; print("RETRY round", rnd, "attempt", attempt, "escaped:", sum(not ok_lump(L) for L in res))
        frames.append(used)
        for b in range(3):
            lb = [L for L in res if L["bay"] == b]
            settled[b] += lb; bvh[b] = mesh_bvh(settled[b])
            units.append(dict(round=rnd, bay=b, item=BAY_ITEM[b], copies=lb))
        if rnd % 5 == 0 or rnd == ROUNDS - 1:
            pk = [round(max(w.z for L in settled[b] for w in lump_world(L)[1]), 2) for b in range(3)]
            print("ROUND", rnd, "frames", used, "peaks", pk, flush=True)
    clear_sim()
    for i, u in enumerate(units): u["index"] = i
    return units, frames, retries

def anchors_json(units):
    out = []
    for u in units:
        allw = [w for L in u["copies"] for w in lump_world(L)[1]]
        lo = Vector((min(w.x for w in allw), min(w.y for w in allw), min(w.z for w in allw)))
        hi = Vector((max(w.x for w in allw), max(w.y for w in allw), max(w.z for w in allw)))
        ctr = (lo + hi) / 2
        cps = []
        for L in u["copies"]:
            eu, q = u_rot(L["rot"])
            cps.append(dict(offset=u_vec(L["loc"] - ctr), rot_euler=eu, rot_quat=q, scale=round(L["s"], 4)))
        out.append(dict(index=u["index"], kind="settled_drop", bay=u["bay"], drop_round=u["round"],
                        position=u_vec(ctr), rotation=[0, 0, 0],
                        box=[round(hi.x - lo.x, 4), round(hi.z - lo.z, 4), round(hi.y - lo.y, 4)],
                        render_item=u["item"], copies=cps))
    return out


# ---------- scene ----------
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.fps = 24
atlas = build_atlas()
MAT = bpy.data.materials.new("bunker"); MAT.use_nodes = True
nt = MAT.node_tree; bsdf = nt.nodes["Principled BSDF"]
ti = nt.nodes.new("ShaderNodeTexImage"); ti.image = atlas; ti.interpolation = "Closest"
nt.links.new(ti.outputs["Color"], bsdf.inputs["Base Color"])
bsdf.inputs["Roughness"].default_value = 0.8
load_templates()
FILLS = (0.1, 0.5, 1.0)
SPACE = 4.9
def tris(obs): return sum(len(p.vertices) - 2 for o in obs for p in o.data.polygons)

def join(obs, name):
    bpy.ops.object.select_all(action="DESELECT")
    for o in obs: o.select_set(True)
    bpy.context.view_layer.objects.active = obs[0]
    bpy.ops.object.join(); ob = bpy.context.active_object; ob.name = name
    return ob

def bvh_of_mesh_list(items):
    V, F = [], []
    for vs, ps in items:
        base = len(V)
        V += vs
        for p in ps: F.append(tuple(base + i for i in p))
    return BVHTree.FromPolygons(V, F)

def inside(bvh, p):
    votes = 0
    for dv in (Vector((0.31, 0.47, 0.83)), Vector((-0.52, 0.21, 0.71)), Vector((0.12, -0.63, 0.55))):
        d = dv.normalized(); n = 0; o = p.copy()
        while True:
            h = bvh.ray_cast(o, d)
            if h[0] is None: break
            n += 1; o = h[0] + d * 1e-4
        votes += n % 2
    return votes >= 2

import time
from collections import Counter
t0 = time.time()

# ---- 1. frame (reference build for the clip check and the OBJ export) ----
rng.seed(7); PARTS.clear()
build_frame()
FRAME = [([v.co.copy() for v in o.data.vertices], [tuple(p.vertices) for p in o.data.polygons]) for o in PARTS]
fb = bvh_of_mesh_list(FRAME)
frame_tris = tris(PARTS)
bpy.ops.object.select_all(action="DESELECT")
for o in PARTS: o.select_set(True)
bpy.ops.wm.obj_export(filepath=os.path.join(OUTA, "Bunker.obj"), export_selected_objects=True, export_materials=False,
                      export_triangulated_mesh=True, forward_axis="NEGATIVE_Z", up_axis="Y")
ct = Counter()
for o in PARTS: ct[o.name.split(".")[0]] += tris([o])
print("TRIS", dict(ct)); print("BUNKER frame_tris", frame_tris)
for o in PARTS: bpy.data.objects.remove(o, do_unlink=True)
PARTS.clear()

# ---- 2. rigid body simulation ----
bpy.ops.rigidbody.world_add()
rbw = sc.rigidbody_world
rbw.substeps_per_frame = SIM_SUBSTEPS; rbw.solver_iterations = SIM_ITERS
rbw.point_cache.frame_start = 1; rbw.point_cache.frame_end = MAXF + 5
sc.frame_start = 1; sc.frame_end = MAXF + 5
build_colliders()
units, frames, retries = run_all()
N = len(units)
ncop = sum(len(u["copies"]) for u in units)
print("SIM rounds", ROUNDS, "units", N, "copies", ncop, "retries", retries, "wall %.0fs" % (time.time() - t0))
print("SETTLE frames per round: min %d mean %.1f max %d  (= %.1f / %.1f / %.1f s at %d fps)" % (
    min(frames), sum(frames) / len(frames), max(frames), min(frames) / 24, sum(frames) / len(frames) / 24, max(frames) / 24, 24))
print("FINAL-FRAME motion per round (last accepted attempt incl. retries): max %.4f mm/frame, max rot %.3f deg/frame" % (
    max(f[0] for f in FINAL) * 1000, math.degrees(max(f[1] for f in FINAL))))
for ob in COLL: bpy.data.objects.remove(ob, do_unlink=True)
bpy.ops.rigidbody.world_remove()
sc.frame_set(1)

# ---- 3. checks ----
bad_items = []
M_IT = 0
for u in units:
    for ci, L in enumerate(u["copies"]):
        M_IT += 1
        tp = TPL[L["item"]]
        M, W = lump_world(L)
        ib = bvh_of_mesh_list([(W, tp["F"])])
        xl, xr = BAYS[L["bay"]]
        ov = len(fb.overlap(ib)) > 0
        oob = any(w.x < xl - 1e-4 or w.x > xr + 1e-4 or w.y < YF_IN - 1e-4 or w.z < Z_FLOOR_FRAME - 1e-4 or nrm(w.y, w.z) > N_MAX + 1e-4 for w in W)
        ins = inside(fb, sum(W, Vector()) / len(W))
        if ov or oob or ins: bad_items.append((u["index"], ci, ov, oob, ins))
print("CLIPPING", len(bad_items), "of", M_IT, bad_items[:8])

# interpenetration between items: deepest vertex of one lump inside another lump's real mesh
allL = [(u["index"], L) for u in units for L in u["copies"]]
Wall = [lump_world(L)[1] for _, L in allL]
bv = [BVHTree.FromPolygons([tuple(w) for w in W], TPL[L["item"]]["F"]) for W, (_, L) in zip(Wall, allL)]
bbmin = [Vector((min(w.x for w in W), min(w.y for w in W), min(w.z for w in W))) for W in Wall]
bbmax = [Vector((max(w.x for w in W), max(w.y for w in W), max(w.z for w in W))) for W in Wall]
depths = []
for i in range(len(allL)):
    for j in range(len(allL)):
        if i == j or allL[i][1]["bay"] != allL[j][1]["bay"]: continue
        if any(bbmax[i][k] < bbmin[j][k] or bbmin[i][k] > bbmax[j][k] for k in range(3)): continue
        for w in Wall[i]:
            if any(w[k] < bbmin[j][k] or w[k] > bbmax[j][k] for k in range(3)): continue
            h = bv[j].find_nearest(w)
            if h[0] is None: continue
            if (w - h[0]).dot(h[1]) < 0: depths.append(((w - h[0]).length, i, j))
tri_pairs = 0; near = 0
for i in range(len(allL)):
    for j in range(i + 1, len(allL)):
        if allL[i][1]["bay"] != allL[j][1]["bay"]: continue
        if any(bbmax[i][k] < bbmin[j][k] - 0.02 or bbmin[i][k] > bbmax[j][k] + 0.02 for k in range(3)): continue
        near += 1
        if len(bv[i].overlap(bv[j])) > 0: tri_pairs += 1
print("MESH-CROSSING item pairs (real meshes, triangle overlap): %d of %d neighbouring pairs" % (tri_pairs, near))
depths.sort(reverse=True)
dd = [d[0] for d in depths]
print("INTERPENETRATION max %.4f m; vertices inside another item: %d; p95 %.4f; >5mm: %d; >1cm: %d" % (
    dd[0] if dd else 0, len(dd), dd[int(len(dd) * 0.05)] if dd else 0, sum(d > 0.005 for d in dd), sum(d > 0.01 for d in dd)))
# unit stats
for b in range(3):
    ws = [w for u in units if u["bay"] == b for L in u["copies"] for w in lump_world(L)[1]]
    print("BAY", b, BAY_ITEM[b], "lumps", sum(len(u["copies"]) for u in units if u["bay"] == b),
          "peak z %.2f" % max(w.z for w in ws), "front-most y %.2f" % min(w.y for w in ws))

# ---- 4. exports ----
meta = dict(round=3, slots_designed_for=N, unit="one unit = one settled drop of %d lumps (one stack)" % UNIT_N,
            convention="Blender z-up/-y front -> Unity y-up/+z front: ux=-bx, uy=bz, uz=-by; rotations R_u=C R_b C^-1",
            frame_obj="Bunker.obj (forward -Z, up Y, triangulated, no materials)",
            fill_order="units[] is in fill order (drop round, then bay). Each unit's copies carry their FINAL settled pose, so a stack is placed "
                       "exactly as listed; earlier units never move when later ones are added (each drop landed on the frozen earlier ones).",
            pivot="copy offset locates the item's bounds centre; scale multiplies the item's natural prefab scale",
            item_hint="one material per bay: bay 0 (Unity +x side) / 1 / 2 hold render_item; the mod places whatever item the stack holds",
            simulation="Blender rigid body: lumps CONVEX_HULL margin 0.003, friction 0.8, restitution 0, damping 0.45/0.85, box colliders for floor/walls/dividers/leaning back wall; "
                       "substeps %d, solver iterations %d, 24 fps; settled when max step < 0.25 mm and < 0.15 deg over 6 frames" % (SIM_SUBSTEPS, SIM_ITERS),
            frame_tris=frame_tris, clipping=len(bad_items),
            max_interpenetration_m=round(dd[0], 4) if dd else 0,
            bay_bounds_x=[list(b) for b in BAYS],
            bay_bounds_unity_x=[[round(-b[1], 4), round(-b[0], 4)] for b in BAYS])
aj = anchors_json(units)
print("ROTCHECK max euler-vs-matrix error %.5f" % ROTERR[0])
json.dump(dict(meta=meta, units=aj), open(os.path.join(OUTA, "bunker_anchors.json"), "w"), indent=1)

# ---- 5. render ----
def spawn(u, dx):
    for L in u["copies"]:
        ob = bpy.data.objects.new(u["item"], TPL[u["item"]]["mesh"])
        ob.location = L["loc"] + Vector((dx, 0, 0)); ob.rotation_mode = "QUATERNION"
        ob.rotation_quaternion = L["rot"].to_quaternion(); ob.scale = (L["s"],) * 3
        sc.collection.objects.link(ob)

for k, fill in enumerate(reversed(FILLS)):
    rng.seed(7); PARTS.clear()
    build_frame()
    dx = (len(FILLS) - 1 - k) * SPACE - SPACE
    ob = join(list(PARTS), "bunker_%d" % int(fill * 100))
    ob.location.x = dx
    shown = units[:round(fill * N)]
    for u in shown: spawn(u, dx)
    print("FILL", fill, "units", len(shown))

# vanilla wood chest + a plain 1.8 m post, for scale (reference only, never exported)
CH_X = -(SPACE + 3.6)
if "--no-ref" not in argv:
    rep = json.load(open("C:/Users/joost/ValheimRip/chests/report.json"))["piece_chest_wood"]["nodes"]
    vimg = bpy.data.images.load(f"{RIP}/woodchest_d.png")
    vm = bpy.data.materials.new("ref"); vm.use_nodes = True
    vt = vm.node_tree.nodes.new("ShaderNodeTexImage"); vt.image = vimg; vt.interpolation = "Closest"
    vm.node_tree.links.new(vt.outputs["Color"], vm.node_tree.nodes["Principled BSDF"].inputs["Base Color"])
    for node in rep:
        if not node["path"].endswith(("/woodchest", "/woodchesttop_closed")): continue
        V, T_, F = [], [], []
        for l in open(node["mesh"]["obj"]):
            p = l.split()
            if not p: continue
            if p[0] == "v": V.append(Vector((-float(p[1]), float(p[2]), float(p[3]))))
            elif p[0] == "vt": T_.append((float(p[1]), float(p[2])))
            elif p[0] == "f": F.append([tuple(int(x) - 1 for x in q.split("/")[:2]) for q in reversed(p[1:])])
        q = node["rot"]
        M = Matrix.Translation(Vector(node["pos"])) @ Quaternion((q[3], q[0], q[1], q[2])).to_matrix().to_4x4() \
            @ Matrix.Diagonal((*node["scale"], 1))
        verts = [M @ v for v in V]
        verts = [Vector((-v.x + CH_X + 5.9 - 5.9, -v.z - 0.3, v.y)) for v in verts]
        F = [list(reversed(f)) for f in F]
        me = bpy.data.meshes.new("ref"); me.from_pydata(verts, [], [[c[0] for c in f] for f in F])
        uvl = me.uv_layers.new(); i = 0
        for f in F:
            for c in f: uvl.data[i].uv = T_[c[1]]; i += 1
        ob = bpy.data.objects.new("ref", me); sc.collection.objects.link(ob); ob.data.materials.append(vm)
    # plain 1.8 m player-height post
    pm = bpy.data.materials.new("post"); pm.use_nodes = True
    pm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.30, 0.30, 0.29, 1)
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(CH_X - 1.3, -0.3, 0.9))
    pst = bpy.context.active_object; pst.scale = (0.14, 0.14, 1.8); pst.data.materials.append(pm); pst.name = "post_1.8m"

world = bpy.data.worlds.new("w"); sc.world = world; world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.42, 0.45, 0.5, 1)
world.node_tree.nodes["Background"].inputs[1].default_value = 0.9
sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN")); sun.data.energy = 3.2
sun.rotation_euler = (math.radians(50), 0, math.radians(35)); sc.collection.objects.link(sun)
bpy.ops.mesh.primitive_plane_add(size=120)
gm = bpy.data.materials.new("ground"); gm.use_nodes = True
gm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.16, 0.14, 0.11, 1)
bpy.context.active_object.data.materials.append(gm)
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam); sc.camera = cam
sc.render.engine = "BLENDER_EEVEE_NEXT"
sc.render.resolution_x, sc.render.resolution_y = 1600, 900
sc.view_settings.view_transform = "Standard"
VIEWS = {"fills": (-8, 27, 24.5, (-1.9, 0, 0.5)), "close": (-28, 30, 8.6, (SPACE, 0, 0.65)),
         "alt": (35, 48, 8.4, (SPACE, 0.1, 0.6))}
for vn, (yaw, pitch, dist, tgt) in VIEWS.items():
    t = Vector(tgt)
    d = Vector((math.cos(math.radians(pitch)) * math.sin(math.radians(yaw)),
                -math.cos(math.radians(pitch)) * math.cos(math.radians(yaw)), math.sin(math.radians(pitch))))
    cam.location = t + d * dist; cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    sc.render.filepath = os.path.join(OUT, f"{TAG}-{vn}.png")
    bpy.ops.render.render(write_still=True)
print("DONE")
