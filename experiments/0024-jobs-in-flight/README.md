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

*Run 108* (21:37 and 21:39, GPU, unattended, two minutes each to the title screen; captures
`kytyplus-20261001-2137` and `-2139`, `raw/run108-summary.txt`). Between runs 107 and 108 the
maintainer pinned the GPU clock at 1850 MHz (governor range 1850–1850 instead of 1000–1850).

| Title screen, 60–115 s | synchronous | jobs in flight |
|---|---|---|
| submissions, failed | 78,366, 0 | 91,046, 0 |
| frames per second | 43.9 | 54.0 |
| frame, ms | 22.8 | 18.5 |
| GPU: voltage, power, highest temperature | 912 mV, 110 W, 66 °C | 910 mV, 118 W, 69 °C |

No wait of the soft CP timed out in the asynchronous run, the slowest second has 53 flips, and
the picture is the title screen as before. In the synchronous run the GPU's share of the frame
is 16.8 ms; with jobs in flight the frame is 1.7 ms longer than that.

What the pinned clock did cannot be read from this: the title screen's GPU time was 14.3–16.3 ms
in runs 101–107 under the old governor setting and is 16.8 ms now, so the old setting was
probably at its upper end already under this load.

**Verdict.** Open, with the first half answered: at the title screen the frame does shrink to
about the GPU's own time (44 to 54 fps) and nothing of the protocol breaks. Not yet run: a
level load, the cutscene, gameplay with input, and a fault with jobs in flight.
