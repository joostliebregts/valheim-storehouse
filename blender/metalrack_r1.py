"""Metal Rack round 1: NARROW AND TALL outdoor mass storage for metal bars, back to a wall, stackable like crates.
Our own furniture mesh and own 128x128 point-filtered atlas; the CONTENTS are the game's own bar models (Copper, Tin,
Bronze, Iron, Silver, BlackMetal, FlametalNew), laid as real ingot piles: per unit 3 layers of 2 bars, crosswise.
Run: blender -b -P metalrack_r1.py -- [--out DIR] [--quick] [--views a,b] [--frame-only]

Frame 1.26 W x 0.60 D x 2.00 H (Blender x, y, z; -y = front). Stackable: four corner posts carry the load, a flat top
frame at 2.00 and a flat foot at 0; the outer box is a clean rectangle (iron post bands flush with the bounds, posts 4 mm
inside them) so the mod's bounding-box corner snap points line up. Open front, iron X straps on the back and sides.
64 units = 8 shelves x (4 across x 2 deep). MIRRORED: every unit of a shelf shares one height; the mod groups the units by
height into rows of 8 (top row first) and reads each row by Unity x descending (left to right from the front), front
before back. units_data is written in that same grid order (index = grid_row * 8 + grid_col).

Copies use the mod's align rule (bar long axis -> x or z, thin axis -> up), fit_longest_m, anchor bottom, explicit layer
offsets. The renders place the bars with a Python copy of StoreModel.Place, so what you see is what the mod draws.
This file is also the shared library for metalpallet_r1.py (everything below MAIN runs only when run directly).

Atlas 128x128 rows (v from the bottom): 96-127 hewn timber, 64-95 end grain (4 ring tiles), 32-63 sawn planks, 0-31 iron.
Unity prefab space: ux = -bx, uy = bz, uz = -by. OBJ export forward NEGATIVE_Z, up Y writes (bx, bz, -by); Unity's
importer negates x, the same mapping. Item models (ValheimRip/items, extraction convention): b = (ux, uz, uy).
"""
import bpy, bmesh, sys, os, math, json, random
import numpy as np
from mathutils import Vector, Matrix, Euler
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
ITEMS_DIR = "C:/Users/joost/ValheimRip/items"
RIP = "C:/Users/joost/ValheimRip/chests/piece_chest_wood"
SCRATCH = "C:/Users/joost/AppData/Local/Temp/claude/C--Users-joost--pai/5e4bc60b-cdfe-4638-8e29-2e507fa13cf9/scratchpad/metal"
sys.path.append(ITEMS_DIR)
from load_item import load_item

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
def arg(k, d=None): return argv[argv.index(k) + 1] if k in argv else d
QUICK = "--quick" in argv
FRAME_ONLY = "--frame-only" in argv
VIEWSEL = arg("--views").split(",") if arg("--views") else None
rng = random.Random(7)

TW = TH = 128
DENS = 48.0
STRIP = {"hewn": 0.75, "end": 0.50, "plank": 0.25, "iron": 0.0}

# ---------- bars ----------
BARS = ["Copper", "Tin", "Bronze", "Iron", "Silver", "BlackMetal", "FlametalNew"]
BAR_L = 0.245            # bar length in the store (m); the native model is 0.62 m long
GAP = 0.008              # between the two bars of a layer
LIFT = 0.001             # air between layers (the bars' flat faces would otherwise touch exactly)
YAW_J, POS_J = 0.8, 0.001   # hand-laid jitter: degrees of yaw, metres along the short axis

def bar_info():
    i = json.load(open(f"{ITEMS_DIR}/Copper/info.json"))
    bmin, bmax = np.array(i["bounds_min"]), np.array(i["bounds_max"])
    sb = bmax - bmin
    size_u = np.array([sb[0], sb[2], sb[1]])          # Unity (x, y, z) from Blender item (x, z, y)
    s = BAR_L / size_u.max()
    return {"size_u": size_u, "s": s, "t": s * size_u[1], "w": s * size_u[0], "L": BAR_L}
BAR = bar_info()
PILE = 2 * BAR["w"] + GAP                             # footprint of a pile (square: 2 bars side by side ~ one bar long)
LAYER_DY = BAR["t"] + LIFT

# ---------- Unity math (a copy of the mod's StoreModel.Place for Fit.Longest + Align.Axes + anchor bottom) ----------
def u_euler(e):
    x, y, z = (math.radians(a) for a in e)
    Rx = np.array([[1, 0, 0], [0, math.cos(x), -math.sin(x)], [0, math.sin(x), math.cos(x)]])
    Ry = np.array([[math.cos(y), 0, math.sin(y)], [0, 1, 0], [-math.sin(y), 0, math.cos(y)]])
    Rz = np.array([[math.cos(z), -math.sin(z), 0], [math.sin(z), math.cos(z), 0], [0, 0, 1]])
    return Ry @ Rx @ Rz

