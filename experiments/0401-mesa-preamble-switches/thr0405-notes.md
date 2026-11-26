# Experiment 0401 series e5: exp 0405's thread synchronisation and semaphore ports (tag `thr`)

Exp 0405's top-32 rows 6 (R2 KK06), 10 (R2 KK03 + SK11), 28 (R1 #7, #8 with R2 SK09) and 31 (R1 #14), plus the extra
R2 KK07, ported into `src/kernel/pthread.cpp` and `src/kernel/semaphore.cpp` behind two switches, default off. Specs:
`bc5-0405/experiments/0405-port-research-all-titles/README.md` (top-32 table), `raw/r2-kyty-sharpemu.md` §4.1/§5
(items 5, 6, 31, 32), `raw/r1-anyps5.md` §1 rows 7, 8, 14 and §2 items 5, 6, 11.

Inputs (e5 input tree, read only): `src/kernel/pthread.cpp` is e4's private unit `0363847b` (mkpth0401.py,
`KYTY_BC5_PTHREAD_FIXES`; its 6 lines marked "experiment 0401 series e4" and their behaviour are untouched, the script
checks the count); `src/kernel/semaphore.cpp` is the base tree's `c9c4aaf5`. Both CRLF. Line numbers below: "in" is the
input, "out" the output.

No upstream code is copied: each change is the rule, written in this file's style, with a comment naming the project,
commit, path:lines and licence. KytyPS5 (github.com/KytyPS5/KytyPS5) dfec14a is GPL-2.0 (its LICENSE); AnyPS5
(github.com/boykopovar/AnyPS5) 4f41f4c37 GPL-2.0-only; shadPS4 60c42b9 GPL-2.0-or-later (cited for a value only). No
header is changed; every new state is inside the two .cpp files.

## Switches and journal lines

- `KYTY_BC5_THREAD_SYNC_FIXES` (pthread.cpp), parts `kk06`, `kk03`, `signalto`, `x87`, `kk07`. Unset, empty or `0`:
  off, today's code path exactly. Any other value: all five, unless it names parts (comma list): only those. Read once.
  One stderr line at the Pthread subsystem's init (out 1301): `[bc5] exp 0405: thread sync on (items: kk06,kk03,signalto,x87,kk07)`
  or `[bc5] exp 0405: thread sync off`.
- `KYTY_BC5_SEMA_FIXES` (semaphore.cpp), parts `attr`, `signal`; same reading. One stderr line at the first
  `sceKernelCreateSema` or `sceKernelSignalSema` that reads it: `[bc5] exp 0405: sema on (items: attr,signal)` or
  `[bc5] exp 0405: sema off`.
- Off path: every inserted statement is behind `Bc5ThreadSyncFix(part) && ...` / `Bc5SemaFix(part) && ...` (the switch
  is tested first), except the switch helpers themselves, one `bool bc5_woke` local and its assignment in
  `PthreadCondSignalto`, the `Bc5IsLive` member (called only with `signalto` on) and the init-time switch read. Checked
  mechanically: the outputs differ from the inputs by inserted lines only (difflib and `diff`: no changed or deleted
  line); removing them gives each input back byte for byte.

## Per item

