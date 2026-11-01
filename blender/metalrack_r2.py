"""Metal Rack round 2: the r1 rack style at TRUE SIZE (every bar at scale 1.0), every chest stack visible, in four modules.
Our own furniture mesh and 128x128 point-filtered atlas (palette and helpers imported from metalrack_r1.py); the CONTENTS
are the game's own bar models, laid as real ingot piles: each unit = one pile of 2 bars, long side into the depth.
Run: blender -b -P metalrack_r2.py -- [--out DIR] [--quick] [--views a,b] [--no-render]

True size: a vanilla bar is 0.6226 x 0.3045 x 0.1239 m (ValheimRip/items/Iron/info.json; all bars share one mesh). Every copy
uses fit_longest_m 0.6226 = the bar's own longest side, so the mod's scale is 1.000 for every bar.

Four modules, all one system (Blender x, y, z; -y = front; posts 4 mm inside the bounds, iron post bands flush with them):
  metalrack_r2         whole tall  2.88 W x 0.70 D x 2.40 H   8 shelves x 8 piles = 64 units
  metalrackhalf_r1     half  tall  1.44 W x 0.70 D x 2.40 H   8 shelves x 4 piles = 32 units
  metalracklow_r1      whole low   2.88 W x 0.70 D x 1.20 H   4 shelves x 8 piles = 32 units
  metalracklowhalf_r1  half  low   1.44 W x 0.70 D x 1.20 H   4 shelves x 4 piles = 16 units
The half low module is the cell: a whole module is two halves side by side (double post at the seam), a tall module is two
lows stacked (continuous posts, no deck at the joint). So two lows stacked = one tall and two halves side by side = one
whole, in footprint, post positions, top and bottom faces AND shelf heights (the shelves line up across neighbours).
Why 2.40 and not 2.00 tall: 8 shelves x 2 bars x 0.124 m is 1.98 m of metal alone; with 25 mm planks, 50/45 mm foot and
top rails and 7.7 mm headroom per shelf the minimum is 2.40. Why 1.44 per half: 4 bars side by side are 1.22 m.
MIRRORED: units_data in grid order (index = grid_row * W + grid_col, grid_row 0 = the top shelf, each row left to right
from the front), all units of a shelf at one exact height; the mod's GridOrder (rows of W by position.y descending, each by
position.x descending) gives exactly this order. W = 8 (whole) or 4 (half).
"""
import os, sys, math, json, random
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import bpy
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
import metalrack_r1 as base
from metalrack_r1 import (box, strap, join, clamp_bounds, tris, tri_list, references, lights_and_render, metal_mix, b2u,
                          save_atlas, export_obj, write_json_atomic, build_atlas, make_material, load_bars, place_unit,
                          bar_world, mod_place, TEMPL, argv, arg)

HERE = os.path.dirname(os.path.abspath(__file__))
SCRATCH2 = "C:/Users/joost/AppData/Local/Temp/claude/C--Users-joost--pai/5e4bc60b-cdfe-4638-8e29-2e507fa13cf9/scratchpad/metal2"

# ---------- true-size bars ----------
_i = json.load(open(f"{base.ITEMS_DIR}/Iron/info.json"))
BAR_SIZE = _i["size"]                         # item (x, y, z) = (width, length, thickness) at scale 1
BAR_L, BAR_W, BAR_T = BAR_SIZE[1], BAR_SIZE[0], BAR_SIZE[2]   # 0.6226, 0.3045, 0.1239
FIT_L = round(BAR_L, 4)                        # 0.6226: scale 1.000
LIFT = 0.001
LAYER_DY = BAR_T + LIFT
LAYERS = 2
PILE_H = LIFT + LAYERS * BAR_T + (LAYERS - 1) * LIFT   # 0.2498 above the plank
YAW_J, X_J, Z_J = 0.3, 0.002, 0.004

# ---------- the cell (half low) ----------
WH, D, HL = 1.44, 0.70, 1.20                   # half width, depth, low height
HXH, HY = WH / 2, D / 2
PS, INS = 0.08, 0.004
PX, PY = HXH - INS - PS / 2, HY - INS - PS / 2  # post centres (relative to the cell)
IX, IY = PX - PS / 2, PY - PS / 2               # inner faces of the posts: 0.636, 0.266
RF, RT = 0.05, 0.045                            # foot rail, top rail heights
PT = 0.025                                      # shelf plank thickness
NS = 4                                          # shelves per low
S0 = RF                                         # bottom shelf top = foot rail top (boards flush with the rails)
TOPZ_L = HL - RT                                # 1.155: underside of the top rails
PITCH = (TOPZ_L - S0 + PT) / NS                 # equal headroom on every shelf (and under the top rails)
HEAD = PITCH - PT - PILE_H
PP = (2 * IX - 2 * 0.010 - BAR_W) / 3          # pile pitch across (4 piles, 10 mm end clearance): 0.3158
PILE_XS = [PP * (i - 1.5) for i in range(4)]   # relative to the cell, left to right from the front
YB1 = 0.312                                     # back edge of the shelf boards (back rails behind it)
PILE_Y = -HY + 0.020 + BAR_L / 2                # pile front edge 20 mm behind the front face

