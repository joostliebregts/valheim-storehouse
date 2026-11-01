"""Pantry Dresser round 3 (Joost, 24 Oct): round 2 was logical but read empty from the front (flat dishes, low heaps); round 1 looked full but its towers were physically
illogical. Round 3 keeps r2's physics and schema and fills the dresser the way people really keep food: VERTICALLY, each layer resting on a tier, a cloth or the layer below.
Same dresser (2.16 W x 0.46 D x 2.14 H, 5 tiers of 8 = 40 places, 80 slots, 32 kinds), the same schema as pantry_r2 (vessel_meshes, vessels with "at" and "default", units per place
and family with "bin"/"place" and "kind" = family, crate_floor_centres, crop_layouts per item, item_family, families); the vessel follows the item.
  jar      Spice (Forests, Plains, Mountains, Oceans, Mistlands, Deep North, Ashlands)   glass jar, open at the front, cork: the pouches lie heaped in it, now to the top    7 kinds
  basket   Bread dough, Fish and bread, Fragrant bundle, Magically stuffed shroom        round wicker basket LINED WITH A LINEN NAPKIN draped over the rim (four corners hang down the
           outside): loaves, shrooms, dough lumps and herb bundles lie heaped in it, a mound crowning well above the rim                                                   4 kinds
  stand    the 9 uncooked dishes (Baked poteitr, Honey glazed chicken, Kale chips, Lox pie, Meat platter, Misthare supreme, Oven pancake, Piquant pie, Roasted crust pie) and the
           Viking cupcakes: a THREE-TIER SERVING STAND (a timber tea tray: three planks on one iron post, 88 mm apart, the lowest widest): every dish lies flat on its own tier,
           two dishes deep on the lowest (2 x 2 cells) and one wide on the two above (1 x 2 cells), pies and pans two high (flat tops), cupcakes four to a cell    10 kinds
  crock    the 9 Feast ingredients (Meadows, Black Forest, Swamps, Mountains, Plains, Oceans, Deep North, Mistlands, Ashlands)   a wide shallow clay crock with a cord: the big platters lie in it
           and crown above the rim (a mound: the heap closes inward above the rim, each platter on the ones below)                                                          9 kinds
  sack     Barley flour, Oat flour                                                       squat hessian sack with a rolled cuff and a cord: the flour sacks crown above the cuff   2 kinds
(r2's bread board is gone: dough rises in a linen-lined basket, which is how bakers keep it; r2's platter is the stand's lowest tier, three times over.)
Never two kinds in one vessel. Light on top, heavy below: the mod claims places in reading order, families jar, basket, stand, crock, sack (tier 0 = top), each kind by name;
the full render and the defaults follow that: tier 0 the jars (7 kinds on 8 places), tier 1 the baskets (4 kinds on 5) and the first 3 stands, tier 2 the other 8 stands (10 kinds on 11),
tiers 3 and 4 the crocks (9 kinds on 13) and the sacks (2 on 3). Empty places stand empty (the mod draws nothing there); "default" only says which family a place is for.
Units: every place has 2 stacks for EVERY family (the mod's perPlace logic keys on (place, family)): 40 x 5 x 2 = 400 units, 80 per family, so any one family can show all 80 slots;
a place holding fewer than 2 stacks shows a vessel that is only partly full. Stack 0 / stack 1: heaps = the first / second half of the settled copies; STAND = stack 0 the lowest tier
(2 x 2 cells), stack 1 the two upper tiers (1 x 2 cells each), so one stack is the lowest tier alone, two stacks the whole stand.
Clear space: the round vessels (jar, basket, crock, sack) have an upright cylinder on a floor at origin + 0.02 (= crate_floor_centres[place]); basket, crock and sack close inward above
their rim (a cone, 43 degrees off vertical: the crown of a heap), so a heap there is a mound, never a column (numbers: CLR below). The STAND's clear space is eight cell boxes: lowest
tier 4 cells of 0.098 x 0.114 at (+-0.057, +-0.067), upper tiers 2 cells at (0, +-0.067), each 0.078 high above its plank (plank tops at 0, 0.088, 0.176 above the floor); the iron
post (r 0.0095) stands in the middle, off all cells.
Placed layouts (stand) put each dish flat in the pose it has in the rip (its own plate or tin down), turned a few degrees, resting on the plank or, one layer up, on the dish below it
(hull against height field, 1 mm gap); the heaps (jars, baskets, crocks, sacks) are physics-settled as in r2, now inside the cone-topped clear space.
Performance (the Feast models are heavy: 2.5k-14.2k triangles each): copies per crock are capped by a budget of 7000 item triangles, at least one copy (so Black Forest, Mountains and Oceans show 2,
the other six 1, in stack 0; stack 1 of those is empty), and the platters lie on a 50 mm timber riser filling the shallow crock to its rim, like lids. Other vessels: 7000 item triangles too; RoastedCrustPie one high.
Result (the numbers in pantry_anchors.json "tris"): frame 3404; vessels jar 372, basket 1824, stand 480, crock 524, sack 720; full demo (default places) about 196k; every place one kind: Ashlands
593k (one 14.2k copy per crock is already over 300k x 40 places: the real prefab's own cost), Deep North 372k, Swamps 336k, Kale chips 323k, all others under 295k.
Checks (all 0): clipping (every copy's mesh inside its clear space; the clear space inside no vessel part; vessels and clear spaces inside no frame part), z-fighting
(report_coplanar, tolerance 2 mm: frame and every vessel), floating copies (each rests on its floor, plank, a copy below, or the heap's wall).
Run: "C:/Program Files/Blender Foundation/Blender 4.5/blender.exe" -b -P pantry_r3.py -- [--out DIR] [--no-render] [--quick] [--no-export] [--assets DIR]

Dimensions: Blender x, y, z; -y = front, back face y = 0 at the wall, x centred, z = 0 the foot. Tiers (shelf tops) at 1.63, 1.25, 0.87, 0.49, 0.11 m; places 0.24 m apart
(x = -0.84 ... 0.84), vessel centre y = -0.25. n = tier * 8 + column, tier 0 the top, column 0 the left as seen from the front (Blender x ascending, Unity x descending).
Vessels are at most 0.116 in radius / half-width (24 cm pitch), at most 0.31 high (the shelf above is 0.33 up); the stand is 0.226 wide, 0.26 deep (y -0.38 ... -0.12), 0.25 high.

THE ITEM MODELS: all 32 kinds are the real Valheim 1.0 prefabs, ripped with scripts/items_extract.py into C:/Users/joost/ValheimRip/items/<Prefab>/ (as r2). Every layout carries "scale"
(the prefab's own size times it = the drawn size) and fit_longest_m; rotations are about the model's bounds centre as in every store.

Atlas 128 x 128 (point filtered, 48 px/m): bunker_r4's timber, end grain and iron rows byte-identical; clay, glass, cord and swatches as apothecary_r2; wicker rows 24-35 copied from
apothecary_r2's atlas; rows 8-11 the hessian tile (sacks); rows 12-15 a LINEN tile (ivory weave, madder-red stripe pairs: the basket cloth; r2's unused tin tile made way for it);
swatches cork/ivory/amber/crust/flour/bright glass/worn timber/soot.
Files (assets/pantry_r3/): Pantry.obj (frame only), Vessel_{jar,basket,stand,crock,sack}.obj (local coordinates, origin = centre of the footprint at the shelf surface),
pantry_atlas.png, pantry_anchors.json (last, temp + rename). Unity prefab space: ux = -bx, uy = bz, uz = -by (OBJ exported forward -Z, up Y, like every store).
"""
import bpy, bmesh, sys, os, math, json, random, time, zlib
import numpy as np
from mathutils import Vector, Matrix, Euler, Quaternion
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, ".."))
OUTA = os.path.join(REPO, "assets", "pantry_r3")
BUNKER = os.path.join(REPO, "assets", "bunker_r4")
R2DIR = os.path.join(REPO, "assets", "apothecary_r2")
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
def arg(k, d=None): return argv[argv.index(k) + 1] if k in argv else d
OUT = arg("--out", "C:/Users/joost/AppData/Local/Temp/claude/C--Users-joost--pai/5e4bc60b-cdfe-4638-8e29-2e507fa13cf9/scratchpad/pantry_r3")
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
    "BreadDough": "basket", "FragrantBundle": "basket", "FishAndBreadUncooked": "basket", "MagicallyStuffedShroomUncooked": "basket",
    "BakedPoteitrUncooked": "stand", "HoneyGlazedChickenUncooked": "stand", "KaleChipsUncooked": "stand", "LoxPieUncooked": "stand", "MeatPlatterUncooked": "stand",
    "MisthareSupremeUncooked": "stand", "OvenPancakeUncooked": "stand", "PiquantPieUncooked": "stand", "RoastedCrustPieUncooked": "stand", "VikingCupcakeUncooked": "stand",
    "FeastAshlands_Material": "crock", "FeastBlackforest_Material": "crock", "FeastDeepNorth_Material": "crock", "FeastMeadows_Material": "crock",
    "FeastMistlands_Material": "crock", "FeastMountains_Material": "crock", "FeastOceans_Material": "crock", "FeastPlains_Material": "crock", "FeastSwamps_Material": "crock",
    "BarleyFlour": "sack", "OatFlour": "sack",
}
ITEMS = list(PANTRY)
FAMILIES = ["jar", "basket", "stand", "crock", "sack"]            # the order the mod claims places in: light on top, heavy below
LIQUIDS = []
if QUICK: ITEMS = ["SpiceForests", "SpicePlains", "BreadDough", "FragrantBundle", "VikingCupcakeUncooked", "LoxPieUncooked", "PiquantPieUncooked", "MeatPlatterUncooked", "FeastMeadows_Material", "FeastOceans_Material", "BarleyFlour"]
PANTRY = {k: v for k, v in PANTRY.items() if k in ITEMS}

