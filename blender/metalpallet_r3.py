"""Metal Pallet round 3: the r2 pallet made HEAVY. Joost on r2 in game: "it feels kinda lightweight for a rack that's supposed
to hold hundreds of bars of metal" (slim posts, thin top rail, X braces that read as thin dark rods: a fruit crate).
Same contents as r2 (64 units, 2-bar piles in 4 alternating tiers, bars at TRUE SIZE = scale 1.0, same fill order, same
per-unit seeds), a new heavy-duty frame and a darker, worn atlas. Helpers from metalrack_r1.py, true-size bar numbers and
the clip checks from metalrack_r2.py, the r2 pallet itself (for the side-by-side render) from metalpallet_r2.py.
Run: blender -b -P metalpallet_r3.py -- [--out DIR] [--quick] [--views a,b] [--no-render]

Frame 2.86 W x 1.50 D x 1.20 H (Blender x, y, z; -y = front). The contents block (2.526 x 1.257 m) sits inside the opening
of the frame, so the beams can be deep without touching it:
  posts      0.14 x 0.14 (r2 0.09: 2.4x the section), 4 mm inside the bounds, three 0.10 iron bands each, flush with the bounds
  top frame  a ring of 0.13 deep beams (r2: a 0.06 rail), flat at 1.20, an iron band on every outer face and riveted iron
             corner brackets where the beams meet the posts
  base       five 0.16 x 0.10 skids front to back on the ground (dark fork gaps between them from the front), 7 deck planks
             0.05 thick along x across them (deck top 0.15); iron-strapped ends: a riveted strap up every skid end and the deck
             edge, folded over the deck, front and back; side sills 0.21 high, a back kick beam
  back       a centre stud and two panels of crossed TIMBER braces, an iron plate with rivets on each crossing
  sides      a mid rail and an X of FLAT IRON STRAPS 0.10 wide, a riveted iron plate on the crossing, the strap ends under
             riveted corner brackets
  front      open (the top beam is the only thing across it)
1.20 H = the low Metal Rack, so two pallets stacked are as tall as the tall rack. Stacking: flat foot at 0 and flat top at
1.20, outer box exactly the bounds (post bands flush), so the mod's bounding-box corner snap points stack one pallet on
another; the upper pallet's skids and side sills land on the lower one's top beams.
Atlas 128x128 point, same row layout as r1/r2 (v from the bottom: 96-127 hewn timber, 64-95 end grain, 32-63 planks, 0-31
iron), darker oiled timber, iron with a black-to-rust gradient; the 4th end-grain tile is a WEAR swatch: every bevel
(chamfer) face maps to worn light timber or worn bright iron, so all edges read worn, and the rivet heads map to it too.
Contents: as r2 (see metalpallet_r2.py), block centred in y, on the deck at 0.15; contents top 1.149.
"""
import os, sys, math, json, random
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import bpy
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
import metalrack_r1 as base
import metalrack_r2 as rack
import metalpallet_r2 as p2
from metalrack_r1 import (box, strap, corner_posts, join, clamp_bounds, tris, tri_list, references, lights_and_render, metal_mix,
                          b2u, save_atlas, export_obj, write_json_atomic, build_atlas, make_material, load_bars, place_unit,
                          bar_world, TEMPL, argv, arg, TW, TH)
from metalrack_r2 import BAR_L, BAR_W, BAR_T, FIT_L, LIFT, LAYER_DY, checks, spawn2

SCRATCHP = "C:/Users/joost/AppData/Local/Temp/claude/C--Users-joost--pai/5e4bc60b-cdfe-4638-8e29-2e507fa13cf9/scratchpad/pallet3"
YAW_J, LAT_J, LON_J = p2.YAW_J, p2.LAT_J, p2.LON_J

# ---------- the stack block (as r2) ----------
G, NT, LAYERS = p2.G, p2.NT, p2.LAYERS
SPAN_X, SPAN_Y, GX, GY = p2.SPAN_X, p2.SPAN_Y, p2.GX, p2.GY      # 2.5264 x 1.2572

