"""Hauler's Strongbox - procedural low-poly model for Valheim (Jotunn AssetUtils.LoadMesh).

Run headless:   blender -b -P strongbox.py            (also runs as plain python3, it only needs mathutils)
Outputs (../assets/strongbox/):
    StrongboxBody.obj, StrongboxLid.obj, StrongboxBodyLOD.obj, StrongboxLidLOD.obj,
    StrongboxCollider.obj, strongbox.json

Conventions (verified against the vanilla piece_chest_blackmetal prefab, see vanilla-chest-measurements.md):
  * Modelling space = Blender world, metres, = the prefab's world space:  -Y = chest front, +Z = up.
  * Jotunn's ObjImporter reads `v x y z` VERBATIM as Unity mesh-local coordinates, takes `vt` verbatim
    (no v-flip), `vn` verbatim, and builds triangles in file order (Unity front face = clockwise).
    So this script writes Unity coordinates directly and reverses every Blender (CCW) triangle.
  * Body/LOD meshes live under vanilla node `New/blackmetalchest` (localRot = 180 deg about Y, localScale 0.9):
        mesh_local = (bx, bz, by) / 0.9
  * Lid meshes live under `New/Closed/blackmetalchesttop_closed` (localPos (0, 0.907, 0)) and
    `New/Open/blackmetalchesttop_open` (parents Closed/Open have the same 180deg/0.9 transform):
        lid_local = (bx, bz, by) / 0.9 - (0, 0.907, 0)
    The closed lid therefore needs no transform change; the OPEN lid needs the position given in
    strongbox.json (hinge differs from vanilla).
  * Collider mesh lives under `collider` (no rotation, localScale 0.8):  collider_local = (-bx, bz, -by) / 0.8
  * UVs land on the vanilla BlackMetalChest_D/_N/_M atlas (256 px): wood planks u 0.594-0.99 / v 0.01-0.49
    (grain runs along v), dark interior u 0.60-0.99 / v 0.62-0.99, metal u 0.02-0.52 (any v, Repeat wrap).
"""
import math, json, os, random, sys
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, "..", "assets", "strongbox"))
PX = 256.0
D_WOOD = 50.0 / PX      # uv per metre, vanilla wood measured 47-57 px/m
D_METAL = 78.0 / PX     # vanilla metal measured 66-81 px/m
D_BAND = 64.0 / PX      # along-band density (vanilla bands ~50-55 px/m along their length)
BODY_SCALE = 0.9
LID_CLOSED_POS = (0.0, 0.907, 0.0)
OPEN_ANGLE = 30.0       # same as vanilla open lid

# ------------------------------------------------------------------ dimensions (metres, world)
Z0, ZK, ZT = 0.10, 0.50, 1.32          # core bottom, flare kink, core top
HW = ((Z0, 1.50), (ZK, 1.31), (ZT, 1.25))   # half width  (vanilla core ~1.04 at bottom)
HD = ((Z0, 0.95), (ZK, 0.80), (ZT, 0.76))   # half depth  (vanilla core ~0.64)
WALL = 0.07
ZF = 0.24                                # interior floor
BAND_T, STRAP_T, PLATE_T = 0.030, 0.022, 0.040
BAND_ZS = [(0.12, 0.27), (0.43, 0.58), (0.88, 1.03), (1.16, 1.31)]   # 0.15 tall like vanilla (0.16)
FRONT_STRAPS = (-0.55, 0.55)
STRAP_W = 0.13                           # vanilla front straps 0.132
LID_OVER = 0.03
LID_EDGE, LID_CROWN = 1.45, 1.51
LID_STRAPS = (-0.75, 0.0, 0.75)
HINGES = (-0.75, 0.75)
RIVET_R0, RIVET_R1, RIVET_H = 0.032, 0.021, 0.026   # vanilla rivet 0.06 x 0.062 x 0.047 bbox


def lerp_prof(prof, z):
    if z <= prof[0][0]:
        (za, a), (zb, b) = prof[0], prof[1]
    elif z >= prof[-1][0]:
        (za, a), (zb, b) = prof[-2], prof[-1]
    else:
        for i in range(len(prof) - 1):
            if prof[i][0] <= z <= prof[i + 1][0]:
                (za, a), (zb, b) = prof[i], prof[i + 1]
                break
    return a + (b - a) * (z - za) / (zb - za)


def hw(z): return lerp_prof(HW, z)
def hd(z): return lerp_prof(HD, z)


FACES = {  # s-axis, outward normal
    "front": (Vector((1, 0, 0)), Vector((0, -1, 0))),
    "back": (Vector((1, 0, 0)), Vector((0, 1, 0))),
    "left": (Vector((0, 1, 0)), Vector((-1, 0, 0))),
    "right": (Vector((0, 1, 0)), Vector((1, 0, 0))),
}


def surf(face, s, z, t=0.0):
    if face == "front": return Vector((s, -(hd(z) + t), z))
    if face == "back": return Vector((s, hd(z) + t, z))
    if face == "left": return Vector((-(hw(z) + t), s, z))
    return Vector((hw(z) + t, s, z))


def half_len(face, z):
    return hw(z) if face in ("front", "back") else hd(z)


# ------------------------------------------------------------------ mesh container
def newell(pts):
    n = Vector((0, 0, 0))
    for i, a in enumerate(pts):
        b = pts[(i + 1) % len(pts)]
        n.x += (a.y - b.y) * (a.z + b.z)
        n.y += (a.z - b.z) * (a.x + b.x)
        n.z += (a.x - b.x) * (a.y + b.y)
    return n


