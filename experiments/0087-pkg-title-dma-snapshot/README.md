# 0087 — DMA_DATA source snapshots for the second title: the ring could not be mapped yet

**Question.** The second title uploads per-frame data by CP DMA from rotating CPU staging (F146).
Its menu text breaks with deferred flips, and the maintainer reports it also breaks while
scrolling the menu with the shortcut's undeferred flips. Does copying each large DMA source at
submission (and pointing the DMA at the copy) stop that?

**Setup.**
- Backend: `FilterOptions::dma_source` (commit 726db48, unit test).
- Host: `BC5_DIRECT_DMA_SNAPSHOT=<min bytes>`, a 64 MiB ring in guest flexible memory
  ("bc5-dma-snap"), with counters for each reason a source was not replaced.
- Runs 340–343, 2026-10-14 17:38–17:51, with the maintainer present. Settings of run 327
  (flips deferred), a fresh save directory each, and `input340.cmd`: cross at 80 s, then down,
  down, down, down, up, up, down every 3 s.
  - Run 340: the knob alone.
  - Run 341: the ring's name added to `BC5_DIRECT_EAGER_NAMES`.
  - Run 342: counters added.
  - Run 343: the ring mapped explicitly with `Device::map_userptr`.

**Result.**
- No source was replaced in any run.
  - Run 342: 8,000 calls, every source mapped, and every ring range not mapped for the GPU.
  - Neither the eager name (run 341) nor `map_userptr` (run 343, which returned false) mapped
    the ring.
- No faults and no timeouts; 23.3–24.4 fps.
- The scrolled menu (screenshots, private):
  - item texts flicker between complete and cut;
  - the description panel keeps a line of the previous item's text ("…gue including in-dialogue
    sounds…" under the next item's description).
  The text data is stale, as F146 expects.
- The maintainer: the menu background should not be black. An animated scene shows only through
  the highlighted item, so the scene is rendered but the pass that puts it behind the whole menu
  is missing.

**Verdict.** Inconclusive: the fix was never in effect. Next: carry the snapshot in memory the
direct path already maps for the job. That means the job's own IB buffer, with the copied data
behind the IB, which needs a change in `direct.cpp`. The knob stays; it does nothing while the
ring is unmapped.
