"""The mannequins' carved arms in the vanilla pose, checked outside the game (27 Oct).

python arm-gate.py [--render DIR]

Builds armrun/ (ArmPose.cs as the game compiles it) and runs it on every shipped armory round with mannequins, then poses the same
arms again here, independently (numpy: SVD for the arm axis, rotation matrices), from the same files: Frame.obj (x flipped, as the
game loads it), the anchors (figures, front_axis, yaw) and assets/armorstand_pose.json. PASS when
  (i)   every figure gets the same facing and the same choice per arm (own, mirrored, fist slid, as carved),
  (ii)  every posed corner of every part agrees within 0.1 mm,
  (iii) every posed figure's elbows are within 3 cm of the rig's and its fists within 3 cm of the grip (Hand_Attach),
  (iv)  no posed arm point lies inside its own figure's torso, hips, legs or neck (the shoulder yoke excepted: the joint sits in it,
        as it did carved).
--render writes a front and a side view per figure, carved and posed, with the rig's shoulder, elbow and grip as red dots.
"""
import glob, json, os, re, subprocess, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, 'assets')
POSE = os.path.join(ASSETS, 'armorstand_pose.json')
TOL = 0.03
armPart = re.compile(r'_(Left|Right)_(upper|forearm|wrist_core|sleeve|wrist_tenon)(\.\d+)?$')
upperRe = re.compile(r'_(Left|Right)_(upper|sleeve)(\.\d+)?$')
lowerRe = re.compile(r'_(Left|Right)_(forearm|wrist_core|wrist_tenon)(\.\d+)?$')


def rounds():
    out = subprocess.run([sys.executable, os.path.join(HERE, 'ship-rounds.py')], capture_output=True, text=True, cwd=HERE, check=True).stdout.split()
    res = []
    for d in out:
        d = os.path.basename(d.strip())
        a = glob.glob(os.path.join(ASSETS, d, '*anchors*.json'))
        if len(a) == 1 and os.path.exists(os.path.join(ASSETS, d, 'Frame.obj')) and 'mannequins' in json.load(open(a[0], encoding='utf-8')):
            res.append(d)
    return res


def load_obj(path):
    v = []; objs = {}; order = []; cur = None
    for line in open(path, encoding='utf-8'):
        p = line.split()
        if not p: continue
        if p[0] == 'o': cur = line.strip()[1:].strip(); objs.setdefault(cur, []); order.append(cur)
        elif p[0] == 'v': v.append([-np.float32(p[1]), np.float32(p[2]), np.float32(p[3])])
        elif p[0] == 'f':
            c = [int(x.split('/')[0]) - 1 for x in p[1:]]
            for i in range(1, len(c) - 1): objs[cur].append((c[0], c[i], c[i + 1]))
    v = np.array(v, dtype=np.float64)
    return {k: v[np.array(f, dtype=int).reshape(-1, 3)] for k, f in objs.items() if f}   # name -> (n, 3 corners, xyz)


def capture():
    d = json.load(open(POSE, encoding='utf-8'))
    scale = d['visualLocalScale'][0]
    bones = {}
    for b in d['bones']:
        name = b['path'].split('/')[-1]
        if name not in bones: bones[name] = np.array(b['visualLocalMatrixRowMajor'], dtype=np.float64).reshape(4, 4)[:3, 3] * scale
    return bones


def axis(points):
    pts = np.unique(points.reshape(-1, 3), axis=0); c = pts.mean(0)
    return c, np.linalg.svd(pts - c)[2][0], pts


def centre(points): return np.unique(points.reshape(-1, 3), axis=0).mean(0)


def fromto(a, b):
    a = a / np.linalg.norm(a); b = b / np.linalg.norm(b); v = np.cross(a, b); c = np.dot(a, b)
    K = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]]); return np.eye(3) + K + K @ K / (1 + c)


