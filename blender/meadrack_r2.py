"""Mead Rack round 2: our own frame + atlas, contents are anchors for the game's own item models.
Run: blender -b -P meadrack_r2.py -- [--out DIR] [--tag NAME] [--views fills,close,alt] [--no-ref] [--probe]
Writes assets/meadrack_r2/{MeadRack.obj (frame only), meadrack_atlas.png (128x128), meadrack_anchors.json} and renders
three racks (10/50/100 %) beside the vanilla wood chest and a 1.8 m post. Item models come from the local rip
(C:/Users/joost/ValheimRip/items, reference only, never exported).

Atlas 128x128, four 32 px strips tiling in u:  v .75 hewn grain | v .50 end grain (4 ring tiles) | v .25 iron | v 0 rope

Anchors (meadrack_anchors.json), Unity prefab space. Blender z-up / -y front  ->  Unity y-up / +z front:
    ux = -bx, uy = bz, uz = -by.   Rotations: R_unity = P R_blender P^-1, decomposed as Unity Euler (Rz, then Rx, then Ry).
Per unit: position = centre of the unit box; box_size = (x, y, z) metres the unit may fill; copies[].local_position = BOTTOM
centre of the copy in the unit's local axes (unit rotation is identity), copies[].fit_box = the box that copy's model is
scaled uniformly to fit (the mod computes scale = min(fit/size) from the item's own bounds, anchor bottom-centre).
"""
import bpy, bmesh, sys, os, math, json, random
import numpy as np
from mathutils import Vector, Matrix, Euler, Quaternion

HERE = os.path.dirname(os.path.abspath(__file__))
SLUG = "meadrack"
OUTA = os.path.normpath(os.path.join(HERE, "..", "assets", SLUG + "_r2"))
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = argv[argv.index("--out") + 1] if "--out" in argv else OUTA
TAG = argv[argv.index("--tag") + 1] if "--tag" in argv else SLUG
RIP = "C:/Users/joost/ValheimRip/chests/piece_chest_wood"
ITEMS_DIR = "C:/Users/joost/ValheimRip/items"
PROBE = 1.6 if "--probe" in argv else 1.0
os.makedirs(OUTA, exist_ok=True); os.makedirs(OUT, exist_ok=True)
sys.path.append(ITEMS_DIR)
from load_item import load_item
rng = random.Random(11)

TEXW = TEXH = 128
DENS = 48.0
SH = 0.25
STRIP = {"hewn": 0.75, "end": 0.5, "iron": 0.25, "rope": 0.0}

def srgb(c): return np.array(c, dtype=np.float32)
WOOD, WOOD_D = srgb((0.38, 0.29, 0.18)), srgb((0.21, 0.16, 0.10))
END, END_D = srgb((0.55, 0.45, 0.31)), srgb((0.35, 0.27, 0.17))
IRON, IRON_D = srgb((0.22, 0.21, 0.20)), srgb((0.09, 0.09, 0.09))
ROPE, ROPE_D = srgb((0.45, 0.37, 0.24)), srgb((0.22, 0.17, 0.10))

def build_atlas():
    nr = np.random.default_rng(5)
    img = np.zeros((TEXH, TEXW, 3), np.float32)
    x = np.arange(TEXW)[None, :].repeat(32, 0).astype(np.float32)
    y = np.arange(32)[:, None].repeat(TEXW, 1).astype(np.float32)
    tile = lambda k: 2 * math.pi * k / TEXW
    mix = lambda a, b, t: a * (1 - t[..., None]) + b * t[..., None]
    g = np.sin(y * 1.25 + 1.6 * np.sin(x * tile(2) + y * 0.15) + 0.7 * np.sin(x * tile(5)))
    t = np.clip((g - 0.55) * 2.5, 0, 1) * 0.65 + nr.random((32, TEXW)) * 0.18
    t += np.clip(1 - np.minimum(y, 31 - y) / 3.0, 0, 1) * 0.35
    img[96:128] = mix(WOOD, WOOD_D, np.clip(t, 0, 1))
    for k in range(4):
        cx, cy = 15.5 + nr.uniform(-2, 2), 15.5 + nr.uniform(-2, 2)
        xx, yy = np.meshgrid(np.arange(32), np.arange(32))
        d = np.hypot(xx - cx, yy - cy) + 0.6 * np.sin(np.arctan2(yy - cy, xx - cx) * 3 + k)
        t = (np.sin(d * 1.5) * 0.5 + 0.5) * 0.45 + nr.random((32, 32)) * 0.15
        t = np.where(d > 13.5, 0.95, t)
        img[64:96, 32 * k:32 * k + 32] = mix(END, END_D, t)
    t = nr.random((32, TEXW)) * 0.4 + np.clip(1 - np.minimum(y, 31 - y) / 4.0, 0, 1) * 0.5
    img[32:64] = mix(IRON, IRON_D, np.clip(t, 0, 1))
    t = np.sin(x * tile(16) + y * 0.9) * 0.5 + 0.5
    t = np.clip(t * 0.8 + nr.random((32, TEXW)) * 0.25, 0, 1)
    img[0:32] = mix(ROPE, ROPE_D, t)
    im = bpy.data.images.new("meadrack_atlas", TEXW, TEXH, alpha=False)
    px = np.concatenate([np.clip(img, 0, 1), np.ones((TEXH, TEXW, 1), np.float32)], 2)
    im.pixels.foreach_set(px.ravel())
    im.filepath_raw = os.path.join(OUTA, "meadrack_atlas.png"); im.file_format = "PNG"; im.save()
    return im

