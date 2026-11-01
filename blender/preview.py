"""Preview renderer: vanilla BlackMetalChest (local rip, reference only) next to the Strongbox.
Run: blender -b -P preview.py -- [--out DIR] [--only-vanilla] [--tag NAME]
All geometry is handled in Unity space and converted to Blender with (x,y,z)_b = (-ux, -uz, uy).
"""
import bpy, sys, os, math, json
from mathutils import Vector, Quaternion, Matrix

RIP = "C:/Users/joost/ValheimRip/chests/piece_chest_blackmetal"
HERE = os.path.dirname(os.path.abspath(__file__))
SB = os.path.normpath(os.path.join(HERE, "..", "assets", "strongbox"))
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = argv[argv.index("--out") + 1] if "--out" in argv else SB
TAG = argv[argv.index("--tag") + 1] if "--tag" in argv else "preview"
ONLY_VANILLA = "--only-vanilla" in argv
LOD = "LOD" if "--lod" in argv else ""
TEX = os.path.join(RIP, "BlackMetalChest_D.png")

def read_obj(fn, unitypy):
    V, T, N, F = [], [], [], []
    for l in open(fn):
        p = l.split()
        if not p: continue
        if p[0] == "v": V.append([float(x) for x in p[1:4]])
        elif p[0] == "vt": T.append([float(x) for x in p[1:3]])
        elif p[0] == "f":
            F.append([tuple(int(x) - 1 if x else -1 for x in (q.split("/") + ["", ""])[:2]) for q in p[1:]])
    if unitypy:  # UnityPy writes (-ux,uy,uz) and reversed winding
        V = [[-v[0], v[1], v[2]] for v in V]
        F = [list(reversed(f)) for f in F]
    return V, T, F

def u2b(v):
    return Vector((-v[0], -v[2], v[1]))

def make(name, V, T, F, chain, offset_u=(0, 0, 0)):
    """chain: list of (pos, rot(x,y,z,w), scale) from outermost to innermost (Unity local transforms)."""
    M = Matrix.Identity(4)
    for pos, rot, sc in chain:
        q = Quaternion((rot[3], rot[0], rot[1], rot[2]))
        M = M @ (Matrix.Translation(Vector(pos)) @ q.to_matrix().to_4x4() @ Matrix.Diagonal((sc[0], sc[1], sc[2], 1)))
    verts = [u2b(M @ Vector(v) + Vector(offset_u)) for v in V]
    # Unity winding is clockwise-from-outside; Blender wants counter-clockwise -> reverse every face
    F = [list(reversed(f)) for f in F]
    faces = [[c[0] for c in f] for f in F]
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], faces)
    uvl = me.uv_layers.new(name="UV")
    li = 0
    for f in F:
        for c in f:
            uvl.data[li].uv = T[c[1]] if c[1] >= 0 else (0, 0)
            li += 1
    me.update()
    for p in me.polygons: p.use_smooth = False
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob.data.materials.append(MAT)
    return ob

# ---------- scene ----------
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
img = bpy.data.images.load(TEX)
MAT = bpy.data.materials.new("BlackMetalChest_preview")
MAT.use_nodes = True
nt = MAT.node_tree
bsdf = nt.nodes["Principled BSDF"]
ti = nt.nodes.new("ShaderNodeTexImage"); ti.image = img; ti.interpolation = "Closest"
nt.links.new(ti.outputs["Color"], bsdf.inputs["Base Color"])
bsdf.inputs["Roughness"].default_value = 0.75
bsdf.inputs["Metallic"].default_value = 0.0

ROOT = [((0, 0, 0), (0, 0, 0, 1), (1, 1, 1))]
BODY_T = ((0, 0, 0), (0, -1, 0, 0), (0.9, 0.9, 0.9))
OPEN_T, CLOSED_T = BODY_T, BODY_T
LID_CLOSED = ((0, 0.907, 0), (0, 0, 0, 1), (1, 1, 1))
LID_OPEN = ((0, 1.218, 0.016), (0.259, 0, 0, 0.966), (1, 1, 1))

