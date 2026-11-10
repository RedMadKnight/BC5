# Audit 0406: host-side safeguards that cost time (audio, pad, FS, APR, threads/sync, system libraries)

2026-11-05, laptop only. I read files and git history in `C:\Users\kjani\Downloads\bc5\bc5-0401` (HEAD 19f9d1df). There was no box access and nothing was edited.
Patch line numbers below refer to `backend/kytyplus-patches/0001-bc5-lle-agc.patch` ("P:line").

## 0. Bottom line

- **Nothing on the host side here is a measured frame lever.**
  - **F482:** on the render thread, host HLE outside the direct path is under 1 %.
  - **F470 (exp 0360):** cutting the two largest per-call host costs on the title's threads, the TLS trampoline and the TSC double read, moved neither flips nor game-main's CPU. The freed time went into the title's own job-wait spin.
  - **0401's night arms:** every single host port runs at or above its base arm (README.md:172-191, 264-288, 385-413).
  - **The real cost is memory and I/O.** The frame rate follows mount reads (F689, r = −0.93), and the mount levers tried so far gave no frames (F814, RR4, RR5).
- **The one consistent all-on deficit is GPU-side, not host-side.**
  - At the start, all-on runs below none on all three nights: sall 22.8 vs s0 23.4, tall 22.9 vs t0 23.6, t6all 22.0 vs t6 22.8.
  - On the 15-minute route, all-on gives 50.6–51.9 against the control rB at 53.4.
  - Every all-on arm carries `BC5_DIRECT_FL_CRUMBS`. Its single arm, scrumbs, was the slowest e4 arm (22.9). README:153 says it "adds end-of-pipe load".
  - This is outside the host scope. It is worth one A/B (FL_CRUMBS=0 against =1 on the route), because it is in his shortcut (README:418).
- **The brief has one error.** t6fwa *was* repeated: base, fwa, base, fwa reached the list at 93, 94, 93 and 93 s, with 23.2 and 23.0 flips/s for fwa against 22.6 and 23.0 for base, all clean (README:410-413).

## 1. Ranked items (likely gain × low risk)