MODULES = {
    "metalrack_r2":        {"name": "MetalRack",        "title": "Metal Rack",            "cols": 2, "tiers": 2, "round": 2},
    "metalrackhalf_r1":    {"name": "MetalRackHalf",    "title": "Metal Rack (half)",     "cols": 1, "tiers": 2, "round": 1},
    "metalracklow_r1":     {"name": "MetalRackLow",     "title": "Low Metal Rack",        "cols": 2, "tiers": 1, "round": 1},
    "metalracklowhalf_r1": {"name": "MetalRackLowHalf", "title": "Low Metal Rack (half)", "cols": 1, "tiers": 1, "round": 1},
}

def cell_xs(cols): return [0.0] if cols == 1 else [-HXH, HXH]
def shelf_tops(tiers): return [t * HL + S0 + k * PITCH for t in range(tiers) for k in range(NS)]

def build_frame(cols, tiers):
    H = tiers * HL
    for xo in cell_xs(cols):
        # continuous corner posts, bands flush with the bounds (each tier's bands = the low module's)
        bands = [b for t in range(tiers) for b in ((t * HL + 0.012, 0.05), (t * HL + HL / 2 - 0.025, 0.05), (t * HL + HL - 0.062, 0.05))]
        for sx in (-1, 1):
            for sy in (-1, 1):
                box("post", (PS, PS, H), (xo + sx * PX, sy * PY, H / 2), jitter=0.002, bevel=0.012)
                for z0, h in bands:
                    box("band", (PS + 2 * INS, PS + 2 * INS, h), (xo + sx * PX, sy * PY, z0 + h / 2), kind="iron", jitter=0, bevel=0.003)
        for t in range(tiers):
            zo = t * HL
            # foot frame (its top is the bottom shelf) and top frame
            for z0, rh in ((zo, RF), (zo + HL - RT, RT)):
                for sy in (-1, 1):
                    box("rail", (2 * IX + 0.02, PS, rh), (xo, sy * PY, z0 + rh / 2), jitter=0.0, bevel=0.008)
                for sx in (-1, 1):
                    box("rail", (PS, 2 * IY + 0.02, rh), (xo + sx * PX, 0, z0 + rh / 2), jitter=0.0, bevel=0.008)
            # bottom shelf: boards flush with the foot rails, on three bearers on the floor (or on the joint below)
            for x in (-0.42, 0.0, 0.42):
                box("bearer", (0.05, 2 * IY, RF - PT), (xo + x, 0, zo + (RF - PT) / 2), jitter=0.0, bevel=0.005)
            bw = 2 * IY / 3
            for i in range(3):
                box("shelf", (2 * IX, bw - 0.005, PT), (xo, -IY + bw * (i + 0.5), zo + RF - PT / 2), kind="plank", jitter=0.0, bevel=0.005)
            # upper shelves: 3 sawn planks on cleats between the posts, iron edge strip on the front
            pw = (YB1 - (-HY + INS)) / 3
            for k in range(1, NS):
                s = zo + S0 + k * PITCH
                for i in range(3):
                    box("shelf", (2 * IX + 0.06, pw - 0.005, PT), (xo, -HY + INS + pw * (i + 0.5), s - PT / 2), kind="plank", jitter=0.0, bevel=0.005)
                for sx in (-1, 1):
                    box("cleat", (0.045, 2 * IY, 0.035), (xo + sx * (IX + 0.03), 0, s - PT - 0.0175), jitter=0.0, bevel=0.006)
                box("edge", (2 * IX - 0.01, 0.006, 0.02), (xo, -HY + 0.003, s - 0.0125), kind="iron", jitter=0, bevel=0.002)
                for x in (-PP, 0.0, PP):
                    box("nail", (0.02, 0.006, 0.02), (xo + x, -HY + 0.003, s - 0.0125), kind="iron", jitter=0, bevel=0.003)
            # back: two timber rails and an X strap; sides: an X strap each
            for z in (0.40, 0.80):
                box("backrail", (2 * IX, 0.028, 0.06), (xo, 0.328, zo + z), jitter=0.002, bevel=0.008)
            za, zb = zo + RF, zo + HL - RT
            strap("xb", (xo - IX, za), (xo + IX, zb), "xz", HY - 0.006, thick=0.004)
            strap("xb", (xo - IX, zb), (xo + IX, za), "xz", HY - 0.002, thick=0.004)
            for sx in (-1, 1):
                strap("xs", (-IY, za), (IY, zb), "yz", xo + sx * (HXH - 0.006), thick=0.004)
                strap("xs", (-IY, zb), (IY, za), "yz", xo + sx * (HXH - 0.002), thick=0.004)
        # deck on top keeps the rain off the top shelf (only at the very top: no deck at the joint of a tall module)
        dw = 2 * IY / 3
        for i in range(3):
            box("deck", (2 * IX, dw - 0.006, 0.03), (xo, -IY + dw * (i + 0.5), H - 0.008 - 0.015), kind="plank", jitter=0.0, bevel=0.005)