rng = random.Random(7)
TEX = 128
DENS = 48.0
STRIP = {"hewn": 0.75, "end": 0.50, "iron": 0.375}
STRIPH = {"hewn": 32, "iron": 16}
ROWS = {"clay": (36, 12), "wicker": (24, 12), "glass": (16, 8), "rope": (4, 4), "sack": (8, 4), "linen": (12, 4)}
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
    x, y = grid(4)                                    # linen (rows 12-15): an ivory plain weave, thread-level noise, madder-red stripe pairs every 16 px, a fine dark thread between
    weave = (((x).astype(int) + y.astype(int)) % 2)
    t = 0.30 + 0.12 * weave + nr.random((4, TEX)) * 0.16 + 0.05 * np.sin(x * tile(7))
    c = mix(srgb((0.90, 0.86, 0.74)), srgb((0.66, 0.60, 0.48)), t)
    stripe = ((x % 16) == 3) | ((x % 16) == 4)
    red = mix(srgb((0.66, 0.30, 0.24)), srgb((0.44, 0.17, 0.14)), 0.15 + nr.random((4, TEX)) * 0.5 + 0.1 * weave)
    c = np.where(stripe[..., None], red, c)
    c = np.where(((x % 16) == 9)[..., None], mix(c, srgb((0.45, 0.40, 0.32)), np.full((4, TEX), 0.5)), c)
    img[12:16] = c
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
TB = 0.02                                   # the floor of every vessel (the shelf surface + TB = crate_floor_centres)
FAM_RANK = {f: i for i, f in enumerate(FAMILIES)}
SHARE = {"jar": 8, "basket": 5, "stand": 11, "crock": 13, "sack": 3}   # places per family in the full demo (and the defaults): 7 / 4 / 10 / 9 / 2 kinds on 8 / 5 / 11 / 13 / 3 places
def full_assign():
    """every kind in the order the mod claims places (families jar, basket, stand, crock, sack; then by name); a family takes its SHARE of the places, the first
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

# ---------- the clear spaces (what a place's contents may occupy; the origin of every one is the vessel floor = shelf surface + TB) ----------
COL_IN = 0.0025
TANB = 0.45                                 # above the rim a heap closes inward: radius shrinks 0.45 per metre of height (24 degrees off vertical): a mound
CLR = {                                     # R: radius, H: height above the floor, zr: height where the cone starts (None: a straight cylinder)
    "jar": dict(R=0.092, H=0.236, zr=None),     # under the cork
    "basket": dict(R=0.086, H=0.250, zr=0.100, tb=0.30),  # the rim is 0.096 above the floor; the linen lines the basket 0.0873 .. 0.094 from the axis
    "crock": dict(R=0.100, H=0.205, zr=None, z0=0.050),   # the shallow crock's rim is 0.048 above the floor, inside 0.0987; a timber riser 50 mm high fills it to the rim and the platters lie on it, like lids (z0: where the contents start); flat platters, so no cone
    "sack": dict(R=0.090, H=0.205, zr=0.100),    # the cuff's top is 0.108 above the floor, inside 0.097
    "generic": dict(R=0.070, H=0.135, zr=None, z0=0.050),  # the fallback lumps: fit every family's space (z0 0.05: clear of the crock's riser too)
}
ROUND = ("jar", "basket", "crock", "sack")
# the stand: three planks on one iron post; cells are the clear space (all coordinates relative to the vessel's footprint centre, z relative to the floor = lowest plank top)
TIERZ = [0.0, 0.088, 0.176]                 # plank tops
TCLEAR = 0.0755                             # clear height above a plank top (the plank above is 0.076 up)
PLK_T = 0.012
PLANK_W = [0.226, 0.170, 0.130]
PLANK_D = 0.26
CELL_W, CELL_D = 0.098, 0.108
CELL_CX, CELL_CY = 0.057, 0.070
ROD_R = 0.0095
CELLS = {0: [(sx * CELL_CX, sy * CELL_CY) for sy in (-1, 1) for sx in (-1, 1)], 1: [(0.0, -CELL_CY), (0.0, CELL_CY)], 2: [(0.0, -CELL_CY), (0.0, CELL_CY)]}
STAND_H = TIERZ[2] + TCLEAR                 # 0.254: the whole clear space of the stand

def rad_at(fam, z):
    c = CLR[fam]; z = np.asarray(z, dtype=float)
    if c["zr"] is None: return np.full(z.shape, c["R"])
    return np.maximum(c["R"] - np.maximum(z - c["zr"], 0.0) * c.get("tb", TANB), 0.0)

def in_clear(P, fam, eps=0.0015):
    """points inside a round family's clear space"""
    c = CLR[fam]; z0 = c.get("z0", 0.0)
    return (P[:, 2] >= z0 + min(eps, 0.0) - 0.0002) & (P[:, 2] <= c["H"] - eps) & (np.hypot(P[:, 0], P[:, 1]) <= rad_at(fam, P[:, 2]) - eps)

def outside_clear(P, fam):
    c = CLR[fam]; z0 = c.get("z0", 0.0)
    return float(np.max(np.maximum.reduce([z0 - P[:, 2], P[:, 2] - c["H"], np.hypot(P[:, 0], P[:, 1]) - rad_at(fam, P[:, 2])])))

def outside_cell(P, tier, cell):
    """how far the points are outside the cell box (negative: inside, by that much) of a stand tier; the post's column counts as outside too"""
    cx, cy = cell; z0 = TIERZ[tier]
    return float(np.max(np.maximum.reduce([z0 - P[:, 2], P[:, 2] - (z0 + TCLEAR), np.abs(P[:, 0] - cx) - CELL_W / 2, np.abs(P[:, 1] - cy) - CELL_D / 2, ROD_R - np.hypot(P[:, 0], P[:, 1])])))

def wall_gap(P, fam):
    """distance of the points from the clear space's walls (the layouts keep clear of them)"""
    return float((rad_at(fam, P[:, 2]) - COL_IN - np.hypot(P[:, 0], P[:, 1])).min())

# ---------- the five vessels, in local coordinates (origin = centre of the footprint at the shelf surface) ----------
KRJ, KZJ = 0.95, 0.92                       # glass jar: apothecary_r2's, scaled to the 24 cm pitch
KRC = 0.88                                  # clay crock: apothecary_r2's, wide and SHALLOW (KZC): the platters in it crown above the rim
KZC = 0.45
KZS = 0.80                                  # the sack: low, so the flour sacks in it crown above the cuff
VESSEL_PROF = {
    "jar": dict(prof=[(0.116 * KRJ, 0.004), (0.119 * KRJ, 0.02 * KZJ), (0.119 * KRJ, 0.262 * KZJ), (0.111 * KRJ, 0.285 * KZJ)], t=0.008 * KRJ),
    "crock": dict(prof=[(r * KRC, z * KZC) for r, z in ((0.121, 0.0), (0.126, 0.04), (0.129, 0.085), (0.125, 0.12), (0.122, 0.14), (0.126, 0.152))], t=0.014 * KRC),
    "sack": dict(prof=[(r * 0.985, z * KZS) for r, z in ((0.106, 0.0), (0.108, 0.025), (0.114, 0.06), (0.113, 0.10), (0.109, 0.128), (0.1085, 0.145), (0.110, 0.153))], t=0.011),
    # a round wicker basket 0.108 high with a rope rim to 0.116: the wall's inner side is at 0.090 (floor) .. 0.098 (rim) from the axis, the outside at most 0.106, the rope 0.109; the linen
    # lines it (3.5 mm thick, 0.5 mm off the wall) and hangs over the rope at 0.1165 .. 0.113 + folds, so nothing is wider than 0.116 (the 24 cm pitch)
    "basket": dict(prof=[(0.098, 0.0), (0.102, 0.03), (0.105, 0.065), (0.106, 0.095), (0.106, 0.108)], t=0.008, tb=0.015),
}

