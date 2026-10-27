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

**Phase S, built and run (2026-10-26, in the maintainer's autonomous window).** His words: "samodzielnie działaj i
podejmuj decyzję przez ok. 1,5h". The supervisor took phase S only: diagnostic, nothing released, RT off, private saves.
Phase R and every other item in the list above still need his yes.
- **`patch0333.py`** (9 edits on exp 0330's output 29664e3c; output f8732646) implements the two diagnostic switches of
  the design. The release switches are not in it.
  - `BC5_DIRECT_ZEROSCAN_AT` takes a list. Scans run one at a time; times that pass while one runs go to the next.
  - `BC5_DIRECT_ZEROSCAN_MAP` writes the map and counts after each scan.
  - The learned class comes from the chunks that `map_window` forces. Only `learned_apply` calls it, so `S.forced`
    minus those chunks is the hint class.
  - Checked offline:
    - the new code compiles in a stand-in harness with g++ and clang (`-std=c++20 -Wall -Wextra -Wformat=2 -Wshadow
      -Werror`);
    - the harness ran three scans over a synthetic 32 MiB file (12 chunks, two views, two BOs);
    - the classes, the counts, the left-zero numbers and the always-zero runs were all as worked out by hand.
- **`run0333.sh build`** built `~/bc5-work/exp0333/kyty_emulator`, **9a0939b4**, in 28 s, with one unit compiled and
  linked (`build0333.py`).
  - It links the shared normal build's objects (4a146894) and exp 0332's `runtimeLinker.cpp.o`, so a crash in a run
    also dumps the frame.
  - Its 4 warnings are the ones in exp 0330's build, all in older code.
- **`s6n0333.sh`** is arm S1, one run derived from exp 0330's `s6n0330.sh`:
  - the S6N route (`o2-continue.cmd`) from exp 0196's route saves, in a private working directory with its own
    `_SaveData`;
  - RT off through a private input configuration;
  - 1,200 s, with the breakdown at 230 s and the mapped scans at 240, 480, 720, 960 and 1,180 s;
  - learned faults go to a private copy of the shared learned file (07fa5425, 108 windows);
  - the live saves are compared only.

  The launcher is `play-pkg.sh` (b10eac6d) with four lines changed (log, working directory, save directory, learned
  file) and one hook added (the input configuration). Unlike exp 0330's run, the save directory is a new private one:
  exp 0330's working directory linked it to the shared, empty `~/bc5-work/_SaveData-pkg-play`. That collision stopped
  the first start at 16:23, at setup and before any emulator (BOX-QUEUE 177).
- **`stream0333.sh`** keeps the kernel log and the journal's key lines in this session (`raw/kernel-stream.txt`,
  `raw/journal-stream.txt`).

**Result (arm S1, 2026-10-26 16:24:41–16:45:01; `raw/`).**
- **The run passed.**
  - 1,200 s at 38.5 flips/s (median 39.5 per 10 s), with no crash line, kernel GPU line, TIMEOUT or devcoredump.
  - The kernel stream (`raw/kernel-stream.txt`) has no amdgpu line.
  - 11,263 RT-off drop lines.
  - The private learned file is unchanged: no new fault.
  - The live saves read 3496e40ff61ca57e before and after.
  - 11,220 MiB pinned in 91 BOs.
  - MemAvailable after 3 minutes had a median of 761 MiB (min 738), with GTT at most 11,906 MiB. This is the bench,
    standing after Continue; his play holds ~0.4 GB.
- **The zero map** (`raw/S1-zeromap.txt`, all five scans; `table0333.py`):

  | heap | zero | unforced | learned | hint only | data | zero and unforced in all 5 scans |
  |---|---|---|---|---|---|---|
  | RenderGpuWcLarge (1,379 chunks) | 1,432–1,442 MiB | 302 | 932–934 | 196–206 | 1,316–1,326 | 302 MiB in 5 runs |
  | CommitIABufferAllocator (1,368 chunks) | 1,382 | 436 | 946 | 0 | 1,354 | 436 MiB in 6 runs |

  - **Stable from 240 s to 1,180 s.** CommitIABufferAllocator did not change one chunk.
  - In RenderGpuWcLarge, 3–8 chunks a scan moved between zero and data. All of them were in the learned or hint
    windows (classes `L` ↔ `l` and `H` ↔ `h`). No unforced chunk changed.
  - **738 MiB is zero and unforced in every scan, nearly all in a few long runs:**
    - RenderGpuWcLarge: 256 MiB at +2,450 MiB, near the heap's end, plus 24, 12, 8 and 2 MiB;
    - CommitIABufferAllocator: 224 MiB at +2,240 MiB, 116 MiB at +748, then 32, 32, 28 and 4 MiB.
  - **The learned windows hold most of the zero memory: 1,878 MiB of the two heaps' 2,814 MiB of zero.** Examples
    are a 406 MiB zero run inside CommitIABufferAllocator's learned windows, and 96, 70 and 272 MiB runs.
  - On this route the hint windows touch only RenderGpuWcLarge.

**Verdict (phase S, arm S1).**
- **On the bench route a narrowing that keeps today's protections can release at most ~0.74 GB,** not the ~1.8 GB
  ceiling read offline. That ceiling assumed no learned window held zeros, but 1,878 of the two heaps' 3,190 MiB in learned
  windows (59%) is zero.
- **The first half of the gate S → R holds:** ≥ 500 MiB zero and unforced in S1 (738 MiB), and stable in S1.
- **The second half needs S2,** in his free play, which moves through the world. Is the 738 MiB still zero there, and
  does less than 64 MiB leave the zero set after 480 s? S2 needs his yes, because it changes the test shortcut and
  plays on his saves.
- **A larger lever is now visible:** the learned windows. Each is 96 MiB around one fault (`learned_add`), and on this
  route 59% of their chunks in these heaps stay zero. A narrower learned window, for example 32 MiB
  around the fault, is a separate question. It risks the 14-s freeze each time it misses, so it needs its own
  experiment and his yes.
- Nothing was released, and nothing shared changed: the binary, launcher, saves and learned file were all private.
