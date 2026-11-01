"""Mead Rack, our own mesh and our own texture (no vanilla geometry or texture in it).
Run: blender -b -P meadrack.py -- [--out DIR] [--tag NAME] [--no-ref]
Writes meadrack_atlas.png (128x256, point-filtered), MeadRack.obj (frame), MeadRackItems.obj (one object per stored
item, in fill order) and meadrack.json into assets/meadrack/, then renders three racks (10/50/100 % full) beside the
vanilla wood chest (local rip, reference only) for scale and palette.

Atlas 128x256: eight horizontal strips of 32 px, each tiling along u.
  s7 hewn side grain   s6 end grain (4 ring tiles)   s5 iron   s4 rope
  s3 clay (u<.5 dark flask clay, u>.5 light jug clay)
  s2 swatches: 8 cells of 16 px per row. Row A (v .3125-.375) liquid / paint colour, row B (v .25-.3125) wax colour
  s1 glass (u<.5) and cork (u>.5)       s0 cask staves with iron hoop rows at the rim
Item variants: a content piece is shape x colour. Faces that carry the variant colour have their UV inside strip s2,
so the mod can re-colour a shape by shifting u by (new-old)/8 on exactly those faces.
"""
import bpy, bmesh, sys, os, math, json, random
import numpy as np
from mathutils import Vector, Matrix, Euler, Quaternion

HERE = os.path.dirname(os.path.abspath(__file__))
SLUG = "meadrack"
OUTA = os.path.normpath(os.path.join(HERE, "..", "assets", SLUG))
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = argv[argv.index("--out") + 1] if "--out" in argv else OUTA
TAG = argv[argv.index("--tag") + 1] if "--tag" in argv else SLUG
RIP = "C:/Users/joost/ValheimRip/chests/piece_chest_wood"
os.makedirs(OUTA, exist_ok=True); os.makedirs(OUT, exist_ok=True)
rng = random.Random(7)
PROBE = 1.6 if "--probe" in argv else 1.0      # negative control for the clip check: oversized items must be caught

TEXW, TEXH = 128, 256
DENS = 48.0                      # px per metre, vanilla wood is 47-57
SH = 32 / TEXH                   # v height of one strip
STRIP = {"hewn": 7 * SH, "end": 6 * SH, "iron": 5 * SH, "rope": 4 * SH, "clay": 3 * SH, "swatch": 2 * SH,
         "glass": 1 * SH, "cask": 0.0}
NAMES = ["red", "blue", "green", "amber", "purple", "orange", "teal", "pale"]
ROW_LIQ_V, ROW_WAX_V = 88 / TEXH, 72 / TEXH           # centre v of the two swatch rows

# ---------- texture ----------
def srgb(c): return np.array(c, dtype=np.float32)
WOOD, WOOD_D = srgb((0.38, 0.29, 0.18)), srgb((0.21, 0.16, 0.10))
END, END_D = srgb((0.55, 0.45, 0.31)), srgb((0.35, 0.27, 0.17))
IRON, IRON_D = srgb((0.22, 0.21, 0.20)), srgb((0.09, 0.09, 0.09))
ROPE, ROPE_D = srgb((0.45, 0.37, 0.24)), srgb((0.22, 0.17, 0.10))
CLAY_A, CLAY_A_D = srgb((0.34, 0.25, 0.18)), srgb((0.18, 0.13, 0.10))
CLAY_B, CLAY_B_D = srgb((0.52, 0.40, 0.28)), srgb((0.32, 0.24, 0.17))
GLASS, GLASS_L = srgb((0.14, 0.18, 0.15)), srgb((0.30, 0.36, 0.30))
CORK, CORK_D = srgb((0.50, 0.38, 0.24)), srgb((0.30, 0.22, 0.14))
# muted accents: liquid / paint, and a deeper wax
LIQ = [(0.52, 0.17, 0.15), (0.26, 0.36, 0.55), (0.31, 0.46, 0.26), (0.72, 0.54, 0.20),
       (0.43, 0.27, 0.48), (0.68, 0.38, 0.16), (0.21, 0.46, 0.45), (0.76, 0.70, 0.56)]
