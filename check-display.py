"""What a store holds, it can show (the coordinator's retro, 26 Oct: stores that held more than they could ever show, and kinds that
were accepted but had nowhere to go). Static, from Storehouse.cs and each store's newest round folder (the files StoreModel.Files
picks, as check-rounds.py finds them). Two rules:

1. Slots vs places: a store that shows one stack per place (equipment places, mannequin slots, units with stack_per_unit) must
   have at least as many places as chest slots (rows x columns). Heaps, cells and bays (Fletcher's, the Ossuary, the bunkers)
   show mass rather than stacks and are not counted here. A store with typed places (its rule is an EquipRules equipment rule, not
   the mannequins'; TypedSlots in Storehouse.cs) has a window made of its places: a slot per place, the rows rounded up, the cells past
   the last place holding nothing. Its slots are its places by construction; this check reads them from the anchors and says so.
2. Every kind a store accepts by name is routed somewhere: in a store that sends kinds by a table (item_family: Fletcher's,
   Apothecary, Pantry; supported_prefabs: the Ossuary), every name in its default Accepts is in that table. Wildcard names
   (Arrow*) can't be listed without the game; the in-game self-test covers those.

A store in the release set (Kinds.Released, Kinds.NextRelease) that breaks a rule fails the build, unless it is listed in KNOWN
with the reason (a decision someone still has to make). Prototypes outside the release set only print a note.
Run by build.sh and test-swap.sh stage; usage: python check-display.py [--all]
"""
import importlib.util
import json
import os
import re
import sys

here = os.path.dirname(os.path.abspath(__file__))


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), os.path.join(here, name + '.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ah = load('accepts-history')   # the C# argument and string-constant reader
cr = load('check-rounds')      # the round and file pick
src = open(os.path.join(here, 'Storehouse.cs'), encoding='utf-8').read()
assets = os.path.join(here, 'assets')
COLUMNS = int(re.search(r'public const int Columns = (\d+);', src).group(1))

# Release-set stores that break a rule on purpose or pending a decision: slug -> why.
KNOWN = {}


def release_set():
    out = set()
    for name in ('Released', 'NextRelease'):
        m = re.search(r'HashSet<string> ' + name + r' = new\(StringComparer\.Ordinal\)\s*\{(.*?)\n    \};', src, re.S)
        out |= set(re.findall(r'"([^"]+)"', re.sub(r'//.*', '', m.group(1))))
    return out


def stores():
    for m in re.finditer(r'\bStore\(\s*"', src):
        a = ah.args(src, m.end() - len(m.group(0)) + m.group(0).index('('))
        rest = ''.join(f'"{t[1]}"' if t[0] == 'str' else t[1] for x in a[7:] for t in x)
        r = re.search(r'rounds:new\[\]\{(.*?)\}', rest)
        piece = re.search(r'piece:"([^"]+)"', rest)
        cols = re.search(r'columns:(\d+)', rest)
        yield {
            'slug': a[0][0][1], 'title': a[1][0][1], 'accepts': ah.value(src, a[5]) or '',
            'units': int(''.join(t[1] for t in a[6])), 'columns': int(cols.group(1)) if cols else COLUMNS,
            'rounds': re.findall(r'"(_r\d+\w*)"', r.group(1)) if r else cr.DEFAULT_ROUNDS,
            'piece': piece.group(1) if piece else None,
            'typed': (lambda r: r.startswith('EquipRules.') and r != 'EquipRules.Mannequin')(''.join(t[1] for t in a[4])),
        }


def places(doc):
    """(count, what) of one-stack places in an anchors document, or (None, why) when the store shows mass."""
    if isinstance(doc.get('mannequins'), list):
        return 6 * len(doc['mannequins']), 'mannequin slots'
    units = doc.get('units_data') or doc.get('units_list') or (doc['units'] if isinstance(doc.get('units'), list) else None)
    if isinstance(doc.get('places'), list) and not units:
        return len(doc['places']), 'equipment places'
    if units and any(isinstance(u, dict) and ('accepted_item_types' in u or 'allocation_group' in u or 'equipment_types' in u) for u in units):
        return sum(1 for u in units if isinstance(u, dict) and ('accepted_item_types' in u or 'allocation_group' in u or 'equipment_types' in u)), 'equipment places'
    if units and str(doc.get('stack_per_unit')).lower() in ('1', 'true'):
        return len(units), 'units, one stack each'
    return None, 'shows mass (heaps, bays or cells)'


def main():
    shipping = release_set()
    fails, notes = [], []
    for st in stores():
        dirs = [os.path.join(assets, st['slug'] + r) for r in st['rounds'] if os.path.isdir(os.path.join(assets, st['slug'] + r))]
        if not dirs or st['units'] <= 0:
            continue
        d = dirs[0]
        obj, png, js = cr.files_in(d, st['piece'])
        if not js:
            continue
        doc = json.load(open(js, encoding='utf-8'))
        problems = []
        slots = -(-st['units'] // st['columns']) * st['columns']
        n, what = places(doc)
        if st['typed'] and what == 'equipment places':
            slots, what = n, f'equipment places = typed slots, {-(-n // st["columns"])} rows of {st["columns"]}'
        if n is not None and slots > n:
            problems.append(f'{slots} chest slots but {n} {what}')
        tables = {}
        lay = os.path.join(d, st['slug'] + '_layouts.json')
        for f, doc2 in ((js, doc), (lay, json.load(open(lay, encoding='utf-8')) if os.path.exists(lay) else {})):
            if isinstance(doc2.get('item_family'), dict):
                tables['item_family'] = set(doc2['item_family'])
            if isinstance(doc2.get('supported_prefabs'), list):
                tables['supported_prefabs'] = set(doc2['supported_prefabs'])
        names = [x.strip() for x in st['accepts'].split(',') if x.strip() and '*' not in x]
        for t, kinds in tables.items():
            missing = [x for x in names if x not in kinds]
            if missing:
                problems.append(f'accepts {", ".join(missing)} but its {t} has no place for them')
        if not problems:
            if '--all' in sys.argv:
                print(f'  ok   {st["slug"]}: {slots} slots, {what if n is None else f"{n} {what}"}{", kinds by " + "/".join(tables) if tables else ""}')
            continue
        line = f'{st["slug"]} ({os.path.basename(d)}): ' + '; '.join(problems)
        if st['slug'] in KNOWN and st['slug'] in shipping:
            notes.append(line + f' [known: {KNOWN[st["slug"]]}]')
        elif st['slug'] in shipping:
            fails.append(line)
        else:
            notes.append(line + ' [prototype, not in the release set]')
    for x in notes:
        print('  note ' + x)
    if fails:
        print('DISPLAY: FAIL\n  ' + '\n  '.join(fails))
        sys.exit(1)
    print('DISPLAY: PASS (release-set stores show what they hold: places >= slots, accepted kinds routed)')


if __name__ == '__main__':
    main()
