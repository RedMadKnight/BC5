# 0151 — Why the animation stream stops: not the APR waits, and serial reads change nothing

**Question.** Experiment 0150's candidates for the opening's stalled animation stream: (b) an AMPR
event the title waits for, (c) a `WaitOnAddress` command the host completes wrongly, and (c′)
the parallel APR reads (`KYTY_BC5_APR_PARALLEL=8` in the play shortcut) racing the title's
completion tickets.

**Setup.**
- Run 579's trace (`~/bc5-work/run579-stderr.log`) read again: every `wait-on-address` and
  `resumed submission` line after New Game; the host's `AprWaitSatisfied`, `RunOrderedAprCommands`
  and `PumpParkedAprBuffersLocked` (`libAmpr.cpp`).
- Run 580, 2026-10-17 10:41, maintainer away: run 579's script with a temporary
  `~/bc5-work/bc5-pkg.env` = `KYTY_BC5_APR_PARALLEL=0` (serial reads; the file removed 12 s after
  the start, the shortcut reads it only at start), the same scripted input, killed at +134 s.

**Result.**
- **(c) ruled out.** The trace prints `wait-on-address` when the title *records* the command, not
  when the host runs it. Every wait after New Game is the title's ticket protocol in one buffer:
  `write-address 0x90adf7f98 = N`, `wait-on-address 0x90adf7f98 ≥ N` (op 4), `write-address
  <status> = 3`, then the buffer's maps or reads; the wait is satisfied by the write before it. 33
  waits and 20 "resumed" lines after New Game: the other 13 were satisfied at submission and never
  parked. The last two (tickets 0x146b, 0x146c at +8 s) carry unmaps, not the stream.
- **(b) stands as unknown.** The animstrm buffer's completion was event id 1, triggered after its
  reads; ids 2 (3 times, before New Game) and 3 (never) have no visible consumer.
- **(c′) inconclusive.** With serial reads the title loaded slower, the scripted presses landed
  elsewhere (after "New Game" the trace shows `cinematic2`, `tex_sky`, `landscape`,
  `envprobes_night`, `tex_japan`, `soundbank`, …: a level or the start screen loading, black
  screenshots at +130 and +138 s), and the run was killed at +134 s. `animstrm` was again read
  exactly twice (0x3f400 + 0x3ff00) and never again. No second attempt: a mis-navigated script can
  select "Continue" and enter the game proper, which has taken the machine down.
- Host-side noise seen after New Game: 764 `[bc5-cp] event 0x40 fired but nobody is listening`
  (3,660 before it: the GPU event without a kevent listener is normal for this title), and the
  stall detector's reports for the five "File Video Stream" threads, `Save Thread`,
  `EntitlementSysPPR`, `User UDS Thread`, `UXAnalytics` (idle service threads).

**Verdict.**
- The host's APR engine is not what holds the animation stream: its waits, events and reads for the
  stream all complete. The streamer itself asks for no third chunk, so the reason is in the
  title: what it does with the two chunks it has (candidate (a): the chunk header or index the
  title checks after the read), or a GPU-written value it polls (experiment 0142's idea), or the
  cinematic clock that drives the stream's demand.
- Next, offline: find the `animstrm` reader in the title's code (the APR submission with two reads
  of 0x3f400/0x3ff00 from file id 0x628c6db3 — the call site of `sceAmprCommandBufferReadFile` for
  that id, through the event id 1 handler), and read what it does after the completion event.
  Then a run with a breakpoint or a memory watch on the chunk header, with the maintainer at the
  pad, since every opening run must end within 20 s.
- Input scripts for runs with a different loading speed need a screenshot check before each press;
  the slot list's position is not fixed in time.
