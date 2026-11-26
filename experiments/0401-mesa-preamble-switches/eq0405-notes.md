# Experiment 0401 series e5, port agent `eq`: equeue, timer, kevent and mmap fixes (exp 0405)

Files: `mkeq0405.py` (the edit), `eq0405.cpp` (the CPU test), this note. Units edited: `src/kernel/eventQueue.cpp`
(whole unit) and `src/libs/bc5LleAgc.cpp`, only in the libkernel shims (the `mmap`, `kevent` and
`sceKernelAddTimerEvent` shims, a block between `Ioctl` and the `mmap` shim, and one registration line). The soft CP and
the gc ioctl handlers (agent `gpu`) are not touched. No header changes. No GPU submission changes.

Input: the e5 input tree. Output line numbers below are in `mkeq0405.py`'s output of that tree.

## Switches and journal lines

| Switch | Items | stderr line (once) |
|---|---|---|
| `KYTY_BC5_EQUEUE_FIXES` | `kk02`, `sk03`, `g1`, `kk01` | `[bc5] exp 0405: equeue fixes on (items: kk02 sk03 g1 kk01)` or `[bc5] exp 0405: equeue fixes off` |
| `KYTY_BC5_MMAP_SHIM_FIXES` | `hint`, `prot` (together: R3 M2) | `[bc5] exp 0405: mmap shim fixes on (items: hint prot)` or `[bc5] exp 0405: mmap shim fixes off` |

- **Grammar** (e4's convention, `aud0401`):
  - unset, empty or `0` is off;
  - a comma list turns on the items it names;
  - any other value (`1`, `yes`, an unknown name) turns on all items.
- **When the lines print.**
  - The equeue line prints at init. The libkernel registration reads the switch, because `kk01` registers one NID.
  - The mmap line prints at the first `mmap`, which is the driver's, early in a run.
- **Catcher lines, only with the item on:**
  - `[bc5] exp 0405: kevent eq N timeout {s s, ns ns} nevents N -> R (#k)`: the first 8 `kevent` calls with a timeout;
  - `[bc5] exp 0405: mmap hint P len L is not free: mapped at Q (#k)`: the first 8 hints that moved.
- **Off.** Each changed spot branches on the switch, and the off branch is today's code. Undoing every replacement gives
  the input back byte for byte (checked).

## Per item

### 1. R2 KK02 (+SK01): level event once per wait. Ported

- **Sources.**
  - KytyPS5 dfec14a `kernel/eventQueue.cpp:120-127`: `else break;` after the pending pop. GPL-2.0.
  - sharpemu 514d766 `SharpEmu.Libs/Kernel/KernelEventQueueCompatExports.cs:1940-1960` (commit 816ec4a): each entry is
    delivered once per wait, and a level entry is queued again. GPL-2.0-or-later.
  - Adapted; no line copied.
- **Change** (`eventQueue.cpp` out:198, 222-226). `GetTriggeredEvents` reads the switch once per call. With it on, an
  event that is still triggered after its reset or EV_CLEAR step, with no pending copy, stops this wait's loop for that
  event.
- **Hazard.** An event that its reset clears, or that has pending copies, is delivered exactly as before. That covers:
  - EOP (`sync.cpp` `EopEventResetFunc`/`EopEventTriggerFunc`);
  - VideoOut flip (`ResetVideoOutEvent`);
  - AMPR;
  - EV_CLEAR user events;
  - the soft CP's `fire` (EVFILT_GRAPHICS into the same EOP events).
  The `else break` triggers only where today's loop would copy the same triggered event again.
- **Behaviour change, by design.** The renderer's `AGC_USER_INTERRUPT_EVENT` (0x1800, `KernelTriggerUserEventForAll`;
  host renderer path, not the LLE path) changes only if a title registered it as a *level* user event: then one copy per
  wait instead of up to `num`. Exp 0188 had this rule as `KYTY_BC5_EQUEUE_LEVEL_ONCE`. That lever was removed with the
  unused ones on 2026-11-01, and the second title showed no repeated level event (F247, run M2).
- **Test.** Cases 2-8 below.

### 2. R2 SK03: `sceKernelWaitEqueue` with `out == NULL`. Ported

