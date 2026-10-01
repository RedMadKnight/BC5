# 0024 — Jobs in flight: not waiting for every submission

**Question.** A frame is 21–24 ms, 15–17 of them the GPU's own work (experiment 0023). The host
waits for each of a frame's 14–16 jobs before it lets the game go on, so the game's work and the
host's preparation of the next buffer never overlap the GPU's. If submissions return as soon as
the kernel has queued the job, does the frame shrink towards the GPU's own time — and does the
game's label and event protocol survive it?

**Setup.** BC-250 dev box, 2026-10-01, as experiment 0023.

**Change** (`BC5_DIRECT_ASYNC=1`, off by default; needs `BC5_DIRECT_JOURNAL=min`).

- Backend: `Device::set_async` — `submit()` returns after the CS ioctl with the job's sequence
  number; `Device::finish()` waits for it. A job in flight keeps its own scratch buffer: sixteen
  of them, used in turn, each at its own address, mapped uncached like the one before (F25).
  Synchronous submission is unchanged and uses the first.
- Host: what has to follow a buffer's execution — the soft CP's pass over it (events, what the
  GPU did not execute), a ring's read-pointer publication — is a closure handed to a completion
  queue behind the buffer's jobs. Each submitting thread (the game's, through the ioctls; the
  doorbell-queue consumer) has its own queue and thread, because one buffer's pass may wait for
  what the other's writes. At most twelve jobs are in flight. A flip first waits until nothing
  is. A fence timeout is handled by the completion thread that sees it: jobs queued on the old
  device are dropped, the device is reopened as before.

**Result.**

*Map-only* (60 s; no jobs, but every soft-CP pass goes through the queues): 27 flips against 28
synchronously. A first version with one queue for both threads managed 6 — the passes waited for
each other until their timeouts — which is what the two queues are for.

No GPU run yet.

**Verdict.** Open.
