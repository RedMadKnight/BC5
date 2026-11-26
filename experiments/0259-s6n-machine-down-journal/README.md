# 0259 — S6N's machine-down, read from its GPU journal: the held tail or the CS prefix?

**Question.** Exp 0254's S6N went down at 00:26 on 2026-10-24. It was the second title on the normal build `02ed5340`,
which has the held tail (ADR 0013, F312) and exp 0195's CS prefix, integrated at 00:23. The kernel stream showed
`ring comp_1.1.0 timeout`, `reset failed`, MODE1 and "VRAM is lost" (F315). The box supervisor asked four things:
- In the timed-out compute buffer, is the last packet a WAIT_REG_MEM (with its label, value and reference) or a
  dispatch?
- Does a hold release or a prefixed graphics buffer come just before it?
- What is `lockup_timeout`?
- Is the hold, the prefix or neither implicated?

**Setup.** Read-only, 2026-10-24 13:55–14:00, on the supervisor's GO after the power cycle (boot 9f3e0da8), under my
own lock line, which was released afterwards. No emulator ran.
- S6N's GPU journal, `~/bc5-data/captures/play-20261024-0024/gc/direct.log`: 416,021 lines, last written
  00:26:46.473. That is the kernel's "Dumping IP State" second, so the journal's t 142.126 s is 00:26:46.47.
