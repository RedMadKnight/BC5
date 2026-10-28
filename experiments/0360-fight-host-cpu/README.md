# 0360 — the host's CPU cost per frame at the second title's fight

Ordered by the top session on 2026-10-28 after the maintainer's decision on Q24 ("łatka jako opcja w menu emulatora
(tymczasowo), a docelowo zacznij prace nad odciążeniem aby pozbyć się łatki"). Exp 0359 (the bvh session) is the
temporary game patch for F454; this experiment is the throughput work meant to make that patch unnecessary. Base: main
9a91242 (shared normal affa0c22, archive bb50b2e0); branch exp/0360-fight-host-cpu; nothing shared changed (D19).
Box work under the BOX-LOCK, claimed in `~/bc5-work/BOX-QUEUE` and `~/bc5-work/exp0360/CLAIM.txt`. RT on for every run.

**Question.** Where does the host's CPU go per frame at the maintainer's fight (by host thread and host function), and
which change cuts it enough that the title's own Hi job workers finish their frame-end chunks before the main (owner)
thread reaches its help loop, so that the fight passes with exp 0359's patch switched off?

## Offline reading (laptop only; the shared tree rebuilt locally)

The shared tree's units were rebuilt on the laptop from KytyPlus f266548 plus main's patch 0001: `bc5LleAgc.cpp`
e7cc2f60, `runtimeLinker.cpp` e37ed5cd, `pthread.cpp` 46c7ac3a and `semaphore.cpp` 8a9ddbc4 are byte-equal to the
box's (the md5s exp 0358's build checks). Everything below is read from that tree and from exp 0358's committed files.

- **The trap's per-thread CPU columns are kernel time, not CPU.** `bc5_proc_state` (exp 0358
  `raw/patch0358v4.pl` lines 68–80, reused by v5) parses `/proc/self/task/<tid>/stat` from ppid (field 4) into
  `f[0]`, so `f[10]` is utime (field 14) and `f[11]` stime (field 15) (proc(5)). It prints `f[11]` as "user" and
  `f[11] + f[12]` (stime + cutime) as "cpu". So every CPU figure of trap v4/v5 is system time:
  - the crash prints' guest and host thread lines;
  - the sampler's Hi columns;
  - the v5 thread table's "top 12 by CPU" every fifth second.

  The FIX=3 crash print (`raw/maintainer-test/playlog-stream.txt` of exp 0358, 75 s of play) shows the effect: the
  Render Thread at "2.07 s" and game-main at "1.42 s", while the frame profile has the game thread inside the host
  66 ms of each 104-ms frame. What those lines do measure is kernel time:
  - bc5-ring 6.70 s, bc5-chainwd 2.78 s, the Render Thread 2.07 s, game-main 1.42 s, bc5-apr-q5 1.28 s;
  - each Lo/Hi worker 0.50–0.58 s, with ~131,000 voluntary switches (1,750 a second, the semaphore's sleep/wake);
  - each Bk worker 0.04–0.06 s.

  So F453/F454's "the Bk workers got only 0.05 CPU s, runnable without a core" and "the Hi workers' CPU 0.5 s each"
  are not CPU readings. The state letters are right (R = running or runnable). The box's busy share in the v5 table
  comes from `/proc/stat` and is right. The load average at his fights was ~7 on 16 hardware threads (exp 0358
  `samples.txt`: 14:51:32 load 7.36). Whether the cores are saturated at the fight is therefore open again, and with it
  the premise that host CPU slows the Hi workers.
- **The frame profile's "game thread" mixes two threads.** `frame_profile_job(t_cq == 0, …)` counts every submission
  made on a thread whose `t_cq` is 0. The chain watchdog (`bc5-chainwd`, which submits a game thread's held chain after
  `BC5_DIRECT_CHAIN_HOLD_US`) never sets `t_cq`. Its prepare/list/cs therefore land in the game thread's "inside the
  host". Its "sync" and "hints" come only from `Direct::submit`, which is the game thread's.
- **What "sync" is** (`submit_one`, `sync_mappings`, `direct_sync_one`): `probe + sync_mappings + direct_sync`.
  - `sync_mappings`: the `/proc/self/maps` walk and `mincore`. It is throttled to once a second while private guest
    memory sits in its memfd.
  - `direct_sync_one`, at most every 50 ms unless the guest's ranges generation changed. It then:
    - rebuilds the views from a snapshot of every guest range: ~22,000, one `std::string` name each;
    - checks the memfd's block count (the fast path);
    - scans for chunks to import, merges BOs every 250 ms, and rebuilds the wanted mapping list;
    - drains the GPU (`wait_jobs`) when the views' signature changed or BOs were retired;
    - unmaps and maps the difference.

  At the fight the title maps and unmaps streaming pages, so most submissions see a new generation. Part of the
  28.6 ms is the GPU drain: a wait, not CPU. `BC5_DIRECT_TIMING=1` (on in the plays, exp 0343) journals the split
  every 128 submissions ("timing split").
- **The ring thread** (`queue_consumer_thread`) polls the 56 registered queues every 200 µs while any queue moved
  (1 ms after 1,000 idle passes). It submits the compute slices itself: filter, prepare and the CS ioctl on bc5-ring.
- **The title's `fs:0` accesses** are patched to a call into a 0x1000-byte trampoline. It saves nine registers, runs
  `pushfq`/`popfq` and an indirect call, and reads a thread-local cache (`TlsMainGetAddr`, `runtimeLinker.cpp`). That
  is tens of cycles per access where the console takes one, but no lock and no syscall. Whether the 603-block jobs
  touch `fs:` in their inner loop is not known.

## Design: the CPU meter (measurement first)

The decisive number is whether the Hi workers **wait for a core** at the fight. If they do not, host CPU is not what
delays their chunks, and no throughput candidate can close F454's race. Then the patch (exp 0359) stays the answer.
`/proc/<tid>/schedstat` gives each thread's ns on a CPU, its ns runnable but not running, and its slices (proc(5),
Linux `Documentation/scheduler/sched-stats.rst`), with no root.