def look_rotation(f, up):
    f = np.array(f, float); f /= np.linalg.norm(f)
    r = np.cross(up, f); r /= np.linalg.norm(r)
    u = np.cross(f, r)
    return np.column_stack([r, u, f])

def mod_place(unit_pos, copy, size, center):
    """Unity 4x4 of an item placed by the mod. size, center = the item's Unity bounds (root space)."""
    ax = copy["align"]
    il, it = int(np.argmax(size)), int(np.argmin(size))
    if it == il: it = (il + 1) % 3
    L = np.array(ax["long_axis_to"], float); L /= np.linalg.norm(L)
    T = np.array(ax["thin_axis_to"], float); T = T - L * T.dot(L); T /= np.linalg.norm(T)
    E = np.eye(3)
    align = look_rotation(T, L) @ look_rotation(E[it], E[il]).T
    r = u_euler(ax["then_rotate_euler_zxy"]) @ align
    d = np.abs(align) @ size
    s = copy["longest_m"] / size.max()
    centre = np.array(copy["offset"], float)
    centre[1] += s * d[1] * 0.5
    pos = centre - r @ (s * center)
    M = np.eye(4); M[:3, :3] = r * s; M[:3, 3] = np.array(unit_pos) + pos
    return M

AW = np.array([[-1, 0, 0], [0, 0, -1], [0, 1, 0]], float)   # Unity world -> Blender world
AI = np.array([[1, 0, 0], [0, 0, 1], [0, 1, 0]], float)     # Unity item -> Blender item
def u2b_matrix(Mu):
    M = np.eye(4); M[:3, :3] = AW @ Mu[:3, :3] @ AI.T; M[:3, 3] = AW @ Mu[:3, 3]
    return Matrix(M.tolist())
def b2u(v): return [-v[0], v[2], -v[1]]

def pile_copies(start_layer, nlayers, seed):
    """One ingot pile: nlayers x 2 bars, layer parity (global) picks the direction. Offsets in Unity, relative to the
    unit position (bottom centre of the unit's own first layer)."""
    r = random.Random(seed)
    out = []
    half = (BAR["w"] + GAP) / 2
    for j in range(nlayers):
        g = start_layer + j
        along_x = g % 2 == 0
        for side in (-1, 1):
            k = side * half + r.uniform(-POS_J, POS_J)
            yaw = r.uniform(-YAW_J, YAW_J)
            off = [0.0, j * LAYER_DY, k] if along_x else [k, j * LAYER_DY, 0.0]
            q = [0.0, math.sin(math.radians(yaw) / 2), 0.0, math.cos(math.radians(yaw) / 2)]
            out.append({"layer": j, "offset": [round(a, 5) for a in off], "longest_m": BAR_L, "anchor": "bottom",
                        "align": {"long_axis_to": [1, 0, 0] if along_x else [0, 0, 1], "thin_axis_to": [0, 1, 0],
                                  "then_rotate_euler_zxy": [0.0, round(yaw, 3), 0.0], "then_rotate_quat_xyzw": [round(a, 6) for a in q]}})
    return out

# ---------- texture ----------
def srgb(c): return np.array(c, dtype=np.float32)
WOOD, WOOD_D = srgb((0.36, 0.28, 0.18)), srgb((0.20, 0.15, 0.10))
END, END_D = srgb((0.53, 0.43, 0.30)), srgb((0.33, 0.26, 0.17))
PLNK, PLNK_D = srgb((0.47, 0.37, 0.25)), srgb((0.30, 0.23, 0.15))
IRON, IRON_D = srgb((0.22, 0.21, 0.20)), srgb((0.09, 0.09, 0.09))

