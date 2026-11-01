"""Hide Rack, round 1 (static): an iron-banded post carrying 8 hinged timber frames, each with one stretched rawhide as its
label, fanned over a half-disc plank deck with 8 wedge bays where the stored hides pile up (Joost on the concept sketch: "4 is
sick!"). Round 1 is static: the frames do not move in game yet (flipping them is a later code round).

The fan (the sketch's weakness: the middle frames showed only slivers from the front). Every frame hangs from the post in a
plane through the post axis, so a frame pointing at the viewer is seen edge on and two frames at the same height on the same
side hide each other. Round 1 therefore uses two rows (low 0.60-1.26 m, high 1.32-1.98 m) and per row and side one WIDE frame
swung back almost onto the back line (3 and 12 degrees from it: seen nearly face on) and one NARROW frame swung forward
(44 and 54 degrees): the narrow frame covers only the inner part of the wide one behind it, so from a standing view in front
every hide shows (the wide ones their outer ~60%, the narrow ones whole, foreshortened to cos 44-54 = 0.6-0.7).

The frame hides are our own geometry and texture (a neutral rawhide), not item copies: 8 of the 11 hide items are ROLLED
bundles (DeerHide, WolfPelt, LoxPelt, ScaleHide, AskHide, BjornHide, MooseHide, SealHide; only TrollHide and LeatherScraps
are flat), so an item model laid in a frame reads as a log in a frame, not as a stretched skin. The bays below show the
stored item's own model.

Contents: 64 units = 8 bays x 8 units (one stack each), one hide kind per bay (group key "bay"). Every hide has its own
physics-settled pile (Blender rigid body / Bullet, convex hulls, copy by copy, earlier copies frozen), 12 copies at full
(per stack 2,1,2,1,2,1,2,1), settled once in a bay-local wedge cavity; all 8 bays are the same wedge turned about the post.
- units[]: today's schema (Anchors.Parse): each bay's units carry the pile of that bay's designated hide (BAY_ITEMS),
  offsets/quat/fit_longest_m in prefab space. Another hide stored in that bay reuses those poses (fit_longest_m).
- hide_layouts{} + bays[]: every hide's own pile in BAY-LOCAL space (offset from the bay floor centre, rotation), and per bay
  its floor centre and turn about up, so a code round can show ANY hide in ANY bay with its own settled pile.
Checks: copies inside the wedge cavity (dividers, rim, post foot, under the frames), mesh vs frame clipping for every hide in
every bay, mesh vs mesh between copies, support (no copy floats over 5 mm), hull interpenetration.
Files: assets/hiderack_r1/{HideRack.obj, hiderack_atlas.png, hiderack_anchors.json}; the json is written last (temp + rename).
Atlas: 128 px point filtered; the timber, end grain and iron tiles are copied from bunker_r4's atlas, the sawn plank row and
the wear swatch (chamfers, rivet heads) from metalpallet_r3's; rawhide and leather lashing are new.
Run: blender -b -P hiderack_r1.py -- [--out DIR] [--frame-only] [--no-render] [--items DeerHide,TrollHide] [--quick]
"""
import bpy, bmesh, sys, os, math, json, random, time
import numpy as np
from mathutils import Vector, Matrix, Euler, Quaternion
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, ".."))
OUTA = os.path.join(REPO, "assets", "hiderack_r1")
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
def arg(k, d=None, typ=str): return typ(argv[argv.index(k) + 1]) if k in argv else d
OUT = arg("--out", "C:/Users/joost/AppData/Local/Temp/claude/C--Users-joost--pai/5e4bc60b-cdfe-4638-8e29-2e507fa13cf9/scratchpad/hiderack1")
FRAME_ONLY = "--frame-only" in argv
QUICK = "--quick" in argv
ITEMS_DIR = "C:/Users/joost/ValheimRip/items"
sys.path.append(ITEMS_DIR)
from load_item import load_item
os.makedirs(OUT, exist_ok=True)
rng = random.Random(7)

# ---------- the hides (prefab names; the code's item list) ----------
# BAY_ITEMS: the designated hide per bay, bay 0 = the right end as seen from the front (Unity -x), bay 7 the left end.
BAY_ITEMS = ["TrollHide", "WolfPelt", "LoxPelt", "DeerHide", "LeatherScraps", "AskHide", "ScaleHide", "BjornHide"]
EXTRA_ITEMS = ["MooseHide", "SealHide", "Leatherstraps"]     # in the game files, not obtainable in vanilla today
MODE = {n: "roll" for n in ("DeerHide", "WolfPelt", "LoxPelt", "ScaleHide", "AskHide", "BjornHide", "MooseHide", "SealHide")}
MODE.update({"TrollHide": "flat", "LeatherScraps": "flat", "Leatherstraps": "flat"})
ALL_ITEMS = BAY_ITEMS + EXTRA_ITEMS
if "--items" in argv:
    ALL_ITEMS = arg("--items").split(",")
PER_STACK = [2, 1, 2, 1, 2, 1, 2, 1]                        # 12 copies in a full bay

# ---------- layout (Blender metres: z up, -y front, +x = right as seen from the front = Unity -x) ----------
YP = 0.36                    # post axis (back centre); the deck runs from y = YP - R_DECK (front) to YP + BACK
R_DECK, BACK = 0.98, 0.26
SKID_H, PT = 0.10, 0.05
DECK = SKID_H + PT           # 0.15 deck top
POST = 0.16                  # square hewn post
POST_TOP = 2.03
NB = 8; SPAN = 180.0 / NB; HALF = math.radians(SPAN / 2)
DIV_T, DIV_H = 0.05, 0.16    # radial divider boards between the bays
RIM_R, RIM_T, RIM_H = 0.955, 0.06, 0.13
R_IN = 0.28                  # cavity: from the post foot ...
X_OUT = 0.90                 # ... to the rim (a line across the bay at 0.90 m from the post axis; the rim's inner face is >= 0.925)
WALL_MG = DIV_T / 2 + 0.006  # cavity side walls: the divider faces plus 6 mm
R_C = (R_IN + X_OUT) / 2     # bay floor centre, from the post axis along the bay's centre line
FLOOR_Z = 0.003              # the cavity floor: 3 mm over the deck planks
HEAP_CAP = 0.40              # piles stay under deck + 0.40 (the low frames start at 0.60)
ROWS = {"low": (0.60, 1.26), "high": (1.32, 1.98)}
R0 = 0.15                    # frame hinge stile inner edge, from the post axis
# frames: (row, angle from the +x back line toward the front, degrees; radial length). Left side mirrored (180 - angle).
FR_RIGHT = [("high", 3.0, 0.84), ("low", 12.0, 0.84), ("high", 44.0, 0.52), ("low", 54.0, 0.52)]
FRAMES = FR_RIGHT + [(r, 180.0 - a, L) for r, a, L in FR_RIGHT]
FT, FS = 0.07, 0.10          # frame depth (thickness), stile / rail width

# ---------- atlas: tiles copied from bunker_r4 and metalpallet_r3, rawhide and leather new ----------
TEX = 128; DENS = 48.0
STRIP = {"hewn": (0.75, 32), "end": (0.5, 32), "iron": (0.375, 16), "plank": (0.25, 16)}
SWATCH_U = 96                # metalpallet_r3's wear swatch: v 80-95 worn timber, v 64-79 worn iron (u 96-127)
def srgb(c): return np.array(c, dtype=np.float32)
def mix(a, b, t): t = np.clip(t, 0, 1)[..., None]; return a * (1 - t) + b * t
HIDE, HIDE_D, HIDE_L = srgb((0.58, 0.49, 0.37)), srgb((0.38, 0.30, 0.21)), srgb((0.69, 0.61, 0.48))
LEA, LEA_D, LEA_L = srgb((0.28, 0.185, 0.11)), srgb((0.12, 0.075, 0.045)), srgb((0.43, 0.31, 0.20))

def load_px(path):
    im = bpy.data.images.load(path)
    a = np.array(im.pixels[:], np.float32).reshape(im.size[1], im.size[0], 4)[..., :3]   # row 0 = v 0 (bottom)
    bpy.data.images.remove(im)
    return a

