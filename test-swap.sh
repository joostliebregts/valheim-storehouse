#!/usr/bin/env bash
# Test a Storehouse build in your own world, and back again for the server. The server runs the release Storehouse inside the
# KritterKruelty_Extras bundle (plugins/KritterKruelty_Extras/Storehouse); a test build must replace it, never sit beside it:
# two Storehouse.dll files would both load (build.sh dev only guards against Finn-Storehouse-dev, not the bundle).
#
# From PowerShell or cmd: test-swap.cmd on   (the same, through Git Bash)
#   bash test-swap.sh stage [--release] build the dev variant into bin/dev (--release: the release into bin/release) and stage it,
#                                      with the models, in bin/test-<version> (bin/test-<version>-release)
#   bash test-swap.sh on  [--dry-run]  with Valheim CLOSED: the bundle's Storehouse goes to BepInEx/_finn-holding, the staged
#                                      build goes to BepInEx/scripts (ScriptEngine loads it; build.sh dev updates it live after)
#   bash test-swap.sh off [--dry-run]  with Valheim CLOSED: the test build goes to _finn-holding, the bundle's Storehouse comes back
#   bash test-swap.sh on --release     the same, but the staged release goes to plugins/Finn-Storehouse-test (BepInEx loads it, as
#                                      a release is loaded): start Valheim to the main menu, quit, 'off'; build.sh then packs it
#   bash test-swap.sh status           which Storehouse.dll files would load now
# Nothing is deleted: whatever is taken out is moved under _finn-holding with the date. Portal Compass and Hearthwoven in the
# bundle stay where they are. The dev build lets you place the pieces in your own worlds only and cannot join the server.
set -euo pipefail
cd "$(dirname "$0")"
. ./copy-models.sh
v=$(grep -o 'const string Version = "[^"]*"' Storehouse.cs | cut -d'"' -f2)
# Git Bash only: from PowerShell, "bash" may be WSL, which has no APPDATA (test-swap.cmd starts the right one).
[ -n "${APPDATA:-}" ] || { echo "APPDATA is not set: run this from Git Bash or with test-swap.cmd, not WSL."; exit 1; }
bepinex="${STOREHOUSE_BEPINEX:-$APPDATA/com.kesomannen.gale/valheim/profiles/ValheimKK/BepInEx}"
# From 0.8.0 the release is the Thunderstore package Gale installs (same shape: Storehouse.dll and assets/ at its root);
# before it, the KritterKruelty_Extras bundle.
# Decided by the old bundle being there, not the package: during a swap the package folder is out in _finn-holding.
bundle="$bepinex/plugins/DJ_Lifecoach-Storehouse"
[ -d "$bepinex/plugins/KritterKruelty_Extras/Storehouse" ] && bundle="$bepinex/plugins/KritterKruelty_Extras/Storehouse"
scripts="$bepinex/scripts"
holding="$bepinex/_finn-holding"
day=$(date +%Y%m%d)
dry=0
release=0
for a in "${@:2}"; do
  case "$a" in --dry-run) dry=1 ;; --release) release=1 ;; *) echo "unknown option $a"; exit 1 ;; esac
done
stage="bin/test-$v"
[ $release = 1 ] && stage="bin/test-$v-release"
plugintest="$bepinex/plugins/Finn-Storehouse-test"

do_() { if [ $dry = 1 ]; then echo "  would: $*"; else "$@"; fi; }
# Gale (from 0.8.3) unpacks the package one level down: plugins/DJ_Lifecoach-Storehouse/Storehouse/Storehouse.dll.
has_dll() { [ -f "$1/Storehouse.dll" ] || [ -f "$1/Storehouse/Storehouse.dll" ]; }