PARTS, CHK = [], []
UV = None

def uv_face(f, kind, long_axis, seed):
    n = f.normal
    ax = max(range(3), key=lambda i: abs(n[i]))
    tang = [i for i in range(3) if i != ax]
    if kind == "hewn" and ax == long_axis:
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

def timber(name, size, pos, kind="hewn", rot=(0, 0, 0), jitter=0.012, bevel=0.014, chk=False):
    global UV
    bm = bmesh.new()
    verts = bmesh.ops.create_cube(bm, size=1.0)["verts"]
    for v in verts: v.co = Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2]))
    la = max(range(3), key=lambda i: size[i])
    for v in verts:
        for i in range(3):
            if i != la: v.co[i] += rng.uniform(-jitter, jitter)
    if bevel > 0:
        bmesh.ops.bevel(bm, geom=list({e for v in verts for e in v.link_edges}), offset=bevel, segments=1, affect="EDGES")
    bm.normal_update()
    UV = bm.loops.layers.uv.verify()
    seed = rng.randrange(1000)
    for j, f in enumerate(bm.faces): uv_face(f, kind, la, seed + j % 2)
    bmesh.ops.rotate(bm, verts=bm.verts[:], cent=(0, 0, 0), matrix=Euler([math.radians(a) for a in rot]).to_matrix())
    bmesh.ops.translate(bm, verts=bm.verts[:], vec=Vector(pos))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = False
    ob = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(ob)
    ob.data.materials.append(MAT); PARTS.append(ob)
    if chk:
        cs = [v.co for v in me.vertices]
        CHK.append((name, Vector(min(c[i] for c in cs) for i in range(3)), Vector(max(c[i] for c in cs) for i in range(3))))

# ---------- layout ----------
W, TOPZ = 2.0, 2.0
PX, PY, PS = 0.945, 0.18, 0.09          # post centre x / y, post section
BT = 0.04                               # shelf board thickness
RISER = 0.035                           # back-row step
MARG = 0.014                            # air above the tallest item of a tier
XIN = PX - PS / 2                       # inner face of the posts (0.90)
DT = 0.03                               # divider thickness
CW = (2 * XIN - 3 * DT) / 4             # clear cubby width
CUBX = [-XIN + CW / 2 + k * (CW + DT) for k in range(4)]
DIVX = [-XIN + CW + DT / 2 + k * (CW + DT) for k in range(3)]
BACK_Y = 0.20
ROWY = (-0.10, 0.085)                   # front / back row centre y
ROWD = 0.135                            # depth of one row
# tier classes: (item height target, copies per row)
CLS = {"tall": (0.170, 6), "squat": (0.125, 6), "wide": (0.130, 4)}
TIERS = ["tall", "squat", "wide", "tall", "squat", "wide", "squat", "tall"]
ASSORT = [
    ["MeadStaminaMinor", "MeadPoisonResist", "MeadFrostResist", "MeadStaminaMedium", "MeadStaminaMinor", "MeadTasty", "MeadFrostResist", "MeadBugRepellent"],
    ["MeadHealthMinor", "MeadHealthMedium", "MeadEitrMinor", "MeadHealthMinor", "MeadHealthMedium", "MeadHealthMinor", "MeadEitrMinor", "MeadHealthMedium"],
    ["BarleyWine", "MeadHealthLingering", "MeadTrollPheromones", "MeadStaminaLingering", "MeadHealthMajor", "BarleyWine", "MeadStaminaLingering", "MeadHealthLingering"],
    ["MeadPoisonResist", "MeadStaminaMedium", "MeadTasty", "MeadBugRepellent", "MeadPoisonResist", "MeadFrostResist", "MeadStaminaMinor", "MeadTasty"],
    ["MeadEitrMinor", "MeadHealthMinor", "MeadHealthMedium", "MeadHealthMinor", "MeadHealthMedium", "MeadEitrMinor", "MeadHealthMinor", "MeadHealthMedium"],
    ["MeadHealthMajor", "BarleyWine", "MeadStaminaLingering", "MeadHealthLingering", "MeadTrollPheromones", "MeadHealthMajor", "BarleyWine", "MeadStaminaLingering"],
    ["MeadHealthMedium", "MeadHealthMinor", "MeadEitrMinor", "MeadHealthMedium", "MeadHealthMinor", "MeadHealthMedium", "MeadEitrMinor", "MeadHealthMinor"],
    ["MeadStaminaMedium", "MeadStaminaMinor", "MeadPoisonResist", "MeadTasty", "MeadFrostResist", "MeadBugRepellent", "MeadStaminaMedium", "MeadPoisonResist"],
]

