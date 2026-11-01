"""Emergency Shelf, our own mesh and our own texture (no vanilla geometry or texture in it).
Run: blender -b -P emergencyshelf.py -- [--out DIR] [--tag NAME]
Wall-mounted respawn-kit shelf: hewn planks on knee-brace brackets, back ledger, low front lip, iron pegs with a
hanging pouch. Two sizes: 1 m (one shelf) and 2 m (two shelves 0.45 m apart), depth 0.35 m.
Writes into assets/emergencyshelf/: emergencyshelf_atlas.png (128x128, point-filtered), EmergencyShelf{1m,2m}.obj
(frame), EmergencyShelf{1m,2m}Items.obj (one "o" object per item, alphabetical = fill order), emergencyshelf.json.
Renders: <tag>-fills.png, <tag>-close.png, <tag>-small.png into --out.

Frame local space: wall plane is y=0, shelf sticks out towards -y, lower plank bottom at z=0 (top z=0.07).

Atlas (128x128, v=0 bottom), four 32 px strips:
  v 0.75-1.00  contents swatches: 8 columns (16 px wide) x 4 rows (8 px high). A variant = another COLUMN, i.e. add
               col * 0.125 to u. Rows from the top:
               row 0 seal / wax colour per mead:  0 health, 1 stamina, 2 poison res, 3 fire res, 4 frost res,
                                                  5 eitr, 6 plain wax, 7 cork
               row 1 flask glass + liquid tint, same 8 columns
               row 2 food: 0 crust, 1 crumb, 2 cheese, 3 rind, 4 sausage, 5 linen, 6 twine, 7 dark meat
               row 3 misc: 0 clay, 1 dark clay, 2 stew, 3 leather, 4 dark leather, 5 leaf, 6 berry, 7 honey
  v 0.50-0.75  hewn timber side grain     v 0.25-0.50 end grain (4 ring tiles)     v 0.00-0.25 iron
"""
import bpy, bmesh, sys, os, math, json, random
import numpy as np
from mathutils import Vector, Matrix, Euler
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
OUTA = os.path.normpath(os.path.join(HERE, "..", "assets", "emergencyshelf"))
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = argv[argv.index("--out") + 1] if "--out" in argv else OUTA
TAG = argv[argv.index("--tag") + 1] if "--tag" in argv else "emergencyshelf"
os.makedirs(OUTA, exist_ok=True); os.makedirs(OUT, exist_ok=True)
rng = random.Random(11)

TEX = 128
DENS = 48.0
STRIP = {"swatch": 0.75, "hewn": 0.50, "end": 0.25, "iron": 0.0}

# ---------- texture ----------
def srgb(c): return np.array(c, dtype=np.float32)
WOOD, WOOD_D = srgb((0.38, 0.29, 0.18)), srgb((0.21, 0.16, 0.10))
END, END_D = srgb((0.55, 0.45, 0.31)), srgb((0.35, 0.27, 0.17))
IRON, IRON_D = srgb((0.22, 0.21, 0.20)), srgb((0.09, 0.09, 0.09))

SEAL = [(0.56, 0.16, 0.13), (0.66, 0.54, 0.16), (0.30, 0.47, 0.18), (0.70, 0.36, 0.10),
        (0.24, 0.40, 0.60), (0.42, 0.24, 0.52), (0.72, 0.66, 0.50), (0.36, 0.28, 0.18)]
GLASS_BASE = srgb((0.15, 0.17, 0.13))
FOOD = [(0.62, 0.44, 0.22), (0.80, 0.66, 0.40), (0.82, 0.66, 0.24), (0.58, 0.40, 0.18),
        (0.50, 0.20, 0.15), (0.72, 0.66, 0.50), (0.45, 0.35, 0.20), (0.30, 0.14, 0.10)]
MISC = [(0.64, 0.40, 0.26), (0.38, 0.22, 0.14), (0.58, 0.30, 0.10), (0.31, 0.21, 0.13),
        (0.18, 0.12, 0.08), (0.30, 0.40, 0.20), (0.45, 0.12, 0.20), (0.70, 0.45, 0.10)]
