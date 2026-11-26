# 0130 — The second title's menu still breaks now and then on one ring too: not the compute ring, not small DMA uploads

**Question.**
- In runs 529 and 531 (experiment 0129), the menu broke now and then with the compute ring on:
  - letters were missing or broken;
  - the scene, or a settings preview image, showed inside the highlight bar.
- The maintainer had also seen it in play after experiment 0122.
- Is the compute ring the cause, and which order between the rings matters?

**Setup.**
- BC-250 dev box, 2026-10-15 23:05–23:33, maintainer present, not touching the pad.
- `exp0129m.sh` (experiment 0129), with screenshots every 3 s from 95 to 200 s: 36 per run.
  - The run is the menu of run 513: Initial Setup, then Settings > Visuals scrolled down and up.
  - DMA snapshots from 4096 bytes are on (experiment 0122).
- `menubleed.py` scores each screenshot by the share of colourful pixels in the menu list area
  (left 55 % of the width, 8–70 % of the height). Menu text and bars are grey or white there.
  - The settings' colour swatches give at most 0.73 %.
  - The breakages checked by eye give 1.15–3.69 %.
  - A screenshot counts as broken above 1 %.
- Raw: `raw/runs-536-541.txt` (each run's summary and every screenshot's score).

**Result.**

| run | rings | order between the rings | fps 120–135 s | rings busy at once | broken / 36 |
|---|---|---|---|---|---|
| 540 | one | — | 43.7 | — | 2 (119 s, 173 s) |
| 541 | one, DMA snapshots from 64 bytes | — | 45.8 | — | 2 (107 s, 110 s) |
| 536 | compute ring, waits `all` | none | 41.0 | 14.7 % | 2 (110 s, 197 s) |
| 537 | the same | compute after GFX (`RING_DEPS=acb`) | 40.5 | 9.7 % | 2 (107 s, 197 s) |
| 538 | the same | GFX after compute (`dcb`) | 33.8 | 8.9 % | 2 (113 s, 155 s) |
| 539 | the same | both (one job at a time) | 32.5 | 0 % | 3 (104 s, 137 s, 161 s) |

- No run had a timeout or a fault.
- Run 541 copied as many DMA sources as run 540 (7,265 against 7,252 by the last summary line).
  The title's CP DMA has no sources between 64 and 4,096 bytes.
- The screenshots cost frame rate: run 534 (8 screenshots) ran at 49.9 fps against run 540's
  43.7 fps (36 screenshots).

**Verdict.**
- **The breakage is not the compute ring's.** It occurs on one ring at the same rate, about 1
  screenshot in 18, whatever the order between the rings.
- **It is not a DMA source below 4,096 bytes either.** Experiment 0122 removed the stale CP DMA
  staging. What remains reaches the picture another way.
- Candidates:
  - CPU-written data the GPU reads in place, with no DMA in between;
  - the compute buffers' memory-to-memory copies (experiment 0128: 79);
  - a missing wait.
- **The compute ring costs the menu little.** With screenshots, 41.0 fps against 43.7 fps on one
  ring. Its gain is on the start screen (experiment 0129).
- Next for the breakage: find the surface that the broken highlight bar reads, then who writes it,
  and when.
