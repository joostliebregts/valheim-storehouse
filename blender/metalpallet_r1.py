"""Metal Pallet round 1: WIDE AND LOW outdoor mass storage for metal bars, on the ground, stackable like crates.
Our own furniture mesh and own 128x128 point-filtered atlas (same palette and helpers as metalrack_r1.py, imported from
it); the CONTENTS are the game's own bar models laid as real ingot piles, 2 bars per layer, crosswise layers.
Run: blender -b -P metalpallet_r1.py -- [--out DIR] [--quick] [--views a,b] [--no-render]

Frame 2.28 W x 1.20 D x 0.80 H (Blender x, y, z; -y = front): a heavy pallet (runners, bearers, deck at 0.18), four
load-bearing corner posts, a flat top frame at 0.80 with an iron band round it, iron X straps on the back and sides, open
front. The outer box is a clean rectangle (post bands flush with the bounds, posts 4 mm inside), so the mod's bounding-box
corner snap points stack one pallet on another; contents stay inside the posts and below the top frame (z < 0.73).
64 units = 32 pile footprints (8 across x 4 deep, 0.258 m pitch) x 2 tiers: each footprint is one pile of 10 layers,
the lower unit = layers 0-4, the upper unit = layers 5-9 on top of it (5 layers x 2 bars = 10 bars per unit).
NOT mirrored (the mod's mirror sort is by height rows, which a flat pallet can't give): units are listed in FILL ORDER,
pile by pile: footprints from the back row to the front, each row left to right seen from the front, and per footprint
the lower unit then the upper one (unit 2k+1 lies on unit 2k). A pile grows to full height before the next starts, so a
run of one metal in the chest makes whole single-metal piles, and an upper unit never floats (the mod fills units 0..n-1).
"""
import os, sys, math, json
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import bpy
import metalrack_r1 as base
from metalrack_r1 import (box, strap, corner_posts, join, clamp_bounds, tris, run_checks, spawn, references, lights_and_render,
                          metal_mix, pile_copies, b2u, save_atlas, export_obj, write_json_atomic, build_atlas, make_material, load_bars,
                          BAR, BAR_L, PILE, LAYER_DY, argv, arg, SCRATCH)

W, D, H = 2.28, 1.20, 0.80
HX, HY = W / 2, D / 2
PS, INS = 0.10, 0.004
DECK = 0.18                      # top of the deck boards
TOPZ = 0.73                      # underside of the top frame
PITCH = 0.258
COLS_X = [PITCH * (i - 3.5) for i in range(8)]      # Blender x, left to right seen from the front
ROWS_Y = [PITCH * (1.5 - j) for j in range(4)]      # Blender y, back row first (+y = back)
LAYERS = 5                                           # per unit; a footprint holds 2 units = 10 layers

