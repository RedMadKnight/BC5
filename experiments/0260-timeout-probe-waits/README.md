# 0260 — a timeout probe that survives a machine-down and shows what a stuck buffer waits on

**Question.** Exp 0259 could not tell what the compute buffer did when S6N's machine went down (F316): a stuck
WAIT_REG_MEM, and on what, or a dispatch that never ended. Can the timeout probe (exp 0160,
`BC5_DIRECT_TIMEOUT_PROBE=1`) be made to record that, so that the next machine-down of this class (F250, F256, F260,
F262, F316) shows the stuck packet in both buffers?

**Known before this experiment.**
- **Correction of 0259 / F316: the probe was on in S6N.**
  - The second title's launcher exports `BC5_DIRECT_TIMEOUT_PROBE=1` unless `BC5_NO_TIMEOUT_PROBE=1` or
    `BC5_LEAN=1` (`play-pkg.sh` line 108, md5 3973c8ca: the file S6N ran, unchanged since 00:22).
  - S6N's runner set neither ("extra env ''", exp 0254 `S6N-start.txt`), and S6N ran the normal build, where
    `BC5_DIAG_ENV` is `getenv` (`src/common/logging/log.h:27-30`).
  - What 0259 found missing was lost, not never written:
    - The dump goes through `fopen`/`fwrite`/`fclose` with no sync, so it sat in the page cache when the box died.
    - The probe's journal lines are written after the TIMEOUT line's fsync, into the min journal's 1-MiB stdio
      buffer, which is flushed only on the next failure or after 0.5 s. They never reached the file.
    - Where the box survived the timeout, the dumps are on disk: the 22:59 play's `ib-timeout-00767668-dcb-66622.bin`
      and `ib-timeout-00767674-acb-865.bin`, and R11B's acb-875.
- The probe journals draws and dispatches: the register state before each, including COMPUTE_PGM, the packet's
  dwords and the V# memory at a dispatch. It does not journal waits or label writes.
- The completion thread clears the pending-write registry (`forget_label_writes(…, timed_out)`) before the probe
  runs, so the probe cannot report which writer the ring order expected.

**Setup.**
- `patch0260.py` makes `patch_0260.diff` (90 lines, 5 edits) against the shared tree's `bc5LleAgc.cpp` after the
  CS-prefix integration (md5 67859271). It touches only `timeout_probe()`; without the switch nothing changes.
  - The dump is fflush'ed and fsync'ed before it is closed.
  - For each WAIT_REG_MEM (0x3C) and WAIT_REG_MEM64 (0x93) in the timed-out buffer, one line:
    - its offset, the label (memory space) or register, function, reference, mask and engine (me / pfp);
    - the label's value now and whether that meets the wait;
    - `ran` (kept for the GPU) or `DROPPED` (served on the CPU).

    Fields as this file's `wait_satisfied()` reads them, and MEM_SPACE bits 5:4 and PFP bit 8 from Mesa
    `src/amd/common/sid.h` @ 0866ae7, lines 90–95.
  - For each label write (RELEASE_MEM 0x49, EVENT_WRITE_EOP 0x47, WRITE_DATA 0x37 to memory): the address, data
    select, value and the address's value now, as `register_label_writes()` reads them.
  - For each dispatch: its program, or "not set in this buffer".
  - At most 200 lines of each kind, then a count line ("N waits (K kept for the GPU), M label writes, D dispatches").
  - Then the min journal is flushed and fsync'ed, so the lines reach the disk and a stream of the journal.
- **Private binary** (the box supervisor's instruction; the shared builds and the switch's default are untouched):
  - `run0260.sh build` patches the tree's file on the box into `~/bc5-work/exp0260/src/bc5LleAgc.probe.cpp`
    (md5 daca24cc, the same diff as here).
  - It compiles that one unit with the shared normal build's flags, from a fresh `ninja -t compdb -x`; `-x` because
    the compdb otherwise names response files that ninja has deleted.
  - It links `~/bc5-work/exp0260/kyty_emulator` from the shared build's other objects (`build0260.py`, as exp
    0226's), nice 19.
