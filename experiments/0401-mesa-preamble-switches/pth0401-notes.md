# Experiment 0401 series e4: AnyPS5's rwlock and condvar fixes against our pthread code (KYTY_BC5_PTHREAD_FIXES)

Exp 0402's survey, Top 10 row 3 and its libkernel row: AnyPS5's fixes after `7ba97f4` — `4ed0f9f91`,
`372f0f6c6`, `83b1015c4`, `45a8b80a5` and `16375634e` (boykopovar/AnyPS5, GPL-2.0-only; clone at HEAD `4f41f4c37`).
Correction to the survey's path: the first four are in
`core/libs/prx/libkernel/SyncOnAddress/src/SyncOnAddress.cpp` (AnyPS5's `_umtx_op`, the FreeBSD kernel's lock operation
that guest-side libthr code calls). Only `16375634e` is in `core/libs/prx/libkernel/Pthread` (`src/Cond.cpp`, `src/Mutex.cpp`).

Our code is the shared builds' tree: KytyPlus `f266548` + patch 0001, `src/kernel/pthread.cpp` md5
`11cef59e0ff15f650eba98bb11f91bce` (CRLF line endings), `pthread.h` `6b9e6414…`, `src/libs/libKernel.cpp` `3bf94a61…`.
The line numbers below are from that `pthread.cpp`.

## Our design in one paragraph

Each rwlock, mutex and condition variable is a `std::mutex m` plus a `std::condition_variable cv` plus plain fields,
and every field is read and changed only under `m` (`PthreadRwlockPrivate` 479-494, `PthreadMutexPrivate` 397-406,
`PthreadCondPrivate` 508-516). Waiters check their predicate under `m` and sleep in `cv.wait_for` with a 10 ms poll
(`SIGNAL_APC_POLL_MICROS`), so even a lost notify costs at most 10 ms (rwlock 2604-2611, mutex 1399-1406, condvar
3127-3145 / 3215-3233 / 3296-3313). There is no `_umtx_op` anywhere in `src/` (no `umtx` in a grep of the tree). The
title's rwlocks reach `RwlockLockCooperative` (2546-2616), `PthreadRwlockTryrdlock` (2659-2689) and `PthreadRwlockUnlock`
(2724-2761) through the sce exports (libKernel.cpp 3600-3616, exp 0327's timed ones at 3609-3611) and the posix ones
(F408; libKernel.cpp 2456-2460, 2499-2500, 3603-3607 → pthread.cpp 4660-4694, which call the same functions).

## Per-commit verdicts

| Commit | AnyPS5 defect | Verdict | Evidence in our tree |
|---|---|---|---|
| `4ed0f9f91` (a) | RwlockLock decided "not free" and then set the waiter bit unconditionally; an unlock between the two woke nobody | **not applicable** | 2562-2593: the decision and the writer registration (`waiting_writers++`, 2582-2585) happen under `rwlock->m`; unlock changes state and `notify_all`s under the same lock (2744-2756); the wait is `cv.wait_for` under `m` with a 10 ms poll (2608/2610) |
| `4ed0f9f91` (b) | ConditionWait queued a stack waiter, then MutexUnlock threw for a priority-protected umutex and unwound past the cleanup: a dangling waiter | **not applicable** | `NativeMutexUnlock` (1467-1495) returns codes and never throws (`EXIT_*` ends the process, it does not unwind); a failed unlock is cleaned up at once (3113-3116, 3205-3208, 3284-3287); protocol 2 is only stored (1833-1856), lock/unlock ignore it; the waiter entry is the long-lived `Pthread`, not a stack object (518-524) |
| `372f0f6c6` | the last waiter cleared the waiter bit outside the bucket lock and could erase a new waiter's bit | **not applicable** | there is no waiter bit: `waiting_writers` is a counter changed only under `rwlock->m`, once per call through `writer_wait_registered` (2564-2569, 2582-2585, undone at 2573/2577/2599) |
| `83b1015c4` | the same cleanup made atomic with the predicate under the bucket mutex | **not applicable** (our design is what this commit converges to) | all bookkeeping and the predicate already run under the one `rwlock->m` (2562) |
| `45a8b80a5` | `_umtx_op` RW_RDLOCK ignored `URWLOCK_PREFER_READER` passed per call; libthr passes it while the thread holds any read lock | **missing, in adapted form** | the code path (`_umtx_op`) does not exist, but the rule it carries does not hold here: our reader admission lets only a reader *of the same lock* past waiting writers (`already_reader`, 2587-2593 and 2680-2685) |
| `16375634e` | the condvar wait relocked its mutex directly instead of through scePthreadMutexLock's spin-and-yield path | **not applicable** | our condvar relock is `NativeMutexLockRecurse` → `NativeMutexLock` (3152, 3239, 3317 → 1497-1506 → 1373), the very path `PthreadMutexLock` takes (1958); neither spins (no spin/yield counts in `PthreadMutexPrivate`, no Setspinloops export), so the two paths cannot differ |

Reasons, one paragraph each:

- **4ed0f9f91 (a)**. AnyPS5's urwlock keeps its state in one word changed with CAS outside any lock, and the waiter bit
  told unlock whom to wake; the window between the freedom check and `fetch_or` lost wake-ups. Ours has no lock-free
  state: the freedom check, the registration as a waiting writer and the sleep (`wait_for` releases `m` atomically) are
  one critical section with respect to unlock, which needs `m` to change the state and notifies while holding it.
  A missed notify cannot happen; if one did, the 10 ms poll would recover it.
- **4ed0f9f91 (b)**. Nothing between `CondAddWaiter` (under `cond->m`) and the check of `NativeMutexUnlock`'s result can
  throw or unwind: the mutex code returns `EPERM` for a non-owner (and the owner was checked at 3102/3194/3273), and the
  priority protocol has no special path. Case 7 of the test checks it: waits with an unowned mutex return `EPERM`, a
  wait on a protocol-2 mutex is an ordinary wait, and one later signal reaches the one real waiter.
- **372f0f6c6, 83b1015c4**. Both repair the cleanup of a shared waiter bit by the last waiter. Our writer registration is a
  per-call flag plus a counter, both under `m`; a timed-out writer unregisters itself under `m` before returning
  (2599). Case 10 checks that 480 writer time-outs leave no mark (a thread holding nothing reads at once afterwards).
- **45a8b80a5**. FreeBSD 11.4 libthr (`lib/libthr/thread/thr_rwlock.c` @ `release/11.4.0`, read 2026-11-03):
  `rwlock_rdlock_common` and `_pthread_rwlock_tryrdlock` set `flags = URWLOCK_PREFER_READER` when
  `curthread->rdlock_count` is not 0 and count up on success; `_pthread_rwlock_unlock` counts down after a read unlock;
  `thr_umtx.h` `_thr_rwlock_tryrdlock` then refuses the reader only for `URWLOCK_WRITE_OWNER`, not for
  `URWLOCK_WRITE_WAITERS`. AnyPS5's commit makes its `_umtx_op` honour that per-call flag "as the console does", and its
  own HLE rwlocks keep the same count (`core/libs/prx/libkernel/Pthread/src/Rwlock.cpp` @ `4f41f4c37`, `readLocksHeld`,
  lines 44-57 and 166). Ours honours it only for the same lock, so a thread that holds a read lock on A waits for B's
  queued writer: two such readers, each behind the other lock's writer, deadlock for ever (case 3 shows it with timed
  locks). That is the one thing ported.
