"""Ore Bin, our own mesh and our own texture (no vanilla geometry or texture in it).
Run: blender -b -P orebin.py -- [--out DIR] [--tag NAME] [--no-ref] [--quick]
Timber-framed bin lined with rough stone blocks, iron rim, low sloped front board, open top (2.0 x 1.4 x 1.0 m).
Contents: a rising heap of low-poly ore chunks, one object per chunk, named heap_<step>_<n> (alphabetical = fill order).

Atlas 128x256, point-filtered, strips tile along u (v rows count from the bottom):
  rows 224-255 hewn timber side grain    rows 192-223 end grain (4 ring tiles)
  rows 160-191 rough stone               rows 128-159 iron
  rows 112-127 ore swatches 0-7 (16x16)  rows  96-111 ore swatches 8-15 (16x16)
Ore swatch k: u0 = (k % 8) * 0.125, v0 = (112 - (k // 8) * 16) / 256, size 0.125 x 0.0625.
Every chunk's UVs lie inside ONE swatch, so a mod can recolour a chunk by adding (dk%8)*0.125 to u and -(dk//8)*0.0625 to v.
"""
import bpy, bmesh, sys, os, math, json, random
import numpy as np
from mathutils import Vector, Matrix, Euler
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
OUTA = os.path.normpath(os.path.join(HERE, "..", "assets", "orebin"))
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = argv[argv.index("--out") + 1] if "--out" in argv else OUTA
TAG = argv[argv.index("--tag") + 1] if "--tag" in argv else "orebin"
QUICK = "--quick" in argv
RIP = "C:/Users/joost/ValheimRip/chests/piece_chest_wood"
os.makedirs(OUTA, exist_ok=True); os.makedirs(OUT, exist_ok=True)
rng = random.Random(11)

TW, TH = 128, 256
DENS = 48.0                      # px per metre, vanilla wood is 47-57
STRIP = {"hewn": 224 / 256, "end": 192 / 256, "stone": 160 / 256, "iron": 128 / 256}

# ---------- texture ----------
def srgb(c): return np.array(c, dtype=np.float32)
WOOD, WOOD_D = srgb((0.38, 0.29, 0.18)), srgb((0.21, 0.16, 0.10))
END, END_D = srgb((0.55, 0.45, 0.31)), srgb((0.35, 0.27, 0.17))
IRON, IRON_D = srgb((0.22, 0.21, 0.20)), srgb((0.09, 0.09, 0.09))
STONE, STONE_D, LICHEN = srgb((0.40, 0.38, 0.34)), srgb((0.19, 0.18, 0.17)), srgb((0.30, 0.33, 0.21))

# ore swatches: (name, base colour, fleck colour or None, fleck density)
ORES = [
    ("copper",     (0.58, 0.36, 0.20), (0.30, 0.46, 0.36), 0.12),   # orange-brown, green tinge
    ("tin",        (0.52, 0.52, 0.49), None, 0),                    # pale grey
    ("iron",       (0.31, 0.17, 0.13), (0.40, 0.34, 0.30), 0.06),   # rust brown
    ("silver",     (0.52, 0.57, 0.65), (0.80, 0.84, 0.90), 0.05),   # bluish white
    ("blackmetal", (0.13, 0.13, 0.15), (0.25, 0.30, 0.45), 0.07),   # dark, faint blue sheen
    ("flametal",   (0.17, 0.11, 0.10), (0.95, 0.45, 0.12), 0.09),   # dark, ember specks
    ("coal",       (0.15, 0.15, 0.15), None, 0),
    ("greystone",  (0.42, 0.41, 0.39), None, 0),
    ("gold",       (0.66, 0.52, 0.20), (0.90, 0.80, 0.40), 0.06),
    ("green",      (0.30, 0.48, 0.34), (0.55, 0.75, 0.55), 0.05),
    ("blue",       (0.30, 0.40, 0.58), (0.55, 0.65, 0.85), 0.05),
    ("red",        (0.58, 0.25, 0.20), None, 0),
    ("violet",     (0.44, 0.32, 0.50), None, 0),
    ("sand",       (0.64, 0.57, 0.40), None, 0),
    ("white",      (0.70, 0.70, 0.67), None, 0),
    ("teal",       (0.28, 0.52, 0.52), None, 0),
]
TILE_U, TILE_V = 16 / TW, 16 / TH