# ---------- the frame ----------
W, D, H = 2.86, 1.50, 1.20
HX, HY = W / 2, D / 2
PS, INS = 0.14, 0.004
PX, PY = HX - INS - PS / 2, HY - INS - PS / 2      # post centres 1.356, 0.676
IX = PX - PS / 2                                   # 1.286: inner face of the posts (contents span +-1.2632)
IYP = PY - PS / 2                                  # 0.606: inner face of the posts in y (beams along y end here)
BO = HY - 0.016                                    # 0.734: outer face of the front/back beams (12 mm behind the post face)
BI = 0.640                                         # inner face of the front/back beams (contents span +-0.6286)
SXI, SXO = IX + 0.010, HX - 0.022                  # side beams: x 1.296 .. 1.408 (outer face 18 mm behind the post face)
SK_H, SK_W = 0.10, 0.16                            # skids (front to back)
SKX = [-1.15, -0.575, 0.0, 0.575, 1.15]            # skid centres in x
DT = 0.05                                          # deck plank thickness
DECK = SK_H + DT                                   # 0.15: deck top
SILL = 0.21                                        # side sill top
KICK = 0.27                                        # back kick beam top
TB = 0.13                                          # top beam depth
TOPZ = H - TB                                      # 1.07: underside of the top beams (outside the contents in plan)
MIDZ = (SILL + TOPZ) / 2                           # 0.64: side mid rail, post mid band
YC = 0.0                                           # contents centred in y
FE = 0.008                                         # iron plate / band thickness on the beams
RV = 0.005                                         # rivet head height
TOP_LIMIT = H - 0.03                               # contents must stay below this (upper pallet's skids rest at H)

# ---------- atlas ----------
def srgb(c): return np.array(c, dtype=np.float32)
WOOD, WOOD_D, WOOD_L = srgb((0.29, 0.21, 0.135)), srgb((0.12, 0.085, 0.055)), srgb((0.47, 0.37, 0.25))
END, END_D = srgb((0.44, 0.34, 0.22)), srgb((0.21, 0.15, 0.095))
PLNK, PLNK_D = srgb((0.35, 0.26, 0.165)), srgb((0.16, 0.115, 0.07))
IRON, IRON_D, RUST, STEEL = srgb((0.21, 0.20, 0.19)), srgb((0.045, 0.045, 0.05)), srgb((0.33, 0.19, 0.105)), srgb((0.50, 0.49, 0.46))
SWATCH_U = 96                                      # end-grain tile 3 = wear swatch: v 80-95 worn timber, v 64-79 worn iron

def mix(a, b, t): t = np.clip(t, 0, 1)[..., None]; return a * (1 - t) + b * t

