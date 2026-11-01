# Storehouse items: what still has no home, and where it should go

A proposal, not a change. Nothing in the mod, the config or the server was touched. Written 24 Oct 2026 for Joost, from SPEC.md
(intent, "What lies where", "Released pieces stay"), the filters in `Storehouse.cs` (the `Kinds.Stores` Accepts lists and the type rules
in `ItemRules`), and the server's live config override.

## Summary

| | Count |
|---|---|
| Items looked at (stackable materials, consumables, trophies, valuables, misc, plus the server's modded ones; weapons, armour, build pieces left out) | **605** |
| Already have a store (by name list, wildcard or type rule) | **278** |
| **No store takes them** | **327** |
| of those: proposed moves into an **existing** store | **62** (60 sure, 2 gold items to check) |
| of those: proposed for **5 new stores** | **137** (71 trophies, 32 pantry goods, 12 gems and relics, 12 hardware, 10 glowing cores) |
| of those: one-offs the existing **Shelf** already takes (keys, boss drops, tankards, moulds, boss-power items) | **82** |
| of those: worn gear, tools and saddles, a separate rack idea (end of the proposals) | **30** |
| of those: internal upgrade-step items, not worth storing | **16** |
| Items whose current home looks wrong, doubled or accidental | **8** (section 3) |

Not in these counts: 8 siege and firework items that sit in the weapons folder (ballista bolts x5, catapult ammo x2, the sparkler); they also
have no home and are proposed for Fletcher's Barrels in section 1.

**New stores proposed (5):** Trophy Hall (71 trophies, one board each), Pantry Dresser (flour, dough, spices, feast ingredients, uncooked
dishes), Smith's Drawers (nails, chain and fittings), Jeweller's Casket (gems, ancient coins, pot shards), Ember Cabinet (wisps, cores, embers,
orbs). One optional sixth, a Tackle Locker, only if you do not want the bait in the Apothecary Rack.

### How this was made, and what to trust

- The item universe is the game's own asset folders (the dump in the session scratchpad: `materials`, `consumables`, `trophies`, `valuables`,
  `misc`, `Trinkets`, `utility`, `Upgrades`, `tools`), cross-checked against Jotunn's item list, plus the 13 fish prefabs. Mods come from the
  `Added item` lines in `Player.log` and the server mod configs: ValheimArmory adds 147 prefabs (about 130 weapons, shields and staves, 14 arrows
  and bolts that the Fletcher's patterns already take, 4 gold moulds and casts), Storehouse its own board, PlanBuild a crystal and a rune,
  ClayBuildPieces its clay (stack 50). No other server mod adds a stackable that I could find (FeastMaster, TameCraft and the camps use vanilla items).
- **I could not read each item's `m_itemType` offline.** The "type" column is the asset folder, which is only a good guess (the `consumables`
  folder also holds moulds and uncooked dishes). Items covered "by type rule" (meals, meads, produce, meat, ore, bars) are assumed to land
  where the rule says; section 3 lists the spots where I doubt that. A 10-minute in-game check (Store All beside each store) would settle it.
- Biomes and in-game names come from the prefab names and my knowledge of Valheim 1.0; a `?` means unsure. The wiki search did not confirm
  every Deep North and Ashlands item.
- **Server config drift:** BepInEx never rewrites an `Accepts` line that already exists in a config. Every Accepts addition below therefore
  also needs the server's `com.joostliebregts.storehouse.cfg` edited (it is already out of step once: section 4). The cleaner route is how
  `animalParts` was done: put new names in the code (a fixed set or pattern in `ItemRules`), so an old config cannot hold them back.

---

## 1. Moves into existing stores (62 items)

Filter changes only. "Layout" says whether the store's model already has a place; per SPEC every kind needs its own bay, crate or vessel,
or an honest way to share. None of these removes anything, so "released pieces stay" holds.

| Store | Items to add | Why it fits | Accepts / rule to add | Layout |
|---|---|---|---|---|
| **Timber Crib** (5) | Storehouse board, Root, Writhan roots, Barka branch, Ymir flesh | The board is the mod's own timber and nothing takes it today. Roots and branches are timber-ish stock next to elder bark. Ymir flesh is low confidence (building stock; could be the Apothecary). | `StorehouseBoard,Root,WrithanRoots,BarkaBranch,YmirRemains` | Crib is a rack of logs; boards and roots stack as a bundle. Fine. |
| **Coal & Stone Bunker**, both (7) | Sulfur stone, Stone rock, Pungent pebbles, Thunderstone, Clay (ClayBuildPieces), Frozen fuel, Ice | Loose heaps by the barrow-load: stone, clay, fuel, ice. The old parked Strongbox list already had Sulfur stone. Clay is the one modded item certain to pile up (collectors give 60 an hour, stack 50). | `SulfurStone,StoneRock,PungentPebbles,Thunderstone,BFP_Clay,FrozenFuel,Ice` | Three bays for 14 kinds: sharing is already the rule here (thick plank). Ice and Frozen fuel are the Deep North pair that could later get a "cold" variant. |
| **Produce Crates** (6) | Acorn, Ancient seed, Fir cone, Fir cone (frost), Pine cone, Fresh seaweed | The crates take seeds, but only names ending in `Seeds`; cones and acorns are the forest's seeds and the seaweed is a sea plant. | `Acorn,AncientSeed,FirCone,FirConeFrost,PineCone,FreshSeaweed` | Light goods share a thin board: fine. |
| **Cooper's Row**, both (6) | Honey, Charcoal resin, Ooze (Mork), Hateful blood, Void plasm, Blob vial | Sticky and liquid goods, one kind per vessel. Honey belongs with Royal Jelly, which you just moved there (section 3). The rest are the later biomes' goo. | `Honey,CharcoalResin,OozeMork,HatefulBlood,Voidplasm,BlobVial` | Cooper's has one place per kind, so six more vessels is a **new layout**: a newer model of the same piece is safe (items live in the container), or a third piece beside the two that exist. |
| **Fletcher's Barrels** (7, plus 8 not counted) | Fireworks rockets (7 colours), Sparkler; ballista bolts (5), catapult ammo (2) | Things you load and launch. The `Bolt*` pattern does not match `TurretBolt*`, and `Catapult_*` is not a `Bomb*`. | `FireworksRocket_*,Sparkler,TurretBolt*,Catapult_*` | The store is being split into arrows, bolts and bombs (SPEC): siege bolts join the bolt store; catapult ammo and fireworks the bomb crate. |
| **Apothecary Rack** (18) | Fishing bait (9 kinds), Fishing hook, Mole claws, Cured squirrel hamstring, Dvergr needle, Queen bee, Proustite powder, Powdered dragon egg, Soft tissue, Larva | Small things in jars, crocks and on hooks. The rack already has a hook vessel (SPEC), so bait tins and a fishing hook fit its own logic. Powders go in jars. | `FishingBait*,Hook,MoleClaws,CuredSquirrelHamstring,DvergrNeedle,QueenBee,ProustitePowder,PowderedDragonEgg,Softtissue,Larva` | "One vessel per place, chosen by what it holds": 18 more kinds on top of today's 22 nearly fills the 64 places, so do it with the planned 2 m / 5 x 8 version. **Alternative:** the Tackle Locker (section 2) for the bait and hook only. |
| **Ossuary Bin** (8) | Asksvin carrion neck, pelvic and ribcage, Undead bjorn ribcage, Large bone (+ 2 halves), Ghost skull | More bones next to the skull already in the bin. | `AsksvinCarrionNeck,AsksvinCarrionPelvic,AsksvinCarrionRibcage,UndeadBjornRibcage,LargeBone*,GhostSkull` | Bays share on a thick plank. Fine. |
| **Cloth Rack** (1) | Candle wick | It is thread. | `CandleWick` | One more bay on a 32-slot half-width rack with 4 kinds: fits. |
| **Meat Rack** (1) | Rotten meat | Meat, however far gone. Check it is not already taken (type). | `RottenMeat` | Hooks and bins: fine. |
| **Ore Bin** (1) | Ironpit (unknown) | Name says iron; look it up in game first. | `Ironpit` | - |
| **Ore Bin / Metal racks** (2) | Gold, Gold ore | The parked Strongbox list names `Gold,GoldOre`; the stores' lists do not. They are taken only if the gold smelter burns coal (the bar rule keys on coal-fired smelters). | Check in game; if refused: `Gold` on the five metal pieces, `GoldOre` on the Ore Bin | Each metal has a bay or slot; gold needs one. |

