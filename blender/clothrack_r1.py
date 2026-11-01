"""Cloth Rack, round 1: a half-width spinner's cabinet for cloth and thread (concept: scratchpad sketch7/cloth, a 2.4 m rack
of 4 x 2 bays; Joost: "the cloth rack is boring, but cool. Maybe a narrower cabinet version (half the width), because we
don't have that much of it").
Run: "C:/Program Files/Blender Foundation/Blender 4.5/blender.exe" -b -P clothrack_r1.py -- [--out DIR] [--no-render] [--quick] [--views a,b]

Size 1.20 W x 0.60 D x 1.86 H (frame body; the drop spindle's arm reaches 0.10 m past the front). Blender x, y, z: -y = front,
x centred, z = 0 the floor. Placement.Normal: it stands on a floor in a house.
Two columns x two tiers = four bays, one item kind per bay (the mod's ByGroup, group key "bay" 0-3: 0 top left, 1 top
right, 2 bottom left, 3 bottom right, as seen from the front). 32 units (a 4-wide container grid x 8 rows), 8 per bay:
4 layers x 2 rows (front, back), one copy per unit. Units are listed in fill order per bay: layer 0 front, layer 0 back,
layer 1 front, ... so a bay stacks up layer by layer from its plank and nothing ever rests on an empty spot.
Contents: the game's own item models (LinenThread, JuteRed, JuteBlue, NornThread), any kind in any bay. A unit uses the
larder's layout rule (layout {cols 1, rows 1, layers 4, pitch_frac 1.0}): the mod turns each item so its longest bounds
axis runs left-right and its thinnest axis up (align.long_axis_to / thin_axis_to), turns it by a small yaw
(then_rotate_quat_xyzw), fits the turned bounds uniformly into box_x*0.96 x box_y/4 x box_z*0.96, and stands layer k on
k x its own turned height. So every kind lies as bolts or spindles stacked bounds-on-bounds on the plank: no gap, and
no overlap whatever the model (pitch 1.0). Checked here with all four kinds (and a fat worst-case capsule) in every unit.
LinenThread: its prefab is a Unity built-in capsule plus a stick (not in the rip, and no "Item model 'LinenThread'" line
in Player.log yet), so its bay is checked and rendered with a 0.25 m spindle stand-in (a stick through a wound cop).
Character (two touches, no clutter): a carved crown board (stepped, with a spindle-whorl roundel) carrying an arm with
a drop spindle hanging from it on its yarn, and a linen cloth with a woven border draped over the top at the left.
Atlas (128 px, point filtered, 48 px per metre), laid out like coopersrow_r1: rows 0-31 hewn timber, 32-63 x0-63 end grain,
64-79 iron: assets/bunker_r4; 32-63 x64-95 dark oiled timber and x96-127 the wear swatch: assets/metalpallet_r3; new:
80-111 linen (full width, a muted madder border stripe), 112-127 rope (x0-63), wound yarn (x64-95), soapstone (x96-127).
Files: assets/clothrack_r1/{ClothRack.obj, clothrack_atlas.png, clothrack_anchors.json}, the json written last (temp file +
rename). Renders in --out (default: the scratchpad clothrack1 folder), replayed from the exported files the mod's way.
"""
import bpy, bmesh, sys, os, math, json, random, time
import numpy as np
from mathutils import Vector, Matrix, Euler, Quaternion
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, ".."))
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
def arg(k, d=None): return argv[argv.index(k) + 1] if k in argv else d
SCR = "C:/Users/joost/AppData/Local/Temp/claude/C--Users-joost--pai/5e4bc60b-cdfe-4638-8e29-2e507fa13cf9/scratchpad/clothrack1"
OUTA = arg("--assets", os.path.join(REPO, "assets", "clothrack_r1"))
OUT = arg("--out", SCR)
QUICK = "--quick" in argv
NORENDER = "--no-render" in argv
VIEWSEL = arg("--views").split(",") if "--views" in argv else None
ITEMS_DIR = "C:/Users/joost/ValheimRip/items"
sys.path.append(ITEMS_DIR)
from load_item import load_item
os.makedirs(OUTA, exist_ok=True); os.makedirs(OUT, exist_ok=True)
rng = random.Random(23)        # frame
crng = random.Random(31)       # contents jitter

TEX, DENS = 128, 48.0

# ---------- layout (Blender metres, z up, -y = front) ----------
PS = 0.13                       # post section
PXC, PYC = 0.535, 0.235         # post centres
XIN = PXC - PS / 2              # 0.47: inner face of the posts and side boards
DT = 0.05                       # centre divider
CW = XIN - DT / 2               # clear bay width 0.445
BAYX = (-(DT / 2 + CW / 2), DT / 2 + CW / 2)        # bay centres x: left (-x, seen from the front), right
BT = 0.05                       # shelf planks
PT = (0.17, 0.83)               # plank tops: bottom tier, top tier
CLEAR = 0.61                    # clear bay height
BEAM_Z = PT[1] + CLEAR          # 1.44: underside of the top beams
TOPB = BEAM_Z + 0.12            # 1.56: top board underside
TOPZ = TOPB + 0.05              # 1.61: top board top
BACK_IN = 0.215                 # inner face of the back boards
FRONT_EDGE = -0.29              # shelf front edge
# units: 4 layers x 2 rows, one copy each, fit box per copy = box*0.96 / box_y/4
LAYERS, LP = 4, 0.14            # layer height of the fit box
BOXX, BOXZ = 0.4167, 0.235      # unit box: x (fit 0.40), depth (fit 0.2256)
ROWY = (BACK_IN - 0.004 - BOXZ / 2 - BOXZ, BACK_IN - 0.004 - BOXZ / 2)   # front, back row centres (Blender y)
BAYS = [(0, 1), (1, 1), (0, 0), (1, 0)]            # (column, tier): 0 top left, 1 top right, 2 bottom left, 3 bottom right
DEFAULT_KIND = ["LinenThread", "NornThread", "JuteRed", "JuteBlue"]
KINDS = ["LinenThread", "JuteRed", "JuteBlue", "NornThread"]

