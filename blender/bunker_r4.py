"""Coal & Stone Bunker, round 4: the round 3 bunker made visibly load-bearing, so a second bunker can stand on top of it.
Run: blender -b -P bunker_r4.py -- [--out DIR] [--tag NAME]
Writes into assets/bunker_r4/: Bunker.obj (frame only, forward -Z, up Y, triangulated, no materials),
bunker_atlas.png (128x128, point filtered) and bunker_anchors.json (written last; same schema as round 3).

What changed against round 3 (Joost, 22 Oct: "the front has no pillars going up, so the bunker on top is held up by nothing"):
  - four full-height hewn posts at the front (both corners and each divider) and four upright posts at the back, all to one height;
  - a flat top frame: a heavy beam along the front and one along the back, a side beam over every post line, all flush on top,
    so the top box lines up with the bottom box (front sill under the front beam, a new back sill under the back beam,
    cross sills under the side beams) and the frame's bounds corners, where the mod puts its snap points, carry real timber;
  - knee braces in the upper corners of every bay opening (front) and over the sloped side caps; iron T-brackets where the
    posts meet the beams (front, back and on the outer sides), the low straps and rivets of round 3 kept;
  - kept: the low front boards in their cleats, the slanted (stepped) side and divider boards with their sloped caps, the
    leaning back plank wall (now resting against the upright back posts; the side boards close the wedge behind it).
The contents volume (bays, floor, front bound, leaning back wall plane) is unchanged, so the settled contents of round 3 are
reused as they are: the units are copied verbatim from assets/bunker_r3/bunker_anchors.json, and every lump is clip-checked
against this round's frame before the anchors are written.

Atlas and anchor convention as round 3 (Blender z up, -y front -> Unity y up, +z front: ux=-bx, uy=bz, uz=-by).
"""
import bpy, bmesh, sys, os, math, json, random
import numpy as np
from mathutils import Vector, Matrix, Euler, Quaternion
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUTA = argv[argv.index("--assets") + 1] if "--assets" in argv else os.path.normpath(os.path.join(HERE, "..", "assets", "bunker_r4"))
OUT = argv[argv.index("--out") + 1] if "--out" in argv else OUTA
TAG = argv[argv.index("--tag") + 1] if "--tag" in argv else "bunker4"
R3 = os.path.normpath(os.path.join(HERE, "..", "assets", "bunker_r3"))
ITEMS_DIR = "C:/Users/joost/ValheimRip/items"
os.makedirs(OUTA, exist_ok=True); os.makedirs(OUT, exist_ok=True)
sys.path.append(ITEMS_DIR)
from load_item import load_item
rng = random.Random(7)      # frame

TEX = 128
DENS = 48.0                                                    # px per metre, vanilla wood is 47-57
STRIP = {"hewn": 0.75, "end": 0.50, "iron": 0.375}
STRIPH = {"hewn": 32, "iron": 16}

# ---------- texture (identical to round 3) ----------
def srgb(c): return np.array(c, dtype=np.float32)
WOOD, WOOD_D = srgb((0.36, 0.29, 0.20)), srgb((0.20, 0.16, 0.11))
END, END_D = srgb((0.50, 0.42, 0.31)), srgb((0.33, 0.27, 0.19))
IRON, IRON_D = srgb((0.22, 0.21, 0.20)), srgb((0.09, 0.09, 0.09))

def build_atlas():
    nr = np.random.default_rng(3)
    img = np.full((TEX, TEX, 3), 0.5, np.float32)          # row 0 = v 0 (bottom); lower part unused
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
    im = bpy.data.images.new("bunker_atlas", TEX, TEX, alpha=False)
    px = np.concatenate([np.clip(img, 0, 1), np.ones((TEX, TEX, 1), np.float32)], 2)
    im.pixels.foreach_set(px.ravel())
    im.filepath_raw = os.path.join(OUTA, "bunker_atlas.png"); im.file_format = "PNG"; im.save()
    return im

# ---------- geometry helpers (as round 3) ----------
PARTS = []

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
    room = max(hpx / TEX - span * vscale * DENS / TEX * 0.94 - 0.012, 0)
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