ROWS = [SEAL, [tuple(0.45 * GLASS_BASE + 0.40 * srgb(c)) for c in SEAL], FOOD, MISC]
# tile codes = row * 8 + col
def T(row, col): return row * 8 + col
CRUST, CRUMB, CHEESE, RIND, SAUSAGE, LINEN, TWINE, MEATD = [T(2, i) for i in range(8)]
CLAY, CLAYD, STEW, LEATHER, LEATHERD, LEAF, BERRY, HONEY = [T(3, i) for i in range(8)]
HEALTH, STAMINA, POISON, FIRE, FROST, EITR, WAX, CORK = range(8)

def build_atlas():
    nr = np.random.default_rng(5)
    img = np.zeros((TEX, TEX, 3), np.float32)
    x = np.arange(TEX)[None, :].repeat(32, 0).astype(np.float32)
    y = np.arange(32)[:, None].repeat(TEX, 1).astype(np.float32)
    tile = lambda k: 2 * math.pi * k / TEX
    # hewn side grain (strip v 0.50-0.75 = image rows 64..95)
    g = np.sin(y * 1.25 + 1.6 * np.sin(x * tile(2) + y * 0.15) + 0.7 * np.sin(x * tile(5)))
    t = np.clip((g - 0.55) * 2.5, 0, 1) * 0.65 + nr.random((32, TEX)) * 0.18
    t += np.clip(1 - np.minimum(y, 31 - y) / 3.0, 0, 1) * 0.35
    img[64:96] = WOOD * (1 - t[..., None]) + WOOD_D * t[..., None]
    # end grain, four 32x32 ring tiles (rows 32..63)
    for k in range(4):
        cx, cy = 15.5 + nr.uniform(-2, 2), 15.5 + nr.uniform(-2, 2)
        xx, yy = np.meshgrid(np.arange(32), np.arange(32))
        d = np.hypot(xx - cx, yy - cy) + 0.6 * np.sin(np.arctan2(yy - cy, xx - cx) * 3 + k)
        t = (np.sin(d * 1.5) * 0.5 + 0.5) * 0.45 + nr.random((32, 32)) * 0.15
        t = np.where(d > 13.5, 0.95, t)
        img[32:64, 32 * k:32 * k + 32] = END * (1 - t[..., None]) + END_D * t[..., None]
    # iron (rows 0..31)
    t = nr.random((32, TEX)) * 0.4 + np.clip(1 - np.minimum(y, 31 - y) / 4.0, 0, 1) * 0.5
    img[0:32] = IRON * (1 - t[..., None]) + IRON_D * t[..., None]
    # swatches (rows 96..127): 8x4 tiles of 16x8 px, mild grain so a flat colour still reads as handmade
    for r in range(4):
        y0 = 96 + (3 - r) * 8
        for c in range(8):
            base = srgb(ROWS[r][c])
            n = 1.0 + (nr.random((8, 16)) - 0.5) * 0.14
            grad = 1.0 + (np.arange(8)[:, None] / 7.0 - 0.5) * 0.10
            img[y0:y0 + 8, c * 16:c * 16 + 16] = np.clip(base * (n * grad)[..., None], 0, 1)
    im = bpy.data.images.new("emergencyshelf_atlas", TEX, TEX, alpha=False)
    px = np.concatenate([np.clip(img, 0, 1), np.ones((TEX, TEX, 1), np.float32)], 2)
    im.pixels.foreach_set(px.ravel())
    im.filepath_raw = os.path.join(OUTA, "emergencyshelf_atlas.png"); im.file_format = "PNG"; im.save()
    return im

# ---------- geometry plumbing ----------
CUR = []          # list the next committed object is appended to

