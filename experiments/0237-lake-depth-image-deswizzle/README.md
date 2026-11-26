# 0237 — The night lake: the water's slot-4 image, de-swizzled, against the screenshot

**Question.** Exp 0235 (F294) left one water input untested: the vertex stage's slot-4 image at
0x113cb40000, a depth-like 16_FLOAT target the GPU rewrites every frame. One dump of it was kept
(I3 ts00). Read in its tiled layout, does it show the patchwork of the screenshot taken right
after the dump?

**Setup.**
- Analysis only: BC-250 dev box, 2026-10-23 18:27–18:31, granted by the top session. One lock,
  `nice`, no emulator.
- Input: the kept dump `~/bc5-data/priv/exp0235/ts00.img.gs4.bin`, 12,779,520 bytes from
  0x113cb40000, with swizzle mode 27 (`ADDR_SW_64KB_R_X`). The shot taken right after it,
  `r-I3/shots/142555-ts00.png`, has a 24.3 % patch share.
- `gen0237.py` pulls the `ADDR_SW_64KB_R_X` 1xaa patterns for 2-byte elements, one per pipe count
  (1–64), out of Mesa's addrlib (`src/amd/addrlib/src/gfx10/gfx10SwizzlePattern.h` @ ab2374a, MIT,
  AMD) into `swz0237.json`.
  - The selection follows `Gfx10Lib::GetSwizzlePatternInfo` for a part without RB+ (gfx10.1):
    `GFX10_SW_64K_R_X_1xaa_PATINFO[pipesLog2 × 5 + elemLog2]` (`gfx10addrlib.cpp:939-941,
    4392-4670`).
  - Each address bit is an XOR of coordinate bits, so the in-block offset is fx(x) XOR fy(y).
- `deswz0237.py` computes address = (y / 128 × pitch + x / 256) × 64 KiB + (fx(x) ^ fy(y)), with a
  block of 256×128 elements and the pitch equal to the width aligned to 256 (`gfx10addrlib.cpp:
  4751-4845`). The pipe/bank XOR is 0: the base is 64-KiB aligned, and gfx10 T#s carry the tile
  swizzle in the base address. The chip's `GB_ADDR_CONFIG` is not read here, so the pipe count
  and the frame's render width are found from the data:
  - pipe counts 2^0–2^6 at four sizes, scored by roughness (mean |step| of log depth between
    neighbours);
  - widths 2304–3584 at 16 pipes, scored by block-row shear: the mean |step| across the 128-row
    block boundaries over the mean |step| between other rows. A wrong pitch shifts each block row
    against the one above.

  It then compares the image with the screenshot's patch mask: exp 0197's thresholds, its window
  x 300–1900, y 400–680, and the image resampled to 1920×1080. Three tests: the high-pass of log
  depth, the share of the far value (≥ 9000) in patch and other pixels, and the depth step across
  the mask's edges. Both vertical orientations are tested.
- `render0237.py` renders the image at a given pipe count and size.
- **The renders are the title's rendered data and stay in `~/bc5-data/priv/exp0237` (mode 700),
  with the kept dump. The repo has the summary (`raw/I3-ts00.deswz.txt`), the scripts and the
  extracted pattern table.**

**Result** (`raw/I3-ts00.deswz.txt`, `raw/I3-journal-targets.txt`).
- **16 pipes.** At every size, 2^4 pipes gave the smoothest image by a wide margin (at 3072×1728:
  0.094 against 0.160–0.210 for the other counts). So `GB_ADDR_CONFIG.NUM_PIPES` is 16 on this
  chip (inferred, TODO(verify) against the kernel's value).
- **The frame drew at 3072×1728.**
  - The block-row shear was 0.94 at 3072 against 13.1–18.0 at 2304–2816 and 3328–3584.
  - The journal's descriptor said 2816×1584, but that came from a draw 15 s earlier.
  - Roughness alone pointed at 3328×1872. That was wrong: the image there is a staircase, a 12-block
    pitch read at 13.
- **At 3072×1728 the image is a coherent picture of the screenshot's view**: the bushes at the
  lower left, the rock in front, the curve of the shore, the cliff at the upper left. Values run
  from 5 to 10,010, and the far value (~10,000) is at the top.
- **Over the lake the image has its own patchwork.** Rectangular cells at the far value lie next to
  cells at the water's depth, in the same perspective as the screenshot's cells.
- **Its cells line up with the screenshot's.**
  - The step of log depth across the patch mask's edges is 0.234, against 0.058 over the window
    (×4.0).
  - The far value covers 50.8 % of patch pixels against 23.5 % of the other pixels (phi +0.255).
  - Flipped vertically, the link goes away: ×1.06, phi +0.09.
  - Many of the screenshot's cell edges lie exactly on the image's cell edges. The agreement is
    partial: the dump and the screenshot are different frames, and I3's patch share moved
    18–27 % from shot to shot.
- **The water does not write it.** Both water draws render to colour target 0 at 0x113f230000 (I3's
  journal: 112 and 28 draws). The journal's host hint names 0x113cb40000 as `CB0`, the colour
  target of some draw outside the journal's water filter.

**Verdict.**
- **The patchwork is already in an input of the water draw.** The slot-4 image its vertex stage
  reads has cells at the far value, and their edges line up with the cells on screen.
- **Open:**
  - Cause or fellow symptom: does this target's pattern make the water's, or do both come from one
    earlier fault?
  - Which pass writes `CB0` 0x113cb40000, and in what order relative to the water's draws.
- **Method, for later dumps:** de-swizzle at 16 pipes, and take the width from the block-row shear
  rather than the journal.
- **Next:**
  1. Exp 0238: the same image in clean and patched frames. If the far cells go away in clean
     frames, the image tracks the visible state.
  2. The draw that writes `CB0` 0x113cb40000, from one frame of an unfiltered journal.
