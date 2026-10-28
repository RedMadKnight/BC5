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

**Setup.** (filled in as the work goes)

**Result.**

**Verdict.**