def build_atlas_r3(name):
    nr = np.random.default_rng(23)
    img = np.zeros((TH, TW, 3), np.float32)
    x = np.arange(TW)[None, :].repeat(32, 0).astype(np.float32)
    y = np.arange(32)[:, None].repeat(TW, 1).astype(np.float32)
    tile = lambda k: 2 * math.pi * k / TW
    # hewn timber: dark oiled, wavy grain, oil patches (low frequency), drying checks, a few worn light streaks
    g = np.sin(y * 1.25 + 1.6 * np.sin(x * tile(2) + y * 0.15) + 0.7 * np.sin(x * tile(5)))
    t = np.clip((g - 0.5) * 2.5, 0, 1) * 0.55 + nr.random((32, TW)) * 0.22
    t += 0.18 * (0.5 + 0.5 * np.sin(x * tile(1) + 0.9 + 0.4 * np.sin(y * 0.3)))
    t += np.clip(1 - np.minimum(y, 31 - y) / 2.5, 0, 1) * 0.3
    for _ in range(9):                                                     # checks: short dark cracks along the grain
        yy, x0, n = nr.integers(2, 30), nr.integers(0, TW), nr.integers(6, 18)
        for k in range(n): t[yy, (x0 + k) % TW] += 0.6
    hew = mix(WOOD, WOOD_D, t)
    worn = (nr.random((32, TW)) < 0.035) & (t < 0.5)
    hew[worn] = mix(hew[worn], WOOD_L, np.full(worn.sum(), 0.55))
    img[96:128] = hew
    # end grain: 3 ring tiles (k = 0..2), darker rings, a radial check
    for k in range(3):
        cx, cy = 15.5 + nr.uniform(-2, 2), 15.5 + nr.uniform(-2, 2)
        xx, yy = np.meshgrid(np.arange(32), np.arange(32))
        ang = np.arctan2(yy - cy, xx - cx)
        d = np.hypot(xx - cx, yy - cy) + 0.6 * np.sin(ang * 3 + k)
        t = (np.sin(d * 1.5) * 0.5 + 0.5) * 0.5 + nr.random((32, 32)) * 0.15
        t += (np.abs(ang - (k * 2.1 - 2.0)) < 0.09) * (d > 3) * 0.6           # radial drying check
        t = np.where(d > 13.5, 1.0, t)
        img[64:96, 32 * k:32 * k + 32] = mix(END, END_D, t)
    # wear swatch: worn timber (top half) and worn bright iron (bottom half)
    n = nr.random((16, 32))
    img[80:96, 96:128] = mix(WOOD_L, WOOD, n * 0.45)
    img[64:80, 96:128] = mix(STEEL, IRON, n * 0.5)
    # sawn planks: straighter, finer grain, a dark board seam every 16 px (v), saw marks across every 32 px (u)
    g = np.sin(y * 2.1 + 0.8 * np.sin(x * tile(3) + y * 0.3))
    t = np.clip((g - 0.6) * 2.0, 0, 1) * 0.45 + nr.random((32, TW)) * 0.18 + 0.12 * (0.5 + 0.5 * np.sin(x * tile(2) + 2.0))
    t += ((y % 16) == 0) * 0.55 + ((y % 16) == 15) * 0.25 + ((x % 32) < 1) * 0.12
    img[32:64] = mix(PLNK, PLNK_D, t)
    # iron: black-to-rust gradient along u (iron faces wrap in u with world position), pitting, dark face edges
    b = 0.5 + 0.5 * np.sin(x * tile(2) + 0.8 * np.sin(x * tile(5)))
    t = b * 0.55 + nr.random((32, TW)) * 0.35 + np.clip(1 - np.minimum(y, 31 - y) / 2.0, 0, 1) * 0.35
    ir = mix(IRON, IRON_D, t)
    rust = np.clip((np.sin(x * tile(3) + 2.0 + 1.5 * np.sin(x * tile(7))) * 0.5 + 0.5 - 0.45) * 2.2, 0, 1) * (0.4 + 0.6 * nr.random((32, TW)))
    img[0:32] = mix(ir, RUST, rust * 0.75)
    im = bpy.data.images.new(name, TW, TH, alpha=False)
    px = np.concatenate([np.clip(img, 0, 1), np.ones((TH, TW, 1), np.float32)], 2)
    im.pixels.foreach_set(px.ravel())
    return im

