# 0248 — The night lake: the depth buffer under the G-buffer's holes

**Question.** Exp 0245 (F305) found the water's full-screen draw (PS 0x11d01d7100) depth-tested,
GEQUAL with no write, against the depth buffer 0x1129ec0000. About 130 earlier draws write that
buffer. What depth do the hole cells hold when the draw runs, and what shape does it have? Does a
within-run journal of the depth-only writers change between clean and patched frames?

**Setup.**
- BC-250 dev box, 2026-10-23. The top session granted this after exp 0247: at most 2 runs in about
  30 min, reads summarised and then deleted, and one depth render kept.
  - Run H1: 21:13–21:19. Analysis lock until 21:27. Boot 31c1a6ac; `/var/home` at 70 %.
- **Binary.** `ab0248.sh` and `bench0248.sh` are exp 0245's driver and bench, renamed. They run
  exp 0245's private binary (`~/bc5-work/exp0245/kyty_emulator`: today's shared tree plus the
  "bake db" journal line), not exp 0194's.
- **Run conditions** were the same as before:
  - the 3-s `dmesg` poll and the kernel stream to the laptop;
  - `/var/home` under 80 %;
  - the live saves checksummed;
  - 26 frozen-view shots, each scored with exp 0197's patch metric (clean under 5 %, patched 8 % or more).
- **Journal.** `BC5_DIRECT_DRAW_JOURNAL=150:12`, `_EVERY=15`, and `_PS` set to the full-screen draw
  plus the four depth-only writers seen in exp 0245: 0x11d1d88300, 0x11d1dd6400, 0x11d090d900 and
  0x11d0a98300. `jr0245.py` and `cmp0245.py` (exp 0245's) summarise it.
- **Reads.** `capl0248.sh` was started by hand during the frozen view. Every 15 s, at most 8 times, it
  reads the depth buffer and the G-buffer target 0x113f230000 together.
  - The read is exp 0212's `mem0212.py`, read-only through `/proc/<pid>/mem`.
  - Each read is 0x1860000 bytes per buffer: 26 × 15 blocks of 64 KiB.
  - Reads went to `~/bc5-data/priv/exp0248` (mode 700).
- **De-swizzle.** As exps 0237/0240, with Mesa addrlib's patterns at 16 pipes and 4-byte elements:
  - the depth buffer uses `ADDR_SW_64KB_Z_X`: `swz0248-z4.json`, made by `gen0248.py` (exp 0240's
    generator, given the table name);
  - the G-buffer uses `ADDR_SW_64KB_R_X`: exp 0244's `swz0244-4.json`.
- **Analysis (`ana0248.py`).** It works in the lake window of the patch mask: x 300–1900,
  y 400–680 of the 1920×1080 shot. For each read it reports:
  - the render width, taken as the 128-element block pitch from 1920 to 3328 with the least
    block-row shear in the G-buffer;
  - the G-buffer's holes: pixels at the cleared value, 10,000 or more;
  - the depth there and elsewhere;
  - both compared with the next shot's patch mask.

  A first pass that tried widths only from 2304, in steps of 256, chose the same widths.

**Result** (`raw/H1.*`).
- **Box state.**
  - No kernel fault, timeout or reset: `H1.out` has 0 fault lines, and the stream has only 6
    routine IPv6 lines.
  - The live saves' checksum was the same before and after (f6475842373bf369).
  - Written: run directory 78 MB, journal 89 MB, reads 391 MB. The reads were deleted after the
    summary; `cap4-depth.png` stays in `~/bc5-data/priv/exp0248`.
  - Only one run was used.
- **H1's course.** Clean for ts00–ts05 (0.9–1.0 %), patched from ts06 to ts14 (3.0, 4.4, then
  5.5–11.2 %), and clean again from ts15 to ts25 (0.7–1.0 %). Reads cap1–cap8 fell after ts00, ts03,
  ts06, ts09, ts12, ts15, ts18 and ts20.
- **Complete patched reads: the G-buffer's holes are the patches.** cap3 and cap4 have G-buffer
  shear 1.19 and 1.64 at 3328×1872; the next best width scores 9.3 and 9.7.
  - cap3 against ts07: phi +0.57. 34.7 % of patch pixels are holes, against 0.1 % of the others.
  - cap4 against ts10: phi +0.70. 53.5 % of patch pixels are holes, against 0.2 % of the others.

  This repeats F299 within one run.
- **Depth in the patch cells.**
  - **cap4:** the cells hold written depth. In patch pixels p10/p50/p90 is 0.00064 / 0.00077 /
    0.00085; in the other window pixels it is ~0 / 0.00061 / 0.00081. In hole pixels the median is
    0.00079, against 0.00063 elsewhere.
    - The buffer is reverse-Z (0 is the cleared far value), so the cells hold a depth somewhat
      nearer than the median of the lake around them.
    - The step across the patch edges is only ×1.32 the window's mean step. That is a small
      offset, not a separate object far in front.
    - The two medians also mix screen positions: the patches sit in the nearer middle of the lake.
  - **cap3:** its holes hold depth 0 (98.6 %), and so does a third of the patch pixels.
  - **cap5:** a mixed read. Its G-buffer shear is 9.15 (mid-update), so its holes do not line up
    (phi −0.06). In its depth buffer the patch pixels are at depth 0 in 86.5 % of cases, against
    1.9 % of the others: phi +0.83, edge step ×12.6. So in that memory, the lake around the cells
    held written depth and the cells held 0.
