"""Treasure Hoard, round 1: a Viking-age coffer (after the Mastermyr chest: low, heavy, iron-strapped, hewn oak) standing open on
two hewn runners, its front kept low so the heap shows. Concept: scratchpad sketch7/treasure (Joost liked the idea, called the
sketch "mwah, a bit plasticky"); this round keeps its layout and fixes its colour, iron, timber and shape.
Run: blender -b -P treasure_r1.py -- [--out DIR] [--assets DIR] [--quick] [--no-render] [--views a,b] [--cseed N]

Inside, left to right as seen from the front: the Amber tray (full depth), the coin well (the big middle), and on the right the
Ruby tray (front) and the Amber Pearl tray (back). The trays are raised false floors lined with wool cloth; the coin well has a
rough hide on its floor, one corner thrown over the low front rim. One item kind per compartment (the mod's ByGroup, group key
"compartment": 0 Amber, 1 Coins, 2 Ruby, 3 Amber Pearl).

Contents: 96 units (8 x 12 container grid): Coins 48, Amber 20, Ruby 16, Amber Pearl 12 (the live server: 43 / 17 / 13 / 7
stacks). Each compartment is filled batch by batch (Blender rigid bodies / Bullet, convex hulls, friction 0.75, restitution 0;
each batch dropped onto the frozen earlier copies at the spots furthest under the target surface, settled, checked, frozen)
until its target surface is covered: from every wall's visible top (EDGE under it) rising inward at CROWN, at most CAPOVER over
the compartment's highest wall, so a full store is crowned over the low front and a half one is a low mound. The deficit rule
drops the first copies under the crown, so the heap grows as a mound from the middle. A copy that leaves its compartment, leans
on the invisible wall extension above a visible top, or touches the frame is taken out (its batch re-settled without it). The
copy sequence is then cut into the compartment's units in drop order (any prefix rests only on what is shown).
Item scale (family range, ore 0.45-0.5): Coins 0.50 (one copy = a small pile standing for ~200 coins), Amber 0.40, Ruby 0.40,
Amber Pearl 0.50. Amber Pearl: the prefab's model is a MeshRenderer with Unity's built-in Sphere (default resources mesh 10207)
at scale 0.15 under attach (y 0.088), plus a particle glow; the rip tool cannot read built-in meshes, so its tray is laid out
with a 0.15 m UV sphere stand-in and the mod draws the game's own sphere and material (ItemVisual skips the particle renderer).
unit.position = centre of the unit's copies; unit.box = their bounding box, its bottom lowered to the lowest rotated-bounds
corner (the mod's never-below-the-floor lift leaves the settled heap alone).
Atlas (128 px, point filtered, 48 px per metre): hewn timber, end grain and iron rows from assets/bunker_r4, the dark oiled
timber and the wear swatch (worn timber / worn iron for chamfers and rivet heads) from assets/metalpallet_r3; new: fur hide
(two), madder wool cloth, leather.
Files: assets/treasure_r1/{TreasureHoard.obj, treasure_atlas.png, treasure_anchors.json}, the json written last (temp file +
rename). Renders and simlog in --out (default: the scratchpad treasure1 folder).
"""
import bpy, bmesh, sys, os, math, json, random, time
import numpy as np
from mathutils import Vector, Matrix, Euler, Quaternion
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, ".."))
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
def arg(k, d=None): return argv[argv.index(k) + 1] if k in argv else d
SCR = "C:/Users/joost/AppData/Local/Temp/claude/C--Users-joost--pai/5e4bc60b-cdfe-4638-8e29-2e507fa13cf9/scratchpad/treasure1"
OUTA = arg("--assets", os.path.join(REPO, "assets", "treasure_r1"))
OUT = arg("--out", SCR)
QUICK = "--quick" in argv
NORENDER = "--no-render" in argv
VIEWSEL = arg("--views").split(",") if "--views" in argv else None
SKETCH = "C:/Users/joost/AppData/Local/Temp/claude/C--Users-joost--pai/5e4bc60b-cdfe-4638-8e29-2e507fa13cf9/scratchpad/sketch7/treasure/treasure-100.png"
ITEMS_DIR = "C:/Users/joost/ValheimRip/items"
sys.path.append(ITEMS_DIR)
from load_item import load_item
os.makedirs(OUTA, exist_ok=True); os.makedirs(OUT, exist_ok=True)
rng = random.Random(23)                           # frame
crng = random.Random(int(arg("--cseed", 31)))     # contents

TEX, DENS = 128, 48.0
FPS = 24
MARGIN = 0.003
EDGE, CROWN, CAPOVER = 0.02, 0.85, 0.08
GRID = 0.03
GAP = 0.006                    # colliders this far inside the wood

# ---------- layout (Blender metres, z up, -y = front) ----------
Z0 = 0.12                      # runner height: the chest stands on two hewn runners
FLOOR = 0.17                   # bottom boards' top
HX, HY = 1.00, 0.48            # chest outer half extents (2.0 x 0.96)
ST, WT = 0.14, 0.06            # corner stiles, wall boards
IX, IY = HX - WT, HY - WT      # wall inner faces (0.94, 0.42)
SX, SY = HX - ST, HY - ST      # stile inner faces (0.86, 0.34)
FRONT_TOP, BACK_TOP = 0.44, 0.82
def TOP(y): return FRONT_TOP + (y + HY) / (2 * HY) * (BACK_TOP - FRONT_TOP)    # side walls and stiles slope front to back
DV0, DV1 = 0.50, 0.55          # the two long dividers (|x|), level, just over the front rim
DIVTOP = 0.50
XD = 0.025                     # cross divider half thickness (Ruby | Amber Pearl till); the till's rims:
XDTOP = 0.62
TILLX = DV1 + 0.04             # the till's inner side board (x from DV1)
HIDE, CLOTH = 0.012, 0.008
TRAY = {"Amber": 0.36, "Ruby": 0.34, "AmberPearl": 0.54}     # tray floor tops (raised false floors)
SCALE = {"Coins": 0.50, "Amber": 0.40, "Ruby": 0.40, "AmberPearl": 0.50}
PEARL_SIZE, PEARL_CENTER = 0.15, (0.0, 0.0, 0.088)             # the game's sphere: 0.15 m, bounds centre (Blender item space)

def k(v): return lambda *_a: v
COMPS = [  # name, item, group, units, interior box (inside the lining), floor, visible tops of the four boundaries, batch, cap
    dict(item="Amber", group=0, units=20, x0=-IX, x1=-DV1, y0=-IY, y1=IY, floor=TRAY["Amber"] + CLOTH,
         top=dict(x0=lambda y: TOP(y), x1=k(DIVTOP), y0=k(FRONT_TOP), y1=k(BACK_TOP)), batch=4, cap=150,
         notch=[(-1, -1), (-1, 1)]),
    dict(item="Coins", group=1, units=48, x0=-DV0, x1=DV0, y0=-IY + HIDE, y1=IY, floor=FLOOR + HIDE,
         top=dict(x0=k(DIVTOP), x1=k(DIVTOP), y0=k(FRONT_TOP), y1=k(BACK_TOP)), batch=4, cap=230, notch=[]),
    dict(item="Ruby", group=2, units=16, x0=DV1, x1=IX, y0=-IY, y1=-XD, floor=TRAY["Ruby"] + CLOTH,
         top=dict(x0=k(DIVTOP), x1=lambda y: TOP(y), y0=k(FRONT_TOP), y1=k(XDTOP)), batch=4, cap=110, notch=[(1, -1)]),
    dict(item="AmberPearl", group=3, units=12, x0=TILLX, x1=IX, y0=XD, y1=IY, floor=TRAY["AmberPearl"] + CLOTH,
         top=dict(x0=k(XDTOP), x1=lambda y: TOP(y), y0=k(XDTOP), y1=k(BACK_TOP)), batch=4, cap=84, notch=[(1, 1)]),
]
CAPSCALE = float(arg("--capscale", 1.0))      # quick look: fewer copies
for c in COMPS: c["cap"] = max(c["units"], int(c["cap"] * CAPSCALE))
NUNITS = sum(c["units"] for c in COMPS)
assert NUNITS == 96
for c in COMPS:
    c["bx"] = (c["x0"] + GAP, c["x1"] - GAP, c["y0"] + GAP, c["y1"] - GAP)

