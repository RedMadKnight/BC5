# ADR 0013 — At a cross-queue wait, hold the buffer's tail, not the submitting thread

**Status:** proposed (2026-10-22). Nothing of it is built; it would be behind `BC5_DIRECT_HOLD_TAIL=1`,
off by default. The maintainer decides on the A/B after reading this. Hard rule 5 applies: nothing
changes without the direct path's own switches.

## Context

**What the host does today at a graphics wait** (the second title's play settings: `CHAIN=2`,
`COMPUTE_RING=0`, `CROSS_RING_WAITS=all`, `PIECES_FULL=1`, `RING_ORDER_WAITS=1`,
`TWO_RING_WAIT_MS=4`, `DCB_WAIT_MS` 8):
- The title's Render Thread calls a gc submit ioctl. The host walks the buffer on that thread
  (`submit_split`).
- At a `WAIT_REG_MEM[64]` on a label that no submitted job writes, it splits the buffer: the head
  goes to the GFX ring at once (ADR 0008's pieces, `chain_flush(1)`, ADR 0010).
- Then it polls the label on the title's thread:
  - once the label's writer is on a ring (`ring_will_satisfy`), the wait is kept for the GPU and
    the walk goes on;
  - once the label is satisfied, the walk goes on without it;
  - after the limit (4 ms two-ring poll, then `BC5_DIRECT_DCB_WAIT_MS`) it gives up: the wait is
    dropped from the stream (`self_waits_only`) and the rest goes anyway.
- The title's submit call returns only after that.

**Why that cannot work for these waits** (exp 0224, F284; the chain of exps 0219–0223, F279–F283):
- No queue's doorbell was written while the game thread sat in such a wait: 0 writes in 957 ms of
  waits, against 0.45 per ms just before them. After the give-up the first doorbell write came
  0.2–0.8 ms later (9 of 13).
- The label's writer is a compute buffer that the title rings after its graphics submit returns,
  7 of 13 give-ups. It is GPU-written (F282: 11 of 11; F283: its compute labels too). Holding the
  thread holds the writer back. The give-up releases it, and the buffer has run ahead of its data
  by then (the race of F263, the machine-down precursor of F262).
- ASTRO BOT's geyser has the same shape (exp 0133, ADR 0009 amendment of 2026-10-16). There "the
  game rings the doorbell of the counter's queue only after it has submitted the graphics buffer
  that waits for the counter". F228 found it for the second title's two-ring waits (~1.7 a frame,
  0.4 ms each).
- The ring consumer (`bc5-ring`) is held the same way, inside a compute slice's own CPU wait (5 of
  13 give-ups, 22–28 ms across the give-up). While it is held it serves no other queue.
- On the console a submit returns at once. The command processor blocks at the wait, the title's
  thread goes on and rings the compute queue, and the compute pipe writes the label.

## What has been tried, and why each failed

| | what | why it failed |
| --- | --- | --- |
| exp 0063 | Defer **all** of the game thread's submission to a host thread (`DEFER_SUBMIT`) | The heads were held too. Every label a held buffer writes reached the ring late. The compute tails waited on the CPU, or on the GPU for writers that were not there (`RING_ORDER_WAITS` counted them as pending), and timed out: 6 jobs, 3 ring resets. Its verdict: "the call cannot return before its buffer is on the ring". That is true for the part of a buffer **before** its first unserved wait. |
| exp 0071 | Leave a wait to the GPU on host memory (the flip) | The page must stay mapped, and the presentation thread's read is not bounded (> 150 ms seen). |
| exps 0133–0135 | Speculative graphics waits: kept for the GPU before the writer is submitted, plus a watchdog that writes the awaited value | The watchdog's guessed value broke the second title's semaphore protocol, and the GPU hung hard (F181). |
| today | Serve the wait on the title's thread, give up at the limit | It holds the thread that submits the writer (F284). |

## Decision (proposed)

Hold what the console's CP holds, and nothing more: the part of the graphics stream from the first
wait that cannot be served. The title's thread returns at once, as on the console.

