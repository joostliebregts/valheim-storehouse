"""Apothecary Rack round 2 (Joost, 24 Oct): the vessel follows the item. 32 places in 4 tiers of 8; every place can hold any of the
four families of creature parts and shows the vessel of whatever it holds ("a rack full of needles is all crocks"):
  hanging  Feathers, WolfHairBundle, ElakingHairBundle, MooseSinew, MorgenSinew     a little gallows: base, two posts, a bar, two iron pegs; one big bundle hangs from each
  jar      GreydwarfEye, RoyalJelly, Ectoplasm, GiantBloodSack, DragonTear, AskBladder   glass jar, open at the front, cork (RoyalJelly and
           Ectoplasm are semi-liquid: a jelly column that rises, as Cooper's Row's liquids)
  crock    Needle, WolfFang, WolfClaw, SurtlingCore, Mandible, MorgenHeart, Bilebag    bellied clay crock with a cord at the neck
  basket   Chitin, Carapace, SerpentScale, BonemawSerpentScale, BjornPaw, CelestialFeather   wicker basket with two rope handles (front/back)
Never two kinds in one vessel (SPEC.md "What lies where"). Each place has 2 units (stacks) per family (32 x 4 x 2 = 256 units, 64 stacks
of a family at most: 64 total in the store), so a vessel of any family can be full, and how full it is shows (a heap that rises, hooks that fill,
a jelly column that rises).
Run: "C:/Program Files/Blender Foundation/Blender 4.5/blender.exe" -b -P apothecary_r2.py -- [--out DIR] [--no-render] [--quick] [--no-export]

Size 2.52 W x 0.45 D x 2.0 H (Blender x, y, z; -y = front, back face y = 0 at the wall, x centred, z = 0 the foot). Tiers (shelf tops) at
1.47, 1.02, 0.57, 0.11 m; places 0.28 m apart (x = -0.98 ... 0.98), vessel centre y = -0.25. n = tier * 8 + column, tier 0 the top, column 0
the left as seen from the front (Blender x ascending, Unity x descending).
Every vessel has the SAME clear space: an upright cylinder R_C 0.100 x H_C 0.22 on a floor at origin + 0.02 (= crate_floor_centres[place]). The
hanging parts hang from the pegs (tips at its top) in the gallows' room between its posts (|x| <= 0.099, |y| <= 0.05, a bit wider than the cylinder). So each item is settled once (heap, or hung) and fits any place of its family.
Contents: the game's own item models; physics-settled like r1 (rigid body, convex hulls), split in 2 stacks; hanging parts are laid out by hand
(one big bundle per stack). Budget: a full store of the heaviest kind under ~250k triangles.

Atlas 128 x 128 (point filtered, 48 px/m): bunker_r4's timber, end grain and iron rows byte-identical; clay, wicker, glass, cord and swatches as r1;
leather is gone and rows 8-15 hold the liquid tiles: per liquid a 16x8 side and an 8x8 top (RoyalJelly: pale translucent gold; Ectoplasm: pale
ghostly green-white).
Files (assets/apothecary_r2/): Apothecary.obj (frame only), Vessel_{hanging,jar,crock,basket}.obj (local coordinates, origin = centre of the
footprint at the shelf surface), Liquid_<place>_<Item>.obj, apothecary_atlas.png, apothecary_anchors.json (last, temp + rename).
Unity prefab space: ux = -bx, uy = bz, uz = -by (OBJ exported forward -Z, up Y, like every store).
"""
import bpy, bmesh, sys, os, math, json, random, time
import numpy as np
from mathutils import Vector, Matrix, Euler, Quaternion
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, ".."))
OUTA = os.path.join(REPO, "assets", "apothecary_r2")
BUNKER = os.path.join(REPO, "assets", "bunker_r4")
R1DIR = os.path.join(REPO, "assets", "apothecary_r1")
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
def arg(k, d=None): return argv[argv.index(k) + 1] if k in argv else d
OUT = arg("--out", "C:/Users/joost/AppData/Local/Temp/claude/C--Users-joost--pai/5e4bc60b-cdfe-4638-8e29-2e507fa13cf9/scratchpad/apothecary_r2")
RENDER = "--no-render" not in argv
QUICK = "--quick" in argv
EXPORT = "--no-export" not in argv
ITEMS_DIR = "C:/Users/joost/ValheimRip/items"
sys.path.append(ITEMS_DIR)
from load_item import load_item
OUTA = arg("--assets", OUTA)
os.makedirs(OUTA, exist_ok=True); os.makedirs(OUT, exist_ok=True)

APOTHECARY = {   # item -> family (the dictionary in Storehouse.cs)
    "Feathers": "hanging", "WolfHairBundle": "hanging", "ElakingHairBundle": "hanging", "MooseSinew": "hanging", "MorgenSinew": "hanging",
    "GreydwarfEye": "jar", "RoyalJelly": "jar", "Ectoplasm": "jar", "GiantBloodSack": "jar", "DragonTear": "jar", "AskBladder": "jar",
    "Needle": "crock", "WolfFang": "crock", "WolfClaw": "crock", "SurtlingCore": "crock", "Mandible": "crock", "MorgenHeart": "crock", "Bilebag": "crock",
    "Chitin": "basket", "Carapace": "basket", "SerpentScale": "basket", "BonemawSerpentScale": "basket", "BjornPaw": "basket", "CelestialFeather": "basket",
}
ITEMS = list(APOTHECARY)
FAMILIES = ["hanging", "jar", "crock", "basket"]
LIQUIDS = ["RoyalJelly", "Ectoplasm"]
if QUICK: ITEMS = ["Feathers", "MooseSinew", "GreydwarfEye", "RoyalJelly", "Ectoplasm", "Needle", "WolfFang", "Chitin", "BjornPaw"]

rng = random.Random(7)
TEX = 128
DENS = 48.0
STRIP = {"hewn": 0.75, "end": 0.50, "iron": 0.375}
STRIPH = {"hewn": 32, "iron": 16}
ROWS = {"clay": (36, 12), "wicker": (24, 12), "glass": (16, 8), "rope": (4, 4)}
SWATCH = {"cork": 0, "ivory": 1, "amber": 2, "pupil": 3, "feather": 4, "glassbright": 5, "wear": 6, "soot": 7}

# ---------- atlas ----------
def srgb(c): return np.array(c, dtype=np.float32)
def mix(a, b, t): t = np.clip(t, 0, 1)[..., None]; return a * (1 - t) + b * t

LIQ_COL = {   # side base, dark, light; top base, dark, light
    "RoyalJelly": ((0.80, 0.68, 0.34), (0.60, 0.48, 0.20), (0.93, 0.85, 0.58), (0.88, 0.78, 0.46), (0.72, 0.60, 0.30), (0.97, 0.92, 0.72)),
    "Ectoplasm": ((0.74, 0.85, 0.78), (0.55, 0.70, 0.62), (0.92, 0.97, 0.94), (0.84, 0.93, 0.88), (0.68, 0.80, 0.74), (0.96, 0.99, 0.97)),
}

