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

- The second title, 300 s, with exp 0430's runner on the private lean binary. Set `P_BIN` to the private lean binary, `P_WANT` to its md5, and `P_WORDS` to `~/bc5-work/exp0413/n/words0413nz.txt`; also `N_SLOT=4 N_ARENA=off N_FUSE=0 N_NOWD=1`. Call it as `run0430f.sh s433u h 300`. **Correction from the box (2026-11-19):** `run0430f.sh` gates its route on the journal's frame-profile lines, and lean writes none, so s433u ended as SETUP at 61 s (a void run). The lean runner is `run0430l.sh`, launched as top's `abl0430.sh` S arm: `P_HOST=0 N_TIMED=1 N_T0=90 N_T1=10 N_T2=8 N_T3=25 N_MH=1 N_MHD=373 N_LEANSESS=1`, plus the words above and way 2's five words (run s433l).
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
**Closed 2026-11-19, no replug check needed.**
- His words, relayed by top: "dźwięk i pad (trzęsie) w testach działają" (sound and pad rumble work in the tests).
- Why no check: R2a changes the AJM decoder only. It touches neither the audio device route nor the pad code. The replug rule covers only audio/pad device code or kernel/PipeWire changes.
- His word on shared deployment is still needed.

## Results on the box (2026-11-19, top's GO after exp 0430's swap; shared state patch d1388db0, normal eb85d32e, lean 364c6146, archive 6eac453e, all checked unchanged after every build)

All raw files are on the box: the second title's under `~/bc5-work/exp0430/n/raw/<tag>-*`, ASTRO BOT's under `~/bc5-work/exp0413/n/raw/<tag>-*`, the probe's under `~/bc5-work/exp0433/probe/`. Every run had RT on (rtkit grants or 14 SCHED_RR threads seen), JobArenaFix off, `ulimit -c 0`, launched under the user manager (`systemd-run --user`).

**Build (step 1).** Private normal `4c48c55b`, lean `d3d4de8e`, archive `51db2c91`. 0 errors; the 34/37 warnings are all on old lines. Three kit fixes were needed on the box: the host has no `patch` (now `git apply`); `eventQueue.cpp` has 8 compdb entries because the test programs compile it too (the entry is now chosen by product); and the quoted include `event_cap0412.hpp` needed `-iquote` of the shared source directory.

