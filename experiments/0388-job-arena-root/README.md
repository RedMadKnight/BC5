# 0388 — The root of the job-arena crash, so the workaround can go

**Date.** 2026-10-31. **Branch.** `exp/0388-job-arena-root`, base main `5b22f70`. **Status.** Finished 2026-10-31: the workaround is still needed. See the result at the end.

**Question.** Why does the title's main thread reach a worker-only job (F444–F454) on this host, and can a host fix make the crash go with `JobArenaFix` off?

**The root, read from the code (2026-10-31, the title's own files on the box, nothing kept beyond offsets and names).**

- The job system's count comes from the import at +0x5f20280, slot 0x980b430, NID `dt3C+gjXHKk`, `std::__sce_v2::_Thrd_hardware_concurrency()` (name from the public table in `ps5rs/data/nids.csv`, 5cfb032).
- The title's own `libc.prx` exports it at +0xca580: it returns a global at +0x1978d4. The init at +0xca5c0 fills that global with the population count of the mask from `scePthreadAttrGet` + `scePthreadAttrGetaffinity` on the calling thread.
- So the title's CPU count **is** the host's default thread mask: `0x7f` gives 7, and +0x3cc9117–+0x3cc9223 turns that into 5 workers per entry. Exp 0358's "7, as on the console" came from the host.
- The formula is N = cpus < 7 ? 4 : min(cpus − 2, 8). Thirteen CPUs would give 8 workers.
- The crash job's class is the title's "any thread" mask (read from +0xb064040 at +0x466306c, before the push at +0x46630aa), so the owner's help at +0x3cca7dd takes it by the title's own rules. Its arena lookup at +0x466212d–+0x4662171 gives null on a thread with no worker slots. Who gets the job first is a race between the owner and the workers, and the host gives the title 5 workers.

**Lead still to show.** That more workers end the crash. The mask `0x1fff` comes from KytyPS5 8c01d8e and AnyPS5 27c88a8, neither a console measurement (TODO(verify)).

## Switches of the private build

All default off; off leaves the host as it was. `patch0388.py` applies them to private copies of four units; the pure parts are `backend/include/bc5/cpu_model.hpp`.

| switch | does |
|---|---|
| `KYTY_BC5_0388_CPU_MASK` | the default thread affinity: unset, empty or `0` keep `0x7f`, `1` is `0x1fff`, `0x<hex>` a mask inside it |
| `KYTY_BC5_0388_CURRENT_CPU=1` | `sceKernelGetCurrentCpu` returns the real CPU inside the thread's mask, not 0 |
| `KYTY_BC5_0388_APPLY_AFFINITY=1` | a guest mask narrower than the model's is applied to the host thread |
| `KYTY_BC5_0388_PUSH_SPIN_US=<0..500>` | after a main-thread signal of `JobLoaderSema`, a bounded spin so a worker can go first |
| `KYTY_BC5_0388_TRACE=1` | catcher: logs the first 400 affinity reads, attribute reads and sets, and each host mask applied |

**Tests so far.** The pure parts: 65 checks, 0 failed, on the laptop with clang 22 and a small stand-in for Catch2's macros, not Catch2 itself. `patch0388.py` applied to a tree of `f266548` + main's patch; the patched units have not been compiled.

**Box scripts.** `box0388.sh claim|build|release`, with `build0388.py`, `patch0388.py`, `units.sha256` and `backend/include/bc5/cpu_model.hpp` beside it on the box. `test_box0388.sh` tests the claim and release in a temporary HOME with a stand-in `pgrep`: 14 of 14. The `build` step has had `bash -n` only.

## Test layout, fixed before the runs

- **Build.** Private binary md5 `8801066653a7ce491b9be3f753ec3b30`, `~/bc5-work/exp0388/kyty_emulator`: three patched units linked with the shared normal build's objects (78f25172). The shared binary was unchanged by the build.
- **Runner.** `mk0388run.py` derives `run0388.sh`, `go0388.sh`, `series0388.sh`, `s6n0388.sh`, `check0388.py` and the rest from exp 0386's reviewed runner. Same F464 fight route, same named save copy `saves-live-47aefd45` (private copy per run), same gates, one atomic claim per run, RT on, 180 s.
- **All arms:** `JobArenaFix` off (`KYTY_BC5_JOB_ARENA_FIX=0`), `TRACE=1`, the same binary. The shared `input.cfg` is not changed.

| arm | tags | switches beyond those |
|---|---|---|
| C, control | C1 C2 C3 | none: mask `0x7f`, 5 workers |
| A | A1 A2 A3 | `CPU_MASK=1` |
| B | B1 B2 B3 | `CPU_MASK=1 CURRENT_CPU=1 APPLY_AFFINITY=1` |

Order C1 A1 B1 C2 A2 B2 C3 A3 B3, about 4 min each, 36 min, deadline 52 min. One replacement for a run that does not reach the fight. Arm D (`PUSH_SPIN_US=200`) runs only if A and B both fail.

**Exposure.** `<tag>-jobs.txt` counts the `Job ` threads at 70 s, and the trace shows the mask read. An A or B run with the job count of the control has not tested the candidate and does not count.

**Rule (`check0388.py rule`).**

- Control: at least 2 of 3 crash at eboot+0x3d7eca0, or no conclusion on any arm.
- HOLDS: 3 of 3 NO_CRASH that reached the fight, none at the site, none elsewhere.
- REFUTED: any crash at the site.
- OPEN: anything else. A crash elsewhere is reported on its own and is not a pass.
- A pass here says the crash did not come in 180 s on this route; it is not yet the maintainer's fight, and exp 0359's fix stays until that play.

**Stops.** The first kernel amdgpu line, GPU reset or devcoredump ends the series with no retry. No one touches the pad during the series: exp 0386's runs had mixed input.

## Result (2026-10-31 21:36–22:07, F790–F794)

Runner tests before the runs: 43 of the stand-in checks passed, 0 failed, and they found one real fault (the manifest demanded the shared binary), fixed before the first run. The suite hit its 590 s cap, so its kernel, ssh, signal, recovery, gate, release, storage, rule and series groups did not run on the derived scripts. `check0388.py rule` was tried by hand on sample rows.

Pins at the start: `input.cfg` a5259c60 (JobArenaFix off) and the learned file 5b92521f differ from exp 0386's pins and were re-measured. The route copy is 9347496fbaf30f25.

| arm | runs | at the site | no crash | `Job ` threads |
|---|---|---|---|---|
| C, control, mask `0x7f` | C1 C2 C3 | 3 | 0 | 15 |
| A, mask `0x1fff` | A1 A2 A3 | 3 | 0 | 24 |
| B, A + real CPU + applied affinity | B1 B2 B3 | 3 | 0 | 24 |
| D, spin 200 µs | D1 D2 D3 | 1 (D2) | 2 (D1, D3, 180 s) | 15 |

All 12 reached the fight and all crashes read 0xc at eboot+0x3d7eca0, 110–119 s in, about 10 s after the gameplay inputs. There was no amdgpu kernel line, GPU reset or devcoredump; the only kernel lines were IPv6 MLD. Rule output for C, A and B: control 3 of 3, A REFUTED, B REFUTED. The rule's code does not read D; by the fixed rule D is also REFUTED, since a run crashed at the site.

- **F790.** The title's CPU count is the population count of the host's thread mask, read by the title's `libc.prx` (the root section above). Exp 0358's "7, as on the console" came from the host. Shown in the runs: the mask was read as `0x1fff`, and the job threads rose from 15 to 24, so N rose from 5 to 8.
- **F791.** The worker count is not the crash's cause: 8 workers crash 6 of 6, at the same time as 5 workers. CURRENT_CPU and APPLY_AFFINITY do not change that. Whether `0x1fff` is right for other reasons is still open, as neither source is a console measurement.
- **F792.** With no pad input from a person the crash came 9 of 9 without the spin. The automated route is a fast repro: under 2 min, about 10 s after the inputs.
- **F793.** The 200 µs spin after the owner's push changed the outcome: 1 of 3 crashed against 9 of 9 without it. D differs from C only by this switch. Three runs are few and D has no counter of its own, so the spin's effect is shown only by this difference. Exp 0358's "a spin cannot" does not hold here. This contradicts what I expected before the runs.
- **F794.** The time between the owner's push and its help is the lever, not the number of workers. That fits a worker that needs more time to take the job than the owner does. It is not proven, and the spin is not a fix: it still crashed, and 180 s is not the maintainer's fight.

**Verdict.** No candidate holds; `JobArenaFix` stays. Next: the host's wake-to-run time for a worker after the owner's signal, with a counter on the spin, 500 µs, and a longer window.

## Second cycle, fixed before its build (the maintainer's yes, after water)

**Question.** Does a bounded wait after the owner's push, fixed or until a wait on the semaphore returns, end the crash?

**New in the build.**

| switch | does |
|---|---|
| `KYTY_BC5_0388_PUSH_UNTIL_RETURN_US=<0..500>` | candidate: after a main-thread signal of `JobLoaderSema`, spin until the count of returned waits changes, at most this long |
| `KYTY_BC5_0388_TRACE=1` | adds two catchers: the time from the latest signal to a wait's return in five bands, and the count of push spins and how many saw a wait return in time |

`PUSH_SPIN_US` keeps its meaning. The binary's md5 goes into `pins0388.env` (`NORMAL`, `caede695c1f41c2b322c9a04bfec5bf1`) after `box0388.sh build`.

**Arms.** All with `JobArenaFix` off, `TRACE=1`, RT on, 180 s, the same route and named save copy, one binary.

| arm | tags | switch |
|---|---|---|
| G, control | G1–G3 | none |
| E | E1–E5 | `PUSH_SPIN_US=500` |
| F | F1–F5 | `PUSH_UNTIL_RETURN_US=500` |

Order G1 E1 F1 E2 F2 G2 E3 F3 E4 F4 G3 E5 F5, about 4 min each, about 52 min, deadline 75 min.

**Exposure.** An E or F run needs `push spin` lines in its log, or it has not tested the candidate and does not count.

**Rule.** Control at least 2 of 3 at the site, or no conclusion. HOLDS: 5 of 5 NO_CRASH that reached the fight. REFUTED: any crash at the site. OPEN: anything else. A hold is still a 180 s result on this route, and a spin is a host-side workaround until the reason is shown.

**Limits of the catchers (R11).** Both use global state with no pairing to a signal, a sema generation or a job. A later signal overwrites the time of an earlier one, and an old credit or a return between the snapshot and the signal changes the count. So the bands do not measure one worker's wake-to-run time, and a wait that returned in time does not show that the target job was taken. They support only the effect of the bounded wait on the outcome and the change in those counts. `JobArenaFix` goes only after the maintainer's own fight.

**Local tests so far.** `patch0388.py` applies (5 edits on `semaphore.cpp`), the scripts parse, `check0388.py rule` tried on sample rows, `test_box0388.sh` 14 of 14. The patched units are not compiled until the slot.

## Second cycle's result (2026-10-31 to 11-01, F795–F798)

Binary `caede695c1f41c2b322c9a04bfec5bf1`, order as fixed, with one replacement E1R. The rule's output: control 2 of 3 at the site, arm E OPEN, arm F HOLDS.

| arm | runs | at the site | no crash, reached the fight | not routed | flips/s, 120–170 s |
|---|---|---|---|---|---|
| G, control | 3 | 2 | 1 (G3) | 0 | 33.5 (G3) |
| E, spin 500 µs | 5 + E1R | 0 | 0 | 6 | 16.7 (E3) |
| F, until a wait returns, at most 500 µs | 5 | 0 | 5 | 0 | 27.8–29.1 |

No crash elsewhere, no amdgpu kernel line, GPU reset or devcoredump. Exposure in F: about 570,000 push spins per run, of which about 430,000 saw a wait return within the limit. The job threads stayed at 15.

- **F795.** Arm F held 5 of 5 by the rule fixed before the build. The controls of both cycles crashed 5 of 6.
- **F796.** Arm E did not test the candidate: every run missed the gameplay gate and got its inputs late (P2 at 120–123 s, gameplay 0). A fixed 500 µs on about 270,000 pushes halves the frame rate.
- **F797.** Arm F costs frame rate: about 28–29 flips/s against 33.5 in G3, about 15 %. About 140,000 spins per run ran to the limit, which is up to 70 s of the main thread's 180 s.
- **F798.** G3 ran 180 s without the crash, so the crash is not certain on this route. It is frequent, not fixed; F792's 9 of 9 was without a spin and in the first cycle.

**Limits.** 180 s on one route, after a fight start at about 107 s. By R11 the counts are not paired with a signal or a job, so this shows the effect of the bounded wait on the outcome, not why it works. The cause of the worker's lateness is not shown. Arm F is a host-side timing change with a cost, not a shown root fix.

**Verdict.** Arm F is the first host candidate that holds with `JobArenaFix` off. The workaround stays until the maintainer's own fight passes with F on and the fix off. It is not in any shared build.

## Third cycle, prepared on the laptop only (2026-11-01)

**Question.** Why is a worker late after the owner's push, and is there a cheaper bounded wait than arm F?

**What the host's code shows (read, not run).**

- Thread count: 15 job threads with `0x7f`, 24 with `0x1fff`, of 16 hardware threads. `0x7f` stays the host's default; F791 says more workers do not end the crash.
- Semaphore: every worker entry has its own `JobLoaderSema` (exp 0358 F451, fifo, a worker waits with an 8000 µs timeout). `Signal` marks the waiters it hands the count to, then broadcasts one condvar while it holds the semaphore's mutex. Every waiter wakes, takes that mutex in turn, drops it for the pending-signal dispatch and takes it again. On Linux this is a `std::condition_variable` on a recursive mutex.
- Priorities: guest 300 (main) and 500 (Hi workers) are both nice 0, the same as the host's own threads; guest 733 and above is +5.
- Affinity: guest masks are only stored. No guest thread is pinned unless `APPLY_AFFINITY=1`.

**What earlier experiments measured.** Exp 0358 F453 and the trace after it: a woken Hi worker returned 718–836 µs after its signal, median 1114 µs, 342 µs with the host's 22 threads at nice +5. The targeted wake alone did not stop the crash, and at the push of the crash job the Hi workers were awake, inside the 603-block chunks. Exp 0360 F471 measured about 20 µs of run-queue wait per wake, with the box 28–43 % busy.

**Hypotheses, none shown.**

- H1. The workers are mostly late because they are working, not asleep (F453). A wait on sleeping workers then misses the dangerous case. Arm H tests this: if it crashes while J holds, H1 stands.
- H2. A sleeping worker is late because of the scheduler's choice of core with host threads at the same nice: nice +5 on them cut the median by two thirds. Arm L tests the other side, Hi workers at nice −5.
- H3. Idle cores coming out of a deep state add to the wake time. Each run now keeps the idle-state counts, latencies and the governor. Holding cores awake would be a system setting, so it is not in this build.
- H4. The broadcast and the double mutex pass add to it. F453 says this alone is not the crash; arm K tests the targeted wake and a 20 µs waiter spin on top of J.
- Why the console does not crash stays unknown. F790 removed one reason (the worker count), and no console measurement exists.

**Switches added.** All default off, all on `JobLoaderSema` or the Hi workers only.

| switch | does |
|---|---|
| `KYTY_BC5_0388_PUSH_UNTIL_PAIRED_US=<0..5000>` | wait until every waiter this semaphore marked has returned; no wait if none is marked |
| `KYTY_BC5_0388_PUSH_UNTIL_TARGET_US=<0..5000>` | wait only while this semaphore's entry has an open job of the crash's function (+0x4661e50), read from the title's job table |
| `KYTY_BC5_0388_TARGETED_WAKE=1` | wake only the marked waiters, each on its own condvar (exp 0358's candidate) |
| `KYTY_BC5_0388_WAIT_SPIN_US=<0..500>` | a waiter watches an atomic snapshot of the count, stored under the mutex at every write, for this long before it sleeps |
| `KYTY_BC5_0388_TARGET_TRACE=1` | catcher: count open target jobs on pushes without the target wait; reads the title's job table |
| `KYTY_BC5_0388_WORKER_NICE=<-10..0>` | the nice of guest priority 500 threads |

**Catchers with pairing (R11).** With `TRACE=1`: per semaphore, signal to return of the waiter that signal marked (`marked waiter returned`), and a credit taken without sleeping (`credit taken after signal`), kept apart. Per push of the main thread: `open target jobs` (only with the target wait or `TARGET_TRACE=1`), spins, and spins ended by their condition. The older band stays and is now named unpaired. The credit band is only the time since the semaphore's last signal, so it pairs by semaphore, not by credit.

**Risks in the build.**

- J and K read the title's job table from a host thread while the title changes it, and so does `TARGET_TRACE=1`. No other arm reads it: `TRACE=1` alone does not. A torn read could give a wrong answer for one push; a moved pending list could fault. Hypothesis: the title's list stays mapped.
- Where the job object keeps the function is not read, so J looks through all 0xc0 bytes for the address. `open target jobs` at 0 means J never armed.
- All of this is title-specific. J is a host workaround that knows the title's layout, not a root fix.

**Local tests.** `test_sem0388.py`, 15 of 15: text checks with three mutants, then the patched semaphore built against stand-ins and run on one thread pair. The table is unmapped there, so the two switches that read it die and the seven other cases live. That covers these paths, not concurrency: no sanitizer ran, and the build is not the host's. Pure parts 102 checks, 0 failed (clang 22 with the stand-in for Catch2's macros). The patched `semaphore.cpp` type-checked with stand-ins for the project's headers, up to the POSIX part; not compiled with its real headers, and `pthread.cpp` and `libKernel.cpp` not rechecked. `patch0388.py` applies, the scripts parse, `test0388run.sh positive` 7 of 7 and `test_box0388.sh` 14 of 14, the rule tried on sample rows. Nothing ran on the box.

**Arms, fixed before the build.** All with `JobArenaFix` off, `TRACE=1`, RT on, 180 s, the same route and named save copy, one binary, `NORMAL` pinned after the build.

| arm | runs | tags | switches |
|---|---|---|---|
| G, control | 3 | G4–G6 | none |
| F, reference | 3 | F6–F8 | `PUSH_UNTIL_RETURN_US=500` |
| H | 5 | H1–H5 | `PUSH_UNTIL_PAIRED_US=500` |
| J | 5 | J1–J5 | `PUSH_UNTIL_TARGET_US=2000` |
| K | 3 | K1–K3 | J + `TARGETED_WAKE=1 WAIT_SPIN_US=20` |
| L | 3 | L1–L3 | F + `WORKER_NICE=-5` |

22 runs, mixed in the order in `series0388.sh`, about 80 min, deadline 105 min.

**Rule.**

- Control at least 2 of 3 at the site, or no conclusion.
- HOLDS: every planned run NO_CRASH that reached the fight (5 of 5 for H and J, 3 of 3 for F, K and L). REFUTED: any crash at the site. OPEN: anything else; a crash elsewhere is reported on its own.
- Exposure: a run needs `push spin` lines; H needs spins above 0; J and K need `open target jobs` above 0, or the arm is NO TEST. L needs nice −5 on its `Job Hi` threads in `<tag>-nice.txt`, taken at 70 s; a host that refuses the nice leaves L as NO TEST.
- CHEAPER: an arm that HOLDS and has mean flips/s over 120–170 s of at least 31, against F's 28–29 and the control's 33.5.
- The pick for the maintainer's play: the cheapest arm that HOLDS, J first if tied. If none is cheaper, F.

**The maintainer's play.** `play0388.sh F` or `play0388.sh J` on the box, started by the top session: `JobArenaFix` off, the chosen wait on, RT as in `input.cfg`, the normal launcher and his own saves, no time limit. `input.cfg` is not changed. The script prints the binary's md5 at start: `caede695` is enough for F, and J needs the third build. The 5 of 5 belongs to `caede695`; the third build's F has its own three runs. Pass: he plays through the fight that crashed and on, and closes the game himself, with no access violation and no amdgpu line. Fail: a crash at eboot+0x3d7eca0, and `JobArenaFix` stays. Only that pass can start the removal of exp 0359's fix, and that is his decision.