def tile_origin(k): return (k % 8) * TILE_U, (112 - (k // 8) * 16) / TH

def build_atlas():
    nr = np.random.default_rng(5)
    img = np.zeros((TH, TW, 3), np.float32)
    blocky = lambda h, w, s: np.kron(nr.random((h // s, w // s)), np.ones((s, s), np.float32))
    x = np.arange(TW)[None, :].repeat(32, 0).astype(np.float32)
    y = np.arange(32)[:, None].repeat(TW, 1).astype(np.float32)
    tile = lambda k: 2 * math.pi * k / TW
    # hewn side grain
    g = np.sin(y * 1.25 + 1.6 * np.sin(x * tile(2) + y * 0.15) + 0.7 * np.sin(x * tile(5)))
    t = np.clip((g - 0.55) * 2.5, 0, 1) * 0.65 + nr.random((32, TW)) * 0.18
    t += np.clip(1 - np.minimum(y, 31 - y) / 3.0, 0, 1) * 0.35
    img[224:256] = WOOD * (1 - t[..., None]) + WOOD_D * t[..., None]
    # end grain, four ring tiles
    for k in range(4):
        cx, cy = 15.5 + nr.uniform(-2, 2), 15.5 + nr.uniform(-2, 2)
        xx, yy = np.meshgrid(np.arange(32), np.arange(32))
        d = np.hypot(xx - cx, yy - cy) + 0.6 * np.sin(np.arctan2(yy - cy, xx - cx) * 3 + k)
        t = (np.sin(d * 1.5) * 0.5 + 0.5) * 0.45 + nr.random((32, 32)) * 0.15
        t = np.where(d > 13.5, 0.95, t)
        img[192:224, 32 * k:32 * k + 32] = END * (1 - t[..., None]) + END_D * t[..., None]
    # rough stone: blocky mottling, a little lichen, dark seams at the strip edges
    t = blocky(32, TW, 8) * 0.40 + blocky(32, TW, 4) * 0.30 + blocky(32, TW, 2) * 0.15 + nr.random((32, TW)) * 0.15
    t += np.clip(1 - np.minimum(y, 31 - y) / 2.5, 0, 1) * 0.30
    t = np.clip(t, 0, 1)
    st = STONE * (1 - t[..., None]) + STONE_D * t[..., None]
    lm = (blocky(32, TW, 4) > 0.86)[..., None]
    img[160:192] = np.where(lm, st * 0.6 + LICHEN * 0.4, st)
    # iron
    t = nr.random((32, TW)) * 0.4 + np.clip(1 - np.minimum(y, 31 - y) / 4.0, 0, 1) * 0.5
    img[128:160] = IRON * (1 - t[..., None]) + IRON_D * t[..., None]
    # ore swatches
    for k, (nm, base, fleck, dens) in enumerate(ORES):
        u0, v0 = int(round(tile_origin(k)[0] * TW)), int(round(tile_origin(k)[1] * TH))
        c = srgb(base)
        t = blocky(16, 16, 4) * 0.42 + blocky(16, 16, 2) * 0.30 + nr.random((16, 16)) * 0.28
        dark, bright = c * 0.52, np.clip(c * 1.15 + 0.02, 0, 1)
        sw = dark * (1 - t[..., None]) + bright * t[..., None]
        if fleck is not None:
            m = (nr.random((16, 16)) < dens)[..., None]
            sw = np.where(m, srgb(fleck), sw)
        img[v0:v0 + 16, u0:u0 + 16] = sw
    im = bpy.data.images.new("orebin_atlas", TW, TH, alpha=False)
    px = np.concatenate([np.clip(img, 0, 1), np.ones((TH, TW, 1), np.float32)], 2)
    im.pixels.foreach_set(px.ravel())
    im.filepath_raw = os.path.join(OUTA, "orebin_atlas.png"); im.file_format = "PNG"; im.save()
    return im

# ---------- geometry ----------
PARTS, CH = [], []     # frame parts, content chunks (fill order)

def uv_face(f, kind, long_axis, seed):
    n = f.normal
    ax = max(range(3), key=lambda i: abs(n[i]))
    tang = [i for i in range(3) if i != ax]
    if kind == "hewn" and ax == long_axis:          # cut end of a timber
        k = seed % 4
        cs = [l.vert.co for l in f.loops]
        c = sum(cs, Vector()) / len(cs)
        ext = max(max(abs(v[tang[0]] - c[tang[0]]), abs(v[tang[1]] - c[tang[1]])) for v in cs) or 1
        for l in f.loops:
            a = (l.vert.co[tang[0]] - c[tang[0]]) / ext; b = (l.vert.co[tang[1]] - c[tang[1]]) / ext
            l[UV].uv = ((k + 0.5 + a * 0.45) / 4, STRIP["end"] + (0.5 + b * 0.45) * 32 / TH)
        return
    cs = [l.vert.co for l in f.loops]
    spans = [max(v[i] for v in cs) - min(v[i] for v in cs) for i in tang]
    if kind == "hewn" and long_axis in tang: ua = long_axis
    else: ua = tang[0] if spans[0] >= spans[1] else tang[1]
    va = tang[1] if ua == tang[0] else tang[0]
    off = (seed * 0.37) % 1
    vmin = min(v[va] for v in cs); span = max(max(v[va] for v in cs) - vmin, 1e-4)
    vscale = min(1.0, (30 / DENS) / span)
    used = span * vscale * DENS
    shift = ((seed * 13) % 100) / 100 * max(0.0, 30 - used) if kind in ("stone", "hewn") else 0.0
    base = STRIP[kind]
    for l in f.loops:
        u = l.vert.co[ua] * DENS / TW + off
        v = base + (1 + shift + (l.vert.co[va] - vmin) * vscale * DENS) / TH
        l[UV].uv = (u, v)

def box(name, size, pos, kind="hewn", rot=(0, 0, 0), jitter=0.02, bevel=0.02, rough=False):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2]))
    long_axis = max(range(3), key=lambda i: size[i])
    for v in bm.verts:
        for i in range(3):
            if rough or i != long_axis: v.co[i] += rng.uniform(-jitter, jitter)
    if bevel > 0:
        bmesh.ops.bevel(bm, geom=bm.edges[:], offset=bevel, segments=1, affect="EDGES")
    bm.normal_update()
    global UV
    UV = bm.loops.layers.uv.verify()
    seed = rng.randrange(1000)
    for f in bm.faces: uv_face(f, kind, long_axis, seed + f.index % 2)
    bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Euler([math.radians(a) for a in rot]).to_matrix())
    bmesh.ops.translate(bm, verts=bm.verts, vec=Vector(pos))
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = False
    ob = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(ob)
    ob.data.materials.append(MAT); PARTS.append(ob)

FLOOR = 0.16
HX, HY, PS = 1.0, 0.70, 0.16           # outer half width, half depth, post section
PX, PY = HX - PS / 2, HY - PS / 2      # post centres

def build_frame():
    # posts
    for sx in (-1, 1):
        for sy in (-1, 1):
            h = 1.0 + rng.uniform(-0.02, 0.02)
            box("post", (PS, PS, h), (sx * PX, sy * PY, h / 2), rot=(rng.uniform(-0.8, 0.8), rng.uniform(-0.8, 0.8), 0))
    # ground sills: long ones front and back, short ones under the side walls
    for sy in (-1, 1):
        box("sill", (2.0 + 0.1, 0.2, 0.16), (0, sy * 0.60, 0.08), rot=(0, 0, rng.uniform(-0.5, 0.5)))
    for sx in (-1, 1):
        box("sill", (0.2, 1.3, 0.14), (sx * 0.90, 0, 0.07), rot=(0, 0, rng.uniform(-0.5, 0.5)))
    # floor planks
    for i in range(7):
        box("plank", (0.25, 1.28, 0.05), (-0.84 + i * 0.28, 0, FLOOR - 0.025), jitter=0.004, bevel=0)
    # stone lining: three courses, back wall and both side walls, rough blocks (no bevel, all-axis wobble)
    CH_H, COURSES = 0.25, 3
    for c in range(COURSES):
        zc = FLOOR + CH_H * (c + 0.5)
        # back wall
        x = -0.84
        while x < 0.84 - 0.05:
            w = min(rng.uniform(0.32, 0.5), 0.84 - x)
            if 0.84 - (x + w) < 0.2: w = 0.84 - x
            box("stone", (w - 0.015, 0.15, CH_H - 0.015), (x + w / 2, 0.62, zc + rng.uniform(-0.01, 0.01)),
                kind="stone", jitter=0.03, bevel=0, rough=True)
            x += w
        # side walls (between the front and back posts)
        for sx in (-1, 1):
            y = -0.54 + (0.0 if c % 2 == 0 else 0.0)
            while y < 0.54 - 0.05:
                w = min(rng.uniform(0.3, 0.46), 0.54 - y)
                if 0.54 - (y + w) < 0.2: w = 0.54 - y
                box("stone", (0.15, w - 0.015, CH_H - 0.015), (sx * 0.915, y + w / 2, zc + rng.uniform(-0.01, 0.01)),
                    kind="stone", jitter=0.03, bevel=0, rough=True)
                y += w
    # cap timbers over the stone (back, sides) and a lintel across the front
    box("cap", (1.7, 0.2, 0.1), (0, 0.62, 0.955), rot=(0, 0, rng.uniform(-0.4, 0.4)))
    for sx in (-1, 1):
        box("cap", (0.2, 1.1, 0.1), (sx * 0.92, 0, 0.955), rot=(0, 0, rng.uniform(-0.4, 0.4)))
    box("lintel", (1.7, 0.17, 0.1), (0, -0.62, 0.955), rot=(0, 0, rng.uniform(-0.4, 0.4)))
    # low sloped front board: two planks, leaning outward, standing on the front sill
    th = 13.0
    for z in (0.26, 0.45):
        y = -0.60 - (z - FLOOR) * math.tan(math.radians(th))
        box("frontboard", (1.68, 0.06, 0.2), (0, y, z), rot=(th, 0, rng.uniform(-0.4, 0.4)), bevel=0.014)
    for sx in (-0.52, 0.52):       # iron straps over the planks
        z = 0.355; y = -0.60 - (z - FLOOR) * math.tan(math.radians(th)) - 0.04
        box("strap", (0.09, 0.02, 0.42), (sx, y, z), kind="iron", rot=(th, 0, 0), jitter=0.003, bevel=0.004)
    # iron rim on top, round the whole opening, rivets along it
    box("rim", (2.0, 0.17, 0.045), (0, 0.62, 1.022), kind="iron", jitter=0.003, bevel=0.007)
    box("rim", (2.0, 0.17, 0.045), (0, -0.62, 1.022), kind="iron", jitter=0.003, bevel=0.007)
    for sx in (-1, 1):
        box("rim", (0.17, 1.4, 0.045), (sx * 0.92, 0, 1.022), kind="iron", jitter=0.003, bevel=0.007)
    for sy in (-1, 1):
        for x in (-0.6, -0.2, 0.2, 0.6):
            box("rivet", (0.04, 0.04, 0.035), (x, sy * 0.62, 1.06), kind="iron", jitter=0, bevel=0)
    for sx in (-1, 1):
        for y in (-0.35, 0.0, 0.35):
            box("rivet", (0.04, 0.04, 0.035), (sx * 0.92, y, 1.06), kind="iron", jitter=0, bevel=0)
    # iron band round each post, mid height
    for sx in (-1, 1):
        for sy in (-1, 1):
            box("band", (PS + 0.04, PS + 0.04, 0.08), (sx * PX, sy * PY, 0.58), kind="iron", jitter=0.003, bevel=0.006)

# ---------- contents ----------
# demo assortment: (label, shape, swatch, weight). In the game the item decides shape (class) and swatch (colour).
ITEMS = [("copper ore", "rock", 0, 0.22), ("tin ore", "rock", 1, 0.17), ("iron scrap", "shard", 2, 0.17),
         ("silver ore", "rock", 3, 0.10), ("black metal scrap", "shard", 4, 0.12), ("flametal ore", "rock", 5, 0.07),
         ("coal", "lump", 6, 0.08), ("modded gem", "crystal", 9, 0.05)]
LIMX, LIMY0, LIMY1 = 0.79, -0.57, 0.52      # content bounds (inside posts/stone, behind the front board)

def tri_list(me):
    V = [v.co.copy() for v in me.vertices]; T = []
    for p in me.polygons:
        vs = list(p.vertices)
        for i in range(1, len(vs) - 1): T.append((vs[0], vs[i], vs[i + 1]))
    return V, T

def clipped(ob, frame_bvh):
    me = ob.data
    for v in me.vertices:
        c = v.co
        if abs(c.x) > LIMX or c.y < LIMY0 or c.y > LIMY1 or c.z < FLOOR - 1e-4: return True
    V, T = tri_list(me)
    return bool(frame_bvh.overlap(BVHTree.FromPolygons(V, T, all_triangles=True)))

def make_chunk(name, shape, sw, pos, zbottom, frame_bvh):
    bm = bmesh.new()
    if shape in ("rock", "lump"):
        bmesh.ops.create_icosphere(bm, subdivisions=1, radius=0.5)
        sx, sy, sz = ((rng.uniform(0.31, 0.38), rng.uniform(0.28, 0.34), rng.uniform(0.22, 0.27)) if shape == "rock"
                      else (rng.uniform(0.17, 0.21), rng.uniform(0.16, 0.2), rng.uniform(0.14, 0.18)))
        j = 0.17 if shape == "rock" else 0.08
        for v in bm.verts:
            v.co = Vector((v.co.x * sx, v.co.y * sy, v.co.z * sz)) + Vector((rng.uniform(-j, j) * sx, rng.uniform(-j, j) * sy, rng.uniform(-j, j) * sz))
            if v.co.z < -0.3 * sz: v.co.z = -0.3 * sz
        tilt = 14
    elif shape == "shard":
        bmesh.ops.create_cube(bm, size=1.0)
        sx, sy, sz = rng.uniform(0.32, 0.38), rng.uniform(0.22, 0.27), rng.uniform(0.13, 0.17)
        for v in bm.verts:
            top = v.co.z > 0
            v.co = Vector((v.co.x * sx, v.co.y * sy, v.co.z * sz))
            if top: v.co.x += rng.uniform(-0.10, 0.10); v.co.y *= 0.62
            for i in range(3): v.co[i] += rng.uniform(-0.055, 0.055)
        tilt = 22
    else:   # crystal: elongated octahedron
        w, h = rng.uniform(0.15, 0.19), rng.uniform(0.30, 0.36)
        P = [bm.verts.new(p) for p in ((w / 2, 0, 0), (0, w / 2, 0), (-w / 2, 0, 0), (0, -w / 2, 0), (0, 0, h / 2), (0, 0, -h / 2))]
        for i in range(4):
            bm.faces.new((P[i], P[(i + 1) % 4], P[4])); bm.faces.new((P[(i + 1) % 4], P[i], P[5]))
        for v in bm.verts:
            for i in range(3): v.co[i] += rng.uniform(-0.025, 0.025)
        tilt = 38
    bm.normal_update()
    cs = [v.co for v in bm.verts]
    ext = [max(abs(c[i]) for c in cs) or 1 for i in range(3)]
    global UV
    UV = bm.loops.layers.uv.verify()
    u0, v0 = tile_origin(sw)
    for f in bm.faces:
        ax = max(range(3), key=lambda i: abs(f.normal[i]))
        tang = [i for i in range(3) if i != ax]
        jx, jy = rng.uniform(-0.06, 0.06), rng.uniform(-0.06, 0.06)
        for l in f.loops:
            a = l.vert.co[tang[0]] / ext[tang[0]]; b = l.vert.co[tang[1]] / ext[tang[1]]
            l[UV].uv = (u0 + (0.5 + jx + a * 0.34) * TILE_U, v0 + (0.5 + jy + b * 0.34) * TILE_V)
    bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Euler((math.radians(rng.uniform(-tilt, tilt)),
                     math.radians(rng.uniform(-tilt, tilt)), rng.uniform(0, math.tau))).to_matrix())
    minz = min(v.co.z for v in bm.verts)
    bmesh.ops.translate(bm, verts=bm.verts, vec=Vector((pos[0], pos[1], zbottom - minz)))
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = False
    ob = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(ob)
    ob.data.materials.append(MAT)
    # pull towards the middle until nothing touches the frame (never up, so the heap shape stays)
    cx, cy = 0.0, -0.03
    for _ in range(24):
        if not clipped(ob, frame_bvh): break
        d = Vector((cx - ob.data.vertices[0].co.x, cy - ob.data.vertices[0].co.y, 0))
        if d.length < 1e-4: break
        ob.data.transform(Matrix.Translation(d.normalized() * 0.02))
    return ob

