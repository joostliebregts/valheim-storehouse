// The units style's plan (the coordinator, 27 Oct: "the units style already is one component with variants, like a UI component"):
// which stacks a store draws, on which unit, how many copies of each, which crop heap, which liquid, label, vessel, band and board,
// decided in plain C# from plain numbers. No UnityEngine here: StoreContents.Rebuild makes the plan and draws it (StoreModel.Place,
// the floor, KeepSide, the ammo turn, the jitter, the meat rack's bundles), and planrun/ compiles this same file outside the game to
// prove the plan the game made is the one this code makes (plan-gate.py). The arithmetic is the drawing's own, moved here unchanged:
// V2, V3 and PlanMath are UnityEngine's Vector2, Vector3 and Mathf as far as the plan uses them, decompiled from the game's
// UnityEngine.CoreModule, so every float operation stays the same operation in the same order.
using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Text;

namespace Finn.Storehouse;

struct V2
{
    public float x, y;
    public V2(float x, float y) { this.x = x; this.y = y; }
    public float sqrMagnitude => x * x + y * y;
    public static V2 operator -(V2 a, V2 b) => new V2(a.x - b.x, a.y - b.y);
}

struct V3
{
    public float x, y, z;
    public V3(float x, float y, float z) { this.x = x; this.y = y; this.z = z; }
    public static V3 zero => new V3(0f, 0f, 0f);
    public static V3 operator +(V3 a, V3 b) => new V3(a.x + b.x, a.y + b.y, a.z + b.z);
    public static V3 operator /(V3 a, float d) => new V3(a.x / d, a.y / d, a.z / d);
}

static class PlanMath
{
    public static float Min(float a, float b) => (a < b) ? a : b;
    public static int Min(int a, int b) => (a < b) ? a : b;
    public static float Max(float a, float b) => (a > b) ? a : b;
    public static int Max(int a, int b) => (a > b) ? a : b;
    public static float Round(float f) => (float)Math.Round(f);
    public static int CeilToInt(float f) => (int)Math.Ceiling(f);
    public static int FloorToInt(float f) => (int)Math.Floor(f);
    public static int RoundToInt(float f) => (int)Math.Round(f);
    public static int Clamp(int value, int min, int max)
    {
        if (value < min) value = min;
        else if (value > max) value = max;
        return value;
    }
    public static float Clamp01(float value)
    {
        if (value < 0f) return 0f;
        if (value > 1f) return 1f;
        return value;
    }
}

// One side of a bay two kinds share (StoreModel.SplitSide; KeepSide keeps a copy on it).
readonly struct PlanSplit
{
    public readonly float Lo, Hi;              // the side's right (-x) and left (+x) edge
    public readonly bool LoBoard, HiBoard;     // a board at that edge (else the bay's wall)
    public PlanSplit(float lo, float hi, bool loBoard, bool hiBoard) { Lo = lo; Hi = hi; LoBoard = loBoard; HiBoard = hiBoard; }
}

sealed class UnitPlan
{
    // ---- In: the store's model as plain numbers (StoreModel.PlanSummary), its stock and the facts asked of the game on the way.

    public sealed class Unit { public V3 Pos, Box; public int Group = -1; public string Kind, Item; public int Copies; }

    public sealed class Model
    {
        public string Title, Slug, KindSlug;        // StoreModel.Slug; its Kind's slug (null: no kind)
        public bool Homes, KindPerBay, Display, Mirror, Heap;
        public List<Unit> Units = new();
        public Dictionary<string, int?> Crops;      // crop layout key -> its stack count (null layout: null); null: no crop layouts
        public int? CrateFloors;                    // how many crate floors; null: none
        public List<(int Group, string Item)> Liquids = new();
        public List<int> Labels = new(), Places = new(), Panels = new();   // per label, vessel place, panel: its group
        public List<int> Bands = new(), Bindings = new();                  // the groups with a band, the units with a binding, in model order
        public Dictionary<string, string> ItemFamily = new(StringComparer.Ordinal);
        public List<string> FamilyOrder = new(), VesselFamilies = new();
        public Dictionary<int, PlanSplit> PriorSplit = new();   // the model's split sides before this plan (a store not laid out by group keeps them)
        public bool ManyKindBoards;
        public Func<string, string> Ammo;           // StoreModel.AmmoFamily: "arrow", "bolt" or null, from the item's ammo type
        // StoreModel.ExtentIn (item, unit, crop stack k, mirrored): half the width (x) of the narrowest copy a stack of the item draws there,
        // as KeepSide measures it: of crop layout stack k in the unit's crate (k >= 0), else of the unit's own copies. Null: no model.
        public Func<string, int, int, bool, float?> Extent;

        // The key a capture keeps an Extent answer under: per crate and crop stack, or per unit.
        public string ExtentKey(int unit, int k, bool mirrored) => k >= 0 ? $"crate {Units[unit].Group} stack {k}{(mirrored ? " mirrored" : "")}" : $"unit {unit}";

        // StoreModel.FamilyOf: which vessel family an item takes.
        public string FamilyOf(string item) => item != null && ItemFamily.TryGetValue(item, out var f) ? f
            : Family(item, Ammo) is { } g && VesselFamilies.Contains(g) ? g : FamilyOrder.FirstOrDefault() ?? VesselFamilies.FirstOrDefault() ?? "crock";
    }

    public sealed class Row { public string Kind, Drop; public int Stack, Max, X, Y; }   // Kind: the drop prefab's name, else the shared name; Drop: null without a drop prefab

    public sealed class Inputs
    {
        public int Width, Height, MaxTrisPerStack;
        public List<Row> Rows = new();               // the inventory's stacks, in its own order
        public Model Model;
        public Func<int, int?> Look;                 // per row: the item model's triangles per copy; null: no model can be read
        public Func<int, int?> PartsTris;            // per row: the triangles the bay log counts (dev)
        public Dictionary<string, int?> Looks, Parts;   // by drop name: what Look and PartsTris answered (a capture), or are to answer (planrun)
        public Dictionary<string, string> Ammos;
        public Dictionary<string, Dictionary<string, float?>> Extents;   // by kind, then Model.ExtentKey: what Model.Extent answered

        // A capture: every fact the plan asks for is kept, so planrun can answer it the same way.
        public void Record()
        {
            var look = Look;
            var parts = PartsTris;
            var ammo = Model.Ammo;
            Looks = new Dictionary<string, int?>(StringComparer.Ordinal);
            Parts = new Dictionary<string, int?>(StringComparer.Ordinal);
            Ammos = new Dictionary<string, string>(StringComparer.Ordinal);
            Look = r => { var v = look(r); if (Rows[r].Drop != null) Looks[Rows[r].Drop] = v; return v; };
            PartsTris = r => { var v = parts(r); if (Rows[r].Drop != null) Parts[Rows[r].Drop] = v; return v; };
            Model.Ammo = s => { var v = ammo(s); Ammos[s] = v; return v; };
            var extent = Model.Extent;
            var model = Model;
            Extents = new Dictionary<string, Dictionary<string, float?>>(StringComparer.Ordinal);
            if (extent != null)
                Model.Extent = (t, u, k, mirrored) =>
                {
                    var v = extent(t, u, k, mirrored);
                    if (!Extents.TryGetValue(t, out var d)) Extents[t] = d = new Dictionary<string, float?>(StringComparer.Ordinal);
                    d[model.ExtentKey(u, k, mirrored)] = v;
                    return v;
                };
        }

        // planrun: the facts from a capture; one the plan asks for that the game was never asked fails loudly.
        public void Replay()
        {
            int? From(Dictionary<string, int?> d, string what, int r) => Rows[r].Drop == null ? null
                : d.TryGetValue(Rows[r].Drop, out var v) ? v : throw new KeyNotFoundException($"{what} of {Rows[r].Drop}: not in the capture");
            Look = r => From(Looks, "look", r);
            PartsTris = r => From(Parts, "parts_tris", r);
            Model.Ammo = s => Ammos.TryGetValue(s, out var v) ? v : throw new KeyNotFoundException($"ammo of {s}: not in the capture");
            var model = Model;
            Model.Extent = (t, u, k, mirrored) => Extents != null && Extents.TryGetValue(t, out var d) && d.TryGetValue(model.ExtentKey(u, k, mirrored), out var v) ? v
                : throw new KeyNotFoundException($"extent of {t} at {model.ExtentKey(u, k, mirrored)}: not in the capture");
        }
    }

    // ---- Out.

