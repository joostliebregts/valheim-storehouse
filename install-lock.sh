# Sourced by build.sh and test-swap.sh before anything goes into (or out of) BepInEx/scripts or BepInEx/plugins.
# Two rules (the coordinator, 27 Oct, after an older build went live from a second session 30 s after an install):
#   1. Only the session that owns the install may do it: BepInEx/scripts/.storehouse-install-owner holds that session's name, and
#      the caller sets STOREHOUSE_SESSION to the same name. The owner writes the file once:
#        echo "<session name>" > "$APPDATA/com.kesomannen.gale/valheim/profiles/ValheimKK/BepInEx/scripts/.storehouse-install-owner"
#   2. Not while Valheim has a world loaded: Player.log's last "ZDOMan.LoadChunks done" (a world loaded) must not be newer than
#      its last "ZNet OnDestroy" (back to the menu). Except the live dev build (build.sh dev: install_lock <BepInEx> live): it
#      reloads in a world (Joost, 1 Nov). The 51 pieces lost on 25 Oct were not a reload: Storehouse 0.5.2 failed to load at all
#      (an apostrophe in a config name), so Valheim dropped its pieces at world load. A reloading copy leaves the prefabs
#      registered (Jotunn keeps the first copy's), and the dev build only places pieces in your own worlds.
# Staging into bin/ or work/ (test-swap.sh stage) needs neither.
install_lock() {
  local bepinex="$1" owner_file="$1/scripts/.storehouse-install-owner" owner
  if [ ! -f "$owner_file" ]; then
    echo "Refused: no install owner ($owner_file is missing). Only the session that owns BepInEx/scripts installs; it writes its name there."
    return 1
  fi
  owner=$(tr -d '\r\n' < "$owner_file")
  if [ -z "$owner" ] || [ "${STOREHOUSE_SESSION:-}" != "$owner" ]; then
    echo "Refused: BepInEx/scripts belongs to '$owner'; this caller is '${STOREHOUSE_SESSION:-unnamed}' (STOREHOUSE_SESSION). Stage into work/ instead and hand it to the owner."
    return 1
  fi
  [ "${2:-}" = live ] && return 0
  if tasklist //FI "IMAGENAME eq valheim.exe" 2>/dev/null | grep -qi "valheim.exe"; then
    local log="$USERPROFILE/AppData/LocalLow/IronGate/Valheim/Player.log" loaded left
    loaded=$(grep -n "ZDOMan.LoadChunks done" "$log" 2>/dev/null | tail -1 | cut -d: -f1)
    left=$(grep -n "ZNet OnDestroy" "$log" 2>/dev/null | tail -1 | cut -d: -f1)
    if [ -n "$loaded" ] && [ "${left:-0}" -lt "$loaded" ]; then
      echo "Refused: Valheim has a world loaded (Player.log line $loaded, no logout after it). Back to the main menu first."
      return 1
    fi
  fi
  return 0
}
