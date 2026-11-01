"""Meat Rack bundles, ROUND 1: one hung bundle per meat/fish item, built from the game's OWN item model (2-5 copies posed
so they hang from one hook) plus OUR OWN cord (strands from the hook knot and a tight binding where each piece is tied).
Item meshes are a local reference only (C:/Users/joost/ValheimRip/items); nothing of them goes into the exported files.
Run: blender -b -P meatbundles_r1.py -- [--out DIR] [--no-render]
Writes into assets/meatbundles_r1/:  Cord_<Item>.obj (cord only, forward -Z, up Y, triangulated, no materials),
  meatbundles_atlas.png (128x128, point-filtered: v 0.5-1 cord hemp, v 0-0.5 darker binding hemp), bundles.json (last,
  temp + rename: the mod live-reloads).

Hook space: origin = the hook point = centre of the rack's horizontal hook bar where the bundle's cord hangs (in
meatrack_r3: (x, y_cord, beam bottom - 0.075)). The rack frame already carries the hook's short cord and knot down to
0.095 m below that point; our cords start inside that knot. Blender: z up, -y front. JSON/Unity: ux=-bx, uy=bz, uz=-by.
"""
import bpy, bmesh, sys, os, math, json, random
import numpy as np
from mathutils import Vector, Matrix, Quaternion
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
OUTA = os.path.normpath(os.path.join(HERE, "..", "assets", "meatbundles_r1"))
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = argv[argv.index("--out") + 1] if "--out" in argv else \
    "C:/Users/joost/AppData/Local/Temp/claude/C--Users-joost--pai/5e4bc60b-cdfe-4638-8e29-2e507fa13cf9/scratchpad/bundles"
ITEMS_DIR = "C:/Users/joost/ValheimRip/items"
RACK = os.path.normpath(os.path.join(HERE, "..", "assets", "meatrack_r3"))
sys.path.append(ITEMS_DIR)
from load_item import load_item
os.makedirs(OUTA, exist_ok=True); os.makedirs(OUT, exist_ok=True)
rng = random.Random(11)

# ---------- limits (from meatrack_r3: hooks 0.2 m apart along the rails; a ridge bundle hangs 0.125 m in front of /
# behind the upper-rail bundles, whose pieces start 0.365 m below the ridge hooks; upper and lower rail bundles are 0.186 m apart) ----------
MAX_W, MAX_D, MAX_H = 0.19, 0.13, 0.45       # x across the rail, y depth, z down from the hook point
KNOT_Z = -0.095                              # the frame's knot centre (0.035 cube)
K = Vector((0, 0, -0.105))                   # where our strands leave the knot (inside it)
TIE_Z = -0.13                                # tie points of a bunch

# ---------- atlas ----------
TEX = 128
CORD_RECT = (0.0, 0.5, 1.0, 1.0)             # u0, v0, u1, v1
BIND_RECT = (0.0, 0.0, 1.0, 0.5)
def srgb(c): return np.array(c, dtype=np.float32)
CORD, CORD_D = srgb((0.40, 0.32, 0.21)), srgb((0.26, 0.20, 0.12))
BIND, BIND_D = srgb((0.32, 0.25, 0.16)), srgb((0.18, 0.13, 0.08))

def build_atlas():
    nr = np.random.default_rng(5)
    img = np.zeros((TEX, TEX, 3), np.float32)        # row 0 = v 0
    yy, xx = np.mgrid[0:64, 0:TEX].astype(np.float32)
    nz = nr.random((64, TEX))
    twist = np.where(((xx + yy * 0.6) % 6) < 3, 0.0, 1.0) * 0.55 + nz * 0.3      # cord: diagonal twist along u
    img[64:128] = CORD * (1 - twist[..., None]) + CORD_D * twist[..., None]
    wrap = np.where((yy % 4) < 2, 0.0, 1.0) * 0.5 + np.where(((xx + yy * 1.5) % 9) < 1, 0.4, 0) + nz * 0.25  # turns along u
    img[0:64] = BIND * (1 - np.clip(wrap, 0, 1)[..., None]) + BIND_D * np.clip(wrap, 0, 1)[..., None]
    im = bpy.data.images.new("meatbundles_atlas", TEX, TEX, alpha=False)
    px = np.concatenate([np.clip(img, 0, 1), np.ones((TEX, TEX, 1), np.float32)], 2)
    im.pixels.foreach_set(px.ravel())
    im.filepath_raw = os.path.join(OUTA, "meatbundles_atlas.png"); im.file_format = "PNG"; im.save()
    return im

# ---------- small maths ----------
def Rx(a): return Matrix.Rotation(math.radians(a), 3, "X")
def Ry(a): return Matrix.Rotation(math.radians(a), 3, "Y")
def Rz(a): return Matrix.Rotation(math.radians(a), 3, "Z")
I3 = Matrix.Identity(3)
M_B2U = Matrix(((-1, 0, 0), (0, 0, 1), (0, -1, 0)))
def uvec(v): return [round(-v.x, 4), round(v.z, 4), round(-v.y, 4)]
def uquat(R):
    q = (M_B2U @ R @ M_B2U.transposed()).to_quaternion()
    if q.w < 0: q.negate()
    return [round(q.x, 5), round(q.y, 5), round(q.z, 5), round(q.w, 5)]

