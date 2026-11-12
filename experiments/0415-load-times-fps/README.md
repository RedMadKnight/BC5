# 0415: load times, then fps (the second title)

The maintainer's order of 2026-11-12: "następny problem jakim masz się zająć - długie czasy wczytywania poziomów i
ładowania gry (np. po uruchomieniu gry po zakończeniu fimków na początku, długo wczytuje się menu), a potem problem
zwiększenia fps".

Marks: [M] measured (a number read from a raw file, named), [D] derived by a rule stated here from raw files,
[C] read from code (file and line; not a cost), [I] inferred.

Code references: `K:` is KytyPlus f266548 with the patch 0001 of branch `int/0413-tested-into-shared` (057e7d07)
applied; `E12/` is `experiments/0412-memory-guardian/`.

## Question

1. What makes the second title's loads slow on our host: the menu after the intro movies, and a save load up to play?
   Ranked by measured seconds, with fixes behind default-off switches and an A/B.
2. After that: what limits its frame rate in play (the ordinary frame is 34.1 ms and GPU-bound, E12 section 26).

## Setup

Sections 1-3 are laptop work on existing data and on the source: no box access, nothing run. Section 4 is the design
of the measurement; it runs only on the top session's slot.

## Result

### 1. The time line of a scripted start, from exp 0412's existing runs (2026-11-12, laptop)

Source: 25 scripted runs of `E12/run0412n.sh` on builds g412f-g412n (`E12/raw/<tag>-frames.txt`, `-sampler.txt`,
`-start.txt`, `-route.txt`), RT on, the unpacked title (`BC5_GAME_DIR`: no bc5-mount, no Kraken decode in the path),
the copy of his save. Times are on the journal's clock (the first frame-profile line is at 2.1-2.3 s; the runner's
clock is about 1.3-1.5 s ahead [M `raw/x1why-route.txt`]). The rules [D]: movies end = the first 3 s window after 8 s
under 24 flips/s; start screen runs = the first moment after that with 30 flips/s or more in two 3 s windows in a row.