| # | Item | Guards against / source | Evidence still reproducible? | Overlap | Cost | Verdict |
|---|---|---|---|---|---|---|
| 1 | **Main AudioOut blocking wait: a 500-µs poll** (`while (SDL_GetQueuedAudioSize > min) SleepMicro(500)`, P:27002-27022) | Exp 0180: the console blocks until the hardware has room, so the title's clock follows the DAC (F211, F247). Clears the queue after 1 s with no progress. | Yes: F211 and F247 hold the main port ~900–1,000 ms/s | None | **Reasoned, not measured.** ~2,000 wake-ups/s on the title's audio-output thread (nice −15, so it preempts whatever runs on that core). Each wake-up takes SDL's device lock, which it shares with the PipeWire callback. Estimate: ~0.5–1 % of a core plus ~2k preemptions/s. | **merge-candidate**, low gain, low–medium risk: sleep for (queued − min) / `tr_queued_bytes_per_ms` instead of a fixed 500 µs, with a switch. Audio change, so the 0372 replug check applies. No env value gives the old behaviour (the poll *is* today's). |
| 2 | **APR parallel reads spawn threads for every run** (`RunAprReadsInParallel`, up to 7 `std::thread` creates and joins per run of ReadFile commands, P:38327+740-790) | Exp 0112 / F166: serial reads idled the mount, logo 10.9 → 9.0 s | Yes (F166, F287) | Read-ahead leaves these buffers to the worker (exp 0227) | **Reasoned.** Creating and joining a thread with glibc's stack cache is ~15–30 µs. The run rate is not recorded (count the "(parallel)" journal lines). Cost lands on the APR worker threads, not on render. | **keep** `KYTY_BC5_APR_PARALLEL=8`. **merge-candidate**: a persistent pool of 7. Small gain, low risk. Old behaviour: `KYTY_BC5_APR_PARALLEL=0` (serial). |
| 3 | **APR read-ahead** (`KYTY_BC5_APR_READAHEAD=4`: 4 readers per priority queue, so 16 threads; ≤ 32 MiB of host buffers; only buffers ≤ 1 MiB without parallel runs; P:38327+1019-1245) | F267/F273: clock-voice reads arriving late (cutscene queue p95 3.4 → 0.42 s); F287/F288 fix for loads | Measured on 10-22/23, *before* the memory-tight regime (F505, F620, F689) | One global `recursive_mutex` plus one `condition_variable_any` with `notify_all` for all queues, so every submit or pop wakes up to 20 threads | **Measured:** readers 0.53 % of a core (F288); idle 7–11 ms per 10 s (F281); no load slowdown (F287). **Page cache:** the readers read the *same* ranges the worker would, only earlier. The extra footprint is ≤ 32 MiB of anon memory plus one host-to-guest memcpy per buffer, not extra page-cache bytes. | **keep.** The page-cache-competition worry is not supported by the code. One optional arm in a storm-prone free play: `READAHEAD=0`, which is also the old-behaviour value. Optional merge: per-queue condition variables. |
| 4 | **APR parallelism under memory pressure** | Same as #2 | Never A/B'd since F505 | Up to 8 FUSE reads in flight per buffer, beside the title's major faults (swap-in bursts, RR4) | Unmeasured. It could deepen the I/O queue during F689 storms (slow minutes follow PSI io, r = −0.89). | **keep**, low-confidence test arm `PARALLEL=4`. Not a drop. |
| 5 | **bc5-mount disk cache** (`BC5_MOUNT_DISK_CACHE`, `tools/bc5-mount/src/pkg/diskcache.rs`) | F167: start-up 9.0 → 7.9 s | Full at 8 GiB since 10-25, with no eviction (diskcache.rs:181-186 stops writing at the limit) | `POSIX_FADV_RANDOM` on its data file (F398). No fsync. CRC32 per hit. | **Measured (RR5):** the shared cache served 2.2–3.1 of 14–19 GiB; reads 0.7–1.4 ms. A 64 GiB cache cut decode time 91–96 % with no frames gained and no memory change. A hit puts a decoded 256 KiB block into the cache file's page cache, and FUSE then holds a second copy. | **keep** (start-up). The one untested lever is RR4 lever 6, `BC5_MOUNT_DISK_CACHE` unset, in a storm play. Low confidence of gain. This worktree's mount source lacks F690's switches (DROP_BACKING, DIRECT_IO, MAX_READAHEAD). The box mount c39cac9f differs. |
| 6 | **KK06 notify under the internal lock** (`KYTY_BC5_THREAD_SYNC_FIXES`, thr0405-notes:37, 53-60) | Use-after-free when a waiter destroys a cond or mutex in the notify window (KytyPS5 dfec14a) | Correctness, a race | No | The notes say so themselves: "a woken waiter may briefly block on the internal lock". That is an extra futex pair per contended handoff. Pthread cond and mutex only: the Hi workers' ~1,750 wake-ups/s go through *semaphores* (F471, exp 0358), and semaphores are not covered. tthr 24.3 vs t0 23.6. | **keep.** If it is ever suspected: `KYTY_BC5_THREAD_SYNC_FIXES=kk03,signalto,x87,kk07` drops only kk06. |
| 7 | **Mount-table lock held across a FUSE stat** (`GetRealFilename` → `ResolvePathIgnoringCase` → `std::filesystem::exists`, P:13039+1652-1690; FS_FIXES sk05 adds path normalisation under the same lock, fs0405-notes:173-180) | Exp 0022 (the folded-name cache); KytyPS5 a107d1e; sk05 path escape | Yes | No | Reasoned: one getattr per open, serialised over all threads. The open rate is unknown. The APR reads use cached host paths and bypass this lock. sk05 itself is µs-level string work. | **keep.** Optional merge: do the `exists()` outside `m_mutex`. Low gain. |
| 8 | **Pad audio route** (exp 0372, `PadRouteStep` before each pad-port write, P:26402+664-702; `pad_audio_route.hpp` decide(), once-a-second device look) | F500–F504: haptics on the speakers after a replug | Yes: needed and passed (F504; a5, a5r, a6 PASS) | No | ~94 writes/s × 2 pad ports. Each does `SDL_GetAudioDeviceStatus`, two atomic counters and a `SDL_GetQueuedAudioSize` (pad_nb). Once a second it lists SDL's devices. Well under 1 ms/s. | **keep** (required). |
| 9 | **Rumble worker** (F330, controller.cpp, P:35606+1374-1437) | F326/F328: `SDL_JoystickRumble` takes SDL's joystick lock on the audio thread | Yes | It replaces the inline call | Waits on a condition variable with no spin. Writes when the value changes plus a 40-ms refresh while non-zero, so ≤ 25 writes/s. It *removes* cost from the audio thread. | **keep.** |
| 10 | **AUDIO_FIXES=set,room** (aud0401-notes) | AnyPS5 c34ab0258 and 42beeaa46 | `set` cannot be shown on this title (F247). `room` only applies on the timer path, which this title never takes with a sink. | — | One grain copy at SetAttributes (main port 8 ch × 512 × 4 B ≈ 16 KiB, at 94/s ≈ 1.5 MB/s). Negligible. | **keep.** Software replug PASS with set,room (a5r, README:296-299). Old behaviour: unset or `0`. |
| 11 | **NGS2_RACK_FIX** (ao0405: render walk under `g_bc5_racks_mutex`) | KytyPS5: writes into freed rack memory | Correctness | — | One uncontended lock per Ngs2 render grain, ~20 ns. | **keep.** |
| 12 | **Pause clock adjust** (exp 0166: a second rdtsc per `KernelReadTsc` / process-time counter, and long-double maths in `KernelPauseAdjust` per monotonic `clock_gettime`, P:25035+180-240) | F-row of 0166: time catch-up after a pause | Yes | — | **Measured:** F470 candidate B, one rdtsc, "saves nothing measurable". | **keep**. Already tried. |
| 13 | **TLS_FIXES** (tls0405) | KL01: the stubs clobbered RFLAGS (measured, all flags cleared); KL02: a bad prefix scan | Correctness | — | Load time only. `lea` costs the same as `sub`, and the stubs keep their length, so nothing changes per call. The trampoline itself (pushfq/popfq) is game-main's largest host cost (F463: ~6 % of its CPU), but F470 showed removing it moves nothing. | **keep.** If 0360's fast TLS (`BC5_0360_FAST_TLS`) comes back, its `test reg,reg; jz` clobbers the flags, which is exactly what KL01 fixes. It would need a flag-preserving form. |
| 14 | **AUDIO_TRACE=1** (P:26402+861-900) | Diagnostic (F211) | — | — | Per call, two counters and one clock read. One line per second, and only when logging is on or `KYTY_BC5_MEASURE` is set. Negligible. | Dropping it is trivial for play and does not change behaviour (unset). Keep for tests. |
| 15 | **INPUT_RECORD** (P:35606+1440-1500) | Route recording | — | — | An `fflush`, i.e. a `write(2)`, per line, ≤ ~35/s, on SDL's event thread. Axis events take one uncontended lock and a compare. Negligible. | **keep** (scripted routes depend on it). |
| 16 | **SaveData sidecars and ports** (FIXES, EVENT_CB, SORT, MEMORY_FIXES, DELETE_BUSY, ALIASES) | F217, F319, F324; sav0401/svc0405 | — | — | **No fsync/fdatasync found** in libSaveData (P:44349-46623): writes go to a tmp file, then rename. SORT does a recursive walk per search, only at the slot list (9 searches per visit, F319). EVENT_CB starts its thread only when the title registers, and it does not. The `lock` item takes one mutex per GetEventResult poll. | **keep all.** No hot path. A durability note, not a cost: an unsynced sidecar can be lost in a machine-down, as F317 found for the probe. |
| 17 | **EQUEUE_FIXES, MMAP_SHIM_FIXES, SEMA_FIXES, PTHREAD_FIXES, POSIX_RET, ULT, JSON2, FW_*, LOAD_*, NP_SESSION_V2, USER/SYSTEMSERVICE, AUDIOOUT/IN_CHECKS, PAD_OPEN_EXT** | Behaviour ports | — | LOAD_*: live tables keep their exact-key imports (tld0405-notes:54, 147) | A static switch read or one bit test per call. PTHREAD_FIXES adds a thread_local counter per rdlock. The kevent G1 timeout catcher never fired (README:281). The rest is registration only. | **keep.** Each night arm is at or above its base. |
| 18 | **APR wait thread** (`bc5-apr-wait`, a 500-µs sleep loop forever, P:38327+1227-1238) and the worker's `wait_for(500 µs)` when a WaitOnAddress is unmet | F295 | The second title never starts it (F295). Its waits are met by earlier writes (F196). | Exp 0390 (`KYTY_BC5_APR_PARK_TO_WORKER`, private candidate) removes that path | 0 while it is not started | **keep.** 0390 supersedes it when integrated. |