def iron(name, size, pos, rot=(0, 0, 0)):
    timber(name, size, pos, kind="iron", rot=rot, jitter=0.002, bevel=0)

def rivet(pos, face):
    """small square rivet head standing 12 mm off a face; face = (axis, sign)"""
    s = [0.03, 0.03, 0.03]; s[face[0]] = 0.012
    p = list(pos); p[face[0]] += face[1] * 0.006
    iron("rivet", s, p)

# ---------- layout (contents volume identical to round 3) ----------
BW = 1.20                      # bay pitch (post centre to post centre); three bays
PXS = [-1.5 * BW, -0.5 * BW, 0.5 * BW, 1.5 * BW]
P = 0.20                       # posts are P x P
YF, YB = -0.70, 0.70           # front post centre y, back wall (leaning planks) base y
T = math.radians(8.0)          # back wall lean (top moves back)
sT, cT = math.sin(T), math.cos(T)
HF = 1.15                      # round 3 front post height: now the height where the sloped side caps meet the front posts
HB = 1.72                      # length of the leaning back wall along its axis
PITCH, PH = 0.22, 0.20         # plank pitch / height
NPL = 7
BAYS = [(PXS[i] + 0.135, PXS[i + 1] - 0.135) for i in range(3)]     # contents x bounds per bay
YF_IN = YF + 0.15              # contents front bound
Z_FLOOR_FRAME = 0.118
N_MAX = -0.115                 # contents back bound in the leaning back wall's normal coordinate
# round 4: the load-bearing box
TOP = 1.837                    # flat top of the frame (round 3's highest point, so the height stays)
BH, BD = 0.24, 0.22            # front/back top beam height and depth (heavy)
ZBOT = TOP - BH                # underside of the top beams = top of the posts
YBK = 0.935                    # upright back post / back beam / back sill centre y (outer face 1.045, round 3 reached 1.055)
SBW, SBH = 0.26, 0.20          # side top beams (over each post line) width / height

def tilt_pt(s, n):
    """Point on the leaning back wall: s along the lean, n along its outward normal. Returns (y, z)."""
    return YB + s * sT + n * cT, s * cT - n * sT

def bracket_t(sx, y_post_face, y_beam_face, sgn, xlim):
    """iron T on a front or back face: an upright plate down the post, a flat plate along the beam above it, rivets"""
    iron("bracket", (0.13, 0.016, 0.28), (sx, y_post_face + sgn * 0.008, ZBOT - 0.14))
    cx = min(max(sx, -xlim + 0.22), xlim - 0.22)
    iron("bracket", (0.44, 0.016, 0.10), (cx, y_beam_face + sgn * 0.008, ZBOT + 0.075))
    if sgn < 0:                                           # rivets on the front only (keeps the depth of round 3)
        for z in (ZBOT - 0.07, ZBOT - 0.21):
            rivet((sx, y_post_face + sgn * 0.016, z), (1, sgn))
        for dx in (-0.15, 0.15):
            rivet((cx + dx, y_beam_face + sgn * 0.016, ZBOT + 0.075), (1, sgn))

