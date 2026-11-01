# Storehouse spec: what the mod is for

Read this before changing what a store holds, how big it is, or how it shows its contents. STYLE.md covers how stores look;
this file covers what they are for. Written 24 Oct 2026 from Joost's own words (22-24 Oct sessions), after a context
compaction lost them and the new stores were wrongly shrunk to 32 slots.

## Intent

**Mass storage that fits Valheim thematically.** It started as "a chest that is huge ... way larger than the black metal
chest" and grew into one store per kind of stuff, meant to replace the plain chests a base fills up with:

> "al deze dingen zijn eigenlijk een soort van massastorage. En het moet ook lijken alsof er meer in kan dan in een chest"
> (Joost, 22 Oct)

> "een oplossing voor al onze opslag. Gewoon een soort van mass storage die wel thematisch past" (23 Oct)

The selling point is the theme and the filter: you know at a glance that *this* is where the hides (or the tar, or the
bones) go, and that a lot of it fits.

## Size

- **Every store holds substantially more than a black metal chest** (4 rows of 8 = 32). Joost measures size against that
  chest: "als iets acht rijen heeft, dan is het al twee keer zo groot ... Acht rijen is best wel sick." Scrolling in the chest
  window is fine; a taller window (StorehouseUI) helps more than a smaller store.
- **64 slots is the standard for everything in and around the house** (agreed 22 Oct). Bigger where the store is bigger or
  the stuff comes in bulk; the count follows the store's own logic where it has one (nine crates of 8 = 72; 40 hooks + 24
  in the bins = 64).
- **The small exceptions are deliberate:** the Shelf (one item per stack, only what fits on the planks), and the half-size
  pieces that exist next to a full one (the half and low metal racks, the half-width Cloth Rack).
- **Open question (Joost, 24 Oct):** size by volume, "wat passend is voor een bepaalde opslaggrootte ... voor een volume":
  how much of that kind of stuff a base piles up, and how much the store looks like it can take. Decide that per store
  together with him; until then the sizes below stand. Never shrink a store as a general rule.

| Store | Slots | Note |
|---|---|---|
| Timber Crib | 64 | |
| Mead Rack, Larder Hutch, Meat Rack | 64 | stack (Mead Rack, Larder) |
| Produce Crates | 72 | nine crates of 8 |
| Ore Bin | 80 | bunker-sized, does not stack |
| Coal & Stone Bunker | 90 | stacks (load-bearing top) |
| Open Coal & Stone Bunker | 90 | the earlier bunker (r3), does not stack |
| Metal Rack (tall) / (tall, half) / (low) / (low, half) | 64 / 32 / 32 / 16 | stack |
| Metal Pallet | 64 | stacks |
| Cooper's Row, Fletcher's Barrels, Hide Rack, Apothecary Rack | 64 | |
| Treasure Hoard | 96 | |
| Ossuary Bin | 128 | |
| Cloth Rack | 32 | half width |
| Shelf (1, 2, 3 planks) | 6 per plank | display, holds anything |

## Principles

- **Native and our own:** our own models in Valheim's style (STYLE.md), never re-skinned stock chests. Logical real-world
  size: indoor pieces fit a 2 m room; outdoor pieces may be bigger.
- **Real item models inside.** Mass stores fill up visibly (heaps, rows, liquids) and **full must look full**. Display
  furniture shows one model per stack. One kind per bay, crate or vessel; two kinds sharing a bay get a board only when each
  has a real share.
- **A thematic filter per store,** by item type where possible so later items (Iron Gate's or other mods') land in the
  right store. The Shelf takes anything.
- **Placement must be obvious without instructions:** a store stands wherever it looks like it could stand (no wall-only
  pieces that look free-standing). Only what has a flat, sturdy top stacks; where both make sense, offer a stacking and a
  non-stacking variant as separate pieces.
- **Rubric for a new store** (23 Oct): it feels mentally logical ("dit past wel en dit is wat je ermee kan"), its size is
  logical, it may be bigger than a standard chest, and its theme says "hier kan ik echt zoveel shit in kwijt".

## What lies where (Joost, 24 Oct)