# ---------- atlas ----------
TILES = {"hewn": (0, 0, 128, 32), "end0": (0, 32, 32, 32), "end1": (32, 32, 32, 32), "dark": (64, 32, 32, 32),
         "wearw": (96, 32, 32, 16), "weari": (96, 48, 32, 16), "iron": (0, 64, 128, 16),
         "linen": (0, 80, 128, 32), "rope": (0, 112, 64, 16), "yarn": (64, 112, 32, 16), "stone": (96, 112, 32, 16)}

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
    A = np.zeros((TEX, TEX, 3), np.float32)
    A[0:32] = B[0:32]                       # bunker hewn timber
    A[32:64, 0:64] = B[32:64, 0:64]         # bunker end grain, rings 0 and 1
    A[32:64, 64:96] = P[0:32, 0:32]         # pallet dark oiled hewn timber
    A[32:64, 96:128] = P[32:64, 96:128]     # pallet wear swatch: worn timber (top), worn iron (bottom)
    A[64:80] = B[64:80]                     # bunker iron
    nr = np.random.default_rng(43)
    blocky = lambda h, w, s: np.kron(nr.random((h // s, w // s)), np.ones((s, s), np.float32))
    # linen: muted flax off-white, plain weave (1 px over-under), slubs, darker creases, a madder border band
    yy, xx = np.meshgrid(np.arange(32), np.arange(128), indexing="ij")
    base, dark, light = srgb((0.60, 0.56, 0.47)), srgb((0.33, 0.29, 0.23)), srgb((0.70, 0.67, 0.58))
    weave = ((xx + yy) % 2) * 0.10 + ((yy % 4) == 0) * 0.06
    slub = (nr.random((32, 128)) < 0.03) * 0.25
    crease = np.clip(np.sin(xx * 0.21 + 0.8 * np.sin(yy * 0.3)) - 0.82, 0, 1) * 2.2
    t = weave + blocky(32, 128, 4) * 0.16 + nr.random((32, 128)) * 0.08 + crease + slub
    img = mix(base, dark, t)
    hl = (nr.random((32, 128)) < 0.04) & (t < 0.25)
    img[hl] = mix(img[hl], np.broadcast_to(light, img[hl].shape), np.full(hl.sum(), 0.6))
    mad, madd = srgb((0.43, 0.24, 0.17)), srgb((0.25, 0.13, 0.09))
    band = (yy >= 25) & (yy <= 26)
    bimg = mix(np.broadcast_to(mad, img.shape), np.broadcast_to(madd, img.shape), weave * 2 + nr.random((32, 128)) * 0.25)
    img[band] = bimg[band]
    thin = (yy == 23)
    img[thin] = mix(img[thin], np.broadcast_to(mad, img[thin].shape), np.full(thin.sum(), 0.7))
    A[80:112] = img
    # rope: twisted hemp, diagonal strands with dark gaps and light crowns
    yy, xx = np.meshgrid(np.arange(16), np.arange(64), indexing="ij")
    base, dark, light = srgb((0.47, 0.39, 0.26)), srgb((0.20, 0.15, 0.09)), srgb((0.60, 0.51, 0.36))
    s = (xx + yy * 1.1) % 6
    t = (s < 1.1) * 0.9 + nr.random((16, 64)) * 0.18
    img = mix(base, dark, t)
    h = (s > 2.6) & (s < 3.6)
    img[h] = mix(img[h], np.broadcast_to(light, img[h].shape), np.full(h.sum(), 0.4))
    A[112:128, 0:64] = img
    # wound yarn: fine horizontal turns, muted linen, darker between the turns
    yy, xx = np.meshgrid(np.arange(16), np.arange(32), indexing="ij")
    base, dark = srgb((0.64, 0.60, 0.51)), srgb((0.38, 0.34, 0.27))
    t = ((yy % 2) == 1) * 0.35 + nr.random((16, 32)) * 0.15 + np.clip(np.sin(xx * 0.4 + yy) - 0.9, 0, 1) * 2
    A[112:128, 64:96] = mix(base, dark, t)
    # soapstone: grey-green, blotchy, light worn specks
    base, dark, light = srgb((0.37, 0.38, 0.33)), srgb((0.19, 0.20, 0.18)), srgb((0.52, 0.53, 0.47))
    t = blocky(16, 32, 4) * 0.35 + blocky(16, 32, 2) * 0.2 + nr.random((16, 32)) * 0.12
    img = mix(base, dark, t)
    sp = nr.random((16, 32)) < 0.05
    img[sp] = mix(img[sp], np.broadcast_to(light, img[sp].shape), np.full(sp.sum(), 0.7))
    A[112:128, 96:128] = img
    im = bpy.data.images.new("clothrack_atlas", TEX, TEX, alpha=False)
    px = np.concatenate([np.clip(A[::-1], 0, 1), np.ones((TEX, TEX, 1), np.float32)], 2)
    im.pixels.foreach_set(px.ravel())
    im.filepath_raw = os.path.join(OUTA, "clothrack_atlas.png"); im.file_format = "PNG"; im.save()
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

# box timbers: bunker_r4's mapping (hewn strip v 0.75, end grain v 0.5 two rings, iron v 0.375), chamfers -> wear swatch
STRIP = {"hewn": 0.75, "end": 0.50, "iron": 0.375}
STRIPH = {"hewn": 32, "iron": 16}
def uv_tile_face(f, uvl, tile, long_axis, seed):
    """planar map onto a small tile at 48 px/m (scaled down to fit), a random spot inside it"""
    n = f.normal
    ax = max(range(3), key=lambda i: abs(n[i]))
    tang = [i for i in range(3) if i != ax]
    ua = long_axis if long_axis in tang else tang[0]
    va = tang[1] if ua == tang[0] else tang[0]
    x0, y0, w, h = TILES[tile]
    cs = [l.vert.co for l in f.loops]
    umin, vmin = min(c[ua] for c in cs), min(c[va] for c in cs)
    uspan, vspan = max(max(c[ua] for c in cs) - umin, 1e-4), max(max(c[va] for c in cs) - vmin, 1e-4)
    k = min(1.0, (w - 2) / (uspan * DENS), (h - 2) / (vspan * DENS))
    r = random.Random(seed * 31 + f.index)
    ou = 1 + r.uniform(0, max(0, w - 2 - uspan * DENS * k)); ov = 1 + r.uniform(0, max(0, h - 2 - vspan * DENS * k))
    for l in f.loops:
        l[uvl].uv = tuv(tile, ou + (l.vert.co[ua] - umin) * DENS * k, ov + (l.vert.co[va] - vmin) * DENS * k)

def uv_box_face(f, uvl, kind, long_axis, seed):
    if kind in ("rope", "yarn", "stone", "linen"):
        return uv_tile_face(f, uvl, kind, long_axis, seed)
    n = f.normal
    r = random.Random(seed * 7919 + f.index)
    if kind == "rivet" or max(abs(n[0]), abs(n[1]), abs(n[2])) < 0.98:
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
        l[uvl].uv = (u, v)

def timber(name, size, pos, kind="hewn", rot=(0, 0, 0), jitter=0.010, bevel=0.014):
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

def boxat(name, x0, x1, y0, y1, z0, z1, **kw):
    return timber(name, (x1 - x0, y1 - y0, z1 - z0), ((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2), **kw)

def iron(name, size, pos, rot=(0, 0, 0)):
    return timber(name, size, pos, kind="iron", rot=rot, jitter=0.0015, bevel=0)

def rivet(pos, normal, s=0.022, h=0.007):
    n = Vector(normal).normalized()
    yaw = math.degrees(math.atan2(n.y, n.x)) if abs(n.z) < 0.5 else 0
    size = (h, s, s) if abs(n.z) < 0.5 else (s, s, h)
    p = Vector(pos) + n * (h / 2)
    timber("rivet", size, tuple(p), kind="rivet", rot=(0, 0, yaw), jitter=0, bevel=0)

def lathe(name, prof, at, tile, cap=None, segs=12, phase=0.0, axis="z"):
    """a turned part: profile [(r, h)] revolved about a vertical axis through `at` (or along -y for axis='y': h runs to -y).
    Sides on `tile` (around = u, along = v, 48 px/m, scaled to fit the tile), caps (r > 0 at the ends) on `cap`."""
    bm = bmesh.new(); uvl = bm.loops.layers.uv.verify()
    x0, y0, w, h = TILES[tile]
    def P(r, a, z):
        c, s = r * math.cos(a), r * math.sin(a)
        if axis == "z": return Vector((at[0] + c, at[1] + s, at[2] + z))
        return Vector((at[0] + c, at[1] - z, at[2] + s))
    ang = [phase + 2 * math.pi * i / segs for i in range(segs + 1)]
    L = sum(math.hypot(r1 - r0, z1 - z0) for (r0, z0), (r1, z1) in zip(prof, prof[1:]))
    rmax = max(r for r, _ in prof)
    ku = min(1.0, (w - 2) / max(2 * math.pi * rmax * DENS, 1e-4)) if w < 128 else 1.0
    kv = min(1.0, (h - 2) / max(L * DENS, 1e-4))
    rr = random.Random(hash(name) % 1000 + len(PARTS))
    ou, ov = rr.uniform(0, 128) if w == 128 else 1.0, 1.0
    s_acc = 0.0
    for (r0, z0), (r1, z1) in zip(prof, prof[1:]):
        seg = math.hypot(r1 - r0, z1 - z0)
        for i in range(segs):
            a0, a1 = ang[i], ang[i + 1]
            pts = [P(r0, a0, z0), P(r0, a1, z0), P(r1, a1, z1), P(r1, a0, z1)]
            if r0 < 1e-6: pts = [pts[0], pts[2], pts[3]]
            elif r1 < 1e-6: pts = pts[:3]
            try: f = bm.faces.new([bm.verts.new(p) for p in pts])
            except ValueError: continue
            uvs = [(a0, r0, s_acc), (a1, r0, s_acc), (a1, r1, s_acc + seg), (a0, r1, s_acc + seg)]
            if r0 < 1e-6: uvs = [uvs[0], uvs[2], uvs[3]]
            elif r1 < 1e-6: uvs = uvs[:3]
            for l, (a, r, sv) in zip(f.loops, uvs):
                l[uvl].uv = tuv(tile, ou + (a - phase) * rmax * DENS * ku, ov + sv * DENS * kv)
        s_acc += seg
    for (r, z), top in ((prof[0], False), (prof[-1], True)):
        if r < 1e-6 or cap is None: continue
        pts = [P(r, ang[i], z) for i in range(segs)]
        if not top: pts = pts[::-1]
        f = bm.faces.new([bm.verts.new(p) for p in pts])
        cx, cy, cw, chh = TILES[cap]
        for l, i in zip(f.loops, range(segs)):
            a = ang[i] if top else ang[segs - 1 - i]
            l[uvl].uv = tuv(cap, cw / 2 + math.cos(a) * min(r * DENS, cw / 2 - 1.5), chh / 2 + math.sin(a) * min(r * DENS, chh / 2 - 1.5))
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return new_obj(name, bm)

def drape():
    """a linen cloth lying on the top board at the left, folded over its front edge, hanging over the front beam"""
    x0, x1 = -0.455, -0.150
    T = 0.007
    yb, yf, ze = -0.05, -0.322, TOPZ          # back end on the board, the board's front edge, its top
    rad = 0.022
    # path (y, z) along the cloth's middle sheet: on the board, round the edge, down the front
    path = []
    for i in range(7): path.append((yb + (yf + rad - yb) * i / 6, ze + T / 2))
    for i in range(1, 6):
        a = math.pi / 2 * i / 5
        path.append((yf + rad - (rad + T / 2) * math.sin(a), ze - rad + (rad + T / 2) * math.cos(a)))
    hang = 0.155
    for i in range(1, 9): path.append((yf - T / 2 - 0.004 * i / 8, ze - rad - hang * i / 8))
    S = [0.0]
    for (ya, za), (yb_, zb) in zip(path, path[1:]): S.append(S[-1] + math.hypot(yb_ - ya, zb - za))
    s_edge = S[6]
    NX = 18
    xs = [x0 + (x1 - x0) * j / NX for j in range(NX + 1)]
    def disp(j, i):
        x = xs[j]; s = S[i]
        down = max(0.0, s - S[11]) / (S[-1] - S[11])           # 0 at the edge, 1 at the hem
        fold = (0.5 + 0.5 * math.sin(2 * math.pi * (x - x0) / 0.095 + 0.7)) * (0.004 + 0.030 * down ** 1.2)             + (0.5 + 0.5 * math.sin(2 * math.pi * (x - x0) / 0.041 + 2.1)) * 0.006 * down
        wr = 0.0025 * math.sin(2 * math.pi * (x - x0) / 0.07 + s * 9) if s < s_edge else 0.0
        hem = 0.0
        if i == len(path) - 1: hem = 0.009 * math.sin(2 * math.pi * (x - x0) / 0.16 + 1.9) + 0.003 * math.sin(x * 61)
        back = 0.012 * math.sin(x * 37 + 0.4) if i == 0 else 0.0
        return fold, wr, hem, back
    bm = bmesh.new(); uvl = bm.loops.layers.uv.verify()
    rows_o, rows_i = [], []
    for i, (y, z) in enumerate(path):
        # outward normal of the sheet at this path point (up on the board, -y down the front)
        ya, za = path[max(i - 1, 0)]; yb_, zb = path[min(i + 1, len(path) - 1)]
        ty, tz = yb_ - ya, zb - za; ln = math.hypot(ty, tz) or 1
        ny, nz = tz / ln, -ty / ln                           # rotate the tangent: on the board (-y going) -> up
        if nz < 0 and i < 6: ny, nz = -ny, -nz
        ro, ri = [], []
        for j in range(len(xs)):
            fold, wr, hem, back = disp(j, i)
            yy = y + ny * (fold + wr) + (0 if i < len(path) - 1 else 0)
            zz = z + nz * (fold + wr) + hem
            yy += back
            ro.append(bm.verts.new((xs[j], yy + ny * T / 2, zz + nz * T / 2)))
            ri.append(bm.verts.new((xs[j], yy - ny * T / 2, zz - nz * T / 2)))
        rows_o.append(ro); rows_i.append(ri)
    def uv_at(j, i, inner=False):
        return tuv("linen", 3 + (xs[j] - x0) * DENS + (40 if inner else 0), 29.0 - (S[-1] - S[i]) * DENS * min(1.0, 27.0 / (S[-1] * DENS)))
    for i in range(len(path) - 1):
        for j in range(NX):
            f = bm.faces.new((rows_o[i][j], rows_o[i][j + 1], rows_o[i + 1][j + 1], rows_o[i + 1][j]))
            for l, (jj, ii) in zip(f.loops, ((j, i), (j + 1, i), (j + 1, i + 1), (j, i + 1))): l[uvl].uv = uv_at(jj, ii)
            f = bm.faces.new((rows_i[i][j], rows_i[i + 1][j], rows_i[i + 1][j + 1], rows_i[i][j + 1]))
            for l, (jj, ii) in zip(f.loops, ((j, i), (j, i + 1), (j + 1, i + 1), (j + 1, i))): l[uvl].uv = uv_at(jj, ii, True)
    for i in range(len(path) - 1):                      # side edges
        for j, flip in ((0, True), (NX, False)):
            q = (rows_o[i][j], rows_o[i + 1][j], rows_i[i + 1][j], rows_i[i][j])
            f = bm.faces.new(q if flip else q[::-1])
            for l in f.loops: l[uvl].uv = uv_at(j, i)
    for i, flip in ((0, False), (len(path) - 1, True)):  # back end and hem
        for j in range(NX):
            q = (rows_o[i][j], rows_o[i][j + 1], rows_i[i][j + 1], rows_i[i][j])
            f = bm.faces.new(q if flip else q[::-1])
            for l in f.loops: l[uvl].uv = uv_at(j, i)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return new_obj("drape", bm)

def build_frame():
    # posts, floor to the top board
    for sx in (-1, 1):
        for sy in (-1, 1):
            timber("post", (PS, PS, TOPB), (sx * PXC, sy * PYC, TOPB / 2), jitter=0.004, bevel=0.016)
    # bottom frame: front kick, back rail, side rails (0.10 x 0.10)
    boxat("kick", -PXC + PS / 2, PXC - PS / 2, -0.29, -0.20, 0.02, 0.12, jitter=0.004)
    boxat("rail", -PXC + PS / 2, PXC - PS / 2, 0.19, 0.28, 0.02, 0.12, jitter=0.004)
    for sx in (-1, 1): boxat("rail", sx * PXC - 0.045, sx * PXC + 0.045, -PYC + PS / 2, PYC - PS / 2, 0.02, 0.12, jitter=0.004)
    # side boards (3 planks, 0.045) and back boards (6 planks, 0.04), floor frame to the top beams
    for sx in (-1, 1):
        y0 = -PYC + PS / 2; w = (2 * (PYC - PS / 2)) / 3
        for k in range(3):
            xa, xb = (XIN, XIN + 0.045) if sx > 0 else (-XIN - 0.045, -XIN)
            boxat("side", xa, xb, y0 + k * w + 0.002, y0 + (k + 1) * w - 0.002, 0.12, BEAM_Z, jitter=0.002, bevel=0.008)
    xb0 = -PXC + PS / 2; wb = 2 * (PXC - PS / 2) / 6
    for k in range(6):
        boxat("back", xb0 + k * wb + 0.002, xb0 + (k + 1) * wb - 0.002, BACK_IN, BACK_IN + 0.04, 0.12, BEAM_Z, jitter=0.002, bevel=0.008)
    # shelves: 3 planks along x each, 0.05 thick, front edge to the back boards
    for zt in PT:
        d = (BACK_IN - FRONT_EDGE) / 3
        for k in range(3):
            boxat("shelf", -XIN, XIN, FRONT_EDGE + k * d + 0.002, FRONT_EDGE + (k + 1) * d - 0.002, zt - BT, zt, jitter=0.0, bevel=0.010)
    # centre divider in each bay (0.05), iron strap down its front edge with rivets
    for zt in PT:
        top = zt + CLEAR
        boxat("divider", -DT / 2, DT / 2, FRONT_EDGE + 0.02, BACK_IN, zt, top, jitter=0.002, bevel=0.008)
        iron("strap", (0.06, 0.006, CLEAR - 0.02), (0, FRONT_EDGE + 0.02 - 0.004, zt + CLEAR / 2))
        for zz in (zt + 0.06, zt + CLEAR / 2, zt + CLEAR - 0.06): rivet((0, FRONT_EDGE + 0.02 - 0.007, zz), (0, -1, 0))
    # top beams 0.12 x 0.12 (front, back), side beams; top board (3 planks, overhanging)
    boxat("beam", -PXC + PS / 2, PXC - PS / 2, -PYC - 0.06, -PYC + 0.06, BEAM_Z, TOPB, jitter=0.004)
    boxat("beam", -PXC + PS / 2, PXC - PS / 2, PYC - 0.06, PYC + 0.06, BEAM_Z, TOPB, jitter=0.004)
    for sx in (-1, 1): boxat("beam", sx * PXC - 0.05, sx * PXC + 0.05, -PYC + PS / 2, PYC - PS / 2, BEAM_Z, TOPB, jitter=0.004)
    d = 0.644 / 3
    for k in range(3):
        boxat("top", -0.625, 0.625, -0.322 + k * d + 0.002, -0.322 + (k + 1) * d - 0.002, TOPB, TOPZ, jitter=0.002, bevel=0.012)
    # iron: bands on the front posts over each shelf, L brackets where the front beam meets the posts
    for sx in (-1, 1):
        for zt in PT:
            iron("band", (PS + 0.016, PS + 0.016, 0.045), (sx * PXC, -PYC, zt + 0.07))
            rivet((sx * PXC, -PYC - PS / 2 - 0.008, zt + 0.07), (0, -1, 0))
        xp = sx * (PXC - PS / 2)
        yf = -PYC - 0.06
        iron("bracket", (0.17, 0.006, 0.05), (xp - sx * 0.085, yf - 0.003, BEAM_Z + 0.05))
        iron("bracket", (0.05, 0.006, 0.17), (sx * PXC - sx * 0.02, -PYC - PS / 2 - 0.003, BEAM_Z + 0.03))
        rivet((xp - sx * 0.13, yf - 0.006, BEAM_Z + 0.05), (0, -1, 0))
        rivet((sx * PXC - sx * 0.02, -PYC - PS / 2 - 0.006, BEAM_Z - 0.03), (0, -1, 0))
    # crown: a stepped carved board standing on the middle of the top, a spindle-whorl roundel on its face, braces behind
    boxat("crown", -0.57, 0.57, -0.025, 0.025, TOPZ, TOPZ + 0.12, jitter=0.002, bevel=0.012)
    boxat("crown", -0.35, 0.35, -0.025, 0.025, TOPZ + 0.12, TOPZ + 0.19, jitter=0.002, bevel=0.012)
    boxat("crown", -0.15, 0.15, -0.025, 0.025, TOPZ + 0.19, TOPZ + 0.25, jitter=0.002, bevel=0.012)
    lathe("roundel", [(0.080, 0.0), (0.080, 0.012), (0.066, 0.026)],
          (0.0, -0.025, TOPZ + 0.135), "hewn", cap="end0", segs=16, axis="y")
    lathe("boss", [(0.0, 0.026), (0.024, 0.026), (0.020, 0.040), (0.0, 0.044)], (0.0, -0.025, TOPZ + 0.135), "hewn", segs=10, axis="y")
    for sx in (-1, 1): boxat("brace", sx * 0.42 - 0.03, sx * 0.42 + 0.03, 0.025, 0.115, TOPZ, TOPZ + 0.08, jitter=0.002, bevel=0.01)
    # front finials: turned spindles on the front posts (the right one carries the arm)
    for sx in (-1, 1):
        prof = [(0.058, 0.0), (0.058, 0.018), (0.034, 0.030), (0.030, 0.045), (0.060, 0.070), (0.050, 0.090), (0.030, 0.100), (0.030, 0.120)]
        if sx < 0: prof += [(0.040, 0.128), (0.034, 0.150), (0.0, 0.158)]
        lathe("finial", prof, (sx * PXC, -PYC, TOPZ), "hewn", cap="end1", segs=12)
    # the arm: on the crown and the right finial, lashed at both, a drop spindle hanging from its tip on its yarn
    AX, AZ = PXC, TOPZ + 0.12           # arm bottom at the crown base's top and the finial's top
    boxat("arm", AX - 0.0225, AX + 0.0225, -0.405, 0.07, AZ, AZ + 0.045, jitter=0.002, bevel=0.010)
    lathe("armtip", [(0.0, 0.0), (0.026, 0.0), (0.030, 0.012), (0.024, 0.026), (0.0, 0.030)], (AX, -0.405, AZ + 0.0225), "hewn",
          segs=10, axis="y")
    for yc, dys, zlo in ((0.0, (-0.046, -0.032, 0.032, 0.046), AZ - 0.006), (-PYC, (-0.018, 0.0, 0.018), AZ - 0.014)):
        for dy in dys:
            boxat("lash", AX - 0.031, AX + 0.031, yc + dy - 0.0075, yc + dy + 0.0075, zlo, AZ + 0.052, kind="rope", jitter=0.001, bevel=0.004)
    SY = -0.385
    boxat("hitch", AX - 0.028, AX + 0.028, SY - 0.008, SY + 0.008, AZ - 0.004, AZ + 0.049, kind="yarn", jitter=0, bevel=0.003)
    top_s = 1.31
    boxat("yarn", AX - 0.0025, AX + 0.0025, SY - 0.0025, SY + 0.0025, top_s - 0.01, AZ - 0.003, kind="yarn", jitter=0, bevel=0)
    lathe("shaft", [(0.0, 0.0), (0.004, 0.006), (0.008, 0.03), (0.0095, 0.22), (0.007, 0.27), (0.003, 0.285), (0.0, 0.29)],
          (AX, SY, top_s - 0.29), "hewn", segs=8)
    lathe("cop", [(0.009, 0.0), (0.024, 0.03), (0.033, 0.075), (0.030, 0.105), (0.018, 0.135), (0.009, 0.15)],
          (AX, SY, top_s - 0.215), "yarn", cap=None, segs=12)
    lathe("whorl", [(0.009, 0.0), (0.040, 0.004), (0.044, 0.014), (0.036, 0.026), (0.009, 0.028)],
          (AX, SY, top_s - 0.265), "stone", cap=None, segs=14)
    drape()

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

# ---------- items (Unity item space: ux=-bx, uy=bz, uz=-by) ----------
B2U = np.array([[-1, 0, 0], [0, 0, 1], [0, -1, 0]], float)     # u = B2U @ b ; b = B2U.T @ u
TPL = {}

def standin_mesh(name, stick_len, stick_r, cop_len, cop_r):
    """LinenThread stand-in: a stick along the item's up axis through a wound cop (Blender item space, z = Unity y)"""
    bm = bmesh.new()
    def rev(prof, segs=12):
        rings = []
        for r, z in prof:
            rings.append([bm.verts.new((r * math.cos(2 * math.pi * i / segs), r * math.sin(2 * math.pi * i / segs), z)) for i in range(segs)])
        for a, b in zip(rings, rings[1:]):
            for i in range(segs): bm.faces.new((a[i], a[(i + 1) % segs], b[(i + 1) % segs], b[i]))
        bm.faces.new(rings[0][::-1]); bm.faces.new(rings[-1])
    h = stick_len / 2
    rev([(stick_r * 0.5, -h), (stick_r, -h + 0.02 * stick_len / 0.25), (stick_r, h - 0.02 * stick_len / 0.25), (stick_r * 0.5, h)], 8)
    c = cop_len / 2
    rev([(stick_r * 1.05, -c), (cop_r * 0.75, -c * 0.6), (cop_r, -c * 0.1), (cop_r * 0.9, c * 0.4), (cop_r * 0.55, c * 0.85), (stick_r * 1.05, c)], 12)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    return me

def load_templates():
    for k in ["JuteRed", "JuteBlue", "NornThread"]:
        ob = load_item(k, anchor="origin")[0]
        me = ob.data; me.name = "tpl_" + k
        bpy.data.objects.remove(ob, do_unlink=True)
        TPL[k] = {"mesh": me}
    me = standin_mesh("tpl_LinenThread", 0.25, 0.0055, 0.16, 0.036)
    m_wood = bpy.data.materials.new("linen_stick"); m_wood.use_nodes = True
    m_wood.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.30, 0.20, 0.11, 1)
    m_th = bpy.data.materials.new("linen_thread"); m_th.use_nodes = True
    m_th.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.42, 0.36, 0.25, 1)
    m_th.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.9
    me.materials.append(m_wood); me.materials.append(m_th)
    for p in me.polygons: p.material_index = 1 if max(abs(me.vertices[v].co.x) for v in p.vertices) > 0.0065 else 0
    TPL["LinenThread"] = {"mesh": me, "standin": True}
    TPL["LinenThread_fat"] = {"mesh": standin_mesh("tpl_LinenThread_fat", 2.6, 0.08, 2.0, 0.5), "check_only": True}   # Unity capsule 1 x 2 x 1 + stick
    for k, t in TPL.items():
        me = t["mesh"]
        Vb = np.array([tuple(v.co) for v in me.vertices], float)
        Vu = Vb @ B2U.T
        lo, hi = Vu.min(0), Vu.max(0)
        t["Vu"] = Vu; t["size"] = hi - lo; t["center"] = (hi + lo) / 2
        t["T"] = [(p.vertices[0], p.vertices[i], p.vertices[i + 1]) for p in me.polygons for i in range(1, len(p.vertices) - 1)]

# ---------- the mod's placement, replicated (StoreModel.Place, layout rule, unit rotation identity) ----------
E3 = np.eye(3)
def look_rotation(f, up):
    f = np.array(f, float); f /= np.linalg.norm(f)
    r = np.cross(up, f); r /= np.linalg.norm(r)
    return np.column_stack([r, np.cross(f, r), f])

def q2m(q):
    x, y, z, w = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])

