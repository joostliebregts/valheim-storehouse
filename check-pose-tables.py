"""Every pose_table.json under assets/ names the sha256 of the anchors file beside it; the mod refuses a table whose anchors bytes
differ (PoseTable.Load), and the store then falls back to its round's own rules. 0.8.1 shipped that way (CRLF anchors from a
fresh Windows checkout, 28 Oct): this check fails the build instead. Run from this folder: python check-pose-tables.py"""
import glob, hashlib, json, os, sys

bad, ok = [], 0
for table in sorted(glob.glob('assets/*/pose_table.json')):
    folder = os.path.dirname(table)
    want = json.load(open(table, encoding='utf-8')).get('anchors_sha256', '')
    anchors = [p for p in glob.glob(os.path.join(folder, '*anchors*.json'))]
    have = {p: hashlib.sha256(open(p, 'rb').read()).hexdigest() for p in anchors}
    if want in have.values(): ok += 1
    else: bad.append(f'  {folder}: table wants {want[:12]}, anchors are ' + ', '.join(f'{os.path.basename(p)} {h[:12]}' for p, h in have.items()))
if bad:
    print('POSE TABLES: FAIL'); print('\n'.join(bad)); sys.exit(1)
print(f'POSE TABLES: PASS ({ok} tables match their anchors byte for byte)')