def build_frame():
    WID = PXS[-1] - PXS[0]
    LEN = WID + 0.34                                       # 3.94: sills and top beams reach the full width
    XL = LEN / 2
    # ---- posts: 4 front and 4 back, upright, to the underside of the top beams
    h = ZBOT + 0.02
    for sx in PXS:
        timber("post", (P, P, h), (sx, YF, h / 2), rot=(rng.uniform(-0.3, 0.3), rng.uniform(-0.3, 0.3), 0), jitter=0.012)
        timber("post", (P, P, h), (sx, YBK, h / 2), rot=(rng.uniform(-0.3, 0.3), rng.uniform(-0.3, 0.3), 0), jitter=0.012)
    # ---- bottom box: front sill, the round 3 back sill (seat of the leaning wall), a new back sill under the back posts,
    #      cross sills under every post line, front to back
    timber("sill", (LEN, 0.22, 0.18), (0, YF, 0.09), rot=(0, 0, rng.uniform(-0.3, 0.3)), bevel=0, jitter=0.006)
    timber("sill", (LEN - 0.10, 0.22, 0.16), (0, YB + 0.04, 0.08), rot=(0, 0, rng.uniform(-0.3, 0.3)), bevel=0, jitter=0.006)
    timber("sill", (LEN, BD, 0.18), (0, YBK, 0.09), rot=(0, 0, rng.uniform(-0.3, 0.3)), bevel=0, jitter=0.006)
    for sx in PXS:
        timber("sill", (0.22, YBK - YF + 0.20, 0.16), (sx, (YF + YBK) / 2, 0.08), bevel=0, jitter=0.006)
    # ---- top box: heavy front and back beams, a side beam over every post line, all flush on top
    timber("beam", (LEN, BD, BH), (0, YF, TOP - BH / 2), jitter=0.004)
    timber("beam", (LEN, BD, BH), (0, YBK, TOP - BH / 2), jitter=0.004)
    for sx in PXS:
        timber("topside", (SBW, YBK - YF, SBH), (sx, (YF + YBK) / 2, TOP - 0.003 - SBH / 2), jitter=0.004)
    # ---- floor slats under each bay (as round 3)
    for (xl, xr) in BAYS:
        n = 5
        for k in range(n):
            xs = xl + (k + 0.5) * (xr - xl) / n
            timber("slat", (0.17, 1.26, 0.10), (xs, 0.03, 0.06), bevel=0, jitter=0.006)
    # ---- back wall: leaning planks (as round 3, but ending inside the side walls now that no leaning post covers their
    #      ends) plus one more row that tucks under the back beam
    for i in range(NPL + 1):
        s = 0.11 + PITCH * i
        y, z = tilt_pt(s, -0.04)
        timber("backplank", (WID - 0.04, 0.10, PH), (0, y, z),          # ends hidden in the outer side walls
               rot=(-math.degrees(T) + rng.uniform(-0.6, 0.6), 0, rng.uniform(-0.4, 0.4)))
    # ---- side walls and dividers: planks run front-back, top edge steps up to the back (the round 3 slope),
    #      now running on to the upright back post so the wedge behind the leaning wall is closed
    by_, bz_ = tilt_pt(HB, 0)
    slope = (bz_ + 0.05 - (HF + 0.05)) / (by_ - YF)
    walls = [(PXS[0] + 0.04, 0.10), (PXS[1], 0.16), (PXS[2], 0.16), (PXS[3] - 0.04, 0.10)]
    y1 = YBK - P / 2 + 0.05
    for sx, th in walls:
        for i in range(NPL):
            zc = 0.11 + PITCH * i
            top = zc + PH / 2
            y0 = YF if top <= HF else YF + (top - HF) / slope
            if y1 - y0 < 0.12: continue
            timber("sideplank", (th, y1 - y0, PH), (sx, (y0 + y1) / 2, zc), rot=(0, rng.uniform(-0.4, 0.4), 0))
    # sloped caps over the four walls: same line as round 3, from the front post up into the side top beam
    ya, za = YF, HF + 0.05
    yb = YBK - P / 2 + 0.04
    zb = za + slope * (yb - ya)
    ang = math.degrees(math.atan2(zb - za, yb - ya))
    ln = math.hypot(yb - ya, zb - za) + 0.08
    for sx in PXS:
        timber("cap", (P + 0.04, ln, 0.11), ((sx, (ya + yb) / 2, (za + zb) / 2)), rot=(ang, 0, rng.uniform(-0.3, 0.3)))
    # ---- knee braces: upper corners of every bay opening (front), and over each sloped cap (side), into post and beam
    KB = 0.35
    for sx in PXS:
        for d in (-1, 1):
            if abs(sx + d * 0.3) > PXS[-1]: continue          # no brace outside the end posts
            x0, z0 = sx + d * P / 2, ZBOT - KB
            timber("brace", (KB * math.sqrt(2) + 0.10, 0.12, 0.12), (x0 + d * KB / 2, YF, z0 + KB / 2),
                   rot=(0, -45 * d, 0), jitter=0.006, bevel=0.016)
        y0, z0 = YF + P / 2, ZBOT - 0.27
        timber("brace", (0.12, 0.27 * math.sqrt(2) + 0.08, 0.12), (sx, y0 + 0.135, z0 + 0.135),
               rot=(45, 0, 0), jitter=0.006, bevel=0.016)
    # ---- front board slots and boards (as round 3)
    for i in range(3):
        xa, xb = PXS[i], PXS[i + 1]
        for cx in (xa + P / 2 + 0.02, xb - P / 2 - 0.02):
            for dy in (-0.06, 0.06):
                timber("cleat", (0.04, 0.04, 0.88), (cx, YF + dy, 0.55), jitter=0.004, bevel=0)
        bx = (xa + xb) / 2
        lift = 0.15 if i == 2 else 0.0         # right bay: top board pulled half out of its slot
        for j in range(3):
            zc = 0.11 + 0.22 * j + 0.1 + (lift if j == 2 else 0)
            timber("board", (BW - P + 0.03, 0.08, PH), (bx, YF, zc), jitter=0.012, bevel=0.016,
                   rot=(0, rng.uniform(-0.3, 0.3), rng.uniform(-0.5, 0.5) + (2.5 if (j == 2 and lift) else 0)))
            if j == 2:
                iron("pull", (0.10, 0.025, 0.06), (bx, YF - 0.055, zc))
    # ---- iron
    yfp, yfb = YF - P / 2, YF - BD / 2                     # front faces of post and beam
    ybp, ybb = YBK + P / 2, YBK + BD / 2                   # back faces
    for sx in PXS:
        # round 3: band where the sloped cap meets the front post, two straps low on the front post, rivets
        timber("band", (P + 0.04, P + 0.04, 0.08), (sx, YF, HF + 0.02), kind="iron", jitter=0.003, bevel=0.006)
        iron("strap", (P + 0.05, 0.02, 0.14), (sx, yfp - 0.008, 0.30))
        iron("strap", (P + 0.05, 0.02, 0.14), (sx, yfp - 0.008, 0.80))
        for dx in (-0.06, 0.06):
            rivet((sx + dx, yfp - 0.018, 0.30), (1, -1))
        # round 4: T-brackets where the posts meet the top beams, front and back
        bracket_t(sx, yfp, yfb, -1, XL - 0.04)
        bracket_t(sx, ybp, ybb, +1, XL - 0.04)
        iron("strap", (P + 0.05, 0.02, 0.14), (sx, ybp + 0.008, 0.30))
    # outer sides of the four corner posts: an upright plate under the beam and a flat plate on the side top beam
    for sx in (PXS[0], PXS[-1]):
        sg = 1 if sx > 0 else -1
        for yp, d in ((YF, 1), (YBK, -1)):
            iron("bracket", (0.016, 0.13, 0.28), (sx + sg * (P / 2 + 0.008), yp, ZBOT - 0.14))
            iron("bracket", (0.016, 0.36, 0.09), (sx + sg * (SBW / 2 + 0.008), yp + d * (BD / 2 + 0.20), TOP - 0.003 - SBH / 2))
            for dy in (0.10, 0.28):
                rivet((sx + sg * (SBW / 2 + 0.016), yp + d * (BD / 2 + dy), TOP - 0.003 - SBH / 2), (0, sg))
    # long iron straps over the back wall planks (one per bay centre, as round 3)
    for sx in [(PXS[i] + PXS[i + 1]) / 2 for i in range(3)]:
        y, z = tilt_pt(0.65, 0.07)
        iron("backstrap", (0.10, 0.02, 1.0), (sx, y, z), rot=(-math.degrees(T), 0, 0))