def euler_unity(e):
    x, y, z = [math.radians(a) for a in e]
    Rx = np.array([[1, 0, 0], [0, math.cos(x), -math.sin(x)], [0, math.sin(x), math.cos(x)]])
    Ry = np.array([[math.cos(y), 0, math.sin(y)], [0, 1, 0], [-math.sin(y), 0, math.cos(y)]])
    Rz = np.array([[math.cos(z), -math.sin(z), 0], [math.sin(z), math.cos(z), 0], [0, 0, 1]])
    return Ry @ Rx @ Rz

def place(u, c, size, center):
    """Unity 4x4 of one copy in store space, as StoreModel.Place does it (Fit.Box / Fit.Longest, align, layout, bottom)"""
    size = np.array(size, float); center = np.array(center, float)
    if "align" in c:
        il, it = int(np.argmax(size)), int(np.argmin(size))
        if it == il: it = (il + 1) % 3
        L = np.array(c["align"]["long_axis_to"], float); L /= np.linalg.norm(L)
        T = np.array(c["align"]["thin_axis_to"], float); T = T - L * T.dot(L); T /= np.linalg.norm(T)
        align = look_rotation(T, L) @ look_rotation(E3[it], E3[il]).T
        rot = q2m(c["align"].get("then_rotate_quat_xyzw", [0, 0, 0, 1]))
    else:
        align = np.eye(3)
        rot = euler_unity(c["rotation"]) if "rotation" in c else np.eye(3)
    r = rot @ align
    off = np.array(c.get("offset", c.get("local_position", [0, 0, 0])), float)
    lay = u.get("layout"); bottom = False; pitch = 0.0; fit_after = False
    if "fit_longest_m" in c:
        d = np.abs(align) @ size; s = c["fit_longest_m"] / size.max()
    elif "fit_box" in c:
        d = np.abs(align) @ size; fb = np.array(c["fit_box"], float); s = (fb / d).min(); bottom = True
    else:
        cols, rows, layers, pitch = lay["cols"], lay["rows"], lay["layers"], lay.get("pitch_frac", 1.0)
        bx = np.array(u["box"], float)
        fb = np.array([bx[0] / cols * 0.96, bx[1] / (1 + (layers - 1) * pitch), bx[2] / rows * 0.96])
        d = np.abs(r) @ size; s = (fb / d).min(); bottom = True; fit_after = True
    if "anchor" in c: bottom = c["anchor"].startswith("bottom")
    centre = off.copy()
    if pitch > 0: centre[1] = 0.0
    if bottom: centre[1] += s * d[1] * 0.5
    if pitch > 0: centre[1] += c.get("layer", 0) * pitch * s * d[1]
    pos = centre - r @ (s * center)
    M = np.eye(4); M[:3, :3] = r * s; M[:3, 3] = np.array(u["position"], float) + pos
    return M, s

