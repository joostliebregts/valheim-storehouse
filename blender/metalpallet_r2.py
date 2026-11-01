"""Metal Pallet round 2: the r1 pallet look at TRUE SIZE (every bar at scale 1.0), every chest stack visible.
Our own furniture mesh and 128x128 point-filtered atlas (palette and helpers from metalrack_r1.py, true-size bar numbers
and the checks from metalrack_r2.py); the CONTENTS are the game's own bar models, laid as a real stacked pallet of ingots.
Run: blender -b -P metalpallet_r2.py -- [--out DIR] [--quick] [--views a,b] [--no-render]

True size: a vanilla bar is 0.6226 x 0.3045 x 0.1239 m; every copy uses fit_longest_m 0.6226, so the mod's scale is 1.000.

Frame 2.74 W x 1.35 D x 1.20 H (Blender x, y, z; -y = front): a heavy timber pallet (three runners, five bearers, deck at
0.13), four load-bearing corner posts with iron bands flush with the bounds (posts 4 mm inside), a flat top frame at 1.20
with an iron band round it, iron X straps on the back and sides, open front. 1.20 H = the low Metal Rack, so two pallets
stacked are as tall as the tall rack.
64 units = 4 tiers x 16 piles; a pile = one stack = 2 bars on top of each other. The tiers alternate the bar direction like
a real ingot stack: tiers 0 and 2 = 8 across x 2 deep with the bars along the depth, tiers 1 and 3 = 4 across x 4 deep with
the bars along the width. Both grids fill the same 2.526 x 1.257 m block, so every tier rests on the one below (each upper
pile lies across two or more piles under it). Contents top 1.129, top frame underside 1.14.
NOT mirrored: units are listed in FILL ORDER, the n-th stack goes to unit n: lowest tier first, per tier the back row then
the front, each row left to right seen from the front. A tier is complete before the next starts, so nothing floats (only a
partly full stack under the next tier shows 1 bar instead of 2, the mod's rule for partial stacks).
"""
import os, sys, math, json, random
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import bpy
import metalrack_r1 as base
import metalrack_r2 as rack
from metalrack_r1 import (box, strap, corner_posts, join, clamp_bounds, tris, references, lights_and_render, metal_mix, b2u,
                          save_atlas, export_obj, write_json_atomic, build_atlas, make_material, load_bars, argv, arg)
from metalrack_r2 import BAR_L, BAR_W, BAR_T, FIT_L, LIFT, LAYER_DY, checks, spawn2

SCRATCHP = "C:/Users/joost/AppData/Local/Temp/claude/C--Users-joost--pai/5e4bc60b-cdfe-4638-8e29-2e507fa13cf9/scratchpad/pallet2"
YAW_J, LAT_J, LON_J = 0.3, 0.002, 0.004       # hand-laid jitter: degrees of yaw, metres across / along the bar

# ---------- the stack block ----------
G = 0.012                                     # gap between piles (the short-side grid)
NT, LAYERS = 4, 2                             # tiers, bars per pile
SPAN_X = 4 * BAR_L + 3 * G                    # 2.5264: 4 bars end to end across = 8 bars side by side
SPAN_Y = 2 * BAR_L + G                        # 1.2572: 2 bars end to end deep = 4 bars side by side
GX = (SPAN_X - 8 * BAR_W) / 7                 # 0.0129
GY = (SPAN_Y - 4 * BAR_W) / 3                 # 0.0131

# ---------- the frame ----------
PS, INS = 0.09, 0.004
W, D, H = 2.74, 1.35, 1.20
HX, HY = W / 2, D / 2
IX = HX - INS - PS                            # 1.276: inner face of the posts (contents span +-1.2632)
DECK = 0.13                                   # top of the deck boards
RH = 0.06                                     # top rail height
TOPZ = H - RH                                 # 1.14: underside of the top frame
FM = 0.015                                    # contents' front edge behind the front face
YC = -HY + FM + SPAN_Y / 2                    # centre of the block in y
BACKIN = HY - 0.049                           # inner face of the back rail
MIDZ = (DECK + TOPZ) / 2