def build_atlas():
    B4 = load_px(os.path.join(REPO, "assets", "bunker_r4", "bunker_atlas.png"))
    P3 = load_px(os.path.join(REPO, "assets", "metalpallet_r3", "metalpallet_atlas.png"))
    img = np.zeros((TEX, TEX, 3), np.float32)
    img[96:128] = B4[96:128]                       # hewn timber (bunker_r4)
    img[64:96, 0:96] = B4[64:96, 0:96]             # end grain, ring tiles 0-2 (bunker_r4)
    img[64:96, 96:128] = P3[64:96, 96:128]         # wear swatch: worn timber / worn iron (metalpallet_r3)
    img[48:64] = B4[48:64]                         # dark iron (bunker_r4)
    img[32:48] = P3[32:48]                         # sawn plank row (metalpallet_r3)
    nr = np.random.default_rng(11)
    # rawhide (v 0-31, u 0-95): low mottling, fine grain, a few darker veins and scraped light patches, darker towards the
    # tile's rim rows (stretched hides darken where the lashing pulls)
    x = np.arange(96)[None, :].repeat(32, 0).astype(np.float32); y = np.arange(32)[:, None].repeat(96, 1).astype(np.float32)
    m = (0.5 + 0.5 * np.sin(x * 0.23 + 1.3 * np.sin(y * 0.31))) * (0.5 + 0.5 * np.sin(y * 0.27 + 1.1 * np.sin(x * 0.19)))
    n0 = nr.random((32, 96)); n1 = (n0 + np.roll(n0, 1, 0) + np.roll(n0, 1, 1) + np.roll(n0, -1, 1)) / 4   # soft blotches
    t = 0.22 * m + 0.25 * n1 + nr.random((32, 96)) * 0.12
    for _ in range(7):                                                     # veins: thin dark wandering lines
        cx, cy, a = nr.uniform(0, 96), nr.uniform(4, 28), nr.uniform(0, math.pi)
        for k in range(nr.integers(8, 18)):
            xi, yi = int(cx + k * math.cos(a)) % 96, int(cy + k * math.sin(a) + 1.5 * math.sin(k * 0.6))
            if 0 <= yi < 32: t[yi, xi] += 0.35
    hide = mix(HIDE, HIDE_D, t)
    worn = (nr.random((32, 96)) < 0.06) & (t < 0.35)
    hide[worn] = mix(hide[worn], HIDE_L, np.full(worn.sum(), 0.6))
    img[0:32, 0:96] = hide
    # leather lashing (v 16-31, u 96-127): twisted thong, diagonal turns, dark crevices, worn light crests
    x = np.arange(32)[None, :].repeat(16, 0).astype(np.float32); y = np.arange(16)[:, None].repeat(32, 1).astype(np.float32)
    tw = 0.5 + 0.5 * np.sin((x + y * 0.8) * 2 * math.pi / 5.0)
    t = tw * 0.55 + nr.random((16, 32)) * 0.25
    lea = mix(LEA, LEA_D, t)
    crest = (tw < 0.12) & (nr.random((16, 32)) < 0.5)
    lea[crest] = mix(lea[crest], LEA_L, np.full(crest.sum(), 0.7))
    img[16:32, 96:128] = lea
    # hide edge / dark leather (v 0-15, u 96-127)
    img[0:16, 96:128] = mix(HIDE_D * 0.85, LEA, nr.random((16, 32)) * 0.6)
    im = bpy.data.images.new("hiderack_atlas", TEX, TEX, alpha=False)
    px = np.concatenate([np.clip(img, 0, 1), np.ones((TEX, TEX, 1), np.float32)], 2)
    im.pixels.foreach_set(px.ravel())
    return im

def save_atlas(im, path):
    tmp = path[:-4] + ".part.png"
    im.filepath_raw = tmp; im.file_format = "PNG"; im.save()
    os.replace(tmp, path)

def atlas_mat(name, img):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    t = m.node_tree.nodes.new("ShaderNodeTexImage"); t.image = img; t.interpolation = "Closest"
    m.node_tree.links.new(t.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.9; b.inputs["Specular IOR Level"].default_value = 0.1
    return m

# ---------- geometry helpers (bunker_r4's timber + metalpallet_r3's worn chamfers) ----------
PARTS = []
MAT = None
UV = None

def texel(u, v):
    return ((u + 0.5) / TEX, (v + 0.5) / TEX)

def uv_face(f, kind, long_axis, seed):
    n = f.normal
    r = random.Random(seed * 7919 + f.index)
    if kind == "rivet" or max(abs(n[0]), abs(n[1]), abs(n[2])) < 0.98:      # chamfers and rivet heads: the wear swatch
        uv = texel(SWATCH_U + 1 + r.randrange(30), (65 if kind in ("iron", "rivet") else 81) + r.randrange(14))
        for l in f.loops: l[UV].uv = uv
        return
    ax = max(range(3), key=lambda i: abs(n[i]))
    tang = [i for i in range(3) if i != ax]
    if kind in ("leather", "hidegeo"):
        for l in f.loops: l[UV].uv = texel(98 + r.randrange(28), 2 + r.randrange(12))
        return
    if kind != "iron" and ax == long_axis:          # cut end of a timber: end grain ring tiles 0-2
        k = seed % 3
        cs = [l.vert.co for l in f.loops]
        c = sum(cs, Vector()) / len(cs)
        ext = max(max(abs(v[tang[0]] - c[tang[0]]), abs(v[tang[1]] - c[tang[1]])) for v in cs) or 1
        for l in f.loops:
            a = (l.vert.co[tang[0]] - c[tang[0]]) / ext; b = (l.vert.co[tang[1]] - c[tang[1]]) / ext
            l[UV].uv = ((k + 0.5 + a * 0.45) / 4, STRIP["end"][0] + (0.5 + b * 0.45) / 4)
        return
    ua = long_axis if long_axis in tang else tang[0]
    va = tang[1] if ua == tang[0] else tang[0]
    off = (seed * 0.37) % 1
    vs = [l.vert.co[va] for l in f.loops]
    vmin, span = min(vs), max(max(vs) - min(vs), 1e-4)
    base, hpx = STRIP[kind]
    vscale = min(1.0, (hpx / DENS) / span)
    room = max(hpx / TEX - span * vscale * DENS / TEX * 0.94 - 0.012, 0)
    voff = ((seed * 0.618) % 1) * room
    for l in f.loops:
        u = l.vert.co[ua] * DENS / TEX + off
        v = base + ((l.vert.co[va] - vmin) * vscale * DENS / TEX) * 0.94 + 0.0075 + voff
        l[UV].uv = (u, v)

def finish(bm, name, kind, long_axis, pos, rot, uvfun=None):
    global UV
    bm.normal_update()
    UV = bm.loops.layers.uv.verify()
    seed = rng.randrange(1000)
    for f in bm.faces:
        if uvfun: uvfun(f)
        else: uv_face(f, kind, long_axis, seed + f.index % 2)
    bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Euler([math.radians(a) for a in rot]).to_matrix())
    bmesh.ops.translate(bm, verts=bm.verts, vec=Vector(pos))
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = False
    ob = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(ob)
    ob.data.materials.append(MAT); PARTS.append(ob)
    return ob

def timber(name, size, pos, kind="hewn", rot=(0, 0, 0), jitter=0.006, bevel=0.015):
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
    return finish(bm, name, kind, long_axis, pos, rot)

def iron(name, size, pos, rot=(0, 0, 0)):
    return timber(name, size, pos, kind="iron", rot=rot, jitter=0.0015, bevel=0)

def rivet(pos, axis, sign, s=0.024, h=0.006):
    sz = [s, s, s]; sz[axis] = h
    p = list(pos); p[axis] += sign * h / 2
    return timber("rivet", sz, p, kind="rivet", jitter=0, bevel=0)

def cord(name, p0, p1, w=0.016):
    """A leather thong in a frame's plane (frame-local x = radial, z = up) from p0 to p1 (x, z)."""
    dx, dz = p1[0] - p0[0], p1[1] - p0[1]; L = math.hypot(dx, dz)
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts: v.co = Vector((v.co.x * (L + 0.012), v.co.y * w, v.co.z * w))
    def uvf(f, L=L):
        n = f.normal
        if abs(n.x) > 0.9:
            for l in f.loops: l[UV].uv = texel(100, 20)
            return
        span = min(L * DENS, 28.0)
        cross = 1 if abs(n.y) > 0.9 else 2
        for l in f.loops:
            a = (l.vert.co.x / (L + 0.012) + 0.5); b = (l.vert.co[cross] / w + 0.5)
            l[UV].uv = ((98 + a * span) / TEX, (18 + b * 11) / TEX)
    return finish(bm, name, "leather", 0, ((p0[0] + p1[0]) / 2, 0, (p0[1] + p1[1]) / 2), (0, -math.degrees(math.atan2(dz, dx)), 0), uvfun=uvf)

