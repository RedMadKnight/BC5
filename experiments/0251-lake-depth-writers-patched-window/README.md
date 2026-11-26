# 0251 — The night lake: the HTILE clear, the filter, and the depth-only writers in patched frames

**Question.**
- Exps 0245–0250 narrowed the night lake's patches to water-plane cells where the full-screen water
  draw fails its GEQUAL depth test (F305, F307).
- The depth buffer's HTILE moves with the render size and is overwritten within every frame (F309),
  so each frame has to re-initialise it. Before the full-screen draw, the lake's depth comes from
  about 20 GPU-driven depth-only writers: `DRAW_INDIRECT` draws by PS 0x11d1d88300, 0x11d1dd6400,
  0x11d090d900 and 0x11d0a98300.
- The top session's revised hypothesis (2026-10-23): the 3328 HTILE is not re-initialised, so it
  keeps the depth that the 3840×2160 pass writes over it, and those words follow the scene's
  geometry. A packet the backend's filter drops could be the cause.
- Within runs:
  1. Is the HTILE re-initialised in patched frames?
  2. Does the filter drop anything that could do it?
  3. What do the HTILE ranges hold?
  4. Do the writers or their arguments differ between clean and patched frames?

**Setup.**
- BC-250 dev box, 2026-10-23, granted by the top session after exp 0250: the private build and
  1–2 runs, about 25 min.
  - Build 21:55; run W251a 21:56–22:02.
  - Rebuild 22:06; run W251b 22:07–22:13.
  - Analysis until 22:15. Boot 31c1a6ac; `/var/home` at 70 %.
