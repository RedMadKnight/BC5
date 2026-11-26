# 0208 — the 100-ms wait limit's frame cost is within the run-to-run spread, and it removes almost every given-up wait

**Question.** Experiment 0207 (F264) left the frame cost of `BC5_DIRECT_DCB_WAIT_MS=100` unsettled:
one run per setting cannot separate it from the spread between runs. With a second run per
setting, is the cost more than noise?

**Setup.**
- Two more scripted runs on 2026-10-22, granted by the box supervisor and run attended, in the
  order it asked for (100 ms first, against box warm-up):
  - tcpW2b, 17:32–17:42, `BC5_DIRECT_DCB_WAIT_MS=100`;
  - tcpW1b, 17:42–17:52, the default 8 ms.
- Both runs otherwise used the same settings:
  - the water session's bench `~/bc5-work/exp0201/bench0201.sh <tag> 600`, from the private lake
    save copy into gameplay, Photo Mode after ~5 min;
  - the shared build (`~/bc5-work/kytyplus-build/src/kyty_emulator`) with the launcher's defaults,
    plus `BC5_DIRECT_WAIT_TRACE=1` (logging only);
  - no AMM trace.
- Between the runs: no emulator, no BOX-LOCK, no leftover bench process, the same boot
  (ac5dab11), no new amdgpu lines.
- Compared with tcpW1 (exp 0206: the same, plus `KYTY_BC5_AMM_TRACE=1`) and tcpW2 (exp 0207: the
  same as tcpW2b).
- Journals: play-20261022-1652 (tcpW1), -1712 (tcpW2), -1732 (tcpW2b), -1742 (tcpW1b). Figures from
  their "frame profile" (time since the last flip) and "cpu-wait … GIVEN UP" lines
  (`raw/four-runs.txt`).
- Box: kernel 7.2.9-ogc3.1. The maintainer was away.

**Result.**

| Run | Limit | Frames | Mean between flips | > 50 ms | > 100 ms | > 250 ms | > 1 s | Waits given up (on 0x12004b3c38) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| tcpW1 | 8 ms | 17,814 | 33.5 ms | 875 | 44 | 7 | 0 | 17 (6) |
| tcpW1b | 8 ms | 17,288 | 34.6 ms | 1,166 | 64 | 16 | 0 | 12 (8) |
| tcpW2 | 100 ms | 17,144 | 34.6 ms | 1,075 | 123 | 12 | 2 | 1 (1) |
| tcpW2b | 100 ms | 17,106 | 34.9 ms | 1,143 | 72 | 10 | 0 | 0 (0) |

- No run had a timeout or a fault.
- Waits given up: 29 with 8 ms (14 on the machine-downs' label) against 1 with 100 ms (1).
- The mean between flips: 34.05 ms with 8 ms against 34.75 ms with 100 ms, a difference of 0.7 ms.
  The two 8-ms runs alone differ by 1.1 ms.
- Frames over 250 ms: 23 against 22. Over 1 s: 0 against 2, both in tcpW2.
- Frames over 100 ms: 108 against 195. Most of that is tcpW2 (123); tcpW2b (72) is close to
  tcpW1b (64). This is the one figure that may be a real cost, at most a few dozen extra frames over
  100 ms in 10 minutes.

**Verdict.** Passed.
- With two runs per setting, `BC5_DIRECT_DCB_WAIT_MS=100` removes the given-up waits: 29 → 1 in
  20 minutes, including F262's precursor on 0x12004b3c38 (14 → 1).
- Its cost on the mean frame time is within the spread between runs of the same setting. Long
  frames over 250 ms are unchanged. Frames over 100 ms may rise somewhat (one of two runs).
- It does not show that the machine-downs go away: they come about once an hour of play, and these
  runs were 40 minutes in all, without one.
- Whether to make it the launcher's default, and checking it in play time, are the maintainer's
  call. The launchers are unchanged.