- **Source.** sharpemu 514d766 `KernelEventQueueCompatExports.cs:783-976` (the out checks at 813 and 937).
- **Change** (out:580-586). With the item on, a NULL `out` points at a local count. The wait and the return codes are
  unchanged, and no count is written. Off: today's `EXIT_NOT_IMPLEMENTED`.
- **Test.** On only. With the switch off, today's code ends the process, so that case is not run (the test prints a
  note).

### 3. R3 G1: `kevent` honours its timespec. Ported

- **Sources.**
  - FreeBSD kevent(2) semantics: `{0,0}` polls; on expiry, 0 is returned.
  - AnyPS5 4f41f4c37 `core/libs/prx/libkernel/Equeue/src/Kqueue.cpp:545-551, 669-678` (GPL-2.0-only), read for the
    semantics only: EINVAL for `tv_sec < 0`, `tv_nsec < 0` or `>= 1e9`; no deadline when `tv_sec > INT32_MAX`.
- **Change** (`bc5LleAgc.cpp` out:9318-9361 `Bc5KeventTimed0405`, and the branch at out:9444-9449 in `Kevent`). A non-NULL
  timeout with the item on:
  - rounds nsec up to whole microseconds;
  - calls `EQ::KernelWaitEqueue` with that timeout, in parts of 1000 s (its timeout is 32-bit microseconds);
  - maps ETIMEDOUT to 0 and other errors to -1;
  - returns -1 for an invalid timespec (no errno, like the shim's other failures).
  A NULL timeout, or the item off, takes today's untimed wait.
- **TODO(verify).** FreeBSD `sys/kern/kern_event.c` (kqueue_scan) was not read tonight (no network).
- **Risk.** `kevent` is libSceAgcDriver's EOP wait. If the driver passes a timeout, it now gets 0 at expiry, as on the
  console, where today it blocked until an event. The catcher's first 8 lines show whether it does. Events are delivered
  as before.

### 4. R2 KK01 (F246): `sceKernelAddTimerEvent`. Ported in full: periodic, with a side table

- **Sources.**
  - KytyPS5 dfec14a `kernel/eventQueue.cpp:142-154, 210-234, 525-539` (GPL-2.0);
  - AnyPS5 4f41f4c37 `Equeue.cpp:829-843` (GPL-2.0-only), including `sceKernelDeleteTimerEvent`.
- **The side table.** KytyPS5's `interval_ns` lives in the header struct. Here the period lives in a side table instead:
  `KernelEqueuePrivate::m_bc5_timer_period_ns` (ident → period), a member of the class `eventQueue.cpp` defines (the
  header only forward-declares it). Filled only with the item on.
- **Changes.**
  - The shim (out:9617-9628) takes the low 32 bits of the third argument as microseconds. The upper half of rdx is not
    part of a 32-bit argument; the test passes garbage there.
  - It calls `Bc5KernelAddTimerEvent0405` (eventQueue out:714-738): EVFILT_TIMER (-7), `EV_ADD|EV_CLEAR`, first deadline
    one period from now.
  - `Bc5TriggerExpiredPeriodicTimers` (out:252-271) adds the periods that ran out to `data` and moves the deadline on.
  - `Bc5AddPeriodicTimer` (out:351-378): a re-add first counts the expired periods, then takes the new deadline and udata.
  - `DeleteEvent` drops the period (out:468-470).
  - `sceKernelDeleteTimerEvent` (YWQFUyXIVdU) is registered only with the item on (out:9686-9688).
- **Period 0** becomes 1 µs. TODO(verify): FreeBSD's `filt_timervalidate` rule, from memory; the console is not
  measured.
- **Off.** Today's path: the third argument is read as a `KernelTimespec*`, giving a one-shot HR timer; a small integer
  faults.

### 5. R3 M2: the `mmap` shim. Ported, with the driver's fixed path kept

- **Sources** (behaviour only, all GPL):
  - shadPS4 60c42b9 `src/core/libraries/kernel/memory.cpp:753-816`;
  - AnyPS5 `DirectMemory/PosixMemory.cpp:145-249`;
  - sharpemu `KernelMemoryCompatExports.Mmap.cs:10-42`.
- **`hint`** (out:9379-9389). An anonymous mapping (`fd < 0`) whose flags lack MAP_FIXED (0x10) passes its address as a
  search start: `KernelMapNamedFlexibleMemory`'s non-fixed branch, `FindGuestFreeRange(addr)`. It no longer replaces a
  live mapping. Unchanged:
  - **Device mappings** (`fd >= 0`, the gc page at 0xfe0200000) keep today's fixed-at-address path, whatever their flags
    say. Exp 0011 logged the driver's call as `MAP_SHARED` without saying whether MAP_FIXED was set. TODO(verify) in a
    run's `[bc5-gc] mmap ... flags` line. R3's spec assumed FIXED; this keeps the path either way.
  - **MAP_FIXED** still replaces.
  - The retry-anywhere fallback.
- **`prot`** (out:9384, 9405).
  - prot 0 stays 0 (no access) instead of 0x33.
  - No `memset` without CPU write. Flexible memory is already zeroed at map (`FlexibleMemory::Map`'s `ZeroBacking`), and
    today's memset on a read-only mapping faults.

### 6. Extras. Held

- **R3 G15** (general kevent filters): M effort, as the brief says.
- **R2 KK15** (EVFILT_AMPR -25) touches only `eventQueue.cpp`, but its risk is M. The same rule existed as
  `K_AMPR_FILTER`, removed 2026-11-01, and exp 0036 saw no change. Not for tonight.
- **R2 SK34, SK35** and **R3 M13, M14**: "later" in their reports.
- **Not ported, noted:** `mmap` with a length that is not a multiple of 16 KiB fails here (`KernelMapNamedFlexibleMemory`
  EINVAL → NULL). shadPS4 aligns it up. Belongs to M14.

## The CPU test, `eq0405.cpp`

- **Build:** `build0401.py ... src/kernel/eventQueue.cpp=<out> src/libs/bc5LleAgc.cpp=<out> --gate eq0405.cpp <dir>/eq0405
  --like src/kernel/eventQueue.cpp`.
  - Both private objects must be in, also when the `gpu` edit is chained.
  - With a shared object the link fails on the `*0405` functions.
- **Runs:** both switches `=1` (`eq0405 on`), both `=0` and both unset (`eq0405 off`).
- **End lines:** `eq0405: on 21 of 21; end` and `eq0405: off 18 of 18; end`. An item list prints `eq0405: mixed ...`.
- **Watchdog:** 90 s.
- **Init,** as amm0401: the Common, Threads, Config, Log and Memory subsystems, `Libs::InitAll`, and the shims by NID.
  The NIDs are checked by `mkeq0405.py`.

| # | Case | On | Off |
|---|---|---|---|
| 1 | grammar: 20 values through both units' parsers; the values read once | same | same |
| 2 | level user event, num 4 | 1, again 1 | 4, again 4 (today) |
| 3 | edge user event | 1, then ETIMEDOUT | same |
| 4 | AMPR, 3 completions | 3 (data 1, 2, 3) | same |
| 5 | EOP-style EVFILT_GRAPHICS (sync.cpp's rules): 3 triggers, num 8; 3 more, num 2 | 3; 2 + 1 | same |
| 6 | flip-style (updated in place): 2 triggers | 1, fflags 2 | same |
| 7 | user interrupt 0x1800, edge, `KernelTriggerUserEventForAll` | 1 | same |
| 8 | EOP-style + level user event in one queue | 2 EOP + 1 | 2 EOP (identical) + 6 |
| 9 | out == NULL: poll with event, empty poll, untimed | OK, ETIMEDOUT, OK | not run (EXIT today) |
| 10-13 | kevent {0,0} / {0,30 ms} / tv_nsec 1e9 / ready event with {0,0}, NULL, {5 s} | 0 at once / 0 after ≥29 ms / -1 / 1,1,1 | 1 after the late trigger (150/300/150 ms) / 1,1,1 |
| 14 | AddTimerEvent 20 ms (garbage upper half): EVFILT_TIMER, EV_CLEAR, udata; data = expirations within the clock's bounds | yes | case "today's one-shot HR timer via a timespec pointer; YWQFUyXIVdU unregistered" |
| 15 | re-add without a duplicate, DeleteTimerEvent (OK, then ENOENT), bad queue EBADF, 0 period | yes | (in 14) |
| 16 | mmap anonymous hint over a live mapping | elsewhere, old intact | replaced and cleared (today) |
| 17 | mmap free hint | at the hint | same |
| 18 | MAP_FIXED over a live mapping | replaces | same |
| 19 | driver-style 0xfe0200000 (MAP_SHARED, fd 5) and 0xfe0204000 (MAP_SHARED and MAP_FIXED, fd 5) | fixed, prot 0x22, writable | same |
| 20 | prot 0 | prot 0 | 0x33, reads 0 (today) |
| 21 | prot 1 | prot 1, reads 0 | not run (today's memset faults) |

## Verified on the laptop

- **Script.**
  - `mkeq0405.py e5/e4tree <out>` printed the two md5s in the table below. The inputs matched their pins.
  - It refuses its own output, with and without `--chain` ("has this edit already").
  - It refuses the `gpu` output without `--chain` (md5).
  - Undoing every replacement in reverse gives both inputs back byte for byte.
  - Brackets keep their balance (the script asserts it). The inserted text is ASCII.
- **Chain.** The `gpu` output (8d71e9f6) with `mkeq0405.py --chain`, and `mkgpu0405.py --chain` on this output, give the
  same unit `d1cfd9bb1f1b3485bed4207a7f064d4f`.
- **Syntax.** clang 22 (VS 18, MSVC target) `-fsyntax-only -std=c++20 -Wall -Wextra -Werror`, with the stub
  `cmake_config.h` and GPCS4's fmt.
  - `eventQueue.cpp` output: clean, apart from MSVC's `getenv` deprecation. Under `-Wshadow -Wconversion
    -Wsign-conversion` it has the input's one warning (`SetName`), and nothing new.
  - `bc5LleAgc.cpp`: its whole `Bc5LleKernel` namespace, with stubs for the `Bc5Gc` parts it calls. The rest of the unit
    needs Linux headers. Clean; no new warnings under the stricter flags either.
  - `eq0405.cpp`: clean with `-Werror`.
- **Stand-in run, Windows.**
  - The real output `eventQueue.cpp`, the real shims namespace and `eq0405.cpp`'s cases, with stubs for the rest. The
    mmap cases need the memory subsystem and were not run.
  - Results: on 15/15; off 13/13.
  - Against the **unedited** units: off 13/13, so the off expectations are today's code. With the on expectations it
    fails cases 2 and 8 and EXITs in case 9, so the test tells the two apart.
- **Not checked:** GCC on the box, the Linux branches, the link with all emulator objects, the mmap cases, and the real
  driver's `kevent`/`mmap` arguments.

## Risks

- **g1:** the driver's EOP waits may carry a timeout (see item 3). The catcher lines tell.
- **kk02:** a title that relied on N copies of a level event. On the console it gets one.
- **kk01:**
  - a title that never deletes its periodic timer keeps it firing (as on the console);
  - the timer callback data accumulates while unread.
- **hint:** a title that passed a non-fixed hint expecting replacement now gets another address, as on FreeBSD.
- **prot:** a prot-0 mapping the title then touches now faults, as on the console. Guard pages work.
- **Link:** the edited `bc5LleAgc.cpp` needs the edited `eventQueue.cpp` (`Bc5EqueueFixes0405`,
  `Bc5KernelAddTimerEvent0405`). Ship the two together.

## Files

| File | md5 |
|---|---|
| `mkeq0405.py` | see the final report |
| `eq0405.cpp` | see the final report |
| in `src/kernel/eventQueue.cpp` | `c45e6a72c8e419d98059c3477a9373cc` |
| out `src/kernel/eventQueue.cpp` | `d8eaa6d22e3e415ea8331dced30867c0` |
| in `src/libs/bc5LleAgc.cpp` | `df12bb2de3e90b8c82a234eedf0babb5` |
| out `src/libs/bc5LleAgc.cpp` | `09770e46272ed52107f055c6f1af2332` |
| out with `gpu` chained (either order, gpu at 8d71e9f6) | `d1cfd9bb1f1b3485bed4207a7f064d4f` |
