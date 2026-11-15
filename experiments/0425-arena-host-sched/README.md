# 0425 — The job-arena race at its source in the host's scheduling model

**Date.** 2026-11-15. **Branch.** `exp/0425-arena-host-sched`, base main `8846a2a0` (patch 0001 `4945ef1b`, the shared
builds' patch). **Status.** Prepared on the laptop. The private build and the runs wait for the top session's GO and
slot. No box access so far.

## Question

The maintainer asked for this on 2026-11-15: "jak naprawisz ten błąd - zrób nowe podejście do arena-fix".

Can a change in the host's model of the console's scheduling end the second title's job-arena crash with `JobArenaFix`
off? The crash is the access violation reading 0xc at eboot+0x3d7eca0 (F444–F454). The goal is a host fix that lets
exp 0359's eboot patch go.

## What is known (read before this experiment)

- **The crash.** The owner (main) thread pushes a pair of jobs into the Hi entry at frame end, signals that entry's
  `JobLoaderSema`, then helps. Its help loop scans from index 0 and takes the first "any thread" job with a block left.
  On a thread with no worker slot that job's arena lookup gives null (F447–F450, exp 0388's root section). On the box
  the owner takes the job within microseconds of the push. The woken workers arrive 0.7–1.4 ms later and find nothing
  left (F453, F454).
- **Ruled out or limited.**
  - The worker count is not the cause: 8 workers crash like 5 (F790, F791).
  - A targeted wake alone did not stop the crash (F452, F453).
  - Host throughput is not the lever (F461, F470, F471).
- **What moved the outcome.** Each of these is a bounded wait after the owner's push (exp 0388):
  - a 200 µs spin (F793);
  - a spin until any wait returns, which costs about 15 % frame rate (F795, F797);
  - J, which knows the title's job table and buys time (F801–F805). The maintainer's fight passed once with J (F806).
    J was removed from the code on 2026-11-02 (F811).
  - H waited only for the sleepers that signal had marked, and still crashed 1 time in 5 (F800). That fits workers
    that were busy at the push, not asleep (F454).
- **The host's code as it is** (patch `4945ef1b` on KytyPlus `f266548`):
  - `KernelSemaPrivate::Signal` (`src/kernel/semaphore.cpp`) hands the count to the waiters it serves. It then calls
    `notify_all` on the semaphore's single `std::condition_variable_any` while it still holds the semaphore's
    recursive mutex. Every waiter wakes and blocks on that mutex. After the signaller unlocks, each waiter takes the
    mutex, drops it for the pending-signal dispatch, and takes it again (`common/threads.cpp`; F451).
  - Every wait also registers in, and unregisters from, one global waiter list under its own mutex.
  - Guest priorities map to nice levels (`Bc5GuestNice`, pthread.cpp): 256–299 → −15, 733 and up → +5, the rest 0.
    So main (300) and the Hi workers (500) run at nice 0, beside the host's own threads.
  - Guest affinity masks are only stored.

## The regression hunt (the maintainer's widening, relayed by the top session)

His words: "nie tylko historia tej - sesja sprawdzi też inne eksperymenty - być może gdzieś jest już odpowiedź -
być może to jakiś nasz błąd w kodzie na którymś wcześniejszym etapie - zauważmy że ten błąd wystąpił dopiero
później - kiedy zaczęliśmy naprawiać patche na wodzie". Done on the laptop from HANDOFF and every experiment README;
the full table is in the session notes (`exp0425-regression-hunt.md`).

**Timeline.**

| when | build | what |
|---|---|---|
| up to 2026-10-25 09:27 | 893f8ab4 and older | no crash at the site in any README, over many hours (exp 0281's 63 min, exp 0296's 19 min) |
| 10-25 ~09:25 | 893f8ab4 | the title stops: "more data must be installed" (F361). The later story was unreachable, the fight included |
| **10-25 10:03** | → **e62a97c6** | **exp 0298's PlayGo answers integrated:** all 100 chunks "local fast", plus one Prefetch; ASTRO BOT's PlayGo module dropped from the pack. This is the only change between the two builds |
| **10-25 10:27:41** | e62a97c6 | **the first crash at the site** (exp 0299 L1), at the save-slot list: 23 min later, in a menu the old builds had passed many times |
| 10-25 21:00, 10-26, 10-28 | | exp 0326, F397, then the fight's 6 of 6 |
| 10-31 to 11-02 | | the water patches (exps 0392–0399): after the crash had already appeared |

