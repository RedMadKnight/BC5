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

## Result 10: build 10, stopped at the gate after one run (2026-11-20 15:26–15:35, boot eb264b8c, binary 3ff1d182)

**Build.** normal `3ff1d182af952e6d2a7402948a5c4f1d` (unit `a5629394…`), 0 errors and the 7 old warnings, built
under BOX-LOCK 15:26–15:27. Shared builds unchanged.

**The chain stopped by rule.** Its first run, u438sMC52 (MC: s438 off, on the UR base), ended NO_CRASH at
**32.89 flips/s**, with 218 s with a gap over 50 ms, 71 over 100 ms, pad keys 0 and 0 give-ups. That is under the
gate of 33.3, so the chain stopped. No M run was made, and there was no GPU line.
- The gate was set for a both-off control (C/UC).
- In result 9 the UR base ran 33.33, 33.43 and 34.75: it sits at the gate.
- Whether the box was slow or the gate does not fit this base is the top session's call.

**The s438 line from MC52 (scan on, t 420 s)** answers where direct_sync's time goes:
- **Passes:** 464,199 fast and 9,292 full. 2,826 of the full passes (30 %) were merge-only, the ones s438 would
  skip.
- **The full passes' time by part:** views 12.75 s, scan 7.78 s, merge 2.57 s, drain 0.11 s, **maps 16.12 s**.
- **The most s438 can save** is about 30 % of the scan, so about 2.3 s in 420 s, plus nothing of the views or maps
  time. **s438 is a small lever.**
- **The large parts are the mapping rebuild (maps) and the views list (views).** Both run when the title's mapping
  layout changes. That points to the map calls themselves, not to polling.

**The scan yield (a first answer to the maintainer's question, from MC52's journal, before y438).** These are BOs
imported by sync passes, from the journal's `+N BOs` lines, timed by the nearest earlier timed line:

| phase | sync lines with imports | BOs | pinned at the end of the phase |
|---|---|---|---|
| load (t < 60 s) | 323 | 430 | — |
| play (t ≥ 60 s) | 127 | 139 | 11,240 MiB at t 86 s → 11,742 MiB at t 421 s |

- **During play the syncs still find new data:** about 500 MiB in about 335 s, one or two chunks every 2–3 s. So it
  is not ~0.
- **Not yet separated:** scans against forced imports. k1f412 forced none ("k1 at the filter" lines: 0); ud434 logged
  22 user-data imports in play. y438 (`mks438y.py`, next build) counts by kind.
- **What this means for an event-driven design (an inference, not measured).**
  - On the console the GPU sees memory from the map call on. Here the title's direct memory is a memfd whose pages
    exist only once written, and the scan imports chunks when they first hold data (`SEEK_DATA`).
  - A first write to a mapped range is not a call the host sees. "Import at the map call" would mean importing
    (pinning) the whole mapped range at once, which is the eager-names path, at the cost of GTT for memory the title
    has not touched.
  - The play-time yield above is what that trade would have to cover.

**i438: the two unknown ioctls (MC52, 456 lines).** Every logged call had the same in-buffer:
- `0xc0088133` (8 bytes; 228 calls logged, all on Render Thread): in `00 00 00 00 01 00 00 00`;
- `0xc0108139` (16 bytes; 227 calls logged on Render Thread, 1 on game-main at t 0): in
  `00 00 00 00 01 00 00 00` followed by 8 zero bytes;
- out: zeros, as the host returns today.

Read as little-endian u32s, the in-buffer is {0, 1}, the same on every call. That fits a query or a toggle with a
fixed argument rather than a per-submit payload. TODO(verify): no public source names either request yet.

## Build 11: e438, the layout-change path made event-driven and incremental (design)

**The top session's decisions after result 10:**
- s438 is dropped. It is now off unless `BC5_0438_MERGESCAN=1`; the code stays, for the record.
- The next build is y438's records plus a lever on the layout-change path. It works the way the console does: a
  map, unmap or protect call updates only that range.
- First-write chunks stay on the scan for now. **This is the open part of the maintainer's question:** about
  500 MiB per 335 s of play are found by the scan, because the memfd's pages appear on the title's first write,
  not at a map call (result 10).

**Unit chain:**
1. `mks438y.py` on `s438.cpp` → `y438.cpp` (`7e338e9f…`);
2. `mke438.py` → `e438.cpp` (**`3fe3a79a459cb1ea60a7d27ff92f8c14`**, `e438-unit.diff`; the first version `850918e1` had the 2-s lazy-cover gap, rejected). Switch `BC5_0438_LAYOUT`: behaviour, so in lean too; on unless "0".

**Today (result 10, MC52, 420 s): 12.8 s of view builds and 16.1 s of mapping rebuilds.** Both run on every change
of the title's layout:
1. **The view list.** `direct_views` sees a new `Bc5MappedRangesGeneration`. For the direct-memory DState it rebuilds
   the list from all ~11,600 guest ranges (`direct_views_build`).
2. **The mapping rebuild.** `direct_sync_one` sees a new views signature. It drains, then rebuilds every wanted
   mapping:
   - every view against every BO it shows;
   - k1r412's read-only zero cover over every gap, with kl412's lazy-view rule;
   - then the sort and two walks over all of `S.maps` (about 17,000).

**e438, part 1: the views from the change records.** It reuses exp 0415's mr415 path in mode "views":
- The kept list is updated from `Bc5RangesDirtyTouching`'s records, the range table's own change log.
- mr415 S1 found it equal to the full build in 7,991 comparisons. The full build still runs every 2 s as a check,
  and at once after a record-log gap.
- Item V (exp 0432) was slower with this path. A likely reason, not measured: `x432_prev` always held a reference to
  the last list, so every change cloned the whole list (`views_clone`). Under e438 `x432_prev` holds nothing, so
  the records are applied in place when no one else holds the list. The `clones` counter shows whether that held.
- **Each change span is classified** by the direct views it overlaps before and after:
  - map (none before);
  - unmap (none after);
  - remap (they differ);
  - same (identical va, size, offset, lazy and eager: a protect or a rename);
  - other (no direct view).

  Every span except "same" and "other" is queued, with its record step (`DViews::e438_seq`), for the mapping side.

**e438, part 2: the mapping update for the touched intervals only** (`e438_maps`, under `g_dev_mutex`).
- **The touched va intervals come from two sources:**
  - (a) the queued spans up to the list's step;
  - (b) the BOs that differ from those the mappings were made with (imports, merges, cuts), as file intervals. Every
    view that shows such an interval adds its whole va range.
- **The intervals are grown until they stop growing:** to whole old mappings that overlap them, and to whole new
  views that overlap them. So every mapping lies wholly inside or wholly outside.
- **Inside, the wanted mappings are computed exactly as the old rebuild computes them** (the views' own, and the k1r412
  covers):
  - wanted old mappings stay;
  - others are unmapped;
  - missing ones are mapped, with the same zero-piece releases as the old add pass.
- **Outside, nothing is touched.**
- **The drain before the update is unchanged:** the same condition and the same drain as today.

| what | today | with e438 |
|---|---|---|
| guest range table → view list | full build per generation, under `direct_views`' mutex | records applied in place under the same mutex; full build every 2 s and after a gap |
| pending spans | – | `e438::mu` (its own mutex); written under `direct_views`' mutex, read under `g_dev_mutex` |
| `S.bos`, `S.maps`, the GPU VA map/unmap, `g_kl412` | `g_dev_mutex` | `g_dev_mutex`, unchanged |
| `e438::bos_at/have/seq_at/k1r_at/check_ns` (what the mappings were made from) | – | `g_dev_mutex` |

