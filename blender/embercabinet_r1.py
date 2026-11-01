"""Ember Cabinet, round 1 (ITEMS.md section 2, new store #5): an iron-framed, glass-fronted lantern cabinet, 1.03 x 2.0 m,
for the glowing things: Wisp, Glow worm, Fader's ember, Memorial coal, Molten core, Black core, Frost core, Shield core and the
two orbs (frost and fire, thunder and blood). Joost also named "embers and the other glowy things from the Mistlands", so the
cabinet has two spare niches for the next glowing item (Surtling core, a later biome's core): it takes them without touching a
niche that has an owner.
Run: blender -b -P embercabinet_r1.py -- [--out DIR] [--assets DIR] [--quick] [--no-render] [--views a,b] [--cseed N]
     [--capscale F] [--items2 DIR]

Store (SPEC.md "What lies where"): nothing lies mixed, every kind has a niche of its own, a niche that fills may be shared only
with an empty one. 12 niches (3 columns x 4 rows, each a lantern-like cell: dark oiled timber on all sides, the open front framed
by iron bars with a corner plate and a name-plate on every cell) for 10 kinds, so 2 niches belong to no kind. 64 units
(SPEC: 64 is the standard) spread by how much of each there is to find:
  row 4 (top, 0.22 m)   Wisp 8 | Fader's ember 5 | spare B 6        (the small glowing balls: the most plentiful, wisps come in tens)
  row 3 (0.28 m)        Orb (frost and fire) 4 | Orb (thunder and blood) 4 | spare A 5
  row 2 (0.34 m)        Molten core 6 | Black core 6 | Glow worm 5
  row 1 (bottom, 0.40 m) Frost core 5 | Memorial coal 5 | Shield core 5          (the big heavy pieces stand lowest)
The row heights follow the items: small things get short niches so a heap fills them, the big cores get tall ones. The split is
my guess of how much of each there is to find (stack sizes not checked in game); any niche shows as full at its unit count.
The glass is a thin frame with open panes: iron bars at every shelf and mullion, a corner plate in each opening corner (where
the glazing would be clipped in), and nothing across the openings, so the items show whole and their own emissive glow does the
lighting in game (the mod's material is opaque, so a glass face would hide them). Posts, bars and cap are iron (bunker_r4's dark
iron tile); the carcass (walls, shelves, mullions, back) is dark oiled timber (metalpallet_r3's tile), the plinth hewn timber
(bunker_r4). The cap is a hipped iron roof with a ridge strip, a finial and a carrying ring, as a ship's lantern has.
Layout, Blender metres, z up, -y front, x to the right as seen from the front: carcass x +-0.50, y -0.20..0.24 (inner depth
0.40, back boards 0.04), plinth 0.06-0.20, shelves 0.04, niche columns 0.27 wide (x -0.445..-0.175, -0.135..0.135,
0.175..0.445), niche rows 0.24-0.64, 0.68-1.02, 1.06-1.34, 1.38-1.60, eaves at 1.64-1.68, roof to 1.84, ring to ~1.99.

Contents: each niche is filled copy by copy (Blender rigid bodies / Bullet, convex hulls, friction 0.75, restitution 0; batches
of copies dropped onto the frozen earlier ones at the lowest free places, settled, checked, frozen) until there is no room for
another under the niche's ceiling; the invisible colliders are the niche's six inner faces pulled in by GAP. A copy that leaves
the niche, touches the frame or does not settle is taken out (its batch re-settled without it). The copy sequence is then cut
into the niche's units in drop order (any prefix rests only on what is shown). Item sizes (longest side, fit_longest_m, about
0.25-0.5 of true size, the balls 0.7): Wisp and Fader's ember 0.07 (true: a 0.1 m ball, drawn by the mod with the game's own
sphere and its glowing material; the rip tool cannot read Unity's built-in sphere, so these two are laid out with a 0.1 m
UV-sphere stand-in, as Treasure Hoard does for the Amber Pearl), orbs 0.085, Molten core 0.09, Black core 0.12, Memorial coal
0.12, Frost core 0.12, Shield core 0.13, Glow worm 0.13. The spare niches are laid out with a Molten core at 0.09 (row 3) and
an orb at 0.07 (row 4): whatever lands there is drawn at that size.
Items not in ValheimRip/items yet (all ten) were ripped with the same tool (items_extract.py, wrapper in the session
scratchpad: embercabinet_r1/rip_ember.py) into <scratchpad>/embercabinet_r1/items, with their emission maps; --items2 points here.
unit.position = centre of the unit's copies; unit.box = their bounding box, its bottom lowered to the lowest rotated-bounds
corner (the mod's never-below-the-floor lift leaves the settled heap alone). unit.bin = the niche (row * 3 + column, row 0 the
bottom); unit.cell = [column, row]; unit.item = the kind the niche is for (absent on the two spare niches, whose units carry
example_item, the item their heap was laid out with).
Atlas (128 px, point filtered, 48 px per metre): hewn timber, end grain and iron rows from assets/bunker_r4, dark oiled hewn
timber strip and wear swatch from assets/metalpallet_r3; nothing new.
Files: assets/embercabinet_r1/{EmberCabinet.obj, embercabinet_atlas.png, embercabinet_anchors.json}, the json written last (temp
file + rename). Renders and simlog in --out (default: the scratchpad embercabinet_r1 folder).
"""
import bpy, bmesh, sys, os, math, json, random, time, importlib.util
import numpy as np
from mathutils import Vector, Matrix, Euler, Quaternion
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, ".."))
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
def arg(k, d=None): return argv[argv.index(k) + 1] if k in argv else d
SCR = "C:/Users/joost/AppData/Local/Temp/claude/C--Users-joost--pai/5e4bc60b-cdfe-4638-8e29-2e507fa13cf9/scratchpad/embercabinet_r1"
OUTA = arg("--assets", os.path.join(REPO, "assets", "embercabinet_r1"))
OUT = arg("--out", SCR)
QUICK = "--quick" in argv
NORENDER = "--no-render" in argv
VIEWSEL = arg("--views").split(",") if "--views" in argv else None
ITEM_DIRS = ["C:/Users/joost/ValheimRip/items", arg("--items2", SCR + "/items")]
os.makedirs(OUTA, exist_ok=True); os.makedirs(OUT, exist_ok=True)
rng = random.Random(29)                           # frame
crng = random.Random(int(arg("--cseed", 37)))     # contents

TEX, DENS = 128, 48.0
FPS = 24
MARGIN = 0.003
GRID = 0.03
GAP = 0.008                    # colliders this far inside the wood

# ---------- item loading (the ripped items live in ValheimRip/items, the ten new ones in --items2) ----------
_MODS = {}
def _mod(d):
    if d not in _MODS:
        spec = importlib.util.spec_from_file_location("load_item_" + str(len(_MODS)), os.path.join(d, "load_item.py"))
        m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); _MODS[d] = m
    return _MODS[d]
def item_dir(name):
    for d in ITEM_DIRS:
        if os.path.exists(os.path.join(d, name, "info.json")): return d
    raise FileNotFoundError(name)
def load_one(name): return _mod(item_dir(name)).load_item(name, anchor="center")
def item_info(name): return json.load(open(os.path.join(item_dir(name), name, "info.json")))
EMIS = json.load(open(os.path.join(ITEM_DIRS[1], "emission.json")))

# ---------- layout (Blender metres, z up, -y front) ----------
HXC = 0.50                                   # carcass half width
WALLT, MULLT, SHELF, BACKT = 0.055, 0.04, 0.04, 0.04
FY, BY = -0.20, 0.20                         # the niches' front and back planes
COLS = [(-0.445, -0.175), (-0.135, 0.135), (0.175, 0.445)]
ROWS_Z = [(0.24, 0.64), (0.68, 1.02), (1.06, 1.34), (1.38, 1.60)]      # niche floor and ceiling per row, bottom to top
Z_PLINTH0, Z_PLINTH1 = 0.06, 0.20
Z_TOP = 1.64                                 # top of the carcass
Z_EAVES1 = 1.68
Z_ROOF = 1.84
LEVELS = [(0.20, 0.24), (0.64, 0.68), (1.02, 1.06), (1.34, 1.38), (1.60, 1.64)]     # the five boards the front bars cover
BARX = 0.46                                  # the front bars run between the posts
GAME_TRIS_SPHERE = 768                       # Unity's built-in Sphere