def build_atlas(name, outdir):
    nr = np.random.default_rng(5)
    img = np.zeros((TH, TW, 3), np.float32)
    x = np.arange(TW)[None, :].repeat(32, 0).astype(np.float32)
    y = np.arange(32)[:, None].repeat(TW, 1).astype(np.float32)
    tile = lambda k: 2 * math.pi * k / TW
    g = np.sin(y * 1.25 + 1.6 * np.sin(x * tile(2) + y * 0.15) + 0.7 * np.sin(x * tile(5)))
    t = np.clip((g - 0.55) * 2.5, 0, 1) * 0.65 + nr.random((32, TW)) * 0.18
    t += np.clip(1 - np.minimum(y, 31 - y) / 3.0, 0, 1) * 0.35
    img[96:128] = WOOD * (1 - t[..., None]) + WOOD_D * t[..., None]
    for k in range(4):
        cx, cy = 15.5 + nr.uniform(-2, 2), 15.5 + nr.uniform(-2, 2)
        xx, yy = np.meshgrid(np.arange(32), np.arange(32))
        d = np.hypot(xx - cx, yy - cy) + 0.6 * np.sin(np.arctan2(yy - cy, xx - cx) * 3 + k)
        t = (np.sin(d * 1.5) * 0.5 + 0.5) * 0.45 + nr.random((32, 32)) * 0.15
        t = np.where(d > 13.5, 0.95, t)
        img[64:96, 32 * k:32 * k + 32] = END * (1 - t[..., None]) + END_D * t[..., None]
    # sawn planks: straighter, finer grain, a dark board seam every 16 px (v), saw marks across every 8 px (u)
    g = np.sin(y * 2.1 + 0.8 * np.sin(x * tile(3) + y * 0.3))
    t = np.clip((g - 0.6) * 2.0, 0, 1) * 0.45 + nr.random((32, TW)) * 0.16
    t += ((y % 16) == 0) * 0.55 + ((y % 16) == 15) * 0.25 + ((x % 32) < 1) * 0.12
    img[32:64] = PLNK * (1 - np.clip(t, 0, 1)[..., None]) + PLNK_D * np.clip(t, 0, 1)[..., None]
    t = nr.random((32, TW)) * 0.4 + np.clip(1 - np.minimum(y, 31 - y) / 4.0, 0, 1) * 0.5
    t += ((x % 16) == 8) * ((y % 16) == 8) * 0.6                                  # rivet heads
    img[0:32] = IRON * (1 - np.clip(t, 0, 1)[..., None]) + IRON_D * np.clip(t, 0, 1)[..., None]
    im = bpy.data.images.new(name, TW, TH, alpha=False)
    px = np.concatenate([np.clip(img, 0, 1), np.ones((TH, TW, 1), np.float32)], 2)
    im.pixels.foreach_set(px.ravel())
    return im

def save_atlas(im, path):
    tmp = path + ".part"
    im.filepath_raw = tmp; im.file_format = "PNG"; im.save()
    os.replace(tmp, path)

# ---------- frame geometry ----------
PARTS = []
MAT = None
UV = None

def uv_face(f, kind, long_axis, seed):
    n = f.normal
    ax = max(range(3), key=lambda i: abs(n[i]))
    tang = [i for i in range(3) if i != ax]
    cs = [l.vert.co for l in f.loops]
    if kind in ("hewn", "plank") and ax == long_axis:     # end grain, a whole ring tile
        k = seed % 4
        c = sum(cs, Vector()) / len(cs)
        ext = max(max(abs(v[tang[0]] - c[tang[0]]), abs(v[tang[1]] - c[tang[1]])) for v in cs) or 1
        for l in f.loops:
            a = (l.vert.co[tang[0]] - c[tang[0]]) / ext; b = (l.vert.co[tang[1]] - c[tang[1]]) / ext
            l[UV].uv = ((k + 0.5 + a * 0.45) / 4, STRIP["end"] + (0.5 + b * 0.45) * 32 / TH)
        return
    spans = [max(v[i] for v in cs) - min(v[i] for v in cs) for i in tang]
    if long_axis in tang: ua = long_axis
    else: ua = tang[0] if spans[0] >= spans[1] else tang[1]
    va = tang[1] if ua == tang[0] else tang[0]
    off = (seed * 0.37) % 1
    vmin = min(v[va] for v in cs); span = max(max(v[va] for v in cs) - vmin, 1e-4)
    vscale = min(1.0, (30 / DENS) / span)
    used = span * vscale * DENS
    shift = ((seed * 13) % 100) / 100 * max(0.0, 30 - used) if kind != "iron" else 0.0
    base = STRIP[kind]
    for l in f.loops:
        u = l.vert.co[ua] * DENS / TW + off
        v = base + (1 + shift + (l.vert.co[va] - vmin) * vscale * DENS) / TH
        l[UV].uv = (u, v)

def box(name, size, pos, kind="hewn", rot=(0, 0, 0), jitter=0.006, bevel=0.012):
    global UV
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
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    bm.normal_update()
    UV = bm.loops.layers.uv.verify()
    seed = rng.randrange(1000)
    for f in bm.faces: uv_face(f, kind, long_axis, seed)
    bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Euler([math.radians(a) for a in rot]).to_matrix())
    bmesh.ops.translate(bm, verts=bm.verts, vec=Vector(pos))
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = False
    ob = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(ob)
    ob.data.materials.append(MAT); PARTS.append(ob)
    return ob

