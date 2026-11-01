"""Emergency Shelf round 4: a wall shelf unit with 1, 2 or 3 planks, one item per stack at DISPLAY size (Joost, 22 Oct 2026):
0.7 x the item's true in-game size (dev config "Display item size"), so two stacks of the same thing show as two copies.
Run: blender -b -P emergencyshelf_r4.py -- [--out DIR] [--tag NAME] [--views row,close,side] [--noexport]
Our own mesh + own 128 px point-filtered atlas (same palette as round 2). Contents are NOT in our model: the mod packs
each stored stack's own game model onto the planks at runtime (StoreContents.Pack in Storehouse.cs), with the plank
surfaces in assets/emergencyshelf_r4/emergencyshelf_r4.json. The renders run the SAME packing rule here on the real item
models from the local rip (C:/Users/joost/ValheimRip/items, reference only, never exported), at DS x true size.

Unit space (Blender, z up, -y front): wall plane y=0, x centred, BOTTOM plank underside at z=0, planks at PITCH.
Unity prefab space (all JSON numbers): ux=-bx, uy=bz, uz=-by (front -y -> +z). OBJ export forward -Z, up Y, loaded flipX.

Packing rule (mirrored exactly in Storehouse.cs):
  stacks in slot order, one item each, at DS x the item's own size (as dropped in the world), left to right as seen
  from the front along the top plank, then the one below, ... (reading order, like the container grid's rows); an item that doesn't fit the rest of a plank goes to the next one;
  what fits nowhere isn't shown. Orientation: yaw so the longest horizontal side runs along the plank; for an item
  longer than 0.5 m (true size), a diagonal yaw (and/or a lean against the wall) is used when it fits the plank depth and height
  and saves at least 3 cm of plank; an item too deep for the plank leans back against the wall if that fits, else it
  stands against the wall and overhangs the front (resting on the lip). Gap 3 cm between items and at the ends.
"""
import bpy, bmesh, sys, os, math, json, random
import numpy as np
from mathutils import Vector, Matrix, Euler, Quaternion
sys.path.append("C:/Users/joost/ValheimRip/items")
from load_item import load_item

HERE = os.path.dirname(os.path.abspath(__file__))
OUTA = os.path.normpath(os.path.join(HERE, "..", "assets", "emergencyshelf_r4"))
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = argv[argv.index("--out") + 1] if "--out" in argv else OUTA
TAG = argv[argv.index("--tag") + 1] if "--tag" in argv else "emergencyshelf_r4"
EXPORT = "--noexport" not in argv
os.makedirs(OUTA, exist_ok=True); os.makedirs(OUT, exist_ok=True)
rng = random.Random(11)
ITEMROOT = "C:/Users/joost/ValheimRip/items"

TEX = 128; DENS = 48.0
STRIP = {"hewn": 0.75, "hewn2": 0.50, "end": 0.25, "iron": 0.0}
W = 2.0            # overall width
TS = 0.06          # side board thickness
PT = 0.06          # plank thickness
DEPTH = 0.45       # plank depth (wall to front edge)
LIP_T, LIP_H = 0.035, 0.035
TALLEST = 0.504    # tallest meal/mead at runtime (FishAndBread 0.504, MeadTrollPheromones 0.500)
DS = float(argv[argv.index("--ds") + 1]) if "--ds" in argv else 0.7   # display item size (x true size)
CLEAR = 0.42       # free height above a plank: the tallest item at 0.7 is 0.353 m; 0.42 leaves room up to ~0.8
PITCH = round(CLEAR + PT, 3)        # 0.48
DROP = 0.12        # side boards / bracket reach below the bottom plank
GAP = 0.03
XIN = W / 2 - TS   # inner face of the side boards
YB, YF = -0.01, -(DEPTH - LIP_T) + 0.003   # usable depth: 1 cm off the wall .. lip inner face
LONG = 0.5 * DS; SAVE = 0.03