class Mesh:
    def __init__(self, name):
        self.name, self.polys = name, []

    def add(self, pts, uvf, hint):
        pts = [Vector(p) for p in pts]
        n = newell(pts)
        if n.length < 1e-10:
            return
        c = sum(pts, Vector()) / len(pts)
        want = (c - hint[1]) if (isinstance(hint, tuple) and len(hint) == 2 and hint[0] == "c") else Vector(hint)
        if n.dot(want) < 0:
            pts = list(reversed(pts))
        self.polys.append((pts, uvf(pts)))

    def tris(self):
        out = []
        for pts, uvs in self.polys:
            for i in range(1, len(pts) - 1):
                out.append(((pts[0], pts[i], pts[i + 1]), (uvs[0], uvs[i], uvs[i + 1])))
        return out


# ------------------------------------------------------------------ UV helpers
def uv_axes(o, ax_u, ax_v, u0, v0, du, dv):
    def f(pts):
        return [(u0 + (p - o).dot(ax_u) * du, v0 + (p - o).dot(ax_v) * dv) for p in pts]
    return f


def face_basis(pts):
    n = newell(pts).normalized()
    up = Vector((0, 0, 1)) if abs(n.z) < 0.9 else Vector((0, 1, 0))
    v = (up - n * up.dot(n)).normalized()
    u = v.cross(n).normalized()
    return u, v


def metal(center_uv, du=D_METAL):
    """per-face planar projection, centred on a fixed metal-atlas spot (vanilla shares islands the same way)"""
    def f(pts):
        u, v = face_basis(pts)
        c = sum(pts, Vector()) / len(pts)
        return [(center_uv[0] + (p - c).dot(u) * du, center_uv[1] + (p - c).dot(v) * du) for p in pts]
    return f


def dark(pts):
    u, v = face_basis(pts)
    c = sum(pts, Vector()) / len(pts)
    # interior is near-black; keep it inside u .62-.98 / v .65-.97
    return [(0.80 + max(-0.17, min(0.17, (p - c).dot(u) * 0.12)), 0.81 + max(-0.15, min(0.15, (p - c).dot(v) * 0.12))) for p in pts]


RNG = random.Random(7)


def metal_spot(size=0.5):
    """random island centre that keeps an island of `size` metres inside the metal half"""
    r = size * D_METAL / 2 + 0.02
    return (RNG.uniform(0.04 + r, 0.50 - r), RNG.uniform(0.05 + r, 0.95 - r))


# ------------------------------------------------------------------ primitives
def rivet(m, p, n, up=Vector((0, 0, 1)), lod=False):
    if lod:
        return
    n = Vector(n).normalized()
    a = (up - n * up.dot(n))
    if a.length < 1e-4:
        a = Vector((1, 0, 0)) - n * n.x
    a.normalize()
    b = n.cross(a)
    ring0 = [p + (a * math.cos(k * math.pi / 4 + math.pi / 8) + b * math.sin(k * math.pi / 4 + math.pi / 8)) * RIVET_R0 for k in range(8)]
    ring1 = [p + n * RIVET_H + (a * math.cos(k * math.pi / 4 + math.pi / 8) + b * math.sin(k * math.pi / 4 + math.pi / 8)) * RIVET_R1 for k in range(8)]
    uvf = metal((0.15, 0.135))
    for k in range(8):
        m.add([ring0[k], ring0[(k + 1) % 8], ring1[(k + 1) % 8], ring1[k]], uvf, ("c", p))
    m.add(ring1, uvf, n)


