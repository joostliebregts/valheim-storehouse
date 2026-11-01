"""Pantry Dresser round 1 (Joost, 24 Oct): a NEW store beside the others (ITEMS.md section 2, #2): "what you cook with". A tall timber dresser, 2.16 W x 0.46 D x 2.14 H,
40 places in 5 tiers of 8, 80 slots (40 places x 2 stacks), 32 kinds, the vessel follows the item (r2's method, SPEC.md "What lies where": every kind its own place,
never mixed; full looks full; mass storage). The SAME schema as apothecary_r2 / apothecarytall_r1 (vessel_meshes, vessels with "at" and "default", units per place and
family with "bin"/"place" and "kind" = family, crate_floor_centres, crop_layouts per item), so the mod loads it unchanged.
  jar    Spice (Forests, Plains, Mountains, Oceans, Mistlands, Deep North, Ashlands)       glass jar, open at the front, cork: the spice pouches show
  tray   Bread dough, Fragrant bundle, the 12 uncooked dishes                              round tin baking tray with a rolled rim; dough and dishes lie on it
  crock  the 9 Feast ingredients (Meadows, Black Forest, Swamps, Mountains, Plains, Oceans, Deep North, Mistlands, Ashlands)     bellied clay crock with a cord
  sack   Barley flour, Oat flour                                                           squat hessian sack with a rolled cuff and a cord
Never two kinds in one vessel. Light on top, heavy below: the mod claims places in reading order, families jar, tray, crock, sack (tier 0 = top), each kind by name;
the full render and the defaults follow that: tier 0 jars (7 kinds on 8 places), tiers 1-2 trays (14 kinds on 16), tiers 3-4 crocks (9 kinds on 12) and sacks (2 on 4).
Empty places stand empty (the mod draws nothing there); "default" only says which family a place is for.
Units: every place has 2 stacks for EVERY family (the mod's perPlace logic keys on (place, family)): 40 x 4 x 2 = 320 units, 80 per family, so any one family can show all
80 slots; a place holding fewer than 2 stacks shows a vessel that is only partly full.
Run: "C:/Program Files/Blender Foundation/Blender 4.5/blender.exe" -b -P pantry_r1.py -- [--out DIR] [--no-render] [--quick] [--no-export]

Dimensions: Blender x, y, z; -y = front, back face y = 0 at the wall, x centred, z = 0 the foot. Tiers (shelf tops) at 1.63, 1.25, 0.87, 0.49, 0.11 m; places 0.24 m apart
(x = -0.84 ... 0.84), vessel centre y = -0.25. n = tier * 8 + column, tier 0 the top, column 0 the left as seen from the front (Blender x ascending, Unity x descending).
Every vessel has the SAME clear space: an upright cylinder R_C 0.090 x H_C 0.22 on a floor at origin + 0.02 (= crate_floor_centres[place]); items are settled once per kind
(rigid body, convex hulls, split in 2 stacks) and fit every place of the family. Vessels are at most 0.116 in radius (24 cm pitch), at most 0.31 high (the shelf above is 0.33 up).

THE ITEM MODELS: the 32 kinds are Valheim 1.0 items that are NOT in the model rip (C:/Users/joost/ValheimRip/items has 160 older items). Until they are ripped each kind is
built from a stand-in: a ripped cooked dish where one exists (LoxPie, MeatPlatter, FishAndBread, HoneyGlazedChicken) or a small procedural proxy (flour bag, spice pouch,
dough, herb bundle, produce cluster, pie, pancake, cupcake, leaf pile, stuffed mushroom), tinted per kind. The layouts therefore carry fit_longest_m (the final longest side,
which the mod scales the real prefab to) and "scale": null for every stand-in; rotations are relative to the stand-in's axes. When a kind's real model lands in the rip
(items/<Prefab>/), re-running this script uses it automatically and writes the real scale. The vessels, frame, places, units and counts do not depend on this.

Atlas 128 x 128 (point filtered, 48 px/m): bunker_r4's timber, end grain and iron rows byte-identical; clay, glass, cord and swatches as apothecary_r2; rows 8-11 hold the
hessian tile (sacks), rows 12-15 the tin tile (trays); swatches cork/ivory/amber/crust/flour/bright glass/worn timber/soot.
Files (assets/pantry_r1/): Pantry.obj (frame only), Vessel_{jar,tray,crock,sack}.obj (local coordinates, origin = centre of the footprint at the shelf surface),
pantry_atlas.png, pantry_anchors.json (last, temp + rename). Unity prefab space: ux = -bx, uy = bz, uz = -by (OBJ exported forward -Z, up Y, like every store).
"""
import bpy, bmesh, sys, os, math, json, random, time, zlib
import numpy as np
from mathutils import Vector, Matrix, Euler, Quaternion
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, ".."))
OUTA = os.path.join(REPO, "assets", "pantry_r1")
BUNKER = os.path.join(REPO, "assets", "bunker_r4")
R2DIR = os.path.join(REPO, "assets", "apothecary_r2")
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
def arg(k, d=None): return argv[argv.index(k) + 1] if k in argv else d
OUT = arg("--out", "C:/Users/joost/AppData/Local/Temp/claude/C--Users-joost--pai/5e4bc60b-cdfe-4638-8e29-2e507fa13cf9/scratchpad/pantry_r1")
RENDER = "--no-render" not in argv
QUICK = "--quick" in argv
EXPORT = "--no-export" not in argv
ITEMS_DIR = "C:/Users/joost/ValheimRip/items"
sys.path.append(ITEMS_DIR)
from load_item import load_item
OUTA = arg("--assets", OUTA)
os.makedirs(OUTA, exist_ok=True); os.makedirs(OUT, exist_ok=True)

PANTRY = {   # item -> family (what Storehouse.cs would carry for this store)
    "SpiceForests": "jar", "SpicePlains": "jar", "SpiceMountains": "jar", "SpiceOceans": "jar", "SpiceMistlands": "jar", "SpiceDeepNorth": "jar", "SpiceAshlands": "jar",
    "BreadDough": "tray", "FragrantBundle": "tray",
    "BakedPoteitrUncooked": "tray", "FishAndBreadUncooked": "tray", "HoneyGlazedChickenUncooked": "tray", "KaleChipsUncooked": "tray", "LoxPieUncooked": "tray",
    "MagicallyStuffedShroomUncooked": "tray", "MeatPlatterUncooked": "tray", "MisthareSupremeUncooked": "tray", "OvenPancakeUncooked": "tray",
    "PiquantPieUncooked": "tray", "RoastedCrustPieUncooked": "tray", "VikingCupcakeUncooked": "tray",
    "FeastAshlands_Material": "crock", "FeastBlackforest_Material": "crock", "FeastDeepNorth_Material": "crock", "FeastMeadows_Material": "crock",
    "FeastMistlands_Material": "crock", "FeastMountains_Material": "crock", "FeastOceans_Material": "crock", "FeastPlains_Material": "crock", "FeastSwamps_Material": "crock",
    "BarleyFlour": "sack", "OatFlour": "sack",
}
ITEMS = list(PANTRY)
FAMILIES = ["jar", "tray", "crock", "sack"]            # the order the mod claims places in: light on top, heavy below
LIQUIDS = []
if QUICK: ITEMS = ["SpiceForests", "SpicePlains", "BreadDough", "LoxPieUncooked", "PiquantPieUncooked", "VikingCupcakeUncooked", "FeastMeadows_Material", "FeastOceans_Material", "BarleyFlour"]
PANTRY = {k: v for k, v in PANTRY.items() if k in ITEMS}