# ---------- real item models (render and clip check only; never exported) ----------
TPL = {}
def load_templates(names):
    for nm in sorted(set(names)):
        objs = [o for o in load_item(nm, anchor="center") if o.type == "MESH"]
        o = objs[0]
        V = np.array([v.co[:] for v in o.data.vertices], dtype=np.float64)
        ctr = (V.min(0) + V.max(0)) / 2
        o.data.transform(Matrix.Translation(-Vector(ctr)))          # exact bounds centre at the origin (as round 3)
        V = V - ctr
        F = [tuple(p.vertices) for p in o.data.polygons]
        TPL[nm] = dict(mesh=o.data, V=V, F=F)
        for x in objs: bpy.data.objects.remove(x, do_unlink=True)

C = Matrix(((-1, 0, 0), (0, 0, 1), (0, -1, 0)))
Cinv = C.inverted()
def b_vec(u): return Vector((-u[0], -u[2], u[1]))                  # Unity -> Blender

def lumps_from_anchors(units):
    """rebuild every lump's Blender pose from the anchors (inverse of round 3's export)"""
    out = []
    for u in units:
        ctr = b_vec(u["position"])
        for c in u["copies"]:
            q = c["rot_quat"]
            Ru = Quaternion((q[3], q[0], q[1], q[2])).to_matrix()
            out.append(dict(item=u["render_item"], unit=u["index"], bay=u["bay"], loc=ctr + b_vec(c["offset"]),
                            rot=(Cinv @ Ru @ C).normalized(), s=c["scale"]))
    return out

