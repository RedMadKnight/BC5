# 0364 — The RT-on shader-fault hang of F443: which dispatch wrote where, and why the GPU had no page there

**Date.** 2026-10-28. **Branch.** `exp/0300-rt-dispatch-sync`. **Box.** Offline so far (no run); box runs RT on under
the lock, after exp 0360's slots.

**Question.** Exp 0356 R2 (S6N, RT on, the ledger build) hung at 107 s: a TCP write fault at 0x1110e1d000 with four
faults at junk addresses 0xe3808c5f2000…0xe3808c634000 in the same second, the GFX ring reset recovered it (F443).
Which dispatch of the hung dcb #81108 wrote to 0x1110e1d000 — its program, user data, descriptors? Is the junk the
F399/F403 class (a stale descriptor, a pointer from a lost or late frame)? Does it sit near the ~100-s big frame
that exp 0349's cut now handles? Then a trap or a fix.

**Setup.** Read-only: the journal `~/bc5-data/captures/play-20261028-1046/gc/direct.log`, the dumps
`ib-timeout-00081108-dcb-34003.bin` (decoded with `tools/bc5-agc dump` into `~/bc5-work/exp0364/dcb81108-dump.txt`
on the box; 19,617 lines) and `…-00081109-acb-4.bin`, the devcoredump `20261028-104822-devcd1.txt`, exp 0356's
`raw/R2-kernel-stream.txt`, the shared learned list `~/bc5-work/direct-learned-pkg.txt` (109 windows), the host's
code in patch 0001 (the learned regions, the hints, the lazy names). Nothing of the title's data leaves the box.

## Result

- **F467 — the faulting pointer is the title's own user data: a recurring compute dispatch family carries 32-bit
  offsets in its user-data registers under one shared high dword, and the second member's output pointer is the
  faulting page.** The dcb opens with triples of dispatches (first `DISPATCH_DIRECT` 1×1×1, then `DISPATCH_INDIRECT`
  with argument offsets 0x40 / 0x27f40 / 0x3f640, 0x0 / 0x27f00 / 0x3f600, …, each triple preceded by a
  `LOAD_SH_REG_INDEX` from a table at 0x909841e50 / 0x909842900 / 0x9098426a0 … — the program registers come from
  those tables, not from the IB). Every member sets `COMPUTE_USER_DATA_3..6` by `SET_SH_REG`: the three members
  carry (3, 4, 6) = (0x8c61aa00, 0x8c5f4500, 0x722cf000), (0x8c632100, 0x8c631d00, **0x10e1d700**), (0x8c5f2b00,
  0x8c5f0000, 0x12779f00), all with `USER_DATA_5` = 0x11 — the high dword of the title's 4-GiB window (exp 0346
  learned 0x1100000000 for the same title). So the second member's `USER_DATA_6` is the pointer 0x1110e1d700, and
  the first fault, a TCP write at page 0x1110e1d000, is that dispatch writing its output. The four junk faults are
  the same family's `USER_DATA_3` offsets (0x8c632100 → page 0x8c632000, 0x8c61aa00 → 0x8c61a000, 0x8c5f2b00 →
  0x8c5f2000, and 0x8c634000) under a garbage high dword 0xe380 instead of 0x11: once the first access faulted
  (`MORE_FAULTS` set, no retry), the waves' later loads of a high dword returned garbage and the pointers built
  from it went to nowhere. One cause, then, not two. The devcoredump agrees on where: `CP_IB1_CMD_BUFSZ` 0x9740,
  `CP_IB1_BUFSZ` 0x94e0 — the CP had fetched 608 dwords of the 38,720-dword host IB, i.e. the hung dispatch is among
  the first dozen packets, where these triples are; `GRBM_STATUS_SE0/SE1` 0x08000006 (shaders busy in two SEs), the
  fault status 0x00741051 (TCP, write, MORE_FAULTS), the same shape as F403's freezes but with a real address.
