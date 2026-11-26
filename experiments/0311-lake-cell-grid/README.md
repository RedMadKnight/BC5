# 0311 — The night lake water's per-cell ping-pong grid against the hole halves

**Question.** Exp 0309 (F374): the only buffer the lake's draws swap every frame is in the full-screen water draw's
geometry-stage table (GS user-data pair 4, dword 0). Exp 0283's writer summary (`raw/W283a.wr.txt`) decodes it as a
buffer V# of stride 8 and 65,536 records, two copies 2 MiB apart: a 256 × 256 grid of 8-byte records, current and
previous frame, plausibly one record per water cell.

The lake's patches are one half of a checkerboard of cells, and the halves swap between the two states (F342, F372).
Does a field of this grid follow the hole halves, a checkerboard whose phase changes with the state?

**Plan** (the top session's yes of 2026-10-25 ~14:35; a slot after the BVH session's exp 0310; RT off; ~20 min).
- **The bench:** exp 0309's lake bench on today's setup (`bench0311.sh`: 20 frozen-view shots 5 s apart, two rings, RT
  off by `input-0311.cfg`; the launcher copy derived by exp 0299's three edits).
  - Its journal: `BC5_DIRECT_DRAW_JOURNAL=150:30` with `_PS=11d01d7100`. After each full-screen water draw, patch 0001
    prints "bake table gs ud4 <addr>: <dwords>".
- **`grid0311.py`**, run beside the bench:
  - it reads those lines and decodes the V# in dwords 0–3 (as exp 0253's `wr0253.py`), keeping the two stride-8 bases;
  - in the frozen view it takes 12 bursts 5 s apart, each 8 × (grid A, grid B, the depth image) 30 ms apart, read-only
    through `/proc/<pid>/mem`, then the G-buffer;
  - capa0287.py's file layout, so `rd0311.py` (exp 0289's `rd0289.py`, unchanged) gives each depth read its hole
    family (X, Y, …).
- **`gan0311.py`**, per bit of the 8-byte record (64 bits):
  - its set share and its checkerboard parity contrast on the 256 × 256 layout;
  - X reads against Y reads: the share of cells whose majority value differs;
  - per read, which grid changed.
  - `--selftest`: a synthetic bit 3 that is a checkerboard following the state comes out on top (to be run on the box,
    numpy).
- **Viewed shots:** one or two, deleted right after.
- **Rules:** the live saves are never used and are checked before and after; the kernel stream; stop at the first
  reset. The reads (title data) go to `~/bc5-data/priv/exp0311` and are deleted after the analysis; numbers only in the
  repo.
- **Reading:**
  - a bit with a strong parity contrast whose phase flips between X and Y reads names the cell state the lake's
    writers act on;
  - if the grid shows nothing of the kind, it is the water's other per-frame data, and the cell state lives elsewhere.

**Setup as run** (the top session's GO of 14:45 CET, after exp 0310b; boot 664515e3; launcher 628b2714; build
226bcb82; RT off by `input-0311.cfg`).
- **14:49.** Our lock line; live saves 8289704a9338a118 (never used; checked before and after).
  - `play-pkg-0311.sh` was derived by exp 0299's three edits, the four expected lines (`raw/play-pkg-0311.diff`).
  - `gan0311.py --selftest` in the distrobox: the planted bit 3 came out on top, cells differing 1.000 and parity
    contrast +1.00 / −1.00; random bits reach ~0.47 on the cell-difference measure.
  - The kernel stream ran throughout (`raw/window.kern.txt`).
- **G1, 14:50–14:55** (`raw/G1.ab.txt`, `raw/G1.out.txt`):
  - two rings (4 "compute ring" lines), RT off (3,298 build-list drops), journal `BC5_DIRECT_DRAW_JOURNAL=150:30` with
    `_PS=11d01d7100`;
  - 20 frozen-view shots.
  - `grid0311.py` beside it (`raw/G1.grid.txt`): the grid bases came from the full-screen draw's tables, then 12
    bursts 14:53:18–14:54:13, each 8 × (grid A, grid B, depth) 30 ms apart.
- **No shot was viewed:** the numbers decided it.
- **Analysis, 14:55–14:58:** `rd0311.py` (`raw/G1.rd.txt`, `raw/G1.reads.json`) and `gan0311.py` (`raw/G1.gan.txt`).
  The reads (2.7 GB) were deleted at 14:59.
- **Released 14:59:12** (BOX-QUEUE line 115).

**Result** (`raw/`).
- **No kernel event:** 0 fault lines, the amdgpu dmesg count 273 before and after (the earlier lines are exp 0310's).
- **The grids:** the journal named the same two bases as exp 0283's W283a a day earlier, 0x112f3a5810 and 0x112f5a5810
  (15 full-screen draws each). So their allocation is fixed.
- **The lake was mostly clean in this run:** patched at ts00 (18.4 %), ts01 (8.4 %) and ts16 (18.6 %), clean in the
  other 17 shots.
  - Only burst b02 has labelled depth reads: Y at z0 and z6, X at z5 and z7. The two families are nearly disjoint:
    0.3 % of the window in both, 1.8 % of each in the other.
- **The grids are nearly static:**
  - between consecutive reads 30 ms apart, 0–68 of 524,288 bytes change, a few records, in A or in B by turns (one
    grid written per frame);
  - the share of non-zero records stays at 0.650 (A) and 0.706 (B) in every read.
  - In b02 the hole state went Y (z0) … X (z5) → Y (z6) → X (z7), while grid A changed by 22, 0 and 21 bytes and grid
    B by 0, 18 and 0 bytes between z4 and z7.
  - The bit-level comparison (2 X against 2 Y reads) finds 0 cells differing in every bit of both grids, and no bit
    with a parity contrast.

**Verdict.**
- **The water's 256 × 256 ping-pong grid does not carry the lake's hole state.** The hole halves swap while the grid
  changes by a few records at most.
  - It is sparse per-frame water data, the full-screen water draw's, written one copy per frame.
  - With exp 0309 (F374), this closes the ping-pong lead: neither the depth writers nor this grid hold a frame-swapped
    state that follows the halves.
- **Thin on labels, decisive on change:**
  - only one burst had labelled reads, because the lake was mostly clean;
  - but a grid that changes by ≤ 68 bytes per 30 ms cannot hold two 16 %-of-the-window halves that swap within one
    read interval.
- **Next candidates:**
  - what the depth writers read beyond the first 32 dwords of their tables (the bindless T# table of F272, image
    contents);
  - the writers' own per-draw coverage of the two halves.
