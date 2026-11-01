"""Every Rows default each store ever had, from the git history of Storehouse.cs on every branch (releases and the test builds
Joost ran), written into Storehouse.cs between the ROWS HISTORY markers (Settings.PastRows). The mod raises a stored Rows value
that equals one of these to today's default, never lowers it: fewer rows would hide what lies in the others (SPEC: released
pieces stay). Run from this folder:

    python rows-history.py            regenerate the table in Storehouse.cs
    python rows-history.py --print    only show it
"""
import importlib.util
import math
import os
import re
import subprocess
import sys

here = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location('accepts_history', os.path.join(here, 'accepts-history.py'))
ah = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ah)   # its C# tokenizer and call-argument reader

SRC = 'tools/valheim-storehouse/Storehouse.cs'
BEGIN, END = '    // ROWS HISTORY BEGIN (rows-history.py)', '    // ROWS HISTORY END'


def rows(s):
    """{config section: default Rows} in one version of Storehouse.cs (stores with a Rows setting only)."""
    out = {}
    cols = int(m.group(1)) if (m := re.search(r'const int Columns\s*=\s*(\d+)', s)) else 8
    for m in re.finditer(r'\bStore\(\s*"', s):
        a = ah.args(s, m.end() - len(m.group(0)) + m.group(0).index('('))
        if len(a) < 7 or not a[1] or a[1][0][0] != 'str':
            continue
        title = a[1][0][1]
        units = next((int(t[1]) for t in a[6] if t[0] == 'id' and t[1].isdigit()), None)
        named = {}
        for arg in a[7:]:   # named arguments: columns: 6, planks: 3
            if len(arg) >= 3 and arg[0][0] == 'id' and arg[1][0] == 'p' and arg[1][1] == ':' and arg[2][0] == 'id' and arg[2][1].isdigit():
                named[arg[0][1]] = int(arg[2][1])
        if units is None or named.get('planks', 0) > 0:
            continue
        c = named.get('columns', 0) or cols
        out['4 - ' + ''.join(ch for ch in title if ch not in ah.NOT_IN_SECTION)] = math.ceil(units / c)
    for m in re.finditer(r'Section\s*=\s*"([^"]+)"', s):
        block_end = s.find('};', m.end())
        d = re.compile(r'DefaultRows\s*=\s*(\d+)').search(s, m.end(), block_end)
        if d:
            out.setdefault(''.join(ch for ch in m.group(1) if ch not in ah.NOT_IN_SECTION), int(d.group(1)))
    return out


def main():
    root = subprocess.run(['git', 'rev-parse', '--show-toplevel'], capture_output=True, text=True, check=True).stdout.strip()
    commits = subprocess.run(['git', '-C', root, 'log', '--all', '--format=%h', '--', SRC], capture_output=True, text=True, check=True).stdout.split()
    now = rows(open(f'{root}/{SRC}', encoding='utf-8').read())
    past = {}
    for c in reversed(commits):
        s = subprocess.run(['git', '-C', root, 'show', f'{c}:{SRC}'], capture_output=True, text=True, encoding='utf-8').stdout
        for section, r in rows(s).items():
            if section in now and r != now[section]:
                past.setdefault(section, set()).add(r)
    lines = [BEGIN,
             f'    // {len(commits)} versions of Storehouse.cs read (every branch); per config section the default Rows that differ from today\'s.',
             '    internal static readonly Dictionary<string, int[]> PastRows = new()',
             '    {']
    for section in sorted(past):
        lines.append(f'        ["{section}"] = new[] {{ {", ".join(str(v) for v in sorted(past[section]))} }},')
    lines += ['    };', END]
    block = '\n'.join(lines)
    if '--print' in sys.argv:
        print(block)
        return
    path = f'{root}/{SRC}'
    src = open(path, encoding='utf-8', newline='').read()
    a, b = src.index(BEGIN), src.index(END) + len(END)
    open(path, 'w', encoding='utf-8', newline='').write(src[:a] + block + src[b:])
    print(f'{sum(len(v) for v in past.values())} earlier Rows default(s) for {len(past)} store(s), from {len(commits)} versions')


if __name__ == '__main__':
    main()
