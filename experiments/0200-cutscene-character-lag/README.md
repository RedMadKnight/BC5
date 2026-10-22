# 0200 — Why the cutscene characters lag behind hair, effects and sound: their clock voice stops at a loop end when its streamed data is not read again

**Question.** In the second title's in-game cutscenes the characters move in slow motion, or lag behind, while hair,
effects and the sound run in real time. The maintainer saw it in all four sessions of 2026-10-22 (1056, 1136, 1337,
1345), with the compute-state prefix on and off, at 30–37 and at 45–50 flips a second (F254, F256). What sets the
characters' time in a cutscene, and which input makes it slow? Does it follow the memory stalls of F256, or the
title's clock inputs (flip and vblank timing, the audio grains of F247)?

**Setup.**
- BC-250 dev box, 2026-10-22 14:00–15:30. Kernel 7.2.9-ogc3.1, Mesa 26.2.4 (as in exps 0196/0198).
- One play session was launched for this experiment: S1, 15:14–15:26, with the maintainer at the pad (result 7).
  The live sample of result 4 was taken read-only on exp 0199's watched session, after the maintainer reported a
  slowdown in it.
- Kept logs of the sessions:
  - 1136 (exp 0196, `~/bc5-work/exp0196/play-pkg-cs1.log`) and 1345 (exp 0198 arm B,
    `~/bc5-work/exp0198/play-pkg-armB.log`): the fps counter and the host's AudioOut port trace, once a second.
  - Their journals (`~/bc5-data/captures/play-20261022-*/gc/direct.log`). Only a 4-MiB block of 1345 was sampled,
    read with `O_DIRECT` so the page cache was left alone.
  - The pad recording of 1345 (`~/bc5-work/exp0200/route-record-armB-1345.txt`; the live file is overwritten by each
    session).
  - The play logs of 1056 and 1337 were not kept.
- Code read from the running title's memory through `/proc/<pid>/mem` (yama `ptrace_scope` is 0 on the box, so no
  attach and no stop).
  - During the water session's scripted runs (exp 0197, 14:03–14:29).
  - From 14:33 to 14:40, during the run started 14:30:56. That was exp 0199's watched run (normal binary,
    `BC5_DIRECT_AMM_PRT=1`), not a water run, which I only noticed afterwards; that session was told. It was
    memory reads only, with no disk reads.
  - Disassembled with `objdump -b binary` on the box. Only addresses and behaviour are recorded here; no code
    bytes are in the repo.
  - The pieces read: the clock writer around 0x903b87fc1, the players' tick loop 0x903b880c0–0x903b88217, and the
    clip-advance function 0x903b77670.
  - Callers were found with `scan_mem_calls.py`, which looks for direct calls in the text 0x900000000–0x905f24000.
- New tools, here and in `~/bc5-work/exp0200`:

  | File | What it does |
  |---|---|
  | `sample0200.py` | Outside sampler, read-only, 20 Hz. It reads the sync clock, the cinematic players' clip time, advance, debt, rate and path flags, two global time doubles and the wrap period. Once a second it also writes `/proc/vmstat` deltas (compaction stalls, major faults, swap-ins, alloc stalls), PSI memory/io/cpu, MemAvailable, and per watched thread (game-main, the `AK::` Wwise threads, the archive threads, `bc5-apr-q*`, the render and present threads) the schedstat run and wait ms with R/S/D state counts. |
  | `find_player.py` | Finds the main cinematic players in the 104-MiB pool at 0x1070000000 (where exp 0153's player was). Synced players are found by the unwrapped clock at +0x110. Unsynced ones are found by a vtable learned from the synced ones. It runs as a child process at nice 19, every 20 s, in under 1 s. |
  | `filt0200.py`, `emu0200.sh` | A `BC5_EMU` wrapper, as in exp 0186's `emu-ts.sh`. `KYTY_BC5_AJM_TRACE` decode jobs go into a mono-stamped index, and the APR lines of `KYTY_BC5_AMM_TRACE=1` (submit, read, finished) go into their own file. Everything else goes to the play log. |
  | `launch0200.sh`, `after0200.sh` | One measured session from `~/bc5-work/saves-pre-1136`, slot 3, through exp 0196's `ab-restore.sh`, which keeps the current saves aside. `after0200.sh` puts the maintainer's saves back and collects the logs. |
  | `ana0200.py`, `amm0200.py` | Per window on journal time: clock, clip, debt, rate, clock-voice decode speed (the 479,352-sample passes of F242), AudioOut2 advances/pushes, flips, pressure and threads, plus the clock voice's playing id and the host's AJM instance counter. `amm0200.py` adds submit→finished per APR worker and the bytes per file. |
  | `ajm_wrap.py` | From an AJM index: instances in order of first job, the wraps of the 14-bit slot counter, and the clock-voice instances with their last job and first job that wrote nothing. |
  | `patch_0200.diff`, `build0200.py` | `KYTY_BC5_AJM_UNIQUE_IDS` in KytyPlus `src/libs/ajm.cpp` (result 6), and the one-file rebuild of a test binary `~/bc5-work/exp0200/kyty_emulator`, as exp 0195's `build0195.py`. |

- Tool test: `sample0200.py` read-only on the water session's run of 14:21 (exp 0197, lake save, scripted, Photo
  Mode), from 14:23 to 14:29. Output: `raw/test-water-ana.txt`. A 50-s check of the final format was taken on the
  14:31 run.