ORIG_UV_FACE = base.uv_face
def uv_face_r3(f, kind, long_axis, seed):
    """r1 mapping, plus: rivet heads and every chamfer face -> the wear swatch; end grain uses ring tiles 0-2 only."""
    n = f.normal
    r = random.Random(seed * 7919 + f.index)
    if kind == "rivet" or max(abs(n[0]), abs(n[1]), abs(n[2])) < 0.98:
        u = (SWATCH_U + 1 + r.randrange(30) + 0.5) / TW
        v = ((65 if kind in ("iron", "rivet") else 81) + r.randrange(14) + 0.5) / TH
        for l in f.loops: l[base.UV].uv = (u, v)
        return
    ORIG_UV_FACE(f, kind, long_axis, (seed // 4) * 4 + seed % 3)

# ---------- geometry helpers ----------
def rivet(x, y, z, axis, s=0.024):
    """A square iron rivet head; axis = 'x' or 'y' (the face normal it sits on), (x, y, z) = the centre of the head."""
    size = (RV, s, s) if axis == "x" else (s, RV, s)
    box("rivet", size, (x, y, z), kind="rivet", jitter=0, bevel=0)

def plate_y(x0, x1, z0, z1, yface, sgn, rivets=()):
    """Iron plate on a face at y = yface (sgn = +1 back, -1 front), FE thick, with rivets at (x, z)."""
    box("plate", (x1 - x0, FE, z1 - z0), ((x0 + x1) / 2, yface + sgn * FE / 2, (z0 + z1) / 2), kind="iron", jitter=0, bevel=0.002)
    for rx, rz in rivets: rivet(rx, yface + sgn * (FE + RV / 2), rz, "y")

def plate_x(y0, y1, z0, z1, xface, sgn, rivets=(), t=FE):
    box("plate", (t, y1 - y0, z1 - z0), (xface + sgn * t / 2, (y0 + y1) / 2, (z0 + z1) / 2), kind="iron", jitter=0, bevel=0.002)
    for ry, rz in rivets: rivet(xface + sgn * (t + RV / 2), ry, rz, "x")

def brace_xz(a, b, y0, y1, width=0.085):
    """A timber brace in a back-plane panel, from a to b ((x, z) points), y from y0 to y1."""
    dx, dz = b[0] - a[0], b[1] - a[1]
    L = math.hypot(dx, dz); ang = math.degrees(math.atan2(dz, dx))
    box("brace", (L, y1 - y0, width), ((a[0] + b[0]) / 2, (y0 + y1) / 2, (a[1] + b[1]) / 2), rot=(0, -ang, 0), jitter=0.0, bevel=0.01)

def build_pallet():
    corner_posts(HX, HY, H, PS, INS, bands=[(0.02, 0.10), (MIDZ - 0.05, 0.10), (H - 0.12, 0.10)])
    # ---- base: five skids front to back on the ground (dark fork gaps between them seen from the front) ----
    for x in SKX:
        box("skid", (SK_W, 2 * BO, SK_H), (x, 0, SK_H / 2), jitter=0.003, bevel=0.014)
    # deck: 7 heavy planks along x across the skids
    nb, gap = 7, 0.007
    bw = (2 * BO - (nb - 1) * gap) / nb
    for i in range(nb):
        box("deck", (2 * IX, bw, DT), (0, -BO + bw / 2 + i * (bw + gap), SK_H + DT / 2), kind="plank", jitter=0.0, bevel=0.008)
    # iron-strapped ends: at every skid, front and back, a riveted strap up the skid end and the deck edge, folded over the deck
    for x in SKX:
        for sg in (-1, 1):
            plate_y(x - 0.045, x + 0.045, 0.012, DECK, sg * BO, sg, rivets=[(x, SK_H / 2), (x, DECK - DT / 2)])
            box("clip", (0.09, 0.07, FE), (x, sg * (BO + FE - 0.035), DECK + FE / 2), kind="iron", jitter=0, bevel=0.002)
    # side sills on the ground (the upper pallet's sills land on the lower one's side top beams), back kick beam on the deck
    for sx in (-1, 1):
        box("sill", (SXO - SXI, 2 * IYP, SILL), (sx * (SXI + SXO) / 2, 0, SILL / 2), jitter=0.003, bevel=0.014)
    box("kick", (2 * IX, BO - BI, KICK - DECK), (0, (BO + BI) / 2, (DECK + KICK) / 2), jitter=0.003, bevel=0.012)
    # ---- top frame: a ring of deep beams flat at H ----
    for sg in (-1, 1):
        box("topbeam", (2 * IX, BO - BI, TB), (0, sg * (BO + BI) / 2, H - TB / 2), jitter=0.003, bevel=0.014)
    for sx in (-1, 1):
        box("topbeam", (SXO - SXI, 2 * IYP, TB), (sx * (SXI + SXO) / 2, 0, H - TB / 2), jitter=0.003, bevel=0.014)
    # iron bands along the top beams and riveted corner brackets at the posts (front/back faces)
    BRK = 0.17
    for sg in (-1, 1):
        box("topband", (2 * (IX - BRK), FE, 0.045), (0, sg * (BO + FE / 2), H - TB / 2), kind="iron", jitter=0, bevel=0.002)
        for sx in (-1, 1):
            xa, xb = sorted((sx * IX, sx * (IX - BRK)))
            xm = (xa + xb) / 2
            plate_y(xa, xb, TOPZ + 0.012, H - 0.012, sg * BO, sg,
                    rivets=[(xm + dx, TOPZ + TB / 2 + dz) for dx in (-0.045, 0.045) for dz in (-0.03, 0.03)])
    # ---- back: kick beam, a centre stud, two panels of crossed timber braces with a riveted plate on each crossing ----
    box("stud", (0.11, BO - BI, TOPZ - KICK), (0, (BO + BI) / 2, (KICK + TOPZ) / 2), jitter=0.003, bevel=0.012)
    for xa, xb in ((-IX, -0.055), (0.055, IX)):
        brace_xz((xa, KICK), (xb, TOPZ), BI + 0.006, BO - 0.006)
        brace_xz((xa, TOPZ), (xb, KICK), BI + 0.007, BO - 0.007)
        xc, zc = (xa + xb) / 2, (KICK + TOPZ) / 2
        plate_y(xc - 0.11, xc + 0.11, zc - 0.085, zc + 0.085, BO - 0.006, 1,      # on the braces' outer face
                rivets=[(xc + dx, zc + dz) for dx in (-0.075, 0.075) for dz in (-0.05, 0.05)])
    # ---- sides: a mid rail, an X of flat iron straps (two layers), a riveted plate on the crossing, corner brackets ----
    for sx in (-1, 1):
        xo = sx * SXO
        box("midrail", (SXO - SXI, 2 * IYP, 0.10), (sx * (SXI + SXO) / 2, 0, MIDZ), jitter=0.003, bevel=0.012)
        strap("xs", (-IYP, SILL), (IYP, TOPZ), "yz", xo + sx * 0.0025, width=0.10, thick=0.005)
        strap("xs", (-IYP, TOPZ), (IYP, SILL), "yz", xo + sx * 0.0075, width=0.10, thick=0.005)
        plate_x(-0.10, 0.10, MIDZ - 0.08, MIDZ + 0.08, xo + sx * 0.010, sx, t=0.005,
                rivets=[(dy, MIDZ + dz) for dy in (-0.065, 0.065) for dz in (-0.045, 0.045)])
        # top beam band, corner brackets top and bottom (thick plates from the beam face, over the strap ends)
        box("topband", (0.015, 2 * (IYP - BRK), 0.045), (xo + sx * 0.0075, 0, H - TB / 2), kind="iron", jitter=0, bevel=0.002)
        for sy in (-1, 1):
            ya, yb = sorted((sy * IYP, sy * (IYP - BRK)))
            ym = (ya + yb) / 2
            for z0, z1 in ((TOPZ + 0.012, H - 0.012), (0.03, SILL - 0.015)):
                zm = (z0 + z1) / 2
                plate_x(ya, yb, z0, z1, xo, sx, t=0.015,
                        rivets=[(ym + dy, zm + dz) for dy in (-0.045, 0.045) for dz in (-0.03, 0.03)])

# ---------- the contents (as r2, block centred in y on the deck at 0.15) ----------
def tier_grid(t):
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
                          "render_item": "Iron", "copies": p2.pile_copies(9100 + 37 * idx, along_x)})
    return units

