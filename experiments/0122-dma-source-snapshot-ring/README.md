# 0122 — The second title's broken menu text was stale CP DMA sources; a snapshot ring fixes it at no measurable cost

**Question.**
- The maintainer sees "the scene in a strip behind" the second title's settings menus while moving
  through them. On the console its Initial Setup screen is black (the maintainer, from their PS5),
  so any scene there is a fault.
- What is it?
- Does experiment 0087's idea, copying each large `DMA_DATA` source at submission, fix it once the
  copies live in memory the GPU can reach?

**Setup.**
- BC-250 dev box, 2026-10-15, maintainer available. The second title with its play shortcut's
  settings.
- Input `raw/input506.cmd`:
  1. cross at 80 s;
  2. down ×7 to *View All Settings*;
  3. cross;
  4. down ×5 to *Visuals*;
  5. cross;
  6. then down every 2 s and up every 1.5 s.

  Nothing else is selected.
- A screenshot every second from 88 s; `shotlit.py` scores them by bright pixels per band.
- A new opt-in host detector, `BC5_DIRECT_FLIP_BRIGHT=<t0>[:<points>]`, journals jumps in the
  display buffer's share of non-black samples at each flip.
- Runs 503–505:
  - 503: Initial Setup;
  - 504: its list scrolled;
  - 505: *View All Settings* scrolled.
- **Run 506:** the path above, no snapshots.
- **The fix, 507–513.** `FilterOptions::dma_snapshot_min` (backend `Device::submit`) copies the
  source of every `DMA_DATA` that reads memory (SRC_SEL 0/3, SAS 0) of at least that many bytes,
  at submission, and points the packet at the copy. The host sets it from
  `BC5_DIRECT_DMA_SNAPSHOT=<min bytes>` (4096 here).
- Variants:
  - 507: 16 MiB buffer per job slot, GPU-uncached, every buffer kind;
  - 508: the same, CPU write-combined;
  - 509: the same, GPU-cached;
  - 510: graphics buffers (dcb) only;
  - 511: no snapshots, same binary (baseline);
  - 512: per-slot buffers from 1 MiB, grown on demand;
  - **513: one shared 64 MiB ring (one BO on every list); a copy never overwrites those of a job
    still in flight; graphics buffers only.**
- Raw: `raw/runs-506-513.txt` (frame rate per window; host and GPU time per frame, t 100–190 s;
  copy counters).
- Screenshots private.

**Result.**
- **What the maintainer saw.** Run 506, t=120 s, *Visuals > Contrast* with its preview picture on
  the right: the menu's upper text has holes and blocks filled with that picture (sky, water). The
  affected text includes "VISUALS", "GRAPHICS", "Graphics Mode", "VRR" and "HDR".
- **What it is not.** It is not the 3D scene behind a transparent layer:
  - the whole-buffer detector saw no brightening in 503–505 (Initial Setup and plain lists, 0 jumps
    over about 4,000 frames);
  - the bright frames of 506 are the options' preview pictures.
- **Cause.** It is F146's stale staging. The title uploads UI images and glyphs by CP DMA from
  rotating CPU staging. Our jobs run later than the console's, so the staging already holds the
  next upload (the preview picture) when the copy runs.

| run | snapshots | fps t 84–95 / 100–190 | host / CS / GPU ms per frame | copied | text |
|---|---|---|---|---|---|
| 506 | none | 43.6 / 39.9–41.6 | 9.30 / 2.86 / 12.69 | — | broken |
| 511 | none (same binary as 513) | 42.1 / 40.2–41.3 | 9.69 / 2.95 / 12.65 | — | — |
| 507 | per slot, all kinds | 37.6 / 34.2–35.4 | 12.44 / 4.03 / 15.31 | 28,748 (7.9 GB) | clean |
| 508–509 | as 507, WC / cached | 36.5–36.6 / 33.7–35.1 | 12.4–12.7 / 4.3 / 14.7–15.1 | 7.9 GB | — |
| 510 | per slot, dcb only | 38.7 / 35.4–36.7 | 11.75 / 4.09 / 13.52 | 5,196 (163 MiB) | clean |
| 512 | per slot from 1 MiB | 36.6 / 34.8–35.7 | 11.75 / 4.42 / 13.48 | 122 MiB, 50 left | — |
| **513** | **shared ring, dcb only** | **39.9 / 40.9–42.7** | **9.19 / 2.86 / 12.82** | **6,222 (178 MiB), 0 left** | **clean** |

- **Cost of the per-slot variants: the BO list.**
  - Up to 64 more buffers named on every submission put 1.1–1.6 ms a frame on the CS ioctl and
    0.3–0.4 ms on list creation.
  - Neither the buffers' size (512), their CPU mapping (508) nor their GPU caching (509) mattered.
  - With the single ring (513), CS time and fps are back at the baseline's.
- **The compute buffers' copies (507–509: 7.9 GB against 163 MiB for graphics buffers) are mostly
  data the GPU writes before the copy runs** (experiment 0050: tree headers before the refit). A
  copy taken at submission would freeze them before they are written, so snapshots apply to
  graphics buffers only.
- **No GPU fault or timeout in any run.**

**Verdict.**
- Passed.
- The "scene in a strip" is UI image data landing in the menu's text, from staging rewritten
  before our copy ran.
- `BC5_DIRECT_DMA_SNAPSHOT=4096` (backend snapshot ring, graphics buffers only) keeps the text
  clean at the baseline's frame rate. It can go into the second title's play shortcut, with the
  maintainer's yes.
- The Initial Setup screen's black background is correct (the console shows it too). The scene
  under it is rendered and covered, as on the console.
- Open:
  - New Game from Initial Setup hangs the GPU queue 0.3 s after the press (run 502: 26 timeouts,
    "No active waves" in the hang dump, the machine survived), so the menus after it are still
    out of reach;
  - a long play session with snapshots on.
