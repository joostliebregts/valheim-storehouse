import os
import sys
# The first icon (25 Oct): a line drawing of the Strongbox, which the mod no longer has. The icon is now Joost's cut-out badge
# (27 Oct, package/icon.png from Videos/Storehouse/icon/out/storehouse-icon.png, master v8-badge-cream-master.png beside it); this
# script draws the old one only to a file that does not exist yet:  python make-icon.py <new file>  (needs Pillow)
from PIL import Image, ImageDraw

if len(sys.argv) < 2 or os.path.exists(sys.argv[1]):
    sys.exit("make-icon.py: name a file that does not exist yet (package/icon.png is Joost's badge; it is not redrawn here).")

# Same flat look as Aim Stamina, Portal Picker and Sound Muffler: charcoal ground, light grey strokes, one accent (iron amber).
S = 4
BG, LIGHT, AMBER, DIM = (30, 35, 32), (230, 233, 228), (232, 162, 58), (64, 72, 67)
im = Image.new("RGB", (256 * S, 256 * S), BG)
d = ImageDraw.Draw(im, "RGBA")
s = lambda *v: [x * S for x in v]

# Ground line
d.line(s(14, 214, 242, 214), fill=DIM, width=4 * S)

# The Strongbox, big, in the middle: body, lid, two iron bands
d.rectangle(s(70, 120, 186, 210), outline=LIGHT, width=7 * S)
d.polygon(s(66, 120, 190, 120, 178, 92, 78, 92), outline=LIGHT, width=7 * S)
for x in (96, 160):
    d.line(s(x, 94, x, 208), fill=AMBER, width=8 * S)
d.rectangle(s(118, 132, 138, 150), fill=AMBER)

# The Timber Crib, left: posts and stacked log ends
d.line(s(18, 150, 18, 210), fill=LIGHT, width=6 * S)
d.line(s(58, 150, 58, 210), fill=LIGHT, width=6 * S)
for cx, cy in ((28, 200), (48, 200), (38, 182), (28, 164), (48, 164)):
    d.ellipse(s(cx - 8, cy - 8, cx + 8, cy + 8), outline=LIGHT, width=4 * S)

# The Ore Bin, right: an open bin with lumps and an amber rim
d.line(s(198, 172, 238, 172), fill=AMBER, width=7 * S)
d.line(s(200, 172, 204, 210), fill=LIGHT, width=6 * S)
d.line(s(236, 172, 232, 210), fill=LIGHT, width=6 * S)
for box in ((206, 158, 220, 172), (218, 152, 234, 170)):
    d.ellipse(s(*box), fill=DIM, outline=LIGHT, width=3 * S)

im.resize((256, 256), Image.LANCZOS).save(sys.argv[1])
print("saved", sys.argv[1])
