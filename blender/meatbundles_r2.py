"""Meat Rack bundles, ROUND 2: the meat on the hooks as big as the rack allows, measured against the item's TRUE size.

Joost (22 Oct, in game): "the lox meat is way too small, but it looks cute as hell". Round 1 tied 2-5 copies of an item to a
hook and fitted the whole bunch into 0.19 x 0.13 x 0.45 m, which left a single piece at 0.12-0.39x its true size (LoxMeat
0.15x = 0.127 m long, true 0.85 m). Round 2 hangs ONE big piece per hook (or, for small pieces, a string of 2-3 one under the
other, and for flat fish two back to back), each scaled as far as a FULL rack allows without anything touching.

True size: the mod draws a copy as at * part.M (Storehouse.cs Add); part.M is ItemVisual's item space = the prefab ROOT space
WITHOUT the root's own localScale (root.worldToLocalMatrix * renderer.localToWorldMatrix, turned 180 degrees about up), and
MeatBundles.Place gives `at` = T(hook) R(face) T(offset) R(rot) S(scale). So `scale` multiplies the model in root space and the
true size in the world is scale / root scale. Every meat, fish and animal-part prefab here has root scale (1, 1, 1) (the mod's
own log: "Item model 'LoxMeat': 1 mesh(es), size (0.500, 0.543, 0.892), root scale (1.000, 1.000, 1.000)"; the rips agree), so
`scale` IS the fraction of true size, written per recipe as x_true_size.

Why not 0.6-1.0x: the rack (meatrack_r3, kept) has 8 hooks per row 0.20 m apart and its rows step out only 0.125 m (ridge to
upper rail) and 0.186 m (upper to lower) while their pieces overlap in height, and every row can hold any item next to any
other. A piece that hangs past the next row's tops must stay within 0.117 m deep and 0.194 m across (copies of the same item
hang 0.2 m apart). True sizes are 0.43-1.9 m long and 0.12-1.26 m across, so a lox (0.46 x 0.44 m in cross-section) cannot
pass ~0.27x on these hooks, a serpent steak ~0.15x; long thin items (fish, neck tail, wolf meat) get 0.3-0.65x.

The space every recipe (pieces and cord) must stay in, hook space (origin = the hook point, z up, -y = the side the bundle
faces, u = -y outward, v = z): top at v -0.12 (just under the frame's knot), bottom v >= -0.67 (the lower rail's pieces end
at z 0.55, 9 cm over the round-5 bin heaps), inward u >= -0.075, outward u <= 0.055 for v >= -0.235 (the upper rail's pieces
pass the lower rail beam), 0.095 for v in [-0.235, -0.33] (no other row's piece at that height; clear of the next row's
hook iron and knot by 1 cm), 0.042 below; across the rail |x| <= 0.11 (the end hooks clear the A-frame legs). Any two rows then keep >= 8 mm apart wherever they share a height. Across the rail
a recipe must not touch its own copy 0.194 m along x. All of it is checked afterwards mesh against mesh: every item against
every item on every pair of nearby hooks of a full rack, each item at all 40 hooks against the frame.

Run: blender -b -P meatbundles_r2.py -- [--out DIR] [--rip DIR] [--items A,B] [--no-render]
Writes into assets/meatbundles_r2/: Cord_<Item>.obj (our cord only, forward -Z, up Y, triangulated, no materials),
  meatbundles_atlas.png (round 1's, the same hemp), bundles.json (last, temp + rename: the mod live-reloads). Same schema and
  keys as round 1. The mod (MeatBundles.Load) reads the folder meatbundles_r1 BY NAME: round 2 needs that one name changed
  (or a ModelFolder holding these files under that name). Renders go to --out (the scratchpad).
Item rips: C:/Users/joost/ValheimRip/items, and the ones it lacks (cooked meats, Fish7-12, bonemaw, bjorn, blubber, freeze
gland, entrails) from --rip DIR (made with ValheimRip/scripts/items_extract.py, read-only on the game). Nothing of the item
meshes goes into the exported files. Blender: z up, -y front. JSON/Unity: ux=-bx, uy=bz, uz=-by.
"""
import bpy, bmesh, sys, os, math, json, random, time, subprocess
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
OUTA = os.path.normpath(os.path.join(HERE, "..", "assets", "meatbundles_r2"))
R1 = os.path.normpath(os.path.join(HERE, "..", "assets", "meatbundles_r1"))
RACK = os.path.normpath(os.path.join(HERE, "..", "assets", "meatrack_r3"))
R4 = os.path.normpath(os.path.join(HERE, "..", "assets", "meatrack_r4"))
R5 = os.path.normpath(os.path.join(HERE, "..", "assets", "meatrack_r5"))
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
SCR = "C:/Users/joost/AppData/Local/Temp/claude/C--Users-joost--pai/5e4bc60b-cdfe-4638-8e29-2e507fa13cf9/scratchpad/meat2"
OUT = argv[argv.index("--out") + 1] if "--out" in argv else SCR
EXTRA = argv[argv.index("--rip") + 1] if "--rip" in argv else os.path.join(SCR, "rip")
ITEMS_DIR = "C:/Users/joost/ValheimRip/items"
sys.path.append(ITEMS_DIR)
import load_item as LI
os.makedirs(OUTA, exist_ok=True); os.makedirs(OUT, exist_ok=True)
rng = random.Random(11)

def item_dir(name):
    for d in (ITEMS_DIR, EXTRA):
        if os.path.exists(f"{d}/{name}/info.json"): return d
    return None

def load(name, **kw):
    d = item_dir(name); old = LI.ROOT; LI.ROOT = d
    try: return LI.load_item(name, **kw)
    finally: LI.ROOT = old

# ---------- the hook-space envelope (see the docstring) ----------
TOP = -0.12                  # top of the hung pieces (the frame's knot ends at -0.1125)
V_MIN = -0.67
A_IN = 0.075
PITCH, GAPX = 0.2, 0.006
X_HALF = 0.11               # the end hooks (x +-0.7) stay 5 mm clear of the A-frame legs (inner faces at x +-0.815)
GAP_STRING = 0.018
def b_out(v): return np.where(v >= -0.235, 0.055, np.where(v >= -0.33, 0.095, 0.042))
KNOT_Z = -0.095
K = Vector((0, 0, -0.105))   # where our strands leave the frame's knot (inside it)