def build_pallet():
    PX, PY = corner_posts(HX, HY, H, PS, INS, bands=[(0.015, 0.06), (MIDZ - 0.03, 0.06), (H - 0.065, 0.06)])
    IY = PY - PS / 2
    # pallet: three runners along x (full length: in a stack their ends rest on the side top rails below), five bearers, seven boards
    for y in (-0.50, 0.0, 0.50):
        box("runner", (2 * HX, 0.13, 0.075), (0, y, 0.0375), jitter=0.003, bevel=0.014)
    for x in (-1.0, -0.5, 0.0, 0.5, 1.0):
        box("bearer", (0.11, 2 * HY - 2 * INS, 0.025), (x, 0, 0.0875), kind="plank", jitter=0.002, bevel=0.007)
    nb = 7; bw = (2 * HY - 2 * INS) / nb
    for i in range(nb):
        box("deck", (2 * IX, bw - 0.008, 0.03), (0, -HY + INS + bw * (i + 0.5), DECK - 0.015), kind="plank", jitter=0.0, bevel=0.006)
    for sy in (-1, 1):                         # iron edge strips on the deck's front and back edges
        box("edge", (2 * IX - 0.01, 0.005, 0.026), (0, sy * (HY - 0.0025), DECK - 0.015), kind="iron", jitter=0, bevel=0.002)
    # top frame, flat at H, with an iron band on its outer faces
    for sy in (-1, 1):
        box("toprail", (2 * IX + 0.02, PS, RH), (0, sy * PY, H - RH / 2), jitter=0.002, bevel=0.01)
        box("topband", (2 * IX, 0.004, 0.035), (0, sy * (HY - 0.002), H - RH / 2), kind="iron", jitter=0, bevel=0.0015)
    for sx in (-1, 1):
        box("toprail", (PS, 2 * IY + 0.02, RH), (sx * PX, 0, H - RH / 2), jitter=0.002, bevel=0.01)
        box("topband", (0.004, 2 * IY, 0.035), (sx * (HX - 0.002), 0, H - RH / 2), kind="iron", jitter=0, bevel=0.0015)
    # back: a mid rail and two X straps; sides: a mid rail and an X strap each
    box("backrail", (2 * IX, 0.045, 0.08), (0, HY - INS - 0.0225, MIDZ), jitter=0.002, bevel=0.008)
    for xa, xb in ((-IX, 0.0), (0.0, IX)):
        strap("xb", (xa, DECK), (xb, TOPZ), "xz", HY - 0.006, thick=0.004)
        strap("xb", (xa, TOPZ), (xb, DECK), "xz", HY - 0.002, thick=0.004)
    for sx in (-1, 1):
        box("siderail", (0.06, 2 * IY, 0.08), (sx * (HX - INS - 0.035), 0, MIDZ), jitter=0.002, bevel=0.008)
        strap("xs", (-IY, DECK), (IY, TOPZ), "yz", sx * (HX - 0.006), thick=0.004)
        strap("xs", (-IY, TOPZ), (IY, DECK), "yz", sx * (HX - 0.002), thick=0.004)

def pile_copies(seed, along_x):
    r = random.Random(seed)
    out = []
    for j in range(LAYERS):
        yaw = r.uniform(-YAW_J, YAW_J) + (180.0 if j == 1 and r.random() < 0.5 else 0.0)
        lat, lon = r.uniform(-LAT_J, LAT_J), r.uniform(-LON_J, LON_J)
        off = [lon, j * LAYER_DY, lat] if along_x else [lat, j * LAYER_DY, lon]
        q = [0.0, math.sin(math.radians(yaw) / 2), 0.0, math.cos(math.radians(yaw) / 2)]
        out.append({"layer": j, "offset": [round(a, 5) for a in off], "longest_m": FIT_L, "anchor": "bottom",
                    "align": {"long_axis_to": [1, 0, 0] if along_x else [0, 0, 1], "thin_axis_to": [0, 1, 0],
                              "then_rotate_euler_zxy": [0.0, round(yaw, 3), 0.0], "then_rotate_quat_xyzw": [round(a, 6) for a in q]}})
    return out

def tier_grid(t):
    """(along_x, [(row_from_back, col_from_left, bx, by)]) for tier t, back row first, each row left to right from the front."""
    if t % 2 == 0:   # bars along the depth: 8 across x 2 deep
        xs = [(i - 3.5) * (BAR_W + GX) for i in range(8)]
        ys = [YC + (BAR_L + G) / 2, YC - (BAR_L + G) / 2]
        return False, [(r, c, x, y) for r, y in enumerate(ys) for c, x in enumerate(xs)]
    xs = [(i - 1.5) * (BAR_L + G) for i in range(4)]     # bars along the width: 4 across x 4 deep
    ys = [YC + (1.5 - j) * (BAR_W + GY) for j in range(4)]
    return True, [(r, c, x, y) for r, y in enumerate(ys) for c, x in enumerate(xs)]

