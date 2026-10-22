# 0214 — APR read-ahead on by default

**Question.** Does exp 0203's APR read-ahead (`KYTY_BC5_APR_READAHEAD`, v2) show any regression in the runs made
with it? And does it then work in the shared builds with no switch set? It goes in under the maintainer's rule of
2026-10-22, relayed by the top session: "jeżeli w wyniku jakiegoś eksperymentu - nastąpiło przyspieszenie i nie
nastąpiło pogorszenie, ale nie znaleziono przyczyny błędu, to taką poprawkę wprowadzamy do użytku". In short: a
speed-up with no regression goes into use even without the root cause.

**Setup.**
- The speed-up is exp 0203's (F267). With the switch at 4, a cutscene's APR queue q1 had a 95th-percentile
  submit→finished time of 0.42 s instead of 3.4 s.
- Regression data: the GPU journals (`~/bc5-data/captures/play-20261022-<HHMM>/gc/direct.log`) of every run on exp
  0203's test binary (`~/bc5-work/exp0203/kyty_emulator`; arm A1 ran its v1 build with the switch off):
  - the water session's exp 0205 lake bench, the same route, about 277 s each:
    - A1 (1722), A2 (1830), A3 (1835): switch off;
    - B1b (1811), B2 (1825), B3 (1840): switch at 4. B3's camera ended at another angle, so it has no patch score,
      but its frames count.
  - exp 0203's cutscene route, 600 s each: O2 (1642, switch off) and O3 (1758, switch at 4).