rng = random.Random(7)
TEX = 128
DENS = 48.0
STRIP = {"hewn": 0.75, "end": 0.50, "iron": 0.375}
STRIPH = {"hewn": 32, "iron": 16}
ROWS = {"clay": (36, 12), "glass": (16, 8), "rope": (4, 4), "sack": (8, 4), "tin": (12, 4)}
SWATCH = {"cork": 0, "ivory": 1, "amber": 2, "crust": 3, "flour": 4, "glassbright": 5, "wear": 6, "soot": 7}

# ---------- atlas ----------
def srgb(c): return np.array(c, dtype=np.float32)
def mix(a, b, t): t = np.clip(t, 0, 1)[..., None]; return a * (1 - t) + b * t

def build_atlas():
    src = bpy.data.images.load(os.path.join(BUNKER, "bunker_atlas.png"))
    img = np.array(src.pixels[:], np.float32).reshape(TEX, TEX, 4)[..., :3].copy()
    nr = np.random.default_rng(29)
    tile = lambda k: 2 * math.pi * k / TEX
    def grid(h): return (np.arange(TEX)[None, :].repeat(h, 0).astype(np.float32), np.arange(h)[:, None].repeat(TEX, 1).astype(np.float32))
    x, y = grid(12)                                   # clay (as apothecary_r2)
    t = 0.30 + 0.22 * np.sin(y * 2.3 + 0.7 * np.sin(x * tile(3))) * 0.5 + 0.20 * (0.5 + 0.5 * np.sin(x * tile(2) + 1.3)) + nr.random((12, TEX)) * 0.18
    t += (y < 1.5) * 0.45 + (y < 0.5) * 0.2
    c = mix(srgb((0.50, 0.34, 0.24)), srgb((0.24, 0.155, 0.11)), t)
    c = np.where((y > 10.5)[..., None], mix(c, srgb((0.62, 0.48, 0.36)), np.full((12, TEX), 0.6)), c)
    sp = nr.random((12, TEX)) < 0.04; c[sp] = c[sp] * 0.7
    img[36:48] = c
    img[24:36] = img[36:48]                           # (rows 24-35 were wicker in apothecary_r2: not used here, kept quiet)
    x, y = grid(8)                                    # glass (as apothecary_r2)
    t = 0.45 + nr.random((8, TEX)) * 0.12 + 0.12 * np.sin(x * tile(5) + 0.4)
    t -= ((x % 32 >= 5) & (x % 32 <= 6)) * 0.45 + ((x % 32) == 19) * 0.3
    t += (y < 1) * 0.25
    img[16:24] = mix(srgb((0.80, 0.86, 0.82)), srgb((0.46, 0.54, 0.51)), t)
    x, y = grid(4)                                    # cord
    t = ((x + y * 1.5) % 5 < 2.5) * 0.45 + nr.random((4, TEX)) * 0.2 + ((y == 0) | (y == 3)) * 0.2
    img[4:8] = mix(srgb((0.52, 0.44, 0.30)), srgb((0.22, 0.17, 0.10)), t)
    x, y = grid(4)                                    # hessian: a fine plain weave (one-pixel threads), a few darker and lighter threads, soft stripes
    weave = (((x).astype(int) + y.astype(int)) % 2)
    t = 0.38 + 0.16 * weave + nr.random((4, TEX)) * 0.20 + 0.10 * np.sin(x * tile(9)) - ((x % 13) == 4) * 0.18 + ((x % 17) == 9) * 0.12
    img[8:12] = mix(srgb((0.86, 0.80, 0.66)), srgb((0.50, 0.42, 0.30)), t)
    x, y = grid(4)                                    # tin: worn dark metal, a lighter edge at the top row
    t = 0.50 + nr.random((4, TEX)) * 0.22 + 0.06 * np.sin(x * tile(4)) - (y == 3) * 0.35 + (y == 0) * 0.2
    img[12:16] = mix(srgb((0.50, 0.49, 0.46)), srgb((0.20, 0.19, 0.19)), t)
    SW = [((0.55, 0.42, 0.27), (0.30, 0.21, 0.12)), ((0.80, 0.76, 0.64), (0.55, 0.49, 0.38)), ((0.82, 0.64, 0.20), (0.50, 0.34, 0.08)),
          ((0.60, 0.40, 0.19), (0.38, 0.22, 0.09)), ((0.90, 0.86, 0.76), (0.70, 0.65, 0.54)), ((0.88, 0.93, 0.90), (0.66, 0.74, 0.71)),
          ((0.52, 0.43, 0.31), (0.36, 0.29, 0.20)), ((0.13, 0.11, 0.10), (0.06, 0.05, 0.05))]
    for i, (a, b) in enumerate(SW):
        img[0:4, 16 * i:16 * i + 16] = mix(srgb(a), srgb(b), nr.random((4, 16)) * 0.55 + (i == 1) * 0.1)
    im = bpy.data.images.new("pantry_atlas", TEX, TEX, alpha=False)
    px = np.concatenate([np.clip(img, 0, 1), np.ones((TEX, TEX, 1), np.float32)], 2)
    im.pixels.foreach_set(px.ravel())
    im.filepath_raw = os.path.join(OUTA, "pantry_atlas.png"); im.file_format = "PNG"; im.save()
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
NCOL, PITCH = 8, 0.24
PS = 0.12                                   # front post section
XIN = NCOL * PITCH / 2                      # 0.96: inner face of the posts
PX = XIN + PS / 2                           # post centre x
W, DEPTH, H = 2 * (XIN + PS), 0.46, 2.14    # 2.16
YF0, YF1 = -DEPTH, -DEPTH + PS
YB0, YB1 = -0.115, -0.005
YBACK = (-0.045, -0.005)
SHELF_T = 0.05
LEVEL = [1.63, 1.25, 0.87, 0.49, 0.11]      # shelf tops, tier 0 (top) to 4 (floor board)
TOPB = 2.08
COLX = [(c - (NCOL - 1) / 2) * PITCH for c in range(NCOL)]
VY = -0.25
NPLACE = NCOL * len(LEVEL)
UNITS_PER = 2                               # stacks per place and family: 40 x 2 = 80
SEG = 16
TB = 0.02                                   # the floor of every vessel
R_C, H_C = 0.090, 0.22                      # the clear space: upright cylinder on the floor (z = TB above the shelf)
FAM_RANK = {f: i for i, f in enumerate(FAMILIES)}
SHARE = {"jar": 8, "tray": 16, "crock": 12, "sack": 4}      # places per family in the full demo (and the defaults): 7 / 14 / 9 / 2 kinds on 8 / 16 / 12 / 4 places
def full_assign():
    """every kind in the order the mod claims places (families jar, tray, crock, sack; then by name); a family takes its SHARE of the places, the first
    kinds of a family take the extra ones; so every place is full"""
    out = []
    for f in sorted(FAM_RANK, key=FAM_RANK.get):
        kinds = sorted(n for n in ITEMS if PANTRY[n] == f)
        if not kinds: continue
        pl = SHARE[f] if not QUICK else len(kinds)
        for i, it in enumerate(kinds): out += [it] * (pl // len(kinds) + (1 if i < pl % len(kinds) else 0))
    return out[:NPLACE] + [None] * max(0, NPLACE - len(out))
FULL_ASSIGN = full_assign()
def _fam_of_place(n):
    it = FULL_ASSIGN[n]
    if it: return PANTRY[it]
    return "sack"
DEFAULT = [_fam_of_place(n) for n in range(NPLACE)]     # the family a place is for (the mod draws nothing in an empty place)

def place_origin(n):
    r, c = divmod(n, NCOL)
    return Vector((COLX[c], VY, LEVEL[r]))

def in_cyl(P, eps=0.0015):
    return (P[:, 2] >= min(eps, 0.0) - 0.0002) & (P[:, 2] <= H_C - eps) & (np.hypot(P[:, 0], P[:, 1]) <= R_C - eps)

def outside_cyl(P):
    return float(np.max(np.maximum.reduce([-P[:, 2], P[:, 2] - H_C, np.hypot(P[:, 0], P[:, 1]) - R_C])))

# ---------- the four vessels, in local coordinates (origin = centre of the footprint at the shelf surface) ----------
KRJ, KZJ = 0.95, 0.92                       # glass jar: apothecary_r2's, scaled to the 24 cm pitch
KRC = 0.88                                  # clay crock: apothecary_r2's
VESSEL_PROF = {
    "jar": dict(prof=[(0.116 * KRJ, 0.0), (0.119 * KRJ, 0.02 * KZJ), (0.119 * KRJ, 0.262 * KZJ), (0.111 * KRJ, 0.285 * KZJ)], t=0.008 * KRJ),
    "crock": dict(prof=[(r * KRC, z) for r, z in ((0.121, 0.0), (0.126, 0.04), (0.129, 0.085), (0.125, 0.12), (0.122, 0.14), (0.126, 0.152))], t=0.014 * KRC),
    "sack": dict(prof=[(r * 0.985, z) for r, z in ((0.106, 0.0), (0.108, 0.025), (0.114, 0.06), (0.113, 0.10), (0.109, 0.128), (0.1085, 0.145), (0.110, 0.153))], t=0.011),
    "tray": dict(prof=[(0.105, 0.0), (0.110, 0.02), (0.1125, 0.045)], t=0.006),
}

def build_vessel(fam):
    o = Vector((0, 0, 0))
    if fam == "jar":
        v = VESSEL_PROF["jar"]; half = math.radians(62); front = -math.pi / 2
        shell("jar", v["prof"], v["t"], "glass", SEG, arc=(front + half, front - half + 2 * math.pi), bottom=False, at=o)
        disc("jarbase", 0.118 * KRJ, 0.118 * KRJ, 0.0, TB, "glass", o, SEG)
        shell("jarrim", [(0.110 * KRJ, 0.282 * KZJ), (0.111 * KRJ, 0.300 * KZJ)], 0.012 * KRJ, "glassbright", 12, bottom=False, at=o)
        disc("cork", 0.094 * KRJ, 0.086 * KRJ, 0.292 * KZJ, 0.334 * KZJ, "cork", o, 12)
    elif fam == "crock":
        v = VESSEL_PROF["crock"]
        shell("crock", v["prof"], v["t"], "clay", SEG, bottom=True, tb=TB, at=o, rotz=rng.uniform(0, 2 * math.pi))
        ring("crockcord", 0.1235 * KRC, 0.128, 0.011 * KRC, o, "rope", 10, 0.0)
    elif fam == "sack":
        v = VESSEL_PROF["sack"]
        sk = shell("sack", v["prof"], v["t"], "sack", 16, bottom=True, tb=TB, at=o, rotz=rng.uniform(0, 2 * math.pi))
        ph = rng.uniform(0, 6.28)
        for vt in sk.data.vertices:                                                         # a cloth sack is not a lathe: soft folds, only ever outwards (the clear space stays clear)
            a = math.atan2(vt.co.y, vt.co.x); f = 1.012 + 0.012 * math.sin(3 * a + 11 * vt.co.z + ph) + 0.006 * math.sin(5 * a - 7 * vt.co.z)
            vt.co.x *= f; vt.co.y *= f
        ring("sackcuff", 0.104, 0.151, 0.016, o, "sack", 14, rng.uniform(0, 1))             # the rolled-down cuff
        ring("sackcord", 0.108, 0.100, 0.008, o, "rope", 12, 0.0)                         # the cord round the belly
        for k in range(4): cord("seam", (0.0, -0.111, 0.03 + 0.025 * k), (0.004, -0.111, 0.046 + 0.025 * k), 0.006, "soot")        # a sewn seam down the front
    else:                                                                                  # the baking tray: a round tin pan with a rolled rim
        v = VESSEL_PROF["tray"]
        shell("tray", v["prof"], v["t"], "tin", 18, bottom=True, tb=TB, at=o, rotz=rng.uniform(0, 2 * math.pi))
        ring("trayrim", 0.1085, 0.0465, 0.010, o, "tin", 18, 0.0)

# ---------- the frame ----------
def build_frame():
    j = lambda a: rng.uniform(-a, a)
    for sx in (-1, 1):
        timber("post", (PS, PS, TOPB), (sx * PX, (YF0 + YF1) / 2, TOPB / 2), rot=(j(0.3), j(0.3), 0), jitter=0.012, bevel=0.02)
        timber("post", (PS, YB1 - YB0, TOPB), (sx * PX, (YB0 + YB1) / 2, TOPB / 2), jitter=0.008, bevel=0.018)
        plank("sideboard", (0.045, YB0 - YF1 + 0.04, TOPB - 0.14), (sx * PX, (YF1 + YB0) / 2, 0.10 + (TOPB - 0.14) / 2), rot=(0, 0, j(0.2)), jitter=0.004)   # solid side boards: a dresser's carcass
    plank("top", (W + 0.07, DEPTH + 0.06, 0.05), (0, -DEPTH / 2 + 0.005, TOPB + 0.025), rot=(0, 0, j(0.2)))                  # the overhanging top
    plank("cornice", (W + 0.02, 0.05, 0.03), (0, YF0 - 0.015, TOPB + 0.005), jitter=0.003)
    xs = np.linspace(-XIN, XIN, 10)
    for a, b in zip(xs[:-1], xs[1:]):
        plank("back", (b - a + 0.012, YBACK[1] - YBACK[0], TOPB - 0.06), ((a + b) / 2, sum(YBACK) / 2, 0.06 + (TOPB - 0.06) / 2), rot=(0, j(0.3), 0))
    for y in (-DEPTH + 0.05, -0.12):
        timber("sill", (2 * XIN + 0.02, 0.10, 0.06), (0, y, 0.03), jitter=0.006, bevel=0.012)
    plank("plinth", (2 * XIN + 0.02, 0.04, 0.09), (0, YF0 + 0.02, 0.055), jitter=0.004)                                    # a kick plate under the floor board
    for top in LEVEL:
        # shelves: thin jitter so the vessel feet stand on a flat surface; a low lip along the front edge
        plank("shelf", (2 * XIN + 0.04, DEPTH + YBACK[0], SHELF_T), (0, (-DEPTH + YBACK[0]) / 2, top - SHELF_T / 2), rot=(0, 0, j(0.2)), jitter=0.0015)
        plank("lip", (2 * XIN, 0.035, 0.045), (0, -DEPTH + 0.0175, top + 0.0225), jitter=0.0015)
    timber("header", (W, 0.12, 0.12), (0, YF0 + 0.06, TOPB - 0.06), rot=(0, 0, j(0.15)), jitter=0.01, bevel=0.018)
    # back stiles between the places (behind the vessels, in front of the back boards), between columns 1|2, 3|4, 5|6
    STILE_X = [COLX[c] + PITCH / 2 for c in range(1, NCOL - 1, 2)]
    tops = sorted(LEVEL) + [TOPB - 0.06]
    for lo, hi in zip(tops[:-1], tops[1:]):
        for x in STILE_X:
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

def relief(name, c, r, sw, u=8, v=5, rotz=0.0):
    global UV
    bm = bmesh.new(); UV = bm.loops.layers.uv.verify()
    res = bmesh.ops.create_uvsphere(bm, u_segments=u, v_segments=v, radius=1.0)
    for vv in res["verts"]: vv.co = Vector((vv.co.x * r[0], vv.co.y * r[1], vv.co.z * r[2]))
    bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(rotz, 3, "Y"))
    bmesh.ops.translate(bm, verts=bm.verts, vec=Vector(c))
    bm.normal_update()
    for f in bm.faces: sw_uv(f, sw)
    return link(bm, name)

