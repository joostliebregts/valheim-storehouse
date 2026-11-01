"""Ore Bin round 5: the same furniture as round 4 (OBJ + atlas copied byte-identical from assets/orebin_r4), new contents
that make a FULL bin (80/80 stacks) look full: every compartment heaped up to its wall tops and crowned over them in the
middle like a shovelled pile, at 50% visibly half (Joost, 80/80 in game: "it needs to be fuller than this when it's full").
Run: blender -b -P orebin_r5.py -- [--out DIR] [--assets DIR] [--tag NAME] [--quick] [--no-render] [--views a,b]
     [--cseed N] contents seed   [--nc CopperOre:4/3,...] copies per stack, cycled   [--quota CopperOre:12,...]
     [--crown K] [--capover M]   [--adaptive --nmin N --nmax N --fill F] copies per stack from the open volume (calibration)
Renders (in --out): full34 / half34 (standing three-quarter view), fullfront / halffront (standing, from the front),
r4r5 (round 4 full beside round 5 full, both replayed from their EXPORTED files the mod's way), top (overview).

Why round 5: round 4 had 1-3 copies per stack (187 copies) and its heaps peaked at 0.85-0.93 m (front row) and 1.19-1.32 m
(back row), well under the walls: a full bin read as a third full. Round 5 keeps round 4's item scales (0.36-0.50 of true
size) and raises the copies per stack instead. How many fit is set by the compartment, not by taste: at round 4's lump
size a compartment filled to its target surface holds ~30 (tin, flametal), ~43 (copper, silver), ~57-65 (the scrap) copies;
asking more (5/4 copper, 6/5 iron, ...) just left the last stacks with nothing that would stay inside. So 2-5 per stack.

Contents: 80 units (one unit = one full stack), one item type per compartment, the same layout, scales and fill order
interleaving as round 4. Each compartment gets a TARGET SURFACE: from every boundary the visible wall top (stone + cap,
2 cm under it), rising inward at slope CROWN (a shovelled pile resting against its walls), so the heap meets each wall at
its top and crowns over the walls in the middle (never more than CAPOVER over its highest wall). Copies are dropped stack by stack (earlier stacks frozen) at the spot of
16 random candidates that lies furthest under the target surface (with a pull towards the back wall, BACKW, so the heap
grows from the back forward and a half-full bin shows its heaps over the low front), from just above the local heap, and settled with
Blender rigid bodies (convex hulls, friction 0.75, restitution 0, as round 4). Copies per stack: NCOPY (cycled per stack,
from --adaptive calibration runs). A copy that ends leaning on an invisible collider above a visible wall top, outside its
compartment or touching the frame is taken out and dropped again from a spot further from the walls (the stack's good
copies stay and are re-settled with it).
unit.position is the centre of the unit's box (round 4: mean of the copy centres); the box's bottom is the lowest corner of
any copy's rotated bounds, so the mod's never-below-the-floor lift (Storehouse.cs, a copy's transformed bounds vs
unit.Pos.y - unit.Box.y / 2) never moves a copy of the item the heap was settled with.
Files: OBJ + atlas copied first, anchors last (temp file + rename, so the mod's live reload never sees half a round).
"""
import bpy, bmesh, sys, os, math, json, random, time, shutil
import numpy as np
from mathutils import Vector, Matrix, Euler, Quaternion
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, ".."))
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
def arg(k, d=None): return argv[argv.index(k) + 1] if k in argv else d
OUTA = arg("--assets", os.path.join(REPO, "assets", "orebin_r5"))
OUT = arg("--out", OUTA)
R4 = os.path.join(REPO, "assets", "orebin_r4")
TAG = arg("--tag", "orebin5")
QUICK = "--quick" in argv
NORENDER = "--no-render" in argv
VIEWSEL = arg("--views").split(",") if "--views" in argv else None
ITEMS_DIR = "C:/Users/joost/ValheimRip/items"
sys.path.append(ITEMS_DIR)
from load_item import load_item
os.makedirs(OUTA, exist_ok=True); os.makedirs(OUT, exist_ok=True)
CSEED = int(arg("--cseed", 51))
crng = random.Random(CSEED)
NMIN, NMAX = int(arg("--nmin", 4)), int(arg("--nmax", 7))
CROWN = float(arg("--crown", 0.85))          # slope of the target surface inward from the wall tops (0.85 = 40 degrees)
CAPOVER = float(arg("--capover", 0.15))      # and never more than this over the compartment's highest wall top
FILL = float(arg("--fill", 1.35))            # the surface-based fill estimate counts the voids under the top lumps as full: over-ask by this
BACKW = float(arg("--backw", 2.0))           # pull towards the back wall (m of target deficit): the heap grows from the back
                                             # wall forward, so a half-full bin shows heaps against the back over its low front
EDGE = 0.02                                  # target surface meets the walls this far under their visible top

# ---- round 4's layout (Blender metres, z up, -y = front); the furniture itself is round 4's exported OBJ ----
FLOOR, BACK_FLOOR = 0.14, 0.30
ROWFLOOR = {0: FLOOR, 1: BACK_FLOOR}
HX, HY, PS = 1.90, 0.95, 0.22
LIMX, LIMY = HX - PS, HY - PS
COURSE = 0.205
def LEV(n): return FLOOR + COURSE * n
DIVT, CT, YC = 0.12, 0.16, -0.06
CELLW = (2 * LIMX - 2 * DIVT) / 3
YMIDSTEP = -0.40
YSTEP5 = YC + 0.30
YSTART = [-LIMY, -LIMY, -LIMY, YMIDSTEP, YC - CT / 2, YSTEP5]
CAPH = 0.08
FRONT_RAIL_TOP = 0.785

