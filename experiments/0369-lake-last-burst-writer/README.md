# 0369 — The night lake's last depth burst: which pass writes it, and whether the holes' 0 is a missed clear

**Question** (the top session's GO of 2026-10-28 ~19:30, after exp 0365's F478). In each frame the lake's depth holds
the previous frame's final until about +18 ms. Then one burst rewrites it, leaving one complementary half (X or Y) at
0. This experiment asks, offline first:
1. Which draws or dispatches in that last burst bind the lake's depth as a target or UAV?
2. What are their programs, sizes and viewports, and do their parameters show a checkerboard or half-res pattern?
3. Is the 0 a clear that the draws miss, or a value that something writes?

**Sources** (offline; no emulator, nothing written on the box):
- Draw journals copied read-only from the box at 19:33 and 19:48, stored in the laptop's private folder, never
  committed:
  - exp 0251's private binary, which logs the depth/stencil state of every journalled draw (exp 0245's "bake db" line):
    - Z2 (exp 0245, a clean window at 3328): `play-20261023-2023`;
    - W251b (patched, 2560, filtered): `play-20261023-2207`;
    - W257a (exp 0257, patched, 3072, unfiltered `_EVERY` windows): `play-20261024-1413`;
  - the shared build:
    - H1 (exp 0362, clean, 2560): `play-20261028-1647`, with `_FIND=1129ec00` and per-job timing lines;
    - J1 (exp 0354): `play-20261028-0934`;
    - K1 (exp 0365): `play-20261028-1916` (no draw journal; not used in the end).
- The committed poll logs: exp 0362's `raw/H1.events.txt.gz`; exp 0354's `raw/J1.rdj2.json` and `raw/J1.ph.txt`;
  exp 0365's `raw/K1.ana.txt`.
- Register fields: the repo's `tools/bc5-agc/regdb/gfx10.json` (Mesa's gfx10 register JSON), checked against the
  box's Mesa clone at 0866ae7, `src/amd/registers/gfx10.json`:
  - DB_RENDER_CONTROL (0x28000): STENCIL_COMPRESS_DISABLE is bit 5 and DEPTH_COMPRESS_DISABLE bit 6;
  - DB_Z_INFO (0x28040): FORMAT [1:0], NUM_SAMPLES [3:2], SW_MODE [8:4], TILE_SURFACE_ENABLE [29];
  - the bake line's "clear z" is DB_DEPTH_CLEAR (ctx 0x00b, `patch0245.py`).
  - radeonsi sets the same two bits for its in-place depth flush (`src/gallium/drivers/radeonsi/si_state.c:1728`,
    `db_flush_depth_inplace`).

**Scripts** (each prints a summary only; the journals stay private):
- `seq0369.py <direct.log>`: every pass with the lake's depth as its target, the HTILE fill, CS 0x11d0288800, the
  water draw and any draw with a non-zero DB_RENDER_CONTROL, as a letter string in journal order. Also the passes
  around each decompress (`raw/W257a.seq.txt`, `raw/Z2.seq.txt`).
- `al0369.py`: H1's depth bursts and pyramid changes against the water draw's submit (`raw/H1.align.txt`).
- `jb0369.py`: H1's jobs paired with their GPU completions, from the journal's per-job "timing" lines (`raw/H1.jobs.txt`):
  - a pass's prepare time (the ring thread's "find"/"bake" line) is a lower bound for its GPU time;
  - the completion of the job of the last submit line before it is an upper bound.
- `fl0369.py`: J1's per-frame A/B side (F436) against the flip count and the display buffer index (`raw/J1.flip.txt`).

**Setup as run** (offline; the number was given by the top session, and `~/bc5-work/exp0369` was not created because
nothing was to be written on the box).
- **19:33:** four journals were copied read-only (`cat` of the `.zst` files, and `zstd -c` of H1's log at
  `nice -n19 ionice -c3`). BOX-LOCK was empty and no emulator ran.
