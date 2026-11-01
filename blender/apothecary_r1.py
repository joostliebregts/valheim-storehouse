"""Apothecary Rack round 1: a wall rack of hand-sized vessels for creature parts (the concept sketch made real).
Rule: small things a creature leaves behind that you can't eat or wear (eyes, fangs, feathers, jelly, glands, scales...);
never meat, bones, hides, ore or trophies (they have their own stores). The prefab list is ITEMS below, also written to
assets/apothecary_r1/apothecary_anchors.json ("items") and the sketch's NOTES.md.
Run: "C:/Program Files/Blender Foundation/Blender 4.5/blender.exe" -b -P apothecary_r1.py -- [--out DIR] [--no-render] [--quick]

Size 2.0 W x 0.45 D x 2.0 H (Blender x, y, z; -y = front, the back face at y = 0 is the wall, x centred, z = 0 the foot).
Placement.Wall like the emergency shelf: the back sits at the wall. Four tiers of four vessels (16 vessels):
  top     hanging bags on cords from a rail (1.48-1.77 m): two open-weave net bundles on a wooden base, two leather bags cut
          low at the front, so their contents show
  eye     glass jars on the shelf at 1.04 m, open at the front (the frame has one opaque material: the glass is a pale
          tile and the jar's front 124 degrees are left out), a glass rim, a cork in the mouth
  middle  bellied clay crocks on the shelf at 0.58 m, rim at 0.21 so a full heap crowns over it
  floor   wicker baskets with rope handles on the floor board at 0.11 m, rim at 0.20 (the heap crowns over it)
Every vessel has the SAME clear space inside, whatever it looks like outside: an upright cylinder 0.224 wide and 0.245
high on its floor (crate_floor_centres[vessel]). That lets the contents be the Produce Crates' kind (rootbin_r6): one
physics-settled heap per item kind (crop_layouts, keyed by prefab name), which the mod puts into whichever vessel the
kind lands in (Anchors.ParseCrops, StoreContents.Rebuild's crop branch). So each kind is settled with its OWN model:
eyes heap like eyes, needles lie like needles, nothing floats.

Contents: the game's own item models (C:/Users/joost/ValheimRip/items). Per kind: its convex hull dropped as a Blender rigid
body (Bullet; friction 0.6, restitution 0, damping 0.5/0.95, margin 1 mm, substeps 20, iterations 40) into the cylinder
(passive box slabs), one copy at a time at the lowest well-supported spot, settled, checked inside the cylinder, frozen,
until no copy fits or the kind's triangle cap is reached. The drop sequence is then split into 4 equal stacks in order,
so stack k lies on stacks 0..k-1 (a vessel with k stacks of a kind shows stacks 0..k-1 of its layout: it fills up).
Scale per kind (x its true size): long side 0.078 m for round kinds, 0.098 m for long or flat ones, larger for heavy
meshes so their capped copies still fill the vessel (a full store stays under about 250k triangles). '_generic' (any
other item): a neutral lump, scaled by fit_longest_m. units_list (the 64 stacks, 4 per vessel, bin = vessel) carries the
groups; its copies are the _generic heap as Fit.Longest copies (a fallback).

Atlas 128 x 128, point filtered, 48 px per metre. Rows (v from the bottom, px): 96-127 hewn timber, 64-95 end grain,
48-63 dark iron: copied byte-identical from assets/bunker_r4/bunker_atlas.png (the family look). New, painted here in
the same palette logic: 36-47 clay, 24-35 wicker, 16-23 glass, 8-15 leather, 4-7 cord, 0-3 eight 16 px swatches
(cork, ivory, amber, pupil, feather, bright glass, worn timber, soot).
Files (assets/apothecary_r1/): ApothecaryRack.obj (frame, forward -Z up Y like every store), apothecary_atlas.png, and
apothecary_anchors.json written last (temp file + rename). Unity prefab space: ux = -bx, uy = bz, uz = -by.
"""
import bpy, bmesh, sys, os, math, json, random, time, subprocess
import numpy as np
from mathutils import Vector, Matrix, Euler, Quaternion
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, ".."))
OUTA = os.path.join(REPO, "assets", "apothecary_r1")
BUNKER = os.path.join(REPO, "assets", "bunker_r4")
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
def arg(k, d=None): return argv[argv.index(k) + 1] if k in argv else d
OUT = arg("--out", "C:/Users/joost/AppData/Local/Temp/claude/C--Users-joost--pai/5e4bc60b-cdfe-4638-8e29-2e507fa13cf9/scratchpad/apothecary1")
RENDER = "--no-render" not in argv
QUICK = "--quick" in argv
ITEMS_DIR = "C:/Users/joost/ValheimRip/items"
sys.path.append(ITEMS_DIR)
from load_item import load_item
os.makedirs(OUTA, exist_ok=True); os.makedirs(OUT, exist_ok=True)

# the rule's item list (prefab names): creature parts that are not food, meat, bone, hide, ore or a trophy. Entrails,
# blood bag, blood clot and freeze gland stay with the Meat Rack (ItemRules.RawMeat), ooze with Cooper's Row, the antler
# and the bonemaw tooth with the bones.
ITEMS = ["Feathers", "Needle", "GreydwarfEye", "RoyalJelly", "GiantBloodSack", "Ectoplasm", "AskBladder", "WolfFang", "Carapace",
         "WolfHairBundle", "ElakingHairBundle", "Chitin", "CelestialFeather", "MooseSinew", "BjornPaw", "WolfClaw", "MorgenHeart",
         "Bilebag", "SurtlingCore", "MorgenSinew", "DragonTear", "Mandible", "SerpentScale", "BonemawSerpentScale"]
if QUICK: ITEMS = ["Feathers", "Needle", "GreydwarfEye", "RoyalJelly", "Chitin", "DragonTear"]