def build_plaque():
    """a board on the header: a scored loaf and an ear of barley in relief, riveted at its corners"""
    yb = YF0 - 0.035
    plank("plaque", (0.62, 0.035, 0.105), (0, YF0 - 0.0175, TOPB - 0.06))
    for dx in (-0.28, 0.28):
        for dz in (-0.033, 0.033): rivet((dx, yb, TOPB - 0.06 + dz), (1, -1))
    zc = TOPB - 0.06; yf = yb - 0.004
    relief("loaf", (-0.12, yf - 0.002, zc - 0.004), (0.074, 0.018, 0.034), "crust", 10, 6)
    for dx in (-0.045, -0.12, -0.195):
        cord("score", (dx - 0.010, yf - 0.019, zc - 0.012), (dx + 0.010, yf - 0.019, zc + 0.020), 0.007, "soot")
    cord("stem", (0.17, yf - 0.004, zc - 0.044), (0.17, yf - 0.006, zc + 0.030), 0.006, "amber")
    for i in range(5):
        for sx in (-1, 1): relief("grain", (0.17 + sx * 0.011, yf - 0.009, zc - 0.012 + i * 0.012), (0.0075, 0.006, 0.013), "amber", 6, 4, sx * 0.4)
    relief("grain", (0.17, yf - 0.009, zc + 0.052), (0.0075, 0.006, 0.014), "amber", 6, 4)