def tier_geometry():
    z = 0.07 + BT / 2
    out = []
    for cls in TIERS:
        h, n = CLS[cls]
        clear = h + RISER + MARG
        out.append({"cls": cls, "board_z": z, "base": z + BT / 2, "h": h, "clear": clear, "n": n})
        z = z + BT / 2 + clear + BT / 2
    return out, z - BT / 2            # z of the underside of the top board
TG, CEIL = tier_geometry()

def build_frame():
    for sx in (-1, 1):
        for sy in (-1, 1):
            h = 1.86
            timber("post", (PS, PS, h), (sx * PX, sy * PY, 0.07 + h / 2),
                   rot=(rng.uniform(-0.3, 0.3), rng.uniform(-0.3, 0.3), 0), jitter=0.004, bevel=0.012, chk=True)
        timber("sill", (0.13, 0.50, 0.07), (sx * 0.93, 0, 0.035), rot=(0, 0, rng.uniform(-0.6, 0.6)), jitter=0.004, chk=True)
    for sx in (-1, 1):                        # closed side planks between the posts
        for k, yy in enumerate((-0.09, 0.09)):
            timber("side", (0.03, 0.17, 1.80), (sx * 0.915, yy, 0.07 + 0.90), jitter=0.002, bevel=0.006, chk=True)
    timber("kick", (1.80, 0.06, 0.07), (0, -0.21, 0.035), jitter=0.004, chk=True)
    for t in TG:
        timber("shelf", (1.80, 0.42, BT), (0, 0, t["board_z"]), rot=(0, 0, rng.uniform(-0.3, 0.3)), jitter=0.0, bevel=0.01, chk=True)
    timber("top", (2.0, 0.50, 0.07), (0, 0, TOPZ - 0.035), rot=(0, 0, rng.uniform(-0.2, 0.2)), jitter=0.004, bevel=0.016, chk=True)
    for i in range(10):                       # carved tooth row hanging off the top board's front edge
        x = -0.9 + i * 0.2
        timber("tooth", (0.10, 0.035, 0.035 + (0.015 if i % 2 else 0)), (x, -0.235, TOPZ - 0.07 - 0.0175 - (0.0075 if i % 2 else 0)),
               jitter=0.003, bevel=0.004)
    for t in TG:
        zt, zb = t["base"], t["base"] + t["clear"]
        for dx in DIVX:
            timber("divider", (DT, 0.38, t["clear"] + 0.01), (dx, -0.02, (zt + zb) / 2), rot=(0, 0, rng.uniform(-0.3, 0.3)),
                   jitter=0.003, bevel=0, chk=True)
        timber("back", (1.80, 0.03, t["clear"] + BT), (0, BACK_Y, (zt + zb) / 2), jitter=0.003, bevel=0, chk=True)
        timber("riser", (1.80, 0.17, RISER), (0, 0.09, zt + RISER / 2), jitter=0.0, bevel=0.006, chk=True)
    for sx in (-1, 1):
        for t in TG:
            timber("band", (PS + 0.02, PS + 0.02, 0.045), (sx * PX, -PY, t["base"] + 0.07), kind="iron", jitter=0.002, bevel=0.004)
    for t in TG:
        for dx in DIVX:
            timber("strap", (0.09, 0.012, 0.04), (dx, -0.226, t["board_z"]), kind="iron", jitter=0.001, bevel=0)
            timber("rivet", (0.026, 0.026, 0.026), (dx, -0.236, t["board_z"]), kind="iron", jitter=0, bevel=0)
    for sx in (-1, 1):
        for zz in (0.17, TOPZ - 0.16):
            for dz in (-0.02, 0.02):
                timber("lash", (PS + 0.012, PS + 0.012, 0.03), (sx * PX, -PY, zz + dz), kind="rope", jitter=0.002, bevel=0.005)