- **F468 — the page had no GPU mapping because the title's memory there was not imported: the host's learned
  windows (109, one per 96 MiB region learned at an earlier fault) stop at 0x1116000000, and the pointer sits
  below the lowest of them, in a region the lazy policy leaves out.** The learned list covers 0x1116000000 …
  0x1855…; nothing covers 0x1110e1d000 (the run's private copy learned 0x110e000000+0x6000000 at the fault, the
  mechanism's purpose: `learned_add`, 64-MiB-aligned, 32 MiB before, 96 MiB long). The run's lazy names were
  `orbis_user_malloc` (the title's CPU heap, from `bc5-run.env`) and F394's four; a lazy view is imported only where
  a hint or a learned region asks. The title's shader data is placed by the title in its window; when it lands in a
  lazy view that no earlier run has faulted on, the first GPU access faults, the host learns the region, the kernel
  resets the ring, and the next run has it. That is the "one hang in ten RT-on runs since the cut" of F443: not the
  cut (the big frame of t 101.8 s was cut and ran), but a region the accumulated list had not met — this run's was
  the lowest region of the window so far. The hang sits one second after the big frame, in a stretch of heavy
  mapping churn (the 128 submissions before: direct sync 48.4 ms, views +30 / +3 / +6 and −24 / −5, maps 15.3 ms =
  want 4.7 + drop 6.8 + add 3.5, learned 51.9 ms): the title was mapping new memory for the scene, and the first
  GPU write into one of the new views found it unimported. Whether that view was `orbis_user_malloc` or a hole
  the title never mapped (exp 0255's class: a TCP fault with no guest memory) the dumps cannot say — the journal does
  not record the views' names and ranges; a hole would mean the title's pointer is bad (F403's class after all),
  a lazy view means the host's import policy is. The 0x11-window placement, the regular family and the 109 learned
  windows all inside the title's window argue for the lazy view.
- **F469 — the cut is not involved.** The big frame (1,121,536 dwords, cut into two IBs at the default limit at
  t 101.8 s) completed; #81108 (34,003 dwords) is a later, small job, submitted at t 102.84 s and timed out at
  104.84 s; exp 0352's arms cut jobs of 1.04–2.27 M dwords 600 s each without a fault.

## Design: the trap, and the fix candidate

1. **Trap (name the view at the fault).** In `recover_after_timeout`, before `learned_add`: look the faulting
   address up in the title's mapped ranges (KytyPlus's list the direct mapper already reads, with the names
   `direct_lazy_name` is applied to) and journal the covering range's name, bounds and whether it is lazy, or "no
   guest memory" — one line. That settles F468's last question at the next occurrence and costs nothing.
2. **Fix candidate (compute user-data hints).** The hints pass already turns the render-target base registers
   (CB/DB bases, the `hint CB0 0x113f230000: window …, direct memory +34.0 MiB` lines) into forced imports of a
   64 MiB window in direct memory before the job runs (`direct_force`). Extend it to compute user data: for each
   dispatch, each `COMPUTE_USER_DATA_n` dword that, under the title's learned window high dword (exp 0346's
   `hi_window_learned`; 0x11 here), lands inside a direct-memory view — lazy or not — gets the same forced window
   (once per 64 MiB, the `hinted` list as today). The lazy policy keeps its memory saving (the CPU heap stays out
   until the GPU is about to touch it), and the first touch no longer faults. Cost: a few compares per dispatch in
   the filter's pass; imports happen once per region. Measured by: S6N RT-on runs with a reset learned list (a
   private copy emptied of the 0x11-window entries) — without the hint the first runs hang as F443 did; with it they
   should not, and the journal's hint lines name the regions. Behind `BC5_DIRECT_USER_DATA_HINTS=1`, off by default
   until measured; a Catch2 case for the pointer rule (offset + window, inside a view) in the backend.
3. Not a candidate: importing `orbis_user_malloc` eagerly (F394's memory pressure: the title pins 9.8 GiB already).

## The build and the runs (17:00–18:xx)

**Build.** `raw/build0364.sh` (0359's pattern): the backend's Catch2 first (84 cases pass, the four `[user_data_hint]`
among them), then `src/libs/bc5LleAgc.cpp` patched by `raw/patch0364.pl` in a private copy, compiled with the shared
normal build's compdb command and relinked with the shared objects of 1000ad2a (exp 0361's integration) and the
archive bb50b2e0 (header-only change). Three versions in the afternoon: v1 86f6c2f8 (the hint, "asked" = chunks
marked), v2 cf3d1e53 (the window's views and its bytes not yet imported journaled, the 1 MiB threshold, a forced
sync only when something is missing), v3 (16-byte-aligned candidates only; after the forced sync the hinted
windows re-measured). Nothing shared written; the previous binaries kept beside the new one.

**Runs.** `raw/s6n0364.sh` (exp 0358's S6N script under `~/bc5-work/exp0364/`: the S6N route save, RT on, the private
working directory, a private copy of the learned list), `BC5_0364_RESET_LEARNED=1` dropping the 31 learned windows
inside the title's 0x11 window from that copy (78 of 109 kept), so the runs meet those regions as a box without
the accumulated list would; the kernel log streamed by the script; 600 s each; the live saves compared only.

| run | build | hint | result |
|---|---|---|---|
| R1 17:26 | v1 86f6c2f8 | on | pass, 35.5 flips/s, no fault, no learned window; 62 regions asked (2,108 MiB marked) |
| R2 17:49 | v2 cf3d1e53 | on | pass, 35.8 flips/s, no fault; 62 regions asked, 122 MiB of them not yet imported in 3 regions |
| R3 18:01 | v2 cf3d1e53 | off (trap only) | pass, 35.0 flips/s, no fault, nothing learned |
| R4 18:13 | v3 1336dbd4 | on | MACHINE-DOWN at t ≈ 122 s (F475): a GFX ring timeout without a fault, the reset failed, the watchdog rebooted the box 18:15 |

- **F472 — the hint finds the F443 case before it happens: on the route a dispatch's user-data pointer landed in
  the title's lazy `FileSystem` heap with 52 MiB of it not imported for the GPU, and the hint asked for it.** R2's
  journal: `hint user data 0 0x11114b2000 (dispatch at 8084): window 0x110f4b0000+0x4000000, 1 views, lazy:
  FileSystem, 52.0 MiB marked, 52.0 MiB not yet imported`. That pointer is the same user-data family as F467's
  (register 0, the window's high dword 0x11), the region is the one F443 faulted in (0x1110e1d700 lies 25 MiB
  above it, in the same heap), and the heap is one of the four F394 made lazy — so F468's open question is closed:
  the title keeps GPU-written buffers in its `FileSystem` heap, the lazy policy does not import that heap, and a
  first GPU write into a part of it no earlier fault has learned is the one-in-ten hang. Two more windows had
  unimported bytes in R2 (66 MiB at the window's start from a false candidate 0x100011 — v3 rejects it: real
  pointers are 16-byte aligned — and 4 MiB at 0x1102d00000); 59 of the 62 windows were already imported (normal
  views) and the hint cost nothing there. Over 600 s: 709,120 IBs, 32.8 M dispatches, 168 M candidate dwords, 62
  regions; the hint pass adds 0.8 ms per 128 submissions to the timing split (hints 2.17 ms against 1.36 ms in
  0358 R1: ~6 µs per IB).
- **F473 — the learned-region path did not cover F443 because the list grows one hang at a time and the title's
  heap placement moves: 31 of the 109 learned windows are the title's 0x11 window, all learned at earlier hangs, and
  F443's region lay below the lowest of them; a fresh box (or a title update that moves the heap) meets every
  region again.** With the 31 windows dropped, three 600-s S6N runs (R1–R3) still passed — the event is rare on the
  route (F443's one in ten), the regular sync's lag usually suffices, and the hint's imports in R1/R2 covered the
  three windows that were missing. R3 (the hint off) had no fault to show the trap's view line; the trap stays in
  for the next occurrence.

- **F474 (corrected by R4) — the forced sync after a hint does import the marked chunks before the job: v3's check after
  the sync reads "66.0 / 52.0 / 4.0 MiB were not imported, 0.0 MiB still are not" for the three windows that mattered,
  in 0.0–0.1 ms each** (memfd chunks whose pages already exist import cheaply; v2's "0.0 ms" lines were real, and the
  "+N BOs" journal line I looked for is printed by the mapping rebuild, not the import). So the hint is a real fix of
  the import path: the region a dispatch's user data points into is imported before the dispatch runs, with the
  title's own views — not a skip, not a NOP — and the lazy `FileSystem` view of F472 was imported that way in R4 too.
- **F475 — R4 (v3 1336dbd4, hint on, the list reset) ended in a machine-down at t ≈ 122 s: a GFX ring timeout with no
  fault (`timeout: fault 0x0 status 0`), the kernel's ring reset failed, the full GPU reset began, and
  `bc5-gpu-watch` crashed and rebooted the box (18:15:05, up again 18:15:35).** The hung pair: dcb #103567 (10,842
  dwords, 53 dispatches, 14 indirect, the largest grid 57,600 groups) and acb #103568, both timed out after 2,026 ms;
  the probe's last ran dispatch at dword 10652 (program 0x11d03fe700, 320×180×1) carries in `COMPUTE_USER_DATA_0..3` a
  V# whose base reads 0x117ffa00 and which the probe calls unmapped (a bare 32-bit value, TODO(verify) whether the
  probe shows the descriptor's low dword only); the submit line counts `unmapped 2`. The devcoredump
  `20261028-181505-devcd2.txt` (5.9 MB), the dumps `ib-timeout-00103567-dcb-10842.bin` / `…-00103568-acb-68.bin` in
  `~/bc5-data/captures/play-20261028-1813/gc/` and four pstore records (`~/bc5-data/captures/pstore/`, the panic's
  kernel log) are kept; nothing of them in the repo. This is F399/F403's class (a stuck dispatch, no page fault, the
  ring reset failing), not F443's (the TCP fault). Whether the hint's forced syncs — a direct sync in the submission
  path, 0.0–0.1 ms, three in the run's first 20 s, none within 100 s of the hang — had a part is open: R1–R3 ran the
  same forced syncs (v1 after every hint, v2 after a missing one) 600 s each without a reset, and the three F399
  freezes of 2026-10-26 had no hint at all. The run and every other session's run died with the reboot; the shared
  builds and archive are intact (1000ad2a, bb50b2e0), the live saves were only read.

**Verdict.** F443's hang is explained: a dispatch's output pointer into the title's lazy `FileSystem` heap, in a
part of it no earlier fault had learned (F467–F468, F472–F473). The compute user-data hint (F474) imports such a
region before the dispatch runs and is the fix candidate for the shared builds, behind `BC5_DIRECT_USER_DATA_HINTS=1`
(the title's window from `BC5_DIRECT_HOST_INDIRECT`), with the fault-view trap beside it; three 600-s runs with the
hint and the learned list reset passed, one ended in a machine-down of F403's class (F475) whose relation to the
hint is not shown either way. No further box run from this session after the reset: the next step — R4's dumps read
offline (the V# at dword 10652), and whether to repeat the runs with the hint on and off — is the top session's call.

## R4's dumps, read offline (18:4x)

- **F476 — R4's machine-down is F403's class exactly, not F437's runaway grid and not a stuck V#, and the hint is not
  in its state.** The devcoredump `20261028-181505-devcd2.txt`: `CP_PFP_INSTR_PNTR` 0xe9f and `CP_ME_INSTR_PNTR` 0x77a
  (F403: 0xea0–0xea1 / 0x77a–0x77b), the PFP's last eight packet headers the host's GFX-form indirect dispatch with
  its CP check (`ACQUIRE_MEM`, `EVENT_WRITE`, `DISPATCH_INDIRECT`, `COND_EXEC`, `PFP_SYNC_ME`, `WRITE_DATA`,
  `COND_EXEC`, `PFP_SYNC_ME`) and the ME's two `COND_WRITE`s last — F403's shape to the packet; `GRBM_STATUS`
  0xa0407028 with SE0/SE1 0x0a000016 (shaders busy in two SEs), no fresh fault (`timeout: fault 0x0`; the dump's
  "page fault observed 0x1110e1d000" is the device's last record, 0356 R2's, repeated). Unlike F403 the CP had
  fetched only ~1,920 of the host IB's 12,248 dwords (`CP_IB1_BUFSZ` 0x2858 of 0x2fd8), i.e. it stood near dword
  1,500–1,900 of the dcb, between the indirect dispatch at 1470 and the ME wait at 1570 (`WAIT_REG_MEM` on
  0x11e02104a0 == 1, now 0, "NOT met"). The probe's dispatches in that stretch are small: 2869×1×1 at 1289/1339/1369
  (arguments 0x11d05df300), 3543×1×1 at 1470 (0x11d0571b00), all marked ran, the largest grid of the dcb 57,600
  groups (320×180×1, a direct dispatch at 10652) — nothing like 818×820×819, and the product staircase was not the
  limit here. The probe's "ud0-3 V# base 0x115a2400 … records 7651535 unmapped" lines are its reading of
  `COMPUTE_USER_DATA_0..3` as a buffer descriptor for dispatches whose user data is not one (7.6 M records of 1,136
  bytes is no buffer); a shader stuck on a bad descriptor would fault, and none did. So: waves busy, the CP inside
  the host's own check sequence, no fault — the state the three freezes of 2026-10-26 (F399/F403, before any hint
  existed) and F416's ~106-s bench hang (2026-10-27) showed; R4's came at t ≈ 122 s on the same route. The hint's
  only actions were three forced syncs in the run's first 20 s (imports of 66 / 52 / 4 MiB, each verified imported);
  an import adds mappings and changes no ordering, no label and no packet, and nothing of it is in the CP's state
  100 s later. It cannot be excluded by a proof, only by the state, which shows the class the host had before it.
  The pstore's four records hold the panic the gpu-watch raised after the kernel's "Ring gfx_0.0.0 reset failed"
  (10:48's R2 reset succeeded; this one did not — the difference between a 2-s hang and a machine-down is the
  kernel's reset, not the host).

**Verdict (18:4x).** F443's hang is explained and the compute user-data hint imports its region before the dispatch
(F472–F474). R4's machine-down (F475) is F403's class (F476): the CP inside the host's GFX-form indirect-dispatch
check with waves busy and no fault, the class that predates the hint and that one ring, the guards and the cut did
not remove; its cause is still open (HANDOFF Q20's family), and the host's own check sequence around
`DISPATCH_INDIRECT` is where the CP stands every time. The hint stays off in the shared builds until the top session
decides; a repeat of the S6N runs with the hint on and off would only re-measure a one-in-ten event. No box run
from this session after the reset.
