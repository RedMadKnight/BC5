# 0366 — what the render thread does "outside" the direct path at the fight

A short offline addendum to exp 0360, asked by the top session on 2026-10-28 after the merge of exp 0360 (main 382ca2f).
No box runs. The data is exp 0360's, already on main: the meter and sampler lines of the meter2 build
(`experiments/0360-fight-host-cpu/raw/M2f*-meter.txt.gz`) and its `nm` output (`raw/nm-5a00f0b8.txt.gz`). This is about
the frame rate, not the crash.

**Question.** At the maintainer's fight the render thread spends 54.4 of a 69.8-ms frame outside the direct path
(F461). How does that time split into title code, host HLE code and libraries, syscalls and page faults, and time off
a CPU? Is there a host share whose removal would shorten the fight's frame?

**Setup.**
- `split0366.pl <meter lines> <nm> <t from> <t to> [group]` reads, for a window of an exp 0360 meter run:
  - the meter (per second): the group's ms on a CPU, the ms runnable but waiting, and the rest of the second off a
    CPU (asleep or blocked); its kernel time (stime) from the meter's per-thread list; and the direct path's wall
    time on the title's threads (the meter's submit costs: sync + hints + prepare + list + cs);
  - the sampler (one RIP per 4 ms of the thread's CPU, exp 0360's `prof0360.pl` as fixed for meter2): title code (the
    guest's memory), the emulator's code, a syscall return (the timer expired in the kernel inside a syscall), the
    other libraries;
  - the window alone from the cumulative histograms: the difference of the dumps before and at the end of the window.
    Only the buckets in the run's global top lists are dumped (60 host, 40 title buckets), so these tables cover part
    of the samples. Emulator code is resolved with `nm`; title code is given as eboot.bin offsets (numbers only, base
    0x900000000 from the fault prints).
- Window: M2f t 104–146 s (exp 0360's scripted fight, F464: meter2, the job-arena fix off, the run that did not crash),
  42 meter lines, 30.4 flips/s. The crashed repeats M2f2 and M2f3 give t 104–113 as a check.
- Limitation: the scripted fight runs at ~30 flips/s, the maintainer's fight scene at ~14 (F461, F471). The meter never
  ran at his fight. The class split below is the scripted fight's. His frame is known only from the frame profiles
  (inside vs outside, wall time).

**Result.** (`split0366.pl ../0360-fight-host-cpu/raw/M2f-meter.txt.gz ../0360-fight-host-cpu/raw/nm-5a00f0b8.txt.gz 104 146 <group>`)

- **The Render Thread, per second.** The box is 33 % busy.
  - On a CPU 434 ms, runnable waiting 17, **off a CPU 549 ms**.
  - Its kernel time is 58 ms/s and its syscall samples 14.2 % of its CPU (~62 ms/s). So the kernel time is the
    syscalls, and page faults are negligible.
  - The direct path's wall time on the title's threads is 150 ms/s (244 submits/s).
- **The Render Thread's CPU by class** (4,574 samples): title code 36.8 %, the emulator's code 36.0 %, syscalls
  14.2 %, libraries 12.7 % (libc in 42 of 42 seconds' "most often").
  - **Emulator code:** the top buckets of the window (643 samples) are the direct path: `full_state::Tracker::emit_prefix`
    27.5 %, `Direct::submit_now` 21.5 %, `full_state::Tracker::apply_level` 10.4 %, `direct::Device::submit` 5.1 %,
    `state_stack::Tracker::apply_in_place` 5.0 %, then `indirect_check`, `chain_*`, `shadow_labels` and the containers
    they use. Host HLE outside the direct path (`KernelGetProcessTimeCounter`) is 0.2 %.
  - **Title code:** 322 of its ~1,680 title samples (19 %) fall in one 256-byte bucket, eboot.bin+0x3f37900. The
    rest is spread below the global top 40.
- **Per frame of the scripted fight** (33 ms at 30.4 flips/s):
  - on a CPU 14.3 ms: title code 5.3 (≥ 1.0 in that one bucket), the direct path's code 5.1, syscalls 2.0,
    libraries 1.8;
  - off a CPU 18.1 ms;
  - runnable waiting 0.6 ms;
  - the direct path's wall time ~4.9 ms.

  So the ~28 ms the frame profile would call "outside" is ~18 ms off a CPU, ~5 ms title code and at most ~4 ms of
  syscalls and libraries. The libraries and syscalls are largely the direct path's own (memcpy of IBs, the CS
  ioctl), so they are an upper bound for anything else.
- **The crashed repeats agree.** M2f2 and M2f3, t 104–113: Render on a CPU 415–416, off a CPU 567–569 ms/s; title code
  45–46 %, emulator 31–32 %, syscalls 11 %, libraries 11–12 %.
- **The threads it waits for**, in the same window:
  - **game-main:** on a CPU 592 ms/s, off a CPU 402. Title code 85.4 %, emulator 10.3 % (`TlsMainGetAddr` 53 %,
    `KernelGetProcessTimeCounter` 33 %, removed or unchanged by F470's candidates without effect), syscalls 2.8 %.
    Of its ~5,330 title samples, 2,250 fall in three buckets of the job system's wait and help paths: eboot.bin+0x3cca700
    (1,461), +0x3ccb600 (481) and +0x3f39100 (308). F448/F449 place the owner's spin there.
  - **The Hi workers:** 87.4 % title code, 2.4 % emulator, 7.2 % syscalls.
  - **The Bk workers:** 1,334 ms/s on a CPU, 99.4 % title code.
- **F482 — the render thread's time outside the direct path is the title's own: waiting and title code; no host share
  outside the direct path is there to remove.**
  - At exp 0360's scripted fight the render thread is off a CPU 55 % of each frame. Its CPU is title code (37 %), the
    direct path itself (36 %, all of the emulator's code on it), and syscalls and libc (27 %, mostly the direct
    path's).
  - Host HLE outside the direct path is under 1 % of its CPU, and page faults are negligible.
  - The threads it waits on run title code: game-main 85 %, a large part of it the job system's own wait loops; the
    workers 87–99 %.

**Verdict.**
- **The title's own code sets the frame.** The render thread's "outside" time is time it waits, off a CPU or in title
  code, plus title code. The host work on it is the direct path, which F461 already counts as "inside".
- **Nothing in the host outside the direct path would shorten the fight's frame.** The direct path itself is at most
  ~13 ms of his 70-ms frame (F461) and ~5 ms of the scripted 33-ms frame. Its largest part, `emit_prefix`, is the
  candidate C sketched in exp 0360. It is not on the frame's critical path, since the render thread then waits anyway.
- Stopped here, as asked. The split was measured on the scripted fight at ~30 flips/s. A meter play of his own fight
  scene at 14 flips/s would be needed to give the same classes for that scene.
