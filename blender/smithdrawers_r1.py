"""Smith's Drawers, round 1 (ITEMS.md section 2 #3): a chest of drawers by the forge, 1.2 m wide x 1.6 m tall, for the twelve kinds of hardware
no store takes. Seven tiers of two drawers: fourteen places for twelve kinds, one kind per drawer, two spare. A prototype of a NEW piece
(SPEC.md "What lies where": every kind its own place, never mixed, full looks full, contents visible from outside).
Run: blender -b -P smithdrawers_r1.py -- [--out DIR] [--assets DIR] [--quick] [--no-render] [--views a,b] [--cseed N] [--capscale F]
     [--scale Item:s,...]

Look: a hewn-timber carcass (end planks, a centre stile, tier rails, a three-board top slab, two hewn skids and a kick rail) with iron straps
down its front edges and over the top. Every drawer is a sheet-iron tin (floor, back, two sloped side sheets) behind a hewn front board with a
bar pull of iron (two posts and a bar) and a small label card in an iron frame. The tin is open: its side sheets fall from full height at
the back to the front board's top, so the heap shows over the front and from the side, a hardware-merchant's scoop drawer. Every drawer is
pulled about half out (0.20-0.26 m of its 0.40 m, staggered a little so the face of the chest is not a flat wall), so the contents show.
Tiers (top to bottom), clear height 0.135 / 0.14 / 0.155 / 0.165 / 0.18 / 0.21 / 0.215 m: small things on top, big and heavy below.
  tier 0 BronzeNails | IronNails        tier 1 MechanicalSpring | SharpeningStone    tier 2 AxeHead1 | AxeHead2
  tier 3 CeramicPlate | Chain          tier 4 BarrelRings | BellFragment            tier 5 CharredCogwheel | ScytheHandle
  tier 6 spare | spare                 (left to right as seen from the front; bin n = tier * 2 + column)
Spare drawers: built, pulled out and EMPTY, no units (what doesn't fit isn't drawn: a spare shows what the chest can still take; the
mod can only use a spare once it has per-kind layouts for it, see the anchors' "spare_bins").

Contents: 64 units = 12 homes: the two nails, Chain and Barrel rings 6 units each, the other eight kinds 5 (the 64 slots; "bin" = the drawer,
unit.item = the kind). Every drawer is filled copy by copy (Blender rigid bodies / Bullet, convex hulls, friction 0.75, restitution 0; batches
of four dropped onto the frozen earlier copies at the spots furthest under the target surface, settled, checked, frozen) until its target
surface is covered: from each wall's visible top (EDGE under it) rising inward at CROWN, never above the tier's own clear height (HMAX = clear -
0.034, so a full heap stops 14 mm under the rail above). A copy that leaves its drawer, leans on the invisible wall extension above a visible
top or touches the frame is taken out and its batch re-settled without it. The copy sequence is cut into the drawer's units in drop order, so
any prefix of units (and of a unit's copies) only rests on what is shown.
Items (the game's own models, ripped to C:/Users/joost/ValheimRip/items: the twelve prefabs of this store were ripped for it on 24 Oct with
the existing items_extract.py): scale per kind below (the family range is 0.45-0.5 for ore; these drawers are small, so cogwheel, nails and
spring are 0.17-0.3 of true size, the plate and axe heads 0.55-0.6). Mode: flat = the thinnest axis up (plates, rings, cogs, axe heads, the
stone), long = rods lying (chain, scythe handle), tumble = any way (nails, spring, bell fragment).
unit.position = centre of the unit's copies; unit.box = their bounding box, its bottom lowered to the lowest rotated-bounds corner.
Atlas (128 px, point filtered, 48 px per metre): hewn timber, end grain and iron rows from assets/bunker_r4, the dark oiled timber and the
wear swatch from assets/metalpallet_r3 (as treasure_r1, without the hide, cloth and leather rows); new: a sheet-iron tin strip (rows 80-95,
mid slate-grey with darker crevices, a rolled-edge line top and bottom, light worn specks) for the drawers' floors, backs and sides.
Size: carcass 1.2 x 0.5 x 1.6 m (top slab 1.26 x 0.56, 1.606 m with the strap heads); with the drawers pulled out 0.20-0.26 m the footprint is
1.26 x 0.83 m. Heap ceilings per tier (clear height - 0.034): 0.10 m (top tier) to 0.18 m (bottom).
Files: assets/smithdrawers_r1/{SmithDrawers.obj, smithdrawers_atlas.png, smithdrawers_anchors.json}, the json written last (temp file +
rename). Renders and simlog in --out (default: the scratchpad smithdrawers_r1 folder).
"""
import bpy, bmesh, sys, os, math, json, random, time
import numpy as np
from mathutils import Vector, Matrix, Euler, Quaternion
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, ".."))
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
def arg(k, d=None): return argv[argv.index(k) + 1] if k in argv else d
SCR = "C:/Users/joost/AppData/Local/Temp/claude/C--Users-joost--pai/5e4bc60b-cdfe-4638-8e29-2e507fa13cf9/scratchpad/smithdrawers_r1"
OUTA = arg("--assets", os.path.join(REPO, "assets", "smithdrawers_r1"))
OUT = arg("--out", SCR)
QUICK = "--quick" in argv
NORENDER = "--no-render" in argv
VIEWSEL = arg("--views").split(",") if "--views" in argv else None
ITEMS_DIR = "C:/Users/joost/ValheimRip/items"
sys.path.append(ITEMS_DIR)
from load_item import load_item
os.makedirs(OUTA, exist_ok=True); os.makedirs(OUT, exist_ok=True)
rng = random.Random(23)                           # frame
crng = random.Random(int(arg("--cseed", 41)))     # contents