def scene_objects(open_lid):
    obs = []
    V, T, F = read_obj(f"{RIP}/blackmetalchest{LOD}.obj", True)
    vx = -1.5 if not ONLY_VANILLA else 0
    obs.append(make("vanilla_body", V, T, F, ROOT + [BODY_T], (vx, 0, 0)))
    V, T, F = read_obj(f"{RIP}/blackmetalchesttop_closed{LOD}.obj", True)
    obs.append(make("vanilla_lid", V, T, F, ROOT + [BODY_T, LID_OPEN if open_lid else LID_CLOSED], (vx, 0, 0)))
    if not ONLY_VANILLA:
        meta = json.load(open(os.path.join(SB, "strongbox.json")))
        ox = 2.1
        V, T, F = read_obj(os.path.join(SB, f"StrongboxBody{LOD}.obj"), False)
        obs.append(make("sb_body", V, T, F, ROOT + [BODY_T], (ox, 0, 0)))
        V, T, F = read_obj(os.path.join(SB, f"StrongboxLid{LOD}.obj"), False)
        lt = meta["lid_transform_open"] if open_lid else meta["lid_transform_closed"]
        obs.append(make("sb_lid", V, T, F, ROOT + [BODY_T, (lt["pos"], lt["rot"], (1, 1, 1))], (ox, 0, 0)))
    return obs

# lights / world
world = bpy.data.worlds.new("w"); sc.world = world; world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.42, 0.45, 0.5, 1)
world.node_tree.nodes["Background"].inputs[1].default_value = 0.9
sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
sun.data.energy = 3.2; sun.rotation_euler = (math.radians(50), 0, math.radians(35))
sc.collection.objects.link(sun)
# ground
bpy.ops.mesh.primitive_plane_add(size=30)
g = bpy.context.active_object
gm = bpy.data.materials.new("ground"); gm.use_nodes = True
gm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.16, 0.14, 0.11, 1)
g.data.materials.append(gm)

cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam); sc.camera = cam
cam.data.lens = 50
sc.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items] else "BLENDER_EEVEE"
sc.render.resolution_x, sc.render.resolution_y = 1600, 900
sc.view_settings.view_transform = "Standard"
try: sc.eevee.taa_render_samples = 32
except Exception: pass

def look(cam, target, dist, yaw, pitch):
    t = Vector(target)
    d = Vector((math.cos(math.radians(pitch)) * math.sin(math.radians(yaw)), -math.cos(math.radians(pitch)) * math.cos(math.radians(yaw)), math.sin(math.radians(pitch))))
    cam.location = t + d * dist
    cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()

# Prefab front = Unity +Z = Blender -Y. Camera at -Y looks at the front.
views = {"front": (-22, 16), "back": (150, 20)} if not ONLY_VANILLA else {"front": (-25, 18), "back": (155, 22), "top": (0, 70)}
center = (-0.3, 0, 0.75) if not ONLY_VANILLA else (0, 0, 0.5)
dist = 12.5 if not ONLY_VANILLA else 5.5
if "--views" in argv:   # e.g. --views det1:-30:15,det2:120:25 --center -2.1,0,0.8 --dist 6
    views = {v.split(":")[0]: (float(v.split(":")[1]), float(v.split(":")[2])) for v in argv[argv.index("--views") + 1].split(",")}
if "--center" in argv: center = tuple(float(x) for x in argv[argv.index("--center") + 1].split(","))
if "--dist" in argv: dist = float(argv[argv.index("--dist") + 1])
os.makedirs(OUT, exist_ok=True)
for open_lid in (False, True):
    obs = scene_objects(open_lid)
    for vn, (yaw, pitch) in views.items():
        look(cam, center, dist, yaw, pitch)
        sc.render.filepath = os.path.join(OUT, f"{TAG}-{vn}-{'open' if open_lid else 'closed'}.png")
        bpy.ops.render.render(write_still=True)
    for o in obs: bpy.data.objects.remove(o, do_unlink=True)
print("DONE")