**Where the full rebuild (today's code) stays** (`m_why` counts each):
- the private DState;
- a list not made from records;
- a record gap, a kept-list mismatch, or a failed map in an earlier pass;
- an unsorted list;
- zskip;
- the g412 guard cap;
- the kc412 cover log;
- the first rebuild, and a device reopen (no mappings, or a new zero buffer);
- a list older than the mappings;
- no fixpoint in 16 rounds;
- **every 2 s per DState, as a check.** It runs the full rebuild even when nothing changed. The maps it adds or drops
  then are counted: anything other than 0 means the incremental path left a stale or missing mapping. It is also
  where kl412's lazy-view scan runs (see below).

**What e438 changes in behaviour, besides the time.**
- **Under lazy views** (the second title's four CPU-only heaps: Wwise, SoundAlloc, FileSystem, UIStringAlloc):
  **no change in freshness.**
  - The first design used kl412's known-written set with no new scan between the 2-s rebuilds. That would have let
    a written lazy chunk read as zeros on the GPU for up to 2 s. The top session rejected it: silent wrong data is
    worse than the named fault.
  - Now `e438_lazy_scan` runs kl412's scan at today's cadence, on the same 100 ms period and the same
    `g_kl412.begin()`. It asks `SEEK_DATA` of every chunk under a lazy view's zero cover, as `k1r412_want` does.
  - When the known-written set changed (a chunk was written, or freed), the pass falls back to the full rebuild.
    That rebuild's `k1r412_want` then uses the fresh set (`m_why[11]`, "lazy chunk written").
  - Between scans both paths use the same known set, so a zero cover sits on a written lazy chunk at most until the
    next scan, as today.
  - **New counter, on both paths** (also in today's `k1r412_want`): the lazy chunks taken out of a zero cover, the
    scans, and the time since the scan before (average and longest). That time is how long each chunk can have sat
    under the cover.
- **A missed record** would leave a view without its mappings (a GPU fault in a mapped range) or keep mappings of an
  unmapped one (the GPU reads pages the title gave back). The 2-s check and the full-build check bound that to
  2 s, and both count it.

**Records** (normal build; 60-s lines from `direct_sync`):
- `e438 layout`, for load and for play: change spans by class (map, unmap, remap, same, other), with MiB and a size
  histogram;
- `e438`: incremental updates (time, intervals, views, maps +/−), full rebuilds (time; the 2-s checks and their
  changes), the reasons for each full rebuild, record gaps, kept-list mismatches, view builds and clones;
- y438's scan yield by kind and phase, and the layout and mapped-range generation changes.

**The offline test** (`test_e438.sh`; on `3fe3a79a`: PASS, 7,200 random steps in 60 scenarios, 4,677 incremental and 2,523 full because a lazy chunk was written, every step equal to the full rebuild; the lazy case: a 50 ms clock step, random writes into lazy views' chunks, and no zero cover may sit on a written lazy chunk 150 ms or more after the later of the write and the cover's appearance; 3,734 chunks taken out of a cover in 3,600 scans, longest wait 100 ms. Two broken copies FAIL: BO tracking left out, at scenario 0 step 7; the lazy scan left out, at scenario 0 step 3. A test bug found on the way: the fake zero buffer's id 999 collided with BO ids, now 0xfffffff0): it cuts e438's pieces from the unit and runs `e438_maps` against the full
rebuild. It uses random view lists (unmaps, shrinks, remaps, splits, protects, new views, lazy views, aliases) and
random BO lists (imports, merges, cuts) on a fake device. After every step:
- `S.maps` must equal the full rebuild's list;
- the device must hold exactly `S.maps`;
- no map may land over another mapping, and no unmap may miss.

**Chain** (clean boot, his scene, RT on, the same gates):
- Order: `LC L LR` × 3.
- LC = control: `SPLIT=1 EARLYREG=0 LAYOUT=0 MERGESCAN=0`. The gate: the first LC run at ≥ 33.3 flips/s.
- L = `LAYOUT=1`.
- LR = `LAYOUT=1 EARLYREG=1`.
- **Refuted if:** L or LR shows a GPU line, a visual change the control does not show, or a nonzero 2-s check
  change.

## Result 11: build 11 (e438) on a clean boot (2026-11-20 16:18–17:27, boot eb264b8c, 0 GPU reset lines, binary 88a67303)

**Build.** Normal `88a673030a3fd26ba3bc3d5e1b71ef56` (unit `3fe3a79a…`), 0 errors and the 7 old warnings, built under
BOX-LOCK 16:18–16:19. Shared builds unchanged.

**Chain.** `LC L LR` × 3 ran to its end: 9 of 9 NO_CRASH, pad keys 0, no GPU line. The gate passed: the first LC was
at 33.61. Raw: `raw/e438-chain-out.txt`, `raw/e438-chain-rows.txt`.

| arm | flips/s | s with a gap > 50 ms | > 100 ms | give-ups | own `prep-direct-sync` (s) | views (s) | maps (s) | 2-s check changes |
|---|---|---|---|---|---|---|---|---|
| LC (control) | 33.61, 32.76, 32.92 | 222, 221, 218 | 74, 82, 84 | 2, 1, 2 | 23.6, 18.5, 19.5 | 12.3, 10.9, 11.2 | 16.7, 13.6, 13.3 | – |
| L | 33.92, 32.78, 33.16 | 212, 214, 213 | **98, 113, 109** | 0, 1, 0 | 31.4, 35.5, 34.7 | **24.7, 26.6, 26.5** | **7.0, 7.6, 7.4** | +0 −0, **+0 −4**, +0 −0 |
| LR | 34.58, 31.78, 33.75 | 206, 220, 217 | **90, 124, 99** | 0, 0, 0 | 31.7, 37.3, 32.7 | **24.0, 28.7, 24.7** | 7.2, 7.7, 7.3 | (not read), +0 −0, **+0 −1** |

The views and maps figures are s438's full-pass time by part. LC runs 2 and 3 and LR run 1 report at 360 s; the
others at 420 s.

**Verdict: refuted under the top session's rule.** Two L/LR runs show nonzero 2-s check changes (u438sL66 −4,
u438sLR70 −1). Frames over 100 ms rose from 74–84 to 90–124. flips/s overlap.

**What the records show.**
- **The incremental mapping update works and is cheaper.** Mapping time fell from 13.3–16.7 s to 7.0–7.7 s:
  - about 5,000 incremental updates a run, about 1.2 ms each;
  - about 22 views and maps +20 / −14 per update;
  - about 235 full rebuilds: the private DState, about 23; the lazy fallback, 6–9; the 2-s checks, 205.
- **The change-record view list made the views slower**, 24–29 s against 11–12 s.
  - The title's layout changes are many and spread: in play about 4,000–5,000 generation changes per 300 s, but
    280,000–310,000 change spans, about 60 spans per change, 120,000 of them under 64 KiB.
  - Applying them one by one cost more than today's full build per change. This is the regression in long frames:
    bc5-ring's own `prep-direct-sync` rose from 19–24 s to 31–37 s.
- **Lazy freshness was worse than today in build 11.**
  - Chunks taken out of a zero cover: 87–90 in every arm. In L and LR, though, the time since the scan before was
    about 1.0 s on average (longest 1.3 s), against 0.15–0.18 s in LC (longest 0.27–0.43 s).
  - The cause: e438_lazy_scan ran only inside `e438_maps`, so most changes were found by the 2-s check's old
    rebuild. That is also the likely source of its −4 and −1: covers dropped over written lazy chunks.
  - Build 12 runs the scan in every full pass, before the drain decision.
- **No record gaps or kept-list mismatches; clones 1–2.**

**The scan yield** (y438; the maintainer's question), per run in play (t ≥ 60 s):
- change-driven scans: 3,900–5,400 passes, importing 461–580 chunks, 0.9–1.2 GiB;
- merge-only scans: 2,000–2,500 passes, **0 chunks**;
- forced: 64–78 passes, 0–118 chunks.

Load (t < 60 s): forced 2,134 chunks, change 3,600 chunks, merge 0.

So during play, new data is found by the scans triggered by a change, about 1 GiB per run. The merge-only scans find
nothing. That confirms s438's skip was safe, though small.

## Build 12 (prepared offline, not built): the mapping index updated in place, no full rebuild after the first

**The ask.** The maintainer, through the top session: "a full rebuild shouldn't be needed; an update of the mapping
index is enough".

**Unit chain:** `mkf438.py` on `e438.cpp` (`3fe3a79a…`) → **`346ebf6efa736bdbc5bf054901f40253`** (`f438-unit.diff`).
The switch is still `BC5_0438_LAYOUT`. The first form, `beb28ae0`, still used build 11's change-record view list. Result 11
showed that list is slower than today's build, so it is dropped: the view list is built as today, and the layout
statistics now come from the tuple diff.

**What changes against build 11.**
1. **Touched intervals come from a diff, not the records.** Each DState keeps a copy of the (va, size, offset, lazy,
   eager) tuples of the view list its mappings were made from. The current list is diffed against that copy (both
   rise by va); the pending queue and its step numbers are no longer read.
   - So a record gap, a kept-list mismatch, a list not made from records, the private DState and a list older than
     the mappings are all ordinary diffs, not reasons for a full rebuild.
   - The records still feed the view list (the 12.8 s) and the layout statistics.
2. **A lazy chunk is a local update.** kl412's scan runs in `direct_sync_one` before the drain decision, at today's
   cadence. A chunk whose written state changed goes into the drain condition, as today's rebuild drained, and
   becomes a touched interval: the lazy views that show it are recomputed.
   - Their zero cover on a written chunk goes.
   - If the chunk is imported, its BO mapping comes through the BO diff.
   - A written lazy chunk that is not imported stays unmapped and faults by name, as today. Importing it would undo
     F394's 242 MiB; that needs a decision of its own.
3. **A failed map is retried** on its own interval at the next update (`e438::retry`); no full rebuild.
4. **The growth runs until it stops.** It only grows, inside a finite set of endpoints, so it needs no cap.
5. **What can still take the old rebuild:**
   - the first build of each DState, and a device reopen (no mappings, or a new zero buffer);
   - an unsorted list. It cannot occur: the direct views are the guest range table's ranges, which are disjoint by
     construction (`VirtualRanges`), and the private views are the address space's map. It is counted as a bug.
   - zskip (`BC5_DIRECT_ZERO_SKIP`), the g412 cap (`BC5_GUARD_CAP_ACT`) and the kc412 cover log
     (`BC5_GUARD_COVER_LOG`). These are environment switches read once at start and unset in every launcher; exp 0419
     took zskip and the pin cap out of the defaults. They cannot turn on during play. In a diagnostic run with one
     set, the old rebuild is used, and counted.
6. **The 2-s check is a diagnostic** (`#ifndef BC5_LEAN`, so not in lean).
   - It compares `S.maps` with the full list made the old way (`e438_full_want`: every view's own mappings and
     covers, from the same known-written set).
   - A difference is journaled as a BUG with its extra and missing counts. It is not repaired.

**The offline test** (`test_f438.sh`): the same equality checks as test_e438, on 80 scenarios. Every fourth is the
private DState; every fifth has maps that fail 3 % of the time. It also checks:
- the unit's own diagnostic list against the test's;
- **0 full rebuilds after the first**.

PASS:
- 9,600 steps, all incremental, 0 full rebuilds after the first;
- 2,194 local lazy updates and 841 retry rounds;
- 2,946 lazy chunks taken out of a cover, longest wait 100 ms;
- 9,600 diagnostic lists equal.

Two broken copies FAIL: the local lazy update left out (scenario 0, step 0), and the retry left out (scenario 1,
step 3).

## Result 12: build 12 on a clean boot (2026-11-20 17:32–18:41, boot eb264b8c, 0 GPU reset lines, binary 577aa2e2)

**Build.** Normal `577aa2e25da266685625c2542c1f49d2` (unit `346ebf6e…`), built under BOX-LOCK 17:32–17:33. Shared
builds unchanged.

**Chain.** `LC L LR` × 3 ran to its end:
- 9 of 9 NO_CRASH, pad keys 0;
- GPU timeout or reset lines: 0 at the start and 0 after the end;
- the gate passed: the first LC ran at 35.10 flips/s.

Raw: `raw/f438-chain-out.txt`, `raw/f438-chain-rows.txt`.

| arm | flips/s | s with a gap > 50 ms | > 100 ms | give-ups | own `prep-direct-sync` (s) | maps (s) | e438 BUG lines |
|---|---|---|---|---|---|---|---|
| LC (control) | 35.10, 33.48, 33.61 | 204, 225, 214 | 63, 76, 71 | 1, 2, 1 | 20.8, 23.5, 22.1 | 15.0, 16.4, 16.5 | – |
| L | 34.31, 32.93, 35.70 | 217, 222, 199 | 73, 76, 66 | 2, 1, 0 | 18.2*, 22.5, 18.2* | 12.3*, 15.5, 12.3* | 0, 0, 0 |
| LR | 33.25, 34.79, 32.82 | 221, 207, 221 | 68, 66, 73 | 0, 0, 0 | 17.5*, 20.8, 24.2 | 12.4*, 13.9, 16.2 | 0, 0, 0 |

\* These runs report at 360 s. All other runs report at 420 s.

**The view-list build time per run** (s438's full-pass "views" part, as the top session asked; the next candidate):

| arm | run 1 | run 2 | run 3 |
|---|---|---|---|
| LC | 10.8 s | 12.9 s | 12.5 s |
| L | 9.4 s* | 13.1 s | 9.9 s* |
| LR | 9.4 s* | 12.2 s | 13.9 s |

The view list is built as today in every arm, so these are today's cost. Over 420 s it is 12–14 s; scaled to 420 s,
the 360-s runs come to 11.0–11.6 s. The other full-pass parts:
- scan: 6.5–8.6 s;
- merge: 1.7–2.5 s;
- drain: 0.1 s in LC, 0.66–0.85 s in L and LR. Lazy changes now drain too.

**Verdict under the top session's rule: not refuted.**
- 0 GPU lines.
- 0 BUG lines from the 2-s check, in 2,272 checks: 348–408 per run, each with 0 extra and 0 missing.
- New visuals: not checked. The runs were scripted with no one watching.

Build 11's regression is gone:
- frames over 100 ms are 66–76 in L and LR, against 63–76 in LC (build 11: 90–124);
- the views take as long as in LC;
- flips/s overlap.

**But the gain is mostly gone too, and one condition is not met.**

1. **Maps: about 1 s per 420 s saved, not build 11's 7 s.**
   - At 420 s: L/LR 13.9–16.2 s against LC 15.0–16.5 s. Scaled to 420 s: L and LR 14.3–16.2 s.
   - The incremental updates run as planned: 4,400–5,800 per run, about 22–25 intervals and views each, maps +23 / −16.
   - The only full rebuilds are the 2 first builds per run. No reopen, unsorted list, zskip, g412 or kc412 rebuild,
     and 0 retries.
   - Each update now costs **2.4–2.5 ms, against about 1.2 ms in build 11**.
   - A candidate, not checked: build 12 diffs the whole tuple list, about 11,600 entries, and copies it (prev_v) on
     every update. Build 11 read only the change records.
   - bc5-ring's own `prep-direct-sync` is 17.5–24.2 s in L and LR, against 20.8–23.5 s in LC: the same range.
2. **Lazy freshness is not about 100 ms; it stays about 1 s, as in build 11.**
   - L and LR: chunks taken out of a zero cover 87–90 per run, 918–1,009 ms on average since the scan before, longest
     1.2–1.3 s. One LR run: 474 ms, longest 611 ms.
   - LC: 148–184 ms, longest 430–448 ms.
   - Build 12 runs the scan before the drain decision on every full pass, 2,000–2,500 scans per run against LC's
     1,600–1,700. Even so, the chunks found sat longer. Local lazy updates: 9–11 per run.
   - Why is not explained. The row has no time-split of these waits (load against play), and the scan runs only on
     full passes, as LC's does. The top session's condition (keep about 100 ms) **is not met by build 12.**
3. **r438 BUG lines in LR (seen now; missed in Result 11).**
   - LR74: 1. Build 11: LR67 2, LR70 2.
   - Each one is the r438 watchdog line "a game-thread wait … has waited 100.0 ms for an early-registered writer to
     reach the ring". The longest of these waits were 100.7, 168.9 and 146.0 ms. Of 31,000–35,000 such waits per run,
     the total is 17–20 s.
   - Its invariant still held: early writes that never reached the ring: 0.
   - This is r438's arm (EARLYREG=1), not e438. It is a slow wait, not a lost write. It is still a BUG line by r438's
     own rule, and the >100 ms waits sit on the game thread.

**Where it stands.** Updating the mapping index in place is correct by every check:
- 0 differences in 2,272 full comparisons;
- 0 full rebuilds after the first;
- 0 GPU lines.

On this scene it is barely faster than today's merge rebuild, and its lazy freshness is about 1 s. Not proposed for
the shared builds as it is. Next, if pursued:
- per-update time without the whole-list diff (the touched va range from the BO diff and the generation);
- the lazy waits split by load and play, to find why the scan finds chunks late.

The view list (11–14 s per 420 s) is the larger cost and is the next candidate, event-wise, as the top session
decided.

**Closed (the top session, 2026-11-20, after Result 12).**
- e438 is closed: there will be no build 13, and it does not go to the shared builds.
- **Build 12 has a defect: do not reuse it as it is.** In the L and LR arms (`BC5_0438_LAYOUT=1`), a written lazy chunk
  stayed under a read-only zero cover for about 1 s (up to 1.3 s). The required freshness was about 100 ms.
- The device-mutex line (u438, s438, e438) gave about 1–2 s per 420 s and no change at the frame level in 4 builds.
  No more mutex levers are added.

## Frame-time budget of his scene (offline, from a journal already on the laptop; no box)

**Source.** u436sS3's `direct.log`, copied to `data-0438/` for Result 1:
- the shared normal build `f345db74`, his 09:46 scene, RT on, 4 rings;
- its frame-profile lines, one per flip, written by `frame_profile_flip` in the unit.

The scene starts at t ≈ 120.6 s, when the rate rises after the second load. From there to the hang at 188.7 s there
are 2,621 frames, 38.6 flips/s. One 3.4-s frame at the load's end is left out.

This is **one run and 68 s** of the scene. The chain runs' journals on the box have the same lines, about 10,000 frames
a run, if a check is wanted. Tool: `fp0438.py` (`python fp0438.py <frame-profile lines>`).

**What the fields are** (unit lines 14,655–14,750 and 15,279):
- **interval:** time from flip to flip.
- **inside:** the render thread's time in our submit path. Its parts:
  - sync: probe + anon sync + direct sync, including the device-mutex acquire;
  - hints;
  - prepare;
  - cs: the ioctl;
  - label waits and event waits.
- **at the flip:** `Direct::drain()` in SubmitFlip, the wait until the frame's jobs are done. Flip-defer is off.
- **outside:** interval − inside − at the flip. This is the render thread outside our submit and flip: the title's own
  CPU work, its waits on its other threads, and HLE calls not profiled here.
- **GPU busy:** the union of each job's [queued, completion seen) over the frame. It covers the game thread's jobs and
  bc5-ring's (way 2: the GFX and compute rings together). Queueing in the kernel and the completion thread's
  latency are included, so this is an **upper bound** on the GPU's execution time.

| frames | n | share of the time | interval (ms) | GPU busy | at the flip | inside (sync / prepare / cs) | outside |
|---|---|---|---|---|---|---|---|
| typical, 15–40 ms | 2,361 | 72 % | 21.9 (p50 20.8) | 13.1 (60 %) | 5.3 (24 %) | 5.7 (1.3 / 2.0 / 2.0) (26 %) | **10.9 (50 %)** |
| 40–100 ms | 239 | 18 % | 55.0 | 14.1 (26 %) | 5.8 (11 %) | 27.4 (**19.1** / 2.3 / 2.2) (50 %) | 21.8 (40 %) |
| over 100 ms | 21 | 9 %* | 151.2 | 27.5 (18 %) | 5.6 (4 %) | 41.7 (27.6 / 4.8 / 4.5) (28 %) | **103.9 (69 %)** |
| all | 2,621 | | 25.9 | 13.3 (51 %) | 5.4 (21 %) | 8.0 (3.2 / 2.0 / 2.0) (31 %) | **12.6 (49 %)** |

\* The 9 % includes the 3.4-s frame. Without it, over-100-ms frames are about 5 % of the time.

Typical frames, p10 / p50 / p90:
- interval 18.6 / 20.8 / 26.3;
- GPU busy 11.3 / 12.9 / 14.7;
- at the flip 3.5 / 5.3 / 7.0;
- inside 3.8 / 4.8 / 6.9;
- outside 9.0 / 10.7 / 12.9.

Label waits on the render thread are 0.0 in every class. Per frame: jobs 7.5 from the render thread and 23.1 from
bc5-ring.

**Reading.**
- **The scene is host-bound, not GPU-bound.**
  - Even as an upper bound, the GPU is busy 60 % of a typical frame and 18 % of a frame over 100 ms.
  - 1 frame in 2,621 has GPU busy ≥ 90 % of its interval.
  - A GPU-bound frame would show the render thread waiting at the flip most of the frame. It waits 5.3 ms of 21.9.
- **The biggest share is "outside": the render thread outside our submit and flip.**
  - It is 10.9 ms (50 %) of a typical frame and 104 ms (69 %) of a frame over 100 ms.
  - This journal cannot say what it is: the title's own CPU work, a wait on its own workers (whose jobs may wait on
    the host), or an unprofiled HLE call.
- **Second: the wait at the flip,** 5.3 ms (24 %). This is the GPU finishing the frame's last jobs, which bc5-ring
  submits about 23 of.
- **Our submit path on the render thread is 26 % of a typical frame** (prepare 2.0, ioctl 2.0, sync 1.3).
  - In 40–100 ms frames, sync is the largest host part (19 ms). In 5 of the 21 frames over 100 ms, sync is 66–112 ms.
  - Sync includes the device-mutex acquire. That is the line the top session stopped.
- **bc5-ring's prep is not in this profile.** It reaches the frame only through the wait at the flip and through
  sync's mutex wait.
- **The r438 and F262 waits:**
  - In this run (the shared build, r438 off), label waits were 0 on the render thread in every frame.
  - In r438 runs, the chain rows give 31,000–36,000 game-thread waits for an early writer, 17–20 s per 420 s: about
    4–5 % of the time.
  - Those runs' journals are on the box, so these waits are not placed in frames here.

**What the journals cannot answer:** what "outside" is made of. Splitting it needs a records-only item: the render
thread's time in the title's other HLE calls (semaphores, event flags, equeue waits, sleeps), with the waker thread
where there is one. That is a build item, and is asked for first, as the top session ruled.

**Measured on normal builds only (the maintainer, through the top session, 2026-11-20).**
- Every flips/s figure in this experiment comes from normal builds, with their catchers and journal lines on: results
  2–12, u438, s438, e438, r438. That includes every "no gain" and "no cost" reading. The diagnostics cost frame time
  themselves, so these comparisons may be biased.
- u438's and e438's "no frame-level gain" were **not checked on lean**.
- The frame-time budget above comes from a normal build with the frame profile on. Its shares may be distorted by the
  profile's own cost: a mutex and counters per submit and per job, a journal line per flip. The catchers add more.
- From now on a gain or a cost counts only from lean against lean, read from MangoHud's per-frame log: median, p95 and
  p99 frame time, plus mean flips/s.

## The lean round's kit (b438; prepared offline, not built)

**Unit.** `mkb438.py` on the shared tree's unit (`a62e8bf6`, patch bb04219b) → b438
**`7218cab6684267d51701159397ce7902`**. It is r438 alone, in the shape a bake would take:
- No c438, k438, u438, s438 or e438. Mode 1 only, since r438a's mode 2 never fired.
- `BC5_0438_EARLYREG` is on unless "0". It is behaviour, so lean reads it too.
- Lean keeps the early registration, the game-thread poll and the removal of a lost write's early entry.
- Normal only: the counters, both BUG lines and a 60-s line `r438 (exp 0438, b438)`.

**Test.** `bash test_b438.sh` (test_r438's cases, with the mode-2 case made a mode-1 case) PASSES in five
configurations:
- normal with the switch unset, =1 and =0;
- lean (`-DBC5_LEAN`) with it unset and =0.

On the laptop, case 1's wait (the writer registers 30 ms after the game thread starts waiting) took 60–175 ms, and in
3 of 6 runs it crossed the 100-ms BUG line. So case 1 checks for no lost write, not for "no BUG line".
- A candidate, not checked on the box: the poll holds `g_plw_mutex` while it scans `g_plw` (up to 8,192 entries) and
  sleeps only 20 µs between scans, so the writer's `register_label_writes` can be held off.
- Not changed: it is a behaviour change, for the top session to decide.

**Runner.** `mkrun0438l.py` makes `run0438l.sh` (`7c6da668`). It is exp 0432's scene runner (`2d11fd6b`) with exp
0430's `mkrun0430l.py` hunks applied unchanged:
- N_MH: MangoHud's own per-frame log, an invisible overlay, every frame;
- N_LEANSESS: the Plasma shell stopped for the run, as the lean shortcuts do;
- P_HOST: off, the distrobox as before;
- the checks at 30 s and at G+60.

The timed-route hunks are skipped, since the runner already has them.

**Chain.** `chain0438l.sh`. Every arm runs the same way:
- the route by time: cross at 90 s, slot 4 at +8, Continue at +8, G at +20 = 126 s;
- MangoHud's log as the one counter, written before the run ends;
- G+300.

| arm | build | `BC5_0438_EARLYREG` | other |
|---|---|---|---|
| L0 | lean b438 | 0 | |
| L1 | lean b438 | 1 | |
| N0 | normal b438 | 0 | the usual journal words |
| O | normal b438 | 0 | `BC5_0438_OUTSIDE=1`, if built |

Gate: the first L0 at ≥ 33.3 flips/s.

**Statistics.** `mh0438.py G FROM TO csv...` gives, per run:
- frames and mean flips/s;
- frame time median, p95, p99 and max;
- frames over 50 and over 100 ms;
- the share of the time spent in frames over 50 ms.

**Build.** `box0438.sh buildb` builds normal and lean from b438 with each shared build's own command, and stops if the
lean binary holds r438's journal strings.

### The lean round's kit, second form (the top session's additions, fixes first)

1. **PLWCV** (`BC5_0438_PLWCV`, on unless "0", read in lean too).
   - The game thread's wait for an early writer sleeps on `g_plw_cv`, at most 10 ms per sleep, and the wait goes on.
   - The condition variable is signalled when a job registers its writes, and at the slice's end.
   - "0" keeps r438's 20-µs poll.
   - test_b438 case 6 measures the time from the writer's registration to the game thread's return, 20 rounds on the
     laptop:

     | wait | median | p90 |
     |---|---|---|
     | condition variable | 0.06 ms | 2.5–15 ms |
     | poll | 4.9–7.0 ms | 18–19 ms |

     The condition variable's long tail is the laptop's scheduler.
2. **Lean lost-write counter.**
   - Lean counts the early writes that never reached the ring. The first one prints one stderr line (in play.log),
     and the total is printed at a normal exit.
   - A SIGTERM from the runner ends the process without that total, because the tree installs no handler. So in a
     chain run the first-line count is the record: 0 lines means no lost write.
3. **o438** (`o438.hpp`, `mko438.py`): normal build only, off unless `BC5_0438_OUTSIDE=1`.
   - Wait spans sit in the sync HLEs: sema, posix and pthread sem, event flag, mutex lock, cond wait, equeue,
     usleep, nanosleep, sync-on-address, join, yield.
   - Signal marks give the waker's tid for the object: unlock, cond signal, broadcast and signalto, sema signal,
     posts, set event flag, the equeue triggers, sync-on-address wake.
   - Recorded for the Render Thread and game-main. Only a thread's outermost span counts. A span of 50 µs or more
     counts as blocked, and its waker is the last signaller of its object.
   - Output (stderr): each frame over 100 ms with both roles' waits and their wakers, and the totals every 60 s.
   - `test_o438.sh` (stub POSIX headers on the laptop) PASSES with the switch =1 and unset, and in lean. Its cases:
     the waker is attributed, a nested lock counts once, a thread of neither role records nothing, one frame line for
     a long frame and none for a short one.
   - `box0438.sh buildb` compiles the six tree files with o438 into the normal build only.

Units:
- b438 `9035b9defc7a923f656527c65821bb87`;
- mko438's output on the tree files, pinned by their LF md5s.

Chain order: `L0 L1p L1c` ×3, then `N0`, then `O O` (the records runs, not pooled with the lean comparison).

### p438: the prologue merge (the maintainer's word, 2026-11-20)

**The switch.** `BC5_0438_PROLMERGE` is on unless "0", and lean reads it. It is a behaviour change, in b438 (unit
`a31a2091ddeed206db7daec79771e932`).

**What it does.**
- 0xc0488131 no longer submits on its own. Its context-control dwords and 3 header IB packets are copied to one of 64
  stable slots: the soft CP may still read a submitted prologue's dwords.
- The next 0xc0188132 submits them at the head of its own chain, ahead of its DCBs: the same buffers, in the same order,
  on the same ring, in one kernel submit.
- Two prologues before a submit stay in call order.

**When it is not merged** (each case is today's separate submit):
- Pending prologues are flushed alone before any other gc submit (0xc0108102, 0xc020810c), at "submit done" and
  "wait idle", and at the EOP flip.
- A prologue is submitted alone at once:
  - when a header IB writes memory or nests an IB (RELEASE_MEM, EVENT_WRITE_EOP, WRITE_DATA, DMA_DATA,
    INDIRECT_BUFFER): a CPU waiter may need that write before the next submit;
  - when 8 are pending;
  - with the acb rings off (`w428_rings() == 0`), since the acbs then share the GFX ring.
- A device reopen needs nothing: the slots are host copies, submitted later like any buffer.
- At exit a pending prologue is dropped: the emulator ends anyway.

**Records** (normal only): a 60-s line `p438 (exp 0438)` counting merged prologues, and those sent alone by reason.
Pending prologues flushed because a writing prologue followed are counted under "writes".

**Test.** `test_p438.sh` cuts p438's block from the unit and models gc_ioctl's cases with the hooks where mkb438.py puts
them. It runs 400 random scenarios (48,457 steps); every tenth has the acb rings off. It PASSES:
- the buffers handed over are identical with the merge on and off;
- with the merge on, submissions are off minus the merged prologues (9,739 merged);
- no prologue that writes memory is kept (1,204 sent alone);
- nothing is merged with the rings off.

Two broken copies FAIL:
- the pending prologues taken in reverse order (354 failures);
- the check for header IBs that write memory left out (723 failures).

`test_b438.sh` still passes, 7 of 7.

**Chain.** The order is `L0 L1p L1c LP` ×3, then `N0 O O`: 15 runs.
- LP = `EARLYREG=1 PLWCV=1 PROLMERGE=1`.
- Every other arm has `PROLMERGE=0`.

**The maintainer's rule (2026-11-20, through the top session).** Performance tests run on lean builds only. Normal
builds are for diagnosis, never for fps or frame-time comparisons.
- N0 is dropped.
- O O stay as diagnosis runs, and their rows report no fps.
- ORDER: `L0 L1p L1c LP` ×3, then `O O`.
- Every normal-build number in this README (results 2–12, the budget) is a **diagnosis** number, not a performance
  result.

## Result 13: the lean round (2026-11-20 21:27–23:20, boot eb264b8c, lean d4d2ab82, normal 8f622148)

**Pre-checks (top's GO, 21:26).**
- 0 GPU reset or timeout lines on this boot. The only `dmesg` match was bc5-gpu-watch's boot line.
- No emulator running, BOX-LOCK empty.
- No scp, rsync or md5sum running; only the idle `nfsiod` kernel worker.

**Build (BOX-LOCK 21:27–21:31).** `box0438.sh buildb` first stopped in mko438.py. Three of the tree's six files are
CRLF on the box (semaphore.cpp, eventFlag.cpp, pthread.cpp), and their pins are LF md5s. mko438 now:
- pins and patches the LF form;
- writes each file back in its own line endings (mko438.py `4513a0ec`, box0438.sh `4f958591`).

Before the build it was dry-run on the real tree; all marks applied. Build results:

| Build | md5 | Errors | Warnings | Contents |
|---|---|---|---|---|
| lean | `d4d2ab82a4245e45f43e31f09ad23e80` | 0 | 8 | EARLYREG, PLWCV and PROLMERGE; no journal lines, no o438 |
| normal | `8f622148de65df63ebe2d821e85ec383` | 0 | 15 | the same three switches, plus the r438 and p438 lines and o438 |

The shared builds are unchanged (f345db74 / 6a735b81 / d6638808, tree unit a62e8bf6).

**Chain.** chain0438l (`55740c7f`), runner `7c6da668`, his 09:46 scene, RT on, way 2's words, PLAY 300 s. It ran
under the user manager (`systemd-run --user`, unit chain0438l). One laptop ssh blocked on `systemctl --user
is-active` and read nothing until the unit ended.
- Runs 327–340, all 14 NO_CRASH.
- GPU timeout/reset lines: 0 at the start, 0 at the end.
- Lean lost-write lines: 0 in every run.
- Kernel lines: runs 327–329 each have two drm `Unsupported screen format RA24` display messages, not GPU faults.
- **LP334 is void.** It had 428 pad keys (his input) and is left out of the verdict. Its numbers are listed only in
  `lean-round/mh0438-out.txt`.

**Lean numbers.** These are the performance result, lean against lean. They come from MangoHud's per-frame log over
G+10 to G+290, which is clipped by the log's end to 275 s in every run. Tool: `mh0438.py 126 10 290`; output in
`lean-round/mh0438-out.txt`.

| Arm | Runs | flips/s per run | Mean flips/s | p50 ms | p95 ms | p99 ms | Time in frames > 50 ms |
|---|---|---|---|---|---|---|---|
| L0 (control) | 327, 331, 335 | 35.32, 34.98, 35.68 | **35.33** | 17.0 / 16.9 / 17.0 | 66.5 / 66.6 / 50.6 | 99.9 / 100.0 / 99.9 | 26.3 / 28.2 / 24.2 % |
| L1p (r438, poll) | 328, 332, 336 | 34.31, 34.52, 35.61 | **34.81** | 17.1 / 17.0 / 17.1 | 66.7 / 66.6 / 50.6 | 99.9 / 100.0 / 99.8 | 28.7 / 28.1 / 23.6 % |
| L1c (r438, CV) | 329, 333, 337 | 35.39, 36.11, 33.60 | **35.03** | 16.9 / 16.9 / 17.1 | 66.5 / 50.5 / 66.7 | 99.9 / 99.8 / 100.1 | 26.8 / 23.9 / 31.3 % |
| LP (L1c + p438) | 330, 338 (334 void) | 35.24, 34.23 | **34.74** | 17.0 / 17.0 | 66.6 / 66.7 | 99.8 / 100.0 | 27.3 / 29.2 % |

- The arm means are within 0.6 flips/s of each other. Within each arm, runs differ by up to 2.5 flips/s (L1c: 33.60
  to 36.11).
- Median, p95 and p99 are the same across arms. p95 is either 50.5 or 66.7 ms in every arm, which fits frame times
  quantised to whole vblanks of 16.7 ms.
- **Verdict (perf): no measurable effect.** This holds for r438 in either wait form (poll or condition variable) and
  for p438's prologue merge, with no gain and no loss beyond run-to-run spread, in 3 + 3 + 3 + 2 lean runs. r438 is a
  correctness fix (F865's source), and on these numbers its bake costs no frame time. The poll against the
  condition-variable choice makes no difference to frame time; CV is the one offline test case 6 found faster to
  wake (0.06 against 4.9–7.0 ms median). p438 gives no gain, so it has no performance case for a bake.

**Diagnosis runs (O339, O340; normal 8f622148, `BC5_0438_OUTSIDE=1`, EARLYREG=0 PROLMERGE=0): diagnosis only.**
These are cumulative o438 totals from the start to the end of the run (load included, ~14,000 frames). Files:
`lean-round/b438O33*-o438-last-totals.txt`.
- **The Render Thread barely waits in the title's own syncs.**
  - Mutex lock: 2.29 M / 2.10 M calls, 432 / 390 ms in total, longest 1.3–1.5 ms; nearly all uncontended.
  - Cond wait: 11 calls, 16–21 ms, woken by "Coherent Layout".
  - No semaphore, event flag, equeue or sync-on-address wait.
  - In the 126 / 141 frames over 100 ms, its recorded waits add up to 7.5 ms in total.
  - So its ~9 ms per frame of "other waits" (exp 0432's perf, d432S16) is not in the guest sync HLEs. It is host
    side: our gc ioctls, the flip, host locks or the kernel (TODO(verify): the next profile should split these).
- **game-main waits for the Render Thread.**
  - Cond wait: 137.8 / 136.9 s over the run (about 9.8 ms per frame), with 135.0 / 133.3 s of it woken by the Render
    Thread. Longest single wait 100.1 ms, which is the title's timed wait.
  - Its semaphore waits total 5.8 / 5.2 s, woken by Havok Solve and Havok Queries.
- So the frame is paced by the Render Thread's own work, not by any wait it makes on the title.
- GIVEN UP lines: 2 in O339 and 1 in O340, in the normal build's direct.log, with EARLYREG off (as in the shared
  builds).

## Frame pacing in the lean round (offline, from the 11 valid lean MangoHud logs; no box)

The top session asked whether the pacing is two-moded: p50 is 16.9 ms while the mean is ~35 flips/s, so are frames
either one vblank or 3+? Two tools answer it, using the same window as `mh0438.py` (G+10 to G+290, 275 s per run):
- `vb0438.py` counts each frame as round(t / 16.667 ms) vblanks;
- `lean-round/sec0438.py` and `cad0438.py` look at rates per second and at how long frames cluster.

Outputs: `lean-round/vb0438-out.txt`, `lean-round/per-second.txt`.

| Vblanks per frame | 1 | 2 | 3 | 4 | 5–6 | 7–12 | > 12 |
|---|---|---|---|---|---|---|---|
| Share of frames (all 11 runs, 105,883 frames) | 57.6 % | 27.8 % | 9.0 % | 3.0 % | 2.0 % | 0.5 % | 0.1 % |
| Share of wall time | 33.6 % | 32.3 % | 15.8 % | 7.0 % | 6.0 % | 2.7 % | 2.5 % |

- **Not two-moded.** One-, two- and 3+-vblank frames each take about a third of the time. Every run shows the same
  shape: the 1-vblank share runs from 55.9 to 59.4 % of frames.
- **Long frames come in stretches.**
  - Of 15,487 frames of 3+ vblanks, 8,059 directly follow another one.
  - The 6-frame pattern "3+ ×6" occurs 2,528 times.
  - The common 6-frame patterns are 1-vblank runs with at most one 2-vblank frame in them.
- **The rate follows the scene, not chance.**
  - Each run's per-second rate correlates 0.68–0.89 with the mean of the other runs.
  - The run-averaged rate per 10 s from G+10: 35, 39, 44, 48, 46, 49, 48, 47, 40, 46, 40, 43, 40, 37, **11**, 29, 33,
    28, 27, 21, 31, 28, 27, 27, 26, 29, 29.
  - So the first ~140 s run at ~45 flips/s; then a drop to ~11 at G+150–160 (the same in every run); then ~27 flips/s
    to the end.
  - Per second, 1.4 % of seconds have 0–4 flips and 15.2 % have 50–54.
- **For the next diagnosis:** compare the fast phase (G+10 to G+140) with the slow one (G+160 to G+290), and the 3+
  frames with the 1-vblank frames, within the same runs. Whether the long frames are the same host waits is open until
  then.

## The bake kit (r438 with PLWCV; prepared offline, not built, not deployed)

The top session's proposal of 2026-11-20 to the maintainer is r438 with PLWCV and without p438, which has no
performance case (result 13). The switches stay for a per-run opt-out. Nothing is deployed until his word. Kit
`bake/` (on the box `~/bc5-work/exp0438/bake/`):
- **`mkbake438.py`** (`154de2af`): runs mkb438.py (`3b00ab29`, the tested one) for its steps 1–6 only, so p438
  (step 7) is not run. It also removes the lean build's lost-write counter and its two stderr lines: a catcher, and the
  lean build carries no diagnostics (the maintainer's rule of 2026-11-15).
  - Kept: BC5_0438_EARLYREG and BC5_0438_PLWCV, both on unless "0", read in normal and lean; normal's r438 count line
    every 60 s and its BUG lines.
  - On the tree unit `a62e8bf6` it gives `ff9e8fe2e4139264ebaf74f9e84bd892`. Against b438 (`a31a2091`, regenerated
    here byte for byte) it removes 130 lines and adds none: the lean counter (2 hunks), p438's block and its 6 hooks.
- **`0002-bc5-0438-baked.patch`** (`eb431795`): that unit against the tree's unit. It applies to a copy of
  `a62e8bf6` and gives `ff9e8fe2` (git apply, core.autocrlf off).
- **`swap0438.sh`** (`9efe522f`): exp 0436's swap0436.sh without its backend step, because r438 is in the host unit
  only and the archive stays `d6638808`.
  - Checks: patch bb04219b, the unit a62e8bf6, normal f345db74, lean 6a735b81.
  - Copies the old state; applies the patch (the unit must become ff9e8fe2); the new 0001 must be PATCH_NEW, with
    exp 0372 lines 5, the pad_audio_route header in and the same file list.
  - Rebuilds normal and lean in place. Each binary must gain exactly BC5_0438_EARLYREG and BC5_0438_PLWCV, lose no
    word, hold no p438 text, and only normal holds r438's count line.
  - DRY=1 runs on copies.
- **`undo0438.sh`** (`3b52da05`): back to bb04219b / f345db74 / 6a735b81, checked by md5. Without a rebuild,
  `BC5_0438_EARLYREG=0` turns r438 off for one run.
- **`run-swap0438.sh`** (`11712615`) and **`smoke0438s.sh`** (`0a990022`, exp 0436's smoke with its tags s438s*): the
  normal ASTRO BOT run reports r438's count and BUG lines.
- **`box0438.sh buildk`** (box0438.sh `24e773eb`): the private baked build, before any swap. Unit only, the shared
  archive, `~/bc5-work/exp0438/bake/{normal,lean}`. It checks the switches, no p438 / o438 / lean counter, and r438's
  line in normal only.
- **Not done:** buildk on the box, the swap's dry run on copies of the tree (both need a box slot), and CI's backend
  build (unchanged: the backend is not touched). After a swap, `backend/kytyplus-patches/0001-bc5-lle-agc.patch` on
  main must become the box's new `git diff f266548`.

## h438: the Render Thread's host-side split (prepared offline, not built)

The question, from the O runs: the Render Thread blocks ~9 ms per frame outside the guest syncs. Where, and do the
long frames block in the same places? h438 is records only, normal build only, off unless `BC5_0438_HOSTWAIT=1`.
It is built on the bake unit, so it measures what would ship.
- **`h438.hpp`** (`bdf94bf5`) writes one CSV line per Render Thread frame, flip to flip:
  - wall; thread CPU, run-queue delay and timeslices (`/proc/self/task/<tid>/schedstat`); minor and major faults
    (`.../stat`);
  - gc_ioctl calls by code (0xc0488131, 0xc0188132, 0xc0108102, 0xc020810c, 0xc0048116, 0xc0048117, 0xc0088133,
    0xc0108139, other): count, wall, and blocked (wall − thread CPU), counting the outermost call only;
  - the VideoOutSubmitEopFlip span and its Direct::drain;
  - lock-acquisition waits of 20 µs or more, by site;
  - o438's guest-sync blocked time by kind (with `BC5_0438_OUTSIDE=1`; o438.hpp `a194989d` gains one hook pointer and
    is otherwise unchanged).
  - File: `BC5_0438_HOSTWAIT_FILE`, written every 64 frames.
- **`mkh438.py`** (`7466020c`) on the bake unit `ff9e8fe2` gives `h438.cpp` `3aa9d745…` (not committed). It adds the
  include, the gc_ioctl span, the flip span with its drain, and 123 lock sites:
  - 122 one-line lock_guard / unique_lock sites;
  - exp 0436's submit-ring lock, timed as one statement.
  - Two sites are left as they are: a try_to_lock, which never blocks, and the ring lock's declaration.
- **`box0438.sh buildh`** (box0438.sh `417da0ce`): the normal build of h438.cpp plus o438's six tree units, unit
  only, with the shared archive: `~/bc5-work/exp0438/h438/normal`.
- **chain0438l arm H** (chain0438l.sh `a4650a79`): the h438 normal build with `BC5_0438_HOSTWAIT=1
  BC5_0438_OUTSIDE=1`, its CSV `$RAW/$t-h438.csv`. Diagnosis only, so no fps is reported.
- **`ah438.py`** (laptop) gives the mean ms per frame:
  - CPU, run queue and blocked;
  - of blocked: gc by code, the flip with its drain, guest syncs, and the rest;
  - lock waits by mutex and site, and faults;
  - all of it for all frames, by vblank class (1 / 2 / 3+), and by scene phase × class.
- **Tests:**
  - `test_h438.sh` (`4989a0a7`, `test_h438.cpp` `97f08d56`): PASS in all four cases. These are HOSTWAIT with and
    without OUTSIDE (gc codes, the nested call counted once, the flip and drain, a 30-ms lock wait by name, the /proc
    deltas, guest-sync time), HOSTWAIT unset (no file), and lean (empty macros).
  - `test_o438.sh` failed its waker case on the laptop, with the committed o438.hpp too. A timestamp probe showed why:
    the worker's post landed 40 ms after the Render Thread's wait began, while the wait slept a fixed 20 ms (22 ms
    measured). Thread start plus a 5-ms sleep take ~40 ms on the laptop. That is a race in the test, not in o438.
    - Fixed: the wait now lasts until the worker has posted (at least 20 ms), as a semaphore wait ends because of its
      post.
    - Now PASS 3 of 3 runs, in all three variants (OUTSIDE=1, unset, lean).
    - A broken copy of o438.hpp that stores no waker tid fails the case (lines 89 and 107), so the case still tests
      attribution.
- **Planned runs:** 3 scene runs of arm H on one boot, RT on. Then ah438 over three phases, placed from each CSV's
  own per-10-s counts: fast (about G+10 to G+140), the dip to ~11 flips/s at about G+150 to G+160 (seen in every run;
  a target of its own, the top session's addition), and slow (about G+165 to G+290). Usage:
  `ah438.py FROM TO fast=A-B dip=C-D slow=E-F csv…`.

## Result 14: where the Render Thread's frame goes (h438; 2026-11-21 00:26–00:49, boot eb264b8c; DIAGNOSIS numbers)

**Setup.**
- Slot (BOX-LOCK 00:20–00:31, CPU only): buildk, the swap's DRY run, then buildh (h438 normal `0c2a31782cbfea2ac5d7c41d10a99898`,
  0 errors). The shared builds were unchanged at every step.
- Before the runs: reimpl's leftover kernel-log reader (`journalctl -k -f`, pid 2123478) was killed on the top
  session's authorization. No other reader was left; 0 GPU resets, lock empty.
- Chain: chain0438l `ORDER="H H H" K0=340` (unit chain0438h), with `BC5_0438_HOSTWAIT=1 BC5_0438_OUTSIDE=1` on
  top of the bake unit's defaults (EARLYREG=1 PLWCV=1). His 09:46 scene, RT on, no input. One blocking waiter, no reads
  during the runs.
- Runs b438H341–343: NO_CRASH 3 of 3, 0 pad keys, GIVEN UP 0, CSVs of 14,208 / 13,952 / 14,144 frames.
- The CSV clock starts at the Render Thread's first flip and runs within a few seconds of the runner's.
- Phases, from each CSV's frames per 10 s (the dip shows at t 280–290 in all three: 101–125 frames per 10 s):
  fast t 140–270, dip 280–290, slow 295–415. Window t 136–416 (G+10 to G+290).
- Tool: `ah438.py 136 416 fast=140-270 dip=280-290 slow=295-415`; output in `lean-round/ah438-out.txt`.

**The split (mean ms per Render Thread frame, the three runs together; normal build with records: diagnosis numbers):**

| Group | Frames | Frame | CPU | Run queue | Blocked | in 0xc0188132 | flip's drain | Lock waits (s.flush_mu / g_dev_mutex) | Minor faults |
|---|---|---|---|---|---|---|---|---|---|
| all | 28,804 | 29.2 | 16.3 | 1.2 | 11.7 | 7.2 | 4.9 | 3.2 / 0.7 | 11.7 |
| 1 vblank | 18,306 | 20.0 | 11.1 | 1.3 | 7.6 | 3.5 | 4.7 | 0.08 / 0.10 | 0.5 |
| 2 vblanks | 6,203 | 31.7 | 16.9 | 1.1 | 13.6 | 9.0 | 5.1 | 5.4 / 0.3 | 9.3 |
| 3+ vblanks | 4,295 | 64.7 | 37.5 | 0.8 | 26.4 | 20.6 | 5.6 | 13.2 / 3.9 | 63.3 |
| fast phase | 16,639 | 23.4 | 12.3 | 1.2 | 9.9 | 5.3 | 5.2 | 1.5 / 0.4 | 1.3 |
| dip | 337 | 89.5 | 60.1 | 1.2 | 28.2 | 22.1 | 5.8 | 10.2 / 5.6 (+ g_jq_mutex 0.9) | 257 |
| dip, 3+ vblanks | 190 | 137.6 | 94.6 | 1.3 | 41.7 | 33.6 | 7.2 | 15.1 / 9.6 (+ g_jq_mutex 1.5) | 412 |
| slow phase | 9,846 | 36.6 | 21.2 | 1.1 | 14.2 | 10.0 | 4.7 | 5.6 / 1.0 | 18.0 |

- **The Render Thread's ~12 ms off CPU per frame is host time in two places:**
  - gc 0xc0188132 (the submit list, ~51 calls per frame) and the flip's Direct::drain, about 5 ms in every class;
  - nothing else: the guest syncs are under 0.01 ms, "other" is within ±1.6 ms of zero (the clock and schedstat
    rounding), and the run queue is ~1 ms.
- **The long frames are not the same waits, larger.** They differ in two ways:
  - **More CPU.** 37.5 ms in a 3+ frame against 11.1 in a 1-vblank frame; 94.6 ms in the dip's long frames.
    Inside 0xc0188132 the CPU is 30.8 − 20.6 = 10.2 ms (3+), so about 27 ms of a 3+ frame's CPU is outside our gc
    calls: guest code, other HLEs or fault handling. Minor faults rise with it: 0.5 → 63 → 412 per frame.
    TODO(verify): which; a CPU profile of the long frames is the next step.
  - **The submit list waits on s.flush_mu.** That is `chain_submit`'s `std::lock_guard order(s.flush_mu)`, the chain
    slot's flush-order lock (unit line 7985): it is held through a whole submission, the watchdog's or an observe
    point's foreign flush too (its comment: "the owner's next flush waits for the watchdog's"). It costs 13.2 ms per
    3+ frame, against 0.08 ms in a 1-vblank frame. g_dev_mutex (`submit_impl`'s lock at line 15283, after exp 0436's
    ring lock) adds 3.9 ms (9.6 in the dip). The rest of the long frames' 0xc0188132 blocked time (~3.5 ms) is the
    back-pressure sleep, r438's game-thread wait for an early writer, the backend or the kernel; it is not split
    here. r438's own line gives its share over a whole run: ~37,000 waits, 19.0–19.6 s per run, about 1.35 ms per
    frame on average, longest 32–47 ms, 0 BUG lines. Result 13 found no frame-time cost from it in lean.
- **r438 in these runs:** 3.77–3.83 M early writes per run, 0 that never reached the ring, GIVEN UP 0 in all three.
- **The dip at G+150–160** is the extreme of the same shape:
  - 89.5 ms per frame on average, 60 ms of it on CPU;
  - 257 minor faults per frame (412 in its long frames);
  - the same s.flush_mu and g_dev_mutex waits, larger;
  - g_jq_mutex (the job queue) appears only here (0.9 ms per frame).
  - The fault count points at memory work (a lazy import, a mapping, a new allocation); TODO(verify).
- **Next (not done here), simplest first:**
  1. who holds s.flush_mu when the Render Thread waits on it (the holder's thread and the reason code `why`), and
     for how long;
  2. a CPU profile of the 3+ frames and of the dip (perf on the Render Thread, the lean build, with frame marks);
  3. what the dip's faults are (fault addresses against the guest's mappings).

## The bake (2026-11-21 00:50–01:05, boot eb264b8c)

**Decision.** The maintainer's word, through the top session: "tak - wdrażaj wszystko, tym bardziej jeżeli nie obniża
płynności a poprawia błędy". The top session's proposal was r438 with PLWCV, no p438, and the switches kept.

**Before the swap** (the slot of 00:20–00:31, CPU only):
- buildk, the private baked build: normal `662cd4b5`, lean `5e49efc3`, 0 errors.
- swap0438 with DRY=1 on a copy of the tree: PATCH_NEW `9889b06a`. The undo restored `bb04219b` on the copy; the copy
  was then deleted.

**The swap** (`run-swap0438.sh` under the user manager, unit bc5-0438-swap; checks before it: 0 GPU resets, no
emulator, lock empty):
- Patch `bb04219b` → `9889b06a`: 135 files, 5 "exp 0372" lines, the pad_audio_route header kept. Tree unit
  `a62e8bf6` → `ff9e8fe2`.
- Normal `f345db74` → `b1b57df91b414743920f1fc500e1c300`; lean `6a735b81` → `d3485ed4f475f01549573763af804ce0`.
- Archive `d6638808` unchanged; the backend is not touched.
- Words: each binary gained exactly `BC5_0438_EARLYREG` and `BC5_0438_PLWCV` and lost none.
- `backend/kytyplus-patches/0001-bc5-lle-agc.patch` on the branch is the installed file: `9889b06a`, commit
  `dd7406c2`.

**Smokes** (`smoke0438s.sh`): **ALL PASS**. Each run had 0 kernel lines, 0 crash lines and 0 pad keys, and each ran
the new binary (`/proc/<pid>/exe` md5).
- s438sc: ASTRO BOT, lean, 200 s.
- s438su: the second title, lean, 300 s, 33 of 33 key lines.
- s438sn: ASTRO BOT, normal, 200 s.
  - The smoke printed "r438 lines 0" because it reads play.log, while r438's lines go to the journal.
  - The run's direct.log has 3 r438 lines: 94,914 early writes, 0 that never reached the ring, 0 BUG lines, GIVEN UP 0.

**Undo:** `bash ~/bc5-work/exp0438/bake/undo0438.sh`, back to `bb04219b` / `f345db74` / `6a735b81`. Per run with no
build: `BC5_0438_EARLYREG=0` turns r438 off, and `BC5_0438_PLWCV=0` gives the 20-µs poll.

## The last records on the second title: f438, m438 and two perf modes (prepared offline, not built)

The top session's order of 2026-11-21: one combined slot of at most ~45 min before the second title is uninstalled
(exp 0439 installs the third). Fixes first: all three records go into one slot. Diagnosis only.
- **f438** (`h438.hpp` `4075a6dc`; normal; on with `BC5_0438_HOSTWAIT=1`): who holds the chain slot's flush lock
  `s.flush_mu` when the Render Thread waits on it, and why.
  - Each `ChainSlot` gets a holder record (thread, flush reason, start), set by a thread's outermost hold. The lock is
    recursive.
  - chain_submit's lock line becomes `BC5_F438_FLUSH_LOCK(s, why, foreign)`. It reads the holder before the wait and,
    after it, records a wait of 20 µs or more by (waiter, holder, reason).
  - The Render Thread's waits also go into h438's per-frame `locks` column as `flush<-<holder>/<reason>`. Reasons:
    end, wait, ring/class, cond_exec, size, drain, acb-head, other, observe, hold-wd (the chain watchdog), hold-end.
  - Every hold is timed by (holder, reason, own or foreign). A stderr line `f438 (exp 0438): 60-s totals` gives both
    sets of totals.
  - `test_h438.sh` case 5 PASS: a `bc5-chainwd` thread holds 30 ms as a foreign `hold-wd` flush, and the Render
    Thread's frame shows `flush<-bc5-chainwd:2003/hold-wd=…`. Its own recursive re-entry records no wait, and the
    slot's depth and holder are back to 0 and none afterwards.
- **m438** (in both test units): frame marks. At the top of VideoOutSubmitEopFlip, with `BC5_0438_FRAMEMARK=1`, the
  steady clock (CLOCK_MONOTONIC, the clock `perf -k CLOCK_MONOTONIC` stamps with) is written in ns per flip, every 64
  flips, to `BC5_0438_FRAMEMARK_FILE`.
  - It is also in lean, because these are private test builds. The no-diagnostics rule is for the shared lean build.
- **prof0438.sh** (`1739ce73`): run from G by the runner (`N_SIDE`), after exp 0432's prof0432.sh. It is read-only
  towards the emulator: user-space perf_event_open, `perf_event_paranoid` untouched. It finds the Render Thread's tid
  and profiles that thread only:
  - `PROF_MODE=cpu`: cpu-clock:u at 999 Hz;
  - `PROF_MODE=faults`: page-faults:u with `-c 1 -d`, every user-space fault with its data address.
  - It writes `perf script --ns` text (gz) and `/proc/<pid>/maps` every 10 s.
- **`mkfm438.py`** (`mkfm438.py` md5 in the commit):
  - on `h438.cpp` it gives `fm438.cpp` `d014b652…` (f438 + m438; normal);
  - on the bake unit it gives `m438.cpp` `e525cc84…` (m438 only; lean).
  - `box0438.sh buildfm` (`4f9232ed`) builds both: the normal one with o438's units, the lean one with the unit only.
    It checks the switches, f438's line in normal, and no h438 / o438 / f438 / r438 lines in lean.
- **chain0438l arms** (`0aa9368d`):
  - **F**: normal fm438, `HOSTWAIT=1 OUTSIDE=1 FRAMEMARK=1`, prof in faults mode. Its CSV and marks go beside the run
    files, so it answers (1) and (3) in one run.
  - **P**: lean m438, `FRAMEMARK=1`, prof in cpu mode, which answers (2).
- **Tools** (laptop):
  - `ah438.py` reads F's CSV, f438's waits included.
  - `pf438.py` puts perf samples or faults into frames by the marks. It reports per vblank class and phase: samples
    or faults per frame, the top DSOs or mappings and symbols, and for faults the mapping of the faulting address.
  - `test_pf438.py` PASS on synthetic marks, both perf line forms and a maps file. TODO(verify): the real
    `perf script -F` line form on the box; prof0438 keeps the raw text, so pf438's parser can follow it.
- **Proposed slot** (~35 min):
  1. buildfm (CPU, ~5 min);
  2. chain `ORDER="F P P"` (3 × ~7.5 min) under `systemd-run --user`, with one blocking waiter and no reads during
     the runs.

## The flush-order lock: the narrowest hold that keeps the order (design, not built; for every title)

**What it does today.** `chain_submit` takes `s.flush_mu` after the chain is swapped out of the slot. It holds it
through the whole `submit_now`:
- the preparation (mapping sync, filter, direct sync);
- the back-pressure sleep (`g_cq_fences >= 24`, 50-µs sleeps);
- the ring lock (exp 0436) and `g_dev_mutex`;
- the kernel submit.

So the next flush of the same slot waits for all of it, whichever thread took the earlier chain: the owner, the chain
watchdog after the 2-ms hold bound, or an observe point / the flip's flush_all. The lock gives three things:
1. **Take order = submit order per slot.** Without it, a chain taken later could reach the ring mutex first.
2. **One submission in flight per slot.** exp 0430's F10 keeps a single `f10_flight` write set and F16 a single phase
   per slot; both assume it.
3. **Re-entry.** `submit_now`'s mapping sync can call `wait_jobs` → `chain_flush` on the same thread. That nested
   chain goes out before the outer one, which the recursive mutex allows.

**The candidate (accepted by the top session, built only after f438's data): an order ticket per slot, waited for at the
ring step.** See the code reading below for what it can and cannot gain.
- **At the take** (already under `s.mu`): `mine.ticket = ++s.taken`. The chain's F10 write set moves with it, as one
  entry in a per-slot list keyed by ticket, so several can be in flight, each removed after its own submission.
- **The order gate** goes where the order matters: just before the ring lock in `submit_now`. The submission waits
  until `s.done == ticket - 1` (a condition variable on the slot). Preparation and back-pressure before the gate run
  without it.
- **After the kernel submit returns:** `s.done = ticket`, then notify. That is the point where the kernel has the job
  in its ring order; any later chain of the slot may go.
- **Re-entry:** a nested flush on the thread that owns the current ticket, before that ticket's gate, goes ahead as
  today: it takes the current ticket, and the outer one is given the next. Done in one place, under `s.mu`.
- **F16's phase:** per ticket instead of per slot.
- **What it keeps:** take-order submits per slot, exp 0436's per-ring lock order (ring, then `g_dev_mutex`, then the
  backend), F10's flight set per chain, and the nesting behaviour.
- **What it removes:** a flush waiting behind another thread's preparation and back-pressure sleep.

**The "not verified" list, settled by reading the code** (the bake unit `ff9e8fe2`, `submit_now` and `chain_submit`).
This corrects the gain claimed above. The order inside `submit_now` is:
1. the back-pressure sleep (`g_cq_fences >= 24`; F16 phase 1);
2. exp 0436's **ring lock** `g_su436_ring_mu[ring]`, then `g_dev_mutex` (phase 2 while asking, 3 once held);
3. the **preparation**, under both: `sync_mappings`, `direct_sync`, the filter's options and its mapping list;
4. the backend's submit: it calls back before the CS ioctl to let `g_dev_mutex` go, the kernel submit runs, and
   `g_dev_mutex` is taken again;
5. `register_label_writes` (the global `g_plw` and its ring-order counter), then `cq_push`.

The ring lock is held from step 2 to the return.

After `submit_now` returns, `chain_submit` touches the slot: `f10_flight` is cleared, F16's phase is set to 0 and
`f16_done` is bumped, and for a cross-ioctl chain the marks from the thread-local `t_gpu_done` go into `s.marks` and
`chain_post_soft_locked` posts the soft replays. Before this reading I had placed the preparation before the ring
step, and with it the waiter's gain.

**What it means:**
- For two chains of one slot on the same ring, the ring lock already serializes steps 3–5. The ring lock is not FIFO,
  which is why `flush_mu` is still needed for take order.
- So a ticket gate at the ring step would not take a waiter out from behind another thread's preparation. It removes
  only the holder's back-pressure sleep (step 1) and the tail after step 5 from the waiter's wait.
- A gate later, at the kernel submit in the backend's callback, would let the next chain's preparation start during
  the holder's CS. But that preparation needs the ring lock, which the holder keeps until its return. It only helps
  if the ring lock is narrowed to the CS too.
  - TODO(verify): whether the preparation needs the ring at all, or only `g_dev_mutex`.
- **Slot state after the gate**, which the ticket must make per chain:
  - `f10_flight`, read by exp 0430 F10's waiters until it is cleared;
  - F16's phase and `f16_done`;
  - the cross marks and the soft replays.
  - `t_gpu_done` is thread-local, so it moves with its submitting thread; `register_label_writes` is global, in ring
    order under the ring lock.

**So f438 records the holder's F16 phase** at the moment the wait starts. `h438.hpp` `ca501adf`; the frame column
becomes `flush<-holder/reason/phase`, and test case 5 now checks `hold-wd/backpressure`. The design follows the phase:
- **Mostly phase 1 (back-pressure):** the holder sleeps because 24 jobs are in flight, so the wait is the GPU's. A
  ticket at the ring step moves the waiter to the same back-pressure; it does not shorten the frame.
- **Mostly phase 2–3 (the ring and device locks, the preparation and CS):** the ring lock is the real order. The fix
  is to narrow the preparation's need for the ring (TODO(verify) above), not `flush_mu`.
- **Phase 0 / 4 (the tail, or draining the GPU in `wait_jobs`):** the ticket removes the wait, since the tail needs
  only the slot's own state per chain. The drain is the GPU again.

## Result 15: the last records on the second title (f438, m438, perf; 2026-11-21 07:29–07:55, boot eb264b8c; DIAGNOSIS)

**Slot** (the top session's GO, 07:26):
- Pre-checks: 0 GPU resets, no emulator, lock empty.
- The kit's pins were still the pre-bake builds. They were repinned to the baked ones before the build: box0438.sh
  `6a317124` (P_UNIT `ff9e8fe2`, normal `b1b57df9`, lean `d3485ed4`) and chain0438l.sh `6f2f83f2`.
- buildfm under BOX-LOCK 07:29–07:31: normal `d5f1a175f95a7b8c5ab7b9903e4c46a2` (fm438.cpp: h438 + f438 + m438) and
  lean `90cc275adb96ccd6c6ba2eca5316e7aa` (m438.cpp), 0 errors. The shared builds were unchanged.
- **perf's real line forms** (perf 7.0.14 in the ubuntu container, on a throwaway process):
  - cpu: `tid time: ip sym (dso)`;
  - faults: `tid time: addr addrsym (addrdso) ip sym (dso)`, with the data address resolved too.
  - A DSO may hold a nested pair, `(/memfd:KytyDirectMemory (deleted))`.
  - pf438's parser and test_pf438 follow these forms (PASS).
  - The clock is CLOCK_MONOTONIC (68351 s ≈ the uptime), m438's clock.
- Chain `ORDER="F P P" K0=343` (unit chain0438fp), his 09:46 scene, RT on, no input. Before it, no other session's
  reader or process was left.
- **Runs:** b438F344 (F), b438P345 and b438P346 (P), all NO_CRASH, 0 pad keys, 0 kernel lines. F344: GIVEN UP 0, r438
  0 lost.
- **Data:** all of it was copied to `data-0438/FP` (laptop) and checked by md5, 147 of 147, before the box was
  released. This was the last data from this title; exp 0439 uninstalls it.
- **Phases** from the marks per 10 s, the same shape in all three runs: fast t 140–270, dip 280–290, slow 295–415;
  window 136–416.
- Outputs: `lean-round/ah438-F344.txt`, `lean-round/pf438-{F344,P345,P346}.txt`.

**(1) Who holds s.flush_mu when the Render Thread waits** (f438, F344's last 60-s line, the whole run):

| Waiter ← holder / reason / holder's F16 phase | Waits | Total | Longest |
|---|---|---|---|
| Render Thread ← bc5-chainwd / hold-wd / devheld | 4,076 | 30.9 s | 262 ms |
| Render Thread ← bc5-chainwd / hold-wd / asking | 425 | 6.3 s | 221 ms |
| Render Thread ← bc5-chainwd / hold-wd / tail | 54 | 0.13 s | 12.7 ms |
| Render Thread ← bc5-chainwd / hold-wd / backpressure | 14 | 0.02 s | 3.2 ms |
| bc5-chainwd ← Render Thread / hold-end / (all phases) | 224 | 0.62 s | 61.6 ms |

- **Holds:**
  - the watchdog's foreign `hold-wd` holds of the Render Thread's chain: 17,052, 79.6 s in all, longest 509 ms;
  - the Render Thread's own `wait` / `hold-end` / `drain` flushes: 72,360 / 10,226 / 13,603;
  - bc5-ring's `end` holds: 154,454, 128.9 s, its own slot.
- **Per frame** (ah438 on F344's CSV): the 3+ vblank frames wait 9.6 ms on `hold-wd/devheld` and 3.7 ms on
  `hold-wd/asking`, plus 4.3 ms on g_dev_mutex. The dip's long frames: 7.8 + 5.6 + 3.9 ms. The 1-vblank frames:
  0.07 ms.
- **Reading:** the Render Thread waits for the chain watchdog's submission of its own chain. The watchdog takes it
  after the 2-ms hold bound, when the Render Thread has been busy between ioctls. Its holder is almost always in the
  ring and device locks (the preparation and the CS), not in back-pressure.
- **What that decides:** by the code reading, the per-ring order of those steps is the ring lock's. So the ticket at
  the ring step would not shorten these waits. The Render Thread would only wait on the ring lock instead. What would
  remove them is not making the Render Thread wait for a submission of its own chain that another thread is doing:
  - for example, a per-slot submit queue that the owner only pushes to, with one submitter per slot draining it in
    order, and the owner waiting only where it must (back-pressure, or a CPU wait that needs its chain submitted);
  - or a cheaper preparation and CS.
  - This is a design for a next experiment, not built. It holds for every title, since the watchdog and the lock are
    common code.

**(2) What the Render Thread's CPU is** (lean P345 / P346, perf cpu-clock 999 Hz on the thread, by frame from the
marks; samples ≈ ms):

| Frames | CPU per frame | Guest code (`/memfd:KytyPrivateMemory`) | Emulator | libc / libstdc++ |
|---|---|---|---|---|
| 1 vblank (6,396 / 6,807) | 8.2 / 8.8 | 42.8 % | 40.8 % | 15.4 % / 0.6 % |
| 3+ vblanks (1,381 / 1,136) | 35.9 / 34.9 | 75.6 / 77.0 % | 15.7 / 14.9 % | 5.8 / 5.7 % / 2.8 / 2.3 % |
| dip, 3+ (50 / 65) | 136.8 / 94.5 | 77.6 / 80.8 % | 8.8 / 9.9 % | 5.4 / 4.3 % / 8.2 / 5.0 % |

- **In short frames** the host's share is ~3.4 ms. Its top symbols: `submit_now`, `full_state::Tracker::emit_prefix`
  / `apply_level`, and `__memmove_avx_unaligned_erms`.
- **The long frames' extra CPU is the title's own code** on the Render Thread: ~27 ms of a 3+ frame's ~35 ms. The host
  share rises only to ~5.5 ms.
- **In the dip** two host symbols appear: `std::_Rb_tree_increment` (5–8 %, a std::map walk) and a `std::__find_if`
  over a `vector<std::string>` with `strlen`. That is a host lookup over names, about 5–11 ms per long dip frame.
  Without call stacks its caller is not known. TODO(verify): on the next title, with `--call-graph` (the host is
  built with frame pointers? to check).
- **Lean against normal** (diagnosis only): 8.2–8.8 ms of CPU per 1-vblank frame in lean, against h438's 11.0 ms in
  normal. That is the diagnostics' own CPU.

**(3) The faults** (F344, page-faults:u, every fault of the Render Thread with its address; maps snapshot 15, about
t 280):

| Frames | Faults per frame | Into the anonymous rw region of 15 MiB at `0x7fcf7c000000` | Into `/memfd:KytyDirectMemory` | Faults per distinct page |
|---|---|---|---|---|
| 1 vblank | 0.46 | 19 % | 77 % | 1.04 |
| 3+ vblanks | 95.8 | 94.6 % | 4.0 % | 13.5 |
| dip, 3+ | 1,010 | 97.5 % | 1.7 % | 14.5 |

- **The long frames' faults** go almost all into one 15 MiB rw anonymous region, followed by 49 MiB of `---p`. The
  64-MiB alignment and that layout look like a glibc per-thread malloc arena (TODO(verify)).
- **About 14 faults per page:** the same pages are dropped and touched again, which fits the arena's top being
  trimmed after large frees and grown back. TODO(verify): glibc's non-main arena trim (`heap_trim` / `shrink_heap`
  by `MADV_DONTNEED`).
- **The faulting instructions:** 62–63 % in libc and 31–37 % in the emulator. The emulator's symbols were not
  resolved by `perf script` for the fault mode; its cpu mode resolved them.
- **The cost:** about 1,000 faults of zero-filled pages per long dip frame is a few ms at most, not the 60–95 ms of
  CPU. The faults mark large host allocations around the long frames; they are not the time itself.
- **A host-side check for the next title, simplest first:** `M_TRIM_THRESHOLD` / `M_MMAP_THRESHOLD` (mallopt, or
  `MALLOC_TRIM_THRESHOLD_` in the launcher) or keeping the large buffers, and see whether the faults and the host
  share go. It cannot touch the guest's 27 ms.

**Summary for the next titles** (diagnosis numbers):
- The second title's long frames are, first, the title's own CPU work on its Render Thread.
- Second, ~13 ms per long frame waiting for the chain watchdog's submission of the Render Thread's own chain.
- Third, a few ms of host work, with a malloc-arena fault churn beside it.
- The open host items, in order:
  1. the watchdog / owner submission design (a per-slot submit queue), every title;
  2. the arena trim check;
  3. the dip's name lookup, with call stacks.

## Result 16 (offline, from the P runs): the long frames' guest CPU is one tight loop

`gip438.py` (`7babfa96`) reads P345 + P346's Render Thread samples whose ip lies in the guest's executable
KytyPrivateMemory mappings. Each module is named by its 256-MiB load base (`module@<base>+<offset>`). The groups are
by vblank class and phase. Its output stays private (`hot-ips.txt` and the full output, outside git) because it
names offsets in the title's code. The shape:

| Frames | Guest samples per frame (of all) | Distinct ips | 50 % of guest samples in | 90 % in | The top page's share |
|---|---|---|---|---|---|
| 1 vblank (13,203) | 3.65 of 8.52 | 8,916 | 234 ips / 92 lines / 15 pages | 4,175 ips / 114 pages | 13.7 % |
| 2 vblanks (4,060) | 6.72 of 13.17 | 5,545 | 45 ips / 17 lines / 4 pages | 92 pages | 40.6 % |
| 3+ vblanks (2,517) | 27.02 of 35.46 | 4,489 | **13 ips / 1 line / 1 page** | 296 ips / 18 pages | 81.2 % |
| dip, 3+ (115) | 89.26 of 112.86 | 484 | **11 ips / 1 line / 1 page** | 20 ips / 2 lines / 1 page | 92.9 % |

- **The long frames' guest CPU is concentrated, not spread.** In a 3+ frame, half of it is in 13 ips of one 64-byte
  line of the title's main module (module@900000000, 97–99 % of the guest samples there). Those ips are about 36
  bytes long, hit almost evenly at every second byte (~4 % each).
- The 1-vblank frames run the same line too, but only for 14 %; their guest time is spread over ~4,000 ips.
- **Overlap:** 92.5 % of the 3+ frames' guest samples lie in the 1-vblank frames' top-50 pages. The long frames run
  the same code, mostly that one line, for longer.
- **Reading** (behaviour, not code): a short loop of two-byte instructions, hit evenly, is the shape of a busy-wait
  (a spin with a pause-like backoff). In its long frames the Render Thread spins in the title's own code waiting for
  something, and the more it waits the longer the frame. On the console, the same CPU (Zen 2) would not spin 22–90 ms
  per frame unless what it waits for comes late: a job worker's result, or a value the GPU or our soft CP writes.
  - TODO(verify), for the next step: from the hot code's bytes (private), which memory the loop reads, and from a
    second profile, which thread writes it.
- **Not in this data:** which threads run while it spins. The P runs profiled the Render Thread only, with no
  per-thread schedstat. For the next title, prof0438 gets an all-thread mode: perf on every thread at a low rate,
  plus /proc/<pid>/task/*/schedstat every second (exp 0432's prof0432.sh form).
- **The hot code's bytes:** `gipbytes438.py` (`fe760d21`), read-only on the box (top's 2-minute GO, before exp 0439's
  uninstall). It finds the title's eboot.bin under ~/bc5-data, requires its first load segment to match the maps
  region at module@900000000 (0x5f24000), and writes 256-byte windows around the top 60 ips to
  `~/bc5-data/private/exp0438-hotcode` (mode 700), copied to a private folder on the laptop outside git.
  - A stand-in dry run on the laptop (a synthetic ELF) PASS.
  - The bytes and any disassembly are never committed; this README describes behaviour only.

## The per-slot submit queue (design, not built; for every title)

**Goal (F869).** The Render Thread waits ~13 ms per long frame on its slot's flush lock while the chain watchdog
submits the Render Thread's own chain (holder phase: device held or asking). The owner should not wait for a
submission of its own chain that another thread is doing. It should wait only where it has to.

**Shape (switch `BC5_0438_SUBMITQ`, off unless "1" in the test build).**
- **The queue.** Each ChainSlot gets a FIFO of taken chains, at most 4. Each entry holds the chain, its F10 write
  set, its why and its take ticket.
- **Taking a chain.** `chain_submit(s, why, foreign)` keeps its take under `s.mu`, unchanged, and pushes the taken
  chain instead of calling `submit_now`.
- **The submitter.** One submitter per slot drains the queue in order and calls `submit_now` exactly as today:
  back-pressure, the ring lock, g_dev_mutex, the preparation, the CS, the registration. It runs the tail after each
  entry (below). It is a thread per registered slot, woken by a condition variable on the slot, so a slot's chains
  reach the kernel in take order, as `flush_mu` guarantees today.
- **The watchdog** pushes as well, instead of submitting. It no longer holds anything for the time of a submission.
- **The owner waits only:**
  1. **When the queue is full** (4 entries): back-pressure on the owner, as today's 24-fence wait is on the
     submitter. The wait is the GPU's or the submitter's.
  2. **Where a CPU wait needs its chain.** Today `chain_flush(1)` before a game-thread wait makes the chain's label
     writes registered (`register_label_writes`) before `ring_will_satisfy` looks. With the queue they are not
     registered until the submitter's CS. That is exactly F865's give-up path ("no pending write") if nothing
     covers it.
     - So at push, the entry's label writes are registered early, as r438 does for bc5-ring's slices: pending
       entries with `seq = kR438Early | bit 62 | ticket`.
     - r438's game-thread rule then applies unchanged: a wait whose last pending write is early waits, on PLWCV's
       condition variable, for the real registration, and is kept in ring order.
     - At the entry's end the submitter checks that every early write was registered for real; one that was not is
       a BUG line and is removed. This is r438's invariant.
  3. **At the flip's drain** (`chain_flush(5)` + `chain_flush_all(5)` before `Direct::drain()`) and at `wait_jobs`:
     the queue must be empty and its last entry submitted before the GPU drain means anything. The owner pushes,
     then waits for its slot's `done == taken`. That is today's behaviour, since the flip waits for the drain anyway.
  4. **Sync mode** (`g_async` off): no queue; the owner submits inline, as today.
- **State the owner (or another thread) still touches after a push, and how each moves:**
  - `f10_writes` (the open chain): unchanged, the owner's, under `s.mu`.
  - `f10_flight` (today: the one chain in submission) becomes the union of the queued and in-flight entries' write
    sets, under `s.mu`. `f10_pending` and `f10_observe` (exp 0430 F10, other threads) read it as today, a list of
    per-entry sets. An entry's set is removed after its own submission's registration, as today's clear.
  - `f16_done` is bumped per entry done (F10's waiter list compares it as today). `f16_phase` is the submitter's phase
    for the entry it carries. `t_f16_slot` is set by the submitter, which is the thread inside `submit_now` now.
  - `f10_wanted` / `open_ns = 1` (F10 asks the owner, or the watchdog, to flush): unchanged. They now lead to a push.
  - `in_submit` (the owner is inside Direct::submit; a buffer may be split at a wait): unchanged. It guards the take
    under `s.mu`, not the submission.
  - `marks` and `soft` (cross-ioctl chains: soft replays posted once the chain carrying their buffers is submitted):
    the submitter posts them after the entry's submission, as `chain_submit`'s tail does today. `t_gpu_done` is
    thread-local, so the submitter collects its own and moves it into `s.marks` under `s.mu`.
  - `t_fs415_*`, `t_cq` and the other thread-locals `submit_now` reads: the submitter sets them from the entry
    (fs415's open time, why and segments go into the entry at the take).
  - The `Chain` object stays alive in the entry until `submit_now` returns (`keep_wait_offsets`,
    `chain_mark_executed`).
  - **Re-entry:** `submit_now`'s mapping sync can call `wait_jobs` → `chain_flush` on the submitter. That is the
    submitter's own slot, which pushes onto the queue behind the current entry. A wait for it inside the current
    entry's submission would deadlock, so a re-entrant flush on the submitter submits inline, ahead, as today's
    recursive `flush_mu` does.
  - **Slot destruction** (the thread_local slot at thread exit): the submitter drains and stops first; then
    `~ChainSlot` unregisters it as today.
- **Ordering kept:**
  - per slot: take order to the kernel;
  - per ring: exp 0436's ring lock, then g_dev_mutex, then the backend, unchanged inside `submit_now`;
  - registration: `register_label_writes` under the ring lock, as today;
  - r438's early entries for both bc5-ring's slices and the queued chains, one rule.
- **What it changes for the Render Thread:** a flush becomes a push plus an early registration (a scan of the chain's
  packets, as r438's `r438_scan`, ~µs). The chain's preparation and CS run on its slot's submitter, overlapping the
  Render Thread's next CPU work.
  - The flush-lock waits behind the watchdog (F869: 9.6 + 3.7 ms per 3+ frame) go.
  - The Render Thread's own `wait` / `hold-end` / `drain` flushes (72,360 / 10,226 / 13,603 per run) stop costing it
    the preparation and CS.
  - Where its next CPU wait needs the chain, it waits for the real registration, which is the same time it waits
    today, minus the overlap.
- **Risk:** this changes every title's submission path, the path behind F848, F852 and F865. So: a switch, an offline
  test, then lean A/B on ASTRO BOT and the third title, as the top session ordered. The offline test (`test_q438`)
  cuts the take, push, submitter, early registration and tail from the generated unit against stubs, after
  test_r438 and test_p438. It checks:
  - take order to `submit_now` across owner, watchdog and flush_all pushes;
  - no wait finds "no pending write" for a queued chain's label;
  - the F10 flight union and `f16_done` per entry;
  - the re-entrant flush inline;
  - drain = empty;
  - a broken copy (the early registration removed) must fail.

## Result 17: who releases the Render Thread's spin (b438S347, 2026-11-21 08:22, boot d1ac0537; DIAGNOSIS)

**Writers of the spun-on word** (`xref438.py` scan of the main module's code segment, read-only on the
box, private output; in behaviour terms):
- 35 RIP-relative references to the word. The known load in the spin loop is among them, which checks the scan.
- **A frame-phase state machine:** the word takes the values 0–6.
- **The Render Thread sets 1 itself**, just before its loop. The stores of 3, 4, 5 and 6 follow in the same
  function, after the loop.
- **One lone store of 2** sits in a separate function close by. It is the only store that can end the spin, since the
  loop leaves on any value other than 1.
- Seven instructions take the word's address, so some updates may go through a pointer.

**The run:** b438S347, the SHARED lean build `d3485ed4` with no extra word, his scene, RT on, PLAY 220. prof0438.sh
in all mode (`d95b2237`) ran from G for 200 s: perf cpu-clock:u at 199 Hz on every thread (141,922 samples, 87
threads) and every thread's schedstat each second. Chain0438l arm S (`3c6c6516`). Tool `sp438.py`; the code ranges come
from a private file.

**Result:**
- **Spins:** 564 episodes, 14.6 s in all, longest 947 ms.
- **The releaser is game-main.**
  - It has a sample in the 10 ms before 545 of the 564 spin ends.
  - It is the only thread ever sampled near the releasing store.
  - The job workers barely run during the spins and wait 0.1 ms/s in the run queue, so nothing runnable is starved.
- **What game-main does:**

  | game-main's samples | Host memmove (libc) | Guest code | Our AMPR/AMM and memory HLE |
  |---|---|---|---|
  | during the spins (1,853) | 87.4 % | 1.1 % | `LibAmpr::Ampr::WriteCommandBufferPointers` 1.1 %, `AmmAutoReleaseVa` 0.9 %, `GuestAddressSpace::MapBacking` 0.5 % |
  | outside them (20,732) | 4.1 % | 88.4 % | – |

- **Reading:** the title's main thread issues AMPR/AMM commands, and our host executes them synchronously as large
  memory copies on that thread. The Render Thread spins, as the title is written to, until main reaches the next
  phase.
  - The console presumably does this work asynchronously or by remapping (TODO(verify): the AMPR path in KytyPlus
    f266548 plus patch 0001, and the API's documented behaviour).
  - **This is the main lever for the long frames.** It is host work, with every title's reach.
- **Also during the spins:**
  - bc5-chainwd (745 samples): submission preparation (`direct_sync_one`, views build, a std::map walk, memmove,
    strlen);
  - "Archive Asset I" (382): memmove.
- **Not shown:** the window ended at 1514.18 s; the run then hung at 1516.3 s (result 18).

## Result 18: S347's GPU hang, on the shared lean build with r438 baked in (1516.3–1518.3 s)

- **The first event:** at 1516.28 s, gfxhub TCP write-permission faults (`GCVM_L2_PROTECTION_FAULT_STATUS 0x00741051`,
  PERMISSION_FAULTS 0x5, RW 1, MORE_FAULTS; "167 callbacks suppressed"), from a job of bc5-ring (an acb), vmid 7.
  - Ten distinct fault pages in 0x14…–0x16…, plus 0x1c… and 0x139e….
  - The fault record (`~/bc5-data/captures/faults/20261121-082800/`) calls it K3 "no guest range (a hole)": no
    guest range, view or GPU mapping.
  - The addresses repeat their low bits under different high parts: a valid low address with a junk high part.
- **Then:** at 1518.3 s the comp_1.3.0 ring timed out (signaled 83501, emitted 83503), then gfx_0.0.0 (118092 /
  118094). Both ring resets succeeded; "device wedged, but no recovery needed". The run ended by itself at 335 s.
- **The devcoredump** `~/bc5-data/captures/devcoredump/20261121-082800-devcd1.txt` (process thread bc5-chainwd) is
  not yet decoded beyond the IB registers. It and the dmesg are copied privately.
- **Class: F852/F858** (an acb that ran with bad descriptors or pointers and wrote into holes), not F865's shape (a
  wait on a label nobody writes). The lean build writes no journal, so the dropped-wait probe line that named
  F852/F858 does not exist for this run.
- **r438** changes game-thread dcb waits and early registration from bc5-ring's slices. The acb-side decisions
  (bc5-ring's own `ring_will_satisfy`, F2/F4) ignore early entries by design. The class predates r438 (F852 11-17,
  F858 11-18). Recommendation to the top session: keep r438.
  - Counted: 1 hang in about 20 r438-on runs today.
- **The profiler:** perf record stopped at 1514.18. Its `perf script` and gzip ran in the container around the
  fault, a timing nudge at most, not a cause.
- **Naming the dropped wait** would need normal-build runs with the journal, at about 1 hang per 10–20 runs. F852's
  open candidate (keep a met cross-queue wait for the GPU) does not need that capture first.

## Result 19: game-main's copies are O(n) guest-memory bookkeeping (b438M349, 2026-11-21 09:02–09:08, boot d1ac0537; DIAGNOSIS)

**Why a shim.** Every perf call-graph form (`--call-graph fp`, `-g`, `--user-callchains`, `dwarf` with `-m 16` / `-m
32`) is refused with EACCES at `kernel.perf_event_paranoid` = 2, while plain records work. That is why the K348 run got
no game-main stacks. Changing the setting is the maintainer's to decide. Our host build keeps frame pointers
(`-fno-omit-frame-pointer` on all 4,278 compile lines of the lean compdb), so fp chains are usable once perf may record
them.

**The shim** `cpy438.c` (`fe7a094f`), loaded with LD_PRELOAD. It is records only, for test runs.
- **What it wraps:** `memcpy`, `memmove`, `mempcpy` and their `_chk` forms. Ubuntu's gcc fortifies by default, so the
  calls go to `__memcpy_chk` / `__memmove_chk`; the shared lean binary imports all four.
- **What it records:** for every copy of 256 KiB or more, on any thread, the time, size, dst, src and up to 12
  frame-pointer return addresses. The frames are read with `process_vm_readv` on our own pid, so a bad frame pointer
  ends the walk instead of faulting.
- **No locks, no malloc** in the hot path; a writer thread drains every 2 s.
- **Test:** `test_cpy438.sh` PASS in the ubuntu container. A dummy's 1-MiB copies are recorded on their thread with
  the calling function in the chain; nothing is written below the bar or without `CPY438_OUT`.
- **Not seen:** copies inside libc itself and small inlined fixed-size copies.

**The run:** b438M349, the shared lean build `d3485ed4` (the 2-s load check first: rc 0), his scene, RT on, PLAY 220.
- chain arm M (`88d98198`): `LD_PRELOAD=cpy438.so CPY438_OUT=…`, with prof0438 cpu mode on the Render Thread for the
  spins (1,613 episodes).
- NO_CRASH, 0 pad keys. All 115 files copied and md5-checked.
- 366,421 copies of 256 KiB or more from the emulator, symbolized on the box with `sym438.py` (addr2line; host frames
  only, guest frames shown as `[guest]`; the full output is private).

| Thread | Copies (≥ 256 KiB) | Bytes | In spins | Top caller families |
|---|---|---|---|---|
| game-main | 213,154 | ≈ 350 GB | 136,588 (≈ 240 GB) | `VirtualRanges::MergeAroundUnlocked`; `GuestBackingStore::UnmapOne` under `VirtualRanges::EditUnlocked` / `Rename`; `std::_Rb_tree<…GuestBackingStore::MapEntry>`; `std::vector<PooledMemory::Mapping>::_M_realloc_append`; `GuestAddressSpace::FindFreeAligned` over `vector<PhysicalRange>` |
| Archive Asset I | 30,994 | ≈ 67 GB | 7,302 | the same (`GuestBackingStore::Unmap`, the MapEntry tree, the Mapping vector) |
| bc5-ring | 58,549 | ≈ 40 GB | 12 | `bc5::direct::Device::sorted_mappings()` (52,935) |
| bc5-chainwd | 34,837 | ≈ 44 GB | 8,776 | `bc5::direct::Device::sorted_mappings()` (22,049), `Lzr0401::Range` vectors, `VirtualRanges::Range` copies |
| kyty-gpu | 12,309 | ≈ 51 GB | 51 | 3–7 MiB from KytyDirectMemory to renderD128 (uploads) |

- **game-main's copies are not guest data.** Sizes are 0.25–3 MiB, and the destination and source are both host heap
  (`[anon]`). They are KytyPlus's guest-memory bookkeeping: range lists kept as sorted vectors (or rebuilt copies),
  shifted or reallocated on every guest map / unmap / rename.
  - The fault record of result 18 shows ~29,000 views and 29,767 GPU mappings, so each edit moves MiB. That is O(n)
    per operation, at about 1.7 GB/s on game-main over the window.
  - Some names are approximate where inlined, but the family is clear.
- **The Render Thread spins on game-main meanwhile** (result 17). On the console a map / unmap edits page tables,
  O(1) per page, with no copy of a global list.
- **bc5's own submission path pays a similar O(n) copy:** `Device::sorted_mappings()` copies the sorted mapping list,
  inside the flush_mu holds of F869.
- **Fix candidates** (one test build, each behind a switch; offline tests that compare the resulting map state, and
  the guest's views, before and after):
  - **A1, KytyPlus memory:** the range structures of `VirtualRanges`, `GuestBackingStore` and `PooledMemory` as
    ordered maps, or an interval structure keyed by start, with in-place merge and split: no vector shift or full
    rebuild per edit.
  - **A2, backend:** `sorted_mappings()` hands out a shared immutable snapshot (rebuilt once per change, shared by
    every submit) instead of a copy.
- **This replaces the AMPR hypothesis of result 17.** The AMPR symbols were neighbours, not the caller. APR reads run
  on the APR workers, and AMM commands move no bulk bytes. game-main's map / unmap calls go through these memory
  structures.

## A1 / A1m / A2: the mapping bookkeeping edited in place (design, not built; for every title)

**What the code does today** (KytyPlus f266548 with patch 0001, `src/kernel/memory.cpp`, `memory.h`,
`memoryAddressSpace.inc`). A read-only reading, its key claims checked by hand: `m_ranges` is a vector at
memory.cpp:875, and `SameMergeKey` rejects Direct at 625–627.
- **`VirtualRanges::m_ranges`** is a `std::vector<Range>` sorted by start (memory.cpp:875). A Range is about 72 B, so
  29,000 ranges are about 2.1 MiB, matching the 0.25–3 MiB copies.
  - Every Add, Remove, Rename, Protect or SetMemoryType, and every merge, inserts or erases in the middle, so the tail
    moves (`insert` 337, `erase` 349, 705 / 716, 786–787, 810–811, 825).
  - One AMM fixed map over a live range (ReplaceFixedRangeWithReserved) makes about 6–8 tail moves, roughly 7–9 MiB per
    remap.
  - `Snapshot` / `SnapshotWithDirty` (487, 498) copy all 2.1 MiB for the BC5 host's readers (`Bc5ForEachPrivateRegion`
    on every sync, `Bc5ForEachMappedRange`, `Bc5RangesWithDirty`).
- **`PhysicalMemory::m_mappings`** is a `vector<AllocatedBlock>` (~104 B each; sorted when `KYTY_BC5_PHYSMAP_SORTED`,
  the default).
  - Insert and erase move the tail (918, 959, 968).
  - `ProtectMapping` rebuilds the whole vector (2253–2287), once per Direct range of an mprotect.
- **`FlexibleMemory::m_allocated`** (`vector`): a full sort per Map (2462); full rebuilds per Unmap and Protect.
- **`PooledMemory`:**
  - `m_mappings` is an unsorted `vector<Mapping>` with linear queries. Release rebuilds a vector with no reserve (the
    profiled `_M_realloc_append`).
  - `m_free` is a `vector<PhysicalRange>`, sorted and rebuilt per released piece.
- **`GuestBackingStore::m_maps` and `GuestAddressSpace`'s maps** are `std::map`, so their edits are O(log n) and move
  nothing. Their names in result 19's chains are inlining neighbours. `FindFreeAlignedUnlocked` walks `m_free` from
  `begin()` and ignores its search start (memoryAddressSpace.inc:1281): O(n), but not a copy.
- **Which splits are ours:**
  - Flexible and Pooled maps make one view and block per free-backing fragment.
  - Protect and type edits split ranges.
  - A non-exact Rename splits through EditUnlocked.
  - A partial unmap splits a backing view into left and right.
  - ReplaceFixedRangeWithReserved re-adds a Reserved "anon".
  - Named direct maps are added as "" and then renamed.
  - There is no 2-MiB chunking.
- **Merging:** VirtualRanges merges only non-Direct ranges (`SameMergeKey` rejects Direct, 625–627, and never checks
  that offsets continue). So the 42 % contiguous direct views of result 19 are never merged; the free lists do merge.
- **Locking:** the guest entry points take `g_memory_operation_mutex` (recursive). The BC5 host's snapshot readers take
  only `VirtualRanges::m_mutex`. Callers keep no iterator or pointer across calls; every query returns copies.
  - Vector-specific uses: `bc5::map_records::touching(m_ranges, …)` returns index pairs, `Bc5ForEachPrivateRegion`
    runs `upper_bound` on the snapshot, and the pm412 templates take random-access iterators.

**A1: ordered containers with in-place split and merge** (switch `KYTY_BC5_0438_A1`, test build only; the old vectors
stay selectable).
- **The containers:**
  - `VirtualRanges::m_ranges` becomes a `std::map<uint64_t, Range>` keyed by start. A split shortens the left node in
    place and emplaces the middle and right nodes with hints; a merge erases a neighbour node.
  - `PhysicalMemory::m_mappings` and `FlexibleMemory::m_allocated` become maps keyed by `map_vaddr`. `ProtectMapping`
    and Flexible's Unmap / Protect edit only the window.
  - `PooledMemory::m_mappings` becomes a map keyed by vaddr. `m_free` becomes a map with neighbour merge, as
    GuestAddressSpace's already is.
- **The queries:** the public queries keep their signatures and results.
- **Snapshots:** cached by `Generation`. One vector per change, not one per call: the host's readers stop copying
  2.1 MiB per sync.
- **The rewrites:** `touching()` and `DirtyWithTouching` work on map iterators.
- **Also:** `FindFreeAlignedUnlocked` starts at `m_free.upper_bound(search_start)`.
- **Test** (`test_a1438`): a differential test drives old and new with the same operation sequences, random ones
  plus a recorded one if a normal run's journal holds one (TODO: check the journal tags). It compares every query
  result and the final range lists. A broken copy (a split that loses the right part) must fail.

**A1m: merge contiguous same-attribute direct views** (switch `KYTY_BC5_0438_A1M`, on top of A1).
- `SameMergeKey` also merges Direct when `right.offset == left.offset + left.size` and the protection, memory type
  and name match; never for `disallow_merge` (NO_COALESCE).
- It needs `PhysicalMemory::Unmap` and `ProtectMapping` to accept a span covering several blocks. Today Unmap matches
  one block, so a merged range's munmap would fail with EACCES (memory.cpp:3306–3309).
- It is guest-visible: VirtualQuery and QueryMemoryProtection return larger ranges. TODO(verify): whether the
  console's vm_map coalesces such entries; until then A1m is an experiment arm, not a default.
- Up to −42 % of the ranges (result 19).

**A2: the backend's mapping list, not copied per change** (switch `BC5_DIRECT_0438_A2`).
- **Today:** `Device::sorted_mappings()` (backend/src/direct.cpp:851) rebuilds lazily per `list_gen` (exp 0170). But
  each rebuild copies and merges every entry (~17,000 shared maps plus the userptrs) under the device mutex. In the dip
  the list changes ~900 times a second, so nearly every submission rebuilds ~0.7 MiB (result 19: 52,935 + 22,049
  copies).
- **A dirty flag would not help:** a change lands between nearly every pair of submits.
- **A2's structure:** a chunked persistent list. Sorted chunks of ≤ 512 entries sit behind a top array of
  `shared_ptr<const Chunk>` (~34 entries).
  - An edit copies only the affected chunk (~12 KB) and the top array, under the device mutex.
  - `sorted_mappings()` returns the top array's `shared_ptr`.
- **The readers:** `submit_now`'s probe (`covered_sorted`) and the filter's `mapped` callback. They hold the snapshot
  for one submission's preparation and filter (milliseconds) and need it stable for exactly that long. A lookup is a
  binary search on the chunks' first VAs, then within the chunk.
  - `covered_sorted` takes the chunked type; one overload.
- **Test** (`test_a2438`): the same random edit sequences against today's rebuild, comparing every `covered` answer
  and the flattened list.

**Non-atomic windows** (the top session's point 6):
- **What exists:** a partial `UnmapOne` replaces the whole old view with PROT_NONE and then remaps the left and right
  parts (memoryAddressSpace.inc:413–429). `ReplaceFixedRangeWithReserved` runs `UnmapGpuRange` and the range's
  Remove before the new view is mapped (memory.cpp:4259–4260, 3945–3948).
- **What the GPU can see:** the direct and private memory reach the GPU as dma-bufs of their memfds (ADR 0006, exp
  0023). So the GPU sees backing pages, not the host's VA swaps. Only the `UnmapGpuRange` gap is a GPU-visible window,
  and only at the range's real, page-aligned addresses.
- **So these windows do not explain S347's faults** (result 18: valid low halves under junk high parts). No tie to the
  F852/F858 class from this reading.

**Test-build order** (the top session's point 5): A2 and A1 first, then A1m and Q438, with the T arm env-only. One
build, each behind its own switch. Lean A/B on the third title and ASTRO BOT; in normal builds a compare-only check of
new against old, never a repair.

## Finding draft (separate, not chased): host text in guest memory

u438sK2's dumped dcb #65701 has a title NOP marker (dword 718, 10 dwords). Its payload is host journal text, "eps its
wait at 6167 on 0x12004b4c38", from k438's 10th journal line. Title memory at 0x11e0450aa8 (one of the title's direct views,
eager at 0x11e0000000) reads "its wait" too, at the probe. The title's own NOP markers carry its debug strings, copied
from its memory. So host-formatted text reached guest memory that the title later copies or uses. A candidate, not
checked: host code (`journal`'s formatting) running on a guest thread's stack, below the title's frames, in memory the
title reuses. To be checked on its own: which thread's stack spans that address, and whether host buffers live in
guest-allocated stacks.

## Result 20: r438o, two holes in the deployed r438 and their fix (F874, F875; 2026-11-21)

Two holes in the deployed r438 (patch 9889b06a), found offline on the bake unit ff9e8fe2:

- **Ring order (F874).** Another thread's real write of the same label can pass a taken slice's early write in `g_plw`.
  - bc5-ring's `r438_begin` gives the early write order N. Before the slice's own job registers it for real, the Render Thread's or bc5-chainwd's `submit_now` can register a real write of the same label with order N+1.
  - `ring_will_satisfy` then answers a game-thread wait on the slice's value "not satisfied", while its writer is still to come.
- **The trim (F875).** `g_plw`'s trim erases the oldest 4,096 entries by position, early ones included.

Both reproduce deterministically: `r438o/test_r438o.sh bake438.cpp order` and `... trim` FAIL.

The fix, `r438o/mkr438o.py`, works inside the EARLYREG path and has no new switch:

- **E2:** `register_label_writes` renumbers the other early entries of its labels after its own real writes.
- **E3:** with r438 on, the trim drops only real entries. The bound: an early entry lives only until its slice's `r438_end`, so the table holds at most 8,192 real entries, one batch and the slices in flight.
- **E4:** normal-build counters in r438's 60-s line.
- **E5:** the renumbering scan runs only while early entries are in the table (`g_r438o_live`).

Tests:

- order and trim PASS.
- The planted bugs (no renumbering; the old trim) FAIL.
- Identity with EARLYREG=0 and with it on equals the bake unit.

The lean A/B on ASTRO BOT, on the clean boot c05993c0 (`r438o/ab438o.sh`; MangoHud per frame, from 30 s, 140 s per run):

- **q438oA**, without E5:
  - Control d3485ed4: 59.67 / 59.48 / 59.32 flips/s, p99 17.0 / 17.4 / 33.3 ms, over 50 ms 1 / 5 / 4.
  - r438o lean aae9c294: 59.11 / 58.88 / 59.22 flips/s, p99 33.5 / 33.7 / 33.5 ms, over 50 ms 5 / 7 / 3.
  - The ranges do not overlap: about 0.7 % lower, and the p99 doubled.
  - The normal run printed no r438 line: ASTRO took no slice.
  - The cost was r438o's renumbering scan of the whole `g_plw` on every `register_label_writes` under `g_plw_mutex`, with nothing to renumber. E5 removes it.
- **The deployed r438 itself** adds no per-submit scan of `g_plw` on a title with no slices. Per submit it adds only:
  - `t_r438_real.push_back` while a slice is on (bake unit line 9254);
  - the PLWCV `notify_all` (line 9263).

  Its scans run per slice (`r438_begin` / `r438_end`) and at waits (`ring_will_satisfy`).
- **q438oB**, with E5 (unit 2e6168de; lean ef76f031, normal 94e0e462), the same boot, 14:27–14:50:
  - Control: 58.61 / 58.56 / 58.54 flips/s, p99 33.89 / 33.90 / 33.86 ms, over 50 ms 4 / 8 / 4.
  - r438o: 58.69 / 58.51 / 58.05 flips/s, p99 33.84 / 33.87 / 34.36 ms, over 50 ms 6 / 8 / 4.
  - The ranges overlap for flips/s and p99, and r438o's over-50 counts are within the control's.
  - Means: control 58.57, r438o 58.42; the lowest run is O3.
  - The control itself fell from 59.49 (q438oA) to 58.57 flips/s on the same boot, and its p99 from 17 to 34 ms. That drift of the box is larger than the difference between the arms.
  - The normal run again printed no r438 line (no slice) and no kernel line.

**The bake (2026-11-21 14:52–15:02, the top session's GO; one lock line for the swap and the smoke):**

- Patch 9889b06a → 0fede35d (135 files, exp 0372 lines 5, the pad_audio_route header in).
- Normal b1b57df9 → 199a0f39, lean d3485ed4 → 3a20b974, archive d6638808 unchanged. No switch word gained or lost.
- Smokes: o438sc (ASTRO lean 200 s) and o438sn (normal 200 s) PASS, 0 kernel lines. The exe md5s read back.
- The chain cannot separate a cost under about 0.3 % from the boot's drift, and every r438o run followed a control run.
- Undo: `bash ~/bc5-work/exp0438/r438okit/bake/undo0438o.sh`.

**Unexercised.** ASTRO BOT takes no r438 slices, so this A/B shows only that r438o costs nothing when idle. The fix's own path (the renumbering and the trim-keep) stays unexercised on a real title until the second title is installed again.

**Display mode of these series (LESSONS R72).** Every lean series of 2026-11-21 from 13:51 on ran at 640x480@59.94, not 1920x1080@60. On boots c05993c0, c97d43e6 and 7986fd90 the kernel logged "No EDID read" on DP-1, and the boot check read only `status = connected`. That covers q438oA and q438oB (result 20), qa1A, qngA, qggA and qbkA. They are valid as within-series comparisons only, not as measurements of normal play, and they cannot justify a bake. The r438o bake of 14:54 stays as deployed (its series was a no-regression check). The bake candidate's A/B has to run again at 1920x1080 under the five-pair rule. Since then ab438o.sh and the smokes check the display (`display438.inc`: EDID > 0 bytes, first mode 1920x1080, 0 "No EDID read" lines in the boot, active mode 1920x1080@60 from kscreen-doctor) and write the mode into each series header.

## Result 21: the acb gate (F878, F879), A1 + A1P + A2, and the bake candidate (2026-11-21, boots c97d43e6 and 7986fd90)

Two holes in bc5-ring's acb gate, both found offline, and their fix:

- **F878, in flight.** The gate passed an acb on a stale label value while the label's writer was inside its submit_now (det `inflight` on 2e6168de: at_wait gave up after 77.2 / 31.4 ms).
  - Together with an ordering wait this forms a two-ring hang through ring order: det `rings`, on the shared unit with every switch off.
- **F879, open chain.** The same window exists while the writer sits in its owner's open chain. INFLIGHT_NG alone cannot see it; the full set hung at #67 with INFLIGHT_NG on.
- **The fix:** `BC5_0438_INFLIGHT_NG` + `BC5_0438_OPEN_NG`. A live count of pending writers makes the test one atomic load when idle (ngcount).

Lean A/Bs on ASTRO BOT. MangoHud from 30 s, 140 s per run; alternating; judged only within each series.

| Series | Arms | flips/s | Verdict |
|---|---|---|---|
| A1 + A1P + A2, boot c97d43e6 | control 59.65 / 58.39 / 58.60, A1+A1P+A2 58.55 / 58.64 / 58.66 | — | overlapping |
| INFLIGHT_NG alone, unguarded | control 58.65–59.08, INFLIGHT_NG 58.39–58.45 | about −0.8 % | not overlapping (the per-poll scan) |
| INFLIGHT_NG + OPEN_NG, guarded (W0 discarded) | control 58.05–58.61, both on 57.96–58.22 | means −0.24 % | overlapping |

- In the A1 + A1P + A2 series, C1 (59.65) is a first-run-after-boot outlier.
- The guarded gate on ASTRO: 371 in-flight holds per minute, longest 2.7 ms, all released by the writer's registration, none by the 10-s fallback.
- The gate costs one full test in about 65 polls.

The bake candidate (bake438b: A1 + A1b + A1P + A2 + the guarded gate, all on unless "0"; without SUBMITQ, R438_LWM and A2_CHECK):

- **Private build:** normal 87f2e1cf, lean 2761e911, archive a548a249.
- **Lean's switch words:** 500 → 505, none of its diagnostics.
- **Pairs 1–3** (boot c97d43e6; W0 discarded): shared lean 3a20b974 58.68 / 58.68 / 58.95 against bake lean 58.90 / 58.21 / 58.26 flips/s. They overlap only through O1, with means −0.5 %, so the swap was held.
  - In its N1 run the gate's longest hold was 23.9 ms. The mapping work was the same as the gate-only run (about 1,500 rebuilds by 60 s); "BOs retired while busy" was 233 against 38. Not explained.
- **Pairs 4–5** run on a different boot (7986fd90): judge them within their own alternating pairs.
  - The first attempt's control run qbkBC1 (19:45, boot c97d43e6) is VOID. It ended at about 57 s when the box was shut down from the desktop (an orderly logout and shutdown at 19:45:13; no amdgpu line, no pstore, no fault record). It is not a failure of 3a20b974.

## Verdict

**F865's source is fixed and built into the shared builds (r438 with PLWCV, 2026-11-21 00:52). The long frames are a
separate, host-side question (result 14).**
- **F865's cause** (from the records, high confidence): a game-thread dcb wait on an acb's release, with no writer on
  any ring yet, was given up after ~21 ms (the F262 give-up). The dcb ran ahead of the acb's work and the GFX ring
  hung. It is not F3's case: F2 cycles were 0 all run.
- **The fix at the source: r438.** bc5-ring registers a taken slice's label writes "early", before the kernel call.
  The game thread's wait on such a label waits for the real registration and is kept in ring order. So the writer
  is in the kernel before its waiter and the give-up path is never reached; there is no give-up and no recovery.
  PLWCV makes that wait a condition variable (0.06 ms median wake against 4.9–7.0 ms for the poll, test case 6).
  - **Invariant** ("an early write must reach the ring"): 0 lost in every r438 run, about 3.8 M early writes per run.
  - **Give-ups:** 0 in every r438-on run counted here (R ×3 in result 6, H ×3 in result 14). Off: 1 in 3 C3 runs
    (result 6) and 2 + 1 in the two O runs (result 13). The base rate is too low to call it a shown removal by count;
    the mechanism removes the path.
  - **Frame time:** no measurable effect in 3 + 3 + 3 lean runs (result 13): L0 35.33, L1p 34.81, L1c 35.03 flips/s,
    with the same median, p95 and p99.
- **Refuted on the way:**
  - k438 (keep the wait for the GPU): 1 GPU hang in 1 run, at its own kept wait;
  - k438b (ADR 0013's held tail, no give-up): 1 GPU hang in 1 run;
  - e438 (build 12's lazy freshness): closed;
  - p438 (the prologue merge): correct offline, no frame-time gain (result 13), not baked.
- **The bake** (the maintainer's "tak - wdrażaj wszystko, tym bardziej jeżeli nie obniża płynności a poprawia
  błędy", through the top session):
  - patch `bb04219b` → `9889b06a`, normal `b1b57df9`, lean `d3485ed4`, archive `d6638808` unchanged;
  - `BC5_0438_EARLYREG=0` turns r438 off for one run with no build, `BC5_0438_PLWCV=0` gives the 20-µs poll;
  - undo `bash ~/bc5-work/exp0438/bake/undo0438.sh`.
- **Open, for a next experiment (result 14):**
  - The Render Thread's long frames spend more CPU outside our gc calls (~27 ms in a 3+ frame), and with it far more
    minor faults.
  - They also wait on the chain slot's flush-order lock s.flush_mu inside the submit list (13 ms per 3+ frame).
  - The dip at G+150–160 is the extreme of both.
- **Pacing (lean, 105,883 frames):** not two-moded. It follows the scene: ~45 flips/s, the dip to ~11, then ~27.

## HANDOFF rows

In `docs/HANDOFF.md` since 2026-11-21: F866 (F865 was the F262 give-up), F867 (r438 with PLWCV, the source fix, built
into the shared builds), F868 (frame pacing and the Render Thread's long frames, diagnosis).

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