# a stretched hide's outline (u, v in [-1, 1]): neck at the top, fore legs, flanks, hind legs, tail
OUTL = [(-0.20, 1.0), (0.20, 1.0), (0.24, 0.80), (0.58, 0.76), (0.98, 0.88), (1.0, 0.60), (0.82, 0.38), (0.88, 0.08),
        (0.90, -0.25), (0.95, -0.55), (0.98, -0.95), (0.60, -0.98), (0.50, -0.70), (0.16, -0.76), (0.10, -1.0), (-0.10, -1.0),
        (-0.16, -0.76), (-0.50, -0.70), (-0.60, -0.98), (-0.98, -0.95), (-0.95, -0.55), (-0.90, -0.25), (-0.88, 0.08),
        (-0.82, 0.38), (-1.0, 0.60), (-0.98, 0.88), (-0.58, 0.76), (-0.24, 0.80)]
TIPS = [0, 1, 4, 5, 7, 10, 11, 14, 15, 18, 19, 22, 24, 25]

def stretched_hide(cx, cz, ax, az, seed, uoff, voff):
    """The rawhide in a frame (frame-local: x radial, y thickness, z up), centred at (cx, cz), half sizes ax, az."""
    sj = random.Random(seed)
    pts = [(cx + (u + sj.uniform(-0.04, 0.04)) * ax, cz + (v + sj.uniform(-0.04, 0.04)) * az) for u, v in OUTL]
    bm = bmesh.new()
    th = 0.006
    front = [bm.verts.new((x, -th, z)) for x, z in pts]
    back = [bm.verts.new((x, th, z)) for x, z in pts]
    bm.faces.new(front[::-1]); bm.faces.new(back)
    n = len(pts)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((front[i], front[j], back[j], back[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method="BEAUTY", ngon_method="EAR_CLIP")
    x0, z0 = min(p[0] for p in pts), min(p[1] for p in pts)
    def uvf(f):
        if abs(f.normal.y) > 0.9:
            for l in f.loops:
                l[UV].uv = ((uoff + (l.vert.co.x - x0) * DENS) / TEX, (voff + (l.vert.co.z - z0) * DENS) / TEX)
        else:
            for l in f.loops: l[UV].uv = texel(104, 6)
    finish(bm, "hide", "hidegeo", 0, (0, 0, 0), (0, 0, 0), uvfun=uvf)
    return pts

def frame_dir(phi):
    a = math.radians(phi)
    return Vector((math.cos(a), -math.sin(a), 0))

COLLARS = {}   # (row) -> next collar index

def build_frame(i, row, phi, L):
    """One hinged frame, built frame-local (x radial from the post axis, y across, z up) then turned onto its angle."""
    start = len(PARTS)
    z0, z1 = ROWS[row]; H = z1 - z0
    x0, x1 = R0, R0 + L
    zc = (z0 + z1) / 2
    timber("stile", (FS, FT, H), (x0 + FS / 2, 0, zc), bevel=0.015, jitter=0.003)
    timber("stile", (FS, FT, H), (x1 - FS / 2, 0, zc), bevel=0.015, jitter=0.003)
    timber("rail", (L - 2 * FS + 0.02, FT - 0.01, FS), (zx := (x0 + x1) / 2, 0, z1 - FS / 2), bevel=0.013, jitter=0.003)
    timber("rail", (L - 2 * FS + 0.02, FT - 0.01, FS), (zx, 0, z0 + FS / 2), bevel=0.013, jitter=0.003)
    # iron corner plates with a rivet, on both faces (iron where timber meets timber)
    for cxp in (x0 + 0.05, x1 - 0.05):
        for czp in (z0 + 0.05, z1 - 0.05):
            for s in (-1, 1):
                iron("plate", (0.11, 0.008, 0.11), (cxp, s * (FT / 2 + 0.004), czp))
                rivet((cxp, s * (FT / 2 + 0.008), czp), 1, s)
    # the stretched rawhide and its lashing to the rails
    ix0, ix1, iz0, iz1 = x0 + FS, x1 - FS, z0 + FS, z1 - FS
    ax, az = (ix1 - ix0) / 2 - 0.045, (iz1 - iz0) / 2 - 0.04
    uoff = 2 + (i * 11) % max(1, int(94 - 2 * ax * DENS))
    pts = stretched_hide((ix0 + ix1) / 2, (iz0 + iz1) / 2, ax, az, 100 + i, uoff, 3)
    for k in TIPS:
        x, z = pts[k]
        cands = [(x - ix0, (ix0 + 0.004, z)), (ix1 - x, (ix1 - 0.004, z)), (z - iz0, (x, iz0 + 0.004)), (iz1 - z, (x, iz1 - 0.004))]
        d, tgt = min(cands, key=lambda c: c[0])
        if d > 0.008: cord("lash", (x, z), tgt)
    # hinge: an iron collar on the post at the bottom and the top of the frame, a riveted strap over the stile
    for zz in ("bot", "top"):
        k = COLLARS.get((row, zz), 0); COLLARS[(row, zz)] = k + 1
        zcol = z0 + 0.035 + 0.046 * k if zz == "bot" else z1 - 0.035 - 0.046 * k
        iron("strap", (x0 + FS + 0.04 - 0.095, FT + 0.016, 0.040), ((0.095 + x0 + FS + 0.04) / 2, 0, zcol))
        for s in (-1, 1): rivet((x0 + FS / 2 + 0.01, s * (FT / 2 + 0.008), zcol), 1, s, s=0.02)
    M = Matrix.Translation((0, YP, 0)) @ Matrix.Rotation(-math.radians(phi), 4, "Z")
    for o in PARTS[start:]: o.data.transform(M)
    return dict(index=i, row=row, angle_deg=phi, length=L)

def build_rack():
    # skids across under the deck, deck planks front to back (cut square at the circle), the back strip behind the post
    for y, hw in ((YP + 0.14, 0.95), (YP - 0.40, 0.83), (YP - 0.78, 0.52)):
        timber("skid", (2 * hw, 0.13, SKID_H), (0, y, SKID_H / 2), bevel=0.018, jitter=0.004)
    for k in range(-5, 6):
        x = k * 0.19
        hx = abs(x) + 0.06
        yf = YP - math.sqrt(max(R_DECK ** 2 - hx ** 2, 0.04)) + 0.01
        yb = YP + BACK
        timber("plank", (0.18, yb - yf, PT), (x, (yf + yb) / 2, SKID_H + PT / 2), kind="plank", bevel=0.008, jitter=0.002)
    # rim: two chunky segments per bay along the arc
    for s in range(2 * NB):
        a = math.radians((s + 0.5) * SPAN / 2)
        d = frame_dir(math.degrees(a))
        L = 2 * RIM_R * math.sin(math.radians(SPAN / 4)) + 0.015
        timber("rim", (RIM_T, L, RIM_H), (d.x * RIM_R, YP + d.y * RIM_R, DECK + RIM_H / 2), rot=(0, 0, -math.degrees(a)),
               bevel=0.012, jitter=0.002)
    # radial dividers between the bays, an iron bracket where each meets the rim
    for k in range(NB + 1):
        a = k * SPAN; d = frame_dir(a)
        r0, r1 = 0.21, RIM_R - RIM_T / 2
        rm = (r0 + r1) / 2
        timber("divider", (r1 - r0, DIV_T, DIV_H), (d.x * rm, YP + d.y * rm, DECK + DIV_H / 2), rot=(0, 0, -a), bevel=0.010,
               jitter=0.002)
        rb = r1 - 0.06
        iron("bracket", (0.10, DIV_T + 0.012, 0.012), (d.x * rb, YP + d.y * rb, DECK + DIV_H + 0.006), rot=(0, 0, -a))
    # post: foot block with iron corner brackets, the hewn post, head
    timber("foot", (0.36, 0.36, 0.11), (0, YP, DECK + 0.055), bevel=0.02, jitter=0.003)
    for sx in (-1, 1):
        for sy in (-1, 1):
            iron("footiron", (0.05, 0.05, 0.115), (sx * 0.163, YP + sy * 0.163, DECK + 0.0575))
    timber("post", (POST, POST, POST_TOP - DECK - 0.11), (0, YP, (DECK + 0.11 + POST_TOP) / 2), bevel=0.025, jitter=0.002)
    timber("head", (0.22, 0.22, 0.07), (0, YP, POST_TOP + 0.035), bevel=0.018, jitter=0.002)
    for z in (DECK + 0.20, 0.47, 2.00 - 0.0):
        iron("band", (0.18, 0.18, 0.05), (0, YP, z))
    # the 8 frames, each on two iron collars
    info = []
    for i, (row, phi, L) in enumerate(FRAMES):
        info.append(build_frame(i, row, phi, L))
    for row, (z0, z1) in ROWS.items():
        n = sum(1 for f in FRAMES if f[0] == row)
        for k in range(n):
            iron("collar", (0.21, 0.21, 0.040), (0, YP, z0 + 0.035 + 0.046 * k))
            iron("collar", (0.21, 0.21, 0.040), (0, YP, z1 - 0.035 - 0.046 * k))
    return info

def tris(obs): return sum(len(p.vertices) - 2 for o in obs for p in o.data.polygons)

# ---------- scene ----------
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
ATLAS = build_atlas()
MAT = atlas_mat("hiderack", ATLAS)
FRAME_INFO = build_rack()
ntris = tris(PARTS)
allv = np.array([v.co[:] for o in PARTS for v in o.data.vertices])
FMIN, FMAX = allv.min(0), allv.max(0)
print("HR1 FRAME tris", ntris, "size W x D x H %.3f x %.3f x %.3f" % tuple((FMAX - FMIN)[[0, 1, 2]]), "x", np.round(FMIN, 3), np.round(FMAX, 3), flush=True)
FV = [Vector(v[:]) for v in allv]
FT_ = []; off = 0
for o in PARTS:
    for p in o.data.polygons:
        vs = [off + i for i in p.vertices]
        for k in range(1, len(vs) - 1): FT_.append((vs[0], vs[k], vs[k + 1]))
    off += len(o.data.vertices)
FBVH = BVHTree.FromPolygons(FV, FT_, all_triangles=True)

# ---------- bays (Blender): floor centre and turn about up; bay b spans [b * SPAN, (b + 1) * SPAN] from the +x back line ----------
def bay_matrix(b):
    phi = (b + 0.5) * SPAN; d = frame_dir(phi)
    return Matrix.Translation((d.x * R_C, YP + d.y * R_C, DECK)) @ Matrix.Rotation(-math.radians(phi), 4, "Z")
BAYM = [bay_matrix(b) for b in range(NB)]

# the cavity, bay-local (x along the bay's centre line from its floor centre, z up from the deck top): 4 half-planes
SH, CH = math.sin(HALF), math.cos(HALF)
def inside_cav(P, eps=0.0):
    xa = P[:, 0] + R_C
    return ((xa >= R_IN - eps) & (xa <= X_OUT + eps) & (-SH * xa + CH * P[:, 1] <= -WALL_MG + eps)
            & (-SH * xa - CH * P[:, 1] <= -WALL_MG + eps))
def cav_over(P):
    """how far (m) points leave the cavity (<= 0: inside); floor and ceiling included."""
    xa = P[:, 0] + R_C
    o = np.max(np.stack([R_IN - xa, xa - X_OUT, (-SH * xa + CH * P[:, 1]) + WALL_MG, (-SH * xa - CH * P[:, 1]) + WALL_MG,
                         FLOOR_Z - P[:, 2], P[:, 2] - HEAP_CAP]), 0)
    return float(o.max())
YW = X_OUT * math.tan(HALF) - WALL_MG / CH
CAVB = (R_IN - R_C, X_OUT - R_C, -YW, YW, FLOOR_Z, HEAP_CAP)

# ---------- renders: helpers ----------
def setup_world():
    world = bpy.data.worlds.new("w"); sc.world = world; world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.42, 0.45, 0.5, 1)
    world.node_tree.nodes["Background"].inputs[1].default_value = 0.9
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN")); sun.data.energy = 3.2
    sun.rotation_euler = (math.radians(50), 0, math.radians(35)); sc.collection.objects.link(sun)
    bpy.ops.mesh.primitive_plane_add(size=300, location=(0, 30, -0.001))
    gm = bpy.data.materials.new("ground"); gm.use_nodes = True
    gm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.16, 0.14, 0.11, 1)
    bpy.context.active_object.data.materials.append(gm)
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam); sc.camera = cam
    sc.render.engine = "BLENDER_EEVEE_NEXT"
    sc.view_settings.view_transform = "Standard"
    pm = bpy.data.materials.new("plain"); pm.use_nodes = True
    pm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.85, 0.85, 0.85, 1)
    bpy.ops.mesh.primitive_cylinder_add(radius=0.06, depth=1.8, location=(1.45, -0.2, 0.9)); p = bpy.context.active_object
    p.data.materials.append(pm); p.name = "post_1.8m"
    return cam