def strap(name, a, b, plane, depth, width=0.05, thick=0.006):
    """Flat iron strap from point a to b (2D in the plane), plane 'xz' (at y = depth) or 'yz' (at x = depth)."""
    dx, dz = b[0] - a[0], b[1] - a[1]
    L = math.hypot(dx, dz); ang = math.degrees(math.atan2(dz, dx))
    mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
    if plane == "xz":
        return box(name, (L, thick, width), (mid[0], depth, mid[1]), kind="iron", rot=(0, -ang, 0), jitter=0, bevel=0.002)
    return box(name, (thick, L, width), (depth, mid[0], mid[1]), kind="iron", rot=(ang, 0, 0), jitter=0, bevel=0.002)

def corner_posts(HX, HY, H, PS, INS, bands):
    """Four load-bearing corner posts (4 mm inside the bounds) with iron bands flush with the bounds."""
    PX, PY = HX - INS - PS / 2, HY - INS - PS / 2
    for sx in (-1, 1):
        for sy in (-1, 1):
            box("post", (PS, PS, H), (sx * PX, sy * PY, H / 2), jitter=0.002, bevel=0.012)
            for z0, h in bands:
                box("band", (PS + 2 * INS, PS + 2 * INS, h), (sx * PX, sy * PY, z0 + h / 2), kind="iron", jitter=0, bevel=0.003)
    return PX, PY

def make_material(name, atlas):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; bsdf = nt.nodes["Principled BSDF"]
    ti = nt.nodes.new("ShaderNodeTexImage"); ti.image = atlas; ti.interpolation = "Closest"
    nt.links.new(ti.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 1.0
    bsdf.inputs["Specular IOR Level"].default_value = 0.0
    return m

def join(obs, name):
    bpy.ops.object.select_all(action="DESELECT")
    for o in obs: o.select_set(True)
    bpy.context.view_layer.objects.active = obs[0]
    bpy.ops.object.join(); ob = bpy.context.active_object; ob.name = name
    return ob

def clamp_bounds(ob, HX, HY, H):
    for v in ob.data.vertices:
        v.co.x = min(max(v.co.x, -HX), HX); v.co.y = min(max(v.co.y, -HY), HY); v.co.z = min(max(v.co.z, 0.0), H)
    ob.data.update()

def tris(ob): return sum(len(p.vertices) - 2 for p in ob.data.polygons)

def tri_list(me):
    V = [v.co.copy() for v in me.vertices]; T = []
    for p in me.polygons:
        vs = list(p.vertices)
        for i in range(1, len(vs) - 1): T.append((vs[0], vs[i], vs[i + 1]))
    return V, T

def export_obj(ob, path):
    bpy.ops.object.select_all(action="DESELECT"); ob.select_set(True)
    tmp = path[:-4] + ".part"
    bpy.ops.wm.obj_export(filepath=tmp, export_selected_objects=True, export_materials=False,
                          export_triangulated_mesh=True, forward_axis="NEGATIVE_Z", up_axis="Y")
    os.replace(tmp, path)

def write_json_atomic(doc, path):
    tmp = path[:-5] + ".tmp"
    with open(tmp, "w") as f: json.dump(doc, f, indent=1)
    os.replace(tmp, path)

# ---------- bar templates (render only) ----------
TEMPL = {}
def load_bars():
    for pf in BARS:
        ob = load_item(pf, anchor="origin")[0]
        ob.data.transform(ob.matrix_world); ob.matrix_world = Matrix.Identity(4)
        info = json.load(open(f"{ITEMS_DIR}/{pf}/info.json"))
        bmin, bmax = np.array(info["bounds_min"]), np.array(info["bounds_max"])
        cb, sb = (bmin + bmax) / 2, bmax - bmin
        for m in ob.data.materials:
            b = m.node_tree.nodes.get("Principled BSDF")
            if b: b.inputs["Roughness"].default_value = 0.5; b.inputs["Metallic"].default_value = 0.6
            if pf == "BlackMetal":   # the ripped tint is vivid green; the game's shader reads dark: render as dark metal
                for n in m.node_tree.nodes:
                    if n.type == "MIX": n.inputs["B"].default_value = (0.22, 0.25, 0.27, 1)
            if pf == "Silver" and b: b.inputs["Base Color"].default_value = (0.74, 0.76, 0.80, 1)
        ob.hide_render = True; ob.hide_viewport = True
        V = np.array([tuple(v.co) for v in ob.data.vertices], float)
        TEMPL[pf] = {"mesh": ob.data, "size_u": np.array([sb[0], sb[2], sb[1]]), "center_u": np.array([cb[0], cb[2], cb[1]]), "V": V,
                     "tris": [(p.vertices[0], p.vertices[i], p.vertices[i + 1]) for p in ob.data.polygons for i in range(1, len(p.vertices) - 1)]}

def place_unit(u, item):
    """Blender world matrices of a unit's copies when it holds `item` (mod placement)."""
    T = TEMPL[item]
    return [u2b_matrix(mod_place(u["position"], c, T["size_u"], T["center_u"])) for c in u["copies"]]

# ---------- checks ----------
def bar_world(M, item):
    Mn = np.array(M); return TEMPL[item]["V"] @ Mn[:3, :3].T + Mn[:3, 3]

def run_checks(units, frame, inner, top_limit, item="Copper"):
    """Clip (bar vs frame triangles), unit overlap (bar vs bar, BVH), containment (inside the posts, below the top frame).
    Checked with the given item and with BlackMetal (its root sits differently)."""
    V, T = tri_list(frame.data)
    fbvh = BVHTree.FromPolygons(V, T, all_triangles=True)
    res = {}
    for it in sorted({item, "BlackMetal"}):
        bars = []
        for u in units:
            for k, M in enumerate(place_unit(u, it)):
                W = bar_world(M, it)
                bars.append((u["index"], k, W, BVHTree.FromPolygons([Vector(w) for w in W], TEMPL[it]["tris"])))
        clip = [(a, k) for a, k, W, b in bars if fbvh.overlap(b)]
        C = np.array([W.mean(0) for _, _, W, _ in bars])
        over_units, over_in = set(), 0
        for i in range(len(bars)):
            near = np.nonzero(np.linalg.norm(C - C[i], axis=1) < 0.3)[0]
            for j in near[near > i]:
                if bars[i][3].overlap(bars[j][3]):
                    if bars[i][0] != bars[j][0]: over_units.add((bars[i][0], bars[j][0]))
                    else: over_in += 1
        lo = np.min([W.min(0) for *_, W, _ in bars], 0); hi = np.max([W.max(0) for *_, W, _ in bars], 0)
        out = int(lo[0] < inner[0] or hi[0] > inner[1] or lo[1] < inner[2] or hi[1] > inner[3] or hi[2] > top_limit)
        res[it] = {"copies": len(bars), "clipping": len(clip), "unit_overlaps": len(over_units), "overlaps_within_unit": over_in,
                   "outside_inner_box": out, "contents_x": [round(lo[0], 4), round(hi[0], 4)], "contents_y": [round(lo[1], 4), round(hi[1], 4)],
                   "contents_top_z": round(float(hi[2]), 4), "top_limit_z": top_limit}
        print("CHECK", it, json.dumps(res[it]), "clip list", clip[:10])
    return res

# ---------- scene, references, renders ----------
def setup_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)

