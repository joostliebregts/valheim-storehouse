"""A models-session pose table (Long Rack r5c's long-lean-table.json, the Spine's hang table) as the game reads it.

python pose-table.py <delivered table.json> <assets/round folder> [--conflicts <neighbour-conflicts.json>]

Writes <round>/pose_table.json (schema storehouse-pose-table/1): the anchors' sha256 the table was made for, and per (place index,
prefab) either its pose or why it has none:
  [place, prefab, 1, pivot x, y, z, quat x, y, z, w, tight centre x, y, z]   drawn T(pivot) . R(quat) . T(-centre) in ItemVisual's
                                                                               turned source space (the contract in its READY)
  [place, prefab, 0, reason]                                                   no approved pose: the item does not go there
With --visibility (the Arsenal's pair-visibility.json, made for exactly this delivered table: its pose_table_sha256): "visibility",
[near place, near prefab, far place, far prefab, near visible fraction, far visible fraction] per neighbouring pair that does not
cross; the game orders a row of places so its least visible item is as visible as possible.
With --conflicts (the Spine's neighbour-conflicts.json): "conflicts", [place, prefab, neighbour place, neighbour prefab] per pair
whose poses cross; the game gives no place to an item that would cross what a neighbour holds.
Field names of either table: place_index or place; raw_source_root_matrix_unity or root_matrix_unity; game_tight_turned_center_unity
or tight_turned_center_unity.
Refuses (exit 1) when the round's anchors file is not the one the table names, when a row is missing or doubled, or when a fit row's
raw_source_root_matrix_unity differs from T(pivot) . R(quat) . T(-centre) by more than 0.01 mm. The delivered file (several MB of
provenance per row) stays with the delivery; the game reads only this.
"""
import glob, hashlib, json, os, sys
import numpy as np


