# Storehouse

Storage for Valheim that holds a lot and shows what's inside. There's a store for each kind of stuff: logs in a timber crib, ore in a bin, arrows in barrels, hides on stretching frames, armor on carved mannequins. Each store takes only its own kind of item and fills up with the real items as you put things in. Full looks full.

![Produce Crates filled with vegetables, berries and mushrooms](https://raw.githubusercontent.com/joostliebregts/valheim-storehouse/main/media/produce-crates.webp)

*The Produce Crates in a kitchen corner. Every crate holds one kind of crop, and you see at a glance how much is in it.*

## Why I made this

I wanted storage that actually fits the game, and that shows you what's in it and how full it is. I love giving your brain more ways to understand something than reading text or numbers. My mod [Oof](https://thunderstore.io/c/valheim/p/DJ_Lifecoach/Oof/) does that for the weight you carry; Storehouse does it for everything you store. You look at your base and you see your stock.

I'm a designer. I studied industrial design, worked with CAD, and I like making things. AI unlocks a lot of that for me: Storehouse is the fourth Valheim mod I made in the last two months. Each one got a lot of time and care. It starts with playing the game and noticing what I'd love to have in it, and then I get caught up in the details.

This one started as an experiment. I wanted to see how far today's AI models (Claude Opus 5.5 and Sol 6.1) can go with 3D models for a game, and I was thoroughly impressed. So I went with it, and before I knew it I had a whole storage system: a fitting store for almost everything you can carry. I didn't model any of it by hand. I directed, the AI built. It took three or four days of focused work, and without AI this mod wouldn't exist.

I quite like it, and that's why I'm sharing it. You can build amazing bases with it, organized by theme, with storage that fits what goes in it. I'm curious how you use it and what you think of it.

## What it does

- **You see what's in it.** The items lie in the store as themselves: heaps of coal, bars on a rack, meads on a shelf, a full set of armor on a mannequin. As you add more, the heaps grow and the shelves fill.
- **One kind of stuff per store.** You know at a glance where the hides go, or the bones, or the tar. The store refuses what doesn't belong, and nothing lies mixed.
- **Big, and based on real things.** Most stores hold more than a black metal chest. Most items show at their real size; some are a bit smaller so they fit, and some are there just so you can see them.
- **The armor stands are chests.** No more putting gear on a stand one item at a time with the hotbar keys. Open it, take your set, go.
- **A little work to build, not a grind.** No fine wood, because you always run short of it. Most stores use **Boards**, an item this mod adds, which you make from normal wood. Add nails and the materials that make sense for that piece.

## An experiment, in development

Storehouse is a hobby project, made in collaboration with AI (yes, vibe-coded). It isn't perfect, and that's part of the experiment. The heaps in several stores are settled by a real physics simulation ahead of time, so they cost nothing while you play. Other stores are simpler for now, and some still look a bit rough. I keep working on them.

It isn't balanced the way Valheim is, on purpose: the stores hold a lot and cost less than a black metal chest. It's made for one thing: a base that looks great, with storage that fits.

When I update the mod, I make sure you keep your items. Still, **back up your world (or your server) before you install it, and before every update.**

## Tell me what you think

On the [GitHub page](https://github.com/joostliebregts/valheim-storehouse), open an issue for anything: a store that looks off, an item with no store or in the wrong one, a build cost that feels unfair, an idea for a new store. I'm not a professional developer, so I'm learning how this works along the way.

In the meantime, you can change a lot yourself: the **Accepts** setting decides what goes in a store, and the **Recipe** setting what it costs.

## The stores

Build them with the hammer, on their own **Storage** tab, near a workbench.

**Wood, ore and stone**
- **Timber Crib**: wood, fine wood, core wood, ancient bark, yggdrasil wood, ashwood, frostwood, roots and branches, shown as a growing log pile.
- **Ore Bin**: ore and scrap.
- **Coal & Stone Bunker**: coal, stone, flint, obsidian, black marble and other loose heaps, in three bays. Stacks. The **Open Coal & Stone Bunker** is the same without a load-bearing top.

![The Timber Crib filling up](https://raw.githubusercontent.com/joostliebregts/valheim-storehouse/main/media/timber-crib-fill.webp)

*Time-lapse: a Timber Crib fills up. The more wood you store, the higher the log pile.*

**Metal**
- **Metal Rack** (tall, tall half, low, low half) and **Metal Pallet**: metal bars. All stack; two halves side by side make a whole rack, two lows stacked make a tall one.

![Metal Racks and a Metal Pallet with bars](https://raw.githubusercontent.com/joostliebregts/valheim-storehouse/main/media/metal-racks.webp)

*Metal Racks and a Metal Pallet along a wall, from empty to full: bars stacked per kind of metal.*

**Kitchen**
- **Brewer's Cabinet**: meads and potions. Stacks.
- **Larder Hutch**: cooked meals. Stacks.
- **Meat Rack**: meat and fish, raw or cooked.
- **Produce Crates**: vegetables, mushrooms, berries, herbs, seeds, cones and eggs.
- **Pantry Dresser**: flour, spices and other cooking ingredients.

![The Brewer's Cabinet, meads and potions in its compartments](https://raw.githubusercontent.com/joostliebregts/valheim-storehouse/main/media/mead-rack.webp)

*The Brewer's Cabinet: meads and potions, each kind in its own compartments.*

![The Larder Hutch, full of meals](https://raw.githubusercontent.com/joostliebregts/valheim-storehouse/main/media/larder.webp)

*The Larder Hutch, full: every meal on show, a little under its real size.*

![The Larder Hutch filling up with meals](https://raw.githubusercontent.com/joostliebregts/valheim-storehouse/main/media/larder-fill.webp)

*Time-lapse: the Larder Hutch fills up with meals, shelf by shelf.*

![The Produce Crates filling up, a crate per kind](https://raw.githubusercontent.com/joostliebregts/valheim-storehouse/main/media/produce-crates-fill.webp)

*Time-lapse: the Produce Crates take in one crop after another, each in its own crate.*

**Crafting goods**
- **Cooper's Row**: tar, resin, sap, guck, eitr, ooze and the like, a vessel per kind. The **Stacking Cooper's Row** puts the same vessels under a plank deck that something else can stand on.
- **Apothecary Rack** and **Tall Apothecary Rack**: feathers, eyes, fangs, scales, hearts and other creature parts. Each vessel suits what it holds: hooks, glass jars, clay crocks or baskets.
- **Hide Rack**: hides and leather, stretched on frames and folded below.
- **Cloth Rack**: linen, jute, Norn thread and candle wick.
- **Ossuary Bin**: bones, skulls and antlers, in settled heaps.
- **Smith's Drawers**: nails, chain, rings, springs and the smith's odds and ends.
- **Ember Cabinet**: wisps, cores, embers, orbs, glow worms and the elemental stones.

![The Ossuary Bin](https://raw.githubusercontent.com/joostliebregts/valheim-storehouse/main/media/ossuary.webp)

*The Ossuary Bin: bones, skulls and antlers in heaps, one kind per bay.*

![The Ossuary Bin filling up, the heaps growing in their bays](https://raw.githubusercontent.com/joostliebregts/valheim-storehouse/main/media/ossuary-fill.webp)

*Time-lapse: the Ossuary Bin fills up. The heaps were settled by a physics simulation, so they lie the way bones would.*

![Smith's Drawers filling up](https://raw.githubusercontent.com/joostliebregts/valheim-storehouse/main/media/smiths-drawers-fill.webp)

*Time-lapse: Smith's Drawers fill up, drawer by drawer.*

![Cooper's Row filling up, a vessel per kind](https://raw.githubusercontent.com/joostliebregts/valheim-storehouse/main/media/coopers-row-fill.webp)

*Time-lapse: Cooper's Row fills up, each good in its own vessel.*

**Ammunition**
- **Fletcher's Barrels**: arrows, bolts and bombs.
- **Arrow Tubes**: arrows, a tube per kind.
- **Bolt Crate**: crossbow bolts.
- **Bomb Crate**: bombs, a tray per kind.

![Fletcher's Barrels up close, every kind of arrow in its own barrel](https://raw.githubusercontent.com/joostliebregts/valheim-storehouse/main/media/fletcher-row.webp)

*A slow pass along the Bolt Crate and Fletcher's Barrels: every kind of bolt and arrow in its own place.*

**Weapons.** Your real weapons at their true size (or very close to it), modded ones included.
- **Weapon Rack A** and **Weapon Rack B**: eight one-handed weapons each, two builds of the same idea. Put several side by side.
- **Arsenal**: weapons, bows and shields, the best shield on show.
- **Arsenal Spine**, **Arsenal Shield Trough**, **Arsenal Long Rack** and **Arsenal Bow Rack**: an arsenal you put together yourself. The spine holds one-handed weapons; shield troughs snap to its sides, the long rack and the bow rack to its ends.

![An Arsenal with shields and weapons](https://raw.githubusercontent.com/joostliebregts/valheim-storehouse/main/media/arsenal.webp)

*An Arsenal: one-handed and long weapons in racks, bows, and shields on show at the front.*

**Armor**
- **Armor Stand** and **Armor Stand, open**: a carved wooden mannequin wearing a full set of armor with its cape, weapon and shield. The open one has no back rail and snaps to other stands and the armory rails.
- **Armory Rail**, **Short Armory Rail** and **Armory Island**: rows of the same mannequins, ready to grab.
- **Armory**: armor, weapons and shields together, on two sides, so you can reach it from both aisles.
- **Armor Cabinet** and **Armor Coffer**: helmets in their places, the rest folded on piles.

![Armor Stands](https://raw.githubusercontent.com/joostliebregts/valheim-storehouse/main/media/mannequins.webp)

*Two Armor Stands, each wearing a full set, with a Shelf between them. You open a stand like a chest.*

![The armories from above](https://raw.githubusercontent.com/joostliebregts/valheim-storehouse/main/media/armory-overview.webp)

*The armories from above: Armory Rails and an Armory Island, each mannequin wearing its set.*

**Trophies**
- **Trophy Hall** and **Tall Trophy Hall**: a free-standing wall with a trophy mounted on each board, the bosses' too.

**Valuables**
- **Treasure Hoard**: coins in the well, gold in the trays.
- **Jeweller's Casket**: gems and jewellery, sorted finer.

**Shelves**
- **Shelf** with 1, 2 or 3 planks: a wall shelf for what you grab in a hurry, such as portal materials next to the portal, or your gear for the run back to a boss after you die. It holds anything. Each stack shows as one item on the planks; when the planks are full, the rest stays inside, out of sight.

## Building them

Most stores are built from **Boards**, a new item made at the workbench: 1 wood makes 2 boards, or 5 wood make 10 in one go. Add some nails, iron, wood, stone or leather depending on the store; the hammer shows the exact cost.

Big outdoor stores stand on level ground or a floor. Only stores with a flat, sturdy top take another on top: the Coal & Stone Bunker, the metal racks and pallet, the Brewer's Cabinet, the Larder Hutch and the Stacking Cooper's Row. The Shelf hangs on a wall.

## How they behave

- **Each store takes only its own kind of item.** Anything else stays where it was, with a short message, whether you drag it, ctrl-click it, use Place stacks or a quick-stack mod. Hovering over a store shows what it takes. Items already inside always stay, even if the list changes later.
- **Bays fill one kind at a time.** The bunkers, the Ore Bin and the Jeweller's Casket hold as many kinds as they have bays, and refuse a new kind once every bay is taken. Build another one.
- **What has no place to show stays in the chest.** It's stored, just not drawn, and the hover tells you how many kinds that is.

## Settings

BepInEx config, synced from the server and changeable by admins only. Each store has:
- **Rows**: slots in rows of 8. The chest window scrolls.
- **Recipe** and **Crafting station**.
- **Accepts**: extra item names the filter lets in, so items from other mods can find their store.

Settings that change only how things look on your own screen: **Item size** (makes the items inside a store bigger), **Model** (an older model for a few stores), and a Performance section (how far away contents are drawn, and how detailed).

## Performance

I tested it with a lot of weapons and stores in one base. It costs some performance, but in my game the drop was small. Try it for yourself. If you need more frame rate, these settings help (Performance section):
- **Contents distance**: how far away the items in a store are drawn.
- **Far contents beyond**: from this distance, stores draw the game's lighter item models.
- **Max triangles per stack**: fewer copies of heavy items, such as feast platters and big trophies.

## Works with

- **LumberCamp / MiningCamp**: link a crib or bin with "Add nearest chest". Workers only put in what it takes.
- **MultiUserChest**: works. The filter runs first.
- **AzuCraftyBoxes**: crafting takes from the stores like from any chest.
- **ValheimArmory**: its arrows and bolts go to the ammunition stores, by type.

## Important for servers

This mod adds building pieces, so **the server and every player need it**, on the same minor version. **If Storehouse is ever removed, or fails to load while a world loads, Valheim deletes every placed Storehouse piece and everything inside it.** Decide before adding it to a shared world, and check that the BepInEx log shows Storehouse loaded before anyone joins after an update.

Lowering a store's **Rows** hides the items in the removed rows until the rows come back, so empty them first.

## Known limits

- The Ossuary Bin looks right when full of one kind; with a mix of bones it still looks thin.

## Credits

Made in collaboration with AI: the code was written by Claude (Claude Code), the 3D models by Sol 6.1 and Claude Opus 5.5, in Valheim's own style. No game files are included: the stores use the game's own materials and item models while it runs.

Requires Jotunn. License: MIT. You can do what you want with it, as long as the copyright notice stays in; a link back to this page is appreciated.

## My other mods

Storehouse is one of four Valheim mods I made in the last two months, all in collaboration with AI. The other three:
- **Hearthwoven Stats Book** ([GitHub](https://github.com/joostliebregts/Hearthwoven), [Thunderstore](https://thunderstore.io/c/valheim/p/DJ_Lifecoach/Hearthwoven_Stats_Book/)): all your stats in an in-game book, from cooking and mining to damage per weapon.
- **Portal Compass** ([GitHub](https://github.com/joostliebregts/valheim-portal-compass), [Thunderstore](https://thunderstore.io/c/valheim/p/DJ_Lifecoach/PortalCompass/)): search, pin and pick XPortal destinations, with a map of your portals.
- **Oof** ([Thunderstore](https://thunderstore.io/c/valheim/p/DJ_Lifecoach/Oof/)): feel your inventory's weight at a glance.