    public enum Draw { None, Crop, Copies, Undrawn }
    // One stack the units loop reached with a unit: its item (index into Items), unit, the liquid it fills (-1: none) and how it is
    // drawn: nothing more (a liquid), a crop heap (Layout's stack K, mirrored when Variant is 1, at most Cap copies), N copies on the
    // unit (Hang: the meat rack tries its hung bundles first; Bind: the unit's binding goes on), or not at all (Undrawn).
    public sealed class Stack
    {
        public int Item, Unit, Liquid = -1;
        public Draw Draw;
        public string Layout;
        public int K, Variant, Cap, N;
        public bool Hang, Bind;
    }
    public sealed class Divider { public float X, Y0, Y1, Z0, Z1, Thick; }   // a board SplitShared stood up (StoreModel.Apply makes its matrix)
    // What ByGroup leaves on the model (StoreModel.PlannedPairs, Dividers, SplitSide); null when it returned before touching them.
    public sealed class GroupState
    {
        public HashSet<int> PlannedPairs = new();
        public List<Divider> Dividers = new();
        public Dictionary<int, PlanSplit> Split = new();
        public HashSet<string> TooWide = new();   // kinds refused a shared group: no side of it would hold a copy (not in the JSON; the unshown line says it)
    }

    public string Order = "none";                   // grid, heap, group, slot: how stacks found their units
    public int PerStack = 1;
    public List<int> Items = new();                 // the stacks drawn, as row indices: in slot order, repeated per stack, sampled
    public int[] Grid, Crates;
    public List<int> Assigned = new();              // per item its unit (-1: none)
    public int Unseen;                              // kinds with no stack on a unit (UnrepresentedKindCount)
    public Dictionary<int, int> CropVariant;        // per crate: its crop layout as is (0) or mirrored (1)
    public GroupState State;
    public Dictionary<int, PlanSplit> Split = new();   // the split sides the loop keeps copies on: State's, else the model's from before
    public bool Topless;                            // the root bin's crops without their greens
    public bool Dividers;                           // the boards are drawn
    public List<Stack> Stacks = new();
    public int Shown;                               // the stacks counted as shown
    public Dictionary<int, int> LabelItem = new();  // per group: the first item the loop reached in it
    public List<(int Liquid, float Below, float Share)> Liquids = new();
    public List<(int Label, int Item)> Labels = new();
    public List<(int Place, string Family)> Places = new();
    public List<(int Panel, int Item)> Panels = new();
    public List<(int Band, int Item)> Bands = new();   // Band: the group (StoreModel.Bands' key)
#if !RELEASE
    public string BayLine, UnshownLine, UndrawnLine;   // dev log lines (null: none)
#endif

    public static UnitPlan Make(Inputs input)
    {
        var m = input.Model;
        var rows = input.Rows;
        var p = new UnitPlan { Topless = m.Slug == "rootbin" };
        int w = PlanMath.Max(1, input.Width);
        var items = Enumerable.Range(0, rows.Count).OrderBy(i => rows[i].Y * w + rows[i].X).ToList();
        // A store with fewer slots than its model has units (the second series, 32 slots on models of 64-128): each stack fills
        // that many units in its group, so a full store looks full (Joost, 24 Oct).
        int perStack = m.Mirror || m.Heap || m.Places.Count > 0 ? 1 : m.Units.Count / PlanMath.Max(1, w * PlanMath.Max(1, input.Height));
        if (perStack > 1) items = items.SelectMany(it => Enumerable.Repeat(it, perStack)).ToList();
        // The other way round (review 25 Oct: the bunker's 96 slots on 54 units): more slots than units. The units drawn follow the
        // stock (stacks over slots, so a full bunker looks full and a half one half), never fewer when stock rises, and every kind
        // present keeps at least one (Joost, 24 Oct: everything in the store shows from outside). The kinds share the rest by stock.
        int slots = w * PlanMath.Max(1, input.Height);
        if (perStack <= 1 && !m.Mirror && !m.Heap && m.Places.Count == 0 && m.Units.Count > 0 && slots > m.Units.Count)
            items = StockSample(items, m.Units.Count, slots, it => rows[it].Kind)
                .OrderBy(it => rows[it].Y * w + rows[it].X).ToList();
        var grid = m.Mirror ? GridOrder(m.Units, w, PlanMath.Max(1, input.Height)) : null;
        // Each crate its own variant of its crop's layout (the coordinator, 25 Oct: the schema has one layout per crop, so two crates of
        // one crop looked identical): the nth crate holding a crop, in crate order, is drawn as is or mirrored across, about its floor
        // centre. Never turned half round: the crate's back is high, so the heap's high side must stay at the back, not the low front
        // lip. Heights stay, so the floor-first order stays; the cavity is symmetric across, so it stays inside.
        Dictionary<int, int> cropVariant = null;
        int h = PlanMath.Max(1, input.Height);
        GroupState state = null;
        var crates = grid == null && m.Heap ? HeapOrder(m.Units, items.Select(it => (rows[it].X, rows[it].Y)).ToList())
            : grid == null ? ByGroup(m, items.Select(it => rows[it].Kind).ToList(),
            items.Select(it => new V2((rows[it].X + 0.5f) / w, (rows[it].Y + 0.5f) / h)).ToList(), out state) : null;
        if (m.Crops != null && crates != null) cropVariant = CropVariants(m, items.Select(it => rows[it].Kind).ToList(), crates);
        p.Order = grid != null ? "grid" : crates == null ? "slot" : m.Heap ? "heap" : "group";
        p.PerStack = perStack;
        p.Items = items;
        p.Grid = grid;
        p.Crates = crates;
        p.CropVariant = cropVariant;
        p.State = state;
        p.Split = state != null ? state.Split : m.PriorSplit;
        p.Dividers = crates != null && !m.Heap && state != null && state.Dividers.Count > 0;
        var assigned = items.Select((item, i) =>
        {
            int slot = rows[item].Y * w + rows[item].X;
            int unit = grid != null ? slot >= 0 && slot < grid.Length ? grid[slot] : -1 : crates != null ? crates[i] : i;
            return unit >= 0 && unit < m.Units.Count ? unit : -1;
        }).ToList();
        p.Assigned = assigned;
        p.Unseen = StorageReviewPolicy.UnrepresentedKinds(items.Select(it => rows[it].Kind).ToList(), assigned, m.Units.Count);
#if !RELEASE
        // Bay stores (the coordinator, 25 Oct: an Ore Bin showed "Bays: 7/6" and ~4 lumps in one bay): per bay its kind and stacks,
        // the kinds without a bay, and each kind's triangles per copy. Once per change of contents.
        if (m.KindPerBay && crates != null)
        {
            string KindOf(int it) => rows[it].Kind;
            var perBay = assigned.Select((u, i) => (u, i)).Where(x => x.u >= 0).GroupBy(x => m.Units[x.u].Group).OrderBy(g => g.Key)
                .Select(g => $"bay {g.Key}: " + string.Join(" + ", g.GroupBy(x => KindOf(items[x.i])).Select(k => $"{k.Key} x{k.Count()}"))).ToList();
            var none = items.Select((it, i) => (it, i)).GroupBy(x => KindOf(x.it)).Where(k => k.All(x => assigned[x.i] < 0)).Select(k => $"{k.Key} x{k.Count()}").ToList();
            var cost = items.GroupBy(KindOf).Select(k => input.PartsTris(k.First()) is int t ? $"{k.Key} {t}" : null).Where(x => x != null);
            p.BayLine = $"{m.Title}: {string.Join("; ", perBay)}; no bay: {(none.Count > 0 ? string.Join(", ", none) : "none")}; triangles per copy: {string.Join(", ", cost)}";
        }
        // Any store drawn by units: which kinds are not shown and why, as the equipment stores say it (the coordinator, 25 Oct:
        // Fletcher's Barrels showed 43 of 64 stacks and "3 stored kinds have no display place"). Once per change of contents.
        p.UnshownLine = NotShown(m.Title, items.Select(it => rows[it].Kind).ToList(), assigned, rows.Count - items.Count, p.NoPlace);
        var undrawn = new List<string>();   // placed, yet not drawn (the coordinator, 25 Oct: a full Trophy Hall with one empty place)
#endif
        // The units loop: per stack its unit, and what is drawn there.
        var cropCount = new Dictionary<(int, string), int>();   // per crate and crop: two crops in one crate each start at their layout's stack 0
        var liquidFill = new Dictionary<int, float>();
        int stacks = 0;
        for (int i = 0; i < items.Count && i < m.Units.Count; i++)
        {
            var row = rows[items[i]];
            int slot = row.Y * w + row.X;
            if (grid != null && (slot < 0 || slot >= grid.Length)) continue;
            int u = grid != null ? grid[slot] : crates != null ? crates[i] : i;
            if (u < 0) continue;
            var unit = m.Units[u];
            string prefabName = row.Drop ?? "";
            if (unit.Group >= 0 && !p.LabelItem.ContainsKey(unit.Group)) p.LabelItem[unit.Group] = i;
            var s = new Stack { Item = i, Unit = u };
            p.Stacks.Add(s);
            int liquid = m.Liquids.FindIndex(l => l.Group == unit.Group && (l.Item == null || l.Item == prefabName));
            if (liquid >= 0)
            {
                s.Liquid = liquid;
                int perGroup = m.Units.Count(x => x.Group == unit.Group && (m.Places.Count == 0 || x.Kind == unit.Kind));   // a place's units of this vessel
                liquidFill.TryGetValue(liquid, out float f);
                liquidFill[liquid] = f + PlanMath.Clamp01(row.Stack / (float)PlanMath.Max(1, row.Max)) / PlanMath.Max(1, perGroup);
                // Liquid, not lumps. A store without labels may still put a copy on a liquid unit as the vessel's label (Cooper's
                // Row r4: the sap keg on the first sap unit).
                if (m.Labels.Count > 0 || unit.Copies == 0 || m.Places.Count > 0) { stacks++; continue; }
            }
            if (m.Crops != null && m.CrateFloors is int floors && unit.Group >= 0 && unit.Group < floors
                && input.Look(items[i]) is int cropTris)
            {
                string key = row.Drop ?? "";
                string lay = m.Crops.TryGetValue(key, out var own) ? (own != null ? key : null) : m.Crops.TryGetValue("_generic", out var gen) ? (gen != null ? "_generic" : null) : null;
                // A split crate: each crop from its own layout's stack 0, on its own side. A mixed crate: one count for the crate, so
                // two crops take different spots in the heap instead of the same ones.
                var countKey = (unit.Group, p.Split.ContainsKey(u) ? key : "");
                cropCount.TryGetValue(countKey, out int k);
                cropCount[countKey] = k + 1;
                if (lay != null && k < m.Crops[lay].Value)
                {
                    stacks++;
                    s.Draw = Draw.Crop;
                    s.Layout = lay;
                    s.K = k;
                    s.Cap = input.MaxTrisPerStack > 0 && cropTris > 0 ? Math.Max(1, input.MaxTrisPerStack / cropTris) : int.MaxValue;
                    s.Variant = cropVariant != null && cropVariant.TryGetValue(unit.Group, out int cv) ? cv : 0;
                    continue;
                }
            }
            var look = input.Look(items[i]);
            if (look == null || unit.Copies == 0)
            {
                s.Draw = Draw.Undrawn;
#if !RELEASE
                undrawn.Add($"{row.Kind} at unit {u} ({(look == null ? "its model could not be read" : "the layout has no copy at that unit")})");
#endif
                continue;
            }
            stacks++;
            int max = row.Max;
            s.Draw = Draw.Copies;
            s.Hang = HungOn(m, unit);
            int n = m.Display ? 1 : max > 1 ? PlanMath.Clamp(PlanMath.CeilToInt(unit.Copies * (float)row.Stack / max), 1, unit.Copies) : unit.Copies;
            if (input.MaxTrisPerStack > 0 && look.Value > 0) n = PlanMath.Min(n, PlanMath.Max(1, input.MaxTrisPerStack / look.Value));
            s.N = n;
            s.Bind = m.Bindings.Contains(u);
        }
        p.Shown = stacks;
#if !RELEASE
        p.UndrawnLine = undrawn.Count > 0 ? $"{m.Title}: placed but not drawn: {string.Join(", ", undrawn)}" : null;
#endif
        // A holder's band shows what it holds; an empty holder keeps the frame's plain band.
        foreach (int band in m.Bands)
            if (p.LabelItem.TryGetValue(band, out int held) && rows[items[held]].Drop != null) p.Bands.Add((band, held));
        // Two liquids in one vessel (one spilled over from its own full vessel) lie in layers: the vessel's own liquid at the
        // bottom, the other on top of it, together never above the rim (Joost, 24 Oct: "what if it overflows?").
        var under = new Dictionary<int, float>();
        string HomeOf(int g) => m.Units.FirstOrDefault(x => x.Group == g)?.Item;
        foreach (var kv in liquidFill.OrderBy(kv => m.Liquids[kv.Key].Item == HomeOf(m.Liquids[kv.Key].Group) ? 0 : 1))
        {
            var l = m.Liquids[kv.Key];
            if (kv.Value <= 0f) continue;
            under.TryGetValue(l.Group, out float below);
            float share = PlanMath.Min(kv.Value, 1f - below);
            if (share <= 0f) continue;
            under[l.Group] = below + share;
            p.Liquids.Add((kv.Key, below, share));
        }
        // Labels: the item a vessel holds, one copy standing in front of it (Joost: "only show what's actually in there").
        for (int j = 0; j < m.Labels.Count; j++)
            if (p.LabelItem.TryGetValue(m.Labels[j], out int held) && input.Look(items[held]) != null) p.Labels.Add((j, held));
        // Places: each shows the vessel of what it holds, or its own default while empty.
        for (int j = 0; j < m.Places.Count; j++)
        {
            // An empty place stands empty: how many vessels stand shows how full the rack is (Joost, 24 Oct).
            string fam = p.LabelItem.TryGetValue(m.Places[j], out int held) && rows[items[held]].Drop != null ? m.FamilyOf(rows[items[held]].Drop) : null;
            if (fam != null && m.VesselFamilies.Contains(fam)) p.Places.Add((j, fam));
        }
        // Panels: the Hide Rack's frames show the hide their bay holds, in that hide's colour; an empty bay's frame stands empty.
        for (int j = 0; j < m.Panels.Count; j++)
            if (p.LabelItem.TryGetValue(m.Panels[j], out int held)) p.Panels.Add((j, held));
        return p;
    }