- Raw:
  - `raw/audio-port0-play-pkg-cs1.txt` (1136) and `raw/audio-port0-play-pkg-armB.txt` (1345): every second of the
    main port off 0.98–1.02, with clears, or held under 900 ms.
  - `raw/test-water-ana.txt`.
  - `raw/L1-sample.txt` and `raw/L1-ana.txt`: the live sample of 14:47–14:50 (result 4).
  - Session S1 (result 7):
    - `raw/S1-ana.txt` (20-s windows), `raw/S1-amm-windows.txt` (APR per 20 s), `raw/S1-clock-voice.txt` (the
      clock voice's reads and pass boundaries), `raw/S1-ajm-wrap.txt`, `raw/S1-start.txt` and the restore lines.
    - Too large for the repo, on the box in `~/bc5-work/exp0200/raw/`: the sample (2.2 MB), AJM index (40 MB),
      APR trace (10.5 MB), play log, frame profile, pad recording.
  - `raw/ajm-wrap-kept-indexes.txt`: `ajm_wrap.py` over the kept AJM indexes of exps 0185–0188
    (`~/bc5-work/dump-*/ajm-index.txt`).
  - The pad recording and the 14:30 session's play log (`~/bc5-work/exp0200/raw/L1-play-pkg.log`) stay on the box.

**Result.**
1. **The kept logs hold no input of the characters' clock, and the title's sound output ran at real time through
   the cutscenes.**
   - The journal (`BC5_DIRECT_JOURNAL=min`) is GPU timing only (frame profile, submissions, flips).
   - The AudioOut trace of the 8-channel main port (94 pushes of 512 frames a second, held by the host ~999 ms):
     - 1345: at 1.000 (0.98–1.02, 0 clears) in every second from t 238 to 484 s, the stretch with the
       cutscenes (44–49 flips a second; pad recording: no input or only cross presses).
     - 1136: the same over t 210–450 s, except 259 s (0.968), 289 s (0.404, the 2.4-s GPU frame) and 432 s
       (0.692, the 9-s GPU frame).
   - Over the whole of 1345 (677 s), 20 seconds after the start were off rate, most of them after t 484 s. About
     1.4 s of sound was lost net.
   - So the Wwise engine pushed its mix at real time in the slow cutscenes. A held or starved audio thread does
     not explain a sustained slow motion.
2. **How the characters' time is made (code read; extends exp 0153 result 3).**
   - game-main reads the clock as `GetSourcePlayPosition(playingId, &ms, false)`: the third argument is 0, so
     there is no extrapolation. It stores `ms × 0.001` at 0x90ae007b4.
   - The function that does this (0x903b87b40, struct 0x90ae007a0) is handed an array of cinematic players, which
     its caller 0x903b88270 builds from a component query.
     - The main player is the one with +0xc8 == 1. It ticks with the frame dt.
     - The others tick with the main player's last advance (+0xfc) divided by its source rate.
   - The clip advance 0x903b77670 for a main player synced to the clock (+0xc9 == 1, +0x120 & 3 == 3):
     - `dt' = dt / *(double*)0x90bee5f48`. The divisor read 1.0.
     - `err = target(+0x114) − dt' + debt(+0x100)`; `added = dt' + 0.02·err`; `debt = 0.98·err` (exp 0153).
     - **Then `added ×= rate`**, where rate = clamp(+0x108, 0.0001, 4.0). It is also multiplied by
       `(+0x560)->+0x50` when the sync source's +0x30 & 0x80, and forced to 1 when +0x4c & 8.
     - Finally `clip = min(clip + added, source length +0x3c)`.
   - The rate is applied after the filter, so nothing corrects it. The clip runs at rate × the clock's speed, and
     the debt stays near 0.
   - A player that is not synced takes the frame-dt path instead: the double at 0x90bee5f98 (0.0215 s when read)
     × the rate. That path is clamped at 0.133 s a frame, and the excess is paid back at up to 0.25 s a frame.
   - **What follows:** the characters run slower than the sound only if (a) the clock (the master voice's play
     position) runs slower than real time, (b) the rate is below 1, or (c) the cutscene's player is not synced
     and its frame dt is short.
   - A stall alone does not make slow motion. While the game thread stands still the clock runs on. Afterwards
     the slew pays the debt back at 2 % a frame: the characters catch up at up to ~3× for ~50 frames. That is a
     jump forward after each freeze, not slow motion.
   - The frame dt and the divisor change only the transient.
3. **Tool test on the water run (`raw/test-water-ana.txt`).**
   - In gameplay the clock ran 1.00× in every 10-s window.
   - An ambient cinematic player (0x10705b90c0, a 15-s loop) followed it at 1.00× with debt −0.015..+0.066 s.
     Its +0x110 is the clock unwrapped: it counts on past the 10-s wrap.
   - In Photo Mode the clock stopped (0.00 for 60–90 s) and a player held.
   - The finder's first, loose version matched hundreds of objects while the clock sat at 9.993 s. The kept
     version also checks the sync source pointer, the clip time and the debt, and returns none there.
   - The water run had MemAvailable 4.1 → 0.74 GB and PSI io full up to 57 % (avg10). The 14:31 run went down to
     0.38 GB. The audio manager thread used 15–55 % of a core.
4. **Seen live, 14:46–14:48, in exp 0199's watched run (journal `play-20261022-1430`, normal binary with
   `BC5_DIRECT_AMM_PRT=1`, the maintainer playing).**
   - The maintainer reported "teraz scena ma spowolnienia" (the scene is slowing down now), and I started
     `sample0200.py` at 14:47:00 (`~/bc5-work/exp0200/raw/L1-sample.txt`, read-only).
   - **The cinematic clock sat at 9.993 s, the end of the clock voice's 10-s pass, for at least 84 s.** It was
     frozen before the sampler started.
   - Meanwhile the main AudioOut port ran at 1.000 (94 pushes a second) and the game at 41–45 flips a second.
   - The followed cutscene players (0x10705b90c0, then 0x1071e6ed70, vtable 0x909261b30, path flags 14:
     synced, source rate 0.996, rate 1.0) had their clip time crawl at 2–7 % of real time. The debt stayed at
     −1.0..−1.16 s, the filter's steady state for a clock that stands still (−49·dt).
   - 0x1071e6ed70 went away at t+80 s. Four seconds later the clock restarted from 0 and ran at 1.00× again.
   - The clock's table entry (index 0 at 0x90ae007bc; the table at `*(0x90bede218)`) still held playing id
     0x19b9 throughout. That id was posted early in the session; the live voices' ids were around 0x5a00.
   - The analysis is `raw/L1-ana.txt`, 5-s windows on that session's journal time; the sample itself is
     `raw/L1-sample.txt`. The clock read 0.00× in every window from t 965 s (the sampler started at 964 s) to
     1040 s. It restarted at t 1048 s and read 1.00× from 1050 s on.
   - **The freeze does not follow the memory stalls.**
     - From t 965 to 1005 s memory was quiet: 2–51 major faults a second, PSI memory full 0.00–0.03, io full
       about 1 %, 44–47 flips a second. The clock stood still all the same.
     - The pressure spike (t 1015–1050 s: up to 5,238 major faults a second, memory full 4–9, io full 6–21 %,
       14–30 flips a second) came in the middle of the freeze and did not end it.
     - The Wwise audio manager thread ran 42–82 % of a core and waited 10–30 ms per 5 s for a CPU.
   - So in this slowdown the characters' clock was a stalled master voice: case (a), with a real-time mix.
