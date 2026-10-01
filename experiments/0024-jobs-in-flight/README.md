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

*Run 109* (21:53 and 21:55, GPU, unattended, the same two runs with the GPU clock pinned at
2000 MHz and 1000 mV by the maintainer; captures `kytyplus-20261001-2153` and `-2155`,
`raw/run109-summary.txt`):

| Title screen, 60–115 s | synchronous, 1850 MHz | jobs in flight, 1850 MHz | synchronous, 2000 MHz | jobs in flight, 2000 MHz |
|---|---|---|---|---|
| submissions, failed | 78,366, 0 | 91,046, 0 | 79,435, 0 | 94,087, 0 |
| frames per second | 43.9 | 54.0 | 44.8 | 56.3 |
| frame, ms | 22.8 | 18.5 | 22.3 | 17.8 |
| GPU time waited for, ms | 16.8 | — | 16.2 | — |
| GPU: voltage, power, highest temperature | 912 mV, 110 W, 66 °C | 910 mV, 118 W, 69 °C | 977 mV, 125 W, 73 °C | 974 mV, 143 W, 78 °C |

Eight per cent more clock gives four per cent less GPU time and 25 W more. With jobs in flight
the temperature climbs to 75 °C in the first minute and then levels off at 76–78 °C; the
governor throttles at 85 °C, so a longer run at this setting should still be watched.

*Run 110* (22:05, GPU, jobs in flight, 2000 MHz, the maintainer at the controller; capture
`kytyplus-20261001-2205`): **the design above fails past the title screen.** Title screen at
60 fps (the display's rate), loading at 46–50 fps, no failed submission in 225,928 — and from
the cutscene on the game runs in bursts: a few seconds at 58–60 fps, then nothing for ten
seconds, 79 seconds of the run with fewer than ten flips. The maintainer stopped it at 350 s.

The journal shows the mechanism. The frame's compute buffers end in a wait for the *next*
frame's label (a `RELEASE_MEM` early in the next main command buffer; F34). Synchronously that
wait blocks the doorbell consumer's thread, and only it, while the game's thread flips and
submits the next frame. With a completion thread of its own for the consumer's buffers the
wait blocked that thread instead — and the flip, which waited for *everything* in flight, with
it: the game could not submit the buffer that would have satisfied the wait. The consumer gave
up after its 10 s limit ("cross-queue wait unsatisfied"), five waits ran into their 2 s
timeouts.

A second fault of the design, found by reading rather than by a symptom: the direct mapper
replaced mappings (merged imports, views gone) while jobs that might use them were still
running; the kernel clears the page-table entries of an unmapped range at once.

Reworked:

- the doorbell consumer waits for its own jobs and runs its soft-CP pass itself, as before;
  only the game's threads queue their jobs and go on, with one completion thread;
- a flip waits for that queue only;
- before a mapping goes away or is replaced the host waits until everything queued has run
  (`Device::wait_idle`);
- replacing the device after a timeout excludes a thread still waiting on it.

For runs without anybody at the controller the emulator got `KYTY_BC5_AUTOPRESS` (patch 0001):
buttons and a shake at given seconds after start.

Map-only, both modes: 28 flips each. No GPU run of the reworked design yet.

**Verdict.** Open. At the title screen the frame shrinks to about the GPU's own time (44 to 54
fps at 1850 MHz, 45 to 56 at 2000 MHz); the first design broke the compute queue's blocking
wait in the cutscene and is replaced; the replacement has not run on the GPU.