    // Which stacks a store with fewer units than slots draws: units x stacks / slots of them (at least one per kind, at most one
    // per unit), shared out over the kinds by their stacks (largest remainder), each kind its first stacks in grid order. Rises
    // with every stack added: the count is monotonic in the stock, and a new kind takes its one unit from the biggest share.
    internal static List<T> StockSample<T>(List<T> items, int units, int slots, Func<T, string> kindOf)
    {
        if (items.Count == 0 || units <= 0 || slots <= units) return items;
        var kinds = items.GroupBy(kindOf).Select(g => g.ToList()).ToList();
        int target = PlanMath.Clamp(PlanMath.CeilToInt(units * (float)items.Count / slots), PlanMath.Min(kinds.Count, units), units);
        var take = kinds.Select(_ => 0).ToArray();
        int left = target;
        // One each first, the most plentiful kinds first when there are more kinds than units.
        foreach (int k in Enumerable.Range(0, kinds.Count).OrderByDescending(k => kinds[k].Count).ThenBy(k => k))
            if (left > 0) { take[k] = 1; left--; }
        // The rest by stock: each kind's fair share of the target, rounded by largest remainder, never more than it has.
        var want = kinds.Select(g => target * (float)g.Count / items.Count).ToArray();
        while (left > 0)
        {
            int best = -1;
            float gap = float.MinValue;
            for (int k = 0; k < kinds.Count; k++)
                if (take[k] < kinds[k].Count && want[k] - take[k] > gap) { gap = want[k] - take[k]; best = k; }
            if (best < 0) break;
            take[best]++;
            left--;
        }
        return kinds.SelectMany((g, k) => g.Take(take[k])).ToList();
    }

    // Mirror stores: unit index per grid slot. The units are grouped by height into the grid's rows (top row = highest), each
    // row read left to right as seen from the front (+x is the left side, front row before back row). Null when the units
    // don't make a full grid.
    public static int[] GridOrder(List<Unit> Units, int w, int h)
    {
        if (Units.Count != w * h) return null;
        var byHeight = Enumerable.Range(0, Units.Count).OrderByDescending(i => Units[i].Pos.y).ToList();
        var order = new int[w * h];
        for (int r = 0; r < h; r++)
        {
            var row = byHeight.Skip(r * w).Take(w).OrderByDescending(i => Units[i].Pos.x).ThenByDescending(i => Units[i].Pos.z).ToList();
            for (int c = 0; c < w; c++) order[r * w + c] = row[c];
        }
        return order;
    }

    // Heap stores (Joost: the pallet showed the grid upside down): the stacks in grid order from the bottom row up, left to right,
    // laid on the units layer by layer from the bottom, each layer front to back and left to right. Gaps in the grid close up,
    // so nothing ever floats over an empty spot. Returns the unit per stack (-1: no room).
    public static int[] HeapOrder(List<Unit> Units, List<(int x, int y)> slots)
    {
        var units = Enumerable.Range(0, Units.Count).OrderBy(i => PlanMath.Round(Units[i].Pos.y * 20f))   // layers 5 cm apart
            .ThenByDescending(i => Units[i].Pos.z).ThenByDescending(i => Units[i].Pos.x).ToList();       // front is +z, left is +x
        var result = Enumerable.Repeat(-1, slots.Count).ToArray();
        var stacks = Enumerable.Range(0, slots.Count).OrderByDescending(i => slots[i].y).ThenBy(i => slots[i].x).ToList();
        for (int r = 0; r < stacks.Count && r < units.Count; r++) result[stacks[r]] = units[r];
        return result;
    }