def swatch_uv(f, uvl):
    row, col = divmod(f.material_index, 8)
    u0, v0 = col * 0.125, (96 + (3 - row) * 8) / 128.0
    for l in f.loops:
        c = l.vert.co
        h = lambda k: (math.sin(c.x * 127.1 + c.y * 311.7 + c.z * 74.7 + k * 19.19) * 43758.5453) % 1
        l[uvl].uv = (u0 + (0.25 + 0.5 * h(0)) * 0.125, v0 + (0.25 + 0.5 * h(1)) * 0.0625)

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
            l[uvl].uv = (l.vert.co[ua] * DENS / TEX + off,
                         base + ((l.vert.co[va] - vmin) * vscale * DENS / TEX) * 0.94 + 0.0075)
    return fn

def commit(bm, name, uvfun, pos=(0, 0, 0), rot=(0, 0, 0), target=None):
    bm.normal_update()
    uvl = bm.loops.layers.uv.verify()
    for f in bm.faces: uvfun(f, uvl)
    if any(rot):
        bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Euler([math.radians(a) for a in rot]).to_matrix())
    bmesh.ops.translate(bm, verts=bm.verts, vec=Vector(pos))
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = False; p.material_index = 0
    ob = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(ob)
    ob.data.materials.append(MAT)
    (CUR if target is None else target).append(ob)
    return ob

def timber(name, size, pos, kind="hewn", rot=(0, 0, 0), jitter=0.01, bevel=0.012, target=None, flat_z=False):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts: v.co = Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2]))
    long_axis = max(range(3), key=lambda i: size[i])
    for v in bm.verts:
        for i in range(3):
            if i != long_axis and not (flat_z and i == 2): v.co[i] += rng.uniform(-jitter, jitter)
    if bevel > 0:
        bmesh.ops.bevel(bm, geom=bm.edges[:], offset=bevel, segments=1, affect="EDGES")
    return commit(bm, name, wood_uv(kind, long_axis, rng.randrange(1000)), pos, rot, target)

def add_box(bm, size, c, tile, tile_top=None, taper=1.0, jit=0.0, bevel=0.0):
    before = set(bm.faces)
    vs = bmesh.ops.create_cube(bm, size=1.0)["verts"]
    for v in vs:
        v.co = Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2]))
        if taper != 1.0 and v.co.z > 0: v.co.x *= taper; v.co.y *= taper
        v.co += Vector(c) + Vector((rng.uniform(-jit, jit), rng.uniform(-jit, jit), rng.uniform(-jit, jit)))
    if bevel:
        bmesh.ops.bevel(bm, geom=list({e for v in vs for e in v.link_edges}), offset=bevel, segments=1, affect="EDGES")
    bm.normal_update()
    new = [f for f in bm.faces if f not in before]
    for f in new:
        f.material_index = tile_top if (tile_top is not None and f.normal.z > 0.6) else tile

def add_cyl(bm, r, length, segs, c, tile, tile_end=None, along="x", jit=0.0, r2=None):
    before = set(bm.faces)
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=segs, radius1=r, radius2=r2 or r, depth=length)
    new = [f for f in bm.faces if f not in before]
    vs = {v for f in new for v in f.verts}
    m = Matrix.Rotation(math.radians(90), 3, "Y") if along == "x" else (
        Matrix.Rotation(math.radians(90), 3, "X") if along == "y" else Matrix.Identity(3))
    for v in vs:
        v.co = m @ v.co + Vector(c) + Vector((rng.uniform(-jit, jit), rng.uniform(-jit, jit), rng.uniform(-jit, jit)))
    for f in new:
        f.material_index = tile
    bm.normal_update()
    if tile_end is not None:
        for f in new:
            ax = max(range(3), key=lambda i: abs(f.normal[i]))
            if (along == "x" and ax == 0) or (along == "y" and ax == 1) or (along == "z" and ax == 2):
                f.material_index = tile_end

