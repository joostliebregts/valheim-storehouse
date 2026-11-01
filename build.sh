#!/usr/bin/env bash
# Build Storehouse.dll and pack the Thunderstore zip. Build only: no deploy target (install through Gale from the zip).
# The release (0.3.0 on) is the dev code (DEV) with RELEASE on top: version check, pieces in every world, no skin hotkey,
# no perf log. It ships every model the dev build reads (copy_models: the crib and each <store>_r<n> folder, our own
# Blender output) under plugins/Storehouse/assets/, but nothing taken from the game: the Ossuary's display sidecar (the game's
# bone meshes) goes only into dev installs (copy_models <folder> dev). The Strongbox is parked and not packed.
#   ./build.sh dev         the dev variant (no version check, pieces only in your own worlds) LIVE: into BepInEx/scripts,
#                          where ScriptEngine (re)loads it in the running game within ~2 s (tools/valheim-mods/LIVE-MODDING.md).
#                          Models go to scripts/Storehouse/assets; with "Live models" on it reads them straight from assets/ here.
#                          Refuses while the plugins copy (dev-plugin) is installed: both would load.
#   ./build.sh dev-plugin  the dev variant the old way, into BepInEx/plugins (takes effect at the next game start).
#                          Refuses while the live copy is in scripts.
set -euo pipefail
cd "$(dirname "$0")"
v=$(grep -o 'const string Version = "[^"]*"' Storehouse.cs | cut -d'"' -f2)
bepinex="${STOREHOUSE_BEPINEX:-$APPDATA/com.kesomannen.gale/valheim/profiles/ValheimKK/BepInEx}"   # your BepInEx folder: STOREHOUSE_BEPINEX (BUILDING.md)
cfg="$bepinex/config/com.joostliebregts.storehouse.cfg"

. ./copy-models.sh   # copy_models <folder>: the models every build ships
. ./install-lock.sh   # install_lock <BepInEx> [live]: only the install owner; not with a world loaded, except live
default_cfg() {
  [ -f "$cfg" ] || printf '[9 - Debug]\n\nLive models = true\n\nModel folder = %s\n' "$(cygpath -m "$PWD/assets")" > "$cfg"
}

if [ "${1:-}" = dev ]; then
  install_lock "$bepinex" live || exit 1   # the live copy may reload with a world loaded (install-lock.sh, rule 2)
  plugin_copy="$bepinex/plugins/Finn-Storehouse-dev/Storehouse/Storehouse.dll"
  if [ -f "$plugin_copy" ]; then
    echo "The plugins copy is installed ($plugin_copy): with the game CLOSED, remove the folder plugins/Finn-Storehouse-dev, then run this again."
    exit 1
  fi
  python check-config-keys.py || { echo "Not built: a config key or section BepInEx would refuse (the mod would not load)."; exit 1; }
  python check-rounds.py || { echo "Not built: a store's newest model round is incomplete (it would show an older round)."; exit 1; }
python check-pose-tables.py || { echo "Not built: a pose table no longer matches its anchors' bytes (the mod would refuse it)."; exit 1; }
  python check-display.py || { echo "Not built: a store in the release set holds more than it can show, or accepts a kind it has no place for."; exit 1; }
  dotnet build -c Release -nologo -v q -p:DefineConstants=DEV -o bin/dev
  scripts="$bepinex/scripts"
  copy_models "$scripts/Storehouse" dev   # ScriptEngine only loads DLLs at the top of scripts/ (IncludeSubdirectories off)
  default_cfg
  # ScriptEngine reads the symbols too and refuses a DLL without its .pdb: the pdb first, the DLL last (that triggers the reload).
  cp bin/dev/Storehouse.pdb "$scripts/Storehouse.pdb"
  cp bin/dev/Storehouse.dll "$scripts/Storehouse.dll"
  echo "live: dev build $v -> $scripts (ScriptEngine reloads it in ~2 s; reloads every other mod in scripts too)"
  exit 0
fi
if [ "${1:-}" = dev-plugin ]; then
  install_lock "$bepinex" || exit 1
  if [ -f "$bepinex/scripts/Storehouse.dll" ]; then
    echo "The live copy is in scripts: take it out first (bash ../valheim-mods/dev/live.sh --off Storehouse), then run this again."
    exit 1
  fi
  dotnet build -c Release -nologo -v q -p:DefineConstants=DEV -o bin/dev
  dest="$bepinex/plugins/Finn-Storehouse-dev/Storehouse"
  copy_models "$dest" dev
  # The DLL last: while the game runs it holds the old one open, and the copy fails here (it then lands at the next start).
  cp bin/dev/Storehouse.dll "$dest/" || { echo "Storehouse.dll is locked (the game has it loaded): models copied, DLL not; run build.sh dev-plugin again with the game closed."; exit 1; }
  default_cfg
  echo "dev build $v -> $dest (takes effect at the next game start)"
  exit 0