# ---------- texture (round 2 palette) ----------
def srgb(c): return np.array(c, dtype=np.float32)
WOOD, WOOD_D = srgb((0.38, 0.29, 0.18)), srgb((0.21, 0.16, 0.10))
WOOD2, WOOD2_D = srgb((0.33, 0.27, 0.19)), srgb((0.19, 0.155, 0.11))
END, END_D = srgb((0.55, 0.45, 0.31)), srgb((0.35, 0.27, 0.17))
IRON, IRON_D = srgb((0.22, 0.21, 0.20)), srgb((0.09, 0.09, 0.09))

def build_atlas():
    nr = np.random.default_rng(5)
    img = np.zeros((TEX, TEX, 3), np.float32)
    x = np.arange(TEX)[None, :].repeat(32, 0).astype(np.float32)
    y = np.arange(32)[:, None].repeat(TEX, 1).astype(np.float32)
    tile = lambda k: 2 * math.pi * k / TEX
    for base, (c0, c1), ph in ((96, (WOOD, WOOD_D), 0.0), (64, (WOOD2, WOOD2_D), 1.3)):
        g = np.sin(y * 1.25 + 1.6 * np.sin(x * tile(2) + y * 0.15 + ph) + 0.7 * np.sin(x * tile(5) + ph))
        t = np.clip((g - 0.55) * 2.5, 0, 1) * 0.65 + nr.random((32, TEX)) * 0.18
        t += np.clip(1 - np.minimum(y, 31 - y) / 3.0, 0, 1) * 0.35
        img[base:base + 32] = c0 * (1 - t[..., None]) + c1 * t[..., None]
    for k in range(4):
        cx, cy = 15.5 + nr.uniform(-2, 2), 15.5 + nr.uniform(-2, 2)
        xx, yy = np.meshgrid(np.arange(32), np.arange(32))
        d = np.hypot(xx - cx, yy - cy) + 0.6 * np.sin(np.arctan2(yy - cy, xx - cx) * 3 + k)
        t = (np.sin(d * 1.5) * 0.5 + 0.5) * 0.45 + nr.random((32, 32)) * 0.15
        t = np.where(d > 13.5, 0.95, t)
        img[32:64, 32 * k:32 * k + 32] = END * (1 - t[..., None]) + END_D * t[..., None]
    t = nr.random((32, TEX)) * 0.4 + np.clip(1 - np.minimum(y, 31 - y) / 4.0, 0, 1) * 0.5
    img[0:32] = IRON * (1 - t[..., None]) + IRON_D * t[..., None]
    im = bpy.data.images.new("emergencyshelf_r4_atlas", TEX, TEX, alpha=False)
    px = np.concatenate([np.clip(img, 0, 1), np.ones((TEX, TEX, 1), np.float32)], 2)
    im.pixels.foreach_set(px.ravel())
    im.filepath_raw = os.path.join(OUTA, "emergencyshelf_r4_atlas.png"); im.file_format = "PNG"
    if EXPORT: im.save()
    return im

# ---------- frame geometry ----------
CUR = []
def wood_uv(kind, long_axis, seed):
    def fn(f, uvl):
        n = f.normal
        ax = max(range(3), key=lambda i: abs(n[i]))
        tang = [i for i in range(3) if i != ax]
        if kind != "iron" and ax == long_axis:
            k = seed % 4
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
        vscale = min(1.0, (32 / DENS) / span)
        base = STRIP[kind]
        for l in f.loops:
            l[uvl].uv = (l.vert.co[ua] * DENS / TEX + off, base + ((l.vert.co[va] - vmin) * vscale * DENS / TEX) * 0.94 + 0.0075)
    return fn

def commit(bm, name, uvfun, pos=(0, 0, 0), rot=(0, 0, 0), target=None, mat=None):
    bm.normal_update()
    uvl = bm.loops.layers.uv.verify()
    for f in bm.faces: uvfun(f, uvl)
    if any(rot):
        bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Euler([math.radians(a) for a in rot]).to_matrix())
    bmesh.ops.translate(bm, verts=bm.verts, vec=Vector(pos))
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = False
    ob = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(ob)
    ob.data.materials.append(mat or MAT)
    (CUR if target is None else target).append(ob)
    return ob