def build_stand():
    """a three-tier serving stand (a timber tea tray): a foot, three timber planks 0.226 / 0.170 / 0.130 wide and 0.26 deep, 12 mm thick, their tops 88 mm apart, on ONE iron post
    (r 9.5 mm) with iron rings above and below each plank and a finial; an iron strap with two rivets across each plank's front edge"""
    timber("foot", (0.17, 0.215, 0.008), (0, 0, 0.004), jitter=0.0006, bevel=0.003)
    for k in range(3):
        top = TB + TIERZ[k]
        timber("plank", (PLANK_W[k], PLANK_D, PLK_T), (0, 0, top - PLK_T / 2), jitter=0.0006, bevel=0.003)
        zc = top - PLK_T / 2
        iron("strap", (0.06, 0.004, PLK_T + 0.008), (0, -PLANK_D / 2 - 0.001, zc))
        for sx in (-1, 1): iron("rivet", (0.008, 0.006, 0.008), (sx * 0.02, -PLANK_D / 2 - 0.0035, zc))
        disc("ringtop", 0.0125, 0.0125, top, top + 0.007, "iron", (0, 0, 0), 8)
        if k > 0: disc("ringbottom", 0.0125, 0.0125, top - PLK_T - 0.007, top - PLK_T, "iron", (0, 0, 0), 8)
    ztop = TB + TIERZ[2]
    disc("rod", ROD_R, ROD_R, 0.011, ztop + 0.040, "iron", (0, 0, 0), 8)
    disc("finial", 0.016, 0.006, ztop + 0.036, ztop + 0.052, "iron", (0, 0, 0), 8)

def basket_cloth(a0):
    """the linen napkin: a two-skinned shell (3.5 mm) lining the basket, over the rope rim and hanging down the outside in four corners (a square napkin on a round rim)"""
    global UV
    N = 24; T = 0.0035; ZT = 0.0200
    wz = [0.015, 0.03, 0.065, 0.095, 0.108]; wr = [0.090, 0.094, 0.097, 0.098, 0.098]            # the wall's inner side
    win = lambda z: float(np.interp(z, wz, wr))
    fixed = [(0.0, ZT), (0.040, ZT), (win(ZT) - 0.004, ZT)] + [(win(z) - 0.004, z) for z in (0.045, 0.075, 0.105)] + \
            [(win(0.108) - 0.004, 0.1170), (0.0975, 0.1205), (0.1045, 0.1205), (0.1115, 0.1195), (0.1130, 0.1165)]
    NV = 3
    def path(a):
        L = 0.012 + 0.040 * max(0.0, math.cos(4 * (a - a0))) ** 1.2
        fold = 0.0025 * (0.5 + 0.5 * math.sin(5 * a + 1.3))
        return fixed + [(0.1130 + fold * k / NV, 0.1165 - L * k / NV) for k in range(1, NV + 1)]
    J = len(fixed) + NV
    bm = bmesh.new(); UV = bm.loops.layers.uv.verify()
    S = [[None] * J for _ in range(N)]; B = [[None] * J for _ in range(N)]
    cs = bm.verts.new((0, 0, ZT)); cb = bm.verts.new((0, 0, ZT - T))
    for i in range(N):
        a = 2 * math.pi * i / N; pts = path(a)
        nrm = []
        for j in range(J):
            sn = []
            if j > 0: d = (pts[j][0] - pts[j - 1][0], pts[j][1] - pts[j - 1][1]); l = math.hypot(*d); sn.append((-d[1] / l, d[0] / l))
            if j < J - 1: d = (pts[j + 1][0] - pts[j][0], pts[j + 1][1] - pts[j][1]); l = math.hypot(*d); sn.append((-d[1] / l, d[0] / l))
            nx, nz = sum(s[0] for s in sn), sum(s[1] for s in sn); l = math.hypot(nx, nz); nrm.append((nx / l, nz / l))
        for j in range(J):
            r, z = pts[j]; br, bz = r - T * nrm[j][0], z - T * nrm[j][1]
            S[i][j] = cs if j == 0 else bm.verts.new((r * math.cos(a), r * math.sin(a), z))
            B[i][j] = cb if j == 0 else bm.verts.new((br * math.cos(a), br * math.sin(a), bz))
    b0, h0 = ROWS["linen"]
    def uv(f, angs, js):
        for l, a, j in zip(f.loops, angs, js): l[UV].uv = (a / (2 * math.pi) * 32 / TEX, (b0 + 0.5 + j / (J - 1) * (h0 - 1)) / TEX)
    for i in range(N):
        i1 = (i + 1) % N; a0_, a1_ = 2 * math.pi * i / N, 2 * math.pi * (i + 1) / N
        for j in range(J - 1):
            if j == 0:
                uv(bm.faces.new([S[i][0], S[i][1], S[i1][1]]), (a0_, a0_, a1_), (0, 1, 1)); uv(bm.faces.new([B[i][0], B[i1][1], B[i][1]]), (a0_, a1_, a0_), (0, 1, 1))
            else:
                uv(bm.faces.new([S[i][j], S[i][j + 1], S[i1][j + 1], S[i1][j]]), (a0_, a0_, a1_, a1_), (j, j + 1, j + 1, j))
                uv(bm.faces.new([B[i][j], B[i1][j], B[i1][j + 1], B[i][j + 1]]), (a0_, a1_, a1_, a0_), (j, j, j + 1, j + 1))
        uv(bm.faces.new([S[i][J - 1], S[i1][J - 1], B[i1][J - 1], B[i][J - 1]]), (a0_, a1_, a1_, a0_), (J - 1, J - 1, J - 1, J - 1))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return link(bm, "linen")

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
        disc("riser", 0.0905, 0.0905, TB, TB + 0.050, "hewn", o, 16)                       # a round timber riser inside, up to the rim: the platters lie on it like lids
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
        shell("basket", v["prof"], v["t"], "wicker", SEG, bottom=True, tb=v["tb"], at=o, rotz=rng.uniform(0, 2 * math.pi))
        shell("basketrim", [(0.109, 0.100), (0.109, 0.116)], 0.009, "rope", 16, bottom=False, at=o)          # the rope rim: a ring 3 mm proud of the wall, its inner side inside the wall
        shell("basketband", [(0.1065, 0.035), (0.1065, 0.047)], 0.006, "rope", 16, bottom=False, at=o)       # a binding round the belly
        basket_cloth(math.pi / 4 + rng.uniform(-0.15, 0.15))
    else: build_stand()

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
    print("PAN3 vessel %-8s parts %d tris %d" % (fam, len(PARTS), VESSEL_TRIS[fam]), flush=True)
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
print("PAN3 frame tris", FRAME_TRIS, "parts", len(FRAME_PARTS), flush=True)
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
#   HEAP (physics-settled in a round vessel, up into the crown): mode "pile" = on its broad side, tilts up to 18 degrees (flat pouches heaped in a jar, none on edge); "lie" = on its broad side,
#   tilts up to 15 (herb bundles criss-cross); "natural" = in the pose it has in the rip, tilts up to 25 (loaves, dough, mushrooms in a basket, big feast platters in a crock, flour sacks in a sack).
#   STAND (placed, on the tiers): every dish flat in its rip pose, cells (sub-columns, sub-rows) per cell, layers = how many dishes high (only flat-topped pies and pans stack).
HEAP = {
    "SpiceForests": ("pile", 0.098, 22), "SpicePlains": ("pile", 0.098, 22), "SpiceMountains": ("pile", 0.098, 22), "SpiceOceans": ("pile", 0.098, 22),
    "SpiceMistlands": ("pile", 0.098, 22), "SpiceDeepNorth": ("pile", 0.098, 22), "SpiceAshlands": ("pile", 0.098, 22),
    "BreadDough": ("natural", 0.090, 12), "FragrantBundle": ("lie", 0.105, 10), "FishAndBreadUncooked": ("natural", 0.072, 20), "MagicallyStuffedShroomUncooked": ("natural", 0.092, 12),
    "BarleyFlour": ("lie", 0.072, 12), "OatFlour": ("lie", 0.078, 12),
}
for _n in PANTRY:
    if _n.startswith("Feast"): HEAP[_n] = ("natural", 0.155, 4)