def lathe(bm, prof, sides, pair_tile, bottom_tile, top_tile, jit=0.0015, ang0=0.0):
    rings = []
    for (r, z) in prof:
        ring = []
        for j in range(sides):
            a = ang0 + 2 * math.pi * j / sides
            ring.append(bm.verts.new((r * math.cos(a) + rng.uniform(-jit, jit), r * math.sin(a) + rng.uniform(-jit, jit),
                                      z + rng.uniform(-jit, jit) * 0.4)))
        rings.append(ring)
    for i in range(len(prof) - 1):
        for j in range(sides):
            a, b = rings[i][j], rings[i][(j + 1) % sides]
            c, d = rings[i + 1][(j + 1) % sides], rings[i + 1][j]
            f = bm.faces.new((a, b, c, d)); f.material_index = pair_tile[i]
    f = bm.faces.new(list(reversed(rings[0]))); f.material_index = bottom_tile
    f = bm.faces.new(rings[-1]); f.material_index = top_tile

# ---------- contents ----------
FLASK_SIDES = 6
SHAPES = {"round": (1.0, 1.0), "tall": (0.82, 1.28), "squat": (1.22, 0.78)}

def make_flask(bm, s):
    rs, hs = SHAPES[s.get("shape", "round")]
    v = s["var"]
    seal, glass = T(0, v), T(1, v)
    prof = [(0.030 * rs, 0), (0.040 * rs, 0.030 * hs), (0.014, 0.075 * hs), (0.014, 0.098 * hs),
            (0.022, 0.098 * hs), (0.022, 0.122 * hs)]
    lathe(bm, prof, FLASK_SIDES, [glass, glass, glass, seal, seal], glass, seal, ang0=rng.uniform(0, 1))

def make_bread(bm, s):
    add_box(bm, (0.19, 0.085, 0.07), (0, 0, 0.035), CRUST, tile_top=CRUMB, taper=0.78, jit=0.004, bevel=0.012)
    bx = rng.uniform(-0.015, 0.025)
    add_box(bm, (0.04, 0.093, 0.074), (bx, 0, 0.037), LINEN, jit=0.002)

def make_cheese(bm, s):
    for k, (R, ang, H, z0, yaw, dx) in enumerate([(0.12, 38, 0.055, 0.0, 0, -0.07), (0.09, 34, 0.05, 0.055, 150, -0.045)]):
        a = math.radians(ang)
        pts = [(0, 0), (R * math.cos(a), -R * math.sin(a)), (R, 0), (R * math.cos(a), R * math.sin(a))]
        cy, sy = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
        def P(i, z):
            x, y = pts[i]; x += dx
            return bm.verts.new((x * cy - y * sy + rng.uniform(-.003, .003), x * sy + y * cy + rng.uniform(-.003, .003),
                                 z + rng.uniform(-.002, .002)))
        bot = [P(i, z0) for i in range(4)]; top = [P(i, z0 + H) for i in range(4)]
        f = bm.faces.new(list(reversed(bot))); f.material_index = CHEESE
        f = bm.faces.new(top); f.material_index = CHEESE
        for i in range(4):
            j = (i + 1) % 4
            f = bm.faces.new((bot[i], bot[j], top[j], top[i]))
            f.material_index = RIND if i in (1, 2) else CHEESE

def make_sausage(bm, s):
    for (dy, dz, ln) in [(-0.019, 0.016, 0.17), (0.019, 0.016, 0.16), (0.0, 0.047, 0.165)]:
        add_cyl(bm, 0.0165, ln, 6, (rng.uniform(-.006, .006), dy, dz), SAUSAGE, tile_end=MEATD, along="x", jit=0.002)
    add_box(bm, (0.014, 0.08, 0.07), (0.0, 0, 0.033), TWINE, jit=0.001)

def make_parcel(bm, s):
    add_box(bm, (0.12, 0.08, 0.05), (0, 0, 0.025), LEAF, taper=0.88, jit=0.004)
    add_box(bm, (0.014, 0.084, 0.054), (0.0, 0, 0.026), TWINE, jit=0.001)
    add_box(bm, (0.124, 0.014, 0.054), (0.0, 0, 0.026), TWINE, jit=0.001)

def make_bowl(bm, s):
    prof = [(0.032, 0), (0.062, 0.062), (0.054, 0.062), (0.047, 0.046)]
    lathe(bm, prof, 8, [CLAY, CLAYD, CLAYD], CLAYD, s.get("stew", STEW), ang0=rng.uniform(0, 1), jit=0.002)

