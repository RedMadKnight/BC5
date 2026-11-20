# 0438 — F865's source: a given-up game-thread wait, not F3's case

**Question.** What caused F865, the GPU hang of u436sS3 (shared build of patch `8986853b`, 2026-11-20 00:59)? The
working hypothesis was F3's uncovered case, removed in F859. Is it that? And what source fix removes the cause, with no
recovery, no learned window and no hard stop?

**Setup.**
- Records, read-only. The top session gave GO; BOX-LOCK was held 07:50:17–07:51. The files were copied to the laptop's
  `data-0438/` and are never committed:
  - `~/bc5-data/captures/devcoredump/20261120-005901-devcd10.txt`;
  - `~/bc5-data/captures/play-20261120-0055/gc/{direct.log, ib-timeout-00165177-dcb-15678.bin, ib-timeout-00165180-acb-7775.bin}`.
- Tools (this directory):
  - `pair0438.py WAITER.bin WRITER.bin`: lists each wait of one dumped IB with the dword where the other IB writes
    the same label, and each wait of the writer on a label the waiter writes;
  - `box0438.sh`: atomic claim and release copied from exp 0436 (R35), a read-only `pack` of the records, and `build`.
- Fix: `mk0438.py` applies it to patch `bb04219b`'s `src/libs/bc5LleAgc.cpp`. The input is the tree unit `a62e8bf6…`
  (exp 0436's `bake/bc5LleAgc.cpp`); the output is unit `59a5df70…`. `k438-unit.diff` is the change. Only this unit
  changes. It is linked with the shared archive `d6638808`.
- Build: `box0438.sh build`. It pins the shared builds (normal `f345db74`, lean `6a735b81`, archive `d6638808`), the
  tree's unit and the kit's files. It compiles with each shared build's own command (`build0438.py` = exp 0436's
  `build0436.py`, unchanged) and writes `~/bc5-work/exp0438/{normal,lean}/kyty_emulator`. Nothing shared is written.
- Test: `chain0438.sh` (exp 0436's chain, with the private build as C and the shared normal `f345db74` as S),
  `MODE=scene`. His 09:46 scene: the read-only snapshot, slot 4, no input after the load, G+300, RT on as the title's
  settings hold it, way 2's words and `BC5_DIRECT_TIMEOUT_PROBE=1`. After each run it records, from that run's
  `direct.log`, the GIVEN UP count, the k438 lines and ho430's last 60-s line.

## Result 1: what u436sS3's records show

**F3's case is refuted.**
- The 60-s ho430 lines show "F2 cycles left as they are 0" at t 60.9, 120.9 and 180.9 s; the hang came at about
  188.7 s.
- F3 preset a stale label at a *writer's* submit, for an acb waiting on a dcb's release. Here the acb's waits were not
  the cause: see the next block.

**The acb's five dropped waits** (#165180, all 64-bit `== 0`) are a consequence, not the cause. `pair0438.py`:

| acb wait (dword) | label | written by dcb #165177 at |
|---|---|---|
| 88 | 0x12004b4bc8 | nowhere (an earlier job) |
| 2513 | 0x12004b4fc8 | nowhere (an earlier job) |
| 5712 | 0x12004b53c8 | 8637 (RELEASE_MEM, 64-bit 0) |
| 6701 | 0x12004b57c8 | 11145 |
| 7492 | 0x12004b5bc8 | 11340 |

- All five read 0 at the stall. The GFX CP had fetched up to about dword 16,000 of the 16,752-dword executed copy
  (`CP_IB1_BUFSZ` 0x2f0 left of 0x4170). That is past the dcb's three releases: the zeros of 53c8, 57c8 and 5bc8 are
  that dcb's own writes.
- The acb's junk grids are its later indirect arguments, read from memory at the stall. The acb had not reached them
  (next block). They are not evidence that it ran on junk.

**The cause: a wait the game thread gave up, in the other direction.**
- dcb chain #165177 carries a pfp `WAIT_REG_MEM64` at dword 1285: 0x12004b4c38 == 0. Its writer is acb #165180, which
  releases 0x12004b4c38 = 0 at its dword 2332.
- The probe reads the label at the stall: still 0x907616589, the busy value. "NOT met … DROPPED" for the dcb's wait,
  so the acb's release never ran.
- The game thread's journal (the "journal quiet" lines before the timeout) shows, just before the chain was submitted,
  four such waits given up in a row:

  ```
  two rings (exp 0428 split-late): dcb 1556 dwords, wait at 418 on 0x12004b3c38 still splits: no pending write
    wait detail: function 3, value 0x907616589, reference 0x0, mask 0xffffffffffffffff
  cpu-wait WAIT_REG_MEM64 at 418 on 0x12004b3c38: GIVEN UP after 20.6 ms
    indirect draw op 24 at 1466 after a given-up wait: DROPPED (1 so far)
  … at 320 on 0x12004b4438: GIVEN UP after 20.6 ms
  … at 2251 on 0x12004b4c38: GIVEN UP after 20.9 ms
  … at 321 on 0x12004b5438: GIVEN UP after 20.9 ms
  ```

  About 83 ms of the title's thread went on these. "No pending write" means the host had no writer of the label on
  any ring.
- From the timing lines: the chain #165177 was submitted at t ≈ 188.638 s and acb #165180 at t ≈ 188.658 s, 20 ms
  later. Both hit the host's 2-s fence bound (2034.7 and 2015.8 ms). The kernel then logged
  `ring gfx_0.0.0 timeout`, the reset failed and the box rebooted.
- Earlier in the run, one more wait was given up (0x12004b5438, 32.0 ms).

**What follows from the records, and what is inferred.**
- Confirmed by the records:
  - the dcb's wait on the acb's release was given up on the CPU and dropped;
  - the dcb went to the GPU without it;
  - its writer acb reached the host 20 ms after the dcb;
  - the acb's release never executed before the stall.
- Inferred, not shown: what the GFX ring hung on inside the dcb. The ME header history ends in a DRAW_INDIRECT, then
  RELEASE_MEMs; the executed copy differs from the dumped dcb (prefix, rewrites), so the packet was not mapped. Running
  ahead of the acb's work fits, as with F262's dropped indirect draw. Whether F4 fenced the acb behind the dcb (it would
  have: a pending writer, no kept wait to make a cycle) is not journaled for this acb (F4 lines are sampled).
- Why the acb came so late is not proven. The host blocks the title's thread in its submit call for up to ~21 ms per
  wait, which the console never does. If the title produces that acb on the same thread after the dcb (the 20-ms gap
  right after the last give-up fits), each wait could only be given up. That is a host-made deadlock.

**So F865 is the F262 family** ("given-up game-thread waits and the indirect draw dropped after them"), not F848/F852's
stale `== 0` on a c8 label, and not F3's case. Its frequency:

| run | cpu-wait GIVEN UP |
|---|---|
| u436sS3 | 5 |
| h430I1 | 8 |
| h430M1, M2, M3 | 0 |
| his 57-min play (F859) | 39 |

## The fix: k438 (switch `BC5_0438_KEEP`, default 1 in the test build)

The console's CP decides a `WAIT_REG_MEM` when it reaches the packet. The title's submit call returns, and the dcb
waits on the GPU until the acb's release runs.

**k438.** For a game-thread dcb wait on a label with no writer on any ring:
- mode 1: after exp 0428's 8 ms poll, the wait stays in the buffer for the GPU (`t_keep_waits`, like ring order's
  kept waits). The second 8 ms poll, the ~8 ms limit and the give-up with its dropped wait are no longer reached.
- mode 2: the wait is kept at once, with no poll.
- 0: as before.

It does not apply to the host's flip labels, or to a label outside the GPU's mappings: those take the old path, counted
as "refused".

Two guards keep the host from deadlocking on a wait the GPU now holds:
- **G1.** While a kept wait is open (not satisfied, and its label not yet written by a compute job submitted since),
  compute-ring submissions are not held by the 24-job in-flight cap. The acb that releases the label must reach its
  ring while the GFX ring waits for it.
- **G2.** F2's cycle check (no F4 fence when the writer holds a kept GPU wait on a label this buffer writes) also looks
  at every pending job ahead of the writer on its ring. F4's whole-job fence of an acb on a GFX writer queued behind a
  dcb that waits for that acb could never be met. Such a case is counted ("G2 cycles ahead") and left unfenced, as
  F2's own cycles are.

Counts (normal build only): k438 lines (the first 64 keeps, then every 1024th), and on ho430's 60-s line "kept after
the poll / at once / refused / compute past the cap / G2 cycles ahead".

**Not covered, known:**
- An acb that never comes leaves the GFX ring waiting until the kernel's timeout. This is a hang with a record, the
  same as the console would show; nothing recovers from it.
- The w428 ring move's `wait_idle(2 s)` on bc5-ring could wait on a GFX ring that waits for an acb queued behind that
  move. It is bounded at 2 s and rare (ring moves only when a queue is busy); it is not counted separately.

## Result 2: build and test

**Caveat on u438sC1: "polled reads, 60 s".** From the chain's start (08:06:19) to 08:07:15 a laptop waiter read the
box every 60 s: the boot id, a `dmesg` count, and the last two lines of the chain output. That made at most two reads,
both during the run's load. This breaks R55's "no reads during measured runs"; the top session caught it. It was
replaced by one ssh that blocks on `systemctl --user is-active chain0438s.service` and reads nothing until the unit
ends. Read u438sC1's numbers with that caveat. No other run was polled.

**Build (2026-11-20 08:04, BOX-LOCK held by 0438).**
- The test build carries both candidates, each behind its own switch (the standing rule):
  - k438;
  - exp 0437's vg437 (`mkvg437.py` `cad85761…` from branch exp/0437-q30-syncs f89c3861), folded in at the top
    session's word.
- `box0438.sh build` (k438 first, then `mkvg437.py` on private copies of the tree's `memory.cpp` `aa7d7f5b…`, `memory.h`
  `224b9fa8…` and the unit) gave these sources: unit `b68df52e…`, memory.cpp `281b18ef…`, memory.h `0b3ac45f…`.