def side_top(y):
    n = max(c for c in range(6) if y >= YSTART[c] - 1e-6) + 1
    return LEV(n)

ITEMS = [("CopperOre", "copper ore", False), ("TinOre", "tin ore", False), ("IronScrap", "iron scrap", True),
         ("SilverOre", "silver ore", False), ("BlackMetalScrap", "black metal scrap", True), ("FlametalOreNew", "flametal ore", False)]
SCALE = {"CopperOre": 0.45, "TinOre": 0.48, "IronScrap": 0.50, "SilverOre": 0.45, "BlackMetalScrap": 0.50, "FlametalOreNew": 0.36}   # round 4's
QUOTA = {"CopperOre": 12, "TinOre": 15, "IronScrap": 14, "SilverOre": 14, "BlackMetalScrap": 15, "FlametalOreNew": 10}   # 80 stacks
# copies per stack, cycled per stack: the compartment's capacity up to its target surface (measured with --adaptive runs:
# copper ~43, flametal ~31, silver ~43, tin ~31, black metal ~57, iron ~65 copies) over its stacks, a little under it so the
# last stacks still find room. --adaptive sets them from the open volume instead (calibration).
NCOPY = {"CopperOre": (4, 3, 4, 3, 3), "TinOre": (2, 2, 2, 2, 2, 2, 1), "IronScrap": (5, 4), "SilverOre": (3,), "BlackMetalScrap": (4, 4, 3), "FlametalOreNew": (3, 3, 2)}
ADAPTIVE = "--adaptive" in argv
if "--nc" in argv:
    for kv in arg("--nc").split(","):
        k, v = kv.split(":"); NCOPY[k] = tuple(int(a) for a in v.split("/"))
if "--quota" in argv:
    for kv in arg("--quota").split(","):
        k, v = kv.split(":"); QUOTA[k] = int(v)
LAYOUT = {(0, 1): "CopperOre", (1, 1): "FlametalOreNew", (2, 1): "SilverOre",
          (0, 0): "TinOre", (1, 0): "BlackMetalScrap", (2, 0): "IronScrap"}
NUNITS = 80
assert sum(QUOTA.values()) == NUNITS, QUOTA
MARGIN = 0.003
FPS = 24

def cell_bounds(col, row):
    x0 = -LIMX + col * (CELLW + DIVT); x1 = x0 + CELLW
    ix0 = 0.025 if col == 0 else 0.03; ix1 = 0.025 if col == 2 else 0.03
    if row == 0: y0, y1 = -LIMY + 0.025, YC - CT / 2 - 0.03
    else: y0, y1 = YC + CT / 2 + 0.03, LIMY - 0.01
    return (x0 + ix0, x1 - ix1, y0, y1)

def wall_top(col, row, side, y=None):
    """visible top (stone + cap) of the wall behind a cell boundary"""
    if side == "y0": return FRONT_RAIL_TOP if row == 0 else LEV(4) + CAPH
    if side == "y1": return LEV(4) + CAPH if row == 0 else LEV(6) + CAPH
    return side_top(y) + CAPH

def target(col, row, x, y):
    """target heap surface: each wall's top (EDGE under it) rising inward at CROWN; the lowest of the four governs"""
    x0, x1, y0, y1 = cell_bounds(col, row)
    x = np.asarray(x, np.float64); y = np.asarray(y, np.float64)
    sy = np.vectorize(side_top)(y) + CAPH
    t = np.minimum.reduce([sy - EDGE + CROWN * (x - x0), sy - EDGE + CROWN * (x1 - x),
                           wall_top(col, row, "y0") - EDGE + CROWN * (y - y0), wall_top(col, row, "y1") - EDGE + CROWN * (y1 - y)])
    return np.minimum(t, max(wall_top(col, row, "y0"), wall_top(col, row, "y1"), side_top(y1) + CAPH) + CAPOVER)