STAND_SPEC = {      # (sub-columns, sub-rows, layers) per cell
    "BakedPoteitrUncooked": (1, 1, 1), "HoneyGlazedChickenUncooked": (1, 1, 1), "KaleChipsUncooked": (1, 1, 1), "MeatPlatterUncooked": (1, 1, 1), "MisthareSupremeUncooked": (1, 1, 1),
    "LoxPieUncooked": (1, 1, 2), "PiquantPieUncooked": (1, 1, 2), "RoastedCrustPieUncooked": (1, 1, 1), "OvenPancakeUncooked": (1, 1, 2), "VikingCupcakeUncooked": (2, 2, 1),
}
TILT = {"pile": 18, "lie": 15, "natural": 25, "upright": 8}
HEAP = {k: v for k, v in HEAP.items() if k in PANTRY}; STAND_SPEC = {k: v for k, v in STAND_SPEC.items() if k in PANTRY}
assert set(HEAP) | set(STAND_SPEC) == set(PANTRY) and not (set(HEAP) & set(STAND_SPEC)), (set(PANTRY) - set(HEAP) - set(STAND_SPEC))

TRI_PER_VESSEL = 7000                       # item triangles a full vessel may hold (jar, basket, sack)
TRI_FEAST = 7000                            # the feast platters are 2.5k-14.2k triangles each: copies per crock = 7000 // triangles, at least 1
TPL = {}
def fam_of(name): return PANTRY.get(name, "generic")
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
    ent = dict(datas=datas, verts=verts, size=size, A=A, tris=ntri, hv=hv, F=F, N=np.array(N), D=np.array(D), vol=vol, fam=fam_of(name))
    if name == "_generic": mode, Lb, cap = "pile", 0.09, 3
    elif name in STAND_SPEC: mode, Lb, cap = "stand", None, 8
    else:
        mode, Lb, cap = HEAP[name]
        if name.startswith("Feast"): cap = int(max(1, min(cap, TRI_FEAST // max(ntri, 1))))
        else: cap = int(max(2, min(cap, TRI_PER_VESSEL // max(ntri, 1))))
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


# ---------- the settle (r2's; one clear space per kind side by side, the cone-topped cylinders; only the heaps of the round vessels) ----------
CELL = 0.005
class HF:
    def __init__(self, fam="jar"):
        self.n = 64; self.x0 = -0.16
        self.h = np.full((self.n, self.n), CLR[fam].get("z0", 0.0) if fam in CLR else 0.0)
        g = (np.arange(self.n) + 0.5) * CELL + self.x0
        self.X, self.Y = np.meshgrid(g, g, indexing="ij")
        if fam == "stand": self.mask = np.ones((self.n, self.n), bool)
        else: self.mask = np.hypot(self.X, self.Y) <= CLR[fam]["R"] - 0.004
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
GXY = [(x, y) for x in np.arange(-0.092, 0.092 + 1e-9, GSTEP) for y in np.arange(-0.092, 0.092 + 1e-9, GSTEP) if math.hypot(x, y) <= 0.092 - 0.008]
def lowest_spot(st, h, rr):
    t = st["t"]; s = t["s"]; cands = []; fam = st["fam"]; Rf = CLR[fam]["R"]; Hf = CLR[fam]["H"]
    for _o in range(8):
        tl = t["tilt"]
        if t["mode"] in ("lie", "pile"): R = np.array(Rz(rr.uniform(0, 360)) @ Rx(rr.uniform(-tl, tl)) @ Ry(rr.uniform(-tl, tl))) @ t["A"]
        elif t["mode"] in ("upright", "natural"): R = np.array(Rz(rr.uniform(0, 360)) @ Rx(rr.uniform(-tl, tl)) @ Ry(rr.uniform(-tl, tl)))
        else: R = rand_rot(rr)
        HV = (t["hv"] * s) @ R.T; Nr = t["N"] @ R.T; Dr = t["D"] * s
        lo, hi = HV.min(0), HV.max(0); rc = float(np.hypot(HV[:, 0], HV[:, 1]).max())
        for x, y in GXY:
            if math.hypot(x, y) + rc > Rf - 0.005: continue
            rest, idx, sup = drop_z(st["hf"], h, Nr, Dr, lo, hi, x, y)
            z = rest + 0.006
            if z + hi[2] > Hf - 0.003 or sup < 0.12: continue
            P = HV + np.array((x, y, z))
            if not in_clear(P, fam, 0.005).all(): continue
            cands.append((round((z + lo[2]) / 0.005) + 2.0 * (1 - sup) - 1.5 * math.hypot(x, y) / Rf + rr.uniform(0, 0.6), R, np.array((x, y, z)), idx, hi))
    if not cands: return None
    cands.sort(key=lambda c: c[0])
    return cands[rr.randrange(min(3, len(cands)))]

def collider_slabs(ox, fam):
    """the passive colliders of a round clear space: a floor, a ring of upright slabs to the cone's start, then a ring of slabs leaning inward (the crown of the heap)"""
    c = CLR[fam]; R = c["R"]; zr = c["zr"]
    z0 = c.get("z0", 0.0)
    out = [(Matrix.Translation((ox, 0, z0 - 0.05)), (0.6, 0.6, 0.1))]
    n = 32; ri = R - COL_IN; T = 0.03; w = 2 * ri * math.tan(math.pi / n) * 1.08
    Hv = zr if zr is not None else c["H"] + 0.08
    for i in range(n):
        a = 2 * math.pi * (i + 0.5) / n
        M = Matrix.Rotation(a, 4, "Z"); M.translation = Vector((ox + (ri + T / 2) * math.cos(a), (ri + T / 2) * math.sin(a), Hv / 2))
        out.append((M, (T, w, Hv)))
    if zr is not None:
        beta = math.atan(c.get('tb', TANB)); ztop = c["H"] + 0.05
        Hs = (ztop - zr) / math.cos(beta); zm = (zr + ztop) / 2; rm = ri - (zm - zr) * c.get('tb', TANB)
        for i in range(n):
            a = 2 * math.pi * (i + 0.5) / n
            u = Vector((math.cos(a), math.sin(a), 0)); tg = Vector((-math.sin(a), math.cos(a), 0)); zh = Vector((0, 0, 1))
            nrm = u * math.cos(beta) + zh * math.sin(beta); sl = -u * math.sin(beta) + zh * math.cos(beta)
            M = Matrix((nrm, tg, sl)).transposed().to_4x4()
            M.translation = Vector((ox, 0, 0)) + u * rm + zh * zm + nrm * (T / 2)
            out.append((M, (T, w, Hs)))
    return out

def hull_bvh(b, t):
    return BVHTree.FromPolygons([Vector(v) for v in b["HV"]], [tuple(int(i) for i in f) for f in t["F"]])

def copy_gap(s, b, fr):
    """how far a settled copy hangs above what holds it (its floor, the heap's wall or a lower copy): hull against hull, mm-accurate; penetration counts as 0"""
    t = s["t"]; P = b["HV"]; span = P[:, 2].max() - P[:, 2].min()
    low = P[P[:, 2] <= P[:, 2].min() + 0.35 * span + 1e-6]
    g = min(float(low[:, 2].min()) - CLR[s["fam"]].get("z0", 0.0), wall_gap(low, s["fam"]))
    bb = None
    for q in fr:
        if (q["HV"].min(0) > P.max(0) + 0.02).any() or (q["HV"].max(0) < P.min(0) - 0.02).any(): continue
        d = q["D"][None, :] - P @ q["N"].T
        if (d > 0).all(1).any(): return 0.0
        g = min(g, min(hull_bvh(q, t).find_nearest(Vector(p))[3] for p in low))
        if bb is None: bb = hull_bvh(b, t)
        Q = q["HV"][q["HV"][:, 2] >= q["HV"][:, 2].max() - 0.35 * (q["HV"][:, 2].max() - q["HV"][:, 2].min())]
        g = min(g, min(bb.find_nearest(Vector(p))[3] for p in Q))
    return max(g, 0.0)

def finish(s):
    s["done"] = True; n = len(s["frozen"])
    cut = [math.ceil(n * k / UNITS_PER) for k in range(UNITS_PER + 1)]
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
        ox = 0.4 * i; fam = fam_of(name)
        for M, dm in collider_slabs(ox, fam):
            col = bpy.data.objects.new("col", cube); sc.collection.objects.link(col)
            col.matrix_world = M @ Matrix.Diagonal((dm[0], dm[1], dm[2], 1))
            rb = set_rb(col, "PASSIVE"); rb.collision_shape = "BOX"; rb.use_margin = True; rb.collision_margin = 0.0
        t = tpl(name)
        ST[name] = dict(t=t, fam=fam, ox=ox, hf=HF(fam), hfl=HF(fam), frozen=[], fails=0, done=False)
    stats = dict(attempts=0, frames=0, rejected=0)
    while not all(s["done"] for s in ST.values()):
        sc.frame_set(1); spawned = []
        for name, s in ST.items():
            if s["done"]: continue
            t = s["t"]; tmp = s["hf"].h.copy(); nb = 1 + (t["cap"] > 9) + (t["cap"] > 50); got = 0
            for _b in range(min(nb, t["cap"] - len(s["frozen"]))):
                best = lowest_spot(s, tmp, rr)
                if best is None: break
                _, R, c, (i0, i1, j0, j1), hi = best
                tmp[max(0, i0 - 3):i1 + 4, max(0, j0 - 3):j1 + 4] = CLR[s["fam"]]["H"] + 1
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
                N = t["N"] @ R.T; D = t["D"] * t["s"] + N @ c
                nb_ = dict(R=R, c=c, id=len(s["frozen"]), HV=HV, N=N, D=D)
                if in_clear(HV, s["fam"]).all() and copy_gap(s, nb_, s["frozen"]) <= 0.003:
                    ob.matrix_world = Matrix(M.tolist()); ob.rigid_body.type = "PASSIVE"
                    s["frozen"].append(nb_)
                    s["hf"].add(N, D); s["hfl"].add(N, D, dilate=False); s["fails"] = 0
                else:
                    bpy.data.objects.remove(ob); s["fails"] += 1; stats["rejected"] += 1
        for name, s in ST.items():
            if s["done"]: continue
            if len(s["frozen"]) >= s["t"]["cap"] or s["fails"] >= 8:
                n, cut = finish(s)
                print("PAN3 %-30s full: %2d copies (cap %d), scale %.3f, level %.3f, top %.3f, stacks %s" % (name, n, s["t"]["cap"], s["t"]["s"], s["hfl"].level(),
                      max(float(b["HV"][:, 2].max()) for b in s["frozen"]) if n else 0, [cut[k + 1] - cut[k] for k in range(UNITS_PER)]), flush=True)
    for o in [o for o in bpy.data.objects if o.rigid_body is not None]: bpy.data.objects.remove(o)
    bpy.ops.rigidbody.world_remove()
    sc.frame_set(1)
    return ST, stats

HEAPKINDS = [n for n in ITEMS if n in HEAP] + ["_generic"]
ST, SIMST = settle(HEAPKINDS)
print("PAN3 SIM", SIMST, "%.0fs" % (time.time() - t0), flush=True)

# ---------- the placed layouts: the stand (a cook lines the dishes up, tier by tier) ----------
def stand_layout(name):
    """per tier: the cells (4 on the lowest plank, 2 on each upper one), in each cell cols x rows dishes, every dish flat in the pose it has in the rip (yaw 0 or 90, whichever lets it grow
    larger, a few degrees of turn), layers high: each rests on the plank or on the dishes below (hull against height field + 1 mm). One scale per kind. Stack 0 = the lowest tier,
    stack 1 = the two upper tiers."""
    rr = random.Random(zlib.crc32(name.encode()))
    t = tpl(name); sc_, sr_, layers = STAND_SPEC[name]
    subw, subd = CELL_W / sc_, CELL_D / sr_
    best = None
    for yaw in (0, 90):
        R0 = np.array(Rz(yaw)); HV0 = t["hv"] @ R0.T; ext = HV0.max(0) - HV0.min(0)
        s_ = min(subw * 0.90 / ext[0], subd * 0.90 / ext[1], (TCLEAR - 0.008) / layers / ext[2])
        if best is None or s_ > best[0] + 1e-9: best = (s_, yaw)
    s_, yaw0 = best
    for attempt in range(12):
        t["s"] = s_; frozen = []
        for ti in range(3):
            hf = HF("stand"); tier = []
            for L in range(layers):
                new = []
                for (cx, cy) in CELLS[ti]:
                    for j in range(sr_):
                        for i in range(sc_):
                            x = cx - CELL_W / 2 + (i + 0.5) * subw; y = cy - CELL_D / 2 + (j + 0.5) * subd
                            R = np.array(Rz(yaw0 + rr.uniform(-3, 3)))
                            HVr = (t["hv"] * s_) @ R.T; Nr = t["N"] @ R.T; Dr = t["D"] * s_
                            lo, hi = HVr.min(0), HVr.max(0)
                            rest, idx, sup = drop_z(hf, hf.h, Nr, Dr, lo, hi, x, y)
                            c = np.array((x, y, rest + (0.0005 if L == 0 else 0.001)))
                            if L > 0:                                          # lower the dish in 0.25 mm steps until its hull just touches the dish below
                                below = [b for b in tier if b["layer"] == L - 1 and (np.abs(b["cl"][:2] - c[:2]) < 0.05).all()]
                                bvs = [BVHTree.FromPolygons([Vector(v) for v in b["HVl"]], [tuple(int(k) for k in f) for f in t["F"]]) for b in below]
                                for _k in range(60):
                                    c2 = c - np.array((0, 0, 0.00025))
                                    me = BVHTree.FromPolygons([Vector(v) for v in (HVr + c2)], [tuple(int(k) for k in f) for f in t["F"]])
                                    if any(me.overlap(bv) for bv in bvs) or c2[2] + lo[2] < 0: break
                                    c = c2
                                c[2] += 0.0005
                            ca = c + np.array((0, 0, TIERZ[ti]))
                            new.append(dict(R=R, c=ca, cl=c, HVl=HVr + c, HV=HVr + ca, N=Nr, D=Dr + Nr @ ca, Dl=Dr + Nr @ c, tier=ti, layer=L, cell=(cx, cy), sup=round(sup, 2), stack=0 if ti == 0 else 1))
                for b in new: hf.add(b["N"], b["Dl"])
                tier += new
            frozen += tier
        top = max(float(b["HV"][:, 2].max() - TIERZ[b["tier"]]) for b in frozen)
        if top <= TCLEAR - 0.002: break
        s_ *= 0.96
    for k, b in enumerate(frozen): b["id"] = k
    print("PAN3 %-32s placed: %d copies (%d tiers, %dx%dx%d per cell), scale %.3f, yaw %d, top %.3f above a plank" % (name, len(frozen), 3, sc_, sr_, layers, t["s"], yaw0, top), flush=True)
    return dict(t=t, fam="stand", ox=0.0, hf=None, hfl=None, frozen=frozen, fails=0, done=True)
for _n in STAND_SPEC: ST[_n] = stand_layout(_n)
for _n, _s in ST.items():
    _e = [k for k in range(UNITS_PER) if not any(b["stack"] == k for b in _s["frozen"])]
    if _e: print("PAN3 WARNING empty stack", _n, _e, flush=True)
KINDS = [n for n in ITEMS] + ["_generic"]

# ---------- checks on the layouts ----------
def float_pen(name):
    s = ST[name]; t = s["t"]; fr = s["frozen"]; gaps = []; pen = 0.0
    for b in fr:
        P = b["HV"]; span = P[:, 2].max() - P[:, 2].min()
        low = P[P[:, 2] <= P[:, 2].min() + 0.35 * span + 1e-6]
        g = min(float(low[:, 2].min()) - CLR[s["fam"]].get("z0", 0.0), wall_gap(low, s["fam"]))
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

def stand_gap(name):
    """placed layouts: how far above its support each dish hangs: the gap from its lowest vertices to its plank (layer 0) or to the nearest lower dish's hull (layer 1)"""
    s = ST[name]; t = s["t"]; fr = s["frozen"]; worst = 0.0
    for b in fr:
        P = b["HV"]; low = P[P[:, 2] <= P[:, 2].min() + 0.25 * (P[:, 2].max() - P[:, 2].min()) + 1e-6]
        dn = [i for i in range(len(t["F"])) if b["N"][i][2] < -0.5]       # the downward faces of its hull: sample their corners and centres too, not only the vertices
        low = np.vstack([low] + [np.array([P[f].mean(0) for f in t["F"][dn]])] + [np.array([(P[f[0]] + P[f[1]]) / 2 for f in t["F"][dn]])])
        if b["layer"] == 0: g = float(low[:, 2].min()) - TIERZ[b["tier"]]
        else:
            g = 9.0
            for q in fr:
                if q["tier"] != b["tier"] or q["layer"] != b["layer"] - 1 or (q["HV"].min(0)[:2] > P.max(0)[:2]).any() or (q["HV"].max(0)[:2] < P.min(0)[:2]).any(): continue
                bv = hull_bvh(q, t); g = min(g, min(bv.find_nearest(Vector(p))[3] for p in low))
        if g > 0.003: print("PAN3 DEBUG gap", name, b["tier"], b["layer"], np.round(b["c"], 4), "gap_mm", round(g * 1000, 2), flush=True)
        worst = max(worst, g)
    return worst

def stand_overlap(name):
    """penetration between dishes of one tier (hull against hull, mm): 0 expected"""
    s = ST[name]; t = s["t"]; fr = s["frozen"]; pen = 0.0
    for b in fr:
        for q in fr[:b["id"]]:
            if q["tier"] != b["tier"] or (q["HV"].min(0) > b["HV"].max(0) + 0.002).any() or (q["HV"].max(0) < b["HV"].min(0) - 0.002).any(): continue
            d = q["D"][None, :] - b["HV"] @ q["N"].T; ins = (d > 0).all(1)
            if ins.any(): pen = max(pen, float(d[ins].min(1).max()))
    return pen

CHECK = {}
for name in KINDS:
    s = ST[name]; t = s["t"]; fr = s["frozen"]; fam_ = s["fam"]
    if fam_ == "stand":
        fmax = stand_gap(name); pen = stand_overlap(name)
        out = max(outside_cell((t["verts"] * t["s"]) @ b["R"].T + b["c"], b["tier"], b["cell"]) for b in fr)
        lv = [round(max(float(b["HV"][:, 2].max() - TIERZ[b["tier"]]) for b in fr if b["stack"] == k), 3) if any(b["stack"] == k for b in fr) else 0.0 for k in range(UNITS_PER)]
    else:
        fmax, pen = float_pen(name)
        P = np.vstack([(t["verts"] * t["s"]) @ b["R"].T + b["c"] for b in fr]) if fr else np.zeros((1, 3))
        out = outside_clear(P, fam_)
        hf = HF(fam_); lv = []
        for k in range(UNITS_PER):
            for b in fr:
                if b["stack"] == k: hf.add(b["N"], b["D"], dilate=False)
            lv.append(round(hf.level(), 3))
    P = np.vstack([(t["verts"] * t["s"]) @ b["R"].T + b["c"] for b in fr]) if fr else np.zeros((1, 3))
    CHECK[name] = dict(copies=len(fr), copies_by_stack=[sum(1 for b in fr if b["stack"] == k) for k in range(UNITS_PER)], cap=t["cap"],
                       mesh_outside_clear_mm=round(out * 1000, 1), float_worst_mm=round(fmax * 1000, 2),
                       overlap_max_mm=round(pen * 1000, 2), level_by_stacks_m=lv, top_m=round(float(P[:, 2].max()), 3),
                       longest_m=round(float(t["size"].max() * t["s"]), 3), drawn_tris_per_copy=t["tris"], tris_full_vessel=len(fr) * t["tris"])
    print("PAN3 CHECK %-32s %s" % (name, CHECK[name]), flush=True)

# ---------- clipping: copies/clear space vs vessels, vessels vs frame, clear space vs frame ----------
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
    PLO = np.array([p["lo"] for p in parts]) - slack; PHI = np.array([p["hi"] for p in parts]) + slack; hits = 0; notes = []
    inb = ((points[:, None, :] >= PLO[None]) & (points[:, None, :] <= PHI[None])).all(2)
    for qi in np.nonzero(inb.any(1))[0]:
        q = points[qi]
        for c in np.nonzero(inb[qi])[0]:
            if inside_part(parts[c]["bvh"], q): hits += 1; notes.append(parts[c]["name"]); break
    return hits, notes

def clear_points(fam):
    """sample points of a family's clear space (its surface every 1 cm, its inside every 2 cm), 1 mm in from the boundary, relative to the vessel floor"""
    pts = []
    if fam == "stand":
        for ti in range(3):
            for cx, cy in CELLS[ti]:
                x0, x1 = cx - CELL_W / 2 + 0.001, cx + CELL_W / 2 - 0.001; y0, y1 = cy - CELL_D / 2 + 0.001, cy + CELL_D / 2 - 0.001
                z0, z1 = TIERZ[ti] + 0.001, TIERZ[ti] + TCLEAR - 0.001
                for z in np.arange(z0, z1 + 1e-9, 0.01):
                    for x in np.arange(x0, x1 + 1e-9, 0.01): pts += [(x, y0, z), (x, y1, z)]
                    for y in np.arange(y0, y1 + 1e-9, 0.01): pts += [(x0, y, z), (x1, y, z)]
                for x in np.arange(x0, x1 + 1e-9, 0.02):
                    for y in np.arange(y0, y1 + 1e-9, 0.02):
                        for z in (z0, z1) + tuple(np.arange(TIERZ[ti] + 0.02, z1, 0.04)): pts.append((x, y, z))
        return np.array(pts)
    c = CLR[fam]; R = c["R"]; z0 = c.get("z0", 0.0)
    for z in np.arange(z0 + 0.001, c["H"] - 0.001 + 1e-9, 0.01):
        r = float(rad_at(fam, z)) - 0.001
        if r < 0.004: continue
        n = max(8, int(2 * math.pi * r / 0.01))
        pts += [(r * math.cos(a), r * math.sin(a), z) for a in np.linspace(0, 2 * math.pi, n, endpoint=False)]
    for x in np.arange(-R, R + 1e-9, 0.02):
        for y in np.arange(-R, R + 1e-9, 0.02):
            for z in (z0 + 0.001, c["H"] - 0.001) + tuple(np.arange(z0 + 0.02, c["H"], 0.04)):
                if math.hypot(x, y) <= float(rad_at(fam, z)) - 0.001: pts.append((x, y, z))
    return np.array(pts)

def in_clear_any(Q, eps=0.001):
    """points (relative to a floor) inside any family's clear space (the frame's vertices are tested against these)"""
    hit = np.zeros(len(Q), bool)
    for fam in ROUND: hit |= in_clear(Q, fam, eps)
    for ti in range(3):
        for cx, cy in CELLS[ti]:
            hit |= ((Q[:, 2] >= TIERZ[ti] + eps) & (Q[:, 2] <= TIERZ[ti] + TCLEAR - eps) & (np.abs(Q[:, 0] - cx) <= CELL_W / 2 - eps) & (np.abs(Q[:, 1] - cy) <= CELL_D / 2 - eps))
    return hit & (Q[:, 2] > eps)

CS = {fam: clear_points(fam) for fam in FAMILIES}                 # relative to the floor centre (shelf surface + TB)
FLOORS = [np.array(place_origin(n)) + np.array((0, 0, TB)) for n in range(NPLACE)]

# (a) the clear space against each vessel (local coordinates): 0 points inside a vessel part
VES_CYL = {}
for fam in FAMILIES:
    h, notes = count_inside(CS[fam] + np.array((0, 0, TB)), VESSEL_PARTS[fam]); VES_CYL[fam] = h
    print("PAN3 clear space vs vessel %-8s: %d of %d points inside %s" % (fam, h, len(CS[fam]), notes[:4]), flush=True)
# (b) every copy (all its vertices) inside its clear space, i.e. clear of every vessel (a) -> the max over all layouts
COPY_OUT = max(CHECK[n]["mesh_outside_clear_mm"] for n in KINDS)      # <= 0: inside the clear space
FV = np.vstack([p["V"] for p in FRAME_DATA])
ves_frame = {}; cyl_frame = 0; cyl_notes = []; fv_in = 0
for n in range(NPLACE):
    org = np.array(place_origin(n))
    for fam in FAMILIES:
        pts = np.vstack([np.vstack([p["V"], p["cent"]]) for p in VESSEL_PARTS[fam]]) + org
        pts = pts[pts[:, 2] > org[2] + 0.003]
        h, notes = count_inside(pts, FRAME_DATA)
        ves_frame[(n, fam)] = h
        if h: print("PAN3 vessel %s at place %d inside frame: %d %s" % (fam, n, h, notes[:3]), flush=True)
        h, notes = count_inside(CS[fam] + FLOORS[n], FRAME_DATA); cyl_frame += h; cyl_notes += notes
    Q = FV - FLOORS[n]; fv_in += int(in_clear_any(Q, 0.001).sum())
VES_FRAME = sum(ves_frame.values())
print("PAN3 vessels vs frame: %d vessel points inside frame parts (%d vessel x place combinations); clear spaces vs frame: %d points %s, frame vertices in a clear space %d" %
      (VES_FRAME, len(ves_frame), cyl_frame, cyl_notes[:3], fv_in), flush=True)
# (d) neighbours: the widest vessel against the 0.24 m pitch
RMAX = {f: max(float(np.hypot(p["V"][:, 0], p["V"][:, 1]).max()) for p in VESSEL_PARTS[f]) for f in FAMILIES}       # the round ones: the radius; the stand: the corner (half-diagonal)
YEXT = {f: round(max(float(np.abs(p["V"][:, 1]).max()) for p in VESSEL_PARTS[f]), 3) for f in FAMILIES}
XEXT = {f: round(max(float(np.abs(p["V"][:, 0]).max()) for p in VESSEL_PARTS[f]), 3) for f in FAMILIES}
ZEXT = {f: round(max(float(p["V"][:, 2].max()) for p in VESSEL_PARTS[f]), 3) for f in FAMILIES}
print("PAN3 vessel x half-extent", XEXT, "widest pair", round(2 * max(XEXT.values()), 3), "of", PITCH, "; y half-extent", YEXT, "; height", ZEXT, flush=True)


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
    stacks = []
    for k in range(UNITS_PER):
        cps = []
        for b in s["frozen"]:
            if b["stack"] != k: continue
            cp = {"offset": uvec(b["c"]), "rot_quat_xyzw": uquat(b["R"])}
            if s["fam"] == "stand": cp["tier"] = b["tier"]; cp["layer"] = b["layer"]
            cps.append(cp)
        stacks.append(cps)
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
        ent["note"] = "fallback for any item without its own layout in any vessel: a neutral round lump (a settled heap), scaled uniformly so its longest bounds side is fit_longest_m; it fits every round family's clear space (the stand's units carry their own lumps, one per cell)."
    else:
        ent["model"] = "the item's own ripped model (C:/Users/joost/ValheimRip/items/%s)" % name
        if name in STAND_SPEC:
            sc_, sr_, layers = STAND_SPEC[name]
            ent["layout"] = {"kind": "placed", "tiers": 3, "cells_per_tier": [len(CELLS[k]) for k in range(3)], "per_cell": {"cols": sc_, "rows": sr_, "layers": layers},
                             "stack_is": "tier group (stack 0 = the lowest tier, stack 1 = the two upper tiers)", "copy_fields": "tier 0..2, layer 0..%d (a 2nd layer rests on the 1st)" % (layers - 1)}
        else: ent["layout"] = {"kind": "heap", "settled_in": "%s (clear space with a cone-shaped crown)" % PANTRY[name]}
    layouts[name] = ent
GEN = layouts["_generic"]
ITEM_FAMILY = {k: v for k, v in PANTRY.items() if k in ITEMS}
def stand_lumps(k):
    """the fallback lumps of a stand unit: one per cell (stack 0: the lowest tier's 4 cells, stack 1: the upper tiers' 4)"""
    out = []
    for ti in ([0] if k == 0 else [1, 2]):
        for cx, cy in CELLS[ti]: out.append(uvec((cx, cy, TIERZ[ti] + 0.037)))
    return out
units = []
for n in range(NPLACE):
    r, c = divmod(n, NCOL)
    for fam in FAMILIES:
        if fam == "stand": hh = STAND_H
        else: hh = CLR[fam]["H"]
        cen = FLOORS[n] + np.array((0, 0, hh / 2))
        if fam == "stand": box = [round(2 * (CELL_CX + CELL_W / 2), 4), round(STAND_H, 4), round(2 * (CELL_CY + CELL_D / 2), 4)]
        else: box = [round(2 * CLR[fam]["R"], 4), round(CLR[fam]["H"], 4), round(2 * CLR[fam]["R"], 4)]
        for k in range(UNITS_PER):
            if fam == "stand":
                copies = [{"offset": [o[0], round(o[1] - hh / 2, 4), o[2]], "rot_quat_xyzw": [0, 0, 0, 1], "fit_longest_m": GEN["fit_longest_m"]} for o in stand_lumps(k)]
            else:
                copies = [{"offset": [round(cp["offset"][0], 4), round(cp["offset"][1] - hh / 2, 4), round(cp["offset"][2], 4)],
                           "rot_quat_xyzw": cp["rot_quat_xyzw"], "fit_longest_m": GEN["fit_longest_m"]} for cp in GEN["stacks"][k]]
            units.append({"index": len(units), "bin": n, "place": n, "kind": fam, "vessel": fam, "tier": r, "col": c, "fill_step": k, "position": uvec(cen),
                          "rotation": [0, 0, 0], "box": box, "copies": copies})
vessels = [{"position": n, "at": uvec(place_origin(n)), "default": DEFAULT[n]} for n in range(NPLACE)]
heaviest = max(ITEMS, key=lambda n: CHECK[n]["tris_full_vessel"])
PLACES_OF = {f: sum(1 for d in DEFAULT if d == f) for f in FAMILIES}
full_store = {n: NPLACE * (CHECK[n]["tris_full_vessel"] + VESSEL_TRIS[PANTRY[n]]) + FRAME_TRIS for n in ITEMS}      # every one of the 40 places holding this one kind, both stacks
worst_item = max(full_store, key=full_store.get)
FULL_DEMO_TRIS = FRAME_TRIS + sum(VESSEL_TRIS[PANTRY[it]] + CHECK[it]["tris_full_vessel"] for it in FULL_ASSIGN if it)
doc = {
    "store": "Pantry Dresser round 3 (blender/pantry_r3.py): 2.16 m wide, 5 tiers of 8 places, the vessel follows the item; real item models; tiered serving stands (3 tiers on one post), linen-lined wicker baskets, heaps that crown above the rim",
    "rule": "what you cook with: flours, dough, herbs, spices, feast ingredients and the uncooked dishes waiting for the oven; one kind per place, the vessel is the item's family (jar, basket, stand, crock, sack): spices in jars, dough, herbs, loaves and shrooms heaped in linen-lined baskets, dishes and cupcakes on three-tier serving stands, feast ingredients in crocks, flour in sacks",
    "items": ITEMS, "item_family": ITEM_FAMILY, "families": FAMILIES,
    "family_kinds": {f: sorted(n for n in ITEMS if PANTRY[n] == f) for f in FAMILIES},
    "slots": 80, "places": NPLACE, "grid": [NCOL, len(LEVEL)], "units_total": len(units), "units_per_family": {f: sum(1 for u in units if u["kind"] == f) for f in FAMILIES},
    "units_split": ("every one of the %d places has %d units (stacks) for each of the %d families: %d x %d x %d = %d units, %d per family, so any one family can show all 80 slots; "
                    "a full place = %d stacks of one kind, a place holding fewer shows a vessel that is only partly full (a stand: its lowest tier only). Not every stack needs its own place: %d kinds share %d places."
                    % (NPLACE, UNITS_PER, len(FAMILIES), NPLACE, len(FAMILIES), UNITS_PER, len(units), NPLACE * UNITS_PER, UNITS_PER, len(ITEMS), NPLACE)),
    "full_demo": FULL_ASSIGN,
    "stacks_per_place_and_family": UNITS_PER, "stack_per_unit": 1, "placement": "wall",
    "frame": {"obj": "Pantry.obj", "tris": FRAME_TRIS, "size_m": [round(W + 0.07, 3), H + 0.0, DEPTH + 0.06], "atlas": "pantry_atlas.png 128x128 point",
              "atlas_rows": "v px from the bottom: 96-127 hewn, 64-95 end grain, 48-63 iron (byte-identical from bunker_r4), 36-47 clay, 16-23 glass, 24-35 wicker (baskets, apothecary_r2's), 12-15 linen (the basket cloth), 8-11 hessian (sacks), 4-7 cord, 0-3 swatches cork/ivory/amber/crust/flour/bright glass/worn timber/soot"},
    "space": "Unity prefab space, metres. Origin: the wall plane (back face, z = 0), x centred, y = 0 the foot; front is +z. Blender z-up/-y front -> Unity: ux=-bx, uy=bz, uz=-by. OBJ exported forward -Z, up Y (the mod loads it flipX).",
    "vessel_meshes": {f: "Vessel_%s.obj" % f for f in FAMILIES},
    "vessel_meshes_doc": ("one mesh per family in the same OBJ convention as the frame, in local coordinates: origin = the centre of the vessel's footprint at the shelf "
                          "surface (vessels[].at); draw it at 'at' (no rotation) with the frame's material. Tris: %s." % ", ".join("%s %d" % (f, VESSEL_TRIS[f]) for f in FAMILIES)),
    "vessels": vessels,
    "vessels_doc": ("one entry per place: 'at' = where its vessel stands (prefab space), 'default' = the family the place is for (light on top, heavy below: the order the mod claims "
                    "places in is jar, basket, stand, crock, sack, each kind by name, in reading order; the defaults are the full demo: %s places). An EMPTY place draws nothing. A place holding an "
                    "item draws the vessel of the item's family (item_family): the vessel follows the item. place n = tier * 8 + column; tier 0 is the top, column 0 the left as seen "
                    "from the front (Blender x ascending, Unity x descending)." % ", ".join("%s %d" % (f, PLACES_OF[f]) for f in FAMILIES)),
    "groups": ("place 0..%d = one vessel position (key 'bin' in units_list, which the mod already reads as the group; 'place' repeats it). EVERY place has units for EVERY "
               "family: kind = %s, %d stacks (fill_step 0..%d) each, same position in all %d. The clear space of the round vessels (jar, basket, crock, sack) is an upright cylinder %s "
               "(radius x height; basket, crock and sack close inward above their rim as a cone), that of the stand eight cell boxes (the unit's 'box' is their bounding box "
               "%.3f x %.3f x %.3f), all standing on crate_floor_centres[place]."
               % (NPLACE - 1, " | ".join(FAMILIES), UNITS_PER, UNITS_PER - 1, len(FAMILIES), ", ".join("%s %.3f x %.3f" % (f, CLR[f]["R"], CLR[f]["H"]) for f in ROUND),
                  2 * (CELL_CX + CELL_W / 2), STAND_H, 2 * (CELL_CY + CELL_D / 2))),
    "clear_spaces": {"round": {f: dict(radius_m=CLR[f]["R"], height_m=CLR[f]["H"], cone_starts_m=CLR[f]["zr"], cone_shrink_per_m=CLR[f].get("tb", TANB) if CLR[f]["zr"] is not None else None) for f in ROUND},
                     "stand": {"tier_floors_m": TIERZ, "clear_height_above_tier_m": TCLEAR, "cell_size_m": [CELL_W, CELL_D], "cells_xy_m_blender": {str(k): [list(map(float, c)) for c in v] for k, v in CELLS.items()},
                               "post_radius_m": ROD_R, "plank_widths_m": PLANK_W, "plank_depth_m": PLANK_D}},
    "crate_floor_centres": [uvec(fc) for fc in FLOORS],
    "crop_layouts": layouts,
    "crop_layouts_doc": ("crop_layouts: one full vessel per item kind, as apothecary_r2 / pantry_r2; '_generic' (any other item in any vessel). All 32 are the REAL prefab models. A place holding n stacks of a kind shows "
                         "stacks[0..n-1] of that kind's layout (%d stacks). Per copy: the item's model scaled uniformly (by 'scale' x its true size where 'scale' is set, else to "
                         "fit_longest_m), turned by rot_quat_xyzw about its bounds centre, that centre at crate_floor_centres[place] + offset. layout.kind 'heap' (jar, basket, crock, sack; "
                         "mode pile/lie/natural/tumble) is physics-settled (stack k dropped onto stacks 0..k-1) and crowns above the vessel's rim; layout.kind 'placed' (stand) lines the dishes up flat "
                         "in their rip pose on the stand's three planks: copies carry 'tier' (0 lowest) and 'layer' (pies and pans two high, the 2nd on the 1st); stack 0 = the lowest tier, stack 1 = the two upper tiers. "
                         "Every layout fits its family's clear space, so it fits every place of its family. Dishes keep their own plate or tin down; nothing stands on edge, nothing floats." % UNITS_PER),
    "liquids": [],
    "unit_semantics": ("units_list: one unit = one stack, %d per place and family in fill order; kind = the family; copies = the generic lump as Fit.Longest copies "
                       "(centre at position + offset; one per cell on a stand), a fallback only." % UNITS_PER),
    "physics": ("heaps: Blender rigid body (Bullet), each copy the convex hull of its item, friction 0.6, restitution 0, damping 0.5/0.95, margin 1 mm, substeps 20, iterations 40, "
                "in the clear space made of passive box slabs (round vessels only: upright slabs to the cone's start, then slabs leaning inward); copies drop one or two at a time at one of the "
                "three lowest well-supported spots of a 1 cm grid x 8 orientations, settled, checked inside the clear space, then frozen; until no copy fits or the kind's cap (~%d item triangles per "
                "vessel; Feast kinds %d per crock, at least one copy)." % (TRI_PER_VESSEL, TRI_FEAST)),
    "checks": {"copies_outside_clear_space_mm_max": COPY_OUT, "clear_points_inside_vessel": VES_CYL, "clear_points_per_family": {k: len(v) for k, v in CS.items()},
               "coplanar_same_facing_overlaps": COP,
               "vessel_points_inside_frame": VES_FRAME, "vessel_places_checked": len(ves_frame), "clear_space_points_inside_frame": cyl_frame,
               "frame_vertices_inside_clear_spaces": fv_in, "vessel_radius_m": {k: round(v, 3) for k, v in RMAX.items()}, "vessel_x_half_extent_m": XEXT, "vessel_y_half_extent_m": YEXT, "vessel_height_m": ZEXT, "pitch_m": PITCH,
               "rotation_roundtrip_max_err": rt, "sim": SIMST,
               "overlap_between_copies_mm_max": max(CHECK[n]["overlap_max_mm"] for n in KINDS), "float_worst_mm_max": max(CHECK[n]["float_worst_mm"] for n in KINDS)},
    "tris": {"frame": FRAME_TRIS, "vessels": VESSEL_TRIS,
             "full_store_worst_kind": {"item": worst_item, "tris": full_store[worst_item], "note": "every one of the 40 places holding this one kind, both stacks"},
             "full_store_every_kind": {n: full_store[n] for n in sorted(ITEMS, key=lambda n: -full_store[n])},
             "heaviest_kinds_full_vessel": {n: CHECK[n]["tris_full_vessel"] for n in sorted(ITEMS, key=lambda n: -CHECK[n]["tris_full_vessel"])[:8]},
             "full_demo": FULL_DEMO_TRIS},
    "units_list": units,
}
if EXPORT:
    out = os.path.join(OUTA, "pantry_anchors.json"); tmp = out + ".tmp"
    with open(tmp, "w") as fh: json.dump(doc, fh, indent=1)
    os.replace(tmp, out)
    print("PAN3 wrote", out, flush=True)
print("PAN3 STATS frame %d, vessels %s, copies %d, tris %s, roundtrip %.2g" % (FRAME_TRIS, VESSEL_TRIS, sum(c["copies"] for c in CHECK.values()), doc["tris"], rt), flush=True)

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
    # the round-compare views (the same camera in pantry_r1.py / pantry_r2.py runs through scratchpad/pantry_r3/mkcmp.py): standing eye height 1.62 m, 3.8 m away
    CMP = [("front", (0, 9.4, 3.8, (0, -0.25, 1.0))), ("34", (-30, 9.4, 3.8, (0, -0.25, 1.0)))]
    fill(FULL)
    for nm, v in CMP:
        look(*v); render("cmp-%s-r3.png" % nm, 1600, 1000)
    V34 = (-26, 8, 5.4, (0, -0.2, 1.07))
    look(*V34); render("pantry3-full.png")
    look(-4, 4, 5.0, (0, -0.24, 1.07)); render("pantry3-full-front.png")
    clear(); look(*V34); fill([]); render("pantry3-empty.png")
    fill(HALF); render("pantry3-half.png"); clear()
    fill(FULL)
    for tier, nm in ((0, "jars"), (1, "baskets-stands"), (2, "stands"), (3, "crocks"), (4, "crocks-sacks")):
        look(-10, 12, 2.5, (0, -0.25, LEVEL[tier] + 0.13)); render("pantry3-closeup-tier%d-%s.png" % (tier, nm))
    # the stands from the front, from above and three-quarter (tier 2: ten kinds on 8 places, cupcakes last)
    look(0, 6, 1.7, (0, -0.25, LEVEL[2] + 0.12)); render("pantry3-closeup-stands-row-front.png")
    look(-4, 26, 1.7, (0, -0.25, LEVEL[2] + 0.10)); render("pantry3-closeup-stands-row-above.png")
    look(-24, 18, 0.95, (COLX[3], -0.25, LEVEL[2] + 0.13)); render("pantry3-closeup-stands-three-quarter.png")
    look(24, 18, 0.95, (COLX[6], -0.25, LEVEL[2] + 0.13)); render("pantry3-closeup-stands-three-quarter-right.png")
    look(-20, 16, 0.75, (COLX[7], -0.25, LEVEL[2] + 0.13)); render("pantry3-closeup-stand-cupcakes.png")
    look(-22, 16, 0.95, (COLX[2], -0.25, LEVEL[1] + 0.07)); render("pantry3-closeup-baskets.png")
    look(22, 22, 0.55, (COLX[1], -0.25, LEVEL[1] + 0.08)); render("pantry3-closeup-basket-cloth.png")
    look(-10, 20, 1.3, (COLX[4], -0.25, LEVEL[4] + 0.10)); render("pantry3-closeup-crocks-sacks-above.png")
    # as a player sees it: 2.2 m from the front, eye height 1.6 m
    cam.data.lens = 24; cam.location = (0.0, -2.45, 1.6); cam.rotation_euler = (math.radians(78), 0, 0)
    render("pantry3-from-2m-eye1.6.png", 1400, 1000); cam.data.lens = 38
    # the dresser beside apothecary_r2 and bunker_r4 (as shipped, same scale, same ground), and a 1.8 m post for scale
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
    look(-8, 8, 14.2, (0.15, -0.5, 0.95)); render("pantry3-full-beside-apothecary_r2-bunker_r4.png", 2000, 900)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(1.75, -0.7, 0.9)); post = bpy.context.active_object; post.scale = (0.1, 0.1, 1.8)
    pm = bpy.data.materials.new("post"); pm.use_nodes = True
    pm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.85, 0.85, 0.88, 1); post.data.materials.append(pm)
    look(-8, 5, 5.8, (0.2, -0.2, 1.07)); render("pantry3-full-post-1.8m.png")
    bpy.data.objects.remove(post)
print("DONE %.0fs" % (time.time() - t0))