- **16375634e**. AnyPS5's commit aligns its condvar relock with its mutex lock, which spins (2000 for adaptive mutexes) and
  yields before it blocks. In ours both paths are the same function and neither spins; the commit's defect (two paths
  that disagree) cannot occur. Adding a spin phase would be a mutex performance change on both paths at once, not this
  fix; not done.

## What was ported (one switch)

`mkpth0401.py` edits `src/kernel/pthread.cpp` only. One switch, `KYTY_BC5_PTHREAD_FIXES` (only one fix is ported, so one
switch): on when set, non-empty and not `"0"`, read once in a function-local static; stderr line at first use:
`[bc5] exp 0401: pthread fixes on (rwlock: a thread that holds any read lock reads past waiting writers, AnyPS5 45a8b80a5, libthr rdlock_count)`
or `[bc5] exp 0401: pthread fixes off (rwlock: today's rule, only a reader of the same lock reads past waiting writers)`.
First use is the first read lock of the run (a run that never takes a read lock prints nothing).

- A block before `RwlockFindReader`: the comment naming exp 0401 series e4, AnyPS5's path and commit, libthr's source,
  GPL-2.0-only and the switch; `Bc5PthreadFixesOn()`, a `static thread_local uint32_t g_bc5_read_locks_held`,
  `Bc5HoldsAReadLock()` (switch on and count not 0), `Bc5ReadLockTaken()`, `Bc5ReadLockReleased()` (both no-ops off).
- `RwlockLockCooperative` read side and `PthreadRwlockTryrdlock`: `already_reader = FindReader(...) != nullptr ||
  Bc5HoldsAReadLock()`; `Bc5ReadLockTaken()` after each `RwlockAddReader`.
- `PthreadRwlockUnlock`: `Bc5ReadLockReleased()` after a successful `RwlockRemoveReader` (an `EPERM` unlock does not count
  down, as in libthr).
