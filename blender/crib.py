"""Timber Crib, our own mesh and our own texture (no vanilla geometry or texture in it).
Run: blender -b -P crib.py -- [--out DIR] [--tag NAME] [--no-ref]
Writes crib_atlas.png (128x128, point-filtered) and Crib.obj next to this script (assets/crib/), then renders a
preview beside the vanilla wood chest (local rip, reference only) for scale and palette.

Atlas: four horizontal strips, each tiling along u, so long timbers just run on in u.
  v 0.75-1.00 hewn timber side grain   v 0.50-0.75 bark
  v 0.25-0.50 end grain (4 ring tiles) v 0.00-0.25 iron
"""
import bpy, bmesh, sys, os, math, json, random
import numpy as np
from mathutils import Vector, Matrix, Euler

HERE = os.path.dirname(os.path.abspath(__file__))
OUTA = os.path.normpath(os.path.join(HERE, "..", "assets", "crib"))
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = argv[argv.index("--out") + 1] if "--out" in argv else OUTA
TAG = argv[argv.index("--tag") + 1] if "--tag" in argv else "crib"
RIP = "C:/Users/joost/ValheimRip/chests/piece_chest_wood"
os.makedirs(OUTA, exist_ok=True); os.makedirs(OUT, exist_ok=True)
rng = random.Random(7)

TEX = 128
DENS = 48.0                      # px per metre, vanilla wood is 47-57
STRIP = {"hewn": 0.75, "bark": 0.50, "end": 0.25, "iron": 0.0}

# ---------- texture ----------
def srgb(c): return np.array(c, dtype=np.float32)
# duller olive-brown, from the mid/light tones of vanilla woodchest_d (0.385,0.289,0.172 / 0.502,0.399,0.269)
WOOD, WOOD_D = srgb((0.38, 0.29, 0.18)), srgb((0.21, 0.16, 0.10))
BARK, BARK_D = srgb((0.27, 0.22, 0.16)), srgb((0.12, 0.10, 0.08))
END, END_D = srgb((0.55, 0.45, 0.31)), srgb((0.35, 0.27, 0.17))
IRON, IRON_D = srgb((0.22, 0.21, 0.20)), srgb((0.09, 0.09, 0.09))

def build_atlas():
    nr = np.random.default_rng(3)
    img = np.zeros((TEX, TEX, 3), np.float32)          # row 0 = v 0 (bottom)
    x = np.arange(TEX)[None, :].repeat(32, 0).astype(np.float32)
    y = np.arange(32)[:, None].repeat(TEX, 1).astype(np.float32)
    tile = lambda k: 2 * math.pi * k / TEX                # periodic in u
    # hewn side grain: long wavy lines along u, plank edge darkening
    g = np.sin(y * 1.25 + 1.6 * np.sin(x * tile(2) + y * 0.15) + 0.7 * np.sin(x * tile(5)))
    t = np.clip((g - 0.55) * 2.5, 0, 1) * 0.65 + nr.random((32, TEX)) * 0.18
    t += np.clip(1 - np.minimum(y, 31 - y) / 3.0, 0, 1) * 0.35
    img[96:128] = WOOD * (1 - t[..., None]) + WOOD_D * t[..., None]
    # bark: rough ridges along u
    r = np.sin(y * 1.9 + 1.3 * np.sin(x * tile(6) + y * 0.4))
    t = np.clip(r * 0.5 + 0.5, 0, 1) * 0.6 + nr.random((32, TEX)) * 0.35
    img[64:96] = BARK * (1 - t[..., None]) + BARK_D * t[..., None]
    # end grain: four 32x32 ring tiles, a bark rim
    for k in range(4):
        cx, cy = 15.5 + nr.uniform(-2, 2), 15.5 + nr.uniform(-2, 2)
        xx, yy = np.meshgrid(np.arange(32), np.arange(32))
        d = np.hypot(xx - cx, yy - cy) + 0.6 * np.sin(np.arctan2(yy - cy, xx - cx) * 3 + k)
        t = (np.sin(d * 1.5) * 0.5 + 0.5) * 0.45 + nr.random((32, 32)) * 0.15
        t = np.where(d > 13.5, 0.95, t)
        img[32:64, 32 * k:32 * k + 32] = END * (1 - t[..., None]) + END_D * t[..., None]
    # iron: mottled, darker towards the strip edges
    t = nr.random((32, TEX)) * 0.4 + np.clip(1 - np.minimum(y, 31 - y) / 4.0, 0, 1) * 0.5
    img[0:32] = IRON * (1 - t[..., None]) + IRON_D * t[..., None]
    im = bpy.data.images.new("crib_atlas", TEX, TEX, alpha=False)
    px = np.concatenate([np.clip(img, 0, 1), np.ones((TEX, TEX, 1), np.float32)], 2)
    im.pixels.foreach_set(px.ravel())
    im.filepath_raw = os.path.join(OUTA, "crib_atlas.png"); im.file_format = "PNG"; im.save()
    return im

# ---------- geometry ----------
PARTS = []   # (bmesh-built object)

