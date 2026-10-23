# 0236 — APR async mode: can the wait thread's pump race the per-queue workers and readers?

**Question.** Exp 0216 left one path open: in KytyPlus's async APR mode an AMM-only submission that stops at a
WaitOnAddress starts the `bc5-apr-wait` thread, whose pump (`PumpParkedAprBuffersLocked`) runs and pops the fronts
of every priority queue, including the queues a worker (`AprWorkerThread`) and its read-ahead readers
(`AprReaderThread`) own. Does that path occur in the second title, and is the race real?

**Setup.** Read-only. No GPU run, no build. On the box only the claimed `~/bc5-work/exp0236` was written (the
scan scripts, their output and a copy of the source). 2026-10-23, 14:19–17:02.

- The code: `~/src/KytyPlus/src/libs/libAmpr.cpp` on the box, md5 `5f2ec30b…` (mtime 2026-10-23 11:30), exp 0229's
  integrated tree (F288; blob `8873cc8` in exp 0229's `raw/git-diff-f266548-after.txt`). Line numbers below are of
  that file; `raw/libAmpr-5f2ec30b-excerpt.txt` has the cited functions with their numbers.
- Thread evidence (laptop, `threads0236.sh`): the per-thread samplers of exps 0214, 0216, 0220, 0222 and 0229
  (`cpu0214.sh`/`cpu0216.sh`: every 10 s, every emulator thread whose name starts with `bc5-apr-`, which includes
  `bc5-apr-wait`). The wait thread never exits once started (libAmpr.cpp:2379–2391), so a run whose samples never
  show it never started it before its last sample.
- Trace evidence (box, `nice -n 19 ionice -c3`, in gaps with no emulator and no other lock, under a short lock line
  of its own): existing async-mode logs with `KYTY_BC5_AMM_TRACE=1`.
  - In async mode the submitting thread runs `RunOrderedAprCommands` only for an AMM-only submission (maps, no
    reads; libAmpr.cpp:2455, 2466–2477, 2487). So `amm trace: submission … waits at command` (2491) is printed only
    when that path parks a buffer and starts the wait thread (2489). `amm trace: resumed submission … finished`
    (2140) is printed only by the pump. `parked0236.py` counts both, the submissions by kind, and the
    `finished on worker` lines.
  - `parked0236.py` also paired waits with submits by the literal address. That is wrong for AMM buffers: the title
    records on the command-buffer object (`set-buffer cb X va Y`) and submits an AMM buffer by its buffer address Y,
    which the host resolves to X through `g_command_buffer_aliases` (libAmpr.cpp:1090–1101, 1282–1296). Its
    "AMM-only with a wait: 0" is void. `unpaired0236.py` found this (`raw/unpaired-G1.txt`,
    `raw/G1-amm-only-wait-example.txt`).
  - `waits0236.py` pairs them as the host does. It classifies each wait of a submission by what the host meets when
    it runs the buffer in record order: met by an earlier write-address of the same buffer to the same address
    (`self`), met already when recorded (`now`), or neither (`open`). It also counts who writes each waited address.
  - Files: the seven lake-bench runs of exps 0232/0233 (`~/bc5-work/exp0194/r-{G1,G2,G3,N1,N2,N3,N4}/emu.log`, exp
    0194's bench binary of 2026-10-22 12:04) and exp 0206's tcpW1 (`~/bc5-work/exp0206/tcpW1-play-pkg.log`), all
    full AMM traces. Also exp 0200's session S1 (`~/bc5-work/exp0200/raw/S1-amm.txt`, its own binary of 15:04): a
    filtered APR trace without the `amm trace: ` prefix, which keeps the submit and host lines but folds waits and
    writes into counts. So it gives the host lines only.
- Files here: `threads0236.sh`, `parked0236.py`, `unpaired0236.py`, `waits0236.py`, `patch_0236.diff`; `raw/`:
  `threads.txt`, `parked-first-scan.txt`, `parked.txt`, `unpaired-G1.txt`, `waits.txt`,
  `G1-amm-only-wait-example.txt`, `libAmpr-5f2ec30b-excerpt.txt`. The logs read stay on the box.

**Result.**

1. **The code: in async mode the pump has no notion of queue ownership** (`raw/libAmpr-5f2ec30b-excerpt.txt`).
   - `ExecuteAprCommandBuffer` holds `g_apr_queue_mutex` and runs an AMM-only submission on the title's thread
     (2455–2457, 2487). If it stops at an unmet wait, the rest is pushed onto `g_apr_parked[qi]` (2488), the same
     deque a worker owns when that priority has one, and `StartAprWaitThread()` starts `bc5-apr-wait` (2489).
   - That thread never stops. Every 500 µs it takes the mutex and calls the pump (2384–2387), which walks all eight
     queues. For each queue it runs the front with `RunOrderedAprCommands` (2134) and finishes and pops it
     (2138–2142), then the next one, until a front stops at a wait.
   - The worker takes `queue.front()` under the lock, then unlocks and runs it (2343–2358). Its comment says
     "Only this thread pops this queue" (2341). A reader marks a buffer `ra_state = 1`, unlocks, and keeps a raw
     pointer to it while it reads the file ranges, then writes `ra_data`, `ra_rc` and `ra_state = 2` through that
     pointer (2307–2326).
   - The pump does not look at `ra_state` or `ra_data`, does not lower `g_apr_ra_bytes`, and does not notify.
2. **So once the wait thread runs, the race is real and frequent: it is not a narrow window.** A worker runs its front
   unlocked for as long as the front takes (a file read: ms; a wait: polled every 500 µs). The pump gets the mutex
   within 500 µs whenever the worker has released it, and it then runs that same front. The interleaving:
   1. The worker takes front F and runs it unlocked.
   2. The pump runs F as well, while the worker is still in it. Both threads advance `F.next` without
      synchronisation, a data race and UB in C++. F's reads (the pump ignores the read-ahead data and reads the
      file again), maps, kernel events and address writes can run twice. What a second run of the same map does
      is not checked here. The pump finishes F (`FinishAprSubmission`: submission result and result buffer), pops
      it, and goes on to the buffers behind it, which may include ones a reader holds (`ra_state 1`) and
      prefetched ones (`ra_state 2`).
   3. The worker comes back and takes the lock. It calls `FinishAprSubmission` on the destroyed F (2364). By its
      declaration F is about 290 bytes, so libstdc++'s deque keeps one per 512-byte node and frees the node on
      `pop_front`: a heap use-after-free that writes a result through a `result_ptr` read from freed memory. If F
      was prefetched it lowers `g_apr_ra_bytes` by a size read from freed memory. Its own `pop_front` (2372) then
      removes a buffer it never ran, so that submission is lost (no reads, no events, no completion). If the pump
      has emptied the queue, it pops an empty deque (UB).
   4. A reader whose buffer the pump popped writes `ra_data`, `ra_rc` and `ra_state` into freed memory (2323–2326):
      heap corruption. Those bytes also stay counted in `g_apr_ra_bytes` for good. Prefetched buffers the pump
      pops leak their bytes the same way. Once 32 MiB have leaked, no reader can pick anything again, and the
      read-ahead is silently off.
   5. Smaller: the pump's pops do not notify, so readers wait up to their 1-s limit (exp 0216).
   - Sync mode (`KYTY_BC5_APR_SYNC=1`) is not affected: no workers or readers exist there (2466), and every pump call
     runs under the mutex.
   - A parked AMM-only buffer in a queue that has a worker is run by that worker anyway, at its turn. The pump is
     only needed for a priority that never had a non-AMM-only submission, so no worker exists.
3. **The wait thread never ran in any sampled run** (`raw/threads.txt`): 9 runs of exps 0214–0229 (the second
   title on the shared build or its test builds, all with the read-ahead on: 12 or 16 readers), 133–288 s each,
   2,125 s of samples in all, with workers `q0`/`q1`/`q3`/`q5`. `bc5-apr-wait` appears in 0 of 3,544 APR-thread
   samples.
4. **No AMM-only submission parked in any traced run** (`raw/parked.txt`; `raw/parked-first-scan.txt` is the same
   counts without the spans and wait totals):

   | run (trace span) | submissions with reads / AMM-only / other | `waits at command` | `resumed submission` | `finished on worker` |
   | --- | --- | --- | --- | --- |
   | G1 (275 s) | 2,478 / 539 / 913 | 0 | 0 | 3,391 |
   | G2 (277 s) | 2,507 / 566 / 923 | 0 | 0 | 3,430 |
   | G3 (279 s) | 2,479 / 533 / 846 | 0 | 0 | 3,325 |
   | N1 (359 s) | 2,508 / 552 / 884 | 0 | 0 | 3,392 |
   | N2 (357 s) | 2,521 / 536 / 919 | 0 | 0 | 3,440 |
   | N3 (356 s) | 2,544 / 534 / 895 | 0 | 0 | 3,439 |
   | N4 (354 s) | 2,504 / 542 / 806 | 0 | 0 | 3,310 |
   | tcpW1 (596 s) | 2,531 / 537 / 919 | 0 | 0 | 3,450 |
   | exp 0200 S1 (719 s) | 10,420 / 2,134 / 8,524 | 0 | 0 | 18,908 |

   - In all, 3,572 s of traced play and 6,473 AMM-only submissions, every one finished on the submitting thread.
   - In each of the eight full traces, `finished on worker` equals the submissions with reads plus the "other" ones
     (e.g. G1: 2,478 + 913 = 3,391). So every worker-path submission was run by a worker, and the pump finished none.
   - In S1 the worker lines are 36 short of that sum. That is the queue still behind at the end of the trace: S1's
     queues fell up to 129 s behind (exp 0200).
5. **The title's AMM-only submissions do carry waits, but each is met by the buffer's own earlier write**
   (`raw/waits.txt`, `raw/G1-amm-only-wait-example.txt`). With aliases resolved, every recorded wait pairs with a
   submission (0 left at the end of any trace). All waits are on one address, the sequence counter 0x90adf7f98
   (exps 0035, 0156).
   - In the eight full traces 555 AMM-only submissions carry a wait (67–71 per run, about one in eight). All 555 are
     `self`, with 0 `now` and 0 `open`. The buffer writes the counter := V and then waits for counter ≥ V (op 4),
     e.g. G1 at 45340.869 s: `write-address … 0x90adf7f98 value 0x20000000000007da`, then `wait-on-address … value
     0x20000000000007da … (now 0x20000000000007d9)`.
   - The 3,817 read submissions that carry a wait are all `open`. They wait for the counter to reach a value that
     an AMM-only submission writes later, which is exp 0035's pattern.
   - Only AMM-only submissions write the counter: 12,611–12,689 write-address commands per run, against 0 from
     submissions with reads or the others. AMM-only submissions run on the submitting thread under
     `g_apr_queue_mutex` (2457, 2487), one at a time. So nothing the host runs can move the counter between such a
     buffer's write and its wait, and the wait is met when the host reaches it. Only a store by the title's own CPU
     code in that interval could change it, and the trace cannot show those.

**Verdict.**

- **The path does not occur in the second title, and with the submission pattern seen it cannot.** Evidence:
  - 9 AMM-trace runs: 3,572 s and 6,473 AMM-only submissions.
  - 9 thread-sampled runs: 2,125 s.
  - In none of them did an AMM-only submission stop at a wait, did the wait thread start, or did the pump finish a
    buffer.
  - About one AMM-only submission in eight does carry a WaitOnAddress. In every one of the 555 traced, the wait is
    on the sequence counter the same buffer has just written to the waited value. Only AMM-only submissions write
    that counter, one at a time under the queue mutex, so their waits are met when the host reaches them.
  - The waits that do stop are in the read buffers. Those go to the workers, never through this path.
  - Coverage: seven lake-bench runs (a save loaded and the route to the lake, 4.6–6 min each), exp 0206's bench run
    tcpW1 (10 min) and exp 0200's 12-min session S1 through the cutscene's streaming burst. Another title, or a part
    of this one with another AMM pattern, could still reach the path.
- **The race is real in the code.** If the path ever fires in async mode, the pump runs fronts that a worker is
  running unlocked and pops buffers that the worker or a reader still holds. The results:
  - a data race on `next`;
  - commands run twice;
  - use-after-free and heap corruption;
  - lost submissions;
  - a read-ahead budget that leaks until the read-ahead is off.

  With any APR traffic this would follow within milliseconds, not rarely. The 1-s reader limit of exp 0216 covers
  only the missing notify. The race is latent today: nothing in the traced play reaches it.
- **Proposed fix (`patch_0236.diff`, not applied; for the top session).** In async mode a parked AMM-only
  submission goes to its priority's worker, as every other submission does: `StartAprWorker(qi)` (the worker and
  readers' `call_once`, factored out of the async branch) instead of `StartAprWaitThread()`. The worker already
  handles a front parked at a wait (it re-polls every 500 µs and is woken by the amm-only path's `notify_all`,
  2501–2503). Readers skip it: it has no reads. It keeps the same order as with the pump: the rest of the buffer
  runs behind the buffers already queued at its priority, and its wait is polled at the same 500 µs. At a priority
  that never had a worker, the parked buffer now starts one, with its readers. The wait thread and its pump remain
  for sync mode only, where nothing else touches the queues. The patch also corrects the readers' comment on the
  1-s limit.
  - `git apply --check` passes against a copy of the box's file (blob `8873cc8`). It was not compiled (no build on
    the box without a grant; no compiler on the laptop). It adds one function and changes two call sites. The
    worker's "only this thread pops this queue" invariant then holds in async mode.
  - Behaviour on today's traces is unchanged, because the changed branch never runs. A smoke run on the usual route
    would only show that nothing else changed. A test of the branch itself needs a title, or a synthetic APR
    submission, with an AMM-only buffer that waits.
  - When it goes in, `backend/kytyplus-patches/0001-bc5-lle-agc.patch` is to be regenerated from the tree (as in
    F288).
  - The alternative, a pump that skips worker-owned queues, needs a per-queue flag and keeps a
    second consumer of the same deques plus a 2,000-wake-ups-a-second thread. Routing to the worker removes both.
