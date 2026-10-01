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

*Run 111* (22:49, GPU, the reworked design, unattended with `KYTY_BC5_AUTOPRESS`; capture
`kytyplus-20261001-2249`): **the stall is still there, and regular.** Title screen and loading
as in run 110 (58–60 and 48 fps, no failed submission in 182,964); from the cutscene on, three
frames in 70 ms and then nothing for 12 s, over and over (203 seconds with fewer than ten
flips). The maintainer stopped it. No controller was connected during this run (the kernel log
shows its last disconnect forty minutes earlier), so the automatic presses were the only input.

What the journal and the captured buffers of run 100 show about the cutscene's frame:

- the game cycles through three frame slots, each with its own labels;
- the main command buffer waits, at its start, for a label the compute buffer writes
  (`…d40`), sets a slot label early on (`RELEASE_MEM`, `…f80` := 1), and further in waits for
  another compute label (`…dc0`);
- the compute buffer ends in a wait for that slot label (`…f80` == 1) and, past it, writes the
  labels the main buffer waits for;
- nothing in any buffer writes a label back to 0: the game's CPU code does.

On the console two queues run side by side and this is a handshake inside one frame. Here both
run on one ring and the host satisfies cross-queue waits on the CPU before a buffer is
submitted. Synchronously that works because the game's thread is held for the whole of the
main buffer's execution. With the game's thread released at once, one of the three slot labels
is 0 when the compute queue looks (`wait detail: function 3, value 0x0, reference 0x1`), its
tail is not submitted, the other two slots' tails queue up behind it, and the game stops until
the consumer's 10 s limit and the 2 s wait timeout pass. Which write is lost or overtaken — the
GPU's early `RELEASE_MEM`, or the game's CPU reset arriving after it — is not established.

**Verdict (2026-10-01, 23:05).** Failed for the game as a whole, kept off. Jobs in flight give
54–60 fps where a frame has no handshake between the queues (title screen, loading), and break
the cutscene, where it has one: the host's CPU-side emulation of cross-queue waits depends on
the game's thread being held during a buffer's execution. `BC5_DIRECT_ASYNC` stays off by
default; the synchronous path of the same build is what runs (41–47 fps). To take this up
again the labels' history around one main buffer has to be traced first.

**Addendum, run 112** (23:04, GPU, unattended, the synchronous path of the same build, automatic
presses; capture `kytyplus-20261001-2304`): 238,396 submissions in 358 s, none failed, no wait
timed out; loading at 48 fps, the cutscene at 40–41 fps, GPU at most 74 °C with the governor's
range at 1850–2000 MHz. The build's default path is what run 107 measured. (The dev box was restarted in an orderly way a few minutes after the run; not a crash.)

**Addendum, run 113: the label trace** (23:14, GPU, unattended, jobs in flight with
`BC5_DIRECT_LABEL_TRACE=1`: a thread journals every change of every address a cross-queue wait
looks at, with a microsecond time stamp; capture `kytyplus-20261001-2314`). The stall is
reproduced at 236 s, and the trace shows what the verdict above could not establish.

- Each of the three frame slots has five labels. A main command buffer, on the GPU, first
  clears the five labels of the *next* slot in the rotation and then sets its own slot label —
  all within 1.2 ms of its start. Nothing is lost and nothing arrives late: a slot label is
  simply 1 for two frames (38 ms here) and then 0 again.
- A frame's compute buffer ends in a wait for the slot label the *next* frame's main buffer
  sets. So at any time the compute queue holds up to three buffers whose tails wait for three
  different labels, each satisfied for a two-frame window.
- The host's doorbell consumer served a queue's pending entries all or nothing: if any entry's
  wait was unsatisfied, none was submitted. Synchronously the game never gets a second buffer
  into the queue before the first one's tail has gone. With the game's thread released, the
  second arrives while the first is ready, the pair is held back for the second's sake, and by
  the time the second's label is set a third has arrived; the first one's label is cleared
  again before the three are ever ready together. The consumer scans that queue only every
  20 ms or so, because it waits behind the game's long main buffer for its own small jobs.

That is a fault in the host's model of a queue, not a property of jobs in flight: a queue runs
its entries in order, and an entry whose wait is satisfied goes, whatever stands behind it.
The consumer now serves the ready entries at the front of a queue and leaves the rest
(`BC5_GC_QUEUE_ALL_OR_NOTHING=1` brings the old behaviour back). Map-only, both modes: 28
flips each. The cutscene has not been run with it.

*Run 114* (23:27, GPU, unattended, jobs in flight with the consumer serving queues in order;
capture `kytyplus-20261001-2327`, `raw/run114-summary.txt`): **237,558 submissions in 298 s,
none failed, no wait timed out, no queue held back; loading at 59–60 fps, the cutscene at
50–53 fps** (48 and 40–41 synchronously, run 112). The slowest second of the cutscene has 43
flips; the picture is the cutscene's. GPU at most 78 °C, with the governor's range at
1850–2000 MHz.

**Verdict (2026-10-01, 23:35).** Passed for what has been run: title screen, level load and
cutscene with jobs in flight, 25–30 % more frames than synchronously. The stalls of runs 110
and 111 were the host's all-or-nothing serving of a queue, exposed by the game's thread running
ahead, not the scheme itself. Still to run before it becomes the default: gameplay with a
controller, a longer session, and a page fault with jobs in flight.
