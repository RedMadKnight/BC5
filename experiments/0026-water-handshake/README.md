# 0026 — The water: a frame with two cycles between the queues, and where the frame's time goes

**Question.** In the second level the game stops at half a frame a second the moment the player
enters water (the maintainer, 2026-10-06: "wpada do wody i jest przywieszone"). Why, and what does
the host have to do about it? Alongside: with a per-frame profile of the game's thread, where
does a 22–28 ms frame go in that level?

**Setup.** BC-250 dev box, 2026-10-06, as experiment 0024 (`BC5_DIRECT_ASYNC=1`), the maintainer at
the controller from the saved game through the first level into the second and into its water;
8-core unlock confirmed (`nproc` 16, HANDOFF D13). New in the host for this experiment:
`BC5_DIRECT_FRAME_PROFILE=1` (one journal line per flip: the game thread's time inside the host
split into sync, hints, prepare, list, CS ioctl, fence, the in-flight cap, CPU-side label waits and
event waits, then the wait at the flip, the rest, and the GPU's busy time from the jobs' queue and
completion times), a consumer diagnostic (a doorbell queue deferred for more than a second says
what its first unready buffer waits for), `BC5_DIRECT_LABEL_TRACE=1` as in experiment 0024.
Captures `kytyplus-20261006-1652` (run 118) … `-1839` (run 125); `raw/` has the summaries.

**Result, the water.** Run 118's journal: from the moment the player is in the water every frame
takes 4,027 ms — the main command buffer's two CPU-side cross-queue waits (positions 115 and
~11,000) time out one after the other at 2 s each, and the compute queue 0x21 reports "deferred
4,015 ms for another queue". Run 119 (label trace, consumer diagnostic) shows the mechanism to the
millisecond:

- Outside the water the frame's compute buffer is 3,624 dwords with its cross-queue wait at
  3,575, followed by 49 dwords of label writes. The host splits it there (ADR 0005 xviii): head at
  once, tail when the label arrives.
- In the water the compute buffer is 3,825 dwords: the same wait at 3,575, then 250 dwords — seven
  `SET_SH_REG` and a `DISPATCH_DIRECT`, repeated, and a second cross-queue wait in the middle (the
  fluid simulation). The tail no longer "only signals", the host did not split, and the whole
  buffer waited for the slot label the *next* main buffer sets at position 1,588 — while that
  main buffer waits at 115 for a label the compute buffer's head writes. Each waits for the
  other; on the console the two queues run on their own pipes and the compute pipe simply blocks
  at its wait while the graphics pipe goes on.
- Run 121: splitting at any wait whose tail has no draw or dispatch does not reach the water's
  tail (it has dispatches). Run 122: splitting at every wait, with the buffer's register-setting
  packets replayed as a small job before each later segment (`acb-state`, 70 or ~1,600 dwords),
  serves the compute side — and exposes the second cycle: the main buffer waits at 11,097 (later
  frames: 18,000–20,700) for a label the fluid tail writes, and the fluid tail waits for the slot
  label this very main buffer sets at 1,588, which cannot execute because the host serves all of a
  buffer's waits on the CPU before the buffer goes to the GPU.
- Run 123: the main buffer split at an unsatisfied wait, with the same state replay, faults from
  the first frames (`0x800000005000`, a shader fetch with foreign state; 35 failed submissions in
  the first minute) and took the box down — the objection ADR 0005 recorded after run 44, met
  again. Pieces are opt-in (`BC5_DIRECT_PIECES=1`) until the replayed state is complete.
- Run 124: a cycle test (the compute queue's blocked buffer waits for a label this main buffer
  writes) fires in the ordinary handshake too and misses the geyser's variant; the frame is still
  2 s.
- **Run 125: the game thread's cross-queue waits get a limit of 8 ms (`BC5_DIRECT_DCB_WAIT_MS`)
  instead of 2 s, and a wait whose queue is blocked on a label this buffer writes, while that
  queue's buffer writes the label waited for past its own wait, is not waited for at all. 859 s,
  847,332 submissions, none failed, no 2 s timeout, no page fault; the water, its geysers and the
  rest of the level at 40–51 fps (the maintainer: playable, no hang).** 3,342 waits given up and
  5,844 cycles broken, all in the water (positions 6,290–9,230 of the main buffer); the fluid
  simulation's results reach the picture a frame late.

**Result, the frame** (`raw/run125-profile.txt`; the second level, 120–660 s, with jobs in flight
and 16 threads):

| Per frame | Value |
|---|---|
| frame | 21.4–24.1 ms (41–47 fps) |
| game thread inside the host | 6.8–8.3 ms, of which `prepare` 4.0–4.6 (the pass over a 25,000–34,000-dword main buffer), CS ioctl 1.5, sync 0.6 |
| in-flight cap, label waits, event waits | 0, 0–1.7, 0 |
| at the flip | 2.2–3.7 ms |
| outside the host (the game's own work on its render thread) | 11.8–13.3 ms |
| GPU busy | 17.1–17.9 ms of the frame, 9 jobs from the game's thread and 12 from the queues |

The GPU is busy for 75–80 % of the frame; the rest is the game's thread not having the next
buffer ready. Deferring the flip (`BC5_DIRECT_FLIP_DEFER=1`, built and checked map-only, not yet
run) can hide the 2–4 ms at the flip; the host's `prepare` pass is the next 4 ms; the game's own
12 ms are the game's. The synchronous reference (experiment 0025) stands: 18.6 ms of GPU time in
the sync measurement, 36 ms a frame.

**Verdict (2026-10-06).** The water is playable with a stopgap that is not the console's
semantics: a wait the single ring cannot serve is abandoned after 8 ms, and the fluid simulation
runs a frame behind. The host's model — every cross-queue wait served on the CPU before a buffer
goes — cannot express two queues that wait for each other mid-buffer. The way out, recorded in
ADR 0005 (xxii): pieces, with the state between them replayed from the backend's own tracking
(context registers today; SH and UCONFIG registers to be added), not from the packets. The frame
in the second level is 75–80 % GPU; the levers in the host's hands are the flip and `prepare`.