1. **Where it applies.** A game-thread `dcb` wait on the two-ring path whose label is unsatisfied
   and whose writer is not on any ring (`ring_will_satisfy` false), after the head has been split
   off and submitted as today. Nothing changes for waits that are satisfied or kept for the GPU.
2. **The head goes, the tail is held.**
   - The head, everything before the wait, is submitted at once, as now. So every label it writes
     reaches the ring at the moment of the title's call; that is the order exp 0063 lost.
   - The tail is the buffer from the wait on, with its prefix (`full_prefix`). It goes into a hold
     queue for the GFX ring.
   - `Direct::submit` returns, and so does the title's ioctl.
3. **Later buffers queue behind the tail.** While the hold queue is not empty, every later
   game-thread buffer (the next ioctls' `cc`, `hib`, `dcb`) is appended to it whole, in order, and
   the call returns. On the console they would also be behind the blocked CP.
   - Buffers the title rewrites at once are copied at hand-over: the 3-dword `CONTEXT_CONTROL` of
     the submit header, and every buffer of up to 64 dwords, as 0063 did. 0063's stability check
     found nothing else changing before its job was done, apart from NOP payloads.
4. **A holder thread (`bc5-hold`) submits the queue.**
   - It polls the first item's wait every ~20–50 µs, with the criteria the title's thread uses now.
     When the writer is on a ring, the wait is kept for the GPU. When the label is satisfied, the
     wait is not needed.
   - Then it runs that item, and the items behind it in order, through the normal path:
     `piece_check`, `submit_split` from the wait on, the chains of ADR 0010.
   - A later item that meets its own unserved wait becomes the queue's new head item, and the holder
     goes on polling.
   - It submits with the game thread's context: completion queue 0, the game thread's chain and
     carried CP state (F209), and `on_game_thread()` true for the policy. Listing and carrying each
     thread-local value is step 1 of the plan; 0063's `defer2.py` is the starting list.
5. **Writes count as pending only when submitted.** A held buffer's label writes are registered
   (`register_label_writes`) only when it reaches a ring. So `RING_ORDER_WAITS` and
   `ring_will_satisfy` never leave another queue's wait to the GPU on a held writer. This was 0063's
   failure: its compute tails waited on the GPU for writers still in the deferral queue.
   - The ACB readiness gate then defers a compute queue that waits on a held write, as the console's
     compute queue would wait.
6. **A bound, and the old behaviour as the fallback.** If the held wait is neither satisfied nor
   its writer on a ring within `BC5_DIRECT_DCB_WAIT_MS` of the wait's start, the holder gives up
   exactly as the title's thread does today: the wait is dropped and the tail goes. That is
   journaled, so the worst case is today's. With the title's thread free it should hardly fire;
   that is a measure of the A/B. The host never writes a label, so 0135's guessed values cannot
   occur.
7. **Where the title can observe the GPU, the hold queue is drained first.** At these points the
   calling thread blocks until the holder has emptied the queue, or the bound expires, and then
   goes on:
   - the flip (`SubmitEopFlip` → `Direct::drain()`);
   - the gc "submit done" and "wait idle" ioctls;
   - event-queue waits;
   - `wait_jobs()` before an unmap.

   These are the points that close a held chain in ADR 0010 §B.2. By the time the title reaches
   them it has rung its compute queue, so the writer is on its ring and the drain takes a few ms.
8. **Back-pressure.** The hold queue is capped (64 items or 4 MiB of buffers). A hand-over beyond
   that blocks the title's thread until the queue shrinks, as a full ring would on the console.
9. **The soft CP and the journals.**
   - Per-buffer marks and replays stay posted behind the submitting chain's fence, in order (ADR 0010
     §B.4).
   - The DMA snapshot (exp 0122) is taken at the actual submission, as for a held chain.
   - The crash journal names held items, and their hold time on submission.
