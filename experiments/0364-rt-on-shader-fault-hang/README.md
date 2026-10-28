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