# ---------- scene ----------
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
ATLAS = build_atlas()
MAT = bpy.data.materials.new("pantry"); MAT.use_nodes = True
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
    print("PAN1 vessel %-8s parts %d tris %d" % (fam, len(PARTS), VESSEL_TRIS[fam]), flush=True)
    if EXPORT:
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
print("PAN1 frame tris", FRAME_TRIS, "parts", len(FRAME_PARTS), flush=True)
if "--frame-only" in argv: sys.exit(0)
if EXPORT: obj_export(FRAME_PARTS, os.path.join(OUTA, "Pantry.obj"))

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

# ---- stand-ins for the kinds that are not in the model rip (see the docstring): procedural proxies in the game's flat low-poly style ----
def pmat(name, rgb, rough=0.85):
    key = "PX_" + name
    m = bpy.data.materials.get(key)
    if m: return m
    m = bpy.data.materials.new(key); m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (rgb[0] ** 2.2, rgb[1] ** 2.2, rgb[2] ** 2.2, 1); b.inputs["Roughness"].default_value = rough
    return m

def _new_faces(bm, fn):
    before = set(bm.faces); fn(); return [f for f in bm.faces if f not in before]

def blob(bm, c, r, mi, u=10, v=6, noise=0.0, zclip=None, rotz=0.0, rg=None):
    """an ellipsoid at c with radii r (x, y, z), material index mi; zclip (unit-sphere z) flattens the bottom or leaves only the upper half"""
    rg = rg or random.Random(1)
    def mk():
        res = bmesh.ops.create_uvsphere(bm, u_segments=u, v_segments=v, radius=1.0)
        for vv in res["verts"]:
            n = 1 + rg.uniform(-noise, noise) if noise else 1.0
            x, y, z = vv.co
            if zclip is not None: z = max(z, zclip)
            px, py = x * r[0] * n, y * r[1] * n
            vv.co = Vector((c[0] + px * math.cos(rotz) - py * math.sin(rotz), c[1] + px * math.sin(rotz) + py * math.cos(rotz), c[2] + z * r[2] * n))
    for f in _new_faces(bm, mk): f.material_index = mi

def cyl(bm, c, r0, r1, h, mi, segs=8, tilt=None):
    def mk():
        res = bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=segs, radius1=r0, radius2=r1, depth=h)
        if tilt is not None: bmesh.ops.rotate(bm, verts=res["verts"], cent=(0, 0, 0), matrix=tilt)
        bmesh.ops.translate(bm, verts=res["verts"], vec=Vector(c))
    for f in _new_faces(bm, mk): f.material_index = mi

def pmesh(bm, mats, name):
    bm.normal_update()
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for m in mats: me.materials.append(m)
    for p in me.polygons: p.use_smooth = False
    return me

def px_bag(name, body, band, size=(0.075, 0.056, 0.10), tie=(0.30, 0.22, 0.13), noise=0.04):
    """a gathered cloth bag (flour, spice): a pillow body with a flat foot, a tied neck, a flared mouth; a band round the belly"""
    bm = bmesh.new(); rg = random.Random(zlib.crc32(name.encode()))
    blob(bm, (0, 0, 0), size, 0, 10, 6, noise, -0.8, rg=rg)
    for f in bm.faces:
        zc = sum(v.co.z for v in f.verts) / len(f.verts)
        if -0.15 * size[2] <= zc <= 0.28 * size[2] and band is not None: f.material_index = 1
    cyl(bm, (0, 0, size[2] * 0.96), size[0] * 0.38, size[0] * 0.28, 0.034, 0, 8)
    cyl(bm, (0, 0, size[2] + 0.014), size[0] * 0.40, size[0] * 0.40, 0.012, 2, 8)
    cyl(bm, (0, 0, size[2] + 0.045), size[0] * 0.30, size[0] * 0.58, 0.050, 0, 8)
    return pmesh(bm, [pmat(name + "_a", body), pmat(name + "_b", band or body), pmat("tie", tie)], name)

def px_dough(name):
    bm = bmesh.new(); rg = random.Random(5)
    blob(bm, (0, 0, 0), (0.115, 0.085, 0.062), 0, 10, 6, 0.06, -0.45, rg=rg)
    blob(bm, (0.045, 0.02, 0.030), (0.052, 0.050, 0.036), 0, 8, 5, 0.06, -0.2, rg=rg)
    blob(bm, (-0.03, -0.025, 0.040), (0.040, 0.036, 0.020), 1, 7, 4, 0.0, 0.0, rg=rg)          # a dusting of flour
    return pmesh(bm, [pmat("dough", (0.91, 0.82, 0.60)), pmat("flourdust", (0.96, 0.93, 0.86))], name)

def px_bundle(name):
    """a bunch of dried herbs tied with cord: eight stalks that splay a little, leaves, a few violet blossoms at the top"""
    bm = bmesh.new(); rg = random.Random(9)
    for i in range(8):
        a = 2 * math.pi * i / 8 + rg.uniform(-0.2, 0.2); sp = 0.10 if i else 0.0
        dirv = Vector((math.cos(a) * sp, math.sin(a) * sp, 1.0)).normalized()
        L = rg.uniform(0.19, 0.23); q = Vector((0, 0, 1)).rotation_difference(dirv).to_matrix()
        base = Vector((math.cos(a) * 0.006, math.sin(a) * 0.006, -0.10)); mid = base + dirv * (L / 2)
        cyl(bm, mid, 0.0075, 0.0045, L, 0, 5, q)
        for k, t in enumerate((0.55, 0.80)):
            p = base + dirv * (L * t)
            blob(bm, (p.x + math.cos(a + 1.2 * k) * 0.012, p.y + math.sin(a + 1.2 * k) * 0.012, p.z), (0.022, 0.007, 0.014), 1, 5, 3, 0.0, None, a + 1.2 * k, rg)
        top = base + dirv * L
        blob(bm, (top.x, top.y, top.z), (0.011, 0.011, 0.016), 2, 5, 3, 0.0, None, 0.0, rg)
    cyl(bm, (0, 0, -0.045), 0.030, 0.030, 0.016, 3, 8)
    return pmesh(bm, [pmat("herb_stem", (0.46, 0.50, 0.30)), pmat("herb_leaf", (0.40, 0.52, 0.34)), pmat("herb_bloom", (0.55, 0.40, 0.66)), pmat("tie", (0.30, 0.22, 0.13))], name)

