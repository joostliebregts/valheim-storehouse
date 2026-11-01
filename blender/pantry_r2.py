"""Pantry Dresser round 2 (Joost, 24 Oct): round 1's dresser with the vessels and layouts fixed so every kind lies the way a cook keeps it, and the 32 REAL item models.
Joost on r1's tray row: pies and dishes stacked into towers and the mushrooms piled on edge are "physically very illogical; better put them in a basket or so".
Same dresser (2.16 W x 0.46 D x 2.14 H, 5 tiers of 8 = 40 places, 80 slots, 32 kinds), the same schema as apothecary_r2 / pantry_r1 (vessel_meshes, vessels with "at" and
"default", units per place and family with "bin"/"place" and "kind" = family, crate_floor_centres, crop_layouts per item, item_family, families), the vessel follows the item.
  jar      Spice (Forests, Plains, Mountains, Oceans, Mistlands, Deep North, Ashlands)   glass jar, open at the front, cork: the pouches lie heaped in it          7 kinds
  board    Bread dough                                                                   a bread board, floured; the dough lumps lie on it                         1 kind
  basket   Fragrant bundle, Fish and bread, Magically stuffed shroom, Viking cupcake    wicker basket with a rope rim: herbs lie criss-cross, loaves and shrooms heaped, cupcakes standing     4 kinds
  platter  the 9 uncooked dishes that come in their own tin, bowl or plate: Baked poteitr, Honey glazed chicken, Kale chips, Lox pie, Meat platter, Misthare supreme,
           Oven pancake, Piquant pie, Roasted crust pie    a timber board with a low rim: the dishes lie FLAT, side by side in neat rows; pies and pans (flat tops) at most 2 high,
                                                           directly on one another; every other dish one layer                                                       9 kinds
  crock    the 9 Feast ingredients (Meadows, Black Forest, Swamps, Mountains, Plains, Oceans, Deep North, Mistlands, Ashlands)   bellied clay crock with a cord        9 kinds
  sack     Barley flour, Oat flour                                                       squat hessian sack with a rolled cuff and a cord                          2 kinds
Never two kinds in one vessel. Light on top, heavy below: the mod claims places in reading order, families jar, board, basket, platter, crock, sack (tier 0 = top), each kind
by name; the full render and the defaults follow that: tier 0 the jars (7 kinds on 8 places), tier 1 the board (1), the baskets (4 kinds on 5), the first 2 platters, tier 2 the
other 8 platters (9 kinds on 10), tiers 3 and 4 the crocks (9 kinds on 13) and the sacks (2 on 3). Empty places stand empty (the mod draws nothing there); "default" only says
which family a place is for.
Units: every place has 2 stacks for EVERY family (the mod's perPlace logic keys on (place, family)): 40 x 6 x 2 = 480 units, 80 per family, so any one family can show all 80
slots; a place holding fewer than 2 stacks shows a vessel that is only partly full: stack 0 is the FRONT row (platter, board) or the first half of a heap; stack 1 the back row,
the second layer (pies and pans) or the rest of the heap.
Clear space: the round vessels (jar, basket, crock, sack) keep r1's upright cylinder R_C 0.090 x H_C 0.22 on a floor at origin + 0.02 (= crate_floor_centres[place]); the platter and
the board a box 0.19 x 0.216 (x, y) x 0.20 on the same floor (the dresser is 0.46 deep, the vessel 0.226 x 0.25 at the 0.24 m pitch). A unit's "box" says which.
Platter and board layouts are placed, not poured (a cook lines the dishes up): each dish lies in the pose it has in the rip (its own plate or tin down), turned a few degrees, resting
on the floor or, one layer up, on the dishes below it (hull against height field, 1 mm gap); the heaps (jars, baskets, crocks, sacks) are physics-settled as in r1.
Also changed from r1 (Joost, 24 Oct: no z-fighting): the frame and the six vessels have NO two same-facing faces in one plane that overlap (report_coplanar, tolerance 2 mm; r1's frame had 25 such pairs,
the r2 vessels 395 in their first build, now 0 everywhere: iron band / bracket / strap / plinth / back-board offsets, the jar's foot, the sack's cuff and the basket's rim and binding as lathed shells, the
board's flour as one slab). The crock is squat (0.6 of its height) so the flat feast platters fill it to the rim, the sack 0.8.
Run: "C:/Program Files/Blender Foundation/Blender 4.5/blender.exe" -b -P pantry_r2.py -- [--out DIR] [--no-render] [--quick] [--no-export]

Dimensions: Blender x, y, z; -y = front, back face y = 0 at the wall, x centred, z = 0 the foot. Tiers (shelf tops) at 1.63, 1.25, 0.87, 0.49, 0.11 m; places 0.24 m apart
(x = -0.84 ... 0.84), vessel centre y = -0.25. n = tier * 8 + column, tier 0 the top, column 0 the left as seen from the front (Blender x ascending, Unity x descending).
Vessels are at most 0.116 in radius / half-width (24 cm pitch), at most 0.31 high (the shelf above is 0.33 up).

THE ITEM MODELS: all 32 kinds are the real Valheim 1.0 prefabs, ripped with scripts/items_extract.py (a wrapper around its extract() for the 32 names; the shared script is untouched)
into C:/Users/joost/ValheimRip/items/<Prefab>/. No stand-ins: every layout carries "scale" (the prefab's own size times it = the drawn size) and fit_longest_m; rotations are about the
model's bounds centre as in every store. What the rip shows: the twelve "Uncooked" dishes bring their own tin, bowl or plate (so they lie flat on the platter and never tower), the
spice is a flat paper pouch, the flours are sacks themselves, and the nine Feast ingredients are big heavy platters (2.5k-14k triangles each, so a crock holds 2-4 copies).

Atlas 128 x 128 (point filtered, 48 px/m): bunker_r4's timber, end grain and iron rows byte-identical; clay, glass, cord and swatches as apothecary_r2; wicker rows 24-35 copied from
apothecary_r2's atlas (the baskets); rows 8-11 the hessian tile (sacks), rows 12-15 a tin tile (kept from r1's layout); swatches cork/ivory/amber/crust/flour/bright glass/worn timber/soot.
Files (assets/pantry_r2/): Pantry.obj (frame only), Vessel_{jar,board,basket,platter,crock,sack}.obj (local coordinates, origin = centre of the footprint at the shelf surface),
pantry_atlas.png, pantry_anchors.json (last, temp + rename). Unity prefab space: ux = -bx, uy = bz, uz = -by (OBJ exported forward -Z, up Y, like every store).
"""
import bpy, bmesh, sys, os, math, json, random, time, zlib
import numpy as np
from mathutils import Vector, Matrix, Euler, Quaternion
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, ".."))
OUTA = os.path.join(REPO, "assets", "pantry_r2")
BUNKER = os.path.join(REPO, "assets", "bunker_r4")
R2DIR = os.path.join(REPO, "assets", "apothecary_r2")
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
def arg(k, d=None): return argv[argv.index(k) + 1] if k in argv else d
OUT = arg("--out", "C:/Users/joost/AppData/Local/Temp/claude/C--Users-joost--pai/5e4bc60b-cdfe-4638-8e29-2e507fa13cf9/scratchpad/pantry_r2")
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
    "BreadDough": "board",
    "FragrantBundle": "basket", "FishAndBreadUncooked": "basket", "MagicallyStuffedShroomUncooked": "basket", "VikingCupcakeUncooked": "basket",
    "BakedPoteitrUncooked": "platter", "HoneyGlazedChickenUncooked": "platter", "KaleChipsUncooked": "platter", "LoxPieUncooked": "platter", "MeatPlatterUncooked": "platter",
    "MisthareSupremeUncooked": "platter", "OvenPancakeUncooked": "platter", "PiquantPieUncooked": "platter", "RoastedCrustPieUncooked": "platter",
    "FeastAshlands_Material": "crock", "FeastBlackforest_Material": "crock", "FeastDeepNorth_Material": "crock", "FeastMeadows_Material": "crock",
    "FeastMistlands_Material": "crock", "FeastMountains_Material": "crock", "FeastOceans_Material": "crock", "FeastPlains_Material": "crock", "FeastSwamps_Material": "crock",
    "BarleyFlour": "sack", "OatFlour": "sack",
}
ITEMS = list(PANTRY)
FAMILIES = ["jar", "board", "basket", "platter", "crock", "sack"]            # the order the mod claims places in: light on top, heavy below
LIQUIDS = []
if QUICK: ITEMS = ["SpiceForests", "SpicePlains", "BreadDough", "FragrantBundle", "VikingCupcakeUncooked", "LoxPieUncooked", "PiquantPieUncooked", "MeatPlatterUncooked", "FeastMeadows_Material", "FeastOceans_Material", "BarleyFlour"]
PANTRY = {k: v for k, v in PANTRY.items() if k in ITEMS}