def uv_face(f, kind, long_axis, seed):
    """Project one face onto its strip. long_axis 0/1/2 (local) runs along u."""
    n = f.normal
    ax = max(range(3), key=lambda i: abs(n[i]))
    tang = [i for i in range(3) if i != ax]
    if kind != "iron" and ax == long_axis:          # cut end of a timber or log
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
    vscale = min(1.0, (32 / DENS) / span)            # fit across the strip
    base = STRIP["bark" if kind == "log" else kind]
    for l in f.loops:
        u = l.vert.co[ua] * DENS / TEX + off
        v = base + ((l.vert.co[va] - vmin) * vscale * DENS / TEX) * 0.94 + 0.0075
        l[UV].uv = (u, v)

def timber(name, size, pos, kind="hewn", rot=(0, 0, 0), jitter=0.022, bevel=0.022):
    """A hewn box (or iron strap): size along local x,y,z; long axis = largest."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2]))
    long_axis = max(range(3), key=lambda i: size[i])
    for v in bm.verts:   # hand-hewn wobble, never along the length
        for i in range(3):
            if i != long_axis: v.co[i] += rng.uniform(-jitter, jitter)
    if bevel > 0:
        bmesh.ops.bevel(bm, geom=bm.edges[:], offset=bevel, segments=1, affect="EDGES")
    finish(bm, name, kind, long_axis, pos, rot)

def log(name, length, radius, pos, rot=(0, 0, 0), sides=8):
    """A round log lying along local y (across the crib), bark sides, end grain on both cuts."""
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=sides, radius1=radius, radius2=radius * rng.uniform(0.82, 0.95),
                          depth=length)
    for v in bm.verts:
        v.co.x += rng.uniform(-0.015, 0.015); v.co.y += rng.uniform(-0.015, 0.015)
    bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.radians(90), 3, "X"))
    finish(bm, name, "log", 1, pos, rot, LOGS)

def finish(bm, name, kind, long_axis, pos, rot, into=None):
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
    ob.data.materials.append(MAT); (PARTS if into is None else into).append(ob)

L, D, H = 3.0, 1.5, 1.25               # outer footprint x depth, rail height
P = 0.24                               # post section
INNER_Y = D / 2 - P / 2 + 0.03 - 0.06  # inner face of the long-side rails
INNER_X = L / 2 - P                    # inner face of the posts

def build_crib():
    hx, hy = L / 2 - P / 2, D / 2 - P / 2
    for sx in (-1, 1):
        for sy in (-1, 1):
            h = H + 0.18 + rng.uniform(-0.03, 0.03)
            timber("post", (P, P, h), (sx * hx, sy * hy, h / 2), rot=(rng.uniform(-1, 1), rng.uniform(-1, 1), 0))
    # sills on the ground, long and short, a little proud of the posts
    for sy in (-1, 1):
        timber("sill", (L + 0.12, 0.26, 0.22), (0, sy * hy, 0.11), rot=(0, 0, rng.uniform(-0.6, 0.6)))
    for sx in (-1, 1):
        timber("sill", (0.26, D - 0.1, 0.2), (sx * hx, 0, 0.21))
    # open rails on the long sides: three, gaps between (it's a crib, you see the logs)
    for sy in (-1, 1):
        for z in (0.55, 0.88, 1.18):
            timber("rail", (L - 0.05, 0.12, 0.15), (0, sy * (hy + 0.03), z),
                   rot=(rng.uniform(-1, 1), 0, rng.uniform(-0.5, 0.5)))
    # short ends: two rails and an X brace
    for sx in (-1, 1):
        for z in (0.55, 1.18):
            timber("endrail", (0.12, D - 0.05, 0.15), (sx * (hx + 0.03), 0, z))
        ang = math.degrees(math.atan2(0.6, D - 0.35))
        for s in (-1, 1):
            timber("brace", (0.08, math.hypot(D - 0.35, 0.6), 0.1), (sx * (hx + 0.06), 0, 0.87), rot=(s * ang, 0, 0))
    # floor slats
    for i in range(7):
        x = -L / 2 + 0.35 + i * (L - 0.7) / 6
        timber("slat", (0.16, D - 0.3, 0.06), (x, 0, 0.33), bevel=0.01)
    # iron: corner straps over each rail-post joint, a band round each post top
    for sx in (-1, 1):
        for sy in (-1, 1):
            x, y = sx * hx, sy * (hy + 0.1)
            for z in (0.55, 1.18):
                timber("strap", (0.36, 0.02, 0.1), (x - sx * 0.08, y, z), kind="iron", jitter=0.003, bevel=0.004)
            timber("band", (P + 0.04, P + 0.04, 0.08), (x, sy * hy, H + 0.04), kind="iron", jitter=0.003, bevel=0.006)
            for dz in (-0.025, 0.025):
                timber("rivet", (0.035, 0.035, 0.035), (x - sx * 0.2, y + sy * 0.015, 1.18 + dz), kind="iron",
                       jitter=0, bevel=0.008)
    # content: round logs across the short side, nested rows. LOGS is in fill order: bottom row first, each row
    # from the middle out, so k logs shown = k/len(LOGS) full.
    r, inner = 0.12, L - 2 * P - 0.06
    z = 0.36 + r
    for row in range(5):
        n = int(inner // (2 * r)) - (row % 2) - (1 if row == 4 else 0) * 2
        x0 = -(n - 1) * r
        order = sorted(range(n), key=lambda i: abs(i - (n - 1) / 2) + i * 1e-3)
        for i in order:   # sized to stay inside the rails (|y| < INNER_Y) and between the posts (|x| < INNER_X)
            rr = r * rng.uniform(0.82, 1.0)
            log("log", 2 * INNER_Y - 0.1 + rng.uniform(-0.16, 0.0), rr,
                (x0 + i * 2 * r + rng.uniform(-0.015, 0.015), rng.uniform(-0.03, 0.03), z + (rr - r) * 0.5),
                rot=(0, rng.uniform(-2, 2), rng.uniform(-3, 3)))
        z += r * 1.72

# ---------- scene ----------
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
atlas = build_atlas()
MAT = bpy.data.materials.new("crib"); MAT.use_nodes = True
nt = MAT.node_tree; bsdf = nt.nodes["Principled BSDF"]
ti = nt.nodes.new("ShaderNodeTexImage"); ti.image = atlas; ti.interpolation = "Closest"
nt.links.new(ti.outputs["Color"], bsdf.inputs["Base Color"])
bsdf.inputs["Roughness"].default_value = 0.8
LOGS = []
FILLS = (0.1, 0.5, 1.0)
def tris(obs): return sum(len(p.vertices) - 2 for o in obs for p in o.data.polygons)

def join(obs, name):
    bpy.ops.object.select_all(action="DESELECT")
    for o in obs: o.select_set(True)
    bpy.context.view_layer.objects.active = obs[0]
    bpy.ops.object.join(); ob = bpy.context.active_object; ob.name = name
    return ob

# one crib per fill level, same seed so all three are identical; the first (full) one is exported
cribs = []
for k, fill in enumerate(reversed(FILLS)):
    rng.seed(7); PARTS.clear(); LOGS.clear()
    build_crib()
    if k == 0:
        # no log may poke through the rails or posts
        clip = [o.name for o in LOGS if any(abs(v.co.y) > INNER_Y or abs(v.co.x) > INNER_X for v in o.data.vertices)]
        print("CLIPPING LOGS", len(clip), "of", len(LOGS))
        # export: frame as one OBJ, logs as one OBJ with an object per log in fill order (the mod shows the first n)
        stats = {"frame_tris": tris(PARTS), "log_count": len(LOGS), "logs_tris": tris(LOGS)}
        for obs, fn in ((PARTS, "Crib.obj"), (LOGS, "CribLogs.obj")):
            bpy.ops.object.select_all(action="DESELECT")
            for i, o in enumerate(obs): o.select_set(True); o.name = f"log_{i:03d}" if obs is LOGS else o.name
            bpy.ops.wm.obj_export(filepath=os.path.join(OUTA, fn), export_selected_objects=True, export_materials=False,
                                  export_triangulated_mesh=True, forward_axis="NEGATIVE_Z", up_axis="Y")
        json.dump(stats, open(os.path.join(OUTA, "crib.json"), "w")); print("CRIB", stats)
    shown = LOGS[:round(fill * len(LOGS))]
    for o in LOGS[len(shown):]: bpy.data.objects.remove(o, do_unlink=True)
    ob = join(PARTS + shown, f"crib_{int(fill * 100)}")
    ob.location.x = (len(FILLS) - 1 - k) * 3.6 - 3.6
    cribs.append(ob)

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
        q = node["rot"]; from mathutils import Quaternion
        M = Matrix.Translation(Vector(node["pos"])) @ Quaternion((q[3], q[0], q[1], q[2])).to_matrix().to_4x4() \
            @ Matrix.Diagonal((*node["scale"], 1))
        verts = [M @ v for v in V]
        verts = [Vector((-v.x - 6.2, -v.z, v.y)) for v in verts]
        F = [list(reversed(f)) for f in F]
        me = bpy.data.meshes.new("ref"); me.from_pydata(verts, [], [[c[0] for c in f] for f in F])
        uvl = me.uv_layers.new(); i = 0
        for f in F:
            for c in f: uvl.data[i].uv = T[c[1]]; i += 1
        ob = bpy.data.objects.new("ref", me); sc.collection.objects.link(ob); ob.data.materials.append(vm)

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
for vn, (yaw, pitch, dist, tgt) in {"fills": (-8, 26, 15.5, (0.2, 0, 0.5)), "close": (-35, 22, 5.2, (3.6, 0, 0.7)),
                                     "end": (75, 20, 5.0, (3.6, 0, 0.7))}.items():
    t = Vector(tgt)
    d = Vector((math.cos(math.radians(pitch)) * math.sin(math.radians(yaw)),
                -math.cos(math.radians(pitch)) * math.cos(math.radians(yaw)), math.sin(math.radians(pitch))))
    cam.location = t + d * dist; cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    sc.render.filepath = os.path.join(OUT, f"{TAG}-{vn}.png")
    bpy.ops.render.render(write_still=True)
print("DONE")