def pile_copies(seed):
    r = random.Random(seed)
    out = []
    for j in range(LAYERS):
        yaw = r.uniform(-YAW_J, YAW_J) + (180.0 if j == 1 and r.random() < 0.5 else 0.0)
        off = [r.uniform(-X_J, X_J), j * LAYER_DY, r.uniform(-Z_J, Z_J)]
        q = [0.0, math.sin(math.radians(yaw) / 2), 0.0, math.cos(math.radians(yaw) / 2)]
        out.append({"layer": j, "offset": [round(a, 5) for a in off], "longest_m": FIT_L, "anchor": "bottom",
                    "align": {"long_axis_to": [0, 0, 1], "thin_axis_to": [0, 1, 0],
                              "then_rotate_euler_zxy": [0.0, round(yaw, 3), 0.0], "then_rotate_quat_xyzw": [round(a, 6) for a in q]}})
    return out

def module_units(cols, tiers):
    xs = sorted(xo + px for xo in cell_xs(cols) for px in PILE_XS)    # Blender x ascending = left to right from the front
    Wn = len(xs)
    tops = shelf_tops(tiers)
    units = []
    for k, s in enumerate(reversed(tops)):                               # grid_row 0 = top shelf
        for col, x in enumerate(xs):
            idx = k * Wn + col
            units.append({"index": idx, "grid_row": k, "grid_col": col, "shelf_from_bottom": len(tops) - 1 - k,
                          "position": [round(a, 5) for a in b2u((x, PILE_Y, s + LIFT))], "rotation": [0.0, 0.0, 0.0],
                          "box_size": [round(BAR_W, 4), round(PILE_H - LIFT, 4), round(BAR_L, 4)], "render_item": "Copper",
                          "copies": pile_copies(7000 + 131 * cols + 17 * tiers + idx)})
    return units, Wn