def timber(name, size, pos, kind="hewn", rot=(0, 0, 0), jitter=0.008, bevel=0.012, target=None, mat=None):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts: v.co = Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2]))
    long_axis = max(range(3), key=lambda i: size[i])
    for v in bm.verts:
        for i in range(3):
            if i != long_axis: v.co[i] += rng.uniform(-jitter, jitter)
    if bevel > 0:
        bmesh.ops.bevel(bm, geom=bm.edges[:], offset=bevel, segments=1, affect="EDGES")
    return commit(bm, name, wood_uv(kind, long_axis, rng.randrange(1000)), pos, rot, target, mat)

def side_board(xc, ztop):
    """A hand-hewn side board (x thickness TS): bracket foot below the bottom plank, chamfered top front."""
    prof = [(0.0, -DROP), (-0.13, -DROP), (-(DEPTH + 0.02), -0.035), (-(DEPTH + 0.02), ztop - 0.09), (-(DEPTH - 0.06), ztop), (0.0, ztop)]
    prof = [(y + (rng.uniform(-0.006, 0.006) if 0 < i < 5 else 0), z + rng.uniform(-0.005, 0.005)) for i, (y, z) in enumerate(prof)]
    bm = bmesh.new()
    vs = [[bm.verts.new((s * TS / 2 + rng.uniform(-0.003, 0.003), y, z)) for (y, z) in prof] for s in (-1, 1)]
    n = len(prof)
    bm.faces.new(list(reversed(vs[0]))); bm.faces.new(vs[1])
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((vs[0][i], vs[0][j], vs[1][j], vs[1][i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bmesh.ops.bevel(bm, geom=bm.edges[:], offset=0.008, segments=1, affect="EDGES")
    return commit(bm, "side", wood_uv("hewn2", 2, rng.randrange(1000)), (xc, 0, 0))

def plank_z(k): return k * PITCH

def build_frame(n):
    ztop = plank_z(n - 1) + PT + 0.15
    for s in (-1, 1):
        side_board(s * (W / 2 - TS / 2), ztop)
    for k in range(n):
        z0 = plank_z(k)
        timber("plank", (2 * XIN + 0.03, DEPTH - 0.004, PT), (0, -0.002 - (DEPTH - 0.004) / 2, z0 + PT / 2), jitter=0.0, bevel=0.01, rot=(0, 0, rng.uniform(-0.15, 0.15)))
        timber("lip", (2 * XIN, LIP_T, LIP_H), (0, -DEPTH + LIP_T / 2 + 0.001, z0 + PT + LIP_H / 2), kind="hewn2", jitter=0.002, bevel=0.006)
        for s in (-1, 1):   # wedged through-tenon ends + iron straps on the lip corners
            timber("peg", (0.016, 0.05, 0.04), (s * (W / 2 + 0.002), -0.25, z0 + PT / 2), kind="end", jitter=0.0, bevel=0.003)
            timber("strap", (0.05, 0.045, 0.05), (s * (XIN - 0.05), -DEPTH + LIP_T / 2 + 0.001, z0 + PT + LIP_H / 2 - 0.004), kind="iron", jitter=0.0, bevel=0.004)
    for s in (-1, 1):       # iron wall straps on the side boards
        for zz in [-DROP + 0.05] + [plank_z(k) + PT + 0.2 for k in range(n - 1)] + [ztop - 0.07]:
            timber("wallstrap", (0.014, 0.12, 0.045), (s * (W / 2 + 0.004), -0.055, zz), kind="iron", jitter=0.0, bevel=0.0)
            timber("bolt", (0.01, 0.022, 0.022), (s * (W / 2 + 0.012), -0.08, zz), kind="iron", jitter=0.0, bevel=0.0)
    # centre bracket under the bottom plank (nothing hangs below it)
    timber("plate", (0.08, 0.04, DROP + 0.0), (0, -0.02, -DROP / 2), jitter=0.002, bevel=0.0)
    timber("arm", (0.075, 0.40, 0.05), (0, -0.24, -0.025), jitter=0.002, bevel=0.0)
    dy, dz = -0.28, DROP - 0.06
    L = math.hypot(dy, dz)
    timber("brace", (0.06, L, 0.05), (0, -0.04 + dy / 2, -DROP + 0.03 + dz / 2), rot=(math.degrees(math.atan2(dz, dy)) + 180, 0, 0), jitter=0.002, bevel=0.006)
    for zz in (-0.03, -0.09):
        timber("bolt", (0.026, 0.02, 0.026), (rng.uniform(-.006, .006), -0.045, zz), kind="iron", jitter=0.0, bevel=0.0)

def planks_json(n):
    return [dict(y=round(plank_z(k) + PT, 4), z=round(-(YB + YF) / 2, 4), x=[round(-XIN, 4), round(XIN, 4)],
                 z_back=round(-YB, 4), z_front=round(-YF, 4), lip_top=LIP_H, clear_height=CLEAR) for k in reversed(range(n))]   # fill order: top plank first

# ---------- items + the packing rule ----------
PROTO, PTS = {}, {}
def proto(name):
    if name not in PROTO:
        objs = load_item(name)
        for o in objs:
            for c in list(o.users_collection): c.objects.unlink(o)
        PROTO[name] = objs
        PTS[name] = np.array([[v.co.x, v.co.y, v.co.z] for o in objs for v in o.data.vertices])
    return PROTO[name]

def rot(theta, alpha):
    """yaw theta about z, then tilt alpha about x (alpha>0 raises the back, +y, against the wall)."""
    return Matrix.Rotation(math.radians(alpha), 3, "X") @ Matrix.Rotation(math.radians(theta), 3, "Z")

ORIENT = {}
def orient(name, D, H):
    """(theta, alpha, ext, qmin) for an item on a plank with usable depth D and free height H; None if it can't stand there."""
    key = (name, round(D, 4), round(H, 4))
    if key in ORIENT: return ORIENT[key]
    proto(name); P = PTS[name] * DS
    cand = []
    for th in range(0, 180, 5):
        for al in [0] + list(range(10, 85, 5)):
            R = np.array(rot(th, al))
            Q = P @ R.T
            lo, hi = Q.min(0), Q.max(0)
            cand.append((th, al, hi - lo, lo))
    flat = [c for c in cand if c[1] == 0]
    base = min(flat, key=lambda c: (round(c[2][1], 5), c[0]))   # long side along the plank = least depth
    ok = lambda c: c[2][1] <= D + 1e-4 and c[2][2] <= H + 1e-4
    feas = [c for c in cand if ok(c)]
    best = min(feas, key=lambda c: (round(c[2][0], 4), c[1], min(abs(c[0] - base[0]), 180 - abs(c[0] - base[0])))) if feas else None
    if ok(base):
        pick = base
        if base[2][0] > LONG and best and best[2][0] < base[2][0] - SAVE: pick = best
    elif best: pick = best
    elif base[2][2] <= H + 1e-4: pick = base          # too deep for any lean: against the wall, overhanging
    else: pick = None
    ORIENT[key] = pick
    return pick

def pack(names, planks):
    """planks: Blender-space dicts (z top, y back/front, x min/max, H). Returns [(name, Matrix4, plank index)] + skipped."""
    out, skipped = [], []
    k, cursor = 0, planks[0]["x0"] if planks else 0
    for nm in names:
        placed = False
        for kk in range(k, len(planks)):
            p = planks[kk]
            cur = cursor if kk == k else p["x0"]
            o = orient(nm, p["yb"] - p["yf"], p["H"])
            if o is None: continue
            th, al, ext, lo = o
            if cur + GAP + ext[0] > p["x1"] - GAP + 1e-6: continue
            x = cur + GAP + ext[0] / 2
            lift = 0.0
            if ext[1] <= p["yb"] - p["yf"] + 1e-4 and al == 0: y = (p["yb"] + p["yf"]) / 2
            else:
                y = p["yb"] - ext[1] / 2
                if y - ext[1] / 2 < p["yf"] - 1e-4: lift = LIP_H
            t = Vector((x - (lo[0] + ext[0] / 2), y - (lo[1] + ext[1] / 2), p["z"] + lift - lo[2]))
            out.append((nm, Matrix.Translation(t) @ rot(th, al).to_4x4() @ Matrix.Scale(DS, 4), kk, (th, al, lift)))
            k, cursor, placed = kk, cur + GAP + ext[0], True
            break
        if not placed: skipped.append(nm)
    return out, skipped

def planks_blender(n, origin):
    return [dict(z=origin[2] + plank_z(k) + PT, yb=origin[1] + YB, yf=origin[1] + YF, x0=origin[0] - XIN, x1=origin[0] + XIN, H=CLEAR) for k in reversed(range(n))]   # top plank first

def spawn(name, M):
    made = []
    for o in proto(name):
        c = o.copy(); bpy.context.scene.collection.objects.link(c)
        c.matrix_world = M
        made.append(c)
    return made

# ---------- scene ----------
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
atlas = build_atlas()
MAT = bpy.data.materials.new("emergencyshelf"); MAT.use_nodes = True
nt = MAT.node_tree; bsdf = nt.nodes["Principled BSDF"]
ti = nt.nodes.new("ShaderNodeTexImage"); ti.image = atlas; ti.interpolation = "Closest"
nt.links.new(ti.outputs["Color"], bsdf.inputs["Base Color"]); bsdf.inputs["Roughness"].default_value = 0.8
POSTMAT = bpy.data.materials.new("post"); POSTMAT.use_nodes = True
POSTMAT.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.55, 0.58, 0.62, 1)
WALLMAT = bpy.data.materials.new("wall"); WALLMAT.use_nodes = True
wn = WALLMAT.node_tree; wt = wn.nodes.new("ShaderNodeTexImage"); wt.image = atlas; wt.interpolation = "Closest"
wm = wn.nodes.new("ShaderNodeMixRGB"); wm.blend_type = "MULTIPLY"; wm.inputs[0].default_value = 1.0
wm.inputs[2].default_value = (0.70, 0.68, 0.66, 1)
wn.links.new(wt.outputs["Color"], wm.inputs[1]); wn.links.new(wm.outputs["Color"], wn.nodes["Principled BSDF"].inputs["Base Color"])
wn.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.85

def join(obs, name):
    bpy.ops.object.select_all(action="DESELECT")
    for o in obs: o.select_set(True)
    bpy.context.view_layer.objects.active = obs[0]
    bpy.ops.object.join(); ob = bpy.context.active_object; ob.name = name
    return ob

def frame_at(n, origin, seed=11):
    rng.seed(seed + n); CUR.clear()
    build_frame(n)
    parts = list(CUR)
    for o in parts: o.location = Vector(origin)
    bpy.context.view_layer.update()
    return parts

def tris(obs): return sum(len(p.vertices) - 2 for o in obs for p in o.data.polygons)

JS, STATS = {}, {}
for n in (1, 2, 3):
    parts = frame_at(n, (0, 0, 0))
    ft = tris(parts)
    bb = [min(v[i] for o in parts for v in (o.matrix_world @ w.co for w in o.data.vertices)) for i in range(3)] + \
         [max(v[i] for o in parts for v in (o.matrix_world @ w.co for w in o.data.vertices)) for i in range(3)]
    frame = join(parts, f"EmergencyShelf{n}")
    if EXPORT:
        bpy.ops.object.select_all(action="DESELECT"); frame.select_set(True)
        bpy.ops.wm.obj_export(filepath=os.path.join(OUTA, f"EmergencyShelf{n}.obj"), export_selected_objects=True,
                              export_materials=False, export_triangulated_mesh=True, forward_axis="NEGATIVE_Z", up_axis="Y")
    bpy.data.objects.remove(frame, do_unlink=True)
    JS[str(n)] = dict(frame_obj=f"EmergencyShelf{n}.obj", frame_tris=ft, planks=planks_json(n),
                      size_m=[round(bb[3] - bb[0], 3), round(bb[5] - bb[2], 3), round(bb[4] - bb[1], 3)])
    STATS[n] = (ft, JS[str(n)]["size_m"])
if EXPORT:
    json.dump(dict(atlas="emergencyshelf_r4_atlas.png", layout="packing",
                   conversion="Blender z-up/-y front -> Unity y-up/+z front: ux=-bx, uy=bz, uz=-by. Origin: wall plane, centred in x, bottom plank underside = y 0.",
                   how_to_use="Runtime packing: stacks in slot order, one item each at scale 1, filled from +x (left as seen from the front) to -x along planks[0], then planks[1], ... (planks are listed in fill order: TOP plank first) "
                              "Each plank: y = top surface, z = row centre, x = [min, max] between the side boards, z_back..z_front = usable depth (wall .. lip), "
                              "lip_top = lip height above y, clear_height = free height above y. Gap 0.03 m between items and at the ends.",
                   tallest_item_m=TALLEST, display_size=DS, clear_height=CLEAR, pitch=PITCH, depth=DEPTH, width=W, gap=GAP, long_item_m=LONG, min_saving_m=SAVE,
                   pieces=JS), open(os.path.join(OUTA, "emergencyshelf_r4.json"), "w"), indent=1)
print("STATS", STATS)

def wall_panel(ox, h=2.0):
    wall = []
    rng.seed(5)
    for k in range(10):
        hh = h + rng.uniform(-0.015, 0.015)
        timber("wall", (0.248, 0.07, hh), (ox - 1.125 + k * 0.25, 0.04, hh / 2), jitter=0.004, bevel=0.01,
               rot=(0, rng.uniform(-0.3, 0.3), rng.uniform(-0.4, 0.4)), target=wall, mat=WALLMAT)

def post_at(x, y):
    post = bpy.data.objects.new("post", bpy.data.meshes.new("post"))
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts: v.co = Vector((v.co.x * 0.1, v.co.y * 0.1, v.co.z * 1.8 + 0.9))
    bm.to_mesh(post.data); bm.free()
    for p in post.data.polygons: p.use_smooth = False
    post.data.materials.append(POSTMAT); post.location = (x, y, 0)
    sc.collection.objects.link(post)

def vanilla_chest(ox, oy):
    RIP = "C:/Users/joost/ValheimRip/chests/piece_chest_wood"
    rep = json.load(open("C:/Users/joost/ValheimRip/chests/report.json"))["piece_chest_wood"]["nodes"]
    vimg = bpy.data.images.load(f"{RIP}/woodchest_d.png", check_existing=True)
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
        M = Matrix.Translation(Vector(node["pos"])) @ Quaternion((q[3], q[0], q[1], q[2])).to_matrix().to_4x4() @ Matrix.Diagonal((*node["scale"], 1))
        verts = [M @ v for v in V]
        verts = [Vector((-v.x + ox, -v.z + oy, v.y)) for v in verts]
        F = [list(reversed(f)) for f in F]
        me = bpy.data.meshes.new("ref"); me.from_pydata(verts, [], [[c[0] for c in f] for f in F])
        uvl = me.uv_layers.new(); i = 0
        for f in F:
            for c in f: uvl.data[i].uv = T[c[1]]; i += 1
        ob = bpy.data.objects.new("ref", me); sc.collection.objects.link(ob); ob.data.materials.append(vm)

# realistic emergency kits, in slot order (4 slots per plank)
KITS = {
 1: ["MeadHealthMedium", "MeadHealthMedium", "MeadStaminaMedium", "MeadPoisonResist", "CookedMeat", "QueensJam"],
 2: ["MeadHealthMedium", "MeadHealthMedium", "MeadHealthMinor", "MeadStaminaMedium", "MeadStaminaMinor", "MeadFrostResist",
     "LoxPie", "CookedMeat", "QueensJam", "MeadPoisonResist", "FishWraps", "Bread"],
 3: ["MeadHealthMedium", "MeadHealthMedium", "MeadHealthMinor", "MeadStaminaMedium", "MeadStaminaMedium", "MeadStaminaMinor",
     "MeadFrostResist", "MeadPoisonResist", "MeadTrollPheromones", "MeatPlatter", "QueensJam", "CookedMeat",
     "Bread", "LoxPie", "FishWraps", "SerpentStew", "Sausages", "BloodPudding"],
}
TOP = 1.9                                   # top of the highest plank's free space, under a 2 m wall
SX = {1: -2.5, 2: 0.0, 3: 2.5}
REPORT = {}
for n in (1, 2, 3):
    ox = SX[n]; oz = round(TOP - (plank_z(n - 1) + PT + CLEAR), 3)
    wall_panel(ox)
    frame_at(n, (ox, 0, oz))
    placed, skipped = pack(KITS[n], planks_blender(n, (ox, 0, oz)))
    for nm, M, kk, how in placed: spawn(nm, M)
    REPORT[n] = dict(base_z=oz, shown=[(nm, kk + 1, how) for nm, M, kk, how in placed], not_shown=skipped)
    print("PACK", n, "planks, bottom plank underside at", oz, "m:", REPORT[n])
vanilla_chest(-4.6, -0.45); post_at(4.4, -0.45)
for nm in sorted(PROTO):
    e = PTS[nm].max(0) - PTS[nm].min(0)
    print("SIZE", nm, [round(float(v), 3) for v in e], "orient(plank)", orient(nm, YB - YF, CLEAR)[:2] if orient(nm, YB - YF, CLEAR) else None)

world = bpy.data.worlds.new("w"); sc.world = world; world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.42, 0.45, 0.5, 1)
world.node_tree.nodes["Background"].inputs[1].default_value = 0.9
sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN")); sun.data.energy = 3.2
sun.rotation_euler = (math.radians(50), 0, math.radians(-30)); sc.collection.objects.link(sun)
bpy.ops.mesh.primitive_plane_add(size=60, location=(0, 0, 0))
gm = bpy.data.materials.new("ground"); gm.use_nodes = True
gm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.16, 0.14, 0.11, 1)
bpy.context.active_object.data.materials.append(gm)
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam); sc.camera = cam
sc.render.engine = "BLENDER_EEVEE_NEXT"
sc.view_settings.view_transform = "Standard"
VIEWS = {"row": (0, 8, 11.5, (0, 0, 1.0), 35, (3200, 1300)),
         "close": (-18, 12, 3.4, (0.0, 0, 1.1), 40, (1800, 1300)),
         "close3": (14, 10, 3.6, (2.5, 0, 1.05), 40, (1800, 1300)),
         "side": (-62, 10, 4.2, (2.5, 0, 1.05), 40, (1600, 1200))}
only = argv[argv.index("--views") + 1].split(",") if "--views" in argv else list(VIEWS)
for vn in only:
    yaw, pitch, dist, tgt, lens, res = VIEWS[vn]
    sc.render.resolution_x, sc.render.resolution_y = res
    cam.data.lens = lens; t = Vector(tgt)
    d = Vector((math.cos(math.radians(pitch)) * math.sin(math.radians(yaw)),
                -math.cos(math.radians(pitch)) * math.cos(math.radians(yaw)), math.sin(math.radians(pitch))))
    cam.location = t + d * dist; cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    sc.render.filepath = os.path.join(OUT, f"{TAG}-{vn}.png")
    bpy.ops.render.render(write_still=True)
print("DONE")
