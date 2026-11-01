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

## What a source build leaves out

Two files in the released zip hold shapes measured from the game's own items, so they stay out of this repository:
`assets/item_points.bin` (the true shape of items whose mesh the game keeps on the GPU) and the Ossuary's native bone meshes
(`assets/ossuary_r5b/display_meshes/*-native.json`). Without them the mod measures those items by their bounding box and draws the
Ossuary with the game's own meshes. Everything else, the furniture models included, is our own work and is here.

The `blender/` scripts that made the models expect a local extraction of the game's files for reference and scale; they are
included to show how each model was made, not as a one-step rebuild.