1. **Everything in the store shows from outside.** 2. **Nothing lies mixed** ("you'd never do that IRL"). Every kind gets its
own bay, crate, vessel or hook first; a kind that fills it may take an empty one, never one where something else lies; what
doesn't fit isn't drawn (the place already looks full). Two kinds share a place only where each kind's side still holds a copy
of it as drawn (Joost, 27 Oct: the Meat Rack's bins split into halves too narrow for any meat, so nothing showed there); a kind
with no such place is not shown, and the hover and the log count it as not shown, never as shown.

Three questions per store: does it have a place for every kind it takes; if not, where is sharing natural; and what
separates the kinds in that store's own theme.

| Store | Places vs kinds | When two kinds must share |
|---|---|---|
| Coal & Stone Bunker (both), Ore Bin, Ossuary | fewer bays than kinds | a thick plank (heavy bulk) |
| Produce Crates | fewer crates than kinds | a thin board (light goods) |
| Fletcher's Barrels | fewer barrels than arrow kinds | no board: each kind a bundle tied with cord |
| Hide Rack | fewer bays than hides | no board: folded hides lie as separate piles; each frame above shows its bay's hide, in that hide's colour |
| Treasure Hoard, Cooper's Row, Cloth Rack | one place per kind | never; a liquid is never shared |
| Apothecary Rack | one vessel per place, chosen by what it holds | never: the vessel follows the item (hook, glass, crock, basket), so a rack full of needles is all crocks; how full each vessel is shows |

## Variants and upgrades

- **Now: variants as separate pieces** (Joost, 24 Oct), like the vanilla chests and our metal racks: stacking and
  non-stacking bunker side by side, a stackable Cooper's Row next to the ground one. You empty the old one and build the new.
- Later ideas, not decided: upgrading a placed store in place (growing up is safer than growing back into a wall; never
  shrink while it holds items), and linking separate stores into one window. Nothing may ever make items unreachable or lost.

## Rules that protect the server

- If Storehouse is ever missing or fails to load while a world loads, Valheim deletes every Storehouse piece near a player,
  with its contents ("Destroyed invalid prefab ZDO"). A server start must show the Storehouse loaded line before anyone
  joins; every release is rehearsed on a copy of the server world with the item count (tools/storehouse-count.py).
- **Nothing may stand between the start and the pieces' registration** (25 Oct: the key "Contents in the frame's shade" made
  BepInEx throw in Settings.Bind, the mod never registered its pieces, and Valheim deleted 51 placed ones in Joost's test world).
  Every config entry binds through `Settings.Safe`: a key, section or value BepInEx refuses logs an error and the setting runs at
  its default from a memory-only file. The pieces are subscribed right after the settings; every later start-up step runs in
  `Plugin.Guard`, which logs and switches off only that step. `check-config-keys.py` (run by build.sh and test-swap.sh stage)
  fails on a key or section with `= \n \t \ " ' [ ]` and on any direct `config.Bind(` that bypasses `Settings.Safe`.
- Lowering a store's rows hides the items in the removed rows until the rows come back.
- **Released pieces stay** (0.4.0 live on 24 Oct): never remove a piece or lower its rows. A new model or layout for the same
  piece is safe (items live in the container, not the model). A redesign that changes what a store is (Fletcher's Barrels split
  into arrows, bolts and bombs; a 2 m Apothecary Rack) becomes a new piece beside the old one (Joost).
- Still being worked on after 0.4.0 (state 24 Oct, late): in code but NOT tested in game: Arrow Tubes, Bolt Crate, Bomb Crate,
  Tall Apothecary Rack, Pantry Dresser (r2 wired; r3 built, Joost to choose), Smith's Drawers, Jeweller's Casket, Ember Cabinet,
  Trophy Hall (r2, faces forward), Cooper's Row r6 (wired; r7 zigzag and r8 two tiers built, Joost to choose), Ossuary r3 (wired),
  triangle cap per stack and far LOD contents. Open: test all in a dev build (Joost's profile runs the 0.4.0 release; the dev copy
  is in BepInEx/_finn-holding/scripts-storehouse-dev-20261024), a narrower Bomb Crate, Tall Apothecary 8 vs 7 per row, Voidplasm
  liquid colour (the item is dark teal, not violet), Royal Jelly still in the server's Apothecary Accepts, and the server cfg's
  Accepts lines must be updated by hand at the next release (BepInEx keeps existing lines).

- **State 25 Oct (0.5.0 in progress):** the review's policy merged (A's 41 tests pass on the canonical file); bunkers draw
  heaps by stock (monotonic) with every kind shown, more than two kinds a bay side by side (boards switchable); Hide Rack per-kind
  piles; rough-glass loader ready for A's Cooper's Row and Apothecary rounds. Waiting on A's READY rows before any `_sol61`
  round is wired (Cooper's r9 then takes 13 goods; r6 stays the fallback, r7 never); Ossuary broad heaps wait for A's
  allocation recipe; Timber Crib shows its kinds only in the hover until A's crib round gives them a place; thread B's
  geometry-only rounds (z-fighting) get wired after the coordinator's re-audit. Nothing of this is tested in game yet.
---
- 2026-10-25: state section for 0.5.0 (integration by W).
- 2026-10-24: "What lies where" added (visibility first, never mixed, separators per store).
- 2026-10-24: written from Joost's words after the 32-slot mistake; sizes as in the code at commit 5957b038e.
