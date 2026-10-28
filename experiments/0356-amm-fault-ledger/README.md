# 0356 — the host's fatal on an AMM page the title touched (F438)

Ordered by the top session on 2026-10-28. Arm B of exp 0352 ended at 554 s with the host's own fatal, exit 65:
`AMM virtual-memory unmap is unsupported: addr=0x0000008500001930` (KytyPlus `src/kernel/memory.cpp`, F438). It ends
the game for the player, so it ranks with the crash bugs. Base: main 9bd60be (shared normal affa0c22, archive bb50b2e0,
play-pkg.sh 55531ab6); no change to the shared builds (D19). Findings from F442.

**Question.** Which title access reaches the fatal, what the host's AMM model does at that moment, and what the correct
behaviour is instead of exiting.

## What the fatal is (read from the host tree, not a guess)

- The message is misleading: it is not an unmap call. `KernelHandleReservedRangeAccessViolation(vaddr)` runs from the
  host's SIGSEGV handler (`src/loader/runtimeLinker.cpp` line 919) when a CPU access of the title hit an address whose
  `VirtualRanges` entry is named "AMM" and has no page behind it: the AMM window (64 GiB reserved at 0x8000000000, F88)
  or a range an AMM map named. The handler's EXIT was written in exp 0035, when the window reservation itself wiped
  mappings (F87); that cause is gone, and the text stayed.
- The AMM model (`src/libs/libAmpr.cpp`): the title fills an AMPR/AMM command buffer (reads, maps, unmaps, waits,
  address writes, events) and submits it; since exp 0156 a submit only enqueues it and one host worker per priority
  runs the queue in order, as the console's engine does. A map is `KernelMapDirectMemory2` with MAP_FIXED into the
  window (the range then named "AMM"), an unmap is `KernelMunmap` (which also drops the GPU side, `UnmapGpuRange`,
  so no dangling GPU mapping is left by an unmap). The title learns of completion through the buffer's events,
  address writes (`WriteAddressOnCompletion`) and `WaitCommandBuffer`. AMM-only submissions still run at once on the
  submitting thread; mixed ones (reads + maps) run on the worker, behind the reads and the waits ahead of them.
- The same fatal struck three times on 2026-10-18 (runs 634–636, other addresses) and not since, until arm B.
  Nothing in the journal names the range 0x8500000000: the direct path never mapped it, so it is a CPU-side page.
- What could not be read offline: which thread and instruction touched the page (the trace that prints the faulting
  rip exists only with `KYTY_BC5_AMM_TRACE`), and whether the page's map was pending, executed, failed or already
  unmapped. The host keeps no history of AMM commands.

## Design

A ledger of AMM commands (`raw/ammLedger.h`, header-only, `raw/AmmLedgerTests.cpp`): every AMM map/unmap of a
submitted buffer pends from the submit until the worker executes it (keyed by command buffer and record offset),
executed commands move into a ring of the last 16,384 with their result and time, a buffer the engine drops leaves
the pending list. The fault handler (`bc5_amm_fault(vaddr)` in `libAmpr.cpp`, called by
`KernelHandleReservedRangeAccessViolation` before its EXIT):
1. if a *pending* map covers the page: the access was issued before the host's worker reached the map. On the
   console the AMM unit is fast enough for a title that touches a page soon after submitting its map; the host's
   worker, behind file reads, is not. The handler prints the pending command, waits for it (polled every 200 µs, at
   most 3 s), and returns true: the faulting instruction is retried on the now-mapped page. This is the semantics
   the title expects, not a stub: the page is really mapped before the access proceeds. If the map executed with an
   error or did not execute in 3 s, the handler falls through;
2. otherwise it prints the page's history (the executed maps and unmaps overlapping it, the last 16 commands, the
   pending ones on it) and the host exits as before, with a message that says what was found
   (`AMM page not mapped at the access, no pending map covers it`), and the faulting instruction's module and offset
   (the trace line in `runtimeLinker.cpp` is now printed for every fault that reaches this handler).
Two outcomes are possible on the box: the title goes on (the race was the cause; the fix is in place), or the fatal
returns with the page's history, which names the next step (a title access to a page it unmapped, a failed map, a
page never mapped by AMM).