def build_atlas():
    src = bpy.data.images.load(os.path.join(BUNKER, "bunker_atlas.png"))
    img = np.array(src.pixels[:], np.float32).reshape(TEX, TEX, 4)[..., :3].copy()
    nr = np.random.default_rng(29)
    tile = lambda k: 2 * math.pi * k / TEX
    def grid(h): return (np.arange(TEX)[None, :].repeat(h, 0).astype(np.float32), np.arange(h)[:, None].repeat(TEX, 1).astype(np.float32))
    x, y = grid(12)
    t = 0.30 + 0.22 * np.sin(y * 2.3 + 0.7 * np.sin(x * tile(3))) * 0.5 + 0.20 * (0.5 + 0.5 * np.sin(x * tile(2) + 1.3)) + nr.random((12, TEX)) * 0.18
    t += (y < 1.5) * 0.45 + (y < 0.5) * 0.2
    c = mix(srgb((0.50, 0.34, 0.24)), srgb((0.24, 0.155, 0.11)), t)
    c = np.where((y > 10.5)[..., None], mix(c, srgb((0.62, 0.48, 0.36)), np.full((12, TEX), 0.6)), c)
    sp = nr.random((12, TEX)) < 0.04; c[sp] = c[sp] * 0.7
    img[36:48] = c
    x, y = grid(12)
    over = (((x // 8).astype(int) + (y // 3).astype(int)) % 2) == 0
    row = y % 3; col = x % 8
    t = np.where(over, np.where(row == 1, 0.15, 0.45), np.where((col >= 3) & (col <= 4), 0.35, 0.6))
    t += ((row == 0) & over) * 0.25 + ((col == 0) & ~over) * 0.35 + nr.random((12, TEX)) * 0.15
    c = mix(srgb((0.56, 0.47, 0.30)), srgb((0.22, 0.165, 0.095)), t)
    hi = over & (row == 1) & (col == 4); c[hi] = mix(c[hi], srgb((0.70, 0.61, 0.42)), np.full(hi.sum(), 0.5))
    img[24:36] = c
    x, y = grid(8)
    t = 0.45 + nr.random((8, TEX)) * 0.12 + 0.12 * np.sin(x * tile(5) + 0.4)
    t -= ((x % 32 >= 5) & (x % 32 <= 6)) * 0.45 + ((x % 32) == 19) * 0.3
    t += (y < 1) * 0.25
    img[16:24] = mix(srgb((0.80, 0.86, 0.82)), srgb((0.46, 0.54, 0.51)), t)
    x, y = grid(4)
    t = ((x + y * 1.5) % 5 < 2.5) * 0.45 + nr.random((4, TEX)) * 0.2 + ((y == 0) | (y == 3)) * 0.2
    img[4:8] = mix(srgb((0.52, 0.44, 0.30)), srgb((0.22, 0.17, 0.10)), t)
    SW = [((0.55, 0.42, 0.27), (0.30, 0.21, 0.12)), ((0.80, 0.76, 0.64), (0.55, 0.49, 0.38)), ((0.80, 0.62, 0.20), (0.48, 0.32, 0.08)),
          ((0.09, 0.08, 0.07), (0.02, 0.02, 0.02)), ((0.82, 0.81, 0.77), (0.55, 0.55, 0.53)), ((0.88, 0.93, 0.90), (0.66, 0.74, 0.71)),
          ((0.52, 0.43, 0.31), (0.36, 0.29, 0.20)), ((0.13, 0.11, 0.10), (0.06, 0.05, 0.05))]
    for i, (a, b) in enumerate(SW):
        img[0:4, 16 * i:16 * i + 16] = mix(srgb(a), srgb(b), nr.random((4, 16)) * 0.55 + (i == 1) * 0.1)
    # liquids (rows 8-15, where r1 had leather): per liquid a 16x8 side tile (blobs and trapped bubbles / wisps) and an 8x8 top tile
    for i, it in enumerate(LIQUIDS):
        sb, sd, sl, tb, td, tl = [srgb(v) for v in LIQ_COL[it]]
        blob = np.kron(nr.random((2, 4)), np.ones((4, 4), np.float32)) * 0.35 + np.kron(nr.random((4, 8)), np.ones((2, 2), np.float32)) * 0.3
        if it == "Ectoplasm":
            wisp = 0.5 + 0.5 * np.sin(np.arange(16)[None, :] * 0.9 + np.arange(8)[:, None] * 0.55 + 2.0 * i)
            blob = blob * 0.55 + wisp * 0.4
        side = mix(sb, sd, blob + nr.random((8, 16)) * 0.12)
        bub = nr.random((8, 16)) < 0.07
        side[bub] = mix(side[bub], np.broadcast_to(sl, side[bub].shape), np.full(bub.sum(), 0.75))
        img[8:16, 24 * i:24 * i + 16] = side
        t = nr.random((8, 8)) * 0.25 + 0.15 * np.sin(np.arange(8)[None, :] * 0.8 + np.arange(8)[:, None] * 0.7)
        top = mix(tb, td, t)
        gl = nr.random((8, 8)) < 0.08
        top[gl] = mix(top[gl], np.broadcast_to(tl, top[gl].shape), np.full(gl.sum(), 0.85))
        img[8:16, 24 * i + 16:24 * i + 24] = top
    im = bpy.data.images.new("apothecary_atlas", TEX, TEX, alpha=False)
    px = np.concatenate([np.clip(img, 0, 1), np.ones((TEX, TEX, 1), np.float32)], 2)
    im.pixels.foreach_set(px.ravel())
    im.filepath_raw = os.path.join(OUTA, "apothecary_atlas.png"); im.file_format = "PNG"; im.save()
    bpy.data.images.remove(src)
    return im

# ---------- geometry helpers (r1's) ----------
PARTS = []
UV = None

def uv_face(f, kind, long_axis, seed):
    n = f.normal
    ax = max(range(3), key=lambda i: abs(n[i]))
    tang = [i for i in range(3) if i != ax]
    if kind in SWATCH:
        sw_uv(f, kind); return
    if kind != "iron" and ax == long_axis:
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
    if kind in ROWS:
        b, h = ROWS[kind]
        for l in f.loops:
            l[UV].uv = (l.vert.co[ua] * DENS / TEX + off, (b + 0.5 + (l.vert.co[va] - vmin) / span * (h - 1)) / TEX)
        return
    hpx = STRIPH[kind]
    vscale = min(1.0, (hpx / DENS) / span)
    room = max(hpx / TEX - span * vscale * DENS / TEX * 0.94 - 0.012, 0)
    voff = ((seed * 0.618) % 1) * room
    for l in f.loops:
        u = l.vert.co[ua] * DENS / TEX + off
        v = STRIP[kind] + ((l.vert.co[va] - vmin) * vscale * DENS / TEX) * 0.94 + 0.0075 + voff
        l[UV].uv = (u, v)

def sw_uv(f, kind):
    i = SWATCH[kind]
    for l in f.loops:
        p = l.vert.co
        l[UV].uv = ((16 * i + 2 + ((p.x * 31 + p.y * 17 + p.z * 23) * DENS) % 12) / TEX, (0.5 + ((p.x * 13 + p.z * 29) * DENS) % 3) / TEX)

def link(bm, name):
    bm.normal_update()
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = False
    ob = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(ob)
    ob.data.materials.append(MAT); PARTS.append(ob)
    return ob

def timber(name, size, pos, kind="hewn", rot=(0, 0, 0), jitter=0.022, bevel=0.022):
    global UV
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
    bm.normal_update()
    UV = bm.loops.layers.uv.verify()
    seed = rng.randrange(1000)
    for f in bm.faces: uv_face(f, kind, long_axis, seed + f.index % 2)
    bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Euler([math.radians(a) for a in rot]).to_matrix())
    bmesh.ops.translate(bm, verts=bm.verts, vec=Vector(pos))
    return link(bm, name)

def plank(name, size, pos, rot=(0, 0, 0), kind="hewn", jitter=0.006):
    return timber(name, size, pos, kind=kind, rot=rot, jitter=jitter, bevel=0.008)

def iron(name, size, pos, rot=(0, 0, 0)):
    return timber(name, size, pos, kind="iron", rot=rot, jitter=0.002, bevel=0)

def rivet(pos, face):
    s = [0.03, 0.03, 0.03]; s[face[0]] = 0.012
    p = list(pos); p[face[0]] += face[1] * 0.006
    iron("rivet", s, p)

def shell(name, prof, t, kind, segs=24, arc=None, bottom=True, tb=None, at=(0, 0, 0), rotz=0.0):
    """A vessel wall of revolution (r1's): prof = [(r_out, z)] bottom to top, wall t; arc leaves the rest open; bottom: a floor tb thick"""
    global UV
    tb = t if tb is None else tb
    z0 = prof[0][1]
    full = arc is None
    if full: angs = [2 * math.pi * i / segs for i in range(segs)]
    else:
        n = max(2, round(segs * (arc[1] - arc[0]) / (2 * math.pi)))
        angs = [arc[0] + (arc[1] - arc[0]) * i / n for i in range(n + 1)]
    inner = [(max(r - t, 0.004), max(z, z0 + tb) if bottom else z) for r, z in prof]
    bm = bmesh.new(); UV = bm.loops.layers.uv.verify()
    O = [[bm.verts.new((r * math.cos(a), r * math.sin(a), z)) for a in angs] for r, z in prof]
    I = [[bm.verts.new((r * math.cos(a), r * math.sin(a), z)) for a in angs] for r, z in inner]
    nA = len(angs); nseg = nA if full else nA - 1
    rref = max(r for r, _ in prof); zlo, zhi = prof[0][1], prof[-1][1]
    off = rng.random()
    def wall(vs, ia):
        f = bm.faces.new(vs)
        if kind in SWATCH: sw_uv(f, kind); return f
        b, h = ROWS[kind]
        for l, a in zip(f.loops, ia):
            l[UV].uv = (a * rref * DENS / TEX + off, (b + 0.5 + (l.vert.co.z - zlo) / max(zhi - zlo, 1e-4) * (h - 1)) / TEX)
        return f
    def flat(vs):
        f = bm.faces.new(vs)
        if kind in SWATCH: sw_uv(f, kind); return f
        b, h = ROWS[kind]
        ys = [v.co.y for v in vs]; y0 = min(ys); sp = max(max(ys) - y0, 1e-4)
        for l in f.loops:
            l[UV].uv = (l.vert.co.x * DENS / TEX + off, (b + 0.5 + (l.vert.co.y - y0) / sp * min(h - 1, sp * DENS)) / TEX)
        return f
    A = angs + [2 * math.pi] if full else angs
    for j in range(len(prof) - 1):
        for i in range(nseg):
            i1 = (i + 1) % nA
            wall([O[j][i], O[j][i1], O[j + 1][i1], O[j + 1][i]], [A[i], A[i + 1], A[i + 1], A[i]])
            wall([I[j][i], I[j + 1][i], I[j + 1][i1], I[j][i1]], [A[i], A[i], A[i + 1], A[i + 1]])
    for i in range(nseg):
        i1 = (i + 1) % nA
        wall([O[-1][i], I[-1][i], I[-1][i1], O[-1][i1]], [A[i], A[i], A[i + 1], A[i + 1]])
        if not bottom: wall([O[0][i], O[0][i1], I[0][i1], I[0][i]], [A[i], A[i + 1], A[i + 1], A[i]])
    if bottom:
        co = bm.verts.new((0, 0, z0)); ci = bm.verts.new((0, 0, inner[0][1]))
        for i in range(nseg):
            i1 = (i + 1) % nA
            flat([co, O[0][i1], O[0][i]]); flat([ci, I[0][i], I[0][i1]])
        if not full:
            for e in (0, nA - 1):
                flat([co, ci, I[0][e], O[0][e]])
    if not full:
        for e in (0, nA - 1):
            for j in range(len(prof) - 1):
                wall([O[j][e], O[j + 1][e], I[j + 1][e], I[j][e]], [0, 0, 0.02, 0.02])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(rotz, 3, "Z"))
    bmesh.ops.translate(bm, verts=bm.verts, vec=Vector(at))
    return link(bm, name)

def cord(name, p0, p1, w=0.008, kind="rope"):
    global UV
    p0, p1 = Vector(p0), Vector(p1); d = p1 - p0; L = d.length
    if kind == "rope":
        bm = bmesh.new(); UV = bm.loops.layers.uv.verify(); off = rng.random()
        bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=3, radius1=w * 0.62, radius2=w * 0.62, depth=L + w * 0.6)
        bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, "Y"))
        b, h = ROWS[kind]
        for f in bm.faces:
            for l in f.loops:
                c = l.vert.co
                l[UV].uv = (c.x * DENS / TEX + off, (b + 0.5 + (0.5 + math.atan2(c.y, c.z) / (2 * math.pi)) * (h - 1)) / TEX)
        R = Vector((1, 0, 0)).rotation_difference(d.normalized()).to_matrix()
        bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=R)
        bmesh.ops.translate(bm, verts=bm.verts, vec=(p0 + p1) / 2)
        return link(bm, name)
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts: v.co = Vector((v.co.x * (L + w * 0.6), v.co.y * w, v.co.z * w))
    UV = bm.loops.layers.uv.verify(); off = rng.random()
    bm.normal_update()
    for f in bm.faces:
        if kind in SWATCH: sw_uv(f, kind); continue
        if kind == "iron": uv_face(f, "iron", 0, rng.randrange(100)); continue
        b, h = ROWS[kind]
        for l in f.loops:
            c = l.vert.co
            l[UV].uv = (c.x * DENS / TEX + off, (b + 0.5 + (0.5 + (c.y + c.z) / (2 * w)) * (h - 1)) / TEX)
    R = Vector((1, 0, 0)).rotation_difference(d.normalized()).to_matrix()
    bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=R)
    bmesh.ops.translate(bm, verts=bm.verts, vec=(p0 + p1) / 2)
    return link(bm, name)

def disc(name, r0, r1, z0, z1, kind, at, segs=24):
    global UV
    bm = bmesh.new(); UV = bm.loops.layers.uv.verify()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=segs, radius1=r0, radius2=r1, depth=z1 - z0)
    bm.normal_update(); sd = rng.randrange(1000)
    for f in bm.faces: uv_face(f, kind, 2, sd)
    bmesh.ops.translate(bm, verts=bm.verts, vec=Vector(at) + Vector((0, 0, (z0 + z1) / 2)))
    return link(bm, name)

def ring(name, r, z, w, center, kind="rope", segs=16, rotz=0.0):
    c = Vector(center)
    pts = [c + Vector((r * math.cos(rotz + 2 * math.pi * i / segs), r * math.sin(rotz + 2 * math.pi * i / segs), z)) for i in range(segs)]
    for i in range(segs): cord(name, pts[i], pts[(i + 1) % segs], w, kind)