    // Stores whose units sit in crates, bays or bins (root bin, bunker, ore bin, meat rack bins): one item type per group, so a
    // crate holds turnips or mushrooms, not a mix (Joost). Types claim groups in slot order: a new type takes the free group
    // nearest to where its stack sits in the container grid (Joost: bottom left in the grid showed up back right in the ore
    // bin), the grid laid over the store as seen from the front: left to right, and top to bottom = top to bottom for a tall
    // store, back to front for a low one. A type with more stacks than its group has units spills into the nearest empty group.
    // `at`: each stack's grid spot, 0-1 across and down. Returns the unit per stack (-1: no room), or null without groups (state
    // then null too: the model's planned pairs, boards and split sides stay as they were).
    // A kind shares a group only where its side holds a copy of it (Joost, 27 Oct: the Meat Rack's hooks full and its bins empty, the
    // log saying 51 of 63 stacks shown: a 0.37 m bin split in two left sides of 0.12-0.24 m, and every meat, 0.2-0.25 m across, was
    // too wide for its side, so KeepSide drew none). The plan is made, and each stack on a split side is measured as the drawing will
    // draw it (Model.Extent: its crop layout stack at that crate's variant, else its unit's copies, at their scale, what KeepSide
    // measures). A kind none of whose stacks there would draw a copy makes the group fail: the kind that joined it is refused that
    // group (the joiner too narrow itself, else the last to join; never the group's own), and the plan is made again, until every
    // kind on a side draws. A kind no group can take beside another has no place: unseen, and logged so. Hung bundles (the meat
    // rack's hooks) are never drawn on a side.
    public static int[] ByGroup(Model m, List<string> types, List<V2> at, out GroupState state)
    {
        var refused = new HashSet<(string, int)>();
        var asked = new Dictionary<(string, int, int, bool), float?>();   // as Model.ExtentKey: a crop stack per crate, else per unit
        float? Extent(string t, int u, int k, bool mirrored)
        {
            var key = (t, k >= 0 ? -1 - m.Units[u].Group : u, k, mirrored);
            return asked.TryGetValue(key, out var e) ? e : asked[key] = m.Extent(t, u, k, mirrored);
        }
        var unitsOf = new Dictionary<int, List<int>>();
        var firstIndex = new Dictionary<string, int>(StringComparer.Ordinal);
        int FirstIndex(string t) => firstIndex.TryGetValue(t, out int i) ? i : firstIndex[t] = types.IndexOf(t);
        // Would these kinds (claim order) in group g, at the caps their stocks give, each draw a copy on their side? Each at its
        // narrowest: any of its crop stacks it would take, as is or mirrored, or any unit of the group. Too narrow there: certainly
        // nothing drawn, so the share is passed over; else ByGroup's check below has the last word.
        bool Foresee(List<string> kinds, int g, Dictionary<string, int> count, int total)
        {
            if (m.Extent == null || total < kinds.Count) return true;
            if (!unitsOf.TryGetValue(g, out var gu)) unitsOf[g] = gu = Enumerable.Range(0, m.Units.Count).Where(u => m.Units[u].Group == g).ToList();
            if (gu.All(u => HungOn(m, m.Units[u]))) return true;
            var caps = Caps(total, kinds, count);
            var n = kinds.Select((t, j) => PlanMath.Min(count[t], caps[j])).ToArray();
            var order = Enumerable.Range(0, kinds.Count).OrderBy(j => FirstIndex(kinds[j])).ToList();   // left to right as SplitShared sets them
            var edge = Edges(gu.Select(u => m.Units[u]).ToList(), order.Select(j => n[j]).ToArray());
            for (int s = 0; s < order.Count; s++)
            {
                string t = kinds[order[s]];
                var side = new PlanSplit(edge[s + 1], edge[s], s < order.Count - 1, s > 0);
                string lay = m.Crops == null ? null : m.Crops.TryGetValue(t, out var own) ? (own != null ? t : null)
                    : m.Crops.TryGetValue("_generic", out var gen) ? (gen != null ? "_generic" : null) : null;
                bool crop = lay != null && m.CrateFloors is int floors && g >= 0 && g < floors;
                bool any = false;
                for (int k = 0; k < n[order[s]] && !any; k++)
                    any = crop && k < m.Crops[lay].Value ? Holds(Extent(t, gu[0], k, false), side) || Holds(Extent(t, gu[0], k, true), side)
                        : gu.Any(u => Holds(Extent(t, u, -1, false), side));
                if (!any) return false;
            }
            return true;
        }
        while (true)
        {
            var joined = new List<(string, int)>();
            var passed = new HashSet<string>();
            var result = Fill(m, types, at, refused, joined, passed, Foresee, out state);
            if (state == null || m.Extent == null || state.Split.Count == 0) return result;
            // Per split group and kind: does any of its stacks draw a copy? The crop stack and variant as UnitPlan.Make will choose them.
            var variant = m.Crops != null ? CropVariants(m, types, result) : null;
            var rank = new Dictionary<(int, string), int>();
            var draws = new Dictionary<(int, string), bool>();
            for (int i = 0; i < types.Count && i < m.Units.Count; i++)
            {
                int u = result[i];
                if (u < 0 || !state.Split.TryGetValue(u, out var side) || HungOn(m, m.Units[u])) continue;
                int g = m.Units[u].Group;
                rank.TryGetValue((g, types[i]), out int k);
                rank[(g, types[i])] = k + 1;
                string lay = m.Crops == null ? null : m.Crops.TryGetValue(types[i], out var own) ? (own != null ? types[i] : null)
                    : m.Crops.TryGetValue("_generic", out var gen) ? (gen != null ? "_generic" : null) : null;
                bool crop = lay != null && m.CrateFloors is int floors && g >= 0 && g < floors && k < m.Crops[lay].Value;
                bool fits = Holds(Extent(types[i], u, crop ? k : -1, crop && variant.TryGetValue(g, out int v) && v == 1), side);
                draws[(g, types[i])] = fits || draws.TryGetValue((g, types[i]), out bool d) && d;
            }
            var more = new HashSet<(string, int)>();
            foreach (var grp in draws.GroupBy(kv => kv.Key.Item1).OrderBy(x => x.Key))
            {
                var narrow = grp.Where(kv => !kv.Value).Select(kv => kv.Key.Item2).ToList();
                if (narrow.Count == 0) continue;
                var joiners = joined.Where(x => x.Item2 == grp.Key).Select(x => x.Item1).ToList();
                var go = narrow.Where(joiners.Contains).ToList();
                if (go.Count == 0 && joiners.Count > 0) go.Add(joiners[joiners.Count - 1]);
                foreach (var t in go) more.Add((t, grp.Key));
            }
            if (more.Count == 0)
            {
                foreach (var (t, _) in refused) state.TooWide.Add(t);
                state.TooWide.UnionWith(passed);
                return result;
            }
            refused.UnionWith(more);
        }
    }

    // Each crate its own variant of its crop's layout (the coordinator, 25 Oct: the schema has one layout per crop, so two crates of
    // one crop looked identical): the nth crate holding a crop, in crate order, is drawn as is (0) or mirrored across (1).
    static Dictionary<int, int> CropVariants(Model m, List<string> kinds, int[] crates)
    {
        var firstCrop = new SortedDictionary<int, string>();
        for (int i = 0; i < kinds.Count && i < crates.Length; i++)
            if (crates[i] >= 0 && crates[i] < m.Units.Count && m.Units[crates[i]].Group is var g && g >= 0 && !firstCrop.ContainsKey(g))
                firstCrop[g] = kinds[i];
        var cropVariant = new Dictionary<int, int>();
        var nth = new Dictionary<string, int>(StringComparer.Ordinal);
        foreach (var kv in firstCrop)
        {
            nth.TryGetValue(kv.Value, out int n);
            cropVariant[kv.Key] = n % 2;
            nth[kv.Value] = n + 1;
        }
        return cropVariant;
    }

    // A copy of half-width `e` stays on side s: StoreModel.KeepSide's own test (6 cm board, so 4 cm clear of its middle). Null: no model to measure.
    static bool Holds(float? e, PlanSplit s)
    {
        if (e is not float x) return true;
        float half = x + 0.04f;
        float lo = s.Lo + (s.LoBoard ? half : x), hi = s.Hi - (s.HiBoard ? half : x);
        return !(lo > hi);
    }

    // The meat rack's hooks hang whole bundles (MeatBundles), never on a side of a bay.
    static bool HungOn(Model m, Unit u) => m.Slug == "meatrack" && u.Kind == "bundle";

