# 0269 — ASTRO BOT's geyser at "~20 fps" in the maintainer's 16:11 session: waiting, the known one-ring cycle

**Question.** On 2026-10-24 16:11:42–16:14:31 the maintainer played ASTRO BOT on the normal build
(`play-astro.sh`, emulator built 15:26:37, repo `ce2e5d7a`) with a DualShock 4 and saw about 20 fps
at the water geyser, lower than he remembers. Is the geyser stretch GPU-bound, host-bound (flip
preparation, `kyty-gpu`) or waiting, and did today's integrations (the tiler pool F311, the alias
guard, the DS4 rumble fallback F214) plausibly cost frames?

**Setup.** Read-only, no run. The session's GPU journal `~/bc5-data/captures/play-20261024-1611/gc/direct.log`
(23.7 MB, `BC5_DIRECT_JOURNAL=min`, frame profile and timing lines on: 7,610 frames, journal t 0–166.2 s,
exit 0, no kernel line in 16:11–16:15) and its log `~/bc5-work/play-review-20261024/astro-normal.log`.
Settings: `bc5-run.env` as committed (one GFX ring, `BC5_DIRECT_RINGS=1`, no compute ring, pieces full,
ring order, deferred flip; no `BC5_DIRECT_CHAIN`, no prefix). Tools: the awk scripts of exp 0269's
predecessor note in `~/bc5-work/*-astro.awk` (10-s bins of the frame profile, CPU-side wait durations,
fence time per job kind, the flip-wait end against the last GPU completion). Earlier geyser numbers from
experiments 0132–0135 (2026-10-16) and the water from 0078 (F137). Box reads were targeted (one 24 MB file,
three 25 MB files), while no emulator ran.

**Result.**

Timeline (10-s bins; `raw/bins-1611.txt`):

| t (s) | fps | frame | GPU ring busy | label waits / own work / prepare+cs | what |
|---|---|---|---|---|---|
| 10–50 | 58–60 | 16.7–17.2 ms | 7–12 ms | 2.6–6.3 / 8.5–12.9 / 1.0–1.7 ms | start, hub |
| 50–100 | 34–42 | 24–30 ms | 13.6–15.9 ms | 7–8.4 / 13.5–17.3 / 3.1–3.6 ms | the level's first part (F137: 34.9 fps, 15.8 ms GPU) |
| 100–150 | 43–49 | 20–23 ms | 15.2–16.2 ms | 6.5–8 / 9.6–13.2 / 2.2–2.9 ms | the level (F137: 45 fps, 13.2 ms) |
| 152–166 | **27–28** | **36–37 ms** | 12.8–14.7 ms | **22 / 11–12 / 2.9 ms** | the geyser (new render targets imported at t 152.4) |

The geyser, per second from t 153 to 166 (`raw/geyser-per-second.txt`): 27–28 frames a second, mean frame
35.9–37.2 ms, label waits 21.7–22.5 ms, GPU busy 12.8–14.7 ms. Nothing in the capture is at 20 fps; the
slowest second has 27 frames.

What the game thread waits for (t ≥ 150, 491 frames):

- 373 `cpu-wait WAIT_REG_MEM64 … GIVEN UP after 16.7–17.0 ms`: the 8-ms limit (`BC5_DIRECT_DCB_WAIT_MS`
  default) twice, once before the head piece is submitted and once after it (`pieces full` in the last
  10 s: 207 splits, the wait then satisfied 0, not satisfied 207). One or two a frame.
- The waits sit at dwords 19,192–19,581 of a ~40,000-dword main graphics buffer, on three rotating
  labels 0x403678cc0 / 0x403678d00 / 0x403678d40 (function 3, reference = a frame counter). The label's
  value is 3 below the reference, or 0xff, at every give-up. Experiment 0132 saw the same at the geyser on
  2026-10-16: "waits at dwords ~20,234–20,309 for three counters that a compute buffer of 1,332 dwords
  increments; the value is always 3 below the reference" — the graphics/compute cycle of F180, whose two
  halves live in two guest compute queues (exp 0133).