def roty(deg):
    t = np.radians(deg); c, s = np.cos(t), np.sin(t); return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def turn(facing, yaw):
    near = round(yaw / 180.0) * 180.0
    delta = (yaw - near) % 360.0
    if delta > 180: delta -= 360
    return np.degrees(np.arctan2(0.0, facing)) + delta


def inside(points, tris, ray=np.array([0.5773, 0.5774, 0.5773])):
    v0 = tris[:, 0]; e1 = tris[:, 1] - v0; e2 = tris[:, 2] - v0
    h = np.cross(ray, e2); a = (e1 * h).sum(1); ok = np.abs(a) > 1e-12; f = np.where(ok, 1 / np.where(ok, a, 1), 0)
    res = []
    for p in points:
        s = p - v0; u = f * (s * h).sum(1); q = np.cross(s, e1); w = f * (q @ ray); t = f * (e2 * q).sum(1)
        res.append(((ok & (u >= 0) & (u <= 1) & (w >= 0) & (u + w <= 1) & (t > 1e-9)).sum()) % 2 == 1)
    return np.array(res)


def repose(o, arms, pos, facing, yaw, B):
    R = roty(turn(facing, yaw)); at = lambda n: pos + R @ B[n]
    S_ = {}
    for side in ('Left', 'Right'):
        up = [x for x in arms if upperRe.search(x) and upperRe.search(x).group(1) == side]
        lo = [x for x in arms if lowerRe.search(x) and lowerRe.search(x).group(1) == side]
        fist = [x for x in arms if not armPart.search(x) and side.lower() in x.lower()]
        s = dict(up=up, lo=lo, fist=fist, fits=False)
        if up and lo and fist:
            c, d, pts = axis(np.vstack([o[x] for x in up]))
            if np.dot(d, centre(np.vstack([o[x] for x in lo])) - c) < 0: d = -d
            pr = (pts - c) @ d; s['S'] = c + d * pr.min(); s['E'] = c + d * pr.max()
            s['F'] = centre(np.vstack([o[x] for x in fist])); s['grip'] = at(side + 'Hand_Attach'); s['elbow'] = at(side + 'ForeArm')
            s['miss'] = abs(np.linalg.norm(s['F'] - s['E']) - np.linalg.norm(s['grip'] - s['elbow']))
            s['fits'] = np.linalg.norm(s['S'] - at(side + 'Arm')) <= 0.05 and abs(np.linalg.norm(s['E'] - s['S']) - np.linalg.norm(s['elbow'] - s['S'])) <= 0.05
        S_[side] = s
    both = S_['Left']['fits'] and S_['Right']['fits']
    out = {}; how = {}; err = {}
    if not both:
        for side in ('Left', 'Right'):
            for x in S_[side]['up'] + S_[side]['lo'] + S_[side]['fist']: out[x] = o[x]
            how[side] = 'as carved'
        return out, how, err
    L, Rt = S_['Left'], S_['Right']
    M = (L['S'] + Rt['S']) / 2; n = Rt['S'] - L['S']; n[1] = 0; n /= np.linalg.norm(n)
    refl = lambda X: X - 2 * np.outer((X - M) @ n, n)
    for side, other in (('Left', 'Right'), ('Right', 'Left')):
        s, t = S_[side], S_[other]
        lower = {x: o[x] for x in s['lo']}; fists = {x: o[x] for x in s['fist']}; F = s['F']; h = 'own'
        if s['miss'] > TOL and t['miss'] <= TOL:
            d = s['E'] - refl(t['E'][None])[0]
            mir = lambda x: (refl(o[x].reshape(-1, 3)) + d).reshape(-1, 3, 3)[:, ::-1]
            lower = {x + '~mirror': mir(x) for x in t['lo']}; fists = {x + '~mirror': mir(x) for x in t['fist']}
            F = refl(t['F'][None])[0] + d; h = 'mirrored'
        S, E = s['S'], s['E']
        R1 = fromto(E - S, s['elbow'] - S); E2 = S + R1 @ (E - S)
        one = lambda X: S + (X.reshape(-1, 3) - S) @ R1.T
        R2 = fromto(one(F)[0] - E2, s['grip'] - E2)
        two = lambda X: E2 + (one(X) - E2) @ R2.T
        F2 = two(F)[0]; slide = s['grip'] - F2; slid = np.linalg.norm(slide) > TOL
        if slid: h += ', slid'
        for x in s['up']: out[x] = one(o[x]).reshape(-1, 3, 3)
        for x, tr in lower.items(): out[x] = two(tr).reshape(-1, 3, 3)
        for x, tr in fists.items(): out[x] = (two(tr) + (slide if slid else 0)).reshape(-1, 3, 3)
        how[side] = h; err[side] = (np.linalg.norm(E2 - s['elbow']), np.linalg.norm(F2 + (slide if slid else 0) - s['grip']))
    return out, how, err


