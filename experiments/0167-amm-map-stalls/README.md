# 0167 — The picture freezes then races: the title's streaming maps held the game thread in the host's virtual-range table (a full sort per map); now the table is edited in place

**Question.** The maintainer, at the pad with the window build (2026-10-19 11:09–11:20):
"without chains the sound runs naturally and stays in sync; when the picture freezes on some
scene the sound goes on correctly and then the picture races to catch up. Either drop frames so
the picture keeps moving, or find out what it freezes on." What does the game thread do during
such a freeze?

**Setup.**
- The maintainer's sessions 11:09 (no chains) and 11:16 (chains): the frame profile's frames
  longer than 500 ms, with the game thread's time inside and outside the host.
- `stall-watch.sh` (new): watches the direct journal of the running emulator; when it stops
  growing for 400 ms it dumps every thread's stack (`eu-stack -m`) with the thread states, at
  most every 2 s. Run 810: the gameplay route (start, slot 1, Continue; the save loads into the
  night scene at +121 s) with the watchdog, 230 s.
- `stallcmp.sh` (new): per run, the frames over 250 ms and 500 ms in the gameplay window
  (t 130–230 s) and the audio rate deviations.
- Fix in `src/kernel/memory.cpp` (`VirtualRanges`): the three editing operations
  (`RemoveUnlocked`, `EditUnlocked`, the `ConsumeReserved*` lookups) touch only the ranges that
  overlap the edited span — found by binary search — and keep the vector sorted;
  `MergeUnlocked` sorts only if the table is out of order (a safety net) and merges in place.
  Before, each of them rebuilt the whole vector and `MergeUnlocked` re-sorted it.
- Run 811: the same route with the fix and the watchdog; run 812: the old table again,
  without the watchdog (control); run 813: the fix without the watchdog.
- The maintainer's session with the fix (12:19–12:25, no chains): "much better, smaller freezes
  remain; at the end the game almost froze completely". Its journal and the kernel log.
- Second fix (`bc5LleAgc.cpp`, the direct mapper's BO merge): a merge pass may move at most
  `BC5_DIRECT_MERGE_MAPS` GPU mappings (default 512; 0 = unbounded as before); runs of BOs whose
  mappings do not fit are deferred. Run 814: the route with it.

**Result.**
- In the maintainer's 11:09 session the long frames were of two kinds: frames of 0.5–2.4 s
  almost entirely *outside* the host (t 37, 104, 176, 181 s), and a 6-s stretch at t 201–207 s
  of ~0.8-s frames spent *inside* the host: mapping sync 145–274 ms, hints 91–135 ms and 370–633
  ms of label waits per frame, with the journal full of `cpu-wait WAIT_REG_MEM64 … GIVEN UP
  after 88–208 ms` and `learned … direct memory +2.0 MiB` / `scratch:` lines — the title
  streaming new memory in.
- Run 810's stall dumps name the "outside" kind: in every dump of 1.4 s the game thread
  (`game-main`, state R) is inside the host's memory code called from the title's AMM
  submission — `ExecuteAmmMapCommand → KernelMapDirectMemory2 → KernelMapDirectMemory →
  VirtualRanges::ConsumeReservedSpan → MergeUnlocked → std::__introsort_loop`, or
  `ReplaceFixedRangeWithReserved → GpuResourceManager::UnmapMemory → SendCommandSync`; the
  ring thread sleeps. The table held ~14,000 ranges; an AMM map of the title costs three
  edits, each a full copy and a full sort of the table; a burst of 100+ maps is a second or
  more of the game thread. (The map-only AMM submissions run on the submitting thread,
  `ExecuteAprCommandBuffer`, `amm_only`; the console's AMM engine executes them off the CPU.)
- Runs 810 → 811 (both with the watchdog): frames over 500 ms in the gameplay window 8 (7.5 s)
  → 0; over 250 ms 17 (10.3 s) → 1 (0.3 s); the watchdog fired 11 → 2 times; audio rate
  deviations 0 → 0. Flips per second vary with the scene the scripted route reaches
  (22–43 across runs) and are not the measure here.
- Runs 812 → 813 (the control pair, no watchdog, the same scripted route and scene): frames over
  500 ms 12 (11.6 s of the 100-s window) → 0; over 250 ms 24 (15.4 s) → 1 (0.3 s); frames in
  the window 1,840 → 2,383 (+30 %); audio rate deviations 0 → 0; no fault, no reset.

- The maintainer's 12:19 session: the remaining freezes of 0.5–0.95 s (t 164–181 s) are inside
  the host, `sync` 394–752 ms: the direct mapper's **BO merge** moving every GPU mapping that lies
  on the merged BOs — `maps +7808 -7808`, `+8137 -7798`, `+8012 -8018` in one sync each, with
  the GPU drained first (8 such passes in the session, 1,300–8,100 mappings each). The title's
  streaming heaps carry thousands of small AMM mappings. With the budget (run 814) no pass moves
  more than 512 mappings; four runs stay unmerged (102 BOs instead of ~60), the gameplay window
  is unchanged against 813 (2,394 frames, 1 frame over 250 ms, none over 500 ms).
- The **final freeze** of that session is not a host stall: at t 342.6 s the GE faulted on pages
  0x1000–0xf000 (the first 64 KiB, F208's read from address 0 — the part no user-space mapping
  can cover), the kernel reset the gfx and compute rings ("device wedged"), the host's fences
  timed out at 2 s. The device coredump and the kernel log are saved on the box
  (`~/bc5-work/coredump-1219-f208.txt`, `dmesg-1219-f208.txt`) for the F208 work.

**Verdict.** The freezes the maintainer saw without chains were the host's virtual-range table:
a full copy and a full sort of ~14,000 ranges three times per AMM map, on the game thread, for
every burst of the title's streaming maps. The table is now edited in place around the touched
ranges (F221); the gameplay window lost its half-second-and-longer frames altogether and gained
30 % frames. The remaining 0.5–0.95 s freezes were the BO merge's mass remaps, now budgeted
(F222). The session-ending freeze is F208 (open). Still different from the console: the map-only AMM submissions run on the submitting
thread (the console's AMM engine runs them off the CPU) and each map's GPU-side unmap is a
synchronous round trip to the renderer thread — the next steps if streaming stalls remain.
