"""Meat Rack, our own mesh and our own texture (no vanilla geometry or texture in it).
Run: blender -b -P meatrack.py -- [--out DIR] [--tag NAME] [--no-ref]
Writes meatrack_atlas.png (128x256, point-filtered), MeatRack.obj (frame), MeatRackItems.obj (one object per hanging
item, name order = fill order) and meatrack.json into assets/meatrack/, then renders a preview beside the vanilla
wood chest (local rip, reference only) for scale and palette.

Atlas 128x256, rows from the top (v 1.0 downwards), each strip 32 px high:
  v 0.875-1.0 hewn timber   v 0.75-0.875 end grain (4 tiles)   v 0.625-0.75 iron   v 0.5-0.625 stained tray wood
  v 0.0-0.5   VARIANT GRID: 4 x 4 cells of 32x32 px = 16 colour variants. Each cell has four 16x16 role quadrants:
              role 0 body (lower left), role 1 light (fat, belly, bone; lower right),
              role 2 dark (back, skin, hoof; upper left),  role 3 hemp cord (upper right, same in every cell).
A content mesh is UV-mapped into ONE cell. The mod picks a variant by shifting every UV of that item by whole cells:
  du = +0.25 per cell column, dv = +0.125 per cell row.
"""
import bpy, bmesh, sys, os, math, json, random
import numpy as np
from mathutils import Vector, Matrix, Euler
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
OUTA = os.path.normpath(os.path.join(HERE, "..", "assets", "meatrack"))
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = argv[argv.index("--out") + 1] if "--out" in argv else \
    "C:/Users/joost/AppData/Local/Temp/claude/C--Users-joost--pai/5e4bc60b-cdfe-4638-8e29-2e507fa13cf9/scratchpad/proto/meatrack"
TAG = argv[argv.index("--tag") + 1] if "--tag" in argv else "meatrack"
RIP = "C:/Users/joost/ValheimRip/chests/piece_chest_wood"
os.makedirs(OUTA, exist_ok=True); os.makedirs(OUT, exist_ok=True)
rng = random.Random(7)

TEXW, TEXH = 128, 256
DENS = 48.0                      # px per metre, vanilla wood is 47-57
SH = 32.0 / TEXH                 # v height of one strip
STRIP = {"hewn": 0.875, "end": 0.75, "iron": 0.625, "stain": 0.5}

# ---------- texture ----------
def srgb(c): return np.array(c, dtype=np.float32)
WOOD, WOOD_D = srgb((0.38, 0.29, 0.18)), srgb((0.21, 0.16, 0.10))
STAIN, STAIN_D = srgb((0.26, 0.20, 0.13)), srgb((0.12, 0.10, 0.07))     # drip tray, wet and dark
END, END_D = srgb((0.55, 0.45, 0.31)), srgb((0.35, 0.27, 0.17))
IRON, IRON_D = srgb((0.22, 0.21, 0.20)), srgb((0.09, 0.09, 0.09))
HEMP, HEMP_D = srgb((0.46, 0.38, 0.25)), srgb((0.30, 0.24, 0.15))
CREAM = srgb((0.86, 0.78, 0.66))

# (name, main colour). light and dark are derived. Muted, only the flesh colours carry any chroma.
VARIANTS = [
    ("red meat", (0.52, 0.19, 0.16)), ("pink meat", (0.66, 0.40, 0.38)), ("dark lox meat", (0.30, 0.12, 0.13)),
    ("silver fish", (0.60, 0.63, 0.62)),
    ("blue-grey fish", (0.34, 0.44, 0.52)), ("golden fish", (0.74, 0.46, 0.30)), ("pale poultry", (0.76, 0.64, 0.48)),
    ("brown game", (0.42, 0.30, 0.20)),
    ("swamp green", (0.32, 0.42, 0.24)), ("mist purple", (0.44, 0.28, 0.46)), ("deep teal", (0.22, 0.46, 0.46)),
    ("fatty ochre", (0.72, 0.60, 0.26)),
    ("sausage brown-red", (0.48, 0.24, 0.18)), ("smoked brown", (0.36, 0.24, 0.16)), ("bone white", (0.76, 0.72, 0.62)),
    ("charcoal", (0.22, 0.21, 0.22)),
]

