# 0220 — the APR readers' condition-variable wait: a back-to-back pair against the shared build

**Question.** Exp 0216 (F276) removed the APR read-ahead readers' idle polling with a condition-variable wait. Its one
smoke run had worse frames than exp 0214's S1N, but under far heavier memory and io pressure, so it showed no frame
regression either way. Under the maintainer's policy, integration needs a speed-up with no regression. Run back to
back on the same route, with the box in the same state, is exp 0216's binary as good as the shared build?

**Setup.**
- Arms, both through `play-pkg.sh` with `BC5_EMU`, no `KYTY_BC5_APR_READAHEAD` (4 readers per queue), the clock
  voice's journal on (`KYTY_BC5_APR_FILE_JOURNAL=7cd713df`):
  - A1, shared: `~/bc5-work/kytyplus-build/src/kyty_emulator` (md5 `9d43e945…`, exp 0214's build, 5-ms poll);
  - B1, test: `~/bc5-work/exp0216/kyty_emulator` (md5 `35fa8d52…`): the same objects with `patch_0216.diff`.
    The chain checks that the shared build is unchanged before it starts.
- Route: exp 0203's O2 (saves `exp0196/saves-before-152617`, `o2-continue.cmd`), 300 s each, A1 first, a 20-s pause,
  then B1.
- The launcher is not the one of S1N and S1. On the maintainer's yes, `play-pkg.sh` defaults since about
  2026-10-22 21:00 to `BC5_DIRECT_FLAT_APERTURE=1`, `BC5_DIRECT_AMM_PRT=1`, `BC5_DIRECT_SKIP_PGM=909974400`:
  reflections on, only the BVH compaction skipped (exps 0211, 0218). Both arms get them, so A1 and B1 compare with
  each other, but not like for like with S1N and S1. Each run's `raw/<tag>-start.txt` keeps the launcher's md5 and
  those lines.
- `run0220.sh` is exp 0216's `run0216.sh` with the binary as an argument: saves kept aside by `ab-restore.sh`, put
  back after each run and checked with `diff -rq`; only the emulator PID it started is ever stopped. Beside each run:
  - exp 0216's `cpu0216.sh` (the APR threads' schedstat every 10 s);
  - exp 0200's `sample0200.py` (the cinematic clock, faults, PSI);
  - `mem0220.sh`: the box's memory every 15 s (meminfo, swap, GTT and VRAM use, the six largest processes). The
    consumer behind S1's swap-in storm was not found.
  - The start of each run records `free -m`, PSI and the largest processes (`raw/<tag>-start.txt`).
- `chain0220.sh` holds one lock line for both arms and the journal reads (`ana0220.sh`: exp 0214's `ra0214.py` and
  exp 0216's `long0216.py` with O_DIRECT at 15 MB/s, exp 0200's `ana0200.py`). It stops on saves that differ or a new
  amdgpu line. Locally, after the pull: exp 0216's `cpu0216.py`, `cpuq0216.py` and `lat0216.py`.
- Afterwards, under a short lock of its own: exp 0214's `gu0214.py` counts the given-up waits by label (both journals,
  O_DIRECT, 15 MB/s).
- The kernel log is streamed to the laptop during the chain (`raw/kernel-stream.txt`).
- Box use: the top session's Go at 21:41. The chain ran 21:41:48–21:53:04, the given-up count 21:54:44–21:54:58.
  The play logs and samplers stay on the box (`~/bc5-work/exp0220/raw`).

**Result.**
1. **Both arms passed** (`raw/chain.out`, `raw/*-summary.txt`):
   - each ran the full 300 s, with the completion sequence increasing and no crash or kernel line;
   - the laptop stream has only IPv6 MLD lines;
   - the live saves came back identical after each (`diff -rq`).
   - A1: 16 reader threads (the title used priority queue 0 too), 485 read-ahead lines, 562 in-order copies.
   - B1: 12 reader threads, 443 read-ahead lines, 515 in-order copies.
   - Both used the same launcher (md5 `7952a900…`, the new defaults), and the shared build was unchanged
     (`9d43e945…`).
2. **The box was in the same state for both** (`raw/*-mem.txt`, `raw/*-ana5.txt`, `raw/*-start.txt`):
   - Before each: about 13.7 GB available and 0.66 GB of swap in use.
   - During each run the GPU's GTT rose to 12.0 GB and Shmem to 11.7 GB, so MemAvailable fell to 540–690 MiB, and
     swap use grew alike. The game's GTT is the box's big memory consumer on this route with the new defaults.
   - Means over the run, A1 against B1:
     - major faults 70 against 48 a second;
     - compaction stalls 0.4 against 0.1 a second;
     - PSI memory full 1.2 against 0.65 %, io full 15.5 against 13.5 %.
   - Both were far calmer than exp 0216's S1 (memory full 15–22 % for minutes).
