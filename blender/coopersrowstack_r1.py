"""Cooper's Row, stackable, round 1 (Joost, 24 Oct: "Cooper's Row is something you would expect to be stackable"): the round 5 store in a
timber frame, so a second copy can stand on the first. A sketch to look at, not wired into the mod.
- Kept exactly from coopersrow_r5: the six vessels (shapes, places, sight slots, gauges, hoops), the 64 units with their settled Resin
  lumps (copied verbatim from assets/coopersrow_r5/coopersrow_anchors.json, not re-simulated), the 30 liquid columns, the six labels, the
  atlas. The skid (4.12 x 1.24 m, deck top 0.15 m) is the bottom deck as before.
- New frame: SIX uprights, 0.15 m square, foot on the ground, head under the ring: four corners and one pair (front and back) in the gap
  between the Sap and the Guck vessel, which is also where no label stands; a top ring of heavy front and back beams and five cross
  beams (0.12 high); a closed plank deck on it (0.05); the pouring room = CLEAR (0.35 m) above the tallest rim (Tar and Eitr 0.95 m);
  knee braces under the ring along the front, back and across at every post; iron T brackets at every post head, a strap round every
  post foot, end plates on the corners, r5's straps over the deck ends.
- Stacking (as bunker_r4): the bottom frame (two sills the length of the store, five sleepers) matches the top ring in footprint, a second
  copy's origin goes up by the module height (stack.module_height_m): its sills rest on the lower deck, its posts stand over the lower posts.
Run: blender -b -P coopersrowstack_r1.py -- [--out DIR] [--assets DIR] [--quick] [--no-render] [--views a,b]
Files: assets/coopersrowstack_r1/{CoopersRow.obj, Liquid_<c>_<Item>.obj x 30, coopersrow_atlas.png, coopersrow_anchors.json} (json last).
Renders (default: the scratchpad coopersrowstack folder): lineup (bunker_r4 | r5 | stackable, 70 % and bare), stacked pair, filled.
"""
import bpy, bmesh, sys, os, math, json, random, time
import numpy as np
from mathutils import Vector, Matrix, Euler, Quaternion
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, ".."))
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
def arg(k, d=None): return argv[argv.index(k) + 1] if k in argv else d
SCR = "C:/Users/joost/AppData/Local/Temp/claude/C--Users-joost--pai/5e4bc60b-cdfe-4638-8e29-2e507fa13cf9/scratchpad/coopersrowstack"
OUTA = arg("--assets", os.path.join(REPO, "assets", "coopersrowstack_r1"))
OUT = arg("--out", SCR)
QUICK = "--quick" in argv
NORENDER = "--no-render" in argv
VIEWSEL = arg("--views").split(",") if "--views" in argv else None
R5DIR = os.path.join(REPO, "assets", "coopersrow_r5")   # round 5: contents (units) are reused verbatim from here
ITEMS_DIR = "C:/Users/joost/ValheimRip/items"
sys.path.append(ITEMS_DIR)
from load_item import load_item
os.makedirs(OUTA, exist_ok=True); os.makedirs(OUT, exist_ok=True)
rng = random.Random(17)        # frame

TEX, DENS = 128, 48.0
FPS = 24
MARGIN = 0.003
# longest side of the lumps per item (m), in the family range (ore bin ~0.33): the kinds with many units a little smaller so
# every unit still gets at least one copy (Resin 16 units, Sap 9, Eitr 10 in their vessels)
LONGS = {"Tar": 0.26, "Resin": 0.25, "Sap": 0.22, "Guck": 0.26, "Eitr": 0.25, "Ooze": 0.25}
WALLGAP = 0.012                # collider inside the inner wall
EDGE, CROWN, CAPOVER = 0.04, 0.85, 0.18
COVER_TOL = 0.06
LIQUID = ["Sap", "Tar", "Guck", "Ooze", "Eitr"]   # drawn as liquid columns by the mod in any vessel
LUMP = "Resin"                 # the solid fallback every vessel's units carry
ITEMS6 = ["Tar", "Resin", "Sap", "Guck", "Eitr", "Ooze"]
LABEL_LONG, LABEL_YAW, LABEL_R = 0.22, 18.0, 0.15   # the label copy: longest side, turn, the radius any of the six needs on the deck
LIQ_INSET, LIQ_FLOOR, LIQ_FREEBOARD = 0.005, 0.003, 0.07   # inside the staves, over the inner floor, under the rim when full
GRID = 0.03

# ---------- layout (Blender metres, z up, -y = front) ----------
SLEEPER_H, PLANK_T = 0.10, 0.05
DECK = SLEEPER_H + PLANK_T     # 0.15: deck top, vessel bottoms
FLREL = 0.06                   # inner floor over the vessel bottom
FL = DECK + FLREL
D = 1.24                       # skid depth (round 5: room for the labels in front)
# item, kind, rim height (world), outer profile shape [(r, z/h)] (round 1's), units, widest outer radius (the shape is scaled to it)
_V = [
    ("Tar",   "barrel", 0.95, [(0.225, 0), (0.25, 0.12), (0.27, 0.5), (0.25, 0.88), (0.23, 1.0)], 10, 0.30),
    ("Resin", "clay",   0.88, [(0.19, 0), (0.26, 0.15), (0.30, 0.45), (0.285, 0.72), (0.25, 0.88), (0.272, 0.93), (0.272, 1.0)], 16, 0.36),
    ("Sap",   "bark",   0.90, [(0.24, 0), (0.255, 0.5), (0.27, 1.0)], 9, 0.28),       # round 2's tub
    ("Guck",  "half",   0.84, [(0.25, 0), (0.27, 0.3), (0.285, 0.7), (0.29, 1.0)], 10, 0.31),
    ("Eitr",  "cask",   0.95, [(0.20, 0), (0.235, 0.14), (0.25, 0.5), (0.235, 0.86), (0.205, 1.0)], 10, 0.30),
    ("Ooze",  "dclay",  0.84, [(0.17, 0), (0.23, 0.15), (0.26, 0.45), (0.245, 0.72), (0.215, 0.88), (0.235, 0.93), (0.235, 1.0)], 9, 0.30),
]
VESSELS = [(it, k, rim, [(r * R / max(a for a, _ in pr), z) for r, z in pr], nu) for it, k, rim, pr, nu, R in _V]
NUNITS = sum(v[4] for v in VESSELS)
assert NUNITS == 64
NSEG = {"vat": 16, "barrel": 14, "half": 14, "cask": 12, "clay": 16, "dclay": 16, "bark": 16}
NW = 2                          # faces left out for the slot
WALLT = {"vat": 0.04, "barrel": 0.04, "half": 0.04, "cask": 0.04, "clay": 0.035, "dclay": 0.035, "bark": 0.03}
HOOPOUT = 0.012
GAP = 0.012
L = 4.12
SLOT_R = {"Sap": 0.34}          # round 4: the tub keeps round 3's vat slot (room in front for the label keg)
xs, cur = [], -L / 2 + 0.03
for it, kind, rim, prof, nu in VESSELS:
    R = SLOT_R.get(it, max(r for r, _ in prof)) + HOOPOUT + 0.003
    xs.append(cur + R); cur += 2 * R + GAP
SHIFT = -(cur - GAP - (-L / 2 + 0.03)) / 2 - (-L / 2 + 0.03)
xs = [x + SHIFT for x in xs]

# ---------- atlas ----------
TILES = {"hewn": (0, 0, 128, 32), "end0": (0, 32, 32, 32), "end1": (32, 32, 32, 32), "dark": (64, 32, 32, 32),
         "wearw": (96, 32, 32, 16), "weari": (96, 48, 32, 16), "iron": (0, 64, 128, 16),
         "clay": (0, 80, 32, 32), "dclay": (32, 80, 32, 32), "bark": (64, 80, 32, 32), "root": (96, 80, 32, 32),
         "iron2": (120, 112, 8, 16)}