rng = random.Random(7)
TEX = 128
DENS = 48.0
STRIP = {"hewn": 0.75, "end": 0.50, "iron": 0.375}
STRIPH = {"hewn": 32, "iron": 16}
ROWS = {"clay": (36, 12), "wicker": (24, 12), "glass": (16, 8), "rope": (4, 4), "sack": (8, 4), "tin": (12, 4)}
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
    wk = bpy.data.images.load(os.path.join(R2DIR, "apothecary_atlas.png"))                  # wicker rows 24-35: apothecary_r2's, byte for byte
    wpx = np.array(wk.pixels[:], np.float32).reshape(TEX, TEX, 4)[..., :3]
    img[24:36] = wpx[24:36]
    bpy.data.images.remove(wk)
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
SHARE = {"jar": 8, "board": 1, "basket": 5, "platter": 10, "crock": 13, "sack": 3}   # places per family in the full demo (and the defaults): 7 / 1 / 4 / 9 / 9 / 2 kinds on 8 / 1 / 5 / 10 / 13 / 3 places
CLEAR = {"jar": "cyl", "crock": "cyl", "sack": "cyl", "basket": "cyl", "platter": "rect", "board": "rect"}      # the shape of a family's clear space
HX, HY, H_R = 0.095, 0.108, 0.20            # the clear space of the platter and the board: half-width, half-depth, height (z = TB above the shelf)
PHX, PHY = 0.114, 0.126                     # their vessels' half-width and half-depth
def full_assign():
    """every kind in the order the mod claims places (families jar, board, basket, platter, crock, sack; then by name); a family takes its SHARE of the places, the first
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

def in_box(P, eps=0.0015):
    return (P[:, 2] >= min(eps, 0.0) - 0.0002) & (P[:, 2] <= H_R - eps) & (np.abs(P[:, 0]) <= HX - eps) & (np.abs(P[:, 1]) <= HY - eps)

def outside_box(P):
    return float(np.max(np.maximum.reduce([-P[:, 2], P[:, 2] - H_R, np.abs(P[:, 0]) - HX, np.abs(P[:, 1]) - HY])))

def in_clear(P, fam, eps=0.0015): return in_box(P, eps) if CLEAR.get(fam, "cyl") == "rect" else in_cyl(P, eps)
def outside_clear(P, fam): return outside_box(P) if CLEAR.get(fam, "cyl") == "rect" else outside_cyl(P)
def wall_gap(P, fam):
    """distance of the points from the clear space's walls (the layouts keep clear of them)"""
    if CLEAR.get(fam, "cyl") == "rect": return float(min((HX - np.abs(P[:, 0])).min(), (HY - np.abs(P[:, 1])).min()))
    return float((R_C - COL_IN - np.hypot(P[:, 0], P[:, 1])).min())

# ---------- the six vessels, in local coordinates (origin = centre of the footprint at the shelf surface) ----------
KRJ, KZJ = 0.95, 0.92                       # glass jar: apothecary_r2's, scaled to the 24 cm pitch
KRC = 0.88                                  # clay crock: apothecary_r2's, but squat (KZC): a wide pot the flat feast platters fill to the rim, so it reads full from the front
KZC = 0.60
KZS = 0.80                                  # the sack: lower, so the flour sacks in it show above the cuff
VESSEL_PROF = {
    "jar": dict(prof=[(0.116 * KRJ, 0.004), (0.119 * KRJ, 0.02 * KZJ), (0.119 * KRJ, 0.262 * KZJ), (0.111 * KRJ, 0.285 * KZJ)], t=0.008 * KRJ),
    "crock": dict(prof=[(r * KRC, z * KZC) for r, z in ((0.121, 0.0), (0.126, 0.04), (0.129, 0.085), (0.125, 0.12), (0.122, 0.14), (0.126, 0.152))], t=0.014 * KRC),
    "sack": dict(prof=[(r * 0.985, z * KZS) for r, z in ((0.106, 0.0), (0.108, 0.025), (0.114, 0.06), (0.113, 0.10), (0.109, 0.128), (0.1085, 0.145), (0.110, 0.153))], t=0.011),
    # a round wicker basket, 0.126 high with a rope rim: the inside is wider than the clear cylinder (0.094 at the floor, 0.103 at the rim), the outside at most 0.113
    "basket": dict(prof=[(0.104, 0.0), (0.108, 0.03), (0.111, 0.07), (0.113, 0.105), (0.113, 0.122)], t=0.010),
}

def build_platter():
    """a timber serving board 0.228 x 0.252 with a low rim (25 mm) set 4 mm in from its edge: a base 20 mm thick, four rim planks sunk into it, iron corner caps with rivets; the dishes lie on its floor"""
    t = 0.012; hr = 0.025; ins = 0.004; z0 = 0.012
    timber("platterbase", (2 * PHX, 2 * PHY, TB), (0, 0, TB / 2), jitter=0.0008, bevel=0.003)
    zc = lambda top: (z0 + top) / 2; hh = lambda top: top - z0
    tf, tb_ = TB + hr, TB + hr + 0.012
    plank("rimF", (2 * (PHX - ins) - 0.008, t, hh(tf)), (0, -(PHY - ins) + t / 2, zc(tf)), jitter=0.0006)
    plank("rimB", (2 * (PHX - ins) - 0.008, t, hh(tb_)), (0, (PHY - ins) - t / 2, zc(tb_)), jitter=0.0006)       # a taller back rim: the dishes cannot slide off the back
    for sx in (-1, 1): plank("rimS", (t, 2 * (PHY - ins) - 2 * t + 0.008, hh(tf)), (sx * (PHX - ins - t / 2), 0, zc(tf)), jitter=0.0006)
    for sx in (-1, 1):
        for sy in (-1, 1):
            top = tb_ if sy > 0 else tf
            cx, cy = sx * (PHX - ins - 0.006), sy * (PHY - ins - 0.006)                                               # on the rim itself: outside the clear box (x > 0.095, |y| > 0.108)
            iron("cap", (0.014, 0.014, 0.005), (cx, cy, top + 0.001))
            iron("rivet", (0.007, 0.007, 0.008), (cx, cy, top + 0.0075))
    for sx in (-1, 1):
        iron("strap", (0.045, 0.004, 0.014), (sx * 0.07, -PHY - 0.0015, 0.010))                                        # two iron straps on the front edge of the base
        iron("rivet", (0.010, 0.006, 0.010), (sx * 0.07, -PHY - 0.005, 0.010))