rng = random.Random(7)
TEX = 128
DENS = 48.0                                   # px per metre (bunker_r4)
STRIP = {"hewn": 0.75, "end": 0.50, "iron": 0.375}
STRIPH = {"hewn": 32, "iron": 16}
ROWS = {"clay": (36, 12), "wicker": (24, 12), "glass": (16, 8), "leather": (8, 8), "rope": (4, 4)}
SWATCH = {"cork": 0, "ivory": 1, "amber": 2, "pupil": 3, "feather": 4, "glassbright": 5, "wear": 6, "soot": 7}

# ---------- atlas: bunker_r4's timber, end grain and iron rows, new materials below ----------
def srgb(c): return np.array(c, dtype=np.float32)
def mix(a, b, t): t = np.clip(t, 0, 1)[..., None]; return a * (1 - t) + b * t

def build_atlas():
    src = bpy.data.images.load(os.path.join(BUNKER, "bunker_atlas.png"))
    img = np.array(src.pixels[:], np.float32).reshape(TEX, TEX, 4)[..., :3].copy()       # row 0 = v 0 (bottom)
    nr = np.random.default_rng(29)
    tile = lambda k: 2 * math.pi * k / TEX
    def grid(h): return (np.arange(TEX)[None, :].repeat(h, 0).astype(np.float32), np.arange(h)[:, None].repeat(TEX, 1).astype(np.float32))
    # clay: wheel rings along the height, low-frequency firing blotches, a dark foot, a light worn rim, grit specks
    x, y = grid(12)
    t = 0.30 + 0.22 * np.sin(y * 2.3 + 0.7 * np.sin(x * tile(3))) * 0.5 + 0.20 * (0.5 + 0.5 * np.sin(x * tile(2) + 1.3)) + nr.random((12, TEX)) * 0.18
    t += (y < 1.5) * 0.45 + (y < 0.5) * 0.2
    c = mix(srgb((0.50, 0.34, 0.24)), srgb((0.24, 0.155, 0.11)), t)
    c = np.where((y > 10.5)[..., None], mix(c, srgb((0.62, 0.48, 0.36)), np.full((12, TEX), 0.6)), c)
    sp = nr.random((12, TEX)) < 0.04; c[sp] = c[sp] * 0.7
    img[36:48] = c
    # wicker: horizontal withies (3 px) woven over upright stakes (every 8 px), dark gaps, lighter crowns
    x, y = grid(12)
    over = (((x // 8).astype(int) + (y // 3).astype(int)) % 2) == 0
    row = y % 3; col = x % 8
    t = np.where(over, np.where(row == 1, 0.15, 0.45), np.where((col >= 3) & (col <= 4), 0.35, 0.6))
    t += ((row == 0) & over) * 0.25 + ((col == 0) & ~over) * 0.35 + nr.random((12, TEX)) * 0.15
    c = mix(srgb((0.56, 0.47, 0.30)), srgb((0.22, 0.165, 0.095)), t)
    hi = over & (row == 1) & (col == 4); c[hi] = mix(c[hi], srgb((0.70, 0.61, 0.42)), np.full(hi.sum(), 0.5))
    img[24:36] = c
    # glass: pale grey-green, upright highlight streaks (two per 32 px), a darker band near the foot, faint bubbles
    x, y = grid(8)
    t = 0.45 + nr.random((8, TEX)) * 0.12 + 0.12 * np.sin(x * tile(5) + 0.4)
    t -= ((x % 32 >= 5) & (x % 32 <= 6)) * 0.45 + ((x % 32) == 19) * 0.3
    t += (y < 1) * 0.25
    c = mix(srgb((0.80, 0.86, 0.82)), srgb((0.46, 0.54, 0.51)), t)
    img[16:24] = c
    # leather: mottled brown, darker creases, a worn light top edge, a stitch line near the bottom
    x, y = grid(8)
    t = 0.40 + 0.25 * np.sin(x * tile(4) + 2 * np.sin(y * 0.9 + x * tile(1))) * 0.5 + nr.random((8, TEX)) * 0.22
    t += ((x * 0.37 + y * 1.7) % 9 < 0.6) * 0.3
    c = mix(srgb((0.42, 0.29, 0.19)), srgb((0.17, 0.11, 0.07)), t)
    c[7] = mix(c[7], srgb((0.55, 0.42, 0.29)), np.full(TEX, 0.5))
    st = (y == 1) & (x % 4 < 2); c[st] = mix(c[st], srgb((0.60, 0.52, 0.38)), np.full(st.sum(), 0.6))
    img[8:16] = c
    # cord: a twisted lay (diagonal strands)
    x, y = grid(4)
    t = ((x + y * 1.5) % 5 < 2.5) * 0.45 + nr.random((4, TEX)) * 0.2 + ((y == 0) | (y == 3)) * 0.2
    img[4:8] = mix(srgb((0.52, 0.44, 0.30)), srgb((0.22, 0.17, 0.10)), t)
    # swatches (16 x 4 px): noise between a base and its dark, never flat
    SW = [((0.55, 0.42, 0.27), (0.30, 0.21, 0.12)), ((0.80, 0.76, 0.64), (0.55, 0.49, 0.38)), ((0.80, 0.62, 0.20), (0.48, 0.32, 0.08)),
          ((0.09, 0.08, 0.07), (0.02, 0.02, 0.02)), ((0.82, 0.81, 0.77), (0.55, 0.55, 0.53)), ((0.88, 0.93, 0.90), (0.66, 0.74, 0.71)),
          ((0.52, 0.43, 0.31), (0.36, 0.29, 0.20)), ((0.13, 0.11, 0.10), (0.06, 0.05, 0.05))]
    for i, (a, b) in enumerate(SW):
        img[0:4, 16 * i:16 * i + 16] = mix(srgb(a), srgb(b), nr.random((4, 16)) * 0.55 + (i == 1) * 0.1)
    im = bpy.data.images.new("apothecary_atlas", TEX, TEX, alpha=False)
    px = np.concatenate([np.clip(img, 0, 1), np.ones((TEX, TEX, 1), np.float32)], 2)
    im.pixels.foreach_set(px.ravel())
    im.filepath_raw = os.path.join(OUTA, "apothecary_atlas.png"); im.file_format = "PNG"; im.save()
    bpy.data.images.remove(src)
    return im

# ---------- geometry helpers (bunker_r4's timber, plus shells of revolution, cords and swatch parts) ----------
PARTS = []
UV = None

def uv_face(f, kind, long_axis, seed):
    """bunker_r4's mapping: cut ends get an end-grain ring tile, long faces the grain / iron strip at 48 px/m."""
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

def plank(name, size, pos, rot=(0, 0, 0), kind="hewn"):
    return timber(name, size, pos, kind=kind, rot=rot, jitter=0.006, bevel=0.008)

def iron(name, size, pos, rot=(0, 0, 0)):
    return timber(name, size, pos, kind="iron", rot=rot, jitter=0.002, bevel=0)

def rivet(pos, face):
    """bunker_r4's rivet: a small square iron head standing 12 mm off a face; face = (axis, sign)"""
    s = [0.03, 0.03, 0.03]; s[face[0]] = 0.012
    p = list(pos); p[face[0]] += face[1] * 0.006
    iron("rivet", s, p)

def shell(name, prof, t, kind, segs=24, arc=None, bottom=True, tb=None, at=(0, 0, 0), rotz=0.0):
    """A vessel wall of revolution: prof = [(r_out, z)] bottom to top, wall t; arc = (a0, a1) radians leaves the rest
    open (end faces close the wall); bottom: a floor tb thick (else an annulus closes the wall foot). Closed solid."""
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
    """a square cord (or iron rod) from p0 to p1, w thick"""
    global UV
    p0, p1 = Vector(p0), Vector(p1); d = p1 - p0; L = d.length
    if kind == "rope":                                    # a three-sided cord (8 triangles), length along x
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
    """a solid cylinder / frustum (jar base, cork)"""
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
W, DEPTH, H = 2.0, 0.45, 2.0
PS = 0.14                                   # front post section
PX = W / 2 - PS / 2                         # 0.93: post centre x
XIN = PX - PS / 2                           # 0.86: inner face of the posts
YF0, YF1 = -DEPTH, -DEPTH + PS              # front posts -0.45 .. -0.31
YB0, YB1 = -0.115, -0.005                   # back posts (0.14 x 0.11) against the wall
YBACK = (-0.045, -0.005)                    # back boards
SHELF_T = 0.05
LEVEL = {"basket": 0.11, "pot": 0.58, "jar": 1.04, "top": 1.46}   # top faces of the floor board and the shelves
TOPB = 1.94                                 # underside of the top board (1.94 .. 2.00)
BAYX = [-0.645, -0.215, 0.215, 0.645]
DIVX = [-0.43, 0.0, 0.43]
VY = -0.24                                  # vessel centre y
POUCH_Z0 = 1.48                             # hanging bag bottom
RAIL = (-0.29, -0.19, 1.84, 1.94)           # rail y0, y1, z0, z1: the hooks hang under it

# the clear space every vessel has inside: an upright cylinder on the vessel's floor
R_C, H_C = 0.112, 0.245
# vessels: outer profile [(r, z)] from the vessel's foot, wall t, floor thickness tb (= where the cylinder stands)
SEG = 16
VESSEL = {
    "basket": dict(prof=[(0.148, 0.0), (0.162, 0.03), (0.174, 0.14), (0.178, 0.178), (0.188, 0.186), (0.188, 0.202)], t=0.014, tb=0.016),
    "pot": dict(prof=[(0.140, 0.0), (0.153, 0.04), (0.158, 0.10), (0.151, 0.16), (0.142, 0.19), (0.150, 0.212)], t=0.016, tb=0.018),
    "jar": dict(prof=[(0.125, 0.0), (0.130, 0.02), (0.130, 0.262), (0.121, 0.285)], t=0.008, tb=0.022),
    "pouch": dict(prof=[(0.128, 0.0), (0.130, 0.02), (0.132, 0.16), (0.128, 0.25), (0.124, 0.29)], t=0.008, tb=0.020),
}
TIER = [("pouch", "top"), ("jar", "jar"), ("pot", "pot"), ("basket", "basket")]      # listed top to bottom
CV = dict(rs=np.array([R_C, R_C]), zs=np.array([0.0, H_C]), zmax=H_C, floor=0.0)

def in_cyl(P, eps=0.0015):
    return (P[:, 2] >= min(eps, 0.0) - 0.0002) & (P[:, 2] <= H_C - eps) & (np.hypot(P[:, 0], P[:, 1]) <= R_C - eps)

def outside_cyl(P):
    return float(np.max(np.maximum.reduce([-P[:, 2], P[:, 2] - H_C, np.hypot(P[:, 0], P[:, 1]) - R_C])))

def vessel_origin(vt, b):
    lev = dict(TIER)[vt]
    return Vector((BAYX[b], VY, POUCH_Z0 if vt == "pouch" else LEVEL[lev]))

def floor_centre(vt, b):
    return vessel_origin(vt, b) + Vector((0, 0, VESSEL[vt]["tb"]))

def build_frame():
    j = lambda a: rng.uniform(-a, a)
    # posts: front 0.14 x 0.14, back 0.14 x 0.11 against the wall, up to the top board
    for sx in (-1, 1):
        timber("post", (PS, PS, TOPB), (sx * PX, (YF0 + YF1) / 2, TOPB / 2), rot=(j(0.3), j(0.3), 0), jitter=0.012, bevel=0.02)
        timber("post", (PS, YB1 - YB0, TOPB), (sx * PX, (YB0 + YB1) / 2, TOPB / 2), jitter=0.008, bevel=0.018)
    plank("top", (W + 0.02, DEPTH + 0.02, 0.06), (0, -DEPTH / 2 + 0.005, TOPB + 0.03), rot=(0, 0, j(0.2)))
    # back boards (vertical, 0.04 thick), from the floor board to the top board
    xs = np.linspace(-XIN, XIN, 8)
    for a, b in zip(xs[:-1], xs[1:]):
        plank("back", (b - a + 0.012, YBACK[1] - YBACK[0], TOPB - 0.06), ((a + b) / 2, sum(YBACK) / 2, 0.06 + (TOPB - 0.06) / 2), rot=(0, j(0.3), 0))
    # sills, floor board, shelves; side boards carry them between the posts
    for y in (-0.40, -0.12):
        timber("sill", (2 * XIN + 0.02, 0.10, 0.06), (0, y, 0.03), jitter=0.006, bevel=0.012)
    for nm, top in LEVEL.items():
        plank("shelf", (2 * XIN + 0.04, DEPTH + YBACK[0], SHELF_T), (0, (-DEPTH + YBACK[0]) / 2, top - SHELF_T / 2), rot=(0, 0, j(0.2)))
        for sx in (-1, 1):
            plank("side", (0.06, YB0 - YF1 + 0.06, 0.14), (sx * PX, (YF1 + YB0) / 2, max(top - 0.07, 0.07)), kind="hewn")
    for sx in (-1, 1):                                                   # the rail's side boards and a high side board
        plank("side", (0.06, YB0 - YF1 + 0.06, 0.14), (sx * PX, (YF1 + YB0) / 2, TOPB - 0.07))
    # header beam on the front (carries the plaque), the rail for the hanging vessels
    timber("header", (W, 0.12, 0.12), (0, YF0 + 0.06, TOPB - 0.06), rot=(0, 0, j(0.15)), jitter=0.01, bevel=0.018)
    timber("rail", (2 * XIN + 0.08, RAIL[1] - RAIL[0], RAIL[3] - RAIL[2]), (0, (RAIL[0] + RAIL[1]) / 2, (RAIL[2] + RAIL[3]) / 2), jitter=0.008, bevel=0.015)
    # dividers between the bays on the crock and jar tiers
    for lo, hi in ((LEVEL["pot"], LEVEL["jar"] - SHELF_T), (LEVEL["jar"], LEVEL["top"] - SHELF_T)):
        for x in DIVX:
            plank("divider", (0.04, -0.047 + 0.42, hi - lo), (x + j(0.003), (-0.42 - 0.047) / 2, (lo + hi) / 2))
    # iron: a riveted bracket on every front post where a shelf or the header meets it, bands round the post feet
    for sx in (-1, 1):
        for top in list(LEVEL.values()) + [TOPB - 0.06]:
            zc = top - 0.025
            iron("bracket", (0.11, 0.008, 0.17), (sx * PX, YF0 - 0.004, zc))
            for dz in (-0.05, 0.05): rivet((sx * PX, YF0 - 0.008, zc + dz), (1, -1))
            iron("strap", (0.16, 0.008, 0.045), (sx * (XIN - 0.07), YF0 - 0.002, top - SHELF_T / 2 if top != TOPB - 0.06 else top - 0.03))
            rivet((sx * (XIN - 0.11), YF0 - 0.006, top - SHELF_T / 2 if top != TOPB - 0.06 else top - 0.03), (1, -1))
        iron("band", (PS + 0.016, PS + 0.016, 0.05), (sx * PX, (YF0 + YF1) / 2, 0.06))
    # hooks under the rail, one per hanging vessel
    for x in BAYX:
        cord("hook", (x, VY, RAIL[2] + 0.005), (x, VY, RAIL[2] - 0.05), 0.016, "iron")
        cord("hook", (x, VY, RAIL[2] - 0.05), (x, VY - 0.03, RAIL[2] - 0.05), 0.014, "iron")
        iron("hookplate", (0.06, 0.06, 0.01), (x, VY, RAIL[2] - 0.004))
    build_plaque()
    build_vessels()

def build_plaque():
    """the rule on the header: a board with a fang, an eye and a feather in relief, riveted at its corners"""
    global UV
    yb = YF0 - 0.035
    plank("plaque", (0.62, 0.035, 0.105), (0, YF0 - 0.0175, TOPB - 0.06))
    for dx in (-0.28, 0.28):
        for dz in (-0.033, 0.033): rivet((dx, yb, TOPB - 0.06 + dz), (1, -1))
    zc = TOPB - 0.06; yf = yb - 0.004
    # fang: a curved six-sided tusk, ivory
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
    # eye: an amber dome with an upright slit pupil
    bm = bmesh.new(); UV = bm.loops.layers.uv.verify()
    bmesh.ops.create_uvsphere(bm, u_segments=10, v_segments=6, radius=0.032)
    for v in bm.verts: v.co.y *= 0.6
    for f in bm.faces: sw_uv(f, "amber")
    bmesh.ops.translate(bm, verts=bm.verts, vec=Vector((0, yf + 0.004, zc)))
    link(bm, "eye")
    timber("pupil", (0.009, 0.006, 0.040), (0, yf - 0.016, zc), kind="pupil", jitter=0, bevel=0)
    for dz in (-1, 1):                                            # lids
        cord("lid", (-0.04, yf - 0.004, zc + dz * 0.012), (0, yf - 0.012, zc + dz * 0.036), 0.009, "soot")
        cord("lid", (0, yf - 0.012, zc + dz * 0.036), (0.04, yf - 0.004, zc + dz * 0.012), 0.009, "soot")
    # feather: a flat vane (lens outline) with an ivory quill, leaning
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

POUCH_STYLE = ["net", "leather", "net", "leather"]
def build_vessels():
    for vt, _ in TIER:
        v = VESSEL[vt]
        for b in range(4):
            o = vessel_origin(vt, b); rz = rng.uniform(0, 2 * math.pi)
            if vt == "basket":
                shell("basket", v["prof"], v["t"], "wicker", SEG, bottom=True, tb=v["tb"], at=o, rotz=rz)
                for a in (0, math.pi):                                  # two rope handles
                    p = [o + Vector(((0.184) * math.cos(rz + a + d), 0.184 * math.sin(rz + a + d), 0.19 + h)) for d, h in ((-0.18, 0), (-0.1, 0.035), (0.1, 0.035), (0.18, 0))]
                    for q0, q1 in zip(p[:-1], p[1:]): cord("handle", q0 + Vector((0, 0, 0.004)), q1 + Vector((0, 0, 0.004)), 0.014, "rope")
            elif vt == "pot":
                shell("pot", v["prof"], v["t"], "clay", SEG, bottom=True, tb=v["tb"], at=o, rotz=rz)
                ring("potcord", 0.150, 0.172, 0.011, o, "rope", 10, rz)
            elif vt == "jar":
                half = math.radians(62); front = -math.pi / 2
                shell("jar", v["prof"], v["t"], "glass", SEG, arc=(front + half, front - half + 2 * math.pi), bottom=False, at=o)
                disc("jarbase", 0.129, 0.129, 0.0, 0.022, "glass", o, SEG)
                shell("jarrim", [(0.126, 0.282), (0.127, 0.300)], 0.012, "glassbright", 12, bottom=False, at=o)
                disc("cork", 0.106, 0.097, 0.288, 0.336, "cork", o, 12)
            else:
                style = POUCH_STYLE[b]
                prof = v["prof"]
                if style == "leather":                                  # a leather bag, its front cut away above 0.10
                    lo = [p for p in prof if p[1] < 0.10] + [(0.1311, 0.10)]
                    shell("bag", lo, v["t"], "leather", SEG, bottom=True, tb=v["tb"], at=o, rotz=0.0)
                    hi = [(0.1311, 0.10)] + [p for p in prof if p[1] > 0.10]
                    half = math.radians(70); front = -math.pi / 2
                    shell("bag", hi, v["t"], "leather", SEG, arc=(front + half, front - half + 2 * math.pi), bottom=False, at=o)
                else:                                                   # an open net on a wooden base
                    disc("netbase", 0.126, 0.128, 0.0, v["tb"], "hewn", o, 12)
                    nm = 6
                    for k in range(nm):                                 # upright cords, then rings
                        a = rz + 2 * math.pi * k / nm
                        pts = [o + Vector(((r - 0.004) * math.cos(a), (r - 0.004) * math.sin(a), max(z, 0.01))) for r, z in prof]
                        for q0, q1 in zip(pts[:-1], pts[1:]): cord("net", q0, q1, 0.008)
                    for zz in (0.08, 0.16, 0.235):
                        rr = float(np.interp(zz, [p[1] for p in prof], [p[0] for p in prof])) - 0.004
                        ring("net", rr, zz, 0.008, o, "rope", 9, rz + math.pi / 9)
                ring("collar", 0.126, 0.285, 0.016, o, "rope", 10, rz)
                hook = Vector((o.x, VY - 0.03, RAIL[2] - 0.056))
                for a in (math.radians(90), math.radians(210), math.radians(330)):
                    cord("hang", o + Vector((0.124 * math.cos(a), 0.124 * math.sin(a), 0.29)), hook, 0.008)

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

if "--frame-only" in argv:
    rng.seed(7); build_frame(); _by = {}
    for o in PARTS: k = o.name.split(".")[0]; _by[k] = _by.get(k, 0) + tris([o])
    print("APO frame tris", tris(PARTS), sorted(_by.items(), key=lambda x: -x[1]), flush=True); sys.exit(0)

# ---------- item templates: the visible mesh (centred on its bounds) and its convex hull ----------
def Rz(a): return Euler((0, 0, math.radians(a))).to_matrix()
def Rx(a): return Euler((math.radians(a), 0, 0)).to_matrix()
def Ry(a): return Euler((0, math.radians(a), 0)).to_matrix()

def lump_mesh():
    """the generic fallback (any item not in ITEMS): a neutral round lump, 0.12 m (rootbin_r6's)"""
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
TRI_BUDGET = 240000 - 10000                 # item triangles in a full store (16 vessels) of the heaviest kind
FILL_PACK = 0.30                            # the hull volume share of a filled vessel (sets the scale of capped kinds)
TPL = {}
def tpl(name):
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
    # convex hull (planes outward, faces for the proxy and BVH)
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
    mode = "lie" if ss[2] / ss[0] < 0.32 and ss[1] / ss[0] >= 0.45 else "tumble"     # flat kinds lie; rods and round ones tumble
    # scale: a round kind's long side 0.078 m, a long or flat one's 0.098 m; a heavy mesh's capped copies still fill the vessel
    cap = int(max(8, min(200, TRI_BUDGET // (16 * max(ntri, 1)))))
    Lb = 0.078 if ss[1] / ss[0] >= 0.75 and mode == "tumble" else 0.098
    s_fill = (FILL_PACK * V_CYL / (cap * vol)) ** (1 / 3)
    s = max(Lb / ss[0], s_fill) if name != "_generic" else Lb / ss[0]
    s = min(s, (0.14 if ss[1] / ss[0] < 0.45 else 0.10) / ss[0])      # rods (needles, sinew) up to 14 cm, others 10 cm
    pm = bpy.data.meshes.new("prox_" + name)
    pm.from_pydata([tuple(v * s) for v in hv], [], [tuple(int(i) for i in f) for f in F]); pm.update()
    TPL[name] = dict(datas=datas, verts=verts, size=size, A=A, tris=ntri, hv=hv, F=F, N=np.array(N), D=np.array(D), vol=vol,
                     mode=mode, cap=cap, s=s, prox=pm)
    return TPL[name]

# ---------- the settle (rootbin_r6's method, one cylinder per kind side by side) ----------
CELL = 0.005
class HF:
    def __init__(self):
        self.n = 54; self.x0 = -0.135
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
        if dilate:                                   # its edges between cell centres: one cell around it at its height
            zp = np.pad(zt, 1, constant_values=-9.0)
            zt = np.max([zp[1 + di:1 + di + self.n, 1 + dj:1 + dj + self.n] for di in (-1, 0, 1) for dj in (-1, 0, 1)], axis=0)
        self.h = np.maximum(self.h, zt)
    def level(self): return float(self.h[self.mask].mean())

def drop_z(hf, h, N, D, lo, hi, x, y):
    """the lowest centre height at (x, y) where the turned hull (planes N, D about its centre; vertex bounds lo, hi) rests on
    the heightfield h, the cells it covers, and the share of its footprint it rests on (within 6 mm)"""
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

GRID = 0.012
GXY = [(x, y) for x in np.arange(-R_C, R_C + 1e-9, GRID) for y in np.arange(-R_C, R_C + 1e-9, GRID) if math.hypot(x, y) <= R_C - 0.008]
def lowest_spot(st, h, rr):
    """every spot of a 1.2 cm grid at 8 orientations: where would the copy rest, does it fit the cylinder there; one of the
    three lowest well-supported resting places (lowest first, then towards the wall), at random"""
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
    """the cylinder as passive BOX slabs (Bullet's box contacts are clean): a floor block COL_IN over the floor and 32 wall
    slabs whose inner faces lie COL_IN inside R_C, 8 cm over the top"""
    out = [(Matrix.Translation((ox, 0, -0.05)), (0.6, 0.6, 0.1))]          # the floor: the vessel's own floor (z = 0)
    n = 32; ri = R_C - COL_IN; T = 0.03; w = 2 * ri * math.tan(math.pi / n) * 1.08; Hh = H_C + 0.08
    for i in range(n):
        a = 2 * math.pi * (i + 0.5) / n
        M = Matrix.Rotation(a, 4, "Z"); M.translation = Vector((ox + (ri + T / 2) * math.cos(a), (ri + T / 2) * math.sin(a), Hh / 2))
        out.append((M, (T, w, Hh)))
    return out

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
                tmp[max(0, i0 - 3):i1 + 4, max(0, j0 - 3):j1 + 4] = H_C + 1          # the next copy of this drop goes elsewhere
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
                s["done"] = True; n = len(s["frozen"])
                cut = [round(n * k / 4) for k in range(5)]
                for b in s["frozen"]: b["stack"] = max(k for k in range(4) if b["id"] >= cut[k])
                print("APO %-20s full: %2d copies (cap %d), scale %.3f, level %.3f, top %.3f, stacks %s" % (name, n, s["t"]["cap"], s["t"]["s"], s["hfl"].level(),
                      max(float(b["HV"][:, 2].max()) for b in s["frozen"]) if n else 0, [cut[k + 1] - cut[k] for k in range(4)]), flush=True)
    for o in [o for o in bpy.data.objects if o.rigid_body is not None]: bpy.data.objects.remove(o)
    bpy.ops.rigidbody.world_remove()
    sc.frame_set(1)
    return ST, stats

KINDS = ITEMS + ["_generic"]
ST, SIMST = settle(KINDS)
print("APO SIM", SIMST, "%.0fs" % (time.time() - t0), flush=True)

# ---------- checks on the settled heaps ----------
def hull_bvh(b, t):
    return BVHTree.FromPolygons([Vector(v) for v in b["HV"]], [tuple(int(i) for i in f) for f in t["F"]])
def float_pen(name):
    """per copy: the gap to its nearest support frozen before it (the floor, the wall, or a copy of the same kind touching it
    from below), and the deepest overlap of two copies"""
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
    for k in range(4):
        for b in fr:
            if b["stack"] == k: hf.add(b["N"], b["D"], dilate=False)
        lv.append(round(hf.level(), 3))
    CHECK[name] = dict(copies=len(fr), copies_by_stack=[sum(1 for b in fr if b["stack"] == k) for k in range(4)], cap=t["cap"],
                       mesh_outside_cylinder_mm=round(outside_cyl(P) * 1000, 1), float_worst_mm=round(fmax * 1000, 2),
                       overlap_max_mm=round(pen * 1000, 2), level_by_stacks_m=lv, top_m=round(float(P[:, 2].max()), 3),
                       longest_m=round(float(t["size"].max() * t["s"]), 3), drawn_tris_per_copy=t["tris"], tris_full_vessel=len(fr) * t["tris"])
    print("APO CHECK %-20s %s" % (name, CHECK[name]), flush=True)

# ---------- frame and its clipping check against the 16 cylinders ----------
rng.seed(7); PARTS.clear(); build_frame()
FRAME_TRIS = tris(PARTS)
print("APO frame tris", FRAME_TRIS, "parts", len(PARTS), flush=True)
VESSELS = [(vt, b) for vt, _ in TIER for b in range(4)]     # bin = index: hanging 0-3, jars 4-7, crocks 8-11, baskets 12-15
FLOORS = [np.array(floor_centre(vt, b)) for vt, b in VESSELS]
# (a) no frame vertex inside any cylinder
FV = np.vstack([np.array([o.matrix_world @ v.co for v in o.data.vertices]) for o in PARTS])
frame_in = 0
for fc in FLOORS:
    Q = FV - fc; hit = in_cyl(Q, 0.001) & (Q[:, 2] > 0.001); frame_in += int(hit.sum())
    if hit.any(): print("APO frame vertex in cylinder", np.round(FV[hit][:3], 3).tolist(), flush=True)
# (b) no cylinder point (surface every 1 cm, interior grid 2 cm) inside a frame part
PB = []
for o in PARTS:
    vs = [v.co.copy() for v in o.data.vertices]; a = np.array([v[:] for v in vs])
    PB.append((a.min(0), a.max(0), BVHTree.FromPolygons(vs, [tuple(p.vertices) for p in o.data.polygons]), o.name))
PLO = np.array([p[0] for p in PB]); PHI = np.array([p[1] for p in PB])
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
cs = []
RS, Z0, Z1 = R_C - 0.001, 0.001, H_C - 0.001             # 1 mm inside: the floor itself is the vessel's
for z in np.arange(Z0, Z1 + 1e-9, 0.01):
    for a in np.arange(0, 2 * math.pi, 0.01 / R_C): cs.append((RS * math.cos(a), RS * math.sin(a), z))
for x in np.arange(-RS, RS + 1e-9, 0.02):
    for y in np.arange(-RS, RS + 1e-9, 0.02):
        if math.hypot(x, y) <= RS:
            for z in (Z0, Z1) + tuple(np.arange(0.02, H_C, 0.04)): cs.append((x, y, z))
CS = np.array(cs); cyl_in = 0; cyl_notes = []
for (vt, b), fc in zip(VESSELS, FLOORS):
    for q in CS + fc:
        for c in np.where(((q >= PLO - 1e-4) & (q <= PHI + 1e-4)).all(1))[0]:
            if inside_part(PB[c][2], q): cyl_in += 1; cyl_notes.append((vt, b, PB[c][3])); break
print("APO FRAME vs cylinders: frame vertices inside %d, cylinder points (%d per vessel, 1 mm inset) inside a frame part %d %s" % (frame_in, len(CS), cyl_in, cyl_notes[:4]), flush=True)

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
    stacks = [[{"offset": uvec(b["c"]), "rot_quat_xyzw": uquat(b["R"])} for b in s["frozen"] if b["stack"] == k] for k in range(4)]
    for b in s["frozen"]:
        qx, qy, qz, qw = uquat(b["R"]); Rb = MC.transposed() @ Quaternion((qw, qx, qy, qz)).to_matrix() @ MC
        rt = max(rt, float(np.abs(np.array(Rb) - b["R"]).max()))
    sz = t["size"]
    ent = {"scale": round(t["s"], 5), "true_size_m": [round(float(sz[0]), 4), round(float(sz[2]), 4), round(float(sz[1]), 4)], "mode": t["mode"],
           "copies_per_stack": round(len(s["frozen"]) / 4, 2), "copies_by_stack": [len(x) for x in stacks], "stacks": stacks, "check": CHECK[name]}
    if name == "_generic":
        ent["scale"] = None; ent["fit_longest_m"] = round(float(sz.max() * t["s"]), 4); ent["true_size_m"] = None
        ent["note"] = "fallback for any item without its own layout: settled with a neutral round lump; scale the item uniformly so its longest bounds side is fit_longest_m."
    layouts[name] = ent
GEN = layouts["_generic"]
KIND = {"pouch": "hanging", "jar": "jar", "pot": "crock", "basket": "basket"}
units = []
for bi, (vt, b) in enumerate(VESSELS):
    fc = FLOORS[bi]; cen = fc + np.array((0, 0, H_C / 2))
    for k in range(4):
        units.append({"index": len(units), "bin": bi, "vessel": KIND[vt] + ("_" + POUCH_STYLE[b] if vt == "pouch" else ""), "kind": KIND[vt],
                      "tier": [t for t, _ in TIER].index(vt), "bay": b, "fill_step": k, "position": uvec(cen), "rotation": [0, 0, 0],
                      "box": [round(2 * R_C, 4), round(H_C, 4), round(2 * R_C, 4)],
                      "copies": [{"offset": [round(c["offset"][0], 4), round(c["offset"][1] - H_C / 2, 4), round(c["offset"][2], 4)],
                                  "rot_quat_xyzw": c["rot_quat_xyzw"], "fit_longest_m": GEN["fit_longest_m"]} for c in GEN["stacks"][k]]})
worst = max(ITEMS, key=lambda n: CHECK[n]["tris_full_vessel"])
doc = {
    "store": "Apothecary Rack round 1 (blender/apothecary_r1.py)",
    "rule": "small things a creature leaves behind that you can't eat or wear",
    "items": ITEMS,
    "slots": 64, "grid": [8, 8], "stack_per_unit": 1, "placement": "wall",
    "frame": {"obj": "ApothecaryRack.obj", "tris": FRAME_TRIS, "size_m": [W, H, DEPTH], "atlas": "apothecary_atlas.png 128x128 point",
              "atlas_rows": "v px from the bottom: 96-127 hewn, 64-95 end grain, 48-63 iron (byte-identical from bunker_r4), 36-47 clay, 24-35 wicker, 16-23 glass, 8-15 leather, 4-7 cord, 0-3 swatches cork/ivory/amber/pupil/feather/bright glass/worn timber/soot"},
    "space": "Unity prefab space, metres. Origin: the wall plane (back face, z = 0), x centred, y = 0 the foot; front is +z. Blender z-up/-y front -> Unity: ux=-bx, uy=bz, uz=-by. OBJ exported forward -Z, up Y (the mod loads it flipX).",
    "groups": "bin 0..15 = one vessel each (one item kind per vessel): 0-3 hanging (net, leather, net, leather), 4-7 glass jars, 8-11 clay crocks, 12-15 wicker baskets; within a tier Blender x ascending (Unity x descending). Every vessel's clear space is the same upright cylinder (radius %.3f, height %.3f) standing on crate_floor_centres[bin]." % (R_C, H_C),
    "crate_floor_centres": [uvec(fc) for fc in FLOORS],
    "crop_layouts": layouts,
    "crop_layouts_doc": ("crop_layouts: one physics-settled full vessel per item kind (prefab name; '_generic' for any other item), as the Produce Crates "
                         "(rootbin_r6). A vessel holding n stacks of a kind shows stacks[0..n-1] of that kind's layout (all of a stack's copies); stack k was "
                         "dropped onto stacks 0..k-1 after they were frozen. Per copy: the item's model in the mod's item space (ItemVisual), scaled uniformly by "
                         "'scale' (x its true size), turned by rot_quat_xyzw about its bounds centre, that centre at crate_floor_centres[bin] + offset. The heaps "
                         "were settled in one cylinder and fit every vessel (checked against the frame in all 16)."),
    "unit_semantics": "units_list: one unit = one stack, 4 per vessel in fill order, bin = the vessel; copies = the _generic heap's stack as Fit.Longest copies (centre at position + offset), a fallback only.",
    "physics": ("Blender rigid body (Bullet): each copy the convex hull of its item, friction 0.6, restitution 0, damping 0.5/0.95, margin 1 mm, substeps 20, "
                "iterations 40, in the cylinder made of passive box slabs; one copy per kind per drop at one of the three lowest well-supported spots of a "
                "1.2 cm grid x 8 orientations (lying for flat and long kinds, any for the others), settled, checked inside the cylinder, then frozen; until no "
                "copy fits or the kind's cap (a full store of it under ~%d item triangles); the sequence split into 4 equal stacks." % TRI_BUDGET),
    "checks": {"frame_vertices_inside_cylinders": frame_in, "cylinder_points_inside_frame_parts": cyl_in, "cylinder_points_per_vessel": len(CS),
               "rotation_roundtrip_max_err": rt, "sim": SIMST},
    "tris_full_store_worst_kind": {"item": worst, "tris": 16 * CHECK[worst]["tris_full_vessel"] + FRAME_TRIS},
    "units_list": units,
}
if not QUICK:
    bpy.ops.object.select_all(action="DESELECT")
    for o in PARTS: o.select_set(True)
    bpy.context.view_layer.objects.active = PARTS[0]
    bpy.ops.wm.obj_export(filepath=os.path.join(OUTA, "ApothecaryRack.obj"), export_selected_objects=True, export_materials=False,
                          export_triangulated_mesh=True, forward_axis="NEGATIVE_Z", up_axis="Y")
    out = os.path.join(OUTA, "apothecary_anchors.json"); tmp = out + ".tmp"
    with open(tmp, "w") as fh: json.dump(doc, fh, indent=1)
    os.replace(tmp, out)
    print("APO wrote", out, flush=True)
print("APO STATS frame tris %d, copies %d, worst full store %s, roundtrip %.2g" % (FRAME_TRIS, sum(c["copies"] for c in CHECK.values()), doc["tris_full_store_worst_kind"], rt), flush=True)

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
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0.3, 1.5)); wall = bpy.context.active_object; wall.scale = (14, 0.6, 3.0)
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
    shown = []
    def fill(assign, nstacks=4):
        for bi in range(16):
            name = assign[bi % len(assign)]
            if name not in ST: continue
            t = ST[name]["t"]
            for b in ST[name]["frozen"]:
                if b["stack"] >= nstacks: continue
                M = np.eye(4); M[:3, :3] = b["R"] * t["s"]; M[:3, 3] = b["c"] + FLOORS[bi]
                for dta in t["datas"]:
                    io = bpy.data.objects.new(name, dta); sc.collection.objects.link(io); io.matrix_world = Matrix(M.tolist()); shown.append(io)
    def clear():
        for o in shown: bpy.data.objects.remove(o)
        shown.clear()
    def render(fn, rx=1600, ry=1000):
        sc.render.resolution_x, sc.render.resolution_y = rx, ry
        sc.render.filepath = os.path.join(OUT, fn); bpy.ops.render.render(write_still=True); return sc.render.filepath
    A = ["Feathers", "WolfHairBundle", "CelestialFeather", "MorgenSinew",
         "GreydwarfEye", "RoyalJelly", "Ectoplasm", "GiantBloodSack",
         "Needle", "WolfFang", "SurtlingCore", "WolfClaw",
         "Carapace", "Chitin", "Bilebag", "AskBladder"]
    B = ["ElakingHairBundle", "MooseSinew", "DragonTear", "Mandible",
         "MorgenHeart", "SerpentScale", "BjornPaw", "BonemawSerpentScale",
         "Feathers", "GreydwarfEye", "RoyalJelly", "Chitin",
         "Needle", "MorgenSinew", "SurtlingCore", "_generic"]
    if QUICK: A = B = ITEMS
    V34 = (-28, 8, 4.6, (0, -0.2, 1.0))
    look(*V34); render("apothecary1-empty.png")
    fill(A, 2); render("apothecary1-50.png"); clear()
    fill(A, 4); render("apothecary1-full.png")
    look(-14, 14, 1.35, (0.0, -0.24, 1.22)); render("apothecary1-closeup-jars.png")
    look(-10, 30, 1.5, (0.0, -0.24, 0.55)); render("apothecary1-closeup-crocks-baskets.png")
    look(-6, 2, 1.4, (0.0, -0.24, 1.62)); render("apothecary1-closeup-hanging.png")
    bpy.ops.mesh.primitive_cube_add(size=1, location=(1.45, -0.3, 0.9)); post = bpy.context.active_object; post.scale = (0.1, 0.1, 1.8)
    pm = bpy.data.materials.new("post"); pm.use_nodes = True
    pm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.85, 0.85, 0.88, 1); post.data.materials.append(pm)
    look(-8, 5, 4.6, (0.3, -0.2, 1.0)); render("apothecary1-post-1.8m.png")
    bpy.data.objects.remove(post)
    clear(); fill(B, 4); look(*V34); render("apothecary1-full-mixB.png")
    look(-14, 14, 1.35, (0.0, -0.24, 1.22)); render("apothecary1-closeup-jars-mixB.png"); clear()
    # beside bunker_r4 at the same scale (its OBJ + atlas, as shipped)
    fill(A, 4)
    before = set(bpy.data.objects)
    bpy.ops.wm.obj_import(filepath=os.path.join(BUNKER, "Bunker.obj"), forward_axis="NEGATIVE_Z", up_axis="Y")
    bk = [o for o in bpy.data.objects if o not in before]
    bmat = bpy.data.materials.new("bunker"); bmat.use_nodes = True
    bt = bmat.node_tree.nodes.new("ShaderNodeTexImage"); bt.image = bpy.data.images.load(os.path.join(BUNKER, "bunker_atlas.png")); bt.interpolation = "Closest"
    bmat.node_tree.links.new(bt.outputs["Color"], bmat.node_tree.nodes["Principled BSDF"].inputs["Base Color"])
    bmat.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.8
    for o in bk:
        o.data.materials.clear(); o.data.materials.append(bmat); o.location = (3.4, -1.12, 0)
    look(-14, 9, 9.0, (2.2, -0.6, 0.95)); render("apothecary1-beside-bunker_r4.png", 1800, 900)
print("DONE %.0fs" % (time.time() - t0))