TEX, DENS = 128, 48.0
FPS = 24
MARGIN = 0.003
EDGE, CROWN = 0.02, 0.85
GRID = 0.03
GAP = 0.006                    # colliders this far inside the iron
COVERTOL = 0.03                # a drawer counts as full when its heap is within this of the target surface over 92% of the mouth

# ---------- layout (Blender metres, z up, -y = front, origin = the carcass's footprint centre on the ground) ----------
HX, HY = 0.60, 0.25            # carcass outer half extents (1.2 x 0.5)
Z0, BOT = 0.10, 0.04           # skid height, bottom boards
DT, TOPT = 0.035, 0.05         # tier rails, top slab
ENDT, CDT = 0.04, 0.04         # end planks, centre stile
CLEAR = [0.135, 0.14, 0.155, 0.165, 0.18, 0.21, 0.215]     # clear height of each tier, top to bottom
CLEAR_BU = CLEAR[::-1]         # the same, bottom to top (tier index 0 is the TOP tier everywhere else: bin = tier * 2 + column)
BASE_BU = []                   # z of each tier's rail top (the drawer stands on it), bottom to top
_z = Z0 + BOT
for _c in CLEAR_BU: BASE_BU.append(_z); _z += _c + DT
BASE = BASE_BU[::-1]           # by tier from the top
ZTOP = BASE_BU[-1] + CLEAR_BU[-1]    # underside of the top slab
HTOT = ZTOP + TOPT
assert abs(HTOT - 1.60) < 1e-6, HTOT
COLX = (-0.29, 0.29)           # drawer column centres (left, right as seen from the front)
DW = 0.26                      # drawer outer half width (opening 0.27)
WT = 0.012                     # sheet iron
FB = 0.03                      # front board thickness
LD = 0.40                      # drawer length
LIP = 0.075                    # front board height
SLOPE = 0.13                   # the side sheets fall from full height to the lip over the front 0.13 m of the tin
PULL = [0.24, 0.20, 0.22, 0.26, 0.25, 0.21, 0.20, 0.24, 0.26, 0.22, 0.21, 0.25, 0.24, 0.23]   # how far each drawer is out (bin 0..13)
KINDS = ["BronzeNails", "IronNails", "MechanicalSpring", "SharpeningStone", "AxeHead1", "AxeHead2", "CeramicPlate", "Chain",
         "BarrelRings", "BellFragment", "CharredCogwheel", "ScytheHandle", None, None]       # bin n = tier * 2 + column
assert len(KINDS) == 14 and len(PULL) == 14
# item: (scale, mode, units, copy cap)
ITEMS = {
    "BronzeNails":      (0.17, "tumble", 6, 80),
    "IronNails":        (0.17, "tumble", 6, 80),
    "MechanicalSpring": (0.20, "long",   5, 40),
    "SharpeningStone":  (0.22, "flat",   5, 40),
    "AxeHead1":         (0.58, "flat",   5, 40),
    "AxeHead2":         (0.58, "flat",   5, 40),
    "CeramicPlate":     (0.50, "flat",   5, 40),
    "Chain":            (0.32, "long",   6, 50),
    "BarrelRings":      (0.19, "flat",   6, 40),
    "BellFragment":     (0.14, "flat",   5, 40),
    "CharredCogwheel":  (0.16, "flat",   5, 40),
    "ScytheHandle":     (0.20, "long",   5, 20),
}
if "--scale" in argv:
    for kv in arg("--scale").split(","):
        k_, v_ = kv.split(":"); s_, m_, u_, c_ = ITEMS[k_]; ITEMS[k_] = (float(v_), m_, u_, c_)
CAPSCALE = float(arg("--capscale", 1.0))