- `#include <cstdlib>` for `std::getenv`.
- Adapted, not copied: no line of AnyPS5's code is taken (their `_umtx_op` has no counterpart here); the count follows
  their `readLocksHeld` and libthr's `rdlock_count`. A write owner still blocks such a reader (case 10).

Off: `Bc5HoldsAReadLock()` is false and the two counters do nothing, so admission is today's expression with today's value.
Checked mechanically: `scratchpad/offpath.py` removes the switch-guarded additions from the output and gets the input back
byte for byte. Bracket counts change by +7/+7 `{}`, +18/+18 `()`, +2/+2 `[]` (the unit itself does not balance on its
own because of `#if` alternatives and inline asm, so the delta is what was checked).

## Outputs on the shared builds' tree (laptop, 2026-11-03)

```
mkpth0401.py <...>/e4/full <...>/scratchpad/pth0401-out
0363847bd540883467dee22797475031  src/kernel/pthread.cpp
```

Input md5 `11cef59e0ff15f650eba98bb11f91bce` (CRLF kept). An LF copy of the input gives
`25bfd5c9d95316f6e9bacd85129008b8` (same text, LF), with a stderr note that the input is not the shared copy. A second
run on the output is refused ("pthread.cpp has the edit already").

## The test, pth0401.cpp

One program, run twice in the build container: `KYTY_BC5_PTHREAD_FIXES=1 ./pth0401` and `KYTY_BC5_PTHREAD_FIXES=0 ./pth0401`
(unset is off too). It reads the switch itself. One line per case, then exactly `pth0401: on 10 of 10; end` or
`pth0401: off 10 of 10; end`; exit 0 only then (1 if a case failed, 2 on a setup failure, 3 from the watchdog, which
prints `pth0401: FAIL watchdog: case "<name>" still running after 50 s (a hang); ...`). Expected time: a few seconds;
every wait has a bound (host flags 10 s, lock failsafes 2-5 s, watchdog 50 s). Also check stderr for the unit's
`[bc5] exp 0401: pthread fixes on|off (` line matching the run.

| # | Case | On | Off |
|---|---|---|---|
| 1 | same-lock recursion past a queued writer: the reader's second timed rdlock OK; a thread holding nothing gets EBUSY; the writer gets the lock after the last read unlock | same | same |
| 2 | a thread holding 2 read locks on A (and after an EPERM unlock of C) tries B while B's writer is queued: try, timed 50 ms; then holding 1; then none | OK, OK, OK, EBUSY | EBUSY, ETIMEDOUT, EBUSY, EBUSY (today) |
| 3 | two readers, each holding one lock and reading the other while that lock's writer is queued (timed 300 ms; nobody releases before both tried) | both OK | both ETIMEDOUT: "cross-lock cycle seen 1 time(s)", today's behaviour, not a failure |
| 4 | 8 threads x 2000 rounds over B and C: wrlock, timed wrlock, C wrlock, nested C→B rdlock, timed rdlock, try rd/wr, rdlock, nested timed C→B; checks exclusion (atomic counters + a plain counter that must equal the writes), no error, no 2 s failsafe time-out, both locks free after | same | same |
| 5 | condvar ring, 4 threads x 200 turns, broadcast each turn, mutex types 1, 2 (held twice), 4 x untimed / timed (10 s) waits: 800 turns, no overlap, no error | same | same |
| 6 | 2 producers x 3000 items, signal under the mutex; 3 consumers in 2 ms timed waits: every item once, sum right, exclusion | same | same |
| 7 | waits with an unowned mutex return EPERM (timed and untimed); a wait on a protocol-2 (PRIO_PROTECT) mutex times out and returns holding it; then one signal wakes the one real waiter (< 1 s) | same | same |
| 8 | broadcast wakes all 8 waiters (4 untimed, 4 timed 5 s), none times out, < 1 s | same | same |
| 9 | timed waits: 30 ms relative (≥ 29 ms), 0, absolute realtime + 30 ms (≥ 20 ms): ETIMEDOUT with the mutex held | same | same |
| 10 | 8 writers x 60 timed wrlocks (1-5 ms) behind a held read lock, 3 probes alongside: 480 time-outs, none acquired; afterwards a thread holding nothing reads at once; behind a write owner a reader and a reader holding another lock both time out; then a writer gets the lock | same | same |

Which races show where: the cross-lock cycle (case 3) shows only with the switch **off** (that is today's behaviour; the
case records it and passes); with the switch **on** it does not form. The lost-wake-up and waiter-cleanup races of
`4ed0f9f91`, `372f0f6c6` and `83b1015c4`, and the condvar relock of `16375634e`, cannot form in our design: cases 4-10
are their regression checks and must pass identically on and off.

### How it is built