def view(cam, yaw, dist, eye, tgt, lens=35):
    t = Vector(tgt)
    cam.location = t + Vector((math.sin(math.radians(yaw)) * dist, -math.cos(math.radians(yaw)) * dist, eye - t.z))
    cam.rotation_euler = (t - cam.location).to_track_quat("-Z", "Y").to_euler(); cam.data.lens = lens

def render(fn, w=1600, h=1000):
    sc.render.resolution_x, sc.render.resolution_y = (w // 2, h // 2) if QUICK else (w, h)
    sc.render.filepath = fn; bpy.ops.render.render(write_still=True); print("RENDER", fn, flush=True)

if FRAME_ONLY:
    cam = setup_world()
    view(cam, 0, 4.0, 1.75, (0, 0, 1.0)); render(os.path.join(OUT, "frame-front.png"))
    view(cam, -35, 4.2, 1.75, (0, 0, 0.95)); render(os.path.join(OUT, "frame-34.png"))
    view(cam, -15, 3.0, 4.2, (0, 0, 0.5)); render(os.path.join(OUT, "frame-top.png"))
    print("DONE"); sys.exit(0)

# ---------- items ----------
def align_A(size):
    """rotation taking the item's longest bounds axis onto +x and its thinnest onto +z."""
    il = int(np.argmax(size)); it = int(np.argmin(size))
    if it == il: it = (il + 1) % 3
    im = 3 - il - it
    R = np.zeros((3, 3)); R[0, il] = 1; R[2, it] = 1; R[1, im] = 1
    if np.linalg.det(R) < 0: R[1, im] = -1
    return Matrix(R.tolist())

MERGED = {}
def merged(item):
    if item in MERGED: return MERGED[item]
    objs = [o for o in load_item(item, anchor="center") if o.type == "MESH"]
    if len(objs) > 1:
        bpy.ops.object.select_all(action="DESELECT")
        for o in objs: o.select_set(True)
        bpy.context.view_layer.objects.active = objs[0]; bpy.ops.object.join(); ob = bpy.context.active_object
    else: ob = objs[0]
    ob.data.transform(ob.matrix_world); ob.matrix_world = Matrix.Identity(4)
    me = ob.data; me.name = item
    verts = np.array([v.co[:] for v in me.vertices])
    mn, mx = verts.min(0), verts.max(0); c = (mn + mx) / 2
    me.transform(Matrix.Translation(-Vector(c))); verts = verts - c
    bpy.data.objects.remove(ob)
    tri = []
    for p in me.polygons:
        for k in range(1, len(p.vertices) - 1): tri.append((p.vertices[0], p.vertices[k], p.vertices[k + 1]))
    bm = bmesh.new()
    for v in verts: bm.verts.new(v)
    res = bmesh.ops.convex_hull(bm, input=bm.verts[:])
    for g in res["geom_interior"] + res["geom_unused"]:
        if isinstance(g, bmesh.types.BMVert) and g.is_valid and not g.link_faces: bm.verts.remove(g)
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if f.is_valid])
    bm.normal_update(); bm.verts.index_update()
    vol = abs(bm.calc_volume())
    tf = [f for f in bm.faces if f.is_valid]
    used = sorted({v.index for f in tf for v in f.verts}); remap = {o: n for n, o in enumerate(used)}
    bm.verts.ensure_lookup_table()
    hv = np.array([bm.verts[i].co[:] for i in used]); F = np.array([[remap[v.index] for v in f.verts] for f in tf])
    cen = hv.mean(0); N = []; D = []
    for f in tf:
        n = np.array(f.normal[:]); d0 = n @ np.array(f.verts[0].co[:])
        if n @ cen > d0: n = -n; d0 = -d0
        N.append(n); D.append(d0)
    bm.free()
    pm = bpy.data.meshes.new(f"prox_{item}"); pm.from_pydata([tuple(v) for v in hv], [], [tuple(int(i) for i in f) for f in F]); pm.update()
    edges = sorted({tuple(sorted((int(f[a]), int(f[(a + 1) % 3])))) for f in F for a in range(3)})
    MERGED[item] = dict(mesh=me, verts=verts, tri=tri, hullV=hv, hullF=F, hullN=np.array(N), hullD=np.array(D), hullE=edges,
                        prox=pm, vol=vol, size=mx - mn, centre=c, A=align_A(mx - mn))
    return MERGED[item]

