# 0061 — ASTRO BOT in a later level: the ring order and a faster policy filter

**Question.** Experiment 0060 measured the ring order on the first level, where the GPU is the
limit. In a later level the game thread is part of the limit (F65). How much do the ring order of
experiment 0055 and the host's `prepare` pass cost or give there? A second question came from the
maintainer: can the runs be driven without someone at the pad?

**Setup.**
- **Pad from a script.** `KYTY_BC5_INPUT_CMD=<file>` (KytyPlus patch 0001, `controller.cpp`): a
  thread tails the file and runs each new line (`press`, `hold`, `release`, `stick`, `trigger`,
  `wait`, `shake`, `reset`; `backend/kytyplus-patches/README.md`). Screenshots in between, private.
  A copy of the maintainer's save; the saves of the runs go to their own directories.
- **The scene.** From the title, a fixed list of commands:
  - load the save;
  - fly the ship to a jungle-temple level of the first galaxy (not the water level of F64);
  - hold cross for 1.5 s (a short press does not start a level, it took a few runs to find out);
  - walk forward 2.5 s, jump, then stand still at the wall.

  The same frame on screen in all three runs.
- **Window.** 55–135 s after the level loaded (the last frame over 300 ms). Summaries from the
  journal, `raw/`:
  - `winsum.py`: waits;
  - `frameprof.py` (exp. 0025): the frame profile;
  - the parts of `prepare` from the same line.
- **Settings.** As in 0060 (`FLIP_DEFER`, 24 jobs in flight, `TS_SCALE=1.2`).
- **Runs** (2026-10-13):
  - run 280: the ring order on;
  - run 281: off, the 8 ms rule only;
  - run 282: on, with the faster filter below.
- **Buffer dump.** Run 281 dumped 60 buffers, about three frames, from the level
  (`BC5_DIRECT_IB_DUMP`, private), for `prepare-bench` (exp. 0027).

**Result 1, the ring order** (the same scene):

| | run 281, 8 ms rule | run 280, ring order |
|---|---|---|
| fps | 34.9 | 37.2 |
| frame, mean | 28.7 ms | 26.9 ms |
| game thread inside the host | 12.8 ms | 10.0 ms |
| ... of it waiting for labels | 2.8 ms | 0.1 ms |
| waits given up at 8 ms | 0 | 0 |
| GPU busy | 15.0 ms | 15.8 ms |

Here no wait reaches the 8 ms limit. The waits are short but many: 13,950 in 80 s, 7.9 s in total.
The ring order hands them to the GPU, and the game thread gets 2.7 ms a frame back.

**Result 2, `prepare`.** With the ring order on, `prepare` is still 7.8 ms a frame, and 6.4 ms of
that is the policy filter: three times the second level's 2.4–3.1 ms in exp. 0027. The frame is
bigger: four main buffers of 50,000–118,000 dwords, about 355,000 dwords a frame against
130,000.

In the largest buffer, 93,000 of its 110,000 dwords are SET_SH_REG packets of about 30 registers.
The filter decided each such packet by looking up every register in the table, and then looked
every register up again for registers to rewrite. Offline (`prepare-bench --filter-only`) the
four main buffers of a frame took 4.2 ms.

**Change.**
- `Policy::span_listed`: the register span of a SET packet that touches none of the table's 8
  ranges has the default verdict, answered in one test per range.
- `Policy::span_has(…, Rewrite)`: the rewrite loop runs only for spans that may hold a register
  to rewrite.
- The same verdicts, the same dwords:
  - a unit test compares `packet()` with the register-by-register answer for every offset of
    the five SET opcodes and six lengths;
  - `prepare-bench --hash` gives the same output for all 60 dumped buffers, with `mapped()`
    answering yes and no.

  ctest 40/40.

| Offline, 3 frames (13 main buffers) | before | after |
|---|---|---|
| filter + offsets + copy | 11.1–14.3 ms | 3.5–3.9 ms |
| all 60 dumped buffers | 11.4–12.3 ms | 3.7 ms |

**Result 3, run 282** (ring order and the faster filter, the same scene):

| | run 280 | run 282 |
|---|---|---|
| fps | 37.2 | **41.7** |
| frame, mean / p90 | 26.9 / 29.3 ms | 24.0 / 26.2 ms |
| game thread inside the host | 10.0 ms | 6.3 ms |
| prepare | 7.8 ms | 3.5 ms |
| filter | 6.4 ms | 1.8 ms |
| outside the host | 16.9 ms | 17.7 ms |
| GPU busy | 15.8 ms | 15.6 ms |

No failed submission, no timeout, nothing in the kernel log.

**Verdict.** Passed. In this level the two changes take the frame rate from 34.9 to 41.7 fps
(+19%):
- the ring order removes 2.7 ms of label waits a frame;
- the faster filter removes 4.5 ms of `prepare`.

Neither changes a dword the GPU executes. The game thread's own time outside the host (17.7 ms)
is now the larger half of the 24 ms frame; the GPU is busy 15.6 ms of it. What is left inside the
host:
- `prepare` 3.5 ms (filter 1.8, tracker 0.9, copy 0.5);
- the CS ioctls 1.6 ms.

The pad script makes such measurements repeatable without the maintainer. The whole route from
the title to the level is a list of timed commands.