    static int[] Fill(Model m, List<string> types, List<V2> at, HashSet<(string, int)> refused, List<(string, int)> joined, HashSet<string> passed,
        Func<List<string>, int, Dictionary<string, int>, int, bool> foresee, out GroupState state)
    {
        state = null;
        var Units = m.Units;
        if (Units.Count == 0 || Units[0].Group < 0) return null;
        var free = Units.Select((u, i) => (u, i)).Where(x => x.u.Group >= 0).GroupBy(x => x.u.Group)
            .ToDictionary(g => g.Key, g => new Queue<int>(g.Select(x => x.i)));
        var centre = Units.Where(u => u.Group >= 0).GroupBy(u => u.Group)
            .ToDictionary(g => g.Key, g => g.Aggregate(V3.zero, (sum, u) => sum + u.Pos) / g.Count());
        float x0 = centre.Values.Min(c => c.x), x1 = centre.Values.Max(c => c.x);
        float y0 = centre.Values.Min(c => c.y), y1 = centre.Values.Max(c => c.y);
        float z0 = centre.Values.Min(c => c.z), z1 = centre.Values.Max(c => c.z);
        bool tall = y1 - y0 > z1 - z0;
        static float Part(float a, float span) => span > 1e-3f ? a / span : 0.5f;
        var spot = centre.ToDictionary(kv => kv.Key, kv => new V2(Part(x1 - kv.Value.x, x1 - x0),   // +x is the left side
            tall ? Part(y1 - kv.Value.y, y1 - y0) : Part(kv.Value.z - z0, z1 - z0)));                // front is +z
        // What can't hang goes in a bin, never on a hook (Joost: "an egg on the hooks would be ridiculous, it's a meat rack").
        // Only the Meat Rack's hooks (Joost, 27 Oct: the Root Bin's two "bundle" crates are crates; eggs and the like may go in).
        var hooks = new HashSet<int>(centre.Keys.Where(k => Units.Where(u => u.Group == k).All(u => HungOn(m, u))));
        static bool Hangs(string type) => StorageReviewPolicy.CanHangMeat(type);
        // Homes stores: the group whose layout was made for this item comes first (coins in the coin well, tar in the tar
        // barrel). Arrows, bolts and bombs only ever go where their own kind of holder stands (Fletcher's Barrels).
        // A group may be home to two kinds (a planned pair, Joost 24 Oct: "seven things in six bays: the biggest bay holds two that
        // belong together, with a divider"): its units then say which kind each is for, and the model carries the divider.
        var homeOf = m.Homes ? Units.Where(u => u.Group >= 0 && u.Item != null).GroupBy(u => u.Group)
            .ToDictionary(g => g.Key, g => new HashSet<string>(g.Select(u => u.Item), StringComparer.Ordinal)) : null;
        var PlannedPairs = new HashSet<int>();
        if (homeOf != null) foreach (var kv in homeOf) if (kv.Value.Count > 1) PlannedPairs.Add(kv.Key);
        // Places whose vessel follows the item (Places): any place takes any family, and a stack takes only its family's units.
        bool perPlace = m.Places.Count > 0;
        string SlotOf(string type) => perPlace ? m.FamilyOf(type) : null;
        var freeBy = Units.Select((u, i) => (u, i)).Where(x => x.u.Group >= 0).GroupBy(x => (x.u.Group, perPlace ? x.u.Kind : PlannedPairs.Contains(x.u.Group) ? x.u.Item : null))
            .ToDictionary(g => g.Key, g => new Queue<int>(g.Select(x => x.i)));
        string Sub(int g, string type) => perPlace ? SlotOf(type) : PlannedPairs.Contains(g) ? type : null;
        bool Room(int g, string type) => freeBy.TryGetValue((g, Sub(g, type)), out var q) && q.Count > 0;
        // Holder families only where the store has them: the Cloth Rack's cloth "bolt" units are no crossbow bolts (Joost, 24 Oct:
        // "the cloth rack shows nothing").
        var familyOf = !perPlace && m.KindSlug is "fletcher" or "apothecary"
            ? Units.Where(u => u.Group >= 0 && Family(u.Kind, m.Ammo) != null).GroupBy(u => u.Group).ToDictionary(g => g.Key, g => g.First().Kind)
            : new Dictionary<int, string>();
        // Joost, 24 Oct: (1) everything in the store shows from outside, (2) nothing lies mixed ("you'd never do that IRL").
        var result = Enumerable.Repeat(-1, types.Count).ToArray();
        var count = new Dictionary<string, int>();
        var firstAt = new Dictionary<string, V2>();
        for (int i = 0; i < types.Count; i++)
        {
            count.TryGetValue(types[i], out int c);
            count[types[i]] = c + 1;
            if (!firstAt.ContainsKey(types[i])) firstAt[types[i]] = at[i];
        }
        bool soft = familyOf.Values.Any(softFamilies.Contains);
        // A store whose groups have homes is laid out by name, not by where the stacks sit in the chest: sorting the chest never
        // changes the picture (Joost's test, 25 Oct: the Jeweller's Casket after a sort). Bulk stores keep following the grid
        // (Joost, 22 Oct: bottom left in the chest is bottom left in the bin).
        bool stable = m.Homes;
        bool CoinWell(int k) => m.KindSlug == "treasure" && homeOf != null && homeOf.TryGetValue(k, out var home) && home.Contains("Coins");
        bool Eligible(string type, int k, bool strict) => (Hangs(type) || !hooks.Contains(k))
            && StorageReviewPolicy.CoinWellAllows(m.KindSlug, CoinWell(k), type)
            && (!strict || familyOf.Count == 0 || (familyOf.TryGetValue(k, out var f) ? f == Family(type, m.Ammo) : Family(type, m.Ammo) == null));
        // Of the groups a type may use, those the fewest types present may use come first, so the places anything fits stay free for
        // what fits nowhere else (Joost, 27 Oct: meat that can hang takes the hooks before a bin, so the bins stay for what can't hang,
        // the blood bags, freeze glands and entrails). Where every group takes every type, all count the same and nothing changes.
        var users = free.Keys.ToDictionary(g => g, g => count.Keys.Count(t => Eligible(t, g, true)));
        // The group nearest to where the type's first stack sits in the grid; an Apothecary tier that is full may use another.
        int Nearest(string type, Func<int, bool> ok, Func<int, float> rank = null)
        {
            foreach (bool strict in soft ? new[] { true, false } : new[] { true })
            {
                int k = free.Keys.Where(g => ok(g) && Eligible(type, g, strict))
                    .OrderBy(g => users[g]).ThenBy(g => rank?.Invoke(g) ?? 0f).ThenBy(g => stable ? 0f : (spot[g] - firstAt[type]).sqrMagnitude).ThenBy(g => g).DefaultIfEmpty(-1).First();
                if (k >= 0) return k;
            }
            return -1;
        }
        // Every group Nearest would give, in the order it would give them were each passed over in turn.
        List<int> NearestAll(string type, Func<int, bool> ok, Func<int, float> rank)
        {
            var order = new List<int>();
            foreach (bool strict in soft ? new[] { true, false } : new[] { true })
                order.AddRange(free.Keys.Where(g => !order.Contains(g) && ok(g) && Eligible(type, g, strict))
                    .OrderBy(g => users[g]).ThenBy(g => rank(g)).ThenBy(g => stable ? 0f : (spot[g] - firstAt[type]).sqrMagnitude).ThenBy(g => g).ToList());
            return order;
        }
        var claims = new Dictionary<string, List<int>>();   // the groups each type holds, its first one first
        var owner = new Dictionary<int, List<string>>();    // the types in a group: one, or two with a board between them
        void Claim(string type, int k)
        {
            if (!claims.TryGetValue(type, out var l)) claims[type] = l = new List<int>();
            l.Add(k);
            if (!owner.TryGetValue(k, out var o)) owner[k] = o = new List<string>();
            o.Add(type);
        }
        // Fletcher's Barrels: each barrel's painted band says what goes in (Joost, 24 Oct: "the green and orange barrels, you knew
        // where the fire and the frost arrows were"). Groups as fletcher_r2 paints them: 0 bone white, 1 slate blue, 2 moss green,
        // 3 rust orange, 4 char black, 5 verdigris; tubs 6 verdigris, 7 char black; crate halves 8 bile yellow, 9 ember red.
        var colourHome = m.KindSlug == "fletcher" ? FletcherColours : null;
        bool HomeOfPresent(int k) => homeOf != null && homeOf.TryGetValue(k, out var h) && h.Any(count.ContainsKey)
            || colourHome != null && colourHome.Any(kv => kv.Value == k && count.ContainsKey(kv.Key));
        // 1. Every type gets a group of its own: its home first, else the nearest group no type present calls home. Types with
        //    a home go first, then the most plentiful, so with more types than groups it is a stray stack that waits.
        // A rack whose vessel follows the item is kept sorted (Joost, 24 Oct: "in a cabinet you put things together, not mixed;
        // it looks calmer"): the families in a fixed order (hooks, glass, crocks, baskets: light on top, heavy below), each kind by
        // name, taking the places in reading order, as many as its stock needs. With more stock than places each kind keeps one.
        if (perPlace)
        {
            var famOrder = m.FamilyOrder.Count > 0 ? m.FamilyOrder.ToArray() : new[] { "hanging", "jar", "crock", "basket" };
            int Rank(string t) { int r = Array.IndexOf(famOrder, SlotOf(t)); return r < 0 ? famOrder.Length : r; }
            var sorted = count.Keys.OrderBy(Rank).ThenBy(t => t, StringComparer.Ordinal).ToList();
            var places = free.Keys.OrderBy(g => g).ToList();
            int PerPlace(string t) => Math.Max(1, freeBy.TryGetValue((places[0], SlotOf(t)), out var q) ? q.Count : 1);
            var need = sorted.ToDictionary(t => t, t => (count[t] + PerPlace(t) - 1) / PerPlace(t));
            while (need.Values.Sum() > places.Count && need.Values.Any(n => n > 1))
            {
                var most = need.OrderByDescending(kv => kv.Value).First().Key;
                need[most]--;
            }
            int next = 0;
            foreach (var t in sorted)
                for (int n = 0; n < need[t] && next < places.Count; n++) Claim(t, places[next++]);
        }
        var unplaced = new List<string>();
        // The other half of that rule: a type fewer groups take chooses before one any group takes (what can't hang before what can).
        var reach = count.Keys.ToDictionary(t => t, t => free.Keys.Count(g => Eligible(t, g, true)));
        foreach (var t in perPlace ? new List<string>() : count.Keys.OrderByDescending(t => homeOf != null && homeOf.Values.Any(h => h.Contains(t)))
            .ThenBy(t => reach[t]).ThenByDescending(t => stable ? 0 : count[t]).ThenBy(t => stable ? 0 : types.IndexOf(t)).ThenBy(t => t, StringComparer.Ordinal).ToList())
        {
            int k = -1;
            if (colourHome != null && colourHome.TryGetValue(t, out int painted) && free.ContainsKey(painted)
                && (!owner.TryGetValue(painted, out var there) || there.Count == 1 && colourHome.TryGetValue(there[0], out int theirs) && theirs == painted))
                k = painted;   // its own colour, alone or beside the other kind of that colour
            if (k < 0) k = homeOf == null ? -1 : homeOf.Where(kv => kv.Value.Contains(t) && (!owner.ContainsKey(kv.Key) || kv.Value.Count > 1 && owner[kv.Key].Count == 1 && kv.Value.Contains(owner[kv.Key][0])))
                .Select(kv => kv.Key).DefaultIfEmpty(-1).First();
            if (k < 0) k = Nearest(t, g => !owner.ContainsKey(g) && !HomeOfPresent(g));
            if (k < 0) k = Nearest(t, g => !owner.ContainsKey(g));
            if (k >= 0) Claim(t, k); else unplaced.Add(t);
        }
        // 2. More types than groups: two share a group with a board between them, the group whose type has the least stock. A
        //    vessel of liquid is never shared. Still more types (review 25 Oct: fourteen kinds in the bunker's three bays): in a
        //    store without homes a bay takes a third kind and more, each beside the next with a board, as long as every kind
        //    keeps two units of the bay. Visible beats unmixed (Joost, 24 Oct: first everything visible, then nothing mixed).
        // A share is foreseen before it is made (the sides it would split, at the stocks the caps will give), and passed over where a kind
        // would draw no copy even at its narrowest (ByGroup checks the plan as made; this keeps it from making the same plan many times).
        if (m.Liquids.Count == 0 && m.KindSlug != "apothecary")   // the Apothecary Rack: a vessel per place, never two kinds in one
            foreach (var t in unplaced)
            {
                bool Foreseen(int g)
                {
                    if (foresee == null || foresee(owner[g].Append(t).ToList(), g, count, freeBy.TryGetValue((g, Sub(g, t)), out var q) ? q.Count : 0)) return true;
                    passed.Add(t);
                    return false;
                }
                int k = -1;
                foreach (int c in NearestAll(t, g => owner.TryGetValue(g, out var o) && o.Count == 1 && !refused.Contains((t, g)), g => count[owner[g][0]]))
                    if (Foreseen(c)) { k = c; break; }
                if (k < 0 && homeOf == null && colourHome == null)
                    foreach (int c in NearestAll(t, g => owner.TryGetValue(g, out var o) && o.Count >= 2 && !PlannedPairs.Contains(g) && !refused.Contains((t, g))
                        && free[g].Count >= 2 * (o.Count + 1), g => owner[g].Count * 1000f + owner[g].Sum(x => count[x])))
                        if (Foreseen(c)) { k = c; break; }
                if (k >= 0) { Claim(t, k); joined.Add((t, k)); }
            }
        // A shared group is split by stock before filling, or the type that comes first in the grid (after a Sort, all of one
        // kind) fills it and the other never shows (Joost, 24 Oct: seven kinds in the Ossuary, six to be seen). Each side keeps at
        // least a fifth of the group (with more than two kinds: an equal part of two fifths).
        var cap = new Dictionary<(int, string), int>();
        var used = new Dictionary<(int, string), int>();
        foreach (var kv in owner.Where(kv => kv.Value.Count >= 2 && !PlannedPairs.Contains(kv.Key)))
        {
            var kinds = kv.Value;
            int total = freeBy.TryGetValue((kv.Key, SlotOf(kinds[0])), out var q) ? q.Count : 0;
            if (total < kinds.Count) continue;
            var share = Caps(total, kinds, count);
            for (int j = 0; j < kinds.Count; j++) cap[(kv.Key, kinds[j])] = share[j];
        }
        bool Fits(int g, string type) => Room(g, type) && (!cap.TryGetValue((g, type), out int c) || (used.TryGetValue((g, type), out int n) ? n : 0) < c);
        // 3. Fill in slot order: each stack into its own groups; a type that fills them may take a group nobody holds, never one
        //    where another type lies. What doesn't fit is not drawn: the group already looks full.
        for (int i = 0; i < types.Count; i++)
        {
            if (!claims.TryGetValue(types[i], out var mine)) continue;
            int k = mine.Where(g => Fits(g, types[i])).DefaultIfEmpty(-1).First();
            if (k < 0)
            {
                k = Nearest(types[i], g => !owner.ContainsKey(g) && Room(g, types[i]));
                if (k >= 0) Claim(types[i], k);
            }
            if (k < 0) continue;
            result[i] = freeBy[(k, Sub(k, types[i]))].Dequeue();
            used[(k, types[i])] = (used.TryGetValue((k, types[i]), out int u0) ? u0 : 0) + 1;
        }
        var home = claims.ToDictionary(kv => kv.Key, kv => kv.Value[0]);   // the group each type claimed first: its side
        state = new GroupState { PlannedPairs = PlannedPairs };
        SplitShared(m, types, result, home, spot, state);
        return result;
    }