def px_produce(name, body, leaf):
    """a feast ingredient (not ripped yet): a small cluster of three round pieces of produce with a leaf and a stalk"""
    bm = bmesh.new(); rg = random.Random(zlib.crc32(name.encode()))
    for c, r in (((0.0, 0.0, 0.0), 0.052), ((0.062, 0.010, -0.004), 0.046), ((0.030, -0.052, -0.002), 0.044)):
        blob(bm, c, (r, r, r * 0.92), 0, 9, 6, 0.05, -0.85, rg=rg)
    blob(bm, (0.030, -0.012, 0.050), (0.040, 0.016, 0.010), 1, 6, 4, 0.0, None, 0.7, rg)
    cyl(bm, (0.030, -0.012, 0.042), 0.007, 0.005, 0.030, 1, 5)
    return pmesh(bm, [pmat(name + "_a", body), pmat(name + "_l", leaf)], name)

def px_pie(name, rim, fill, r=0.115, lattice=False, domeh=0.034):
    bm = bmesh.new(); rg = random.Random(zlib.crc32(name.encode()))
    cyl(bm, (0, 0, 0), r, r * 0.96, 0.044, 0, 16)
    for i in range(16):
        a = 2 * math.pi * i / 16
        blob(bm, ((r - 0.004) * math.cos(a), (r - 0.004) * math.sin(a), 0.026), (0.013, 0.013, 0.011), 0, 5, 3, 0.0, None, 0.0, rg)
    blob(bm, (0, 0, 0.022), (r * 0.84, r * 0.84, domeh), 1, 14, 5, 0.025, 0.0, rg=rg)
    if lattice:
        for k in (-1, 0, 1):
            for ang in (0.6, -0.6):
                def mk(k=k, ang=ang):
                    res = bmesh.ops.create_cube(bm, size=1.0)
                    for vv in res["verts"]: vv.co = Vector((vv.co.x * r * 1.5, vv.co.y * 0.012, vv.co.z * 0.008))
                    bmesh.ops.rotate(bm, verts=res["verts"], cent=(0, 0, 0), matrix=Matrix.Rotation(ang, 3, "Z"))
                    bmesh.ops.translate(bm, verts=res["verts"], vec=Vector((-k * 0.032 * math.sin(ang), k * 0.032 * math.cos(ang), 0.022 + domeh * 0.80)))
                for f in _new_faces(bm, mk): f.material_index = 0
    return pmesh(bm, [pmat(name + "_c", rim), pmat(name + "_f", fill)], name)

def px_pancake(name):
    bm = bmesh.new(); rg = random.Random(3)
    blob(bm, (0, 0, 0), (0.118, 0.118, 0.026), 0, 16, 4, 0.02, -0.4, rg=rg)
    blob(bm, (0.012, -0.01, 0.020), (0.080, 0.075, 0.010), 1, 10, 3, 0.04, 0.0, rg=rg)
    return pmesh(bm, [pmat("batter", (0.90, 0.78, 0.52)), pmat("batter2", (0.95, 0.86, 0.62))], name)

def px_cupcake(name):
    bm = bmesh.new(); rg = random.Random(4)
    cyl(bm, (0, 0, -0.030), 0.034, 0.050, 0.044, 0, 12)
    blob(bm, (0, 0, -0.004), (0.055, 0.055, 0.046), 1, 12, 5, 0.03, -0.05, rg=rg)
    blob(bm, (0.004, 0, 0.040), (0.012, 0.012, 0.012), 2, 6, 4, 0.0, None, 0.0, rg)
    return pmesh(bm, [pmat("cupcup", (0.62, 0.34, 0.22)), pmat("cupbatter", (0.93, 0.84, 0.62)), pmat("cupberry", (0.62, 0.16, 0.18))], name)

def px_leafpile(name):
    bm = bmesh.new(); rg = random.Random(8)
    for i in range(7):
        a = rg.uniform(0, 2 * math.pi); d = 0.045 if i else 0.0
        blob(bm, (d * math.cos(a), d * math.sin(a), 0.006 * i), (0.075, 0.034, 0.008), i % 2, 8, 3, 0.05, None, a + 1.3, rg)
    return pmesh(bm, [pmat("kale1", (0.30, 0.44, 0.24)), pmat("kale2", (0.38, 0.52, 0.28))], name)

def px_shroom(name):
    bm = bmesh.new(); rg = random.Random(6)
    cyl(bm, (0, 0, 0.0), 0.022, 0.026, 0.060, 1, 8)
    blob(bm, (0, 0, 0.030), (0.078, 0.078, 0.046), 0, 12, 5, 0.03, 0.0, rg=rg)
    blob(bm, (0, 0, 0.060), (0.046, 0.046, 0.018), 2, 8, 4, 0.0, 0.0, rg=rg)                    # the stuffing heaped on the cap
    return pmesh(bm, [pmat("shroomcap", (0.50, 0.34, 0.52)), pmat("shroomstem", (0.88, 0.84, 0.72)), pmat("stuffing", (0.86, 0.78, 0.50))], name)

SPICE_RGB = {"SpiceForests": (0.46, 0.55, 0.28), "SpicePlains": (0.80, 0.62, 0.22), "SpiceMountains": (0.52, 0.60, 0.74), "SpiceOceans": (0.28, 0.56, 0.56),
             "SpiceMistlands": (0.55, 0.40, 0.66), "SpiceDeepNorth": (0.80, 0.88, 0.93), "SpiceAshlands": (0.76, 0.30, 0.15)}
FEAST_RGB = {"FeastMeadows_Material": ((0.78, 0.32, 0.24), (0.38, 0.55, 0.28)), "FeastBlackforest_Material": ((0.45, 0.30, 0.20), (0.26, 0.40, 0.25)),
             "FeastSwamps_Material": ((0.48, 0.52, 0.30), (0.30, 0.38, 0.22)), "FeastMountains_Material": ((0.76, 0.82, 0.90), (0.40, 0.55, 0.45)),
             "FeastPlains_Material": ((0.84, 0.66, 0.24), (0.55, 0.52, 0.22)), "FeastOceans_Material": ((0.30, 0.55, 0.60), (0.24, 0.42, 0.40)),
             "FeastDeepNorth_Material": ((0.70, 0.82, 0.90), (0.50, 0.62, 0.70)), "FeastMistlands_Material": ((0.58, 0.40, 0.68), (0.34, 0.30, 0.50)),
             "FeastAshlands_Material": ((0.82, 0.40, 0.14), (0.30, 0.24, 0.20))}