# (row, col): home item (None = spare), units, example item for the heap, fit_longest_m, cap on copies
PLAN = {
    (0, 0): ("FrostCore", 5, "FrostCore", 0.12, 40),
    (0, 1): ("MemorialCoal", 5, "MemorialCoal", 0.12, 50),
    (0, 2): ("ShieldCore", 5, "ShieldCore", 0.13, 50),
    (1, 0): ("MoltenCore", 6, "MoltenCore", 0.09, 80),
    (1, 1): ("BlackCore", 6, "BlackCore", 0.12, 60),
    (1, 2): ("GlowWorm", 5, "GlowWorm", 0.13, 40),
    (2, 0): ("OrbFrostFire", 4, "OrbFrostFire", 0.085, 80),
    (2, 1): ("OrbThunderBlood", 4, "OrbThunderBlood", 0.085, 80),
    (2, 2): (None, 5, "MoltenCore", 0.09, 80),
    (3, 0): ("Wisp", 8, "Wisp", 0.07, 70),
    (3, 1): ("FaderEmber", 5, "FaderEmber", 0.07, 70),
    (3, 2): (None, 6, "OrbFrostFire", 0.07, 80),
}
def tkey(item, fit): return f"{item}@{fit:g}"
SPHERES = {"Wisp": 0.1, "FaderEmber": 0.1}   # true diameter of the stand-in sphere (the prefab's ball: Sphere mesh at scale 0.1)
CAPSCALE = float(arg("--capscale", 1.0))
COMPS = []
for (r, c), (home, units, ex, fit, cap) in sorted(PLAN.items()):
    x0, x1 = COLS[c]; z0, z1 = ROWS_Z[r]
    COMPS.append(dict(row=r, col=c, group=r * 3 + c, home=home, item=ex, key=tkey(ex, fit), units=units, fit=fit, cap=max(units + 2, int(cap * CAPSCALE)),
                      x0=x0, x1=x1, y0=FY, y1=BY, z0=z0, z1=z1, batch=5 if ex in SPHERES or ex.startswith("Orb") else 4))
NUNITS = sum(c["units"] for c in COMPS)
assert NUNITS == 64
for c in COMPS: c["bx"] = (c["x0"] + GAP, c["x1"] - GAP, c["y0"] + GAP, c["y1"] - GAP, c["z0"] + 0.004, c["z1"] - GAP)

# ---------- atlas ----------
TILES = {"hewn": (0, 0, 128, 32), "end0": (0, 32, 32, 32), "end1": (32, 32, 32, 32), "dark": (64, 32, 32, 32),
         "wearw": (96, 32, 32, 16), "weari": (96, 48, 32, 16), "iron": (0, 64, 128, 16), "dkwood": (0, 80, 128, 32),
         "iron2": (0, 112, 128, 16)}

def load_px(path):
    im = bpy.data.images.load(path)
    w, h = im.size
    a = np.array(im.pixels[:], np.float32).reshape(h, w, 4)[::-1, :, :3]     # top-down
    bpy.data.images.remove(im)
    return a

def build_atlas():
    B = load_px(os.path.join(REPO, "assets", "bunker_r4", "bunker_atlas.png"))
    P = load_px(os.path.join(REPO, "assets", "metalpallet_r3", "metalpallet_atlas.png"))
    A = np.zeros((TEX, TEX, 3), np.float32)
    A[0:32] = B[0:32]                       # bunker hewn timber
    A[32:64, 0:64] = B[32:64, 0:64]         # bunker end grain, rings 0 and 1
    A[32:64, 64:96] = P[0:32, 0:32]         # pallet dark oiled hewn timber (one texel for the plates' slots)
    A[32:64, 96:128] = P[32:64, 96:128]     # pallet wear swatch: worn timber (top), worn iron (bottom)
    A[64:80] = B[64:80]                     # bunker dark iron
    A[80:112] = P[0:32]                     # pallet dark oiled hewn timber, the whole strip
    A[112:128] = B[64:80]                   # (spare) bunker iron again
    im = bpy.data.images.new("embercabinet_atlas", TEX, TEX, alpha=False)
    px = np.concatenate([np.clip(A[::-1], 0, 1), np.ones((TEX, TEX, 1), np.float32)], 2)
    im.pixels.foreach_set(px.ravel())
    im.filepath_raw = os.path.join(OUTA, "embercabinet_atlas.png"); im.file_format = "PNG"; im.save()
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
STRIP = {"hewn": 0.75, "iron": 0.375, "dkwood": 0.125}       # v of each strip's bottom (bunker_r4's mapping)
STRIPH = {"hewn": 32, "iron": 16, "dkwood": 32}

def new_obj(name, bm):
    bm.normal_update()
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = False
    ob = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(ob)
    ob.data.materials.append(MAT); PARTS.append(ob)
    return ob

def uv_faces(bm, uvl, kind, L, seed):
    """the family's mapping: grain along the timber's long axis L in the hewn (or dark) strip at 48 px/m, end grain on faces
    across it, the wear swatch on chamfers and narrow faces; iron in the iron strip, its thin edges and rivets worn iron"""
    L = Vector(L).normalized()
    r = random.Random(seed)
    off = r.random()
    wear = "weari" if kind in ("iron", "rivet") else "wearw"
    for f in bm.faces:
        cs = [l.vert.co.copy() for l in f.loops]
        n = f.normal
        if kind in ("rivet", "dark"):
            uv = texel("weari" if kind == "rivet" else "dark", r)
            for l in f.loops: l[uvl].uv = uv
            continue
        if kind not in ("iron",) and abs(n.dot(L)) > 0.9:          # end grain
            t1 = n.cross(Vector((0, 0, 1)) if abs(n.z) < 0.9 else Vector((1, 0, 0))).normalized(); t2 = n.cross(t1)
            c = sum(cs, Vector()) / len(cs)
            ext = max(max(abs((p - c).dot(t1)), abs((p - c).dot(t2))) for p in cs) * DENS
            sc_ = min(1.0, 13.0 / max(ext, 1e-4))
            et = "end0" if r.random() < 0.5 else "end1"; cx, cy = r.uniform(14, 18), r.uniform(14, 18)
            for l in f.loops:
                p = l.vert.co - c
                l[uvl].uv = tuv(et, cx + p.dot(t1) * DENS * sc_, cy + p.dot(t2) * DENS * sc_)
            continue
        t = n.cross(L)
        if t.length < 1e-4: t = n.orthogonal()
        t.normalize()
        al = [p.dot(L) for p in cs]; ac = [p.dot(t) for p in cs]
        if min(max(al) - min(al), max(ac) - min(ac)) < 0.022:
            uv = texel(wear, r)
            for l in f.loops: l[uvl].uv = uv
            continue
        strip = "iron" if kind == "iron" else ("dkwood" if kind == "darkwood" else "hewn")
        hpx = STRIPH[strip]
        vmin, span = min(ac), max(max(ac) - min(ac), 1e-4)
        vscale = min(1.0, (hpx / DENS) / span)
        room = max(hpx / TEX - span * vscale * DENS / TEX * 0.94 - 0.012, 0)
        voff = ((seed * 0.618) % 1) * room
        for l, a_, c_ in zip(f.loops, al, ac):
            u = a_ * DENS / TEX + off
            v = STRIP[strip] + ((c_ - vmin) * vscale * DENS / TEX) * 0.94 + 0.0075 + voff
            l[uvl].uv = (u, v)

def finish(bm, kind, L, bevel, name, xform=None):
    if bevel > 0: bmesh.ops.bevel(bm, geom=bm.edges[:], offset=bevel, segments=1, affect="EDGES")
    bm.normal_update()
    uvl = bm.loops.layers.uv.verify()
    uv_faces(bm, uvl, kind, L, rng.randrange(10 ** 6))
    if xform is not None: bmesh.ops.transform(bm, matrix=xform, verts=bm.verts)
    return new_obj(name, bm)

def box(name, lo, hi, kind="hewn", bevel=0.012, jitter=0.0, L=None, xform=None):
    """an axis-aligned timber (or iron) between corners lo and hi; L: grain axis (default: the longest side)"""
    lo, hi = Vector(lo), Vector(hi)
    size = hi - lo
    if L is None:
        a = max(range(3), key=lambda i: size[i]); L = [0, 0, 0]; L[a] = 1
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector(tuple((lo[i] + hi[i]) / 2 + v.co[i] * size[i] for i in range(3)))
    if jitter:
        la = max(range(3), key=lambda i: abs(L[i]))
        for v in bm.verts:
            for i in range(3):
                if i != la: v.co[i] += rng.uniform(-jitter, jitter)
    return finish(bm, kind, L, bevel, name, xform)

