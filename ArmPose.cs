// The armory mannequins' carved arms in the vanilla Armor Stand pose (Joost, 27 Oct: every mannequin in the vanilla pose, "just
// relocating the arms"; the models session's code route). The pose is Joost's own capture of the vanilla ArmorStand_Male in
// Pose_Upright (storehouse_posecapture, 27 Oct 20:03, shipped as assets/armorstand_pose.json); the worn sets are baked on a rig posed
// from the same file (MannequinBaker), so a fist ends where the weapon is held.
// No UnityEngine here: StoreModel.SplitArms calls Repose on the frame's arm triangles at model load, and armrun/ compiles this same
// file outside the game against the shipped Frame.obj and anchors (arm-gate.py checks it against an independent reference).
// Per arm, in piece space: the upper arm turns about its carved shoulder until its elbow meets the rig's elbow; the forearm, wrist and
// fist turn about that elbow until the fist's centre meets the rig's grip (Hand_Attach). Some fists are carved folded back (the right
// hand of most calm poses holds the sword up, its fist beside the forearm): such an arm takes its figure's other forearm and fist,
// mirrored, when that one is carved straight; when neither is, the fist alone slides onto the grip. Lengths are never changed.
using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Text;
using System.Text.RegularExpressions;

namespace Finn.Storehouse;

struct D3
{
    public double x, y, z;
    public D3(double x, double y, double z) { this.x = x; this.y = y; this.z = z; }
    public static D3 operator +(D3 a, D3 b) => new(a.x + b.x, a.y + b.y, a.z + b.z);
    public static D3 operator -(D3 a, D3 b) => new(a.x - b.x, a.y - b.y, a.z - b.z);
    public static D3 operator *(D3 a, double d) => new(a.x * d, a.y * d, a.z * d);
    public static double Dot(D3 a, D3 b) => a.x * b.x + a.y * b.y + a.z * b.z;
    public static D3 Cross(D3 a, D3 b) => new(a.y * b.z - a.z * b.y, a.z * b.x - a.x * b.z, a.x * b.y - a.y * b.x);
    public double Length => Math.Sqrt(Dot(this, this));
    public D3 Unit => this * (1.0 / Length);
}

// A 3x3 rotation, row-major.
struct Rot
{
    public double a, b, c, d, e, f, g, h, i;
    public static Rot Identity => new() { a = 1, e = 1, i = 1 };
    public D3 Apply(D3 v) => new(a * v.x + b * v.y + c * v.z, d * v.x + e * v.y + f * v.z, g * v.x + h * v.y + i * v.z);
    // The shortest turn taking direction u onto direction w (Rodrigues: I + K + K^2 / (1 + cos)).
    public static Rot FromTo(D3 u, D3 w)
    {
        u = u.Unit; w = w.Unit;
        var v = D3.Cross(u, w);
        double cos = D3.Dot(u, w);
        if (cos < -0.999999) return Identity;   // opposite: no arm turns that far (said by the caller's numbers)
        double k = 1.0 / (1.0 + cos);
        return new Rot
        {
            a = 1 - k * (v.y * v.y + v.z * v.z), b = -v.z + k * v.x * v.y, c = v.y + k * v.x * v.z,
            d = v.z + k * v.x * v.y, e = 1 - k * (v.x * v.x + v.z * v.z), f = -v.x + k * v.y * v.z,
            g = -v.y + k * v.x * v.z, h = v.x + k * v.y * v.z, i = 1 - k * (v.x * v.x + v.y * v.y),
        };
    }
    public static Rot AboutY(double degrees)   // as UnityEngine's Quaternion.Euler(0, degrees, 0)
    {
        double t = degrees * Math.PI / 180.0, cs = Math.Cos(t), sn = Math.Sin(t);
        return new Rot { a = cs, c = sn, e = 1, g = -sn, i = cs };
    }
}