10. **The ring consumer gets the same rule.** `bc5-ring` must not be held in a CPU wait on a label
    whose writer is not on a ring.
    - The acb readiness gate and tail split already hold a queue's buffer at its first unready
      wait: the read pointer stays, and the other queues are served.
    - What still holds the consumer inside a taken slice (F284 #10–#13: 22–28 ms) is not yet
      identified, so the plan starts there. The wait, once found, gets the same treatment: split
      at the wait, the tail left in its queue, and the next poll moves on.

## Why this is not exp 0063 again

| | exp 0063 | this ADR |
| --- | --- | --- |
| what is held | every buffer, from its start | only the tail from an unserved wait, and what follows it on the GFX ring |
| the head's label writes | late, behind the deferral queue | on the ring at the title's call, as today |
| pending writes for `RING_ORDER_WAITS` | registered at hand-over: other queues waited on the GPU for absent writers | registered at submission only |
| when a held item goes | when the deferral thread got to it | when its wait's writer is on a ring, or its label is satisfied (today's criteria) |
| how often | every job (~130 a frame) | only while a give-up chain would form: 8–13 per 600 s in tcpW5–W8, each held ~2–50 ms |
| failure mode left | ring resets | today's give-up, at the same bound |

## Plan, in order of risk

1. **Offline and journal-only.** One-file test builds, as exps 0219–0224.
   - Name the consumer's in-slice CPU waits: label, writer state, duration.
   - List the thread-local state the holder must carry. The first list: 0063's `defer2.py`, the
     chain state of ADR 0010 §B.3, `t_keep_waits`, the carried CP state of F209.
   - Count how often decision 1 would apply, and how long each hold would last: the time from the
     give-up to the writer's doorbell, from exp 0224's trace.
2. **Map-only** (`Stage::MapOnly`). The hold queue and the holder run, with nothing submitted.
   Check the order of submission against today's for the same frames.
3. **GPU, outside the water and the lake, with the maintainer present.** `BC5_DIRECT_HOLD_TAIL=1`,
   the hang watcher, the devcoredump (exp 0058). One short run.
4. **A/B at the lake bench** (tcpW pattern; old launcher values), then the maintainer's play.
   Compare:
   - give-ups and the holder's fallbacks;
   - frames over 100 ms, flips/s;
   - the label flips after hand-over;
   - faults and ring resets.
5. **A long run** for the machine-down class (F262). That class had a give-up 29–71 ms before every
   case.

Each step goes to the next only after the previous one is recorded as passed.

## Risks

- **Thread context.** The host's per-thread state is wide (thread-locals of the walk, the chain,
  the filter). A value not carried makes the holder submit with the wrong state. Step 1 lists them,
  and step 2 compares the order.
- **Title memory reuse.** A held buffer's memory must stay as the title left it until the holder
  has submitted it. 0063 found that true for jobs until done (condition 1). A title that reuses a
  buffer after a submit returns but before the GPU can have seen it would break the console's own
  rules; the observation points (7) cover the documented ones. 0063's stability check
  (`BC5_DIRECT_IB_STABLE_CHECK`) runs alongside in steps 3–4.
- **A title thread spinning on memory** that a held buffer writes, without calling the host. On
  the console the CP would hold those writes too, so the title cannot rely on them. The bound (6)
  caps the hold anyway.
- **Ordering against the ring thread's own submissions.** Exp 0134 found no ring dependency is
  needed once the compute heads keep their waits; a held graphics tail changes nothing on the
  compute ring.
- **No new GPU hang path.** No wait is left to the GPU without its writer on a ring, and the host
  never writes a label. The bound keeps today's give-up as the worst case.

## Consequences

- If step 4 passes, the given-up waits of this class go, and with them the race of F263 that came
  before every machine-down of F262. The Render Thread no longer stalls 8–100 ms at these waits.
- The 8-ms limit, the cycle break and the give-up become fallbacks of the holder, not the
  title's thread's normal path.
- `BC5_DIRECT_SPEC_WAIT_MS` (exp 0135) stays off. This is the safe form that F228 sketched and
  that exp 0135's verdict asked for: no guessed write, and no GPU wait on an absent writer.