def world_b(Vu, M):
    """item verts (Unity item space) -> Blender world"""
    W = Vu @ M[:3, :3].T + M[:3, 3]
    return W @ B2U        # b = B2U.T u  (row form: W @ B2U)

# ---------- units ----------
def b2u(v): return [round(-v[0], 5), round(v[2], 5), round(-v[1], 5)]

def build_units():
    units = []
    for bay, (col, tier) in enumerate(BAYS):
        x = BAYX[col]; floor = PT[tier] + 0.0015
        for layer in range(LAYERS):
            for row in (0, 1):                               # front, then back
                # one yaw magnitude for every copy: the mod fits each copy's turned bounds on its own, so equal |sin| gives
                # every copy of a kind the same scale and height, and layer k lands exactly on layer k-1
                yaw = crng.choice((0.0, 180.0)) + crng.choice((-2.0, 2.0))
                q = [0.0, round(math.sin(math.radians(yaw) / 2), 6), 0.0, round(math.cos(math.radians(yaw) / 2), 6)]
                off = [round(crng.uniform(-0.008, 0.008), 4), 0.0, round(crng.uniform(-0.004, 0.004), 4)]
                units.append({"index": len(units), "bay": bay, "layer": layer, "row": ("front", "back")[row], "column": col, "tier": tier,
                              "kind": "bolt", "example_item": DEFAULT_KIND[bay],
                              "position": b2u((x, ROWY[row], floor)), "rotation": [0, 0, 0],
                              "box": [BOXX, round(LAYERS * LP, 4), BOXZ],
                              "layout": {"cols": 1, "rows": 1, "layers": LAYERS, "pitch_frac": 1.0},
                              "copies": [{"layer": layer, "offset": off,
                                          "align": {"long_axis_to": [1, 0, 0], "thin_axis_to": [0, 1, 0], "then_rotate_quat_xyzw": q}}]})
    return units