# a ripped cooked dish as the stand-in where one exists (same shape family; the colours are the cooked ones)
STANDIN = {"FishAndBreadUncooked": "FishAndBread", "HoneyGlazedChickenUncooked": "HoneyGlazedChicken", "LoxPieUncooked": "LoxPie", "MeatPlatterUncooked": "MeatPlatter"}
PROXY = {
    "BarleyFlour": lambda n: px_bag(n, (0.86, 0.76, 0.52), (0.58, 0.44, 0.22), (0.082, 0.058, 0.105)),
    "OatFlour": lambda n: px_bag(n, (0.90, 0.86, 0.74), (0.48, 0.52, 0.40), (0.082, 0.058, 0.105)),
    "BreadDough": px_dough, "FragrantBundle": px_bundle,
    "BakedPoteitrUncooked": lambda n: px_pie(n, (0.84, 0.72, 0.50), (0.82, 0.70, 0.36)),
    "KaleChipsUncooked": px_leafpile, "MagicallyStuffedShroomUncooked": px_shroom,
    "MisthareSupremeUncooked": lambda n: px_pie(n, (0.80, 0.70, 0.54), (0.60, 0.50, 0.62), lattice=True),
    "OvenPancakeUncooked": px_pancake,
    "PiquantPieUncooked": lambda n: px_pie(n, (0.84, 0.70, 0.48), (0.72, 0.30, 0.18), domeh=0.030),
    "RoastedCrustPieUncooked": lambda n: px_pie(n, (0.80, 0.62, 0.38), (0.72, 0.54, 0.30), lattice=True, domeh=0.040),
    "VikingCupcakeUncooked": px_cupcake,
}
for _n, (_b, _l) in FEAST_RGB.items(): PROXY[_n] = (lambda b, l: (lambda n: px_produce(n, b, l)))(_b, _l)
for _n, _c in SPICE_RGB.items(): PROXY[_n] = (lambda c: (lambda n: px_bag(n, c, None, (0.060, 0.052, 0.062), noise=0.05)))(_c)
LB_OVERRIDE = {"BarleyFlour": 0.115, "OatFlour": 0.115, "FragrantBundle": 0.17, "BreadDough": 0.105}      # the longest side of a copy, m (default by shape: 0.09 round, 0.13 lying, 0.14 long)
UPRIGHT = {"VikingCupcakeUncooked", "MagicallyStuffedShroomUncooked"}      # stand on their foot (yaw only), not tumble
LIE = {n for n in PANTRY if n.endswith("Uncooked")} - UPRIGHT                      # the dishes lie on their broad side in the tray

def item_source(name):
    """('real', prefab) when the model is in the rip, ('standin', prefab) for a ripped cooked dish, else ('proxy', None)"""
    if os.path.isdir(os.path.join(ITEMS_DIR, name)): return "real", name
    if name in STANDIN and os.path.isdir(os.path.join(ITEMS_DIR, STANDIN[name])): return "standin", STANDIN[name]
    return "proxy", None
SRC = {n: item_source(n) for n in ITEMS}

V_CYL = math.pi * R_C ** 2 * H_C
TRI_PER_VESSEL = 5400
NMAX_ROD = 20                               # slender bundles
NMAX_THIN = 14                              # flat kinds (pies, pancakes, leaf piles, dough)
NMAX = 12                                   # most copies in a full vessel: big, readable items, few of them
FILL_PACK = 0.30
TPL = {}
def tpl(name):
    """name: an item or '_generic' (heap lump)"""
    if name in TPL: return TPL[name]
    if name == "_generic": datas = [lump_mesh()]
    else:
        kind, prefab = SRC[name]
        if kind == "proxy": datas = [PROXY[name](name)]
        else:
            objs = [o for o in load_item(prefab, anchor="center") if o.type == "MESH"]
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
    ent = dict(datas=datas, verts=verts, size=size, A=A, tris=ntri, hv=hv, F=F, N=np.array(N), D=np.array(D), vol=vol, cap=cap)
    if name in UPRIGHT: mode = "upright"
    elif name in LIE or (ss[2] / ss[0] < 0.32 and ss[1] / ss[0] >= 0.30): mode = "lie"
    else: mode = "tumble"
    Lb = 0.090 if ss[1] / ss[0] >= 0.75 and mode != "lie" else (0.120 if mode == "lie" else 0.140)
    if mode == "upright": Lb = 0.088
    Lb = LB_OVERRIDE.get(name, 0.092 if name.startswith("Spice") else Lb)
    s = Lb / ss[0]
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
        elif t["mode"] == "upright": R = np.array(Rz(rr.uniform(0, 360)) @ Rx(rr.uniform(-8, 8)) @ Ry(rr.uniform(-8, 8)))
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
                print("PAN1 %-20s full: %2d copies (cap %d), scale %.3f, level %.3f, top %.3f, stacks %s" % (name, n, s["t"]["cap"], s["t"]["s"], s["hfl"].level(),
                      max(float(b["HV"][:, 2].max()) for b in s["frozen"]) if n else 0, [cut[k + 1] - cut[k] for k in range(UNITS_PER)]), flush=True)
    for o in [o for o in bpy.data.objects if o.rigid_body is not None]: bpy.data.objects.remove(o)
    bpy.ops.rigidbody.world_remove()
    sc.frame_set(1)
    return ST, stats

KINDS = [n for n in ITEMS] + ["_generic"]
ST, SIMST = settle(KINDS)
print("PAN1 SIM", SIMST, "%.0fs" % (time.time() - t0), flush=True)

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

CHECK = {}
for name in KINDS:
    s = ST[name]; t = s["t"]; fr = s["frozen"]
    fmax, pen = float_pen(name)
    P = np.vstack([(t["verts"] * t["s"]) @ b["R"].T + b["c"] for b in fr]) if fr else np.zeros((1, 3))
    hf = HF(); lv = []
    for k in range(UNITS_PER):
        for b in fr:
            if b["stack"] == k: hf.add(b["N"], b["D"], dilate=False)
        lv.append(round(hf.level(), 3))
    CHECK[name] = dict(copies=len(fr), copies_by_stack=[sum(1 for b in fr if b["stack"] == k) for k in range(UNITS_PER)], cap=t["cap"],
                       mesh_outside_cylinder_mm=round(outside_cyl(P) * 1000, 1), float_worst_mm=round(fmax * 1000, 2),
                       overlap_max_mm=round(pen * 1000, 2), level_by_stacks_m=lv, top_m=round(float(P[:, 2].max()), 3),
                       longest_m=round(float(t["size"].max() * t["s"]), 3), drawn_tris_per_copy=t["tris"], tris_full_vessel=len(fr) * t["tris"])
    print("PAN1 CHECK %-32s %s" % (name, CHECK[name]), flush=True)

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
    print("PAN1 cylinder vs vessel %-8s: %d of %d points inside %s" % (fam, h, len(CS), notes[:4]), flush=True)
# (b) every copy (all its vertices) inside the clear cylinder, i.e. clear of every vessel (a) -> the max over all layouts
COPY_OUT = max(CHECK[n]["mesh_outside_cylinder_mm"] for n in KINDS)      # <= 0: inside the cylinder
FV = np.vstack([p["V"] for p in FRAME_DATA])
ves_frame = {}; cyl_frame = 0; cyl_notes = []; fv_in = 0
for n in range(NPLACE):
    org = np.array(place_origin(n))
    for fam in FAMILIES:
        pts = np.vstack([np.vstack([p["V"], p["cent"]]) for p in VESSEL_PARTS[fam]]) + org
        pts = pts[pts[:, 2] > org[2] + 0.003]
        h, notes = count_inside(pts, FRAME_DATA)
        ves_frame[(n, fam)] = h
        if h: print("PAN1 vessel %s at place %d inside frame: %d %s" % (fam, n, h, notes[:3]), flush=True)
    h, notes = count_inside(CS + FLOORS[n], FRAME_DATA); cyl_frame += h; cyl_notes += notes
    Q = FV - FLOORS[n]; hit = in_cyl(Q, 0.001) & (Q[:, 2] > 0.001); fv_in += int(hit.sum())
VES_FRAME = sum(ves_frame.values())
print("PAN1 vessels vs frame: %d vessel points inside frame parts (%d vessel x place combinations); cylinders vs frame: %d points %s, frame vertices in a cylinder %d" %
      (VES_FRAME, len(ves_frame), cyl_frame, cyl_notes[:3], fv_in), flush=True)