- `/sys/module/amdgpu/parameters/lockup_timeout` and the parameter's own description (`modinfo -p amdgpu`). Also
  the kernel versions of the crashed boot (bac6c7e0, from 23:14:17, the boot of exp 0226's A/B) and the current
  one.
- Committed in `raw/`:
  - the journal's last 145 lines (`journal-tail.txt`);
  - every hold summary and give-up line (`hold-summaries.txt`);
  - all 33 `cs prefix (exp 0195)` lines;
  - the two TIMEOUT lines;
  - the 51 earlier runs of the hung graphics buffer's size (`dcb1813-lines.txt`);
  - `kernel-params.txt` and `crashed-boot-kernel.txt`.

**Result.**

1. **The kernel's timeout is 2000 ms for every ring.**
   - The parameter is empty, and its description reads "default: 2000 … format: [single value for all] or
     [GFX,Compute,SDMA,Video]" (`raw/kernel-params.txt`).
   - Kernel 7.2.9-ogc3.1 on both the crashed boot and the current one. CLAUDE.md's recorded 7.2.4 is out of date.

2. **What hung, in order** (`raw/journal-tail.txt`; the submission numbers are the host's):
   - t 140.079 s: acb **#163938**, 5,278 dwords, compute queue 0, went whole to the ring. It had no split and no
     "acb rest" line: all its waits were satisfied, or kept for the GPU by the ring order, when it went. It never
     completed. Before it, every compute job had completed within 2 ms.
   - The graphics ring went on: #163939, #163942 and #163948 completed at 140.081–140.086 s.
   - t 140.086 s: dcb **#163953**, 1,813 dwords, a single buffer (254 packets passed), went next on the graphics
     ring. It never completed either. A graphics buffer of that size had run 50 times before in this run without
     trouble.
   - From t 140.089 s nothing: the game thread, the ring consumer and the holder all stop writing. The last game-thread
     lines are a flip-label wait and a 2,710-dword dcb. The game thread presumably waited at the flip for GPU work
     stuck behind #163953.
   - t 142.126 s (00:26:46.47): both fences fail together, "TIMEOUT 2040.06 ms" for #163953 and "2046.60 ms" for
     #163938, when the kernel reset the ring. #163938 went 2.05 s before the kernel's comp_1.1.0 timeout, which is
     the 2000-ms limit, so it is the job the kernel names. The kernel showed 2 compute jobs unsignalled.
   - So it is the class seen before: **a graphics buffer and a compute buffer stuck together, the compute one first,
     with no fault.** The graphics job would have timed out about 7 ms after the compute one. The compute ring's reset
     failed first, and MODE1 followed before the graphics timeout was reported. So "only comp_1.1.0 timed out" does not
     mean the graphics ring ran.

3. **The last packet of #163938 is not recorded.** The run had no timeout probe: `BC5_DIRECT_TIMEOUT_PROBE` is not set
   by `play-pkg.sh`, there are no `ib-timeout-*.bin` files and no "timeout probe" lines. The journal does not record an
   acb's kept waits. The buffer lived in the title's compute queue memory (0x7f1d500ec640, a region the queue reuses:
   earlier buffers there had 845–8,577 dwords), which is gone with the process. The devcoredump the kernel created
   lived in memory and was lost in the reset.
   - So whether it stopped at a WAIT_REG_MEM or in a dispatch cannot be answered from S6N.

4. **No prefixed buffer comes near it.**
   - The prefix acted on 33 graphics buffers in the run, each one journaled (the counter in the last line is 33). The
     last was at t 139.871 s, a 31,124-dword dcb, 208 ms before #163938.
   - The graphics ring completed work for 200 ms after that, and the hung #163953 was not prefixed.
   - The prefix acts only on graphics buffers that dispatch before they set a program. It does not touch compute
     buffers, and the first ring to hang was compute.

5. **The held tail at the time.**
   - 9,129 holds by t 140.089 s: 8,285 released with the writer on a ring, 843 satisfied, 1 given up. The give-up came
     at t 115.4 s, after 217 ms, on 0x12004b3c38 (F262's label), 25 s before the hang, so it was no precursor. The
     holds' rate was ~65 a second all run.
   - The per-hold lines are sampled (the first 20 holds and every 64th; the first 50 releases and every 64th), so
     whether a hold was released in the ms before t 140.079 s is not recorded.
   - No hold was given up during the 2 s of the hang. A chain held for its bound (100 ms) would have produced one,
     unless its owner sat inside `Direct::submit` the whole time.
   - The hold acts only on the game thread's graphics buffers (`two_rings` requires `dcb`). The compute buffer that hung
     first went from the ring consumer, a path the hold does not touch (ADR 0013 point 10 is not done).
   - A held chain's label writes are registered as pending only when it is actually submitted (`register_label_writes`
     after the ioctl). So no compute wait can be kept for the GPU on a write that a held chain still holds back.
   - The 2,049-wait sample of the two-ring path shows 0 "not served". The old give-up precursor of F262 (a "NOT
     served" wait and a cpu-wait "GIVEN UP" 29–71 ms before) is absent; there is no cpu-wait line in the whole
     journal.

**Verdict.** Neither the held tail nor the CS prefix is implicated. The cause stays open, because the packet that hung
the compute ring was not recorded.
- **Same class as before, and older than both switches.** The machine-downs of 2026-10-22 have the same signature: a
  graphics buffer and a compute buffer stuck together at 2 s, no fault, a ring reset that fails, MODE1. They are
  F250's 07:44, F256's (exp 0198 arm A, with the prefix only journaled), F260's 14:50 (with PRT) and F262's 13:41 and
  16:36. All came before the held tail (integrated 2026-10-24 00:13) and the prefix (00:23).
  - In F260 the compute ring also timed out first, but its reset succeeded and the graphics ring's failed. In S6N the
    compute ring's own reset failed, and MODE1 came before the graphics timeout. With one 2000-ms limit for every
    ring, which ring reports first depends on when each stuck job started.
- **The prefix: excluded with high confidence.** No prefixed buffer in the 208 ms before; graphics buffers only; and
  the ring that hung first was compute.
- **The hold: not implicated, medium confidence.** It cannot keep a compute wait on held work, the compute buffer did
  not go through it, and the class occurs without it. What is not recorded is whether a hold release came just before.
  So a timing effect, the held tail letting the title submit in a different order, cannot be excluded by S6N alone.
- **The F262 precursor (given-up waits) is gone.** The held tail removed it, and the machine-down happened anyway. So
  the given-up waits were not this class's cause either: F263 had already shown that they are a race, not a GPU wait.

**Next step.** Record the stuck packets in the next machine-down instead of bisecting by machine-downs:
- In the second title's test runs, set `BC5_DIRECT_TIMEOUT_PROBE=1`. Its copy of each IB costs about 11 MB/s of memcpy
  at S6N's 2.8 M dwords/s.
- Stream the GPU journal (`tail -F direct.log`) to the laptop with the kernel stream. The dumps on the box are lost in
  the reboot; F262's probe lines survived only in a stream.
- But the probe as it stands would not catch a stuck acb (pointed out by the compute session, checked in
  `timeout_probe`):
  - its dump (`ib-timeout-*.bin`) is written with `fopen`/`fwrite`/`fclose` and no fsync, so a machine-down loses it,
    as in F260 and F262;
  - its journal lines decode only draw packets and the state before them, so for a compute buffer the streamed
    journal would hold the dump's name and little else.
- It needs a small diagnostic change, under the same switch:
  - fsync the dump;
  - journal, as text, each WAIT_REG_MEM of the timed-out buffer (offset, label, function, reference, mask, the
    label's value now and whether the host kept it for the GPU) and each dispatch's offset and program.

  With the journal streamed, that shows whether the compute buffer waits, and on what, and what the graphics buffer
  waits for. Where the CP stopped inside the buffer would still need the hung queue's read pointer: the kernel's
  devcoredump (TODO(verify): whether gfx10's IP dump has the compute queue's IB read pointer, and whether a user can
  read it without a new sudoers line).
- A bisect by switch would need several machine-downs (power cycles) for one comparison; this class came once in
  137 s here and once in 1,155 s in F260.
- Keep both switches as they are for that run, so that it reproduces S6N.
- The safe mode `BC5_DIRECT_HOLD_TAIL=2` is prepared (outside the repo, in the tcp session's notes, not built). It is
  only worth building if the probe shows a compute wait whose writer is behind a held graphics wait.
