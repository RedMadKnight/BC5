# 0155 — the second title's menu artefacts: what they are, and fourteen host variables that do not change them

**Question.** The maintainer sees artefacts in the second title's menus when moving between
options (F179, F182: the options' preview picture landing in the highlight bar and in the text).
What exactly is drawn wrong, when, how often, and which part of the host causes it?

**Setup.**
- BC-250 dev box, 2026-10-17 20:07–22:00, the maintainer away; runs 624–628 and 650–668
  (run numbers from 650 on were reserved for this experiment; the main session kept below 650).
  Emulator build of 16:45 (experiment 0154) for runs up to 658; from run 659 a build with two
  diagnostic knobs added to the KytyPlus patch (off by default, see below).
- The route, fully scripted (`raw/exp0155v.sh`, pad script `KYTY_BC5_INPUT_CMD`): the play
  shortcut's settings, but started from a private working directory with no saves
  (`raw/play-pkg-exp0155.sh`, a copy of `play-pkg.sh` with `BC5_RUN_CWD`, `BC5_UNSET`,
  `BC5_OVERRIDE` and `BC5_EMU_PREFIX` hooks), so the title shows its first-boot *Initial Setup*
  instead of the save slots: ✕ at 80 s, down ×7 to *View All Settings*, ✕, down ×5 to *Visuals*,
  ✕, then down ×35 and up ×35 at 2 s a step (the whole Visuals list, with its previews). No ✕
  after the third, so the script can never reach New Game or Continue (F201). A screenshot every
  2 s from +94 s (88 a run, `watchNNN.sh`), kill at +270 s.
- Detector (`raw/score.py`, experiment 0130's measure): the share of colourful pixels in the menu
  list area (left 55 %, 8–70 % of the height). The settings' colour swatches give at most 0.95 %;
  a screenshot over 1 % is "flagged" and was checked by eye. One screenshot of the title screen
  before the menu (s47) is flagged in some runs and does not count.
- Runs 624–628 found the route (the save-slot screen and its ✕ = Continue, triangle = delete;
  the options are reachable without saves only through Initial Setup); 650 swept Initial Setup
  itself (down ×7 / up ×7, ten times) with the title-area diff as detector.
- Offline, on run 653's 30,000 dumped buffers (`BC5_DIRECT_IB_DUMP=1:400000:95:30000`, private):
  `raw/waitdma.py` (waits and DMA copies per buffer), `raw/labelwriters.py` (who writes the
  labels waited on), `raw/ophist.py` (opcode histogram, the packets around a position),
  `raw/dmawaits.py`, `raw/splitself.py`, `raw/loadidx.py`.
- Raw: `raw/scores.txt` (every flagged screenshot per run), `raw/journals.txt` (fps 110–260 s,
  timeouts, given-up waits, splits per run), the run scripts, `raw/watch653.log` (shot times).
  Screenshots and dumps are game output and stay private.

**Result.**

*What the artefact is.*
- The glyph cells of the menu's text carry fragments of pictures (the forest scene rendered
  under the black background, the options' preview images); letters go missing ("V SLALS",
  "IN T AL SETUP"); the thin rule under the title shows a strip of picture; the frosted highlight
  bar, now and then, a strip of the scene. Whole rows are affected together, the right-hand
  description text and the preview itself stay clean.
- It is not a per-frame flicker: once broken, a row stays broken until the title re-bakes its text
  at the next layout change — 10 s and more when nothing is pressed (run 627, screenshots 2 s
  apart identical), under 2 s while scrolling (run 660: s62 broken, s63 clean). Experiment 0130's
  "1 frame in 18" is this rate of broken bakes, not of frames.
- It needs new text: ten sweeps over the eight items of Initial Setup (run 650, 140 presses,
  nothing new drawn after the first) stayed clean; the first pass through seven new items broke
  the title in run 627 and not in run 650.

*Rate per variant* (flagged screenshots of 88, the title-screen one left out; fps at 110–260 s):

| run | variant | flagged | fps | given-up waits | splits |
|---|---|---|---|---|---|
| 653 | the play shortcut as is | 9 | 42.9 | 15 | 16,687 |
| 654 | cross-queue waits given up only after 2 s (`BC5_DIRECT_DCB_WAIT_MS=2000`, `ACB_WAIT_MS=2000`) | 5 | 42.5 | 0 | 16,476 |
| 657 | synchronous submission on one ring (`ASYNC`, `RING_ASYNC`, `COMPUTE_RING`, `CROSS_RING_WAITS`, `MAX_IN_FLIGHT` taken away) | 6 | 33.2 | 4 | 27 |
| 658 | as is, with the ranges dump and memory snapshots | 3 | 38.3 | 23 | 14,912 |
| 659 | DMA sources of compute buffers copied at submission too (`BC5_DIRECT_DMA_SNAPSHOT_ACB=1`) | 3 | 41.4 | 13 | 17,274 |
| 660 | graphics pieces off (`PIECES_FULL`, `PIECES_DRY` taken away) | 1 | 42.9 | 59 | 0 |
| 661 | pieces on, one ring | 3 | 45.7 | 5 | 26 |
| 662 | pieces' prefix without CONTEXT_CONTROL and CLEAR_STATE (`BC5_DIRECT_PIECES_NO_CLEAR=1`) | 1 | 42.3 | 10 | 16,464 |
| 663 | DMA sources copied from 64 KiB only (the 12 KiB per-frame copy left in place) | 7 | 41.9 | 11 | 16,215 |
| 664 | as is, dispatches into the staging ring journaled (`FIND_VA`) | 3 | 37.0 | 25 | 14,777 |
| 665 | as is, packets dropped as unmapped traced | 7 | 40.2 | 18 | 16,167 |
| 666 | the emulator pinned to CPUs 0–3 (`taskset`) | 4 | 32.0 | 42 | 22,312 |
| 667 | automatic AMM maps zero-filled (`KYTY_BC5_AMM_ZERO_AUTO=1`) | 3 | 42.4 | 11 | 16,543 |
| 668 | as is, draw journal of three buffers from 112 s | 4 | — | — | — |

- No run had a GPU timeout or fault. Every variant lies within one Poisson spread of the others
  (1–9 of 88, mean 4.3); none moved the rate the way a cause would (run 660's single broken
  screenshot is of the same kind as the rest).

*What the buffers show* (run 653's dumps, 243 frames):
- Every graphics-buffer DMA from memory (256) is a copy of 12,288 bytes a frame into
  0x11e0e1c200 (`RenderGpuRwLarge`), from rotating CPU staging in `RenderGpuWcLarge`
  (0x1122…–0x1124…), behind a chain of the buffer's own waits; the compute buffers copy 720,896
  bytes twice a frame into 0x11f0d1cc00 (474 copies, all behind a cross-queue wait on a label the
  graphics buffer writes). The 12 KiB destination reads 0xff over 3,062 of its 3,072 dwords with
  ten other values (a byte table). Neither copy is the glyph upload: leaving the 12 KiB one in
  place (663) or copying the compute ones too (659) changes nothing.
- The waits: 3,373 cross-queue (labels in `RenderGpuRwSmall` 0x12004b…, written by RELEASE_MEM
  of both buffer kinds) and 11,999 self-waits (WRITE_DATA sets a label to 0, a RELEASE_MEM
  FLUSH_AND_INV_DB_DATA_TS (event 43, `tools/bc5-agc/regdb/gfx10.json`) sets it to 1 at end of
  pipe, WAIT_REG_MEM waits for 1). No self-wait is ever cut from its writer by a split at a
  cross-queue wait (0 of 11,999), so the pieces cannot orphan one.
- The text is drawn into small colour targets with per-glyph scissors (CB0 256×256 with scissors
  of 8×8 to 128×128, 512×512 with 256×256, 1024×1024) — the atlas bakes — and the UI draws are
  `DRAW_INDIRECT` with `SET_BASE` before each; the tracker of ADR 0008 reads every register
  table (921 context, 177 SH, 60 UCONFIG registers; 0 unreadable).
- The only packets dropped as unmapped are the known per-frame RELEASE_MEM and WAIT_REG_MEM64 on
  the flip-label page (run 665). The automatic AMM maps the title makes in the menu (4,828 a run)
  were all zero before our zero-fill (667), and the view names behind the addresses are the
  title's own GPU heaps (`RenderGpuWcLarge`, `RenderGpuRwLarge`, `RenderGpuRwSmall`).

**Verdict.**
- Reproduced and measured: a bake of new menu text goes wrong in about 1 of 20 steps and stays
  wrong until the next bake; the wrong cells hold fragments of other UI pictures.
- Ruled out as the cause, each by a run with the variable removed and the rate unchanged: the
  game thread running ahead of the GPU (synchronous submission), the compute ring and the order
  between the rings, cross-queue waits given up, stale DMA sources of either buffer kind, the
  12 KiB per-frame copy, the graphics pieces and their prefix (with and without its
  CLEAR_STATE), packets dropped as unmapped, the host's CPU timing, and recycled memory under
  the title's automatic AMM maps.
- Not ruled out: what the bake draws read — their texture descriptors and the font or source
  images they sample — and what the title computes on the CPU before the bake. The next step is
  the draw journal of one broken bake against a clean one: the colour target and the descriptor
  tables of the draws into the 256×256 / 512×512 targets at a flagged moment, then
  `BC5_DIRECT_RT_DUMP` of those targets before and after a break. Run 668's draw journal
  (`BC5_DIRECT_DRAW_JOURNAL=112:3`) caught three small compute-only buffers, not the frame's
  main buffer; the next attempt needs more buffers or a size filter.
- The two diagnostic knobs stay in the patch, off by default: `BC5_DIRECT_DMA_SNAPSHOT_ACB=1`
  (the snapshot ring for compute buffers too) and `BC5_DIRECT_PIECES_NO_CLEAR=1` (a piece's
  prefix without its CONTEXT_CONTROL and CLEAR_STATE).
- For the maintainer: the shortcut's settings are not what breaks the menu; no setting change
  helps, so none is proposed.