def world_pts(P, M): return P @ M[:3, :3].T + M[:3, 3]
def rec_world(m, M, s):
    hv = world_pts(m["hullV"], M); Rw = M[:3, :3] / s
    N = m["hullN"] @ Rw.T; D = m["hullD"] * s + N @ M[:3, 3]
    return dict(M=M, s=s, hv=hv, N=N, D=D, lo=hv.min(0), hi=hv.max(0), F=m["hullF"], E=m["hullE"])

CELL = 0.02
class Heap:
    """height field over the bay-local cavity rectangle, from the frozen copies' hulls."""
    def __init__(self, b):
        self.b = b; self.bodies = []
        self.nx = int(math.ceil((b[1] - b[0]) / CELL)); self.ny = int(math.ceil((b[3] - b[2]) / CELL))
        self.hf = np.full((self.nx, self.ny), b[4])
    def add_hull(self, N, D, lo, hi):
        i0 = max(0, int((lo[0] - self.b[0]) / CELL)); i1 = min(self.nx - 1, int((hi[0] - self.b[0]) / CELL))
        j0 = max(0, int((lo[1] - self.b[2]) / CELL)); j1 = min(self.ny - 1, int((hi[1] - self.b[2]) / CELL))
        if i1 < i0 or j1 < j0: return
        I, J = np.meshgrid(np.arange(i0, i1 + 1), np.arange(j0, j1 + 1), indexing="ij")
        X = (I.ravel() + 0.5) * CELL + self.b[0]; Y = (J.ravel() + 0.5) * CELL + self.b[2]
        P = N[:, 0:1] * X[None, :] + N[:, 1:2] * Y[None, :]
        up = N[:, 2] > 1e-6; dn = N[:, 2] < -1e-6; ve = ~(up | dn)
        if not up.any() or not dn.any(): return
        zt = ((D[up, None] - P[up]) / N[up, 2][:, None]).min(0); zb = ((D[dn, None] - P[dn]) / N[dn, 2][:, None]).max(0)
        ok = zt > zb
        if ve.any(): ok &= (P[ve] <= D[ve, None]).all(0)
        zt = np.where(ok, zt, -9.0)
        self.hf[I.ravel(), J.ravel()] = np.maximum(self.hf[I.ravel(), J.ravel()], zt)

def _bvh(r):
    if "bvh" not in r: r["bvh"] = BVHTree.FromPolygons([Vector(v) for v in r["hv"]], [tuple(int(i) for i in f) for f in r["F"]])
    return r["bvh"]
def _samples(r, step=0.006):
    if "smp" not in r:
        hv = r["hv"]; pts = [hv]
        for a, b in r["E"]:
            L = float(np.linalg.norm(hv[a] - hv[b])); n = int(L / step)
            if n >= 1:
                t = (np.arange(1, n + 1) / (n + 1))[:, None]; pts.append(hv[a] * (1 - t) + hv[b] * t)
        r["smp"] = np.vstack(pts)
    return r["smp"]
def inside_hull(r, p): return bool(((r["N"] @ p) - r["D"] <= 0).all())
def hull_dist(A, B):
    best = (1e9, None)
    bb = _bvh(B)
    for p in _samples(A):
        if inside_hull(B, p): return 0.0, p
        loc, nrm, idx, dist = bb.find_nearest(Vector(p))
        if loc is not None and dist < best[0]: best = (dist, p)
    ba = _bvh(A)
    for p in _samples(B):
        if inside_hull(A, p): return 0.0, p
        loc, nrm, idx, dist = ba.find_nearest(Vector(p))
        if loc is not None and dist < best[0]: best = (dist, np.array(loc[:]))
    return best
def support_gap(r, floor_z, earlier):
    zmin, zmax = r["lo"][2], r["hi"][2]
    gap = max(0.0, zmin - floor_z); what = "floor"
    if gap <= 0.0015: return gap, what
    span = max(zmax - zmin, 1e-6)
    for q in earlier:
        if (q["lo"] > r["hi"] + 0.02).any() or (q["hi"] < r["lo"] - 0.02).any(): continue
        d, pt = hull_dist(r, q)
        if pt is None or d >= gap: continue
        if pt[2] - zmin <= 0.35 * span + 1e-6: gap = d; what = "body"
    return gap, what

def Rz(a): return Euler((0, 0, math.radians(a))).to_matrix()
def Ry(a): return Euler((0, math.radians(a), 0)).to_matrix()
def Rx(a): return Euler((math.radians(a), 0, 0)).to_matrix()

# ---------- per-item scale: a full bay (12 copies) piles to about TARGET_H ----------
TARGET_H = 0.27
CAV_AREA = 0.5 * 2 * HALF * (X_OUT ** 2 - R_IN ** 2) * 0.9
SIM_DX = 2.5                 # cavities side by side, far enough apart that no wall reaches the next one
ITEM = {}
for i, name in enumerate(ALL_ITEMS):
    m = merged(name); longest = float(m["size"].max())
    vstar = TARGET_H * CAV_AREA * 0.5 / sum(PER_STACK)
    s = (vstar / m["vol"]) ** (1 / 3)
    lmax = 0.40 if MODE[name] == "roll" else 0.18          # the wedge is 0.13 m wide 0.5 m out from the post, 0.31 m at the rim
    s = min(s, lmax / longest); s = max(s, 0.20 / longest)
    ITEM[name] = dict(i=i, name=name, mode=MODE[name], s=s, origin=np.array((i * SIM_DX, 0.0, 0.0)))
    print("HR1 ITEM %-14s mode %-4s size %s hull vol %.4f -> scale %.4f longest %.3f m tris %d" % (
        name, MODE[name], np.round(m["size"], 3), m["vol"], s, s * longest, len(m["tri"])), flush=True)

# ---------- simulation: every item in its own bay-local cavity, side by side ----------
MAXF = 150; MINF = 16
NTRY = arg("--ntry", 30, int)
MARGIN = 0.0015
FLOAT_MAX = 0.005
VW = 0.35

