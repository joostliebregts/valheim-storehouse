"""Every BepInEx config section and key in Storehouse.cs must avoid = newline tab backslash " ' [ ] (BepInEx throws, the mod does not
hook in, and Valheim deletes every Storehouse piece near the player: 25 Oct, "Contents in the frame's shade"). Fails (exit 1) on any
string literal used as a Bind key or section, any `Section = "..."`, and any `const string`/variable named like a section, that holds
one. Store titles reach the config only through SectionSafe(); every entry binds through Settings.Safe (the runtime half: a throw falls
back to the default), and a direct .Bind( anywhere else fails this check. Every release store must sit in a Kinds.Groups theme group
(F1's categories and the hammer's order, 27 Oct). Run by test-swap.sh stage and build.sh; usage: python check-config-keys.py
"""
import os
import re
import sys

BAD = set('=\n\t\\"\'[]')
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Storehouse.cs'), encoding='utf-8').read()
lit = r'"((?:[^"\\]|\\.)*)"'
problems = []


def check(kind, text, at):
    value = bytes(text, 'utf-8').decode('unicode_escape')
    if any(c in BAD for c in value):
        problems.append(f'line {src[:at].count(chr(10)) + 1}: {kind} {value!r}')


for m in re.finditer(r'\.(?:Bind|Safe)(?:<[^>]*>)?\(\s*([^,]+?),\s*' + lit, src):
    check('key', m.group(2), m.start())
    sec = m.group(1).strip()
    if sec.startswith('"'):
        check('section', sec.strip('"'), m.start())
for m in re.finditer(r'\bSection\s*=\s*' + lit, src):
    check('section', m.group(1), m.start())
for m in re.finditer(r'\b(?:string|var)\s+(\w*(?:section|perf|debug|Section)\w*)\s*=\s*' + lit, src):
    check('section variable ' + m.group(1), m.group(2), m.start())
binds = len(re.findall(r'config\.Safe(?:<[^>]*>)?\(', src))
direct = [src[:m.start()].count(chr(10)) + 1 for m in re.finditer(r'\b(?:[cC]onfig|fallback)\.Bind(?:<[^>]*>)?\(', src)
          if not re.search(r'return (?:config|fallback)\.Bind\(', src[max(0, m.start() - 20):m.end()])]
if direct:
    problems.append('config entries bound without Settings.Safe (a throw there stops the start) at line ' + ', '.join(map(str, direct)))
if 'SectionSafe(title)' not in src:
    problems.append('store sections are no longer built with SectionSafe(title)')


# F1 and the hammer by theme (Kinds.Groups, Joost 27 Oct): a store in the release set but in no group would show in F1 under
# "Test pieces (dev)" and sit after the shelves in the hammer tab.
def slugs(name):
    m = re.search(r'\b' + name + r'\s*=\s*new\(StringComparer\.Ordinal\)\s*\{(.*?)\n\s*\};', src, re.S)
    return set(re.findall(r'"([a-z0-9_]+)"', re.sub(r'//[^\n]*', '', m.group(1)))) if m else set()


groups = re.search(r'\bGroups\s*=\s*\{(.*?)\n\s*\};', src, re.S)
released = slugs('Released') | slugs('NextRelease')
grouped = set(re.findall(r'"([a-z0-9_]+)"', groups.group(1))) if groups else set()
if not groups or not released:
    problems.append('Kinds.Groups, Kinds.Released or Kinds.NextRelease not found')
elif released - grouped:
    problems.append('release stores in no Kinds.Groups group (F1 would show them under Test pieces): ' + ', '.join(sorted(released - grouped)))
if problems:
    print('CONFIG KEYS: FAIL\n  ' + '\n  '.join(problems))
    sys.exit(1)
print(f'CONFIG KEYS: PASS ({binds} entries through Settings.Safe, no direct Bind; literal keys and sections free of = newline tab backslash quotes [ ]; '
      f'all {len(released)} release stores in a theme group)')