    // How many units of a shared group each kind takes (kinds in claim order).
    static int[] Caps(int total, List<string> kinds, Dictionary<string, int> count)
    {
        if (kinds.Count == 2)
        {
            string a = kinds[0], b = kinds[1];
            int least = PlanMath.Max(1, PlanMath.CeilToInt(total * 0.2f));
            int nb = PlanMath.Clamp(PlanMath.RoundToInt(total * (float)count[b] / (count[a] + count[b])), PlanMath.Min(count[b], least), total - PlanMath.Min(count[a], least));
            return new[] { total - nb, nb };
        }
        int floor = PlanMath.Max(1, PlanMath.FloorToInt(total * 0.4f / kinds.Count));
        var share = kinds.Select(t => PlanMath.Min(count[t], floor)).ToArray();
        int rest = total - share.Sum(), all = kinds.Sum(t => count[t]);
        var want = kinds.Select(t => total * (float)count[t] / all).ToArray();
        while (rest > 0)
        {
            int best = -1;
            float gap = float.MinValue;
            for (int j = 0; j < kinds.Count; j++) if (share[j] < count[kinds[j]] && want[j] - share[j] > gap) { gap = want[j] - share[j]; best = j; }
            if (best < 0) break;
            share[best]++;
            rest--;
        }
        return share;
    }

    // Where the boards of a shared group stand: edge[j] is side j's left (+x) edge, edge[j+1] its right one; n: each side's stacks.
    static float[] Edges(List<Unit> all, int[] n)
    {
        float xl = all.Max(u => u.Pos.x + u.Box.x / 2f), xr = all.Min(u => u.Pos.x - u.Box.x / 2f);
        float least = n.Length == 2 ? 0.15f : PlanMath.Min(0.15f, 0.6f / n.Length);
        var part = n.Select(c => PlanMath.Max(least, c / (float)n.Sum())).ToArray();
        float sum = part.Sum();
        var edge = new float[n.Length + 1];
        edge[0] = xl;
        // In double, rounded only where stored: the game's Mono evaluates float expressions at double precision, .NET 8 (planrun) per
        // step in float; written out, both give the game's bits (the gate of 27 Oct: 6 plans 1-3 ulp apart here).
        for (int j = 0; j < n.Length; j++) edge[j + 1] = (float)((double)edge[j] - ((double)xl - (double)xr) * (double)part[j] / (double)sum);
        edge[n.Length] = xr;
        return edge;
    }