WAX = [(0.42, 0.12, 0.11), (0.19, 0.28, 0.44), (0.22, 0.35, 0.18), (0.58, 0.42, 0.13),
       (0.32, 0.19, 0.37), (0.54, 0.29, 0.11), (0.14, 0.35, 0.35), (0.64, 0.58, 0.45)]

def build_atlas():
    nr = np.random.default_rng(5)
    img = np.zeros((TEXH, TEXW, 3), np.float32)          # row 0 = v 0 (bottom)
    x = np.arange(TEXW)[None, :].repeat(32, 0).astype(np.float32)
    y = np.arange(32)[:, None].repeat(TEXW, 1).astype(np.float32)
    tile = lambda k: 2 * math.pi * k / TEXW
    mix = lambda a, b, t: a * (1 - t[..., None]) + b * t[..., None]
    rows = lambda s: slice(s * 32, s * 32 + 32)
    # s7 hewn side grain
    g = np.sin(y * 1.25 + 1.6 * np.sin(x * tile(2) + y * 0.15) + 0.7 * np.sin(x * tile(5)))
    t = np.clip((g - 0.55) * 2.5, 0, 1) * 0.65 + nr.random((32, TEXW)) * 0.18
    t += np.clip(1 - np.minimum(y, 31 - y) / 3.0, 0, 1) * 0.35
    img[rows(7)] = mix(WOOD, WOOD_D, np.clip(t, 0, 1))
    # s6 end grain, four 32x32 ring tiles
    for k in range(4):
        cx, cy = 15.5 + nr.uniform(-2, 2), 15.5 + nr.uniform(-2, 2)
        xx, yy = np.meshgrid(np.arange(32), np.arange(32))
        d = np.hypot(xx - cx, yy - cy) + 0.6 * np.sin(np.arctan2(yy - cy, xx - cx) * 3 + k)
        t = (np.sin(d * 1.5) * 0.5 + 0.5) * 0.45 + nr.random((32, 32)) * 0.15
        t = np.where(d > 13.5, 0.95, t)
        img[6 * 32:7 * 32, 32 * k:32 * k + 32] = mix(END, END_D, t)
    # s5 iron
    t = nr.random((32, TEXW)) * 0.4 + np.clip(1 - np.minimum(y, 31 - y) / 4.0, 0, 1) * 0.5
    img[rows(5)] = mix(IRON, IRON_D, np.clip(t, 0, 1))
    # s4 rope: twisted diagonal strands, period 8 px so it tiles in u
    t = np.sin(x * tile(16) + y * 0.9) * 0.5 + 0.5
    t = np.clip(t * 0.8 + nr.random((32, TEXW)) * 0.25, 0, 1)
    img[rows(4)] = mix(ROPE, ROPE_D, t)
    # s3 clay: left dark, right light, mottled
    t = np.clip(nr.random((32, TEXW)) * 0.7 + 0.1 * np.sin(x * 0.4 + y * 0.3), 0, 1)
    img[rows(3), :64] = mix(CLAY_A, CLAY_A_D, t)[:, :64]
    img[rows(3), 64:] = mix(CLAY_B, CLAY_B_D, t)[:, 64:]
    # s2 swatches: row A rows 80-95 liquid / paint, row B rows 64-79 wax
    for k in range(8):
        for r0, cols in ((80, LIQ), (64, WAX)):
            n = 1 + (nr.random((16, 16, 1)) - 0.5) * 0.10
            img[r0:r0 + 16, 16 * k:16 * k + 16] = np.clip(srgb(cols[k]) * n, 0, 1)
    # s1 glass (left) and cork (right)
    t = np.clip(nr.random((32, TEXW)) ** 3 * 1.2, 0, 1)
    img[rows(1), :64] = mix(GLASS, GLASS_L, t)[:, :64]
    t = np.clip(nr.random((32, TEXW)) * 0.8, 0, 1)
    img[rows(1), 64:] = mix(CORK, CORK_D, t)[:, 64:]
    # s0 cask staves: 8 staves of 16 px, iron hoop in the first 7 rows (the rim)
    stave = (x // 16).astype(int)
    tone = nr.random(8)[stave] * 0.40
    edge = ((x % 16) < 1.5) | ((x % 16) > 14.5)
    t = np.clip(tone + nr.random((32, TEXW)) * 0.12 + edge * 0.45, 0, 1)
    wood = mix(WOOD, WOOD_D, t)
    hoop = mix(IRON, IRON_D, np.clip(nr.random((32, TEXW)) * 0.5, 0, 1))
    hoop[7] *= 0.55
    img[rows(0)] = np.where((y < 7)[..., None], hoop, wood)
    im = bpy.data.images.new("meadrack_atlas", TEXW, TEXH, alpha=False)
    px = np.concatenate([np.clip(img, 0, 1), np.ones((TEXH, TEXW, 1), np.float32)], 2)
    im.pixels.foreach_set(px.ravel())
    im.filepath_raw = os.path.join(OUTA, "meadrack_atlas.png"); im.file_format = "PNG"; im.save()
    return im

# ---------- geometry helpers ----------
PARTS, ITEMS, CHK = [], [], []     # frame objects, content objects (fill order), solid AABBs for the clip check
UV = None

def uv_face(f, kind, long_axis, seed):
    """Project one face of a timber/strap onto its strip. long_axis 0/1/2 (local) runs along u."""
    n = f.normal
    ax = max(range(3), key=lambda i: abs(n[i]))
    tang = [i for i in range(3) if i != ax]
    if kind == "hewn" and ax == long_axis:          # cut end of a timber
        k = seed % 4
        cs = [l.vert.co for l in f.loops]
        c = sum(cs, Vector()) / len(cs)
        ext = max(max(abs(v[tang[0]] - c[tang[0]]), abs(v[tang[1]] - c[tang[1]])) for v in cs) or 1
        for l in f.loops:
            a = (l.vert.co[tang[0]] - c[tang[0]]) / ext; b = (l.vert.co[tang[1]] - c[tang[1]]) / ext
            l[UV].uv = ((k + 0.5 + a * 0.45) / 4, STRIP["end"] + (0.5 + b * 0.45) * SH)
        return
    ua = long_axis if long_axis in tang else tang[0]
    va = tang[1] if ua == tang[0] else tang[0]
    off = (seed * 0.37) % 1
    vs = [l.vert.co[va] for l in f.loops]
    vmin, span = min(vs), max(max(vs) - min(vs), 1e-4)
    vscale = min(1.0, (32 / DENS) / span)
    base = STRIP[kind]
    for l in f.loops:
        u = l.vert.co[ua] * DENS / TEXW + off
        v = base + ((l.vert.co[va] - vmin) * vscale * DENS / TEXH) * 0.94 + 1.0 / TEXH
        l[UV].uv = (u, v)

def uv_flat(f, spec):
    """Flat-colour patch for lathe items. spec: ('liq'|'wax', colour) / ('clay'|'clay2'|'glass'|'cork',)."""
    kind = spec[0]
    if kind in ("liq", "wax"):
        cu = (spec[1] + 0.5) / 8; cv = ROW_LIQ_V if kind == "liq" else ROW_WAX_V
        for l in f.loops:
            l[UV].uv = (cu + rng.uniform(-0.03, 0.03), cv + rng.uniform(-0.011, 0.011))
        return
    if kind == "endg":
        cu, cv = rng.uniform(0.05, 0.95), STRIP["end"] + rng.uniform(0.3, 0.7) * SH
    elif kind == "rope":
        cu, cv = rng.uniform(0, 1), STRIP["rope"] + rng.uniform(0.03, 0.09)
    else:
        half = {"clay": 0.0, "clay2": 0.5, "glass": 0.0, "cork": 0.5}[kind]
        base = STRIP["clay" if kind.startswith("clay") else "glass"]
        cu, cv = half + rng.uniform(0.04, 0.46), base + rng.uniform(0.02, 0.105)
    for l in f.loops: l[UV].uv = (cu + rng.uniform(-0.004, 0.004), cv + rng.uniform(-0.004, 0.004))

def box_into(bm, size, pos, kind, rot=(0, 0, 0), jitter=0.02, bevel=0.02, flat=None):
    """A hewn box (or strap, rope wrap, wax cap) added to bm. kind: hewn/iron/rope, or flat=spec for item parts."""
    global UV
    before = set(bm.faces)
    verts = bmesh.ops.create_cube(bm, size=1.0)["verts"]
    for v in verts: v.co = Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2]))
    la = max(range(3), key=lambda i: size[i])
    for v in verts:
        for i in range(3):
            if i != la: v.co[i] += rng.uniform(-jitter, jitter)
    if bevel > 0:
        edges = list({e for v in verts for e in v.link_edges})
        bmesh.ops.bevel(bm, geom=edges, offset=bevel, segments=1, affect="EDGES")
    new = [f for f in bm.faces if f not in before]
    bm.normal_update()
    UV = bm.loops.layers.uv.verify()
    seed = rng.randrange(1000)
    for j, f in enumerate(new):
        if flat is not None: uv_flat(f, flat)
        else: uv_face(f, kind, la, seed + j % 2)
    vs = list({v for f in new for v in f.verts})
    bmesh.ops.rotate(bm, verts=vs, cent=(0, 0, 0), matrix=Euler([math.radians(a) for a in rot]).to_matrix())
    bmesh.ops.translate(bm, verts=vs, vec=Vector(pos))