def kind(report, side):
    m = re.search(side.lower() + r' (own|mirrored from the \w+|as carved)(, fist slid)?', report)
    if not m: return '?'
    return {'own': 'own', 'as carved': 'as carved'}.get(m.group(1), 'mirrored') + (', slid' if m.group(2) else '')


def render(groups, path, view, dots, centre_xy, size=420, scale=210):
    from PIL import Image, ImageDraw
    img = Image.new('RGB', (size, size), (250, 248, 244)); dr = ImageDraw.Draw(img); polys = []
    Lt = np.array([0.3, 0.8, -0.5]); Lt /= np.linalg.norm(Lt)
    for col, tris in groups:
        for t in tris:
            nrm = np.cross(t[1] - t[0], t[2] - t[0]); nn = np.linalg.norm(nrm)
            if nn < 1e-12: continue
            sh = 0.45 + 0.55 * abs(np.dot(nrm / nn, Lt))
            xy = [(c[0], c[1]) if view == 'front' else (c[2], c[1]) for c in t]
            depth = -t[:, 2].mean() if view == 'front' else t[:, 0].mean()
            polys.append((depth, [(size / 2 + (a - centre_xy[0]) * scale, size / 2 - (b - centre_xy[1]) * scale) for a, b in xy], tuple(int(c * sh) for c in col)))
    for _, p, c in sorted(polys, key=lambda z: z[0]): dr.polygon(p, fill=c)
    for p in dots:
        a, b = (p[0], p[1]) if view == 'front' else (p[2], p[1]); x, y = size / 2 + (a - centre_xy[0]) * scale, size / 2 - (b - centre_xy[1]) * scale
        dr.ellipse([x - 4, y - 4, x + 4, y + 4], fill=(200, 30, 30))
    img.save(path)


