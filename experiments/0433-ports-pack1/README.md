# 0433 — ports pack 1

The experiment number is provisional until the top session confirms it.

**Question.** Do the first verified ports from KytyPS5 and AnyPS5 (`notes/ports-20261118.md`) leave both titles at least as stable and fast as the shared build? Each fix sits behind its own switch, all of them are in one private build, and the test can single out any fix that hurts.

## What this is

- **Patch layer.** `backend/kytyplus-patches/0002-bc5-ports-pack1.patch` goes on top of patch 0001 `ef2ff54f`. Patch 0001 itself is untouched: `grep -c 'exp 0372'` = 5, and `src/bc5/pad_audio_route.hpp` is still present.
  - It also applies cleanly with `git apply --check` on exp 0430's current 0001 (`d1388db0`, branch `exp/0430-hang-catcher` at 15210775), so it can be rebased onto the patch 0430 is baking.
  - It does not touch `bc5LleAgc.cpp` (the direct submission and XQ).
- **Backend.** `backend/src/policy.cpp` gets the 0x51 counter only. The private build therefore needs its own backend archive, built from this branch. That file is identical on main and on 0430's branch.
- **Switches.**
  - Every fix is ON unless its word is exactly `0` (`src/bc5/ports_pack1.hpp`).
  - `NAME=0` gives back the old code path of that one fix, with no rebuild.
  - The switches are read in the lean build too: they are fix switches, not diagnostics.
  - The first read prints one line: `[bc5] ports pack 1: EQ_WAKE_ALL=on NO_COND_REGISTRY=on ...`.
- **Licences.** KytyPS5 and AnyPS5 are GPL-2.0 (checked on 2026-11-18), the same as our host.
  - Every changed site carries a comment with the project, the commit and the upstream file and lines, plus what BC5 did differently.
  - Where the code is BC5's own rather than upstream's, the comment says so (A6, K1's log, K6's stack size).
- **Nothing has been built or run.** Checks so far, all on the laptop:
  - clang 22 (VS 18, MSVC target) `-fsyntax-only`, Windows branches: clean for `eventQueue.cpp`, `threads.cpp`, `libAmpr.cpp`, `semaphore.cpp`, `hostException.cpp`, `libAppContent.cpp`, `libSaveData.cpp`, `libSysmodule.cpp`, `libUserService.cpp` and `network.cpp`, and for the backend's `policy.cpp`.
  - Not compiled, because the laptop has no Linux headers:
    - `pthread.cpp`, `memory.cpp`, `controller.cpp`, `ajm.cpp` (ffmpeg headers);
    - the Linux branches of `sysLinuxFileIO.cpp`, `sysLinuxVirtual.cpp` and `hostException.cpp`.
  - Those were reviewed by hand. The box build is their first compile.

## Per-fix table

