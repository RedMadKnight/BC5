# 0216 — APR read-ahead readers: a condition-variable wait in place of the 5-ms poll

**Question.** Exp 0214's smoke run S1N found that the 12 APR read-ahead readers (4 each for queues q1, q3 and q5)
used 149–171 ms of CPU per 10 s with the queues idle: about 1.6 % of one core, some 2,400 wake-ups a second from
their 5-ms poll. Does a plain condition-variable wait remove that cost without a regression?

**Setup.**
- The code (`~/src/KytyPlus/src/libs/libAmpr.cpp` = exp 0214's tree, md5 `387bc07c…`):
  - `AprReaderThread` picks a buffer from the first 64 of its queue when it has `ra_state == 0`, `next == 0`, file
    reads, and its bytes fit under the 32-MiB cap in `g_apr_ra_bytes`. With none it did
    `g_apr_queue_cv.wait_for(lock, 5 ms)`.
  - What can make a buffer pickable, all under `g_apr_queue_mutex`:
    - a submit in `ExecuteAprCommandBuffer` pushes a buffer: `notify_all` follows;
    - the worker's `pop_front` frees the read-ahead budget (`g_apr_ra_bytes -=` just before) and moves the 64-buffer
      window: `notify_all` follows;
    - `ra_state` only moves away from 0 (0 → 1 by a reader, 0 → 4 by the worker, 1 → 2 by a reader); `next` only
      grows; the cap is fixed at start.
  - So no plain wait misses a pickable buffer. One exception: the wait thread's pump (`StartAprWaitThread`,
    `PumpParkedAprBuffersLocked`) pops without a notify. In async mode it starts only when an AMM-only submission
    stops at a wait. The reader keeps a 1-s limit as a safety net for that path.
  - The worker waited `wait_for(200 µs)` while its front had `ra_state == 1`. Only the reader moves it on, to 2, and
    it then calls `notify_all` under the lock, so a plain `wait` would be enough. On the top session's review it
    keeps a 50-ms limit: a missed notify there would stop the title's I/O, and the limit costs nothing.
  - A reader's missed wake-up could not hang the title: the worker runs every buffer itself (`ra_state` 0 → 4) when
    no reader took it.
  - The worker's `wait_for(500 µs)` while a guest-memory wait is unmet stays a poll: guest writes are not notified
    (exp 0156).
- `patch_0216.diff`: those two waits, against exp 0214's tree. `git apply --check` passes in `~/src/KytyPlus` (check
  only).
- Test binary: `build0216.py` (exp 0203's `build0203.py` with another directory) compiles `src/libAmpr.cv-wait.cpp`
  with the shared build's flags (exp 0203's `compdb.json` of 10:43, newer than `build.ninja` of 2026-10-20) and links
  it with the shared normal build's other objects into `~/bc5-work/exp0216/kyty_emulator`. The shared tree, binaries
  and objects are not written.
- `chain0216.sh` holds one lock line for the build and the smoke run S1: `run0216.sh`, exp 0214's `run0214.sh` with
  `BC5_EMU` set to the test binary, O2's route for 300 s, no `KYTY_BC5_APR_READAHEAD` (4 readers per queue), the
  clock voice's journal on (`KYTY_BC5_APR_FILE_JOURNAL=7cd713df`), live saves kept aside and put back by
  `ab-restore.sh`, checked with `diff -rq`.
- `run0216.sh` stops only the emulator PID it started, where `run0214.sh` used `pkill -x kyty_emulator`, which would
  also hit another session's emulator.
- `cpu0216.sh` is exp 0214's sampler with the whole schedstat line, so it also counts each thread's wake-ups (times
  run on a CPU). `cpu0216.py` gives the CPU per 10 s of the readers and workers. "Quiet" intervals are those where
  the workers ran under 10 ms, exp 0214's definition. `cpuq0216.py` splits it by queue.