def to_object(bm, name, into):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = False
    ob = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(ob)
    ob.data.materials.append(MAT); into.append(ob)
    return ob

def timber(name, size, pos, kind="hewn", rot=(0, 0, 0), jitter=0.012, bevel=0.014, chk=False):
    bm = bmesh.new()
    box_into(bm, size, (0, 0, 0), kind, rot, jitter, bevel)
    bmesh.ops.translate(bm, verts=bm.verts[:], vec=Vector(pos))
    ob = to_object(bm, name, PARTS)
    if chk:
        cs = [v.co for v in ob.data.vertices]
        CHK.append((name, Vector(min(c[i] for c in cs) for i in range(3)), Vector(max(c[i] for c in cs) for i in range(3))))

# ---------- the rack ----------
PX, PY, PS = 0.75, 0.20, 0.10                  # post centre x / y, post section
ZB = [0.16, 0.54, 0.92, 1.30, 1.70]            # shelf board centres; the last one is the crown base
BT = 0.05                                      # shelf board thickness
DIVX = [-0.2417, 0.2417]                       # cubby dividers (0.05 thick)
CUBX = [-0.4833, 0.0, 0.4833]                  # cubby centres (clear width 0.433)
BACK_Y = 0.19

def build_frame():
    h = 1.66
    for sx in (-1, 1):
        for sy in (-1, 1):
            timber("post", (PS, PS, h), (sx * PX, sy * PY, 0.07 + h / 2),
                   rot=(rng.uniform(-0.3, 0.3), rng.uniform(-0.3, 0.3), 0), jitter=0.01, bevel=0.012, chk=True)
        timber("sill", (0.13, 0.58, 0.08), (sx * PX, 0, 0.04), rot=(0, 0, rng.uniform(-1, 1)), chk=True)
    for z in ZB[:4]:
        timber("shelf", (1.56, 0.44, BT), (0, 0, z), rot=(0, 0, rng.uniform(-0.4, 0.4)), jitter=0.006, bevel=0.012, chk=True)
    timber("crownbase", (1.56, 0.44, 0.06), (0, 0, ZB[4]), rot=(0, 0, rng.uniform(-0.4, 0.4)), jitter=0.006, bevel=0.012, chk=True)
    timber("top", (1.74, 0.56, 0.07), (0, 0, 1.765), rot=(0, 0, rng.uniform(-0.3, 0.3)), jitter=0.008, bevel=0.016, chk=True)
    for sx in (-1, 1):                         # carved horns on the top board
        timber("horn", (0.07, 0.07, 0.15), (sx * 0.83, 0, 1.87), rot=(0, sx * 26, rng.uniform(-3, 3)), jitter=0.008, bevel=0.01)
    for i in range(8):                         # carved tooth row under the top board
        x = -0.6 + i * 0.1714
        timber("tooth", (0.09, 0.035, 0.05 + (0.02 if i % 2 else 0)), (x, -0.238, 1.685 - (0.01 if i % 2 else 0)),
               jitter=0.004, bevel=0.004, chk=True)
    for r in range(4):
        zc = (ZB[r] + ZB[r + 1]) / 2
        hh = ZB[r + 1] - ZB[r] - BT + 0.02
        for dx in DIVX:
            timber("divider", (0.05, 0.37, hh), (dx, -0.015, zc), rot=(0, 0, rng.uniform(-0.3, 0.3)), jitter=0.006,
                   bevel=0, chk=True)
        timber("back", (1.42, 0.03, hh + 0.04), (0, BACK_Y, zc), rot=(0, 0, rng.uniform(-0.3, 0.3)), jitter=0.004,
               bevel=0, chk=True)
    # iron: a band round each front post above every shelf, a strap along the shelf front, one rivet
    for sx in (-1, 1):
        for z in ZB[:4]:
            timber("band", (PS + 0.035, PS + 0.035, 0.045), (sx * PX, -PY, z + 0.075), kind="iron", jitter=0.002, bevel=0.004)
            timber("strap", (0.26, 0.012, 0.045), (sx * 0.565, -0.226, z), kind="iron", jitter=0.002, bevel=0)
            timber("rivet", (0.03, 0.03, 0.03), (sx * 0.50, -0.236, z), kind="iron", jitter=0, bevel=0)
    # side braces outside the posts, lashed with rope at both ends
    ang = math.degrees(math.atan2(1.3, 0.4))
    for sx in (-1, 1):
        timber("brace", (0.04, math.hypot(0.4, 1.3), 0.075), (sx * 0.822, 0, 0.85), rot=(sx * ang, 0, 0), jitter=0.006, bevel=0.008)
        for sy, zz in ((-1 if sx > 0 else 1, 0.25), (1 if sx > 0 else -1, 1.45)):
            for dz in (-0.03, 0.03):
                timber("lash", (0.17, 0.13, 0.04), (sx * 0.77, sy * PY, zz + dz), kind="rope", jitter=0.004, bevel=0.006)

