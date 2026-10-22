# 0203 — Is the cutscene clock voice's next read never requested, or lost in the host's APR path?

**Question.** Experiment 0200 (F259) found the second title's cutscene slow motion to be its clock voice stopping
at the end of a 10-s pass. The clock voice is the silent Wwise loop whose play position the cinematic follows. Its
data, entry +0x7c69535a (0x16a83 bytes) of file 0x7cd713df, was read through the APR path at each pass boundary
until t 280 s of session S1. It came late at 293.6 and 301.6 s, then never again, during a cutscene's streaming
burst (80–125 APR buffers a second, worker q1 3–16 s behind, 1–8 MiB/s). No read failed. So is the next read:
1. never recorded by the title (Wwise did not ask);
2. recorded, but the ReadFile record or the submit failed in the host (EINVAL, EFAULT, "no recorded state");
3. submitted and never run; or
4. run, but its completion (an address write or a kernel event in the same buffer) never reached Wwise, so Wwise
   still waits on it and asks for nothing more?

**Setup.**
- BC-250 dev box, 2026-10-22. The test binary was built 15:40–15:41 under the top session's grant (BOX REQUEST /
  GRANTED, BOX-LOCK).
- `patch_0203.diff` touches KytyPlus `src/libs/libAmpr.cpp` (on top of patch 0001) and adds
  `KYTY_BC5_APR_FILE_JOURNAL=<file id>[,...]` (hex), off by default. It applies to `~/src/KytyPlus` with
  `git apply -p1` (checked, not applied). For the files named it journals on stderr:
  - each ReadFile record: command buffer, offset, size, destination, result, the title's caller one frame up;
  - the address writes, address waits and kernel events recorded into the same buffer (the completion protocol);
  - the buffer's submit: priority, its queue and how many were ahead, submission id, result pointer, command
    counts;
  - each of its commands as it runs: the read with result and bytes, each event trigger's result, each address
    write, and the first unmet address wait;
  - its finish, with result;
  - the erase of its recorded state.
  - With the switch set, any failed ReadFile record, failed submit, failed event trigger or failed address
    write is journaled for every file: the first 200, then every 1,000th.
  - Lines start with `apr journal (exp 0203): mono <CLOCK_MONOTONIC s>`.
- The same patch also adds a candidate fix, `KYTY_BC5_APR_READAHEAD=<n>` (1–16), off by default. It was written
  after O1 while the box was down at 16:36; it is not in the binary built at 15:41.
  - Each priority queue gets n reader threads beside its worker.
  - A reader takes a queued buffer from the first 64 and runs its file reads early. A buffer qualifies when every
    command before its last read is a read, and none of its destinations overlaps an earlier buffer whose reads
    are not finished.
  - The worker still takes buffers in order and runs everything but the reads already done. Events, the
    completion sequence written to 0x90adf7fe0, status writes and finishes therefore keep their per-priority
    order; only the I/O goes parallel.
  - S1's bursts (one serial worker per priority, waiting on I/O, 3–16 s behind) are what it targets. The water
    session's lake patchwork comes from the same reads: sparse tiles filled by APR reads that land late (exp
    0201). So the fix is measured on both the clock voice and the patch share.
  - Built at 17:03:20 under the top session's grant of 16:56 (`rebuild0203.sh`, CPU only, rc 0, only the
    existing warnings; `raw/build-readahead.txt`). The binary is `~/bc5-work/exp0203/kyty_emulator` (md5
    8af7e8ed…); the journal-only one of 15:41 is kept as `kyty_emulator.journal-only`.
  - With the switch on, the readers show as threads `bc5-apr-r<queue>-<k>`.
  - The water session measures the patch share as its exp 0205: A = switch off, B = `KYTY_BC5_APR_READAHEAD=4`,
    alternating arms on its frozen-lake bench, with private saves.
- `build0203.py` compiled `~/bc5-work/exp0203/src/libAmpr.cpp` with the shared build's flags (exp 0195's
  `compdb.json`). It linked `~/bc5-work/exp0203/kyty_emulator` from the shared build's other objects (as of
  10:22:48) in 15 s. The source was unchanged since 2026-10-19 21:17 and its object dates from 10-20 15:01, so
  only this file differs.
  - Warnings: the existing `stringUtils.h` one, and two `-Wformat-extra-args` in existing `amm trace` lines of
    patch 0001 (not this patch).