| Item | Verdict | Source | Out (file:line) | Part |
|---|---|---|---|---|
| R2 KK06 notify under the internal lock | ported | KytyPS5 dfec14a `src/kernel/pthread.cpp:506-525` (comment 523), `1404-1413`, `2765-2771` | pthread.cpp 691 (PthreadWakeForSignal), 1598 (NativeMutexUnlock), 3139 (Broadcast), 3248 (Signal), 3287 (Signalto) | kk06 |
| R2 KK03 + SK11 static rwlock | ported | KytyPS5 4592e4c, dfec14a `src/kernel/pthread.cpp:2288-2299, 2469-2501` | 2599 (Destroy: OK, nothing made), 2832/2850 (Timedrdlock/Timedwrlock: CreateObject first) | kk03 |
| KK03 extended: static cond destroy | ported (r2's note on KK03: "extend the fix") | as KK03; FreeBSD libthr's behaviour TODO(verify) | 3164 (CondDestroy of a NULL handle: OK) | kk03 |
| R1 #7 scePthreadCondSignalto | ported | AnyPS5 0a5c3be28 `core/libs/prx/libkernel/Pthread/src/Cond.cpp:258-268` (PS5 fw 13.60 per their `docs/dev/debt/libkernel.md:345`) | 3282-3297 (Signalto), 1772 (`PthreadPool::Bc5IsLive`), 1786 (`Bc5SignaltoNotWaiting`), class decl +1 line | signalto |
| R1 #14 x87 control word 0x037f | ported | AnyPS5 8b626e307 `core/libs/prx/libkernel/Pthread/src/Thread.cpp:65, 891`; shadPS4 60c42b9 `src/core/thread.cpp:23, 71` | 3716-3723 (RunThread, before any guest code) | x87 |
| R1 #8 sema attributes 0x100-0x102 | ported | AnyPS5 58295ef07 `core/libs/prx/libkernel/Semaphore/src/Semaphore.cpp:25-34` (prosper oracle `kernel.golden.tsv` L10-23 @3ea5cb9, cited at their debt `libkernel.md:5, 91`) | semaphore.cpp 331-335 (mask to the low two bits when only 0x100 is extra) | attr |
| R1 #8 + SK09 signal count ≤ 0, overflow | ported | AnyPS5 `Semaphore.cpp:55-64`; sharpemu 514d766 `KernelSemaphoreCompatExports.cs:379, 388` (same compare) | 416-419 (count ≤ 0: EINVAL), 207-210 (`m_count > m_max_count - signal_count`) | signal |
| R1 #8 poll of 0 (and above max) | already match | — | in semaphore.cpp:188 (`need_count < 1 \|\| need_count > m_max_count`), :329 (InvalCount → EINVAL) | — |
| SK09 `sceKernelCreateSema(NULL, ...)` | held | AnyPS5 debt `libkernel.md:91`: the console faults there; sharpemu's EINVAL would hide what crashes on a console; our EXIT is the nearest | in semaphore.cpp:260 unchanged | — |
| R2 KK07 ESRCH for a joined thread | ported (extra, S, my file) | KytyPS5 dfec14a `src/kernel/pthread.cpp:3410-3413, 3518-3520, 3534-3537` | 3903 (Cancel), 4007 (Getprio), 4030 (Setprio) | kk07 |
| R2 KK08 FiberRun race | held | not in my files (`libs/libKernel.cpp`) | — | — |
| R1 #11 thread lifecycle, #29 deleted semaphore | held (brief: M, later) | — | — | — |
| MXCSR at thread start | not ported | shadPS4 loads 0x9fc0, FreeBSD's default is 0x1f80: sources disagree; TODO(verify) | — | — |

Details:

- **kk06.** Today `NativeMutexUnlock` does `lock.unlock(); mutex->cv.notify_one();` and the three condvar wakes do
  `{lock_guard; wake} if (notify) (*cond)->cv.notify_all();` (re-reading the handle). A woken thread, or a waiter whose
  10 ms poll fires in that window, can return, destroy and free; the notify then runs on freed memory, or dereferences the
  handle `PthreadCondDestroy` set to NULL. With `kk06` the notify happens before the lock is released; the waiter cannot
  get past `wait_for` until then, and nothing touches the object after the unlock (glibc's own futex wake after an unlock
  is the POSIX-sanctioned pattern). Cost: a woken waiter may briefly block on the internal lock (no wait morphing).
  Not closed: `PthreadWakeForSignal` still reads `thread->waiting_cond` before taking `cond->m` (a guest-signal wake of
  a cond that is being destroyed); `PthreadMutexDestroy`/`PthreadCondDestroy` still do not take the internal lock.
- **kk03.** `Destroy` of a NULL handle returns OK without `CreateObject`. Risk: a double destroy (or a destroy after a
  destroy) also returns OK now, where it stopped the emulator; FreeBSD returns EINVAL for a destroyed lock, but here a
  destroyed handle is NULL like a static one. `PthreadDeleteStaticObjects` at module unload benefits (it stopped on a
  guest-destroyed static rwlock). TODO(verify): the console's value for a destroy of a static initialiser (FreeBSD 11
  libthr returns 0 for its initialisers in `thr_rwlock.c`/`thr_cond.c`; not on disk here).