`meter0360.pl` (measurement only, one unit, `bc5LleAgc.cpp`) adds:
1. **bc5-meter**, a host thread at nice +5 started at the first flip. It journals one `cpu meter:` line a second:
   - every thread's CPU, run-queue wait and kernel time over the second, with the top 18 by CPU;
   - the sums for the title's threads and for the host's threads, and for the Hi, Lo and Bk workers, game-main and the
     Render Thread, plus the Hi workers' largest wait;
   - the box's CPUs from `/proc/stat` (one digit per CPU), the package mount's own CPU (the `bc5-mount` process, which
     decompresses PFSC outside the emulator), and the rest of the box as the difference.
2. **The direct path's submit costs by the submitting thread's class**: the title's threads, bc5-ring, bc5-chainwd and
   other host threads, each with sync, hints, prepare, list and cs per second. This is fed from `frame_profile_submit`
   and `frame_profile_job` under the profile's own mutex.

`BC5_0360_METER=0` turns the thread off. Its cost is ~100 small `/proc` reads a second, on its own thread.
`build0360.sh <variant> <patch>…` builds `~/bc5-work/exp0360/<variant>/kyty_emulator` (exp 0358's compdb pattern,
one unit, `build0360.py`). The meter applies cleanly to a local copy of e7cc2f60 (4 edits). It has not been compiled
yet: there is no compiler on the laptop.

Plan:
1. Read the day's journals (frame profiles, timing splits, the v5 tables' busy share) for the fight seconds.
2. Run a meter build on the S6N route with RT on: the per-thread baseline and the meter's own cost.
3. The maintainer plays one fight on a meter shortcut. That gives the fight's real per-thread CPU and wait.
4. Choose 2–3 candidates from (1)–(3), each designed here before code.

## The fight in the day's journals (read-only extracts, the top session's GO, 15:29)

`~/bc5-work/exp0360/CLAIM.txt` and a BOX-QUEUE line were written at 15:29:01. The lock was empty and no emulator ran.
The extracts were taken at nice 19 / ionice idle; nothing else was written on the box:
- the journals of the six fight plays: 11:10 and 11:16 (test 0356), 12:16, 13:53, 14:29 and 14:50 (test 0358 traps v1, v3, v4, v5);
- the 14:44 trap v5 smoke run on the Continue route, which has thread tables like the 14:50 play;
- the 11:33 S6N 900-s run.

Only the lines `fp0360.pl` and the thread tables need are kept, in `raw/journal-extracts.txt.gz` (the 11:33 run left
out for size). `raw/frame-profiles-5s.txt` holds the 5-s means of every frame profile line (`fp0360.pl`). The trap
play logs were read on the laptop and not committed: their fault prints carry title code bytes.