MAKERS = {"flask": make_flask, "bread": make_bread, "cheese": make_cheese, "sausage": make_sausage,
          "parcel": make_parcel, "bowl": make_bowl}

ISCALE = {"flask": 1.3, "bread": 1.15, "cheese": 1.1, "sausage": 1.15, "parcel": 1.15, "bowl": 1.1}
BACK, FRONT = -0.125, -0.235
def F(x, var, shape="round", row=BACK): return dict(kind="flask", x=x, y=row, var=var, shape=shape)
SPEC_2M = [
    # shelf 0 (lower)
    [F(-0.79, HEALTH), F(-0.63, POISON), dict(kind="bread", x=-0.68, y=FRONT, yaw=6),
     dict(kind="bowl", x=-0.34, y=FRONT), F(-0.20, FIRE, "tall"), F(0.24, FROST, "squat"),
     dict(kind="cheese", x=0.40, y=-0.225, yaw=-6), F(0.66, STAMINA, "round", FRONT)],
    # shelf 1 (upper)
    [F(-0.80, STAMINA, "tall"), dict(kind="sausage", x=-0.60, y=-0.24, yaw=4), F(-0.50, FIRE),
     F(-0.33, POISON, "round"), dict(kind="parcel", x=-0.28, y=FRONT, yaw=-10), F(0.25, HEALTH, "tall"),
     F(0.42, FROST), dict(kind="bread", x=0.60, y=FRONT, yaw=-8), F(0.78, EITR, "squat")],
]
SPEC_1M = [
    [F(-0.27, HEALTH), F(-0.10, POISON), dict(kind="bread", x=-0.18, y=FRONT, yaw=5), F(0.10, FIRE, "tall"),
     F(0.26, FROST), F(0.0, STAMINA, "squat", FRONT), dict(kind="bowl", x=0.20, y=FRONT)],
]

# ---------- frame ----------
LEDGER_Y = -0.05
ITEM_Y_MIN, ITEM_Y_MAX = -0.312, -0.058

