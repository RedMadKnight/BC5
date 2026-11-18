# 0433 — ports pack 1

The top session confirmed the number 0433 on 2026-11-18. The box directory `~/bc5-work/exp0433` is made only in the slot.

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
- **Nothing has been built or run.** All checks so far ran on the laptop.
  - **Syntax, Windows configuration.** clang 22 (VS 18, MSVC target) `-fsyntax-only` is clean for `eventQueue.cpp`, `threads.cpp`, `libAmpr.cpp`, `semaphore.cpp`, `hostException.cpp`, `libAppContent.cpp`, `libSaveData.cpp`, `libSysmodule.cpp`, `libUserService.cpp`, `network.cpp` and the backend's `policy.cpp`.
  - **Syntax, Linux configuration.** All 16 changed units and the new header were checked with `KYTY_PLATFORM` set to Linux. Missing Linux headers were stood in by empty files, and the POSIX symbols the pack's own lines use were declared with their glibc x86-64 shapes. The errors that remain all come from the stood-in headers; the pack's added lines have **0 errors**, `ports_pack1.hpp` included.
    - Script: the session's scratchpad `lincheck.py`, not committed.
    - The method was proven by planting a typo on an added line. Each one was caught: in `hostException.cpp`, `sysLinuxFileIO.cpp`, `sysLinuxVirtual.cpp`, `pthread.cpp` (K2, K3 and K6 lines), `ajm.cpp`, `controller.cpp` and `memory.cpp`.
    - This is a syntax check, not a full compile. The box build is still the first real compile on Linux, with glibc and libstdc++.
  - **0002 on d1388db0.** Generated on top of exp 0430's d1388db0 instead of ef2ff54f, 0002 comes out byte for byte the same (md5 `e682b061`). d1388db0 changes only `bc5LleAgc.cpp`, so nothing needs rebasing.

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

## Box plan (in the top session's slot, after exp 0430's swap to d1388db0 and its test)

Every step runs with RT on. The runners are the ones that already exist: exp 0430's `run0430f.sh`, as `chain0430.sh` calls it, for the second title, and exp 0431's `astro0431.sh` for ASTRO BOT. Both take a private binary. Saves are reset from the named snapshots before every run (R45), never his live saves. `ulimit -c 0`.

**0. Kit.** Copy from this branch to `~/bc5-work/exp0433/kit/`:
- from `experiments/0433-ports-pack1/`: `box0433.sh`, `build0433.py`, `units.sha256`, `backend.sha256` and `policy0433.diff`;
- `backend/kytyplus-patches/0002-bc5-ports-pack1.patch`.

**1. Build (CPU only, nothing reaches the GPU, about 15–20 min at nice 19).**

```bash
cd ~/bc5-work/exp0433/kit
bash box0433.sh claim "0433 private build" 30
bash box0433.sh build
bash box0433.sh release
```

What `build` checks and makes:
- **Shared tree.** It must equal the pins: the 16 units and `hostException.h`, plus `bc5LleAgc.cpp` at d1388db0 (`ALLOW_EF2=1` accepts ef2ff54f instead).
- **Units.** 0002 is applied to copies of the units.
- **Backend archive.** A private copy of the shared archive is made, with only its `policy.cpp` member rebuilt from the pinned shared source plus `policy0433.diff`.
- **Builds.** Normal and lean are built with the shared builds' own compile and link commands (`build0433.py`, after exp 0429's `build0429.py`). A unit whose object sits inside a static library gets a private copy of that library.
- **Stop conditions.** The build stops if any of the 14 words or the 0x51 line is missing from either binary, or if a shared binary or the shared archive changed.
- **Output.** `~/bc5-work/exp0433/{normal,lean}/kyty_emulator`, `binary.md5`, `backend/libbc5_backend.a`.
- **Already tried on a laptop stand-in** (a fake HOME holding the d1388db0 tree, stub `distrobox` and `pgrep`):
  - claim, the pins, 0002 on the copies and `policy0433.diff` all pass, up to the first distrobox call;
  - the patched `pthread.cpp` copy equals the pack tree.

  `build0433.py` itself has only been byte-compiled; it first runs on the box.

**2. Smoke, private lean (gate for step 3).**
- ASTRO BOT, 200 s:

  ```bash
  XBIN=$HOME/bc5-work/exp0433/lean/kyty_emulator bash ~/bc5-work/exp0431/astro0431.sh 200 s433a:x:D
  ```

- The second title, 300 s, with exp 0430's runner on the private lean binary. Set `P_BIN` to the private lean binary, `P_WANT` to its md5, and `P_WORDS` to `~/bc5-work/exp0413/n/words0413nz.txt`; also `N_SLOT=4 N_ARENA=off N_FUSE=0 N_NOWD=1`. Call it as `run0430f.sh s433u h 300`.
- **PASS:** the `[bc5] ports pack 1:` line is there with all 14 `on`; both runs end with the runner's PASS; no kernel line, no crash text.
- **On FAIL:** stop and bisect with words before anything else (the halves, then single words, `NAME=0`).

**3. Per-fix runs, private normal binary.** The control is the **same binary** with all 14 words `=0` (the list under Tests), so it isolates the pack from everything else.

| Set | Runs | Look at |
|---|---|---|
| fight | the second title, `run0430f.sh` fight route (slot 4, the 14:50 record's gameplay at G, then exp 0379's walk), 3 pack + 3 control, alternated: `s433f1 P`, `s433c1 C`, `s433f2 P`, … | A1/A2/K2/K3: flips/s and seconds over a 50 ms gap (exp 0432's measures); hangs. K4: `VmRSS` of the emulator at G+120 s (one `grep VmRSS /proc/<pid>/status`). B1/K1/K7/R2b: time from start to G. Every run: `grep -a "ports pack 1"` (the startup line, any K1 collision line, the 0x51 count, any K6 sigaltstack failure) |
| astro | ASTRO BOT normal 480 s, 1 pack + 1 control (`astro0431.sh 480 s433n1:x:D`, with `XWORDS` for the control) | The same greps; flips/s; R2a, from the log only (no AJM errors) |
| profile (optional) | 1 pack + 1 control of the fight route with exp 0432's host profile | A2, K2, K3: time in `PthreadCondSignal`/`notify_all`, the CondVar registry mutex and `PthreadGetspecific` |

**Read-out.**
- **The pack passes if:**
  - no new crash, hang or fault against the control;
  - flips/s and the gap seconds equal to or better than the control, within the control's spread;
  - load time to G within noise;
  - no new error-code line from the C sites.
- **0x51 is answered either way:**
  - count lines mean the titles send it; the next step is a `pass` row, which needs the maintainer's word;
  - no lines mean they do not send it, and the question is closed.
- **Any K1 line** names two paths with the same hash, so the old hash ids would have read the wrong file.

**4. Last, the maintainer's step: replug check for R2a** (audio code changed, `bc5-audio-replug-check`). Top asks him; it needs him at the box. Nothing from this pack goes to the shared builds before that check and his word.