# (d) neighbours: the widest vessel radius against the 0.25 m pitch
RMAX = {f: max(float(np.hypot(p["V"][:, 0], p["V"][:, 1]).max()) for p in VESSEL_PARTS[f]) for f in FAMILIES}
print("PAN1 vessel radii", {k: round(v, 3) for k, v in RMAX.items()}, "pitch", PITCH, "widest pair", round(max(RMAX.values()) * 2, 3), flush=True)
# (e) the vessels' x extent (hanging bars) is in x; the gallows is the widest in x, the others round
XEXT = {f: round(max(float(np.abs(p["V"][:, 0]).max()) for p in VESSEL_PARTS[f]), 3) for f in FAMILIES}
print("PAN1 vessel x half-extent", XEXT, flush=True)


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
    real = name != "_generic" and SRC[name][0] == "real"
    ent = {"family": PANTRY.get(name, "any"), "mode": t["mode"],
           "scale": round(t["s"], 5) if real else None, "true_size_m": [round(float(sz[0]), 4), round(float(sz[2]), 4), round(float(sz[1]), 4)],
           "fit_longest_m": round(float(sz.max() * t["s"]), 4),
           "copies_per_stack": round(len(s["frozen"]) / UNITS_PER, 2), "copies_by_stack": [len(x) for x in stacks], "stacks": stacks, "check": CHECK[name]}
    if name == "_generic":
        ent["scale"] = None; ent["true_size_m"] = None
        ent["note"] = "fallback for any item without its own layout in a jar, tray, crock or sack: a neutral round lump (a settled heap), scaled uniformly so its longest bounds side is fit_longest_m."
    else:
        kind, prefab = SRC[name]
        ent["model"] = {"real": "the item's own ripped model", "standin": "STAND-IN: ripped cooked dish '%s' (the uncooked prefab is not in the rip)" % prefab,
                        "proxy": "STAND-IN: procedural proxy (the prefab is not in the rip)"}[kind]
        if kind != "real":
            ent["note"] = ("layout built on a stand-in mesh: draw the real prefab uniformly scaled to fit_longest_m (scale is null on purpose); rotations are relative to the "
                           "stand-in's axes and 'true_size_m' is the stand-in's size. Re-run pantry_r1.py once the prefab is in the rip to get its own.")
    layouts[name] = ent
GEN = {f: layouts["_generic"] for f in FAMILIES}
ITEM_FAMILY = {k: v for k, v in PANTRY.items() if k in ITEMS}
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
vessels = [{"position": n, "at": uvec(place_origin(n)), "default": DEFAULT[n]} for n in range(NPLACE)]
heaviest = max(ITEMS, key=lambda n: CHECK[n]["tris_full_vessel"])
worst_vessel = max(VESSEL_TRIS.values())
PLACES_OF = {f: sum(1 for d in DEFAULT if d == f) for f in FAMILIES}
doc = {
    "store": "Pantry Dresser round 1 (blender/pantry_r1.py): 2.16 m wide, 5 tiers of 8 places, the vessel follows the item",
    "rule": "what you cook with: flours, dough, herbs, spices, feast ingredients and the uncooked dishes waiting for the oven; one kind per place, the vessel is the item's family (jar, tray, crock, sack)",
    "items": ITEMS, "item_family": ITEM_FAMILY, "families": FAMILIES,
    "family_kinds": {f: sorted(n for n in ITEMS if PANTRY[n] == f) for f in FAMILIES},
    "slots": 80, "places": NPLACE, "grid": [NCOL, len(LEVEL)], "units_total": len(units), "units_per_family": {f: sum(1 for u in units if u["kind"] == f) for f in FAMILIES},
    "units_split": ("every one of the %d places has %d units (stacks) for each of the four families: %d x 4 x %d = %d units, %d per family, so any one family can show all 80 slots; "
                    "a full place = %d stacks of one kind, a place holding fewer shows a vessel that is only partly full. Not every stack needs its own place: %d kinds share %d places."
                    % (NPLACE, UNITS_PER, NPLACE, UNITS_PER, len(units), NPLACE * UNITS_PER, UNITS_PER, len(ITEMS), NPLACE)),
    "full_demo": FULL_ASSIGN,
    "stacks_per_place_and_family": UNITS_PER, "stack_per_unit": 1, "placement": "wall",
    "frame": {"obj": "Pantry.obj", "tris": FRAME_TRIS, "size_m": [round(W + 0.07, 3), H + 0.0, DEPTH + 0.06], "atlas": "pantry_atlas.png 128x128 point",
              "atlas_rows": "v px from the bottom: 96-127 hewn, 64-95 end grain, 48-63 iron (byte-identical from bunker_r4), 36-47 clay, 16-23 glass, 12-15 tin (trays), 8-11 hessian (sacks), 4-7 cord, 0-3 swatches cork/ivory/amber/crust/flour/bright glass/worn timber/soot"},
    "space": "Unity prefab space, metres. Origin: the wall plane (back face, z = 0), x centred, y = 0 the foot; front is +z. Blender z-up/-y front -> Unity: ux=-bx, uy=bz, uz=-by. OBJ exported forward -Z, up Y (the mod loads it flipX).",
    "vessel_meshes": {f: "Vessel_%s.obj" % f for f in FAMILIES},
    "vessel_meshes_doc": ("one mesh per family in the same OBJ convention as the frame, in local coordinates: origin = the centre of the vessel's footprint at the shelf "
                          "surface (vessels[].at); draw it at 'at' (no rotation) with the frame's material. Tris: %s." % ", ".join("%s %d" % (f, VESSEL_TRIS[f]) for f in FAMILIES)),
    "vessels": vessels,
    "vessels_doc": ("one entry per place: 'at' = where its vessel stands (prefab space), 'default' = the family the place is for (light on top, heavy below: the order the mod claims "
                    "places in is jar, tray, crock, sack, each kind by name, in reading order; the defaults are the full demo: %s places). An EMPTY place draws nothing. A place holding an "
                    "item draws the vessel of the item's family (item_family): the vessel follows the item. place n = tier * 8 + column; tier 0 is the top, column 0 the left as seen "
                    "from the front (Blender x ascending, Unity x descending)." % ", ".join("%s %d" % (f, PLACES_OF[f]) for f in FAMILIES)),
    "groups": ("place 0..%d = one vessel position (key 'bin' in units_list, which the mod already reads as the group; 'place' repeats it). EVERY place has units for EVERY "
               "family: kind = jar | tray | crock | sack, %d stacks (fill_step 0..%d) each, same position and box in all four. The clear space of every vessel of every "
               "family is the same upright cylinder (radius %.3f, height %.3f) standing on crate_floor_centres[place]." % (NPLACE - 1, UNITS_PER, UNITS_PER - 1, R_C, H_C)),
    "crate_floor_centres": [uvec(fc) for fc in FLOORS],
    "crop_layouts": layouts,
    "crop_layouts_doc": ("crop_layouts: one full vessel per item kind, as apothecary_r2; '_generic' (any other item in any vessel). A place holding n stacks of a kind shows "
                         "stacks[0..n-1] of that kind's layout (%d stacks). Per copy: the item's model scaled uniformly (by 'scale' x its true size where 'scale' is set, else to "
                         "fit_longest_m), turned by rot_quat_xyzw about its bounds centre, that centre at crate_floor_centres[place] + offset. mode 'lie'/'tumble'/'upright': "
                         "physics-settled (stack k dropped onto stacks 0..k-1; 'lie' on the broad side, 'upright' on its foot). Every layout fits its vessel, so it fits every "
                         "place of its family. 'model' says whether the layout was made on the real model or a stand-in (see the file docstring)." % UNITS_PER),
    "liquids": [],
    "unit_semantics": ("units_list: one unit = one stack, %d per place and family in fill order; kind = the family; copies = the generic lump as Fit.Longest copies "
                       "(centre at position + offset), a fallback only." % UNITS_PER),
    "physics": ("heaps: Blender rigid body (Bullet), each copy the convex hull of its item, friction 0.6, restitution 0, damping 0.5/0.95, margin 1 mm, substeps 20, iterations 40, "
                "in the cylinder made of passive box slabs; one copy per kind per drop at one of the three lowest well-supported spots of a 1 cm grid x 8 orientations, "
                "settled, checked inside the cylinder, then frozen; until no copy fits or the kind's cap (~%d item triangles per vessel)." % TRI_PER_VESSEL),
    "checks": {"copies_outside_cylinder_mm_max": COPY_OUT, "cylinder_points_inside_vessel": VES_CYL, "cylinder_points_per_vessel": len(CS),
               "vessel_points_inside_frame": VES_FRAME, "vessel_places_checked": len(ves_frame), "cylinder_points_inside_frame": cyl_frame,
               "frame_vertices_inside_cylinders": fv_in, "vessel_radius_m": {k: round(v, 3) for k, v in RMAX.items()}, "pitch_m": PITCH,
               "rotation_roundtrip_max_err": rt, "sim": SIMST,
               "overlap_between_copies_mm_max": max(CHECK[n]["overlap_max_mm"] for n in KINDS), "float_worst_mm_max": max(CHECK[n]["float_worst_mm"] for n in KINDS)},
    "tris": {"frame": FRAME_TRIS, "vessels": VESSEL_TRIS,
             "full_store_worst_kind": {"item": heaviest, "tris": NPLACE * (CHECK[heaviest]["tris_full_vessel"] + VESSEL_TRIS[PANTRY[heaviest]]) + FRAME_TRIS},
             "full_store_worst_case_any_family": NPLACE * (max(CHECK[n]["tris_full_vessel"] for n in ITEMS) + worst_vessel) + FRAME_TRIS,
             "full_demo": FRAME_TRIS + sum(VESSEL_TRIS[PANTRY[it]] + CHECK[it]["tris_full_vessel"] for it in FULL_ASSIGN if it)},
    "units_list": units,
}
if EXPORT:
    out = os.path.join(OUTA, "pantry_anchors.json"); tmp = out + ".tmp"
    with open(tmp, "w") as fh: json.dump(doc, fh, indent=1)
    os.replace(tmp, out)
    print("PAN1 wrote", out, flush=True)
