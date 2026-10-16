# 0133 — ASTRO BOT's geyser: the two sides of its cycle come from different compute queues; a 4 ms two-ring limit gives 32–34 fps

**Question.**
- Experiment 0132 found the geyser to be a cycle. The main graphics buffer waits for counters that a
  1,332-dword compute buffer increments. A 3,624-dword compute buffer ahead of it waits for labels
  the graphics buffer writes after its own wait.
- Are the two compute buffers in the same guest queue? The console runs each queue on its own
  hardware queue, so the cycle would not block there if they are not.
- How short can the two-ring split's limit be?

**Setup.**
- BC-250 dev box, 2026-10-16 13:29–13:33, the maintainer at the geyser.
- Play shortcut `play-astro-compute.sh`: compute ring, `CROSS_RING_WAITS=all`, `RING_DEPS=acb`,
  plus for this session `BC5_DIRECT_WAIT_TRACE=1` and `BC5_DIRECT_TWO_RING_WAIT_MS=4`.
- **Host:**
  - the ring thread's timing lines carry the guest queue (`q<index>` into the registrations);
  - the trace of held-back compute buffers names it too;
  - the registrations are journaled once.
- Raw: `raw/session-1330.txt`.

**Result.**
- **Queues:**
  - the title registers 56 queues (32 with `a` = 1, 24 with `a` = 2);
  - compute buffers came from four of them: queue 32 (42,727 buffers), 40 (21,366), 38 (16,600)
    and 26 (1,020);
  - the others had two each.
- **The cycle crosses queues:**
  - the 3,624-dword buffer held back by its waits is in queue 32;
  - the 1,332-dword buffer whose counters the graphics buffer awaits is in queue 40.
- **At the geyser** (fps per 15 s from 165 s on):

  | session | setting | fps | waits given up |
  |---|---|---|---|
  | 1318 (0132) | one ring | 26–27 | 916 |
  | 1322 (0132) | two-ring limit 8 ms | 30–31 | 1,472 |
  | 1330 | two-ring limit 4 ms | **32–34** | 2,883 |

- When the writer of a split wait comes, it comes within 0.6 ms (3 sampled cases here; 0.3 ms in run
  546).
- The extra ~1,400 given-up waits at 4 ms would have been satisfied between 4 and 8 ms. That is
  ordinary compute work, not the cycle; those frames use the compute results of the frame before.
- No timeout, fault or reset.

**Verdict.**
- **The cycle is the host's, not the game's.** The two halves come from queues 32 and 40. On the
  console each blocks alone. Here one host thread and one kernel compute ring serve them in turn.
- **Four active compute queues match the four kernel compute rings** of the BC-250 (experiment
  0127). One ring per active guest queue is the next step: ADR 0009 amendment first, then the
  backend (a slot pool and fences per ring), then the host (queue → ring, and a compute wait left
  to its own ring's GPU instead of holding the host thread).
- **The limit stays at 4 ms** in both compute-ring shortcuts (maintainer's choice of the faster
  geyser). Shorter limits trade more frames on last frame's compute results for speed. With
  separate rings the limit should rarely be reached.
