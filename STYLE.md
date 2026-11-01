# Storehouse style guide

Every store is one family. Joost, 23 Oct 2026: "You are responsible for ensuring they all look similar style wise."
The reference pieces are the ones he likes: bunker_r4, orebin (frame r4), metalpallet_r3, crib.

- **Atlas:** 128 px, point-filtered, about 48 px per metre on timber faces, on a copy of the wood chest's Custom/Piece
  material. Reuse the timber grain, end grain, dark iron and rivet tiles from bunker_r4 / metalpallet_r3; no new wood
  colour. New materials (clay, wicker, leather, birch bark, glass) follow the same palette logic: muted, slightly
  desaturated, light worn edges, darker crevices, never flat colour.
- **Timber:** chunky, hand-hewn, bevelled edges. Posts 0.12-0.16 m, beams 0.10-0.14 m, planks 0.04-0.06 m. No sticks.
- **Iron:** dark bands and brackets with rivet heads where timber meets timber; the bunker's and pallet's tile.
- **Heights:** tall pieces up to 2.0-2.1 m (mead rack, larder), low pieces 0.8-1.2 m, two stacked outdoor pieces 2.4 m.
- **Contents:** the items' own models. Mass stores visibly fill up (heaps physics-settled, 0 clipping); display stores
  show one per stack. One kind per group (crate, bay, vessel); full must look full.
- **Gravity and no patterns** (Joost, 25 Oct): every copy rests the way gravity would leave it (floor, wall, or an earlier copy
  it can lean on); heaps come from a rigid-body settle, never placed in rows; every bay/region its own random seed so no two
  heaps repeat; vary yaw and tilt; humans spot symmetry at a glance. Where the loader places copies itself (labels,
  equipment, shelf items) it adds a small deterministic yaw per place, never enough to leave the support.
- **Budget:** frames about 3-10k triangles; a full store stays under about 250k with its contents.
- **Check:** every new piece gets one render beside bunker_r4 at the same scale before it is wired in.
- **Compare rounds** (Joost, 24 Oct): every new round also gets a render beside its last few rounds at the same scale, all full.
- **No z-fighting:** no two same-facing faces in one plane that overlap (report_coplanar in blender/fletcher_r2.py); 0 before a round is
  committed, fixed by geometry (inset or offset a few mm), never by material tricks.

---
- 2026-10-25: gravity and no patterns (Joost).
- 2026-10-23: written for the four new stores (Apothecary Rack, Cooper's Row, Fletcher's Barrels, Hide Rack).