# ---------- layout ----------
NCOL, PITCH = 8, 0.28
PS = 0.14                                   # front post section
XIN = NCOL * PITCH / 2                      # 1.12: inner face of the posts
PX = XIN + PS / 2                           # post centre x
W, DEPTH, H = 2 * (XIN + PS), 0.45, 2.0     # 2.52
YF0, YF1 = -DEPTH, -DEPTH + PS
YB0, YB1 = -0.115, -0.005
YBACK = (-0.045, -0.005)
SHELF_T = 0.05
LEVEL = [1.47, 1.02, 0.57, 0.11]            # shelf tops, tier 0 (top) to 3 (floor board)
TOPB = 1.94
COLX = [(c - 3.5) * PITCH for c in range(NCOL)]
VY = -0.25
NPLACE = NCOL * len(LEVEL)
UNITS_PER = 2                               # stacks per place and family: 32 x 2 = 64
SEG = 16
TB = 0.02                                   # the floor of every vessel
R_C, H_C = 0.100, 0.22                      # the clear space: upright cylinder on the floor (z = TB above the shelf)
FAM_ORDER = ["jar", "crock", "hanging", "basket"]
DEFAULT = [FAM_ORDER[(c + r) % 4] for r in range(len(LEVEL)) for c in range(NCOL)]     # a mix: every row and column has all four

def place_origin(n):
    r, c = divmod(n, NCOL)
    return Vector((COLX[c], VY, LEVEL[r]))

def in_cyl(P, eps=0.0015):
    return (P[:, 2] >= min(eps, 0.0) - 0.0002) & (P[:, 2] <= H_C - eps) & (np.hypot(P[:, 0], P[:, 1]) <= R_C - eps)

def in_hang(P, eps=0.0015):
    """the hanging parts' room: between the gallows' posts (|x| <= HANG_X), a little deep (|y| <= HANG_Y), under the peg tips"""
    return (P[:, 2] >= eps) & (P[:, 2] <= H_C - eps) & (np.abs(P[:, 0]) <= HANG_X - eps) & (np.abs(P[:, 1]) <= HANG_Y - eps)

def outside_hang(P):
    return float(np.max(np.maximum.reduce([-P[:, 2], P[:, 2] - H_C, np.abs(P[:, 0]) - HANG_X, np.abs(P[:, 1]) - HANG_Y])))

def outside_cyl(P):
    return float(np.max(np.maximum.reduce([-P[:, 2], P[:, 2] - H_C, np.hypot(P[:, 0], P[:, 1]) - R_C])))

# ---------- the four vessels, in local coordinates (origin = centre of the footprint at the shelf surface) ----------
PEG_Z = TB + H_C                             # peg tips at the top of the clear space
PEGS = [(-0.052, 0.0), (0.052, 0.0)]         # two pegs on one bar: one big bundle per stack (the Cloth Rack's one bolt per unit)
PEG_ORDER = [0, 1]
HANG_X, HANG_Y = 0.099, 0.050                # the hanging parts' room: between the gallows' posts, a little deep
VESSEL_PROF = {
    "jar": dict(prof=[(0.116, 0.0), (0.119, 0.02), (0.119, 0.262), (0.111, 0.285)], t=0.008),
    "crock": dict(prof=[(0.121, 0.0), (0.129, 0.04), (0.133, 0.085), (0.128, 0.12), (0.122, 0.14), (0.127, 0.152)], t=0.014),
    "basket": dict(prof=[(0.121, 0.0), (0.127, 0.03), (0.133, 0.075), (0.136, 0.11), (0.137, 0.12)], t=0.013),
}

def build_vessel(fam):
    o = Vector((0, 0, 0))
    if fam == "jar":
        v = VESSEL_PROF["jar"]; half = math.radians(62); front = -math.pi / 2
        shell("jar", v["prof"], v["t"], "glass", SEG, arc=(front + half, front - half + 2 * math.pi), bottom=False, at=o)
        disc("jarbase", 0.118, 0.118, 0.0, TB, "glass", o, SEG)
        shell("jarrim", [(0.110, 0.282), (0.111, 0.300)], 0.012, "glassbright", 12, bottom=False, at=o)
        disc("cork", 0.094, 0.086, 0.292, 0.334, "cork", o, 12)
    elif fam == "crock":
        v = VESSEL_PROF["crock"]
        shell("crock", v["prof"], v["t"], "clay", SEG, bottom=True, tb=TB, at=o, rotz=rng.uniform(0, 2 * math.pi))
        ring("crockcord", 0.1235, 0.128, 0.011, o, "rope", 10, 0.0)
    elif fam == "basket":
        v = VESSEL_PROF["basket"]
        shell("basket", v["prof"], v["t"], "wicker", SEG, bottom=True, tb=TB, at=o, rotz=rng.uniform(0, 2 * math.pi))
        for a in (math.pi / 2, 3 * math.pi / 2):                      # two rope handles, front and back
            p = [o + Vector((0.139 * math.cos(a + d), 0.139 * math.sin(a + d), 0.128 + h)) for d, h in ((-0.20, 0), (-0.11, 0.045), (0.11, 0.045), (0.20, 0))]
            for q0, q1 in zip(p[:-1], p[1:]): cord("handle", q0 + Vector((0, 0, 0.003)), q1 + Vector((0, 0, 0.003)), 0.013, "rope")
    else:                                                              # the gallows: base, two posts, one bar, two iron pegs
        disc("hbase", 0.116, 0.116, 0.0, TB, "hewn", o, 12)
        for sx in (-1, 1):
            timber("hpost", (0.022, 0.022, 0.29), (sx * 0.113, 0.0, TB + 0.145), jitter=0.0008, bevel=0.003)
            iron("hstrap", (0.030, 0.030, 0.008), (sx * 0.113, 0.0, PEG_Z + 0.020 + 0.011))
        timber("hbar", (0.250, 0.024, 0.024), (0, 0.0, PEG_Z + 0.020 + 0.012), jitter=0.0008, bevel=0.004)
        for x, y in PEGS: iron("peg", (0.010, 0.010, 0.020), (x, y, PEG_Z + 0.010))

# ---------- the frame ----------
def build_frame():
    j = lambda a: rng.uniform(-a, a)
    for sx in (-1, 1):
        timber("post", (PS, PS, TOPB), (sx * PX, (YF0 + YF1) / 2, TOPB / 2), rot=(j(0.3), j(0.3), 0), jitter=0.012, bevel=0.02)
        timber("post", (PS, YB1 - YB0, TOPB), (sx * PX, (YB0 + YB1) / 2, TOPB / 2), jitter=0.008, bevel=0.018)
    plank("top", (W + 0.02, DEPTH + 0.02, 0.06), (0, -DEPTH / 2 + 0.005, TOPB + 0.03), rot=(0, 0, j(0.2)))
    xs = np.linspace(-XIN, XIN, 10)
    for a, b in zip(xs[:-1], xs[1:]):
        plank("back", (b - a + 0.012, YBACK[1] - YBACK[0], TOPB - 0.06), ((a + b) / 2, sum(YBACK) / 2, 0.06 + (TOPB - 0.06) / 2), rot=(0, j(0.3), 0))
    for y in (-0.40, -0.12):
        timber("sill", (2 * XIN + 0.02, 0.10, 0.06), (0, y, 0.03), jitter=0.006, bevel=0.012)
    for top in LEVEL:
        # shelves: thin jitter so the vessel feet stand on a flat surface; a low lip along the front edge
        plank("shelf", (2 * XIN + 0.04, DEPTH + YBACK[0], SHELF_T), (0, (-DEPTH + YBACK[0]) / 2, top - SHELF_T / 2), rot=(0, 0, j(0.2)), jitter=0.0015)
        plank("lip", (2 * XIN, 0.035, 0.045), (0, -DEPTH + 0.0175, top + 0.0225), jitter=0.0015)
        for sx in (-1, 1):
            plank("side", (0.06, YB0 - YF1 + 0.06, 0.14), (sx * PX, (YF1 + YB0) / 2, max(top - 0.07, 0.07)), kind="hewn")
    for sx in (-1, 1):
        plank("side", (0.06, YB0 - YF1 + 0.06, 0.14), (sx * PX, (YF1 + YB0) / 2, TOPB - 0.07))
    timber("header", (W, 0.12, 0.12), (0, YF0 + 0.06, TOPB - 0.06), rot=(0, 0, j(0.15)), jitter=0.01, bevel=0.018)
    # back stiles between the places (behind the vessels, in front of the back boards) in every tier: x = -0.5, 0, 0.5
    tops = sorted(LEVEL) + [TOPB - 0.06]
    for lo, hi in zip(tops[:-1], tops[1:]):
        for x in (-0.56, 0.0, 0.56):
            plank("stile", (0.07, YBACK[0] - YB0 + 0.0, hi - SHELF_T - lo), (x, (YB0 + YBACK[0]) / 2, (lo + hi - SHELF_T) / 2), jitter=0.0015)
    for sx in (-1, 1):
        for top in LEVEL + [TOPB - 0.06]:
            zc = top - 0.025
            iron("bracket", (0.11, 0.008, 0.17), (sx * PX, YF0 - 0.004, zc))
            for dz in (-0.05, 0.05): rivet((sx * PX, YF0 - 0.008, zc + dz), (1, -1))
            iron("strap", (0.16, 0.008, 0.045), (sx * (XIN - 0.07), YF0 - 0.002, top - SHELF_T / 2 if top != TOPB - 0.06 else top - 0.03))
            rivet((sx * (XIN - 0.11), YF0 - 0.006, top - SHELF_T / 2 if top != TOPB - 0.06 else top - 0.03), (1, -1))
        iron("band", (PS + 0.016, PS + 0.016, 0.05), (sx * PX, (YF0 + YF1) / 2, 0.06))
    build_plaque()