# ---------- item templates ----------
TPL = {}
ANCH = {}   # item -> each copy's tie point (hook space), from the last layout
def template(name):
    if name not in TPL:
        info = json.load(open(f"{ITEMS_DIR}/{name}/info.json", encoding="utf-8"))
        obs = load_item(name, anchor="origin")
        ob = obs[0]
        V = [v.co.copy() for v in ob.data.vertices]
        F = [list(p.vertices) for p in ob.data.polygons]
        bpy.data.objects.remove(ob, do_unlink=True)
        bmin, bmax = Vector(info["bounds_min"]), Vector(info["bounds_max"])
        TPL[name] = dict(V=V, F=F, c=(bmin + bmax) / 2, size=bmax - bmin)
    return TPL[name]

# ---------- recipes ----------
# R0 turns the item (Blender item space) so the end it is tied by points up (+z) and its broad side faces front (-y).
# bunch: n copies tied at the top round one point under the knot, fanned; stack: copies one under the other on the cord.
FISH = Rz(90) @ Rx(-90)                       # fish: tail (-y) up, flat side to the front
R = {   # spread / depth: tie ring radius across / front-back (m); fan: tilt away from the cord (deg); bind: binding depth / length
    "RawMeat":     dict(R0=Rx(90), n=3, L=0.30, spread=0.03, fan=9, depth=0.016, yaw=40, bind=0.10),
    "LoxMeat":     dict(R0=Rx(90), n=3, L=0.30, spread=0.03, fan=9, depth=0.016, yaw=40, bind=0.10),
    "DeerMeat":    dict(R0=Rx(-90), n=3, L=0.26, spread=0.03, fan=7, depth=0.018, yaw=12, bind=0.12),
    "NeckTail":    dict(R0=Rx(90), n=4, L=0.30, spread=0.025, fan=7, depth=0.016, yaw=30, bind=0.14),
    "WolfMeat":    dict(R0=Rx(90), n=3, L=0.32, spread=0.025, fan=7, depth=0.015, yaw=15, bind=0.12),
    "AsksvinMeat": dict(R0=Rz(90) @ Rx(90), n=2, L=0.30, spread=0.05, fan=6, depth=0.022, yaw=10, bind=0.12, ang=[195, 15]),
    "BugMeat":     dict(R0=Ry(90), n=3, L=0.32, spread=0.03, fan=7, depth=0.016, yaw=20, bind=0.10),
    "ChickenMeat": dict(R0=Rz(90) @ Ry(90), n=3, L=0.26, spread=0.042, fan=8, depth=0.016, yaw=20, bind=0.14),
    "HareMeat":    dict(R0=Rz(90) @ Ry(-90), n=2, L=0.32, spread=0.025, fan=2, depth=0.024, yaw=6, bind=0.08, ang=[200, 20], tie_z=-0.15),
    "VoltureMeat": dict(R0=Rx(-90), n=2, L=0.30, spread=0.042, fan=6, depth=0.02, yaw=25, bind=0.06),
    "SerpentMeat": dict(R0=Rx(90), n=2, stack=True, L=0.16, yaw=8, bind=0.12),
    "FishRaw":     dict(R0=Rz(90) @ Rx(90), n=4, L=0.27, spread=0.022, fan=8, depth=0.016, yaw=15, bind=0.16),
    "Fish1":       dict(R0=FISH, n=4, L=0.31, spread=0.022, fan=6, depth=0.015, yaw=12, bind=0.12),
    "Fish2":       dict(R0=FISH, n=3, L=0.32, spread=0.025, fan=6, depth=0.015, yaw=12, bind=0.12),
    "Fish3":       dict(R0=FISH, n=3, L=0.32, spread=0.025, fan=6, depth=0.015, yaw=12, bind=0.12),
    "Fish4_cave":  dict(R0=FISH, n=4, L=0.30, spread=0.022, fan=6, depth=0.015, yaw=12, bind=0.12),
    "Fish5":       dict(R0=FISH, n=3, L=0.31, spread=0.025, fan=6, depth=0.015, yaw=12, bind=0.12),
    "Fish6":       dict(R0=FISH, n=4, L=0.31, spread=0.022, fan=6, depth=0.015, yaw=12, bind=0.12),
}
NOT_RIPPED = ["BoneMawSerpentMeat", "Fish7", "Fish8", "Fish9", "Fish10", "Fish11", "Fish12", "Bloodclot", "Entrails"]
GENERIC_BOX = (0.18, 0.11, 0.10)              # Blender x, y(depth), z(height) per copy
GENERIC_N = 3

def posed(name, Rm, s, pos):
    t = template(name)
    return [pos + Rm @ (v * s) for v in t["V"]], t["F"]

def tie_point(P, a, L):
    h = max(p.dot(a) for p in P)
    sel = [p for p in P if p.dot(a) > h - 0.06 * L]
    return sum(sel, Vector()) / len(sel), h