fi
python check-config-keys.py || { echo "Not built: a config key or section BepInEx would refuse (the mod would not load)."; exit 1; }
python check-rounds.py || { echo "Not built: a store's newest model round is incomplete (it would show an older round)."; exit 1; }
python check-pose-tables.py || { echo "Not built: a pose table no longer matches its anchors' bytes (the mod would refuse it)."; exit 1; }
python check-display.py || { echo "Not built: a store in the release set holds more than it can show, or accepts a kind it has no place for."; exit 1; }
# The fix list (~/.pai/tools/valheim-storehouse/fixes.json, CLAUDE.md here): no release while an approved or in-progress fix is
# neither done in this version nor left open on purpose (STOREHOUSE_OPEN_FIXES=F3,...).
fixes="${STOREHOUSE_FIXES:-$HOME/.pai/tools/valheim-storehouse/roadmap.ts}"
if [ -f "$fixes" ]; then bun "$fixes" release-check "$v" || exit 1; else echo "note: fix list not found (only on the author's machine); release check skipped"; fi
dotnet build -c Release -nologo -v q -p:DefineConstants=DEV%3BRELEASE -o bin/release
# The live gate (the coordinator's retro, 26 Oct): a release is packed only after a real game start ran exactly this DLL to the main
# menu with every piece registered and no start-up failure. The build is deterministic, so the same source gives the same hash.
sha=$(sha256sum bin/release/Storehouse.dll | cut -c1-12)
logs=("$bepinex/LogOutput.log" "${USERPROFILE:-$HOME}/AppData/LocalLow/IronGate/Valheim/Player.log")
live=$(cat "${logs[@]}" 2>/dev/null | tr -d '
' | grep -o "Storehouse $v: live, sha256 $sha, [0-9]*/[0-9]* pieces, [0-9]* start-up failure(s)[^.]*" | tail -1 || true)
if [ -z "$live" ]; then
  echo "Not packed: no game start ran this release DLL (sha256 $sha). bash test-swap.sh stage --release && bash test-swap.sh on --release,"
  echo "start Valheim to the main menu, quit, bash test-swap.sh off, then build.sh again."
  exit 1
fi
pieces=$(echo "$live" | grep -o '[0-9]*/[0-9]* pieces' | cut -d' ' -f1)
if [ "${pieces%/*}" != "${pieces#*/}" ] || ! echo "$live" | grep -q ", 0 start-up failure(s)"; then
  echo "Not packed: the game start of this DLL did not load fully: $live"
  exit 1
fi
echo "live gate: $live"
mkdir -p package/plugins/Storehouse
cp bin/release/Storehouse.dll package/plugins/Storehouse/
copy_models package/plugins/Storehouse
echo "packed $(find package/plugins/Storehouse/assets -type f | wc -l) model file(s) in $(ls package/plugins/Storehouse/assets | wc -l) folder(s)"
# The package gets the public changelog (CHANGELOG.public.md); CHANGELOG.md keeps the developer history and stays out of it.
head -n 5 CHANGELOG.public.md | grep -qx "## $v" || { echo "Not packed: CHANGELOG.public.md has no '## $v' entry at the top."; exit 1; }
cp CHANGELOG.public.md package/CHANGELOG.md
cp README.md LICENSE package/
sed -i "s/\"version_number\":\"[^\"]*\"/\"version_number\":\"$v\"/" package/manifest.json
[ -f package/icon.png ] || echo "note: package/icon.png missing (Thunderstore needs a 256x256 icon: Joost's badge, Videos/Storehouse/icon/out/storehouse-icon.png)"
# Forward slashes in the zip (Compress-Archive wrote backslashes, which Linux and Mac unzip into one long file name).
rm -f "Finn-Storehouse-$v.zip"
python -c "
import os, sys, zipfile
with zipfile.ZipFile(sys.argv[2], 'w', zipfile.ZIP_DEFLATED) as z:
    for d, _, fs in os.walk(sys.argv[1]):
        for f in sorted(fs):
            p = os.path.join(d, f)
            z.write(p, os.path.relpath(p, sys.argv[1]).replace(os.sep, '/'))
" package "Finn-Storehouse-$v.zip"
echo "built $v"
