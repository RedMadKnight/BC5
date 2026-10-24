# 0274 — The night lake: the depth writers' per-cell coverage, the pyramid they read, and its producer

**Question.** Exp 0271 (F333): in patched frames the G-buffer holes are pixels where nothing drew in
that frame (no depth, no G-buffer), while every lake draw compared within a run is issued
identically in both states (F313, F320, F323). So the same draws cover less. What decides the
coverage of the GPU-driven depth writers per cell, and does it differ between clean and patched
frames?

**The lead.** Exp 0253's journals (`0253-…/raw/W251a.wr.txt`) show that the depth writers' vertex stage
(GS user data 16–19 and 24) points at a table of image descriptors: a 32_FLOAT pyramid of five
levels, 128×64 at 0x11d0886000 down to 8×4 at 0x11d0892000, and three other textures (256×256
format 20 at 0x1162e60000, 1024×1024 format 179 at 0x848789c000, 256×256 format 179 at
0x119975c000). A float pyramid read by the vertex stage of GPU-driven depth writers is the kind of
input that culls or places whole cells (for example a hierarchical-depth pyramid for occlusion
culling, or a height pyramid). If it holds other values in patched frames, identical draws would
cover fewer cells.

**New lead (top session, 2026-10-24 ~21:00).** In the maintainer's test 0280 arm A (20:48–20:57, private
binary md5 cd17ab79) `KYTY_BC5_RT=0` dropped the BVH build work: the compaction, the compute chain
0x909939400/0x909936c00/0x909939700/0x909939900, and the second tree family 0x909974200,
0x909973900, 0x909973b00, 0x909973d00, 0x909973f00. Every ray-query consumer kept running, and the
maintainer saw no patches on the lake. That is one observation in play, not yet a bench A/B.