5. **A host defect that stalls exactly such a voice: AJM instance ids are reused while live.**
   - KytyPlus `src/libs/ajm.cpp` (f266548 on the box; the same at upstream 3eee96a :639–650 and in KytyPS5):
     `AjmInstanceCreate` makes `id = codec << 14 | (g_ajm_next_instance++ & 0x3fff)`, then sets
     `g_ajm_instances[id] = state`.
   - After 16,384 creations the slots come round again. A new instance then replaces any still-live instance
     on the same slot, so the old voice now decodes through the new one's decoder.
   - `AjmInstanceDestroy` of either one erases the shared entry. From then on every decode job of the other
     returns `AJM_RESULT_INVALID_PARAMETER` with 0 bytes (`AjmDecodeInstance`, :421–425), so that voice gets no
     PCM and Wwise does not advance its position.
   - The victims are long-lived voices: the silent clock voice, played all game long from early in the session
     (F242), first of all.
   - AnyPS5 skips ids that are still live and fails with OUT_OF_RESOURCES only when all 16,384 are taken
     (`core/libs/prx/libSceAjm.native/src/Ajm.cpp:1723–1740` @ 27c88a8, GPL-2.0).
   - Rate: in fights the title creates up to 3,010 decoder instances a minute (exp 0185), so the counter wraps
     within about 5–6 minutes of combat. That fits the slow motion appearing in longer sessions and after
     fights (F254, F256), and not in the short idle and opening runs of exp 0188 (M5, M6, O6).
   - The kept AJM indexes confirm the wrap (`ajm_wrap.py`, `raw/ajm-wrap-kept-indexes.txt`).
     - Exp 0185's long fighting run L1 (772 s, 10,749 instances that decoded) wrapped the counter at 406 s.
     - The idle night runs L2–L8 and M0–M6 (200–360 instances in 7–13 min) and V1 (3,247 in 292 s) did not.
   - A wrap does not always hit a live voice. The counter is shared by all codecs, so a live Opus voice is
     replaced only when its slot comes round to another Opus instance.
     - In L1 the clock voice 0x607b8 (from 208.8 s) kept its passes to the end: slot 0x7b8 came round at about
       432 s to a codec-1 instance (0x47a0–0x47a9 were created then).
     - The run before the wrap's clock voice, 0x60001, had ended at 114 s, and the new 0x60001 at 406 s was
       another sound.
     - The dump index logs only jobs that wrote bytes, so failed decodes cannot be seen in these files.
       `filt0200.py`'s trace index keeps them.
   - **Not verified:** the counter's value at the freeze. The machine went down (~14:50, during exp 0199's run)
     while I was reading `g_ajm_next_instance` (binary offset 0x1174490) and the map header; the TCP session has
     that timeline. The reads were read-only `/proc/<pid>/mem` preads of the emulator's own data.