def build_plaque():
    """r1's plaque on the header: a board with a fang, an eye and a feather in relief, riveted at its corners"""
    global UV
    yb = YF0 - 0.035
    plank("plaque", (0.62, 0.035, 0.105), (0, YF0 - 0.0175, TOPB - 0.06))
    for dx in (-0.28, 0.28):
        for dz in (-0.033, 0.033): rivet((dx, yb, TOPB - 0.06 + dz), (1, -1))
    zc = TOPB - 0.06; yf = yb - 0.004
    bm = bmesh.new(); UV = bm.loops.layers.uv.verify()
    rings = []
    for k in range(6):
        t = k / 5; rr = 0.016 * (1 - t) + 0.0015
        cx = 0.012 * math.sin(t * 1.6); cz = 0.038 - 0.08 * t
        rings.append([bm.verts.new((cx + rr * math.cos(a), -rr * math.sin(a) * 0.8, cz)) for a in [2 * math.pi * i / 6 for i in range(6)]])
    for k in range(5):
        for i in range(6): bm.faces.new([rings[k][i], rings[k][(i + 1) % 6], rings[k + 1][(i + 1) % 6], rings[k + 1][i]])
    bm.faces.new(rings[0]); bm.faces.new(list(reversed(rings[-1])))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    for f in bm.faces: sw_uv(f, "ivory")
    bmesh.ops.translate(bm, verts=bm.verts, vec=Vector((-0.17, yf - 0.006, zc)))
    link(bm, "fang")
    bm = bmesh.new(); UV = bm.loops.layers.uv.verify()
    bmesh.ops.create_uvsphere(bm, u_segments=10, v_segments=6, radius=0.032)
    for v in bm.verts: v.co.y *= 0.6
    for f in bm.faces: sw_uv(f, "amber")
    bmesh.ops.translate(bm, verts=bm.verts, vec=Vector((0, yf + 0.004, zc)))
    link(bm, "eye")
    timber("pupil", (0.009, 0.006, 0.040), (0, yf - 0.016, zc), kind="pupil", jitter=0, bevel=0)
    for dz in (-1, 1):
        cord("lid", (-0.04, yf - 0.004, zc + dz * 0.012), (0, yf - 0.012, zc + dz * 0.036), 0.009, "soot")
        cord("lid", (0, yf - 0.012, zc + dz * 0.036), (0.04, yf - 0.004, zc + dz * 0.012), 0.009, "soot")
    bm = bmesh.new(); UV = bm.loops.layers.uv.verify()
    n = 9; L = 0.095; pts = []
    for i in range(n): t = i / (n - 1); pts.append((0.022 * math.sin(math.pi * t) ** 0.7 * (1.1 - 0.3 * t), t * L))
    outline = [Vector((x, 0, z)) for x, z in pts] + [Vector((-x, 0, z)) for x, z in reversed(pts[1:-1])]
    vs = [bm.verts.new(p) for p in outline]
    f = bm.faces.new(vs)
    ext = bmesh.ops.extrude_face_region(bm, geom=[f])
    bmesh.ops.translate(bm, verts=[e for e in ext["geom"] if isinstance(e, bmesh.types.BMVert)], vec=Vector((0, -0.006, 0)))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    for fc in bm.faces: sw_uv(fc, "feather")
    bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.radians(-22), 3, "Y"))
    bmesh.ops.translate(bm, verts=bm.verts, vec=Vector((0.15, yb + 0.002, zc - 0.045)))
    link(bm, "feather")
    a = math.radians(-22)
    q = lambda z: (0.15 + z * math.sin(a), yb - 0.006, zc - 0.045 + z * math.cos(a))
    cord("quill", q(-0.016), q(0.092), 0.004, "ivory")

# ---------- scene ----------
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
ATLAS = build_atlas()
MAT = bpy.data.materials.new("apothecary"); MAT.use_nodes = True
nt = MAT.node_tree; bsdf = nt.nodes["Principled BSDF"]
ti = nt.nodes.new("ShaderNodeTexImage"); ti.image = ATLAS; ti.interpolation = "Closest"
nt.links.new(ti.outputs["Color"], bsdf.inputs["Base Color"])
bsdf.inputs["Roughness"].default_value = 0.8
def tris(obs): return sum(len(p.vertices) - 2 for o in obs for p in o.data.polygons)
t0 = time.time()

def part_data(obs):
    """per part: vertex array, triangles, bounds, a BVH, for the inside tests"""
    out = []
    for o in obs:
        vs = [v.co.copy() for v in o.data.vertices]; a = np.array([v[:] for v in vs])
        out.append(dict(name=o.name, V=a, lo=a.min(0), hi=a.max(0), bvh=BVHTree.FromPolygons(vs, [tuple(p.vertices) for p in o.data.polygons]),
                        cent=np.array([[*(sum((vs[i] for i in p.vertices), Vector()) / len(p.vertices))] for p in o.data.polygons])))
    return out

def obj_export(obs, path):
    bpy.ops.object.select_all(action="DESELECT")
    for o in obs: o.select_set(True)
    bpy.context.view_layer.objects.active = obs[0]
    bpy.ops.wm.obj_export(filepath=path, export_selected_objects=True, export_materials=False, export_triangulated_mesh=True,
                          forward_axis="NEGATIVE_Z", up_axis="Y")

# vessels first: one joined object per family, exported, their parts kept as data for the checks
rng.seed(7)
VESSEL_PARTS, VESSEL_TRIS = {}, {}
for fam in FAMILIES:
    PARTS = []
    build_vessel(fam)
    VESSEL_PARTS[fam] = part_data(PARTS)
    VESSEL_TRIS[fam] = tris(PARTS)
    print("APO2 vessel %-8s parts %d tris %d" % (fam, len(PARTS), VESSEL_TRIS[fam]), flush=True)
    if EXPORT:
        for o in PARTS: o.select_set(True)
        bpy.ops.object.select_all(action="DESELECT")
        for o in PARTS: o.select_set(True)
        bpy.context.view_layer.objects.active = PARTS[0]
        bpy.ops.object.join(); jo = bpy.context.active_object; jo.name = "Vessel_" + fam
        obj_export([jo], os.path.join(OUTA, "Vessel_%s.obj" % fam))
        VESSEL_TRIS[fam] = tris([jo])
        bpy.data.objects.remove(jo)
    else:
        for o in PARTS: bpy.data.objects.remove(o)

PARTS = []
rng.seed(11); build_frame()
FRAME_PARTS = list(PARTS)
FRAME_TRIS = tris(FRAME_PARTS)
FRAME_DATA = part_data(FRAME_PARTS)
print("APO2 frame tris", FRAME_TRIS, "parts", len(FRAME_PARTS), flush=True)
if "--frame-only" in argv: sys.exit(0)
if EXPORT: obj_export(FRAME_PARTS, os.path.join(OUTA, "Apothecary.obj"))

# ---------- item templates ----------
def Rz(a): return Euler((0, 0, math.radians(a))).to_matrix()
def Rx(a): return Euler((math.radians(a), 0, 0)).to_matrix()
def Ry(a): return Euler((0, math.radians(a), 0)).to_matrix()

def lump_mesh():
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