- **The catch run**: scripted, on the box supervisor's GO, with the maintainer reachable to power-cycle after a
  machine-down.
  - `catch0260.sh [runs] [secs]` is exp 0254's `run0254b.sh` (the APR session's) cut down to its `pkgn` title: the
    second title, `play-pkg.sh` with its defaults, and S6N's route (exp 0203's `o2-continue.cmd` from exp 0196's
    `saves-before-152617`, put in and taken back by `ab-restore.sh`).
  - It differs in four ways:
    - `BC5_EMU` is the private binary, checked by the md5 of `/proc/<pid>/exe`, with `BC5_DIRECT_TIMEOUT_PROBE=1` set
      explicitly;
    - the route is repeated, by default 4 × 300 s, each run with its own save restore;
    - a run is stopped at the first new kernel amdgpu line (checked every 5 s), and the chain stops after any run that
      is not a pass;
    - the live saves' checksum (exp 0253's method) must be 1a39860996fdac5c before and after.
  - The held tail, the CS prefix, the tiler pool and the probe all stay on, so that it reproduces S6N.
  - After a machine-down, the live saves are in the run's `exp0196/saves-before-*` (named in `<tag>-restore.txt`)
    and are put back by hand.
  - `stream0260.sh`, started on the laptop first, streams into `raw/` the kernel log and, from each new GPU journal of
    the chain, the probe, TIMEOUT, give-up, hold-summary, prefix and fault lines.
    - It follows journals only while the chain's own lock line is there, so other sessions' runs are never read.
    - Both streams only read, and they end by themselves.
  - `play0260.sh` (the maintainer's own play with the same binary) was the first plan and is not used.

**Result.**
- **Build**, 2026-10-24 14:09–14:10, under my own lock line (removed by the script's trap), no emulator:
  - rc 0, with only the 4 warnings the file already had, none in the probe (`raw/build.out`);
  - `~/bc5-work/exp0260/kyty_emulator`, 166,418,408 bytes, md5 9c55e29e; the three new journal formats are in it;
  - inputs (`raw/build-inputs.txt`): the tree's file of 00:22:13 (67859271), the shared normal binary of 00:22:41
    (md5 02ed5340, S6N's), its objects of 00:22:37.
  - The first attempt (14:09:13) failed on the compdb's response files and changed nothing.
- **Not tested on the GPU.** The new code runs only after a fence timeout. Its reads are guarded by the mapping check
  `rd()` uses.
- **The catch run**, 2026-10-24 14:49–15:10, `catch0260.sh 4 300` (`raw/catch.out`).
  - Approved by the maintainer in the tcp session ("Yes, I approve: start the exp 0260 catch run … I'm reachable for
    a power-cycle"). The box supervisor's GO alone had been refused by the permission check at 14:33, and nothing ran
    then.
  - Boot 9f3e0da8, launcher md5 3973c8ca. The emulator's exe was the 0260 binary each time (md5 9c55e29e), with the
    switches as in S6N: `BC5_DIRECT_RING_ORDER_WAITS=1`, `BC5_DIRECT_CS_PREFIX=1`, `BC5_DIRECT_TIMEOUT_PROBE=1`,
    `BC5_DIRECT_CROSS_RING_WAITS=all`, `BC5_DIRECT_CHAIN=2` and `BC5_DIRECT_COMPUTE_RING=0`, with the held tail on by
    default (`raw/K*-start.txt`).
  - **All four runs passed** (`raw/K*-summary.txt`, `K*-verdict.txt`, `K*-journal.txt`):

    | run | TIMEOUT | kernel lines | crash | holds (writer on a ring / satisfied / given up) | longest hold | prefixed buffers |
    | --- | --- | --- | --- | --- | --- | --- |
    | K1 | 0 | 0 | 0 | 20,857 (19,044 / 1,812 / 1) | 382.5 ms | 32 |
    | K2 | 0 | 0 | 0 | 19,693 (18,032 / 1,658 / 2) | 100.3 ms | 36 |
    | K3 | 0 | 0 | 0 | 19,040 (17,437 / 1,602 / 0) | 86.2 ms | 31 |
    | K4 | 0 | 0 | 0 | 19,214 (17,512 / 1,700 / 1) | 100.0 ms | 34 |

  - In each run: 0 "cpu-wait … GIVEN UP", 0 "two rings … NOT served", 0 alias lines.
  - The saves came back identical after each run, and the live checksum was 1a39860996fdac5c before and after
    (`raw/catch-saves.txt`).
  - The kernel stream shows only the network's IPv6 lines (`raw/kernel-stream.txt`).
  - The journal stream followed all four journals (`raw/journal-stream.txt`). It lags the box's files by the min
    journal's 1-MiB buffer, which is why its last hold summaries show fewer holds than the files.
  - The play logs stay on the box.
- **The probe's new lines were not exercised**: no fence timed out.

**Verdict.**
- **Built:** a private binary whose timeout probe survives a machine-down, by syncing its dump and its journal lines,
  and shows a stuck buffer's waits (label, value now, met or not, kept or dropped), label writes and dispatches. On
  the GPU it is still untested.
- **The hang did not recur** in 4 × 300 s of S6N's route with S6N's settings (S6N hung after ~140 s). This class is
  rare: once in 137 s in S6N, after 1,155 s in F260, and not in these 1,200 s. A single catch run is a poor way to
  wait for it.
- **Next (the box supervisor's and the maintainer's call):**
  - Put `patch0260.py`'s probe into the shared builds. It acts only after a fence timeout, and `play-pkg.sh` already
    sets the switch, so every play becomes a catch run.
  - The stuck pair's structure (exp 0255, F322) gives a concrete thing for the probe's lines to confirm or refute.