def layout(name, rc, s):
    """Copies as (Rm, pos, axis, length). Bunch: tie points spread round (0, 0, TIE_Z); stack: one under the other."""
    t = template(name)
    out = []
    n = rc["n"]
    if rc.get("stack"):
        top = -0.115
        for i in range(n):
            Rm = Rz(rc["yaw"] * (1 if i % 2 else -1)) @ rc["R0"]
            P = [Rm @ (v * s) for v in t["V"]]
            zmax, zmin = max(p.z for p in P), min(p.z for p in P)
            cx = (max(p.x for p in P) + min(p.x for p in P)) / 2; cy = (max(p.y for p in P) + min(p.y for p in P)) / 2
            pos = Vector((-cx, -cy, top - zmax))
            out.append((Rm, pos, Vector((0, 0, 1)), zmax - zmin))
            top = top - (zmax - zmin) - 0.012
        return out
    # bunch: tie points on a small ring round the cord (left, right, front, back), each piece tilted a little away from
    # the cord, as pieces tied together at the top hang
    anch = []
    ang = rc.get("ang") or {1: [270], 2: [180, 0], 3: [180, 0, 270], 4: [180, 0, 270, 90], 5: [180, 0, 270, 90, 225]}[n]
    for i in range(n):
        ph = math.radians(ang[i])
        d = Vector((math.cos(ph), math.sin(ph) * 0.45, 0))
        tilt = rc["fan"] * (1.0 if abs(math.cos(ph)) > 0.5 else 0.35) + rng.uniform(-1.5, 1.5)
        Rt = Matrix.Rotation(math.radians(tilt), 3, d.cross(Vector((0, 0, 1))).normalized()) if d.length > 1e-6 else I3
        yaw = rc["yaw"] * (1 if i % 2 else -1) + rng.uniform(-5, 5)
        Rm = Rt @ Rz(yaw) @ rc["R0"]
        a = Rt @ Vector((0, 0, 1))
        P = [Rm @ (v * s) for v in t["V"]]
        L = max(p.dot(a) for p in P) - min(p.dot(a) for p in P)
        tp, _ = tie_point(P, a, L)
        # a lopsided piece (its tie end off to one side) turns so its bulk hangs towards the cord, not away from it
        bx = (max(p.x for p in P) + min(p.x for p in P)) / 2 - tp.x
        if bx * math.cos(ph) > 0.004:
            Rm = Rt @ Rz(yaw + 180) @ rc["R0"]
            P = [Rm @ (v * s) for v in t["V"]]
            tp, _ = tie_point(P, a, L)
        if rc.get("one_leg"):
            # hung by its inner hind leg only: tie at that leg's tip and let the body swing under it
            top = max(p.dot(a) for p in P)
            sel = [p for p in P if p.dot(a) > top - 0.12 * L]
            mx = sum(p.x for p in sel) / len(sel)
            grp = [p for p in sel if (p.x - mx) * -math.cos(ph) > 0] or sel
            hz = max(p.z for p in grp)
            grp = [p for p in grp if p.z > hz - 0.04 * L]
            tp = sum(grp, Vector()) / len(grp)
            tl = Rm.inverted() @ tp / s                       # that leg tip in item space
            # centre of mass ~ area-weighted surface centroid (vertex density is highest in the legs)
            acc, wsum = Vector(), 0.0
            for f in t["F"]:
                for j in range(1, len(f) - 1):
                    p0, p1, p2 = P[f[0]], P[f[j]], P[f[j + 1]]
                    w = (p1 - p0).cross(p2 - p0).length; acc += (p0 + p1 + p2) / 3 * w; wsum += w
            com = acc / wsum; v = com - tp
            th = math.degrees(math.atan2(v.x, -v.z)) - rc["fan"] * math.cos(ph)
            Rf = Ry(th)
            Rm = Rf @ Rm; a = Rf @ a
            tp = Rm @ (tl * s)
        A = Vector((math.cos(ph) * rc["spread"], math.sin(ph) * rc["depth"], rc.get("tie_z", TIE_Z) - 0.006 * (i >= 2)))
        anch.append(A)
        out.append((Rm, A - tp, a, L))
    ANCH[name] = anch
    return out

def bundle_box(name, cps, s):
    P = []
    for Rm, pos, a, L in cps: P += posed(name, Rm, s, pos)[0]
    mn = Vector([min(p[j] for p in P) for j in range(3)]); mx = Vector([max(p[j] for p in P) for j in range(3)])
    return mn, mx

def fits(mn, mx, margin=0.0):
    return (max(-mn.x, mx.x) <= MAX_W / 2 - margin and max(-mn.y, mx.y) <= MAX_D / 2 - margin and mn.z >= -MAX_H
            and mx.z <= -0.098)

def solve(name, rc):
    t = template(name)
    up = rc["R0"] @ Vector((0, 0, 1))
    ext = max(v.dot(rc["R0"].transposed() @ Vector((0, 0, 1))) for v in t["V"]) - \
        min(v.dot(rc["R0"].transposed() @ Vector((0, 0, 1))) for v in t["V"])
    s = rc["L"] / ext
    for it in range(80):
        rng.seed(sum(map(ord, name)))
        cps = layout(name, rc, s)
        mn, mx = bundle_box(name, cps, s)
        if fits(mn, mx): break
        if it == 0:
            print("LIMIT", name, "w", round(max(-mn.x, mx.x) * 2, 3), "d", round(max(-mn.y, mx.y) * 2, 3), "bottom", round(mn.z, 3),
                  "top", round(mx.z, 3))
        s *= 0.975
    return s, cps, mn, mx