def build_atlas():
    nr = np.random.default_rng(3)
    img = np.zeros((TEXH, TEXW, 3), np.float32)          # row 0 = v 0 (bottom)
    x = np.arange(TEXW)[None, :].repeat(32, 0).astype(np.float32)
    y = np.arange(32)[:, None].repeat(TEXW, 1).astype(np.float32)
    tile = lambda k: 2 * math.pi * k / TEXW

    def grain(c1, c2, rows):
        g = np.sin(y * 1.25 + 1.6 * np.sin(x * tile(2) + y * 0.15) + 0.7 * np.sin(x * tile(5)))
        t = np.clip((g - 0.55) * 2.5, 0, 1) * 0.65 + nr.random((32, TEXW)) * 0.18
        t += np.clip(1 - np.minimum(y, 31 - y) / 3.0, 0, 1) * 0.35
        img[rows] = c1 * (1 - t[..., None]) + c2 * t[..., None]
    grain(WOOD, WOOD_D, slice(224, 256))
    for k in range(4):                                    # end grain tiles
        cx, cy = 15.5 + nr.uniform(-2, 2), 15.5 + nr.uniform(-2, 2)
        xx, yy = np.meshgrid(np.arange(32), np.arange(32))
        d = np.hypot(xx - cx, yy - cy) + 0.6 * np.sin(np.arctan2(yy - cy, xx - cx) * 3 + k)
        t = (np.sin(d * 1.5) * 0.5 + 0.5) * 0.45 + nr.random((32, 32)) * 0.15
        t = np.where(d > 13.5, 0.95, t)
        img[192:224, 32 * k:32 * k + 32] = END * (1 - t[..., None]) + END_D * t[..., None]
    t = nr.random((32, TEXW)) * 0.4 + np.clip(1 - np.minimum(y, 31 - y) / 4.0, 0, 1) * 0.5
    img[160:192] = IRON * (1 - t[..., None]) + IRON_D * t[..., None]
    grain(STAIN, STAIN_D, slice(128, 160))

    # variant grid
    for k, (_, main) in enumerate(VARIANTS):
        cx, cy = k % 4, k // 4
        main = srgb(main)
        main = main * 0.78 + float(main @ np.array([0.3, 0.59, 0.11], np.float32)) * 0.22   # mute: pull 22% toward grey
        light = main * 0.42 + CREAM * 0.58
        dark = main * 0.5
        yy, xx = np.mgrid[0:16, 0:16].astype(np.float32)
        nz = nr.random((16, 16))
        scale = ((xx + yy) % 5 < 2).astype(np.float32) * 0.07           # faint diagonal scale / fibre pattern
        body = main * (0.86 + 0.26 * nz[..., None] + scale[..., None])
        speck = (nr.random((16, 16)) < 0.10)[..., None]
        body = np.where(speck, body * 0.45 + light * 0.55, body)         # fat marbling
        lt = light * (0.92 + 0.16 * nz[..., None])
        dk = dark * (0.85 + 0.30 * nz[..., None])
        cd = (HEMP * (0.85 + 0.3 * nz[..., None])) * np.where((yy % 4 < 2), 1.0, 0.8)[..., None]
        for (qx, qy), q in (((0, 0), body), ((1, 0), lt), ((0, 1), dk), ((1, 1), cd)):
            r0, c0 = cy * 32 + qy * 16, cx * 32 + qx * 16
            img[r0:r0 + 16, c0:c0 + 16] = q
    im = bpy.data.images.new("meatrack_atlas", TEXW, TEXH, alpha=False)
    px = np.concatenate([np.clip(img, 0, 1), np.ones((TEXH, TEXW, 1), np.float32)], 2)
    im.pixels.foreach_set(px.ravel())
    im.filepath_raw = os.path.join(OUTA, "meatrack_atlas.png"); im.file_format = "PNG"; im.save()
    return im