// The capture: every bone under the stand's Visual as Visual.worldToLocalMatrix * bone.localToWorldMatrix, row-major (schema
// storehouse-native-pose-capture/1, written by storehouse_posecapture).
sealed class VanillaPose
{
    public readonly Dictionary<string, float[]> Bones = new(StringComparer.Ordinal);   // path under Visual -> 16 values
    readonly Dictionary<string, string> byName = new(StringComparer.Ordinal);          // a bone's own name -> its first path
    public double Scale = 1.0;                                                          // Visual's local scale (the stand's 0.95)
    public string From;

    static readonly Regex bone = new(@"""path""\s*:\s*""([^""]*)""[^\[\]]*?""visualLocalMatrixRowMajor""\s*:\s*\[([^\]]*)\]");
    static readonly Regex scale = new(@"""visualLocalScale""\s*:\s*\[\s*([-0-9.eE+]+)");

    public static VanillaPose Parse(string text, string from)
    {
        if (text == null || !text.Contains("storehouse-native-pose-capture/1")) return null;
        var p = new VanillaPose { From = from };
        foreach (Match m in bone.Matches(text))
        {
            var values = m.Groups[2].Value.Split(',').Select(s => float.Parse(s.Trim(), CultureInfo.InvariantCulture)).ToArray();
            if (values.Length != 16) continue;
            string path = m.Groups[1].Value;
            p.Bones[path] = values;
            string name = path.Substring(path.LastIndexOf('/') + 1);
            if (!p.byName.ContainsKey(name)) p.byName[name] = path;
        }
        var s = scale.Match(text);
        if (s.Success) p.Scale = double.Parse(s.Groups[1].Value, CultureInfo.InvariantCulture);
        return p.Bones.Count > 0 ? p : null;
    }

    public bool Has(string name) => byName.ContainsKey(name);

    // A bone's place in the stand's "Player Pose" space: Visual sits at its origin, unturned, at Scale (MannequinBaker checks this on
    // the rig in game and says the largest difference).
    public D3 Point(string name)
    {
        var m = Bones[byName[name]];
        return new D3(m[3], m[7], m[11]) * Scale;
    }
}

sealed class ArmPart
{
    public string Name, Side;   // Side: "Left" or "Right", the figure's own
    public int Kind;            // 0 upper arm, 1 forearm and wrist, 2 fist
    public D3[] P, N;           // triangle corners, three per triangle, in piece space
}

sealed class ArmOut
{
    public ArmPart From;        // whose triangles (and texture coordinates) these are
    public D3[] P, N;
    public bool Flip;           // mirrored: each triangle's corners go in reverse order
}

static class ArmPose
{
    public const double Tol = 0.03;   // a fist within 3 cm of its grip stays on its own forearm
    static readonly Regex upper = new(@"_(Left|Right)_(upper|sleeve)(\.\d+)?$");
    static readonly Regex lower = new(@"_(Left|Right)_(forearm|wrist_core|wrist_tenon)(\.\d+)?$");

    // -1: not an arm part. The fists ("hand_objects") by left/right in their names.
    public static int KindOf(string name, bool fist, out string side)
    {
        side = null;
        if (fist)
        {
            string n = name.ToLowerInvariant();
            side = n.Contains("left") ? "Left" : n.Contains("right") ? "Right" : null;
            return side != null ? 2 : -1;
        }
        var m = upper.Match(name);
        if (m.Success) { side = m.Groups[1].Value; return 0; }
        m = lower.Match(name);
        if (m.Success) { side = m.Groups[1].Value; return 1; }
        return -1;
    }

    // The figure's turn about y (degrees), as StoreContents.Rebuild turns a worn set onto it: the rig's forward (+z) onto the side the
    // figure faces, plus the anchor's own few degrees.
    public static double Turn(int facing, double yaw)
    {
        double toSide = Math.Atan2(0.0, facing) * 180.0 / Math.PI;
        double near = Math.Round(yaw / 180.0) * 180.0;
        double delta = (yaw - near) - Math.Floor((yaw - near) / 360.0) * 360.0;
        if (delta > 180.0) delta -= 360.0;
        return toSide + delta;
    }

    static D3 Centre(IEnumerable<D3> corners)
    {
        var seen = new HashSet<(double, double, double)>();
        D3 sum = default;
        int n = 0;
        foreach (var c in corners)
            if (seen.Add((c.x, c.y, c.z))) { sum += c; n++; }
        return n > 0 ? sum * (1.0 / n) : sum;
    }

    // The main axis of a set of points (power iteration on their covariance), and their centre.
    static (D3 centre, D3 axis, List<D3> points) Axis(IEnumerable<D3> corners)
    {
        var seen = new HashSet<(double, double, double)>();
        var pts = new List<D3>();
        foreach (var c in corners) if (seen.Add((c.x, c.y, c.z))) pts.Add(c);
        var mid = Centre(pts);
        double xx = 0, xy = 0, xz = 0, yy = 0, yz = 0, zz = 0;
        foreach (var p in pts)
        {
            var d = p - mid;
            xx += d.x * d.x; xy += d.x * d.y; xz += d.x * d.z; yy += d.y * d.y; yz += d.y * d.z; zz += d.z * d.z;
        }
        var rows = new[] { new D3(xx, xy, xz), new D3(xy, yy, yz), new D3(xz, yz, zz) };
        var v = rows.OrderByDescending(r => r.Length).First();
        for (int k = 0; k < 100 && v.Length > 1e-12; k++) v = new D3(D3.Dot(rows[0], v), D3.Dot(rows[1], v), D3.Dot(rows[2], v)).Unit;
        return (mid, v.Length > 1e-12 ? v.Unit : new D3(0, -1, 0), pts);
    }

    sealed class Side
    {
        public List<ArmPart> Upper = new(), Lower = new(), Fist = new();
        public D3 S, E, F, Grip, Elbow;
        public double Miss;   // how far the carved elbow-to-fist differs from the rig's elbow-to-grip
        public double Shoulder = double.NaN;   // the carved shoulder from the rig's (an older figure, r1, is not this rig's: over 5 cm)
        public double Reach;                   // the carved upper arm's length against the rig's
        public bool Whole => Upper.Count > 0 && Lower.Count > 0 && Fist.Count > 0;
        public bool Fits => Whole && Shoulder <= 0.05 && Reach <= 0.05;
    }

    // One figure's arm parts in the vanilla pose. pos: the figure's feet in piece space; facing and yaw as the form has them.
    public static List<ArmOut> Repose(List<ArmPart> parts, D3 pos, int facing, double yaw, VanillaPose pose, out string report)
    {
        var turn = Rot.AboutY(Turn(facing, yaw));
        D3 At(string bone) => pos + turn.Apply(pose.Point(bone));
        var sides = new Dictionary<string, Side>(StringComparer.Ordinal);
        foreach (var name in new[] { "Left", "Right" })
        {
            var s = sides[name] = new Side();
            foreach (var p in parts.Where(p => p.Side == name)) (p.Kind == 0 ? s.Upper : p.Kind == 1 ? s.Lower : s.Fist).Add(p);
            if (!s.Whole || !pose.Has(name + "Arm") || !pose.Has(name + "ForeArm") || !pose.Has(name + "Hand_Attach")) continue;
            var (mid, axis, pts) = Axis(s.Upper.SelectMany(p => p.P));
            if (D3.Dot(axis, Centre(s.Lower.SelectMany(p => p.P)) - mid) < 0) axis = axis * -1.0;
            double lo = pts.Min(p => D3.Dot(p - mid, axis)), hi = pts.Max(p => D3.Dot(p - mid, axis));
            s.S = mid + axis * lo;
            s.E = mid + axis * hi;
            s.F = Centre(s.Fist.SelectMany(p => p.P));
            s.Grip = At(name + "Hand_Attach");
            s.Elbow = At(name + "ForeArm");
            s.Miss = Math.Abs((s.F - s.E).Length - (s.Grip - s.Elbow).Length);
            s.Shoulder = (s.S - At(name + "Arm")).Length;
            s.Reach = Math.Abs((s.E - s.S).Length - (s.Elbow - s.S).Length);
        }
        var outs = new List<ArmOut>();
        var said = new List<string>();
        bool both = sides.Values.All(x => x.Fits);
        var l = sides["Left"]; var r = sides["Right"];
        var plane = both ? new D3(r.S.x - l.S.x, 0, r.S.z - l.S.z) : default;
        if (both) plane = plane.Unit;
        var middle = (l.S + r.S) * 0.5;
        D3 Reflect(D3 v, D3 at) => v - plane * (2.0 * D3.Dot(v - at, plane));
        foreach (var (name, otherName) in new[] { ("Left", "Right"), ("Right", "Left") })
        {
            var s = sides[name];
            var o = sides[otherName];
            if (!both)
            {
                foreach (var p in s.Upper.Concat(s.Lower).Concat(s.Fist)) outs.Add(new ArmOut { From = p, P = p.P, N = p.N });
                said.Add(name.ToLowerInvariant() + " as carved (" + (!s.Whole ? "no upper arm, forearm and fist" : double.IsNaN(s.Shoulder) ? "no arm bones in the pose"
                    : s.Fits ? "the other arm is not this rig's" : string.Format(CultureInfo.InvariantCulture, "its shoulder {0:F1} cm from the rig's, upper arm {1:F1} cm longer or shorter: not this rig's figure", s.Shoulder * 100, s.Reach * 100)) + ")");
                continue;
            }
            // (source part, corner positions and normals before the turn, mirrored)
            var lowerParts = s.Lower.Select(p => (p, p.P, p.N, false)).ToList();
            var fistParts = s.Fist.Select(p => (p, p.P, p.N, false)).ToList();
            var fist = s.F;
            string how = "own";
            if (both && s.Miss > Tol && o.Miss <= Tol)
            {
                var shift = s.E - Reflect(o.E, middle);
                (ArmPart, D3[], D3[], bool) Mirror(ArmPart p) => (p, p.P.Select(c => Reflect(c, middle) + shift).ToArray(), p.N.Select(n => Reflect(n, default)).ToArray(), true);
                lowerParts = o.Lower.Select(Mirror).ToList();
                fistParts = o.Fist.Select(Mirror).ToList();
                fist = Reflect(o.F, middle) + shift;
                how = "mirrored from the " + otherName.ToLowerInvariant();
            }
            var r1 = Rot.FromTo(s.E - s.S, s.Elbow - s.S);
            var e2 = s.S + r1.Apply(s.E - s.S);
            D3 One(D3 v) => s.S + r1.Apply(v - s.S);
            var r2 = Rot.FromTo(One(fist) - e2, s.Grip - e2);
            D3 Two(D3 v) => e2 + r2.Apply(One(v) - e2);
            var f2 = Two(fist);
            var slide = s.Grip - f2;
            bool slid = slide.Length > Tol;
            if (slid) how += string.Format(CultureInfo.InvariantCulture, ", fist slid {0:F1} cm", slide.Length * 100);
            foreach (var p in s.Upper) outs.Add(new ArmOut { From = p, P = p.P.Select(One).ToArray(), N = p.N.Select(r1.Apply).ToArray() });
            foreach (var (p, pp, nn, flip) in lowerParts)
                outs.Add(new ArmOut { From = p, P = pp.Select(Two).ToArray(), N = nn.Select(n => r2.Apply(r1.Apply(n))).ToArray(), Flip = flip });
            foreach (var (p, pp, nn, flip) in fistParts)
                outs.Add(new ArmOut { From = p, P = pp.Select(v => slid ? Two(v) + slide : Two(v)).ToArray(), N = nn.Select(n => r2.Apply(r1.Apply(n))).ToArray(), Flip = flip });
            said.Add(string.Format(CultureInfo.InvariantCulture, "{0} {1}: elbow {2:F1} cm from the rig's, fist {3:F1} cm from the grip",
                name.ToLowerInvariant(), how, (e2 - s.Elbow).Length * 100, ((slid ? f2 + slide : f2) - s.Grip).Length * 100));
        }
        report = string.Join("; ", said);
        return outs;
    }
}