- **19:48:** J1's and K1's logs were copied the same way, during the bvh session's soak (exp 0368's lock line, its
  emulator up, 810 MB available), under the GO's read-only, idle-priority rule.
- **19:51:** Mesa's `gfx10.json` and `si_state.c` were read on the box (a few KB).
- All analysis ran on the laptop (Python 3.14 + numpy). The decompressed journals sit in the laptop's private folder
  outside the repo.
- **Changes after seeing the data:**
  - `seq0369.py`'s first version cut frames at every HTILE fill. There are several per frame, so it now prints a
    letter string.
  - `jb0369.py`'s job attribution was checked against the ring thread's prepare times, which give the bounds in the
    table below.
  - `fl0369.py` was added once K1's 45 % switching suggested a coin.

**Result.**
- **The lake's depth is compressed.**
  - All 7,127 DB lines that bind the lake's depth (0x1129ec0000; Z2 794, W251b 2,394, W257a 3,939) have
    DB_Z_INFO 0xa0000183: Z_32_FLOAT, one sample, SW_MODE 24, TILE_SURFACE_ENABLE 1 (HTILE), ZRANGE_PRECISION 1.
  - All 12,406 DB lines have DB_DEPTH_CLEAR 0.0 (`clear z 0`).
- **The order per frame is the same in the clean Z2 and the patched W257a** (`raw/*.seq.txt`, letter strings):
  1. the HTILE fill, CS 0x11d0288a00 (F310);
  2. about 128 depth writers: Z on + write, GEQUAL, viewport and target at the render size, mostly DRAW_INDIRECT;
  3. the water draw, PS 0x11d01d7100;
  4. post-water draws, then a full-screen stencil pass (PS 0x11d01e2300, Z off);
  5. nine indexed writers (PS 0x11d01ff900, 0x11d0203f00, 0x11d0208400), Z on + write, GREATER, with stencil;
  6. **decompress #1:** DRAW_INDEX_AUTO, 3 vertices, PS 0x11d0208400, colour mask 0, Z off,
     DB_RENDER_CONTROL 0x60 (DEPTH_COMPRESS_DISABLE + STENCIL_COMPRESS_DISABLE);
  7. 43–86 depth-tested draws into 0x113d770000 and the depth readers (exp 0362's PS 0x11d4d01800, CS 0x11d02d0a00,
     …, CS 0x11d0404200, CS 0x11d039cd00);
  8. the 3840 HTILE fill (640 groups, HTILE 0x112bea0000; F310);
  9. CS 0x11d0288800: 7,168 groups at 3328, 6,144 at 3072. At 3328 that equals the HTILE fill's group count (one per
     KiB of HTILE + stencil, F310); at 3072 the fill has 5,760;
  10. **decompress #2:** DRAW_INDEX_AUTO, 3 vertices, no PS (W257a) or a stale PS 0x11d01e1700 (Z2), CB0 left at
      0x114c6c0000 3840×2160 with mask 0, Z off, DB_RENDER_CONTROL 0x60, viewport at the render size, on the lake's
      depth and that size's HTILE;
  11. the 3840×2160 compute passes (CS 0x11d03f7900, 0x11d03f8800).
- **The timing places the last burst at decompress #2** (H1, medians after the pyramid change, `raw/H1.jobs.txt`):

| Event | When |
|---|---|
| Bursts 1 and 2 | +6.4, +8.3 ms |
| Water draw prepared, its job done by | +2.5, +6.7 ms |
| First reader (CS 0x11d02d0a00) prepared, its job done by | +14.0, +16.4 ms |
| CS 0x11d0288800 prepared, its job done by | +16.0, +23.4 ms |
| Burst 3 | +19.2 ms |

  - Burst 3 comes after the readers' job is done, and inside the next job. That job holds CS 0x11d0288800 and, by
    Z2's and W257a's order, decompress #2. Example, frame 101: the readers' jobs were done at +15.0 and +17.0; bursts
    came at +17.6 and +18.6; that job was done at +23.0.
  - That job's CS 0x11d0288800 dispatches are not depth writers: the `_FIND` match is a register block next to their
    user data (CB_COLOR0_BASE 0x114c6c00, CB_COLOR0_INFO 0x8028, which is decompress #2's colour state).
  - **Decompress #1 changes nothing in the polled sample:** no burst between +8.3 and +17.6 ms. Why is open (a
    scissor would do it; scissors are not journalled in these windows).