TEMPL = {}
def load_templates():
    for pf, _lab, _flat in ITEMS:
        ob = load_item(pf, anchor="center")[0]
        info = json.load(open(f"{ITEMS_DIR}/{pf}/info.json"))
        bmin, bmax = Vector(info["bounds_min"]), Vector(info["bounds_max"])
        size = bmax - bmin
        s = SCALE[pf]
        ob.data.transform(Matrix.Diagonal((s, s, s, 1))); ob.data.update()
        ob.location = (0, 0, 0); ob.scale = (1, 1, 1)
        if pf == "TinOre":                  # blown-out white crystals -> pale grey (render only)
            for m in ob.data.materials:
                b = m.node_tree.nodes.get("Principled BSDF")
                if b and not any(n.type == "TEX_IMAGE" for n in m.node_tree.nodes): b.inputs["Base Color"].default_value = (0.62, 0.64, 0.68, 1)
        if pf == "BlackMetalScrap":         # the ripped tint is a vivid green; render it as dark metal (render only)
            for m in ob.data.materials:
                for n in m.node_tree.nodes:
                    if n.type == "MIX": n.inputs["B"].default_value = (0.20, 0.22, 0.27, 1)
        for m in ob.data.materials:
            b = m.node_tree.nodes.get("Principled BSDF")
            if b: b.inputs["Specular IOR Level"].default_value = 0.1; b.inputs["Roughness"].default_value = 0.95
        ob.hide_render = True; ob.hide_viewport = True; ob.location = (0, 0, -50)
        V = np.array([tuple(v.co) for v in ob.data.vertices], np.float32)
        bm = bmesh.new(); bm.from_mesh(ob.data)
        hull = bmesh.ops.convex_hull(bm, input=bm.verts)
        planes = []
        for f in [g for g in hull["geom"] if isinstance(g, bmesh.types.BMFace)]:
            n = f.normal.copy(); planes.append((n.x, n.y, n.z, n.dot(f.verts[0].co)))
        hv = np.array(sorted({tuple(round(c, 5) for c in v.co) for v in hull["geom"] if isinstance(v, bmesh.types.BMVert)}), np.float32)
        bm.free()
        TEMPL[pf] = {"obj": ob, "mesh": ob.data, "V": V, "s": float(s), "size": tuple(size), "center": tuple((bmin + bmax) / 2),
                     "planes": np.array(planes, np.float32), "hv": hv, "radius": float(np.linalg.norm(V, axis=1).max()),
                     "vol": float(size.x * size.y * size.z * s ** 3),
                     "he": (V.max(0) - V.min(0)) / 2, "mid": (V.max(0) + V.min(0)) / 2,     # local AABB (renderer bounds) half extents, centre
                     "tris": [(p.vertices[0], p.vertices[i], p.vertices[i + 1]) for p in ob.data.polygons for i in range(1, len(p.vertices) - 1)]}