def box_between(m, p0, p1, w, h, side, uvc, ext=0.0):
    """square-ish bar from p0 to p1; `side` = a direction perpendicular-ish to the bar giving width axis"""
    t = (p1 - p0).normalized()
    p0, p1 = p0 - t * ext, p1 + t * ext
    k1 = (side - t * side.dot(t)).normalized()
    k2 = t.cross(k1).normalized()
    c = (p0 + p1) / 2
    corners = lambda p: [p + k1 * (sx * w / 2) + k2 * (sy * h / 2) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    A, B = corners(p0), corners(p1)
    uvf = metal(uvc)
    for i in range(4):
        m.add([A[i], A[(i + 1) % 4], B[(i + 1) % 4], B[i]], uvf, ("c", c))
    m.add(A, uvf, -t)
    m.add(B, uvf, t)


def plate(m, outline, n, t, uvc, back_closed=False, lod=False):
    """extrude an outline lying on a surface outward along n by t (front face + side walls)"""
    n = Vector(n).normalized()
    top = [p + n * t for p in outline]
    uvf = metal(uvc)
    m.add(top, uvf, n)
    if lod:
        return top
    c = sum(outline, Vector()) / len(outline)
    for i in range(len(outline)):
        a, b = outline[i], outline[(i + 1) % len(outline)]
        mid = (a + b) / 2
        m.add([a, b, top[(i + 1) % len(top)], top[i]], uvf, mid - c)
    return top


# ------------------------------------------------------------------ BODY
def build_core(m, lod):
    # outer walls, split into panels (each panel gets its own island on the wood region)
    tiers = [(Z0, ZK), (ZK, ZT)]
    v_offsets = iter([0.03, 0.24, 0.12, 0.06, 0.27, 0.15, 0.04, 0.09, 0.20, 0.10])
    for face, (es, n) in FACES.items():
        cuts = list(FRONT_STRAPS) if face in ("front", "back") else []
        bounds = [None] + cuts + [None]
        for i in range(len(bounds) - 1):
            sa = (lambda z: -half_len(face, z)) if bounds[i] is None else (lambda z, s=bounds[i]: s)
            sb = (lambda z: half_len(face, z)) if bounds[i + 1] is None else (lambda z, s=bounds[i + 1]: s)
            ref = sa(Z0)
            v0 = next(v_offsets)
            o = Vector((0, 0, Z0))
            if face in ("front", "back"): o.x = ref
            else: o.y = ref
            # grain along the face (v), plank stack upward (u): planks stay aligned across panels
            uvf = uv_axes(o, Vector((0, 0, 1)), es, 0.600, v0, D_WOOD, D_WOOD)
            for z0, z1 in tiers:
                q = [surf(face, sa(z0), z0), surf(face, sb(z0), z0), surf(face, sb(z1), z1), surf(face, sa(z1), z1)]
                m.add(q, uvf, n)
    # top rim + inner walls + floor
    W, D = hw(ZT), hd(ZT)
    outer = [Vector((-W, -D, ZT)), Vector((W, -D, ZT)), Vector((W, D, ZT)), Vector((-W, D, ZT))]
    inner = [Vector((-W + WALL, -D + WALL, ZT)), Vector((W - WALL, -D + WALL, ZT)), Vector((W - WALL, D - WALL, ZT)), Vector((-W + WALL, D - WALL, ZT))]
    for i in range(4):
        a, b = outer[i], outer[(i + 1) % 4]
        along = (b - a).normalized()
        across = Vector((0, 0, 1)).cross(along)
        m.add([a, b, inner[(i + 1) % 4], inner[i]], uv_axes(a, across, along, 0.62, 0.30, D_WOOD, D_WOOD), (0, 0, 1))
    c_in = Vector((0, 0, (ZF + ZT) / 2))
    for i in range(4):
        a, b = inner[i], inner[(i + 1) % 4]
        q = [a, b, Vector((b.x, b.y, ZF)), Vector((a.x, a.y, ZF))]
        cq = sum(q, Vector()) / 4
        m.add(q, dark, c_in - cq)          # faces inward
    m.add([Vector((p.x, p.y, ZF)) for p in inner], dark, (0, 0, 1))
    if not lod:
        Wb, Db = hw(Z0), hd(Z0)
        m.add([Vector((-Wb, -Db, Z0)), Vector((Wb, -Db, Z0)), Vector((Wb, Db, Z0)), Vector((-Wb, Db, Z0))], dark, (0, 0, -1))


PERIM = ["front", "right", "back", "left"]


def corner_s(face, z, end, t):
    """s of a face's end (end=-1 start, +1 end) pushed out to the offset corner"""
    return end * (half_len(face, z) + t)


def build_band(m, z0, z1, u0, lod, rivets=True, t=BAND_T, seed=0):
    rng = random.Random(seed)
    rows = [z0, ZK, z1] if z0 < ZK < z1 else [z0, z1]
    vrun = 0.0
    for face in PERIM:
        es, n = FACES[face]
        L = 2 * half_len(face, z0)
        nseg = 1 if lod else max(2, int(round(L / 0.55)))
        # breakpoints in fraction 0..1 along the side (corners at 0 and 1 are clean, inner ones wobble)
        fr = [i / nseg for i in range(nseg + 1)]
        jz = [0.0] + [rng.uniform(-0.012, 0.012) for _ in range(nseg - 1)] + [0.0]
        jt = [0.0] + [rng.uniform(-0.006, 0.004) for _ in range(nseg - 1)] + [0.0]
        # direction of travel: front -> +x, right -> +y, back -> -x, left -> -y (counter-clockwise from above)
        sgn = 1 if face in ("front", "right") else -1

        def P(k, z, tt):
            hl = half_len(face, z) + tt
            s = sgn * (-hl + 2 * hl * fr[k])
            return surf(face, s, z, tt)

        o = P(0, z0, 0.0)
        along = es * sgn
        uvf = uv_axes(o, Vector((0, 0, 1)), along, u0, vrun * D_BAND, D_METAL, D_BAND)
        # chamfered profile (z, t-fraction): edge at 45% thickness, flat face inset 0.022 from each edge
        CH = 0.022
        prof = [(z0, 0.45), (z0 + CH, 1.0)] + [(z, 1.0) for z in rows[1:-1]] + [(z1 - CH, 1.0), (z1, 0.45)]
        if lod:
            prof = [(z, 1.0) for z in rows]
        for k in range(nseg):
            for r in range(len(prof) - 1):
                (za, fa), (zb, fb) = prof[r], prof[r + 1]
                q = [P(k, za + jz[k], (t + jt[k]) * fa), P(k + 1, za + jz[k + 1], (t + jt[k + 1]) * fa),
                     P(k + 1, zb + jz[k + 1], (t + jt[k + 1]) * fb), P(k, zb + jz[k], (t + jt[k]) * fb)]
                m.add(q, uvf, n + Vector((0, 0, 0.8 if fb < fa else (-0.8 if fa < fb else 0))))
            # top cap
            ft = prof[-1][1]
            m.add([P(k, z1 + jz[k], 0.0), P(k + 1, z1 + jz[k + 1], 0.0), P(k + 1, z1 + jz[k + 1], (t + jt[k + 1]) * ft), P(k, z1 + jz[k], (t + jt[k]) * ft)], uvf, (0, 0, 1))
            if not lod:
                fb0 = prof[0][1]
                m.add([P(k, z0 + jz[k], 0.0), P(k + 1, z0 + jz[k + 1], 0.0), P(k + 1, z0 + jz[k + 1], (t + jt[k + 1]) * fb0), P(k, z0 + jz[k], (t + jt[k]) * fb0)], uvf, (0, 0, -1))
        vrun += L
        if rivets and not lod:
            zc = (z0 + z1) / 2
            hl = half_len(face, zc)
            nr = max(1, int((2 * hl - 0.9) / 0.50))
            for i in range(nr + 1):
                s = -hl + 0.45 + i * (2 * hl - 0.9) / max(1, nr)
                if face in ("front", "back") and any(abs(s - x) < 0.12 for x in FRONT_STRAPS + (0.0,)):
                    continue
                if face in ("left", "right") and abs(s) < 0.12:
                    continue
                rivet(m, surf(face, s, zc, t), n)


def build_strap(m, face, s, lod, w=STRAP_W, t=STRAP_T, z0=Z0 + 0.01, z1=ZT - 0.01):
    es, n = FACES[face]
    rows = [z0, ZK, z1]
    uvc = metal_spot(0.2)
    o = surf(face, s, z0, t)
    uvf = uv_axes(o, es, Vector((0, 0, 1)), uvc[0], 0.05, D_METAL, D_BAND)
    for r in range(2):
        za, zb = rows[r], rows[r + 1]
        m.add([surf(face, s - w / 2, za, t), surf(face, s + w / 2, za, t), surf(face, s + w / 2, zb, t), surf(face, s - w / 2, zb, t)], uvf, n)
        if not lod:
            for sx in (-1, 1):
                ss = s + sx * w / 2
                m.add([surf(face, ss, za, 0), surf(face, ss, zb, 0), surf(face, ss, zb, t), surf(face, ss, za, t)], uvf, es * sx)
    if not lod:
        m.add([surf(face, s - w / 2, z1, 0), surf(face, s + w / 2, z1, 0), surf(face, s + w / 2, z1, t), surf(face, s - w / 2, z1, t)], uvf, (0, 0, 1))
        for zr in (0.35, 0.74):
            rivet(m, surf(face, s, zr, t), n)


CORNERS = [("front", -1, "left", -1), ("front", 1, "right", -1), ("back", 1, "right", 1), ("back", -1, "left", 1)]


def build_corner(m, corner, za, zb, spike_out, spike_up, lod):
    fa, ea, fb, eb = corner
    zm = (za + zb) / 2
    t = PLATE_T
    uvc = metal_spot(0.5)
    uvf = metal(uvc)
    wing_outline = [(-t, za), (0.17, za), (0.32, zm), (0.17, zb), (-t, zb)]  # (d into face, z)

    def W(face, end, d, z, tt):
        hl = half_len(face, z)
        s = end * (hl - d) if d >= 0 else end * (hl + tt)
        return surf(face, s, z, tt)

    corner_mid = None
    for face, end in ((fa, ea), (fb, eb)):
        n = FACES[face][1]
        top = [W(face, end, d, z, t) for d, z in wing_outline]
        m.add(top, uvf, n)
        if not lod:
            base = [W(face, end, max(d, 0.0), z, 0.0) for d, z in wing_outline]
            cpl = sum(base, Vector()) / len(base)
            for i in range(4):  # skip the corner edge (shared with the other wing)
                a, b = base[i], base[i + 1]
                m.add([a, b, top[i + 1], top[i]], uvf, (a + b) / 2 - cpl)
            rivet(m, W(face, end, 0.13, za + 0.08, t), n)
            rivet(m, W(face, end, 0.13, zb - 0.08, t), n)
    # spike (pyramid on the corner)
    diag = (FACES[fa][1] + FACES[fb][1]).normalized()
    base = [W(fa, ea, 0.075, zm - 0.075, t), W(fb, eb, 0.075, zm - 0.075, t), W(fb, eb, 0.075, zm + 0.075, t), W(fa, ea, 0.075, zm + 0.075, t)]
    cb = sum(base, Vector()) / 4
    tip = W(fa, ea, -1, zm, t) + diag * spike_out + Vector((0, 0, spike_up))
    for i in range(4):
        m.add([base[i], base[(i + 1) % 4], tip], uvf, ((base[i] + base[(i + 1) % 4]) / 2 + tip) / 2 - cb)


def build_foot(m, corner, lod):
    fa, ea, fb, eb = corner
    sx = ea if fa in ("front", "back") else eb
    sy = -1 if fa == "front" else 1
    cx, cy = sx * (hw(Z0) - 0.10), sy * (hd(Z0) - 0.10)
    rings = [(0.25, 0.0), (0.25, 0.07), (0.19, 0.15)] if not lod else [(0.25, 0.0), (0.19, 0.15)]
    R = [[Vector((cx + a * r, cy + b * r, z)) for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1))] for r, z in rings]
    uvf = metal(metal_spot(0.5))
    c = Vector((cx, cy, 0.0))
    for j in range(len(R) - 1):
        for i in range(4):
            m.add([R[j][i], R[j][(i + 1) % 4], R[j + 1][(i + 1) % 4], R[j + 1][i]], uvf, ("c", c))
    m.add(R[-1], uvf, (0, 0, 1))


