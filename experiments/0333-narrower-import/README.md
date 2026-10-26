# 0333 — a narrower eager import of the second title's two big render heaps

*Number claimed by the cloud supervisor, 2026-10-26 (the maintainer: "a i c"). Design written offline from the repo; not
built, not run.*

**Question.** Can the host stop pinning the all-zero parts of RenderGpuWcLarge and CommitIABufferAllocator with no GPU
fault, freeze or loss of frame rate? Does MemAvailable in play then rise from ~0.35 GB (F397, F400) by about what is
released?

**Known before this experiment** (`bc5LleAgc.cpp` 5bccbb80 is main's patch 0001; patch line = file line + 27,271).
- **The import unit** is a 2 MiB chunk (:1356). Chunks are imported in runs up to udmabuf's `size_limit_mb` (`kDMaxBo`,
  :1358; 1,024 since F125).
- **When chunks are imported.** `direct_sync_one` (:1609) runs before each submission (:7232). It does nothing when the
  memfd's `st_blocks`, the views and the forced set are unchanged (:1641). Otherwise it imports:
  - every chunk of an eager view (:1654);
  - only the forced chunks of a lazy view (:1660);
  - the CPU-written chunks of any other view (`SEEK_DATA`, :1665);
  - the whole forced set (:1672).
- **The forced set** is filled by `direct_force` (:1884) from two sources:
  - the learned windows, at each layout change (`learned_apply`, :2372);
  - the hint windows before each IB: every new CB/DB base ±32 MiB (`hint_targets`, :2476–2482, :7251).
- **Nothing is released.** A BO is freed only when a merge replaces it (:1850, `free_shared` in direct.cpp:699) or at a
  device reopen (:5875), which frees them all. udmabuf pins, and so allocates, every page (ADR 0006).
- **What a miss costs.** A shader access to an unmapped page faults.
  - If the job stalls, the 2-s fence wait ends and the backend reads the last VM fault (`AMDGPU_INFO_GPUVM_FAULT`,
    direct.cpp:1236). `recover_after_timeout` (:5821) then calls `learned_add` (:2222), which adds a 96 MiB window
    from 32 MiB below the fault's 64 MiB block to the learned file.
  - `BC5_DIRECT_REOPEN` then waits 12 s and imports everything again (:5851–5889). That is the 14-s freeze
    (F88 (4); :1438–1441). The reset has taken the machine down before (F207; F208 run 785).
  - A fault that does not stall is never learned (F208); only the kernel log shows it.
  - A PM4 operand in unmapped memory does not fault: the filter NOPs its packet (policy.cpp:542; :7433). A GPU wait on
    unmapped labels once took the machine down (F130).
- **The zero scan** (exp 0330, F394, F397, F400) found 3.4–3.7 GB of the 11.4 GB pinned in all-zero 2 MiB chunks
  after ~9 minutes. RenderGpuWcLarge and CommitIABufferAllocator hold 1.2–1.4 GB each of that, in three runs: the
  bench route RT off, free play RT on, and free play RT off. The scan gives totals per heap, not positions.
- **The forced windows already cover much of the two heaps.** This is read offline from exp 0330's `raw/{A,B,C}-forced.txt`
  (600-s runs) and the learned file of 10-24 in exp 0288's `raw/`:

  | heap | learned | hint only | unforced |
  |---|---|---|---|
  | RenderGpuWcLarge (2,758 MiB) | 1,798 | 514–526 | 434–446 |
  | CommitIABufferAllocator (2,736 MiB) | 1,392 | 0 | 1,344 |

  So a narrowing that keeps today's protections saves at most ~1.8 GB, three quarters of it in
  CommitIABufferAllocator. The real figure is what is both zero and unforced, which needs positions.
- **Zero is not the same as untouched.** The GPU may read zeros, write zeros (clears), or leave a fast-cleared target
  unwritten. TODO(verify) for this title. And 540 s is not forever: no session was scanned later.

**Setup (proposed).**
- **`patch0333.py`** applies to exp 0330's output 29664e3c (tree 5bccbb80; both md5s checked). Every switch is
  `BC5_DIAG_ENV` and off by default.
  - `BC5_DIRECT_ZEROSCAN_AT` takes a list of times.
  - `BC5_DIRECT_ZEROSCAN_MAP=<names>` journals one line per heap and scan, one character per chunk: zero `.` unforced,
    `l` learned, `h` hint only; data `#`, `L`, `H`. Each line counts the chunks that left the zero set since the last
    scan. That is ~2.7 k characters per scan, with no content.
  - `BC5_DIRECT_RELEASE_AT=<s>` releases the chunks that were zero and unforced in every scan of the session. The pass
    sits in `direct_sync_one` and is bounded like the merge (256 MiB per 250 ms, :1718–1721). Per BO it:
    - re-imports the kept parts and remaps them with the GPU drained (:1774);
    - frees the old BO, re-reads the chunk and punches it (`fallocate`; `F_SEAL_SHRINK` allows that per mm/shmem.c,
      TODO(verify) on 7.2.9). Unpinning alone frees nothing: the shmem pages stay (F353: Shmem equals pinned).
    - Runs under `BC5_DIRECT_RELEASE_MIN_MIB` (default 8) stay pinned, because the CS cost grows with the BO count
      (F124).
    - `BC5_DIRECT_RELEASE_PUNCH=0` tests the remap without the punch, which frees nothing.
  - Learned faults go to a private copy, `exp0333/direct-learned-pkg.txt`.
- **How a released chunk comes back:**
  - a later CPU write, through ADR 0006's `SEEK_DATA` path;
  - a new forced window (:1672);
  - a fault, journalled as "released hit", which takes the chunk and its neighbours back.

  PM4 operands are recorded by the filter callback, under the device mutex (direct.cpp:810), so the import follows
  the submit.
- **Its own risk:** a CPU write in the microseconds between the re-read and the punch is lost.
- **The build** is `run0333.sh build`, as run0330.sh: one unit, linked from the shared normal objects, nice 19,
  ~2 min, no GPU.

**Arms.**

| arm | where | switches | GPU risk |
|---|---|---|---|
| S1 | S6N chain, RT off, 1,200 s | mapped scans at 240, 480, 720, 960, 1,180 s | as in play |
| S2 | his free play, RT off, test shortcut | mapped scans every 240 s | as in play |
| R1 | S6N chain, 1,200 s | S1 + release at 480 s | freeze or machine-down |
| R2 | his free play, ≥ 30 min | S2 + release at 480 s | the same |

- **Gate S → R:** ≥ 500 MiB zero and unforced in both S1 and S2, and ≤ 64 MiB leaving the zero set after 480 s in S2.
- **Readings:**
  - MemAvailable (median, minimum) before and after the release; Shmem; GTT; the pinned line and its BO count;
  - the release line: chunks, MiB, runs, BOs, ms held;
  - "released hit", learned, TIMEOUT and reopen lines;
  - gfxhub faults and ring timeouts in the kernel stream. A fault in a released chunk fails the arm, even without a
    timeout;
  - devcoredumps, by path; flips/s per 10 s against S; PSI "full"; refaults.

**Needs the maintainer's yes:**
1. R1 and R2, one yes each: a missed GPU access is a 14-s freeze or a machine-down.
2. The punch and its race.
3. S2 and R2 on his own saves, and the changed shortcut.
4. Merging the private learned windows into the shared file.
5. RT on, which is untested here: it uses ~120 MiB more of CommitIABufferAllocator.
6. Box time: ~2 min for the build and ~45 min for S1 and R1.

**Result.** Pending.