def build_pallet():
    PX, PY = corner_posts(HX, HY, H, PS, INS, bands=[(0.02, 0.07), (0.40, 0.06), (0.735, 0.06)])
    IX, IY = PX - PS / 2, PY - PS / 2
    # pallet: three runners along x, four bearers along y, six deck boards along x
    for y in (-0.42, 0.0, 0.42):   # full length: in a stack their ends rest on the side top rails of the pallet below
        box("runner", (2 * HX, 0.13, 0.10), (0, y, 0.05), jitter=0.003, bevel=0.014)
    for x in (-0.78, -0.26, 0.26, 0.78):
        box("bearer", (0.11, 2 * HY - 2 * INS, 0.04), (x, 0, 0.12), kind="plank", jitter=0.002, bevel=0.008)
    nb = 6; bw = (2 * HY - 2 * INS) / nb
    for i in range(nb):
        box("deck", (2 * IX, bw - 0.008, 0.04), (0, -HY + INS + bw * (i + 0.5), DECK - 0.02), kind="plank", jitter=0.0, bevel=0.007)
    for sy in (-1, 1):                                  # iron edge strips on the deck's front and back edges
        box("edge", (2 * IX - 0.01, 0.005, 0.03), (0, sy * (HY - 0.0025), DECK - 0.02), kind="iron", jitter=0, bevel=0.002)
    # top frame, flat at H, with an iron band on its outer faces
    RH = H - TOPZ
    for sy in (-1, 1):
        box("toprail", (2 * IX + 0.02, PS, RH), (0, sy * PY, H - RH / 2), jitter=0.002, bevel=0.01)
        box("topband", (2 * IX, 0.004, 0.035), (0, sy * (HY - 0.002), H - RH / 2), kind="iron", jitter=0, bevel=0.0015)
    for sx in (-1, 1):
        box("toprail", (PS, 2 * IY + 0.02, RH), (sx * PX, 0, H - RH / 2), jitter=0.002, bevel=0.01)
        box("topband", (0.004, 2 * IY, 0.035), (sx * (HX - 0.002), 0, H - RH / 2), kind="iron", jitter=0, bevel=0.0015)
    # back: a mid rail and two X straps; sides: a mid rail and an X strap each
    box("backrail", (2 * IX, 0.06, 0.08), (0, HY - INS - 0.035, 0.45), jitter=0.002, bevel=0.008)
    for xa, xb in ((-IX, 0.0), (0.0, IX)):
        base.strap("xb", (xa, DECK), (xb, TOPZ), "xz", HY - 0.006, thick=0.004)
        base.strap("xb", (xa, TOPZ), (xb, DECK), "xz", HY - 0.002, thick=0.004)
    for sx in (-1, 1):
        box("siderail", (0.06, 2 * IY, 0.08), (sx * (HX - INS - 0.035), 0, 0.45), jitter=0.002, bevel=0.008)
        base.strap("xs", (-IY, DECK), (IY, TOPZ), "yz", sx * (HX - 0.006), thick=0.004)
        base.strap("xs", (-IY, TOPZ), (IY, DECK), "yz", sx * (HX - 0.002), thick=0.004)
    return IX, IY

def pallet_units():
    units = []
    for r, y in enumerate(ROWS_Y):
        for c, x in enumerate(COLS_X):
            for tier in (0, 1):
                idx = len(units)
                z = DECK + 0.001 + tier * LAYERS * LAYER_DY
                units.append({"index": idx, "tier": tier, "row_from_back": r, "col_from_left": c,
                              "position": [round(a, 5) for a in b2u((x, y, z))], "rotation": [0.0, 0.0, 0.0],
                              "box_size": [round(PILE, 4), round(LAYERS * LAYER_DY, 4), round(PILE, 4)], "render_item": "Iron",
                              "copies": pile_copies(tier * LAYERS, LAYERS, 2000 + r * 8 + c + 100 * tier)})
    return units

