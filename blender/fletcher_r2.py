"""Fletcher's Barrels, round 2 (round 1 = fletcher_r1.py; this file is r1 with the changes listed in R2_CHANGES: no coplanar
overlapping faces in the frame (checked, report_coplanar), arrows and bolts as bundles per unit, a bomb crate that fills up).

Fletcher's Barrels, round 1: a ground store for ammunition. Arrows stand in tall stave barrels, one kind per barrel, the
bundle thickening with stock; bolts stand in two short tubs, bombs lie on straw in a two-half crate.
Run: blender -b -P fletcher_r2.py -- [--out DIR] [--rip DIR] [--quick] [--views a,b] [--no-render] [--frame-only]
Writes into assets/fletcher_r2/: Fletcher.obj (frame only, forward -Z, up Y, triangulated, no materials),
fletcher_atlas.png (128x128, point filtered) and fletcher_anchors.json (written last, temp + rename: the mod live-reloads).

ARROW SIZE (settled before building). The mod measures an item as ItemVisual does: every LOD0 mesh renderer in prefab root
space (root.worldToLocalMatrix * renderer.localToWorldMatrix, turned 180 degrees about up), times the root's own localScale.
From the game files (UnityPy, bundle c4210710): ArrowFlint's root scale is (1, 1, 1); its child 'model' has localScale 1.5
around a 1.144 m mesh (polySurface20), and the flint head 'Sphere' sits under it. So the arrow you pick up IS 1.84 m long:
the mod would log "Item model 'ArrowFlint': 2 mesh(es), size (0.176, 0.302, 1.839), root scale (1.000, 1.000, 1.000)".
(Player.log has no arrow line yet: no store has drawn an arrow.) Every arrow measures 1.63-1.84 m, every bolt 0.56-0.58 m
(table MODB below). The arrow you see in flight is a different prefab (bow_projectile_*: the same mesh at scale 1.2, 1.37 m),
which is why the item reads long. Chosen: arrows at fit_longest_m 0.86 m (0.47x flint, 0.53x charred: a real arrow's
length), bolts 0.32 m (0.55x), bombs 0.22 m (0.66x bile, 0.83x lava); one layout holds any kind of its family at one size.
Why not 0.7-1.0x: these models are fat (carapace and silver 0.24 m across at true size, fletchings 0.1-0.2 m). Packed
mesh against mesh for all 11 arrow models at once, a 0.38 m barrel holds 2-5 arrows at 0.70x (1.28 m); at 0.47x, with
four foot heights, it holds 16.

Frame 3.20 W x 1.30 D x 1.07 H (Blender x, y, z; -y = front). The tallest arrows stand to 1.50 m.
  base       five 0.14 x 0.10 skids, seven 0.045 deck planks along x (deck top 0.145), iron skid caps with rivets
  posts      four 0.14 corner posts (back 1.07, front 0.45), iron bands flush with the bounds
  back       top beam 0.12 x 0.10 at 0.95-1.07, mid rail at 0.48-0.58, a centre stud; riveted T-brackets
  sides      a side rail 0.10 x 0.12 at 0.33-0.45 and a hewn knee brace from the back post down to it; riveted plates
  front      a 0.10 x 0.10 sill beam on the deck (the tubs and the crate stand behind it)
  barrels    6 x (12 hewn staves 0.04 thick, 0.66 high, outer apothem 0.228, long edges bevelled; 2 iron hoops and a painted
             band; a plank tag with a painted mark on the front stave; packed with straw to 0.45 over the head, the straw
             cut away wherever any copy of any arrow model passes), pitch 0.485, centres y +0.30
  tubs       2 x (12 staves, 0.30 high, outer apothem 0.265; 2 hoops, a painted band, a tag; straw to 0.11), centres y -0.24
  crate      1.74 x 0.58 x 0.30 of 0.045 planks, a divider, riveted iron corners, hemp rope handles, a straw bed per half
Atlas 128x128 point: the Metal Pallet r3 atlas (hewn timber v 96-127, end grain + wear swatch v 64-95, iron v 0-31, its upper
plank board v 48-63) with v 32-47 repainted: straw (u 0-31), hemp (u 32-63), eight painted marks (u 64-127, 8 px each,
v 32-39; v 40-47 the same, more worn). Every chamfer and rivet maps to the worn swatch, as the pallet and bunker do.

Units: 64 = 6 barrels x 8 + 2 tubs x 4 + 2 crate halves x 4; group key "crate" 0-9 (one item kind per group, ByGroup).
Each unit is one stack; its copies are a few items added to the holder's bundle in fill order (core first), so a full
barrel is a full sheaf: 2 arrows per unit (16 per barrel), 6 bolts per unit (24 per tub), 2 bombs per unit (8 per half:
a layer of 6 on the straw, 2 on top). Arrows stand with their feet at 0, 0.14, 0.28 or 0.42 m in the straw (bolts 0 or
0.08), so neighbouring fletchings and heads sit at different heights. The layouts are packed against EVERY ripped model of
the family at once (arrows: 11, bolts: 5, bombs: 3), mesh against mesh (alpha-cut fletching only where it is opaque): no
copy touches another, the frame, or a neighbour holder's space.
Copies: align long axis -> up (arrows/bolts), thin axis -> x, then_rotate = lean x spin; fit_longest_m; anchor bottom;
offset.y = the foot height (plus the lift a lean needs).
Heads: align maps the item's +long axis to up, and the models differ in sign: flint, iron, fire, wood, bronze, obsidian,
silver stand head-up; poison, frost, charred and carapace stand fletching-up (see the 'heads' block in the anchors).

Unity prefab space: ux = -bx, uy = bz, uz = -by. Item models (ValheimRip/items, extraction convention, root space):
item_u = (-bx, bz, -by) (the mod's half turn included); copy matrix in Blender = B @ M_unity @ K (see place_u).
"""
import os, sys, math, json, random
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import bpy, bmesh
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
import metalrack_r1 as base
from metalrack_r1 import (box, join, tris, tri_list, export_obj, write_json_atomic, make_material, setup_scene, references,
                          lights_and_render, b2u, argv, arg, TW, TH)

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.normpath(os.path.join(HERE, "..", "assets"))
OUTA = os.path.join(ASSETS, "fletcher_r2")
SCR = "C:/Users/joost/AppData/Local/Temp/claude/C--Users-joost--pai/5e4bc60b-cdfe-4638-8e29-2e507fa13cf9/scratchpad/fletcher1"
SCR2 = "C:/Users/joost/AppData/Local/Temp/claude/C--Users-joost--pai/5e4bc60b-cdfe-4638-8e29-2e507fa13cf9/scratchpad/fletcher_r2"
OUT = arg("--out", SCR2)
RIP2 = arg("--rip", os.path.join(SCR, "rip"))        # ArrowWood/Bronze/Obsidian/Silver/Frost, BoltBone/Iron/Blackmetal, BombDynamite
ITEMS_DIR = base.ITEMS_DIR
import load_item as LI
DENS = 48.0
rng = random.Random(29)

# ---------- the game's own numbers (UnityPy, read-only on the game files; method in the docstring) ----------
# ItemVisual.Bounds per prefab in the mod's item space: (centre, size); every root scale is (1, 1, 1).
MODB = {
    "ArrowFlint": ([-0.0022, -0.0503, 0.055], [0.176, 0.3015, 1.8388]),
    "ArrowIron": ([0.0042, -0.0503, 0.0283], [0.1313, 0.2281, 1.7744]),
    "ArrowPoison": ([0.0016, 0.0, -0.0146], [0.1313, 0.2281, 1.7452]),
    "ArrowFire": ([0.0001, -0.0503, -0.0009], [0.1135, 0.2281, 1.7161]),
    "ArrowCharred": ([-0.0097, -0.004, 0.0036], [0.0887, 0.0932, 1.6346]),
    "ArrowCarapace": ([0.0002, 0.0002, 0.0206], [0.2441, 0.2323, 1.7815]),
    "ArrowWood": ([0.0001, -0.0503, -0.0009], [0.1135, 0.2281, 1.7161]),
    "ArrowBronze": ([0.0047, -0.0503, 0.0241], [0.1227, 0.2281, 1.766]),
    "ArrowObsidian": ([0.0045, -0.0503, 0.0244], [0.1313, 0.2281, 1.7666]),
    "ArrowSilver": ([0.0025, -0.0503, 0.0569], [0.2391, 0.2281, 1.8354]),
    "ArrowFrost": ([0.0016, 0.0, -0.0146], [0.1313, 0.2281, 1.7452]),
    "ArrowNeedle": ([0.0, 0.0062, -0.12], [0.1021, 0.0766, 1.822]),
    "BoltCarapace": ([-0.0, -0.0547, 0.016], [0.1292, 0.1292, 0.5797]),
    "BoltCharred": ([0.2675, -0.0539, 0.1105], [0.0526, 0.0407, 0.5786]),
    "BoltBone": ([0.0073, -0.0548, 0.0968], [0.1413, 0.1413, 0.5733]),
    "BoltIron": ([0.0054, -0.0567, -0.0], [0.1675, 0.1675, 0.5591]),
    "BoltBlackmetal": ([0.0081, -0.051, 0.0105], [0.1292, 0.1292, 0.5841]),
    "BombBile": ([-0.0016, 0.0261, -0.0043], [0.3069, 0.3339, 0.2994]),
    "BombLava": ([-0.001, 0.0697, -0.0278], [0.2356, 0.2503, 0.2647]),
    "BombDynamite": ([-0.0006, 0.0181, 0.0044], [0.1687, 0.2596, 0.1776]),
}
FAM = {"arrow": ["ArrowCarapace", "ArrowFlint", "ArrowSilver", "ArrowIron", "ArrowPoison", "ArrowFire", "ArrowCharred",
                 "ArrowWood", "ArrowBronze", "ArrowObsidian", "ArrowFrost"],
       "bolt": ["BoltIron", "BoltBone", "BoltCarapace", "BoltBlackmetal", "BoltCharred"],
       "bomb": ["BombBile", "BombLava", "BombDynamite"]}
HEADS = {"up (head at the top)": ["ArrowFlint", "ArrowIron", "ArrowFire", "ArrowWood", "ArrowBronze", "ArrowObsidian", "ArrowSilver"],
         "down (fletching at the top)": ["ArrowPoison", "ArrowFrost", "ArrowCharred", "ArrowCarapace"]}
LONG = {"arrow": 0.86, "bolt": 0.32, "bomb": 0.22}

# ---------- frame dimensions ----------
W, D = 3.20, 1.30
HX, HY = W / 2, D / 2
PS, INS = 0.14, 0.004
PX, PY = HX - INS - PS / 2, HY - INS - PS / 2        # 1.526, 0.576
IX, IY = PX - PS / 2, PY - PS / 2                    # 1.456, 0.506: inner faces of the posts
BO = HY - 0.004                                      # 0.646: outer face of the front sill / back beams
H_BACK, H_FRONT = 1.07, 0.45
SK_H, SK_W, DT = 0.10, 0.14, 0.045
DECK = SK_H + DT                                     # 0.145
SKX = [-1.25, -0.625, 0.0, 0.625, 1.25]
BEAM = 0.10
FE, RV = 0.008, 0.005