def dk(name, lo, hi, bevel=0.01, L=None): return box(name, lo, hi, kind="darkwood", bevel=bevel, jitter=0.0, L=L)
def iron(name, lo, hi, xform=None, bevel=0.0): return box(name, lo, hi, kind="iron", bevel=bevel, jitter=0, xform=xform)

def rivet(pos, normal, s=0.02, h=0.008):
    n = Vector(normal).normalized()
    p = Vector(pos) + n * (h / 2)
    half = [s / 2] * 3
    a = max(range(3), key=lambda i: abs(n[i])); half[a] = h / 2
    box("rivet", tuple(p[i] - half[i] for i in range(3)), tuple(p[i] + half[i] for i in range(3)), kind="rivet", bevel=0, jitter=0)

def strut(p0, p1, w, t, kind="iron"):
    """a bar of width w (across) and thickness t between two points, any direction (hip strips of the roof)"""
    p0, p1 = Vector(p0), Vector(p1)
    d = p1 - p0; Ln = d.length
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts: v.co = Vector((v.co.x * Ln, v.co.y * w, v.co.z * t))
    rot = d.to_track_quat("X", "Z").to_matrix().to_4x4()
    return finish(bm, kind, (1, 0, 0), 0, "strut", Matrix.Translation((p0 + p1) / 2) @ rot)

def ring(name, cx, cy, cz, r=0.055, seg=10, t=0.012):
    """an iron ring in the y-z plane at x = cx, built from short square bars"""
    for k in range(seg):
        a0, a1 = 2 * math.pi * k / seg, 2 * math.pi * (k + 1) / seg
        am = (a0 + a1) / 2
        L = 2 * r * math.sin(math.pi / seg) + t * 0.6
        bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
        for v in bm.verts: v.co = Vector((v.co.x * t, v.co.y * L, v.co.z * t))
        bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(am + math.pi / 2, 3, "X"))
        bmesh.ops.translate(bm, verts=bm.verts, vec=Vector((cx, cy + r * math.cos(am), cz + r * math.sin(am))))
        finish(bm, "iron", (0, math.cos(am + math.pi / 2), math.sin(am + math.pi / 2)), 0, name)