| # | Switch (`KYTY_BC5_P1_…`) | Source | What changes (with the switch on) | Files |
|---|---|---|---|---|
| A1 | `EQ_WAKE_ALL` | AnyPS5 `daad982457` | An equeue event that is added, re-added as a periodic timer, or triggered wakes **every** thread waiting on that queue (`SignalAll`), not one. | `kernel/eventQueue.cpp` |
| A2 | `NO_COND_REGISTRY` | KytyPS5 `18a1e0fa` | No global registry of host CondVar waiters: no global mutex taken twice per wait, and `CondVar::SignalThread` is a no-op. The guest's own wake for a signal (`PthreadWakeForSignal`) stays. | `common/threads.cpp` |
| A3 | `FAULT_MASK` | KytyPS5 `3b0a78a9` (hostException.cpp:235-237) | The host fault handler (SIGSEGV/SIGBUS/SIGILL) blocks the guest-signal dispatch signal `SIGRTMIN+3` while it runs, so a `KernelRaiseException` cannot preempt a fault between the protection fix and the retry. | `common/hostException.cpp` |
| A6 | `SEMA_UAF` | AnyPS5 `ff9a68aed4` (BC5 form) | POSIX semaphores are reference-counted. Destroy or re-init marks the object destroyed, wakes its waiters with EINVAL, and deletes it only after the last caller has left. Before, a waiter or a poster could touch freed memory. | `kernel/semaphore.cpp` |
| B1 | `AMPR_RESULT` | AnyPS5 `23a0020ab1` | APR/AMM `Submit…AndGetId` and `…AndGetResult` write the id and the "submitted" result **before** queueing. Afterwards they write only a failure. Before, a late write could overwrite the worker's real result. | `libs/libAmpr.cpp` |
| K1 | `APR_FILE_ID` | KytyPS5 `e43aadf7` (libAmpr.cpp:214-221) | APR file ids come from a counter, once per resolved path, below 2^31. The 31-bit FNV path hash let two paths share an id, and the second overwrote the first in `g_files`. **In both modes**, a hash collision is logged: `[bc5] ports pack 1 K1: APR path hash 0x… shared by A and B; …`. | `libs/libAmpr.cpp` |
| K2 | `COND_SIGNAL_ONE` | KytyPS5 `47b26e49` | A guest condvar waiter sleeps on its own thread's condition variable. Signal and signalto wake only the chosen waiter; broadcast and the guest-signal wake reach each waiter. The 10 ms poll stays, so a missed wake costs at most 10 ms. Exp 0405's kk06 and signalto are kept. | `kernel/pthread.cpp` |
| K3 | `PTHREAD_KEYS` | KytyPS5 `733842ca` (pthread.cpp:619-632, 1589-1620, 4002-4068) | Key values live per thread (`thread_local` array, odd/even generations). getspecific and setspecific take no lock and do no search; destructors run on the exiting thread. Before, every call took one global mutex and walked every thread's values. | `kernel/pthread.cpp` |
| K4 | `PROT_RANGES` | KytyPS5 `73363f12` | No per-4-KiB-page `std::map` of host protections, which was written on every alloc, protect and free under `g_virtual_mutex`. Its only reader is `SysVirtualProtect`'s `old_mode`, which no caller in the tree asks for; if one does, `/proc/self/maps` answers. | `common/platform/sysLinuxVirtual.cpp` |
| K6 | `ALTSTACK` | KytyPS5 `21124245` | Each guest thread, and the main thread, gets a 256 KiB alternate signal stack (upstream: 64 KiB), and the fault handler has `SA_ONSTACK`. A fault on an exhausted or read-only guest stack is then still handled and recorded. If the stack cannot be set, that is logged once and the thread goes on as before. | `common/hostException.{h,cpp}`, `kernel/pthread.cpp` |
| K7 | `FILE_UNBUFFERED` | KytyPS5 `cbe5b629` | Host files opened through `SysFileCreate/OpenR/OpenW/OpenRw` are unbuffered (`setvbuf _IONBF`), so two handles of one file see each other's writes. APR reads do not use this path (exp 0415's pread). | `common/platform/sysLinuxFileIO.cpp` |
| R2a | `AJM_GAPLESS` | KytyPS5 `2e315a3c`, `1cc0ac7e` (exp 0405 R2 KA04) | An AJM control job with the gapless sideband takes it first and passes only the remaining bytes to the codec's Initialize. Before, the gapless bytes were taken as codec parameters. Set-gapless with reset also resets the decoder. | `libs/ajm.cpp` |
| R2b | `AMPR_FILTER` | KytyPS5 `deb45a8b` (exp 0405 R2 KK15) | AMPR completion events carry `EVFILT_AMPR` (-25), not `EVFILT_USER`, so an AMPR id can no longer collide with a user event with the same ident on the same queue. KytyPS5 and AnyPS5 agree on -25. | `kernel/eventQueue.cpp` |
| C | `FATAL_TO_ERROR` | AnyPS5 (per site: `c55fb36d57` Export.cpp lines, `6843151af3`, `3acca27f27`, `dca5752e1b`, …; cited at each site) | About 20 host exits become the error code AnyPS5 returns. The old exit is still right below each check, for `=0`. | `network.cpp` (NpManager ×7), `controller.cpp` (PadRead), `libUserService.cpp`, `libAppContent.cpp`, `libSaveData.cpp`, `libSysmodule.cpp`, `memory.cpp` (unknown prot), `pthread.cpp` (setcancelstate/type) |
| H1 | none (count only) | AnyPS5 `6cec611cd0` (Pm4.cpp, from PAL), as knowledge | Counts CONTEXT_REG_RMW (0x51) packets seen by the policy filter and how many were dropped. One line is printed at the 1st, 2nd, 4th, 8th … packet. **Nothing about the packet changes.** A `pass` row needs the maintainer's word. | `backend/src/policy.cpp` |

**C sites in detail.**

| Site | Before | With the switch on |
|---|---|---|
| NpSetNpTitleId | exit on null | OK (AnyPS5 ignores both pointers) |
| NpSetContentRestriction | exit | INVALID_ARGUMENT 0x80550003 / INVALID_SIZE 0x80550011 |
| NpGetNpId, NpGetOnlineId, NpGetAccountIdA, NpGetAccountCountryA, NpGetState | exit on null | INVALID_ARGUMENT |
| PadRead | exit for num ∉ 1..64 | PAD_ERROR_INVALID_ARG; null data too, checked before the handle |
| UserService GetInitialUser, GetEvent, GetLoginUserIdList | exit on null | 0x80960005 |
| UserService GetUserName (only the path with `KYTY_BC5_USERSERVICE_VALUES` off) | exit | INVALID_ARGUMENT, UNKNOWN_USER 0x80960105, or BUFFER_TOO_SHORT 0x8096000A |
| AppContent AppParamGetInt | exit on null or unknown id | 0x80D90002 |
| SaveData Mount3, SetParam, GetMountInfo, SaveIcon | exit on null | 0x809F0000 |
| Sysmodule LoadModuleInternalWithArg | exit on any nonzero argument or null ret | 0; `*ret = 0` when ret is set |
| KernelMapNamedFlexibleMemory | exit on unknown prot | EINVAL plus a red log line |
| PthreadSetcancelstate / Setcanceltype | exit on an unknown value | EINVAL, before `old_*` is written |