# ---------- items and how they hang ----------
ONE = ("LoxMeat CookedLoxMeat SerpentMeat SerpentMeatCooked AsksvinMeat CookedAsksvinMeat BoneMawSerpentMeat CookedBoneMawSerpentMeat "
       "VoltureMeat CookedVoltureMeat BugMeat CookedBugMeat HareMeat CookedHareMeat WolfMeat CookedWolfMeat BjornMeat CookedBjornMeat "
       "Fish9 Fish12 Entrails FreezeGland SealBlubber CookedSealBlubber").split()
SMALL = "RawMeat CookedMeat NeckTail NeckTailGrilled ChickenMeat CookedChickenMeat DeerMeat CookedDeerMeat FishRaw FishCooked".split()
FISHP = "Fish1 Fish2 Fish3 Fish4_cave Fish5 Fish6 Fish7 Fish8 Fish10 Fish11".split()
ORDER = ["RawMeat", "LoxMeat", "DeerMeat", "NeckTail", "WolfMeat", "AsksvinMeat", "BugMeat", "ChickenMeat", "HareMeat", "VoltureMeat",
         "SerpentMeat", "BoneMawSerpentMeat", "BjornMeat", "SealBlubber", "Entrails", "FreezeGland", "FishRaw"] + \
        [f"Fish{i}" for i in range(1, 13) if i != 4][:3] + ["Fish4_cave"] + [f"Fish{i}" for i in range(5, 13)] + \
        ["CookedMeat", "CookedLoxMeat", "CookedDeerMeat", "NeckTailGrilled", "CookedWolfMeat", "CookedAsksvinMeat", "CookedBugMeat",
         "CookedChickenMeat", "CookedHareMeat", "CookedVoltureMeat", "SerpentMeatCooked", "CookedBoneMawSerpentMeat", "CookedBjornMeat",
         "CookedSealBlubber", "FishCooked"]
NOT_RIPPED = ["Bloodclot", "BloodBag"]          # not in the item bundle the rips come from
WANT = argv[argv.index("--items") + 1].split(",") if "--items" in argv else ORDER
NAMES = [n for n in ORDER if n in WANT and item_dir(n)]
print("R2 items", len(NAMES), "missing", [n for n in ORDER if n in WANT and n not in NAMES], flush=True)

# ---------- atlas: round 1's hemp ----------
TEX = 128
CORD_RECT = (0.0, 0.5, 1.0, 1.0)
BIND_RECT = (0.0, 0.0, 1.0, 0.5)

# ---------- small maths ----------
def Rz(a): return Matrix.Rotation(math.radians(a), 3, "Z")
M_B2U = Matrix(((-1, 0, 0), (0, 0, 1), (0, -1, 0)))
def uvec(v): return [round(-v[0], 4), round(v[2], 4), round(-v[1], 4)]
def uquat(R):
    q = (M_B2U @ R @ M_B2U.transposed()).to_quaternion()
    if q.w < 0: q.negate()
    return [round(q.x, 5), round(q.y, 5), round(q.z, 5), round(q.w, 5)]
def npm(R): return np.array(R)

# ---------- item templates ----------
TPL = {}
def template(name):
    if name not in TPL:
        info = json.load(open(f"{item_dir(name)}/{name}/info.json", encoding="utf-8"))
        obs = load(name, anchor="origin")
        ob = obs[0]
        V = np.array([v.co[:] for v in ob.data.vertices])
        F = [list(p.vertices) for p in ob.data.polygons]
        for o in obs: bpy.data.objects.remove(o, do_unlink=True)
        bmin, bmax = np.array(info["bounds_min"]), np.array(info["bounds_max"])
        C = V - V.mean(0)
        w, E = np.linalg.eigh(C.T @ C)
        axes = [E[:, i] for i in np.argsort(-w)]                 # long, middle, thin
        TPL[name] = dict(V=V, F=F, c=(bmin + bmax) / 2, size=bmax - bmin, axes=axes, longest=float((bmax - bmin).max()))
    return TPL[name]

def orient(name, up_i, sign, phi):
    """the item turned so its PCA axis up_i (x sign) points up (+z), then turned phi degrees about up."""
    a = Vector(template(name)["axes"][up_i] * sign)
    return Rz(phi) @ a.rotation_difference(Vector((0, 0, 1))).to_matrix()

def end_pref(name, up_i, sign):
    """hang by the narrow end (a fish by its tail, a joint by its bone): 1.0 narrow end up, 0.97 wide end up; 0.94 for the middle axis."""
    if up_i != 0: return 0.94
    t = template(name); a = t["axes"][0] * sign; V = t["V"]
    h = V @ a; L = h.max() - h.min()
    def spread(sel):
        Q = V[sel] - np.outer(h[sel], a); Q -= Q.mean(0); return float(np.sqrt((Q ** 2).sum(1)).max()) if len(Q) else 0
    top = spread(h > h.max() - 0.12 * L); bot = spread(h < h.min() + 0.12 * L)
    return 1.0 if top <= bot else 0.97

# ---------- layouts: pieces (R, offset) in hook space at scale s ----------
def posed(name, Rm, s, pos):
    return npm(Rm) @ (template(name)["V"] * s).T + np.array(pos)[:, None]