def lump_world(L):
    M = Matrix.Translation(L["loc"]) @ L["rot"].to_4x4() @ Matrix.Diagonal((L["s"],) * 3 + (1,))
    return M, [M @ Vector(v) for v in TPL[L["item"]]["V"]]

def nrm(y, z): return (y - YB) * cT - z * sT

def bvh_of_mesh_list(items):
    V, F = [], []
    for vs, ps in items:
        base = len(V); V += vs
        for p in ps: F.append(tuple(base + i for i in p))
    return BVHTree.FromPolygons(V, F)

def inside(bvh, p):
    votes = 0
    for dv in (Vector((0.31, 0.47, 0.83)), Vector((-0.52, 0.21, 0.71)), Vector((0.12, -0.63, 0.55))):
        d = dv.normalized(); n = 0; o = p.copy()
        while True:
            h = bvh.ray_cast(o, d)
            if h[0] is None: break
            n += 1; o = h[0] + d * 1e-4
        votes += n % 2
    return votes >= 2

def tris(obs): return sum(len(p.vertices) - 2 for o in obs for p in o.data.polygons)

def join(obs, name):
    bpy.ops.object.select_all(action="DESELECT")
    for o in obs: o.select_set(True)
    bpy.context.view_layer.objects.active = obs[0]
    bpy.ops.object.join(); ob = bpy.context.active_object; ob.name = name
    return ob