- **The site lines before 10-25.** The handler's site lines were silenced until exp 0318 (F380). Even so, no
  unexplained `exit 65` of the second title appears before 10-25: the others have named causes (0034, 0203, 0310,
  0320).
- **The other host changes.** Every change from 10-20 to 10-25 except PlayGo was already in 893f8ab4, which ran
  without the crash, though only up to the PlayGo stop. These were:
  - exp 0180's nice mapping;
  - chains and 30 fps by default;
  - APR's condition-variable wait and read-ahead;
  - the 100-ms wait limit;
  - the held tail;
  - exp 0243's ATRAC9 haptics decode, the only one adding CPU time on the title's own threads (not measured);
  - the tiler pool;
  - the DS4 fixes.
- **Not changed in that window:** the CPU mask, the semaphore, ULT and the time code.
- **No earlier answer.** No experiment outside 0358/0359/0360/0361/0386/0388 addresses the race.

**Reading.** The chronology rules out the later work (the water patches included) as the cause of the first
occurrence. It does not show what PlayGo did. Two readings stay open:

- PlayGo's answers created the race, for example by an answer the console gives differently;
- the answers only exposed a path or changed the title's load, and the race was the host's all along.

No other host change falls in the window. A bisect is not possible: without PlayGo the save cannot reach the fight.
That leaves the PlayGo answers themselves as the first group to test.

## Candidates, simplest first

Each candidate has its own switch, off by default. With every switch unset the private build behaves as the shared
build. The rule for every word: unset, empty or `0` is off, and a value that is not a positive number is off as well.

### P1–P3 — the PlayGo answers (first group; `src/libs/libPlayGo.cpp`)

- **What the PS5 answers is not public.** TODO(verify) on a console for each answer.
- **What the open emulators do.** They all answer as exp 0298 does: "local fast" for every installed chunk, an
  immediate OK for Prefetch, ETA 0. All of it runs synchronously on the calling thread. Sources:
  - AnyPS5 `27c88a8`, `core/libs/prx/libScePlayGo/Export.cpp:180` (GetLocus), `:230` (Prefetch);
  - shadPS4 `60c42b9`, `src/core/libraries/playgo/playgo.cpp:162`, `:290–315`;
  - KytyPS5 `4644c52`, `src/libs/libPlayGo.cpp`.
- **One known difference.** For GetProgress, KytyPlus counts entries and shadPS4 sums the chunk sizes in bytes.
  Exp 0298's trace shows the title never calls it, so it is not an arm.
- **On the console** libScePlayGo is a user library over the system's PlayGo service, so a call may take IPC time.
  The host answers instantly (TODO(verify)).
- **The switches.**
  - **P1** `KYTY_BC5_0425_PLAYGO_LOCUS=slow`: GetLocus answers "local slow" (2) for every valid chunk.
  - **P2** `KYTY_BC5_0425_PLAYGO_PREFETCH_MS=<1..5000>`: Prefetch blocks its caller this long before its OK. The arm
    uses 500.
  - **P3** `KYTY_BC5_0425_PLAYGO_CALL_US=<1..20000>`: every PlayGo call blocks its caller this long. The arm uses 200.
  - The catcher (`KYTY_BC5_0425_CATCH=1`) also logs each PlayGo call kind's first call and every 1000th, with the
    calling thread's name. That shows whether the title calls PlayGo during play, and from which thread.
- **Risk.** P1 may make the title think its data is on slow storage: a "please wait" or a changed streaming pace is
  possible, and a stop shows as NOT_ROUTED. P2 and P3 only delay.
- **Measured by.** The crash outcome. Exposure: the arm's ON line plus a call of the function it changes.

