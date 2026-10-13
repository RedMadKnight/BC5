# 0063 — taking the submission off the game's thread: the buffers allow it, the cross-queue order does not

**Question.** Experiment 0062 left the next lever in our code: the draw thread spends ~6 ms a frame
inside the host (prepare, CS, waits). Can that work move to a thread of our own, so that the
game's thread only hands the buffer over?

There are two conditions:
1. The game must leave a buffer's packets alone until its job is done, because the filter would
   read them later.
2. The order the jobs reach the single ring must still serve the cross-queue waits.

**Setup.** Host knobs (patch 0001):
- `BC5_DIRECT_IB_STABLE_CHECK=1`: every job's buffer and nested buffers are hashed at submission
  and again once the job is done; changes are counted.
- `BC5_DIRECT_IB_STABLE_CHECK=2`: in addition, every 32nd job keeps a copy. The changed dwords are
  located by packet, and changes inside NOP payloads are counted apart.
- `BC5_DIRECT_DEFER_SUBMIT=1`: tried and removed again; the patches are `defer.py` and
  `defer2.py` in this directory.
  - The game's threads queued `Direct::submit` and `post`. A thread of ours did the waits, the
    sync, the filter, the CS ioctl and the posts in the same order.
  - Buffers of at most 64 dwords were copied at once.
  - Header IBs (soft CP at once) waited for the queue.
  - First version: one queue for all game threads (run 287). Second: one queue per game thread
    (run 288).

ASTRO BOT with the settings of run 282 and the pad route of 0061, 2026-10-13:
- 284–286: the stability check;
- 287–288: the deferral;
- 289: a check of the build with the deferral removed.

Summaries are in `raw/runs-284-289.txt`.

**Result 1, the buffers.** Over 442,368 jobs in run 286 (title, map and the later level), 27% of
jobs change before they are done, but only in two places:
- NOP payloads: data the GPU writes into the command buffer, which the CP does not execute;
- the 3-dword CONTEXT_CONTROL buffer of the submit header, which the game rewrites at once.

Of 3,584 compared changed jobs, the 75 with a change outside NOP payloads are all that 3-dword
buffer. The packets the filter reads stay as they were until the job is done: condition 1 holds.

**Result 2, the deferral.**

| Run | waits given up at 8 ms | GPU timeouts (ring resets) | frames |
|---|---|---|---|
| 286, no deferral | 20 | 0 | 23,884 in ~600 s |
| 287, one queue | 709 | 6 jobs (3 resets) | 5,203; stuck loading after the save was chosen |
| 288, a queue per thread | 476 | 2 jobs (1 reset) | 6,308; title reached late |
| 289, deferral removed | 15 | 0 | 8,511 in ~150 s |

The given-up waits are the main graphics buffer's wait at dword 115 on its three rotating frame
labels (0060). The chain behind it, once per frame:
- graphics buffer N−1 sets its slot label;
- the compute tail waits for that label and then writes the frame label;
- buffer N waits for the frame label.

The ring order (0055) leaves such a wait to the GPU only once the writer is on the ring. With the
graphics buffers held in our queue, the writer often was not there yet:
- the compute tail waited on the CPU;
- the frame label came late;
- buffer N gave its wait up after 8 ms.

The timed-out jobs are compute tails (`acb 49`) and the jobs behind them on the one ring. Each
ended in a kernel ring reset (`ring gfx_0.0.0 timeout ... reset succeeded`, threads `bc5-submit`
and `bc5-ring`). The machine recovered every time, without a reboot.

**Verdict.** Failed, removed. Condition 1 holds, condition 2 does not. On one ring the host must
put each label's writer on the ring before anything that waits for it. That order is decided at
the moment of the game's submit call, so the call cannot return before its buffer is on the ring.
The waits on the game's thread are part of that order, not overhead.

What remains for the game's thread is making the work itself cheaper:
- the filter (1.5–1.8 ms a frame);
- the tracker (0.8);
- the CS ioctls (1.6 ms in 9 calls).

The stability check stays in the patch (off by default).