# ---------- contents ----------
def lathe_into(bm, prof, sides, bands, capb, capt, wob=0.004):
    """prof [(r, z)] rings; bands: per ring pair a spec ('liq', ci) ... or ('cask', t0, t1); capb/capt specs."""
    global UV
    UV = bm.loops.layers.uv.verify()
    rings = []
    for r, z in prof:
        a0 = rng.uniform(-0.12, 0.12)
        rings.append([bm.verts.new(((r * (1 + rng.uniform(-0.04, 0.04))) * math.cos(a0 + 2 * math.pi * i / sides),
                                    (r * (1 + rng.uniform(-0.04, 0.04))) * math.sin(a0 + 2 * math.pi * i / sides),
                                    z + rng.uniform(-wob, wob))) for i in range(sides)])
    for b, spec in enumerate(bands):
        for i in range(sides):
            j = (i + 1) % sides
            f = bm.faces.new((rings[b][i], rings[b][j], rings[b + 1][j], rings[b + 1][i]))
            if spec[0] == "cask":
                t0, t1 = spec[1], spec[2]
                us = [i / sides + 0.004, (i + 1) / sides - 0.004, (i + 1) / sides - 0.004, i / sides + 0.004]
                ts = [t0, t0, t1, t1]
                for l, u, t in zip(f.loops, us, ts): l[UV].uv = (u, STRIP["cask"] + (0.03 + t * 0.94) * SH)
            else:
                uv_flat(f, spec)
    for ring, spec, rev in ((rings[0], capb, True), (rings[-1], capt, False)):
        f = bm.faces.new(reversed(ring) if rev else ring)
        if spec[0] == "cask": spec = ("wax", 0)
        uv_flat(f, spec)