- memory.h gains one free-function declaration only, so no other unit changes.
- Builds: private normal `d4a2f86d`, lean `1bdb1020`, 0 errors. Every warning sits on a line that was already
  there; none is in k438's or vg437's code. The shared normal `f345db74`, lean `6a735b81`, archive `d6638808` and
  tree unit `a62e8bf6` were checked unchanged after the build.

**Chain (scene, boot f813bbc0 with 0 GPU reset lines at the start, RT on, 4 rings, his 09:46 scene, G+300).**
- `ORDER="C K KV C K KV"` on the one private binary:
  - C: `BC5_0438_KEEP=0 BC5_DIRECT_VIEWS_GEN=0`;
  - K: `BC5_0438_KEEP=1 BC5_DIRECT_VIEWS_GEN=0`;
  - KV: both 1.
- The chain stopped after the second run (R55):

| run | arm | class | flips/s from G+10 | s with a gap > 50 / > 100 ms | note |
|---|---|---|---|---|---|
| u438sC1 | C | NO_CRASH | 36.91 (292 s) | 204 / 56 | polled reads, 60 s (above) |
| u438sK2 | K | **KERNEL: GPU hang at ~90 s, during the load** (before G); `gfx_0.0.0` timeout, reset succeeded, then `comp_1.1.0` timeout 2.05 s later, reset succeeded; the box stayed up | – | – | the boot now has a reset (R60) |

The chain's journal lookup found no `direct.log` for either run. It looked for the newest capture directory, but each
run's capture directory is made at its own start; to be fixed before the next chain. KV and the second cycle did not
run.

**u438sK2's hang is at k438's kept wait.**
- Records: `data-0438/K2` on the laptop (not committed). They are the run's raw files,
  `captures/play-20261120-0813/gc` (direct.log, dumped dcb #65701 and acb #65702), the fault record
  `faults/20261120-081529`, and devcd1 (gfx) and devcd2 (compute).
- The CP stopped inside dcb #65701:
  - The ME's header history, newest first, is 0x49 0x49 0x49 0x58 (0x0c) 0x46 0x9f 0x49. That matches the dcb's packets
    at dwords 318 (RELEASE_MEM), 326 (0x9f), 331 (EVENT_WRITE), 333 (ACQUIRE_MEM), 341, 349 and 357 (RELEASE_MEM).
  - The PFP's newest header is 0xc0079300, the WAIT_REG_MEM64 at dword 369 (pfp): 0x12004b5438 == 0.
  - That wait is k438's keep #11: "dcb 947 dwords keeps its wait at 311 on 0x12004b5438 … value 0x907616589, no writer on
    a ring; after the poll". The chain's segment starts at 58, and 311 + 58 = 369.
- **Its writer arrived.**
  - Acb #65702 releases 0x12004b5438 = 0 at its dword 874.
  - It went into the kernel right after the dcb ("cs 0.45 ms"; both then waited 2.04 s on their fences).
  - Every other job up to #65700 had completed by t 85.687 s.
  - At the host's 2-s probe the label already read 0. The GFX ring still timed out, and comp_1.1.0 timed out 2.05 s
    after the GFX reset.
- What fits: the acb did not run until the GFX job was ended, i.e. it had a kernel-level dependency on the waiting
  GFX job, a deadlock with the kept wait.
  - It cannot be F4: #65701 writes none of the acb's six waited labels (`pair0438.py`), and G2 counts nothing for it.
  - The candidate is amdgpu's VMID handling. The process's GPU mappings change between the two submissions
    (26943 / 26941 in the submit lines). A job on another ring that needs a VM flush cannot flush a VMID still in use
    without concurrent flushes, so it waits for that VMID's active fences, here the GFX job.
    TODO(verify): Linux `drivers/gpu/drm/amd/amdgpu/amdgpu_ids.c`, `amdgpu_vmid_grab*` and `vm_manager.concurrent_flush`
    for this ASIC; not read in this experiment.
  - Ring order's kept waits (thousands a run) never meet this, because their writer is on a ring before the GFX wait
    blocks.
- Also seen, not the hang:
  - The title's NOP marker at dword 718 of the dcb carries host journal text ("eps its wait at 6167 on 0x12004b4c38",
    from k438's 10th line).
  - The same text sits in title memory at 0x11e0450aa8, in one of the title's direct views (eager, at 0x11e0000000). The dcb's own label
    there, written 0 then 1 at dwords 728/733 and waited `== 1` at 745, reads "its wait". The ME was past it, so it was
    overwritten after.
  - Host data in guest memory points to host code writing on a guest thread's stack below the title's frames, which the
    title later reuses. It is to be checked separately.

**So k438 as built is refuted as a fix.** Keeping a GFX wait for a writer that has not been submitted deadlocks on this
host. F865's cause stands (the give-up after a late writer); its fix must not put the wait on the GFX ring before the
writer is on a ring. Proposed k438b (not built): at such a wait the dcb is split; its head goes; the tail and every
later buffer of that thread wait in a host queue while the title's submit call returns at once; when the writer acb's
writes are registered on a ring, the queued tail is submitted in order with the wait kept by ring order. There is no
give-up, no learned window and no hard stop; an acb that never comes is a bug with a record.

**On the VMID-flush candidate (read 2026-11-20 from torvalds/linux master, `amdgpu_ids.c` and `amdgpu_vm.c`, through a
fetch agent; function names only, no line numbers):**
- `amdgpu_vm_manager_init` sets
  `concurrent_flush = !(asic_type < CHIP_VEGA10 || asic_type == CHIP_NAVI10 || asic_type == CHIP_NAVI14)`. CHIP_CYAN_SKILLFISH is not named.
- `amdgpu_vmid_grab_used` never waits on another ring's fence: with a flush needed and no concurrent flush it skips
  that VMID.
- The cross-ring waits are in `amdgpu_vmid_grab_idle` (no idle VMID) and `amdgpu_vmid_grab_reserved` (a reserved
  VMID).
- So the VMID-flush dependency stands only if this ASIC has no concurrent flush and no VMID was idle, or the host
  reserves a VMID. TODO(verify): the enum position of CHIP_CYAN_SKILLFISH, and whether the backend reserves a VMID.
- Until then, what held acb #65702 back is **not known**. The finding is only the deadlock shape: a GFX wait kept on
  the ring before its writer was submitted, and that writer did not complete until the GFX job was reset.

**vg437 chain C/V (top's GO, boot f813bbc0 with 10 GPU timeout/reset lines as its baseline, `ORDER="C V C V C V"`, binary
d4a2f86d, `BC5_0438_KEEP=0` in every arm). The chain stopped after its first run at my own gate.**

| run | arm | class | flips/s from G+10 | s with a gap > 50 / > 100 ms | frames (last 290 s of the journal) over 50 / 100 ms | journal |
|---|---|---|---|---|---|---|
| u438sC3 | C | NO_CRASH | 34.10 (294 s) | 224 / 68 | 9847: 968 / 82 | GIVEN UP 2, k438 0, F4 fences 37228, F2 cycles 0; vg437 off: range table generation 452556, direct generation 228479, view builds 14666 |

- The gate (≥ 35.0 flips/s) came from u438sC1's 36.91 alone. In 0436's clean-boot scene runs the six runs ranged 33.29–35.46
  (arm means 34.30 and 34.43), so C3 is inside that spread and C1 looks high.
- The gate is the top session's to set again. V did not run.
- **Top's ruling (2026-11-20):** the C gate on this boot is ≥ 33.3 flips/s with NO_CRASH. That is the low end of
  0436's clean-boot scene range (33.29–35.46): a C run inside the spread of the same scene on a clean boot is taken as
  the box behaving normally after the reset. One C run (C1) set the old gate, and one run is no reference (R13).
  C3 (34.10) passes it.

## k438b: ADR 0013's held tail, back on the way-2 path, with no give-up

**What it is.**
- ADR 0013 (exp 0226, F312) is this design: hold the buffer's tail, not the title's thread. It was on by default from
  2026-10-24.
- Its entry points went in build W (patch `101555c7`, commit a2468923) together with the dead one-ring code. At that
  time every compute buffer ran on the GFX ring (F412). Exp 0428's way 2 brought the compute rings back without them;
  the rest of the machinery is still in the unit: `HoldCond`, `hold_release`, `hold_note_writes`, `chain_submit`'s
  gate, and the watchdog's and F10's "hold.empty()" checks.
- k438b (`mk0438b-part.py`, applied by `mk0438.py`; switch `BC5_0438_HOLD`, on in the test build unless "0") puts
  back, as of patch 4945ef1b (a2468923^):
  - `hold_keep_wait`, `hold_chain_held`, `hold_stats` and the holder thread `bc5-hold`;
  - the two call sites, on exp 0428's way-2 path before its 8 ms poll. One is the join, when the thread's chain is
    already held. The other is the hold: the head is split off and goes, the rest waits in the held chain, and the
    title's submit returns at once.
- The holder submits the chain when the label is met or its writer's writes are registered on a ring. Then the wait is
  a ring-order kept wait, whose writer was submitted before it.

**Changes against ADR 0013:**
- **No give-up.** At `hold_ns()` (100 ms) the kept wait is not dropped. The hold is journaled as a record, "STILL
  HELD", at 100 ms, at 1 s and then every 10 s, with the label's value and its pending writers. If an acb never comes,
  that is a bug with a record. There is no recovery, no learned window and no hard stop.
- **The owner does not flush a held chain at a later wait.** The two `chain_flush(1)` calls before the way-2 path skip
  it while the chain is held, so the title's thread is never held there: the F284 shape. The later wait joins the
  hold.
- **Counted:** owner flushes that did wait for a hold, with the total and longest time (observe points, size,
  ring/class). They appear in `hold_stats`' 10-s line.
- **k438 stays** behind `BC5_0438_KEEP`, now **off unless set**, refuted.

**The deadlock check the top session asked for: can the thread that submits the writer acb wait on a label the held
tail writes?**
- **Yes, the records show it.** In u436sS3, acb #165180 is the writer of the dcb's wait (0x12004b4c38 at its dword
  2332). It then waits at its dwords 5712, 6701 and 7492 on 0x12004b53c8, 57c8 and 5bc8, which that dcb releases at
  dwords 8637, 11145 and 11340: after its own wait, in the tail the hold would keep.