def build_handle(m, face, lod):
    es, n = FACES[face]
    zc = 0.73
    uvc = metal_spot(0.6)
    for s in (-0.25, 0.25):
        q = [surf(face, s - 0.055, zc - 0.075, 0), surf(face, s + 0.055, zc - 0.075, 0), surf(face, s + 0.055, zc + 0.075, 0), surf(face, s - 0.055, zc + 0.075, 0)]
        plate(m, q, n, 0.03, uvc, lod=lod)
        rivet(m, surf(face, s, zc + 0.035, 0.03), n, lod=lod)
    path = [surf(face, -0.25, zc - 0.03, 0.03), surf(face, -0.25, zc - 0.15, 0.11), surf(face, 0.25, zc - 0.15, 0.11), surf(face, 0.25, zc - 0.03, 0.03)]
    if lod:
        box_between(m, path[1], path[2], 0.04, 0.04, n, uvc, 0.02)
        return
    for i in range(3):
        box_between(m, path[i], path[i + 1], 0.04, 0.04, es if i != 1 else n, uvc, 0.02)


def build_hinge_leaves(m, lod):
    for x in HINGES:
        q = [surf("back", x - 0.08, ZT - 0.005, 0), surf("back", x - 0.08, 1.10, 0), surf("back", x, 1.01, 0),
             surf("back", x + 0.08, 1.10, 0), surf("back", x + 0.08, ZT - 0.005, 0)]
        plate(m, q, (0, 1, 0), 0.036, metal_spot(0.3), lod=lod)
        rivet(m, surf("back", x, 1.20, 0.036), (0, 1, 0), lod=lod)
        rivet(m, surf("back", x, 1.08, 0.036), (0, 1, 0), lod=lod)


