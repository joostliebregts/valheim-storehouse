# Changelog

## 0.8.6

- The mod no longer ships any shapes taken from the game's files or other mods. Items whose model the game keeps on the graphics card are now measured in your own game the first time a store shows them, and remembered in BepInEx/cache (Storehouse-item-points.bin). They sit in the stores as before; items from other mods are now measured too.
- The first piece in the Storage tab says that Storehouse is an unofficial mod, not affiliated with or endorsed by Iron Gate or Coffee Stain.
- The Brewer's Cabinet takes the barley wine base too; it took the finished barley wine but refused its base. Thanks to ShadowTox for the report.
- The Brewer's Cabinet takes everything a Fermenter takes in or gives out, from the game and from any mod, so other mods' meads and mead bases fit too.
- A store opens where its items are: at the top when a sorting or filter mod put them there, at the bottom when the game did, and at the top when it's empty. Thanks to ShadowTox for the report.
- The main menu shows "Storehouse 0.8.6 loaded" at the top left, so after an update you can see it loaded before you load your world. If it did not load fully, a red warning shows instead; no line at all means it did not load.
- Works together with other 0.8 versions: you can join a server that runs an older 0.8.

## 0.8.5

- Fixed backpacks disappearing when you put them into a store that doesn't take them, with Store All (Quick Stack mod), shift-click or any other way. Adventure Backpacks said yes after the store said no; the store's no now holds, and the backpack stays with you.
- Fixed shift-click giving you a second copy when the item stacked onto a stack already in the store.
- Works together with 0.8.4 and other 0.8 versions: you can join a server that runs an older 0.8.

## 0.8.4

- New store guide on this page: every store with its picture, and at the bottom the full list of what goes where. Nothing changed in the game.

## 0.8.3

- Fixed items that a store doesn't take disappearing when you shift-click them into it (seen with backpacks and the Armory Island). A shift-click now checks first whether the store takes the item and has a place for it; if not, the item stays with you.

## 0.8.2

- Fixed weapons and shields in the Arsenal and Armory pieces not hanging in their proper places (broken in 0.8.1).

## 0.8.1

- Some items have a better home now: a few storage locations rebalanced.
- Fixed a big stutter when you put items into the Arsenal Spine.
- More stores have snap points, so they line up side by side.

## 0.8.0

First public release.

- Adds 47 storage pieces. Each piece keeps one type of item and shows the items that are in it.
- More than 50 new 3D models, made for this mod in the style of Valheim.
- We tested the pieces in the game for many hours. This is a hobby mod, but we tested it carefully.