# ---------- cord geometry (one bmesh per bundle) ----------
class CordMesh:
    def __init__(self):
        self.bm = bmesh.new(); self.uv = self.bm.loops.layers.uv.verify()

    def face(self, pts, rect, along):
        vs = [self.bm.verts.new(p) for p in pts]
        f = self.bm.faces.new(vs)
        f.normal_update()
        n = f.normal
        a = along - n * along.dot(n)
        if a.length < 1e-6: a = n.orthogonal()
        a.normalize(); b = n.cross(a)
        cs = [l.vert.co for l in f.loops]
        us = [(c - cs[0]).dot(a) * 300 / TEX for c in cs]; ws = [(c - cs[0]).dot(b) * 300 / TEX for c in cs]
        u0, v0, u1, v1 = rect
        mg = 1.5 / TEX
        su, sv = max(us) - min(us), max(ws) - min(ws)
        k = min(1.0, (u1 - u0 - 2 * mg) / max(su, 1e-6), (v1 - v0 - 2 * mg) / max(sv, 1e-6))
        ou = u0 + mg + rng.uniform(0, max(0, (u1 - u0 - 2 * mg) - su * k))
        ov = v0 + mg + rng.uniform(0, max(0, (v1 - v0 - 2 * mg) - sv * k))
        for l, uu, ww in zip(f.loops, us, ws):
            l[self.uv].uv = (ou + (uu - min(us)) * k, ov + (ww - min(ws)) * k)

    def strand(self, p0, p1, r=0.0045, sides=4, rect=CORD_RECT):
        d = (p1 - p0)
        if d.length < 1e-4: return
        t = d.normalized(); e1 = t.orthogonal().normalized(); e2 = t.cross(e1)
        ring = lambda c: [c + (e1 * math.cos(2 * math.pi * (j + 0.5) / sides) + e2 * math.sin(2 * math.pi * (j + 0.5) / sides)) * r
                          for j in range(sides)]
        A, B = ring(p0), ring(p1)
        for j in range(sides):
            jn = (j + 1) % sides
            self.face([A[j], A[jn], B[jn], B[j]], rect, t)

    def bead(self, c, r=0.009, h=0.011, sides=6):
        A = [c + Vector((math.cos(2 * math.pi * j / sides) * r, math.sin(2 * math.pi * j / sides) * r, h / 2)) for j in range(sides)]
        B = [p - Vector((0, 0, h)) for p in A]
        for j in range(sides):
            jn = (j + 1) % sides
            self.face([B[j], B[jn], A[jn], A[j]], BIND_RECT, Vector((0, 0, 1)).cross(A[j] - c))
        self.face(list(A), BIND_RECT, Vector((1, 0, 0))); self.face(list(reversed(B)), BIND_RECT, Vector((1, 0, 0)))

    def band(self, hull, a, half=0.0055):
        """A tight binding: the item's cross-section hull (points in the plane), extruded +-half along the axis a."""
        n = len(hull)
        A = [p + a * half for p in hull]; B = [p - a * half for p in hull]
        for j in range(n):
            jn = (j + 1) % n
            self.face([B[j], B[jn], A[jn], A[j]], BIND_RECT, hull[jn] - hull[j])

    def tris(self):
        return sum(len(f.verts) - 2 for f in self.bm.faces)

def hull2d(pts):
    pts = sorted(set(pts))
    if len(pts) < 3: return pts
    def cross(o, a, b): return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, up = [], []
    for p in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0: lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(up) >= 2 and cross(up[-2], up[-1], p) <= 0: up.pop()
        up.append(p)
    return lo[:-1] + up[:-1]

def simplify(h, k=8):
    h = list(h)
    def area(i):
        a, b, c = h[i - 1], h[i], h[(i + 1) % len(h)]
        return abs((b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1]))
    while len(h) > k: h.pop(min(range(len(h)), key=area))
    return h

def cross_section(P, F, co, no):
    """Points where the posed mesh crosses the plane (co, no)."""
    pts = []
    for f in F:
        for i in range(len(f)):
            p, q = P[f[i]], P[f[(i + 1) % len(f)]]
            dp, dq = (p - co).dot(no), (q - co).dot(no)
            if (dp > 0) != (dq > 0) and abs(dp - dq) > 1e-9:
                pts.append(p + (q - p) * (dp / (dp - dq)))
    return pts

def clusters2d(P2, gap=0.009):
    lab = list(range(len(P2)))
    def find(i):
        while lab[i] != i: lab[i] = lab[lab[i]]; i = lab[i]
        return i
    for i in range(len(P2)):
        for j in range(i + 1, len(P2)):
            if math.hypot(P2[i][0] - P2[j][0], P2[i][1] - P2[j][1]) < gap: lab[find(i)] = find(j)
    groups = {}
    for i in range(len(P2)): groups.setdefault(find(i), []).append(P2[i])
    return list(groups.values())

def diam(g):
    xs = [x for x, _ in g]; ys = [y for _, y in g]
    return math.hypot(max(xs) - min(xs), max(ys) - min(ys))

def flatness(g):
    h = hull2d([(round(x, 5), round(y, 5)) for x, y in g])
    if len(h) < 3: return 0.0
    ar = 0.5 * abs(sum(h[i][0] * h[(i + 1) % len(h)][1] - h[(i + 1) % len(h)][0] * h[i][1] for i in range(len(h))))
    return ar / max(diam(g) ** 2, 1e-9)

