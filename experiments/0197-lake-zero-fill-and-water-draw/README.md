# 0197 — The night lake's patchwork: AMM zero-fill A/B and the water's draw

**Question.** Experiment 0194 (F255) found that the lake's flat patches are water surface the title
does not draw. Which patches is decided once per run, differently from run to run. In one run with
the automatic AMM maps zero-filled (`KYTY_BC5_AMM_ZERO_AUTO=1`) only a few remained. Does the
zero-fill remove the patchwork reliably? Which draw is the water, and what per-tile input decides
which of its patches exist?

**Setup.**
- BC-250 dev box, 2026-10-22 13:57–14:29. At 14:29 the box passed to exp 0199's watched run (the
  maintainer playing), so the run list ends there. Kernel 7.2.9-ogc3.1.
- The exp 0194 bench. The maintainer's lake save is used from a private copy
  (`~/bc5-work/exp0194/wd`); the live saves are never touched. The diagnostic binary is
  `~/bc5-work/exp0194/kyty_emulator` (12:04:59) with `input-0194.cfg` (keyboard layout off).
- `bench0197.sh <tag>` runs the bench in one go: title, slot 3, load, Photo Mode, camera. It takes
  screenshots `slot`, `game`, `v1` and `v2` (10 s apart) and prints the patch share. Switches go in
  `ENVX`.
- `patch0197.py`: the patch share, i.e. the fraction of pixels in the near-lake window
  (x 300–1900, y 400–680 of the 1920×1080 shot) with luma > 47 and blue minus red > 38. Patch
  pixels are lighter and bluer than water, and rain sparkle is white. Calibrated on exp 0194's
  frozen views:

  | exp 0194 run (switches) | patch share |
  |---|---|
  | L6 (`BC5_DIRECT_CHAIN=0`, `BC5_DIRECT_DMA_SNAPSHOT=0`), clean | 1.1 % |
  | L12 (`KYTY_BC5_AMM_ZERO_AUTO=1`), a few patches | 1.9 % |
  | L5 (defaults) | 18.2 % |
  | L8 (`BC5_DIRECT_DMA_SNAPSHOT=0`) | 21.9 % |
  | L9 (`BC5_DIRECT_CHAIN=0`) | 25.0 % |
  | L10 (`BC5_DIRECT_CHAIN=0`, `BC5_DIRECT_DMA_SNAPSHOT=0`) | 17.9–19.0 % (three shots over 21 s) |

- `ps0197.py`: per pixel shader, the draws and the meshlet counts (first argument of each single
  indirect draw) in the draw-journal windows of the frozen view. `ts0197.py`: the same per window,
  as a time series.
- Diagnostic build `~/bc5-work/exp0197/kyty_emulator` (14:23:36): exp 0194's edit plus
  `edit0197.py`, built by `build0197.py`. It is off unless its switches are set:
  - `BC5_DIRECT_DROP_PS=<hex list>` drops every draw of a graphics buffer whose pixel shader is in
    the list. The shader is tracked in the submission walk from `SPI_SHADER_PGM_LO/HI_PS` (SH
    0x8/0x9, as exp 0089's draw journal reads them). The walk follows `SET_SH_REG`,
    `SET_SH_REG_INDEX`, `LOAD_SH_REG` spans and both forms of `LOAD_SH_REG_INDEX`, as
    `bc5::full_state::Tracker` does; draws in nested `INDIRECT_BUFFER`s are not reached.
  - `BC5_DIRECT_DROP_PS_FILE=<path>` re-reads the list from a file whenever its mtime changes, so
    draws can be dropped and restored within one frozen view.
  - `BC5_DIRECT_DROP_PS_TRACE=1` journals each new pixel shader seen at a draw.

**Result** (`raw/runs.txt`).
- **The zero-fill is not the cause.** Under the launcher defaults (D1) the frozen lake stayed clean
  for the whole 60-s series: 0.6–0.9 % in 13 shots. With `KYTY_BC5_AMM_ZERO_AUTO=1` (Z1) a
  checkerboard region appeared 11 s into the frozen view (0.8 % → 7.2 %). Exp 0194's lighter L12 was
  the spread, not the switch. The planned three runs per arm were not finished (box off), but one
  clean defaults run against one patchy zero-fill run already rules the switch out as a cause.
- **Patches appear during a run, with the camera and the scene frozen.** Z1 and R1 (0.9 % → 2.9 %
  in 80 s) grew patches in Photo Mode; L10 (exp 0194) stayed at 18–19 %. This corrects exp 0194's
  "decided once per run". The layout is not fixed at the load: patches are added over time and
  then stay. In D1 none appeared in 60 s.
- **Shader addresses differ between runs** (`raw/shader-addresses.txt`). A block of the G-buffer
  materials sits 0xd00 lower in D1 than in L4 (0x11d29e9f00 → 0x11d29e9200 and four more); others
  do not move. So a drop list by address only holds for the run it was read in; hence P1/P2 dropped
  nothing. The drop path itself works: T3 dropped 0x11d1d10f00 and 0x11d1e02b00, 8,193 draws.
- **The three "lake-only" materials of exp 0194 are not lake-bed-only.** 0x11d29e9f00 is in D1's
  *clean* view as 0x11d29e9200, with 231 draws and 32k meshlets: a large G-buffer material.
- **The water candidate.** In R1's frozen view the HDR scene target (0x113d770000) receives 24
  `DRAW_INDEX_INDIRECT_MULTI` (0x38) of pixel shader 0x11d4b0df00 with 194,688 indices in all
  (`raw/R1-frozen-view-draws.txt`). That is a forward-rendered surface of many patch-sized
  sub-draws, the shape a tiled water surface would take. A second multi-draw (0x11d3ebde00, into
  0x116da40000) is another candidate. Dropping 0x11d4b0df00 live was prepared but not tested:
  the game of R1 was played with the pad and closed at the box at 14:29:28, when the box passed to
  exp 0199's watched run.

**Verdict.**
- **Narrowed further, not named.** The patchwork is not the zero-fill (nor, per exp 0194, the GPU
  check, the `COND_EXEC` fallback, chains or DMA snapshots). It builds up during a run while the
  frame is frozen, so something the GPU or the title keeps updating every frame removes water
  patches over time. It is not set once at the load.
- **A lead that fits the time-dependence (from exp 0199, F257, untested here).** Every hole of a
  learned window, the AMM window included, is backed by one shared 2 MiB zero buffer. That buffer
  stops being zero once anything writes a hole, e.g. the title's clears of its never-backed sparse
  UI surfaces. A water whose unbacked tiles should read zero, as PRT pages do on the console, would
  see more garbage the longer the run goes, differently each run. The test is one bench run with
  `BC5_DIRECT_AMM_PRT=1` (the window as PRT pages: reads 0, writes dropped; exp 0102), watched, D16,
  followed by the patch-share series.
- **Next (one parked run, about 20 min, after exp 0199's watched run).** Run `bench0197.sh` with
  `BC5_DIRECT_DROP_PS_FILE`, read the run's addresses from its journal (`ps0197.py`), and drop the
  candidates live: 0x11d4b0df00 (that run's address), then 0x11d3ebde00, then the G-buffer
  materials in halves. When the water draw is known, journal its multi-draw's per-draw arguments
  (count, per-sub-draw index counts and offsets) in a clean and in a patchy frame. A patch that
  vanishes is then either a sub-draw whose count went to zero (a GPU-written list) or a sub-draw
  that is present but reads missing data; the producer follows from that.