| phase | journal time | what is seen | already timed? |
|---|---|---|---|
| P0 process start to the first flip | 0 to 2.1-2.3 s [M] | one 1,499 ms hold of the device mutex by `bc5-ring` (direct sync 850, learned 606) [M `raw/r1holds-lockstat.txt`]; 3.9 GiB pinned before the first flip, 8.8 GiB at 5 s [M sampler] | no profile at all |
| P1 logo card and intro movies (Bink, decoded by the title: `BinkAsy0/1` threads) | to 29.5-30.0 s in all 25 runs [D] | 29.6 flips/s, emulator 1.5 CPUs, GPU busy about 75 % of the time [M `raw/x1why-frames.txt`]; the length does not vary, so it is the movies' own length | frames only |
| **P2 the scene behind the start screen loads (his "po filmikach długo wczytuje się menu")** | 30 to 48.5-54.5 s: **19.0-24.5 s, median 20.5 s over 25 runs** [D] | 11-17 flips/s; Render Thread 64-87 % of a core, game-main 32-73 %, `bc5-ring` 18-35 %, `bc5-chainwd` 12-25 %, job threads 13-20 % each, emulator 2.9-5.1 CPUs of 16; minor faults 42,000-83,000/s; GTT 9.1 to 12.0 GiB (+2.9 GiB pinned); available 3.7 GiB to 0.57 GiB; GPU busy 12-34 % of the time [M `raw/x1why-sampler.txt`, `-frames.txt`] | E12's "scene load 33-62 s" window: it also holds about 10 s of the idle start screen |
| P3 the start screen, idle | 51 to 86 s | 37-38 flips/s; the runner does not look before 85 s (`E12/run0412n.sh:161`), so about 35 s of every run is waiting | (not a load) |
| P4 the list and the Continue menu | cross at 86, 92 and 98 s (runner 87-88, 93-94, 99-101 [M 13 runs]) | 25-37 flips/s | only as part of "menu and list 62-104 s" |
| **P5 the save load** | from the Continue cross (about 98 s) to the first return to speed at 112-118 s [D]: **about 15-20 s**; the runner's "G" is at 117-126 s on its own clock | 10-14 flips/s at 96-108 s; GTT falls 12.16 to 10.97 GiB and comes back (the title frees the start scene and maps the level); `Archive_Asset_I` 32 %, `bc5-apr-q5` 8-16 % [M] | E12's "save load 104-132 s" |
| P6 play with streaming still going on | G to about 150 s | further slow stretches 118-130 s and 130-150 s in nearly every run [D]; major faults 450-4,800/s at 130-150 s with available at 230-370 MiB [M]: the memory wall (exp 0412's subject) | E12's "play" |

So of a scripted run of 180 s, the two loads the maintainer named are **about 20 s (P2) and about 15-20 s (P5)**,
and P5 runs straight into the memory wall. The length of P1 is the movies'. What was never measured: P0; P2 and P5
as phases of their own (the per-phase tables of E12 sections 19-24 use fixed windows that mix them with idle
screens); where P5 ends by a rule that knows about reads (the runner's G is a frame-rate rule); anything about file
reads per phase; any wait of the title's own threads by cause.

What E12 already says about the loads (its windows, so roughly P2 and P5) [M there]: no thread is at 100 % of a core
over a whole phase; the GPU is 6-29 % busy; the Render Thread is 47 % / 35 % in guest code, 29 % / 50 % waiting,
22 % / 14 % in host code; game-main waits about half the time on the title's own condition variables; the device
mutex is held 45 % of the wall clock and three threads wait 35 s for it over a run; the two table fixes
(`KYTY_BC5_RANGES_FAST`, `KYTY_BC5_PHYSMAP_SORTED`, both defaults in 0413's table) took the load windows from
15.0 / 12.1 to about 22 / 18 flips/s. A load in which nothing is saturated is a chain of hand-offs: its length is
the sum of the latencies on the critical path, not anybody's CPU time. Section 4 measures it that way.

### 2. Where our host does slowly what the console does in hardware or in its kernel (code reading, laptop)

Nothing in this section is a measured cost. "Count" says how section 4 measures it.

| # | candidate | where [C] | why it can cost seconds in a load [I] | count |
|---|---|---|---|---|
| C1 | **The compute queues' doorbell is polled.** `bc5-ring` reads the doorbell page, serves what it finds and then sleeps 200 µs after every pass, 1,000 µs after 1,000 idle passes ("the driver never tells us about a doorbell write") | `K:src/libs/bc5LleAgc.cpp` soft-CP queue loop, the `sleep_for(idle_ticks > 1000 ? 1000 : 200)` at its end | on the console a doorbell write reaches the GPU at once; here every compute submission starts 0.1-1.1 ms late (plus 50 µs of timer slack). `bc5-ring` makes about 620 submissions/s. A loader that dispatches, waits for the result and dispatches again pays this on every step | the period as a switch: load time against period is the measurement |
| C2 | **Every host wait in the submit path is a sleep poll**: `drain()` at each flip (50 µs), the in-flight cap of 24 (50 µs), the label waits (20 and 50 µs), the hold thread (20 µs). With the default timer slack of 50 µs each poll is 70-110 µs | same file: `drain()`, `submit_now`'s cap, `wait_satisfied` loops | each wait ends up to 0.1 ms late and the Render Thread makes about 5,400 voluntary context switches a second already in the movies [M `E12/raw/n1src-prof-render.txt`] | count and time per wait site; timer slack as a switch |
| C3 | **A layout change drains the GPU.** `direct_sync` calls `wait_jobs()` (`wait_idle`, up to 2 s) whenever the view set's signature changed or a BO retires, and once more per stale anonymous mapping; all under the device mutex | same file: `direct_sync` ("mappings are about to go or be replaced"), `sync_mappings` pass 1, `wait_jobs()` | in P2 the title maps 2.9 GiB in thousands of steps; each submission after a map waits for everything in flight, with every other submitter stopped behind the mutex. Fits "GPU 12-34 % busy" | `g_dprof_drains` exists; add the time, per phase |
| C4 | **The device mutex covers the whole submission** (probe, mapping sync, import, learned windows, filter, ioctl) on three threads | E12 sections 20-22 [M]: held 45 % of the time, 35 s waited per run | stage 1 of `E12/DESIGN-device-mutex.md` (import and mapping maintenance outside the lock) was never built | hold and wait per part, per phase |
| C5 | **Guest mutexes never spin.** A guest mutex is a host `std::mutex` + condition variable + owner field; a contended lock sleeps on the condition variable and is handed over by `notify_one` | `K:src/kernel/pthread.cpp:1480-1603` (`NativeMutexLock`, `NativeMutexUnlock`) | the console's adaptive mutexes spin briefly; here every contention on a short section (allocator, asset tables) is a sleep and a wake of tens of µs, and the unlock is a futex syscall. Fits "nothing saturated, 3-5 CPUs used" | contended locks and their wait, per phase |
| C6 | **A signal wakes everybody**: `PthreadCondSignal` picks one waiter but calls `notify_all`; a semaphore signal and an event-flag set wake all waiters; every wait registers in one global list under one mutex | `K:src/kernel/pthread.cpp` (cond signal), `semaphore.cpp`, `eventFlag.cpp`, `common/threads.cpp` | ten job threads on one semaphore: nine futile wake-ups per job posted (E14 survey item 5, "a targeted semaphore wake") | signals, woken, futile |
| C7 | **One global memory mutex** (`g_memory_operation_mutex`, recursive) around every map, unmap, protect, query and name call; AMM commands run under it from the APR worker | `K:src/kernel/memory.cpp` | the title's own `mmap`/`mprotect`/query calls and the AMM worker run one at a time; with the two table fixes the passes under it are short, the lock is still one | contended acquisitions and wait |
| C8 | **Recommitted private memory is zeroed by one thread** with an `lseek(SEEK_DATA/SEEK_HOLE)` loop and `memset`, under two locks | `K:src/kernel/memoryAddressSpace.inc` (`Commit`) | hundreds of MiB recycled in a load would be seconds; the console's kernel hands out zero pages lazily | bytes and time |
| C9 | **File reads are copied twice and staged**: APR read-ahead into a host vector, then `memcpy` into the guest at the read's turn; one in-order worker per priority queue; with `KYTY_BC5_APR_PARALLEL` a run of reads creates and joins up to 7 threads; buffers over 1 MiB are not read ahead; no `fadvise` | `K:src/libs/libAmpr.cpp` (`AprWorkerThread`, readers, `ReadHostFileToGuest`); the copies are listed in the 0408 note | the console reads into the destination pages. E12 saw 150-190 MiB/s asked and 310-440 MiB/s read from disk in the loads: the disk reads twice what the title asks | per read: bytes, queue wait, read time, copy time; time with a read outstanding per phase |
| C10 | **Guest TLS access and the process-time counter go through a thunk** (`Jit::SafeCall`: flags and nine registers saved per call) | `Loader::TlsMainGetAddr`, `KernelGetProcessTimeCounter` | measured before: 3.0-3.6 % and 2.2 % of game-main's CPU [M E12 section 24] | (known) |
| C11 | **`sceHttpSendRequest` is synchronous on the real network**, with a blocking resolve and connect and no timeout | `K:src/libs/network.cpp` (`HttpFetchSync`) | if the title asks the network on the way into the menu, one call can block for seconds | calls and time (expected 0; a catcher) |
| C12 | **The kernel's own work at the wall**: P2 pins 2.9 GiB (`udmabuf` imports under the device mutex; each first touch a fault: 42,000-83,000/s), and from the end of P2 on available memory is under 0.6 GiB, with `kcompactd0` at 30 % of a CPU [M E12 section 25] | the import path of `direct_sync`; exp 0412 owns the wall | imports of a few MiB take up to 600 ms when memory is full [M E12 section 27] | import count, bytes and time per phase; reclaim counters of `/proc/vmstat` per phase |

Read and set aside [C]: shaders run natively, so there is no shader or pipeline compilation and no cache to add;
APR completion is event-driven (no polling between the worker and the waiting thread); `sceKernelUsleep` is exact;
the flip is paced only by the vblank; save data, user and system service calls have no sleeps; the journal in "min"
mode is a buffered file flushed twice a second (exp 0406's audit). The movies are the title's own Bink decode.

### 3. What a first reading of the phases suggests [I]

- P2 looks bound by the Render Thread and what it waits for: it is the one thread near a full core (64-87 %), a
  fifth of it is host code and a third is waiting (E12 section 19), and the things it waits on are C2, C3 and C4.
- P5 adds the reads (C9) and the release and re-import of memory at the wall (C12); its end is set by streaming, so
  its length needs a rule on reads, not on frames.
- C1, C5 and C6 are latency on every hand-off between the title's threads and between them and the GPU; no profile
  of CPU time can show them. Their cost is measured by changing them.

### 4. The measurement (design; nothing built or run yet)

**Route** (`run0415.sh`, from `E12/run0412n.sh`'s skeleton: atomic BOX-LOCK claim, own lines only, private working
directory, private save copy reset from the named read-only snapshot
`~/bc5-data/saves/PPSA03671-20261111-2100-memory-heavy`, its sum by one stated recipe under `LC_ALL=C`, `ulimit -c 0`,
the emulator checked by pid, exe md5 and environment, the kernel log streamed to the laptop, stop on a kernel line).
Differences: the keys are gated on the journal from 35 s, not 85 s (cross when the start screen has run at 30
flips/s for two polls after the slow stretch; then cross, cross as before), which also takes 35 s of idle screen out
of every run; play for 30 s after the load and stop. One run is about 130 s. The words are 0413's launch words
(`words0413launch.txt`), RT on.

**Phase marks**, from the emulator itself: the counter file below gets a line per second and a mark line when an
input command is consumed (the key's moment on the journal clock), at the first flip, and at the first and the last
APR read of a burst. Phases are cut offline by rule: P0 to the first flip; P1 to the first frame over 60 ms after
15 s; **P2 to the first second of 30 flips or more that starts a run of three**; P4 between the keys; **P5 from the
Continue key to the first three seconds with 20 flips/s or more and no APR read outstanding**; P6 the 30 s after.

**In-emulator counters**, one switch `KYTY_BC5_LOAD_STAT=<file>`, default off, no change of behaviour (one
relaxed atomic add per event when on, one predictable branch when off): per cause a count, the summed time and the
longest single time, written once a second with the journal clock and CLOCK_MONOTONIC. Causes: APR reads (bytes,
size classes, wait in the queue, read, copy; time with at least one read outstanding); AMM commands by kind; the
memory mutex (contended, wait); `Commit` zeroing (bytes, time); guest mutex locks (all, contended, wait); condition
and semaphore signals (waiters woken, woken for nothing); the device mutex by thread and part (hold, wait);
`wait_jobs` (count, time, by reason); the flip's drain, the in-flight cap and each label-wait site; imports (count,
bytes, time); ring passes (packets served, passes that found work right after a sleep); `sceKernel` open, stat and
read (count, bytes, time); HTTP sends. CPU test of the table and its writer on the laptop and the box.

**Outside the emulator**, per run (all read-only, no ptrace, never attached to a `bc5-*` thread): perf cpu-clock at
1 kHz on the title's threads with symbols (`E12/perfall0412.sh`'s pattern, widened to the job and asset threads);
every thread's CPU, run-queue wait and voluntary switches each 250 ms (`E12/thr0412.py`); the 1 s sampler with
`/proc/<pid>/io`, `/proc/diskstats` of the NVMe, PSI io and memory, `/proc/vmstat` reclaim and compaction counters,
GPU engine time from fdinfo. A NAS rsync seen during a run is written into its row.

**Cause by change, not by profile** (one build, every knob default = today's behaviour):
- `KYTY_BC5_RING_POLL_US` (200): runs at 50, 200 and 1,000. If P2 and P5 move with the period, the doorbell latency
  is on the critical path and its slope gives the seconds.
- `KYTY_BC5_LOAD_DELAY=<cause>:<µs>`: a busy delay added to one cause (APR completion, AMM command, guest mutex
  hand-off, submission outside the lock). The phase's growth divided by count × delay says how much of that cause's
  time is on the critical path (1 = all of it; 0 = it runs beside the path and a fix buys nothing).
- Candidate fixes in the same build, each default off: `KYTY_BC5_RING_SPIN_US` (after work, look at the doorbell
  without sleeping for that long), `KYTY_BC5_TIMERSLACK_NS` (the polls' 50 µs slack), `KYTY_BC5_MUTEX_SPIN_US`
  (guest mutex: try for that long before sleeping; same lock order and owner rules). The fixes for C3, C4, C6, C9
  are written after the first ranking, into the same build line.

**Runs.** Baseline four times (the spread: P2 was 19.0-24.5 s over 25 old runs, so a fix must beat about 2 s on a
mean of four to count); then each arm twice in ABBA order with the baseline. About 20 runs of 130 s plus the build:
about 60 minutes of the box. Whole-run numbers are labelled as such; a phase a run did not reach is "not measured",
not zero.

**What the design cannot see.** Which of the title's threads waits for which other (no call chains of guest code);
the GPU's own time per pass (part 2); the effect of the memory wall on P5 is recorded (available memory, reclaim,
major faults per phase) but not removed: exp 0412 owns it.

### 5. The kit for build L1 (laptop, 2026-11-12; not built on the box, not run)

`kit/` (pinned by `kit/kit.sha256`):

- `0415-l1.diff` (md5 `80b3086f`, stored byte-exact: the host tree mixes LF and CRLF files): against the host tree
  with main's swapped patch `01abfc0c` (the box's shared tree reads the same pin [M, 2026-11-12 18:16]; the edits
  were first made on 057e7d07 and came out the same). One new header, `src/bc5/load_stat.hpp` (tag ls415), and
  edits in eleven files
  (`tree-l1.md5` has the sums the box must reproduce). All words default off; unset, empty and "0" are off.
  - `KYTY_BC5_LOAD_STAT=<file>`: 31 causes (the list is the header's `Cause`), each a count, a summed time, the
    longest single time of the second and an item or byte count; one cumulative line a second with CLOCK_MONOTONIC,
    the journal's time of the last flip and the number of APR command buffers outstanding; a mark line per scripted
    key press. When off, a call site costs one test of a flag.
  - `KYTY_BC5_RING_POLL_US` (200 = today, the long-idle sleep stays five times it) and
    `KYTY_BC5_LOAD_DELAY=<cause>:<µs>` (a busy delay per event of one cause; wired for `ring_pass`, `dev_wait`
    (before the lock), `apr_buffer`, `amm_cmd`, `mutex_contended`): the two measurement knobs.
  - Candidate fixes: `KYTY_BC5_RING_SPIN_US` (C1: after a pass that served packets the doorbells are read again
    without a sleep for that long), `KYTY_BC5_TIMERSLACK_NS` (C2: `PR_SET_TIMERSLACK` at process start, inherited
    by every thread), `KYTY_BC5_MUTEX_SPIN_US` (C5: a held guest mutex is tried again for that long before the
    thread sleeps; `mutex->m` is released between tries, the owner field is read and written under it as before;
    a timed lock's deadline starts after the spin, so it can be late by at most the spin).
  - From exp 0416 (branch `exp/0416-emufive-switches` c7bc3250, its `mk0416.py` run on the pinned inputs, outputs
    `81049581` and `2d97421c` as that session states), so that every candidate is in one build:
    `KYTY_BC5_SEMA_TARGETED_WAKE` (C6 for kernel semaphores: a signal wakes only the waiters it serves) and
    `KYTY_BC5_EVENT_COALESCE_SAME` (a repeated EOP trigger with the same data counts on the newest unread entry).
    My two semaphore counters sit on top of its `semaphore.cpp`.
  - Limits: in the lean build the label-wait and in-flight-cap counters are absent (they sit in a function lean
    compiles out); `sema_wait` and `cond_wait` time every call, blocked or not; `mem_lock_wait` counts only
    acquisitions that found the mutex taken.
- `test0415.cpp`: the header's CPU test, two processes (off: nothing counted, nothing written, the knobs read
  today's values, the words' grammar; on: counts, times, the busy-stretch accounting, the delay of one cause only,
  contended against uncontended locks, 8 threads on one slot, the file's lines). **49 of 49 and 31 of 31 on the
  laptop** (clang 22, MSVC target) [M]. Its last part is a model of the guest mutex with the spin loop copied by
  hand (exclusion and progress over 160,000 sections, with and without spin): a check of the loop's logic, not of
  the host's function.
- Not checked on the laptop: that the ten edited units compile (they need the Linux headers; the box build is the
  first compile), and anything at run time.
- `mk0415.sh`: copies the shared host tree (pinned by the md5 of its diff against f266548, given as `P_TREE`),
  applies the diff, checks the edited files against `tree-l1.md5`, builds and runs the CPU test in the container,
  then configures and builds the normal and the lean variant under `~/bc5-work/exp0415` (0413's `p0413g.sh`
  options); the shared tree, builds and backend archive are only read. No emulator.
- `run0415.sh <tag> normal|lean <play s> [WORD=VALUE ...]`: one run of section 4's route. Dry-run on the laptop
  [M]: the launcher's six anchors each occur once in the pre-swap `play-pkg.sh` copy of exp 0409 and the edit gives
  the expected 11 diff lines and a script that parses; the gate reads a synthetic counter file. Never run as a whole.
- `col0415.py` (host, `/proc` and `/sys` only, one JSON line a second) and `perf0415.sh` (container, cpu-clock at
  1 kHz on the title's threads; every `bc5-*` and `kyty-*` thread is left out by name).
- `phases0415.py` (laptop): cuts a run into P1-P6 by section 4's rules and prints per phase the counters'
  deltas and the collector's (per-thread CPU, GPU engine time, reads asked and from disk, reclaim). Checked on a
  synthetic file with known phase lengths (30, 20, 5, 12, 17, 25 s: reproduced) [M].

**The first slot's runs** (each about 130-150 s; RT on; words of 0413's launcher; `R_WD_MIB=220`):

| # | runs | arm | answers |
|---|---|---|---|
| 1 | b1..b4 | normal, counters on, perf on | the spread of P2 and P5; the ranking by counters |
| 2 | n1, n2 | normal, counters on, `R_PERF=0` | what perf costs |
| 3 | l1, l2 | lean, counters on | what the journal, timing and frame-profile lines cost in a load (his daily play is lean) |
| 4 | p50a/b, p1000a/b | `KYTY_BC5_RING_POLL_US=50` / `1000` | C1 by slope |
| 5 | s1, s2 | `KYTY_BC5_RING_SPIN_US=300` | C1's fix |
| 6 | t1, t2 | `KYTY_BC5_TIMERSLACK_NS=1000` | C2's fix |
| 7 | m1, m2 | `KYTY_BC5_MUTEX_SPIN_US=30` | C5's fix |
| 8 | d1..d3 | `KYTY_BC5_LOAD_DELAY=amm_cmd:200`, `apr_buffer:2000`, `mutex_contended:100` | which of these is on the critical path |
| 9 | w1, w2 | `KYTY_BC5_SEMA_TARGETED_WAKE=1` | C6's fix (exp 0416's) |
| 10 | e1, e2 | `KYTY_BC5_EVENT_COALESCE_SAME=1` | exp 0416's second switch |

Arms 4-8 alternate with a fresh baseline when the first four show a drift over the session.

### 6. The first slot (2026-11-12 19:21-21:00 box time, the top session's window): build L1, the baseline, the first cause and its fix

**Builds** (private, `~/bc5-work/exp0415`; shared tree pin `01abfc0c`, archive `75e30335`, both only read) [M]:
- `mk0415.sh` stopped at configure (ffmpeg-core's CMake asks git for its commit and wants its prebuilt archive);
  `mk0415b.sh` copies the tree with `.git` and the shared build's prebuilt, as 0413's `p0413.sh`. The 12 edited
  files matched the laptop's sums; CPU test on the box 49 of 49 and 32 of 32 (one more than on the laptop: the
  CLOCK_MONOTONIC check). **L1: normal `8f0e4c8c`, lean `2e397081`**, 284 / 287 warnings (not compared with the
  shared build's count).
- `mk0415c.sh`, incremental: **L1b = L1 + `kit/0415-l1b-apr.diff`** (`KYTY_BC5_APR_POSIX`, below): normal
  `55b05fae`, lean `f691fcf5`; L1 kept in `bin-l1`, `bin-lean-l1`.

**Runner.** `run0415.sh` needed three corrections on the box, each as a new file: `run0415b.sh` (`/home` is a link
to `/var/home`, so the "save directory is under exp0415" check compares resolved paths), `run0415c.sh` (the
collector's errors kept), `run0415d.sh` (the snapshot is read-only and `cp -a` kept that: the private copy is made
writable; **b1 ran on a read-only save copy**, the others on a writable one). The private launcher is derived from the
shared `play-pkg.sh` `157021e3` (installed by exp 0413 at 19:20): its first start on the new shared-tree code was
run b1, which started and reached play. The snapshot is the `PPSA03671` directory itself (sum `e3b9be4116574c95` by
the runner's recipe); the private copy is reset from it before every run (section 7 on what the title writes). RT on, no zero skip, the launcher's own words,
watchdog 220 MiB (never acted; lowest available 378-534 MiB over the first twelve runs). No kernel line and no crash line in any run. The NAS
rsync ran during most runs (the tables' last column: 1 = an rsync process was seen in that phase).

**The route works from 12 s:** the first cross goes out at 56-63 s on the runner's clock instead of 87 s, a run with
30 s of play is 109-126 s.

**Baseline, six runs** (b1-b4 on L1; c1, c2 on L1b with the new switch off), by `tab0415.py` [M]:

| | menu load (P2) | Continue to 20 flips/s | P2: APR busy | P2: asked / from disk | P2: per read | P2: buffer's wait in the queue | P2: device mutex held / waited |
|---|---|---|---|---|---|---|---|
| b1-b4, c1, c2 | **20.0-22.0 s, mean 20.9** | 15.5-22.9 s, mean 18.0 | 17.9-20.3 s (90-97 % of the phase) | 4.9-5.0 GiB / **11.0-11.9 GiB** | 1.5-1.8 ms | 603-689 ms | 10.9-13.2 s / 5.8-7.4 s |

- The menu load is the disk's: a read buffer is outstanding 90-97 % of the phase, the title asks for 5 GiB in
  63,000-65,000 reads (mean 80 KiB) and **the NVMe delivers 2.2-2.4 times that at 550-590 MiB/s, which is its limit
  on this board** (PCIe 2.0 x2; F286 measured 154-623 MiB/s). The phase's length is the bytes from the disk divided by
  that rate.
- Why twice the bytes [C, then M below]: `ReadHostFileToGuest` and `ReadHostFileToHost` open the file anew for every
  read (`Common::File::Open`, then seek and `fread`). A fresh descriptor has no read-ahead history, so the kernel
  treats each 80 KiB read as the start of a sequential stream and reads ahead of it. The console reads exactly the
  bytes the command names.
- More reader threads do not help while the disk is the limit: `KYTY_BC5_APR_READAHEAD=12` (ra1, ra2) gave 22.0
  and 21.0 s [M].
- The save load by the rule "reads quiet" is 17-40 s and too noisy to compare (streaming goes on into play); the
  column "Continue to 20 flips/s" is the comparable one.
- Other counters of P2 in b1, for the ranking that follows the disk [M]: device mutex held 55 % of the phase and
  6.2 s waited for it (three threads); direct sync 3.9 s, learned windows 1.8 s, imports 1.1 s (6.1 GiB), AMM
  commands 1.0 s (14,857), the flip's drain 0.8 s, label waits 0.8 s, anonymous sync 0.7 s, contended guest mutexes
  0.2 s (2,297 of 959,000 locks), `wait_jobs` 0.1 s, memory-lock waits and zeroing under 0.1 s, HTTP 0. Every ring
  pass that served packets came right after a sleep (7,604 of 7,604: C1's precondition holds). Semaphores: 254,000
  signals with 693,000 waiters present, so each signal woke 2.7 threads on average (C6). Render Thread 73 % of a core,
  game-main 58 %, emulator 3.9 CPUs.

**The fix: `KYTY_BC5_APR_POSIX`** (default off; `kit/0415-l1b-apr.diff`, tag ls415b). `random`: an APR read is
`open` + `posix_fadvise(POSIX_FADV_RANDOM)` + `pread`, through the same staging buffer and `memcpy` as before.
`direct`: the same, read straight into the guest's pages (no staging buffer, no second copy); a destination the
kernel refuses falls back to the staging copy. Missing files, short reads and reads past the end return what the
old path returned [C]. Not unit-tested: the function needs a file and guest memory; its check is the runs.

| arm (L1b, same session, runs interleaved: c1 x1 y1 c2 y2 x2) | menu load (P2) | Continue to 20 flips/s | P2: from disk | P2: per read | P2: APR busy | to gameplay on the runner's clock |
|---|---|---|---|---|---|---|
| off (c1, c2; with b1-b4: six runs) | 22.0, 21.0 (20.0-22.0, mean 20.9) | 15.5, 16.3 (15.5-22.9, mean 18.0) | 11.0-11.9 GiB | 1.5-1.8 ms | 17.9-20.3 s | 90-96 s |
| `random` (x1, x2) | **16.0, 15.0** | 13.9, 14.9 | 5.07, 5.05 GiB | 0.77, 0.78 ms | 11.0, 11.2 s | 81, 82 s |
| `direct` (y1, y2) | **16.0, 16.0** | 12.6, 13.0 | 5.11, 5.08 GiB | 0.78, 0.80 ms | 11.4, 11.2 s | 81, 79 s |

**Result [M]: the menu load after the movies goes from 20.9 s (six runs, 20.0-22.0) to 15.8 s (four runs,
15.0-16.0), 5.1 s or a quarter less; the save load to a steady 20 flips/s from 18.0 s to 13.6 s (12.6-14.9); the
whole start to gameplay 9-15 s earlier.** The disk now delivers what is asked (5.05-5.11 GiB for 5.1-5.2 asked).
The two modes do not differ in the menu load; `direct` has the two shortest save loads, inside the spread of two
runs each. Frame rate in the 20-30 s of play after the load: 22.9-26.0 flips/s in every arm (no difference).

What the fix does not change, and what binds the menu load now: a read buffer is still outstanding 11 of the 16 s
and waits 340-370 ms in the queue; the device mutex is held 9.2-10.2 s of the 16 s. Series C (below) measures the
other candidates on top of `direct`.

### 7. All 38 runs of the slot: the read fix confirmed, the other candidates measured on top of it

Series C and D ran every other candidate on top of `KYTY_BC5_APR_POSIX=direct`, a closing series two more controls
and one more `random`. Steadier measures than P2's length (whose start and end are cut on one-second flip counts):
the second, from the first counter line, at which 6.0 GiB of APR data had been read; the second of the runner's first
key (the start screen ran at 30 flips/s in two polls); the time from the Continue key to the first of three seconds
with 20 flips or more. `sum0415.py`, data `raw/<tag>-*` [M]:

| arm | runs | 6 GiB read at, s | first key at, s | Continue to 20 flips/s, s |
|---|---|---|---|---|
| off (L1: b1-b4; L1b: c1-c4; c3, c4 at the end of the session) | 8 | 57 53 52 52 53 54 52 52 | 55.1-62.1, mean 57.6 | 15.4-22.9, mean 17.5 |
| `random` (x1-x3) | 3 | 45 45 45 | 49.6 50.6 50.6 | 13.9 14.9 13.9 |
| `direct` (y1-y7) | 7 | 45 45 45 45 45 44 45 | 48.4-51.9, mean 50.3 | 12.1-13.9, mean 12.9 |
| `direct` + `KYTY_BC5_RING_SPIN_US=300` (s1-s4) | 4 | 45 44 45 46 | 49.5 49.7 49.6 51.8 | 13.0 13.9 12.0 13.7 |
| `direct` + `KYTY_BC5_RING_POLL_US=50` (p50, p50b) | 2 | 45 46 | 49.8 51.3 | 12.7 13.1 |
| `direct` + `KYTY_BC5_RING_POLL_US=1000` (p1000) | 1 | 45 | 50.5 | 12.1 |
| `direct` + `KYTY_BC5_EVENT_COALESCE_SAME=1` (e1-e3) | 3 | 45 45 45 | 48.6 50.2 49.4 | 12.9 15.2 12.9 |
| `direct` + `KYTY_BC5_APR_READAHEAD=12` (r12a, r12b) | 2 | 45 45 | 49.5 49.6 | 13.0 13.0 |
| `direct` + `KYTY_BC5_TIMERSLACK_NS=1000` (t1) | 1 | 45 | 49.4 | 13.0 |
| `direct` + `KYTY_BC5_MUTEX_SPIN_US=30` (m1) | 1 | 45 | 51.5 | 13.9 |
| `direct` + `KYTY_BC5_SEMA_TARGETED_WAKE=1` (w1) | 1 | 45 | 49.5 | 13.9 |
| `direct`, lean build (l1) | 1 | 45 | 50.7 | 13.8 |

- **The read fix, 10 runs against 8 [M]: the menu's data is read 7-12 s earlier (44-45 s against 52-57 s), the
  start screen takes its first key 7.3 s earlier in the mean (50.3 against 57.6 s; the ranges do not overlap:
  48.4-51.9 against 55.1-62.1), and the save load reaches 20 flips/s 4.2 s sooner in the mean (13.3 s over the ten
  runs against 17.5 s; ranges 12.1-14.9 against 15.4-22.9).** The controls at the end of the session (c3, c4) read as
  the first ones: no drift. No kernel line, no crash line, the watchdog never acted, in all 38 runs.
- `random` and `direct` do not differ at this resolution (the save load: 13.9-14.9 against 12.1-13.9, three and
  seven runs).
- **No other candidate moved either load by a second** (one to four runs each, every value inside the `direct` runs'
  range): the doorbell poll at 50 or 1,000 µs or with a 300 µs spin (C1), the timer slack (C2), the guest mutex spin
  (C5), exp 0416's targeted semaphore wake (C6) and EOP coalescing, twelve reader threads, the lean build (the
  journal, timing and frame-profile lines). What this says: none of them is on the loads' critical path at a
  resolution of 1-2 s. It says nothing about frame gaps in play, which this route does not measure (30 s of play,
  22.5-26.2 flips/s in every arm).
- The time between "6 GiB read" and a steady 30 flips/s (1-8 s) varies as much inside the `direct` runs as between
  arms; three arms that had 1 s in their first run had 3-8 s in the repeats. Not an effect.
- The title writes its save directory in every run on a writable copy (35 of 35 after b1; the private copy is reset
  from the snapshot before each run). b1's read-only copy did not change its phases against b2-b4.

**What the menu load is made of with the fix on** (run y2, per second, `raw/y2-loadstat.txt`) [M]: nothing is read
while the movies play (5-33 s: the title starts the menu's reads when they end; before them, at 4-7 s, about 1.2 GiB).
Then about 6 s of reads at 400-570 MiB/s, again near the NVMe's limit, now with real bytes; then about 6 s in which
reads are slow with no buffer waiting, the device mutex is held 510-710 ms of every second and its three users wait
220-520 ms of every second for it, while 500-700 MiB a second are imported (pinned). Over the whole phase the mutex
is held 9.2-10.2 s of 16 s, of which the imports are about 1.1 s, direct sync as a whole 3.9 s, the learned windows
1.8 s and the anonymous sync 0.7 s (b1's figures; the rest of the hold is the submission itself: filter, state,
BO list, ioctl).

**Next, in this order** [I]:
1. The device mutex in the second half of the menu load and in the save load: split `dev_hold` by part first (the
   counters above name a third of it), then move the mapping maintenance out of the hold (the lock side of exp
   0412's `DESIGN-device-mutex.md`, agreed with that session on 2026-11-12: 0415 the lock, 0412 the memory policy).
2. The first half is the disk at its limit with the bytes the title asks for. Not ours to fix in the host; listed for
   the maintainer, not asked for: the unpacked game is uncompressed on btrfs, and the same files stored compressed by
   the file system would trade idle CPU threads for disk bytes. Unmeasured.
3. Process start to the first flip (2-3 s: 7.4 GiB imported under one 1.8 s hold) and the reads at 4-7 s.

Private state on the box: `~/bc5-work/exp0415` (3.1 GiB: the tree copy with its two build directories, L1 and L1b
binaries, raw files). Nothing shared was written; BOX-LOCK was held only by `mk0415*.sh` and the runs and is empty.

### 8. The second slot (2026-11-12 21:31-22:08 box time): build L2, the hold by part, the checks of the read fix

**Build L2** = L1b + `kit/0415-l2.diff` (tag ls415c; `mk0415d.sh` stopped at a compile error of the new test, a
volatile increment; `mk0415e.sh` finished it): normal `468f304b`, lean `92b76c16`; L1b kept in `bin-l1b`,
`bin-lean-l1b`. It adds the device mutex's hold in `submit_now` by part and `direct_sync_one` by part to the counters
(13 more causes), and moves the read path of `KYTY_BC5_APR_POSIX` into `src/bc5/apr_posix.hpp` (same behaviour) with
a counter for the fallback. CPU tests on the box [M]: `test0415` 62 of 62 and 32 of 32; **`test0415apr` 33 of 33**:
both modes against a known file (aligned and unaligned offsets and lengths, chunks smaller than the read, a read
across, at and past the end, size 0, a missing file, a directory) and the refused destination: pages mapped
PROT_NONE that only the process's own SIGSEGV handler opens, as the host's lazy pages are; the direct read ends with
every byte in place, the refused part goes through the staging copy with one fault per refused page, and `pread`
alone returns a short count and the flag without a fault.

**The device mutex's hold by part** (runs a1, a2 off; d1, d2 `direct`; `raw/<tag>-loadstat.txt`; seconds, per run) [M]:

| | menu load, off (a1 / a2) | menu load, fix (d1 / d2) | save load, fix (d1 / d2) | 34 s of play, fix (d1 / d2) |
|---|---|---|---|---|
| the phase | 27.3 / 39.2 | 16.0 / 28.4 | 14.1 / 14.0 | 34.0 / 34.0 |
| **mutex held** | 16.0 / 19.1 | **10.7 / 12.7** | 7.6 / 6.9 | **16.7 / 16.5** |
| waited for it (three threads) | 8.8 / 9.9 | 7.3 / 8.0 | 5.2 / 4.7 | 8.6 / 8.4 |
| direct sync, whole | 5.4 / 5.6 | 4.7 / 4.7 | 2.5 / 2.2 | 3.5 / 3.3 |
| - imports | 2.3 / 2.0 | 2.2 / 1.6 | 0.05 / 0.05 | 0.6 / 0.3 |
| - mappings recomputed | 1.3 / 1.3 | 1.2 / 1.2 | 1.05 / 1.0 | 1.0 / 0.95 |
| - view list | 1.2 / 1.2 | 0.95 / 0.9 | 1.1 / 0.9 | 1.3 / 1.4 |
| - merge, drain | 0.2 / 0.2 | 0.2 / 0.2 | 0.1 / 0.1 | 0.4 / 0.15 |
| learned windows | 2.3 / 2.3 | 1.9 / 2.0 | 2.45 / 2.25 | 2.0 / 1.95 |
| anonymous sync | 1.0 / 1.2 | 0.65 / 0.8 | 0.7 / 0.7 | 2.0 / 2.0 |
| the device call | 5.9 / 7.6 | 2.7 / 4.1 | 1.5 / 1.4 | 7.1 / 7.1 |
| - its CS ioctl / prepare / BO list | 3.5 / 1.9 / 0.4 | 1.6 / 0.9 / 0.2 | 0.7 / 0.7 / 0.1 | 3.3 / 3.4 / 0.3 |
| before the device call, hints, probe | 1.0 / 1.8 | 0.6 / 0.75 | 0.35 / 0.3 | 1.5 / 1.65 |

- In the menu load with the fix the mutex is held two thirds of the phase, and **68 % of the hold is mapping
  maintenance** (imports 2.2 s, learned windows 1.9 s, mappings 1.2 s, view list 0.95 s, anonymous sync 0.65 s of
  10.7 s in d1); the submission itself is a quarter.
- The GPU drain before mappings change (`wait_jobs`) is 0.03-0.07 s in every phase: **C3 is refuted as a cost.**
- In play the mutex is held 49 % of the time; the device call is the largest part (7.1 s of 16.6 s), mapping
  maintenance 7.5 s.
- The learned windows by their own journal lines (d1 and d2, the applications over 5 ms, whole run) [M]: 626 and 648
  applications, 6.1 and 6.3 s, of which **4.8 s is `map_window` over the 81 learned entries** against a copy of the
  device's 21,300 mappings, 0.3-0.4 s the copy and sort of those mappings, 0.6 s the guard holes, 0.4 s the fill.
- The view list is rebuilt whenever the guest's ranges change (`direct_views`, one `std::string` and two name
  classifications per range) [C].

**This session was slower than the first one, with and without the fix** [M]: off, 6 GiB read at 57-60 s against
52-54 s and the first key at 64.6 and 67.4 s against 55.1-62.1 s; with the fix 46-50 s against 44-45 s. Not the NAS
archive: its log has 32 lines in the 19 h hour, 8 in the 20 h hour and 6 in the 21 h hour, the last at 21:31. What
differs in the collector's rows: `kcompactd0` used 15.8 and 20.1 s of CPU in the menu loads of a1 and a2 (27 and
39 s) against 3.2-9.1 s in c1-c3 (20-21 s), `kswapd0` about twice as much, and the disk delivered 342-462 MiB/s
against 551-571. The kernel was compacting memory harder (the box had run about fifty emulator starts by then); why
is the memory side's question (exp 0412), noted for it. Inside the session the fix's gain is the same size (57-60
to 46-50 s).

**The checks asked for before the read fix goes shared** [M]:
- **A long second-title run, `direct`, RT on** (`long1`, no perf): 873 s, of which 773 s of play after the load
  (the walk): mean 23.1 flips/s, median 25, 58 seconds under 15 flips and 4 under 5 (no run of this length without
  the fix to compare with), 34.5 GiB of APR data read, the fallback counter 0, lowest available memory 390 MiB, the
  watchdog did not act, no kernel line, no crash line. In the play phase the mutex was held 49 % of the time and
  179 s were waited for it.
- **ASTRO BOT, 120 s from start, no input, a private launcher** (`astro0415c.sh`: private mountpoint, an empty private
  save directory; `as4off`, `as4on`): both ran their 120 s, no kernel line, no crash; 6,511 flips with the switch
  off and 6,874 with `direct`; 1,000 flips reached by 24 s and by 19 s; 11,745 and 11,750 APR reads of 5.5 GiB at
  1.26 and 1.50 ms a read (this title reads through the image mount, so what the switch turns off is the kernel's
  read-ahead on the mounted file; one run each: no harm seen, no gain claimed). The fallback counter 0.
  Three earlier attempts (`as1off`, `as1on`, `as3off`) ended after 6-8 s in the host renderer with the switch off
  and on alike: the shared settings file names the system-module directory under the SHARED mountpoint, so a private
  mountpoint needs that word set after the settings are read. Not a fault of the build.
- Not done: ASTRO BOT with input (a level load), and the second title's `random` mode in a long run.

**Candidates for build L3, against this split** (each default off, with a CPU test where a unit allows; nothing built):
(a) the learned windows applied only where the layout changed, and `map_window` searching the sorted mappings
instead of walking them (4.8 s a run); (b) the view list without a string per range, classified once per name
(0.9-1.4 s per phase); (c) imports prepared outside the hold (2.2 s of the menu load); (d) mappings recomputed only
for changed views (1.0-1.3 s per phase); (e) the device call's prepare (3.4 s per 34 s of play) and (f) the
anonymous sync (2.0 s per 34 s of play): what they recompute per submission. Expected effect, stated before the
build [I]: less waiting of the title's threads on the mutex (8-9 s per 34 s of play, 7-8 s per menu load) and
shorter long frames; the ordinary play frame is GPU-bound (exp 0412 section 26), so not a higher mean frame rate.

### 9. The kit for build L3: three exact fast forms of the mapping maintenance (laptop, 2026-11-12 night; not built on the box, not run)

The maintainer on section 8's split (2026-11-12, through the top session): "Wyuczone okna nie są rozwiązaniem tylko
obejściem. Zleć znalezienie rozwiązania". Replacing the learned windows by a rule is exp 0412's work now; what is
here for them is a stopgap for the lock, labelled as one.

`kit/0415-l3.diff` (against the L2 tree; `tree-l3.md5`), a new header `src/bc5/sync_fast.hpp` (tag ls415d) with the
old and the new form of each piece as pure functions, and their use in `bc5LleAgc.cpp`. Each switch is default off;
`=verify` runs both forms, uses the old one's result where they differ and counts the difference (`fast_diff`).

| switch | what it changes [C] | cost it aims at [M, section 8] | if it were wrong |
|---|---|---|---|
| `KYTY_BC5_WINDOW_FAST` (candidate a, **stopgap**) | `map_window` cut a window's pieces by every device mapping and rebuilt the piece list once per mapping (21,300 mappings x 81 windows per layout change). The pieces lie inside the window, so a mapping that does not touch the window leaves them unchanged and is passed over. No order of the mappings is assumed | 4.8 s a run inside the learned windows' 6.1-6.3 s | a piece mapped twice, or a window's piece left unmapped (the GPU fault the window was learned from) |
| `KYTY_BC5_VMA_FAST` (candidate f, in part) | the anonymous sync asked "is this mapping inside one VMA of its kind" by walking every VMA for each mapping; a binary search when the list is sorted and without overlaps, which is checked on every sync (else the old walk; a reversed range also takes the old walk) | part of the anonymous sync's 2.0 s per 34 s of play (its other part, reading and parsing `/proc/self/maps`, is not touched; the counters do not split the two yet) | a mapping whose VMA is gone stays on the GPU (stale pages), or a valid one is unmapped (a GPU fault) |
| `KYTY_BC5_NAMES_FAST` (candidate b, in part) | the view list classified every range's name against the lazy and the eager list (two walks of string compares per range, on every rebuild); the class is remembered per name (both lists are read once, so a name's class never changes) | part of the view list's 0.9-1.4 s per phase (the per-range `std::string` stays) | a heap imported eagerly or lazily against its list |

CPU test `kit/test0415sync.cpp`, **15 of 15 on the laptop** [M]: 20,000 random windows (mappings in any order,
overlapping each other, zero-sized, on the window's ends, covering it, far away; 3,052 cases with pieces left) with 0
differences between the old and the new piece lists; 720,000 inside-queries on ordered VMA lists (touching, with
gaps, empty entries, both kinds; ranges on every boundary, empty and reversed) with 0 differences; the ordered check
on ordered and disordered lists; the memo. Mutation check [M]: with the window's skip moved by one page the test
reports 6,068 differences, with the VMA walk's stop moved by one it reports 11,560: the test can fail.
Not checked on the laptop: that the edited unit compiles (the box build is its first compile).

Three counters come with it: `learned_apply` (full applications: count and time), `learned_changed` (windows that
mapped something: count and bytes; the number exp 0412 asked for), `fast_diff`.

**Not built, and why.** (c) imports outside the hold and (d) mappings recomputed only for changed views both rewrite
`direct_sync_one`'s import and mapping loops, which exp 0412 is about to change for the windows' replacement (its diff
comes to this experiment first, as agreed); building them against the loop as it is today would be work thrown
away, and both change what reaches the GPU, so they need a design note and review, not a night's edit. (e) the device
call's prepare is the shared backend's filter and state tracker (`backend/src`), its own tests and its own
experiment. The second half of (f), a faster reader of `/proc/self/maps`, waits for a counter that says how much of
the anonymous sync is the read and how much the walk.

**Runs planned for L3** (`mk0415f.sh`, then `run0415d.sh`): each switch once as `verify` (the `fast_diff` counter
must stay 0 over a whole run); then all three on against all off, twice each in ABBA order, `KYTY_BC5_APR_POSIX=direct`
in every run, reading per phase: mutex held and waited, learned windows, anonymous sync, view list, the first key's
time, Continue to 20 flips/s, and in the 34 s of play the flips per second and the seconds under 15 flips. Expected
[I]: the hold shorter by up to the learned windows' part (about 2 s per load phase and per 34 s of play) and a part
of the anonymous sync; no change of the mean frame rate.

### 10. The third slot (2026-11-12 22:34-22:48 box time): build L3 and its A/B

**Build L3** = L2 + `kit/0415-l3.diff` (`mk0415f.sh`): normal `3ef2bbf9`, lean `4fd184da`; L2 kept in `bin-l2`,
`bin-lean-l2`. CPU tests on the box [M]: `test0415` 65 of 65 and 32 of 32, `test0415apr` 33 of 33, `test0415sync` 15
of 15. Five runs, `KYTY_BC5_APR_POSIX=direct` in each, RT on: v1 (the three switches as `verify`), then n1, f1, f2, n2
(all three on / off / off / on). No kernel line, no crash line. `hold0415.py`, `sum0415.py`; data `raw/<tag>-*`.

**Verify** [M]: `fast_diff` = 0 in every phase of v1: over a whole run the fast forms gave what the old forms gave,
for every window, every VMA question and every name.

**On against off** (seconds per phase; two runs each) [M]:

| | menu load, off (f1 / f2) | menu load, on (n1 / n2) | save load, off | save load, on | 33-34 s of play, off | play, on |
|---|---|---|---|---|---|---|
| the phase | 21 / 16 | 22 / 15 | 14 / 15 | 14 / 15 | | |
| mutex held | 12.6 / 9.9 | 13.1 / 9.2 | 7.6 / 7.6 | 7.1 / 7.3 | 17.1 / 16.3 | 15.5 / 14.1 |
| waited for it | 7.2 / 6.4 | 7.4 / 5.9 | 5.5 / 5.4 | 4.9 / 4.9 | 9.1 / 8.5 | 8.0 / 7.1 |
| **learned windows** | 2.2 / 2.0 | **1.8 / 1.4** | 2.6 / 2.6 | **2.1 / 2.1** | 2.1 / 2.2 | **1.3 / 1.2** |
| anonymous sync | 0.9 / 0.7 | 0.9 / 0.6 | 0.7 / 0.7 | 0.7 / 0.7 | 1.9 / 1.9 | 1.9 / 1.8 |
| view list | 1.2 / 1.0 | 1.5 / 1.2 | 1.0 / 1.1 | 1.1 / 1.2 | 1.4 / 1.5 | 1.7 / 1.7 |
| flips/s, seconds under 15 flips | | | | | 21.6 / 22.1, 4 / 2 | 23.2 / 24.1, 2 / 0 |
| `kcompactd0` CPU | 17.9 / 12.8 | 18.7 / 7.7 | 10.8 / 12.6 | 11.4 / 7.5 | 27.1 / 28.2 | 24.1 / 13.4 |
| first key at / Continue to 20 flips/s | 52.2, 52.9 / 14.4, 15.9 | 53.0, 52.4 / 14.5, 15.2 | | | | |

- **`KYTY_BC5_WINDOW_FAST` shortens the learned windows' time by 0.4-0.9 s per phase** (2.0-2.6 s to 1.2-2.1 s; in
  play 2.1-2.2 to 1.2-1.3), not by the 4.8 s a run that the journal's "windows" part suggested: the rest of that
  part is not the piece loop (each window also asks `direct_force` and walks the VMAs; not split further).
- **`KYTY_BC5_VMA_FAST` and `KYTY_BC5_NAMES_FAST` show no effect**: the anonymous sync is 0.6-0.9 and 1.8-1.9 s with
  and without, the view list 1.0-1.7 s with and without. Their targets are not where those two parts spend their
  time (for the anonymous sync that leaves the read and parse of `/proc/self/maps`; for the view list the walk of
  the guest's ranges and a string per range). Exact and harmless, and not worth a default.
- **The loads did not get shorter** (the first key at 52.2-53.0 s in all four runs; Continue to 20 flips/s
  14.4-15.9 s) and the mutex's hold in the loads is inside the runs' spread.
- In play the hold is 1.6-2.2 s shorter in the two "on" runs and the frame rate 1.5-2 flips/s higher, but
  `kcompactd0` used 24.1 and 13.4 s of CPU in those against 27.1 and 28.2 s, so two runs each do not separate the
  switches from the kernel's compaction: no claim about the frame rate.
- **In no run did a learned window map anything** (`learned_changed` = 0 in all 15 phases of the five runs), while
  `learned_apply` did its full work 262-332 times per phase: on this route the whole application re-derives, about
  860 times a run and under the device mutex, that everything is already mapped. Passed to exp 0412, which is
  replacing the windows; it is the measured argument for that work, and for nothing more in this stopgap.

**Verdict of L3.** The stopgap is correct by test and by a verified run and small in effect; the two other fast forms
do nothing measurable. None of the three is proposed for the shared builds. The mapping maintenance's cost is the
repetition of whole-layout work on every change of the guest's ranges (views, mappings, windows, the VMA read), and
that is what a fix has to remove: (d) and the windows' replacement, with exp 0412.

### 11. Part 2, the frame rate: what is known and the measurement's design (laptop, 2026-11-12 night; nothing built or run)

**Known before any new run** [M, with its source]:
- The ordinary play frame is 34.1 ms; the title calls the flip at 22.4 ms and the last fence comes at 33.5 ms;
  something is in flight on the GPU for 30.4 of the 34.1 ms; 148 buffers in 36 submissions a frame (exp 0412 section
  26). The frame is GPU-bound; the host hands buffers on within a millisecond.
- The long frames (16 % of play time there) had an idle GPU and the device mutex held for mapping maintenance (exp
  0412 section 25). This experiment's section 8: the mutex is held 49 % of play, the device call 7.1 s per 34 s
  (prepare 3.4, CS ioctl 3.3), mapping maintenance 7.5 s; `kcompactd0` used 13-28 s of CPU per 34 s of play.
- RT's own GPU work was about 1.5 ms a frame, the CP check 0.8 ms, BVH compaction about 0.7 ms (the 10-31 ranking
  note: journals of different days, not an A/B). The 15-minute run of section 8: mean 23.1 flips/s, 58 of 773
  seconds under 15 flips.
- Not known: what the GPU's 21-30 ms of a frame are made of.

**Question 1: where does the GPU's time of an ordinary frame go?**

*What can be attributed.* The completion thread sees every submission's fence. For submission i of a frame, with
`flush_i` the time it reached the kernel and `fence_i` its completion, the GPU's serial time is
`fence_i - max(flush_i, fence_(i-1) on the same ring)`. A frame has 36 submissions: that is the grain the host has
without reading the title's shaders. To turn submissions into passes each gets a signature the title itself defines:
the ring (GFX or compute), the kind (draw or dispatch buffer), the render-target size and count from the context
registers the buffer sets, the number of draws and dispatches, and the address of its first shader. Frames are then
aligned by signature, not by position. The title's own debug markers, if it ships any in its command buffers, are
recorded as they are (a count per frame decides whether they exist).

*Counter.* `KYTY_BC5_FRAME_STAT=<file>` (default off; tag fs415): for one frame in sixteen, one line per submission
(frame number, ring, kind, signature, dwords from the title and dwords the host added, draws, dispatches, target
size, flush and fence on CLOCK_MONOTONIC, BO count, device prepare / list / CS milliseconds), and one line per frame
(flip called, flip returned, label waits, the drain). No behaviour change; the lines are written by the completion
thread outside the device mutex. A laptop script groups by signature: per pass the median GPU-serial milliseconds,
its share of the frame, its target size, and whether it exists with RT off.

*Arms on a fixed place* (the save's spot after the load, standing still for 60 s, then the walk; four runs each for
the spread; `kcompactd0`'s CPU and available memory per run beside every number):
1. RT on (the baseline) against RT off (the input configuration's switch): RT's passes are the signatures that
   disappear, their GPU time is RT's share by measurement, and what else changes with it.
2. The render-target sizes per pass answer "at what resolution does each pass run" (the title's own dynamic
   resolution and upscale path, read from its registers, not set by us).
3. What the host adds, each with its existing switch or a count: the state prefix it emits per submission (host
   dwords against title dwords per pass; `BC5_DIRECT_ACB_CS_PREFIX`, `ACB_STATE_RESTORE`), the CP coherence check
   (`BC5_DIRECT_CP_COHER_START_DELAY`), the ring dependencies (`BC5_DIRECT_RING_DEPS=dcb`: "every GFX-ring job
   starts after the compute rings' last jobs" serialises the two rings, by the launcher's own comment at the cost of
   "about the one-ring flip rate"), the two-ring wait (4 ms), and the number of submissions a frame (each has a
   fence round trip). For each: the GPU-serial time between submissions with nothing running (the gaps), per frame.
4. The GPU's clock: the governor's range is 1,850-2,150 MHz and the frequency in play has never been read (exp 0412
   section 27). It is the maintainer's setting; listed for him if the per-pass times scale with it, not asked for.

**Question 2: the device call under the mutex in play** (prepare 3.4 s and CS ioctl 3.3 s per 34 s, 27,000
submissions: 0.13 and 0.12 ms each). The device already reports prepare's parts (filter, state tracker, CU, nested,
copy) and the BO count per submission; they go into the same counter file per phase. Two things to read from it:
whether the CS ioctl's time follows the BO count (then the short list is the lever), and which part of prepare
dominates (then that part's cache per layout generation is the candidate). The backend's own tests cover any change
there.

**Question 3: the long frames.** Per frame over 50 ms: was the GPU idle, who held the mutex and in which part
(section 8's counters per second already give the totals; the per-frame line gives the join), `kcompactd0`'s CPU in
that second, major faults. Exp 0412 owns the memory causes; this gives it the per-frame evidence.

**What this design cannot see.** Inside one submission: several passes of the title in one buffer are one number.
The GPU's time is serial time between fences, not a hardware counter. A pass's time includes the kernel's scheduling
of the job.

**Added on the top session's review (2026-11-12 night), to do in the build and the runs:** (a) record the GPU's
clock per run if the governor exposes the frequency it set without root (its sysfs or its journal; not yet looked
for); (b) `BC5_DIRECT_RING_DEPS=dcb` exists for correctness (exp 0323, F385: the BVH build split over two rings hung
11 of 11 runs at about 2 minutes with RT on), so its gap time is measured directly and any relaxation would be default
off with its catcher; (c) with RT off the title may change other passes too, so "the signatures that disappear" count
as RT's share only where the remaining passes keep their target sizes.

**Slot needed:** a build with the counter (incremental, minutes), then about 45 minutes: 4 x RT on, 4 x RT off on the
fixed place (120 s each), then the host-side arms one at a time against a fresh baseline.

### 12. The kit for build L4: stage S1 (change records, verify) and the frame counter (laptop, 2026-11-12 night; not built on the box, not run)

`kit/0415-l4.diff` against the L3 tree (`tree-l4.md5`; `mk0415g.sh`). Both parts default off, neither changes
behaviour.

**S1, `KYTY_BC5_MAP_RECORDS` (tag mr415).**
- Where the layout is written [C]: the direct path's view list is derived only from the range table `VirtualRanges`
  (`kernel/memory.cpp`), and that table has eight mutators (`Add`, `Remove`, `ReleaseReserved`, `ConsumeReserved`,
  `ConsumeReservedSpan`, `Rename`, `Protect`, `SetMemoryType`). Each bumps the generation under the table's mutex;
  each now also notes the span it was called with, in the same critical section, failed calls included. So a reader
  cannot see a change without its record (the review's ordering point), and whatever reaches the view list goes
  through these eight. What this does NOT cover is a writer of the real address space that never tells the range
  table (the review named libAmpr's set-buffer map, guest stacks, save-data and file mmaps): such a mapping is
  invisible to the view list today as well; it is a question of the table against the address space, listed as open,
  not answered by S1.
- `VirtualRanges::SnapshotWithDirty` hands out, under one hold of the mutex, the ranges, their generation and the
  spans since the last call; the log holds 65,536 spans, a full log is reported and counted (`rec_overflow`).
- `src/bc5/map_records.hpp`: `apply` brings a list derived from the ranges up to date for one span: the current
  ranges that overlap or touch the span are read again and replace what the list held in their extent (a mutator
  merges or splits only ranges that overlap or touch its span). Spans can be applied late and in any order against
  one snapshot.
- In the direct path, at every rebuild of the views: the list kept from records is compared with the list built
  from the same snapshot's every range (`map_record` counts comparisons and records, `rec_mismatch` differences,
  with a journal line for the first eight). The rebuilt list is what is used.
- CPU test `kit/test0415rec.cpp`, **10 of 10 on the laptop** [M]: a model of the range table (merging equal
  neighbours, splitting under partial edits) takes 120,000 random add / remove / rename / protect / retype calls;
  the kept list equals the rebuilt list after every call and after each of 20,051 batches (spans applied late,
  shuffled, with spans of calls that changed nothing among them): 0 differences. Mutation check [M]: without the
  "touch" at the span's lower edge 9,838 calls differ, without the widening to the touched ranges' extent 5,697.
- Still open from the review, for the stages that will use the records: the lock order and the bounded wait (point
  2), coalescing (3), the import's file range at publication (4), the private-memory side (5).

**The frame counter, `KYTY_BC5_FRAME_STAT=<file>` (tag fs415).** One line per flip, and for two frames in every
sixteen one line per completed job: kind, ring, the title's dwords, what the filter saw and dropped, BOs listed, the
device's prepare / list / CS milliseconds, queued and fence-seen times, and the GPU's own start and end stamps.
The stamps exist only with the existing diagnostic `BC5_DIRECT_JOB_TS=1` (exp 0124: a GPU timestamp at each job's
start and end, which adds packets to every job; so a run with stamps is compared with one without for its frame
rate before its per-pass numbers are used). The signature is weaker than section 11 planned: kind, ring and the
title's dwords; render-target size and the first shader's address need the buffer parsed and are not in this build.
`frame0415.py` groups the job lines by signature (checked on a synthetic file of known passes [M]).

Also in the diff: a busy stretch of the APR counter shorter than the clock's step was not counted as a stretch
(seen as an intermittent failure of `test0415` on the laptop's coarser clock; 8 of 8 runs pass after the fix).

**Runs planned for L4:** (1) `KYTY_BC5_MAP_RECORDS=verify` over the scripted route twice, one 15-minute run and
ASTRO BOT 120 s: `rec_mismatch` and `rec_overflow` must be 0; the records per phase bound what later stages can
gain. (2) The frame counter standing at the save's spot: twice with `BC5_DIRECT_JOB_TS=1`, twice without (the cost
of the stamps), then RT off twice with stamps.

### 13. The fourth slot (2026-11-12 23:06-23:44 box time): build L4, S1's verify, the first frame-counter runs

**Build L4** = L3 + `kit/0415-l4.diff` (`mk0415g.sh`): normal `9c2dddee`, lean `45be70e6`; L3 kept in `bin-l3`,
`bin-lean-l3`. CPU tests on the box [M]: `test0415` 70 of 70 and 32 of 32, `test0415apr` 33 of 33, `test0415sync` 15
of 15, `test0415rec` 10 of 10. On the top session's review the diff also got a check of its own thread (`bc5-mapschk`,
with `KYTY_BC5_MAP_RECORDS` on): every 5 s the readable VMAs of `/proc/self/maps` inside the guest's span are held
against the range table and bytes that no range covers are counted (`maps_check`, `maps_uncovered`).
All runs `KYTY_BC5_APR_POSIX=direct`, no kernel line, no crash line; the watchdog did not act.

**S1, `KYTY_BC5_MAP_RECORDS=verify`** [M]:

| run | comparisons (view rebuilds) | records applied | mismatches | log full | maps checks | uncovered |
|---|---|---|---|---|---|---|
| g1, g2: the scripted route, 114 s each | 1,021 / 1,048 | 208,063 / 207,357 | 0 / 0 | 0 / 0 | 22 / 22 | 0 bytes |
| lv1: the route and 664 s of play (the walk) | 5,898 | 451,103 | 0 | 0 | 147 | 16,384 bytes in one check |
| as5rec: ASTRO BOT, 120 s from start, no input | 24 | 209 | 0 | 0 | 23 | 0 bytes |

- **The records are complete and in order for the view list**: in 7,991 comparisons over 866,732 records the list
  kept from records equalled the list rebuilt from the same snapshot every time, in both titles.
- **No mapper bypassed the range table in these runs**: 214 checks of `/proc/self/maps`, one of which saw 16 KiB
  uncovered once and not again (a map call caught between its two steps, the case the check's comment names). The
  review's suspects (libAmpr's set-buffer map, guest stacks, save-data and file mmaps) left no stable trace on this
  route or in ASTRO BOT's start. A level load of ASTRO BOT and other places of the second title are not covered.
- The rate: 4,100-5,500 records a second in the two loads, 620-660 a second in play, for about 20 view rebuilds a
  second in the loads and 10 in play: 200-390 records per rebuild in a load. That is the size of the work a later
  stage would do instead of walking 12,500-28,000 ranges.
- In lv1's 664 s of play: mean 23.9 flips/s, median 25, 27 seconds under 15 flips, none under 5.

**The frame counter, standing still at the save's spot for 60 s after the load** (`run0415f.sh` with `R_WALK=0`;
two runs per arm; `raw/f*-frame.txt.gz`, `frame0415.py`) [M]:

| arm | flips/s (two runs) | median frame | GPU busy per sampled frame | GPU idle between the frame's jobs | GPU engines busy (fdinfo) | `kcompactd0` CPU in the 65 s |
|---|---|---|---|---|---|---|
| RT on, `BC5_DIRECT_JOB_TS=1` (ft1, ft2) | 22.5 / 22.9 | 36.0 ms (ft1) | 26.4 ms (ft1) | 5.4 ms (ft1) | 60 / 61 % | 26.9 (in 48 s) / 39.8 s |
| RT on, no stamps (fu1, fu2) | 22.6 / 22.9 | 35.4 ms (fu1) | not measured (no stamps) | | 60 / 60 % | 40.9 / 41.1 s |
| **RT off**, stamps (fo1, fo2) | **22.8 / 23.0** | 35.7 ms (fo1) | 24.6 ms (fo1) | 6.5 ms (fo1) | 57 / 58 % | 36.3 / 27.9 s |

- **The GPU's own stamps cost nothing measurable** (22.5-22.9 against 22.6-22.9 flips/s), so they can be used.
- **RT off does not make the frame shorter at this place**: 22.8-23.0 flips/s against 22.5-22.9, the median frame
  35.7 against 36.0 ms. The GPU's busy time per frame is 1.8 ms lower with RT off (24.6 against 26.4 ms, one run
  each): RT's share of the GPU's work is about 7 % here. RT is not what limits the frame rate at this place. (RT off
  was run only for this measurement.)
- An ordinary frame of 36 ms has the GPU busy 26 ms and idle 5.4-6.5 ms between its 39 jobs; the frame is longer
  than the GPU's work by about 10 ms.
- **Long frames are frequent even standing still**: in ft1's 43 s, 208 of 961 frames are over 50 ms and 12 over
  100 ms (p90 72.6 ms). In these runs the device mutex was held about half the time (31-33 s of 65 s) and its
  users waited 15-16 s for it; `kcompactd0` used 27-41 s of CPU per 65 s, more than half a core throughout.
- **A third of the jobs are tiny compute jobs**: of ft1's 12,493 sampled jobs about 4,000 have 2-28 dwords from the
  title (1-4 packets), and in 934 of them the filter dropped the only packet, so an empty job went to the kernel and
  was waited for (GPU time 0.04 ms, 3.4 ms from queue to fence, 0.07 ms of host work under the mutex each). About
  13 such tiny jobs a frame.
- **The pass table is not usable yet.** The signature of this build (kind, ring, the title's dwords) splits one pass
  into many rows because the dwords vary from frame to frame: no row has more than 3.2 % of the GPU's time. The ring
  column reads -1 in every line (the field is not filled at that point of the completion code). Per-pass GPU time
  needs the signature section 11 planned (render-target size, first shader), which needs the buffer parsed: next
  build.

**Review notes carried in** (the top session, from Codex's review of the read path in L2: no blocking remark).
`KYTY_BC5_APR_POSIX=direct` means reading into the destination memory instead of a staging buffer; it is not
`O_DIRECT`, the page cache is used as before. The gains of section 7 (7.3 s and 4.2 s) are those of that series:
10 runs against 8, RT on, the NAS archive active during most runs.

**What follows for part 2** [I]. At this place the frame is not bound by RT and not by the GPU alone: 26 ms of GPU
work sit in a 36 ms frame, with 5-6 ms of GPU idle between jobs and a fifth of the frames long. The candidates, in
the order the numbers suggest: the idle between jobs (39 jobs a frame, a third of them tiny or empty: fewer and
fuller submissions), the mutex held half the time (the lock-side stages), and the kernel's compaction at the memory
wall (exp 0412). None is built. The GPU's clock per run was not read (not looked for yet).

## Verdict

Part 1, first result. The largest cause of the long loads was ours: every APR read opened its file anew, the
kernel's read-ahead doubled the disk's work and the NVMe ran at its limit for the whole menu load.
`KYTY_BC5_APR_POSIX=random|direct` (default off, private build L1b `55b05fae` / lean `f691fcf5`) brings the start
screen 7.3 s earlier (50.3 against 57.6 s after the start, ten runs against eight) and the save load to 20 flips/s
4.2 s sooner (13.3 against 17.5 s). Eight other candidates showed no effect on the loads at a resolution of 1-2 s.
The read path has its CPU test now (33 of 33); a 15-minute run and an ASTRO BOT start with the switch on were clean
(section 8). Open: the device mutex, held two thirds of the menu load and half of play, 68 % of it mapping
maintenance in the load; the start before the first flip; part 2 (fps). Build L3 (section 10) tried three exact
fast forms of that maintenance: one shortens the learned windows by 0.4-0.9 s per phase, two do nothing, none
shortens a load. In five runs no learned window mapped anything.
Build L4 (section 13): the change records of the guest's range table are complete and in order for the view list
(7,991 comparisons, 0 mismatches, both titles), the base for the lock-side stages. Part 2's first runs: standing
still the frame is 36 ms with 26 ms of GPU work; RT off does not shorten it (RT is about 1.8 ms of GPU time); a fifth
of the frames are long. Per-pass GPU time is not measured yet (the signature was too weak).

## Podsumowanie dla maintainera (stan na 2026-11-12, noc)

Oznaczenia: [zmierzone] = liczba z biegu na boxie; [wniosek] = moja interpretacja.

**Wczytywanie.**
- [zmierzone] Główna przyczyna długiego wczytywania menu po filmikach była w naszym kodzie: każdy odczyt pliku
  otwierał plik od nowa, więc system czytał „na zapas” i dysk dostarczał ponad 2× więcej danych, niż gra prosiła
  (11–12 GiB zamiast 5 GiB), pracując na swoim limicie.
- [zmierzone] Poprawka (przełącznik `KYTY_BC5_APR_POSIX`, domyślnie wyłączony; jest już w main, w buildach wspólnych
  jeszcze nie): ekran startowy gotowy ok. 7 s wcześniej (50,3 s zamiast 57,6 s od startu), wczytanie save'a do
  płynnej gry ok. 4 s krócej (13,3 s zamiast 17,5 s). 10 biegów z poprawką, 8 bez, RT on. Test jednostkowy 33/33,
  bieg 15 min i start ASTRO BOT czyste.
- [zmierzone] Podczas ok. 28 s filmików gra niczego nie czyta; tego po naszej stronie nie skrócimy.
- [zmierzone] Reszta wczytywania: nasza blokada urządzenia jest trzymana przez 2/3 czasu, a 68 % tego to ponowne
  przeliczanie całego układu pamięci przy każdej zmianie. Trzy szybkie poprawki pojedynczych pętli dały mało
  (0,4–0,9 s na fazę) i żadna nie skróciła wczytywania.
- [zmierzone] „Wyuczone okna” w pięciu biegach nie zmapowały niczego, a były przeliczane ok. 860 razy na bieg. To
  potwierdza Twoją ocenę, że to obejście; zastąpienie ich regułą robi sesja pamięci (exp 0412).
- [zmierzone] Pierwszy etap właściwej poprawki (zapis zmian układu pamięci zamiast przeliczania całości) jest
  sprawdzony w trybie porównawczym: 7 991 porównań, 0 różnic, w obu grach. Jeszcze niczego nie przyspiesza.

**FPS.**
- [zmierzone] W miejscu z save'a, stojąc: klatka trwa 36 ms, z czego GPU pracuje 26 ms.
- [zmierzone] **Wyłączenie RT nie zwiększa FPS w tym miejscu** (22,8–23,0 vs 22,5–22,9 klatki/s); RT kosztuje ok.
  1,8 ms pracy GPU na klatkę.
- [zmierzone] Co piąta klatka jest długa (ponad 50 ms) nawet w bezruchu. W tych biegach nasza blokada była trzymana
  przez połowę czasu, a jądro systemu zużywało ponad pół rdzenia na porządkowanie pamięci (`kcompactd0`).
- [zmierzone] Jedna trzecia zadań wysyłanych do GPU jest malutka, a ok. 7 % jest pustych (filtr usuwa jedyny pakiet,
  a zadanie i tak idzie do jądra).
- [wniosek] FPS ogranicza tu nie RT i nie samo GPU, tylko przerwy między zadaniami, nasza blokada i ściana pamięci.
  Rozbicia czasu GPU na przebiegi jeszcze nie ma (pierwsza sygnatura była za słaba).

**Co dalej:** etap 2 poprawki blokady, pomijanie pustych zadań, przypisanie przerw GPU do przyczyn, lepsze
sygnatury przebiegów. Wszystko za przełącznikami, domyślnie wyłączone.

**Nie proszę o zmianę ustawień boxa.** Do Twojej wiadomości: nie odczytałem jeszcze, jaki zegar GPU faktycznie
ustawia governor w grze (zakres 1850–2150 MHz); gra rozpakowana leży na dysku nieskompresowana, a pierwsza połowa
wczytywania menu to dysk na limicie.