- **It cannot block the host, by the code.**
  - The writer acb is submitted by `bc5-ring` through `acb_ready`. At an acb wait that is not met and has no writer on
    a ring, `acb_ready` submits the head up to that wait (`submit_segment` + `chain_flush(6)`) and returns false: the
    rest stays queued. It does not CPU-wait.
  - So the head with the release at 2332 goes. Its writes are registered, and the holder releases the dcb's tail with
    its writer on a ring. The tail's releases at 8637 and later are registered in turn, and the acb's rest becomes
    ready with its waits kept by ring order.
  - In every step the writer of a GPU-kept wait is submitted before its waiter: the order k438 broke.
  - F10 skips held chains (`cs->hold.empty()`), and the watchdog skips them too, so neither bc5-ring nor the watchdog
    waits on a hold.
- **What can still wait on a hold:**
  - an observe point of the title's thread: submit-done or wait-idle ioctls, an event-queue wait;
  - a chain closed by size, ring/class change or COND_EXEC past its end.
  The first is the console's own semantics (its CP is blocked at the same wait). The second is counted, with each
  hold's records.

**Unit test.** `bash test_k438b.sh` cuts `HoldCond`, the switch and `hold_release` from the generated unit, unchanged,
and runs `test_k438b.cpp` against stubs on a fake clock. Laptop, VS clang++, 2026-11-20:
- **`BC5_0438_HOLD` unset:** PASS.
  - The writer on a ring releases the hold.
  - A met label releases it.
  - Neither, for 25 s: never released, the kept wait not dropped, 0 GIVEN UP, 4 STILL HELD records (100 ms, 1 s, 11 s,
    21 s).
- **`BC5_0438_HOLD=0`:** PASS. The old give-up happens at 100 ms.

Unit `680bda1f…`, md5s: `mk0438.py` 31ff0cbe, `mk0438b-part.py` 5f9baeca, `test_k438b.cpp` f27d1a5b,
`test_k438b.sh` 72801594. **Not yet compiled into the emulator**: the box is running the vg437 chain.

## Result 3: k438b on the box (chain `C V H HV C V H HV`, test build c4b23cd1, 2026-11-20 08:38–08:56)