6. **The switch and a test binary (built 15:04, not yet run).**
   - `patch_0200.diff` touches only KytyPlus `src/libs/ajm.cpp`. It applies with `git apply -p1` to
     `~/src/KytyPlus` (checked, not applied). The shared tree, `kytyplus-build` and `-lean` are untouched.
   - The switch is `KYTY_BC5_AJM_UNIQUE_IDS`, off by default.
     - `=log` keeps the old ids and journals on stderr each id assigned over a live instance, with both
       instances' codec, the old one's age, jobs, bytes and decoded samples, and the counter and its wrap
       count. It also journals each destroy of an id not present, and the first decode on a missing instance
       (then every 1,024th).
     - `=1` ports AnyPS5's rule (`libSceAjm.native/src/Ajm.cpp:1723–1740` @ 27c88a8, GPL-2.0, named in the
       header comment): a live id is skipped, and `AJM_ERROR_OUT_OF_RESOURCES` (0x80930007, its line 37) is
       returned only when all 16,384 ids are live. Each skip is journaled.
   - With the switch off the only change is four per-instance counters, used by the journal. The
     `KYTY_BC5_AJM_TRACE` and `KYTY_BC5_AJM_DUMP` hooks of exps 0183/0186 are unchanged.
   - `build0200.py` compiled the file with the shared build's flags (exp 0195's `compdb.json` of 10:43). The
     only warning is the existing one from `stringUtils.h`. It linked `~/bc5-work/exp0200/kyty_emulator` from
     the shared build's other objects (as of 10:22:48) in 14 s, under a short BOX-LOCK; no GPU was used.
   - The counter `g_ajm_next_instance` is at offset 0x1174e10 in that binary.
   - Not run yet: it needs the title, so the GPU and the maintainer.