def build_board():
    """a bread board 0.224 x 0.25, no rim, a hewn top; a few floured patches on it (thin, flush with the floor level)"""
    timber("board", (2 * PHX, 2 * PHY, TB - 0.005), (0, 0, (TB - 0.005) / 2), jitter=0.0008, bevel=0.004)
    timber("flourdust", (2 * HX, 2 * HY, 0.006), (0, 0, TB - 0.003), kind="flour", jitter=0.0004, bevel=0.0025)        # a floured patch, its top at the floor level of the vessel
    for sx in (-1, 1):
        cord("score", (sx * 0.1055, -0.09, TB - 0.0035), (sx * 0.1055, 0.09, TB - 0.0035), 0.004, "soot")                  # knife scores near the rim
    iron("hang", (0.03, 0.006, 0.018), (0, PHY + 0.001, 0.010))                                                      # a hanging lug at the back edge

def build_vessel(fam):
    o = Vector((0, 0, 0))
    if fam == "jar":
        v = VESSEL_PROF["jar"]; half = math.radians(62); front = -math.pi / 2
        shell("jar", v["prof"], v["t"], "glass", SEG, arc=(front + half, front - half + 2 * math.pi), bottom=False, at=o)
        disc("jarbase", 0.106, 0.106, 0.0, TB, "glass", o, SEG)                     # a foot a little narrower than the glass; the glass starts 4 mm up, its bottom ring hidden inside the foot
        shell("jarrim", [(0.110 * KRJ, 0.282 * KZJ), (0.111 * KRJ, 0.300 * KZJ)], 0.012 * KRJ, "glassbright", 12, bottom=False, at=o)
        disc("cork", 0.094 * KRJ, 0.086 * KRJ, 0.292 * KZJ, 0.334 * KZJ, "cork", o, 12)
    elif fam == "crock":
        v = VESSEL_PROF["crock"]
        shell("crock", v["prof"], v["t"], "clay", SEG, bottom=True, tb=TB, at=o, rotz=rng.uniform(0, 2 * math.pi))
        ring("crockcord", 0.1235 * KRC, 0.128 * KZC, 0.011 * KRC, o, "rope", 10, 0.0)
    elif fam == "sack":
        v = VESSEL_PROF["sack"]
        sk = shell("sack", v["prof"], v["t"], "sack", 16, bottom=True, tb=TB, at=o, rotz=rng.uniform(0, 2 * math.pi))
        ph = rng.uniform(0, 6.28)
        for vt in sk.data.vertices:                                                         # a cloth sack is not a lathe: soft folds, only ever outwards (the clear space stays clear)
            a = math.atan2(vt.co.y, vt.co.x); f = 1.012 + 0.012 * math.sin(3 * a + 11 * vt.co.z + ph) + 0.006 * math.sin(5 * a - 7 * vt.co.z)
            vt.co.x *= f; vt.co.y *= f
        shell("sackcuff", [(0.115, 0.142 * KZS), (0.1155, 0.160 * KZS)], 0.018, "sack", 16, bottom=False, at=o, rotz=rng.uniform(0, 2 * math.pi))      # the rolled-down cuff (a roll of cloth, one piece)
        ring("sackcord", 0.108, 0.100 * KZS, 0.008, o, "rope", 12, 0.0)                         # the cord round the belly
        for k in range(4): cord("seam", (0.0, -0.111, (0.03 + 0.025 * k) * KZS), (0.004, -0.111, (0.046 + 0.025 * k) * KZS), 0.006, "soot")        # a sewn seam down the front
    elif fam == "basket":
        v = VESSEL_PROF["basket"]
        shell("basket", v["prof"], v["t"], "wicker", SEG, bottom=True, tb=TB, at=o, rotz=rng.uniform(0, 2 * math.pi))
        shell("basketrim", [(0.1155, 0.112), (0.1155, 0.127)], 0.009, "rope", 16, bottom=False, at=o)       # the rope rim: a ring 2.5 mm proud of the wall, its inner side inside the wall
        shell("basketband", [(0.1135, 0.052), (0.1135, 0.064)], 0.006, "rope", 16, bottom=False, at=o)     # a binding round the belly
    elif fam == "platter": build_platter()
    else: build_board()

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
    for bi, (a, b) in enumerate(zip(xs[:-1], xs[1:])):       # alternate boards 4 mm shorter and 3 mm further forward: where two overlap their faces are not in one plane
        odd = bi % 2; hh = TOPB - 0.06 - 0.008 * odd
        plank("back", (b - a + 0.012, YBACK[1] - YBACK[0], hh), ((a + b) / 2, sum(YBACK) / 2 - 0.003 * odd, 0.06 + 0.004 * odd + hh / 2), rot=(0, j(0.3), 0))
    for y in (-DEPTH + 0.05, -0.12):
        timber("sill", (2 * XIN + 0.02, 0.10, 0.06), (0, y, 0.03), jitter=0.006, bevel=0.012)
    plank("plinth", (2 * XIN + 0.012, 0.04, 0.09), (0, YF0 + 0.02, 0.055), jitter=0.004)                                    # a kick plate under the floor board
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
            iron("strap", (0.15, 0.008, 0.045), (sx * (XIN - 0.075), YF0 - 0.002, top - SHELF_T / 2 if top != TOPB - 0.06 else top - 0.03))
            rivet((sx * (XIN - 0.11), YF0 - 0.006, top - SHELF_T / 2 if top != TOPB - 0.06 else top - 0.03), (1, -1))
        iron("band", (PS + 0.024, PS + 0.024, 0.05), (sx * PX, (YF0 + YF1) / 2, 0.06))
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

# ---------- coplanar check (round 2): faces that face the same way, lie in one plane and overlap z-fight in the game ----------
def _clip_area(subj, clipper):
    """Area of the intersection of two convex 2D polygons (Sutherland-Hodgman); both counter-clockwise or both clockwise."""
    def orient(poly): return sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1] for i in range(len(poly)))
    sg = 1.0 if orient(clipper) >= 0 else -1.0
    out = list(subj)
    for i in range(len(clipper)):
        a, b = clipper[i], clipper[(i + 1) % len(clipper)]
        inp, out = out, []
        if not inp: break
        def side(p): return sg * ((b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0]))
        for k in range(len(inp)):
            p, q = inp[k], inp[(k + 1) % len(inp)]
            sp, sq = side(p), side(q)
            if sp >= 0: out.append(p)
            if (sp >= 0) != (sq >= 0):
                t = sp / (sp - sq); out.append((p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])))
    return abs(orient(out)) / 2 if len(out) >= 3 else 0.0