def quat_matrix(x, y, z, w):
    n = np.sqrt(x * x + y * y + z * z + w * w); x, y, z, w = x / n, y / n, z / n, w / n
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def main():
    src, round_dir = sys.argv[1], sys.argv[2].rstrip('/\\')
    conflicts_src = sys.argv[sys.argv.index('--conflicts') + 1] if '--conflicts' in sys.argv else None
    first = lambda r, *keys: next((r[k] for k in keys if r.get(k) is not None), None)   # a field present but empty (null) is not the value
    t = json.load(open(src, encoding='utf-8'))
    anchors = [f for f in glob.glob(os.path.join(round_dir, '*anchors*.json'))]
    if len(anchors) != 1: sys.exit(f'{round_dir}: {len(anchors)} anchors files')
    sha = hashlib.sha256(open(anchors[0], 'rb').read()).hexdigest()
    if t.get('anchors_sha256') != sha: sys.exit(f'REFUSED: the table is for anchors {t.get("anchors_sha256")}, {anchors[0]} is {sha}')
    rows, seen, worst, fits = [], set(), 0.0, 0
    for r in t['rows']:
        key = (int(first(r, 'place_index', 'place')), r['prefab'])
        if key in seen: sys.exit(f'REFUSED: row {key} twice')
        seen.add(key)
        if r.get('anchors_sha256', sha) != sha: sys.exit(f'REFUSED: row {key} names other anchors')
        if not r.get('fit'):
            rows.append([key[0], key[1], 0, r.get('reason') or 'no approved pose'])
            continue
        p = np.array(r['fitted_display_pivot_position_unity'], dtype=float)
        q = [float(v) for v in r['rotation_unity_quat_xyzw']]
        c = np.array(first(r, 'game_tight_turned_center_unity', 'tight_turned_center_unity', 'tight_center_turned_unity'), dtype=float)
        R = quat_matrix(*q)
        raw = np.array(first(r, 'raw_source_root_matrix_unity', 'root_matrix_unity'), dtype=float)
        mine = np.eye(4); mine[:3, :3] = R; mine[:3, 3] = p - R @ c
        # The item's own root scale (Armory B r2c's small crossbows: 0.4, 0.5) is in the raw matrix; the game scales by it as well.
        rs = np.array(r['root_scale'], dtype=float) * np.ones(3) if r.get('root_scale') is not None else np.ones(3)
        err = float(np.abs(raw[:3, 3] - mine[:3, 3]).max()) + float(np.abs(raw[:3, :3] - R @ np.diag(rs)).max())
        worst = max(worst, err)
        if err > 1e-5: sys.exit(f'REFUSED: row {key}: raw root matrix differs from T(pivot) R T(-centre) by {err * 1000:.4f} mm')
        row = [key[0], key[1], 1] + [round(v, 7) for v in list(p) + q + list(c)]
        if r.get('contacts'):   # the Spine's: where it rests on the frame, one point per arm (their mean), Unity (-x, z, -y)
            arms = {}
            for k in r['contacts']: arms.setdefault(k.get('arm', 0), []).append(k['frame_point_blender'])
            row.append([[round(v, 5) for v in (-m[0], m[2], -m[1])] for m in (np.mean(ps, axis=0) for _, ps in sorted(arms.items(), key=lambda kv: str(kv[0])))])
        rows.append(row)
        fits += 1
    places = sorted({k[0] for k in seen}); prefabs = sorted({k[1] for k in seen})   # a table may cover some places only (Arsenal B: its shields)
    missing = [(pl, pf) for pl in places for pf in prefabs if (pl, pf) not in seen]
    # Armory B r2c lists each place with its own kind only (weapon places x weapons, shield places x shields): a pair without a row
    # is "not there" in the game, as a fit:false row is.
    if missing: print(f'note: {len(missing)} (place, prefab) pairs have no row (not there), e.g. {missing[:3]}')
    conflicts = []
    if conflicts_src:
        fit = {(r[0], r[1]) for r in rows if r[2] == 1}
        cdoc = json.load(open(conflicts_src, encoding='utf-8'))
        # the Spine's "crossings" ({place, prefab, neighbour_place, neighbour_prefab}) or Arsenal B's "pairs" ({a, b} of {place_index, prefab})
        pairs = [((x['place'], x['prefab']), (x['neighbour_place'], x['neighbour_prefab'])) for x in cdoc.get('crossings', [])] \
            + [((x['a']['place_index'], x['a']['prefab']), (x['b']['place_index'], x['b']['prefab'])) for x in cdoc.get('pairs', [])]
        if not pairs: sys.exit(f'REFUSED: {conflicts_src} has neither crossings nor pairs')
        for (pa, fa), (pb, fb) in pairs:
            a, b = (int(pa), fa), (int(pb), fb)
            if a not in fit or b not in fit: sys.exit(f'REFUSED: conflict {a} x {b} names a pose the table does not have')
            conflicts.append([a[0], a[1], b[0], b[1]])
    visibility = []
    vis_src = sys.argv[sys.argv.index('--visibility') + 1] if '--visibility' in sys.argv else None
    if vis_src:
        vdoc = json.load(open(vis_src, encoding='utf-8'))
        table_sha = hashlib.sha256(open(src, 'rb').read()).hexdigest()
        if vdoc.get('pose_table_sha256') != table_sha: sys.exit(f'REFUSED: {vis_src} is for pose table {vdoc.get("pose_table_sha256")}, {src} is {table_sha}')
        if vdoc.get('anchors_sha256') != sha: sys.exit(f'REFUSED: {vis_src} names other anchors')
        fit = {(r[0], r[1]) for r in rows if r[2] == 1}
        for x in vdoc['rows']:
            if not x.get('fit') or not x.get('compatible'): continue   # a crossing pair is never used, however visible
            a, b = (int(x['near_place_index']), x['near_prefab']), (int(x['far_place_index']), x['far_prefab'])
            if a not in fit or b not in fit: sys.exit(f'REFUSED: visibility {a} x {b} names a pose the table does not have')
            visibility.append([a[0], a[1], b[0], b[1], round(x['near_visible_fraction'], 4), round(x['far_visible_fraction'], 4)])
    out = {'schema': 'storehouse-pose-table/1', 'source': os.path.basename(src), 'source_schema': t.get('schema'), 'label': t.get('label') or f"{t.get('module', '')} {t.get('schema', '')}".strip(),
           'anchors_sha256': sha, 'places': len(places), 'prefabs': len(prefabs), 'fit_rows': fits, 'conflicts': conflicts, 'visibility': visibility, 'rows': rows}
    dst = os.path.join(round_dir, 'pose_table.json')
    with open(dst, 'w', encoding='utf-8', newline='\n') as f:
        f.write('{\n' + ',\n'.join(f' {json.dumps(k)}: {json.dumps(v)}' for k, v in out.items() if k != 'rows'))
        f.write(',\n "rows": [\n' + ',\n'.join('  ' + json.dumps(r) for r in rows) + '\n ]\n}\n')
    print(f'{dst}: {len(rows)} rows ({fits} poses, {len(rows) - fits} without), {len(places)} places x {len(prefabs)} prefabs; '
          f'anchors {sha[:12]}; root matrices within {worst * 1000:.5f} mm; {len(conflicts)} crossing neighbour pairs; {len(visibility)} visibility pairs')


if __name__ == '__main__':
    main()
