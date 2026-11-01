"""Every store's model files from one round folder (25 Oct: Fletcher's r3 loaded with r2's anchors because StoreModel.Files picked each
file from the first round that had one). Mirrors StoreModel.Files over assets/ for each Store(...) in Storehouse.cs: the newest round
folder that exists must hold an OBJ, an atlas PNG and a JSON (anchors, or else layouts); a newest round missing one would silently
show an older round. Also prints what the old per-file pick took, to name stores that mixed rounds. Run by build.sh and
test-swap.sh stage; usage: python check-rounds.py [--old]
"""
import glob
import os
import re
import sys

here = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(here, 'Storehouse.cs'), encoding='utf-8').read()
assets = os.path.join(here, 'assets')
DEFAULT_ROUNDS = ['_r6', '_r5', '_r4', '_r3', '_r2']


def stores():
    """(slug, piece, rounds) per Store(...) call, and the shelves' pieces 1-3."""
    out = []
    for m in re.finditer(r'\bStore\(\s*"([^"]+)"', src):
        end = src.find('Store(', m.end())
        call = src[m.start():end if end > 0 else len(src)]
        rounds = re.search(r'rounds:\s*new\[\]\s*\{([^}]*)\}', call)
        rounds = re.findall(r'"(_r\d+\w*)"', rounds.group(1)) if rounds else DEFAULT_ROUNDS
        piece = re.search(r'piece:\s*"([^"]+)"', call)
        if m.group(1) == 'emergencyshelf':
            for n in ('1', '2', '3'):
                out.append(('emergencyshelf', n, rounds))
        else:
            out.append((m.group(1), piece.group(1) if piece else None, rounds))
    return out


def files_in(d, piece):
    def pick(pattern, ok):
        found = [f for f in glob.glob(os.path.join(d, pattern)) if ok(os.path.basename(f))]
        return max(found, key=os.path.getsize) if found else None
    obj = pick('*.obj', lambda n: (piece is None or piece in n) and not n.endswith('_bands.obj') and n != 'Straw.obj')
    png = pick('*.png', lambda n: 'atlas' in n.lower())
    js = pick('*.json', lambda n: '_layouts' not in n and '_display' not in n and n != 'pose_table.json') or pick('*_layouts.json', lambda n: True)
    return obj, png, js


def old_pick(dirs, piece):
    """The per-file pick before 25 Oct: each file from the first round folder that has one."""
    got = [None, None, None]
    for d in dirs:
        for i, f in enumerate(files_in(d, piece)):
            if got[i] is None and f:
                got[i] = f
    return got


def main():
    fails, mixed = [], []
    for slug, piece, rounds in stores():
        dirs = [os.path.join(assets, slug + r) for r in rounds if os.path.isdir(os.path.join(assets, slug + r))]
        if not dirs:
            continue
        newest = dirs[0]
        f = files_in(newest, piece)
        if not all(f):
            fails.append(f'{slug}{"/" + piece if piece else ""}: newest round {os.path.basename(newest)} lacks '
                         + ', '.join(n for n, x in zip(('an OBJ', 'an atlas', 'a JSON'), f) if not x))
        old = old_pick(dirs, piece)
        folders = {os.path.basename(os.path.dirname(x)) for x in old if x}
        if len(folders) > 1:
            mixed.append(f'{slug}{"/" + piece if piece else ""}: ' + ', '.join(f'{os.path.basename(os.path.dirname(x))}/{os.path.basename(x)}' for x in old if x))
    if '--old' in sys.argv:
        print('Stores whose files came from more than one round with the old per-file pick:')
        print('  ' + ('\n  '.join(mixed) if mixed else 'none'))
    if fails:
        print('ROUNDS: FAIL\n  ' + '\n  '.join(fails))
        sys.exit(1)
    print(f'ROUNDS: PASS (every store\'s newest round folder holds its OBJ, atlas and JSON)')


if __name__ == '__main__':
    main()