`NpCheckNpAvailability` (we write 4 bytes, AnyPS5 writes 1) is **not** changed: the width was never measured.

## Not in this pack

These items from the proposal were not in the top session's scope for pack 1. They wait for pack 2, or for a word.

- **A4:** AudioOut2ContextPush on an unknown context.
- **A5:** eventFlag: the wrong-mode exit, the UAF on Delete, the lost wake, the Cancel deadlock.
- **A6's thundering herd (D2)** and KernelSema's delete-while-waiting.
- **A7:** FIFO mutex.
- **B2:** AMPR read failure ends the buffer.
- **D1:** pending-signal scan.
- **K5:** remap window.
- **H1:** behaviour change of 0x51.

## Tests

All of these run with RT on (the standing rule). The control is the same build with every word `=0`, which equals today's shared build:
- `KYTY_BC5_P1_EQ_WAKE_ALL=0 KYTY_BC5_P1_NO_COND_REGISTRY=0 KYTY_BC5_P1_FAULT_MASK=0 KYTY_BC5_P1_SEMA_UAF=0 KYTY_BC5_P1_AMPR_RESULT=0 KYTY_BC5_P1_APR_FILE_ID=0 KYTY_BC5_P1_COND_SIGNAL_ONE=0 KYTY_BC5_P1_ALTSTACK=0 KYTY_BC5_P1_PTHREAD_KEYS=0 KYTY_BC5_P1_PROT_RANGES=0 KYTY_BC5_P1_FILE_UNBUFFERED=0 KYTY_BC5_P1_AJM_GAPLESS=0 KYTY_BC5_P1_AMPR_FILTER=0 KYTY_BC5_P1_FATAL_TO_ERROR=0`.

| # | Title | What shows it works | What shows it hurts |
|---|---|---|---|
| all | both, lean smoke (ASTRO BOT 200 s, the second title 300 s) | The `[bc5] ports pack 1:` line with all `on`; the smoke passes | A crash, hang or exit the control does not have |
| A1, A2, K2 | the second title, fight route (slot 4, phase-2 gate), 3 runs against 3 control | Flips/s equal or higher; host profile (exp 0432 style): less time in `PthreadCondSignal`/`notify_all` wakeups and in the CondVar registry mutex; fewer futex wakes (`perf trace -s` or `strace -c -f -e futex` on a short window) | A new hang (F588/F403-like), or a stall whose sampler shows a thread asleep in an equeue or condvar wait |
| A3, K6 | both: any run that ends in a GPU fault (exit 86) or a host fault | The fault record under `~/bc5-data/captures/faults/` is still complete (K6 moves the handler onto the alt stack); no new SIGSEGV | A record cut short, or a silent death in a fault |
| A6 | both | No regression; the pack's code changes nothing unless a title destroys or re-inits a semaphore while it is in use (not observed so far) | A thread stuck in `sem_wait` after a destroy (the EINVAL path) |
| B1, R2b, K1 | the second title's loads (title → save slot 4 → fight) and ASTRO BOT's level loads | Load times equal to the control; no APR wait hang; any K1 line means two of the title's paths share a hash, and with the switch on they are kept apart (with `=0` the second file would have been read wrong) | A load that hangs on an APR wait or completion event (R2b changes the filter the guest sees) |
| K3, K4 | the second title, fight route | Flips/s equal or higher; RSS after load lower with K4 (about 12 MiB per GiB of host allocations); less time in `PthreadGetspecific` and `g_virtual_mutex` | A crash at thread exit (K3's destructors) or a protect that does not hold |
| K7 | both: loads and a save (away from his live saves, a copy of the save snapshot) | Load time within noise of the control (small reads now cost a syscall each); saves read back correctly | Load time clearly up |
| R2a | ASTRO BOT music and the second title's Wwise audio, by ear, at loop points and track ends | No click or gap where the control has one; **replug check needed** (audio code changed) | Silence, noise or a crash in AJM |
| C | both | No new error-code lines in the log; a title reaching one of these sites gets the code instead of a host exit | A new error code where the control runs clean |
| H1 | the second title, fight route with RT | Lines `[bc5] ports pack 1: CONTEXT_REG_RMW (0x51) seen N, dropped M`, or none at all (then 0x51 is not sent and the question is closed) | Nothing to hurt: the packet is still dropped as before |

If the pack run shows a regression, bisect by turning words off: the halves, then single words. Each word works on its own.