- **Private build** (`build0251.py`, exp 0245's method). A copy of the shared tree's
  `bc5LleAgc.cpp` is patched in turn by:
  1. `edit0194.py` (exp 0194): `BC5_DIRECT_DRAW_JOURNAL_EVERY`, which exp 0245's binary lacked
     (F309), and each journalled indirect draw's arguments at submission;
  2. `patch0245.py` (exp 0245): the "bake db" line;
  3. `patch0251.py`:
     - a "bake db2" line (`DB_HTILE_SURFACE`, `DB_RENDER_OVERRIDE2`);
     - for every buffer in a journal window, the `DMA_DATA`/`WRITE_DATA` packets that write into
       the depth memory 0x1129ec0000–0x112c800000;
     - for W251b's rebuild, an opcode census: the type-3 opcodes that
       `backend/policy/pm4-policy.tsv` does not pass (its default verdict is drop), and the
       `EVENT_WRITE` event types.

  The unit compiled with warnings only (`raw/build.txt`, `raw/build2.txt`). `~/src/KytyPlus` and
  the shared objects were not written. The W251a binary was deleted after the rebuild; the W251b
  binary stays in `~/bc5-work/exp0251`.
- **Runs.** `ab0251.sh` and `bench0251.sh` are exp 0248's, renamed. Conditions as before:
  - 26 frozen-view shots;
  - the 3-s `dmesg` poll and the kernel stream to the laptop;
  - the live saves checksummed.

  The journal ran `BC5_DIRECT_DRAW_JOURNAL=150:12` with `_EVERY=10` and `_PS` set to the
  full-screen draw plus the four writers. `_FIND` looked for:
  - W251a: the four HTILE bases of F309, in register form (base >> 8) and as a low dword;
  - W251b: the low dwords of all ten 16:9 sizes' HTILE bases, 1536–3840 in steps of 256.
- **W251a's reads.** `capl0251.sh` read the whole depth memory (0x2940000 bytes) 8 times, 15 s
  apart, into `~/bc5-data/priv/exp0251`. `ana0251.py` classified the words of each HTILE range and
  located the words outside 0..1. It found the frame's size by block-row shear at 2048, 3072, 3328
  and 3840. The reads (331 MB) were deleted after the summary; no render was made.
- **Summaries:**
  - `jr0240.py`: windows and frames;
  - `jr0245.py`: depth/stencil passes;
  - `db0250.py`: the depth description per draw;
  - `cmp0245.py`: writers per full-screen draw;
  - `args0251.py`: the writers' arguments per window;
  - `clr0251.py`: per frame, its size and the HTILE fills before its full-screen draw;
  - `<tag>.pool.txt`: window, `_FIND` and depth-memory lines;
  - `W251b.census.txt`: the census.

  `edit0194.py` prints a window's opening line for every buffer until the first matched one, so
  `args0251.py` lists many empty "windows". The 21 real windows per run are those with draws.

**Result** (`raw/`).
- **Box state.** No kernel fault, timeout or reset in either run.
  - The amdgpu dmesg line count stayed at 675. The `.out` files have 0 fault lines, and the streams
    have only routine IPv6 lines.
  - The live saves' checksum was the same before and after both runs (f6475842373bf369).
  - Each run wrote about 200 MB: run directory 78–81 MB, journal 120–121 MB.
- **The two runs.**
  - W251a was clean (0.6–1.0 %) except ts13–ts18 (8.1, 5.8, 9.1, 2.9, 0.9, 13.6 %).
  - W251b was patched in all 26 shots (18.9–28.1 %).
  - Each had 21 journal windows of 4–6 frames, at t 150–355.
- **The render size changes every few frames in both states.**
  - W251a's frames ran at 2048, 2304, 2560, 2816, 3072 and 3328 wide, usually three frames at one
    size and then one smaller.
  - W251b's patched frames covered the same sizes: 2048 ×7, 2304 ×3, 2560 ×17, 2816 ×9, 3072 ×8,
    3328 ×34 (`raw/W251b.clr.txt`).
  - Every frame's depth description is its own size's. The HTILE base is the depth base plus that
    size's depth blocks for all six sizes, now including 2304 (0x112ab20000), 2560 (0x112adc0000)
    and 2816 (0x112b0a0000) (`raw/W251a.surf.txt`).
- **1. The per-frame HTILE clear is a compute fill, and it runs in patched frames.**
  - `_FIND` caught CS 0x11d0288a00, exp 0094's "copy kernel", dispatched with user data 0 = the low
    dword of a size's HTILE base, directly in the register (`raw/W251a.pool.txt`). Its group count
    is that size's HTILE + stencil in KiB, i.e. one 1-KiB group per KiB:
    - 3328: 7168 groups = 512 KiB + 6.5 MiB;
    - 3072: 5760 = 384 KiB + 5.25 MiB, so the 3072 stencil is 0x112b420000 (F305's second
      stencil);
    - 2048: 2752 = 192 KiB + 2.5 MiB;
    - the 3840 HTILE alone: 640.
  - Every frame fills the 3840 HTILE and its own size's HTILE + stencil before its full-screen draw.
  - In W251b's 126 journalled frames (78 patched), no frame lacked its own size's fill since the
    previous frame (`raw/W251b.clr.txt`). Only a window's first frame cannot be checked, because
    its fill can fall before the window opens.
  - W251a's frames at 2048, 3072 and 3328 had theirs too. The 19 frames `clr0251.py` flagged there
    are all at 2304, 2560 or 2816, whose HTILE bases that run did not search.
  - The kernel is not on the bench's `BC5_DIRECT_SKIP_PGM` list (11d049aa00, 11d04a6000, 909974400,
    11d04bb900).
- **2. The filter drops nothing in these buffers.**
  - The census covered 2922 window buffers in W251b. None held an opcode outside
    `pm4-policy.tsv`'s pass list.
  - Their `EVENT_WRITE` types are 7, 16, 44, 46, 56 and 57: CS_PARTIAL_FLUSH, PS_PARTIAL_FLUSH,
    FLUSH_AND_INV_DB_META, FLUSH_AND_INV_CB_META, PIXEL_PIPE_STAT_CONTROL and
    PIXEL_PIPE_STAT_DUMP (`VGT_EVENT_TYPE` in `tools/bc5-agc/regdb/gfx10.json`). The table passes
    `EVENT_WRITE`.
  - No `DMA_DATA` or `WRITE_DATA` in any window wrote into the depth memory, in either run.
