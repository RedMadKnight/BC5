# 0207 — a 100-ms game-thread wait limit removes 16 of 17 given-up waits; the frame cost is not settled

**Question.** Experiment 0206 (F263) found that label 0x12004b3c38, behind three machine-downs,
is cleared by something the host does not track. When the host gives up after 8 ms
(`BC5_DIRECT_DCB_WAIT_MS`, default 8), the graphics work runs ahead of it. With the limit at
100 ms, do the give-ups go away, and what does it cost?

**Setup.**
- One scripted run, tcpW2, 17:12–17:22 on 2026-10-22. It was granted by the box supervisor; the
  maintainer was away.
- It is identical to tcpW1 (experiment 0206) except for the limit:
  - the water session's bench, `~/bc5-work/exp0201/bench0201.sh tcpW2 600`, from the private lake
    save copy into gameplay, Photo Mode after ~5 min;
  - `ENVX="BC5_EMU=~/bc5-work/kytyplus-build/src/kyty_emulator BC5_DIRECT_DCB_WAIT_MS=100
    BC5_DIRECT_WAIT_TRACE=1"`, i.e. the shared build with the launcher's defaults, the limit raised,
    and the wait trace on;
  - no AMM trace (tcpW1 had it; it only writes to the emulator log).
- Box: kernel 7.2.9-ogc3.1, boot ac5dab11.
- Journals: tcpW1 `~/bc5-data/captures/play-20261022-1652/gc/direct.log`, tcpW2
  `play-20261022-1712`. Emulator log: `~/bc5-work/exp0207/tcpW2-play-pkg.log`.
- The figures come from the journals' "frame profile" lines (time since the last flip) and the
  "cpu-wait … GIVEN UP" lines (`raw/tcpW1-baseline.txt`, `raw/tcpW2-result.txt`).

**Result.**

| | tcpW1 (8 ms) | tcpW2 (100 ms) |
| --- | --- | --- |
| Timeouts, faults | 0 | 0 |
| Waits given up | 17 | 1 |
| … on 0x12004b3c38 | 6 | 1 (after 100.1 ms) |
| … on other labels | 0x12004b5438 6, 0x12004b7838 2, 0x12004b4838 2, 0x12004b4c38 1 | none |
| Waits traced on 0x12004b3c38 | 6,697 | 6,201 |
| Frames | 17,814 in 599 s | 17,144 in 596 s |
| Mean time between flips | 33.5 ms | 34.6 ms |
| Over 50 / 100 / 250 ms | 875 / 44 / 7 | 1,075 / 123 / 12 |
| Over 1 s | 0 | 2 |

- The waits given up in tcpW1 were served within 100 ms in tcpW2, all but one. The exception is a
  wait on 0x12004b3c38, so that label's writer can be more than 100 ms late.
- The 16 avoided give-ups can add at most ~1.6 s of waiting over 10 minutes. That is far less than
  the extra long frames: 79 more frames over 100 ms and two over 1 s.
- Most of the difference is therefore not the limit. It is the spread between runs under the box's
  memory pressure (exp 0203's O2, with the launcher's defaults, had a 1-s stall of all threads).
  With one run per arm this cannot be separated.

**Verdict.** Passed for the give-ups; inconclusive for the cost.
- `BC5_DIRECT_DCB_WAIT_MS=100` turns 16 of 17 given-up waits, 5 of 6 on the machine-downs' label,
  into waits that are served. It needs no build and changes nothing the GPU runs.
- It cannot remove the race completely (one wait still took over 100 ms). It cannot show in a
  10-minute run whether the machine-downs go away: they come about once an hour of play.
- Next, the maintainer's call:
  - a repeat pair (8 ms and 100 ms, two runs each) to measure the frame cost against the spread;
  - then the launcher: either `BC5_DIRECT_DCB_WAIT_MS=100` in `play-pkg.sh`, or a targeted host change
    behind a switch (a longer CPU wait only for labels with no pending GPU writer).
- The launchers stay unchanged until then.