def stack_clip(units, frame):
    """A second pallet stacked on this one: its frame (shifted up by H) against this pallet's bars, Copper and BlackMetal."""
    V, T = tri_list(frame.data)
    up = BVHTree.FromPolygons([v + Vector((0, 0, H)) for v in V], T, all_triangles=True)
    res = {}
    for it in ("Copper", "BlackMetal"):
        n = 0
        for u in units:
            for M in place_unit(u, it):
                Wb = bar_world(M, it)
                if up.overlap(BVHTree.FromPolygons([Vector(w) for w in Wb], TEMPL[it]["tris"])): n += 1
        res[it] = n
    print("STACK CLIP", json.dumps(res))
    return res

if __name__ == "__main__":
    OUTA = os.path.normpath(os.path.join(base.HERE, "..", "assets", "metalpallet_r3"))
    OUT = arg("--out", SCRATCHP)
    os.makedirs(OUTA, exist_ok=True); os.makedirs(OUT, exist_ok=True)
    base.setup_scene()
    atlas = build_atlas_r3("metalpallet_atlas")
    base.MAT = make_material("metalpallet", atlas)
    load_bars()
    base.PARTS.clear()
    base.uv_face = uv_face_r3
    build_pallet()
    base.uv_face = ORIG_UV_FACE
    frame = join(list(base.PARTS), "MetalPallet")
    clamp_bounds(frame, HX, HY, H)
    ftris = tris(frame)
    bb = np.array([tuple(v.co) for v in frame.data.vertices])
    ctop = DECK + LIFT + NT * LAYERS * LAYER_DY - LIFT
    print(f"PALLET W {W} D {D} H {H} tris {ftris} bounds {bb.min(0).round(4)} {bb.max(0).round(4)}; span {SPAN_X:.4f} x {SPAN_Y:.4f} "
          f"contents top {ctop:.4f} top beams underside {TOPZ} (outside the contents in plan) top limit {TOP_LIMIT}")
    units = pallet_units()
    chk = checks(units, frame, (-IX, IX, -BI, BI), TOP_LIMIT)
    sup = p2.support_check(units)
    fok = p2.fill_order_ok(units)
    sclip = stack_clip(units, frame)
    print("FILL ORDER ok", fok)
    save_atlas(atlas, os.path.join(OUTA, "metalpallet_atlas.png"))
    export_obj(frame, os.path.join(OUTA, "MetalPallet.obj"))
    doc = {
        "schema": "storehouse-anchors/1", "furniture": "Metal Pallet", "slug": "metalpallet", "round": 3,
        "unit_count": len(units), "slots_designed_for": 64, "stack_per_unit": True, "mirror": False,
        "frame": {"obj": "MetalPallet.obj", "atlas": "metalpallet_atlas.png 128x128 point", "tris": ftris, "size_m": [W, H, D],
                  "bounds_unity": {"min": [-HX, 0.0, -HY], "max": [HX, H, HY]},
                  "stacking": f"four 0.14 m corner posts carry the load; flat top at y={H} and flat foot at y=0; the outer box is exactly the "
                              "bounds (iron post bands flush with it, posts 4 mm inside), so bounding-box corner snap points stack one pallet "
                              "on another; the upper pallet's skids and side sills land on the lower one's top beams. 1.20 high = the low "
                              "Metal Rack: two pallets stacked are as tall as the tall rack. The contents sit inside the opening of the top "
                              f"frame (inside the posts and beams in plan) and stay below y = {TOP_LIMIT}.",
                  "heavy": "r3: posts 0.14 (r2 0.09), top beams 0.13 deep (r2 0.06), skids 0.16 x 0.10, deck planks 0.05, timber X braces "
                           "on the back, 0.10 wide iron straps on the sides, riveted brackets and plates"},
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
                   "deck_top_y": DECK, "contents_top_y_full": round(ctop, 4), "contents_top_limit_y": TOP_LIMIT,
                   "top_beams_underside_y": TOPZ, "inner_opening_unity_x_z": [round(2 * IX, 4), round(2 * BI, 4)]},
        "checks": {"fill_order_ok": fok, "support": sup, "stacked_frame_vs_lower_bars_clipping": sclip, **chk},
        "units_data": units}
    write_json_atomic(doc, os.path.join(OUTA, "MetalPalletAnchors.json"))   # last: the mod live-reloads
    print("WROTE", OUTA)
    if "--no-render" in argv: sys.exit(0)

    # ---- comparison pieces: the r2 pallet (its own r1-style atlas) and the low and tall Metal Racks ----
    old_atlas = build_atlas("metalpallet_r2_atlas", OUT)
    base.MAT = make_material("metalpallet_r2", old_atlas)
    base.PARTS.clear()
    p2.build_pallet()
    frame2 = join(list(base.PARTS), "MetalPallet_r2"); clamp_bounds(frame2, p2.HX, p2.HY, p2.H); frame2.hide_render = True
    units2 = p2.pallet_units()
    base.PARTS.clear()
    rack.build_frame(2, 1)
    rlow = join(list(base.PARTS), "MetalRackLow"); clamp_bounds(rlow, rack.WH, rack.HY, rack.HL); rlow.hide_render = True
    rlow_units, _ = rack.module_units(2, 1)
    base.PARTS.clear()
    rack.build_frame(2, 2)
    rtall = join(list(base.PARTS), "MetalRack"); clamp_bounds(rtall, rack.WH, rack.HY, 2 * rack.HL); rtall.hide_render = True
    rtall_units, _ = rack.module_units(2, 2)

    mix64 = metal_mix(64)
    X_EMPTY, X_FULL, X_STACK, X_VS, X_RACK = -24.0, -14.0, -4.0, 6.0, 16.0
    spawn2(units, [None] * 64, X_EMPTY, 0, frame)
    spawn2(units, mix64, X_FULL, 0, frame)
    spawn2(units, [mix64[j] if j < 32 else None for j in range(64)], X_FULL + W + 0.6, 0, frame)     # 50 % beside the full one
    spawn2(units, mix64, X_STACK, 0, frame); spawn2(units, mix64, X_STACK, H, frame)
    spawn2(units, [None] * 64, X_STACK + W + 0.6, 0, frame); spawn2(units, [None] * 64, X_STACK + W + 0.6, H, frame)
    spawn2(units2, mix64, X_VS - p2.HX - 0.3, 0, frame2)                                               # r2 left, r3 right
    spawn2(units, mix64, X_VS + HX + 0.3, 0, frame)
    # low rack | pallet | tall rack | two pallets stacked, 0.4 m apart
    x = X_RACK
    spawn2(rlow_units, metal_mix(32), x + rack.WH, 0, rlow); x += 2 * rack.WH + 0.4
    spawn2(units, mix64, x + HX, 0, frame); x += W + 0.4
    spawn2(rtall_units, metal_mix(64), x + rack.WH, 0, rtall); x += 2 * rack.WH + 0.4
    spawn2(units, mix64, x + HX, 0, frame); spawn2(units, [mix64[j] if j < 40 else None for j in range(64)], x + HX, H, frame)
    XR_MID = (X_RACK + x + W) / 2
    frame.hide_render = True
    references(chest_x=X_FULL - HX - 1.1, post_x=X_FULL - HX - 2.1)
    views = {"empty": (-28, 18, 5.6, (X_EMPTY, 0, 0.55), 40), "emptyback": (150, 16, 5.6, (X_EMPTY, 0, 0.55), 40),
             "full": (-26, 18, 6.6, (X_FULL - 0.6, 0, 0.6), 40), "front": (0, 8, 5.0, (X_FULL, 0, 0.6), 40),
             "detail": (-38, 14, 2.4, (X_FULL - HX + 0.2, -HY + 0.1, 0.55), 40),
             "stack": (-30, 16, 8.4, (X_STACK + 1.6, 0, 1.2), 40), "vs_r2": (-12, 14, 8.0, (X_VS, 0, 0.6), 40),
             "racks": (-6, 10, 15.0, (XR_MID, 0, 1.2), 36)}
    lights_and_render(OUT, "metalpallet3", views)
    print("DONE")