- `ra0214.py` reads each journal with O_DIRECT at 15 MB/s (other sessions' benches were running). It scores the
  "frame profile" lines (one a flip) and counts TIMEOUT, fault, reopen and "GIVEN UP" lines.
- `gu0214.py` breaks the given-up game-thread waits down by label (F262–F265).
- CPU of the APR workers: the 1-s schedstat lines of exp 0200's sampler in O2 and O3. It does not watch the
  readers.
- Integration (only after the top session's go and in its box slot):
  - `patch_0214.diff` is exp 0203's `patch_0203.diff` with the read-ahead default changed from off to 4;
    `KYTY_BC5_APR_READAHEAD=0` turns it off. The clock-voice journal stays off by default. It applies cleanly to
    `~/src/KytyPlus` (f266548 plus the local changes). Nothing in `src/` has changed since the shared builds
    (10:22:48 and 10:49:49), so a rebuild brings in only this change.
  - `rebuild0214.sh` applies it and rebuilds both shared builds. The old binaries and `libAmpr.cpp` are kept as
    `*.before-0214`.
  - `run0214.sh` smoke-runs a shared build through `play-pkg.sh` itself, with no `BC5_EMU` and no
    `KYTY_BC5_APR_READAHEAD`. `cpu0214.sh` samples the APR threads' CPU and the process's RSS beside it.
  - `chain0214.sh` holds one lock line for: the rebuild; S1N, the normal build on O2's route for 300 s; S1L, the
    lean build for 150 s. If a smoke run fails, it puts both binaries and `libAmpr.cpp` back.

**Result.**
1. **Regression check (`raw/ra-regression.txt`, `raw/ra-giveups.txt`).**
   - Water bench, arm A (off) A1/A2/A3 against arm B (=4) B1b/B2/B3:

     | | A1 | A2 | A3 | B1b | B2 | B3 |
     | --- | --- | --- | --- | --- | --- | --- |
     | flips/s | 28.3 | 29.8 | 29.4 | 30.1 | 30.1 | 30.3 |
     | mean ms between flips | 35.3 | 33.6 | 34.0 | 33.2 | 33.2 | 33.0 |
     | frames > 100 ms | 56 | 73 | 71 | 93 | 81 | 42 |
     | frames > 250 ms | 9 | 31 | 28 | 27 | 21 | 9 |
     | frames > 1 s | 2 | 0 | 0 | 0 | 0 | 0 |
     | longest frame, ms | 2792 | 971 | 840 | 814 | 713 | 685 |
     | given-up waits | 14 | 13 | 18 | 27 | 30 | 19 |
     | of them on 0x12004b3c38 | 2 | 2 | 2 | 2 | 5 | 0 |
     | of them on 0x12004b5438 | 7 | 9 | 13 | 18 | 20 | 13 |

     - TIMEOUT, fault and reopen lines: 0 in all six runs. The bench's own check found no new kernel line.
   - Cutscene route, O2 (off) against O3 (=4):
     - flips/s 32.4 against 40.5; mean between flips 30.9 against 24.7 ms;
     - frames > 100 ms 277 against 52; > 250 ms 104 against 10; > 1 s 2 against 1;
     - longest frame 1,421 against 5,646 ms. O3's is the GPU stretch that F266 also finds without the read-ahead.
     - TIMEOUT, fault and reopen lines: 0 and 0.
     - Given-up waits: 47 against 50. On 0x12004b3c38 28 against 14, on 0x12004b5438 12 against 31.
     - O2 ran in a swap storm and O3 with memory calm (exp 0203), so this pair shows no harm. Its gain cannot be
       credited to the switch.
   - CPU of the APR workers (bc5-apr-q1/q3/q5): 3.5 s in O3 against 3.4 s in O2, over 600 s each.
   - Memory: the read-ahead data held is capped at `KYTY_BC5_APR_READAHEAD_MIB` (32 MiB) in all, over every queue.
     A reader reserves a buffer's bytes before reading it and skips a buffer that would go over the cap. No
     process RSS was recorded in these runs.
   - No crash in the five v2 runs with the switch on (S0, O3, B1b, B2, B3).
   - Reading:
     - No regression in frame pacing, faults or timeouts. The water arms overlap, with B slightly faster in
       flips/s.
     - One weak signal: more given-up game-thread waits with the switch on in the water bench, 76 against 45
       (every B run above every A run, p ≈ 0.05 for 3 against 3). The rise is on label 0x12004b5438.
     - The label of F262's machine-downs, 0x12004b3c38, did not rise: 7 against 6 at the lake, 14 against 28 in
       the cutscene.
     - Exp 0205 found that the give-ups do not explain the lake's flashes.
     - A guess, not shown: the title does more once its streaming arrives sooner (O3: game-main 273 s against
       242 s of CPU, each Job_Hi thread 77 s against 65 s).
   - The numbers went to the top session at 19:35, before any integration step.
   - The top session's decision: clean enough under the rule. The given-up rise on 0x12004b5438 is recorded and
     watched, not a blocker.
2. **The patch in the tree (19:43:46, sources only, no build).**
   - `git apply` of `patch_0214.diff` in `~/src/KytyPlus`. The tree's change equals the patch byte for byte, and the
     file equals `src/libAmpr.default-on.cpp`.
   - `git diff f266548 -- src/libs/libAmpr.cpp` went from 819+/111− to 1134+/122−. Both are kept on the box as
     `raw/git-diff-f266548-{before,after}.txt`.
   - The file is LF-only in f266548, in the tree before and after, and in the patch (0 CRs).
   - The pre-patch file is kept as `~/bc5-work/exp0214/src/libAmpr.before-0214.cpp`.
3. **Rebuild (`chain0214.sh` on the top session's go, 20:02:58–20:03:29; `raw/chain.out`, `raw/rebuild.out`).**
   - Each build compiled only `libAmpr.cpp.o` and relinked: 16 s for the normal build, 12 s for the lean one, rc 0.
   - Three warnings, none from this change: two `-Wformat-extra-args` in the AMM-trace lines that predate it, and one
     deprecation in `stringUtils.h`.
   - md5 of the normal build `c0d1b209…` → `9d43e945…`, of the lean build `25432e07…` → `7eac6f35…`; synced. The old
     binaries are kept as `~/bc5-work/exp0214/kyty_emulator{,-lean}.before-0214`.
4. **Smoke run S1N: the normal build through `play-pkg.sh`, no `KYTY_BC5_APR_READAHEAD` set, O2's route, 300 s
   (20:03:32–20:08:43). Passed.**
   - 12 reader threads (4 each for q1, q3 and q5). The journal has 463 read-ahead lines and 512 in-order copies; the
     completion sequence never decreased. No crash and no kernel line. The live saves were back and identical
     (`raw/S1N-*`).
   - Frames (`raw/S1N-frames.txt`):
     - 37.1 flips/s (39.4 for t ≥ 100 s), 27.0 ms mean between flips;
     - frames over 100 ms 43, over 250 ms 15, over 1 s 4;
     - TIMEOUT, fault and reopen 0; given-up waits 13.
   - The four frames over 1 s (`raw/S1N-long-frames.txt`):
     - one GPU stretch: 1,149 ms GPU busy at t 129.9 s;
     - three with the game thread outside the host for 1.07–1.38 s (t 158.8, 162.0, 179.4 s), while MemAvailable
       was about 0.4 GB and PSI io full 16–45 % (the sampler's "v" lines).
     - For comparison, O2 had 2 over 1 s in 600 s, in a swap storm, and O3 had 1.
   - The cinematic clock lost 1.3 s in t 100–250 s and did not stop (`raw/S1N-clock.txt`). O2 lost about 4 s, O3
     7.9 s (exp 0203).
   - CPU (`raw/S1N-cpu.txt`, `cpu0214.sh`): the readers used 12.4 s in 288 s, 4.3 % of one core; the workers 3.6 s,
     1.2 %.
     - In the quiet stretches (workers under 10 ms per 10 s) the 12 readers still used 153–175 ms per 10 s. So about
       1.6 % of one core is the 5-ms polling, some 2,400 wake-ups a second.
     - The other ~7.7 s is the reads themselves, up to 1.7 s per 10 s in bursts.
   - Memory: VmRSS peaked at 4,234 MiB and was 1,798 MiB at the end, as the box swapped. This run has no baseline
     without the read-ahead; its own data is capped at 32 MiB.
5. **Smoke run S1L: the lean build (`BC5_LEAN=1`), the same route, 150 s (20:08:45–20:11:31). Passed.**
   - 16 reader threads: the title used priority queue 0 too this time (q0, q1, q3, q5). No crash and no kernel line;
     the live saves were back and identical.
   - The readers used 7.2 s in 139 s, 5.2 % of one core, with a floor of 159–169 ms per 10 s.
   - The lean build has no journal, so there are no frame data.
6. **The chain's lock was left behind.** Its release matched "chain " against its own "chain:" line. The lock stayed
   from 20:11:46 until removed by hand at 20:12:51; fixed in `chain0214.sh`.

**Verdict.**
- **The APR read-ahead is on by default in both shared builds since 2026-10-22 20:03.** It runs 4 readers per
  priority queue; `KYTY_BC5_APR_READAHEAD=0` turns it off, and the launchers are unchanged.
- It went in under the maintainer's rule:
  - the speed-up: the cutscene's APR queue at a 3.4 → 0.42 s 95th percentile, and slightly more flips a second at
    the lake;
  - no regression in frame pacing, timeouts, faults or crashes in nine runs with it (S0, O3, B1b, B2, B3, S1N, S1L)
    against four without it (A1–A3, O2).
- To watch:
  - more given-up waits on 0x12004b5438 at the lake (76 against 45); F262's machine-down label did not rise;
  - S1N's three outside-host frames over 1 s, under memory and io pressure.
- Cost: about 4–5 % of one core for the readers, of which about 1.6 % is idle polling. A condition-variable wait in
  place of the 5-ms poll would remove that part.
- Not shown: that the cutscene slow motion is gone. S1N is a third run on the route with the read-ahead; its clock
  lost 1.3 s and did not stop.