print("PAN1 STATS frame %d, vessels %s, copies %d, tris %s, roundtrip %.2g" % (FRAME_TRIS, VESSEL_TRIS, sum(c["copies"] for c in CHECK.values()), doc["tris"], rt), flush=True)

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
    # the shipped files, re-imported: the vessels (the frame stays the in-scene one, exported from the same parts)
    PROTO = {}
    for fam in FAMILIES:
        obs = import_obj(os.path.join(OUTA, "Vessel_%s.obj" % fam)) if EXPORT else []
        for o in obs:
            o.data.materials.clear(); o.data.materials.append(MAT); o.hide_render = True; o.hide_viewport = True
        PROTO[fam] = obs
    shown = []
    def put_vessel(fam, org):
        for o in PROTO[fam]:
            c = o.copy(); sc.collection.objects.link(c); c.hide_render = False; c.hide_viewport = False
            c.location = org; shown.append(c)
    def put_item(name, nstacks, org):
        t = ST[name]["t"]
        for b in ST[name]["frozen"]:
            if b["stack"] >= nstacks: continue
            M = np.eye(4); M[:3, :3] = b["R"] * t["s"]; M[:3, 3] = b["c"] + np.array(org + Vector((0, 0, TB)))
            for dta in t["datas"]:
                io = bpy.data.objects.new(name, dta); sc.collection.objects.link(io); io.matrix_world = Matrix(M.tolist()); shown.append(io)
    def fill(assign):
        """assign[n] = (item or None, stacks): the vessel follows the item; None: an empty place stands empty (nothing drawn)"""
        for n in range(NPLACE):
            item, k = assign[n] if n < len(assign) else (None, 0)
            if item is None or item not in ST or k <= 0: continue
            org = place_origin(n)
            put_vessel(PANTRY[item], org); put_item(item, k, org)
    def clear():
        for o in shown: bpy.data.objects.remove(o)
        shown.clear()
    FULL = [(it, UNITS_PER) if it else (None, 0) for it in FULL_ASSIGN]
    seen = set(); HALF = []
    for it in FULL_ASSIGN:                       # half full: every kind on its first place, one stack of two; the second places stand empty
        if it and it not in seen: seen.add(it); HALF.append((it, 1))
        else: HALF.append((None, 0))
    V34 = (-26, 8, 5.4, (0, -0.2, 1.07))
    look(*V34); fill([]); render("pantry1-empty.png")
    fill(HALF); render("pantry1-half.png"); clear()
    fill(FULL); render("pantry1-full.png")
    look(-4, 4, 5.0, (0, -0.24, 1.07)); render("pantry1-full-front.png")
    for tier, nm in ((0, "jars"), (1, "trays-upper"), (2, "trays-lower"), (3, "crocks"), (4, "crocks-sacks")):
        look(-14, 12, 3.6, (0, -0.25, LEVEL[tier] + 0.13)); render("pantry1-closeup-tier%d-%s.png" % (tier, nm))
    # as a player sees it: 2 m from the front, eye height 1.6 m, a wide lens
    cam.data.lens = 20; cam.location = (0.0, -2.46, 1.15); cam.rotation_euler = (math.radians(90), 0, 0)
    render("pantry1-from-2m.png", 1400, 1000); cam.data.lens = 38
    # a 1.8 m post for scale, and the dresser beside apothecary_r2 and bunker_r4 (as shipped, same scale, same ground)
    ap = import_obj(os.path.join(R2DIR, "Apothecary.obj"))
    apm = bpy.data.materials.new("r2"); apm.use_nodes = True
    apt = apm.node_tree.nodes.new("ShaderNodeTexImage"); apt.image = bpy.data.images.load(os.path.join(R2DIR, "apothecary_atlas.png")); apt.interpolation = "Closest"
    apm.node_tree.links.new(apt.outputs["Color"], apm.node_tree.nodes["Principled BSDF"].inputs["Base Color"])
    apm.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.8
    for o in ap: o.data.materials.clear(); o.data.materials.append(apm); o.location = (-4.1, 0, 0)
    bk = import_obj(os.path.join(BUNKER, "Bunker.obj"))
    bmat = bpy.data.materials.new("bunker"); bmat.use_nodes = True
    bt = bmat.node_tree.nodes.new("ShaderNodeTexImage"); bt.image = bpy.data.images.load(os.path.join(BUNKER, "bunker_atlas.png")); bt.interpolation = "Closest"
    bmat.node_tree.links.new(bt.outputs["Color"], bmat.node_tree.nodes["Principled BSDF"].inputs["Base Color"])
    bmat.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.8
    for o in bk: o.data.materials.clear(); o.data.materials.append(bmat); o.location = (4.4, -1.12, 0)
    look(-8, 8, 14.2, (0.15, -0.5, 0.95)); render("pantry1-full-beside-apothecary_r2-bunker_r4.png", 2000, 900)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(1.75, -0.7, 0.9)); post = bpy.context.active_object; post.scale = (0.1, 0.1, 1.8)
    pm = bpy.data.materials.new("post"); pm.use_nodes = True
    pm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.85, 0.85, 0.88, 1); post.data.materials.append(pm)
    look(-8, 5, 5.8, (0.2, -0.2, 1.07)); render("pantry1-full-post-1.8m.png")
    bpy.data.objects.remove(post)
print("DONE %.0fs" % (time.time() - t0))