def roof(name, rx, ry, lx, z0, z1):
    """a hipped roof: base rectangle (+-rx, +-ry) at z0, a ridge from -lx to +lx at z1, bottom closed"""
    bm = bmesh.new()
    b = [bm.verts.new(p) for p in ((-rx, -ry, z0), (rx, -ry, z0), (rx, ry, z0), (-rx, ry, z0))]
    r0, r1 = bm.verts.new((-lx, 0, z1)), bm.verts.new((lx, 0, z1))
    bm.faces.new((b[0], b[1], r1, r0)); bm.faces.new((b[2], b[3], r0, r1))
    bm.faces.new((b[1], b[2], r1)); bm.faces.new((b[3], b[0], r0)); bm.faces.new((b[3], b[2], b[1], b[0]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return finish(bm, "iron", (1, 0, 0), 0, name)

def build_frame():
    W = 0.045
    # feet and plinth
    for sx in (-1, 1):
        for sy in (-1, 1):
            xa, xb = sorted((sx * 0.455, sx * 0.525)); ya, yb = (-0.235, -0.165) if sy < 0 else (0.175, 0.265)
            iron("foot", (xa, ya, 0.0), (xb, yb, Z_PLINTH0), bevel=0.003)
    for a, b in ((Z_PLINTH0, 0.13), (0.13, Z_PLINTH1)):
        box("plinth_front", (-0.47, -0.22, a), (0.47, -0.195, b - 0.002), bevel=0.008, L=(1, 0, 0))
        box("plinth_back", (-0.47, 0.215, a), (0.47, 0.24, b - 0.002), bevel=0.008, L=(1, 0, 0))
        for sx in (-1, 1):
            box("plinth_side", (min(sx * 0.5, sx * 0.475), -0.195, a), (max(sx * 0.5, sx * 0.475), 0.215, b - 0.002), bevel=0.008, L=(0, 1, 0))
    # carcass in dark oiled timber
    dk("bottom", (-HXC, FY, Z_PLINTH1), (HXC, BY, 0.24), L=(1, 0, 0))
    dk("top", (-HXC, FY, ROWS_Z[3][1]), (HXC, BY, Z_TOP), L=(1, 0, 0))
    for (za, zb) in ROWS_Z:
        for sx in (-1, 1):
            dk("wall", (min(sx * HXC, sx * (HXC - WALLT)), FY, za), (max(sx * HXC, sx * (HXC - WALLT)), BY, zb), L=(0, 1, 0))
        for sx in (-1, 1):
            xa, xb = (COLS[0][1], COLS[1][0]) if sx < 0 else (COLS[1][1], COLS[2][0])
            dk("mullion", (xa, FY, za), (xb, BY, zb), L=(0, 1, 0))
    for r in range(3):
        dk("shelf", (-HXC, FY, ROWS_Z[r][1]), (HXC, BY, ROWS_Z[r + 1][0]), L=(1, 0, 0))
    xs_ = np.linspace(-HXC, HXC, 6)
    for a, b in zip(xs_, xs_[1:]):
        dk("back", (a + 0.002, BY, Z_PLINTH1), (b - 0.002, BY + BACKT, Z_TOP), bevel=0.008, L=(0, 0, 1))
    # corner posts (iron)
    for sx in (-1, 1):
        for sy in (-1, 1):
            xa, xb = sorted((sx * 0.46, sx * 0.52))
            ya, yb = (-0.23, -0.17) if sy < 0 else (0.18, 0.26)
            iron("post", (xa, ya, 0.02), (xb, yb, Z_TOP), bevel=0.004)
            for z in (0.12, 0.45, 0.85, 1.25, 1.55):
                if sy < 0: rivet((sx * 0.49, -0.23, z), (0, -1, 0), s=0.02)
                rivet((sx * 0.52, (-0.2 if sy < 0 else 0.22), z), (sx, 0, 0), s=0.02)
    # the front: bars at the five boards, mullion bars, the wall bars
    for (za, zb) in LEVELS:
        iron("bar", (-BARX, -0.225, za - 0.012), (BARX, FY, zb + 0.012))
    for xa, xb in ((COLS[0][1], COLS[1][0]), (COLS[1][1], COLS[2][0])):
        iron("mullbar", (xa - 0.012, -0.225, Z_PLINTH1), (xb + 0.012, FY, Z_TOP))
    for sx in (-1, 1):
        iron("wallbar", (min(sx * BARX, sx * (HXC - WALLT + 0.012)), -0.225, Z_PLINTH1), (max(sx * BARX, sx * (HXC - WALLT + 0.012)), FY, Z_TOP))
    # per opening: four corner plates (where the glazing would be clipped in), a name-plate on the bar under it
    for (za, zb) in ROWS_Z:
        for (xa, xb) in COLS:
            xo0, xo1 = xa + 0.012, xb - 0.012            # the visible opening
            zo0, zo1 = za, zb
            for xc, sxn in ((xo0, 1), (xo1, -1)):
                for zc, szn in ((zo0, 1), (zo1, -1)):
                    p = Vector((xc, -0.225, zc))
                    iron("clip", (min(p.x, p.x + sxn * 0.04), -0.2315, min(p.z, p.z + szn * 0.04)), (max(p.x, p.x + sxn * 0.04), -0.225, max(p.z, p.z + szn * 0.04)))
                    rivet((p.x + sxn * 0.016, -0.2315, p.z + szn * 0.016), (0, -1, 0), s=0.014, h=0.006)
            xm = (xa + xb) / 2
            box("plate", (xm - 0.05, -0.2315, za - 0.052), (xm + 0.05, -0.225, za - 0.012 - 0.0), kind="iron", bevel=0, jitter=0)
            box("slot", (xm - 0.036, -0.2335, za - 0.045), (xm + 0.036, -0.2315, za - 0.02), kind="dark", bevel=0, jitter=0)
    # bar rivets at the mullion crossings
    for xa, xb in ((COLS[0][1], COLS[1][0]), (COLS[1][1], COLS[2][0])):
        for (za, zb) in LEVELS[1:4]:
            for x in ((xa + xb) / 2,):
                rivet((x, -0.225, (za + zb) / 2), (0, -1, 0), s=0.02)
    # hinge straps on the left, a latch on the right: a door in everything but panes
    for z in (0.40, 0.95, 1.40):
        iron("hinge", (-BARX, -0.2315, z - 0.022), (-0.30, -0.225, z + 0.022))
        iron("hingeknuckle", (-0.505, -0.2335, z - 0.03), (-0.465, -0.20, z + 0.03))
        rivet((-0.37, -0.2315, z), (0, -1, 0), s=0.018)
        rivet((-0.43, -0.2315, z), (0, -1, 0), s=0.018)
    iron("latch", (0.42, -0.2315, 0.90), (0.47, -0.225, 1.04))
    iron("latchtongue", (0.40, -0.2395, 0.955), (0.455, -0.2315, 0.985))
    rivet((0.445, -0.2315, 0.92), (0, -1, 0), s=0.016); rivet((0.445, -0.2315, 1.02), (0, -1, 0), s=0.016)
    # sides: bands at the shelves, a ring handle each
    for sx in (-1, 1):
        for (za, zb) in LEVELS[1:4]:
            xo = sx * (HXC + 0.0)
            iron("sideband", (min(xo, xo + sx * 0.006), -0.16, za - 0.012), (max(xo, xo + sx * 0.006), 0.18, zb + 0.012))
            for y in (-0.10, 0.02, 0.14): rivet((xo + sx * 0.006, y, (za + zb) / 2), (sx, 0, 0), s=0.018)
        xo = sx * HXC
        iron("staple", (min(xo + sx * 0.006, xo + sx * 0.012), -0.04, 0.80), (max(xo + sx * 0.006, xo + sx * 0.012), 0.04, 0.85))
        ring("handle", xo + sx * 0.022, 0.0, 0.80 - 0.05, r=0.055)
    # back: three straps and a band
    for x in (-0.30, 0.0, 0.30):
        iron("backstrap", (x - W / 2, BY + BACKT, Z_PLINTH1 + 0.02), (x + W / 2, BY + BACKT + 0.006, Z_TOP - 0.02))
        for z in (0.34, 0.62, 0.90, 1.18, 1.46): rivet((x, BY + BACKT + 0.006, z), (0, 1, 0), s=0.02)
    iron("backband", (-0.46, BY + BACKT, 0.80), (0.46, BY + BACKT + 0.006, 0.80 + W))
    # cap: an iron eaves plate, a hipped roof with ridge and hip strips, finial, carrying ring
    box("eaves", (-0.56, -0.285, Z_TOP), (0.56, 0.305, Z_EAVES1), kind="iron", bevel=0.006, jitter=0)
    for z in (Z_TOP + 0.004,):
        for x in (-0.46, -0.23, 0.0, 0.23, 0.46): rivet((x, -0.285, Z_TOP + 0.02), (0, -1, 0), s=0.02)
    rx, ry, lx = 0.55, 0.28, 0.20
    roof("roof", rx, ry, lx, Z_EAVES1, Z_ROOF)
    for sx in (-1, 1):
        for sy in (-1, 1):
            strut((sx * rx, sy * ry, Z_EAVES1 + 0.004), (sx * lx, 0, Z_ROOF + 0.004), 0.034, 0.016)
    strut((-lx, 0, Z_ROOF + 0.006), (lx, 0, Z_ROOF + 0.006), 0.04, 0.02)
    iron("finial_base", (-0.035, -0.035, Z_ROOF - 0.002), (0.035, 0.035, Z_ROOF + 0.03), bevel=0.003)
    iron("finial", (-0.016, -0.016, Z_ROOF + 0.03), (0.016, 0.016, Z_ROOF + 0.09), bevel=0.002)
    ring("carry", 0.0, 0.0, Z_ROOF + 0.09 + 0.055 - 0.012, r=0.055, seg=12, t=0.014)

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
def sphere_mesh(radius, seg=24, rings=16, name="ball"):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=rings, radius=radius)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    return me

TEMPL = {}
def load_templates():
    for (item, fit) in sorted({(c["item"], c["fit"]) for c in COMPS}):
        key = tkey(item, fit)
        if item in SPHERES:
            d = SPHERES[item]; s = fit / d
            ob = bpy.data.objects.new("templ_" + item, sphere_mesh(d / 2 * s, 16, 10, "templ_" + item)); bpy.context.scene.collection.objects.link(ob)
            size, center = (d,) * 3, (0.0, 0.0, 0.0)
        else:
            ob = load_one(item)[0]
            info = item_info(item)
            bmin, bmax = Vector(info["bounds_min"]), Vector(info["bounds_max"])
            size, center = tuple(bmax - bmin), tuple((bmin + bmax) / 2)
            s = fit / max(size)
            ob.data.transform(Matrix.Diagonal((s, s, s, 1))); ob.data.update()
        ob.location = (0, 0, -50); ob.hide_render = True; ob.name = "templ_" + key
        V = np.array([tuple(v.co) for v in ob.data.vertices], np.float32)
        bm = bmesh.new(); bm.from_mesh(ob.data)
        hull = bmesh.ops.convex_hull(bm, input=bm.verts)
        planes = []
        for f in [g for g in hull["geom"] if isinstance(g, bmesh.types.BMFace)]:
            nn = f.normal.copy(); planes.append((nn.x, nn.y, nn.z, nn.dot(f.verts[0].co)))
        hv = np.array(sorted({tuple(round(q, 5) for q in v.co) for v in hull["geom"] if isinstance(v, bmesh.types.BMVert)}), np.float32)
        bm.free()
        TEMPL[key] = {"obj": ob, "item": item, "mesh": ob.data, "V": V, "s": float(s), "size": tuple(size), "center": tuple(center),
                       "planes": np.array(planes, np.float32), "hv": hv, "radius": float(np.linalg.norm(V, axis=1).max()),
                       "he": (V.max(0) - V.min(0)) / 2, "mid": (V.max(0) + V.min(0)) / 2,
                       "tris": [(p.vertices[0], p.vertices[i], p.vertices[i + 1]) for p in ob.data.polygons for i in range(1, len(p.vertices) - 1)],
                       "game_tris": GAME_TRIS_SPHERE if item in SPHERES else None}
        if TEMPL[key]["game_tris"] is None: TEMPL[key]["game_tris"] = len(TEMPL[key]["tris"])

def world_verts(key, M):
    Mn = np.array(M); return TEMPL[key]["V"] @ Mn[:3, :3].T + Mn[:3, 3]

def make_box_mesh(name, size):
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts: v.co = Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2]))
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    return me

def add_rb(ob, kind, shape, mass=1.0, damp=(0.25, 0.45)):
    for o in bpy.context.view_layer.objects: o.select_set(False)
    ob.select_set(True); bpy.context.view_layer.objects.active = ob
    bpy.ops.rigidbody.object_add(type=kind)
    rb = ob.rigid_body
    rb.collision_shape = shape; rb.friction = 0.75; rb.restitution = 0.0
    rb.use_margin = True; rb.collision_margin = MARGIN
    if kind == "ACTIVE":
        rb.mass = mass; rb.linear_damping, rb.angular_damping = damp
        rb.use_deactivation = False