- **The renders are not usable as pictures of depth.** The kept cap4 render (in priv; it and
  temporary cap5/cap2 renders were viewed on the laptop, then deleted there) was stretched from the
  1st to the 99th percentile with the words outside 0..1 left in.
  - It shows where those words are, speckled over the frame and in blobs over the near shore,
    rather than the depth relief.
  - `ana0248.py` now zeroes those words before stretching. The kept render predates that fix.
  - The clean cap2 render, which has no such words, is a smooth depth picture of the view at
    3072×1728.
- **Words outside 0..1.** Z_32_FLOAT depth cannot exceed 0..1 here, so these words are probably
  raw compressed tiles (see the caveat).
  - cap3–cap6 hold 2.9–8.2 % of their words outside 0..1, up to ±3.4e38. Those reads cover ts06–ts15,
    the patched phase and its edges. In the patch pixels the share is 0.0–0.7 %, against 3.0–3.5 %
    in the rest of the window.
  - cap1, cap2, cap7 and cap8 (ts00–ts03, ts18–ts20, all clean) hold none. Their depth is smooth,
    from 0 to 0.0187.
- **The clean reads caught the G-buffer before the lake surface.** cap1, cap2 and cap7 have 74.7–74.8 %
  of the window at 10,000 and no relation to the (≈1 %) patch mask.
  - Exp 0240 saw the same state as "drawn shore, lake not yet drawn" (67.5 %).
  - That all three clean reads, at three different widths, landed in that state is notable but
    unexplained.
  - cap8 (shear 10.7) is mixed.
- **The render size changes from frame to frame.**
  - In the journal window (t 150, clean, ts00), frames 5032–5034 draw the G-buffer at 3328×1872 and
    frames 5035–5037 at 2048×1152.
  - Both sizes use the same depth buffer address. The stencil buffer differs: 0x112b7a0000 at
    3328, 0x112a7f0000 at 2048.
  - The width finder picked 2560, 3072, 3328 and 3072 for the clean reads, and 3328 for all four
    of cap3–cap6. That is suggestive but proves nothing: frames 5032–5034 were clean at 3328.
- **Within-run journal: only the first window.** `_EVERY=15` repeated no window even with the `_PS`
  filter. The journal holds 126 draws, all at t 150.0–150.2, in the clean phase.
  - Every frame in it issues the same 20 depth writers before the full-screen draw, in the same
    order: 1 × 0x11d0a98300, 2 × 0x11d090d900, then 10 × 0x11d1d88300 and 7 × 0x11d1dd6400 interleaved.
  - All are `DRAW_INDIRECT` with colour mask 0, Z on + write with GEQUAL, and `KILL_ENABLE` 1.
  - From frame to frame 11–14 of the 20 change their indirect-argument offsets (e.g. 0x780 →
    0x7c0); the shader mix does not change.
  - There is no patched window to compare with.

**Caveat: HTILE.** The depth buffer uses depth compression. The reads are raw memory, not the
depth the DB sees: a compressed or fast-cleared tile's memory need not hold per-pixel depth, and
its HTILE word decides what the depth test uses.
- The words outside 0..1 in cap3–cap6 are taken to be such tiles. A tile that reads as 0 may be
  a cleared tile or stale memory.
- HTILE was not read, so "the cells hold depth 0" (cap3, cap5) and "nearer depth" (cap4) describe
  memory, not necessarily what the test compared against.
- The reads are not synchronised with the frame (F299's mid-frame caveat), so each one shows
  whatever point of the frame it caught.

**Verdict.**
- **In one run, the patches coincide with G-buffer holes (phi +0.57/+0.70), and under them the
  depth buffer is not plain lake.**
  - In the one complete read (cap4), the cells hold depth a little nearer than the lake around
    them. A full-screen draw testing GEQUAL against that would fail there.
  - In a mixed read (cap5), the memory held written lake depth around the cells and 0 in them.
  - Both fit the cells' depth being written by draws other than the ones that write the rest of
    the lake, or at another time. The GPU-driven, discard-capable depth-only writers
    (0x11d1d88300 / 0x11d1dd6400, 17 per frame) are the candidates. They are not shown to be the
    cause.
- **Not settled:**
  - What depth the full-screen draw itself tests with. Its vertex stage, ES 0x11d00bdf00, was not
    read.
  - Whether HTILE agrees with the memory read.
  - Whether the compressed-tile share or the render size moves with the patches. Both are
    correlations in one run, with exceptions.
- **Next:**
  1. Fix or work around `_EVERY` for filtered windows (read patch 0001's repeat logic offline),
     then journal a patched window of the same writers with their indirect-argument buffers.
  2. Read the full-screen draw's vertex output depth (its ES and constants), so the GEQUAL test
     can be evaluated against the cell depths.
  3. Optionally, a read of the HTILE base next to the depth buffer.
