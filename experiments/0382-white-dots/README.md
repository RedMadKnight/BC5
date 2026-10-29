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

**Laptop analysis** (2026-10-30 ~00:30, the top session's ask: narrow the pass, prepare the thresholds; no box
access, nothing from the title's binaries read beyond what main's experiments already state).
- **Today's defaults exclude F370's cause.** With `BC5_DIRECT_SKIP_PGM=0` the compaction runs and the traversal walks
  compacted trees, the configuration in which the lab's reflections came out right (F370). The flat-aperture rewrite is
  on in the second title's settings (D15; its "flat aperture: program … 6 stack pushes" lines are in the shared
  build's journal of 2026-10-28 16:47, a private copy on the laptop).
- **The traversal's own stack is not a source of wrong hits on the host.** Exp 0190 decoded the walk: the stack
  pointer is one VGPR whose high half is a scratch offset starting at 0xff84 (the empty stack) and whose low half is
  an LDS address. Entries 0–30 live in LDS, later ones in scratch, and pushes stop at 76. The push address's high
  dword is `v_med3_u32` of two aperture constants and that whole pointer; the host's rewrite changes the constants
  from (0x80000000, 0x70000000) to (0x20000000, 0x10000000) (F249).
  - LDS entries: the pointer's high half is negative (0xff84–0xfffc), so the pointer is ≥ 0xff840000 and the median is
    the upper constant, LDS, with either pair.
  - Spilled entries: the high half is 0x0000–0x00b4 ((76 − 31) × 4), so the pointer is ≤ 0x00b4ffff, under both lower
    constants, and the median is the lower constant, private, with either pair.
  - So the rewrite sends every one of the 76 possible entries to the same aperture as on the console. Pushes go
    through FLAT and pops through `ds_read_b32` / `scratch_load_dword`. For spilled entries that pairing relies on
    FLAT's private aperture and the `scratch_` instructions resolving through the same per-wave scratch base, as the
    RDNA 1.0 ISA describes for the private aperture. TODO(verify): the section number and the lane swizzle, AMD's
    "RDNA 1.0 Instruction Set Architecture", flat and scratch memory chapter.
  - This removes the one host-made defect that would hit only deep (rare) rays: a mis-paired push and pop on spill.
- **What is left for hypothesis 1** is wrong input to a correct walk, or wrong shading of its hits:
  - tree data read while being rebuilt or refit (the build chain's ordering, F371's argument pointer in node data);
  - stale or zero pages under the trees or the hit materials (hypothesis 3);
  - a hit shading or denoise pass downstream.
  All of these sit downstream of, or inside, what arm B removes (no traversal dispatch, so no reflection samples),
  and none of them is in arm C either.
- **If box time is short: arms A (with the pause) and B.**
  - A shows whether the bench shows dots at all, and whether pausing removes them.
  - B decides "the reflection traversal and what it feeds" against everything else in one run.
  - C is needed only if B still has dots (another RT pass against not RT).
- **The pause is weak evidence until a paused shot is viewed.** The title's pause menu may blur, darken or cover the
  scene behind it, which would remove the dots for a reason that is not history. Arm A's paused shots therefore get a
  look (in the session scratchpad, deleted after, with the top session's leave) before any reading of them.
- **Thresholds.** No shot of the dots exists to calibrate on. The committed shot metrics (exp 0299/0303/0305's
  `*.wh.txt`) only bound the ordinary brights: the scenes' p99 luma runs 0.68–0.96. The shots are also the 1920×1080
  window after the title's upscale, which dims a one-pixel dot. So `dots0382.py` now defaults to T 0.70 / D 0.25 and
  also counts every shot on a 3 × 3 grid, T 0.55 / 0.70 / 0.85 by D 0.15 / 0.25 / 0.40, with the grid's medians at the
  end. An arm comparison that holds on most of the grid does not hinge on one threshold.
  - Self-test: six dots at T 0.70 (four 1-px, one 2×2, one dim at 0.75), five at T 0.85; none in a bright area or on
    its edges; kept 6 of 6 unchanged, 0 when moved.
  - Synthetic shots (1920×1080, σ 0.05 noise, 20/30/40 one-pixel dots): the counts match at every grid point, with
    no false dot from the noise.

**Bookkeeping.** Findings F640–F659 (the top session's range). Branch `exp/0382-white-dots`, never main.

**Status** (2026-10-29 ~23:55). Claimed in the repo. The box side is not claimed: this session's permission
classifier refused the `mkdir ~/bc5-work/exp0382` of the GO'd read as a write to a shared resource, so no file has
been written on the box. The arms need that permission (box writes: the lock line, the private working directory, the
save snapshot, the shots) before they can run from this session.
