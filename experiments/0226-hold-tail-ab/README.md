# 0226 — ADR 0013's held tail: a test build, its smoke run, and the A/B

**Question.** Does not holding the title's submitting thread at a cross-queue wait (ADR 0013) remove
the given-up waits of F284, without faults, ring resets or a frame regression?

**Setup.**
- Test build: `patch_0226.diff` against the shared tree's `bc5LleAgc.cpp` (md5 b210fa8e), made by
  `patch0226.py`. Switch `BC5_DIRECT_HOLD_TAIL=1`, off by default; unset, nothing changes. How it
  works is ADR 0013's amendment of 2026-10-23:
  - at a two-ring wait whose writer is not on a ring, the wait is kept for the GPU and the game
    thread's chain (ADR 0010 §B, `BC5_DIRECT_CHAIN=2`) is held;
  - a holder thread `bc5-hold` submits it once the label is satisfied or its writer is on a ring;
  - owner and observe-point flushes wait for that;
  - after `BC5_DIRECT_HOLD_TAIL_MS` (100) the kept wait is dropped, as today's give-up;
  - the host never writes a label.

  The ring consumer (ADR 0013 point 10) is not in it.
- Build: `build0226.py` (as exp 0219's). The binary is `~/bc5-work/exp0226/kyty_emulator`.
  - First build: 2026-10-22 23:25:32–23:26:04, against the shared objects of 22:11 (after exp 0222),
    rc 0, the 4 warnings that were already there (`raw/build-20261022.out`). The smoke run tcpH1 used
    it.
  - Relinked 2026-10-23 12:29 (md5 2205598e), the same source. It picks up the shared libAmpr.o of
    11:30 (libAmpr.cpp md5 5f2ec30b: the APR CV wait, F281, and the read-ahead fix, F287/F288). The
    A/B and the maintainer's play use this one (`raw/build-20261023.out`).
  - Later changes to the shared builds are not in it. F301's ATRAC9 decoder went into them at
    2026-10-23 19:28, after this link, so the A/B compares the held tail against today's path of
    this binary, not against the shared build of the evening.
- Runs: `run0226.sh bench <A|B> <tag> [secs]`, the lake bench, the same binary for both arms.
  - A: the switch unset; B: `BC5_DIRECT_HOLD_TAIL=1`.
  - Old launcher values pinned (`FLAT_APERTURE=0`, the old skip list; `AMM_PRT` absent), the default
    8-ms limit, no traces.
  - Attended, on the box supervisor's grant, with the maintainer reachable for a reboot. A passive
    watcher reads only the kernel log and the journal, and stops nothing. The rule is to stop at the
    first fault, ring timeout or reset line, with no retry of the binary that night.
- Risk: a new submission path. Exp 0063's earlier deferral reset rings, and a GPU hang can take the
  machine down (F262).
- `play0226.sh`: the maintainer's own play with the switch, on the current launcher defaults. He
  starts it himself; it copies his live saves aside first and writes a BOX-LOCK naming him.
- Committed in `raw/`:
  - per run: the bench output, the environment 60 s in, the arm, the journal path, `*-journal-lines.txt`
    (the hold summaries, give-up, two-ring, chain and timeout lines), every 50th frame-profile line,
    and the emulator's fps-counter lines;
  - the comparison `ab-tcpH2-H5.txt` and both build logs.

  The full extracts (3–7 MB each), the emulator logs and `patch_0226.diff` are in
  `~/bc5-work/exp0226` on the box. `patch0226.py` regenerates the diff from the shared file.

**Result.**

*Smoke run tcpH1* (arm B, 300 s, 2026-10-22 23:26–23:31):
- Clean: 0 fault lines, 0 ring timeout or reset lines, 0 fence timeouts, same boot, no new amdgpu
  line. The watcher saw no fault line.
- 14,291 holds, about 48 a second:
  - released with the writer on a ring: 13,479;
  - with the label satisfied: 810;
  - given up at the 100-ms bound: 1, on 0x12004b3c38.
  - Held 0.91 ms on average and 34.6 ms at most, apart from that one. The first holds came in the
    load at t 2.3 s and were released 0.25–0.8 ms later.
  - These are the two-ring waits that the Render Thread used to sit out (F228: about 1.7 a frame,
    0.4 ms each).
- No other give-ups: no "cpu-wait … GIVEN UP" line and no "two rings … NOT served". tcpW8, the old
  path at the same settings, had 13 in 600 s.
- Frames, t 150–290 s: 28.4 flips/s; 19 seconds with a gap over 100 ms, 2 over 250 ms
  (`raw/tcpH1-emu.log`). tcpW8 over t 150–590: 28.8 flips/s, 8 and 2. The windows differ, so this
  is for the A/B to settle. One candidate cost: the flip's drain now waits for a held chain.
- The journal's frame profile over the same window: 3,924 frames, 35.7 ms each on average, 18 over
  100 ms. The game thread spent, per frame:
  - 5.79 ms inside the host, of which 0.52 ms in label waits;
  - 17.70 ms at the flip;
  - 12.19 ms outside the host.

  The A/B gives the same split for arm A (`ab0226.py`), and so shows whether time moved from the
  label waits to the flip.
- The box was rebooted by a user command at 2026-10-23 00:05:34, during the maintainer's ASTRO BOT
  play after this run. The kernel stream ends with the shutdown broadcast and has no amdgpu line
  before it.

*A/B*, 2026-10-23 23:17–23:59, after a reboot (boot bac6c7e0; the 28 amdgpu lines at boot are
display noise and were taken as the baseline). The runs alternated: tcpH2 A, tcpH3 B, tcpH4 A,
tcpH5 B, 600 s each. The relinked binary (md5 2205598e), the maintainer reachable, a passive watcher.
- All four clean: 0 fault lines, 0 ring timeout or reset lines, 0 fence timeouts, the same boot, no
  new amdgpu line.
- `ab0226.py` (`raw/ab-tcpH2-H5.txt`), window t 150–590 s (the frozen view):

| | A: tcpH2 | A: tcpH4 | B: tcpH3 | B: tcpH5 |
| --- | --- | --- | --- | --- |
| waits given up (cpu-wait GIVEN UP) | 10 | 18 | **0** | **0** |
| two-ring waits "NOT served" | 26 | 30 | 0 | 0 |
| holds (writer on a ring / satisfied / given up) | – | – | 31,383 (29,375 / 2,007 / 0) | 32,476 (30,043 / 2,432 / 0) |
| hold time, mean / max | – | – | 1.05 / 58.7 ms | 1.10 / 314.6 ms |
| flips/s | 28.1 | 28.2 | 29.3 | 28.9 |
| seconds with a gap over 100 ms | 44 | 36 | **10** | **12** |
| seconds with a gap over 250 ms | 11 | 20 | **0** | **2** |
| journal frames over 100 ms | 49 | 37 | 10 | 13 |
| mean frame | 35.6 ms | 35.4 ms | 34.1 ms | 34.6 ms |
| game thread inside the host / frame | 6.35 ms | 5.75 ms | 4.28 ms | 4.91 ms |
| … of it label waits | 1.17 ms | 1.51 ms | 0.50 ms | 0.58 ms |
| … at the flip | 16.56 ms | 19.05 ms | 19.91 ms | 19.29 ms |
| … outside the host | 12.65 ms | 10.57 ms | 9.90 ms | 10.37 ms |

- The arms' means:
  - give-ups 14.0 against 0.0;
  - 28.17 against 29.11 flips/s;
  - seconds with a gap over 100 ms 40.0 against 11.0, over 250 ms 15.5 against 1.0.
- tcpH1's 19 seconds over 100 ms in t 150–290 were that window. Over t 150–590 the held tail has
  about a quarter of the long gaps of today's path.
- The one hold past the 100-ms bound, 314.6 ms in tcpH5, came in the load before the frozen view
  (between the summaries at t ≈ 120 and 150 s). There the game thread spent up to 76 ms inside the
  host on one frame (sync 29, prepare 32). The holder does not touch a chain whose owner is inside
  `Direct::submit`, so the bound is checked only once the owner leaves it. The hold ended released,
  with the writer on a ring or the label satisfied, and no wait went to the GPU without its writer.
  But the bound is not strict while the owner sits in long submits.
- The 2026-10-23 22:59 fault in the maintainer's play (shared build, today's defaults) is not part
  of this experiment and has its own.

