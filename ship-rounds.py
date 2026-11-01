"""The model folders a build ships (copy-models.sh): per store its newest round (the first of its rounds list in Storehouse.cs that
exists under assets/, else the newest of the default list), plus the alternatives in Kinds.ModelAlternates; the Meat Rack's newest
bundles. Older rounds carry z-fighting and are not meant to be chosen (0.5.1). Prints one assets/<folder> per line.
"""
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'Storehouse.cs'), encoding='utf-8').read()
assets = os.path.join(HERE, 'assets')
DEFAULT = ['_r6', '_r5', '_r4', '_r3', '_r2']
alt = {m.group(1): re.findall(r'"(_r\d+\w*)"', m.group(2))   # round names may carry a suffix (_r3ds, _r5b)
       for m in re.finditer(r'\["(\w+)"\] = new\[\] \{([^}]*)\}', src[src.index('ModelAlternates'):src.index('public static readonly Kind[] Stores')])}
out = []
for m in re.finditer(r'\bStore\("(\w+)",', src):
    slug = m.group(1)
    i, depth, in_str = m.start() + len('Store'), 0, False
    while i < len(src):   # to the call's own closing parenthesis, strings skipped
        ch = src[i]
        if in_str:
            if ch == '\\': i += 1
            elif ch == '"': in_str = False
        elif ch == '"': in_str = True
        elif ch == '(': depth += 1
        elif ch == ')':
            depth -= 1
            if depth == 0: break
        i += 1
    call = src[m.end():i]
    r = re.search(r'rounds: new\[\] \{([^}]*)\}', call)
    rounds = re.findall(r'"(_r\d+\w*)"', r.group(1)) if r else DEFAULT
    first = next((x for x in rounds if os.path.isdir(os.path.join(assets, slug + x))), None)
    for x in ([first] if first else []) + alt.get(slug, []):
        d = slug + x
        if os.path.isdir(os.path.join(assets, d)) and d not in out:
            out.append(d)
bundles = sorted((d for d in os.listdir(assets) if re.fullmatch(r'meatbundles_r\d+', d)), key=lambda d: int(d.split('_r')[1]))
if bundles:
    out.append(bundles[-1])
for d in out:
    print('assets/' + d)
