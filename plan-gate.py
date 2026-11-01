"""The gate for the units style's plan step (DisplayPlan.cs): two captures (storehouse_selftest capture <tag>), one from before the
split and one after it.
  (i)  every <store>/<state>-draw.json of before is byte-identical in after (the same parts, materials, meshes and matrices);
  (ii) planrun makes, from each after/<store>/<state>-inputs.json alone, the very plan the game wrote to <state>-plan.json.
    python plan-gate.py <before capture dir> <after capture dir>
Prints PASS or FAIL with the first differences; exit 0 on PASS."""
import difflib, glob, os, subprocess, sys, tempfile

here = os.path.dirname(os.path.abspath(__file__))


def files(root, suffix):
    return {os.path.relpath(p, root).replace('\\', '/'): p for p in glob.glob(os.path.join(root, '*', '*' + suffix))}


def first_diff(a, b, name):
    la, lb = a.decode('utf-8', 'replace').splitlines(), b.decode('utf-8', 'replace').splitlines()
    return '\n'.join(list(difflib.unified_diff(la, lb, name + ' (expected)', name + ' (got)', n=1, lineterm=''))[:12])


def main(before, after):
    problems = []
    # (i) draw.json, byte for byte.
    b, a = files(before, '-draw.json'), files(after, '-draw.json')
    for name in sorted(set(b) - set(a)): problems.append(f'draw: {name} missing in after')
    for name in sorted(set(a) - set(b)): problems.append(f'draw: {name} new in after (not in before)')
    same = 0
    for name in sorted(set(a) & set(b)):
        x, y = open(b[name], 'rb').read(), open(a[name], 'rb').read()
        if x == y: same += 1
        else: problems.append(f'draw: {name} differs\n{first_diff(x, y, name)}')
    print(f'draw.json: {same} of {len(b)} identical' + (' (expected 196)' if len(b) != 196 else ''))
    # (ii) planrun on every after inputs.json, against the plan the game wrote.
    out = os.path.join(here, 'planrun', 'bin', 'gate')
    build = subprocess.run(['dotnet', 'build', os.path.join(here, 'planrun', 'planrun.csproj'), '-c', 'Release', '-nologo', '-v', 'q', '-o', out],
                           capture_output=True, text=True)
    if build.returncode != 0:
        problems.append('planrun: build failed\n' + build.stdout[-2000:])
    else:
        with tempfile.TemporaryDirectory() as tmp:
            run = subprocess.run(['dotnet', os.path.join(out, 'planrun.dll'), '--batch', after, tmp], capture_output=True, text=True)
            print(run.stdout.strip())
            if run.returncode != 0: problems.append('planrun: ' + (run.stderr.strip()[:2000] or f'exit {run.returncode}'))
            game, made = files(after, '-plan.json'), files(tmp, '-plan.json')
            inputs = files(after, '-inputs.json')
            for name in sorted(inputs):
                if name.replace('-inputs.json', '-plan.json') not in game: problems.append(f'plan: the game wrote no plan for {name}')
            match = 0
            for name in sorted(game):
                if name not in made: problems.append(f'plan: planrun made none for {name}'); continue
                x, y = open(game[name], 'rb').read(), open(made[name], 'rb').read()
                if x == y: match += 1
                else: problems.append(f'plan: {name}: planrun differs from the game\n{first_diff(x, y, name)}')
            print(f'plan.json: {match} of {len(game)} made identically by planrun')
    if problems:
        print(f'FAIL ({len(problems)} problem(s)); the first:')
        for p in problems[:8]: print(' - ' + p)
        return 1
    print('PASS')
    return 0


if __name__ == '__main__':
    if len(sys.argv) != 3: sys.exit(__doc__)
    sys.exit(main(sys.argv[1], sys.argv[2]))