def place(name, kind, Rm, s, n=1, sep=None):
    """pieces as [(R, pos)] with tops, x-centres and one common outward shift fitted to the envelope; None if it cannot fit."""
    V = template(name)["V"] * s
    pieces = []
    if kind == "single" or kind == "stack":
        top = TOP
        for i in range(n):
            R = (Rz(5 if i % 2 else -5) @ Rm) if kind == "stack" and n > 1 else Rm
            P = (npm(R) @ V.T).T
            pos = np.array((-(P[:, 0].min() + P[:, 0].max()) / 2, 0.0, top - P[:, 2].max()))
            pieces.append((R, pos))
            top = top - (P[:, 2].max() - P[:, 2].min()) - GAP_STRING
    else:   # pair: A faces front, B (turned 180 about up) faces back, back to back with `sep` between their u-centres
        RB = Rz(180) @ Rm
        for R, su in ((Rm, 0.5), (RB, -0.5)):
            P = (npm(R) @ V.T).T
            uc = -(P[:, 1].min() + P[:, 1].max()) / 2
            pos = np.array((-(P[:, 0].min() + P[:, 0].max()) / 2, -(su * sep - uc), TOP - P[:, 2].max()))
            pieces.append((R, pos))
    allP = np.vstack([(npm(R) @ V.T).T + p for R, p in pieces])
    v = allP[:, 2]; u = -allP[:, 1]
    if v.min() < V_MIN or np.abs(allP[:, 0]).max() > X_HALF: return None
    lo = (-A_IN - u).max(); hi = (b_out(v) - u).min()
    if lo > hi: return None
    du = (lo + hi) / 2
    return [(R, p + np.array((0.0, -du, 0.0))) for R, p in pieces]

def tree(Ps, F, extra=None):
    verts, faces = [], []
    for P in Ps:
        b = len(verts); verts += [Vector(p) for p in P.T]; faces += [[b + i for i in f] for f in F]
    if extra is not None:
        b = len(verts); verts += [Vector(v) for v in extra[0]]; faces += [[b + i for i in f] for f in extra[1]]
    return BVHTree.FromPolygons(verts, faces)

def self_clear(name, s, pieces, cord=None):
    """the recipe against its own copy on the next hook along the rail (PITCH - GAPX along x)."""
    F = template(name)["F"]
    Ps = [posed(name, R, s, p) for R, p in pieces]
    xs = np.concatenate([P[0] for P in Ps] + ([np.array(cord[0])[:, 0]] if cord is not None else []))
    if xs.max() - xs.min() < PITCH - GAPX: return True
    A = tree(Ps, F, cord)
    sh = np.array((PITCH - GAPX, 0, 0))[:, None]
    B = tree([P + sh for P in Ps], F, (np.array(cord[0]) + sh[:, 0], cord[1]) if cord is not None else None)
    return not A.overlap(B)

def pair_sep(name, Rm, s):
    """the smallest distance between the u-centres of a back-to-back pair at which the two pieces do not touch (3 mm air)."""
    V = template(name)["V"] * s; F = template(name)["F"]
    P = (npm(Rm) @ V.T).T; d = P[:, 1].max() - P[:, 1].min()
    lo, hi = 0.0, 2 * d + 0.01
    for _ in range(14):
        mid = (lo + hi) / 2
        pcs = [(Rm, np.array((0, -mid / 2 - 0.0015, 0))), (Rz(180) @ Rm, np.array((0, mid / 2 + 0.0015, 0)))]
        if tree([posed(name, R, s, p) for R, p in pcs[:1]], F).overlap(tree([posed(name, R, s, p) for R, p in pcs[1:]], F)): lo = mid
        else: hi = mid
    return hi + 0.003

def max_scale(name, kind, Rm, n=1, lo=0.03, hi=1.3):
    def ok(s):
        sep = pair_sep(name, Rm, s) if kind == "pair" else None
        pcs = place(name, kind, Rm, s, n, sep)
        return pcs is not None and self_clear(name, s, pcs)
    if not ok(lo): return 0.0
    for _ in range(13):
        mid = (lo + hi) / 2
        if ok(mid): lo = mid
        else: hi = mid
    return lo

def best_orientation(name):
    """every hanging pose (long or middle PCA axis up, either end, 24 turns about up): the largest scale wins, the narrow end up
    and the broad side to the front break ties."""
    best = None
    t = template(name)
    for up_i in (0, 1):
        for sign in (1, -1):
            pref = end_pref(name, up_i, sign)
            for phi in range(0, 360, 15):
                Rm = orient(name, up_i, sign, phi)
                s = max_scale(name, "single", Rm)
                P = (npm(Rm) @ (t["V"] * s).T).T
                wide = (P[:, 0].max() - P[:, 0].min()) / max(1e-6, P[:, 1].max() - P[:, 1].min())
                score = s * pref * (1 + 0.02 * min(wide, 3))
                if best is None or score > best[0]: best = (score, s, Rm, up_i, sign, phi)
    return best

# ---------- cord geometry (round 1's) ----------
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
        n = len(hull)
        A = [p + a * half for p in hull]; B = [p - a * half for p in hull]
        for j in range(n):
            jn = (j + 1) % n
            self.face([B[j], B[jn], A[jn], A[j]], BIND_RECT, hull[jn] - hull[j])

    def tris(self):
        return sum(len(f.verts) - 2 for f in self.bm.faces)

    def arrays(self):
        V = [tuple(v.co) for v in self.bm.verts]; self.bm.verts.index_update()
        return np.array(V), [[v.index for v in f.verts] for f in self.bm.faces]

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

def tie(cm, P, F, a, L, depth_frac=0.12, grow=0.0028):
    """round 1's binding: a tight band round the piece's NARROWEST section in its top part. Returns [(ring, centre)]."""
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
        score = sum(max(diam(g), 0.006) + (0.03 if flatness(g) < 0.15 else 0) for g in groups) * (1 + 0.5 * dd / L)
        if best is None or score < best[0]: best = (score, co, groups)
    if best is None: return []
    _, co, groups = best
    if len(groups) > 2: groups = clusters2d([p for g in groups for p in g], 0.025)
    if len(groups) > 2: groups = [[p for g in groups for p in g]]
    rings = []
    for g in groups:
        h = hull2d([(round(x, 5), round(y, 5)) for x, y in g])
        if len(h) < 3:
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

def build_cord(name, kind, s, pieces):
    cm = CordMesh(); a = Vector((0, 0, 1))
    F = template(name)["F"]
    ties = []
    for R, p in pieces:
        P = [Vector(q) for q in posed(name, R, s, p).T]
        L = max(q.z for q in P) - min(q.z for q in P)
        ties.append(tie(cm, P, F, a, L))
    if kind == "stack":
        prev = K
        for rings in ties:
            for ring, centre in rings: cm.strand(prev, centre + a * 0.0055)
            if rings: prev = sum((c for _, c in rings), Vector()) / len(rings) - a * 0.0055
    else:
        for rings in ties:
            for ring, centre in rings: cm.strand(K, min(ring, key=lambda q: (q - K).length) + a * 0.0055)
    return cm