# ---------- atlas ----------
TILES = {"hewn": (0, 0, 128, 32), "end0": (0, 32, 32, 32), "end1": (32, 32, 32, 32), "dark": (64, 32, 32, 32),
         "wearw": (96, 32, 32, 16), "weari": (96, 48, 32, 16), "iron": (0, 64, 128, 16),
         "fur": (0, 80, 32, 32), "fur2": (32, 80, 32, 32), "cloth": (64, 80, 32, 32), "leather": (96, 80, 32, 32),
         "iron2": (0, 112, 128, 16)}

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
    A[64:80] = B[64:80]                     # bunker dark iron
    A[112:128] = B[64:80]                   # (spare) bunker iron again
    nr = np.random.default_rng(53)
    yy, xx = np.meshgrid(np.arange(32), np.arange(32), indexing="ij")
    blocky = lambda s: np.kron(nr.random((32 // s, 32 // s)), np.ones((s, s), np.float32))
    def fur(base, dark, light, patches):
        # hair lies in strands (short streaks down the tile), darker partings between tufts, lighter tips
        t = blocky(8) * 0.20 + blocky(4) * 0.18 + nr.random((32, 32)) * 0.10
        strand = np.zeros((32, 32), np.float32)
        for _ in range(70):
            x0, y0, n = nr.integers(0, 32), nr.integers(0, 32), nr.integers(3, 8)
            v = nr.uniform(-0.35, 0.45)
            for q in range(n): strand[(y0 + q) % 32, (x0 + (q // 3)) % 32] += v
        t += strand
        part = (blocky(4) > 0.82) & (nr.random((32, 32)) < 0.6)
        t[part] += 0.55
        img = mix(base, dark, t)
        tips = (strand < -0.15) & (nr.random((32, 32)) < 0.7)
        img[tips] = mix(img[tips], np.broadcast_to(light, img[tips].shape), np.full(tips.sum(), 0.55))
        if patches:
            pm = (blocky(8) > 0.72) & (blocky(4) > 0.35)
            img[pm] = mix(img[pm], np.broadcast_to(light, img[pm].shape), np.full(pm.sum(), 0.45))
        return img
    A[80:112, 0:32] = fur(srgb((0.29, 0.25, 0.20)), srgb((0.11, 0.09, 0.07)), srgb((0.52, 0.47, 0.38)), True)
    A[80:112, 32:64] = fur(srgb((0.25, 0.21, 0.17)), srgb((0.09, 0.075, 0.06)), srgb((0.54, 0.49, 0.40)), True)
    # madder wool: dull red-brown twill, darker weave crevices, lighter worn specks
    base, dark, light = srgb((0.40, 0.21, 0.15)), srgb((0.20, 0.095, 0.07)), srgb((0.52, 0.36, 0.28))
    tw = ((xx + yy) % 4 < 2) * 0.22 + ((xx - yy) % 8 == 0) * 0.15
    t = tw + blocky(8) * 0.18 + blocky(2) * 0.10 + nr.random((32, 32)) * 0.10
    img = mix(base, dark, t)
    worn = (nr.random((32, 32)) < 0.06) & (t < 0.35)
    img[worn] = mix(img[worn], np.broadcast_to(light, img[worn].shape), np.full(worn.sum(), 0.6))
    A[80:112, 64:96] = img
    # leather (the hide's flesh side): brown with dark creases and lighter worn patches
    base, dark, light = srgb((0.36, 0.25, 0.155)), srgb((0.16, 0.10, 0.06)), srgb((0.48, 0.36, 0.24))
    t = blocky(8) * 0.22 + blocky(4) * 0.15 + nr.random((32, 32)) * 0.12
    crease = np.abs(np.sin(xx * 0.45 + 2.0 * np.sin(yy * 0.21))) < 0.12
    t[crease] += 0.5
    img = mix(base, dark, t)
    pm = (blocky(8) > 0.75) & (nr.random((32, 32)) < 0.8)
    img[pm] = mix(img[pm], np.broadcast_to(light, img[pm].shape), np.full(pm.sum(), 0.4))
    A[80:112, 96:128] = img
    im = bpy.data.images.new("treasure_atlas", TEX, TEX, alpha=False)
    px = np.concatenate([np.clip(A[::-1], 0, 1), np.ones((TEX, TEX, 1), np.float32)], 2)
    im.pixels.foreach_set(px.ravel())
    im.filepath_raw = os.path.join(OUTA, "treasure_atlas.png"); im.file_format = "PNG"; im.save()
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
STRIP = {"hewn": 0.75, "iron": 0.375}       # v of each strip's bottom (bunker_r4's mapping)
STRIPH = {"hewn": 32, "iron": 16}
COLLIDE = {}       # stile name -> its prism (for the heap colliders)

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
        if kind != "iron" and abs(n.dot(L)) > 0.9:          # end grain
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
        strip = "iron" if kind == "iron" else "hewn"
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

def box(name, lo, hi, kind="hewn", bevel=0.014, jitter=0.006, L=None, xform=None):
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

def prism_x(name, x0, x1, poly, L=(0, 1, 0), kind="hewn", bevel=0.012, xform=None):
    """a timber with a (y, z) outline (counter-clockwise seen from +x), between x0 and x1 (a sloped cheek board, a stile)"""
    bm = bmesh.new()
    A = [bm.verts.new((x0, y, z)) for y, z in poly]
    Bv = [bm.verts.new((x1, y, z)) for y, z in poly]
    bm.faces.new(Bv)
    bm.faces.new(A[::-1])
    n = len(poly)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((A[i], A[j], Bv[j], Bv[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return finish(bm, kind, L, bevel, name, xform)

def iron(name, lo, hi, xform=None):
    return box(name, lo, hi, kind="iron", bevel=0, jitter=0, xform=xform)

def rivet(pos, normal, s=0.022, h=0.008, xform=None):
    n = Vector(normal).normalized()
    p = Vector(pos) + n * (h / 2)
    half = [s / 2] * 3
    a = max(range(3), key=lambda i: abs(n[i])); half[a] = h / 2
    box("rivet", tuple(p[i] - half[i] for i in range(3)), tuple(p[i] + half[i] for i in range(3)), kind="rivet", bevel=0, jitter=0, xform=xform)

def sheet(name, P, N, thick, tile, seed, U, V, back="leather"):
    """a thin solid sheet (hide, cloth) over a grid of points P[j][i] with normals N (towards the visible side) and surface
    coordinates U, V in metres: top face in `tile` (each cell at its own offset inside the 32 px tile), back and edges leather"""
    r = random.Random(seed)
    bm = bmesh.new(); uvl = bm.loops.layers.uv.verify()
    nj, ni = len(P), len(P[0])
    Bv = [[bm.verts.new(P[j][i]) for i in range(ni)] for j in range(nj)]
    Tv = [[bm.verts.new(P[j][i] + N[j][i] * thick) for i in range(ni)] for j in range(nj)]
    allu = [u for row in U for u in row]; allv = [v for row in V for v in row]
    umin, vmin = min(allu), min(allv)
    du, dv = (max(allu) - umin) * DENS, (max(allv) - vmin) * DENS
    su, sv = min(1.0, 30.5 / max(du, 1e-4)), min(1.0, 30.5 / max(dv, 1e-4))
    ou = r.uniform(0.5, max(0.6, 31.5 - du * su)); ov = r.uniform(0.5, max(0.6, 31.5 - dv * sv))
    def put(f, us, vs, tl):
        for l, u, v in zip(f.loops, us, vs):
            l[uvl].uv = tuv(tl, ou + (u - umin) * DENS * su, ov + (v - vmin) * DENS * sv)
    for j in range(nj - 1):
        for i in range(ni - 1):
            idx = [(j, i), (j, i + 1), (j + 1, i + 1), (j + 1, i)]
            nn = sum((N[a][b] for a, b in idx), Vector())
            f = bm.faces.new([Tv[a][b] for a, b in idx])
            f.normal_update()
            if f.normal.dot(nn) < 0: f.normal_flip(); idx = idx[::-1]
            put(f, [U[a][b] for a, b in idx], [V[a][b] for a, b in idx], tile)
            g = bm.faces.new([Bv[a][b] for a, b in idx[::-1]])
            put(g, [U[a][b] for a, b in idx[::-1]], [V[a][b] for a, b in idx[::-1]], back)
    centre = sum((P[j][i] for j in range(nj) for i in range(ni)), Vector()) / (nj * ni)
    border = [(0, i) for i in range(ni)] + [(j, ni - 1) for j in range(1, nj)] + [(nj - 1, i) for i in range(ni - 2, -1, -1)] + [(j, 0) for j in range(nj - 2, 0, -1)]
    for a, b in zip(border, border[1:] + border[:1]):
        f = bm.faces.new((Bv[a[0]][a[1]], Bv[b[0]][b[1]], Tv[b[0]][b[1]], Tv[a[0]][a[1]]))
        f.normal_update()
        mid = sum((v.co for v in f.verts), Vector()) / 4
        if f.normal.dot(mid - centre) < 0: f.normal_flip()
        uv = texel(back, r)
        for l in f.loops: l[uvl].uv = uv
    return new_obj(name, bm)

def flat_sheet(name, x0, x1, y0, y1, z, thick, tile, cell=0.2, seed=0):
    nx, ny = max(1, round((x1 - x0) / cell)), max(1, round((y1 - y0) / cell))
    xs_ = np.linspace(x0, x1, nx + 1); ys_ = np.linspace(y0, y1, ny + 1)
    P = [[Vector((x, y, z)) for x in xs_] for y in ys_]
    N = [[Vector((0, 0, 1)) for _x in xs_] for _y in ys_]
    U = [[x for x in xs_] for _y in ys_]; V = [[y for _x in xs_] for y in ys_]
    return sheet(name, P, N, thick, tile, seed, U, V)

def hide_flap():
    """the hide's corner thrown over the low front rim: up the inner face, over the top, hanging down the front, left of the
    lock plate; the hanging part folds and ends raggedly"""
    xi = np.linspace(-0.50, -0.12, 7)
    rows = []        # (y, z, ny, nz) along the path, the last rows hang outside
    for z in np.linspace(FLOOR + HIDE, FRONT_TOP - 0.03, 4): rows.append((-IY, z, 1.0, 0.0, 0.0))
    rows.append((-IY, FRONT_TOP, 0.707, 0.707, 0.0))
    rows.append((-HY + 0.0, FRONT_TOP, 0.0, 1.0, 0.0))
    yo = -HY - 0.016
    rows.append((yo, FRONT_TOP, -0.707, 0.707, 0.0))
    for q in (0.25, 0.5, 0.75, 1.0): rows.append((yo, FRONT_TOP - q * 0.15, -1.0, 0.0, q))
    hang = [0.10 + 0.06 * abs(math.sin(3.1 * i + 0.7)) + 0.02 * (i % 2) for i in range(len(xi))]
    P, N, U, V = [], [], [], []
    s = 0.0; prev = None
    for (y, z, ny, nz, q) in rows:
        pr, nr_, ur, vr = [], [], [], []
        for i, x in enumerate(xi):
            zz = z
            yy = y
            xx = x
            if q > 0:
                zz = FRONT_TOP - q * hang[i]
                yy = y - q * (0.006 + 0.008 * math.sin(x * 23 + 1.3))          # folds
                xx = x - q * 0.06 * (x - xi[-1]) / (xi[0] - xi[-1])           # the left edge flares, the right stays clear of the lock
            pr.append(Vector((xx, yy, zz))); nr_.append(Vector((0, ny, nz)).normalized()); ur.append(xx)
        if prev is not None: s += (Vector((0, y, z)) - Vector((0, prev[0], prev[1]))).length
        prev = (y, z)
        P.append(pr); N.append(nr_); U.append(ur); V.append([s] * len(xi))
    return sheet("hide_flap", P, N, HIDE, "fur", 77, U, V)

def ring(name, cx, cy, cz, r=0.055, seg=10, t=0.012):
    """an iron ring hanging in the y-z plane at x = cx (a side handle), built from short square bars"""
    for k in range(seg):
        a0, a1 = 2 * math.pi * k / seg, 2 * math.pi * (k + 1) / seg
        am = (a0 + a1) / 2
        L = 2 * r * math.sin(math.pi / seg) + t * 0.6
        bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
        for v in bm.verts: v.co = Vector((v.co.x * t, v.co.y * L, v.co.z * t))
        bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(am + math.pi / 2, 3, "X"))
        bmesh.ops.translate(bm, verts=bm.verts, vec=Vector((cx, cy + r * math.cos(am), cz + r * math.sin(am))))
        finish(bm, "iron", (0, math.cos(am + math.pi / 2), math.sin(am + math.pi / 2)), 0, name)

LID = {}
def build_frame():
    # runners: two hewn timbers under the front and back walls, ends proud of the chest
    for sy in (-1, 1):
        box("runner", (-1.12, sy * HY - (0.16 if sy > 0 else 0), 0), (1.12, sy * HY + (0.16 if sy < 0 else 0), Z0), bevel=0.016, jitter=0.005)
    # bottom boards (along x, inside the walls)
    for k_ in range(3):
        y0 = -IY + k_ * (2 * IY / 3); y1 = y0 + 2 * IY / 3 - 0.004
        box("bottom", (-IX, y0, Z0), (IX, y1, FLOOR), bevel=0.008, jitter=0.0)
    # corner stiles (their tops follow the slope)
    for sx in (-1, 1):
        for sy in (-1, 1):
            ya, yb = (-HY, -SY) if sy < 0 else (SY, HY)
            poly = [(ya, Z0), (yb, Z0), (yb, TOP(yb)), (ya, TOP(ya))]
            xa, xb = (-HX, -SX) if sx < 0 else (SX, HX)
            prism_x("stile", xa, xb, poly, L=(0, 0, 1), bevel=0.016)
            COLLIDE[(sx, sy)] = (xa, xb, poly)
    # front: two boards to the low rim; back: four boards
    zf = [Z0, 0.28, FRONT_TOP]
    for a, b in zip(zf, zf[1:]): box("front", (-SX, -HY, a), (SX, -IY, b), bevel=0.012, jitter=0.004, L=(1, 0, 0))
    zb = np.linspace(Z0, BACK_TOP, 5)
    for a, b in zip(zb, zb[1:]): box("back", (-SX, IY, a), (SX, HY, b), bevel=0.012, jitter=0.004, L=(1, 0, 0))
    # sides: two boards, then a sloped cheek board
    for sx in (-1, 1):
        xa, xb = (-HX, -IX) if sx < 0 else (IX, HX)
        for a, b in zip(zf, zf[1:]): box("side", (xa, -SY, a), (xb, SY, b), bevel=0.012, jitter=0.004, L=(0, 1, 0))
        prism_x("cheek", xa, xb, [(-SY, FRONT_TOP), (SY, FRONT_TOP), (SY, TOP(SY)), (-SY, TOP(-SY))], L=(0, 1, 0))
    # long dividers (level), the cross divider and the Amber Pearl till's side board (the till: a raised tray in the back right
    # corner, as Viking chests kept a small till at one end), tray floors
    for sx in (-1, 1):
        xa, xb = (-DV1, -DV0) if sx < 0 else (DV0, DV1)
        box("divider", (xa, -IY, FLOOR), (xb, IY, DIVTOP), bevel=0.01, jitter=0.0, L=(0, 1, 0))
    box("xdivider", (DV1, -XD, TRAY["Ruby"]), (IX, XD, XDTOP), bevel=0.01, jitter=0.0, L=(1, 0, 0))
    box("tillside", (DV1, XD, TRAY["AmberPearl"] - 0.06), (TILLX, IY, XDTOP), bevel=0.01, jitter=0.0, L=(0, 1, 0))
    for item, xa, xb, ya, yb in (("Amber", -IX, -DV1, -IY, IY), ("Ruby", DV1, IX, -IY, -XD), ("AmberPearl", TILLX, IX, XD, IY)):
        zt = TRAY[item]
        xm = (xa + xb) / 2
        for p, q in ((xa, xm), (xm, xb)): box("trayfloor", (p, ya, zt - 0.045), (q, yb, zt), bevel=0.008, jitter=0.0, L=(0, 1, 0))
        flat_sheet(f"cloth_{item}", xa, xb, ya, yb, zt, CLOTH, "cloth", seed=rng.randrange(999))
    # the hide on the coin well's floor and its corner over the front rim
    xs_ = np.linspace(-DV0, DV0, 6); ys2 = np.linspace(IY, -IY, 6)
    P = [[Vector((x, y, FLOOR)) for x in xs_] for y in ys2]
    N = [[Vector((0, 0, 1)) for _x in xs_] for _y in ys2]
    sheet("hide_floor", P, N, HIDE, "fur2", 41, [[x for x in xs_] for _y in ys2], [[y for _x in xs_] for y in ys2])
    hide_flap()

    # ---- iron: only where it binds timber ----
    W = 0.045
    for sx in (-1, 1):                     # front straps binding the two front boards, folded over the rim
        x = sx * 0.62
        iron("strap", (x - W / 2, -HY - 0.006, Z0 + 0.01), (x + W / 2, -HY, FRONT_TOP))
        iron("strap", (x - W / 2, -HY - 0.006, FRONT_TOP), (x + W / 2, -IY - 0.004, FRONT_TOP + 0.006))
        for z in (0.20, 0.36): rivet((x, -HY - 0.006, z), (0, -1, 0))
        rivet((x, -HY + 0.028, FRONT_TOP + 0.006), (0, 0, 1), s=0.018)
    iron("lockplate", (-0.065, -HY - 0.007, 0.25), (0.065, -HY, 0.40))
    box("keyhole", (-0.008, -HY - 0.009, 0.29), (0.008, -HY - 0.006, 0.335), kind="dark", bevel=0, jitter=0)
    for x in (-0.045, 0.045):
        for z in (0.27, 0.38): rivet((x, -HY - 0.007, z), (0, -1, 0), s=0.018)
    for sx in (-1, 1):                     # corner brackets: stile to board, both faces
        for sy in (-1, 1):
            for zc in ((0.30,) if sy < 0 else (0.30, 0.64)):
                xo, yo = sx * HX, sy * HY
                xin = sx * (SX - 0.14)
                yin = sy * (SY - 0.14)
                iron("bracket", (min(xo, xin), min(yo, yo + sy * 0.006), zc - W / 2), (max(xo, xin), max(yo, yo + sy * 0.006), zc + W / 2))
                iron("bracket", (min(xo, xo + sx * 0.006), min(yo, yin), zc - W / 2), (max(xo, xo + sx * 0.006), max(yo, yin), zc + W / 2))
                for xr in (sx * (HX - 0.07), sx * (SX - 0.08)): rivet((xr, yo + sy * 0.006, zc), (0, sy, 0), s=0.02)
                for yr in (sy * (HY - 0.07), sy * (SY - 0.08)): rivet((xo + sx * 0.006, yr, zc), (sx, 0, 0), s=0.02)
            # foot: stile to runner
            xo = sx * HX; ys = sy * (HY - 0.07)
            iron("foot", (min(xo, xo + sx * 0.006), ys - W / 2, Z0 - 0.002), (max(xo, xo + sx * 0.006), ys + W / 2, Z0 + 0.13))
            iron("foot", (min(xo, xo + sx * 0.09), ys - W / 2, Z0), (max(xo, xo + sx * 0.09), ys + W / 2, Z0 + 0.006))
            rivet((xo + sx * 0.006, ys, Z0 + 0.08), (sx, 0, 0), s=0.02)
            rivet((xo + sx * 0.06, ys, Z0 + 0.006), (0, 0, 1), s=0.02)
    for sx in (-1, 1):                     # side strap binding the side boards and the cheek (and the cross divider), ring handle
        xo = sx * HX
        iron("sidestrap", (min(xo, xo + sx * 0.006), -W / 2, Z0 + 0.04), (max(xo, xo + sx * 0.006), W / 2, TOP(0) - 0.015))
        for z in (0.20, 0.36, 0.55): rivet((xo + sx * 0.006, 0, z), (sx, 0, 0))
        iron("staple", (min(xo + sx * 0.006, xo + sx * 0.012), -0.04, 0.40), (max(xo + sx * 0.006, xo + sx * 0.012), 0.04, 0.45))
        ring("handle", xo + sx * 0.022, 0.0, 0.40 - 0.05)
    for x in (-0.6, 0.0, 0.6):             # hinge straps binding the back boards
        iron("hinge", (x - 0.025, HY, 0.47), (x + 0.025, HY + 0.006, BACK_TOP))
        for z in (0.52, 0.64, 0.76): rivet((x, HY + 0.006, z), (0, 1, 0), s=0.02)
        iron("knuckle", (x - 0.035, HY - 0.004, BACK_TOP - 0.014), (x + 0.035, HY + 0.024, BACK_TOP + 0.012))
    for sx in (-1, 1):                     # divider nails through the front and back
        for z in (0.21, 0.36): rivet((sx * (DV0 + DV1) / 2, -HY, z), (0, -1, 0), s=0.018)
        for z in (0.30, 0.62): rivet((sx * (DV0 + DV1) / 2, HY, z), (0, 1, 0), s=0.018)

    # ---- the lid, open: built closed in its own frame (x, y back up the slope, z out), then swung back on the hinge ----
    d = Vector((0, -(2 * HY), FRONT_TOP - BACK_TOP)).normalized()          # down the slope, to the front
    n = Vector((0, d.z, -d.y))                                             # out of the closed lid (up); x, -d, n right-handed
    Bm = Matrix(((1, 0, 0, 0), (0, -d.y, n.y, 0), (0, -d.z, n.z, 0), (0, 0, 0, 1)))     # local x, y (= -d), z (= n) -> world
    hinge = Vector((0, HY, BACK_TOP))
    th_c = math.atan2(d.z, d.y); th_o = math.atan2(math.cos(math.radians(14)), math.sin(math.radians(14)))
    alpha = th_o - th_c
    alpha = (alpha + math.pi) % (2 * math.pi) - math.pi
    M = Matrix.Translation(hinge) @ Matrix.Rotation(alpha, 4, "X") @ Bm
    LL = math.hypot(2 * HY, BACK_TOP - FRONT_TOP) + 0.03
    TL = 0.05
    LID.update(alpha=math.degrees(alpha), length=LL, top=(M @ Vector((0, -LL, TL))).z)
    yb = np.linspace(-LL, 0, 5)
    for a, b in zip(yb, yb[1:]): box("lidboard", (-HX, a + 0.002, 0), (HX, b - 0.002, TL), bevel=0.012, jitter=0.004, L=(1, 0, 0), xform=M)
    for sx in (-1, 1):                     # clamp battens inside
        x = sx * 0.80
        box("batten", (x - 0.05, -LL + 0.08, -0.045), (x + 0.05, -0.05, 0), bevel=0.012, jitter=0.003, L=(0, 1, 0), xform=M)
        for yc in ((a + b) / 2 for a, b in zip(yb, yb[1:])):
            if -LL + 0.1 < yc < -0.07: rivet((x, yc, -0.045), (0, 0, -1), s=0.018, h=0.006, xform=M)
    for x in (-0.6, 0.0, 0.6):             # lid straps, round the front edge (now the top) onto the inside
        iron("lidstrap", (x - 0.025, -LL, TL), (x + 0.025, 0.0, TL + 0.006), xform=M)
        iron("lidstrap", (x - 0.025, -LL - 0.006, -0.006), (x + 0.025, -LL, TL + 0.006), xform=M)
        iron("lidstrap", (x - 0.025, -LL, -0.006), (x + 0.025, -LL + 0.08, 0.0), xform=M)
        for yc in (-0.12, -0.38, -0.64, -0.90): rivet((x, yc, TL + 0.006), (0, 0, 1), s=0.02, xform=M)
        for yc in (-0.38, -0.64): rivet((x, yc, 0.0), (0, 0, -1), s=0.016, h=0.005, xform=M)
        rivet((x, -LL + 0.05, -0.006), (0, 0, -1), s=0.018, h=0.006, xform=M)
    iron("hasp", (-0.03, -LL - 0.012, 0.0), (0.03, -LL - 0.006, 0.10), xform=M)

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
def pearl_mesh(radius, seg=24, rings=16, name="pearl"):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=rings, radius=radius)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    return me

TEMPL = {}
def load_templates():
    for c in COMPS:
        item = c["item"]; s = SCALE[item]
        if item == "AmberPearl":
            me = pearl_mesh(PEARL_SIZE / 2 * s, 16, 10, "templ_pearl")
            ob = bpy.data.objects.new("templ_AmberPearl", me); bpy.context.scene.collection.objects.link(ob)
            size, center = (PEARL_SIZE,) * 3, PEARL_CENTER
        else:
            ob = load_item(item, anchor="center")[0]
            info = json.load(open(f"{ITEMS_DIR}/{item}/info.json"))
            bmin, bmax = Vector(info["bounds_min"]), Vector(info["bounds_max"])
            size, center = tuple(bmax - bmin), tuple((bmin + bmax) / 2)
            ob.data.transform(Matrix.Diagonal((s, s, s, 1))); ob.data.update()
        ob.location = (0, 0, -50); ob.hide_render = True; ob.name = "templ_" + item
        V = np.array([tuple(v.co) for v in ob.data.vertices], np.float32)
        bm = bmesh.new(); bm.from_mesh(ob.data)
        hull = bmesh.ops.convex_hull(bm, input=bm.verts)
        planes = []
        for f in [g for g in hull["geom"] if isinstance(g, bmesh.types.BMFace)]:
            nn = f.normal.copy(); planes.append((nn.x, nn.y, nn.z, nn.dot(f.verts[0].co)))
        hv = np.array(sorted({tuple(round(q, 5) for q in v.co) for v in hull["geom"] if isinstance(v, bmesh.types.BMVert)}), np.float32)
        bm.free()
        TEMPL[item] = {"obj": ob, "mesh": ob.data, "V": V, "s": float(s), "size": tuple(size), "center": tuple(center),
                       "planes": np.array(planes, np.float32), "hv": hv, "radius": float(np.linalg.norm(V, axis=1).max()),
                       "he": (V.max(0) - V.min(0)) / 2, "mid": (V.max(0) + V.min(0)) / 2,
                       "tris": [(p.vertices[0], p.vertices[i], p.vertices[i + 1]) for p in ob.data.polygons for i in range(1, len(p.vertices) - 1)],
                       "game_tris": 768 if item == "AmberPearl" else None}
        if TEMPL[item]["game_tris"] is None: TEMPL[item]["game_tris"] = len(TEMPL[item]["tris"])

def world_verts(item, M):
    Mn = np.array(M); return TEMPL[item]["V"] @ Mn[:3, :3].T + Mn[:3, 3]

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

def notch_rects(c):
    out = []
    for sx, sy in c["notch"]:
        xa, xb, poly = COLLIDE[(sx, sy)]
        ys_ = [p[0] for p in poly]
        out.append((xa - GAP, xb + GAP, min(ys_) - GAP, max(ys_) + GAP))
    return out

def colliders(c):
    sc = bpy.context.scene
    x0, x1, y0, y1 = c["bx"]
    T, H = 0.3, 3.0
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    FL = c["floor"]
    obs = []
    for nm, sz, pos in [("floor", (x1 - x0 + 2 * T, y1 - y0 + 2 * T, T), (cx, cy, FL + 0.004 - T / 2)),
                        ("wx0", (T, y1 - y0 + 2 * T, H), (x0 - T / 2, cy, FL + H / 2)), ("wx1", (T, y1 - y0 + 2 * T, H), (x1 + T / 2, cy, FL + H / 2)),
                        ("wy0", (x1 - x0, T, H), (cx, y0 - T / 2, FL + H / 2)), ("wy1", (x1 - x0, T, H), (cx, y1 + T / 2, FL + H / 2))]:
        ob = bpy.data.objects.new(f"col_{c['item']}_{nm}", make_box_mesh(nm, sz)); ob.location = pos
        sc.collection.objects.link(ob); add_rb(ob, "PASSIVE", "BOX"); ob.hide_render = True; obs.append(ob)
    for sx, sy in c["notch"]:              # the corner stile reaching into the tray: its own shape, a little fatter
        xa, xb, poly = COLLIDE[(sx, sy)]
        bm = bmesh.new()
        for x in (xa - GAP, xb + GAP):
            for y, z in poly:
                yy = y + (GAP if y == max(p[0] for p in poly) else -GAP)
                bm.verts.new((x, yy, z + (0.004 if z > Z0 + 0.01 else 0)))
        bmesh.ops.convex_hull(bm, input=bm.verts)
        me = bpy.data.meshes.new("notch"); bm.to_mesh(me); bm.free()
        ob = bpy.data.objects.new(f"col_{c['item']}_notch", me); sc.collection.objects.link(ob)
        add_rb(ob, "PASSIVE", "CONVEX_HULL"); ob.hide_render = True; obs.append(ob)
    return obs

def in_notch(c, x, y):
    m = np.zeros(np.shape(x), bool)
    for xa, xb, ya, yb in notch_rects(c): m |= (x > xa) & (x < xb) & (y > ya) & (y < yb)
    return m

def target(c, X, Y):
    x0, x1, y0, y1 = c["bx"]; t = c["top"]
    tx0 = np.vectorize(t["x0"])(Y); tx1 = np.vectorize(t["x1"])(Y)
    v = np.minimum.reduce([tx0 - EDGE + CROWN * (X - x0), tx1 - EDGE + CROWN * (x1 - X),
                           t["y0"](0) - EDGE + CROWN * (Y - y0), t["y1"](0) - EDGE + CROWN * (y1 - Y)])
    hi = max(t["x0"](y1), t["x1"](y1), t["x0"](y0), t["x1"](y0), t["y0"](0), t["y1"](0))
    return np.minimum(v, hi + CAPOVER)

def surface(c, HV):
    x0, x1, y0, y1 = c["bx"]
    nx, ny = int(math.ceil((x1 - x0) / GRID)), int(math.ceil((y1 - y0) / GRID))
    gx = x0 + (np.arange(nx) + 0.5) * GRID; gy = y0 + (np.arange(ny) + 0.5) * GRID
    X, Y = np.meshgrid(gx, gy, indexing="ij")
    H = np.full((nx, ny), c["floor"], np.float64)
    if len(HV):
        ix = np.clip(((HV[:, 0] - x0) / GRID).astype(int), 0, nx - 1); iy = np.clip(((HV[:, 1] - y0) / GRID).astype(int), 0, ny - 1)
        np.maximum.at(H, (ix, iy), HV[:, 2])
        P = np.pad(H, 1, mode="edge")
        H = np.max([P[i:i + nx, j:j + ny] for i in range(3) for j in range(3)], axis=0)
    notch = in_notch(c, X, Y)
    mouth = (X > x0 + 0.03) & (X < x1 - 0.03) & (Y > y0 + 0.03) & (Y < y1 - 0.03) & ~notch
    Tg = target(c, X, Y)
    Tg[notch] = -1.0
    return X, Y, H, Tg, mouth

def lean_over(c, W):
    x0, x1, y0, y1 = c["bx"]; t = c["top"]
    over = -1.0
    for side, d in (("x0", W[:, 0] - x0), ("x1", x1 - W[:, 0]), ("y0", W[:, 1] - y0), ("y1", y1 - W[:, 1])):
        near = d < 0.02
        for w in W[near]: over = max(over, float(w[2]) - t[side](float(w[1])))
    return over

def check_copy(c, item, M):
    W = world_verts(item, M)
    x0, x1, y0, y1 = c["bx"]
    tol = 0.006
    escaped = bool((W[:, 0] < x0 - tol).any() or (W[:, 0] > x1 + tol).any() or (W[:, 1] < y0 - tol).any()
                   or (W[:, 1] > y1 + tol).any() or (W[:, 2] < c["floor"] - tol).any())
    lean = lean_over(c, W) > 0
    clip = bool(fbvh.overlap(BVHTree.FromPolygons([Vector(tuple(float(a) for a in w)) for w in W], TEMPL[item]["tris"])))
    return escaped, lean, clip

def rand_rot(item):
    if item == "Coins":      # a coin pile lies mostly flat
        return Euler((math.radians(crng.uniform(-25, 25)), math.radians(crng.uniform(-25, 25)), crng.uniform(0, math.tau)), "XYZ")
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
    coll = bpy.data.collections.new(f"rb_{c['item']}")
    rbw.collection = coll
    cols = colliders(c)
    item = c["item"]; T_ = TEMPL[item]; R = T_["radius"]
    x0, x1, y0, y1 = c["bx"]
    damp = (0.5, 0.95) if item == "AmberPearl" else (0.25, 0.45)
    HV = np.zeros((0, 3), np.float32)
    copies = []; fails = 0; t0 = time.time()
    notches = notch_rects(c)
    while len(copies) < c["cap"] and fails < 6:
        X, Y, H, Tg, mouth = surface(c, HV)
        cover = float(((Tg - H)[mouth] < 0.05).mean())
        if cover >= 0.92: break
        deficit = Tg - H
        nb = min(c["batch"], c["cap"] - len(copies))
        placed = 0
        for attempt in range(4):
            inset = R * 0.55 + 0.01 + 0.015 * attempt
            obs = []; spots = []
            sc.frame_set(1)
            for kb in range(nb):
                best = None
                for _c in range(20):
                    px = crng.uniform(x0 + inset, x1 - inset); py = crng.uniform(y0 + inset, y1 - inset)
                    if any(xa - R < px < xb + R and ya - R < py < yb + R for xa, xb, ya, yb in notches): continue
                    i = min(max(int((px - x0) / GRID), 0), X.shape[0] - 1); j = min(max(int((py - y0) / GRID), 0), X.shape[1] - 1)
                    s_ = -float(deficit[i, j]) + crng.uniform(0, 0.02 + 0.01 * attempt)
                    s_ += sum(0.3 for (qx, qy) in spots if (qx - px) ** 2 + (qy - py) ** 2 < (2.2 * R) ** 2)
                    if best is None or s_ < best[0]: best = (s_, px, py)
                if best is None: continue
                _s, px, py = best; spots.append((px, py))
                m = (HV[:, 0] - px) ** 2 + (HV[:, 1] - py) ** 2 < (R + 0.06) ** 2 if len(HV) else None
                lt = float(HV[m, 2].max()) if m is not None and m.any() else c["floor"]
                ob = bpy.data.objects.new(f"c_{item}_{len(copies)}_{attempt}_{kb}", T_["mesh"]); sc.collection.objects.link(ob)
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
                bad = [any(check_copy(c, item, M)) or s < 3 for M, s in zip(Ms, still)]
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
                copies.append({"item": item, "M": M.copy(), "obj": o})
                Mn = np.array(M)
                HV = np.concatenate([HV, (T_["hv"] @ Mn[:3, :3].T + Mn[:3, 3]).astype(np.float32)])
            placed = len(obs)
            break
        fails = 0 if placed else fails + 1
    X, Y, H, Tg, mouth = surface(c, HV)
    cover = float(((Tg - H)[mouth] < 0.05).mean())
    SIMLOG["comps"][item] = {"copies": len(copies), "cover_5cm": round(cover, 3), "peak": round(float(HV[:, 2].max()), 3) if len(HV) else None,
                             "target_peak": round(float(Tg[mouth].max()), 3), "floor": round(c["floor"], 3), "seconds": round(time.time() - t0, 1)}
    print("COMP", item, json.dumps(SIMLOG["comps"][item]), flush=True)
    for o in cols: bpy.data.objects.remove(o, do_unlink=True)
    return copies

# ---------- checks ----------
def interpenetration(cps):
    P = np.array([np.array(cp["M"])[:3, 3] for cp in cps]); R = np.array([TEMPL[cp["item"]]["radius"] for cp in cps])
    worst = 0.0; npairs = 0; over = []
    for i in range(len(cps)):
        d = np.linalg.norm(P - P[i], axis=1)
        for j in np.nonzero((d < R + R[i]) & (np.arange(len(cps)) > i))[0]:
            npairs += 1
            for a, b in ((i, int(j)), (int(j), i)):
                Ma, Mb = np.array(cps[a]["M"]), np.array(cps[b]["M"])
                Ta, Tb = TEMPL[cps[a]["item"]], TEMPL[cps[b]["item"]]
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
    M = np.array(cp["M"]); T = TEMPL[cp["item"]]
    c = M[:3, :3] @ T["mid"] + M[:3, 3]
    return float(c[2] - np.abs(M[2, :3]) @ T["he"])

def build_units(seqs):
    """cut each compartment's copy sequence into its units (drop order), then interleave the 96 units by fill fraction"""
    units = []
    for ci, (c, seq) in enumerate(zip(COMPS, seqs)):
        nu = c["units"]; C = len(seq)
        assert C >= nu, (c["item"], C, nu)
        for k_ in range(nu):
            a, b = round(k_ * C / nu), round((k_ + 1) * C / nu)
            units.append({"comp": ci, "item": c["item"], "k": k_, "frac": (k_ + 0.5) / nu + crng.uniform(-0.01, 0.01), "copies": seq[a:b]})
    units.sort(key=lambda u: (u["frac"], u["comp"]))
    for n_, u in enumerate(units): u["index"] = n_; u["step"] = n_ * 8 // NUNITS
    return units

def build_anchors(units, frame_info, checks):
    maxerr = 0; out = []
    for u in units:
        W = np.concatenate([world_verts(cp["item"], cp["M"]) for cp in u["copies"]])
        lo = Vector(tuple(float(a) for a in W.min(0))); hi = Vector(tuple(float(a) for a in W.max(0)))
        lo.z = min(lo.z, min(bounds_low(cp) for cp in u["copies"])) - 0.002
        c = (lo + hi) / 2
        cps = []
        for cp in u["copies"]:
            M = cp["M"]; eul, quat, err = rot_to_unity(M.to_3x3().normalized()); maxerr = max(maxerr, err)
            T = TEMPL[cp["item"]]
            cps.append({"item": cp["item"], "offset": [round(a, 4) for a in b2u_vec(M.translation - c)], "euler": eul, "quat_xyzw": quat,
                        "scale": round(T["s"], 5), "fit_longest_m": round(T["s"] * max(T["size"]), 4),
                        "world_position": [round(a, 4) for a in b2u_vec(M.translation)]})
        cc = COMPS[u["comp"]]
        out.append({"index": u["index"], "step": u["step"], "kind": "heap_step", "item": u["item"], "compartment": cc["group"],
                    "position": [round(a, 4) for a in b2u_vec(c)], "rotation": [0, 0, 0],
                    "box": [round(hi.x - lo.x, 4), round(hi.z - lo.z, 4), round(hi.y - lo.y, 4)], "layer": 0, "copies": cps})
    comps = []
    for ci, c in enumerate(COMPS):
        us = [u for u in units if u["comp"] == ci]
        x0, x1, y0, y1 = c["x0"], c["x1"], c["y0"], c["y1"]
        comps.append({"compartment": c["group"], "item": c["item"], "units": len(us), "copies": sum(len(u["copies"]) for u in us),
                      "copies_per_unit": [len(u["copies"]) for u in sorted(us, key=lambda u: u["k"])],
                      "x": [round(-x1, 4), round(-x0, 4)], "z": [round(-y1, 4), round(-y0, 4)], "floor_y": round(c["floor"], 4),
                      "heap_peak_y": SIMLOG["comps"][c["item"]]["peak"], "cover_5cm": SIMLOG["comps"][c["item"]]["cover_5cm"]})
    items = {}
    for c in COMPS:
        T = TEMPL[c["item"]]
        items[c["item"]] = {"bounds_size_unity": [round(T["size"][0], 4), round(T["size"][2], 4), round(T["size"][1], 4)],
                            "bounds_center_unity": [round(a, 4) for a in b2u_vec(T["center"])], "scale_used": round(T["s"], 5),
                            "fit_longest_m": round(T["s"] * max(T["size"]), 4), "tris_per_copy_in_game": T["game_tris"]}
    items["AmberPearl"]["note"] = ("The prefab's model is attach/model: a MeshRenderer with Unity's built-in Sphere (default resources mesh 10207) "
                                   "at scale 0.15 (0.15 m), 0.088 m up, plus a ParticleSystem glow. The rip cannot read built-in meshes, so this "
                                   "tray was laid out with a UV-sphere stand-in of that size; the mod draws the game's own sphere and material "
                                   "(ItemVisual takes MeshRenderers and skips the ParticleSystemRenderer).")
    doc = {
        "store": "Treasure Hoard round 1: an open Viking-age coffer on two hewn runners, low front; Amber tray (left), coin well (middle), "
                 "Ruby tray (right front), Amber Pearl tray (right back); one kind per compartment, heaped and crowned over the rim when full",
        "slots": NUNITS, "units": len(out), "steps": 8, "stack_per_unit": 1, "frame": frame_info,
        "space": "Unity prefab space, origin = footprint centre on the ground. Blender z-up/-y front -> Unity y-up/+z front: ux=-bx, uy=bz, uz=-by. "
                 "OBJ export (forward NEGATIVE_Z, up Y) writes (bx, bz, -by); Unity's importer negates x, same mapping.",
        "unit_semantics": "SETTLED: every copy has an explicit final pose from a rigid-body simulation (convex-hull items, friction 0.75, restitution 0), "
                          "dropped in batches onto the frozen earlier copies; each compartment's copy sequence is cut into its units in drop order. "
                          "Each copy: the item's bounds centre at unit.position + copy.offset (= copy.world_position), rotated by copy.quat_xyzw "
                          "(or copy.euler, Unity ZXY), longest side fit_longest_m. unit.position = centre of unit.box = the bounding box of the unit's "
                          "copies, its bottom lowered to the lowest rotated-bounds corner (the never-below-the-floor lift leaves every settled copy alone).",
        "fill_order": "units are listed in fill order (interleaved over the compartments); within a compartment its units fill bottom up. Show the first n "
                      "copies of a unit for a partial stack. Later copies rest on earlier ones, earlier ones never move. One item kind per compartment "
                      "(compartment 0 Amber, 1 Coins, 2 Ruby, 3 Amber Pearl).",
        "compartments": comps, "items": items, "checks": checks, "rotation_convert_max_err": maxerr, "units_list": out}
    return doc

# ---------- scene + frame ----------
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
atlas = build_atlas()
MAT = bpy.data.materials.new("treasure"); MAT.use_nodes = True
_b = MAT.node_tree.nodes["Principled BSDF"]
_t = MAT.node_tree.nodes.new("ShaderNodeTexImage"); _t.image = atlas; _t.interpolation = "Closest"
MAT.node_tree.links.new(_t.outputs["Color"], _b.inputs["Base Color"])
_b.inputs["Roughness"].default_value = 1.0; _b.inputs["Specular IOR Level"].default_value = 0.0

build_frame()
frame = join(list(PARTS), "TreasureHoard")
FV_, FT_ = tri_list(frame.data)
frame_tris = len(FT_)
fbvh = BVHTree.FromPolygons(FV_, FT_, all_triangles=True)
FVn = np.array([tuple(v) for v in FV_])
frame_size = (float(FVn[:, 0].max() - FVn[:, 0].min()), float(FVn[:, 2].max()), float(FVn[:, 1].max() - FVn[:, 1].min()))
print("FRAME tris", frame_tris, "size W H D", [round(a, 3) for a in frame_size], "lid", {k_: round(v, 3) for k_, v in LID.items()}, flush=True)

load_templates()
for c in COMPS:
    T_ = TEMPL[c["item"]]
    print("ITEM", c["item"], "scale", T_["s"], "longest m", round(T_["s"] * max(T_["size"]), 3), "tris", len(T_["tris"]), "game tris", T_["game_tris"])
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
res = [check_copy(c, cp["item"], cp["M"]) for c, cp in allc]
nclip = sum(r[2] for r in res); nesc = sum(r[0] for r in res); nlean = sum(r[1] for r in res)
pen, npairs, over = interpenetration([cp for _c, cp in allc])
print("CLIPPING", nclip, "of", len(allc), "; ESCAPED", nesc, "; LEANING over a wall top", nlean)
print("INTERPENETRATION max", round(pen * 1000, 2), "mm over", npairs, "near pairs;", len(over), "pairs penetrate, median",
      round(float(np.median(over)) * 1000, 2) if over else 0, "mm")
units = build_units(seqs)
tris_full = sum(TEMPL[cp["item"]]["game_tris"] for _c, cp in allc)
checks = {"clipping": nclip, "of_copies": len(allc), "escaped": nesc, "leaning_over_wall_top": nlean,
          "interpenetration_max_m": round(max(pen, 0.0), 5), "retries": SIMLOG["retries"], "batches_dropped": SIMLOG["batches_dropped"],
          "contents_tris_full_in_game": tris_full, "frame_tris": frame_tris, "total_tris_full": tris_full + frame_tris,
          "per_compartment": SIMLOG["comps"]}
frame_info = {"obj": "TreasureHoard.obj", "tris": frame_tris, "size_m": [round(a, 3) for a in frame_size], "atlas": "treasure_atlas.png 128x128",
              "lid": {"open_deg": round(LID["alpha"], 2), "top_m": round(LID["top"], 3)},
              "atlas_sources": "rows 0-31 hewn timber, 32-63 x0-63 end grain, 64-79 dark iron: assets/bunker_r4; 32-63 x64-95 dark oiled timber, "
                               "x96-127 wear swatch: assets/metalpallet_r3; 80-111: fur hide, spotted fur hide, madder wool cloth, leather (new)"}
doc = build_anchors(units, frame_info, checks)
print("UNITS", len(units), "copies per compartment", {c["item"]: len(s) for c, s in zip(COMPS, seqs)}, "rot err", doc["rotation_convert_max_err"])
print("TRIS frame", frame_tris, "contents full", tris_full, "total", tris_full + frame_tris, flush=True)
json.dump(SIMLOG, open(os.path.join(OUT, "simlog.json"), "w"), indent=1)
for _c, cp in allc: bpy.data.objects.remove(cp["obj"], do_unlink=True)
bpy.ops.rigidbody.world_remove()
# files: atlas (saved) -> OBJ -> anchors last (temp file + rename)
bpy.ops.object.select_all(action="DESELECT"); frame.select_set(True); bpy.context.view_layer.objects.active = frame
bpy.ops.wm.obj_export(filepath=os.path.join(OUTA, "TreasureHoard.obj"), export_selected_objects=True, export_materials=False,
                      export_triangulated_mesh=True, forward_axis="NEGATIVE_Z", up_axis="Y")
tmp = os.path.join(OUT, "treasure_anchors.json.tmp")
json.dump(doc, open(tmp, "w"), indent=1)
os.replace(tmp, os.path.join(OUTA, "treasure_anchors.json"))
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

def item_material(item, m):
    """the items at their own, darker colours: worn gold with dark flecks, honey amber over its own texture, deep ruby, an amber
    pearl; no emission"""
    nt = m.node_tree; b = nt.nodes.get("Principled BSDF")
    b.inputs["Emission Strength"].default_value = 0.0
    if item == "Coins":
        g = lin((0.85, 0.817, 0.355))                      # the game's coin colour, worn down
        gold = (g[0] * 0.58, g[1] * 0.43, g[2] * 0.62, 1)            # warm, darker: no green cast from the sky
        nz = nt.nodes.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 70.0; nz.inputs["Detail"].default_value = 6.0
        cr = nt.nodes.new("ShaderNodeValToRGB")
        cr.color_ramp.elements[0].position = 0.53; cr.color_ramp.elements[0].color = gold
        cr.color_ramp.elements[1].position = 0.62; cr.color_ramp.elements[1].color = (0.075, 0.055, 0.028, 1)
        nt.links.new(nz.outputs["Fac"], cr.inputs["Fac"]); nt.links.new(cr.outputs["Color"], b.inputs["Base Color"])
        b.inputs["Metallic"].default_value = 0.85; b.inputs["Roughness"].default_value = 0.55
    elif item == "Amber":
        for n_ in nt.nodes:
            if n_.type == "MIX": n_.inputs["B"].default_value = (0.34, 0.12, 0.01, 1)     # the game's tint, darker: honey to brown
        b.inputs["Alpha"].default_value = 1.0
        for l in list(nt.links):
            if l.to_socket == b.inputs["Alpha"]: nt.links.remove(l)
        if hasattr(m, "surface_render_method"): m.surface_render_method = "DITHERED"
        b.inputs["Roughness"].default_value = 0.32; b.inputs["Specular IOR Level"].default_value = 0.5
    elif item == "Ruby":
        b.inputs["Base Color"].default_value = (0.20, 0.006, 0.016, 1)
        b.inputs["Metallic"].default_value = 0.35; b.inputs["Roughness"].default_value = 0.18
        b.inputs["Specular IOR Level"].default_value = 0.6
    elif item == "AmberPearl":
        b.inputs["Base Color"].default_value = (0.38, 0.14, 0.025, 1)
        b.inputs["Roughness"].default_value = 0.3; b.inputs["Coat Weight"].default_value = 0.5

RAW = {}
def raw_mesh(item):
    if item not in RAW:
        if item == "AmberPearl":
            me = pearl_mesh(PEARL_SIZE / 2, 24, 16, "pearl_render")
            m = bpy.data.materials.new("pearl"); m.use_nodes = True; me.materials.append(m)
            item_material(item, m)
            RAW[item] = (me, np.array([tuple(v.co) for v in me.vertices], np.float32), PEARL_SIZE)
        else:
            ob = load_item(item, anchor="center")[0]
            info = json.load(open(f"{ITEMS_DIR}/{item}/info.json"))
            for m in ob.data.materials: item_material(item, m)
            RAW[item] = (ob.data, np.array([tuple(v.co) for v in ob.data.vertices], np.float32), max(Vector(info["bounds_max"]) - Vector(info["bounds_min"])))
            bpy.data.objects.remove(ob, do_unlink=True)
    return RAW[item]

LIFTS = {}
def spawn_file(folder, obj, png, anchors, fill, dx, dy, tag):
    """a store replayed from its files: per compartment its first fill x units in list order, a partial last unit, copies at
    unit.position + copy.offset, longest side fit_longest_m, the mod's never-below-the-floor lift"""
    import_frame(os.path.join(folder, obj), os.path.join(folder, png), dx, dy)
    if fill <= 0: return
    d = json.load(open(os.path.join(folder, anchors)))
    groups = {}
    for u in d["units_list"]: groups.setdefault(json.dumps(u.get("compartment")), []).append(u)
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

A_ = (OUTA, "TreasureHoard.obj", "treasure_atlas.png", "treasure_anchors.json")
ROWS = {"empty": 0.0, "half": 8.0, "full": 16.0, "fam": 26.0}
spawn_file(*A_, 0.0, 0.0, ROWS["empty"], "e")
spawn_file(*A_, 0.5, 0.0, ROWS["half"], "h")
spawn_file(*A_, 1.0, 0.0, ROWS["full"], "f")
post(-1.7, ROWS["full"] + 0.2)
spawn_file(*A_, 1.0, 0.0, ROWS["fam"], "fam")
import_frame(os.path.join(REPO, "assets", "bunker_r4", "Bunker.obj"), os.path.join(REPO, "assets", "bunker_r4", "bunker_atlas.png"), -3.6, ROWS["fam"] + 0.3)
post(1.6, ROWS["fam"] + 0.2)
print("MOD FLOOR LIFTS", LIFTS, flush=True)

world = bpy.data.worlds.new("w"); sc.world = world; world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.42, 0.45, 0.5, 1)
world.node_tree.nodes["Background"].inputs[1].default_value = 0.9
sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN")); sun.data.energy = 3.2
sun.rotation_euler = (math.radians(50), 0, math.radians(35)); sc.collection.objects.link(sun)
bpy.ops.mesh.primitive_plane_add(size=160, location=(0, 12, 0))
gm = bpy.data.materials.new("ground"); gm.use_nodes = True
gm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.16, 0.14, 0.11, 1)
bpy.context.active_object.data.materials.append(gm)
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam); sc.camera = cam
sc.render.engine = "BLENDER_EEVEE_NEXT"
sc.render.resolution_x, sc.render.resolution_y = (1000, 562) if QUICK else (1600, 900)
sc.view_settings.view_transform = "Standard"
EYE = 1.75
VIEWS = {  # name: (yaw deg, horizontal distance, eye height, target, lens)
    "empty34": (-30, 4.4, EYE, (0.0, ROWS["empty"], 0.6), 35),
    "half34": (-30, 4.4, EYE, (0.0, ROWS["half"], 0.6), 35),
    "full34": (-30, 4.4, EYE, (0.0, ROWS["full"], 0.6), 35),
    "standing": (0, 2.6, EYE, (0.0, ROWS["full"], 0.5), 32),
    "halfstanding": (0, 2.6, EYE, (0.0, ROWS["half"], 0.5), 32),
    "family": (-12, 8.5, 2.4, (-1.5, ROWS["fam"] + 0.3, 0.8), 35),
    "halfclose": (-10, 1.9, 1.35, (-0.25, ROWS["half"], 0.45), 32),
    "sketchview": (-33, 4.4, 2.1, (0.2, ROWS["full"], 0.62), 25),     # the sketch's own camera, for the comparison
}
for vn, (yaw, dist, hgt, tgt, lens) in VIEWS.items():
    if VIEWSEL and vn not in VIEWSEL: continue
    t = Vector(tgt)
    cam.location = t + Vector((math.sin(math.radians(yaw)) * dist, -math.cos(math.radians(yaw)) * dist, hgt - t.z))
    cam.rotation_euler = (t - cam.location).to_track_quat("-Z", "Y").to_euler(); cam.data.lens = lens
    sc.render.filepath = os.path.join(OUT, f"treasure1-{vn}.png")
    bpy.ops.render.render(write_still=True)
    print("RENDER", vn, flush=True)
# the old sketch beside the new round, same camera
if (not VIEWSEL or "sketchview" in VIEWSEL) and os.path.exists(SKETCH):
    a = load_px(SKETCH); b_ = load_px(os.path.join(OUT, "treasure1-sketchview.png"))
    if a.shape == b_.shape:
        h, w, _ = a.shape
        cmp_ = np.concatenate([a, np.ones((h, 12, 3), np.float32) * 0.1, b_], 1)
        im = bpy.data.images.new("cmp", cmp_.shape[1], h, alpha=False)
        im.pixels.foreach_set(np.concatenate([cmp_[::-1], np.ones((h, cmp_.shape[1], 1), np.float32)], 2).ravel())
        im.filepath_raw = os.path.join(OUT, "treasure1-sketch-vs-r1.png"); im.file_format = "PNG"; im.save()
        print("RENDER sketch-vs-r1", flush=True)
print("DONE")