def spawn(units, fill_items, dx, frame):
    """A copy of the frame at x offset dx with units filled: fill_items[i] = item of unit i (None = empty)."""
    fr = frame.copy(); bpy.context.scene.collection.objects.link(fr); fr.hide_render = False
    fr.location = (dx, 0, 0)
    for u, it in zip(units, fill_items):
        if not it: continue
        for k, M in enumerate(place_unit(u, it)):
            ob = bpy.data.objects.new(f"u{u['index']:02d}_{k}", TEMPL[it]["mesh"])
            bpy.context.scene.collection.objects.link(ob)
            ob.matrix_world = Matrix.Translation((dx, 0, 0)) @ M
    return fr

def references(chest_x, post_x):
    sc = bpy.context.scene
    pm = bpy.data.materials.new("plain"); pm.use_nodes = True
    pm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.55, 0.52, 0.46, 1)
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(post_x, -0.3, 0.9)); pst = bpy.context.active_object
    pst.scale = (0.12, 0.12, 1.8); pst.data.materials.append(pm); pst.name = "post_1.8m"
    rep = json.load(open("C:/Users/joost/ValheimRip/chests/report.json"))["piece_chest_wood"]["nodes"]
    vimg = bpy.data.images.load(f"{RIP}/woodchest_d.png")
    vm = bpy.data.materials.new("ref"); vm.use_nodes = True
    vt = vm.node_tree.nodes.new("ShaderNodeTexImage"); vt.image = vimg; vt.interpolation = "Closest"
    vm.node_tree.links.new(vt.outputs["Color"], vm.node_tree.nodes["Principled BSDF"].inputs["Base Color"])
    from mathutils import Quaternion
    for node in rep:
        if not node["path"].endswith(("/woodchest", "/woodchesttop_closed")): continue
        Vv, Tt, F = [], [], []
        for l in open(node["mesh"]["obj"]):
            p = l.split()
            if not p: continue
            if p[0] == "v": Vv.append(Vector((-float(p[1]), float(p[2]), float(p[3]))))
            elif p[0] == "vt": Tt.append((float(p[1]), float(p[2])))
            elif p[0] == "f": F.append([tuple(int(x) - 1 for x in q.split("/")[:2]) for q in reversed(p[1:])])
        q = node["rot"]
        M = Matrix.Translation(Vector(node["pos"])) @ Quaternion((q[3], q[0], q[1], q[2])).to_matrix().to_4x4() @ Matrix.Diagonal((*node["scale"], 1))
        verts = [M @ v for v in Vv]
        verts = [Vector((-v.x + chest_x, -v.z, v.y)) for v in verts]
        F = [list(reversed(f)) for f in F]
        me = bpy.data.meshes.new("ref"); me.from_pydata(verts, [], [[c[0] for c in f] for f in F])
        uvl = me.uv_layers.new(); i = 0
        for f in F:
            for c in f: uvl.data[i].uv = Tt[c[1]]; i += 1
        ob = bpy.data.objects.new("ref", me); sc.collection.objects.link(ob); ob.data.materials.append(vm)