V_CYL = math.pi * R_C ** 2 * H_C
TRI_PER_VESSEL = 6400
NMAX_ROD = 36                               # slender rods (needles) need more to show a heap
NMAX_THIN = 16                              # rods and flat kinds (needles, scales) show a deeper heap
NMAX = 14                                   # most copies in a full vessel: big, readable items, few of them                       # item triangles in one full vessel (32 vessels + the frame + the vessels stay under ~250k)
FILL_PACK = 0.30
TPL = {}
def tpl(name):
    """name: an item, '_generic' (heap lump) or '_ghang' (the same lump, hung)"""
    if name in TPL: return TPL[name]
    hang = APOTHECARY.get(name) == "hanging" or name == "_ghang"
    if name in ("_generic", "_ghang"): datas = [lump_mesh()]
    else:
        objs = [o for o in load_item(name, anchor="center") if o.type == "MESH"]
        datas = [o.data for o in objs]
        for o in objs: bpy.data.objects.remove(o)
    allv = np.array([v.co[:] for d in datas for v in d.vertices])
    mn, mx = allv.min(0), allv.max(0); c = (mn + mx) / 2
    for d in datas: d.transform(Matrix.Translation(-Vector(c)))
    verts = allv - c; size = mx - mn
    ntri = sum(len(p.vertices) - 2 for d in datas for p in d.polygons)
    bm = bmesh.new()
    for v in verts: bm.verts.new(v)
    res = bmesh.ops.convex_hull(bm, input=bm.verts[:])
    for g in res["geom_interior"] + res["geom_unused"]:
        if isinstance(g, bmesh.types.BMVert) and g.is_valid and not g.link_faces: bm.verts.remove(g)
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if f.is_valid])
    bm.normal_update(); bm.verts.index_update(); bm.verts.ensure_lookup_table()
    vol = abs(bm.calc_volume())
    used = sorted({v.index for f in bm.faces for v in f.verts}); remap = {o: n for n, o in enumerate(used)}
    hv = np.array([bm.verts[i].co[:] for i in used])
    F = np.array([[remap[v.index] for v in f.verts] for f in bm.faces])
    cen = hv.mean(0); N = []; D = []
    for f in bm.faces:
        n = np.array(f.normal[:]); d0 = n @ np.array(f.verts[0].co[:])
        if n @ cen > d0: n = -n; d0 = -d0
        N.append(n); D.append(d0)
    bm.free()
    il = int(np.argmax(size)); it = int(np.argmin(size))
    if it == il: it = (il + 1) % 3
    im = 3 - il - it
    A = np.zeros((3, 3)); A[:, il] = (1, 0, 0); A[:, im] = (0, 1, 0); A[:, it] = (0, 0, 1)
    if np.linalg.det(A) < 0: A[:, im] = (0, -1, 0)
    ss = np.sort(size)[::-1]
    rod_or_flat = ss[1] / ss[0] < 0.45 or ss[2] / ss[0] < 0.32
    cap = int(max(4, min(NMAX_ROD if ss[1] / ss[0] < 0.3 else (NMAX_THIN if rod_or_flat else NMAX), TRI_PER_VESSEL // max(ntri, 1))))
    ent = dict(datas=datas, verts=verts, size=size, A=A, tris=ntri, hv=hv, F=F, N=np.array(N), D=np.array(D), vol=vol, cap=cap, hang=hang)
    if hang:
        # long axis vertical (the narrower end up), the thin side along x (peg spacing 0.034), the mid side along y; the cross-section
        # limits keep the 7 hung copies apart and inside the clear cylinder
        s = min(0.20 / ss[0], 2 * 0.044 / max(ss[1], 1e-6), 0.068 / max(ss[2], 1e-6))
        u = verts[:, il]; span = u.max() - u.min()
        oth = [i for i in range(3) if i != il]
        wid = lambda sel: float(np.std(verts[sel][:, oth[0]]) + np.std(verts[sel][:, oth[1]])) if sel.sum() > 2 else 0.0
        sgn = 1.0 if wid(u > u.max() - 0.2 * span) <= wid(u < u.min() + 0.2 * span) else -1.0
        R0 = np.zeros((3, 3)); R0[0, im] = 1; R0[1, it] = 1; R0[2, il] = sgn      # the wide side faces the front (x), the thin one is the depth (y)
        if np.linalg.det(R0) < 0: R0[1, it] = -1
        ent.update(mode="hang", s=s, R0=R0, cap=len(PEGS))
    else:
        mode = "lie" if ss[2] / ss[0] < 0.32 and ss[1] / ss[0] >= 0.30 else "tumble"
        Lb = 0.088 if ss[1] / ss[0] >= 0.75 and mode == "tumble" else (0.130 if mode == "lie" else 0.150)
        s_fill = (FILL_PACK * V_CYL / (cap * vol)) ** (1 / 3)
        s = max(Lb / ss[0], s_fill) if name != "_generic" else Lb / ss[0]
        s = min(s, (0.150 if mode == "lie" else 0.19) / ss[0])
        ent.update(mode=mode, s=s)
    pm = bpy.data.meshes.new("prox_" + name)
    pm.from_pydata([tuple(v * ent["s"]) for v in hv], [], [tuple(int(i) for i in f) for f in F]); pm.update()
    ent["prox"] = pm
    TPL[name] = ent
    return ent

# ---------- the settle (r1's; one cylinder per kind side by side) ----------
CELL = 0.005
class HF:
    def __init__(self):
        self.n = 40; self.x0 = -0.1
        self.h = np.zeros((self.n, self.n))
        g = (np.arange(self.n) + 0.5) * CELL + self.x0
        self.X, self.Y = np.meshgrid(g, g, indexing="ij")
        self.mask = np.hypot(self.X, self.Y) <= R_C - 0.004
    def add(self, N, D, dilate=True):
        P = N[:, 0:1] * self.X.ravel()[None, :] + N[:, 1:2] * self.Y.ravel()[None, :]
        up = N[:, 2] > 1e-6; dn = N[:, 2] < -1e-6; ve = ~(up | dn)
        if not up.any() or not dn.any(): return
        zt = ((D[up, None] - P[up]) / N[up, 2][:, None]).min(0)
        zb = ((D[dn, None] - P[dn]) / N[dn, 2][:, None]).max(0)
        ok = zt > zb
        if ve.any(): ok &= (P[ve] <= D[ve, None]).all(0)
        zt = np.where(ok, zt, -9.0).reshape(self.n, self.n)
        if dilate:
            zp = np.pad(zt, 1, constant_values=-9.0)
            zt = np.max([zp[1 + di:1 + di + self.n, 1 + dj:1 + dj + self.n] for di in (-1, 0, 1) for dj in (-1, 0, 1)], axis=0)
        self.h = np.maximum(self.h, zt)
    def level(self): return float(self.h[self.mask].mean())

def drop_z(hf, h, N, D, lo, hi, x, y):
    dn = N[:, 2] < -1e-6; up = N[:, 2] > 1e-6
    i0 = max(0, int(math.floor((x + lo[0] - hf.x0) / CELL))); i1 = min(hf.n - 1, int(math.floor((x + hi[0] - hf.x0) / CELL)))
    j0 = max(0, int(math.floor((y + lo[1] - hf.x0) / CELL))); j1 = min(hf.n - 1, int(math.floor((y + hi[1] - hf.x0) / CELL)))
    I, J = np.meshgrid(np.arange(i0, i1 + 1), np.arange(j0, j1 + 1), indexing="ij")
    X = (I.ravel() + 0.5) * CELL + hf.x0 - x; Y = (J.ravel() + 0.5) * CELL + hf.x0 - y
    P = N[:, 0:1] * X[None, :] + N[:, 1:2] * Y[None, :]
    zb = ((D[dn, None] - P[dn]) / N[dn, 2][:, None]).max(0); zt = ((D[up, None] - P[up]) / N[up, 2][:, None]).min(0)
    ok = zt > zb
    if not ok.any(): return float(h[I.ravel(), J.ravel()].max()) - lo[2], (i0, i1, j0, j1), 0.0
    need = h[I.ravel()[ok], J.ravel()[ok]] - zb[ok]; rest = float(need.max())
    return rest, (i0, i1, j0, j1), float((need >= rest - 0.006).mean())

def rand_rot(rr):
    q = Quaternion([rr.gauss(0, 1) for _ in range(4)]); q.normalize(); return np.array(q.to_matrix())

GRID = 0.010
GXY = [(x, y) for x in np.arange(-R_C, R_C + 1e-9, GRID) for y in np.arange(-R_C, R_C + 1e-9, GRID) if math.hypot(x, y) <= R_C - 0.008]
def lowest_spot(st, h, rr):
    t = st["t"]; s = t["s"]; cands = []
    for _o in range(8):
        if t["mode"] == "lie": R = np.array(Rz(rr.uniform(0, 360)) @ Rx(rr.uniform(-15, 15)) @ Ry(rr.uniform(-15, 15))) @ t["A"]
        else: R = rand_rot(rr)
        HV = (t["hv"] * s) @ R.T; Nr = t["N"] @ R.T; Dr = t["D"] * s
        lo, hi = HV.min(0), HV.max(0); rc = float(np.hypot(HV[:, 0], HV[:, 1]).max())
        for x, y in GXY:
            if math.hypot(x, y) + rc > R_C - 0.005: continue
            rest, idx, sup = drop_z(st["hf"], h, Nr, Dr, lo, hi, x, y)
            z = rest + 0.006
            if z + hi[2] > H_C - 0.003 or sup < 0.12: continue
            P = HV + np.array((x, y, z))
            if not in_cyl(P, 0.005).all(): continue
            cands.append((round((z + lo[2]) / 0.005) + 2.0 * (1 - sup) - 1.5 * math.hypot(x, y) / R_C + rr.uniform(0, 0.6), R, np.array((x, y, z)), idx, hi))
    if not cands: return None
    cands.sort(key=lambda c: c[0])
    return cands[rr.randrange(min(3, len(cands)))]

COL_IN = 0.0025
def collider_slabs(ox):
    out = [(Matrix.Translation((ox, 0, -0.05)), (0.6, 0.6, 0.1))]
    n = 32; ri = R_C - COL_IN; T = 0.03; w = 2 * ri * math.tan(math.pi / n) * 1.08; Hh = H_C + 0.08
    for i in range(n):
        a = 2 * math.pi * (i + 0.5) / n
        M = Matrix.Rotation(a, 4, "Z"); M.translation = Vector((ox + (ri + T / 2) * math.cos(a), (ri + T / 2) * math.sin(a), Hh / 2))
        out.append((M, (T, w, Hh)))
    return out

def finish(s):
    s["done"] = True; n = len(s["frozen"])
    cut = [round(n * k / UNITS_PER) for k in range(UNITS_PER + 1)]
    for b in s["frozen"]: b["stack"] = max(k for k in range(UNITS_PER) if b["id"] >= cut[k])
    return n, cut

def settle(names, seed=5):
    rr = random.Random(seed)
    bpy.ops.rigidbody.world_add()
    rbw = sc.rigidbody_world
    sc.frame_start = 1; sc.frame_end = 600
    rbw.point_cache.frame_start = 1; rbw.point_cache.frame_end = 600
    rbw.substeps_per_frame = 20; rbw.solver_iterations = 40
    def set_rb(ob, typ, mass=1.0):
        with bpy.context.temp_override(object=ob, active_object=ob, selected_objects=[ob], selected_editable_objects=[ob]):
            bpy.ops.rigidbody.object_add(type=typ)
        rb = ob.rigid_body
        rb.friction = 0.6; rb.restitution = 0.0; rb.mass = mass
        rb.linear_damping = 0.5; rb.angular_damping = 0.95
        if typ == "ACTIVE":
            rb.use_deactivation = True; rb.deactivate_linear_velocity = 0.06; rb.deactivate_angular_velocity = 0.3
        return rb
    cube = bpy.data.meshes.new("slab"); bmc = bmesh.new(); bmesh.ops.create_cube(bmc, size=1.0); bmc.to_mesh(cube); bmc.free()
    ST = {}
    for i, name in enumerate(names):
        ox = 0.4 * i
        for M, dm in collider_slabs(ox):
            col = bpy.data.objects.new("col", cube); sc.collection.objects.link(col)
            col.matrix_world = M @ Matrix.Diagonal((dm[0], dm[1], dm[2], 1))
            rb = set_rb(col, "PASSIVE"); rb.collision_shape = "BOX"; rb.use_margin = True; rb.collision_margin = 0.0
        t = tpl(name)
        ST[name] = dict(t=t, ox=ox, hf=HF(), hfl=HF(), frozen=[], fails=0, done=False)
    stats = dict(attempts=0, frames=0, rejected=0)
    while not all(s["done"] for s in ST.values()):
        sc.frame_set(1); spawned = []
        for name, s in ST.items():
            if s["done"]: continue
            t = s["t"]; tmp = s["hf"].h.copy(); nb = 1 + (t["cap"] > 50) + (t["cap"] > 90) + (t["cap"] > 150); got = 0
            for _b in range(min(nb, t["cap"] - len(s["frozen"]))):
                best = lowest_spot(s, tmp, rr)
                if best is None: break
                _, R, c, (i0, i1, j0, j1), hi = best
                tmp[max(0, i0 - 3):i1 + 4, max(0, j0 - 3):j1 + 4] = H_C + 1
                ob = bpy.data.objects.new("b_" + name, t["prox"]); sc.collection.objects.link(ob)
                ob.matrix_world = Matrix.Translation(Vector(c + np.array((s["ox"], 0, 0)))) @ Matrix(R.tolist()).to_4x4()
                rb = set_rb(ob, "ACTIVE", max(0.02, t["vol"] * t["s"] ** 3 * 1500))
                rb.collision_shape = "CONVEX_HULL"; rb.mesh_source = "BASE"; rb.use_margin = True; rb.collision_margin = 0.001
                spawned.append((name, ob)); got += 1
            if not got: s["fails"] += 1
        stats["attempts"] += 1
        if spawned:
            bpy.context.view_layer.update(); prev = {}
            for f in range(2, 202):
                sc.frame_set(f); stats["frames"] += 1
                if f >= 14 and f % 3 == 0:
                    dg = bpy.context.evaluated_depsgraph_get(); mx = 0.0
                    for name, ob in spawned:
                        M = np.array(ob.evaluated_get(dg).matrix_world)
                        p = (ST[name]["t"]["hv"][:12] * ST[name]["t"]["s"]) @ M[:3, :3].T + M[:3, 3]
                        if ob.name in prev: mx = max(mx, float(np.abs(p - prev[ob.name]).max()))
                        prev[ob.name] = p
                    if mx < 4e-4 and f > 20: break
            dg = bpy.context.evaluated_depsgraph_get()
            res = [(name, ob, np.array(ob.evaluated_get(dg).matrix_world)) for name, ob in spawned]
            sc.frame_set(1)
            for name, ob, M in res:
                s = ST[name]; t = s["t"]; R = M[:3, :3]; c = M[:3, 3] - np.array((s["ox"], 0, 0))
                HV = (t["hv"] * t["s"]) @ R.T + c
                if in_cyl(HV).all():
                    ob.matrix_world = Matrix(M.tolist()); ob.rigid_body.type = "PASSIVE"
                    N = t["N"] @ R.T; D = t["D"] * t["s"] + N @ c
                    s["frozen"].append(dict(R=R, c=c, id=len(s["frozen"]), HV=HV, N=N, D=D))
                    s["hf"].add(N, D); s["hfl"].add(N, D, dilate=False); s["fails"] = 0
                else:
                    bpy.data.objects.remove(ob); s["fails"] += 1; stats["rejected"] += 1
        for name, s in ST.items():
            if s["done"]: continue
            if len(s["frozen"]) >= s["t"]["cap"] or s["fails"] >= 8:
                n, cut = finish(s)
                print("APO2 %-20s full: %2d copies (cap %d), scale %.3f, level %.3f, top %.3f, stacks %s" % (name, n, s["t"]["cap"], s["t"]["s"], s["hfl"].level(),
                      max(float(b["HV"][:, 2].max()) for b in s["frozen"]) if n else 0, [cut[k + 1] - cut[k] for k in range(UNITS_PER)]), flush=True)
    for o in [o for o in bpy.data.objects if o.rigid_body is not None]: bpy.data.objects.remove(o)
    bpy.ops.rigidbody.world_remove()
    sc.frame_set(1)
    return ST, stats

def hang_layout(name, seed):
    """the hanging parts: 2 pegs, one big bundle per stack; each copy hangs from its peg (its top 1.5 mm under the tip), long axis vertical,
    wide side to the front, a small turn; inside the gallows' room or the scale shrinks (by 7 % steps) until both fit; 2 stacks"""
    t = tpl(name); s0 = t["s"]
    for fac in (1.0, 0.93, 0.86, 0.80, 0.74, 0.68, 0.62):
        rr = random.Random(seed); s = s0 * fac; fr = []
        for k in range(t["cap"]):
            px, py = PEGS[PEG_ORDER[k]]
            for _try in range(16):
                R = np.array(Rz(rr.uniform(-8, 8) + rr.choice((0, 180)))) @ t["R0"]
                HVs = (t["hv"] * s) @ R.T
                zmax = float(HVs[:, 2].max()); top = HVs[HVs[:, 2] >= zmax - 0.1 * (zmax - HVs[:, 2].min())]
                c = np.array((px - top[:, 0].mean(), py - top[:, 1].mean(), (H_C - 0.0015) - zmax))
                HV = HVs + c
                if in_hang(HV).all():
                    N = t["N"] @ R.T; D = t["D"] * s + N @ c
                    fr.append(dict(R=R, c=c, id=len(fr), HV=HV, N=N, D=D)); break
        if len(fr) == t["cap"]: break
    t["s"] = s
    st = dict(t=t, ox=0.0, frozen=fr, fails=0, done=False, hang=True)
    n, cut = finish(st)
    print("APO2 %-20s hung: %2d copies (cap %d), scale %.3f (x%.2f), longest %.3f, stacks %s" % (name, n, t["cap"], s, fac, float(t["size"].max() * s), [cut[k + 1] - cut[k] for k in range(UNITS_PER)]), flush=True)
    return st

HEAP = [n for n in ITEMS if APOTHECARY[n] != "hanging"] + ["_generic"]
HUNG = [n for n in ITEMS if APOTHECARY[n] == "hanging"] + ["_ghang"]
ST, SIMST = settle(HEAP)
for i, n in enumerate(HUNG): ST[n] = hang_layout(n, 100 + i)
KINDS = [n for n in ITEMS] + ["_generic", "_ghang"]
print("APO2 SIM", SIMST, "%.0fs" % (time.time() - t0), flush=True)

# ---------- checks on the layouts ----------
def hull_bvh(b, t):
    return BVHTree.FromPolygons([Vector(v) for v in b["HV"]], [tuple(int(i) for i in f) for f in t["F"]])
def float_pen(name):
    s = ST[name]; t = s["t"]; fr = s["frozen"]; gaps = []; pen = 0.0
    for b in fr:
        P = b["HV"]; span = P[:, 2].max() - P[:, 2].min()
        low = P[P[:, 2] <= P[:, 2].min() + 0.35 * span + 1e-6]
        g = min(float(low[:, 2].min()), float((R_C - COL_IN - np.hypot(low[:, 0], low[:, 1])).min()))
        for q in fr[:b["id"]]:
            if (q["HV"].min(0) > P.max(0) + 0.02).any() or (q["HV"].max(0) < P.min(0) - 0.02).any(): continue
            d = q["D"][None, :] - P @ q["N"].T; ins = (d > 0).all(1)
            if ins.any(): pen = max(pen, float(d[ins].min(1).max())); g = 0.0; continue
            bv = hull_bvh(q, t)
            g = min(g, min(bv.find_nearest(Vector(p))[3] for p in low))
            bb = hull_bvh(b, t); Q = q["HV"][q["HV"][:, 2] >= q["HV"][:, 2].max() - 0.35 * (q["HV"][:, 2].max() - q["HV"][:, 2].min())]
            g = min(g, min(bb.find_nearest(Vector(p))[3] for p in Q))
        gaps.append(max(g, 0.0))
    return (max(gaps) if gaps else 0.0), pen

def hung_pen(name):
    """overlap between hung copies (hull vertices inside another's hull) and the gap from each copy's top to its peg tip"""
    fr = ST[name]["frozen"]; pen = 0.0
    for i, b in enumerate(fr):
        for q in fr[:i]:
            d = q["D"][None, :] - b["HV"] @ q["N"].T; ins = (d > 0).all(1)
            if ins.any(): pen = max(pen, float(d[ins].min(1).max()))
            d = b["D"][None, :] - q["HV"] @ b["N"].T; ins = (d > 0).all(1)
            if ins.any(): pen = max(pen, float(d[ins].min(1).max()))
    return pen

CHECK = {}
for name in KINDS:
    s = ST[name]; t = s["t"]; fr = s["frozen"]
    if s.get("hang"): fmax, pen = H_C - max([float(b["HV"][:, 2].max()) for b in fr] or [H_C]), hung_pen(name)
    else: fmax, pen = float_pen(name)
    P = np.vstack([(t["verts"] * t["s"]) @ b["R"].T + b["c"] for b in fr]) if fr else np.zeros((1, 3))
    lv = None
    if not s.get("hang"):
        hf = HF(); lv = []
        for k in range(UNITS_PER):
            for b in fr:
                if b["stack"] == k: hf.add(b["N"], b["D"], dilate=False)
            lv.append(round(hf.level(), 3))
    CHECK[name] = dict(copies=len(fr), copies_by_stack=[sum(1 for b in fr if b["stack"] == k) for k in range(UNITS_PER)], cap=t["cap"],
                       mesh_outside_cylinder_mm=round((outside_hang(P) if s.get("hang") else outside_cyl(P)) * 1000, 1), float_worst_mm=round(fmax * 1000, 2),
                       overlap_max_mm=round(pen * 1000, 2), level_by_stacks_m=lv, top_m=round(float(P[:, 2].max()), 3),
                       longest_m=round(float(t["size"].max() * t["s"]), 3), drawn_tris_per_copy=t["tris"], tris_full_vessel=len(fr) * t["tris"])
    print("APO2 CHECK %-20s %s" % (name, CHECK[name]), flush=True)

# ---------- clipping: copies/cylinder vs vessels, vessels vs frame, cylinder vs frame ----------
DRAYS = [Vector(d).normalized() for d in ((0.267, 0.534, 0.802), (-0.71, 0.31, -0.63), (0.45, -0.82, 0.36))]
def inside_part(bvh, p):
    odd = 0
    for dr in DRAYS:
        o = Vector(p); n = 0
        while n < 64:
            hit = bvh.ray_cast(o, dr)
            if hit[0] is None: break
            n += 1; o = hit[0] + dr * 1e-5
        odd += n % 2
    return odd >= 2

def count_inside(points, parts, slack=1e-4):
    """points (n, 3) inside any of the parts (closed solids); returns count and the first few part names"""
    PLO = np.array([p["lo"] for p in parts]); PHI = np.array([p["hi"] for p in parts]); hits = 0; notes = []
    for q in points:
        for c in np.where(((q >= PLO - slack) & (q <= PHI + slack)).all(1))[0]:
            if inside_part(parts[c]["bvh"], q): hits += 1; notes.append(parts[c]["name"]); break
    return hits, notes

cs = []
RS, Z0, Z1 = R_C - 0.001, 0.001, H_C - 0.001
for z in np.arange(Z0, Z1 + 1e-9, 0.01):
    for a in np.arange(0, 2 * math.pi, 0.01 / R_C): cs.append((RS * math.cos(a), RS * math.sin(a), z))
for x in np.arange(-RS, RS + 1e-9, 0.02):
    for y in np.arange(-RS, RS + 1e-9, 0.02):
        if math.hypot(x, y) <= RS:
            for z in (Z0, Z1) + tuple(np.arange(0.02, H_C, 0.04)): cs.append((x, y, z))
CS = np.array(cs)                                               # relative to the floor centre (shelf surface + TB)
FLOORS = [np.array(place_origin(n)) + np.array((0, 0, TB)) for n in range(NPLACE)]

# (a) the clear cylinder against each vessel (local coordinates): 0 points inside a vessel part
VES_CYL = {}
for fam in FAMILIES:
    h, notes = count_inside(CS + np.array((0, 0, TB)), VESSEL_PARTS[fam]); VES_CYL[fam] = h
    print("APO2 cylinder vs vessel %-8s: %d of %d points inside %s" % (fam, h, len(CS), notes[:4]), flush=True)
# (b) every copy (all its vertices) inside the clear cylinder, i.e. clear of every vessel (a) -> the max over all layouts
COPY_OUT = max(CHECK[n]["mesh_outside_cylinder_mm"] for n in KINDS)      # <= 0: inside the cylinder (hung parts: inside the gallows' room)
HANG_VES = {}
for n in KINDS:
    if ST[n].get("hang"):
        P = np.vstack([(ST[n]["t"]["verts"] * ST[n]["t"]["s"]) @ b["R"].T + b["c"] for b in ST[n]["frozen"]]) + np.array((0, 0, TB))
        HANG_VES[n], _nt = count_inside(P, VESSEL_PARTS["hanging"])
        print("APO2 hung %-20s mesh points inside the gallows: %d of %d" % (n, HANG_VES[n], len(P)), flush=True)
# (c) the vessels against the frame at every place (vessel points above the foot, 3 mm up) and the cylinders against the frame
FV = np.vstack([p["V"] for p in FRAME_DATA])
ves_frame = {}; cyl_frame = 0; cyl_notes = []; fv_in = 0
for n in range(NPLACE):
    org = np.array(place_origin(n))
    for fam in FAMILIES:
        pts = np.vstack([np.vstack([p["V"], p["cent"]]) for p in VESSEL_PARTS[fam]]) + org
        pts = pts[pts[:, 2] > org[2] + 0.003]
        h, notes = count_inside(pts, FRAME_DATA)
        ves_frame[(n, fam)] = h
        if h: print("APO2 vessel %s at place %d inside frame: %d %s" % (fam, n, h, notes[:3]), flush=True)
    h, notes = count_inside(CS + FLOORS[n], FRAME_DATA); cyl_frame += h; cyl_notes += notes
    Q = FV - FLOORS[n]; hit = in_cyl(Q, 0.001) & (Q[:, 2] > 0.001); fv_in += int(hit.sum())
VES_FRAME = sum(ves_frame.values())
print("APO2 vessels vs frame: %d vessel points inside frame parts (%d vessel x place combinations); cylinders vs frame: %d points %s, frame vertices in a cylinder %d" %
      (VES_FRAME, len(ves_frame), cyl_frame, cyl_notes[:3], fv_in), flush=True)
# (d) neighbours: the widest vessel radius against the 0.25 m pitch
RMAX = {f: max(float(np.hypot(p["V"][:, 0], p["V"][:, 1]).max()) for p in VESSEL_PARTS[f]) for f in FAMILIES}
print("APO2 vessel radii", {k: round(v, 3) for k, v in RMAX.items()}, "pitch", PITCH, "widest pair", round(max(RMAX.values()) * 2, 3), flush=True)
# (e) the vessels' x extent (hanging bars) is in x; the gallows is the widest in x, the others round
XEXT = {f: round(max(float(np.abs(p["V"][:, 0]).max()) for p in VESSEL_PARTS[f]), 3) for f in FAMILIES}
print("APO2 vessel x half-extent", XEXT, flush=True)

# ---------- export ----------
MC = Matrix(((-1, 0, 0), (0, 0, 1), (0, -1, 0)))
def uvec(v): return [round(-float(v[0]), 4), round(float(v[2]), 4), round(-float(v[1]), 4)]
def uquat(Rb):
    q = (MC @ Matrix(Rb.tolist()) @ MC.transposed()).to_quaternion(); q.normalize()
    if q.w < 0: q = -q
    return [round(c, 5) for c in (q.x, q.y, q.z, q.w)]
rt = 0.0
layouts = {}
for name in KINDS:
    s = ST[name]; t = s["t"]
    stacks = [[{"offset": uvec(b["c"]), "rot_quat_xyzw": uquat(b["R"])} for b in s["frozen"] if b["stack"] == k] for k in range(UNITS_PER)]
    for b in s["frozen"]:
        qx, qy, qz, qw = uquat(b["R"]); Rb = MC.transposed() @ Quaternion((qw, qx, qy, qz)).to_matrix() @ MC
        rt = max(rt, float(np.abs(np.array(Rb) - b["R"]).max()))
    sz = t["size"]
    ent = {"family": APOTHECARY.get(name, "hanging" if name == "_ghang" else "jar/crock/basket"), "mode": "hang" if t["hang"] else t["mode"],
           "scale": round(t["s"], 5), "true_size_m": [round(float(sz[0]), 4), round(float(sz[2]), 4), round(float(sz[1]), 4)],
           "copies_per_stack": round(len(s["frozen"]) / UNITS_PER, 2), "copies_by_stack": [len(x) for x in stacks], "stacks": stacks, "check": CHECK[name]}
    if name in ("_generic", "_ghang"):
        ent["scale"] = None; ent["fit_longest_m"] = round(float(sz.max() * t["s"]), 4); ent["true_size_m"] = None
        ent["note"] = ("fallback for any item without its own layout in a %s: a neutral round lump, scaled uniformly so its longest bounds side is fit_longest_m."
                       % ("hanging vessel (hung from the pegs)" if name == "_ghang" else "jar, crock or basket (settled heap)"))
    layouts[name] = ent
GEN = {"hanging": layouts["_ghang"], "jar": layouts["_generic"], "crock": layouts["_generic"], "basket": layouts["_generic"]}
ITEM_FAMILY = {k: v for k, v in APOTHECARY.items() if k in ITEMS}
units = []
for n in range(NPLACE):
    cen = FLOORS[n] + np.array((0, 0, H_C / 2)); r, c = divmod(n, NCOL)
    for fam in FAMILIES:
        for k in range(UNITS_PER):
            g = GEN[fam]
            units.append({"index": len(units), "bin": n, "place": n, "kind": fam, "vessel": fam, "tier": r, "col": c, "fill_step": k, "position": uvec(cen),
                          "rotation": [0, 0, 0], "box": [round(2 * R_C, 4), round(H_C, 4), round(2 * R_C, 4)],
                          "copies": [{"offset": [round(cp["offset"][0], 4), round(cp["offset"][1] - H_C / 2, 4), round(cp["offset"][2], 4)],
                                      "rot_quat_xyzw": cp["rot_quat_xyzw"], "fit_longest_m": g["fit_longest_m"]} for cp in g["stacks"][k]]})
# the liquids: a closed 16-sided prism of height 1 (z 0..1) per place x liquid, on the jar's own angles, 5 mm inside the jar's narrowest inside
jprof = VESSEL_PROF["jar"]["prof"]; jt = VESSEL_PROF["jar"]["t"]
LIQ_R = min(float(np.interp(z, [p[1] for p in jprof], [p[0] for p in jprof])) - jt for z in np.linspace(TB, TB + H_C, 40)) - 0.005
LIQ_FLOOR = TB + 0.001
LIQ_TOP = TB + H_C - 0.005
def liquid_mesh(it, nm):
    bm = bmesh.new(); uvl = bm.loops.layers.uv.verify()
    li = LIQUIDS.index(it)
    ang = [2 * math.pi * i / SEG for i in range(SEG)]
    bot = [bm.verts.new((LIQ_R * math.cos(a), LIQ_R * math.sin(a), 0.0)) for a in ang]
    top = [bm.verts.new((LIQ_R * math.cos(a), LIQ_R * math.sin(a), 1.0)) for a in ang]
    tuv = lambda x0, w, px, py: ((x0 + px) / TEX, (8 + py) / TEX)
    for i in range(SEG):
        j = (i + 1) % SEG
        f = bm.faces.new((bot[i], bot[j], top[j], top[i]))
        u0 = 0.5 + (i % 3) * 5
        for l, (pu, pv) in zip(f.loops, ((u0, 0.5), (u0 + 5, 0.5), (u0 + 5, 7.5), (u0, 7.5))): l[uvl].uv = tuv(24 * li, 16, pu, pv)
    f = bm.faces.new(top)
    for l, v in zip(f.loops, top): l[uvl].uv = tuv(24 * li + 16, 8, 4 + v.co.x * DENS * 0.15, 4 + v.co.y * DENS * 0.15)
    f = bm.faces.new(bot[::-1])
    for l in f.loops: l[uvl].uv = tuv(24 * li, 16, 8, 4)
    bm.normal_update()
    me = bpy.data.meshes.new(nm); bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = False
    ob = bpy.data.objects.new(nm, me); sc.collection.objects.link(ob); ob.data.materials.append(MAT)
    return ob
liquids = []
for n in range(NPLACE):
    org = np.array(place_origin(n))
    for it in LIQUIDS:
        if it not in ITEMS: continue
        nm = "Liquid_%d_%s" % (n, it)
        if EXPORT:
            lo_ = liquid_mesh(it, nm); obj_export([lo_], os.path.join(OUTA, nm + ".obj")); bpy.data.objects.remove(lo_)
        liquids.append({"position": n, "item": it, "obj": nm + ".obj", "floor": uvec(org + np.array((0, 0, LIQ_FLOOR))),
                        "top_y": round(float(org[2] + LIQ_TOP), 4), "radius": round(LIQ_R, 4), "sides": SEG})
vessels = [{"position": n, "at": uvec(place_origin(n)), "default": DEFAULT[n]} for n in range(NPLACE)]
heaviest = max(ITEMS, key=lambda n: CHECK[n]["tris_full_vessel"])
worst_vessel = max(VESSEL_TRIS.values())
doc = {
    "store": "Apothecary Rack round 2 (blender/apothecary_r2.py): the vessel follows the item",
    "rule": "small things a creature leaves behind that you can't eat or wear; one kind per vessel, the vessel is the item's family (hanging, jar, crock, basket)",
    "items": ITEMS, "item_family": ITEM_FAMILY, "families": FAMILIES,
    "slots": 64, "places": NPLACE, "grid": [NCOL, len(LEVEL)], "stacks_per_place_and_family": UNITS_PER, "stack_per_unit": 1, "placement": "wall",
    "frame": {"obj": "Apothecary.obj", "tris": FRAME_TRIS, "size_m": [W, H, DEPTH], "atlas": "apothecary_atlas.png 128x128 point",
              "atlas_rows": "v px from the bottom: 96-127 hewn, 64-95 end grain, 48-63 iron (byte-identical from bunker_r4), 36-47 clay, 24-35 wicker, 16-23 glass, 8-15 liquid tiles (RoyalJelly: side x 0-15 / top x 16-23; Ectoplasm: side x 24-39 / top x 40-47), 4-7 cord, 0-3 swatches cork/ivory/amber/pupil/feather/bright glass/worn timber/soot"},
    "space": "Unity prefab space, metres. Origin: the wall plane (back face, z = 0), x centred, y = 0 the foot; front is +z. Blender z-up/-y front -> Unity: ux=-bx, uy=bz, uz=-by. OBJ exported forward -Z, up Y (the mod loads it flipX).",
    "vessel_meshes": {f: "Vessel_%s.obj" % f for f in FAMILIES},
    "vessel_meshes_doc": ("one mesh per family in the same OBJ convention as the frame, in local coordinates: origin = the centre of the vessel's footprint at the shelf "
                          "surface (vessels[].at); draw it at 'at' (no rotation) with the frame's material. Tris: %s." % ", ".join("%s %d" % (f, VESSEL_TRIS[f]) for f in FAMILIES)),
    "vessels": vessels,
    "vessels_doc": ("one entry per place: 'at' = where its vessel stands (prefab space), 'default' = the family drawn while the place is empty (a mix: every row and "
                    "column has all four). A place holding an item draws the vessel of the item's family (item_family) instead: the vessel follows the item. "
                    "place n = tier * 8 + column; tier 0 is the top, column 0 the left as seen from the front (Blender x ascending, Unity x descending)."),
    "groups": ("place 0..31 = one vessel position (key 'bin' in units_list, which the mod already reads as the group; 'place' repeats it). EVERY place has units for EVERY "
               "family: kind = hanging | jar | crock | basket, %d stacks (fill_step 0..%d) each, same position and box in all four. The clear space of every vessel of every "
               "family is the same upright cylinder (radius %.3f, height %.3f) standing on crate_floor_centres[place]." % (UNITS_PER, UNITS_PER - 1, R_C, H_C)),
    "crate_floor_centres": [uvec(fc) for fc in FLOORS],
    "crop_layouts": layouts,
    "crop_layouts_doc": ("crop_layouts: one full vessel per item kind, as the Produce Crates (rootbin_r6) and apothecary r1; '_generic' (any other item in a jar, crock or "
                         "basket) and '_ghang' (any other item in a hanging vessel). A place holding n stacks of a kind shows stacks[0..n-1] of that kind's layout "
                         "(%d stacks). Per copy: the item's model scaled uniformly by 'scale' (x its true size), turned by rot_quat_xyzw about its bounds centre, that centre "
                         "at crate_floor_centres[place] + offset. mode 'heap'/'lie'/'tumble': physics-settled (stack k dropped onto stacks 0..k-1); mode 'hang': hung "
                         "from the vessel's two pegs (long axis vertical, wide side to the front, top 1.5 mm under the peg tip at the top of the clear space; one big "
                         "bundle per stack, left peg first), inside the gallows' room |x| <= %.3f, |y| <= %.3f. Every layout fits its vessel, so it fits every place of its family." % (UNITS_PER, HANG_X, HANG_Y)),
    "liquids": liquids,
    "liquids_doc": ("one entry per (place, liquid item) for the two semi-liquids in a jar (RoyalJelly: pale translucent gold; Ectoplasm: pale ghostly green-white): obj = a "
                    "closed 16-sided prism of height 1 (y 0..1) in this folder, drawn with the frame's material as T(floor) * S(1, (top_y - floor.y) * fill, 1), fill = "
                    "stacks / %d; floor = bottom centre (prefab space), top_y = its surface when full; radius %.3f = the jar's narrowest inside minus 5 mm. An item "
                    "with an entry for its place is drawn as this column, in the place's jar; crop_layouts still has the item's lumps as the fallback." % (UNITS_PER, LIQ_R)),
    "unit_semantics": ("units_list: one unit = one stack, %d per place and family in fill order; kind = the family; copies = the generic lump of that family (a heap for jar/"
                       "crock/basket, hung from the pegs for hanging) as Fit.Longest copies (centre at position + offset), a fallback only." % UNITS_PER),
    "physics": ("heaps: Blender rigid body (Bullet), each copy the convex hull of its item, friction 0.6, restitution 0, damping 0.5/0.95, margin 1 mm, substeps 20, iterations 40, "
                "in the cylinder made of passive box slabs; one copy per kind per drop at one of the three lowest well-supported spots of a 1 cm grid x 8 orientations, "
                "settled, checked inside the cylinder, then frozen; until no copy fits or the kind's cap (~%d item triangles per vessel). Hanging: by hand." % TRI_PER_VESSEL),
    "checks": {"copies_outside_cylinder_mm_max": COPY_OUT, "cylinder_points_inside_vessel": VES_CYL, "hung_mesh_points_inside_gallows": HANG_VES, "cylinder_points_per_vessel": len(CS),
               "vessel_points_inside_frame": VES_FRAME, "vessel_places_checked": len(ves_frame), "cylinder_points_inside_frame": cyl_frame,
               "frame_vertices_inside_cylinders": fv_in, "vessel_radius_m": {k: round(v, 3) for k, v in RMAX.items()}, "pitch_m": PITCH,
               "rotation_roundtrip_max_err": rt, "sim": SIMST},
    "tris": {"frame": FRAME_TRIS, "vessels": VESSEL_TRIS,
             "full_store_worst_kind": {"item": heaviest, "tris": NPLACE * (CHECK[heaviest]["tris_full_vessel"] + VESSEL_TRIS[APOTHECARY[heaviest]]) + FRAME_TRIS},
             "full_store_worst_case_any_family": NPLACE * (max(CHECK[n]["tris_full_vessel"] for n in ITEMS) + worst_vessel) + FRAME_TRIS},
    "units_list": units,
}
if EXPORT:
    out = os.path.join(OUTA, "apothecary_anchors.json"); tmp = out + ".tmp"
    with open(tmp, "w") as fh: json.dump(doc, fh, indent=1)
    os.replace(tmp, out)
    print("APO2 wrote", out, flush=True)
print("APO2 STATS frame %d, vessels %s, copies %d, worst full store %s, roundtrip %.2g" % (FRAME_TRIS, VESSEL_TRIS, sum(c["copies"] for c in CHECK.values()), doc["tris"], rt), flush=True)

# ---------- renders ----------
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
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0.3, 1.5)); wall = bpy.context.active_object; wall.scale = (24, 0.6, 3.0)
    wm = bpy.data.materials.new("wall"); wm.use_nodes = True
    wm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.30, 0.29, 0.27, 1); wall.data.materials.append(wm)
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam); sc.camera = cam
    cam.data.lens = 38
    sc.render.engine = "BLENDER_EEVEE_NEXT"
    sc.view_settings.view_transform = "Standard"
    def look(yaw, pitch, dist, tgt):
        t = Vector(tgt)
        d = Vector((math.cos(math.radians(pitch)) * math.sin(math.radians(yaw)),
                    -math.cos(math.radians(pitch)) * math.cos(math.radians(yaw)), math.sin(math.radians(pitch))))
        cam.location = t + d * dist; cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    def render(fn, rx=1600, ry=1000):
        sc.render.resolution_x, sc.render.resolution_y = rx, ry
        sc.render.filepath = os.path.join(OUT, fn); bpy.ops.render.render(write_still=True); return sc.render.filepath
    def import_obj(path):
        before = set(bpy.data.objects)
        bpy.ops.wm.obj_import(filepath=path, forward_axis="NEGATIVE_Z", up_axis="Y")
        return [o for o in bpy.data.objects if o not in before]
    # the shipped files, re-imported: the vessels and the liquid prisms (the frame stays the in-scene one, exported from the same parts)
    PROTO = {}
    for fam in FAMILIES:
        obs = import_obj(os.path.join(OUTA, "Vessel_%s.obj" % fam)) if EXPORT else []
        for o in obs:
            o.data.materials.clear(); o.data.materials.append(MAT); o.hide_render = True; o.hide_viewport = True
        PROTO[fam] = obs
    LIQPROTO = {}
    for it in LIQUIDS:
        if it in ITEMS and EXPORT:
            obs = import_obj(os.path.join(OUTA, "Liquid_0_%s.obj" % it)); lo_ = obs[0]
            bpy.ops.object.select_all(action="DESELECT"); lo_.select_set(True); bpy.context.view_layer.objects.active = lo_
            bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
            lo_.data.materials.clear(); lo_.data.materials.append(MAT); lo_.hide_render = True; lo_.hide_viewport = True
            LIQPROTO[it] = lo_
    shown = []
    FRAMEOFF = Vector((0, 0, 0))
    def put_vessel(fam, org):
        for o in PROTO[fam]:
            c = o.copy(); sc.collection.objects.link(c); c.hide_render = False; c.hide_viewport = False
            c.location = org; shown.append(c)
    def put_item(name, nstacks, org, ofs):
        t = ST[name]["t"]
        for b in ST[name]["frozen"]:
            if b["stack"] >= nstacks: continue
            M = np.eye(4); M[:3, :3] = b["R"] * t["s"]; M[:3, 3] = b["c"] + np.array(org + Vector((0, 0, TB))) + np.array(ofs)
            for dta in t["datas"]:
                io = bpy.data.objects.new(name, dta); sc.collection.objects.link(io); io.matrix_world = Matrix(M.tolist()); shown.append(io)
    def fill(assign, ofs=(0, 0, 0)):
        """assign[n] = (item or None, stacks): the vessel follows the item; None: the default family, empty"""
        for n in range(NPLACE):
            item, k = assign[n] if n < len(assign) else (None, 0)
            org = place_origin(n) + Vector(ofs)
            if item is None or item not in ST:
                put_vessel(DEFAULT[n], org); continue
            put_vessel(APOTHECARY[item], org)
            if item in LIQPROTO:
                c = LIQPROTO[item].copy(); sc.collection.objects.link(c); c.hide_render = False; c.hide_viewport = False
                c.location = org + Vector((0, 0, LIQ_FLOOR)); c.scale = (1, 1, (LIQ_TOP - LIQ_FLOOR) * k / UNITS_PER); shown.append(c)
            else:
                put_item(item, k, org, ofs=(0, 0, 0))
    def clear():
        for o in shown: bpy.data.objects.remove(o)
        shown.clear()
    prng = random.Random(5)
    spots = list(range(NPLACE)); prng.shuffle(spots)
    ALL = [(None, 0)] * NPLACE
    for i, it in enumerate(ITEMS): ALL[spots[i]] = (it, UNITS_PER)
    HALF = [(it, 1 if it else 0) for it, _k in ALL]
    NEEDLES = [("Needle", UNITS_PER) if "Needle" in ST else (None, 0)] * NPLACE
    V34 = (-26, 8, 6.9, (0, -0.2, 1.0))
    look(*V34); fill([]); render("apothecary2-empty.png"); clear()
    fill(HALF); render("apothecary2-50.png"); clear()
    fill(ALL); render("apothecary2-full-24kinds.png")
    look(-4, 4, 6.0, (0, -0.24, 1.0)); render("apothecary2-full-24kinds-front.png")
    for tier, nm in ((0, "top"), (1, "upper"), (2, "lower"), (3, "floor")):
        look(-14, 12, 3.4, (0, -0.25, LEVEL[tier] + 0.15)); render("apothecary2-closeup-tier%d-%s.png" % (tier, nm))
    clear()
    fill(NEEDLES); look(*V34); render("apothecary2-full-needles-only.png")
    look(-10, 12, 3.8, (0, -0.25, 0.9)); render("apothecary2-full-needles-closeup.png"); clear()
    # one of each family full, beside its empty twin, close: (jar+jelly, ectoplasm, hanging, crock, basket)
    DEMO = [(None, 0)] * NPLACE
    row = [("Feathers", 2), ("GreydwarfEye", 2), ("Needle", 2), ("Chitin", 2), ("RoyalJelly", 2), ("Ectoplasm", 1), ("WolfHairBundle", 1), ("BjornPaw", 1)]
    for c, (it, k) in enumerate(row):
        if it in ST: DEMO[8 + c] = (it, k)
    fill(DEMO); look(-8, 10, 3.1, (0, -0.25, LEVEL[1] + 0.15)); render("apothecary2-closeup-families.png")
    bpy.ops.mesh.primitive_cube_add(size=1, location=(1.95, -0.3, 0.9)); post = bpy.context.active_object; post.scale = (0.1, 0.1, 1.8)
    pm = bpy.data.materials.new("post"); pm.use_nodes = True
    pm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.85, 0.85, 0.88, 1); post.data.materials.append(pm)
    clear(); fill(ALL); look(-8, 5, 6.6, (0.3, -0.2, 1.0)); render("apothecary2-post-1.8m.png")
    bpy.data.objects.remove(post)
    # beside apothecary r1 (as shipped) and bunker_r4 (as shipped), same scale, same ground
    r1 = import_obj(os.path.join(R1DIR, "ApothecaryRack.obj"))
    r1m = bpy.data.materials.new("r1"); r1m.use_nodes = True
    r1t = r1m.node_tree.nodes.new("ShaderNodeTexImage"); r1t.image = bpy.data.images.load(os.path.join(R1DIR, "apothecary_atlas.png")); r1t.interpolation = "Closest"
    r1m.node_tree.links.new(r1t.outputs["Color"], r1m.node_tree.nodes["Principled BSDF"].inputs["Base Color"])
    r1m.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.8
    for o in r1: o.data.materials.clear(); o.data.materials.append(r1m); o.location = (-3.9, 0, 0)
    bk = import_obj(os.path.join(BUNKER, "Bunker.obj"))
    bmat = bpy.data.materials.new("bunker"); bmat.use_nodes = True
    bt = bmat.node_tree.nodes.new("ShaderNodeTexImage"); bt.image = bpy.data.images.load(os.path.join(BUNKER, "bunker_atlas.png")); bt.interpolation = "Closest"
    bmat.node_tree.links.new(bt.outputs["Color"], bmat.node_tree.nodes["Principled BSDF"].inputs["Base Color"])
    bmat.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.8
    for o in bk: o.data.materials.clear(); o.data.materials.append(bmat); o.location = (4.5, -1.12, 0)
    look(-8, 8, 13.6, (0.9, -0.5, 0.95)); render("apothecary2-beside-r1-bunker_r4.png", 2000, 900)
    clear(); fill([]); render("apothecary2-beside-r1-bunker_r4-empty.png", 2000, 900)
print("DONE %.0fs" % (time.time() - t0))