    // A group two types ended up sharing (both overflowed into the middle bay; Joost: "this one is still mixed") is split in
    // two halves across: each type gets the half on the side of its own group, so they lie as two heaps side by side.
    static void SplitShared(Model m, List<string> types, int[] result, Dictionary<string, int> home, Dictionary<int, V2> spot, GroupState state)
    {
        var Units = m.Units;
        var PlannedPairs = state.PlannedPairs;
        var Dividers = state.Dividers;
        var SplitSide = state.Split;
        var shared = Enumerable.Range(0, types.Count).Where(i => result[i] >= 0).GroupBy(i => Units[result[i]].Group)
            .Where(g => g.Select(i => types[i]).Distinct().Count() >= 2 && !PlannedPairs.Contains(g.Key));   // a planned pair has its own divider
        foreach (var g in shared)
        {
            // The kinds left to right as their homes stand (a kind that joined this bay has it as its home: it keeps its place in
            // the grid order). +x is the left side; spot x grows to the right.
            var kinds = g.Select(i => types[i]).Distinct().Select((t, n) => (t, n)).OrderBy(x => spot[home[x.t]].x).ThenBy(x => x.n).Select(x => x.t).ToList();
            var n = kinds.Select(t => g.Count(i => types[i] == t)).ToArray();
            // Two types in one group always get the board (Joost, 24 Oct: never mixed). The boards stand where the kinds' shares
            // meet (Joost: 15 coal and 3 stone is a big heap and a small one, not two halves), each share kept a little wide.
            var units = Units.Select((u, k) => (u, k)).Where(x => x.u.Group == g.Key).ToList();
            var all = units.Select(x => x.u).ToList();
            var edge = Edges(all, n);   // edge[j] is side j's left (+x) edge, edge[j+1] its right one
            // Each side takes the units on its own stretch in the layout's own fill order (a settled heap's later units rest on
            // earlier ones); a side that runs out borrows from the side with most to spare, and those copies are moved across below.
            var queue = Enumerable.Range(0, kinds.Count).Select(j => new Queue<int>(units.Where(x => x.u.Pos.x <= edge[j] && (x.u.Pos.x > edge[j + 1] || j == kinds.Count - 1)).Select(x => x.k))).ToArray();
            foreach (int i in g)
            {
                int j = kinds.IndexOf(types[i]);
                var from = queue[j].Count > 0 ? queue[j] : queue.OrderByDescending(q => q.Count).First();
                result[i] = from.Count > 0 ? from.Dequeue() : -1;
                if (result[i] >= 0) SplitSide[result[i]] = new PlanSplit(edge[j + 1], edge[j], j < kinds.Count - 1, j > 0);
            }
            // And a board pushed in between each two, front to back (Joost: "as if someone stuck a plank in"), from the floor to
            // just over the heap, so you see the bay is split (StoreModel.Apply stands the plank up).
            float z0 = all.Min(u => u.Pos.z - u.Box.z / 2f), z1 = all.Max(u => u.Pos.z + u.Box.z / 2f);
            float y0 = all.Min(u => u.Pos.y - u.Box.y / 2f), y1 = PlanMath.Max(y0 + 0.3f, all.Max(u => u.Pos.y + u.Box.y / 2f) + 0.05f);
            // The separator fits the store (SPEC.md): a thick plank between heavy bulk, a thin board between crops; arrows (tied
            // bundles) and folded hides (piles) need none.
            if (m.KindSlug is "fletcher" or "hiderack" or "jeweller") continue;   // the Jeweller: one kind a tray, never a board (Joost, 25 Oct)
            float thick = m.KindSlug == "rootbin" ? 0.4f : 1f;
            if (kinds.Count > 2 && !m.ManyKindBoards) continue;   // side by side, each heap kept to its own stretch
            for (int j = 1; j < kinds.Count; j++)
                Dividers.Add(new Divider { X = edge[j], Y0 = y0, Y1 = y1, Z0 = z0, Z1 = z1, Thick = thick });
        }
    }

    // Which holder an item belongs in, as the units of a store are marked ("kind"). Fletcher's Barrels: arrows, bolts and bombs,
    // strictly. The Apothecary Rack: what is dry and light hangs, what is wet and soft stands in glass, small hard things go in
    // clay crocks, big ones in baskets (Joost: "give certain items certain containers"); there an item may take another tier
    // once its own is full. Null: no family. `ammo`: the item's ammo family as the game says it (StoreModel.AmmoFamily).
    static readonly Dictionary<string, string> apothecary = new()
    {
        ["Feathers"] = "hanging", ["WolfHairBundle"] = "hanging", ["ElakingHairBundle"] = "hanging", ["MooseSinew"] = "hanging", ["MorgenSinew"] = "hanging",
        ["GreydwarfEye"] = "jar", ["RoyalJelly"] = "jar", ["Ectoplasm"] = "jar", ["GiantBloodSack"] = "jar", ["DragonTear"] = "jar", ["AskBladder"] = "jar",
        ["Needle"] = "crock", ["WolfFang"] = "crock", ["WolfClaw"] = "crock", ["SurtlingCore"] = "crock", ["Mandible"] = "crock", ["MorgenHeart"] = "crock", ["Bilebag"] = "crock",
        ["Chitin"] = "basket", ["Carapace"] = "basket", ["SerpentScale"] = "basket", ["BonemawSerpentScale"] = "basket", ["BjornPaw"] = "basket", ["CelestialFeather"] = "basket",
    };
    static readonly HashSet<string> softFamilies = new() { "hanging", "jar", "crock", "basket" };
    public static string Family(string prefabOrKind, Func<string, string> ammo) => prefabOrKind == null ? null
        : softFamilies.Contains(prefabOrKind) ? prefabOrKind
        : apothecary.TryGetValue(prefabOrKind, out var tier) ? tier
        : ammo(prefabOrKind) is { } a ? a
        : prefabOrKind.StartsWith("Arrow", StringComparison.OrdinalIgnoreCase) || prefabOrKind == "arrow" ? "arrow"
        : prefabOrKind.StartsWith("Bolt", StringComparison.OrdinalIgnoreCase) || prefabOrKind == "bolt" ? "bolt"
        : prefabOrKind.StartsWith("Bomb", StringComparison.OrdinalIgnoreCase) || prefabOrKind == "Dynamite" || prefabOrKind == "bomb" ? "bomb"
        : null;

    static readonly Dictionary<string, int> FletcherColours = new(StringComparer.Ordinal)
    {
        ["ArrowWood"] = 0, ["ArrowSilver"] = 0, ["ArrowNeedle"] = 0,
        ["ArrowFrost"] = 1, ["ArrowIron"] = 1,
        ["ArrowPoison"] = 2,
        ["ArrowFire"] = 3, ["ArrowCharred"] = 3,
        ["ArrowObsidian"] = 4, ["ArrowFlint"] = 4,
        ["ArrowBronze"] = 5, ["ArrowCarapace"] = 5,
        ["BoltBone"] = 6, ["BoltCarapace"] = 6,
        ["BoltIron"] = 7, ["BoltBlackmetal"] = 7, ["BoltCharred"] = 7,
        ["BombBile"] = 8, ["BombOoze"] = 8,
        ["BombLava"] = 9, ["BombSmoke"] = 9, ["Dynamite"] = 9,
        // ValheimArmory (Joost, 24 Oct): bone white for bone, rust orange for surtling fire, char black for black metal, verdigris for
        // chitin and ancient; its bolts in the two tubs.
        ["VAArrowBone"] = 0, ["VAarrow_surtling_fire"] = 3, ["VAArrowGreenMetal"] = 4, ["VAChitinArrow"] = 5, ["VAArrowAncient"] = 5,
        ["VABoltWood"] = 6, ["VABoltCoreWood"] = 6, ["VABoltNeedle"] = 6, ["VAbolt_bronze"] = 6, ["VAbolt_poison"] = 6, ["VAbolt_frost"] = 6,
        ["VAFireBolt"] = 7, ["VASurtlingBolt"] = 7, ["VAObsidianBolt"] = 7,
    };

#if !RELEASE
    // Why a kind has no place at all: no group would take it, or (Joost, 27 Oct) every group it could share had no side wide enough.
    public string NoPlace(string kind) => State != null && State.TooWide.Contains(kind) ? "no place: every group it could share is full or too narrow for it" : "no place for its kind in this model";

    // The not-shown line: per kind with stacks not shown, how many and why; `at` per stack its unit, -1 when it does not show. The plan
    // says it of its places (UnshownLine); the drawing says it again of what it drew, when a stack it placed drew nothing.
    public static string NotShown(string title, List<string> kinds, List<int> at, int sampled, Func<string, string> none)
    {
        var missing = kinds.Select((t, i) => (t, i)).Where(x => x.i < at.Count).GroupBy(x => x.t).Where(k => k.Any(x => at[x.i] < 0))
            .Select(k => $"{k.Key} x{k.Count(x => at[x.i] < 0)} ({(k.All(x => at[x.i] < 0) ? none(k.Key) : $"its places are full, {k.Count(x => at[x.i] >= 0)} shown")})").ToList();
        return missing.Count == 0 && sampled <= 0 ? null
            : $"{title}: not shown: {(missing.Count > 0 ? string.Join(", ", missing) : "none")}" + (sampled > 0 ? $"; {sampled} stack(s) left out by the stock sample (more stacks than places)" : "");
    }