def lights_and_render(out, tag, views):
    sc = bpy.context.scene
    world = bpy.data.worlds.new("w"); sc.world = world; world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.42, 0.45, 0.5, 1)
    world.node_tree.nodes["Background"].inputs[1].default_value = 0.9
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN")); sun.data.energy = 3.2
    sun.rotation_euler = (math.radians(50), 0, math.radians(35)); sc.collection.objects.link(sun)
    bpy.ops.mesh.primitive_plane_add(size=60)
    gm = bpy.data.materials.new("ground"); gm.use_nodes = True
    gm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.16, 0.14, 0.11, 1)
    bpy.context.active_object.data.materials.append(gm)
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam); sc.camera = cam
    sc.render.engine = "BLENDER_EEVEE_NEXT"
    sc.render.resolution_x, sc.render.resolution_y = (1000, 562) if QUICK else (1600, 900)
    sc.view_settings.view_transform = "Standard"
    os.makedirs(out, exist_ok=True)
    for vn, (yaw, pitch, dist, tgt, lens) in views.items():
        if VIEWSEL and vn not in VIEWSEL: continue
        t = Vector(tgt)
        d = Vector((math.cos(math.radians(pitch)) * math.sin(math.radians(yaw)),
                    -math.cos(math.radians(pitch)) * math.cos(math.radians(yaw)), math.sin(math.radians(pitch))))
        cam.location = t + d * dist; cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
        cam.data.lens = lens
        sc.render.filepath = os.path.join(out, f"{tag}-{vn}.png")
        bpy.ops.render.render(write_still=True)

def metal_mix(n_units, seed=3):
    """A believable chest: runs of each metal, in slot order."""
    runs = [("Copper", 11), ("Tin", 6), ("Bronze", 12), ("Iron", 13), ("Silver", 8), ("BlackMetal", 8), ("FlametalNew", 6)]
    seq = [m for m, k in runs for _ in range(k)]
    return (seq * 2)[:n_units]

# ====================================================================================================== MAIN (rack)
W, D, H = 1.26, 0.60, 2.00
HX, HY = W / 2, D / 2
PS, INS = 0.09, 0.004
NT, PITCH, S0 = 8, 0.236, 0.09          # shelves, shelf pitch, top of the bottom shelf
PT = 0.04                                # shelf plank thickness
LAYERS = 3
TOPZ = 1.93                              # underside of the top frame rails
COLS_X = [-0.40125, -0.13375, 0.13375, 0.40125]     # Blender x of the 4 columns (pitch 0.2675)
ROWS_Y = {"front": -0.140, "back": 0.118}            # Blender y of the 2 depth rows