- The session: `launch0203.sh <tag> [files]` and `after0203.sh <tag>`, as exp 0200's launch/after scripts.
  - It plays from `~/bc5-work/saves-pre-1136` slot 3, with the saves swapped by exp 0196's `ab-restore.sh`.
  - It runs the normal `play-pkg.sh` through `emu0203.sh`: exp 0200's `filt0200.py` and `sample0200.py`, with
    the AJM, AudioOut2 and APR (`KYTY_BC5_AMM_TRACE=1`) traces.
  - It only starts after the top session's GRANTED, with the maintainer at the pad (the route opens with a
    fight, exp 0200).
- The analysis reuses exp 0200's `ana0200.py`, `amm0200.py` and `ajm_wrap.py`.
- Box helpers:
  - `wait0203.sh` starts a run once the box is free (no BOX-LOCK and no emulator for GRACE s), the boot id is
    unchanged, the last journal has no TIMEOUT and no new amdgpu line has appeared.
  - `rebuild0203.sh` rebuilds under its own lock.
  - `chain0203.sh` does the grant of 17:36 in one go: rebuild v2, smoke run S0, then O3 only if S0 passes.
  - `o2-continue.cmd` is the menu input of O2, S0 and O3.
- With the maintainer away from 15:44 (the top session's rule: scripted runs only, one at a time, at most
  ~20 min), there is a first try without the pad: `run0203-opening.sh <tag> [secs] [files]`.
  - It plays the New Game opening on exp 0180/0187's input route (start screen, slot 3, the challenge level),
    with the same switches and traces.
  - The opening's cutscenes are where exp 0153 saw the clock frozen (F198) and exp 0184 saw 0.3× stretches.
  - Saves: `opening-run.sh` itself would overwrite the live saves with `save-backup-0180-0953`. This script keeps
    the live saves aside with `ab-restore.sh`, puts that backup in (slot 3 holds only `.param` files, so New Game
    goes there), and after the run puts the live saves back and checks them with `diff -rq`.

**Result.**
1. **Run O1: the scripted New Game opening (16:01–16:11, 600 s, nobody at the pad).**
   - The waiter `wait0203.sh` started it once the box was free, the boot id unchanged (5329b991), the water run's
     journal free of TIMEOUT and the kernel log free of new amdgpu errors.
   - The live saves were kept in `exp0196/saves-before-160133`, put back after the run and identical
     (`raw/O1-saves.txt`). There were 0 kernel GPU lines.
   - **No clock stop:** the clock ran 1.00× in every 20-s window from t 0 to 580 s (`raw/O1-ana.txt`).
     - The opening's streaming was milder than S1's: the APR workers were in D state at most 374 samples in
       20 s, PSI io full peaked at 32 % at t 240 s and fell to ~0 after t 340 s.
     - The followed cinematic players ran at 1.00× with their debt within ±0.05 s (one at +0.72 s briefly). From
       t 351 s a player held its clip at its end.
   - **The clock voice's read protocol** (`raw/O1-journal-summary.txt`; 8,207 journal lines):
     - Each read of file 0x7cd713df is recorded by the title's stream flush (caller 0x903c7c1ba; exp 0153's
       0x903c7c010) into its own command buffer, followed by three completion commands:
       - a kernel event (eq 1, id 1, data 0x40000000000000NN, a sequence number);
       - an address write of the same number to 0x90adf7fe0;
       - an address write of 3 to the buffer's status word.
     - It is submitted at priority 1 (queue q1), with nothing ahead in O1.
     - All 793 such submits ran at priority 1. All 810 sequence writes to 0x90adf7fe0 ran in increasing order.
       No record, submit, event or write failed.
     - The clock voice's entry +0x7c69535a was recorded and run at each 10-s pass (t 7.2, 17.1, …), within the
       same millisecond. A buffer can also be run again without a new record (t 67.0).
   - So in a run without a stop the path works as designed. O1 cannot tell why S1's request vanished.