- After the run, all read-only (`ana0216.sh`, nice 19, under a short lock of its own):
  - the GPU journal with O_DIRECT at 15 MB/s: exp 0214's `ra0214.py` for frames, and `long0216.py` for the frames
    over 1 s;
  - exp 0200's `ana0200.py` on the sampler (5-s windows: the cinematic clock, major faults, compaction stalls, PSI)
    for S1 and for exp 0214's S1N;
  - `lat0216.py`: submit → finish time per queue from the clock voice's APR journal, for S1 and S1N.
- The kernel log was streamed to the laptop during the run (`raw/S1-kernel-stream.txt`).
- Box use, in the top session's queue order: GRANTED at 20:22, Go at 20:32. The chain ran 20:33:30–20:38:58, the
  journal read 20:44:56–20:45:08.

**Result.**
1. **Build (`raw/chain.out`, `raw/build.log`).**
   - One unit compiled and linked in 14 s, rc 0. The three warnings predate the change: a deprecation in
     `stringUtils.h` and two `-Wformat-extra-args` in the AMM-trace lines.
   - Test binary md5 `35fa8d52…`; source md5 `eaef1da1…` = `src/libAmpr.cv-wait.cpp`. The shared binary was
     unchanged (md5 `9d43e945…`, as after exp 0214).
2. **Smoke run S1: the test binary, O2's route, 300 s (20:33:45–20:38:58). Passed by exp 0214's criteria**
   (`raw/S1-summary.txt`):
   - it ran the full 300 s, with 16 reader threads: the title used priority queue 0 too, as in exp 0214's S1L;
   - 412 read-ahead lines and 486 in-order copies in the clock voice's journal;
   - the completion sequence (0x90adf7fe0) never decreased;
   - no crash line and no new kernel line (the laptop stream has only IPv6 MLD lines);
   - the live saves were back and identical (`diff -rq`).
3. **Reader CPU, before (exp 0214's S1N, 5-ms poll) and after (S1)** (`raw/cpu-before-after.txt`,
   `raw/cpu-per-queue.txt`):

   | | S1N (before) | S1 (after) |
   | --- | --- | --- |
   | quiet 10-s intervals (workers < 10 ms) | 13 | 7 |
   | readers' CPU per 10 s in them: min / median / max | 149 / 160 / 171 ms | 2.4 / 13.4 / 50 ms |
   | the same, as a share of one core (median) | 1.60 % | 0.13 % |
   | readers' wake-ups a second in them | ~2,400 (12 × 200, the poll) | 20–400, median 154 |
   | per queue (4 readers), idle | 50–60 ms per 10 s | 2–10 ms per 10 s |
   | readers in all | 12.4 s in 288 s (4.32 %) | 13.4 s in 285 s (4.70 %) |
   | workers in all | 3.6 s (1.24 %) | 2.9 s (1.03 %) |

   - The fully idle interval of S1 (t 20 s) cost the 12 readers 2.4 ms and 200 wake-ups in 10 s: the 1-s safety
     limit plus a few notifies. The other quiet intervals keep a trickle of submits (workers 4–10 ms), and each submit
     wakes every reader through `notify_all`.
   - The readers' total rose by 1.0 s. It is all in the busy stretch t 157–233 s, mostly q3's readers: 7.9 s in all
     against 5.8 s, up to 2.5 s in one 10-s interval (t 191). That stretch lay in a swap-in storm (item 5), where
     the file reads cost more. Each wake-up costs the same as before, and there are fewer, so the change cannot
     add reader work. Per wake-up the busy intervals cost 30–180 µs, which is read work, not scanning.
4. **Frames, against S1N** (`raw/S1-frames.txt`, `raw/S1-long-frames.txt`; S1N from exp 0214):

   | | S1N | S1 |
   | --- | --- | --- |
   | flips/s (all / t ≥ 100 s) | 37.1 / 39.4 | 28.7 / 26.8 |
   | mean ms between flips | 27.0 | 34.8 |
   | frames > 100 ms / > 250 ms / > 1 s | 43 / 15 / 4 | 82 / 20 / 3 |
   | longest frame | 1,433 ms | 3,143 ms |
   | TIMEOUT / fault / reopen | 0 / 0 / 0 | 0 / 0 / 0 |
   | given-up waits | 13 | 7 |

   - S1's three frames over 1 s:
     - a GPU stretch at t 55.4 s, 3,138 ms GPU busy (the kind F266 finds without the read-ahead);
     - two with the game thread outside the host, 1.83 s at t 119.6 s and 2.92 s at t 173.2 s.