def build_rack():
    PX, PY = corner_posts(HX, HY, H, PS, INS, bands=[(0.02, 0.07), (0.96, 0.06), (1.90, 0.07)])
    IX, IY = PX - PS / 2, PY - PS / 2        # inner faces of the posts: 0.536, 0.206
    RH = 0.07
    # top frame (flat at H) and foot frame (flat at 0), flush with the posts' outer faces
    for z0 in (0.0, H - RH):
        for sy in (-1, 1):
            box("rail", (2 * IX + 0.02, PS, RH), (0, sy * PY, z0 + RH / 2), jitter=0.002, bevel=0.01)
        for sx in (-1, 1):
            box("rail", (PS, 2 * IY + 0.02, RH), (sx * PX, 0, z0 + RH / 2), jitter=0.002, bevel=0.01)
    # top deck (1 cm under the top surface) keeps the rain off the top shelf
    for i, y in enumerate((-0.135, 0.0, 0.135)):
        box("deck", (2 * IX, 0.13, 0.035), (0, y, H - 0.01 - 0.0175), kind="plank", jitter=0.002, bevel=0.006)
    # shelves: 3 heavy sawn planks on side cleats, iron edge strip on the front
    y0, y1 = -HY + INS, 0.256
    pw = (y1 - y0) / 3
    for k in range(NT):
        s = S0 + k * PITCH
        for i in range(3):
            box("shelf", (2 * IX, pw - 0.006, PT), (0, y0 + pw * (i + 0.5), s - PT / 2), kind="plank", jitter=0.0, bevel=0.006)
        for sx in (-1, 1):
            box("cleat", (0.05, y1 - y0 - 0.02, 0.04), (sx * (IX - 0.025), (y0 + y1) / 2, s - PT - 0.02), jitter=0.002, bevel=0.007)
        box("edge", (2 * IX - 0.01, 0.006, 0.03), (0, -HY + 0.003, s - 0.018), kind="iron", jitter=0, bevel=0.002)
        for x in (-0.4, 0.0, 0.4):
            box("nail", (0.022, 0.006, 0.022), (x, -HY + 0.003, s - 0.018), kind="iron", jitter=0, bevel=0.003)
    # back: two timber rails and X straps (behind the shelves, against the wall)
    for z in (0.62, 1.30):
        box("backrail", (2 * IX, 0.028, 0.08), (0, 0.272, z), jitter=0.002, bevel=0.008)
    for za, zb in ((RH, 0.96), (0.96, H - RH)):
        strap("xb", (-IX, za), (IX, zb), "xz", HY - 0.006, thick=0.004)
        strap("xb", (-IX, zb), (IX, za), "xz", HY - 0.002, thick=0.004)
    # sides: X straps in the side planes, flush outside
    for sx in (-1, 1):
        for za, zb in ((RH, 0.96), (0.96, H - RH)):
            strap("xs", (-IY, za), (IY, zb), "yz", sx * (HX - 0.006), thick=0.004)
            strap("xs", (-IY, zb), (IY, za), "yz", sx * (HX - 0.002), thick=0.004)
    return IX, IY

def rack_units():
    units = []
    for k in range(NT):                       # grid_row 0 = top shelf
        tier = NT - 1 - k
        s = S0 + tier * PITCH
        col = 0
        for cx in sorted(COLS_X):             # Blender x ascending = left to right from the front
            for row in ("front", "back"):
                bpos = (cx, ROWS_Y[row], s + 0.001)   # 1 mm of air over the plank
                idx = k * 8 + col
                units.append({"index": idx, "grid_row": k, "grid_col": col, "shelf_from_bottom": tier, "column": sorted(COLS_X).index(cx),
                              "depth_row": row, "position": [round(a, 5) for a in b2u(bpos)], "rotation": [0.0, 0.0, 0.0],
                              "box_size": [round(PILE, 4), round(LAYERS * LAYER_DY, 4), round(PILE, 4)], "render_item": "Copper",
                              "copies": pile_copies(0, LAYERS, 1000 + idx)})
                col += 1
    return units

def grid_order_check(units):
    """The mod's GridOrder on these units: must give index order."""
    P = [u["position"] for u in units]
    by_h = sorted(range(len(units)), key=lambda i: -P[i][1])
    order = []
    for r in range(8):
        row = sorted(by_h[r * 8:(r + 1) * 8], key=lambda i: (-P[i][0], -P[i][2]))
        order += row
    return order == list(range(len(units))), order

