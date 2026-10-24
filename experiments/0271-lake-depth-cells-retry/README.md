# 0271 — The night lake: the depth in the patch cells, clean against patched reads of one run (retry of 0266)

**Question.** As exp 0266 (F331): within one run that shows both states, at one frame size, what
depth do the patch cells hold in clean reads and in patched reads, against the lake around them?
Exp 0266 got no answer: its first run stopped on a GPU write fault during load, its second stayed
clean. Within a run every lake draw compared so far is issued identically in both states (F313,
F320, F323), so this compares what those draws leave in memory.

**Setup.**
- Granted by the top session after exp 0266: the same run, up to 3 tries, stopping at the first run
  that shows both states or at any fault, with the last run ending by 18:40.
  - GO at 18:10, after the box's power-cycle (18:05, boot 831e5915) and the saves' restore.
  - W271a 18:11–18:17, W271b 18:18–18:24; analysis until 18:27. `/var/home` at 71–72 %.
- **Binary:** exp 0251's private `kyty_emulator` (`~/bc5-work/exp0251`, built 2026-10-23 22:06), through
  the bench's own launcher copy, as in exps 0251–0266; not the shared builds.
- **Scripts:** exp 0266's, renamed: `ab0271.sh` / `bench0271.sh` (the full-screen draw journalled with
  `_EVERY=10`), `capl0271.sh` (every 7 s, at most 20 times, the whole depth memory 0x1129ec0000 +
  0x2940000 and the G-buffer 0x113f230000 + 0x1860000 through `/proc/<pid>/mem`, into
  `~/bc5-data/priv/exp0271`, summarised then deleted) and `ana0271.py` (size and completeness of each
  read, the cell mask from the run's patched shots, cells against the rest of the lake window by
  size and state). `ab0271.sh` also lists the newest saved GPU coredumps
  (`~/bc5-data/captures/devcoredump/`) if a run stops on a fault.
- Baseline from exp 0266's clean run W266b (`0266-…/raw/W266b.ana.txt`): in its 13 complete reads the
  lake window had no G-buffer cleared pixels and no depth 0, depth median about 0.00074.
- **`coin0271.py`** was added after the first summary. Per pixel of the lake window in a read, it
  tests whether the depth buffer's cleared value (0) and the G-buffer's cleared value (10,000) fall
  on the same pixels.

**Result** (`raw/`).
- **Box state.** No kernel fault, timeout or reset in either run: the amdgpu dmesg count stayed at
  123, the `.out` files have 0 fault lines, and the stream (`raw/W271ab.kern.txt`) has only routine
  lines. The live saves' checksum was the same before and after each run (2f5d956c8f1b6ebd). No
  coredump was made, and `~/bc5-data/captures/devcoredump/` did not exist yet. Each run took 20 reads
  (1.3 GB); all were deleted after the summaries.
- **The runs.**
  - W271a was patched in all 26 shots (21.5–31.3 %).
  - W271b was patched ts00–ts11 (12.5–25.6 %), moved through ts12–ts16 (1.5, 7.3, 14.5, 22.7,
    3.9 %), and was clean ts17–ts25 (1.2–1.6 %).
  - W271b showed both states, so there was no third run.
- **W271b, clean against patched** (`raw/W271b.ana.txt`, `raw/W271b.coin.txt`).
  - **Complete reads:** patched 4 at 3328×1872 and 1 at 3072×1728 (cap02, cap04–cap06) plus one at
    the edge of the transition (cap11). Clean: 3072 ×3 and 3328 ×1 (cap13, cap15, cap17, cap18).
  - **Clean reads:** the lake window has depth everywhere, with medians 0.00078 in the cell mask
    and 0.00081 outside it, and no cleared G-buffer. Three of them have no depth 0 at all; cap13
    has 5 % depth 0 that does not coincide with anything. cap17, complete by shear, caught the
    G-buffer just after its per-frame clear.
  - **Patched reads:** 25–32 % of the window holds a cleared G-buffer, and 97–99 % of those pixels
    hold depth 0 too (phi +0.84 to +0.97). The depth-0 share is 25–34 %. So in the hole pixels
    nothing wrote depth in that frame either: the depth stayed at its cleared value. How a
    cleared tile's 0 reaches memory is TODO(verify): perhaps through an expand, such as F305's late
    compression-disable passes.
  - **The cell mask is the other set of cells.** The mask from W271b's patched shots (23 % of the
    window) holds the cells with depth (0.00077); the holes lie outside it. The light cells on
    screen and the holes in a read were different cells here.
  - **The transition read** (cap11, between ts10 at 23.5 % and ts11 at 12.5 %) has only 6 %
    cleared and 6 % depth 0, not on the same pixels.
- **W271a, patched throughout** (`raw/W271a.ana.txt`, `raw/W271a.coin.txt`; 8 complete reads, all
  at 3328×1872).
  - 27–37 % of the window holds depth 0 in every read, and 31–66 % a cleared G-buffer. But only
    41–57 % of the cleared pixels hold depth 0 (phi +0.14 to +0.47).
  - Here the holes lie mostly inside the cell mask (depth 0 on 52 % and cleared on 56 % of its
    pixels, against 20 % and 25 % outside).
  - The depth memory and the G-buffer are read one after the other (41 MB, then 25 MB), so they
    can come from different frames. A hole pattern that changes from frame to frame would give
    partial overlap.

**Verdict.**
- **Within one run, the patch state is visible in the depth buffer itself.**
  - In clean frames the lake window holds written depth everywhere.
  - In patched frames a quarter to a third of it still holds the cleared depth value. In W271b,
    those are the same pixels where the G-buffer stays at its cleared value (97–99 %, phi up to
    +0.97).
- **The holes are therefore pixels where nothing drew in that frame:** no depth write and no
  G-buffer write.
- **This revises F305/F307's reading.**
  - The earlier reading was that a nearer depth left by an earlier draw makes the full-screen
    draw fail its GEQUAL test.
  - In complete reads the hole pixels hold no depth at all. Against the cleared value (0) a GEQUAL
    test passes any fragment at 0 or nearer. So the full-screen draw is not what leaves these holes
    empty, unless its fragments lie behind 0 or are rejected before the per-pixel test (for example
    by hierarchical Z), which these reads cannot see.
  - What normally covers these pixels with depth is another draw, or the same draws covering less.
- **The draws are not what changes.** Every lake draw compared within a run is issued identically
  in both states (F313, F320, F323). Identical draws that cover fewer pixels point at data they
  read on the GPU: for example a per-cell visibility or LOD buffer that collapses a cell's
  triangles, or vertex data written by compute work earlier in the frame.
- **The relation between screen cells and holes is not fixed.** The holes matched the light screen
  cells in W271a and the other cells in W271b, consistent with F297's mixed signs between dumps
  and shots.
- **Next:**
  - find which draw writes the lake surface's depth in clean frames in these pixels: the depth
    writers' coverage per cell. That means a read right after the depth-only writers, or the
    vertex-stage output of the GPU-driven writers;
  - and look for the compute pass that writes their per-cell input, comparing clean and patched
    frames.