def tie(cm, P, F, a, L, depth_frac, grow=0.0028, near=None):
    """A tight binding round the piece's NARROWEST section in its top part (a bone shaft, a fish's tail root, a hare's
    legs), at most depth_frac x 2.5 of its length below its top. Returns [(band ring, band centre)], one per part tied."""
    top = max(p.dot(a) for p in P)
    e1 = a.orthogonal().normalized(); e2 = a.cross(e1)
    best = None
    lo, hi = 0.010, max(0.02, depth_frac * 2.5 * L)
    for k in range(14):
        dd = lo + (hi - lo) * k / 13
        near_pts = [p for p in P if abs(p.dot(a) - (top - dd)) < 0.02] or P
        c = sum(near_pts, Vector()) / len(near_pts)
        co = c + a * ((top - dd) - c.dot(a))
        pts = cross_section(P, F, co, a)
        if len(pts) < 2: continue
        P2 = [((p - co).dot(e1), (p - co).dot(e2)) for p in pts]
        groups = clusters2d(P2)
        # flat parts (fins, fin lobes) are not where you tie: they cut as thin lines
        score = sum(max(diam(g), 0.006) + (0.03 if flatness(g) < 0.15 else 0) for g in groups) * (1 + 0.5 * dd / L)
        if best is None or score < best[0]: best = (score, co, groups)
    if best is None: return []
    _, co, groups = best
    if len(groups) > 2: groups = clusters2d([p for g in groups for p in g], 0.025)   # pieces of one part
    if len(groups) > 2: groups = [[p for g in groups for p in g]]          # several ribs: one band round them all
    if near is not None and len(groups) > 1:                               # tied by one leg only
        def cen(g): return co + e1 * (sum(x for x, _ in g) / len(g)) + e2 * (sum(y for _, y in g) / len(g))
        groups = [min(groups, key=lambda g: (cen(g) - near).length)]
    rings = []
    for g in groups:
        h = hull2d([(round(x, 5), round(y, 5)) for x, y in g])
        if len(h) < 3:   # a flat part: a small square band round it
            gx = sum(x for x, _ in g) / len(g); gy = sum(y for _, y in g) / len(g)
            ext = max([math.hypot(x - gx, y - gy) for x, y in g] + [0.003])
            h = [(gx + ext * math.cos(k * math.pi / 2 + 0.6), gy + ext * math.sin(k * math.pi / 2 + 0.6)) for k in range(4)]
        h = simplify(h, 8 if len(groups) == 1 else 6)
        cx = sum(x for x, _ in h) / len(h); cy = sum(y for _, y in h) / len(h)
        ring = []
        for x, y in h:
            v = Vector((x - cx, y - cy)); l = v.length or 1
            v = v * ((l + grow) / l)
            ring.append(co + e1 * (cx + v.x) + e2 * (cy + v.y))
        cm.band(ring, a)
        rings.append((ring, co + e1 * cx + e2 * cy))
    return rings

def build_cord(name, rc, s, cps):
    cm = CordMesh()
    ties = []
    for i, (Rm, pos, a, L) in enumerate(cps):
        P, F = posed(name, Rm, s, pos)
        near = ANCH[name][i] if rc.get("one_leg") else None
        ties.append((tie(cm, P, F, a, L, rc.get("bind", 0.12), near=near), a))
    if rc.get("stack"):
        prev = K
        for rings, a in ties:
            for ring, centre in rings:
                cm.strand(prev, centre + a * 0.0055)
            if rings: prev = sum((c for _, c in rings), Vector()) / len(rings) - a * 0.0055
    else:
        for rings, a in ties:
            for ring, centre in rings:
                # from the knot to the band point nearest to it (top edge): reads as tied there
                cm.strand(K, min(ring, key=lambda p: (p - K).length) + a * 0.0055)
    return cm

def build_generic():
    cm = CordMesh(); cps = []
    top = -0.115
    knots = []
    for i in range(GENERIC_N):
        bottom = top - GENERIC_BOX[2]
        knots.append(Vector((0, 0, bottom - 0.0055)))
        cps.append(dict(box=GENERIC_BOX, bottom_center=Vector((0, 0, bottom))))
        top = bottom - 0.011
    cm.strand(K, knots[-1] - Vector((0, 0, 0.004)), r=0.0042)
    for k in knots: cm.bead(k)
    return cm, cps

def export_cord(cm, fname):
    me = bpy.data.meshes.new(fname); cm.bm.to_mesh(me)
    for p in me.polygons: p.use_smooth = False
    ob = bpy.data.objects.new(fname, me); bpy.context.scene.collection.objects.link(ob)
    ob.data.materials.append(CMAT)
    bpy.ops.object.select_all(action="DESELECT"); ob.select_set(True)
    bpy.ops.wm.obj_export(filepath=os.path.join(OUTA, fname), export_selected_objects=True, export_materials=False,
                          export_triangulated_mesh=True, forward_axis="NEGATIVE_Z", up_axis="Y", export_uv=True,
                          export_normals=True)
    return ob

# ---------- build ----------
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
atlas = build_atlas()
CMAT = bpy.data.materials.new("cord"); CMAT.use_nodes = True
ti = CMAT.node_tree.nodes.new("ShaderNodeTexImage"); ti.image = atlas; ti.interpolation = "Closest"
CMAT.node_tree.links.new(ti.outputs["Color"], CMAT.node_tree.nodes["Principled BSDF"].inputs["Base Color"])
CMAT.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.9

BUNDLES = {}   # name -> (s, cps, cord object, stats)
doc = {}
for name, rc in R.items():
    s, cps, mn, mx = solve(name, rc)
    rng.seed(sum(map(ord, name)) + 1)
    cm = build_cord(name, rc, s, cps)
    tris = cm.tris()
    ob = export_cord(cm, f"Cord_{name}.obj")
    cmn = Vector([min(v.co[j] for v in ob.data.vertices) for j in range(3)])
    cmx = Vector([max(v.co[j] for v in ob.data.vertices) for j in range(3)])
    mn = Vector([min(mn[j], cmn[j]) for j in range(3)]); mx = Vector([max(mx[j], cmx[j]) for j in range(3)])
    # overlaps between copies (tri pairs), for tuning
    trees = []
    for Rm, pos, a, L in cps:
        P, F = posed(name, Rm, s, pos); trees.append(BVHTree.FromPolygons(P, F))
    ov = sum(len(trees[i].overlap(trees[j])) for i in range(len(trees)) for j in range(i + 1, len(trees)))
    t = template(name)
    copies = []
    for Rm, pos, a, L in cps:
        c = pos + Rm @ (t["c"] * s)
        copies.append({"offset": uvec(pos), "rot_quat_xyzw": uquat(Rm), "bounds_center": uvec(c)})
    umn, umx = Vector((-mx.x, mn.z, -mx.y)), Vector((-mn.x, mx.z, -mn.y))
    doc[name] = {"kind": "stack" if rc.get("stack") else "bunch", "scale": round(s, 5),
                 "item_longest_m": round(s * max(t["size"]), 4), "copies": copies, "cord_obj": f"Cord_{name}.obj",
                 "cord_tris": tris, "extent_min": [round(x, 4) for x in umn], "extent_max": [round(x, 4) for x in umx],
                 "footprint_m": [round(umx.x - umn.x, 4), round(-umn.y, 4), round(umx.z - umn.z, 4)]}
    BUNDLES[name] = (s, cps, ob.data)
    print("BUNDLE", name, "s", round(s, 4), "n", len(cps), "foot w/h/d", doc[name]["footprint_m"], "tris", tris, "overlap", ov,
          "fits", fits(mn, mx))