def pallet_units():
    units = []
    for t in range(NT):
        along_x, cells = tier_grid(t)
        z = DECK + LIFT + t * LAYERS * LAYER_DY
        for r, c, x, y in cells:
            idx = len(units)
            units.append({"index": idx, "tier": t, "row_from_back": r, "col_from_left": c, "bars_along": "width" if along_x else "depth",
                          "position": [round(a, 5) for a in b2u((x, y, z))], "rotation": [0.0, 0.0, 0.0],
                          "box_size": [round(BAR_L if along_x else BAR_W, 4), round(LAYERS * BAR_T + (LAYERS - 1) * LIFT, 4),
                                       round(BAR_W if along_x else BAR_L, 4)],
                          "render_item": "Iron", "copies": pile_copies(9100 + 37 * idx, along_x)})
    return units

def support_check(units):
    """Every upper pile rests on piles of the tier below that come earlier in the fill order: min supported area fraction."""
    def rect(u):
        x, z = u["position"][0], u["position"][2]; sx, sz = u["box_size"][0], u["box_size"][2]
        return x - sx / 2, x + sx / 2, z - sz / 2, z + sz / 2
    worst, min_under, order_ok = 1.0, 99, True
    for u in units:
        if u["tier"] == 0: continue
        a = rect(u); area = (a[1] - a[0]) * (a[3] - a[2]); cov = 0.0; n = 0
        for v in units:
            if v["tier"] != u["tier"] - 1: continue
            b = rect(v)
            ox = max(0.0, min(a[1], b[1]) - max(a[0], b[0])); oz = max(0.0, min(a[3], b[3]) - max(a[2], b[2]))
            if ox * oz > 0:
                cov += ox * oz; n += 1
                order_ok &= v["index"] < u["index"]
        worst = min(worst, cov / area); min_under = min(min_under, n)
    # each tier's bottom = the top of the bars under it + LIFT
    zs = sorted({round(u["position"][1], 5) for u in units})
    steps = [round(b - a, 5) for a, b in zip(zs, zs[1:])]
    res = {"min_supported_area_fraction": round(worst, 3), "min_piles_under_an_upper_pile": min_under,
           "supports_fill_before": order_ok, "tier_bottoms_y": zs, "tier_steps_m": steps}
    print("SUPPORT", json.dumps(res))
    return res

def fill_order_ok(units):
    """Fill order: tier ascending, then the back row first (Unity -z = back), then left to right from the front (Unity x descending)."""
    key = [(u["tier"], round(u["position"][2], 5), -u["position"][0]) for u in units]
    return key == sorted(key)

