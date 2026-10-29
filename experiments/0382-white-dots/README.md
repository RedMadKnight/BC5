# 0382 — The second title's white dots with ray tracing on: which pass makes them

**Question.** On 2026-10-29 the maintainer saw white dots ("białe kropki") in his own play of the second title
from his current save (slot 4), RT on, on the shared normal build and on the 0380 test builds, within the first
30–60 minutes. In the 17:xx–18:08 session he paused and saw none, then they came back after he unpaused (a few moments
before the 18:08 graphics-pipe stall). There is no shot and no description of their size or colour yet (the top
session asks him in the morning). Neither exp 0380's switches nor exp 0379's zero skip cause them. Which pass makes
them, and is there a default-off fix?

**Today's defaults** (read on the box 2026-10-29 23:5x with the top session's GO, read only):
- `play-pkg.sh` 55531ab6 and the shared normal build 58c4a627.
- `BC5_DIRECT_SKIP_PGM=${BC5_DIRECT_SKIP_PGM:-0}` (line 92): nothing is skipped with RT on. The BVH compaction
  0x909974400 runs (exp 0323, F388) and so does every reflection-traversal variant.
- `KYTY_BC5_RT_BUILD_PGM` (line 96), the programs the host's RT switch drops when off: the ten BVH builders plus the
  three traversal variants 0x11d049aa00, 0x11d04a6000, 0x11d04bb900 (F343, F362).
- `BC5_DIRECT_RING_DEPS=dcb` (line 125, F385/F388).

**Hypotheses, ranked** (laptop, from what is on main at 51faa1b):
1. **The reflection traversal returns sparse wrong hits that the composite does not clamp.** For: the traversal's
   output has been wrong, and too bright, every time its input was wrong. Over never-built trees (RT off) and over
   uncompacted trees (RT on, compaction skipped) it washed the lab out white (F362, F366). With the compaction running
   the lab's reflections came out right (F370). A partial version of the same failure, a few rays per frame hitting
   wrong nodes of a tree being rebuilt or read early, would show as isolated white points. Against: the defaults now
   run the compaction (F388), which fixed the lab, and no report places dots in the lab.
2. **Temporal history (denoise or accumulation) carries invalid samples forward.** For: dots absent while paused and
   back after unpausing. Whatever the game does when paused (the history freezes, or the paused frame is not
   re-traced), a per-frame trace or history defect stops showing. Against: nothing direct; this title's
   reflection and denoise passes are not identified by program yet.
3. **Memory pressure leaves the RT inputs stale or zero** (re-reads under pressure, F505; learned windows and zero
   pages). For: the dots came in long play, under the deepest pressure measured so far (the 36-min 0380wb play of
   2026-10-29, exp 0379's hand-over note: GTT 12.7 GiB, MemAvailable 0.19–0.37 GB, PSI mem full up to 24 %). Against: zero skip (0379), which frees ~2 GB, did not remove
   them. The bench's short runs do not reach that pressure.
4. **Not RT at all** (the game's own rain or specular sparkle; the night lake has white rain sparkle, exps 0194
   and 0197).

**Plan: the cheapest discriminating test** (the top session's scene choice: not the lab, but a fresh copy of his
current save, slot 4, RT on).
- **Bench:** `s6n0382.sh`, after exp 0378's `s6n0378.sh`.
  - The shared normal build 58c4a627, through a private copy of `play-pkg.sh` (4 lines changed, 1 added: own log,
    working directory, save directory, learned-file copy; the input-configuration hook).
  - The route save is a fresh snapshot of the live saves taken at each arm's start, copied into the private working
    directory. The live saves are compared only.
  - Slot 4 by exp 0305's `slot4-90.cmd` (✕ at 90 s, down ×3, ✕, ✕), then the scene idles.
  - Shots by exp 0190's `shots.sh`, every 10 s from t 200 s to 300 s. Arm A adds a pause: options at 310 s, three
    shots paused (320–340 s), options at 350 s, three shots after (360–380 s).
  - The kernel log is streamed to the laptop during each arm.
- **Measured on the box only** (the shots never leave it): exp 0299's `wh0299.py` (luma, white and clipped shares),
  and `dots0382.py`.
  - `dots0382.py` counts isolated bright points: luma ≥ 0.80, ≥ 0.30 above the mean of the 7×7 ring around them,
    at most two bright pixels in that ring, one count per 3×3 maximum. It also counts how many of a shot's dots sit
    within 2 px of the previous shot's.
  - Self-test: `python dots0382.py --selftest` on the laptop (synthetic frame: four 1-px dots and one 2×2 dot found,
    none in a bright area or on its edges, kept 5 of 5 unchanged, 0 when moved).
- **Arms**, ~400 s each, ~8 min each with the setup and the metrics, ~25 min in all:
  - A: RT on, the defaults, with the pause segment.
  - B: RT on, the reflection traversal skipped:
    `BC5_DIRECT_SKIP_PGM=11d049aa00,11d04a6000,11d04bb900,11d040e200,11d040c900` (the three of the RT switch's
    list and the two F234 variants). The BVH is still built and compacted.
  - C: RT off (the input configuration, `KYTY_BC5_RT=0`; its "ray tracing off" drop lines checked by 180 s).
- **Reading:**
  - dots in A and not in B → the traversal (hypothesis 1 or 2);
  - in A and B but not in C → another RT pass (build, denoise);
  - in all three → not RT (hypothesis 4);
  - none in A → the bench does not reach them (hypothesis 3; next a longer arm, or the scene he played).
  - Within A, the paused shots against the running ones separate a per-frame defect from a history one.

**Bookkeeping.** Findings F640–F659 (the top session's range). Branch `exp/0382-white-dots`, never main.

**Status** (2026-10-29 ~23:55). Claimed in the repo. The box side is not claimed: this session's permission
classifier refused the `mkdir ~/bc5-work/exp0382` of the GO'd read as a write to a shared resource, so no file has
been written on the box. The arms need that permission (box writes: the lock line, the private working directory, the
save snapshot, the shots) before they can run from this session.
