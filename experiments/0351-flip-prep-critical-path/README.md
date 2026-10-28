# 0351 — is the flip preparation on the second title's critical path?

The top session, 2026-10-28, HANDOFF Q18 step 1. The maintainer asked for "presentation without a copy" next after the
RT-on failures, "jeżeli to w miarę łatwo". Box work under the BOX-LOCK, claimed in `~/bc5-work/BOX-QUEUE` and
`~/bc5-work/exp0351/CLAIM.txt`.

**Question.** How long does the host's per-flip preparation take on the second title? It is the read and detile of
the display buffer plus the range invalidation (F129, F131 measured it on ASTRO BOT only). Does the frame wait on it,
i.e. would shortening it raise the frame rate?

**Setup.**
- One S6N run with RT on, 600 s: the shared normal build affa0c22 through the integrated launcher, using exp 0350's
  `s6n0350.sh` with `BC5_0350_SWITCHES="KYTY_BC5_FLIP_TIMING=1"` (tag Q18a, files in `~/bc5-work/exp0350/raw/Q18a-*`).
  The switch only journals, every 120 flips:
  - `bc5 flip timing`: from `VideoOutSubmitFlip` to the preparation, and the preparation;
  - `bc5 flip prepare parts`: lookup, invalidate, `PrepareFrame`;
  - `bc5 PrepareFrame parts`: acquire, render lock, `ResolveSurface` (exps 0070, 0072).
- The emulator's GFX engine time, read from `/proc/<pid>/fdinfo` every 10 s on the box (`gpu_busy_percent` is not
  supported on this APU). Kernel log streamed to the laptop.

**Result.**
- **The run passed:** 35.9 flips/s over 597 s, no crash, kernel or TIMEOUT line, live saves unchanged. One cut by the
  0349 limit at ~102 s, no plateau (`raw/Q18a-flips-per-10s.txt`).
- **The display buffer:** 3840×2160, pitch 3840, tile mode 27, guest format 50, 33,423,360 bytes. That is the same
  tiled 33-MB surface as ASTRO BOT's (F131).
- **The preparation takes 2.01 ms per flip** (178 windows of 120 flips; window means 1.70–5.06 ms, the 5.06 at the
  start). It splits into:
  - lookup: 0.01 ms;
  - **range invalidation: 0.49 ms**;
  - `PrepareFrame`: 1.51 ms, of which `ResolveSurface`, the read and detile, is 1.42 ms.
  ASTRO BOT's was 2.9 ms (F129).
- **Submit to preparation: 0.03 ms.** The kyty-gpu thread takes each flip at once, so no flip queues behind other
  host work.
- **GFX engine busy:** mean 68 % over 47 ten-second windows (min 12 %, max 87 %; `raw/F1-gfx-busy.txt`). With one
  ring this is all the title's GPU work. The GPU is not saturated, so the frame pace is set by the title's own
  threads and syncs as much as by the GPU.
- Not measured: whether the title's render thread waits on the flip's label. That label is released once the copy is
  recorded (F129), i.e. ~2 ms after the flip, while a frame is ~28 ms.

**Verdict.** The preparation is small, 2.0 ms on a thread that is idle when the flip comes, and it starts at once.
The cheap part that Q18 step 2 would remove, the range invalidation, is 0.49 ms, at most ~1.7 % of a 28-ms frame,
and only if the frame waits on it. Nothing in the run shows the frame waiting on it. The read and detile (1.42 ms)
could only go with the GPU-side detile that took the box down twice (F130). Q18 is therefore not "reasonably easy" for
a gain worth having. It is parked again, with these numbers. A definitive answer needs an A/B with an injected
delay, which is not run.