if __name__ == "__main__":
    OUTA = os.path.normpath(os.path.join(HERE, "..", "assets", "metalrack_r1"))
    OUT = arg("--out", os.path.join(SCRATCH, "rack"))
    os.makedirs(OUTA, exist_ok=True); os.makedirs(OUT, exist_ok=True)
    setup_scene()
    atlas = build_atlas("metalrack_atlas", OUTA)
    MAT = make_material("metalrack", atlas)
    load_bars()
    IX, IY = build_rack()
    frame = join(list(PARTS), "MetalRack")
    clamp_bounds(frame, HX, HY, H)
    ftris = tris(frame)
    bb = np.array([tuple(v.co) for v in frame.data.vertices])
    print("RACK frame tris", ftris, "bounds", bb.min(0).round(4), bb.max(0).round(4))
    units = rack_units()
    ok, order = grid_order_check(units)
    print("GRID mirror order ok", ok)
    chk = run_checks(units, frame, (-IX, IX, -HY, 0.256), TOPZ)
    save_atlas(atlas, os.path.join(OUTA, "metalrack_atlas.png"))
    export_obj(frame, os.path.join(OUTA, "MetalRack.obj"))
    doc = {
        "schema": "storehouse-anchors/1", "furniture": "Metal Rack", "slug": "metalrack", "round": 1,
        "unit_count": len(units), "slots_designed_for": 64, "stack_per_unit": True, "mirror": True,
        "frame": {"obj": "MetalRack.obj", "atlas": "metalrack_atlas.png 128x128 point", "tris": ftris, "size_m": [W, H, D],
                  "bounds_unity": {"min": [-HX, 0.0, -HY], "max": [HX, H, HY]},
                  "stacking": "four corner posts carry the load; flat top at y=2.00 and flat foot at y=0; the outer box is exactly the bounds "
                              "(iron post bands flush with it, posts 4 mm inside), so bounding-box corner snap points stack one rack on another. "
                              "Contents stay inside the posts and below the top frame (y < 1.93)."},
        "space": {"unity": "prefab space, origin on the floor at the centre of the footprint, +z front, +y up, +x to the furniture's left seen from the front",
                  "from_blender": "ux=-bx, uy=bz, uz=-by"},
        "fill_order": "MIRROR grid order: index = grid_row * 8 + grid_col; grid_row 0 = the top shelf; each row left to right seen from the front, "
                      "in pairs (front unit, then the back unit behind it). All 8 units of a shelf share one position.y, so the mod's GridOrder "
                      "(rows of 8 by position.y descending, each by position.x descending, then z descending) gives exactly this order.",
        "position": "unit position = bottom centre of its pile, on the shelf top. box_size = [x, y, z] Unity, informational.",
        "copy_rule": "Each copy = one bar: align (long axis -> long_axis_to, thin axis -> up), then then_rotate (a little yaw), uniform scale so the "
                     "longest side = longest_m, anchor bottom (the turned bounds' bottom at unit.position + offset). Layer j sits at offset.y = j * "
                     f"{LAYER_DY:.5f} m (one bar's thickness at {BAR_L} m long + 1 mm). Copies are listed bottom layer first, 2 per layer, "
                     "crosswise layers: even layers along x, odd along z.",
        "items": {"all_bars": {"bounds_size_unity": [round(a, 4) for a in BAR["size_u"]], "longest_m": BAR_L, "scale": round(BAR["s"], 5),
                               "bar_size_m": [round(BAR["L"], 4), round(BAR["t"], 4), round(BAR["w"], 4)],
                               "note": "Copper, Tin, Bronze, Iron, Silver, BlackMetal, Flametal and FlametalNew share one 44-triangle bar mesh"}},
        "layout": {"shelves": NT, "shelf_pitch_m": PITCH, "bottom_shelf_top_y": S0, "per_shelf": "4 across x 2 deep", "layers_per_pile": LAYERS,
                   "bars_per_unit": LAYERS * 2, "pile_footprint_m": round(PILE, 4)},
        "checks": {"grid_mirror_order_ok": ok, **chk},
        "units_data": units}
    write_json_atomic(doc, os.path.join(OUTA, "MetalRackAnchors.json"))
    print("WROTE", OUTA)
    if "--no-render" in argv: sys.exit(0)
    SP = 1.9
    mix = metal_mix(64)
    fills = {"empty": 0, "10": 6, "50": 32, "100": 64}
    for i, (nm, n) in enumerate(fills.items()):
        spawn(units, [mix[j] if j < n else None for j in range(64)], i * SP, frame)
    frame.hide_render = True
    references(chest_x=-1.55, post_x=-2.6)
    # a stacked pair beside the fills: an empty rack standing on a 50 % rack, to show the posts carry it
    spawn(units, [mix[j] if j < 32 else None for j in range(64)], 4 * SP + 0.4, frame)
    top = spawn(units, [None] * 64, 4 * SP + 0.4, frame); top.location.z = H
    cx = 2 * SP
    views = {"fills": (-6, 12, 13.0, (cx - 1.0, 0, 1.4), 38), "close": (-20, 8, 2.7, (3 * SP, 0, 1.55), 40),
             "low": (-30, 6, 2.6, (3 * SP, 0, 0.55), 40), "side": (62, 20, 4.2, (3 * SP, 0, 1.0), 40),
             "stack": (-35, 14, 6.0, (4 * SP + 0.4, 0, 2.0), 40)}
    lights_and_render(OUT, "metalrack", views)
    print("DONE")