# ---------- frame geometry (timbers, as in crib.py) ----------
PARTS, ITEMS = [], []
UV = None

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
            l[UV].uv = ((k + 0.5 + a * 0.45) / 4, STRIP["end"] + (0.5 + b * 0.45) * SH)
        return
    ua = long_axis if long_axis in tang else tang[0]
    va = tang[1] if ua == tang[0] else tang[0]
    off = (seed * 0.37) % 1
    vs = [l.vert.co[va] for l in f.loops]
    vmin, span = min(vs), max(max(vs) - min(vs), 1e-4)
    vscale = min(1.0, (32 / DENS) / span)
    base = STRIP[kind]
    for l in f.loops:
        u = l.vert.co[ua] * DENS / TEXW + off
        v = base + ((l.vert.co[va] - vmin) * vscale * DENS / TEXH) * 0.94 + 0.004
        l[UV].uv = (u, v)

def timber(name, size, pos, kind="hewn", rot=(0, 0, 0), jitter=0.02, bevel=0.02):
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

# ---------- content meshes: little low-poly lathe / box builders, UV by role into a variant cell ----------
QUAD = {0: (0, 0), 1: (1, 0), 2: (0, 1), 3: (1, 1)}

class MB:
    def __init__(s): s.v, s.f = [], []
    def vert(s, p): s.v.append(Vector(p)); return len(s.v) - 1
    def add(s, idx, role):
        pts = [s.v[i] for i in idx]; n = Vector(); c = Vector()
        for a, b in zip(pts, pts[1:] + pts[:1]):                      # Newell normal, gives the face's side for the role rule
            n += Vector(((a.y - b.y) * (a.z + b.z), (a.z - b.z) * (a.x + b.x), (a.x - b.x) * (a.y + b.y)))
            c += a
        c /= len(pts)
        s.f.append((idx, role(c, n.normalized()) if callable(role) else role))
    def lathe(s, rings, sides, role, jit=0.007, phase=0.0, cap_top=True, cap_bottom=True):
        R = []
        for (z, rx, ry, cx, cy) in rings:                # top to bottom
            if rx < 1e-6:
                R.append([s.vert((cx, cy, z))])
            else:
                R.append([s.vert((cx + rx * math.cos(phase + 2 * math.pi * j / sides) + rng.uniform(-jit, jit),
                                  cy + ry * math.sin(phase + 2 * math.pi * j / sides) + rng.uniform(-jit, jit),
                                  z + rng.uniform(-jit, jit))) for j in range(sides)])
        for a, b in zip(R, R[1:]):
            if len(a) == 1 and len(b) == 1: continue
            for j in range(sides):
                j2 = (j + 1) % sides
                if len(a) == 1: s.add([a[0], b[j2], b[j]], role)
                elif len(b) == 1: s.add([a[j], a[j2], b[0]], role)
                else: s.add([a[j], a[j2], b[j2], b[j]], role)
        if cap_top and len(R[0]) > 1: s.add(R[0][::-1], role)
        if cap_bottom and len(R[-1]) > 1: s.add(R[-1], role)
    def box(s, c, size, role, rot=(0, 0, 0), jit=0.0015):
        M = Euler([math.radians(a) for a in rot]).to_matrix()
        ids = []
        for ix in (-1, 1):
            for iy in (-1, 1):
                for iz in (-1, 1):
                    p = M @ Vector((ix * size[0] / 2 + rng.uniform(-jit, jit), iy * size[1] / 2 + rng.uniform(-jit, jit),
                                    iz * size[2] / 2 + rng.uniform(-jit, jit)))
                    ids.append(s.vert(Vector(c) + p))
        for q in ((0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)):
            s.add([ids[i] for i in q], role)
    def cord(s, length=0.07, role=3):                    # hemp loop from the hook down to the item (triangular prism, 8 tris)
        s.lathe([(0, 0.009, 0.009, 0, 0), (-length, 0.009, 0.009, 0, 0)], 3, role, jit=0.0006)