**Smoke (step 2), private lean: PASS.**
- ASTRO BOT s433a: 200 s PASS.
- The second title s433l: run0430l.sh, G+300, NO_CRASH, 37.0 flips/s (top's shared-lean hs430S1: 39.3).
- s433u is void (SETUP: the wrong runner, see step 2).

**Fight route (step 3), private normal, G+1500, P/C alternated: 6 of 6 NO_CRASH, 0 kernel or crash lines.**

| Run | flips/s | s over 50 ms | longest gap | G s | anon at G+120 MiB |
|---|---|---|---|---|---|
| s433f1 P | 37.8 | 354 | 2560 ms | 107 | 135 |
| s433c1 C | 40.2 | 295 | 688 ms | 106 | 128 |
| s433f2 P | 38.7 | 267 | 274 ms | 106 | 131 |
| s433c2 C | 39.7 | 228 | 269 ms | 106 | 139 |
| s433f3 P | 39.3 | 204 | 995 ms | 108 | 122 |
| s433c3 C | 39.3 | 216 | 3527 ms | 107 | 139 |

- P mean 38.6 flips/s, C mean 39.7. P is at or below its paired C every time. That is a hint of about 1 flips/s, the size of the run-to-run noise (R13).
- Time to G is the same in both arms.
- K4 shows no change in the emulator's anonymous memory.

**ASTRO BOT normal 480 s.** s433n1 P and s433m1 C both PASS, with the same job counts. AJM lines are equal: one each.

**Hit counters and probe (step 3b).**
- Build `cfb54fd3`: 0002 with hit counters. Each `BC5_P1()` evaluation that returns ON is counted; normal build only; `KYTY_BC5_P1_HITS=0` turns counting off.
- One short pair, G+300: s433p1 P 37.6, s433q1 C 37.8 flips/s.

Hit counts in P (lower bounds, about 400 s):

| Word | Hits |
|---|---|
| NO_COND_REGISTRY | 16.8M |
| PTHREAD_KEYS | 1.05M |
| COND_SIGNAL_ONE | 524k |
| PROT_RANGES | 131k |
| EQ_WAKE_ALL | 16k |
| AJM_GAPLESS | 16k |
| AMPR_FILTER | 8.3k |
| APR_FILE_ID | 64 |
| FILE_UNBUFFERED | 64 |
| ALTSTACK | 32 |
| SEMA_UAF | 16 |
| FAULT_MASK | 1 |
| AMPR_RESULT | 0 |
| FATAL_TO_ERROR | 0 |

**Never triggered on these routes, so harmless but untested:**
- B1 AMPR_RESULT (0 hits);
- every C site (0 hits);
- the K1 collision line;
- the K6 sigaltstack failure;
- the 0x51 count (neither title sent CONTEXT_REG_RMW on these routes).

**Context switches per thread, G+120 to G+288, P against C.**

| Threads | voluntary P / C | nonvoluntary P / C |
|---|---|---|
| Total | 9.65M / 9.97M | 1.80M / 1.88M |
| Job_Hi | 2.90M / 3.09M | |
| Job_Lo | 1.42M / 1.52M | |
| Render_Thread | 418k / 466k | |
| bc5-apr-q, bc5-apr-r1/r3/r5 | 9–10 % higher in P | |

- There is no wake inflation from A1/K2/A2/K3.
- The only group higher in P is the APR threads, and the APR-path fixes that change behaviour there are K7 and R2b.
- perf failed: the container's sudo cannot read the host's tracefs.

**Suspect arm (K7 + R2b off), 2026-11-19 07:12–09:59, binary cfb54fd3, `KYTY_BC5_P1_HITS=0`, G+1500, alternated A/P.**

- Arm A is P with `KYTY_BC5_P1_FILE_UNBUFFERED=0 KYTY_BC5_P1_AMPR_FILTER=0`.
- 7 runs, 6 NO_CRASH. s433xf1 (P) was NOT_ROUTED: no load within 40 s of Continue, a menu flake. The chain was resumed with one NOT_ROUTED tolerated, as in chain0430.

| Run (in time order) | Arm | flips/s | s over 50 ms | longest gap |
|---|---|---|---|---|
| s433xa1 | A | 39.0 | 237 | 621 ms |
| s433yf1 | P | 38.6 | 272 | 3624 ms |
| s433ya1 | A | 44.2 | 67 | 469 ms |
| s433yf2 | P | 40.8 | 179 | 815 ms |
| s433ya2 | A | 42.2 | 163 | 275 ms |
| s433yf3 | P | 42.1 | 136 | 250 ms |

- Mean A 41.8 flips/s and 156 s over 50 ms; mean P 40.5 and 196.
- The ranges overlap: P 38.6–42.1, A 39.0–44.2.
- Both arms drift upward through the morning, and the drift (about 3 flips/s from first to last pair) is as large as the A–P gap.
- **Verdict: not shown.** K7/R2b are not a cost above run-to-run noise at 3+3.
- Over all 12 fight runs (P 6, C 3, A 3), the pack shows no cost outside the noise: P 37.8–42.1, C 39.3–40.2.

## The shared swap kit: the pack built in (`bake/`, prepared 2026-11-19 offline; the swap waits for the maintainer's word)

The top session asked for a shared form of the full pack with no switches, in the form of the 0430 bake. The lean build carries no hit counters. The 0x51 packet stays counted only.

- **`ports_pack1.hpp` (baked).**
  - `BC5_P1("KYTY_BC5_P1_<NAME>")` is now the constant `true`, so every site runs the path tested as arm P. Each site's old path is still in the source but can never be taken.
  - The name is checked at compile time with a `static_assert`, so the site's string is not in the binary. Nothing reads the environment, and the `[bc5] ports pack 1: ...=on` line is gone.
  - The hit counters stay in the normal build, always on (no `KYTY_BC5_P1_HITS` word), and are compiled out of lean.
  - The sites' comments "`KYTY_BC5_P1_X=0`: ..." now read "Before the pack: ...".
  - Syntax-checked, normal and `-DBC5_LEAN`, with clang++ `-std=c++20 -Wall -Wextra`: clean. A wrong name fails to compile.
- **`0002-bc5-ports-pack1-baked.patch` (md5 e3124f5d).**
  - The delta on the shared tree: 17 changed files and the new header.
  - Shared patch 0001: d1388db0 → **59f00d27**. Its file list grows from 131 to 134. The exp 0372 lines stay at 5. The guard, learned and JOB_ARENA line counts do not change.
- **`be/policy.cpp` (md5 107bb1b6).** main's policy.cpp (d5ae7298) plus `policy0433.diff`: the 0x51 count, with no change to the packet.
- **`int0433.sh`.**
  - Checks the shared state: patch d1388db0, normal eb85d32e, lean 364c6146, archive 6eac453e, policy.cpp d5ae7298, no `ports_pack1.hpp` in the tree, and both builds including the shared backend source.
  - Takes one lock line and makes copies.
  - Applies the delta and marks the new header with `git add -N`, then requires the diff to be 59f00d27.
  - Puts `be/policy.cpp` in place and rebuilds the archive (it must change and carry the 0x51 line). Rebuilds normal and lean.
  - Checks the strings:
    - no `(KYTY_)BC5_` word gained or lost;
    - no `KYTY_BC5_P1_` text;
    - the 0x51 line in both builds;
    - the hit-count line in normal only.
  - Any failure after the copies runs `undo0433.sh`.
- **`undo0433.sh`.**
  - Restores the 17 units and removes the header (from the file system and the index).
  - Restores policy.cpp, the archive and both binaries.
  - Checks each by md5 and the tree's diff against d1388db0.
  - Run alone, it takes its own lock line. The next step back is exp 0430's `undo0430b.sh`.
- **`test_int0433.sh`: a dry run on a copy.**
  - The world: a local tree that reproduces d1388db0, main's policy.cpp, and fake binaries, ninja and distrobox.
  - Cases:
    - success;
    - undo alone;
    - refusal while old copies exist;
    - success again;
    - a lean build failure that undoes by itself;
    - a wrong tree that stops before the lock.
  - Result: **20 of 20 passed**. The run tree is built by applying patch 0001 to f266548, so its diff is d1388db0, as on the box.

## The shared swap (2026-11-19 12:12–12:26)

The maintainer approved it, through the top session: "Tak i porządki na git". The swap ran as the user unit `bc5-0433-swap` (`bake/run-swap0433.sh`: `int0433.sh`, then `smoke0433.sh`). Raw files are in `raw/swap/`.

- **Before:** patch d1388db0, normal eb85d32e, lean 364c6146, archive 6eac453e, policy.cpp d5ae7298.
- **After:**
  - **patch 0001 59f00d27** (131 → 134 files, exp 0372 lines 5, the pad_audio_route header in);
  - **archive 51db2c91**, the same md5 as the private test archive, so the rebuild reproduced it;
  - **normal efc28a30**, 21 steps, 40 warnings;
  - **lean d8b75137**, 21 steps, 43 warnings.
- **Words:** `+[] -[]` in both builds. The shared builds never carried a `KYTY_BC5_P1_*` word.
  - The 15 words of the switch form are gone with the bake: the 14 fix words and `KYTY_BC5_P1_HITS`.
  - No `KYTY_BC5_P1_` text is in either binary.
  - The 0x51 count line is in both builds; the hit-count line is in normal only.
- **Smokes, all PASS, every one with 0 kernel lines, 0 crash lines and 0 pad keys:**
  - **s433sc:** ASTRO BOT, lean, 200 s.
  - **s433su:** the second title, lean, 300 s, the route by time; all 33 of 33 key lines done. Way 2 shows as compute engine time.
  - **s433sn:** ASTRO BOT, normal, 200 s.
    - It printed hit lines for 12 fixes: ALTSTACK, AMPR_RESULT, APR_FILE_ID, COND_SIGNAL_ONE, EQ_WAKE_ALL, FATAL_TO_ERROR, FAULT_MASK, FILE_UNBUFFERED, NO_COND_REGISTRY, PROT_RANGES, PTHREAD_KEYS and SEMA_UAF.
    - AJM_GAPLESS and AMPR_FILTER did not run in ASTRO BOT's first 200 s. They did run in the second title (step 3b).
    - No switch line was printed.
- **Undo:** `bash ~/bc5-work/exp0433/bake/undo0433.sh` returns to d1388db0 (copies in `~/bc5-work/exp0433/swap`). One step further back is `~/bc5-work/exp0430/kitb/undo0430b.sh`.
- **Repository:** `backend/kytyplus-patches/0001-bc5-lle-agc.patch` is now 59f00d27, the patch the shared builds were built from (D19). The switch form `0002-bc5-ports-pack1.patch` is removed, since the pack lives in 0001; the switch form stays in this branch's history (4cb69cb2, 605b5ff0).