def main():
    out_dir = sys.argv[sys.argv.index('--render') + 1] if '--render' in sys.argv else None
    run = os.path.join(HERE, 'armrun')
    subprocess.run(['dotnet', 'build', '-c', 'Release', '-nologo', '-v', 'q'], cwd=run, check=True, capture_output=True)
    rs = rounds()
    got = json.loads(subprocess.run(['dotnet', os.path.join(run, 'bin', 'Release', 'net8.0', 'armrun.dll'), ASSETS, POSE] + rs, capture_output=True, text=True, check=True).stdout)
    B = capture(); fails = []; figures = posed = 0
    for r in rs:
        o = load_obj(os.path.join(ASSETS, r, 'Frame.obj'))
        doc = json.load(open(glob.glob(os.path.join(ASSETS, r, '*anchors*.json'))[0], encoding='utf-8'))
        for i, m in enumerate(doc['mannequins']):
            figures += 1
            arms = list(dict.fromkeys(list(m.get('hand_objects', [])) + [x for x in m.get('form_objects', []) if armPart.search(x)]))
            yaw = float(np.float32(m.get('yaw', 0.0))); pos = np.array(m['position'], dtype=np.float32).astype(np.float64)
            ax = m.get('front_axis', '') or ''
            facing = (-1 if np.cos(np.radians(yaw)) > 0 else 1) if ('Unity' in ax and '-Z' in ax) else None
            g = got[r][i]
            tag = f'{r} figure {i + 1}'
            if facing is None: fails.append(f'{tag}: no front_axis (the game falls back to the open-side rule; not checked here)'); continue
            if g['facing'] != facing: fails.append(f'{tag}: facing {g["facing"]} in C#, {facing} here')
            new, how, err = repose(o, [x for x in arms if x in o], pos, facing, yaw, B)
            for side in ('Left', 'Right'):
                if kind(g['report'], side) != how.get(side, 'as carved'): fails.append(f'{tag} {side}: C# "{kind(g["report"], side)}", here "{how.get(side)}"')
            if set(new) != set(g['parts']): fails.append(f'{tag}: parts differ: {sorted(set(new) ^ set(g["parts"]))}'); continue
            worst = 0.0
            for name, tris in new.items():
                a = np.round(np.unique(tris.reshape(-1, 3), axis=0), 4); b = np.round(np.unique(np.array(g['parts'][name]), axis=0), 4)
                if a.shape != b.shape: fails.append(f'{tag} {name}: {len(a)} corners here, {len(b)} in C#'); continue
                worst = max(worst, float(np.abs(np.sort(a.view('f8,f8,f8'), axis=0).view(np.float64).reshape(-1, 3) - np.sort(b.view('f8,f8,f8'), axis=0).view(np.float64).reshape(-1, 3)).max()))
            if worst > 1.5e-4: fails.append(f'{tag}: a posed corner {worst * 1000:.2f} mm apart')
            line = f'{tag}: facing {facing:+d}, ' + ', '.join(f'{s.lower()} {how[s]}' for s in ('Left', 'Right'))
            if err:
                posed += 1
                for s, (e, f) in err.items():
                    if e > TOL or f > TOL + 1e-6: fails.append(f'{tag} {s}: elbow {e * 100:.1f} cm, fist {f * 100:.1f} cm from the rig')
                body = [x for x in m.get('form_objects', []) if x in o and x not in arms and 'yoke' not in x and len(o[x]) >= 4]
                pts = np.unique(np.vstack([t.reshape(-1, 3) for t in new.values()]), axis=0)
                hits = {x: int(inside(pts, o[x]).sum()) for x in body}; hits = {k: v for k, v in hits.items() if v}
                if hits: fails.append(f'{tag}: posed arm points inside the body: {hits}')
                line += '; ' + ', '.join(f'{s.lower()} elbow {e * 100:.1f} cm, fist {f * 100:.1f} cm' for s, (e, f) in err.items()) + f'; C# within {worst * 1000:.3f} mm'
                if out_dir:
                    os.makedirs(out_dir, exist_ok=True)
                    R = roty(turn(facing, yaw)); dots = [pos + R @ B[n] for n in ('LeftArm', 'LeftForeArm', 'LeftHand_Attach', 'RightArm', 'RightForeArm', 'RightHand_Attach')]
                    bodyT = np.vstack([o[x] for x in m.get('form_objects', []) if x in o and x not in arms])
                    for view in ('front', 'side'):
                        c = (pos[0] if view == 'front' else pos[2], pos[1] + 0.95)
                        for state, armT in (('carved', np.vstack([o[x] for x in arms if x in o])), ('posed', np.vstack(list(new.values())))):
                            render([((196, 160, 112), bodyT), ((150, 190, 120), armT)], os.path.join(out_dir, f'{r}_{i + 1}_{view}_{state}.png'), view, dots, c)
            print(line)
    print(f'\n{figures} figures in {len(rs)} rounds, {posed} posed.')
    if fails:
        print('FAIL:\n  ' + '\n  '.join(fails)); return 1
    print('PASS'); return 0


if __name__ == '__main__':
    sys.exit(main())