    // ---- The capture's files (storehouse_selftest capture, planrun): the inputs and the plan as JSON, one writer for both sides, so
    // the game's file and planrun's are the same text exactly when the plans are the same. A float is its 32 bits in hex ("x3f800000"),
    // so no runtime's number formatting can tell two equal floats apart, or two unequal ones together.

    public string ToJson()
    {
        string StackJson(Stack s) => J.Obj(("item", J.I(s.Item)), ("unit", J.I(s.Unit)), ("liquid", J.I(s.Liquid)), ("draw", J.S(s.Draw.ToString().ToLowerInvariant())),
            ("layout", J.S(s.Layout)), ("k", J.I(s.K)), ("variant", J.I(s.Variant)), ("cap", J.I(s.Cap)), ("n", J.I(s.N)), ("hang", J.B(s.Hang)), ("bind", J.B(s.Bind)));
        var o = new StringBuilder("{\n");
        void Line(string key, string value, bool last = false) => o.Append("  ").Append(J.S(key)).Append(": ").Append(value).Append(last ? "\n" : ",\n");
        Line("order", J.S(Order));
        Line("per_stack", J.I(PerStack));
        Line("items", J.Arr(Items, J.I));
        Line("grid", Grid == null ? "null" : J.Arr(Grid, J.I));
        Line("crates", Crates == null ? "null" : J.Arr(Crates, J.I));
        Line("assigned", J.Arr(Assigned, J.I));
        Line("unseen", J.I(Unseen));
        Line("crop_variant", CropVariant == null ? "null" : J.Map(CropVariant, kv => kv.Key.ToString(CultureInfo.InvariantCulture), kv => J.I(kv.Value)));
        Line("state", State == null ? "null" : J.Obj(("planned_pairs", J.Arr(State.PlannedPairs, J.I)),
            ("dividers", J.Arr(State.Dividers, d => J.Arr(new[] { d.X, d.Y0, d.Y1, d.Z0, d.Z1, d.Thick }, J.F))), ("split", Splits(State.Split))));
        Line("split", Splits(Split));
        Line("topless", J.B(Topless));
        Line("dividers", J.B(Dividers));
        Line("stacks", Stacks.Count == 0 ? "[]" : "[\n    " + string.Join(",\n    ", Stacks.Select(StackJson)) + "\n  ]");
        Line("shown", J.I(Shown));
        Line("label_item", J.Map(LabelItem, kv => kv.Key.ToString(CultureInfo.InvariantCulture), kv => J.I(kv.Value)));
        Line("liquids", J.Arr(Liquids, l => J.Arr(new[] { J.I(l.Liquid), J.F(l.Below), J.F(l.Share) }, x => x)));
        Line("labels", J.Arr(Labels, l => J.Arr(new[] { l.Label, l.Item }, J.I)));
        Line("places", J.Arr(Places, l => J.Arr(new[] { J.I(l.Place), J.S(l.Family) }, x => x)));
        Line("panels", J.Arr(Panels, l => J.Arr(new[] { l.Panel, l.Item }, J.I)));
        Line("bands", J.Arr(Bands, l => J.Arr(new[] { l.Band, l.Item }, J.I)));
        Line("bay_line", J.S(BayLine));
        Line("unshown_line", J.S(UnshownLine));
        Line("undrawn_line", J.S(UndrawnLine), last: true);
        return o.Append("}\n").ToString();
    }

    static string Splits(Dictionary<int, PlanSplit> d) => J.Map(d, kv => kv.Key.ToString(CultureInfo.InvariantCulture),
        kv => J.Arr(new[] { J.F(kv.Value.Lo), J.F(kv.Value.Hi), J.B(kv.Value.LoBoard), J.B(kv.Value.HiBoard) }, x => x));

    // The inputs as the plan read them, with the facts it asked for: the "plan_model" section of a capture's inputs.json. planrun reads
    // it back and writes it again; the two texts must be the same (nothing lost on the way).
    public static string InputsJson(Inputs input)
    {
        var m = input.Model;
        string Unit(Unit u) => J.Obj(("pos", J.Arr(new[] { u.Pos.x, u.Pos.y, u.Pos.z }, J.F)), ("box", J.Arr(new[] { u.Box.x, u.Box.y, u.Box.z }, J.F)),
            ("group", J.I(u.Group)), ("kind", J.S(u.Kind)), ("item", J.S(u.Item)), ("copies", J.I(u.Copies)));
        string Row(Row r) => J.Obj(("kind", J.S(r.Kind)), ("drop", J.S(r.Drop)), ("stack", J.I(r.Stack)), ("max", J.I(r.Max)), ("x", J.I(r.X)), ("y", J.I(r.Y)));
        string Opt(int? v) => v.HasValue ? J.I(v.Value) : "null";
        var o = new StringBuilder("{\n");
        void Line(string key, string value, bool last = false) => o.Append("    ").Append(J.S(key)).Append(": ").Append(value).Append(last ? "\n" : ",\n");
        Line("width", J.I(input.Width));
        Line("height", J.I(input.Height));
        Line("max_tris_per_stack", J.I(input.MaxTrisPerStack));
        Line("rows", input.Rows.Count == 0 ? "[]" : "[\n      " + string.Join(",\n      ", input.Rows.Select(Row)) + "\n    ]");
        Line("title", J.S(m.Title));
        Line("slug", J.S(m.Slug));
        Line("kind_slug", J.S(m.KindSlug));
        Line("flags", J.Obj(("homes", J.B(m.Homes)), ("kind_per_bay", J.B(m.KindPerBay)), ("display", J.B(m.Display)), ("mirror", J.B(m.Mirror)), ("heap", J.B(m.Heap)), ("many_kind_boards", J.B(m.ManyKindBoards))));
        Line("units", m.Units.Count == 0 ? "[]" : "[\n      " + string.Join(",\n      ", m.Units.Select(Unit)) + "\n    ]");
        Line("crops", m.Crops == null ? "null" : J.Map(m.Crops, kv => kv.Key, kv => Opt(kv.Value)));
        Line("crate_floors", Opt(m.CrateFloors));
        Line("liquids", J.Arr(m.Liquids, l => J.Arr(new[] { J.I(l.Group), J.S(l.Item) }, x => x)));
        Line("labels", J.Arr(m.Labels, J.I));
        Line("places", J.Arr(m.Places, J.I));
        Line("panels", J.Arr(m.Panels, J.I));
        Line("bands", J.Arr(m.Bands, J.I));
        Line("bindings", J.Arr(m.Bindings, J.I));
        Line("item_family", J.Map(m.ItemFamily, kv => kv.Key, kv => J.S(kv.Value)));
        Line("family_order", J.Arr(m.FamilyOrder, J.S));
        Line("vessel_families", J.Arr(m.VesselFamilies, J.S));
        Line("prior_split", Splits(m.PriorSplit));
        Line("looks", J.Map(input.Looks ?? new Dictionary<string, int?>(), kv => kv.Key, kv => Opt(kv.Value)));
        Line("parts_tris", J.Map(input.Parts ?? new Dictionary<string, int?>(), kv => kv.Key, kv => Opt(kv.Value)));
        Line("ammo", J.Map(input.Ammos ?? new Dictionary<string, string>(), kv => kv.Key, kv => J.S(kv.Value)));
        Line("extents", J.Map(input.Extents ?? new Dictionary<string, Dictionary<string, float?>>(), kv => kv.Key,
            kv => J.Map(kv.Value, e => e.Key, e => e.Value.HasValue ? J.F(e.Value.Value) : "null")), last: true);
        return o.Append("  }").ToString();
    }

    public static class J
    {
        public static string I(int v) => v.ToString(CultureInfo.InvariantCulture);
        public static string B(bool v) => v ? "true" : "false";
        public static string F(float v) => "\"x" + BitConverter.ToInt32(BitConverter.GetBytes(v), 0).ToString("x8", CultureInfo.InvariantCulture) + "\"";
        public static float ParseF(string s) => BitConverter.ToSingle(BitConverter.GetBytes(int.Parse(s.Substring(1), NumberStyles.HexNumber, CultureInfo.InvariantCulture)), 0);
        public static string S(string v)
        {
            if (v == null) return "null";
            var b = new StringBuilder("\"");
            foreach (char c in v)
                if (c == '"' || c == '\\') b.Append('\\').Append(c);
                else if (c < 0x20) b.Append("\\u").Append(((int)c).ToString("x4", CultureInfo.InvariantCulture));
                else b.Append(c);
            return b.Append('"').ToString();
        }
        public static string Arr<T>(IEnumerable<T> xs, Func<T, string> f) => "[" + string.Join(", ", xs.Select(f)) + "]";
        public static string Obj(params (string k, string v)[] fields) => "{" + string.Join(", ", fields.Select(x => S(x.k) + ": " + x.v)) + "}";
        public static string Map<T>(IEnumerable<T> xs, Func<T, string> key, Func<T, string> value) => "{" + string.Join(", ", xs.Select(x => S(key(x)) + ": " + value(x))) + "}";
    }
#endif
}