**Verdict.** Passed, at the lake bench with the old launcher values and the 8-ms default.
- **The held tail removes the given-up waits.** 14 a run on today's path against 0, and the two-ring
  waits that today's path does not serve go with them.
  - About 50 holds a second replace them, released after 1.1 ms on average, nearly all with the
    writer on a ring.
  - So the waits F284 traced to the host's held thread are released by the title itself, as soon as
    its thread is free.
- **Frames improve, with no regression.**
  - Long frame gaps fall to about a quarter: seconds over 100 ms 40 → 11, over 250 ms 15.5 → 1.
  - Flips/s rise by ~3 %.
  - The game thread's time inside the host falls by 1.5 ms a frame (label waits −0.8 ms). Its wait at
    the flip rises by 1.8 ms, the held work now going to the GPU there, but less than what it saves.
- **No faults, ring timeouts or resets** in 4 × 600 s plus the smoke run, with no wait left to the
  GPU without its writer.
- **The 314.6-ms hold is benign.**
  - The bound lives in `hold_release()`. The holder skips an owner inside `Direct::submit` (ADR 0010
    §B.3), and owner and observer flushes return early while the chain has no segments yet. So in a
    load with long submits the check can slip.
  - But only to the next flip: `drain()`'s owner flush ignores `in_submit` and waits for the bound.
    A hold cannot outlive its frame or stay unreleased, and it never holds the title's thread.
  - An optional improvement for later is to have the owner release on leaving each
    `Direct::submit`.
- **Not done:** the ring consumer (ADR 0013 point 10). And the A/B was two runs per arm, at one bench,
  with the old launcher values.

**Integration** (the maintainer's yes, 2026-10-23, in the box supervisor's session: "jest moja
zgoda"; the supervisor applies it).
- `patch0226i.py` makes `integration_0226.diff` (also `~/bc5-work/exp0226/integration/`: the full
  file, md5 a0018272, and the diff), against the tree's `bc5LleAgc.cpp` (md5 b210fa8e).
- It is the tested code with the default flipped: the hold is on unless `BC5_DIRECT_HOLD_TAIL=0`.
  Against the A/B's source only two comments and `hold_on()` differ.
- Where it acts: only with `BC5_DIRECT_CHAIN=2`, a compute ring (`BC5_DIRECT_COMPUTE_RING` ≥ 0) and
  `BC5_DIRECT_CROSS_RING_WAITS=all`, on the game thread's graphics buffers.
  - The second title's `play-pkg.sh` has all three, which is what was tested.
  - ASTRO BOT's default `play-astro.sh` (`bc5-run.env`) sets no compute ring, so the hold is inactive
    there.
  - `play-astro-compute.sh` does set the compute ring, so the hold acts there. That is untested.