def build_frame(W, levels, pegx, bx):
    for s in range(levels):
        z0 = 0.45 * s
        timber("ledger", (W - 0.04, 0.05, 0.16), (0, -0.025, z0 + 0.075), jitter=0.004, bevel=0.01,
               rot=(0, 0, rng.uniform(-0.2, 0.2)))
        for (y0, y1) in ((-0.204, -0.052), (-0.352, -0.212)):
            timber("plank", (W, abs(y1 - y0), 0.07), (0, (y0 + y1) / 2, z0 + 0.035),
                   jitter=0.005, bevel=0.01, rot=(0, rng.uniform(-0.2, 0.2), rng.uniform(-0.3, 0.3)), flat_z=True)
        timber("lip", (W - 0.03, 0.035, 0.06), (0, -0.3325, z0 + 0.10), jitter=0.003, bevel=0.0,
               rot=(0, 0, rng.uniform(-0.3, 0.3)))
        for xb in bx:
            timber("plate", (0.09, 0.045, 0.28), (xb, -0.0225, z0 - 0.14), jitter=0.004, bevel=0.0)
            timber("arm", (0.09, 0.30, 0.065), (xb, -0.19, z0 - 0.0325), jitter=0.004, bevel=0.0)
            dy, dz = -0.24, 0.215
            L = math.hypot(dy, dz)
            timber("brace", (0.07, L, 0.06), (xb, -0.04 + dy / 2, z0 - 0.27 + dz / 2 + 0.0),
                   rot=(math.degrees(math.atan2(dz, dy)) + 180, 0, 0), jitter=0.003, bevel=0.008)
            for zz in (-0.2, -0.07):
                timber("bolt", (0.03, 0.02, 0.03), (xb + rng.uniform(-.008, .008), -0.045, z0 + zz), kind="iron",
                       jitter=0.0, bevel=0.0)
    # pegs and a hanging pouch under the lower shelf
    for i, px in enumerate(pegx):
        timber("peg", (0.03, 0.03, 0.105), (px, -0.30, -0.045), kind="iron", jitter=0.002, bevel=0.0,
               rot=(rng.uniform(-6, -2), 0, 0))
    px = pegx[len(pegx) // 2]
    bm = bmesh.new()
    add_box(bm, (0.045, 0.045, 0.022), (px, -0.30, -0.08), LEATHERD, jit=0.002)       # loop round the peg
    add_box(bm, (0.02, 0.02, 0.06), (px, -0.31, -0.115), LEATHERD, jit=0.002)
    add_box(bm, (0.115, 0.075, 0.13), (px, -0.315, -0.215), LEATHER, taper=1.0, jit=0.004, bevel=0.012)
    add_box(bm, (0.12, 0.08, 0.04), (px, -0.315, -0.155), LEATHERD, jit=0.003)         # flap
    commit(bm, "pouch", swatch_uv)

PIECES = {
    "2m": dict(W=2.0, levels=2, pegx=(-0.62, -0.46, -0.30), bx=(-0.93, 0.0, 0.93), spec=SPEC_2M),
    "1m": dict(W=1.0, levels=1, pegx=(-0.16, 0.0, 0.16), bx=(-0.38, 0.38), spec=SPEC_1M),
}

# ---------- scene helpers ----------
def tris(obs): return sum(len(p.vertices) - 2 for o in obs for p in o.data.polygons)

def join(obs, name):
    bpy.ops.object.select_all(action="DESELECT")
    for o in obs: o.select_set(True)
    bpy.context.view_layer.objects.active = obs[0]
    bpy.ops.object.join(); ob = bpy.context.active_object; ob.name = name
    return ob

def tri_list(ob):
    verts = [v.co.copy() for v in ob.data.vertices]; t = []
    for p in ob.data.polygons:
        idx = list(p.vertices)
        for k in range(1, len(idx) - 1): t.append((idx[0], idx[k], idx[k + 1]))
    return verts, t

def frame_bvh(parts):
    verts, tr = [], []
    for ob in parts:
        base = len(verts); vs, ts = tri_list(ob)
        verts += vs; tr += [(base + a, base + b, base + c) for a, b, c in ts]
    return BVHTree.FromPolygons(verts, tr)

def place_item(spec, z0, tree, name):
    bm = bmesh.new()
    MAKERS[spec["kind"]](bm, spec)
    sc_ = ISCALE[spec["kind"]]
    for v in bm.verts: v.co *= sc_
    yaw = spec.get("yaw", rng.uniform(-18, 18))
    bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.radians(yaw), 3, "Z"))
    x, y = spec["x"], spec["y"]
    gz = -1e9
    for v in bm.verts:
        if v.co.z < 0.012:
            h = tree.ray_cast(Vector((x + v.co.x, y + v.co.y, z0 + 0.33)), Vector((0, 0, -1)), 1.0)
            if h[0] is not None: gz = max(gz, h[0].z)
    ob = commit(bm, name, swatch_uv, pos=(x, y, gz - 0.002), target=ITEMS)
    ob["shelf_z0"] = z0
    return ob

RAYD = Vector((0.31, 0.52, 0.79)).normalized()
def inside_depth(tree, p):
    """>0 if p lies inside this closed part (ray parity), value = distance to its nearest surface."""
    n, o = 0, p.copy()
    while n < 30:
        h = tree.ray_cast(o, RAYD)
        if h[0] is None: break
        n += 1; o = h[0] + RAYD * 1e-5
    if n % 2 == 0: return 0.0
    return tree.find_nearest(p)[3]