def build_staple(m, lod):
    if lod:
        return
    uvc = metal_spot(0.2)
    p = [surf("front", 0, 1.13, 0.0), surf("front", 0, 1.13, 0.115), surf("front", 0, 1.23, 0.115), surf("front", 0, 1.23, 0.0)]
    for i in range(3):
        box_between(m, p[i], p[i + 1], 0.03, 0.03, Vector((1, 0, 0)), uvc, 0.015)


def build_body(lod):
    RNG.seed(11 if not lod else 11)
    m = Mesh("StrongboxBodyLOD" if lod else "StrongboxBody")
    build_core(m, lod)
    for i, (z0, z1) in enumerate(BAND_ZS):
        build_band(m, z0, z1, (0.150, 0.170, 0.190, 0.160)[i], lod, seed=100 + i)
    for s in FRONT_STRAPS:
        build_strap(m, "front", s, lod)
        build_strap(m, "back", s, lod)
    for f in ("left", "right"):
        build_strap(m, f, 0.0, lod)
    for c in CORNERS:
        build_corner(m, c, 0.06, 0.52, 0.22, 0.03, lod)
        build_corner(m, c, 0.84, 1.31, 0.13, 0.17, lod)
        build_foot(m, c, lod)
    for f in ("left", "right"):
        build_handle(m, f, lod)
    build_hinge_leaves(m, lod)
    build_staple(m, lod)
    return m


# ------------------------------------------------------------------ LID
WL = hw(ZT) + LID_OVER
DL = hd(ZT) + LID_OVER
PROFILE = [(-DL, ZT), (-DL, LID_EDGE), (0.0, LID_CROWN), (DL, LID_EDGE), (DL, ZT)]   # (y, z), front -> back
HINGE_Y, HINGE_Z = DL + 0.03, ZT
LID_CUTS = (-0.75, 0.0, 0.75)