def grid_order_ok(units, Wn):
    P = [u["position"] for u in units]
    by_h = sorted(range(len(units)), key=lambda i: -P[i][1])
    order = []
    for r in range(len(units) // Wn):
        order += sorted(by_h[r * Wn:(r + 1) * Wn], key=lambda i: (-P[i][0], -P[i][2]))
    heights_ok = all(len({round(P[i][1], 6) for i in range(r * Wn, (r + 1) * Wn)}) == 1 for r in range(len(units) // Wn))
    return order == list(range(len(units))) and heights_ok

def checks(units, frame, inner, top_limit):
    """Clip (bar vs frame triangles), overlaps (bar vs bar, BVH, any pair within 0.8 m), containment. Copper and BlackMetal."""
    V, T = tri_list(frame.data)
    fbvh = BVHTree.FromPolygons(V, T, all_triangles=True)
    res = {}
    for it in ("Copper", "BlackMetal"):
        bars = []
        scales = set()
        for u in units:
            for k, M in enumerate(place_unit(u, it)):
                W = bar_world(M, it)
                scales.add(round(float(np.linalg.norm(np.array(M)[:3, 0])), 5))
                bars.append((u["index"], k, W, BVHTree.FromPolygons([Vector(w) for w in W], TEMPL[it]["tris"])))
        clip = [(a, k) for a, k, W, b in bars if fbvh.overlap(b)]
        C = np.array([W.mean(0) for _, _, W, _ in bars])
        pairs = 0
        for i in range(len(bars)):
            near = np.nonzero(np.linalg.norm(C - C[i], axis=1) < 0.8)[0]
            for j in near[near > i]:
                if bars[i][3].overlap(bars[j][3]): pairs += 1
        lo = np.min([W.min(0) for *_, W, _ in bars], 0); hi = np.max([W.max(0) for *_, W, _ in bars], 0)
        out = int(lo[0] < inner[0] or hi[0] > inner[1] or lo[1] < inner[2] or hi[1] > inner[3] or hi[2] > top_limit)
        # minimum gap between neighbouring piles across (x) and headroom under the next plank
        res[it] = {"copies": len(bars), "bar_scale": sorted(scales), "clipping": len(clip), "bar_overlaps": pairs, "outside_inner_box": out,
                   "contents_x": [round(lo[0], 4), round(hi[0], 4)], "contents_y": [round(lo[1], 4), round(hi[1], 4)],
                   "contents_top_z": round(float(hi[2]), 4), "top_limit_z": round(top_limit, 4)}
        print("CHECK", it, json.dumps(res[it]), "clip list", clip[:10])
    return res

def spawn2(units, fill_items, dx, dz, frame):
    fr = frame.copy(); bpy.context.scene.collection.objects.link(fr); fr.hide_render = False
    fr.location = (dx, 0, dz)
    for u, it in zip(units, fill_items):
        if not it: continue
        for k, M in enumerate(place_unit(u, it)):
            ob = bpy.data.objects.new(f"u{u['index']:02d}_{k}", TEMPL[it]["mesh"])
            bpy.context.scene.collection.objects.link(ob)
            ob.matrix_world = Matrix.Translation((dx, 0, dz)) @ M
    return fr

if __name__ == "__main__":
    OUT = arg("--out", SCRATCH2)
    os.makedirs(OUT, exist_ok=True)
    base.setup_scene()
    atlas = build_atlas("metalrack_atlas", OUT)
    base.MAT = make_material("metalrack", atlas)
    load_bars()
    print(f"TRUE SIZE bar L {BAR_L} W {BAR_W} T {BAR_T}; pitch {PITCH:.4f} headroom {HEAD:.4f} pile pitch {PP:.4f} "
          f"gap {PP - BAR_W:.4f} pile y {PILE_Y:.4f}")
    built = {}
    for slug, m in MODULES.items():
        base.PARTS.clear()
        cols, tiers = m["cols"], m["tiers"]
        W, H = cols * WH, tiers * HL
        build_frame(cols, tiers)
        frame = join(list(base.PARTS), m["name"])
        clamp_bounds(frame, W / 2, HY, H)
        frame.hide_render = True
        bb = np.array([tuple(v.co) for v in frame.data.vertices])
        units, Wn = module_units(cols, tiers)
        gok = grid_order_ok(units, Wn)
        chk = checks(units, frame, (-W / 2 + PS + INS, W / 2 - PS - INS, -HY, YB1), H - RT)
        built[slug] = (frame, units, W, H)
        print("FRAME", slug, "tris", tris(frame), "bounds", bb.min(0).round(4), bb.max(0).round(4), "units", len(units), "grid ok", gok)
        outa = os.path.normpath(os.path.join(HERE, "..", "assets", slug))
        os.makedirs(outa, exist_ok=True)
        save_atlas(atlas, os.path.join(outa, f"{slug.split('_')[0]}_atlas.png"))
        export_obj(frame, os.path.join(outa, f"{m['name']}.obj"))
        post_xs = sorted(round(-(xo + sx * PX), 4) for xo in cell_xs(cols) for sx in (-1, 1))
        doc = {
            "schema": "storehouse-anchors/1", "furniture": m["title"], "slug": slug.split("_")[0], "round": m["round"],
            "unit_count": len(units), "slots_designed_for": len(units), "stack_per_unit": True, "mirror": True, "row_width": Wn,
            "frame": {"obj": f"{m['name']}.obj", "atlas": f"{slug.split('_')[0]}_atlas.png 128x128 point", "tris": tris(frame),
                      "size_m": [W, H, D], "bounds_unity": {"min": [-W / 2, 0.0, -HY], "max": [W / 2, H, HY]},
                      "post_centres_unity_x": post_xs, "post_centres_unity_z": [-PY, PY],
                      "modular": "cell = the half low module (1.44 x 1.20 x 0.70). Whole = two halves side by side, tall = two lows stacked: "
                                 "same footprint, post positions, flat top and foot, and shelf heights. Posts 4 mm inside the bounds, iron "
                                 "bands flush with them, so the mod's bounding-box corner snap points stack and line up any two modules.",
                      "shelf_tops_y": [round(s, 4) for s in shelf_tops(tiers)], "contents_top_limit_y": round(H - RT, 4)},
            "space": {"unity": "prefab space, origin on the floor at the centre of the footprint, +z front, +y up, +x to the furniture's left seen from the front",
                      "from_blender": "ux=-bx, uy=bz, uz=-by"},
            "fill_order": f"MIRROR grid order: index = grid_row * {Wn} + grid_col; grid_row 0 = the top shelf; each row left to right seen from "
                          f"the front. All {Wn} units of a shelf share one position.y, so the mod's GridOrder (rows of {Wn} by position.y "
                          "descending, each by position.x descending) gives exactly this order.",
            "position": "unit position = bottom centre of its pile, 1 mm over the shelf top. box_size = [x, y, z] Unity, informational.",
            "copy_rule": f"Each copy = one bar at TRUE SIZE: align (long axis -> +z, into the depth; thin axis -> up), then_rotate (a little "
                         f"yaw, the top bar sometimes turned end for end), fit_longest_m {FIT_L} = the vanilla bar's own longest side, so "
                         f"scale 1.000; anchor bottom. Layer j sits at offset.y = j * {LAYER_DY:.4f} m. 2 bars per unit, bottom first.",
            "items": {"all_bars": {"bounds_size_unity": [BAR_W, BAR_T, BAR_L], "longest_m": FIT_L, "scale": 1.0,
                                   "source": "ValheimRip/items/Iron/info.json size [0.3045, 0.6226, 0.1239]",
                                   "note": "Copper, Tin, Bronze, Iron, Silver, BlackMetal, Flametal and FlametalNew share one 44-triangle bar mesh"}},
            "layout": {"shelves": len(shelf_tops(tiers)), "piles_per_shelf": Wn, "shelf_pitch_m": round(PITCH, 4),
                       "headroom_per_shelf_m": round(HEAD, 4), "pile_pitch_x_m": round(PP, 4), "pile_gap_x_m": round(PP - BAR_W, 4),
                       "layers_per_pile": LAYERS, "bars_per_unit": LAYERS},
            "checks": {"grid_mirror_order_ok": gok, **chk},
            "units_data": units}
        write_json_atomic(doc, os.path.join(outa, f"{m['name']}Anchors.json"))   # last: the mod live-reloads
        print("WROTE", outa)
    # modular equality: two lows stacked = tall, two halves side by side = whole (bounds and post positions)
    print("MODULAR shelf tops tall", [round(s, 4) for s in shelf_tops(2)], "low", [round(s, 4) for s in shelf_tops(1)])
    if "--no-render" in argv: sys.exit(0)

    mix = lambda n: metal_mix(n)
    order = ["metalrack_r2", "metalrackhalf_r1", "metalracklow_r1", "metalracklowhalf_r1"]
    def lineup(x0, full):
        x = x0
        for slug in order:
            fr, units, W, H = built[slug]
            x += W / 2
            spawn2(units, mix(len(units)) if full else [None] * len(units), x, 0, fr)
            x += W / 2 + 0.5
        return x
    lineup(0.0, True)          # full: whole tall, half tall, whole low, half low, 0.5 m apart
    lineup(20.0, False)        # empty
    fr, units, W, H = built["metalrack_r2"]
    spawn2(units, [mix(64)[j] if j < 32 else None for j in range(64)], -6.0, 0, fr)    # 50 %: the top four shelves
    # combo wall, every piece flush with its neighbour: whole tall | two half lows stacked | half tall | two whole lows stacked
    X = -20.0
    def put(slug, xl, z, fill=True):
        fr, units, W, H = built[slug]
        spawn2(units, mix(len(units)) if fill else [None] * len(units), xl + W / 2, z, fr)
        return xl + W
    xr = put("metalrack_r2", X, 0)
    put("metalracklowhalf_r1", xr, 0); xr = put("metalracklowhalf_r1", xr, HL, fill=False)
    xr = put("metalrackhalf_r1", xr, 0)
    put("metalracklow_r1", xr, 0, fill=False); xr = put("metalracklow_r1", xr, HL)
    references(chest_x=-1.1, post_x=-2.1)
    views = {"full": (-4, 10, 17.5, (4.6, 0, 1.1), 38), "empty": (-4, 10, 17.5, (24.6, 0, 1.1), 38),
             "half50": (-12, 10, 7.0, (-6.0, 0, 1.2), 40), "combo": (-6, 12, 15.0, (X + 4.32, 0, 1.2), 36),
             "close": (-22, 10, 4.6, (-0.5, 0, 0.8), 40), "side": (52, 14, 6.0, (1.44, 0, 1.2), 40)}
    lights_and_render(OUT, "metalrack2", views)
    print("DONE")
