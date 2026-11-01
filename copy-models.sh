# Sourced by build.sh and test-swap.sh.
# The models: crib, and the meshes, atlas and anchors of each store's newest round and its alternatives (ship-rounds.py; each picks per
# file; the meat bundles' cords are meshes too). Previews stay here. $1 = the folder that gets assets/; $2 = dev for a dev install.
# Nothing taken from the game's files or other mods' ships (0.8.6, 1 Nov 2026): the item points that were assets/item_points.bin are read
# back from the player's GPU in game (ItemPoints), and the Ossuary's display sidecar (its native bone meshes, display_meshes/*-native.json,
# and the <slug>_display.json that indexes their faces) goes only into dev installs, the only builds that read it (PileDisplay).
copy_models() {
  rm -rf "$1/assets"
  mkdir -p "$1/assets/crib" && cp assets/crib/Crib.obj assets/crib/CribLogs.obj assets/crib/crib_atlas.png "$1/assets/crib/"
  if [ -f assets/crib/crib.json ]; then cp assets/crib/crib.json "$1/assets/crib/"; fi   # sample spots, when the model has them
  if [ -f assets/armory_outfits.json ]; then cp assets/armory_outfits.json "$1/assets/"; fi   # the armories' outfit map
  if [ -f assets/armorstand_pose.json ]; then cp assets/armorstand_pose.json "$1/assets/"; fi   # the vanilla Armor Stand pose (Joost's capture): the mannequins' worn sets and carved arms
  for d in $(python ship-rounds.py | tr -d '\r'); do   # newest round per store and the chosen alternatives (0.5.1), not every old round; no CR (Windows python)
    [ -d "$d" ] || continue
    mkdir -p "$1/$d"
    for f in "$d"/*.obj "$d"/*atlas*.png "$d"/*.json; do
      if [ -f "$f" ] && { [ "${2:-}" = dev ] || [ "${f%_display.json}" = "$f" ]; }; then cp "$f" "$1/$d/"; fi
    done
    if [ "${2:-}" = dev ] && [ -d "$d/display_meshes" ]; then mkdir -p "$1/$d/display_meshes" && cp "$d"/display_meshes/*-native.json "$1/$d/display_meshes/"; fi   # the Ossuary sidecar's meshes (dev only)
  done
}