- The compute writer comes only after the give-up: the next compute submission follows a give-up by
  9.0 ms on average (373 of 373), i.e. the title's thread submits it once our wait releases it (F284's
  mechanism, named for the geyser in ADR 0013).
- The GPU is not the limit: ring busy 14.5 ms of a 36.5 ms frame; the gap from the last GPU completion to
  the next submission is 5.7 ms on average (1.9 ms at t 100–150), the GPU queue runs empty while the
  thread waits.
- The flip is not the limit: a flip-label wait ends 0.24 ms after the last GPU completion at t 100–150
  and 0.40 ms at t 60–100 (2.7 ms in the 2026-10-18 session before the tiler pool, F129's 2.8 ms).
- Host sync 0.1–0.3 ms a frame, `prepare` 2.3–2.5 ms, pinned memory flat (8.15 GiB from t 60), one
  learned-window apply at start. No `aliases:` line, no `two rings`, no `spec waits`, no TIMEOUT, no
  ring reset; 50 `cycle broken` at t 130–140 (one spot before the geyser), 5 `chain hold` watchdog
  lines spread over the session (one per 1,024).

Against earlier measurements:

| where | setting | fps at the geyser | give-ups |
|---|---|---|---|
| exp 0132, session 1318 (2026-10-16) | one ring (`play-astro.sh`) | 26–27 | 916 in the session |
| exp 0132, 1322 / exp 0133, 1330 | compute ring, two-ring limit 8 / 4 ms (`play-astro-compute.sh`) | 30–31 / 32–34 | 1,472 / 2,883 |
| exp 0134–0135 | compute ring + acb heads / four rings + speculative waits (off since F181) | ~33 | 721 / 6 |
| **today, play-20261024-1611** | **one ring (`play-astro.sh`)** | **27–28** | **373 in 17 s** |

The scripted ASTRO routes of 2026-10-23 and 2026-10-24 00:14/00:18 (S4A's route) never reach the geyser
(2–19 give-ups in 150–200 s, 55–60 fps), so they are no reference for it.

Today's changes:

- Tiler pool (F311): on, 3 buffers of 32 MiB for 7,168 requests, 7,165 reused. It is where the flip
  preparation's 2.7 ms went (0.24 ms today). It gained, not cost.
- Alias guard: no `aliases:` line in the journal; it never acted.
- DS4 rumble fallback (F214): not measurable here. The log has four `AudioOut` lines and no
  `type 10 … (pad)` line, but a vibration port with no controller audio device is never traced and
  its open line is off in play logging (exp 0268, result 3), so the log does not show whether the
  fallback ran (the maintainer felt rumble, which suggests it did). It runs on the title's audio
  thread; the geyser's waits above are on the game thread and are explained without it. (Corrected
  by the top session before commit; the first draft read the missing trace line as "never ran".)
- Held tail (ADR 0013, on by default): applies only on the two-ring path (`two_rings` needs
  `BC5_DIRECT_COMPUTE_RING`), so on `play-astro.sh` it never engages; the geyser's waits take the
  one-ring pieces path and give up as in exp 0132.

**Verdict.** The geyser stretch is **waiting**, not GPU- or host-bound: the main graphics buffer's wait
on the fluid counters is given up every frame after two 8-ms limits because the title's thread, held in
that wait, is the one that submits the compute buffer that increments the counters — the one-ring
geyser cycle of F180/exp 0132, unchanged since 2026-10-16 (26–27 fps then, 27–28 fps today). The fluid
runs 3 frames behind the picture, which reads as slower than the counter says. None of today's
integrations costs frames here; the flip preparation is faster than before. What would raise it, as
measured then: the compute-ring shortcut `play-astro-compute.sh` (32–34 fps, F181), or carrying ADR 0013's
held tail to the one-ring path (its §1 limits it to the two-ring path), which is the fix the ADR already
names for this cycle. Not verified today: anything on the box, since this experiment made no run.