if __name__ == "__main__":
    OUTA = os.path.normpath(os.path.join(base.HERE, "..", "assets", "metalpallet_r2"))
    OUT = arg("--out", SCRATCHP)
    os.makedirs(OUTA, exist_ok=True); os.makedirs(OUT, exist_ok=True)
    base.setup_scene()
    atlas = build_atlas("metalpallet_atlas", OUTA)
    base.MAT = make_material("metalpallet", atlas)
    load_bars()
    base.PARTS.clear()
    build_pallet()
    frame = join(list(base.PARTS), "MetalPallet")
    clamp_bounds(frame, HX, HY, H)
    ftris = tris(frame)
    bb = np.array([tuple(v.co) for v in frame.data.vertices])
    print(f"PALLET W {W} D {D} H {H} tris {ftris} bounds {bb.min(0).round(4)} {bb.max(0).round(4)}; span {SPAN_X:.4f} x {SPAN_Y:.4f} "
          f"gx {GX:.4f} gy {GY:.4f} contents top {DECK + LIFT + NT * LAYERS * LAYER_DY - LIFT:.4f} topz {TOPZ}")
    units = pallet_units()
    chk = checks(units, frame, (-IX, IX, -HY, BACKIN), TOPZ)
    sup = support_check(units)
    fok = fill_order_ok(units)
    print("FILL ORDER ok", fok)
    save_atlas(atlas, os.path.join(OUTA, "metalpallet_atlas.png"))
    export_obj(frame, os.path.join(OUTA, "MetalPallet.obj"))
    doc = {
        "schema": "storehouse-anchors/1", "furniture": "Metal Pallet", "slug": "metalpallet", "round": 2,
        "unit_count": len(units), "slots_designed_for": 64, "stack_per_unit": True, "mirror": False,
        "frame": {"obj": "MetalPallet.obj", "atlas": "metalpallet_atlas.png 128x128 point", "tris": ftris, "size_m": [W, H, D],
                  "bounds_unity": {"min": [-HX, 0.0, -HY], "max": [HX, H, HY]},
                  "stacking": f"four corner posts carry the load; flat top at y={H} and flat foot at y=0; the outer box is exactly the bounds "
                              "(iron post bands flush with it, posts 4 mm inside), so bounding-box corner snap points stack one pallet on another; "
                              "the runners run the full width and rest on the side top rails of the pallet below. 1.20 high = the low Metal Rack: "
                              f"two pallets stacked are as tall as the tall rack. Contents stay inside the posts and below the top frame (y < {TOPZ})."},
        "space": {"unity": "prefab space, origin on the floor at the centre of the footprint, +z front, +y up, +x to the furniture's left seen from the front",
                  "from_blender": "ux=-bx, uy=bz, uz=-by"},
        "fill_order": "NOT mirrored: units are listed in fill order, the n-th stack goes to unit n. Lowest tier first (units 0-15 tier 0, "
                      "16-31 tier 1, 32-47 tier 2, 48-63 tier 3); per tier the back row then the front, each row left to right seen from "
                      "the front. A tier is full before the next one starts, so nothing floats. Leave mirror off for this store.",
        "position": "unit position = bottom centre of its pile, 1 mm over the deck (tier 0) or over the top bar of the tier below. "
                    "box_size = [x, y, z] Unity, informational.",
        "copy_rule": f"Each copy = one bar at TRUE SIZE: align (long axis -> +z on tiers 0 and 2, into the depth; -> +x on tiers 1 and 3, "
                     f"across; thin axis -> up), then_rotate (a little yaw, the top bar sometimes turned end for end), fit_longest_m {FIT_L} "
                     f"= the vanilla bar's own longest side, so scale 1.000; anchor bottom. Layer j sits at offset.y = j * {LAYER_DY:.4f} m. "
                     "2 bars per unit, bottom first.",
        "items": {"all_bars": {"bounds_size_unity": [BAR_W, BAR_T, BAR_L], "longest_m": FIT_L, "scale": 1.0,
                               "source": "ValheimRip/items/Iron/info.json size [0.3045, 0.6226, 0.1239]",
                               "note": "Copper, Tin, Bronze, Iron, Silver, BlackMetal, Flametal and FlametalNew share one 44-triangle bar mesh"}},
        "layout": {"tiers": NT, "piles_per_tier": 16, "layers_per_pile": LAYERS, "bars_per_unit": LAYERS,
                   "tiers_0_2": "8 across x 2 deep, bars along the depth", "tiers_1_3": "4 across x 4 deep, bars along the width",
                   "block_m": [round(SPAN_X, 4), round(SPAN_Y, 4)], "pile_gap_m": [round(GX, 4), G, round(GY, 4)],
                   "deck_top_y": DECK, "contents_top_y_full": round(DECK + NT * LAYERS * LAYER_DY, 4), "top_frame_underside_y": TOPZ},
        "checks": {"fill_order_ok": fok, "support": sup, **chk},
        "units_data": units}
    write_json_atomic(doc, os.path.join(OUTA, "MetalPalletAnchors.json"))   # last: the mod live-reloads
    print("WROTE", OUTA)
    if "--no-render" in argv: sys.exit(0)

    SP = W + 0.6
    mix = metal_mix(64)
    for i, n in enumerate((64, 32, 0)):                             # full, 50 %, empty, left to right
        spawn2(units, [mix[j] if j < n else None for j in range(64)], i * SP, 0, frame)
    XS = 3 * SP + 0.4                                               # two full pallets stacked
    spawn2(units, mix, XS, 0, frame); spawn2(units, mix, XS, H, frame)
    # next to the tall Metal Rack r2 (full), with one pallet and a stack of two
    XR = -22.0
    base.PARTS.clear()
    rack.build_frame(2, 2)
    rframe = join(list(base.PARTS), "MetalRack"); clamp_bounds(rframe, rack.WH, rack.HY, 2 * rack.HL); rframe.hide_render = True
    runits, _ = rack.module_units(2, 2)
    spawn2(runits, metal_mix(64), XR + rack.WH, 0, rframe)
    spawn2(units, mix, XR + 2 * rack.WH + 0.6 + HX, 0, frame)
    xs2 = XR + 2 * rack.WH + 1.2 + W + HX
    spawn2(units, mix, xs2, 0, frame); spawn2(units, [mix[j] if j < 40 else None for j in range(64)], xs2, H, frame)
    frame.hide_render = True
    references(chest_x=-HX - 1.1, post_x=-HX - 2.1)
    views = {"fills": (-4, 20, 16.0, (SP - 1.0, 0, 0.5), 34), "close": (-24, 20, 6.0, (-1.4, 0, 0.6), 40),
             "front": (0, 8, 4.6, (0, 0, 0.6), 40), "top50": (18, 42, 5.2, (SP, 0, 0.5), 40),
             "stack": (-34, 16, 6.6, (XS, 0, 1.2), 40), "rack": (-8, 10, 13.0, (XR + 4.6, 0, 1.2), 36)}
    lights_and_render(OUT, "metalpallet2", views)
    print("DONE")