def clip_check(items, trees, W):
    bad = []
    for ob in items:
        z0 = ob["shelf_z0"]; why = None
        for v in ob.data.vertices:
            p = v.co
            if abs(p.x) > W / 2 - 0.03: why = "x"
            elif not (ITEM_Y_MIN <= p.y <= ITEM_Y_MAX): why = "y"
            elif p.z > z0 + 0.45 - 0.04: why = "z-top"
            else:
                for t in trees:
                    d = inside_depth(t, p)
                    if d > 0.006:
                        why = "inside frame"; print("   inside", ob.name, tuple(round(c, 3) for c in p), "depth", round(d, 4)); break
            if why: break
        if why: bad.append((ob.name, why))
    ov = 0
    trees = [BVHTree.FromPolygons(*(lambda vt: (vt[0], vt[1]))(tri_list(o))) for o in items]
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            if abs(items[i]["shelf_z0"] - items[j]["shelf_z0"]) > 0.01: continue
            if trees[i].overlap(trees[j]):
                ov += 1; print("  OVERLAP", items[i].name, items[j].name)
    return bad, ov

ITEMS = []
STATS = {}
def build(size, fill, ox, export=False):
    cfg = PIECES[size]; W = cfg["W"]
    rng.seed(11); CUR.clear(); ITEMS.clear()
    build_frame(W, cfg["levels"], cfg["pegx"], cfg["bx"])
    parts = list(CUR); tree = frame_bvh(parts)
    rng.seed(99)
    items = []
    for s, lst in enumerate(cfg["spec"]):
        for sp in sorted(lst, key=lambda d: d["x"]):
            items.append((s, sp))
    for i, (s, sp) in enumerate(items):
        place_item(sp, 0.45 * s, tree, f"item_{i:02d}_{sp['kind']}")
    obs = list(ITEMS)
    if export and "--selftest" in argv:      # sanity check of the clip detector: sink item 0 into the plank
        for v in obs[0].data.vertices: v.co.z -= 0.03
    if export:
        bad, ov = clip_check(obs, [BVHTree.FromPolygons(*tri_list(o)) for o in parts], W)
        print(f"CLIPPING {len(bad)} of {len(obs)}", bad, "ITEM OVERLAPS", ov)
        STATS[size] = {"frame_tris": tris(parts), "item_count": len(obs), "items_tris": tris(obs),
                       "clipping": len(bad), "item_overlaps": ov,
                       "items": [{"name": o.name, "tris": tris([o]), "shelf": int(round(o["shelf_z0"] / 0.45)),
                                  "x": round(sp["x"], 3), "kind": sp["kind"], "variant_col": sp.get("var"),
                                  "shape": sp.get("shape")} for o, (s, sp) in zip(obs, items)]}
    frame = join(parts, f"EmergencyShelf{size}")
    if export:
        for obl, fn in (([frame], f"EmergencyShelf{size}.obj"), (obs, f"EmergencyShelf{size}Items.obj")):
            bpy.ops.object.select_all(action="DESELECT")
            for o in obl: o.select_set(True)
            bpy.ops.wm.obj_export(filepath=os.path.join(OUTA, fn), export_selected_objects=True,
                                  export_materials=False, export_triangulated_mesh=True,
                                  forward_axis="NEGATIVE_Z", up_axis="Y")
        print("SHELF", size, STATS[size]["frame_tris"], STATS[size]["items_tris"])
    shown = obs[:round(fill * len(obs))]
    for o in obs[len(shown):]: bpy.data.objects.remove(o, do_unlink=True)
    zl = 0.95
    for o in [frame] + shown: o.location = (ox, 0, zl)
    # wall panel (2 x 2 m planks) and a 1.8 m player-height post
    wall = []
    for k in range(8):
        h = 2.0 + rng.uniform(-0.015, 0.015)
        timber("wall", (0.248, 0.07, h), (ox - 0.875 + k * 0.25, 0.04, h / 2), jitter=0.004, bevel=0.01,
               rot=(0, rng.uniform(-0.3, 0.3), rng.uniform(-0.4, 0.4)), target=wall)
    for o in wall: o.data.materials[0] = WALLMAT
    post = bpy.data.objects.new("post", bpy.data.meshes.new("post"))
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts: v.co = Vector((v.co.x * 0.1, v.co.y * 0.1, v.co.z * 1.8 + 0.9))
    bm.to_mesh(post.data); bm.free()
    for p in post.data.polygons: p.use_smooth = False
    post.data.materials.append(POSTMAT); post.location = (ox + 1.3, -0.3, 0)
    bpy.context.scene.collection.objects.link(post)