def build_heap(frame_bvh):
    """A mound that grows: candidate chunks on a staggered lattice, each tagged with the smallest fill level at which the
    growing dome (wider and higher with f) contains it. Sorted by that level = fill order, so every prefix is a whole heap."""
    T, SX, SY, CY = 0.14, 0.27, 0.245, -0.02
    cand = []
    for l in range(6):
        for j in range(-2, 3):
            for i in range(-3, 4):
                x = i * SX + (0.125 if (l + j) % 2 else 0.0) + rng.uniform(-0.025, 0.025)
                y = CY + j * SY + rng.uniform(-0.025, 0.025)
                if abs(x) > 0.69 or y < -0.50 or y > 0.46: continue
                rho = (abs(x / 0.68) ** 3 + abs((y - CY) / 0.46) ** 3) ** (1 / 3)
                fmin = None
                for fi in range(0, 81):
                    f = fi / 80
                    R, Hm = 0.55 + 0.75 * f, 0.10 + 0.66 * f
                    if rho < R and l * T <= Hm * (1 - (rho / R) ** 2) ** 0.9:
                        fmin = f; break
                if fmin is not None: cand.append((round(fmin, 3), l, math.hypot(x, (y - CY) * 1.4), x, y))
    cand.sort()
    placed = []
    for n, (f, l, _, x, y) in enumerate(cand):
        near = [p for p in placed if math.hypot(p[0] - x, p[1] - y) < 0.45]
        if near and rng.random() < 0.35: item = min(near, key=lambda p: math.hypot(p[0] - x, p[1] - y))[2]
        else:
            r, acc = rng.random() * sum(i[3] for i in ITEMS), 0
            for item in ITEMS:
                acc += item[3]
                if r <= acc: break
        step = min(7, int(f * 8))
        zb = FLOOR + 0.004 + l * T + rng.uniform(0, 0.025)
        ob = make_chunk(f"heap_{step:02d}_{n:03d}", item[1], item[2], (x, y), zb, frame_bvh)
        ob["item"], ob["step"] = item[0], step
        placed.append((x, y, item))
        CH.append(ob)