# ---------- scene + frame ----------
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
atlas = build_atlas()
MAT = bpy.data.materials.new("clothrack"); MAT.use_nodes = True
_b = MAT.node_tree.nodes["Principled BSDF"]
_t = MAT.node_tree.nodes.new("ShaderNodeTexImage"); _t.image = atlas; _t.interpolation = "Closest"
MAT.node_tree.links.new(_t.outputs["Color"], _b.inputs["Base Color"])
_b.inputs["Roughness"].default_value = 1.0; _b.inputs["Specular IOR Level"].default_value = 0.0

build_frame()
frame = join(list(PARTS), "ClothRack")
FV_, FT_ = tri_list(frame.data)
frame_tris = len(FT_)
fbvh = BVHTree.FromPolygons(FV_, FT_, all_triangles=True)
FVn = np.array([tuple(v) for v in FV_])
frame_size = (float(FVn[:, 0].max() - FVn[:, 0].min()), float(FVn[:, 2].max()), float(FVn[:, 1].max() - FVn[:, 1].min()))
body = FVn[(FVn[:, 1] > -0.33)]
print("FRAME tris", frame_tris, "size W H D", [round(a, 3) for a in frame_size], "x", round(FVn[:, 0].min(), 3), round(FVn[:, 0].max(), 3),
      "y", round(FVn[:, 1].min(), 3), round(FVn[:, 1].max(), 3), flush=True)