2. **Run O2: S1's own end saves, a scripted Continue (16:42–16:52 box time, 600 s, boot ac5dab11, after the
   16:36 machine-down that hit the water session's run).**
   - The start: S1's slot-3 autosave of 15:22:36 (S1 t ≈ 506 s), just before S1's second lagging cutscene. Only
     S1's menu inputs were played (`o2-continue.cmd`: cross at 85 s, down, down, cross, cross), so no fight
     needed replaying. `run0203-opening.sh` takes `SAVES=` and `CMD=` for it.
   - The live saves were kept in `exp0196/saves-before-164205`, put back and identical (`raw/O2-saves.txt`).
     O2's own saves are in `exp0196/saves-before-165217`. There were 0 kernel GPU lines, and the TCP session
     watched the journal.
   - **No permanent stop, but a partial one** (`raw/O2-ana.txt`, `raw/O2-ana5.txt`).
     - A cutscene player ran at t 126–183 s.
     - The clock fell to 0.80× (t 170 s), 0.66× (175 s) and 0.77× (180 s), about 4 s of clock time lost, and
       the player's clip with it (0.71, 0.74, 0.24×). Then it ran 1.00× again.
     - Before it, 0.94–0.97× at t 120–130 s.
   - **The journal shows where** (`raw/O2-journal-summary.txt`). The clock voice's entry was recorded and run
     every 10.0 s (t 14.0, 23.9, …, 148.2 s). Then:
     - recorded at 158.0 s but run only at 160.9 s (APR q1 behind);
     - recorded and run on time at 168.0 s;
     - the next record, due at ~178 s, came only at **181.8 s**, about 4 s late, and ran at 182.7 s.
     - After that it was on time to the end (191.9 … 594.3 s).
     - All 765 submits were at priority 1. All 799 sequence writes to 0x90adf7fe0 ran in increasing order, and
       no record, submit, event or write failed.
   - **What the box did then** (`raw/O2-pressure-150-200.txt`):
     - swap-ins rose to 24,899 a second at t 170.6 s and 43,982 at 182.9 s, with major faults to 46,873 a
       second;
     - PSI memory full 11–14 %, io full 32–48 %, MemAvailable 0.65–1.0 GB;
     - at t 180.9 s every watched thread of the emulator (game-main, the Wwise and archive threads, the APR
       worker) got 0 ms on the CPU for about a second;
     - the APR worker q1 was in D state in 7–19 of its ~20 samples a second around it.
   - So the clock voice starves when its next read comes late. Here the title itself recorded the request late
     while the box swapped, and once the APR queue ran it late. Both recovered, where S1's did not.
   - O2's APR baseline in the cutscene window t 120–200 s: q1 submit→finished median 0.15 s, 95th percentile
     3.4 s, single buffers up to ~62 s (`amm0200.py`).
3. **Read-ahead v1 crashed: the water session's B1 and my O3 both died after 16–17 s.**
   - O3 ran 17:30:47–17:31:03 (`raw/O3v1-play-pkg.log` on the box; v1's O3 files were renamed `O3v1-*`). The log ends in "Access violation: Write
     [000000807ce04020]" in libc's memcpy on a std::thread worker (rdi 0x807ce04020, rdx 0x807ce0ff80, r12 = r14 =
     0xc000), and the host exited with code 65.
   - The live saves were put back and identical (`exp0196/saves-before-173046`).
   - The cause is the design. A v1 reader wrote the file data straight into the guest destination ahead of the
     worker, here 0xc000 bytes into the AMM window. An earlier queued buffer had not yet mapped that page: the
     title maps AMM pages and reads into them through the same queue, so read-ahead must not write guest memory
     ahead of the queue. The overlap check covered only earlier reads, not maps.
   - v2 (`src/libAmpr.readahead-v2.cpp`, now in `patch_0203.diff`):
     - the readers read the file ranges into host memory only (`ReadHostFileToHost`, the same bounds as
       `ReadHostFileToGuest`);
     - the worker, at each read's turn in queue order, checks the guest range as before and copies the data
       in. So every guest write (data, maps, events, the completion sequence) keeps the original order.
     - The host memory held is capped by `KYTY_BC5_APR_READAHEAD_MIB` (default 32).
     - The v1 binary is kept as `kyty_emulator.readahead-v1`.
   - Next: rebuild, then a 240-s smoke run S0 on O2's route. It must survive the 240 s, show `bc5-apr-r` threads
     and "readahead … into host memory" journal lines with in-order copies, and keep the sequence writes
     increasing. Then O3.
4. **Run O3 (to be repeated with v2): O2's route with `EXTRA_ENV=KYTY_BC5_APR_READAHEAD=4`.** The criteria were set
   before the run and sent to the top session with the request:
   1. Mechanism: q1 submit→finished 95th percentile ≤ 1.0 s in t 120–200 s, and every record→run delay of the
      clock voice's entry ≤ 0.5 s.
   2. Safety: no failure line, the sequence writes to 0x90adf7fe0 still in increasing order, no TIMEOUT.
   3. Symptom: clock time lost in t 100–250 s (O2 ≈ 4 s). It is reported, and read only together with 1:
      - 1 met and little lost: supports the read-ahead;
      - 1 met and the same loss: the dip is the late request under swap, not the queue;
      - 1 not met: the read-ahead does not relieve the queue.
      One run cannot separate the swap noise, so 3 alone decides nothing.
