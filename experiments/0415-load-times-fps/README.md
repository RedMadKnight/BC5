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

- `0415-l1.diff` (md5 `3993d0d2`, stored byte-exact: the host tree mixes LF and CRLF files): against the host tree
  with 0413's patch 057e7d07. One new header, `src/bc5/load_stat.hpp` (tag ls415), and edits in ten files
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

Arms 4-8 alternate with a fresh baseline when the first four show a drift over the session.

## Verdict

Open. Part 1's measurement is designed and its kit written and CPU-tested on the laptop; nothing is built on the
box or run.