def build_lid(lod):
    RNG.seed(23)
    m = Mesh("StrongboxLidLOD" if lod else "StrongboxLid")
    xs = [-WL] + list(LID_CUTS) + [WL]
    v_offs = [0.05, 0.22, 0.12, 0.30]
    # lid surfaces between profile points, split in x into panels; grain along x (v), planks stacked over y/z (u)
    seg_u0 = 0.600
    for j in range(len(PROFILE) - 1):
        (ya, za), (yb, zb) = PROFILE[j], PROFILE[j + 1]
        seglen = math.hypot(yb - ya, zb - za)
        a3, b3 = Vector((0, ya, za)), Vector((0, yb, zb))
        across = (b3 - a3).normalized()
        for i in range(len(xs) - 1):
            q = [Vector((xs[i], ya, za)), Vector((xs[i + 1], ya, za)), Vector((xs[i + 1], yb, zb)), Vector((xs[i], yb, zb))]
            o = Vector((xs[i], ya, za))
            outward = Vector((0, (zb - za), -(yb - ya)))      # rotate segment direction by -90 in y/z -> outward
            uvf = uv_axes(o, across, Vector((1, 0, 0)), seg_u0, v_offs[i], D_WOOD, D_WOOD)
            m.add(q, uvf, -outward if outward.dot(Vector((0, (ya + yb) / 2, (za + zb) / 2 - ZT - 0.05))) < 0 else outward)
        seg_u0 += seglen * D_WOOD
        if seg_u0 > 0.95:
            seg_u0 = 0.60
    # end caps (pentagons) and underside
    for sx in (-1, 1):
        pts = [Vector((sx * WL, y, z)) for y, z in PROFILE]
        m.add(pts, uv_axes(Vector((sx * WL, -DL, ZT)), Vector((0, 0, 1)), Vector((0, 1, 0)), 0.62, 0.05, D_WOOD, D_WOOD), (sx, 0, 0))
    # underside: wooden planks (seen when the lid is open), split at the strap cuts like the top
    for i in range(len(xs) - 1):
        q = [Vector((xs[i], -DL, ZT)), Vector((xs[i + 1], -DL, ZT)), Vector((xs[i + 1], DL, ZT)), Vector((xs[i], DL, ZT))]
        m.add(q, uv_axes(Vector((xs[i], -DL, ZT)), Vector((0, 1, 0)), Vector((1, 0, 0)), 0.62, v_offs[-1 - i], D_WOOD, D_WOOD), (0, 0, -1))

    # rim band on the vertical lid faces (front/back/ends)
    rng = random.Random(5)
    rz0, rz1, rt = ZT + 0.012, LID_EDGE - 0.012, 0.025
    sides = [((-WL, -DL), (WL, -DL), (0, -1, 0)), ((WL, -DL), (WL, DL), (1, 0, 0)), ((WL, DL), (-WL, DL), (0, 1, 0)), ((-WL, DL), (-WL, -DL), (-1, 0, 0))]
    vrun = 0.0
    for (ax, ay), (bx, by), n in sides:
        n = Vector(n)
        A, B = Vector((ax, ay, 0)), Vector((bx, by, 0))
        L = (B - A).length
        nseg = 1 if lod else max(2, int(round(L / 0.55)))
        jz = [0.0] + [rng.uniform(-0.008, 0.008) for _ in range(nseg - 1)] + [0.0]
        dirv = (B - A).normalized()

        def P(k, z, tt):
            p = A + (B - A) * (k / nseg) + n * tt
            if k == 0: p = p - dirv * tt
            if k == nseg: p = p + dirv * tt
            return Vector((p.x, p.y, z))
        uvf = uv_axes(P(0, rz0, 0), Vector((0, 0, 1)), dirv, 0.47, vrun * D_BAND, D_METAL, D_BAND)
        for k in range(nseg):
            m.add([P(k, rz0 + jz[k], rt), P(k + 1, rz0 + jz[k + 1], rt), P(k + 1, rz1 + jz[k + 1], rt), P(k, rz1 + jz[k], rt)], uvf, n)
            if not lod:
                m.add([P(k, rz1 + jz[k], 0), P(k + 1, rz1 + jz[k + 1], 0), P(k + 1, rz1 + jz[k + 1], rt), P(k, rz1 + jz[k], rt)], uvf, (0, 0, 1))
                m.add([P(k, rz0 + jz[k], 0), P(k + 1, rz0 + jz[k + 1], 0), P(k + 1, rz0 + jz[k + 1], rt), P(k, rz0 + jz[k], rt)], uvf, (0, 0, -1))
        vrun += L
        if not lod:
            nr = max(1, int(round(L / 0.45)))
            for i in range(nr):
                f = (i + 0.5) / nr
                p = A + (B - A) * f
                if abs(n.y) > 0.5 and any(abs(p.x - x) < 0.12 for x in LID_STRAPS):
                    continue
                rivet(m, Vector((p.x, p.y, (rz0 + rz1) / 2)) + n * rt, n)

    # straps over the lid, front edge -> back hinge
    st = 0.032
    prof = [(-DL, ZT + 0.005)] + PROFILE[1:4] + [(DL, ZT + 0.005)]
    # mitred outward offset of the lid profile (outward = away from a point just above the lid bottom)
    off = []
    for i, (y, z) in enumerate(prof):
        ns = []
        for j in (i - 1, i):
            if 0 <= j < len(prof) - 1:
                (ya, za), (yb, zb) = prof[j], prof[j + 1]
                d = Vector((yb - ya, zb - za)).normalized()
                cand = Vector((d.y, -d.x))
                mid = Vector(((ya + yb) / 2, (za + zb) / 2))
                if cand.dot(mid - Vector((0, ZT + 0.05))) < 0:
                    cand = -cand
                ns.append(cand)
        nn = sum(ns, Vector((0, 0))).normalized()
        k = st / max(0.5, nn.dot(ns[0]))
        off.append((y + nn.x * k, z + nn.y * k))
    for x in LID_STRAPS:
        w = STRAP_W
        uvc = metal_spot(0.3)
        vr = 0.0
        for j in range(len(prof) - 1):
            (ya, za), (yb, zb) = prof[j], prof[j + 1]
            (oya, oza), (oyb, ozb) = off[j], off[j + 1]
            seg = Vector((0, oyb - oya, ozb - oza))
            outward = Vector((0, oya - ya + oyb - yb, oza - za + ozb - zb))
            o = Vector((x - w / 2, oya, oza))
            uvf = uv_axes(o, Vector((1, 0, 0)), seg.normalized(), uvc[0], uvc[1] - 0.15 + vr * D_BAND, D_METAL, D_BAND)
            m.add([Vector((x - w / 2, oya, oza)), Vector((x + w / 2, oya, oza)), Vector((x + w / 2, oyb, ozb)), Vector((x - w / 2, oyb, ozb))], uvf, outward)
            vr += seg.length
            if not lod:
                for sx in (-1, 1):
                    xx = x + sx * w / 2
                    m.add([Vector((xx, ya, za)), Vector((xx, yb, zb)), Vector((xx, oyb, ozb)), Vector((xx, oya, oza))], uvf, (sx, 0, 0))
        if not lod:
            for (y, z), (oy, oz) in ((prof[0], off[0]), (prof[-1], off[-1])):
                m.add([Vector((x - w / 2, y, z)), Vector((x + w / 2, y, z)), Vector((x + w / 2, oy, oz)), Vector((x - w / 2, oy, oz))], metal(uvc), (0, 0, -1))
            for f in (0.3, 0.75):
                for j in (1, 2):
                    (oya, oza), (oyb, ozb) = off[j], off[j + 1]
                    p = Vector((x, oya + (oyb - oya) * f, oza + (ozb - oza) * f))
                    (ya, za), (yb, zb) = prof[j], prof[j + 1]
                    n = Vector((0, oya - ya, oza - za)).normalized()
                    rivet(m, p, n, up=Vector((0, 1, 0)))

    # hinge knuckles (hex barrels on the hinge axis) - rotate with the lid
    if not lod:
        for x in HINGES:
            r, L = 0.045, 0.20
            ring = lambda xx: [Vector((xx, HINGE_Y + r * math.cos(k * math.pi / 3), HINGE_Z + r * math.sin(k * math.pi / 3))) for k in range(6)]
            A, B = ring(x - L / 2), ring(x + L / 2)
            uvf = metal(metal_spot(0.25))
            c = Vector((x, HINGE_Y, HINGE_Z))
            for k in range(6):
                m.add([A[k], A[(k + 1) % 6], B[(k + 1) % 6], B[k]], uvf, ("c", c))
            m.add(A, uvf, (-1, 0, 0))
            m.add(B, uvf, (1, 0, 0))

    # hasp plate hanging from the lid front
    hy0 = -(DL + 0.015)
    outline = [Vector((-0.085, hy0, LID_EDGE + 0.01)), Vector((0.085, hy0, LID_EDGE + 0.01)), Vector((0.085, hy0, 1.15)),
               Vector((0.0, hy0, 1.06)), Vector((-0.085, hy0, 1.15))]
    plate(m, outline, (0, -1, 0), 0.03, metal_spot(0.4), lod=lod)
    if not lod:
        rivet(m, Vector((0, hy0 - 0.03, 1.40)), (0, -1, 0))
        rivet(m, Vector((0, hy0 - 0.03, 1.32)), (0, -1, 0))
    # lid corner caps (small angle plates on the four top corners)
    if not lod:
        for sx in (-1, 1):
            for sy in (-1, 1):
                uvc = metal_spot(0.3)
                cx, cy = sx * WL, sy * DL
                # plate on the end face and on the front/back face, meeting at the corner
                pe = [Vector((cx, cy, ZT + 0.01)), Vector((cx, cy - sy * 0.22, ZT + 0.01)), Vector((cx, cy - sy * 0.22, LID_EDGE)), Vector((cx, cy, LID_EDGE))]
                pf = [Vector((cx, cy, ZT + 0.01)), Vector((cx - sx * 0.22, cy, ZT + 0.01)), Vector((cx - sx * 0.22, cy, LID_EDGE)), Vector((cx, cy, LID_EDGE))]
                plate(m, pe, (sx, 0, 0), 0.034, uvc)
                plate(m, pf, (0, sy, 0), 0.034, uvc)
                rivet(m, Vector((cx + sx * 0.034, cy - sy * 0.12, (ZT + LID_EDGE) / 2)), (sx, 0, 0))
                rivet(m, Vector((cx - sx * 0.12, cy + sy * 0.034, (ZT + LID_EDGE) / 2)), (0, sy, 0))
    return m