def item_flask(bm, ci):
    lathe_into(bm, [(0.056, 0), (0.084, 0.055), (0.050, 0.120), (0.031, 0.165), (0.031, 0.188)], 6,
               [("liq", ci), ("liq", ci), ("glass",), ("glass",)], ("glass",), ("glass",))
    box_into(bm, (0.060, 0.060, 0.046), (0, 0, 0.206), "hewn", jitter=0.003, bevel=0, flat=("wax", ci))

def item_vial(bm, ci):
    lathe_into(bm, [(0.040, 0), (0.049, 0.090), (0.029, 0.172), (0.026, 0.212)], 5,
               [("liq", ci), ("liq", ci), ("glass",)], ("glass",), ("glass",))
    box_into(bm, (0.046, 0.046, 0.044), (0, 0, 0.228), "hewn", jitter=0.002, bevel=0, flat=("wax", ci))

def item_jug(bm, ci):
    lathe_into(bm, [(0.062, 0), (0.090, 0.065), (0.058, 0.135), (0.044, 0.178)], 6,
               [("clay2",), ("wax", ci), ("rope",)], ("clay2",), ("wax", ci))

def item_cask(bm, ci):
    lathe_into(bm, [(0.066, -0.15), (0.092, -0.15), (0.122, -0.055), (0.122, 0.055), (0.092, 0.15), (0.066, 0.15)], 8,
               [("endg",), ("cask", 0.0, 1.0), ("cask", 1.0, 1.0), ("cask", 1.0, 0.0), ("endg",)], ("wax", ci), ("wax", ci))