# ---------- scene ----------
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
atlas = build_atlas()
MAT = bpy.data.materials.new("emergencyshelf"); MAT.use_nodes = True
nt = MAT.node_tree; bsdf = nt.nodes["Principled BSDF"]
ti = nt.nodes.new("ShaderNodeTexImage"); ti.image = atlas; ti.interpolation = "Closest"
nt.links.new(ti.outputs["Color"], bsdf.inputs["Base Color"])
bsdf.inputs["Roughness"].default_value = 0.8
POSTMAT = bpy.data.materials.new("post"); POSTMAT.use_nodes = True
POSTMAT.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.55, 0.58, 0.62, 1)

WALLMAT = bpy.data.materials.new("wall"); WALLMAT.use_nodes = True
wn = WALLMAT.node_tree; wt = wn.nodes.new("ShaderNodeTexImage"); wt.image = atlas; wt.interpolation = "Closest"
wm = wn.nodes.new("ShaderNodeMixRGB"); wm.blend_type = "MULTIPLY"; wm.inputs[0].default_value = 1.0
wm.inputs[2].default_value = (0.62, 0.6, 0.6, 1)
wn.links.new(wt.outputs["Color"], wm.inputs[1]); wn.links.new(wm.outputs["Color"], wn.nodes["Principled BSDF"].inputs["Base Color"])
wn.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.85
DX = 3.2
build("2m", 1.0, DX, export=True)
build("2m", 0.5, 0.0)
build("2m", 0.1, -DX)
build("1m", 1.0, 20.0, export=True)
build("1m", 0.5, 20.0 + DX)
json.dump({"atlas": "emergencyshelf_atlas.png", "pieces": STATS,
           "swatch_layout": "u += col*0.125 picks a variant column; rows (top to bottom): seal, glass, food, misc"},
          open(os.path.join(OUTA, "emergencyshelf.json"), "w"), indent=1)

world = bpy.data.worlds.new("w"); sc.world = world; world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.42, 0.45, 0.5, 1)
world.node_tree.nodes["Background"].inputs[1].default_value = 0.9
sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN")); sun.data.energy = 3.2
sun.rotation_euler = (math.radians(50), 0, math.radians(35)); sc.collection.objects.link(sun)
bpy.ops.mesh.primitive_plane_add(size=80, location=(10, 0, 0))
gm = bpy.data.materials.new("ground"); gm.use_nodes = True
gm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.16, 0.14, 0.11, 1)
bpy.context.active_object.data.materials.append(gm)
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam); sc.camera = cam
sc.render.engine = "BLENDER_EEVEE_NEXT"
sc.render.resolution_x, sc.render.resolution_y = 1600, 900
sc.view_settings.view_transform = "Standard"
VIEWS = {"fills": (-2, 8, 13.4, (0, 0, 1.15), 50, (2000, 800)), "close": (-24, 15, 4.3, (DX, 0, 1.3), 50, (1600, 900)),
         "small": (-20, 13, 3.6, (20, 0, 1.05), 50, (1600, 900))}
only = argv[argv.index("--views") + 1].split(",") if "--views" in argv else list(VIEWS)
for vn in only:
    yaw, pitch, dist, tgt, lens, res = VIEWS[vn]
    sc.render.resolution_x, sc.render.resolution_y = res
    cam.data.lens = lens
    t = Vector(tgt)
    d = Vector((math.cos(math.radians(pitch)) * math.sin(math.radians(yaw)),
                -math.cos(math.radians(pitch)) * math.cos(math.radians(yaw)), math.sin(math.radians(pitch))))
    cam.location = t + d * dist; cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    sc.render.filepath = os.path.join(OUT, f"{TAG}-{vn}.png")
    bpy.ops.render.render(write_still=True)
print("DONE")