- **This fits exp 0365's K1 exactly.**
  - The HTILE fill clears without touching the depth memory, so mid-frame (+9 ms) the memory still holds the previous
    final.
  - The compressed writes touch part of it (K1: 8 % changed, 5 % zeroed).
  - The per-pixel image appears only when the decompress expands every tile. A tile or pixel still in the clear state
    gets DB_DEPTH_CLEAR, 0.0. So K1's "late zeros" (previous values at +9 ms, 0 at the end) are the clear made
    visible.
- **No checkerboard or half-res in the depth state:** one sample, the full render-size viewport for the writers and
  both decompresses, and one full-screen triangle.
- **The X/Y choice behaves like a fair coin per frame** (`raw/J1.flip.txt`):
  - In J1, the side does not follow the display buffer index or the flip count's parity (A 28 / 31, B 29 / 23).
  - Over 88 consecutive frame pairs there was always one flip between them; the side changed in 41 and held in 47.
  - K1 switched in 55 of 122 transitions (exp 0365).
  - So it is not a frame-parity checkerboard. There is no tendency to switch either, which a self-occlusion feedback
    through the previous frame's pyramid (F350's TODO) would give.

**Verdict** (F484, F485).
- **1, the writer:** the last burst is the in-place decompress of the lake's depth, decompress #2 (step 10 above), by
  its position in two journals and H1's job timing. Its program is a PS-less full-screen triangle. In that job, H1's
  `_FIND` matched no dispatch's user data except CS 0x11d0288800's neighbouring register block. A dispatch writing the
  depth through a deeper table would not show, so "no UAV writer" is not proven.
- **2, the parameters:** no checkerboard or half-res. The pattern is not in the decompress.
- **3, the 0:** it is the frame's fast clear (the HTILE fill, DB_DEPTH_CLEAR 0.0) made visible by the decompress, not a
  value a draw writes. A hole is a pixel that the HTILE still marks as cleared when decompress #2 runs. Two readings
  remain:
  - **(a) coverage:** no writer drew there. F333's G-buffer coincidence and F309's perspective-cell shape fit this.
  - **(b) metadata:** a writer drew there, but the HTILE that decompress #2 reads says "cleared". CS 0x11d0288800 runs
    right before it, over the HTILE + stencil size at 3328, which could restore an HTILE. This is not excluded.
- **Next: run K2** (designed below; ~6 min of box time, fits 22:45–23:00).
  - Under (b) the holes are whole 8×8 depth tiles. Under (a) their edges cross tiles.
  - Under (a) the hole tiles' memory is untouched until decompress #2, and the drawn tiles' compressed writes sit at
    fixed offsets within each 256-byte tile.

**Run K2 (prepared, not run; needs a slot after 22:45):** exp 0365's lake bench and poller unchanged (`setup0369.sh`,
`ab0369.sh`, `bench0369.sh`, `pl0369.py`: 0365 → 0369), RT ON, one run.
- **`tz0369.py`**, on frames with an untorn final at a clear size, at full render resolution in the lake window:
  - the share of 8×8 tiles that are all hole, no hole and mixed, on the true tile grid and on a grid shifted by
    (4, 4). Tile-aligned holes give few mixed tiles on the true grid and many on the shifted one; cell-shaped holes
    give similar shares on both;
  - for consecutive pairs, the mid snapshot against the previous final: the changed dwords' offsets within their
    256-byte tile, and the changed share in tiles that are holes in this frame's final against drawn tiles.
- **Stop rules:** the standing ones.
- **Snapshots and shots** deleted after the analysis, unviewed.