# ---------- anchors ----------
P = Matrix(((-1, 0, 0), (0, 0, 1), (0, -1, 0)))
def to_unity_vec(v): return [round(-v[0], 4), round(v[2], 4), round(-v[1], 4)]
def to_unity_euler(rot_blender_deg):
    R = Euler([math.radians(a) for a in rot_blender_deg], "XYZ").to_matrix()
    M = P @ R @ P.inverted()
    x = math.asin(max(-1, min(1, -M[1][2]))); y = math.atan2(M[0][2], M[2][2]); z = math.atan2(M[1][0], M[1][1])
    return [round(math.degrees(a), 2) for a in (x, y, z)]

def build_units():
    units = []; n = 0
    for ti, t in enumerate(TG):
        for rowi in (0, 1):
            for c in range(4):
                name = ASSORT[ti][rowi * 4 + c]
                h, cnt = CLS[t["cls"]]
                pitch = (CW - 0.012) / cnt
                base = t["base"] + (RISER if rowi else 0.0)
                box_c = Vector((CUBX[c], ROWY[rowi], base + h / 2))
                copies = []
                for j in range(cnt):
                    lx = (j - (cnt - 1) / 2) * pitch + rng.uniform(-0.002, 0.002)
                    ly = rng.uniform(-0.004, 0.004)
                    yaw = rng.uniform(-5, 5)
                    tilt = (rng.uniform(-1, 1), rng.uniform(-1, 1))
                    copies.append({"item": name, "blender_local_bottom": (lx, ly, -h / 2), "blender_rot": (tilt[0], tilt[1], yaw),
                                   "fit": (pitch * 0.96, ROWD * 0.96, h)})
                units.append({"index": n, "tier": ti, "row": ("front", "back")[rowi], "column": c, "kind": "row", "item": name,
                              "center": box_c, "box": (cnt * pitch, ROWD, h), "copies": copies}); n += 1
    return units

def anchors_json(units):
    out = []
    for u in units:
        bx = u["box"]
        out.append({"index": u["index"], "kind": u["kind"], "position": to_unity_vec(u["center"]), "rotation": [0, 0, 0],
                    "box_size": [round(bx[0], 4), round(bx[2], 4), round(bx[1], 4)],
                    "tier": u["tier"], "row": u["row"], "column": u["column"], "example_item": u["item"],
                    "copies": [{"local_position": to_unity_vec(c["blender_local_bottom"]), "rotation": to_unity_euler(c["blender_rot"]),
                                "fit_box": [round(c["fit"][0], 4), round(c["fit"][2], 4), round(c["fit"][1], 4)],
                                "anchor": "bottom_center"} for c in u["copies"]]})
    return out

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

TEMPLATES, INFO = {}, {}
for name in sorted({n for row in ASSORT for n in row}):
    objs = load_item(name, anchor="bottom")
    TEMPLATES[name] = objs[0].data
    INFO[name] = json.load(open(f"{ITEMS_DIR}/{name}/info.json"))
    for ob in objs: bpy.data.objects.remove(ob, do_unlink=True)

SHR = 0.002
REASON = {}
def clipped_world(vs):
    for p in vs:
        for nm, lo, hi in CHK:
            if all(lo[i] + SHR < p[i] < hi[i] - SHR for i in range(3)): REASON[nm] = REASON.get(nm, 0) + 1
        if abs(p.x) > XIN + 0.0005 or p.y < -0.19 or p.y > 0.178: REASON["bounds"] = REASON.get("bounds", 0) + 1
    for p in vs:
        if abs(p.x) > XIN + 0.0005 or p.y < -0.19 or p.y > 0.178: return True
        for _, lo, hi in CHK:
            if all(lo[i] + SHR < p[i] < hi[i] - SHR for i in range(3)): return True
    return False