if __name__ == "__main__":
    OUTA = os.path.normpath(os.path.join(base.HERE, "..", "assets", "metalpallet_r1"))
    OUT = arg("--out", os.path.join(SCRATCH, "pallet"))
    os.makedirs(OUTA, exist_ok=True); os.makedirs(OUT, exist_ok=True)
    base.setup_scene()
    atlas = build_atlas("metalpallet_atlas", OUTA)
    base.MAT = make_material("metalpallet", atlas)
    load_bars()
    IX, IY = build_pallet()
    frame = join(list(base.PARTS), "MetalPallet")
    clamp_bounds(frame, HX, HY, H)
    ftris = tris(frame)
    bb = np.array([tuple(v.co) for v in frame.data.vertices])
    print("PALLET frame tris", ftris, "bounds", bb.min(0).round(4), bb.max(0).round(4))
    units = pallet_units()
    chk = run_checks(units, frame, (-IX, IX, -HY, HY - INS - 0.065), TOPZ)
    save_atlas(atlas, os.path.join(OUTA, "metalpallet_atlas.png"))
    export_obj(frame, os.path.join(OUTA, "MetalPallet.obj"))
    doc = {
        "schema": "storehouse-anchors/1", "furniture": "Metal Pallet", "slug": "metalpallet", "round": 1,
        "unit_count": len(units), "slots_designed_for": 64, "stack_per_unit": True, "mirror": False,
        "frame": {"obj": "MetalPallet.obj", "atlas": "metalpallet_atlas.png 128x128 point", "tris": ftris, "size_m": [W, H, D],
                  "bounds_unity": {"min": [-HX, 0.0, -HY], "max": [HX, H, HY]},
                  "stacking": "four corner posts carry the load; flat top at y=0.80 and flat foot at y=0; the outer box is exactly the bounds "
                              "(iron post bands flush with it, posts 4 mm inside), so bounding-box corner snap points stack one pallet on another. "
                              f"Contents stay inside the posts and below the top frame (y < {TOPZ})."},
        "space": {"unity": "prefab space, origin on the floor at the centre of the footprint, +z front, +y up, +x to the furniture's left seen from the front",
                  "from_blender": "ux=-bx, uy=bz, uz=-by"},
        "fill_order": "NOT mirrored: units are listed in fill order, the n-th stack goes to unit n. Pile by pile: the 32 footprints from the "
                      "back row to the front, each row left to right seen from the front; per footprint the lower unit (tier 0, even index) then "
                      "the upper unit (tier 1, odd index) lying on it. A pile reaches full height before the next one starts; upper units never "
                      "float. Leave mirror off for this store: its units have only two heights.",
        "position": "unit position = bottom centre of its pile part (the deck top for the lower tier, the top of the lower unit for the upper). "
                    "box_size = [x, y, z] Unity, informational.",
        "copy_rule": "Each copy = one bar: align (long axis -> long_axis_to, thin axis -> up), then then_rotate (a little yaw), uniform scale so the "
                     "longest side = longest_m, anchor bottom (the turned bounds' bottom at unit.position + offset). Layer j sits at offset.y = j * "
                     f"{LAYER_DY:.5f} m. Copies are listed bottom layer first, 2 per layer, crosswise layers (lower unit: layers 0,2,4 along x, "
                     "1,3 along z; the upper unit continues the alternation, its layer 0 along z).",
        "items": {"all_bars": {"bounds_size_unity": [round(a, 4) for a in BAR["size_u"]], "longest_m": BAR_L, "scale": round(BAR["s"], 5),
                               "bar_size_m": [round(BAR["L"], 4), round(BAR["t"], 4), round(BAR["w"], 4)],
                               "note": "Copper, Tin, Bronze, Iron, Silver, BlackMetal, Flametal and FlametalNew share one 44-triangle bar mesh"}},
        "layout": {"footprints": "8 across x 4 deep", "pitch_m": PITCH, "tiers": 2, "layers_per_unit": LAYERS, "bars_per_unit": LAYERS * 2,
                   "deck_top_y": DECK, "pile_top_y_full": round(DECK + 0.001 + 2 * LAYERS * LAYER_DY, 4), "pile_footprint_m": round(PILE, 4)},
        "checks": chk,
        "units_data": units}
    write_json_atomic(doc, os.path.join(OUTA, "MetalPalletAnchors.json"))
    print("WROTE", OUTA)
    if "--no-render" in argv: sys.exit(0)
    SP = 2.8
    mix = metal_mix(64)
    fills = {"empty": 0, "10": 6, "50": 32, "100": 64}
    for i, (nm, n) in enumerate(fills.items()):
        spawn(units, [mix[j] if j < n else None for j in range(64)], i * SP, frame)
    spawn(units, mix, 4 * SP + 0.2, frame)
    top = spawn(units, [None] * 64, 4 * SP + 0.2, frame); top.location.z = H
    frame.hide_render = True
    references(chest_x=-2.05, post_x=-3.0)
    views = {"fills": (-4, 22, 15.5, (1.6 * SP - 1.2, 0, 0.4), 34), "close": (-22, 24, 3.6, (3 * SP, 0, 0.45), 40),
             "alt": (35, 48, 4.2, (2 * SP, 0, 0.4), 40), "low": (-8, 6, 3.0, (3 * SP - 0.5, 0, 0.45), 40),
             "stack": (-38, 18, 5.0, (4 * SP + 0.2, 0, 0.8), 40)}
    lights_and_render(OUT, "metalpallet", views)
    print("DONE")