3. **Frames** (`raw/frames.txt`, `raw/*-long-frames.txt`):

   | | A1 shared | B1 exp 0216 |
   | --- | --- | --- |
   | flips/s (all / t ≥ 100 s) | 38.6 / 41.6 | 37.9 / 41.0 |
   | mean ms between flips | 25.9 | 26.4 |
   | frames > 100 ms / > 250 ms / > 1 s | 41 / 4 / 0 | 35 / 4 / 0 |
   | longest frame | 550 ms | 706 ms |
   | TIMEOUT / fault / reopen | 0 / 0 / 0 | 0 / 0 / 0 |
   | given-up waits | 8 | 15 |

4. **Reader and worker CPU** (`raw/cpu-a-b.txt`, `raw/cpu-per-queue.txt`):

   | | A1 shared | B1 exp 0216 |
   | --- | --- | --- |
   | quiet 10-s intervals (workers < 10 ms) | 13 | 13 |
   | readers' CPU per 10 s in them: min / median / max | 158 / 208 / 228 ms | 3.6 / 9.0 / 11.8 ms |
   | as a share of one core (median) | 2.08 % | 0.09 % |
   | readers' wake-ups a second in them (median) | 3,310 | 98 |
   | per queue (4 readers), quiet | 51–61 ms per 10 s | 0.7–6.7 ms per 10 s |
   | readers in all | 14.5 s in 287 s (5.03 %) | 7.9 s in 287 s (2.76 %) |
   | workers in all | 3.7 s (1.28 %) | 2.6 s (0.90 %) |

   - Per queue the readers' totals fell too: q1 2.12 → 0.65 s, q3 6.16 → 3.80 s, q5 4.84 → 3.47 s. A1's q0 readers
     add 1.32 s that B1 did not have.
5. **The clock voice's APR queue (priority 1)** (`raw/apr-latency.txt`):

   | | A1 shared | B1 exp 0216 |
   | --- | --- | --- |
   | submissions finished | 599 | 536 |
   | submit → finish, median | 57 ms | 20 ms |
   | 95th percentile | 1,413 ms | 499 ms |
   | max | 3,503 ms | 643 ms |

   - The cinematic clock lost 0.5 s in t 100–250 s in A1 and 0.2 s in B1.
   - Exp 0216's S1 against S1N showed the same direction: median 25 against 52 ms, p95 608 against 1,295 ms.
   - A guess, not shown: 12–16 readers polling every 5 ms take `g_apr_queue_mutex` about 3,000 times a second, each
     time to scan up to 64 buffers. Under that lock contention the worker's turns and the submits wait.
6. **Given-up waits by label** (`raw/giveups.txt`): A1 8 (0x12004b5438 4, 0x12004b4838 2, 0x12004b3c38 2), B1 15
   (0x12004b5438 10, 0x12004b3c38 3, 0x12004b4838 2).
   - The rise is again on 0x12004b5438, the label F273 watches. With the read-ahead on, it rose at the lake (76
     against 45).
   - With 14 on that label in all, 10 against 4 has p ≈ 0.09 (one-sided). F262's machine-down label 0x12004b3c38 is
     3 against 2.

**Verdict.**
- **Exp 0216's condition-variable wait is a speed-up with no regression in this pair.**
  - The readers' idle cost fell from 208 to 9 ms per 10 s (2.08 % → 0.09 % of one core), and their wake-ups from
    3,310 to 98 a second.
  - The readers' total CPU fell from 14.5 to 7.9 s (12 against 16 readers), and the workers' from 3.7 to 2.6 s.
  - The clock voice's queue was faster: median 57 → 20 ms, p95 1.4 → 0.5 s, max 3.5 → 0.6 s.
  - Frames were the same: 38.6 against 37.9 flips a second, 4 and 4 frames over 250 ms, none over 1 s, no timeout,
    fault or crash.
- The box was in the same state for both arms, unlike exp 0216's S1. Its worse frames came from the box, as that
  experiment suspected.
- To watch, as in F273: given-up waits on 0x12004b5438 (4 → 10 here, weak). They again rise with a faster read path.
- Under the maintainer's rule this qualifies for integration: `patch_0216.diff` into `~/src/KytyPlus` and both shared
  builds. That is the top session's step. One pair on one route.
- Both arms used the new launcher defaults (reflections on, the compaction skipped), so this pair is not like for like
  with S1N or S1.
