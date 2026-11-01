# Building Storehouse

Storehouse is one C# plugin for BepInEx, built against your own copy of Valheim. Nothing from the game or from other mods is in
this repository; the build references them where they are installed on your machine.

## What you need

- Valheim, with BepInEx 5 and Jotunn 2.30 installed in a mod manager profile (Gale, r2modman or Thunderstore Mod Manager).
- The .NET SDK (any version that builds netstandard2.1), Git Bash (on Windows) and Python 3.

## Your paths

The build reads three paths. Set them as environment variables; the defaults are the author's machine.

| Variable | What it points at | Example |
|---|---|---|
| `GameDir` | the Valheim install | `C:/Program Files (x86)/Steam/steamapps/common/Valheim` |
| `ProfileDir` | the mod manager profile that holds `BepInEx/` | `C:/Users/you/AppData/Roaming/r2modmanPlus-local/Valheim/profiles/Default` |
| `STOREHOUSE_BEPINEX` | that profile's `BepInEx` folder (for `build.sh`) | `$ProfileDir/BepInEx` |

## Build

    dotnet build -c Release -p:DefineConstants=DEV%3BRELEASE -o bin/release   # the release DLL only
    ./build.sh dev-plugin                  # dev build into your profile's BepInEx/plugins, with the models

The code needs the `DEV` constant in every build (`RELEASE` on top for the release); plain `dotnet build` does not compile.
`./build.sh` without an argument makes the release zip. It packs only after a real game start ran exactly that DLL
(the live gate in `build.sh`, with `test-swap.sh`).

## Nothing of the game's

Since 0.8.6 neither this repository nor the released zip holds anything taken from the game's files or other mods:

- Items whose mesh the game keeps on the graphics card are measured in the player's own game: the mod reads their vertices back from
  the GPU the first time a store shows them and keeps the result in `BepInEx/cache/Storehouse-item-points.bin`. Until 0.8.5 these
  shapes shipped as `assets/item_points.bin`.
- The Ossuary's display sidecar (the game's bone meshes as `display_meshes/*-native.json`, and `ossuary_display.json`) is a dev-only
  experiment. Release builds never read it, `copy-models.sh` copies it only into dev installs, and it is not in this repository: a
  release build draws the Ossuary's bones with the game's own meshes.

Everything here, the furniture models included, is our own work.

The `blender/` scripts that made the models expect a local extraction of the game's files for reference and scale; they are
included to show how each model was made, not as a one-step rebuild.