5. **The box's state differed from S1N's** (`raw/S1-ana5.txt`, `raw/S1N-ana5.txt`):
   - The loading screen (about 14 fps) lasted from t 90 to 160 s, about 70 s with PSI io full at 40–52 %. In S1N it
     lasted about 25 s (t 90–115 s). This alone takes S1's flips down.
   - From t 160 s on: 1,000–29,000 major faults a second (S1N: under 1,000), 30–120 compaction stalls a second
     (S1N: 0–10), PSI memory full 15–22 % (S1N: under 6 %).
   - The emulator's RSS at the end was 441 MiB (anon 60 MiB) against 1,798 MiB; most of it was swapped out. After the
     cutscene S1 ran 37–39 fps against S1N's 43–45, under that pressure.
   - At 20:45, after the run, nothing large held memory on the box (12 GB free, 1.4 GB in swap). The consumer during
     S1 was not found.
6. **The clock voice's APR queue (priority 1) was faster in S1** (`raw/apr-latency.txt`, `lat0216.py`):

   | | S1N | S1 |
   | --- | --- | --- |
   | submissions finished | 501 | 570 |
   | submit → finish, median | 52 ms | 25 ms |
   | 95th percentile | 1,295 ms | 608 ms |
   | max | 1,634 ms | 2,347 ms |

   - S1's five longest (1.7–2.3 s) were submitted at journal t 174.4–175.0 s, inside the swap-in storm (11,308 major
     faults a second at t 175 s). The 2.92-s outside-host frame falls there too.
7. **The cinematic clock** (`raw/clock-100-250.txt`, t 100–250 s): S1 lost 4.8 s, 3.3 s of it in the 5-s window at
   t 170 s (0.34×), the same storm. S1N lost 1.4 s (exp 0214 said 1.3), O2 about 4 s, O3 7.9 s (exp 0203).

**Verdict.**
- **The readers' idle polling cost is gone.** In quiet intervals the readers (12, or 16 from t 133 s) use a median
  of 13 ms of CPU per 10 s, against 160 ms for 12 (0.13 % of one core against 1.6 %). They wake 20–400 times a
  second against about 2,400. Fully idle, they use 2.4 ms and wake 20 times a second.
- The change: the reader's `wait_for(5 ms)` becomes `wait_for(1 s)`, and the worker's `wait_for(200 µs)` while a
  reader has its front becomes `wait_for(50 ms)`. Both limits are safety nets: every state change they wait for
  notifies under the queue mutex. The 1 s covers the wait thread's pump, which pops without a notify.
- No crash, no timeout, fault or kernel line, saves intact. The completion sequence kept its order, and the read
  ahead worked: the clock voice's queue had a median of 25 ms and a 95th percentile of 608 ms, against 52 and
  1,295 ms.
- Frames were worse than S1N: 28.7 against 37.1 flips a second, and 82 against 43 frames over 100 ms. S1 ran under
  much heavier io and memory pressure (a loading screen about 45 s longer at io full 40–52 %; then 10–30 times the
  major faults and the emulator mostly swapped out). Its long frames and the queue's worst latencies sit in that
  storm. The change adds no memory and no work, so it cannot plausibly cause that.
- **Not shown: no frame regression.** One run against one run cannot separate the change from the box's state. A
  back-to-back pair on the same route (the shared build, then this binary, 300 s each) would settle it, if the frame
  numbers matter before integration.
- Not in this experiment, to look at:
  - In async mode the wait thread's pump (`StartAprWaitThread`, started when an AMM-only submission stops at a wait)
    runs the same queues as the workers, under the lock while a worker runs its front unlocked. It could pop a buffer
    a worker or a reader still holds. Whether that path ever starts is not known.
  - A single `g_apr_queue_cv` serves all queues, so each submit wakes every reader and worker. Per-queue condition
    variables would cut the rest of the wake-ups (median 154 a second in the quiet intervals with a trickle of
    submits).