def build_order():
    """80 stacks, interleaved over the six compartments by quota so every prefix is a whole, spread-out fill (as round 4)."""
    seq = []
    for (col, row), pf in LAYOUT.items():
        q = QUOTA[pf]
        for k in range(q):
            seq.append(((k + 0.5) / q + crng.uniform(-0.01, 0.01), col, row, pf, k))
    seq.sort(key=lambda t: t[0])
    return [{"index": n, "step": n * 8 // NUNITS, "col": col, "row": row, "item": pf, "k": k, "copies": []}
            for n, (_sc, col, row, pf, k) in enumerate(seq[:NUNITS])]

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

def euler_rand(flat):
    if flat:
        return Euler((math.radians(crng.uniform(-14, 14)), math.radians(crng.uniform(-14, 14)), crng.uniform(0, math.tau)), "XYZ")
    return Euler((crng.uniform(0, math.tau), crng.uniform(0, math.tau), crng.uniform(0, math.tau)), "XYZ")

def world_verts(pf, M):
    Mn = np.array(M)
    return TEMPL[pf]["V"] @ Mn[:3, :3].T + Mn[:3, 3]

def inside(W, col, row):
    x0, x1, y0, y1 = cell_bounds(col, row)
    return not ((W[:, 0] < x0 - 0.006).any() or (W[:, 0] > x1 + 0.006).any() or (W[:, 1] < y0 - 0.006).any()
                or (W[:, 1] > y1 + 0.006).any() or (W[:, 2] < ROWFLOOR[row] - 0.006).any())

def lean_over(W, col, row):
    """how far a copy rises above the visible wall top where it is within 2 cm of a compartment boundary (<= 0: fine)"""
    x0, x1, y0, y1 = cell_bounds(col, row)
    over = -1.0
    for side, d in (("x0", W[:, 0] - x0), ("x1", x1 - W[:, 0]), ("y0", W[:, 1] - y0), ("y1", y1 - W[:, 1])):
        near = d < 0.02
        if not near.any(): continue
        for w in W[near]:
            over = max(over, float(w[2]) - wall_top(col, row, side, float(w[1])))
    return over

GRID = 0.04
def surface(HV, col, row):
    """heap surface on a 4 cm grid over the compartment: the highest hull vertex per cell, gaps closed by a 3x3 max"""
    x0, x1, y0, y1 = cell_bounds(col, row)
    nx, ny = int(math.ceil((x1 - x0) / GRID)), int(math.ceil((y1 - y0) / GRID))
    H = np.full((nx, ny), ROWFLOOR[row], np.float64)
    if len(HV):
        ix = np.clip(((HV[:, 0] - x0) / GRID).astype(int), 0, nx - 1); iy = np.clip(((HV[:, 1] - y0) / GRID).astype(int), 0, ny - 1)
        np.maximum.at(H, (ix, iy), HV[:, 2])
        P = np.pad(H, 1, mode="edge")
        H = np.max([P[i:i + nx, j:j + ny] for i in range(3) for j in range(3)], axis=0)
    gx = x0 + (np.arange(nx) + 0.5) * GRID; gy = y0 + (np.arange(ny) + 0.5) * GRID
    X, Y = np.meshgrid(gx, gy, indexing="ij")
    return H, target(col, row, X, Y)

SIMLOG = {"frames": [], "wall": 0.0, "unsettled": 0, "resid": [], "retries": 0, "cells": {}}
def simulate_all(units):
    sc = bpy.context.scene
    sc.render.fps = FPS
    bpy.ops.rigidbody.world_add()
    rbw = sc.rigidbody_world
    rbw.substeps_per_frame = 20; rbw.solver_iterations = 40; rbw.time_scale = 1.0
    rbw.point_cache.frame_start = 1; rbw.point_cache.frame_end = 400
    sc.frame_start = 1; sc.frame_end = 400
    t0 = time.time()
    for (col, row), pf in LAYOUT.items():
        coll = bpy.data.collections.new(f"rb_{col}{row}")
        rbw.collection = coll
        x0, x1, y0, y1 = cell_bounds(col, row)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        T = 0.3; H = 5.0
        FL = ROWFLOOR[row]
        walls = [("floor", (x1 - x0 + 2 * T, y1 - y0 + 2 * T, T), (cx, cy, FL + 0.006 - T / 2)),
                 ("wx0", (T, y1 - y0 + 2 * T, H), (x0 - T / 2, cy, FLOOR + H / 2)), ("wx1", (T, y1 - y0 + 2 * T, H), (x1 + T / 2, cy, FLOOR + H / 2)),
                 ("wy0", (x1 - x0, T, H), (cx, y0 - T / 2, FLOOR + H / 2)), ("wy1", (x1 - x0, T, H), (cx, y1 + T / 2, FLOOR + H / 2))]
        for nm, sz, pos in walls:
            ob = bpy.data.objects.new(f"col_{col}{row}_{nm}", make_box_mesh(nm, sz)); ob.location = pos
            sc.collection.objects.link(ob); add_rb(ob, "PASSIVE", "BOX"); ob.hide_render = True
        sc.frame_set(1)
        flat = next(i[2] for i in ITEMS if i[0] == pf)
        T_ = TEMPL[pf]
        R = T_["radius"]
        HV = np.zeros((0, 3), np.float32)
        def local_top(x, y, r):
            if not len(HV): return FL
            m = (HV[:, 0] - x) ** 2 + (HV[:, 1] - y) ** 2 < r ** 2
            return float(HV[m, 2].max()) if m.any() else FL
        mine = [u for u in units if u["col"] == col and u["row"] == row]
        Hs, Tg = surface(HV, col, row)
        vtarget = float(np.maximum(Tg - FL, 0).sum()) * GRID * GRID
        v0 = T_["vol"] * 0.55 / 0.40       # prior volume per copy: hull ~55% of its box, heap packing ~40%
        ncop = 0
        for si, u in enumerate(mine):
            Hs, Tg = surface(HV, col, row)
            filled = float(np.clip(np.minimum(Hs, Tg) - FL, 0, None).sum()) * GRID * GRID
            veff = filled / ncop if ncop >= 10 else v0
            open_ = max(vtarget - filled, 0.0)
            want = FILL * open_ / max(veff, 1e-6) / (len(mine) - si)
            u["ncopy"] = int(min(NMAX, max(NMIN, round(want)))) if ADAPTIVE else NCOPY[pf][u["k"] % len(NCOPY[pf])]
            deficit = Tg - Hs
            gap = 1.0 * max(T_["size"]) * T_["s"] * (0.7 if flat else 1.0)
            NATT = 16
            # copies that ended fine stay (still active, restarted from their settled pose); only the bad ones are
            # dropped again, from spots further from the walls
            kept = []; pending = u["ncopy"]; spots = []
            for attempt in range(NATT):
                inset = R * 0.55 + 0.02 + (0.03 * min(attempt - 1, 7) if attempt > 1 else 0.0)
                sx = max(0.02, (x1 - x0) / 2 - inset); sy = max(0.02, (y1 - y0) / 2 - inset)
                sc.frame_set(1)
                for o, M in kept: o.matrix_world = M
                obs = [o for o, _M in kept]
                for k in range(pending):
                    ob = bpy.data.objects.new(f"u{u['index']:03d}_{attempt}_{k}", T_["mesh"]); sc.collection.objects.link(ob)
                    ob.rotation_euler = euler_rand(flat)
                    # shovel into the spot that lies furthest under the target surface (of 16 random spots), away from
                    # the spots this stack already took
                    best = None
                    for _c in range(16):
                        px = cx + crng.uniform(-sx, sx); py = cy + crng.uniform(-sy, sy)
                        i = min(max(int((px - x0) / GRID), 0), deficit.shape[0] - 1); j = min(max(int((py - y0) / GRID), 0), deficit.shape[1] - 1)
                        sc_ = -float(deficit[i, j]) + BACKW * (y1 - py) / (y1 - y0) + crng.uniform(0, 0.03 + 0.02 * attempt)
                        sc_ += sum(0.3 for (qx, qy) in spots if (qx - px) ** 2 + (qy - py) ** 2 < 0.22 ** 2)
                        if best is None or sc_ < best[0]: best = (sc_, px, py)
                    _s, px, py = best; spots.append((px, py))
                    lt = max([local_top(px, py, R + 0.10)] + [float(np.array(M)[2, 3]) + R for (o, M) in kept
                              if (np.array(M)[0, 3] - px) ** 2 + (np.array(M)[1, 3] - py) ** 2 < (2 * R + 0.05) ** 2])
                    ob.location = (px, py, lt + 0.04 + R + gap * k * 0.6)
                    add_rb(ob, "ACTIVE", "CONVEX_HULL", mass=max(0.05, T_["vol"] * 700))
                    obs.append(ob)
                bpy.context.view_layer.update()
                sc.frame_set(1)
                prev = None; still = 0; f = 1; dp = dr = 0.0
                while f < 360:
                    f += 1; sc.frame_set(f)
                    cur = [(o.matrix_world.translation.copy(), o.matrix_world.to_quaternion()) for o in obs]
                    if prev:
                        dp = max((a[0] - b[0]).length for a, b in zip(cur, prev))
                        dr = max(a[1].rotation_difference(b[1]).angle for a, b in zip(cur, prev))
                        still = still + 1 if (dp < 2e-4 and dr < 4e-3 and f > 8) else 0
                        if still >= 3: break
                    prev = cur
                Ms = [o.matrix_world.copy() for o in obs]
                bads = [max(lean_over(world_verts(pf, M), col, row), 0.0 if inside(world_verts(pf, M), col, row) else 1.0,
                            1.0 if fbvh.overlap(BVHTree.FromPolygons([Vector(tuple(float(a) for a in w)) for w in world_verts(pf, M)], T_["tris"])) else 0.0)
                        for M in Ms]
                kept = []
                pending = 0
                for o, M, bd in zip(obs, Ms, bads):
                    if bd <= 0.0: kept.append((o, M))
                    else: bpy.data.objects.remove(o, do_unlink=True); pending += 1
                if pending == 0: break
                SIMLOG["retries"] += 1
            if pending: SIMLOG["dropped"] = SIMLOG.get("dropped", 0) + pending
            obs = [o for o, _M in kept]; Ms = [M for _o, M in kept]
            if pending:     # the last try removed copies: settle the kept ones once more without them, then check again
                sc.frame_set(1)
                for o, M in kept: o.matrix_world = M
                bpy.context.view_layer.update()
                for f in range(2, 120): sc.frame_set(f)
                Ms = [o.matrix_world.copy() for o in obs]
                okk = [lean_over(world_verts(pf, M), col, row) <= 0 and inside(world_verts(pf, M), col, row) for M in Ms]
                for o, ok in zip(obs, okk):
                    if not ok: bpy.data.objects.remove(o, do_unlink=True); SIMLOG["dropped"] += 1
                obs = [o for o, ok in zip(obs, okk) if ok]; Ms = [M for M, ok in zip(Ms, okk) if ok]
            SIMLOG["resid"].append((round(dp * 1000, 3), round(dr, 4)))
            if still < 3: SIMLOG["unsettled"] += 1
            SIMLOG["frames"].append(f)
            for o in obs: o.rigid_body.type = "PASSIVE"
            for o, M in zip(obs, Ms): o.matrix_world = M
            bpy.context.view_layer.update()
            sc.frame_set(1)
            for o, M in zip(obs, Ms):
                u["copies"].append({"item": u["item"], "M": M.copy(), "obj": o})
                Mn = np.array(M)
                HV = np.concatenate([HV, (T_["hv"] @ Mn[:3, :3].T + Mn[:3, 3]).astype(np.float32)])
            ncop += len(Ms)
        Hs, Tg = surface(HV, col, row)
        filled = float(np.clip(np.minimum(Hs, Tg) - FL, 0, None).sum()) * GRID * GRID
        top = float(HV[:, 2].max())
        # how much of the compartment is covered up to (within 6 cm of) its target surface
        cover = float(((Tg - Hs) < 0.06).mean())
        tmax = float(Tg.max())
        SIMLOG["cells"][f"{col}{row}"] = {"item": pf, "copies": ncop, "per_stack": [len(u["copies"]) for u in mine], "peak": round(top, 3),
                                          "target_peak": round(tmax, 3), "filled_frac": round(filled / vtarget, 3), "cover_6cm": round(cover, 3),
                                          "wall_tops": [round(wall_top(col, row, "y0"), 3), round(wall_top(col, row, "y1"), 3),
                                                        round(side_top(y0) + CAPH, 3), round(side_top(y1) + CAPH, 3)]}
        print("CELL", col, row, pf, json.dumps(SIMLOG["cells"][f"{col}{row}"]), "elapsed", round(time.time() - t0, 1), flush=True)
    SIMLOG["wall"] = time.time() - t0

# ---------- checks ----------
def copy_world_verts(cp):
    M = np.array(cp["M"])
    return TEMPL[cp["item"]]["V"] @ M[:3, :3].T + M[:3, 3]

def clip_check(units, frame_bvh):
    bad = []
    for u in units:
        for k, cp in enumerate(u["copies"]):
            W = copy_world_verts(cp)
            bt = BVHTree.FromPolygons([Vector(tuple(float(a) for a in w)) for w in W], TEMPL[cp["item"]]["tris"])
            if frame_bvh.overlap(bt): bad.append((u["index"], k, cp["item"])); print("clip", u["index"], k, cp["item"], "cell", (u["col"], u["row"]))
    return bad

def containment(units):
    escaped, leaning, worst = [], [], 0.0
    for u in units:
        for k, cp in enumerate(u["copies"]):
            W = copy_world_verts(cp)
            if not inside(W, u["col"], u["row"]): escaped.append((u["index"], k))
            over = lean_over(W, u["col"], u["row"])
            if over > 0: leaning.append((u["index"], k, round(over, 3)))
            worst = max(worst, over)
    return escaped, leaning, worst

def interpenetration(units):
    """Deepest vertex-in-hull penetration between any two copies (hull vertices of A inside the convex hull of B), per item."""
    cps = [cp for u in units for cp in u["copies"]]
    P = np.array([np.array(cp["M"])[:3, 3] for cp in cps]); R = np.array([TEMPL[cp["item"]]["radius"] for cp in cps])
    worst = 0.0; npairs = 0; over = []
    per_item = {pf: 0.0 for pf, *_ in ITEMS}
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
                per_item[cps[a]["item"]] = max(per_item[cps[a]["item"]], max(m, 0.0))
    return worst, npairs, over, per_item

# ---------- anchors export (Unity prefab space, round 4's schema) ----------
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
    """lowest z of the copy's rotated renderer bounds (the box the mod's floor lift tests), Blender space"""
    M = np.array(cp["M"]); T = TEMPL[cp["item"]]
    c = M[:3, :3] @ T["mid"] + M[:3, 3]
    return float(c[2] - np.abs(M[2, :3]) @ T["he"])

def build_anchors(units, frame_info, clip_bad, ncop, pen, per_item_checks):
    maxerr = 0
    out_units = []
    for u in units:
        lo = Vector((1e9,) * 3); hi = Vector((-1e9,) * 3)
        for cp in u["copies"]:
            W = copy_world_verts(cp)
            lo = Vector(tuple(min(lo[i], float(W[:, i].min())) for i in range(3))); hi = Vector(tuple(max(hi[i], float(W[:, i].max())) for i in range(3)))
        if not u["copies"]:       # a stack none of whose tries stayed inside (reported as EMPTY): an empty unit at the cell centre
            x0, x1, y0, y1 = cell_bounds(u["col"], u["row"]); FLr = ROWFLOOR[u["row"]]
            lo, hi = Vector((x0, y0, FLr)), Vector((x1, y1, FLr + 0.1)); print("EMPTY unit", u["index"])
        else:
            lo.z = min(lo.z, min(bounds_low(cp) for cp in u["copies"])) - 0.002
        c = (lo + hi) / 2
        cps = []
        for cp in u["copies"]:
            M = cp["M"]; R = M.to_3x3().normalized()
            eul, quat, err = rot_to_unity(R); maxerr = max(maxerr, err)
            T = TEMPL[cp["item"]]
            cps.append({"item": cp["item"], "offset": [round(a, 4) for a in b2u_vec(M.translation - c)], "euler": eul, "quat_xyzw": quat,
                        "scale": round(T["s"], 4), "fit_longest_m": round(T["s"] * max(T["size"]), 3),
                        "world_position": [round(a, 4) for a in b2u_vec(M.translation)]})
        out_units.append({"index": u["index"], "step": u["step"], "kind": "heap_step", "item": u["item"], "compartment": [u["col"], u["row"]],
                           "position": [round(a, 4) for a in b2u_vec(c)], "rotation": [0, 0, 0],
                           "box": [round(hi.x - lo.x, 4), round(hi.z - lo.z, 4), round(hi.y - lo.y, 4)], "layer": 0, "copies": cps})
    items = {}
    for pf, *_ in ITEMS:
        T = TEMPL[pf]
        items[pf] = {"bounds_size_unity": [round(T["size"][0], 4), round(T["size"][2], 4), round(T["size"][1], 4)],
                     "bounds_center_unity": [round(a, 4) for a in b2u_vec(T["center"])], "scale_used": round(T["s"], 4)}
    comps = []
    for (col, row), pf in LAYOUT.items():
        x0, x1, y0, y1 = cell_bounds(col, row)
        cell = SIMLOG["cells"][f"{col}{row}"]
        comps.append({"compartment": [col, row], "item": pf, "stacks": QUOTA[pf],
                      "x": [round(-x1, 4), round(-x0, 4)], "z": [round(-y1, 4), round(-y0, 4)], "floor_y": ROWFLOOR[row],
                      "copies": cell["copies"], "heap_peak_y": cell["peak"]})
    doc = {
        "bin": "OreBin round 5 (round 4's furniture, heaped to the wall tops when full, physically settled)", "slots": NUNITS, "units": len(out_units),
        "steps": 8, "stack_per_unit": 1,
        "frame": frame_info,
        "space": "Unity prefab space, origin = bin footprint centre on the ground. Blender z-up/-y front -> Unity y-up/+z front: ux=-bx, uy=bz, uz=-by. "
                 "OBJ export (forward NEGATIVE_Z, up Y) writes (bx, bz, -by); Unity's importer negates x, same mapping.",
        "unit_semantics": "SETTLED: every copy has an explicit final pose from a rigid-body simulation (convex-hull items, friction 0.75, restitution 0, damping 0.25/0.45, "
                          "dropped stack by stack in fill order, earlier stacks frozen). unit.position = centre of unit.box; each copy: place the "
                          "item's prefab so that its BOUNDS CENTRE sits at unit.position + copy.offset (= copy.world_position, prefab space), rotated by copy.euler "
                          "(Unity Quaternion.Euler, ZXY) or copy.quat_xyzw, uniform scale copy.scale relative to the item prefab's native size. "
                          "Item root = bounds centre - R * (scale * item.bounds_center_unity). unit.box = bounding box of the unit's copies, its bottom "
                          "lowered to the lowest corner of any copy's rotated bounds (so a never-below-the-floor lift leaves the settled heap alone).",
        "fill_order": "units are listed in fill order; show the first n (a partial stack: its first k copies). Later stacks lie on earlier ones, earlier stacks never move. "
                      "Each compartment holds one item type (compartments[]); unit.item is its type, copies keep it.",
        "compartments": comps, "items": items, "clip_check": {"clipping": len(clip_bad), "of_copies": ncop},
        "interpenetration_max_m": round(max(pen, 0.0), 5), "rotation_convert_max_err": maxerr,
        "checks_per_item": per_item_checks, "units_list": out_units}
    return doc, maxerr

# ---------- scene ----------
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene

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
    m = atlas_mat(png, os.path.basename(png))
    for o in new:
        o.data.materials.clear(); o.data.materials.append(m)
        o.location = (dx, dy, 0)
    return new

# the furniture: round 4's files, byte-identical
for fn in ("OreBin.obj", "orebin_atlas.png"):
    shutil.copyfile(os.path.join(R4, fn), os.path.join(OUTA, fn))
r4doc = json.load(open(os.path.join(R4, "orebin_anchors.json")))
frame = import_frame(os.path.join(OUTA, "OreBin.obj"), os.path.join(OUTA, "orebin_atlas.png"), 0, 0)[0]
bpy.context.view_layer.update()
FV = [frame.matrix_world @ v.co for v in frame.data.vertices]
FT = [(p.vertices[0], p.vertices[i], p.vertices[i + 1]) for p in frame.data.polygons for i in range(1, len(p.vertices) - 1)]
fbvh = BVHTree.FromPolygons(FV, FT, all_triangles=True)
print("FRAME (round 4 OBJ) tris", len(FT), "round 4 says", r4doc["frame"]["tris"])
frame.hide_render = True; frame.location = (0, 0, -100)

load_templates()
for pf, *_ in ITEMS:
    T_ = TEMPL[pf]
    print("ITEM", pf, "scale", T_["s"], "longest m", round(T_["s"] * max(T_["size"]), 3), "tris", len(T_["tris"]))
units = build_order()
simulate_all(units)
ncop = sum(len(u["copies"]) for u in units)
print("SIM wall", round(SIMLOG["wall"], 1), "s; frames per stack: mean", round(sum(SIMLOG["frames"]) / len(SIMLOG["frames"]), 1),
      "max", max(SIMLOG["frames"]), "; unsettled stacks", SIMLOG["unsettled"], "; re-dropped stacks", SIMLOG["retries"])
bad = clip_check(units, fbvh)
print("CLIPPING", len(bad), "of", ncop, "copies", bad)
esc, lean, lworst = containment(units)
print("CONTAIN escaped", len(esc), esc[:10], "; leaning above a visible wall top", len(lean), lean[:12], "worst", round(lworst, 3), "m")
pen, npairs, over, per_item = interpenetration(units)
print("INTERPENETRATION max", round(pen * 1000, 2), "mm over", npairs, "near pairs;", len(over), "pairs penetrate, median",
      round(float(np.median(over)) * 1000, 2) if over else 0, "mm")
print("INTERP per item (mm)", {k: round(v * 1000, 2) for k, v in per_item.items()})
print("residual per-frame move at freeze (mm, rad): worst", max(SIMLOG["resid"]), "; unsettled-flagged", SIMLOG["unsettled"])
checks = {}
for pf, *_ in ITEMS:
    us = [u for u in units if u["item"] == pf]
    n = sum(len(u["copies"]) for u in us)
    checks[pf] = {"copies": n, "copies_per_stack": [len(u["copies"]) for u in us], "clipping": sum(1 for b in bad if b[2] == pf),
                  "interpenetration_max_m": round(per_item[pf], 5),
                  "escaped": sum(1 for (i, k) in esc if units[i]["item"] == pf),
                  "leaning_above_wall": sum(1 for (i, k, o) in lean if units[i]["item"] == pf),
                  "longest_m": round(TEMPL[pf]["s"] * max(TEMPL[pf]["size"]), 3),
                  "tris_per_copy": len(TEMPL[pf]["tris"]), "tris_full": n * len(TEMPL[pf]["tris"])}
print("CHECKS", json.dumps(checks))
ftris = sum(c["tris_full"] for c in checks.values())
frame_info = dict(r4doc["frame"])
frame_info["source"] = "assets/orebin_r4 (OBJ and atlas copied byte-identical)"
doc, err = build_anchors(units, frame_info, bad, ncop, pen, checks)
doc["contents_tris_full"] = ftris
print("rotation convert err", err)
json.dump({"frames": SIMLOG["frames"], "cells": SIMLOG["cells"], "retries": SIMLOG["retries"]}, open(os.path.join(OUT, "simlog.json"), "w"), indent=1)
for u in units:
    for cp in u["copies"]: bpy.data.objects.remove(cp["obj"], do_unlink=True)
for o in [o for o in bpy.data.objects if o.name.startswith("col_")]: bpy.data.objects.remove(o, do_unlink=True)
bpy.ops.rigidbody.world_remove()
tmp = os.path.join(OUT, "orebin_anchors.json.tmp")
json.dump(doc, open(tmp, "w"), indent=1)
os.replace(tmp, os.path.join(OUTA, "orebin_anchors.json"))
print("OREBIN5 copies", ncop, "contents tris full", ftris, "+ frame", r4doc["frame"]["tris"], "=", ftris + r4doc["frame"]["tris"])
print("DROPPED copies (never placed)", SIMLOG.get("dropped", 0))
for k, c in SIMLOG["cells"].items(): print("HEAP", k, c["item"], "copies", c["copies"], "per stack", c["per_stack"], "peak", c["peak"],
                                          "target peak", c["target_peak"], "wall tops (front, back, side@front, side@back)", c["wall_tops"],
                                          "filled", c["filled_frac"], "cover", c["cover_6cm"])
if NORENDER:
    print("DONE"); sys.exit(0)

# ---------- render scene: replayed from the exported files the mod's way ----------
C = Matrix(((-1, 0, 0), (0, 0, 1), (0, -1, 0)))
def u2b_pos(p): return Vector((-p[0], -p[2], p[1]))
def u2b_rot(q): return C.transposed() @ Quaternion((q[3], q[0], q[1], q[2])).to_matrix() @ C

RAW = {}
def raw_mesh(pf):
    if pf not in RAW:
        ob = load_item(pf, anchor="center")[0]
        RAW[pf] = (ob.data, np.array([tuple(v.co) for v in ob.data.vertices], np.float32))
        bpy.data.objects.remove(ob, do_unlink=True)
    return RAW[pf]

LIFTS = {}
def spawn_file(folder, fill, dx, dy, tag):
    """a round replayed from its files: unit.position + copy.offset, the first n units, a partial last unit, the mod's floor lift"""
    import_frame(os.path.join(folder, "OreBin.obj"), os.path.join(folder, "orebin_atlas.png"), dx, dy)
    d = json.load(open(os.path.join(folder, "orebin_anchors.json")))
    ul = d["units_list"]
    exact = fill * len(ul); n = int(math.floor(exact + 1e-9)); part = exact - n
    lifts = 0
    for ui, u in enumerate(ul[:n + (1 if part > 1e-6 else 0)]):
        cps = u["copies"] if ui < n else u["copies"][:max(1, math.ceil(len(u["copies"]) * part))]
        floor = u["position"][1] - u["box"][1] / 2
        for cp in cps:
            mesh, V = raw_mesh(cp["item"])
            s = cp["scale"]
            Rb = u2b_rot(cp["quat_xyzw"])
            p = u2b_pos([a + b for a, b in zip(u["position"], cp["offset"])])
            # the mod's lift: the copy's transformed bounds never below unit.Pos.y - unit.Box.y / 2
            he = (V.max(0) - V.min(0)) / 2 * s; mid = (V.max(0) + V.min(0)) / 2 * s
            Rn = np.array(Rb)
            low = float((Rn @ mid)[2] + p.z - np.abs(Rn[2]) @ he)
            if low < floor - 1e-4: p.z += floor - low; lifts += 1
            ob = bpy.data.objects.new(f"{tag}_item", mesh); sc.collection.objects.link(ob)
            ob.matrix_world = Matrix.Translation(p + Vector((dx, dy, 0))) @ Rb.to_4x4() @ Matrix.Diagonal((s,) * 3 + (1,))
    LIFTS[f"{tag}@{fill}"] = lifts

pm = bpy.data.materials.new("plain"); pm.use_nodes = True
pm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.55, 0.52, 0.46, 1)
def post(x, y):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(x, y, 0.9)); p = bpy.context.active_object
    p.scale = (0.14, 0.14, 1.8); p.data.materials.append(pm); p.name = "post_1.8m"