def colliders(c):
    sc = bpy.context.scene
    x0, x1, y0, y1, z0, z1 = c["bx"]
    T = 0.3
    cx, cy, cz = (x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2
    obs = []
    for nm, sz, pos in [("floor", (x1 - x0 + 2 * T, y1 - y0 + 2 * T, T), (cx, cy, z0 - T / 2)),
                        ("ceil", (x1 - x0 + 2 * T, y1 - y0 + 2 * T, T), (cx, cy, z1 + T / 2)),
                        ("wx0", (T, y1 - y0 + 2 * T, z1 - z0), (x0 - T / 2, cy, cz)), ("wx1", (T, y1 - y0 + 2 * T, z1 - z0), (x1 + T / 2, cy, cz)),
                        ("wy0", (x1 - x0, T, z1 - z0), (cx, y0 - T / 2, cz)), ("wy1", (x1 - x0, T, z1 - z0), (cx, y1 + T / 2, cz))]:
        ob = bpy.data.objects.new(f"col_{c['group']}_{nm}", make_box_mesh(nm, sz)); ob.location = pos
        sc.collection.objects.link(ob); add_rb(ob, "PASSIVE", "BOX"); ob.hide_render = True; obs.append(ob)
    return obs

def surface(c, HV):
    x0, x1, y0, y1, z0, z1 = c["bx"]
    nx, ny = int(math.ceil((x1 - x0) / GRID)), int(math.ceil((y1 - y0) / GRID))
    gx = x0 + (np.arange(nx) + 0.5) * GRID; gy = y0 + (np.arange(ny) + 0.5) * GRID
    X, Y = np.meshgrid(gx, gy, indexing="ij")
    H = np.full((nx, ny), z0, np.float64)
    if len(HV):
        ix = np.clip(((HV[:, 0] - x0) / GRID).astype(int), 0, nx - 1); iy = np.clip(((HV[:, 1] - y0) / GRID).astype(int), 0, ny - 1)
        np.maximum.at(H, (ix, iy), HV[:, 2])
        P = np.pad(H, 1, mode="edge")
        H = np.max([P[i:i + nx, j:j + ny] for i in range(3) for j in range(3)], axis=0)
    mouth = (X > x0 + 0.03) & (X < x1 - 0.03) & (Y > y0 + 0.03) & (Y < y1 - 0.03)
    Tg = np.full((nx, ny), z1 - 0.012)
    return X, Y, H, Tg, mouth

def check_copy(c, key, M):
    W = world_verts(key, M)
    x0, x1, y0, y1, z0, z1 = c["bx"]
    tol = 0.006
    escaped = bool((W[:, 0] < x0 - tol).any() or (W[:, 0] > x1 + tol).any() or (W[:, 1] < y0 - tol).any()
                   or (W[:, 1] > y1 + tol).any() or (W[:, 2] < z0 - tol).any() or (W[:, 2] > z1 + tol).any())
    clip = bool(fbvh.overlap(BVHTree.FromPolygons([Vector(tuple(float(a) for a in w)) for w in W], TEMPL[key]["tris"])))
    return escaped, False, clip

def rand_rot(item):
    return Euler((crng.uniform(0, math.tau), crng.uniform(0, math.tau), crng.uniform(0, math.tau)), "XYZ")

SIMLOG = {"comps": {}, "frames": [], "retries": 0, "unsettled": 0, "resid": [], "batches_dropped": 0}
def settle(obs, maxf=300):
    sc = bpy.context.scene
    sc.frame_set(1)
    prev = None; still = [0] * len(obs); f = 1; dp = dr = 0.0
    while f < maxf:
        f += 1; sc.frame_set(f)
        cur = [(o.matrix_world.translation.copy(), o.matrix_world.to_quaternion()) for o in obs]
        if prev:
            for i, (a, b) in enumerate(zip(cur, prev)):
                dpi = (a[0] - b[0]).length; dri = a[1].rotation_difference(b[1]).angle
                still[i] = still[i] + 1 if (dpi < 2e-4 and dri < 4e-3 and f > 8) else 0
            dp = max((a[0] - b[0]).length for a, b in zip(cur, prev)); dr = max(a[1].rotation_difference(b[1]).angle for a, b in zip(cur, prev))
            if min(still) >= 3: break
        prev = cur
    return f, still, dp, dr

def simulate(c):
    sc = bpy.context.scene
    rbw = sc.rigidbody_world
    coll = bpy.data.collections.new(f"rb_{c['group']}")
    rbw.collection = coll
    cols = colliders(c)
    item = c["item"]; key = c["key"]; T_ = TEMPL[key]; R = T_["radius"]
    x0, x1, y0, y1, z0, z1 = c["bx"]
    damp = (0.5, 0.95) if item in SPHERES or item.startswith("Orb") else (0.25, 0.45)
    HV = np.zeros((0, 3), np.float32)
    copies = []; fails = 0; t0 = time.time()
    slack = max(0.05, 0.9 * R)
    while len(copies) < c["cap"] and fails < 6:
        X, Y, H, Tg, mouth = surface(c, HV)
        cover = float(((Tg - H)[mouth] < slack).mean())
        if cover >= 0.97: break
        deficit = Tg - H
        nb = min(c["batch"], c["cap"] - len(copies))
        placed = 0
        for attempt in range(4):
            inset = R * 0.55 + 0.01 + 0.015 * attempt
            obs = []; spots = []
            sc.frame_set(1)
            for kb in range(nb):
                best = None
                # the lowest places first (so a niche fills evenly, layer by layer), with a little noise and a push away from
                # the other copies of this batch; the first one that has room under the ceiling
                ok_ = (X > x0 + inset) & (X < x1 - inset) & (Y > y0 + inset) & (Y < y1 - inset)
                sc_ = H + np.array([[crng.uniform(0, 0.02 + 0.01 * attempt) for _j in range(H.shape[1])] for _i in range(H.shape[0])])
                for (qx, qy) in spots: sc_ = sc_ + 0.3 * (((X - qx) ** 2 + (Y - qy) ** 2) < (2.2 * R) ** 2)
                sc_ = np.where(ok_, sc_, np.inf)
                for flat in np.argsort(sc_, axis=None)[:40]:
                    i, j = np.unravel_index(flat, sc_.shape)
                    if not np.isfinite(sc_[i, j]): break
                    px, py = float(X[i, j]), float(Y[i, j])
                    m = (HV[:, 0] - px) ** 2 + (HV[:, 1] - py) ** 2 < (R + 0.06) ** 2 if len(HV) else None
                    lt = float(HV[m, 2].max()) if m is not None and m.any() else z0
                    if lt + 0.02 + 1.55 * R > z1 - 0.004: continue          # no room under the ceiling here
                    best = (float(sc_[i, j]), px, py, lt); break
                if best is None: continue
                _s, px, py, lt = best; spots.append((px, py))
                ob = bpy.data.objects.new(f"c_{c['group']}_{len(copies)}_{attempt}_{kb}", T_["mesh"]); sc.collection.objects.link(ob)
                ob.rotation_euler = rand_rot(item)
                ob.location = (px, py, lt + 0.02 + R)
                add_rb(ob, "ACTIVE", "CONVEX_HULL", mass=0.4, damp=damp)
                obs.append(ob)
            if not obs: continue
            bpy.context.view_layer.update()
            # settle; drop the bad ones and settle the rest again without them (nothing may rest on a removed copy)
            ok = False
            for rnd in range(3):
                f, still, dp, dr = settle(obs)
                Ms = [o.matrix_world.copy() for o in obs]
                bad = [any(check_copy(c, key, M)) or s < 3 for M, s in zip(Ms, still)]
                SIMLOG["unsettled"] += sum(1 for s in still if s < 3)
                if not any(bad): ok = True; break
                SIMLOG["retries"] += sum(bad)
                keep = []
                for o, M, b in zip(obs, Ms, bad):
                    if b: bpy.data.objects.remove(o, do_unlink=True)
                    else: keep.append((o, M))
                obs = [o for o, _M in keep]
                if not obs: break
                sc.frame_set(1)
                for o, M in keep: o.matrix_world = M
                bpy.context.view_layer.update()
            if not ok:
                for o in obs: bpy.data.objects.remove(o, do_unlink=True)
                SIMLOG["batches_dropped"] += 1
                continue
            SIMLOG["frames"].append(f); SIMLOG["resid"].append((round(dp * 1000, 3), round(dr, 4)))
            for o in obs: o.rigid_body.type = "PASSIVE"
            for o, M in zip(obs, Ms): o.matrix_world = M
            bpy.context.view_layer.update()
            sc.frame_set(1)
            for o, M in zip(obs, Ms):
                copies.append({"item": item, "key": key, "M": M.copy(), "obj": o})
                Mn = np.array(M)
                HV = np.concatenate([HV, (T_["hv"] @ Mn[:3, :3].T + Mn[:3, 3]).astype(np.float32)])
            placed = len(obs)
            break
        fails = 0 if placed else fails + 1
    X, Y, H, Tg, mouth = surface(c, HV)
    cover = float(((Tg - H)[mouth] < slack).mean())
    SIMLOG["comps"][c["group"]] = {"item": item, "home": c["home"], "copies": len(copies), "cover": round(cover, 3),
                                   "peak": round(float(HV[:, 2].max()), 3) if len(HV) else None, "ceiling": round(z1, 3),
                                   "floor": round(z0, 3), "seconds": round(time.time() - t0, 1)}
    print("NICHE", c["group"], json.dumps(SIMLOG["comps"][c["group"]]), flush=True)
    for o in cols: bpy.data.objects.remove(o, do_unlink=True)
    return copies

# ---------- checks ----------
def interpenetration(cps):
    P = np.array([np.array(cp["M"])[:3, 3] for cp in cps]); R = np.array([TEMPL[cp["key"]]["radius"] for cp in cps])
    worst = 0.0; npairs = 0; over = []
    for i in range(len(cps)):
        d = np.linalg.norm(P - P[i], axis=1)
        for j in np.nonzero((d < R + R[i]) & (np.arange(len(cps)) > i))[0]:
            npairs += 1
            for a, b in ((i, int(j)), (int(j), i)):
                Ma, Mb = np.array(cps[a]["M"]), np.array(cps[b]["M"])
                Ta, Tb = TEMPL[cps[a]["key"]], TEMPL[cps[b]["key"]]
                x = Ta["hv"] @ Ma[:3, :3].T + Ma[:3, 3]
                xb = (x - Mb[:3, 3]) @ Mb[:3, :3]
                pl = Tb["planes"]
                m = float((pl[:, 3][None, :] - xb @ pl[:, :3].T).min(axis=1).max())
                if m > 0: over.append(m)
                worst = max(worst, m)
    return worst, npairs, over

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

def bounds_low(cp):
    M = np.array(cp["M"]); T = TEMPL[cp["key"]]
    c = M[:3, :3] @ T["mid"] + M[:3, 3]
    return float(c[2] - np.abs(M[2, :3]) @ T["he"])

def build_units(seqs):
    """cut each niche's copy sequence into its units (drop order), then interleave the 64 units by fill fraction"""
    units = []
    for ci, (c, seq) in enumerate(zip(COMPS, seqs)):
        nu = c["units"]; C = len(seq)
        assert C >= nu, (c["group"], c["item"], C, nu)
        for k_ in range(nu):
            a, b = round(k_ * C / nu), round((k_ + 1) * C / nu)
            units.append({"comp": ci, "item": c["item"], "k": k_, "frac": (k_ + 0.5) / nu + crng.uniform(-0.01, 0.01), "copies": seq[a:b]})
    units.sort(key=lambda u: (u["frac"], u["comp"]))
    for n_, u in enumerate(units): u["index"] = n_; u["step"] = n_ * 8 // NUNITS
    return units

def build_anchors(units, frame_info, checks):
    maxerr = 0; out = []
    for u in units:
        W = np.concatenate([world_verts(cp["key"], cp["M"]) for cp in u["copies"]])
        lo = Vector(tuple(float(a) for a in W.min(0))); hi = Vector(tuple(float(a) for a in W.max(0)))
        lo.z = min(lo.z, min(bounds_low(cp) for cp in u["copies"])) - 0.002
        c = (lo + hi) / 2
        cps = []
        for cp in u["copies"]:
            M = cp["M"]; eul, quat, err = rot_to_unity(M.to_3x3().normalized()); maxerr = max(maxerr, err)
            T = TEMPL[cp["key"]]
            cps.append({"item": cp["item"], "offset": [round(a, 4) for a in b2u_vec(M.translation - c)], "euler": eul, "quat_xyzw": quat,
                        "scale": round(T["s"], 5), "fit_longest_m": round(T["s"] * max(T["size"]), 4),
                        "world_position": [round(a, 4) for a in b2u_vec(M.translation)]})
        cc = COMPS[u["comp"]]
        d = {"index": u["index"], "step": u["step"], "kind": "heap_step"}
        if cc["home"]: d["item"] = cc["home"]
        else: d["example_item"] = cc["item"]
        d.update({"bin": cc["group"], "cell": [cc["col"], cc["row"]], "position": [round(a, 4) for a in b2u_vec(c)], "rotation": [0, 0, 0],
                  "box": [round(hi.x - lo.x, 4), round(hi.z - lo.z, 4), round(hi.y - lo.y, 4)], "layer": 0, "copies": cps})
        out.append(d)
    bins = []
    for ci, c in enumerate(COMPS):
        us = [u for u in units if u["comp"] == ci]
        bins.append({"bin": c["group"], "cell": [c["col"], c["row"]], "home": c["home"], "layout_item": c["item"], "units": len(us),
                     "copies": sum(len(u["copies"]) for u in us),
                     "copies_per_unit": [len(u["copies"]) for u in sorted(us, key=lambda u: u["k"])],
                     "inner_x_unity": [round(-c["x1"], 4), round(-c["x0"], 4)], "inner_z_unity": [round(-c["y1"], 4), round(-c["y0"], 4)],
                     "floor_y": round(c["z0"], 4), "ceiling_y": round(c["z1"], 4),
                     "heap_peak_y": SIMLOG["comps"][c["group"]]["peak"], "cover": SIMLOG["comps"][c["group"]]["cover"]})
    items = {}
    for key in sorted(TEMPL):
        T = TEMPL[key]
        items[key] = {"bounds_size_unity": [round(T["size"][0], 4), round(T["size"][2], 4), round(T["size"][1], 4)],
                      "bounds_center_unity": [round(a, 4) for a in b2u_vec(T["center"])], "scale_used": round(T["s"], 5),
                      "fit_longest_m": round(T["s"] * max(T["size"]), 4), "tris_per_copy_in_game": T["game_tris"]}
        if T["item"] in SPHERES:
            items[key]["note"] = ("The prefab's model is demister_ball: a MeshRenderer with Unity's built-in Sphere (default resources mesh 10207) "
                                  "at scale 0.1 (0.1 m) at the prefab root, plus ParticleSystems and a point light. The rip cannot read built-in "
                                  "meshes, so its niche was laid out with a UV-sphere stand-in of that size; the mod draws the game's own sphere "
                                  "and material (ItemVisual takes MeshRenderers and skips the ParticleSystemRenderer).")
    doc = {
        "store": "Ember Cabinet round 1: an iron-framed, glass-fronted lantern cabinet (open panes), 12 niches in 3 columns x 4 rows for 10 glowing "
                 "kinds (Wisp, Glow worm, Fader's ember, Memorial coal, Molten core, Black core, Frost core, Shield core, two orbs) and 2 spare "
                 "niches for the next glowing item; one kind per niche, heaped up to the ceiling when full",
        "slots": NUNITS, "units": len(out), "steps": 8, "stack_per_unit": 1, "frame": frame_info, "placement": "ground",
        "filter_prefabs": [c["home"] for c in COMPS if c["home"]],
        "space": "Unity prefab space, origin = footprint centre on the ground. Blender z-up/-y front -> Unity y-up/+z front: ux=-bx, uy=bz, uz=-by. "
                 "OBJ export (forward NEGATIVE_Z, up Y) writes (bx, bz, -by); Unity's importer negates x, same mapping.",
        "unit_semantics": "SETTLED: every copy has an explicit final pose from a rigid-body simulation (convex-hull items, friction 0.75, restitution 0), "
                          "dropped in batches onto the frozen earlier copies; each niche's copy sequence is cut into its units in drop order. "
                          "Each copy: the item's bounds centre at unit.position + copy.offset (= copy.world_position), rotated by copy.quat_xyzw "
                          "(or copy.euler, Unity ZXY), longest side fit_longest_m. unit.position = centre of unit.box = the bounding box of the unit's "
                          "copies, its bottom lowered to the lowest rotated-bounds corner (the never-below-the-floor lift leaves every settled copy alone).",
        "fill_order": "units are listed in fill order (interleaved over the niches); within a niche its units fill bottom up. Show the first n "
                      "copies of a unit for a partial stack. Later copies rest on earlier ones, earlier ones never move. One item kind per niche "
                      "(unit.bin = row * 3 + column, row 0 the bottom, column 0 the left as seen from the front; unit.item = the kind the niche is for). "
                      "Bins 8 and 11 (row 2 column 2, row 3 column 2) are spare: their units have no item, only example_item, the item the heap was "
                      "laid out with; they are free for any kind that has no niche or more stock than its own.",
        "bins": bins, "items": items, "checks": checks, "rotation_convert_max_err": maxerr, "units_list": out}
    return doc

# ---------- scene + frame ----------
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
atlas = build_atlas()
MAT = bpy.data.materials.new("embercabinet"); MAT.use_nodes = True
_b = MAT.node_tree.nodes["Principled BSDF"]
_t = MAT.node_tree.nodes.new("ShaderNodeTexImage"); _t.image = atlas; _t.interpolation = "Closest"
MAT.node_tree.links.new(_t.outputs["Color"], _b.inputs["Base Color"])
_b.inputs["Roughness"].default_value = 1.0; _b.inputs["Specular IOR Level"].default_value = 0.0

build_frame()
frame = join(list(PARTS), "EmberCabinet")
FV_, FT_ = tri_list(frame.data)
frame_tris = len(FT_)
fbvh = BVHTree.FromPolygons(FV_, FT_, all_triangles=True)
FVn = np.array([tuple(v) for v in FV_])
frame_size = (float(FVn[:, 0].max() - FVn[:, 0].min()), float(FVn[:, 2].max()), float(FVn[:, 1].max() - FVn[:, 1].min()))
print("FRAME tris", frame_tris, "size W H D", [round(a, 3) for a in frame_size], "x", [round(float(FVn[:, 0].min()), 3), round(float(FVn[:, 0].max()), 3)],
      "y", [round(float(FVn[:, 1].min()), 3), round(float(FVn[:, 1].max()), 3)], flush=True)

load_templates()
for key, T_ in TEMPL.items():
    print("ITEM", key, "scale", round(T_["s"], 4), "longest m", round(T_["s"] * max(T_["size"]), 3), "radius", round(T_["radius"], 3), "tris", len(T_["tris"]), "game tris", T_["game_tris"])
sc.render.fps = FPS
bpy.ops.rigidbody.world_add()
rbw = sc.rigidbody_world
rbw.substeps_per_frame = 20; rbw.solver_iterations = 40; rbw.time_scale = 1.0
rbw.point_cache.frame_start = 1; rbw.point_cache.frame_end = 400
sc.frame_start = 1; sc.frame_end = 400
t0 = time.time()
seqs = [simulate(c) for c in COMPS]
print("SIM seconds", round(time.time() - t0, 1), "retries", SIMLOG["retries"], "unsettled", SIMLOG["unsettled"], "batches dropped", SIMLOG["batches_dropped"], flush=True)
allc = [(c, cp) for c, s in zip(COMPS, seqs) for cp in s]
res = [check_copy(c, cp["key"], cp["M"]) for c, cp in allc]
nclip = sum(r[2] for r in res); nesc = sum(r[0] for r in res)
pen, npairs, over = interpenetration([cp for _c, cp in allc])
print("CLIPPING", nclip, "of", len(allc), "; ESCAPED", nesc)
print("INTERPENETRATION max", round(pen * 1000, 2), "mm over", npairs, "near pairs;", len(over), "pairs penetrate, median",
      round(float(np.median(over)) * 1000, 2) if over else 0, "mm")
units = build_units(seqs)
tris_full = sum(TEMPL[cp["key"]]["game_tris"] for _c, cp in allc)
checks = {"clipping": nclip, "of_copies": len(allc), "escaped": nesc,
          "interpenetration_max_m": round(max(pen, 0.0), 5), "retries": SIMLOG["retries"], "batches_dropped": SIMLOG["batches_dropped"],
          "contents_tris_full_in_game": tris_full, "frame_tris": frame_tris, "total_tris_full": tris_full + frame_tris,
          "per_bin": {str(k): v for k, v in SIMLOG["comps"].items()}}
frame_info = {"obj": "EmberCabinet.obj", "tris": frame_tris, "size_m": [round(a, 3) for a in frame_size], "atlas": "embercabinet_atlas.png 128x128",
              "atlas_sources": "rows 0-31 hewn timber, 32-63 x0-63 end grain, 64-79 and 112-127 dark iron: assets/bunker_r4; 32-63 x64-95 dark oiled "
                               "timber texel, x96-127 wear swatch, 80-111 dark oiled hewn strip: assets/metalpallet_r3; nothing new"}
doc = build_anchors(units, frame_info, checks)
print("UNITS", len(units), "copies per bin", {c["group"]: len(s) for c, s in zip(COMPS, seqs)}, "rot err", doc["rotation_convert_max_err"])
print("TRIS frame", frame_tris, "contents full", tris_full, "total", tris_full + frame_tris, flush=True)
json.dump(SIMLOG, open(os.path.join(OUT, "simlog.json"), "w"), indent=1)
for _c, cp in allc: bpy.data.objects.remove(cp["obj"], do_unlink=True)
bpy.ops.rigidbody.world_remove()
# files: atlas (saved) -> OBJ -> anchors last (temp file + rename)
bpy.ops.object.select_all(action="DESELECT"); frame.select_set(True); bpy.context.view_layer.objects.active = frame
bpy.ops.wm.obj_export(filepath=os.path.join(OUTA, "EmberCabinet.obj"), export_selected_objects=True, export_materials=False,
                      export_triangulated_mesh=True, forward_axis="NEGATIVE_Z", up_axis="Y")
tmp = os.path.join(OUT, "embercabinet_anchors.json.tmp")
json.dump(doc, open(tmp, "w"), indent=1)
os.replace(tmp, os.path.join(OUTA, "embercabinet_anchors.json"))
if NORENDER:
    print("DONE"); sys.exit(0)

# ---------- renders: replayed from the EXPORTED files the mod's way ----------
for o in list(bpy.data.objects): bpy.data.objects.remove(o, do_unlink=True)
C = Matrix(((-1, 0, 0), (0, 0, 1), (0, -1, 0)))
def u2b_pos(p): return Vector((-p[0], -p[2], p[1]))
def u2b_rot(q): return C.transposed() @ Quaternion((q[3], q[0], q[1], q[2])).to_matrix() @ C

def atlas_mat(png, name):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    t = m.node_tree.nodes.new("ShaderNodeTexImage"); t.image = bpy.data.images.load(png); t.interpolation = "Closest"
    m.node_tree.links.new(t.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 1.0; b.inputs["Specular IOR Level"].default_value = 0.0
    return m

def import_frame(objpath, png, dx, dy):
    before = set(bpy.data.objects)
    bpy.ops.wm.obj_import(filepath=objpath, forward_axis="NEGATIVE_Z", up_axis="Y")
    new = [o for o in bpy.data.objects if o not in before]
    m = atlas_mat(png, os.path.basename(png) + str(dx))
    for o in new:
        o.data.materials.clear(); o.data.materials.append(m); o.location = (dx, dy, 0)
    return new

def lin(c): return tuple(((x + 0.055) / 1.055) ** 2.4 if x > 0.04045 else x / 12.92 for x in c)
GLOW_STRENGTH = {"Wisp": 2.2, "FaderEmber": 2.2, "OrbFrostFire": 2.0, "OrbThunderBlood": 3.0}

def item_material(item, m, strength):
    """the item's own glow: its emission colour (normalised) times its emission map where it has one"""
    nt = m.node_tree; b = nt.nodes.get("Principled BSDF")
    e = EMIS[item][0]["emission"]; mx = max(e) or 1.0
    tint = (e[0] / mx, e[1] / mx, e[2] / mx, 1)
    mapf = EMIS[item][0]["map"]
    if mapf:
        tn = nt.nodes.new("ShaderNodeTexImage"); tn.interpolation = "Closest"
        tn.image = bpy.data.images.load(os.path.join(item_dir(item), item, mapf), check_existing=True)
        mix = nt.nodes.new("ShaderNodeMix"); mix.data_type = "RGBA"; mix.blend_type = "MULTIPLY"; mix.inputs["Factor"].default_value = 1.0
        mix.inputs["B"].default_value = tint
        nt.links.new(tn.outputs["Color"], mix.inputs["A"]); nt.links.new(mix.outputs["Result"], b.inputs["Emission Color"])
    else:
        b.inputs["Emission Color"].default_value = tint
    b.inputs["Emission Strength"].default_value = strength
    if item.startswith("Orb"):
        b.inputs["Metallic"].default_value = 0.3; b.inputs["Roughness"].default_value = 0.3

RAW = {}
def raw_mesh(item):
    if item not in RAW:
        if item in SPHERES:
            me = sphere_mesh(SPHERES[item] / 2, 24, 16, "ball_render")
            m = bpy.data.materials.new("ball_" + item); m.use_nodes = True; me.materials.append(m)
            b = m.node_tree.nodes["Principled BSDF"]
            b.inputs["Base Color"].default_value = (0.02, 0.10, 0.12, 1) if item == "Wisp" else (0.30, 0.12, 0.02, 1)
            b.inputs["Roughness"].default_value = 0.35
            e = EMIS[item][0]["emission"]; mx = max(e)
            b.inputs["Emission Color"].default_value = (e[0] / mx, e[1] / mx, e[2] / mx, 1); b.inputs["Emission Strength"].default_value = GLOW_STRENGTH[item]
            RAW[item] = (me, np.array([tuple(v.co) for v in me.vertices], np.float32), SPHERES[item])
        else:
            ob = load_one(item)[0]
            info = item_info(item)
            for m in ob.data.materials: item_material(item, m, GLOW_STRENGTH.get(item, 1.6))
            RAW[item] = (ob.data, np.array([tuple(v.co) for v in ob.data.vertices], np.float32), max(Vector(info["bounds_max"]) - Vector(info["bounds_min"])))
            bpy.data.objects.remove(ob, do_unlink=True)
    return RAW[item]

LIFTS = {}
def spawn_file(folder, obj, png, anchors, fill, dx, dy, tag):
    """a store replayed from its files: per bin its first fill x units in list order, a partial last unit, copies at
    unit.position + copy.offset, longest side fit_longest_m, the mod's never-below-the-floor lift"""
    import_frame(os.path.join(folder, obj), os.path.join(folder, png), dx, dy)
    if fill <= 0: return
    d = json.load(open(os.path.join(folder, anchors)))
    groups = {}
    for u in d["units_list"]: groups.setdefault(json.dumps(u.get("bin")), []).append(u)
    lifts = 0
    for g, us in groups.items():
        exact = fill * len(us); n_ = int(math.floor(exact + 1e-9)); part = exact - n_
        for ui, u in enumerate(us[:n_ + (1 if part > 1e-6 else 0)]):
            cps = u["copies"] if ui < n_ else u["copies"][:max(1, math.ceil(len(u["copies"]) * part))]
            floor = u["position"][1] - u["box"][1] / 2
            for cp in cps:
                mesh, Vv, longest = raw_mesh(cp["item"])
                s = cp["fit_longest_m"] / longest
                Rb = u2b_rot(cp["quat_xyzw"])
                p = u2b_pos([a + b for a, b in zip(u["position"], cp["offset"])])
                he = (Vv.max(0) - Vv.min(0)) / 2 * s; mid = (Vv.max(0) + Vv.min(0)) / 2 * s
                Rn = np.array(Rb)
                low = float((Rn @ mid)[2] + p.z - np.abs(Rn[2]) @ he)
                if low < floor - 1e-4: p.z += floor - low; lifts += 1
                ob = bpy.data.objects.new(f"{tag}_item", mesh); sc.collection.objects.link(ob)
                ob.matrix_world = Matrix.Translation(p + Vector((dx, dy, 0))) @ Rb.to_4x4() @ Matrix.Diagonal((s,) * 3 + (1,))
    LIFTS[f"{tag}@{fill}"] = lifts

pm = bpy.data.materials.new("plain"); pm.use_nodes = True
pm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.62, 0.60, 0.55, 1)
def post(x, y):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(x, y, 0.9)); p = bpy.context.active_object
    p.scale = (0.12, 0.12, 1.8); p.data.materials.append(pm); p.name = "post_1.8m"