# ---------- scene ----------
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
atlas = build_atlas()
MAT = bpy.data.materials.new("orebin"); MAT.use_nodes = True
nt = MAT.node_tree; bsdf = nt.nodes["Principled BSDF"]
ti = nt.nodes.new("ShaderNodeTexImage"); ti.image = atlas; ti.interpolation = "Closest"
nt.links.new(ti.outputs["Color"], bsdf.inputs["Base Color"])
bsdf.inputs["Roughness"].default_value = 0.8
FILLS = (0.1, 0.5, 1.0)
SPACE = 2.9
def tris(obs): return sum(len(p.vertices) - 2 for o in obs for p in o.data.polygons)

def join(obs, name):
    bpy.ops.object.select_all(action="DESELECT")
    for o in obs: o.select_set(True)
    bpy.context.view_layer.objects.active = obs[0]
    bpy.ops.object.join(); ob = bpy.context.active_object; ob.name = name
    return ob

bins = []
for k, fill in enumerate(reversed(FILLS)):
    rng.seed(11); PARTS.clear(); CH.clear()
    build_frame()
    frame_tris = tris(PARTS)
    frame = join(list(PARTS), f"orebin_frame_{int(fill * 100)}")
    V, T = tri_list(frame.data)
    fbvh = BVHTree.FromPolygons(V, T, all_triangles=True)
    build_heap(fbvh)
    if k == 0:
        clip = [o.name for o in CH if clipped(o, fbvh)]
        print("CLIPPING", len(clip), "of", len(CH), clip)
        stats = {"frame_tris": tris([frame]), "chunk_count": len(CH), "contents_tris": tris(CH),
                 "steps": 7, "atlas": "orebin_atlas.png 128x256",
                 "swatches": {i: {"name": o[0], "u0": tile_origin(i)[0], "v0": tile_origin(i)[1]} for i, o in enumerate(ORES)},
                 "chunks": [{"name": o.name, "step": o["step"], "demo_item": o["item"], "tris": len(o.data.polygons) if False else tris([o])} for o in CH],
                 "clip_check": {"clipping": len(clip), "of": len(CH)},
                 "mapping": "Chunk objects heap_<step>_<n>, alphabetical = fill order; show the first n. Shape by item class: "
                            "rock = ore, shard = scrap/plates, lump = coal/charcoal, crystal = gems. Swatch by item colour: "
                            "average RGB of the inventory icon (alpha-weighted) -> nearest of the 16 swatch base colours (ORES), "
                            "or a fixed table for vanilla items. Recolour a chunk by shifting its UVs: u += (k%8)*0.125, "
                            "v -= (k//8)*0.0625, relative to the exported demo swatch. Slots are handed out in fill order "
                            "to the stored items in proportion to their stack counts, interleaved so the heap reads as a mix."}
        bpy.ops.object.select_all(action="DESELECT"); frame.select_set(True)
        frame.name = "OreBin"
        bpy.ops.wm.obj_export(filepath=os.path.join(OUTA, "OreBin.obj"), export_selected_objects=True, export_materials=False,
                              export_triangulated_mesh=True, forward_axis="NEGATIVE_Z", up_axis="Y")
        bpy.ops.object.select_all(action="DESELECT")
        for o in CH: o.select_set(True)
        bpy.ops.wm.obj_export(filepath=os.path.join(OUTA, "OreBinContents.obj"), export_selected_objects=True,
                              export_materials=False, export_triangulated_mesh=True, forward_axis="NEGATIVE_Z", up_axis="Y")
        json.dump(stats, open(os.path.join(OUTA, "orebin.json"), "w"), indent=1)
        print("OREBIN frame", stats["frame_tris"], "contents", stats["contents_tris"], "chunks", len(CH))
    shown = CH[:round(fill * len(CH))]
    for o in CH[len(shown):]: bpy.data.objects.remove(o, do_unlink=True)
    cont = join(shown, f"contents_{int(fill * 100)}")
    for ob in (frame, cont): ob.location.x = (len(FILLS) - 1 - k) * SPACE - SPACE
    bins.append((frame, cont))

