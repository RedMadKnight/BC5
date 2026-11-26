# 0125 — Fewer submissions are not faster on the start screen: the order on the one GFX ring matters more

**Question.**
- Experiment 0124 found the GPU idle 27.5 % of the time between the second title's ~115 jobs a
  frame on its start screen.
- Do fewer submissions, or a different submission order, raise its 31 fps?

**Setup.**
- BC-250 dev box, 2026-10-15, maintainer present.
- The start screen as in 0124: play settings, New Game at 100 s.
- **Run 521:** the 2- and 16-dword buffers dumped and decoded (`bc5-agc dump`).
- **Run 522:** a new host rule leaves NOP-only buffers unsubmitted (`submit_one`). Job timestamps
  were journaled from 165 to 180 s, as in 0124's run 520.
- **Runs 523, 524:** existing settings changed one at a time:
  - 523: without `BC5_DIRECT_RING_ASYNC` (the ring thread waits for its own jobs);
  - 524: `BC5_DIRECT_MAX_IN_FLIGHT=12` instead of 24.
- The GPU clock governor (`cyan-skillfish-governor-smu`) is configured for 1850–2000 MHz.
- Raw: `raw/runs-521-524.txt`.

**Result.**
- **The small buffers, per frame:**
  - 34 compute buffers of 2 dwords, each a single NOP;
  - 18 compute and 20 graphics buffers of 16 dwords, each two `RELEASE_MEM` (a fence value, then a
    zero).

| run | change | jobs in 15 s | GPU idle | fps (start screen) |
|---|---|---|---|---|
| 520 (0124) | — | 53,982 | 27.5 % | 31.3 |
| 522 | NOP-only buffers not submitted | 35,938 | 24.0 % | 28.2–29.9 |
| 523 | ring thread waits for its jobs | — | — | 24.8–25.9 |
| 524 | 12 jobs in flight | — | — | 30.1–31.3 |

- **Without the NOP jobs** the GPU idles less and has more work (11.4 s against 10.85 s in 15 s),
  but the frame rate drops.
- **No faults or timeouts** in any run.

**Verdict.**
- Negative for fewer submissions as such. The empty compute jobs pace the ring thread: without
  them its compute work reaches the one GFX ring earlier and delays the frame's graphics.
  - The NOP rule stays opt-in: `BC5_DIRECT_SKIP_NOPS=1`.
  - Waiting for the ring thread's own jobs (523) is worse.
  - Fewer jobs in flight (524) changes nothing.
- The shortcut's settings are the best of these. The GPU clock is not the limit (the governor keeps
  1850–2000 MHz).
- What remains for a large gain is the structure itself: on the console async compute overlaps
  the graphics queue, here both share one ring. Compute is about half of the start screen's GPU
  time (0124).
- Candidates:
  - submitting the graphics frame's critical buffers ahead of queued compute (a priority order
    on the one ring);
  - a separate compute queue (ADR 0005 keeps it out after earlier hangs; only with the
    maintainer present).