load_templates()
units = build_units()

# ---------- checks: every kind in every unit ----------
t0 = time.time()
clip_frame = {}; clip_pair = {}; lifts = 0; scales = {}; heights = {}
CK = list(TPL.keys())
WB = {}
for u in units:
    for k in CK:
        t = TPL[k]
        M, s = place(u, u["copies"][0], t["size"], t["center"])
        W = world_b(t["Vu"], M)
        floor = u["position"][1] - u["box"][1] / 2
        if (W[:, 2].min() < floor - 1e-4): lifts += 1
        bvf = BVHTree.FromPolygons([Vector(p) for p in W], t["T"], all_triangles=True)
        c_, e_ = (W.max(0) + W.min(0)) / 2, (W.max(0) - W.min(0)) / 2
        Ws = c_ + (W - c_) * np.maximum(e_ - 0.001, 0) / np.maximum(e_, 1e-6)      # 1 mm in from its bounds: contacts don't count
        bv = BVHTree.FromPolygons([Vector(p) for p in Ws], t["T"], all_triangles=True)
        if bvf.overlap(fbvh):
            clip_frame[k] = clip_frame.get(k, 0) + 1
            if "--debug" in argv: print("FRAMECLIP", k, u["index"], u["bay"], u["layer"], u["row"], "W min", W.min(0).round(3), "max", W.max(0).round(3))
        WB[(u["index"], k)] = (W, bv, W.min(0), W.max(0))
        scales.setdefault(k, set()).add(round(s, 4)); heights.setdefault(k, []).append(float(W[:, 2].max() - W[:, 2].min()))