# ---------- design every recipe ----------
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
atlas = bpy.data.images.load(os.path.join(R1, "meatbundles_atlas.png"))
CMAT = bpy.data.materials.new("cord"); CMAT.use_nodes = True
ti = CMAT.node_tree.nodes.new("ShaderNodeTexImage"); ti.image = atlas; ti.interpolation = "Closest"
CMAT.node_tree.links.new(ti.outputs["Color"], CMAT.node_tree.nodes["Principled BSDF"].inputs["Base Color"])
CMAT.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.9

def export_cord(cm, fname):
    me = bpy.data.meshes.new(fname); cm.bm.to_mesh(me)
    for p in me.polygons: p.use_smooth = False
    ob = bpy.data.objects.new(fname, me); bpy.context.scene.collection.objects.link(ob)
    ob.data.materials.append(CMAT)
    bpy.ops.object.select_all(action="DESELECT"); ob.select_set(True)
    bpy.ops.wm.obj_export(filepath=os.path.join(OUTA, fname), export_selected_objects=True, export_materials=False,
                          export_triangulated_mesh=True, forward_axis="NEGATIVE_Z", up_axis="Y", export_uv=True, export_normals=True)
    return ob

t0 = time.time()
BUNDLES = {}
doc = {}
for name in NAMES:
    t = template(name)
    score, s1, Rm, up_i, sign, phi = best_orientation(name)
    kind, n, s = "single", 1, s1
    if name in SMALL:
        for nn in (3, 2):
            sn = max_scale(name, "stack", Rm, nn, hi=s1 * 1.02)
            if sn >= 0.93 * s1: kind, n, s = "stack", nn, sn; break
    elif name in FISHP:
        sp = max_scale(name, "pair", Rm, 2, hi=s1 * 1.02)
        if sp >= 0.95 * s1: kind, n, s = "pair", 2, sp
    # cord and bindings; shrink 2% at a time until pieces + cord clear the envelope and the next hook
    for it in range(25):
        sep = pair_sep(name, Rm, s) if kind == "pair" else None
        pieces = place(name, kind, Rm, s, n, sep)
        if pieces is None: s *= 0.98; continue
        rng.seed(sum(map(ord, name)) + 1)
        cm = build_cord(name, kind, s, pieces)
        CV, CF = cm.arrays()
        okenv = (np.abs(CV[:, 0]) <= X_HALF).all() and (-CV[:, 1] >= -A_IN - 1e-4).all() and (-CV[:, 1] <= b_out(CV[:, 2]) + 1e-4).all() and CV[:, 2].min() >= V_MIN
        if okenv and self_clear(name, s, pieces, (CV, CF)): break
        cm.bm.free(); s *= 0.98
    ob = export_cord(cm, f"Cord_{name}.obj")
    Ps = [posed(name, R, s, p) for R, p in pieces]
    allP = np.hstack(Ps + [CV.T])
    mn, mx = allP.min(1), allP.max(1)
    copies = []
    for R, p in pieces:
        c = Vector(p) + R @ (Vector(t["c"]) * s)
        copies.append({"offset": uvec(Vector(p)), "rot_quat_xyzw": uquat(R), "bounds_center": uvec(c)})
    umn, umx = [-mx[0], mn[2], -mx[1]], [-mn[0], mx[2], -mn[1]]
    doc[name] = {"kind": kind, "scale": round(s, 5), "x_true_size": round(s, 4), "true_longest_m": round(t["longest"], 4),
                 "item_longest_m": round(s * t["longest"], 4), "copies": copies, "cord_obj": f"Cord_{name}.obj", "cord_tris": cm.tris(),
                 "extent_min": [round(x, 4) for x in umn], "extent_max": [round(x, 4) for x in umx],
                 "footprint_m": [round(umx[0] - umn[0], 4), round(-umn[1], 4), round(umx[2] - umn[2], 4)],
                 "pose": {"hung_by": ("long" if up_i == 0 else "middle") + " axis, " + ("narrow" if end_pref(name, up_i, sign) == 1.0 else "wide") + " end up",
                          "turn_deg": phi}}
    BUNDLES[name] = (s, pieces, ob.data, kind)
    print("R2 %-24s %-6s n %d  x%.3f true  piece %.3f m (r1 %s)  footprint w/h/d %s  %.0fs" % (
        name, kind, n, s, s * t["longest"], "-", doc[name]["footprint_m"], time.time() - t0), flush=True)

# ---------- checks: a full rack, mesh against mesh ----------
anc = json.load(open(os.path.join(R4, "MeatRackAnchors.json"), encoding="utf-8"))
ZP = {"ridge": 1.90 - 0.07 - 0.075, "uf": 1.64 - 0.045 - 0.075, "ub": 1.64 - 0.045 - 0.075, "lf": 1.34 - 0.045 - 0.075,
      "lb": 1.34 - 0.045 - 0.075}
hooks = {}
for u in anc["units"]:
    if u["kind"] != "bundle": continue
    hooks[str(u["index"])] = {"row": u["group"], "hook_point": [u["position"][0], round(ZP[u["group"]], 4), u["position"][2]],
                              "faces": "front" if u["position"][2] > 0 else "back"}
def hook_frame(h):
    hp = h["hook_point"]; at = np.array((-hp[0], -hp[2], hp[1]))
    R = npm(Rz(180)) if h["faces"] == "back" else np.eye(3)
    return at, R

LOCAL = {}
def local_mesh(name):
    """pieces + cord of a recipe in hook space: (V 3xN, F, cordV, cordF)."""
    if name not in LOCAL:
        s, pieces, cme, kind = BUNDLES[name]
        F = template(name)["F"]; V, FF = [], []
        for R, p in pieces:
            P = posed(name, R, s, p); b = sum(x.shape[1] for x in V); V.append(P); FF += [[b + i for i in f] for f in F]
        V = np.hstack(V)
        CV = np.array([v.co[:] for v in cme.vertices]).T; CF = [list(p.vertices) for p in cme.polygons]
        LOCAL[name] = (V, FF, CV, CF)
    return LOCAL[name]