7. **Session S1 (15:14–15:26, the maintainer at the pad; `launch0200.sh S1 log`).**
   - The run: the test binary with `KYTY_BC5_AJM_UNIQUE_IDS=log`, from `saves-pre-1136` slot 3, with the normal
     launcher's skips and the TF ring.
     - The sampler's first 26 s read the AJM counter at a wrong base (the first mapping, 0x40000). It was
       restarted with the binary's own mapping (fixed in `sample0200.py`); both runs appended to
       `raw/S1-sample.txt` (box).
     - The maintainer reported "teraz, jest lag" (now, there is lag) at about 15:21 and a second lag later. They
       added that the background sound, effects and music play, but no new sounds come.
     - The game was closed from SSH at 15:26 on the maintainer's word. The saves were put back
       (`raw/S1-restore-back.txt`; S1's own saves are in `~/bc5-work/exp0196/saves-before-152617`).
     - 0 kernel GPU lines.
   - **The freeze was the same as in L1:** the clock stood at 9.993 s from t 320.5 s to the end (t ≈ 710 s).
     - The followed players' clip time crawled at 3–5 % with the debt near −1.0 (`raw/S1-ana.txt`).
     - The audio port stayed at 1.000, and AudioOut2 advances equalled pushes.
   - **It was not the AJM ids.** The counter stood at 4,071 during the lag and at 4,848 at t 520 s, never near
     16,384. There was not one "reused", "missing" or "not present" line (`raw/S1-ajm-ids.txt`, empty).
     `ajm_wrap.py`: 3,801 decoding instances, slots up to 0x1495, 0 wraps (`raw/S1-ajm-wrap.txt`).
     Result 5's defect is real, but it did not cause this freeze.
   - **The clock voice is a stream, and its next loop was never read** (`raw/S1-clock-voice.txt`).
     - Its data is one 92,803-byte entry of file 0x7cd713df (+0x7c69535a).
     - The APR path read that entry at the voice's start (t 8.7 s), at its new instance (140.4 s), and within
       0.1 s of 26 of its 27 pass boundaries from 18.6 to 280.3 s (none at 78.5 s).
     - Then 290.3 s was read only at 293.6 s and 300.3 s at 301.6 s. After that it was never read again, while
       other reads went on to the end.
     - The clock voice's AJM instance 0x60009 got its last decode job at t 320.44 s, exactly at the end of its
       pass (480,000 samples total, the pass full at 479,352). There was no failed (0-byte) job: it was simply
       not fed again.
     - No read in the session failed or came back short.
   - **What the stream ran into: a cutscene's streaming burst on a slow, serial APR path**
     (`raw/S1-amm-windows.txt`, 20-s windows).
     - From t 280 to 400 s the title submitted 80–125 APR buffers a second (4,958 in t 280–320 s), against
       17–42 a second in t 160–280 s.
     - Time from submit to finished grew to a mean of 3–16 s on worker q1, 2–10 s on q3, and up to 129 s for
       single buffers.
     - Throughput fell from 65–72 MiB/s (t 140–200 s) to 1–8 MiB/s (t 420–500 s).
     - The three APR worker threads were in D state (waiting on I/O) in 35–85 % of samples, with PSI io full at
       26–42 % and MemAvailable at 0.55–0.70 GB (`raw/S1-ana.txt`).
     - The cutscene's animation stream `animstrm` (file 0x628c6db3, exp 0153) went 74 s without a read
       (t 300–374 s).
     - Wwise's `AK::IOThread` went on running, and by t 520 s the queues kept up again (submits ≈ finished),
       yet the clock voice's entry was not requested again.
   - **S2 (the AJM fix) was not run:** S1 showed it could not have changed this freeze.

**Verdict.** The cutscene slow motion is the cinematic clock, Wwise's play position of a silent 10-s looping
voice, stopping at the end of a pass while the rest of the mix plays on. The characters then crawl at 2–8 %
(the slew filter of exp 0153 with a stopped clock). The maintainer also heard no new sounds start.
- In S1 the voice stopped because its next loop's data, a 92.8-KB read from file 0x7cd713df that came every
  10.0 s before, was never read again. This began at the onset of a cutscene's streaming burst, when the host's
  APR queues fell 3–16 s behind on average and up to 129 s, at 1–8 MiB/s with the workers waiting on I/O.
- Ruled out as this freeze's cause:
  - the memory stalls themselves (L1: the freeze began with memory quiet);
  - the frame rate and the slew filter (both pass a running clock at 1.00×);
  - the AudioOut2 grains (a/p = 1);
  - AJM decode failures and the AJM id reuse (S1: counter at 4,848, no reuse).
- The id reuse (result 5) is a real host defect of its own; the switch is ready in a test binary (result 6).
- Open:
  - why Wwise never asked for the block again. A request lost or never completed in the host, or a Wwise
    stream that gives up after starving, are the two candidates.
  - whether a faster or more parallel APR path prevents the stall. The host runs one serial worker per
    priority through the FUSE mount; the console reads at GB/s.
- Next: journal every ReadFile command of file 0x7cd713df when it is recorded and when it is submitted, to tell
  "not requested" from "requested and lost". Then a second APR worker per priority (or Wwise's reads ahead of
  the bulk) behind a switch, tried on the same route.
