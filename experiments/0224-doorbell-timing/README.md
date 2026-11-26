# 0224 — no doorbell is rung while the game thread waits: the give-up chains are made by the host

**Question.** Exp 0223 (F283) found that at a give-up the GPU work that releases the waited label B
has not been submitted yet. Two questions:
1. Does the host's ring consumer take that work late, or does the title ring its doorbell late?
2. The box supervisor's side lead: does the completion thread's timestamp rescale write into labels
   that the title and the GPU use as semaphores? It rewrites every `ts_collect()` destination as
   `value * ts_scale()`.

**Setup.**
- Diagnostic: `patch_0224.diff` against the shared tree's `bc5LleAgc.cpp` (md5 b210fa8e, unchanged
  since exp 0219). `patch0224.py` applied it on top of exp 0221's v3 source; `patch_0224-on-v3.diff`
  shows only the new part. Journal only, off by default.
  - `BC5_DIRECT_DOORBELL_TRACE=1`. A thread of its own, `bc5-dbw`, reads every registered queue's
    write pointer, the title's doorbell, every ~50 µs. The ring consumer (`queue_consumer_thread`)
    records when it takes a slice of entries, when its `Direct::submit()` of them returns, and when a
    queue's deferral starts. The events go into a ring buffer. For each given-up wait, the flip trace
    journals them from 50 ms before the give-up to its end.
  - With `BC5_DIRECT_FLIP_TRACE=1`, the timestamp rescale in the completion thread is journaled
    whenever its address is a label a wait has polled, or one of the fixed compute labels. The line
    gives the address, the values read and written, the scale, and the thread that last polled the
    label. The rewrite is unchanged: the value is read once, as before. The labels come from a
    lock-free table filled in `wait_satisfied()`.
  - Exp 0221 v3's flip trace and its counting write breakpoints on the four compute labels are
    included.