# ---------- scene ----------
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
atlas = build_atlas()
def atlas_mat(name, img):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; bsdf = nt.nodes["Principled BSDF"]
    ti = nt.nodes.new("ShaderNodeTexImage"); ti.image = img; ti.interpolation = "Closest"
    nt.links.new(ti.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.8
    return m
MAT = atlas_mat("bunker", atlas)

R3J = json.load(open(os.path.join(R3, "bunker_anchors.json")))
UNITS = R3J["units"]
load_templates([u["render_item"] for u in UNITS])
LUMPS = lumps_from_anchors(UNITS)

# ---- 1. frame: build, export ----
rng.seed(7); PARTS.clear()
build_frame()
FRAME = [([v.co.copy() for v in o.data.vertices], [tuple(p.vertices) for p in o.data.polygons]) for o in PARTS]
fb = bvh_of_mesh_list(FRAME)
frame_tris = tris(PARTS)
allv = [v for vs, _ in FRAME for v in vs]
lo = Vector([min(v[i] for v in allv) for i in range(3)]); hi = Vector([max(v[i] for v in allv) for i in range(3)])
print("BUNKER frame_tris", frame_tris, "bounds blender lo", tuple(round(c, 4) for c in lo), "hi", tuple(round(c, 4) for c in hi),
      "W x H x D %.3f x %.3f x %.3f" % (hi.x - lo.x, hi.z - lo.z, hi.y - lo.y))
bpy.ops.object.select_all(action="DESELECT")
for o in PARTS: o.select_set(True)
bpy.ops.wm.obj_export(filepath=os.path.join(OUTA, "Bunker.obj"), export_selected_objects=True, export_materials=False,
                      export_triangulated_mesh=True, forward_axis="NEGATIVE_Z", up_axis="Y")
from collections import Counter
ct = Counter()
for o in PARTS: ct[o.name.split(".")[0]] += tris([o])
print("TRIS", dict(ct))
for o in PARTS: bpy.data.objects.remove(o, do_unlink=True)
PARTS.clear()

# ---- 2. clip check: every reused lump against this round's frame ----
bad = []
for k, L in enumerate(LUMPS):
    _, W = lump_world(L)
    ib = BVHTree.FromPolygons([tuple(w) for w in W], TPL[L["item"]]["F"])
    xl, xr = BAYS[L["bay"]]
    ov = len(fb.overlap(ib)) > 0
    oob = any(w.x < xl - 1e-3 or w.x > xr + 1e-3 or w.y < YF_IN - 1e-3 or w.z < Z_FLOOR_FRAME - 1e-3 or nrm(w.y, w.z) > N_MAX + 1e-3 for w in W)
    ins = inside(fb, sum(W, Vector()) / len(W))
    if ov or oob or ins: bad.append((L["unit"], k, ov, oob, ins))
print("CLIPPING", len(bad), "of", len(LUMPS), bad[:10])
# clearance of the contents to the new parts (posts, beams, braces) and the peak of the heap
peak = max(w.z for L in LUMPS for w in lump_world(L)[1])
print("CONTENTS peak z %.3f (top beams start at %.3f), front-most y %.3f, back-most y %.3f" % (
    peak, ZBOT, min(w.y for L in LUMPS for w in lump_world(L)[1]), max(w.y for L in LUMPS for w in lump_world(L)[1])))

# ---- 3. anchors, written last: round 3's units verbatim, meta updated ----
meta = dict(R3J["meta"])
meta.update(round=4, frame_tris=frame_tris, clipping=len(bad),
            contents="reused unchanged from round 3: the round 4 frame (full-height posts, flat top frame, braces, brackets) "
                     "lies outside the contents volume; every lump clip-checked against this frame")
json.dump(dict(meta=meta, units=UNITS), open(os.path.join(OUTA, "bunker_anchors.json"), "w"), indent=1)
print("ANCHORS units", len(UNITS), "copies", len(LUMPS))

# ---- 4. renders ----
def new_coll(name):
    c = bpy.data.collections.new(name); sc.collection.children.link(c); return c

def frame_into(coll, off, mat=None):
    rng.seed(7); PARTS.clear()
    build_frame()
    ob = join(list(PARTS), "frame"); PARTS.clear()
    for c in ob.users_collection: c.objects.unlink(ob)
    coll.objects.link(ob); ob.location = off
    return ob

def r3_into(coll, off):
    bpy.ops.wm.obj_import(filepath=os.path.join(R3, "Bunker.obj"), forward_axis="NEGATIVE_Z", up_axis="Y")
    obs = list(bpy.context.selected_objects)
    m3 = atlas_mat("r3", bpy.data.images.load(os.path.join(R3, "bunker_atlas.png")))
    for ob in obs:
        ob.data.materials.clear(); ob.data.materials.append(m3)
        for c in ob.users_collection: c.objects.unlink(ob)
        coll.objects.link(ob); ob.location = off

def contents_into(coll, off, fill):
    n = round(fill * len(UNITS))
    for L in LUMPS:
        if L["unit"] >= n: continue
        ob = bpy.data.objects.new(L["item"], TPL[L["item"]]["mesh"])
        ob.location = L["loc"] + Vector(off); ob.rotation_mode = "QUATERNION"
        ob.rotation_quaternion = L["rot"].to_quaternion(); ob.scale = (L["s"],) * 3
        coll.objects.link(ob)

DZ = hi.z - lo.z                                           # bounds height: snap points sit on the bounds corners
G = {}
G["empty"] = new_coll("empty"); frame_into(G["empty"], (0, 0, 0))
G["full"] = new_coll("full"); frame_into(G["full"], (0, 0, 0)); contents_into(G["full"], (0, 0, 0), 1.0)
G["stacked"] = new_coll("stacked")
frame_into(G["stacked"], (0, 0, 0)); contents_into(G["stacked"], (0, 0, 0), 1.0)
frame_into(G["stacked"], (0, 0, DZ)); contents_into(G["stacked"], (0, 0, DZ), 0.5)
G["r3r4"] = new_coll("r3r4")
r3_into(G["r3r4"], (-2.45, 0, 0)); contents_into(G["r3r4"], (-2.45, 0, 0), 1.0)
frame_into(G["r3r4"], (2.45, 0, 0)); contents_into(G["r3r4"], (2.45, 0, 0), 1.0)
G["r3r4stack"] = new_coll("r3r4stack")
r3_into(G["r3r4stack"], (-2.45, 0, 0)); r3_into(G["r3r4stack"], (-2.45, 0, 1.858))
frame_into(G["r3r4stack"], (2.45, 0, 0)); frame_into(G["r3r4stack"], (2.45, 0, DZ))
# 1.8 m player-height post for scale
pm = bpy.data.materials.new("post"); pm.use_nodes = True
pm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.30, 0.30, 0.29, 1)
for gname in G:
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(-2.55 if not gname.startswith("r3r4") else -5.2, -1.3, 0.9))
    pst = bpy.context.active_object; pst.scale = (0.14, 0.14, 1.8); pst.data.materials.append(pm)
    for c in pst.users_collection: c.objects.unlink(pst)
    G[gname].objects.link(pst)