# barrels, tubs, crate (Blender)
NST = 12
BAR_R, BAR_T, BAR_H = 0.228, 0.04, 0.66              # outer apothem, stave thickness, stave height
BAR_PITCH, BAR_Y = 0.485, 0.30
BAR_X = [(i - 2.5) * BAR_PITCH for i in range(6)]
TUB_R, TUB_H, TUB_Y = 0.265, 0.30, -0.24
TUB_X = [-1.176, -0.626]
HEAD_Z0, HEAD_T = 0.03, 0.04                         # head above the deck (chime), thickness
FLOOR = DECK + HEAD_Z0 + HEAD_T                      # 0.215: top of the barrel and tub heads (under the straw)
LEVELS = {"arrow": (0.0, 0.07, 0.14, 0.21, 0.28, 0.35, 0.42), "bolt": (0.0, 0.03, 0.055, 0.08), "bomb": (0.0,)}   # foot heights over the head
STRAW_IN = {"arrow": 0.45, "bolt": 0.11}             # straw packing over the head: every foot stands in it
HOOP_T = 0.008
EMB = 0.0015                                          # r2: plates, tags, rivets sink this far into what they sit on (no shared plane)
KISS = 0.002                                          # r2: beams, boards and studs run this far into the post, deck or wall they meet
CR_X0, CR_X1, CR_Y0, CR_Y1 = -0.30, 1.44, -0.535, 0.045
CR_H, CR_T, CR_FT = 0.30, 0.045, 0.04                # wall height above the deck, wall planks, floor boards
CR_MID = (CR_X0 + CR_X1) / 2
STRAW_TOP = DECK + CR_FT + 0.034                     # straw peaks stay below this
# paint marks (atlas swatches): barrels 0-5, tubs 5 and 4, crate halves 6 and 7 (the sketch's kind colours)
PAINT_BAR, PAINT_TUB, PAINT_CRATE = [0, 1, 2, 3, 4, 5], [5, 4], [6, 7]

# ---------- atlas ----------
def srgb(c): return np.array(c, dtype=np.float32)
WOOD_L = srgb((0.47, 0.37, 0.25))
STRAW, STRAW_D = srgb((0.60, 0.50, 0.27)), srgb((0.33, 0.26, 0.12))
HEMP, HEMP_D = srgb((0.50, 0.44, 0.33)), srgb((0.26, 0.21, 0.15))
PAINTS = [(0.60, 0.57, 0.50), (0.33, 0.37, 0.42), (0.30, 0.38, 0.17), (0.60, 0.31, 0.13),
          (0.11, 0.10, 0.095), (0.20, 0.38, 0.38), (0.47, 0.47, 0.17), (0.55, 0.20, 0.10)]
PAINT_NAMES = ["bone white", "slate blue", "moss green", "rust orange", "char black", "verdigris", "bile yellow", "ember red"]

def build_atlas():
    src = bpy.data.images.load(os.path.join(ASSETS, "metalpallet_r3", "metalpallet_atlas.png"))
    px = np.array(src.pixels[:], np.float32).reshape(TH, TW, 4)
    img = px[..., :3].copy()
    nr = np.random.default_rng(31)
    x = np.arange(32)[None, :].repeat(16, 0).astype(np.float32)
    y = np.arange(16)[:, None].repeat(32, 1).astype(np.float32)
    # straw: stalks along u, dark gaps between them, a few bright ends
    t = 0.5 + 0.5 * np.sin(y * 2.6 + 0.9 * np.sin(x * 0.45 + y))
    t = t * 0.55 + nr.random((16, 32)) * 0.35
    t += (nr.random((16, 32)) < 0.06) * 0.4
    s = STRAW * (1 - np.clip(t, 0, 1)[..., None]) + STRAW_D * np.clip(t, 0, 1)[..., None]
    img[32:48, 0:32] = s
    # hemp: twisted strands (diagonal), darker between the strands
    t = 0.5 + 0.5 * np.sin((x + y * 1.4) * 1.1)
    t = np.clip(t * 0.7 + nr.random((16, 32)) * 0.25, 0, 1)
    img[32:48, 32:64] = HEMP * (1 - t[..., None]) + HEMP_D * t[..., None]
    # painted marks: muted, a darker rim, light worn specks (timber showing through), two wear levels
    for row, wear in ((0, 0.05), (1, 0.14)):
        for k, c in enumerate(PAINTS):
            c = np.array(c, np.float32)
            blk = c * (0.84 + 0.16 * nr.random((8, 8)))[..., None]
            blk[[0, 7], :] *= 0.78; blk[:, [0, 7]] *= 0.78
            worn = nr.random((8, 8)) < wear
            blk[worn] = blk[worn] * 0.45 + WOOD_L * 0.55
            img[32 + 8 * row:40 + 8 * row, 64 + 8 * k:72 + 8 * k] = blk
    im = bpy.data.images.new("fletcher_atlas", TW, TH, alpha=False)
    im.pixels.foreach_set(np.concatenate([np.clip(img, 0, 1), np.ones((TH, TW, 1), np.float32)], 2).ravel())
    return im

# ---------- UV (box faces are mapped before the box is turned) ----------
STRIPS = {"hewn": (96, 30), "plank": (48, 14), "iron": (0, 30)}
SWATCH_U = 96

def planar(f, u0, v0, wpx, hpx, dens=DENS):
    """Map a face into the atlas rectangle [u0, u0+wpx] x [v0, v0+hpx] (px), planar along its two widest axes."""
    n = f.normal
    ax = max(range(3), key=lambda i: abs(n[i]))
    tang = [i for i in range(3) if i != ax]
    cs = [l.vert.co for l in f.loops]
    spans = [max(v[i] for v in cs) - min(v[i] for v in cs) for i in tang]
    ua, va = (tang[0], tang[1]) if spans[0] >= spans[1] else (tang[1], tang[0])
    umin, vmin = min(v[ua] for v in cs), min(v[va] for v in cs)
    su = min(dens, wpx / max(max(v[ua] for v in cs) - umin, 1e-4))
    sv = min(dens, hpx / max(max(v[va] for v in cs) - vmin, 1e-4))
    for l in f.loops:
        l[base.UV].uv = ((u0 + (l.vert.co[ua] - umin) * su) / TW, (v0 + (l.vert.co[va] - vmin) * sv) / TH)

