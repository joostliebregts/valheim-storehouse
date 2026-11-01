"""Every Accepts default each store ever had, from the git history of Storehouse.cs, written into Storehouse.cs between the
ACCEPTS HISTORY markers (Settings.PastAccepts). The mod replaces a stored Accepts value that equals one of these (ignoring
order and spacing) with today's default: a value nobody chose was never a decision. Run from this folder:

    python accepts-history.py            regenerate the table in Storehouse.cs
    python accepts-history.py --print    only show it
"""
import re
import subprocess
import sys

SRC = 'tools/valheim-storehouse/Storehouse.cs'
# What shipped: from the 0.3.0 release build up to the commit the 0.4.0 server release was built from (24 Oct, 18:36; live at
# 18:49). Defaults of dev builds after that never reached a server, so an Accepts value equal to one of them may be an admin's
# own edit (Joost added Royal Jelly to Cooper's Row on the server before it became the default) and is kept.
FIRST, LAST = '7e9575c61', '92ee67e82'
# And the 0.5 test builds Joost ran in his own world, only for the stores named: their defaults reached his config but never a
# server (25 Oct: Liquid Frost, Thunderstone and Crystal moved from the bunkers to the Ember Cabinet; the Board out of the crib). Never Cooper's Row here: its 0.5
# interim default equals the server admin's own edit (six + Royal Jelly), which must stay his.
TESTED = ['2 - Timber Crib', '4 - Coal & Stone Bunker', '4 - Open Coal & Stone Bunker', '4 - Ember Cabinet', '4 - Jewellers Casket']
# The 0.8.0 public release (27 Oct): its defaults reached every server and player, so a value equal to one is no decision either.
# Only the sections 0.8.1 changed (Joost's sorting round, 28 Oct).
RELEASED_080 = ['4 - Coal & Stone Bunker', '4 - Open Coal & Stone Bunker', '4 - Coopers Row', '4 - Stacking Coopers Row',
                '4 - Apothecary Rack', '4 - Tall Apothecary Rack', '4 - Ember Cabinet']
EXTRA = {'4f70e4b0f': TESTED, '907e2164b': TESTED, 'b307bcb3c': RELEASED_080}
BEGIN, END = '    // ACCEPTS HISTORY BEGIN (accepts-history.py)', '    // ACCEPTS HISTORY END'
NOT_IN_SECTION = set('=\n\t\\"\'[]')


def tokens(s, i):
    """C# tokens from i: ('str', text), ('id', name), ('p', char). Skips comments and whitespace."""
    n = len(s)
    while i < n:
        c = s[i]
        if c.isspace():
            i += 1
        elif s.startswith('//', i):
            i = s.index('\n', i)
        elif s.startswith('/*', i):
            i = s.index('*/', i) + 2
        elif c == '"' or (c in '$@' and i + 1 < n and s[i + 1] == '"'):
            j = i + (2 if c in '$@' else 1)
            out = []
            while s[j] != '"':
                if s[j] == '\\':
                    out.append(s[j + 1])
                    j += 2
                else:
                    out.append(s[j])
                    j += 1
            yield ('str', ''.join(out), j + 1)
            i = j + 1
        elif c == "'":
            j = s.index("'", i + 2 if s[i + 1] == '\\' else i + 1)
            yield ('p', s[i:j + 1], j + 1)
            i = j + 1
        elif c.isalnum() or c == '_':
            j = i
            while j < n and (s[j].isalnum() or s[j] in '_.'):
                j += 1
            yield ('id', s[i:j], j)
            i = j
        else:
            yield ('p', c, i + 1)
            i += 1


def args(s, i):
    """The top-level arguments of the call whose '(' is at i, each as a token list."""
    depth, cur, out = 0, [], []
    for t in tokens(s, i):
        if t[0] == 'p' and t[1] in '([{':
            depth += 1
            if depth == 1:
                continue
        elif t[0] == 'p' and t[1] in ')]}':
            depth -= 1
            if depth == 0:
                out.append(cur)
                return out
        elif t[0] == 'p' and t[1] == ',' and depth == 1:
            out.append(cur)
            cur = []
            continue
        cur.append(t)
    return out


