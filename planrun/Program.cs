// planrun: the units style's plan (../DisplayPlan.cs) made outside the game from a capture's inputs.json ("plan_model"), written with
// the game's own serializer, so plan-gate.py can compare it byte for byte with the <state>-plan.json the game wrote.
//   planrun <state>-inputs.json [<out>-plan.json]     one plan, to the file or stdout
//   planrun --batch <capture dir> <out dir>           every <store>/<state>-inputs.json into <out dir>/<store>/<state>-plan.json
// Exit 0 when every plan was made; 1 when one could not be (no plan_model, a fact the capture lacks, inputs that read back differently).
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using System.Text.Json;
using Finn.Storehouse;

static class Program
{
    static int Main(string[] args)
    {
        try
        {
            if (args.Length == 3 && args[0] == "--batch")
            {
                int made = 0, failed = 0;
                foreach (var store in Directory.GetDirectories(args[1]).OrderBy(d => d, StringComparer.Ordinal))
                    foreach (var file in Directory.GetFiles(store, "*-inputs.json").OrderBy(f => f, StringComparer.Ordinal))
                    {
                        string state = Path.GetFileName(file)[..^"-inputs.json".Length];
                        var dir = Path.Combine(args[2], Path.GetFileName(store));
                        try
                        {
                            var plan = Run(file);
                            Directory.CreateDirectory(dir);
                            File.WriteAllText(Path.Combine(dir, state + "-plan.json"), plan);
                            made++;
                        }
                        catch (Exception e) when (e is InvalidDataException or KeyNotFoundException or JsonException)
                        {
                            Console.Error.WriteLine($"{Path.GetFileName(store)}/{state}: {e.Message}");
                            failed++;
                        }
                    }
                Console.WriteLine($"planrun: {made} plan(s) made, {failed} failed.");
                return failed == 0 && made > 0 ? 0 : 1;
            }
            if (args.Length is 1 or 2)
            {
                var plan = Run(args[0]);
                if (args.Length == 2) File.WriteAllText(args[1], plan); else Console.Out.Write(plan);
                return 0;
            }
            Console.Error.WriteLine("usage: planrun <inputs.json> [<plan.json>] | planrun --batch <capture dir> <out dir>");
            return 2;
        }
        catch (Exception e) when (e is InvalidDataException or KeyNotFoundException or JsonException or IOException)
        {
            Console.Error.WriteLine("planrun: " + e.Message);
            return 1;
        }
    }

    // One inputs.json: its plan_model read, checked to write back as the very same text, its facts replayed, the plan made.
    static string Run(string file)
    {
        using var doc = JsonDocument.Parse(File.ReadAllText(file, Encoding.UTF8));
        if (!doc.RootElement.TryGetProperty("plan_model", out var pm)) throw new InvalidDataException("no plan_model (a capture from before the plan step?)");
        var input = Read(pm);
        string again = UnitPlan.InputsJson(input);
        if (again != pm.GetRawText())
        {
            string raw = pm.GetRawText();
            int at = 0;
            while (at < again.Length && at < raw.Length && again[at] == raw[at]) at++;
            throw new InvalidDataException($"plan_model does not read back as written (first difference at character {at}: "
                + $"file \"{Snip(raw, at)}\", read \"{Snip(again, at)}\")");
        }
        input.Replay();
        return UnitPlan.Make(input).ToJson();
    }

    static string Snip(string s, int at) => s.Substring(Math.Max(0, at - 30), Math.Min(s.Length, at + 30) - Math.Max(0, at - 30)).Replace("\n", "\\n");

