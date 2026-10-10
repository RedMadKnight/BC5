# 0045 — ASTRO BOT's first level at 57 fps: the flip deferred and a deeper queue

**Question.** Option A of the 60 fps plan (the maintainer's choice, 2026-10-10): take back the GPU's
idle time on the host's side. Experiment 0043 found 1.1 ms of idle GPU per frame of the first
level. Where does it come from, and does it go away?

**Setup.** As in 0043/0044 (`run151.sh` recipe, 420 s, the first level's gameplay at 380–418 s,
`gpu-timeline.py`). The game thread's frame profile of run 159 (unchanged): of an 18 ms frame
it spent 7.3 ms at the flip (the host held the flip until nothing was in flight, F57), 3.4 ms at
the cap of 12 jobs in flight, about 3 ms elsewhere in the host and 4.7 ms in the game itself, so
at every flip the GPU's queue ran empty. Experiment 0028 deferred the flip
(`BC5_DIRECT_FLIP_DEFER=1`, the flip queued behind the frame's jobs) and found the game's thread
then waiting at the cap instead. New here: `BC5_DIRECT_MAX_IN_FLIGHT` (host, default 12) and the
backend's scratch slots raised from 16 to 64 (`backend/src/direct.cpp`, `Impl::kSlots`; with 16
slots a cap of 48 failed 30,609 submissions with `-EBUSY`, run 160). Backend tests 33 of 33.
Runs 159–163, 2026-10-10 06:08–15:53. Raw output in `raw/`.

**Result.**

| Run | Setting | Frames 380–418 s | fps | GPU idle per frame (median) | Failed |
|---|---|---|---|---|---|
| 159 | as before | 2,060 | 54.2 | 1.11 ms | 0 |
| 160 | flip deferred, cap 48, 16 slots | — | — | — | 30,609 (`-EBUSY`) |
| 161 | flip deferred, cap 12 | 2,116 | 55.7 | 0.94 ms | 1 |
| 163 | flip deferred, cap 24, 64 slots | 2,157 | 56.8 | 0.00 ms | 0 |
| 162 | flip deferred, cap 48, 64 slots | 2,167 | 57.0 | 0.00 ms | 0 |

With the flip deferred and room for 24 or more jobs the GPU never waits for work: busy
16–18 ms of every 16–18 ms frame (median 17), graphics 11.7–11.8 ms, compute 4.8 ms. The game's
thread now waits on its own labels (8–10 ms per frame) instead of at the flip or the cap. The
picture is right (run 163 at 400 s, the window's counter at 57.2 fps; screenshot to the
maintainer only). No failed submission in runs 162–163, from the intro to the first level.

**Verdict.** Passed: the first level goes from 54 to 57 fps and the GPU's idle time is gone. The
frame is now the GPU's own time, 17 ms, against 16.7 ms: 60 fps needs the GPU to do less work or
the compute buffers to run beside graphics (F31). The play settings (`bc5-run.env`) now carry
`BC5_DIRECT_FLIP_DEFER=1 BC5_DIRECT_MAX_IN_FLIGHT=24`; the second level and the maintainer's own
play are still to be checked with them.
