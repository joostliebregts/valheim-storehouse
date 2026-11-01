"""Coal & Stone Bunker, our own mesh and our own texture (no vanilla geometry or texture in it).
Run: blender -b -P bunker.py -- [--out DIR] [--tag NAME] [--no-ref]
Writes bunker_atlas.png (128x128, point-filtered), Bunker.obj (frame), BunkerContents.obj (one object per lump, in fill
order) and bunker.json next to the other assets (assets/bunker/), then renders three bunkers (10/50/100 %) beside the
vanilla wood chest (local rip, reference only) for scale and palette.

Atlas 128x128, horizontal strips that tile along u:
  v 0.75-1.00 hewn timber side grain (32 px)   v 0.50-0.75 end grain (4 ring tiles of 32 px)
  v 0.375-0.5 iron (16 px)                     v 0.00-0.375 content swatches: 8 x 3 tiles of 16 x 16 px
Content swatch tile (col,row) -> uv rect u [col/8,(col+1)/8], v [row/8,(row+1)/8]. A lump's uvs sit inside ONE tile,
so the mod re-colours a lump by translating its uvs by the tile delta (no new mesh, no new material).
"""
import bpy, bmesh, sys, os, math, json, random
import numpy as np
from mathutils import Vector, Matrix, Euler
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
OUTA = os.path.normpath(os.path.join(HERE, "..", "assets", "bunker"))
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = argv[argv.index("--out") + 1] if "--out" in argv else OUTA
TAG = argv[argv.index("--tag") + 1] if "--tag" in argv else "bunker"
RIP = "C:/Users/joost/ValheimRip/chests/piece_chest_wood"
os.makedirs(OUTA, exist_ok=True); os.makedirs(OUT, exist_ok=True)
rng = random.Random(7)      # frame
crng = random.Random(11)    # contents (own stream so the frame never shifts)

TEX = 128
DENS = 48.0                                                    # px per metre, vanilla wood is 47-57
STRIP = {"hewn": 0.75, "end": 0.50, "iron": 0.375}
STRIPH = {"hewn": 32, "iron": 16}

# ---------- texture ----------
def srgb(c): return np.array(c, dtype=np.float32)
WOOD, WOOD_D = srgb((0.38, 0.29, 0.18)), srgb((0.21, 0.16, 0.10))
END, END_D = srgb((0.55, 0.45, 0.31)), srgb((0.35, 0.27, 0.17))
IRON, IRON_D = srgb((0.22, 0.21, 0.20)), srgb((0.09, 0.09, 0.09))