def place_items(units, nshow, xoff, check=False):
    objs, bad, tot = [], 0, 0
    for u in units[:nshow]:
        for c in u["copies"]:
            size = INFO[c["item"]]["size"]
            s = min(c["fit"][i] / size[i] for i in range(3)) * PROBE
            pos = u["center"] + Vector(c["blender_local_bottom"])
            if check:
                R = Euler([math.radians(a) for a in c["blender_rot"]], "XYZ").to_matrix().to_4x4()
                M = Matrix.Translation(pos) @ R @ Matrix.Diagonal((s, s, s, 1))
                tot += 1
                if clipped_world([M @ v.co for v in TEMPLATES[c["item"]].vertices]): bad += 1
                continue
            o = bpy.data.objects.new(c["item"], TEMPLATES[c["item"]]); sc.collection.objects.link(o)
            o.scale = (s, s, s); o.rotation_euler = Euler([math.radians(a) for a in c["blender_rot"]], "XYZ")
            o.location = pos + Vector((xoff, 0, 0))
            objs.append(o)
    return objs, bad, tot

SPACING = 2.5
for k, fill in enumerate(reversed(FILLS)):
    rng.seed(11); PARTS.clear(); CHK.clear()
    build_frame()
    units = build_units()
    nshow = round(fill * len(units))
    if k == 0:
        _, bad, tot = place_items(units, len(units), 0.0, check=True)
        print(f"CLIPPING {bad} of {tot}", REASON)
        if PROBE != 1.0: sys.exit(0)
        bpy.ops.object.select_all(action="DESELECT")
        for o in PARTS: o.select_set(True)
        bpy.ops.wm.obj_export(filepath=os.path.join(OUTA, "MeadRack.obj"), export_selected_objects=True, export_materials=False,
                              export_triangulated_mesh=True, forward_axis="NEGATIVE_Z", up_axis="Y")
        stats = {"frame_tris": tris(PARTS), "units": len(units), "slots_designed_for": len(units),
                 "copies_total": sum(len(u["copies"]) for u in units), "clip_count": bad, "clip_of": tot,
                 "size_m": [2.0, 0.5, TOPZ], "conversion": "ux=-bx, uy=bz, uz=-by", "atlas": [TEXW, TEXH],
                 "fill_order": "tier bottom to top; per tier the front row left to right, then the back row", "units_list": anchors_json(units)}
        json.dump(stats, open(os.path.join(OUTA, "meadrack_anchors.json"), "w"), indent=1)
        print("FRAME", {a: b for a, b in stats.items() if a != "units_list"}, "CEIL", round(CEIL, 3))
    xoff = (len(FILLS) - 1 - k) * SPACING - SPACING
    for o in PARTS: o.location.x += xoff
    place_items(units, nshow, xoff)

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
        verts = [Vector((-v.x + 5.6, -v.z, v.y)) for v in verts]
        F = [list(reversed(f)) for f in F]
        me = bpy.data.meshes.new("ref"); me.from_pydata(verts, [], [[c[0] for c in f] for f in F])
        uvl = me.uv_layers.new(); i = 0
        for f in F:
            for c in f: uvl.data[i].uv = T[c[1]]; i += 1
        o = bpy.data.objects.new("ref", me); sc.collection.objects.link(o); o.data.materials.append(vm)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(4.2, 0, 0.9)); pm = bpy.context.active_object
    pm.scale = (0.10, 0.10, 1.8); pm.name = "marker_1_8m"
    mm = bpy.data.materials.new("marker"); mm.use_nodes = True
    mm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.5, 0.5, 0.52, 1); pm.data.materials.append(mm)

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
sc.view_settings.view_transform = "Standard"
VIEWS = {"fills": (-5, 7, 15.6, (1.4, 0, 0.95)), "close": (-18, 8, 6.4, (2.5, 0, 1.0)),
         "alt": (50, 12, 6.6, (2.5, 0, 1.0)), "detail": (-14, 6, 2.0, (2.5, 0, 0.55))}
only = argv[argv.index("--views") + 1].split(",") if "--views" in argv else ["fills", "close", "alt"]
for vn in only:
    yaw, pitch, dist, tgt = VIEWS[vn]
    t = Vector(tgt)
    d = Vector((math.cos(math.radians(pitch)) * math.sin(math.radians(yaw)),
                -math.cos(math.radians(pitch)) * math.cos(math.radians(yaw)), math.sin(math.radians(pitch))))
    cam.location = t + d * dist; cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    if vn == "fills": sc.render.resolution_x, sc.render.resolution_y = 2400, 1000
    else: sc.render.resolution_x, sc.render.resolution_y = 1600, 900
    sc.render.filepath = os.path.join(OUT, f"{TAG}-{vn}.png")
    bpy.ops.render.render(write_still=True)
print("DONE")