SHAPES = {"flask": item_flask, "vial": item_vial, "jug": item_jug, "cask": item_cask}

# hand-set assortment, bottom shelf first, left to right: (shape, colour). Colours stand for mead / potion types.
LAYOUT = [
    [[("cask", 3)], [("cask", 0)], [("jug", 5), ("jug", 5), ("jug", 7)]],
    [[("flask", 0), ("flask", 0), ("flask", 4)], [("vial", 1), ("vial", 1), ("vial", 1)], [("cask", 2)]],
    [[("flask", 2), ("flask", 2), ("flask", 2)], [("jug", 3), ("jug", 6)], [("vial", 0), ("vial", 5)]],
    [[("vial", 4), ("vial", 1)], [("flask", 1), ("flask", 1)], [("flask", 3), ("jug", 7)]],
]
SLOTS = {1: [(0.0, -0.01)], 2: [(-0.095, -0.07), (0.095, -0.07)],
         3: [(-0.09, -0.09), (0.09, -0.09), (0.0, 0.065)]}

def build_items():
    n = 0
    for r, row in enumerate(LAYOUT):
        zt = ZB[r] + BT / 2 + 0.008
        for c, cub in enumerate(row):
            for s, (shape, ci) in enumerate(cub):
                bm = bmesh.new()
                SHAPES[shape](bm, ci)
                dx, dy = SLOTS[len(cub)][s]
                lie = shape == "cask"
                yaw = rng.uniform(-7, 7) if lie else rng.uniform(0, 360)
                tilt = (0, 0) if lie else (rng.uniform(-1.2, 1.2), rng.uniform(-1.2, 1.2))
                sc = rng.uniform(0.97, 1.04) * (1.0 if s == 2 and len(cub) == 3 else {'cask': 1.08, 'vial': 1.12, 'jug': 1.10}.get(shape, 1.12)) * PROBE
                M = (Matrix.Translation((CUBX[c] + dx, dy, 0)) @ Euler((0, 0, math.radians(yaw))).to_matrix().to_4x4()
                     @ Euler((math.radians(tilt[0]) + (math.pi / 2 if lie else 0), math.radians(tilt[1]), 0)).to_matrix().to_4x4()
                     @ Matrix.Diagonal((sc, sc, sc, 1)))
                for v in bm.verts: v.co = M @ v.co
                dz = zt - min(v.co.z for v in bm.verts)
                for v in bm.verts: v.co.z += dz
                to_object(bm, f"item_{n:03d}_{shape}_{NAMES[ci]}", ITEMS); n += 1