def k(v): return lambda *_a: v
def make_drawer(n):
    tier, col = divmod(n, 2)
    xc = COLX[col]; base = BASE[tier]; clear = CLEAR[tier]; pull = PULL[n]
    yf = -HY - pull; yb = yf + LD
    zb = base + 0.002; floor = zb + WT; ztop = base + clear - WT; zlip = base + LIP
    x0, x1, y0, y1 = xc - DW + WT, xc + DW - WT, yf + FB, yb - WT
    def side(y, zlip=zlip, ztop=ztop, y0=y0): return zlip + (ztop - zlip) * min(max((y - y0) / SLOPE, 0.0), 1.0)
    return dict(n=n, tier=tier, col=col, xc=xc, base=base, clear=clear, pull=pull, yf=yf, yb=yb, zb=zb, floor=floor, ztop=ztop, zlip=zlip,
                x0=x0, x1=x1, y0=y0, y1=y1, side=side, hmax=clear - 0.034, item=KINDS[n], group=n)
DRAWERS = [make_drawer(n) for n in range(14)]
COMPS = []
for d in DRAWERS:
    if d["item"] is None: continue
    s_, m_, u_, c_ = ITEMS[d["item"]]
    COMPS.append(dict(item=d["item"], group=d["n"], units=u_, x0=d["x0"], x1=d["x1"], y0=d["y0"], y1=d["y1"], floor=d["floor"],
                      top=dict(x0=d["side"], x1=d["side"], y0=k(d["zlip"]), y1=k(d["ztop"])), batch=4,
                      cap=max(u_, int(c_ * CAPSCALE)), notch=[], hmax=d["hmax"], drawer=d))
NUNITS = sum(c["units"] for c in COMPS)
assert NUNITS == 64, NUNITS
for c in COMPS:
    c["bx"] = (c["x0"] + GAP, c["x1"] - GAP, c["y0"] + GAP, c["y1"] - GAP)