# every item against every item on the rack's neighbouring hooks (mesh against mesh, items + cords; the frame itself is
# not checked): ridge over upper rail, along a rail, upper over lower rail
def bundle_mesh(name, at, flip):
    s, cps, cob = BUNDLES[name]
    W = Matrix.Translation(at) @ (Matrix.Rotation(math.pi, 4, "Z") if flip else Matrix.Identity(4))
    V, F = [], []
    for Rm, pos, a, L in cps:
        P, Fi = posed(name, Rm, s, pos); b = len(V)
        V += [W @ p for p in P]; F += [[b + i for i in f] for f in Fi]
    b = len(V); V += [W @ v.co for v in cob.vertices]; F += [[b + i for i in p.vertices] for p in cob.polygons]
    return BVHTree.FromPolygons(V, F)
RZ, UZ, LZ = 1.755, 1.52, 1.22
PAIRS = [("ridge/upper", Vector((0.1, -0.09, RZ)), Vector((0.1, -0.215, UZ))),
         ("ridge/upper next", Vector((0.1, -0.09, RZ)), Vector((0.3, -0.215, UZ))),
         ("ridge/ridge", Vector((0.1, -0.09, RZ)), Vector((0.3, 0.09, RZ))),
         ("along rail", Vector((0.1, -0.215, UZ)), Vector((0.3, -0.215, UZ))),
         ("upper/lower", Vector((0.1, -0.215, UZ)), Vector((0.1, -0.401, LZ))),
         ("upper/lower next", Vector((0.1, -0.215, UZ)), Vector((0.3, -0.401, LZ)))]
names_chk = list(R.keys())
clash = []
for tag, pa, pb in PAIRS:
    TA = {n: bundle_mesh(n, pa, False) for n in names_chk}
    TB = {n: bundle_mesh(n, pb, pb.y > 0) for n in names_chk}
    for na in names_chk:
        for nb in names_chk:
            if TA[na].overlap(TB[nb]): clash.append((tag, na, nb))
print("NEIGHBOUR-CLASH", len(clash), clash[:30])

gcm, gcps = build_generic()
gob = export_cord(gcm, "Cord__generic.obj")
doc["_generic"] = {
    "kind": "stack", "cord_obj": "Cord__generic.obj", "cord_tris": gcm.tris(),
    "rule": "for an item with no recipe of its own (modded items, and the vanilla ones not ripped here): turn it so its "
            "longest bounds axis runs along x (across the rail) and its thinnest along z (depth), scale it uniformly to fit "
            "inside fit_box, and put the bottom centre of its fitted bounds at bottom_center. The cord runs down through the "
            "copies' centres with a knot under each.",
    "copies": [{"fit_box": [GENERIC_BOX[0], GENERIC_BOX[2], GENERIC_BOX[1]], "bottom_center": uvec(c["bottom_center"]),
                "align": {"long_axis_to": [1, 0, 0], "thin_axis_to": [0, 0, 1]}} for c in gcps],
    "footprint_m": [GENERIC_BOX[0], round(0.115 + GENERIC_N * (GENERIC_BOX[2] + 0.011), 4), GENERIC_BOX[1]],
}
# a fish recipe for fish that are not ripped (Fish7-12 and modded fish): Fish1's pose, sized by longest side, placed by bounds centre
f1 = doc["Fish1"]
doc["_fish"] = {"kind": "bunch", "cord_obj": "Cord_Fish1.obj", "cord_tris": f1["cord_tris"],
                "rule": "for a fish with no recipe of its own (Fish7-12, modded fish): the vanilla fish models all have the tail "
                        "on the same end (Blender item -y = Unity item -z) and the flat side on x, so Fish1's pose fits: scale so "
                        "the longest bounds side = longest_m, rotate by rot_quat_xyzw, and put the bounds centre at bounds_center.",
                "longest_m": f1["item_longest_m"],
                "copies": [{"rot_quat_xyzw": c["rot_quat_xyzw"], "bounds_center": c["bounds_center"]} for c in f1["copies"]]}

# hook points of the round 3/4 rack (Unity prefab space, same origin as MeatRack.obj), by r4 unit index
anc = json.load(open(os.path.join(HERE, "..", "assets", "meatrack_r4", "MeatRackAnchors.json"), encoding="utf-8"))
ZP = {"ridge": 1.90 - 0.07 - 0.075, "uf": 1.64 - 0.045 - 0.075, "ub": 1.64 - 0.045 - 0.075, "lf": 1.34 - 0.045 - 0.075,
      "lb": 1.34 - 0.045 - 0.075}
hooks = {}
for u in anc["units"]:
    if u["kind"] != "bundle": continue
    hooks[str(u["index"])] = {"row": u["group"], "hook_point": [u["position"][0], round(ZP[u["group"]], 4), u["position"][2]],
                              "faces": "front" if u["position"][2] > 0 else "back"}