pairs = 0
for bay in range(4):
    us = [u for u in units if u["bay"] == bay]
    for i, a in enumerate(us):
        for b in us[i + 1:]:
            for ka in CK:
                for kb in CK:
                    A, Bv = WB[(a["index"], ka)], WB[(b["index"], kb)]
                    if (A[2] <= Bv[3]).all() and (Bv[2] <= A[3]).all():
                        pairs += 1
                        if A[1].overlap(Bv[1]):
                            key = (ka, kb) if ka == kb else ("mixed", "")
                            clip_pair[key] = clip_pair.get(key, 0) + 1
                            if "--debug" in argv and key[0] != "mixed": print("PAIRCLIP", ka, kb, a["index"], a["layer"], a["row"], b["index"], b["layer"], b["row"], A[2].round(3), A[3].round(3), Bv[2].round(3), Bv[3].round(3))
# same kind, full bay: the stack tops (what a full bay shows)
stack_top = {}
for k in CK:
    for bay, (col, tier) in enumerate(BAYS):
        stack_top.setdefault(k, []).append(round(max(WB[(u["index"], k)][3][2] for u in units if u["bay"] == bay) - PT[tier], 3))
checks = {"clipping_frame": clip_frame, "clipping_copy_pairs_same_kind": {f"{a}|{b}": n for (a, b), n in clip_pair.items() if a != "mixed"}, "mixed_bay_pairs_overlapping": clip_pair.get(("mixed", ""), 0),
          "copy_pairs_tested": pairs, "units_x_kinds": len(units) * len(CK), "kinds_checked": CK, "mod_floor_lifts": lifts,
          "item_height_m": {k: round(float(np.mean(v)), 3) for k, v in heights.items()},
          "full_stack_height_over_plank_m": {k: v[0] for k, v in stack_top.items()}, "bay_clear_height_m": CLEAR}
print("CHECKS", json.dumps(checks), "seconds", round(time.time() - t0, 1), flush=True)

# ---------- files: atlas (saved) -> OBJ -> anchors last ----------
bpy.ops.object.select_all(action="DESELECT"); frame.select_set(True); bpy.context.view_layer.objects.active = frame
bpy.ops.wm.obj_export(filepath=os.path.join(OUTA, "ClothRack.obj"), export_selected_objects=True, export_materials=False,
                      export_triangulated_mesh=True, forward_axis="NEGATIVE_Z", up_axis="Y")
items = {}
for k in KINDS:
    t = TPL[k]
    items[k] = {"bounds_size_unity": [round(a, 4) for a in t["size"]], "drawn_size_in_a_unit_m": sorted([round(a * min(scales[k]), 3) for a in t["size"]], reverse=True)}
items["LinenThread"]["note"] = ("LinenThread's prefab is a Unity built-in capsule plus a stick: not in the rip, and Player.log had no "
                                "\"Item model 'LinenThread'\" line yet. Checked and rendered with a 0.25 m spindle stand-in (a stick through a wound "
                                "cop) and a fat worst case (Unity capsule 1 x 2 x 1 + stick); the layout rule keeps any shape inside its unit.")
doc = {
    "store": "Cloth Rack round 1: a half-width spinner's cabinet, 2 columns x 2 tiers = 4 bays, one cloth or thread kind per bay, "
             "bolts and spindles lying left-right, stacked layer by layer; a carved crown with a drop spindle on its arm, a linen cloth draped at the left",
    "schema": "storehouse-anchors/1", "slots": len(units), "units": len(units), "columns": 4, "rows": len(units) // 4, "stack_per_unit": 1,
    "placement": "normal (stands on a floor in a house)",
    "frame": {"obj": "ClothRack.obj", "tris": frame_tris, "size_m": [round(a, 3) for a in frame_size], "atlas": "clothrack_atlas.png 128x128",
              "atlas_sources": "rows 0-31 hewn timber, 32-63 x0-63 end grain, 64-79 iron: assets/bunker_r4; 32-63 x64-95 dark oiled timber, "
                               "x96-127 wear swatch: assets/metalpallet_r3; 80-111 linen with a madder border, 112-127 rope, wound yarn, soapstone (new)"},
    "space": "Unity prefab space, origin = footprint centre on the floor, +z front, +y up, +x the left side seen from the front. "
             "Blender z-up/-y front -> Unity: ux=-bx, uy=bz, uz=-by. OBJ export (forward NEGATIVE_Z, up Y) writes (bx, bz, -by); the mod's loader negates x.",
    "unit_semantics": "One stack per unit, one copy (layout rule, like the larder): position = bottom centre of the unit's box on its bay's plank; "
                      "box = [x, 4 layers, z]; the mod turns the item long axis -> +x, thin axis -> up (align), then by the small yaw "
                      "(then_rotate_quat_xyzw), fits the turned bounds into box_x*0.96 x box_y/4 x box_z*0.96 and lifts layer k by k x its own "
                      "turned height (pitch_frac 1.0): bounds on bounds, never a gap, never an overlap. copy.offset x/z = a small jitter.",
    "fill_order": "per bay (group key \"bay\" 0-3: 0 top left, 1 top right, 2 bottom left, 3 bottom right, seen from the front): layer 0 front, "
                  "layer 0 back, layer 1 front, ... up to layer 3 back. One item kind per bay.",
    "bays": [{"bay": b, "column": c, "tier": ("bottom", "top")[t], "plank_top_y": PT[t], "centre_x": round(-BAYX[c], 4),
              "clear_m": [round(CW, 3), CLEAR, round(BACK_IN - FRONT_EDGE, 3)], "render_item": DEFAULT_KIND[b]} for b, (c, t) in enumerate(BAYS)],
    "items": items, "checks": checks, "units_list": units}