def coplanar_overlaps(parts, tol=0.002, min_area=2e-7, facing=1):
    """parts: [(name, mesh)] in world space. Every pair of triangles that (facing=1) face the same way or (facing=-1) face
    each other, whose planes are within tol (m) of each other and whose projections overlap by more than min_area (m2).
    Returns [(area, name_a, name_b, centre, normal, gap)] sorted by area, largest first."""
    P, Tn, own = [], [], []
    for nm, me in parts:
        V = np.array([tuple(v.co) for v in me.vertices], float)
        for pl in me.polygons:
            vs = list(pl.vertices)
            for i in range(1, len(vs) - 1): P.append(V[[vs[0], vs[i], vs[i + 1]]]); own.append(nm)
    P = np.array(P)
    N = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0]); A = np.linalg.norm(N, axis=1) / 2
    ok = A > 1e-9
    N = N / np.where(ok, 2 * A, 1)[:, None]
    res = []
    for i in np.nonzero(ok)[0]:
        j = np.arange(i + 1, len(P))
        j = j[ok[j]]
        j = j[(N[j] @ N[i]) * facing > 0.9995]
        if not len(j): continue
        dist = np.einsum("jkc,c->jk", P[j] - P[i][0], N[i])
        near = (np.abs(dist).max(1) <= tol) if facing > 0 else (np.abs(dist).max(1) <= tol)
        for jj in j[near]:
            n = N[i]; ax = int(np.argmax(np.abs(n))); keep = [a for a in range(3) if a != ax]
            a2 = [tuple(q[keep]) for q in P[i]]; b2 = [tuple(q[keep]) for q in P[jj]]
            ar = _clip_area(a2, b2)
            if ar > min_area:
                gap = float(np.mean(np.einsum("kc,c->k", P[jj] - P[i][0], n)))
                res.append((ar, own[i], own[jj], ((P[i].mean(0) + P[jj].mean(0)) / 2).round(3).tolist(), n.round(2).tolist(), round(gap, 4)))
    res.sort(key=lambda r: -r[0])
    return res

def report_coplanar(parts, label):
    same = coplanar_overlaps(parts, facing=1)
    back = coplanar_overlaps(parts, facing=-1)
    print(f"COPLANAR {label}: same-facing overlapping pairs {len(same)} (0 expected); back-to-back pairs {len(back)} (hidden, informational)", flush=True)
    import re, collections
    agg = collections.OrderedDict()
    for r in same:
        key = (re.sub(r"\.\d+$", "", r[1]), re.sub(r"\.\d+$", "", r[2]), tuple(int(round(a)) for a in r[4]), round(r[5] * 1000, 1))
        e = agg.setdefault(key, [0, 0.0, r[3]]); e[0] += 1; e[1] += r[0]
    for key, (n, ar, c) in sorted(agg.items(), key=lambda kv: -kv[1][1]):
        print("  SAME", key[0], "x", key[1], "normal", key[2], "gap_mm", key[3], "pairs", n, f"area {ar * 1e4:.1f}cm2", "e.g. at", c, flush=True)
    agg = collections.OrderedDict()
    for r in back:
        key = (re.sub(r"\.\d+$", "", r[1]), re.sub(r"\.\d+$", "", r[2]), tuple(abs(int(round(a))) for a in r[4]))
        e = agg.setdefault(key, [0, 0.0, r[3]]); e[0] += 1; e[1] += r[0]
    for key, (n, ar, c) in sorted(agg.items(), key=lambda kv: -kv[1][1]):
        print("  BACK", key[0], "x", key[1], "axis", key[2], "pairs", n, f"area {ar * 1e4:.1f}cm2", "e.g. at", c, flush=True)
    return {"same_facing_overlaps": len(same), "back_to_back": len(back), "tolerance_mm": 2.0, "min_area_cm2": 0.002}

COP = {}
# vessels first: one joined object per family, exported, their parts kept as data for the checks
rng.seed(7)
VESSEL_PARTS, VESSEL_TRIS = {}, {}
for fam in FAMILIES:
    PARTS = []
    build_vessel(fam)
    VESSEL_PARTS[fam] = part_data(PARTS)
    VESSEL_TRIS[fam] = tris(PARTS)
    COP[fam] = report_coplanar([(o.name, o.data) for o in PARTS], "vessel " + fam)
    print("PAN2 vessel %-8s parts %d tris %d" % (fam, len(PARTS), VESSEL_TRIS[fam]), flush=True)
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
COP["frame"] = report_coplanar([(o.name, o.data) for o in FRAME_PARTS], "frame")
print("PAN2 frame tris", FRAME_TRIS, "parts", len(FRAME_PARTS), flush=True)
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

# ---- the item models: all 32 are the real prefabs (C:/Users/joost/ValheimRip/items/<Prefab>/) ----
# How each kind lies (what a cook would do), per kind:
#   HEAP (physics-settled in a round vessel): mode "pile" = on its broad side, tilts up to 18 degrees (flat pouches heaped in a jar, none on edge); "lie" = on its broad side, tilts up to 15 (herb bundles criss-cross);
#   "natural" = in the pose it has in the rip, tilts up to 25 (loaves and mushrooms in a basket, big feast platters in a crock, flour sacks in a sack); "upright" = in its rip pose on its foot, yaw only (cupcakes).
#   GRID (placed, platter and board): (cols, rows, layers): cols x rows dishes per layer, every dish flat in its rip pose, layers = how many dishes high (only flat-topped pies and pans stack).
HEAP = {
    "SpiceForests": ("pile", 0.092, 14), "SpicePlains": ("pile", 0.092, 14), "SpiceMountains": ("pile", 0.092, 14), "SpiceOceans": ("pile", 0.092, 14),
    "SpiceMistlands": ("pile", 0.092, 14), "SpiceDeepNorth": ("pile", 0.092, 14), "SpiceAshlands": ("pile", 0.092, 14),
    "FragrantBundle": ("lie", 0.15, 6), "FishAndBreadUncooked": ("natural", 0.115, 5), "MagicallyStuffedShroomUncooked": ("natural", 0.105, 7), "VikingCupcakeUncooked": ("upright", 0.082, 10),
    "BarleyFlour": ("natural", 0.105, 6), "OatFlour": ("natural", 0.12, 6),
}
for _n in PANTRY:
    if _n.startswith("Feast"): HEAP[_n] = ("natural", 0.145, 4)
GRID = {
    "BreadDough": (1, 2, 1),
    "LoxPieUncooked": (2, 2, 2), "PiquantPieUncooked": (2, 2, 2), "RoastedCrustPieUncooked": (2, 2, 2),
    "MisthareSupremeUncooked": (2, 2, 1), "BakedPoteitrUncooked": (2, 2, 1), "HoneyGlazedChickenUncooked": (2, 2, 1), "KaleChipsUncooked": (2, 2, 1),
    "OvenPancakeUncooked": (1, 2, 2), "MeatPlatterUncooked": (1, 2, 1),
}
TILT = {"pile": 18, "lie": 15, "natural": 25, "upright": 8}
HEAP = {k: v for k, v in HEAP.items() if k in PANTRY}; GRID = {k: v for k, v in GRID.items() if k in PANTRY}
assert set(HEAP) | set(GRID) == set(PANTRY) and not (set(HEAP) & set(GRID)), (set(PANTRY) - set(HEAP) - set(GRID))