def build_collider():
    m = Mesh("StrongboxCollider")
    W0, D0, W1, D1 = hw(Z0) + 0.05, hd(Z0) + 0.05, WL + 0.02, DL + 0.02
    B = [Vector((-W0, -D0, 0)), Vector((W0, -D0, 0)), Vector((W0, D0, 0)), Vector((-W0, D0, 0))]
    T = [Vector((-W1, -D1, LID_CROWN)), Vector((W1, -D1, LID_CROWN)), Vector((W1, D1, LID_CROWN)), Vector((-W1, D1, LID_CROWN))]
    c = Vector((0, 0, 0.7))
    f = lambda pts: [(0.3, 0.5)] * len(pts)
    for i in range(4):
        m.add([B[i], B[(i + 1) % 4], T[(i + 1) % 4], T[i]], f, ("c", c))
    m.add(B, f, (0, 0, -1))
    m.add(T, f, (0, 0, 1))
    return m


# ------------------------------------------------------------------ export
def body_frame(p): return (p.x / BODY_SCALE, p.z / BODY_SCALE, p.y / BODY_SCALE)
def lid_frame(p): return (p.x / BODY_SCALE, p.z / BODY_SCALE - LID_CLOSED_POS[1], p.y / BODY_SCALE)
def body_dir(n): return (n.x, n.z, n.y)
def coll_frame(p): return (-p.x / 0.8, p.z / 0.8, -p.y / 0.8)
def coll_dir(n): return (-n.x, n.z, -n.y)


def write_obj(m, frame, dirf, path):
    tris = m.tris()
    L = [f"# {m.name} - Hauler's Strongbox, generated by blender/strongbox.py",
         "# Unity mesh-local coordinates, written for Jotunn ObjImporter (verbatim axes, clockwise winding, no UV flip)",
         f"# triangles {len(tris)}"]
    V, T, N, F = [], [], [], []
    for (a, b, c), (ua, ub, uc) in tris:
        n = (b - a).cross(c - a)
        if n.length < 1e-12:
            continue
        n.normalize()
        nn = dirf(n)
        base = len(V)
        for p, uv in ((c, uc), (b, ub), (a, ua)):          # reversed = Unity clockwise
            V.append(frame(p)); T.append(uv); N.append(nn)
        F.append((base + 1, base + 2, base + 3))
    L += [f"v {x:.5f} {y:.5f} {z:.5f}" for x, y, z in V]
    L += [f"vt {u:.5f} {v:.5f}" for u, v in T]
    L += [f"vn {x:.4f} {y:.4f} {z:.4f}" for x, y, z in N]
    L += [f"f {a}/{a}/{a} {b}/{b}/{b} {c}/{c}/{c}" for a, b, c in F]
    with open(path, "w", newline="\n") as fh:
        fh.write("\n".join(L) + "\n")
    xs = [v for v in V]
    mn = [round(min(v[i] for v in xs), 4) for i in range(3)]
    mx = [round(max(v[i] for v in xs), 4) for i in range(3)]
    return {"file": os.path.basename(path), "triangles": len(F), "unity_vertices_after_import": len(V), "bounds_min": mn, "bounds_max": mx}


def texel_stats(m):
    acc = {}
    for (a, b, c), (ua, ub, uc) in m.tris():
        wa = (b - a).cross(c - a).length / 2
        ta = abs((ub[0] - ua[0]) * (uc[1] - ua[1]) - (uc[0] - ua[0]) * (ub[1] - ua[1])) / 2 * PX * PX
        cu = ((ua[0] + ub[0] + uc[0]) / 3) % 1.0
        cv = (ua[1] + ub[1] + uc[1]) / 3
        r = "metal" if cu < 0.58 else ("interior" if cv > 0.6 else "wood")
        s = acc.setdefault(r, [0.0, 0.0, 0])
        s[0] += wa; s[1] += ta; s[2] += 1
    return {r: {"tris": n, "px_per_m": round(math.sqrt(ta / wa), 1)} for r, (wa, ta, n) in acc.items() if wa > 0}


def world_bounds(m):
    pts = [p for poly, _ in m.polys for p in poly]
    return [round(min(p[i] for p in pts), 3) for i in range(3)], [round(max(p[i] for p in pts), 3) for i in range(3)]


