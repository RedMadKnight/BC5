# 0201 — The night lake's checkerboard: the shared zero buffer, and the water's own draw

**Question.** Exp 0197 (F258) found that the lake's patches are added during a run, and exp 0199
(F257) found that every hole of a learned window, the AMM window included, is backed by one
shared 2 MiB "zero" buffer that does not stay zero. Is that buffer what the water reads where its
surface goes missing? Which draw is the water, and is a missing cell a sub-draw whose count went
to zero, or a sub-draw that reads bad data?

**Setup.**
- BC-250 dev box, 2026-10-22 14:34–16:37. Kernel as in exp 0197 (7.2.9-ogc3.1), not re-read.
  Runs X1–X4 were granted one at a time by the top session (the box supervisor) and held
  `~/bc5-work/BOX-LOCK` while they ran.
- The exp 0194 bench: the maintainer's lake save from a private copy (`~/bc5-work/exp0194/wd`,
  `run-0194b.sh`, `play-pkg-0194.sh`); the live saves are never read or written. The exp 0197
  diagnostic build (`~/bc5-work/exp0197/kyty_emulator`, 14:23:36): indirect-draw arguments in the
  draw journal, and the live drop list `BC5_DIRECT_DROP_PS_FILE` (exp 0197 README).
- `bench0201.sh <tag> [secs]`: exp 0197's bench script with the box lock (taken at the start,
  released when its emulator exits) and a series of `SERIES` shots `STEP` s apart in the frozen
  view, each scored by exp 0197's `patch0197.py` (clean 1–2 %, patchy 15–25 %). For slower starts:
  `ROUTE` (the title-press file; `interactive-110.cmd` presses at 110 s instead of 60 s),
  `SLOTWAIT` (title press to slot list, default 5 s) and `LOADWAIT` (load to the Parry prompt,
  default 60 s). Switches go in `ENVX`; `BC5_EMU` picks the binary.
- `wd0201.py`: per draw-journal window, a multi-draw's count and its zero-count sub-draws. Written
  for exp 0197's multi-draw candidate; not needed once the water turned out to be direct draws.
- `x3scan.py`: dispatches whose user data hold a water texture's descriptor, and AMM trace lines
  inside the textures' address ranges.
- Runs:
  - X1 (15:42): `BC5_DIRECT_AMM_PRT=1` plus a learned-fault file without its 9 AMM windows
    (`~/bc5-work/exp0197/learned-noamm.txt`, 93 entries, a fresh copy per run through
    `BC5_0197_LEARNED` in the private launcher). The AMM window is then PRT pages (reads 0, writes
    dropped; exp 0102), and no shared buffer backs any of it. Live drops of the frozen view's
    G-buffer pixel shaders.
  - X2 (15:55): launcher defaults, `BC5_DIRECT_DRAW_JOURNAL_PS=11d01d7100,11d01ff900` (user data
    and tables of the two water shaders).
  - X3 (16:12): launcher defaults, `BC5_DIRECT_DISPATCH_JOURNAL=1`, `KYTY_BC5_AMM_TRACE=1`.
  - X4a–c (16:22–16:37): `KYTY_BC5_APR_PARALLEL=1 KYTY_BC5_APR_SYNC=1` (one package read at a
    time on the submitting thread, the paths before exps 0112/0156).

**Result** (`raw/`).
- **Observed in exp 0199's watched PRT run** (`raw/prt-run-observation.txt`): with
  `BC5_DIRECT_AMM_PRT=1` alone, the 9 learned AMM windows still backed by the shared buffer, the
  patchwork comes and goes within tens of seconds in live play. Near the shore it is a regular
  every-other-cell checkerboard. PRT alone does not remove it.
- **The shared zero buffer is not the cause** (X1, `raw/X1-X2.txt`). With PRT on and no shared
  buffer anywhere in the AMM window, the frozen view scored 6.6–21.7 % in 24 shots over 2 min,
  mostly 17–22 %, as patchy as the defaults (X2: 15.4–21.0 %). The PRT window was accepted
  (rc 0), no learned window was added during the run, and the kernel logged no page fault and no
  timeout.
- **The water is two G-buffer draws, not exp 0197's multi-draw** (X1 live drops, 74 G-buffer
  pixel shaders of that run):
  - Dropping shaders 1–37 removed the whole water surface: the lake bed with its sunken trees and
    structures everywhere. Dropping 38–74 changed nothing (18.9 %).
  - Dropped one at a time (1–18), only two shaders changed the lake. Each turned the whole near
    lake into the flat light surface the patches show, with no detailed cell left.
  - PS 0x11d01ff900: four `DRAW_INDEX_2` of 256 indices each (index buffer 0x1210012000), ES
    0x11d0148800, present only with the lake in view.
  - PS 0x11d01d7100: `DRAW_INDEX_AUTO` of 3 vertices, a full-screen triangle into the five
    G-buffer targets, ES 0x11d00bdf00.
  - Both addresses were the same in every run seen (title screen T2/T3, L4, D1, X1, X2), unlike
    the shifting material block of exp 0197.
  - Both are direct draws with fixed counts. So a missing cell is not a sub-draw whose count went
    to zero; the surface is drawn whole and is flat where its inputs are.
