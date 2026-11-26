# 0234 — The night lake: the water's per-frame constants in clean and patched frames

**Question.** Exp 0233 (F292) found that the lake's clean/patched state is set per frame. In N3
the lake went patched, clean for 20 s, then patched again, with a byte-identical texture table.
Exp 0212 dumped two more ranges before each shot: 0x11e04c0000 + 0x20000, described as "the per-draw
pointers of the pixel stage", and 0x11e0c2b000 + 0x2000. Exp 0233's hashes showed both rewritten
almost every second. Do they differ between N3's clean shots (ts02–05) and its patched shots?

**Setup.**
- Analysis only, on the dumps and journals that exps 0232/0233 left on the box. BC-250 dev box,
  2026-10-23 13:57–14:02, granted by the top session. One lock, `nice`/`ionice`, no emulator.
- `ptr0234.py` and `ptr0234b.py` read N3's draw journal. They list which user-data dwords of the
  water's draws (PS 0x11d01ff900 and the full-screen 0x11d01d7100) point into the two ranges, and
  each journalled draw's constant pointer.
- `cmp0234.py dumps <run> <bench.txt>` takes the water's constant slots (below) from every dump of
  a run. It classes the shots by the bench's patch share: clean under 5 %, patched at 8 % or more,
  the rest left out. Per draw, stage and dword it counts:
  - constant;
  - separating: no value shared between the classes, one class with a single value or both with
    at most two;
  - varying.

  `MINSIM=50` keeps only the samples in which at least half the dwords equal the most common value
  at that place, i.e. the samples that hold the water's constants (see Result). Separating values
  stay on the box; the repo copies give their counts.
- `cmp0234.py journal` lists, per journalled water draw, the render target and the vertex stage's
  slot-4 image (both at the dynamic render resolution), on the wall clock. Times are the journal's
  `t` mapped through the file's mtime, so ±1 s.
- Runs: N3 (patched, clean, patched), plus G3 (switching), N2 (one clean shot) and G2 (clean after
  its first shot) as checks.

**Result** (`raw/N3.pointers-*.txt`, `raw/*.dumps.txt` with all samples, `raw/*.dumps50.txt` with
`MINSIM=50`, `raw/N3.journal.txt`).
- **The two ranges are not fixed buffers. They are slots in the title's per-frame constant pool.**
  - The water's four draws take their constants through user-data dwords 28–29 of both stages.
  - That pointer moves every frame through a pool of 128-KiB blocks. N3's 28 journalled frames
    used 27 different blocks, between 0x11e02c0000 and 0x11e0d8ffff.
  - The in-block offsets never change. Draw k (k = 0–3) has 0x280 bytes of pixel-stage constants
    at 0xc554 − k·0x308 and 0x88 bytes of vertex-stage constants 0x280 above that. The four draws
    span 0xbc3c–0xc85c.
  - Exp 0212's two ranges are block 0x11e04c0000 and the 0xb000–0xcfff part of block 0x11e0c20000.
    Both contain that slot. In N3's journal, each points to the water's constants in one frame.
  - A dump therefore holds whatever the last frame to take that block wrote there.
- **Only some dumps hold the water's constants at the slot.** Per sample, 3–93 % of the dwords
  match the most common value. With `MINSIM=50`:
  - N3: 17 of 52 samples kept (2 clean, 15 patched);
  - G3: 9 of 26 (3 clean, 6 patched);
  - N2: 13 of 52 (1 clean, 12 patched);
  - G2: 9 of 26 (8 clean, 1 patched).
- **Among those, no dword separates clean from patched.**
  - N3: 443 dwords constant, 333 varying, none separating.
  - G3: 680 constant, 96 varying, none separating.
  - N2 and G2 show 30 and 11 "separating" dwords. In each, one class has a single sample, and the
    other has a different value in nearly every sample (12 values in 12 samples, 7 in 8). Those
    are per-frame values, not a state.
- The pixel stage's dwords 36–95 hold small integers (822–953) next to a few other words. These
  are in the range of the texture table's record numbers, so they are probably the water's
  bindless texture indices (TODO(verify)). They are identical in N3's clean ts03 sample and its
  patched ts10 and ts11 samples. They were decoded on the box; the values were not copied.
- **Dynamic resolution.** N3's journal has one water frame every 15 s.
  - The one inside the clean stretch (13:17:43; clean from 13:17:39 to 13:17:54) drew to a
    3328×1872 target. The patched frames at 13:17:58 and 13:18:13 had the same size.
  - At 13:17:28 (patched) the target was 2560×1440. Over the run the size moves between
    3072×1728 and 3328×1872.
- Box: one lock, 13:57–14:02, no emulator. About 116 KiB written (`~/bc5-work/exp0234`),
  `/var/home` at 69 %.

**Verdict.**
- **The byte compare points at no buffer or region.** In the dumps that hold the water draws'
  per-frame constants, those constants don't differ between clean and patched frames. Neither do
  the indices in them that probably pick the water's textures. Exp 0233 showed the same for the
  texture table, which is byte-identical.
- **Method correction for exps 0212/0233.** The two extra dump ranges are slots of the title's
  per-frame constant pool. Their hashes only show the pool's reuse. A dump of the water's
  constants must follow the journal's pointer for the frame.
- **One dynamic-resolution sample** inside N3's clean stretch had the same render size as the
  patched frames around it. The resolution doesn't look like the switch, but that is one sample.
- **Inputs not yet compared between clean and patched frames:**
  - the contents of the water's textures: the pixel stage's 2048² BC4 texture (it moves per run),
    the 512² float texture and the 4×4 at 0x11d0078000;
  - the vertex stage's slot-4 image at 0x113cb40000, which the GPU writes every frame at the
    render resolution.

  The other two vertex-stage images are all zero in clean and patched runs alike (exp 0205).
- **Next step (needs emulator runs, so a BOX REQUEST):** in a run that switches, dump those
  images before each shot, the way exp 0205 read the vertex stage's other two. The slot-4 image is
  at most 3328×1872 × 2 bytes, about 12 MB. Then compare summary statistics between the clean and
  patched shots on the box.