def simulate(items, seed):
    rr = random.Random(seed)
    bpy.ops.rigidbody.world_add()
    rbw = sc.rigidbody_world
    sc.frame_start = 1; sc.frame_end = 900
    rbw.point_cache.frame_start = 1; rbw.point_cache.frame_end = 900
    rbw.substeps_per_frame = 20; rbw.solver_iterations = 40
    def set_rb(ob, typ, mass):
        with bpy.context.temp_override(object=ob, active_object=ob, selected_objects=[ob], selected_editable_objects=[ob]):
            bpy.ops.rigidbody.object_add(type=typ)
        rb = ob.rigid_body
        rb.friction = 0.8; rb.restitution = 0.0; rb.mass = mass
        rb.linear_damping = 0.5; rb.angular_damping = 0.95
        if typ == "ACTIVE":
            rb.use_deactivation = True; rb.deactivate_linear_velocity = 0.08; rb.deactivate_angular_velocity = 0.4
        return rb
    def add_slab(origin, normal, d, T=0.2, size=1.2):
        """a passive slab whose inner face is the plane normal . p = d (bay local + origin); normal points out of the cavity."""
        me = bpy.data.meshes.new("col")
        bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0); bm.to_mesh(me); bm.free()
        ob = bpy.data.objects.new("col", me); sc.collection.objects.link(ob)
        n = Vector(normal).normalized()
        q = Vector((0, 0, 1)).rotation_difference(n)
        ob.rotation_mode = "QUATERNION"; ob.rotation_quaternion = q
        ob.scale = (size, size, T)
        ob.location = Vector(origin) + n * (d + T / 2)
        rb = set_rb(ob, "PASSIVE", 1.0); rb.collision_shape = "BOX"; rb.use_margin = True; rb.collision_margin = 0.0
    for c in items:
        o = c["origin"]
        add_slab(o, (0, 0, -1), -FLOOR_Z)                                     # floor: z >= FLOOR_Z
        add_slab(o, (-1, 0, 0), -(R_IN - R_C))                                # inner: x >= R_IN - R_C
        add_slab(o, (1, 0, 0), X_OUT - R_C)                                   # outer: x <= X_OUT - R_C
        # side walls: -SH*(x+R_C) + CH*y <= -WALL_MG  ->  (-SH, CH) . p <= -WALL_MG + SH*R_C
        add_slab(o, (-SH, CH, 0), -WALL_MG + SH * R_C)
        add_slab(o, (-SH, -CH, 0), -WALL_MG + SH * R_C)
    st = dict(frames=0, tries=0, drops=0, rej={})
    allr = []
    PROBE = np.array([[1, 0, 0], [-1, 0, 0], [0, 1, 0], [0, -1, 0], [0, 0, 1], [0, 0, -1]], float)
    frz = [0]

    def orient(c, m):
        A = m["A"]
        if c["mode"] == "roll":
            yaw = rr.uniform(-4, 4) + (180 if rr.random() < 0.5 else 0)
            return Rz(yaw) @ Rx(rr.uniform(0, 360)) @ A
        return Rz(rr.uniform(0, 360)) @ Rx(rr.uniform(-5, 5)) @ Ry(rr.uniform(-5, 5)) @ A

    def spawn(w):
        c = w["c"]; hp = c["heap"]; m = merged(c["name"]); s = c["s"]; ox = c["origin"][0]
        for _ in range(24):
            Rc = orient(c, m); Rn = np.array(Rc)
            HV = (m["hullV"] @ Rn.T) * s; AV = (m["verts"] @ Rn.T) * s
            lo = np.minimum(AV.min(0), HV.min(0)); hi = np.maximum(AV.max(0), HV.max(0))
            # footprint: the drawn vertices' and hull's plan, must fit the cavity with a margin at some spot
            FP = np.vstack([AV[:, :2], HV[:, :2]])
            hullxy = FP[np.unique(np.concatenate([np.argmin(FP, 0), np.argmax(FP, 0)]))]
            cands = []
            for xx in np.arange(CAVB[0] + 0.01, CAVB[1], CELL):
                for yy in np.arange(CAVB[2] + 0.01, CAVB[3], CELL):
                    P = np.column_stack([FP[:, 0] + xx, FP[:, 1] + yy, np.zeros(len(FP))])
                    if inside_cav(P, -0.004).all(): cands.append((xx, yy))
            if cands: break
        else:
            return False, "plan"
        low = -HV[:, 2].min()
        tx = (X_OUT - R_C) - 0.10 - 0.30 * w["stack"] / 7.0
        Nr = m["hullN"] @ Rn.T; Dr = m["hullD"] * s
        dn = Nr[:, 2] < -1e-6; up = Nr[:, 2] > 1e-6
        kx = np.arange(int(math.floor(HV[:, 0].min() / CELL)), int(math.ceil(HV[:, 0].max() / CELL)) + 1)
        ky = np.arange(int(math.floor(HV[:, 1].min() / CELL)), int(math.ceil(HV[:, 1].max() / CELL)) + 1)
        KX, KY = np.meshgrid(kx, ky, indexing="ij"); PX = KX.ravel() * CELL; PY = KY.ravel() * CELL
        P = Nr[:, 0:1] * PX[None, :] + Nr[:, 1:2] * PY[None, :]
        zb = ((Dr[dn, None] - P[dn]) / Nr[dn, 2][:, None]).max(0); zt = ((Dr[up, None] - P[up]) / Nr[up, 2][:, None]).min(0)
        okc = zt > zb
        if not okc.any(): okc[:] = True; zb[:] = -low
        KXo, KYo, ZB = KX.ravel()[okc], KY.ravel()[okc], zb[okc]
        best = None
        for xx, yy in cands:
            i = int((xx - CAVB[0]) / CELL); j = int((yy - CAVB[2]) / CELL)
            ii = i + KXo; jj = j + KYo
            v = (ii >= 0) & (ii < hp.nx) & (jj >= 0) & (jj < hp.ny)
            zc = max(float((hp.hf[ii[v], jj[v]] - ZB[v]).max()) if v.any() else 0, FLOOR_Z + low) + 0.012
            if zc + hi[2] > HEAP_CAP + 0.05: continue
            cost = zc + VW * abs(xx - tx) + 0.15 * abs(yy) + rr.uniform(0, 0.008)
            if best is None or cost < best[0]: best = (cost, xx, yy, zc)
        if best is None: return False, "ceiling"
        _, x, y, zc = best
        ob = bpy.data.objects.new(c["name"], m["prox"]); sc.collection.objects.link(ob)
        ob.matrix_world = Matrix.Translation(Vector((x + ox, y, zc))) @ Rc.to_4x4() @ Matrix.Diagonal((s, s, s, 1))
        ext = HV.max(0) - HV.min(0)
        rb = set_rb(ob, "ACTIVE", max(0.02, float(np.prod(ext)) * 600))
        rb.collision_shape = "CONVEX_HULL"; rb.mesh_source = "BASE"; rb.use_margin = True; rb.collision_margin = MARGIN
        w.update(ob=ob, m=m, probe=PROBE * 0.5 * ext)
        return True, ""

    def local(M, c):
        M = M.copy(); M[:3, 3] -= c["origin"]; return M

    def evaluate(w):
        m = w["m"]; c = w["c"]
        r = rec_world(m, local(w["Mw"], c), c["s"])
        r.update(name=c["name"], stack=w["stack"], k=w["k"])
        V = world_pts(m["verts"], r["M"])
        bad = []
        over = cav_over(V)
        if over > -0.0005: bad.append("outside cavity %.1f mm" % (over * 1000))
        gap, what = support_gap(r, FLOOR_Z, c["heap"].bodies)
        r["gap"] = gap; r["support"] = what
        if gap > FLOAT_MAX: bad.append("floats %.1f mm" % (gap * 1000))
        return (not bad), ",".join(bad), r

    def attempt(pending):
        sc.frame_set(1)
        ok = []
        for w in pending:
            good, why = spawn(w)
            if good: ok.append(w)
            else: w["why"] = why; st["rej"][why] = st["rej"].get(why, 0) + 1
        if not ok: return [], 0
        bpy.context.view_layer.update()
        prev = {}; f = 1
        for f in range(2, MAXF + 2):
            sc.frame_set(f); st["frames"] += 1
            if f >= MINF and f % 3 == 0:
                dg = bpy.context.evaluated_depsgraph_get(); mx = 0.0
                for w in ok:
                    pts = world_pts(w["probe"], np.array(w["ob"].evaluated_get(dg).matrix_world))
                    if w["uid"] in prev: mx = max(mx, float(np.abs(pts - prev[w["uid"]]).max()))
                    prev[w["uid"]] = pts
                if mx < 6e-4 and f > MINF + 3: break
        dg = bpy.context.evaluated_depsgraph_get()
        for w in ok: w["Mw"] = np.array(w["ob"].evaluated_get(dg).matrix_world)
        return ok, f

    def run_batch(batch):
        pending = list(batch); tries = 0
        while pending and tries < NTRY:
            tries += 1; st["tries"] += 1
            ok, f = attempt(pending)
            failed = [w for w in pending if w not in ok]
            accepted = []
            for w in ok:
                good, why, r = evaluate(w)
                if good: r["unsettled"] = f >= MAXF + 1; accepted.append((w, r))
                else:
                    key = why.split(" ")[0]; st["rej"][key] = st["rej"].get(key, 0) + 1
                    w["why"] = why; failed.append(w)
            for w in ok:
                if w in failed: bpy.data.objects.remove(w["ob"])
            sc.frame_set(1)
            for w, r in accepted:
                w["ob"].matrix_world = Matrix(w["Mw"].tolist()); w["ob"].rigid_body.type = "PASSIVE"
                r["id"] = frz[0]; frz[0] += 1
                w["c"]["heap"].bodies.append(r); w["c"]["heap"].add_hull(r["N"], r["D"], r["lo"], r["hi"]); allr.append(r)
            pending = failed
        st["drops"] += len(pending)
        for w in pending: w["c"].setdefault("dropped", []).append((w["stack"], w["k"], w.get("why")))

    uid = 0; t0 = time.time()
    for stack in range(8):
        for k in range(PER_STACK[stack]):
            batch = []
            for c in items:
                batch.append(dict(c=c, stack=stack, k=k, uid=uid)); uid += 1
            run_batch(batch)
        print("HR1 stack", stack, "bodies", len(allr), "frames", st["frames"], "tries", st["tries"], "dropped", st["drops"],
              "t=%.0fs" % (time.time() - t0), flush=True)
    for o in [o for o in bpy.data.objects if o.rigid_body is not None]: bpy.data.objects.remove(o)
    bpy.ops.rigidbody.world_remove()
    sc.frame_set(1)
    return allr, st