A_ = (OUTA, "EmberCabinet.obj", "embercabinet_atlas.png", "embercabinet_anchors.json")
ROWS = {"empty": 0.0, "half": 20.0, "full": 40.0, "fam": 60.0}      # the variants stand 20 m apart along x, out of each other's pictures
spawn_file(*A_, 0.0, ROWS["empty"], 0.0, "e")
spawn_file(*A_, 0.5, ROWS["half"], 0.0, "h")
spawn_file(*A_, 1.0, ROWS["full"], 0.0, "f")
post(ROWS["full"] - 1.4, 0.2)
spawn_file(*A_, 1.0, ROWS["fam"], 0.0, "fam")
import_frame(os.path.join(REPO, "assets", "bunker_r4", "Bunker.obj"), os.path.join(REPO, "assets", "bunker_r4", "bunker_atlas.png"), ROWS["fam"] - 3.0, 0.3)
post(ROWS["fam"] + 1.1, 0.2)
print("MOD FLOOR LIFTS", LIFTS, flush=True)

world = bpy.data.worlds.new("w"); sc.world = world; world.use_nodes = True
WBG = world.node_tree.nodes["Background"]
WBG.inputs[0].default_value = (0.42, 0.45, 0.5, 1); WBG.inputs[1].default_value = 0.9
sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN")); sun.data.energy = 3.2
sun.rotation_euler = (math.radians(50), 0, math.radians(35)); sc.collection.objects.link(sun)
bpy.ops.mesh.primitive_plane_add(size=400, location=(30, 12, 0))
gm = bpy.data.materials.new("ground"); gm.use_nodes = True
gm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.16, 0.14, 0.11, 1)
bpy.context.active_object.data.materials.append(gm)
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam); sc.camera = cam
sc.render.engine = "BLENDER_EEVEE_NEXT"
sc.render.resolution_x, sc.render.resolution_y = (800, 900) if QUICK else (1200, 1350)
sc.view_settings.view_transform = "Standard"
EYE = 1.6
VIEWS = {  # name: (yaw deg, horizontal distance, eye height, target, lens, width, height)
    "empty34": (-28, 5.2, EYE, (ROWS["empty"], 0.0, 1.0), 40, None),
    "half34": (-28, 5.2, EYE, (ROWS["half"], 0.0, 1.0), 40, None),
    "full34": (-28, 5.2, EYE, (ROWS["full"], 0.0, 1.0), 40, None),
    "front": (0, 4.6, 1.2, (ROWS["full"], 0.0, 1.0), 40, None),
    "halffront": (0, 4.6, 1.2, (ROWS["half"], 0.0, 1.0), 40, None),
    "emptyfront": (0, 4.6, 1.2, (ROWS["empty"], 0.0, 1.0), 40, None),
    "closetop": (-12, 2.0, 1.55, (ROWS["full"], 0.0, 1.25), 40, None),
    "family": (-6, 8.6, 2.1, (ROWS["fam"] - 1.45, 0.2, 0.95), 35, (1600, 900)),
}
def render_views(names, suffix=""):
    for vn in names:
        if VIEWSEL and vn not in VIEWSEL: continue
        yaw, dist, hgt, tgt, lens, res = VIEWS[vn]
        t = Vector(tgt)
        cam.location = t + Vector((math.sin(math.radians(yaw)) * dist, -math.cos(math.radians(yaw)) * dist, hgt - t.z))
        cam.rotation_euler = (t - cam.location).to_track_quat("-Z", "Y").to_euler(); cam.data.lens = lens
        if res: sc.render.resolution_x, sc.render.resolution_y = (res[0] // 2, res[1] // 2) if QUICK else res
        else: sc.render.resolution_x, sc.render.resolution_y = (800, 900) if QUICK else (1200, 1350)
        sc.render.filepath = os.path.join(OUT, f"embercabinet1-{vn}{suffix}.png")
        bpy.ops.render.render(write_still=True)
        print("RENDER", vn + suffix, flush=True)
render_views(list(VIEWS))

# ---------- dusk: the glow does the lighting (a faint point light per niche for the bounce Eevee does not compute) ----------
if not VIEWSEL or "dusk" in VIEWSEL or "dusk34" in VIEWSEL:
    WBG.inputs[0].default_value = (0.02, 0.025, 0.04, 1); WBG.inputs[1].default_value = 1.0
    sun.data.energy = 0.25; sun.data.color = (0.6, 0.7, 1.0)
    GLOWCOL = {"Wisp": (0.0, 0.83, 1.0), "FaderEmber": (1.0, 0.32, 0.0), "GlowWorm": (1.0, 0.57, 0.39), "MemorialCoal": (1.0, 0.05, 0.05),
               "MoltenCore": (1.0, 0.26, 0.0), "BlackCore": (1.0, 0.0, 0.4), "FrostCore": (0.35, 0.75, 1.0), "ShieldCore": (1.0, 0.0, 0.35),
               "OrbFrostFire": (0.0, 0.25, 1.0), "OrbThunderBlood": (1.0, 0.03, 0.0)}
    for c in COMPS:
        col = GLOWCOL[c["item"]]
        ld = bpy.data.lights.new("niche", "POINT"); ld.color = col; ld.energy = 1.0; ld.shadow_soft_size = 0.05
        lo = bpy.data.objects.new("niche", ld); sc.collection.objects.link(lo)
        lo.location = (ROWS["full"] + (c["x0"] + c["x1"]) / 2, (c["y0"] + c["y1"]) / 2 - 0.05, (c["z0"] + c["z1"]) / 2 + 0.05)
    VIEWS["dusk34"] = (-28, 5.2, EYE, (ROWS["full"], 0.0, 1.0), 40, None)
    VIEWS["duskfront"] = (0, 4.6, 1.2, (ROWS["full"], 0.0, 1.0), 40, None)
    render_views(["dusk34", "duskfront"])
print("DONE")