world = bpy.data.worlds.new("w"); sc.world = world; world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.42, 0.45, 0.5, 1)
world.node_tree.nodes["Background"].inputs[1].default_value = 0.9
sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN")); sun.data.energy = 3.2
sun.rotation_euler = (math.radians(50), 0, math.radians(35)); sc.collection.objects.link(sun)
bpy.ops.mesh.primitive_plane_add(size=120)
gm = bpy.data.materials.new("ground"); gm.use_nodes = True
gm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.16, 0.14, 0.11, 1)
bpy.context.active_object.data.materials.append(gm)
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam); sc.camera = cam
sc.render.engine = "BLENDER_EEVEE_NEXT"
sc.render.resolution_x, sc.render.resolution_y = 1600, 900
sc.view_settings.view_transform = "Standard"
DBG = [("dbg-corner", "empty", 120, 15, 2.6, (1.8, -0.6, 1.4))] if "--debug" in argv else []
VIEWS = DBG + [("front34-empty", "empty", -30, 22, 7.6, (0, 0, 0.85)),
         ("front34-full", "full", -30, 22, 7.6, (0, 0, 0.85)),
         ("back34-empty", "empty", 150, 24, 7.6, (0, 0, 0.85)),
         ("side-empty", "empty", 90, 6, 6.0, (0, 0.1, 0.9)),
         ("stacked", "stacked", -32, 16, 10.5, (0, 0, 1.75)),
         ("stacked-side", "stacked", -78, 8, 9.0, (0, 0, 1.75)),
         ("r3-vs-r4", "r3r4", -18, 20, 14.5, (-0.5, 0, 0.85)),
         ("r3-vs-r4-stacked", "r3r4stack", -20, 14, 16.0, (-0.6, 0, 1.75))]
for vn, gname, yaw, pitch, dist, tgt in VIEWS:
    for k, c in G.items(): c.hide_render = (k != gname)
    t = Vector(tgt)
    d = Vector((math.cos(math.radians(pitch)) * math.sin(math.radians(yaw)),
                -math.cos(math.radians(pitch)) * math.cos(math.radians(yaw)), math.sin(math.radians(pitch))))
    cam.location = t + d * dist; cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    sc.render.filepath = os.path.join(OUT, f"{TAG}-{vn}.png")
    bpy.ops.render.render(write_still=True)
print("DONE")