- **3. What the HTILE ranges hold** (W251a's 8 reads, `raw/W251a.ana.txt`; frames mostly at 3072,
  some at 2048 or 3328).
  - **3840 HTILE:** all zero in every read.
  - **3328 HTILE:** never a depth float; the "depth-like" share, floats in [1e-6, 1], was 0.000 in
    all 8 reads.
    - In cap5, taken during the only 3328 frames, it held HTILE words: 74 % small non-zero words
      such as 0x002800af and 0x0024009f, plus zeros.
    - Otherwise it held zeros (71–100 %) and 0x40404040 or 0x00000040 words. Those are 8-bit
      stencil bytes: the 3072 stencil (0x1560000–0x1aa0000 from the base) covers the 3328 HTILE
      (0x1860000–0x18e0000).
  - **3072 HTILE:** HTILE words (84 %) and zeros when the frame was at 3072. In cap5, after the
    3328 frames, zeros and stencil bytes.
  - **The words outside 0..1 are stencil bytes.** They are 8–18 % of the memory, mostly 0x40404040,
    and sit in the 3072 stencil range (0–49 % of its words), the 3328 stencil range (25–47 %) and the
    parts of the 3328 depth data that the smaller sizes' stencils cover. That explains exp 0248's
    out-of-range words: another size's stencil, not compressed depth tiles.
- **4. The writers.**
  - Within W251a, every frame had 22 depth writers before its full-screen draw, in clean,
    mixed and patched windows alike (`raw/W251a.cmp.txt`): 2 × 11d090d900, 1 × 11d0a98300,
    12 × 11d1d88300, 7 × 11d1dd6400.
  - In each argument slot, the patched frames' vertex counts fell within the clean frames' range
    (e.g. one slot of 11d1d88300: patched 448–2231, clean 447–2239). No zero-count writer appeared
    in either state.
  - Across runs the count differs: H1 (exp 0248) 20, W251a 22, W251b 18. W251b, the fully
    patched run, had one 11d090d900, two 11d1d88300 and one 11d1dd6400 fewer per frame, and its
    argument slots lie elsewhere in the argument buffer (0x760–0xaa0 against 0xb20–0xf80). That is a
    run-level difference; within a run it does not follow the patches.

**Verdict.**
- **The HTILE route is closed.**
  - The per-frame depth/stencil clear exists: a compute fill (CS 0x11d0288a00) of each size's
    HTILE + stencil, plus the 3840 HTILE.
  - It ran before the full-screen draw in every checked frame, patched ones included. The filter
    dropped no packet in those buffers.
  - The 3328 HTILE never held the 3840 pass's depth. The aliased memory holds other sizes'
    stencil bytes, which a correctly cleared HTILE makes harmless.
  - This refutes the top session's revised aliasing hypothesis for these runs, and the words
    outside 0..1 of F307 are stencil bytes.
- **What remains is the writers' GPU-side work.**
  - Within a run, the writer draws and their arguments do not separate patched from clean frames.
  - Across runs, the number of writers per frame is a run property (18–22), and the fully patched
    run had the fewest.
  - The water-plane cells, the per-run patch state and the GPU-written indirect arguments all
    point at the GPU-driven culling or LOD that feeds those writers, or at what the writers
    themselves draw: their vertex data, not their counts.
- **Next:** compare, within one run, the depth the writers leave in patched cells and in clean ones.
  That means reading the depth buffer right after the writers and before the full-screen draw, by
  a journal-triggered read rather than a random-time one. Alternatively, read the writers'
  vertex/instance buffers in a clean and a patched run.
