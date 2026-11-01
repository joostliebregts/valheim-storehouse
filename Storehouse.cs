// Storehouse: three big storage pieces. The Hauler's Strongbox (64 slots), the Timber Crib (64 slots, wood only) and
// the Ore Bin (48 slots, ore, stone and metal only). The big ones stand on level ground or a floor.
// Copyright (c) 2026 Joost Liebregts. MIT License (see LICENSE). Uses Jotunn (MIT, Valheim-Modding) for pieces, config sync and icons.
// Ships no game assets: every vanilla mesh and material is looked up in the running game. The Strongbox .obj meshes are our own.

using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Text;
using BepInEx;
using BepInEx.Configuration;
using HarmonyLib;
using Jotunn.Configs;
using Jotunn.Entities;
using Jotunn.Managers;
using Jotunn.Utils;
using UnityEngine;
using UnityEngine.UI;

namespace Finn.Storehouse;

// How it works:
// - Each piece is a Jotunn clone of a vanilla chest, so it keeps Container, WearNTear, ZNetView, sounds and the container UI.
//   Strongbox: piece_chest_blackmetal, with our own meshes swapped in when assets/strongbox/*.obj ships next to the DLL.
//   Timber Crib and Ore Bin: a wood/reinforced chest with its own look hidden, dressed in copies of vanilla parts
//   (wood stacks, log poles, iron-banded beams, stone walls, iron plates) that are measured and fitted at runtime.
// - Size: Container.Awake is patched to give our containers 8 columns and the configured rows, so a config change reaches
//   every chest that loads after it. The vanilla container grid sits in a scroll view, so 8 rows scroll (4 visible at once).
// - Filter: our containers are recognised by their inventory name (a $token only they use). Inventory.CanAddItem and every
//   Inventory.AddItem path refuse items that are not on the list, except while an inventory is being loaded from the world
//   (so nothing already inside is ever lost). That covers drag and drop, ctrl-click, Place stacks, Quick Stack mods,
//   MultiUserChest (whose own AddItem hooks run after ours) and LumberCamp/MiningCamp deposits (they ask CanAddItem first).
//   InventoryGrid.DropItem is checked as well, because its swap path removes the item before it adds it.
// - Every client and the server run the same patch (EveryoneMustHaveMod), so whoever owns the chest enforces it.
[BepInPlugin(Id, "Storehouse", Version)]
[BepInDependency(Jotunn.Main.ModGuid)]
[BepInProcess("valheim.exe")]
[BepInProcess("valheim_server.exe")]
// The pieces are world objects and the filter runs wherever the chest is owned: server and every client need the same mod.
// A dev build (build.sh dev) lives in Joost's normal profile instead: no version check, so the live server still lets him
// in, and our pieces leave the hammer while he is connected to someone else's server (they only exist in his own worlds).
// The release (build.sh, 0.3.0 on) is the same code as the dev build (DEV) with RELEASE on top: the version check, pieces
// in every world, no skin hotkey, no perf log.
#if DEV && !RELEASE
[NetworkCompatibility(CompatibilityLevel.NotEnforced, VersionStrictness.None)]
#else
[NetworkCompatibility(CompatibilityLevel.EveryoneMustHaveMod, VersionStrictness.Minor)]
#endif
public sealed class Plugin : BaseUnityPlugin
{
    public const string Id = "com.joostliebregts.storehouse";
    public const string Version = "0.8.6";   // ships nothing of the game's: item shapes read from the GPU, the Ossuary sidecar dev-only; unofficial note (1 Nov)
    // 0.8.5: a store's refusal holds against other mods; shift-click no longer doubles a stacked item (31 Oct)
    // 0.8.1: the sorting hotfix (Joost, 28 Oct)
    // 0.8.0: the release (Joost, 27 Oct: "a good number that feels like it's almost finished")

    internal static BepInEx.Logging.ManualLogSource Log;
    internal static string Dir;
    // What failed while this copy started (a guarded step, a piece not registered, a store without its model): in the live line,
    // which build.sh's pack gate reads, and on the main menu of a dev build (the coordinator's retro, 26 Oct).
    internal static readonly List<string> Failures = new();
    // This copy is hooked in. Static callbacks (patches, setting handlers) of a copy that has left (dev live reload) do nothing.
    internal static bool Live { get; private set; }
    // A dedicated server: no graphics device, and its chest prefabs carry no piece material. The models still load there (frame
    // mesh, colliders, snap points, units: what the server's copy of a piece needs), only without material or texture.
    internal static bool Headless => SystemInfo.graphicsDeviceType == UnityEngine.Rendering.GraphicsDeviceType.Null;

#if DEV
    // Live reload (dev, ScriptEngine): every load is a new assembly with its own statics. The live copy is noted in the
    // shared AppDomain, so a new copy hooks in only once the old one has left (ScriptEngine destroys the old copy at the end
    // of the frame and adds the new one a frame later; the wait covers the other order too), and once Jotunn is up
    // (LoadOnStart ignores BepInDependency). Guide: tools/valheim-mods/LIVE-MODDING.md, and Reload below.
    const string LiveSlot = Id + ".live";
    internal static bool FromScripts;   // loaded by ScriptEngine from BepInEx/scripts (its assembly is renamed per load)
    bool started, failed, quitting;
    float nextWaitLog;
    Action onQuit;
    Harmony harmony;
    EventHandler<SettingChangedEventArgs> onConfig;
    EventHandler<ConfigurationSynchronizationEventArgs> onSync;
#endif

    private void Awake()
    {
        Log = Logger;
#if DEV
        FromScripts = typeof(Plugin).Assembly.GetName().Name != "Storehouse";
        // ScriptEngine sets Info.Location only after Awake; build.sh dev puts the models in scripts/Storehouse/assets.
        Dir = FromScripts ? Path.Combine(BepInEx.Paths.BepInExRootPath, "scripts", "Storehouse") : Path.GetDirectoryName(Info.Location);
        onQuit = () => quitting = true;
        Application.quitting += onQuit;
        if (FromScripts) { Log.LogInfo($"Storehouse {Version}: loaded from BepInEx/scripts (live reload); hooking in once Jotunn is up and an older copy has left."); return; }
        Begin();
    }

    // Everything a copy hooks into the game. The plugin copy (no ScriptEngine) runs it from Awake, a scripts copy once it may.
    void Begin()
    {
        started = true;
        Live = true;
        AppDomain.CurrentDomain.SetData(LiveSlot, this);
        if (FromScripts) Guard("version check", ShowToVersionCheck);
#else
        Dir = Path.GetDirectoryName(Info.Location);
        Live = true;
#endif
        // The pieces are registered before anything that can throw (25 Oct: one config key BepInEx refused stopped the start
        // before the registration, and Valheim deleted every placed piece as an unknown prefab). The settings come first only
        // because the pieces read them; every entry binds through Settings.Safe, which falls back to its default instead of
        // throwing. Each step after the registration is guarded on its own: a failure logs an error and switches only that part off.
        Guard("settings", () => Settings.Bind(Config));
#if DEV
        Guard("icon settings", () => Icons.Bind(Config));
        // Vanilla prefabs already there (a live reload in the menu or in a world, or ScriptEngine's start-up load landing
        // after the menu's ObjectDB): build or take over the pieces at the end, once this copy is set up. Otherwise when Jotunn says
        // they are available, whatever happens below.
        if (!ObjectDB.instance) PrefabManager.OnVanillaPrefabsAvailable += AddPieces;
#else
        PrefabManager.OnVanillaPrefabsAvailable += AddPieces;
#endif
        Guard("words", AddLocalization);
#if DEV
        // Per load, so the old copy's UnpatchSelf leaves this copy's patches alone.
        harmony = new Harmony(Id + "." + Guid.NewGuid().ToString("N"));
#else
        var harmony = new Harmony(Id);
#endif
        Guard("patches", () => harmony.PatchAll(typeof(Patches)));
        Guard("load guard", () => harmony.PatchAll(typeof(LoadGuard)));
#if DEV
        Guard("skin patches", () => harmony.PatchAll(typeof(SkinPatches)));
        Guard("armory tidy", () => harmony.PatchAll(typeof(Mannequins)));
        Guard("typed slots", () => harmony.PatchAll(typeof(TypedSlots)));
#if !RELEASE
        Guard("dev fill", DevFill.Register);
#endif
        Guard("skins", () =>
        {
            Skins.Load();
            Settings.SkinChests.SettingChanged += (_, _) => { if (Live) Skins.Refresh(); };
        });
        // The overlay is its own component, so no OnGUI runs at all while it is off.
        void Overlay() { if (!this) return; var o = GetComponent<PerfOverlay>(); if (Settings.PerfOverlay.Value && !o) gameObject.AddComponent<PerfOverlay>(); else if (!Settings.PerfOverlay.Value && o) Destroy(o); }
        Guard("perf overlay", () =>
        {
            Settings.PerfOverlay.SettingChanged += (_, _) => Overlay();
            Overlay();
        });
        onSync = (_, _) => { if (Live) Settings.ApplyToPieces(); };
        onConfig = (_, _) => { if (Live) Settings.ApplyToPieces(); };
        SynchronizationManager.OnConfigurationSynchronized += onSync;
        Config.SettingChanged += onConfig;
        if (ObjectDB.instance) AddPieces();
    }

    // A scripts copy shows itself to Jotunn's version check, so the live dev build can join a server that runs 0.8.x (Joost, 1 Nov:
    // test on the server). Jotunn lists the mods BepInEx loaded (Chainloader.PluginInfos), once, in its own cache; a ScriptEngine
    // copy is in neither, and the server answered "Storehouse 0.8.5 was not loaded on your game". The dev attribute (NotEnforced)
    // asks nothing of a server; the server's rule for its own Storehouse (EveryoneMustHaveMod, Minor) then accepts any 0.8.
    void ShowToVersionCheck()
    {
        var info = Info;
        if (info.Instance != this) AccessTools.Property(typeof(PluginInfo), "Instance").SetValue(info, this);
        BepInEx.Bootstrap.Chainloader.PluginInfos[Id] = info;
        var cache = AccessTools.Field(typeof(BepInExUtils), "Plugins");   // null until Jotunn first asks; then built from the list above
        if (cache.GetValue(null) is BaseUnityPlugin[] cached)
            cache.SetValue(null, cached.Where(p => p && p.Info?.Metadata?.GUID != Id).Append(this).ToArray());   // an old copy is gone (false)
        Log.LogInfo($"Version check: this live copy counts as Storehouse {info.Metadata.Version}; a server with any 0.8 lets it in.");
    }

    // A scripts copy: hook in once Jotunn is up and no older copy is live any more.
    void TryBegin()
    {
        var other = AppDomain.CurrentDomain.GetData(LiveSlot) as UnityEngine.Object;
        bool jotunn = BepInEx.Bootstrap.Chainloader.PluginInfos.TryGetValue(Jotunn.Main.ModGuid, out var j) && j.Instance;
        if ((other && other != this) || !jotunn)
        {
            if (Time.realtimeSinceStartup >= nextWaitLog)
            {
                nextWaitLog = Time.realtimeSinceStartup + 5f;
                Log.LogInfo(!jotunn ? "Waiting for Jotunn." : "Waiting for the previous Storehouse copy to leave.");
            }
            return;
        }
        try { Begin(); }
        catch (Exception e) { failed = true; Live = false; Log.LogError($"Live reload: could not hook in; this copy stays idle until the next build ({e})."); }
    }

    // Leaving (a live reload, or the game closing): undo everything, so the next copy starts from a clean world.
    private void OnDestroy()
    {
        Application.quitting -= onQuit;
        ModelWatch.Stop();   // its events would otherwise fire into a copy that has left
        if (GetComponent<LoadWarning>() is { } warning) Destroy(warning);   // the next copy says its own
        if (!started) return;
        Live = false;
        if (ReferenceEquals(AppDomain.CurrentDomain.GetData(LiveSlot), this)) AppDomain.CurrentDomain.SetData(LiveSlot, null);
        PrefabManager.OnVanillaPrefabsAvailable -= AddPieces;
        PieceManager.OnPiecesRegistered -= HammerOrder;   // a static event: the next copy subscribes its own
#if !RELEASE
        ItemManager.OnItemsRegistered -= EquipFit.Report;   // a static event: the next copy subscribes its own
#endif
        if (onSync != null) SynchronizationManager.OnConfigurationSynchronized -= onSync;
        if (onConfig != null) Config.SettingChanged -= onConfig;
        harmony?.UnpatchSelf();
        if (quitting) return;
        try { Reload.Teardown(); }
        catch (Exception e) { Log.LogError($"Live reload: cleanup failed ({e})."); }
        Log.LogInfo("Storehouse copy unloaded (live reload).");
    }
#else
        SynchronizationManager.OnConfigurationSynchronized += (_, _) => Settings.ApplyToPieces();
        Config.SettingChanged += (_, _) => Settings.ApplyToPieces();
    }
#endif

    // One start-up step: a throw is logged and switches off only that step (never the pieces' registration, which comes before).
    static void Guard(string step, Action run)
    {
        try { run(); }
        catch (Exception e)
        {
            Failures.Add(step);
            Log.LogError($"Storehouse {Version}: start-up step '{step}' failed; the pieces stay registered, this part is off until the next start ({e}).");
        }
    }

    float nextModelCheck;
#if DEV
    float nextConfigCheck;
    DateTime configStamp;
#endif

    private void Update()
    {
#if DEV
        if (!started) { TryBegin(); return; }
        if (failed) return;
        long t0 = System.Diagnostics.Stopwatch.GetTimestamp();
        Perf.Frame();
        try { Tick(); }
        finally { Perf.Add(t0); }
    }

    // After every Update: draw the stores' contents (no GameObjects per item copy), and close the frame's perf sample.
    private void LateUpdate()
    {
        if (!started || failed) return;
        long t0 = System.Diagnostics.Stopwatch.GetTimestamp();
        try { StoreContents.DrawAll(); }
        finally { Perf.Add(t0); Perf.EndFrame(); }
    }

    void Tick()
    {
#if DEV
        // The config manager may still hold the settings of a copy that has left (its window was open across a live reload), so a
        // change there only reaches the file (Joost, 24 Oct: "the item sizes don't change"). Read the file again when it changes.
        if (Time.unscaledTime >= nextConfigCheck)
        {
            nextConfigCheck = Time.unscaledTime + 1f;
            var stamp = File.Exists(Config.ConfigFilePath) ? File.GetLastWriteTimeUtc(Config.ConfigFilePath) : default;
            if (configStamp == default) configStamp = stamp;
            else if (stamp != configStamp) { configStamp = stamp; Config.Reload(); }
        }
#endif
#if !RELEASE
        Skins.CheckHotkey();   // every frame: a key press lasts one frame
#endif
#endif
        if (Time.time < nextModelCheck) return;
        nextModelCheck = Time.time + 1f;
#if DEV && !RELEASE
        // Our own world (we host, or no network yet): pieces in the hammer. Someone else's server: out of the hammer.
        bool own = !ZNet.instance || ZNet.instance.IsServer();
        foreach (var k in Kinds.All)
            if (PrefabManager.Instance.GetPrefab(k.Prefab)?.GetComponent<Piece>() is { } piece && piece.m_enabled != own)
            {
                piece.m_enabled = own;
                Log.LogInfo($"{k.Title}: {(own ? "in" : "out of")} the hammer (dev build, {(own ? "own world" : "someone else's server")}).");
            }
#endif
        if (Settings.LiveModels.Value && ModelWatch.Changed())
        {
#if DEV
            long t1 = System.Diagnostics.Stopwatch.GetTimestamp();
#endif
            CribModel.CheckForChanges();
#if DEV
            StoreModel.CheckAllForChanges();
            Perf.LiveCheck(t1);   // disk reads once a second: a hitch candidate for the 1% low
#endif
        }
        Icons.Tick();   // re-render an icon whose piece changed, or that missed items before ObjectDB had them
    }

    // Iron Gate asks every mod to say it is unofficial, in game and on any website (README too): once, under the description of the
    // first piece in the Storage tab, which the build menu shows when you open the tab.
    const string UnofficialNote = "Unofficial mod, not affiliated with or endorsed by Iron Gate or Coffee Stain.";
    static void Unofficial(Dictionary<string, string> words)
    {
        string key = Kinds.All.First(k => k == Kinds.Crib || Kinds.InRelease(k)).Token + "_desc";
        if (words.TryGetValue(key, out var desc) && !desc.EndsWith(UnofficialNote, StringComparison.Ordinal)) words[key] = desc + "\n\n" + UnofficialNote;
    }

    static void AddLocalization()
    {
        var words = new Dictionary<string, string>
        {
            ["$item_storehouse_board"] = "Board",
            ["$item_storehouse_board_desc"] = "A plank split and planed from a log. What furniture and storage are built from.",
            [Kinds.Strongbox.Token] = "Hauler's Strongbox",
            [Kinds.Strongbox.Token + "_desc"] = "A black metal chest built for a cart, not a doorway. Holds twice what a black metal chest does. Stands on level ground or a floor.",
            [Kinds.Crib.Token] = "Timber Crib",
            [Kinds.Crib.Token + "_desc"] = "An open crib of logs and iron-banded beams. Holds wood only: wood, fine wood, core wood, ancient bark, yggdrasil wood, ashwood. Stands on level ground or a floor.",
            [Kinds.Bin.Token] = "Ore Bin",
            [Kinds.Bin.Token + "_desc"] = "A stone-lined bin with an iron rim. Holds ore, scrap, stone, coal and metal bars only. Stands on level ground or a floor.",
        };
        Unofficial(words);
        LocalizationManager.Instance.GetLocalization().AddTranslation("English", words);
#if DEV
        // The stores (dev only). The Ore Bin store reuses the parked Ore Bin's token, so its text replaces that one.
        var stores = new Dictionary<string, string>();
        foreach (var k in Kinds.All)
            if (k.Desc != null)
            {
                stores[k.Token] = k.Shown ?? k.Title;
                stores[k.Token + "_desc"] = k.Desc;
            }
        Unofficial(stores);
        LocalizationManager.Instance.GetLocalization().AddTranslation("English", stores);
        // Jotunn hands its words to the game when the language is set up; a live reload comes after that, so a changed name
        // or description goes straight into the running game's table too (only once the game has made it).
        if (AccessTools.Field(typeof(Localization), "m_instance")?.GetValue(null) is Localization loc
            && AccessTools.Method(typeof(Localization), "AddWord", new[] { typeof(string), typeof(string) }) is { } addWord)
            foreach (var kv in words.Concat(stores)) addWord.Invoke(loc, new object[] { kv.Key.TrimStart('$'), kv.Value });
#endif
    }

    void AddPieces()
    {
        PrefabManager.OnVanillaPrefabsAvailable -= AddPieces;
#if DEV
        Guard("board", Board.Add);   // once: an existing board prefab is kept on a live reload
        if (Settings.DumpPrefabs.Value && !PrefabManager.Instance.GetPrefab(Kinds.Crib.Prefab))   // once per game, not per live reload
#else
        if (Settings.DumpPrefabs.Value)
#endif
            Guard("prefab dump", () => Inspect.Dump(PrefabManager.Instance.GetPrefab(Kinds.Crib.Base), "vanilla base of the Timber Crib"));
        int added = 0;
        foreach (var kind in Kinds.All)
        {
            try { AddPiece(kind); }
            catch (Exception e) { Log.LogError($"{kind.Title}: not added ({e})"); }
            if (PrefabManager.Instance.GetPrefab(kind.Prefab)) added++;
            else Failures.Add($"piece {kind.Title}");
        }
        PieceManager.OnPiecesRegistered += HammerOrder;   // the hammer is filled again at each world load
        Guard("hammer order", HammerOrder);
#if DEV
        Guard("armory sort", () => Mannequins.HookSort(harmony));   // here, not at the start: every plugin's assembly is loaded by now
#if !RELEASE
        // Once the game has its items: Jotunn's OnVanillaPrefabsAvailable comes before the menu's ObjectDB is filled (27 Oct 15:06:15,
        // "0 one-handed weapons tested"), so after every mod's items are in a world's ObjectDB (OnItemsRegistered, at each world load;
        // Report runs once), or right away on a live reload into a world.
        Guard("weapon rack fit", () => { ItemManager.OnItemsRegistered += EquipFit.Report; EquipFit.Report(); });
        Guard("points check", PointsCheck.Hook);
#endif
        // A live reload: the pieces already standing in the world, the ghost in your hand, and recipes with the real items.
        try { Reload.AfterPieces(); }
        catch (Exception e) { Log.LogError($"Live reload: the world's pieces were not all redressed ({e})."); }
#endif
        // The live line: this exact DLL (its sha256), how many pieces registered, what failed. build.sh packs a release only after a
        // game start logged it for that DLL with every piece and no failure.
        string copy = "";
#if DEV
        if (FromScripts) copy = $" (ScriptEngine copy {typeof(Plugin).Assembly.GetName().Name})";
#endif
        Log.LogInfo($"Storehouse {Version}: live, sha256 {DllSha()}, {added}/{Kinds.All.Length} pieces, {Failures.Count} start-up failure(s)"
            + (Failures.Count > 0 ? $": {string.Join("; ", Failures)}" : "") + copy + ".");
        if (!Headless && !GetComponent<LoadWarning>()) gameObject.AddComponent<LoadWarning>().Set(added, Kinds.All.Length);
    }

    // The hammer's Storehouse pieces in Kinds.All's order (the theme groups) wherever they sit in the hammer's list: Jotunn keeps a
    // piece where it was first added, so a piece new to a live reload landed after the shelves (Joost, 27 Oct: "Armor Stand, open" at
    // the very end). A dev build leaves the pieces outside the release out of the list unless "Show pieces not in the release" is on;
    // their prefabs stay registered. Runs after the pieces register, at each world load, and when that setting changes.
    internal static void HammerOrder()
    {
        var table = PieceManager.Instance.GetPieceTable(PieceTables.Hammer);
        if (!table) return;
        var ours = new HashSet<string>(Kinds.All.Select(k => k.Prefab), StringComparer.Ordinal);
        var list = table.m_pieces;
        int first = list.FindIndex(p => p && ours.Contains(p.name));
        if (first < 0) first = list.Count;
        list.RemoveAll(p => p && ours.Contains(p.name));
#if RELEASE
        var shown = Kinds.All;
#else
        var shown = Kinds.All.Where(k => Settings.ShowTestPieces?.Value == true || k == Kinds.Crib || Kinds.InRelease(k));
#endif
        list.InsertRange(Math.Min(first, list.Count), shown.Select(k => PrefabManager.Instance.GetPrefab(k.Prefab)).Where(p => p));
        if (Player.m_localPlayer) AccessTools.Method(typeof(Player), "UpdateAvailablePiecesList")?.Invoke(Player.m_localPlayer, null);
    }

    // The first 12 hex digits of this copy's DLL file ("unknown" when it can't be read).
    string DllSha()
    {
        try
        {
#if DEV
            string path = FromScripts ? Path.Combine(BepInEx.Paths.BepInExRootPath, "scripts", "Storehouse.dll") : Info.Location;
#else
            string path = Info.Location;
#endif
            using var sha = System.Security.Cryptography.SHA256.Create();
            using var file = File.OpenRead(path);
            return BitConverter.ToString(sha.ComputeHash(file)).Replace("-", "").ToLowerInvariant().Substring(0, 12);
        }
        catch (Exception e) { Log.LogWarning($"Storehouse: could not hash its own DLL ({e.Message})."); return "unknown"; }
    }

    void AddPiece(Kind kind)
    {
#if DEV
        // Registered by an earlier copy (a live reload): never register a piece twice (Jotunn refuses the name, the game's
        // tables would hold two); take the same prefab over and build it again with this copy's code.
        if (PrefabManager.Instance.GetPrefab(kind.Prefab) is { } existing)
        {
            Reload.Rebuild(existing, kind);
            return;
        }
#else
        if (PrefabManager.Instance.GetPrefab(kind.Prefab)) return;
#endif
        var cfg = new PieceConfig
        {
            Name = kind.Token,
            Description = kind.Token + "_desc",
            PieceTable = PieceTables.Hammer,
            Category = "Storage",   // its own hammer tab (Jotunn adds a custom category); vanilla keeps chests under Furniture
            CraftingStation = kind.Station?.Value ?? kind.DefaultStation,   // the default if its setting never bound
        };
        foreach (var (item, amount) in Settings.ParseRecipe(kind.Recipe?.Value ?? kind.DefaultRecipe)) cfg.AddRequirement(new RequirementConfig(item, amount, 0, true));
        var piece = new CustomPiece(kind.Prefab, kind.Base, cfg);
        if (piece.PiecePrefab == null)
        {
            Log.LogError($"Could not clone {kind.Base}; the {kind.Title} is not added.");
            return;
        }
        var go = piece.PiecePrefab;
        var p = piece.Piece;
        var container = Configure(go, p, kind);
        if (!container)
        {
            Log.LogError($"{kind.Base} has no Container; the {kind.Title} is not added.");
            return;
        }

        kind.Build(go, container);
        p.m_icon = Icons.Render(go, kind) ?? p.m_icon;
        PieceManager.Instance.AddPiece(piece);
#if DEV
        Reload.RegisterLate(go, kind);   // a piece type that is new in this copy, added during a live reload in a world
#endif
        if (Settings.DumpPrefabs.Value) Inspect.Dump(go, kind.Title + " (built)");
        Log.LogInfo($"{kind.Title}: piece added ({kind.Width}x{kind.Height}).");
    }

    // The piece's placement rules and its container's name and size. Null when the base chest has no Container.
    internal static Container Configure(GameObject go, Piece p, Kind kind)
    {
        p.m_comfort = 0;
        p.m_notOnFloor = false;   // a live reload reuses the prefab: a store that left Wall placement may stand again
        switch (kind.Placement)
        {
            case Placement.Ground:
                // Big stores: on terrain or a floor, but level (not on steep slopes). Terrain only was too limiting (Joost, 22 Oct).
                p.m_groundOnly = false;
                p.m_notOnTiltingSurface = true;
                break;
            case Placement.Wall:
                // Only against something upright: the game refuses a hit whose surface faces up (m_notOnFloor) and pushes the
                // ghost out along the wall's normal until its collider touches, which is how wall-hung pieces sit.
                p.m_groundOnly = false;
                p.m_notOnFloor = true;
                p.m_notOnTiltingSurface = false;
                break;
            default:
                // Furniture: wherever the base chest may stand (floors, terrain).
                p.m_groundOnly = false;
                break;
        }

        var container = go.GetComponentInChildren<Container>(true);
        if (!container) return null;
        container.m_name = kind.Token;      // shown as the chest's title, and how the filter recognises it
        container.m_width = kind.Width;
        container.m_height = kind.Height;
        return container;
    }
}

enum Placement { Ground, Normal, Wall }

// The pieces: their names, vanilla base, settings and how each one is dressed.
sealed class Kind
{
    public string Title, Prefab, Token, Base, Section, DefaultRecipe, DefaultStation, DefaultAccepts, FilterLabel;
    public string Shown;   // the name the player reads, when it differs from Title (which names the config section and stays)
    public HashSet<string> Never;   // prefabs it refuses whatever its Accepts says (none today: boss trophies go in the Trophy Halls, Joost 27 Oct)
    public string NeverWhy;         // and what to tell the player about them
#if DEV
    public string Desc;                         // hammer description for the dev stores (the crib's text sits in AddLocalization)
    public string Slug, Piece;                  // dev stores: model folder <Slug>_r3|_r2 (or Rounds), and the piece inside it (emergency shelf)
    public string[] Rounds;                     // model folder suffixes to look in, first wins; null: _r5, _r4, _r3, then _r2
    public bool Display;                        // display furniture (larder, shelf): one item per stack at Display item size
    public bool Mirror;                         // the store's units mirror the container grid: slot (column, row) = the same spot
    public bool Heap;                           // a stacked heap (metal pallet): the grid's bottom row is the bottom layer, front first
    public bool Homes;                          // each group belongs to the item its layout was made for (coins in the coin well)
    public Action<GameObject> Dress;            // live reload: dress a piece standing in the world with the models Build loaded
#endif
    public int Planks;                          // packed shelf (emergency shelf): its planks; the grid is slots-per-plank x planks
    public int DefaultRows;
    public Placement Placement = Placement.Ground;
    public ConfigEntry<int> Rows;
    public ConfigEntry<float> ItemSize;   // the items inside, per store (Joost, 24 Oct: "per kind of store")
    public ConfigEntry<Color> GlassColour;   // the stores with glass (Cooper's Rows, Apothecary Racks): its colour, alpha its opacity
    public ConfigEntry<string> Model;     // which of its rounds a store shows ("newest" or e.g. "r1"); stores with one round have none
    public ConfigEntry<string> Recipe, Station, Accepts;
    public Action<GameObject, Container> Build;
    public Func<ItemDrop.ItemData, bool> Rule = null;  // takes items by type, on top of the Accepts list; null: the list only
    public Filter Filter;   // null: takes anything

    // Container grid. A packed shelf: one grid row per plank, "Slots per plank" wide; a store with its own column count (the
    // half-width metal racks: 4); everything else: 8 x Rows.
#if DEV
    public int Columns;                         // 0: Kinds.Columns
    public int Width => Planks > 0 ? Settings.SlotsPerPlank.Value : Columns > 0 ? Columns : Kinds.Columns;
    public int Height => Planks > 0 ? Planks : Rows?.Value ?? TypedSlots.Rows(this, Width) ?? DefaultRows;   // no Rows setting: fixed (the armories: a row per figure; typed places: their places)
#else
    public int Width => Kinds.Columns;
    public int Height => Rows?.Value ?? DefaultRows;
#endif
}

static class Kinds
{
    public const int Columns = 8;   // the container grid is 8 wide (the black metal chest's width); wider would overflow
#if DEV
    public const int MinRows = 1;
#else
    public const int MinRows = 2;
#endif

    public static readonly Kind Strongbox = new()
    {
        Title = "Hauler's Strongbox", Prefab = "piece_storehouse_strongbox", Token = "$piece_storehouse_strongbox",
        Base = "piece_chest_blackmetal", Section = "1 - Haulers Strongbox", DefaultRows = 8,
        DefaultRecipe = "BlackMetal:12,Iron:8,FineWood:20", DefaultStation = "forge",
        Build = StrongboxModel.Build,
    };

    public static readonly Kind Crib = new()
    {
        Title = "Timber Crib", Prefab = "piece_storehouse_timbercrib", Token = "$piece_storehouse_timbercrib",
        Base = "piece_chest_wood", Section = "2 - Timber Crib", DefaultRows = 8,
        DefaultRecipe = "Wood:20,StorehouseBoard:10,BronzeNails:10", DefaultStation = "piece_workbench",
        // Prefab names (ObjectDB). Blackwood is ashwood; Frostwood is the Deep North's. Unknown names are logged and skipped.
        DefaultAccepts = "Wood,FineWood,RoundLog,ElderBark,YggdrasilWood,Blackwood,Frostwood,Root,WrithanRoots,BarkaBranch",   // no boards (Joost, 25 Oct: "unlogical")   // + ITEMS.md (24 Oct)
        FilterLabel = "Wood only",
        Build = CribModel.Build,
#if DEV
        Dress = go => CribModel.Dress(go, quiet: true),
#endif
    };

    public static readonly Kind Bin = new()
    {
        Title = "Ore Bin", Prefab = "piece_storehouse_orebin", Token = "$piece_storehouse_orebin",
        Base = "piece_chest", Section = "3 - Ore Bin", DefaultRows = 6,
        DefaultRecipe = "Stone:30,Iron:6,Wood:10", DefaultStation = "piece_stonecutter",
        DefaultAccepts = "CopperOre,TinOre,IronScrap,IronOre,SilverOre,BlackMetalScrap,FlametalOre,FlametalOreNew,GoldOre,CopperScrap,BronzeScrap,"
            + "Stone,Flint,Coal,Obsidian,Crystal,Grausten,BlackMarble,SulfurStone,"
            + "Copper,Tin,Bronze,Iron,Silver,BlackMetal,Flametal,FlametalNew,Gold",
        FilterLabel = "Ore, stone and metal only",
        Build = Kitbash.OreBin,
    };

#if DEV
    // The seven round-2 stores (dev build only): our own frame (OBJ + atlas) holding the stored items' own models.
    // Rows = the designed number of stacks over 8, rounded up. Accepts is the fallback list on top of the type rule.
    // Config section names may not hold = newline tab backslash " ' [ ] (BepInEx); a title like "Cooper's Row" stopped the
    // whole mod loading (Joost, 24 Oct).
    static readonly char[] notInSection = { '=', '\n', '\t', '\\', '"', '\'', '[', ']' };
    static string SectionSafe(string title) => new string(title.Where(c => Array.IndexOf(notInSection, c) < 0).ToArray());

    static Kind Store(string slug, string title, string desc, string label, Func<ItemDrop.ItemData, bool> rule, string accepts,
        int units, Placement placement, string recipe, string station, string piece = null, string prefab = null,
        bool display = false, int planks = 0, string[] rounds = null, bool mirror = false, int columns = 0, bool heap = false, bool homes = false)
    {
        string key = piece == null ? slug : slug + "_" + piece;
        prefab ??= "piece_storehouse_" + key;
        return new Kind
        {
            Title = title, Prefab = prefab, Token = "$" + prefab, Base = "piece_chest_wood", Section = "4 - " + SectionSafe(title),
            Slug = slug, Piece = piece,
            Desc = desc, FilterLabel = label, Rule = rule, DefaultAccepts = accepts, DefaultRows = (units + (columns > 0 ? columns : Columns) - 1) / (columns > 0 ? columns : Columns), Columns = columns,
            Placement = placement, DefaultRecipe = recipe, DefaultStation = station, Display = display, Planks = planks, Rounds = rounds, Mirror = mirror, Heap = heap, Homes = homes,
            Build = (go, container) => StoreModel.Get(slug, piece, title).BuildPiece(go),
            Dress = go => StoreModel.Get(slug, piece, title).BuildPiece(go, quiet: true),
        };
    }

    // The earlier models a store keeps on purpose, to compare in game (Joost, 25 Oct: the wide Bomb Crate, the Ossuary's bays). They are
    // shipped and offered in the store's Model setting; every other older round stays in the repo only (ship-rounds.py).
    public static readonly Dictionary<string, string[]> ModelAlternates = new(StringComparer.Ordinal)
    {
        ["bombcrate"] = new[] { "_r2" },   // the stepped one, to compare with r3 (Joost: wide, not deep)
        ["fletcher"] = new[] { "_r3ds", "_r3cs", "_r3s", "_r2" },   // r3es (r3e's cells: no repeats in 642 regions, 20 distinct cells per bolt kind; with r3s's closed straw) the default since 27 Oct; r3ds (r3d's cells, 25 Oct), r3cs, r3s and r2 selectable
        ["ossuary"] = new[] { "_r5", "_r3", "_r4" },   // r5b (r5's heaps, bay 3 refilled, drawn through its display masks) the default; r5 (Joost: "exactly it"), r3's bays his fallback, r4 to compare
        // Equipment r2 (Sol 6.1, with clear boxes and the coverage gaps) against r1, Joost compares (the Arsenal r2 is 5.8-6.1 m wide).
        ["weaponrack"] = new[] { "_r3", "_r1" }, ["weaponrackb"] = new[] { "_r3", "_r1" }, ["arsenal"] = new[] { "_r1" }, ["arsenalb"] = new[] { "_r4", "_r3", "_r1" },   // r6 the default (Joost, 27 Oct: "R6 can go in. That looks nice."); r4: straw 3 cm under the rims (25 Oct)
        ["utilitywall"] = new[] { "_r1" }, ["utilityisland"] = new[] { "_r1" },
        ["armoryrail"] = new[] { "_r1" }, ["armoryrail3"] = new[] { "_r1" }, ["armoryisland"] = new[] { "_r2" },   // r3 the default (25 Oct)
        ["armorcoffer"] = new[] { "_r2", "_r1" }, ["armorcabinet"] = new[] { "_r2", "_r1" },   // r3 the default (27 Oct); r2 (more, less honest places) to compare
        ["armory"] = new[] { "_r1" }, ["armoryb"] = new[] { "_r2b", "_r1" },   // r2c the default (27 Oct); r2b to compare
        // The giant shield: r3's giant in the trough (kit 4.8 x 4 m) the default (Joost, 27 Oct, in game: "R3 all the way"); r4's
        // turned end bay on the 1 m plank (kit 4.8 x 5 m) stays selectable.
        ["arsenalkit_shield"] = new[] { "_r3", "_r4" },
        // Round 5 the default (Joost, 27 Oct: the release ships it): the Spine's knives, swords and Porcupine hang, nothing floats; the
        // Long Rack's weapons lean back and the Bow Rack's bows each lean, all designed in the anchors; the Shield Trough r3b is r3 with
        // no shield hiding another. Round 4 to compare.
        ["arsenalkit_spine"] = new[] { "_r4" }, ["arsenalkit_long"] = new[] { "_r5b", "_r4" },   // r5c the default (Joost, 27 Oct: a crossbar on each face); r5b to compare
        // The Bow Rack is r4 only (Joost, 27 Oct, r5 in game: thin and janky, "so much thicker and sturdier back then"; later, of r5's
        // posts: "I don't like these little upside down L's, they make it seem very fragile"): r5 is not shipped or selectable.
        ["arrowtubes"] = new[] { "_r3" },   // r4 (20 arrangements, 27 Oct) the default; r3's three turned ones to compare
        // r11 / stack r4 the default (Joost, 27 Oct: "R11. That looks really good."): 14 vessels on r9's footprint again; r10 / stack r3
        // (the same 14, 1.1 m wider) and the 13-vessel r9 / stack r2 to compare.
        ["coopersrow"] = new[] { "_r10", "_r9" }, ["coopersrowstack"] = new[] { "_r3", "_r2" },
    };

    public static readonly Kind[] Stores =
    {
        // Shown as "Brewer's Cabinet" (Joost, 27 Oct, release names); its config section stays "Mead Rack".
        Shown("Brewer's Cabinet", Store("meadrack", "Mead Rack", "A rack of shelves for bottles. Holds meads and potions only.", "Meads and potions only",
            ItemRules.Mead, "BarleyWine,BarleyWineBase,MeadBase*", 64, Placement.Normal, "StorehouseBoard:16,BronzeNails:10", "piece_workbench", mirror: true, rounds: new[] { "_r3", "_r2" })),
        Store("larder", "Larder Hutch", "A kitchen hutch for cooked food. Holds meals only.", "Meals only",
            ItemRules.Meal, "", 64, Placement.Normal, "StorehouseBoard:18,BronzeNails:12", "piece_workbench", display: true, mirror: true, rounds: new[] { "_r6", "_r5", "_r4", "_r3", "_r2" }),
        Store("meatrack", "Meat Rack", "Hooks and bins for the day's catch. Holds meat and fish, raw or cooked, and the animal parts for food and meads.", "Meat and fish only",
            ItemRules.RawMeat, "RawMeat,DeerMeat,NeckTail,WolfMeat,LoxMeat,SerpentMeat,ChickenMeat,HareMeat,BugMeat,AsksvinMeat,VoltureMeat,BoneMawSerpentMeat,FishRaw,Bloodclot,Entrails",
            64, Placement.Normal, "Wood:12,StorehouseBoard:10,BronzeNails:10", "piece_workbench"),   // 64 like every store in and around the house (Joost)
        Store("rootbin", "Produce Crates", "Crates for what the farm and the forest give. Holds vegetables, mushrooms, berries, herbs, seeds and eggs only.", "Produce only",   // was the Root Bin (Joost, 22 Oct: eggs go in too); prefab and token stay rootbin so placed ones keep their contents
            ItemRules.Plant, "Turnip,Onion,Carrot,Barley,Flax,Thistle,Dandelion,Fiddleheadfern,*Seeds,Mushroom*,*berries,Raspberry,Cloudberry,Acorn,AncientSeed,FirCone,FirConeFrost,PineCone,FreshSeaweed",
            72, Placement.Normal, "StorehouseBoard:14,BronzeNails:8", "piece_workbench", rounds: new[] { "_r8", "_r7", "_r6", "_r5", "_r4", "_r3", "_r2" }),   // nine crates of 8 (Joost); r7: z-fix
        // Same prefab name as the parked 0.1.0 Ore Bin, so ore bins already standing in a world take this look.
        Store("orebin", "Ore Bin", "A timber bin for the mine's haul. Holds ore and scrap only. Stands on level ground or a floor.", "Ore and scrap only",
            ItemRules.Ore, "CopperOre,TinOre,IronScrap,IronOre,SilverOre,BlackMetalScrap,FlametalOre,FlametalOreNew,CopperScrap,BronzeScrap",
            80, Placement.Ground, "Wood:12,StorehouseBoard:10,Stone:10,IronNails:8,Iron:4", "piece_workbench", prefab: "piece_storehouse_orebin"),
        Store("bunker", "Coal & Stone Bunker", "Three bays for loose heaps. Holds coal and stone only. Stands on level ground or a floor.", "Coal and stone only",
            ItemRules.StoneCoal, "Coal,Stone,Flint,Grausten,BlackMarble,Obsidian,SulfurStone,StoneRock,PungentPebbles,BFP_Clay,Ice,Crystal", 90, Placement.Ground, "Wood:16,StorehouseBoard:12,IronNails:8,Iron:4", "piece_workbench"),   // all timber (Joost)
        // The bunker as it was before it stacked (bunker_r3, kept as assets/bunkeropen_r1): slanted sides and a leaning back wall,
        // no load-bearing top. Joost, 24 Oct: "I loved it before it was stackable"; both stay, like the metal racks' variants.
        Store("bunkeropen", "Open Coal & Stone Bunker", "The bunker without a load-bearing top: three open bays under a leaning back wall. Holds coal and stone only; nothing stacks on it.", "Coal and stone only",
            ItemRules.StoneCoal, "Coal,Stone,Flint,Grausten,BlackMarble,Obsidian,SulfurStone,StoneRock,PungentPebbles,BFP_Clay,Ice,Crystal", 90, Placement.Ground, "Wood:14,StorehouseBoard:10,IronNails:6,Iron:2", "piece_workbench", rounds: new[] { "_r1" }),
        // Metal storage (Joost, 22 Oct): outdoor, stackable (corner posts, flat top). Narrow and tall against a wall; wide and low
        // on the ground. The rack mirrors the chest grid; the pallet's piles fill back to front.
        Store("metalrack", "Metal Rack (tall)", "A tall timber rack for bars, iron-strapped. Holds metal bars only. Stacks.", "Metal bars only",
            ItemRules.Metal, "Copper,Tin,Bronze,Iron,Silver,BlackMetal,Flametal,FlametalNew", 64, Placement.Ground,
            "Wood:12,StorehouseBoard:12,IronNails:8,Iron:4", "piece_workbench", rounds: new[] { "_r3", "_r2", "_r1" }, mirror: true),
        // Round 2 (Joost): bars at true size, every stack a pile you see; modules that line up: two halves side by side = a
        // whole rack, two lows stacked = a tall one.
        Store("metalrackhalf", "Metal Rack (tall, half)", "A tall timber rack for bars, half as wide. Holds metal bars only. Stacks.", "Metal bars only",
            ItemRules.Metal, "Copper,Tin,Bronze,Iron,Silver,BlackMetal,Flametal,FlametalNew", 32, Placement.Ground,
            "Wood:8,StorehouseBoard:8,IronNails:6,Iron:2", "piece_workbench", rounds: new[] { "_r2", "_r1" }, mirror: true, columns: 4),
        Store("metalracklow", "Metal Rack (low)", "A low timber rack for bars. Holds metal bars only. Stacks.", "Metal bars only",
            ItemRules.Metal, "Copper,Tin,Bronze,Iron,Silver,BlackMetal,Flametal,FlametalNew", 32, Placement.Ground,
            "Wood:8,StorehouseBoard:8,IronNails:6,Iron:2", "piece_workbench", rounds: new[] { "_r2", "_r1" }, mirror: true),
        Store("metalracklowhalf", "Metal Rack (low, half)", "A low timber rack for bars, half as wide. Holds metal bars only. Stacks.", "Metal bars only",
            ItemRules.Metal, "Copper,Tin,Bronze,Iron,Silver,BlackMetal,Flametal,FlametalNew", 16, Placement.Ground,
            "Wood:4,StorehouseBoard:4,IronNails:4,Iron:1", "piece_workbench", rounds: new[] { "_r2", "_r1" }, mirror: true, columns: 4),
        Store("metalpallet", "Metal Pallet", "A low pallet for stacked bars. Holds metal bars only. Stacks.", "Metal bars only",
            ItemRules.Metal, "Copper,Tin,Bronze,Iron,Silver,BlackMetal,Flametal,FlametalNew", 64, Placement.Ground,
            "Wood:16,StorehouseBoard:10,IronNails:8,Iron:4", "piece_workbench", rounds: new[] { "_r4", "_r3", "_r2", "_r1" }, heap: true),
        // The second series (Joost, 23 Oct 2026: "storage that fits Valheim for everything we still keep in plain chests"). Each
        // group belongs to the item its layout was made for (homes); STYLE.md keeps them one family with the stores above.
        // Mass storage, sized to the volume of what they hold (Joost, 24 Oct: four rows "is exactly not the point"; SPEC.md).
        Store("coopersrow", "Cooper's Row", "Barrels, pots and tubs for sticky goods: tar, resin, sap, guck, ooze and powder, one kind per vessel.", "Tar, resin, sap and goo only",
            // CooperDefaults: the 14 kinds, one vessel each; Ectoplasm moved here from the Apothecary (Joost, 25 Oct) once r10 gave it a
            // vessel (27 Oct). r11 is r9's 3.92 m again with all 14 (a smaller front row); r10 was 5.04 m wide.
            null, StorageReviewPolicy.CooperDefaults, 64, Placement.Ground,
            "Wood:10,StorehouseBoard:12,IronNails:6,Iron:2", "piece_workbench", rounds: new[] { "_r11", "_r10", "_r9", "_r6", "_r5", "_r4", "_r3", "_r2", "_r1" }, homes: true),
        // The same vessels in a six-post frame with a plank deck 0.35 m above the rims, so you can still pour and something can
        // stand on it (Joost, 24 Oct: "Cooper's Row you'd expect to stack"; a bit dearer). First sketch: coopersrowstack_r1.
        Store("coopersrowstack", "Stacking Cooper's Row", "Cooper's Row in a six-post frame under a plank deck: the same vessels, room above to pour, and another one stacks on top.", "Tar, resin, sap and goo only",
            null, StorageReviewPolicy.CooperDefaults, 64, Placement.Ground,   // r4: Cooper's Row r11's 14 vessels, 3.95 m wide again (r3 5.04)
            "Wood:16,StorehouseBoard:18,IronNails:10,Iron:4", "piece_workbench", rounds: new[] { "_r4", "_r3", "_r2", "_r1" }, homes: true),
        Store("fletcher", "Fletcher's Barrels", "Barrels for arrows, tubs for bolts and a straw crate for bombs, one kind per holder.", "Arrows, bolts and bombs only",
            ItemRules.ArrowOrBolt, "Arrow*,Bolt*,Bomb*,VA*Arrow*,VA*arrow*,VA*Bolt*,VA*bolt*,TurretBolt*,Catapult_*,FireworksRocket_*,Sparkler", 64, Placement.Ground,   // VA*: ValheimArmory's arrows and bolts (Joost, 24 Oct)
            "StorehouseBoard:14,BronzeNails:10,LeatherScraps:4", "piece_workbench", rounds: new[] { "_r3es", "_r3ds", "_r3cs", "_r3s", "_r3", "_r2", "_r1" }, homes: true),
        // The gold heap (Joost, 27 Oct: "Treasure Hoard wordt de goudberg (munten en goud), juwelen naar de Jeweller's Casket"). Gems
        // already in a placed hoard stay in it and come out as before; only new deposits follow the new rule.
        Store("treasure", "Treasure Hoard", "An iron-bound coffer heaped with coins and gold. Gems and jewellery go in the Jeweller's Casket. Open the inventory for any stored kinds without a display place.", "Coins and gold only",
            ItemRules.CoinOrGold, StorageReviewPolicy.TreasureDefaults, 96, Placement.Ground,
            "StorehouseBoard:12,IronNails:8,Iron:4,DeerHide:2", "piece_workbench", rounds: new[] { "_r2", "_r1" }, homes: true),
        Store("apothecary", "Apothecary Rack", "Jars, crocks, bags and baskets on a standing rack for the small things creatures leave behind, one kind per vessel.", "Creature parts only",
            // No Surtling cores: they belong in the Ember Cabinet (Joost, 25 Oct 18:10).
            null, "Feathers,Needle,GreydwarfEye,GiantBloodSack,AskBladder,WolfFang,Carapace,WolfHairBundle,ElakingHairBundle,Chitin,"
                + "CelestialFeather,MooseSinew,BjornPaw,WolfClaw,MorgenHeart,Bilebag,MorgenSinew,Mandible,SerpentScale,BonemawSerpentScale,FreezeGland,MoleClaws",
            64, Placement.Normal, "StorehouseBoard:12,BronzeNails:8,LeatherScraps:2", "piece_workbench", rounds: new[] { "_r3", "_r2", "_r1" }),
        Store("hiderack", "Hide Rack", "Hinged frames on an iron-banded post, one hide stretched in each, the folded hides piled in the bay below.", "Hides and leather only",
            null, "TrollHide,WolfPelt,LoxPelt,DeerHide,LeatherScraps,AskHide,ScaleHide,BjornHide,MooseHide,SealHide,Leatherstraps", 64, Placement.Ground,
            "Wood:10,StorehouseBoard:12,BronzeNails:8,LeatherScraps:4", "piece_workbench", rounds: new[] { "_r3", "_r2", "_r1" }, homes: true),
        Store("clothrack", "Cloth Rack", "A narrow rack for cloth and thread: linen, jute and Norn thread, one kind per bay.", "Cloth and thread only",
            null, "LinenThread,JuteRed,JuteBlue,NornThread,CandleWick", 32, Placement.Normal,
            "StorehouseBoard:10,BronzeNails:6,LinenThread:2", "piece_workbench", rounds: new[] { "_r2", "_r1" }, columns: 4),
        Store("ossuary", "Ossuary Bin", "A stone-footed bin for bones: fragments, charred and withered bones, skulls and antlers, one kind per bay.", "Bones only",
            null, "BoneFragments,CharredBone,WitheredBone,Charredskull,HardAntler,AsksvinCarrionSkull,BonemawSerpentTooth,AsksvinCarrionNeck,AsksvinCarrionPelvic,AsksvinCarrionRibcage,UndeadBjornRibcage,LargeBone,GhostSkull", 128, Placement.Ground,
            "Wood:12,StorehouseBoard:10,Stone:16,IronNails:6,Iron:2", "piece_workbench", rounds: new[] { "_r5b", "_r5", "_r3", "_r2", "_r1" }, homes: true),
        // The third series (Joost, 24 Oct: "everything that is a new group: make a prototype"; ITEMS.md). Prototypes, round 1.
        Store("arrowtubes", "Arrow Tubes", "A stepped stand of tubes, one per kind of arrow, each with its painted band; bundles packed tight.", "Arrows only",
            ItemRules.Arrow, "Arrow*,VA*Arrow*,VA*arrow*", 80, Placement.Ground,
            "Wood:12,StorehouseBoard:14,BronzeNails:10,LeatherScraps:4", "piece_workbench", rounds: new[] { "_r4", "_r3", "_r2", "_r1" }, homes: true),   // r4: 20 tube arrangements (r3: 3, turned), fewer arrows through each other; r3: straw 15-25 mm under the rim, bands by contents
        Store("bolttubs", "Bolt Crate", "A stepped crate of square cells for handheld crossbow bolts, one kind per cell. Siege ammunition needs its own fitted storage.", "Crossbow bolts only",
            ItemRules.Bolt, "Bolt*,VA*Bolt*,VA*bolt*", 64, Placement.Ground,
            "Wood:10,StorehouseBoard:12,IronNails:8", "piece_workbench", rounds: new[] { "_r3", "_r2", "_r1" }, homes: true),   // r3: straw to 0.175-0.185 m
        Store("bombcrate", "Bomb Crate", "A compact stepped crate of straw-bedded trays, one kind of bomb per tray, a reserve tier at the back and a bucket of sand at hand.", "Bombs only",
            null, "Bomb*", 64, Placement.Ground,
            "StorehouseBoard:14,IronNails:8,Iron:2", "piece_workbench", rounds: new[] { "_r3", "_r2" }, homes: true),   // r3: wide and shallow (Sol 6.1); r2: stepped (Claude Opus 5.5); 64 slots (was 40); r1 (hazard stripes) no longer shipped
        Shown("Apothecary Rack, Tall", Store("apothecarytall", "Tall Apothecary Rack", "The Apothecary Rack two metres wide and as tall as a metal rack: forty places, each vessel following what it holds.", "Creature parts only",
            // No Surtling cores: they belong in the Ember Cabinet (Joost, 25 Oct 18:10).
            null, "Feathers,Needle,GreydwarfEye,GiantBloodSack,AskBladder,WolfFang,Carapace,WolfHairBundle,ElakingHairBundle,Chitin,"
                + "CelestialFeather,MooseSinew,BjornPaw,WolfClaw,MorgenHeart,Bilebag,MorgenSinew,Mandible,SerpentScale,BonemawSerpentScale,FreezeGland,MoleClaws",
            64, Placement.Normal, "StorehouseBoard:16,BronzeNails:10,LeatherScraps:2", "piece_workbench", rounds: new[] { "_r2", "_r1" })),
        Store("pantry", "Pantry Dresser", "A cook's dry reserve for flour, spices, herbs and processed ingredients. Genuine uncooked dishes are optional stock; prepared meals belong in the Larder.", "Dry cooking ingredients and uncooked food only",
            null, StorageReviewPolicy.PantryDefaults, 80, Placement.Normal,
            "StorehouseBoard:16,BronzeNails:10", "piece_workbench", rounds: new[] { "_r4", "_r2", "_r1" }),
        Store("smithdrawers", "Smith's Drawers", "A chest of timber drawers pulled half open: nails, chain, rings, springs, axe heads and the smith's odds and ends.", "Smithing parts only",
            null, "BronzeNails,IronNails,Chain,BarrelRings,MechanicalSpring,AxeHead1,AxeHead2,ScytheHandle,CeramicPlate,CharredCogwheel,SharpeningStone,BellFragment", 64, Placement.Normal,
            "StorehouseBoard:12,Iron:4,IronNails:10", "piece_workbench", rounds: new[] { "_r2", "_r1" }, homes: true),
        Store("jeweller", "Jeweller's Casket", "A casket of lined trays for gems and jewellery, one kind per tray. Coins and gold go in the Treasure Hoard; open the inventory for stored kinds without a place.", "Gems and jewellery only",
            ItemRules.Jewel, StorageReviewPolicy.JewellerDefaults, 64, Placement.Normal,
            "StorehouseBoard:8,IronNails:6,LinenThread:4", "piece_workbench", rounds: new[] { "_r2", "_r1" }, homes: true),
        Store("embercabinet", "Ember Cabinet", "An iron lantern cabinet with a niche for each glowing thing: wisps, cores, embers, orbs and glow worms.", "Glowing things only",
            ItemRules.ArcaneCore, "Wisp,GlowWorm,FaderEmber,MemorialCoal,MoltenCore,BlackCore,FrostCore,ShieldCore,OrbFrostFire,OrbThunderBlood,SurtlingCore,FrozenFuel,Thunderstone,Eitr,DragonTear", 64, Placement.Normal,
            "StorehouseBoard:8,Iron:6,IronNails:6", "piece_workbench", rounds: new[] { "_r2", "_r1" }, homes: true),
        // The first hall (80 places) stays as it was, so a placed one keeps every trophy; only its shown name says which it is.
        Shown("Trophy Hall (80, first)", Store("trophyhall", "Trophy Hall", "A free-standing wall of boards, one trophy mounted on each.", "Trophies only",
            item => item.m_shared.m_itemType == ItemDrop.ItemData.ItemType.Trophy, "Trophy*", 80, Placement.Normal,
            "Wood:20,StorehouseBoard:24,IronNails:12", "piece_workbench", display: true, mirror: true, columns: 10, rounds: new[] { "_r3", "_r2", "_r1" })),
        // Sized for every creature's trophy but the bosses' (Joost, 25 Oct: 65 in his game; "add both"): a long wall of 13 x 5 and a
        // tall one of 10 x 7, a place per slot (trophyhall-variants, r3's schema; flat back for a wall, runners for the floor). Boss
        // trophies go in too (Joost, 27 Oct: "why not, it's up to the player").
        Shown("Trophy Hall", Store("trophyhall13x5", "Trophy Hall 13x5", "A long wall of boards, one trophy mounted on each, the bosses' too.", "Trophies only",
            item => item.m_shared.m_itemType == ItemDrop.ItemData.ItemType.Trophy, "Trophy*", 65, Placement.Normal,
            "Wood:18,StorehouseBoard:22,IronNails:11", "piece_workbench", display: true, mirror: true, columns: 13, rounds: new[] { "_r1" })),
        Store("trophyhall10x7", "Tall Trophy Hall", "A tall wall of boards, one trophy mounted on each, the bosses' too.", "Trophies only",
            item => item.m_shared.m_itemType == ItemDrop.ItemData.ItemType.Trophy, "Trophy*", 70, Placement.Normal,
            "Wood:18,StorehouseBoard:24,IronNails:12", "piece_workbench", display: true, mirror: true, columns: 10, rounds: new[] { "_r1" }),
        // Equipment storage (Joost, 25 Oct: armor as a chest with automatic display; shields edge-on like CDs, one featured; weapons
        // dense like Fletcher's; a narrow handheld unit and a combined one). Two versions of each idea as separate prototype pieces,
        // models by B (Sol 6.1 / extra high, real game meshes at true size). Each shows real stored gear at its own size in a place
        // made for its type (EquipPlace); what has no fitting place stays in the chest, unseen. A plain chest otherwise.
        Store("armorcoffer", "Armor Coffer", "An open reserve coffer for armor: helmets in their trays, chest, legs and capes folded in piles. Shows every piece it holds.", "Armor and trinkets only",
            EquipRules.Armor, "", 64, Placement.Normal, "StorehouseBoard:16,IronNails:10,Iron:2", "piece_workbench", rounds: new[] { "_r3", "_r2", "_r1" }),   // r3 (Joost, 27 Oct): honest piles by true height, full-size helmet places, 19 on average
        Store("armorcabinet", "Armor Cabinet", "A tall coffer cabinet for armor: helmets in cubbies, the rest folded in piles. Shows every piece it holds.", "Armor and trinkets only",
            EquipRules.Armor, "", 64, Placement.Normal, "StorehouseBoard:20,IronNails:12,Iron:4", "piece_workbench", rounds: new[] { "_r3", "_r2", "_r1" }),   // r3 (Joost, 27 Oct): honest piles by true height, full-size helmet places, 36 on average
        Store("weaponrack", "Weapon Rack A", "A narrow rack for eight one-handed weapons at their true size. Put several side by side.", "One-handed weapons only",
            EquipRules.RackWeapon, "", 8, Placement.Normal, "StorehouseBoard:6,IronNails:4", "piece_workbench", rounds: new[] { "_r4", "_r3", "_r2", "_r1" }),
        Store("weaponrackb", "Weapon Rack B", "The narrow weapon rack in a second build: eight one-handed weapons at their true size.", "One-handed weapons only",
            EquipRules.RackWeapon, "", 8, Placement.Normal, "StorehouseBoard:6,IronNails:4", "piece_workbench", rounds: new[] { "_r4", "_r3", "_r2", "_r1" }),
        Store("arsenal", "Arsenal A", "Weapons and shields: one-handed and long weapons, bows, reserve shields edge-on and the best shield on show.", "Weapons, tools and shields only",
            EquipRules.Arsenal, "", 64, Placement.Normal, "StorehouseBoard:16,IronNails:10,Iron:4", "piece_workbench", rounds: new[] { "_r2", "_r1" }),
        // Shown as "Arsenal" (Joost, 27 Oct: "I guess we should just call that the Arsenal, right?"); its config section stays "Arsenal B".
        Shown("Arsenal", Store("arsenalb", "Arsenal B", "Weapons, bows, reserve shields edge-on and the best shield on show.", "Weapons, tools and shields only",
            EquipRules.Arsenal, "", 32, Placement.Normal, "StorehouseBoard:18,IronNails:10,Iron:4", "piece_workbench", rounds: new[] { "_r6", "_r4", "_r3", "_r2", "_r1" })),   // chest = its 32 places (Joost, test sheet f13); was 64
        // The Arsenal kit (Joost's trestle sketch, 25 Oct; models by Sol, arsenal-kit r4): four pieces that snap together, shield troughs
        // at the spine's sides and the long and bow racks at its ends. Each shows real weapons at their true size; one chest slot per
        // place. The shield trough may still change (Joost's choice on the giant shield): its round folder is swapped whole.
        Store("arsenalkit_spine", "Arsenal Spine", "A trestle spine with arms on both faces: swords, knives, axes and maces hung by their heads in three tiers. Shield troughs snap to its sides, the long and bow racks to its ends.", "One-handed swords, knives, axes and maces only",
            EquipRules.KitSpine, "", 56, Placement.Normal, "StorehouseBoard:20,IronNails:12,Iron:4", "piece_workbench", rounds: new[] { "_r5", "_r4" }),
        Store("arsenalkit_shield", "Arsenal Shield Trough", "A low trough with a high back: shields lean in their own heel slots, the largest in the turned end bay. Snaps to a side of the Arsenal Spine.", "Shields only",
            EquipRules.KitShield, "", 10, Placement.Normal, "StorehouseBoard:12,IronNails:8", "piece_workbench", rounds: new[] { "_r3b", "_r3", "_r4" }, columns: 5),
        Store("arsenalkit_long", "Arsenal Long Rack", "A straw-filled box with an upper guide: spears, atgeirs, sledges, battleaxes and greatswords standing upright. Snaps to an end of the Arsenal Spine.", "Spears and two-handed weapons only",
            EquipRules.KitLong, "", 12, Placement.Normal, "StorehouseBoard:12,IronNails:8", "piece_workbench", rounds: new[] { "_r5c", "_r5b", "_r5", "_r4" }, columns: 6),   // r5b (27 Oct): the back six lean in toward the ridge too, like an A (Joost); r5 leaned them out
        Store("arsenalkit_bow", "Arsenal Bow Rack", "An A-frame end cap: six bows in skinny slots and two crossbows across their pegs. Snaps to an end of the Arsenal Spine.", "Bows and crossbows only",
            EquipRules.KitBow, "", 8, Placement.Normal, "StorehouseBoard:8,IronNails:6", "piece_workbench", rounds: new[] { "_r4", "_r5" }),
        Store("armory", "Armory A", "Armor, weapons and shields together: armor folded in the coffer, weapons racked, the best shield on show.", "Armor, weapons and shields only",
            EquipRules.Combined, "", 64, Placement.Normal, "StorehouseBoard:24,IronNails:14,Iron:6", "piece_workbench", rounds: new[] { "_r2", "_r1" }),
        // Shown as "Armory" (Joost, 27 Oct: "And then we have Arsenal, Armory"); its config section stays "Armory B".
        Shown("Armory", Store("armoryb", "Armory B", "Reachable from both sides: armor, weapons and shields together.", "Armor, weapons and shields only",
            EquipRules.Combined, "", 64, Placement.Normal, "StorehouseBoard:24,IronNails:14,Iron:6", "piece_workbench", rounds: new[] { "_r2c", "_r2b", "_r2", "_r1" })),   // r2c: the back face redone (8 shields leaning like the trough, guided weapon bays, a checked pose per item; Joost, 27 Oct); r2b: r2 with its back-face weapons and shields facing the back aisle (Joost, 27 Oct, f70: "rotated backwards")
        // Worn armor (Joost, 25 Oct: "armor doesn't fold"; both versions in game): sets on carved wooden forms, each form wearing a
        // helmet, chest, legs and cape, a one-handed weapon in the right hand and a shield in the left (models by Sol 6.1 / extra high).
        Store("armoryrail", "Armory Rail", "A rail of carved wooden mannequins, each wearing a full set of armor with its cape, weapon and shield, ready to grab.", "Armor, one-handed weapons and shields only",
            EquipRules.Mannequin, "", 36, Placement.Normal, "StorehouseBoard:18,IronNails:10,Iron:4", "piece_workbench", rounds: new[] { "_r3b", "_r3", "_r1" }, columns: 6),   // a column per mannequin, six slot rows; r3b: r3 with corner snaps (27 Oct)
        Store("armoryisland", "Armory Island", "A two-sided island of carved wooden mannequins, each wearing a full set of armor with its cape, weapon and shield.", "Armor, one-handed weapons and shields only",
            EquipRules.Mannequin, "", 36, Placement.Normal, "StorehouseBoard:20,IronNails:12,Iron:4", "piece_workbench", rounds: new[] { "_r3", "_r2", "_r1" }, columns: 6),   // a column per mannequin; r2 armed (B2a)
        // Three armed figures on a short deck (Joost, 25 Oct 17:56: the six-figure Rail stays, and a three-figure one beside it).
        Store("armoryrail3", "Short Armory Rail", "A short rail of three carved wooden mannequins, each wearing a full set of armor with its cape, weapon and shield.", "Armor, one-handed weapons and shields only",
            EquipRules.Mannequin, "", 18, Placement.Normal, "StorehouseBoard:10,IronNails:6,Iron:2", "piece_workbench", rounds: new[] { "_r3b", "_r3", "_r1" }, columns: 3),   // 3 mannequins x 6 slot rows; r3b: r3 with corner snaps
        // One armed figure on its own deck with the rail's high back (Joost, 25 Oct: the single Armor Stand), exactly an armory of one.
        // Joost, 27 Oct: both versions, with and without the back rail, and the stands snap to each other and to the rails: r2 and
        // the rails' r3b carry four floor corners ("snap_points"), stand to stand 1.187 m, to the short rail 2.374 m, the long 4.1545 m.
        Store("armorstand", "Armor Stand", "A carved wooden mannequin on its own deck, wearing a full set of armor with its cape, weapon and shield.", "Armor, one-handed weapons and shields only",
            EquipRules.Mannequin, "", 6, Placement.Normal, "StorehouseBoard:5,IronNails:3,Iron:1", "piece_workbench", rounds: new[] { "_r2", "_r1" }, columns: 1),   // 1 mannequin x 6 slot rows
        Store("armorstandopen", "Armor Stand, open", "A carved wooden mannequin on its own open deck, without the back rail, wearing a full set of armor with its cape, weapon and shield. Snaps to other stands and the armory rails.", "Armor, one-handed weapons and shields only",
            EquipRules.Mannequin, "", 6, Placement.Normal, "StorehouseBoard:5,IronNails:3,Iron:1", "piece_workbench", rounds: new[] { "_r2" }, columns: 1),   // Sol's armor_stand_r2_open: r2's figure and deck, the back taken off
        Store("utilitywall", "Utility Wall", "Shelves and sockets for tools, belts and wearables, trinkets, and a saddle on the deep bay floor.", "Tools, utility items, trinkets and saddles only",
            EquipRules.Utility, "Saddle*", 64, Placement.Normal, "StorehouseBoard:14,IronNails:8,Iron:2", "piece_workbench", rounds: new[] { "_r2", "_r1" }),
        Store("utilityisland", "Utility Island", "A low island table for tools, wearables, trinkets and two saddles on its top.", "Tools, utility items, trinkets and saddles only",
            EquipRules.Utility, "Saddle*", 64, Placement.Normal, "StorehouseBoard:12,IronNails:8,Iron:2", "piece_workbench", rounds: new[] { "_r2", "_r1" }),
        // Round 4 (Joost, 22 Oct 2026): only what fits goes on, so you choose what you grab after dying. One item per stack,
        // packed along the planks at runtime (StoreContents.Pack); one grid, one row per plank.
        Shelf(1, "StorehouseBoard:5,BronzeNails:4"),
        Shelf(2, "StorehouseBoard:10,BronzeNails:8"),
        Shelf(3, "StorehouseBoard:15,BronzeNails:12"),
    };

    // "Name them the same and then put the tall at the back" (Joost, 25 Oct): only the name the player reads; the prefab and the
    // config section keep the title.
    static Kind Shown(string name, Kind k) { k.Shown = name; return k; }

    static Kind Never(HashSet<string> refused, string why, Kind k) { k.Never = refused; k.NeverWhy = why; return k; }

    static Kind Shelf(int planks, string recipe) =>
        Store("emergencyshelf", $"Shelf ({planks} plank{(planks > 1 ? "s" : "")})",
            $"A 2 m wall shelf with {(planks == 1 ? "one plank" : planks == 2 ? "two planks" : "three planks")} for what you grab in a hurry. "
            + "Holds anything; only what fits on the planks shows. Hangs on a wall.", null,   // anything (Joost, 23 Oct: portal bottles beside the portal)
            null, null, 0, Placement.Wall, recipe, "piece_workbench", piece: planks.ToString(CultureInfo.InvariantCulture),
            display: true, planks: planks, rounds: new[] { "_r5", "_r4" });   // r5: z-fix

    // What the release build registers (Joost, 25 Oct 18:58). Everything 0.4.0 or earlier shipped always stays: a piece type missing
    // from a build deletes its placed pieces (rule 13). Then the next release's new stores. Dev builds keep everything.
    public static readonly HashSet<string> Released = new(StringComparer.Ordinal)
    {
        "meadrack", "larder", "meatrack", "rootbin", "orebin", "bunker", "bunkeropen", "metalrack", "metalrackhalf", "metalracklow",
        "metalracklowhalf", "metalpallet", "coopersrow", "coopersrowstack", "fletcher", "treasure", "apothecary", "hiderack", "clothrack",
        "ossuary", "emergencyshelf",
    };
    public static readonly HashSet<string> NextRelease = new(StringComparer.Ordinal)
    {
        "armoryrail", "armoryrail3", "armoryisland", "armorstand", "weaponrack", "weaponrackb", "bolttubs", "bombcrate", "arrowtubes", "apothecarytall",
        "arsenalb",   // one Arsenal: B, whose shield section has the closed back (71% of it covered by the back panel, A 37%)
        "armoryb",    // Joost, 27 Oct, after testing it all evening: Armory B in the release and back in the hammer; Armory A stays out
        // Joost, 25 Oct: the ember cabinet, pantry, smith's drawers, jeweller and the two 65+ trophy halls (shown as "Trophy Hall"
        // and "Tall Trophy Hall") go in.
        "embercabinet", "pantry", "smithdrawers", "jeweller", "trophyhall13x5", "trophyhall10x7",
        // Joost, 27 Oct 16:3x: "Ja, de Arsenal kit gaat erin, alle vier de stukken" (Spine, Shield Trough, Long Rack, Bow Rack).
        "arsenalkit_spine", "arsenalkit_shield", "arsenalkit_long", "arsenalkit_bow",
        "armorstandopen",   // Joost, 27 Oct: both stands in the release, the open one beside the one with the back rail
        // Joost, 27 Oct: "for the armor cabinet and coffer we do need to fix the logic of how many slots it actually has, and also what
        // actually shows on the slots, like we do on the armor dummies": in, now that their window is their places (TypedSlots: a block
        // per kind of place with faded hints, piles by true height, refusals that name what is full).
        "armorcoffer", "armorcabinet",
        // Out: the first 80-place Trophy
        // Hall (never released, so no one on the server has one); the combined armories (armory, armoryb), the utility pieces
        // (utilitywall, utilityisland) and Arsenal A.
    };
    public static bool InRelease(Kind k) => k.Slug != null && (Released.Contains(k.Slug) || NextRelease.Contains(k.Slug));

    // The hammer and F1 by theme (Joost, 27 Oct: "the arrow tubes, the bolt crate, the bomb crate, and the Fletcher barrels grouped
    // together in the menu, and then the same for the other things, sort of thematically grouped"): these groups in this order, each
    // store in its place. A slug not in this build is skipped; a store in no group (the test-only ones) comes after them, in its
    // Stores order. All follows it: Jotunn fills the hammer tab in the order pieces register, and F1 lists sections as they bind.
    // (Must stand above All: static fields initialise in this order.)
    public static readonly (string Name, string[] Slugs)[] Groups =
    {
        ("Wood, ore and stone", new[] { "timbercrib", "orebin", "bunker", "bunkeropen" }),
        ("Metal", new[] { "metalrack", "metalrackhalf", "metalracklow", "metalracklowhalf", "metalpallet" }),
        ("Kitchen", new[] { "meadrack", "larder", "meatrack", "rootbin", "pantry" }),
        ("Crafting goods", new[] { "coopersrow", "coopersrowstack", "apothecary", "apothecarytall", "hiderack", "clothrack", "ossuary", "smithdrawers", "embercabinet" }),
        ("Ammunition", new[] { "fletcher", "arrowtubes", "bolttubs", "bombcrate" }),
        ("Weapons", new[] { "weaponrack", "weaponrackb", "arsenalb", "arsenalkit_spine", "arsenalkit_shield", "arsenalkit_long", "arsenalkit_bow" }),
        ("Armor", new[] { "armoryrail", "armoryrail3", "armoryisland", "armorstand", "armorstandopen", "armorcabinet", "armorcoffer", "armoryb" }),
        ("Trophies", new[] { "trophyhall13x5", "trophyhall10x7" }),
        ("Valuables", new[] { "treasure", "jeweller" }),
        ("Shelves", new[] { "emergencyshelf" }),
    };
    static string GroupSlug(Kind k) => k == Crib ? "timbercrib" : k.Slug;
    public static string GroupOf(Kind k) => Groups.FirstOrDefault(g => Array.IndexOf(g.Slugs, GroupSlug(k)) >= 0).Name;   // null: test-only
    static int Rank(Kind k)
    {
        int i = 0;
        foreach (var g in Groups) foreach (var s in g.Slugs) { if (s == GroupSlug(k)) return i; i++; }
        return int.MaxValue;   // OrderBy is stable: the rest keep their Stores order
    }
#if RELEASE
    public static readonly Kind[] All = new[] { Crib }.Concat(Stores.Where(InRelease)).OrderBy(Rank).ToArray();
#else
    // Dev build: the crib and the stores. Strongbox and the kitbash Ore Bin stay parked.
    public static readonly Kind[] All = new[] { Crib }.Concat(Stores).OrderBy(Rank).ToArray();
#endif
#else
    // Strongbox and Ore Bin are parked (Joost, 22 Oct 2026): they are built from vanilla models; ours come first.
    public static readonly Kind[] All = { Crib };
#endif

    public static Kind ByToken(string token)
    {
        if (token == null || token.Length < 10 || token[0] != '$') return null;
        for (int i = 0; i < All.Length; i++) if (All[i].Token == token) return All[i];
        return null;
    }
}

static class Settings
{
    public static ConfigEntry<bool> DumpPrefabs, LiveModels, MatteFrames;
#if !RELEASE
    public static ConfigEntry<bool> ShowTestPieces;
#endif
    public static ConfigEntry<string> ModelFolder;
#if DEV
    public static ConfigEntry<bool> SkinChests;
    public static ConfigEntry<KeyboardShortcut> SkinKey;
    public static ConfigEntry<float> DisplaySize;
    public static ConfigEntry<int> SlotsPerPlank;
    public static ConfigEntry<bool> ShowContents, ContentsShadows, Instancing, PerfLog, PerfOverlay, ManyKindBoards, ContentsInShade, PlacementCheck;
    public static ConfigEntry<float> MannequinTurn;
    public static ConfigEntry<float> ContentsDistance;
    public static ConfigEntry<int> MaxTrisPerStack;
    public static ConfigEntry<float> FarContents;
#endif

    // ACCEPTS HISTORY BEGIN (accepts-history.py)
    // 62 shipped versions of Storehouse.cs read (7e9575c61 = 0.3.0 to 92ee67e82 = 0.4.0); per config section
    // the shipped defaults that differ from today's.
    internal static readonly Dictionary<string, string[]> PastAccepts = new()
    {
        ["2 - Timber Crib"] = new[] { "Wood,FineWood,RoundLog,ElderBark,YggdrasilWood,Blackwood,Frostwood,StorehouseBoard,Root,WrithanRoots,BarkaBranch", "Wood,FineWood,RoundLog,ElderBark,YggdrasilWood,Blackwood,Frostwood" },
        ["4 - Apothecary Rack"] = new[] { "Feathers,Needle,GreydwarfEye,GiantBloodSack,AskBladder,WolfFang,Carapace,WolfHairBundle,ElakingHairBundle,Chitin,CelestialFeather,MooseSinew,BjornPaw,WolfClaw,MorgenHeart,Bilebag,MorgenSinew,DragonTear,Mandible,SerpentScale,BonemawSerpentScale", "Feathers,Needle,GreydwarfEye,RoyalJelly,GiantBloodSack,Ectoplasm,AskBladder,WolfFang,Carapace,WolfHairBundle,ElakingHairBundle,Chitin,CelestialFeather,MooseSinew,BjornPaw,WolfClaw,MorgenHeart,Bilebag,SurtlingCore,MorgenSinew,DragonTear,Mandible,SerpentScale,BonemawSerpentScale" },
        ["4 - Cloth Rack"] = new[] { "LinenThread,JuteRed,JuteBlue,NornThread" },
        ["4 - Coal & Stone Bunker"] = new[] { "Coal,Stone,Flint,Grausten,BlackMarble,Obsidian,SulfurStone,StoneRock,PungentPebbles,BFP_Clay,Ice", "Coal,Stone,Flint,Grausten,BlackMarble,Obsidian,Crystal,SulfurStone,StoneRock,PungentPebbles,Thunderstone,BFP_Clay,FrozenFuel,Ice", "Coal,Stone,Flint,Grausten,BlackMarble,Obsidian,Crystal" },
        ["4 - Coopers Row"] = new[] { "Tar,Resin,Sap,Guck,Eitr,Ooze,RoyalJelly,Honey,CharcoalResin,OozeMork,HatefulBlood,Voidplasm,BlobVial,Ectoplasm", "Tar,Resin,Sap,Guck,Eitr,Ooze" },
        ["4 - Ember Cabinet"] = new[] { "Wisp,GlowWorm,FaderEmber,MemorialCoal,MoltenCore,BlackCore,FrostCore,ShieldCore,OrbFrostFire,OrbThunderBlood,SurtlingCore,FrozenFuel,Thunderstone,Crystal", "Wisp,GlowWorm,FaderEmber,MemorialCoal,MoltenCore,BlackCore,FrostCore,ShieldCore,OrbFrostFire,OrbThunderBlood,SurtlingCore,FrozenFuel,Thunderstone", "Wisp,GlowWorm,FaderEmber,MemorialCoal,MoltenCore,BlackCore,FrostCore,ShieldCore,OrbFrostFire,OrbThunderBlood,SurtlingCore" },
        ["4 - Fletchers Barrels"] = new[] { "Arrow*,Bolt*,Bomb*,Dynamite" },
        ["4 - Jewellers Casket"] = new[] { "Coins,Amber,Ruby,AmberPearl,GemstoneBlue,GemstoneGreen,GemstoneRed,AncientGemstone*,AncientCoin,SilverNecklace,CrownJewel,Pot_Shard*" },
        ["4 - Mead Rack"] = new[] { "BarleyWine,MeadBase*" },
        ["4 - Open Coal & Stone Bunker"] = new[] { "Coal,Stone,Flint,Grausten,BlackMarble,Obsidian,SulfurStone,StoneRock,PungentPebbles,BFP_Clay,Ice", "Coal,Stone,Flint,Grausten,BlackMarble,Obsidian,Crystal,SulfurStone,StoneRock,PungentPebbles,Thunderstone,BFP_Clay,FrozenFuel,Ice", "Coal,Stone,Flint,Grausten,BlackMarble,Obsidian,Crystal" },
        ["4 - Ossuary Bin"] = new[] { "BoneFragments,CharredBone,WitheredBone,Charredskull,HardAntler,AsksvinCarrionSkull,BonemawSerpentTooth" },
        ["4 - Produce Crates"] = new[] { "Turnip,Onion,Carrot,Barley,Flax,Thistle,Dandelion,Fiddleheadfern,*Seeds,Mushroom*,*berries,Raspberry,Cloudberry" },
        ["4 - Stacking Coopers Row"] = new[] { "Tar,Resin,Sap,Guck,Eitr,Ooze,RoyalJelly,Honey,CharcoalResin,OozeMork,HatefulBlood,Voidplasm,BlobVial,Ectoplasm", "Tar,Resin,Sap,Guck,Eitr,Ooze" },
        ["4 - Tall Apothecary Rack"] = new[] { "Feathers,Needle,GreydwarfEye,GiantBloodSack,AskBladder,WolfFang,Carapace,WolfHairBundle,ElakingHairBundle,Chitin,CelestialFeather,MooseSinew,BjornPaw,WolfClaw,MorgenHeart,Bilebag,MorgenSinew,DragonTear,Mandible,SerpentScale,BonemawSerpentScale" },
        ["4 - Treasure Hoard"] = new[] { "Coins,Amber,Ruby,AmberPearl" },
    };
    // ACCEPTS HISTORY END

    // Defaults that only test builds carried (0.5.x, never released), kept by hand: a value equal to one was never an admin's
    // choice either, so it moves on like a shipped default. Joost's test config has these (25 Oct).
    internal static readonly Dictionary<string, string[]> TestAccepts = new()
    {
        // The valuables split (Joost, 27 Oct): the Hoard's 0.5 coins-and-gems list and the Casket's with the ancient coin, both in his config.
        ["4 - Treasure Hoard"] = new[] { "Coins,Amber,Ruby,AmberPearl,GemstoneBlue,GemstoneGreen,GemstoneRed,AncientGemstone*,AncientCoin,SilverNecklace,CrownJewel,Pot_Shard*" },
        ["4 - Jewellers Casket"] = new[] { "Amber,Ruby,AmberPearl,GemstoneBlue,GemstoneGreen,GemstoneRed,AncientGemstone*,AncientCoin,SilverNecklace,CrownJewel,Pot_Shard*" },
        // Surtling cores belong in the Ember Cabinet only (Joost, 25 Oct 18:10); Ectoplasm in Cooper's Row (27 Oct: r10 has its vessel).
        ["4 - Apothecary Rack"] = new[] { "Feathers,Needle,GreydwarfEye,GiantBloodSack,Ectoplasm,AskBladder,WolfFang,Carapace,WolfHairBundle,ElakingHairBundle,Chitin,CelestialFeather,MooseSinew,BjornPaw,WolfClaw,MorgenHeart,Bilebag,SurtlingCore,MorgenSinew,DragonTear,Mandible,SerpentScale,BonemawSerpentScale", "Feathers,Needle,GreydwarfEye,GiantBloodSack,Ectoplasm,AskBladder,WolfFang,Carapace,WolfHairBundle,ElakingHairBundle,Chitin,CelestialFeather,MooseSinew,BjornPaw,WolfClaw,MorgenHeart,Bilebag,MorgenSinew,DragonTear,Mandible,SerpentScale,BonemawSerpentScale" },
        ["4 - Tall Apothecary Rack"] = new[] { "Feathers,Needle,GreydwarfEye,GiantBloodSack,Ectoplasm,AskBladder,WolfFang,Carapace,WolfHairBundle,ElakingHairBundle,Chitin,CelestialFeather,MooseSinew,BjornPaw,WolfClaw,MorgenHeart,Bilebag,SurtlingCore,MorgenSinew,DragonTear,Mandible,SerpentScale,BonemawSerpentScale", "Feathers,Needle,GreydwarfEye,GiantBloodSack,Ectoplasm,AskBladder,WolfFang,Carapace,WolfHairBundle,ElakingHairBundle,Chitin,CelestialFeather,MooseSinew,BjornPaw,WolfClaw,MorgenHeart,Bilebag,MorgenSinew,DragonTear,Mandible,SerpentScale,BonemawSerpentScale" },
    };

    // ROWS HISTORY BEGIN (rows-history.py)
    // 188 versions of Storehouse.cs read (every branch); per config section the default Rows that differ from today's.
    internal static readonly Dictionary<string, int[]> PastRows = new()
    {
        ["4 - Apothecary Rack"] = new[] { 4 },
        ["4 - Armory Island"] = new[] { 8 },
        ["4 - Armory Rail"] = new[] { 5, 8 },
        ["4 - Arsenal B"] = new[] { 8 },
        ["4 - Bomb Crate"] = new[] { 5 },
        ["4 - Coopers Row"] = new[] { 4 },
        ["4 - Fletchers Barrels"] = new[] { 4 },
        ["4 - Hide Rack"] = new[] { 4 },
        ["4 - Larder Hutch"] = new[] { 9 },
        ["4 - Meat Rack"] = new[] { 10 },
        ["4 - Ossuary Bin"] = new[] { 4 },
        ["4 - Short Armory Rail"] = new[] { 3 },
        ["4 - Treasure Hoard"] = new[] { 4 },
    };
    // ROWS HISTORY END

    // A stored Rows value that equals an earlier default was never anyone's choice either (the coordinator, 25 Oct: Joost's Bomb
    // Crate still had 5 rows, so its reserve never filled): raised to today's default. Lowered only for a store shrunk on purpose
    // (Shrunk: Arsenal B, 27 Oct, chest = places); a placed one keeps the rows its stacks lie in until they fit (Patches.KeepRows).
    // Other released stores are never lowered here (the coordinator: that is Joost's call). Any other value was an admin's and
    // stays, with a line in the log.
    static readonly HashSet<string> Shrunk = new(StringComparer.Ordinal) { "arsenalb" };
    static void MigrateRows(Kind k)
    {
        if (k.Rows == null || k.Rows.Value == k.DefaultRows) return;
        int have = k.Rows.Value;
        if (PastRows.TryGetValue(k.Section, out var past) && past.Contains(have))
        {
            if (k.DefaultRows > have || Shrunk.Contains(k.Slug))
            {
                k.Rows.Value = k.DefaultRows;
                Plugin.Log.LogInfo($"Storehouse: {k.Title} Rows {have} -> {k.DefaultRows}, the {Plugin.Version} default"
                    + (k.DefaultRows < have ? "; placed ones keep their rows until what they hold fits." : "."));
            }
            else Plugin.Log.LogWarning($"Storehouse: {k.Title} Rows kept at {have}: the {Plugin.Version} default {k.DefaultRows} is fewer, and fewer rows would hide what lies in the others.");
            return;
        }
        Plugin.Log.LogWarning($"Storehouse: {k.Title} Rows {have} was edited, kept. The {Plugin.Version} default is {k.DefaultRows}.");
    }

    // A stored Accepts value that is a default some release shipped was never anyone's choice: it becomes today's default (the
    // coordinator, 25 Oct: the 0.5 policy must reach Joost's test and the server without editing configs by hand). A value that
    // differs from every shipped default was edited by an admin and stays; the log says what today's default would change.
    static void MigrateAccepts(Kind k)
    {
        if (k.Accepts == null || k.DefaultAccepts == null) return;
        static HashSet<string> Names(string v) => new((v ?? "").Split(',').Select(x => x.Trim()).Where(x => x.Length > 0), StringComparer.OrdinalIgnoreCase);
        var have = Names(k.Accepts.Value);
        var want = Names(k.DefaultAccepts);
        if (have.SetEquals(want)) return;
        var past = (PastAccepts.TryGetValue(k.Section, out var shipped) ? shipped : new string[0])
            .Concat(TestAccepts.TryGetValue(k.Section, out var tested) ? tested : new string[0]).ToArray();
        if (past.Length == 0) past = null;
        if (past != null && past.Any(v => Names(v).SetEquals(have)))
        {
            k.Accepts.Value = k.DefaultAccepts;
            Plugin.Log.LogInfo($"Storehouse: {k.Title} Accepts updated to the {Plugin.Version} default.");
            return;
        }
        // An admin who only added to a shipped default, all of which today's default now takes too (the server's Cooper's Row: the
        // shipped six plus Royal Jelly, inside the 0.5.1 thirteen): nothing of theirs is lost, so it moves on as well.
        if (past != null && past.Any(v => Names(v).IsSubsetOf(have)) && have.IsSubsetOf(want))
        {
            k.Accepts.Value = k.DefaultAccepts;
            Plugin.Log.LogInfo($"Storehouse: {k.Title} Accepts updated to the {Plugin.Version} default, which keeps every name added to it.");
            return;
        }
        var add = want.Where(x => !have.Contains(x)).ToList();
        var drop = have.Where(x => !want.Contains(x)).ToList();
        Plugin.Log.LogWarning($"Storehouse: {k.Title} Accepts was edited, kept as it is. The {Plugin.Version} default would "
            + (add.Count > 0 ? $"add {string.Join(", ", add)}" : "add nothing") + (drop.Count > 0 ? $" and remove {string.Join(", ", drop)}" : "") + ".");
    }

    // Every entry binds through here. BepInEx throws on a key or section holding = newline tab backslash quotes [ ] and on a
    // default outside its range; one such throw once stopped the start before the pieces registered (25 Oct). Instead: an error
    // line, and the same setting at its default in a file kept in memory only, so no entry is ever null and nothing after it is
    // skipped. check-config-keys.py refuses such keys at build time; this is the runtime half.
    static ConfigFile fallback;
    internal static ConfigEntry<T> Safe<T>(this ConfigFile config, string section, string key, T value, ConfigDescription description = null)
    {
        try { description = InF1(section, key, description); }   // only how F1 shows it: never in the way of the binding
        catch (Exception e) { Plugin.Log.LogWarning($"Storehouse: '{section}' / '{key}' keeps its plain F1 look ({e.Message})."); }
        try { return config.Bind(section, key, value, description); }
        catch (Exception e)
        {
            Plugin.Log.LogError($"Storehouse: setting '{section}' / '{key}' could not be bound; it stays at its default {value} for this session ({e.Message}).");
            static string Clean(string s) => new string((s ?? "").Where(c => "=\n\t\\\"'[]".IndexOf(c) < 0).ToArray()).Trim() is { Length: > 0 } t ? t : "Setting";
            fallback ??= new ConfigFile(Path.Combine(BepInEx.Paths.CachePath ?? Path.GetTempPath(), "Storehouse.fallback.cfg"), false) { SaveOnConfigSet = false };
            return fallback.Bind(Clean(section), Clean(key), value, new ConfigDescription(description?.Description ?? ""));
        }
    }
    internal static ConfigEntry<T> Safe<T>(this ConfigFile config, string section, string key, T value, string description) =>
        config.Safe(section, key, value, new ConfigDescription(description));

    // What F1 shows (Joost, 27 Oct: "why are all these things numbered in the same way?"). The cfg keeps its "N - Title" sections, so
    // no one's settings move and the migrations, history tables and scripts still key on them; ConfigurationManager only shows each
    // entry under its theme group (Kinds.Groups) as "<store>: <setting>", or under its section without the number. Joost's
    // ConfigurationManager (shudnal's) lists categories in the order their first entry binds and entries by Order, highest first:
    // General binds first (BindGeneral), the stores in hammer order, then Skins and Debug. Its attributes go first among the tags
    // (it stops reading tags at the first one it doesn't know).
    static int bound;
    static readonly Dictionary<string, string> F1Names = new(StringComparer.Ordinal) { ["Performance (dev)"] = "General", ["Shelf"] = "Shelves" };
    static ConfigDescription InF1(string section, string key, ConfigDescription description)
    {
        var kind = Kinds.All.FirstOrDefault(k => k.Section == section);
        string plain = System.Text.RegularExpressions.Regex.Replace(section ?? "", @"^\d+ - ", "");
#if DEV
        string group = kind != null ? Kinds.GroupOf(kind) ?? "Test pieces (dev)" : null;
#else
        string group = kind != null ? "Wood, ore and stone" : null;   // the crib is the only store
#endif
        string category = group
            ?? (key == "Display item size" ? "General"   // every display store's items: a general look, though it sits under Skins in the cfg
            : F1Names.TryGetValue(plain, out var named) ? named : plain);
        // The two Cooper's Rows read alike in F1 (Joost, 27 Oct: the ground row's glass changed in the stacking row's entry).
        string store = kind?.Slug == "coopersrow" ? (key is "Item size" or "Glass colour" ? "Cooper's Rows (both)" : "Cooper's Row (ground)")
            : kind?.Slug == "apothecary" && key is "Item size" or "Glass colour" ? "Apothecary Racks (both)"
            : kind != null ? kind.Shown ?? kind.Title : plain == "Shelf" ? "Shelf" : null;
        var tags = description?.Tags ?? new object[0];
        var shown = tags.OfType<ConfigurationManagerAttributes>().FirstOrDefault() ?? new ConfigurationManagerAttributes();
        shown.Category = category;
        shown.Order = -++bound;
        if (store != null) shown.DispName = $"{store}: {key}";
        return new ConfigDescription(description?.Description ?? "", description?.AcceptableValues,
            new object[] { shown }.Concat(tags.Where(t => t != shown)).ToArray());
    }

    // The pieces that take another's look settings (Item size, Glass colour): the stacking Cooper's Row and the tall Apothecary Rack.
    static readonly Dictionary<string, string> LookOf = new(StringComparer.Ordinal) { ["coopersrowstack"] = "coopersrow", ["apothecarytall"] = "apothecary" };

    public static void Bind(ConfigFile config)
    {
#if DEV
        BindGeneral(config);   // first: F1 lists its categories in the order they bind (InF1)
#endif
        foreach (var k in Kinds.All)
        {
            // An armory's rows are its figures (Joost, 18:08): no setting, so a saved value from an earlier build can't change them.
            // Nor a store with typed places: its window is its places (TypedSlots, Joost 27 Oct), whatever an earlier build saved.
            if (k.Planks == 0 && !Mannequins.Is(k) && !TypedSlots.Is(k)) k.Rows = config.Safe(k.Section, "Rows", k.DefaultRows, new ConfigDescription(
                "Rows of 8 slots. The chest UI scrolls past 4 rows. Applies to chests that load after the change. "
                + "Lowering it hides items in the removed rows (the game keeps them, out of reach) until the rows come back: empty them first.",
                new AcceptableValueRange<int>(Kinds.MinRows, 16), Synced()));
            try { MigrateRows(k); }
            catch (Exception e) { Plugin.Log.LogError($"Storehouse: {k.Title} Rows not migrated, kept as it is ({e})."); }
            // Joost, 27 Oct: the two Cooper's Rows share their look ("it makes sense to me that they share their settings, except the
            // stacking one costs more"), and so do the two Apothecary Racks: the stacking and tall ones use the ground and short ones'
            // Item size and Glass colour (bound first, Kinds.All being in hammer order). Their own entries from before stay in the cfg,
            // unread. Recipes, rows and models stay per piece.
            if (k.Slug != null && LookOf.TryGetValue(k.Slug, out var lookSlug) && Kinds.All.FirstOrDefault(x => x.Slug == lookSlug) is { ItemSize: not null } look)
            {
                k.ItemSize = look.ItemSize;
                k.GlassColour = look.GlassColour;
            }
            // Joost, 24 Oct: "you have to look closely to see what some things are"; per store, as each has its own items.
            else if (k.Planks == 0)
            {
                k.ItemSize = config.Safe(k.Section, "Item size", 1f, new ConfigDescription(
                    "Live: grows the item models inside this store by this factor, each about its own centre (1 = the layout's own size). "
                    + "Heaps may poke through walls above about 1.2. Only how it looks on your screen.", new AcceptableValueRange<float>(0.8f, 1.6f)));
                k.ItemSize.SettingChanged += (_, _) => { if (Plugin.Live) StoreModel.Touch(); };
            }
            // Joost, 27 Oct: Cooper's Row's clear glass "still kinda meh" white, and the colour his to set in game: the Pantry's
            // blue-green at 40% (the Apothecary Racks' since this morning) for both, a colour picker in F1, alpha the opacity.
            // Joost, 27 Oct evening: his own pick, 3E9F8A0D (a clear sea green, about 5% opaque), the default for all four.
            if (k.Slug is "coopersrow" or "apothecary")
            {
                var entry = k.GlassColour = config.Safe(k.Section, "Glass colour", Glass.Default, new ConfigDescription(
                    "Live: the colour of the glass (sight strips, jars), shared with the " + (k.Slug == "coopersrow" ? "Stacking Cooper's Row" : "Tall Apothecary Rack")
                    + "; alpha is how opaque it is (at least 4%). Only how it looks on your screen."));
                entry.SettingChanged += (_, _) =>
                {
                    if (!Plugin.Live) return;
                    foreach (var shared in Kinds.All.Where(x => x.GlassColour == entry)) StoreModel.Get(shared.Slug, shared.Piece, shared.Title).Retint(entry.Value);
                };
            }
            // Joost, 25 Oct: compare rounds in game (the Ossuary's bays against its broad heaps, the wide Bomb Crate against the
            // stepped one). Only the look on this PC; the inventory is the same in every round.
            if (k.Rounds is { Length: > 1 } && k.Slug != null && Kinds.ModelAlternates.TryGetValue(k.Slug, out var alternates))
            {
                k.Model = config.Safe(k.Section, "Model", "newest", new ConfigDescription(
                    $"Live (with Live models on): which model this store shows. newest = {k.Rounds[0].TrimStart('_')}. Only how it looks on your screen.",
                    new AcceptableValueList<string>(new[] { "newest", k.Rounds[0].TrimStart('_') }.Concat(alternates.Select(r => r.TrimStart('_'))).ToArray())));
                k.Model.SettingChanged += (_, _) => ModelWatch.Poke();
            }
            k.Recipe = config.Safe(k.Section, "Recipe", k.DefaultRecipe, new ConfigDescription(
                "Build cost: item prefab names with amounts, e.g. BlackMetal:12,Iron:8.", null, Synced()));
            k.Station = config.Safe(k.Section, "Crafting station", k.DefaultStation, new ConfigDescription(
                "Station prefab that must be nearby: piece_workbench, forge, piece_stonecutter, blackforge, piece_artisanstation, or empty for none.", null, Synced()));
            if (k.DefaultAccepts != null)
            {
                k.Accepts = config.Safe(k.Section, "Accepts", k.DefaultAccepts, new ConfigDescription(k.Rule == null
                    ? "Item prefab names this chest takes, comma separated. Anything else is refused. Items already inside always stay."
                    : $"Takes its own kind of item by type ({k.FilterLabel}), plus these item prefab names, comma separated; * stands for any letters "
                      + "(MeadBase* is every mead base). Anything else is refused. Items already inside always stay.", null, Synced()));
                try { MigrateAccepts(k); }
                catch (Exception e) { Plugin.Log.LogError($"Storehouse: {k.Title} Accepts not migrated, kept as it is ({e})."); }
                k.Filter = new Filter(k);
            }
        }
#if DEV
        SkinChests = config.Safe("8 - Skins (dev)", "Skin chests", true,
            "Dev, this PC only: look at a vanilla chest and press the hotkey to dress it as one of the Storehouse stores, with its real contents. "
            + "Only you see it; the chest itself, its size and the network stay vanilla. Off: every chest shows its own look again (choices are kept).");
        SkinKey = config.Safe("8 - Skins (dev)", "Hotkey", new KeyboardShortcut(KeyCode.K, KeyCode.LeftControl),
            "Cycles the skin of the chest you look at: none, then each store, then none again.");
        // Display furniture (larder, emergency shelf) shows one item per stack a bit under true size, so two stacks of the same
        // thing read as two copies (Joost, 22 Oct 2026). Mass storage keeps its layouts' own fit sizes.
        DisplaySize = config.Safe("8 - Skins (dev)", "Display item size", 0.7f, new ConfigDescription(
            "Dev, live: the size of the items in the display stores (Larder Hutch, Shelf) as a fraction of the item's true "
            + "in-game size (as it lies in the world when dropped). The shelf's planks have room for up to about 0.8; taller items "
            + "move on to a plank where they fit or are not shown. Mass stores (crib, racks, bins, bunker) keep their own fit.",
            new AcceptableValueRange<float>(0.3f, 1.2f)));
        DisplaySize.SettingChanged += (_, _) => { if (Plugin.Live) StoreModel.Touch(); };
        SlotsPerPlank = config.Safe("4 - Shelf", "Slots per plank", 6, new ConfigDescription(
            "Container slots per plank of the Shelf (1, 2 or 3 planks: 1, 2 or 3 rows of this many). 6 is what typically "
            + "fits on a 2 m plank at Display item size 0.7 (meads about 0.2 m, meals about 0.4 m across); a stack that does not fit "
            + "is not shown but stays in the chest. Applies to shelves that load after the change; lowering it hides the stacks in "
            + "the removed slots until it goes back up.",
            new AcceptableValueRange<int>(1, Kinds.Columns), Synced()));
#endif
        BindDebug(config);
    }

#if DEV
    // F1's General: the switches for how every store draws its contents.
    static void BindGeneral(ConfigFile config)
    {
        // Performance (Joost, 22 Oct 2026): what the stores' contents cost, and switches to A/B it in the same spot.
        const string perf = "7 - Performance (dev)";
        // A new key: the old "Mannequin turn" (180) was the wrong default and stays behind in configs; the facing now comes from the frame.
        MannequinTurn = config.Safe(perf, "Mannequin extra turn", 0f, new ConfigDescription(
            "Dev, live: extra degrees the worn sets turn on their forms. They face the frame's open side by themselves; 0 normally.",
            new AcceptableValueRange<float>(-180f, 180f)));
        MannequinTurn.SettingChanged += (_, _) => { if (Plugin.Live) StoreModel.Touch(); };
        ContentsInShade = config.Safe(perf, "Contents in the frames shade", false,   // no apostrophe: BepInEx refuses = newline tab backslash quotes [ ] in keys (check-config-keys.py)
            "Live: the items in a store take the shadows of its frame (a bunker's stacking top darkens its heaps). Off: they are lit "
            + "by the surroundings only, so what lies inside reads (Joost, 25 Oct: the bunker's coal and stone looked black).");
        ManyKindBoards = config.Safe(perf, "Boards between three or more kinds", true,
            "Live: a bay that holds three or more kinds side by side (a bunker with more kinds than bays) gets a board between each. "
            + "Off: those kinds lie as heaps side by side without boards; two kinds in a bay always keep their board.");
        ManyKindBoards.SettingChanged += (_, _) => { if (Plugin.Live) StoreModel.Touch(); };
        ShowContents = config.Safe(perf, "Show contents", true,
            "Dev, live: draw the item models inside the stores. Off: every store shows its frame only, so you can compare the FPS in the same spot.");
        ContentsDistance = config.Safe(perf, "Contents distance", 35f, new ConfigDescription(
            "Dev, live: a store's contents are drawn only while the camera is within this many metres of it; further away they cost "
            + "nothing per frame (and a store out of range rebuilds its contents only once you come near).",
            new AcceptableValueRange<float>(5f, 150f)));
        // Joost, 24 Oct: "make the feast models, and all models, lighter". The game's own item meshes can be heavy (a Feast platter is
        // up to 14k triangles); a stack of such an item shows fewer copies instead of piling up hundreds of thousands.
        MaxTrisPerStack = config.Safe(perf, "Max triangles per stack", 6000, new ConfigDescription(
            "Live: a stack shows at most this many triangles of item copies (always at least one copy). Light items (ore, arrows, "
            + "bones) are not affected; heavy ones (Feast platters, trophies of big bosses) show fewer copies. 0 = no limit.",
            new AcceptableValueRange<int>(0, 50000)));
        MaxTrisPerStack.SettingChanged += (_, _) => { if (Plugin.Live) StoreModel.Touch(); };
        FarContents = config.Safe(perf, "Far contents beyond", 12f, new ConfigDescription(
            "Live: beyond this many metres a store draws its items with the game's own lighter far models (their last LOD), "
            + "where an item has one. 0 = always the full models.", new AcceptableValueRange<float>(0f, 100f)));
        ContentsShadows = config.Safe(perf, "Contents cast shadows", false,
            "Dev, live: the item models in the stores cast shadows. Hundreds of small casters are expensive (one extra draw per shadow "
            + "cascade); the frame keeps its own shadows either way.");
        Instancing = config.Safe(perf, "GPU instancing", true,
            "Dev, live: draw the copies of an item whose mesh can't be merged (not readable) with one instanced draw per mesh and "
            + "material, where the item's shader supports it. Off: one draw per copy. Turn off if copies of an item show up in one spot.");
#if RELEASE
        const bool perfLogDefault = false;
#else
        const bool perfLogDefault = true;
#endif
        PerfLog = config.Safe(perf, "Perf log", perfLogDefault,
            "Dev, live: every 10 s write one line to the BepInEx log: FPS (average and 1% low), stores in range and in view, item "
            + "copies drawn, draws issued by Storehouse, ms per frame spent in Storehouse code, and the last contents rebuild.");
        PerfOverlay = config.Safe(perf, "Perf overlay", false, "Dev, live: show the latest perf line on screen, top left.");
        // FEEDBACK-0.8 item 3 (the Spine's lag spike on every add): the typed stores ask their placement "and one more?" by replay.
        PlacementCheck = config.Safe(perf, "Placement self-check", false,
            "Dev, live: every answer a typed store's window and display get by replay (which slots show hints, whether a dropped item "
            + "shows, where each item is drawn) is also solved from scratch the 0.8.0 way, and any difference is logged as a warning "
            + "(Placement self-check: ...). Costs what 0.8.0 cost, the Spine's lag included: on only to check.");
    }
#endif

    static void BindDebug(ConfigFile config)
    {
#if !RELEASE
        // Joost, 27 Oct: the pieces outside the release (Utility Wall and Island, Arsenal A, Armory A and B, the first Trophy Hall) out
        // of his hammer for now. Their prefabs stay registered, so the ones standing in a world still load.
        ShowTestPieces = config.Safe("8 - Test pieces (dev)", "Show pieces not in the release", false,
            "Dev, live: list the pieces outside the release in the hammer too. Off: only the release pieces; the others already placed stay as they are.");
        ShowTestPieces.SettingChanged += (_, _) => { if (Plugin.Live) Plugin.HammerOrder(); };
#endif
        LiveModels = config.Safe("9 - Debug", "Live models", false,
            "Dev: check the model files once a second and swap a changed model into the running game (piece and placed ones).");
        ModelFolder = config.Safe("9 - Debug", "Model folder", "",
            "Dev: read the models from this folder (with a crib/ subfolder, and <store>_r3 or <store>_r2 subfolders for the dev stores) "
            + "instead of the mod's own assets, e.g. the Blender export folder.");
        MatteFrames = config.Safe("9 - Debug", "Matte frames", true,   // Joost, 25 Oct: "that seems to have fixed it"
            "Dev, live: every store's frame without gloss, specular, metal, wetness or noise (the default since 25 Oct: straw glints and dark patches). Off: as the wood chest's material, to compare.");
        MatteFrames.SettingChanged += (_, _) => { if (Plugin.Live) Atlas.Matte(MatteFrames.Value); };
        DumpPrefabs = config.Safe("9 - Debug", "Dump prefabs", true,
            "At game start, write the hierarchy, meshes, materials, colliders and LODs of the black metal chest and the three pieces to the BepInEx log.");
    }

    static ConfigurationManagerAttributes Synced() => new() { IsAdminOnly = true };

    public static List<(string item, int amount)> ParseRecipe(string s)
    {
        var list = new List<(string, int)>();
        foreach (var part in (s ?? "").Split(','))
        {
            var kv = part.Split(':');
            if (kv.Length != 2 || !int.TryParse(kv[1].Trim(), NumberStyles.Integer, CultureInfo.InvariantCulture, out int n) || n <= 0) continue;
            var name = kv[0].Trim();
            if (name.Length > 0) list.Add((name, n));
        }
        return list;
    }

    // After the server's settings arrive (or an admin changes one): recipe and station on the piece prefabs.
    public static void ApplyToPieces()
    {
        foreach (var k in Kinds.All)
        {
            k.Filter?.Invalidate();
            var go = PrefabManager.Instance?.GetPrefab(k.Prefab);
            var piece = go ? go.GetComponent<Piece>() : null;
            if (!piece) continue;
            var reqs = new List<Piece.Requirement>();
            bool ok = true;
            foreach (var (item, amount) in ParseRecipe(k.Recipe.Value))
            {
                var prefab = ObjectDB.instance ? ObjectDB.instance.GetItemPrefab(item) : PrefabManager.Instance.GetPrefab(item);
                var drop = prefab ? prefab.GetComponent<ItemDrop>() : null;
                if (!drop) { ok = false; Plugin.Log.LogWarning($"{k.Title}: recipe item '{item}' not found; keeping the previous recipe."); break; }
                reqs.Add(new Piece.Requirement { m_resItem = drop, m_amount = amount, m_recover = true });
            }
            if (ok && reqs.Count > 0) piece.m_resources = reqs.ToArray();
            var station = k.Station.Value?.Trim();
            if (string.IsNullOrEmpty(station)) piece.m_craftingStation = null;
            else
            {
                var st = ZNetScene.instance ? ZNetScene.instance.GetPrefab(station) : PrefabManager.Instance.GetPrefab(station);
                if (st && st.GetComponent<CraftingStation>() is { } cs) piece.m_craftingStation = cs;
                else Plugin.Log.LogWarning($"{k.Title}: crafting station '{station}' not found; keeping the previous one.");
            }
        }
    }
}

// REVIEW POLICY BEGIN
// Isolated review candidate, authored by Sol 6.1 / extra high. These pure
// category/handling decisions are tested independently of Unity and the game.
static class StorageReviewPolicy
{
    public const string PantryUncooked = "BakedPoteitrUncooked,FishAndBreadUncooked,HoneyGlazedChickenUncooked,KaleChipsUncooked,LoxPieUncooked,"
        + "MagicallyStuffedShroomUncooked,MeatPlatterUncooked,MisthareSupremeUncooked,OvenPancakeUncooked,PiquantPieUncooked,RoastedCrustPieUncooked,VikingCupcakeUncooked";
    public const string PantryDefaults = "SpiceForests,SpicePlains,SpiceMountains,SpiceOceans,SpiceMistlands,SpiceDeepNorth,SpiceAshlands,BarleyFlour,OatFlour,BreadDough,FragrantBundle,"
        + "FeastAshlands_Material,FeastBlackforest_Material,FeastDeepNorth_Material,FeastMeadows_Material,FeastMistlands_Material,FeastMountains_Material,FeastOceans_Material,FeastPlains_Material,FeastSwamps_Material,"
        + PantryUncooked;
    public const string CooperLegacy = "Tar,Resin,Sap,Guck,Eitr,Ooze,RoyalJelly";
    // 0.8.1 (Joost, 28 Oct): Refined Eitr is glowing orbs, so the Ember Cabinet's; Proustite powder, a lava blob drop, pours like the goo.
    public const string CooperDefaults = "Tar,Resin,Sap,Guck,Ooze,RoyalJelly,Honey,CharcoalResin,OozeMork,HatefulBlood,Voidplasm,BlobVial,Ectoplasm,ProustitePowder";
    // Every valuable either store takes by name: the Hoard's coins and the Casket's jewels.
    public const string ValuablesDefaults = "Coins,Amber,Ruby,AmberPearl,GemstoneBlue,GemstoneGreen,GemstoneRed,AncientGemstone*,AncientCoin,SilverNecklace,CrownJewel,Pot_Shard*";
    // Joost, 27 Oct: "Treasure Hoard wordt de goudberg (munten en goud), juwelen naar de Jeweller's Casket." The Hoard: the coins and the
    // gold bar by name, other gold by its rule (ItemRules.CoinOrGold). The Casket: the jewels, no coin (Coins in the Hoard's well, Joost,
    // 25 Oct; the ancient coin is a coin too).
    public const string TreasureDefaults = "Coins,AncientCoin,Gold";
    public const string JewellerDefaults = "Amber,Ruby,AmberPearl,GemstoneBlue,GemstoneGreen,GemstoneRed,AncientGemstone*,SilverNecklace,CrownJewel,Pot_Shard*";
    static readonly HashSet<string> uncookedFoods = new(PantryUncooked.Split(','), StringComparer.OrdinalIgnoreCase);
    static readonly HashSet<string> valuables = new(ValuablesDefaults.Split(',').Where(n => !n.Contains('*')), StringComparer.Ordinal);
    static readonly HashSet<string> wetParts = new(StringComparer.OrdinalIgnoreCase) { "entrails", "bloodclot", "giantbloodsack", "bloodbag", "freezegland" };

    // Old config files retain *Uncooked. Guard the accidental wildcard matches
    // before accepting a name, while keeping world loading/removal untouched.
    public static bool NonFoodUncooked(string prefab) => !string.IsNullOrEmpty(prefab)
        && prefab.EndsWith("Uncooked", StringComparison.OrdinalIgnoreCase) && !uncookedFoods.Contains(prefab);
    public static bool MeadProductName(string prefab) => !string.IsNullOrEmpty(prefab)
        && (prefab.Equals("BarleyWine", StringComparison.OrdinalIgnoreCase)
            || prefab.StartsWith("Mead", StringComparison.OrdinalIgnoreCase) && !prefab.StartsWith("MeadBase", StringComparison.OrdinalIgnoreCase));
    // The Brewer's Cabinet by type (fix list F5; Joost, 1 Nov: "take everything from the brewing casket"): whatever a Fermenter, the
    // game's or any mod's, takes in (a base) or gives out (the drink), whatever its item type or food values; and for drinks no
    // Fermenter makes (potions, other mods' meads), a consumable without food values named Mead* or BarleyWine.
    public static bool MeadProduct(bool consumable, bool food, bool fermenter, string prefab) => fermenter || consumable && !food && MeadProductName(prefab);
    public static bool CoinWellAllows(string store, bool coinHome, string prefab) => store != "treasure" || !coinHome || prefab == "Coins";
    public static bool ValuableName(string prefab) => prefab != null && (valuables.Contains(prefab)
        || prefab.StartsWith("AncientGemstone", StringComparison.Ordinal) || prefab.StartsWith("Pot_Shard", StringComparison.Ordinal));
    public static bool JewelName(string prefab) => ValuableName(prefab) && !CoinOrGoldName(prefab);
    // Named for coin or gold: the Hoard's half of the rule (the item's type is the other, ItemRules.CoinOrGold). Gold gear in the making
    // is the smith's, not treasure: the forge's blanks (*GoldUncooked) and moulds; nor the bloodgold catapult ammo, a key, or ore.
    static readonly string[] notTreasure = { "uncooked", "mold", "mould", "ammo" };
    public static bool CoinOrGoldName(string prefab) => !string.IsNullOrEmpty(prefab)
        && (prefab.IndexOf("coin", StringComparison.OrdinalIgnoreCase) >= 0 || prefab.IndexOf("gold", StringComparison.OrdinalIgnoreCase) >= 0)
        && !notTreasure.Any(w => prefab.IndexOf(w, StringComparison.OrdinalIgnoreCase) >= 0)
        && !prefab.EndsWith("Key", StringComparison.OrdinalIgnoreCase) && !prefab.EndsWith("Ore", StringComparison.OrdinalIgnoreCase);
    public static int UnrepresentedKinds(IReadOnlyList<string> types, IReadOnlyList<int> places, int processed)
    {
        var all = new HashSet<string>(types, StringComparer.Ordinal);
        for (int i = 0; i < Math.Min(types.Count, Math.Min(places.Count, processed)); i++)
            if (places[i] >= 0) all.Remove(types[i]);
        return all.Count;
    }
    public static bool CanHangMeat(string prefab)
    {
        if (string.IsNullOrEmpty(prefab)) return false;
        if (prefab.IndexOf("egg", StringComparison.OrdinalIgnoreCase) >= 0) return false;
        string token = prefab.StartsWith("$item_", StringComparison.OrdinalIgnoreCase) ? prefab.Substring(6) : prefab;
        return !wetParts.Contains(token.Replace("_", ""));
    }
}
// REVIEW POLICY END

// Which items a filtered container takes. Resolved against ObjectDB lazily, so it follows config changes and world loads.
sealed class Filter
{
    readonly Kind kind;
    readonly HashSet<string> prefabs = new(StringComparer.Ordinal), shared = new(StringComparer.Ordinal);
    readonly List<System.Text.RegularExpressions.Regex> patterns = new();   // list entries with a *, matched on the prefab name
    string resolvedFrom;
    ObjectDB resolvedFor;
    float nextMessage;

    public Filter(Kind kind) { this.kind = kind; }
    public string Label => kind.FilterLabel;

    // Joost, 25 Oct: "this bunker is a bunker because it is so big. And only three items fit, because there are only three bays.
    // If you want to store more, you build another bunker." Each bay holds one kind; a kind that fills its bay (its share of the
    // slots) takes another; a new kind only goes in while a bay is free. What is inside already always stays (a chest over the
    // limit from before shows as it did, with boards).
    static readonly HashSet<string> oneKindPerBay = new(StringComparer.Ordinal) { "bunker", "bunkeropen", "orebin", "jeweller" };   // the Jeweller's trays too (Joost: "be consistent")
    public bool KindPerBay => kind.Slug != null && oneKindPerBay.Contains(kind.Slug);
    int Bays => KindPerBay ? StoreModel.BaysOf(kind.Slug, kind.Piece) : 0;
    static string KindOf(ItemDrop.ItemData it) => it.m_dropPrefab ? it.m_dropPrefab.name : it.m_shared.m_name;

    // (bays in use, bays): each kind present needs a bay per bay's worth of slots it fills.
    public (int used, int bays) BayUse(Inventory inv) => BayUse(inv, null, null);
    // The same with one stack less (gone) and one stack more of a kind (added): what the bays would be after an add.
    (int used, int bays) BayUse(Inventory inv, ItemDrop.ItemData gone, string added)
    {
        int bays = Bays;
        if (bays <= 0 || inv == null) return (0, 0);
        float perBay = inv.GetWidth() * inv.GetHeight() / (float)bays;
        var kinds = inv.GetAllItems().Where(i => i?.m_shared != null && i != gone).Select(KindOf);
        if (added != null) kinds = kinds.Append(added);
        int used = kinds.GroupBy(n => n).Sum(g => Mathf.Max(1, Mathf.CeilToInt(g.Count() / perBay)));
        return (used, bays);
    }

    // Would this add put a new stack in the inventory, and which stack would it take out (a swap)? A merge into a stack of the same
    // item with room adds none. at: the cell the private AddItem and a drop aim at (it merges there or nowhere); without it the
    // game's AddItem fills free room in the same item's stacks first and starts a stack with the rest. A whole stack moved inside
    // the inventory is no new stack; part of one is.
    static bool NewStack(Inventory inv, ItemDrop.ItemData item, int amount, Vector2i? at, out ItemDrop.ItemData gone)
    {
        gone = null;
        amount = amount > 0 ? Mathf.Min(amount, item.m_stack) : item.m_stack;
        if (inv.ContainsItem(item) && amount >= item.m_stack) return false;
        if (at is { } cell)
        {
            if (cell.x < 0 || cell.y < 0 || cell.x >= inv.GetWidth() || cell.y >= inv.GetHeight()) return false;   // the game refuses it
            var there = inv.GetItemAt(cell.x, cell.y);
            if (there == null || there == item) return there == null;
            // InventoryGrid.DropItem swaps a different item out (its own test); anything else merges or is refused by the game.
            if ((there.m_shared.m_name != item.m_shared.m_name || (item.m_shared.m_maxQuality > 1 && there.m_quality != item.m_quality) || there.m_shared.m_maxStackSize == 1) && item.m_stack == amount)
            {
                gone = there;
                return true;
            }
            return false;
        }
        if (item.m_shared.m_maxStackSize <= 1) return true;
        int room = inv.GetAllItems().Where(i => i != null && i != item && i.m_shared.m_name == item.m_shared.m_name && i.m_quality == item.m_quality && i.m_worldLevel == item.m_worldLevel)
            .Sum(i => Mathf.Max(0, i.m_shared.m_maxStackSize - i.m_stack));
        return room < amount;
    }

    // The item may go into this inventory: the filter, and in a bay store the bays a new stack needs. amount and at as NewStack.
    public bool AllowsIn(Inventory inv, ItemDrop.ItemData item, out string why, int amount = -1, Vector2i? at = null)
    {
        why = null;
        if (!Allows(item)) return false;
        if (Mannequins.Is(kind) && inv != null) return Mannequins.AllowsIn(inv, item, out why);
        if (inv != null && EquipFit.Refuses(kind, inv, item, out why)) return false;
        if (!KindPerBay || inv == null || item?.m_shared == null) return true;
        // Joost, 27 Oct, in game: the Jeweller's Casket read "Bays: 25/13". A kind already in the store used to take any stack, and a
        // kind past its bay's share of the slots needs another bay. Now one rule for every bay store: a new stack, of a new kind or
        // one already there, goes in only while the bays it needs are free. A chest over the limit from before keeps everything and
        // takes nothing that needs another bay; a merge into a stack with room needs no bay.
        if (!NewStack(inv, item, amount, at, out var gone)) return true;
        var (used, bays) = BayUse(inv);
        int after = BayUse(inv, gone, KindOf(item)).used;
        if (bays <= 0 || after <= bays || after <= used) return true;
        why = $"No free bay for {Name(item)}: build another {kind.Shown ?? kind.Title}.";
        return false;
    }

    public void Invalidate() => resolvedFrom = null;

    public bool Allows(ItemDrop.ItemData item)
    {
        if (item?.m_shared == null) return true;
        if (kind.Never != null && item.m_dropPrefab && kind.Never.Contains(item.m_dropPrefab.name)) return false;
#if DEV
        if (kind.Slug == "pantry" && StorageReviewPolicy.NonFoodUncooked(item.m_dropPrefab ? item.m_dropPrefab.name : item.m_shared.m_name)) return false;
#endif
        Resolve();
        if (shared.Contains(item.m_shared.m_name)) return true;
        var drop = item.m_dropPrefab;
        if (drop && prefabs.Contains(drop.name)) return true;
        if (drop && patterns.Count > 0) foreach (var p in patterns) if (p.IsMatch(drop.name)) return true;
        return kind.Rule != null && kind.Rule(item);
    }

    void Resolve()
    {
        var list = kind.Accepts.Value ?? "";
        var db = ObjectDB.instance;
        if (list == resolvedFrom && db == resolvedFor) return;
        resolvedFrom = list;
        resolvedFor = db;
        prefabs.Clear();
        shared.Clear();
        patterns.Clear();
        var found = new List<string>();
        var missing = new List<string>();
        foreach (var raw in list.Split(','))
        {
            var name = raw.Trim();
            if (name.Length == 0) continue;
            if (name.Contains('*'))
            {
                patterns.Add(new System.Text.RegularExpressions.Regex("^" + System.Text.RegularExpressions.Regex.Escape(name).Replace("\\*", ".*") + "$"));
                found.Add(name);
                continue;
            }
            var go = db ? db.GetItemPrefab(name) : null;
            // Not under that exact prefab name (Joost: the blood clot was skipped): the same name in another case, or the item
            // whose own name token is $item_<name>.
            if (!go && db)
            {
                string token = "$item_" + name.ToLowerInvariant();
                go = db.m_items.FirstOrDefault(p => p && (string.Equals(p.name, name, StringComparison.OrdinalIgnoreCase)
                    || p.GetComponent<ItemDrop>()?.m_itemData?.m_shared?.m_name == token));
            }
            prefabs.Add(go ? go.name : name);
            var drop = go ? go.GetComponent<ItemDrop>() : null;
            if (drop?.m_itemData?.m_shared != null)
            {
                shared.Add(drop.m_itemData.m_shared.m_name);
                found.Add($"{name} ({drop.m_itemData.m_shared.m_name})");
            }
            else missing.Add(name);
        }
        if (!db) return;   // main menu: try again in the world, quietly
        Plugin.Log.LogInfo($"{kind.Title} takes {(kind.Rule != null ? $"by type ({Label}), plus " : "")}{found.Count} item(s): {string.Join(", ", found)}");
        if (missing.Count > 0) Plugin.Log.LogInfo($"{kind.Title}: not in this game, skipped: {string.Join(", ", missing)}");
    }

    // A short centre message for the local player; the same one at most every 1.5 s (drag, ctrl-click and stack-all fire in bursts),
    // a different one always (Joost, 27 Oct: a refused shield showed nothing, a second try within 1.5 s of an earlier refusal was
    // swallowed). The one held back is still on screen: Notice fades over 4 s.
    public void Refuse(ItemDrop.ItemData item, string why = null)
    {
        if (!Player.m_localPlayer) return;
        string text = why ?? WhereItGoes(item, Name(item));
        if (text == lastMessage && Time.time < nextMessage) return;
        lastMessage = text;
        nextMessage = Time.time + 1.5f;
        Notice.Show(text);
    }
    string lastMessage;

    public static string Name(ItemDrop.ItemData item) => item?.m_shared != null ? Localization.instance.Localize(item.m_shared.m_name) : "That";

    // Instead of only "doesn't go in here": the stores whose own rules take it, the first two by name (the coordinator, 25 Oct).
    // Short (Joost, 27 Oct): what was refused, why, and where it goes instead; the player is looking at the store already.
    string WhereItGoes(ItemDrop.ItemData item, string what)
    {
        if (kind.Never != null && item?.m_dropPrefab && kind.Never.Contains(item.m_dropPrefab.name) && kind.NeverWhy != null)
            return $"{what}: {kind.NeverWhy}.";
        if (kind.Slug is "weaponrack" or "weaponrackb" && item?.m_shared != null && EquipRules.Handheld(item) && EquipRules.NotForRack(item, what) is { } notRack) return notRack;
        var homes = item?.m_shared == null ? new List<string>() : Kinds.All
            .Where(k => k != kind && k.Filter != null && k.Filter.Allows(item))
            .Select(k => k.Shown ?? k.Title).Distinct().OrderBy(n => n, StringComparer.Ordinal).Take(2).ToList();
        return homes.Count switch
        {
            0 => Label is { Length: > 0 } l ? $"{what} doesn't go here: {char.ToLowerInvariant(l[0])}{l.Substring(1)}." : $"{what} doesn't go here.",
            1 => $"{what} goes in the {homes[0]}.",
            _ => $"{what} goes in the {homes[0]} or the {homes[1]}.",
        };
    }

    public static Filter For(Inventory inv) => inv == null ? null : Kinds.ByToken(inv.GetName())?.Filter;
}

// The mod's messages on screen (refusals, skins): plain text like the game's centre message, no background (Joost, 27 Oct), at most
// a third of the screen wide and wrapped over as many lines as it needs (the game's one line ran across the screen). A copy of the
// game's centre text (font, outline), found again by name after a live reload; the game's own centre messages stay as they are.
// On a canvas of its own, drawn over everything (Joost, 27 Oct, f68: "I'm still not getting a message... maybe it's hidden under the
// HUD or the items"): a refusal comes while the inventory is open, and the HUD's canvas, where the game's centre text lives, lies
// under the inventory's. Same place on screen as the game's centre text, same scale as the HUD.
static class Notice
{
    const string Name = "storehouse_message";
    static TMPro.TMP_Text text;

    public static void Show(string message)
    {
        var player = Player.m_localPlayer;
        if (!player || Hud.IsUserHidden()) return;
        var hud = MessageHud.instance;
        if (!text && hud) text = Make(hud.m_messageCenterText);
        if (!text) { player.Message(MessageHud.MessageType.Center, message); return; }   // no copy to be had: the game's own
        var game = hud ? hud.m_messageCenterText : null;
        if (game && game.canvas && text.canvas)
        {
            text.canvas.scaleFactor = game.canvas.rootCanvas.scaleFactor;   // the HUD's UI scale
            text.rectTransform.position = game.rectTransform.position;      // overlay canvases: both in screen pixels
        }
        var root = text.canvas ? text.canvas.rootCanvas.transform as RectTransform : null;
        text.rectTransform.SetSizeWithCurrentAnchors(RectTransform.Axis.Horizontal, (root ? root.rect.width : Screen.width) / 3f);
        text.text = Localization.instance.Localize(message);
        if (hud && hud.m_messageCenterText) hud.m_messageCenterText.CrossFadeAlpha(0f, 0f, true);   // one centre message at a time
        text.canvasRenderer.SetAlpha(1f);
        text.CrossFadeAlpha(0f, 4f, true);                      // the game's centre message fades the same way
    }

    static TMPro.TMP_Text Make(TMPro.TMP_Text game)
    {
        if (!game) return null;
        var layer = GameObject.Find(Name + "_canvas");
        if (!layer)
        {
            layer = new GameObject(Name + "_canvas");
            var canvas = layer.AddComponent<Canvas>();
            canvas.renderMode = RenderMode.ScreenSpaceOverlay;
            canvas.sortingOrder = 32000;   // over the HUD, the inventory and its dragged item
        }
        var parent = layer.transform;
        var go = parent.Find(Name)?.gameObject;
        if (!go)
        {
            go = UnityEngine.Object.Instantiate(game.gameObject, parent);
            go.name = Name;
            var rt = (RectTransform)go.transform;
            rt.anchorMin = rt.anchorMax = rt.pivot = new Vector2(0.5f, 0.5f);
            foreach (Transform child in go.transform)   // the text only, nothing hung under it (TMP's own glyph meshes stay)
                if (!child.GetComponent<TMPro.TMP_SubMeshUI>()) UnityEngine.Object.Destroy(child.gameObject);
            foreach (var fit in go.GetComponents<ContentSizeFitter>()) UnityEngine.Object.Destroy(fit);   // it would undo the width
        }
        var t = go.GetComponent<TMPro.TMP_Text>();
        if (!t) return null;
        t.enableAutoSizing = false;   // narrower must wrap, not shrink
        t.fontSize = game.fontSize;
        t.textWrappingMode = TMPro.TextWrappingModes.Normal;
        t.overflowMode = TMPro.TextOverflowModes.Overflow;   // as many lines as it needs, around the same centre
        t.raycastTarget = false;
        t.canvasRenderer.SetAlpha(0f);
        return t;
    }
}

// Hauler's Strongbox: the black metal chest with our own meshes, or the vanilla chest scaled up when they are missing.
static class StrongboxModel
{
    static readonly Vector3 FallbackScale = new(2f, 1.6f, 2f);

    public static void Build(GameObject go, Container container)
    {
        string folder = Path.Combine(Plugin.Dir, "assets", "strongbox");
        var meta = LoadMeta(folder);
        bool flipX = Json.Bool(meta, "flip_x") ?? false;
        var body = ObjMesh.Load(Path.Combine(folder, "StrongboxBody.obj"), flipX);
        if (body == null)
        {
            go.transform.localScale = Vector3.Scale(go.transform.localScale, FallbackScale);
            Plugin.Log.LogWarning($"Hauler's Strongbox: no model at {folder}; using the vanilla black metal chest scaled x{FallbackScale.x} wide/deep, x{FallbackScale.y} high (colliders scale along).");
            return;
        }
        var lid = ObjMesh.Load(Path.Combine(folder, "StrongboxLid.obj"), flipX);
        var bodyLod = ObjMesh.Load(Path.Combine(folder, "StrongboxBodyLOD.obj"), flipX) ?? body;
        var lidLod = ObjMesh.Load(Path.Combine(folder, "StrongboxLidLOD.obj"), flipX) ?? lid;
        if (meta != null) Plugin.Log.LogInfo("Hauler's Strongbox: model metadata keys: " + string.Join(", ", meta.Keys));

        var open = container.m_open ? container.m_open.transform : null;
        var closed = container.m_closed ? container.m_closed.transform : null;
        var root = go.transform;
        var bounds = new Bounds();
        bool haveBounds = false;
        int swapped = 0;
        foreach (var mf in go.GetComponentsInChildren<MeshFilter>(true))
        {
            if (!mf.sharedMesh || !mf.GetComponent<MeshRenderer>()) continue;
            var t = mf.transform;
            string mesh = mf.sharedMesh.name.ToLowerInvariant();
            if (mesh.Contains("snow")) { Snow(t, meta, root); continue; }
            // Vanilla meshes: body "blackmetalchest", lids "blackmetalchesttop_closed" / "_open" (+ "LOD" variants)
            // under New/Closed and New/Open. Anything else on the prefab stays as it is.
            bool isLid = mesh.Contains("lid") || mesh.Contains("top");
            if (!isLid && !mesh.Contains("chest")) { Plugin.Log.LogInfo($"Hauler's Strongbox: left '{mf.sharedMesh.name}' on {Inspect.Path(t, root)} as it is."); continue; }
            bool underOpen = (open && t.IsChildOf(open)) || mesh.Contains("open") || t.name.ToLowerInvariant().Contains("open");
            bool isLod = mesh.Contains("lod");
            var m = isLid ? (isLod ? lidLod : lid) : (isLod ? bodyLod : body);
            if (m == null) { Plugin.Log.LogWarning($"Hauler's Strongbox: no replacement for mesh '{mf.sharedMesh.name}' on {Inspect.Path(t, root)}; kept vanilla."); continue; }
            Plugin.Log.LogInfo($"Hauler's Strongbox: {Inspect.Path(t, root)}: '{mf.sharedMesh.name}' -> '{m.name}'");
            mf.sharedMesh = m;
            swapped++;
            // The lid's open and closed poses (position + rotation under the body transform) come from the model's json,
            // since a bigger lid has its hinge further back and higher than the vanilla one.
            if (isLid)
            {
                var pose = Json.Obj(meta, underOpen ? "lid_transform_open" : "lid_transform_closed");
                if (pose != null)
                {
                    if (Json.Vec3(pose, "pos") is { } pos) t.localPosition = pos;
                    if (Json.Quat(pose, "rot") is { } rot) t.localRotation = rot;
                    if (Json.Vec3(pose, "scale") is { } sc) t.localScale = sc;
                }
            }
            if (!isLod && (!isLid || !underOpen))   // collider: body + closed lid
            {
                var b = Geometry.BoundsIn(root, t, m.bounds);
                if (haveBounds) bounds.Encapsulate(b); else { bounds = b; haveBounds = true; }
            }
        }
        Plugin.Log.LogInfo($"Hauler's Strongbox: model loaded ({body.vertexCount} body verts{(lid ? $", {lid.vertexCount} lid verts" : ", no lid mesh")}), {swapped} renderer(s) swapped.");
        foreach (var group in go.GetComponentsInChildren<LODGroup>(true)) group.RecalculateBounds();   // LOD switch distance follows the new size

        // Collider: the vanilla chest has one on a child named "collider". The model ships a box for it in that child's own
        // space (StrongboxCollider.obj); without it, one box is fitted around body and closed lid.
        var colMesh = ObjMesh.Load(Path.Combine(folder, "StrongboxCollider.obj"), flipX);
        var target = go.GetComponentsInChildren<Collider>(true).FirstOrDefault(c => !c.isTrigger && c.name.ToLowerInvariant().Contains("collider"));
        if (colMesh && target is MeshCollider mc)
        {
            mc.sharedMesh = colMesh;
            Plugin.Log.LogInfo($"Hauler's Strongbox: MeshCollider on {Inspect.Path(mc.transform, root)} now uses '{colMesh.name}' ({colMesh.bounds.size:F2} local).");
        }
        else if (colMesh && target is BoxCollider bc)
        {
            bc.center = colMesh.bounds.center;
            bc.size = colMesh.bounds.size;
            Plugin.Log.LogInfo($"Hauler's Strongbox: BoxCollider on {Inspect.Path(bc.transform, root)} set to {bc.size:F2} local.");
        }
        else if (haveBounds) Geometry.FitColliders(go, bounds, "Hauler's Strongbox");
    }

    // The vanilla chest carries a snow plane on its lid. Move it up to the bigger lid: from a "snow" {pos, scale} object in the
    // json if there is one, else from the "snow_hint" note ("... use about y=1.490, scale (1.35,1,0.78)").
    static void Snow(Transform t, Dictionary<string, object> meta, Transform root)
    {
        if (Json.Obj(meta, "snow") is { } snow)
        {
            if (Json.Vec3(snow, "pos") is { } p) t.localPosition = p;
            if (Json.Vec3(snow, "scale") is { } s) t.localScale = s;
        }
        else if (meta != null && meta.TryGetValue("snow_hint", out var h) && h is string hint)
        {
            var m = System.Text.RegularExpressions.Regex.Match(hint, @"use about y=([-0-9.]+), scale \(([-0-9.]+),([-0-9.]+),([-0-9.]+)\)");
            if (!m.Success) return;
            float F(int g) => float.Parse(m.Groups[g].Value, CultureInfo.InvariantCulture);
            t.localPosition = new Vector3(t.localPosition.x, F(1), t.localPosition.z);
            t.localScale = new Vector3(F(2), F(3), F(4));
        }
        else return;
        Plugin.Log.LogInfo($"Hauler's Strongbox: snow plane {Inspect.Path(t, root)} at {t.localPosition:F3}, scale {t.localScale:F3}.");
    }

    static Dictionary<string, object> LoadMeta(string folder)
    {
        if (!Directory.Exists(folder)) return null;
        var file = Path.Combine(folder, "strongbox.json");
        if (!File.Exists(file)) file = Directory.GetFiles(folder, "*.json").FirstOrDefault();
        if (file == null) return null;
        try { return Json.Parse(File.ReadAllText(file)) as Dictionary<string, object>; }
        catch (Exception e) { Plugin.Log.LogWarning($"Hauler's Strongbox: could not read {file}: {e.Message}"); return null; }
    }
}

// Timber Crib: our own model (blender/crib.py -> assets/crib/). The vanilla wood chest underneath gives Container, WearNTear
// and sounds; its look is hidden. Frame and logs use our 128 px atlas on a copy of the wood chest's material, so the game's
// piece shader still adds snow, rain and wear. CribLogs.obj holds one object per log in fill order (bottom row first);
// CribFill shows as many as the crib is full.
// Live models (dev): with "Live models" on, the model files are checked once a second (in "Model folder" if set, so a
// Blender export lands straight in the game); a change swaps the meshes and the atlas on the piece and on every crib
// in the world, without a restart.
static class CribModel
{
    internal static Mesh Frame, Logs;
    internal static int[] LogTris;        // all log triangles, log after log
    internal static int[] LogEnds;        // index count up to and including log i
    static Material mat;
    static Texture2D tex;
    static DateTime stamp;

    static string Dir => string.IsNullOrWhiteSpace(Settings.ModelFolder.Value)
        ? Path.Combine(Plugin.Dir, "assets", "crib")
        : Path.Combine(Settings.ModelFolder.Value.Trim(), "crib");
    internal static string[] Files => new[] { Path.Combine(Dir, "Crib.obj"), Path.Combine(Dir, "CribLogs.obj"), Path.Combine(Dir, "crib_atlas.png") };

    public static void Build(GameObject go, Container container)
    {
        mat = Atlas.Material(go, "storehouse_crib", "Timber Crib");
        if ((!mat && !Plugin.Headless) || !Load()) { Plugin.Log.LogError($"Timber Crib: model files missing in {Dir}; the crib stays a plain wood chest."); return; }
        Dress(go, quiet: false);
    }

    // The crib's look on a piece (the prefab, or during a live reload one standing in the world), from the loaded model.
    public static void Dress(GameObject go, bool quiet)
    {
        if ((!mat && !Plugin.Headless) || !Frame || LogEnds == null) return;
        var vis = Kitbash.Strip(go, "storehouse_crib");
        Part(vis, "frame", Frame);
        Part(vis, "logs", Logs);
        go.AddComponent<CribFill>();
        Kitbash.Finish(go, vis, Frame.bounds, WearNTear.MaterialType.Wood, 1200f, quiet, stackable: true);
        if (!quiet) Plugin.Log.LogInfo($"Timber Crib: own model from {Dir}, frame {Frame.triangles.Length / 3} + logs {LogTris.Length / 3} triangles, {LogEnds.Length} logs, {Frame.bounds.size:F2} m.");
    }

    // Read the three files into the statics. False (and nothing changed) when one is missing or half written.
    static bool Load()
    {
        var files = Files;
        if (!files.All(File.Exists)) return false;
        var ends = new List<int>();
        var frame = ObjMesh.Load(files[0], flipX: true);
        var logs = ObjMesh.Load(files[1], flipX: true, ends);
        byte[] png;
        try { png = File.ReadAllBytes(files[2]); } catch (IOException) { return false; }
        if (!frame || !logs || png.Length == 0) return false;
        if (mat)
        {
            if (!tex) tex = new Texture2D(2, 2, TextureFormat.RGBA32, true) { name = "storehouse_crib_atlas" };
            if (!ImageConversion.LoadImage(tex, png)) return false;
            tex.filterMode = FilterMode.Point;
            tex.wrapMode = TextureWrapMode.Repeat;
            mat.SetTexture("_MainTex", tex);
        }
        Frame = frame;
        Logs = logs;
        LogTris = logs.triangles;
        LogEnds = ends.ToArray();
        stamp = files.Max(File.GetLastWriteTimeUtc);
        return true;
    }

    // Called once a second while "Live models" is on.
    public static void CheckForChanges()
    {
        if (!mat || !Frame) return;
        var files = Files;
        if (!files.All(File.Exists) || files.Max(File.GetLastWriteTimeUtc) <= stamp) return;
        Mesh oldFrame = Frame, oldLogs = Logs;
        if (!Load()) return;                   // half written: try again next second
        int swapped = 0;
        var prefab = PrefabManager.Instance.GetPrefab(Kinds.Crib.Prefab);
        if (prefab) Apply(prefab);
        foreach (var fill in UnityEngine.Object.FindObjectsByType<CribFill>(FindObjectsInactive.Include, FindObjectsSortMode.None))
            if (fill.gameObject != prefab) { Apply(fill.gameObject); fill.Rebind(); swapped++; }
        UnityEngine.Object.Destroy(oldFrame);
        UnityEngine.Object.Destroy(oldLogs);
        Plugin.Log.LogInfo($"Timber Crib: model reloaded from {Dir} ({Frame.triangles.Length / 3} + {LogTris.Length / 3} triangles, {LogEnds.Length} logs), {swapped} crib(s) in the world updated.");
    }

    // On a crib piece the model hangs under "storehouse_crib" and the colliders follow it. On a skinned vanilla chest (dev)
    // CribFill sits on that child itself, and the chest keeps its own colliders.
    static void Apply(GameObject go)
    {
        var vis = go.name == "storehouse_crib" ? go.transform : go.transform.Find("storehouse_crib");
        if (!vis) return;
        if (vis.Find("frame")?.GetComponent<MeshFilter>() is { } frame) frame.sharedMesh = Frame;
        if (vis.Find("logs")?.GetComponent<MeshFilter>() is { } logs) logs.sharedMesh = Logs;
        if (vis != go.transform) Geometry.FitColliders(go, Frame.bounds, go.name);
        if (vis.GetComponent<LODGroup>() is { } lod) lod.RecalculateBounds();
    }

    internal static void Part(Transform parent, string name, Mesh mesh)
    {
        var go = new GameObject(name) { layer = parent.gameObject.layer };
        go.transform.SetParent(parent, false);
        go.AddComponent<MeshFilter>().sharedMesh = mesh;
        go.AddComponent<MeshRenderer>().sharedMaterial = mat;
    }

#if DEV
    // Skin mode: the crib's frame and logs on a vanilla chest, filled by that chest's own inventory. Null when the crib
    // model never loaded.
    internal static GameObject Skin(Transform root)
    {
        if (!mat || !Frame || LogEnds == null) return null;
        var vis = new GameObject("storehouse_crib") { layer = root.gameObject.layer }.transform;
        vis.SetParent(root, false);
        Part(vis, "frame", Frame);
        Part(vis, "logs", Logs);
        vis.gameObject.AddComponent<CribFill>();
        var group = vis.gameObject.AddComponent<LODGroup>();
        group.SetLODs(new[] { new LOD(0.03f, vis.GetComponentsInChildren<Renderer>(true)) });
        group.RecalculateBounds();
        return vis.gameObject;
    }

    // Live reload: this copy's material, atlas and meshes go with it.
    internal static void Release()
    {
        foreach (var o in new UnityEngine.Object[] { mat, tex, Frame, Logs }) if (o) UnityEngine.Object.Destroy(o);
        mat = null;
        tex = null;
        Frame = Logs = null;
        LogEnds = LogTris = null;
    }
#endif
}

// Rough see-through glass (A's SCHEMA.md, 25 Oct): the game's pieces have no glass, so a lit transparent shader from the build.
// The anchors' material gives the tint and opacity ("color_rgba"), or only an opacity ("alpha") over the glass tile of the
// store's atlas, plus roughness and specular. Without any transparent shader: the frame's own material, smoky and opaque (said
// once in the log), so the strips are never missing.
static class Glass
{
    static readonly string[] Shaders = { "Legacy Shaders/Transparent/Specular", "Legacy Shaders/Transparent/Diffuse", "Particles/Standard Surface", "Sprites/Diffuse" };
    static bool told;

    public static bool SeeThrough(Material m) => m && m.renderQueue >= 2500;

    // The Pantry Dresser's glass (the Apothecary Racks' jars, Joost, 27 Oct: bluish glass like the Pantry's, "yes"): the Pantry's glass
    // jars are opaque, drawn with the frame's material through the blue-green glass band of pantry_r4's atlas (mean 0.24, 0.33, 0.28
    // over its 300 glass faces). Here that colour itself, not lightened, at 40% opaque: still a jar you see into, yet as blue-green as
    // the Pantry's. Cooper's Row keeps its clear glass (at most 18%).
    public static readonly Color Pantry = new(0.24f, 0.33f, 0.28f, 0.40f);
    public static readonly Color Default = new(0x3E / 255f, 0x9F / 255f, 0x8A / 255f, 0x0D / 255f);   // Joost's pick in game, 27 Oct: 3E9F8A0D

    // A shader by name: Shader.Find only knows the shaders the build lists by name; the game's asset bundles load others (the
    // legacy transparent and cutout shaders, Standard), which only a search of the loaded shaders finds (25 Oct: the glass and the
    // mannequins' garments fell back to opaque for that reason).
    static readonly Dictionary<string, Shader> loaded = new(StringComparer.Ordinal);
    public static Shader Loaded(string name)
    {
        if (loaded.TryGetValue(name, out var sh) && sh) return sh;
        sh = Shader.Find(name);
        if (!sh) sh = Resources.FindObjectsOfTypeAll<Shader>().FirstOrDefault(x => x && x.name == name);
        if (sh) loaded[name] = sh;
        return sh;
    }

    public static Material Make(Dictionary<string, object> look, Texture atlas, Material frame, string name, string label, Color? tint = null)
    {
        static float? Num(Dictionary<string, object> d, string k) => d != null && d.TryGetValue(k, out var v) && v is double x ? (float)x : null;
        bool tinted = look != null && look.TryGetValue("color_rgba", out var co) && co is List<object> rgba && rgba.Count >= 4;
        var c = tinted ? new Color(Convert.ToSingle(((List<object>)look["color_rgba"])[0]), Convert.ToSingle(((List<object>)look["color_rgba"])[1]),
                Convert.ToSingle(((List<object>)look["color_rgba"])[2]), Convert.ToSingle(((List<object>)look["color_rgba"])[3]))
            : new Color(0.20f, 0.28f, 0.23f, Num(look, "alpha") ?? 0.25f);   // alpha only: the smoky tint of A's Cooper's glass
        float rough = Mathf.Clamp01(Num(look, "roughness") ?? 0.72f), spec = Mathf.Clamp01(Num(look, "specular") ?? 0.16f);
        // Clearer (Joost, 25 Oct 19:17: "why else put glass on it"): at most 18% opaque, the tint lightened halfway to white.
        c = tint ?? new Color(Mathf.Lerp(c.r, 1f, 0.5f), Mathf.Lerp(c.g, 1f, 0.5f), Mathf.Lerp(c.b, 1f, 0.5f), Mathf.Min(c.a, 0.18f));   // tint: the store's own, as it is
        var shader = Shaders.Select(Loaded).FirstOrDefault(sh => sh && sh.isSupported);
        if (!shader && Loaded("Standard") is { } standard && standard.isSupported)
        {
            // Unity's Standard shader, switched to its fade mode the way its own editor does it.
            var fade = new Material(standard) { name = name, renderQueue = 3000 };
            fade.SetFloat("_Mode", 2f);
            fade.SetInt("_SrcBlend", (int)UnityEngine.Rendering.BlendMode.SrcAlpha);
            fade.SetInt("_DstBlend", (int)UnityEngine.Rendering.BlendMode.OneMinusSrcAlpha);
            fade.SetInt("_ZWrite", 0);
            fade.DisableKeyword("_ALPHATEST_ON");
            fade.EnableKeyword("_ALPHABLEND_ON");
            fade.DisableKeyword("_ALPHAPREMULTIPLY_ON");
            fade.SetColor("_Color", c);
            if (fade.HasProperty("_Glossiness")) fade.SetFloat("_Glossiness", Mathf.Lerp(0.1f, 0.6f, 1f - rough));
            Plugin.Log.LogInfo($"{label}: glass on 'Standard' (fade), colour {c}.");
            return fade;
        }
        if (!shader)
        {
            if (!told)
            {
                var candidates = Resources.FindObjectsOfTypeAll<Shader>().Where(sh => sh && sh.isSupported).Select(sh => sh.name).Distinct().OrderBy(n => n).ToList();
                Plugin.Log.LogInfo($"{label}: shaders in this build ({candidates.Count}): {string.Join(", ", candidates)}");
            }
            if (!told) { told = true; Plugin.Log.LogWarning($"{label}: no transparent shader in this build ({string.Join(", ", Shaders)}); glass drawn opaque and smoky."); }
            var opaque = new Material(frame) { name = name + "_opaque" };
            if (opaque.HasProperty("_Color")) opaque.SetColor("_Color", tinted || tint != null ? Color.Lerp(Color.white, new Color(c.r, c.g, c.b), 0.5f) : new Color(0.75f, 0.8f, 0.78f));
            return opaque;
        }
        var m = new Material(shader) { name = name, renderQueue = 3000 };
        if (m.HasProperty("_MainTex")) m.SetTexture("_MainTex", Texture2D.whiteTexture);   // the colour is the glass; the atlas tile read milky
        if (m.HasProperty("_Color")) m.SetColor("_Color", c);
        if (m.HasProperty("_SpecColor")) m.SetColor("_SpecColor", new Color(spec, spec, spec, 1f));
        if (m.HasProperty("_Shininess")) m.SetFloat("_Shininess", Mathf.Lerp(0.03f, 1f, 1f - rough));   // rough glass: a broad, dull highlight
        Plugin.Log.LogInfo($"{label}: glass on '{shader.name}', colour {c}, roughness {rough:F2}" + (tint != null ? " (the store's own tint)" : tinted ? "" : " (alpha only: smoky tint)") + ".");
        return m;
    }
}

// Equipment stores show what they hold (Joost's bunker rule, 25 Oct: a store refuses what it can't show and says why). A piece goes
// in only when the store then shows one piece more than before (Allocate with and without it), so it never lies there unseen and
// never pushes a shown one out. And, once per session in dev builds, every one-handed weapon in the game against the weapon racks.
static class EquipFit
{
    public static Vector3? TrueSize(ItemDrop.ItemData it, Quaternion turn) => it?.m_dropPrefab && ItemVisual.Get(it.m_dropPrefab) is { } v
        ? StoreModel.Turned(turn, v.TrueSize) : null;

    // An equipment store refuses only what no arrangement of its places can show (TypedSlots.Cell says why, in the player's words).
    public static bool Refuses(Kind kind, Inventory inv, ItemDrop.ItemData item, out string why)
    {
        why = null;
        if (kind?.Slug == null || item?.m_shared == null || TypedSlots.Model(kind) is not { } model) return false;
        return TypedSlots.Cell(kind, model, inv, item, -1, -1, out why) < 0 && why != null;
    }

#if !RELEASE
    static bool reported;
    // Every one-handed weapon in ObjectDB (vanilla and mods) against Weapon Rack A and B: the best place and turn for each, and for
    // the misfits by how much and in which direction. Written once per session to BepInEx/cache/Storehouse-weaponrack-fit.md, the
    // first time ObjectDB holds one-handed weapons (an empty one, the main menu's before it is filled, waits for the next call).
    public static void Report()
    {
        if (reported || !ObjectDB.instance) return;
        var weapons = ObjectDB.instance.m_items.Where(p => p && p.GetComponent<ItemDrop>()?.m_itemData?.m_shared is { } sh && sh.m_itemType == ItemDrop.ItemData.ItemType.OneHandedWeapon)
            .GroupBy(p => p.name).Select(g => g.First()).OrderBy(p => p.name, StringComparer.Ordinal).ToList();
        if (weapons.Count == 0) return;
        reported = true;
        var sb = new StringBuilder($"# One-handed weapons vs the weapon racks ({Plugin.Version}, {DateTime.Now:yyyy-MM-dd HH:mm})\n\n"
            + "Fit as the game tests it (StoreModel.Excess: the place's clear box, else its box x1.25 + 2 cm and the ceiling), at the place's turn and the turns StoreModel.Turns allows. Sizes in metres, x y z in the rack's space.\n");
        foreach (var kind in Kinds.All.Where(k => k.Slug is "weaponrack" or "weaponrackb"))
        {
            if (StoreModel.Get(kind.Slug, kind.Piece, kind.Title) is not { Equip: not null } model) continue;
            var places = model.Equip.Where(pl => pl.Types.Contains("OneHandedWeapon")).ToList();
            var misfits = new List<string>();
            var refused = new List<string>();   // kept out by the racks' rule (EquipRules.NotForRack): not for sizing the places
            int fit = 0, skipped = 0;
            foreach (var prefab in weapons)
            {
                var item = prefab.GetComponent<ItemDrop>().m_itemData.Clone();
                item.m_dropPrefab = prefab;
                if (!EquipRules.Players(item) || EquipRules.IsBomb(item)) { skipped++; continue; }
                if (!EquipRules.RackWeapon(item)) { refused.Add(prefab.name); continue; }
                if (TrueSize(item, Quaternion.identity) is not { } own) { misfits.Add($"| {prefab.name} | no model | | | |"); continue; }
                float best = float.PositiveInfinity;
                Vector3 bestSize = own, bestBox = Vector3.zero;
                foreach (var pl in places)
                    foreach (var q in StoreModel.Turns(pl.Rot, false))
                        if (TrueSize(item, q) is { } d && StoreModel.Excess(pl, d, own) is var e && e < best) { best = e; bestSize = d; bestBox = pl.Clear ?? pl.Box * 1.25f + Vector3.one * 0.02f; }
                if (best <= 0f) { fit++; continue; }
                var over = new[] { ("x", bestSize.x - bestBox.x), ("y", bestSize.y - bestBox.y), ("z", bestSize.z - bestBox.z) }.Where(a => a.Item2 > 0f)
                    .Select(a => $"{a.Item1} +{a.Item2:F2}");
                misfits.Add($"| {prefab.name} | {Localization.instance.Localize(item.m_shared.m_name)} | ({bestSize.x:F2}, {bestSize.y:F2}, {bestSize.z:F2}) | ({bestBox.x:F2}, {bestBox.y:F2}, {bestBox.z:F2}) | {(over.Any() ? string.Join(", ", over) : $"ceiling +{best:F2}")} |");
            }
            sb.Append($"\n## {kind.Title} ({places.Count} one-handed places): {fit} fit, {misfits.Count} do not{(skipped > 0 ? $", {skipped} skipped (no icon or a bomb)" : "")}, {refused.Count} refused by the racks' rule\n\n");
            if (misfits.Count > 0) sb.Append("| Prefab | Name | Best true size | Its place allows | Over by |\n|---|---|---|---|---|\n" + string.Join("\n", misfits) + "\n");
            if (refused.Count > 0) sb.Append($"\nRefused, not sized here (spears: the Arsenal Long Rack; no damage; thrown): {string.Join(", ", refused)}\n");
        }
        var path = Path.Combine(BepInEx.Paths.CachePath, "Storehouse-weaponrack-fit.md");
        File.WriteAllText(path, sb.ToString());
        Plugin.Log.LogInfo($"Weapon rack fit: {weapons.Count} one-handed weapons tested, written to {path}.");
    }
#endif
}

// Arrows and bolts in their holders: which end is the head, and how deep each kind stands (Joost, 25 Oct 19:17: at least 30% of an
// arrow's length inside its tube, logged per kind).
static class Ammo
{
    static readonly Dictionary<string, Vector3?> heads = new(StringComparer.Ordinal);

    // The head in ItemVisual space: an arrow's projectile prefab flies along its own forward axis and draws the item's mesh, so that
    // mesh's axis toward the projectile's forward is the head. Null when the projectile shares no mesh with the item.
    public static Vector3? HeadOf(ItemVisual v)
    {
        if (v?.PrefabName == null) return null;
        if (heads.TryGetValue(v.PrefabName, out var h)) return h;
        h = null;
        var prefab = ObjectDB.instance ? ObjectDB.instance.GetItemPrefab(v.PrefabName) : null;
        var proj = prefab ? prefab.GetComponent<ItemDrop>()?.m_itemData?.m_shared?.m_attack?.m_attackProjectile : null;
        if (proj)
            foreach (var mf in proj.GetComponentsInChildren<MeshFilter>(true))
            {
                if (!mf.sharedMesh) continue;
                var part = v.Parts.FirstOrDefault(x => x.Mesh && (x.Mesh == mf.sharedMesh || x.Mesh.name == mf.sharedMesh.name));
                if (part == null) continue;
                h = part.M.MultiplyVector(mf.transform.InverseTransformDirection(proj.transform.forward)).normalized;
                break;
            }
        heads[v.PrefabName] = h;
        return h;
    }

#if !RELEASE
    // Per model and kind: copies, how many turned head up, and the buried share of the length, min and max, against the holder's rim
    // (the highest frame vertex within 8 cm of the unit's axis). Logged once per model and kind set.
    static readonly Dictionary<(string, string), (int n, int flipped, float min, float max, bool known)> seen = new();
    static readonly Dictionary<(StoreModel, int), float> rims = new();
    static readonly HashSet<string> told = new(StringComparer.Ordinal);
    public static void Note(StoreModel model, int unit, string kind, Bounds b, bool known, bool flipped)
    {
        int group = model.Units[unit].Group;
        float rim = Top(model, $"straw_u{unit}", $"straw_g{group}");
        if (float.IsNaN(rim) && !rims.TryGetValue((model, unit), out rim))
        {
            rim = float.NaN;
            var axis = model.Units[unit].Pos;
            if (model.Frame && model.Frame.isReadable)
                foreach (var v in model.Frame.vertices)
                    if (new Vector2(v.x - axis.x, v.z - axis.z).sqrMagnitude < 0.0064f && (float.IsNaN(rim) || v.y > rim)) rim = v.y;
            rims[(model, unit)] = rim;
        }
        Note(model, kind, b, rim, known, flipped);
    }
    // The straw top for a place: its own object, else the store's single "straw", else NaN.
    public static float Top(StoreModel model, params string[] names)
    {
        foreach (var n in names) if (model.StrawTops.TryGetValue(n, out var t)) return t;
        return model.StrawTops.TryGetValue("straw", out var all) ? all : float.NaN;
    }
    // Any copy against a straw (or rim) top: the share of its height below it.
    public static void Note(StoreModel model, string kind, Bounds b, float rim, bool known = true, bool flipped = false)
    {
        float buried = float.IsNaN(rim) || b.size.y <= 0f ? float.NaN : Mathf.Clamp01((rim - b.min.y) / b.size.y);
        var key = (model.Title, kind);
        seen.TryGetValue(key, out var e);
        e = (e.n + 1, e.flipped + (flipped ? 1 : 0), e.n == 0 ? buried : Mathf.Min(e.min, buried), e.n == 0 ? buried : Mathf.Max(e.max, buried), known);
        seen[key] = e;
    }
    // After a store's draw: one line per model with every kind seen so far.
    public static void Report(StoreModel model)
    {
        var mine = seen.Where(kv => kv.Key.Item1 == model.Title).OrderBy(kv => kv.Key.Item2, StringComparer.Ordinal).ToList();
        if (mine.Count == 0) return;
        string line = $"{model.Title}: standing in straw " + string.Join("; ", mine.Select(kv => $"{kv.Key.Item2} x{kv.Value.n} buried {kv.Value.min * 100:F0}-{kv.Value.max * 100:F0}%"
            + $"{(kv.Value.flipped > 0 ? ", turned head up" : "")}{(kv.Value.known ? "" : " (head from the old list)")}{(kv.Value.min < 0.3f ? " UNDER 30%" : "")}"));
        if (told.Add(line)) Plugin.Log.LogInfo(line);
    }
#endif
}

// Our atlas on the game's piece shader.
static class Atlas
{
    // The wood chest's own material (Custom/Piece) for our atlas, with its normal and metal maps taken out
    // (they belong to the chest's UV layout, not ours). The atlas goes in at load time.
    public static Material Material(GameObject go, string name, string label)
    {
        var src = go ? go.GetComponentsInChildren<MeshRenderer>(true).Select(r => r.sharedMaterial)
            .FirstOrDefault(m => m && m.HasProperty("_MainTex") && m.shader.name == "Custom/Piece" && !m.name.Contains("snow")) : null;
        if (!src) { if (!Plugin.Headless) Plugin.Log.LogWarning($"{label}: the wood chest has no material to copy."); return null; }
        var m = new UnityEngine.Material(src) { name = name };
        var cleared = new List<string>();
        // The emission map too (the coordinator, 25 Oct: white glints on single straw faces): the chest's glow, read at our UVs.
        foreach (var p in m.GetTexturePropertyNames())
            if (p != "_MainTex" && m.GetTexture(p) && (p.Contains("Bump") || p.Contains("Normal") || p.Contains("Metal") || p.Contains("Emission")))
            {
                m.SetTexture(p, null);
                cleared.Add(p);
            }
        m.DisableKeyword("_NORMALMAP");
        m.DisableKeyword("_EMISSION");
        if (m.HasProperty("_EmissionColor")) m.SetColor("_EmissionColor", Color.black);
        Plugin.Log.LogInfo($"{label}: material from '{src.name}' ({src.shader.name}), textures {string.Join(", ", m.GetTexturePropertyNames())}; cleared {string.Join(", ", cleared)}; "
            + $"keywords {string.Join("+", m.shaderKeywords)}; " + string.Join(", ", Gloss(m).Select(kv => $"{kv.Key} {kv.Value:F2}")));
        var keep = Gloss(m);
        made.Add((m, keep, m.HasProperty("_NoiseTex") ? m.GetTexture("_NoiseTex") : null));
        if (Settings.MatteFrames?.Value == true) Matte(m, keep, null, true);
        return m;
    }

    // A darker copy of a frame's material (the straw's shades and its entry rings, Joost via M, 27 Oct): its colour times k; it follows
    // the frames' matte A/B with the frame it was copied from.
    public static Material Shade(Material src, float k, string name)
    {
        var m = new UnityEngine.Material(src) { name = name };
        if (m.HasProperty("_Color")) { var c = src.GetColor("_Color"); m.SetColor("_Color", new Color(c.r * k, c.g * k, c.b * k, c.a)); }
        var e = made.FirstOrDefault(x => x.m == src);
        if (e.m) made.Add((m, e.gloss, e.noise));
        return m;
    }

    // A/B, live (the coordinator, 25 Oct: shiny straw, dark patches on straw beds): every frame's gloss, smoothness, metal and
    // specular to 0 and its noise texture off, or back as the chest had them.
    static readonly List<(Material m, Dictionary<string, float> gloss, Texture noise)> made = new();
    static Dictionary<string, float> Gloss(Material m)
    {
        var d = new Dictionary<string, float>();
        for (int i = 0; i < m.shader.GetPropertyCount(); i++)
        {
            var type = m.shader.GetPropertyType(i);
            string n = m.shader.GetPropertyName(i);
            if ((type == UnityEngine.Rendering.ShaderPropertyType.Float || type == UnityEngine.Rendering.ShaderPropertyType.Range)
                && (n.IndexOf("gloss", StringComparison.OrdinalIgnoreCase) >= 0 || n.IndexOf("smooth", StringComparison.OrdinalIgnoreCase) >= 0
                    || n.IndexOf("metal", StringComparison.OrdinalIgnoreCase) >= 0 || n.IndexOf("spec", StringComparison.OrdinalIgnoreCase) >= 0
                    || n.IndexOf("rain", StringComparison.OrdinalIgnoreCase) >= 0 || n.IndexOf("wet", StringComparison.OrdinalIgnoreCase) >= 0))
                d[n] = m.GetFloat(n);
        }
        return d;
    }
    static void Matte(Material m, Dictionary<string, float> gloss, Texture noise, bool on)
    {
        foreach (var kv in gloss) m.SetFloat(kv.Key, on ? 0f : kv.Value);
        if (m.HasProperty("_NoiseTex")) m.SetTexture("_NoiseTex", on ? null : noise);
    }
    public static void Matte(bool on)
    {
        made.RemoveAll(x => !x.m);
        foreach (var (m, gloss, noise) in made) Matte(m, gloss, noise, on);
        Plugin.Log.LogInfo($"Frames: {(on ? "matte" : "as the chest's material")} ({made.Count} material(s)).");
    }
}

// Shows the logs by how full the crib is: each slot counts as its stack over the item's max stack, so 64 full slots of
// wood is 100% and every log. Checked once a second, which also catches other players' changes (the game reloads a
// container's inventory from the world when it changes).
sealed class CribFill : MonoBehaviour
{
    Container container;
    MeshFilter filter;
    Mesh mesh;
    int shown = -1;
    float next;

    void Start()
    {
        container = GetComponentInChildren<Container>();
        if (!container) container = GetComponentInParent<Container>();      // dev skin: we sit on the chest's child
        filter = (transform.Find("storehouse_crib/logs") ?? transform.Find("logs"))?.GetComponent<MeshFilter>();
        if (!filter || CribModel.LogEnds == null) { enabled = false; return; }
        Rebind();
    }

    // Own copy of the logs mesh (each crib shows its own number of logs); again after a live model reload.
    public void Rebind()
    {
        if (!filter) return;
        if (mesh) Destroy(mesh);
        mesh = Instantiate(CribModel.Logs);
        filter.sharedMesh = mesh;
        shown = -1;
        next = 0f;
        Show(0);
    }

    void Update()
    {
        if (Time.time < next) return;
        next = Time.time + 1f;
        var inv = container ? container.GetInventory() : null;
        if (inv == null) return;
        float full = 0f;
        foreach (var item in inv.GetAllItems())
            full += item.m_shared.m_maxStackSize > 0 ? (float)item.m_stack / item.m_shared.m_maxStackSize : 1f;
        float fraction = Mathf.Clamp01(full / Mathf.Max(1, inv.GetWidth() * inv.GetHeight()));
        int count = CribModel.LogEnds.Length;
        // Any wood at all shows at least one log; the last log only when it's really full.
        Show(full > 0f ? Mathf.Clamp(Mathf.FloorToInt(fraction * count + 0.999f), 1, count) : 0);
    }

    void Show(int logs)
    {
        if (logs == shown || !mesh) return;
        shown = logs;
        int length = logs == 0 ? 0 : CribModel.LogEnds[Mathf.Min(logs, CribModel.LogEnds.Length) - 1];
        mesh.SetTriangles(CribModel.LogTris, 0, length, 0, false);
    }

    void OnDestroy()
    {
        if (mesh) Destroy(mesh);
    }
}

// Live models: the model folder is watched (FileSystemWatcher) instead of reading every model file's time once a second, which
// cost 6-10 ms a second and showed in the 1% low (Joost asked how we do on performance). The folder check runs only after the
// watcher saw a write, and once more 2 s later for a file still being written.
static class ModelWatch
{
    static FileSystemWatcher watcher;
    static string folder;
    static volatile bool dirty = true;
    static float again;

    public static void Poke() => dirty = true;   // look again now (a store's Model setting changed)

    public static bool Changed()
    {
        var want = string.IsNullOrWhiteSpace(Settings.ModelFolder.Value) ? Path.Combine(Plugin.Dir, "assets") : Settings.ModelFolder.Value.Trim();
        if (want != folder)
        {
            Stop();
            folder = want;
            dirty = true;
            if (Directory.Exists(folder))
                try
                {
                    watcher = new FileSystemWatcher(folder) { IncludeSubdirectories = true, NotifyFilter = NotifyFilters.LastWrite | NotifyFilters.FileName | NotifyFilters.Size };
                    watcher.Changed += (_, _) => dirty = true;
                    watcher.Created += (_, _) => dirty = true;
                    watcher.Renamed += (_, _) => dirty = true;
                    watcher.Deleted += (_, _) => dirty = true;
                    watcher.EnableRaisingEvents = true;
                }
                catch (Exception e) { Plugin.Log.LogWarning($"Live models: can't watch {folder} ({e.Message}); checking every second."); watcher = null; }
        }
        if (watcher == null) return true;   // no watcher: the old once-a-second check
        if (dirty) { dirty = false; again = Time.time + 2f; return true; }
        if (again > 0f && Time.time >= again) { again = 0f; return true; }
        return false;
    }

    public static void Stop()
    {
        if (watcher == null) return;
        watcher.EnableRaisingEvents = false;
        watcher.Dispose();
        watcher = null;
    }
}

// Ore Bin (parked): a vanilla chest (for its Container, WearNTear and sounds) with its own look hidden,
// dressed in copies of vanilla parts. Sizes of the parts are measured from the game, then each part is fitted to a box.
static class Kitbash
{
    public static void OreBin(GameObject go, Container container)
    {
        var vis = Strip(go, "storehouse_orebin");
        const float L = 2.0f, D = 1.4f, H = 0.9f, t = 0.22f;
        // Stone walls, a stone floor, a heap of stone inside
        foreach (var szn in new[] { -1f, 1f })
            Kit.Place(vis, "stone_wall_2x1", new Vector3(0f, H / 2f, szn * (D / 2f - t / 2f)), new Vector3(L, H, t), Kit.Orient.Yaw);
        foreach (var sxn in new[] { -1f, 1f })
            Kit.Place(vis, "stone_wall_2x1", new Vector3(sxn * (L / 2f - t / 2f), H / 2f, 0f), new Vector3(t, H, D - 2f * t), Kit.Orient.Yaw);
        Kit.Place(vis, "stone_floor", new Vector3(0f, 0.05f, 0f), new Vector3(L - 2f * t, 0.1f, D - 2f * t), Kit.Orient.Yaw);
        Kit.Place(vis, "stone_pile", new Vector3(0f, 0.1f + 0.3f, 0f), new Vector3(L - 2f * t - 0.08f, 0.6f, D - 2f * t - 0.08f), Kit.Orient.Yaw);
        // Iron rim on top of the walls, iron straps down the corners
        foreach (var szn in new[] { -1f, 1f })
            Kit.Place(vis, "iron_floor_1x1", new Vector3(0f, H + 0.03f, szn * (D / 2f - t / 2f)), new Vector3(L + 0.04f, 0.06f, t + 0.06f), Kit.Orient.Yaw);
        foreach (var sxn in new[] { -1f, 1f })
            Kit.Place(vis, "iron_floor_1x1", new Vector3(sxn * (L / 2f - t / 2f), H + 0.03f, 0f), new Vector3(t + 0.06f, 0.06f, D - 2f * t), Kit.Orient.Yaw);
        foreach (var sxn in new[] { -1f, 1f })
            foreach (var szn in new[] { -1f, 1f })
            {
                Kit.Place(vis, "iron_wall_1x1", new Vector3(sxn * (L / 2f - 0.1f), H / 2f, szn * (D / 2f + 0.015f)), new Vector3(0.14f, H, 0.03f), Kit.Orient.Yaw);
                Kit.Place(vis, "iron_wall_1x1", new Vector3(sxn * (L / 2f + 0.015f), H / 2f, szn * (D / 2f - 0.1f)), new Vector3(0.03f, H, 0.14f), Kit.Orient.Yaw);
            }
        Finish(go, vis, new Bounds(new Vector3(0f, (H + 0.06f) / 2f, 0f), new Vector3(L + 0.04f, H + 0.06f, D + 0.04f)), WearNTear.MaterialType.Stone, 1500f);
    }

    // A live model change (Cooper's Row r9 to r10, 1.1 m wider, 27 Oct): a stackable store's corners anew from the new frame's box.
    // A store without corners stays without.
    internal static void Resnap(GameObject go, Bounds box)
    {
        var old = go.transform.Cast<Transform>().Where(t => t.name.StartsWith("storehouse_snap_", StringComparison.Ordinal)).ToList();
        if (old.Count == 0) return;
        foreach (var t in old) { t.SetParent(null); UnityEngine.Object.Destroy(t.gameObject); }
        Snap(go, box);
    }

    // Outdoor stores stack and line up like crates (Joost): a snap point on each corner of the frame's box, top and bottom.
    // Valheim reads snap points from the piece root's direct children tagged "snappoint"; the "storehouse_" name lets a live
    // reload remove and add them again with the rest of our parts.
    static void Snap(GameObject go, Bounds box)
    {
        int n = 0;
        foreach (var y in new[] { box.min.y, box.max.y })
            foreach (var x in new[] { box.min.x, box.max.x })
                foreach (var z in new[] { box.min.z, box.max.z })
                {
                    var p = new GameObject($"storehouse_snap_{n++}") { tag = "snappoint", layer = go.layer };
                    p.SetActive(false);
                    p.transform.SetParent(go.transform, false);
                    p.transform.localPosition = new Vector3(x, y, z);
                }
    }

    // Hide the base chest's look (renderers off, colliders and LOD group gone) and add an empty child for the new parts.
    public static Transform Strip(GameObject go, string name)
    {
        foreach (var r in go.GetComponentsInChildren<Renderer>(true)) r.enabled = false;
        foreach (var lod in go.GetComponentsInChildren<LODGroup>(true)) UnityEngine.Object.DestroyImmediate(lod);
        var vis = new GameObject(name).transform;
        vis.SetParent(go.transform, false);
        vis.gameObject.layer = go.layer;
        return vis;
    }

    public static void Finish(GameObject go, Transform vis, Bounds box, WearNTear.MaterialType material, float health, bool quiet = false, bool stackable = false)
    {
        Geometry.FitColliders(go, box, go.name, replaceAll: true, quiet: quiet);
        Geometry.SolidFrame(go, vis, go.name, quiet);
        if (stackable) Snap(go, box);
        // A chest carries nothing in vanilla (WearNTear.m_supports off: "Invalid placement" on top). Outdoor stores carry the next one.
        if (stackable && go.GetComponent<WearNTear>() is { } carry) carry.m_supports = true;
        if (go.GetComponent<WearNTear>() is { } wnt)
        {
            wnt.m_materialType = material;
            wnt.m_health = health;
        }
        // One LOD level so the parts drop out at a distance like vanilla pieces do.
        var renderers = vis.GetComponentsInChildren<Renderer>(true);
        if (renderers.Length > 0)
        {
            var group = vis.gameObject.AddComponent<LODGroup>();
            group.SetLODs(new[] { new LOD(0.03f, renderers) });
            group.RecalculateBounds();
        }
    }
}

// Copies of vanilla prefabs' visible meshes (mesh + materials only, no components), fitted into a box.
static class Kit
{
    public enum Orient { Yaw, Free }   // Yaw: only turn 0/90 degrees around up. Free: lay the part's longest axis along the box's.

    sealed class Part { public Mesh Mesh; public Material[] Mats; public Vector3 Pos, Scale; public Quaternion Rot; public int Layer; public UnityEngine.Rendering.ShadowCastingMode Shadows; public bool Receive; }
    sealed class Source { public readonly List<Part> Parts = new(); public Bounds Bounds; }
    static readonly Dictionary<string, Source> sources = new();

    public static Vector3? Size(string prefab) => Get(prefab)?.Bounds.size;

    static Source Get(string prefab)
    {
        if (sources.TryGetValue(prefab, out var cached)) return cached;
        sources[prefab] = null;
        var go = PrefabManager.Instance.GetPrefab(prefab);
        if (!go) { Plugin.Log.LogWarning($"Kitbash: vanilla prefab '{prefab}' not found; that part is left out."); return null; }
        var root = go.transform;
        var wnt = go.GetComponent<WearNTear>();
        var skip = new HashSet<Renderer>();
        if (go.GetComponentInChildren<LODGroup>(true) is { } group)
        {
            var lods = group.GetLODs();
            for (int i = 1; i < lods.Length; i++) foreach (var r in lods[i].renderers) if (r) skip.Add(r);
        }
        var src = new Source();
        bool first = true;
        foreach (var mr in go.GetComponentsInChildren<MeshRenderer>(true))
        {
            if (skip.Contains(mr) || !ActiveChain(mr.transform, root)) continue;
            if (wnt && wnt.m_new != wnt.m_worn && wnt.m_worn && mr.transform.IsChildOf(wnt.m_worn.transform)) continue;
            if (wnt && wnt.m_new != wnt.m_broken && wnt.m_broken && mr.transform.IsChildOf(wnt.m_broken.transform)) continue;
            var mf = mr.GetComponent<MeshFilter>();
            if (!mf || !mf.sharedMesh) continue;
            var m = root.worldToLocalMatrix * mr.transform.localToWorldMatrix;
            src.Parts.Add(new Part
            {
                Mesh = mf.sharedMesh, Mats = mr.sharedMaterials, Pos = m.GetColumn(3), Rot = m.rotation, Scale = m.lossyScale,
                Layer = mr.gameObject.layer, Shadows = mr.shadowCastingMode, Receive = mr.receiveShadows,
            });
            var b = Geometry.Xform(m, mf.sharedMesh.bounds);
            if (first) { src.Bounds = b; first = false; } else src.Bounds.Encapsulate(b);
        }
        if (src.Parts.Count == 0) { Plugin.Log.LogWarning($"Kitbash: '{prefab}' has no visible mesh; left out."); return null; }
        Plugin.Log.LogInfo($"Kitbash: '{prefab}': {src.Parts.Count} mesh(es), size {src.Bounds.size:F2}, centre {src.Bounds.center:F2}");
        return sources[prefab] = src;
    }

    internal static bool ActiveChain(Transform t, Transform root)
    {
        for (; t && t != root; t = t.parent) if (!t.gameObject.activeSelf) return false;
        return true;
    }

    // Place a copy of the prefab's look so that its measured bounds fill the box (centre, size) in parent space.
    public static void Place(Transform parent, string prefab, Vector3 center, Vector3 size, Orient orient)
    {
        var src = Get(prefab);
        if (src == null) return;
        var b = src.Bounds.size;
        Quaternion rot = Quaternion.identity;
        if (orient == Orient.Yaw)
        {
            if ((b.x >= b.z) != (size.x >= size.z)) rot = Quaternion.Euler(0f, 90f, 0f);
        }
        else
        {
            int a = Longest(b), t = Longest(size);
            if (a != t) rot = Quaternion.FromToRotation(Axis(a), Axis(t));
        }
        // Rotations here only swap axes, so each source axis lands on exactly one box axis: scale it to that box size.
        var scale = Vector3.one;
        for (int j = 0; j < 3; j++)
        {
            var d = rot * Axis(j);
            int i = Longest(new Vector3(Mathf.Abs(d.x), Mathf.Abs(d.y), Mathf.Abs(d.z)));
            scale[j] = b[j] > 0.001f ? size[i] / b[j] : 1f;
        }
        var holder = new GameObject("kit_" + prefab).transform;
        holder.SetParent(parent, false);
        holder.gameObject.layer = parent.gameObject.layer;
        holder.localRotation = rot;
        holder.localScale = scale;
        holder.localPosition = center - rot * Vector3.Scale(scale, src.Bounds.center);
        foreach (var part in src.Parts)
        {
            var go = new GameObject(part.Mesh.name);
            go.layer = part.Layer;
            var tr = go.transform;
            tr.SetParent(holder, false);
            tr.localPosition = part.Pos;
            tr.localRotation = part.Rot;
            tr.localScale = part.Scale;
            go.AddComponent<MeshFilter>().sharedMesh = part.Mesh;
            var mr = go.AddComponent<MeshRenderer>();
            mr.sharedMaterials = part.Mats;
            mr.shadowCastingMode = part.Shadows;
            mr.receiveShadows = part.Receive;
        }
    }

    static int Longest(Vector3 v) => v.x >= v.y && v.x >= v.z ? 0 : v.y >= v.z ? 1 : 2;
    static Vector3 Axis(int i) => i == 0 ? Vector3.right : i == 1 ? Vector3.up : Vector3.forward;
}

static class Geometry
{
    // Smooth shading for a curved panel exported face by face (the Hide Rack's hides showed their triangle fan, Joost 25 Oct): every
    // vertex gets the average normal of all vertices at its position. Vertices, UVs and triangles stay as they are.
    public static Mesh SmoothNormals(Mesh mesh)
    {
        if (!mesh) return mesh;
        mesh.RecalculateNormals();
        var v = mesh.vertices;
        var n = mesh.normals;
        var sum = new Dictionary<Vector3Int, Vector3>();
        Vector3Int Key(Vector3 p) => new(Mathf.RoundToInt(p.x * 1e4f), Mathf.RoundToInt(p.y * 1e4f), Mathf.RoundToInt(p.z * 1e4f));
        for (int i = 0; i < v.Length; i++) { var k = Key(v[i]); sum[k] = (sum.TryGetValue(k, out var t) ? t : Vector3.zero) + n[i]; }
        for (int i = 0; i < v.Length; i++) n[i] = sum[Key(v[i])].normalized;
        mesh.normals = n;
        return mesh;
    }

    public static Bounds Xform(Matrix4x4 m, Bounds b)
    {
        var c = b.center;
        var e = b.extents;
        var res = new Bounds(m.MultiplyPoint3x4(c), Vector3.zero);
        for (int i = 0; i < 8; i++)
            res.Encapsulate(m.MultiplyPoint3x4(c + new Vector3((i & 1) == 0 ? -e.x : e.x, (i & 2) == 0 ? -e.y : e.y, (i & 4) == 0 ? -e.z : e.z)));
        return res;
    }

    // Bounds of a mesh on transform t, in root space.
    public static Bounds BoundsIn(Transform root, Transform t, Bounds local) => Xform(root.worldToLocalMatrix * t.localToWorldMatrix, local);

    // One solid box collider covering box (root space). Keeps the first solid BoxCollider (and its layer), removes the other
    // solid colliders; triggers stay. With replaceAll every solid collider goes and a fresh box goes on the root.
    public static void FitColliders(GameObject go, Bounds box, string label, bool replaceAll = false, bool quiet = false)
    {
        var root = go.transform;
        int layer = -1;
        BoxCollider keep = null;
        // Built before (a dev live reload): keep our own box, so the collider the game already knows stays the same object.
        if (replaceAll && root.Find("storehouse_collider") is { } own) keep = own.GetComponent<BoxCollider>();
        var removed = new List<string>();
        foreach (var c in go.GetComponentsInChildren<Collider>(true))
        {
            if (c.isTrigger || c == keep) continue;
            if (layer < 0) layer = c.gameObject.layer;
            if (!replaceAll && !keep && c is BoxCollider bc) { keep = bc; continue; }
            removed.Add($"{c.GetType().Name} on {Inspect.Path(c.transform, root)}");
            UnityEngine.Object.DestroyImmediate(c);
        }
        if (!keep)
        {
            var holder = new GameObject("storehouse_collider");
            holder.transform.SetParent(root, false);
            holder.layer = layer >= 0 ? layer : LayerMask.NameToLayer("piece");
            keep = holder.AddComponent<BoxCollider>();
        }
        var local = Xform(keep.transform.worldToLocalMatrix * root.localToWorldMatrix, box);
        keep.center = local.center;
        keep.size = local.size;
        keep.enabled = true;   // SolidFrame switches it off again where the frame's hull aims instead
        if (!quiet) Plugin.Log.LogInfo($"{label}: collider {Inspect.Path(keep.transform, root)} (layer {LayerMask.LayerToName(keep.gameObject.layer)}) set to {box.size:F2} at {box.center:F2}"
            + (removed.Count > 0 ? "; removed " + string.Join(", ", removed) : ""));
    }

    // The frame itself is what you bump into and stand on (Joost: he stood on air over the open Ore Bin): a mesh collider on
    // each of our part meshes. The box stays, for aiming at and opening the store, on the layer players walk through
    // (piece_nonsolid, as rugs and banners use). Without that layer or our meshes it stays the solid box.
    public static void SolidFrame(GameObject go, Transform vis, string label, bool quiet = false)
    {
        int through = LayerMask.NameToLayer("piece_nonsolid");
        var box = go.transform.Find("storehouse_collider");
        var parts = vis ? vis.GetComponentsInChildren<MeshFilter>(true).Where(f => f.sharedMesh && f.sharedMesh.isReadable).ToList() : new List<MeshFilter>();
        if (through < 0 || !box || parts.Count == 0) return;
        int solid = box.gameObject.layer != through ? box.gameObject.layer : LayerMask.NameToLayer("piece");
        box.gameObject.layer = through;
        foreach (var f in parts)
        {
            var mc = f.GetComponent<MeshCollider>();
            if (!mc) mc = f.gameObject.AddComponent<MeshCollider>();
            mc.sharedMesh = f.sharedMesh;
            f.gameObject.layer = solid;
        }
        // What you aim at hugs the frame (Joost, 27 Oct: aiming at the wall above the Ossuary's gable still picked the bin, the box
        // being the frame's whole bounds): a convex hull of our part meshes on the box's object and layer, the box itself switched off
        // (kept, so a rebuild finds it). The hull still takes in an open bin's or cabinet's inside, so aiming at the contents opens it.
        var aim = box.GetComponent<BoxCollider>();
        var hullMesh = Hull(box, parts);
        if (hullMesh)
        {
            var hull = box.GetComponent<MeshCollider>() ?? box.gameObject.AddComponent<MeshCollider>();
            hull.sharedMesh = hullMesh;
            hull.convex = true;
            if (aim) aim.enabled = false;
        }
        if (!quiet) Plugin.Log.LogInfo($"{label}: solid as its frame ({parts.Count} mesh collider(s), layer {LayerMask.LayerToName(solid)}); aimed at by {(hullMesh ? "the frame's convex hull" : "its box")}.");
    }

    // Our part meshes in t's space, as one mesh for a convex collider (Unity cooks the hull from it).
    static Mesh Hull(Transform t, List<MeshFilter> parts)
    {
        var combine = parts.Where(f => f.sharedMesh.vertexCount > 0).SelectMany(f => Enumerable.Range(0, f.sharedMesh.subMeshCount)
            .Select(k => new CombineInstance { mesh = f.sharedMesh, subMeshIndex = k, transform = t.worldToLocalMatrix * f.transform.localToWorldMatrix })).ToArray();
        if (combine.Length == 0) return null;
        var mesh = new Mesh { name = "storehouse_aim_hull", indexFormat = UnityEngine.Rendering.IndexFormat.UInt32 };
        mesh.CombineMeshes(combine, true, true);
        return mesh;
    }
}

// Wavefront .obj reader. Our own instead of Jotunn's AssetUtils.LoadMesh, which parses numbers with the PC's culture
// (a Dutch or German Windows reads "0.5" as 5) and leaves out tangents (the piece shader's normal map needs them).
// Same convention as Jotunn's: coordinates are taken as Unity space as written, faces keep their winding; flipX converts
// a right-handed export (Blender default) by mirroring X and reversing the winding.
static class ObjMesh
{
    // objectEnds: when given, gets the index count at the end of each "o" object, in file order; objectNames: that object's name
    // beside each end (an object without faces gets no end, so the names keep step).
    public static Mesh Load(string path, bool flipX, List<int> objectEnds = null, List<string> objectNames = null)
    {
        if (!File.Exists(path)) return null;
        try
        {
            var v = new List<Vector3>();
            var vt = new List<Vector2>();
            var vn = new List<Vector3>();
            var verts = new List<Vector3>();
            var uvs = new List<Vector2>();
            var norms = new List<Vector3>();
            var tris = new List<int>();
            var index = new Dictionary<(int, int, int), int>();
            bool hasNormals = true;
            var ci = CultureInfo.InvariantCulture;
            var corner = new List<int>();
            string current = null;
            foreach (var rawLine in File.ReadLines(path))
            {
                var line = rawLine.Trim();
                if (line.Length < 2 || line[0] == '#') continue;
                var p = line.Split((char[])null, StringSplitOptions.RemoveEmptyEntries);
                switch (p[0])
                {
                    case "o":
                        if (objectEnds != null && tris.Count > 0 && (objectEnds.Count == 0 || objectEnds[objectEnds.Count - 1] != tris.Count)) { objectEnds.Add(tris.Count); objectNames?.Add(current); }
                        current = line.Substring(1).Trim();
                        break;
                    case "v":
                        v.Add(new Vector3(float.Parse(p[1], ci), float.Parse(p[2], ci), float.Parse(p[3], ci)));
                        break;
                    case "vt":
                        vt.Add(new Vector2(float.Parse(p[1], ci), p.Length > 2 ? float.Parse(p[2], ci) : 0f));
                        break;
                    case "vn":
                        vn.Add(new Vector3(float.Parse(p[1], ci), float.Parse(p[2], ci), float.Parse(p[3], ci)));
                        break;
                    case "f":
                        corner.Clear();
                        for (int i = 1; i < p.Length; i++)
                        {
                            var s = p[i].Split('/');
                            int a = Idx(s[0], v.Count), b = s.Length > 1 && s[1].Length > 0 ? Idx(s[1], vt.Count) : -1, c = s.Length > 2 && s[2].Length > 0 ? Idx(s[2], vn.Count) : -1;
                            if (c < 0) hasNormals = false;
                            if (!index.TryGetValue((a, b, c), out int k))
                            {
                                k = verts.Count;
                                index[(a, b, c)] = k;
                                var pos = v[a];
                                var n = c >= 0 ? vn[c] : Vector3.up;
                                if (flipX) { pos.x = -pos.x; n.x = -n.x; }
                                verts.Add(pos);
                                uvs.Add(b >= 0 ? vt[b] : Vector2.zero);
                                norms.Add(n);
                            }
                            corner.Add(k);
                        }
                        for (int i = 1; i + 1 < corner.Count; i++)
                        {
                            if (flipX) { tris.Add(corner[0]); tris.Add(corner[i + 1]); tris.Add(corner[i]); }
                            else { tris.Add(corner[0]); tris.Add(corner[i]); tris.Add(corner[i + 1]); }
                        }
                        break;
                }
            }
            if (tris.Count == 0) { Plugin.Log.LogWarning($"{path}: no faces."); return null; }
            if (objectEnds != null && (objectEnds.Count == 0 || objectEnds[objectEnds.Count - 1] != tris.Count)) { objectEnds.Add(tris.Count); objectNames?.Add(current); }
            var mesh = new Mesh { name = Path.GetFileNameWithoutExtension(path) };
            if (verts.Count > 65000) mesh.indexFormat = UnityEngine.Rendering.IndexFormat.UInt32;
            mesh.SetVertices(verts);
            mesh.SetUVs(0, uvs);
            mesh.SetTriangles(tris, 0);
            if (hasNormals) mesh.SetNormals(norms); else mesh.RecalculateNormals();
            mesh.RecalculateTangents();
            mesh.RecalculateBounds();
            return mesh;
        }
        catch (Exception e)
        {
            Plugin.Log.LogError($"{path}: could not read ({e.Message}).");
            return null;
        }
    }

    static int Idx(string s, int count)
    {
        int i = int.Parse(s, CultureInfo.InvariantCulture);
        return i < 0 ? count + i : i - 1;
    }
}

// Tiny JSON reader for the Strongbox's metadata (objects, arrays, numbers, strings, true/false/null). No dependency.
static class Json
{
    public static object Parse(string s)
    {
        int i = 0;
        var v = Value(s, ref i);
        return v;
    }

    static void Ws(string s, ref int i) { while (i < s.Length && char.IsWhiteSpace(s[i])) i++; }

    static object Value(string s, ref int i)
    {
        Ws(s, ref i);
        if (i >= s.Length) throw new FormatException("unexpected end");
        char c = s[i];
        if (c == '{')
        {
            var d = new Dictionary<string, object>();
            i++;
            Ws(s, ref i);
            if (s[i] == '}') { i++; return d; }
            while (true)
            {
                Ws(s, ref i);
                var key = Str(s, ref i);
                Ws(s, ref i);
                if (s[i++] != ':') throw new FormatException("expected :");
                d[key] = Value(s, ref i);
                Ws(s, ref i);
                if (s[i] == ',') { i++; continue; }
                if (s[i] == '}') { i++; return d; }
                throw new FormatException("expected , or }");
            }
        }
        if (c == '[')
        {
            var l = new List<object>();
            i++;
            Ws(s, ref i);
            if (s[i] == ']') { i++; return l; }
            while (true)
            {
                l.Add(Value(s, ref i));
                Ws(s, ref i);
                if (s[i] == ',') { i++; continue; }
                if (s[i] == ']') { i++; return l; }
                throw new FormatException("expected , or ]");
            }
        }
        if (c == '"') return Str(s, ref i);
        if (s.Length - i >= 4 && string.CompareOrdinal(s, i, "true", 0, 4) == 0) { i += 4; return true; }
        if (s.Length - i >= 5 && string.CompareOrdinal(s, i, "false", 0, 5) == 0) { i += 5; return false; }
        if (s.Length - i >= 4 && string.CompareOrdinal(s, i, "null", 0, 4) == 0) { i += 4; return null; }
        int start = i;
        while (i < s.Length && "+-0123456789.eE".IndexOf(s[i]) >= 0) i++;
        return double.Parse(s.Substring(start, i - start), NumberStyles.Float, CultureInfo.InvariantCulture);
    }

    static string Str(string s, ref int i)
    {
        if (s[i] != '"') throw new FormatException("expected string");
        var sb = new StringBuilder();
        for (i++; s[i] != '"'; i++)
        {
            if (s[i] != '\\') { sb.Append(s[i]); continue; }
            i++;
            switch (s[i])
            {
                case 'n': sb.Append('\n'); break;
                case 't': sb.Append('\t'); break;
                case 'u': sb.Append((char)Convert.ToInt32(s.Substring(i + 1, 4), 16)); i += 4; break;
                default: sb.Append(s[i]); break;
            }
        }
        i++;
        return sb.ToString();
    }

    public static Dictionary<string, object> Obj(Dictionary<string, object> d, string key) =>
        d != null && d.TryGetValue(key, out var v) ? v as Dictionary<string, object> : null;

    public static bool? Bool(Dictionary<string, object> d, string key) =>
        d != null && d.TryGetValue(key, out var v) && v is bool b ? b : null;

    static float[] Floats(Dictionary<string, object> d, string key, params string[] names)
    {
        if (d == null || !d.TryGetValue(key, out var v)) return null;
        if (v is List<object> l && l.Count >= names.Length && l.All(x => x is double))
            return l.Take(names.Length).Select(x => (float)(double)x).ToArray();
        if (v is Dictionary<string, object> o && names.All(n => o.TryGetValue(n, out var x) && x is double))
            return names.Select(n => (float)(double)o[n]).ToArray();
        return null;
    }

    public static Vector3? Vec3(Dictionary<string, object> d, string key) =>
        Floats(d, key, "x", "y", "z") is { } f ? new Vector3(f[0], f[1], f[2]) : null;

    // Quaternion as [x, y, z, w] (Unity order).
    public static Quaternion? Quat(Dictionary<string, object> d, string key) =>
        Floats(d, key, "x", "y", "z", "w") is { } f ? new Quaternion(f[0], f[1], f[2], f[3]) : null;
}

// Hammer icons, rendered at runtime from the running game like vanilla's own (no image ships with the mod): a showcase
// copy of the finished piece (our frame and, for the dev stores, their contents shown full with the anchors' demo items,
// or a default per store where a unit names none), seen in the front three-quarter view vanilla's piece icons use, on a
// transparent background, at the pixel size of the wood chest's icon. Rendered at 4x with Jotunn's RenderManager (its
// camera and light) and averaged down, so the edges are smooth like vanilla's. Rendered again when the piece's look
// changes (live models, Display item size, slots per plank) and, if an item was missing at the first render (ObjectDB not
// there yet), once the game's ObjectDB has its items. Falls back to the plain prefab, then to a vanilla icon.
static class Icons
{
    // Front three-quarter view: turned 30 degrees (front towards the left, the right side in view), looking down 20 degrees.
    static readonly Quaternion View = Quaternion.Euler(20f, 0f, 0f) * Quaternion.Euler(0f, 30f, 0f);
    const int DefaultSize = 128, MaxRender = 512, Supersample = 4;

    sealed class State
    {
        public Kind Kind;
        public GameObject Prefab;
        public Sprite Sprite;
        public int Signature;
        public bool Missing;    // an item model could not be found at the last render
        public ObjectDB Db;     // the ObjectDB of the last render
    }

    static readonly Dictionary<Kind, State> states = new();
    static int size;
#if DEV
    public static ConfigEntry<bool> Dump;

    public static void Bind(ConfigFile config)
    {
        Dump = config.Safe("9 - Debug", "Dump icons", false,
            "Dev: save every hammer icon the mod renders as a PNG in BepInEx/cache/Storehouse-icons/ (again whenever one is re-rendered). "
            + "Turning it on saves the current ones right away.");
        Dump.SettingChanged += (_, _) => { if (Plugin.Live && Dump.Value) foreach (var s in states.Values) Save(s); };
    }

    // Live reload: this copy's icons are handed to the next copy (through the AppDomain, which every copy shares), with what
    // they were rendered from. The next copy keeps an icon whose piece looks the same and renders only the changed ones:
    // re-rendering all of them was most of the hitch of a live reload (Joost). What the next copy doesn't take, it destroys.
    const string Handover = "Finn.Storehouse.icons";
    internal static void Release()
    {
        var keep = new Dictionary<string, object[]>();
        foreach (var s in states.Values)
            if (s.Sprite && s.Prefab) keep[s.Prefab.name] = new object[] { s.Sprite, Content(s), s.Missing };
        AppDomain.CurrentDomain.SetData(Handover, keep);
        states.Clear();
    }

    // Icons the previous copy left: reuse when the content matches.
    static Dictionary<string, object[]> handed;
    static Sprite Inherit(State s)
    {
        handed ??= AppDomain.CurrentDomain.GetData(Handover) as Dictionary<string, object[]> ?? new Dictionary<string, object[]>();
        AppDomain.CurrentDomain.SetData(Handover, null);
        if (!handed.TryGetValue(s.Prefab.name, out var old) || old[0] is not Sprite sprite || !sprite) return null;
        handed.Remove(s.Prefab.name);
        if (old[1] as string != Content(s) || old[2] is true) { Drop(sprite); return null; }
        s.Sprite = sprite;
        s.Missing = false;
        s.Signature = Signature(s);
        s.Db = ObjectDB.instance;
        return sprite;
    }

    // Once the pieces are rebuilt: the previous copy's icons nobody took.
    static void DropLeftovers()
    {
        if (handed == null) return;
        foreach (var old in handed.Values) if (old[0] is Sprite sprite) Drop(sprite);
        handed.Clear();
    }

    static void Drop(Sprite sprite)
    {
        if (!sprite) return;
        if (sprite.texture) UnityEngine.Object.Destroy(sprite.texture);
        UnityEngine.Object.Destroy(sprite);
    }

    // What an icon shows, independent of this copy: the piece, its grid, the display size and the model files it was built
    // from (path + time written).
    static string Content(State s)
    {
        var sb = new StringBuilder($"{s.Prefab.name}|{s.Kind.Width}x{s.Kind.Height}|{Settings.DisplaySize?.Value:F3}");
        IEnumerable<string> files = s.Kind == Kinds.Crib ? CribModel.Files : null;
        foreach (Transform vis in s.Prefab.transform)
            if (StoreModel.ForVis(vis.name) is { LoadedFiles: { } f }) files = f;
        foreach (var f in files ?? Enumerable.Empty<string>())
            sb.Append('|').Append(f).Append('@').Append(File.Exists(f) ? File.GetLastWriteTimeUtc(f).Ticks : 0);
        return sb.ToString();
    }
#endif

    static bool Headless => SystemInfo.graphicsDeviceType == UnityEngine.Rendering.GraphicsDeviceType.Null;

    // At piece creation. Null: keep the base chest's icon.
    public static Sprite Render(GameObject go, Kind kind)
    {
        if (!states.TryGetValue(kind, out var s)) states[kind] = s = new State { Kind = kind };
        s.Prefab = go;
#if DEV
        if (Inherit(s) is { } kept) return kept;
#endif
        return Make(s) ?? Fallback(go, kind);
    }

    // Once a second: render again what changed, and what missed items before ObjectDB had them.
    public static void Tick()
    {
        if (states.Count == 0 || Headless) return;
#if DEV
        DropLeftovers();
#endif
        var db = ObjectDB.instance;
        foreach (var s in states.Values)
        {
            if (!s.Prefab || s.Prefab.GetComponent<Piece>() is not { } piece) continue;
            bool changed = Signature(s) != s.Signature;
            bool retry = s.Missing && db && db != s.Db && db.m_items.Count > 0;
            if (!changed && !retry) continue;
            // The old sprite is left alone: an open hammer menu may still show it.
            if (Make(s) is { } sprite) piece.m_icon = sprite;
        }
    }

    // What the icon depends on: the meshes the piece shows, its grid (a shelf shows one item per slot), the store's version.
    static int Signature(State s)
    {
        unchecked
        {
            int h = s.Kind.Width * 1000 + s.Kind.Height;
            var root = s.Prefab.transform;
            foreach (var r in root.GetComponentsInChildren<Renderer>(true))
                if (r.enabled && Kit.ActiveChain(r.transform, root) && MeshOf(r) is { } mesh) h = h * 31 + mesh.GetInstanceID();
#if DEV
            foreach (Transform vis in root) if (StoreModel.ForVis(vis.name) is { } model) h = h * 31 + model.Version;
#endif
            return h;
        }
    }

    static Mesh MeshOf(Renderer r) =>
        r is SkinnedMeshRenderer smr ? smr.sharedMesh : r is MeshRenderer && r.GetComponent<MeshFilter>() is { } mf ? mf.sharedMesh : null;

    // Pixel size of a vanilla piece icon, read from the game (the wood chest's), once.
    static int Size()
    {
        if (size > 0) return size;
        var chest = PrefabManager.Instance.GetPrefab("piece_chest_wood");
        var icon = chest && chest.GetComponent<Piece>() is { } p ? p.m_icon : null;
        size = icon ? Mathf.Clamp(Mathf.RoundToInt(Mathf.Max(icon.rect.width, icon.rect.height)), 32, MaxRender) : DefaultSize;
        Plugin.Log.LogInfo(icon
            ? $"Icons: the wood chest's hammer icon is {icon.rect.width:0}x{icon.rect.height:0} px; ours are rendered at {size}x{size}."
            : $"Icons: no vanilla chest icon to measure; ours are rendered at {size}x{size}.");
        return size;
    }

    static Sprite Make(State s)
    {
        s.Signature = Signature(s);   // also after a failure: try again only when something changes
        if (Headless) return null;
        GameObject show = null;
        var meshes = new List<Mesh>();
        try
        {
            show = Showcase(s, meshes, out bool missing);
            if (!show) return null;
            int px = Size(), ss = Mathf.Clamp(MaxRender / px, 1, Supersample);
            var big = RenderManager.Instance.Render(new RenderManager.RenderRequest(show) { Rotation = View, Width = px * ss, Height = px * ss });
            if (!big) return null;
            s.Sprite = Shrink(big, ss, s.Kind.Prefab);
            s.Missing = missing;
            s.Db = ObjectDB.instance;
            Plugin.Log.LogInfo($"{s.Kind.Title}: hammer icon rendered ({px}x{px} px from {px * ss}x{px * ss}"
                + (missing ? "; some item models not found yet, rendered again once the game has them" : "") + ").");
#if DEV
            if (Dump.Value) Save(s);
#endif
            return s.Sprite;
        }
        catch (Exception e)
        {
            Plugin.Log.LogWarning($"{s.Kind.Title}: icon render failed ({e.Message}).");
            return null;
        }
        finally
        {
            if (show) UnityEngine.Object.DestroyImmediate(show);
            foreach (var m in meshes) if (m) UnityEngine.Object.Destroy(m);
        }
    }

    // A copy of the piece's visible meshes (nothing else: no scripts, colliders or LOD groups), plus its contents, with its
    // bounds centre on the origin so the render camera frames it tightly. Active for this frame only (destroyed right after
    // the render, before any scene camera draws). Null when the piece shows nothing.
    static GameObject Showcase(State s, List<Mesh> meshes, out bool missing)
    {
        missing = false;
        var src = s.Prefab.transform;
        var root = new GameObject("storehouse_icon_" + s.Kind.Prefab);
        var pivot = new GameObject("pivot").transform;
        pivot.SetParent(root.transform, false);
        var toRoot = src.worldToLocalMatrix;
        int parts = 0;
        foreach (var r in src.GetComponentsInChildren<Renderer>(true))
        {
            if (!r.enabled || !Kit.ActiveChain(r.transform, src) || MeshOf(r) is not { } mesh) continue;
            Part(pivot, mesh, r.sharedMaterials, toRoot * r.transform.localToWorldMatrix);
            parts++;
        }
#if DEV
        foreach (Transform vis in src)
            if (StoreModel.ForVis(vis.name) is { } model && model.Ready)
                parts += Fill(pivot, toRoot * vis.localToWorldMatrix, model, s.Kind, meshes, ref missing);
#endif
        if (parts == 0) { UnityEngine.Object.DestroyImmediate(root); return null; }
        var renderers = pivot.GetComponentsInChildren<Renderer>();
        var b = renderers[0].bounds;
        foreach (var r in renderers) b.Encapsulate(r.bounds);
        pivot.localPosition = -b.center;
        return root;
    }

    static void Part(Transform parent, Mesh mesh, Material[] mats, Matrix4x4 m)
    {
        var go = new GameObject(mesh.name);
        var t = go.transform;
        t.SetParent(parent, false);
        t.localPosition = m.GetColumn(3);
        t.localRotation = m.rotation;
        t.localScale = m.lossyScale;
        go.AddComponent<MeshFilter>().sharedMesh = mesh;
        go.AddComponent<MeshRenderer>().sharedMaterials = mats;
    }

    // Supersampled render averaged down by ss x ss, weighted by alpha so the edges don't darken against the clear colour.
    static Sprite Shrink(Sprite big, int ss, string name)
    {
        var src = big.texture;
        if (ss <= 1) { src.name = name + "_icon"; return big; }
        int w = src.width / ss, h = src.height / ss, sw = src.width;
        var from = src.GetPixels32();   // readable: Jotunn makes it with ReadPixels
        var to = new Color32[w * h];
        for (int y = 0; y < h; y++)
            for (int x = 0; x < w; x++)
            {
                float r = 0f, g = 0f, bl = 0f, a = 0f;
                for (int dy = 0; dy < ss; dy++)
                    for (int dx = 0; dx < ss; dx++)
                    {
                        var c = from[(y * ss + dy) * sw + x * ss + dx];
                        r += c.r * c.a; g += c.g * c.a; bl += c.b * c.a; a += c.a;
                    }
                to[y * w + x] = a > 0f
                    ? new Color32((byte)Mathf.Clamp(Mathf.RoundToInt(r / a), 0, 255), (byte)Mathf.Clamp(Mathf.RoundToInt(g / a), 0, 255),
                        (byte)Mathf.Clamp(Mathf.RoundToInt(bl / a), 0, 255), (byte)Mathf.RoundToInt(a / (ss * ss)))
                    : new Color32(0, 0, 0, 0);
            }
        var tex = new Texture2D(w, h, TextureFormat.RGBA32, false) { name = name + "_icon", filterMode = FilterMode.Bilinear, wrapMode = TextureWrapMode.Clamp };
        tex.SetPixels32(to);
        tex.Apply();
        UnityEngine.Object.Destroy(big);
        UnityEngine.Object.Destroy(src);
        return Sprite.Create(tex, new Rect(0, 0, w, h), new Vector2(0.5f, 0.5f));
    }

    // The old way: the plain prefab (an empty store), then a vanilla piece's icon.
    static Sprite Fallback(GameObject go, Kind kind)
    {
        try
        {
            if (!Headless && RenderManager.Instance.Render(new RenderManager.RenderRequest(go) { Rotation = View, Width = Size(), Height = Size() }) is { } sprite && sprite)
                return sprite;
        }
        catch (Exception e) { Plugin.Log.LogWarning($"{kind.Title}: icon render failed ({e.Message}); using a vanilla icon."); }
        string fallback = kind == Kinds.Crib ? "wood_stack" : kind == Kinds.Bin ? "stone_pile" : null;
        var src = fallback != null ? PrefabManager.Instance.GetPrefab(fallback) : null;
        return src && src.GetComponent<Piece>() is { } p ? p.m_icon : null;
    }

#if DEV
    static void Save(State s)
    {
        if (!s.Sprite || !s.Sprite.texture) return;
        try
        {
            var dir = Path.Combine(BepInEx.Paths.CachePath, "Storehouse-icons");
            Directory.CreateDirectory(dir);
            var file = Path.Combine(dir, s.Kind.Prefab + ".png");
            File.WriteAllBytes(file, s.Sprite.texture.EncodeToPNG());
            Plugin.Log.LogInfo($"{s.Kind.Title}: icon saved to {file}.");
        }
        catch (Exception e) { Plugin.Log.LogWarning($"{s.Kind.Title}: icon not saved ({e.Message})."); }
    }

    // A store's contents, full: every unit with all its copies of the unit's demo item (one per unit on display furniture),
    // or on a packed shelf one item per slot along the planks; the same placement StoreContents uses for real stacks.
    // Readable item meshes are merged per material (into meshes destroyed after the render), the others go in as they are.
    static int Fill(Transform parent, Matrix4x4 store, StoreModel model, Kind kind, List<Mesh> meshes, ref bool missing)
    {
        var defaults = Defaults(kind.Slug);
        var groups = new Dictionary<Material, List<CombineInstance>>();
        int parts = 0;
        void Put(ItemVisual look, Matrix4x4 at)
        {
            foreach (var part in look.Parts)
            {
                var m = store * at * part.M;
                if (!part.Readable) { Part(parent, part.Mesh, part.Mats, m); parts++; continue; }
                for (int sm = 0; sm < part.Mesh.subMeshCount; sm++)
                {
                    var mat = part.Mats.Length > 0 ? part.Mats[Mathf.Min(sm, part.Mats.Length - 1)] : null;
                    if (!mat) continue;
                    if (!groups.TryGetValue(mat, out var list)) groups[mat] = list = new List<CombineInstance>();
                    list.Add(new CombineInstance { mesh = part.Mesh, subMeshIndex = sm, transform = m });
                }
            }
        }

        if (model.Planks.Count > 0)
        {
            var looks = new List<ItemVisual>();
            for (int i = 0; i < Mathf.Max(1, kind.Width * kind.Height); i++)
            {
                var look = Item(defaults[i % defaults.Length]);
                if (look == null) missing = true;
                looks.Add(look);
            }
            var placed = Packing.Pack(model.Planks, looks, Packing.Planks(Enumerable.Range(0, looks.Count), looks.Count, model.Planks.Count), Settings.DisplaySize.Value);
            for (int i = 0; i < placed.Count; i++) if (placed[i] is { } at && looks[i] != null) Put(looks[i], at);
        }
        for (int i = 0; i < model.Units.Count; i++)
        {
            var unit = model.Units[i];
            if (unit.Copies.Count == 0) continue;
            var demo = Item(unit.Demo);
            if (demo == null && unit.Demo != null) missing = true;
            var look = demo ?? Item(defaults[i % defaults.Length]);
            if (look == null) { missing = true; continue; }
            int n = model.Display ? 1 : unit.Copies.Count;
            var drawn = kind.Slug == "rootbin" ? look.Topless : look;   // as in the store: root crops without their greens
            for (int j = 0; j < n; j++) Put(drawn, StoreModel.Place(unit, unit.Copies[j], look, demo, model.Display, model.Kind?.ItemSize?.Value ?? 1f));
        }
        foreach (var kv in groups)
        {
            var mesh = new Mesh { name = "storehouse_icon_" + kv.Key.name, indexFormat = UnityEngine.Rendering.IndexFormat.UInt32 };
            mesh.CombineMeshes(kv.Value.ToArray(), true, true);
            meshes.Add(mesh);
            Part(parent, mesh, new[] { kv.Key }, Matrix4x4.identity);
            parts++;
        }
        return parts;
    }

    // The game's own item model by prefab name: from ObjectDB, or before it exists (at piece creation) from Jotunn's prefab cache.
    static ItemVisual Item(string name)
    {
        if (string.IsNullOrEmpty(name)) return null;
        var go = ObjectDB.instance ? ObjectDB.instance.GetItemPrefab(name) : null;
        if (!go || !go.GetComponent<ItemDrop>()) go = PrefabManager.Instance.GetPrefab(name);
        return go && go.GetComponent<ItemDrop>() ? ItemVisual.Get(go) : null;
    }

    // What a store shows where its anchors name no item: a mix of what it holds, cycled over the units.
    static string[] Defaults(string slug) => slug switch
    {
        "meadrack" => new[] { "MeadHealthMinor", "MeadStaminaMinor", "MeadHealthMedium", "MeadEitrMinor", "MeadPoisonResist", "MeadFrostResist", "BarleyWine", "MeadTasty" },
        "larder" => new[] { "Bread", "CookedMeat", "LoxPie", "CarrotSoup", "TurnipStew", "Sausages", "QueensJam", "FishWraps", "SerpentStew", "MeatPlatter" },
        "meatrack" => new[] { "RawMeat", "DeerMeat", "NeckTail", "WolfMeat", "FishRaw", "ChickenMeat", "LoxMeat" },
        "rootbin" => new[] { "Carrot", "Turnip", "Onion", "Mushroom", "Barley", "Flax" },
        "orebin" => new[] { "CopperOre", "TinOre", "IronScrap", "SilverOre", "BlackMetalScrap", "FlametalOreNew" },
        "bunker" or "bunkeropen" => new[] { "Coal", "Stone", "Flint" },
        "emergencyshelf" => new[] { "MeadHealthMinor", "Bread", "MeadStaminaMinor", "CookedMeat", "MeadHealthMedium", "QueensJam", "MeadEitrMinor", "Sausages", "MeadPoisonResist", "LoxPie" },
        _ => new[] { "Wood" },
    };
#endif
}

// Writes what a prefab is made of to the log, so the vanilla hierarchy can be read without Unity.
static class Inspect
{
    public static string Path(Transform t, Transform root)
    {
        var parts = new List<string>();
        for (; t && t != root; t = t.parent) parts.Add(t.name);
        parts.Add(root ? root.name : "?");
        parts.Reverse();
        return string.Join("/", parts);
    }

    public static void Dump(GameObject go, string label)
    {
        if (!go) { Plugin.Log.LogWarning($"Dump: {label} not found."); return; }
        var sb = new StringBuilder();
        sb.AppendLine($"=== {label}: {go.name} ===");
        Walk(go.transform, 0, sb);
        if (go.GetComponentInChildren<Container>(true) is { } c)
            sb.AppendLine($"Container '{c.m_name}' {c.m_width}x{c.m_height}, open={(c.m_open ? c.m_open.name : "-")}, closed={(c.m_closed ? c.m_closed.name : "-")}, privacy={c.m_privacy}");
        if (go.GetComponent<WearNTear>() is { } w)
            sb.AppendLine($"WearNTear {w.m_materialType}, health {w.m_health}, new={(w.m_new ? w.m_new.name : "-")}, worn={(w.m_worn ? w.m_worn.name : "-")}, broken={(w.m_broken ? w.m_broken.name : "-")}");
        if (go.GetComponent<Piece>() is { } p)
            sb.AppendLine($"Piece '{p.m_name}' groundOnly={p.m_groundOnly} groundPiece={p.m_groundPiece} notOnFloor={p.m_notOnFloor} notOnTilting={p.m_notOnTiltingSurface} station={(p.m_craftingStation ? p.m_craftingStation.name : "-")} "
                + "cost=" + string.Join(",", p.m_resources.Select(r => $"{(r.m_resItem ? r.m_resItem.name : "?")}:{r.m_amount}")));
        Plugin.Log.LogInfo(sb.ToString());
    }

    static void Walk(Transform t, int depth, StringBuilder sb)
    {
        var ind = new string(' ', depth * 2);
        var go = t.gameObject;
        sb.Append(ind).Append(t.name).Append(go.activeSelf ? "" : " (inactive)").Append($" layer={LayerMask.LayerToName(go.layer)} pos={t.localPosition:F3} rot={t.localRotation:F3} scale={t.localScale:F3}");
        var comps = go.GetComponents<Component>().Where(x => x && x is not Transform).Select(x => x.GetType().Name);
        sb.Append(" [").Append(string.Join(", ", comps)).AppendLine("]");
        if (go.GetComponent<MeshFilter>() is { } mf && mf.sharedMesh)
            sb.AppendLine($"{ind}  mesh '{mf.sharedMesh.name}' {mf.sharedMesh.vertexCount} verts, {mf.sharedMesh.subMeshCount} submesh, bounds c={mf.sharedMesh.bounds.center:F3} s={mf.sharedMesh.bounds.size:F3}");
        if (go.GetComponent<Renderer>() is { } r)
            sb.AppendLine($"{ind}  {r.GetType().Name} enabled={r.enabled} shadows={r.shadowCastingMode} mats=" + string.Join(", ", r.sharedMaterials.Select(m => m ? $"{m.name} ({(m.shader ? m.shader.name : "?")})" : "null")));
        foreach (var col in go.GetComponents<Collider>())
            sb.AppendLine(ind + "  " + col switch
            {
                BoxCollider b => $"BoxCollider c={b.center:F3} s={b.size:F3} trigger={b.isTrigger}",
                MeshCollider m => $"MeshCollider mesh='{(m.sharedMesh ? m.sharedMesh.name : "-")}' convex={m.convex} trigger={m.isTrigger}",
                _ => $"{col.GetType().Name} trigger={col.isTrigger}",
            });
        if (go.GetComponent<LODGroup>() is { } g)
        {
            var lods = g.GetLODs();
            for (int i = 0; i < lods.Length; i++)
                sb.AppendLine($"{ind}  LOD{i} @{lods[i].screenRelativeTransitionHeight:F3}: " + string.Join(", ", lods[i].renderers.Where(x => x).Select(x => x.name)));
        }
        if (go.GetComponent<Animator>() is { } an)
            sb.AppendLine($"{ind}  Animator controller='{(an.runtimeAnimatorController ? an.runtimeAnimatorController.name : "-")}' params=" + (an.runtimeAnimatorController ? string.Join(",", an.parameters.Select(x => x.name)) : ""));
        if (go.GetComponent<Animation>() is { } anim)
            sb.AppendLine($"{ind}  Animation clips=" + string.Join(",", anim.Cast<AnimationState>().Select(s => s.name)));
        foreach (Transform child in t) Walk(child, depth + 1, sb);
    }
}

static class Patches
{
    static readonly AccessTools.FieldRef<InventoryGrid, Inventory> GridInventory = AccessTools.FieldRefAccess<InventoryGrid, Inventory>("m_inventory");
    static readonly AccessTools.FieldRef<InventoryGui, Container> GuiContainer = AccessTools.FieldRefAccess<InventoryGui, Container>("m_currentContainer");
    static readonly AccessTools.FieldRef<InventoryGui, InventoryGrid> GuiContainerGrid = AccessTools.FieldRefAccess<InventoryGui, InventoryGrid>("m_containerGrid");
    static bool uiChecked;

    // Stacking (Joost): an outdoor store placed on other objects must rest on all four bottom corners; on terrain it may stand
    // as it lands (being refused there is just annoying). Each bottom snap point casts a short ray down; the ghost turns red
    // ("Invalid placement") when a corner has nothing under it within 15 cm.
    static readonly AccessTools.FieldRef<Player, GameObject> Ghost = AccessTools.FieldRefAccess<Player, GameObject>("m_placementGhost");
    static readonly AccessTools.FieldRef<Player, Player.PlacementStatus> Status = AccessTools.FieldRefAccess<Player, Player.PlacementStatus>("m_placementStatus");
    static readonly AccessTools.FieldRef<Player, int> RayMask = AccessTools.FieldRefAccess<Player, int>("m_placeRayMask");
    static readonly RaycastHit[] hits = new RaycastHit[16];

    [HarmonyPatch(typeof(Player), "UpdatePlacementGhost"), HarmonyPostfix]
    static void FourCorners(Player __instance)
    {
        if (!Plugin.Live || Status(__instance) != Player.PlacementStatus.Valid) return;
        var ghost = Ghost(__instance);
        if (!ghost || !ghost.name.StartsWith("piece_storehouse_", StringComparison.Ordinal)) return;
        var corners = new List<Vector3>();
        float low = float.MaxValue;
        foreach (Transform t in ghost.transform)
            if (t.name.StartsWith("storehouse_snap_", StringComparison.Ordinal)) low = Mathf.Min(low, t.localPosition.y);
        foreach (Transform t in ghost.transform)
            if (t.name.StartsWith("storehouse_snap_", StringComparison.Ordinal) && Mathf.Abs(t.localPosition.y - low) < 0.01f) corners.Add(t.position);
        if (corners.Count < 4) return;   // not a stackable store
        int mask = RayMask(__instance);
        bool onTerrain = false, allHeld = true;
        foreach (var c in corners)
        {
            var inward = (ghost.transform.position - c); inward.y = 0f;
            // From well above the corner (Joost, 22 Oct: a crib on bumpy but level ground was refused, and not even shown red: a
            // corner a few cm into the ground saw nothing from 10 cm up). A corner at or in the terrain counts as resting on it.
            var foot = c + inward.normalized * 0.08f;
            if (ZoneSystem.instance && ZoneSystem.instance.GetGroundHeight(foot) >= foot.y - 0.15f) { onTerrain = true; continue; }
            int n = Physics.RaycastNonAlloc(foot + Vector3.up * 0.5f, Vector3.down, hits, 0.65f, mask);
            bool held = false;
            for (int i = 0; i < n; i++)
            {
                if (hits[i].collider.transform.IsChildOf(ghost.transform)) continue;
                held = true;
                if (hits[i].collider.GetComponentInParent<Heightmap>()) onTerrain = true;
            }
            allHeld &= held;
        }
        if (allHeld || onTerrain) return;
        Status(__instance) = Player.PlacementStatus.Invalid;
        SetGhostValid?.Invoke(__instance, new object[] { false });   // red, like every other refusal (the game colours it before we run)
    }

    static readonly System.Reflection.MethodInfo SetGhostValid = AccessTools.Method(typeof(Player), "SetPlacementGhostValid");

    // Size comes from the (server-synced) config at the moment each chest is created, before its inventory exists.
    [HarmonyPatch(typeof(Container), "Awake"), HarmonyPrefix]
    static void ContainerAwake(Container __instance)
    {
        if (!Plugin.Live) return;   // every patch: a copy that has left (live reload) does nothing
        var kind = Kinds.ByToken(__instance.m_name);
        if (kind == null) return;
        __instance.m_width = kind.Width;
        __instance.m_height = kind.Height;
    }

    // A store whose chest got fewer rows (Arsenal B, 27 Oct: 8 rows -> 4, chest = its places) never loses access to what it holds.
    // Valheim loads stacks below the grid but shows no row for them: a placed store keeps the rows its stacks lie in, and takes the
    // new size once it holds no more than that, its lower stacks moved up into free slots (by the owner; the others follow its save).
    static readonly AccessTools.FieldRef<Inventory, int> InvRows = AccessTools.FieldRefAccess<Inventory, int>("m_height");
    static readonly MethodInfo invChanged = AccessTools.Method(typeof(Inventory), "Changed");
    static bool fitting;

    [HarmonyPatch(typeof(Container), "Load"), HarmonyPostfix]
    static void ContainerLoaded(Container __instance) => KeepRows(__instance);

    [HarmonyPatch(typeof(Container), "OnContainerChanged"), HarmonyPostfix]
    static void ContainerChanged(Container __instance) => KeepRows(__instance);

    static void KeepRows(Container c)
    {
        if (!Plugin.Live || fitting || Kinds.ByToken(c.m_name) is not { } kind || Mannequins.Is(kind) || c.GetInventory() is not { } inv) return;
        if (TypedSlots.Model(kind) != null) { TypedSlots.Fit(c); return; }   // its window is its places: sized and kept by the blocks
        var items = inv.GetAllItems();
        int want = kind.Height, have = inv.GetHeight(), lowest = items.Count == 0 ? -1 : items.Max(i => i.m_gridPos.y);
        if (lowest >= have)
        {
            Plugin.Log.LogInfo($"{kind.Title}: keeps {lowest + 1} rows for now (stacks lie below its {want}); it takes {want} once it holds {want * inv.GetWidth()} or fewer.");
            InvRows(inv) = c.m_height = have = lowest + 1;
        }
        if (have <= want || items.Count > want * inv.GetWidth() || c.GetComponent<ZNetView>() is not { } nview || !nview.IsOwner()) return;
        fitting = true;
        try
        {
            var free = (from y in Enumerable.Range(0, want) from x in Enumerable.Range(0, inv.GetWidth()) where inv.GetItemAt(x, y) == null select new Vector2i(x, y)).ToList();
            var below = items.Where(i => i.m_gridPos.y >= want).ToList();
            for (int k = 0; k < below.Count; k++) below[k].m_gridPos = free[k];
            InvRows(inv) = c.m_height = want;
            Plugin.Log.LogInfo($"{kind.Title}: {have} -> {want} rows, {items.Count} stack(s) fit ({below.Count} moved up).");
            invChanged?.Invoke(inv, invChanged.GetParameters().Select(p => p.HasDefaultValue ? p.DefaultValue : p.ParameterType.IsValueType ? Activator.CreateInstance(p.ParameterType) : null).ToArray());
        }
        finally { fitting = false; }
    }

    // LumberCamp, MiningCamp and hoppers ask this before they move anything.
    [HarmonyPatch(typeof(Inventory), nameof(Inventory.CanAddItem), new[] { typeof(ItemDrop.ItemData), typeof(int) }), HarmonyPostfix]
    static void CanAdd(Inventory __instance, ItemDrop.ItemData item, int stack, ref bool __result)
    {
        if (__result && Plugin.Live && !LoadGuard.Loading && Filter.For(__instance) is { } f && !f.AllowsIn(__instance, item, out _, stack)) __result = false;
    }

    // Every way an item gets into an inventory. First in line, so MultiUserChest (which re-routes adds to the chest's owner
    // and checks __runOriginal) never sends a refused item on.
    // An armory (Joost, 25 Oct 18:38: "you can only throw in three chest pieces and three helmets"): a piece without a position goes to
    // the first free place of its own row, a position in another row moves to its own row; nothing lands where it can't be worn.
    [HarmonyPatch(typeof(Inventory), nameof(Inventory.AddItem), new[] { typeof(ItemDrop.ItemData) }), HarmonyPrefix, HarmonyPriority(Priority.First)]
    static bool Add1(Inventory __instance, ItemDrop.ItemData item, ref bool __result)
    {
        if (!Check(__instance, item, ref __result)) return false;
        if (LoadGuard.Loading || !Plugin.Live || !Mannequins.Holds(__instance) && !TypedSlots.Holds(__instance)) return true;
        int x = -1, y = -1;
        if (!Typed(__instance, item, ref x, ref y, ref __result)) return false;
        __result = __instance.AddItem(item, new Vector2i(x, y));
        if (!__result) SaidNo(__instance, item);
        return false;
    }

    // Our no stands (Joost, 31 Oct: Store All into the Ember Cabinet ate the backpacks in his inventory). Adventure Backpacks' own
    // AddItem prefix doesn't look at __runOriginal: for a backpack it writes its own answer ("not a backpack in a backpack, so yes")
    // over our refusal. The add then reports true while nothing was added, and the caller (Quick Stack's Store All, vanilla's
    // shift-click) takes the item out of the player's inventory. Last in line, every add route puts our no back, whoever came after us.
    [ThreadStatic] static ItemDrop.ItemData noItem;
    [ThreadStatic] static Inventory noInv;

    static void SaidNo(Inventory inv, ItemDrop.ItemData item) { noInv = inv; noItem = item; }

    static void HoldNo(Inventory inv, ItemDrop.ItemData item, ref bool result)
    {
        if (noItem == null || noItem != item || noInv != inv) return;
        noItem = null; noInv = null;
        if (result)
            Plugin.Log.LogWarning($"{Kinds.ByToken(inv.GetName())?.Title ?? inv.GetName()}: another mod answered yes after Storehouse refused {Filter.Name(item)}; the refusal stands, it stays where it was.");
        result = false;
    }

    [HarmonyPatch(typeof(Inventory), nameof(Inventory.AddItem), new[] { typeof(ItemDrop.ItemData) }), HarmonyPostfix, HarmonyPriority(Priority.Last)]
    static void Held1(Inventory __instance, ItemDrop.ItemData item, ref bool __result) => HoldNo(__instance, item, ref __result);

    [HarmonyPatch(typeof(Inventory), nameof(Inventory.AddItem), new[] { typeof(ItemDrop.ItemData), typeof(Vector2i) }), HarmonyPostfix, HarmonyPriority(Priority.Last)]
    static void Held2(Inventory __instance, ItemDrop.ItemData item, ref bool __result) => HoldNo(__instance, item, ref __result);

    [HarmonyPatch(typeof(Inventory), "AddItem", new[] { typeof(ItemDrop.ItemData), typeof(int), typeof(int), typeof(int), typeof(bool) }), HarmonyPostfix, HarmonyPriority(Priority.Last)]
    static void Held3(Inventory __instance, ItemDrop.ItemData item, ref bool __result) => HoldNo(__instance, item, ref __result);

    [HarmonyPatch(typeof(Inventory), nameof(Inventory.AddItem), new[] { typeof(ItemDrop.ItemData), typeof(Vector2i) }), HarmonyPrefix, HarmonyPriority(Priority.First)]
    static bool Add2(Inventory __instance, ItemDrop.ItemData item, ref Vector2i pos, ref bool __result)
    {
        if (!Check(__instance, item, ref __result)) return false;
        int x = pos.x, y = pos.y;
        if (!Typed(__instance, item, ref x, ref y, ref __result)) return false;
        pos = new Vector2i(x, y);
        return true;
    }

    // The private AddItem(item, amount, x, y, skipValidPositionCheck): drag and drop, MoveAll, and loading a saved chest.
    [HarmonyPatch(typeof(Inventory), "AddItem", new[] { typeof(ItemDrop.ItemData), typeof(int), typeof(int), typeof(int), typeof(bool) }), HarmonyPrefix, HarmonyPriority(Priority.First)]
    static bool Add3(Inventory __instance, ItemDrop.ItemData item, int amount, ref int x, ref int y, ref bool __result) =>
        Check(__instance, item, ref __result, amount, new Vector2i(x, y)) && Typed(__instance, item, ref x, ref y, ref __result);

    static bool Typed(Inventory inv, ItemDrop.ItemData item, ref int x, ref int y, ref bool result)
    {
        if (LoadGuard.Loading || !Plugin.Live) return true;
        bool armory = Mannequins.Holds(inv);
        if (!armory && !TypedSlots.Holds(inv)) return true;
        if (armory ? Mannequins.Place(inv, item, ref x, ref y, out var why) : TypedSlots.Place(inv, item, ref x, ref y, out why)) return true;
        if (InventoryGui.IsVisible() && Player.m_localPlayer && Player.m_localPlayer.GetInventory().ContainsItem(item)) Filter.For(inv)?.Refuse(item, why);
        SaidNo(inv, item);
        result = false;
        return false;
    }

    static bool Check(Inventory inv, ItemDrop.ItemData item, ref bool result, int amount = -1, Vector2i? at = null)
    {
        if (LoadGuard.Loading || !Plugin.Live) return true;
        var f = Filter.For(inv);
        if (f == null || f.AllowsIn(inv, item, out var why, amount, at)) return true;
        if (InventoryGui.IsVisible() && Player.m_localPlayer && Player.m_localPlayer.GetInventory().ContainsItem(item)) f.Refuse(item, why);
        SaidNo(inv, item);
        result = false;
        return false;
    }

    // Drag and drop onto a chest slot that holds something else swaps the two: vanilla removes the dragged item first and
    // adds it last, so a refusal there would lose it. Refuse the whole drop up front instead (both directions of the swap).
    [HarmonyPatch(typeof(InventoryGrid), nameof(InventoryGrid.DropItem)), HarmonyPrefix, HarmonyPriority(Priority.First)]
    static bool DropItem(InventoryGrid __instance, Inventory fromInventory, ItemDrop.ItemData item, int amount, ref Vector2i pos, ref bool __result)
    {
        if (!Plugin.Live) return true;
        var to = GridInventory(__instance);
        if (to == null || item == null) return true;
        var toFilter = Filter.For(to);
        var fromFilter = Filter.For(fromInventory);
        if (toFilter == null && fromFilter == null) return true;
        if (Mannequins.Holds(to))
        {
            // Its own row: the cell dropped on (a swap with the piece there is fine), else the row's first free place.
            int x = pos.x, y = pos.y;
            string no = null;
            if (!toFilter.Allows(item) || !Mannequins.Place(to, item, ref x, ref y, out no)) { toFilter.Refuse(item, no); __result = false; return false; }
            pos = new Vector2i(x, y);
        }
        else if (toFilter != null && TypedSlots.Holds(to))
        {
            // A block that takes it: the cell dropped on when free, else its block's first free cell (TypedSlots.Cell). A drop on another
            // piece swaps the two (as vanilla does below): judged with that piece gone, so a full store still trades one for another.
            int x = pos.x, y = pos.y;
            var held = to.GetItemAt(pos.x, pos.y);
            var leaving = held != null && held != item && fromInventory != to && item.m_stack == amount && (held.m_shared.m_name != item.m_shared.m_name
                || (item.m_shared.m_maxQuality > 1 && held.m_quality != item.m_quality) || held.m_shared.m_maxStackSize == 1) ? held : null;
            string no = null;
            if (!toFilter.Allows(item) || !TypedSlots.Place(to, item, ref x, ref y, out no, leaving)) { toFilter.Refuse(item, no); __result = false; return false; }
            pos = new Vector2i(x, y);
        }
        else if (toFilter != null && !toFilter.AllowsIn(to, item, out var why, amount, pos)) { toFilter.Refuse(item, why); __result = false; return false; }
        var at = to.GetItemAt(pos.x, pos.y);
        bool swap = at != null && at != item && (at.m_shared.m_name != item.m_shared.m_name || (item.m_shared.m_maxQuality > 1 && at.m_quality != item.m_quality) || at.m_shared.m_maxStackSize == 1) && item.m_stack == amount;
        if (swap && fromFilter != null && !fromFilter.Allows(at)) { fromFilter.Refuse(at); __result = false; return false; }
        // The swapped-out item lands where the dragged one was; a bay store it goes back into needs a bay for it (the swap's add can't
        // be refused halfway: the dragged item is out by then).
        if (swap && fromFilter is { KindPerBay: true } && fromInventory != to && !fromFilter.AllowsIn(fromInventory, at, out var back, at.m_stack, item.m_gridPos)) { fromFilter.Refuse(at, back); __result = false; return false; }
        return true;
    }

    // Shift-click into a store (Joost, 29 Oct: backpacks shift-clicked into the Armory Island left his inventory and never showed up in
    // it). The move is judged up front, as a drop is: what the store refuses never starts moving. Afterwards the item has to be somewhere:
    // still with the player, or in the store. When neither holds it and this player owns the store (so no MultiUserChest request is on
    // its way to another owner), it goes back to the player and the log says so. Every shift-click into a store is logged.
    // 0.8.5 (Joost's log, 31 Oct: Frozen Fuel shift-clicked into the Ember Cabinet "left the player but is not in the store" four times,
    // then landed): a stack that joins a stack already in the store is in the store by count, not as the same object. Put back only what
    // the count says is gone from both, else the guard doubles what it should protect.
    struct MoveState { public bool Watch, Had, Owner; public int Stack, Total; public string Name; }

    // How many of this item the two inventories hold together, by its name, read from the lists themselves
    // (Adventure Backpacks' CountItems patch adds what's in an equipped backpack).
    static int Held(Inventory a, Inventory b, ItemDrop.ItemData item)
    {
        string n = item.m_shared?.m_name;
        int sum = 0;
        foreach (var inv in new[] { a, b })
            foreach (var i in inv.GetAllItems())
                if (i.m_shared?.m_name == n) sum += i.m_stack;
        return sum;
    }

    [HarmonyPatch(typeof(Inventory), nameof(Inventory.MoveItemToThis), new[] { typeof(Inventory), typeof(ItemDrop.ItemData) }), HarmonyPrefix, HarmonyPriority(Priority.First)]
    static bool MoveIn(Inventory __instance, Inventory fromInventory, ItemDrop.ItemData item, out MoveState __state)
    {
        __state = default;
        if (!Plugin.Live || LoadGuard.Loading || item == null || fromInventory == null || fromInventory == __instance) return true;
        var f = Filter.For(__instance);
        if (f == null) return true;
        string name = item.m_dropPrefab ? item.m_dropPrefab.name : item.m_shared?.m_name ?? "?";
        string title = Kinds.ByToken(__instance.GetName())?.Title ?? __instance.GetName();
        var c = InventoryGui.instance ? GuiContainer(InventoryGui.instance) : null;
        bool owner = c && c.GetInventory() == __instance && c.GetComponent<ZNetView>() is { } nv && nv.IsValid() && nv.IsOwner();
        int x = -1, y = -1;
        string why = null;
        bool ok = f.AllowsIn(__instance, item, out why, item.m_stack)
            && (Mannequins.Holds(__instance) ? Mannequins.Place(__instance, item, ref x, ref y, out why)
                : !TypedSlots.Holds(__instance) || TypedSlots.Place(__instance, item, ref x, ref y, out why));
        if (!ok)
        {
            Plugin.Log.LogInfo($"Shift-click: {name} x{item.m_stack} into {title} refused up front ({why ?? "not taken"}); it stays where it was.");
            f.Refuse(item, why);
            return false;
        }
        __state = new MoveState { Watch = true, Had = fromInventory.ContainsItem(item), Owner = owner, Stack = item.m_stack, Total = Held(fromInventory, __instance, item), Name = name };
        return true;
    }

    [HarmonyPatch(typeof(Inventory), nameof(Inventory.MoveItemToThis), new[] { typeof(Inventory), typeof(ItemDrop.ItemData) }), HarmonyPostfix, HarmonyPriority(Priority.Last)]
    static void MovedIn(Inventory __instance, Inventory fromInventory, ItemDrop.ItemData item, MoveState __state)
    {
        if (!__state.Watch) return;
        bool withPlayer = fromInventory.ContainsItem(item), inStore = __instance.ContainsItem(item);
        string title = Kinds.ByToken(__instance.GetName())?.Title ?? __instance.GetName();
        string owned = __state.Owner ? "" : " (the store is owned by another peer)";
        if (withPlayer || inStore || !__state.Had)
        {
            Plugin.Log.LogInfo($"Shift-click: {__state.Name} x{__state.Stack} into {title}: {(inStore ? "in the store" : withPlayer ? "still with the player" : "not tracked")}{owned}.");
            return;
        }
        if (!__state.Owner) { Plugin.Log.LogInfo($"Shift-click: {__state.Name} x{__state.Stack} into {title}: sent to the store's owner{owned}."); return; }
        if (item.m_stack <= 0 || Held(fromInventory, __instance, item) >= __state.Total)
        {
            Plugin.Log.LogInfo($"Shift-click: {__state.Name} x{__state.Stack} into {title}: stacked onto what the store held.");
            return;
        }
        bool back = fromInventory.AddItem(item);
        Plugin.Log.LogError($"Shift-click: {__state.Name} x{__state.Stack} into {title} left the player but is not in the store; {(back ? "put back with the player" : "COULD NOT be put back")}.");
    }

    [HarmonyPatch(typeof(Container), nameof(Container.GetHoverText)), HarmonyPostfix]
    static void Hover(Container __instance, ref string __result)
    {
        if (!Plugin.Live) return;
        var kind = Kinds.ByToken(__instance.m_name);
        if (kind == null || string.IsNullOrEmpty(__result)) return;
        if (kind.Filter != null) __result += $"\n<color=#b0a890>{kind.Filter.Label}</color>";
        if (kind.Filter is { KindPerBay: true } bayFilter && bayFilter.BayUse(__instance.GetInventory()) is { bays: > 0 } use)
            __result += $"\n<color=#b0a890>Bays: {use.used}/{use.bays}</color>";
#if DEV
        int unseen = __instance.GetComponentsInChildren<StoreContents>(true).Select(contents => contents.UnrepresentedKindCount).DefaultIfEmpty(0).Max();
        if (unseen > 0) __result += $"\n<color=#e0bd7c>{unseen} stored {(unseen == 1 ? "kind has" : "kinds have")} no display place. Open the inventory.</color>";
        int more = __instance.GetComponentsInChildren<StoreContents>(true).Select(contents => contents.MoreInStorage).DefaultIfEmpty(0).Max();
        if (more > 0) __result += Mannequins.Is(kind) ? $"\n<color=#b0a890>{more} {(more == 1 ? "piece" : "pieces")} not worn.</color>"
            : $"\n<color=#b0a890>{more} more in storage.</color>";
        if (Mannequins.Is(kind) && Mannequins.Counts(__instance) is { } counts) __result += $"\n<color=#b0a890>{counts}</color>";
        if (Mannequins.Is(kind) && Mannequins.Legend(__instance) is { } legend) __result += $"\n<color=#b0a890>{legend}</color>";
        if (TypedSlots.Counts(__instance) is { } blocks) __result += $"\n<color=#b0a890>{blocks}</color>";
        // The Timber Crib's logs show how full it is, not what lies in it (review 25 Oct): its kinds by name. Only the logs are drawn
        // (Joost, 27 Oct: "stick with just showing the logs and don't show anything else"; the sill samples are gone).
        if (kind == Kinds.Crib && __instance.GetInventory() is { } cribInv)
        {
            var held = cribInv.GetAllItems().Where(i => i?.m_shared != null).GroupBy(i => i.m_shared.m_name)
                .OrderByDescending(g => g.Sum(i => i.m_stack)).Select(g => Localization.instance.Localize(g.Key)).ToList();
            if (held.Count > 1) __result += $"\n<color=#b0a890>Holds {string.Join(", ", held.Take(6))}{(held.Count > 6 ? $" and {held.Count - 6} more" : "")}</color>";
        }
#endif
    }

    // Our stores open on their items (fix list F6; issue #2, ShadowTox: a sort or filter mod put them top left, and opening at the
    // bottom showed empty rows; design by Astra Finn, 1 Nov): the first row holding an item at the top of the view, as far as the
    // grid scrolls; an empty store at the top. What the game puts in the bottom rows (Inventory.TopFirst, Quick Stack Store's Sort)
    // still opens at the bottom, as before (Joost). The row is chosen once, when the store opens: putting items in while it is open
    // never moves the view. Again whenever the window or the grid changes size while it is open (StorehouseUI grows the window after
    // it opens, which left the view halfway, Joost), until you scroll by hand: from then on the view is yours. Only the scroll view;
    // no item moves.
    static Container scrolledFor;
    static int scrollFrames;
    static float openedAt;
    static Vector2 scrolledSize;
    static int openRow;                   // the first row with an item when the store opened; -1: empty
    static float placedAt = float.NaN;    // where we last put the view: a different position at the same size is a hand scroll
    static bool handScrolled;
    static readonly AccessTools.FieldRef<InventoryGrid, List<InventoryElement>> GridCells = AccessTools.FieldRefAccess<InventoryGrid, List<InventoryElement>>("m_elements");
    // After StorehouseUI's postfix (Priority.Last; its Harmony id changes per load, so HarmonyAfter cannot name it): it grows the
    // window in the same frame, and placing the view before that drew one frame at the old size (Joost, 1 Nov: "you can see it twitch").
    [HarmonyPatch(typeof(InventoryGui), "UpdateContainer"), HarmonyPostfix, HarmonyPriority(Priority.Last - 1)]
    static void OpenAtItems(InventoryGui __instance)
    {
        if (!Plugin.Live) return;
        var c = GuiContainer(__instance);
        if (!c) { scrolledFor = null; return; }
        if (c != scrolledFor) { scrolledFor = c; scrollFrames = 3; openedAt = Time.unscaledTime; handScrolled = false; placedAt = float.NaN; }
        if (handScrolled || Kinds.ByToken(c.m_name) == null) return;
        var grid = GuiContainerGrid(__instance);
        if (!grid || grid.GetComponentInParent<ScrollRect>() is not { } scroll || !scroll || !scroll.content) return;
        var view = scroll.viewport ? scroll.viewport : (RectTransform)scroll.transform;   // no viewport set: Unity scrolls in its own rect
        float age = Time.unscaledTime - openedAt;
        bool settling = age <= 0.5f;   // the game and StorehouseUI lay the window out in turns: the view is ours, whatever moves it
        if (settling)   // the row is read until the window settles: the items can arrive a frame after the window opens
            openRow = c.GetInventory()?.GetAllItems() is { } items && items.Any(i => i != null) ? items.Where(i => i != null).Min(i => i.m_gridPos.y) : -1;
        var size = new Vector2(view.rect.height, scroll.content.rect.height);
        float now = scroll.verticalNormalizedPosition;
        if (size != scrolledSize) { scrolledSize = size; scrollFrames = Mathf.Max(scrollFrames, 2); }   // the layout moved it, not a hand
        else if (!settling && scrollFrames <= 0 && !float.IsNaN(placedAt) && Mathf.Abs(now - placedAt) > 0.002f)
        {
            handScrolled = true;
            return;
        }
        if (!settling && scrollFrames <= 0) return;   // after the first half second: only a few frames after each size change
        if (!settling) scrollFrames--;
        scroll.velocity = Vector2.zero;
        scroll.verticalNormalizedPosition = placedAt = RowAtTop(grid, scroll, view, openRow);
    }

    // The scroll position (1 top, 0 bottom) that puts this row's top edge at the top of the view, from the cell's own rectangle in
    // the scrolled content (not a row count times a guessed height). Empty, unknown or not scrollable: the top.
    static float RowAtTop(InventoryGrid grid, ScrollRect scroll, RectTransform view, int row)
    {
        float range = scroll.content.rect.height - view.rect.height;
        if (row < 0 || range <= 0.5f) return 1f;
        var cell = GridCells(grid)?.FirstOrDefault(e => e && e.Position.y == row);
        if (cell == null) return 1f;
        var corners = new Vector3[4];
        ((RectTransform)cell.transform).GetWorldCorners(corners);   // [1]: the top left corner
        float fromTop = scroll.content.rect.yMax - scroll.content.InverseTransformPoint(corners[1]).y;
        return Mathf.Clamp01(1f - fromTop / range);
    }

    // Once per session: confirm in the log that the container grid scrolls for our 8-wide, 6-8 row chests.
    [HarmonyPatch(typeof(InventoryGui), "UpdateContainer"), HarmonyPostfix]
    static void UiCheck(InventoryGui __instance)
    {
        if (uiChecked || !Plugin.Live) return;
        var c = GuiContainer(__instance);
        if (!c || Kinds.ByToken(c.m_name) == null) return;
        var grid = GuiContainerGrid(__instance);
        if (!grid) return;
        uiChecked = true;
        var scroll = grid.GetComponentInParent<ScrollRect>();
        var view = (RectTransform)grid.transform;
        Plugin.Log.LogInfo($"Container UI: {c.GetInventory().GetWidth()}x{c.GetInventory().GetHeight()} grid; scroll view {(scroll ? "present" : "MISSING")}, "
            + $"scrollbar {(grid.m_scrollbar ? "present" : "missing")}, viewport {view.rect.height:0} px, grid {grid.m_gridRoot.rect.height:0} px.");
    }
}

// True while an inventory is being read from the world (Inventory.Load), so the filter never drops items already stored.
[HarmonyPatch]
static class LoadGuard
{
    [ThreadStatic] static int depth;
    public static bool Loading => depth > 0;

    static IEnumerable<MethodBase> TargetMethods() =>
        typeof(Inventory).GetMethods(BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic)
            .Where(m => m.Name == "Load" && m.GetParameters().FirstOrDefault()?.ParameterType == typeof(ZPackage));

    static void Prefix() => depth++;
    static Exception Finalizer(Exception __exception) { depth--; return __exception; }
}

#if DEV
// =====================================================================================================================
// Dev build only: the seven round-2 stores (pieces in your own worlds) and skin mode (any vanilla chest, this PC only).
// =====================================================================================================================

// Content anchors. The seven Blender scripts (blender/<slug>_r2.py) each wrote their own JSON layout. They agree on the
// space (Unity prefab space, metres, y up, +z front) and on the fill order (units listed in the order stacks fill them,
// one stack per unit), and differ in key names and in how a copy is sized. Anchors.Parse reads all seven into one shape:
//   StoreUnit  Pos, Rot, Box (the space the unit may fill), Demo (the item the render used), Copies (in fill order)
//   StoreCopy  Offset (unit space) and Rot, then:
//     Align   None | LongX (turn the item's longest bounds axis onto x: root bin) | LongYaw (turn about up only, so the
//             longest flat side runs along x: emergency shelf) | Axes (longest axis onto LongTo, thinnest onto ThinTo: meat rack)
//     Fit     Box (scale the aligned item uniformly to fit inside FitBox) | Longest (longest side = Longest metres: ore bin,
//             meat rack) | Volume (bounds volume = Scale^3 x the demo item's: bunker, which sized its heaps by volume)
//     Bottom  the bottom centre of the fitted bounds sits at Offset; otherwise the bounds centre does
//     Layer   stacked copies (larder, shelf) are lifted by Layer x Pitch x their own fitted height
//   A copy turns about its bounds centre. FitAfterRotation: the box fit includes the copy's own turn (the larder's rule).
// Item space: the scripts placed the item meshes in Blender space and converted the result with ux=-bx, uz=-by, which for
// an item is a half turn about up compared with the game's own item space. So every item model is turned 180 degrees about
// up before it is placed (ItemVisual). Checked against the meat rack's rendered rotations: exact to 4 decimals.
// Round 3 (physics-settled copies) keeps each store's schema, so it parses the same way.
enum Align { None, LongX, LongYaw, Axes }
enum Fit { Box, Longest, Volume }

// Broad heaps of related kinds (A's ossuary_layouts.json, schema storehouse.ossuary.floor_piles.v1, Sol 6.1 / extra high; review
// 25 Oct: "related bones mix in broad heaps, each kind recognisable"). Six bays, each home to some kinds. Per kind a "mixed" region
// in its home bay (its share when the bay's other home kinds are there too), and per bay a "whole" alternative (the whole bay of
// that kind). Every region lists its copies in a prefix-safe order: copy k only ever rests on copies before it of the same kind,
// so showing the first n is always physically sound. The recipe (its allocation_policy):
//   a bay with two or more of its home kinds present: each one's mixed region;
//   a bay with one home kind present: that kind's whole-bay alternative;
//   a bay with none: the whole-bay alternative of a present kind, by stock (largest average per bay, ties in the layout's order);
//   how much of a kind's regions shows follows its stock (the recipe's "quantity": q = desired over assigned nominal volume,
//   F = all stock over the slots, fraction = q + F^4 (1 - q), so a full store saturates every region);
//   a kind of at most one full stack whose floor seeds are all hidden from the working side shows only its identity sample, and
//   its heaps go to the others ("sparse_hidden_kind");
//   a kind none of whose shown copies can be seen from the working side has its last shown copy replaced by its identity sample
//   ("hidden_pile_kind"; the full-mixed sight test when several kinds lie there, else the frame-only one).
sealed class FloorPiles
{
    public sealed class Copy { public string Id; public Vector3 Pos; public Quaternion Rot; public float Longest; public bool FrameVisible, MixedVisible; }
    public sealed class Region { public string Id; public int Bay; public string Item; public float Volume; public readonly List<Copy> Copies = new(); }
    // One shown copy, with the display sidecar's keys (Ossuary r5b): its region and copy ids and the region's prefix count, the copies
    // shown from it. An identity sample stands outside every prefix (Region null, Prefix 0).
    public readonly struct Shown
    {
        public readonly string Item, Region, Copy;
        public readonly Vector3 Pos;
        public readonly Quaternion Rot;
        public readonly float Longest;
        public readonly int Prefix;
        public Shown(string item, Copy c, string region, int prefix) { Item = item; Pos = c.Pos; Rot = c.Rot; Longest = c.Longest; Copy = c.Id; Region = region; Prefix = prefix; }
    }
    public readonly List<string> Kinds = new();                                  // supported, in the layout's order
    public readonly Dictionary<string, Region> Mixed = new(StringComparer.Ordinal);
    public readonly Dictionary<(string, int), Region> Whole = new();
    public readonly Dictionary<string, Copy> Identity = new(StringComparer.Ordinal);
    public readonly SortedSet<int> Bays = new();
    public int FrameTris;   // the layouts' frame.tris: the display budget counts the frame

    public static FloorPiles Parse(Dictionary<string, object> doc)
    {
        if (doc == null || !(doc.TryGetValue("schema", out var sc) && sc is string schema && schema.EndsWith("floor_piles.v1", StringComparison.Ordinal))) return null;
        var p = new FloorPiles();
        if (doc.TryGetValue("supported_prefabs", out var sp) && sp is List<object> kinds) p.Kinds.AddRange(kinds.OfType<string>());
        if (Json.Obj(doc, "frame") is { } frame && frame.TryGetValue("tris", out var ft)) p.FrameTris = Convert.ToInt32(ft);
        static Copy ReadCopy(Dictionary<string, object> c)
        {
            var at = (List<object>)c["position"];
            var q = (List<object>)c["quat_xyzw"];
            return new Copy
            {
                Id = c.TryGetValue("id", out var id) ? id as string : null,
                Pos = new Vector3(Convert.ToSingle(at[0]), Convert.ToSingle(at[1]), Convert.ToSingle(at[2])),
                Rot = new Quaternion(Convert.ToSingle(q[0]), Convert.ToSingle(q[1]), Convert.ToSingle(q[2]), Convert.ToSingle(q[3])).normalized,
                Longest = c.TryGetValue("fit_longest_m", out var f) ? Convert.ToSingle(f) : 0.3f,
                FrameVisible = c.TryGetValue("working_side_frame_visible", out var fv) && fv is bool fb && fb,
                MixedVisible = c.TryGetValue("working_side_full_mixed_visible", out var mv) && mv is bool mb && mb,
            };
        }
        Region Read(Dictionary<string, object> r)
        {
            var region = new Region
            {
                Id = r.TryGetValue("id", out var id) ? id as string : null,
                Bay = (int)Convert.ToSingle(r["bay"]), Item = r["item"] as string,
                Volume = r.TryGetValue("nominal_volume_m3", out var v) ? Convert.ToSingle(v) : 0f,
            };
            foreach (var c in ((List<object>)r["copies"]).OfType<Dictionary<string, object>>()) region.Copies.Add(ReadCopy(c));
            if (region.Volume <= 0f) region.Volume = region.Copies.Count;   // no volume given: copies as the measure
            p.Bays.Add(region.Bay);
            return region;
        }
        foreach (var r in ((List<object>)doc["mixed_regions"]).OfType<Dictionary<string, object>>())
            if (Read(r) is { Item: not null } region) p.Mixed[region.Item] = region;
        foreach (var kv in (Dictionary<string, object>)doc["one_kind_full"])
            foreach (var r in ((List<object>)kv.Value).OfType<Dictionary<string, object>>())
                if (Read(r) is { } region) p.Whole[(kv.Key, region.Bay)] = region;
        if (doc.TryGetValue("identity_samples", out var ids) && ids is Dictionary<string, object> samples)
            foreach (var kv in samples) if (kv.Value is Dictionary<string, object> c) p.Identity[kv.Key] = ReadCopy(c);
        return p.Mixed.Count > 0 ? p : null;
    }

    // What shows for this stock (kind -> full stacks' worth, the inventory's "mass"), per copy its item, centre, turn and longest side,
    // with its region's prefix count. unseen: stored kinds the layouts have no heap for.
    public List<Shown> Select(Dictionary<string, float> mass, int slots, out int unseen)
    {
        var present = Kinds.Where(k => mass.TryGetValue(k, out float m) && m > 0f).ToList();
        unseen = mass.Keys.Count(k => mass[k] > 0f && !Kinds.Contains(k));
        var result = new List<Shown>();
        if (present.Count == 0) return result;
        // Sparse and hidden: at most one full stack, and no whole-bay floor seed of that kind visible from the working side.
        var sparse = present.Where(k => mass[k] <= 1f && Identity.ContainsKey(k)
            && Bays.All(b => !Whole.TryGetValue((k, b), out var w) || w.Copies.Count == 0 || !w.Copies[0].FrameVisible)).ToList();
        var piled = present.Where(k => !sparse.Contains(k)).ToList();
        var regions = new List<(string kind, Region region)>();
        var empty = new List<int>();
        foreach (int bay in Bays)
        {
            var homes = piled.Where(k => Mixed.TryGetValue(k, out var r) && r.Bay == bay).ToList();
            if (homes.Count >= 2) foreach (var k in homes) regions.Add((k, Mixed[k]));
            else if (homes.Count == 1 && Whole.TryGetValue((homes[0], bay), out var whole)) regions.Add((homes[0], whole));
            else if (homes.Count == 1) regions.Add((homes[0], Mixed[homes[0]]));
            else empty.Add(bay);
        }
        foreach (int bay in empty)
        {
            int Has(string k) => regions.Where(x => x.kind == k).Select(x => x.region.Bay).Distinct().Count();
            var pick = piled.Where(k => Whole.ContainsKey((k, bay))).OrderByDescending(k => mass[k] / (1 + Has(k))).ThenBy(k => Kinds.IndexOf(k)).FirstOrDefault();
            if (pick != null) regions.Add((pick, Whole[(pick, bay)]));
        }
        float stock = present.Sum(k => mass[k]);
        float allVolume = Mathf.Max(1e-6f, regions.Sum(x => x.region.Volume));
        float F = Mathf.Clamp01(stock / Mathf.Max(1, slots));
        bool several = present.Count > 1;
        foreach (var k in piled)
        {
            var mine = regions.Where(x => x.kind == k).ToList();
            float assigned = mine.Sum(x => x.region.Volume);
            if (assigned <= 0f) { unseen++; continue; }
            float q = Mathf.Min(1f, allVolume * mass[k] / Mathf.Max(1, slots) / assigned);
            float fraction = q + F * F * F * F * (1f - q);
            var shown = new List<Shown>();
            var picked = new List<Copy>();
            foreach (var (_, region) in mine)
            {
                int n = Mathf.Clamp(Mathf.CeilToInt(fraction * region.Copies.Count), 1, region.Copies.Count);
                foreach (var c in region.Copies.Take(n)) { shown.Add(new Shown(k, c, region.Id, n)); picked.Add(c); }
            }
            // Hidden pile: the last leaf becomes the kind's identity sample, never an extra copy.
            if (Identity.TryGetValue(k, out var sample) && shown.Count > 0 && !picked.Any(c => several ? c.MixedVisible : c.FrameVisible))
                shown[shown.Count - 1] = new Shown(k, sample, null, 0);
            result.AddRange(shown);
        }
        foreach (var k in sparse) result.Add(new Shown(k, Identity[k], null, 0));
        return result;
    }
}

// The Ossuary's display sidecar (r5b, storehouse.ossuary.display.v3, Sol; DISPLAY-INTEGRATION.md): the native bone meshes as exported
// from Blender, drawn in place of the game's own so the sidecar's per-face masks can leave out what no camera sees. Used only when its
// physical_export_sha256 matches the round's files (line endings ignored: git checks text out with CRLF on Windows). Version 4 (Sol,
// 25 Oct): the masks protect the front, lean-in, overhead, both sides and the back corners; the selector below is display_r5b.select
// with strict native protection, the budget at 85,000 (the coordinator). Dev builds only, until it is checked in game.
sealed class PileDisplay
{
    public sealed class KindMesh
    {
        public string Material;        // the game material's name: the Blender one without "VH_<prefab>_"
        public float TemplateLongest;  // the longest side the mesh is at; a copy scales by its fit_longest_m over this
        public Vector3[] V, N;
        public Vector4[] T;            // from the complete mesh, before any face is left out (the contract: never from the remaining faces)
        public Vector2[] UV;
        public int[] Tri;              // 3 per native face, in face order, winding reversed for Unity
        public Bounds Bounds;
        public int Faces => Tri.Length / 3;
    }
    public readonly Dictionary<string, KindMesh> Meshes = new(StringComparer.Ordinal);
    // Per region, per copy in prefix order, per native face: the last prefix count that keeps it (Keep), that needs it (Primary: seen
    // from a protected view), and its projected area in the other views (Area: what the budget pass leaves out first).
    public sealed class Region
    {
        public readonly Dictionary<string, int> Index = new(StringComparer.Ordinal);
        public int[][] Keep, Primary;
        public double[][] Area;
    }
    public readonly Dictionary<string, Region> Regions = new(StringComparer.Ordinal);
    public readonly HashSet<string> Exempt = new(StringComparer.Ordinal);   // always the whole native mesh (four tiny front exposures)
    public string Schema;
    public const int Budget = 85000;   // the coordinator, 25 Oct: the sides protected need up to 83,138 in tested stocks; half of the unmasked 170,273
    readonly Dictionary<string, Material> games = new(StringComparer.Ordinal);

    // Null when the round has no sidecar; null and why when it is for other files or can't be read.
    public static PileDisplay Load(string dir, string slug, out string why)
    {
        why = null;
        var file = Path.Combine(dir, slug + "_display.json");
        if (!File.Exists(file)) return null;
        if (Json.Parse(File.ReadAllText(file)) is not Dictionary<string, object> doc) { why = "unreadable"; return null; }
        if (Json.Obj(doc, "physical_export_sha256") is not { } sums || sums.Count == 0) { why = "no physical_export_sha256"; return null; }
        foreach (var kv in sums)
        {
            var path = Path.Combine(dir, kv.Key);
            if (!File.Exists(path)) { why = $"{kv.Key} missing"; return null; }
            if (!string.Equals(Sha(path), kv.Value as string, StringComparison.OrdinalIgnoreCase)) { why = $"{kv.Key} is not the file it was made for"; return null; }
        }
        var d = new PileDisplay { Schema = doc.TryGetValue("schema", out var sc) ? sc as string : null };
        if (d.Schema != "storehouse.ossuary.display.v4" || !(doc.TryGetValue("strict_native_protection", out var strict) && strict is bool on && on))
        { why = $"{d.Schema}: this build reads storehouse.ossuary.display.v4 with strict native protection"; return null; }
        if (Json.Obj(doc, "meshes") is { } meshes)
            foreach (var kv in meshes)
            {
                if (kv.Value is not Dictionary<string, object> levels || Json.Obj(levels, "native") is not { } native || !(native.TryGetValue("path", out var po) && po is string rel)) continue;
                var meshFile = Path.Combine(dir, rel.Replace('/', Path.DirectorySeparatorChar));
                if (!File.Exists(meshFile)) { why = $"{rel} missing"; return null; }
                if (native.TryGetValue("sha256", out var ms) && ms is string want && !string.Equals(Sha(meshFile), want, StringComparison.OrdinalIgnoreCase)) { why = $"{rel} is not the mesh it lists"; return null; }
                if (Json.Parse(File.ReadAllText(meshFile)) is not Dictionary<string, object> m) { why = $"{rel} unreadable"; return null; }
                if (Build(m, kv.Key) is { } k) d.Meshes[kv.Key] = k;
                else Plugin.Log.LogWarning($"Ossuary display: {rel} has more than one material; {kv.Key} is drawn with the game's own mesh.");
            }
        static int[][] Ints(object o) => ((List<object>)o).Select(row => ((List<object>)row).Select(x => Convert.ToInt32(x)).ToArray()).ToArray();
        if (Json.Obj(doc, "regions") is { } regions)
            foreach (var kv in regions)
            {
                if (kv.Value is not Dictionary<string, object> r) continue;
                var region = new Region
                {
                    Keep = Ints(r["face_keep_through_prefix"]),
                    Primary = Ints(r["primary_face_keep_through_prefix"]),
                    Area = ((List<object>)r["face_projected_area_extra_views"]).Select(row => ((List<object>)row).Select(x => Convert.ToDouble(x)).ToArray()).ToArray(),
                };
                var ids = ((List<object>)r["copy_ids"]).OfType<string>().ToList();
                for (int j = 0; j < ids.Count; j++) region.Index[ids[j]] = j;
                d.Regions[kv.Key] = region;
            }
        if (doc.TryGetValue("cull_exempt_copy_ids", out var ex) && ex is List<object> exempt) d.Exempt.UnionWith(exempt.OfType<string>());
        return d;
    }

    // SHA-256, hex; a text file (.obj, .json) without its carriage returns.
    static string Sha(string path)
    {
        var bytes = File.ReadAllBytes(path);
        if (path.EndsWith(".obj", StringComparison.OrdinalIgnoreCase) || path.EndsWith(".json", StringComparison.OrdinalIgnoreCase))
            bytes = bytes.Where(b => b != 13).ToArray();
        using var sha = System.Security.Cryptography.SHA256.Create();
        return BitConverter.ToString(sha.ComputeHash(bytes)).Replace("-", "").ToLowerInvariant();
    }

    // Blender (x, y, z) to Unity (-x, z, -y): a mirror, so each face's winding is reversed. Corners with the same vertex, UV and normal
    // are one vertex, so the tangents average over the faces that share it, as on the whole mesh.
    static Vector3 U(List<object> b) => new Vector3(-Convert.ToSingle(b[0]), Convert.ToSingle(b[2]), -Convert.ToSingle(b[1]));
    static KindMesh Build(Dictionary<string, object> m, string prefab)
    {
        var materials = ((List<object>)m["materials"]).OfType<string>().ToList();
        if (materials.Count != 1) return null;
        string prefix = "VH_" + prefab + "_";
        var verts = ((List<object>)m["vertices"]).Select(o => U((List<object>)o)).ToList();
        var faces = (List<object>)m["triangles"];
        var uvs = (List<object>)m["triangle_uvs"];
        var normals = (List<object>)m["triangle_normals"];
        var at = new Dictionary<(int, Vector2, Vector3), int>();
        List<Vector3> V = new(), N = new();
        var UV = new List<Vector2>();
        var tri = new List<int>(faces.Count * 3);
        for (int f = 0; f < faces.Count; f++)
        {
            var face = (List<object>)faces[f];
            var fu = (List<object>)uvs[f];
            var fn = (List<object>)normals[f];
            foreach (int c in new[] { 0, 2, 1 })
            {
                int vi = Convert.ToInt32(face[c]);
                var cu = (List<object>)fu[c];
                var uv = new Vector2(Convert.ToSingle(cu[0]), Convert.ToSingle(cu[1]));
                var n = U((List<object>)fn[c]).normalized;
                if (!at.TryGetValue((vi, uv, n), out int k)) { at[(vi, uv, n)] = k = V.Count; V.Add(verts[vi]); N.Add(n); UV.Add(uv); }
                tri.Add(k);
            }
        }
        var whole = new Mesh { indexFormat = UnityEngine.Rendering.IndexFormat.UInt32 };
        whole.SetVertices(V);
        whole.SetNormals(N);
        whole.SetUVs(0, UV);
        whole.SetTriangles(tri, 0);
        whole.RecalculateTangents();
        var km = new KindMesh
        {
            Material = materials[0].StartsWith(prefix, StringComparison.Ordinal) ? materials[0].Substring(prefix.Length) : materials[0],
            TemplateLongest = m.TryGetValue("template_fit_longest_m", out var tl) ? Convert.ToSingle(tl) : 0.36f,
            V = V.ToArray(), N = N.ToArray(), UV = UV.ToArray(), T = whole.tangents, Tri = tri.ToArray(), Bounds = whole.bounds,
        };
        UnityEngine.Object.Destroy(whole);
        return km;
    }

    public sealed class Report { public long Total, Mandatory; public int Dropped, Hidden, Whole, Copies; }

    // Per shown copy the native faces it draws: null, the whole mesh (an exempt copy, or one outside every prefix); empty, hidden. As
    // display_r5b.select (version 4, strict): face f of copy j stays when Keep[j][f] >= N, its region's prefix count; over the budget
    // the extra-angle faces go, smallest projected area first (then copy id, ordinal, and face), never a protected face (Primary >= N)
    // nor a copy's last one (a copy seen only at an extra angle keeps its largest face). Where the protected faces alone exceed the
    // budget, they all stay and the report says by how much. Kinds without a native mesh are not counted (drawn the game's way).
    public int[][] Faces(List<FloorPiles.Shown> shown, int frameTris, out Report report)
    {
        report = new Report { Total = frameTris, Mandatory = frameTris, Copies = shown.Count };
        var faces = new int[shown.Count][];
        var whole = new bool[shown.Count];
        var rec = new (Region r, int j, int n)[shown.Count];
        for (int i = 0; i < shown.Count; i++)
        {
            var c = shown[i];
            if (!Meshes.TryGetValue(c.Item, out var km)) { whole[i] = true; continue; }
            if (c.Region == null || !Regions.TryGetValue(c.Region, out var r) || !r.Index.TryGetValue(c.Copy, out int j) || Exempt.Contains(c.Copy))
            {
                whole[i] = true;
                report.Whole++;
                report.Total += km.Faces;
                report.Mandatory += km.Faces;
                continue;
            }
            int n = c.Prefix, primary = 0;
            var keep = new List<int>();
            for (int f = 0; f < r.Keep[j].Length; f++)
            {
                if (r.Keep[j][f] >= n) keep.Add(f);
                if (r.Primary[j][f] >= n) primary++;
            }
            faces[i] = keep.ToArray();
            rec[i] = (r, j, n);
            if (keep.Count == 0) report.Hidden++;
            report.Total += keep.Count;
            report.Mandatory += Math.Max(primary, keep.Count > 0 ? 1 : 0);
        }
        if (report.Total > Budget)
        {
            long target = Math.Max(Budget, report.Mandatory);
            int drop = (int)(report.Total - target);
            var candidates = new List<(double area, string id, int f, int i)>();
            for (int i = 0; i < shown.Count; i++)
            {
                if (whole[i] || faces[i].Length == 0) continue;
                var (r, j, n) = rec[i];
                var area = r.Area[j];
                bool anyPrimary = faces[i].Any(f => r.Primary[j][f] >= n);
                int largest = -1;
                if (!anyPrimary) foreach (int f in faces[i]) if (largest < 0 || area[f] > area[largest]) largest = f;
                foreach (int f in faces[i])
                    if (anyPrimary ? r.Primary[j][f] < n : f != largest) candidates.Add((area[f], shown[i].Copy, f, i));
            }
            candidates.Sort((a, b) => a.area != b.area ? a.area.CompareTo(b.area) : string.CompareOrdinal(a.id, b.id) is var o && o != 0 ? o : a.f.CompareTo(b.f));
            var gone = new Dictionary<int, HashSet<int>>();
            for (int k = 0; k < drop && k < candidates.Count; k++)
            {
                if (!gone.TryGetValue(candidates[k].i, out var set)) gone[candidates[k].i] = set = new HashSet<int>();
                set.Add(candidates[k].f);
            }
            foreach (var kv in gone) faces[kv.Key] = faces[kv.Key].Where(f => !kv.Value.Contains(f)).ToArray();
            report.Dropped = Math.Min(drop, candidates.Count);
            report.Total -= report.Dropped;
        }
        return faces;
    }

    // The game's material for a kind: the item's own of that name, else its only one; null: draw the kind with the game's own mesh.
    // Logged once per kind with both shapes, longest side 1 (an axis swapped or a mirror shows as a mismatch here).
    public Material GameMaterial(string prefab, KindMesh k, ItemVisual look)
    {
        if (games.TryGetValue(prefab, out var mat)) return mat;
        var all = look.Parts.SelectMany(p => p.Mats).Where(x => x).Distinct().ToList();
        mat = all.FirstOrDefault(x => x.name.Replace(" (Instance)", "") == k.Material) ?? (all.Count == 1 ? all[0] : null);
        games[prefab] = mat;
        static Vector3 Unit(Vector3 v) => v / Mathf.Max(1e-6f, Mathf.Max(v.x, Mathf.Max(v.y, v.z)));
        Plugin.Log.LogInfo($"Ossuary display: {prefab} '{k.Material}' -> {(mat ? $"'{mat.name}'" : "no game material, its own mesh")}; "
            + $"native {Unit(k.Bounds.size):F3} at {k.Faces} faces, the game's {Unit(look.Bounds.size):F3} at {look.Triangles} (longest 1).");
        return mat;
    }

    // One merged mesh per material (the contract: no renderer per copy), built anew when the shown copies change.
    public sealed class Builder
    {
        readonly List<Vector3> v = new(), n = new();
        readonly List<Vector4> t = new();
        readonly List<Vector2> uv = new();
        readonly List<int> tri = new();
        int[] map = new int[0];
        public int Faces => tri.Count / 3;

        // One copy: the faces given (null: all), moved by at; normals and tangents turned by rot (a copy's scale is uniform).
        public void Add(KindMesh k, Matrix4x4 at, Quaternion rot, IEnumerable<int> faces)
        {
            if (map.Length < k.V.Length) map = new int[k.V.Length];
            for (int i = 0; i < k.V.Length; i++) map[i] = -1;
            foreach (int f in faces ?? Enumerable.Range(0, k.Faces))
                for (int c = 0; c < 3; c++)
                {
                    int vi = k.Tri[3 * f + c];
                    if (map[vi] < 0)
                    {
                        map[vi] = v.Count;
                        v.Add(at.MultiplyPoint3x4(k.V[vi]));
                        n.Add(rot * k.N[vi]);
                        var tg = k.T[vi];
                        var dir = rot * new Vector3(tg.x, tg.y, tg.z);
                        t.Add(new Vector4(dir.x, dir.y, dir.z, tg.w));
                        uv.Add(k.UV[vi]);
                    }
                    tri.Add(map[vi]);
                }
        }

        public Mesh Mesh(string name)
        {
            var m = new Mesh { name = name, indexFormat = UnityEngine.Rendering.IndexFormat.UInt32 };
            m.SetVertices(v);
            m.SetNormals(n);
            m.SetTangents(t);
            m.SetUVs(0, uv);
            m.SetTriangles(tri, 0);
            m.RecalculateBounds();
            return m;
        }
    }
}

// Fletcher's Barrels r3 (A's fletcher_layouts.json, schema storehouse.fletcher.cells.v1, Sol 6.1 / extra high). Fixed display cells in
// the barrels, tubs and crate; per cell and kind a checked prefix of saved copies, each a native root transform. Allocate is A's
// executable reference selector allocate_cells (variants/blender/fletcher_sol61.py), ported line for line:
//   per family, its kinds sorted by (case-folded name, name); one cell each in the family's allocation order, then the rest by the
//   largest deficit N*q_k/Q_fam - owned (ties in that kind order); the quota Q = representative_quota_at_64 * capacity/64; per kind
//   q = min(1, q_k / (Q*n/N)), F = min(1, Q_fam/Q), fraction = q + F^4 (1 - q); its copies ranked by (index + 0.5)/cell count, then
//   cell order (holder for the one-kind override), the first max(1, ceil(total * fraction)) taken. One kind alone in a family with a
//   single_kind_family_layouts entry (ArrowCarapace) uses those holder layouts instead of the cells.
sealed class FletcherCells
{
    public sealed class Copy { public string Id, Item; public Vector3 Pos; public Quaternion Rot; public float Scale; public int Holder; public string[] Requires; }
    sealed class Cell { public string Id, Family; public int Holder; public readonly Dictionary<string, List<Copy>> Copies = new(StringComparer.Ordinal); }
    sealed class Family { public string Name; public List<string> Order = new(); public float Quota; }
    readonly Dictionary<string, string> itemFamily = new(StringComparer.Ordinal);
    readonly List<Family> families = new();
    readonly Dictionary<string, Cell> cells = new(StringComparer.Ordinal);
    readonly Dictionary<string, Dictionary<string, List<(int holder, List<Copy> copies)>>> single = new(StringComparer.Ordinal);

    public static FletcherCells Parse(Dictionary<string, object> doc)
    {
        if (doc == null || !(doc.TryGetValue("schema", out var sc) && sc as string == "storehouse.fletcher.cells.v1")) return null;
        var f = new FletcherCells();
        static Copy ReadCopy(Dictionary<string, object> c, int holder)
        {
            var at = (List<object>)c["position_root_m"];
            var q = (List<object>)c["quat_xyzw"];
            return new Copy
            {
                Id = c["id"] as string, Item = c["item"] as string, Holder = holder,
                Pos = new Vector3(Convert.ToSingle(at[0]), Convert.ToSingle(at[1]), Convert.ToSingle(at[2])),
                Rot = new Quaternion(Convert.ToSingle(q[0]), Convert.ToSingle(q[1]), Convert.ToSingle(q[2]), Convert.ToSingle(q[3])).normalized,
                Scale = c.TryGetValue("uniform_scale", out var s) ? Convert.ToSingle(s) : 1f,
                Requires = c.TryGetValue("requires", out var r) && r is List<object> rl ? rl.OfType<string>().ToArray() : new string[0],
            };
        }
        foreach (var kv in (Dictionary<string, object>)doc["item_family"]) if (kv.Value is string fam) f.itemFamily[kv.Key] = fam;
        foreach (var kv in (Dictionary<string, object>)doc["families"])
        {
            var spec = (Dictionary<string, object>)kv.Value;
            f.families.Add(new Family
            {
                Name = kv.Key, Order = ((List<object>)spec["allocation_cell_order"]).OfType<string>().ToList(),
                Quota = Convert.ToSingle(spec["representative_quota_at_64"]),
            });
        }
        foreach (var o in ((List<object>)doc["cells"]).OfType<Dictionary<string, object>>())
        {
            var cell = new Cell { Id = o["id"] as string, Family = o["family"] as string, Holder = (int)Convert.ToSingle(o["holder"]) };
            foreach (var kv in (Dictionary<string, object>)o["copies_by_item"])
            {
                var list = ((List<object>)kv.Value).OfType<Dictionary<string, object>>().Select(c => ReadCopy(c, cell.Holder)).ToList();
                cell.Copies[kv.Key] = list;
            }
            f.cells[cell.Id] = cell;
        }
        if (doc.TryGetValue("single_kind_family_layouts", out var sk) && sk is Dictionary<string, object> byFamily)
            foreach (var fam in byFamily)
                foreach (var kind in (Dictionary<string, object>)fam.Value)
                {
                    var holders = ((List<object>)kind.Value).OfType<Dictionary<string, object>>().Select(h =>
                    {
                        int holder = (int)Convert.ToSingle(h["holder"]);
                        return (holder, ((List<object>)h["copies"]).OfType<Dictionary<string, object>>().Select(c => ReadCopy(c, holder)).ToList());
                    }).ToList();
                    if (!f.single.TryGetValue(fam.Key, out var m)) f.single[fam.Key] = m = new Dictionary<string, List<(int, List<Copy>)>>(StringComparer.Ordinal);
                    m[kind.Key] = holders;
                }
        return f.cells.Count > 0 ? f : null;
    }

    // stock: kind -> full stacks' worth. unseen: stored kinds outside the catalogue (never drawn as something else).
    public List<Copy> Allocate(Dictionary<string, float> stock, int capacitySlots, out int unseen)
    {
        double capacity = Math.Max(1, capacitySlots);   // doubles throughout, as A's Python: the same ranks and ceilings at the edges
        var held = stock.Where(kv => kv.Value > 0f && itemFamily.ContainsKey(kv.Key)).ToDictionary(kv => kv.Key, kv => (double)kv.Value, StringComparer.Ordinal);
        unseen = stock.Count(kv => kv.Value > 0f && !itemFamily.ContainsKey(kv.Key));
        var selected = new List<Copy>();
        foreach (var fam in families)
        {
            var kinds = held.Keys.Where(k => itemFamily[k] == fam.Name).OrderBy(k => k.ToLowerInvariant(), StringComparer.Ordinal).ThenBy(k => k, StringComparer.Ordinal).ToList();
            var famCells = fam.Order.Where(cells.ContainsKey).Select(id => cells[id]).ToList();
            if (kinds.Count == 0 || famCells.Count == 0) continue;
            if (kinds.Count > famCells.Count) { unseen += kinds.Count - famCells.Count; kinds = kinds.Take(famCells.Count).ToList(); }   // A raises here; in game: show what fits
            var assigned = kinds.ToDictionary(k => k, k => new List<Cell>(), StringComparer.Ordinal);
            double famQuantity = kinds.Sum(k => held[k]);
            double quota = capacity * fam.Quota / 64.0;
            double famFill = Math.Min(1.0, famQuantity / quota);
            for (int i = 0; i < kinds.Count; i++) assigned[kinds[i]].Add(famCells[i]);
            foreach (var c in famCells.Skip(kinds.Count))
            {
                string best = null;
                double bestScore = double.NegativeInfinity;
                foreach (var k in kinds)   // max by deficit; ties keep the earlier kind (A: -index as the tie key)
                {
                    double score = famCells.Count * held[k] / famQuantity - assigned[k].Count;
                    if (score > bestScore) { bestScore = score; best = k; }
                }
                assigned[best].Add(c);
            }
            foreach (var k in kinds)
            {
                var own = assigned[k];
                double q = Math.Min(1.0, held[k] / (quota * own.Count / famCells.Count));
                double fraction = q + famFill * famFill * famFill * famFill * (1.0 - q);
                var options = new List<(double rank, int order, Copy copy)>();
                if (kinds.Count == 1 && single.TryGetValue(fam.Name, out var byKind) && byKind.TryGetValue(k, out var holders))
                    foreach (var (holder, copies) in holders)
                        for (int i = 0; i < copies.Count; i++) options.Add(((i + 0.5) / copies.Count, holder, copies[i]));
                else
                    foreach (var cell in own)
                        if (cell.Copies.TryGetValue(k, out var copies))
                            for (int i = 0; i < copies.Count; i++) options.Add(((i + 0.5) / copies.Count, fam.Order.IndexOf(cell.Id), copies[i]));
                var ranked = options.OrderBy(o => o.rank).ThenBy(o => o.order).Select(o => o.copy).ToList();
                int budget = Math.Max(1, (int)Math.Ceiling(ranked.Count * fraction));
                selected.AddRange(ranked.Take(budget));
            }
        }
        return selected;
    }
}

// Worn armor on mannequins (Joost, 25 Oct: "armor doesn't fold"; the Armory Rail and Armory Island). Which stored item each form wears:
// six slots per form, helmet, chest, legs and cape on the body, a one-handed weapon in the right hand and a shield in the left.
// Pieces that belong together make an outfit: the set name when the game gives one (root_armor), else the name stem (ArmorBronzeChest,
// ArmorBronzeLegs and HelmetBronze are "bronze"). Complete outfits first, then the fullest, then by armor; a weapon and a shield of
// the same stem where there is one, else any; capes to the dressed forms in turn; what is left onto empty forms; then the spare
// places of its slot; the rest stays in the chest, counted. Pure logic, independent of the chest's order (a sort never changes it).
static class Outfits
{
    public enum Slot { Helmet, Chest, Legs, Cape, Weapon, Shield, None }
    public sealed class Piece
    {
        public int Index;            // into the caller's item list
        public string Prefab, Type, SetName;
        public float Armor;          // armor or block at its quality, for the order
        public bool Wearable;        // the prefab has attach children (else it can only lie or hang)
        public int X, Y;             // its slot in the window: column x, row y
        public bool Pinned;          // favorited (Quick Stack Store): a sort leaves it where it is
        public Slot Slot => Type switch
        {
            "Helmet" => Slot.Helmet, "Chest" => Slot.Chest, "Legs" => Slot.Legs, "Shoulder" => Slot.Cape,
            "OneHandedWeapon" => Slot.Weapon, "Shield" => Slot.Shield, _ => Slot.None,
        };
    }
    public sealed class Result
    {
        public readonly List<Dictionary<Slot, Piece>> Forms = new();
        public readonly List<Piece> Spares = new();   // per spare place, or null
        public readonly List<Piece> Unseen = new();
        public readonly List<string> FormKey = new();
    }

    static readonly string[] noise = { "helmet", "armor", "chest", "legs", "greaves", "cuirass", "cape", "shield", "buckler", "tower", "banded",
        "round", "sword", "axe", "mace", "knife", "spear", "club", "dagger", "hood", "hat" };
    // The curated map (assets/armory_outfits.json): prefab -> outfit, and per outfit its weapons and shields in order of preference.
    public static readonly Dictionary<string, string> Map = new(StringComparer.Ordinal);
    public static readonly Dictionary<string, (List<string> weapon, List<string> shield)> Hands = new(StringComparer.Ordinal);
    static string mapFrom;

    public static void LoadMap(string path, Func<string, bool> exists)
    {
        if (path == mapFrom) return;
        mapFrom = path;
        Map.Clear();
        Hands.Clear();
        if (!System.IO.File.Exists(path)) return;
        var missing = new List<string>();
        try   // the file is for hand edits: a broken one leaves the outfits to their names, once, instead of failing every redraw
        {
            var doc = Json.Parse(System.IO.File.ReadAllText(path)) as Dictionary<string, object>;
            foreach (var o in ((List<object>)doc["outfits"]).OfType<Dictionary<string, object>>())
            {
                if (!o.TryGetValue("name", out var n) || n is not string name) continue;
                List<string> Names(string key) => o.TryGetValue(key, out var v) && v is List<object> l ? l.OfType<string>().ToList() : new List<string>();
                foreach (var piece in Names("pieces")) { Map[piece] = name; if (exists != null && !exists(piece)) missing.Add(piece); }
                var hands = (Names("weapon"), Names("shield"));
                missing.AddRange(hands.Item1.Concat(hands.Item2).Where(x => exists != null && !exists(x)));
                Hands[name] = hands;
            }
        }
        catch (Exception e)
        {
            Map.Clear();
            Hands.Clear();
            Plugin.Log.LogError($"Armory outfits: {path} could not be read; outfits group by set and name stem instead ({e.Message}).");
            return;
        }
        Plugin.Log.LogInfo($"Armory outfits: {Hands.Count} from {path}" + (missing.Count > 0 ? $"; not in this game: {string.Join(", ", missing)}" : "; every name found."));
    }

    public static string Stem(Piece p)
    {
        if (Map.TryGetValue(p.Prefab, out var mapped)) return mapped;
        if (!string.IsNullOrEmpty(p.SetName)) return p.SetName.ToLowerInvariant();
        string s = p.Prefab.ToLowerInvariant();
        foreach (var w in noise) s = s.Replace(w, "");
        s = new string(s.Where(char.IsLetter).ToArray());
        return s.Length > 0 ? s : p.Prefab.ToLowerInvariant();
    }

    public static Result Dress(IList<Piece> items, int forms, IList<Slot> spareSlots)
    {
        var r = new Result();
        var order = items.OrderBy(p => Stem(p), StringComparer.Ordinal).ThenBy(p => p.Prefab, StringComparer.Ordinal).ThenByDescending(p => p.Armor).ThenBy(p => p.Index).ToList();
        var body = new[] { Slot.Helmet, Slot.Chest, Slot.Legs };
        var free = order.Where(p => p.Wearable && p.Slot != Slot.None).ToList();
        // Outfits: per stem, as many as its most plentiful body slot; each takes one piece of each body slot it has.
        var outfits = new List<(string stem, Dictionary<Slot, Piece> wear)>();
        foreach (var g in free.Where(p => body.Contains(p.Slot)).GroupBy(Stem))
        {
            var bySlot = body.ToDictionary(s => s, s => new Queue<Piece>(g.Where(p => p.Slot == s)));
            while (bySlot.Values.Any(q => q.Count > 0))
            {
                var wear = new Dictionary<Slot, Piece>();
                foreach (var s in body) if (bySlot[s].Count > 0) wear[s] = bySlot[s].Dequeue();
                outfits.Add((g.Key, wear));
            }
        }
        outfits = outfits.OrderByDescending(o => o.wear.Count).ThenByDescending(o => o.wear.Values.Sum(p => p.Armor)).ThenBy(o => o.stem, StringComparer.Ordinal).ToList();
        for (int f = 0; f < forms; f++) { r.Forms.Add(new Dictionary<Slot, Piece>()); r.FormKey.Add(null); }
        var left = new List<Piece>();
        for (int i = 0; i < outfits.Count; i++)
        {
            if (i < forms) { foreach (var kv in outfits[i].wear) r.Forms[i][kv.Key] = kv.Value; r.FormKey[i] = outfits[i].stem; }
            else left.AddRange(outfits[i].wear.Values);
        }
        // Hands: the same stem first, else any; capes in turn; dressed forms first.
        foreach (var slot in new[] { Slot.Weapon, Slot.Shield, Slot.Cape })
        {
            var pool = free.Where(p => p.Slot == slot).ToList();
            for (int f = 0; f < forms && pool.Count > 0; f++)
            {
                if (r.FormKey[f] == null) continue;
                var tier = slot == Slot.Cape || !Hands.TryGetValue(r.FormKey[f], out var h) ? null : slot == Slot.Weapon ? h.weapon : h.shield;
                var pick = (tier == null ? null : tier.Select(n => pool.FirstOrDefault(p => p.Prefab == n)).FirstOrDefault(p => p != null))
                    ?? pool.FirstOrDefault(p => Stem(p) == r.FormKey[f]) ?? pool[0];
                r.Forms[f][slot] = pick;
                pool.Remove(pick);
            }
            left.AddRange(pool);
        }
        // Odd pieces onto forms that still have that slot free, empty forms included (a cape alone hangs from the wooden shoulders).
        foreach (var p in left.ToList())
            for (int f = 0; f < forms; f++)
                if (!r.Forms[f].ContainsKey(p.Slot))   // an empty form has shoulders and hands too
                {
                    r.Forms[f][p.Slot] = p;
                    r.FormKey[f] ??= Stem(p);
                    left.Remove(p);
                    break;
                }
        // Spare places take helmets only (on their pegs; Joost: "armor doesn't fold"): a chest, legs or cape beyond the forms, and what
        // can't be worn, stays in the chest, counted ("3 more in storage").
        foreach (var slot in spareSlots)
        {
            var p = slot == Slot.Helmet ? left.FirstOrDefault(x => x.Slot == slot) : null;
            r.Spares.Add(p);
            if (p != null) left.Remove(p);
        }
        r.Unseen.AddRange(left);
        r.Unseen.AddRange(order.Where(p => !p.Wearable || p.Slot == Slot.None));
        return r;
    }

    // The window is the mannequins (Joost, 25 Oct 17:35, rows after a column detour: "one row gives you more visual clarity of like
    // this is one set"): six wide, helmet, chest, legs, cape, weapon, shield; row y (y < figures) is worn by figure y, any mix of sets;
    // the rows below are storage, helmets on the spare pegs and the rest counted. A piece dresses its row's figure by its type in any
    // column; two for one slot: the one in that slot's own column is worn, else the leftmost, and the other counts as storage.
    // In body order (Joost, 18:30: helmet, cape, chest, legs, weapon, shield). The game shows these lines transposed: Mannequins maps a
    // window column to a figure (Y here) and a window row to a slot line (X here).
    public static readonly Slot[] Columns = { Slot.Helmet, Slot.Cape, Slot.Chest, Slot.Legs, Slot.Weapon, Slot.Shield };
    public static int ColumnOf(Slot s) => Array.IndexOf(Columns, s);
    static IEnumerable<Piece> WearOrder(IEnumerable<Piece> row) => row.OrderBy(p => p.X == ColumnOf(p.Slot) ? 0 : 1).ThenBy(p => p.X).ThenBy(p => p.Index);

    // Who wears what, read from where the pieces lie.
    public static Result FromGrid(IList<Piece> items, int figures, IList<Slot> spareSlots)
    {
        var r = new Result();
        for (int f = 0; f < figures; f++) { r.Forms.Add(new Dictionary<Slot, Piece>()); r.FormKey.Add(null); }
        var left = new List<Piece>();
        // Typed rows (the contents audit, rule 9): worn only from its own slot line; a piece anywhere else is counted, not worn.
        foreach (var row in items.GroupBy(p => p.Y).OrderBy(g => g.Key))
            foreach (var p in WearOrder(row))
                if (p.Y < figures && p.Wearable && p.Slot != Slot.None && p.X == ColumnOf(p.Slot) && !r.Forms[p.Y].ContainsKey(p.Slot))
                {
                    r.Forms[p.Y][p.Slot] = p;
                    r.FormKey[p.Y] ??= Stem(p);
                }
                else left.Add(p);
        foreach (var slot in spareSlots)
        {
            var p = slot == Slot.Helmet ? left.FirstOrDefault(x => x.Slot == slot && x.Y >= figures) : null;   // pegs take helmets from storage
            r.Spares.Add(p);
            if (p != null) left.Remove(p);
        }
        r.Unseen.AddRange(left);
        return r;
    }

    // What a sort ends as: complete outfits one per figure row with their hands (Dress), each piece in its own column; the rest in the
    // storage rows, helmets first (the pegs take those), by outfit. Favorited pieces stay put and the others go around them. Independent
    // of the order the sort left them in. Returns the slot per Piece.Index.
    public static Dictionary<int, (int x, int y)> Arrange(IList<Piece> items, int figures, int width, int height)
    {
        var target = new Dictionary<int, (int x, int y)>();
        var taken = new HashSet<(int, int)>();
        foreach (var p in items.Where(p => p.Pinned)) { target[p.Index] = (p.X, p.Y); taken.Add((p.X, p.Y)); }
        var loose = items.Where(p => !p.Pinned).ToList();
        var dressed = Dress(loose, figures, Array.Empty<Slot>());
        var rest = new List<Piece>();
        for (int f = 0; f < figures && f < height; f++)
            foreach (var kv in dressed.Forms[f].OrderBy(kv => ColumnOf(kv.Key)))
            {
                var cell = (ColumnOf(kv.Key), f);
                if (cell.Item1 >= 0 && cell.Item1 < width && taken.Add(cell)) target[kv.Value.Index] = cell;
                else rest.Add(kv.Value);
            }
        rest.AddRange(dressed.Unseen);
        rest = rest.OrderBy(p => p.Slot == Slot.Helmet ? 0 : 1).ThenBy(p => Stem(p), StringComparer.Ordinal).ThenBy(p => ColumnOf(p.Slot) < 0 ? 99 : ColumnOf(p.Slot))
            .ThenBy(p => p.Prefab, StringComparer.Ordinal).ThenByDescending(p => p.Armor).ThenBy(p => p.Index).ToList();
        // Storage rows first, row by row. Only when they are full the figure rows' gaps: first in a row whose figure already wears
        // that slot (there it stays storage), then its own column in a row that lacks it (worn properly), then any gap.
        var wears = Enumerable.Range(0, figures).Select(f => new HashSet<Slot>(dressed.Forms[f].Where(kv => target.ContainsKey(kv.Value.Index)).Select(kv => kv.Key)
            .Concat(items.Where(p => p.Pinned && p.Y == f && p.Wearable).Select(p => p.Slot)))).ToList();
        var storage = Enumerable.Range(figures, Math.Max(0, height - figures)).SelectMany(y => Enumerable.Range(0, width).Select(x => (x, y))).Where(c => !taken.Contains(c)).ToList();
        int next = 0;
        foreach (var p in rest)
        {
            (int, int)? cell = null;
            if (next < storage.Count) cell = storage[next++];
            else
            {
                var gaps = Enumerable.Range(0, Math.Min(figures, height)).SelectMany(y => Enumerable.Range(0, width).Select(x => (x, y))).Where(c => !taken.Contains(c)).ToList();
                cell = gaps.Where(c => wears[c.y].Contains(p.Slot) || p.Slot == Slot.None || !p.Wearable).Select(c => ((int, int)?)c).FirstOrDefault()
                    ?? gaps.Where(c => c.x == ColumnOf(p.Slot)).Select(c => ((int, int)?)c).FirstOrDefault()
                    ?? gaps.Select(c => ((int, int)?)c).FirstOrDefault();
                if (cell is { } g && g.Item2 < figures && p.Wearable && p.Slot != Slot.None) wears[g.Item2].Add(p.Slot);
            }
            if (cell is { } c2) { target[p.Index] = c2; taken.Add(c2); }
            else target[p.Index] = (p.X, p.Y);   // no slot left (rows lowered under the stock): where it is
        }
        // And what a tidy would still do (a full window), so the sorted window is already tidy.
        var placed = items.Select(p => new Piece { Index = p.Index, Prefab = p.Prefab, Type = p.Type, SetName = p.SetName, Wearable = p.Wearable, Pinned = p.Pinned, X = target[p.Index].x, Y = target[p.Index].y }).ToList();
        foreach (var kv in Tidy(placed, figures, width)) target[kv.Key] = kv.Value;
        return target;
    }

    // After a drag or a shift-click: the piece a figure wears moves into its own column of the row when that is free, so the row
    // reads helmet to shield. Pieces in storage rows, spares and favorited pieces stay. Returns the moves per Piece.Index.
    public static Dictionary<int, (int x, int y)> Tidy(IList<Piece> items, int figures, int width)
    {
        var moves = new Dictionary<int, (int x, int y)>();
        var at = items.ToDictionary(p => p.Index, p => (x: p.X, y: p.Y));
        var taken = new HashSet<(int, int)>(at.Values);
        // Again until nothing moves: a piece that moves frees the slot another one of its row was waiting for.
        for (bool moved = true; moved;)
        {
            moved = false;
            foreach (var row in items.Where(p => p.Y < figures).GroupBy(p => p.Y))
            {
                var now = row.Select(p => new Piece { Index = p.Index, Type = p.Type, Wearable = p.Wearable, Pinned = p.Pinned, X = at[p.Index].x, Y = p.Y }).ToList();
                // The piece the figure wears per slot (the figure's own piece only, once per slot).
                var wornBy = new Dictionary<Slot, Piece>();
                foreach (var p in WearOrder(now)) if (p.Wearable && p.Slot != Slot.None && !wornBy.ContainsKey(p.Slot)) wornBy[p.Slot] = p;
                foreach (var p in wornBy.Values.OrderBy(p => p.X))
                {
                    int x = ColumnOf(p.Slot);
                    if (p.Pinned || x == p.X || x >= width || at[p.Index].x != p.X) continue;
                    if (taken.Contains((x, p.Y)))
                    {
                        // Two worn pieces in each other's slots (legs where the helmet goes, the helmet where the legs go): they swap.
                        // Never with a spare, which would then be worn instead.
                        var q = wornBy.Values.FirstOrDefault(o => o != p && at[o.Index].x == x);
                        if (q == null || q.Pinned || ColumnOf(q.Slot) != p.X) continue;
                        at[q.Index] = (p.X, p.Y);
                        moves[q.Index] = (p.X, p.Y);
                        at[p.Index] = (x, p.Y);
                        moves[p.Index] = (x, p.Y);
                        moved = true;
                        continue;
                    }
                    taken.Remove((p.X, p.Y));
                    taken.Add((x, p.Y));
                    at[p.Index] = (x, p.Y);
                    moves[p.Index] = (x, p.Y);
                    moved = true;
                }
            }
        }
        return moves;
    }
}

// The armory windows in the game (Outfits has the rules): one COLUMN per mannequin, six ROWS for the slots top to bottom like the body
// (Joost, 25 Oct 18:30: "the armor stand is a vertical thing"). Outfits works in lines (Y a figure, X a slot), so here a piece's
// window column is its Y and its window row its X. A tidy after every change by the owner, and a sort that ends as complete outfits. Joost sorts with Quick Stack Store (Goldenrevolver; key O and its button): its
// container sort gets a postfix when that mod is there, and its favorited items stay where they are.
static class Mannequins
{
    public static bool Is(Kind kind) => kind is { Slug: "armoryrail" or "armoryrail3" or "armoryisland" or "armorstand" or "armorstandopen" };

    // Figure columns: one per figure, and nothing else (Joost, 25 Oct 18:08: "I thought we were getting rid of the extra storage"; a full
    // chest is every figure fully dressed).
    public static int Figures(StoreModel model, int width) => model?.Forms == null ? 0 : Math.Min(model.Forms.Count, width);

    public static List<Outfits.Piece> Pieces(IList<ItemDrop.ItemData> gear, Func<ItemDrop.ItemData, bool> pinned = null) =>
        gear.Select((it, k) => new Outfits.Piece
        {
            Index = k, Prefab = it.m_dropPrefab.name, Type = it.m_shared.m_itemType.ToString(), SetName = it.m_shared.m_setName,
            Armor = it.m_shared.m_armor + it.m_shared.m_armorPerLevel * Mathf.Max(0, it.m_quality - 1) + EquipRules.Block(it),
            Wearable = MannequinBaker.Wearable(it.m_dropPrefab),
            X = it.m_gridPos.y, Y = it.m_gridPos.x,   // transposed: see above
            // Favorites are by item name in Quick Stack Store, so one favorited type would stay put in every armory: pinned only
            // where it already lies in its own row (the contents audit, rule 6).
            Pinned = pinned != null && pinned(it) && it.m_gridPos.y == Outfits.ColumnOf(new Outfits.Piece { Type = it.m_shared.m_itemType.ToString() }.Slot),
        }).ToList();

    static List<ItemDrop.ItemData> Gear(Inventory inv) => inv.GetAllItems().Where(it => it?.m_shared != null && it.m_dropPrefab).ToList();

    // Typed rows (Joost, 18:38): each window row takes only its slot, one place per mannequin.
    public static bool Holds(Inventory inv) => inv != null && Is(Kinds.ByToken(inv.GetName()));
    public static Outfits.Slot SlotOf(ItemDrop.ItemData item) => new Outfits.Piece { Type = item.m_shared.m_itemType.ToString() }.Slot;
    static readonly string[] slotNames = { "helmet", "cape", "chest", "legs", "weapon", "shield" };
    static string NameOf(Outfits.Slot slot) => Outfits.ColumnOf(slot) is int i and >= 0 && i < slotNames.Length ? slotNames[i] : "other";
    static int FreeX(Inventory inv, int row, ItemDrop.ItemData self, int prefer = -1)
    {
        bool Free(int x) => inv.GetItemAt(x, row) is not { } at || at == self;
        if (prefer >= 0 && prefer < inv.GetWidth() && Free(prefer)) return prefer;
        // The figure whose outfit it belongs to (the contents audit, rule 3): most of its other pieces share the item's outfit.
        if (self?.m_dropPrefab)
        {
            var mine = Outfits.Stem(Pieces(new[] { self })[0]);
            var gear = Gear(inv);
            var pieces = Pieces(gear);
            int best = -1, bestCount = 0;
            for (int x = 0; x < inv.GetWidth(); x++)
            {
                if (!Free(x)) continue;
                int n = pieces.Count(q => q.Y == x && Outfits.Stem(q) == mine);
                if (n > bestCount) { best = x; bestCount = n; }
            }
            if (best >= 0) return best;
        }
        for (int x = 0; x < inv.GetWidth(); x++) if (Free(x)) return x;
        return -1;
    }

    // May this piece go in: a slot a mannequin wears, and a free place in its row (itself counts as free when it moves inside).
    public static bool AllowsIn(Inventory inv, ItemDrop.ItemData item, out string why)
    {
        why = null;
        var slot = SlotOf(item);
        int row = Outfits.ColumnOf(slot);
        if (row < 0 || row >= inv.GetHeight() || !item.m_dropPrefab || !MannequinBaker.Wearable(item.m_dropPrefab))
        {
            why = $"{Filter.Name(item)}: mannequins wear only armor, capes, one-handed weapons and shields.";
            return false;
        }
        if (FreeX(inv, row, item) >= 0) return true;
        why = $"All {inv.GetWidth()} {NameOf(slot)} places are taken.";
        return false;
    }

    // Where it goes: (x, y) when that is in its own row (an occupied cell there swaps), else the row's first free place.
    public static bool Place(Inventory inv, ItemDrop.ItemData item, ref int x, ref int y, out string why)
    {
        int row = Outfits.ColumnOf(SlotOf(item));
        bool ownCell = y == row && x >= 0 && x < inv.GetWidth();
        if (!AllowsIn(inv, item, out why))
        {
            // A full row still takes a swap onto one of its own cells; a piece no mannequin wears never goes in.
            bool wearable = row >= 0 && row < inv.GetHeight() && item.m_dropPrefab && MannequinBaker.Wearable(item.m_dropPrefab);
            if (!(ownCell && wearable)) return false;
            why = null;
            return true;
        }
        if (ownCell) return true;
        x = FreeX(inv, row, item, x);   // a drop on another row: the same figure's cell when free (rule 4)
        y = row;
        return x >= 0;
    }

    // The window says what each row is for (Joost, 18:38: "this row, that's for a helmet"): an empty cell shows its slot's icon faded,
    // as the game's own equipment slots do.
    static readonly AccessTools.FieldRef<InventoryGui, Container> OpenContainer = AccessTools.FieldRefAccess<InventoryGui, Container>("m_currentContainer");
    static readonly AccessTools.FieldRef<InventoryGui, InventoryGrid> ContainerGrid = AccessTools.FieldRefAccess<InventoryGui, InventoryGrid>("m_containerGrid");
    static readonly AccessTools.FieldRef<InventoryGrid, List<InventoryElement>> Elements = AccessTools.FieldRefAccess<InventoryGrid, List<InventoryElement>>("m_elements");
    static readonly string[] hintItems = { "HelmetLeather", "CapeDeerHide", "ArmorLeatherChest", "ArmorLeatherLegs", "SwordBronze", "ShieldWood" };
    static readonly Sprite[] hints = new Sprite[6];
    static readonly HashSet<InventoryElement> hinted = new();
    static Sprite Hint(int row)
    {
        if (row < 0 || row >= hints.Length) return null;
        if (!hints[row] && ObjectDB.instance && ObjectDB.instance.GetItemPrefab(hintItems[row]) is { } prefab && prefab.GetComponent<ItemDrop>()?.m_itemData?.m_shared?.m_icons is { Length: > 0 } icons)
            hints[row] = icons[0];
        return hints[row];
    }
    [HarmonyPatch(typeof(InventoryGui), "UpdateContainer"), HarmonyPostfix]
    static void RowHints(InventoryGui __instance)
    {
        try
        {
            var c = OpenContainer(__instance);
            var grid = ContainerGrid(__instance);
            if (!grid || Elements(grid) is not { } elements) return;
            bool armory = Plugin.Live && c && Is(Kinds.ByToken(c.m_name));
            var inv = armory ? c.GetInventory() : null;
            foreach (var e in elements)
            {
                if (e?.m_icon == null) continue;
                var at = e.Position;
                if (armory && inv.GetItemAt(at.x, at.y) == null && Hint(at.y) is { } sprite)
                {
                    e.m_icon.enabled = true;
                    e.m_icon.sprite = sprite;
                    e.m_icon.color = new Color(1f, 1f, 1f, 0.22f);
                    hinted.Add(e);
                }
                else if (hinted.Remove(e)) e.m_icon.color = Color.white;   // a piece lies there now, or another chest is open
            }
        }
        catch (Exception ex) { Plugin.Log.LogWarning($"Armory: row hints off ({ex.Message})."); }
    }

    static StoreModel ModelOf(Container c, out Kind kind)
    {
        kind = c ? Kinds.ByToken(c.m_name) : null;
        return Is(kind) ? StoreModel.Get(kind.Slug, kind.Piece, kind.Title) : null;
    }

    static readonly AccessTools.FieldRef<Container, ZNetView> View = AccessTools.FieldRefAccess<Container, ZNetView>("m_nview");
    static readonly AccessTools.FieldRef<Container, bool> Loading = AccessTools.FieldRefAccess<Container, bool>("m_loading");
    static bool Mine(Container c) => View(c) is { } v && v && v.IsValid() && v.IsOwner() && !Loading(c);

    static void Apply(List<ItemDrop.ItemData> gear, Dictionary<int, (int x, int y)> to)
    {
        foreach (var kv in to) gear[kv.Key].m_gridPos = new Vector2i(kv.Value.y, kv.Value.x);   // back from lines to the window
    }

    // Every change in an armory the local player owns (a drag, a shift-click, Quick Stack): the worn piece into its own column. Before
    // the game saves the change, so the save holds the tidy order; positions only, never an item added or removed.
    [HarmonyPatch(typeof(Container), "OnContainerChanged"), HarmonyPrefix]
    static void TidyOnChange(Container __instance)
    {
        try   // runs inside the game's save of the container: it may never throw there
        {
            if (!Plugin.Live || !Mine(__instance) || ModelOf(__instance, out _) is not { } model) return;
            var inv = __instance.GetInventory();
            int figures = Figures(model, inv.GetWidth());
            if (figures <= 0) return;
            var gear = Gear(inv);
            var moves = Outfits.Tidy(Pieces(gear), figures, inv.GetHeight());
            if (moves.Count > 0) Apply(gear, moves);
        }
        catch (Exception e) { Plugin.Log.LogError($"Armory: could not tidy the rows; they stay as they are ({e.Message})."); }
    }

    // After Quick Stack Store sorted an armory: outfits per figure column, its favorited items in place. keepFavorites false: a resized
    // window, where the old slots no longer mean anything.
    public static void Sorted(Container container) => Arrange(container, true);
    public static void Arrange(Container container, bool keepFavorites)
    {
        if (!Plugin.Live || !container || !Mine(container) || ModelOf(container, out _) is not { } model) return;
        var inv = container.GetInventory();
        int figures = Figures(model, inv.GetWidth());
        if (figures <= 0) return;
        var gear = Gear(inv);
        Apply(gear, Outfits.Arrange(Pieces(gear, keepFavorites ? Favorited : null), figures, inv.GetHeight(), inv.GetWidth()));
        Changed(inv);   // saves, and redraws the figures
#if !RELEASE
        SortReport(model, gear, figures);
#endif
    }
    // Inventory.Changed is private and has grown parameters with defaults (success, cheatedStateChanged): called with its own defaults.
    static readonly MethodInfo changed = AccessTools.Method(typeof(Inventory), "Changed");
    static void Changed(Inventory inv) => changed?.Invoke(inv, changed.GetParameters()
        .Select(p => p.HasDefaultValue ? p.DefaultValue : p.ParameterType.IsValueType ? Activator.CreateInstance(p.ParameterType) : null).ToArray());

    // Quick Stack Store, read by reflection (a soft dependency: without it nothing is patched): its SortModule.SortContainer(Container)
    // and the local player's item favorites (UserConfig.GetPlayerConfig(id).IsItemNameFavorited(item.m_shared), the item's shared data).
    static MethodInfo playerConfig, itemFavorited;
    public static void HookSort(Harmony harmony)
    {
        var sort = AccessTools.TypeByName("QuickStackStore.SortModule") is { } t ? AccessTools.Method(t, "SortContainer", new[] { typeof(Container) }) : null;
        if (sort == null) { Plugin.Log.LogInfo("Armory sort: Quick Stack Store not found; a sort leaves the armory rows as it puts them."); return; }
        var user = AccessTools.TypeByName("QuickStackStore.UserConfig");
        playerConfig = user != null ? AccessTools.Method(user, "GetPlayerConfig") : null;
        itemFavorited = user != null ? AccessTools.Method(user, "IsItemNameFavorited", new[] { typeof(ItemDrop.ItemData.SharedData) }) : null;
        harmony.Patch(sort, postfix: new HarmonyMethod(typeof(Mannequins), nameof(AfterSort)));
        Plugin.Log.LogInfo($"Armory sort: Quick Stack Store's container sort ends as outfits per figure row{(itemFavorited == null ? " (its favorites not found: none kept)" : ", favorites kept")}.");
    }
    static void AfterSort(Container container)
    {
        try { Sorted(container); TypedSlots.Sorted(container); }
        catch (Exception e) { Plugin.Log.LogError($"Armory sort: could not arrange the outfits; the sort's own order stays ({e})."); }
    }
    internal static bool Favorited(ItemDrop.ItemData item)
    {
        if (itemFavorited == null || playerConfig == null || !Player.m_localPlayer) return false;
        try { return playerConfig.Invoke(null, new object[] { Player.m_localPlayer.GetPlayerID() }) is { } cfg && itemFavorited.Invoke(cfg, new object[] { item.m_shared }) is true; }
        catch { return false; }
    }

#if !RELEASE
    // After a sort (Joost, 18:30: "I don't think sorting really works just yet": the Berserker mannequin had no chest): what each
    // mannequin wears, what stays unworn, and the whole sets the chest holds (helmet, chest and legs of one outfit) against the ones
    // worn whole, so a set that could have been complete and was split shows.
    static void SortReport(StoreModel model, List<ItemDrop.ItemData> gear, int figures)
    {
        var pieces = Pieces(gear);
        var r = Outfits.FromGrid(pieces, figures, new Outfits.Slot[0]);
        var body = new[] { Outfits.Slot.Helmet, Outfits.Slot.Chest, Outfits.Slot.Legs };
        var lines = Enumerable.Range(0, figures).Select(f => $"mannequin {f + 1} [{r.FormKey[f] ?? "-"}]: "
            + string.Join(", ", r.Forms[f].OrderBy(kv => Outfits.ColumnOf(kv.Key)).Select(kv => $"{kv.Key.ToString().ToLowerInvariant()} {kv.Value.Prefab}"))).ToList();
        var whole = pieces.Where(x => x.Wearable && body.Contains(x.Slot)).GroupBy(Outfits.Stem)
            .Where(g => body.All(sl => g.Any(x => x.Slot == sl))).Select(g => g.Key).OrderBy(k => k, StringComparer.Ordinal).ToList();
        var wornWhole = r.Forms.Where(f => body.All(f.ContainsKey) && body.Select(sl => Outfits.Stem(f[sl])).Distinct().Count() == 1)
            .Select(f => Outfits.Stem(f[Outfits.Slot.Chest])).ToList();
        var split = whole.Where(k => !wornWhole.Contains(k)).ToList();
        Plugin.Log.LogInfo($"{model.Title} sort:\n  " + string.Join("\n  ", lines)
            + $"\n  not worn: {(r.Unseen.Count > 0 ? string.Join(", ", r.Unseen.Select(x => x.Prefab)) : "none")}"
            + $"\n  pinned (favorites in their own row): {(Pieces(gear, Favorited).Any(x => x.Pinned) ? string.Join(", ", Pieces(gear, Favorited).Where(x => x.Pinned).Select(x => x.Prefab)) : "none")}"
            + $"\n  whole sets in the chest: {(whole.Count > 0 ? string.Join(", ", whole) : "none")}; worn whole: {(wornWhole.Count > 0 ? string.Join(", ", wornWhole) : "none")}"
            + (split.Count > 0 ? $"; split although whole: {string.Join(", ", split)}{(whole.Count > figures ? $" (more whole sets than the {figures} mannequins)" : "")}" : ""));
    }
#endif

    // Rule 8 of the contents audit: an armory saved in an older layout (rows per figure, or before typed rows) is arranged once into
    // the typed columns when its owner loads it, and remembers that on its ZDO; never again after, so a player's own order stays.
    const string LayoutKey = "storehouse_armory_layout";
    const int LayoutVersion = 2;   // 2: a column per mannequin, typed slot rows (25 Oct)
    [HarmonyPatch(typeof(Container), "Load"), HarmonyPostfix]
    public static void AfterLoad(Container __instance)
    {
        try
        {
            if (!Plugin.Live || !Mine(__instance) || ModelOf(__instance, out var kind) is not { } model || model.Forms == null) return;
            var zdo = View(__instance).GetZDO();
            if (zdo == null || zdo.GetInt(LayoutKey) >= LayoutVersion) return;
            var inv = __instance.GetInventory();
            bool typed = Gear(inv).All(it => it.m_gridPos.y == Outfits.ColumnOf(SlotOf(it)) && it.m_gridPos.x < Figures(model, inv.GetWidth()));
            if (!typed) Arrange(__instance, false);
            zdo.Set(LayoutKey, LayoutVersion);
            Plugin.Log.LogInfo($"{kind.Title}: layout {(typed ? "already in typed columns" : "arranged into typed columns")} (once; marked on the container).");
        }
        catch (Exception e) { Plugin.Log.LogError($"Armory: layout check on load failed; left as it is ({e.Message})."); }
    }

    // Rule 10: the hover counts each slot against the mannequins.
    public static string Counts(Container c)
    {
        if (ModelOf(c, out _) is not { } model || model.Forms == null || c.GetInventory() is not { } inv) return null;
        int figures = Figures(model, inv.GetWidth());
        if (figures <= 0) return null;
        var gear = Gear(inv);
        string[] plural = { "Helmets", "capes", "chests", "legs", "weapons", "shields" };
        return string.Join(", ", Enumerable.Range(0, Outfits.Columns.Length).Select(r =>
            $"{plural[r]} {gear.Count(it => it.m_gridPos.y == r && SlotOf(it) == Outfits.Columns[r] && it.m_gridPos.x < figures)}/{figures}"));
    }

    // The hover's legend: which column is which mannequin.
    public static string Legend(Container c)
    {
        if (ModelOf(c, out _) is not { } model || model.Forms == null) return null;
        int width = c.GetInventory()?.GetWidth() ?? 0, figures = Figures(model, width);
        if (figures <= 0) return null;
        int front = model.Forms.Take(figures).Count(f => !f.Back);   // the forms are ordered front first (OrderForms)
        bool twoSides = front > 0 && front < figures;
        string columns = figures == 1 ? "The column: the mannequin" : twoSides
            ? $"Columns 1-{front}: the front mannequins, {front + 1}-{figures}: the back ones, each left to right as you face them"
            : $"Columns: the mannequins, left to right";
        return $"{columns}; rows: helmet, cape, chest, legs, weapon, shield.";
    }
}

// The chest window of every store with typed places (Joost, 27 Oct, the c-rule: one rule for every store, and a refusal must make
// sense to a person: "visually there's space for another shield... if it doesn't make sense to me as a person, the game rule needs
// to be different"). The window is the places: a block of slots per class of places (StoreModel.Classes: the places that take the
// same items, e.g. the Armor Cabinet's chest/legs/cape piles and its helmet places), as many slots as places, the blocks in reading
// order, each empty slot showing its kind faded as on the Armory Rails. An item goes into a slot of a block that takes it; which
// place of that class it then fills is the model's best fit (StoreModel.Allocate), so it may move as others come and go. Refused
// only when no arrangement can show it, and the refusal names what is full. Everything is derived from the anchors: a new round
// with other counts resizes the window (Fit), and what a chest already holds is never hidden or dropped.
static class TypedSlots
{
    public static bool Is(Kind kind) => kind?.Slug != null && kind.Rule != null && !Mannequins.Is(kind)
        && kind.Rule.Method.DeclaringType == typeof(EquipRules) && kind.Rule.Method.Name != nameof(EquipRules.Mannequin);
    public static StoreModel Model(Kind kind) => Is(kind) && Settings.ModelFolder != null
        && StoreModel.Get(kind.Slug, kind.Piece, kind.Title) is { Equip: not null, Classes: not null, CellClass: not null } m ? m : null;
    public static bool Holds(Inventory inv) => inv != null && Model(Kinds.ByToken(inv.GetName())) != null;
    public static int? Rows(Kind kind, int width) => width > 0 && Model(kind) is { } m ? Math.Max(1, (m.CellClass.Length + width - 1) / width) : null;

    static int CellOf(Inventory inv, ItemDrop.ItemData it) => it.m_gridPos.x >= 0 && it.m_gridPos.x < inv.GetWidth() && it.m_gridPos.y >= 0 ? it.m_gridPos.y * inv.GetWidth() + it.m_gridPos.x : -1;
    public static int ClassOf(StoreModel m, Inventory inv, ItemDrop.ItemData it) => m?.CellClass != null && CellOf(inv, it) is int c and >= 0 && c < m.CellClass.Length ? m.CellClass[c] : -1;

    // The cell an item goes to (dropped on x, y; -1: anywhere), or -1 with the reason it can't go in. Inside already: the cell it was
    // dropped on when that block takes it, else where it lies. leaving: the piece a drag swaps out of the dropped cell (it goes first).
    public static int Cell(Kind kind, StoreModel m, Inventory inv, ItemDrop.ItemData item, int x, int y, out string why, ItemDrop.ItemData leaving = null)
    {
        why = null;
        int w = inv.GetWidth(), cells = Math.Min(m.CellClass.Length, w * inv.GetHeight());
        int dropped = x >= 0 && x < w && y >= 0 && y * w + x < cells ? y * w + x : -1;
        var mine = Enumerable.Range(0, m.Classes.Count).Where(c => m.Classes[c].Takes(item)).ToList();
        if (inv.GetAllItems().Contains(item)) return dropped >= 0 && mine.Contains(m.CellClass[dropped]) ? dropped : CellOf(inv, item);
        string name = Localization.instance.Localize(item.m_shared.m_name), store = kind.Shown ?? kind.Title;
        if (mine.Count == 0) { why = $"The {store} has no place for {name}."; return -1; }
        bool Free(int cell) => inv.GetItemAt(cell % w, cell / w) is not { } at || at == leaving;
        int FirstFree(int c) => Enumerable.Range(m.Classes[c].First, m.Classes[c].Places.Count).Where(k => k < cells && Free(k)).DefaultIfEmpty(-1).First();
        var gear = inv.GetAllItems().Where(it => it?.m_shared != null && it.m_dropPrefab && it != leaving).ToList();
        // The chest's placement, asked "and this one too, in block c?" (StoreModel.Placement.With): the drop asks three times
        // (DropItem, the filter, Typed), all of the same placement.
        var basis = item.m_dropPrefab ? m.Basis(inv, gear) : null;
        int before = basis?.Shown ?? 0;
        bool Shows(int c)
        {
            if (!item.m_dropPrefab) return true;
            int shown = basis.With(item, c).Shown;
            if (Checking) Check(m, $"{item.m_dropPrefab.name} into {m.Classes[c].Name}", $"{before} -> {shown}", $"{Scratch(m, inv, gear, (ItemDrop.ItemData)null, c)} -> {Scratch(m, inv, gear, item, c)}");
            return shown > before;
        }
        if (dropped >= 0 && mine.Contains(m.CellClass[dropped]) && Free(dropped) && Shows(m.CellClass[dropped])) return dropped;
        foreach (int c in mine.OrderBy(c => dropped >= 0 && m.CellClass[dropped] == c ? 0 : 1))
            if (FirstFree(c) is int cell and >= 0 && Shows(c)) return cell;
        // Why, in what the player sees: the block is full; the item is too big even drawn smaller; or the places it fits are full.
        var first = m.Classes[mine[0]];
        if (mine.All(c => FirstFree(c) < 0)) { why = $"All {first.Places.Count} {first.Name} places of the {store} are taken."; return -1; }
        var places = mine.SelectMany(c => m.Classes[c].Places).ToList();
        var fitting = places.Where(k => StoreModel.FitTurn(m.Equip[k], item, EquipFit.TrueSize) != null).ToList();
        if (fitting.Count == 0) fitting = places.Where(k => StoreModel.MaxScale(m.Equip[k], item, EquipFit.TrueSize, m.Floor) > 0f).ToList();   // drawn smaller
        if (fitting.Count == 0) { why = $"{name} is too big for the {store}'s {first.Name} places, even at half size."; return -1; }
        int pile = fitting.Where(k => m.Equip[k].Pile >= 0).DefaultIfEmpty(-1).First();
        why = pile >= 0 ? $"The {store}'s {m.Equip[pile].Name} piles are full to the top."
            : $"The {store}'s {string.Join(" and ", fitting.Select(k => m.Equip[k].Name).Distinct())} places are taken.";
        return -1;
    }

    public static bool Place(Inventory inv, ItemDrop.ItemData item, ref int x, ref int y, out string why, ItemDrop.ItemData leaving = null)
    {
        why = null;
        var kind = Kinds.ByToken(inv.GetName());
        if (Model(kind) is not { } m) return true;
        int cell = Cell(kind, m, inv, item, x, y, out why, leaving);
        if (cell < 0) return why == null;   // inside already, outside every block: it stays where it lies
        x = cell % inv.GetWidth();
        y = cell / inv.GetWidth();
        return true;
    }

    // Where each item lies in a window of w x (cells / w): keep (every item already in a cell of a block that takes it stays) or not
    // (a sort: in the sort's order block by block, pinned items stay), the rest to the first free cell of a block that takes them,
    // and what has no such cell where it lay, else in any free cell. Null when the window has fewer cells than the chest holds.
    static Dictionary<ItemDrop.ItemData, int> Plan(List<ItemDrop.ItemData> gear, StoreModel m, int w, int cells, bool keep, Func<ItemDrop.ItemData, bool> pinned)
    {
        var claimed = new ItemDrop.ItemData[cells];
        var to = new Dictionary<ItemDrop.ItemData, int>();
        int Was(ItemDrop.ItemData it) => it.m_gridPos.x >= 0 && it.m_gridPos.x < w && it.m_gridPos.y >= 0 && it.m_gridPos.y * w + it.m_gridPos.x < cells ? it.m_gridPos.y * w + it.m_gridPos.x : -1;
        bool Valid(ItemDrop.ItemData it, int c) => c >= 0 && c < m.CellClass.Length && m.Classes[m.CellClass[c]].Takes(it);
        var order = gear.OrderBy(it => it.m_gridPos.y).ThenBy(it => it.m_gridPos.x).ToList();
        foreach (var it in order)
            if ((keep || pinned?.Invoke(it) == true) && Was(it) is int c && Valid(it, c) && claimed[c] == null) { claimed[c] = it; to[it] = c; }
        foreach (var it in order.Where(it => !to.ContainsKey(it)))
            foreach (int c in Enumerable.Range(0, m.Classes.Count).Where(c => m.Classes[c].Takes(it))
                .OrderBy(c => it.m_dropPrefab && m.Classes[c].Places.Any(k => StoreModel.FitTurn(m.Equip[k], it, EquipFit.TrueSize) != null) ? 0 : 1).ThenBy(c => c))
            {
                int cell = Enumerable.Range(m.Classes[c].First, m.Classes[c].Places.Count).Where(k => k < cells && claimed[k] == null).DefaultIfEmpty(-1).First();
                if (cell >= 0) { claimed[cell] = it; to[it] = cell; break; }
            }
        foreach (var it in order.Where(it => !to.ContainsKey(it)))
        {
            int was = Was(it);
            int cell = was >= 0 && claimed[was] == null ? was : Enumerable.Range(0, cells).Where(k => claimed[k] == null).DefaultIfEmpty(-1).First();
            if (cell < 0) return null;
            claimed[cell] = it;
            to[it] = cell;
        }
        return to;
    }

    static readonly AccessTools.FieldRef<Container, ZNetView> View = AccessTools.FieldRefAccess<Container, ZNetView>("m_nview");
    static readonly AccessTools.FieldRef<Container, bool> Loading = AccessTools.FieldRefAccess<Container, bool>("m_loading");
    static readonly AccessTools.FieldRef<Inventory, int> InvWidth = AccessTools.FieldRefAccess<Inventory, int>("m_width");
    static readonly AccessTools.FieldRef<Inventory, int> InvHeight = AccessTools.FieldRefAccess<Inventory, int>("m_height");
    static readonly MethodInfo changed = AccessTools.Method(typeof(Inventory), "Changed");
    static bool Mine(Container c) => View(c) is { } v && v && v.IsValid() && v.IsOwner() && !Loading(c);
    static void Changed(Inventory inv) => changed?.Invoke(inv, changed.GetParameters()
        .Select(p => p.HasDefaultValue ? p.DefaultValue : p.ParameterType.IsValueType ? Activator.CreateInstance(p.ParameterType) : null).ToArray());
    static void Size(Container c, Inventory inv, int w, int h) { c.m_width = InvWidth(inv) = w; c.m_height = InvHeight(inv) = h; }
    static bool Apply(Dictionary<ItemDrop.ItemData, int> plan, int w)
    {
        bool moved = false;
        foreach (var kv in plan)
            if (kv.Key.m_gridPos.x != kv.Value % w || kv.Key.m_gridPos.y != kv.Value / w) { kv.Key.m_gridPos = new Vector2i(kv.Value % w, kv.Value / w); moved = true; }
        return moved;
    }
    static bool busy;
    static readonly HashSet<string> told = new(StringComparer.Ordinal);

    // The window as the model's places say (a new round with other counts, or a chest from before the blocks): resized and every
    // item into a block that takes it, by the owner; the others follow its save. A chest holding more stacks than the new window
    // has cells keeps its size, and every row a stack lies in, until it holds fewer.
    public static void Fit(Container c)
    {
        var kind = c ? Kinds.ByToken(c.m_name) : null;
        if (busy || !Plugin.Live || Model(kind) is not { } m || c.GetInventory() is not { } inv) return;
        var gear = inv.GetAllItems().Where(it => it?.m_shared != null).ToList();
        int lowest = gear.Count == 0 ? -1 : gear.Max(it => it.m_gridPos.y);
        busy = true;
        try
        {
            if (!Mine(c)) { if (lowest >= inv.GetHeight()) Size(c, inv, inv.GetWidth(), lowest + 1); return; }
            int w = kind.Width, h = kind.Height;
            bool resize = inv.GetWidth() != w || inv.GetHeight() != h;
            var plan = Plan(gear, m, w, w * h, true, null);
            if (plan == null)
            {
                w = inv.GetWidth();
                h = Math.Max(inv.GetHeight(), lowest + 1);
                if (told.Add(kind.Title + h)) Plugin.Log.LogWarning($"{kind.Title}: keeps {w}x{h}: it holds {gear.Count} stacks, more than its {m.CellClass.Length} places; it takes {kind.Width}x{kind.Height} once it holds fewer.");
                resize = inv.GetWidth() != w || inv.GetHeight() != h;
                if ((plan = Plan(gear, m, w, w * h, true, null)) == null) return;
            }
            if (resize)
            {
                Plugin.Log.LogInfo($"{kind.Title}: window {inv.GetWidth()}x{inv.GetHeight()} -> {w}x{h} ({m.CellClass.Length} places: {string.Join(", ", m.Classes.Select(x => $"{x.Places.Count} {x.Name}"))}).");
                Size(c, inv, w, h);
            }
            if (Apply(plan, w) | resize) Changed(inv);
        }
        catch (Exception e) { Plugin.Log.LogError($"{kind.Title}: could not fit the window to its places; left as it is ({e.Message})."); }
        finally { busy = false; }
    }

    // After Quick Stack Store sorted the store: its order, block by block; favorited items stay where they lie in a block that takes them.
    public static void Sorted(Container c)
    {
        var kind = c ? Kinds.ByToken(c.m_name) : null;
        if (busy || !Plugin.Live || Model(kind) is not { } m || !Mine(c) || c.GetInventory() is not { } inv) return;
        busy = true;
        try
        {
            if (Plan(inv.GetAllItems().Where(it => it?.m_shared != null).ToList(), m, inv.GetWidth(), inv.GetWidth() * inv.GetHeight(), false, Mannequins.Favorited) is { } plan && Apply(plan, inv.GetWidth()))
                Changed(inv);
        }
        finally { busy = false; }
    }

    // The hover: each block against its places.
    public static string Counts(Container c)
    {
        if (Model(Kinds.ByToken(c.m_name)) is not { } m || c.GetInventory() is not { } inv) return null;
        var n = new int[m.Classes.Count];
        foreach (var it in inv.GetAllItems())
            if (it?.m_shared != null && ClassOf(m, inv, it) is int k and >= 0 && m.Classes[k].Takes(it)) n[k]++;
        var line = string.Join(", ", m.Classes.Select((x, k) => $"{x.Name} {n[k]}/{x.Places.Count}"));
        return line.Length > 0 ? char.ToUpperInvariant(line[0]) + line.Substring(1) : null;
    }

    // Every empty slot shows the kind its block takes, faded, as the game's own equipment slots and the Armory Rails do (item 4).
    static readonly AccessTools.FieldRef<InventoryGui, Container> OpenContainer = AccessTools.FieldRefAccess<InventoryGui, Container>("m_currentContainer");
    static readonly AccessTools.FieldRef<InventoryGui, InventoryGrid> ContainerGrid = AccessTools.FieldRefAccess<InventoryGui, InventoryGrid>("m_containerGrid");
    static readonly AccessTools.FieldRef<InventoryGrid, List<InventoryElement>> Elements = AccessTools.FieldRefAccess<InventoryGrid, List<InventoryElement>>("m_elements");
    static readonly Dictionary<string, Sprite> icons = new(StringComparer.Ordinal);
    static readonly HashSet<InventoryElement> hinted = new();
    static Container opened;
    static Sprite Icon(string prefab)
    {
        if (prefab == null) return null;
        if (!icons.TryGetValue(prefab, out var s) || !s)
            icons[prefab] = s = ObjectDB.instance && ObjectDB.instance.GetItemPrefab(prefab) is { } p && p.GetComponent<ItemDrop>()?.m_itemData?.m_shared?.m_icons is { Length: > 0 } all ? all[0] : null;
        return s;
    }
    // What each empty slot shows: only a kind its block takes right now, the slot's own when it does (Joost, 27 Oct: an empty Shield
    // Trough slot showed a shield the trough then refused). Its own is the designed one (CellHint), which a full place or pile can make
    // false; then another kind the block still takes, else nothing: a blank slot takes nothing more of its kind. Worked out again
    // only when the contents change.
    static Container hintFor;
    static int hintSig;
    static string[] hintCells;
    static bool[] blockedCells;   // empty cells no more of their block can show in (LiveHints): not shown
    // Per block, as many faded hints as items can still be shown there, the rest of its empty cells hidden (Joost via M, 27 Oct, the
    // Armor Cabinet and Coffer r3: "there's still empty slots with no icon hints of what actually can still go in there"; their piles
    // fill by true height, so a block's cells outnumber what it can show). How many more: samples of the hinted kinds added one by one
    // while each still shows.
    static string[] LiveHints(Kind kind, StoreModel m, Inventory inv)
    {
        int sig;
        unchecked
        {
            sig = m.Version * 31 + inv.GetWidth() * 7 + inv.GetHeight();
            foreach (var it in inv.GetAllItems())
                if (it?.m_shared != null) sig = sig * 31 + (it.m_dropPrefab ? it.m_dropPrefab.name.GetHashCode() : 0) + it.m_gridPos.x * 131 + it.m_gridPos.y * 7919;
        }
        if (hintCells != null && hintFor == opened && sig == hintSig) return hintCells;
        hintFor = opened;
        hintSig = sig;
        int w = inv.GetWidth(), cells = Math.Min(m.CellClass.Length, w * inv.GetHeight());
        hintCells = new string[cells];
        blockedCells = new bool[cells];
        var watch = System.Diagnostics.Stopwatch.StartNew();
        var said = new List<string>();
        var filter = kind?.Filter;
        var gear = inv.GetAllItems().Where(it => it?.m_shared != null && it.m_dropPrefab).ToList();
        // Every question is "and one more?" of the chest's placement (StoreModel.Placement.With), never solved anew (FEEDBACK-0.8
        // item 3: the Spine solved it about 250 times per change, a lag spike on every add).
        var basis = m.Basis(inv, gear);
        int before = basis.Shown;
        for (int c = 0; c < m.Classes.Count; c++)
        {
            var cls = m.Classes[c];
            var empty = Enumerable.Range(cls.First, cls.Places.Count).Where(k => k < cells && inv.GetItemAt(k % w, k / w) == null).ToList();
            if (empty.Count == 0) continue;
            int klass = c;
            var kinds = Enumerable.Range(cls.First, cls.Places.Count).Select(k => m.CellHint[k]).Where(h => h != null).Distinct()
                .Where(h => Sample(h) is { } data && cls.Takes(data) && (filter == null || filter.Allows(data))).ToList();
            var takes = kinds.Where(h => basis.With(Sample(h), klass).Shown > before).ToList();
            // How many more: a sample of the first kind that still shows, added to the placement with the ones before it, while one
            // does. A kind that no longer shows is not asked again in this count: exact where the places form a plain matching, and every
            // slot counted has an arrangement behind it (spine-lag-investigation.md; asking again cost the Spine four times as much).
            var active = new List<string>(takes);
            var now = basis;
            int extra = 0;
            while (extra < empty.Count && active.Count > 0)
            {
                var next = now.With(Sample(active[0]), klass, keep: true);
                if (next.Shown > now.Shown) { now = next; extra++; }
                else active.RemoveAt(0);
            }
            if (Checking) CheckHints(m, inv, gear, cls.Name, klass, kinds, takes, extra, empty.Count);
#if !RELEASE
            said.Add($"{cls.Name}: {cls.Places.Count} places, {empty.Count} empty, {extra} can still show" + (takes.Count > 0 ? $" ({string.Join(", ", takes)})" : " (no hinted kind would show)"));
#endif
            for (int j = 0; j < empty.Count; j++)
                if (j < extra && takes.Count > 0) hintCells[empty[j]] = takes.Contains(m.CellHint[empty[j]]) ? m.CellHint[empty[j]] : takes[j % takes.Count];
                else blockedCells[empty[j]] = true;
        }
#if !RELEASE
        // Once per change of what the window shows (Joost via M, 27 Oct: the Bow Rack showed no hints): per block what it decided.
        Plugin.Log.LogInfo($"Typed slots: {kind?.Title} in {watch.ElapsedMilliseconds} ms, {blockedCells.Count(b => b)} hidden; " + (said.Count > 0 ? string.Join("; ", said) : "no empty cell in any block") + ".");
#endif
        if (Checking)
        {
            Plugin.Log.LogInfo($"Placement self-check: {kind?.Title}: {compared} answers compared with a solve from scratch since the last line, {differed} differ.");
            compared = differed = 0;
        }
        return hintCells;
    }

    // The dev self-check (7 - Performance (dev), Placement self-check): every answer the placement gave by replay, asked again of a
    // placement solved from scratch the 0.8.0 way (every crossing pair by name, the tier by walking the recipes, the hints' count asking
    // every kind again); any difference is logged as a warning. It costs what 0.8.0 cost, the Spine's lag spike included: on only to check.
#if DEV
    static bool Checking => Settings.PlacementCheck?.Value == true;
#else
    const bool Checking = false;
#endif
    static int compared, differed;
    static void Check(StoreModel m, string what, string replay, string scratch)
    {
        compared++;
        if (replay == scratch) return;
        differed++;
        Plugin.Log.LogWarning($"Placement self-check: {m.Title}: {what}: replay {replay}, from scratch {scratch}.");
    }
    // How many items show of gear and more (more: of block klass), solved from scratch.
    static int Scratch(StoreModel m, Inventory inv, List<ItemDrop.ItemData> gear, ItemDrop.ItemData more, int klass) =>
        Scratch(m, inv, gear, more != null ? new List<ItemDrop.ItemData> { more } : new List<ItemDrop.ItemData>(), klass);
    static int Scratch(StoreModel m, Inventory inv, List<ItemDrop.ItemData> gear, List<ItemDrop.ItemData> more, int klass) =>
        m.Solve(gear.Concat(more).ToList(), EquipFit.TrueSize, g => more.Contains(g) ? klass : ClassOf(m, inv, g), keep: false, scan: true).Shown;
    // A block's hints as 0.8.0 worked them out against the replay's.
    static void CheckHints(StoreModel m, Inventory inv, List<ItemDrop.ItemData> gear, string block, int klass, List<string> kinds, List<string> takes, int extra, int empty)
    {
        int before = Scratch(m, inv, gear, (ItemDrop.ItemData)null, klass);
        var slow = kinds.Where(h => Scratch(m, inv, gear, Sample(h), klass) > before).ToList();
        Check(m, $"{block}: kinds that still show", string.Join(", ", takes), string.Join(", ", slow));
        var more = new List<ItemDrop.ItemData>();
        int shown = before;
        while (more.Count < empty)
        {
            bool added = false;
            foreach (var h in slow)
            {
                var trial = new List<ItemDrop.ItemData>(more) { Sample(h) };
                int n = Scratch(m, inv, gear, trial, klass);
                if (n > shown) { more = trial; shown = n; added = true; break; }
            }
            if (!added) break;
        }
        Check(m, $"{block}: how many more show", extra.ToString(), more.Count.ToString());
    }
    static ItemDrop.ItemData Sample(string prefab)
    {
        if (!ObjectDB.instance || ObjectDB.instance.GetItemPrefab(prefab) is not { } go || go.GetComponent<ItemDrop>()?.m_itemData is not { } data) return null;
        var item = data.Clone();
        item.m_dropPrefab = go;
        return item;
    }
    [HarmonyPatch(typeof(InventoryGui), "UpdateContainer"), HarmonyPostfix]
    static void Hints(InventoryGui __instance)
    {
        try
        {
            var c = OpenContainer(__instance);
            var grid = ContainerGrid(__instance);
            if (!grid || Elements(grid) is not { } elements) return;
            var m = Plugin.Live && c ? Model(Kinds.ByToken(c.m_name)) : null;
            var inv = m != null ? c.GetInventory() : null;
            if (inv != null && c != opened) Fit(c);   // opened: a round changed live since it loaded
            opened = c;
            var live = inv != null ? LiveHints(Kinds.ByToken(c.m_name), m, inv) : null;
            foreach (var e in elements)
            {
                if (e?.m_icon == null) continue;
                var at = e.Position;
                int cell = inv != null ? at.y * inv.GetWidth() + at.x : -1;
                if (cell >= 0 && cell < live.Length && inv.GetItemAt(at.x, at.y) == null && Icon(live[cell]) is { } sprite)
                {
                    e.m_icon.enabled = true;
                    e.m_icon.sprite = sprite;
                    e.m_icon.color = new Color(1f, 1f, 1f, 0.22f);
                    hinted.Add(e);
                }
                else if (hinted.Remove(e)) e.m_icon.color = Color.white;
                // Blocked: an empty cell its block can show nothing more in is not shown at all, so the window holds as many slots as
                // the store can show (Joost, 27 Oct: "can't we just show as many slots as it actually holds?"; darkening did not show).
                // The element is the slot's own MonoBehaviour; it comes back for another chest or when the block has room again.
                // Past the last place too: the window is rows of its width, the places may end mid-row (the Armor Coffer's 19 places
                // in rows of 8 showed 24 slots; Joost, 27 Oct: "does it have to be a full row?").
                bool block = cell >= 0 && inv.GetItemAt(at.x, at.y) == null
                    && (cell >= m.CellClass.Length || blockedCells != null && cell < blockedCells.Length && blockedCells[cell]);
                if (block && e.gameObject.activeSelf) { e.gameObject.SetActive(false); blocked.Add(e); }
                else if (!block && blocked.Remove(e)) e.gameObject.SetActive(true);
            }
        }
        catch (Exception ex) { Plugin.Log.LogWarning($"Typed slots: hints off ({ex.Message})."); }
    }
    static readonly HashSet<InventoryElement> blocked = new();
}

// The Arsenal Spine's holders (Joost via M, 27 Oct: "if we can try one and four, that seems like a good idea together"): under every arm
// a drawn weapon rests on (its pose table row's contacts, one point per arm), a small wooden peg, 2.5 cm square and 6 cm along the arm
// (the arms reach out from the spine along z), its top 1 mm under the contact; and on it a dark collar, 3.5 cm square and 3 mm thick,
// where the weapon touches, as the straw's dip ring does. The thin dark rods alone read as floating. The peg takes the frame's own
// wood: the atlas colour of the frame's largest face; the collar that colour darkened. Two little meshes per model, merged with the
// store's other meshes.
static class Holders
{
    sealed class Made { public int Version; public Mesh Peg, Collar; public Material Wood, Dark; }
    static readonly Dictionary<StoreModel, Made> made = new();

    public static int Add(StoreModel model, Vector3[] contacts, Dictionary<Material, List<CombineInstance>> groups)
    {
        if (!model.FrameMat || !model.Frame) return 0;
        if (!made.TryGetValue(model, out var m) || m.Version != model.Version || !m.Peg)
        {
            var uv = WoodUv(model.Frame);
            m = made[model] = new Made { Version = model.Version, Peg = Box("storehouse_peg", uv), Collar = Box("storehouse_collar", uv), Wood = model.FrameMat,
                Dark = Atlas.Shade(model.FrameMat, 0.35f, $"storehouse_{model.Key}_collar") };
            Plugin.Log.LogInfo($"{model.Title}: holders in the frame's wood (atlas {uv.x:F3}, {uv.y:F3}).");
        }
        if (!groups.TryGetValue(m.Wood, out var wood)) groups[m.Wood] = wood = new List<CombineInstance>();
        if (!groups.TryGetValue(m.Dark, out var dark)) groups[m.Dark] = dark = new List<CombineInstance>();
        foreach (var c in contacts)
        {
            wood.Add(new CombineInstance { mesh = m.Peg, transform = Matrix4x4.TRS(c + new Vector3(0f, -0.001f - 0.0125f, 0f), Quaternion.identity, new Vector3(0.025f, 0.025f, 0.06f)) });
            dark.Add(new CombineInstance { mesh = m.Collar, transform = Matrix4x4.TRS(c + new Vector3(0f, -0.0003f - 0.0015f, 0f), Quaternion.identity, new Vector3(0.035f, 0.003f, 0.035f)) });
        }
        return contacts.Length;
    }

    // The atlas point of the frame's largest face (the spine's beam): the wood every frame part is cut from.
    static Vector2 WoodUv(Mesh frame)
    {
        var v = frame.vertices;
        var uv = frame.uv;
        var t = frame.triangles;
        float best = -1f;
        var at = new Vector2(0.5f, 0.5f);
        if (uv == null || uv.Length != v.Length) return at;
        for (int i = 0; i + 2 < t.Length; i += 3)
        {
            float area = Vector3.Cross(v[t[i + 1]] - v[t[i]], v[t[i + 2]] - v[t[i]]).sqrMagnitude;
            if (area > best) { best = area; at = (uv[t[i]] + uv[t[i + 1]] + uv[t[i + 2]]) / 3f; }
        }
        return at;
    }

    // A unit box about its centre, every corner at one atlas point (flat colour), its own normals per face.
    static Mesh Box(string name, Vector2 uv)
    {
        var pos = new List<Vector3>();
        var nor = new List<Vector3>();
        var tris = new List<int>();
        foreach (var n in new[] { Vector3.right, Vector3.left, Vector3.up, Vector3.down, Vector3.forward, Vector3.back })
        {
            var a = Vector3.Cross(n, Mathf.Abs(n.y) > 0.5f ? Vector3.forward : Vector3.up) * 0.5f;
            var b = Vector3.Cross(n, a) ;
            var c0 = n * 0.5f;
            int k = pos.Count;
            pos.AddRange(new[] { c0 - a - b, c0 + a - b, c0 + a + b, c0 - a + b });
            for (int j = 0; j < 4; j++) nor.Add(n);
            tris.AddRange(new[] { k, k + 2, k + 1, k, k + 3, k + 2 });
        }
        var mesh = new Mesh { name = name };
        mesh.SetVertices(pos);
        mesh.SetNormals(nor);
        mesh.SetUVs(0, Enumerable.Repeat(uv, pos.Count).ToList());
        mesh.SetTriangles(tris, 0);
        mesh.RecalculateBounds();
        return mesh;
    }
}

// Worn armor without a live figure (WORN-ARMOR.md, route a): the vanilla ArmorStand's "Player Pose" copied once, off-screen, with every
// script, cloth and the body's drawing removed; posed by its Animator ("Pose" 0-2), then each item attached the way VisEquipment does
// it (attach_skin bound to the body's bones, attach_<joint> on that joint, the helmet's and hands' "attach" on their joints at local
// zero) and baked into plain meshes in the figure's own space. Cached per item and pose; nothing live stays in the world. Known gap:
// the garments a chest or legs paint onto the player's body (m_armorMaterial) need the body surface and are not drawn yet.
static class MannequinBaker
{
    static GameObject holder;
    static Transform root;
    static SkinnedMeshRenderer body;
    static Animator animator;
    static int posed = -1;
    static bool told;
    static readonly Dictionary<(string, int), ItemVisual> cache = new();
    public static int Baked;
    public static double BakeMs;
    // Joints by name in the player rig (VisEquipment's m_helmet, m_rightHand, m_leftHand).
    static readonly Dictionary<Outfits.Slot, string> joints = new() { [Outfits.Slot.Helmet] = "Helmet_attach", [Outfits.Slot.Weapon] = "RightHand_Attach", [Outfits.Slot.Shield] = "LeftHand_Attach" };

    static readonly Dictionary<int, Mesh> bodies = new();
    static readonly Dictionary<Texture, Texture2D> readable = new();
    static readonly Dictionary<string, Material> garments = new(StringComparer.Ordinal);
    static bool toldShader;

    // The body baked in a pose (readable, in the body renderer's space), once per pose.
    static Mesh BodyPosed(int pose)
    {
        if (bodies.TryGetValue(pose, out var m) && m) return m;
        m = new Mesh { name = "storehouse_mannequin_body_" + pose };
        body.BakeMesh(m, false);   // without the renderer's scale: the rig's bones carry it (x100 in the FBX, 0.01 on the renderer); placed at scale 1
        return bodies[pose] = m;
    }

    // A readable copy of a game texture (they aren't), through a render texture, at most 512 px: only its alpha is sampled.
    static Texture2D Readable(Texture tex)
    {
        if (readable.TryGetValue(tex, out var r) && r) return r;
        int w = Mathf.Min(512, tex.width), h = Mathf.Min(512, tex.height);
        var rt = RenderTexture.GetTemporary(w, h, 0, RenderTextureFormat.ARGB32, RenderTextureReadWrite.Linear);
        var before = RenderTexture.active;
        Graphics.Blit(tex, rt);
        RenderTexture.active = rt;
        r = new Texture2D(w, h, TextureFormat.RGBA32, false);
        r.ReadPixels(new Rect(0, 0, w, h), 0, 0);
        r.Apply();
        RenderTexture.active = before;
        RenderTexture.ReleaseTemporary(rt);
        return readable[tex] = r;
    }

    // The body's triangles that the garment covers: alpha at a corner or the middle of a triangle's UVs over 0.25.
    static Mesh Garment(Mesh posed, Texture garment)
    {
        var alpha = Readable(garment);
        var uv = posed.uv;
        if (uv == null || uv.Length == 0) return null;
        var keep = new List<int>();
        var tris = posed.GetTriangles(0);
        for (int t = 0; t < tris.Length; t += 3)
        {
            Vector2 a = uv[tris[t]], b = uv[tris[t + 1]], c = uv[tris[t + 2]], mid = (a + b + c) / 3f;
            float best = Mathf.Max(Mathf.Max(alpha.GetPixelBilinear(a.x, a.y).a, alpha.GetPixelBilinear(b.x, b.y).a),
                Mathf.Max(alpha.GetPixelBilinear(c.x, c.y).a, alpha.GetPixelBilinear(mid.x, mid.y).a));
            if (best > 0.25f) { keep.Add(tris[t]); keep.Add(tris[t + 1]); keep.Add(tris[t + 2]); }
        }
        if (keep.Count == 0) return null;
        var mesh = new Mesh { name = "storehouse_garment_" + garment.name, indexFormat = posed.indexFormat };
        mesh.SetVertices(posed.vertices);
        mesh.SetNormals(posed.normals);
        mesh.SetUVs(0, uv);
        mesh.SetTriangles(keep, 0);
        mesh.RecalculateBounds();
        return mesh;
    }

    // The garment texture on an alpha-cutout material (lit), so the garment's own edge shows; without that shader the body's
    // material with only this garment layer (skin may show at the edges; said once).
    static Material GarmentMaterial(Texture garment, string key)
    {
        if (garments.TryGetValue(key, out var mat) && mat) return mat;
        var shader = Glass.Loaded("Legacy Shaders/Transparent/Cutout/Diffuse");
        if (shader && shader.isSupported)
        {
            mat = new Material(shader) { name = "storehouse_garment_" + key };
            mat.SetTexture("_MainTex", garment);
            if (mat.HasProperty("_Cutoff")) mat.SetFloat("_Cutoff", 0.5f);
        }
        else
        {
            if (!toldShader) { toldShader = true; Plugin.Log.LogWarning("Mannequins: no cutout shader in this build; garments drawn on the body's material."); }
            mat = new Material(body.sharedMaterials[0]) { name = "storehouse_garment_" + key };
            foreach (var p in new[] { "_ChestTex", "_LegsTex" }) if (mat.HasProperty(p)) mat.SetTexture(p, key.EndsWith(p, StringComparison.Ordinal) ? garment : null);
        }
        return garments[key] = mat;
    }

    // It has attach children, or it is painted onto the body (a chest or legs whose look is only its m_armorMaterial).
    public static bool Wearable(GameObject prefab)
    {
        if (!prefab) return false;
        foreach (Transform c in prefab.transform) if (c.name.StartsWith("attach", StringComparison.Ordinal)) return true;
        return prefab.GetComponent<ItemDrop>()?.m_itemData?.m_shared?.m_armorMaterial is { } am && (am.HasProperty("_ChestTex") && am.GetTexture("_ChestTex") || am.HasProperty("_LegsTex") && am.GetTexture("_LegsTex"));
    }

    // The vanilla Armor Stand's skeleton in Pose_Upright as Joost captured it (assets/armorstand_pose.json, storehouse_posecapture of
    // 27 Oct 20:03). The baker's own Animator never posed the copy (its renderers are off, so the Animator culls: every set was baked
    // on the bind pose, arms 32 degrees out, turned to 15): with the file the rig takes these bones instead, and the carved arms
    // (ArmPose) the same pose. Read once per file change; null without it (the Animator and ArmsDown, as before).
    static VanillaPose vanilla;
    static string vanillaFrom;
    static DateTime vanillaStamp;
    static int vanillaLooked = int.MinValue;
    public static VanillaPose Vanilla()
    {
        var path = StoreModel.AssetPath("armorstand_pose.json");
        if (path == vanillaFrom && unchecked(Environment.TickCount - vanillaLooked) < 2000) return vanilla;   // the file looked at at most every 2 s
        vanillaLooked = Environment.TickCount;
        var stamp = File.Exists(path) ? File.GetLastWriteTimeUtc(path) : DateTime.MinValue;
        if (path == vanillaFrom && stamp == vanillaStamp) return vanilla;
        vanillaFrom = path;
        vanillaStamp = stamp;
        vanilla = null;
        posed = -1;
        cache.Clear();
        if (stamp == DateTime.MinValue) { Plugin.Log.LogWarning($"Mannequins: no {path}; the stand's own Animator poses the sets, the carved arms stay as carved."); return null; }
        try { vanilla = VanillaPose.Parse(File.ReadAllText(path), Path.GetFileName(path)); }
        catch (Exception e) { Plugin.Log.LogWarning($"Mannequins: {path} not read ({e.Message})."); }
        if (vanilla == null) Plugin.Log.LogWarning($"Mannequins: {path} is no storehouse-native-pose-capture/1; the stand's own Animator poses the sets.");
        else Plugin.Log.LogInfo($"Mannequins: the vanilla pose, {vanilla.Bones.Count} bones at scale {vanilla.Scale:F2}, from {path}.");
        return vanilla;
    }

    // Every bone under the copy's Visual where the capture has it (parents first, so a child lands where it was captured); the
    // Animator stays off. Said once: bones set and missing, and how far the rig's arm joints are from where ArmPose puts them in the
    // stand's space (Visual at its origin, unturned, at the capture's scale): the carved fists meet the held items only if that is ~0.
    static bool toldVanilla;
    static void PoseVanilla(VanillaPose pose)
    {
        var visual = root.Find("Visual");
        if (!visual) { Plugin.Log.LogWarning("Mannequins: no Visual in the stand's Player Pose; the vanilla pose not applied."); return; }
        if (animator) animator.enabled = false;
        int set = 0;
        var notIn = new List<string>();
        foreach (var t in visual.GetComponentsInChildren<Transform>(true))
        {
            if (t == visual) continue;
            string path = t.name;
            for (var p = t.parent; p && p != visual; p = p.parent) path = p.name + "/" + path;
            if (!pose.Bones.TryGetValue(path, out var m)) { notIn.Add(path); continue; }
            var x = new Vector3(m[0], m[4], m[8]);
            var y = new Vector3(m[1], m[5], m[9]);
            var z = new Vector3(m[2], m[6], m[10]);
            if (Vector3.Dot(Vector3.Cross(x, y), z) < 0f) continue;   // mirrored (the cloth colliders): no rotation says that; they skin nothing
            t.position = visual.TransformPoint(new Vector3(m[3], m[7], m[11]));
            if (z.sqrMagnitude > 1e-12f && y.sqrMagnitude > 1e-12f) t.rotation = visual.rotation * Quaternion.LookRotation(z, y);
            set++;
        }
        if (toldVanilla) return;
        toldVanilla = true;
        double worst = 0;
        string at = "";
        foreach (var name in new[] { "LeftArm", "LeftForeArm", "LeftHand_Attach", "RightArm", "RightForeArm", "RightHand_Attach" })
            if (Utils.FindChild(root, name) is { } j && pose.Has(name))
            {
                var p = root.InverseTransformPoint(j.position);
                var d = pose.Point(name);
                double off = Math.Sqrt((p.x - d.x) * (p.x - d.x) + (p.y - d.y) * (p.y - d.y) + (p.z - d.z) * (p.z - d.z));
                if (off > worst) { worst = off; at = name; }
            }
        Plugin.Log.LogInfo($"Mannequins: the rig in the vanilla pose ({set} bones from {pose.From}" + (notIn.Count > 0 ? $"; not in it: {string.Join(", ", notIn.Take(8))}{(notIn.Count > 8 ? $" and {notIn.Count - 8} more" : "")}" : "")
            + $"); its arm joints {worst * 1000:F1} mm from where the carved arms were posed{(worst > 0.005 ? $" (worst {at}: the fists miss the held items)" : "")}; forward {Forward:F2} ({ForwardFrom}).");
    }

    public static bool Ensure()
    {
        if (holder && root && body) return true;
        var stand = ZNetScene.instance ? (ZNetScene.instance.GetPrefab("ArmorStand_Male") ?? ZNetScene.instance.GetPrefab("ArmorStand")) : null;
        var pose = stand ? stand.transform.Find("Player Pose") : null;
        if (!pose)
        {
            if (!told) { told = true; Plugin.Log.LogWarning("Mannequins: no ArmorStand_Male/Player Pose in this game; worn sets are not drawn."); }
            return false;
        }
        holder = new GameObject("storehouse_mannequin_rig");
        holder.SetActive(false);   // nothing of the copy wakes up before its scripts are gone
        holder.transform.position = new Vector3(0f, -5000f, 0f);
        var copy = UnityEngine.Object.Instantiate(pose.gameObject, holder.transform, false);
        foreach (var mb in copy.GetComponentsInChildren<MonoBehaviour>(true)) UnityEngine.Object.DestroyImmediate(mb);
        foreach (var c in copy.GetComponentsInChildren<Cloth>(true)) UnityEngine.Object.DestroyImmediate(c);
        root = copy.transform;
        animator = copy.GetComponentInChildren<Animator>(true);
        var skins = copy.GetComponentsInChildren<SkinnedMeshRenderer>(true);
        body = skins.FirstOrDefault(x => x.name == "body") ?? skins.FirstOrDefault();
        if (!body) { UnityEngine.Object.Destroy(holder); holder = null; return false; }
        foreach (var r in copy.GetComponentsInChildren<Renderer>(true)) r.enabled = false;   // the copy is never drawn itself
        holder.SetActive(true);
        posed = -1;
        bodies.Clear();   // a new copy: its poses are baked again
        Forward = MeasureForward();
        return true;
    }

    // Which way a baked set faces in the figure's space (y up), from the rig itself: heel to toe of both feet, level. Measured, never
    // assumed (Joost's Rail, 25 Oct: the sets faced the back rail at both 0 and 180 degrees of an assumed turn).
    public static Vector3 Forward { get; private set; } = Vector3.forward;
    public static string ForwardFrom { get; private set; } = "assumed +z";
    static Vector3 MeasureForward()
    {
        var sum = Vector3.zero;
        foreach (var side in new[] { "Left", "Right" })
            if (Utils.FindChild(root, side + "Foot") is { } foot && (Utils.FindChild(root, side + "ToeBase") ?? Utils.FindChild(root, side + "Toe")) is { } toe)
                sum += root.InverseTransformPoint(toe.position) - root.InverseTransformPoint(foot.position);
        sum.y = 0f;
        if (sum.sqrMagnitude < 1e-6f) { ForwardFrom = "assumed +z (no foot and toe bones)"; return Vector3.forward; }
        ForwardFrom = "the rig's feet";
        Plugin.Log.LogInfo($"Mannequins: a baked set faces {sum.normalized:F2} in the figure's space (from the rig's feet).");
        return sum.normalized;
    }

    static void Pose(int index)
    {
        if (Vanilla() is { } vanillaPose)
        {
            if (posed != 0) { PoseVanilla(vanillaPose); posed = 0; }
            return;
        }
        if (posed == index || !animator) return;
        animator.enabled = true;
        animator.SetInteger("Pose", index);
        for (int i = 0; i < 6; i++) animator.Update(0.5f);   // through any transition into the pose
        animator.enabled = false;
        ArmsDown();
        posed = index;
    }

    // Arms a little down, the same on every mannequin (Joost, 25 Oct 18:30: "slightly more angled down; on most of them the arms are
    // actually down"): after the pose, each upper arm turned within the body's side plane to ArmAngle degrees out from straight
    // down. Hands, and the weapon and shield on them, follow.
    const float ArmAngle = 15f;
    static bool toldArms;
    static void ArmsDown()
    {
        var fwd = root.TransformDirection(Forward);
        var said = new List<string>();
        foreach (var side in new[] { "Left", "Right" })
        {
            var arm = Utils.FindChild(root, side + "Arm");
            var fore = Utils.FindChild(root, side + "ForeArm");
            if (!arm || !fore) { said.Add($"{side.ToLowerInvariant()}: no arm bones"); continue; }
            var dir = Vector3.ProjectOnPlane(fore.position - arm.position, fwd);
            if (dir.sqrMagnitude < 1e-8f) continue;
            float now = Vector3.SignedAngle(Vector3.down, dir, fwd);
            float want = (now < 0f ? -1f : 1f) * ArmAngle;
            arm.Rotate(fwd, want - now, Space.World);
            said.Add($"{side.ToLowerInvariant()} {now:F0} -> {want:F0}");
        }
        if (!toldArms) { toldArms = true; Plugin.Log.LogInfo($"Mannequins: upper arms from straight down, pose {animator.GetInteger("Pose")}: {string.Join(", ", said)}."); }
    }

    // The item worn in that pose as an ItemVisual in the figure's space (its root = the figure's feet), or null.
    public static ItemVisual Get(GameObject item, int pose, Outfits.Slot slot)
    {
        if (!item || Plugin.Headless) return null;
        if (Vanilla() != null) pose = 0;   // one pose for every figure: the vanilla stand's
        if (cache.TryGetValue((item.name, pose), out var hit)) return hit;
        if (!Ensure()) return null;
        var watch = System.Diagnostics.Stopwatch.StartNew();
        Pose(pose);
        var made = new List<GameObject>();
        foreach (Transform child in item.transform)
        {
            if (!child.name.StartsWith("attach", StringComparison.Ordinal)) continue;
            Transform at;
            if (child.name == "attach_skin") at = body.transform.parent;
            else if (child.name == "attach") at = joints.TryGetValue(slot, out var jn) ? Utils.FindChild(root, jn) : null;
            else at = Utils.FindChild(root, child.name.Substring(7));
            if (!at) continue;
            var go = UnityEngine.Object.Instantiate(child.gameObject, at, false);
            foreach (var mb in go.GetComponentsInChildren<MonoBehaviour>(true)) UnityEngine.Object.DestroyImmediate(mb);
            foreach (var c in go.GetComponentsInChildren<Cloth>(true)) UnityEngine.Object.DestroyImmediate(c);
            go.transform.localPosition = Vector3.zero;
            go.transform.localRotation = Quaternion.identity;
            go.SetActive(true);
            foreach (var smr in go.GetComponentsInChildren<SkinnedMeshRenderer>(true)) { smr.rootBone = body.rootBone; smr.bones = body.bones; }
            made.Add(go);
        }
        var v = new ItemVisual();
        var toRoot = root.worldToLocalMatrix;
        bool any = false;
        foreach (var go in made)
            foreach (var r in go.GetComponentsInChildren<Renderer>(true))
            {
                Mesh mesh;
                Matrix4x4 m;
                if (r is SkinnedMeshRenderer smr && smr.sharedMesh)
                {
                    mesh = new Mesh { name = "storehouse_worn_" + item.name };
                    smr.BakeMesh(mesh, false);   // as the body: with its scale the pieces came out 100x small (the Rail stood bare, 25 Oct)
                    m = toRoot * Matrix4x4.TRS(smr.transform.position, smr.transform.rotation, Vector3.one);
                }
                else if (r is MeshRenderer && r.GetComponent<MeshFilter>() is { sharedMesh: { } shared }) { mesh = shared; m = toRoot * r.transform.localToWorldMatrix; }
                else continue;   // particles and the like: worn effects stay off
                v.Parts.Add(new ItemVisual.Part
                {
                    Mesh = mesh, Mats = r.sharedMaterials, M = m, Name = r.name, Readable = mesh.isReadable,
                    Shadows = UnityEngine.Rendering.ShadowCastingMode.On, Receive = true,
                    Probes = UnityEngine.Rendering.LightProbeUsage.BlendProbes, Reflections = UnityEngine.Rendering.ReflectionProbeUsage.BlendProbes,
                });
                var b = Geometry.Xform(m, mesh.bounds);
                if (any) v.Bounds.Encapsulate(b); else { v.Bounds = b; any = true; }
            }
        // What a chest or legs paints onto the body (m_armorMaterial's _ChestTex / _LegsTex: Bronze trousers, Padded sleeves): the
        // posed body's own triangles where that texture has garment (alpha), drawn with the texture and an alpha cutout. Skin, face
        // and hands are never drawn; the wooden form shows there.
        if ((slot == Outfits.Slot.Chest || slot == Outfits.Slot.Legs) && item.GetComponent<ItemDrop>()?.m_itemData?.m_shared?.m_armorMaterial is { } am)
        {
            string prop = slot == Outfits.Slot.Chest ? "_ChestTex" : "_LegsTex";
            if (am.HasProperty(prop) && am.GetTexture(prop) is Texture garment && Garment(BodyPosed(pose), garment) is { } cloth)
            {
                var m = toRoot * Matrix4x4.TRS(body.transform.position, body.transform.rotation, Vector3.one);
                v.Parts.Add(new ItemVisual.Part
                {
                    Mesh = cloth, Mats = new[] { GarmentMaterial(garment, item.name + prop) }, M = m, Name = "garment", Readable = true,
                    Shadows = UnityEngine.Rendering.ShadowCastingMode.On, Receive = true,
                    Probes = UnityEngine.Rendering.LightProbeUsage.BlendProbes, Reflections = UnityEngine.Rendering.ReflectionProbeUsage.BlendProbes,
                });
                var b = Geometry.Xform(m, cloth.bounds);
                if (any) v.Bounds.Encapsulate(b); else { v.Bounds = b; any = true; }
            }
        }
        foreach (var go in made) { go.SetActive(false); UnityEngine.Object.Destroy(go); }
        watch.Stop();
        BakeMs += watch.Elapsed.TotalMilliseconds;
        Baked++;
#if !RELEASE
        // Where a bake lands, in the figure's space (feet at 0, about 1.8 m tall), per part: its mesh's own size and the scale of the
        // matrix that places it (the coordinator, 25 Oct: the Rail's figures stand bare though 25 pieces were baked).
        Plugin.Log.LogInfo($"Mannequins: baked {item.name} ({slot}, pose {pose}): {v.Parts.Count} part(s), bounds centre {v.Bounds.center:F2} size {v.Bounds.size:F2}; "
            + string.Join("; ", v.Parts.Select(x => $"{x.Name} mesh {x.Mesh.bounds.size:F2} x{x.M.lossyScale:F2} at {x.M.GetColumn(3):F2} "
                + $"mats [{string.Join(", ", (x.Mats ?? new Material[0]).Where(m => m).Select(m => $"{m.name} {m.shader.name} q{m.renderQueue}{(m.HasProperty("_Cutoff") ? $" cut{m.GetFloat("_Cutoff"):F2}" : "")}{(m.HasProperty("_Color") ? $" a{m.color.a:F2}" : "")} {string.Join("+", m.shaderKeywords)}"))}]")));
#endif
        return cache[(item.name, pose)] = v.Parts.Count > 0 ? v : null;
    }
}

sealed class CropLayout
{
    public float? Scale;        // x the item's true size; null: fit the longest side to Longest
    public float Longest;
    public readonly List<List<(Vector3 offset, Quaternion rot)>> Stacks = new();
}

sealed class StoreUnit
{
    public Vector3 Pos, Box;
    public Quaternion Rot = Quaternion.identity;
    public string Demo;
    public int Group = -1;   // its crate / bay / bin, when the anchors say (one item type per group)
    public string Kind;      // "bundle" (hung on a hook: gets a cord), "pile", "row", "arrow"/"bolt"/"bomb" (Fletcher's), ...
    public Dictionary<string, Quaternion> ItemRot;   // per item kind, a mounting turn (Trophy Hall: the face out of the wall)
    public string Item;      // the item the layout was made for ("item" or "render_item"): its group's home in a Homes store
    public readonly List<StoreCopy> Copies = new();
}

sealed class StoreCopy
{
    public Vector3 Offset, FitBox, LongTo, ThinTo;
    public Quaternion Rot = Quaternion.identity;
    public Align Align;
    public Fit Fit;
    public float Longest, Scale = 1f, Pitch;
    public int Layer;
    public bool Bottom, Back, FitAfterRotation;   // Back: the copy's back rests on the anchor (a trophy on its board, Trophy Hall)
}

static class Anchors
{
    // piece: the module inside a file that holds several (the emergency shelf's "2m" and "1m"); null for the others.
    // "item_rotation": {prefab: [x, y, z] Unity euler degrees}: a turn per item kind before the layout's own (the game's trophy models
    // lie face up; Trophy Hall r2 hangs each with its face out of the wall, a little down).
    static Dictionary<string, Quaternion> ItemRotations(Dictionary<string, object> doc)
    {
        if (Json.Obj(doc, "item_rotation") is not { } t) return null;
        var d = new Dictionary<string, Quaternion>(StringComparer.Ordinal);
        foreach (var kv in t) if (V(t, kv.Key) is { } e) d[kv.Key] = Quaternion.Euler(e);
        return d;
    }

    public static List<StoreUnit> Parse(Dictionary<string, object> doc, string piece)
    {
        List<object> list = null;
        if (piece != null && Json.Obj(doc, "pieces") is { } pieces && Json.Obj(pieces, piece) is { } module) list = List(module, "units");
        list ??= List(doc, "units") ?? List(doc, "units_data") ?? List(doc, "units_list") ?? List(doc, "places");
        if (list == null) return null;
        var units = new List<StoreUnit>();
        var itemRot = ItemRotations(doc);
        foreach (var o in list)
        {
            if (o is not Dictionary<string, object> ud) continue;
            var u = new StoreUnit
            {
                ItemRot = itemRot,
                Pos = V(ud, "position") ?? V(ud, "position_unity") ?? Vector3.zero,
                Rot = E(ud, "rotation") ?? E(ud, "rotation_euler") ?? E(ud, "rotation_euler_deg") ?? Quaternion.identity,
                Box = V(ud, "box") ?? V(ud, "box_size") ?? Vector3.one * 0.2f,
                Demo = S(ud, "render_item") ?? S(ud, "example_item") ?? S(ud, "item"),
                Group = (int)(Num(ud, "crate") ?? Num(ud, "bay") ?? Num(ud, "bin") ?? Num(ud, "compartment") ?? Cell(ud, "compartment") ?? -1f),
                Kind = S(ud, "kind"),
                Item = S(ud, "item") ?? S(ud, "render_item"),
            };
            var layout = Json.Obj(ud, "layout");   // larder: cols x rows x layers per unit
            foreach (var co in List(ud, "copies") ?? new List<object>())
                if (co is Dictionary<string, object> cd) u.Copies.Add(Copy(cd, u, layout));
            units.Add(u);
        }
        return units;
    }

    static StoreCopy Copy(Dictionary<string, object> cd, StoreUnit u, Dictionary<string, object> layout)
    {
        var c = new StoreCopy
        {
            Offset = V(cd, "offset") ?? V(cd, "local_position") ?? Vector3.zero,
            Rot = Q(cd, "rot_quat") ?? Q(cd, "quat_xyzw") ?? Q(cd, "rot_quat_xyzw")
                ?? E(cd, "rot_euler") ?? E(cd, "euler") ?? E(cd, "rot_euler_deg") ?? E(cd, "rotation") ?? Quaternion.identity,
        };

        cd.TryGetValue("align", out var align);
        if (align is Dictionary<string, object> axes)
        {
            c.Align = Align.Axes;
            c.LongTo = V(axes, "long_axis_to") ?? Vector3.right;
            c.ThinTo = V(axes, "thin_axis_to") ?? Vector3.up;
            c.Rot = Q(axes, "then_rotate_quat_xyzw") ?? E(axes, "then_rotate_euler_zxy") ?? Quaternion.identity;
        }
        else if (align as string == "long_x") c.Align = Align.LongX;
        else if (align as string == "long_axis_x")
        {
            // The shelf's yaw holds the quarter turn it gave its own demo item plus a few degrees of jitter. The stored item
            // gets its own quarter turn from LongYaw; keep only the jitter.
            c.Align = Align.LongYaw;
            var e = V(cd, "euler") ?? Vector3.zero;
            c.Rot = Quaternion.Euler(e.x, Mathf.Repeat(e.y + 45f, 90f) - 45f, e.z);
        }

        if ((Num(cd, "fit_longest_m") ?? Num(cd, "longest_m")) is { } longest) { c.Fit = Fit.Longest; c.Longest = longest; }
        else if (V(cd, "fit_box") is { } box) { c.Fit = Fit.Box; c.FitBox = box; c.Bottom = true; }
        else if (layout != null)
        {
            // Larder: the unit box split into cols x rows cells (4% air), its height shared by the stacked layers.
            float cols = Mathf.Max(1f, Num(layout, "cols") ?? 1f), rows = Mathf.Max(1f, Num(layout, "rows") ?? 1f);
            float layers = Mathf.Max(1f, Num(layout, "layers") ?? 1f), pitch = Num(layout, "pitch_frac") ?? 1f;
            c.Fit = Fit.Box;
            c.FitBox = new Vector3(u.Box.x / cols * 0.96f, u.Box.y / (1f + (layers - 1f) * pitch), u.Box.z / rows * 0.96f);
            c.Bottom = true;
            c.FitAfterRotation = true;
            c.Pitch = pitch;
        }
        else if (Num(cd, "scale") is { } scale) { c.Fit = Fit.Volume; c.Scale = scale; }
        else { c.Fit = Fit.Box; c.FitBox = u.Box; }

        if (S(cd, "anchor") is { } anchor) { c.Bottom = anchor.StartsWith("bottom", StringComparison.Ordinal); c.Back = anchor.StartsWith("back", StringComparison.Ordinal); }
        if (cd.ContainsKey("layer_pitch_hint")) c.Pitch = 0.93f;   // shelf: each layer rests at 93% of the one below
        if (c.Pitch > 0f)
        {
            // The file's y offset is the lift its own demo item needed; the stored item gets its own from Layer x Pitch.
            c.Layer = Mathf.RoundToInt(Num(cd, "layer") ?? 0f);
            c.Offset.y = 0f;
        }
        return c;
    }

    static List<object> List(Dictionary<string, object> d, string k) => d != null && d.TryGetValue(k, out var v) ? v as List<object> : null;
    // A compartment given as [column, row] (the Ore Bin's anchors): one number per cell. Read as a plain number before, it came
    // out as no group at all, so the Ore Bin never kept one kind of ore per compartment.
    static float? Cell(Dictionary<string, object> d, string k) =>
        List(d, k) is { Count: >= 2 } c ? Convert.ToSingle(c[0]) + 16f * Convert.ToSingle(c[1]) : null;

    // The Hide Rack r2's "hide_layouts" are the same piles per item, but bay-local: each bay has its floor centre and its turn
    // (the rack is a fan of bays), so a hide of any kind lies in any bay as its own settled pile (review 25 Oct: two kinds in a
    // bay showed as the first kind's poses). Their scale fits the longest side (the "scale" there is of Blender's true size).
    public static Dictionary<string, CropLayout> ParseCrops(Dictionary<string, object> doc, out List<Vector3> floors, out List<Quaternion> turns)
    {
        floors = null;
        turns = null;
        bool bayLocal = false;
        if (Json.Obj(doc, "crop_layouts") is { } crop && List(doc, "crate_floor_centres") is { } fl)
            floors = fl.OfType<List<object>>().Select(f => new Vector3(Convert.ToSingle(f[0]), Convert.ToSingle(f[1]), Convert.ToSingle(f[2]))).ToList();
        else if (Json.Obj(doc, "hide_layouts") is { } hides && List(doc, "bays") is { } bays)
        {
            var bayList = bays.OfType<Dictionary<string, object>>().Where(b => Num(b, "bay").HasValue && V(b, "floor_centre").HasValue).ToList();
            if (bayList.Count == 0) return null;
            int n = bayList.Max(b => (int)Num(b, "bay").Value) + 1;
            floors = Enumerable.Repeat(Vector3.zero, n).ToList();
            turns = Enumerable.Repeat(Quaternion.identity, n).ToList();
            foreach (var b in bayList)
            {
                int k = (int)Num(b, "bay").Value;
                floors[k] = V(b, "floor_centre").Value;
                turns[k] = Q(b, "rot_quat_xyzw") ?? Quaternion.identity;
            }
            crop = hides;
            bayLocal = true;
        }
        else return null;
        var all = crop;
        var result = new Dictionary<string, CropLayout>();
        foreach (var kv in all)
        {
            if (kv.Value is not Dictionary<string, object> c) continue;
            var lay = new CropLayout { Scale = bayLocal ? null : Num(c, "scale"), Longest = Num(c, "fit_longest_m") ?? 0.12f };
            foreach (var st in List(c, "stacks") ?? new List<object>())
            {
                var copies = new List<(Vector3, Quaternion)>();
                foreach (var co in (st as List<object>) ?? new List<object>())
                    if (co is Dictionary<string, object> cd) copies.Add((V(cd, "offset") ?? Vector3.zero, Q(cd, "rot_quat_xyzw") ?? Quaternion.identity));
                lay.Stacks.Add(copies);
            }
            result[kv.Key] = lay;
        }
        return result;
    }
    static string S(Dictionary<string, object> d, string k) => d != null && d.TryGetValue(k, out var v) ? v as string : null;
    static float? Num(Dictionary<string, object> d, string k) => d != null && d.TryGetValue(k, out var v) && v is double x ? (float)x : null;

    static float[] Floats(Dictionary<string, object> d, string k, int n) =>
        d != null && d.TryGetValue(k, out var v) && v is List<object> l && l.Count >= n && l.Take(n).All(x => x is double)
            ? l.Take(n).Select(x => (float)(double)x).ToArray() : null;

    static Vector3? V(Dictionary<string, object> d, string k) => Floats(d, k, 3) is { } f ? new Vector3(f[0], f[1], f[2]) : null;
    static Quaternion? Q(Dictionary<string, object> d, string k) => Floats(d, k, 4) is { } f ? new Quaternion(f[0], f[1], f[2], f[3]).normalized : null;
    static Quaternion? E(Dictionary<string, object> d, string k) => V(d, k) is { } e ? Quaternion.Euler(e) : null;   // Unity order: Z, X, Y
}

#if DEV
// Board (Joost, 22 Oct 2026): a simple processing step instead of fine wood as the gate for storage furniture. One wood at
// the workbench splits into two boards. A clone of the vanilla Wood item (so it stacks, weighs and burns like wood) with a plank
// shape instead of a log.
static class Board
{
    public const string Prefab = "StorehouseBoard";
    const int Wood = 1, Boards = 2;
    // The bulk recipe (Joost: "crafting one at a time is annoying"): the same rate, ten boards in one go.
    const string Bulk = "Recipe_StorehouseBoard_x10";
    const int BulkWood = 5, BulkBoards = 10;

    public static void Add()
    {
        var existing = PrefabManager.Instance.GetPrefab(Prefab);
        if (existing) { Retune(); Dress(existing); return; }   // live reload: registered by an earlier copy
        var cfg = new ItemConfig
        {
            Name = "$item_storehouse_board",
            Description = "$item_storehouse_board_desc",
            CraftingStation = "piece_workbench",
            Amount = Boards,
        };
        cfg.AddRequirement(new RequirementConfig("Wood", Wood));
        var item = new CustomItem(Prefab, "Wood", cfg);
        if (item.ItemPrefab == null) { Plugin.Log.LogError("Board: could not clone Wood; not added."); return; }
        item.ItemDrop.m_itemData.m_shared.m_weight = 1.5f;
        ItemManager.Instance.AddItem(item);
        var bulk = new RecipeConfig { Name = Bulk, Item = Prefab, Amount = BulkBoards, CraftingStation = "piece_workbench" };
        bulk.AddRequirement(new RequirementConfig("Wood", BulkWood));
        ItemManager.Instance.AddRecipe(new CustomRecipe(bulk));
        Dress(item.ItemPrefab);
        Plugin.Log.LogInfo($"Board: item added ({Wood} wood at the workbench makes {Boards}, or {BulkWood} make {BulkBoards}).");
    }

    // The plank's look: our own sawn-wood texture from the crib's atlas (pale planed grain on the faces, rings on the cut
    // ends) on a copy of the log's material, a plank mesh, colliders to match, and an icon rendered from it. Not the log's
    // own texture: that is made for a round trunk and showed bark and an orange cut on a flat plank (Joost).
    static Material mat;
    static void Dress(GameObject prefab)
    {
        var plank = Plank();
        var atlas = LoadAtlas();
        foreach (var r in prefab.GetComponentsInChildren<MeshRenderer>(true))
        {
            if (atlas && r.sharedMaterial)
            {
                if (mat) UnityEngine.Object.Destroy(mat);
                mat = new Material(r.sharedMaterial) { name = "storehouse_board" };
                mat.SetTexture("_MainTex", atlas);
                foreach (var t in mat.GetTexturePropertyNames())
                    if (t != "_MainTex" && mat.GetTexture(t) && (t.Contains("Bump") || t.Contains("Normal") || t.Contains("Metal"))) mat.SetTexture(t, null);
                mat.DisableKeyword("_NORMALMAP");
            }
            if (mat) r.sharedMaterials = new[] { mat };
            if (r.GetComponent<MeshFilter>() is { } mf) mf.sharedMesh = plank;
        }
        foreach (var col in prefab.GetComponentsInChildren<Collider>(true))
            if (col is BoxCollider box) { box.center = Vector3.zero; box.size = plank.bounds.size; }
            else if (col is CapsuleCollider cap) { cap.center = Vector3.zero; cap.radius = 0.06f; cap.height = 0.9f; cap.direction = 0; }
            else if (col is MeshCollider mc) mc.sharedMesh = plank;
        var shared = prefab.GetComponent<ItemDrop>().m_itemData.m_shared;
        // The icon: a little stack of three boards seen from above at an angle, like the fine wood icon; one plank on its own read
        // as a grey stick edge-on in the inventory (Joost).
        var stack = new GameObject("storehouse_board_icon");
        for (int i = 0; i < 3; i++)
        {
            var b = new GameObject("board", typeof(MeshFilter), typeof(MeshRenderer));
            b.transform.SetParent(stack.transform, false);
            b.transform.localPosition = new Vector3((i - 1) * 0.04f, i * 0.062f, (i % 2) * 0.05f - 0.025f);
            b.transform.localRotation = Quaternion.Euler(0f, (i - 1) * 6f, 0f);
            b.GetComponent<MeshFilter>().sharedMesh = plank;
            b.GetComponent<MeshRenderer>().sharedMaterial = mat ? mat : prefab.GetComponentInChildren<MeshRenderer>(true)?.sharedMaterial;
        }
        // A dedicated server has no graphics device to render with (and needs no icon).
        var icon = SystemInfo.graphicsDeviceType == UnityEngine.Rendering.GraphicsDeviceType.Null ? null
            : RenderManager.Instance.Render(new RenderManager.RenderRequest(stack) { Rotation = Quaternion.Euler(40f, -30f, 0f), Width = 64, Height = 64 });
        UnityEngine.Object.Destroy(stack);
        if (icon)
            shared.m_icons = new[] { icon };
    }

    static Texture2D atlas;
    static Texture2D LoadAtlas()
    {
        if (atlas) return atlas;
        var folder = string.IsNullOrWhiteSpace(Settings.ModelFolder.Value) ? Path.Combine(Plugin.Dir, "assets") : Settings.ModelFolder.Value.Trim();
        var png = Path.Combine(folder, "crib", "crib_atlas.png");
        if (!File.Exists(png)) { Plugin.Log.LogWarning($"Board: {png} not found; the plank keeps the log's texture."); return null; }
        atlas = new Texture2D(2, 2, TextureFormat.RGBA32, true) { name = "storehouse_board_atlas" };
        ImageConversion.LoadImage(atlas, File.ReadAllBytes(png));
        atlas.filterMode = FilterMode.Point;
        atlas.wrapMode = TextureWrapMode.Repeat;
        return atlas;
    }

    // Live reload: the board was registered by an earlier copy; bring its recipe in line with this one.
    static void Retune()
    {
        var recipes = ObjectDB.instance ? ObjectDB.instance.m_recipes : null;
        var recipe = recipes?.FirstOrDefault(r => r && r.m_item && r.m_item.name == Prefab && r.name != Bulk);
        if (!recipe) return;
        recipe.m_amount = Boards;
        foreach (var req in recipe.m_resources) if (req.m_resItem && req.m_resItem.name == "Wood") req.m_amount = Wood;
        // An earlier copy may not have had the bulk recipe: add it straight to the ObjectDB (Jotunn only adds recipes at load).
        var bulk = recipes.FirstOrDefault(r => r && r.name == Bulk);
        if (!bulk)
        {
            bulk = UnityEngine.Object.Instantiate(recipe);
            bulk.name = Bulk;
            recipes.Add(bulk);
        }
        bulk.m_amount = BulkBoards;
        foreach (var req in bulk.m_resources) if (req.m_resItem && req.m_resItem.name == "Wood") req.m_amount = BulkWood;
        Plugin.Log.LogInfo($"Board: recipes now {Wood} wood -> {Boards} boards and {BulkWood} wood -> {BulkBoards}.");
    }

    // A sawn plank, 0.9 x 0.06 x 0.22 m. UVs on the crib atlas (blender/crib.py): faces on the hewn-grain strip
    // (v 0.75-1, 128 px = 2.67 m along u at 48 px/m), the cut ends on an end-grain ring tile (v 0.25-0.5, u 0-0.25).
    public const float PlankLength = 0.9f, PlankWidth = 0.22f;
    static Mesh plank;
    internal static Mesh PlankMesh => plank ? plank : plank = Plank();
    internal static Material Material => mat;

    static Mesh Plank()
    {
        const float L = 0.45f, T = 0.03f, W = 0.11f, PxPerM = 48f / 128f;
        var v = new List<Vector3>(); var uv = new List<Vector2>(); var tri = new List<int>();
        void Face(Vector3 a, Vector3 b, Vector3 c, Vector3 d, Vector2 u0, Vector2 u1)
        {
            int k = v.Count;
            v.Add(a); v.Add(b); v.Add(c); v.Add(d);
            uv.Add(new Vector2(u0.x, u0.y)); uv.Add(new Vector2(u1.x, u0.y)); uv.Add(new Vector2(u1.x, u1.y)); uv.Add(new Vector2(u0.x, u1.y));
            tri.AddRange(new[] { k, k + 2, k + 1, k, k + 3, k + 2 });
        }
        Vector3 P(float x, float y, float z) => new(x * L, y * T, z * W);
        float len = 2f * L * PxPerM;
        Vector2 g0 = new(0.1f, 0.78f), wide = new(0.1f + len, 0.78f + 2f * W * PxPerM), thin = new(0.1f + len, 0.78f + 2f * T * PxPerM);
        Vector2 e0 = new(0.03f, 0.28f), e1 = new(0.22f, 0.47f);
        Face(P(-1, 1, -1), P(1, 1, -1), P(1, 1, 1), P(-1, 1, 1), g0, wide);         // top
        Face(P(-1, -1, 1), P(1, -1, 1), P(1, -1, -1), P(-1, -1, -1), g0, wide);     // bottom
        Face(P(-1, -1, -1), P(1, -1, -1), P(1, 1, -1), P(-1, 1, -1), g0, thin);     // sides
        Face(P(1, -1, 1), P(-1, -1, 1), P(-1, 1, 1), P(1, 1, 1), g0, thin);
        Face(P(1, -1, -1), P(1, -1, 1), P(1, 1, 1), P(1, 1, -1), e0, e1);           // cut ends
        Face(P(-1, -1, 1), P(-1, -1, -1), P(-1, 1, -1), P(-1, 1, 1), e0, e1);
        var m = new Mesh { name = "storehouse_board" };
        m.SetVertices(v); m.SetUVs(0, uv); m.SetTriangles(tri, 0);
        m.RecalculateNormals(); m.RecalculateTangents(); m.RecalculateBounds();
        return m;
    }
}
#endif


#if DEV
// A hung bundle's cord (Joost: "make the bundles look tied, not like a clipping bug"): one strand from above the bundle down
// through it, and a loop round each piece at a third of its height. Our own two little meshes on a plain hemp material,
// merged with the store's other readable meshes.
static class Cord
{
    static Mesh ring, strand;
    static Material hemp;

    public static void Tie(List<Bounds> pieces, Dictionary<Material, List<CombineInstance>> groups)
    {
        if (pieces.Count == 0) return;
        Make();
        if (!hemp) return;
        if (!groups.TryGetValue(hemp, out var list)) groups[hemp] = list = new List<CombineInstance>();
        Vector3 mid = Vector3.zero;
        float top = float.MinValue, bottom = float.MaxValue;
        foreach (var b in pieces) { mid += b.center; top = Mathf.Max(top, b.max.y); bottom = Mathf.Min(bottom, b.center.y); }
        mid /= pieces.Count;
        float len = top + 0.12f - bottom;
        list.Add(new CombineInstance { mesh = strand, transform = Matrix4x4.TRS(new Vector3(mid.x, bottom + len / 2f, mid.z), Quaternion.identity, new Vector3(0.009f, len, 0.009f)) });
        // One thin binding per piece, tight round its narrowest side near its top, where it hangs from the cord (Joost: the first
        // loops were wide orange plates).
        foreach (var b in pieces)
        {
            float r = 0.5f * Mathf.Min(b.size.x, b.size.z) * 0.7f + 0.003f;
            var at = new Vector3(b.center.x, b.max.y - Mathf.Min(0.05f, b.size.y * 0.15f), b.center.z);
            list.Add(new CombineInstance { mesh = ring, transform = Matrix4x4.TRS(at, Quaternion.identity, new Vector3(r, 0.011f, r)) });
        }
    }

    static void Make()
    {
        if (hemp && ring && strand) return;
        // The wood chest's own piece material, made plain hemp-coloured (Shader.Find("Standard") is null in the game build).
        var src = PrefabManager.Instance.GetPrefab("piece_chest_wood")?.GetComponentsInChildren<MeshRenderer>(true)
            .Select(r => r.sharedMaterial).FirstOrDefault(m => m && m.HasProperty("_MainTex") && !m.name.Contains("snow"));
        if (!src) return;
        hemp = new Material(src) { name = "storehouse_cord" };
        hemp.SetTexture("_MainTex", Texture2D.whiteTexture);
        foreach (var t in hemp.GetTexturePropertyNames())
            if (t != "_MainTex" && hemp.GetTexture(t) && (t.Contains("Bump") || t.Contains("Normal") || t.Contains("Metal"))) hemp.SetTexture(t, null);
        hemp.DisableKeyword("_NORMALMAP");
        if (hemp.HasProperty("_Color")) hemp.color = new Color(0.40f, 0.32f, 0.21f);
        strand = Box();
        ring = Loop(8, 0.8f);
    }

    // A unit cube round the origin.
    static Mesh Box()
    {
        var v = new List<Vector3>(); var t = new List<int>();
        void Q(Vector3 a, Vector3 b, Vector3 c, Vector3 d) { int k = v.Count; v.Add(a); v.Add(b); v.Add(c); v.Add(d); t.AddRange(new[] { k, k + 1, k + 2, k, k + 2, k + 3 }); }
        float h = 0.5f;
        Q(new(-h, -h, -h), new(-h, h, -h), new(h, h, -h), new(h, -h, -h));
        Q(new(h, -h, h), new(h, h, h), new(-h, h, h), new(-h, -h, h));
        Q(new(-h, -h, h), new(-h, h, h), new(-h, h, -h), new(-h, -h, -h));
        Q(new(h, -h, -h), new(h, h, -h), new(h, h, h), new(h, -h, h));
        Q(new(-h, h, -h), new(-h, h, h), new(h, h, h), new(h, h, -h));
        Q(new(-h, -h, h), new(-h, -h, -h), new(h, -h, -h), new(h, -h, h));
        return Finish("storehouse_cord_strand", v, t);
    }

    // A flat band of radius 1 (inner radius `inner`), height 1, `n` sides: outer and inner walls, top and bottom.
    static Mesh Loop(int n, float inner)
    {
        var v = new List<Vector3>(); var t = new List<int>();
        void Q(Vector3 a, Vector3 b, Vector3 c, Vector3 d) { int k = v.Count; v.Add(a); v.Add(b); v.Add(c); v.Add(d); t.AddRange(new[] { k, k + 1, k + 2, k, k + 2, k + 3 }); }
        for (int i = 0; i < n; i++)
        {
            float a0 = i * Mathf.PI * 2f / n, a1 = (i + 1) * Mathf.PI * 2f / n;
            Vector3 o0 = new(Mathf.Cos(a0), 0, Mathf.Sin(a0)), o1 = new(Mathf.Cos(a1), 0, Mathf.Sin(a1));
            Vector3 up = Vector3.up * 0.5f;
            Q(o0 - up, o0 + up, o1 + up, o1 - up);                                   // outer
            Q(o1 * inner - up, o1 * inner + up, o0 * inner + up, o0 * inner - up);   // inner
            Q(o0 + up, o0 * inner + up, o1 * inner + up, o1 + up);                   // top
            Q(o1 - up, o1 * inner - up, o0 * inner - up, o0 - up);                   // bottom
        }
        return Finish("storehouse_cord_loop", v, t);
    }

    static Mesh Finish(string name, List<Vector3> v, List<int> t)
    {
        var m = new Mesh { name = name };
        m.SetVertices(v);
        m.SetUVs(0, v.Select(_ => Vector2.zero).ToList());
        m.SetTriangles(t, 0);
        m.RecalculateNormals(); m.RecalculateBounds();
        return m;
    }
}
#endif

#if DEV
// The Meat Rack's hooks (Joost: "the bundles must show the actual items"): one bundle recipe per meat item, made in Blender
// with that item's own model (blender/meatbundles_r2.py -> assets/meatbundles_r2/bundles.json, near true size since round 2): how many copies, how they
// hang, the uniform scale, and our own cord mesh for that arrangement. Items without a recipe keep the anchors' bundle with
// the generic cord (Cord).
static class MeatBundles
{
    sealed class Recipe { public float Scale; public List<(Vector3 off, Quaternion rot)> Copies = new(); public Mesh Cord; }
    static Dictionary<string, Recipe> recipes;
    static Dictionary<int, (Vector3 hook, bool back)> hooks;
    static Material mat;
    static string loadedFrom;

    // The item copies' transforms go to `ats` (the caller adds them like any other copy); the cord goes straight into `groups`.
    public static bool Place(int unit, ItemDrop.ItemData item, List<Matrix4x4> ats, Dictionary<Material, List<CombineInstance>> groups)
    {
        Load();
        if (recipes == null || hooks == null || !hooks.TryGetValue(unit, out var h)) return false;
        string key = item.m_dropPrefab ? item.m_dropPrefab.name : "";
        if (!recipes.TryGetValue(key, out var r) || r.Copies.Count == 0) return false;
        var face = h.back ? Quaternion.Euler(0f, 180f, 0f) : Quaternion.identity;
        var basis = Matrix4x4.TRS(h.hook, face, Vector3.one);
        int max = item.m_shared.m_maxStackSize;
        int n = max > 1 ? Mathf.Clamp(Mathf.CeilToInt(r.Copies.Count * (float)item.m_stack / max), 1, r.Copies.Count) : r.Copies.Count;
        for (int i = 0; i < n; i++) ats.Add(basis * Matrix4x4.TRS(r.Copies[i].off, r.Copies[i].rot, Vector3.one * r.Scale));
        if (r.Cord && mat)
        {
            if (!groups.TryGetValue(mat, out var list)) groups[mat] = list = new List<CombineInstance>();
            list.Add(new CombineInstance { mesh = r.Cord, transform = basis });
        }
        return true;
    }

    static void Load()
    {
        var assetsDir = string.IsNullOrWhiteSpace(Settings.ModelFolder.Value) ? Path.Combine(Plugin.Dir, "assets") : Settings.ModelFolder.Value.Trim();
        var folder = new[] { "meatbundles_r3", "meatbundles_r2" }.Select(r => Path.Combine(assetsDir, r)).FirstOrDefault(Directory.Exists) ?? Path.Combine(assetsDir, "meatbundles_r2");   // r3: z-fix
        var json = Path.Combine(folder, "bundles.json");
        if (loadedFrom == json + File.GetLastWriteTimeUtc(json).Ticks) return;
        loadedFrom = json + File.GetLastWriteTimeUtc(json).Ticks;
        recipes = null; hooks = null;
        if (!File.Exists(json)) return;
        try
        {
            if (Json.Parse(File.ReadAllText(json)) is not Dictionary<string, object> doc) return;
            if (!mat) mat = Atlas.Material(PrefabManager.Instance.GetPrefab("piece_chest_wood"), "storehouse_meatbundles", "Meat Rack bundles");
            var png = Path.Combine(folder, "meatbundles_atlas.png");
            if (mat && File.Exists(png))
            {
                var tex = new Texture2D(2, 2, TextureFormat.RGBA32, true) { name = "storehouse_meatbundles_atlas" };
                ImageConversion.LoadImage(tex, File.ReadAllBytes(png));
                tex.filterMode = FilterMode.Point;
                mat.SetTexture("_MainTex", tex);
            }
            recipes = new Dictionary<string, Recipe>();
            foreach (var kv in doc)
            {
                if (kv.Key.StartsWith("_") || kv.Key == "doc" || kv.Value is not Dictionary<string, object> c) continue;
                if (c.TryGetValue("scale", out var sc) is false || sc is not double scale) continue;
                var rec = new Recipe { Scale = (float)scale };
                if (c.TryGetValue("copies", out var cl) && cl is List<object> list)
                    foreach (var co in list.OfType<Dictionary<string, object>>())
                        rec.Copies.Add((Vec(co, "offset"), Quat(co, "rot_quat_xyzw")));
                if (c.TryGetValue("cord_obj", out var co2) && co2 is string cord) rec.Cord = ObjMesh.Load(Path.Combine(folder, cord), flipX: true);
                recipes[kv.Key] = rec;
            }
            hooks = new Dictionary<int, (Vector3, bool)>();
            if (doc.TryGetValue("_hooks_meatrack_r4", out var hk) && hk is Dictionary<string, object> hd)
                foreach (var kv in hd)
                    if (int.TryParse(kv.Key, out int idx) && kv.Value is Dictionary<string, object> e)
                        hooks[idx] = (Vec(e, "hook_point"), e.TryGetValue("faces", out var f) && f as string == "back");
            Plugin.Log.LogInfo($"Meat Rack bundles: {recipes.Count} item recipes, {hooks.Count} hooks, from {folder}.");
        }
        catch (Exception e) { Plugin.Log.LogWarning($"Meat Rack bundles: could not read {json} ({e.Message})."); recipes = null; }
    }

    static Vector3 Vec(Dictionary<string, object> d, string k) =>
        d.TryGetValue(k, out var v) && v is List<object> l && l.Count >= 3 ? new Vector3(Convert.ToSingle(l[0]), Convert.ToSingle(l[1]), Convert.ToSingle(l[2])) : Vector3.zero;
    static Quaternion Quat(Dictionary<string, object> d, string k) =>
        d.TryGetValue(k, out var v) && v is List<object> l && l.Count >= 4 ? new Quaternion(Convert.ToSingle(l[0]), Convert.ToSingle(l[1]), Convert.ToSingle(l[2]), Convert.ToSingle(l[3])).normalized : Quaternion.identity;
}
#endif

// One store: our frame (OBJ, atlas on a copy of the wood chest's piece material, like the crib) plus its anchors.
// Files: <Model folder or the mod's assets>/<slug>_r3/ when that has the file, else <slug>_r2/ (per file, so a round 3
// that only re-exports the anchors still finds the round 2 frame). Live models: checked once a second like the crib; a
// change swaps the frame and rebuilds the contents of every piece and skinned chest with this store.
sealed class StoreModel
{
    public readonly string Slug, Piece, Title, Key;
    public Mesh Frame;
    public List<StoreUnit> Units = new();
    // Root bin round 5: a physics-settled heap per crop (rootbin_r5.py), keyed by item prefab name ("_generic" for any other).
    public Dictionary<string, CropLayout> crops;
    // Liquids (Cooper's Row's sap barrel, Joost: "one big barrel that fills up, a jug next to it to scoop it out"): per group a
    // column mesh of height 1 standing at Floor, drawn as tall as the group's stock, up to TopY, with the frame's material.
    // An entry with an item is that item's liquid in that group (Cooper's Row r5: every vessel can hold every liquid); without
    // one it is the group's only liquid. Labels: per group one copy of the item it holds, standing in front of it.
    public sealed class Liquid { public int Group; public string Item; public Mesh Mesh; public Vector3 Floor; public float TopY; }
    public readonly List<Liquid> Liquids = new();
    public sealed class Label { public int Group; public Vector3 Pos; public Quaternion Rot; public float Longest; }
    public readonly List<Label> Labels = new();
    // A face that takes the colour of what its group holds (the Hide Rack's stretched hides): drawn only while the group holds
    // something, on a light neutral tile tinted to that item (HideTint).
    public sealed class Panel { public int Group; public Mesh Mesh; }
    public readonly List<Panel> Panels = new();
    // A place whose vessel follows what it holds (Apothecary Rack r2: "a rack full of needles is all crocks"): its spot, the vessel
    // it shows while empty, and one mesh per family. Its units carry the family as their kind; a stack only takes units of its own.
    public sealed class VesselPlace { public int Group; public Vector3 At; public string Default; }
    public readonly List<VesselPlace> Places = new();
    public readonly Dictionary<string, Mesh> VesselMeshes = new(StringComparer.Ordinal);
    // Rough glass (review 25 Oct, A's SCHEMA.md): sight strips in the frame (Cooper's Row, "transparent_parts"), and per vessel
    // family the glass of a jar (Apothecary Rack, "transparent_parts_by_family"), each on a see-through material of its own. A
    // frame strip stays with the frame, full or empty; a jar's glass stands only where a jar stands, at that jar's spot.
    public sealed class GlassPart { public Mesh Mesh; public Material Mat; }
    public readonly List<GlassPart> FrameGlass = new();
    public readonly Dictionary<string, List<GlassPart>> FamilyGlass = new(StringComparer.Ordinal);
    // A unit's own binding (Fletcher's Barrels r2: the cord round a sheaf of arrows), drawn only while that unit holds a stack.
    public readonly Dictionary<int, Mesh> Bindings = new();
    // Colour bands by contents (Joost, 25 Oct: "the colors on the tubes need to reflect the contents"): per group, a band mesh from the
    // round's *_bands.obj (objects band_g<group>), drawn only while that group holds something, in its item's colour.
    public readonly Dictionary<int, Mesh> Bands = new();
    // The Arsenal kit's modules snap together where the anchors say ("snap_points", Unity space); its long rack's straw is a separate
    // Straw.obj, drawn but never solid and never a support (items stand on the box floor through it).
    public readonly List<Vector3> KitSnaps = new();
    public Mesh Straw;
    // Rougher straw (Joost via M, 27 Oct: rougher, more varied straw; a small dip and a darker rim where an item enters). Straw is one
    // part of its own: the frame's straw objects taken out of the frame (SplitStraw), or the kit's Straw.obj, its surface shaken once
    // per model load (Roughen) and drawn in three shades (StrawShades: the frame's material and copies at 0.88 and 0.76 of its colour).
    // Per model, not per piece: the piece is built once on the prefab, before any piece has a place, and the noise runs in store space,
    // so every straw object of a store already differs from its neighbours. StrawSurface: per straw object its shaken triangles (the
    // height an entry ring sits at, the box it stays in). StrawRing: the ring round an item standing in its own straw, one small mesh
    // per store on the straw's tile, scaled per copy, drawn with the contents on StrawRingMat (0.6 of the frame's colour).
    public Material[] StrawShades;
    public readonly Dictionary<string, Vector3[]> StrawSurface = new(StringComparer.Ordinal);
    public Mesh StrawRing;
    public Material StrawRingMat;
    Rect strawUv;
    // The top of each straw object in the frame OBJ (straw, straw_<n>, straw_g<group>, straw_u<unit>): never a support (items stand
    // on their floor through it); read for the burial log.
    public readonly Dictionary<string, float> StrawTops = new(StringComparer.Ordinal);
    // Which vessel family an item takes, and the families in shelf order (top first), from the anchors ("item_family",
    // "families"): the Pantry Dresser's jars, trays, crocks and sacks as well as the Apothecary Rack's.
    public readonly Dictionary<string, string> ItemFamily = new(StringComparer.Ordinal);
    public readonly List<string> FamilyOrder = new();
    public Material FrameMaterial => mat;
    public FloorPiles Piles;
    public PileDisplay PileLook;   // the Ossuary's display sidecar (dev builds); null: the game's own meshes
    public FletcherCells Cells;
    // Worn-armor forms (the Armory Rail and Island): where each wooden form stands, its turn and pose; spare places by slot.
    public sealed class Form { public Vector3 Pos; public float Yaw; public int Pose; public bool Back; public int Facing; public int Front; public List<string> ArmNames; public Mesh Arms; }   // Front: the anchor's own front (+1/-1 along z, 0: not said)   // Back: on the piece's back side; Facing: +1/-1 along z (OrderForms); Arms: its carved arms and fists apart from the frame (SplitArms)
    public sealed class Spare { public Outfits.Slot Slot; public Vector3 Pos; public Quaternion Rot; }
    public List<Form> Forms;
    public List<Spare> Spares;   // A's display cells (storehouse.fletcher.cells.v1, Fletcher's Barrels r3); null: by units
    // Equipment stores (B's exports): one place per unit for one real item of its types, at its true size. Null: not equipment.
    public sealed class EquipPlace
    {
        public int Unit;
        public HashSet<string> Types;   // item type names (ItemDrop.ItemData.ItemType)
        public bool Saddle, Featured;
        public Vector3 Pos, Box;
        public Vector3? Bottom;         // the support point under the item ("bottom_position_unity")
        public bool OnBottom;           // the position is the bottom centre ("anchor": "bottom_center")
        public Func<ItemDrop.ItemData, bool> Accepts;   // the Arsenal kit: by weapon skill too, not only by type (a spear's place takes no knife)
        public float? HangY;            // hung from arms (the kit's spine): the arm tops' height; HangAt, where along the item's height it rests there
        public Vector3? Pose;           // the kit: where its example's true centre stands as designed ("position_unity")
        public float HangAt;
        public Quaternion Rot = Quaternion.identity;
        public string Example;          // the item the place was made for: it goes here first
        // Stacked places (the armor exports: folded pieces four high in one column): the column is the places at one position,
        // the layer which one from the bottom. A layer is used only on the one below it, and rests on what actually lies there.
        public int Layer;
        public Vector3Int Column;
        public float StackTop;          // the top of the column's highest box: no copy of the stack goes above it
        public Vector3? Clear;          // the largest frame-free box at the place ("clear_box"): an exact fit, no slack
        public bool ByExample;          // the Arsenal kit: the place is its example's room, measured in its own frame (StoreModel.ExampleSize)
        public Vector3? ExampleSize;    // its example's own true size as the game measures it, once known
        public float Ceiling = float.PositiveInfinity;   // the bottom of the next shelf or cubby above, at this x/z
        public float? FixedCeiling;     // the clear box's ceiling in prefab space (stacked armor): no copy of the column above it
        internal bool ExplicitLayer;
        public string Name;             // what the player calls it in a refusal ("crested helmet", "shield oversize")
        public int Class = -1, Pile = -1;   // its window block (Classes) and its pile (Stacks; -1: a place on its own)
    }
    public List<EquipPlace> Equip;   // broad mixed heaps from "<slug>_layouts.json" (schema floor_piles.v1, Ossuary r4); null: by units
    // The chest window of an equipment store (the c-rule, Joost 27 Oct: "if it doesn't make sense to me as a person, the game rule
    // needs to be different"): one block of slots per class of places (the places that take the same items), as many slots as
    // places, the blocks one after the other in reading order. Derived from the anchors only, so a new round resizes the window.
    public sealed class EquipClass
    {
        public string Name;             // "helmet", "chest, legs and cape"
        public readonly List<int> Places = new();
        public int First;               // its first cell in the window
        public Func<ItemDrop.ItemData, bool> Accepts;
        public HashSet<string> Types;
        public bool Saddle;
        public bool Takes(ItemDrop.ItemData it) => Accepts != null ? Accepts(it) : Saddle ? EquipRules.IsSaddle(it) : Types.Contains(it.m_shared.m_itemType.ToString());
    }
    public List<EquipClass> Classes;
    public int[] CellClass;             // per window cell its class; past the last place: none
    public string[] CellHint;           // per window cell the item whose icon shows faded while it is empty
    // Stacked places (folded armor) are one pile: its layers hold what fits under its ceiling by true height, not a fixed count
    // (the Armor Cabinet's self-test, 27 Oct: 64 held, 49-54 drawn, the rest silently above the shelf).
    public List<List<int>> Stacks;
    public List<Vector3> crateFloors;
    public List<Quaternion> crateTurns;   // per crate its turn, when the layouts are crate-local (Hide Rack); null: all straight
    public List<Plank> Planks = new();   // a packed shelf (round 4 emergency shelf): its plank surfaces instead of anchors
    public int Version;   // goes up at every (re)load, so the contents rebuild
    Material mat;
    public Material FrameMat => mat;
    Texture2D tex;
    string[] loaded, failed;
    public string[] LoadedFiles => loaded;
    DateTime stamp, failedStamp;
    bool tried;

    static readonly Dictionary<string, StoreModel> all = new();

    StoreModel(string slug, string piece, string title)
    {
        Slug = slug;
        Piece = piece;
        Title = title;
        Key = piece == null ? slug : slug + "_" + piece;
    }

    public string VisName => "storehouse_" + Key;
    public bool Ready => Frame && (mat || Plugin.Headless) && (Units.Count > 0 || Planks.Count > 0 || Cells != null || Forms != null);

    // The kind(s) this model dresses: their model folders, and whether they are display furniture.
    public Kind Kind => Kinds.Stores.FirstOrDefault(k => k.Slug == Slug && k.Piece == Piece);
    public bool Display => Kind?.Display ?? false;
    public bool Mirror => Kind?.Mirror ?? false;
    public bool Heap => Kind?.Heap ?? false;

    // Stores whose units sit in crates, bays or bins: one item type per group (UnitPlan.ByGroup, DisplayPlan.cs, decides). Returns the
    // unit per stack (-1: no room), or null without groups; leaves its planned pairs, boards and split sides on the model.
    public int[] ByGroup(List<string> types, List<Vector2> at)
    {
        var result = UnitPlan.ByGroup(PlanSummary(), types, at.Select(a => new V2(a.x, a.y)).ToList(), out var state);
        Apply(state);
        return result;
    }

    // What a units-style plan reads of the model, as plain numbers (DisplayPlan.cs).
    internal UnitPlan.Model PlanSummary() => new UnitPlan.Model
    {
        Title = Title, Slug = Slug, KindSlug = Kind?.Slug, Homes = Kind?.Homes == true, KindPerBay = Kind?.Filter is { KindPerBay: true },
        Display = Display, Mirror = Mirror, Heap = Heap,
        Units = Units.Select(u => new UnitPlan.Unit
        {
            Pos = new V3(u.Pos.x, u.Pos.y, u.Pos.z), Box = new V3(u.Box.x, u.Box.y, u.Box.z), Group = u.Group, Kind = u.Kind, Item = u.Item, Copies = u.Copies.Count,
        }).ToList(),
        Crops = crops?.ToDictionary(kv => kv.Key, kv => kv.Value != null ? kv.Value.Stacks.Count : (int?)null),
        CrateFloors = crateFloors?.Count,
        Liquids = Liquids.Select(l => (l.Group, l.Item)).ToList(),
        Labels = Labels.Select(l => l.Group).ToList(),
        Places = Places.Select(pl => pl.Group).ToList(),
        Panels = Panels.Select(pn => pn.Group).ToList(),
        Bands = Bands.Keys.ToList(),
        Bindings = Bindings.Keys.ToList(),
        ItemFamily = new Dictionary<string, string>(ItemFamily, StringComparer.Ordinal),
        FamilyOrder = FamilyOrder.ToList(),
        VesselFamilies = VesselMeshes.Keys.ToList(),
        PriorSplit = new Dictionary<int, PlanSplit>(SplitSide),
        ManyKindBoards = Settings.ManyKindBoards.Value,
        Ammo = AmmoFamily,
        Extent = ExtentIn,
    };

    // What ByGroup decided, onto the model: its planned pairs, its boards stood up in prefab space (Board's plank mesh: it lies along
    // x, thin in y, wide in z, so stood up with its length front to back and its width upright), its split sides. Null: as they were.
    internal void Apply(UnitPlan.GroupState state)
    {
        if (state == null) return;
        PlannedPairs.Clear();
        foreach (int g in state.PlannedPairs) PlannedPairs.Add(g);
        Dividers.Clear();
        var rot = Quaternion.LookRotation(Vector3.up, Vector3.right);
        foreach (var d in state.Dividers)
            Dividers.Add(Matrix4x4.TRS(new Vector3(d.X, (d.Y0 + d.Y1) / 2f, (d.Z0 + d.Z1) / 2f), rot,
                new Vector3((d.Z1 - d.Z0) / Board.PlankLength, d.Thick, (d.Y1 - d.Y0) / Board.PlankWidth)));
        SplitSide.Clear();
        foreach (var kv in state.Split) SplitSide[kv.Key] = kv.Value;
    }

    // Which holder an item belongs in (UnitPlan.Family): the item's ammo family as its ammo type says, cached once it is an item.
    static readonly Dictionary<string, string> ammoFamily = new(StringComparer.Ordinal);
    internal static string AmmoFamily(string prefab)
    {
        if (ammoFamily.TryGetValue(prefab, out var f)) return f;
        var shared = ObjectDB.instance ? ObjectDB.instance.GetItemPrefab(prefab)?.GetComponent<ItemDrop>()?.m_itemData?.m_shared : null;
        if (shared == null) return null;   // not an item (yet): ask again later
        return ammoFamily[prefab] = shared.m_ammoType == "$ammo_arrows" ? "arrow" : shared.m_ammoType == "$ammo_bolts" ? "bolt" : null;
    }
    public static string Family(string prefabOrKind) => UnitPlan.Family(prefabOrKind, AmmoFamily);

    // The boards UnitPlan.SplitShared stood up between two types in one bay, in prefab space (Board's plank mesh), and per unit of a
    // split bay the board's x and the side of the type it holds.
    public readonly List<Matrix4x4> Dividers = new();
    public readonly HashSet<int> PlannedPairs = new();
    public readonly Dictionary<int, PlanSplit> SplitSide = new();   // groups home to two kinds, each on its own units

    // A copy of a split bay's unit stays on its own side of the board: the heap was settled across the whole bay, so a copy
    // that lies over the line is mirrored back across it (Joost: "the items don't lie right yet"), clear of the board.
    // Never past the bay's own wall either (a board close to one wall mirrored copies out through it).
    // False: the copy is wider than its side and would go through a board or wall; it is then not drawn (Joost's test, 25 Oct:
    // crystals sticking out through the bunker's walls with many kinds a bay).
    public static bool KeepSide(ref Matrix4x4 at, Bounds local, PlanSplit s)
    {
        var b = Geometry.Xform(at, local);
        float half = b.extents.x + 0.04f, x = b.center.x;   // +x is the left side; the board is 6 cm thick
        float lo = s.Lo + (s.LoBoard ? half : b.extents.x), hi = s.Hi - (s.HiBoard ? half : b.extents.x);
        float want = s.LoBoard && x < s.Lo + half ? 2f * s.Lo - x : s.HiBoard && x > s.Hi - half ? 2f * s.Hi - x : x;
        if (lo > hi) return false;
        want = Mathf.Clamp(want, lo, hi);
        at.m03 += want - x;
        return true;
    }

    // Half the width (x, store space) of the narrowest copy a stack of an item draws at unit u, the extent KeepSide measures: crop
    // layout stack k of the unit's crate at its scale, as is or mirrored (k >= 0), else the unit's own copies at their fit; the store's
    // Item size in both. UnitPlan.ByGroup shares a group only where each kind's side holds such a copy (Joost, 27 Oct: the Meat Rack's
    // bins empty, every meat wider than its side). Null: the item has no model to read (or no such crop stack).
    internal float? ExtentIn(string prefab, int unit, int k, bool mirrored)
    {
        if (unit < 0 || unit >= Units.Count) return null;
        var u = Units[unit];
        float grow = Kind?.ItemSize?.Value ?? 1f, best = float.MaxValue;
        // Kept per model load (each rebuild asks again): per item, crate and crop stack or per unit, and the size setting it was measured at.
        var key = (prefab, k >= 0 ? -1 - u.Group : unit, k, mirrored, Display && k < 0 ? Settings.DisplaySize.Value : grow);
        if (extents.TryGetValue(key, out var known)) return known;
        var look = ItemVisual.Get(prefab);
        if (look == null) return null;   // not kept: an item model may yet load
        if (k >= 0)
        {
            // The same layout as UnitPlan.Make's units loop chooses: the crop's own, else the generic one; drawn as the loop draws it.
            if (crops == null || (crops.TryGetValue(prefab, out var own) ? own : crops.TryGetValue("_generic", out var gen) ? gen : null) is not { } lay
                || k >= lay.Stacks.Count) return extents[key] = null;
            var drawn = Slug == "rootbin" ? look.Topless : look;
            var local = drawn.Drawn.size != Vector3.zero ? drawn.Drawn : drawn.Bounds;
            var size = look.Bounds.size;
            float sc = (lay.Scale ?? lay.Longest / Mathf.Max(1e-4f, Mathf.Max(size.x, Mathf.Max(size.y, size.z)))) * grow;
            var turn = crateTurns != null && u.Group >= 0 && u.Group < crateTurns.Count ? crateTurns[u.Group] : Quaternion.identity;
            foreach (var (_, l) in lay.Stacks[k])
                best = Mathf.Min(best, Geometry.Xform(Matrix4x4.TRS(Vector3.zero, turn * (mirrored ? new Quaternion(l.x, -l.y, -l.z, l.w) : l), Vector3.one * sc), local).extents.x);
        }
        else
        {
            var demo = u.Demo != null ? ItemVisual.Get(u.Demo) : null;
            foreach (var c in u.Copies) best = Mathf.Min(best, Geometry.Xform(Place(u, c, look, demo, Display, grow), look.Bounds).extents.x);
        }
        return extents[key] = best < float.MaxValue ? best : null;
    }
    readonly Dictionary<(string, int, int, bool, float), float?> extents = new();

    // Newest round first, per file; the round chosen in the store's Model setting first of all.
    string[] Rounds
    {
        get
        {
            var rounds = Kind?.Rounds ?? new[] { "_r6", "_r5", "_r4", "_r3", "_r2" };
            string pick = Kind?.Model?.Value;
            if (string.IsNullOrEmpty(pick) || pick == "newest") return rounds;
            return new[] { "_" + pick }.Concat(rounds.Where(r => r != "_" + pick)).ToArray();
        }
    }

    // How many bays (groups) a store's model has; 0 while it has none or isn't loaded.
    public static int BaysOf(string slug, string piece)
    {
        var m = all.Values.FirstOrDefault(x => x.Slug == slug && x.Piece == piece);
        return m == null ? 0 : m.Units.Where(u => u.Group >= 0).Select(u => u.Group).Distinct().Count();
    }

    // A new glass colour (F1, live): every see-through glass material of this model, frame strips and jars alike; placed pieces and
    // their contents share them, so nothing is rebuilt. Glass drawn opaque (no transparent shader in the build) keeps its colour.
    // Never fully clear (Joost's alpha 0, 27 Oct: the glass gone): at least 4% opaque (his own pick is 5%). One log line per change.
    public void Retint(Color c)
    {
        c.a = Mathf.Max(c.a, 0.04f);
        int n = 0;
        foreach (var g in FrameGlass.Concat(FamilyGlass.Values.SelectMany(l => l)))
            if (g.Mat && Glass.SeeThrough(g.Mat) && g.Mat.HasProperty("_Color")) { g.Mat.SetColor("_Color", c); n++; }
        Plugin.Log.LogInfo($"{Title}: glass colour now {c}, {n} material(s)" + (n == 0 ? " (none yet: the model is not loaded, or its glass is opaque)" : "") + ".");
    }

    public static StoreModel Get(string slug, string piece, string title)
    {
        string key = piece == null ? slug : slug + "_" + piece;
        if (!all.TryGetValue(key, out var m)) all[key] = m = new StoreModel(slug, piece, title);
        if (!m.Ready && !m.tried)
        {
            m.tried = true;
            var files = m.Files();
            if (files == null || !m.Load(files))
                Plugin.Log.LogError($"{title}: model files missing or unreadable in {Base}/{slug}{string.Join(" or ", m.Rounds)}; it stays a plain wood chest (live models retry).");
        }
        return m;
    }

    // Every store's contents rebuild (a dev setting that changes how items are placed).
    public static void Touch() { foreach (var m in all.Values) m.Version++; }

    // Live reload: this copy's materials, atlases and frames go with it.
    public static void ReleaseAll()
    {
        foreach (var m in all.Values)
        {
            foreach (var o in new UnityEngine.Object[] { m.mat, m.tex, m.Frame, m.Straw, m.StrawRing, m.StrawRingMat }.Concat(m.StrawShades?.Skip(1) ?? Enumerable.Empty<Material>())) if (o) UnityEngine.Object.Destroy(o);
            m.DropGlass();
            if (m.Forms != null) foreach (var f in m.Forms) if (f.Arms) UnityEngine.Object.Destroy(f.Arms);
        }
        all.Clear();
    }

    public static StoreModel ForVis(string visName) => all.Values.FirstOrDefault(m => m.VisName == visName);

    public static string AssetPath(string name) => Path.Combine(Base, name);
    static string Base => string.IsNullOrWhiteSpace(Settings.ModelFolder.Value) ? Path.Combine(Plugin.Dir, "assets") : Settings.ModelFolder.Value.Trim();

    // [frame obj, atlas png, anchors json], or null while one of them is missing.
    string[] Files()
    {
        // The dry Pantry uses the existing per-place/vessel/crop schema. Choose
        // its reviewed export atomically; missing companion meshes must never
        // silently fall through to pieces of a different round.
        if (Slug == "pantry" && Rounds[0] == "_r4")   // unless an older round is chosen
        {
            string candidate = Path.Combine(Base, "pantry_r4");
            string[] required = { "Pantry.obj", "pantry_atlas.png", "pantry_anchors.json", "Vessel_jar.obj", "Vessel_glass.obj", "Vessel_board.obj", "Vessel_basket.obj", "Vessel_platter.obj", "Vessel_crock.obj", "Vessel_sack.obj" };
            if (required.All(name => File.Exists(Path.Combine(candidate, name))))
                return required.Take(3).Select(name => Path.Combine(candidate, name)).ToArray();
        }
        // One round at a time (25 Oct: Fletcher's r3 frame was loaded with r2's anchors, each file taken from the first round that had
        // one): the newest round folder that holds all three files wins; a round missing one falls back to the whole round before it,
        // never to one file of it. check-rounds.py fails the build when a store's newest round is incomplete.
        foreach (var d in Rounds.Select(s => Path.Combine(Base, Slug + s)).Where(Directory.Exists))
        {
            string Pick(string pattern, Func<string, bool> ok) =>
                Directory.GetFiles(d, pattern).Where(x => ok(Path.GetFileName(x))).OrderByDescending(x => new FileInfo(x).Length).FirstOrDefault();
            var obj = Pick("*.obj", n => (Piece == null || n.Contains(Piece)) && !n.EndsWith("_bands.obj", StringComparison.Ordinal) && n != "Straw.obj");
            var png = Pick("*.png", n => n.ToLowerInvariant().Contains("atlas"));
            var json = Pick("*.json", n => !n.Contains("_layouts") && !n.Contains("_display") && n != PoseTable.File)   // the anchors: the biggest json but the layouts, the display sidecar and the pose table
                ?? Pick("*_layouts.json", n => true);                    // or a round that has only its layouts (Fletcher r3's cells)
            if (obj == null || png == null || json == null) continue;
            if (loggedRound != d) { loggedRound = d; Plugin.Log.LogInfo($"{Title}: files from {Path.GetFileName(d)} ({Path.GetFileName(obj)}, {Path.GetFileName(png)}, {Path.GetFileName(json)})."); }
            return new[] { obj, png, json };
        }
        return null;
    }
    string loggedRound;

    bool Load(string[] files)
    {
        if (!mat) mat = Atlas.Material(PrefabManager.Instance.GetPrefab("piece_chest_wood"), "storehouse_" + Key, Title);
        if (!mat && !Plugin.Headless) return false;
        byte[] png;
        string text;
        try { png = File.ReadAllBytes(files[1]); text = File.ReadAllText(files[2]); }
        catch (IOException) { return false; }   // still being written: next second
        List<StoreUnit> units;
        List<Plank> planks;
        var glass = new List<(string family, Mesh mesh, Dictionary<string, object> look)>();
        try
        {
            var doc = Json.Parse(text) as Dictionary<string, object>;
            // Glass first: every mesh it names must be there, or the round is not loaded at all (SCHEMA: no half-glazed variant).
            void GlassOf(string family, List<object> list)
            {
                foreach (var g in list.OfType<Dictionary<string, object>>())
                {
                    if (!g.TryGetValue("obj", out var go) || go is not string glassObj) continue;
                    var glassMesh = ObjMesh.Load(Path.Combine(Path.GetDirectoryName(files[2]), glassObj), flipX: true);
                    if (!glassMesh) throw new FileNotFoundException($"its glass mesh {glassObj} is missing");
                    glass.Add((family, glassMesh, g.TryGetValue("material", out var gm) ? gm as Dictionary<string, object> : null));
                }
            }
            if (doc != null && doc.TryGetValue("transparent_parts", out var tp) && tp is List<object> frameGlass) GlassOf(null, frameGlass);
            if (doc != null && doc.TryGetValue("transparent_parts_by_family", out var tf) && tf is Dictionary<string, object> familyGlass)
                foreach (var kv in familyGlass) if (kv.Value is List<object> l) GlassOf(kv.Key, l);
            planks = doc != null ? Plank.Parse(doc, Piece) : null;
            units = doc != null && planks == null ? Anchors.Parse(doc, Piece) : new List<StoreUnit>();
            crops = doc != null ? Anchors.ParseCrops(doc, out crateFloors, out crateTurns) : null;
            Liquids.Clear();
            Labels.Clear();
            Panels.Clear();
            Places.Clear();
            VesselMeshes.Clear();
            Bindings.Clear();
            foreach (var m in Bands.Values) if (m) UnityEngine.Object.Destroy(m);
            Bands.Clear();
            LoadBands(Path.GetDirectoryName(files[0]));
            if (Straw) UnityEngine.Object.Destroy(Straw);
            var strawFile = Path.Combine(Path.GetDirectoryName(files[0]), "Straw.obj");
            Straw = null;
            StrawSurface.Clear();
            var strawEnds = new List<int>();
            var strawNames = new List<string>();
            if (File.Exists(strawFile) && ObjMesh.Load(strawFile, flipX: true, strawEnds, strawNames) is { } loose && loose)
            {
                Straw = Roughen(loose.vertices, loose.uv, loose.triangles, strawNames.Select((n, k) => (n ?? "straw", k > 0 ? strawEnds[k - 1] : 0, strawEnds[k])).ToList(), out _) ?? loose;
                if (Straw != loose) UnityEngine.Object.Destroy(loose);
            }
            KitSnaps.Clear();
            if (doc != null && doc.TryGetValue("snap_points", out var sp) && sp is List<object> snaps)
                foreach (var sn in snaps.OfType<Dictionary<string, object>>())
                    if (sn.TryGetValue("position_unity", out var pu) && pu is List<object> l && l.Count >= 3)
                        KitSnaps.Add(new Vector3(Convert.ToSingle(l[0]), Convert.ToSingle(l[1]), Convert.ToSingle(l[2])));
            StrawTops.Clear();
            ReadStraw(files[0]);
            ItemFamily.Clear();
            FamilyOrder.Clear();
            if (doc != null && doc.TryGetValue("item_family", out var ifm) && ifm is Dictionary<string, object> itemFamilies)
                foreach (var kv in itemFamilies) if (kv.Value is string fam) ItemFamily[kv.Key] = fam;
            if (doc != null && doc.TryGetValue("families", out var fams) && fams is List<object> families)
                foreach (var f in families) if (f is string fam) FamilyOrder.Add(fam);
            if (doc != null && doc.TryGetValue("bindings", out var bd) && bd is List<object> bindings)
                foreach (var l in bindings.OfType<Dictionary<string, object>>())
                    if (l.TryGetValue("unit", out var ui) && l.TryGetValue("obj", out var o) && o is string objName
                        && ObjMesh.Load(Path.Combine(Path.GetDirectoryName(files[2]), objName), flipX: true) is { } bindingMesh && bindingMesh)
                        Bindings[(int)Convert.ToSingle(ui)] = bindingMesh;
            if (doc != null && doc.TryGetValue("vessel_meshes", out var vm) && vm is Dictionary<string, object> meshes)
                foreach (var kv in meshes)
                    if (kv.Value is string objName && ObjMesh.Load(Path.Combine(Path.GetDirectoryName(files[2]), objName), flipX: true) is { } vesselMesh && vesselMesh)
                        VesselMeshes[kv.Key] = vesselMesh;
            if (doc != null && VesselMeshes.Count > 0 && doc.TryGetValue("vessels", out var vs) && vs is List<object> vessels)
                foreach (var v in vessels.OfType<Dictionary<string, object>>())
                    if (v.TryGetValue("at", out var ao) && ao is List<object> a && a.Count >= 3)
                        Places.Add(new VesselPlace
                        {
                            Group = (int)Convert.ToSingle(v.TryGetValue("position", out var po) ? po : v.TryGetValue("bay", out var b) ? b : -1),
                            At = new Vector3(Convert.ToSingle(a[0]), Convert.ToSingle(a[1]), Convert.ToSingle(a[2])),   // anchors are in Unity space already
                            Default = v.TryGetValue("default", out var d) ? d as string : null,
                        });
            if (doc != null && doc.TryGetValue("panels", out var pn) && pn is List<object> panels)
                foreach (var l in panels.OfType<Dictionary<string, object>>())
                    if (l.TryGetValue("obj", out var o) && o is string objName && ObjMesh.Load(Path.Combine(Path.GetDirectoryName(files[2]), objName), flipX: true) is { } panelMesh && panelMesh)
                        Panels.Add(new Panel { Group = (int)Convert.ToSingle(l.TryGetValue("bay", out var b) ? b : l.TryGetValue("compartment", out var c) ? c : -1), Mesh = Geometry.SmoothNormals(panelMesh) });
            if (doc != null && doc.TryGetValue("labels", out var lb) && lb is List<object> labels)
                foreach (var l in labels.OfType<Dictionary<string, object>>())
                    if (l.TryGetValue("position", out var po) && po is List<object> pos && pos.Count >= 3)
                    {
                        var q = l.TryGetValue("rot_quat_xyzw", out var qo) && qo is List<object> qv && qv.Count >= 4
                            ? new Quaternion(Convert.ToSingle(qv[0]), Convert.ToSingle(qv[1]), Convert.ToSingle(qv[2]), Convert.ToSingle(qv[3])).normalized : Quaternion.identity;
                        Labels.Add(new Label
                        {
                            Group = (int)Convert.ToSingle(l.TryGetValue("compartment", out var c) ? c : l.TryGetValue("bay", out var b) ? b : -1),
                            Pos = new Vector3(Convert.ToSingle(pos[0]), Convert.ToSingle(pos[1]), Convert.ToSingle(pos[2])), Rot = q,
                            Longest = l.TryGetValue("fit_longest_m", out var fo) ? Convert.ToSingle(fo) : 0.22f,
                        });
                    }
            if (doc != null && doc.TryGetValue("liquids", out var lq) && lq is List<object> liquids)
                foreach (var l in liquids.OfType<Dictionary<string, object>>())
                    if (l.TryGetValue("obj", out var o) && o is string objName && ObjMesh.Load(Path.Combine(Path.GetDirectoryName(files[2]), objName), flipX: true) is { } liquidMesh && liquidMesh
                        && l.TryGetValue("floor", out var fl) && fl is List<object> f && f.Count >= 3 && l.TryGetValue("top_y", out var ty))
                        Liquids.Add(new Liquid
                        {
                            Group = (int)Convert.ToSingle(l.TryGetValue("compartment", out var c) ? c : l.TryGetValue("bay", out var b) ? b : l.TryGetValue("position", out var pp) ? pp : -1),
                            Item = l.TryGetValue("item", out var it) ? it as string : null, Mesh = liquidMesh, Floor = new Vector3(Convert.ToSingle(f[0]), Convert.ToSingle(f[1]), Convert.ToSingle(f[2])), TopY = Convert.ToSingle(ty),
                        });
        }
        catch (Exception e) { Fail(files, $"could not read {files[2]} ({e.Message})"); return false; }
        FletcherCells cells = null;
        try { cells = FletcherCells.Parse(Json.Parse(text) as Dictionary<string, object>); }
        catch (Exception e) { Fail(files, $"could not read the cells in {files[2]} ({e.Message})"); return false; }
        List<Form> forms = null;
        List<Spare> spares = null;
        try { (forms, spares) = ParseForms(Json.Parse(text) as Dictionary<string, object>); if (forms != null) forms = OrderForms(forms, files[0]); }
        catch (Exception e) { Fail(files, $"could not read the mannequins in {files[2]} ({e.Message})"); return false; }
        if ((units == null || units.Count == 0) && (planks == null || planks.Count == 0) && cells == null && forms == null) { Fail(files, $"no units or planks in {files[2]}"); return false; }
        FloorPiles piles = null;
        var layoutsFile = Path.Combine(Path.GetDirectoryName(files[2]), Slug + "_layouts.json");
        if (cells == null && File.Exists(layoutsFile))
        {
            try { piles = FloorPiles.Parse(Json.Parse(File.ReadAllText(layoutsFile)) as Dictionary<string, object>); }
            catch (Exception e) { Fail(files, $"could not read {layoutsFile} ({e.Message})"); return false; }
            if (piles == null) { Fail(files, $"{layoutsFile} is no floor_piles.v1 layout"); return false; }
        }
        Piles = piles;
        PileLook = null;
#if !RELEASE
        if (piles != null && !Plugin.Headless)
        {
            var watch = System.Diagnostics.Stopwatch.StartNew();
            try
            {
                PileLook = PileDisplay.Load(Path.GetDirectoryName(files[2]), Slug, out string why);
                if (PileLook != null)
                    Plugin.Log.LogInfo($"{Title}: display sidecar {PileLook.Schema}, {PileLook.Meshes.Count} native meshes, {PileLook.Regions.Count} regions, "
                        + $"{PileLook.Exempt.Count} exempt copies, read in {watch.ElapsedMilliseconds} ms; budget {PileDisplay.Budget} triangles.");
                else if (why != null) Plugin.Log.LogWarning($"{Title}: display sidecar not used ({why}); the game's own meshes.");
            }
            catch (Exception e) { PileLook = null; Plugin.Log.LogWarning($"{Title}: display sidecar not read ({e.Message}); the game's own meshes."); }
        }
#endif
        Cells = cells;
        Forms = forms;
        Spares = spares;
        Equip = null;
        try
        {
            Equip = ParseEquip(Json.Parse(text) as Dictionary<string, object>);
            // Tools hang and stand where the weapons do (Joost, 28 Oct: "gereedschap ... op de plek waar ook de wapens passen", the
            // modded shovel refused). Here, not in the anchors: the pose table is bound to the anchors file's bytes.
            if (Equip != null && Slug is "arsenal" or "arsenalb")
                foreach (var p in Equip) if (p.Types.Contains("OneHandedWeapon")) p.Types.Add("Tool");
            // Trinkets are worn (Joost, 28 Oct: "it's worn and should go in the armor coffer"): in the helmet trays and cubbies.
            if (Equip != null && Slug is "armorcoffer" or "armorcabinet")
                foreach (var p in Equip) if (p.Types.Contains("Helmet")) p.Types.Add("Trinket");
            Table = Equip != null ? PoseTable.Load(Path.GetDirectoryName(files[2]), files[2], Title) : null;
            Classify();
        }
        catch (Exception e) { Fail(files, $"could not read the equipment places in {files[2]} ({e.Message})"); return false; }
        bool arms = forms != null && forms.Any(f => f.ArmNames.Count > 0);
        var frameEnds = arms || (StrawTops.Count > 0 && !Straw) ? new List<int>() : null;
        var frameNames = frameEnds != null ? new List<string>() : null;
        var frame = ObjMesh.Load(files[0], flipX: true, frameEnds, frameNames);
        if (!frame || png.Length == 0) { Fail(files, $"no frame in {files[0]}"); return false; }
        var frameTris = frameEnds != null ? frame.triangles : null;   // the object ends count in these, before the arms leave the frame
        if (arms) SplitArms(frame, forms, frameEnds, frameNames);
        if (frameEnds != null && !Straw) Straw = SplitStraw(frame, frameTris, frameEnds, frameNames);
        if (mat)
        {
            if (!tex) tex = new Texture2D(2, 2, TextureFormat.RGBA32, true) { name = "storehouse_" + Key + "_atlas" };
            if (!ImageConversion.LoadImage(tex, png)) { Fail(files, $"could not read {files[1]}"); return false; }
            tex.filterMode = FilterMode.Point;
            tex.wrapMode = TextureWrapMode.Repeat;
            mat.SetTexture("_MainTex", tex);
            if (Straw && StrawShades == null)   // once per model, after the atlas is on the frame's material (the copies share that texture)
            {
                StrawShades = new[] { mat, Atlas.Shade(mat, 0.88f, $"storehouse_{Key}_straw88"), Atlas.Shade(mat, 0.76f, $"storehouse_{Key}_straw76") };
                StrawRingMat = Atlas.Shade(mat, 0.6f, $"storehouse_{Key}_strawring");
            }
        }
        if (StrawRing) UnityEngine.Object.Destroy(StrawRing);
        StrawRing = Straw && StrawSurface.Keys.Any(k => k.StartsWith("straw_u", StringComparison.Ordinal)) ? Ring(strawUv, $"storehouse_{Key}_strawring") : null;
        DropGlass();
        if (mat)   // a server draws no glass
            for (int i = 0; i < glass.Count; i++)
            {
                var part = new GlassPart { Mesh = glass[i].mesh, Mat = Glass.Make(glass[i].look, tex, mat, $"storehouse_{Key}_glass{i}", Title, Kind?.GlassColour?.Value is { } gc ? new Color(gc.r, gc.g, gc.b, Mathf.Max(gc.a, 0.04f)) : null) };
                if (glass[i].family == null) FrameGlass.Add(part);
                else (FamilyGlass.TryGetValue(glass[i].family, out var l) ? l : FamilyGlass[glass[i].family] = new List<GlassPart>()).Add(part);
            }
        Frame = frame;
        Units = units ?? new List<StoreUnit>();
        extents.Clear();
        Planks = planks ?? new List<Plank>();
        loaded = files;
        stamp = files.Max(File.GetLastWriteTimeUtc);
        Version++;
        Plugin.Log.LogInfo($"{Title}: model from {Path.GetDirectoryName(files[0])} ({Path.GetFileName(files[0])}, {frame.triangles.Length / 3} triangles, "
            + $"{frame.bounds.size:F2} m; " + (Planks.Count > 0 ? $"{Planks.Count} plank(s) packed at runtime" : $"{Units.Count} units, {Units.Sum(x => x.Copies.Count)} item copies when full")
            + $", from {Path.GetFileName(files[2])}).");
        return true;
    }

    // "mannequins": [{position, yaw, pose_name}], "spares": [{kind, position, rotation}] (the armory mannequin exports).
    static (List<Form>, List<Spare>) ParseForms(Dictionary<string, object> doc)
    {
        if (doc == null || !doc.TryGetValue("mannequins", out var mo) || mo is not List<object> list) return (null, null);
        static Vector3 V(object o) { var l = (List<object>)o; return new Vector3(Convert.ToSingle(l[0]), Convert.ToSingle(l[1]), Convert.ToSingle(l[2])); }
        var forms = list.OfType<Dictionary<string, object>>().Select(m =>
        {
            string pose = m.TryGetValue("pose_name", out var pn) ? pn as string ?? "" : "";
            int n = int.TryParse(new string(pose.Where(char.IsDigit).ToArray()), out int k) ? k : 1;
            float yaw = m.TryGetValue("yaw", out var y) ? Convert.ToSingle(y) : 0f;
            // "front_axis": "... Unity local -Z" (r2, r3) or "Unity -Z before anchor yaw" (r1): the figure looks along -z turned by its yaw.
            int front = m.TryGetValue("front_axis", out var fa) && fa is string axis && axis.Contains("Unity") && axis.Contains("-Z") ? (Mathf.Cos(yaw * Mathf.Deg2Rad) > 0f ? -1 : 1) : 0;
            return new Form { Pos = V(m["position"]), Yaw = yaw, Front = front, Pose = Math.Max(0, n - 1) % 3,   // the stand has three poses
                ArmNames = (m.TryGetValue("hand_objects", out var ho) && ho is List<object> hl ? hl.OfType<string>() : Enumerable.Empty<string>())
                    .Concat(m.TryGetValue("form_objects", out var fo) && fo is List<object> fl ? fl.OfType<string>().Where(x => armPart.IsMatch(x)) : Enumerable.Empty<string>()).Distinct().ToList() };
        }).ToList();
        var spares = new List<Spare>();
        if (doc.TryGetValue("spares", out var so) && so is List<object> sl)
            foreach (var m in sl.OfType<Dictionary<string, object>>())
                spares.Add(new Spare
                {
                    Slot = (m.TryGetValue("kind", out var kd) ? kd as string : "") switch { "helmet" => Outfits.Slot.Helmet, "chest" => Outfits.Slot.Chest, "legs" => Outfits.Slot.Legs, "cape" => Outfits.Slot.Cape, _ => Outfits.Slot.None },
                    Pos = V(m["position"]), Rot = m.TryGetValue("rotation", out var r) ? Quaternion.Euler(V(r)) : Quaternion.identity,
                });
        return (forms.Count > 0 ? forms : null, spares);
    }

    // A figure's carved arms: its fists ("hand_objects") and, of its own parts ("form_objects"), each side's upper arm, forearm and
    // wrist (r1's sleeve and wrist tenon); never the shoulder yoke or stubs, the torso or anything of another figure. By name, so a
    // new round that keeps the names is split the same way.
    static readonly System.Text.RegularExpressions.Regex armPart = new(@"_(Left|Right)_(upper|forearm|wrist_core|sleeve|wrist_tenon)(\.\d+)?$");

    // Each figure's carved arms and fists out of the frame into a mesh of their own, a part of the piece of its own (StoreContents.SyncArms
    // could hide it; it stays on since the vanilla pose, Joost, 27 Oct). A named part the frame lacks is said in the log.
    // In the vanilla Armor Stand pose when assets/armorstand_pose.json is there (ArmPose: upper arm about the shoulder, forearm and fist
    // about the elbow, onto the rig the worn sets are baked on); as carved without it.
    void SplitArms(Mesh frame, List<Form> forms, List<int> ends, List<string> names)
    {
        var tris = frame.triangles;
        var cut = new bool[tris.Length];
        Vector3[] v = frame.vertices, n = frame.normals;
        Vector2[] uv = frame.uv;
        var missing = new List<string>();
        int moved = 0;
        var pose = MannequinBaker.Vanilla();
        var posed = new List<string>();
        static D3 D(Vector3 x) => new(x.x, x.y, x.z);
        for (int f = 0; f < forms.Count; f++)
        {
            var form = forms[f];
            var parts = new List<ArmPart>();
            var uvs = new Dictionary<ArmPart, Vector2[]>();
            foreach (var hand in form.ArmNames)
            {
                int k = names.IndexOf(hand);
                if (k < 0) { missing.Add(hand); continue; }
                int from = k > 0 ? ends[k - 1] : 0;
                var part = new ArmPart { Name = hand, P = new D3[ends[k] - from], N = new D3[ends[k] - from] };
                part.Kind = ArmPose.KindOf(hand, !armPart.IsMatch(hand), out part.Side);
                var tex = new Vector2[ends[k] - from];
                for (int i = from; i < ends[k]; i++)
                {
                    cut[i] = true;
                    part.P[i - from] = D(v[tris[i]]);
                    part.N[i - from] = D(n.Length > 0 ? n[tris[i]] : Vector3.up);
                    tex[i - from] = uv.Length > 0 ? uv[tris[i]] : Vector2.zero;
                }
                parts.Add(part);
                uvs[part] = tex;
            }
            if (parts.Count == 0) continue;
            List<ArmOut> outs;
            if (pose != null && parts.All(p => p.Kind >= 0))
            {
                outs = ArmPose.Repose(parts, D(form.Pos), form.Facing, form.Yaw, pose, out string said);
                posed.Add($"figure {f + 1}: {said}");
            }
            else outs = parts.Select(p => new ArmOut { From = p, P = p.P, N = p.N }).ToList();
            var pos = new List<Vector3>();
            var nor = new List<Vector3>();
            var texs = new List<Vector2>();
            foreach (var o in outs)
            {
                var tex = uvs[o.From];
                for (int t = 0; t + 2 < o.P.Length; t += 3)
                    foreach (int c in o.Flip ? new[] { t, t + 2, t + 1 } : new[] { t, t + 1, t + 2 })
                    {
                        pos.Add(new Vector3((float)o.P[c].x, (float)o.P[c].y, (float)o.P[c].z));
                        nor.Add(new Vector3((float)o.N[c].x, (float)o.N[c].y, (float)o.N[c].z));
                        texs.Add(tex[c]);
                    }
            }
            var arms = new Mesh { name = $"storehouse_{Key}_arms" };
            if (pos.Count > 65000) arms.indexFormat = UnityEngine.Rendering.IndexFormat.UInt32;
            arms.SetVertices(pos);
            arms.SetNormals(nor);
            arms.SetUVs(0, texs);
            arms.SetTriangles(Enumerable.Range(0, pos.Count).ToArray(), 0);
            arms.RecalculateTangents();
            arms.RecalculateBounds();
            form.Arms = arms;
            moved += pos.Count / 3;
        }
        if (moved > 0) frame.SetTriangles(tris.Where((_, i) => !cut[i]).ToArray(), 0);
        Plugin.Log.LogInfo($"{Title}: {forms.Count(f => f.Arms)} figure(s)' carved arms and fists apart from the frame ({moved} triangles)"
            + (missing.Count > 0 ? $"; not in the frame, left as they are: {string.Join(", ", missing)}" : "")
            + (posed.Count > 0 ? $"; in the vanilla pose from {pose.From}:\n  {string.Join("\n  ", posed)}" : pose == null ? "; as carved (no vanilla pose file)" : "") + ".");
    }

    // The frame's straw objects (straw, straw_<n>, straw_g<group>, straw_u<unit>) out of the frame into the straw's own mesh, roughened;
    // a pad of a few faces stays in the frame as it was. tris: the frame's triangles as loaded, where the object ends count (the arms
    // may have left the frame since); the frame keeps every triangle but the straw's (no vertex is shared between objects).
    Mesh SplitStraw(Mesh frame, int[] tris, List<int> ends, List<string> names)
    {
        var objects = new List<(string, int, int)>();
        for (int k = 0; k < names.Count; k++)
            if (names[k] != null && names[k].StartsWith("straw", StringComparison.OrdinalIgnoreCase)) objects.Add((names[k], k > 0 ? ends[k - 1] : 0, ends[k]));
        var straw = Roughen(frame.vertices, frame.uv, tris, objects, out var used);
        if (!straw) return null;
        var left = frame.triangles;
        var keep = new List<int>(left.Length);
        for (int i = 0; i + 2 < left.Length; i += 3)
            if (!used.Contains(left[i])) { keep.Add(left[i]); keep.Add(left[i + 1]); keep.Add(left[i + 2]); }
        frame.SetTriangles(keep, 0);
        return straw;
    }

    // Rougher, more varied straw (Joost via M, 27 Oct). Per straw object, by corner position (its faces are flat-shaded: one vertex per
    // face corner). A sheet (a surface with an open edge, where it meets its walls) keeps that edge where it is and moves each inner
    // corner up or down by two layers of noise (9 and 3.5 cm cells, 10 and 6 mm, 3 mm down on the whole) and a little sideways (at most
    // a fifth of its shortest edge: no face folds, nothing crosses the edge to a wall). Never above the object's own top (so never above
    // a rim that cleared it), at most 18 mm down. Each face then takes one of three shades by a third layer and a hash of its own. A
    // closed object (the kit's Straw.obj: single stalks, 24 corners each) keeps its shape and takes one shade as a whole: shaking a
    // stalk only bends it. used: the source vertices taken. Null: no object worth it (all pads).
    Mesh Roughen(Vector3[] v, Vector2[] uv, int[] tris, List<(string name, int from, int to)> objects, out HashSet<int> used)
    {
        used = new HashSet<int>();
        int seed = 0;
        foreach (char ch in Key) seed = (seed * 31 + ch) % 9973;
        var pos = new List<Vector3>();
        var tex = new List<Vector2>();
        var shade = new[] { new List<int>(), new List<int>(), new List<int>() };
        int corners = 0, moved = 0, objs = 0;
        foreach (var (name, from, to) in objects)
        {
            var slot = new Dictionary<Vector3Int, int>();
            var p = new List<Vector3>();
            var shortest = new List<float>();
            var corner = new int[to - from];
            for (int i = from; i < to; i++)
            {
                var o = v[tris[i]];
                var key = Vector3Int.RoundToInt(o * 10000f);   // 0.1 mm
                if (!slot.TryGetValue(key, out int s)) { slot[key] = s = p.Count; p.Add(o); shortest.Add(float.MaxValue); }
                corner[i - from] = s;
            }
            if (p.Count < 16) continue;   // a pad of a few faces (the Produce Crates' bedding)
            objs++;
            corners += p.Count;
            for (int i = from; i < to; i++) used.Add(tris[i]);
            var edges = new Dictionary<(int, int), int>();
            for (int t = 0; t + 2 < corner.Length; t += 3)
                for (int e = 0; e < 3; e++)
                {
                    int a = corner[t + e], b = corner[t + (e + 1) % 3];
                    var k = a < b ? (a, b) : (b, a);
                    edges[k] = edges.TryGetValue(k, out int n) ? n + 1 : 1;
                    float len = Vector3.Distance(p[a], p[b]);
                    shortest[a] = Mathf.Min(shortest[a], len);
                    shortest[b] = Mathf.Min(shortest[b], len);
                }
            var edge = new HashSet<int>();
            foreach (var kv in edges) if (kv.Value == 1) { edge.Add(kv.Key.Item1); edge.Add(kv.Key.Item2); }
            bool sheet = edge.Count > 0;
            float top = p.Max(q => q.y);
            var shaken = new Vector3[p.Count];
            for (int s = 0; s < p.Count; s++)
            {
                var o = p[s];
                shaken[s] = o;
                if (!sheet || edge.Contains(s)) continue;
                float dy = 0.010f * Noise(o.x, o.z, 0.09f, seed, 0) + 0.006f * Noise(o.x, o.z, 0.035f, seed, 1) - 0.003f;
                shaken[s].y = Mathf.Clamp(o.y + dy, o.y - 0.018f, top);
                float side = 0.2f * shortest[s];
                shaken[s].x += side * Noise(o.x, o.z, 0.05f, seed, 2);
                shaken[s].z += side * Noise(o.x, o.z, 0.05f, seed, 3);
                moved++;
            }
            var surface = new Vector3[corner.Length];
            var whole = p.Aggregate(Vector3.zero, (acc, q) => acc + q) / p.Count;
            for (int t = 0; t + 2 < corner.Length; t += 3)
            {
                var c = sheet ? (shaken[corner[t]] + shaken[corner[t + 1]] + shaken[corner[t + 2]]) / 3f : whole;
                float h = 0.7f * Noise(c.x, c.z, 0.12f, seed, 4) + 0.3f * Jitter.Degrees(c, seed + (sheet ? t : objs), 1f);
                int level = h > 0.3f ? 2 : h > -0.05f ? 1 : 0;
                for (int e = 0; e < 3; e++)
                {
                    surface[t + e] = shaken[corner[t + e]];
                    shade[level].Add(pos.Count);
                    pos.Add(surface[t + e]);
                    tex.Add(uv.Length > tris[from + t + e] ? uv[tris[from + t + e]] : Vector2.zero);
                }
            }
            StrawSurface[name] = surface;
        }
        if (objs == 0) return null;
        var mesh = new Mesh { name = $"storehouse_{Key}_straw" };
        if (pos.Count > 65000) mesh.indexFormat = UnityEngine.Rendering.IndexFormat.UInt32;
        mesh.SetVertices(pos);
        mesh.SetUVs(0, tex);
        mesh.subMeshCount = 3;
        for (int k = 0; k < 3; k++) mesh.SetTriangles(shade[k], k);
        mesh.RecalculateNormals();
        mesh.RecalculateTangents();
        mesh.RecalculateBounds();
        strawUv = Rect.MinMaxRect(tex.Min(t => t.x), tex.Min(t => t.y), tex.Max(t => t.x), tex.Max(t => t.y));
        Plugin.Log.LogInfo($"{Title}: straw roughened ({moved} of {corners} vertices moved, {objs} object(s), {pos.Count / 3} triangles in three shades "
            + $"{shade[0].Count / 3}/{shade[1].Count / 3}/{shade[2].Count / 3}), a part of its own, never solid.");
        return mesh;
    }

    // Smooth value noise in [-1, 1] over the xz plane (cells of the given size), on Jitter's hash: the same at every load of a store.
    static float Noise(float x, float z, float cell, int seed, int layer)
    {
        float fx = x / cell, fz = z / cell;
        int ix = Mathf.FloorToInt(fx), iz = Mathf.FloorToInt(fz);
        float tx = fx - ix, tz = fz - iz;
        tx = tx * tx * (3f - 2f * tx);
        tz = tz * tz * (3f - 2f * tz);
        float L(int i, int k) => Jitter.Degrees(new Vector3(i * 0.1f, seed * 0.1f, k * 0.1f), layer, 1f);
        return Mathf.Lerp(Mathf.Lerp(L(ix, iz), L(ix + 1, iz), tx), Mathf.Lerp(L(ix, iz + 1), L(ix + 1, iz + 1), tx), tz);
    }

    // The entry ring at unit size (the item's cross-section reaches about r 0.5): a shallow dish a few mm proud of the straw, so the
    // rough straw never swallows it, its middle 3 mm under its lip at r 0.75 (the dip), its edge 3 mm down into the straw; on the
    // straw's own tile. 60 triangles.
    static Mesh Ring(Rect uvs, string name)
    {
        const int n = 12;
        float[] r = { 0.5f, 0.75f, 1f }, y = { 0.002f, 0.004f, -0.003f };
        var pos = new List<Vector3> { new(0f, 0.001f, 0f) };
        for (int k = 0; k < 3; k++)
            for (int i = 0; i < n; i++)
                pos.Add(new Vector3(r[k] * Mathf.Cos(i * 2f * Mathf.PI / n), y[k], r[k] * Mathf.Sin(i * 2f * Mathf.PI / n)));
        var tris = new List<int>();
        for (int i = 0; i < n; i++)
        {
            int j = (i + 1) % n;
            tris.AddRange(new[] { 0, 1 + j, 1 + i });   // clockwise seen from above: facing up
            for (int k = 0; k < 2; k++)
            {
                int a0 = 1 + k * n + i, a1 = 1 + k * n + j;
                tris.AddRange(new[] { a0, a1, a1 + n, a0, a1 + n, a0 + n });
            }
        }
        var mesh = new Mesh { name = name };
        mesh.SetVertices(pos);
        mesh.SetUVs(0, pos.Select(q => new Vector2(uvs.center.x + q.x * uvs.width * 0.25f, uvs.center.y + q.z * uvs.height * 0.25f)).ToList());
        mesh.SetTriangles(tris, 0);
        mesh.RecalculateNormals();
        mesh.RecalculateTangents();
        mesh.RecalculateBounds();
        return mesh;
    }

    // The rough straw's height at x/z in one straw object (its highest face there); NaN: outside it.
    public static float StrawHeight(Vector3[] surface, float x, float z)
    {
        float best = float.NaN;
        for (int t = 0; t + 2 < surface.Length; t += 3)
        {
            Vector3 a = surface[t], b = surface[t + 1], c = surface[t + 2];
            float d = (b.z - c.z) * (a.x - c.x) + (c.x - b.x) * (a.z - c.z);
            if (Mathf.Abs(d) < 1e-9f) continue;
            float l1 = ((b.z - c.z) * (x - c.x) + (c.x - b.x) * (z - c.z)) / d, l2 = ((c.z - a.z) * (x - c.x) + (a.x - c.x) * (z - c.z)) / d, l3 = 1f - l1 - l2;
            if (l1 < -1e-4f || l2 < -1e-4f || l3 < -1e-4f) continue;
            float y = l1 * a.y + l2 * b.y + l3 * c.y;
            if (float.IsNaN(best) || y > best) best = y;
        }
        return best;
    }

    // Which way the figures face and the window's row order, from where they stand in the frame, never from a setting or the export's
    // order (the coordinator, 25 Oct: the Rail's sets faced its back rail and rows 1-3 dressed the right-hand figures). Figures on
    // two sides of the piece's middle (the Island) face away from it. A single row faces the open side: the side where the deck
    // reaches past every tall part (the rail stands behind them), measured on the frame's OBJ (z is the same in piece space).
    // Rows run left to right as seen from the side they face: facing +z the viewer looks toward -z (x descending), facing -z
    // toward +z (x ascending). The +z-facing side comes first; on a two-sided piece the other is the back.
    // A figure whose anchor says its front ("front_axis") faces that way: the open Armor Stand (no back rail, 27 Oct) weighs more in
    // front than behind, so the open-side rule turned its worn set to its back; on every other piece the two agree.
    static List<Form> OrderForms(List<Form> forms, string obj)
    {
        float zMin = forms.Min(f => f.Pos.z), zMax = forms.Max(f => f.Pos.z), mid = (zMin + zMax) / 2f;
        bool twoSides = zMax - zMin > 0.05f;
        int row = twoSides || forms.All(f => f.Front != 0) ? 0 : OpenSide(obj, mid);
        foreach (var f in forms) f.Facing = f.Front != 0 ? f.Front : twoSides ? (f.Pos.z > mid ? 1 : -1) : row;
        int first = forms.Any(f => f.Facing > 0) ? 1 : -1;
        foreach (var f in forms) f.Back = f.Facing != first;
        return forms.Where(f => !f.Back).Concat(forms.Where(f => f.Back)).Select((f, i) => (f, i))
            .OrderBy(x => x.f.Back).ThenBy(x => -x.f.Facing * x.f.Pos.x).Select(x => x.f).ToList();
    }

    // -1 or +1: the open z side of a single row, the side with less tall geometry (above 30 cm) more than 20 cm beyond the figures'
    // line; the back rail and its posts weigh on the other side. The deck's reach alone failed on the r3 frames, whose arms come within
    // a few cm of the deck edge (25 Oct; the mass agrees on every rail frame, e.g. 918 behind against 477 in front).
    static int OpenSide(string obj, float figureZ)
    {
        int behindPlus = 0, behindMinus = 0;
        foreach (var line in File.ReadLines(obj))
        {
            if (!line.StartsWith("v ", StringComparison.Ordinal)) continue;
            var p = line.Split((char[])null, StringSplitOptions.RemoveEmptyEntries);
            if (p.Length < 4) continue;
            float y = float.Parse(p[2], CultureInfo.InvariantCulture), z = float.Parse(p[3], CultureInfo.InvariantCulture);
            if (y <= 0.3f) continue;
            if (z > figureZ + 0.2f) behindPlus++;
            else if (z < figureZ - 0.2f) behindMinus++;
        }
        return behindPlus >= behindMinus ? -1 : 1;
    }

    void ReadStraw(string obj)
    {
        var ys = new List<float>();
        string current = null;
        foreach (var line in File.ReadLines(obj))
        {
            if (line.StartsWith("v ", StringComparison.Ordinal))
            {
                var p = line.Split((char[])null, StringSplitOptions.RemoveEmptyEntries);
                ys.Add(p.Length > 2 ? float.Parse(p[2], CultureInfo.InvariantCulture) : 0f);
            }
            else if (line.StartsWith("o ", StringComparison.Ordinal)) current = line.Substring(2).Trim();
            else if (current != null && current.StartsWith("straw", StringComparison.OrdinalIgnoreCase) && line.StartsWith("f ", StringComparison.Ordinal))
                foreach (var c in line.Split((char[])null, StringSplitOptions.RemoveEmptyEntries).Skip(1))
                {
                    int i = int.Parse(c.Split('/')[0], CultureInfo.InvariantCulture);
                    float y = ys[i > 0 ? i - 1 : ys.Count + i];
                    StrawTops[current] = StrawTops.TryGetValue(current, out var top) ? Mathf.Max(top, y) : y;
                }
        }
        if (StrawTops.Count > 0) Plugin.Log.LogInfo($"{Title}: {StrawTops.Count} straw object(s), never a support (tops {StrawTops.Values.Min():F3}-{StrawTops.Values.Max():F3} m).");
    }

    // The band objects of a round, split into one mesh per group (in file order: ObjMesh gives each object's index end).
    void LoadBands(string folder)
    {
        var path = Directory.GetFiles(folder, "*_bands.obj").FirstOrDefault();
        if (path == null) return;
        var ends = new List<int>();
        var all = ObjMesh.Load(path, flipX: true, ends);
        if (!all) return;
        var names = File.ReadLines(path).Where(l => l.StartsWith("o ", StringComparison.Ordinal)).Select(l => l.Substring(2).Trim()).ToList();
        var tris = all.triangles;
        int start = 0;
        for (int k = 0; k < ends.Count && k < names.Count; k++)
        {
            var m = System.Text.RegularExpressions.Regex.Match(names[k], @"band_g(\d+)$");
            if (m.Success && ends[k] > start)
            {
                var band = new Mesh { name = "storehouse_" + names[k], indexFormat = all.indexFormat };
                band.SetVertices(all.vertices);
                band.SetNormals(all.normals);
                band.SetUVs(0, all.uv);
                band.SetTriangles(tris.Skip(start).Take(ends[k] - start).ToArray(), 0);
                band.RecalculateBounds();
                Bands[int.Parse(m.Groups[1].Value)] = band;
            }
            start = ends[k];
        }
        UnityEngine.Object.Destroy(all);
        Plugin.Log.LogInfo($"{Title}: {Bands.Count} colour band(s) from {Path.GetFileName(path)}.");
    }

    static List<EquipPlace> ParseEquip(Dictionary<string, object> doc)
    {
        if (doc == null) return null;
        var units = doc.TryGetValue("units_data", out var ud) ? ud as List<object> : null;
        var kit = units == null ? KitPlaces(doc) : null;
        if (units == null && kit == null) return null;
        static Vector3? V3(Dictionary<string, object> d, string k) => d.TryGetValue(k, out var v) && v is List<object> l && l.Count >= 3
            ? new Vector3(Convert.ToSingle(l[0]), Convert.ToSingle(l[1]), Convert.ToSingle(l[2])) : null;
        static Quaternion? Q4(Dictionary<string, object> d, string k) => d.TryGetValue(k, out var v) && v is List<object> l && l.Count >= 4
            ? new Quaternion(Convert.ToSingle(l[0]), Convert.ToSingle(l[1]), Convert.ToSingle(l[2]), Convert.ToSingle(l[3])).normalized : null;
        var places = kit ?? new List<EquipPlace>();
        int i = 0;
        foreach (var u in (units ?? new List<object>()).OfType<Dictionary<string, object>>())
        {
            int index = i++;
            string[] types = null;
            bool saddle = false;
            if (u.TryGetValue("equipment_types", out var et) && et is List<object> a) types = a.OfType<string>().ToArray();
            else if (u.TryGetValue("accepted_item_types", out var at) && at is List<object> b) types = b.OfType<string>().ToArray();
            else if (u.TryGetValue("allocation_group", out var ag) && ag is string group && EquipRules.Groups.TryGetValue(group, out var g)) { types = g; saddle = group == "saddles"; }
            if (types == null) continue;
            var copy = u.TryGetValue("copies", out var co) && co is List<object> cl ? cl.OfType<Dictionary<string, object>>().FirstOrDefault() : null;
            var rot = (V3(u, "rotation") is { } ue ? Quaternion.Euler(ue) : Quaternion.identity)
                * (copy == null ? Quaternion.identity : Q4(copy, "rot_quat_xyzw") ?? Q4(copy, "quat_xyzw") ?? (V3(copy, "rotation") is { } ce ? Quaternion.Euler(ce) : Quaternion.identity));
            string kind = u.TryGetValue("kind", out var k) ? k as string ?? "" : "";
            string place = u.TryGetValue("place", out var pl) ? pl as string ?? "" : "";
            places.Add(new EquipPlace
            {
                Unit = index, Types = new HashSet<string>(types, StringComparer.Ordinal), Saddle = saddle,
                Name = (place.Length > 0 && place.Length <= 24 && place.IndexOf(';') < 0 ? place : kind).Replace('_', ' '),
                Featured = kind.Contains("featured") || place.StartsWith("featured", StringComparison.Ordinal) || u.TryGetValue("feature_priority", out var fp) && fp is bool f && f,
                Pos = (V3(u, "position") ?? Vector3.zero) + (copy != null && V3(copy, "offset") is { } off ? off : Vector3.zero),
                Box = V3(u, "box_size") ?? V3(u, "box") ?? Vector3.one,
                Bottom = V3(u, "bottom_position_unity"),
                OnBottom = copy != null && copy.TryGetValue("anchor", out var an) && an as string == "bottom_center",
                Rot = rot,
                Example = (u.TryGetValue("example_item", out var ex) ? ex : u.TryGetValue("render_item", out var ri) ? ri : null) as string,
                Layer = copy != null && copy.TryGetValue("layer", out var ly) ? (int)Convert.ToSingle(ly) : 0,
                ExplicitLayer = copy != null && copy.ContainsKey("layer"),
                Clear = V3(u, "clear_box") ?? (u.TryGetValue("clear_box", out var cb) && cb is Dictionary<string, object> cbd ? V3(cbd, "size") : null),
                // A stacked column's clear box is shared and has a fixed ceiling in prefab space (storehouse-clear-box/1): each layer
                // rests on what lies below and must stay under that ceiling.
                FixedCeiling = u.TryGetValue("clear_box", out var cb2) && cb2 is Dictionary<string, object> cbd2 && cbd2.TryGetValue("fixed_ceiling_unity", out var fc) ? Convert.ToSingle(fc) : (float?)null,
            });
        }
        // Columns (the coordinator's Blender check of the mirror, 25 Oct: Armory armor floating and overlapping): places at one x/z
        // whose boxes touch form a stack, the higher on the lower, whether the export numbers the layers ("layer", one position) or
        // gives each its own height (boxes on top of each other). Shelves apart, with a gap between their boxes, stay apart.
        foreach (var group in places.GroupBy(q => (Mathf.RoundToInt(q.Pos.x * 1000f), Mathf.RoundToInt(q.Pos.z * 1000f))))
        {
            var list = group.OrderBy(q => q.Pos.y).ThenBy(q => q.Layer).ToList();
            var segments = new List<List<EquipPlace>>();
            foreach (var q in list)
            {
                var last = segments.Count > 0 ? segments[^1][^1] : null;
                bool joins = last != null && (q.ExplicitLayer && last.ExplicitLayer ? Mathf.Abs(q.Pos.y - last.Pos.y) < 1e-3f
                    : !q.ExplicitLayer && !last.ExplicitLayer && Mathf.Abs(last.Pos.y + last.Box.y * 0.5f - (q.Pos.y - q.Box.y * 0.5f)) < 0.01f);
                if (joins) segments[^1].Add(q); else segments.Add(new List<EquipPlace> { q });
            }
            for (int n = 0; n < segments.Count; n++)
            {
                var seg = segments[n];
                float ceiling = n + 1 < segments.Count ? segments[n + 1].Min(q => q.ExplicitLayer ? q.Pos.y : q.Pos.y - q.Box.y * 0.5f) : float.PositiveInfinity;
                foreach (var q in seg) q.Ceiling = ceiling;
                float top = seg.Max(q => (q.ExplicitLayer ? q.Pos.y + q.Box.y : q.Pos.y + q.Box.y * 0.5f));   // a layered column's box starts at its base
                for (int k = 0; k < seg.Count; k++)
                {
                    if (!seg[k].ExplicitLayer) seg[k].Layer = k;
                    seg[k].Column = new Vector3Int(group.Key.Item1, n, group.Key.Item2);
                    seg[k].StackTop = top;
                }
            }
        }
        return places.Count > 0 ? places : null;
    }

    // The Arsenal kit (arsenal-kit/concept-3, Sol, 25 Oct): "places" in Blender space (Unity = -x, z, -y; its Unity turn is C R C^T,
    // checked against matrix_blender for all 86 places). Each place is its example's bounds: hung from the arm tops at the example's
    // head fraction (the spine), else standing on the bounds' bottom (heel slots, runners, the long box's floor through the straw).
    // The clear boxes are left out: they are the largest frame-free part of the item's room, smaller than the item itself. An item
    // fits by its example, in the place's own frame (ByExample, Excess), not by these bounds: r5's leans made them a tilted box.
    static List<EquipPlace> KitPlaces(Dictionary<string, object> doc)
    {
        if (!doc.TryGetValue("places", out var pl) || pl is not List<object> list) return null;
        static Vector3 U(List<object> b) => new Vector3(-Convert.ToSingle(b[0]), Convert.ToSingle(b[2]), -Convert.ToSingle(b[1]));
        var places = new List<EquipPlace>();
        int i = 0;
        foreach (var p in list.OfType<Dictionary<string, object>>())
        {
            int index = i++;
            string kind = p.TryGetValue("kind", out var k) ? k as string : null;
            if (EquipRules.KitAccepts(kind) is not { } accepts) continue;
            if (!(p.TryGetValue("bounds_blender", out var bo) && bo is Dictionary<string, object> b && b.TryGetValue("min", out var mn) && mn is List<object> min
                && b.TryGetValue("max", out var mx) && mx is List<object> max)) continue;
            Vector3 lower = Vector3.Min(U(min), U(max)), upper = Vector3.Max(U(min), U(max));   // x and z swap ends under the flip
            var place = new EquipPlace
            {
                Unit = index, Types = new HashSet<string>(EquipRules.KitTypes(kind), StringComparer.Ordinal), Accepts = accepts,
                Name = kind switch { "shield_oversize" => "large shield", "sword_long" => "greatsword", "two_handed_axe" => "battleaxe", _ => kind.Replace('_', ' ') },
                Pos = (lower + upper) * 0.5f, Box = upper - lower,
                Rot = p.TryGetValue("rotation_unity_quat_xyzw", out var qo) && qo is List<object> q && q.Count >= 4
                    ? new Quaternion(Convert.ToSingle(q[0]), Convert.ToSingle(q[1]), Convert.ToSingle(q[2]), Convert.ToSingle(q[3])).normalized : Quaternion.identity,
                Example = p.TryGetValue("prefab", out var ex) ? ex as string : null, ByExample = true,
                Pose = p.TryGetValue("position_unity", out var po) && po is List<object> pu && pu.Count >= 3
                    ? new Vector3(Convert.ToSingle(pu[0]), Convert.ToSingle(pu[1]), Convert.ToSingle(pu[2])) : null,
            };
            if (p.TryGetValue("arm_contacts", out var ac) && ac is List<object> contacts && contacts.OfType<Dictionary<string, object>>().FirstOrDefault() is { } c
                && c.TryGetValue("top_z", out var tz) && c.TryGetValue("head_fraction", out var hf))
            {
                place.HangY = Convert.ToSingle(tz);
                place.HangAt = Convert.ToSingle(hf);
            }
            else place.Bottom = new Vector3(place.Pos.x, lower.y, place.Pos.z);
            places.Add(place);
        }
        return places.Count > 0 ? places : null;
    }

    // A models-session pose table beside the anchors (pose_table.json, written by pose-table.py from the delivered table: Long Rack
    // r5c's lean table, 27 Oct; the Spine's hang table): per (place, prefab) the pose Sol checked against the real frame and item, or
    // none. In a round that has one, an item goes only where its row fits and is drawn exactly as the row says, T(pivot) R T(-centre)
    // in ItemVisual's turned space (the wiring note: never the example's pose, the kind filter or the shared clear box instead); an
    // item with no row goes nowhere. A table may cover some places only (Arsenal B's: its six shield places); the others keep the
    // round's own rules. Refused, and the round's own rules kept, when it was made for other anchors. Its "conflicts" (the
    // Spine's: 220 pairs of poses in neighbouring places that cross, each checked against the widest neighbour) keep an item from a
    // place while a neighbour holds what it would cross (Allocate).
    public sealed class PoseTable
    {
        public const string File = "pose_table.json";
        public sealed class Row { public bool Fit; public Vector3 Pivot, Centre; public Quaternion Rot; public string Reason; public Vector3[] Contacts; }   // Contacts: where it rests on the frame, one point per arm (the Spine)
        readonly Dictionary<(int, string), Row> rows = new();
        readonly HashSet<(int, string, int, string)> crossing = new();
        readonly HashSet<int> covered = new();
        // The Arsenal's: per neighbouring pair of places (nearer, farther from the end it is seen from) and the items in them, how
        // much of each is seen (Sol's renders from the aisle camera); crossing pairs are not in it.
        readonly Dictionary<(int, string, int, string), (float near, float far)> seen = new();
        public bool AnyVisibility => seen.Count > 0;
        public (float near, float far)? Seen(int near, string nearPrefab, int far, string farPrefab) =>
            seen.TryGetValue((near, nearPrefab, far, farPrefab), out var v) ? v : null;
        public bool Covers(int place) => covered.Contains(place);
        // An item with a pose in some place of the table; one with none keeps the round's own rules, never left in the chest for
        // want of a row (Joost via M, 27 Oct: "never hide items just because a table has no row").
        readonly HashSet<string> posed = new(StringComparer.Ordinal);
        public bool Rules(int place, string prefab) => covered.Contains(place) && prefab != null && posed.Contains(prefab);
        public bool AnyCrossing => crossing.Count > 0;
        public bool Crosses(int place, string prefab, int other, string otherPrefab) =>
            crossing.Contains((place, prefab, other, otherPrefab)) || crossing.Contains((other, otherPrefab, place, prefab));
        // Per pose (place, prefab) the poses it crosses, both ways, the prefabs as numbers: the placement's Clash walks those few instead
        // of every place by name pair (FEEDBACK-0.8 item 3: about 670,000 lookups per change of the Spine's contents). Id -1: the
        // prefab crosses nothing. Built at first use after the load.
        readonly Dictionary<string, int> ids = new(StringComparer.Ordinal);
        Dictionary<(int, int), (int unit, int id)[]> crossOf;
        static readonly (int unit, int id)[] crossesNothing = new (int, int)[0];
        public int Id(string prefab) { Index(); return prefab != null && ids.TryGetValue(prefab, out int n) ? n : -1; }
        public (int unit, int id)[] CrossOf(int place, int id) { Index(); return id >= 0 && crossOf.TryGetValue((place, id), out var l) ? l : crossesNothing; }
        void Index()
        {
            if (crossOf != null) return;
            var lists = new Dictionary<(int, int), HashSet<(int, int)>>();
            int Of(string prefab) { if (!ids.TryGetValue(prefab, out int n)) ids[prefab] = n = ids.Count; return n; }
            void Link((int, int) a, (int, int) b) { if (!lists.TryGetValue(a, out var to)) lists[a] = to = new HashSet<(int, int)>(); to.Add(b); }
            foreach (var (place, prefab, other, otherPrefab) in crossing)
            {
                if (prefab == null || otherPrefab == null) continue;
                var a = (place, Of(prefab));
                var b = (other, Of(otherPrefab));
                Link(a, b);
                Link(b, a);
            }
            crossOf = lists.ToDictionary(kv => kv.Key, kv => kv.Value.ToArray());
        }
        public string Label;
        public int Fits, Count, Places, Prefabs;
        public Row Get(int place, string prefab) => prefab != null && rows.TryGetValue((place, prefab), out var r) ? r : null;

        public static PoseTable Load(string folder, string anchorsPath, string title)
        {
            string path = Path.Combine(folder, File);
            if (!System.IO.File.Exists(path)) return null;
            try
            {
                var doc = Json.Parse(System.IO.File.ReadAllText(path)) as Dictionary<string, object>;
                if (doc == null || !(doc.TryGetValue("schema", out var sc) && sc as string == "storehouse-pose-table/1")) throw new InvalidDataException("not a storehouse-pose-table/1");
                string want = doc.TryGetValue("anchors_sha256", out var s) ? s as string ?? "" : "";
                string have;
                using (var sha = System.Security.Cryptography.SHA256.Create())
                    have = string.Concat(sha.ComputeHash(System.IO.File.ReadAllBytes(anchorsPath)).Select(b => b.ToString("x2")));
                if (!string.Equals(want, have, StringComparison.OrdinalIgnoreCase))
                {
                    Plugin.Log.LogError($"{title}: {File} was made for other anchors ({want.Substring(0, Math.Min(12, want.Length))}, these are {have.Substring(0, 12)}); not used, the round's own rules instead.");
                    return null;
                }
                var t = new PoseTable { Label = doc.TryGetValue("label", out var l) ? l as string : null };
                static float F(object o) => Convert.ToSingle(o, CultureInfo.InvariantCulture);
                foreach (var r in ((List<object>)doc["rows"]).OfType<List<object>>())
                {
                    var row = new Row { Fit = Convert.ToInt32(r[2], CultureInfo.InvariantCulture) == 1 };
                    if (row.Fit)
                    {
                        row.Pivot = new Vector3(F(r[3]), F(r[4]), F(r[5]));
                        row.Rot = new Quaternion(F(r[6]), F(r[7]), F(r[8]), F(r[9])).normalized;
                        row.Centre = new Vector3(F(r[10]), F(r[11]), F(r[12]));
                        if (r.Count > 13 && r[13] is List<object> cs)
                            row.Contacts = cs.OfType<List<object>>().Select(c => new Vector3(F(c[0]), F(c[1]), F(c[2]))).ToArray();
                        t.Fits++;
                    }
                    else row.Reason = r.Count > 3 ? r[3] as string : null;
                    if (row.Fit) t.posed.Add(r[1] as string);
                    t.rows[(Convert.ToInt32(r[0], CultureInfo.InvariantCulture), r[1] as string)] = row;
                }
                if (doc.TryGetValue("visibility", out var vo) && vo is List<object> vis)
                    foreach (var v in vis.OfType<List<object>>())
                        t.seen[(Convert.ToInt32(v[0], CultureInfo.InvariantCulture), v[1] as string, Convert.ToInt32(v[2], CultureInfo.InvariantCulture), v[3] as string)] = (F(v[4]), F(v[5]));
                if (doc.TryGetValue("conflicts", out var co) && co is List<object> pairs)
                    foreach (var c in pairs.OfType<List<object>>())
                        t.crossing.Add((Convert.ToInt32(c[0], CultureInfo.InvariantCulture), c[1] as string, Convert.ToInt32(c[2], CultureInfo.InvariantCulture), c[3] as string));
                t.Count = t.rows.Count;
                foreach (var k in t.rows.Keys) t.covered.Add(k.Item1);
                t.Places = t.covered.Count;
                t.Prefabs = t.rows.Keys.Select(k => k.Item2).Distinct().Count();
                Plugin.Log.LogInfo($"{title}: pose table {t.Label ?? File}: {t.Fits} poses, {t.Count - t.Fits} without, {t.Places} places x {t.Prefabs} prefabs, {t.crossing.Count} neighbour pairs that cross, {t.seen.Count} measured for visibility, made for these anchors.");
                return t;
            }
            catch (Exception e)
            {
                Plugin.Log.LogError($"{title}: {File} not read ({e.Message}); the round's own rules instead.");
                return null;
            }
        }
    }
    public PoseTable Table;

    // Where each item goes (index into Equip per item, -1: stored unseen). The featured place takes the best shield; then every item
    // gets a place of its window block's class where its true size fits, as many as any arrangement allows (item 3, 27 Oct: the
    // Shield Trough stopped at 8 of 10 and the Armor Coffer refused a breastplate while a rearrangement had room): small items to
    // small places first, and a bigger place's item moves on when only that place takes a newcomer. Piles take items by true height.
    // size: an item's true size at a place's turn (null: no model). classOf: per item its block's class (-1 or null: any class
    // that takes it). notes: per item, where it went or why it stays unseen (for the log while the places are new).
    public int[] Allocate(List<ItemDrop.ItemData> items, Func<ItemDrop.ItemData, Quaternion, Vector3?> size, List<string> notes = null, Func<ItemDrop.ItemData, int> classOf = null) =>
        Allocate(items, size, out _, out _, notes, classOf);

    // The classes and piles of the places, and the window's cells (Classes): from the anchors alone.
    void Classify()
    {
        Classes = null; CellClass = null; CellHint = null; Stacks = null;
        scaleFit.Clear();
        fitCache.Clear();
        basis = null;
        if (Equip == null) return;
        Classes = new List<EquipClass>();
        var byKey = new Dictionary<string, EquipClass>(StringComparer.Ordinal);
        for (int k = 0; k < Equip.Count; k++)
        {
            var p = Equip[k];
            var accepts = EquipRules.ClassAccepts(p.Accepts);
            string key = accepts != null ? accepts.Method.Name : (p.Saddle ? "saddle|" : "") + string.Join(",", p.Types.OrderBy(t => t, StringComparer.Ordinal));
            if (!byKey.TryGetValue(key, out var c))
            {
                byKey[key] = c = new EquipClass { Accepts = accepts, Types = p.Types, Saddle = p.Saddle, Name = EquipRules.ClassName(p) };
                Classes.Add(c);
            }
            p.Class = Classes.IndexOf(c);
            c.Places.Add(k);
        }
        var cells = new List<int>();
        var hints = new List<string>();
        foreach (var c in Classes)
        {
            c.First = cells.Count;
            // Faded icons like the Armory Rails' (Joost, 27 Oct, item 4): a block taking several armor types shows them in turn
            // (chest, legs, cape), any other block the item each of its places was made for.
            var cycle = c.Accepts == null ? EquipRules.TypeHints.Where(kv => c.Types.Contains(kv.Key)).Select(kv => kv.Value).ToList() : new List<string>();
            for (int j = 0; j < c.Places.Count; j++)
            {
                cells.Add(Classes.IndexOf(c));
                var p = Equip[c.Places[j]];
                hints.Add(cycle.Count > 1 ? cycle[j % cycle.Count] : p.Example ?? cycle.FirstOrDefault());
            }
        }
        CellClass = cells.ToArray();
        CellHint = hints.ToArray();
        Stacks = new List<List<int>>();
        foreach (var g in Enumerable.Range(0, Equip.Count).GroupBy(k => Equip[k].Column).Where(g => g.Count() > 1))
        {
            var pile = g.OrderBy(k => Equip[k].Layer).ToList();
            foreach (int k in pile) Equip[k].Pile = Stacks.Count;
            Stacks.Add(pile);
        }
    }

    // The turn an item fits a place in (one of Turns), or null.
    public static Quaternion? FitTurn(EquipPlace p, ItemDrop.ItemData it, Func<ItemDrop.ItemData, Quaternion, Vector3?> size)
    {
        var own = size(it, Quaternion.identity);
        foreach (var q in Turns(p.Rot, it.m_shared.m_itemType == ItemDrop.ItemData.ItemType.Shield))
            if (size(it, q) is { } d && Excess(p, d, own, q) <= 0f) return q;
        return null;
    }

    // A place's example as the game measures it (its own true size, the same measure as the item it is compared with); null: no
    // example, or no such item (yet).
    public static Vector3? ExampleSize(EquipPlace p)
    {
        if (p.Example == null) return null;
        if (p.ExampleSize is { } known) return known;
        if (ItemVisual.Get(p.Example) is not { } v) return null;
        return p.ExampleSize = v.TrueSize;
    }

    // A pile's floor and the height its items may fill (true heights, 1 mm apart as they are drawn).
    public (float floor, float room) PileRoom(int pile)
    {
        var b = Equip[Stacks[pile][0]];
        float floor = b.Bottom?.y ?? (b.ExplicitLayer || b.OnBottom ? b.Pos.y : b.Pos.y - b.Box.y * 0.5f);
        return (floor, (b.FixedCeiling ?? b.StackTop + 0.01f) - floor);
    }

    // The turns an item may take in a place, in order of preference: as the place says; a quarter turn about up (an axe broader
    // than deep, a staff; the coordinator, 25 Oct: three gold axes and a berserker axe fit turned); a shield also with its axes
    // swapped, so its thickness can lie along the box's thin axis (a square shield where a round one stands).
    public static IEnumerable<Quaternion> Turns(Quaternion place, bool shield)
    {
        yield return place;
        yield return Quaternion.Euler(0f, 90f, 0f) * place;
        if (!shield) yield break;
        foreach (var q in new[] { Quaternion.Euler(90f, 0f, 0f), Quaternion.Euler(0f, 0f, 90f), Quaternion.Euler(90f, 90f, 0f), Quaternion.Euler(0f, 90f, 90f) })
            yield return q * place;
    }

    // How far an item's true size d (already turned) reaches past what a place allows, in metres: 0 or less fits; infinity: never
    // (a flat thing on its edge). own: its size unturned; turn: the turn d is at. Shared by Allocate and the fit report.
    public static float Excess(EquipPlace p, Vector3 d, Vector3? own, Quaternion? turn = null)
    {
        float rest = p.Bottom?.y ?? (p.HangY is { } hang ? hang - p.HangAt * d.y : p.OnBottom || p.ExplicitLayer ? p.Pos.y : p.Pos.y - p.Box.y * 0.5f);
        if (p.Clear is { } exact)   // the frame-free box: exact; a shared stack box by its fixed ceiling
        {
            // It still takes its own example as the game measures it, turned as it stands there, up to the 2 cm every other place
            // allows (Arsenal B r6, 27 Oct: its leaned shield bays refused the Iron Buckler they were made for, by 8 mm, and stood
            // empty). More than that is a model that differs from the game's (the Banded Shield 0.95 m there, 1.34 m in the game).
            var clear = ExampleSize(p) is { } demo && Turned(p.Rot, demo) - exact is var over && Mathf.Max(over.x, over.y, over.z) <= 0.02f
                ? Vector3.Max(exact, Turned(p.Rot, demo)) : exact;
            return Mathf.Max(d.x - clear.x, d.z - clear.z, p.FixedCeiling is { } fc ? rest + d.y - fc : d.y - clear.y);
        }
        // A flat thing (a serving tray, a plate) lies flat: never on its edge, its thin side across and its long side level
        // (Joost's test: the serving tray on its side in a tool socket).
        if (own is { } o)
        {
            var dims = new[] { o.x, o.y, o.z }.OrderBy(x => x).ToArray();
            if (dims[0] <= 0.5f * dims[1] && d.y > dims[0] * 1.05f && d.y < dims[2] * 0.95f) return float.PositiveInfinity;
        }
        // The boxes are the demo item's own size: a little room for measuring differences, but never up into the next shelf or
        // cubby above (a crested helmet reached into the cubby above, the coordinator's Blender check).
        const float slack = 1.25f;
        // A kit place takes what its example takes, measured in the place's own frame: the item's own size, as turned against the
        // place, by the example's (Joost, 27 Oct, the Bow Rack r5 stopping at 3 of 8: its places lean by design, and a leaned
        // item's turned box against the leaned example's bounds refused even the bow each place was made for).
        if (p.ByExample && own is { } mine && turn is { } q && ExampleSize(p) is { } e)
        {
            var m = Turned(Quaternion.Inverse(p.Rot) * q, mine);
            return Mathf.Max(m.x - (e.x * slack + 0.02f), m.y - (e.y * slack + 0.02f), m.z - (e.z * slack + 0.02f), rest + d.y - (p.Ceiling - 0.005f));
        }
        return Mathf.Max(d.x - (p.Box.x * slack + 0.02f), d.y - (p.Box.y * slack + 0.02f), d.z - (p.Box.z * slack + 0.02f), rest + d.y - (p.Ceiling - 0.005f));
    }

    // turns: per item, the turn it is drawn with at its place (one of Turns). scales: per item its drawn size (1: true size).
    public int[] Allocate(List<ItemDrop.ItemData> items, Func<ItemDrop.ItemData, Quaternion, Vector3?> size, out Quaternion[] turns, out float[] scales, List<string> notes = null, Func<ItemDrop.ItemData, int> classOf = null) =>
        Solve(items, size, classOf, keep: false).Final(out turns, out scales, notes);

    // Allocate's placement of these items, kept to be asked "and with one more?" (Placement.With). keep: the state before each of its
    // steps is kept, for With. scan: crossings by scanning every place and the tier by walking the recipes, as 0.8.0 did: the dev
    // self-check's from-scratch answer.
    public Placement Solve(List<ItemDrop.ItemData> items, Func<ItemDrop.ItemData, Quaternion, Vector3?> size, Func<ItemDrop.ItemData, int> classOf = null, bool keep = true, bool scan = false)
    {
        var p = new Placement(this, items, size, classOf, scan);
        p.Run(keep);
        return p;
    }

    // A typed store's contents as its window and its display ask them: solved once per contents, whoever asks first (FEEDBACK-0.8
    // item 3: one drop solved the same contents about six times, the drop's three checks each, the hints, the rebuild). gear: what
    // the chest holds with a model, in the chest's order (the classes come from the cells the items lie in).
    Placement basis;
    Inventory basisInv;
    int basisVersion = -1, basisWidth;
    (ItemDrop.ItemData it, int x, int y, int quality, GameObject prefab)[] basisKey;
    internal Placement Basis(Inventory inv, List<ItemDrop.ItemData> gear)
    {
        var key = gear.Select(it => (it, it.m_gridPos.x, it.m_gridPos.y, it.m_quality, it.m_dropPrefab)).ToArray();
        if (basis != null && basisInv == inv && basisVersion == Version && basisWidth == inv.GetWidth() && basisKey.SequenceEqual(key)) return basis;
        basis = Solve(gear, EquipFit.TrueSize, g => TypedSlots.ClassOf(this, inv, g));
        basisInv = inv;
        basisVersion = Version;
        basisWidth = inv.GetWidth();
        basisKey = key;
        return basis;
    }

    // Where each item goes (Allocate), as a value: the places' holders after each step of the matching are kept, so "these items and
    // one more" (With) takes only the steps from the newcomer's own turn on. Those are the very steps Allocate takes for all of them,
    // so the answer is Allocate's, crossings, the featured place and the drawn-smaller pass included (FEEDBACK-0.8 item 3, Joost:
    // "geen pleisteroplossing": the Spine's hints solved the whole placement about 250 times per change, a lag spike on every add;
    // spine-lag-investigation.md). A step sees the other items only through who holds what: Candidates, Scale and anyTrue are per
    // item and place. Keep it that way, or With stops being exact (the dev self-check, 7 - Performance, logs any difference).
    public sealed class Placement
    {
        // Per item what doesn't depend on the other items: shared by every placement asked from this one.
        sealed class Known
        {
            public List<int> Candidates;
            public bool? AnyTrue;
            public readonly Dictionary<int, Quaternion?> Fit = new();
            public readonly Dictionary<int, float> Drawn = new(), Height = new();
        }
        sealed class State { public int[] Owner, Result; public List<int>[] Members; public float[] Filled; }

        readonly StoreModel m;
        readonly Func<ItemDrop.ItemData, Quaternion, Vector3?> size;
        readonly bool scan;
        readonly List<ItemDrop.ItemData> items;
        readonly int[] cls, tier, order, pid;   // per item: its block's class (-1: any that takes it), tier, chest order, pose table prefab id
        readonly string[] name;                 // per item its prefab's name (null: none)
        readonly Known[] known;
        readonly List<List<int>> piles;
        readonly float[] rooms;
        readonly Dictionary<int, List<int>> placesOf;   // per unit its places: a pose table's crossings name units
        int[] owner, result;
        List<int>[] members;
        float[] filled;
        List<int> steps;      // the matching's steps in order: highest tier first, then chest order
        List<State> before;   // the state before each step; null: not kept
        int shown = -1;
        List<(int i, int k, float s, Quaternion q)> smaller;   // the drawn-smaller pass: who went where, at what size and turn
        Dictionary<long, Quaternion?> tried;                    // every place that pass tried, with its turn there (null: not there)

        internal Placement(StoreModel m, List<ItemDrop.ItemData> items, Func<ItemDrop.ItemData, Quaternion, Vector3?> size, Func<ItemDrop.ItemData, int> classOf, bool scan)
        {
            this.m = m;
            this.size = size;
            this.scan = scan;
            this.items = new List<ItemDrop.ItemData>(items);
            int n = items.Count;
            cls = new int[n]; tier = new int[n]; order = new int[n]; pid = new int[n]; name = new string[n]; known = new Known[n];
            for (int i = 0; i < n; i++) Describe(i, classOf?.Invoke(items[i]) ?? -1);
            piles = m.Stacks ?? new List<List<int>>();
            rooms = Enumerable.Range(0, piles.Count).Select(p => m.PileRoom(p).room + 0.001f).ToArray();   // n items, n - 1 gaps
            placesOf = new Dictionary<int, List<int>>();
            for (int k = 0; k < m.Equip.Count; k++)
            {
                if (!placesOf.TryGetValue(m.Equip[k].Unit, out var at)) placesOf[m.Equip[k].Unit] = at = new List<int>();
                at.Add(k);
            }
            owner = Enumerable.Repeat(-1, m.Equip.Count).ToArray();
            result = Enumerable.Repeat(-1, n).ToArray();
            members = piles.Select(_ => new List<int>()).ToArray();
            filled = new float[piles.Count];
        }
        // These items and one more: its state is set by With.
        Placement(Placement from, ItemDrop.ItemData item, int klass)
        {
            m = from.m; size = from.size; scan = from.scan; piles = from.piles; rooms = from.rooms; placesOf = from.placesOf;
            items = new List<ItemDrop.ItemData>(from.items) { item };
            int n = items.Count;
            cls = Grow(from.cls, n); tier = Grow(from.tier, n); order = Grow(from.order, n); pid = Grow(from.pid, n);
            name = Grow(from.name, n); known = Grow(from.known, n);
            Describe(n - 1, klass);
            owner = Enumerable.Repeat(-1, m.Equip.Count).ToArray();
            result = Enumerable.Repeat(-1, n).ToArray();
            members = piles.Select(_ => new List<int>()).ToArray();
            filled = new float[piles.Count];
        }
        static T[] Grow<T>(T[] a, int n) { var b = new T[n]; Array.Copy(a, b, a.Length); return b; }
        void Describe(int i, int klass)
        {
            var it = items[i];
            cls[i] = klass;
            name[i] = it.m_dropPrefab ? it.m_dropPrefab.name : null;
            pid[i] = m.Table != null && name[i] != null ? m.Table.Id(name[i]) : -1;
            tier[i] = scan ? EquipRules.TierScan(it) : EquipRules.Tier(it);
            order[i] = it.m_gridPos.y * 100 + it.m_gridPos.x;
            known[i] = new Known();
        }

        // An item takes a place at true size where it fits there. Where it doesn't, it is drawn smaller, as much as that place needs
        // (Joost, 27 Oct, the 0.87 m Hood of the Vanguard: "why can't we just scale it down?"), never under MinScale (a toy): in a
        // store where any size goes in any place (AnySize), and for an item no place of its type takes at true size.
        Quaternion? TrueFit(int k, int i)
        {
            // The answer is the kind's at that place, whatever the call (every add asks a few times): kept per model.
            var kind = name[i] != null ? (k, name[i]) : default;
            if (m.Table?.Rules(m.Equip[k].Unit, kind.Item2) == true) return m.Table.Get(m.Equip[k].Unit, kind.Item2) is { Fit: true } row ? row.Rot : null;   // the table's word, nothing else
            if (kind.Item2 != null && m.fitCache.TryGetValue(kind, out var q)) return q;
            q = FitTurn(m.Equip[k], items[i], size);
            if (kind.Item2 != null) m.fitCache[kind] = q;
            return q;
        }
        float Scale(int k, int i)   // how big it is drawn at that place; 0: not there
        {
            var drawn = known[i].Drawn;
            if (drawn.TryGetValue(k, out var s)) return s;
            if (TrueFit(k, i) != null) return drawn[k] = 1f;
            if (m.Table?.Rules(m.Equip[k].Unit, name[i]) == true) return drawn[k] = 0f;   // a pose table draws nothing smaller
            // Only the places it can be given here: the featured one is handed out first, on its own (f72: the Blackmetal Shield fitted
            // only the taken featured bay, so it was allowed no smaller place either).
            known[i].AnyTrue ??= Enumerable.Range(0, m.Equip.Count).Any(j => !m.Equip[j].Featured && Allowed(j, i) && TrueFit(j, i) != null);
            if (!m.AnySize && known[i].AnyTrue == true) return drawn[k] = 0f;
            string most = (name[i] ?? items[i].m_shared.m_name) + "|" + k;
            if (!m.scaleFit.TryGetValue(most, out s)) m.scaleFit[most] = s = MaxScale(m.Equip[k], items[i], size, m.Floor);
            return drawn[k] = s >= m.Floor ? s : 0f;
        }
        Vector3? Size(int k, int i, Quaternion q) => size(items[i], q) is { } d ? d * Scale(k, i) : null;
        Quaternion? Fit(int k, int i)
        {
            var fit = known[i].Fit;
            if (fit.TryGetValue(k, out var q)) return q;
            float s = Scale(k, i);
            return fit[k] = s <= 0f ? null : s >= 1f ? TrueFit(k, i) : FitTurn(m.Equip[k], items[i], (_, t) => Size(k, i, t));
        }
        float Height(int k, int i)   // in a pile: its height lying as it fits the pile's floor place, plus the 1 mm gap
        {
            var height = known[i].Height;
            if (!height.TryGetValue(k, out var h)) height[k] = h = (Fit(k, i) is { } q && Size(k, i, q) is { } d ? d.y : 99f) + 0.001f;
            return h;
        }
        bool Allowed(int k, int i)
        {
            var it = items[i];
            int c = cls[i];
            if (c >= 0 && m.Classes != null && c < m.Classes.Count && m.Classes[c].Takes(it)) return m.Equip[k].Class == c;
            return m.Classes != null && m.Equip[k].Class >= 0 ? m.Classes[m.Equip[k].Class].Takes(it) : m.Equip[k].Types.Contains(it.m_shared.m_itemType.ToString());
        }
        // A pile is one candidate: its floor place stands for it.
        List<int> Candidates(int i) => known[i].Candidates ??= Enumerable.Range(0, m.Equip.Count)
            .Where(k => !m.Equip[k].Featured && (m.Equip[k].Pile < 0 || piles[m.Equip[k].Pile][0] == k) && Allowed(k, i) && Fit(k, i) != null)
            .OrderBy(k => Scale(k, i) < 1f ? 1 : 0).ThenBy(k => m.Equip[k].Example == name[i] ? 0 : 1).ThenByDescending(k => Scale(k, i))
            .ThenBy(k => m.Equip[k].Box.x * m.Equip[k].Box.y * m.Equip[k].Box.z).ThenBy(k => k).ToList();
        bool Free(int k, int i) => m.Equip[k].Pile is int n and >= 0 ? members[n].Count < piles[n].Count && filled[n] + Height(k, i) <= rooms[n] : owner[k] < 0 && !Clash(k, i, -1);
        // A pose table's crossing pairs: i at k would cross what another place holds now (but item except, about to move away). Only
        // the poses that pose crosses (PoseTable.CrossOf); scan: every place, by name, as 0.8.0 did.
        bool Clash(int k, int i, int except)
        {
            var table = m.Table;
            if (table == null || !table.AnyCrossing || name[i] == null) return false;
            if (scan)
            {
                for (int o = 0; o < m.Equip.Count; o++)
                    if (o != k && owner[o] is int j and >= 0 && j != i && j != except && name[j] != null
                        && table.Crosses(m.Equip[k].Unit, name[i], m.Equip[o].Unit, name[j])) return true;
                return false;
            }
            foreach (var (unit, id) in table.CrossOf(m.Equip[k].Unit, pid[i]))
                if (placesOf.TryGetValue(unit, out var at))
                    foreach (int o in at)
                        if (o != k && owner[o] is int j and >= 0 && j != i && j != except && pid[j] == id) return true;
            return false;
        }
        void Put(int k, int i)
        {
            if (m.Equip[k].Pile is int n and >= 0) { members[n].Add(i); filled[n] += Height(k, i); }
            else owner[k] = i;
            result[i] = k;
        }
        void Take(int k, int i)
        {
            if (m.Equip[k].Pile is int n and >= 0) { members[n].Remove(i); filled[n] -= Height(k, i); }
            else if (owner[k] == i) owner[k] = -1;
            result[i] = -1;
        }
        // Kuhn's augmenting path, with piles as places of several layers and a height budget: a free fitting place first, else one
        // whose holder can move on to another place.
        bool Augment(int i, HashSet<int> seen)
        {
            foreach (int k in Candidates(i)) if (!seen.Contains(k) && Free(k, i)) { Put(k, i); return true; }
            foreach (int k in Candidates(i))
            {
                if (!seen.Add(k)) continue;
                if (m.Equip[k].Pile is int n and >= 0)
                {
                    foreach (int j in members[n].ToList())
                    {
                        if (filled[n] - Height(k, j) + Height(k, i) > rooms[n]) continue;
                        Take(k, j);
                        if (Augment(j, seen)) { Put(k, i); return true; }
                        Put(k, j);
                    }
                }
                else if (owner[k] is int j and >= 0 && !Clash(k, i, j))
                {
                    owner[k] = -1;
                    if (Augment(j, seen)) { Put(k, i); return true; }
                    Put(k, j);
                }
            }
            return false;
        }
        // The featured place first, then every other item one step at a time (keep: the state before each step, for With).
        internal void Run(bool keep)
        {
            for (int f = 0; f < m.Equip.Count; f++)
            {
                if (!m.Equip[f].Featured) continue;
                // What fits it at true size first (Joost, 27 Oct, f72: Arsenal B gave its featured bay to a tower shield drawn at 0.76 and the
                // Blackmetal Shield it was made for stayed in the chest).
                int best = Enumerable.Range(0, items.Count).Where(i => result[i] < 0 && Allowed(f, i) && Fit(f, i) != null)
                    .OrderBy(i => Scale(f, i) >= 1f ? 0 : 1).ThenByDescending(i => EquipRules.Block(items[i])).ThenByDescending(i => items[i].m_quality).ThenBy(i => order[i]).DefaultIfEmpty(-1).First();
                if (best >= 0) { owner[f] = best; result[best] = f; }
            }
            // Highest tier first, then chest order: when places run out, the lower tiers stay in the chest.
            steps = Enumerable.Range(0, items.Count).Where(i => result[i] < 0).OrderByDescending(i => tier[i]).ThenBy(i => order[i]).ToList();
            before = keep ? new List<State>(steps.Count) : null;
            foreach (int i in steps)
            {
                before?.Add(Snap());
                Augment(i, new HashSet<int>());
            }
        }
        // a goes before b for the featured place (Run's order; on a tie the earlier item).
        bool Ahead(int f, int a, int b)
        {
            int c = (Scale(f, a) >= 1f ? 0 : 1).CompareTo(Scale(f, b) >= 1f ? 0 : 1);
            if (c == 0) c = EquipRules.Block(items[b]).CompareTo(EquipRules.Block(items[a]));
            if (c == 0) c = items[b].m_quality.CompareTo(items[a].m_quality);
            if (c == 0) c = order[a].CompareTo(order[b]);
            return c < 0 || c == 0 && a < b;
        }
        // j's step comes after i's (Run's order).
        bool After(int j, int i) => tier[j] != tier[i] ? tier[j] < tier[i] : order[j] != order[i] ? order[j] > order[i] : j > i;

        // These items and one more (klass: its block's class), placed as Allocate places them all: the steps before the newcomer's turn
        // went the same, so from the state before its turn on, its step, then the later ones. When its own step finds no place and
        // moves nothing, every later step goes as it went here: one search. The featured place changing hands (or a round with more
        // than one) changes the start of every step: solved anew. keep: the result can be asked again (the hints' count).
        public Placement With(ItemDrop.ItemData item, int klass, bool keep = false)
        {
            var p = new Placement(this, item, klass);
            int h = items.Count, featured = -1, featuredPlaces = 0;
            for (int f = 0; f < m.Equip.Count; f++) if (m.Equip[f].Featured) { featured = f; featuredPlaces++; }
            if (before == null || featuredPlaces > 1
                || featured >= 0 && p.Allowed(featured, h) && p.Fit(featured, h) != null && (owner[featured] < 0 || p.Ahead(featured, h, owner[featured])))
            {
                p.Run(keep);
                return p;
            }
            int slot = 0;
            while (slot < steps.Count && !p.After(steps[slot], h)) slot++;
            var at = slot < steps.Count ? before[slot] : Now();
            p.Restore(at);
            p.steps = new List<int>(steps.Count + 1);
            p.steps.AddRange(steps.Take(slot));
            p.steps.Add(h);
            p.steps.AddRange(steps.Skip(slot));
            p.before = keep ? new List<State>(before.Take(slot)) : null;
            for (int t = slot; t < p.steps.Count; t++)
            {
                p.before?.Add(p.Snap());
                if (!p.Augment(p.steps[t], new HashSet<int>()) && t == slot && p.Same(at))
                {
                    p.Restore(Now());
                    p.before?.AddRange(before.Skip(slot));
                    break;
                }
            }
            return p;
        }
        State Now() => new State { Owner = owner, Result = result, Members = members, Filled = filled };
        State Snap() => new State
        {
            Owner = (int[])owner.Clone(), Result = (int[])result.Clone(),
            Members = piles.Count > 0 ? members.Select(l => new List<int>(l)).ToArray() : null, Filled = piles.Count > 0 ? (float[])filled.Clone() : null,
        };
        // A state of fewer items: the later ones not placed yet.
        void Restore(State s)
        {
            owner = (int[])s.Owner.Clone();
            result = Enumerable.Repeat(-1, items.Count).ToArray();
            Array.Copy(s.Result, result, s.Result.Length);
            members = s.Members != null ? s.Members.Select(l => new List<int>(l)).ToArray() : piles.Select(_ => new List<int>()).ToArray();
            filled = s.Filled != null ? (float[])s.Filled.Clone() : new float[piles.Count];
        }
        bool Same(State s)
        {
            if (!owner.SequenceEqual(s.Owner)) return false;
            for (int i = 0; i < result.Length; i++) if (result[i] != (i < s.Result.Length ? s.Result[i] : -1)) return false;
            for (int n = 0; n < piles.Count; n++) if (!members[n].SequenceEqual(s.Members[n]) || filled[n] != s.Filled[n]) return false;
            return true;
        }

        // How many items show: the matching's, and what goes smaller into a place still empty (Smaller).
        public int Shown { get { if (shown < 0) Smaller(); return shown; } }
        // Still in the chest while a place of its type stands empty: drawn smaller there, as large as that place allows (never under
        // the floor), though it fits a taken place at true size (Joost via M, 27 Oct, Armory B: "an empty headpiece spot top right
        // shelf"; HelmetCarapace is 1 mm too deep for the small helmet places, the crested ones it fits held the Crown and the hood).
        // On a copy of the holders: the matching stays as it is, to be asked again.
        void Smaller()
        {
            var own = (int[])owner.Clone();
            smaller = new List<(int, int, float, Quaternion)>();
            tried = new Dictionary<long, Quaternion?>();
            int count = result.Count(r => r >= 0);
            foreach (int i in Enumerable.Range(0, items.Count).Where(i => result[i] < 0).OrderByDescending(i => tier[i]).ThenBy(i => order[i]).ToList())
            {
                string kind = name[i] ?? items[i].m_shared.m_name;
                float Most(int k) { string key = kind + "|" + k; if (!m.scaleFit.TryGetValue(key, out var s)) m.scaleFit[key] = s = MaxScale(m.Equip[k], items[i], size, m.Floor); return s; }
                foreach (int k in Enumerable.Range(0, m.Equip.Count).Where(k => !m.Equip[k].Featured && m.Equip[k].Pile < 0 && own[k] < 0 && m.Table?.Covers(m.Equip[k].Unit) != true && Allowed(k, i) && Most(k) >= m.Floor)
                    .OrderByDescending(Most).ThenBy(k => k).ToList())
                {
                    float s = Most(k);
                    var q = s >= 1f ? TrueFit(k, i) : FitTurn(m.Equip[k], items[i], (_, t) => size(items[i], t) is { } d ? d * s : null);
                    tried[(long)k * 100000 + i] = q;
                    if (q == null) continue;
                    own[k] = i;
                    smaller.Add((i, k, s, q.Value));
                    count++;
                    break;
                }
            }
            shown = count;
        }

        // The placement as drawn (Allocate's answer): the featured row's order, the smaller ones, each item's turn and size, the piles'
        // layers. notes: per item, where it went or why it stays unseen.
        public int[] Final(out Quaternion[] turns, out float[] scales, List<string> notes = null)
        {
            if (shown < 0) Smaller();
            var owner = (int[])this.owner.Clone();
            var result = (int[])this.result.Clone();
            var turn = new Quaternion[items.Count];
            turns = turn;
            var scale = Enumerable.Repeat(1f, items.Count).ToArray();
            scales = scale;
            var Equip = m.Equip;
            var Table = m.Table;
            // A pose table's row with a featured place (the Arsenal's six shield bays): the big ones in the poses farthest back. Joost, 27
            // Oct, in game: "why are the big shields in the front of the Arsenal? They should all be near the back"; the bays' poses stand at
            // different depths (a tower at z 0.43 in 26, 28 and 30, at -0.02 in the others; the aisle is +z, where Sol's camera stands).
            // Of every order of the held items over the bays nearest the featured place in which each has a row and no two cross (nor with
            // anything else held): the least size-weighted depth toward the aisle, then the fewest larger-nearer-the-featured-end pairs
            // (the end view: a tower at bay 31 hid the Bronze Buckler). Joost's six: towers at 31 and 27, both at the back. The matching's
            // own when there is none (or more than 7 to order). With Sol's per-pair visibility (pass 2, 27 Oct) instead: the order whose
            // least seen item is seen most (each neighbouring pair's measured fractions), then the most seen in all; Joost's six: 93.8%.
            // It reorders held bays only, all pose table places, which the smaller pass never gives: the questions skip it.
            if (Table != null && Equip.FindIndex(p => p.Featured) is int fk and >= 0 && Table.Covers(Equip[fk].Unit))
            {
                var bays = Enumerable.Range(0, Equip.Count).Where(k => Equip[k].Pile < 0 && Equip[k].Class == Equip[fk].Class && Table.Covers(Equip[k].Unit))
                    .OrderBy(k => (Equip[k].Pos - Equip[fk].Pos).sqrMagnitude).ThenBy(k => k).ToList();
                float Big(int i) => size(items[i], Quaternion.identity) is { } d ? Mathf.Max(d.x, Mathf.Max(d.y, d.z)) : 0f;
                var held = bays.Where(k => owner[k] >= 0).Select(k => owner[k]).OrderBy(Big).ThenBy(i => order[i]).ToList();
                if (held.Count > 1 && held.Count <= 7)
                {
                    string Name(int i) => name[i];
                    var others = Enumerable.Range(0, Equip.Count).Where(o => !bays.Contains(o) && owner[o] >= 0 && items[owner[o]].m_dropPrefab).ToList();
                    var size1 = held.Select(Big).ToArray();
                    var pick = new int[held.Count];   // pick[n]: which of held stands in bays[n]
                    var used = new bool[held.Count];
                    int[] best = null;
                    int bestInv = int.MaxValue;
                    float bestFront = float.MaxValue;
                    float back = float.MaxValue;   // the farthest-back pivot of any candidate row: depth is counted from there
                    foreach (int k in bays.Take(held.Count))
                        foreach (int i in held)
                            if (Table.Get(Equip[k].Unit, Name(i)) is { Fit: true } r0) back = Mathf.Min(back, r0.Pivot.z);
                    bool byVis = Table.AnyVisibility;
                    float bestMin = -1f, bestSum = -1f;
                    void Try(int n, int inv, float front, float least, float total)
                    {
                        if (byVis ? least < bestMin - 1e-5f : front > bestFront + 1e-4f || front > bestFront - 1e-4f && inv >= bestInv) return;
                        if (n == held.Count)
                        {
                            if (byVis && (least < bestMin + 1e-5f && total <= bestSum)) return;
                            bestFront = front; bestInv = inv; bestMin = least; bestSum = total; best = (int[])pick.Clone();
                            return;
                        }
                        for (int h = 0; h < held.Count; h++)
                        {
                            if (used[h] || Table.Get(Equip[bays[n]].Unit, Name(held[h])) is not { Fit: true } row) continue;
                            bool clash = false;
                            for (int b = 0; b < n && !clash; b++) clash = Table.Crosses(Equip[bays[n]].Unit, Name(held[h]), Equip[bays[b]].Unit, Name(held[pick[b]]));
                            foreach (int o in others) if (!clash) clash = Table.Crosses(Equip[bays[n]].Unit, Name(held[h]), Equip[o].Unit, Name(owner[o]));
                            if (clash) continue;
                            int more = 0;
                            for (int b = 0; b < n; b++) if (size1[pick[b]] > size1[h]) more++;   // a larger one nearer the featured end
                            float least1 = least, total1 = total;
                            if (byVis && n > 0 && Table.Seen(Equip[bays[n - 1]].Unit, Name(held[pick[n - 1]]), Equip[bays[n]].Unit, Name(held[h])) is { } v)
                            {
                                least1 = Mathf.Min(least, Mathf.Min(v.near, v.far));
                                total1 = total + v.near + v.far;
                            }
                            used[h] = true;
                            pick[n] = h;
                            Try(n + 1, inv + more, front + size1[h] * (row.Pivot.z - back), least1, total1);
                            used[h] = false;
                        }
                    }
                    Try(0, 0, 0f, 1f, 0f);
                    if (best != null)
                    {
                        foreach (int k in bays) owner[k] = -1;
                        for (int n = 0; n < held.Count; n++) { owner[bays[n]] = held[best[n]]; result[held[best[n]]] = bays[n]; }
                    }
                }
            }
            foreach (var (i, k, _, _) in smaller) { owner[k] = i; result[i] = k; }
            // Its size and turn at the place it won (a pile: as on its floor place).
            var drawnSmaller = smaller.ToDictionary(x => x.i);
            for (int i = 0; i < items.Count; i++)
            {
                if (result[i] < 0) continue;
                if (drawnSmaller.TryGetValue(i, out var sm)) { scale[i] = sm.s; turn[i] = sm.q; }
                else { scale[i] = Scale(result[i], i); turn[i] = Fit(result[i], i) ?? Equip[result[i]].Rot; }
                if (scale[i] < 1f && name[i] != null && Scaled.Add(m.Key + "|" + name[i] + "|" + Equip[result[i]].Name))
                    Plugin.Log.LogInfo($"{m.Title}: {name[i]} is too big for its {Equip[result[i]].Name} place ({m.ClassName(result[i])}); drawn at {scale[i]:F2} of its size.");
            }
            // A pile's layers bottom up: the broadest piece at the bottom, then the thicker (a pile a person would make).
            for (int n = 0; n < piles.Count; n++)
            {
                int floor = piles[n][0];
                var layers = members[n].OrderByDescending(i => Size(floor, i, turn[i]) is { } d ? d.x * d.z : 0f).ThenByDescending(i => Height(floor, i)).ToList();
                for (int l = 0; l < layers.Count; l++) result[layers[l]] = piles[n][l];
            }
            if (notes != null)
                for (int i = 0; i < items.Count; i++)
                {
                    var it = items[i];
                    string label = name[i] ?? it.m_shared.m_name;
                    if (result[i] >= 0)
                    {
                        var at = Equip[result[i]];
                        notes.Add($"{label} -> place {at.Unit}{(at.Featured ? " (featured)" : "")}{(at.Pile >= 0 ? $" (pile {at.Pile}, layer {at.Layer})" : "")}{(turn[i] == at.Rot ? "" : ", turned")}"
                            + $"{(scale[i] < 1f ? $", scaled {scale[i]:F2}" : "")}, tier {EquipRules.TierText(it)}, size {size(it, turn[i]) * scale[i]:F2} in box {at.Clear ?? at.Box:F2}"
                            + (at.ExampleSize is { } ex && size(it, Quaternion.identity) is { } own ? $", own size {Turned(Quaternion.Inverse(at.Rot) * turn[i], own * scale[i]):F2} by {at.Example}'s {ex:F2}" : ""));
                        continue;
                    }
                    var mine = Enumerable.Range(0, Equip.Count).Where(k => Allowed(k, i)).ToList();
                    if (mine.Count == 0) { notes.Add($"{label} ({it.m_shared.m_itemType}) unseen: no place of its type in its block"); continue; }
                    // A place the smaller pass tried counts as it found it.
                    if (!mine.Any(k => (tried.TryGetValue((long)k * 100000 + i, out var q) ? q : Fit(k, i)) != null)) { notes.Add($"{label} unseen: too big, even at {m.Floor:F2} of its size"); continue; }
                    notes.Add($"{label} unseen: every place it fits is taken by higher tiers or full piles{(Table?.AnyCrossing == true ? ", or its pose there crosses a neighbour's item" : "")} (tier {EquipRules.TierText(it)})");
                }
            return result;
        }
    }

    // Below this an item drawn smaller would look like a toy: it is refused instead (Joost, via M, 27 Oct).
    public const float MinScale = 0.5f;
    static readonly HashSet<string> Scaled = new(StringComparer.Ordinal);   // logged once per store and kind
    internal static readonly HashSet<string> TableCentres = new(StringComparer.Ordinal);   // a pose table row off the item's true centre: said once per store and kind
    readonly Dictionary<string, float> scaleFit = new(StringComparer.Ordinal);   // per kind and place: its largest fitting scale (Classify clears it)
    // The Shield Trough takes any shield in any of its ten places, drawn smaller where its place is too small (Joost, 27 Oct, in game:
    // "Can we just enable that ten shields can go in here, no matter the size").
    bool AnySize => Slug == "arsenalkit_shield";
    // "No matter the size" (Joost, via M, 27 Oct): no toy floor there, a tower shield goes small into a buckler bay once the big bays
    // are taken (best fit still gives the big bays to the big shields first). Every other typed store keeps MinScale.
    internal float Floor => AnySize ? 0.05f : MinScale;
    readonly Dictionary<(int place, string name), Quaternion?> fitCache = new();   // per place and kind: its turn at true size (Classify clears it)
    string ClassName(int k) => Classes != null && Equip[k].Class >= 0 ? Classes[Equip[k].Class].Name : Equip[k].Name;

    // The largest uniform scale (up to 1) at which an item fits a place in any of its turns; 0 when not even MinScale fits.
    public static float MaxScale(EquipPlace p, ItemDrop.ItemData it, Func<ItemDrop.ItemData, Quaternion, Vector3?> size, float floor = MinScale)
    {
        bool Fits(float s) => FitTurn(p, it, (x, q) => size(x, q) is { } d ? d * s : null) != null;
        if (!Fits(floor)) return 0f;
        float lo = floor, hi = 1f;
        for (int n = 0; n < 12; n++) { float mid = (lo + hi) * 0.5f; if (Fits(mid)) lo = mid; else hi = mid; }
        return lo;
    }
    void DropGlass()
    {
        foreach (var g in FrameGlass.Concat(FamilyGlass.Values.SelectMany(l => l)))
        {
            if (g.Mat) UnityEngine.Object.Destroy(g.Mat);
            if (g.Mesh) UnityEngine.Object.Destroy(g.Mesh);
        }
        FrameGlass.Clear();
        FamilyGlass.Clear();
    }

    void Fail(string[] files, string why)
    {
        var t = files.Max(File.GetLastWriteTimeUtc);
        if (failed != null && files.SequenceEqual(failed) && t == failedStamp) return;   // said once per file version
        failed = files;
        failedStamp = t;
        Plugin.Log.LogWarning($"{Title}: {why}; keeping the previous model.");
    }

    public static void CheckAllForChanges()
    {
        foreach (var m in all.Values.ToList()) m.CheckForChanges();
    }

    void CheckForChanges()
    {
        var files = Files();
        if (files == null) return;
        var newest = files.Max(File.GetLastWriteTimeUtc);
        if (loaded != null && files.SequenceEqual(loaded) && newest <= stamp) return;
        if (failed != null && files.SequenceEqual(failed) && newest == failedStamp) return;
        var old = Frame;
        if (!Load(files)) return;
        int updated = 0;
        foreach (var sc in UnityEngine.Object.FindObjectsByType<StoreContents>(FindObjectsInactive.Include, FindObjectsSortMode.None))
            if (sc.name == VisName) { Refit(sc.transform); updated++; }
        foreach (var k in Kinds.Stores)
            if (k.Slug == Slug && k.Piece == Piece && PrefabManager.Instance.GetPrefab(k.Prefab) is { } prefab && prefab.transform.Find(VisName) is { } vis)
                Refit(vis);
        if (old && old != Frame) UnityEngine.Object.Destroy(old);
        Plugin.Log.LogInfo($"{Title}: model reloaded, {updated} store(s) in the world updated.");
    }

    // The piece's collider box: the frame, and on a packed shelf the free space above the top plank too (so you can aim at
    // what stands on it).
    Bounds Box
    {
        get
        {
            var b = Frame.bounds;
            foreach (var p in Planks) b.Encapsulate(new Vector3(b.center.x, p.Y + p.Clear, p.Z));
            return b;
        }
    }

    // The Arsenal kit's snap points, anew from the loaded round (a live model change: the shield trough's r3 and r4, 27 Oct).
    // Not "storehouse_snap_": those are a stackable store's corners, which the placement check wants resting on something.
    void AddKitSnaps(GameObject go)
    {
        foreach (Transform child in go.transform.Cast<Transform>().ToList())
            if (child.name.StartsWith("storehouse_kitsnap_", StringComparison.Ordinal)) { child.SetParent(null); UnityEngine.Object.Destroy(child.gameObject); }
        for (int n = 0; n < KitSnaps.Count; n++)
        {
            var snap = new GameObject($"storehouse_kitsnap_{n}") { tag = "snappoint", layer = go.layer };
            snap.SetActive(false);
            snap.transform.SetParent(go.transform, false);
            snap.transform.localPosition = KitSnaps[n];
        }
    }

    // Every store lines up with its neighbours (Joost, 28 Oct: "we hebben nog niet alle items snapping points"): a piece without snap
    // points of its own gets one on each floor corner of its box. Not "storehouse_snap_" (those make a store stackable, and the
    // placement check then wants them resting on something), and no top corners: what doesn't stack gets nothing to stand on it.
    void AddEdgeSnaps(GameObject go)
    {
        foreach (Transform child in go.transform.Cast<Transform>().ToList())
            if (child.name.StartsWith("storehouse_edgesnap_", StringComparison.Ordinal)) { child.SetParent(null); UnityEngine.Object.Destroy(child.gameObject); }
        if (go.transform.Cast<Transform>().Any(t => t.CompareTag("snappoint"))) return;
        int n = 0;
        foreach (var x in new[] { Box.min.x, Box.max.x })
            foreach (var z in new[] { Box.min.z, Box.max.z })
            {
                var snap = new GameObject($"storehouse_edgesnap_{n++}") { tag = "snappoint", layer = go.layer };
                snap.SetActive(false);
                snap.transform.SetParent(go.transform, false);
                snap.transform.localPosition = new Vector3(x, Box.min.y, z);
            }
    }

    // New frame on one store; a piece's colliders follow it, a skinned chest keeps its own.
    void Refit(Transform vis)
    {
        if (vis.Find("frame")?.GetComponent<MeshFilter>() is { } frame) frame.sharedMesh = Frame;
        // The glass and the figures' hands anew: a round may bring strips, change them or have none.
        foreach (Transform child in vis.Cast<Transform>().ToList())
            if (child.name.StartsWith("glass", StringComparison.Ordinal) || child.name.StartsWith("arms", StringComparison.Ordinal) || child.name == "straw") { child.SetParent(null); UnityEngine.Object.Destroy(child.gameObject); }
        AddGlass(vis);
        AddArms(vis);
        AddStraw(vis);
        var root = vis.parent;
        if (root && root.GetComponent<Piece>() && !root.GetComponent<SkinState>())
        {
            Geometry.FitColliders(root.gameObject, Box, root.name);
            Geometry.SolidFrame(root.gameObject, vis, root.name);
            if (vis.Find("straw") is { } straw && straw.GetComponent<MeshCollider>() is { } strawSolid) UnityEngine.Object.DestroyImmediate(strawSolid);
            AddKitSnaps(root.gameObject);
            Kitbash.Resnap(root.gameObject, Box);
        }
        if (vis.GetComponent<LODGroup>() is { } lod)
        {
            lod.SetLODs(new[] { new LOD(0.03f, vis.GetComponentsInChildren<Renderer>(true)) });
            lod.RecalculateBounds();
        }
    }

    // The piece: the cloned wood chest with its look hidden, our frame, and StoreContents for what is inside.
    // quiet: a live reload dressing the pieces in the world (one log line for all of them instead).
    public void BuildPiece(GameObject go, bool quiet = false)
    {
        if (!Ready)
        {
            if (!quiet) { Plugin.Log.LogError($"{Title}: no model; the piece stays a plain wood chest."); Plugin.Failures.Add($"{Title} model"); }
            return;
        }
        var vis = Kitbash.Strip(go, VisName);
        Part(vis, "frame", Frame);
        AddGlass(vis);
        AddArms(vis);
        AddStraw(vis);
        if (!Plugin.Headless) vis.gameObject.AddComponent<StoreContents>();   // a server draws nothing
        // What has a flat top stacks: the ground stores, and the Mead Rack and Larder Hutch (Joost, 22 Oct). The Meat Rack (hook
        // beams on top), the Root Bin (open crates) and the Ore Bin (an open stone bin, far too heavy to stack) don't look like they
        // would carry anything, so they don't; nor the wall shelves.
        bool flatTop = Slug is "bunker" or "coopersrowstack" or "metalrack" or "metalrackhalf" or "metalracklow" or "metalracklowhalf" or "metalpallet" or "meadrack" or "larder";
        Kitbash.Finish(go, vis, Box, WearNTear.MaterialType.Wood, 1000f, quiet, stackable: flatTop);
        if (vis.Find("straw") is { } straw && straw.GetComponent<MeshCollider>() is { } strawSolid) UnityEngine.Object.DestroyImmediate(strawSolid);
        AddKitSnaps(go);
        AddEdgeSnaps(go);
        if (!quiet) Plugin.Log.LogInfo($"{Title}: piece built, frame {Frame.bounds.size:F2} m, " + (Planks.Count > 0 ? $"{Planks.Count} plank(s)." : $"{Units.Count} units."));
    }

    // Skin mode: the same frame and contents as a child of a vanilla chest; its own look is hidden by SkinState.
    public GameObject BuildSkin(Transform root)
    {
        if (!Ready) return null;
        var vis = new GameObject(VisName) { layer = root.gameObject.layer }.transform;
        vis.SetParent(root, false);
        Part(vis, "frame", Frame);
        AddGlass(vis);
        AddArms(vis);
        AddStraw(vis);
        var group = vis.gameObject.AddComponent<LODGroup>();
        group.SetLODs(new[] { new LOD(0.03f, vis.GetComponentsInChildren<Renderer>(true)) });
        group.RecalculateBounds();
        if (!Plugin.Headless) vis.gameObject.AddComponent<StoreContents>();   // a server draws nothing
        return vis.gameObject;
    }

    void Part(Transform parent, string name, Mesh mesh, Material material = null)
    {
        var go = new GameObject(name) { layer = parent.gameObject.layer };
        go.transform.SetParent(parent, false);
        go.AddComponent<MeshFilter>().sharedMesh = mesh;
        var r = go.AddComponent<MeshRenderer>();
        r.sharedMaterial = material ? material : mat;
        if (Glass.SeeThrough(r.sharedMaterial)) { r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off; r.receiveShadows = false; }
    }

    // The frame's glass strips, in the frame's own space (they share its origin).
    void AddGlass(Transform vis)
    {
        for (int i = 0; i < FrameGlass.Count; i++) Part(vis, "glass" + i, FrameGlass[i].Mesh, FrameGlass[i].Mat);
    }

    // Each figure's carved arms as a part of its own ("arms<figure>", the frame's space and material), shown or hidden per piece.
    void AddArms(Transform vis)
    {
        if (Forms != null) for (int f = 0; f < Forms.Count; f++) if (Forms[f].Arms) Part(vis, "arms" + f, Forms[f].Arms);
    }

    // The straw as a part of its own ("straw": the frame's straw objects or the kit's Straw.obj, roughened), in its three shades; never
    // solid and never a support (BuildPiece and Refit take its collider off).
    void AddStraw(Transform vis)
    {
        if (!Straw) return;
        Part(vis, "straw", Straw);
        if (StrawShades != null && vis.Find("straw")?.GetComponent<MeshRenderer>() is { } r) r.sharedMaterials = StrawShades;
    }

    // Where one copy of an item goes, as a matrix in store space (the store's own root). Multiply by a part's matrix
    // (ItemVisual) to place that part. demo: the item the anchors were made with, for the bunker's volume rule.
    // display: display furniture (the larder) shows the item at Display item size x its true size instead of the layout's fit.
    public static Matrix4x4 Place(StoreUnit u, StoreCopy c, ItemVisual item, ItemVisual demo, bool display = false, float grow = 1f)
    {
        var size = item.Bounds.size;
        var align = Aligned(c, size);
        if (u.ItemRot != null && item.PrefabName != null && u.ItemRot.TryGetValue(item.PrefabName, out var turn)) align *= turn;
        var r = c.Rot * align;
        var d = Turned(c.FitAfterRotation ? r : align, size);
        float s;
        switch (c.Fit)
        {
            case Fit.Longest:
                s = c.Longest / Mathf.Max(1e-4f, Mathf.Max(size.x, Mathf.Max(size.y, size.z)));
                break;
            case Fit.Volume:
                float own = Mathf.Max(1e-6f, size.x * size.y * size.z);
                float target = c.Scale * c.Scale * c.Scale * (demo != null ? Mathf.Max(1e-6f, demo.Bounds.size.x * demo.Bounds.size.y * demo.Bounds.size.z) : own);
                s = Mathf.Pow(target / own, 1f / 3f);
                break;
            default:
                s = Mathf.Min(c.FitBox.x / Mathf.Max(1e-4f, d.x), Mathf.Min(c.FitBox.y / Mathf.Max(1e-4f, d.y), c.FitBox.z / Mathf.Max(1e-4f, d.z)));
                break;
        }
        if (display) s = Mathf.Min(Settings.DisplaySize.Value * item.RootScale, s * 1.15f);   // display size, capped at its slot
        else s *= grow;
        var centre = c.Offset;
        // Arrows and bolts stand on their holder's floor, through the straw (Joost, 25 Oct 19:17: "straw never support"): the
        // export lifts each foot up to 0.30 m "in the straw" plus a lean's lift, which the bottom anchor of the turned bounds
        // already gives.
        if (u.Kind is "arrow" or "bolt") centre.y = 0f;
        if (c.Bottom) centre.y += s * d.y * 0.5f;
        if (c.Back) centre.z += s * d.z * 0.5f;
        if (c.Pitch > 0f) centre.y += c.Layer * c.Pitch * s * d.y;
        var pos = centre - r * (s * item.Bounds.center);   // turn and scale about the bounds centre
        return Matrix4x4.TRS(u.Pos + u.Rot * pos, u.Rot * r, new Vector3(s, s, s));
    }

    static Quaternion Aligned(StoreCopy c, Vector3 size)
    {
        switch (c.Align)
        {
            case Align.LongYaw:
                return size.z > size.x ? Quaternion.Euler(0f, 90f, 0f) : Quaternion.identity;
            case Align.LongX:
            {
                // The root bin's script turned the longest axis onto Blender +x; in item space that is: x and z come
                // from their negative ends, up from up, and all go to -x.
                int a = ArgMax(size);
                var from = a == 0 ? Vector3.left : a == 1 ? Vector3.up : Vector3.back;
                return Quaternion.FromToRotation(from, Vector3.left);
            }
            case Align.Axes:
            {
                int il = ArgMax(size), it = ArgMin(size);
                if (it == il) it = (il + 1) % 3;
                var L = c.LongTo.normalized;
                var T = Vector3.ProjectOnPlane(c.ThinTo, L).normalized;
                if (L.sqrMagnitude < 0.5f || T.sqrMagnitude < 0.5f) return Quaternion.identity;
                return Quaternion.LookRotation(T, L) * Quaternion.Inverse(Quaternion.LookRotation(Axis(it), Axis(il)));
            }
            default:
                return Quaternion.identity;
        }
    }

    // Size of the axis-aligned box around a turned box of this size.
    internal static Vector3 Turned(Quaternion q, Vector3 size)
    {
        var m = Matrix4x4.Rotate(q);
        return new Vector3(
            Mathf.Abs(m.m00) * size.x + Mathf.Abs(m.m01) * size.y + Mathf.Abs(m.m02) * size.z,
            Mathf.Abs(m.m10) * size.x + Mathf.Abs(m.m11) * size.y + Mathf.Abs(m.m12) * size.z,
            Mathf.Abs(m.m20) * size.x + Mathf.Abs(m.m21) * size.y + Mathf.Abs(m.m22) * size.z);
    }

    static int ArgMax(Vector3 v) => v.x >= v.y && v.x >= v.z ? 0 : v.y >= v.z ? 1 : 2;
    static int ArgMin(Vector3 v) => v.x <= v.y && v.x <= v.z ? 0 : v.y <= v.z ? 1 : 2;
    static Vector3 Axis(int i) => i == 0 ? Vector3.right : i == 1 ? Vector3.up : Vector3.forward;
}

// A packed shelf's plank (assets/emergencyshelf_r4/emergencyshelf_r4.json, made by blender/emergencyshelf_r4.py), in Unity
// prefab space: Y = top surface, Z = row centre, X0..X1 = between the side boards, ZBack..ZFront = usable depth (wall to lip),
// Lip = lip height above Y, Clear = free height above Y. The file lists the planks in fill order (top plank first).
sealed class Plank
{
    public float Y, Z, X0, X1, ZBack, ZFront, Lip, Clear;

    public static List<Plank> Parse(Dictionary<string, object> doc, string piece)
    {
        if (piece == null || Json.Obj(doc, "pieces") is not { } pieces || Json.Obj(pieces, piece) is not { } module) return null;
        if (!module.TryGetValue("planks", out var o) || o is not List<object> list) return null;
        var planks = new List<Plank>();
        foreach (var e in list)
        {
            if (e is not Dictionary<string, object> d) continue;
            float N(string k, float dflt) => d.TryGetValue(k, out var v) && v is double x ? (float)x : dflt;
            var xs = d.TryGetValue("x", out var xv) && xv is List<object> xl && xl.Count == 2 && xl[0] is double a && xl[1] is double b ? (Mathf.Min((float)a, (float)b), Mathf.Max((float)a, (float)b)) : (-0.94f, 0.94f);
            planks.Add(new Plank
            {
                Y = N("y", 0f), Z = N("z", 0.22f), X0 = xs.Item1, X1 = xs.Item2,
                ZBack = N("z_back", 0.01f), ZFront = N("z_front", 0.4f), Lip = N("lip_top", 0f), Clear = N("clear_height", 0.4f),
            });
        }
        return planks;
    }
}

// The shelf's packing (Joost, 22 Oct 2026): one item per stack at Display item size x its true size, left to right as seen
// from the front (+x to -x). Each stack has its plank (the shelf's grid has one row per plank: row 0 is the top plank), and
// every stack on a plank is shown: when they don't fit at that size, all items on that plank shrink together until they do
// (Joost: six in the shelf, six on the plank).
// Orientation (turn about up, then lean back against the wall): the longest horizontal side along the plank; an item over
// 0.5 m (true size) takes a diagonal turn and/or a lean when that fits the plank's depth and height and saves 3 cm of plank;
// an item too deep for the plank leans if that fits, else stands against the wall over the lip. Gap 3 cm.
static class Packing
{
    const float Gap = 0.03f, LongTrue = 0.5f, Saving = 0.03f;

    // Foot: the middle (z) of what the item stands on, its lowest quarter. A bottle's cord or a pie's spoon sticking out on one
    // side no longer pushes the item off the plank's line (Joost: the potions looked set behind one another).
    sealed class Orientation { public Quaternion Rot; public Vector3 Min, Size; public bool Lean; public float Foot; }
    static readonly Dictionary<(ItemVisual, int, int, int), Orientation> cache = new();
    static bool rootsLogged;

    // plankOf[i]: the plank (0 = top) stack i goes on.
    public static List<Matrix4x4?> Pack(List<Plank> planks, List<ItemVisual> items, List<int> plankOf, float display)
    {
        LogRoots();
        var result = new List<Matrix4x4?>(new Matrix4x4?[items.Count]);
        for (int k = 0; k < planks.Count; k++)
        {
            var p = planks[k];
            var mine = new List<(int i, Orientation o)>();
            for (int i = 0; i < items.Count; i++)
                if (items[i] != null && Mathf.Clamp(plankOf[i], 0, planks.Count - 1) == k && Orient(items[i], p.ZFront - p.ZBack, p.Clear, display) is { } o)
                    mine.Add((i, o));
            if (mine.Count == 0) continue;
            float need = mine.Sum(m => m.o.Size.x), room = p.X1 - p.X0 - Gap * (mine.Count + 1);
            float f = need > room && need > 0f ? Mathf.Max(0.2f, room / need) : 1f;   // shrink this plank's items together to fit
            // The row sits in the middle of the plank (Joost: it leaned to one end), whatever room is left over.
            float used = mine.Sum(m => m.o.Size.x * f) + Gap * (mine.Count + 1);
            float cursor = p.X1 - Mathf.Max(0f, (p.X1 - p.X0 - used) / 2f);
            foreach (var (i, o) in mine)
            {
                Vector3 min = o.Min * f, size = o.Size * f;
                float x = cursor - Gap - size.x / 2f, lift = 0f, tz;
                if (!o.Lean && size.z <= p.ZFront - p.ZBack + 1e-4f)
                    tz = Mathf.Clamp(p.Z - o.Foot * f, p.ZBack - min.z, p.ZFront - min.z - size.z);   // its foot on the line, all of it on the plank
                else
                {
                    tz = p.ZBack - min.z;                                       // against the wall
                    if (p.ZBack + size.z > p.ZFront + 1e-4f) lift = p.Lip;      // over the lip
                }
                var t = new Vector3(x - (min.x + size.x / 2f), p.Y + lift - min.y, tz);
                result[i] = Matrix4x4.TRS(t, o.Rot, items[i].RootScaleV * (display * f));
                cursor = x - size.x / 2f;
            }
        }
        return result;
    }

    // Which plank each of n slots goes on: the grid's rows map onto the planks (a shelf's grid has one row per plank; a skinned
    // vanilla chest's rows are shared out evenly).
    public static List<int> Planks(IEnumerable<int> slots, int totalSlots, int planks)
    {
        int per = Mathf.Max(1, Mathf.CeilToInt(totalSlots / (float)Mathf.Max(1, planks)));
        return slots.Select(s => Mathf.Min(planks - 1, s / per)).ToList();
    }

    // How the item stands on a plank of usable depth d and free height h; null when it can't stand there at all.
    static Orientation Orient(ItemVisual item, float d, float h, float display)
    {
        var key = (item, Mathf.RoundToInt(d * 1000f), Mathf.RoundToInt(h * 1000f), Mathf.RoundToInt(display * 1000f));
        if (cache.TryGetValue(key, out var hit)) return hit;
        var pts = item.Points();
        Orientation best = null, baseO = null;
        float bestW = float.MaxValue, bestTurn = float.MaxValue;
        int baseYaw = 0;
        var all = new List<(int yaw, int lean, Orientation o)>();
        for (int yaw = 0; yaw < 180; yaw += 5)
            for (int lean = 0; lean < 85; lean = lean == 0 ? 10 : lean + 5)
            {
                var q = Quaternion.Euler(lean, 0f, 0f) * Quaternion.Euler(0f, yaw, 0f);   // lean > 0 raises the back (-z), at the wall
                Vector3 lo = Vector3.positiveInfinity, hi = Vector3.negativeInfinity;
                foreach (var v in pts)
                {
                    var r = q * (v * display);
                    lo = Vector3.Min(lo, r);
                    hi = Vector3.Max(hi, r);
                }
                float footTop = lo.y + (hi.y - lo.y) * 0.25f, f0 = float.MaxValue, f1 = float.MinValue;
                foreach (var v in pts)
                {
                    var r = q * (v * display);
                    if (r.y <= footTop) { f0 = Mathf.Min(f0, r.z); f1 = Mathf.Max(f1, r.z); }
                }
                var o = new Orientation { Rot = q, Min = lo, Size = hi - lo, Lean = lean > 0, Foot = (f0 + f1) / 2f };
                all.Add((yaw, lean, o));
                if (lean == 0 && (baseO == null || o.Size.z < baseO.Size.z - 1e-5f)) { baseO = o; baseYaw = yaw; }
            }
        bool Fits(Orientation o) => o.Size.z <= d + 1e-4f && o.Size.y <= h + 1e-4f;
        foreach (var (yaw, lean, o) in all)
        {
            if (!Fits(o)) continue;
            float w = Mathf.Round(o.Size.x * 1e4f), turn = lean * 1000f + Mathf.Min(Mathf.Abs(yaw - baseYaw), 180 - Mathf.Abs(yaw - baseYaw));
            if (w < bestW || (w == bestW && turn < bestTurn)) { best = o; bestW = w; bestTurn = turn; }
        }
        Orientation pick;
        if (Fits(baseO)) pick = baseO.Size.x > LongTrue * display && best != null && best.Size.x < baseO.Size.x - Saving ? best : baseO;
        else if (best != null) pick = best;
        else if (baseO.Size.y <= h + 1e-4f) pick = baseO;   // too deep for any lean: against the wall, over the lip
        else pick = null;
        return cache[key] = pick;
    }

    // True size check (Joost): the root scale of a few item prefabs as the running game has them.
    static void LogRoots()
    {
        if (rootsLogged || !ObjectDB.instance) return;
        rootsLogged = true;
        var sb = new StringBuilder("Shelf: item prefab root scale (true size = model x this):");
        foreach (var n in new[] { "Bread", "LoxPie", "MeadHealthMinor", "Turnip", "MeatPlatter", "MeadTrollPheromones" })
        {
            var go = ObjectDB.instance.GetItemPrefab(n);
            sb.Append($" {n} {(go ? go.transform.localScale.ToString("F3") : "missing")};");
        }
        Plugin.Log.LogInfo(sb.ToString());
    }
}

// An item's own look, read from the running game's item prefab: every visible mesh renderer (LOD 0 only, no colliders,
// physics, ItemDrop or ZNetView: we only take mesh, materials and where they sit). Cached per prefab.
// The real shape of items whose meshes the game keeps on the GPU only (Mesh.isReadable false: Unity uploaded the vertices and kept
// no copy a script may read). Read back from the GPU in the player's own game, once per item: the mesh's vertex buffer through
// AsyncGPUReadback, every part in ItemVisual's turned item space (root scale not applied), at most 600 points (the extremes in 13
// directions, the rest evenly through the distinct positions). Kept in BepInEx/cache/Storehouse-item-points.bin with the item's
// meshes (name and vertex count) and the game's box, so a game or mod update that changes a mesh measures it again. Until 0.8.5 these points shipped
// in assets/item_points.bin, taken from the game's bundle and the mods'; from 0.8.6 the mod ships nothing of theirs (1 Nov 2026).
// No graphics device (a dedicated server) or a failed read: the measured table (ItemTightBounds), else the game's box.
static class ItemPoints
{
    public const int Max = 600;
    const string Magic = "SHPC1";
    static Dictionary<string, (string key, Vector3 boxMin, Vector3 boxMax, Vector3[] points)> rows;
    static bool dirty;
    static float lastSave;
    static Action onQuit;
    static string CacheFile => Path.Combine(BepInEx.Paths.CachePath, "Storehouse-item-points.bin");

    public static Vector3[] Get(string prefab, IReadOnlyList<ItemVisual.Part> parts, Bounds box)
    {
        if (prefab == null || Plugin.Headless || !SystemInfo.supportsAsyncGPUReadback) return null;
        if (rows == null) Load();
        string key = Key(parts);
        if (rows.TryGetValue(prefab, out var r) && r.key == key && Near(r.boxMin, box.min) && Near(r.boxMax, box.max)) return r.points;
        var watch = System.Diagnostics.Stopwatch.StartNew();
        var all = Vertices(parts, out string why);
        if (all == null || all.Count == 0)
        {
            Plugin.Log.LogWarning($"Item points: '{prefab}' not read from the GPU ({why ?? "no vertices"}); measured by the table or its box.");
            return null;
        }
        var pts = Sample(all);
        rows[prefab] = (key, box.min, box.max, pts);
        dirty = true;
        Plugin.Log.LogInfo($"Item points: '{prefab}' read from the GPU, {all.Count} vertices, {pts.Length} points kept, in {watch.ElapsedMilliseconds} ms.");
        if (Time.realtimeSinceStartup - lastSave > 10f) Save();
        return pts;
    }

    static string Key(IReadOnlyList<ItemVisual.Part> parts) => string.Join("|", parts.Select(p => p.Mesh ? $"{p.Mesh.name}:{p.Mesh.vertexCount}" : "-"));
    static bool Near(Vector3 a, Vector3 b) => Mathf.Abs(a.x - b.x) <= 1e-4f && Mathf.Abs(a.y - b.y) <= 1e-4f && Mathf.Abs(a.z - b.z) <= 1e-4f;

    // Every vertex of every part, in turned item space: a readable part's own, the others read back from the GPU. Null: one failed.
    public static List<Vector3> Vertices(IReadOnlyList<ItemVisual.Part> parts, out string why)
    {
        why = null;
        var all = new List<Vector3>();
        foreach (var part in parts)
        {
            if (!part.Mesh) continue;
            var vs = part.Readable ? part.Mesh.vertices : Gpu(part.Mesh, out why);
            if (vs == null) { why = $"{part.Mesh.name}: {why}"; return null; }
            foreach (var p in vs) all.Add(part.M.MultiplyPoint3x4(p));
        }
        return all;
    }

    // A mesh's positions from its GPU vertex buffer (the stream that holds them, at their offset and stride; float32 or float16).
    static Vector3[] Gpu(Mesh mesh, out string why)
    {
        why = null;
        var pos = UnityEngine.Rendering.VertexAttribute.Position;
        if (!mesh.HasVertexAttribute(pos)) { why = "no positions"; return null; }
        var format = mesh.GetVertexAttributeFormat(pos);
        if (format != UnityEngine.Rendering.VertexAttributeFormat.Float32 && format != UnityEngine.Rendering.VertexAttributeFormat.Float16) { why = $"positions as {format}"; return null; }
        int stream = mesh.GetVertexAttributeStream(pos), offset = mesh.GetVertexAttributeOffset(pos), stride = mesh.GetVertexBufferStride(stream), n = mesh.vertexCount;
        byte[] data;
        using (var buffer = mesh.GetVertexBuffer(stream))
        {
            if (buffer == null) { why = "no vertex buffer"; return null; }
            var request = UnityEngine.Rendering.AsyncGPUReadback.Request(buffer);
            request.WaitForCompletion();
            if (request.hasError) { why = "the GPU read-back failed"; return null; }
            data = request.GetData<byte>().ToArray();
        }
        int size = format == UnityEngine.Rendering.VertexAttributeFormat.Float32 ? 4 : 2;
        if (n == 0 || data.Length < (n - 1) * stride + offset + 3 * size) { why = $"{data.Length} bytes for {n} vertices of {stride}"; return null; }
        var v = new Vector3[n];
        for (int i = 0; i < n; i++)
        {
            int at = i * stride + offset;
            v[i] = size == 4
                ? new Vector3(BitConverter.ToSingle(data, at), BitConverter.ToSingle(data, at + 4), BitConverter.ToSingle(data, at + 8))
                : new Vector3(Mathf.HalfToFloat(BitConverter.ToUInt16(data, at)), Mathf.HalfToFloat(BitConverter.ToUInt16(data, at + 2)), Mathf.HalfToFloat(BitConverter.ToUInt16(data, at + 4)));
        }
        return v;
    }

    // At most Max points: the extremes along the 3 axes, 6 edge and 4 corner diagonals (both ways), then evenly through the rest.
    static readonly Vector3[] Directions =
    {
        new(1, 0, 0), new(0, 1, 0), new(0, 0, 1), new(1, 1, 0), new(1, -1, 0), new(1, 0, 1), new(1, 0, -1), new(0, 1, 1), new(0, 1, -1),
        new(1, 1, 1), new(1, 1, -1), new(1, -1, 1), new(-1, 1, 1),
    };

    static Vector3[] Sample(List<Vector3> all)
    {
        if (all.Count > Max)   // one point per position: a seam's split vertices share theirs (to 0.1 mm)
        {
            var seen = new HashSet<(int, int, int)>();
            all = all.Where(p => seen.Add((Mathf.RoundToInt(p.x * 1e4f), Mathf.RoundToInt(p.y * 1e4f), Mathf.RoundToInt(p.z * 1e4f)))).ToList();
        }
        if (all.Count <= Max) return all.ToArray();
        var keep = new SortedSet<int>();
        foreach (var d in Directions)
        {
            int lo = 0, hi = 0;
            float min = float.MaxValue, max = float.MinValue;
            for (int i = 0; i < all.Count; i++)
            {
                float t = Vector3.Dot(all[i], d);
                if (t < min) { min = t; lo = i; }
                if (t > max) { max = t; hi = i; }
            }
            keep.Add(lo);
            keep.Add(hi);
        }
        int room = Max - keep.Count;
        for (int k = 0; k < room && keep.Count < Max; k++) keep.Add((int)((long)k * all.Count / room));
        return keep.Select(i => all[i]).ToArray();
    }

    // Format (little-endian): "SHPC1", int32 count; per item: name and key (BinaryWriter strings), 6 float32 (box min, box max),
    // uint16 n, n x 3 float32.
    static void Load()
    {
        rows = new Dictionary<string, (string, Vector3, Vector3, Vector3[])>(StringComparer.Ordinal);
        onQuit = Save;
        Application.quitting += onQuit;
        var path = CacheFile;
        if (!File.Exists(path)) return;
        try
        {
            using var r = new BinaryReader(File.OpenRead(path));
            if (new string(r.ReadChars(Magic.Length)) != Magic) { Plugin.Log.LogWarning($"Item points: {path} is not an item points cache; measured again."); return; }
            int count = r.ReadInt32();
            for (int i = 0; i < count; i++)
            {
                string name = r.ReadString(), key = r.ReadString();
                var min = new Vector3(r.ReadSingle(), r.ReadSingle(), r.ReadSingle());
                var max = new Vector3(r.ReadSingle(), r.ReadSingle(), r.ReadSingle());
                var pts = new Vector3[r.ReadUInt16()];
                for (int k = 0; k < pts.Length; k++) pts[k] = new Vector3(r.ReadSingle(), r.ReadSingle(), r.ReadSingle());
                if (pts.Length > 0) rows[name] = (key, min, max, pts);
            }
            Plugin.Log.LogInfo($"Item points: {rows.Count} item shape(s) from {path}.");
        }
        catch (Exception e) { rows.Clear(); Plugin.Log.LogWarning($"Item points: {path} unreadable ({e.Message}); measured again."); }
    }

    static void Save()
    {
        lastSave = Time.realtimeSinceStartup;
        if (!dirty || rows == null) return;
        var path = CacheFile;
        try
        {
            Directory.CreateDirectory(Path.GetDirectoryName(path));
            using (var w = new BinaryWriter(File.Create(path + ".tmp")))
            {
                w.Write(Magic.ToCharArray());
                w.Write(rows.Count);
                foreach (var kv in rows)
                {
                    w.Write(kv.Key);
                    w.Write(kv.Value.key);
                    foreach (var c in new[] { kv.Value.boxMin, kv.Value.boxMax }) { w.Write(c.x); w.Write(c.y); w.Write(c.z); }
                    w.Write((ushort)kv.Value.points.Length);
                    foreach (var p in kv.Value.points) { w.Write(p.x); w.Write(p.y); w.Write(p.z); }
                }
            }
            if (File.Exists(path)) File.Delete(path);
            File.Move(path + ".tmp", path);
            dirty = false;
        }
        catch (Exception e) { Plugin.Log.LogWarning($"Item points: could not write {path} ({e.Message}); measured again next time."); }
    }

    public static void Release()
    {
        Save();
        if (onQuit != null) Application.quitting -= onQuit;
        onQuit = null;
        rows = null;
    }
}

#if !RELEASE
// The GPU read-back checked against the true bounds measured from the game's files (ItemTightBounds; dev builds, STOREHOUSE_POINTS_CHECK=1
// in the game's environment, "quit" to close the game after): on the main menu, once every mod's items are in, every item with a part
// the game keeps on the GPU only. BepInEx/cache/storehouse-points-check.md. Its first run (1 Nov 2026, against the 0.8.5
// item_points.bin too): 792 items read back, 84/84 within 2 mm of the table, every one of the 161,578 old points on a vertex read back.
static class PointsCheck
{
    public static void Hook()
    {
        var mode = Environment.GetEnvironmentVariable("STOREHOUSE_POINTS_CHECK");
        if (string.IsNullOrEmpty(mode)) return;
        void Once() { ItemManager.OnItemsRegisteredFejd -= Once; Run(mode == "quit"); }
        ItemManager.OnItemsRegisteredFejd += Once;
    }

    static void Run(bool quit)
    {
        var watch = System.Diagnostics.Stopwatch.StartNew();
        var sb = new StringBuilder("| item | vertices | points | vs table (mm) |\n|---|---|---|---|\n");
        int items = 0, read = 0, tableOk = 0, tableN = 0;
        foreach (var prefab in ObjectDB.instance.m_items.Where(p => p).OrderBy(p => p.name, StringComparer.Ordinal))
        {
            ItemVisual v;
            try { v = ItemVisual.Get(prefab); } catch (Exception e) { sb.Append($"| {prefab.name} | error {e.Message} |\n"); continue; }
            if (v == null || v.Parts.All(p => p.Readable) || v.PrefabName != prefab.name) continue;
            items++;
            var all = ItemPoints.Vertices(v.Parts, out string why);
            if (all == null) { sb.Append($"| {prefab.name} | not read: {why} |\n"); continue; }
            read++;
            string table = "";
            if (ItemTightBounds.Rows.TryGetValue(prefab.name, out var row) && Off(row.boxMin, row.boxMax, v.Bounds.min, v.Bounds.max) <= 2f)
            {
                float off = Off(row.min, row.max, v.Tight.min, v.Tight.max);
                tableN++; if (off <= 2f) tableOk++;
                table = $"{off:F1}";
            }
            sb.Append($"| {prefab.name} | {all.Count} | {v.Points().Length} | {table} |\n");
        }
        string summary = $"Points check: {items} item(s) with a part on the GPU only, {read} read back; true bounds within 2 mm of the table for {tableOk}/{tableN}; {watch.ElapsedMilliseconds} ms.";
        var path = Path.Combine(BepInEx.Paths.CachePath, "storehouse-points-check.md");
        File.WriteAllText(path, $"# {summary}\n\n{sb}");
        Plugin.Log.LogInfo(summary + $" ({path})");
        if (quit) Application.Quit();
    }

    static float Off(Vector3 aMin, Vector3 aMax, Vector3 bMin, Vector3 bMax)
    {
        var d = Vector3.Max(new Vector3(Mathf.Abs(aMin.x - bMin.x), Mathf.Abs(aMin.y - bMin.y), Mathf.Abs(aMin.z - bMin.z)),
            new Vector3(Mathf.Abs(aMax.x - bMax.x), Mathf.Abs(aMax.y - bMax.y), Mathf.Abs(aMax.z - bMax.z)));
        return Mathf.Max(d.x, d.y, d.z) * 1000f;
    }
}
#endif

sealed class ItemVisual
{
    public sealed class Part
    {
        public Mesh Mesh;
        public Material[] Mats;
        public Matrix4x4 M;          // item space, already turned 180 degrees about up (see Anchors)
        public string Name;          // the renderer's GameObject name (Topless)
        public bool Readable;        // Mesh.CombineMeshes needs the vertex data on the CPU
        public UnityEngine.Rendering.ShadowCastingMode Shadows;
        public bool Receive;         // the item renderer's own lighting settings, for drawing copies without a renderer
        public UnityEngine.Rendering.LightProbeUsage Probes;
        public UnityEngine.Rendering.ReflectionProbeUsage Reflections;
    }

    public readonly List<Part> Parts = new();
    public ItemVisual Far;   // the game's lightest LOD, drawn beyond Far contents (null: none lighter)
    int tris = -1;
    // Triangles of one copy (index counts work on unreadable meshes too).
    public int Triangles
    {
        get
        {
            if (tris >= 0) return tris;
            long t = 0;
            foreach (var p in Parts) if (p.Mesh) for (int i = 0; i < p.Mesh.subMeshCount; i++) t += p.Mesh.GetIndexCount(i) / 3;
            return tris = (int)Math.Min(int.MaxValue, t);
        }
    }
    public Bounds Bounds;           // around all parts, in that same turned item space
    public Bounds Drawn;            // around the parts actually drawn (a topless crop: the root only); placement keeps Bounds
    // The item itself, in the same space (the models session, 27 Oct: Bounds is the box around each part's turned box, and most
    // weapons and shields are authored 2-33 degrees off their root, so it measures them too big and off-centre: the Banded Shield
    // 1.34 m instead of 0.95, a Butcher Knife 0.43 m wide instead of 0.07; Arsenal Spine weapons floated up to 5 cm off their arms).
    // Every vertex of a readable part; for an item with a part the game keeps on the GPU only, its row in ItemTightBounds (measured
    // from the game's own bundle) while the game's box still equals the one measured there (within 2 mm), else that part's box.
    // Equipment fits and centres on it; piles, crops and the units style keep Bounds.
    Bounds? tight;
    Vector3[] measured;   // ItemPoints' shape, when the game keeps a part on the GPU only
    public Bounds Tight => tight ?? Bounds;
    public Vector3 TrueSize => Vector3.Scale(Tight.size, RootScaleV);
    // The prefab root's own scale. Parts and Bounds are in root space (without it); an item dropped in the world is drawn
    // with it, so its true size is Bounds x RootScaleV. Every vanilla meal and mead has 1 (read from the game files).
    public Vector3 RootScaleV = Vector3.one;
    public float RootScale => (RootScaleV.x + RootScaleV.y + RootScaleV.z) / 3f;
    Vector3[] points;
    string prefabName;
    public string PrefabName => prefabName;
    ItemVisual topless;
    static readonly Dictionary<string, ItemVisual> cache = new();
    static readonly Matrix4x4 HalfTurn = Matrix4x4.Rotate(Quaternion.Euler(0f, 180f, 0f));

    // Stored items stand still (0.3.1, Joost: carrots in the Root Bin swayed). Plant items draw with the game's
    // Custom/Vegetation or Custom/Grass shader, which moves vertices with the wind (_SwaySpeed, _SwayDistance), ripples the
    // leaves (_RippleDistance) and bends them away from a passing player (_PushDistance); no shader keyword switches it (item
    // rips: carrot and turnip leaves, barley, flax, fiddlehead, the Mistlands mushrooms, thistle, dandelion). Contents draw with
    // a copy that has those at 0, made once per material; the shared original (the item in the world and in your hand) is
    // never touched. Every other material is used as it is.
    static readonly string[] WindProps = { "_SwayDistance", "_SwaySpeed", "_RippleDistance", "_PushDistance" };
    static readonly Dictionary<Material, Material> still = new();

    static Material Still(Material src)
    {
        if (!src) return src;
        if (still.TryGetValue(src, out var m)) return m;
        m = src;
        if (src.HasProperty("_SwaySpeed") || src.HasProperty("_SwayDistance"))
        {
            m = new Material(src) { name = src.name + " (storehouse still)" };
            foreach (var p in WindProps) if (m.HasProperty(p)) m.SetFloat(p, 0f);
            Plugin.Log.LogInfo($"Contents: material '{src.name}' ({(src.shader ? src.shader.name : "no shader")}): wind off in a copy (sway, ripple, push 0).");
        }
        return still[src] = m;
    }

    // Live reload: the still copies this copy made (the game's own materials stay).
    public static void Release()
    {
        foreach (var kv in still) if (kv.Value && kv.Value != kv.Key) UnityEngine.Object.Destroy(kv.Value);
        still.Clear();
        cache.Clear();
        ItemPoints.Release();
    }

    // Root crops go into the Root Bin with their tops cut off (0.3.1, Joost and Jake). From the item rips: the carrot's and
    // the turnip's greens are a renderer of their own ("blast (1)" / "blast": the game's Fern01 leaf mesh with an alpha-clipped
    // Custom/Vegetation material), beside the root ("carrot" / "turnip (1)"). The onion is one opaque bulb with no greens;
    // seeds and the other crops keep everything. Matched by renderer name prefix, per item prefab.
    static readonly Dictionary<string, string[]> Greens = new()
    {
        ["Carrot"] = new[] { "blast" },
        ["Turnip"] = new[] { "blast" },
    };

    // This item without its greens; itself when it has none. Bounds and RootScaleV stay the whole item's: the Root Bin's
    // heaps (CropLayout) place and scale each copy by the full item's bounds, so the roots stay exactly where they lay.
    public ItemVisual Topless
    {
        get
        {
            if (topless != null) return topless;
            if (prefabName == null || !Greens.TryGetValue(prefabName, out var names)) return topless = this;
            var v = new ItemVisual { RootScaleV = RootScaleV, Bounds = Bounds, tight = tight, prefabName = prefabName };
            v.topless = v;
            foreach (var part in Parts)
                if (!names.Any(n => part.Name != null && part.Name.StartsWith(n, StringComparison.Ordinal))) v.Parts.Add(part);
            if (v.Parts.Count == Parts.Count || v.Parts.Count == 0)
            {
                Plugin.Log.LogWarning($"Item model '{prefabName}': greens ({string.Join(", ", names)}) "
                    + (v.Parts.Count == 0 ? "are the whole model" : "not found") + "; drawn whole in the Root Bin.");
                return topless = this;
            }
            v.Drawn = Geometry.Xform(v.Parts[0].M, v.Parts[0].Mesh.bounds);
            foreach (var part in v.Parts) v.Drawn.Encapsulate(Geometry.Xform(part.M, part.Mesh.bounds));
            Plugin.Log.LogInfo($"Item model '{prefabName}': {Parts.Count - v.Parts.Count} green part(s) left out in the Root Bin.");
            return topless = v;
        }
    }

    public static ItemVisual Get(string prefab) => ObjectDB.instance ? Get(ObjectDB.instance.GetItemPrefab(prefab)) : null;

    // An item whose own prefab has nothing to draw, drawn as another item that carries its model (Joost, 27 Oct: the Forest Troll
    // trophy missing from both Trophy Halls). Read from the game's asset bundle (27 Oct 2026): TrophyForestTroll's head is a
    // MeshRenderer with no mesh and no materials, so the game draws nothing for it either (the trophy hall layouts list it under
    // kinds_missing); TrophyFrostTroll carries the troll head (trophy_troll) with the forest troll's skin (troll_diffuse), the
    // same item_rotation in both layouts. Used only while the item itself measures empty, so a game patch that gives it its
    // model back takes over by itself. Not an unreadable mesh: those are measured and drawn per copy or instanced (TrophyEikthyr).
    static readonly Dictionary<string, string> StandIns = new(StringComparer.Ordinal) { ["TrophyForestTroll"] = "TrophyFrostTroll" };
    static string TwinOf(string name) => name.StartsWith("FW_", StringComparison.Ordinal) || name.StartsWith("SP_", StringComparison.Ordinal) ? name.Substring(3) : null;

    public static ItemVisual Get(GameObject prefab)
    {
        if (!prefab) return null;
        if (cache.TryGetValue(prefab.name, out var v)) return v;
        var near = Measure(prefab);
        // A mod's twin of a game item drawn with the mod's own see-through-queue shader (the Fallen Warrior set: FW_ShieldBlackmetalTower,
        // "Custom/Fallen Warrior", queue 3000): its copies did not show in the stores (Joost, 27 Oct: the Arsenal's second tower and
        // Armory B's third shield missing, both this one); worn on a mannequin it shows. Drawn with the game twin's model instead (the
        // same mesh, the game's own material), when the twin is there.
        if (near != null && TwinOf(prefab.name) is { } twin && twin != prefab.name && near.Parts.Any(p => p.Mats.Any(m => m && m.shader && m.shader.name.StartsWith("Custom/Fallen", StringComparison.Ordinal)))
            && ObjectDB.instance && ObjectDB.instance.GetItemPrefab(twin) is { } twinPrefab && Get(twinPrefab) is { } twinLook)
        {
            Plugin.Log.LogInfo($"Item model '{prefab.name}': its shader ({near.Parts.SelectMany(p => p.Mats).First(m => m && m.shader && m.shader.name.StartsWith("Custom/Fallen", StringComparison.Ordinal)).shader.name}) does not show in the stores; drawn with {twin}'s model.");
            return cache[prefab.name] = twinLook;
        }
        if (near != null) near.Far = MeasureFar(prefab, near);
        else if (StandIns.TryGetValue(prefab.name, out var standIn))
        {
            near = Get(standIn);
            if (near != null) Plugin.Log.LogInfo($"Item model '{prefab.name}': its prefab has no mesh; drawn with {standIn}'s model.");
            else Plugin.Log.LogWarning($"Item model '{prefab.name}': no visible mesh, nor {standIn} to draw it with; it is left out of the stores.");
        }
        return cache[prefab.name] = near;
    }

    // The item as the game draws it from afar: each LODGroup's last LOD instead of LOD0 (renderers outside any LODGroup as they
    // are), placed and sized exactly as the near version (its bounds), so copies stay where the layout put them. Null when the
    // item has no lighter LOD (most small items have one mesh) or the far one saves too little.
    static ItemVisual MeasureFar(GameObject prefab, ItemVisual near)
    {
        var groups = prefab.GetComponentsInChildren<LODGroup>(true).Where(g => g.lodCount > 1).ToList();
        if (groups.Count == 0) return null;
        var root = prefab.transform;
        var keep = new HashSet<Renderer>();
        var inGroups = new HashSet<Renderer>();
        foreach (var group in groups)
        {
            var lods = group.GetLODs();
            foreach (var lod in lods) foreach (var r in lod.renderers) if (r) inGroups.Add(r);
            for (int i = lods.Length - 1; i >= 0; i--)
            {
                var rs = lods[i].renderers.Where(r => r).ToList();
                if (rs.Count == 0) continue;
                foreach (var r in rs) keep.Add(r);
                break;
            }
        }
        var v = new ItemVisual { RootScaleV = near.RootScaleV, prefabName = prefab.name, Bounds = near.Bounds, tight = near.tight };
        foreach (var r in prefab.GetComponentsInChildren<Renderer>(true))
        {
            if (inGroups.Contains(r) ? !keep.Contains(r) : !near.Parts.Any(x => x.Name == r.name)) continue;
            Mesh mesh = r is SkinnedMeshRenderer smr ? smr.sharedMesh : r is MeshRenderer && r.GetComponent<MeshFilter>() is { } mf ? mf.sharedMesh : null;
            if (!mesh) continue;
            v.Parts.Add(new Part
            {
                Mesh = mesh, Mats = r.sharedMaterials.Select(Still).ToArray(), M = HalfTurn * root.worldToLocalMatrix * r.transform.localToWorldMatrix,
                Name = r.name, Readable = mesh.isReadable, Shadows = r.shadowCastingMode, Receive = r.receiveShadows,
                Probes = r.lightProbeUsage, Reflections = r.reflectionProbeUsage,
            });
        }
        if (v.Parts.Count == 0 || v.Triangles > near.Triangles * 0.8f) return null;
        Plugin.Log.LogInfo($"Item model '{prefab.name}': far version {v.Triangles} triangles (near {near.Triangles}).");
        return v;
    }

    // includeHidden: a second pass for items whose model is switched off in the prefab (MeadStaminaLingering: Joost saw an
    // empty spot on the shelf); the game shows it some other way, we take the hidden mesh.
    static ItemVisual Measure(GameObject prefab, bool includeHidden = false)
    {
        var root = prefab.transform;
        var skip = new HashSet<Renderer>();
        foreach (var group in prefab.GetComponentsInChildren<LODGroup>(true))
        {
            var lods = group.GetLODs();
            // A renderer that LOD0 lists too belongs to LOD0 (Black Marble lists its only mesh in both, and was left out).
            var lod0 = new HashSet<Renderer>(lods.Length > 0 ? lods[0].renderers.Where(r => r) : Enumerable.Empty<Renderer>());
            for (int i = 1; i < lods.Length; i++) foreach (var r in lods[i].renderers) if (r && !lod0.Contains(r)) skip.Add(r);
        }
        var v = new ItemVisual { RootScaleV = root.localScale, prefabName = prefab.name };
        bool first = true;
        int unreadable = 0;
        foreach (var r in prefab.GetComponentsInChildren<Renderer>(true))
        {
            if (skip.Contains(r) || (!includeHidden && (!r.enabled || !Kit.ActiveChain(r.transform, root)))) continue;
            if (includeHidden && InHand(r.transform, root)) continue;   // the in-hand pose, never the dropped item (MeadStaminaLingering: "equipoffset/potion (1)", lying)
            // The worn version, when the item has a dropped one too (the models session, armour r3: FW_/SP_ArmorTrollLeatherChest and
            // FW_/SP_CapeWolf carry an active "attach_skin" body beside their root "log" pouch, 1.29 and 2.06 m tall instead of 0.63).
            if (Under(r.transform, root, "attach_skin") && prefab.GetComponentsInChildren<Renderer>(true).Any(o => o != r && !Under(o.transform, root, "attach_skin")
                && (includeHidden || o.enabled && Kit.ActiveChain(o.transform, root)))) continue;
            Mesh mesh = null;
            if (r is SkinnedMeshRenderer smr) mesh = smr.sharedMesh;            // drawn in its bind pose
            else if (r is MeshRenderer && r.GetComponent<MeshFilter>() is { } mf) mesh = mf.sharedMesh;
            if (!mesh) continue;
            var m = HalfTurn * root.worldToLocalMatrix * r.transform.localToWorldMatrix;
            v.Parts.Add(new Part
            {
                Mesh = mesh, Mats = r.sharedMaterials.Select(Still).ToArray(), M = m, Name = r.name, Readable = mesh.isReadable, Shadows = r.shadowCastingMode,
                Receive = r.receiveShadows, Probes = r.lightProbeUsage, Reflections = r.reflectionProbeUsage,
            });
        }
        // The hidden pass takes every renderer, and one bottle mesh can be there twice, once lying down (Joost, 27 Oct, f79: each
        // Lingering Stamina Mead on the Shelf drawn as an upright bottle with a second one lying through it; "they should just be
        // upright"): of the parts sharing a mesh, only the most upright (its own up nearest the item's).
        if (includeHidden && v.Parts.Count > 1)
        {
            var keep = v.Parts.GroupBy(p => p.Mesh).Select(g => g.OrderByDescending(p => p.M.GetColumn(1).normalized.y).First()).ToList();
            if (keep.Count < v.Parts.Count)
            {
                Plugin.Log.LogInfo($"Item model '{prefab.name}': hidden model, {v.Parts.Count - keep.Count} repeat(s) of a mesh left out "
                    + $"({string.Join(", ", v.Parts.Except(keep).Select(p => p.Name))}); kept {string.Join(", ", keep.Select(p => p.Name))}, the most upright.");
                v.Parts.RemoveAll(p => !keep.Contains(p));
            }
            else Plugin.Log.LogInfo($"Item model '{prefab.name}': hidden model of {v.Parts.Count} different meshes, all kept: "
                + string.Join(", ", v.Parts.Select(p => $"{p.Name} ({p.Mesh.name}, up {p.M.GetColumn(1).normalized.y:F2})")) + ".");
        }
        foreach (var part in v.Parts)
        {
            if (!part.Readable) unreadable++;
            var b = Geometry.Xform(part.M, part.Mesh.bounds);
            if (first) { v.Bounds = b; first = false; } else v.Bounds.Encapsulate(b);
        }
        if ((v.Parts.Count == 0 || v.Bounds.size.sqrMagnitude < 1e-8f) && !includeHidden) return Measure(prefab, includeHidden: true);
        if (v.Parts.Count == 0 || v.Bounds.size.sqrMagnitude < 1e-8f)
        {
            if (!StandIns.ContainsKey(prefab.name)) Plugin.Log.LogWarning($"Item model '{prefab.name}': no visible mesh; it is left out of the stores.");
            return null;
        }
        v.tight = TightOf(v, out string how);
        Plugin.Log.LogInfo($"Item model '{prefab.name}': {v.Parts.Count} mesh(es), size {v.Bounds.size:F3}, root scale {root.localScale:F3}"
            + (unreadable > 0 ? $", {unreadable} not readable (drawn per copy or instanced instead of merged)" : "")
            + (Vector3.Distance(v.Tight.size, v.Bounds.size) > 0.005f || Vector3.Distance(v.Tight.center, v.Bounds.center) > 0.005f
                ? $"; true size {v.Tight.size:F3}, centre {(v.Tight.center - v.Bounds.center) * 1000f:F0} mm off the box's ({how})" : "") + ".");
        return v;
    }

    static bool InHand(Transform t, Transform root) => Under(t, root, "equipoffset");
    static bool Under(Transform t, Transform root, string name)
    {
        for (; t && t != root; t = t.parent) if (t.name.StartsWith(name, StringComparison.OrdinalIgnoreCase)) return true;
        return false;
    }

    static Bounds TightOf(ItemVisual v, out string how)
    {
        // Its real shape, read back from the GPU (ItemPoints): the points stand in for the vertices the game won't give.
        if (v.Parts.Any(p => !p.Readable) && ItemPoints.Get(v.prefabName, v.Parts, v.Bounds) is { Length: > 0 } shape)
        {
            how = "GPU points";
            v.measured = shape;
            var t = new Bounds(shape[0], Vector3.zero);
            foreach (var p in shape) t.Encapsulate(p);
            return t;
        }
        if (v.Parts.Any(p => !p.Readable) && v.prefabName != null && ItemTightBounds.Rows.TryGetValue(v.prefabName, out var row))
        {
            var off = Vector3.Max(Abs(row.boxMin - v.Bounds.min), Abs(row.boxMax - v.Bounds.max));
            if (Mathf.Max(off.x, off.y, off.z) <= 0.002f)
            {
                how = "measured table";
                var t = new Bounds();
                t.SetMinMax(row.min, row.max);
                return t;
            }
            Plugin.Log.LogWarning($"Item model '{v.prefabName}': its box no longer matches the measured table (up to {Mathf.Max(off.x, off.y, off.z) * 1000f:F0} mm; a game update?): "
                + "measured by its vertices where readable, its box elsewhere.");
        }
        how = v.Parts.All(p => p.Readable) ? "vertices" : "vertices, box where not readable";
        bool first = true;
        var b = new Bounds();
        void Grow(Vector3 p) { if (first) { b = new Bounds(p, Vector3.zero); first = false; } else b.Encapsulate(p); }
        foreach (var part in v.Parts)
        {
            if (part.Readable) foreach (var p in part.Mesh.vertices) Grow(part.M.MultiplyPoint3x4(p));
            else
            {
                var mb = part.Mesh.bounds;
                for (int i = 0; i < 8; i++)
                    Grow(part.M.MultiplyPoint3x4(mb.center + Vector3.Scale(mb.extents, new Vector3((i & 1) == 0 ? -1 : 1, (i & 2) == 0 ? -1 : 1, (i & 4) == 0 ? -1 : 1))));
            }
        }
        return first ? v.Bounds : b;
    }
    static Vector3 Abs(Vector3 a) => new Vector3(Mathf.Abs(a.x), Mathf.Abs(a.y), Mathf.Abs(a.z));

    // The item's shape as points in turned item space at true size (root scale applied), for packing: the vertices of
    // readable meshes (at most ~600 per part), the 8 corners of the mesh box for the others. Tighter than Bounds, which is
    // the box around each part's turned box (a pie turned 15 degrees in its prefab measures 0.78 m instead of 0.57).
    public Vector3[] Points()
    {
        if (points != null) return points;
        var list = new List<Vector3>();
        if (measured != null) list.AddRange(measured);   // the measured shape of an item the game won't let us read (ItemPoints)
        else foreach (var part in Parts)
        {
            if (part.Readable)
            {
                var vs = part.Mesh.vertices;
                int step = Mathf.Max(1, vs.Length / 600);
                for (int i = 0; i < vs.Length; i += step) list.Add(part.M.MultiplyPoint3x4(vs[i]));
            }
            else
            {
                var b = part.Mesh.bounds;
                for (int i = 0; i < 8; i++)
                    list.Add(part.M.MultiplyPoint3x4(b.center + Vector3.Scale(b.extents, new Vector3((i & 1) == 0 ? -1 : 1, (i & 2) == 0 ? -1 : 1, (i & 4) == 0 ? -1 : 1))));
            }
        }
        for (int i = 0; i < list.Count; i++) list[i] = Vector3.Scale(list[i], RootScaleV);
        return points = list.ToArray();
    }
}

// What a store shows: the container's stacks in slot order, one per unit in fill order, each unit filled with copies of
// that stack's own item model (fewer for a partial stack). Checked once a second, rebuilt only when the stacks change.
// On a client that doesn't own the chest the inventory is still current: vanilla Container.CheckForChanges reloads it
// from the world data every second on everyone.
// Drawing (performance pass, 22 Oct 2026): no GameObject per copy. Readable item meshes are merged per material into a
// few meshes (Mesh.CombineMeshes). A mesh the game keeps on the GPU only (not readable: Unity refuses to give its vertices
// to scripts, so it can be neither merged nor copied into a readable mesh) keeps a list of matrices per (mesh, submesh,
// material), drawn every frame with Graphics.RenderMeshInstanced (one draw for all its copies) when the material's shader
// has an instancing variant, else with Graphics.RenderMesh per copy. DrawAll (Plugin.LateUpdate) draws only the stores
// within Contents distance, skips stores outside the camera's view (unless contents cast shadows), and draws nothing while
// Show contents is off. A store out of range rebuilds only when you come near, and at most one store rebuilds per frame.
sealed class StoreContents : MonoBehaviour
{
    // Allocation disclosure, not a claim that a mesh is identifiable from every angle.
    public int UnrepresentedKindCount { get; private set; }
    public int MoreInStorage { get; private set; }

#if !RELEASE
    static readonly HashSet<string> told = new(StringComparer.Ordinal);   // dev lines said once per content
#endif
    // Weapon racks (Joost, 25 Oct 19:14: "slight angles, a variance of angles on the weapons"), and since 27 Oct every weapon standing
    // in its own straw (Arsenal B's weapons and bows): each leans a few degrees and turns a little, the same every time for its place
    // and unlike its neighbours; half as much, or none, where it would not fit. Since Joost could not see the 4 degrees ("do I see that
    // some of these weapons are tilted? No", 27 Oct): 8-10 degrees of tilt, its direction varied per place, tried across too (where
    // the room is), then half, then a small 2.5 degrees with the turn as much smaller (W, 27 Oct: so the Bow Rack r4's skinny slots
    // lean at least a little; a full 8-degree turn alone pushed a bow's width across its slot); the fit
    // as Allocate's (StoreModel.Excess at the leaned turn). how: 3 leaning, 2 halved, 1 small, 0 upright.
    Quaternion Leaning(StoreModel.EquipPlace place, ItemVisual look, Quaternion rot, out int how)
    {
        var size = look.TrueSize;
        var p = transform.position;
        float tilt = 8f + Mathf.Abs(Jitter.Degrees(p, 3000 + place.Unit, 2f)), dir = Jitter.Degrees(p, 5000 + place.Unit, 180f);
        float yaw = Jitter.Degrees(p, 4000 + place.Unit, 8f);
        var axis = Quaternion.Euler(0f, dir, 0f) * Vector3.right;
        var steps = new[] { tilt, tilt * 0.5f, 2.5f };
        for (int n = 0; n < steps.Length; n++)
            foreach (var a in new[] { axis, Vector3.Cross(Vector3.up, axis) })
            {
                var q = Quaternion.AngleAxis(steps[n], a) * Quaternion.Euler(0f, yaw * steps[n] / tilt, 0f) * rot;   // the turn shrinks with it
                if (StoreModel.Excess(place, StoreModel.Turned(q, size), size, q) <= 0f) { how = steps.Length - n; return q; }
            }
        how = 0;
        return rot;
    }
    // An anchor with an axis straight up (within 1 degree) has no lean designed into it; one that leans by design (M's model round for
    // the Arsenal kit's Long and Bow Rack, 27 Oct) gets none from the code on top.
    // A small dip and a darker rim where an item enters its straw (Joost via M, 27 Oct): the store's entry ring at the rough straw's
    // own height, round the item's cross-section there (its points from 3 cm under the straw top to 1 cm over it, else 8 cm and 2 cm,
    // else all under it), turned with the item, at most 3 cm wider than it and shrunk to stay inside its straw object; drawn with the
    // contents, on the darker copy of the frame's material. None where the straw leaves no room round the item.
    int entryRings, toldRings = -1;
    void EntryRing(StoreModel model, int unit, ItemVisual look, Vector3 centre, Quaternion turn, Vector3 grown, Dictionary<Material, List<CombineInstance>> groups)
    {
        if (!model.StrawRing || !model.StrawRingMat || !model.StrawSurface.TryGetValue($"straw_u{unit}", out var surface) || !model.StrawTops.TryGetValue($"straw_u{unit}", out float top)) return;
        var at = Matrix4x4.Translate(centre) * Matrix4x4.Rotate(turn) * Matrix4x4.Scale(grown) * Matrix4x4.Translate(-look.Tight.center);
        var rs = look.RootScaleV;
        var all = look.Points().Select(q => at.MultiplyPoint3x4(new Vector3(q.x / rs.x, q.y / rs.y, q.z / rs.z))).ToList();   // Points carry the root scale, at too
        List<Vector3> cut = null;
        foreach (var (below, above) in new[] { (0.03f, 0.01f), (0.08f, 0.02f), (99f, 0f) })
            if ((cut = all.Where(p => p.y > top - below && p.y < top + above).ToList()).Count >= 3) break;
        if (cut.Count == 0) return;
        var ax = turn * Vector3.right;
        ax.y = 0f;
        ax = ax.sqrMagnitude < 1e-4f ? Vector3.right : ax.normalized;
        var az = new Vector3(-ax.z, 0f, ax.x);
        float a0 = cut.Min(p => Vector3.Dot(p, ax)), a1 = cut.Max(p => Vector3.Dot(p, ax)), b0 = cut.Min(p => Vector3.Dot(p, az)), b1 = cut.Max(p => Vector3.Dot(p, az));
        var mid = ax * ((a0 + a1) / 2f) + az * ((b0 + b1) / 2f);
        float ha = (a1 - a0) / 2f + 0.004f, hb = (b1 - b0) / 2f + 0.004f;
        float ox = Mathf.Min(2f * ha, ha + 0.03f), oz = Mathf.Min(2f * hb, hb + 0.03f);
        float x0 = surface.Min(p => p.x) + 0.004f, x1 = surface.Max(p => p.x) - 0.004f, z0 = surface.Min(p => p.z) + 0.004f, z1 = surface.Max(p => p.z) - 0.004f;
        float ex = Mathf.Sqrt(ox * ox * ax.x * ax.x + oz * oz * az.x * az.x), ez = Mathf.Sqrt(ox * ox * ax.z * ax.z + oz * oz * az.z * az.z);
        float k = Mathf.Min(1f, Mathf.Min(Mathf.Min((x1 - mid.x) / ex, (mid.x - x0) / ex), Mathf.Min((z1 - mid.z) / ez, (mid.z - z0) / ez)));
        if (k * Mathf.Min(ox / ha, oz / hb) < 1.15f) return;
        ox *= k;
        oz *= k;
        float h = 0f;
        int n = 0;
        for (int i = 0; i < 8; i++)
        {
            var p = mid + ax * (0.75f * ox * Mathf.Cos(i * Mathf.PI / 4f)) + az * (0.75f * oz * Mathf.Sin(i * Mathf.PI / 4f));
            if (StoreModel.StrawHeight(surface, p.x, p.z) is var y && !float.IsNaN(y)) { h += y; n++; }
        }
        if (n == 0) return;
        if (!groups.TryGetValue(model.StrawRingMat, out var list)) groups[model.StrawRingMat] = list = new List<CombineInstance>();
        list.Add(new CombineInstance { mesh = model.StrawRing, transform = Matrix4x4.TRS(new Vector3(mid.x, h / n, mid.z), Quaternion.LookRotation(az, Vector3.up), new Vector3(ox, 1f, oz)) });
        entryRings++;
    }
    // One dev line per store when its count of entry rings changes.
    void ReportRings(StoreModel model)
    {
#if !RELEASE
        if (model.StrawRing && entryRings != toldRings) Plugin.Log.LogInfo($"{model.Title}: {entryRings} entry ring(s) in its straw ({entryRings * model.StrawRing.triangles.Length / 3} triangles).");
#endif
        toldRings = entryRings;
        entryRings = 0;
    }
    // How far an item reaches above its centre as drawn (true shape, turned, at its size), and the top of a hung place's example in
    // its designed pose (piece space; null: no example to measure).
    static float Above(ItemVisual look, Quaternion rot, Vector3 grown)
    {
        var rs = look.RootScaleV;
        var c = look.Tight.center;
        float top = float.NegativeInfinity;
        foreach (var p in look.Points()) top = Mathf.Max(top, (rot * Vector3.Scale(new Vector3(p.x / rs.x, p.y / rs.y, p.z / rs.z) - c, grown)).y);
        return float.IsInfinity(top) ? Vector3.Scale(look.Tight.size, grown).y * 0.5f : top;
    }
    // How far it reaches below its centre as drawn (negative), the same way.
    static float Below(ItemVisual look, Quaternion rot, Vector3 grown)
    {
        var rs = look.RootScaleV;
        var c = look.Tight.center;
        float low = float.PositiveInfinity;
        foreach (var p in look.Points()) low = Mathf.Min(low, (rot * Vector3.Scale(new Vector3(p.x / rs.x, p.y / rs.y, p.z / rs.z) - c, grown)).y);
        return float.IsInfinity(low) ? -Vector3.Scale(look.Tight.size, grown).y * 0.5f : low;
    }
    static readonly HashSet<string> dropped = new(StringComparer.Ordinal);   // said once per store and kind
    static readonly Dictionary<StoreModel.EquipPlace, float?> tops = new();
    static float? TopOf(StoreModel.EquipPlace place)
    {
        if (tops.TryGetValue(place, out var t)) return t;
        return tops[place] = place.Pose is { } pose && place.Example != null && ItemVisual.Get(place.Example) is { } ex
            ? pose.y + Above(ex, place.Rot, ex.RootScaleV) : null;
    }
    static bool Upright(Quaternion q) => Mathf.Max(Mathf.Abs((q * Vector3.right).y), Mathf.Abs((q * Vector3.up).y), Mathf.Abs((q * Vector3.forward).y)) > 0.99985f;
    // The underside of the floor a place stands on: the highest frame surface straight below its support point (Arsenal B r4: the
    // plank from 0.15 down to 0.095 m, open below it). NaN: nothing below, or the frame is not readable. Once per place and model load.
    static readonly Dictionary<StoreModel.EquipPlace, float> floors = new();
    static float FloorUnder(StoreModel model, StoreModel.EquipPlace place)
    {
        if (floors.TryGetValue(place, out float under)) return under;
        under = float.NaN;
        if (place.Bottom is { } foot && model.Frame && model.Frame.isReadable)
        {
            var v = model.Frame.vertices;
            var t = model.Frame.triangles;
            for (int k = 0; k + 2 < t.Length; k += 3)
            {
                Vector3 a = v[t[k]], b = v[t[k + 1]], c = v[t[k + 2]];
                float det = (b.z - c.z) * (a.x - c.x) + (c.x - b.x) * (a.z - c.z);
                if (Mathf.Abs(det) < 1e-9f) continue;   // a wall: seen edge-on from above
                float l1 = ((b.z - c.z) * (foot.x - c.x) + (c.x - b.x) * (foot.z - c.z)) / det, l2 = ((c.z - a.z) * (foot.x - c.x) + (a.x - c.x) * (foot.z - c.z)) / det;
                if (l1 < 0f || l2 < 0f || l1 + l2 > 1f) continue;
                float y = l1 * a.y + l2 * b.y + (1f - l1 - l2) * c.y;
                if (y < foot.y - 0.005f && (float.IsNaN(under) || y > under)) under = y;
            }
        }
        return floors[place] = under;
    }
#if !RELEASE
    string lastBayLine, lastFiguresLine, lastUnshownLine, lastUndrawnLine, lastCellsLine;
#endif
#if !RELEASE
    static readonly HashSet<string> loggedForms = new(StringComparer.Ordinal);
    string lastHolderLine;
#endif   // worn-armor stores: pieces no form or peg shows
    sealed class Batch
    {
        public Mesh Mesh;
        public int Sub;
        public Material Mat, Inst;          // Inst: Mat with instancing on; null when its shader has no instancing variant
        public bool Merged;                 // our own merged mesh in store space (destroyed with the batch)
        public UnityEngine.Rendering.ShadowCastingMode Shadows;
        public bool Receive;
        public UnityEngine.Rendering.LightProbeUsage Probes;
        public UnityEngine.Rendering.ReflectionProbeUsage Reflections;
        public readonly List<Matrix4x4> Local = new();   // loose: one per copy, store space
        public Matrix4x4[] World;                       // loose: Local in world space, refreshed when the store moves
        public Bounds LocalBounds, WorldBounds;
        public int Tris;                    // triangles per copy (merged: of the whole mesh)
    }

    const int MaxPerDraw = 1023;
    static readonly List<StoreContents> live = new();
    static readonly Dictionary<Material, Material> instanced = new();
    static int rebuiltFrame = -1;

    StoreModel model;
    Container container;
    int shownHash, shownVersion = -1, copiesShown;
    public int CopiesShown => copiesShown;
    public Bounds WorldBounds { get { Refresh(); return worldBounds; } }
    public long TrianglesShown { get; private set; }   // near set, after the last rebuild (merged, and loose per copy)
    float next;
    readonly List<Batch> batches = new();
    readonly List<Batch> farBatches = new();   // the same store with the items' far models; empty when no item has one
    // While a store rebuilds: the item copies' far parts, and which near entries were item copies (so the far set keeps the
    // rest: liquids, vessels, panels, cords, boards).
    static Dictionary<Material, List<CombineInstance>> farItems;
    static readonly List<Mesh> scratch = new();   // the Ossuary's merged pile meshes, for one rebuild
    static readonly List<(Material, Mesh)> blended = new();   // the Ossuary's blended copies (GhostSkull), one mesh each, for one rebuild
    static Dictionary<(Mesh, int, Material), Batch> farLoose;
    static Dictionary<Material, HashSet<int>> nearItemIdx;
    static bool anyFar;
    Bounds localBounds, worldBounds;
    Matrix4x4 root;
    bool rootValid;

    void OnEnable() => live.Add(this);
    void OnDisable() => live.Remove(this);

    void Start()
    {
        model = StoreModel.ForVis(name);
        container = GetComponentInParent<Container>();
        if (!container && transform.parent) container = transform.parent.GetComponentInChildren<Container>();
        if (model == null || !container) { enabled = false; return; }
        next = Time.time + UnityEngine.Random.value;   // spread the checks of many stores over the second
    }

    void Update()
    {
        if (Time.time < next) return;
        long t0 = System.Diagnostics.Stopwatch.GetTimestamp();
        try { Check(); }
        finally { Perf.Add(t0); }
    }

    void Check()
    {
        next = Time.time + 1f;
        SyncArms();
        var inv = container ? container.GetInventory() : null;
        if (inv == null || !model.Ready) return;
        int hash = Hash(inv);
        if (hash == shownHash && model.Version == shownVersion) return;
        // Contents off or the store out of range: rebuild once it matters (a base's stores then rebuild as you walk in).
        if (!Settings.ShowContents.Value || !Near()) return;
        // At most one rebuild per frame over all stores (a base loading in, a model reload): the others try next frame.
        if (rebuiltFrame == Time.frameCount) { next = Time.time; return; }
        rebuiltFrame = Time.frameCount;
        shownHash = hash;
        shownVersion = model.Version;
        try { Rebuild(inv); }
        catch (Exception e) { Plugin.Log.LogError($"{model.Title}: contents not shown ({e})"); }
        SyncArms();
    }

    // A figure's carved arms and fists (the piece's "arms<figure>") would hide while covered[figure]; nothing covers them now. They hid
    // under a worn chest while they were carved in the calm poses (the fists poked through the clothes); in the vanilla pose they lie
    // under the sleeves, and see-through chests showed figures without arms (Joost, 27 Oct: "keep the arms on"). Drawn means drawn
    // now, as DrawAll draws: contents on, built, in range.
    bool[] covered;
    void SyncArms()
    {
        if (model?.Forms == null) return;
        var cam = covered != null && batches.Count > 0 && Settings.ShowContents.Value ? global::Utils.GetMainCamera() : null;
        float d = Settings.ContentsDistance.Value;
        bool shown = cam && WorldBounds.SqrDistance(cam.transform.position) <= d * d;
        for (int f = 0; f < model.Forms.Count; f++)
            if (transform.Find("arms" + f) is { } part && part.GetComponent<Renderer>() is { } r)
            {
                bool want = !(shown && f < covered.Length && covered[f]);
                if (r.enabled != want) r.enabled = want;
            }
    }

    bool Near()
    {
        var cam = global::Utils.GetMainCamera();
        if (!cam) return true;
        float d = Settings.ContentsDistance.Value + 5f;   // + about a store's size, so it is ready when it comes into range
        return (cam.transform.position - transform.position).sqrMagnitude <= d * d;
    }

    static int Hash(Inventory inv)
    {
        unchecked
        {
            int h = inv.GetWidth() * 31 + inv.GetHeight();
            foreach (var it in inv.GetAllItems())
                h = ((h * 31 + (it.m_shared?.m_name?.GetHashCode() ?? 0)) * 31 + it.m_stack) * 31 + it.m_gridPos.x * 97 + it.m_gridPos.y;
            return h;
        }
    }

    void Rebuild(Inventory inv)
    {
        long t0 = System.Diagnostics.Stopwatch.GetTimestamp();
        Clear();
#if !RELEASE
        seenInto = Seen;
        seenInto?.Copies.Clear();
        seenInto?.Extras.Clear();
        At("copy", 0);
#endif
        UnrepresentedKindCount = 0;
        int w = Mathf.Max(1, inv.GetWidth());
        var items = inv.GetAllItems().Where(i => i?.m_shared != null).OrderBy(i => i.m_gridPos.y * w + i.m_gridPos.x).ToList();
        var groups = new Dictionary<Material, List<CombineInstance>>();
        farItems = new Dictionary<Material, List<CombineInstance>>();
        farLoose = new Dictionary<(Mesh, int, Material), Batch>();
        nearItemIdx = new Dictionary<Material, HashSet<int>>();
        anyFar = false;
        var loose = new Dictionary<(Mesh, int, Material), Batch>();
        int stacks = 0, copies = 0, looseCopies = 0;
        bool display = model.Display;
        if (model.Planks.Count > 0)
        {
            // Packed shelf: one item per stack, along the planks; what fits nowhere isn't shown.
            var placed = Packing.Pack(model.Planks, items.Select(it => ItemVisual.Get(it.m_dropPrefab)).ToList(),
                Packing.Planks(items.Select(it => it.m_gridPos.y * w + it.m_gridPos.x), w * Mathf.Max(1, inv.GetHeight()), model.Planks.Count),
                Settings.DisplaySize.Value);
            for (int i = 0; i < placed.Count; i++)
            {
                if (placed[i] is not { } at) continue;
                stacks++;
                copies++;
                At("stack", i);
                var shelfLook = ItemVisual.Get(items[i].m_dropPrefab);
                if (shelfLook != null) at = Jitter.Turn(at, shelfLook.Bounds, Jitter.Degrees(transform.position, i, 6f));
                looseCopies += Add(shelfLook, at, groups, loose);
            }
            UnrepresentedKindCount = StorageReviewPolicy.UnrepresentedKinds(
                items.Select(it => it.m_dropPrefab ? it.m_dropPrefab.name : it.m_shared.m_name).ToList(),
                placed.Select(p => p.HasValue ? 0 : -1).ToList(), placed.Count);
        }
        // The units style (every store not drawn by planks, forms, cells, piles or equipment places): which stack goes on which unit, how
        // many copies, which crop heap, liquid, label, vessel, band and board is decided by a plan in plain numbers (UnitPlan, DisplayPlan.cs);
        // the drawing below turns it into matrices from the items' real bounds.
        var plan = new UnitPlan();
        if (model.Planks.Count == 0 && model.Forms == null && model.Cells == null && model.Piles == null && model.Equip == null)
        {
            var rows = inv.GetAllItems().Where(i => i?.m_shared != null).ToList();
            var input = PlanInputs(inv, rows);
#if !RELEASE
            if (Recording != null) input.Record();   // the capture keeps every fact the plan asks for, for planrun
#endif
            plan = UnitPlan.Make(input);
            model.Apply(plan.State);
            items = plan.Items.Select(r => rows[r]).ToList();
            UnrepresentedKindCount = plan.Unseen;
#if !RELEASE
            if (plan.BayLine != null && plan.BayLine != lastBayLine) { lastBayLine = plan.BayLine; Plugin.Log.LogInfo(plan.BayLine); }
            if (Recording != null) RecordedPlan = (UnitPlan.InputsJson(input), plan.ToJson());
#endif
        }
        else
        {
            // The other styles count the stacks as the units style would (Cells' and Piles' "stacks of items" in the rebuild line).
            int perStack = model.Mirror || model.Heap || model.Planks.Count > 0 || model.Places.Count > 0 ? 1 : model.Units.Count / Mathf.Max(1, w * Mathf.Max(1, inv.GetHeight()));
            if (perStack > 1) items = items.SelectMany(it => Enumerable.Repeat(it, perStack)).ToList();
            int slots = w * Mathf.Max(1, inv.GetHeight());
            if (perStack <= 1 && !model.Mirror && !model.Heap && model.Planks.Count == 0 && model.Places.Count == 0 && model.Equip == null && model.Cells == null && model.Forms == null && model.Units.Count > 0 && slots > model.Units.Count)
                items = UnitPlan.StockSample(items, model.Units.Count, slots, it => it.m_dropPrefab ? it.m_dropPrefab.name : it.m_shared.m_name)
                    .OrderBy(it => it.m_gridPos.y * w + it.m_gridPos.x).ToList();
        }
        var hung = new List<Matrix4x4>();
        // Broad heaps (Ossuary r4): the layouts' own recipe decides which heap each kind lies in and how much of it shows.
        // A's display cells (Fletcher's Barrels r3): the reference selector picks saved copies by stock; each is drawn by its native root
        // transform as saved (no centring, fit or size). Repeats are the layout's to avoid (each holder its own settle), never a turn here.
        // Worn armor: Outfits decides who wears what; each piece is drawn as the game would show it worn on the stand's posed body,
        // baked once per item and pose (MannequinBaker), on the form's spot and turn. Spares lie or hang as their own model.
        if (model.Forms != null)
        {
            Outfits.LoadMap(StoreModel.AssetPath("armory_outfits.json"), n => ObjectDB.instance && ObjectDB.instance.GetItemPrefab(n));
            var gear = inv.GetAllItems().Where(it => it?.m_shared != null && it.m_dropPrefab).ToList();
            int figures = Mannequins.Figures(model, inv.GetWidth());   // the window is the mannequins: column f is worn by figure f
            var dressed = Outfits.FromGrid(Mannequins.Pieces(gear), figures, model.Spares.Select(x => x.Slot).ToList());
#if !RELEASE
            if (MannequinBaker.Baked > 0 && loggedForms.Add(model.Title))
                Plugin.Log.LogInfo($"{model.Title}: figures (piece space) " + string.Join(", ", model.Forms.Take(figures).Select(f => $"{f.Pos:F2} yaw {f.Yaw:F0} facing {(f.Facing > 0 ? "+z" : "-z")}{(f.Back ? " back" : "")} pose {f.Pose}"))
                    + $"; extra turn {Settings.MannequinTurn.Value:F0}");
#endif
            float extra = Settings.MannequinTurn.Value;
            covered = new bool[model.Forms.Count];
            int emptyBakes = 0;   // worn by the rules, yet nothing to draw: counted with the pieces not worn (rule 9)
#if !RELEASE
            var report = new List<string>();
#endif
            for (int f = 0; f < figures; f++)
            {
                var form = model.Forms[f];
                // The set's measured forward turned onto the side the figure faces (+z or -z), plus the anchor's own few degrees.
                MannequinBaker.Ensure();
                var fwd = MannequinBaker.Forward;
                float turn = Mathf.Atan2(0f, form.Facing) * Mathf.Rad2Deg - Mathf.Atan2(fwd.x, fwd.z) * Mathf.Rad2Deg
                    + Mathf.DeltaAngle(Mathf.Round(form.Yaw / 180f) * 180f, form.Yaw) + extra;
                var at = Matrix4x4.TRS(form.Pos, Quaternion.Euler(0f, turn, 0f), Vector3.one);
#if !RELEASE
                var drawn = new List<string>();
                var missed = new List<string>();
#endif
                foreach (var kv in dressed.Forms[f])
                    if (MannequinBaker.Get(gear[kv.Value.Index].m_dropPrefab, form.Pose, kv.Key) is { } worn)
                    {
                        At("figure", f + 1, kv.Value.Prefab);   // a worn bake has no prefab name of its own
                        copies++;
                        looseCopies += Add(worn, at, groups, loose);
#if !RELEASE
                        drawn.Add($"{kv.Key.ToString().ToLowerInvariant()} {kv.Value.Prefab}");
#endif
                    }
                    else
                    {
                        emptyBakes++;
#if !RELEASE
                        missed.Add($"{kv.Value.Prefab} (its worn model baked empty: no attach the stand has)");
#endif
                    }
#if !RELEASE
                foreach (var p in dressed.Unseen.Where(p => p.Y == f))
                    missed.Add($"{p.Prefab} ({(!p.Wearable ? "not wearable: no attach children" : p.Slot == Outfits.Slot.None ? "no slot on a figure" : $"second {p.Slot.ToString().ToLowerInvariant()} in the column")})");
                var worldFwd = transform.rotation * (Quaternion.Euler(0f, turn, 0f) * fwd);
                var worldOpen = transform.rotation * new Vector3(0f, 0f, form.Facing);
                var toPlayer = Player.m_localPlayer ? Vector3.ProjectOnPlane(Player.m_localPlayer.transform.position - transform.TransformPoint(form.Pos), Vector3.up).normalized : Vector3.zero;
                report.Add($"{model.Title} mannequin {f + 1} (column {f + 1}, {(form.Back ? "back" : "front")}, x {form.Pos.x:F2}, faces {(form.Facing > 0 ? "+z" : "-z")}, turn {turn:F0}; "
                    + $"forward . open side {Vector3.Dot(worldFwd, worldOpen):F2}, forward . to player {Vector3.Dot(worldFwd, toPlayer):F2}; forward from {MannequinBaker.ForwardFrom}): drawn {(drawn.Count > 0 ? string.Join(", ", drawn) : "nothing")}"
                    + (missed.Count > 0 ? $"; not drawn: {string.Join(", ", missed)}" : ""));
#endif
            }
#if !RELEASE
            string figuresLine = string.Join("\n  ", report);
            if (figuresLine != lastFiguresLine) { lastFiguresLine = figuresLine; Plugin.Log.LogInfo("Mannequins:\n  " + figuresLine); }
#endif
            for (int k = 0; k < dressed.Spares.Count; k++)
                if (dressed.Spares[k] is { } spare && ItemVisual.Get(gear[spare.Index].m_dropPrefab) is { } spareLook)
                {
                    var b = spareLook.Bounds;
                    var at = Matrix4x4.TRS(model.Spares[k].Pos, model.Spares[k].Rot, spareLook.RootScaleV) * Matrix4x4.Translate(-new Vector3(b.center.x, b.min.y, b.center.z));
                    At("spare", k);
                    copies++;
                    looseCopies += Add(spareLook, at, groups, loose);
                }
            stacks = gear.Count;
            UnrepresentedKindCount = 0;
            MoreInStorage = dressed.Unseen.Count + emptyBakes;
            if (MannequinBaker.Baked > 0) Plugin.Log.LogInfo($"{model.Title}: {MannequinBaker.Baked} worn piece(s) baked so far in {MannequinBaker.BakeMs:F0} ms.");
        }
        if (model.Cells != null)
        {
            var stock = new Dictionary<string, float>(StringComparer.Ordinal);
            foreach (var it in inv.GetAllItems().Where(it => it?.m_shared != null))
            {
                string kind = it.m_dropPrefab ? it.m_dropPrefab.name : it.m_shared.m_name;
                stock.TryGetValue(kind, out float s0);
                stock[kind] = s0 + it.m_stack / (float)Mathf.Max(1, it.m_shared.m_maxStackSize);
            }
            var chosen = model.Cells.Allocate(stock, w * Mathf.Max(1, inv.GetHeight()), out int cellsUnseen);
            var noModel = new List<string>();
            foreach (var c in chosen)
            {
                if (ItemVisual.Get(c.Item) is not { } cellLook) { noModel.Add(c.Item); continue; }
                var at = Matrix4x4.TRS(c.Pos, c.Rot, Vector3.one * c.Scale);
                At("holder", c.Holder);
                copies++;
                looseCopies += Add(cellLook, at, groups, loose);
#if !RELEASE
                if (model.StrawTops.Count > 0 && Ammo.Top(model, $"straw_g{c.Holder}") is var cellTop && !float.IsNaN(cellTop))
                    Ammo.Note(model, c.Item, Geometry.Xform(at, cellLook.Bounds), cellTop);
#endif
            }
            stacks = items.Count;
            UnrepresentedKindCount = cellsUnseen;
#if !RELEASE
            Ammo.Report(model);
#endif
#if !RELEASE
            // The coordinator, 25 Oct (Fletcher's r3b: game = harness?): per holder the kinds and copies drawn, the kinds without a
            // copy, and the stock itself as JSON in BepInEx/cache, once per change of contents.
            var perHolder = chosen.GroupBy(c => c.Holder).OrderBy(g => g.Key)
                .Select(g => $"holder {g.Key}: " + string.Join(" + ", g.GroupBy(c => c.Item).Select(k => $"{k.Key} x{k.Count()}")));
            var without = stock.Keys.Where(k => chosen.All(c => c.Item != k)).OrderBy(k => k, StringComparer.Ordinal).ToList();
            string cellsLine = $"{model.Title}: cells drawn {chosen.Count - noModel.Count} of {chosen.Count} chosen for {stock.Count} kind(s); {string.Join("; ", perHolder)}"
                + $"; no copy: {(without.Count > 0 ? string.Join(", ", without) : "none")}" + (noModel.Count > 0 ? $"; no item model: {string.Join(", ", noModel.Distinct())}" : "");
            if (cellsLine != lastCellsLine)
            {
                lastCellsLine = cellsLine;
                Plugin.Log.LogInfo(cellsLine);
                try
                {
                    var stacksJson = inv.GetAllItems().Where(it => it?.m_shared != null).OrderBy(it => it.m_gridPos.y).ThenBy(it => it.m_gridPos.x)
                        .Select(it => $"  {{\"prefab\": \"{(it.m_dropPrefab ? it.m_dropPrefab.name : it.m_shared.m_name)}\", \"stack\": {it.m_stack}, \"max\": {it.m_shared.m_maxStackSize}, \"x\": {it.m_gridPos.x}, \"y\": {it.m_gridPos.y}}}");
                    var dump = Path.Combine(BepInEx.Paths.CachePath, $"Storehouse-{model.Slug}-stock.json");
                    File.WriteAllText(dump, "[\n" + string.Join(",\n", stacksJson) + "\n]\n");
                    Plugin.Log.LogInfo($"{model.Title}: stock written to {dump}.");
                }
                catch (Exception e) { Plugin.Log.LogWarning($"{model.Title}: stock not written ({e.Message})."); }
            }
#endif
        }
        if (model.Piles != null)
        {
            var mass = new Dictionary<string, float>(StringComparer.Ordinal);
            foreach (var it in inv.GetAllItems().Where(it => it?.m_shared != null))
            {
                string kind = it.m_dropPrefab ? it.m_dropPrefab.name : it.m_shared.m_name;
                mass.TryGetValue(kind, out float m0);
                mass[kind] = m0 + Mathf.Clamp01(it.m_stack / (float)Mathf.Max(1, it.m_shared.m_maxStackSize));
            }
            float pileGrow = model.Kind?.ItemSize?.Value ?? 1f;
            var shown = model.Piles.Select(mass, w * Mathf.Max(1, inv.GetHeight()), out int unseen);
            var merged = new Dictionary<Material, PileDisplay.Builder>();
            PileDisplay.Report report = null;
            var pileFaces = model.PileLook?.Faces(shown, model.Piles.FrameTris, out report);
            for (int i = 0; i < shown.Count; i++)
            {
                var c = shown[i];
                if (ItemVisual.Get(c.Item) is not { } pileLook) continue;
                copies++;
                // From the display sidecar's native mesh (bounds-centred already): its selected faces, merged per material; a blended
                // material (GhostSkull) one mesh per copy, so the copies sort among themselves.
                if (model.PileLook != null && model.PileLook.Meshes.TryGetValue(c.Item, out var native) && model.PileLook.GameMaterial(c.Item, native, pileLook) is { } gameMat)
                {
                    var selected = pileFaces[i];
                    if (selected != null && selected.Length == 0) continue;   // no face of it is seen from any protected view
                    var at = Matrix4x4.TRS(c.Pos, c.Rot, Vector3.one * (c.Longest / Mathf.Max(1e-4f, native.TemplateLongest) * pileGrow));
                    if (gameMat.renderQueue >= 3000)
                    {
                        var one = new PileDisplay.Builder();
                        one.Add(native, at, c.Rot, selected);
                        blended.Add((gameMat, one.Mesh("storehouse_pile_" + c.Item)));
                        continue;
                    }
                    if (!merged.TryGetValue(gameMat, out var builder)) merged[gameMat] = builder = new PileDisplay.Builder();
                    builder.Add(native, at, c.Rot, selected);
                    continue;
                }
                var size = pileLook.Bounds.size;
                At("pile", i);
                float sc = c.Longest / Mathf.Max(1e-4f, Mathf.Max(size.x, Mathf.Max(size.y, size.z))) * pileGrow;
                looseCopies += Add(pileLook, Matrix4x4.TRS(c.Pos - c.Rot * (sc * pileLook.Bounds.center), c.Rot, Vector3.one * sc), groups, loose);
            }
            if (report != null)
                Plugin.Log.LogInfo($"{model.Title}: display {report.Total} triangles (frame {model.Piles.FrameTris}), {report.Copies} copies, {report.Hidden} hidden, "
                    + $"{report.Whole} whole, {report.Dropped} extra-angle faces left out" + (report.Mandatory > PileDisplay.Budget
                        ? $"; protected faces {report.Mandatory} over the budget of {PileDisplay.Budget}, all kept." : $" (budget {PileDisplay.Budget})."));
            foreach (var kv in merged)
            {
                var mesh = kv.Value.Mesh("storehouse_pile_" + kv.Key.name);
                scratch.Add(mesh);
                if (!groups.TryGetValue(kv.Key, out var list)) groups[kv.Key] = list = new List<CombineInstance>();
                list.Add(new CombineInstance { mesh = mesh, transform = Matrix4x4.identity });
            }
            stacks = items.Count;
            UnrepresentedKindCount = unseen;
        }
        // Equipment: each real item at its true size (its prefab's own scale; no display size, no Item size, never shrunk to fit),
        // turned as its place says, resting on the place's support. What has no fitting place stays in the chest.
        if (model.Equip != null)
        {
            var gear = inv.GetAllItems().Where(it => it?.m_shared != null && it.m_dropPrefab).ToList();
            var notes = new List<string>();
            // The placement the window's hints and the drop asked of these contents, solved once (StoreModel.Basis).
            var at = model.Basis(inv, gear).Final(out var turns, out var scales, notes);
#if DEV
            if (Settings.PlacementCheck?.Value == true)
            {
                var slow = model.Solve(gear, EquipFit.TrueSize, g => TypedSlots.ClassOf(model, inv, g), keep: false, scan: true).Final(out _, out var slowScales);
                if (!at.SequenceEqual(slow) || !scales.SequenceEqual(slowScales))
                    Plugin.Log.LogWarning($"Placement self-check: {model.Title}: drawn placement differs: replay [{string.Join(" ", at)}], from scratch [{string.Join(" ", slow)}].");
            }
#endif
            var columnTop = new Dictionary<Vector3Int, float>();   // the top of what lies in each stacked column so far
            var shown = Enumerable.Repeat(-1, gear.Count).ToArray();   // per stack the place it is drawn at: allocated and not dropped below
            var leans = new int[4];   // upright (no room), small, halved, leaning
            int designed = 0;         // examples in their own kit place's designed pose
            int holders = 0;          // pegs under the Spine's contacts (Holders)
            var oneArm = new List<string>();   // drawn copies a pose table rests on one arm only
            // Once per change of contents, while the places are new (Joost's first test tells whether the size slack is right).
            if (notes.Count > 0) Plugin.Log.LogInfo($"{model.Title}: equipment places\n  " + string.Join("\n  ", notes));
            foreach (int i in Enumerable.Range(0, gear.Count).Where(i => at[i] >= 0).OrderBy(i => model.Equip[at[i]].Layer))
            {
                if (ItemVisual.Get(gear[i].m_dropPrefab) is not { } look) continue;
                var place = model.Equip[at[i]];
                At("place", place.Unit);   // the place number the equipment notes use
                var rot = turns[i];   // the place's turn, or the one the item fits in (StoreModel.Turns)
                // Standing in straw (Joost, 27 Oct: a slight random lean for the weapons standing in straw, Arsenal B and the weapon
                // racks): every place with its own straw object, and the racks' places, unless the anchor leans by design; not what is
                // drawn smaller (it fits nowhere at true size, so no room to lean).
                bool inStraw = model.StrawTops.TryGetValue($"straw_u{place.Unit}", out float ownStraw);
                // The Bow Rack r4's upright slots too (Joost, 27 Oct, r4 the default again: its bows with the code lean).
                // Not where the kit's designed pose takes it (below): the Bow Rack's random lean tangled six bows (Joost, 27 Oct).
                if ((inStraw || model.Kind?.Slug is "weaponrack" or "weaponrackb") && Upright(place.Rot) && scales[i] >= 1f && !(place.Pose != null && place.HangY == null))
                {
                    rot = Leaning(place, look, rot, out int how);
                    leans[how]++;
                }
                var grown = look.RootScaleV * scales[i];   // drawn smaller only where no place of its type takes its true size
                var d = StoreModel.Turned(rot, Vector3.Scale(look.Tight.size, grown));
                // Its own place, as designed (the models session, 27 Oct: the Spine's, Long Rack's and Shield Trough's poses hang and
                // lean by design, and the export's position is where the example's true centre stands): the example itself, at true
                // size and the place's own turn, goes exactly there, with no support, planting, lean or jitter on top. Sol's root
                // matrices for all 86 places of Spine r5, Long Rack r5, Bow Rack r5 and Shield Trough r3b equal this to 0.07 mm. The
                // Spine's hang straight down (d38eddeb3 left upright anchors out, and Joost saw them float). A copy the code leaned (the
                // Bow Rack r4) keeps its lean; any other item at a kit place keeps the rules below.
                // Any item that fits a standing or leaning kit place at its own turn takes that place's pose too, about its own true
                // centre (the models session, 27 Oct: the Bow Rack's places were designed 8-11 cm apart, and six of Joost's eight bows
                // were not their place's example; they tangled under the place rules and the random lean). Hung places keep the rule
                // below for other items: a centre on the example's would leave a short weapon off the arms.
                // A pose table's row (StoreModel.PoseTable): exactly as Sol placed and checked it on the real frame and item.
                if (model.Table?.Get(place.Unit, gear[i].m_dropPrefab.name) is { Fit: true } row && scales[i] >= 1f)
                {
                    copies++;
                    shown[i] = at[i];
                    designed++;
#if !RELEASE
                    if ((look.Tight.center - row.Centre).sqrMagnitude > 0.002f * 0.002f && StoreModel.TableCentres.Add(model.Key + "|" + gear[i].m_dropPrefab.name))
                        Plugin.Log.LogWarning($"{model.Title}: {gear[i].m_dropPrefab.name}'s true centre is {(look.Tight.center - row.Centre).magnitude * 1000f:F1} mm from the pose table's (a game update?); drawn as the table says.");
#endif
                    looseCopies += Add(look, Matrix4x4.Translate(row.Pivot) * Matrix4x4.Rotate(row.Rot) * Matrix4x4.Scale(grown) * Matrix4x4.Translate(-row.Centre), groups, loose);
                    if (row.Contacts is { Length: > 0 } contacts)
                    {
                        holders += Holders.Add(model, contacts, groups);
                        if (contacts.Length == 1) oneArm.Add($"{gear[i].m_dropPrefab.name} at {place.Unit}");
                    }
                    continue;
                }
                if (place.Pose is { } pose && scales[i] >= 1f && rot == place.Rot && (gear[i].m_dropPrefab.name == place.Example || place.HangY == null))
                {
                    // Another item than the example, standing: straight down until its lowest true point rests on the place's floor
                    // (the example's bottom), its lean kept; never up (Joost, 27 Oct: a small buckler floated above the Shield
                    // Trough's floor in a giant's pose).
                    // Not in the Shield Trough: its leaning shields lean over their neighbours' places, and a dropped one went into
                    // its neighbour (Joost, 27 Oct); its non-examples keep the designed pose until its own pose table.
                    if (place.HangY == null && gear[i].m_dropPrefab.name != place.Example && model.Kind?.Slug != "arsenalkit_shield" && place.Bottom is { } floorAt
                        && pose.y + Below(look, rot, grown) - floorAt.y is float gap && gap > 0.001f)
                    {
                        pose.y -= gap;
#if !RELEASE
                        if (dropped.Add(model.Key + "|" + gear[i].m_dropPrefab.name + "|" + place.Unit))
                            Plugin.Log.LogInfo($"{model.Title}: {gear[i].m_dropPrefab.name} at place {place.Unit} lowered {gap * 1000f:F0} mm onto the place's floor (its pose is {place.Example}'s).");
#endif
                    }
                    copies++;
                    shown[i] = at[i];
                    designed++;
                    looseCopies += Add(look, Matrix4x4.Translate(pose) * Matrix4x4.Rotate(rot) * Matrix4x4.Scale(grown) * Matrix4x4.Translate(-look.Tight.center), groups, loose);
                    continue;
                }
                // Every place holds its item from below: on the support point the export gives, else on the bottom of the place's
                // box (the export's position is the demo item's centre; another item's centre there floats or sinks, Joost's test:
                // axes hanging above their sockets).
                // Hung (the Arsenal kit's spine): resting on the arm tops at the same share of its height as the place's example.
                var centre = place.HangY is { } hang ? new Vector3(place.Pos.x, hang + (0.5f - place.HangAt) * d.y, place.Pos.z)
                    : place.Bottom is { } b ? b + Vector3.up * (d.y * 0.5f) : place.OnBottom ? place.Pos + Vector3.up * (d.y * 0.5f)
                    : place.Pos + Vector3.up * ((d.y - place.Box.y) * 0.5f);
                // Hung, another item than the example (Joost, 27 Oct: "they're all just hanging floating in midair"): from the example's
                // own top, at its designed centre line. A sword's grip, an axe's or mace's head is at the top, and that is what the arms
                // or the peg hold; the share-of-height rule above put a guardless axe beside its peg. The shapes are real now (vertices,
                // or ItemPoints for the meshes the game won't give).
                if (place.HangY != null && place.Pose is { } line && rot * Vector3.up is var up && Mathf.Abs(up.y) > 0.98f
                    && TopOf(place) is float exampleTop)
                    centre = new Vector3(line.x, exampleTop - Above(look, rot, grown), line.z);
                // Planted, and seen. What stands on its floor under its own straw keeps 30-40% of its height under the straw top:
                // - at least 30% under (Joost, 25 Oct 19:17; 27 Oct: Arsenal B's atgeirs stood 22-25% deep): down, at most to 1 cm above
                //   the underside of that floor, so nothing shows below the frame (a tall one then stays shallower);
                // - at least 60% above (M, 27 Oct: StaffSkeleton and StaffSpiritCaller, 0.4 m, were 100% under): up, held by the straw.
                // The second is applied last and wins where both cannot hold, since an unseen item is worse than a shallow one.
                if (inStraw && place.HangY == null && place.Bottom is { } foot)
                {
                    float lowest = FloorUnder(model, place) is var floor && !float.IsNaN(floor) ? Mathf.Min(foot.y, floor + 0.01f) : foot.y;
                    float bottom = Mathf.Max(lowest, Mathf.Min(foot.y, ownStraw - 0.3f * d.y));
                    bottom = Mathf.Max(bottom, ownStraw - 0.4f * d.y);
                    centre.y += bottom - foot.y;
                }
                if (place.Layer > 0 || columnTop.ContainsKey(place.Column))
                {
                    // On what lies below, never at the same base (Joost's test: stacked armor z-fighting), and not above the column.
                    // Exactly on the true top of the copy below: no gap, no overlap (+1 mm against z-fighting).
                    float bottom = (columnTop.TryGetValue(place.Column, out float top) ? top : place.Pos.y - (place.ExplicitLayer ? 0f : place.Box.y * 0.5f)) + 0.001f;
                    if (bottom + d.y > (place.FixedCeiling ?? place.StackTop + 0.01f)) continue;
                    centre.y = bottom + d.y * 0.5f;
                }
                columnTop[place.Column] = centre.y + d.y * 0.5f;
                float yaw = Jitter.Degrees(transform.position, 2000 + place.Unit, place.Layer > 0 || place.OnBottom ? 5f : 3f);   // folded piles a little more
                copies++;
                shown[i] = at[i];
                looseCopies += Add(look, Matrix4x4.Translate(centre) * Matrix4x4.Rotate(Quaternion.Euler(0f, yaw, 0f) * rot) * Matrix4x4.Scale(grown) * Matrix4x4.Translate(-look.Tight.center), groups, loose);
                if (inStraw) EntryRing(model, place.Unit, look, centre, Quaternion.Euler(0f, yaw, 0f) * rot, grown, groups);
#if !RELEASE
                if (model.StrawTops.Count > 0 && Ammo.Top(model, $"straw_u{place.Unit}") is var strawTop && !float.IsNaN(strawTop))
                    Ammo.Note(model, gear[i].m_dropPrefab.name, new Bounds(centre, d), strawTop);
#endif
            }
            // Shown is what is drawn (W, 27 Oct: Arsenal B read "32 stack(s) of 32 shown" with 28 copies): a stack with no place, or
            // whose copy is dropped above (no model, over its column's ceiling), stays in the chest unseen; held = shown + unseen.
            stacks = shown.Count(k => k >= 0);
            UnrepresentedKindCount = StorageReviewPolicy.UnrepresentedKinds(gear.Select(it => it.m_dropPrefab.name).ToList(), shown.ToList(), gear.Count);
#if !RELEASE
            // How many rest on a single arm (Joost via M, 27 Oct: "one of the weapons is held up by one of those black things rather
            // than two"; a peg alone won't sell that).
            string holderLine = holders > 0 ? $"{model.Title}: {holders} holder(s) under the arms the weapons rest on; on one arm only: {oneArm.Count}"
                + (oneArm.Count > 0 ? $" ({string.Join(", ", oneArm)})" : "") + "." : null;
            if (holderLine != null && holderLine != lastHolderLine) { lastHolderLine = holderLine; Plugin.Log.LogInfo(holderLine); }
#endif
#if !RELEASE
            Ammo.Report(model);
            if (gear.Count > stacks && told.Add($"{model.Title}|unseen|{string.Join(",", Enumerable.Range(0, gear.Count).Where(i => shown[i] < 0).Select(i => gear[i].m_dropPrefab.name))}"))
                Plugin.Log.LogInfo($"{model.Title}: {gear.Count} held, {stacks} shown, {gear.Count - stacks} unseen ({string.Join(", ", Enumerable.Range(0, gear.Count).Where(i => shown[i] < 0)
                    .Select(i => gear[i].m_dropPrefab.name + (at[i] < 0 ? "" : ", dropped at its place")))}).");
            if (leans.Sum() > 0 && told.Add($"{model.Title}|lean|{string.Join("|", leans)}"))
                Plugin.Log.LogInfo($"{model.Title}: leaning {leans[3] + leans[2] + leans[1]} of {leans.Sum()} copies ({leans[2]} halved, {leans[1]} small, {leans[0]} upright: no room).");
            if (designed > 0 && told.Add($"{model.Title}|designed|{designed}|{stacks}"))
                Plugin.Log.LogInfo($"{model.Title}: {designed} of {stacks} shown in their own place's designed pose, the rest by the place rules ({gear.Count} held).");
#endif
            ReportRings(model);
        }
        // The units style, drawn from its plan (empty for the other styles): the boards, then per stack its copies, then the bands,
        // liquids, labels, vessels and panels, in the order the plan's decisions were once made inline.
        if (plan.Dividers && Board.Material is { } boardMat && boardMat)
        {
            if (!groups.TryGetValue(boardMat, out var boards)) groups[boardMat] = boards = new List<CombineInstance>();
            foreach (var d in model.Dividers) boards.Add(new CombineInstance { mesh = Board.PlankMesh, transform = d });
        }
        float grow = model.Kind?.ItemSize?.Value ?? 1f;   // this store's Item size, looked up once per rebuild
        var marks = new List<int>();   // per plan stack the copies drawn before it: what each stack drew
        foreach (var s in plan.Stacks)
        {
            marks.Add(copies);
            var item = items[s.Item];
            int u = s.Unit;
            var unit = model.Units[u];
            At("unit", u);
            if (s.Draw == UnitPlan.Draw.Crop)
            {
                // A crop heap: its layout's stack K, as is or mirrored, kept on its side of a shared crate.
                var cropLook = ItemVisual.Get(item.m_dropPrefab);
                var drawn = plan.Topless ? cropLook.Topless : cropLook;
                var lay = model.crops[s.Layout];
                var size = cropLook.Bounds.size;
                float sc = (lay.Scale ?? lay.Longest / Mathf.Max(1e-4f, Mathf.Max(size.x, Mathf.Max(size.y, size.z)))) * grow;   // the store's Item size too
                var turn = model.crateTurns != null && unit.Group < model.crateTurns.Count ? model.crateTurns[unit.Group] : Quaternion.identity;
                foreach (var (offset, local) in lay.Stacks[s.K].Take(s.Cap))
                {
                    var o = offset;
                    var l = local;
                    // Mirrored across the crate: the position reflected in x, the turn reflected with it (the item itself is not
                    // mirrored).
                    if (s.Variant == 1) { o.x = -o.x; l = new Quaternion(l.x, -l.y, -l.z, l.w); }
                    var rot = turn * l;
                    var centre = model.crateFloors[unit.Group] + turn * o;
                    var at = Matrix4x4.TRS(centre - rot * (sc * cropLook.Bounds.center), rot, Vector3.one * sc);
                    if (plan.Split.TryGetValue(u, out var cropSide) && !StoreModel.KeepSide(ref at, drawn.Drawn.size != Vector3.zero ? drawn.Drawn : drawn.Bounds, cropSide)) continue;   // a shared crate, by what is drawn (a carrot without its greens)
                    copies++;
                    looseCopies += Add(drawn, at, groups, loose);
                }
                continue;
            }
            if (s.Draw != UnitPlan.Draw.Copies) continue;   // a liquid only (UnitPlan.Liquids), or nothing to draw it with
            var look = ItemVisual.Get(item.m_dropPrefab);
            if (s.Hang && MeatBundles.Place(u, item, hung, groups))
            {
                foreach (var at in hung) { copies++; looseCopies += Add(look, at, groups, loose); }
                hung.Clear();
                continue;
            }
            var demo = unit.Demo != null ? ItemVisual.Get(unit.Demo) : null;
            List<Bounds> tied = unit.Kind == "bundle" && model.Slug == "meatrack" ? new List<Bounds>() : null;   // hung bundles only
            for (int j = 0; j < s.N; j++)
            {
                var at = StoreModel.Place(unit, unit.Copies[j], look, demo, display, grow);
                if (unit.Kind != "bundle" && unit.Group >= 0)
                {
                    // Heaps were settled with one particular item; a bigger or flatter one in its place can sink through the
                    // crate or bin floor (Joost: serpent meat). Never below the unit's floor.
                    float floor = unit.Pos.y - unit.Box.y * 0.5f, low = Geometry.Xform(at, look.Bounds).min.y;
                    if (low < floor) at = Matrix4x4.Translate(new Vector3(0f, floor - low, 0f)) * at;
                }
                if (plan.Split.TryGetValue(u, out var side) && !StoreModel.KeepSide(ref at, look.Bounds, side)) continue;
                if (unit.Kind is "arrow" or "bolt")
                {
                    // Head up, every kind (Joost, 25 Oct: some kinds stood reversed, the modded ones): the head is the end the ammo's
                    // projectile flies with; where that can't be read, the old list of models known to point down.
                    var head = Ammo.HeadOf(look);
                    bool down = head is { } headAxis ? at.MultiplyVector(headAxis).y < 0f : unit.Kind == "arrow" && HeadDown.Contains(item.m_dropPrefab ? item.m_dropPrefab.name : "");
                    if (down) at = at * Matrix4x4.Translate(look.Bounds.center) * Matrix4x4.Rotate(Quaternion.Euler(180f, 0f, 0f)) * Matrix4x4.Translate(-look.Bounds.center);
#if !RELEASE
                    Ammo.Note(model, u, item.m_dropPrefab ? item.m_dropPrefab.name : look.PrefabName, Geometry.Xform(at, look.Bounds), head != null, down);
#endif
                }
                copies++;
                looseCopies += Add(plan.Topless ? look.Topless : look, at, groups, loose);
                tied?.Add(Geometry.Xform(at, look.Bounds));
            }
            if (tied != null) Cord.Tie(tied, groups);
            if (s.Bind && model.Bindings.TryGetValue(u, out var binding) && model.FrameMaterial is { } bindMat && bindMat)
            {
                if (!groups.TryGetValue(bindMat, out var bl)) groups[bindMat] = bl = new List<CombineInstance>();
                bl.Add(new CombineInstance { mesh = binding, transform = Matrix4x4.identity });
            }
        }
        // What was drawn, not what was placed (Joost, 27 Oct: "51 stack(s) of 63 shown" with the Meat Rack's bins empty): a stack the
        // plan placed of which nothing was drawn (every copy wider than its side of a shared bay, or no model to draw) is not shown,
        // and its kind is unseen when no other stack of it shows. The plan stays the decision; this is the drawing's report of it.
        var shownAt = plan.Assigned.Select(_ => -1).ToList();
        int drewNothing = 0;
#if !RELEASE
        var culled = new List<string>();
#endif
        for (int k = 0; k < plan.Stacks.Count; k++)
        {
            var s = plan.Stacks[k];
            int drawn = (k + 1 < marks.Count ? marks[k + 1] : copies) - marks[k];
            if (s.Draw == UnitPlan.Draw.None || drawn > 0) { shownAt[s.Item] = s.Unit; continue; }   // None: a liquid, shown as its fill
            if (s.Draw == UnitPlan.Draw.Undrawn) continue;   // never counted as shown; the plan's undrawn line says why
            drewNothing++;
#if !RELEASE
            culled.Add($"{(items[s.Item].m_dropPrefab ? items[s.Item].m_dropPrefab.name : items[s.Item].m_shared.m_name)} at unit {s.Unit} "
                + (plan.Split.ContainsKey(s.Unit) ? "(every copy wider than its side of a shared bay)" : "(no copy drawn)"));
#endif
        }
        stacks += plan.Shown - drewNothing;
        if (plan.Order != "none")   // the units style drew
        {
            var kindOf = items.Select(it => it.m_dropPrefab ? it.m_dropPrefab.name : it.m_shared.m_name).ToList();
            if (plan.Assigned.Count > 0) UnrepresentedKindCount = StorageReviewPolicy.UnrepresentedKinds(kindOf, shownAt, model.Units.Count);
#if !RELEASE
            var placedKinds = new HashSet<string>(kindOf.Where((t, i) => i < plan.Assigned.Count && plan.Assigned[i] >= 0), StringComparer.Ordinal);
            string unshown = drewNothing == 0 && plan.Stacks.All(s => s.Draw != UnitPlan.Draw.Undrawn) ? plan.UnshownLine
                : UnitPlan.NotShown(model.Title, kindOf, shownAt, inv.GetAllItems().Count(i => i?.m_shared != null) - items.Count,
                    t => placedKinds.Contains(t) ? "placed, but nothing of it drawn" : plan.NoPlace(t));
            if (unshown != lastUnshownLine) { lastUnshownLine = unshown; if (unshown != null) Plugin.Log.LogInfo(unshown); }
#endif
        }
#if !RELEASE
        if (model.Units.Any(x => x.Kind is "arrow" or "bolt")) Ammo.Report(model);
#endif
        // A holder's band shows what it holds; an empty holder keeps the frame's plain band.
        if (model.Bands.Count > 0 && model.FrameMaterial is { } bandFrame && bandFrame)
            foreach (var (band, held) in plan.Bands)
                if (HideTint.For(bandFrame, items[held].m_dropPrefab) is { } bandMat)
                {
                    if (!groups.TryGetValue(bandMat, out var bl)) groups[bandMat] = bl = new List<CombineInstance>();
                    bl.Add(new CombineInstance { mesh = model.Bands[band], transform = Matrix4x4.identity });
                }
#if !RELEASE
        string undrawnLine = culled.Count == 0 ? plan.UndrawnLine
            : (plan.UndrawnLine != null ? plan.UndrawnLine + ", " : $"{model.Title}: placed but not drawn: ") + string.Join(", ", culled);
        if (undrawnLine != lastUndrawnLine) { lastUndrawnLine = undrawnLine; if (undrawnLine != null) Plugin.Log.LogInfo(undrawnLine); }
#endif
        // Liquids: each vessel's column as tall as its share (UnitPlan: the vessel's own liquid at the bottom, a spilled-over one on top).
        foreach (var (li, below, share) in plan.Liquids)
        {
            var l = model.Liquids[li];
            if (model.FrameMaterial is not { } liquidMat || !liquidMat) continue;
            float height = l.TopY - l.Floor.y;
            if (!groups.TryGetValue(liquidMat, out var list)) groups[liquidMat] = list = new List<CombineInstance>();
            list.Add(new CombineInstance { mesh = l.Mesh, transform = Matrix4x4.TRS(l.Floor + Vector3.up * (height * below), Quaternion.identity, new Vector3(1f, Mathf.Max(0.01f, height * share), 1f)) });
        }
        // Labels: the item a vessel holds, one copy standing in front of it (Joost: "only show what's actually in there").
        foreach (var (li, held) in plan.Labels)
            if (model.Labels[li] is var label && ItemVisual.Get(items[held].m_dropPrefab) is { } labelLook)
            {
                var b = labelLook.Bounds;
                float sc = label.Longest / Mathf.Max(1e-4f, Mathf.Max(b.size.x, Mathf.Max(b.size.y, b.size.z)));
                var at = Matrix4x4.TRS(label.Pos, label.Rot, Vector3.one * sc) * Matrix4x4.Translate(-new Vector3(b.center.x, b.min.y, b.center.z));
                at = Jitter.Turn(at, b, Jitter.Degrees(transform.position, 1000 + label.Group, 4f));
                At("label", label.Group);
                copies++;
                looseCopies += Add(labelLook, at, groups, loose);
            }
        // Places: each shows the vessel of what it holds; an empty place stands empty (how many vessels stand shows how full the rack is).
        if (model.Places.Count > 0 && model.FrameMaterial is { } placeMat && placeMat)
        {
            if (!groups.TryGetValue(placeMat, out var list)) groups[placeMat] = list = new List<CombineInstance>();
            foreach (var (pi, fam) in plan.Places)
            {
                var place = model.Places[pi];
                if (model.VesselMeshes.TryGetValue(fam, out var vesselMesh))
                {
                    list.Add(new CombineInstance { mesh = vesselMesh, transform = Matrix4x4.Translate(place.At) });
                    // Its glass: once per standing jar, at the jar's own spot; gone again when the place takes another vessel.
                    if (model.FamilyGlass.TryGetValue(fam, out var panes))
                        foreach (var pane in panes)
                        {
                            if (!pane.Mat) continue;
                            if (!groups.TryGetValue(pane.Mat, out var gl)) groups[pane.Mat] = gl = new List<CombineInstance>();
                            gl.Add(new CombineInstance { mesh = pane.Mesh, transform = Matrix4x4.Translate(place.At) });
                        }
                }
            }
        }
        // Panels: the Hide Rack's frames show the hide their bay holds, in that hide's colour (Joost, 24 Oct: "I thought the hides
        // would show on the rack itself"); an empty bay's frame stands empty.
        foreach (var (pi, hide) in plan.Panels)
            if (model.FrameMaterial is { } frameMat && frameMat && HideTint.For(frameMat, items[hide].m_dropPrefab) is { } tinted)
            {
                if (!groups.TryGetValue(tinted, out var list)) groups[tinted] = list = new List<CombineInstance>();
                list.Add(new CombineInstance { mesh = model.Panels[pi].Mesh, transform = Matrix4x4.identity });
            }
#if !RELEASE
        if (Recording != null) { Record("near", groups, loose); Record("far", farItems, farLoose); }
        if (seenInto != null)
        {
            // What is no item copy (boards, vessels, liquids, panels, bands): it hides copies as the frame does.
            foreach (var kv in groups)
            {
                nearItemIdx.TryGetValue(kv.Key, out var marked);
                for (int k = 0; k < kv.Value.Count; k++) if (marked == null || !marked.Contains(k)) seenInto.Extras.Add((kv.Key, kv.Value[k]));
            }
            seenInto = null;
        }
#endif
        int verts = 0;
        long tris = 0;
        foreach (var kv in groups)
        {
            var mesh = new Mesh { name = "storehouse_contents_" + kv.Key.name, indexFormat = UnityEngine.Rendering.IndexFormat.UInt32 };
            mesh.CombineMeshes(kv.Value.ToArray(), true, true);
            verts += mesh.vertexCount;
            bool clear = Glass.SeeThrough(kv.Key);
            var b = new Batch
            {
                Mesh = mesh, Mat = kv.Key, Merged = true, LocalBounds = mesh.bounds, Tris = (int)(mesh.GetIndexCount(0) / 3),
                Shadows = clear ? UnityEngine.Rendering.ShadowCastingMode.Off : UnityEngine.Rendering.ShadowCastingMode.On, Receive = !clear,
                Probes = UnityEngine.Rendering.LightProbeUsage.BlendProbes, Reflections = UnityEngine.Rendering.ReflectionProbeUsage.BlendProbes,
            };
            mesh.UploadMeshData(true);   // only drawn from here on: free the CPU copy
            tris += b.Tris;
            batches.Add(b);
        }
        int inst = 0;
        foreach (var b in loose.Values)
        {
            b.World = new Matrix4x4[b.Local.Count];
            b.Inst = Instanced(b.Mat);
            if (b.Inst) inst++;
            tris += (long)b.Tris * b.Local.Count;
            batches.Add(b);
        }
        // The far set: everything that is not an item copy as it is, the item copies with their far models.
        if (anyFar)
        {
            var far = new Dictionary<Material, List<CombineInstance>>();
            foreach (var kv in groups)
            {
                nearItemIdx.TryGetValue(kv.Key, out var marked);
                var kept = marked == null ? new List<CombineInstance>(kv.Value) : kv.Value.Where((_, i) => !marked.Contains(i)).ToList();
                if (kept.Count > 0) far[kv.Key] = kept;
            }
            foreach (var kv in farItems)
            {
                if (!far.TryGetValue(kv.Key, out var list)) far[kv.Key] = list = new List<CombineInstance>();
                list.AddRange(kv.Value);
            }
            foreach (var kv in far)
            {
                var mesh = new Mesh { name = "storehouse_far_" + kv.Key.name, indexFormat = UnityEngine.Rendering.IndexFormat.UInt32 };
                mesh.CombineMeshes(kv.Value.ToArray(), true, true);
                bool clear = Glass.SeeThrough(kv.Key);
                farBatches.Add(new Batch
                {
                    Mesh = mesh, Mat = kv.Key, Merged = true, LocalBounds = mesh.bounds, Tris = (int)(mesh.GetIndexCount(0) / 3),
                    Shadows = clear ? UnityEngine.Rendering.ShadowCastingMode.Off : UnityEngine.Rendering.ShadowCastingMode.On, Receive = !clear,
                    Probes = UnityEngine.Rendering.LightProbeUsage.BlendProbes, Reflections = UnityEngine.Rendering.ReflectionProbeUsage.BlendProbes,
                });
                mesh.UploadMeshData(true);
            }
            foreach (var b in farLoose.Values)
            {
                b.World = new Matrix4x4[b.Local.Count];
                b.Inst = Instanced(b.Mat);
                farBatches.Add(b);
            }
        }
        foreach (var m in scratch) if (m) UnityEngine.Object.Destroy(m);   // combined into the batches above
        scratch.Clear();
        // The Ossuary's blended copies, each its own batch in the near set and, when there is one, the far set (one mesh for both).
        foreach (var (mat, mesh) in blended)
        {
            Batch Of() => new Batch
            {
                Mesh = mesh, Mat = mat, Merged = true, LocalBounds = mesh.bounds, Tris = (int)(mesh.GetIndexCount(0) / 3),
                Shadows = UnityEngine.Rendering.ShadowCastingMode.Off, Receive = false,
                Probes = UnityEngine.Rendering.LightProbeUsage.BlendProbes, Reflections = UnityEngine.Rendering.ReflectionProbeUsage.BlendProbes,
            };
            batches.Add(Of());
            tris += mesh.GetIndexCount(0) / 3;
            if (farBatches.Count > 0) farBatches.Add(Of());
        }
        blended.Clear();
        long farTris = farBatches.Sum(b => b.Merged ? (long)b.Tris : (long)b.Tris * b.Local.Count);
        farItems = null;
        farLoose = null;
        nearItemIdx = null;
        for (int i = 0; i < batches.Count; i++)
            if (i == 0) localBounds = batches[i].LocalBounds; else localBounds.Encapsulate(batches[i].LocalBounds);
        rootValid = false;
        copiesShown = copies;
        TrianglesShown = tris;
        double ms = (System.Diagnostics.Stopwatch.GetTimestamp() - t0) * 1000.0 / System.Diagnostics.Stopwatch.Frequency;
        Perf.Rebuilt(model.Title, ms, copies);
        Plugin.Log.LogInfo($"{model.Title}: {stacks} stack(s) of {items.Count} shown at item size {grow:F2}, {copies} item copies, {groups.Count} merged mesh(es) ({verts} verts)"
            + (looseCopies > 0 ? $", {looseCopies} unmergeable part copies in {loose.Count} batch(es) ({inst} instanced)" : "")
            + $", {tris / 1000.0:F1}k triangles" + (farBatches.Count > 0 ? $" ({farTris / 1000.0:F1}k from afar)" : "")
            + $", {batches.Count - loose.Count + inst + loose.Values.Where(b => !b.Inst).Sum(b => b.Local.Count)} draws at most; rebuilt in {ms:F1} ms.");
    }

    // One copy of an item at matrix at (store space): its readable parts into the merged meshes, the rest into their
    // (mesh, submesh, material) batch. Returns how many parts went into batches.
    // Arrows whose model points the other way (fletcher_r1's check): turned so every arrow stands head up in its barrel.
    static readonly HashSet<string> HeadDown = new() { "ArrowPoison", "ArrowFrost", "ArrowCharred", "ArrowCarapace" };

    // What the units style's plan reads (DisplayPlan.cs): the stock as plain rows, the model as plain numbers, and per stack the facts
    // only the game knows (its item model's triangles), asked as the plan needs them.
    UnitPlan.Inputs PlanInputs(Inventory inv, List<ItemDrop.ItemData> rows) => new UnitPlan.Inputs
    {
        Width = inv.GetWidth(), Height = inv.GetHeight(), MaxTrisPerStack = Settings.MaxTrisPerStack.Value, Model = model.PlanSummary(),
        Rows = rows.Select(it => new UnitPlan.Row
        {
            Kind = it.m_dropPrefab ? it.m_dropPrefab.name : it.m_shared.m_name, Drop = it.m_dropPrefab ? it.m_dropPrefab.name : null,
            Stack = it.m_stack, Max = it.m_shared.m_maxStackSize, X = it.m_gridPos.x, Y = it.m_gridPos.y,
        }).ToList(),
        Look = r => ItemVisual.Get(rows[r].m_dropPrefab) is { } v ? v.Triangles : null,
#if !RELEASE
        PartsTris = r => ItemVisual.Get(rows[r].m_dropPrefab) is { } v ? v.Parts.Sum(pt => pt.Mesh ? Enumerable.Range(0, pt.Mesh.subMeshCount).Sum(k => (int)pt.Mesh.GetIndexCount(k)) / 3 : 0) : null,
#endif
    };

    static int Add(ItemVisual look, Matrix4x4 at, Dictionary<Material, List<CombineInstance>> groups, Dictionary<(Mesh, int, Material), Batch> loose)
    {
#if !RELEASE
        seenInto?.Copies.Add((seenItem ?? look.PrefabName ?? "?", seenKind + " " + seenNo, look, at));
#endif
        int n = AddParts(look, at, groups, loose, nearItemIdx);
        if (farItems != null)
        {
            if (look.Far != null) anyFar = true;
            AddParts(look.Far ?? look, at, farItems, farLoose, null);
        }
        return n;
    }

    static int AddParts(ItemVisual look, Matrix4x4 at, Dictionary<Material, List<CombineInstance>> groups, Dictionary<(Mesh, int, Material), Batch> loose,
        Dictionary<Material, HashSet<int>> marks)
    {
        int n = 0;
        foreach (var part in look.Parts)
        {
            var m = at * part.M;
            if (!part.Readable) n++;
            for (int sm = 0; sm < part.Mesh.subMeshCount; sm++)
            {
                var mat = part.Mats.Length > 0 ? part.Mats[Mathf.Min(sm, part.Mats.Length - 1)] : null;
                if (!mat) continue;
                if (part.Readable)
                {
                    if (!groups.TryGetValue(mat, out var list)) groups[mat] = list = new List<CombineInstance>();
                    list.Add(new CombineInstance { mesh = part.Mesh, subMeshIndex = sm, transform = m });
                    if (marks != null) { if (!marks.TryGetValue(mat, out var idx)) marks[mat] = idx = new HashSet<int>(); idx.Add(list.Count - 1); }
                    continue;
                }
                var key = (part.Mesh, sm, mat);
                if (!loose.TryGetValue(key, out var b))
                    loose[key] = b = new Batch
                    {
                        Mesh = part.Mesh, Sub = sm, Mat = mat, Shadows = part.Shadows, Receive = part.Receive,
                        Probes = part.Probes, Reflections = part.Reflections, Tris = (int)(part.Mesh.GetIndexCount(sm) / 3),
                    };
                var bounds = Geometry.Xform(m, part.Mesh.bounds);
                if (b.Local.Count == 0) b.LocalBounds = bounds; else b.LocalBounds.Encapsulate(bounds);
                b.Local.Add(m);
            }
        }
        return n;
    }

    // The material with instancing on, for RenderMeshInstanced; null when the shader has no instancing variant (it would
    // draw every copy at one spot). The game's own material is used as is when it already has instancing on; otherwise we
    // draw with a copy, so items elsewhere in the world are not touched.
    static Material Instanced(Material src)
    {
        if (!src || !SystemInfo.supportsInstancing) return null;
        if (instanced.TryGetValue(src, out var m)) return m;
        var shader = src.shader;
        if (src.enableInstancing) m = src;
        else if (shader && shader.keywordSpace.FindKeyword("INSTANCING_ON").isValid)
            m = new Material(src) { name = src.name + " (storehouse instanced)", enableInstancing = true };
        Plugin.Log.LogInfo($"Contents: material '{src.name}' ({(shader ? shader.name : "no shader")}): "
            + (m ? (m == src ? "instancing already on, drawn instanced" : "drawn instanced (copy with instancing on)") : "no instancing variant, one draw per copy") + ".");
        return instanced[src] = m;
    }

    // The store moved (or was just rebuilt): world matrices and bounds again.
    void Refresh()
    {
        var m = transform.localToWorldMatrix;
        if (rootValid && m == root) return;
        root = m;
        rootValid = true;
        worldBounds = Geometry.Xform(m, localBounds);
        foreach (var b in batches.Concat(farBatches))
        {
            b.WorldBounds = Geometry.Xform(m, b.LocalBounds);
            if (b.Merged) continue;
            for (int i = 0; i < b.Local.Count; i++) b.World[i] = m * b.Local[i];
        }
    }

    // Every frame (Plugin.LateUpdate): the contents of every store in range and in view.
    public static void DrawAll()
    {
        int inRange = 0, inView = 0, copies = 0, draws = 0, instDraws = 0, instCopies = 0;
        long tris = 0;
        var cam = Settings.ShowContents.Value && live.Count > 0 ? global::Utils.GetMainCamera() : null;
        var planes = cam ? global::Utils.GetMainCameraFrustumPlanes() : null;
        if (cam && planes != null)
        {
            var pos = cam.transform.position;
            float d = Settings.ContentsDistance.Value, d2 = d * d;
            bool shadows = Settings.ContentsShadows.Value;
            bool useInst = Settings.Instancing.Value && SystemInfo.supportsInstancing;
            for (int s = 0; s < live.Count; s++)
            {
                var sc = live[s];
                if (sc.batches.Count == 0) continue;
                sc.Refresh();
                if (sc.worldBounds.SqrDistance(pos) > d2) continue;
                inRange++;
                if (GeometryUtility.TestPlanesAABB(planes, sc.worldBounds)) inView++;
                else if (!shadows) continue;   // off screen and no shadows to cast into view
                copies += sc.copiesShown;
                int layer = sc.gameObject.layer;
                float farFrom = Settings.FarContents.Value;
                var set = farFrom > 0f && sc.farBatches.Count > 0 && sc.worldBounds.SqrDistance(pos) > farFrom * farFrom ? sc.farBatches : sc.batches;
                foreach (var b in set)
                {
                    if (!shadows && b.Shadows == UnityEngine.Rendering.ShadowCastingMode.ShadowsOnly) continue;
                    bool inst = useInst && !b.Merged && b.Inst;
                    var rp = new RenderParams(inst ? b.Inst : b.Mat)
                    {
                        layer = layer,
                        shadowCastingMode = shadows ? b.Shadows : UnityEngine.Rendering.ShadowCastingMode.Off,
                        receiveShadows = b.Receive && Settings.ContentsInShade.Value,
                        // Instanced: the scene's ambient probe (what Off gives; blended probes per instance need extra data).
                        lightProbeUsage = inst ? UnityEngine.Rendering.LightProbeUsage.Off : b.Probes,
                        reflectionProbeUsage = b.Reflections,
                        worldBounds = b.WorldBounds,
                    };
                    if (b.Merged)
                    {
                        Graphics.RenderMesh(rp, b.Mesh, 0, sc.root);
                        draws++;
                        tris += b.Tris;
                        continue;
                    }
                    int n = b.Local.Count;
                    tris += (long)b.Tris * n;
                    if (inst)
                    {
                        try
                        {
                            for (int i = 0; i < n; i += MaxPerDraw)
                            {
                                Graphics.RenderMeshInstanced(rp, b.Mesh, b.Sub, b.World, Math.Min(MaxPerDraw, n - i), i);
                                draws++;
                                instDraws++;
                            }
                            instCopies += n;
                            continue;
                        }
                        catch (Exception e)
                        {
                            Plugin.Log.LogWarning($"Contents: instanced draw of '{b.Mesh.name}' with '{b.Mat.name}' failed ({e.Message}); one draw per copy from now on.");
                            instanced[b.Mat] = null;
                            b.Inst = null;
                            rp.material = b.Mat;
                            rp.lightProbeUsage = b.Probes;
                        }
                    }
                    rp.worldBounds = new Bounds(Vector3.zero, Vector3.zero);   // per copy: Unity culls each copy by its own bounds
                    for (int i = 0; i < n; i++) Graphics.RenderMesh(rp, b.Mesh, b.Sub, b.World[i]);
                    draws += n;
                }
            }
        }
        Perf.Drawn(live.Count, inRange, inView, copies, draws, instDraws, instCopies, tris);
    }

    void Clear()
    {
        var gone = new HashSet<Mesh>();   // a blended pile copy's mesh is in both sets
        foreach (var b in batches) if (b.Merged && b.Mesh && gone.Add(b.Mesh)) Destroy(b.Mesh);
        batches.Clear();
        foreach (var b in farBatches) if (b.Merged && b.Mesh && gone.Add(b.Mesh)) Destroy(b.Mesh);
        farBatches.Clear();
        copiesShown = 0;
        rootValid = false;
    }

    void OnDestroy() => Clear();
#if !RELEASE

    // storehouse_selftest capture (the coordinator, 27 Oct): what one rebuild draws, recorded before the meshes are merged: every
    // part copy as its set (near, far), merged or loose, material, mesh, submesh and store-space matrix. Null outside a capture.
    static List<string> Recording;
    static (string inputs, string plan)? RecordedPlan;   // the units-style plan of the rebuild a capture recorded: its inputs and the plan, as JSON

    static void Record(string set, Dictionary<Material, List<CombineInstance>> groups, Dictionary<(Mesh, int, Material), Batch> loose)
    {
        static string N(UnityEngine.Object o) => o ? o.name : "none";
        static string R(float v) { double r = Math.Round((double)v, 5); return (r == 0 ? 0 : r).ToString("0.#####", CultureInfo.InvariantCulture); }
        static string M(Matrix4x4 m) => string.Join(" ", Enumerable.Range(0, 12).Select(i => R(m[i / 4, i % 4])));
        if (groups != null)
            foreach (var kv in groups)
                foreach (var ci in kv.Value)
                    Recording.Add($"{set} merged {N(kv.Key)} {N(ci.mesh)}#{(ci.mesh ? ci.mesh.vertexCount : 0)} sub{ci.subMeshIndex} {M(ci.transform)}");
        if (loose != null)
            foreach (var b in loose.Values)
                foreach (var m in b.Local)
                    Recording.Add($"{set} loose {N(b.Mat)} {N(b.Mesh)}#{(b.Mesh ? b.Mesh.vertexCount : 0)} sub{b.Sub} {M(m)}");
    }

    // storehouse_selftest's hidden check (Joost's list, 27 Oct, item 13: the Bow Rack showed 3 of 4 bows while the log said 8/8
    // drawn): every item copy as it goes in, before the merge, with the item and the place it is drawn for, and what the rebuild
    // draws that is no item copy (store space). The self-test sets Seen; every rebuild of this store fills it again. Null: not kept.
    internal sealed class Drawn
    {
        public readonly List<(string item, string place, ItemVisual look, Matrix4x4 at)> Copies = new();
        public readonly List<(Material mat, CombineInstance part)> Extras = new();
    }
    internal Drawn Seen;
    static Drawn seenInto;   // during a rebuild of a store whose Seen is set
    static string seenKind, seenItem;
    static int seenNo;
#endif

    // The place the next copies of a rebuild are drawn for (a unit, an equipment place, a figure...), for the self-test's hidden
    // check; item: when the copy's own model has no prefab name (a worn bake). Does nothing in a release build.
    static void At(string kind, int no, string item = null)
    {
#if !RELEASE
        seenKind = kind;
        seenNo = no;
        seenItem = item;
#endif
    }
#if !RELEASE

    // The self-test (27 Oct: its counts and pictures showed the state before, as a store looks again only once a second): look
    // now, and whether what is drawn is the inventory as it is.
    internal void CheckNow() => next = 0f;
    internal bool Current(Inventory inv) => model != null && shownHash == Hash(inv) && model.Version == shownVersion;

    // One rebuild of a store that stands nowhere: this component sits on an inactive object (so no Start, no Update, never in the
    // draw list), draws the inventory once with the given model, and frees its meshes again. Returns the recorded parts (sorted) and
    // what the rebuild reported; the caller destroys the object.
    internal (List<string> parts, int copies, int unseen, long tris, (string inputs, string plan)? plan) CaptureOnce(StoreModel m, Inventory inv)
    {
        model = m;
        Recording = new List<string>();
        RecordedPlan = null;
        try
        {
            Rebuild(inv);
            Recording.Sort(StringComparer.Ordinal);
            return (Recording, copiesShown, UnrepresentedKindCount, TrianglesShown, RecordedPlan);
        }
        finally { Recording = null; RecordedPlan = null; Clear(); }
    }
#endif

    // Live reload: the instancing copies of item materials this copy made (the game's own materials stay).
    public static void ReleaseInstanced()
    {
        foreach (var kv in instanced) if (kv.Value && kv.Value != kv.Key) Destroy(kv.Value);
        instanced.Clear();
        live.Clear();
    }
}

// Dev perf log (setting "Perf log", every 10 s) and overlay: FPS over the window (average, and 1% low = the average of
// the slowest 1% of frames), what Storehouse drew per frame on average, the time spent in Storehouse code (Plugin.Update
// and LateUpdate, every StoreContents check and rebuild), the worst live-model check and the last contents rebuild.
static class Perf
{
    const float Window = 10f;
    static readonly List<float> frames = new(4096);
    static float started = -1f;
    static long ticks, frameTicks, worstFrame, worstLive;
    static long sumInRange, sumInView, sumCopies, sumDraws, sumInstDraws, sumInstCopies, sumTris;
    static int drawFrames, stores;
    static double worstRebuild;
    static string lastRebuild = "none", worstRebuildWho = "";
    public static string Line;

    static double Ms(long t) => t * 1000.0 / System.Diagnostics.Stopwatch.Frequency;

    public static void Add(long t0)
    {
        long d = System.Diagnostics.Stopwatch.GetTimestamp() - t0;
        ticks += d;
        frameTicks += d;
    }

    public static void EndFrame()
    {
        if (frameTicks > worstFrame) worstFrame = frameTicks;
        frameTicks = 0;
    }

    public static void LiveCheck(long t0) => worstLive = Math.Max(worstLive, System.Diagnostics.Stopwatch.GetTimestamp() - t0);

    public static void Rebuilt(string title, double ms, int copies)
    {
        lastRebuild = $"{title} {ms:F1} ms ({copies} copies)";
        if (ms > worstRebuild) { worstRebuild = ms; worstRebuildWho = title; }
    }

    public static void Drawn(int all, int inRange, int inView, int copies, int draws, int instDraws, int instCopies, long tris)
    {
        stores = all;
        drawFrames++;
        sumInRange += inRange;
        sumInView += inView;
        sumCopies += copies;
        sumDraws += draws;
        sumInstDraws += instDraws;
        sumInstCopies += instCopies;
        sumTris += tris;
    }

    // Start of every frame (Plugin.Update).
    public static void Frame()
    {
        float now = Time.realtimeSinceStartup;
        if (started < 0f) { started = now; return; }
        frames.Add(Time.unscaledDeltaTime);
        if (now - started < Window) return;
        if (Settings.PerfLog.Value || Settings.PerfOverlay.Value) Report(now - started);
        started = now;
        frames.Clear();
        ticks = worstFrame = worstLive = 0;
        sumInRange = sumInView = sumCopies = sumDraws = sumInstDraws = sumInstCopies = sumTris = 0;
        drawFrames = 0;
        worstRebuild = 0;
        worstRebuildWho = "";
    }

    static void Report(float seconds)
    {
        int n = frames.Count;
        if (n == 0) return;
        float total = 0f;
        foreach (var f in frames) total += f;
        frames.Sort((a, b) => b.CompareTo(a));   // slowest first
        int k = Math.Max(1, n / 100);
        float worst = 0f;
        for (int i = 0; i < k; i++) worst += frames[i];
        double fps = n / Math.Max(1e-4, total), low = k / Math.Max(1e-4, worst);
        double f1 = Math.Max(1, drawFrames);
        Line = $"Storehouse perf {seconds:F0} s: {fps:F1} fps avg, {low:F1} fps 1% low ({n} frames) | stores {stores} loaded, "
            + $"{sumInRange / f1:F1} within {Settings.ContentsDistance.Value:F0} m, {sumInView / f1:F1} in view | per frame {sumCopies / f1:F0} item copies, "
            + $"{sumDraws / f1:F0} draws ({sumInstDraws / f1:F0} instanced for {sumInstCopies / f1:F0} part copies), {sumTris / f1 / 1000.0:F1}k triangles | "
            + $"Storehouse code {Ms(ticks) / n:F3} ms/frame avg, {Ms(worstFrame):F2} ms worst frame | live-model check {Ms(worstLive):F1} ms worst | "
            + $"rebuild last {lastRebuild}" + (worstRebuild > 0 ? $", worst this window {worstRebuildWho} {worstRebuild:F1} ms" : "")
            + $" | contents {(Settings.ShowContents.Value ? "on" : "OFF")}, shadows {(Settings.ContentsShadows.Value ? "on" : "off")}, "
            + $"instancing {(Settings.Instancing.Value ? "on" : "off")}";
        if (Settings.PerfLog.Value) Plugin.Log.LogInfo(Line);
    }
}

// Setting "Perf overlay": the latest perf line, top left, with a shadow so it reads on snow and on night.
sealed class PerfOverlay : MonoBehaviour
{
    GUIStyle style;

    void OnGUI()
    {
        if (Perf.Line == null) return;
        style ??= new GUIStyle(GUI.skin.label) { fontSize = 14, wordWrap = true };
        var r = new Rect(12f, 12f, Screen.width - 24f, 80f);
        style.normal.textColor = Color.black;
        GUI.Label(new Rect(r.x + 1f, r.y + 1f, r.width, r.height), Perf.Line, style);
        style.normal.textColor = Color.white;
        GUI.Label(r, Perf.Line, style);
    }
}

// Which items a store takes by type, read from the game's own data, so new and modded items fall in their place:
// meals are food someone makes (a recipe, a cooking station, the oven); raw meat is what goes on a cooking station, and
// fish; the harvest is what a planted crop yields, plus raw food nobody makes (berries, mushrooms); ore is what the
// coal-fired smelters take; coal is their fuel. Each store's Accepts list adds names on top.
// Equipment by the game's item type, so modded gear finds its place too (B's contract: types, not prefab names).
// Gravity and no patterns (Joost, 25 Oct: "the human brain is excellent at spotting patterns"): where the loader places copies
// itself, each turns a little about its own upright axis through its centre, the same every time for that store and place.
static class Jitter
{
    public static float Degrees(Vector3 store, int place, float max)
    {
        unchecked
        {
            int h = Mathf.RoundToInt(store.x * 10f) * 73856093 ^ Mathf.RoundToInt(store.y * 10f) * 19349663 ^ Mathf.RoundToInt(store.z * 10f) * 83492791 ^ place * 2654435761u.GetHashCode();
            h ^= h >> 13; h *= 1274126177; h ^= h >> 16;
            return ((h & 0xFFFF) / 65535f * 2f - 1f) * max;
        }
    }

    // at turned about the world-up axis through the centre of local (in at's frame).
    public static Matrix4x4 Turn(Matrix4x4 at, Bounds local, float degrees)
    {
        var c = at.MultiplyPoint3x4(local.center);
        return Matrix4x4.Translate(c) * Matrix4x4.Rotate(Quaternion.Euler(0f, degrees, 0f)) * Matrix4x4.Translate(-c) * at;
    }
}

// The main menu says whether Storehouse loaded, before a world is loaded (fix list F8; Joost, 1 Nov: players check this after an
// update instead of reading the log). Loaded with every piece: a quiet line at the bottom. Not fully: the red box (the coordinator's
// retro, 26 Oct: a refused config key once stopped the start unnoticed, and Valheim removed every placed piece). No line at all:
// Storehouse did not load.
sealed class LoadWarning : MonoBehaviour
{
    GUIStyle style, okStyle;
    int pieces, total;
    public void Set(int added, int all) { pieces = added; total = all; }

    void OnGUI()
    {
        if (!FejdStartup.instance) return;
        if (Plugin.Failures.Count == 0 && pieces == total)
        {
            // Top left, where the eye starts, sized to the screen (Joost, 1 Nov: 16 px at the bottom was "very subtle and very
            // invisible" on a 4K menu); a dark shadow keeps it readable on the bright sky.
            int size = Mathf.Max(18, Screen.height / 42);
            okStyle ??= new GUIStyle(GUI.skin.label) { alignment = TextAnchor.UpperLeft, fontStyle = FontStyle.Bold };
            okStyle.fontSize = size;
            var at = new Rect(size * 1.2f, size * 1.0f, Screen.width * 0.5f, size * 2f);
            string text = $"Storehouse {Plugin.Version} loaded: {pieces} pieces ready";
            okStyle.normal.textColor = new Color(0f, 0f, 0f, 0.85f);
            GUI.Label(new Rect(at.x + size * 0.08f, at.y + size * 0.08f, at.width, at.height), text, okStyle);
            okStyle.normal.textColor = new Color(0.98f, 0.82f, 0.45f, 1f);
            GUI.Label(at, text, okStyle);
            return;
        }
        style ??= new GUIStyle(GUI.skin.box) { fontSize = 18, wordWrap = true, alignment = TextAnchor.MiddleCenter, normal = { textColor = Color.white } };
        var before = GUI.backgroundColor;
        GUI.backgroundColor = new Color(0.85f, 0.05f, 0.05f, 1f);
        string what = Plugin.Failures.Count == 0 ? $"{pieces} of {total} pieces registered"
            : string.Join("; ", Plugin.Failures.Take(4)) + (Plugin.Failures.Count > 4 ? $" and {Plugin.Failures.Count - 4} more" : "");
        GUI.Box(new Rect(Screen.width * 0.2f, 20f, Screen.width * 0.6f, 96f),
            $"Storehouse {Plugin.Version} did not load fully: {what}. Don't load a world you care about; details in BepInEx/LogOutput.log.", style);
        GUI.backgroundColor = before;
    }
}


static class EquipRules
{
    static readonly HashSet<string> armor = new() { "Helmet", "Chest", "Legs", "Shoulder" };
    static readonly HashSet<string> oneHanded = new() { "OneHandedWeapon" };
    static readonly HashSet<string> weapons = new() { "OneHandedWeapon", "TwoHandedWeapon", "TwoHandedWeaponLeft", "Bow", "Shield" };
    static readonly HashSet<string> utility = new() { "Tool", "Torch", "Utility", "Trinket" };
    static string Type(ItemDrop.ItemData item) => item.m_shared.m_itemType.ToString();
    public static bool IsSaddle(ItemDrop.ItemData item) => (item.m_dropPrefab ? item.m_dropPrefab.name : item.m_shared.m_name ?? "").IndexOf("saddle", StringComparison.OrdinalIgnoreCase) >= 0;
    // A player's item has an icon; the gear monsters carry (Dverger staffs, goblin bones) has none and is no one's to store (Joost's
    // test: those filled a Utility Island with empty-looking slots).
    public static bool Players(ItemDrop.ItemData item) => item.m_shared.m_icons != null && item.m_shared.m_icons.Length > 0 && item.m_shared.m_icons[0];
    // Backpacks (Adventure Backpacks) are Shoulder items but carried gear, not armor to fold: the Utility pieces take them.
    public static bool IsBackpack(ItemDrop.ItemData item) => (item.m_dropPrefab ? item.m_dropPrefab.name : "").IndexOf("backpack", StringComparison.OrdinalIgnoreCase) >= 0;
    // Bombs are thrown one-handed weapons to the game, but they belong in the Bomb Crate (the coordinator, 25 Oct): no weapon store
    // takes them, by the same name the Bomb Crate's Accepts uses.
    public static bool IsBomb(ItemDrop.ItemData item) => (item.m_dropPrefab ? item.m_dropPrefab.name : "").StartsWith("Bomb", StringComparison.OrdinalIgnoreCase);
    public static bool Armor(ItemDrop.ItemData item) => Players(item) && (armor.Contains(Type(item)) || Type(item) == "Trinket") && !IsBackpack(item);   // trinkets too (0.8.1)
    public static bool Handheld(ItemDrop.ItemData item) => Players(item) && oneHanded.Contains(Type(item)) && !IsBomb(item);
    // The weapon racks (M, 27 Oct, from the fit report): the one-handed weapons a rack can show, by item data. Spears (skill Spears,
    // 2.3-3 m tall) stand in the Arsenal Long Rack; what does no damage at all (tankards, drinking horns) is no weapon; what its own
    // attack uses up is thrown (snowballs; also "snowball" in the prefab name, in case a snowball's attack is not marked so).
    // The refusal text, or null when a rack takes it.
    public static string NotForRack(ItemDrop.ItemData item, string what) =>
        item.m_shared.m_skillType == Skills.SkillType.Spears ? "Spears go in the Arsenal Long Rack."
        : item.m_shared.m_damages.GetTotalDamage() <= 0f ? $"{what} is no weapon: the weapon racks show weapons."
        : item.m_shared.m_attack?.m_consumeItem == true || (item.m_dropPrefab ? item.m_dropPrefab.name : "").IndexOf("snowball", StringComparison.OrdinalIgnoreCase) >= 0
            ? $"{what} is for throwing: the weapon racks show weapons." : null;
    public static bool RackWeapon(ItemDrop.ItemData item) => Handheld(item) && NotForRack(item, null) == null;
    public static bool Arsenal(ItemDrop.ItemData item) => Players(item) && (weapons.Contains(Type(item)) || Type(item) == "Tool") && !IsBomb(item);   // tools too (0.8.1)
    public static bool Combined(ItemDrop.ItemData item) => Players(item) && (armor.Contains(Type(item)) || weapons.Contains(Type(item))) && !IsBackpack(item) && !IsBomb(item);
    public static bool Mannequin(ItemDrop.ItemData item) => Players(item) && !IsBackpack(item) && !IsBomb(item) && (armor.Contains(Type(item)) || Type(item) is "OneHandedWeapon" or "Shield");
    public static bool Utility(ItemDrop.ItemData item) => Players(item) && (utility.Contains(Type(item)) || IsSaddle(item) || IsBackpack(item));

    // The Arsenal kit's modules, by weapon skill as well as type: the spine hangs one-handed swords, knives, axes and maces; the long
    // rack stands spears and the two-handed weapons (atgeirs, sledges, battleaxes, greatswords), never a pickaxe or a staff; the bow
    // rack bows in their slots and crossbows across their pegs; the trough shields.
    static string Skill(ItemDrop.ItemData item) => item.m_shared.m_skillType.ToString();
    static readonly HashSet<string> hung = new() { "Swords", "Knives", "Axes", "Clubs" };
    static readonly HashSet<string> standing = new() { "Spears", "Polearms", "Clubs", "Axes", "Swords" };
    public static bool KitSpine(ItemDrop.ItemData item) => Handheld(item) && hung.Contains(Skill(item));
    public static bool KitShield(ItemDrop.ItemData item) => Players(item) && Type(item) == "Shield";
    public static bool KitLong(ItemDrop.ItemData item) => Players(item) && !IsBomb(item) && standing.Contains(Skill(item))
        && (Type(item) is "TwoHandedWeapon" or "TwoHandedWeaponLeft" || (Type(item) == "OneHandedWeapon" && Skill(item) == "Spears"));
    static bool KitBows(ItemDrop.ItemData item) => Players(item) && Skill(item) == "Bows" && Type(item) == "Bow";
    // Crossbows only: bolts share their skill but go in the Bolt Crate (Joost, 27 Oct, on bolts on the Bow Rack's pegs: "it looks
    // dumb, and you can't tell that they're in there"); the refusal names the Bolt Crate (Filter.WhereItGoes).
    static bool KitCrossbows(ItemDrop.ItemData item) => Players(item) && Skill(item) == "Crossbows" && Type(item) is "Bow" or "TwoHandedWeapon" or "TwoHandedWeaponLeft";
    public static bool KitBow(ItemDrop.ItemData item) => KitBows(item) || KitCrossbows(item);
    // A place's kind in the kit's anchors: what it takes (null: not a kit kind), and as which item types.
    public static Func<ItemDrop.ItemData, bool> KitAccepts(string kind) => kind switch
    {
        "sword" or "knife" or "axe" or "mace" => KitSpine,
        "shield" or "shield_oversize" => KitShield,
        "spear" or "atgeir" or "sledge" or "two_handed_axe" or "sword_long" => KitLong,
        "bow" => KitBows,
        "crossbow" => KitCrossbows,
        _ => null,
    };
    public static string[] KitTypes(string kind) => kind switch
    {
        "shield" or "shield_oversize" => new[] { "Shield" },
        "spear" or "atgeir" or "sledge" or "two_handed_axe" or "sword_long" => new[] { "OneHandedWeapon", "TwoHandedWeapon", "TwoHandedWeaponLeft" },
        "bow" => new[] { "Bow" },
        "crossbow" => new[] { "Bow", "TwoHandedWeapon", "TwoHandedWeaponLeft" },
        _ => new[] { "OneHandedWeapon" },
    };

    // A window block's name in the hover and the refusals: what its places take, in the player's words.
    static readonly (string type, string word)[] typeWords =
    {
        ("Helmet", "helmet"), ("Chest", "chest"), ("Legs", "legs"), ("Shoulder", "cape"), ("OneHandedWeapon", "one-handed weapon"),
        ("TwoHandedWeapon", "two-handed weapon"), ("TwoHandedWeaponLeft", "two-handed weapon"), ("Bow", "bow"), ("Shield", "shield"),
        ("Tool", "tool"), ("Torch", "torch"), ("Utility", "wearable"), ("Trinket", "trinket"),
    };
    // A kit place's class: as its own kind. Bows and crossbows were one block for an evening (Joost, 27 Oct: "my bow rack can't hold
    // more bows", its two crossbow places empty), until two bows lay across the rack at the crossbow places' angle, through the six
    // bows; Joost, 27 Oct 20:05: "Crossbow places take crossbows only; extra bows stay in the chest."
    public static Func<ItemDrop.ItemData, bool> ClassAccepts(Func<ItemDrop.ItemData, bool> place) => place;
    public static string ClassName(StoreModel.EquipPlace p)
    {
        if (p.Accepts != null)
            return ClassAccepts(p.Accepts).Method.Name switch { nameof(KitSpine) => "weapon", nameof(KitShield) => "shield", nameof(KitLong) => "long weapon", nameof(KitBow) => "bow and crossbow", _ => p.Name };
        if (p.Saddle) return "saddle";
        var words = typeWords.Where(t => p.Types.Contains(t.type)).Select(t => t.word).Distinct().ToList();
        if (words.Contains("one-handed weapon") && words.Contains("two-handed weapon")) { words.Remove("two-handed weapon"); words[words.IndexOf("one-handed weapon")] = "weapon"; }
        return words.Count == 0 ? p.Name : words.Count == 1 ? words[0] : string.Join(", ", words.Take(words.Count - 1)) + " and " + words[^1];
    }
    // The faded icon per armor type in a block that takes several (as the Armory Rails' rows), in the order they cycle.
    public static readonly KeyValuePair<string, string>[] TypeHints =
    {
        new("Chest", "ArmorLeatherChest"), new("Legs", "ArmorLeatherLegs"), new("Shoulder", "CapeDeerHide"), new("Helmet", "HelmetLeather"),
    };

    // The anchors' groups (combined and utility exports) as item types; the armor and weapon exports name the types themselves.
    public static readonly Dictionary<string, string[]> Groups = new(StringComparer.Ordinal)
    {
        ["armor"] = new[] { "Helmet", "Chest", "Legs", "Shoulder" },
        ["weapons"] = new[] { "OneHandedWeapon", "TwoHandedWeapon", "TwoHandedWeaponLeft", "Bow" },
        ["shields"] = new[] { "Shield" },
        ["tools"] = new[] { "Tool", "Torch" },
        ["larger_worn"] = new[] { "Utility" },
        ["small_trinkets"] = new[] { "Trinket" },
        ["saddles"] = new string[0],
    };

    // An item's place in the game's progression (Joost, 25 Oct 18:58: with more items than places, show the highest tier): the
    // station its recipe needs (workbench, forge, artisan table, black forge and galdr table) and that station's level, then the
    // item's quality. No recipe (a drop, a mod's item without one): 0, after every crafted item.
    static readonly Dictionary<string, int> stationRank = new(StringComparer.Ordinal)
    {
        ["piece_workbench"] = 1, ["forge"] = 2, ["piece_artisanstation"] = 3, ["blackforge"] = 4, ["piece_magetable"] = 4,
    };
    public static int Tier(ItemDrop.ItemData item) => Tier(item, RecipeOf(item));
    internal static int TierScan(ItemDrop.ItemData item) => Tier(item, ObjectDB.instance ? ObjectDB.instance.GetRecipe(item) : null);   // 0.8.0's way: the dev self-check's
    // The game's GetRecipe walks every recipe for the one with the item's name, and the placement sorts by tier per item: about
    // 10,000 walks per change of the Spine's contents (FEEDBACK-0.8 item 3). Kept per name, anew when ObjectDB or its recipe count changes.
    static readonly Dictionary<string, Recipe> recipeOf = new(StringComparer.Ordinal);
    static ObjectDB recipesOf;
    static int recipeCount = -1;
    static Recipe RecipeOf(ItemDrop.ItemData item)
    {
        var db = ObjectDB.instance;
        if (!db) return null;
        if (db != recipesOf || db.m_recipes.Count != recipeCount) { recipeOf.Clear(); recipesOf = db; recipeCount = db.m_recipes.Count; }
        string key = item.m_shared.m_name ?? "";
        if (!recipeOf.TryGetValue(key, out var recipe)) recipeOf[key] = recipe = db.GetRecipe(item);
        return recipe;
    }
    static int Tier(ItemDrop.ItemData item, Recipe recipe)
    {
        if (!recipe) return Mathf.Min(9, item.m_quality);
        int station = recipe.m_craftingStation ? (stationRank.TryGetValue(recipe.m_craftingStation.name, out int r) ? r : 1) : 0;
        return station * 1000 + recipe.m_minStationLevel * 10 + Mathf.Min(9, item.m_quality);
    }
    public static string TierText(ItemDrop.ItemData item)
    {
        var recipe = ObjectDB.instance ? ObjectDB.instance.GetRecipe(item) : null;
        return recipe && recipe.m_craftingStation ? $"{recipe.m_craftingStation.name} {recipe.m_minStationLevel}, q{item.m_quality}" : $"no recipe, q{item.m_quality}";
    }

    // The shield on show: the best block power at its quality, then the higher quality, then the first in the chest.
    public static float Block(ItemDrop.ItemData item) => item.m_shared.m_blockPower + item.m_shared.m_blockPowerPerLevel * Mathf.Max(0, item.m_quality - 1);
}

static class ItemRules
{
    // Arrows and handheld bolts by the game's ammo type, whatever mod adds them (0.5.1, coverage: Joost's mods). Only ammo itself: a
    // bow names the ammo it shoots the same way ("$ammo_arrows"), and bows filled Fletcher's Barrels (Joost's test, 25 Oct).
    static bool Ammo(ItemDrop.ItemData i) => i.m_shared.m_itemType is ItemDrop.ItemData.ItemType.Ammo or ItemDrop.ItemData.ItemType.AmmoNonEquipable;
    public static bool Arrow(ItemDrop.ItemData i) => i.m_shared.m_ammoType == "$ammo_arrows" && Ammo(i) && EquipRules.Players(i);
    public static bool Bolt(ItemDrop.ItemData i) => i.m_shared.m_ammoType == "$ammo_bolts" && Ammo(i) && EquipRules.Players(i);
    public static bool ArrowOrBolt(ItemDrop.ItemData i) => Arrow(i) || Bolt(i);
    static ObjectDB forDb;
    static ZNetScene forScene;
    static readonly HashSet<string> made = new(), cooked = new(), roasted = new(), smelted = new(), fuel = new(), grown = new(), bars = new(), brewed = new(), brewing = new();
    static readonly List<(string station, ItemDrop from, ItemDrop to)> smelts = new();

    static void Refresh()
    {
        var db = ObjectDB.instance;
        var scene = ZNetScene.instance;
        if (db == forDb && scene == forScene) return;
        forDb = db;
        forScene = scene;
        foreach (var set in new[] { made, cooked, roasted, smelted, fuel, grown, bars, brewed, brewing }) set.Clear();
        if (db) foreach (var r in db.m_recipes) if (r && r.m_item) Add(made, r.m_item);
        if (scene)
            foreach (var p in scene.m_prefabs)
            {
                if (!p) continue;
                if (p.GetComponent<CookingStation>() is { } cs)
                    foreach (var c in cs.m_conversion)
                    {
                        if (c == null) continue;
                        Add(made, c.m_to);
                        if (!p.name.Contains("cookingstation")) continue;   // the fire's spit and the griddle, not the oven
                        Add(cooked, c.m_from);
                        Add(roasted, c.m_to);
                    }
                if (p.GetComponent<Fermenter>() is { } f) foreach (var c in f.m_conversion) if (c != null) { Add(made, c.m_to); Add(brewed, c.m_to); Add(brewing, c.m_from); }
                // Bars: what the coal-fired smelters (smelter, blast furnace) make. Not every Smelter: the charcoal kiln is one too
                // and made coal count as metal (Joost: Store All put coal on a Metal Rack).
                if (p.GetComponent<Smelter>() is { } sm && sm.m_fuelItem && sm.m_fuelItem.name == "Coal")
                {
                    Add(fuel, sm.m_fuelItem);
                    foreach (var c in sm.m_conversion) if (c != null && c.m_from && c.m_to) smelts.Add((p.name, c.m_from, c.m_to));
                }
                if (p.GetComponent<Plant>() is { } plant)
                    foreach (var g in plant.m_grownPrefabs)
                        if (g && g.GetComponent<Pickable>() is { } pick && pick.m_itemPrefab) Add(grown, pick.m_itemPrefab.GetComponent<ItemDrop>());
            }
        // Ore and bars: not food. A mod's coal-fired smoker is a Smelter too, and made raw bear meat ore (Joost, 27 Oct, f17: bear meat
        // in the Ore Bin, and its refusal said "goes in the Meat Rack or the Ore Bin"): what the cooking station takes, fish, and
        // anything edible in or out stay out of both.
        static bool Edible(ItemDrop d) => d.m_itemData?.m_shared is { } s && (s.m_food > 0f || s.m_foodStamina > 0f || s.m_foodEitr > 0f
            || s.m_itemType is ItemDrop.ItemData.ItemType.Fish or ItemDrop.ItemData.ItemType.Consumable);
        var left = new List<string>();
        foreach (var (station, from, to) in smelts)
        {
            if (cooked.Contains(from.m_itemData?.m_shared?.m_name ?? "") || Edible(from) || Edible(to)) { left.Add($"{from.name} ({station})"); continue; }
            Add(smelted, from);
            Add(bars, to);
        }
        if (left.Count > 0) Plugin.Log.LogInfo($"Item types: food a coal-fired station takes, not ore: {string.Join(", ", left.Distinct())}.");
        smelts.Clear();
        if (db && scene)
            Plugin.Log.LogInfo($"Item types: {made.Count} made items, {cooked.Count} raw for the cooking station, {smelted.Count} smelter inputs, "
                + $"{fuel.Count} smelter fuel(s), {grown.Count} crop yields, {brewing.Count} fermenter bases, {brewed.Count} fermenter drinks.");
    }

    static void Add(HashSet<string> set, ItemDrop d)
    {
        var n = d ? d.m_itemData?.m_shared?.m_name : null;
        if (n != null) set.Add(n);
    }

    static bool Consumable(ItemDrop.ItemData i) => i.m_shared.m_itemType == ItemDrop.ItemData.ItemType.Consumable;
    static bool Food(ItemDrop.ItemData i) => i.m_shared.m_food > 0f || i.m_shared.m_foodStamina > 0f || i.m_shared.m_foodEitr > 0f;

    public static bool Mead(ItemDrop.ItemData i)
    {
        Refresh();
        return StorageReviewPolicy.MeadProduct(Consumable(i), Food(i), brewed.Contains(i.m_shared.m_name) || brewing.Contains(i.m_shared.m_name),
            i.m_dropPrefab ? i.m_dropPrefab.name : null);
    }
    public static bool ArcaneCore(ItemDrop.ItemData i) => i.m_dropPrefab && i.m_dropPrefab.name == "SurtlingCore";
    // The Treasure Hoard's gold (Joost, 27 Oct: "munten en goud"): a material or misc item, so no gold weapon, shield, armour, ammo or
    // trinket (TrinketBloodGoldStamina is worn), that no coal-fired smelter takes (gold ore is the Ore Bin's), named for coin or gold.
    // In his game: Coins, AncientCoin and the Gold bar.
    public static bool CoinOrGold(ItemDrop.ItemData i)
    {
        if (!i.m_dropPrefab || i.m_shared.m_itemType is not (ItemDrop.ItemData.ItemType.Material or ItemDrop.ItemData.ItemType.Misc)) return false;
        Refresh();
        return !smelted.Contains(i.m_shared.m_name) && StorageReviewPolicy.CoinOrGoldName(i.m_dropPrefab.name);
    }
    public static bool Jewel(ItemDrop.ItemData i) => i.m_dropPrefab && StorageReviewPolicy.JewelName(i.m_dropPrefab.name);
    public static bool Meal(ItemDrop.ItemData i) { Refresh(); return Consumable(i) && Food(i) && made.Contains(i.m_shared.m_name); }
    public static bool Supplies(ItemDrop.ItemData i) => Mead(i) || Meal(i);
    // Raw meat and fish, what the spit and griddle make of them (Joost: cooked meat and fish belong on the Meat Rack too), and
    // the animal parts that go into food and meads ("only the ones for food, meads and crafting edibles", Joost, 22 Oct):
    // entrails (sausages), blood clot (stuffed mushroom), blood bag (blood pudding), freeze gland (frost resistance mead). By
    // the items' name tokens, in the code rather than the Accepts setting, so it holds with a config written by an older
    // version. Hides, bones, bile bags, hearts and other crafting parts stay out.
    static readonly HashSet<string> animalParts = new() { "$item_entrails", "$item_bloodclot", "$item_bloodbag", "$item_freezegland" };
    public static bool RawMeat(ItemDrop.ItemData i)
    {
        Refresh();
        var n = i.m_shared.m_name;
        return !Egg(i) && (i.m_shared.m_itemType == ItemDrop.ItemData.ItemType.Fish || cooked.Contains(n) || roasted.Contains(n) || animalParts.Contains(n));
    }

    // Raw eggs are farm produce: the Root Bin, not the Meat Rack (Joost, 22 Oct). A cooked egg is a meal (Larder Hutch); the
    // dragon egg is a boss offering and stays out.
    static readonly HashSet<string> eggs = new() { "$item_chicken_egg", "$item_voltureegg", "$item_asksvin_egg" };
    static bool Egg(ItemDrop.ItemData i) => eggs.Contains(i.m_shared.m_name);
    public static bool Plant(ItemDrop.ItemData i) { Refresh(); return Egg(i) || grown.Contains(i.m_shared.m_name) || (Consumable(i) && Food(i) && !made.Contains(i.m_shared.m_name)); }
    public static bool Ore(ItemDrop.ItemData i) { Refresh(); return smelted.Contains(i.m_shared.m_name); }
    public static bool StoneCoal(ItemDrop.ItemData i) { Refresh(); return fuel.Contains(i.m_shared.m_name); }
    public static bool Metal(ItemDrop.ItemData i) { Refresh(); return bars.Contains(i.m_shared.m_name); }
}

// Skin mode: on this PC only, a vanilla chest can wear one of the stores. Nothing goes over the network and nothing
// changes in the chest's world data: the choice lives in BepInEx/config/<id>.skins.json, keyed by the chest's ZDOID
// (which stays the same across sessions), and the chest keeps its own container, size, collider and behaviour.
// Other players see a normal chest.
static class Skins
{
    // none, the crib, then the stores (the emergency shelf with 1, 2 and 3 planks; packed from the chest's own grid)
    static readonly string[] Cycle = { null, "crib", "meadrack", "larder", "meatrack", "rootbin", "orebin", "bunker",
        "emergencyshelf_1", "emergencyshelf_2", "emergencyshelf_3" };
    static readonly Dictionary<string, string> chosen = new(StringComparer.Ordinal);

    static string SavePath => Path.Combine(BepInEx.Paths.ConfigPath, Plugin.Id + ".skins.json");
    static string Key(ZDOID id) => $"{id.UserID}:{id.ID}";

    public static void Load()
    {
        chosen.Clear();
        try
        {
            if (File.Exists(SavePath) && Json.Parse(File.ReadAllText(SavePath)) is Dictionary<string, object> d)
                foreach (var kv in d)
                    if (kv.Value is string s && Array.IndexOf(Cycle, s) > 0) chosen[kv.Key] = s;
        }
        catch (Exception e) { Plugin.Log.LogWarning($"Skins: could not read {SavePath} ({e.Message}); starting without skins."); }
        Plugin.Log.LogInfo($"Skins: {chosen.Count} skinned chest(s) remembered ({SavePath}).");
    }

    static void Save()
    {
        var sb = new StringBuilder("{");
        int i = 0;
        foreach (var kv in chosen.OrderBy(k => k.Key, StringComparer.Ordinal))
            sb.Append(i++ > 0 ? "," : "").Append("\n  \"").Append(kv.Key).Append("\": \"").Append(kv.Value).Append('"');
        sb.Append("\n}\n");
        try
        {
            var tmp = SavePath + ".tmp";
            File.WriteAllText(tmp, sb.ToString());
            File.Copy(tmp, SavePath, true);
            File.Delete(tmp);
        }
        catch (Exception e) { Plugin.Log.LogWarning($"Skins: could not save {SavePath} ({e.Message})."); }
    }

    public static string Title(string key) => key == "crib" ? Kinds.Crib.Title : Store(key)?.Title ?? key;
    static Kind Store(string key) => Kinds.Stores.FirstOrDefault(k => k.Prefab == "piece_storehouse_" + key);

    public static StoreModel Model(string key) => Store(key) is { } k ? StoreModel.Get(k.Slug, k.Piece, k.Title) : null;

    public static void CheckHotkey()
    {
        if (Settings.SkinChests == null || !Settings.SkinChests.Value || !Settings.SkinKey.Value.IsDown()) return;
        var player = Player.m_localPlayer;
        if (!player || global::Console.IsVisible() || TextInput.IsVisible() || Menu.IsVisible() || InventoryGui.IsVisible()
            || Minimap.InTextInput() || (Chat.instance && Chat.instance.HasFocus())) return;
        var hover = player.GetHoverObject();
        var container = hover ? hover.GetComponentInParent<Container>() : null;
        if (!container) { Notice.Show("Skin: look at a chest first"); return; }
        var nview = container.GetComponentInParent<ZNetView>();
        var zdo = nview && nview.IsValid() ? nview.GetZDO() : null;
        if (zdo == null) return;
        var root = nview.gameObject;
        if (Kinds.ByToken(container.m_name) != null) { Notice.Show("Skin: Storehouse pieces keep their own look"); return; }
        if (!root.GetComponent<Piece>() || root.GetComponentInParent<Vagon>() || root.GetComponentInParent<Ship>())
        {
            Notice.Show("Skin: only for chests that are building pieces");
            return;
        }
        var key = Key(zdo.m_uid);
        chosen.TryGetValue(key, out var current);
        var next = Cycle[(Array.IndexOf(Cycle, current) + 1) % Cycle.Length];
        if (next == null) chosen.Remove(key); else chosen[key] = next;
        Save();
        bool shown = SkinState.Set(root, next);
        Notice.Show("Skin: " + (next == null ? "none" : Title(next) + (shown ? "" : " (no model, see log)")));
        Plugin.Log.LogInfo($"Skins: {root.name} {key} -> {next ?? "none"}.");
    }

    // A chest came into view (Container.Awake): put its remembered skin on.
    public static void Apply(Container c)
    {
        if (Settings.SkinChests == null || !Settings.SkinChests.Value || chosen.Count == 0 || Kinds.ByToken(c.m_name) != null) return;
        var nview = c.GetComponentInParent<ZNetView>();
        var zdo = nview ? nview.GetZDO() : null;
        if (zdo != null && chosen.TryGetValue(Key(zdo.m_uid), out var key)) SkinState.Set(nview.gameObject, key);
    }

    // "Skin chests" switched: off takes every skin off (the choices stay saved), on puts them back.
    public static void Refresh()
    {
        if (!Settings.SkinChests.Value)
        {
            foreach (var s in UnityEngine.Object.FindObjectsByType<SkinState>(FindObjectsSortMode.None)) SkinState.Set(s.gameObject, null);
            return;
        }
        foreach (var c in UnityEngine.Object.FindObjectsByType<Container>(FindObjectsSortMode.None)) Apply(c);
    }
}

// On a skinned chest: hides the chest's own renderers (locally, renderer.enabled) and shows the store as a child.
// Taking the skin off turns the same renderers back on.
sealed class SkinState : MonoBehaviour
{
    string key;
    bool started;
    GameObject vis;
    readonly List<Renderer> hidden = new();

    // False when the skin's model is not loaded (the chest then keeps its own look).
    public static bool Set(GameObject root, string key)
    {
        var s = root.GetComponent<SkinState>();
        if (key == null)
        {
            if (s) { s.Restore(); Destroy(s); }
            return true;
        }
        if (!s) s = root.AddComponent<SkinState>();
        s.key = key;
        return !s.started || s.Apply();   // a new one applies in Start, when the chest is fully set up
    }

    void Start()
    {
        started = true;
        Apply();
    }

    bool Apply()
    {
        Restore();
        vis = key == "crib" ? CribModel.Skin(transform) : Skins.Model(key)?.BuildSkin(transform);
        if (!vis)
        {
            Plugin.Log.LogWarning($"Skins: no model for '{key}'; {name} keeps its own look.");
            return false;
        }
        foreach (var r in GetComponentsInChildren<Renderer>(true))
            if (r.enabled && !r.transform.IsChildOf(vis.transform)) { r.enabled = false; hidden.Add(r); }
        return true;
    }

    void Restore()
    {
        foreach (var r in hidden) if (r) r.enabled = true;
        hidden.Clear();
        if (vis) Destroy(vis);   // StoreContents or CribFill go with it
        vis = null;
    }

    void OnDestroy() => Restore();
}

#if !RELEASE
// storehouse_posecapture (M, 27 Oct: Joost wants every mannequin in the vanilla Armor Stand pose, "I think we need to do this"; the Sol
// pose round needs the native skeleton as Unity evaluates it): the vanilla ArmorStand_Male's "Player Pose" copied off-screen as the
// mannequin baker copies it (no ZNetView, no ZDO, nothing networked; its scripts and cloth removed, its renderers off), its own
// Animator with its own controller and avatar played at Pose 0, Base Layer.Pose_Upright, time 0, and every bone under Visual
// written as Visual.worldToLocalMatrix * bone.localToWorldMatrix, row-major (M's CaptureArmorStandPose, schema
// storehouse-native-pose-capture/1). The copy is destroyed in the same call.
static class PoseCapture
{
    [Serializable] public sealed class Bone
    {
        public string name, path, parent;
        public float[] visualLocalMatrixRowMajor;
    }
    [Serializable] public sealed class Capture
    {
        public string schema = "storehouse-native-pose-capture/1";
        public string sourcePrefab = "ArmorStand_Male";
        public string stateName = "Base Layer.Pose_Upright";
        public int poseParameter = 0;
        public float sampleTimeSeconds = 0;
        public string controllerName, avatarName;
        public float[] visualLocalScale;
        public Bone[] bones;
    }

    // Joost's 18:20 capture was the rig's bind pose (the models session: 76 bones equal the reference to 0.000006 degrees, arms 32
    // degrees out): the copy's renderers are off, so its Animator (culling by renderer) never wrote the pose, and Update(0) right
    // after Play had nothing evaluated yet. Now: always animate, a control pose first, Pose_Upright read a few frames later after
    // LateUpdate, and the capture refused when it still equals the bind pose.
    public static void Run(Terminal.ConsoleEventArgs args)
    {
        var stand = ZNetScene.instance ? ZNetScene.instance.GetPrefab("ArmorStand_Male") : null;
        var pose = stand ? stand.transform.Find("Player Pose") : null;
        if (!pose) { args.Context.AddString("Storehouse: no ArmorStand_Male/Player Pose in this game (in a world?)."); return; }
        var holder = new GameObject("storehouse_posecapture");
        holder.SetActive(false);   // nothing of the copy wakes up before its scripts are gone
        holder.transform.position = new Vector3(0f, -5000f, 0f);
        try
        {
            var copy = UnityEngine.Object.Instantiate(pose.gameObject, holder.transform, false);
            foreach (var mb in copy.GetComponentsInChildren<MonoBehaviour>(true)) UnityEngine.Object.DestroyImmediate(mb);
            foreach (var c in copy.GetComponentsInChildren<Cloth>(true)) UnityEngine.Object.DestroyImmediate(c);
            foreach (var r in copy.GetComponentsInChildren<Renderer>(true)) r.enabled = false;
            holder.SetActive(true);
            var visual = copy.transform.Find("Visual");
            if (!visual) throw new InvalidOperationException("Player Pose/Visual missing");
            var animator = visual.GetComponent<Animator>();
            if (!animator || !animator.avatar || !animator.isHuman) throw new InvalidOperationException("no humanoid Animator/Avatar on Visual");
            if (!animator.HasState(0, Animator.StringToHash("Base Layer.Pose_Upright"))) throw new InvalidOperationException("the controller has no Base Layer.Pose_Upright");
            animator.cullingMode = AnimatorCullingMode.AlwaysAnimate;   // its renderers are off
            animator.enabled = true;
            animator.Rebind();
            var run = holder.AddComponent<PoseRun>();
            run.StartCoroutine(run.Go(animator, visual, args.Context, holder));
            args.Context.AddString("Storehouse: pose capture running (a few frames).");
        }
        catch (Exception e)
        {
            Plugin.Log.LogError($"Storehouse: pose capture failed ({e}).");
            args.Context.AddString($"Storehouse: pose capture failed ({e.Message}); see the log.");
            UnityEngine.Object.Destroy(holder);
        }
    }

    sealed class PoseRun : MonoBehaviour
    {
        public System.Collections.IEnumerator Go(Animator animator, Transform visual, Terminal context, GameObject holder)
        {
            int upright = Animator.StringToHash("Base Layer.Pose_Upright");
            var bind = Snapshot(visual);   // after Rebind, before anything evaluated: the rig's reference pose
            animator.SetInteger("Pose", 1);   // a control: another pose must give other bones
            animator.Update(0.5f);
            yield return null;
            yield return new WaitForEndOfFrame();
            var control = Snapshot(visual);
            animator.SetInteger("Pose", 0);
            animator.Play(upright, 0, 0f);
            animator.Update(0f);
            yield return null;
            yield return null;
            yield return new WaitForEndOfFrame();   // after LateUpdate
            try
            {
                var state = animator.GetCurrentAnimatorStateInfo(0);
                var clips = animator.GetCurrentAnimatorClipInfo(0);
                string clip = clips.Length > 0 && clips[0].clip ? clips[0].clip.name : "none";
                var now = Snapshot(visual);
                var (fromBind, fromBindDeg) = Diff(now, bind);
                var (fromControl, fromControlDeg) = Diff(now, control);
                string facts = $"enabled {animator.enabled}, initialized {animator.isInitialized}, human {animator.isHuman}, culling {animator.cullingMode}, "
                    + $"state {(state.fullPathHash == upright ? "Pose_Upright" : state.fullPathHash.ToString())}, clip {clip}, frame {Time.frameCount}; "
                    + $"from the bind pose {fromBind * 1000f:F1} mm / {fromBindDeg:F1} deg, from the control pose {fromControl * 1000f:F1} mm / {fromControlDeg:F1} deg";
                if (state.fullPathHash != upright || fromBindDeg < 1f && fromBind < 0.005f)
                {
                    string no = $"Storehouse: pose capture NOT written: {(state.fullPathHash != upright ? "Pose_Upright is not the current state" : "the bones still equal the bind pose")} ({facts}).";
                    Plugin.Log.LogWarning(no);
                    context?.AddString(no);
                    yield break;
                }
                var capture = new Capture
                {
                    controllerName = animator.runtimeAnimatorController.name,
                    avatarName = animator.avatar.name,
                    visualLocalScale = new[] { visual.localScale.x, visual.localScale.y, visual.localScale.z },
                    bones = visual.GetComponentsInChildren<Transform>(true).Where(t => t != visual).Select(t =>
                    {
                        var m = visual.worldToLocalMatrix * t.localToWorldMatrix;
                        var values = new float[16];
                        for (int row = 0; row < 4; row++)
                            for (int col = 0; col < 4; col++)
                                values[row * 4 + col] = m[row, col];
                        return new Bone { name = t.name, path = PathFrom(t, visual), parent = t.parent ? t.parent.name : "", visualLocalMatrixRowMajor = values };
                    }).ToArray(),
                };
                var file = Path.Combine(BepInEx.Paths.CachePath, "armorstand-pose-capture.json");
                File.WriteAllText(file, ToJson(capture));   // not JsonUtility: it writes no array of our own classes from a ScriptEngine copy (27 Oct: no bones)
                var must = new[] { "RightHand_Attach", "LeftHand_Attach", "Helmet_attach" };
                var missing = must.Where(n => capture.bones.All(b => b.name != n)).ToList();
                string line = $"Storehouse: pose capture, {capture.bones.Length} bones of {capture.avatarName} ({capture.controllerName}) in Pose_Upright written to {file}"
                    + (missing.Count > 0 ? $"; MISSING {string.Join(", ", missing)}" : "; RightHand_Attach, LeftHand_Attach and Helmet_attach in it") + $" ({facts}).";
                Plugin.Log.LogInfo(line);
                context?.AddString(line);
            }
            finally { Destroy(holder); }
        }

        static Dictionary<Transform, Matrix4x4> Snapshot(Transform visual) =>
            visual.GetComponentsInChildren<Transform>(true).Where(t => t != visual).ToDictionary(t => t, t => visual.worldToLocalMatrix * t.localToWorldMatrix);

        // The largest change of any bone between two snapshots: its position (m) and its rotation (degrees).
        static (float, float) Diff(Dictionary<Transform, Matrix4x4> a, Dictionary<Transform, Matrix4x4> b)
        {
            float pos = 0f, deg = 0f;
            foreach (var kv in a)
                if (b.TryGetValue(kv.Key, out var o))
                {
                    pos = Mathf.Max(pos, Vector3.Distance(kv.Value.GetColumn(3), o.GetColumn(3)));
                    deg = Mathf.Max(deg, Quaternion.Angle(kv.Value.rotation, o.rotation));
                }
            return (pos, deg);
        }
    }

    static string PathFrom(Transform t, Transform root)
    {
        string path = t.name;
        while (t.parent && t.parent != root) { t = t.parent; path = t.name + "/" + path; }
        return path;
    }

    // The capture as JsonUtility would write it (the same field names and order), every float round-trippable ("R").
    static string ToJson(Capture c)
    {
        static string Q(string v) => "\"" + (v ?? "").Replace("\\", "\\\\").Replace("\"", "\\\"") + "\"";
        static string F(float v) => v.ToString("R", CultureInfo.InvariantCulture);
        static string A(float[] v) => "[" + string.Join(", ", (v ?? new float[0]).Select(F)) + "]";
        var sb = new StringBuilder("{\n");
        sb.Append($"    \"schema\": {Q(c.schema)},\n    \"sourcePrefab\": {Q(c.sourcePrefab)},\n    \"stateName\": {Q(c.stateName)},\n");
        sb.Append($"    \"poseParameter\": {c.poseParameter},\n    \"sampleTimeSeconds\": {F(c.sampleTimeSeconds)},\n");
        sb.Append($"    \"controllerName\": {Q(c.controllerName)},\n    \"avatarName\": {Q(c.avatarName)},\n    \"visualLocalScale\": {A(c.visualLocalScale)},\n");
        sb.Append("    \"bones\": [\n");
        for (int i = 0; i < c.bones.Length; i++)
        {
            var b = c.bones[i];
            sb.Append($"        {{\"name\": {Q(b.name)}, \"path\": {Q(b.path)}, \"parent\": {Q(b.parent)}, \"visualLocalMatrixRowMajor\": {A(b.visualLocalMatrixRowMajor)}}}");
            sb.Append(i < c.bones.Length - 1 ? ",\n" : "\n");
        }
        sb.Append("    ]\n}\n");
        return sb.ToString();
    }
}

// Dev console commands for testing (Joost, 24 Oct: "can we spawn all those items at once instead of one by one?"). Look at a
// store (or stand within 6 m of one) and type:
//   storehouse_fill            two full stacks of every item the store takes
//   storehouse_fill 5          five of each;  storehouse_fill full   round after round until the store is full
//   storehouse_fill 3 Sap Tar  only these items (the Shelf takes anything, so name what to put on it)
//   storehouse_empty           takes everything out of that store (gone: a test world only)
// Each copy registers them again; the game's command list is keyed by name, so the newest copy's commands win.
static class DevFill
{
    public static void Register()
    {
        new Terminal.ConsoleCommand("storehouse_fill", "[n|full] [items...] fills the store you look at with what it takes", Fill);
        new Terminal.ConsoleCommand("storehouse_empty", "empties the store you look at (test worlds only)", Empty);
        new Terminal.ConsoleCommand("storehouse_coverage", "writes BepInEx/storehouse-coverage.md: every player item, its type, which stores take it", Coverage);
        new Terminal.ConsoleCommand("storehouse_timelapse", "[seconds=4] [loop|stop] the store you look at from empty to full in uneven steps over that many seconds (for recordings), then its contents back (local worlds only); loop: again and again until stop", SelfTest.Timelapse);
        new Terminal.ConsoleCommand("storehouse_posecapture", "writes BepInEx/cache/armorstand-pose-capture.json: the vanilla Armor Stand's skeleton evaluated in Pose_Upright (for the mannequins' re-pose)", PoseCapture.Run);
        new Terminal.ConsoleCommand("storehouse_routetest", "every way an item goes from the player into the store you look at, refused and taken items, counted before and after (local worlds only; BepInEx/cache/routetest.md)", RouteTest.Run);
        new Terminal.ConsoleCommand("storehouse_selftest", "[stock.json|restore|capture <tag>] [<n>s] the store you look at through the test states: a log line and three renders each, then its contents back (local worlds only); <n>s: each state stays on show n seconds; restore: the last saved contents; capture <tag>: every units-style store of the release set drawn in memory per test state, written to BepInEx/cache/selftest/capture-<tag>", SelfTest.Run);
    }

    internal static Container Target()
    {
        var player = Player.m_localPlayer;
        if (!player) return null;
        static bool Ours(Container c) => c && c.m_name != null && c.m_name.StartsWith("$piece_storehouse", StringComparison.Ordinal);
        // In free cam, the store the camera looks at (Joost via the models session, 27 Oct: recording a timelapse from free cam
        // filled the store by the character); else, or when it looks at none within 50 m, the character's as before.
        if (GameCamera.InFreeFly() && GameCamera.instance && GameCamera.instance.transform is { } cam)
        {
            var seen = Physics.RaycastAll(cam.position, cam.forward, 50f, ~0, QueryTriggerInteraction.Ignore).OrderBy(h => h.distance)
                .Select(h => h.collider.GetComponentInParent<Container>()).FirstOrDefault(Ours);
            if (seen) return seen;
        }
        var hovered = player.GetHoverObject() ? player.GetHoverObject().GetComponentInParent<Container>() : null;
        if (Ours(hovered)) return hovered;
        return UnityEngine.Object.FindObjectsByType<Container>(FindObjectsSortMode.None).Where(Ours)
            .Select(c => (c, d: (c.transform.position - player.transform.position).sqrMagnitude)).Where(x => x.d < 36f)
            .OrderBy(x => x.d).Select(x => x.c).FirstOrDefault();
    }

    internal static ItemDrop.ItemData Stack(GameObject prefab)
    {
        var data = prefab.GetComponent<ItemDrop>().m_itemData.Clone();
        data.m_dropPrefab = prefab;
        data.m_stack = Mathf.Max(1, data.m_shared.m_maxStackSize);
        return data;
    }

    static void Fill(Terminal.ConsoleEventArgs args)
    {
        var c = Target();
        var db = ObjectDB.instance;
        if (!c || !db) { args.Context.AddString("Storehouse: look at a store, or stand within 6 m of one."); return; }
        var inv = c.GetInventory();
        var filter = Filter.For(inv);
        int per = 2;
        bool full = false;
        var names = new List<string>();
        foreach (var a in args.Args.Skip(1))
            if (a.Equals("full", StringComparison.OrdinalIgnoreCase)) full = true;
            else if (int.TryParse(a, out int n)) per = Mathf.Clamp(n, 1, 100);
            else names.Add(a);
        var unshowable = new List<string>();
        var kinds = names.Count > 0
            ? names.Select(n => db.GetItemPrefab(n)).Where(p => p && p.GetComponent<ItemDrop>()).ToList()
            : Takes(c, out unshowable);
        if (kinds.Count == 0) { args.Context.AddString("Storehouse: no items to add (this store takes anything: name them, e.g. storehouse_fill 2 Coins Ruby)."); return; }
        c.GetComponent<ZNetView>()?.ClaimOwnership();
        int added = 0;
        var refused = new HashSet<string>(StringComparer.Ordinal);
        for (int round = 0; full || round < per; round++)
        {
            int before = added;
            foreach (var p in kinds)
            {
                if (!inv.HaveEmptySlot()) break;
                var stack = Stack(p);
                // What a player could put in: a bay store takes a new kind only while a bay is free (the coordinator, 25 Oct: a full
                // test fill showed seven kinds in six bays).
                if (filter != null && !filter.AllowsIn(inv, stack, out _)) { refused.Add(p.name); continue; }
                if (inv.AddItem(stack)) added++;
            }
            if (added == before || !inv.HaveEmptySlot()) break;
        }
        if (Mannequins.Is(Kinds.ByToken(c.m_name))) Mannequins.Sorted(c);   // whole outfits per row, as a sort leaves them
        string line = $"Storehouse: {added} stack(s) of {kinds.Count - refused.Count} kind(s) into {Localization.instance.Localize(c.m_name)} ({inv.GetAllItems().Count}/{inv.GetWidth() * inv.GetHeight()} slots): {string.Join(", ", kinds.Where(k => !refused.Contains(k.name)).Select(k => k.name))}"
            + (refused.Count > 0 ? $"; no bay left for {string.Join(", ", refused)}" : "")
            + (unshowable.Count > 0 ? $"; left out, no place in this model: {string.Join(", ", unshowable)}" : "");
        args.Context.AddString(line);
        Plugin.Log.LogInfo(line);
    }

    // Every kind the store takes and can show, every item type in turn (a helmet, a chest piece, a cape, a helmet...), not A to Z: a
    // full equipment store then holds some of each kind of place (Joost's test: the Armor Cabinet filled with A..C and its helmet
    // cubbies stayed empty). Only what it can show (the coordinator, 25 Oct: a full Fletcher's fill left 21 stacks unseen): a test
    // fill then looks like what a player can make. unshowable: what it takes but has no place for.
    internal static List<GameObject> Takes(Container c, out List<string> unshowable) => Takes(c.GetInventory(), out unshowable);

    internal static List<GameObject> Takes(Inventory inv, out List<string> unshowable)
    {
        unshowable = new List<string>();
        var filter = Filter.For(inv);
        var db = ObjectDB.instance;
        if (filter == null || !db) return new List<GameObject>();
        var kinds = db.m_items.Where(p => p && !p.name.StartsWith("JVLmock", StringComparison.Ordinal) && p.GetComponent<ItemDrop>()?.m_itemData?.m_shared != null
            && filter.Allows(Stack(p))).GroupBy(p => p.name).Select(g => g.First()).OrderBy(p => p.name).ToList();
        // The Timber Crib has no StoreModel (no slug: CribModel draws it) and shows its logs by fill, so all it takes is showable
        // (Joost, 27 Oct: storehouse_fill full did nothing on the crib; StoreModel.Get(null) threw and the selftest stopped too).
        if (Kinds.ByToken(inv.GetName()) is { Slug: not null } kind && StoreModel.Get(kind.Slug, kind.Piece, kind.Title) is { Ready: true } model)
        {
            var none = kinds.Where(p => !Showable(model, p)).Select(p => p.name).ToList();
            unshowable = none;
            kinds = kinds.Where(p => !none.Contains(p.name)).ToList();
        }
        return kinds.Select(p => (p, t: p.GetComponent<ItemDrop>().m_itemData.m_shared.m_itemType.ToString())).GroupBy(x => x.t)
            .SelectMany(g => g.Select((x, n) => (x.p, n, x.t))).OrderBy(x => x.n).ThenBy(x => x.t, StringComparer.Ordinal).Select(x => x.p).ToList();
    }

    // Whether the store's model has a place for one stack of this kind, asked the way its contents are drawn.
    static bool Showable(StoreModel m, GameObject prefab)
    {
        var item = Stack(prefab);
        if (m.Forms != null) return MannequinBaker.Wearable(prefab) && new Outfits.Piece { Type = item.m_shared.m_itemType.ToString() }.Slot != Outfits.Slot.None;
        if (m.Equip != null)
            return m.Allocate(new List<ItemDrop.ItemData> { item }, (it, turn) => ItemVisual.Get(it.m_dropPrefab) is { } v
                ? StoreModel.Turned(turn, v.TrueSize) : null)[0] >= 0;
        if (m.Cells != null) return m.Cells.Allocate(new Dictionary<string, float> { [prefab.name] = 1f }, 1, out _).Count > 0;
        if (m.Units.Count > 0 && m.Units[0].Group >= 0) return m.ByGroup(new List<string> { prefab.name }, new List<Vector2> { new Vector2(0.5f, 0.5f) }) is not { } r || r[0] >= 0;
        return true;
    }

    // Every item a player can hold (it has an icon), with its type, the stores that take it, and for the equipment pieces whether a
    // place fits it at true size. The exact version of work/storehouse-0.5/coverage.md (0.5.1).
    static void Coverage(Terminal.ConsoleEventArgs args)
    {
        var db = ObjectDB.instance;
        if (!db) return;
        var sb = new System.Text.StringBuilder("| Item | Name | Type | Stores that take it | Shown in |\n|---|---|---|---|---|\n");
        int none = 0, total = 0;
        foreach (var p in db.m_items.Where(p => p && p.GetComponent<ItemDrop>()?.m_itemData?.m_shared != null).GroupBy(p => p.name).Select(g => g.First()).OrderBy(p => p.name))
        {
            var item = Stack(p);
            if (!EquipRules.Players(item)) continue;
            total++;
            var takers = Kinds.All.Where(k => k.Filter != null && k.Filter.Allows(item)).ToList();
            if (takers.Count == 0) none++;
            var shown = new List<string>();
            foreach (var k in takers)
            {
                var model = StoreModel.ForVis("storehouse_" + (k.Piece == null ? k.Slug : k.Slug + "_" + k.Piece));
                if (model?.Equip == null) continue;
                var fits = model.Allocate(new List<ItemDrop.ItemData> { item }, (it, turn) => ItemVisual.Get(it.m_dropPrefab) is { } v
                    ? StoreModel.Turned(turn, v.TrueSize) : null);
                shown.Add(k.Title + (fits[0] >= 0 ? "" : " (no place fits)"));
            }
            sb.Append($"| {p.name} | {Localization.instance.Localize(item.m_shared.m_name)} | {item.m_shared.m_itemType} | {string.Join(", ", takers.Select(k => k.Title))} | {string.Join(", ", shown)} |\n");
        }
        var path = Path.Combine(BepInEx.Paths.BepInExRootPath, "storehouse-coverage.md");
        File.WriteAllText(path, $"# Storehouse coverage ({Plugin.Version}, {DateTime.Now:yyyy-MM-dd HH:mm})\n\n{total} player items, {none} taken by no store.\n\n" + sb);
        args.Context.AddString($"Storehouse: coverage of {total} items written to {path} ({none} without a store).");
    }

    static void Empty(Terminal.ConsoleEventArgs args)
    {
        var c = Target();
        if (!c) { args.Context.AddString("Storehouse: look at a store, or stand within 6 m of one."); return; }
        c.GetComponent<ZNetView>()?.ClaimOwnership();
        int n = c.GetInventory().GetAllItems().Count;
        c.GetInventory().RemoveAll();
        args.Context.AddString($"Storehouse: {n} stack(s) taken out of {Localization.instance.Localize(c.m_name)}.");
    }
}

// storehouse_routetest (dev builds; Joost, 31 Oct: "I do want the complete fix" after Store All ate his backpacks): every way an item
// goes from the player into the store you look at, with an item the store refuses (a backpack, a plain item) and one it takes (into
// an empty place and onto a stack it already holds). Per case the item is counted in player plus store before and after: nothing
// may be lost and nothing doubled. One line per case in the log and BepInEx/cache/routetest.md. Both inventories are saved first and
// put back after. Only in a world this game hosts. Routes from other mods (Quick Stack's Store All, Quick Stack, Restock) run when
// that mod is installed and are reported as skipped when it isn't.
static class RouteTest
{
    sealed class Case { public string Route, Item, Kind; public int Before, After, InStore, WithPlayer; public bool Pass; public string Note; }

    public static void Run(Terminal.ConsoleEventArgs args)
    {
        if (!ZNet.instance || !ZNet.instance.IsServer() || ZNet.instance.IsDedicated()) { args.Context.AddString("Storehouse: the route test runs only in a world this game hosts."); return; }
        var c = DevFill.Target();
        var player = Player.m_localPlayer;
        if (!c || !player) { args.Context.AddString("Storehouse: look at a store, or stand within 6 m of one."); return; }
        var f = Filter.For(c.GetInventory());
        if (f == null) { args.Context.AddString("Storehouse: that store has no rules to test."); return; }
        Inventory pinv = player.GetInventory(), sinv = c.GetInventory();
        string title = Localization.instance.Localize(c.m_name);
        var pSaved = new ZPackage(); pinv.Save(pSaved);
        var sSaved = new ZPackage(); sinv.Save(sSaved);
        var cases = new List<Case>();
        try
        {
            InventoryGui.instance.Show(c);
            var takes = ObjectDB.instance.m_items.Select(p => p ? p.GetComponent<ItemDrop>() : null)
                .Where(d => d && d.m_itemData?.m_shared != null && d.m_itemData.m_shared.m_maxStackSize > 3 && f.AllowsIn(sinv, d.m_itemData, out _, 1))
                .Select(d => d.gameObject.name).FirstOrDefault();
            var plain = new[] { "Wood", "Stone", "Resin", "Flint", "Coins", "Feathers" }
                .FirstOrDefault(n => ObjectDB.instance.GetItemPrefab(n) is { } p && !f.AllowsIn(sinv, p.GetComponent<ItemDrop>().m_itemData, out _, 1));
            var backpack = new[] { "BackpackMeadows", "BackpackSwamp", "CapeIronBackpack" }.FirstOrDefault(n => ObjectDB.instance.GetItemPrefab(n));
            var items = new List<(string name, string kind, bool stackFirst)>();
            if (backpack != null) items.Add((backpack, "refused: backpack", false));
            if (plain != null) items.Add((plain, "refused: plain item", false));
            if (takes != null) { items.Add((takes, "taken: into an empty place", false)); items.Add((takes, "taken: onto a stack it holds", true)); }
            var qss = AccessTools.TypeByName("QuickStackStore.StoreTakeAllModule");
            var qssStack = AccessTools.TypeByName("QuickStackStore.QuickStackModule");
            var qssRestock = AccessTools.TypeByName("QuickStackStore.RestockModule");
            var grid = AccessTools.FieldRefAccess<InventoryGui, InventoryGrid>("m_containerGrid")(InventoryGui.instance);
            var routes = new List<(string name, Func<ItemDrop.ItemData, string> run)>
            {
                ("shift-click", it => { sinv.MoveItemToThis(pinv, it); return null; }),
                ("drag and drop", it =>
                {
                    var on = sinv.GetAllItems().FirstOrDefault(i => i.m_shared.m_name == it.m_shared.m_name)?.m_gridPos ?? FirstFree(sinv);
                    // The grid learns its inventory in the GUI's next Update; the test runs within this frame, so tell it now.
                    AccessTools.FieldRefAccess<InventoryGrid, Inventory>("m_inventory")(grid) = sinv;
                    grid.DropItem(pinv, it, it.m_stack, on);
                    return null;
                }),
                ("Place stacks (vanilla)", it => { sinv.StackAll(pinv); return null; }),
                ("Store All (Quick Stack mod)", it => Call(qss, "StoreAllItemsInOrder", player)),
                ("Quick Stack (Quick Stack mod)", it => Call(qssStack, "DoQuickStack", player, true, null)),
                ("Restock (Quick Stack mod)", it => Call(qssRestock, "DoRestock", player, true)),
            };
            foreach (var (route, run) in routes)
                foreach (var (name, kind, stackFirst) in items)
                {
                    pinv.RemoveAll(); sinv.RemoveAll();
                    if (stackFirst) sinv.AddItem(name, 1, 1, 0, 0, "", false);
                    var it = pinv.AddItem(name, kind.StartsWith("taken") ? 3 : 1, 1, 0, 0, "", new Vector2i(3, 2), false);
                    if (it == null) { cases.Add(new Case { Route = route, Item = name, Kind = kind, Note = "could not give the player the item" }); continue; }
                    var k = new Case { Route = route, Item = name, Kind = kind, Before = Count(pinv, name) + Count(sinv, name) };
                    try { k.Note = run(it); }
                    catch (Exception e) { var x = e.InnerException ?? e; k.Note = "threw " + x.GetType().Name + ": " + x.Message; Plugin.Log.LogError($"Route test {route}: {x}"); }
                    k.WithPlayer = Count(pinv, name); k.InStore = Count(sinv, name); k.After = k.WithPlayer + k.InStore;
                    k.Pass = k.Note == "skipped" || k.After == k.Before && !(kind.StartsWith("refused") && k.InStore > 0) && k.Note == null;
                    cases.Add(k);
                }
        }
        finally
        {
            pinv.RemoveAll(); sinv.RemoveAll();
            pSaved.SetPos(0); pinv.Load(pSaved);
            sSaved.SetPos(0); sinv.Load(sSaved);
            InventoryGui.instance.Hide();
        }
        var sb = new StringBuilder($"# Route test: {title}, Storehouse {Plugin.Version}, {DateTime.Now:yyyy-MM-dd HH:mm}\n\n| route | item | case | before | after (player + store) | result |\n|---|---|---|---|---|---|\n");
        foreach (var k in cases)
        {
            string res = k.Note == "skipped" ? "skipped (mod not installed)" : k.Pass ? "PASS" : "FAIL" + (k.Note != null ? " (" + k.Note + ")" : "");
            sb.Append($"| {k.Route} | {k.Item} | {k.Kind} | {k.Before} | {k.After} ({k.WithPlayer} + {k.InStore}) | {res} |\n");
            var line = $"Route test {title}: {k.Route}, {k.Item} ({k.Kind}): {k.Before} -> {k.WithPlayer} with the player + {k.InStore} in the store: {res}";
            if (k.Pass) Plugin.Log.LogInfo(line); else Plugin.Log.LogError(line);
        }
        int fails = cases.Count(k => !k.Pass);
        sb.Append($"\n{cases.Count} case(s), {fails} failed.\n");
        var dir = Path.Combine(BepInEx.Paths.BepInExRootPath, "cache"); Directory.CreateDirectory(dir);
        File.WriteAllText(Path.Combine(dir, "routetest.md"), sb.ToString());
        Plugin.Log.LogInfo($"Route test {title}: {cases.Count} case(s), {fails} failed; BepInEx/cache/routetest.md");
        args.Context.AddString($"Storehouse: route test of the {title}: {cases.Count} case(s), {fails} failed (BepInEx/cache/routetest.md).");
    }

    static string Call(Type t, string method, params object[] a)
    {
        if (t == null) return "skipped";
        var m = AccessTools.Method(t, method);
        if (m == null) return "skipped";
        var ps = m.GetParameters();
        var full = ps.Select((p, i) => i < a.Length ? a[i] : p.HasDefaultValue ? p.DefaultValue : null).ToArray();
        m.Invoke(null, full);
        return null;
    }

    static int Count(Inventory inv, string prefab)
    {
        int n = 0;
        foreach (var i in inv.GetAllItems()) if (i.m_dropPrefab && i.m_dropPrefab.name == prefab) n += i.m_stack;
        return n;
    }

    static Vector2i FirstFree(Inventory inv)
    {
        for (int y = 0; y < inv.GetHeight(); y++)
            for (int x = 0; x < inv.GetWidth(); x++)
                if (inv.GetItemAt(x, y) == null) return new Vector2i(x, y);
        return new Vector2i(0, 0);
    }
}

// storehouse_selftest [stock.json] (dev builds; the coordinator's retro, 26 Oct): the store you look at through the test states
// (empty, one stack, 25/50/75%, one kind full, mixed full, and a stock file when given: a list of {prefab, stack}, a path or a
// name in BepInEx/cache). Per state one log line (held, drawn, places, refused with the reason, triangles), one line on the copies
// hidden from the front (Hidden, below) and three renders from fixed cameras (front, side, above) in BepInEx/cache/selftest/<store>/. The contents are saved first (also to a file there) and
// put back after. Only in a world this game hosts: never on someone else's server.
sealed class SelfTest : MonoBehaviour
{
    static SelfTest running;

    float pause;   // seconds each state stays on show after its pictures ("storehouse_selftest 3s"), so it can be watched

    public static void Run(Terminal.ConsoleEventArgs args)
    {
        if (running) { args.Context.AddString("Storehouse: a self-test is running."); return; }
        var a = args.Args.ToList();
        int pi = a.FindIndex(1, x => System.Text.RegularExpressions.Regex.IsMatch(x, @"^\d{1,2}(\.\d+)?s$"));
        float pause = pi > 0 ? float.Parse(a[pi].TrimEnd('s'), CultureInfo.InvariantCulture) : 0f;
        if (pi > 0) a.RemoveAt(pi);
        if (a.Count > 1 && a[1] == "capture")
        {
            string tag = a.Count > 2 ? a[2] : "";
            if (!System.Text.RegularExpressions.Regex.IsMatch(tag, "^[A-Za-z0-9_-]{1,32}$")) { args.Context.AddString("Storehouse: give the capture a name, e.g. storehouse_selftest capture before"); return; }
            if (!ObjectDB.instance || ObjectDB.instance.m_items.Count == 0) { args.Context.AddString("Storehouse: the items are not loaded yet."); return; }
            running = new GameObject("storehouse_selftest").AddComponent<SelfTest>();
            running.StartCoroutine(running.Capture(tag));
            args.Context.AddString($"Storehouse: capture '{tag}' started; one store state per frame, the result line in the log.");
            return;
        }
        if (!ZNet.instance || !ZNet.instance.IsServer() || ZNet.instance.IsDedicated()) { args.Context.AddString("Storehouse: the self-test runs only in a world this game hosts."); return; }
        var c = DevFill.Target();
        if (!c || Kinds.ByToken(c.m_name) is not { } kind) { args.Context.AddString("Storehouse: look at a store, or stand within 6 m of one."); return; }
        string stock = a.Count > 1 ? a[1] : null;
        // A test cut short (the world left mid-test: Unity skips the coroutine's finally): its saved contents back into this store.
        if (stock == "restore")
        {
            var folder = Folder(kind);
            var last = Directory.Exists(folder) ? Directory.GetFiles(folder, "contents-*.b64").OrderBy(f => f, StringComparer.Ordinal).LastOrDefault() : null;
            if (last == null) { args.Context.AddString("Storehouse: no saved contents for this store."); return; }
            c.GetComponent<ZNetView>()?.ClaimOwnership();
            c.GetInventory().RemoveAll();
            c.GetInventory().Load(new ZPackage(File.ReadAllText(last)));
            args.Context.AddString($"Storehouse: {c.GetInventory().GetAllItems().Count} stack(s) put back from {Path.GetFileName(last)}.");
            return;
        }
        if (stock != null && !File.Exists(stock)) stock = Path.Combine(BepInEx.Paths.CachePath, stock);
        if (stock != null && !File.Exists(stock)) { args.Context.AddString($"Storehouse: no stock file {a[1]}."); return; }
        running = new GameObject("storehouse_selftest").AddComponent<SelfTest>();
        running.pause = pause;
        running.StartCoroutine(running.States(c, kind, stock));
        args.Context.AddString($"Storehouse: self-test of the {kind.Title} started; results in the log and BepInEx/cache/selftest.");
    }

    // storehouse_timelapse (Joost, 27 Oct, recording GIFs): the store you look at fills from empty to full in uneven steps (a few
    // stacks, a few more, a jump) over the given seconds, each step drawn before the next, with what storehouse_fill full would put
    // in; then its own contents back, saved first as the self-test saves them (storehouse_selftest restore brings them back if the
    // world is left mid-run). loop: empty to full again and again until storehouse_timelapse stop.
    bool looping, stopping;

    public static void Timelapse(Terminal.ConsoleEventArgs args)
    {
        if (args.Args.Skip(1).Any(a => a.Equals("stop", StringComparison.OrdinalIgnoreCase)))
        {
            if (running && running.looping) { running.stopping = true; args.Context.AddString("Storehouse: the timelapse stops after this pass."); }
            else args.Context.AddString("Storehouse: no timelapse is looping.");
            return;
        }
        if (running) { args.Context.AddString("Storehouse: a self-test or timelapse is running."); return; }
        if (!ZNet.instance || !ZNet.instance.IsServer() || ZNet.instance.IsDedicated()) { args.Context.AddString("Storehouse: the timelapse runs only in a world this game hosts."); return; }
        var c = DevFill.Target();
        if (!c || Kinds.ByToken(c.m_name) is not { } kind) { args.Context.AddString("Storehouse: look at a store, or stand within 6 m of one."); return; }
        float seconds = 4f;
        foreach (var a in args.Args.Skip(1))
            if (float.TryParse(a.TrimEnd('s'), NumberStyles.Float, CultureInfo.InvariantCulture, out float f)) seconds = Mathf.Clamp(f, 1f, 60f);
        running = new GameObject("storehouse_selftest").AddComponent<SelfTest>();
        running.looping = args.Args.Skip(1).Any(a => a.Equals("loop", StringComparison.OrdinalIgnoreCase));
        running.StartCoroutine(running.Fill(c, kind, seconds));
        args.Context.AddString($"Storehouse: timelapse of the {kind.Title}, {seconds:F0} s{(running.looping ? ", looping (storehouse_timelapse stop)" : "")}.");
    }

    System.Collections.IEnumerator Fill(Container c, Kind kind, float seconds)
    {
        var inv = c.GetInventory();
        var dir = Folder(kind);
        Directory.CreateDirectory(dir);
        var saved = new ZPackage();
        inv.Save(saved);
        File.WriteAllText(Path.Combine(dir, $"contents-{DateTime.Now:yyyyMMdd-HHmmss}.b64"), saved.GetBase64());
        c.GetComponent<ZNetView>()?.ClaimOwnership();
        try
        {
            var kinds = DevFill.Takes(c, out _);
            int slots = inv.GetWidth() * inv.GetHeight();
            // Uneven steps, the same for this store every time: mostly 4-12% of the slots, now and then a jump of 20-30%.
            var rnd = new System.Random(slots * 31 + kinds.Count);
            var counts = new List<int> { 0 };
            while (counts[counts.Count - 1] < slots)
            {
                double part = rnd.NextDouble() < 0.2 ? 0.2 + rnd.NextDouble() * 0.1 : 0.04 + rnd.NextDouble() * 0.08;
                counts.Add(Math.Min(slots, counts[counts.Count - 1] + Math.Max(1, (int)(slots * part))));
            }
            float hold = seconds / (counts.Count - 1);
            var sc = c.GetComponentInChildren<StoreContents>();
            do
            {
                foreach (int n in counts)
                {
                    inv.RemoveAll();
                    Put(inv, kinds, n);   // the same order each time, so each step is the one before plus more
                    if (Mannequins.Is(kind)) Mannequins.Sorted(c);
                    var waited = System.Diagnostics.Stopwatch.StartNew();
                    while (sc && !sc.Current(inv) && waited.Elapsed.TotalSeconds < 5) { sc.CheckNow(); yield return null; }
                    yield return new WaitForSeconds(n == slots ? Mathf.Max(1f, hold) : hold);
                }
            } while (looping && !stopping);
        }
        finally
        {
            inv.RemoveAll();
            saved.SetPos(0);
            inv.Load(saved);   // saves the container again
            Plugin.Log.LogInfo($"Timelapse {kind.Title}: done, {inv.GetAllItems().Count} stack(s) put back.");
            running = null;
            Destroy(gameObject);
        }
    }

    // The crib has no slug: its own folder, not the selftest root (its contents file landed there).
    static string Folder(Kind kind) => Path.Combine(BepInEx.Paths.CachePath, "selftest", kind == Kinds.Crib ? "timbercrib" : kind.Slug + (kind.Piece == null ? "" : "_" + kind.Piece));

    System.Collections.IEnumerator States(Container c, Kind kind, string stock)
    {
        var inv = c.GetInventory();
        var dir = Folder(kind);
        Directory.CreateDirectory(dir);
        var saved = new ZPackage();
        inv.Save(saved);
        File.WriteAllText(Path.Combine(dir, $"contents-{DateTime.Now:yyyyMMdd-HHmmss}.b64"), saved.GetBase64());
        c.GetComponent<ZNetView>()?.ClaimOwnership();
        var cam = new GameObject("storehouse_selftest_camera").AddComponent<Camera>();
        cam.enabled = false;
        StoreContents watched = null;   // keeps its copies for the hidden check while the test runs
        try
        {
            var kinds = DevFill.Takes(c, out var unshowable);
            int slots = inv.GetWidth() * inv.GetHeight();
            var states = new List<(string name, Func<Dictionary<string, string>> put)>
            {
                ("empty", () => new Dictionary<string, string>()),
                ("one-stack", () => Put(inv, kinds.Take(1).ToList(), 1)),
                ("25pct", () => Put(inv, kinds, slots / 4)),
                ("50pct", () => Put(inv, kinds, slots / 2)),
                ("75pct", () => Put(inv, kinds, slots * 3 / 4)),
                ("one-kind-full", () => Put(inv, kinds.Take(1).ToList(), slots)),
                ("mixed-full", () => Put(inv, kinds, slots)),
            };
            if (stock != null) states.Add(("stock", () => PutStock(inv, stock)));
            if (unshowable.Count > 0) Plugin.Log.LogInfo($"Selftest {kind.Title}: takes but has no place for {string.Join(", ", unshowable)}.");
            foreach (var (name, put) in states)
            {
                inv.RemoveAll();
                var refused = put();
                if (Mannequins.Is(kind)) Mannequins.Sorted(c);
                // The store redraws this state before it is counted and pictured (it looks again only once a second, at most one
                // store per frame); a store that does not catch up in 10 s is logged and pictured as it is.
                var sc = c.GetComponentInChildren<StoreContents>();
                if (sc && sc.Seen == null) { sc.Seen = new StoreContents.Drawn(); watched = sc; }   // before its rebuild (next frame at the earliest)
                var waited = System.Diagnostics.Stopwatch.StartNew();
                while (sc && !sc.Current(inv) && waited.Elapsed.TotalSeconds < 10) { sc.CheckNow(); yield return null; }
                if (sc && !sc.Current(inv)) Plugin.Log.LogWarning($"Selftest {kind.Title} {name}: not redrawn within 10 s (contents off, or out of range?); counted and pictured as it is.");
                yield return null;   // drawn once with the new state
                var held = inv.GetAllItems();
                var model = kind.Slug != null ? StoreModel.Get(kind.Slug, kind.Piece, kind.Title) : null;   // the crib: logs by fill
                int places = model == null ? -1 : model.Equip?.Count ?? (model.Forms != null ? model.Forms.Count * 6 : model.Cells != null || model.Piles != null ? -1 : model.Units.Count);
                Plugin.Log.LogInfo($"Selftest {kind.Title} {name}: held {held.Select(i => i.m_dropPrefab ? i.m_dropPrefab.name : i.m_shared.m_name).Distinct().Count()} kind(s) in {held.Count}/{slots} slots; "
                    + $"drawn {sc?.CopiesShown ?? 0} copies, {sc?.UnrepresentedKindCount ?? 0} kind(s) unseen, {sc?.TrianglesShown ?? 0} triangles; "
                    + $"places {(places < 0 ? "by mass" : places.ToString())}; refused {(refused.Count == 0 ? "none" : string.Join(", ", refused.Select(kv => $"{kv.Key} ({kv.Value})")))}.");
                if (sc && sc.Seen != null)
                {
                    try { Hidden(cam, c, sc, kind, name, dir); }
                    catch (Exception e) { Plugin.Log.LogWarning($"Selftest {kind.Title} {name}: hidden check failed ({e})."); }
                }
                foreach (var view in new[] { "front", "side", "above" })
                {
                    Aim(cam, c, view);
                    var rt = RenderTexture.GetTemporary(1280, 800, 24);
                    cam.targetTexture = rt;
                    cam.enabled = true;
                    // The player out of the picture (they stand by the store): their renderers off for this one frame only.
                    var player = Player.m_localPlayer ? Player.m_localPlayer.GetComponentsInChildren<Renderer>().Where(r => r.enabled).ToList() : new List<Renderer>();
                    try
                    {
                        foreach (var r in player) r.enabled = false;
                        yield return new WaitForEndOfFrame();   // the camera draws with the frame, contents and all
                    }
                    finally { foreach (var r in player) if (r) r.enabled = true; }
                    cam.enabled = false;
                    var before = RenderTexture.active;
                    RenderTexture.active = rt;
                    var tex = new Texture2D(rt.width, rt.height, TextureFormat.RGB24, false);
                    tex.ReadPixels(new Rect(0, 0, rt.width, rt.height), 0, 0);
                    tex.Apply();
                    RenderTexture.active = before;
                    cam.targetTexture = null;
                    RenderTexture.ReleaseTemporary(rt);
                    File.WriteAllBytes(Path.Combine(dir, $"{name}-{view}.png"), tex.EncodeToPNG());
                    Destroy(tex);
                }
                if (pause > 0f) yield return new WaitForSeconds(pause);
            }
        }
        finally
        {
            inv.RemoveAll();
            saved.SetPos(0);
            inv.Load(saved);   // saves the container again
            Plugin.Log.LogInfo($"Selftest {kind.Title}: done, {inv.GetAllItems().Count} stack(s) put back; renders in {dir}.");
            if (watched) watched.Seen = null;
            if (cam) Destroy(cam.gameObject);
            running = null;
            Destroy(gameObject);
        }
    }

    // storehouse_selftest capture <tag> (the coordinator, 27 Oct: the gate for splitting the units display into a plan step): every
    // units-style store of the release set through the test states, in memory only. Per store an Inventory of its default size
    // (Columns x its default rows, not the Rows setting, so a changed setting can't move a capture), no container, no piece, no ZDO,
    // nothing networked; per state it is filled as above and drawn once by a StoreContents on an inactive object at a fixed spot (the
    // jitter is seeded by position), destroyed in the same frame. Written to BepInEx/cache/selftest/capture-<tag>/ (an older capture
    // of that name is moved aside, never deleted): per store <state>-inputs.json (grid, model files, the settings that shape the
    // drawing, the stock) and <state>-draw.json (what the rebuild reported and every part copy drawn), plus index.txt (each draw
    // file's sha256). The same code draws the same files: before and after a refactor they must be identical. Since the units style's
    // plan step (DisplayPlan.cs) inputs.json also holds "plan_model", what the plan read, and <state>-plan.json is the plan the game
    // made: planrun/ must make the same from plan_model alone (plan-gate.py).
    static readonly Vector3 CaptureAt = new(0f, -5000f, 0f);
    static readonly string[] CaptureStates = { "empty", "one-stack", "25pct", "50pct", "75pct", "one-kind-full", "mixed-full" };

    static bool UnitsStyle(StoreModel m) => m.Planks.Count == 0 && m.Forms == null && m.Cells == null && m.Piles == null && m.Equip == null && m.Units.Count > 0;

    System.Collections.IEnumerator Capture(string tag)
    {
        var root = Path.Combine(BepInEx.Paths.CachePath, "selftest", "capture-" + tag);
        var watch = System.Diagnostics.Stopwatch.StartNew();
        var index = new List<string>();
        var skipped = new List<string>();
        int stores = 0;
        try
        {
            if (Directory.Exists(root))
            {
                var aside = $"{root}-moved-{DateTime.Now:yyyyMMdd-HHmmss}";
                Directory.Move(root, aside);
                Plugin.Log.LogInfo($"Selftest capture {tag}: the earlier capture of that name moved to {aside}.");
            }
            foreach (var kind in Kinds.All.Where(k => k.Slug != null && Kinds.InRelease(k)))
            {
                var model = StoreModel.Get(kind.Slug, kind.Piece, kind.Title);
                if (!model.Ready) { skipped.Add($"{kind.Title} (no model loaded)"); continue; }
                if (!UnitsStyle(model)) continue;
                int w = kind.Width, h = kind.DefaultRows;
                var inv = w > 0 && h > 0 ? new Inventory(kind.Token, null, w, h) : null;
                if (inv == null || inv.GetWidth() != w || inv.GetHeight() != h) { skipped.Add($"{kind.Title} (no inventory)"); continue; }
                var kinds = DevFill.Takes(inv, out _);
                var dir = Path.Combine(root, kind.Slug + (kind.Piece == null ? "" : "_" + kind.Piece));
                Directory.CreateDirectory(dir);
                stores++;
                foreach (var state in CaptureStates)
                {
                    if (CaptureState(kind, model, inv, kinds, state, dir) is { } line) index.Add(line);
                    else skipped.Add($"{kind.Title} {state} (the rebuild failed, see above)");
                    yield return null;
                }
            }
            File.WriteAllText(Path.Combine(root, "index.txt"), $"Storehouse {Plugin.Version} capture {tag}, {DateTime.Now:yyyy-MM-dd HH:mm}\n" + string.Join("\n", index) + "\n");
        }
        finally
        {
            Plugin.Log.LogInfo($"Selftest capture {tag}: {stores} store(s), {index.Count} state(s) written, {skipped.Count} skipped"
                + (skipped.Count > 0 ? $" ({string.Join("; ", skipped)})" : "") + $", in {watch.Elapsed.TotalSeconds:F1} s; {root}.");
            running = null;
            Destroy(gameObject);
        }
    }

    // One store in one state: filled, drawn once off-world, both files written. The index line, or null when the rebuild failed.
    static string CaptureState(Kind kind, StoreModel model, Inventory inv, List<GameObject> kinds, string state, string dir)
    {
        static string Q(string v) => "\"" + (v ?? "").Replace("\\", "\\\\").Replace("\"", "\\\"") + "\"";
        int slots = inv.GetWidth() * inv.GetHeight();
        inv.RemoveAll();
        var refused = state switch
        {
            "one-stack" => Put(inv, kinds.Take(1).ToList(), 1),
            "25pct" => Put(inv, kinds, slots / 4),
            "50pct" => Put(inv, kinds, slots / 2),
            "75pct" => Put(inv, kinds, slots * 3 / 4),
            "one-kind-full" => Put(inv, kinds.Take(1).ToList(), slots),
            "mixed-full" => Put(inv, kinds, slots),
            _ => new Dictionary<string, string>(),
        };
        var go = new GameObject("storehouse_capture");
        go.SetActive(false);   // before the component: no OnEnable, so never in the draw list
        go.transform.position = CaptureAt;
        (List<string> parts, int copies, int unseen, long tris, (string inputs, string plan)? plan) drawn;
        try { drawn = go.AddComponent<StoreContents>().CaptureOnce(model, inv); }
        catch (Exception e) { Plugin.Log.LogError($"Selftest capture {kind.Title} {state}: the rebuild failed ({e})."); return null; }
        finally { DestroyImmediate(go); }
        var stock = inv.GetAllItems().Where(it => it?.m_shared != null).OrderBy(it => it.m_gridPos.y).ThenBy(it => it.m_gridPos.x)
            .Select(it => $"    {{\"prefab\": {Q(it.m_dropPrefab ? it.m_dropPrefab.name : it.m_shared.m_name)}, \"stack\": {it.m_stack}, \"max\": {it.m_shared.m_maxStackSize}, \"x\": {it.m_gridPos.x}, \"y\": {it.m_gridPos.y}}}");
        var modelFiles = (model.LoadedFiles ?? new string[0]).Select(f =>
        {
            using var sha = System.Security.Cryptography.SHA256.Create();
            string hex = File.Exists(f) ? BitConverter.ToString(sha.ComputeHash(File.ReadAllBytes(f))).Replace("-", "").ToLowerInvariant().Substring(0, 12) : "missing";
            return $"{Q(Path.GetFileName(Path.GetDirectoryName(f)) + "/" + Path.GetFileName(f))}: {Q(hex)}";
        });
        string inputs = "{\n"
            + $"  \"store\": {Q(kind.Title)}, \"state\": {Q(state)}, \"grid\": [{inv.GetWidth()}, {inv.GetHeight()}],\n"
            + $"  \"model_files\": {{{string.Join(", ", modelFiles)}}},\n"
            + $"  \"settings\": {{\"item_size\": {(kind.ItemSize?.Value ?? 1f).ToString("R", CultureInfo.InvariantCulture)}, \"max_tris_per_stack\": {Settings.MaxTrisPerStack.Value}, \"display\": {(kind.Display ? "true" : "false")}}},\n"
            + $"  \"refused\": {{{string.Join(", ", refused.Select(kv => $"{Q(kv.Key)}: {Q(kv.Value)}"))}}},\n"
            + "  \"stock\": [\n" + string.Join(",\n", stock) + "\n  ]"
            // What the units-style plan read (DisplayPlan.cs): planrun makes the plan again from this section alone.
            + (drawn.plan is { } pm ? ",\n  \"plan_model\": " + pm.inputs : "") + "\n}\n";
        string draw = "{\n"
            + $"  \"store\": {Q(kind.Title)}, \"state\": {Q(state)}, \"copies\": {drawn.copies}, \"kinds_unseen\": {drawn.unseen}, \"triangles\": {drawn.tris}, \"parts\": {drawn.parts.Count},\n"
            + "  \"drawn\": [\n" + string.Join(",\n", drawn.parts.Select(x => "    " + Q(x))) + "\n  ]\n}\n";
        File.WriteAllText(Path.Combine(dir, state + "-inputs.json"), inputs);
        File.WriteAllText(Path.Combine(dir, state + "-draw.json"), draw);
        if (drawn.plan is { } pf) File.WriteAllText(Path.Combine(dir, state + "-plan.json"), pf.plan);   // the plan the game made (plan-gate.py: planrun must make the same)
        using var digest = System.Security.Cryptography.SHA256.Create();
        string Sha(string text) => BitConverter.ToString(digest.ComputeHash(Encoding.UTF8.GetBytes(text))).Replace("-", "").ToLowerInvariant().Substring(0, 12);
        string drawSha = Sha(draw);
        return $"{Path.GetFileName(dir)}/{state}: draw {drawSha}, {inv.GetAllItems().Count} stack(s), {drawn.copies} copies, {drawn.unseen} kind(s) unseen, {drawn.tris} triangles, {drawn.parts.Count} parts"
            + (drawn.plan is { } ps ? $", plan {Sha(ps.plan)}" : ", no plan");
    }

    // Stacks of the kinds in turn until n are in; what the store refuses, with its reason.
    static Dictionary<string, string> Put(Inventory inv, List<GameObject> kinds, int n)
    {
        var refused = new Dictionary<string, string>(StringComparer.Ordinal);
        var filter = Filter.For(inv);
        int added = 0;
        while (added < n && inv.HaveEmptySlot() && kinds.Count > 0)
        {
            int before = added;
            foreach (var p in kinds)
            {
                if (added >= n || !inv.HaveEmptySlot()) break;
                var stack = DevFill.Stack(p);
                if (filter != null && !filter.AllowsIn(inv, stack, out string why)) { refused[p.name] = why ?? "refused"; continue; }
                if (inv.AddItem(stack)) added++;
            }
            if (added == before) break;
        }
        return refused;
    }

    static Dictionary<string, string> PutStock(Inventory inv, string file)
    {
        var refused = new Dictionary<string, string>(StringComparer.Ordinal);
        var filter = Filter.For(inv);
        foreach (var e in (Json.Parse(File.ReadAllText(file)) as List<object> ?? new List<object>()).OfType<Dictionary<string, object>>())
        {
            if (!(e.TryGetValue("prefab", out var pn) && pn is string name) || ObjectDB.instance.GetItemPrefab(name) is not { } prefab || !prefab.GetComponent<ItemDrop>()) continue;
            var stack = DevFill.Stack(prefab);
            if (e.TryGetValue("stack", out var n)) stack.m_stack = Mathf.Clamp(Convert.ToInt32(n), 1, stack.m_shared.m_maxStackSize);
            if (filter != null && !filter.AllowsIn(inv, stack, out string why)) { refused[name] = why ?? "refused"; continue; }
            if (!inv.AddItem(stack)) refused[name] = "no free slot";
        }
        return refused;
    }

    // Item 13 (Joost's list, 27 Oct): copies the counts call drawn that can't be seen from the front (the Bow Rack showed 3 of 4
    // bows at 8/8 drawn, the Shield Trough 7 of 8, Arsenal B empty-looking places at 32/32, the Spine 55 of 56 stacks). An id render
    // from the front camera, in tiles of one render texture: per bit of a copy's number one tile with the store (its frame, and what
    // it draws that is no item copy: boards, vessels, liquids, panels) and every copy in depth, then the copies with that bit where
    // they are front-most, so each pixel's front-most copy reads back bit by bit; one tile with everything (the store's outline); and
    // per copy one tile with it alone, its whole area. The shader (Hidden/Internal-Colored, in every Unity build) multiplies by the
    // mesh's own vertex colours, so a colour can't carry an id: it only blacks a white target (blend zero zero). Cull off, so a
    // flipped target's winding can't turn a copy inside out. A copy here is all one stack draws at one place (a heap's lumps in
    // their unit count once). Hidden: under 5% of its own area seen. One log line per state, and <state>-front-ids.png beside the
    // renders: each copy its own colour, the store grey, where a hidden copy lies magenta.
    const int TileW = 400, TileH = 250, TileCols = 40;   // one row (16000 px wide): no up/down convention between drawing and reading back can swap tiles
    static Material idDepth, idMark;

    // From both aisles (the models session, 27 Oct: Armory B's back-face places 35-45 face the back aisle, where Joost looks at them,
    // and the Spine has a far face): each copy is judged from the side it shows best to; <state>-front-ids.png and -back-ids.png.
    static void Hidden(Camera cam, Container c, StoreContents sc, Kind kind, string state, string dir)
    {
        string head = $"Selftest {kind.Title} {state}: from the front and back";
        if (!idDepth || !idMark)
        {
            var shader = Shader.Find("Hidden/Internal-Colored");
            if (!shader) { Plugin.Log.LogWarning($"{head}: no shader Hidden/Internal-Colored in this build; hidden check skipped."); return; }
            Material Make(UnityEngine.Rendering.BlendMode dst, bool zwrite)
            {
                var m = new Material(shader) { name = "storehouse_selftest_ids", hideFlags = HideFlags.HideAndDontSave };
                m.SetInt("_SrcBlend", (int)UnityEngine.Rendering.BlendMode.Zero);
                m.SetInt("_DstBlend", (int)dst);
                m.SetInt("_ZWrite", zwrite ? 1 : 0);
                m.SetInt("_ZTest", (int)UnityEngine.Rendering.CompareFunction.LessEqual);
                m.SetInt("_Cull", (int)UnityEngine.Rendering.CullMode.Off);
                return m;
            }
            idDepth = Make(UnityEngine.Rendering.BlendMode.One, true);    // depth only, the colour stays
            idMark = Make(UnityEngine.Rendering.BlendMode.Zero, false);   // black where it passes the depth test
        }
        var seen = sc.Seen;
        var root = sc.transform.localToWorldMatrix;
        IEnumerable<(Mesh mesh, int sub, Matrix4x4 m)> Parts(ItemVisual look, Matrix4x4 at)
        {
            foreach (var p in look.Parts)
            {
                if (!p.Mesh) continue;
                var m = root * at * p.M;
                for (int s = 0; s < p.Mesh.subMeshCount; s++)
                    if (p.Mats.Length > 0 && p.Mats[Mathf.Min(s, p.Mats.Length - 1)]) yield return (p.Mesh, s, m);   // the submeshes AddParts draws
            }
        }
        var copies = seen.Copies.GroupBy(x => (x.item, x.place))
            .Select(g => (name: $"{g.Key.item} at {g.Key.place}" + (g.Count() > 1 ? $" ({g.Count()} copies)" : ""), parts: g.SelectMany(x => Parts(x.look, x.at)).ToList()))
            .ToList();
        string notChecked = sc.CopiesShown > seen.Copies.Count ? $"; {sc.CopiesShown - seen.Copies.Count} drawn copies not checked (merged heap faces)" : "";
        if (copies.Count == 0) { Plugin.Log.LogInfo($"{head}: no item copies drawn to check{notChecked}."); return; }
        Aim(cam, c, "front");   // the game camera's culling mask: what it draws is what the store is
        var store = new List<(Mesh mesh, int sub, Matrix4x4 m)>();
        foreach (var r in c.GetComponentsInChildren<MeshRenderer>())
        {
            if (!r.enabled || (cam.cullingMask & (1 << r.gameObject.layer)) == 0 || !r.TryGetComponent<MeshFilter>(out var mf) || !mf.sharedMesh) continue;
            var mats = r.sharedMaterials;
            for (int s = 0; s < mf.sharedMesh.subMeshCount; s++)
                if (mats.Length > 0 && mats[Mathf.Min(s, mats.Length - 1)] is { } mat && mat && !Glass.SeeThrough(mat)) store.Add((mf.sharedMesh, s, r.localToWorldMatrix));
        }
        foreach (var (mat, part) in seen.Extras) if (part.mesh && mat && !Glass.SeeThrough(mat)) store.Add((part.mesh, part.subMeshIndex, root * part.transform));
        var views = new[] { "front", "back" }.Select(v => (view: v, m: Measure(cam, c, v, store, copies.Select(x => x.parts).ToList(), dir, state))).ToList();
        if (views.All(v => v.m == null)) { Plugin.Log.LogWarning($"{head}: the id render drew nothing (the store not in front of the camera?); hidden check not trusted."); return; }
        // Per copy the view it shows most of itself in.
        float Share((string view, Measured m) v, int k) => v.m == null || v.m.Alone[k] == 0 ? -1f : v.m.Shown[k] / (float)v.m.Alone[k];
        var best = Enumerable.Range(0, copies.Count).Select(k => views.OrderByDescending(v => Share(v, k)).First()).ToList();
        string Why(int k)
        {
            var m = best[k].m;
            if (m == null || m.Alone[k] == 0) return "no pixel from either aisle even alone";
            int byOthers = m.ByCopy[k].Values.Sum(), top = byOthers > 0 ? m.ByCopy[k].OrderByDescending(kv => kv.Value).First().Key : 0;
            string by = m.ByStore[k] >= byOthers ? "the store itself" : top <= copies.Count ? copies[top - 1].name : "copies at one depth";
            return $"{100f * m.Shown[k] / m.Alone[k]:F0}% seen from the {best[k].view}, covered mostly by {by}";
        }
        var hidden = Enumerable.Range(0, copies.Count).Where(k => Share(best[k], k) < 0.05f).ToList();
        var mostly = Enumerable.Range(0, copies.Count).Where(k => Share(best[k], k) >= 0.05f && Share(best[k], k) < 0.25f).ToList();
        int fromBack = Enumerable.Range(0, copies.Count).Count(k => best[k].view == "back" && Share(best[k], k) >= 0.05f);
        string List(List<int> ks) => ks.Count == 0 ? "" : ": " + string.Join("; ", ks.Select(k => $"{copies[k].name} ({Why(k)})"));
        Plugin.Log.LogInfo($"{head}: {copies.Count - hidden.Count} of {copies.Count} seen, {fromBack} of them best from the back (a stack at its place counts once; {seen.Copies.Count} item copies{notChecked}); "
            + $"hidden (under 5% of its own area) {hidden.Count}{List(hidden)}; mostly hidden (5-25%) {mostly.Count}{List(mostly)}.");
    }

    sealed class Measured { public int[] Alone, Shown, ByStore; public Dictionary<int, int>[] ByCopy; }

    // One view's id render (see above): per copy its whole area alone, what of it is front-most, and what covers the rest; the
    // picture <state>-<view>-ids.png. Null when the store is not in the picture at all.
    static Measured Measure(Camera cam, Container c, string viewName, List<(Mesh mesh, int sub, Matrix4x4 m)> store, List<List<(Mesh mesh, int sub, Matrix4x4 m)>> copies, string dir, string state)
    {
        Aim(cam, c, viewName);
        var view = cam.worldToCameraMatrix;
        var proj = Matrix4x4.Perspective(cam.fieldOfView, TileW / (float)TileH, cam.nearClipPlane, 200f);   // the renders' 1280x800 shape
        int bits = 1;
        while (1 << bits <= copies.Count) bits++;
        int tiles = bits + 1 + copies.Count, perAtlas = TileCols;
        var front = new int[TileW * TileH];   // per pixel its front-most copy's number + 1; 0: the store, or nothing
        var outline = new bool[TileW * TileH];
        var under = new bool[TileW * TileH];   // where a hidden copy lies
        var r = new Measured { Alone = new int[copies.Count], Shown = new int[copies.Count], ByStore = new int[copies.Count], ByCopy = new Dictionary<int, int>[copies.Count] };
        static Rect Tile(int t) => new(t * TileW, 0, TileW, TileH);
        var rt = RenderTexture.GetTemporary(TileW * TileCols, TileH, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.Linear);
        var tex = new Texture2D(TileW, TileH, TextureFormat.RGBA32, false, true);
        var cb = new UnityEngine.Rendering.CommandBuffer { name = "storehouse_selftest_ids" };
        var was = RenderTexture.active;
        try
        {
            for (int first = 0; first < tiles; first += perAtlas)
            {
                int n = Math.Min(perAtlas, tiles - first);
                cb.Clear();
                cb.SetRenderTarget(rt);
                cb.ClearRenderTarget(true, true, Color.white);
                cb.SetViewProjectionMatrices(view, proj);
                for (int t = 0; t < n; t++)
                {
                    int tile = first + t;
                    cb.SetViewport(Tile(t));
                    if (tile <= bits)
                    {
                        foreach (var p in store) cb.DrawMesh(p.mesh, p.m, tile == bits ? idMark : idDepth, p.sub);
                        foreach (var cp in copies) foreach (var p in cp) cb.DrawMesh(p.mesh, p.m, tile == bits ? idMark : idDepth, p.sub);
                        if (tile < bits)
                            for (int k = 0; k < copies.Count; k++)
                                if (((k + 1) >> tile & 1) != 0) foreach (var p in copies[k]) cb.DrawMesh(p.mesh, p.m, idMark, p.sub);
                    }
                    else foreach (var p in copies[tile - bits - 1]) cb.DrawMesh(p.mesh, p.m, idMark, p.sub);
                }
                Graphics.ExecuteCommandBuffer(cb);
                RenderTexture.active = rt;
                for (int t = 0; t < n; t++)
                {
                    int tile = first + t;
                    tex.ReadPixels(Tile(t), 0, 0, false);
                    var px = tex.GetPixelData<Color32>(0);
                    if (tile < bits) { for (int i = 0; i < px.Length; i++) if (px[i].r < 128) front[i] |= 1 << tile; continue; }
                    if (tile == bits) { for (int i = 0; i < px.Length; i++) outline[i] = px[i].r < 128; continue; }
                    int k = tile - bits - 1;
                    var others = r.ByCopy[k] = new Dictionary<int, int>();
                    for (int i = 0; i < px.Length; i++)
                    {
                        if (px[i].r >= 128) continue;
                        r.Alone[k]++;
                        if (front[i] == k + 1) r.Shown[k]++;
                        else if (front[i] == 0) r.ByStore[k]++;
                        else { others.TryGetValue(front[i], out int o); others[front[i]] = o + 1; }
                    }
                    if (r.Shown[k] < r.Alone[k] * 0.05f) for (int i = 0; i < px.Length; i++) if (px[i].r < 128 && front[i] != k + 1) under[i] = true;
                }
            }
        }
        finally
        {
            RenderTexture.active = was;
            cb.Release();
            RenderTexture.ReleaseTemporary(rt);
            Destroy(tex);
        }
        if (!outline.Any(x => x)) return null;
        var picture = new Color32[TileW * TileH];
        for (int i = 0; i < picture.Length; i++)
        {
            uint h = (uint)front[i] * 2654435761u;
            picture[i] = under[i] ? new Color32(255, 0, 255, 255) : front[i] > 0 ? new Color32((byte)(40 + (h >> 8 & 175)), (byte)(40 + (h >> 16 & 175)), (byte)(40 + (h >> 24 & 175)), 255)
                : outline[i] ? new Color32(70, 70, 70, 255) : new Color32(255, 255, 255, 255);
        }
        var img = new Texture2D(TileW, TileH, TextureFormat.RGBA32, false);
        img.SetPixels32(picture);
        File.WriteAllBytes(Path.Combine(dir, $"{state}-{viewName}-ids.png"), img.EncodeToPNG());
        Destroy(img);
        return r;
    }

    // A fixed camera on the store: its front (+z), its back, its right side, or from above; far enough to see all of it.
    static void Aim(Camera cam, Container c, string view)
    {
        var main = global::Utils.GetMainCamera();
        if (main) { cam.cullingMask = main.cullingMask; cam.clearFlags = main.clearFlags; cam.backgroundColor = main.backgroundColor; }
        var b = new Bounds(c.transform.position, Vector3.one * 0.5f);
        foreach (var r in c.GetComponentsInChildren<Renderer>()) if (r.enabled) b.Encapsulate(r.bounds);
        if (c.GetComponentInChildren<StoreContents>() is { } sc && sc.CopiesShown > 0) b.Encapsulate(sc.WorldBounds);
        cam.fieldOfView = 40f;
        cam.nearClipPlane = 0.05f;
        float dist = b.extents.magnitude / Mathf.Tan(20f * Mathf.Deg2Rad) * 1.1f;
        var t = c.transform;
        var dir = view == "front" ? (t.forward + Vector3.up * 0.25f).normalized : view == "back" ? (-t.forward + Vector3.up * 0.25f).normalized
            : view == "side" ? (t.right + Vector3.up * 0.25f).normalized : (Vector3.up + t.forward * 0.05f).normalized;
        cam.transform.position = b.center + dir * dist;
        cam.transform.rotation = Quaternion.LookRotation(b.center - cam.transform.position, view == "above" ? t.forward : Vector3.up);
    }
}

#endif

// The colour of an item, for faces that show it (the Hide Rack's stretched hides): the mean of its model's main texture times
// the material's colour, read once per item through a small render texture (the game's textures aren't readable), on a copy
// of the store's material with that colour.
static class HideTint
{
    static readonly Dictionary<(Material, string), Material> made = new();

    public static Material For(Material frame, GameObject item)
    {
        if (!item || !frame) return null;
        var key = (frame, item.name);
        if (made.TryGetValue(key, out var m) && m) return m;
        var mat = new Material(frame) { name = frame.name + " tint " + item.name };
        if (mat.HasProperty("_Color")) mat.SetColor("_Color", Mean(item));
        // A stretched hide is matte (Joost, 25 Oct: "shiny"): whatever gloss, smoothness, metal or specular the piece shader has, off.
        var dulled = new List<string>();
        for (int i = 0; i < mat.shader.GetPropertyCount(); i++)
        {
            var type = mat.shader.GetPropertyType(i);
            string name = mat.shader.GetPropertyName(i);
            if ((type == UnityEngine.Rendering.ShaderPropertyType.Float || type == UnityEngine.Rendering.ShaderPropertyType.Range)
                && (name.IndexOf("gloss", StringComparison.OrdinalIgnoreCase) >= 0 || name.IndexOf("smooth", StringComparison.OrdinalIgnoreCase) >= 0
                    || name.IndexOf("metal", StringComparison.OrdinalIgnoreCase) >= 0 || name.IndexOf("spec", StringComparison.OrdinalIgnoreCase) >= 0))
            { mat.SetFloat(name, 0f); dulled.Add(name); }
            else if (type == UnityEngine.Rendering.ShaderPropertyType.Color && name.IndexOf("spec", StringComparison.OrdinalIgnoreCase) >= 0)
            { mat.SetColor(name, Color.black); dulled.Add(name); }
        }
        if (made.Count == 0) Plugin.Log.LogInfo($"Hide panels: matte ({(dulled.Count > 0 ? string.Join(", ", dulled) : "the shader has no gloss settings")}).");
        return made[key] = mat;
    }

    static Color Mean(GameObject item)
    {
        var r = item.GetComponentsInChildren<Renderer>(true).FirstOrDefault(x => x is MeshRenderer or SkinnedMeshRenderer && x.sharedMaterial);
        var mat = r ? r.sharedMaterial : null;
        var tint = mat && mat.HasProperty("_Color") ? mat.GetColor("_Color") : Color.white;
        if (!mat || !(mat.mainTexture is Texture tex)) return tint;
        var rt = RenderTexture.GetTemporary(16, 16, 0, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB);
        var was = RenderTexture.active;
        Graphics.Blit(tex, rt);
        RenderTexture.active = rt;
        var read = new Texture2D(16, 16, TextureFormat.RGBA32, false);
        read.ReadPixels(new Rect(0, 0, 16, 16), 0, 0);
        RenderTexture.active = was;
        RenderTexture.ReleaseTemporary(rt);
        Color sum = Color.clear;
        int n = 0;
        foreach (var px in read.GetPixels()) if (px.a > 0.1f) { sum += px; n++; }
        UnityEngine.Object.Destroy(read);
        var mean = n > 0 ? sum / n : Color.white;
        const float gain = 1.12f;   // the panels' neutral hide tile is ~0.88 grey: keep the hide's own mean (Hide Rack r2)
        return new Color(Mathf.Clamp01(mean.r * tint.r * gain), Mathf.Clamp01(mean.g * tint.g * gain), Mathf.Clamp01(mean.b * tint.b * gain), 1f);
    }

    // Live reload: the tinted copies this copy made.
    public static void ReleaseAll()
    {
        foreach (var m in made.Values) if (m) UnityEngine.Object.Destroy(m);
        made.Clear();
    }
}

static class SkinPatches
{
    [HarmonyPatch(typeof(Container), "Awake"), HarmonyPostfix]
    static void ContainerAwake(Container __instance) { if (Plugin.Live) Skins.Apply(__instance); }
}

// Dev live reload (ScriptEngine; tools/valheim-mods/LIVE-MODDING.md). Every load is a new assembly with its own types and
// statics, while the world keeps what earlier copies built:
// - Pieces: Jotunn keeps the prefab (and its CustomPiece, in ZNetScene and the hammer) the first copy registered, so a later
//   copy never registers that name again. It strips what the earlier copy built on the prefab and on every piece standing
//   in the world (our "storehouse_*" children, our components, found by type NAME since each copy has its own types) and
//   builds them again with its own code, models and materials. The collider box stays the same object, and the game's
//   caches of colliders (WearNTear) and renderers (MaterialMan) are refreshed. The ghost in your hand is made again.
// - A piece type that is new in this copy is registered on the spot (Jotunn's own route on the next world load).
// - Skins come back from skins.json; settings from the same config file.
// - Leaving (Plugin.OnDestroy): the copy takes its components off everything, puts skinned chests back, and destroys the
//   materials, textures, meshes and icons it made. Until the next copy dresses them, the pieces show nothing (a frame).
static class Reload
{
    static readonly HashSet<string> OurTypes = new(StringComparer.Ordinal) { typeof(CribFill).FullName, typeof(StoreContents).FullName, typeof(SkinState).FullName };
    // Looked up by name, null when a game update renames them (then that step is skipped, nothing throws).
    static readonly FieldInfo WearColliders = AccessTools.Field(typeof(WearNTear), "m_colliders");
    static readonly FieldInfo Ghost = AccessTools.Field(typeof(Player), "m_placementGhost");
    static readonly MethodInfo SetupGhost = AccessTools.Method(typeof(Player), "SetupPlacementGhost");
    static readonly MethodInfo UpdatePieces = AccessTools.Method(typeof(Player), "UpdateAvailablePiecesList");
    static readonly MethodInfo RefreshRenderers = AccessTools.Method(typeof(MaterialMan), "RegisterRenderers");
    static int rebuilt;   // prefabs this copy took over from an earlier one
    static bool late;     // a piece type registered while a world was loaded

    static bool Ours(Component c) => c && OurTypes.Contains(c.GetType().FullName);

    static string PrefabName(string name)
    {
        int i = name.IndexOf("(Clone)", StringComparison.Ordinal);
        return i >= 0 ? name.Substring(0, i).TrimEnd() : name;
    }

    // What any copy built on a piece: its components on the root, its "storehouse_*" children (the collider holder stays).
    static void Undress(GameObject go)
    {
        foreach (var c in go.GetComponents<MonoBehaviour>()) if (Ours(c)) UnityEngine.Object.DestroyImmediate(c);
        var old = new List<GameObject>();
        foreach (Transform t in go.transform)
            if (t.name.StartsWith("storehouse_", StringComparison.Ordinal) && t.name != "storehouse_collider") old.Add(t.gameObject);
        foreach (var o in old) UnityEngine.Object.DestroyImmediate(o);
    }

    // A prefab an earlier copy registered: built again with this copy's code (placement, container, look, icon).
    public static void Rebuild(GameObject go, Kind kind)
    {
        var p = go.GetComponent<Piece>();
        if (!p) { Plugin.Log.LogWarning($"{kind.Title}: '{go.name}' exists but is not a piece; left alone."); return; }
        Undress(go);
        var container = Plugin.Configure(go, p, kind);
        if (!container) { Plugin.Log.LogError($"{kind.Title}: the existing prefab has no Container; not rebuilt."); return; }
        kind.Build(go, container);
        p.m_icon = Icons.Render(go, kind) ?? p.m_icon;
        rebuilt++;
        Plugin.Log.LogInfo($"{kind.Title}: piece taken over from the previous copy and built again ({kind.Width}x{kind.Height}).");
    }

    // A piece type this copy adds while a world is loaded: into ZNetScene and the hammer now (Jotunn does it again by its
    // own route on the next world load). Its recipe gets the real items from Settings.ApplyToPieces in AfterPieces.
    public static void RegisterLate(GameObject go, Kind kind)
    {
        if (!ZNetScene.instance || !ObjectDB.instance) return;   // menu or start-up: Jotunn registers it when the world loads
        try
        {
            PieceManager.Instance.RegisterPieceInPieceTable(go, PieceTables.Hammer);
            late = true;
            Plugin.Log.LogInfo($"{kind.Title}: new piece type, registered in the running world (if the hammer doesn't show it, go to the main menu and load the world again).");
        }
        catch (Exception e) { Plugin.Log.LogWarning($"{kind.Title}: new piece type not registered in the running world ({e.Message}); it shows after loading the world again."); }
    }

    // After the pieces: everything standing in the world, the ghost, recipes and skins.
    // A placed store whose grid this copy sizes differently (the armories: a row per figure, Joost 18:08) takes the new size at once,
    // only when every item it holds still has its slot; else it keeps its size and says so (it changes at the next start then).
    static readonly AccessTools.FieldRef<Inventory, int> InvWidth = AccessTools.FieldRefAccess<Inventory, int>("m_width");
    static readonly AccessTools.FieldRef<Inventory, int> InvHeight = AccessTools.FieldRefAccess<Inventory, int>("m_height");
    static void Resize(Container c, Kind kind)
    {
        var inv = c.GetInventory();
        if (inv == null) return;
        if (TypedSlots.Model(kind) != null) { TypedSlots.Fit(c); return; }   // its blocks follow its places, nothing hidden
        int w = kind.Width, h = kind.Height;
        if (inv.GetWidth() == w && inv.GetHeight() == h) return;
        bool armory = Mannequins.Is(kind);   // its slots change meaning with the shape: arranged anew below
        if (!armory && inv.GetAllItems().Any(i => i != null && (i.m_gridPos.x >= w || i.m_gridPos.y >= h)))
        {
            Plugin.Log.LogWarning($"{kind.Title}: kept at {inv.GetWidth()}x{inv.GetHeight()}, items lie outside the new {w}x{h} grid.");
            return;
        }
        Plugin.Log.LogInfo($"{kind.Title}: placed window {inv.GetWidth()}x{inv.GetHeight()} -> {w}x{h} (live reload).");
        c.m_width = w;
        c.m_height = h;
        InvWidth(inv) = w;
        InvHeight(inv) = h;
        if (armory) Mannequins.Arrange(c, false);
    }

    public static void AfterPieces()
    {
        if (rebuilt == 0 && !late) return;   // a first load: nothing in the world was built by an earlier copy
        var t0 = System.Diagnostics.Stopwatch.GetTimestamp();
        int swept = 0;
        foreach (var c in UnityEngine.Object.FindObjectsByType<MonoBehaviour>(FindObjectsInactive.Include, FindObjectsSortMode.None))
            if (Ours(c) && c.GetType().Assembly != typeof(Reload).Assembly) { UnityEngine.Object.DestroyImmediate(c); swept++; }   // left behind by a copy that did not clean up

        var prefabs = new Dictionary<string, (GameObject prefab, Kind kind)>(StringComparer.Ordinal);
        foreach (var k in Kinds.All) if (PrefabManager.Instance.GetPrefab(k.Prefab) is { } pf) prefabs[k.Prefab] = (pf, k);
        var player = Player.m_localPlayer;
        var ghost = player && Ghost != null ? Ghost.GetValue(player) as GameObject : null;
        int dressed = 0, failed = 0;
        foreach (var piece in UnityEngine.Object.FindObjectsByType<Piece>(FindObjectsInactive.Include, FindObjectsSortMode.None))
        {
            var go = piece.gameObject;
            if (go == ghost || !prefabs.TryGetValue(PrefabName(go.name), out var e) || go == e.prefab || e.kind.Dress == null) continue;
            try
            {
                Undress(go);
                e.kind.Dress(go);
                if (go.GetComponent<Container>() is { } placed) { Resize(placed, e.kind); Mannequins.AfterLoad(placed); }   // armories: the one-time layout check too
                if (WearColliders != null && go.GetComponent<WearNTear>() is { } wnt) WearColliders.SetValue(wnt, null);   // read again at the next support check
                if (MaterialMan.instance && RefreshRenderers != null) RefreshRenderers.Invoke(MaterialMan.instance, new object[] { go, true });
                dressed++;
            }
            catch (Exception ex) { failed++; Plugin.Log.LogWarning($"{e.kind.Title}: {go.name} not redressed ({ex.Message})."); }
        }
        if (player && ghost && prefabs.ContainsKey(PrefabName(ghost.name)) && SetupGhost != null) SetupGhost.Invoke(player, null);
        if (player && late && UpdatePieces != null) UpdatePieces.Invoke(player, null);
        if (ObjectDB.instance && ObjectDB.instance.m_items.Count > 0) Settings.ApplyToPieces();
        Skins.Refresh();
        double ms = (System.Diagnostics.Stopwatch.GetTimestamp() - t0) * 1000.0 / System.Diagnostics.Stopwatch.Frequency;
        Plugin.Log.LogInfo($"Live reload: {rebuilt} piece prefab(s) rebuilt, {dressed} piece(s) in the world redressed"
            + (failed > 0 ? $", {failed} failed" : "") + (swept > 0 ? $", {swept} leftover component(s) of an older copy removed" : "")
            + $", skins re-applied; {ms:F0} ms.");
    }

    // This copy leaves: its components off every piece and chest (skinned chests get their own look back), and what it
    // made destroyed. The pieces keep their frame objects and collider for the next copy to dress.
    public static void Teardown()
    {
        int n = 0;
        foreach (var s in UnityEngine.Object.FindObjectsByType<SkinState>(FindObjectsInactive.Include, FindObjectsSortMode.None)) { Gone(s); n++; }
        foreach (var f in UnityEngine.Object.FindObjectsByType<CribFill>(FindObjectsInactive.Include, FindObjectsSortMode.None)) { Gone(f); n++; }
        foreach (var c in UnityEngine.Object.FindObjectsByType<StoreContents>(FindObjectsInactive.Include, FindObjectsSortMode.None)) { Gone(c); n++; }
        StoreContents.ReleaseInstanced();
        ItemVisual.Release();
        CribModel.Release();
        StoreModel.ReleaseAll();
        HideTint.ReleaseAll();
        Icons.Release();
        Plugin.Log.LogInfo($"Live reload: {n} component(s) of this copy removed, its materials, meshes and icons destroyed.");
    }

    static void Gone(Component c)
    {
        try { UnityEngine.Object.DestroyImmediate(c); }
        catch (Exception) { UnityEngine.Object.Destroy(c); }
    }
}
#endif