Also checked:
- `KYTY_BC5_MIN_FLIP_RATE=0` only lifts the 30-flip cap (exp 0184). It is not a safeguard.
- A hidden MangoHud costs nothing measured (exp 0301, verdict at line 155).
- `PthreadTakePendingSignal` on the workers (F463) and the per-command open, fstat and close in `ReadHostFileToGuest` are upstream KytyPlus code, not BC5 safeguards. The second is a possible fd-cache merge, unmeasured.

## 2. Recommended order

1. A GPU-side side note for the top session: an FL_CRUMBS A/B on the 15-minute route (the only consistent ~3 % all-on deficit).
2. Memory and I/O arms in a storm-prone play, one switch at a time: `BC5_MOUNT_DISK_CACHE` unset, `KYTY_BC5_APR_READAHEAD=0`, `KYTY_BC5_APR_PARALLEL=4`. These are cheap env-only tests, but gains are unlikely given F814, RR4 and RR5.
3. Code merges, small and low risk:
   - a persistent pool for the parallel APR reads (#2);
   - a computed sleep in the main audio wait (#1, which needs the replug check);
   - per-queue APR condition variables;
   - the mount-lock stat moved outside the lock.

Do not drop any port. None adds measurable hot-path cost.

## 3. Exp 0372 audio rule

- **The rule.** Every audio change needs exp 0372's DualSense replug check before it ships. This is the standing rule in 0391 README:14 and in the bc5-audio-replug-check memory.
- **What counts as an audio change:**
  - `audio.cpp`;
  - the SDL audio driver or backend;
  - `PIPEWIRE_PROPS`;
  - the pad routing;
  - AudioOut2, because its type-0x6 port feeds the DualSense haptics (aud0401-notes, "The replug check").
- **The check, in order:**
  1. The software check: `s6n0372.sh` with `replug0372.sh`, P1 (three pulls) and P2 (`late`).
  2. The maintainer's physical replug: plan A, a DualSense on USB pulled for 5 s, under 1 s and 30 s.
  3. Plan C: a DualShock 4.
- **Which items in this audit trigger it.** #1, #8, #9, #10 and #11. The APR, mount, pthread, FS and SaveData items do not.
- **Where it stands:**
  - The software check passed with `=1` (a5), with `set,room` (a5r) and with fwa (a6).
  - Still the maintainer's: the physical DualSense replug and the DS4 with set,room, and whether the haptics can be felt with `=1`. Under `=1` the silence line for port type 0x6 appears, which is why play uses set,room.
  - Exp 0391, the replug check on the shared build, is still open.