Boot f813bbc0 (two resets on it by now, the top session's gate: first C ≥ 33.3 flips/s). Normal `c4b23cd1`, lean
`14b9f6e0`, built under BOX-LOCK 08:36 (k438b + vg437; sources: unit `d44a425d…` after vg437, memory.cpp `281b18ef…`,
memory.h `0b3ac45f…`); 0 errors, only the old warnings; shared builds checked unchanged.

| run | arm | class | flips/s from G+10 | s with a gap > 50 / > 100 ms | frames (last 290 s) over 50 / 100 ms | given up | k438b | vg437 line |
|---|---|---|---|---|---|---|---|---|
| u438sC5 | C (all off) | NO_CRASH (gate passed) | 34.52 | 216 / 56 | 9978: 853 / 67 | 2 | off | off: range gen 457641, direct gen 230493, view builds 15158 |
| u438sV6 | V (vg437) | NO_CRASH | 34.46 | 216 / 61 | 9947: 902 / 78 | 2 | off | ON: range gen 446702, direct gen 225852, view builds 14076 |
| u438sH7 | H (k438b) | **KERNEL: GPU hang at 113 s (load), ring reset succeeded, 77 kernel lines** | 9.3 over 107 s | – | – | 0 | 3250 holds, 2913 released with the writer on a ring, 337 satisfied, mean 19.3 ms, **longest 12,126 ms**, **15 STILL HELD records**, owner flushes that waited for a hold 25 (60.4 s in all, longest 12.1 s) | off |

**vg437:** one V against one C. View builds 14076 against 15158 (−7 %). With it ON the direct generation still moved
225852 times. The top session's ruling: no measurable gain so far, not to be run alone again.

**k438b as built is refuted.** Records copied under BOX-LOCK 08:57 to `data-0438/H7` (not committed).
- **Five 12-s holds, all the same cycle.** Each is a dcb wait on 0x12004b7838 (busy 0x907616589, "no pending write"),
  STILL HELD at 100 ms, 1 s and 11 s.
- **Its writer is queue 1/0/0's acb.** The queue journal shows it ("[bc5-q] queue 1/0/0/0x1: deferred 1.0 s … 9.0 s,
  28 dwords pending; the first unready buffer (657 / 6169 dwords) waits at 28 on 0x12004b77c8: value 0x9076d6d8c").
  The acb's very first wait, at dword 28, is on 0x12004b77c8. The release of 0x12004b7838 comes after it.
- **The release of 0x12004b77c8 sits inside the held chain.** In unheld runs (u436sS3) the same pair runs in ring
  order: "ring order: acb … keeps its wait at 0 on 0x12004b77c8" and "dcb 8222 dwords keeps its wait at 8154 on
  0x12004b7838". The dcb releases 77c8 before its own 7838 wait at its end, and the acb waits for that release.
- With k438b the chain was already held on another label when this dcb arrived. **The join** added the dcb's 7838
  wait as one more condition and took the whole dcb into the held chain, its 77c8 release included. The acb then
  could never become ready.
- This is a host-made cycle. On the console the dcb's head, release included, runs before its wait.
- **What broke it every time:** after about 10 s of deferral the queue consumer took the acb anyway, with a CPU wait
  "at 0 on 0x12004b77c8: TIMEOUT after 2000.1 ms" (the old acb limit, a give-up). The acb ran and released 7838, and
  the hold let go at about 12.1 s.
- **The blocked owner flushes (25):** with the chain held for 12 s, the title's thread stopped at a flush path not
  covered by the skip (k438b's counter, the why is not journaled).
- **The GPU hang at 113 s** followed these cycles. Its address is not analysed.

**What a correct hold needs, and why it is not built here:**
- ADR 0013's design point 4 said a later buffer's unserved wait becomes the queue's new head item. In practice the
  holder must submit the held chain up to its first unmet wait and keep only the rest. That means splitting a chained
  segment mid-buffer with a full-state prefix. The pre-W implementation, as restored, holds the whole chain until
  every condition is met.
- That is a new piece of the chain machinery. Per the top session, it is not to be designed before the narrower
  question below is answered.

**The narrower question: what holds the writer acb back by ≥ 20 ms from its dcb?**
- **H7 (k438b): host-side.** The join's cycle above.
- **u436sS3 (shared build): not decided by the records.**
  - Acb #165180 was submitted whole (7775 dwords). `acb_ready` had never split it, so the queue consumer did not see
    it unready while the dcb waited: either the title wrote it to its queue only around t 188.65 s, or the consumer
    did not reach it.
  - No "[bc5-q] … deferred" line falls near t 188 s; those lines start at 1 s of deferral, so a 20-ms one would not
    show.
  - The records cannot tell a title-side late write from a host-side delay.
- **Catcher to decide it**, for the next test build, not built:
  - per acb, the time its queue's write pointer first showed it against its submit time;
  - at each give-up and each hold, which guest queues had unready heads, and on which labels.

## The catcher c438 (built offline, not compiled yet: the box waits for a reboot)

The top session's question: is the writer acb late on the title's side or the host's? `mkcat438.py` applies the
catcher to patch bb04219b's unit (`a62e8bf6…` → `cat/bc5LleAgc.cpp`).
- **Scope:** records only, normal build only (`#ifndef BC5_LEAN`), no switch, no behaviour change.
- **Per compute-queue IB packet**, bc5-ring records:
  - when its look at the queue first found the write pointer past the packet (seen);
  - the gap since its previous look at that queue: the title wrote the packet somewhere inside that gap;
  - when the slice holding the packet went to `Direct::submit`.
- **Every 60 s:** one line with the packet count, the seen→submit histogram (<1, <5, <20, <100 ms, more) and the
  look-gap histogram, with the longest of each.
- **Each packet** with seen→submit ≥ 20 ms or a look gap ≥ 20 ms: one line (the first 200, then every 256th).
- **At every CPU wait** that ends GIVEN UP, TIMEOUT or CYCLE: every guest queue as bc5-ring last left it. That is
  its pending dwords, how long ago bc5-ring looked, and whether its head is unready. For an unready head: since when,
  the label, value and position of its wait, and how long ago its packet was first seen.
- **How it decides:** a late acb with a short look gap and seen→submit near 0 was written late by the title. A long
  seen→submit, or an unready head in front of it, is host-side. A long look gap means bc5-ring was busy elsewhere,
  which is host-side too.
- **Kit:**
  - `box0438.sh buildcat` compiles it with the shared normal build's own command into
    `~/bc5-work/exp0438/cat/normal/kyty_emulator`. It pins `K_CAT`, the md5 of `cat/bc5LleAgc.cpp`.
  - `CB_BIN=$HOME/bc5-work/exp0438/cat/normal/kyty_emulator MODE=scene ORDER="T T T" bash chain0438.sh` runs it as
    arm T, with no words of its own. The chain line carries the last c438 60-s line and the count of late packets.
- **Not compiled yet.** The laptop cannot build the unit. The box is off-limits until the maintainer reboots it.

## Result 4: the catcher on a clean boot (2026-11-20 09:06–09:29, boot a1db5eee, 0 GPU reset lines)

Catcher normal `8b2ae229` (c438, records only), built under BOX-LOCK at 09:05, 0 errors. Three scene runs, arm T
(no words: the shared behaviour), RT on, 4 rings, his 09:46 scene, G+300; R64 waiter, no reads during the runs.

| run | class | flips/s from G+10 | s with a gap > 50 / > 100 ms | frames (last 290 s) over 50 / 100 ms | GIVEN UP |
|---|---|---|---|---|---|
| u438sT11 | NO_CRASH | 37.71 | 195 / 54 | 10894: 703 / 63 | 0 |
| u438sT12 | NO_CRASH | 34.32 | 206 / 56 | 9915: 967 / 76 | 2 |
| u438sT13 | NO_CRASH | 33.31 | 213 / 68 | 9658: 1118 / 94 | 1 |

**Per compute-queue IB packet**, summed over the three runs from each run's last 60-s line (t 360, 420 and 360 s; the
last ~60 s of each run are not in them), 3,127,192 packets:

| | < 1 ms | 1–5 ms | 5–20 ms | 20–100 ms | ≥ 100 ms | longest (T11 / T12 / T13) |
|---|---|---|---|---|---|---|
| seen → into Direct::submit | 57.7 % | 41.7 % | 14,329 (0.46 %) | 1,507 (0.048 %) | 98 | 389 / 846 / 470 ms |
| bc5-ring's look gap before the seen | 56.7 % | 36.3 % | 185,632 (5.9 %) | 32,820 (1.05 %) | 898 | 1485 / 1636 / 1625 ms |

**At the three give-ups:**
- T12: the wait on 0x12004b3c38 at dword 11459 after 50.3 ms, and the wait on 0x12004b5438 at dword 311 after
  35.4 ms.
- T13: the wait on 0x12004b3c38 at dword 11459 after 59.6 ms.
- All three: value 0x907616589, "no pending write".
- In each, queue 1/0/0 had 96, 108 and 96 dwords pending, with its **head ready**. bc5-ring had last looked at it
  12.1, 11.8 and 12.2 ms before the give-up line. (The snapshot updates a queue only while it has pending work, so
  idle queues show old looks.)

**Answer to the narrower question:**
- **The writer acb is late on the host's side.** At every give-up it was already in its queue and ready, and the host
  had not submitted it.
- bc5-ring's look gap is the window in which the title wrote a packet. It is over 20 ms for about 1 % of all packets,
  and up to 1.6 s.
- A title-side late write would show as a short look gap with a near-zero seen→submit. That is not what the
  give-ups show.
- **Not yet measured:** the catcher stamps "submit" when the slice enters `Direct::submit`. Time spent inside it
  (F10/F16/F18's waits on the game thread's chain, the back-pressure cap, exp 0436's ring lock) is not in these
  numbers. What bc5-ring was doing in the ~12 ms before each give-up is therefore inferred, not recorded. A
  host-made mutual wait would fit: the game thread CPU-waits for bc5-ring's acb while bc5-ring waits inside its
  submit.
- **Next catcher field (proposed):** time inside `Direct::submit` per slice, by what it waited on, and the same at
  each give-up.

## Result 5: c438 part 2, what bc5-ring does with its time (2026-11-20 09:35–09:52, boot a1db5eee)

The catcher was extended under the top session's GO (`mkcat438b-part.py`, run by `mkcat438.py`; unit
`3623fd41142c49514fce913c34c2efab`, `c438-unit.diff`; normal `c731c5fa`, 0 errors, only the old warnings).
- **What it adds:** bc5-ring's time split into exclusive kinds, recorded per slice, per look gap of 20 ms or more,
  and at each give-up. The queue views are refreshed at every look.
- **The kinds:** idle, scan, submit, F10, F16, F18, back-pressure, ring-lock, dev-mutex, backend+ioctl, acb-cpu-wait,
  wait-idle.
- **Caveat on "scan":** it is bc5-ring's time outside `Direct::submit` and outside the scoped waits. That includes
  `chain_end`'s flush of the slice's chain, so it covers submit_now's whole preparation (sync, hints, filter) for the
  actual submission. "scan" is therefore mostly submit preparation; this build does not split it.

Two scene runs, arm T, RT on: u438sT14 NO_CRASH 35.45 flips/s (220 / 61 s with a gap over 50 / 100 ms), u438sT15
NO_CRASH 33.99 (219 / 73); 0 kernel lines.

| per run (last 60-s line, t ≈ 420 s) | u438sT14 | u438sT15 |
|---|---|---|
| slices | 160,892 | 155,860 |
| time per slice <1 / <5 / <20 / <100 ms / more | 125,095 / 32,368 / 2,822 / 596 / 11 | 121,248 / 30,997 / 3,018 / 588 / 9 |
| longest | 1,462 ms | 1,472 ms |
| in slices by kind (s): backend+ioctl / dev-mutex / scan(prepare) / submit | 68.3 / 44.6 / 37.4 / 12.6 | 65.5 / 45.1 / 35.4 / 12.2 |
| the rest (s): F10 / F16+F18 / back-pressure / ring-lock / acb-cpu-wait / wait-idle | 0.44 / 0.10 / 0.29 / 0.03 / 0.009 / 0.02 | 0.42 / 0.08 / 0.99 / 0.03 / 0.009 / 0.02 |
| look gaps ≥ 20 ms (per-queue records, one gap counted once per queue) | 40,505 | 42,495 |
| in them by kind (s, inflated about 12×): dev-mutex / scan(prepare) / backend+ioctl / submit / idle | 831 / 685 / 86 / 27 / 12.7 | 935 / 581 / 103 / 34 / 13.8 |

- **The longest gaps:**
  - T14: 1.46 s at the load, of which 1,444 ms was prepare in one slice.
  - T15: 1.47 s, of which 887 ms was prepare and 585 ms dev-mutex.
  - Other long slices: backend calls of 131 ms and 213 ms; dev-mutex waits of 98–106 ms inside 150–170 ms slices.
- **The give-ups** (T14: waits on 0x12004b3c38, 5438 and 7838, given up after 34.5–39.9 ms):
  - Each time, bc5-ring was "in scan for 11.7–12.1 ms".
  - The writer queue 1/0/0 had pending work with its head ready.
  - Since its last look, bc5-ring was "scan 11.9, submit 0.1" (once "scan 12.1, submit 11.6, dev-mutex 10.1").
- **Reading** (inferred from the kinds, the caveat above applies):
  - bc5-ring had taken the writer queue's ready slice and was about 12 ms into its chain's preparation, before the
    kernel call. Label writes are registered only after that call, so the game thread saw no writer on a ring and
    gave up.
  - bc5-ring's biggest losses overall are waiting for the device mutex (about 45 s in about 420 s), which the game
    thread holds for its own preparation, and that preparation itself.
- **Next (proposed, not built):**
  - split submit_now's preparation into its parts, to name what fills those 12 ms and the device-mutex waits;
  - a fix direction to be designed: register a slice's label writes as pending before its preparation. The waiter
    then sees a writer that is already committed to the ring.

## r438: register a taken slice's writes early (the fix the catcher points to)

**Design.** `mkr438.py` on the c438 part-2 unit (`3623fd41…` → `1584911aef05b01c63f7091bf150a546`, `r438-unit.diff`).
Switch `BC5_0438_EARLYREG`, on in this test build unless "0". It is behaviour, so it is in lean too.
- **At the take.** When bc5-ring takes a queue slice, before `chain_end` and submit_now's preparation, the label
  writes of the slice's compute buffers are registered as pending. These are RELEASE_MEM / EVENT_WRITE_EOP with
  immediate data and WRITE_DATA to memory, top-level packets, from past any head already submitted. The entries are
  "early": seq | bit 63.
- **The game thread.** In `ring_will_satisfy`, a wait whose label's last pending write is early waits (polls) until
  bc5-ring has ended the slice, after the real registration that follows the kernel call. Then it decides again, and
  is kept in ring order. So the writer job is in the kernel before the waiter's buffer, the order ring-order keeps
  always had and k438 broke. A wait over 100 ms is journaled as a BUG line (up to 10) and the poll goes on: no
  give-up, no recovery.
- **Who ignores early entries:** bc5-ring's own `ring_will_satisfy`, and F2/F4 (they need a real job to fence on).
- **The invariant** ("a registered write must reach the ring"). At the slice's end every early write must have been
  registered for real by a job of that slice: `register_label_writes` on bc5-ring while the slice is open. One that
  was not is a BUG line, counted as "early writes that never reached the ring", and removed.
- **The paths checked for it:**
  - a failed or dropped submission, and a write the filter drops: each would show as a BUG line;
  - flushes for size and ring/class change: `chain_end` and its flushes all submit on bc5-ring inside the slice;
  - acb heads submitted earlier by `acb_ready`: excluded by their `done` offset;
  - a GPU reset clears `g_plw` whole;
  - process exit: no slice survives it.
- **Records (normal build):**
  - submit_now's preparation split into prep-pre / anon sync / direct sync / learned / hints / filter;
  - bc5-ring's device-mutex waits by the holder at their start (game thread, bc5-ring or other, and its part);
  - an r438 line every 60 s.

**Unit test** `bash test_r438.sh`. It cuts r438's state, `PendingLabelWrite`/`g_plw`, `register_label_writes`,
`r438_scan`/`begin`/`end` and `ring_will_satisfy` from the generated unit, unchanged, and runs them against stubs.
Laptop, VS clang++, image base fixed low so the 40-bit IB address fits; 2026-11-20. **PASS both ways:**
- **`BC5_0438_EARLYREG` unset:**
  1. A game-thread wait on an early-registered label waits about 30 ms, until the job registers it and the slice
     ends, then is kept in ring order; 0 lost.
  2. A slice whose job never registers: 2 lost, 2 BUG lines, the early entries removed.
  3. A head already submitted is not registered again.
  4. bc5-ring's own `ring_will_satisfy` ignores early entries.
- **`BC5_0438_EARLYREG=0`:** nothing is registered early.

**Build:** normal `4b9ffcf8` (r438 + c438), under BOX-LOCK at 10:02, 0 errors, only the old warnings; shared builds
checked unchanged.

## Result 6: r438 on the box (2026-11-20 10:03–10:48, boot a1db5eee, 0 GPU reset lines, binary 4b9ffcf8)

Chain `C3 R C3 R C3 R`, his 09:46 scene, RT on, 4 rings, G+300. C3 = `BC5_0438_EARLYREG=0`, R = `=1`. The first C3
passed the gate (≥ 33.3 flips/s). 0 kernel lines in all six runs.

| run | arm | class | flips/s from G+10 | s with a gap > 50 / > 100 ms | frames (last 290 s) over 50 / 100 ms | given up |
|---|---|---|---|---|---|---|
| u438sC316 | C3 | NO_CRASH | 36.28 | 210 / 61 | 10516: 733 / 69 | 0 |
| u438sR17 | R | NO_CRASH | 33.72 | 211 / 79 | 9776: 998 / 90 | 0 |
| u438sC318 | C3 | NO_CRASH | 35.74 | 217 / 64 | 10318: 800 / 79 | 1 |
| u438sR19 | R | NO_CRASH | 33.88 | 214 / 68 | 9772: 972 / 86 | 0 |
| u438sC320 | C3 | NO_CRASH | 36.28 | 203 / 64 | 10495: 698 / 76 | 0 |
| u438sR21 | R | NO_CRASH | 36.12 | 216 / 58 | 10436: 734 / 73 | 0 |

**r438 in the R runs** (the 60-s line at t 360 / 420 / 420 s):

| | R17 | R19 | R21 |
|---|---|---|---|
| early writes | 3,303,661 | 3,775,091 | 3,960,909 |
| early writes that never reached the ring | **0** | **0** | **0** |
| BUG lines | 0 | 0 | 0 |
| game-thread waits for an early writer | 31,344 | 35,472 | 36,413 |
| their total | 16.6 s | 19.2 s | 19.6 s |
| the longest | 50.0 ms | 34.7 ms | 27.2 ms |
| over 100 ms | none | none | none |

**Prepare split, bc5-ring inside slices** (ranges over the six runs, about 360–420 s each):
- prep-direct-sync 16.8–21.8 s;
- prep-filter 8.5–10.6 s;
- prep-pre 3.3–4.3 s (exp 0412's ww412/k1f412/dt412 passes and what precedes the syncs);
- prep-learned 1.8–2.5 s;
- prep-hints 0.6–0.8 s;
- prep-anon-sync about 0.1 s;
- besides: dev-mutex 37–46 s, backend+ioctl 58–72 s.

**bc5-ring's device-mutex waits, by the holder at their start: always the game thread.**

| holder's part | seconds |
|---|---|
| prep-pre | 15.5–19.2 |
| direct sync | 4.8–6.3 |
| anon sync | 3.4–4.6 |
| hints | 1.5–1.8 |
| filter | 1.3–1.6 |
| backend | 0.2 |

**Reading:**
- **r438 holds its invariant:** 11.0 M early writes, 0 lost. No give-up in 3 R runs against 1 in 3 C3 runs. The base
  rate is too low to call the give-ups removed.
- **It costs the game thread** 17–20 s of waiting a run, about 35,000 waits of about 0.5 ms for bc5-ring's
  preparation.
- **flips/s:** R 33.72 / 33.88 / 36.12 (mean 34.57) against C3 36.28 / 35.74 / 36.28 (mean 36.10). Two R runs are
  below every C3 run, one is inside the C3 range. That is a likely cost, not a shown one (R13).
- **The preparation's biggest parts:** bc5-ring's own direct sync, then the filter. The device mutex is held mostly
  by the game thread's pre-passes and syncs.

## r438a (mode 2) and prep-pre by pass (built 2026-11-20 11:00, normal d59eae9b; chain waiting for the top session)

- **Where the give-up's writer was.** u438sC318's give-up (r438 off) recorded "bc5-ring is in prep-learned for
  1.1 ms; since queue 1/0/0's look: prep-direct-sync 11.1, prep-learned 1.1 ms". The writer was inside bc5-ring's
  direct sync, so registering after the direct sync would not close it.
- **Mode 2 (`BC5_0438_EARLYREG=2`, the test build's default; 1 keeps r438, 0 off)** registers at the take as before,
  but the game thread waits for an early writer only when no real pending write of the label already satisfies the
  wait. That case was kept for the GPU at once before r438, and r438 shadowed it. Counted as "real write satisfied,
  no wait".
- **prep-pre by pass:** exp 0412's ww412 / k1f412 / dt412 passes, each its own c438 kind and holder part.
- **Unit:** `mkr438.py` → `94d696fbfe6cca223346ba255338a0f0`.
- **`test_r438.sh`: PASS** with the mode unset (2), 1 and 0. A new case 5: a real older write satisfying plus a newer
  early one. Mode 2 uses the real one at once (cheap 1); mode 1 waits for the early one.
- **u438** (the game thread's prep-pre and syncs outside `g_dev_mutex`) is **not built**:
  - k1f412 and dt412 import through `direct_force`;
  - `direct_force` and `direct_sync_one` change `g_d`'s state (forced chunks, BOs, views, device mappings) with no
    lock but `g_dev_mutex`, and bc5-ring's prepare syncs the same state;
  - the passes keep static counters;
  - so a narrower lock must cover `g_d` whole, and the gain is not shown.
  The by-pass split is the first step.

## Result 7: r438a (mode 2) against off (2026-11-20 11:02–11:48, boot a1db5eee, binary d59eae9b)

Chain `C3 A C3 A C3 A`, his scene, RT on, 4 rings, G+300. All NO_CRASH, 0 kernel lines; the gate passed (C322 35.03).

| run | arm | flips/s | s with a gap > 50 / > 100 ms | frames (last 290 s) over 50 / 100 ms | given up | early-writer waits (s) |
|---|---|---|---|---|---|---|
| u438sC322 | off | 35.03 | 221 / 62 | 10101: 901 / 75 | 4 | – |
| u438sA23 | mode 2 | 34.16 | 210 / 57 | 9843: 897 / 68 | 0 | 31,612 (17.0 s, longest 39 ms) |
| u438sC324 | off | 34.29 | 225 / 66 | 9900: 970 / 80 | 3 | – |
| u438sA25 | mode 2 | 34.62 | 220 / 63 | 9997: 884 / 74 | 0 | 35,852 (19.7 s, longest 38 ms) |
| u438sC326 | off | 34.02 | 222 / 65 | 9820: 958 / 86 | 5 | – |
| u438sA27 | mode 2 | 34.79 | 221 / 65 | 10051: 879 / 76 | 0 | 35,308 (19.6 s, longest 72 ms) |

- **Mode 2's cheap path never fired** ("real write satisfied, no wait 0" in all three A runs). My explanation for
  r438's waits (a real pending write shadowed by an early one) is refuted. The waits have no satisfying real write,
  and mode 2 behaves as mode 1.
- **The invariant held:** early writes 3.3–3.8 M per run, never reached the ring 0, BUG lines 0.
- **Give-ups:**
  - r438 (modes 1 and 2) had 0 in 6 runs; the controls had 13 in 6 (results 6 and 7 together).
  - flips/s pooled over both chains: r438 mean 34.55 (6 runs), off 35.27 (6). The spreads overlap and the boot's
    later runs are slower; this chain shows no cost (34.52 against 34.45). No cost is shown and none is excluded.
- **prep-pre by pass:** k1f412 dominates.
  - bc5-ring's own time: k1f412 2.8–3.9 s a run, ww412 and dt412 about 30–38 ms each.
  - bc5-ring's device-mutex waits by the game thread's part:

    | holder's part | seconds |
    |---|---|
    | k1f412 | 15.6–19.8 |
    | direct sync | 5.1–6.3 |
    | anon sync | 3.4–4.7 |
    | hints | 1.3–1.7 |
    | filter | 1.3–1.6 |
    | the rest of prep-pre | 0.2–0.5 |

  - The number of walks per submission was not counted.
- **No further work on either.** The maintainer's change of direction: no r438 tuning and no prep-pre speed-up after
  this chain.

## t438: the --submit test, run 1 (2026-11-20 11:49, boot a1db5eee, no title running)

`t438.cpp` (md5 `622a6db1…`), built in the ubuntu distrobox (g++, libdrm-amdgpu1 2.4.131 there); kernel
7.3.3-ogc1.1.fc45, host libdrm 2.4.134, DRM 3.64.

- **Variant d:** a GFX wait on a label in a plain GTT BO, with the writer queued behind it on the GFX ring. The
  CPU guard wrote the label at 300 ms and **the wait never passed**.
- The kernel logged `ring gfx_0.0.0 timeout`, and the reset succeeded. The run stopped there; no other variant ran.
- **Reading** (inferred): the GPU's polling reads the label through its cache, so a CPU store does not release it.
  The harness's guard was wrong in design, my error. The variants that stall by design (c, d, d2) can only end in
  a ring timeout.
- The boot has a GPU reset now (R60).
- **Proposed:** drop c, d and d2; add the timestamps' cache write-back; run a, a0 and b after a reboot.

## t438 run 2: a compute job of the same VM releases a GPU-waiting GFX job (2026-11-20 11:55, boot a1db5eee)

**Run 1 was my harness error, and it reset the GFX ring.** Run 1's CPU guard (11:49) could not release the GPU's
wait. Variant d therefore ended in a gfx ring timeout; the reset succeeded and the box stayed up. The design was
wrong: the stalling variants (c, d, d2) can only end in a ring timeout. They are dropped. The boot carries that reset.

**Run 2: the top session's ruling.** GPU-behaviour tests are allowed on this boot.
- Setup: `t438.cpp` md5 `16763936…`, built in the distrobox. Kernel 7.3.3-ogc1.1.fc45, host libdrm 2.4.134, container
  libdrm-amdgpu1 2.4.131, DRM 3.64. Under BOX-LOCK, no title running.
- Variants, label L:
  - a: in a udmabuf of a memfd, imported as the emulator's direct memory;
  - u: in a userptr BO, as the emulator's writable guest mappings;
  - b: in a GTT BO with EXPLICIT_SYNC.
- Every BO is in both jobs' BO lists. There is no CPU guard. Output: `raw/t438-runs.txt`.

| variant | writer (compute ring 0, 5 ms after G) done after its submit | G done after G's submit | G's wait on the GPU clock | ring timeout |
|---|---|---|---|---|
| a (udmabuf) | 0.266 ms | 5.363 ms | 507,112 ticks (≈ 5.07 ms at 100 MHz) | none |
| u (userptr) | 0.262 ms | 5.342 ms | 506,628 ticks | none |
| b (explicit sync) | 0.262 ms | 5.341 ms | 506,488 ticks | none |

- **Result:** a compute job of the same VM starts at once and releases a GFX job that waits on the GPU for it,
  with the emulator's BO types and shared BO lists. 0 timeouts; the reset count is unchanged at 4 lines.
- **This refutes on the box** both implicit sync and a VMID-flush wait as the reason acb #65702 did not run in
  u438sK2.
- What is left for K2 is host-made: a kernel dependency the host added to the acb (F4's `t_next_deps` landing on
  the waiting GFX job, or a piece of it), or the acb never being in the kernel when believed. Not decided by the
  records.

## A question, not a fact: can a CPU store release a GPU poll on guest label memory?

- **What happened.** In t438 run 1 a CPU store to the label (a plain GTT BO, flags 0) did not release a GFX
  `WAIT_REG_MEM` within 2 s.
- **What the code says** (torvalds/linux master through a fetch agent; TODO(verify) on 7.3.3):
  - a GTT BO with flags 0 gets `ttm_cached` (`amdgpu_ttm_tt_create`), so `AMDGPU_PTE_SNOOPED`
    (`amdgpu_ttm_tt_pde_flags`), and `MTYPE_NC` from `gmc_v10_0_get_vm_pte` (UC only with
    COHERENT/EXT_COHERENT/UNCACHED);
  - a userptr BO and a TT-resident dma-buf import (the emulator's udmabuf) are created the same way. **Guest label
    memory therefore has the same PTE class as t438's GTT BO:** NC, snooped.
  - `gfx_v10_0_wait_reg_mem` carries no cache bits;
  - the job's end fence writes back GL2 but does not invalidate it (`gfx_v10_0_ring_emit_fence`: GL2_WB, GLM_WB/INV);
  - `gfx_v10_0_emit_mem_sync` (ACQUIRE_MEM) invalidates GL2 among others.
- **Inference (not verified):** an NC line the GPU has read can stay in GL2. A GPU poll that hits it does not see a
  later CPU store until GL2 is invalidated. CPU writes made before a job (behind the per-job invalidate) are seen;
  CPU writes during a job's wait may never be.
- **Why it matters:** the host releases some GPU-visible labels from the CPU, e.g. the flip labels it clears itself
  (A:9990-10022). The title's own CPU marks could hit the same case. That is safe only while no GPU wait polls them
  during the store.
- **Checks proposed, no stall test:**
  - the semantics of MTYPE NC in GL2 for this ASIC, from a public AMD source;
  - whether the console's WAIT_REG_MEM carries a cache-policy field the host strips. The title's waits have
    dword-1 bit 26 set (0x04000113), and t438's had 0x113. Mesa's `sid.h` defines no such field for
    WAIT_REG_MEM: TODO(verify).

## Step 2 and step 3 (the top session's order)

- **Step 2:** `adr-draft-gpu-waits.md`, with the four doorbell options. The new one is D, the title's own
  0xc010811c "ding dong" kick, which the host ignores today. Recommendation: a watcher thread with per-ring
  submitters, woken by the kick where the title sends one. End state: GFX waits stay on the GPU, as on the console.
- **Step 3:** `inventory-submission-path.md`, two tables (guest calls, PM4 packets) with code references and the
  console column as the code states it or TODO(verify).

## c438d: the title never kicks (2026-11-20 12:02–12:10, boot a1db5eee, one T run)

- **Build:** `mkc438d.py` on the c438 unit, giving `c438d.cpp` `3a10750d…` (`c438d-unit.diff`); normal `8b61c606`,
  records only, shared behaviour.
- **Run:** u438sT28, NO_CRASH, 33.16 flips/s (218 / 70 s with a gap over 50 / 100 ms).

**`/dev/gc` requests in about 360 s:**

| request | count | thread | what the host does |
|---|---|---|---|
| 0xc0188132 (submit list) | 615,322 | Render Thread, 25 from game-main | implemented |
| 0xc0488131 (submit header) | 14,963 | Render Thread | implemented |
| **0xc0088133** | 14,962 | Render Thread | **unhandled, answered with zeros** |
| **0xc0108139** | 14,963 | Render Thread | **unhandled, answered with zeros** |
| 0xc0408121 (queue registration) | 56 | game-main | implemented |
| 0xc010813b, 0x80048126, 0x8004812a, 0x80048134, 0x80108128, 0x80888123, 0xc004812e | 1 each | game-main | 0xc010813b, 0x80048126, 0x80048134 and 0x80888123 unhandled (zeros); the others handled |

- **Kicks (0xc010811c): 0.** The title never calls "ding dong". Pointer moves seen by bc5-ring: 129,637, none after
  a kick. **Option D is dead** for this title: the doorbell is its only signal.
- **New for the inventory:** two requests the title makes once per frame (0xc0088133 and 0xc0108139, each about
  15,000, with the submit header) are not known to the host. They fall into the default case, which zero-fills
  them. What they are is TODO(verify), from public sources only (RPCSX's gc device is the reference, D18).

## w438 built (the watcher and per-queue submitters)

- **Build:** `mkw438.py` on `mkc438d.py`'s output on r438, giving `w438.cpp` `d67488c3…` (`w438-unit.diff`);
  normal `36c1733a`, 0 errors, only the old warnings; shared builds checked unchanged.
- **Switches:** `BC5_0438_WATCHER` (on unless "0") and `BC5_0438_KICK` (no effect, the title never kicks).
  r438's `BC5_0438_EARLYREG` and c438/c438d's records are in the same binary.
- **`test_w438.sh` (the hand-over cut from the unit): PASS** with the switches unset, with the kick off, and with the
  watcher off.
  - A move wakes the submitter in about 30 ms against a 500 ms timeout (the Windows timer).
  - A move seen while it was busy is not lost.
  - The same pointer counts once.
  - One submitter per queue.
  - A kick wakes the watcher.
- **Chain (for a clean boot):** `WC W WD` × 3.
  - WC = all off; W = watcher + r438 mode 1; WD = W + kick.
  - Since the title never kicks, WD equals W in behaviour. Drop WD for 3 more W, or keep it as a no-op control: the
    top session's call.

## Result 8: w438 on a clean boot (2026-11-20 12:34–13:53, boot eb264b8c, 0 GPU reset lines)

- **The first attempt (12:34) stopped at its first W0 run.** u438sW030 ended at 1.6 s on a refused submission: "submit
  #42 acb 57 dwords on ring 0 was REFUSED by the device (rc -16)". The record is `faults/20261120-124234`, exit 86;
  0 kernel lines.
  - Cause, my bug: the 24-job cap was checked before the ring lock, so several submitters on one compute ring
    overfilled its 24-slot pool.
  - Fixed: the cap is re-checked under the ring lock (`mkw438.py` step 8). Rebuilt as unit `91557164…`, normal
    `97ace22e`.
- **The chain:** `WC W0 W` × 3, his scene, RT on, 4 rings, G+300.
  - WC = all off; W0 = watcher alone (`EARLYREG=0`); W = watcher + r438 mode 1. The kick never fires (c438d).
  - All 9 runs NO_CRASH, 0 kernel lines. The laptop's ssh dropped twice (network); the chain ran on under the user
    manager.

| run | arm | flips/s | s with a gap > 50 / > 100 ms | frames (last 290 s) over 50 / 100 ms | given up | early-writer waits | bc5-ring/submitters' device-mutex wait |
|---|---|---|---|---|---|---|---|
| u438sWC32 | WC | 36.20 | 206 / 55 | 10445: 769 / 67 | 0 | – | 44.7 s |
| u438sW033 | W0 | 33.00 | 216 / 69 | 9514: 1110 / 88 | 5 | – | 237.3 s |
| u438sW34 | W | 34.42 | 218 / 68 | 9934: 929 / 93 | 0 | 26,196 (14.2 s, longest 39 ms) | 196.8 s |
| u438sWC35 | WC | 33.47 | 220 / 66 | 9657: 1059 / 84 | 0 | – | 44.6 s |
| u438sW036 | W0 | 32.73 | 220 / 78 | 9433: 1156 / 101 | 1 | – | 237.5 s |
| u438sW37 | W | 33.32 | 218 / 70 | 9661: 1105 / 93 | 0 | 24,737 (13.6 s, longest **112 ms**) | 197.0 s |
| u438sWC38 | WC | 34.34 | 211 / 70 | 9904: 919 / 88 | 0 | – | 39.9 s |
| u438sW039 | W0 | 35.11 | 211 / 60 | 10142: 773 / 78 | 3 | – | 222.7 s |
| u438sW40 | W | 32.92 | 216 / 72 | 9549: 1036 / 93 | 0 | 25,644 (14.6 s, longest **144 ms**) | 191.2 s |

**Reading** (3 against 3 per arm, R13):
- **The watcher alone (W0) does not close the give-ups:** 9 in 3 runs against 0 in 3 for WC on this boot.
  - It is also no faster: mean 33.61 flips/s against WC 34.67, and frames over 50 ms in the same range or higher.
  - The control's give-ups vary by boot: 12 in 3 on a1db5eee in result 7, 0 in 3 here.
- **W (watcher + r438) has 0 give-ups** (r438 again: 0 in 9 runs across results 6–8).
  - Its early-writer waits are 13.6–14.6 s, below result 7's 17–20 s.
  - But two waits went over 100 ms (112 and 144 ms; BUG lines journaled).
  - Mean 33.55 flips/s against WC 34.67, so no gain.
- **The submitters fight over the device mutex:** 191–237 s of waiting summed over the threads, against 40–45 s for
  the single bc5-ring. Each submitter's preparation still takes `g_dev_mutex`, so N threads queue on one lock. The
  look-gap counts are not comparable between the arms: an idle submitter's 50-ms wait counts as a look gap.
- **Verdict on w438:** refuted as built. Taking the doorbell faster does not help while every submission's
  preparation serializes on `g_dev_mutex`. The lever is that lock: the game thread's k1f412 and syncs, then
  bc5-ring's own direct sync (results 5–7), not the doorbell.

## u438: k1f412's walk out of the device mutex (design; built only on the top session's GO)

- **The top session's decisions after result 8:** w438 is closed (refuted) and is not in this build; r438 mode 1
  stays as the bridge; u438 is the next lever.
- **The unit chain:**
  1. `mkcat438.py`: `3623fd41…`;
  2. `mkr438.py`: `94d696fb…`;
  3. `mkc438d.py`: `fdfa45be…` (`r438d.cpp`);
  4. `mku438.py`: **`78f319da0beee7c0bbb7f6b582470a2e`** (`u438-unit.diff`).
- **Switches:** `BC5_0438_SPLIT` (u438, on unless "0") and `BC5_0438_EARLYREG` (r438). c438/c438d's records are
  in the normal build.

**What k1f412_pass touches, and which lock covers it.** The game thread's k1f412 pass is the largest single holder
of `g_dev_mutex`: 15.6–19.8 s a run, results 6–8.

| what | today | with u438 |
|---|---|---|
| the IB's packets (read) | `g_dev_mutex` (not needed: the title's buffer, unchanged while it is submitted) | none: read before the lock |
| `bc5::policy::memory_operands`, `ud434::scan` (pure parses) | `g_dev_mutex` | none |
| `g_dev->sorted_mappings()` | `g_dev_mutex` + the backend's mutex | the backend's mutex only |
| `covered_sorted` on the snapshot (pure) | `g_dev_mutex` | none |
| `direct_force` (imports: `g_d`'s forced chunks, BOs, views; the device mappings) | `g_dev_mutex` | `g_dev_mutex`, unchanged |
| the pass's static counters and journal lines | `g_dev_mutex` | `g_dev_mutex` (they move with the imports) |

`sorted_mappings()` returns a shared_ptr snapshot that the backend builds under its own mutex, as a new object at
every change of the list (`Device::sorted_mappings`, backend `direct.cpp`).

**The change:**
- `submit_now` walks the IB before its back-pressure wait and the locks (`k1f412_collect`), on the snapshot of that
  moment. It keeps the operands and user-data V#s that are not covered.
- Under `g_dev_mutex`, at k1f412's place, the snapshot is compared with the current one by pointer identity, which
  means the same mapping list:
  - unchanged: only the kept misses are looked at again and imported as today;
  - changed (a sync or an import in between): the walk is done again under the lock, exactly as today.
- So u438 imports what today's pass imports whenever the list did not change in between, and is today's pass
  otherwise.
- **No ABA on the pointer compare** (the top session's condition (b), checked in `mku438.py`'s code):
  - the snapshot is held in `u438::t_pre.snap`, a `std::shared_ptr` member of the thread-local `Pre`, from the walk
    until after the compare under `g_dev_mutex`;
  - `p.valid` is cleared after the compare and the pointer is kept until the next walk replaces it;
  - so the list it points to cannot be freed in between, and its address cannot be reused by a newer list;
  - equal pointers therefore mean the same, still-live list object.
- **Not moved:** the syncs and `direct_force` (they change `g_d` state, which bc5-ring's own preparation syncs too),
  and dt412 (about 30 ms a run).
- **Records:** a `u438` line every 60 s (walks before the lock, their time, used under the lock, walked again). c438's
  holder table shows whether `game/prep-pre-k1f412` drops.

**No standalone unit test.** The walk uses the policy parser and the mapping list; the equivalence is argued above and
measured on the box.

**Chain (clean boot, his scene, RT on, the same gates):** `UC U UR` × 3.
- UC = `SPLIT=0 EARLYREG=0`; U = `SPLIT=1 EARLYREG=0`; UR = `SPLIT=1 EARLYREG=1`.
- Per run:
  - flips/s and frames over 50 / 100 ms;
  - give-ups;
  - early writes lost and early-writer wait seconds;
  - device-mutex waits and their holders;
  - the prepare split;
  - the u438 line.

## Result 9: u438 on a clean boot (2026-11-20 14:07–15:16, boot eb264b8c, 0 GPU reset lines, binary 0ccc5aa8)

- **Build:** normal `0ccc5aa8c2fa9b20e98578c907f3506b` (unit `78f319da…`).
  - Built under BOX-LOCK 14:06–14:10, after checking that no emulator was running and no lock was held.
  - Shared builds unchanged.
- **Chain:** `UC U UR` × 3, his scene, RT on, 300 s each, under the user manager. One R64 waiter, no reads during the
  runs.
- **Outcome:** 9 of 9 NO_CRASH, pad keys 0 in all, no GPU line. The chain ran to its end.
- **Raw:** `raw/u438-chain-out.txt`, `raw/u438-chain-rows.txt`.

| run | arm | flips/s | s with a gap > 50 ms | > 100 ms | give-ups | bc5-ring's dev-mutex waits behind `game/prep-pre-k1f412` (s) | bc5-ring's dev-mutex time in slices (s) | journal line at |
|---|---|---|---|---|---|---|---|---|
| u438sUC42 | UC | 34.67 | 215 | 69 | 2 | 16.4 | 38.2 | 360 s |
| u438sU43 | U | 33.53 | 221 | 68 | 2 | 11.7 | 34.1 | 360 s |
| u438sUR44 | UR | 33.33 | 216 | 74 | 0 | 11.6 | 33.9 | 360 s |
| u438sUC45 | UC | 35.05 | 220 | 66 | 2 | 14.6 | 37.8 | 360 s |
| u438sU46 | U | 35.12 | 204 | 58 | 1 | 12.0 | 33.8 | 360 s |
| u438sUR47 | UR | 33.43 | 230 | 76 | 0 | 17.3 | 43.9 | 420 s |
| u438sUC48 | UC | 34.16 | 227 | 67 | 2 | 18.5 | 45.0 | 420 s |
| u438sU49 | U | 33.72 | 224 | 80 | 2 | 13.3 | 40.3 | 420 s |
| u438sUR50 | UR | 34.75 | 219 | 74 | 0 | 14.0 | 40.5 | 420 s |

**Rates.** The holder and slice times are cumulative up to the run's last 60-s line, at 360 or 420 s, so they are
compared per minute.
- Waits behind k1f412:
  - UC: 2.73, 2.43, 2.64 s/min;
  - U: 1.95, 2.00, 1.90 s/min;
  - UR: 1.93, 2.47, 2.00 s/min.
- bc5-ring's dev-mutex time in slices:
  - UC: 6.37, 6.30, 6.43 s/min;
  - U: 5.68, 5.63, 5.76 s/min;
  - UR: 5.65, 6.27, 5.79 s/min.

**The u438 line (U and UR).**
- 345,736–405,410 walks before the lock, 7.2–9.0 s of walk time in all.
- 99.3 % were used under the lock. 2,325–2,802 were walked again because the mapping list had changed.

**r438 (UR only).**
- Early writes that never reached the ring: 0 in all three runs.
- Game-thread waits for an early writer: 30,707–33,874 waits, 16.95 / 18.48 / 18.96 s in all, longest 35.9 / 63.1 /
  60.7 ms. No bug lines (none over 100 ms).

**Reading** (R13: 3 against 3 shows no significance).
- **u438 does what it was built for, by a little.**
  - bc5-ring's waits behind the game thread's k1f412 drop by about a quarter: 1.90–2.00 s/min in U against 2.43–2.73
    in UC. The ranges do not overlap.
  - bc5-ring's whole device-mutex time in slices drops by about 10 %: 5.63–5.76 against 6.30–6.43 s/min.
- **It does not show at the frame level.**
  - flips/s: UC 34.16–35.05, U 33.53–35.12, UR 33.33–34.75. These overlap.
  - Seconds with a gap over 50 ms: UC 215–227, U 204–224, UR 216–230. These overlap too.
- **Most of k1f412's hold is not the walk.**
  - Even with the walk outside the lock, about 2 s/min of bc5-ring's waits still fall behind `prep-pre-k1f412`.
  - The walk itself costs about 1.2–1.3 s/min, now outside the lock.
  - What is left under the lock is the imports (`direct_force`), the `sorted_mappings()` call for the compare, and
    the redo walks (about 0.7 %). Which of these dominates is not measured.
- **Give-ups.** UC 2/2/2 and U 2/1/2: the F262 give-up still happens, but no run hung. UR 0/0/0, as in result 6, at
  the cost of 17–19 s a run of game-thread waits for early writers.
- **Proposal for the top session** (not done):
  - keep u438 as harmless but too small to bake on its own;
  - r438 mode 1 stays the only arm that removes the give-ups;
  - what is left on the device mutex is bc5-ring's own preparation and the game thread's k1f412 imports:
    - in c438's by-kind slice table, bc5-ring's own `prep-direct-sync` takes 18.6 s and `prep-filter` 8.8 s
      (u438sUC42);
    - among the game-side holders that bc5-ring waits behind, every one other than k1f412 is ≤ 6.4 s a run.

## Build 10: s438 (direct_sync's scan on a merge-only pass) and i438 (the unknown ioctls' buffers), design

The top session's order after result 9:
- u438 and r438 mode 1 stay in the test build behind their switches.
- One build gets (a) step 3's in-buffer records and (b) the next lever, picked by its share of bc5-ring's
  device-mutex time.

**Unit chain:** `mks438.py` on `u438.cpp` (`78f319da…`) → **`a56293942679688016778eef88c704c1`** (`s438-unit.diff`, 84
lines).

**Picking the lever** (result 9's U and UR runs, about 360 s each). bc5-ring's own slices hold the mutex in these
parts:
- `prep-direct-sync` 17.9–19.5 s;
- `prep-filter` 8.9 s;
- `prep-pre-k1f412` 1.6 s.

Of its device-mutex waits, the share behind each game-thread holder:
- `prep-pre-k1f412` 11.6–17.3 s;
- `prep-direct-sync` 5.2–6.4 s;
- `prep-filter` 1.8–2.1 s.

Together (bc5-ring's own hold plus its waits behind the game thread):
- direct-sync is about 23–25 s;
- k1f412 is about 13–19 s;
- filter is about 11 s.

So the lever is `prep-direct-sync`.

**Where direct_sync's time goes.** `direct_sync_one`, under `g_dev_mutex`, is called from `prepare` with `force`
only when the filter found unmapped operands; otherwise it is rate-limited to 50 ms.
- **Its fast path returns** when nothing in the memfd is new (`st_blocks`), no view is new (the views' signature),
  nothing new is forced and every BO is mapped, **and the merge is not due**.
- **The merge is due every 250 ms per DState.** So every 250 ms a full pass runs, even when nothing changed. It
  does:
  1. step 1, the scan for data chunks to import: a binary search on `S.bos` per view gap and an `lseek(SEEK_DATA)`
     on the memfd per uncovered gap, over all views;
  2. the merge;
  3. the lzr pass;
  4. the mapping rebuild, only when something changed.
- The split of these parts is not known for these runs: the "timing split" line needs `BC5_DIRECT_TIMING`. The new
  s438 line records it.

**s438** (`BC5_0438_MERGESCAN`, behaviour, so in lean too; on unless "0").
- A full pass whose only reason is the merge (same blocks, views, forced set and mapped BOs) skips step 1. The
  merge and everything after it run as before.
- It does this only when the last full scan of that DState is under 1 s old. So a full scan still runs at least
  once a second.
- It stays off when `g_zskip` is not empty or a new zero list was placed, so the zero-skip take-back is never left
  out.

| what step 1 touches | lock |
|---|---|
| `S.bos`, `S.forced`, `S.failed`, `S.file_size` (read); `S.bos`, `S.bytes` (import, write) | `g_dev_mutex` |
| the memfd (`lseek SEEK_DATA`, read only) | none needed |
| `g_zskip`, `zskip_take_back` | `g_dev_mutex` |
| `ls415_import` (dma-buf import, ioctls) | `g_dev_mutex` |

s438 moves nothing out of the lock. It runs step 1 less often under it: at most once a second on a merge-only pass,
instead of four times.

What it gives up: a data chunk that appears with `st_blocks` unchanged (a page freed and another written in the
same window) is found up to 1 s later instead of up to 250 ms. A packet operand on such a chunk is still imported
at once by k1f412, since `S.forced` grows and the next sync is then not merge-only.

**What a late chunk would look like** (the top session asked for this, so a future fault can be checked against it).
A late chunk is not imported, so the GPU has no mapping for it for up to 1 s. The chunk is reached only through
memory that no packet operand names: a descriptor inside a buffer, a shader's own load, a BVH node.
- **A read with no mapping and no cover:** a GPU page fault (a VM fault line, `amdgpu … [gfxhub] page fault` with the
  address), or, with the fault recorder, exit 86 and a record under `~/bc5-data/captures/faults/`. The faulting
  address is inside a direct-memory view of the memfd, in a chunk that a later sync line (`+N BOs`) imports.
- **A read through a zero or cover mapping (k1r412, zskip):** zero or stale data with no fault. A texture or
  geometry that is black, missing or flickers for up to 1 s and then shows. Or a compute result built from zeros:
  a lighting, BVH or RT artefact for a frame or more.
- **A write to such a chunk:** lost, or a fault as above.
- **To check a fault against s438:**
  - Is the address in a chunk that was data in the memfd but not imported at the fault?
  - Was the last full scan of that DState up to 1 s before, with merge-only passes since (the s438 line's counts)?
  - Does the same fault happen with `BC5_0438_MERGESCAN=0`?

**s438 records** (normal build): an `s438` line every 60 s, from `direct_sync` under the mutex, with:
- passes fast and full;
- merge-only passes with the scan left out, and with it run;
- the full passes' time by part: views, scan, merge, drain, maps.

If the scan is not the large part, the line names the part that is, for the next build.

**i438** (step 3's follow-up; records only, normal build, no switch: what the title gets back is unchanged).
- In `gc_ioctl`'s default case, for `0xc0088133` and `0xc0108139` only, it logs:
  - the in-buffer before the zero-fill;
  - the out-buffer after it (what the host returns, zeros);
  - the thread name and the call number.
- It reads at most the request's `_IOC` size, 8 or 16 bytes. The 64 bytes asked for are capped at that size,
  because reading past the argument could fault.
- Rate: the first 200 calls of each request, then 1 in 600.

**Chain** (clean boot, his scene, RT on, the same gates): `MC M` × 3, both on result 9's UR base
(`BC5_0438_SPLIT=1 BC5_0438_EARLYREG=1`).
- MC = `BC5_0438_MERGESCAN=0`; M = `BC5_0438_MERGESCAN=1`.
- The gate is the first MC run at ≥ 33.3 flips/s.
- Per run: flips/s, gaps over 50 / 100 ms, give-ups, c438's holder table and slice kinds, the s438 line, and the
  i438 line count.

## Finding draft (separate, not chased): host text in guest memory

u438sK2's dumped dcb #65701 has a title NOP marker (dword 718, 10 dwords). Its payload is host journal text, "eps its
wait at 6167 on 0x12004b4c38", from k438's 10th journal line. Title memory at 0x11e0450aa8 (one of the title's direct views,
eager at 0x11e0000000) reads "its wait" too, at the probe. The title's own NOP markers carry its debug strings, copied
from its memory. So host-formatted text reached guest memory that the title later copies or uses. A candidate, not
checked: host code (`journal`'s formatting) running on a guest thread's stack, below the title's frames, in memory the
title reuses. To be checked on its own: which thread's stack spans that address, and whether host buffers live in
guest-allocated stacks.

## Verdict

**Inconclusive as a fix. The cause stands, two fixes are refuted, and the open question is narrowed.**
- **F865's cause** (from the records, high confidence): a game-thread dcb wait on an acb's release, with no writer on
  any ring, was given up after ~21 ms (the F262 give-up). The dcb ran ahead of the acb's work and the GFX ring hung.
  It is not F3's case: F2 cycles were 0 all run.
- **k438** (keep the wait for the GPU): refuted. 1 GPU hang in 1 run, at its own kept wait (u438sK2). The writer
  acb was in the kernel and did not complete before the GFX job was reset. Why is not known; the VMID-flush candidate
  was weakened by `amdgpu_ids.c`.
- **k438b** (ADR 0013's held tail, no give-up): refuted as built. 1 GPU hang in 1 run (u438sH7), after five
  12-s host-made cycles: the join took a dcb's release into the held chain, and its acb waits for that release.
- **vg437** (exp 0437, folded in): no measurable gain in one V run against one C run; closed by the top session
  unless more data shows one.
- **C arm** (both off, test builds d4a2f86d and c4b23cd1): NO_CRASH in 3 of 3 runs, 36.91 (polled reads), 34.10 and
  34.52 flips/s.
- **Next, not done here:**
  1. decide title-side or host-side lateness with the catcher above;
  2. if the title rings the acb late, make the GFX wait safe (the GPU waits as the console's CP does) with its writer
     guaranteed a path to the GPU;
  3. if the host delays it, remove that delay at its source;
  4. a hold, if one is still wanted, needs ADR 0013 point 4 (submit up to the first unmet wait) built properly.
- The box has had two GPU resets since boot (u438sK2, u438sH7); no runs until it is rebooted.

## HANDOFF row draft

| F866 | **F865 was not F3's case: it was the F262 give-up.** Dcb chain #165177's pfp wait at dword 1285 on 0x12004b4c38 == 0 (busy 0x907616589 at submit) was given up by the game thread after 20.9 ms, with "no pending write", and dropped. It was the fourth give-up in a row (3c38, 4438, 4c38, 5438; ~83 ms). Its writer, acb #165180 (release at dword 2332), reached the host 20 ms after the dcb. At the stall the release had not run: the label still held the busy value. The acb's five dropped `== 0` waits were consequences: three of their labels are that dcb's own releases at dwords 8637, 11145 and 11340, which the GFX CP had passed. F2 cycles 0 all run. The first fix, k438 (exp 0438, `BC5_0438_KEEP`, keep the wait for the GPU instead of giving it up, with guards G1/G2), is refuted. u438sK2 (scene, RT on, test build d4a2f86d with k438 on) hung the GFX ring at ~90 s at k438's own kept wait: CP header history at dcb #65701's dword 369, a WAIT_REG_MEM64 pfp on 0x12004b5438. Its writer, acb #65702 (release at dword 874), was already in the kernel and did not run until the GFX job was reset (comp_1.1.0 timeout 2.05 s later). That fits a kernel-level dependency of the acb on the waiting GFX job; amdgpu's VMID flush is the candidate, TODO(verify). The C arm (k438 off): 1 run NO_CRASH, 36.91 flips/s, polled reads. The second fix, k438b (exp 0438, `BC5_0438_HOLD`: ADR 0013's held tail put back on the way-2 path, with no give-up), is refuted as built. u438sH7 hung the GPU at 113 s after five 12-s host-made cycles. Each time, the chain was held, and the join took a dcb whose release of 0x12004b77c8 precedes its wait on 0x12004b7838 into the held chain, while queue 1/0/0's acb waits for that release at its dword 28 and releases 0x12004b7838 after it. It broke only through the old 2-s acb timeout. The correct hold (ADR 0013 point 4: submit up to the first unmet wait) is not built. vg437 (exp 0437, folded in) showed no measurable gain in 1 V run against 1 C run (view builds 14076 against 15158). The C arm was NO_CRASH 3 of 3 (36.91, 34.10, 34.52 flips/s). Open: is the writer acb late on the title's side or the host's? u436sS3's records cannot tell (a catcher is proposed). Separate draft: host journal text found in guest memory (a NOP marker and the label 0x11e0450aa8 in u438sK2). | experiments/0438-f865-source/README.md; records `data-0438` (laptop), devcd 20261120-005901-devcd10, 20261120-081529-devcd1/2, 20261120-085542-devcd3/4 | high (the give-up cause, from the records); k438 and k438b each refuted on 1 hang in 1 run, with the mechanism read from the records |

## The generated units (not committed)

The two full units are not kept in git (the top session's review: 35k lines). They are made again from patch
bb04219b's tree unit (`a62e8bf6…`, exp 0436's `bake/bc5LleAgc.cpp`):
- `python -I mk0438.py ../0436-submit-unlock/bake/bc5LleAgc.cpp bc5LleAgc.cpp` → `680bda1f3430b676f2dadef8808ae24a`
  (k438, off unless set + k438b; test builds d4a2f86d used the earlier `59a5df70…`, c4b23cd1 this one plus
  `mkvg437.py` on the box copy); the change is `k438-unit.diff`.
- `python -I mkcat438.py ../0436-submit-unlock/bake/bc5LleAgc.cpp cat/bc5LleAgc.cpp` → `3623fd41142c49514fce913c34c2efab`
  (c438 with part 2, build c731c5fa; part 1 alone, build 8b2ae229, was `b7097917…`); the change is `c438-unit.diff`.
- `python -I mkr438.py cat/bc5LleAgc.cpp r438.cpp` → `94d696fbfe6cca223346ba255338a0f0` (r438 modes 1 and 2 + c438 with prep-pre by pass, build d59eae9b; the first r438 build 4b9ffcf8 was `1584911a…`);
  the change is `r438-unit.diff`.
`box0438.sh` pins the md5s (`K_UNIT`, `K_CAT`, `K_R438`) and expects the files at those paths in its kit directory.