# vanilla wood chest beside it, for scale and palette (reference only, never exported)
if "--no-ref" not in argv:
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
        q = node["rot"]; from mathutils import Quaternion
        M = Matrix.Translation(Vector(node["pos"])) @ Quaternion((q[3], q[0], q[1], q[2])).to_matrix().to_4x4() \
            @ Matrix.Diagonal((*node["scale"], 1))
        verts = [M @ v for v in V]
        verts = [Vector((-v.x - 5.4, -v.z, v.y)) for v in verts]
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
sc.render.resolution_x, sc.render.resolution_y = (1000, 562) if QUICK else (1600, 900)
sc.view_settings.view_transform = "Standard"
VIEWS = {"fills": (-8, 24, 15.0, (-1.3, 0, 0.0)), "close": (-30, 22, 5.6, (2.9, 0, 0.62)),
         "alt": (62, 36, 6.0, (2.9, 0, 0.6))}
for vn, (yaw, pitch, dist, tgt) in VIEWS.items():
    if QUICK and vn not in argv and "--all" not in argv and vn != "fills": continue
    t = Vector(tgt)
    d = Vector((math.cos(math.radians(pitch)) * math.sin(math.radians(yaw)),
                -math.cos(math.radians(pitch)) * math.cos(math.radians(yaw)), math.sin(math.radians(pitch))))
    cam.location = t + d * dist; cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    sc.render.filepath = os.path.join(OUT, f"{TAG}-{vn}.png")
    bpy.ops.render.render(write_still=True)
print("DONE")