def my_uv(f, kind, long_axis, seed):
    n = f.normal
    r = random.Random(seed * 7919 + f.index)
    if kind.startswith("paint"):
        k = int(kind[5:]); planar(f, 64 + 8 * (k % 8) + 1, 32 + 8 * (k // 8) + 1, 6, 6, dens=60); return
    if kind == "straw": planar(f, 1 + r.randrange(4), 33, 26, 14); return
    if kind == "hemp": planar(f, 33 + r.randrange(4), 33, 26, 14); return
    if kind == "rivet" or max(abs(n[0]), abs(n[1]), abs(n[2])) < 0.98:
        u = (SWATCH_U + 1 + r.randrange(30) + 0.5) / TW
        v = ((65 if kind in ("iron", "rivet") else 81) + r.randrange(14) + 0.5) / TH
        for l in f.loops: l[base.UV].uv = (u, v)
        return
    ax = max(range(3), key=lambda i: abs(n[i]))
    tang = [i for i in range(3) if i != ax]
    cs = [l.vert.co for l in f.loops]
    if kind in ("hewn", "plank") and ax == long_axis:            # end grain: a whole ring tile (0-2)
        k = seed % 3
        c = sum(cs, Vector()) / len(cs)
        ext = max(max(abs(v[tang[0]] - c[tang[0]]), abs(v[tang[1]] - c[tang[1]])) for v in cs) or 1
        for l in f.loops:
            a = (l.vert.co[tang[0]] - c[tang[0]]) / ext; b = (l.vert.co[tang[1]] - c[tang[1]]) / ext
            l[base.UV].uv = ((32 * k + 16 + a * 14) / TW, (64 + 16 + b * 14) / TH)
        return
    spans = [max(v[i] for v in cs) - min(v[i] for v in cs) for i in tang]
    ua = long_axis if long_axis in tang else (tang[0] if spans[0] >= spans[1] else tang[1])
    va = tang[1] if ua == tang[0] else tang[0]
    v0, usable = STRIPS[kind]
    off = (seed * 0.37) % 1
    vmin = min(v[va] for v in cs); span = max(max(v[va] for v in cs) - vmin, 1e-4)
    vscale = min(1.0, (usable / DENS) / span)
    used = span * vscale * DENS
    shift = ((seed * 13) % 100) / 100 * max(0.0, usable - used) if kind != "iron" else 0.0
    for l in f.loops:
        l[base.UV].uv = (l.vert.co[ua] * DENS / TW + off, (v0 + 1 + shift + (l.vert.co[va] - vmin) * vscale * DENS) / TH)

def mesh_part(name, bm):
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = False
    ob = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(ob)
    ob.data.materials.append(base.MAT); base.PARTS.append(ob)
    return ob

def ring(name, cx, cy, n, apo, thick, z0, z1, kind):
    """A hoop of n flat segments centred at angles 2 pi k / n (the staves), inner apothem apo: outer face, top and bottom
    (the inner face lies on the staves and is left out). Iron: u runs round the hoop; paint: a painted swatch."""
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.verify()
    rc_i, rc_o = apo / math.cos(math.pi / n), (apo + thick) / math.cos(math.pi / n)
    corners = [2 * math.pi * k / n - math.pi / n for k in range(n)]
    def V(r, a, z): return bm.verts.new((cx + r * math.cos(a), cy + r * math.sin(a), z))
    ib = [V(rc_i, a, z0) for a in corners]; it = [V(rc_i, a, z1) for a in corners]
    ob = [V(rc_o, a, z0) for a in corners]; ot = [V(rc_o, a, z1) for a in corners]
    seg = 2 * (apo + thick) * math.tan(math.pi / n)
    pk = int(kind[5:]) if kind.startswith("paint") else None
    for k in range(n):
        j = (k + 1) % n
        for fv, part in (((ob[k], ob[j], ot[j], ot[k]), "out"), ((ot[k], ot[j], it[j], it[k]), "top"), ((ib[k], ib[j], ob[j], ob[k]), "bot")):
            f = bm.faces.new(fv)
            if pk is not None:
                cu, cv = 64 + 8 * (pk % 8) + 1 + rng.random() * 3, 32 + 8 * (pk // 8) + 1 + rng.random() * 3
                uvs = [(cu, cv), (cu + 3, cv), (cu + 3, cv + 3), (cu, cv + 3)]
            elif part == "out":
                u0 = k * seg * DENS + 7
                h = (z1 - z0) * DENS
                uvs = [(u0, 2), (u0 + seg * DENS, 2), (u0 + seg * DENS, 2 + h), (u0, 2 + h)]
            else:
                u = SWATCH_U + 1 + rng.randrange(28); v = 65 + rng.randrange(12)
                uvs = [(u, v), (u + 1, v), (u + 1, v + 1), (u, v + 1)]
            for l, (u, v) in zip(f.loops, uvs): l[uvl].uv = (u / TW, v / TH)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    return mesh_part(name, bm)

def prism(name, cx, cy, n, apo, z0, z1, kind="plank"):
    """A closed n-gon prism (barrel head), side faces centred at the stave angles."""
    bm = bmesh.new()
    rc = apo / math.cos(math.pi / n)
    corners = [2 * math.pi * k / n - math.pi / n for k in range(n)]
    lo = [bm.verts.new((cx + rc * math.cos(a), cy + rc * math.sin(a), z0)) for a in corners]
    hi = [bm.verts.new((cx + rc * math.cos(a), cy + rc * math.sin(a), z1)) for a in corners]
    bm.faces.new(hi); bm.faces.new(list(reversed(lo)))
    for k in range(n):
        j = (k + 1) % n
        bm.faces.new((lo[k], lo[j], hi[j], hi[k]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    bm.normal_update()
    base.UV = bm.loops.layers.uv.verify()
    seed = rng.randrange(1000)
    for f in bm.faces: my_uv(f, kind, 0, seed)
    return mesh_part(name, bm)

def rivet(x, y, z, axis, s=0.024):
    size = {"x": (RV, s, s), "y": (s, RV, s), "z": (s, s, RV)}[axis]
    box("rivet", size, (x, y, z), kind="rivet", jitter=0, bevel=0)

def rivet_at_angle(cx, cy, r, a, z, s=0.022):
    """A rivet head on a hoop or stave face at angle a (radians) and outer radius r."""
    box("rivet", (s, RV, s), (cx + (r + RV / 2 - 0.001) * math.cos(a), cy + (r + RV / 2 - 0.001) * math.sin(a), z), kind="rivet", jitter=0, bevel=0,
        rot=(0, 0, math.degrees(a) - 90))

def plate_y(x0, x1, z0, z1, yface, sgn, rivets=()):
    box("plate", (x1 - x0, FE, z1 - z0), ((x0 + x1) / 2, yface + sgn * (FE / 2 - EMB), (z0 + z1) / 2), kind="iron", jitter=0, bevel=0)
    for rx, rz in rivets: rivet(rx, yface + sgn * (FE - EMB + RV / 2 - 0.001), rz, "y")

def plate_x(y0, y1, z0, z1, xface, sgn, rivets=()):
    box("plate", (FE, y1 - y0, z1 - z0), (xface + sgn * (FE / 2 - EMB), (y0 + y1) / 2, (z0 + z1) / 2), kind="iron", jitter=0, bevel=0)
    for ry, rz in rivets: rivet(xface + sgn * (FE - EMB + RV / 2 - 0.001), ry, rz, "x")

# ---------- the frame ----------
def stave(size, pos, rot_z, bevel=0.007):
    """A hewn stave: a box with only its four long (upright) edges bevelled (28 triangles instead of a fully bevelled 44)."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * size[0] + rng.uniform(-0.002, 0.002), v.co.y * size[1] + rng.uniform(-0.002, 0.002), v.co.z * size[2]))
    long_edges = [e for e in bm.edges if abs(e.verts[0].co.z - e.verts[1].co.z) > 1e-6]
    bmesh.ops.bevel(bm, geom=long_edges, offset=bevel, segments=1, affect="EDGES")
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    bm.normal_update()
    base.UV = bm.loops.layers.uv.verify()
    seed = rng.randrange(1000)
    for f in bm.faces: my_uv(f, "hewn", 2, seed)
    bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.radians(rot_z), 3, "Z"))
    bmesh.ops.translate(bm, verts=bm.verts, vec=Vector(pos))
    return mesh_part("stave", bm)

def stave_ring(cx, cy, apo_out, h, n=NST):
    rm = apo_out - BAR_T / 2
    w = 2 * rm * math.tan(math.pi / n) - 0.003
    for k in range(n):
        a = 2 * math.pi * k / n
        # r2: neighbouring staves overlap at their inner corners, so their tops (and bottoms) lay in one plane: every other stave
        # stands 4 mm lower, and all are sunk into the deck (the bottoms are hidden there)
        dz = -0.001 - (0.004 if k % 2 else 0.0)
        stave((w, BAR_T, h + 0.002), (cx + rm * math.cos(a), cy + rm * math.sin(a), DECK + h / 2 + dz), math.degrees(a) - 90)

def holder(cx, cy, apo_out, h, hoops, band, paint, tag_z, tag_h=0.10):
    """A stave barrel or tub standing on the deck: staves, iron hoops with two front rivets each, a painted band, a plank tag
    with a painted mark on the front stave (angle -90 degrees). Its head lies under the straw packing (straw_disc)."""
    stave_ring(cx, cy, apo_out, h)
    for z0, z1 in hoops:
        ring("hoop", cx, cy, NST, apo_out + 0.001, HOOP_T, DECK + z0, DECK + z1, "iron")
        for a in (-120, -60):
            rivet_at_angle(cx, cy, apo_out + 0.001 + HOOP_T, math.radians(a), DECK + (z0 + z1) / 2)
    ring("band", cx, cy, NST, apo_out + 0.001, 0.006, DECK + band[0], DECK + band[1], f"paint{paint}")
    ty = cy - apo_out - 0.0125 + EMB
    box("tag", (0.13, 0.025, tag_h), (cx, ty, DECK + tag_z), kind="plank", jitter=0.001, bevel=0.005)
    box("mark", (0.08, 0.004, tag_h * 0.6), (cx, ty - 0.0125 - 0.001, DECK + tag_z), kind=f"paint{paint + 8}", jitter=0, bevel=0)
    for dx in (-0.048, 0.048):
        rivet(cx + dx, ty - 0.0125 - RV / 2 + 0.001, DECK + tag_z + tag_h * 0.32, "y", s=0.016)

def build_frame():
    # ---- base: skids front to back, deck planks along x, iron caps on the skid ends ----
    for x in SKX:
        box("skid", (SK_W, 2 * BO, SK_H + KISS), (x, 0, (SK_H + KISS) / 2), jitter=0.003, bevel=0.014)
        for sg in (-1, 1):
            plate_y(x - 0.05, x + 0.05, 0.012, SK_H - 0.012, sg * BO, sg, rivets=[(x, SK_H / 2)])
    nb, gap = 7, 0.007
    bw = (2 * BO - (nb - 1) * gap) / nb
    for i in range(nb):
        box("deck", (2 * IX + 2 * KISS, bw, DT), (0, -BO + bw / 2 + i * (bw + gap), SK_H + DT / 2), kind="plank", jitter=0.0, bevel=0.008)
    # ---- corner posts (back tall, front low) with iron bands flush with the bounds ----
    for sx in (-1, 1):
        for sy, h, bands in ((1, H_BACK, [(0.02, 0.08), (0.49, 0.08), (H_BACK - 0.10 - 0.004, 0.10)]), (-1, H_FRONT, [(0.02, 0.08), (H_FRONT - 0.10 - 0.004, 0.10)])):
            box("post", (PS, PS, h), (sx * PX, sy * PY, h / 2), jitter=0.002, bevel=0.012)
            for z0, bh in bands:
                box("band", (PS + 2 * INS, PS + 2 * INS, bh), (sx * PX, sy * PY, z0 + bh / 2), kind="iron", jitter=0, bevel=0)
    # ---- back: top beam, mid rail, centre stud; riveted T-brackets on the back faces at the posts ----
    yb = BO - BEAM / 2
    box("topbeam", (2 * IX + 2 * KISS, BEAM, 0.12), (0, yb, H_BACK - 0.06), jitter=0.003, bevel=0.014)
    box("midrail", (2 * IX + 2 * KISS, BEAM, 0.10), (0, yb, 0.53), jitter=0.003, bevel=0.012)
    box("stud", (0.10, BEAM, 0.48 - DECK + 2 * KISS), (0, yb, (DECK + 0.48) / 2), jitter=0.002, bevel=0.012)
    box("stud", (0.10, BEAM, 0.95 - 0.58 + 2 * KISS), (0, yb, (0.58 + 0.95) / 2), jitter=0.002, bevel=0.012)
    for sx in (-1, 1):
        xa, xb = sorted((sx * (IX - 0.008), sx * (IX - 0.17)))     # r2: the plate stops short of the post band (no shared plane at its top and bottom edge)
        xm = (xa + xb) / 2
        for z0, z1 in ((0.962, 1.058), (0.488, 0.572)):
            plate_y(xa, xb, z0, z1, BO, 1, rivets=[(xm + dx, (z0 + z1) / 2) for dx in (-0.045, 0.045)])
    plate_y(-0.11, 0.11, 0.962, 1.058, BO, 1, rivets=[(dx, 1.01) for dx in (-0.075, 0.075)])
    plate_y(-0.11, 0.11, 0.488, 0.572, BO, 1, rivets=[(dx, 0.53) for dx in (-0.075, 0.075)])
    # ---- front: a sill beam on the deck, an iron band along it ----
    box("sill", (2 * IX + 2 * KISS, BEAM, BEAM), (0, -yb, DECK + BEAM / 2), jitter=0.003, bevel=0.012)
    # r2: the iron band runs between the plates, not under them (it lay in the plates' plane): a centre piece and two end pieces
    box("sillband", (1.088, FE, 0.04), (0, -BO - (FE / 2 - EMB), DECK + BEAM / 2), kind="iron", jitter=0, bevel=0.002)
    st = (base.rng.getstate(), rng.getstate())          # the extra boxes must not move the random stream of everything after them
    for sgn in (-1, 1):
        box("sillband", (0.62, FE, 0.04), (sgn * 0.966, -BO - (FE / 2 - EMB), DECK + BEAM / 2), kind="iron", jitter=0, bevel=0.002)
    base.rng.setstate(st[0]); rng.setstate(st[1])
    for x in (-IX + 0.12, -0.6, 0.6, IX - 0.12):
        plate_y(x - 0.05, x + 0.05, DECK + 0.012, DECK + BEAM - 0.012, -BO, -1, rivets=[(x, DECK + BEAM / 2)])
    # ---- sides: a rail between the posts, a knee brace from the back post down onto it, riveted plates ----
    SXI, SXO = IX + 0.020, HX - 0.024                       # rail x 1.476 .. 1.576
    for sx in (-1, 1):
        xc = sx * (SXI + SXO) / 2
        box("siderail", (SXO - SXI, 2 * IY + 2 * KISS, 0.12), (xc, 0, 0.39), jitter=0.003, bevel=0.012)
        a, b = (IY, 0.93), (-0.10, 0.45)                    # (y, z): from the back post to the rail top
        L = math.hypot(a[0] - b[0], a[1] - b[1]); ang = math.degrees(math.atan2(a[1] - b[1], a[0] - b[0]))
        box("brace", (SXO - SXI - 0.01, L + 0.05, 0.10), (xc, (a[0] + b[0]) / 2, (a[1] + b[1]) / 2), rot=(ang, 0, 0), jitter=0.002, bevel=0.012)
        xo = sx * SXO
        for (y0, y1, z0, z1) in ((IY - 0.17, IY, 0.342, 0.438), (-IY, -IY + 0.17, 0.342, 0.438), (-0.20, 0.0, 0.342, 0.438)):
            plate_x(y0, y1, z0, z1, xo, sx, rivets=[((y0 + y1) / 2 + dy, 0.39) for dy in (-0.05, 0.05)])
        plate_x(IY - 0.16, IY, 0.86, 0.98, xo, sx, rivets=[(IY - 0.08, 0.92)])
    # ---- six arrow barrels, two bolt tubs ----
    for x, p in zip(BAR_X, PAINT_BAR):
        holder(x, BAR_Y, BAR_R, BAR_H, hoops=[(0.04, 0.10), (0.585, 0.645)], band=(0.50, 0.55), paint=p, tag_z=0.25)
    for x, p in zip(TUB_X, PAINT_TUB):
        holder(x, TUB_Y, TUB_R, TUB_H, hoops=[(0.03, 0.08), (0.235, 0.285)], band=(0.18, 0.215), paint=p, tag_z=0.13, tag_h=0.07)
    # ---- the bomb crate: plank walls, a divider, floor boards, riveted iron corners, hemp handles, straw beds ----
    x0, x1, y0, y1 = CR_X0, CR_X1, CR_Y0, CR_Y1
    bh = (CR_H - 0.005) / 2
    for k in range(2):
        z = DECK + 0.0025 + bh * (k + 0.5)
        for yy in (y0 + CR_T / 2, y1 - CR_T / 2):
            box("cwall", (x1 - x0, CR_T, bh - 0.004), ((x0 + x1) / 2, yy, z), kind="plank", jitter=0.001, bevel=0.006)
        for xx in (x0 + CR_T / 2, x1 - CR_T / 2):
            box("cend", (CR_T, y1 - y0 - 2 * CR_T + 2 * KISS, bh - 0.004), (xx, (y0 + y1) / 2, z), kind="plank", jitter=0.001, bevel=0.006)
    box("divider", (CR_T, y1 - y0 - 2 * CR_T + 3 * KISS, CR_H - 0.06 + KISS), (CR_MID, (y0 + y1) / 2, DECK + (CR_H - 0.06) / 2 - KISS / 2), kind="plank", jitter=0.001, bevel=0.006)
    nf = 4
    fw = (y1 - y0 - 2 * CR_T) / nf
    for i in range(nf):
        e0, e1 = (KISS if i == 0 else 0.0), (KISS if i == nf - 1 else 0.0)       # r2: the outer boards run into the walls, all sink into the deck
        box("cfloor", (x1 - x0 - 2 * CR_T + 2 * KISS, fw - 0.004 + e0 + e1, CR_FT + KISS), ((x0 + x1) / 2, y0 + CR_T + fw * (i + 0.5) + (e1 - e0) / 2, DECK + CR_FT / 2 - KISS / 2), kind="plank", jitter=0, bevel=0.004)
    for xx, sxx in ((x0, -1), (x1, 1)):
        for yy, syy in ((y0, -1), (y1, 1)):
            if syy < 0:   # front corners: an L of two plates, rivets on the front
                plate_y(min(xx, xx - sxx * 0.11), max(xx, xx - sxx * 0.11), DECK + 0.02, DECK + CR_H - 0.02, yy, -1,
                        rivets=[(xx - sxx * 0.06, DECK + z) for z in (0.07, 0.23)])
            plate_x(min(yy, yy - syy * 0.11), max(yy, yy - syy * 0.11), DECK + 0.023, DECK + CR_H - 0.023, xx, sxx,
                    rivets=[(yy - syy * 0.06, DECK + z) for z in (0.07, 0.23)])
    for xx, sxx in ((x0, -1), (x1, 1)):           # hemp rope handles on the short ends
        if sxx < 0: continue                     # the left end stands against the tub: only the right end has a handle
        for yy in (-0.09, 0.09):
            box("rope", (0.05, 0.022, 0.022), (xx + 0.025 - KISS, (y0 + y1) / 2 + yy, DECK + 0.22), kind="hemp", jitter=0, bevel=0.003)
        box("rope", (0.022, 0.20, 0.022), (xx + 0.055, (y0 + y1) / 2, DECK + 0.22), kind="hemp", jitter=0, bevel=0.003)
    for k, (hx0, hx1) in enumerate(((x0 + CR_T, CR_MID - CR_T / 2), (CR_MID + CR_T / 2, x1 - CR_T))):
        xm = (hx0 + hx1) / 2
        box("cmark", (0.07, 0.004, 0.05), (xm, y0 - 0.001, DECK + 0.23), kind=f"paint{PAINT_CRATE[k] + 8}", jitter=0, bevel=0)
        straw_bed(hx0 + 0.003, hx1 - 0.003, y0 + CR_T + 0.003, y1 - CR_T - 0.003, DECK + CR_FT, STRAW_TOP)

def straw_disc(cx, cy, apo, z, copies_bvh, rings=(0.035, 0.07, 0.105, 0.14, 0.17), sectors=32):
    """The straw packing in a barrel or tub, seen from above: a polar grid out to the staves (the inner 12-gon) at height
    z, tufted +-8 mm, with every triangle that any copy of any model of the family would touch left out (the straw parts
    round the shafts), so nothing clips it."""
    pr = random.Random(int(cx * 1000) + 7)
    rad = list(rings)
    def edge_r(a):                                    # the inner 12-gon at angle a (side centres at 2 pi k / NST)
        da = (a + math.pi / NST) % (2 * math.pi / NST) - math.pi / NST
        return (apo - 0.002) / math.cos(da)
    P = [(cx, cy, z + 0.006)]
    for i, r in enumerate(rad + [None]):
        for k in range(sectors):
            a = 2 * math.pi * (k + 0.5 * (i % 2)) / sectors
            rr = edge_r(a) if r is None else r
            P.append((cx + rr * math.cos(a), cy + rr * math.sin(a), z + (0.0 if r is None else pr.uniform(-0.008, 0.008))))
    T = []
    for k in range(sectors): T.append((0, 1 + k, 1 + (k + 1) % sectors))
    for i in range(len(rad)):
        a0, b0 = 1 + i * sectors, 1 + (i + 1) * sectors
        for k in range(sectors):
            k1 = (k + 1) % sectors
            T.append((a0 + k, b0 + k, a0 + k1)); T.append((a0 + k1, b0 + k, b0 + k1))
    tree = BVHTree.FromPolygons(P, T, all_triangles=True)
    hit = set()
    for b in copies_bvh:
        for i, _ in tree.overlap(b): hit.add(i)
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.verify()
    vs = [bm.verts.new(p) for p in P]
    for ti, t in enumerate(T):
        if ti in hit: continue
        f = bm.faces.new([vs[i] for i in t])
        f.normal_update()
        if f.normal.z < 0: f.normal_flip()
        u0, v0 = 1 + pr.randrange(22), 33 + pr.randrange(8)
        for l, (du, dv) in zip(f.loops, ((0, 0), (4, 0), (2, 5))): l[uvl].uv = ((u0 + du) / TW, (v0 + dv) / TH)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    return mesh_part("straw", bm), len(hit)

def straw_bed(x0, x1, y0, y1, z0, ztop, nx=9, ny=6):
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.verify()
    G = [[bm.verts.new((x0 + (x1 - x0) * i / (nx - 1), y0 + (y1 - y0) * j / (ny - 1),
                        z0 + (0.006 if i in (0, nx - 1) or j in (0, ny - 1) else rng.uniform(0.012, ztop - z0 - 0.002))))
          for j in range(ny)] for i in range(nx)]
    for i in range(nx - 1):
        for j in range(ny - 1):
            f = bm.faces.new((G[i][j], G[i + 1][j], G[i + 1][j + 1], G[i][j + 1]))
            u0, v0 = 1 + rng.randrange(20), 33 + rng.randrange(6)
            for l, (du, dv) in zip(f.loops, ((0, 0), (6, 0), (6, 7), (0, 7))): l[uvl].uv = ((u0 + du) / TW, (v0 + dv) / TH)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    return mesh_part("straw", bm)

# ---------- items: the mod's placement (StoreModel.Place: Align.Axes or none, Fit.Longest, anchor bottom) ----------
K3 = np.array([[-1, 0, 0], [0, 0, 1], [0, -1, 0]], float)     # Blender item (root space) -> Unity item space (half turn)
B3 = np.array([[-1, 0, 0], [0, 0, -1], [0, 1, 0]], float)     # Unity prefab space -> Blender
def to4(R): M = np.eye(4); M[:3, :3] = R; return M
K4, B4 = to4(K3), to4(B3)
TPL = {}

def load_tpl(name):
    d = ITEMS_DIR if os.path.isdir(os.path.join(ITEMS_DIR, name)) else RIP2
    LI.ROOT = d
    obs = LI.load_item(name, anchor="origin")
    LI.ROOT = ITEMS_DIR
    ob = obs[0]
    for o in obs[1:]: bpy.data.objects.remove(o, do_unlink=True)
    me = ob.data; me.transform(ob.matrix_world); me.use_fake_user = True
    bpy.data.objects.remove(ob, do_unlink=True)
    Vb, T, frac = visible_mesh(os.path.join(d, name))
    c, s = MODB[name]
    TPL[name] = {"mesh": me, "Vi": Vb @ K3.T, "T": T, "c": np.array(c), "s": np.array(s), "dir": d, "opaque": frac}

def visible_mesh(d, n=8):
    """The model as the game shows it, for the clip checks: triangles of opaque materials as they are; triangles of
    alpha-cut materials (the fletchings: 'arrow' is 82 % holes, carapace 39 %, charred 18 %) cut into n x n pieces, kept
    where the texture (sampled at the piece's centre, the opaque mask grown by one texel) is above the material's cutoff."""
    info = json.load(open(os.path.join(d, "info.json")))
    V, VT, F, mat = [], [], [], None
    for l in open(os.path.join(d, "model.obj")):
        p = l.split()
        if not p: continue
        if p[0] == "v": V.append([float(a) for a in p[1:4]])
        elif p[0] == "vt": VT.append([float(a) for a in p[1:3]])
        elif p[0] == "usemtl": mat = p[1]
        elif p[0] == "f":
            q = [x.split("/") for x in p[1:]]
            for i in range(1, len(q) - 1):
                F.append(([int(q[0][0]) - 1, int(q[i][0]) - 1, int(q[i + 1][0]) - 1],
                          [int(q[0][1]) - 1, int(q[i][1]) - 1, int(q[i + 1][1]) - 1] if len(q[0]) > 1 and q[0][1] else None, mat))
    V, VT = np.array(V, float), np.array(VT, float) if VT else None
    masks = {}
    for m, mi in info["materials"].items():
        if mi.get("alpha_mode") == "clip" and mi.get("texture"):
            im = bpy.data.images.load(os.path.join(d, mi["texture"]["file"]), check_existing=True)
            w, h = im.size
            a = np.array(im.pixels[:], np.float32).reshape(h, w, 4)[..., 3] > (mi.get("cutoff") or 0.5)
            g = a.copy()
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1): g |= np.roll(np.roll(a, dy, 0), dx, 1)
            masks[m] = g
    outV, outT, kept, total = [], [], 0, 0
    for vi, ti, m in F:
        P = V[vi]
        if m not in masks or ti is None:
            b = len(outV); outV.extend(P.tolist()); outT.append((b, b + 1, b + 2)); continue
        UVt = VT[ti]; mk = masks[m]; h, w = mk.shape
        subs = []
        for i in range(n):
            for j in range(n - i):
                for tri in (((i, j), (i + 1, j), (i, j + 1)), ((i + 1, j), (i + 1, j + 1), (i, j + 1))):
                    if tri[1][0] + tri[1][1] > n or tri[2][0] + tri[2][1] > n: continue
                    total += 1
                    bc = [(1 - a / n - b / n, a / n, b / n) for a, b in tri]
                    cen = np.mean(bc, 0)
                    uv = cen @ UVt
                    if not mk[int(math.floor(uv[1] * h)) % h, int(math.floor(uv[0] * w)) % w]: continue
                    kept += 1
                    subs.append(bc)
        if len(subs) == n * n:                         # wholly visible: the triangle itself
            b = len(outV); outV.extend(P.tolist()); outT.append((b, b + 1, b + 2)); continue
        for bc in subs:
            b = len(outV)
            outV.extend([(np.array(c) @ P).tolist() for c in bc]); outT.append((b, b + 1, b + 2))
    return np.array(outV, float), outT, (kept / total if total else 1.0)

def look_rotation(f, up):
    f = np.array(f, float); f /= np.linalg.norm(f)
    r = np.cross(up, f); r /= np.linalg.norm(r)
    return np.column_stack([r, np.cross(f, r), f])

def q2m(q):
    x, y, z, w = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])

def m2q(R):
    t = np.trace(R)
    if t > 0:
        s = math.sqrt(t + 1) * 2; w = 0.25 * s; x = (R[2, 1] - R[1, 2]) / s; y = (R[0, 2] - R[2, 0]) / s; z = (R[1, 0] - R[0, 1]) / s
    elif R[0, 0] > R[1, 1] and R[0, 0] > R[2, 2]:
        s = math.sqrt(1 + R[0, 0] - R[1, 1] - R[2, 2]) * 2; w = (R[2, 1] - R[1, 2]) / s; x = 0.25 * s; y = (R[0, 1] + R[1, 0]) / s; z = (R[0, 2] + R[2, 0]) / s
    elif R[1, 1] > R[2, 2]:
        s = math.sqrt(1 + R[1, 1] - R[0, 0] - R[2, 2]) * 2; w = (R[0, 2] - R[2, 0]) / s; x = (R[0, 1] + R[1, 0]) / s; y = 0.25 * s; z = (R[1, 2] + R[2, 1]) / s
    else:
        s = math.sqrt(1 + R[2, 2] - R[0, 0] - R[1, 1]) * 2; w = (R[1, 0] - R[0, 1]) / s; x = (R[0, 2] + R[2, 0]) / s; y = (R[1, 2] + R[2, 1]) / s; z = 0.25 * s
    q = np.array([x, y, z, w]); return q / np.linalg.norm(q)

def Ry(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])

def Rlean(psi, theta):
    """Tilt the up axis by theta toward the horizontal Unity direction (cos psi, 0, sin psi) (Rodrigues)."""
    a = np.array([math.sin(psi), 0.0, -math.cos(psi)])
    Kx = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + math.sin(theta) * Kx + (1 - math.cos(theta)) * (Kx @ Kx)

E3 = np.eye(3)
def place_u(unit_pos, c, name):
    """Unity 4x4 of one copy, exactly as StoreModel.Place (unit rotation identity)."""
    t = TPL[name]; size, center = t["s"], t["c"]
    if "align" in c:
        il, it = int(np.argmax(size)), int(np.argmin(size))
        if it == il: it = (il + 1) % 3
        L = np.array(c["align"]["long_axis_to"], float); L /= np.linalg.norm(L)
        T = np.array(c["align"]["thin_axis_to"], float); T = T - L * T.dot(L); T /= np.linalg.norm(T)
        align = look_rotation(T, L) @ look_rotation(E3[it], E3[il]).T
        r = q2m(c["align"]["then_rotate_quat_xyzw"]) @ align
    else:
        align = np.eye(3); r = q2m(c["rot_quat_xyzw"])
    d = np.abs(align) @ size
    s = c["longest_m"] / size.max()
    centre = np.array(c["offset"], float); centre[1] += s * d[1] * 0.5
    pos = centre - r @ (s * center)
    M = np.eye(4); M[:3, :3] = r * s; M[:3, 3] = np.array(unit_pos) + pos
    return M

def world(name, M):
    Vi = TPL[name]["Vi"]
    return ((Vi @ M[:3, :3].T + M[:3, 3]) @ B3.T)

def bvh(name, Wv): return BVHTree.FromPolygons(Wv.tolist(), TPL[name]["T"], all_triangles=True)

def copy_dict(fam, off, R):
    q = [round(float(a), 6) for a in m2q(R)]
    c = {"offset": [round(float(a), 5) for a in off], "longest_m": LONG[fam], "anchor": "bottom"}
    if fam == "bomb": c["rot_quat_xyzw"] = q
    else: c["align"] = {"long_axis_to": [0, 1, 0], "thin_axis_to": [1, 0, 0], "then_rotate_quat_xyzw": q}
    return c

# ---------- packing (one layout per holder type, in the holder's own frame: centre at the origin) ----------
def pack_standing(fam, n_units, per_unit, R_in, R_lim, rim_h, seed, tilt_cap=4.5, pool=140, levels=(0.0,)):
    """Stand N = n_units x per_unit copies, core first: each step draws a pool of candidates (position, lean, spin), tries them
    from the centre outward, each at every level (the foot height: the straw-packed barrel holds a copy at 0, 1 or 2 levels
    up, so neighbouring fletchings and heads sit at different heights), and keeps the first that, for EVERY model of the
    family, stays inside R_in (less 4 mm) below the rim and inside R_lim everywhere, and touches no copy already standing.
    Returns [(offset, R)] in Unity holder space (offset.y includes the level and the lift a lean needs)."""
    rnd = random.Random(seed)
    kinds = FAM[fam]
    N = n_units * per_unit
    placed = []                                       # (off, R, {kind: (W, bvh, lo, hi)})
    def attempt(r, phi, R, lv):
        off = np.array([r * math.cos(phi), 0.001 + lv, r * math.sin(phi)])
        c = copy_dict(fam, off, R)
        Ws = {k: world(k, place_u((0, 0, 0), c, k)) for k in kinds}
        need = max(0.002 + lv - Ws[k][:, 2].min() for k in kinds)
        if need > 0:
            off[1] += need
            for k in kinds: Ws[k][:, 2] += need
        for k in kinds:
            Wv = Ws[k]; dd = np.hypot(Wv[:, 0], Wv[:, 1])
            if (dd[Wv[:, 2] < rim_h + 0.01] > R_in - 0.004).any() or (dd > R_lim).any(): return None
        mine = {}
        for k in kinds:
            Wv = Ws[k]; lo, hi = Wv.min(0), Wv.max(0)
            near = [o for _, _, o in placed if (lo <= o[k][3]).all() and (o[k][2] <= hi).all()]
            if near:
                bv = bvh(k, Wv)
                if any(bv.overlap(o[k][1]) for o in near): return None
            else: bv = None
            mine[k] = (Wv, bv, lo, hi)
        for k in kinds:
            if mine[k][1] is None: mine[k] = (mine[k][0], bvh(k, mine[k][0]), mine[k][2], mine[k][3])
        return off, mine
    for j in range(N):
        cands = []
        for _ in range(pool):
            r = 0.0 if (j == 0 and not cands) else (R_in - 0.01) * math.sqrt(rnd.random())
            phi = rnd.uniform(0, 2 * math.pi)
            room = max(0.0, R_in - 0.03 - r)
            tilt = math.radians(rnd.uniform(0.2, 1.0) * min(tilt_cap, math.degrees(math.atan2(room, rim_h))))
            R = Rlean(phi + rnd.uniform(-0.5, 0.5), tilt) @ Ry(rnd.uniform(0, 2 * math.pi))
            cands.append((r, phi, R))
        cands.sort(key=lambda c: c[0])
        got = None
        for r, phi, R in cands:
            lvs = list(levels); rnd.shuffle(lvs)
            for lv in lvs:
                got = attempt(r, phi, R, lv)
                if got: break
            if got: break
        if not got:
            print(f"PACK {fam}: stopped at {len(placed)} of {N}", flush=True)
            break
        placed.append((got[0], R, got[1]))
    print(f"PACK {fam}: {len(placed)} copies", flush=True)
    return [(p[0], p[1]) for p in placed]

def pack_bombs(ax, az, seed, att_max=500):
    """8 bombs in a crate half (Unity holder space, floor = the straw peaks at y 0): a layer of 3 x 2, then 2 on top in the
    hollows, each lowered until a lower one (any bomb model) would be touched."""
    rnd = random.Random(seed)
    kinds = FAM["bomb"]
    cells = [((i - 1) * ax * 2 / 3, (jj - 0.5) * az) for jj in (1, 0) for i in range(3)]       # back row first, left to right
    tops = [(-ax / 3, 0.0), (ax / 3, 0.0)]
    placed = []
    def clear(Ws):
        for k in kinds:
            Wv = Ws[k]
            if (np.abs(Wv[:, 0]) > ax - 0.004).any() or (np.abs(Wv[:, 1]) > az - 0.004).any() or Wv[:, 2].min() < -1e-4: return None
        mine = {}
        for k in kinds:
            Wv = Ws[k]; lo, hi = Wv.min(0), Wv.max(0); bv = bvh(k, Wv)
            for _, _, other in placed:
                olo, ohi, obv = other[k][2], other[k][3], other[k][1]
                if (lo <= ohi).all() and (olo <= hi).all() and bv.overlap(obv): return None
            mine[k] = (Wv, bv, lo, hi)
        return mine
    for (cx, cz), top in [(c, False) for c in cells] + [(t, True) for t in tops]:
        for att in range(att_max):
            jx, jz = (rnd.uniform(-0.02, 0.02), rnd.uniform(-0.015, 0.015)) if not top else (rnd.uniform(-0.03, 0.03), rnd.uniform(-0.03, 0.03))
            R = Rlean(rnd.uniform(0, 2 * math.pi), math.radians(rnd.uniform(0, 10))) @ Ry(rnd.uniform(0, 2 * math.pi))
            off = np.array([-(cx + jx), 0.0, -(cz + jz)])            # Blender (x, y) -> Unity (-x, -z)
            c = copy_dict("bomb", off, R)
            Ws = {k: world(k, place_u((0, 0, 0), c, k)) for k in kinds}
            need = max(0.001 - Ws[k][:, 2].min() for k in kinds)
            for k in kinds: Ws[k][:, 2] += need
            off[1] += need
            if top:
                lift, step = 0.24, 0.004
                for k in kinds: Ws[k][:, 2] += lift
                if clear(Ws) is None: continue
                while lift >= step:
                    for k in kinds: Ws[k][:, 2] -= step
                    if clear(Ws) is None:
                        for k in kinds: Ws[k][:, 2] += step
                        break
                    lift -= step
                off[1] += lift
            mine = clear(Ws)
            if mine is None: continue
            placed.append((off.copy(), R, mine)); break
        else:
            print("PACK bomb: no room for a bomb at", (cx, cz), flush=True)
    print(f"PACK bomb: {len(placed)} copies", flush=True)
    return [(p[0], p[1]) for p in placed]


# ---------- r2: bundles. A unit's copies stand as one bundle gathered in its own spot of the barrel or tub: at the gather height
# the shafts run close together and lean a little apart (a straight shaft that leans outward above that height leans inward
# below it, so the bundle crosses there: heads and fletchings both open out a little). No cord: the straw packing already
# shows it was bundled by hand. Core unit in the middle, the others round it, at least `sep` between bundle centres.
GATHER_Z = {"arrow": 0.66, "bolt": 0.25}      # gather height over the barrel / tub head

def try_copy(fam, kinds, placed, off, R, rim_h, R_in, R_lim):
    """One copy at Unity holder offset off (x, foot height, z) with rotation R: the lift a lean needs, then the same tests as
    pack_standing: every model of the family inside R_in below the rim and inside R_lim, touching no copy already standing."""
    off = np.array(off, float)
    c = copy_dict(fam, off, R)
    Ws = {k: world(k, place_u((0, 0, 0), c, k)) for k in kinds}
    lv = off[1] - 0.001
    need = max(0.002 + lv - Ws[k][:, 2].min() for k in kinds)
    if need > 0:
        off[1] += need
        for k in kinds: Ws[k][:, 2] += need
    for k in kinds:
        Wv = Ws[k]; dd = np.hypot(Wv[:, 0], Wv[:, 1])
        if (dd[Wv[:, 2] < rim_h + 0.01] > R_in - 0.004).any() or (dd > R_lim).any(): return None
    mine = {}
    for k in kinds:
        Wv = Ws[k]; lo, hi = Wv.min(0), Wv.max(0)
        near = [o for _, _, o in placed if (lo <= o[k][3]).all() and (o[k][2] <= hi).all()]
        bv = bvh(k, Wv)
        if any(bv.overlap(o[k][1]) for o in near): return None
        mine[k] = (Wv, bv, lo, hi)
    return off, mine

def pack_sheaves(fam, n_units, per, R_in, R_lim, rim_h, seed, zb, rho_max, sep, edge, tilt=(1.0, 4.5), levels=(0.0,), pool=50, rho_min=0.011, tries=60):
    """n_units bundles of per copies, core first. A bundle: a centre c (at least sep from every other bundle's centre, edge
    inside R_in), its copies' shafts passing the gather height zb within rho_max of c (the tightest candidate that clears
    wins), each leaning by tilt degrees away from c, its foot where that lean puts it (the foot height one of levels, so
    the fletchings of neighbouring shafts sit at different heights). Returns [(offset, R)]."""
    rnd = random.Random(seed)
    kinds = FAM[fam]
    placed, cents = [], []
    for u in range(n_units):
        cs = []
        for _ in range(tries):
            r = 0.0 if (u == 0 and not cs) else (R_in - edge) * math.sqrt(rnd.random())
            a = rnd.uniform(0, 2 * math.pi)
            cs.append((r * math.cos(a), r * math.sin(a)))
        cs.sort(key=lambda c: math.hypot(*c))
        done = False
        for cx, cz in cs:
            if any(math.hypot(cx - ox, cz - oz) < sep for ox, oz in cents): continue
            mark = len(placed); ok = True
            for m in range(per):
                cand = []
                for _ in range(pool):
                    rho = 0.0 if m == 0 else rnd.uniform(rho_min, rho_max)
                    al = rnd.uniform(0, 2 * math.pi)
                    bx, bz = cx + rho * math.cos(al), cz + rho * math.sin(al)
                    if m == 0: phi = (math.atan2(cz, cx) if math.hypot(cx, cz) > 0.03 else rnd.uniform(0, 2 * math.pi)) + rnd.uniform(-0.9, 0.9)
                    else: phi = al + rnd.uniform(-0.5, 0.5)
                    th = math.radians(rnd.uniform(*tilt))
                    lv = rnd.choice(levels)
                    sh = (zb - lv) * math.tan(th)
                    R = Rlean(phi, th) @ Ry(rnd.uniform(0, 2 * math.pi))
                    cand.append((rho, (bx - sh * math.cos(phi), 0.001 + lv, bz - sh * math.sin(phi)), R))
                cand.sort(key=lambda c: c[0])
                got = None
                for rho, off, R in cand:
                    got = try_copy(fam, kinds, placed, off, R, rim_h, R_in, R_lim)
                    if got: break
                if not got: ok = False; break
                placed.append((got[0], R, got[1]))
            if ok: cents.append((cx, cz)); done = True; break
            del placed[mark:]
        if not done:
            print(f"PACK {fam}: bundle {u} found no room", flush=True); break
    print(f"PACK {fam}: {len(placed)} copies in {len(cents)} bundles", flush=True)
    return [(p[0], p[1]) for p in placed]

def pack_bomb_heap(ax, az, n, seed, k_cand=40):
    """n bombs in a crate half (Unity holder space, floor = the straw peaks at y 0), dropped one by one and settled: each drop
    tries k_cand random spots and spins and keeps the one that ends lowest (lowering it from above until a lower bomb or the
    floor is touched), so the heap fills the floor first, then the hollows, then rises over the rim."""
    rnd = random.Random(seed)
    kinds = FAM["bomb"]
    placed = []
    def clear(Ws):
        for k in kinds:
            Wv = Ws[k]
            if (np.abs(Wv[:, 0]) > ax - 0.004).any() or (np.abs(Wv[:, 1]) > az - 0.004).any() or Wv[:, 2].min() < -1e-4: return None
        mine = {}
        for k in kinds:
            Wv = Ws[k]; lo, hi = Wv.min(0), Wv.max(0); bv = bvh(k, Wv)
            for _, _, other in placed:
                olo, ohi, obv = other[k][2], other[k][3], other[k][1]
                if (lo <= ohi).all() and (olo <= hi).all() and bv.overlap(obv): return None
            mine[k] = (Wv, bv, lo, hi)
        return mine
    def shifted(Ws, dz): return {k: Wv + np.array([0, 0, dz]) for k, Wv in Ws.items()}
    for j in range(n):
        best = None
        for _ in range(k_cand):
            cx = rnd.uniform(-ax + 0.09, ax - 0.09); cz = rnd.uniform(-az + 0.09, az - 0.09)
            R = Rlean(rnd.uniform(0, 2 * math.pi), math.radians(rnd.uniform(0, 10))) @ Ry(rnd.uniform(0, 2 * math.pi))
            off = np.array([-cx, 0.0, -cz])
            c = copy_dict("bomb", off, R)
            Ws = {k: world(k, place_u((0, 0, 0), c, k)) for k in kinds}
            need = max(0.001 - Ws[k][:, 2].min() for k in kinds)
            Ws = shifted(Ws, need)
            if clear(shifted(Ws, 0.60)) is None: continue
            lift = 0.60
            while lift > 0.0:
                nxt = max(lift - 0.02, 0.0)
                if clear(shifted(Ws, nxt)) is None: break
                lift = nxt
            if lift > 0:
                lo_bad = max(lift - 0.02, 0.0)
                st = lift
                while st - 0.004 >= lo_bad - 1e-9 and clear(shifted(Ws, st - 0.004)) is not None: st -= 0.004
                lift = st
            final = need + lift
            if best is None or final < best[0]: best = (final, off, R, lift, Ws)
        if best is None:
            print("PACK bomb: no spot for bomb", j, flush=True); break
        final, off, R, lift, Ws = best
        mine = clear(shifted(Ws, lift))
        off = off.copy(); off[1] = final
        placed.append((off, R, mine))
    print(f"PACK bomb: {len(placed)} copies, top {max(float(o[0][1]) for o in placed):.3f}", flush=True)
    return [(p[0], p[1]) for p in placed]

# ---------- units ----------
def holders():
    """(group, holder type, family, Blender centre (x, y), floor z, yaw for the shared layout, paint)"""
    hs = []
    for i, x in enumerate(BAR_X): hs.append((i, "barrel", "arrow", (x, BAR_Y), FLOOR, i * 1.3, PAINT_BAR[i]))
    for i, x in enumerate(TUB_X): hs.append((6 + i, "tub", "bolt", (x, TUB_Y), FLOOR, 0.7 + i * 2.1, PAINT_TUB[i]))
    cy = (CR_Y0 + CR_Y1) / 2
    hx = ((CR_X0 + CR_T + CR_MID - CR_T / 2) / 2, (CR_MID + CR_T / 2 + CR_X1 - CR_T) / 2)
    for i in range(2): hs.append((8 + i, "crate_half", "bomb", (hx[i], cy), STRAW_TOP, math.pi * i, PAINT_CRATE[i]))
    return hs

PER = {"arrow": (8, 2), "bolt": (4, 6), "bomb": (4, 4)}

def best_pack(fam, R_in, R_lim, rim_h, seeds, **kw):
    n_units, per = PER[fam]
    best = []
    for sd in seeds:
        lay = pack_standing(fam, n_units, per, R_in, R_lim, rim_h, seed=sd, pool=300, levels=LEVELS[fam], **kw)
        if len(lay) > len(best): best = lay
        if len(best) == n_units * per: break
    return best
SEEDS_ARROW, SEEDS_BOLT = (7, 5, 6, 8, 9, 10), (9, 10, 11)

def best_sheaf(fam, R_in, R_lim, rim_h, seeds, **kw):
    n_units, per = PER[fam]
    best = []
    for sd in seeds:
        lay = pack_sheaves(fam, n_units, per, R_in, R_lim, rim_h, seed=sd, levels=LEVELS[fam], **kw)
        if len(lay) > len(best): best = lay
        if len(best) == n_units * per: break
    return best
DEMO = {"arrow": "ArrowFlint", "bolt": "BoltCarapace", "bomb": "BombBile"}

def make_units(layouts):
    units = []
    for g, htype, fam, (bx, by), fz, yaw, paint in holders():
        n_units, per = PER[fam]
        lay = layouts[fam]
        Rh = Ry(yaw)
        cu = np.array([-bx, fz, -by])
        abs_copies = [(cu + Rh @ off, Rh @ R) for off, R in lay]
        for k in range(n_units):
            mine = abs_copies[k * per:(k + 1) * per]
            if not mine: continue
            P = np.array([o for o, _ in mine])
            upos = np.array([P[:, 0].mean(), fz, P[:, 2].mean()])
            units.append({"index": len(units), "crate": g, "holder": htype, "kind": fam, "step": k, "paint": PAINT_NAMES[paint],
                          "position": [round(float(a), 5) for a in upos], "rotation": [0.0, 0.0, 0.0],
                          "box": [round(float(np.ptp(P[:, 0])) + 0.06, 3), LONG[fam], round(float(np.ptp(P[:, 2])) + 0.06, 3)],
                          "render_item": DEMO[fam], "copies": [copy_dict(fam, o - upos, R) for o, R in mine]})
    return units

# ---------- checks ----------
def unit_worlds(u, name):
    return [world(name, place_u(u["position"], c, name)) for c in u["copies"]]

def run_checks(units, frame):
    V, T = tri_list(frame.data)
    fbvh = BVHTree.FromPolygons(V, T, all_triangles=True)
    res = {}
    byg = {}
    for u in units: byg.setdefault(u["crate"], []).append(u)
    for fam in ("arrow", "bolt", "bomb"):
        for k in FAM[fam]:
            clip, over, n = 0, 0, 0
            for g, us in byg.items():
                if us[0]["kind"] != fam: continue
                Ws = [w for u in us for w in unit_worlds(u, k)]
                B = [bvh(k, w) for w in Ws]
                n += len(Ws)
                clip += sum(1 for b in B if fbvh.overlap(b))
                for i in range(len(B)):
                    for j in range(i + 1, len(B)):
                        if B[i].overlap(B[j]): over += 1
            res[k] = {"copies": n, "frame_clipping": clip, "copy_overlaps": over}
    print("CHECK", json.dumps(res), flush=True)
    return res

def cross_check(units, fill, frame):
    """A filled store (fill: group -> kind): every copy against the frame and against every copy of every OTHER group."""
    V, T = tri_list(frame.data)
    fbvh = BVHTree.FromPolygons(V, T, all_triangles=True)
    items = []
    for u in units:
        k = fill.get(u["crate"])
        if not k: continue
        for w in unit_worlds(u, k): items.append((u["crate"], k, w, bvh(k, w), w.min(0), w.max(0)))
    clip = sum(1 for it in items if fbvh.overlap(it[3]))
    cross = 0
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            a, b = items[i], items[j]
            if a[0] == b[0] or not ((a[4] <= b[5]).all() and (b[4] <= a[5]).all()): continue
            if a[3].overlap(b[3]): cross += 1
    top = max(float(it[2][:, 2].max()) for it in items) if items else 0.0
    return {"copies": len(items), "frame_clipping": clip, "between_groups": cross, "contents_top_z": round(top, 3)}

# ---------- the mod's ByGroup, for the fill renders (types claim groups by their spot in the 8 x 8 chest grid) ----------
def fam_of(k): return "arrow" if k.startswith("Arrow") else "bolt" if k.startswith("Bolt") else "bomb"

def by_group(units, types, at, family_filter=False):
    groups = sorted({u["crate"] for u in units})
    free = {g: [i for i, u in enumerate(units) if u["crate"] == g] for g in groups}
    free_all = {g: list(v) for g, v in free.items()}
    cen = {g: np.mean([units[i]["position"] for i in free[g]], 0) for g in groups}
    xs = [c[0] for c in cen.values()]; ys = [c[1] for c in cen.values()]; zs = [c[2] for c in cen.values()]
    x0, x1, y0, y1, z0, z1 = min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)
    tall = y1 - y0 > z1 - z0
    part = lambda a, s: a / s if s > 1e-3 else 0.5
    spot = {g: np.array([part(x1 - c[0], x1 - x0), part(y1 - c[1], y1 - y0) if tall else part(c[2] - z0, z1 - z0)]) for g, c in cen.items()}
    mine, res = {}, []
    for t, here in zip(types, at):
        here = np.array(here)
        def nearest(ok):
            c = [g for g in groups if free[g] and ok(g)]
            return min(c, key=lambda g: (float(((spot[g] - here) ** 2).sum()), g)) if c else -1
        fit = (lambda k: units[free_all[k][0]]["kind"] == fam_of(t)) if family_filter else (lambda k: True)
        g = mine[t] if t in mine and free[mine[t]] else -1
        if g < 0: g = nearest(lambda k: k not in mine.values() and fit(k))
        if g < 0: g = nearest(fit)
        if g < 0: res.append(-1); continue
        mine[t] = g; res.append(free[g].pop(0))
    return res

def chest(rows):
    """rows: list of (kind, count) runs laid into an 8 x 8 grid row by row; returns types and grid spots."""
    types, at = [], []
    for k, n in rows:
        for _ in range(n):
            i = len(types); x, y = i % 8, i // 8
            types.append(k); at.append(((x + 0.5) / 8, (y + 0.5) / 8))
    return types, at

def chest_at(cells):
    """cells: list of (kind, row, col0, count)."""
    types, at = [], []
    for k, row, c0, n in cells:
        for c in range(c0, c0 + n): types.append(k); at.append(((c + 0.5) / 8, (row + 0.5) / 8))
    return types, at

# ---------- coplanar check (round 2): faces that face the same way, lie in one plane and overlap z-fight in the game ----------
def _clip_area(subj, clipper):
    """Area of the intersection of two convex 2D polygons (Sutherland-Hodgman); both counter-clockwise or both clockwise."""
    def orient(poly): return sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1] for i in range(len(poly)))
    sg = 1.0 if orient(clipper) >= 0 else -1.0
    out = list(subj)
    for i in range(len(clipper)):
        a, b = clipper[i], clipper[(i + 1) % len(clipper)]
        inp, out = out, []
        if not inp: break
        def side(p): return sg * ((b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0]))
        for k in range(len(inp)):
            p, q = inp[k], inp[(k + 1) % len(inp)]
            sp, sq = side(p), side(q)
            if sp >= 0: out.append(p)
            if (sp >= 0) != (sq >= 0):
                t = sp / (sp - sq); out.append((p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])))
    return abs(orient(out)) / 2 if len(out) >= 3 else 0.0

def coplanar_overlaps(parts, tol=0.002, min_area=2e-7, facing=1):
    """parts: [(name, mesh)] in world space. Every pair of triangles that (facing=1) face the same way or (facing=-1) face
    each other, whose planes are within tol (m) of each other and whose projections overlap by more than min_area (m2).
    Returns [(area, name_a, name_b, centre, normal, gap)] sorted by area, largest first."""
    P, Tn, own = [], [], []
    for nm, me in parts:
        V = np.array([tuple(v.co) for v in me.vertices], float)
        for pl in me.polygons:
            vs = list(pl.vertices)
            for i in range(1, len(vs) - 1): P.append(V[[vs[0], vs[i], vs[i + 1]]]); own.append(nm)
    P = np.array(P)
    N = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0]); A = np.linalg.norm(N, axis=1) / 2
    ok = A > 1e-9
    N = N / np.where(ok, 2 * A, 1)[:, None]
    res = []
    for i in np.nonzero(ok)[0]:
        j = np.arange(i + 1, len(P))
        j = j[ok[j]]
        j = j[(N[j] @ N[i]) * facing > 0.9995]
        if not len(j): continue
        dist = np.einsum("jkc,c->jk", P[j] - P[i][0], N[i])
        near = (np.abs(dist).max(1) <= tol) if facing > 0 else (np.abs(dist).max(1) <= tol)
        for jj in j[near]:
            n = N[i]; ax = int(np.argmax(np.abs(n))); keep = [a for a in range(3) if a != ax]
            a2 = [tuple(q[keep]) for q in P[i]]; b2 = [tuple(q[keep]) for q in P[jj]]
            ar = _clip_area(a2, b2)
            if ar > min_area:
                gap = float(np.mean(np.einsum("kc,c->k", P[jj] - P[i][0], n)))
                res.append((ar, own[i], own[jj], ((P[i].mean(0) + P[jj].mean(0)) / 2).round(3).tolist(), n.round(2).tolist(), round(gap, 4)))
    res.sort(key=lambda r: -r[0])
    return res

def report_coplanar(parts, label):
    same = coplanar_overlaps(parts, facing=1)
    back = coplanar_overlaps(parts, facing=-1)
    print(f"COPLANAR {label}: same-facing overlapping pairs {len(same)} (0 expected); back-to-back pairs {len(back)} (hidden, informational)", flush=True)
    import re, collections
    agg = collections.OrderedDict()
    for r in same:
        key = (re.sub(r"\.\d+$", "", r[1]), re.sub(r"\.\d+$", "", r[2]), tuple(int(round(a)) for a in r[4]), round(r[5] * 1000, 1))
        e = agg.setdefault(key, [0, 0.0, r[3]]); e[0] += 1; e[1] += r[0]
    for key, (n, ar, c) in sorted(agg.items(), key=lambda kv: -kv[1][1]):
        print("  SAME", key[0], "x", key[1], "normal", key[2], "gap_mm", key[3], "pairs", n, f"area {ar * 1e4:.1f}cm2", "e.g. at", c, flush=True)
    agg = collections.OrderedDict()
    for r in back:
        key = (re.sub(r"\.\d+$", "", r[1]), re.sub(r"\.\d+$", "", r[2]), tuple(abs(int(round(a))) for a in r[4]))
        e = agg.setdefault(key, [0, 0.0, r[3]]); e[0] += 1; e[1] += r[0]
    for key, (n, ar, c) in sorted(agg.items(), key=lambda kv: -kv[1][1]):
        print("  BACK", key[0], "x", key[1], "axis", key[2], "pairs", n, f"area {ar * 1e4:.1f}cm2", "e.g. at", c, flush=True)
    return {"same_facing_overlaps": len(same), "back_to_back": len(back), "tolerance_mm": 2.0, "min_area_cm2": 0.002}

R2_CHANGES = [
    "frame: no two faces that face the same way lie in one plane and overlap (checks.coplanar_frame; r1 had 492 such pairs: the iron band "
    "tops lay in the end-grain plane of the post tops, the sill band under its plates, neighbouring stave tops and bottoms, the plate/band edge). "
    "Fixed in geometry: bands end 4 mm below the post heads, the sill band runs between the plates, every other stave stands 4 mm lower, plates "
    "sink 1.5 mm into the beam they sit on, beams, boards and studs run 2 mm into the post, deck or wall they meet.",
    "arrows and bolts stand as bundles: each unit's copies together in their own spot (no cord); same unit count and groups",
    "bomb crate: 4 bombs per unit (16 per half, r1: 8), settled as a heap, so a full half reads full",
]

# ---------- main ----------
if __name__ == "__main__":
    os.makedirs(OUTA, exist_ok=True); os.makedirs(OUT, exist_ok=True)
    setup_scene()
    atlas = build_atlas()
    base.MAT = make_material("fletcher", atlas)
    base.PARTS.clear()
    base.uv_face = my_uv
    build_frame()

    for fam in FAM:
        for k in FAM[fam]: load_tpl(k)
    print("VISIBLE", {k: (len(t["T"]), round(t["opaque"], 3)) for k, t in TPL.items()}, flush=True)
    R_IN_B, R_IN_T = BAR_R - BAR_T, TUB_R - BAR_T
    layouts = {
        "arrow": best_sheaf("arrow", R_IN_B, BAR_PITCH / 2 - 0.01, BAR_H - HEAD_Z0 - HEAD_T, seeds=SEEDS_ARROW, zb=GATHER_Z["arrow"],
                            rho_max=0.05, sep=0.07, edge=0.03, tilt=(0.5, 4.0), pool=150, tries=150),
        "bolt": best_sheaf("bolt", R_IN_T, TUB_R - 0.003, TUB_H - HEAD_Z0 - HEAD_T, seeds=SEEDS_BOLT, zb=GATHER_Z["bolt"],
                           rho_max=0.10, sep=0.14, edge=0.04, tilt=(1.0, 5.0), pool=150, tries=150),
        "bomb": pack_bomb_heap(((CR_MID - CR_T / 2) - (CR_X0 + CR_T)) / 2 - 0.003, (CR_Y1 - CR_Y0 - 2 * CR_T) / 2 - 0.003,
                               n=PER["bomb"][0] * PER["bomb"][1], seed=3),
    }
    units = make_units(layouts)
    straw_cut = {}
    for g, htype, fam, (bx, by), fz, yaw, paint in holders():
        if fam == "bomb": continue
        bvs = [bvh(k, w) for u in units if u["crate"] == g for k in FAM[fam] for w in unit_worlds(u, k)]
        apo = (BAR_R if fam == "arrow" else TUB_R) - BAR_T
        _, nhit = straw_disc(bx, by, apo, fz + STRAW_IN[fam], bvs)
        straw_cut[g] = nhit
    print("STRAW holes (triangles left out) per group", straw_cut, flush=True)
    cop = report_coplanar([(o.name, o.data) for o in base.PARTS], "frame")
    if "--frame-only" in argv: sys.exit(0)
    frame = join(list(base.PARTS), "Fletcher")
    ftris = tris(frame)
    bb = np.array([tuple(v.co) for v in frame.data.vertices])
    print(f"FRAME tris {ftris} bounds {bb.min(0).round(4)} {bb.max(0).round(4)}", flush=True)
    chk = run_checks(units, frame)

    full_t, full_at = chest_at([("ArrowFlint", 0, 0, 8), ("ArrowFlint", 1, 0, 8), ("ArrowPoison", 2, 0, 8), ("ArrowIron", 3, 0, 8),
                                ("ArrowFire", 4, 0, 8), ("ArrowCarapace", 5, 0, 8), ("BoltCarapace", 6, 0, 4), ("BoltCharred", 6, 4, 4),
                                ("BombBile", 7, 0, 4), ("BombLava", 7, 4, 4)])
    half_t, half_at = chest_at([("ArrowFlint", 0, 0, 8), ("ArrowPoison", 1, 0, 6), ("ArrowIron", 2, 0, 5), ("ArrowCarapace", 3, 0, 4),
                                ("ArrowCharred", 4, 0, 3), ("BoltCarapace", 6, 0, 3), ("BoltCharred", 6, 4, 2), ("BombBile", 7, 0, 2),
                                ("BombLava", 7, 4, 1)])
    gfam = {u["crate"]: u["kind"] for u in units}
    def grouped(fill):
        out = {}
        for i, k in fill.items(): out.setdefault(units[i]["crate"], set()).add(k)
        return out
    raw = grouped({i: k for i, k in zip(by_group(units, full_t, full_at), full_t) if i >= 0})
    wrong = sorted(g for g, ks in raw.items() if len(ks) > 1 or any(fam_of(k) != gfam[g] for k in ks))
    print("BYGROUP as the mod does it today (full)", {g: sorted(v) for g, v in sorted(raw.items())}, "mixed or wrong family:", wrong, flush=True)
    fills = {}
    for nm, (ty, at) in {"full": (full_t, full_at), "half": (half_t, half_at)}.items():
        idx = by_group(units, ty, at, family_filter=True)
        fills[nm] = {i: k for i, k in zip(idx, ty) if i >= 0}
    groups_full = grouped(fills["full"])
    wrong_f = sorted(g for g, ks in groups_full.items() if len(ks) > 1 or any(fam_of(k) != gfam[g] for k in ks))
    print("BYGROUP with a family filter (full)", {g: sorted(v) for g, v in sorted(groups_full.items())}, "wrong:", wrong_f, flush=True)
    full_fill_g = {g: sorted(v)[0] for g, v in groups_full.items()}
    xc = cross_check(units, full_fill_g, frame)
    print("CROSS full", json.dumps(xc), flush=True)

    base.save_atlas(atlas, os.path.join(OUTA, "fletcher_atlas.png"))
    export_obj(frame, os.path.join(OUTA, "Fletcher.obj"))
    n_copies = {f: sum(len(u["copies"]) for u in units if u["kind"] == f) for f in FAM}
    doc = {
        "schema": "storehouse-anchors/1", "furniture": "Fletcher's Barrels", "slug": "fletcher", "round": 2, "changes_from_r1": R2_CHANGES, "placement": "ground",
        "unit_count": len(units), "slots_designed_for": 64, "stack_per_unit": True, "mirror": False, "heap": False,
        "frame": {"obj": "Fletcher.obj", "atlas": "fletcher_atlas.png 128x128 point", "tris": ftris, "size_m": [W, H_BACK, D],
                  "bounds_unity": {"min": [-HX, 0.0, -HY], "max": [HX, H_BACK, HY]}, "contents_top_y_full": xc["contents_top_z"],
                  "stacking": "not stackable: the arrow sheaves stand above the frame (to ~1.5 m); keep this store out of the flat-top "
                              "stacking rule in BuildPiece (it is a ground store)."},
        "space": {"unity": "prefab space, origin on the floor at the centre of the footprint, +z front, +y up, +x to the furniture's left seen from the front",
                  "from_blender": "ux=-bx, uy=bz, uz=-by"},
        "groups": {"key": "crate", "0-5": "arrow barrels, left to right seen from the front (8 units each)",
                   "6-7": "bolt tubs, front left (4 units each)", "8-9": "bomb crate halves, front right (4 units each)",
                   "rule": "one item kind per group (StoreModel.ByGroup). Each unit's 'kind' (arrow / bolt / bomb) names the family its "
                           "copies are packed for. ByGroup itself does not look at it: a stack claims the free group nearest to its "
                           "chest-grid spot, so an arrow stack can claim a bolt tub or the crate (drawn as an 0.86 m arrow standing in a tub or among the bombs). "
                           "A family filter in ByGroup (like the existing egg-and-hook rule: ammo type -> unit kind) keeps them apart."},
        "fill_order": "units are listed group by group; inside a group in fill order: step 0 is the core of the sheaf (barrel and tub "
                      "centre, the crate's back row), later steps stand round it, so the bundle thickens as stock grows. ByGroup "
                      "dequeues a group's units in this order.",
        "position": "unit position = mean of its copies' feet, on the floor of its holder (barrel and tub heads at y 0.215, the "
                    "straw peaks at y 0.219). box = [x, y, z] Unity, informational.",
        "copy_rule": "arrows and bolts: align (long axis -> up, thin axis -> x), then_rotate = a lean of up to 4 degrees (5 for "
                     "bolts) times a spin about the shaft, fit_longest_m (arrows 0.86, bolts 0.32), anchor bottom. Bombs: no align, "
                     "rot_quat_xyzw (any spin, up to 10 degrees of tilt), fit_longest_m 0.22, anchor bottom. offset.y = the copy's foot "
                     "height in the straw (arrows 0 .. 0.42 in steps of 0.07, bolts 0 .. 0.08) plus the lift that keeps the lowest vertex "
                     "of every model of the family above it (a leaning copy dips below its bounds). Bombs: 4 per unit, 16 per half, "
                     "dropped and settled one by one (a heap that rises over the rim when full).",
        "straw": "barrels and tubs are packed with straw to 0.45 (arrows) and 0.11 (bolts) over the head; every foot stands in it. "
                 "The straw surface is part of the frame, with each triangle that any copy of any model touches cut away, so "
                 "the straw parts round the shafts and nothing clips it.",
        "heads": {**HEADS, "why": "Align.Axes turns the item's +long axis to up; the arrow models differ in sign (flint's head is at item +z, "
                  "poison's at -z), so no single anchor stands every kind head-up. A per-prefab half turn in C# (like the Greens table) "
                  "for the four 'down' kinds would make all of them head-up."},
        "items": {"arrow_size": "an arrow item is 1.63-1.84 m long in the game (ArrowFlint: root scale 1, child 'model' scale 1.5 on a "
                                "1.144 m mesh; mod bounds 0.176 x 0.302 x 1.839). Here: fit_longest_m 0.86 = 0.47x flint, a real "
                                "arrow's length; at 0.70x a barrel held only 2-5 arrows without touching (the carapace and silver "
                                "models are 0.24 m across).",
                  "bounds_item_space": {k: {"center": v[0], "size": v[1], "root_scale": [1, 1, 1],
                                            "x_true_size": round(LONG["arrow" if k.startswith("Arrow") else "bolt" if k.startswith("Bolt") else "bomb"] / max(v[1]), 3)}
                                        for k, v in MODB.items()},
                  "checked_models": FAM, "not_checked": {"ArrowNeedle": "two Quad renderers from Unity's built-in resources (not in the "
                                                         "bundle, not ripped); its mesh is 1.82 m like the others"}},
        "layout": {"bundles": "each unit's copies stand as one bundle in its own spot: the shafts pass the gather height (arrows %.2f m, bolts %.2f m over the head) within 5 cm (bolts 10 cm) of the bundle centre and lean a few degrees apart there, so heads and fletchings open out a little; no cord (the straw packing shows they were bundled by hand)." % (GATHER_Z["arrow"], GATHER_Z["bolt"]),
                   "barrels": {"count": 6, "units": 8, "copies_per_unit": 2, "foot_levels_m": list(LEVELS["arrow"]), "inner_radius_m": round(R_IN_B, 3), "stave_height_m": BAR_H,
                               "pitch_m": BAR_PITCH, "centre_y_blender": BAR_Y, "x_blender": BAR_X},
                   "tubs": {"count": 2, "units": 4, "copies_per_unit": 6, "foot_levels_m": list(LEVELS["bolt"]), "inner_radius_m": round(R_IN_T, 3), "stave_height_m": TUB_H,
                            "x_blender": TUB_X, "centre_y_blender": TUB_Y},
                   "crate": {"halves": 2, "units": 4, "copies_per_unit": PER["bomb"][1], "x_blender": [CR_X0, CR_X1], "y_blender": [CR_Y0, CR_Y1]},
                   "copies_full": n_copies},
        "checks": {"coplanar_frame": cop, "per_model": chk, "full_store": xc, "bygroup_today_wrong_groups": wrong, "bygroup_family_filter_wrong_groups": wrong_f,
                   "method": "mesh against mesh (BVH): every copy of every checked model against the frame and against every other "
                             "copy in its group; the full render fill also across groups."},
        "units_data": units}
    write_json_atomic(doc, os.path.join(OUTA, "fletcher_anchors.json"))     # last: the mod live-reloads
    print("WROTE", OUTA, flush=True)
    if "--no-render" in argv: sys.exit(0)

    # ---------------- renders ----------------
    def spawn(dx, fill):
        fr = frame.copy(); bpy.context.scene.collection.objects.link(fr); fr.hide_render = False; fr.location = (dx, 0, 0)
        for i, k in fill.items():
            for c in units[i]["copies"]:
                ob = bpy.data.objects.new(k, TPL[k]["mesh"]); bpy.context.scene.collection.objects.link(ob)
                ob.matrix_world = Matrix.Translation((dx, 0, 0)) @ Matrix((B4 @ place_u(units[i]["position"], c, k) @ K4).tolist())
    X_EMPTY, X_HALF, X_FULL, X_BUNK = -8.4, -4.4, 0.0, 5.6
    spawn(X_EMPTY, {}); spawn(X_HALF, fills["half"]); spawn(X_FULL, fills["full"])
    frame.hide_render = True
    # bunker r4 beside, same scale (its own atlas)
    before = set(bpy.data.objects)
    bpy.ops.wm.obj_import(filepath=os.path.join(ASSETS, "bunker_r4", "Bunker.obj"), forward_axis="NEGATIVE_Z", up_axis="Y",
                          use_split_objects=False, use_split_groups=False)
    bk = [o for o in bpy.data.objects if o not in before][0]; bk.location.x = X_BUNK
    bimg = bpy.data.images.load(os.path.join(ASSETS, "bunker_r4", "bunker_atlas.png"))
    bk.data.materials.clear(); bk.data.materials.append(make_material("bunker", bimg))
    references(chest_x=2.95, post_x=2.0)
    views = {"empty": (-28, 18, 6.6, (X_EMPTY, 0, 0.6), 40),
             "half": (-24, 16, 6.6, (X_HALF, 0, 0.75), 40),
             "full": (-26, 18, 6.6, (X_FULL, 0, 0.75), 40),
             "standing": (-8, 10, 4.2, (X_FULL - 0.3, 0, 1.0), 32),
             "top": (-10, 58, 4.6, (X_FULL, 0, 0.8), 40),
             "post": (-4, 6, 8.0, (X_FULL + 1.4, 0, 0.9), 40),
             "bunker": (-14, 12, 11.5, ((X_FULL + X_BUNK) / 2 + 0.3, 0, 0.9), 38),
             "crate": (-18, 36, 2.3, (0.57, -0.245, DECK + 0.12), 40),
             "bundles": (-12, 22, 2.6, (-0.4, 0.3, 0.75), 40),
             "heads_back": (32, 32, 1.5, (1.45, 0.55, 0.95), 50),
             "heads_front": (-34, 24, 1.3, (-1.45, -0.55, 0.35), 50),
             "heads_staves": (-10, 55, 1.4, (BAR_X[0], BAR_Y, 0.7), 50)}
    lights_and_render(OUT, "fletcher2", views)
    print("DONE", flush=True)
