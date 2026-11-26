# 0222 — the APR readers' condition-variable wait in the shared builds

**Question.** Exps 0216 and 0220 (F276, F280) showed that `patch_0216.diff` is a speed-up with no regression. The
readers' idle CPU fell from 2.08 % to 0.09 % of one core, and the clock voice's APR queue got faster, with frames
unchanged. Under the maintainer's rule it goes into use. Do both shared builds work with it, run through their own
launcher?

**Setup.**
- The patch: exp 0216's `patch_0216.diff`, two waits in `libAmpr.cpp`.
  - The read-ahead reader's `wait_for(5 ms)` becomes `wait_for(1 s)`.
  - The worker's `wait_for(200 µs)`, while a reader holds its front buffer, becomes `wait_for(50 ms)`.
- Read-only checks before (`~/bc5-work/exp0220/check`, `raw/tree-vs-tree-plus-0216.diff` there):
  - f266548 plus patch 0001's libAmpr section gives blob `323e90b`, byte-identical to the tree (md5 `387bc07c…`).
  - That plus `patch_0216.diff` is exactly exp 0216's tested source (`eaef1da1…`), two hunks from the tree.
  - `git apply --check` passes.
  - No other file under `src/` is newer than the shared binaries: normal `9d43e945…`, lean `7eac6f35…`, the builds
    of exp 0214.
- `rebuild0222.sh` is exp 0214's `rebuild0214.sh` with this patch.
  - It stops if any source besides `libAmpr.cpp` is newer than the shared binaries.
  - It checks that the patched file equals exp 0216's tested source, then rebuilds both builds.
  - It keeps `~/bc5-work/exp0222/kyty_emulator{,-lean}.before-0216` and `src/libAmpr.before-0216.cpp`.
  - A failure puts all three back. The source gets a new mtime, so ninja recompiles it next time and does not relink
    the patched object.
- `run0222.sh` is exp 0214's `run0214.sh`, with exp 0220's PID-only stop, memory sampler and launcher record. It runs
  through `play-pkg.sh` with no `BC5_EMU`, on the launcher's current defaults (reflections on).
- `chain0222.sh` holds one lock line for the rebuild, then two smoke runs on O2's route:
  - S2N, the normal build, 300 s, with the clock voice's journal;
  - S2L, the lean build, 150 s.
  - Any failure rolls everything back. Afterwards S2N's journal is read with `ra0214.py` and `gu0214.py`.
- Box use: only after the user's approval in this session and the top session's Go. A first attempt to apply the
  patch on the top session's word alone was refused by this session's permission settings; the user approved at
  about 22:03, and the Go came at 22:10. The chain ran 22:10:58–22:19:41 under one lock line. The kernel log was
  streamed to the laptop (`raw/kernel-stream.txt`).

**Result.**
1. **The tree and the rebuild** (`raw/rebuild.out`, `raw/build-*.txt`, `raw/git-diff-f266548-after.txt`):
   - `libAmpr.cpp` went from md5 `387bc07c…` to `eaef1da1…`, which equals exp 0216's tested source. LF only.
   - Each build compiled only `libAmpr.cpp.o` and relinked: 15 s for the normal build, 12 s for the lean one, rc 0.
     The three warnings predate the change.
   - md5 of the normal build `9d43e945…` → `7a37a560…`, of the lean build `7eac6f35…` → `a3456df9…`; synced.
   - The old binaries and source are kept as `~/bc5-work/exp0222/kyty_emulator{,-lean}.before-0216` and
     `src/libAmpr.before-0216.cpp`.
2. **Smoke run S2N: the normal build through `play-pkg.sh`, no `BC5_EMU`, no `KYTY_BC5_APR_READAHEAD`, O2's route,
   300 s (22:11:28–22:16:42). Passed.**
   - Its run: 16 reader threads, 445 read-ahead lines, 506 in-order copies, the completion sequence never
     decreased.
   - No crash line, and no kernel line beyond the IPv6 MLD lines. The live saves came back identical.
   - The launcher had the new defaults (`play-pkg.sh` md5 `7952a900…`: reflections on, the compaction skipped), as
     in exp 0220.
   - Frames (`raw/S2N-frames.txt`):
     - 37.9 flips/s (39.9 for t ≥ 100 s), 26.4 ms mean between flips;
     - frames over 100 ms 34, over 250 ms 8, over 1 s 1;
     - the one over 1 s: 1.16 s at t 173.3 s, the game thread outside the host for 1.12 s, GPU busy 13.5 ms;
     - TIMEOUT, fault and reopen lines 0.
   - Given-up waits 11 (`raw/S2N-giveups.txt`): 0x12004b5438 5, 0x12004b3c38 4, 0x12004b4838 2.
   - The box's state matched exp 0220's (`raw/S2N-mem.txt`): PSI memory full 0.61 % and io full 15.2 % on average,
     MemAvailable down to 438 MiB.
   - Readers in all 6.6 s and workers 2.2 s in 287 s; VmRSS max 6,519 MiB.
   - With the queues quiet (14 intervals), the readers used a median of 11 ms per 10 s and woke 147 times a second
     (`raw/cpu.txt`). With the 5-ms poll it was 208 ms (exp 0220's A1), so the shared build has the change.
3. **Smoke run S2L: the lean build (`BC5_LEAN=1`), the same route, 150 s (22:16:45–22:19:27). Passed.**
   - 12 reader threads, no crash or kernel line, saves identical.
   - The quiet intervals' readers used a median of 7 ms per 10 s. The lean build has no journal, so there are no
     frame data.
4. **The clock voice's queue was not faster in S2N** (`raw/apr-latency.txt`, `raw/slow-reads.txt`):
   - Median 61 ms, p95 1,113 ms, max 2,351 ms. Its slowest reads were submitted at t 157.6–158.5 s; the q3 readers
     were busy then.
   - Reads that took over 1 s from submit to finish, per run:

     | wait | run | reads | over 0.5 s | over 1 s |
     | --- | --- | --- | --- | --- |
     | 5-ms poll | S1N (exp 0214) | 501 | 90 | 55 |
     | 5-ms poll | A1 (exp 0220) | 599 | 117 | 51 |
     | condition variable | S1 (exp 0216) | 570 | 42 | 13 |
     | condition variable | B1 (exp 0220) | 536 | 26 | 0 |
     | condition variable | S2N (this) | 540 | 96 | 35 |

   - So the queue's gain varies from run to run and is not shown: F280's "faster queue" rested on one pair.

**Verdict.**
- **Exp 0216's condition-variable wait is in `~/src/KytyPlus` and both shared builds since 2026-10-22 22:11.** Both
  smoke runs passed.
- What it brings is the CPU: with the queues quiet the readers use about 7–11 ms per 10 s instead of about 160–208,
  waking about 100–150 times a second instead of 2,400–3,300.
- No regression in frames, timeouts, faults or crashes. S2N had 37.9 flips a second, against 38.6 and 37.9 in exp
  0220's pair.
- The clock voice's queue is not shown to be faster: S2N had 35 reads over 1 s, between the polling runs (51, 55) and
  the other two condition-variable runs (13, 0).
- Rollback: copy the `*.before-0216` files back (both binaries and `libAmpr.cpp`, the source with a new mtime).
- Still to watch, as in F273: the given-up waits on 0x12004b5438 (5 in S2N).