- **signalto.** OK when the target was waiting and is woken (unchanged); otherwise ESRCH unless the target is live, then
  EPERM. Live: a pool thread with `!free && !almost_done`, `g_pthread_main`, or the caller. The handle is compared only
  (0x12345 is safe). Risk: a guest-visible thread outside the pool and not the main thread gets ESRCH instead of EPERM
  (in the emulator only the runtime linker's main thread calls `PthreadInitSelfForMainThread`). A finished, unjoined
  thread gets ESRCH, as AnyPS5 (untried on the console there).
- **x87.** `fldcw 0x037f` at the top of `RunThread` (host code between there and the guest entry then runs with 0x037f,
  which is also Linux's default word). FreeBSD's source of the value (`__INITIAL_FPUCW__`, `fpu_initialstate`,
  `cpu_copy_thread` in `sys/amd64`) is cited by AnyPS5's debt note but not on disk here: TODO(verify). Not console-measured.
- **attr / signal.** Attr: `(attr & ~0x103) == 0 && (attr & 3) != 3` → `attr &= 3`, then today's check and queue
  choice. Signal: count ≤ 0 → EINVAL before touching the semaphore; room check `m_count > m_max_count - signal_count`.
- **kk07.** `Bc5ThreadSyncFix(KK07) && thread->free` → ESRCH, after the null check, in Cancel, Getprio, Setprio. Risk:
  a reused pool slot (a new thread) makes an old handle live again (ABA), as before.

## The test, thr0405.cpp

Built like e4's gates (`--gate thr0405.cpp <out> --like src/kernel/pthread.cpp`, both private units in the link). Runs
with both switches 1, 0 and unset; argument `on`/`off` (must match the switches); 9 cases; end line
`thr0405: on 9 of 9; end` / `thr0405: off 9 of 9; end`; exit 0 only then; watchdog 120 s (exit 3). Proposed rows:
`E5_EDITS`: `thr mkthr0405.py - src/kernel/pthread.cpp:0363847bd540883467dee22797475031:81ee12c4fa3e61df4f4b7239356b9f60 src/kernel/semaphore.cpp:c9c4aaf56492434eb84dc6e899260ae8:3aa9c8b441438483d124115d3961c9b0`;
`E5_GATES`: `thr0405.cpp src/kernel/pthread.cpp KYTY_BC5_THREAD_SYNC_FIXES,KYTY_BC5_SEMA_FIXES thr0405`;
`E5_STRS`: `KYTY_BC5_THREAD_SYNC_FIXES 'exp 0405: thread sync' KYTY_BC5_SEMA_FIXES 'exp 0405: sema'`.

| # | Case | On | Off |
|---|---|---|---|
| 1 | kk06 wake-ups, objects kept until both threads are done: 8 pairs × 1000 rounds; signal, broadcast, signalto; under the mutex and after its unlock; untimed and 10 s timed waits; mutex types 1 and 4 | all rounds, no error | same (today's behaviour unchanged) |
| 2 | kk06 destroy at once: same, the waiter destroys both objects and poisons (0xA5) and frees the memory holding their handles as soon as its wait returns (POSIX's pattern), 8 × 1500 rounds | no crash, no error | **not run**: today's notify after the unlock is a use-after-free there (crash once the handle reads NULL/poison); the case line says so and passes |
| 3 | kk03: Destroy of a static rwlock; Timedrdlock / Timedwrlock on static locks (created, another thread times out, unlock, destroy, destroy again); Destroy of a static cond | all OK, nothing made by Destroy | only Tryrdlock on a static lock (exp 0336, both); the rest EXITs today: not run |
| 4 | signalto: null thread; a waiting thread (woken alone, the other waiter stays); a fake handle 0x12345; the caller; a live guest thread; a finished guest thread; a joined guest thread | EINVAL, OK, ESRCH, EPERM, EPERM, ESRCH, ESRCH | EINVAL, OK, OK × 5 (today) |
| 5 | x87: the creator loads 0x027f and creates a guest thread (PthreadCreate → RunThread) | child 0x037f; creator keeps 0x027f; child MXCSR = creator's | child 0x027f (inherited, today) |
| 6 | kk07: Getprio/Setprio/Cancel of a joined guest thread; Getprio of a live one | ESRCH × 3; live OK, 700 | joined: **not run** (today uses the reaped host thread: UB; Setprio may renice a reused tid); live OK, 700 |
| 7 | sema attr: 0-2 OK; 3, 0x103, 0x104, 0x200, 0x1000, 0xffffffff EINVAL; 0x100-0x102 | create, poll, signal, delete work | EINVAL (today) |
| 8 | sema signal at count 1 (max 5) | 0, -1, INT_MAX: EINVAL, count kept; full: EINVAL | 0 and -1 OK, -1 lowers the count (today); INT_MAX recorded only (today's `m_count + signal_count` overflows: UB) |
| 9 | sema poll 0, -1, 4 (max 3), poll to empty, a blocked wait woken by a signal | EINVAL ×3 (already today), OK | same |

Runtime setup: pth0401.cpp's (Threads and Pthread subsystems on a helper thread that ends; logging off; every calling
host thread gets a `PthreadPrivate`), plus the `RuntimeLinker` singleton made on that helper thread (a guest thread's
`CleanupThread` asks it to drop TLS; `CreateObject` for a static object asks it for the owning program). Guest threads
get stacks from the test (`PthreadAttrSetstack`, so no Memory subsystem) and are created on a short-lived host thread,
since `PthreadCreate` ends with `PRINT_NAME_ENABLE(true)` for its caller and `PRINT_NAME` needs the log subsystem.
Guest threads call `SDL_LinuxSetThreadPriority(tid, 0)` at start (`Bc5ApplyGuestPriority`, "start" begins with 's'), as
savcb0401's guest thread did on the box.

## Laptop checks (2026-11-04)

- `mkthr0405.py <e5 input tree> <out>` → `src/kernel/pthread.cpp 81ee12c4fa3e61df4f4b7239356b9f60`,
  `src/kernel/semaphore.cpp 3aa9c8b441438483d124115d3961c9b0` (CRLF kept, ASCII). A second run on the output, or a tree
  with only one unit edited, is refused before anything is written.
- Insert-only: difflib (in the script and in `scratchpad/e5/x/thrcheck.py`) and GNU `diff` show only added lines;
  removing them gives the inputs back. Inserted text balanced: pthread.cpp +38/38 `{}`, +87/87 `()`, +3/3 `[]` (191
  lines in 19 blocks); semaphore.cpp +14/14, +36/36, +2/2 (78 lines in 5 blocks). thr0405.cpp balanced (134 `{}` pairs,
  548 `()`, 26 `[]`), ASCII, LF.
- **Syntax** (added on the coordinator's request): Visual Studio 18's clang++ 22.1.3 (x86_64-pc-windows-msvc),
  `-fsyntax-only -std=c++20 -Wall -Wextra -Werror`, the tree's **Windows** configuration: the stand-in `cmake_config.h`
  of `scratchpad/synchk/stub`, fmt from `refs/Inori_GPCS4/3rdParty/fmt/include` (`-isystem`),
  `-D_CRT_SECURE_NO_WARNINGS -D_SILENCE_ALL_CXX17_DEPRECATION_WARNINGS` (MSVC STL/CRT deprecations of `getenv` and
  `<codecvt>`), and declaration-only stand-ins for winpthreads' `<pthread.h>` and `<pthread_time.h>`
  (`scratchpad/e5/x/syn/pth/`). Results:
  - output pthread.cpp: clean, as the input; under `-Wshadow -Wconversion` 1 warning in both (today's line).
  - output semaphore.cpp: one error, `unused parameter 'opt'` in `KernelCreateSema` (out 326), the same one the input
    has (in 257); nothing else.
  - All new code is in that configuration (checked on the preprocessed output: every part's switch test, the `fldcw`
    block, `Bc5IsLive`, the init line).
  - thr0405.cpp: one error in the first pass, `std::aligned_alloc` (absent from MSVC's STL; glibc has it). Replaced by
    `std::malloc` (RunThread aligns the guest stack top itself); then clean, also under `-Wshadow -Wconversion`. Its
    only Linux-only include, `<unistd.h>` (`_exit`), was the stand-in of `scratchpad/synchk/stub-unistd`; the inline asm
    (`fldcw`, `fnstcw`, `stmxcsr`) and `KYTY_SYSV_ABI` compile as they are.
  - Not checked: the units' Linux branches (none of the new code is in a platform branch), GCC, the link, a run.

## Files

| File | md5 |
|---|---|
| `mkthr0405.py` | `553ac4e084ad77534a864b8e88937d57` |
| `thr0405.cpp` | `54e38bd5c27eaf2146e26b9d0259fa99` (was `a0f92353`: `std::aligned_alloc` replaced by `std::malloc`) |
| `thr0405-notes.md` | (this file; in the report) |
| input `src/kernel/pthread.cpp` | `0363847bd540883467dee22797475031` |
| input `src/kernel/semaphore.cpp` | `c9c4aaf56492434eb84dc6e899260ae8` |
| output `src/kernel/pthread.cpp` | `81ee12c4fa3e61df4f4b7239356b9f60` |
| output `src/kernel/semaphore.cpp` | `3aa9c8b441438483d124115d3961c9b0` |
