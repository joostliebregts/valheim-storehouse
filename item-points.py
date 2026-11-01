# Writes assets/item_points.bin: the real shape, as points, of every item whose mesh the game keeps on the GPU only (a script cannot
# read its vertices, so the game measures it by the box around each part's turned box). Input: the models session's point sets,
# taken from the game's own bundle and the mods' (work/storehouse-0.5/item-points-20261027/item-points-20261027.json, schema
# storehouse-item-points/1, 27 Oct 2026): per prefab at most 600 points in ItemVisual's turned item space, root scale not applied,
# and the game's box (box_turned) to check the mesh is still the one measured. Only items with an unreadable part; the others are
# measured in game from their own vertices.
# Format (little-endian): "SHPT1", int32 count; per item: byte name length, UTF-8 name, 6 float32 (box min, box max), uint16 n,
# n x 3 int16 (millimetres).
#   python item-points.py <item-points.json>
import hashlib
import json
import struct
import sys

src = sys.argv[1]
raw = open(src, "rb").read()
table = json.loads(raw)
rows = sorted((name, r) for name, r in table["items"].items() if not r["all_readable"])
out = bytearray(b"SHPT1" + struct.pack("<i", len(rows)))
for name, r in rows:
    b = name.encode("utf-8")
    out += struct.pack("<B", len(b)) + b
    out += struct.pack("<6f", *r["box_turned"]["min"], *r["box_turned"]["max"])
    pts = r["points"]
    out += struct.pack("<H", len(pts))
    for p in pts:
        out += struct.pack("<3h", *(int(round(x * 1000)) for x in p))
open("assets/item_points.bin", "wb").write(out)
print(f"assets/item_points.bin: {len(rows)} item(s) of {len(table["items"])}, {len(out) / 1024:.0f} kB, from {src.replace(chr(92), '/').split('/')[-1]} (sha256 {hashlib.sha256(raw).hexdigest()[:12]})")