for _i, _it in enumerate(LIQUID):          # round 5: per liquid a 16x16 side tile and an 8x16 top tile, 24 px apart
    TILES[_it + "_side"] = (24 * _i, 112, 16, 16); TILES[_it + "_top"] = (24 * _i + 16, 112, 8, 16)

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
    A[112:128] = B[64:80]                   # (spare) bunker iron again; round 3 paints sap into x 0-63
    nr = np.random.default_rng(41)
    yy, xx = np.meshgrid(np.arange(32), np.arange(32), indexing="ij")
    blocky = lambda s: np.kron(nr.random((32 // s, 32 // s)), np.ones((s, s), np.float32))
    edge = np.minimum(np.minimum(xx, 31 - xx), np.minimum(yy, 31 - yy))
    def clay(base, dark, light):
        t = blocky(8) * 0.22 + blocky(4) * 0.22 + blocky(2) * 0.14 + nr.random((32, 32)) * 0.14
        rings = 0.5 + 0.5 * np.sin(yy * 1.1 + 0.6 * np.sin(xx * 0.35 + 1.0))          # throwing rings, horizontal
        t += np.clip(rings - 0.7, 0, 1) * 1.1
        t += ((yy % 9) == 4) * 0.25                                                     # a crevice every few rings
        img = mix(base, dark, t)
        worn = (nr.random((32, 32)) < 0.05) & (t < 0.45)
        img[worn] = mix(img[worn], np.broadcast_to(light, img[worn].shape), np.full(worn.sum(), 0.6))
        return img
    A[80:112, 0:32] = clay(srgb((0.45, 0.31, 0.22)), srgb((0.27, 0.17, 0.12)), srgb((0.58, 0.45, 0.34)))
    A[80:112, 32:64] = clay(srgb((0.29, 0.24, 0.19)), srgb((0.14, 0.115, 0.09)), srgb((0.42, 0.36, 0.29)))
    # birch bark: muted off-white, dark horizontal lenticels, a few peeled warm patches, darker crevices
    base, dark, warm = srgb((0.64, 0.61, 0.54)), srgb((0.19, 0.16, 0.13)), srgb((0.47, 0.35, 0.24))
    t = blocky(4) * 0.18 + nr.random((32, 32)) * 0.12
    img = mix(base, dark, t)
    peel = (blocky(8) > 0.88) & (blocky(2) > 0.5)
    img[peel] = mix(img[peel], np.broadcast_to(warm, img[peel].shape), np.full(peel.sum(), 0.55))
    for _ in range(22):
        y, x, n = nr.integers(0, 32), nr.integers(0, 32), nr.integers(2, 6)
        for k in range(n): img[y, (x + k) % 32] = mix(img[y, (x + k) % 32][None], dark[None], np.array([0.6]))[0]
    img = mix(img, np.broadcast_to(dark, img.shape), (edge <= 0) * 0.25)
    A[80:112, 64:96] = img
    # root lashing: twisted withies, diagonal strands with dark gaps
    base, dark, light = srgb((0.40, 0.31, 0.19)), srgb((0.17, 0.12, 0.075)), srgb((0.53, 0.43, 0.29))
    s = (xx + yy * 0.8) % 7
    t = (s < 1.2) * 0.85 + nr.random((32, 32)) * 0.2 + ((yy % 8) == 0) * 0.5
    img = mix(base, dark, t)
    hl = (s > 3.0) & (s < 4.2)
    img[hl] = mix(img[hl], np.broadcast_to(light, img[hl].shape), np.full(hl.sum(), 0.45))
    A[80:112, 96:128] = img
    # round 5: five liquids, muted per STYLE.md: side (16x16, darker; liquids with faint vertical streaks the mod stretches with
    # the fill, jellies with blobs and trapped bubbles) and top (8x16, lighter, a few glints). Sap: the Sap item's green
    # (YggdrasilSap_d.png green texels ~0.31/0.70/0.28, muted, as round 4).
    LIQ_COL = {   # side base, dark, light; top base, dark, light; kind
        "Sap":  ((0.30, 0.48, 0.25), (0.19, 0.33, 0.15), (0.44, 0.62, 0.36), (0.40, 0.58, 0.32), (0.28, 0.44, 0.22), (0.58, 0.74, 0.47), "liquid"),
        "Tar":  ((0.075, 0.07, 0.065), (0.03, 0.03, 0.03), (0.21, 0.21, 0.23), (0.11, 0.105, 0.10), (0.05, 0.05, 0.05), (0.32, 0.32, 0.35), "liquid"),
        # Guck (coordinator: it read like Sap): darker, olive and murky, towards the Guck item's own colour (its rock texture x the
        # item tint 0/1/0.255: mean 0/0.45/0.09, a green with almost no blue), a cloudy jelly with a slightly lighter top
        "Guck": ((0.19, 0.23, 0.085), (0.09, 0.115, 0.04), (0.29, 0.33, 0.14), (0.25, 0.30, 0.11), (0.16, 0.20, 0.07), (0.36, 0.41, 0.18), "jelly"),
        "Ooze": ((0.31, 0.30, 0.19), (0.18, 0.18, 0.10), (0.44, 0.42, 0.28), (0.38, 0.37, 0.24), (0.25, 0.24, 0.15), (0.52, 0.50, 0.34), "jelly"),
        "Eitr": ((0.50, 0.62, 0.80), (0.36, 0.47, 0.66), (0.74, 0.84, 0.95), (0.62, 0.74, 0.90), (0.46, 0.58, 0.78), (0.86, 0.92, 0.98), "liquid"),
    }
    yy16, xx16 = np.meshgrid(np.arange(16), np.arange(16), indexing="ij")
    for i, it in enumerate(LIQUID):
        sb, sd, sl, tb, td, tl, kind = [srgb(c) if not isinstance(c, str) else c for c in LIQ_COL[it]]
        if kind == "liquid":
            t = 0.35 + 0.25 * np.sin(xx16 * 1.3 + 1.3 * np.sin(xx16 * 0.4 + i)) + nr.random((16, 16)) * 0.15
            side = mix(mix(sb, sd, t), np.broadcast_to(sl, (16, 16, 3)), (nr.random((16, 16)) < 0.05) * 0.6)
        else:
            blob = np.kron(nr.random((4, 4)), np.ones((4, 4), np.float32)) * 0.35 + np.kron(nr.random((8, 8)), np.ones((2, 2), np.float32)) * 0.3
            side = mix(sb, sd, blob + nr.random((16, 16)) * 0.12)
            bub = nr.random((16, 16)) < 0.07
            side[bub] = mix(side[bub], np.broadcast_to(sl, side[bub].shape), np.full(bub.sum(), 0.75))
        A[112:128, 24 * i:24 * i + 16] = side
        t = nr.random((16, 8)) * 0.25 + 0.15 * np.sin(np.arange(8)[None, :] * 0.8 + np.arange(16)[:, None] * 0.7)
        top = mix(tb, td, t)
        gl = nr.random((16, 8)) < (0.08 if kind == "liquid" else 0.05)
        top[gl] = mix(top[gl], np.broadcast_to(tl, top[gl].shape), np.full(gl.sum(), 0.85))
        A[112:128, 24 * i + 16:24 * i + 24] = top
    A[112:128, 120:128] = B[64:80, 0:8]
    im = bpy.data.images.new("coopersrow_atlas", TEX, TEX, alpha=False)
    px = np.concatenate([np.clip(A[::-1], 0, 1), np.ones((TEX, TEX, 1), np.float32)], 2)
    im.pixels.foreach_set(px.ravel())
    im.filepath_raw = os.path.join(OUTA, "coopersrow_atlas.png"); im.file_format = "PNG"; im.save()
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
def uv_box_face(f, uvl, kind, long_axis, seed):
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

def timber(name, size, pos, kind="hewn", rot=(0, 0, 0), jitter=0.012, bevel=0.016):
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

def iron(name, size, pos, rot=(0, 0, 0)):
    return timber(name, size, pos, kind="iron", rot=rot, jitter=0.0015, bevel=0)

def rivet(pos, normal, s=0.024, h=0.008):
    """square iron rivet head standing h off a face with this outward normal (a unit axis vector or a horizontal direction)"""
    n = Vector(normal).normalized()
    yaw = math.degrees(math.atan2(n.y, n.x)) if abs(n.z) < 0.5 else 0
    size = (h, s, s) if abs(n.z) < 0.5 else (s, s, h)
    p = Vector(pos) + n * (h / 2)
    timber("rivet", size, tuple(p), kind="rivet", rot=(0, 0, yaw), jitter=0, bevel=0)

def lerp_prof(prof, z):
    for (r0, h0), (r1, h1) in zip(prof, prof[1:]):
        if h0 <= z <= h1 + 1e-9 and h1 > h0: return r0 + (r1 - r0) * (z - h0) / (h1 - h0)
    return prof[-1][0] if z > prof[-1][1] else prof[0][0]

def vessel(vi):
    item, kind, rimz, prof_n, _nu = VESSELS[vi]
    x = xs[vi]
    h = rimz - DECK
    prof = [(r, f * h) for r, f in prof_n]
    clayish = kind in ("clay", "dclay")
    core = prof[:-2] + [(prof[-3][0], h)] if clayish else prof        # inner reference: without the rolled lip
    N = NSEG[kind]; T = WALLT[kind]
    phase = -math.pi / 2 - NW * math.pi / N                            # faces 0..NW-1 = the slot, centred on the front (-y)
    ang = [phase + 2 * math.pi * i / N for i in range(N + 1)]
    rin = lambda z: lerp_prof(core, z) - T
    rout = lambda z: lerp_prof(prof, z)
    wlo, whi = FLREL + 0.035, h - 0.13                                 # the slot, vessel-relative heights
    # profile rows: profile points, every ~0.08 m, the slot's ends
    zs = sorted(set([round(z, 5) for _r, z in prof] + [round(z, 5) for z in np.linspace(0, h, max(2, round(h / 0.08)) + 1)]
                    + [round(wlo, 5), round(whi, 5), round(FLREL, 5)]))
    zs = [z for z in zs if 0 <= z <= h + 1e-9]
    bm = bmesh.new(); uvl = bm.loops.layers.uv.verify()
    def P(r, a, z): return Vector((x + r * math.cos(a), r * math.sin(a), DECK + z))
    def face(pts, uvs):
        try: f = bm.faces.new([bm.verts.new(p) for p in pts])
        except ValueError: return
        for l, uv in zip(f.loops, uvs): l[uvl].uv = uv
    r_ = random.Random(100 + vi)
    staves = kind in ("barrel", "half", "cask", "vat")
    otile = {"vat": "hewn", "barrel": "dark", "half": "hewn", "cask": "hewn", "clay": "clay", "dclay": "dclay", "bark": "bark"}[kind]
    itile = {"vat": "dark", "barrel": "dark", "half": "dark", "cask": "dark", "clay": "dclay", "dclay": "dclay", "bark": "dark"}[kind]
    in_slot = lambda i, z0, z1: i < NW and z0 >= wlo - 1e-6 and z1 <= whi + 1e-6
    for i in range(N):
        a0, a1 = ang[i], ang[i + 1]
        cu = r_.uniform(0.5, 128) if otile == "hewn" else r_.uniform(0.5, max(0.6, 32 - h * DENS - 0.5))
        top_edge = r_.random() < 0.5
        cu_in = r_.uniform(0.5, max(0.6, 32 - h * DENS - 0.5))
        def stave_uv(tile, cu_, z, arc, width):
            py = 0.5 + arc * DENS if top_edge else 32 - 0.5 - (width - arc) * DENS
            # round 4 fix: a 32 px tile (dark timber) holds the whole stave height; rounds 2-3 ran into the wear swatch at the top
            return tuv(tile, cu_ + z * (DENS if tile == "hewn" else min(DENS, 30.5 / h)), py)
        def col_uv(tile, cu_, z, arc):     # clay/bark: rings follow z
            # round 4 fix: kept inside the 32 px tile on tall vessels (rounds 2-3 ran past it at the foot of the pots)
            return tuv(tile, min(cu_ + arc * DENS, 31.5), 0.5 + (h - z) * min(DENS * 0.97, 30.5 / h))
        for k in range(len(zs) - 1):
            z0, z1 = zs[k], zs[k + 1]
            if in_slot(i, z0, z1): continue
            r0, r1 = rout(z0), rout(z1)
            if staves:
                c = 0.007
                d0, d1 = 0.012 / r0, 0.012 / r1
                cols = [(a0, -c), (a0 + d0, 0), (a1 - d0, 0), (a1, -c)]
                cols1 = [(a0, -c), (a0 + d1, 0), (a1 - d1, 0), (a1, -c)]
                for j in range(3):
                    pts = [P(r0 + cols[j][1], cols[j][0], z0), P(r0 + cols[j + 1][1], cols[j + 1][0], z0),
                           P(r1 + cols1[j + 1][1], cols1[j + 1][0], z1), P(r1 + cols1[j][1], cols1[j][0], z1)]
                    if j == 1:
                        w0, w1 = r0 * (a1 - a0), r1 * (a1 - a0)
                        uvs = [stave_uv(otile, cu, z0, d0 * r0, w0), stave_uv(otile, cu, z0, (a1 - d0 - a0) * r0, w0),
                               stave_uv(otile, cu, z1, (a1 - d1 - a0) * r1, w1), stave_uv(otile, cu, z1, d1 * r1, w1)]
                    else:
                        uvs = [texel("wearw", r_)] * 4
                    face(pts, uvs)
            else:
                pts = [P(r0, a0, z0), P(r0, a1, z0), P(r1, a1, z1), P(r1, a0, z1)]
                face(pts, [col_uv(otile, cu, z0, 0), col_uv(otile, cu, z0, r0 * (a1 - a0)),
                           col_uv(otile, cu, z1, r1 * (a1 - a0)), col_uv(otile, cu, z1, 0)])
            if z1 > FLREL + 1e-6:      # inner wall (seen from inside)
                zi0 = max(z0, FLREL)
                q0, q1 = rin(zi0), rin(z1)
                pts = [P(q0, a1, zi0), P(q0, a0, zi0), P(q1, a0, z1), P(q1, a1, z1)]
                if staves:
                    w0, w1 = q0 * (a1 - a0), q1 * (a1 - a0)
                    uvs = [stave_uv(itile, cu_in, zi0, w0 * 0.98, w0), stave_uv(itile, cu_in, zi0, 0.0, w0),
                           stave_uv(itile, cu_in, z1, 0.0, w1), stave_uv(itile, cu_in, z1, w1 * 0.98, w1)]
                else:
                    uvs = [col_uv(itile, cu_in, zi0, q0 * (a1 - a0)), col_uv(itile, cu_in, zi0, 0),
                           col_uv(itile, cu_in, z1, 0), col_uv(itile, cu_in, z1, q1 * (a1 - a0))]
                face(pts, uvs)
        # top of the wall: end grain (staves) / clay or bark (pots, tub)
        ro, ri = rout(h), rin(h)
        if staves:
            c = 0.007; d = 0.012 / ro
            pts = [P(ri, a0, h), P(ri, a1, h), P(ro - c, a1, h), P(ro, a1 - d, h), P(ro, a0 + d, h), P(ro - c, a0, h)][::-1]
            et = "end0" if r_.random() < 0.5 else "end1"; cx_, cy_ = r_.uniform(9, 23), r_.uniform(9, 23)
            mid = (P(ri, (a0 + a1) / 2, h) + P(ro, (a0 + a1) / 2, h)) / 2
            face(pts, [tuv(et, cx_ + (p.x - mid.x) * DENS, cy_ + (p.y - mid.y) * DENS) for p in pts])
        else:
            pts = [P(ri, a0, h), P(ri, a1, h), P(ro, a1, h), P(ro, a0, h)]
            uvs = [col_uv(otile, cu, h - (ro - ri), 0), col_uv(otile, cu, h - (ro - ri), ri * (a1 - a0)),
                   col_uv(otile, cu, h, ro * (a1 - a0)), col_uv(otile, cu, h, 0)]
            face(pts[::-1], uvs[::-1])
    # slot: cut ends (horizontal) and reveals (the neighbouring walls' cut sides)
    a0, a1 = ang[0], ang[NW]
    for zc, up in ((wlo, True), (whi, False)):
        ro, ri = rout(zc), rin(zc)
        for i in range(NW):
            b0, b1 = ang[i], ang[i + 1]
            pts = [P(ri, b0, zc), P(ri, b1, zc), P(ro, b1, zc), P(ro, b0, zc)]
            if up: pts = pts[::-1]                  # top of the part below the slot faces up, bottom of the part above down
            if staves:
                et = "end0" if r_.random() < 0.5 else "end1"
                mid = sum(pts, Vector()) / 4
                face(pts, [tuv(et, 16 + (p.x - mid.x) * DENS, 16 + (p.y - mid.y) * DENS) for p in pts])
            else:
                face(pts, [tuv(otile, 4 + (p.x - pts[0].x) * DENS * 0.7 + 8, 3 + abs(p.y - pts[0].y) * DENS) for p in pts])
    srows = [z for z in zs if wlo - 1e-6 <= z <= whi + 1e-6]
    for a, side in ((a0, 1), (a1, -1)):
        for z0, z1 in zip(srows, srows[1:]):
            pts = [P(rin(z0), a, z0), P(rout(z0), a, z0), P(rout(z1), a, z1), P(rin(z1), a, z1)]
            tile = "hewn" if otile == "hewn" else ("dark" if staves else otile)
            uvs = [tuv(tile, 4 + ((z0 if j in (0, 1) else z1) - wlo) * DENS * 0.9, 2 + (rout(z0) - rin(z0)) * DENS * (1 if j in (1, 2) else 0)) for j in range(4)]
            if side > 0: pts = [pts[1], pts[0], pts[3], pts[2]]; uvs = [uvs[1], uvs[0], uvs[3], uvs[2]]
            face(pts, uvs)
    # inner floor
    fr = rin(FLREL)
    pts = [P(fr, ang[i], FLREL) for i in range(N)]
    ft = "dark" if not clayish else "dclay"
    face(pts, [tuv(ft, 16 + (p.x - x) * DENS * 0.6, 16 + p.y * DENS * 0.6) for p in pts])
    ob = new_obj(f"vessel_{item}", bm)

    # ---- bands: iron hoops (barrels), root lashing + bent-wood rim (tub) ----
    def band(z0, z1, tile, out=HOOPOUT, inner_over_slot=True, name="hoop"):
        b = bmesh.new(); ul = b.loops.layers.uv.verify()
        bo = random.Random(rng.randrange(10 ** 6)).uniform(0, 128)
        def F(pts, uvs):
            f = b.faces.new([b.verts.new(p) for p in pts])
            for l, uv in zip(f.loops, uvs): l[ul].uv = uv
        circ = 0.0
        for i in range(N):
            c0, c1 = ang[i], ang[i + 1]
            r00, r01 = rout(z0) + out, rout(z1) + out
            arc = r00 * (c1 - c0)
            if tile in ("iron",):
                uvs = [tuv(tile, bo + circ * DENS, 14.5), tuv(tile, bo + (circ + arc) * DENS, 14.5),
                       tuv(tile, bo + (circ + arc) * DENS, 1.5), tuv(tile, bo + circ * DENS, 1.5)]
            elif tile == "hewn":
                uvs = [tuv(tile, bo + circ * DENS, 30.5), tuv(tile, bo + (circ + arc) * DENS, 30.5),
                       tuv(tile, bo + (circ + arc) * DENS, 30.5 - (z1 - z0) * DENS), tuv(tile, bo + circ * DENS, 30.5 - (z1 - z0) * DENS)]
            else:
                q = (circ * DENS) % 24
                uvs = [tuv(tile, q, 4 + (z1 - z0) * DENS), tuv(tile, q + arc * DENS, 4 + (z1 - z0) * DENS), tuv(tile, q + arc * DENS, 4), tuv(tile, q, 4)]
            circ += arc
            F([P(r00, c0, z0), P(r00, c1, z0), P(r01, c1, z1), P(r01, c0, z1)], uvs)
            wt = "weari" if tile == "iron" else "wearw"
            F([P(rout(z1), c0, z1), P(r01, c0, z1), P(r01, c1, z1), P(rout(z1), c1, z1)], [texel(wt, rng)] * 4)
            F([P(rout(z0), c1, z0), P(r00, c1, z0), P(r00, c0, z0), P(rout(z0), c0, z0)], [texel(wt, rng)] * 4)
            if i < NW and inner_over_slot and z0 >= wlo - 1e-6 and z1 <= whi + 1e-6:     # its inner side, over the slot
                F([P(rout(z0), c1, z0), P(rout(z0), c0, z0), P(rout(z1), c0, z1), P(rout(z1), c1, z1)], uvs[::-1])
        return new_obj(name, b)
    slot_q = lambda f: wlo + f * (whi - wlo)
    def slot_rivets(zc, out):
        for a in (a0 - 0.035 / rout(zc), a1 + 0.035 / rout(zc)):
            r = rout(zc) + out
            rivet((x + r * math.cos(a), r * math.sin(a), DECK + zc), (math.cos(a), math.sin(a), 0), s=0.02, h=0.007)
    def gauge_bar(f):
        zc = slot_q(f)
        ro = rout(zc)
        half = ro * math.sin(NW * math.pi / N) + 0.045
        yb = -ro * math.cos(NW * math.pi / N) - 0.004
        iron("gauge", (2 * half, 0.012, 0.034), (x, yb - 0.006, DECK + zc))
        for sx in (-1, 1): rivet((x + sx * (half - 0.018), yb - 0.012, DECK + zc), (0, -1, 0), s=0.02, h=0.007)
    if staves:
        hw = 0.055
        for zc in (0.065, h - 0.075, slot_q(0.25), slot_q(0.75)):
            band(zc - hw / 2, zc + hw / 2, "iron")
        for zc in (slot_q(0.25), slot_q(0.75)): slot_rivets(zc, HOOPOUT)
        gauge_bar(0.5)
    else:
        for f in (0.25, 0.5, 0.75): gauge_bar(f)
    if kind == "bark":
        band(0.05, 0.11, "root", out=0.012, name="lashing")
        band(h - 0.125, h - 0.07, "root", out=0.012, name="lashing")
        band(h - 0.06, h, "hewn", out=0.02, name="rim")
    return {"item": item, "kind": kind, "x": x, "h": h, "rim": rimz, "prof": prof, "core": core, "N": N, "T": T, "ang": ang,
            "rin": rin, "rout": rout, "wlo": wlo, "whi": whi}

LABEL_CLIP = {}
def build_labels(VS):
    """per vessel: a spot on the deck in front, off the slot's axis (to the right; the last vessel to the left, clear of the end
    strap), LABEL_R clear of every vessel and inside the deck's front edge. position = the bottom centre of the item's rotated
    bounds on the deck (prefab space); rot_quat_xyzw = a turn about up, in the copies' convention. Every one of the six item
    models (Eitr: Resin's lump as its stand-in) is placed there at LABEL_LONG and checked against the frame."""
    docs = []
    yc = -D / 2 + LABEL_R + 0.01
    R = Matrix.Rotation(math.radians(LABEL_YAW), 3, "Z")
    Rn = np.array(R)
    for vi, V in enumerate(VS):
        Rv = max(r for r, _ in V["prof"]) + HOOPOUT + 0.003
        need = Rv + 0.015 + LABEL_R
        dx = max(0.11, math.sqrt(max(0.0, need ** 2 - yc ** 2)) + 0.005)
        side = -1 if vi == len(VS) - 1 else 1
        x = V["x"] + side * dx
        pos = Vector((x, yc, DECK + 0.004))      # the plank tops: DECK + at most 3 mm of jitter (their faces have no vertices mid-span)
        res = {}
        for it in ITEMS6:
            T = TEMPL[it]
            f = LABEL_LONG / (T["s"] * max(T["size"]))
            W = (T["V"] * f) @ Rn.T
            W = W + np.array([pos.x, pos.y, pos.z - float(W[:, 2].min())])
            hits = len(fbvh.overlap(BVHTree.FromPolygons([Vector(tuple(float(a) for a in w)) for w in W], T["tris"])))
            off = bool((np.abs(W[:, 1]) > D / 2).any() or (np.abs(W[:, 0]) > L / 2).any())
            res[it] = hits + (1000 if off else 0)
        LABEL_CLIP[V["item"]] = res
        eul, quat, err = rot_to_unity(R)
        docs.append({"compartment": vi, "position": [round(a, 4) for a in b2u_vec(pos)], "rot_quat_xyzw": quat, "fit_longest_m": LABEL_LONG})
        print("LABEL", json.dumps(docs[-1]), "dx", round(side * dx, 3), "clip per item", res, flush=True)
    return docs

def build_liquids(VS):
    """every vessel x every liquid item: a closed prism of height 1 from the floor point, the vessel's own face count and angles,
    its narrowest inside over the liquid's range 5 mm in, on the item's tiles; returns the anchors entries and the objects"""
    docs, obs = [], []
    for vi, V in enumerate(VS):
        N = V["N"]; ang = V["ang"]
        top_rel = V["h"] - LIQ_FREEBOARD
        r = min(V["rin"](z) for z in np.linspace(FLREL, top_rel, 40)) - LIQ_INSET
        floor = (V["x"], 0.0, FL + LIQ_FLOOR)
        top_y = DECK + top_rel
        me = None
        for it in LIQUID:
            bm = bmesh.new(); uvl = bm.loops.layers.uv.verify()
            bot = [bm.verts.new((r * math.cos(a), r * math.sin(a), 0.0)) for a in ang[:N]]
            top = [bm.verts.new((r * math.cos(a), r * math.sin(a), 1.0)) for a in ang[:N]]
            for i in range(N):
                j = (i + 1) % N
                f = bm.faces.new((bot[i], bot[j], top[j], top[i]))
                u0 = 0.5 + (i % 3) * 5
                for l, (pu, pv) in zip(f.loops, ((u0, 15.5), (u0 + 5, 15.5), (u0 + 5, 0.5), (u0, 0.5))): l[uvl].uv = tuv(it + "_side", pu, pv)
            f = bm.faces.new(top)
            for l, v in zip(f.loops, top): l[uvl].uv = tuv(it + "_top", 4 + v.co.x * DENS * 0.15, 8 + v.co.y * DENS * 0.3)
            f = bm.faces.new(bot[::-1])
            for l in f.loops: l[uvl].uv = tuv(it + "_side", 8, 8)
            bm.normal_update()
            name = f"Liquid_{vi}_{it}"
            me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
            for p in me.polygons: p.use_smooth = False
            ob = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(ob); ob.data.materials.append(MAT)
            obs.append((ob, name + ".obj"))
            docs.append({"compartment": vi, "item": it, "obj": name + ".obj", "floor": [round(a, 4) for a in b2u_vec(floor)],
                         "top_y": round(top_y, 4), "radius": round(r, 4), "sides": N})
        # clipping: the column at a few fills against the frame (the same prism for every item)
        tr = [(p.vertices[0], p.vertices[i], p.vertices[i + 1]) for p in me.polygons for i in range(1, len(p.vertices) - 1)]
        for fill in (0.05, 0.25, 0.5, 0.75, 1.0):
            pts = [Vector((floor[0] + v.co.x, v.co.y, floor[2] + v.co.z * (top_y - floor[2]) * fill)) for v in me.vertices]
            LIQ_CLIP.append((V["item"], fill, len(fbvh.overlap(BVHTree.FromPolygons(pts, tr)))))
        print("LIQUIDS vessel", vi, V["kind"], "radius", round(r, 4), "sides", N, "top_y", round(top_y, 3), "clip", LIQ_CLIP[-5:], flush=True)
    return docs, obs
LIQ_CLIP = []

# ---------- the stackable frame (replaces r5's skid and back rail) ----------
PS = 0.15                                  # posts 0.15 square (STYLE 0.12-0.16)
CLEAR = 0.35                               # clear height over the tallest vessel rim, under the top beams (pour room)
TALLEST_RIM = max(v[2] for v in VESSELS)   # 0.95 (Tar, Eitr)
ZB = round(TALLEST_RIM + CLEAR, 3)         # underside of the top ring = top of the posts
RH = 0.12                                  # ring beam height (STYLE 0.10-0.14)
ZT = round(ZB + RH, 3)                     # top of the ring
TOPPL = 0.05                               # closed plank deck on the ring
HTOT = round(ZT + TOPPL, 3)                # module height = the offset of a copy stacked on top
PROUD = 0.006                              # posts stand this far outside the sills and beams (no coplanar faces)
def _R(i):
    it, kind, rim, prof, nu = VESSELS[i]
    return SLOT_R.get(it, max(r for r, _ in prof)) + HOOPOUT + 0.003
XM = round((xs[2] + _R(2) + xs[3] - _R(3)) / 2, 3)   # the gap between vessel 2 (Sap) and 3 (Guck): the two middle uprights
HL, HD = L / 2, D / 2
XC = HL - PS / 2                           # corner post centres
YF_, YB_ = -(HD - PS / 2), HD - PS / 2
XP = [-XC, XM, XC]

def build_stack_frame():
    # ---- bottom frame: front and back sill, cross sleepers (also under every post line), the deck planks of r5 on top
    for sy in (YF_, YB_): timber("sill", (L, PS, SLEEPER_H), (0, sy, SLEEPER_H / 2), bevel=0.014, jitter=0.002)
    for xsl, w in ((-XC, PS), (-0.95, 0.14), (XM, PS), (1.04, 0.14), (XC, PS)):
        timber("sleeper", (w, D - 2 * PS + 0.02, SLEEPER_H), (xsl, 0, SLEEPER_H / 2), bevel=0.014, jitter=0.003)
    n = 5; w = D / n
    def deck(z0):
        for k in range(n):
            timber("plank", (L - 0.016, w - 0.006, PLANK_T), (rng.uniform(-0.004, 0.004), -HD + w / 2 + k * w, z0 + PLANK_T / 2),
                   bevel=0.010, jitter=0.002)
    deck(SLEEPER_H)
    for sx in (-1, 1):                     # iron straps over the deck ends between the posts (r5's), rivets on the plank centres
        xe = sx * 1.92
        iron("strap", (0.07, D - 2 * PS + 0.02, 0.006), (xe, 0, DECK + 0.003))
        for k in range(1, n - 1): rivet((xe, -HD + w / 2 + k * w, DECK + 0.006), (0, 0, 1), s=0.022, h=0.006)
    # ---- posts: six uprights, the foot on the ground, the head under the ring
    for sy, so in ((YF_, -1), (YB_, 1)):
        for sx in XP:
            cx = sx + (math.copysign(PROUD, sx) if sx != XM else 0.0)
            timber("post", (PS, PS, ZB + 0.02), (cx, sy + so * PROUD, (ZB + 0.02) / 2), bevel=0.016, jitter=0.002)
    # ---- top ring: heavy front and back beams, cross beams (over every post line and between), then the closed deck
    for sy in (YF_, YB_): timber("beam", (L, PS, RH), (0, sy, ZB + RH / 2), bevel=0.014, jitter=0.002)
    for xb, wb in ((-XC, PS), ((-XC + XM) / 2, 0.12), (XM, PS), ((XM + XC) / 2, 0.12), (XC, PS)):
        timber("crossbeam", (wb, D - 2 * PS + 0.02, RH), (xb, 0, ZB + RH / 2), bevel=0.014, jitter=0.003)
    deck(ZT)
    # ---- knee braces under the ring: along the front and back (into the post and the beam), and across at every post
    KB = 0.32; r2 = math.sqrt(2)
    for sy, s in ((YF_, 1), (YB_, -1)):        # s = the direction into the store
        for sx in XP:
            for d in (-1, 1):
                if abs(sx + d * 0.3) > XC + 0.01: continue          # none outside the end posts
                x0, z0 = sx + d * PS / 2, ZB - KB
                timber("brace", (KB * r2 + 0.10, 0.12, 0.12), (x0 + d * KB / 2, sy, z0 + KB / 2), rot=(0, -45 * d, 0), jitter=0.004, bevel=0.016)
            y0 = sy + s * PS / 2
            timber("brace", (0.12, KB * r2 + 0.10, 0.12), (sx, y0 + s * KB / 2, ZB - KB + KB / 2), rot=(45 * s, 0, 0), jitter=0.004, bevel=0.016)
    # ---- iron: T brackets where the posts meet the ring, a strap round the foot of every post, end plates on the corners
    for sy, so in ((YF_, -1), (YB_, 1)):
        pface = sy + so * (PS / 2 + PROUD)      # outer face of the posts
        bface = so * HD                         # outer face of the beams
        for sx in XP:
            px = sx + (math.copysign(PROUD, sx) if sx != XM else 0.0)
            iron("bracket", (0.10, 0.012, 0.26), (sx, pface + so * 0.006, ZB - 0.12))                  # down the post
            cx = sx if sx == XM else sx - math.copysign(0.10, sx)
            iron("bracket", (0.36, 0.012, 0.07), (cx, bface + so * 0.006, ZB + 0.055 + 0.0))           # along the beam
            for zr_ in (ZB - 0.07, ZB - 0.19): rivet((sx, pface + so * 0.012, zr_), (0, so, 0))
            for dx in (-0.12, 0.12): rivet((cx + dx, bface + so * 0.012, ZB + 0.055), (0, so, 0))
            iron("strap", (PS + 0.03, 0.012, 0.12), (sx, pface + so * 0.006, 0.34))
            for dx in (-0.045, 0.045): rivet((sx + dx, pface + so * 0.012, 0.34), (0, so, 0))
            if sx != XM:                                                                            # corner: plates on the end face
                sg = 1 if sx > 0 else -1
                xface = px + sg * (PS / 2)
                iron("bracket", (0.012, 0.10, 0.26), (xface + sg * 0.006, sy + so * PROUD, ZB - 0.12))
                for zr_ in (ZB - 0.07, ZB - 0.19): rivet((xface + sg * 0.012, sy + so * PROUD, zr_), (sg, 0, 0))
                iron("strap", (0.012, PS + 0.03, 0.12), (xface + sg * 0.006, sy + so * PROUD, 0.34))
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

# ---------- items ----------
TEMPL = {}
def load_templates():
    for item, *_ in VESSELS:
        src = "Resin" if item == "Eitr" else item
        ob = load_item(src, anchor="center")[0]
        info = json.load(open(f"{ITEMS_DIR}/{src}/info.json"))
        bmin, bmax = Vector(info["bounds_min"]), Vector(info["bounds_max"])
        size = bmax - bmin
        s = LONGS[item] / max(size)
        ob.data.transform(Matrix.Diagonal((s, s, s, 1))); ob.data.update()
        ob.location = (0, 0, -50); ob.hide_render = True; ob.name = "templ_" + item
        V = np.array([tuple(v.co) for v in ob.data.vertices], np.float32)
        bm = bmesh.new(); bm.from_mesh(ob.data)
        hull = bmesh.ops.convex_hull(bm, input=bm.verts)
        planes = []
        for f in [g for g in hull["geom"] if isinstance(g, bmesh.types.BMFace)]:
            n = f.normal.copy(); planes.append((n.x, n.y, n.z, n.dot(f.verts[0].co)))
        hv = np.array(sorted({tuple(round(c, 5) for c in v.co) for v in hull["geom"] if isinstance(v, bmesh.types.BMVert)}), np.float32)
        bm.free()
        TEMPL[item] = {"obj": ob, "mesh": ob.data, "V": V, "s": float(s), "size": tuple(size), "center": tuple((bmin + bmax) / 2),
                       "planes": np.array(planes, np.float32), "hv": hv, "radius": float(np.linalg.norm(V, axis=1).max()),
                       "he": (V.max(0) - V.min(0)) / 2, "mid": (V.max(0) + V.min(0)) / 2, "src": src,
                       "tris": [(p.vertices[0], p.vertices[i], p.vertices[i + 1]) for p in ob.data.polygons for i in range(1, len(p.vertices) - 1)]}

def world_verts(item, M):
    Mn = np.array(M); return TEMPL[item]["V"] @ Mn[:3, :3].T + Mn[:3, 3]

# ---------- anchors (Unity prefab space: ux=-bx, uy=bz, uz=-by) ----------
CB2U = Matrix(((-1, 0, 0), (0, 0, 1), (0, -1, 0)))
def b2u_vec(v): return (-v[0], v[2], -v[1])
def rot_to_unity(R):
    Ru = CB2U @ R @ CB2U.transposed()
    q = Ru.to_quaternion()
    e = Ru.to_euler("ZXY")
    ex = Matrix.Rotation(e.x, 3, "X"); ey = Matrix.Rotation(e.y, 3, "Y"); ez = Matrix.Rotation(e.z, 3, "Z")
    err = max(abs(a - b) for ra, rb in zip((ey @ ex @ ez), Ru) for a, b in zip(ra, rb))
    return [round(math.degrees(e.x), 3), round(math.degrees(e.y), 3), round(math.degrees(e.z), 3)], [round(q.x, 5), round(q.y, 5), round(q.z, 5), round(q.w, 5)], err

C = Matrix(((-1, 0, 0), (0, 0, 1), (0, -1, 0)))
def u2b_pos(p): return Vector((-p[0], -p[2], p[1]))
def u2b_rot(q): return C.transposed() @ Quaternion((q[3], q[0], q[1], q[2])).to_matrix() @ C

def prism_hits(cx, r, z0, z1, N=16, bvh=None):
    """triangle overlaps between the frame and a closed N-sided prism (ring N bottom verts, then N top verts)"""
    pts = [Vector((cx + r * math.cos(2 * math.pi * i / N), r * math.sin(2 * math.pi * i / N), z)) for z in (z0, z1) for i in range(N)]
    T = []
    for i in range(N):
        j = (i + 1) % N
        T += [(i, j, N + j), (i, N + j, N + i)]
    for i in range(1, N - 1): T += [(N, N + i, N + i + 1), (0, i + 1, i)]
    return len((bvh or fbvh).overlap(BVHTree.FromPolygons(pts, T)))

# ---------- scene + frame ----------
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
atlas = build_atlas()
MAT = bpy.data.materials.new("coopersrow"); MAT.use_nodes = True
_b = MAT.node_tree.nodes["Principled BSDF"]
_t = MAT.node_tree.nodes.new("ShaderNodeTexImage"); _t.image = atlas; _t.interpolation = "Closest"
MAT.node_tree.links.new(_t.outputs["Color"], _b.inputs["Base Color"])
_b.inputs["Roughness"].default_value = 1.0; _b.inputs["Specular IOR Level"].default_value = 0.0

build_stack_frame()
_sv, _st = [], []        # the stack frame alone (before the vessels), for the pouring-room check
for _o in PARTS:
    _off = len(_sv); _v, _t_ = tri_list(_o.data); _sv += _v; _st += [(a + _off, b + _off, c + _off) for a, b, c in _t_]
sbvh = BVHTree.FromPolygons(_sv, _st, all_triangles=True)
VS = [vessel(i) for i in range(len(VESSELS))]
frame = join(list(PARTS), "CoopersRow")
FV_, FT_ = tri_list(frame.data)
frame_tris = len(FT_)
fbvh = BVHTree.FromPolygons(FV_, FT_, all_triangles=True)
FVn = np.array([tuple(v) for v in FV_])
frame_size = (float(FVn[:, 0].max() - FVn[:, 0].min()), float(FVn[:, 2].max() - FVn[:, 2].min()), float(FVn[:, 1].max() - FVn[:, 1].min()))
print("FRAME tris", frame_tris, "size W H D", [round(a, 3) for a in frame_size], "z range", round(FVn[:, 2].min(), 3), round(FVn[:, 2].max(), 3),
      "x range", round(FVn[:, 0].min(), 3), round(FVn[:, 0].max(), 3), "y range", round(FVn[:, 1].min(), 3), round(FVn[:, 1].max(), 3), flush=True)
print("STACK ZB", ZB, "ZT", ZT, "HTOT", HTOT, "XM", XM, "tallest rim", TALLEST_RIM, flush=True)

load_templates()
LIQUIDS_DOC, LIQ_OBS = build_liquids(VS)

# ---------- contents: round 5's settled units, verbatim; clip-checked against THIS frame ----------
R5 = json.load(open(os.path.join(R5DIR, "coopersrow_anchors.json")))
clipped, top_z, n_copies = [], 0.0, 0
for u in R5["units_list"]:
    for cp in u["copies"]:
        n_copies += 1
        Rb = u2b_rot(cp["quat_xyzw"]); p = u2b_pos(cp["world_position"])
        T = TEMPL[cp["item"]]
        W = T["V"] @ np.array(Rb).T + np.array(p)
        top_z = max(top_z, float(W[:, 2].max()))
        if fbvh.overlap(BVHTree.FromPolygons([Vector(tuple(float(a) for a in w)) for w in W], T["tris"])): clipped.append((u["index"], cp["item"]))
print("CLIPPING (lumps of r5 against the stack frame)", len(clipped), "of", n_copies, "; highest lump z", round(top_z, 3), "; clear under the ring", round(ZB - top_z, 3), flush=True)
LABELS_DOC = build_labels(VS)
lab_clip = sum(v for res in LABEL_CLIP.values() for v in res.values())
liq_clip = sum(c for _i, _f, c in LIQ_CLIP)
print("LABEL clip total", lab_clip, "; LIQUID clip total", liq_clip, flush=True)
# pouring room: a column over each mouth (the inside of the rim less 1 cm) from the rim up to the underside of the ring
pour = {V["item"]: prism_hits(V["x"], V["rin"](V["h"]) - 0.01, V["rim"] + 0.001, ZB - 0.01, V["N"], sbvh) for V in VS}
print("POUR COLUMN hits per vessel", pour, flush=True)
# the same column widened by 5 cm round the mouth (a ladle or bucket swing)
wide = {V["item"]: prism_hits(V["x"], V["rin"](V["h"]) + 0.05, V["rim"] + 0.02, ZB - 0.01, 16, sbvh) for V in VS}
print("WIDE COLUMN (rin + 5 cm) hits per vessel", wide, flush=True)
# labels and liquids as r5 wrote them: same numbers?
same_lab = all(a["position"] == b["position"] and a["rot_quat_xyzw"] == b["rot_quat_xyzw"] for a, b in zip(LABELS_DOC, R5["labels"]))
same_liq = all(abs(a["top_y"] - b["top_y"]) < 1e-9 and a["floor"] == b["floor"] and abs(a["radius"] - b["radius"]) < 1e-9 for a, b in zip(LIQUIDS_DOC, R5["liquids"]))
print("labels equal to r5:", same_lab, "; liquids equal to r5:", same_liq, flush=True)

checks = dict(R5["checks"])
checks.update({"clipping_against_stack_frame": len(clipped), "of_copies": n_copies,
               "label_clipping_per_vessel_and_item": LABEL_CLIP, "liquid_clipping": liq_clip,
               "highest_lump_z_m": round(top_z, 3), "clear_under_ring_above_highest_lump_m": round(ZB - top_z, 3),
               "clear_under_ring_above_tallest_rim_m": round(ZB - TALLEST_RIM, 3),
               "pour_column_hits_per_vessel": pour, "pour_column_wide_hits_per_vessel": wide,
               "labels_equal_r5": same_lab, "liquids_equal_r5": same_liq,
               "note": "units, copies and simulation are round 5's, copied verbatim (same vessels, same places); the clip check is re-run against this frame"})
frame_info = {"obj": "CoopersRow.obj", "tris": frame_tris, "size_m": [round(a, 3) for a in frame_size], "atlas": "coopersrow_atlas.png 128x128",
              "atlas_sources": R5["frame"]["atlas_sources"]}
stack_info = {"module_height_m": HTOT, "stack_offset_y_unity": HTOT, "ring_underside_y": ZB, "ring_top_y": ZT, "deck_top_y": HTOT,
              "posts": 6, "post_size_m": PS, "post_x_unity": [round(-x, 4) for x in XP],
              "doc": "A second copy stands with its origin raised by stack_offset_y (module_height_m): its sills (y 0..0.10) rest on this one's "
                     "deck planks, its six posts stand over this one's six posts, and its sills/sleepers/ring footprint is this one's. The "
                     "vessels, units, liquids and labels are identical to coopersrow_r5 (same places, same anchors logic); the floor the "
                     "vessels stand on is the bottom deck (y 0.15), the pouring room is the clear height under the ring."}
doc = dict(R5)
doc["store"] = ("Cooper's Row, stackable (round 1): " + R5["store"].split(": ", 1)[1] + "; in a timber frame of six uprights (four corners and two in the "
                "gap between the Sap and the Guck vessel) under a ring of beams and a closed plank deck, %.2f m clear over the tallest rim for pouring; a "
                "matching bottom frame so a second copy stands on the first" % (ZB - TALLEST_RIM))
doc["frame"] = frame_info; doc["stack"] = stack_info
doc["liquids"] = LIQUIDS_DOC; doc["labels"] = LABELS_DOC; doc["checks"] = checks
print("COOPERSROWSTACK frame tris", frame_tris, flush=True)

# files: atlas (saved) -> OBJ -> anchors last (temp file + rename)
bpy.ops.object.select_all(action="DESELECT"); frame.select_set(True); bpy.context.view_layer.objects.active = frame
bpy.ops.wm.obj_export(filepath=os.path.join(OUTA, "CoopersRow.obj"), export_selected_objects=True, export_materials=False,
                      export_triangulated_mesh=True, forward_axis="NEGATIVE_Z", up_axis="Y")
for lo, fn in LIQ_OBS:
    bpy.ops.object.select_all(action="DESELECT"); lo.select_set(True); bpy.context.view_layer.objects.active = lo
    bpy.ops.wm.obj_export(filepath=os.path.join(OUTA, fn), export_selected_objects=True, export_materials=False,
                          export_triangulated_mesh=True, forward_axis="NEGATIVE_Z", up_axis="Y")
tmp = os.path.join(OUT, "coopersrow_anchors.json.tmp")
json.dump(doc, open(tmp, "w"), indent=1)
os.replace(tmp, os.path.join(OUTA, "coopersrow_anchors.json"))
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

def import_frame(objpath, png, dx, dy, dz=0.0):
    before = set(bpy.data.objects)
    bpy.ops.wm.obj_import(filepath=objpath, forward_axis="NEGATIVE_Z", up_axis="Y")
    new = [o for o in bpy.data.objects if o not in before]
    m = atlas_mat(png, os.path.basename(png) + str(dx) + str(dz))
    for o in new:
        o.data.materials.clear(); o.data.materials.append(m); o.location = (dx, dy, dz)
    return new

RAW = {}
def raw_mesh(item):
    if item not in RAW:
        src = "Resin" if item == "Eitr" else item
        ob = load_item(src, anchor="center")[0]
        info = json.load(open(f"{ITEMS_DIR}/{src}/info.json"))
        for m in ob.data.materials:
            b = m.node_tree.nodes.get("Principled BSDF")
            if not b: continue
            b.inputs["Specular IOR Level"].default_value = 0.25
            b.inputs["Roughness"].default_value = 0.35 if item in ("Tar", "Resin", "Guck", "Sap", "Eitr") else 0.7
        if item == "Eitr":
            me = ob.data.copy(); ob.data = me
            for i, m in enumerate(me.materials):
                m2 = m.copy(); me.materials[i] = m2
                for n in m2.node_tree.nodes:
                    if n.type == "MIX": n.inputs["B"].default_value = (0.30, 0.42, 1.0, 1)
                b = m2.node_tree.nodes.get("Principled BSDF")
                b.inputs["Emission Color"].default_value = (0.25, 0.35, 1.0, 1); b.inputs["Emission Strength"].default_value = 0.6
        if item == "Tar":
            for m in ob.data.materials:
                b = m.node_tree.nodes.get("Principled BSDF")
                if b: b.inputs["Base Color"].default_value = (0.03, 0.03, 0.035, 1)
        RAW[item] = (ob.data, np.array([tuple(v.co) for v in ob.data.vertices], np.float32), max(Vector(info["bounds_max"]) - Vector(info["bounds_min"])))
        bpy.data.objects.remove(ob, do_unlink=True)
    return RAW[item]

def spawn_cr(folder, contents, dx, dy, dz, tag, empty=False):
    """a Cooper's Row (r5 or stack) as the mod draws it: the frame; per vessel (item, fill): the label copy, a liquid column when the
    item has an entry for that vessel (T(floor) * S(1, (top_y - floor.y) * fill, 1)), else the first fill x units of lumps"""
    png = os.path.join(folder, "coopersrow_atlas.png")
    d = json.load(open(os.path.join(folder, "coopersrow_anchors.json")))
    liqs = {(e["compartment"], e["item"]): e for e in d["liquids"]}
    labs = {e["compartment"]: e for e in d["labels"]}
    import_frame(os.path.join(folder, "CoopersRow.obj"), png, dx, dy, dz)
    if empty: return
    groups = {}
    for u in d["units_list"]: groups.setdefault(u["compartment"], []).append(u)
    for c, (item, fill) in enumerate(contents):
        if not item or fill <= 0: continue
        lab = labs[c]
        mesh, Vv, longest = raw_mesh(item)
        s_ = lab["fit_longest_m"] / longest
        Rb = u2b_rot(lab["rot_quat_xyzw"])
        low = float(((Vv * s_) @ np.array(Rb).T)[:, 2].min())
        p = u2b_pos(lab["position"]) + Vector((dx, dy, dz - low))
        ob = bpy.data.objects.new("label_" + item, mesh); sc.collection.objects.link(ob)
        ob.matrix_world = Matrix.Translation(p) @ Rb.to_4x4() @ Matrix.Diagonal((s_,) * 3 + (1,))
        if (c, item) in liqs:
            e = liqs[(c, item)]
            lob = import_frame(os.path.join(folder, e["obj"]), png, 0, 0)[0]
            bpy.ops.object.select_all(action="DESELECT"); lob.select_set(True); bpy.context.view_layer.objects.active = lob
            lob.location = (0, 0, 0); bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
            lob.location = u2b_pos(e["floor"]) + Vector((dx, dy, dz))
            lob.scale = (1, 1, (e["top_y"] - e["floor"][1]) * fill)
            continue
        us = groups[c]; exact = fill * len(us); n = int(math.floor(exact + 1e-9)); part = exact - n
        for ui, u in enumerate(us[:n + (1 if part > 1e-6 else 0)]):
            cps = u["copies"] if ui < n else u["copies"][:max(1, math.ceil(len(u["copies"]) * part))]
            for cp in cps:
                mesh, Vv, longest = raw_mesh(item)
                s_ = cp["fit_longest_m"] / longest
                Rb = u2b_rot(cp["quat_xyzw"])
                p = u2b_pos([a + b for a, b in zip(u["position"], cp["offset"])])
                ob = bpy.data.objects.new(f"{tag}_item", mesh); sc.collection.objects.link(ob)
                ob.matrix_world = Matrix.Translation(p + Vector((dx, dy, dz))) @ Rb.to_4x4() @ Matrix.Diagonal((s_,) * 3 + (1,))

pm = bpy.data.materials.new("plain"); pm.use_nodes = True
pm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.62, 0.60, 0.55, 1)
def post(x, y):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(x, y, 0.9)); p = bpy.context.active_object
    p.scale = (0.12, 0.12, 1.8); p.data.materials.append(pm); p.name = "post_1.8m"

BUNK = os.path.join(REPO, "assets", "bunker_r4")
def bunker(dx, dy): import_frame(os.path.join(BUNK, "Bunker.obj"), os.path.join(BUNK, "bunker_atlas.png"), dx, dy)
MIX7 = [(it, 0.7) for it in ITEMS6]
ROWS = {"line": 0.0, "lineempty": 14.0, "stack": 28.0, "filled": 42.0, "full": 56.0}
BX, RX, NX = -4.75, 0.0, 4.85          # bunker_r4 | coopersrow_r5 | the stackable one
ROWOBJ = {}; _seen = set(bpy.data.objects)
def mark(row):
    global _seen
    now = set(bpy.data.objects); ROWOBJ[row] = list(now - _seen); _seen = now
# a) the family lineup: bunker_r4 (frame only, as in the family render), r5 and the new piece at 70 %, then all three bare
bunker(BX, ROWS["line"] + 0.18); spawn_cr(R5DIR, MIX7, RX, ROWS["line"], 0.0, "r5"); spawn_cr(OUTA, MIX7, NX, ROWS["line"], 0.0, "ns")
post(-7.2, ROWS["line"] - 0.5); mark("line")
bunker(BX, ROWS["lineempty"] + 0.18); spawn_cr(R5DIR, MIX7, RX, ROWS["lineempty"], 0.0, "r5", empty=True); spawn_cr(OUTA, MIX7, NX, ROWS["lineempty"], 0.0, "ns", empty=True)
post(-7.2, ROWS["lineempty"] - 0.5); mark("lineempty")
# b) two copies stacked (both at 70 %: the upper with the mix reversed)
spawn_cr(OUTA, MIX7, 0.0, ROWS["stack"], 0.0, "s1"); spawn_cr(OUTA, [(it, 0.7) for it in reversed(ITEMS6)], 0.0, ROWS["stack"], HTOT, "s2")
post(2.7, ROWS["stack"] - 0.4); mark("stack")
# c) the new piece filled ~70 % with labels (and full)
spawn_cr(OUTA, MIX7, 0.0, ROWS["filled"], 0.0, "f70"); post(2.7, ROWS["filled"] - 0.4); mark("filled")
spawn_cr(OUTA, [(it, 1.0) for it in ITEMS6], 0.0, ROWS["full"], 0.0, "f100"); mark("full")

world = bpy.data.worlds.new("w"); sc.world = world; world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.42, 0.45, 0.5, 1)
world.node_tree.nodes["Background"].inputs[1].default_value = 0.9
sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN")); sun.data.energy = 3.2
sun.rotation_euler = (math.radians(50), 0, math.radians(35)); sc.collection.objects.link(sun)
bpy.ops.mesh.primitive_plane_add(size=240, location=(0, 30, -0.002))
gm = bpy.data.materials.new("ground"); gm.use_nodes = True
gm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.16, 0.14, 0.11, 1)
bpy.context.active_object.data.materials.append(gm)
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam); sc.camera = cam
sc.render.engine = "BLENDER_EEVEE_NEXT"
sc.render.resolution_x, sc.render.resolution_y = (1000, 562) if QUICK else (1600, 900)
sc.view_settings.view_transform = "Standard"
EYE = 1.75
VIEWS = {  # name: (row, yaw deg, horizontal distance, eye height, target, lens)
    "lineup34": ("line", -24, 15.5, 1.9, (-1.0, ROWS["line"], 0.75), 35),
    "lineupempty34": ("lineempty", -24, 15.5, 1.9, (-1.0, ROWS["lineempty"], 0.75), 35),
    "lineupfront": ("line", 0, 15.5, 1.7, (0.0, ROWS["line"], 0.75), 35),
    "stack34": ("stack", -30, 9.0, 2.4, (0.0, ROWS["stack"], HTOT), 35),
    "stackfront": ("stack", 0, 9.0, 1.8, (0.0, ROWS["stack"], HTOT), 35),
    "stackside": ("stack", -90, 8.0, 1.8, (0.0, ROWS["stack"], HTOT), 35),
    "filled34": ("filled", -30, 6.0, EYE, (0.0, ROWS["filled"], 0.7), 35),
    "filledfront": ("filled", 0, 5.2, 1.6, (0.0, ROWS["filled"], 0.7), 35),
    "filledclose": ("filled", -14, 2.6, 1.55, ((xs[1] + xs[2]) / 2, ROWS["filled"], 0.75), 30),
    "filledtop": ("filled", -20, 3.2, 2.4, (0.0, ROWS["filled"], 1.0), 30),
    "full34": ("full", -30, 6.0, EYE, (0.0, ROWS["full"], 0.7), 35),
}
for vn, (row, yaw, dist, hgt, tgt, lens) in VIEWS.items():
    if VIEWSEL and vn not in VIEWSEL: continue
    for rk, obs in ROWOBJ.items():
        for o in obs: o.hide_render = (rk != row)
    t = Vector(tgt)
    cam.location = t + Vector((math.sin(math.radians(yaw)) * dist, -math.cos(math.radians(yaw)) * dist, hgt - t.z))
    cam.rotation_euler = (t - cam.location).to_track_quat("-Z", "Y").to_euler(); cam.data.lens = lens
    sc.render.filepath = os.path.join(OUT, f"coopersrowstack-{vn}.png")
    bpy.ops.render.render(write_still=True)
    print("RENDER", vn, flush=True)
print("DONE")