def world_tree(name, at, R, with_cord=True):
    V, F, CV, CF = local_mesh(name)
    W = R @ V + at[:, None]; verts = [Vector(p) for p in W.T]; faces = list(F)
    lo, hi = W.min(1), W.max(1)
    if with_cord:
        WC = R @ CV + at[:, None]; b = len(verts); verts += [Vector(p) for p in WC.T]; faces += [[b + i for i in f] for f in CF]
        lo, hi = np.minimum(lo, WC.min(1)), np.maximum(hi, WC.max(1))
    return BVHTree.FromPolygons(verts, faces), lo, hi

names_chk = list(BUNDLES)
H = {k: hook_frame(h) for k, h in hooks.items()}
# nearby hook pairs, deduplicated by their relative placement (the check is the same anywhere along the rack)
rel = {}
keys = sorted(H, key=int)
for i, a in enumerate(keys):
    for b in keys[i + 1:]:
        (pa, Ra), (pb, Rb) = H[a], H[b]
        if np.linalg.norm(pa - pb) > 0.75: continue
        same = hooks[a]["row"] == hooks[b]["row"]
        k = (tuple(np.round(Ra.T @ (pb - pa), 3)), hooks[a]["faces"], hooks[b]["faces"], same)
        rel.setdefault(k, (a, b))
t1 = time.time()
clash = []; tests = 0
for (d, fa, fb, same), (a, b) in rel.items():
    (pa, Ra), (pb, Rb) = H[a], H[b]
    TA = {n: world_tree(n, pa, Ra) for n in names_chk}
    TB = {n: world_tree(n, pb, Rb) for n in names_chk}
    for na in names_chk:
        for nb in (names_chk if not same else [na]):
            ta, tb = TA[na], TB[nb]
            if (ta[1] > tb[2]).any() or (tb[1] > ta[2]).any(): continue
            tests += 1
            if ta[0].overlap(tb[0]): clash.append((hooks[a]["row"], hooks[b]["row"], d, na, nb))
print("R2 RACK-CLASH", len(clash), "of", tests, "mesh tests over", len(rel), "hook relations x", len(names_chk), "items", clash[:12],
      "%.0fs" % (time.time() - t1), flush=True)

# each item at all 40 hooks against the frame (its loose parts; the frame's own knots and cord stubs, which our strands start
# inside by design, are left out)
bpy.ops.wm.obj_import(filepath=os.path.join(RACK, "MeatRack.obj"), forward_axis="NEGATIVE_Z", up_axis="Y", use_split_objects=False, use_split_groups=False)
fob = bpy.context.selected_objects[0]
bm = bmesh.new(); bm.from_mesh(fob.data); bm.transform(fob.matrix_world); bm.verts.ensure_lookup_table()   # the importer turns the object
comp = [-1] * len(bm.verts); ncomp = 0
for v in bm.verts:
    if comp[v.index] >= 0: continue
    st = [v]
    while st:
        x = st.pop()
        if comp[x.index] >= 0: continue
        comp[x.index] = ncomp
        for e in x.link_edges: st.append(e.other_vert(x))
    ncomp += 1
cv = np.array([v.co[:] for v in bm.verts]); keep = []
for c in range(ncomp):
    sel = np.where(np.array(comp) == c)[0]; ext = cv[sel].max(0) - cv[sel].min(0)
    small = (ext.max() < 0.045) or (sorted(ext)[1] < 0.02 and ext.max() < 0.09)     # a knot (0.035 cube) or a cord stub (0.016 x 0.07)
    if not small: keep.append(c)
keep = set(keep)
fverts = [Vector(p) for p in cv]
ffaces = [[v.index for v in f.verts] for f in bm.faces if comp[f.verts[0].index] in keep]
bm.free(); bpy.data.objects.remove(fob)
FRAME = BVHTree.FromPolygons(fverts, ffaces)
frame_hits = []
for k, (at, R) in H.items():
    for n in names_chk:
        tr, lo, hi = world_tree(n, at, R)
        if tr.overlap(FRAME): frame_hits.append((hooks[k]["row"], k, n))
print("R2 FRAME-CLASH", len(frame_hits), frame_hits[:12], flush=True)
low = min(float((local_mesh(n)[0][2]).min()) for n in names_chk)
heap = None
if os.path.exists(os.path.join(R5, "MeatRackAnchors.json")):
    heap = json.load(open(os.path.join(R5, "MeatRackAnchors.json")))["stats_r5"]["heap_top_max_z_m"]
print("R2 LOWEST piece bottom z %.3f (lower rail hook 1.22 %+.3f); bin heaps top z %s" % (1.22 + low, low, heap), flush=True)

# ---------- json ----------
gcm = CordMesh(); top = -0.115; knots = []
GENERIC_BOX = (0.18, 0.10, 0.20)
for i in range(2):
    bottom = top - GENERIC_BOX[2]; knots.append(Vector((0, 0, bottom - 0.0055))); top = bottom - 0.011
gcm.strand(K, knots[-1] - Vector((0, 0, 0.004)), r=0.0042)
for k in knots: gcm.bead(k)
export_cord(gcm, "Cord__generic.obj")
doc["_generic"] = {
    "kind": "stack", "cord_obj": "Cord__generic.obj", "cord_tris": gcm.tris(),
    "rule": "(documentation: the mod skips keys starting with '_'; an item with no recipe keeps the anchors' bundle) for an item with "
            "no recipe of its own: turn it so its longest bounds axis runs along x and its thinnest along z (depth), scale it uniformly "
            "to fit inside fit_box, and put the bottom centre of its fitted bounds at bottom_center.",
    "copies": [{"fit_box": [GENERIC_BOX[0], GENERIC_BOX[2], GENERIC_BOX[1]], "bottom_center": uvec(k + Vector((0, 0, 0.0055))),
                "align": {"long_axis_to": [1, 0, 0], "thin_axis_to": [0, 0, 1]}} for k in knots],
    "footprint_m": [GENERIC_BOX[0], round(0.115 + 2 * (GENERIC_BOX[2] + 0.011), 4), GENERIC_BOX[1]]}