# swatch table: name, base, dark, speck.  Row 0 minerals, row 1 ores/metals, row 2 generic hues for other stores.
SWATCHES = [
    ("coal", (0.10, 0.10, 0.11), (0.04, 0.04, 0.05), (0.30, 0.30, 0.33)),
    ("anthracite", (0.15, 0.15, 0.17), (0.06, 0.06, 0.075), (0.44, 0.46, 0.52)),
    ("stone", (0.42, 0.41, 0.39), (0.26, 0.25, 0.24), (0.56, 0.55, 0.51)),
    ("basalt", (0.29, 0.30, 0.31), (0.17, 0.18, 0.19), (0.45, 0.46, 0.48)),
    ("sandstone", (0.47, 0.41, 0.32), (0.29, 0.24, 0.18), (0.62, 0.56, 0.44)),
    ("flint", (0.66, 0.60, 0.47), (0.44, 0.39, 0.30), (0.84, 0.80, 0.68)),
    ("flint_dark", (0.30, 0.28, 0.25), (0.15, 0.14, 0.13), (0.62, 0.58, 0.50)),
    ("grausten", (0.38, 0.43, 0.45), (0.23, 0.27, 0.29), (0.55, 0.59, 0.61)),
    ("copper_ore", (0.55, 0.36, 0.22), (0.30, 0.20, 0.13), (0.42, 0.62, 0.50)),
    ("tin", (0.58, 0.60, 0.62), (0.38, 0.40, 0.42), (0.82, 0.84, 0.86)),
    ("iron_ore", (0.45, 0.24, 0.17), (0.25, 0.14, 0.11), (0.64, 0.42, 0.30)),
    ("silver", (0.66, 0.68, 0.72), (0.45, 0.47, 0.52), (0.92, 0.94, 0.97)),
    ("black_metal", (0.28, 0.22, 0.32), (0.13, 0.10, 0.16), (0.56, 0.46, 0.64)),
    ("crystal", (0.30, 0.52, 0.52), (0.16, 0.30, 0.31), (0.72, 0.90, 0.88)),
    ("amber", (0.62, 0.46, 0.18), (0.38, 0.27, 0.10), (0.86, 0.72, 0.36)),
    ("bone", (0.70, 0.64, 0.52), (0.45, 0.40, 0.31), (0.86, 0.82, 0.72)),
    ("red", (0.55, 0.20, 0.17), (0.30, 0.10, 0.09), (0.74, 0.38, 0.32)),
    ("orange", (0.62, 0.36, 0.15), (0.36, 0.19, 0.08), (0.80, 0.55, 0.30)),
    ("yellow", (0.66, 0.56, 0.22), (0.40, 0.32, 0.11), (0.84, 0.76, 0.42)),
    ("green", (0.30, 0.46, 0.22), (0.16, 0.26, 0.12), (0.52, 0.66, 0.40)),
    ("teal", (0.22, 0.44, 0.42), (0.11, 0.25, 0.24), (0.46, 0.66, 0.62)),
    ("blue", (0.25, 0.35, 0.58), (0.13, 0.19, 0.34), (0.48, 0.58, 0.80)),
    ("purple", (0.42, 0.27, 0.50), (0.23, 0.14, 0.29), (0.64, 0.48, 0.72)),
    ("pink", (0.66, 0.40, 0.45), (0.38, 0.21, 0.25), (0.84, 0.60, 0.64)),
]
SW = {s[0]: i for i, s in enumerate(SWATCHES)}
def tile_uv(i): return ((i % 8) / 8.0, (i // 8) / 8.0)       # lower-left corner of swatch tile i

def build_atlas():
    nr = np.random.default_rng(3)
    img = np.zeros((TEX, TEX, 3), np.float32)          # row 0 = v 0 (bottom)
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
    # content swatches: mottled two-tone with a few light flecks, 16 x 16 each (low-frequency blotches + pixel noise)
    for i, (nm, base, dark, speck) in enumerate(SWATCHES):
        c0, r0 = (i % 8) * 16, (i // 8) * 16
        blot = np.kron(nr.random((4, 4)), np.ones((4, 4)))              # 16x16 blotches
        t = np.clip(blot * 0.55 + nr.random((16, 16)) * 0.45, 0, 1)
        t = np.clip((t - 0.25) * 1.5, 0, 1)
        tile_px = srgb(base)[None, None] * (1 - t[..., None]) + srgb(dark)[None, None] * t[..., None]
        fl = nr.random((16, 16)) > 0.955
        tile_px[fl] = srgb(speck) * 0.6 + srgb(base) * 0.4
        img[r0:r0 + 16, c0:c0 + 16] = tile_px
    im = bpy.data.images.new("bunker_atlas", TEX, TEX, alpha=False)
    px = np.concatenate([np.clip(img, 0, 1), np.ones((TEX, TEX, 1), np.float32)], 2)
    im.pixels.foreach_set(px.ravel())
    im.filepath_raw = os.path.join(OUTA, "bunker_atlas.png"); im.file_format = "PNG"; im.save()
    return im

# ---------- geometry helpers ----------
PARTS = []     # frame objects
LUMPS = []     # (sort key, object, record)

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
PX = 1.1                       # post centre |x|, posts are P x P
P = 0.20
YF, YB = -0.60, 0.60           # front post centre y, back post base centre y
T = math.radians(8.0)          # back wall lean (top moves back)
sT, cT = math.sin(T), math.cos(T)
HF = 1.05                      # front post height
HB = 1.40                      # back post length along its axis
PITCH, PH = 0.22, 0.20         # plank pitch / height
NPL = 6
BAYS = {"L": (-0.95, -0.15), "R": (0.15, 0.95)}      # contents x bounds per bay (clear of posts, jitter and divider)
YF_IN = -0.47                  # contents front bound (boards and cleats lie in front of it)
Z_FLOOR = 0.14                 # contents floor (slat tops are ~0.09)
N_MAX = -0.13                  # contents back bound in the leaning back wall's normal coordinate

def tilt_pt(s, n):
    """Point on the back wall: s along the lean, n along its outward normal (post axis n=0). Returns (y, z)."""
    return YB + s * sT + n * cT, s * cT - n * sT

def build_frame():
    # ---- posts: 3 front (straight), 3 back (leaning)
    for sx in (-PX, 0.0, PX):
        h = HF + rng.uniform(-0.02, 0.03)
        timber("post", (P, P, h), (sx, YF, h / 2), rot=(rng.uniform(-1, 1), rng.uniform(-1, 1), 0))
        y, z = tilt_pt(HB / 2, 0)
        timber("post", (P, P, HB), (sx, y, z), rot=(-math.degrees(T) + rng.uniform(-0.8, 0.8), rng.uniform(-1, 1), 0))
    # ---- sills
    timber("sill", (2 * PX + 0.34, 0.22, 0.18), (0, YF, 0.09), rot=(0, 0, rng.uniform(-0.5, 0.5)), bevel=0)
    timber("sill", (2 * PX + 0.34, 0.22, 0.18), (0, YB + 0.04, 0.09), rot=(0, 0, rng.uniform(-0.5, 0.5)), bevel=0)
    for sx in (-PX, 0.0, PX):
        timber("sill", (0.22, 1.42, 0.16), (sx, 0.02, 0.08), bevel=0)
    # ---- floor slats under each bay (run front-back)
    for xs in (-0.85, -0.65, -0.45, -0.25, 0.25, 0.45, 0.65, 0.85):
        timber("slat", (0.17, 1.10, 0.06), (xs, 0.03, 0.06), bevel=0)
    # ---- back wall: leaning planks flush with the post inner side
    for i in range(NPL):
        s = 0.11 + PITCH * i
        y, z = tilt_pt(s, -0.04)
        timber("backplank", (2 * PX + 0.24, 0.10, PH), (0, y, z),
               rot=(-math.degrees(T) + rng.uniform(-0.6, 0.6), 0, rng.uniform(-0.4, 0.4)))
    y, z = tilt_pt(HB - 0.02, 0.0)
    timber("backcap", (2 * PX + 0.34, 0.20, 0.11), (0, y, z), rot=(-math.degrees(T), 0, rng.uniform(-0.3, 0.3)))
    # ---- side walls and divider: planks run front-back, top edge steps up to the back
    slope = (tilt_pt(HB, 0)[1] + 0.05 - (HF + 0.05)) / (tilt_pt(HB, 0)[0] - YF)
    def hw(y): return HF + (y - YF) * slope
    for sx, th in ((-PX + 0.04, 0.10), (PX - 0.04, 0.10), (0.0, 0.16)):
        for i in range(NPL):
            zc = 0.11 + PITCH * i
            top = zc + PH / 2
            y0 = YF if top <= HF else YF + (top - HF) / slope
            y1 = YB + zc * math.tan(T) + 0.06
            if y1 - y0 < 0.12: continue
            timber("sideplank", (th, y1 - y0, PH), (sx, (y0 + y1) / 2, zc), rot=(0, rng.uniform(-0.4, 0.4), 0))
    # sloped cap beams over the three walls
    ay, az = YF, HF + 0.05
    by, bz = tilt_pt(HB, 0)
    bz += 0.05
    ang = math.degrees(math.atan2(bz - az, by - ay))
    ln = math.hypot(by - ay, bz - az) + 0.14
    for sx in (-PX, 0.0, PX):
        timber("cap", (P + 0.04, ln, 0.11), (sx, (ay + by) / 2, (az + bz) / 2), rot=(ang, 0, rng.uniform(-0.3, 0.3)))
    # ---- front board slots: two cleats on each bay-facing post side, boards slide in between
    for cx in (-PX + P / 2 + 0.02, -P / 2 - 0.02, P / 2 + 0.02, PX - P / 2 - 0.02):
        for dy in (-0.06, 0.06):
            timber("cleat", (0.04, 0.04, 0.88), (cx, YF + dy, 0.55), jitter=0.004, bevel=0)
    for bx, lift in ((-0.55, 0.0), (0.55, 0.15)):       # right bay: top board pulled half out of its slot
        for i in range(3):
            zc = 0.11 + 0.22 * i + 0.1 + (lift if i == 2 else 0)
            timber("board", (0.93, 0.08, PH), (bx, YF, zc), jitter=0.012, bevel=0.016,
                   rot=(0, rng.uniform(-0.3, 0.3), rng.uniform(-0.5, 0.5) + (2.5 if (i == 2 and lift) else 0)))
            if i == 2:
                timber("pull", (0.10, 0.025, 0.06), (bx, YF - 0.055, zc), kind="iron", jitter=0.002, bevel=0)
    # ---- iron: a band round every post top, a strap low on each front post, rivets
    for sx in (-PX, 0.0, PX):
        timber("band", (P + 0.04, P + 0.04, 0.08), (sx, YF, HF - 0.03), kind="iron", jitter=0.003, bevel=0.006)
        y, z = tilt_pt(HB - 0.07, 0)
        timber("band", (P + 0.04, P + 0.04, 0.08), (sx, y, z), kind="iron", jitter=0.003, bevel=0.006,
               rot=(-math.degrees(T), 0, 0))
        timber("strap", (P + 0.05, 0.02, 0.14), (sx, YF - P / 2 - 0.008, 0.30), kind="iron", jitter=0.003, bevel=0)
        timber("strap", (P + 0.05, 0.02, 0.14), (sx, YF - P / 2 - 0.008, 0.80), kind="iron", jitter=0.003, bevel=0)
        for dx in (-0.06, 0.06):
            for zz in (0.30,):
                timber("rivet", (0.035, 0.03, 0.035), (sx + dx, YF - P / 2 - 0.022, zz), kind="iron", jitter=0, bevel=0)
    # long iron straps over the back wall planks
    for sx in (-0.6, 0.6):
        y, z = tilt_pt(0.65, 0.07)
        timber("backstrap", (0.10, 0.02, 1.0), (sx, y, z), kind="iron", jitter=0.003, bevel=0,
               rot=(-math.degrees(T), 0, 0))

# ---------- contents: a faceted heap core per step, plus loose lumps on top ----------
def hull_lump(shape, r, rr):
    bm = bmesh.new()
    sc = {"chunk": (1.0, 0.95, 0.8), "slab": (1.3, 1.0, 0.45), "block": (1.15, 0.8, 0.62),
          "shard": (1.75, 0.5, 0.42), "nugget": (0.7, 0.7, 0.62)}[shape]
    sc = tuple(c * rr.uniform(0.85, 1.15) for c in sc)
    jit = 0.2 if shape == "block" else 0.5
    pts = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            for sz in (-1, 1):
                pts.append(Vector((sx + rr.uniform(-jit, jit), sy + rr.uniform(-jit, jit), sz + rr.uniform(-jit, jit))))
    if shape == "chunk":
        d = Vector((rr.uniform(-1, 1), rr.uniform(-1, 1), rr.uniform(-0.4, 1))).normalized()
        pts.append(d * rr.uniform(1.2, 1.45))
    if shape == "shard":
        pts.append(Vector((2.1, rr.uniform(-0.2, 0.2), rr.uniform(-0.2, 0.2))))
    for p in pts:
        bm.verts.new(Vector((p.x * sc[0], p.y * sc[1], p.z * sc[2])) * r * 0.62)
    return hull_clean(bm)

def hull_clean(bm):
    bm.verts.ensure_lookup_table()
    res = bmesh.ops.convex_hull(bm, input=bm.verts[:], use_existing_faces=False)
    dead = list({g for g in res["geom_interior"] + res["geom_unused"] if isinstance(g, bmesh.types.BMVert)})
    if dead: bmesh.ops.delete(bm, geom=dead, context="VERTS")
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    return bm

def uv_lump(bm, swatch, rr, dens=DENS):
    global UV
    bm.normal_update()
    UV = bm.loops.layers.uv.verify()
    c0, r0 = tile_uv(swatch)
    cu, cv = c0 + 1 / 16, r0 + 1 / 16
    ctr = sum((v.co for v in bm.verts), Vector()) / len(bm.verts)
    pu, pv = rr.uniform(-0.012, 0.012), rr.uniform(-0.012, 0.012)
    for f in bm.faces:
        n = f.normal
        ax = max(range(3), key=lambda i: abs(n[i]))
        t = [i for i in range(3) if i != ax]
        for l in f.loops:
            u = cu + pu + (l.vert.co[t[0]] - ctr[t[0]]) * dens / TEX
            v = cv + pv + (l.vert.co[t[1]] - ctr[t[1]]) * dens / TEX
            l[UV].uv = (min(max(u, c0 + 0.004), c0 + 1 / 8 - 0.004), min(max(v, r0 + 0.004), r0 + 1 / 8 - 0.004))

def nrm(y, z): return (y - YB) * cT - z * sT
def yb_at(z): return YB + (N_MAX + z * sT) / cT - 0.004        # y of the contents back bound at height z

def violation(co):
    xl, xr = BAY
    dx = max(0, xl - min(v.x for v in co)) - max(0, max(v.x for v in co) - xr)
    dy = max(0, YF_IN - min(v.y for v in co))
    dz = max(0, Z_FLOOR - min(v.z for v in co))
    mn = max(nrm(v.y, v.z) for v in co)
    over = max(0, mn - N_MAX)
    return Vector((dx, dy - over * cT, dz + over * sT)), over

def to_object(bm, name):
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = False
    ob = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(ob)
    ob.data.materials.append(MAT)
    return ob

def make_lump(shape, r, centre, swatch, rr, name):
    for attempt in range(8):
        bm = hull_lump(shape, r, rr)
        uv_lump(bm, swatch, rr)
        bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0),
                         matrix=Euler((math.radians(rr.uniform(-25, 25)), math.radians(rr.uniform(-25, 25)),
                                       math.radians(rr.uniform(0, 360)))).to_matrix())
        bmesh.ops.translate(bm, verts=bm.verts, vec=Vector(centre))
        ok = False
        for _ in range(10):
            v, over = violation([x.co for x in bm.verts])
            if v.length < 1e-5: ok = True; break
            bmesh.ops.translate(bm, verts=bm.verts, vec=v)
        if ok: break
        r *= 0.88           # does not fit there: a smaller lump
    return to_object(bm, name)

def make_core(bay, step, swatch, rr, name):
    """The heap body of one step: a faceted wedge against the back wall, repose slope towards the boards."""
    xl, xr = BAYS[bay]; xl += 0.03; xr -= 0.03; xc = (xl + xr) / 2
    hp = PEAK[bay][step] - 0.07
    plat = PLAT[bay][step]
    yp = yb_at(hp) - plat
    yt = max(YF_IN + 0.01, yp - (hp - Z_FLOOR) / SLOPE)
    pts = [(xl, yb_at(hp), hp), (xr, yb_at(hp), hp), (xl + 0.02, yp, hp - 0.02), (xr - 0.02, yp, hp - 0.02),
           (xl + 0.05, yt, Z_FLOOR), (xr - 0.05, yt, Z_FLOOR), (xl, yb_at(Z_FLOOR), Z_FLOOR), (xr, yb_at(Z_FLOOR), Z_FLOOR),
           (xc + rr.uniform(-0.05, 0.05), (yb_at(hp) + yp) / 2, hp + 0.03),
           (xc + rr.uniform(-0.08, 0.08), (yp + yt) / 2 + 0.02, (hp + Z_FLOOR) / 2 + 0.03)]
    bm = bmesh.new()
    for p in pts:
        q = Vector(p) + Vector((rr.uniform(-0.012, 0.012), rr.uniform(-0.012, 0.012), rr.uniform(-0.012, 0.012)))
        q.x = min(max(q.x, BAYS[bay][0] + 0.02), BAYS[bay][1] - 0.02)
        q.y = max(q.y, YF_IN + 0.005); q.z = max(q.z, Z_FLOOR + 0.003)
        q.y = min(q.y, yb_at(q.z) - 0.003)
        bm.verts.new(q)
    hull_clean(bm)
    uv_lump(bm, swatch, rr, dens=DENS * 0.33)
    return to_object(bm, name)

# per bay: item mix (swatch name, weight, shape choices); the heap core alternates CORE_SW
MIX = {
    "L": [("coal", 32, ("chunk", "chunk", "slab")), ("anthracite", 14, ("chunk", "slab")), ("flint", 18, ("shard",)),
          ("flint_dark", 8, ("shard", "nugget")), ("stone", 12, ("chunk",)), ("copper_ore", 10, ("nugget", "chunk")),
          ("tin", 6, ("nugget",))],
    "R": [("stone", 26, ("chunk", "slab")), ("basalt", 14, ("chunk", "slab")), ("sandstone", 10, ("block", "chunk")),
          ("grausten", 22, ("block", "block", "slab")), ("iron_ore", 10, ("nugget", "chunk")), ("tin", 8, ("nugget",)),
          ("flint", 6, ("shard",)), ("copper_ore", 4, ("nugget",))],
}
CORE_SW = {"L": ("coal", "anthracite"), "R": ("basalt", "stone")}
PEAK = {"L": [0.34, 0.55, 0.76, 0.95, 1.08], "R": [0.32, 0.52, 0.74, 0.92, 1.04]}
PLAT = {"L": [0.10, 0.16, 0.22, 0.28, 0.34], "R": [0.08, 0.14, 0.20, 0.28, 0.34]}
SLOPE = 0.58

def surface(bay, step, x, y):
    if step < 0: return 0.0
    xl, xr = BAYS[bay]
    d = max(0.0, (yb_at(0.5) - y))
    h = PEAK[bay][step] - SLOPE * max(0.0, d - PLAT[bay][step])
    h += 0.04 * (1 - ((x - (xl + xr) / 2) / ((xr - xl) / 2)) ** 2)
    return max(0.0, h)

def pick(bay, rr):
    tot = sum(w for _, w, _ in MIX[bay]); a = rr.uniform(0, tot)
    for nm, w, shapes in MIX[bay]:
        a -= w
        if a <= 0: return nm, rr.choice(shapes)
    return MIX[bay][0][0], MIX[bay][0][2][0]

def build_contents():
    global BAY
    rr = crng
    recs = []
    for bay in ("L", "R"):
        BAY = BAYS[bay]
        xl, xr = BAY
        cols = np.linspace(xl + 0.12, xr - 0.12, 3)
        rows = np.arange(YF_IN + 0.12, 0.47, 0.235)
        for step in range(5):
            recs.append(dict(bay=bay, step=step, k=-1, shape="core", swatch=CORE_SW[bay][step % 2], r=0, c=(0, 0, 0)))
            k = 0
            for ci, cx in enumerate(cols):
                for ry in rows:
                    jx, jy = rr.uniform(-0.04, 0.04), rr.uniform(-0.04, 0.04)
                    x, y = cx + jx, ry + jy + (0.11 if ci % 2 else 0)        # staggered rows
                    s_new, s_old = surface(bay, step, x, y), surface(bay, step - 1, x, y)
                    if s_new < 0.12 or s_new - s_old < 0.06: continue
                    sw, shape = pick(bay, rr)
                    r = rr.uniform(0.15, 0.19) * (0.8 if shape in ("shard", "nugget") else 1.0)
                    z = max(Z_FLOOR + r * 0.5, s_new - r * 0.35)
                    recs.append(dict(bay=bay, step=step, k=k, shape=shape, swatch=sw, r=r, c=(x, y, z)))
                    k += 1
    recs.sort(key=lambda d: (d["step"], d["k"], d["bay"]))
    out = []
    for i, d in enumerate(recs):
        BAY = BAYS[d["bay"]]
        if d["shape"] == "core":
            ob = make_core(d["bay"], d["step"], SW[d["swatch"]], rr, f"item_{i:03d}")
        else:
            ob = make_lump(d["shape"], d["r"], d["c"], SW[d["swatch"]], rr, f"item_{i:03d}")
        out.append((ob, d))
    return out

# ---------- scene ----------
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
atlas = build_atlas()
MAT = bpy.data.materials.new("bunker"); MAT.use_nodes = True
nt = MAT.node_tree; bsdf = nt.nodes["Principled BSDF"]
ti = nt.nodes.new("ShaderNodeTexImage"); ti.image = atlas; ti.interpolation = "Closest"
nt.links.new(ti.outputs["Color"], bsdf.inputs["Base Color"])
bsdf.inputs["Roughness"].default_value = 0.8
FILLS = (0.1, 0.5, 1.0)
SPACE = 3.3
def tris(obs): return sum(len(p.vertices) - 2 for o in obs for p in o.data.polygons)

def join(obs, name):
    bpy.ops.object.select_all(action="DESELECT")
    for o in obs: o.select_set(True)
    bpy.context.view_layer.objects.active = obs[0]
    bpy.ops.object.join(); ob = bpy.context.active_object; ob.name = name
    return ob

def bvh_of(obs):
    V, F = [], []
    for o in obs:
        base = len(V)
        V += [v.co.copy() for v in o.data.vertices]
        F += [tuple(base + i for i in p.vertices) for p in o.data.polygons]
    return BVHTree.FromPolygons(V, F)

def inside(bvh, p):
    d = Vector((0.31, 0.47, 0.83)).normalized(); n = 0; o = p.copy()
    while True:
        h = bvh.ray_cast(o, d)
        if h[0] is None: break
        n += 1; o = h[0] + d * 1e-4
    return n % 2 == 1

copies = []
for k, fill in enumerate(reversed(FILLS)):
    rng.seed(7); crng.seed(11); PARTS.clear()
    build_frame()
    items = build_contents()
    LUMP_OBS = [o for o, _ in items]
    if k == 0:
        fb = bvh_of(PARTS)
        bad = []
        for o, d in items:
            xl, xr = BAYS[d["bay"]]
            co = [v.co for v in o.data.vertices]
            oob = any(v.x < xl - 1e-4 or v.x > xr + 1e-4 or v.y < YF_IN - 1e-4 or v.z < Z_FLOOR - 1e-4 or
                      nrm(v.y, v.z) > N_MAX + 1e-4 for v in co)
            ov = len(fb.overlap(bvh_of([o]))) > 0
            ins = inside(fb, sum(co, Vector()) / len(co))
            if oob or ov or ins: bad.append((o.name, oob, ov, ins))
        print("CLIPPING", len(bad), "of", len(LUMP_OBS), bad[:5])
        stats = {"frame_tris": tris(PARTS), "lump_count": len(LUMP_OBS), "contents_tris": tris(LUMP_OBS),
                 "clipping": len(bad), "atlas": "bunker_atlas.png 128x128, point filter",
                 "swatch_tile_uv": "tile i: u0=(i%8)/8, v0=(i//8)/8, size 1/8 x 1/8; lump uvs sit inside one tile",
                 "swatches": [{"i": i, "name": s[0], "u0": (i % 8) / 8, "v0": (i // 8) / 8} for i, s in enumerate(SWATCHES)],
                 "items": [dict(name=o.name, bay=d["bay"], step=d["step"], shape=d["shape"], swatch=d["swatch"],
                                swatch_i=SW[d["swatch"]], tris=tris([o])) for o, d in items]}
        for obs, fn in ((PARTS, "Bunker.obj"), (LUMP_OBS, "BunkerContents.obj")):
            bpy.ops.object.select_all(action="DESELECT")
            for o in obs: o.select_set(True)
            bpy.ops.wm.obj_export(filepath=os.path.join(OUTA, fn), export_selected_objects=True, export_materials=False,
                                  export_triangulated_mesh=True, forward_axis="NEGATIVE_Z", up_axis="Y")
        json.dump(stats, open(os.path.join(OUTA, "bunker.json"), "w"), indent=1)
        from collections import Counter
        ct = Counter()
        for o in PARTS: ct[o.name.split(".")[0]] += tris([o])
        print("TRIS", dict(ct))
        print("BUNKER", {a: b for a, b in stats.items() if a in ("frame_tris", "lump_count", "contents_tris", "clipping")})
        xs = [v.co.x for o in PARTS for v in o.data.vertices]; ys = [v.co.y for o in PARTS for v in o.data.vertices]
        zs = [v.co.z for o in PARTS for v in o.data.vertices]
        print("BOUNDS x %.2f..%.2f y %.2f..%.2f z %.2f..%.2f" % (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)))
    shown = LUMP_OBS[:round(fill * len(LUMP_OBS))]
    for o in LUMP_OBS[len(shown):]: bpy.data.objects.remove(o, do_unlink=True)
    ob = join(PARTS + shown, f"bunker_{int(fill * 100)}")
    ob.location.x = (len(FILLS) - 1 - k) * SPACE - SPACE
    copies.append(ob)

# vanilla wood chest beside it, for scale and palette (reference only, never exported)
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
        q = node["rot"]; from mathutils import Quaternion
        M = Matrix.Translation(Vector(node["pos"])) @ Quaternion((q[3], q[0], q[1], q[2])).to_matrix().to_4x4() \
            @ Matrix.Diagonal((*node["scale"], 1))
        verts = [M @ v for v in V]
        verts = [Vector((-v.x - 5.9, -v.z - 0.3, v.y)) for v in verts]
        F = [list(reversed(f)) for f in F]
        me = bpy.data.meshes.new("ref"); me.from_pydata(verts, [], [[c[0] for c in f] for f in F])
        uvl = me.uv_layers.new(); i = 0
        for f in F:
            for c in f: uvl.data[i].uv = T_[c[1]]; i += 1
        ob = bpy.data.objects.new("ref", me); sc.collection.objects.link(ob); ob.data.materials.append(vm)

world = bpy.data.worlds.new("w"); sc.world = world; world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.42, 0.45, 0.5, 1)
world.node_tree.nodes["Background"].inputs[1].default_value = 0.9
sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN")); sun.data.energy = 3.2
sun.rotation_euler = (math.radians(50), 0, math.radians(35)); sc.collection.objects.link(sun)
bpy.ops.mesh.primitive_plane_add(size=80)
gm = bpy.data.materials.new("ground"); gm.use_nodes = True
gm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.16, 0.14, 0.11, 1)
bpy.context.active_object.data.materials.append(gm)
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam); sc.camera = cam
sc.render.engine = "BLENDER_EEVEE_NEXT"
sc.render.resolution_x, sc.render.resolution_y = 1600, 900
sc.view_settings.view_transform = "Standard"
VIEWS = {"fills": (-8, 24, 18.0, (-1.0, 0, 0.5)), "close": (-28, 30, 6.4, (SPACE, 0, 0.55)),
         "alt": (32, 52, 6.0, (SPACE, 0.1, 0.5))}
for vn, (yaw, pitch, dist, tgt) in VIEWS.items():
    t = Vector(tgt)
    d = Vector((math.cos(math.radians(pitch)) * math.sin(math.radians(yaw)),
                -math.cos(math.radians(pitch)) * math.cos(math.radians(yaw)), math.sin(math.radians(pitch))))
    cam.location = t + d * dist; cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    sc.render.filepath = os.path.join(OUT, f"{TAG}-{vn}.png")
    bpy.ops.render.render(write_still=True)
print("DONE")