V_CYL = math.pi * R_C ** 2 * H_C
TRI_PER_VESSEL = 5400                       # item triangles a full vessel may hold
TRI_FEAST = 12000                           # the feast platters are 2.5k-14k triangles each: two to four copies
TPL = {}
def tpl(name):
    """name: an item or '_generic' (heap lump)"""
    if name in TPL: return TPL[name]
    if name == "_generic": datas = [lump_mesh()]
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
    ent = dict(datas=datas, verts=verts, size=size, A=A, tris=ntri, hv=hv, F=F, N=np.array(N), D=np.array(D), vol=vol)
    if name == "_generic": mode, Lb, cap = "tumble", 0.09, 12
    elif name in GRID: mode, Lb, cap = "grid", None, 8
    else:
        mode, Lb, cap = HEAP[name]
        budget = TRI_FEAST if name.startswith("Feast") else TRI_PER_VESSEL
        cap = int(max(2, min(cap, budget // max(ntri, 1))))
    ent.update(mode=mode, cap=cap)
    if Lb is not None:
        ent["s"] = Lb / ss[0]
    ent["tilt"] = TILT.get(mode, 0)
    pm = bpy.data.meshes.new("prox_" + name)
    ent.setdefault("s", 1.0)
    pm.from_pydata([tuple(v * ent["s"]) for v in hv], [], [tuple(int(i) for i in f) for f in F]); pm.update()
    ent["prox"] = pm
    TPL[name] = ent
    return ent


# ---------- the settle (r1's; one cylinder per kind side by side; only the heaps of the round vessels) ----------
CELL = 0.005
class HF:
    def __init__(self, fam="jar"):
        self.n = 48; self.x0 = -0.12
        self.h = np.zeros((self.n, self.n))
        g = (np.arange(self.n) + 0.5) * CELL + self.x0
        self.X, self.Y = np.meshgrid(g, g, indexing="ij")
        if CLEAR.get(fam, "cyl") == "rect": self.mask = (np.abs(self.X) <= HX - 0.004) & (np.abs(self.Y) <= HY - 0.004)
        else: self.mask = np.hypot(self.X, self.Y) <= R_C - 0.004
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

GSTEP = 0.010
GXY = [(x, y) for x in np.arange(-R_C, R_C + 1e-9, GSTEP) for y in np.arange(-R_C, R_C + 1e-9, GSTEP) if math.hypot(x, y) <= R_C - 0.008]
def lowest_spot(st, h, rr):
    t = st["t"]; s = t["s"]; cands = []
    for _o in range(8):
        tl = t["tilt"]
        if t["mode"] in ("lie", "pile"): R = np.array(Rz(rr.uniform(0, 360)) @ Rx(rr.uniform(-tl, tl)) @ Ry(rr.uniform(-tl, tl))) @ t["A"]
        elif t["mode"] in ("upright", "natural"): R = np.array(Rz(rr.uniform(0, 360)) @ Rx(rr.uniform(-tl, tl)) @ Ry(rr.uniform(-tl, tl)))
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
        ST[name] = dict(t=t, ox=ox, hf=HF(), hfl=HF(), frozen=[], fails=0, done=False)      # heaps are all in round vessels
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
                print("PAN2 %-20s full: %2d copies (cap %d), scale %.3f, level %.3f, top %.3f, stacks %s" % (name, n, s["t"]["cap"], s["t"]["s"], s["hfl"].level(),
                      max(float(b["HV"][:, 2].max()) for b in s["frozen"]) if n else 0, [cut[k + 1] - cut[k] for k in range(UNITS_PER)]), flush=True)
    for o in [o for o in bpy.data.objects if o.rigid_body is not None]: bpy.data.objects.remove(o)
    bpy.ops.rigidbody.world_remove()
    sc.frame_set(1)
    return ST, stats

HEAPKINDS = [n for n in ITEMS if n in HEAP] + ["_generic"]
ST, SIMST = settle(HEAPKINDS)
print("PAN2 SIM", SIMST, "%.0fs" % (time.time() - t0), flush=True)

# ---------- the placed layouts: platter and board (a cook lines the dishes up) ----------
def hull_bvh(b, t):
    return BVHTree.FromPolygons([Vector(v) for v in b["HV"]], [tuple(int(i) for i in f) for f in t["F"]])

def grid_layout(name):
    """cols x rows dishes per layer, all flat in the pose they have in the rip (yaw 0 or 90, whichever lets them grow larger, a few degrees of turn), layers high: each rests on the
    floor or on the dishes below (hull against height field + 1 mm). Stack = the layer when there are two, else the row (0 = the front row)."""
    fam = PANTRY[name]; rr = random.Random(zlib.crc32(name.encode()))
    t = tpl(name); cols, rows, layers = GRID[name]
    cw, cd = 2 * HX / cols, 2 * HY / rows
    best = None
    for yaw in (0, 90):
        R0 = np.array(Rz(yaw)); HV0 = t["hv"] @ R0.T; fw, fd = (HV0.max(0) - HV0.min(0))[:2]
        sc_ = min(cw * 0.90 / fw, cd * 0.90 / fd)
        if best is None or sc_ > best[0] + 1e-9: best = (sc_, yaw)
    s_, yaw0 = best
    t["s"] = s_
    hf, hfl = HF(fam), HF(fam); frozen = []
    for L in range(layers):
        new = []
        for j in range(rows):                                 # row 0 = the front row (low y)
            for i in range(cols):
                x = -HX + (i + 0.5) * cw; y = -HY + (j + 0.5) * cd
                R = np.array(Rz(yaw0 + rr.uniform(-3, 3)))
                HVr = (t["hv"] * s_) @ R.T; Nr = t["N"] @ R.T; Dr = t["D"] * s_
                lo, hi = HVr.min(0), HVr.max(0)
                rest, idx, sup = drop_z(hf, hf.h, Nr, Dr, lo, hi, x, y)
                c = np.array((x, y, rest + (0.0005 if L == 0 else 0.001)))
                if L > 0:                                          # the height field is dilated by a cell: lower the dish in 0.25 mm steps until its hull just touches the dish below
                    below = [b for b in frozen if b["layer"] == L - 1 and (np.abs(b["c"][:2] - c[:2]) < 0.05).all()]
                    bvs = [hull_bvh(b, t) for b in below]
                    for _k in range(60):
                        c2 = c - np.array((0, 0, 0.00025))
                        me = BVHTree.FromPolygons([Vector(v) for v in (HVr + c2)], [tuple(int(i) for i in f) for f in t["F"]])
                        if any(me.overlap(bv) for bv in bvs) or c2[2] + lo[2] < 0: break
                        c = c2
                    c[2] += 0.0005
                new.append(dict(R=R, c=c, id=len(frozen) + len(new), HV=HVr + c, N=Nr, D=Dr + Nr @ c, stack=(L if layers > 1 else j), layer=L, sup=round(sup, 2)))
        for b in new: hf.add(b["N"], b["D"]); hfl.add(b["N"], b["D"], dilate=False)
        frozen += new
    top = max(float(b["HV"][:, 2].max()) for b in frozen)
    print("PAN2 %-32s placed: %d copies (%dx%dx%d), scale %.3f, yaw %d, top %.3f, support %s" % (name, len(frozen), cols, rows, layers, s_, yaw0, top, [b["sup"] for b in frozen]), flush=True)
    return dict(t=t, ox=0.0, hf=hf, hfl=hfl, frozen=frozen, fails=0, done=True)
for _n in GRID: ST[_n] = grid_layout(_n)
for _n, _s in ST.items():
    _e = [k for k in range(UNITS_PER) if not any(b["stack"] == k for b in _s["frozen"])]
    if _e: print("PAN2 WARNING empty stack", _n, _e, flush=True)
KINDS = [n for n in ITEMS] + ["_generic"]

# ---------- checks on the layouts ----------
def hull_bvh(b, t):
    return BVHTree.FromPolygons([Vector(v) for v in b["HV"]], [tuple(int(i) for i in f) for f in t["F"]])
def float_pen(name):
    s = ST[name]; t = s["t"]; fr = s["frozen"]; gaps = []; pen = 0.0
    for b in fr:
        P = b["HV"]; span = P[:, 2].max() - P[:, 2].min()
        low = P[P[:, 2] <= P[:, 2].min() + 0.35 * span + 1e-6]
        g = min(float(low[:, 2].min()), wall_gap(low, PANTRY.get(name, "jar")))
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

def grid_gap(name):
    """placed layouts: how far above its support each dish hangs: the gap from its lowest vertices to the nearest lower dish's hull (layer 1) or to the floor (layer 0)"""
    s = ST[name]; t = s["t"]; fr = s["frozen"]; worst = 0.0
    for b in fr:
        P = b["HV"]; low = P[P[:, 2] <= P[:, 2].min() + 0.25 * (P[:, 2].max() - P[:, 2].min()) + 1e-6]
        dn = [i for i in range(len(t["F"])) if b["N"][i][2] < -0.5]       # the downward faces of its hull: sample their corners and centres too, not only the vertices
        low = np.vstack([low] + [np.array([P[f].mean(0) for f in t["F"][dn]])] + [np.array([(P[f[0]] + P[f[1]]) / 2 for f in t["F"][dn]])])
        if b["layer"] == 0: g = float(low[:, 2].min())
        else:
            g = 9.0
            for q in fr:
                if q["layer"] != b["layer"] - 1 or (q["HV"].min(0)[:2] > P.max(0)[:2]).any() or (q["HV"].max(0)[:2] < P.min(0)[:2]).any(): continue
                bv = hull_bvh(q, t); g = min(g, min(bv.find_nearest(Vector(p))[3] for p in low))
        if g > 0.003: print('PAN2 DEBUG gap', name, b['layer'], np.round(b['c'], 4), 'gap_mm', round(g * 1000, 2), 'lowz', round(float(P[:, 2].min()), 4), 'sup', b['sup'], flush=True)
        worst = max(worst, g)
    return worst

CHECK = {}
for name in KINDS:
    s = ST[name]; t = s["t"]; fr = s["frozen"]; fam_ = PANTRY.get(name, "jar")
    fmax, pen = float_pen(name)
    if name in GRID: fmax = grid_gap(name)
    P = np.vstack([(t["verts"] * t["s"]) @ b["R"].T + b["c"] for b in fr]) if fr else np.zeros((1, 3))
    hf = HF(fam_); lv = []
    for k in range(UNITS_PER):
        for b in fr:
            if b["stack"] == k: hf.add(b["N"], b["D"], dilate=False)
        lv.append(round(hf.level(), 3))
    CHECK[name] = dict(copies=len(fr), copies_by_stack=[sum(1 for b in fr if b["stack"] == k) for k in range(UNITS_PER)], cap=t["cap"],
                       mesh_outside_clear_mm=round(outside_clear(P, fam_) * 1000, 1), float_worst_mm=round(fmax * 1000, 2),
                       overlap_max_mm=round(pen * 1000, 2), level_by_stacks_m=lv, top_m=round(float(P[:, 2].max()), 3),
                       longest_m=round(float(t["size"].max() * t["s"]), 3), drawn_tris_per_copy=t["tris"], tris_full_vessel=len(fr) * t["tris"])
    print("PAN2 CHECK %-32s %s" % (name, CHECK[name]), flush=True)

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
rs = []                                                         # the box of the platter and the board: its surface every 1 cm, its inside every 2 cm
XS, YS, ZB1 = HX - 0.001, HY - 0.001, H_R - 0.001
for z in np.arange(Z0, ZB1 + 1e-9, 0.01):
    for x in np.arange(-XS, XS + 1e-9, 0.01): rs += [(x, -YS, z), (x, YS, z)]
    for y in np.arange(-YS, YS + 1e-9, 0.01): rs += [(-XS, y, z), (XS, y, z)]
for x in np.arange(-XS, XS + 1e-9, 0.02):
    for y in np.arange(-YS, YS + 1e-9, 0.02):
        for z in (Z0, ZB1) + tuple(np.arange(0.02, H_R, 0.04)): rs.append((x, y, z))
CS = {"cyl": np.array(cs), "rect": np.array(rs)}                # relative to the floor centre (shelf surface + TB)
FLOORS = [np.array(place_origin(n)) + np.array((0, 0, TB)) for n in range(NPLACE)]

# (a) the clear cylinder against each vessel (local coordinates): 0 points inside a vessel part
VES_CYL = {}
for fam in FAMILIES:
    cq = CS[CLEAR[fam]]
    h, notes = count_inside(cq + np.array((0, 0, TB)), VESSEL_PARTS[fam]); VES_CYL[fam] = h
    print("PAN2 clear space (%s) vs vessel %-8s: %d of %d points inside %s" % (CLEAR[fam], fam, h, len(cq), notes[:4]), flush=True)
# (b) every copy (all its vertices) inside the clear cylinder, i.e. clear of every vessel (a) -> the max over all layouts
COPY_OUT = max(CHECK[n]["mesh_outside_clear_mm"] for n in KINDS)      # <= 0: inside the cylinder
FV = np.vstack([p["V"] for p in FRAME_DATA])
ves_frame = {}; cyl_frame = 0; cyl_notes = []; fv_in = 0
for n in range(NPLACE):
    org = np.array(place_origin(n))
    for fam in FAMILIES:
        pts = np.vstack([np.vstack([p["V"], p["cent"]]) for p in VESSEL_PARTS[fam]]) + org
        pts = pts[pts[:, 2] > org[2] + 0.003]
        h, notes = count_inside(pts, FRAME_DATA)
        ves_frame[(n, fam)] = h
        if h: print("PAN2 vessel %s at place %d inside frame: %d %s" % (fam, n, h, notes[:3]), flush=True)
    for rg in ("cyl", "rect"):
        h, notes = count_inside(CS[rg] + FLOORS[n], FRAME_DATA); cyl_frame += h; cyl_notes += notes
    Q = FV - FLOORS[n]; hit = (in_cyl(Q, 0.001) | in_box(Q, 0.001)) & (Q[:, 2] > 0.001); fv_in += int(hit.sum())
VES_FRAME = sum(ves_frame.values())
print("PAN2 vessels vs frame: %d vessel points inside frame parts (%d vessel x place combinations); cylinders vs frame: %d points %s, frame vertices in a cylinder %d" %
      (VES_FRAME, len(ves_frame), cyl_frame, cyl_notes[:3], fv_in), flush=True)
# (d) neighbours: the widest vessel radius against the 0.25 m pitch
RMAX = {f: max(float(np.hypot(p["V"][:, 0], p["V"][:, 1]).max()) for p in VESSEL_PARTS[f]) for f in FAMILIES}       # the round ones: the radius; the platter and the board: the corner (half-diagonal)
YEXT = {f: round(max(float(np.abs(p["V"][:, 1]).max()) for p in VESSEL_PARTS[f]), 3) for f in FAMILIES}
print("PAN2 vessel radii", {k: round(v, 3) for k, v in RMAX.items()}, "y half-extent", YEXT, "pitch", PITCH, flush=True)
# (e) the vessels' x extent (hanging bars) is in x; the gallows is the widest in x, the others round
XEXT = {f: round(max(float(np.abs(p["V"][:, 0]).max()) for p in VESSEL_PARTS[f]), 3) for f in FAMILIES}
print("PAN2 vessel x half-extent", XEXT, "widest pair", round(2 * max(XEXT.values()), 3), "of", PITCH, flush=True)


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
    real = name != "_generic"
    ent = {"family": PANTRY.get(name, "any"), "mode": t["mode"],
           "scale": round(t["s"], 5) if real else None, "true_size_m": [round(float(sz[0]), 4), round(float(sz[2]), 4), round(float(sz[1]), 4)],
           "fit_longest_m": round(float(sz.max() * t["s"]), 4),
           "copies_per_stack": round(len(s["frozen"]) / UNITS_PER, 2), "copies_by_stack": [len(x) for x in stacks], "stacks": stacks, "check": CHECK[name]}
    if name == "_generic":
        ent["scale"] = None; ent["true_size_m"] = None
        ent["note"] = "fallback for any item without its own layout in any vessel: a neutral round lump (a settled heap), scaled uniformly so its longest bounds side is fit_longest_m; it fits every family's clear space."
    else:
        ent["model"] = "the item's own ripped model (C:/Users/joost/ValheimRip/items/%s)" % name
        if name in GRID:
            cols, rows, layers = GRID[name]
            ent["layout"] = {"kind": "placed", "cols": cols, "rows": rows, "layers": layers,
                             "stack_is": "layer (the 2nd layer rests on the 1st)" if layers > 1 else "row (stack 0 = the front row, stack 1 = the back row)"}
        else: ent["layout"] = {"kind": "heap", "settled_in": "%s (round clear cylinder)" % PANTRY[name]}
    layouts[name] = ent
GEN = {f: layouts["_generic"] for f in FAMILIES}
ITEM_FAMILY = {k: v for k, v in PANTRY.items() if k in ITEMS}
units = []
for n in range(NPLACE):
    r, c = divmod(n, NCOL)
    for fam in FAMILIES:
        hh = H_R if CLEAR[fam] == "rect" else H_C
        cen = FLOORS[n] + np.array((0, 0, hh / 2))
        box = [round(2 * HX, 4), round(H_R, 4), round(2 * HY, 4)] if CLEAR[fam] == "rect" else [round(2 * R_C, 4), round(H_C, 4), round(2 * R_C, 4)]
        for k in range(UNITS_PER):
            g = GEN[fam]
            units.append({"index": len(units), "bin": n, "place": n, "kind": fam, "vessel": fam, "tier": r, "col": c, "fill_step": k, "position": uvec(cen),
                          "rotation": [0, 0, 0], "box": box,
                          "copies": [{"offset": [round(cp["offset"][0], 4), round(cp["offset"][1] - hh / 2, 4), round(cp["offset"][2], 4)],
                                      "rot_quat_xyzw": cp["rot_quat_xyzw"], "fit_longest_m": g["fit_longest_m"]} for cp in g["stacks"][k]]})
vessels = [{"position": n, "at": uvec(place_origin(n)), "default": DEFAULT[n]} for n in range(NPLACE)]
heaviest = max(ITEMS, key=lambda n: CHECK[n]["tris_full_vessel"])
worst_vessel = max(VESSEL_TRIS.values())
PLACES_OF = {f: sum(1 for d in DEFAULT if d == f) for f in FAMILIES}
doc = {
    "store": "Pantry Dresser round 2 (blender/pantry_r2.py): 2.16 m wide, 5 tiers of 8 places, the vessel follows the item; real item models; dishes lie flat on platters, loose things in baskets",
    "rule": "what you cook with: flours, dough, herbs, spices, feast ingredients and the uncooked dishes waiting for the oven; one kind per place, the vessel is the item's family (jar, board, basket, platter, crock, sack): spices in jars, dough on a floured board, loose things in baskets, dishes flat on platters, feast ingredients in crocks, flour in sacks",
    "items": ITEMS, "item_family": ITEM_FAMILY, "families": FAMILIES,
    "family_kinds": {f: sorted(n for n in ITEMS if PANTRY[n] == f) for f in FAMILIES},
    "slots": 80, "places": NPLACE, "grid": [NCOL, len(LEVEL)], "units_total": len(units), "units_per_family": {f: sum(1 for u in units if u["kind"] == f) for f in FAMILIES},
    "units_split": ("every one of the %d places has %d units (stacks) for each of the six families: %d x 6 x %d = %d units, %d per family, so any one family can show all 80 slots; "
                    "a full place = %d stacks of one kind, a place holding fewer shows a vessel that is only partly full. Not every stack needs its own place: %d kinds share %d places."
                    % (NPLACE, UNITS_PER, NPLACE, UNITS_PER, len(units), NPLACE * UNITS_PER, UNITS_PER, len(ITEMS), NPLACE)),
    "full_demo": FULL_ASSIGN,
    "stacks_per_place_and_family": UNITS_PER, "stack_per_unit": 1, "placement": "wall",
    "frame": {"obj": "Pantry.obj", "tris": FRAME_TRIS, "size_m": [round(W + 0.07, 3), H + 0.0, DEPTH + 0.06], "atlas": "pantry_atlas.png 128x128 point",
              "atlas_rows": "v px from the bottom: 96-127 hewn, 64-95 end grain, 48-63 iron (byte-identical from bunker_r4), 36-47 clay, 16-23 glass, 24-35 wicker (baskets, apothecary_r2's), 12-15 tin (unused), 8-11 hessian (sacks), 4-7 cord, 0-3 swatches cork/ivory/amber/crust/flour/bright glass/worn timber/soot"},
    "space": "Unity prefab space, metres. Origin: the wall plane (back face, z = 0), x centred, y = 0 the foot; front is +z. Blender z-up/-y front -> Unity: ux=-bx, uy=bz, uz=-by. OBJ exported forward -Z, up Y (the mod loads it flipX).",
    "vessel_meshes": {f: "Vessel_%s.obj" % f for f in FAMILIES},
    "vessel_meshes_doc": ("one mesh per family in the same OBJ convention as the frame, in local coordinates: origin = the centre of the vessel's footprint at the shelf "
                          "surface (vessels[].at); draw it at 'at' (no rotation) with the frame's material. Tris: %s." % ", ".join("%s %d" % (f, VESSEL_TRIS[f]) for f in FAMILIES)),
    "vessels": vessels,
    "vessels_doc": ("one entry per place: 'at' = where its vessel stands (prefab space), 'default' = the family the place is for (light on top, heavy below: the order the mod claims "
                    "places in is jar, board, basket, platter, crock, sack, each kind by name, in reading order; the defaults are the full demo: %s places). An EMPTY place draws nothing. A place holding an "
                    "item draws the vessel of the item's family (item_family): the vessel follows the item. place n = tier * 8 + column; tier 0 is the top, column 0 the left as seen "
                    "from the front (Blender x ascending, Unity x descending)." % ", ".join("%s %d" % (f, PLACES_OF[f]) for f in FAMILIES)),
    "groups": ("place 0..%d = one vessel position (key 'bin' in units_list, which the mod already reads as the group; 'place' repeats it). EVERY place has units for EVERY "
               "family: kind = jar | board | basket | platter | crock | sack, %d stacks (fill_step 0..%d) each, same position in all six. The clear space of the round vessels "
               "(jar, basket, crock, sack) is an upright cylinder (radius %.3f, height %.3f), that of the platter and the board a box %.3f x %.3f (x, y) x %.3f high (the unit's 'box'), "
               "all standing on crate_floor_centres[place]." % (NPLACE - 1, UNITS_PER, UNITS_PER - 1, R_C, H_C, 2 * HX, 2 * HY, H_R)),
    "crate_floor_centres": [uvec(fc) for fc in FLOORS],
    "crop_layouts": layouts,
    "crop_layouts_doc": ("crop_layouts: one full vessel per item kind, as apothecary_r2; '_generic' (any other item in any vessel). All 32 are the REAL prefab models. A place holding n stacks of a kind shows "
                         "stacks[0..n-1] of that kind's layout (%d stacks). Per copy: the item's model scaled uniformly (by 'scale' x its true size where 'scale' is set, else to "
                         "fit_longest_m), turned by rot_quat_xyzw about its bounds centre, that centre at crate_floor_centres[place] + offset. layout.kind 'heap' (jar, basket, crock, sack; "
                         "mode pile/lie/natural/upright/tumble) is physics-settled (stack k dropped onto stacks 0..k-1); layout.kind 'placed' (platter, board) lines the dishes up flat "
                         "in their rip pose: cols x rows per layer, layers high, stack = the layer (pies, pans) or the row (0 = front). Every layout fits its family's clear space, so it fits "
                         "every place of its family. Platter and board dishes keep their own plate or tin down; nothing stands on edge, nothing towers." % UNITS_PER),
    "liquids": [],
    "unit_semantics": ("units_list: one unit = one stack, %d per place and family in fill order; kind = the family; copies = the generic lump as Fit.Longest copies "
                       "(centre at position + offset), a fallback only." % UNITS_PER),
    "physics": ("heaps: Blender rigid body (Bullet), each copy the convex hull of its item, friction 0.6, restitution 0, damping 0.5/0.95, margin 1 mm, substeps 20, iterations 40, "
                "in the cylinder made of passive box slabs (round vessels only); one copy per kind per drop at one of the three lowest well-supported spots of a 1 cm grid x 8 orientations, "
                "settled, checked inside the cylinder, then frozen; until no copy fits or the kind's cap (~%d item triangles per vessel)." % TRI_PER_VESSEL),
    "checks": {"copies_outside_clear_space_mm_max": COPY_OUT, "clear_points_inside_vessel": VES_CYL, "clear_points_per_family": {k: len(v) for k, v in CS.items()},
               "coplanar_same_facing_overlaps": COP,
               "vessel_points_inside_frame": VES_FRAME, "vessel_places_checked": len(ves_frame), "cylinder_points_inside_frame": cyl_frame,
               "frame_vertices_inside_clear_spaces": fv_in, "vessel_radius_m": {k: round(v, 3) for k, v in RMAX.items()}, "vessel_x_half_extent_m": XEXT, "vessel_y_half_extent_m": YEXT, "pitch_m": PITCH,
               "rotation_roundtrip_max_err": rt, "sim": SIMST,
               "overlap_between_copies_mm_max": max(CHECK[n]["overlap_max_mm"] for n in KINDS), "float_worst_mm_max": max(CHECK[n]["float_worst_mm"] for n in KINDS)},
    "tris": {"frame": FRAME_TRIS, "vessels": VESSEL_TRIS,
             "full_store_worst_kind": {"item": heaviest, "tris": NPLACE * (CHECK[heaviest]["tris_full_vessel"] + VESSEL_TRIS[PANTRY[heaviest]]) + FRAME_TRIS},
             "full_store_worst_case_any_family": NPLACE * (max(CHECK[n]["tris_full_vessel"] for n in ITEMS) + worst_vessel) + FRAME_TRIS,
             "heaviest_kinds_full_vessel": {n: CHECK[n]["tris_full_vessel"] for n in sorted(ITEMS, key=lambda n: -CHECK[n]["tris_full_vessel"])[:6]},
             "full_demo": FRAME_TRIS + sum(VESSEL_TRIS[PANTRY[it]] + CHECK[it]["tris_full_vessel"] for it in FULL_ASSIGN if it)},
    "units_list": units,
}
if EXPORT:
    out = os.path.join(OUTA, "pantry_anchors.json"); tmp = out + ".tmp"
    with open(tmp, "w") as fh: json.dump(doc, fh, indent=1)
    os.replace(tmp, out)
    print("PAN2 wrote", out, flush=True)
print("PAN2 STATS frame %d, vessels %s, copies %d, tris %s, roundtrip %.2g" % (FRAME_TRIS, VESSEL_TRIS, sum(c["copies"] for c in CHECK.values()), doc["tris"], rt), flush=True)

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
    look(*V34); fill([]); render("pantry2-empty.png")
    fill(HALF); render("pantry2-half.png"); clear()
    fill(FULL); render("pantry2-full.png")
    look(-4, 4, 5.0, (0, -0.24, 1.07)); render("pantry2-full-front.png")
    for tier, nm in ((0, "jars"), (1, "board-baskets-platters"), (2, "platters"), (3, "platter-crocks"), (4, "crocks-sacks")):
        look(-10, 12, 2.5, (0, -0.25, LEVEL[tier] + 0.13)); render("pantry2-closeup-tier%d-%s.png" % (tier, nm))
    # the dishes row (tier 2, the platters) from above and from the front, a close lens: every dish lies flat, nothing towers
    look(-4, 26, 1.7, (0, -0.25, LEVEL[2] + 0.04)); render("pantry2-closeup-dishes-row-above.png")
    look(0, 6, 1.7, (0, -0.25, LEVEL[2] + 0.08)); render("pantry2-closeup-dishes-row-front.png")
    look(-22, 24, 0.95, (COLX[3], -0.25, LEVEL[2] + 0.04)); render("pantry2-closeup-dishes-three-quarter.png")
    look(22, 24, 0.95, (COLX[6], -0.25, LEVEL[2] + 0.04)); render("pantry2-closeup-dishes-three-quarter-right.png")
    # as a player sees it: 2 m from the front, eye height 1.6 m, a wide lens
    cam.data.lens = 20; cam.location = (0.0, -2.46, 1.15); cam.rotation_euler = (math.radians(90), 0, 0)
    render("pantry2-from-2m.png", 1400, 1000); cam.data.lens = 38
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
    look(-8, 8, 14.2, (0.15, -0.5, 0.95)); render("pantry2-full-beside-apothecary_r2-bunker_r4.png", 2000, 900)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(1.75, -0.7, 0.9)); post = bpy.context.active_object; post.scale = (0.1, 0.1, 1.8)
    pm = bpy.data.materials.new("post"); pm.use_nodes = True
    pm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.85, 0.85, 0.88, 1); post.data.materials.append(pm)
    look(-8, 5, 5.8, (0.2, -0.2, 1.07)); render("pantry2-full-post-1.8m.png")
    bpy.data.objects.remove(post)
print("DONE %.0fs" % (time.time() - t0))