ROWS = {"full": 0.0, "half": 12.0, "cmp": 24.0}
spawn_file(OUTA, 1.0, 0.0, ROWS["full"], "r5")
spawn_file(OUTA, 0.5, 0.0, ROWS["half"], "r5")
spawn_file(R4, 1.0, -2.15, ROWS["cmp"], "r4")
spawn_file(OUTA, 1.0, 2.15, ROWS["cmp"], "r5")
post(-2.5, ROWS["full"] - 1.4); post(-2.5, ROWS["half"] - 1.4); post(0.0, ROWS["cmp"] + 0.3)
print("MOD FLOOR LIFTS (copies moved by the mod's never-below-the-floor rule)", LIFTS)

world = bpy.data.worlds.new("w"); sc.world = world; world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.42, 0.45, 0.5, 1)
world.node_tree.nodes["Background"].inputs[1].default_value = 0.9
sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN")); sun.data.energy = 3.2
sun.rotation_euler = (math.radians(50), 0, math.radians(35)); sc.collection.objects.link(sun)
bpy.ops.mesh.primitive_plane_add(size=120, location=(0, 12, 0))
gm = bpy.data.materials.new("ground"); gm.use_nodes = True
gm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.16, 0.14, 0.11, 1)
bpy.context.active_object.data.materials.append(gm)
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam); sc.camera = cam
sc.render.engine = "BLENDER_EEVEE_NEXT"
sc.render.resolution_x, sc.render.resolution_y = (1000, 562) if QUICK else (1600, 900)
sc.view_settings.view_transform = "Standard"
EYE = 1.75     # a standing player's eye height
VIEWS = {  # name: (yaw deg, horizontal distance, eye height, target)
    "full34": (-35, 4.6, EYE, (0.0, ROWS["full"], 0.75)),
    "half34": (-35, 4.6, EYE, (0.0, ROWS["half"], 0.75)),
    "fullfront": (0, 4.4, EYE, (0.0, ROWS["full"], 0.75)),
    "halffront": (0, 4.4, EYE, (0.0, ROWS["half"], 0.75)),
    "r4r5": (-18, 7.4, 3.4, (0.0, ROWS["cmp"], 0.75)),
    "top": (-15, 4.2, 4.6, (0.0, ROWS["full"], 0.7)),
    "halftop": (-15, 4.2, 4.6, (0.0, ROWS["half"], 0.7)),
}
for vn, (yaw, dist, h, tgt) in VIEWS.items():
    if VIEWSEL and vn not in VIEWSEL: continue
    t = Vector(tgt)
    cam.location = t + Vector((math.sin(math.radians(yaw)) * dist, -math.cos(math.radians(yaw)) * dist, h - t.z))
    cam.rotation_euler = (t - cam.location).to_track_quat("-Z", "Y").to_euler(); cam.data.lens = 35 if vn != "r4r5" else 40
    sc.render.filepath = os.path.join(OUT, f"{TAG}-{vn}.png")
    bpy.ops.render.render(write_still=True)
    print("RENDER", vn, flush=True)
print("DONE")