- Build: `build0224.py`. The binary is `~/bc5-work/exp0224/kyty_emulator` (the file name
  `kyty_emulator`, exp 0221's lesson), linked against the same shared objects as exp 0221 v3
  (libAmpr.o md5 d1b1ea24, after exp 0222).
- Run: `run0224.sh build|bench|extract`, attended, on the box supervisor's grant. tcpW8 is
  `bench0201.sh tcpW8 600`, 2026-10-22 22:50–23:00.
  - Switches: `WAIT_TRACE`, `FLIP_TRACE`, `FLIP_TRACE_WP`, the four labels, `DOORBELL_TRACE`, and
    the default 8-ms limit.
  - Old launcher values pinned; `AMM_PRT` absent (`raw/tcpW8-environ.txt`).
- Risk: the bench submits to `amdgpu` as every play does (F262); the diagnostic submits nothing.
- Analyses:
  - `ana0224.py`: per give-up, every consumer take paired with the doorbell write that posted it,
    and the last take before B's flip.
  - `ringer0224.py`: doorbell writes before, during and after each wait.
  - exp 0221's `ana0221b.py` and `consumer0221.py`.

**Result.** The full 600 s ran: 0 fault lines, 0 ring timeout or reset lines, 0 fence timeouts, same
boot, no new amdgpu line. Frames as before: 28.8 flips/s in the frozen view, 8 seconds with a gap over
100 ms. 13 waits were given up; every one was later satisfied, 2.3–46.7 ms after the give-up.

*No queue's doorbell is written while the game thread waits* (`raw/tcpW8-ringer.txt`).
- In the 50 ms before the 13 waits, the doorbells were written 205 times in 458 ms (0.45 per ms).
  During the waits, 957 ms in all, they were written **0 times**; at that rate ~430 were due. This
  holds for the 8–15-ms waits and for the two long ones, 35 ms (#4) and 815 ms (#6).
- After the give-up the first doorbell write came 0.2–0.8 ms later at 9 of 13 give-ups, at
  +18–21 ms at 2 more, and not at all in the window at 2.
- So the doorbells are rung by the thread that waits (the title's Render Thread, which runs our CPU
  wait inside its submit), or by something that cannot run while that thread is held.

*What B's flip came after* (`raw/tcpW8-ana0224.txt`), taking the last consumer take before the flip as
the writer's submission:

| the last take before the flip | give-ups | |
| --- | --- | --- |
| rung after the give-up (+0.5 to +25 ms), taken at once | 7 | #1, #3, #4, #5, #7, #8, #9 |
| rung and taken before the give-up; the consumer's submit of it returned after it | 5 | #2, #10–#13 |
| rung more than 50 ms before, taken 21 ms before the give-up | 1 | #6 (the 815-ms wait) |

- In the second kind the consumer is itself held inside one submit, its own CPU wait on a compute
  buffer, across the give-up:
  - #10–#13 took the slice 8.0–8.8 ms before the give-up. The submit returned 13.9–20.4 ms after
    it, 22–28 ms in all, and B flipped 0.1–3.1 ms after it returned.
  - In #2: taken −14.1 ms, returned +5.26 ms, flip +5.53 ms.
  - While it is held, no other queue's entries are taken.
- Compute labels (exp 0221's breakpoints): every covered release was again a GPU write, 4 of 4. The
  Render Thread armed each label ~12,000 times. One arming change also showed "no CPU write" at the
  change, most likely the ordering artifact of exp 0223 #3: the write is counted at the watch start.

*The timestamp rescale is not the source.* No rewrite of a `ts_collect()` destination landed on any
label a wait had polled, or on the fixed compute labels: 0 lines in 600 s. Yet the breakpoints
counted 40 CPU writes to the compute labels by `bc5-cq0`, the game thread's completion thread. Those
come from another path on that thread. The likely candidate, not checked, is the soft CP's CPU-side
execution of packets in the post callbacks. They are rare (40 against ~49,000 by the Render Thread).
Which path writes them, and what value, stays open.

**Verdict.**
- **The chains behind the give-ups are made by the host.** On the console a buffer's submit returns
  at once and the GPU waits. Here the host runs the game thread's cross-queue wait on the CPU inside
  the title's submit call, before the buffer reaches the GPU. Two consequences:
  - The Render Thread is held there, and it is the one that rings the compute doorbell whose work
    releases B. That doorbell is rung only once the wait ends. In 7 of 13 give-ups B's writer was rung
    after the give-up, mostly within 0.8 ms. Such a wait cannot be satisfied by waiting longer: the
    give-up is what releases it.
  - The ring consumer does the same with compute buffers. It runs their waits on its own thread inside
    a submit, and is held there (5 of 13). Then B's writer, already rung, is submitted only when that
    wait ends.
- **So no dynamic wait limit can find the writer in time.** A longer limit only stalls the frame. A
  shorter one gives up sooner, but then the buffer runs ahead of its data: the race of F263, and the
  precursor of the machine-downs, F262.
- **The fix is not to hold the submitting thread.** At a game-thread wait whose label is not yet
  written, submit the buffer's head, return to the title, and let a host thread submit the tail once
  the label flips. Later buffers of that ring must queue behind the tail. The consumer gets the same
  treatment: one queue's held-back buffer must not stop the others. The existing pieces
  (`pieces_full`, the acb head/tail split) cover part of the mechanism. It needs design (an ADR) and
  an A/B behind a switch, like the other changes.
- **Open:**
  - Why the 100-ms limit of exps 0207/0208 left only one give-up a run. A wait of the first kind
    should always have run into the limit. The chain may form only under the 8-ms limit's frame
    pacing; one run at 100 ms with this trace would show it.
  - Which `bc5-cq0` path writes the compute labels.
  - Whether the waiting thread rings the doorbell itself, or only blocks the thread that does. A
    write breakpoint on the doorbell slots would name the thread.
- One run, at the lake bench.