- **F461 — at the fight the frame is not bound by the direct path, the GPU or the box's CPU count.** Means of the 29
  five-second windows of the six plays with ≥ 60 ms between flips, against the 14:44 route's steady part (t 120–200 s,
  16 windows). All values are ms per flip, except the first row:

  | | fight | route |
  |---|---|---|
  | flips/s | 14.2 | 45.4 |
  | ms between flips | 71.0 | 22.0 |
  | render thread inside the direct path | 13.3 | 9.5 |
  | – sync / hints / prepare / cs | 3.0 / 2.2 / 3.3 / 4.2 | 0.4 / 0.2 / 2.0 / 1.3 |
  | – label waits | 0.4 | 5.6 |
  | at the flip (drain) | 3.0 | 5.2 |
  | **outside the direct path** | **54.6** | 7.4 |
  | GPU busy | 11.8 | 17.4 |
  | game-thread jobs + ring jobs | 19.7 + 73.8 | 7.6 + 26.9 |

  The v5 thread tables of the 14:50 play put the box at 24, 26, 37, 45 and 34 % busy over the fight's 5-s windows
  (t 52–73 s). That is `/proc/stat`, unaffected by F460, and means 4–7 of the 16 hardware threads. The route is
  20–28 % at 45 flips/s. Over the fight the per-second pool sampler finds the five Hi workers asleep (S) in 28 of 29
  samples. So the fight does about the route's CPU work per second at a third of its frame rate. Each frame carries
  2.7 times the route's submissions but less GPU time. And 77 % of the render thread's frame is spent outside the
  direct path: in title code, in other HLE calls, or waiting. F454's single frame (104.6 ms with 66.8 inside the host)
  was a spike. The fight's typical frame has 13 ms inside.

  Consequence for the task: making the direct path or the GPU feed faster can take at most ~13 ms of a 71-ms fight
  frame off the render thread, and the cores are not saturated on average. Whether the title's threads wait for a core
  in bursts, and what the 55 ms "outside" is, needs the CPU meter.

**Setup.** (filled in as the work goes)

**Result.**

- **The meter build a5c7affc (15:49):** `build0360.sh meter meter0360.pl prof0360.pl`. It compiled in 28 s with
  0 errors and the tree's own 4 warnings (lines 85, 403, 701, 2411; none in the new code). The shared binary, the
  archive and the unit were unchanged afterwards.
- **M1 (15:50–15:55), the S6N route, RT on, 300 s, `run0360.sh`, the meter build: pass.**
  - 9,936 flips over 299 s = 33.2 flips/s, GPU busy 21.4 ms a frame, 30.1 ms between flips.
  - No crash, no kernel line (`raw/M1-kernel-stream.txt`: two IPv6 lines only), no TIMEOUT, no devcoredump.
  - Live saves unchanged (41a5a36fffb4f8d4, the maintainer's state after his 15:38 play).
  - The first 300 s of the 11:33 S6N run on the shared units did 33.4 flips/s. So the meter and the sampler cost no
    measurable frame rate.
  - The meter thread itself takes a median 1.7 ms once a second (p90 2.1, max 8.3; `raw/M1-meter.txt.gz`).
- **F462 — the S6N route on the meter: 26–29 % busy, the title's threads seldom wait for a core.** Means over
  t 180–300 s (~39 flips/s), in CPU ms per second (on a CPU / runnable waiting; `meter0360-sum.pl raw/M1-meter.txt.gz 30`):

  | | CPU | waiting |
  |---|---|---|
  | the title's threads | 3,230–3,320 | 220–310 |
  | the host's threads | 460–480 | 74–90 |
  | the five Hi workers | 620–650 | 66–88 |
  | the five Lo workers | 540–570 | 59–69 |
  | the five Bk workers | 800–845 | 14–31 |
  | game-main | 495–505 | 0–4 |
  | Render Thread | 500–515 | 10–12 |

  - Per Hi worker that is 13–18 ms of run-queue wait a second.
  - The package mount (`bc5-mount`, decompression) costs 0–1 ms/s once loaded, 150–600 ms/s while loading.
  - The rest of the box (kernel threads, the compositor) takes 600–1,130 ms/s.
  - Direct-path submit costs: on the title's threads ~250 submits/s, with sync + hints 30–45, prepare 94–103 and cs
    44–50 ms/s; on bc5-ring ~1,000 submits/s, with 9–40, 35–38 and 75–80 ms/s.
- **F463 — where the title's threads spend their host time on the route (the sampler, 4 ms of CPU per sample, M1).**
  The rip classes per group, t 180–300 s (`raw/M1-meter.txt.gz` "cpu prof:"). "lib" here still includes the title's own
  code (the M1 build counted the guest memfd, `memfd:KytyPrivateMemory`, as a library; fixed for later builds):

  | group | emulator | kernel | lib + title |
  |---|---|---|---|
  | game-main | 14–15 % | 2 % | 83 % |
  | Render Thread | 38–40 % | 12–13 % | 49 % |
  | Hi workers | 1 % | 5–6 % | 92–94 % |
  | Lo workers | 1 % | 2–3 % | 96–97 % |

  The emulator-code samples resolved with `nm -n -C` of a5c7affc (`prof0360-sym.pl`, the last cumulative histogram,
  17,239 samples):
  - **game-main:** `Loader::TlsMainGetAddr` 54 % and `LibKernel::KernelGetProcessTimeCounter` 36 %, then the
    memory map calls (`VirtualRanges::QuerySpan` 4 %, `KernelMapDirectMemory2` 3 %).
  - **Render Thread:**
    - `full_state::Tracker::emit_prefix` 27.5 %: the full-state prefix of every drawing buffer, a byte-by-byte
      scan of 28,672 register slots.
    - `Direct::submit_now` 19 %, `full_state::Tracker::apply_level` 13 %, `state_stack::Tracker::apply_in_place`
      8 %, `direct::Device::submit` 5 %, and the rest of the direct path.
  - **Hi/Lo workers:** `PthreadTakePendingSignal` and `TlsMainGetAddr`.

  `TlsMainGetAddr` is the end of every patched `mov reg, fs:[0]` in the title's code. The trampoline in front of it
  (`Jit::SafeCall`: nine pushes, `pushfq`/`popfq`, an indirect call) lives in guest memory, so its own samples are
  in the title's share. `KernelGetProcessTimeCounter` reads the TSC twice per call (exp 0166's pause adjust reads
  it again).