tmp = os.path.join(OUT, "clothrack_anchors.json.tmp")
json.dump(doc, open(tmp, "w"), indent=1)
os.replace(tmp, os.path.join(OUTA, "clothrack_anchors.json"))
print("CLOTHRACK frame tris", frame_tris, "units", len(units), flush=True)
if NORENDER:
    print("DONE"); sys.exit(0)

# ---------- renders: replayed from the EXPORTED files the mod's way ----------
for o in list(bpy.data.objects): bpy.data.objects.remove(o, do_unlink=True)

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
    m = atlas_mat(png, os.path.basename(png) + str(dx) + str(dy))
    for o in new:
        o.data.materials.clear(); o.data.materials.append(m); o.location = (dx, dy, 0)
    return new

RAW = {}
def raw(item):
    """an item's render mesh + its Unity item-space bounds (stand-in for LinenThread)"""
    if item in TPL: t = TPL[item]; return t["mesh"], t["size"], t["center"]
    if item not in RAW:
        ob = load_item(item, anchor="origin")[0]
        me = ob.data; bpy.data.objects.remove(ob, do_unlink=True)
        Vu = np.array([tuple(v.co) for v in me.vertices], float) @ B2U.T
        RAW[item] = (me, Vu.max(0) - Vu.min(0), (Vu.max(0) + Vu.min(0)) / 2)
    return RAW[item]

def spawn(folder, obj, png, anchors, fill, dx, dy, kinds=None):
    """a store replayed from its files: per group its first fill x units in list order (no groups: the first fill x units),
    one item kind per group (kinds[group], else each unit's example item)"""
    import_frame(os.path.join(folder, obj), os.path.join(folder, png), dx, dy)
    if fill <= 0: return 0
    d = json.load(open(os.path.join(folder, anchors)))
    ul = d.get("units_list") or d.get("units_data") or d.get("units")
    groups = {}
    for u in ul: groups.setdefault(u.get("bay", -1), []).append(u)
    n = 0
    for g, us in groups.items():
        for u in us[:round(fill * len(us))]:
            item = kinds[g] if kinds and g >= 0 else u.get("example_item")
            me, size, center = raw(item)
            for c in u["copies"]:
                M, _ = place(u, c, size, center)
                Mb = np.eye(4); Mb[:3, :3] = B2U.T @ M[:3, :3] @ B2U; Mb[:3, 3] = B2U.T @ M[:3, 3]
                ob = bpy.data.objects.new("copy", me); sc.collection.objects.link(ob)
                ob.matrix_world = Matrix.Translation((dx, dy, 0)) @ Matrix([list(r) for r in Mb])
                n += 1
    return n

pm = bpy.data.materials.new("plain"); pm.use_nodes = True
pm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.62, 0.60, 0.55, 1)
def post(x, y):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(x, y, 0.9)); p = bpy.context.active_object
    p.scale = (0.12, 0.12, 1.8); p.data.materials.append(pm); p.name = "post_1.8m"

A_ = (OUTA, "ClothRack.obj", "clothrack_atlas.png", "clothrack_anchors.json")
ROWS = {"empty": 0.0, "half": 6.0, "full": 12.0, "fam": 30.0}
spawn(*A_, 0.0, 0.0, ROWS["empty"], DEFAULT_KIND)
spawn(*A_, 0.5, 0.0, ROWS["half"], DEFAULT_KIND)
spawn(*A_, 1.0, 0.0, ROWS["full"], DEFAULT_KIND)
post(1.05, ROWS["full"] + 0.1)
spawn(*A_, 1.0, 0.0, ROWS["fam"], DEFAULT_KIND)
import_frame(os.path.join(REPO, "assets", "bunker_r4", "Bunker.obj"), os.path.join(REPO, "assets", "bunker_r4", "bunker_atlas.png"), -3.35, ROWS["fam"] + 0.6)
MR = os.path.join(REPO, "assets", "meadrack_r2")
nm = spawn(MR, "MeadRack.obj", "meadrack_atlas.png", "meadrack_anchors.json", 1.0, 2.25, ROWS["fam"])
post(3.85, ROWS["fam"] + 0.1)
print("MEAD copies", nm, flush=True)

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
    "empty": (-30, 3.6, EYE, (0.0, ROWS["empty"], 0.95), 35),
    "half": (-30, 3.6, EYE, (0.0, ROWS["half"], 0.95), 35),
    "full": (-30, 3.6, EYE, (0.0, ROWS["full"], 0.95), 35),
    "standing": (0, 2.9, EYE, (0.0, ROWS["half"], 0.98), 30),
    "fullpost": (-18, 4.2, 1.5, (0.3, ROWS["full"], 0.95), 35),
    "family": (-8, 10.0, 2.3, (-0.2, ROWS["fam"] + 0.4, 0.95), 35),
    "detail": (-35, 1.5, 1.95, (0.15, ROWS["full"], 1.5), 30),
}
for vn, (yaw, dist, hgt, tgt, lens) in VIEWS.items():
    if VIEWSEL and vn not in VIEWSEL: continue
    t = Vector(tgt)
    cam.location = t + Vector((math.sin(math.radians(yaw)) * dist, -math.cos(math.radians(yaw)) * dist, hgt - t.z))
    cam.rotation_euler = (t - cam.location).to_track_quat("-Z", "Y").to_euler(); cam.data.lens = lens
    sc.render.filepath = os.path.join(OUT, f"clothrack1-{vn}.png")
    bpy.ops.render.render(write_still=True)
    print("RENDER", vn, flush=True)
print("DONE")