doc["_hooks_meatrack_r4"] = hooks
doc["_not_ripped"] = {n: ("_fish" if n.startswith("Fish") else "_generic") for n in NOT_RIPPED}
doc["doc"] = (
    "Meat Rack bundles round 1 (blender/meatbundles_r1.py). One recipe per item prefab: copies of the game's OWN item model "
    "plus our cord. Hook space: origin = the hook point = centre of the rack's horizontal hook bar where the cord hangs "
    "(_hooks_meatrack_r4 lists them per r4 bundle unit, Unity prefab space). Unity axes: x across the rail, y up, z front "
    "(ux=-bx, uy=bz, uz=-by from Blender). Per copy: the item model in ItemVisual's item space (already turned 180 degrees "
    "about up, as for the anchors) gets the uniform `scale` (absolute, on the prefab's native size), then rot_quat_xyzw, "
    "and its ROOT goes to `offset`: copy matrix = T(offset) R(rot) S(scale). bounds_center is where the item's bounds "
    "centre lands with that matrix (use it if you place by bounds centre and turn about it, like StoreModel.Place). "
    "Fill: show the first k copies for a partial stack; the cord is drawn whole. cord_obj is in the same folder: our "
    "own mesh (forward -Z, up Y, load with flipX like the frames), UVs on meatbundles_atlas.png (v 0.5-1 cord hemp, v "
    "0-0.5 binding hemp), not tinted. The rack frame (meatrack_r3) already has each hook's short cord and knot down to "
    "0.095 m below the hook point; our strands start inside that knot. Every bundle stays within 0.19 m across the "
    "rail x 0.11 m deep x 0.45 m below the hook point (hooks are 0.2 m apart; a ridge bundle hangs 0.125 m from the "
    "upper-rail bundles). Back-row hooks (faces=back): turn the whole bundle (copies and cord) 180 degrees about up "
    "through the hook point so its broad side faces the aisle. Items with no recipe: _not_ripped maps them to _fish or "
    "_generic; any other unknown item uses _generic.")
BUNDLES["_generic"] = (None, gcps, gob.data)