## Design: candidates (2026-10-28, from F461–F463)

F461 rules out the direct path and the GPU as the fight's limit, and the route's cores are not saturated (F462).
What the host can still change on the threads of F454's race (the owner game-main and the Hi workers) is the host
time inside their own calls. On the route that is 15 % of game-main and 1–6 % of the workers, plus the TLS
trampoline counted in the title's share.

- **A — the TLS fast path (`fasttls0360.pl`, `runtimeLinker.cpp`).**
  - Seven stubs go into the free part of the handler page (handler_vaddr + 0x400 + reg × 32). Each does
    `mov reg, fs:[D]`, `test reg, reg`, `jz slow`, `ret`, where D is the host thread_local `g_tls_cached_main_tcb`
    relative to the thread pointer (the same in every thread: the executable's static TLS). The slow path jumps to
    the existing stub, which fills the cache on a thread's first access.
  - The patched call sites point at the new stubs. The flags and the return-address slot are clobbered as on the
    existing path (SafeCall ends with `add rsp, 0x80`).
  - Expected: each title TLS read drops from the trampoline plus a C++ call (tens of cycles, with `popfq`) to a few
    cycles.
  - The gain is the TlsMainGetAddr samples (~6 % of game-main's CPU on the route) plus the trampoline's, which the
    fixed sampler's title histogram will show at handler_vaddr.
  - It is on every title thread, the workers included. `BC5_0360_FAST_TLS=0` turns it off.
- **B — one TSC read per clock call (`onetsc0360.pl`, `pthread.cpp`).** `KernelGetElapsedTsc` and `KernelReadTsc`
  use one `rdtsc` for the value and the pause adjustment. Expected: half of `KernelGetProcessTimeCounter`'s ~4 % of
  game-main. `BC5_0360_ONE_TSC=0` turns it off.
- **C (designed, not built) — `emit_prefix` without the byte scan.** A bitmap of set registers walked with 64-bit
  words, and the output reserved once. That is ~14 ms/s of the Render Thread on the route. It is left for later:
  the Render Thread is not on the fight's critical path (F461).

A and B change only host functions. The title's code and the job system are untouched, and both are on by default
in the candidate build with a switch each. They are measured on the S6N route against the meter build: flips/s,
game-main's and the Hi workers' CPU per frame, the sampler's shares. Then, if the route passes, the maintainer's
fight with exp 0359's patch off decides.

- **F460 — exp 0358's per-thread "cpu" figures are kernel time (stime), not CPU.** See the offline reading above:
  `bc5_proc_state` (trap v4/v5) prints `/proc/<tid>/stat` field 15 as "user" and fields 15 + 16 as "cpu". Every
  per-thread CPU figure is kernel time: the crash prints, the sampler's Hi columns, and the v5 thread tables'
  ranking. F453/F454's "the Bk workers got only 0.05–0.06 CPU s" and "the Hi workers' CPU 0.5 s each" therefore do
  not show starvation. The state letters and the box's busy share are correct.

**Verdict.**