RES = {}
todo = list(ITEM.values())
for p in range(4):
    for c in todo: c["heap"] = Heap(CAVB); c["dropped"] = []
    r, st = simulate(todo, 5 + 13 * p)
    print("HR1 PASS", p, "rejections", st["rej"], flush=True)
    nxt = []
    for c in todo:
        rs = [x for x in r if x["name"] == c["name"]]
        top = max((float(world_pts(merged(c["name"])["verts"], x["M"])[:, 2].max()) for x in rs), default=0)
        RES[c["name"]] = dict(rs=rs, dropped=list(c["dropped"]), top=top, s=c["s"])
        print("HR1 PASS %d %-14s scale %.4f copies %d dropped %d top %.3f" % (p, c["name"], c["s"], len(rs), len(c["dropped"]), top), flush=True)
        if c["dropped"] and p < 3:
            c["s"] *= 0.92; nxt.append(c)
    todo = nxt
    if not todo: break

# ---------- checks ----------
def interpenetration(res):
    worst = 0.0; n = 0
    for i, a in enumerate(res):
        for j, b in enumerate(res):
            if i == j or a["name"] != b["name"]: continue
            if (a["lo"] > b["hi"]).any() or (b["lo"] > a["hi"]).any(): continue
            d = b["D"][None, :] - a["hv"] @ b["N"].T
            ins = (d > 0).all(1)
            if ins.any(): worst = max(worst, float(d[ins].min(1).max())); n += 1
    return worst, n

def mesh_bvh(name, M):
    m = merged(name); V = world_pts(m["verts"], M)
    return BVHTree.FromPolygons([Vector(v) for v in V], m["tri"], all_triangles=True), V

ALLRES = [x for v in RES.values() for x in v["rs"]]
pen, npen = interpenetration(ALLRES)
mm_pairs = 0
for name, v in RES.items():
    bv = [mesh_bvh(name, x["M"])[0] for x in v["rs"]]
    for i in range(len(bv)):
        for j in range(i + 1, len(bv)):
            if bv[i].overlap(bv[j]): mm_pairs += 1
fl_worst = 0.0; fl_over = 0
for name, v in RES.items():
    earlier = []
    for x in sorted(v["rs"], key=lambda q: q["id"]):
        g, _w = support_gap(x, FLOOR_Z, earlier); earlier.append(x)
        fl_worst = max(fl_worst, g); fl_over += int(g > FLOAT_MAX)
cav_worst = max(cav_over(world_pts(merged(x["name"])["verts"], x["M"])) for x in ALLRES)
# every hide's pile in every bay vs the frame (mesh triangles), and the floor
clip = {}
for name, v in RES.items():
    for b in range(NB):
        Mb = np.array(BAYM[b])
        for x in v["rs"]:
            bvh, V = mesh_bvh(name, Mb @ x["M"])
            if FBVH.overlap(bvh) or V[:, 2].min() < DECK: clip.setdefault(name, []).append((b, x["stack"], x["k"]))
nclip = sum(len(v) for v in clip.values())
print("HR1 CHECK clipping (every hide in every bay, mesh vs frame):", nclip, {k: len(v) for k, v in clip.items()}, list(clip.values())[:2], flush=True)
print("HR1 CHECK mesh-mesh overlaps between copies:", mm_pairs, "| hull interpenetration max %.2f mm (%d pairs)" % (pen * 1000, npen),
      "| float worst %.2f mm, over 5 mm: %d | cavity worst %.2f mm (<=0 inside)" % (fl_worst * 1000, fl_over, cav_worst * 1000), flush=True)

# ---------- export (Unity prefab space: ux = -bx, uy = bz, uz = -by) ----------
CB2U = Matrix(((-1, 0, 0), (0, 0, 1), (0, -1, 0)))
def b2u(v): return [round(-float(v[0]), 4), round(float(v[2]), 4), round(-float(v[1]), 4)]
def uquat(Rb):
    q = (CB2U @ Matrix(Rb) @ CB2U.transposed()).to_quaternion(); q.normalize()
    if q.w < 0: q = -q
    return [round(c, 5) for c in (q.x, q.y, q.z, q.w)]
def qmat_u(q):
    return Quaternion((q[3], q[0], q[1], q[2])).to_matrix()

def bounds_low(name, M):
    """lowest z of the copy's rotated bounds box (what the mod's floor lift tests)."""
    m = merged(name); he = m["size"] / 2
    return float(M[2, 3] - np.abs(M[2, :3]) @ he)

units = []; rot_err = 0.0
for b in range(NB):
    name = BAY_ITEMS[b]
    if name not in RES: continue
    m = merged(name); Mb = np.array(BAYM[b]); longest = float(m["size"].max())
    for st_ in range(8):
        cps = sorted([x for x in RES[name]["rs"] if x["stack"] == st_], key=lambda q: q["k"])
        Ms = [Mb @ x["M"] for x in cps]
        if Ms:
            V = np.vstack([world_pts(m["verts"], M) for M in Ms]); lo, hi = V.min(0), V.max(0)
            lo[2] = min(lo[2], min(bounds_low(name, M) for M in Ms)) - 0.002
        else:
            c0 = np.array(BAYM[b].translation); lo, hi = c0 - (0.1, 0.1, 0), c0 + (0.1, 0.1, 0.1)
        c = (lo + hi) / 2
        copies = []
        for M, x in zip(Ms, cps):
            s = RES[name]["s"]; R = M[:3, :3] / s
            copies.append({"item": name, "offset": b2u(M[:3, 3] - c), "quat_xyzw": uquat(R), "scale": round(s, 5),
                           "fit_longest_m": round(s * longest, 4)})
        units.append({"index": len(units), "kind": "hide_stack", "bay": b, "item": name, "stack": st_, "position": b2u(c),
                      "rotation": [0, 0, 0], "box": [round(hi[0] - lo[0], 4), round(hi[2] - lo[2], 4), round(hi[1] - lo[1], 4)],
                      "copies": copies})

bays = []
for b in range(NB):
    Mb = BAYM[b]; Rb = Mb.to_3x3(); qb = uquat(Rb)
    e = (CB2U @ Rb @ CB2U.transposed()).to_euler("ZXY")
    bays.append({"bay": b, "item": BAY_ITEMS[b], "floor_centre": b2u(Mb.translation), "yaw_deg": round(math.degrees(e.y), 3),
                 "rot_quat_xyzw": qb, "angle_from_right_deg": [b * SPAN, (b + 1) * SPAN]})
layouts = {}
for name, v in RES.items():
    m = merged(name); s = v["s"]; longest = float(m["size"].max())
    stacks = []
    for st_ in range(8):
        cps = sorted([x for x in v["rs"] if x["stack"] == st_], key=lambda q: q["k"])
        stacks.append([{"offset": b2u(x["M"][:3, 3]), "rot_quat_xyzw": uquat(x["M"][:3, :3] / s)} for x in cps])
    gaps = [x.get("gap", 0) for x in v["rs"]]
    layouts[name] = {"scale": round(s, 5), "fit_longest_m": round(s * longest, 4), "mode": MODE[name],
                     "true_size_m": [round(float(m["size"][0]), 4), round(float(m["size"][2]), 4), round(float(m["size"][1]), 4)],
                     "copies_by_stack": [len(x) for x in stacks], "stacks": stacks,
                     "check": {"copies": len(v["rs"]), "dropped": len(v["dropped"]), "heap_top_m": round(v["top"], 3),
                               "float_worst_mm": round(1000 * max(gaps), 2) if gaps else 0,
                               "clipping_in_8_bays": len(clip.get(name, [])), "tris_per_copy": len(m["tri"]),
                               "tris_full_bay": len(m["tri"]) * len(v["rs"])}}
# consistency: units rebuilt from hide_layouts + bays with Unity maths match the units' own poses
for u in units:
    bd = bays[u["bay"]]; lay = layouts[u["item"]]["stacks"][u["stack"]]
    qb = qmat_u(bd["rot_quat_xyzw"])
    for cp, lc in zip(u["copies"], lay):
        p1 = Vector(bd["floor_centre"]) + qb @ Vector(lc["offset"]); p0 = Vector(u["position"]) + Vector(cp["offset"])
        r1 = qb @ qmat_u(lc["rot_quat_xyzw"]); r0 = qmat_u(cp["quat_xyzw"])
        rot_err = max(rot_err, (p1 - p0).length, max(abs(a - c) for ra, rc in zip(r1, r0) for a, c in zip(ra, rc)))
print("HR1 CHECK units vs hide_layouts+bays max error %.5f" % rot_err, flush=True)