---

## 2. New stores (5, plus one optional)

All in the family style (STYLE.md: chunky timber, iron bands, real item models inside, full must look full). Sizes follow SPEC: more than a
black metal chest (32), 64 as the default and bigger where the kinds are many; "size by volume" stays an open question for Joost.

| # | Store | Holds (kinds) | Look and size | Slots | Why it passes the rubric |
|---|---|---|---|---|---|
| 1 | **Trophy Hall** | Every trophy: 71 kinds today (boss, creature and Hildir trophies), by type so new ones land too (rule: `ItemType.Trophy`). | Wall piece, 4 m wide x 2.4 m, dark timber with iron-banded plaques; each trophy mounted on its own board (display style, one model per stack). A 2 m half (40 slots) as a separate piece. | 80 (half: 40) | "Where do the trophies go" needs no explaining, and 71 kinds is a real hoard once you reach Ashlands. |
| 2 | **Pantry Dresser** | Barley flour, Oat flour, Bread dough, Fragrant bundle, 7 Spices, 9 Feast ingredients, and the 12 uncooked dishes waiting for the oven. 32 kinds. | Tall timber dresser (2 m): sacks and crocks below, spice jars above, baking trays for the dough and uncooked dishes. | 80 | The Larder holds the finished meal; this is "what you cook with". Obvious from the name. |
| 3 | **Smith's Drawers** | Bronze nails, Iron nails, Chain, Barrel rings, Mechanical spring, Axe heads (2), Scythe handle, Ceramic plate, Charred cogwheel, Sharpening stone, Bell fragment. 12 kinds. | Chest of drawers 1.2 m wide x 1.6 m tall, iron pulls, nails in small iron tins. Stands by the forge. | 64 | Nails are the one pile every base has and no store takes: the hardware drawer. |
| 4 | **Jeweller's Casket** | Gemstones (blue, green, red), Ancient gemstones (4), Ancient coin, Silver necklace, Crown jewel, Pot shards (2). 12 kinds. | Small iron-bound casket, 1 m, lined trays with the real gems. | 64 | The Treasure Hoard only has trays for coins, amber, rubies and pearls (and a released piece stays), so the new kinds get a second piece beside it. |
| 5 | **Ember Cabinet** | Wisp, Glow worm, Fader's ember, Memorial coal, Molten core, Black core, Frost core, Shield core, Orb (frost and fire), Orb (thunder and blood). 10 kinds. | Iron-framed, glass-fronted lantern cabinet, 1 m wide x 2 m tall; each kind in its own niche, the items glow. | 64 | "Embers and glowing cores": a clear theme, and nothing else holds them. Surtling core could live here too (section 3). |
| 6 (opt.) | **Tackle Locker** | The 9 fishing baits and the fishing hook (10 kinds); fish stay on the Meat Rack. | Fishing-shed locker with bait tins, 1 m. | 64 | Only if the Apothecary Rack should not take the bait. |

Fallback if five new pieces is too many: merge #4 and #5 into one **Curio Cabinet** (22 kinds, glass front). Weapons and armour need their
own racks (SPEC already lists a weapon rack as still being worked on); that is not part of this list.

---

## 3. Current home looks wrong, doubled or accidental

| Item | Situation | Suggestion |
|---|---|---|
| **Blood clot** (`GiantBloodSack`) | In **two** stores: the Meat Rack (`Bloodclot` resolves by token to the same item) and the Apothecary Rack (`GiantBloodSack`). The log shows both resolving to `$item_bloodclot`. | Keep it in the Meat Rack only (a food ingredient: stuffed mushroom) and drop it from the Apothecary default. Your call. |
| **Royal Jelly** | Moved to Cooper's Row in the code, but the **server's** Apothecary Accepts still lists `RoyalJelly`, so both take it today. | Remove it from the server cfg's Apothecary line. |
| **Honey** | Probably lands in the Produce Crates now (a food nobody makes passes the produce rule) while Royal Jelly is in Cooper's Row. | Move to Cooper's Row (section 1) and verify where it goes today. |
| **Cooked meat and fish** | Taken by both the Meat Rack (roasted: on purpose) and the Larder Hutch (the "made food" rule: by accident). | Fine as is, but the Larder fills with cooked meat. Optionally exclude cooking-station outputs from the Larder rule. |
| **Uncooked dishes, moulds, glow items, bait** | The Mead Rack rule is "a Consumable with no food stats". Anything in the consumables folder without food values could match: uncooked dishes, Glow worm, Larva, the cores, `Mold*`. | Check with Store All beside a Mead Rack. If they land there, tighten the rule (require a mead or potion effect). |
| **Surtling core** | Apothecary Rack (a creature drop), but also a glowing core. | Leave it; accept it in both if the Ember Cabinet is built. |
| **`Dynamite`** in Fletcher's list | Not in this game version (the log says "not in this game, skipped"). | Harmless; drop it at the next edit. |
| **Old `Shelf` and `Root Bin` sections** | The server cfg still has `[4 - Root Bin]` and `Accepts = BarleyWine` under the Shelf sections; the code ignores both. | Harmless leftovers. |