# ---------- atlas ----------
TILES = {"hewn": (0, 0, 128, 32), "end0": (0, 32, 32, 32), "end1": (32, 32, 32, 32), "dark": (64, 32, 32, 32),
         "wearw": (96, 32, 32, 16), "weari": (96, 48, 32, 16), "iron": (0, 64, 128, 16), "iron2": (0, 112, 128, 16), "tin": (0, 80, 128, 16)}

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
    # sheet-iron tin (the drawers): a mid slate-grey, darker in the crevices, a rolled-edge line top and bottom, lighter worn specks
    nr = np.random.default_rng(71)
    blocky = lambda s: np.kron(nr.random((16 // s + 1, 128 // s + 1)), np.ones((s, s), np.float32))[:16, :128]
    t = blocky(8) * 0.25 + blocky(4) * 0.22 + nr.random((16, 128)) * 0.18
    img = mix(srgb((0.41, 0.42, 0.44)), srgb((0.19, 0.19, 0.21)), t)
    img[0:2] *= 0.72; img[14:16] *= 0.72
    worn = (nr.random((16, 128)) < 0.07) & (t < 0.45)
    img[worn] = mix(img[worn], np.broadcast_to(srgb((0.58, 0.58, 0.58)), img[worn].shape), np.full(worn.sum(), 0.55))
    A[80:96] = img
    im = bpy.data.images.new("smithdrawers_atlas", TEX, TEX, alpha=False)
    px = np.concatenate([np.clip(A[::-1], 0, 1), np.ones((TEX, TEX, 1), np.float32)], 2)
    im.pixels.foreach_set(px.ravel())
    im.filepath_raw = os.path.join(OUTA, "smithdrawers_atlas.png"); im.file_format = "PNG"; im.save()
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
STRIP = {"hewn": 0.75, "iron": 0.375, "tin": 0.25}       # v of each strip's bottom (bunker_r4's mapping)
STRIPH = {"hewn": 32, "iron": 16, "tin": 16}
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
    wear = "weari" if kind in ("iron", "rivet", "tin") else "wearw"
    for f in bm.faces:
        cs = [l.vert.co.copy() for l in f.loops]
        n = f.normal
        if kind in ("rivet", "dark", "card"):
            uv = texel({"rivet": "weari", "dark": "dark", "card": "wearw"}[kind], r)
            for l in f.loops: l[uvl].uv = uv
            continue
        if kind not in ("iron", "tin") and abs(n.dot(L)) > 0.9:          # end grain
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
        strip = kind if kind in ("iron", "tin") else "hewn"
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

# ---------- the chest ----------
def tin(name, lo, hi): return box(name, lo, hi, kind="tin", bevel=0, jitter=0)
def build_drawer(d):
    xc, base, clear, yf, yb = d["xc"], d["base"], d["clear"], d["yf"], d["yb"]
    zb, ztop, zlip = d["zb"], d["ztop"], d["zlip"]
    tag = f"drawer{d['n']}"
    # the tin: floor, back, two sloped side sheets (full height at the back, down to the front board's top at the front)
    tin(tag + "_floor", (xc - DW + WT, yf + FB, zb), (xc + DW - WT, yb - WT, zb + WT))
    tin(tag + "_back", (xc - DW, yb - WT, zb), (xc + DW, yb, ztop))
    for sx in (-1, 1):
        xa, xb = (xc - DW, xc - DW + WT) if sx < 0 else (xc + DW - WT, xc + DW)
        prism_x(tag + "_side", xa, xb, [(yf + FB, zb), (yb - WT, zb), (yb - WT, ztop), (yf + FB + SLOPE, ztop), (yf + FB, zlip)], L=(0, 1, 0), kind="tin", bevel=0)
    # the front board: hewn timber, a bar pull of iron on two posts, a label card in an iron frame, two rivets
    box(tag + "_front", (xc - DW, yf, zb), (xc + DW, yf + FB, zlip), bevel=0.008, jitter=0.0, L=(1, 0, 0))
    zm = (zb + zlip) / 2
    for sx in (-1, 1):
        iron(tag + "_post", (xc + sx * 0.07 - 0.007, yf - 0.034, zm - 0.007), (xc + sx * 0.07 + 0.007, yf, zm + 0.007))
    iron(tag + "_bar", (xc - 0.085, yf - 0.040, zm - 0.009), (xc + 0.085, yf - 0.028, zm + 0.009))
    iron(tag + "_labelframe", (xc + 0.125, yf - 0.006, zm - 0.022), (xc + 0.225, yf, zm + 0.022))
    box(tag + "_card", (xc + 0.133, yf - 0.009, zm - 0.015), (xc + 0.217, yf - 0.006, zm + 0.015), kind="card", bevel=0, jitter=0)
    for x in (xc - 0.235, xc - 0.185): rivet((x, yf, zm), (0, -1, 0), s=0.02)

def build_frame():
    # two hewn skids, a kick rail front and back, the bottom boards
    for sx in (-1, 1):
        xa, xb = (-HX, -HX + 0.09) if sx < 0 else (HX - 0.09, HX)
        box("skid", (xa, -HY - 0.03, 0), (xb, HY + 0.03, Z0), bevel=0.014, jitter=0.004, L=(0, 1, 0))
    box("kick", (-HX + 0.09, -HY + 0.02, 0.03), (HX - 0.09, -HY + 0.07, Z0), bevel=0.01, jitter=0.0, L=(1, 0, 0))
    box("kick", (-HX + 0.09, HY - 0.07, 0.03), (HX - 0.09, HY - 0.02, Z0), bevel=0.01, jitter=0.0, L=(1, 0, 0))
    for xa, xb in ((-HX + ENDT, -0.002), (0.002, HX - ENDT)):
        box("bottom", (xa, -HY, Z0), (xb, HY, BASE_BU[0]), bevel=0.008, jitter=0.0, L=(0, 1, 0))
    # end planks (two boards each), back boards, centre stile (one piece per tier), tier rails (two halves each)
    for sx in (-1, 1):
        xa, xb = (-HX, -HX + ENDT) if sx < 0 else (HX - ENDT, HX)
        box("end", (xa, -HY, Z0), (xb, -0.002, ZTOP), bevel=0.012, jitter=0.0, L=(0, 0, 1))
        box("end", (xa, 0.002, Z0), (xb, HY, ZTOP), bevel=0.012, jitter=0.0, L=(0, 0, 1))
    for xa, xb in ((-HX + ENDT, -0.002), (0.002, HX - ENDT)):
        box("back", (xa, HY - 0.02, Z0), (xb, HY, ZTOP), bevel=0.008, jitter=0.0, L=(0, 0, 1))
    for t in range(7):
        box("stile", (-CDT / 2, -HY, BASE_BU[t]), (CDT / 2, HY - 0.02, BASE_BU[t] + CLEAR_BU[t]), bevel=0.008, jitter=0.0, L=(0, 0, 1))
        if t < 6:
            for xa, xb in ((-HX + ENDT, -CDT / 2), (CDT / 2, HX - ENDT)):
                box("rail", (xa, -HY, BASE_BU[t] + CLEAR_BU[t]), (xb, HY - 0.02, BASE_BU[t + 1]), bevel=0.008, jitter=0.0, L=(1, 0, 0))
    # the top slab: three boards, proud on every side
    ys_ = np.linspace(-HY - 0.03, HY + 0.03, 4)
    for a, b in zip(ys_, ys_[1:]):
        box("top", (-HX - 0.03, a + 0.002, ZTOP), (HX + 0.03, b - 0.002, HTOT), bevel=0.012, jitter=0.0, L=(1, 0, 0))
    # iron: straps down the three front edges (rivets at every rail), two straps over the top, folded down the front of the slab
    W = 0.03
    for x in (-HX + 0.02, 0.0, HX - 0.02):
        iron("strap", (x - W / 2, -HY - 0.006, Z0 + 0.012), (x + W / 2, -HY, ZTOP - 0.008))
        for t in range(6):
            rivet((x, -HY - 0.006, BASE_BU[t] + CLEAR_BU[t] + DT / 2), (0, -1, 0), s=0.02)
        rivet((x, -HY - 0.006, Z0 + BOT / 2 + 0.012), (0, -1, 0), s=0.02)
        rivet((x, -HY - 0.006, ZTOP - 0.03), (0, -1, 0), s=0.02)
    for x in (-0.45, 0.45):
        iron("topstrap", (x - 0.025, -HY - 0.03, HTOT), (x + 0.025, HY + 0.03, HTOT + 0.006))
        iron("topstrap", (x - 0.025, -HY - 0.036, HTOT - 0.12), (x + 0.025, -HY - 0.03, HTOT + 0.006))
        for y in (-0.16, 0.0, 0.16): rivet((x, y, HTOT + 0.006), (0, 0, 1), s=0.02)
        rivet((x, -HY - 0.036, HTOT - 0.07), (0, -1, 0), s=0.02)
    for sx in (-1, 1):                       # foot brackets: end plank to skid, both faces of the front corners
        xo = sx * HX
        for sy in (-1, 1):
            ys = sy * (HY - 0.05)
            iron("foot", (min(xo, xo + sx * 0.006), ys - 0.02, Z0 - 0.002), (max(xo, xo + sx * 0.006), ys + 0.02, Z0 + 0.15))
            rivet((xo + sx * 0.006, ys, Z0 + 0.10), (sx, 0, 0), s=0.02)
    for d in DRAWERS: build_drawer(d)

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
    for c in COMPS:
        item = c["item"]; s = ITEMS[item][0]
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
                       "tris": [(p.vertices[0], p.vertices[i], p.vertices[i + 1]) for p in ob.data.polygons for i in range(1, len(p.vertices) - 1)]}
        TEMPL[item]["game_tris"] = len(TEMPL[item]["tris"])

def world_verts(item, M):
    Mn = np.array(M); return TEMPL[item]["V"] @ Mn[:3, :3].T + Mn[:3, 3]

def unit_axis(i):
    v = [0.0, 0.0, 0.0]; v[i] = 1.0; return Vector(v)

def align(a, b):
    """rotation taking unit vector a to unit vector b (also when they are opposite)"""
    if a.dot(b) < -0.9999:
        p = a.orthogonal().normalized(); return Matrix.Rotation(math.pi, 3, p)
    return a.rotation_difference(b).to_matrix()

def rand_rot(item):
    T = TEMPL[item]; mode = ITEMS[item][1]
    size = list(T["size"])
    r = lambda lo, hi: crng.uniform(lo, hi)
    if mode == "tumble":
        return Euler((r(0, math.tau), r(0, math.tau), r(0, math.tau)), "XYZ")
    if mode == "flat":      # the thinnest axis up (or down), a little tilt, any yaw
        i = min(range(3), key=lambda j: size[j])
        Rb = align(unit_axis(i), Vector((0, 0, 1 if crng.random() < 0.5 else -1)))
        tilt = 15
    else:                   # long: the longest axis horizontal, any roll about it, any yaw, a little tilt
        i = max(range(3), key=lambda j: size[j])
        Rb = Matrix.Rotation(r(0, math.tau), 3, "X") @ align(unit_axis(i), Vector((1, 0, 0)))
        tilt = 10
    R = (Matrix.Rotation(r(0, math.tau), 3, "Z") @ Matrix.Rotation(math.radians(r(-tilt, tilt)), 3, "X")
         @ Matrix.Rotation(math.radians(r(-tilt, tilt)), 3, "Y") @ Rb)
    return R.to_euler("XYZ")

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
    return np.minimum(v, c["floor"] + c["hmax"])

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

REASONS = {}
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
    while len(copies) < c["cap"] and fails < 12:
        X, Y, H, Tg, mouth = surface(c, HV)
        cover = float(((Tg - H)[mouth] < COVERTOL).mean())
        if cover >= 0.92: break
        ceil_ = c['floor'] + c['hmax'] + 0.004
        w_ = max(1, int(round(0.2 * max(T_['size']) * T_['s'] / GRID)))
        P_ = np.pad(H, w_, mode='edge')
        Hm = np.max([P_[a_:a_ + H.shape[0], b_:b_ + H.shape[1]] for a_ in range(2 * w_ + 1) for b_ in range(2 * w_ + 1)], axis=0)
        feas = Hm + 0.8 * min(T_['size']) * T_['s'] <= ceil_
        if not feas[mouth].any(): SIMLOG.setdefault('full_at', {})[item] = len(copies); break
        deficit = Tg - H
        nb = min(c["batch"] if R < 0.1 else 2, c["cap"] - len(copies))
        placed = 0
        for attempt in range(6):
            inset = min(R * 0.55, 0.11) + 0.01 + 0.015 * attempt
            obs = []; spots = []
            sc.frame_set(1)
            for kb in range(nb if attempt < 2 else 1):
                best = None
                okc = np.argwhere(feas & (X > x0 + inset) & (X < x1 - inset) & (Y > y0 + inset) & (Y < y1 - inset))
                for _c in range(24):
                    if len(okc) == 0: break
                    ci_, cj_ = okc[crng.randrange(len(okc))]
                    px = float(X[ci_, cj_]) + crng.uniform(-GRID / 2, GRID / 2); py = float(Y[ci_, cj_]) + crng.uniform(-GRID / 2, GRID / 2)
                    if any(xa - R < px < xb + R and ya - R < py < yb + R for xa, xb, ya, yb in notches): continue
                    i = min(max(int((px - x0) / GRID), 0), X.shape[0] - 1); j = min(max(int((py - y0) / GRID), 0), X.shape[1] - 1)
                    if not feas[i, j]: continue
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
                chk = [check_copy(c, item, M) for M in Ms]
                for ch_ in chk:
                    for nm_, v_ in zip(('escaped', 'lean', 'clip'), ch_):
                        if v_: REASONS[(item, nm_)] = REASONS.get((item, nm_), 0) + 1
                bad = [any(ch_) or s < 3 for ch_, s in zip(chk, still)]
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
    cover = float(((Tg - H)[mouth] < COVERTOL).mean())
    SIMLOG["comps"][item] = {"copies": len(copies), "cover_3cm": round(cover, 3), "peak": round(float(HV[:, 2].max()), 3) if len(HV) else None,
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
        out.append({"index": u["index"], "step": u["step"], "kind": "heap_step", "item": u["item"], "bin": cc["group"],
                    "position": [round(a, 4) for a in b2u_vec(c)], "rotation": [0, 0, 0],
                    "box": [round(hi.x - lo.x, 4), round(hi.z - lo.z, 4), round(hi.y - lo.y, 4)], "layer": 0, "copies": cps})
    bins = []
    for d in DRAWERS:
        ci = next((i for i, c in enumerate(COMPS) if c["group"] == d["n"]), None)
        e = {"bin": d["n"], "tier": d["tier"], "column": d["col"], "item": d["item"], "spare": d["item"] is None,
             "pulled_out_m": d["pull"], "clear_height_m": d["clear"], "heap_max_m": round(d["hmax"], 4),
             "inner_x_unity": [round(-d["x1"], 4), round(-d["x0"], 4)], "inner_z_unity": [round(-d["y1"], 4), round(-d["y0"], 4)],
             "floor_y": round(d["floor"], 4), "front_lip_top_y": round(d["zlip"], 4), "back_top_y": round(d["ztop"], 4)}
        if ci is not None:
            c = COMPS[ci]; us = [u for u in units if u["comp"] == ci]
            e.update({"units": len(us), "copies": sum(len(u["copies"]) for u in us),
                      "copies_per_unit": [len(u["copies"]) for u in sorted(us, key=lambda u: u["k"])],
                      "heap_peak_y": SIMLOG["comps"][c["item"]]["peak"], "cover_3cm": SIMLOG["comps"][c["item"]]["cover_3cm"]})
        else:
            e["units"] = 0
        bins.append(e)
    items = {}
    for c in COMPS:
        T = TEMPL[c["item"]]
        items[c["item"]] = {"bounds_size_unity": [round(T["size"][0], 4), round(T["size"][2], 4), round(T["size"][1], 4)],
                            "bounds_center_unity": [round(a, 4) for a in b2u_vec(T["center"])], "scale_used": round(T["s"], 5),
                            "fit_longest_m": round(T["s"] * max(T["size"]), 4), "mode": ITEMS[c["item"]][1], "tris_per_copy_in_game": T["game_tris"]}
    doc = {
        "store": "Smith's Drawers round 1: a hewn-timber chest of drawers (1.2 x 0.5 x 1.6 m, drawers pulled out to about 0.75 m deep), seven tiers of two sheet-iron "
                 "scoop drawers with timber fronts and iron bar pulls, each pulled about halfway out; one kind per drawer (12 kinds, 2 spare drawers), "
                 "heaped to the tier's clear height when full",
        "slots": NUNITS, "units": len(out), "steps": 8, "stack_per_unit": 1, "frame": frame_info,
        "space": "Unity prefab space, origin = the carcass's footprint centre on the ground (the pulled drawers reach 0.26 m in front of it). Blender z-up/-y front -> Unity y-up/+z front: "
                 "ux=-bx, uy=bz, uz=-by. OBJ export (forward NEGATIVE_Z, up Y) writes (bx, bz, -by); Unity's importer negates x, same mapping.",
        "unit_semantics": "SETTLED: every copy has an explicit final pose from a rigid-body simulation (convex-hull items, friction 0.75, restitution 0), "
                          "dropped in batches onto the frozen earlier copies; each drawer's copy sequence is cut into its units in drop order. "
                          "Each copy: the item's bounds centre at unit.position + copy.offset (= copy.world_position), rotated by copy.quat_xyzw "
                          "(or copy.euler, Unity ZXY), longest side fit_longest_m. unit.position = centre of unit.box = the bounding box of the unit's "
                          "copies, its bottom lowered to the lowest rotated-bounds corner (the never-below-the-floor lift leaves every settled copy alone). "
                          "unit.bin = the drawer, unit.item = the kind it is for (one kind per drawer).",
        "fill_order": "units are listed in fill order (interleaved over the drawers); within a drawer its units fill bottom up. Show the first n "
                      "copies of a unit for a partial stack. Later copies rest on earlier ones, earlier ones never move. One item kind per drawer; "
                      "bin = tier * 2 + column, tiers top to bottom, columns left to right as seen from the front.",
        "spare_bins": [d["n"] for d in DRAWERS if d["item"] is None],
        "spare_note": "bins 12 and 13 (the bottom tier) are built, pulled out and empty; they carry no units, so the mod's ByGroup does not see them. "
                      "To let a spare take an overflowing kind it needs unit layouts per kind (as the apothecary's per-family units), not done in round 1.",
        "bins": bins, "items": items, "checks": checks, "rotation_convert_max_err": maxerr, "units_list": out}
    return doc

# ---------- scene + frame ----------
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
atlas = build_atlas()
MAT = bpy.data.materials.new("smithdrawers"); MAT.use_nodes = True
_b = MAT.node_tree.nodes["Principled BSDF"]
_t = MAT.node_tree.nodes.new("ShaderNodeTexImage"); _t.image = atlas; _t.interpolation = "Closest"
MAT.node_tree.links.new(_t.outputs["Color"], _b.inputs["Base Color"])
_b.inputs["Roughness"].default_value = 1.0; _b.inputs["Specular IOR Level"].default_value = 0.0

build_frame()
frame = join(list(PARTS), "SmithDrawers")
FV_, FT_ = tri_list(frame.data)
frame_tris = len(FT_)
fbvh = BVHTree.FromPolygons(FV_, FT_, all_triangles=True)
FVn = np.array([tuple(v) for v in FV_])
frame_size = (float(FVn[:, 0].max() - FVn[:, 0].min()), float(FVn[:, 2].max()), float(FVn[:, 1].max() - FVn[:, 1].min()))
carcass = [v for v in FVn if v[1] > -HY - 0.04]
print("FRAME tris", frame_tris, "size W H D (drawers out)", [round(a, 3) for a in frame_size], "carcass W H", round(HX * 2 + 0.06, 3), round(HTOT + 0.006, 3), flush=True)

load_templates()
for c in COMPS:
    T_ = TEMPL[c["item"]]
    print("ITEM", c["item"], "scale", T_["s"], "longest m", round(T_["s"] * max(T_["size"]), 3), "tris", len(T_["tris"]), "bin", c["group"], "hmax", round(c["hmax"], 3))
sc.render.fps = FPS
bpy.ops.rigidbody.world_add()
rbw = sc.rigidbody_world
rbw.substeps_per_frame = 20; rbw.solver_iterations = 40; rbw.time_scale = 1.0
rbw.point_cache.frame_start = 1; rbw.point_cache.frame_end = 400
sc.frame_start = 1; sc.frame_end = 400
t0 = time.time()
seqs = [simulate(c) for c in COMPS]
print("REASONS", REASONS)
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
          "per_drawer": SIMLOG["comps"]}
frame_info = {"obj": "SmithDrawers.obj", "tris": frame_tris, "size_m": [round(a, 3) for a in frame_size], "carcass_m": [round(HX * 2 + 0.06, 3), round(HTOT + 0.006, 3), round(HY * 2 + 0.06, 3)],
              "atlas": "smithdrawers_atlas.png 128x128",
              "atlas_sources": "rows 0-31 hewn timber, 32-63 x0-63 end grain, 64-79 dark iron: assets/bunker_r4; 32-63 x64-95 dark oiled timber, "
                               "x96-127 wear swatch: assets/metalpallet_r3; rows 80-95 sheet-iron tin (new); rows 96-111 unused; rows 112-127 spare copy of the iron row"}
doc = build_anchors(units, frame_info, checks)
print("UNITS", len(units), "copies per drawer", {c["item"]: len(s) for c, s in zip(COMPS, seqs)}, "rot err", doc["rotation_convert_max_err"])
print("TRIS frame", frame_tris, "contents full", tris_full, "total", tris_full + frame_tris, flush=True)
json.dump(SIMLOG, open(os.path.join(OUT, "simlog.json"), "w"), indent=1)
for _c, cp in allc: bpy.data.objects.remove(cp["obj"], do_unlink=True)
bpy.ops.rigidbody.world_remove()
# files: atlas (saved) -> OBJ -> anchors last (temp file + rename)
bpy.ops.object.select_all(action="DESELECT"); frame.select_set(True); bpy.context.view_layer.objects.active = frame
bpy.ops.wm.obj_export(filepath=os.path.join(OUTA, "SmithDrawers.obj"), export_selected_objects=True, export_materials=False,
                      export_triangulated_mesh=True, forward_axis="NEGATIVE_Z", up_axis="Y")
tmp = os.path.join(OUT, "smithdrawers_anchors.json.tmp")
json.dump(doc, open(tmp, "w"), indent=1)
os.replace(tmp, os.path.join(OUTA, "smithdrawers_anchors.json"))
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
A_ = (OUTA, "SmithDrawers.obj", "smithdrawers_atlas.png", "smithdrawers_anchors.json")
ROWS = {"empty": 0.0, "half": 8.0, "full": 16.0, "fam": 26.0}
spawn_file(*A_, 0.0, 0.0, ROWS["empty"], "e")
spawn_file(*A_, 0.5, 0.0, ROWS["half"], "h")
spawn_file(*A_, 1.0, 0.0, ROWS["full"], "f")
post(-1.1, ROWS["full"] + 0.1)
spawn_file(*A_, 1.0, 0.0, ROWS["fam"], "fam")
import_frame(os.path.join(REPO, "assets", "bunker_r4", "Bunker.obj"), os.path.join(REPO, "assets", "bunker_r4", "bunker_atlas.png"), -3.4, ROWS["fam"] + 0.3)
post(1.2, ROWS["fam"] + 0.1)
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
    "empty34": (-28, 3.6, EYE, (0.0, ROWS["empty"] - 0.1, 0.8), 35),
    "half34": (-28, 3.6, EYE, (0.0, ROWS["half"] - 0.1, 0.8), 35),
    "full34": (-28, 3.6, EYE, (0.0, ROWS["full"] - 0.1, 0.8), 35),
    "fullstanding": (0, 3.0, EYE, (0.0, ROWS["full"] - 0.1, 0.8), 32),
    "halfstanding": (0, 3.0, EYE, (0.0, ROWS["half"] - 0.1, 0.8), 32),
    "emptystanding": (0, 3.0, EYE, (0.0, ROWS["empty"] - 0.1, 0.8), 32),
    "family": (-12, 6.2, 2.0, (-1.5, ROWS["fam"] + 0.3, 0.85), 35),
    "fullclose": (-22, 1.7, 1.55, (-0.1, ROWS["full"] - 0.2, 1.25), 32),
    "fullclose_low": (-22, 1.8, 1.25, (0.1, ROWS["full"] - 0.2, 0.55), 32),
    "halfclose": (-22, 1.7, 1.55, (-0.1, ROWS["half"] - 0.2, 1.25), 32),
    "fullside": (-62, 3.0, 1.5, (0.0, ROWS["full"] - 0.1, 0.8), 35),
}
for vn, (yaw, dist, hgt, tgt, lens) in VIEWS.items():
    if VIEWSEL and vn not in VIEWSEL: continue
    t = Vector(tgt)
    cam.location = t + Vector((math.sin(math.radians(yaw)) * dist, -math.cos(math.radians(yaw)) * dist, hgt - t.z))
    cam.rotation_euler = (t - cam.location).to_track_quat("-Z", "Y").to_euler(); cam.data.lens = lens
    sc.render.filepath = os.path.join(OUT, f"smith1-{vn}.png")
    bpy.ops.render.render(write_still=True)
    print("RENDER", vn, flush=True)
print("DONE")