if "Fish1" in doc:
    f1 = doc["Fish1"]
    doc["_fish"] = {"kind": f1["kind"], "cord_obj": f1["cord_obj"], "cord_tris": f1["cord_tris"],
                    "rule": "(documentation) for a fish with no recipe of its own (modded fish): the vanilla fish models have the tail on the "
                            "same end, so Fish1's pose fits: scale so the longest bounds side = longest_m, rotate by rot_quat_xyzw, put the "
                            "bounds centre at bounds_center. All twelve vanilla fish have their own recipe in round 2.",
                    "longest_m": f1["item_longest_m"],
                    "copies": [{"rot_quat_xyzw": c["rot_quat_xyzw"], "bounds_center": c["bounds_center"]} for c in f1["copies"]]}
doc["_hooks_meatrack_r4"] = hooks
doc["_not_ripped"] = {n: "_generic" for n in NOT_RIPPED}
doc["_checks"] = {"rack_clash": len(clash), "rack_mesh_tests": tests, "hook_relations": len(rel), "frame_clash": len(frame_hits),
                  "lowest_piece_bottom_z": round(1.22 + low, 3), "bin_heap_top_z": heap,
                  "envelope": {"top_v": TOP, "bottom_v": V_MIN, "inward_u": A_IN, "outward_u": "0.055 (v >= -0.235), 0.095 (to -0.33), 0.042 below",
                               "rail_pitch_m": PITCH, "air_to_next_hook_m": GAPX}}
doc["doc"] = (
    "Meat Rack bundles round 2 (blender/meatbundles_r2.py): one recipe per item prefab, the game's OWN item model plus our cord, "
    "now ONE big piece per hook (kind single), a string of 2-3 one under the other for small pieces (kind stack, partial stacks "
    "show the top ones first), or two flat fish back to back (kind pair). Same schema as round 1. Hook space: origin = the hook "
    "point = centre of the rack's horizontal hook bar where the cord hangs (_hooks_meatrack_r4 lists them per r4 bundle unit, "
    "Unity prefab space). Unity axes: x across the rail, y up, z front (ux=-bx, uy=bz, uz=-by from Blender). Per copy: the item "
    "model in ItemVisual's item space (prefab root space without the root's own scale, already turned 180 degrees about up) gets "
    "the uniform `scale` (absolute, on the prefab's native size), then rot_quat_xyzw, and its ROOT goes to `offset`: copy matrix "
    "= T(hook) R(face) T(offset) R(rot) S(scale). Every item here has root scale 1, so scale = x_true_size, the fraction of the "
    "item's true size in the world; true_longest_m and item_longest_m give the longest bounds side at 1 and as hung. "
    "bounds_center is where the item's (rip) bounds centre lands. Fill: the first k copies for a partial stack; the cord is drawn "
    "whole. cord_obj is in the same folder: our own mesh (forward -Z, up Y, load with flipX like the frames), UVs on "
    "meatbundles_atlas.png (v 0.5-1 cord hemp, v 0-0.5 binding hemp), not tinted. Our strands start inside the frame's knot, 0.095 m "
    "below the hook point. Every bundle stays in the hook-space envelope of _checks (top 0.12 m and bottom 0.67 m below the hook "
    "point, 0.075 m behind to 0.042-0.095 m in front of the cord) and clear of its own copy 0.194 m along the rail, so a full rack "
    "has no two meshes touching (checked: _checks). Back-row hooks (faces=back): turn the whole bundle (copies and cord) 180 degrees "
    "about up through the hook point. Eggs never hang (the mod keeps them in the bins) and have no recipe. _generic, _fish and "
    "_not_ripped are documentation: the mod skips keys starting with '_'.")

atl = os.path.join(OUTA, "meatbundles_atlas.png")
if not os.path.exists(atl):
    import shutil; shutil.copyfile(os.path.join(R1, "meatbundles_atlas.png"), atl)
if "--items" not in argv:
    tmp = os.path.join(OUTA, "bundles.json.tmp")
    with open(tmp, "w", encoding="utf-8") as f: json.dump(doc, f, indent=1)
    os.replace(tmp, os.path.join(OUTA, "bundles.json"))
    print("R2 wrote", os.path.join(OUTA, "bundles.json"), flush=True)