def haunch(mb):
    mb.cord(0.07)
    mb.lathe([(-0.06, 0, 0, 0, 0), (-0.09, 0.05, 0.045, 0, 0), (-0.15, 0.115, 0.10, 0.012, 0.004),
              (-0.25, 0.125, 0.105, 0.018, -0.004), (-0.33, 0.075, 0.065, -0.004, 0), (-0.40, 0.04, 0.037, -0.006, 0)], 6,
             lambda c, n: 2 if n.x < -0.5 else (1 if c.z > -0.12 else 0), phase=0.3, jit=0.01)
    mb.box((-0.006, 0, -0.44), (0.032, 0.032, 0.09), 1)
    mb.box((-0.006, 0, -0.495), (0.065, 0.055, 0.04), 1, rot=(0, 0, 20))

def fish(mb):
    mb.cord(0.04)
    mb.lathe([(-0.035, 0.075, 0.006, 0, 0), (-0.10, 0.022, 0.014, 0, 0)], 4, 2)             # tail fin
    mb.lathe([(-0.10, 0.022, 0.014, 0, 0), (-0.20, 0.075, 0.042, 0, 0), (-0.31, 0.095, 0.052, 0, 0),
              (-0.41, 0.07, 0.045, 0, 0), (-0.50, 0.03, 0.03, 0, 0), (-0.55, 0, 0, 0, 0)], 6,
             lambda c, n: 2 if n.x > 0.35 else (1 if n.x < -0.35 else 0), phase=0.0, cap_top=True)
    for sy in (-1, 1):                                                                         # eyes, one quad per flank
        a = mb.vert((0.03, sy * 0.043, -0.44)); b = mb.vert((-0.012, sy * 0.043, -0.44))
        c = mb.vert((-0.012, sy * 0.043, -0.475)); d = mb.vert((0.03, sy * 0.043, -0.475))
        mb.add([a, b, c, d] if sy > 0 else [d, c, b, a], 2)

def bird(mb, hare=False):
    k = 0.95 if hare else 1.0
    mb.cord(0.06)
    mb.box((0, 0, -0.085), (0.032, 0.03, 0.05), 3 if not hare else 2)                          # feet / hocks
    mb.lathe([(-0.10 * k, 0.05, 0.045, 0, 0), (-0.17 * k, 0.10, 0.09, 0, 0.0), (-0.28 * k, 0.105, 0.09, 0, 0),
              (-0.37 * k, 0.07, 0.06, 0, 0), (-0.42 * k, 0.025, 0.025, 0, 0)], 5,
             lambda c, n: 2 if n.x < -0.3 else (1 if (n.x > 0.3 and c.z > -0.3 * k) else 0), phase=0.2)
    mb.lathe([(-0.42 * k, 0, 0, 0, 0), (-0.455 * k, 0.04, 0.034, 0, 0), (-0.51 * k, 0.034, 0.03, 0, 0),
              (-0.55 * k, 0, 0, 0, 0)], 4, 2)                                               # head
    if hare:
        for sx in (-0.02, 0.02):
            mb.box((sx, 0, -0.62 * k), (0.012, 0.03, 0.07), 2, rot=(0, rng.uniform(-8, 8), 0))
    else:                                                                                     # wings folded on the flanks
        for sy in (-1, 1):
            mb.lathe([(-0.13, 0.065, 0.009, -0.01, sy * 0.093), (-0.26, 0.05, 0.008, -0.01, sy * 0.093),
                      (-0.40, 0, 0, -0.01, sy * 0.093)], 4, 2, jit=0.003)
        mb.box((0.0, 0.0, -0.545), (0.016, 0.016, 0.05), 3)                                   # beak

def tail(mb):
    mb.cord(0.07)
    mb.box((0, 0, -0.125), (0.05, 0.05, 0.025), 3, rot=(0, 0, 25))
    mb.lathe([(-0.06, 0.02, 0.02, 0, 0), (-0.14, 0.042, 0.04, 0.0, 0), (-0.30, 0.055, 0.05, 0.012, 0),
              (-0.48, 0.05, 0.047, 0.008, 0), (-0.58, 0.02, 0.02, 0, 0)], 6,
             lambda c, n: 2 if c.z > -0.2 else (1 if c.z < -0.47 else 0))

SHAPES = {"haunch": haunch, "fish": fish, "bird": bird, "hare": lambda mb: bird(mb, True), "tail": tail}