- **What the water samples** (X2, gfx10 image descriptors in the shaders' user data):
  - 0x11d01ff900's pixel stage: 2048×2048 with 8 levels at 0x8492504000, and 512×512 with 7
    levels at 0x80907c4000, both in the AMM window. Also a 4×4 image at 0x11d0078000 and a buffer
    of 25,534 records of 32 bytes at 0x11e0007aa0.
  - Its vertex stage: 2048×2048 at 0x8001810000 and 512×512 at 0x8001010000, both in the AMM
    window, plus a 3328×1872 screen-size target at 0x113cb40000.
  - 0x11d01d7100's pixel stage: three buffers of 16-byte records (40, 77 and 168 records).
- **The pixel-stage textures are streamed; the vertex-stage ones are GPU-only** (X3,
  `raw/X3.txt`, `raw/X3-scan.txt`, `raw/X3-amm-water.txt`). The view stayed at the Parry prompt
  (the Photo Mode keys misfired under the heavy journal), with the lake at the frame's left edge.
  - The ranges at the pixel-stage textures are mapped by many small automatic AMM maps (prot
    0x90, mostly 16–256 KiB; `0x80907c4000` itself by one of 688 KiB) and filled by the host's
    APR package reads, `(parallel)`, 16 KiB–2 MiB each. That is a sparse texture streamed tile by
    tile.
  - The vertex-stage textures are each one automatic map, GPU-only (prot 0x30), all zero when
    mapped ("0 of 2048 pages non-zero", "0 of 512"). They are written on the GPU.
  - No compute dispatch held either texture's descriptor in its inline user data. Descriptors in
    tables in memory were not scanned, so the GPU writer of the vertex-stage textures is not found.
  - The scan counts AMM lines within 64 MiB of each base, wider than the textures, so some of the
    counted maps and reads may belong to neighbouring resources of the same streaming pool.
- **No result on APR read ordering** (X4, `raw/X4.txt`). With the old serial APR paths the title
  takes input much later (F203), and the bench's fixed waits missed it:
  - X4a and X4b loaded slot 2's town instead of the lake.
  - X4c (title press at 110 s) ended in a machine-down at 16:36:24, about 60 s after the press.
    A graphics and a compute buffer timed out together with no GPU fault line, the GFX ring reset
    failed, and the box went through a MODE1 reset ("VRAM is lost"). It was caught by the TCP
    session's kernel stream; exp 0204 has the analysis. It is the fault-less class of F256/F260.
    There, as at 13:41 and 14:50 on the default APR paths, it followed by 71 ms a graphics wait
    on label 0x12004b3c38 that the host gave up on. Nothing ties it to these switches.

**Verdict.**
- **Narrowed further, not named.** The water is PS 0x11d01ff900 (a 4 × 256-index mesh) and PS
  0x11d01d7100 (a full-screen G-buffer pass). Their counts are fixed, so a flat cell is not a
  dropped sub-draw: it is a cell whose sampled data is empty. The shared 2 MiB zero buffer of F257
  is ruled out (X1), as are, from exps 0194/0197, the GPU check, the `COND_EXEC` fallback,
  chains, DMA snapshots and the AMM zero-fill.
- **Leading reading.** The pixel stage samples two streamed sparse textures whose tiles the host
  maps (automatic AMM maps) and fills with APR package reads. A flat cell is a tile sampled while
  empty. The patches come and go in play and grow in a frozen view, so tiles change state during
  a run. The title evicts and re-streams them, and for some the data is not there when sampled.
  Three ways remain:
  1. the title never requests the tile again;
  2. the read lands late. F259 measured the same APR path seconds to minutes behind during
     streaming bursts;
  3. the host's CPU copy lands, but the GPU keeps stale lines of the page's earlier content.
- **Next.**
  1. Tell (3) from (1)/(2) without a new GPU path: in a patchy frozen view, dump the CPU side of
     the two streamed textures' mapped pages (read-only, from the running process) and compare
     the cells with the screenshot. Data present under a flat cell means stale GPU caches. Zero
     there means the read never came or came late.
  2. Retry the APR A/B (`KYTY_BC5_APR_PARALLEL=1 KYTY_BC5_APR_SYNC=1`) with
     `ROUTE=interactive-110.cmd` and longer `SLOTWAIT`/`LOADWAIT`, checking the slot shot before
     the load. Each run needs a fresh box grant, since X4c's machine-down.
  3. The cutscene session owns the APR read path (`libAmpr.cpp`, F259). A fix there is measured
     on this bench with `BC5_EMU=<its binary> bench0201.sh <tag>`, three runs against three of
     the defaults.
- Nothing of this is in patch 0001 or the shared build; the diagnostic build is exp 0197's.