def expr_until_comma(s, i):
    """Tokens of an expression from i up to its top-level ',' or ';' or closing brace."""
    depth, cur = 0, []
    for t in tokens(s, i):
        if t[0] == 'p' and t[1] in '([{':
            depth += 1
        elif t[0] == 'p' and t[1] in ')]}':
            if depth == 0:
                return cur
            depth -= 1
        elif t[0] == 'p' and t[1] in ',;' and depth == 0:
            return cur
        cur.append(t)
    return cur


def value(s, toks, seen=()):
    """A string expression ("a" + "b" + NAME): its value, or None when it is not one."""
    parts = []
    for t in toks:
        if t[0] == 'str':
            parts.append(t[1])
        elif t[0] == 'p' and t[1] == '+':
            continue
        elif t[0] == 'id' and t[1] not in ('null',):
            name = t[1].split('.')[-1]
            if name in seen:
                return None
            m = re.search(r'(?:const|readonly)\s+string\s+' + re.escape(name) + r'\s*=', s)
            if not m:
                return None
            v = value(s, expr_until_comma(s, m.end()), seen + (name,))
            if v is None:
                return None
            parts.append(v)
        else:
            return None
    return ''.join(parts)


def defaults(s):
    """{config section: Accepts default} in one version of Storehouse.cs."""
    out = {}
    for m in re.finditer(r'\bStore\(\s*"', s):
        a = args(s, m.end() - len(m.group(0)) + m.group(0).index('('))
        if len(a) < 6 or not a[1] or a[1][0][0] != 'str':
            continue
        title = a[1][0][1]
        v = value(s, a[5])
        if v is not None:
            out['4 - ' + ''.join(c for c in title if c not in NOT_IN_SECTION)] = v
    for m in re.finditer(r'Section\s*=\s*"([^"]+)"', s):
        block_end = s.find('};', m.end())
        d = s.find('DefaultAccepts', m.end(), block_end)
        if d < 0:
            continue
        eq = s.index('=', d)
        v = value(s, expr_until_comma(s, eq + 1))
        if v is not None:
            out.setdefault(m.group(1), v)
    return out


def norm(v):
    return tuple(sorted({x.strip().lower() for x in v.split(',') if x.strip()}))


def main():
    root = subprocess.run(['git', 'rev-parse', '--show-toplevel'], capture_output=True, text=True, check=True).stdout.strip()
    commits = subprocess.run(['git', '-C', root, 'log', '--format=%h', f'{FIRST}^..{LAST}', '--', SRC], capture_output=True, text=True, check=True).stdout.split()
    now = defaults(open(f'{root}/{SRC}', encoding='utf-8').read())
    past = {}
    for c in reversed(commits + list(EXTRA)):
        only = EXTRA.get(c)
        s = subprocess.run(['git', '-C', root, 'show', f'{c}:{SRC}'], capture_output=True, text=True, encoding='utf-8', check=True).stdout
        for section, v in defaults(s).items():
            if only is not None and section not in only:
                continue
            if section in now and norm(v) != norm(now[section]):
                lst = past.setdefault(section, [])
                if all(norm(v) != norm(x) for x in lst):
                    lst.append(v)
    lines = [BEGIN,
             f'    // {len(commits)} shipped versions of Storehouse.cs read ({FIRST} = 0.3.0 to {LAST} = 0.4.0); per config section',
             '    // the shipped defaults that differ from today\'s.',
             '    internal static readonly Dictionary<string, string[]> PastAccepts = new()',
             '    {']
    for section in sorted(past):
        vals = ', '.join('"' + v.replace('\\', '\\\\').replace('"', '\\"') + '"' for v in past[section])
        lines.append(f'        ["{section}"] = new[] {{ {vals} }},')
    lines += ['    };', END]
    block = '\n'.join(lines)
    if '--print' in sys.argv:
        print(block)
        return
    path = f'{root}/{SRC}'
    src = open(path, encoding='utf-8', newline='').read().replace('\r\n', '\n')
    a, b = src.index(BEGIN), src.index(END) + len(END)
    open(path, 'w', encoding='utf-8', newline='').write(src[:a] + block + src[b:])
    print(f'{sum(len(v) for v in past.values())} earlier default(s) for {len(past)} store(s), from {len(commits)} versions')


if __name__ == '__main__':
    main()