# ---------- scene ----------
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
atlas = build_atlas()
MAT = bpy.data.materials.new("meadrack"); MAT.use_nodes = True
nt = MAT.node_tree; bsdf = nt.nodes["Principled BSDF"]
ti = nt.nodes.new("ShaderNodeTexImage"); ti.image = atlas; ti.interpolation = "Closest"
nt.links.new(ti.outputs["Color"], bsdf.inputs["Base Color"])
bsdf.inputs["Roughness"].default_value = 0.8
FILLS = (0.1, 0.5, 1.0)
def tris(obs): return sum(len(p.vertices) - 2 for o in obs for p in o.data.polygons)

def join(obs, name):
    bpy.ops.object.select_all(action="DESELECT")
    for o in obs: o.select_set(True)
    bpy.context.view_layer.objects.active = obs[0]
    bpy.ops.object.join(); ob = bpy.context.active_object; ob.name = name
    return ob

SHR = 0.002
def clipped(o):
    for v in o.data.vertices:
        p = v.co
        if abs(p.x) > 0.70 or p.y < -0.215 or p.y > 0.172: return True       # outside the clear cubby volume
        for _, lo, hi in CHK:
            if all(lo[i] + SHR < p[i] < hi[i] - SHR for i in range(3)): return True
    return False

SPACING = 2.5
racks = []
for k, fill in enumerate(reversed(FILLS)):
    rng.seed(7); PARTS.clear(); ITEMS.clear(); CHK.clear()
    build_frame(); build_items()
    if k == 0 and PROBE != 1.0:
        print("PROBE CLIPPING", sum(clipped(o) for o in ITEMS), "of", len(ITEMS)); sys.exit(0)
    if k == 0:
        bad = [o.name for o in ITEMS if clipped(o)]
        print("CLIPPING", len(bad), "of", len(ITEMS), bad)
        per = {}
        for o in ITEMS:
            sh = o.name.split("_")[2]; per.setdefault(sh, tris([o]))
        stats = {"frame_tris": tris(PARTS), "item_count": len(ITEMS), "items_tris": tris(ITEMS),
                 "tris_per_shape": per, "clip_count": len(bad), "atlas": [TEXW, TEXH],
                 "items": [o.name for o in ITEMS], "colour_names": NAMES,
                 "swatch_cells": {"cell_width_u": 1 / 8, "liquid_row_v": ROW_LIQ_V, "wax_row_v": ROW_WAX_V,
                                  "variant_faces": "uv.v in [0.25, 0.375)"}}
        for obs, fn in ((PARTS, "MeadRack.obj"), (ITEMS, "MeadRackItems.obj")):
            bpy.ops.object.select_all(action="DESELECT")
            for o in obs: o.select_set(True)
            bpy.ops.wm.obj_export(filepath=os.path.join(OUTA, fn), export_selected_objects=True, export_materials=False,
                                  export_triangulated_mesh=True, forward_axis="NEGATIVE_Z", up_axis="Y")
        json.dump(stats, open(os.path.join(OUTA, "meadrack.json"), "w"), indent=1)
        print("RACK", {a: b for a, b in stats.items() if a != "items"})
    shown = ITEMS[:round(fill * len(ITEMS))]
    for o in ITEMS[len(shown):]: bpy.data.objects.remove(o, do_unlink=True)
    ob = join(PARTS + shown, f"rack_{int(fill * 100)}")
    ob.location.x = (len(FILLS) - 1 - k) * SPACING - SPACING
    racks.append(ob)