With box0401's `build0401.py` (series e4 options; it already parses `--like src/kernel/pthread.cpp`, test0401.py
line 565): the private unit `src/kernel/pthread.cpp=<mkpth0401 out dir>/src/kernel/pthread.cpp` and the gate
`--gate pth0401.cpp <out>/pth0401 --like src/kernel/pthread.cpp`. That is: `pth0401.cpp` compiled with
`src/kernel/pthread.cpp`'s compile command from the shared normal build's compdb (`-MD/-MT/-MF` dropped, `-c` and `-o`
replaced), linked with the emulator's link line with `main.cpp.o` taken out, the gate object in its place and the private
objects swapped in (the private `pthread.cpp.o` among them, together with whatever other private units the series e4
build carries; the test uses only the pthread code). The same private `pthread.cpp.o` goes into the private emulator,
where the switch is off unless set.

### Runtime state the test sets up (and its limits)

- `Common::ThreadsSubsystem` and `Libs::LibKernel::PthreadSubsystem` are initialised on a helper thread that then ends:
  the constructors check `IsMainThread()`, and the Pthread init turns `PRINT_NAME` on for its own thread only (a
  `thread_local`), where `PRINT_NAME` would call `Log::GetDirection()`, which exits when the log subsystem is not
  initialised. No thread that calls the pthread code has `PRINT_NAME` on.
- `Log::Bc5SetLogging(false)`: `LOGF` stays off stdout.
- Every thread that calls the pthread code first calls `PthreadInitSelfForMainThread()` (a `PthreadPrivate` with its host
  stack; leaked on purpose). `g_pthread_main` ends up as the last such thread; nothing the test calls reads it.
- The Pthread init starts KytyPlus's detached `FreeDetachedThreads` thread (sleeps 10 s per round); the test ends with
  `_exit` so no static destructor runs beside it.
- No guest code, no guest signals or exception handlers, no static-initialised locks (all objects come from the Init calls,
  so `CreateObject` never reaches the runtime linker).
- Not compiled on the laptop (no compiler); written against the tree's declarations (`pthread.h`, `libs/errno.h`,
  `common/threads.h`, `common/logging/log.h`, `common/subsystems.h`). The first box build is its first compile; the shared
  flags are clang `-Wall -fno-rtti -fno-exceptions` (utils.cmake), probably `-Werror`.

## Doubts

1. **The 18:04 symptom does not fit these defects.** Our waits sleep in 10 ms polls: a lost wake-up costs ≤ 10 ms, and a
   cross-lock deadlock (case 3, off) leaves the threads idle in `wait_for`, not at 100 % user CPU. Two threads at 100 %
   user CPU with the GPU idle look like guest-side spinning (on an atomic, a label, a try-lock or `sched_yield` loop), or a
   host loop outside this code. Stacks (`perf top -t`, `gdb -p ... thread apply all bt`) are what decides; this port is
   not expected to fix 18:04.
2. **The console rule's provenance**: libthr 11.4 was read (fetched from freebsd-src `release/11.4.0` on 2026-11-03), and
   AnyPS5 states the console does the same (`45a8b80a5`'s subject; their HLE `readLocksHeld`). We have not measured a PS5.
3. **Behaviour change with the switch on**: a thread that holds any read lock now enters past queued writers on other
   locks. If the title keeps a long-lived read lock on one thread and takes hot read locks on it, writers of those locks
   may wait longer (the console would do the same, if 2. holds).
4. The count is per host thread (`thread_local`), which here is the guest thread. On Windows a guest exception handler may
   run on a helper thread under `PthreadSwapSelfForSignal` (libKernel.cpp 1139-1144); its read locks would count there.
   Linux does not take that path.
5. Unchanged and different from libthr: a write owner may take a read lock on its own lock here (2590,
   `rwlock->writer == self`); libthr would block. Not touched.
6. A related hazard that none of the five commits covers: a guest exception handler dispatched inside a wait
   (`KernelDispatchPendingSignalForCurrentThread`, 2614, 3141-3143, 3229-3231, 3299-3301) that never returns
   (`PthreadExit` jumps stacks without unwinding, 3826-3856) would leave the thread queued on the condvar (a later
   signal then goes to it and is lost, or touches a freed thread) or leave `waiting_writers` raised (readers then wait
   for ever). No evidence the title does that; not ported, not tested.
7. Unrelated, seen while reading: `PthreadRwlockTimedrdlock` / `Timedwrlock` (2635-2657) do not create a statically
   initialised lock (`EXIT_NOT_IMPLEMENTED(*rwlock == nullptr)`), unlike `Rdlock`/`Wrlock`/`Try*` (exp 0336).
8. The title does not import `_umtx_op` on the routes measured (F408: of 1,935 imports only ten NpCppWebApi NIDs stay
   stubs), so the four SyncOnAddress commits have no entry point here even in principle.