**Setup.** Box: the shared tree's `libAmpr.cpp` 93bdfe77, `memory.cpp` 11b1df22, `runtimeLinker.cpp` e37ed5cd copied
to `~/bc5-work/exp0356/src`, `patch0356.pl` (eight edits), `build0356.sh` + `build0356.py` (the ledger's test built
and run, the three units compiled with the shared build's compdb commands, the shared link command with those
objects; the shared archive bb50b2e0 as it is), `s6n0356.sh` (0352's integrated S6N run on the private binary, RT on,
900 s: arm B hit the fatal at 554 s, arm A did not reach it in 600 s). Kernel log streamed, the live saves compared
only (3f8412c4884ddf14), stop at the first reset. The box is shared with the water session's exp 0355 through the lock.

**Result.**

- **Build** (10:17–10:18): the ledger's test passed (`AmmLedgerTests: ok`), the three units compiled (6 warnings, the
  tree's own), `kyty_emulator` 187910d8 on the shared objects affa0c22 and the shared archive bb50b2e0;
  `patch0356.pl` made 9 edits (libAmpr.cpp 57 lines, memory.cpp 8, runtimeLinker.cpp 2; diffs in
  `~/bc5-work/exp0356/raw/*-0356.diff` on the box). Nothing shared written.
- **R1 (S6N, RT on, 900 s), 10:18:33 → pass, F442:** 35.9 flips/s over 899 s, GPU busy 20.32 ms a frame, host
  prepare 2.80 (filter 1.06); no kernel line (`raw/R1-kernel-stream.txt`), no TIMEOUT, no crash line, live saves
  unchanged (3f8412c4884ddf14). The reserved-range handler never ran: no `amm fault` or `amm ledger` line. The fatal
  of arm B (554 s) did not reproduce in 900 s on the same route; it is rare (once in the day's four S6N runs with RT
  on, three times on 2026-10-18 in the maintainer's plays, never in between). The ledger build is the trap for it.

- **R2 (S6N, RT on, 900 s), 10:46:33 → HANG at 107 s, F443:** a TCP (shader) write fault at 0x1110e1d000 (status
  0x00741051, MORE_FAULTS) with four more faults at junk addresses 0xe3808c5f2000 … 0xe3808c634000 in the same
  second, the GFX ring timed out and its reset succeeded after 132 s; no machine-down, no refusal, live saves
  unchanged (`raw/R2-kernel-stream.txt`; devcd `~/bc5-data/captures/devcoredump/20261028-104822-devcd1.txt`; journal
  `~/bc5-data/captures/play-20261028-1046/gc/`, the dumps `ib-timeout-00081108-dcb-34003.bin` and `…-00081109-acb-4.bin`
  copied to the private folder). The hung dcb #81108 (34,003 dwords) has 58 dispatches, 25 indirect, the largest grid
  1,792 groups: the shader-side class of F399/F403 (garbage pointers in a dispatch's data), not the AMM fault; the
  reserved-range handler never ran in this run either. The cut of exp 0349 is not the cause: at t 101.8 s this run's
  big frame grew to 1,121,536 dwords and was cut into two IBs at the default limit for the first time in this
  experiment, but exp 0352's arms A, B and C each cut jobs of 1,041,856–2,265,120 dwords at the same default (2 and
  3 IBs) and ran 600 s clean. Stopped at the first reset, as ordered.

**Verdict.** The cause of F438 is not yet caught: the fatal did not reproduce in 900 + 132 s of S6N with RT on
(F442, F443), so the ledger has no entry to show. What stands: the fatal is a CPU access of the title to a page of
the AMM window that has no mapping at that moment (the message was a leftover of exp 0035, not an unmap call), the
host keeps no history of AMM commands, and the private build 187910d8 now keeps one: a page whose map is submitted
but not executed yet is waited for and the access retried (the one case that is a host timing artefact, with the
page really mapped before the access proceeds), any other case prints the page's map history, the pending commands
and the faulting instruction's module and offset before the host exits. The fatal is rare (once in four RT-on S6N
runs on 2026-10-28, three plays on 2026-10-18); the efficient trap is the maintainer's own play on this build, which
needs the top session's word for a test shortcut. R2's hang (F443) belongs to the shader-fault class and to the
sessions working on it; its dumps are kept.