    static UnitPlan.Inputs Read(JsonElement pm)
    {
        static float F(JsonElement e) => UnitPlan.J.ParseF(e.GetString());
        static V3 V(JsonElement e) => new V3(F(e[0]), F(e[1]), F(e[2]));
        static int? OptI(JsonElement e) => e.ValueKind == JsonValueKind.Null ? null : e.GetInt32();
        static List<int> Ints(JsonElement e) => e.EnumerateArray().Select(x => x.GetInt32()).ToList();
        static List<string> Strs(JsonElement e) => e.EnumerateArray().Select(x => x.GetString()).ToList();
        static Dictionary<int, PlanSplit> Splits(JsonElement e) => e.EnumerateObject().ToDictionary(p => int.Parse(p.Name),
            p => new PlanSplit(F(p.Value[0]), F(p.Value[1]), p.Value[2].GetBoolean(), p.Value[3].GetBoolean()));
        var flags = pm.GetProperty("flags");
        var crops = pm.GetProperty("crops");
        var m = new UnitPlan.Model
        {
            Title = pm.GetProperty("title").GetString(),
            Slug = pm.GetProperty("slug").GetString(),
            KindSlug = pm.GetProperty("kind_slug").GetString(),
            Homes = flags.GetProperty("homes").GetBoolean(),
            KindPerBay = flags.GetProperty("kind_per_bay").GetBoolean(),
            Display = flags.GetProperty("display").GetBoolean(),
            Mirror = flags.GetProperty("mirror").GetBoolean(),
            Heap = flags.GetProperty("heap").GetBoolean(),
            ManyKindBoards = flags.GetProperty("many_kind_boards").GetBoolean(),
            Units = pm.GetProperty("units").EnumerateArray().Select(u => new UnitPlan.Unit
            {
                Pos = V(u.GetProperty("pos")), Box = V(u.GetProperty("box")), Group = u.GetProperty("group").GetInt32(),
                Kind = u.GetProperty("kind").GetString(), Item = u.GetProperty("item").GetString(), Copies = u.GetProperty("copies").GetInt32(),
            }).ToList(),
            Crops = crops.ValueKind == JsonValueKind.Null ? null : crops.EnumerateObject().ToDictionary(p => p.Name, p => OptI(p.Value)),
            CrateFloors = OptI(pm.GetProperty("crate_floors")),
            Liquids = pm.GetProperty("liquids").EnumerateArray().Select(l => (l[0].GetInt32(), l[1].GetString())).ToList(),
            Labels = Ints(pm.GetProperty("labels")),
            Places = Ints(pm.GetProperty("places")),
            Panels = Ints(pm.GetProperty("panels")),
            Bands = Ints(pm.GetProperty("bands")),
            Bindings = Ints(pm.GetProperty("bindings")),
            ItemFamily = pm.GetProperty("item_family").EnumerateObject().ToDictionary(p => p.Name, p => p.Value.GetString(), StringComparer.Ordinal),
            FamilyOrder = Strs(pm.GetProperty("family_order")),
            VesselFamilies = Strs(pm.GetProperty("vessel_families")),
            PriorSplit = Splits(pm.GetProperty("prior_split")),
        };
        return new UnitPlan.Inputs
        {
            Width = pm.GetProperty("width").GetInt32(),
            Height = pm.GetProperty("height").GetInt32(),
            MaxTrisPerStack = pm.GetProperty("max_tris_per_stack").GetInt32(),
            Rows = pm.GetProperty("rows").EnumerateArray().Select(r => new UnitPlan.Row
            {
                Kind = r.GetProperty("kind").GetString(), Drop = r.GetProperty("drop").GetString(), Stack = r.GetProperty("stack").GetInt32(),
                Max = r.GetProperty("max").GetInt32(), X = r.GetProperty("x").GetInt32(), Y = r.GetProperty("y").GetInt32(),
            }).ToList(),
            Model = m,
            Looks = pm.GetProperty("looks").EnumerateObject().ToDictionary(p => p.Name, p => OptI(p.Value), StringComparer.Ordinal),
            Parts = pm.GetProperty("parts_tris").EnumerateObject().ToDictionary(p => p.Name, p => OptI(p.Value), StringComparer.Ordinal),
            Ammos = pm.GetProperty("ammo").EnumerateObject().ToDictionary(p => p.Name, p => p.Value.GetString(), StringComparer.Ordinal),
            Extents = pm.GetProperty("extents").EnumerateObject().ToDictionary(p => p.Name, p => p.Value.EnumerateObject()
                .ToDictionary(e => e.Name, e => e.Value.ValueKind == JsonValueKind.Null ? (float?)null : F(e.Value), StringComparer.Ordinal), StringComparer.Ordinal),
        };
    }
}