5. **v2 rebuilt and smoke run S0 (17:53–17:58, `chain0203.sh`).**
   - Rebuilt at 17:54:07 (`kyty_emulator`, md5 f374ef26…), rc 0, only the existing warnings
     (`raw/chain-S0-O3.txt`).
   - S0: 240 s of O2's route with `KYTY_BC5_APR_READAHEAD=4`. **Passed every check.**
     - It ran the full 240 s; v1 died at 16 s.
     - 12 `bc5-apr-r` threads at +150 s (4 for each of the 3 queues).
     - 377 reads into host memory and 404 in-order copies.
     - 0 decreases of the completion sequence, 0 kernel lines.
     - The live saves were back and identical (`raw/S0-saves.txt`).
6. **O3 (17:58–18:08, 600 s, the same route and switch, `raw/O3-criteria.txt`):**
   1. **Mechanism met.** q1 submit→finished in t 120–200 s: median 0.02 s, 95th percentile 0.42 s (O2: 0.15 and
      3.4 s). Every clock-voice read ran within 0.34 s of its record (O2: one at 2.9 s).
   2. **Safety met.** No failure line, 975 sequence writes all increasing, 626 reads done ahead, no TIMEOUT, no
      kernel line.
   3. **Symptom not settled.** 7.9 s of clock time was lost in t 100–250 s (O2 ≈ 4 s).
      - 5.6 s of it is one GPU stretch: the frame profile at t 120.24 s reads "GPU busy 5614.8 ms", with the game
        thread outside the host for 5,636 ms (`raw/O3-long-frames.txt`).
      - game-main, which writes the clock, slept through it, while the clock voice was read on time and played
        on. When game-main woke, the clock jumped forward.
      - Memory was calm then (1.6–1.9 GB available, PSI memory full ~1 %).
      - About 2.3 s remains in small dips.
      So this run's loss is the long-GPU-stretch question of F254/F256, not the read path.
7. **A save-handling incident, found and fixed.**
   - S0's end restore and O3's start restore ran exp 0196's `ab-restore.sh` in the same second (17:58:17), so
     both used `saves-before-175817`. The second `cp -a` put the live saves inside it (`…/PPSA03671`).
   - O3's end therefore restored S0's run saves into `_SaveData`. Its `diff -rq` passed, because it compared
     against that same copy.
   - Found at 18:09 and fixed: restored the maintainer's saves from `exp0196/saves-before-175408`, which equals the
     copies of 16:42 and 17:30. `diff -rq` is identical and no nested folder is left. The wrong state is kept in
     `saves-before-180916` (`raw/saves-incident-1809.txt`).
   - `run0203-opening.sh` now waits 2 s before each restore and reports any nested copy. The script's owner (the
     compute session) was told.

**Verdict.**
- **The cutscene clock voice stalls when its next read comes late, and the host path itself is correct.**
  - In three journaled runs every ReadFile record, submit, kernel event, sequence write and finish of the clock
    voice's archive succeeded and ran in order.
  - In O2 the next read came late in two ways: once the APR queue ran it 2.9 s late, and once the title recorded
    it ~4 s late during a swap storm (~44k swap-ins a second, every thread stalled ~1 s). The clock lost ~4 s and
    recovered.
  - S1's permanent stop (exp 0200) was the same starvation without the recovery.
  - Which of "not requested" and "requested late" held in S1 cannot be known; S1 ran without the journal.
- **`KYTY_BC5_APR_READAHEAD` (v2) removes the APR queue's part safely.** In a cutscene with the switch on:
  - the q1 95th percentile fell from 3.4 to 0.42 s;
  - every clock-voice read ran within 0.34 s;
  - S0 and O3 ran clean.
  v1, which wrote guest memory from the readers, crashed on not-yet-mapped AMM pages within 16–17 s; v2
  writes only in queue order.
- **Not shown:** that the read-ahead ends the slow motion. O3's clock loss was dominated by one 5.6-s GPU stretch
  (the compute session's question), and the swap-side late requests are the memory-pressure question (the TCP
  session's). One run per arm cannot separate these.
- The switch stays off by default. Turning it on in the launchers is the maintainer's call, after more runs:
  repeats of O2/O3 and the water session's exp 0205 A/B.