def main():
    os.makedirs(OUT, exist_ok=True)
    body, body_lod = build_body(False), build_body(True)
    lid, lid_lod = build_lid(False), build_lid(True)
    coll = build_collider()
    files = {
        "body": write_obj(body, body_frame, body_dir, os.path.join(OUT, "StrongboxBody.obj")),
        "body_lod": write_obj(body_lod, body_frame, body_dir, os.path.join(OUT, "StrongboxBodyLOD.obj")),
        "lid": write_obj(lid, lid_frame, body_dir, os.path.join(OUT, "StrongboxLid.obj")),
        "lid_lod": write_obj(lid_lod, lid_frame, body_dir, os.path.join(OUT, "StrongboxLidLOD.obj")),
        "collider": write_obj(coll, coll_frame, coll_dir, os.path.join(OUT, "StrongboxCollider.obj")),
    }
    # hinge + lid transforms (in the vanilla Open/Closed parent frame: localRot 180deg Y, scale 0.9)
    C = Vector(LID_CLOSED_POS)
    h = Vector((0.0, HINGE_Z / BODY_SCALE - C.y, HINGE_Y / BODY_SCALE))     # lid-local hinge point
    a = math.radians(OPEN_ANGLE)
    qx, qw = math.sin(a / 2), math.cos(a / 2)
    Rh = Vector((h.x, h.y * math.cos(a) - h.z * math.sin(a), h.y * math.sin(a) + h.z * math.cos(a)))
    open_pos = C + h - Rh
    bmin, bmax = world_bounds(body)
    lmin, lmax = world_bounds(lid)
    meta = {
        "generated_by": "blender/strongbox.py",
        "units": "metres",
        "frames": {
            "body": "Unity mesh-local of New/blackmetalchest (vanilla node: localRot (0,-1,0,0) = 180deg about Y, localScale 0.9). mesh = (bx, bz, by)/0.9 from Blender world.",
            "lid": "Unity mesh-local of New/Closed/blackmetalchesttop_closed and New/Open/blackmetalchesttop_open. lid = (bx, bz, by)/0.9 - (0, 0.907, 0).",
            "collider": "Unity mesh-local of `collider` (no rotation, localScale 0.8). coll = (-bx, bz, -by)/0.8.",
            "blender_world": "prefab world space, -Y = front, +Z = up (prefab Unity = (-bx, bz, -by))",
        },
        "files": files,
        "world_bounds_closed": {"body_min": bmin, "body_max": bmax, "lid_min": lmin, "lid_max": lmax,
                                 "size_m": [round(max(bmax[0], lmax[0]) - min(bmin[0], lmin[0]), 3),
                                            round(max(bmax[1], lmax[1]) - min(bmin[1], lmin[1]), 3),
                                            round(max(bmax[2], lmax[2]) - min(bmin[2], lmin[2]), 3)],
                                 "note": "size_m in Blender axes: [width X, depth Y, height Z]"},
        "pivot": "body pivot = prefab origin on the ground, centred; same as vanilla",
        "hinge": {"blender_world": [0.0, round(HINGE_Y, 4), round(HINGE_Z, 4)],
                  "lid_local_unity": [0.0, round(h.y, 4), round(h.z, 4)],
                  "axis_lid_local": [1, 0, 0]},
        "lid_transform_closed": {"pos": list(LID_CLOSED_POS), "rot": [0.0, 0.0, 0.0, 1.0], "note": "unchanged vanilla value"},
        "lid_transform_open": {"pos": [0.0, round(open_pos.y, 4), round(open_pos.z, 4)], "rot": [round(qx, 5), 0.0, 0.0, round(qw, 5)],
                               "angle_deg": OPEN_ANGLE, "note": "set on New/Open/blackmetalchesttop_open and ..._openLOD (vanilla was pos (0,1.218,0.016))"},
        "texel_density_px_per_m": {"body": texel_stats(body), "lid": texel_stats(lid), "body_lod": texel_stats(body_lod), "lid_lod": texel_stats(lid_lod),
                                   "vanilla_reference": {"body_wood": 47.1, "body_metal": 78.7, "lid_wood": 57.0, "lid_metal": 65.8}},
        "triangles_vs_vanilla": {"body": [files["body"]["triangles"], 2308], "lid": [files["lid"]["triangles"], 920],
                                 "body_lod": [files["body_lod"]["triangles"], 252], "lid_lod": [files["lid_lod"]["triangles"], 88]},
        "snow_hint": "untested: vanilla floor_2x2_snow sits at y=0.666 (lid top 1.033 m); same offset for the Strongbox lid top (%.3f m) gives y=%.3f, scale about (%.2f,1,%.2f)" % (LID_CROWN, 0.666 + LID_CROWN - 1.033, 0.794 * WL / 0.78, 0.57 * DL / 0.61),
    }
    with open(os.path.join(OUT, "strongbox.json"), "w") as fh:
        json.dump(meta, fh, indent=1)
    print(json.dumps({k: meta[k] for k in ("triangles_vs_vanilla", "world_bounds_closed", "hinge", "lid_transform_open", "texel_density_px_per_m")}, indent=1))

    if "bpy" in sys.modules or "--blend" in sys.argv:
        try:
            import bpy
            bpy.ops.wm.read_factory_settings(use_empty=True)
            for mm, frame in ((body, None), (lid, None), (body_lod, None), (lid_lod, None)):
                me = bpy.data.meshes.new(mm.name)
                verts, faces, uvs = [], [], []
                for pts, uv in mm.polys:
                    faces.append(list(range(len(verts), len(verts) + len(pts))))
                    verts += [tuple(p) for p in pts]; uvs += uv
                me.from_pydata(verts, [], faces)
                ul = me.uv_layers.new(name="UV")
                for i, uv in enumerate(uvs): ul.data[i].uv = uv
                ob = bpy.data.objects.new(mm.name, me)
                bpy.context.scene.collection.objects.link(ob)
                if "LOD" in mm.name: ob.location.x = 4.0
            bpy.context.preferences.filepaths.save_version = 0
            bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "strongbox_source.blend"))
        except Exception as e:
            print("blend save skipped:", e)


if __name__ == "__main__":
    main()