# ---------- renders ----------
if "--no-render" not in argv:
    for o in list(sc.collection.objects): bpy.data.objects.remove(o, do_unlink=True)
    IRON = bpy.data.materials.new("iron"); IRON.use_nodes = True
    IRON.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.04, 0.04, 0.04, 1)
    WOODM = bpy.data.materials.new("wood"); WOODM.use_nodes = True
    WOODM.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.13, 0.08, 0.04, 1)
    HEMPM = bpy.data.materials.new("hemp"); HEMPM.use_nodes = True
    HEMPM.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.13, 0.09, 0.05, 1)

    def box(size, loc, mat):
        bpy.ops.mesh.primitive_cube_add(size=1, location=loc); o = bpy.context.active_object
        o.scale = size; o.data.materials.append(mat); return o

    def hang(name, at, flip=False):
        """Hang a bundle with its hook point at `at` (Blender scene); flip = turned 180 degrees about up."""
        s, cps, cob = BUNDLES[name]
        W = Matrix.Translation(at) @ (Matrix.Rotation(math.pi, 4, "Z") if flip else Matrix.Identity(4))
        c = bpy.data.objects.new("cord", cob); sc.collection.objects.link(c); c.matrix_world = W
        made = [c]
        if name == "_generic":
            for cp in cps:
                ob = load_item("Sausages", anchor="origin")[0]
                t = template("Sausages")
                # long axis to x, thin to y, fit the box, bottom centre on the knot
                sz = t["size"]; ax = sorted(range(3), key=lambda i: sz[i])
                cols = [None] * 3
                cols[ax[2]] = Vector((1, 0, 0)); cols[ax[0]] = Vector((0, 1, 0)); cols[ax[1]] = Vector((0, 0, 1))
                Rm = Matrix([[cols[j][i] for j in range(3)] for i in range(3)])
                if Rm.determinant() < 0: cols[ax[1]] = -cols[ax[1]]; Rm = Matrix([[cols[j][i] for j in range(3)] for i in range(3)])
                rs = Rm @ sz
                k = min(GENERIC_BOX[i] / abs(rs[i]) for i in range(3))
                P = [Rm @ (v * k) for v in t["V"]]
                mn = Vector([min(p[j] for p in P) for j in range(3)]); mx = Vector([max(p[j] for p in P) for j in range(3)])
                pos = cp["bottom_center"] - Vector(((mn.x + mx.x) / 2, (mn.y + mx.y) / 2, mn.z))
                ob.matrix_world = W @ Matrix.Translation(pos) @ Rm.to_4x4() @ Matrix.Diagonal((k, k, k, 1))
                made.append(ob)
            return made
        for Rm, pos, a, L in cps:
            ob = load_item(name, anchor="origin")[0]
            ob.matrix_world = W @ Matrix.Translation(pos) @ Rm.to_4x4() @ Matrix.Diagonal((s, s, s, 1))
            made.append(ob)
        return made

    def hook_parts(at, beam_z):   # like meatrack_r3's hook(): a drop from the beam, a bar out to the cord, cord stub, knot
        box((0.022, 0.022, beam_z - at.z + 0.011), (at.x, at.y + 0.05, (beam_z + at.z - 0.011) / 2), IRON)
        box((0.022, 0.072, 0.022), (at.x, at.y + 0.025, at.z), IRON)
        box((0.016, 0.016, 0.07), (at.x, at.y, at.z - 0.05), HEMPM)       # the frame's cord stub and knot
        box((0.035, 0.035, 0.035), (at.x, at.y, at.z + KNOT_Z), HEMPM)

    world = bpy.data.worlds.new("w"); sc.world = world; world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.42, 0.45, 0.5, 1)
    world.node_tree.nodes["Background"].inputs[1].default_value = 0.9
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN")); sun.data.energy = 3.2
    sun.rotation_euler = (math.radians(50), 0, math.radians(25)); sc.collection.objects.link(sun)
    bpy.ops.mesh.primitive_plane_add(size=60)
    gm = bpy.data.materials.new("ground"); gm.use_nodes = True
    gm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.16, 0.14, 0.11, 1)
    bpy.context.active_object.data.materials.append(gm)
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam); sc.camera = cam
    sc.render.engine = "BLENDER_EEVEE_NEXT"
    sc.view_settings.view_transform = "Standard"

    def shoot(fn, tgt, yaw, pitch, dist, res=(1600, 900), lens=50):
        sc.render.resolution_x, sc.render.resolution_y = res
        cam.data.lens = lens
        t = Vector(tgt)
        d = Vector((math.cos(math.radians(pitch)) * math.sin(math.radians(yaw)),
                    -math.cos(math.radians(pitch)) * math.cos(math.radians(yaw)), math.sin(math.radians(pitch))))
        cam.location = t + d * dist; cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
        sc.render.filepath = os.path.join(OUT, fn); bpy.ops.render.render(write_still=True)

    # 1. the row: every bundle on one beam, hooks 0.25 m apart (the rack has 0.2)
    names = list(R.keys()) + ["_generic"]
    BEAM_Z, HZ = 1.9, 1.755
    n = len(names); X0 = -(n - 1) * 0.25 / 2
    box(((n + 1) * 0.25, 0.12, 0.12), (0, 0, BEAM_Z + 0.06), WOODM)
    for i, nm in enumerate(names):
        at = Vector((X0 + i * 0.25, 0, HZ))
        hook_parts(at, BEAM_Z); hang(nm, at)
        tc = bpy.data.curves.new("t", "FONT"); tc.body = nm.strip("_"); tc.size = 0.035; tc.align_x = "CENTER"
        to = bpy.data.objects.new("t", tc); to.location = (at.x, -0.12, 1.22); to.rotation_euler = (math.radians(90), 0, 0)
        sc.collection.objects.link(to)
    shoot("row_all.png", (0, 0, 1.55), 0, 6, 6.2, res=(2400, 900))
    half = n // 2
    shoot("row_3m_a.png", (X0 + (half - 1) * 0.125, 0, 1.55), 0, 8, 3.0, res=(1800, 900), lens=38)
    shoot("row_3m_b.png", (X0 + (half + n - 1) * 0.125, 0, 1.55), 0, 8, 3.0, res=(1800, 900), lens=38)
    for g in range(0, n, 4):
        xs = [X0 + i * 0.25 for i in range(g, min(n, g + 4))]
        shoot(f"close_{g // 4}.png", ((xs[0] + xs[-1]) / 2, 0, 1.55), -12, 6, 1.35, res=(1600, 1000), lens=40)

    # 2. the round 3 rack, every hook filled (one item per row half, like r4), from 3 m: neighbours must not touch
    for o in list(sc.collection.objects):
        if o.type != "LIGHT" and o.name != "cam" and not o.name.startswith("Plane"): bpy.data.objects.remove(o, do_unlink=True)
    bpy.ops.wm.obj_import(filepath=os.path.join(RACK, "MeatRack.obj"), forward_axis="NEGATIVE_Z", up_axis="Y",
                          use_split_objects=False, use_split_groups=False)
    rack = bpy.context.selected_objects[0]
    rm = bpy.data.materials.new("rack"); rm.use_nodes = True
    rt = rm.node_tree.nodes.new("ShaderNodeTexImage"); rt.image = bpy.data.images.load(os.path.join(RACK, "meatrack_atlas.png"))
    rt.interpolation = "Closest"; rm.node_tree.links.new(rt.outputs["Color"], rm.node_tree.nodes["Principled BSDF"].inputs["Base Color"])
    rack.data.materials.clear(); rack.data.materials.append(rm)
    FILL = {"ridge": ["Fish2", "SerpentMeat"], "uf": ["LoxMeat", "HareMeat"], "ub": ["RawMeat", "Fish5"], "lf": ["VoltureMeat", "WolfMeat"],
            "lb": ["AsksvinMeat", "Fish3"]}
    trees = []
    for k, h in hooks.items():
        hp = h["hook_point"]; at = Vector((-hp[0], -hp[2], hp[1]))
        row = h["row"]; nm = FILL[row][0 if at.x < 0 else 1]
        made = hang(nm, at, h["faces"] == "back")
        V, F = [], []
        for o in made:
            base = len(V); V += [o.matrix_world @ v.co for v in o.data.vertices]
            F += [[base + i for i in p.vertices] for p in o.data.polygons]
        trees.append((k, nm, BVHTree.FromPolygons(V, F)))
    # mesh against mesh, every pair of hooks (the frame is not checked)
    touch = [(a[0], a[1], b[0], b[1]) for i, a in enumerate(trees) for b in trees[i + 1:] if a[2].overlap(b[2])]
    print("RACK-TOUCH", len(touch), touch[:12])
    shoot("rack_front.png", (0, 0, 1.25), -20, 12, 3.0, res=(1600, 1000), lens=28)
    shoot("rack_side.png", (0, 0, 1.25), 75, 8, 3.0, res=(1600, 1000), lens=28)

# ---------- json last, temp + rename (the mod live-reloads) ----------
tmp = os.path.join(OUTA, "bundles.json.tmp")
with open(tmp, "w", encoding="utf-8") as f: json.dump(doc, f, indent=1)
os.replace(tmp, os.path.join(OUTA, "bundles.json"))
print("DONE")