def make_item(name, shape, variant, scale, yaw, tilt, anchor):
    mb = MB(); SHAPES[shape](mb)
    cell = (variant % 4, variant // 4)
    M = Matrix.Translation(Vector(anchor)) @ Euler([math.radians(tilt[0]), math.radians(tilt[1]), math.radians(yaw)]).to_matrix().to_4x4() \
        @ Matrix.Scale(scale, 4)
    bm = bmesh.new(); uvl = bm.loops.layers.uv.verify()
    bv = [bm.verts.new(M @ v) for v in mb.v]
    faces = []
    for idx, role in mb.f:
        faces.append((bm.faces.new([bv[i] for i in idx]), role))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    for f, role in faces:
        qx, qy = QUAD[role]
        ox, oy = cell[0] * 32 + qx * 16, cell[1] * 32 + qy * 16
        n = f.normal; ax = max(range(3), key=lambda i: abs(n[i])); tang = [i for i in range(3) if i != ax]
        c = f.calc_center_median(); jx, jy = rng.uniform(-3, 3), rng.uniform(-3, 3)
        for l in f.loops:
            a = max(-4, min(4, (l.vert.co[tang[0]] - c[tang[0]]) * DENS))
            b = max(-4, min(4, (l.vert.co[tang[1]] - c[tang[1]]) * DENS))
            up = min(14.5, max(1.5, 8 + jx + a)); vp = min(14.5, max(1.5, 8 + jy + b))
            l[uvl].uv = ((ox + up) / TEXW, (oy + vp) / TEXH)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = False
    ob = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(ob)
    ob.data.materials.append(MAT); ITEMS.append(ob)
    ob["shape"] = shape; ob["variant"] = variant; ob["cell"] = list(cell)
    return ob

# ---------- the rack ----------
FOOT_Y, APEX_Y, APEX_Z, FOOT_Z = 0.50, 0.07, 1.83, 0.05
LEG_X = 1.05
THETA = math.degrees(math.atan2(FOOT_Y - APEX_Y, APEX_Z - FOOT_Z))
def leg_y(z): return FOOT_Y - (FOOT_Y - APEX_Y) * (z - FOOT_Z) / (APEX_Z - FOOT_Z)

RIDGE_Z, RAIL_Z = 1.90, 1.42
RAIL_Y = leg_y(RAIL_Z) + 0.062 + 0.045 - 0.008            # lashed to the outside of the legs
SLOTS = []

def hook(x, y, zb, s):
    """Iron hook hanging under a beam bottom zb at (x, y); prong points to s*y. Returns the cord anchor."""
    sh = 0.11
    timber("hook", (0.03, 0.03, sh), (x, y, zb - sh / 2 + 0.01), kind="iron", jitter=0.0015, bevel=0)
    zp = zb - sh + 0.01
    timber("hook", (0.03, 0.09, 0.03), (x, y + s * 0.03, zp), kind="iron", jitter=0.0015, bevel=0)
    timber("hook", (0.03, 0.03, 0.055), (x, y + s * 0.06, zp + 0.0125), kind="iron", jitter=0.0015, bevel=0)
    return (x, y + s * 0.03, zp - 0.015 - 0.009)

def build_rack():
    SLOTS.clear()
    for sx in (-1, 1):
        for sy in (-1, 1):
            timber("leg", (0.13, 0.12, math.hypot(FOOT_Y - APEX_Y, APEX_Z - FOOT_Z)),
                   (sx * LEG_X, sy * (FOOT_Y + APEX_Y) / 2, (APEX_Z + FOOT_Z) / 2), rot=(sy * THETA, 0, 0))
        timber("sill", (0.15, 1.16, 0.09), (sx * LEG_X, 0, 0.045), rot=(0, 0, rng.uniform(-1, 1)))
        for z, th in ((0.30, 0.09), (0.95, 0.08)):                                   # ties across each A
            w = 2 * leg_y(z) + 0.06
            timber("tie", (0.10 if z < 0.5 else 0.09, w, th), (sx * LEG_X, 0, z))
        timber("band", (0.06, 0.17, 0.17), (sx * LEG_X, 0, RIDGE_Z), kind="iron", jitter=0.002, bevel=0)
        for sy in (-1, 1):
            timber("clamp", (0.06, 0.105, 0.105), (sx * LEG_X, sy * RAIL_Y, RAIL_Z), kind="iron", jitter=0.002, bevel=0)
    timber("ridge", (2.30, 0.14, 0.14), (0, 0, RIDGE_Z), rot=(0, rng.uniform(-0.4, 0.4), 0))
    for sy in (-1, 1):
        timber("rail", (2.30, 0.09, 0.09), (0, sy * RAIL_Y, RAIL_Z), rot=(0, rng.uniform(-0.4, 0.4), 0))
    # drip tray, on the low ties
    timber("tray", (2.0, 0.66, 0.04), (0, 0, 0.365), kind="stain", bevel=0.008, jitter=0.01)
    for sy in (-1, 1): timber("trayside", (2.0, 0.045, 0.085), (0, sy * 0.333, 0.425), kind="stain", bevel=0.008, jitter=0.006)
    for sx in (-1, 1): timber("trayend", (0.045, 0.62, 0.085), (sx * 0.978, 0, 0.425), kind="stain", bevel=0.008, jitter=0.006)

    # hooks: top row on the ridge (alternating prong side), then one row on each rail pointing outward
    top_x = [-0.77 + 0.22 * i for i in range(8)]
    for i, x in enumerate(top_x):
        SLOTS.append(("top", i, x, hook(x, 0, RIDGE_Z - 0.07, 1 if i % 2 else -1)))
    front_x = [-0.56 + 0.28 * i for i in range(5)]
    for i, x in enumerate(front_x):
        SLOTS.append(("front", i, x, hook(x, -RAIL_Y, RAIL_Z - 0.045, -1)))
    back_x = [-0.42 + 0.28 * i for i in range(4)]
    for i, x in enumerate(back_x):
        SLOTS.append(("back", i, x, hook(x, RAIL_Y, RAIL_Z - 0.045, 1)))

    # what hangs where: (shape, colour variant, scale)
    spec = {"top": [("fish", 4, 1.1), ("haunch", 0, 1.0), ("tail", 12, 1.0), ("haunch", 2, 1.05), ("fish", 3, 1.1),
                    ("haunch", 1, 0.95), ("fish", 5, 1.0), ("haunch", 8, 0.9)],
            "front": [("bird", 6, 1.0), ("fish", 10, 0.95), ("hare", 7, 1.0), ("tail", 0, 0.9), ("fish", 5, 0.9)],
            "back": [("fish", 3, 0.9), ("bird", 7, 1.0), ("haunch", 2, 0.8), ("fish", 9, 0.95)]}
    # fill order: each row from the middle out, rows interleaved top, front, back
    rows = {}
    for r in ("top", "front", "back"):
        sl = [s for s in SLOTS if s[0] == r]
        mid = sum(s[2] for s in sl) / len(sl)
        rows[r] = sorted(sl, key=lambda s: (abs(s[2] - mid), s[2]))
    order = []
    for n in range(8):
        for r in ("top", "front", "back"):
            if n < len(rows[r]): order.append(rows[r][n])
    for k, (r, i, x, anchor) in enumerate(order):
        shape, var, sc = spec[r][i]
        yaw = rng.uniform(-14, 14) if shape == "fish" else rng.uniform(-35, 35)
        make_item(f"item_{k:03d}", shape, var, sc, yaw, (rng.uniform(-2.5, 2.5), rng.uniform(-2.5, 2.5)), anchor)
        ITEMS[-1]["row"], ITEMS[-1]["slot"] = r, i

# ---------- scene ----------
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
atlas = build_atlas()
MAT = bpy.data.materials.new("meatrack"); MAT.use_nodes = True
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

def polys(obs):
    V, P = [], []
    for o in obs:
        b = len(V); V += [v.co.copy() for v in o.data.vertices]
        P += [[b + i for i in p.vertices] for p in o.data.polygons]
    return V, P

racks = []
for k, fill in enumerate(reversed(FILLS)):
    rng.seed(7); PARTS.clear(); ITEMS.clear()
    build_rack()
    if k == 0:
        fv, fp = polys(PARTS); ft = BVHTree.FromPolygons(fv, fp)
        trees = [BVHTree.FromPolygons(*polys([o])) for o in ITEMS]
        clip = [o.name for o, t in zip(ITEMS, trees) if ft.overlap(t)]
        pair = sum(1 for i in range(len(trees)) for j in range(i + 1, len(trees)) if trees[i].overlap(trees[j]))
        print("CLIPPING", len(clip), "of", len(ITEMS), clip, "| item-item overlapping pairs (info):", pair)
        allv = [v for v in fv]
        bb = [(min(v[i] for v in allv), max(v[i] for v in allv)) for i in range(3)]
        print("FRAME BBOX m: x %.2f y %.2f z %.2f" % tuple(b[1] - b[0] for b in bb))
        stats = {"frame_tris": tris(PARTS), "item_count": len(ITEMS), "items_tris": tris(ITEMS),
                 "frame_bbox_m": [round(b[1] - b[0], 2) for b in bb], "atlas": "meatrack_atlas.png 128x256, Closest",
                 "variant_cells": [{"index": i, "name": n, "cell_col": i % 4, "cell_row": i // 4}
                                   for i, (n, _) in enumerate(VARIANTS)],
                 "uv_shift_per_cell": {"du": 0.25, "dv": 0.125},
                 "items": [{"name": o.name, "shape": o["shape"], "variant": o["variant"], "row": o["row"], "slot": o["slot"],
                            "tris": tris([o])} for o in ITEMS]}
        for obs, fn in ((PARTS, "MeatRack.obj"), (ITEMS, "MeatRackItems.obj")):
            bpy.ops.object.select_all(action="DESELECT")
            for o in obs: o.select_set(True)
            bpy.ops.wm.obj_export(filepath=os.path.join(OUTA, fn), export_selected_objects=True, export_materials=False,
                                  export_triangulated_mesh=True, forward_axis="NEGATIVE_Z", up_axis="Y")
        json.dump(stats, open(os.path.join(OUTA, "meatrack.json"), "w"), indent=1)
        print("MEATRACK frame_tris", stats["frame_tris"], "items_tris", stats["items_tris"], "items", len(ITEMS))
    shown = ITEMS[:max(1, round(fill * len(ITEMS)))]
    for o in ITEMS[len(shown):]: bpy.data.objects.remove(o, do_unlink=True)
    ob = join(PARTS + shown, f"rack_{int(fill * 100)}")
    ob.location.x = (len(FILLS) - 1 - k) * 3.6 - 3.6
    racks.append(ob)

# vanilla wood chest beside it, for scale and palette (reference only, never exported)
if "--no-ref" not in argv:
    from mathutils import Quaternion
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
        verts = [Vector((-v.x - 6.2, -v.z, v.y)) for v in verts]
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
bpy.ops.mesh.primitive_plane_add(size=30)
gm = bpy.data.materials.new("ground"); gm.use_nodes = True
gm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.16, 0.14, 0.11, 1)
bpy.context.active_object.data.materials.append(gm)
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam); sc.camera = cam
sc.render.engine = "BLENDER_EEVEE_NEXT"
sc.render.resolution_x, sc.render.resolution_y = 1600, 900
sc.view_settings.view_transform = "Standard"
VIEWS = {"fills": (0, 17, 18.4, (-1.0, 0, 1.0)), "close": (-28, 14, 5.6, (3.6, 0, 1.0)),
         "alt": (62, 18, 5.8, (3.6, 0, 1.0))}
for vn, (yaw, pitch, dist, tgt) in VIEWS.items():
    t = Vector(tgt)
    d = Vector((math.cos(math.radians(pitch)) * math.sin(math.radians(yaw)),
                -math.cos(math.radians(pitch)) * math.cos(math.radians(yaw)), math.sin(math.radians(pitch))))
    cam.location = t + d * dist; cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    sc.render.filepath = os.path.join(OUT, f"{TAG}-{vn}.png")
    bpy.ops.render.render(write_still=True)
print("DONE")