**Plan** (as written before the runs; the GO, 21:06, granted step A: 2 runs, RT off then on).
- **Step A, RT off against on, on the lake bench.**
  - Two runs of the usual frozen-view bench (26 shots, exp 0197's patch metric) on the RT session's
    binary `EMU=~/bc5-work/exp0278/kyty_emulator` (md5 cd17ab79), through the bench's own launcher
    copy. One arm with `KYTY_BC5_RT=0` and `KYTY_BC5_RT_BUILD_PGM=909974400,909939400,909936c00,
    909939700,909939900,909974200,909973900,909973b00,909973d00,909973f00` (0280 arm A's list), one
    with ray tracing on. Only those ten dispatches differ between the arms (the RT session); the
    bench uses its private save copy.
  - `capl0274.sh` reads the depth memory, the G-buffer, the pyramid region and the writers' three other
    images (0x1162e60000, 0x848789c000, 0x119975c000) in both arms.
    - `pyr0274.py` compares the pyramid with where the holes are.
    - `vic0274.py` compares every region read by read against the RT-off run's first read: how many
      words changed and in which 64-KiB blocks. The RT session reads the RT-off fix as a stray store
      from the second tree family (F339), not an intended write, so a change confined to a few blocks
      of an image that should not change would be such a victim.
  - The journal (that binary has patch 0001's, without `_EVERY`): one window at t 150 with `_PS` on the
    full-screen draw and `_FIND` on the four images' bases in image-descriptor form (`11d08860`,
    `1162e600`, `848789c0`, `119975c0`) and the pyramid's as a buffer low dword (`d0886000`). It lists
    the draws and dispatches that reference them in each arm.
- **Step B, which second-family program is involved.** The RT session's roles (2026-10-24):
  - all five take their DISPATCH_INDIRECT arguments from one per-object block (one slot each:
    +0x00 973900, +0x20 973b00/973f00, +0x40 974200, +0x60 973d00);
  - 0x909974200 clears or initialises the block;
  - 973900/973b00/973f00 build the leaf lists;
  - 0x909973d00 is the 69³ cell pass, not disassembled.

  None is known to write the lake writers' inputs. If step A shows a victim region, drop the
  programs one at a time (`KYTY_BC5_RT_BUILD_PGM` with one fewer) to find the writer, on the GO's
  number of runs.
- **Within-run comparison (exps 0266/0271), only if needed:** one run with both states on exp 0251's
  binary, journal on the full-screen draw and the depth-only writers by prefix (`11d1d88`, `11d1dd6`,
  `11d090d`, `11d0a98`, `11d373`, `11d1e2f`, `11d28b`, `11d1d33`, `11d29c`), `_EVERY=10`, the same
  `_FIND` and the same reads.
- **Scripts:**
  - `ab0274.sh` / `bench0274.sh` (exp 0271's, renamed; `EMU=` picks the binary and its md5 is
    logged);
  - `capl0274.sh` (adds the pyramid region 0x11d0880000 + 0x20000 to exp 0271's reads, every 7 s,
    at most 20, into `~/bc5-data/priv/exp0274`, summarised then deleted);
  - `ana0274.py`, `coin0274.py` (exp 0271's);
  - `vic0274.py`: each read region against a reference read (word differences and the 64-KiB blocks
    they fall in), for stray writes;
  - `pyr0274.py`: the pyramid per read, with value statistics per level and mip 0 against the
    clean reads' median texel by texel. It also correlates mip 0 with the hole fraction per texel,
    assuming a linear 128-wide layout and one texel per 32×32 render pixels (both TODO(verify)).
- Raw files under 1 MiB each; no images kept.

**Setup as run.**
- BC-250, 2026-10-24 21:06–21:22, boot 831e5915; `/var/home` at 72 %.
- The live saves held the maintainer's lake save (af64b06adff9c5f1). They were snapshotted before
  the runs and checked before, between and after; they never changed (the bench uses its private
  copy), and the snapshot was removed.
- Binary: `~/bc5-work/exp0278/kyty_emulator` (md5 cd17ab79, the RT session's), through the bench's
  launcher copy.
  - W274a, 21:06–21:12: `KYTY_BC5_RT=0` plus 0280 arm A's ten-program `KYTY_BC5_RT_BUILD_PGM`; the
    emulator's environment was checked.
  - W274b, 21:13–21:19: no RT variables (ray tracing on).
- Journal: one window at t 150, `_PS=11d01d7100`, `_FIND` on the images' bases. Reads:
  `capl0274.sh`, 20 per run (1.4 GB each, deleted after the summaries).

**Result** (`raw/`).
- **Box state.** No kernel fault, timeout or reset in either run: the amdgpu dmesg count stayed at
  257, the `.out` files have 0 fault lines, the stream (`raw/W274ab.kern.txt`) has only routine
  lines, and no new devcoredump was saved.
- **Ray tracing off did not clear the lake on the bench.**
  - W274a's journal shows the build dispatches dropped ("ray tracing off: … of 0x909973f00 dropped
    (build list; 6164481 so far)", and likewise for 0x909973d00, 0x909974200, 0x909973b00 and
    0x909973900).
  - Its shots were still patched at ts07–ts12 (15.2–27.7 %) and ts23–ts25 (15.6–26.6 %), and clean
    at ts00–ts06 and ts14–ts22 (1.1–3.5 %; ts13 6.7 %).
  - W274b, ray tracing on, was patched in all 26 shots (19.9–26.6 %).
  - The maintainer's clean lake with RT off (0280, F340) is therefore not reproduced on the bench.
    It may have fallen in a clean phase, which every run so far has had. The bench's launcher copy
    (old values: no PRT, old skip list) also differs from play-pkg.sh.
- **Within W274a (RT off, both states), the holes are again pixels with cleared depth**
  (`raw/W274a.ana.txt`, `raw/W274a.coin.txt`).
  - The 5 complete clean reads have almost no depth 0 (0–7 %) and no cleared G-buffer, apart from
    one read caught just after the G-buffer's clear.
  - The 2 complete patched reads (cap07, cap18) have 31–34 % depth 0 and 30–33 % cleared G-buffer,
    but on different pixels: 0.5–5 % of the cleared pixels have depth 0, phi −0.46 and −0.39.
  - A read at the edge of the phase (cap10) has 7–8 % of each, 97 % on the same pixels.
- **The hole pattern seems to alternate between two complementary sets of cells from frame to
  frame.** Each read takes the depth memory (41 MB) and then the G-buffer (25 MB), so the two can be
  a few frames apart. In patched reads the two hole sets have coincided (W271b, phi up to +0.97),
  half-overlapped (W271a) and been disjoint (W274a, phi about −0.4), with similar shares each time.
  That fits a pattern that toggles between complementary cells, with the pair landing on the same,
  the opposite or a mixed parity. It is an inference from the reads, not yet a measurement.
- **The writers' images** (`raw/W274ab.vic.txt`, `raw/W274a.pyr.txt`).
  - Within each run the three textures never change. The 1024² format-179 and 256² format-179
    images keep one md5 over all 20 reads. The 256² format-20 image changes by one word in two reads
    of W274a, one clean and one patched, and not at all in W274b.
  - Between the runs they differ, constant within each: content of the run, not damage during it.
  - So no stray write into them shows up, in line with RT off making no difference.
  - The 32_FLOAT pyramid changes in every read (about 4,800 words of mip 0 against the first read)
    and has the same value statistics in clean and patched reads (mip 0 median about 0.0099, max
    0.5). Its image descriptor (`raw/W274ab.find-detail.txt`) has word 3 0x90500324: SW_MODE
    (bits 20–24 per Mesa's `src/amd/registers/gfx10-rsrc.json` @ 0866ae7, as cited in exp 0212's
    `desc0212.py`) is 5, 4KB_S in addrlib's numbering, not linear. So `pyr0274.py`'s per-texel
    correlation with the holes (about 0) maps the wrong texels and says nothing.
- **Who references the images** (`raw/W274a.find.txt`, `raw/W274b.find.txt`,
  `raw/W274ab.find-detail.txt`).
  - In W274a, 57 draw kinds (pixel shader, slot, direct or table) hold them, 67 in W274b. Of W274a's 25
    most frequent kinds, all but one hold them through descriptor tables. Among them are the colour + depth writer 0x11d29e9600 (0x11d29e9c00
    in W274b) and the depth-only writer 0x11d373e600 (0x11d373f100).
  - Two dispatch kinds hold them too. One is CS 0x11d0288800 through a table at user data 0, with
    a DISPATCH_DIRECT of 6144 × 1 × 1 groups (header c0031500, opcode 0x15 per
    `tools/bc5-agc/regdb/pm4-opcodes.tsv`); its address is 0x200 below F310's fill kernel
    0x11d0288a00.
  - The second kind was not printed, so whether a BVH build program references the images is
    open. W274a, with the ten build programs dropped, has two dispatch kinds as well
    (TODO(verify): whether a dropped dispatch still reaches the `_FIND` journal).

**Verdict.**
- **The BVH build work is not needed for the patches.** With the ten build programs dropped
  (millions of dispatches skipped), the lake still went patched in two phases of one bench run.
  The maintainer's RT-off observation (F340) was most likely one clean stretch in play rather than a
  fix.
- **No stray write into the depth writers' images shows,** with ray tracing on or off. Step B (bisecting
  the five programs) is not warranted by this run.
- **The holes are pixels with cleared depth in patched frames** (as F333), now also with ray tracing
  off.
- **New lead:** the depth and G-buffer hole sets of one read pair coincide, half-overlap or are
  disjoint from run to run, which suggests a pattern that alternates between complementary cells
  from frame to frame.
- **Next:**
  - read the depth memory twice in quick succession (two reads about one frame apart) in a patched
    phase, to test the alternation directly;
  - decode the pyramid with addrlib's 4KB_S pattern before comparing it with the holes.
