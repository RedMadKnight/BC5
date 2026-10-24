# 0289 — The night lake writers' image pyramid: its 4KB_S layout, and the pyramid against the depth

**Question.** Exp 0287 (F350): in the frozen view, the lake depth writers' GPU-written indirect arguments change in
steps, always together with the depth memory, and in the same intervals as the 32_FLOAT image pyramid their vertex
stage reads (exp 0274). Both observed hole switches fell on such steps. The hypothesis (TODO(verify)): an occlusion
pass culls the lake's cells against a pyramid built from the depth, so the holes feed back into the next frame's
culling. Exp 0274 found the pyramid's descriptor has SW_MODE 5, ADDR_SW_4KB_S, so its per-texel comparison with a
linear layout was invalid. Decoded properly, is the pyramid a reduction of the depth image, and of the depth of the
same read or of an earlier one?

**Plan** (the top session, overnight 2026-10-24/25 on the maintainer's delegation: the offline de-swizzle first, then
the combined bursts on a BOX REQUEST, at most two bench runs).
- **The 4KB_S pattern, from Mesa's addrlib.**
  - Exps 0237/0248 cite addrlib at ab2374a, but no copy was left on the box (whose `~/src/mesa`, 0866ae7, is a sparse
    checkout of `src/amd/common`, `registers`, `vulkan` and `gallium/drivers/radeonsi`) or on the laptop.
  - With the user's approval (2026-10-25 ~00:05), `src/amd/addrlib/src/gfx10/gfx10SwizzlePattern.h` (504,619 bytes)
    and `gfx10addrlib.cpp` (204,134 bytes) were downloaded at ab2374a from gitlab.freedesktop.org/mesa/mesa (MIT,
    AMD) into a scratch folder. They are read as data only (`gen0289.py` parses the table entries, never evaluates
    them) and not committed.
  - Check: the downloaded header reproduces exp 0248's `swz0248-z4.json` (ADDR_SW_64KB_Z_X, 16 pipes, 4-byte
    elements, table index 4 × 5 + 2) exactly (`raw/check-z4.json`).
  - Selection: `Gfx10Lib::GetSwizzlePatternInfo` takes index elemLog2 for a non-XOR mode (`gfx10addrlib.cpp:4401`).
    For a 2D ADDR_SW_4KB_S image on a part without RB+ it takes `GFX10_SW_4K_S_PATINFO`
    (`gfx10addrlib.cpp:4542-4550`), so entry 2 for 4-byte elements: {1, 2, 3, 0, 0}, i.e. NIBBLE01[2] + NIBBLE2[3]
    (`gfx10SwizzlePattern.h:102-107`, 3725, 3769).
  - `gen0289.py` (exp 0248's gen0248.py, generalised to any table and index) writes it to `swz4k-addrlib.json`.
    Address bits 0–11 of a 4-KiB block: 0 0 X0 X1 Y0 Y1 Y2 X2 Y3 X3 Y4 X4, i.e. 32 × 32 elements.
  - The pattern guessed before the download (`cand/swz4k-dss.json`, X0 X1 Y0 Y1 X2 Y2 X3 Y3 X4 Y4) was wrong above
    bit 5.
  - `cand0289.py`'s five guesses are kept only as a cross-check of `fb0289.py`'s smoothness score, which should pick
    the addrlib pattern on real data. A wrong pattern scrambles every block.
    - Checked offline on synthetic reads swizzled with one candidate: that candidate scored smoothest (0.077 against
      0.096–0.195) and was the only one with r +1.000.
- **`fb0289.py`** decodes the pyramid's five single-level images. Mip 0 is 128 × 64 at 0x11d0886000, down to 8 × 4 at
  0x11d0892000 (exp 0274; widths and heights from the descriptors' words 1–2: word 1 bits 30–31 and word 2 bits
  0–11 the width − 1, word 2 bits 14–27 the height − 1). It sets mip 0 against the depth reads of the same burst, at
  the same read and at earlier and later ones, for two footprints:
  - the depth image stretched over 128 × 64;
  - 32 × 32 depth pixels per texel from the top left, as a 4096 × 2048 pyramid's level 5 would be.

  For each footprint it gives the Pearson r of mip 0 with the per-texel minimum and maximum depth and the share of
  depth-0 pixels.
- **The run(s):** `capa0289.py` (exp 0287's reader with the pyramid on) during the usual frozen-view lake bench
  (`ab0289.sh` / `bench0289.sh`, exp 0251's private binary, exp 0283's journal switches): 12 bursts of 8 × (arguments,
  pyramid, depth) 30 ms apart, then `rd0289.py`, `chg0289.py` (exp 0287's scripts, copied) and `fb0289.py` with
  `swz4k-addrlib.json` and the five guesses.
  - A second run only if the first gives no pyramid decode that matches the depth, or no hole switch.
  - Rules as before: our own lock line, the kernel stream, the run stopped at any new amdgpu line (no power-cycle is
    possible before 07:00), saves reference c0ee58b92c0cadc2, reads summarised then deleted.

**Setup as run.**
- BC-250, boot 831e5915, `/var/home` 58–59 %. Both runs used exp 0251's private binary (5227c025) and the bench's
  private save copy.
- **W289a, 01:08–01:14:** `capa0289.py W289a 12 8 30 … 1024`.
  - The top session gave the box to exp 0288 when the bench's lock ended. Our read analysis followed in a slot of its
    own, 01:25–01:30, under our analysis-only lock.
  - It added `fam0289.py`: each pyramid read against the two families' mean hole maps.
- **W289b, 01:32–01:41**, run with its analysis in one slot, since W289a had no hole switch (the condition in the
  plan).
  - It added `sw0289.py`: at each hole switch, the pyramid before and after against the holes before and after.
  - `fb0289.py` ran with the addrlib pattern and the best guess only.
- **Saves:** c0ee58b92c0cadc2 before and after both runs. Snapshot taken at 01:08 and removed at 01:41, nothing
  restored.
- **Reads:** 2.6 GB per run, deleted after the summaries (W289a at 01:30, W289b at 01:41). MemAvailable was 768–1316
  MiB, so some bursts in W289b were held in memory.

**Result** (`raw/`).
- **Box state.** No fault, timeout or reset in either run: the amdgpu count stayed at 257, the `.out` files have 0
  fault lines, the streams (`raw/W289ab.kern.txt`) have only routine lines, and no new devcoredump was saved.
- **The phases.** W289a was patched in all 26 shots (19.7–32.0 %), W289b too (18.3–23.2 %).
- **addrlib's pattern decodes the pyramid; the guesses do not** (`raw/W289?.fb.txt`). Smoothness of mip 0 (median
  total variation, lower is smoother):
  - W289a: addrlib 0.320; the guesses morton_y 0.631, dss_y 0.702, morton_x 0.855, dss 0.913, rows 1.354;
  - W289b: addrlib 1.031, morton_y 2.070.
- **The pyramid is a depth pyramid in which the lake's holes look far.**
  - Mip 0 values in W289a: 0.0003–0.5, median about 0.031, no texel at 0. Mips 3–4 have medians of 0.5.
  - Against the depth read next to it, with the depth image stretched over 128 × 64:

    | run | depth minimum | depth maximum | hole share |
    |---|---|---|---|
    | W289a | −0.56 | −0.59 | +0.61 |
    | W289b | −0.54 | −0.57 | +0.70 |

    The "pow2" footprint (32 × 32 pixels per texel) fits less well (W289a −0.46, −0.51, +0.47).
  - The pyramid grows with distance: reverse-Z depth is high near. It is high where the depth has holes.
  - The r values are the same at every lag, since the depth reads of a burst seldom change.
- **It does not tell the two hole states apart.**
  - Family check (`raw/W289?.fam.txt`): the X and Y families' mean hole maps over 128 × 64 are much alike (r +0.93
    in W289a, +0.66 in W289b).
  - The pyramid matches both about equally, next to X reads and next to Y reads alike:
    - W289a: +0.65 with X, +0.60 with Y;
    - W289b: +0.74 and +0.73.
- **The pyramid does not follow a hole switch** (`raw/W289b.sw.txt`). W289b had 9 switches, depth reads one or two
  apart with phi below 0.8 in the lake window. Over the texels covering the lake window, the medians:
  - the pyramid before matches the holes before and after alike (r +0.59 and +0.57);
  - the pyramid after matches them the same way (+0.59 and +0.57);
  - the pyramid's change against the holes' change: r −0.001. In 2 switches the pyramid did not change at all.

  So neither "a pyramid built from this frame's depth" nor "the pyramid before predicts the holes after" shows at
  the pyramid's 128 × 64.
- **The steps of exp 0287 again** (`raw/W289?.chg.txt`), consecutive pairs of a burst, depth / arguments / pyramid
  changed:

  | run | all three | depth and arguments | depth and pyramid | depth only | pyramid only | none |
  |---|---|---|---|---|---|---|
  | W289a | 32 | 1 | 2 | 14 | 1 | 34 |
  | W289b | 27 | 2 | 6 | 10 | 1 | 38 |

  - Again no argument change without a depth change: 0 of 168 pairs here, 0 of 336 with exp 0287.
- **The arguments still change at switches.**
  - W289b's two adjacent switches (b03 z6→z7 phi +0.42, b12 z1→z2 phi −0.37) changed 51 and 54 records.
  - The 29 pairs with stable holes changed none.
  - One pair in between (b12 z3→z4, phi +0.947) changed 88.
  - With exp 0287: all 4 adjacent switches fell on argument changes.

**Verdict.**
- **The writers' 32_FLOAT pyramid decodes with addrlib's ADDR_SW_4KB_S pattern** (X0 X1 Y0 Y1 Y2 X2 Y3 X3 Y4 X4 at
  4-byte elements). It is a far-is-high depth pyramid of the screen in which the lake's holes look far. This settles
  exp 0274's open item. The pattern guessed before the download was wrong.
- **The pyramid does not carry the hole state.** At its 128 × 64 it looks the same in X and Y frames. It is not
  rebuilt to match the holes at a switch, and the holes after a switch do not follow from the pyramid before.
  - So the occlusion-feedback hypothesis of F350 is not supported through this pyramid.
  - TODO(verify): the pyramid is coarse (a texel covers about 24 × 27 depth pixels), and finer levels or another
    culling input could still differ.
- **The GPU-side steps hold:** arguments change only with the depth, and every adjacent switch seen (4) fell on an
  argument change. What drives the steps is open. Candidates are the other inputs of the culling pass (exp 0274's
  three textures, the per-cell data of the compute pass that writes the arguments), or a race in that pass.
- **Next:**
  - find the compute pass that writes the arguments (the dispatch writing into 0x11935d3900's range, by `_FIND` on
    the bases) and its inputs;
  - read those inputs at the steps.