tris_full = sum(len(merged(u["item"])["tri"]) * len(u["copies"]) for u in units)
doc = {
    "store": "Hide Rack round 1 (static fan): post with 8 hinged frames, each a stretched rawhide; 8 wedge bays on a half-disc deck",
    "slots": 64, "stack_per_unit": 1,
    "frame": {"obj": "HideRack.obj", "atlas": "hiderack_atlas.png 128x128 point", "tris": ntris,
              "size_m": [round(float(FMAX[0] - FMIN[0]), 3), round(float(FMAX[2] - FMIN[2]), 3), round(float(FMAX[1] - FMIN[1]), 3)],
              "frames": [dict(f, hinge_axis_unity=b2u((0, YP, 0)), rows_m=ROWS[f["row"]]) for f in FRAME_INFO],
              "frames_note": "static in round 1; angle_deg from the right-hand back line (Unity -x) towards the front (+z), about the post axis"},
    "space": "Unity prefab space, metres, y up, +z front, origin = footprint centre on the ground (Blender export: ux=-bx, uy=bz, uz=-by).",
    "items": {"bay_items": BAY_ITEMS, "extra_items": EXTRA_ITEMS,
              "note": "all hides and pelts in the game files; extra_items exist but are not obtainable in vanilla today"},
    "unit_semantics": ("64 units = 8 bays x 8 units, one stack per unit, listed bay by bay in fill order (bay key = group: one hide kind per "
                       "bay). Each copy: the item's model in the mod's item space, scaled uniformly so its longest bounds side is fit_longest_m, "
                       "rotated by quat_xyzw about its bounds centre, bounds centre at unit.position + offset. unit.box bottom = the lowest "
                       "corner of any copy's rotated bounds (the never-below-the-floor lift leaves the settled pile alone). The poses are "
                       "those of the bay's own item (bays[].item)."),
    "units": units,
    "bays": bays,
    "hide_layouts": layouts,
    "hide_layouts_doc": ("Every hide's own physics-settled pile in BAY-LOCAL space, for showing any hide in any bay: stacks[k] = the copies of the "
                         "k-th stack of that hide in a bay. World (prefab) pose: bounds centre = bays[b].floor_centre + bays[b].rot * offset, "
                         "rotation = bays[b].rot * rot_quat_xyzw, uniform scale so the longest bounds side is fit_longest_m (= scale x the "
                         "item's true size). Settled once in the common wedge cavity and checked against the frame in all 8 bays."),
    "physics": ("Blender rigid body (Bullet): convex hulls, friction 0.8, restitution 0, damping 0.5/0.95, margin %.1f mm, substeps 20, iterations 40; "
                "copy by copy (stacks 2,1,2,1,2,1,2,1), earlier copies frozen; a copy is dropped again when it ends outside the wedge cavity "
                "(divider faces + 6 mm, rim, post foot, under deck + %.2f m) or more than %.0f mm from a support." % (MARGIN * 1000, HEAP_CAP, FLOAT_MAX * 1000)),
    "checks": {"clipping_every_hide_every_bay": nclip, "mesh_overlaps_between_copies": mm_pairs, "hull_interpenetration_max_mm": round(pen * 1000, 2),
               "float_worst_mm": round(fl_worst * 1000, 2), "float_over_5mm": fl_over, "cavity_worst_mm": round(cav_worst * 1000, 2),
               "dropped": {k: len(v["dropped"]) for k, v in RES.items()}, "units_vs_layouts_max_err": round(rot_err, 6),
               "contents_tris_full": tris_full, "frame_tris": ntris},
}
os.makedirs(OUTA, exist_ok=True)
save_atlas(ATLAS, os.path.join(OUTA, "hiderack_atlas.png"))
bpy.ops.object.select_all(action="DESELECT")
for o in PARTS: o.select_set(True)
tmp = os.path.join(OUTA, "HideRack.part.obj")
bpy.ops.wm.obj_export(filepath=tmp, export_selected_objects=True, export_materials=False, export_triangulated_mesh=True,
                      forward_axis="NEGATIVE_Z", up_axis="Y")
os.replace(tmp, os.path.join(OUTA, "HideRack.obj"))
tmp = os.path.join(OUTA, "hiderack_anchors.json.tmp")
with open(tmp, "w") as fh: json.dump(doc, fh, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o))
os.replace(tmp, os.path.join(OUTA, "hiderack_anchors.json"))
print("HR1 wrote", OUTA, "units", len(units), "copies", sum(len(u["copies"]) for u in units), "contents tris full", tris_full, flush=True)
for o in PARTS: bpy.data.objects.remove(o, do_unlink=True)

if "--no-render" in argv:
    print("DONE"); sys.exit(0)

# ---------- renders, replayed from the exported files the mod's way ----------
C = Matrix(((-1, 0, 0), (0, 0, 1), (0, -1, 0)))
def u2b_pos(p): return Vector((-p[0], -p[2], p[1]))
def u2b_rot(q): return C.transposed() @ Quaternion((q[3], q[0], q[1], q[2])).to_matrix() @ C
def import_frame(objpath, png, dx, dy):
    before = set(bpy.data.objects)
    bpy.ops.wm.obj_import(filepath=objpath, forward_axis="NEGATIVE_Z", up_axis="Y")
    new = [o for o in bpy.data.objects if o not in before]
    m = atlas_mat(os.path.basename(png), bpy.data.images.load(png))
    for o in new:
        o.data.materials.clear(); o.data.materials.append(m); o.location = (dx, dy, 0)
    return new
LIFTS = {"n": 0}
def spawn_file(fill, dx, dy, tag):
    import_frame(os.path.join(OUTA, "HideRack.obj"), os.path.join(OUTA, "hiderack_atlas.png"), dx, dy)
    d = json.load(open(os.path.join(OUTA, "hiderack_anchors.json")))
    nper = int(round(8 * fill))
    for u in d["units"]:
        if u["stack"] >= nper: continue
        floor = u["position"][1] - u["box"][1] / 2
        for cp in u["copies"]:
            m = merged(cp["item"]); s = cp["fit_longest_m"] / float(m["size"].max())
            Rb = u2b_rot(cp["quat_xyzw"]); p = u2b_pos([a + b for a, b in zip(u["position"], cp["offset"])])
            low = p.z - float(np.abs(np.array(Rb)[2]) @ (m["size"] / 2 * s))
            if low < floor - 1e-4: p.z += floor - low; LIFTS["n"] += 1
            ob = bpy.data.objects.new(f"{tag}_item", m["mesh"]); sc.collection.objects.link(ob)
            ob.matrix_world = Matrix.Translation(p + Vector((dx, dy, 0))) @ Rb.to_4x4() @ Matrix.Diagonal((s, s, s, 1))

cam = setup_world()
bpy.data.objects["post_1.8m"].location = (1.55, -0.3, 0.9)
EYE = 1.75
spawn_file(0.0, 0, 0, "empty")
spawn_file(0.5, 0, 30, "half")
spawn_file(1.0, 0, 60, "full")
for yy in (30, 60):
    bpy.ops.mesh.primitive_cylinder_add(radius=0.06, depth=1.8, location=(1.55, yy - 0.3, 0.9))
    bpy.context.active_object.data.materials.append(bpy.data.materials["plain"])
print("HR1 MOD FLOOR LIFTS", LIFTS, flush=True)
view(cam, -32, 4.3, EYE, (0, 0, 0.9)); render(os.path.join(OUT, "hiderack1-empty-34.png"))
view(cam, -32, 4.3, EYE, (0, 30, 0.9)); render(os.path.join(OUT, "hiderack1-half-34.png"))
view(cam, -32, 4.3, EYE, (0, 60, 0.9)); render(os.path.join(OUT, "hiderack1-full-34.png"))
view(cam, 0, 4.0, EYE, (0, 60, 0.95)); render(os.path.join(OUT, "hiderack1-full-front-standing.png"))
view(cam, 0, 4.0, EYE, (0, 30, 0.95)); render(os.path.join(OUT, "hiderack1-half-front-standing.png"))
view(cam, -12, 2.6, 2.9, (0, 60, 0.35)); render(os.path.join(OUT, "hiderack1-full-top.png"))
# next to the bunker (round 4 frame) at the same scale
import_frame(os.path.join(REPO, "assets", "bunker_r4", "Bunker.obj"), os.path.join(REPO, "assets", "bunker_r4", "bunker_atlas.png"), -3.4, 60)
view(cam, -12, 8.0, EYE, (-1.6, 60, 0.8)); render(os.path.join(OUT, "hiderack1-next-to-bunker4.png"))
print("DONE")