# Every Storehouse.dll under BepInEx, and whether BepInEx or ScriptEngine loads it: anything under plugins/, and the top level
# of scripts/ (ScriptEngine does not look in subfolders). Exactly one may load.
status() {
  local n=0
  while IFS= read -r f; do
    rel=${f#"$bepinex/"}
    case "$rel" in
      plugins/*|scripts/Storehouse.dll) echo "  LOADS  $rel"; n=$((n + 1)) ;;
      *) echo "  idle   $rel" ;;
    esac
  done < <(find "$bepinex" -name Storehouse.dll -not -path "*/DumpedAssemblies/*" -not -path "*/cache/*" 2>/dev/null | sort)
  if [ $n = 1 ]; then echo "  OK: exactly one Storehouse loads"; else echo "  WARNING: $n Storehouse.dll files load (must be exactly 1)"; fi
}

. ./install-lock.sh   # install_lock <BepInEx>: only the install owner, never with a world loaded
game_closed() {
  install_lock "$bepinex" || exit 1
  if tasklist //FI "IMAGENAME eq valheim.exe" 2>/dev/null | grep -qi "valheim.exe"; then
    echo "Valheim is running: close it first (the game holds Storehouse.dll open)."
    exit 1
  fi
}

case "${1:-}" in
  stage)
    python check-config-keys.py || { echo "Not staged: a config key or section BepInEx would refuse (the mod would not load)."; exit 1; }
    python check-rounds.py || { echo "Not staged: a store's newest model round is incomplete (it would show an older round)."; exit 1; }
    python check-display.py || { echo "Not staged: a store in the release set holds more than it can show, or accepts a kind it has no place for."; exit 1; }
    out=bin/dev; defs=DEV
    [ $release = 1 ] && { out=bin/release; defs="DEV%3BRELEASE"; }
    dotnet build -c Release -nologo -v q -p:DefineConstants=$defs -o $out
    rm -rf "$stage"
    mkdir -p "$stage"
    cp $out/Storehouse.dll $out/Storehouse.pdb "$stage/"
    copy_models "$stage/Storehouse"
    echo "staged $([ $release = 1 ] && echo release || echo dev) build $v in $stage ($(find "$stage/Storehouse/assets" -type f | wc -l) model files), DLL sha256 $(sha256sum "$stage/Storehouse.dll" | cut -c1-12)"
    ;;
  on)
    [ $dry = 1 ] || game_closed
    [ -f "$stage/Storehouse.dll" ] || { echo "Nothing staged in $stage: run 'bash test-swap.sh stage$([ $release = 1 ] && echo ' --release')' first."; exit 1; }
    [ -f "$scripts/Storehouse.dll" ] && { echo "A Storehouse is already in scripts/: the test is on (or a dev copy is there). 'off' first."; exit 1; }
    [ -e "$plugintest" ] && { echo "$plugintest exists: a release test is on. 'off' first."; exit 1; }
    has_dll "$bundle" || { echo "No Storehouse in the bundle ($bundle): nothing to swap out."; exit 1; }
    away="$holding/$day-storehouse-release-for-$v-test"
    [ -e "$away" ] && { echo "$away already exists: a test swap from today is still out. 'off' first."; exit 1; }
    do_ mkdir -p "$holding"
    if [ $release = 1 ]; then
      echo "on: release Storehouse -> $away; staged release $v -> $plugintest"
      do_ mv "$bundle" "$away"
      do_ mkdir -p "$plugintest"
      do_ cp -r "$stage/Storehouse" "$plugintest/Storehouse"
      do_ cp "$stage/Storehouse.dll" "$stage/Storehouse.pdb" "$plugintest/Storehouse/"
    else
      echo "on: release Storehouse -> $away; test build $v -> $scripts"
      do_ mv "$bundle" "$away"
      do_ mkdir -p "$scripts"
      do_ cp -r "$stage/Storehouse" "$scripts/Storehouse"
      # ScriptEngine refuses a DLL without its symbols: the pdb first, the DLL last.
      do_ cp "$stage/Storehouse.pdb" "$scripts/Storehouse.pdb"
      do_ cp "$stage/Storehouse.dll" "$scripts/Storehouse.dll"
    fi
    [ $dry = 1 ] || status
    ;;
  off)
    [ $dry = 1 ] || game_closed
    away=$(ls -d "$holding"/*-storehouse-release-for-*-test 2>/dev/null | sort | tail -1 || true)
    [ -n "$away" ] && has_dll "$away" || { echo "No release Storehouse waiting in $holding: nothing to put back."; exit 1; }
    [ -e "$bundle" ] && { echo "$bundle exists again (Gale reinstalled it?): sort that out by hand first."; exit 1; }
    back="$holding/$day-$(date +%H%M)-storehouse-test-build-off"
    echo "off: test build -> $back; release Storehouse <- $away"
    do_ mkdir -p "$back"
    for f in Storehouse.dll Storehouse.pdb Storehouse; do
      if [ -e "$scripts/$f" ]; then do_ mv "$scripts/$f" "$back/"; fi
    done
    if [ -e "$plugintest" ]; then do_ mv "$plugintest" "$back/Finn-Storehouse-test"; fi
    do_ mv "$away" "$bundle"
    [ $dry = 1 ] || status
    ;;
  status) status ;;
  *) sed -n 2,13p "$0"; exit 1 ;;
esac