### C1 — a short wake slice for the guest's threads: `KYTY_BC5_0425_WAKE_SLICE_US=<100..3000>`

- **What the PS5 does.** It schedules a title's threads by fixed priority on cores the title has to itself, so a
  woken game thread on a free core runs at once. TODO(verify): there is no console measurement of the wake-to-run
  time. The PS5's kernel is FreeBSD-derived, and the host's own guest priority bands (256 highest, 767 lowest,
  pthread.cpp) are the console's.
- **The host today.**
  - A woken worker is a nice-0 task among the host's nice-0 threads.
  - Under EEVDF a woken task preempts the running one only when its deadline is earlier.
  - The default slice is several milliseconds on 16 CPUs (TODO(verify): the box's `sched_base_slice`).
  - The 0.7–1.4 ms arrivals (F453) are of that order. Exp 0358's helpers at nice +5 cut the median to 342 µs.
- **The change.** At thread start and on Setprio, every guest thread with priority below 733 asks for a 200 µs slice
  through `sched_setattr`. The call keeps the policy and nice it reads first; `sched_runtime` on `SCHED_OTHER` is
  Linux 6.12's custom slice, clamped by the kernel to 0.1–100 ms. With a shorter slice a woken worker can preempt
  the task on its CPU (PREEMPT_SHORT). That includes the owner, if the wake placed the worker on the owner's CPU.
  This is a scheduling attribute of the guest's threads only; nothing title-specific.
- **Risk.**
  - More context switches for the guest's threads.
  - The host's render and GPU threads lose wakeup preemption against the guest's.
  - Unknown: whether an unprivileged `sched_setattr` of `sched_runtime` is accepted on this kernel (7.3).
    The exposure line reads the value back.
  - It does nothing for workers that are busy inside a 603-block chunk at the push (F454).
- **Measured by.**
  - The crash outcome on F464's route with `JobArenaFix` off.
  - Exposure: a `slice:` line per thread with `set rc 0` and the runtime read back, for a `Job Hi` thread.

### C2 — the signaller hands its CPU to the woken waiter: `KYTY_BC5_0425_HANDOFF_US=<1..2000>`

- **What the PS5 does.** TODO(verify): unknown. A FreeBSD wakeup of a thread on another core does not make the waker
  yield. This candidate is not a copy of the console. It is the "wake that hands the CPU to the woken worker" of the
  task.
- **The change.** After a guest `Signal` that readied a waiter, the signaller calls `sched_yield` in a loop until
  every waiter the semaphore has readied so far has resumed, at most 300 µs.
  - It differs from exp 0388's H in three ways:
    - it yields instead of spinning, so a wakee queued on the signaller's own CPU runs at once;
    - it applies to every guest semaphore;
    - it is not keyed by name or by the title's job table.
  - It counts readied and resumed waiters per semaphore. The resumed counter is shared, so the loop never touches a
    semaphore deleted meanwhile.
- **Risk.**
  - A cost on every signal that wakes someone, at most 300 µs. Exp 0388's F waited on every push and cost about 15 %.
  - Like H, it does not cover workers that are busy at the push.
- **Measured by.**
  - The crash outcome.
  - Exposure: `handoff:` lines, with the number ended by the resume and at the bound, and the mean wait.

### C3 — the console's order of a signal: `KYTY_BC5_0425_DIRECT_WAKE=1`

- **What the PS5 does.** A kernel semaphore hands the count to the waiter it wakes, inside the kernel. That waiter
  wakes once, and no other waiter wakes. TODO(verify): the PS5's semaphore internals are not public. AnyPS5
  58295ef07's `Semaphore.cpp`, which exp 0405 cites for its argument checks, is a host model too.
- **The change.**
  - Each waiter sleeps on its own futex word, without the semaphore's lock.
  - `Signal`, `Cancel` and the destructor mark the waiters they serve. After the lock is released, they wake exactly
    those waiters' words: no broadcast, and no wake into a lock the waker still holds.
  - A waiter leaves `Wait` only once its waker has finished with its word, so no wake touches a dead stack frame.
  - The global waiter list is not used on this path.
- **Risk.**
  - A new wait path in a hot primitive.
  - Exp 0358's targeted wake (F452) did not stop the crash. This one also removes the wake into a held lock and the
    second mutex pass.
  - Linux only: off elsewhere.
- **Measured by.**
  - The crash outcome.
  - Exposure: the `C3 direct wake ON` line.

### The catcher: `KYTY_BC5_0425_CATCH=1` (normal build only, compiled out of lean)

- **In the semaphore.** It counts the `Job Hi` waiters a signal has readied (result Ok) that have not yet run again.
  A `Job Hi` waiter is a host thread whose name starts with `Job Hi`, from the guest name.
- **In the job-arena hook.** At each owner help call through exp 0359's hook (thread index −1), the hook reads that
  count. It sums the owner calls, and the crash-type calls whose block function is +0x4661e50, each with and without
  a pending Hi waiter. TODO(verify): that the job's +0x80 holds F449's function. A crashing run with no crash-type
  line would show it does not.
- **With `JobArenaFix` off,** the same hook is installed as a pass-through: no window, and the title's call is
  unchanged. Every arm, the control included, runs the same pass-through.
- **Limits (R11).**
  - The count is global. It is not paired with this job's push or with one semaphore.
  - A pending Hi waiter says that a woken worker had not yet run. It does not say that the worker would have taken
    this job.

## Setup

**Code.** `patch0425.py` applies the candidates and the catcher to private copies of four units of the shared tree:

- `src/kernel/semaphore.cpp`;
- `src/kernel/pthread.cpp`;
- `src/loader/gamePatch.cpp`;
- `src/libs/libPlayGo.cpp`.

Each unit is pinned by sha256 (`units.sha256`, taken from `f266548` + patch `4945ef1b` on the laptop), and every anchor
must occur once. Line endings are kept: two of the units are CRLF.

**Build** (box, under the top's slot). `box0425.sh claim` / `build` / `release`:

- The claim and release are `box0388.sh`'s (R35).
- `build0425.py` is `build0388.py` with this unit list. It takes the shared normal build's compile commands, puts the
  four objects in `~/bc5-work/exp0425/obj`, and relinks into `~/bc5-work/exp0425/kyty_emulator`.
- The build writes `binary.md5` and checks that the seven switch names and the pass-through text are in the binary.
- It checks that the shared binary is unchanged after the build.
- Nothing shared is written, and there is no lean build: the test is on normal, and lean only has to compile the same
  code without the catcher.

**Runs.** One run is `run0425f.sh`. `mk0425.py` derives it from exp 0413's `run0413p.sh` (md5 `fc4fe47c`), the runner
exp 0423 used on the box on 2026-11-15; the base is kept here as `run0413p.orig.sh`. The changes:

- every file lands in `~/bc5-work/exp0425/n`;
- one named snapshot of F464's route save (R45). `MODE=name` makes it once from exp 0358's copy
  `saves-live-47aefd45`, which must read 9347496fbaf30f25 by exp 0388's recipe. Each run resets its private copy from
  it, and the live saves are not read;
- RT on and `JobArenaFix.PPSA03671=off` in the run's private input.cfg, plus `KYTY_BC5_JOB_ARENA_FIX=0` in the
  environment;
- slot 4 (`N_SLOT=4`). At G, exp 0360's 14:50 record's gameplay is queued (`fight1450-play.cmd`, md5 `b0f9ad5c`, exp
  0388's pin). Play time G+120 s;
- the class and exposure in the summary line;
- the Wayland socket looked up in `$XDG_RUNTIME_DIR`.

Unchanged from `run0413p.sh`:

- the atomic claim, or the chain's one lock line;
- the route gate on the journal;
- the kernel-line stop;
- exp 0412's sampler, fuse and watchdog;
- `ulimit -c 0` through the launcher.

**The chain.** `chain0425.sh`, on the box, detached, started by the top session:

- one set per start, 15 runs under one BOX-LOCK line, through exp 0413's `chainlock0417.inc`;
- each run about 4–5 min, about 75 min a set;
- `CHAIN_SET=playgo` first (simplest first), then `CHAIN_SET=sched` in another slot:

  | set | order | arm | runs | words beyond `KYTY_BC5_JOB_ARENA_FIX=0 KYTY_BC5_0425_CATCH=1` |
  |---|---|---|---|---|
  | playgo | C1 L1 F1 K1 L2 F2 K2 C2 L3 F3 K3 C3 L4 F4 K4 | C, control | 3 | none |
  | | | L, P1 | 4 | `KYTY_BC5_0425_PLAYGO_LOCUS=slow` |
  | | | F, P2 | 4 | `KYTY_BC5_0425_PLAYGO_PREFETCH_MS=500` |
  | | | K, P3 | 4 | `KYTY_BC5_0425_PLAYGO_CALL_US=200` |
  | sched | C4 S1 Y1 D1 S2 Y2 D2 C5 S3 Y3 D3 C6 S4 Y4 D4 | C, control | 3 | none |
  | | | S, C1 | 4 | `KYTY_BC5_0425_WAKE_SLICE_US=200` |
  | | | Y, C2 | 4 | `KYTY_BC5_0425_HANDOFF_US=300` |
  | | | D, C3 | 4 | `KYTY_BC5_0425_DIRECT_WAKE=1` |

- **Stops (R55).**
  - a kernel GPU line (R54's pattern, stack frames excluded);
  - a real pad key (R51; evtest on the joystick devices);
  - any class other than TARGET, NO_CRASH or NOT_ROUTED;
  - a second NOT_ROUTED (one replacement in the series);
  - a `STOP` file beside the chain, read before each run.
- **The known crash.** The crash at the site is what the arms measure. It continues the chain only with
  `CHAIN_TARGET_OK=1`, which the top session sets by name when it starts the chain. That is R55's named exception.
  Without it, the first TARGET stops the chain.

## Rule, fixed before the runs (`check0425.py rule`)

- **Classes.**
  - **TARGET:** the play log has `Access violation: Read [000000000000000c]` and either
    `off=0000000003d7eca0, module=eboot.bin` or `kyty_exception_handler: 0000000903d7eca0`.
  - **NO_CRASH:** G+120 s was reached with no crash text.
  - **CRASH_OTHER, KERNEL, WALL** (the watchdog or the fuse), **SETUP, NOT_ROUTED** as named.
- **Counted runs.** A run counts only if its log shows the fix off, the pass-through hook and the catcher on.
- **Control.** At least 2 of 3 at the site, or **no conclusion** on any arm.
- **Per arm.**
  - **HOLDS:** 4 of 4 NO_CRASH, with the arm's exposure in every run.
  - **REFUTED:** any TARGET.
  - **NO TEST:** a run without its exposure.
  - **OPEN:** anything else. A missing or unreadable count is unknown, not 0 (R19).
  - The exposure per arm:
    - L needs `P1 locus SLOW ON` and a GetLocus call line;
    - F needs `P2 prefetch delay ON` and a Prefetch call line;
    - K needs `P3 call cost ON` and any PlayGo call line;
    - S needs a `Job Hi` slice line with `set rc 0`;
    - Y needs `handoff:` lines;
    - D needs `C3 direct wake ON`.
  - Each set is judged on its own rows, against its own three controls.
- **What a HOLD means.**
  - (2/9)^4 ≈ 0.002 is only an illustration. It holds if p were exactly the past 7 of 9 (F799) and the runs were
    independent; it is not an estimate of the chance from that small history (R13).
  - Fisher's exact test of 4 clean of 4 against the history's 2 clean of 9 gives 15/715 ≈ 0.021 (one-sided). That
    assumes the runs are exchangeable, which they are not quite: other builds, other days.
  - Either way, a HOLD is a pointer, not the mechanism.
  - It is 120 s on one scripted route, not the maintainer's fight.
  - `JobArenaFix` stays until his own fight passes with the candidate on and the fix off, and he decides.
- **Cost.** Flips/s over G..G+120 are reported per run, against the control's clean runs if there are any. This is
  descriptive only: no cost claim from these few runs (R13).

## Commands (for the top session, in its slot)

```bash
# copy to the box, after the GO and with the box free
scp patch0425.py build0425.py units.sha256 box0425.sh run0425f.sh chain0425.sh check0425.py bc250:bc5-work/exp0425/
ssh bc250 'cd ~/bc5-work/exp0425 && bash box0425.sh claim "exp 0425 private build" 20 && bash box0425.sh build; MODE=name bash run0425f.sh; bash box0425.sh release'
# a set, detached; CHAIN_TARGET_OK=1 is the top's named exception for the known crash; playgo first, sched in another slot
ssh -n bc250 'cd ~/bc5-work/exp0425 && (CHAIN_SET=playgo CHAIN_TARGET_OK=1 setsid nohup bash chain0425.sh > chain0425-playgo.out 2>&1 < /dev/null &)'
# stop between runs
ssh bc250 'touch ~/bc5-work/exp0425/STOP'
```

The laptop streams the kernel log for the whole chain:

```bash
ssh bc250 journalctl -k -f -n 0 -o short-precise | tee raw/kern-0425.txt
```

## Local tests (laptop, 2026-11-15)

- **Syntax** with Visual Studio 18's clang++ 22 (msvc target, `-fsyntax-only -std=c++20 -Wall -Wextra`), in the
  tree's Windows configuration with fmt and magic_enum from `refs/`:
  - `semaphore.cpp` patched, normal and `-DBC5_LEAN=1`: the same single warning as the unpatched unit (an unused
    `opt` parameter in `KernelCreateSema`).
  - `libPlayGo.cpp` patched, normal and lean: no warning, as unpatched.
  - Not covered: `gamePatch.cpp` needs `nlohmann/json`, which is not on this laptop. `pthread.cpp`'s C1 block sits
    under the Linux platform branch, which this configuration does not compile.
  - Both of those are covered by the block builds in `test0425.py`. The real Linux compile is the box's build.
- **`test0425.py`: 85 of 85 passed**, with 5 repetitions per semaphore case:
  - the PlayGo block: all 18 entries counted, P1 in GetLocus, P2 in Prefetch after its checks. The block itself was
    built and run in normal and lean under each word: the clamps, `fast` not taken as `slow`, P3's waits measured,
    the catcher's first-call line, lean silent;
  - text checks with mutants: every "ready" goes through `Bc5Ready`, C3's wake comes after the lock, a waiter waits
    for its waker, the catcher is out of lean;
  - the patched `KernelSemaPrivate`, with its Linux paths on and a futex stand-in, built `-Wall -Wextra -Werror` in
    normal and lean. It ran ping-pong with 4 `Job Hi` waiters (20,000 paced signals), timeouts racing signals with
    the count conserved, Cancel, and delete with blocked waiters. Every case ran with the switches off, C2, C3 and
    C2+C3, each under a 60 s cap;
  - C1's block, with a stand-in `sched_getattr`/`sched_setattr`: unset, `0` and `abc` are off; the clamp; the band;
    FIFO left alone; BATCH and nice kept; the lean build silent;
  - the catcher's block, called with stand-ins: the counts and lines.
- **Limits of these tests.**
  - The first run found 9 failures, all in the test itself: it asked the lean build for exposure lines, which it
    has none of by design. A second run found 1 failure, again a test flaw: an unpaced signaller never let the
    waiters sleep, so C2 had nothing to hand off.
  - No ThreadSanitizer on this laptop. Futex and sched_setattr are stand-ins, so the kernel's behaviour is not
    tested here.
- **`test_box0425.sh`: 11 of 11** on stand-ins (a temporary HOME, a fake compile; the real `patch0425.py` on the four
  units):
  - the claim and release refusals: no lock, a foreign line, an emulator running, a second claim;
  - the build's pins, patch, string gate and `binary.md5`;
  - the earlier binary kept aside;
  - a unit off its pin stops the build.
- **`test_chain0425.sh`: the chain dry run on stand-ins.** RESULT_PENDING.

## Result

Not run. Waiting for the top session's GO and slot.

## Verdict

None yet.