# vanilla wood chest beside it, for scale and palette (reference only, never exported)
if "--no-ref" not in argv:
    rep = json.load(open("C:/Users/joost/ValheimRip/chests/report.json"))["piece_chest_wood"]["nodes"]
    vimg = bpy.data.images.load(f"{RIP}/woodchest_d.png")
    vm = bpy.data.materials.new("ref"); vm.use_nodes = True
    vt = vm.node_tree.nodes.new("ShaderNodeTexImage"); vt.image = vimg; vt.interpolation = "Closest"
    vm.node_tree.links.new(vt.outputs["Color"], vm.node_tree.nodes["Principled BSDF"].inputs["Base Color"])
    for node in rep:
        if not node["path"].endswith(("/woodchest", "/woodchesttop_closed")): continue
        V, T, F = [], [], []
        for l in open(node["mesh"]["obj"]):
            p = l.split()
            if not p: continue
            if p[0] == "v": V.append(Vector((-float(p[1]), float(p[2]), float(p[3]))))
            elif p[0] == "vt": T.append((float(p[1]), float(p[2])))
            elif p[0] == "f": F.append([tuple(int(x) - 1 for x in q.split("/")[:2]) for q in reversed(p[1:])])
        q = node["rot"]
        M = Matrix.Translation(Vector(node["pos"])) @ Quaternion((q[3], q[0], q[1], q[2])).to_matrix().to_4x4() \
            @ Matrix.Diagonal((*node["scale"], 1))
        verts = [M @ v for v in V]
        verts = [Vector((-v.x - 4.5, -v.z, v.y)) for v in verts]
        F = [list(reversed(f)) for f in F]
        me = bpy.data.meshes.new("ref"); me.from_pydata(verts, [], [[c[0] for c in f] for f in F])
        uvl = me.uv_layers.new(); i = 0
        for f in F:
            for c in f: uvl.data[i].uv = T[c[1]]; i += 1
        o = bpy.data.objects.new("ref", me); sc.collection.objects.link(o); o.data.materials.append(vm)

world = bpy.data.worlds.new("w"); sc.world = world; world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.42, 0.45, 0.5, 1)
world.node_tree.nodes["Background"].inputs[1].default_value = 0.9
sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN")); sun.data.energy = 3.2
sun.rotation_euler = (math.radians(50), 0, math.radians(35)); sc.collection.objects.link(sun)
bpy.ops.mesh.primitive_plane_add(size=30)
gm = bpy.data.materials.new("ground"); gm.use_nodes = True
gm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.16, 0.14, 0.11, 1)
bpy.context.active_object.data.materials.append(gm)
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam); sc.camera = cam
sc.render.engine = "BLENDER_EEVEE_NEXT"
sc.render.resolution_x, sc.render.resolution_y = 1600, 900
sc.view_settings.view_transform = "Standard"
VIEWS = {"fills": (-6, 13, 13.8, (-1.0, 0, 0.85)), "close": (-16, 10, 5.4, (2.5, 0, 0.95)),
         "alt": (52, 18, 5.6, (2.5, 0, 0.95)), "detail": (-12, 6, 3.3, (2.5, 0, 0.62))}
only = argv[argv.index("--views") + 1].split(",") if "--views" in argv else list(VIEWS)
for vn in only:
    yaw, pitch, dist, tgt = VIEWS[vn]
    t = Vector(tgt)
    d = Vector((math.cos(math.radians(pitch)) * math.sin(math.radians(yaw)),
                -math.cos(math.radians(pitch)) * math.cos(math.radians(yaw)), math.sin(math.radians(pitch))))
    cam.location = t + d * dist; cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    sc.render.filepath = os.path.join(OUT, f"{TAG}-{vn}.png")
    bpy.ops.render.render(write_still=True)
print("DONE")
