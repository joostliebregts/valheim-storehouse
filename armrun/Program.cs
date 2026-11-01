// armrun <assets> <pose.json> <round>...: per round, the frame read as ObjMesh.Load reads it (x flipped, fans with the winding
// reversed), the figures as ParseForms and OrderForms read them, each figure's arm parts cut as SplitArms cuts them and posed by
// ArmPose.Repose; written as JSON to stdout: per figure its facing, report and every posed corner per part.
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace Finn.Storehouse;

static class Program
{
    static readonly Regex armPart = new(@"_(Left|Right)_(upper|forearm|wrist_core|sleeve|wrist_tenon)(\.\d+)?$");
    static string F(double v) => v.ToString("R", CultureInfo.InvariantCulture);

    static int Main(string[] args)
    {
        if (args.Length < 3) { Console.Error.WriteLine("armrun <assets> <pose.json> <round>..."); return 2; }
        var pose = VanillaPose.Parse(File.ReadAllText(args[1]), Path.GetFileName(args[1]));
        if (pose == null) { Console.Error.WriteLine("no pose in " + args[1]); return 2; }
        var sb = new StringBuilder("{");
        for (int a = 2; a < args.Length; a++)
        {
            string dir = Path.Combine(args[0], args[a]);
            string obj = Path.Combine(dir, "Frame.obj");
            string anchors = Directory.GetFiles(dir, "*anchors*.json").Single();
            var (pos, ends, names) = Load(obj);
            var doc = JsonDocument.Parse(File.ReadAllText(anchors)).RootElement;
            var forms = new List<(float[] p, float yaw, List<string> arms, int index, int front)>();
            foreach (var m in doc.GetProperty("mannequins").EnumerateArray())
            {
                var p = m.GetProperty("position").EnumerateArray().Select(x => x.GetSingle()).ToArray();
                float yaw = m.TryGetProperty("yaw", out var y) ? y.GetSingle() : 0f;
                var arms = (m.TryGetProperty("hand_objects", out var ho) ? ho.EnumerateArray().Select(x => x.GetString()) : Enumerable.Empty<string>())
                    .Concat(m.TryGetProperty("form_objects", out var fo) ? fo.EnumerateArray().Select(x => x.GetString()).Where(x => armPart.IsMatch(x)) : Enumerable.Empty<string>())
                    .Distinct().ToList();
                string axis = m.TryGetProperty("front_axis", out var fa) && fa.ValueKind == JsonValueKind.String ? fa.GetString() : "";
                int front = axis.Contains("Unity") && axis.Contains("-Z") ? (MathF.Cos(yaw * (MathF.PI / 180f)) > 0f ? -1 : 1) : 0;
                forms.Add((p, yaw, arms, forms.Count, front));
            }
            float zMin = forms.Min(f => f.p[2]), zMax = forms.Max(f => f.p[2]), mid = (zMin + zMax) / 2f;
            bool twoSides = zMax - zMin > 0.05f;
            int row = twoSides || forms.All(f => f.front != 0) ? 0 : OpenSide(obj, mid);
            sb.Append(a > 2 ? ",\n" : "\n").Append($"\"{args[a]}\": [");
            for (int f = 0; f < forms.Count; f++)
            {
                var form = forms[f];
                int facing = form.front != 0 ? form.front : twoSides ? (form.p[2] > mid ? 1 : -1) : row;
                var parts = new List<ArmPart>();
                foreach (var name in form.arms)
                {
                    int k = names.IndexOf(name);
                    if (k < 0) continue;
                    int from = k > 0 ? ends[k - 1] : 0;
                    var part = new ArmPart { Name = name, P = pos.Skip(from).Take(ends[k] - from).ToArray() };
                    part.N = part.P.Select(_ => new D3(0, 1, 0)).ToArray();
                    part.Kind = ArmPose.KindOf(name, !armPart.IsMatch(name), out part.Side);
                    parts.Add(part);
                }
                string report = "no arm parts";
                var outs = new List<ArmOut>();
                if (parts.Count > 0 && parts.All(p => p.Kind >= 0)) outs = ArmPose.Repose(parts, new D3(form.p[0], form.p[1], form.p[2]), facing, form.yaw, pose, out report);
                sb.Append(f > 0 ? "," : "").Append($"\n {{\"figure\": {form.index}, \"facing\": {facing}, \"report\": {JsonSerializer.Serialize(report)}, \"parts\": {{");
                for (int o = 0; o < outs.Count; o++)
                {
                    var x = outs[o];
                    sb.Append(o > 0 ? ", " : "").Append(JsonSerializer.Serialize(x.From.Name + (x.Flip ? "~mirror" : ""))).Append(": [");
                    sb.Append(string.Join(", ", x.P.Select(c => $"[{F(c.x)}, {F(c.y)}, {F(c.z)}]"))).Append(']');
                }
                sb.Append("}}");
            }
            sb.Append(']');
        }
        sb.Append("\n}\n");
        Console.Out.Write(sb.ToString());
        return 0;
    }

    // Corner positions in triangle order and the object ends, as ObjMesh.Load(flipX: true) gives them (floats, then widened).
    static (List<D3>, List<int>, List<string>) Load(string path)
    {
        var v = new List<float[]>();
        var corners = new List<D3>();
        var ends = new List<int>();
        var names = new List<string>();
        string current = null;
        foreach (var raw in File.ReadLines(path))
        {
            var line = raw.Trim();
            if (line.Length < 2 || line[0] == '#') continue;
            var p = line.Split((char[])null, StringSplitOptions.RemoveEmptyEntries);
            switch (p[0])
            {
                case "o":
                    if (corners.Count > 0 && (ends.Count == 0 || ends[ends.Count - 1] != corners.Count)) { ends.Add(corners.Count); names.Add(current); }
                    current = line.Substring(1).Trim();
                    break;
                case "v":
                    v.Add(new[] { -float.Parse(p[1], CultureInfo.InvariantCulture), float.Parse(p[2], CultureInfo.InvariantCulture), float.Parse(p[3], CultureInfo.InvariantCulture) });
                    break;
                case "f":
                    var c = p.Skip(1).Select(s => { int i = int.Parse(s.Split('/')[0], CultureInfo.InvariantCulture); return i < 0 ? v.Count + i : i - 1; }).ToList();
                    for (int i = 1; i + 1 < c.Count; i++)
                        foreach (int k in new[] { c[0], c[i + 1], c[i] }) corners.Add(new D3(v[k][0], v[k][1], v[k][2]));
                    break;
            }
        }
        if (ends.Count == 0 || ends[ends.Count - 1] != corners.Count) { ends.Add(corners.Count); names.Add(current); }
        return (corners, ends, names);
    }

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
}