# ---------- renders: everything placed from the JSON files the mod reads (round 1 + round 4 vs round 2 + round 5) ----------
if "--no-render" not in argv and "--items" not in argv:
    for o in list(sc.collection.objects): bpy.data.objects.remove(o, do_unlink=True)
    C4 = M_B2U.to_4x4()
    def u2b(Mu): return C4.transposed() @ Mu @ C4
    def trs(p, q, s):
        R = Matrix(((1, 0, 0), (0, 1, 0), (0, 0, 1))) if q is None else q.to_matrix()
        return Matrix.Translation(Vector(p)) @ R.to_4x4() @ Matrix.Diagonal((s, s, s, 1))
    def quat(l):
        from mathutils import Quaternion
        return Quaternion((l[3], l[0], l[1], l[2])).normalized()
    MESH = {}
    def item_mesh(name):
        if name not in MESH:
            obs = load(name, anchor="origin"); MESH[name] = obs[0].data
            for o in obs: bpy.data.objects.remove(o, do_unlink=True)
        return MESH[name]
    CORDS = {}
    def cord_mesh(folder, fn):
        key = (folder, fn)
        if key not in CORDS:
            bpy.ops.wm.obj_import(filepath=os.path.join(folder, fn), forward_axis="NEGATIVE_Z", up_axis="Y", use_split_objects=False, use_split_groups=False)
            o = bpy.context.selected_objects[0]; me = o.data; me.transform(o.matrix_world); me.materials.clear(); me.materials.append(CMAT)
            bpy.data.objects.remove(o); CORDS[key] = me
        return CORDS[key]
    def add(me, Mb, name="o"):
        o = bpy.data.objects.new(name, me); sc.collection.objects.link(o); o.matrix_world = Mb; return o
    r5 = json.load(open(os.path.join(R5, "MeatRackAnchors.json"))) if os.path.exists(os.path.join(R5, "MeatRackAnchors.json")) else None
    def ibounds(name):
        if r5 and name in r5.get("crop_layouts", {}): b = r5["crop_layouts"][name]["item_bounds"]; return Vector(b["center"]), Vector(b["size"])
        return None
    def look_rot(f, u):
        f = f.normalized(); x = u.cross(f).normalized(); y = f.cross(x)
        return Matrix(((x.x, y.x, f.x), (x.y, y.y, f.y), (x.z, y.z, f.z)))
    AXV = [Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))]
    def place_unit_copy(u, c, name):
        """StoreModel.Place for the meat rack's round-4 schema (Align.Axes, Fit.Longest, centre anchor, the bins' floor rule)."""
        bc, sz = ibounds(name)
        il = 0 if sz.x >= sz.y and sz.x >= sz.z else (1 if sz.y >= sz.z else 2)
        it = 0 if sz.x <= sz.y and sz.x <= sz.z else (1 if sz.y <= sz.z else 2)
        if it == il: it = (il + 1) % 3
        L = Vector(c["align"]["long_axis_to"]).normalized(); T = Vector(c["align"]["thin_axis_to"])
        T = (T - L * T.dot(L)).normalized()
        align = look_rot(T, L) @ look_rot(AXV[it], AXV[il]).inverted()
        r = quat(c["align"].get("then_rotate_quat_xyzw", [0, 0, 0, 1])).to_matrix() @ align
        s = c["longest_m"] / max(sz)
        pos = Vector(c["offset"]) - r @ (bc * s)
        Mu = Matrix.Translation(Vector(u["position"]) + pos) @ r.to_4x4() @ Matrix.Diagonal((s, s, s, 1))
        corners = [Mu @ Vector((bc.x + sx * sz.x / 2, bc.y + sy * sz.y / 2, bc.z + sz_ * sz.z / 2)) for sx in (-1, 1) for sy in (-1, 1) for sz_ in (-1, 1)]
        floor = u["position"][1] - u["box_size"][1] / 2; lowy = min(p.y for p in corners)
        if lowy < floor: Mu = Matrix.Translation(Vector((0, floor - lowy, 0))) @ Mu
        return Mu
    def hang_rack(dx, bdoc, bfolder, adoc, fill_hook, fill_bin, frame=True):
        made = []
        off = Matrix.Translation(Vector((dx, 0, 0)))
        if frame:
            bpy.ops.wm.obj_import(filepath=os.path.join(RACK, "MeatRack.obj"), forward_axis="NEGATIVE_Z", up_axis="Y", use_split_objects=False, use_split_groups=False)
            rk = bpy.context.selected_objects[0]; rk.data.materials.clear(); rk.data.materials.append(RMAT); rk.matrix_world = off @ rk.matrix_world; made.append(rk)
        for u in adoc["units"]:
            if u["kind"] == "bundle":
                name = fill_hook[u["group"]]; h = bdoc["_hooks_meatrack_r4"].get(str(u["index"]))
                rc = bdoc.get(name)
                if not h or not rc: continue
                face = Matrix.Rotation(math.pi, 4, "Y") if h["faces"] == "back" else Matrix.Identity(4)
                basis = Matrix.Translation(Vector(h["hook_point"])) @ face
                for c in rc["copies"]:
                    made.append(add(item_mesh(name), off @ u2b(basis @ trs(c["offset"], quat(c["rot_quat_xyzw"]), rc["scale"])), name))
                made.append(add(cord_mesh(bfolder, rc["cord_obj"]), off @ u2b(basis)))
            else:
                name = fill_bin[u["bin"]]
                lay = adoc.get("crop_layouts", {}).get(name)
                if lay:
                    if [x["index"] for x in adoc["units"] if x.get("bin") == u["bin"] and x["kind"] == "pile"].index(u["index"]) != 0: continue
                    bc, sz = ibounds(name); fc = Vector(adoc["crate_floor_centres"][u["bin"]])
                    for st in lay["stacks"]:
                        for c in st:
                            q = quat(c["rot_quat_xyzw"]).to_matrix(); s = lay["scale"]
                            Mu = Matrix.Translation(fc + Vector(c["offset"]) - q @ (bc * s)) @ q.to_4x4() @ Matrix.Diagonal((s, s, s, 1))
                            made.append(add(item_mesh(name), off @ u2b(Mu), name))
                else:
                    for c in u["copies"]: made.append(add(item_mesh(name), off @ u2b(place_unit_copy(u, c, name)), name))
        return made

    world = bpy.data.worlds.new("w"); sc.world = world; world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.42, 0.45, 0.5, 1)
    world.node_tree.nodes["Background"].inputs[1].default_value = 0.9
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN")); sun.data.energy = 3.2
    sun.rotation_euler = (math.radians(50), 0, math.radians(25)); sc.collection.objects.link(sun)
    bpy.ops.mesh.primitive_plane_add(size=60)
    gm = bpy.data.materials.new("ground"); gm.use_nodes = True
    gm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.16, 0.14, 0.11, 1)
    bpy.context.active_object.data.materials.append(gm)
    RMAT = bpy.data.materials.new("rack"); RMAT.use_nodes = True
    rt = RMAT.node_tree.nodes.new("ShaderNodeTexImage"); rt.image = bpy.data.images.load(os.path.join(RACK, "meatrack_atlas.png")); rt.interpolation = "Closest"
    RMAT.node_tree.links.new(rt.outputs["Color"], RMAT.node_tree.nodes["Principled BSDF"].inputs["Base Color"])
    POSTM = bpy.data.materials.new("post"); POSTM.use_nodes = True
    POSTM.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.75, 0.12, 0.08, 1)
    WHITE = bpy.data.materials.new("white"); WHITE.use_nodes = True
    WHITE.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.95, 0.95, 0.9, 1)
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam); sc.camera = cam
    sc.render.engine = "BLENDER_EEVEE_NEXT"; sc.view_settings.view_transform = "Standard"
    def shoot(fn, tgt, yaw, pitch, dist, res=(1600, 900), lens=50):
        sc.render.resolution_x, sc.render.resolution_y = res
        cam.data.lens = lens
        t = Vector(tgt)
        d = Vector((math.cos(math.radians(pitch)) * math.sin(math.radians(yaw)),
                    -math.cos(math.radians(pitch)) * math.cos(math.radians(yaw)), math.sin(math.radians(pitch))))
        cam.location = t + d * dist; cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
        sc.render.filepath = os.path.join(OUT, fn); bpy.ops.render.render(write_still=True)
    def text(body, loc, size=0.06, mat=WHITE):
        tc = bpy.data.curves.new("t", "FONT"); tc.body = body; tc.size = size; tc.align_x = "CENTER"
        to = bpy.data.objects.new("t", tc); to.location = loc; to.rotation_euler = (math.radians(90), 0, 0)
        to.data.materials.append(mat); sc.collection.objects.link(to); return to
    def post(x, y=-0.75):
        bpy.ops.mesh.primitive_cylinder_add(radius=0.03, depth=1.8, location=(x, y, 0.9)); p = bpy.context.active_object
        p.data.materials.append(POSTM)
        for z in (0.5, 1.0, 1.5):
            bpy.ops.mesh.primitive_cylinder_add(radius=0.034, depth=0.012, location=(x, y, z)); bpy.context.active_object.data.materials.append(WHITE)
        text("1.8 m", (x, y - 0.04, 1.84), 0.07)

    r1doc = json.load(open(os.path.join(R1, "bundles.json")))
    a4 = json.load(open(os.path.join(R4, "MeatRackAnchors.json")))
    a5 = r5 if r5 else a4
    FILL_HOOK = {"ridge": "SerpentMeat", "uf": "LoxMeat", "lf": "Fish2", "ub": "AsksvinMeat", "lb": "RawMeat"}
    FILL_BIN = {0: "NeckTail", 1: "ChickenMeat", 2: "DeerMeat", 3: "FishRaw", 4: "LoxMeat", 5: "Fish1"}
    hang_rack(-1.25, r1doc, R1, a4, FILL_HOOK, FILL_BIN)
    hang_rack(1.25, doc, OUTA, a5, FILL_HOOK, FILL_BIN)
    post(0.0)
    text("round 1 + bins r4", (-1.25, -0.9, 2.15), 0.09); text("round 2 + bins r5", (1.25, -0.9, 2.15), 0.09)
    shoot("compare_front.png", (0, 0, 1.05), 0, 6, 6.4, res=(2000, 1050), lens=40)
    shoot("compare_34.png", (0, 0, 1.0), -32, 14, 6.6, res=(2000, 1100), lens=40)
    shoot("new_front.png", (1.25, 0, 1.1), -8, 8, 3.2, res=(1600, 1100), lens=38)
    shoot("new_34.png", (1.25, 0, 1.05), -38, 12, 3.4, res=(1600, 1100), lens=38)
    shoot("old_front.png", (-1.25, 0, 1.1), -8, 8, 3.2, res=(1600, 1100), lens=38)
    # close-up: lox, serpent and a fish bunch, round 1 left and round 2 right of each pair, on one beam with the frame's hook parts
    for o in [o for o in sc.collection.objects if o.type in ("MESH", "FONT") and not o.name.startswith("Plane")]: bpy.data.objects.remove(o, do_unlink=True)
    IRON = bpy.data.materials.new("iron"); IRON.use_nodes = True
    IRON.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.04, 0.04, 0.04, 1)
    WOODM = bpy.data.materials.new("wood"); WOODM.use_nodes = True
    WOODM.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.13, 0.08, 0.04, 1)
    HEMPM = bpy.data.materials.new("hemp"); HEMPM.use_nodes = True
    HEMPM.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.13, 0.09, 0.05, 1)
    def box(size, loc, mat):
        bpy.ops.mesh.primitive_cube_add(size=1, location=loc); o = bpy.context.active_object
        o.scale = size; o.data.materials.append(mat); return o
    BEAM_Z, HZ = 1.9, 1.755
    pairs = [("LoxMeat", "LoxMeat"), ("SerpentMeat", "SerpentMeat"), ("Fish1", "Fish1")]
    xs = []
    for i, (n1, n2) in enumerate(pairs):
        for j, (bd, fold, nm, lab) in enumerate(((r1doc, R1, n1, "r1"), (doc, OUTA, n2, "r2"))):
            x = -1.2 + i * 0.95 + j * 0.42; xs.append(x)
            at = Vector((x, 0, HZ))
            box((0.022, 0.022, BEAM_Z - at.z + 0.011), (at.x, at.y + 0.05, (BEAM_Z + at.z - 0.011) / 2), IRON)
            box((0.022, 0.072, 0.022), (at.x, at.y + 0.025, at.z), IRON)
            box((0.016, 0.016, 0.07), (at.x, at.y, at.z - 0.05), HEMPM); box((0.035, 0.035, 0.035), (at.x, at.y, at.z + KNOT_Z), HEMPM)
            rc = bd.get(nm)
            if rc:
                basis = Matrix.Translation(Vector((-at.x, at.z, -at.y)))
                for c in rc["copies"]: add(item_mesh(nm), u2b(basis @ trs(c["offset"], quat(c["rot_quat_xyzw"]), rc["scale"])), nm)
                add(cord_mesh(fold, rc["cord_obj"]), u2b(basis))
                text("%s %s x%.2f" % (nm, lab, rc["scale"]), (x, -0.25, 1.0), 0.03)
    box((max(xs) - min(xs) + 0.5, 0.12, 0.12), ((max(xs) + min(xs)) / 2, 0.05, BEAM_Z + 0.06), WOODM)
    post(max(xs) + 0.35, 0.0)
    shoot("closeup_lox_serpent_fish.png", ((max(xs) + min(xs)) / 2 + 0.15, 0, 1.4), 0, 4, 3.9, res=(2200, 1100), lens=42)
print("DONE")
