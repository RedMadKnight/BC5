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
