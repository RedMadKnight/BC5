# 0060 — ASTRO BOT's 8 ms waits served by the ring order

**Question.** Since the queue depth of experiment 0045 (24 jobs in flight), how often does ASTRO
BOT's game thread lose time to the 8 ms limit on cross-queue waits (exp. 0026)? Does the ring order
of experiment 0055 (`BC5_DIRECT_RING_ORDER_WAITS=1`) remove it?

**Setup.** ASTRO BOT's first level with the play settings of 0046:
- `BC5_DIRECT_FLIP_DEFER=1`, `BC5_DIRECT_MAX_IN_FLIGHT=24`, `BC5_DIRECT_TS_SCALE=1.2`;
- the run script of run 221, 420 s, autopress.

Run 221 (2026-10-12 02:17) without the ring order; run 279 (2026-10-13 09:18) with it. The same
counts come from both journals: given-up waits, CPU-side wait time, and the frame profile from
380 s to 418 s (`frameprof.py`, exp. 0025). Raw output is in `raw/`.

**Result.**

| | Run 221 | Run 279 (ring order) |
|---|---|---|
| Waits given up at 8 ms | 13,378 | 1,777 |
| CPU-side wait time, all threads | 157 s | 21 s |
| Waits over 4 ms | 16,721 | 2,050 |
| Game thread inside the host per frame, mean | 12.2 ms | 4.1 ms |
| fps, 380–418 s | 57.7 | 56.4 |
| Frame median / p90 | 17.2 / 18.1 ms | 17.0 / 18.9 ms |
| Failed submissions, timeouts | 0 | 0 |

Almost every given-up wait in run 221 is the main graphics buffer's wait at dword 115 on one of
three rotating frame labels (0x400202d40, 0x400203940, 0x400201d40). The compute queue was never
blocked at the time. The label's writer is a compute job already on the one ring: the GPU runs it
first anyway. With 24 jobs in flight it does not finish within 8 ms, so the CPU-side wait was pure
loss. With the ring order about 76,000 such waits went to the GPU. The rest stayed with the old
rule.

**Verdict.** Passed for the waits: the game thread's time inside the host drops from 12.2 ms to
4.1 ms a frame, without a failure. The first level's frame rate does not change, because the GPU
is busy about 17 ms a frame (F97) and that is the limit there. The gain is CPU headroom, which
matters where the game thread is part of the limit (the second level, F65; not measured here).

The true cycle of the water (F64) is untouched: a wait whose writer is not yet on the ring still
falls back to the 8 ms rule. `bc5-run.env` now sets `BC5_DIRECT_RING_ORDER_WAITS=1`; the backup is
`bc5-run.env.before-0060`.
