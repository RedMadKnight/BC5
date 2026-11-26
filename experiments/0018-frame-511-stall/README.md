# 0018 — Why the game stops after 510 frames (F42)

**Question.** On the dma-buf backing the game renders 510 frames — the loading screen, the opening
card, its first video — and then submits nothing more (experiment 0017, run 90). What is it
waiting for?

**Setup.** BC-250 dev box, 2026-10-01, kernel `7.2.4-ogc3.1.fc44`, host as of experiment 0017.
Run 91 (14:56, GPU, `KYTY_BC5_DMABUF=1`, capture `kytyplus-20261001-1456`) with two helpers
started next to it inside the `ubuntu` distrobox: `stall-dump.sh` (when the journal has been quiet
for 8 s: every thread's state from `/proc` and `gdb -batch -p <pid> -ex "thread apply all bt 18"`;
tried first on a run without submissions: 88 threads, the emulator carries on after the detach)
and `shots-loop.sh` (a screenshot every 3 s). Then, without the GPU: the loop the spinning thread
sits in, disassembled from the maintainer's own dump with the existing `guestdis.py`; the
driver library's queue table journaled by the host (`BC5_GC_QUEUE_TABLE=<address>`, `maponly`).

**Result.**

- Run 91 repeats run 90 to the frame: 7,476 submissions, none failed, **510 flips**, then
  silence. Two runs, the same count: not a race.
- The thread dump (95 threads): 31 in `PthreadCondWait`, 28 in semaphore waits, the video
  decoder waiting for a free frame buffer and the demuxer for queue space (the video is not at
  its end; the game stopped fetching frames), one thread waiting for a guest mutex — and **one
  thread running**, in guest code inside the game's own AGC driver library.
- That loop is the library's wait for free space in one of its doorbell rings: with the queue's
  ring size `n` (dwords), its own write pointer `w` and a read pointer `r` that it loads through
  a pointer in its queue table, it computes `free = r - (w mod n)`, plus `n` unless `r` is above,
  and spins with `pause` while `free <= 8`.
- The pointer it loads `r` through is, for every queue, the address right behind the ring
  (`ring end`), not the address the host has been publishing the read pointer at since
  experiment 0012 (the one named in the queue-registration call). The host never wrote there:
  `r` read 0 for ever. The two compute queues in use get 8 dwords a frame; a 4,096-dword ring
  that is never seen to drain has 8 dwords left after 511 × 8 — **the 511th frame cannot be
  queued**. The journal of the driver's table shows it: write pointer 16, 80, 144, 208, 272 at
  flips 0, 8, 16, 24, 32, read pointer 0.
- Fix: the queue consumer also stores the read pointer, as a dword offset inside the ring, in
  the dword behind the ring (`BC5_GC_NO_RING_END_RPTR=1` turns it off). Without the GPU the
  driver's table then shows the read pointer following the write pointer (pending 0 or 8).

The video had nothing to do with it; it merely started 190 frames before the 511th.

*Run 92* (15:17, GPU, with the read pointer behind the ring; capture `kytyplus-20261001-1517`):
7,497 submissions, none failed; the game passes the 511th frame — and stops two frames later,
at 513 flips, with the journal quiet and the log flooded by one thread polling its compute event
queue. The thread dump shows the host's queue consumer inside the soft CP, executing a
`WAIT_REG_MEM` out of an indirect buffer it had already served: frame 512 is where the rings wrap,
the driver writes its doorbell as an offset inside the ring, and the consumer compared it with an
absolute count — after the wrap it walked the ring's old contents over and over. Fix: the
consumer keeps its read pointer inside the ring and serves the slice between it and the doorbell
value, wrapped or not. Built, tried without submissions (before the first wrap only).

*Run 93* (15:28, GPU, pointers modulo the ring size; capture `kytyplus-20261001-1528`,
`raw/run93-summary.txt`): **14,238 submissions, none failed, 935 flips** at one every 0.084 s —
past frames 511 and 513, through the ring wraps, to the end of the game's intro video (the
player's own messages: demuxer at end of file, decoder done, video stopped; about 45 s of
video). No stall: the helper that waits for one reports the emulator exiting first.

What ends the run is the emulator, 90 s in: an access violation, a write through a null pointer
in the game's code right after the video, preceded by 124 calls into unresolved imports of a
system JSON library the host does not provide (two functions, called alternately). That is host
completeness, outside the GPU path and outside this experiment.

**Verdict (2026-10-01, 15:35).** Closed. Two host bugs behind one symptom, both from the queue
protocol being guessed in experiment 0012 and never run for more than 300 frames: the read
pointer was published where the driver library does not look, and ring pointers were compared
as absolute counts. Both fixed; the game now renders until it needs a system library the host
lacks.
