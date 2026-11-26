# 0212 — The night lake: the water's per-cell buffer in clean and patched frames

**Question.** Exp 0205 (F269) ruled out every input the host serves to the water. Whole runs come
out clean or patched, and within a frozen view the patchwork can switch within seconds. The
water's draw PS 0x11d01ff900 reads, in both its stages, a buffer at 0x11e0007aa0 (stride 32,
25,534 records; exp 0201 X1/X2), plus per-draw pointers next to it. Does that buffer differ
between a clean and a patched frame, or between clean and patched runs? Is it rewritten during a
frozen view?

**Setup.**
- BC-250 dev box, 2026-10-22 19:41-20:01, boot ac5dab11; four runs granted by the top session, one lock each.
- The exp 0194 bench, as in exp 0205; private lake-save copy, the live saves never touched.
- `bench0212.sh`: exp 0205's `bench0205.sh` (stops when its emulator dies, refuses a used run tag)
  plus `DUMPS=1`.
  - `mem0212.py hash` runs for the whole run: a CRC-32 per 4-KiB page of the `DUMP_RANGES`
    every second, into `r-<tag>/hash.txt`.
  - `mem0212.py dump` reads the ranges once before each frozen-view shot, into
    `r-<tag>/dumps/tsNN.<base>.bin`.
  - Both are read-only, through `/proc/<pid>/mem` (no ptrace attach, as exps 0200 and 0205).
  - `DUMP_RANGES` defaults to X2's addresses: 0x11e0007aa0 + 0xc7780 (the per-cell buffer),
    0x11e04c0000 + 0x20000 (the per-draw pointers of the pixel stage) and 0x11e0c2b000 + 0x2000.
- `desc0212.py`: the image and buffer descriptors of the water's two draws, from the run's
  journal (`BC5_DIRECT_DRAW_JOURNAL` with `_PS=11d01ff900,11d01d7100`). It checks the dumped
  addresses in each run. Field layout: Mesa `src/amd/registers/gfx10-rsrc.json` @ 0866ae7.
- `cmp0212.py`: dumps compared record by record (32-byte records).
- `ab0212.sh`: the runs, alternating the cutscene session's exp 0203 binary (switch off) and the
  shared build. In exp 0205 four of six runs on the exp 0203 binary had a mostly clean lake,
  against none of four on the shared build and none of two on the exp 0194 build. That could be
  the binary, or time and memory state; alternating gives clean and patched runs to compare and
  tests that.
- Dry-tested on a `sleep` process (dump, hash and compare of its heap).
- `tab0212.py`: the dumps read as gfx10 image descriptors: per texture base, `MIN_LOD` and
  `LAST_LEVEL`, compared between dumps by address. Tables of different runs are not aligned by
  index.
- The dumps are the title's memory and stay on the box; the repo has only their decoded summaries.
- `prog0212.py`, prepared and not run in this experiment: a program from a private dump
  (`~/bc5-data/priv`), disassembled with `llvm-mc -mcpu=gfx1013`. It prints only counts of memory
  writes, atomics and exports, for the GPU-feedback check (see Verdict).

**Result** (`raw/C-runs.txt`).
- **The binary confound is gone.** C1 and C3 (exp 0203 binary) were patched throughout: 12-30 %.
  C2 (shared build) too: 22-27 %. C4 (shared build) started at 4.6 % and 9.7 %, then was clean,
  1.0 % from 19:58:50 to the end. Views were checked on the shots. C4's ts01 and ts02 are the same
  camera, with a checkerboard by the shore in ts01 and a clean lake in ts02.
- **The "per-cell buffer" is a table of image descriptors.** Its 32-byte records are gfx10 T#s:
  about 22,900 images for about 9,400 distinct textures, mostly in the AMM window, with `MIN_LOD`
  from 0 to 6. It is a bindless table of the scene's streamed textures with a detail clamp per
  texture. Its record count differs per run (25,506-25,560).
- **In a frozen view it is static, patched or not.** In C1, C2 and C3 its last change came in the
  view's first second (the camera move). After that, no page changed, and all 13 dumps of each run
  are identical.
- **The one run that turned clean had the only late change.** In C4, at 19:58:41 and 19:58:45,
  five textures had their `MIN_LOD` lowered by one, allowing one finer mip each. The lake was clean
  from the next shot on (19:58:50). None of the five is the water's own BC4 texture.
- **Our path does not rewrite the title's descriptors,** and Mesa expects gfx10 to honour T#
  `MIN_LOD` (`raw/minlod-check.txt`). Patch 0001 only reads T#s for journal lines. RADV implements
  `VK_EXT_image_view_min_lod` on every gfx10 part through WORD1 `MIN_LOD` (4.8 fixed point;
  `ac_descriptors.c` and `radv_physical_device.c` @ ab2374a), with no GFX1013 exception. That the
  chip itself honours it is TODO(verify).
- Across runs the tables are not comparable record by record. Textures sit at other addresses,
  and the 2,083 bases common to all four runs show no clean-against-patched pattern.

**Verdict.**
- **Narrowed, not named.** The water's GS-stage buffer is not per-cell data but the scene's
  streamed-texture table. It does not change during a patched frozen view, so it does not cause
  the steady patchwork by changing.
- **A lead from one event, not established:** the only run that turned clean did so 5-9 s after
  the only late table change, the title lowering five textures' detail clamps. That fits "the
  patchwork ends when the streamer finishes some last mips". It doesn't say which texture the
  water samples through the table, or why the streamer stops in the patched runs.
- **Next:**
  1. Find which table entries the water's draws index. The draw's user data or shader carries an
     index into this table; the shader's disassembly, or the journal's other user-data words,
     would give it.
  2. In a patched frozen view, compare those entries' `MIN_LOD` with their `LAST_LEVEL` and with
     what is resident.
  3. More runs with the table sampled, to see whether every clean switch follows a late table
     change.
- Nothing of this is in patch 0001 or the shared build.