---

## 4. Server config check

The server's `com.joostliebregts.storehouse.cfg` equals the code defaults except: the Apothecary Rack line still has `RoyalJelly` (code: removed),
and the leftover Root Bin and Shelf Accepts above. Every Accepts line in section 1 would have to be edited there by hand, or moved into code.

## 5. Not a Storehouse job (listed so the gap is visible)

Worn and carried gear: 15 trinkets, belt, wisplight, ice shoes and skates, wishbone, saddles, the feaster, fishing rod, hammer, hoe, scythe,
shovel, cultivator. A **gear rack** (weapons, armour, tools, trinkets on pegs) is a separate future piece; the Shelf takes any of it in the
meantime. The 16 `Upgrader*` items are internal upgrade steps and are never held.

---

## 6. The full list: everything no store takes (327 rows)

"Type" is the asset folder, not necessarily the game's item type. Proposal is a store name, `NEW: ...` for the new stores in section 2, or
`Shelf (existing)` for one-offs the Shelf already takes. Sorted by proposal.

| Prefab | In-game name | Type | Biome | Proposal |
|---|---|---|---|---|
| `CuredSquirrelHamstring` | Cured squirrel hamstring | Material | Mistlands | Apothecary Rack |
| `DvergrNeedle` | Dvergr needle | Material | Mistlands | Apothecary Rack |
| `FishingBait` | Fishing bait | Material | Crafted | Apothecary Rack |
| `FishingBaitAshlands` | Fishing bait (Ashlands) | Material | Crafted | Apothecary Rack |
| `FishingBaitCave` | Fishing bait (cave) | Material | Crafted | Apothecary Rack |
| `FishingBaitDeepNorth` | Fishing bait (Deep North) | Material | Crafted | Apothecary Rack |
| `FishingBaitForest` | Fishing bait (forest) | Material | Crafted | Apothecary Rack |
| `FishingBaitMistlands` | Fishing bait (Mistlands) | Material | Crafted | Apothecary Rack |
| `FishingBaitOcean` | Fishing bait (ocean) | Material | Crafted | Apothecary Rack |
| `FishingBaitPlains` | Fishing bait (plains) | Material | Crafted | Apothecary Rack |
| `FishingBaitSwamp` | Fishing bait (swamp) | Material | Crafted | Apothecary Rack |
| `Hook` | Fishing hook | Material | Crafted | Apothecary Rack |
| `Larva` | Larva | Material / consumable | Mistlands? | Apothecary Rack |
| `MoleClaws` | Mole claws | Material | Deep North? | Apothecary Rack |
| `PowderedDragonEgg` | Powdered dragon egg | Material | Mountain | Apothecary Rack |
| `ProustitePowder` | Proustite powder | Material | Mistlands? | Apothecary Rack |
| `QueenBee` | Queen bee | Material | Meadows? (beehive) | Apothecary Rack |
| `Softtissue` | Soft tissue | Material / consumable | Mistlands | Apothecary Rack |
| `CandleWick` | Candle wick | Material | Swamp? | Cloth Rack |
| `BFP_Clay` | Clay | Material (mod) | Mod (ClayBuildPieces) | Coal & Stone Bunker |
| `FrozenFuel` | Frozen fuel | Material | Deep North | Coal & Stone Bunker |
| `Ice` | Ice | Material | Deep North | Coal & Stone Bunker |
| `PungentPebbles` | Pungent pebbles | Material | Ashlands? | Coal & Stone Bunker |
| `StoneRock` | Stone rock | Material | Meadows? | Coal & Stone Bunker |
| `SulfurStone` | Sulfur stone | Material | Swamp | Coal & Stone Bunker |
| `Thunderstone` | Thunderstone | Material | Mountain? | Coal & Stone Bunker |
| `BlobVial` | Blob vial | Misc | Swamp? | Cooper's Row |
| `CharcoalResin` | Charcoal resin | Material | Ashlands? | Cooper's Row |
| `HatefulBlood` | Hateful blood | Material | Ashlands? | Cooper's Row |
| `Honey` | Honey | Material | Meadows | Cooper's Row |
| `OozeMork` | Ooze (Mork) | Material | Ashlands? | Cooper's Row |
| `Voidplasm` | Void plasm | Material | Deep North? | Cooper's Row |
| `FireworksRocket_Blue` | Fireworks rocket (blue) | Material (fireworks) | Crafted | Fletcher's Barrels |
| `FireworksRocket_Cyan` | Fireworks rocket (cyan) | Material (fireworks) | Crafted | Fletcher's Barrels |
| `FireworksRocket_Green` | Fireworks rocket (green) | Material (fireworks) | Crafted | Fletcher's Barrels |
| `FireworksRocket_Purple` | Fireworks rocket (purple) | Material (fireworks) | Crafted | Fletcher's Barrels |
| `FireworksRocket_Red` | Fireworks rocket (red) | Material (fireworks) | Crafted | Fletcher's Barrels |
| `FireworksRocket_White` | Fireworks rocket (white) | Material (fireworks) | Crafted | Fletcher's Barrels |
| `FireworksRocket_Yellow` | Fireworks rocket (yellow) | Material (fireworks) | Crafted | Fletcher's Barrels |
| `BeltStrength` | Belt strength | Utility (worn) | Mountain | Gear racks (future) |
| `Cultivator` | Cultivator | Tool | Crafted | Gear racks (future) |
| `Demister` | Demister | Utility (worn) | Mistlands | Gear racks (future) |
| `Feaster` | Feaster | Tool | Crafted (1.0 feasts) | Gear racks (future) |
| `FishingRod` | Fishing rod | Tool | Crafted | Gear racks (future) |
| `Hammer` | Hammer | Tool | Crafted | Gear racks (future) |
| `Hoe` | Hoe | Tool | Crafted | Gear racks (future) |
| `IceShoes` | Ice shoes | Utility (worn) | Mountain | Gear racks (future) |
| `IceSkates` | Ice skates | Utility (worn) | Deep North? | Gear racks (future) |
| `SaddleAsksvin` | Saddle asksvin | Tool | Crafted | Gear racks (future) |
| `SaddleLox` | Saddle lox | Tool | Crafted | Gear racks (future) |
| `SaddleMoose` | Saddle moose | Tool | Crafted | Gear racks (future) |
| `Scythe` | Scythe | Tool | Crafted | Gear racks (future) |
| `Shovel` | Shovel | Tool | Crafted | Gear racks (future) |
| `TrinketBlackDamageHealth` | Trinket: black damage health | Trinket | Crafted (forge) | Gear racks (future) |
| `TrinketBlackStamina` | Trinket: black stamina | Trinket | Crafted (forge) | Gear racks (future) |
| `TrinketBloodGoldHealth` | Trinket: blood gold health | Trinket | Crafted (forge) | Gear racks (future) |
| `TrinketBloodGoldStamina` | Trinket: blood gold stamina | Trinket | Crafted (forge) | Gear racks (future) |
| `TrinketBronzeHealth` | Trinket: bronze health | Trinket | Crafted (forge) | Gear racks (future) |
| `TrinketBronzeStamina` | Trinket: bronze stamina | Trinket | Crafted (forge) | Gear racks (future) |
| `TrinketCarapaceEitr` | Trinket: carapace eitr | Trinket | Crafted (forge) | Gear racks (future) |
| `TrinketChitinSwim` | Trinket: chitin swim | Trinket | Crafted (forge) | Gear racks (future) |
| `TrinketFlametalEitr` | Trinket: flametal eitr | Trinket | Crafted (forge) | Gear racks (future) |
| `TrinketFlametalStaminaHealth` | Trinket: flametal stamina health | Trinket | Crafted (forge) | Gear racks (future) |
| `TrinketIronHealth` | Trinket: iron health | Trinket | Crafted (forge) | Gear racks (future) |
| `TrinketIronStamina` | Trinket: iron stamina | Trinket | Crafted (forge) | Gear racks (future) |
| `TrinketScaleStaminaDamage` | Trinket: scale stamina damage | Trinket | Crafted (forge) | Gear racks (future) |
| `TrinketSilverDamage` | Trinket: silver damage | Trinket | Crafted (forge) | Gear racks (future) |
| `TrinketSilverResist` | Trinket: silver resist | Trinket | Crafted (forge) | Gear racks (future) |
| `Wishbone` | Wishbone | Utility (worn) | Swamp | Gear racks (future) |
| `RottenMeat` | Rotten meat | Material / consumable | Swamp | Meat Rack |
| `BlackCore` | Black core | Material / consumable | Black Forest / Mistlands | NEW: Ember Cabinet |
| `FaderEmber` | Fader's ember | Material | Ashlands | NEW: Ember Cabinet |
| `FrostCore` | Frost core | Material / consumable | Deep North | NEW: Ember Cabinet |
| `GlowWorm` | Glow worm | Material / consumable | Mistlands? | NEW: Ember Cabinet |
| `MemorialCoal` | Memorial coal | Material | Ashlands? | NEW: Ember Cabinet |
| `MoltenCore` | Molten core | Material / consumable | Ashlands | NEW: Ember Cabinet |
| `OrbFrostFire` | Orb (frost and fire) | Material | Deep North? | NEW: Ember Cabinet |
| `OrbThunderBlood` | Orb (thunder and blood) | Material | Deep North? | NEW: Ember Cabinet |
| `ShieldCore` | Shield core | Material / consumable | Mistlands? | NEW: Ember Cabinet |
| `Wisp` | Wisp | Material | Mistlands | NEW: Ember Cabinet |
| `AncientCoin` | Ancient coin | Valuable | Mistlands? | NEW: Treasure Hoard (coins and gold, Joost 27 Oct) |
| `AncientGemstoneBlack` | Ancient gemstone black | Valuable | Mistlands? | NEW: Jeweller's Casket |
| `AncientGemstoneGreen` | Ancient gemstone green | Valuable | Mistlands? | NEW: Jeweller's Casket |
| `AncientGemstoneOrange` | Ancient gemstone orange | Valuable | Mistlands? | NEW: Jeweller's Casket |
| `AncientGemstonePurple` | Ancient gemstone purple | Valuable | Mistlands? | NEW: Jeweller's Casket |
| `CrownJewel` | Crown jewel | Material | Ashlands? | NEW: Jeweller's Casket |
| `GemstoneBlue` | Gemstone blue | Material | Mistlands? | NEW: Jeweller's Casket |
| `GemstoneGreen` | Gemstone green | Material | Mistlands? | NEW: Jeweller's Casket |
| `GemstoneRed` | Gemstone red | Material | Mistlands? | NEW: Jeweller's Casket |
| `Pot_Shard_Green` | Pot shard (green) | Material | Mistlands | NEW: Jeweller's Casket |
| `Pot_Shard_Red` | Pot shard (red) | Material | Mistlands | NEW: Jeweller's Casket |
| `SilverNecklace` | Silver necklace | Valuable | Mountain | NEW: Jeweller's Casket |
| `BakedPoteitrUncooked` | Baked poteitr (uncooked) | Crafting intermediate | Crafted (foundry or oven) | NEW: Pantry Dresser |
| `BarleyFlour` | Barley flour | Material | Crafted | NEW: Pantry Dresser |
| `BreadDough` | Bread dough | Material | Crafted | NEW: Pantry Dresser |
| `FeastAshlands_Material` | Feast ingredient (ashlands) | Material | Crafted (1.0 feasts) | NEW: Pantry Dresser |
| `FeastBlackforest_Material` | Feast ingredient (blackforest) | Material | Crafted (1.0 feasts) | NEW: Pantry Dresser |
| `FeastDeepNorth_Material` | Feast ingredient (deep north) | Material | Crafted (1.0 feasts) | NEW: Pantry Dresser |
| `FeastMeadows_Material` | Feast ingredient (meadows) | Material | Crafted (1.0 feasts) | NEW: Pantry Dresser |
| `FeastMistlands_Material` | Feast ingredient (mistlands) | Material | Crafted (1.0 feasts) | NEW: Pantry Dresser |
| `FeastMountains_Material` | Feast ingredient (mountains) | Material | Crafted (1.0 feasts) | NEW: Pantry Dresser |
| `FeastOceans_Material` | Feast ingredient (oceans) | Material | Crafted (1.0 feasts) | NEW: Pantry Dresser |
| `FeastPlains_Material` | Feast ingredient (plains) | Material | Crafted (1.0 feasts) | NEW: Pantry Dresser |
| `FeastSwamps_Material` | Feast ingredient (swamps) | Material | Crafted (1.0 feasts) | NEW: Pantry Dresser |
| `FishAndBreadUncooked` | Fish and bread (uncooked) | Crafting intermediate | Crafted (foundry or oven) | NEW: Pantry Dresser |
| `FragrantBundle` | Fragrant bundle | Material | Deep North? | NEW: Pantry Dresser |
| `HoneyGlazedChickenUncooked` | Honey glazed chicken (uncooked) | Crafting intermediate | Crafted (foundry or oven) | NEW: Pantry Dresser |
| `KaleChipsUncooked` | Kale chips (uncooked) | Crafting intermediate | Crafted (foundry or oven) | NEW: Pantry Dresser |
| `LoxPieUncooked` | Lox pie (uncooked) | Crafting intermediate | Crafted (foundry or oven) | NEW: Pantry Dresser |
| `MagicallyStuffedShroomUncooked` | Magically stuffed shroom (uncooked) | Crafting intermediate | Crafted (foundry or oven) | NEW: Pantry Dresser |
| `MeatPlatterUncooked` | Meat platter (uncooked) | Crafting intermediate | Crafted (foundry or oven) | NEW: Pantry Dresser |
| `MisthareSupremeUncooked` | Misthare supreme (uncooked) | Crafting intermediate | Crafted (foundry or oven) | NEW: Pantry Dresser |
| `OatFlour` | Oat flour | Material | Crafted | NEW: Pantry Dresser |
| `OvenPancakeUncooked` | Oven pancake (uncooked) | Crafting intermediate | Crafted (foundry or oven) | NEW: Pantry Dresser |
| `PiquantPieUncooked` | Piquant pie (uncooked) | Crafting intermediate | Crafted (foundry or oven) | NEW: Pantry Dresser |
| `RoastedCrustPieUncooked` | Roasted crust pie (uncooked) | Crafting intermediate | Crafted (foundry or oven) | NEW: Pantry Dresser |
| `SpiceAshlands` | Spice (Ashlands) | Material | Crafted (1.0 feasts) | NEW: Pantry Dresser |
| `SpiceDeepNorth` | Spice (Deep North) | Material | Crafted (1.0 feasts) | NEW: Pantry Dresser |
| `SpiceForests` | Spice (Forests) | Material | Crafted (1.0 feasts) | NEW: Pantry Dresser |
| `SpiceMistlands` | Spice (Mistlands) | Material | Crafted (1.0 feasts) | NEW: Pantry Dresser |
| `SpiceMountains` | Spice (Mountains) | Material | Crafted (1.0 feasts) | NEW: Pantry Dresser |
| `SpiceOceans` | Spice (Oceans) | Material | Crafted (1.0 feasts) | NEW: Pantry Dresser |
| `SpicePlains` | Spice (Plains) | Material | Crafted (1.0 feasts) | NEW: Pantry Dresser |
| `VikingCupcakeUncooked` | Viking cupcake (uncooked) | Crafting intermediate | Crafted (foundry or oven) | NEW: Pantry Dresser |
| `AxeHead1` | Axe head (1) | Material | Black Forest? | NEW: Smith's Drawers |
| `AxeHead2` | Axe head (2) | Material | Black Forest? | NEW: Smith's Drawers |
| `BarrelRings` | Barrel rings | Material | Meadows? | NEW: Smith's Drawers |
| `BellFragment` | Bell fragment | Misc | Plains | NEW: Smith's Drawers |
| `BronzeNails` | Bronze nails | Material | Crafted | NEW: Smith's Drawers |
| `CeramicPlate` | Ceramic plate | Material | Mistlands? | NEW: Smith's Drawers |
| `Chain` | Chain | Material | Swamp | NEW: Smith's Drawers |
| `CharredCogwheel` | Charred cogwheel | Material | Ashlands | NEW: Smith's Drawers |
| `IronNails` | Iron nails | Material | Crafted | NEW: Smith's Drawers |
| `MechanicalSpring` | Mechanical spring | Material | Mistlands | NEW: Smith's Drawers |
| `ScytheHandle` | Scythe handle | Material | Meadows? | NEW: Smith's Drawers |
| `SharpeningStone` | Sharpening stone | Material | Mountain? | NEW: Smith's Drawers |
| `TrophyAbomination` | Trophy: Abomination | Trophy | Swamp | NEW: Trophy Hall |
| `TrophyAsksvin` | Trophy: Asksvin | Trophy | Ashlands | NEW: Trophy Hall |
| `TrophyBarka` | Trophy: Barka | Trophy | Deep North? | NEW: Trophy Hall |
| `TrophyBjorn` | Trophy: Bjorn | Trophy | Black Forest? | NEW: Trophy Hall |
| `TrophyBjornUndead` | Trophy: Bjorn Undead | Trophy | Ashlands? | NEW: Trophy Hall |
| `TrophyBlob` | Trophy: Blob | Trophy | Swamp | NEW: Trophy Hall |
| `TrophyBlob_Frost` | Trophy: Blob Frost | Trophy | Deep North? | NEW: Trophy Hall |
| `TrophyBlob_Lava` | Trophy: Blob Lava | Trophy | Ashlands | NEW: Trophy Hall |
| `TrophyBlob_Morkhalla` | Trophy: Blob Morkhalla | Trophy | Ashlands? | NEW: Trophy Hall |
| `TrophyBoar` | Trophy: Boar | Trophy | Meadows | NEW: Trophy Hall |
| `TrophyBonemass` | Trophy: Bonemass | Trophy | Swamp (boss) | NEW: Trophy Hall |
| `TrophyBonemawSerpent` | Trophy: Bonemaw Serpent | Trophy | Ashlands | NEW: Trophy Hall |
| `TrophyCharredArcher` | Trophy: Charred Archer | Trophy | Ashlands | NEW: Trophy Hall |
| `TrophyCharredMage` | Trophy: Charred Mage | Trophy | Ashlands | NEW: Trophy Hall |
| `TrophyCharredMelee` | Trophy: Charred Melee | Trophy | Ashlands | NEW: Trophy Hall |
| `TrophyCultist` | Trophy: Cultist | Trophy | Mountain | NEW: Trophy Hall |
| `TrophyCultist_Hildir` | Trophy: Cultist Hildir | Trophy | Mountain (Hildir) | NEW: Trophy Hall |
| `TrophyDeathsquito` | Trophy: Deathsquito | Trophy | Plains | NEW: Trophy Hall |
| `TrophyDeer` | Trophy: Deer | Trophy | Meadows | NEW: Trophy Hall |
| `TrophyDeerWhite` | Trophy: Deer White | Trophy | Meadows? | NEW: Trophy Hall |
| `TrophyDragonQueen` | Trophy: Dragon Queen | Trophy | Mountain (boss) | NEW: Trophy Hall |
| `TrophyDraugr` | Trophy: Draugr | Trophy | Swamp | NEW: Trophy Hall |
| `TrophyDraugrElite` | Trophy: Draugr Elite | Trophy | Swamp | NEW: Trophy Hall |
| `TrophyDraugrFem` | Trophy: Draugr Fem | Trophy | Swamp | NEW: Trophy Hall |
| `TrophyDvergr` | Trophy: Dvergr | Trophy | Mistlands | NEW: Trophy Hall |
| `TrophyEikthyr` | Trophy: Eikthyr | Trophy | Meadows (boss) | NEW: Trophy Hall |
| `TrophyElaking` | Trophy: Elaking | Trophy | Deep North? | NEW: Trophy Hall |
| `TrophyFader` | Trophy: Fader | Trophy | Ashlands (boss) | NEW: Trophy Hall |
| `TrophyFallenValkyrie` | Trophy: Fallen Valkyrie | Trophy | Ashlands | NEW: Trophy Hall |
| `TrophyFenring` | Trophy: Fenring | Trophy | Mountain | NEW: Trophy Hall |
| `TrophyForestTroll` | Trophy: Forest Troll | Trophy | Black Forest | NEW: Trophy Hall |
| `TrophyFrostTroll` | Trophy: Frost Troll | Trophy | Mountain? | NEW: Trophy Hall |
| `TrophyGhost` | Trophy: Ghost | Trophy | Black Forest crypts | NEW: Trophy Hall |
| `TrophyGjall` | Trophy: Gjall | Trophy | Mistlands | NEW: Trophy Hall |
| `TrophyGoblin` | Trophy: Goblin | Trophy | Plains | NEW: Trophy Hall |
| `TrophyGoblinBrute` | Trophy: Goblin Brute | Trophy | Plains | NEW: Trophy Hall |
| `TrophyGoblinBruteBrosBrute` | Trophy: Goblin Brute Bros Brute | Trophy | Plains (Hildir) | NEW: Trophy Hall |
| `TrophyGoblinBruteBrosShaman` | Trophy: Goblin Brute Bros Shaman | Trophy | Plains (Hildir) | NEW: Trophy Hall |
| `TrophyGoblinKing` | Trophy: Goblin King | Trophy | Plains (boss) | NEW: Trophy Hall |
| `TrophyGoblinShaman` | Trophy: Goblin Shaman | Trophy | Plains | NEW: Trophy Hall |
| `TrophyGreydwarf` | Trophy: Greydwarf | Trophy | Black Forest | NEW: Trophy Hall |
| `TrophyGreydwarfBrute` | Trophy: Greydwarf Brute | Trophy | Black Forest | NEW: Trophy Hall |
| `TrophyGreydwarfShaman` | Trophy: Greydwarf Shaman | Trophy | Black Forest | NEW: Trophy Hall |
| `TrophyGrowth` | Trophy: Growth | Trophy | Plains | NEW: Trophy Hall |
| `TrophyHare` | Trophy: Hare | Trophy | Mistlands | NEW: Trophy Hall |
| `TrophyHatchling` | Trophy: Hatchling | Trophy | Mountain | NEW: Trophy Hall |
| `TrophyJotunWarrior` | Trophy: Jotun Warrior | Trophy | Deep North? | NEW: Trophy Hall |
| `TrophyJotunWitch` | Trophy: Jotun Witch | Trophy | Deep North? | NEW: Trophy Hall |
| `TrophyLeech` | Trophy: Leech | Trophy | Swamp | NEW: Trophy Hall |
| `TrophyLox` | Trophy: Lox | Trophy | Plains | NEW: Trophy Hall |
| `TrophyMole` | Trophy: Mole | Trophy | Deep North? | NEW: Trophy Hall |
| `TrophyMoose` | Trophy: Moose | Trophy | Deep North? | NEW: Trophy Hall |
| `TrophyMorgen` | Trophy: Morgen | Trophy | Ashlands | NEW: Trophy Hall |
| `TrophyNeck` | Trophy: Neck | Trophy | Meadows | NEW: Trophy Hall |
| `TrophySGolem` | Trophy: SGolem | Trophy | Mountain | NEW: Trophy Hall |
| `TrophySeal` | Trophy: Seal | Trophy | Deep North? | NEW: Trophy Hall |
| `TrophySeeker` | Trophy: Seeker | Trophy | Mistlands | NEW: Trophy Hall |
| `TrophySeekerBrute` | Trophy: Seeker Brute | Trophy | Mistlands | NEW: Trophy Hall |
| `TrophySeekerQueen` | Trophy: Seeker Queen | Trophy | Mistlands (boss) | NEW: Trophy Hall |
| `TrophySerpent` | Trophy: Serpent | Trophy | Ocean | NEW: Trophy Hall |
| `TrophySkeleton` | Trophy: Skeleton | Trophy | Black Forest | NEW: Trophy Hall |
| `TrophySkeletonHildir` | Trophy: Skeleton Hildir | Trophy | Black Forest (Hildir) | NEW: Trophy Hall |
| `TrophySkeletonPoison` | Trophy: Skeleton Poison | Trophy | Swamp? | NEW: Trophy Hall |
| `TrophySurtling` | Trophy: Surtling | Trophy | Swamp | NEW: Trophy Hall |
| `TrophyTheElder` | Trophy: The Elder | Trophy | Black Forest (boss) | NEW: Trophy Hall |
| `TrophyTick` | Trophy: Tick | Trophy | Mistlands | NEW: Trophy Hall |
| `TrophyUlv` | Trophy: Ulv | Trophy | Mountain | NEW: Trophy Hall |
| `TrophyVolture` | Trophy: Volture | Trophy | Ashlands | NEW: Trophy Hall |
| `TrophyWolf` | Trophy: Wolf | Trophy | Mountain | NEW: Trophy Hall |
| `TrophyWraith` | Trophy: Wraith | Trophy | Swamp | NEW: Trophy Hall |
| `TrophyWrithan` | Trophy: Writhan | Trophy | Deep North? | NEW: Trophy Hall |
| `Ironpit` | Ironpit | Material | ? | Ore Bin |
| `Gold` | Gold | Material | Deep North / Mistlands | Ore Bin / Metal racks (check) |
| `GoldOre` | Gold ore | Material | Deep North / Mistlands | Ore Bin / Metal racks (check) |
| `AsksvinCarrionNeck` | Asksvin carrion neck | Material | Ashlands | Ossuary Bin |
| `AsksvinCarrionPelvic` | Asksvin carrion pelvic | Material | Ashlands | Ossuary Bin |
| `AsksvinCarrionRibcage` | Asksvin carrion ribcage | Material | Ashlands | Ossuary Bin |
| `GhostSkull` | Ghost skull | Misc | Black Forest crypts | Ossuary Bin |
| `LargeBone` | Large bone | Misc | Ashlands? | Ossuary Bin |
| `LargeBone_half01` | Large bone half01 | Misc | ? | Ossuary Bin |
| `LargeBone_half02` | Large bone half02 | Misc | ? | Ossuary Bin |
| `UndeadBjornRibcage` | Undead bjorn ribcage | Material | Ashlands? | Ossuary Bin |
| `Acorn` | Acorn | Material | Meadows | Produce Crates |
| `AncientSeed` | Ancient seed | Material | Swamp? | Produce Crates |
| `FirCone` | Fir cone | Material | Black Forest | Produce Crates |
| `FirConeFrost` | Fir cone frost | Material | Deep North? | Produce Crates |
| `FreshSeaweed` | Fresh seaweed | Material | Ocean | Produce Crates |
| `PineCone` | Pine cone | Material | Black Forest | Produce Crates |
| `ArmorGoldHeavyChestUncooked` | Armor gold heavy chest (uncooked) | Crafting intermediate | Crafted (foundry or oven) | Shelf (existing) |
| `ArmorGoldHeavyHelmetUncooked` | Armor gold heavy helmet (uncooked) | Crafting intermediate | Crafted (foundry or oven) | Shelf (existing) |
| `ArmorGoldHeavyLegsUncooked` | Armor gold heavy legs (uncooked) | Crafting intermediate | Crafted (foundry or oven) | Shelf (existing) |
| `ArmorGoldMageChestUncooked` | Armor gold mage chest (uncooked) | Crafting intermediate | Crafted (foundry or oven) | Shelf (existing) |
| `ArmorGoldMageHelmetUncooked` | Armor gold mage helmet (uncooked) | Crafting intermediate | Crafted (foundry or oven) | Shelf (existing) |
| `ArmorGoldMageLegsUncooked` | Armor gold mage legs (uncooked) | Crafting intermediate | Crafted (foundry or oven) | Shelf (existing) |
| `ArmorGoldMediumChestUncooked` | Armor gold medium chest (uncooked) | Crafting intermediate | Crafted (foundry or oven) | Shelf (existing) |
| `ArmorGoldMediumHelmetUncooked` | Armor gold medium helmet (uncooked) | Crafting intermediate | Crafted (foundry or oven) | Shelf (existing) |
| `ArmorGoldMediumLegsUncooked` | Armor gold medium legs (uncooked) | Crafting intermediate | Crafted (foundry or oven) | Shelf (existing) |
| `BarberKit` | Barber kit | Material | Crafted | Shelf (existing) |
| `Bell` | Bell | Misc | Plains | Shelf (existing) |
| `BloodGoldKey` | Bloodgold key | Misc | Deep North / Mistlands | Shelf (existing) |
| `BlueprintRune` | Blueprint rune (PlanBuild) | Tool (mod) | Mod (PlanBuild) | Shelf (existing) |
| `CryptKey` | Crypt key | Misc | Black Forest | Shelf (existing) |
| `DragonEgg` | Dragon egg | Misc | Mountain | Shelf (existing) |
| `DvergrKey` | Dvergr key | Misc | Mistlands | Shelf (existing) |
| `DvergrKeyFragment` | Dvergr key fragment | Misc | Mistlands | Shelf (existing) |
| `DyrnwynBladeFragment` | Dyrnwyn blade fragment | Misc | Ashlands | Shelf (existing) |
| `DyrnwynHiltFragment` | Dyrnwyn hilt fragment | Misc | Ashlands | Shelf (existing) |
| `DyrnwynTipFragment` | Dyrnwyn tip fragment | Misc | Ashlands | Shelf (existing) |
| `FaderDrop` | Fader's drop | Misc | Ashlands (boss) | Shelf (existing) |
| `FrozenKingDrop` | Frozen King's drop | Misc | Deep North (boss) | Shelf (existing) |
| `GenericMoldUncooked` | Generic mold (uncooked) | Crafting intermediate | Crafted (foundry or oven) | Shelf (existing) |
| `GoblinTotem` | Fuling totem | Misc | Plains | Shelf (existing) |
| `GreydwarfSurprise` | Greydwarf surprise | Misc | ? | Shelf (existing) |
| `Greydwarf_Surprise` | Greydwarf surprise | Misc | ? | Shelf (existing) |
| `HealthUpgrade_Bonemass` | Health upgrade (Bonemass) | Upgrade item | Boss reward | Shelf (existing) |
| `HealthUpgrade_GDKing` | Health upgrade (Elder) | Upgrade item | Boss reward | Shelf (existing) |
| `HildirKey_forestcrypt` | Hildir's key (forest crypt) | Misc | Hildir | Shelf (existing) |
| `HildirKey_mountaincave` | Hildir's key (mountain cave) | Misc | Hildir | Shelf (existing) |
| `HildirKey_plainsfortress` | Hildir's key (plains fortress) | Misc | Hildir | Shelf (existing) |
| `KeysGoldUncooked` | Keys gold (uncooked) | Crafting intermediate | Crafted (foundry or oven) | Shelf (existing) |
| `MoldArmorGoldChest` | Mould: armor gold chest | Crafting intermediate | Crafted (foundry or oven) | Shelf (existing) |
| `MoldArmorGoldHelmet` | Mould: armor gold helmet | Crafting intermediate | Crafted (foundry or oven) | Shelf (existing) |
| `MoldArmorGoldLegs` | Mould: armor gold legs | Crafting intermediate | Crafted (foundry or oven) | Shelf (existing) |
| `MoldArmorMageChest` | Mould: armor mage chest | Crafting intermediate | Crafted (foundry or oven) | Shelf (existing) |
| `MoldArmorMageHelmet` | Mould: armor mage helmet | Crafting intermediate | Crafted (foundry or oven) | Shelf (existing) |
| `MoldArmorMageLegs` | Mould: armor mage legs | Crafting intermediate | Crafted (foundry or oven) | Shelf (existing) |
| `MoldArmorMediumHelmet` | Mould: armor medium helmet | Crafting intermediate | Crafted (foundry or oven) | Shelf (existing) |
| `MoldArmorMediumLegs` | Mould: armor medium legs | Crafting intermediate | Crafted (foundry or oven) | Shelf (existing) |
| `MoldArmormediumChest` | Mould: armormedium chest | Crafting intermediate | Crafted (foundry or oven) | Shelf (existing) |
| `MoldAtgeir` | Mould: atgeir | Crafting intermediate | Crafted (foundry or oven) | Shelf (existing) |
| `MoldAxe` | Mould: axe | Crafting intermediate | Crafted (foundry or oven) | Shelf (existing) |
| `MoldAxe2H` | Mould: axe2 h | Crafting intermediate | Crafted (foundry or oven) | Shelf (existing) |
| `MoldBow` | Mould: bow | Crafting intermediate | Crafted (foundry or oven) | Shelf (existing) |
| `MoldCrossbow` | Mould: crossbow | Crafting intermediate | Crafted (foundry or oven) | Shelf (existing) |
| `MoldFistweapon` | Mould: fistweapon | Crafting intermediate | Crafted (foundry or oven) | Shelf (existing) |
| `MoldKeys` | Mould: keys | Crafting intermediate | Crafted (foundry or oven) | Shelf (existing) |
| `MoldKnife` | Mould: knife | Crafting intermediate | Crafted (foundry or oven) | Shelf (existing) |
| `MoldMace` | Mould: mace | Crafting intermediate | Crafted (foundry or oven) | Shelf (existing) |
| `MoldMace2H` | Mould: mace2 h | Crafting intermediate | Crafted (foundry or oven) | Shelf (existing) |
| `MoldShieldBuckler` | Mould: shield buckler | Crafting intermediate | Crafted (foundry or oven) | Shelf (existing) |
| `MoldShieldRound` | Mould: shield round | Crafting intermediate | Crafted (foundry or oven) | Shelf (existing) |
| `MoldShieldTower` | Mould: shield tower | Crafting intermediate | Crafted (foundry or oven) | Shelf (existing) |
| `MoldSmallParts` | Mould: small parts | Crafting intermediate | Crafted (foundry or oven) | Shelf (existing) |
| `MoldSpear` | Mould: spear | Crafting intermediate | Crafted (foundry or oven) | Shelf (existing) |
| `MoldStaffOrbofAhri` | Mould: staff orbof ahri | Crafting intermediate | Crafted (foundry or oven) | Shelf (existing) |
| `MoldStafffrostorbs` | Mould: stafffrostorbs | Crafting intermediate | Crafted (foundry or oven) | Shelf (existing) |
| `MoldStaffspiritcaller` | Mould: staffspiritcaller | Crafting intermediate | Crafted (foundry or oven) | Shelf (existing) |
| `MoldStaffthunderblood` | Mould: staffthunderblood | Crafting intermediate | Crafted (foundry or oven) | Shelf (existing) |
| `MoldSword` | Mould: sword | Crafting intermediate | Crafted (foundry or oven) | Shelf (existing) |
| `MoldSword2H` | Mould: sword2 h | Crafting intermediate | Crafted (foundry or oven) | Shelf (existing) |
| `PlanCrystal` | Plan crystal (PlanBuild) | Tool (mod) | Mod (PlanBuild) | Shelf (existing) |
| `QueenDrop` | Seeker Queen's drop | Misc | Mistlands (boss) | Shelf (existing) |
| `ShieldBucklerGoldUncooked` | Shield buckler gold (uncooked) | Crafting intermediate | Crafted (foundry or oven) | Shelf (existing) |
| `ShieldRoundGoldUncooked` | Shield round gold (uncooked) | Crafting intermediate | Crafted (foundry or oven) | Shelf (existing) |
| `ShieldTowerGoldUncooked` | Shield tower gold (uncooked) | Crafting intermediate | Crafted (foundry or oven) | Shelf (existing) |
| `SmallPartsGoldUncooked` | Small parts gold (uncooked) | Crafting intermediate | Crafted (foundry or oven) | Shelf (existing) |
| `SnowRoller` | Snow roller | Misc | Deep North? | Shelf (existing) |
| `StaminaUpgrade_Greydwarf` | Stamina upgrade (Greydwarf) | Upgrade item | Boss reward | Shelf (existing) |
| `StaminaUpgrade_Troll` | Stamina upgrade (Troll) | Upgrade item | Boss reward | Shelf (existing) |
| `StaminaUpgrade_Wraith` | Stamina upgrade (Wraith) | Upgrade item | Boss reward | Shelf (existing) |
| `Tankard` | Tankard | Misc | Crafted | Shelf (existing) |
| `TankardAnniversary` | Anniversary tankard | Misc | Reward | Shelf (existing) |
| `TankardOdin` | Odin's tankard | Misc | Reward | Shelf (existing) |
| `Tankard_dvergr` | Dvergr tankard | Misc | Mistlands | Shelf (existing) |
| `VAGold_dualaxes_cast` | Gold dual axes cast (VA) | Mould/cast (mod) | Mod (ValheimArmory) | Shelf (existing) |
| `VAGold_dualaxes_mold` | Gold dual axes mould (VA) | Mould/cast (mod) | Mod (ValheimArmory) | Shelf (existing) |
| `VAknife_gold_cast` | Gold knife cast (VA) | Mould/cast (mod) | Mod (ValheimArmory) | Shelf (existing) |
| `VAknife_gold_mold` | Gold knife mould (VA) | Mould/cast (mod) | Mod (ValheimArmory) | Shelf (existing) |
| `VegvisirShard_Bonemass` | Vegvisir shard (Bonemass) | Misc | Swamp | Shelf (existing) |
| `YagluthDrop` | Yagluth's drop | Misc | Plains (boss) | Shelf (existing) |
| `BarkaBranch` | Barka branch | Material | Deep North? | Timber Crib |
| `Root` | Root | Material | Black Forest | Timber Crib |
| `StorehouseBoard` | Storehouse board | Material (mod) | Mod (Storehouse) | Timber Crib |
| `WrithanRoots` | Writhan roots | Material | Deep North? | Timber Crib |
| `YmirRemains` | Ymir flesh | Material | Black Forest / Swamp | Timber Crib |
| `Upgrader0Armor` | Upgrade step 0 (armor) | Upgrade item | n/a | skip (not a hoardable item) |
| `Upgrader0Weapon` | Upgrade step 0 (weapon) | Upgrade item | n/a | skip (not a hoardable item) |
| `Upgrader1Armor` | Upgrade step 1 (armor) | Upgrade item | n/a | skip (not a hoardable item) |
| `Upgrader1Weapon` | Upgrade step 1 (weapon) | Upgrade item | n/a | skip (not a hoardable item) |
| `Upgrader2Armor` | Upgrade step 2 (armor) | Upgrade item | n/a | skip (not a hoardable item) |
| `Upgrader2Weapon` | Upgrade step 2 (weapon) | Upgrade item | n/a | skip (not a hoardable item) |
| `Upgrader3Armor` | Upgrade step 3 (armor) | Upgrade item | n/a | skip (not a hoardable item) |
| `Upgrader3Weapon` | Upgrade step 3 (weapon) | Upgrade item | n/a | skip (not a hoardable item) |
| `Upgrader4Armor` | Upgrade step 4 (armor) | Upgrade item | n/a | skip (not a hoardable item) |
| `Upgrader4Weapon` | Upgrade step 4 (weapon) | Upgrade item | n/a | skip (not a hoardable item) |
| `Upgrader5Armor` | Upgrade step 5 (armor) | Upgrade item | n/a | skip (not a hoardable item) |
| `Upgrader5Weapon` | Upgrade step 5 (weapon) | Upgrade item | n/a | skip (not a hoardable item) |
| `Upgrader6Armor` | Upgrade step 6 (armor) | Upgrade item | n/a | skip (not a hoardable item) |
| `Upgrader6Weapon` | Upgrade step 6 (weapon) | Upgrade item | n/a | skip (not a hoardable item) |
| `Upgrader7Armor` | Upgrade step 7 (armor) | Upgrade item | n/a | skip (not a hoardable item) |
| `Upgrader7Weapon` | Upgrade step 7 (weapon) | Upgrade item | n/a | skip (not a hoardable item) |
