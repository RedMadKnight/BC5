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
  - Slot 4 (✕, down ×3, ✕, ✕), with each key sent only when the journal shows the screen running (revised
    2026-10-30, below: exp 0379's D3 lost fixed-time keys to a save list still loading from a copy of the live saves).
    The scene then idles with the camera where the save left it, apart from one camera nudge.
  - Shots by exp 0190's `shots.sh`, into one directory per phase, measured per phase (`MODE`, below), at times
    relative to G, the start of gameplay found by the gate.
  - The kernel log is streamed to the laptop during each arm.
- **Measured on the box only** (the shots never leave it): exp 0299's `wh0299.py` (luma, white and clipped shares,
  the whole shot) and `dots0382.py` per phase.
  - `dots0382.py` counts isolated bright points: luma ≥ T, ≥ D above the mean of the 7×7 ring around them, at most
    two bright pixels in that ring, one count per 3×3 maximum; T/D 0.70/0.25 and a 3 × 3 grid (Thresholds, below);
    `ROI=x0,y0,x1,y1` restricts it to a fixed scene region without HUD or menu. It also counts how many of a shot's
    dots sit within 2 px of the previous shot's ("kept"). That is a description of the shots, not a test of
    history: with shots 1–10 s apart and no camera control, a low "kept" can be scene motion and a high one static
    geometry or the HUD (Codex review REVIEW-03, R3).
  - Frames are told apart by the SHA-256 of their decoded RGB pixels (REVIEW-03, R2; below). Each phase reports
    its distinct frames, so a paused phase whose shots are one frame shows as one.
  - What kind of dot (added 2026-10-30, below): colour, size, contrast, the view's change between shots, a reading
    per phase, `--compare` between phases, and a private contact sheet.
  - Tests: `python test_dots0382.py` (laptop; numpy and PIL): the self-test, the review's counterexample, an exact
    repeat, the ROI, `--compare`, the contact sheet.

**Order of the box steps** (revised after the Codex review, REVIEW-03, R1/R4/R5; each step only if the one before
showed what it needs):
0. **The private build** (`build0382.sh`, CPU only, ~3 min, no emulator; times revised 2026-10-30): the shared
   normal objects with `controller.cpp` + `patch0382-input-rt.diff`, to `~/bc5-work/exp0382/rt/kyty_emulator`, for
   step 2's one-run form. It can run before A1.
1. **A1, reproduce** (`MODE=pause`, RT on, the defaults, the shared build; the route ~150 s, then G+220 s, then
   ~2 min of numbers): phase `run` (every 10 s from G+60 to G+130, a 1-s burst G+111–115, the camera nudge at
   G+117), options at G+140, phase `paused` (G+150–170), options at G+180, phase `after` (G+190–210). The route's
   four shots and one running and one paused shot are viewed (in the session scratchpad, with the top session's leave,
   deleted after) to check the route, fix the ROI, see the dots' size and whether the pause menu covers the scene. If
   A1 shows no dots in `run`, stop: the bench does not reproduce the symptom, which by itself confirms nothing about
   memory pressure (the scene, time, motion or an event may be missing, R4).
2. **A → C → A in the same scene**, only if A1 shows dots:
   - preferred, one run (`MODE=acs`, the private build of step 0): "rt off" at G+140, 30 s to settle, phase `c`
     (G+170–200); "rt on" at G+210, 30 s to settle, phase `a2` (G+240–270). The scripted input has no RT verb on
     today's builds, hence the build;
   - without a build: three fresh runs on the shared build, A, C (RT off at load), A, in `MODE=run`. Weaker: each run
     is a new start.
   Dots that leave in C and come back in `a2` tie them to the RT path being on (R4: not yet to which RT pass).
3. **Map run** (diagnostic, no images): which buffers the traversal variants write and which passes read them
   (R1). `BC5_DIRECT_DRAW_JOURNAL=250:40` journals each dispatch's user data and the descriptor tables behind it, so
   the traversal dispatches' image and buffer bases. Which of those the traversal stores to comes from the private
   disassemblies on the box (its store instructions' resource registers). A second window with
   `BC5_DIRECT_DRAW_JOURNAL_FIND=<those bases>` lists every draw or dispatch that holds them: the consumers
   (denoise, resolve, composite). Nothing is written or skipped.
4. **B, as a deliberate ablation**, after the map:
   - **B1, a neutral miss:** `BC5_DIRECT_BVH_MISS=<program>:<dword offsets>` (exp 0141, F186) runs one variant from a
     patched copy whose `image_bvh_intersect_ray` instructions return "no child, no hit" (0xffffffff). The traversal
     still runs to its end and writes the title's own miss result, so its consumers read valid data. One variant per
     run; its offsets come from scanning that variant's shader dump for the instruction's first dword 0xF1989F07.
     F186 ran it on 0x11d049aa00 only.
   - **B0, the drop:** `BC5_DIRECT_SKIP_PGM=11d049aa00,11d04a6000,11d04bb900,11d040e200,11d040c900`. It only drops
     the dispatch (`bc5LleAgc.cpp`'s skip path → `policy.cpp`'s Drop): no neutral output is written and the
     consumers still run, on stale, zero or another allocation's data (R1). Its picture is a known-incorrect path; it
     can neither clear nor convict the traversal on its own.
- **What each outcome allows** (REVIEW-03, R4):

  | Outcome | Allowed conclusion | Not settled |
  |---|---|---|
  | A has dots, C none | they depend on the RT path being on, or on its load | traversal against denoise, cache or memory; the source itself |
  | A has, B1 none | they depend on that variant's hits and what they feed | a wrong hit against downstream masking |
  | A and B1 have | that variant's hits are not needed for them | stale outputs or history, another variant |
  | A, B and C all have | at least part is in their common path | an added RT share; a mix of kinds of dots |
  | A has none | the bench does not reproduce them | not memory pressure; the scene, time, motion or an event may be missing |

**Laptop analysis** (2026-10-30 ~00:30, the top session's ask: narrow the pass, prepare the thresholds; no box
access, nothing from the title's binaries read beyond what main's experiments already state).
- **Today's defaults exclude F370's cause.** With `BC5_DIRECT_SKIP_PGM=0` the compaction runs and the traversal walks
  compacted trees, the configuration in which the lab's reflections came out right (F370). The flat-aperture rewrite is
  on in the second title's settings (D15; its "flat aperture: program … 6 stack pushes" lines are in the shared
  build's journal of 2026-10-28 16:47, a private copy on the laptop).
- **No segment-selection fault found in the traversal's stack** (worded as the Codex review asks, REVIEW-03, R6:
  this bounds the aperture choice, it does not prove the physical addresses equal). Exp 0190 decoded the walk: the stack
  pointer is one VGPR whose high half is a scratch offset starting at 0xff84 (the empty stack) and whose low half is
  an LDS address. Entries 0–30 live in LDS, later ones in scratch, and pushes stop at 76. The push address's high
  dword is `v_med3_u32` of two aperture constants and that whole pointer; the host's rewrite changes the constants
  from (0x80000000, 0x70000000) to (0x20000000, 0x10000000) (F249).
  - LDS entries: the pointer's high half is negative (0xff84–0xfffc), so the pointer is ≥ 0xff840000 and the median is
    the upper constant, LDS, with either pair.
  - Spilled entries: the high half is 0x0000–0x00b4 ((76 − 31) × 4), so the pointer is ≤ 0x00b4ffff, under both lower
    constants, and the median is the lower constant, private, with either pair.
  - So for these pointer values the rewrite selects, for every one of the 76 possible entries, the same aperture
    segment as on the console. Pushes go through FLAT and pops through `ds_read_b32` / `scratch_load_dword`. Whether
    a spilled push and its pop reach the same physical slot for every lane rests on FLAT's private aperture and the
    `scratch_` instructions resolving through the same per-wave scratch base and lane swizzle. That is unverified
    here. TODO(verify): AMD's "RDNA 1.0 Instruction Set Architecture", flat and scratch memory chapter; or a box test.
  - So a mis-selected segment on spill, a defect that would hit only deep (rare) rays, is not found; a mis-paired
    address within the right segment is not excluded.
- **What is left for hypothesis 1** is wrong input to a correct walk, or wrong shading of its hits:
  - tree data read while being rebuilt or refit (the build chain's ordering, F371's argument pointer in node data);
  - stale or zero pages under the trees or the hit materials (hypothesis 3);
  - a hit shading or denoise pass downstream;
  - the spill pairing above.
  Which of them B1 (a neutral miss) removes depends on where the dots enter; B0 (the drop) changes the consumers'
  input too, so it separates none of them cleanly (R1).
- **If box time is short:** A1 first. Without dots in A1 nothing else is worth its box time on this bench.
- **The pause is weak evidence until a paused shot is viewed.** The title's pause menu may blur, darken or cover the
  scene behind it, which would remove the dots for a reason that is not history. Arm A's paused shots therefore get a
  look (in the session scratchpad, deleted after, with the top session's leave) before any reading of them.
- **Thresholds.** No shot of the dots exists to calibrate on. The committed shot metrics (exp 0299/0303/0305's
  `*.wh.txt`) only bound the ordinary brights: the scenes' p99 luma runs 0.68–0.96. The shots are also the 1920×1080
  window after the title's upscale, which dims a one-pixel dot. So `dots0382.py` now defaults to T 0.70 / D 0.25 and
  also counts every shot on a 3 × 3 grid, T 0.55 / 0.70 / 0.85 by D 0.15 / 0.25 / 0.40, with the grid's medians at the
  end. The grid is a sensitivity check: agreement across its nine points is not nine independent confirmations, and
  without a shot of the symptom no threshold separates a defect from the title's own specular or rain sparkle
  (REVIEW-03, R3). Arms are therefore compared with each other on the same scene and ROI, not against an absolute
  count.
  - Self-test: six dots at T 0.70 (four 1-px, one 2×2, one dim at 0.75), five at T 0.85; none in a bright area or on
    its edges; kept 6 of 6 unchanged, 0 when moved.
  - Synthetic shots (1920×1080, σ 0.05 noise, 20/30/40 one-pixel dots): the counts match at every grid point, with
    no false dot from the noise.

**Codex review (REVIEW-03, 2026-10-30), folded in** (the top session accepted it; the review itself is outside the
repo, in the maintainer's audit folder):
- R1, arm B's confound: `BC5_DIRECT_SKIP_PGM` drops the dispatch and writes no neutral result, so the consumers read
  stale or unrelated data. B moved after a map run of the traversal's outputs and consumers, and split into B1 (the
  title's own miss result, `BC5_DIRECT_BVH_MISS`) and B0 (the drop, a known-incorrect path).
- R2, a confirmed bug in `dots0382.py`: frames with the same mean luma and dot count were dropped as repeats. Fixed by
  the review's patch (`review03-frame-identity.patch`, applied as is: the SHA-256 of the decoded RGB pixels);
  `test_dots0382.py` carries its counterexample. It fails on the old script and passes on the fixed one.
- R3/R5, the cheaper order: reproduce in A first, then A → C → A in one scene with a fixed settle time, numbers per
  phase on a fixed ROI, B last. `s6n0382.sh` now has `MODE=run|pause|acs`, one shot directory and one set of numbers
  per phase, a 1-s burst, and `ROI`.
- R6, the wording: "no segment-selection fault found", not "ruled out".
- **`patch0382-input-rt.diff`** (new, for MODE=acs; unbuilt, not in patch 0001): an `rt on|off` line for the
  scripted input (`KYTY_BC5_INPUT_CMD`) that calls the existing `SetRayTracing`, the same call as the Emulation
  menu's switch, applied at the next flip (exp 0273). It adds 11 lines to `src/libs/controller.cpp` in the part patch
  0001 already replaces wholesale (LF), and does nothing unless a script sends the line. Made on the laptop against
  KytyPlus `f266548` + patch 0001 as on main (51faa1b), `git -c core.autocrlf=false apply --check` passes, md5
  543a6f9c. Not compiled here: the host does not build on the laptop. Integration into a private build is the top
  session's (D19).

### Morning preparation (2026-10-30, before the box steps)

The maintainer allowed box writes for this experiment this morning (his words to the top session: "masz zgodę -
działaj dalej"). The box order is 0381, then 0380's checks, then this experiment, on the top session's GO. Still no
description of the dots from him, so the arms have to tell from the private shots what they are. Changes, laptop
only:
- **The route is gated** (`s6n0382.sh`). Exp 0379 started three times from a copy of the live saves on 10-30:
  - D3: the save list was still loading at ~5 fps at 88.5 s, so the down and cross presses were dropped and the
    menu stayed;
  - D2 and D4: GPU events at t 61 s, before the first key (the same pages and program; exp 0380 classifies them).
  Now each key waits until the journal's frame profile lines show the screen running: a new flip since the last
  poll and ≥ 25 flips in the newest 3 s of journal time, on 2–3 polls in a row. The first ✕ waits from 85 s, down ×3
  and ✕ wait ≥ 6 s after it, and the Continue ✕ ≥ 6 s after that. A load is 5 flips slower than 55 ms, or no new
  flip. G is the first second of a running screen ≥ 3 s after the load, and all later times are G+.
  - Each stage has a deadline: the start screen by 160 s, the list within 90 s of its ✕, the menu within 60 s, the
    load within 40 s of Continue, gameplay within 150 s of the load. A missed deadline ends the arm as `ROUTE: …`
    with no phase shots.
  - Every poll goes to `raw/<tag>-route.txt` and one private shot per stage to `shots-<tag>/route/`.
  - The stand-in run (laptop, a virtual clock, a fake game that drops keys while its list loads, the real loop):
    - the normal route reached G at 146 s, and the arm ended at G+225 (`pause`) or G+285 (`acs`) with its keys in
      order;
    - a list that never ran ended as "ROUTE: the save list did not run within 90 s of its cross";
    - a load with no flips at all was seen as a load.
    This checks the loop's logic only. The title's real flip rates at each stage are first seen in A1's
    `raw/<tag>-route.txt`.
  - Any amdgpu kernel line still ends the arm. A GPU event before the menu (exp 0379's 61-s event) is not this
    experiment's question; a retry is the top session's call.
- **What kind of dot** (`dots0382.py`, `s6n0382.sh`):
  - per dot, its colour (neutral when (max − min)/max of its RGB is ≤ 0.15, else tinted), its size (pixels of its
    5×5 above halfway from the ring to the peak), and its contrast;
  - per shot, the view's change: the share of pixels whose luma moved by > 0.04 since the previous shot;
  - a camera nudge in the run phase, the right stick right for 300 ms at G+117, between the burst (G+115) and G+120;
  - the readings per phase, with their thresholds printed:
    - in a still view (change ≤ 0.02), dots that move from shot to shot (median kept share < 0.25) are per-frame
      noise, and dots that stay (≥ 0.6) are tied to the scene or to a stuck buffer;
    - at the largest view change (≥ 0.15, the nudge), dots that keep their screen position (≥ 0.6) are stuck to the
      screen, a buffer that is not reprojected; otherwise they moved with the view;
  - `--compare` between phases: the share of B's dots within 2 px of any of A's (run → c: dots that RT off keeps are
    scene brights, not RT's), and the change from A's last shot to B's first. Pairs: `run → after` (pause);
    `run → c`, `run → a2`, `c → a2` (acs);
  - each phase reports its distinct frames by SHA-256: a paused title that presents one frame shows as one;
  - a contact sheet per phase, `shots-<tag>/<phase>-sheet.png`: the 48 highest-contrast dots, 21×21 crops at ×6. It
    is the title's imagery, so it stays on the box like the shots; viewed only with the top session's leave, and
    deleted on the laptop afterwards;
  - the synthetic tests cover each reading; one 1080p shot takes ~2.3 s on the laptop.
- **The private build for A → C → A** (`build0382.sh`, `build0382.py`, after exp 0372's): the shared tree's
  `controller.cpp` is checked by git blob (5cdb29a, patch 0001's on main 49f1116, md5 40a0e7b6), copied into
  `~/bc5-work/exp0382/src`, the diff applied (`git apply`, LF) and checked again (blob 44daf5b, md5 7d3c26f9: the
  diff's own index line, reproduced on the laptop). That one unit is compiled with the shared build's compdb command
  and relinked with the shared objects and archive (bb50b2e0) into `~/bc5-work/exp0382/rt/kyty_emulator`. Shared
  builds, the tree, `play-pkg.sh` and the shortcuts are only read.

### Result (2026-10-30 08:37–09:39)

The maintainer gave his yes for box writes in this session's chat, on the top session's GO for the private build, A1
and the viewing of private shots. Pins held throughout: shared normal 58c4a627, archive bb50b2e0, `play-pkg.sh`
55531ab6, live saves 377a8d456a9b4cb1 before and after each arm. Numbers are in `raw/`; shots, sheets and journals
stay on the box.

**Private build.** `~/bc5-work/exp0382/rt/kyty_emulator`, md5 11f8bc19, 0 errors. The shared binary, archive and tree
were unchanged afterwards. It was not run: step 2 needs dots from A1.

| Arm | Build, mode | Ended | Kernel lines | Flips | Dots |
|---|---|---|---|---|---|
| A1 | shared, `pause` | ROUTE: "the start screen did not run by 160 s" (no key sent) | 0 | 3,400 in 156 s | no shots |
| A2 | shared, `pause` | pass at G+220 (G = 140 s, Continue 99 s, load 101 s, 368 s in all) | 0 | 9,383 in 363 s | below |

- **A1 was my gate's fault** (F700). The threshold of 25 flips/s came from 16 ms flips in an older extract; this
  start screen runs at ~22 flips/s (43 ms). The gate now asks ≥ 15 flips/s in the menus and ≥ 20 after the load.
- **The gated route reaches gameplay from a copy of the live saves** (F700): start-screen ✕ 87 s, slot keys 93 s,
  Continue 99 s, G 140 s, then ~30 flips/s. The shots show the slot list with the highlight on its way down and the
  Madripoor scene. No GPU event this time, so nothing to add to F443's count for exp 0381.
- **The whole-shot counts are not dot counts** (F701). The first sheet is MangoHud's text (digits, "120v1", the clock):
  the 154 dots per shot, like the rest of `raw/A2-*-dots.txt` without `roi`, mean nothing. All counts below use
  `ROI=0,260,1920,870`, which leaves out both overlays, the tutorial box and the subtitles.
- **The pause menu hides the scene** (F702). It is nearly opaque: mean luma 0.049 against 0.215 running, and the 158
  "dots" there are its text. So if he paused with Options, seeing no dots then says nothing about history, and
  hypothesis 2's main support falls away. Whether he used this menu is not known.
- **Inside the ROI** (F703), `run`: median 61 dots per shot, 10 % neutral, median size 8 px; `after`: 60 dots, 7 %
  neutral, size 8 px. The counts are level across the phases.
  - The 48 highest-contrast dots are the scene's lamps: string bulbs and one small lamp, with the title's colour
    fringing.
  - The idle camera drifts 0–5 px between shots, so no pair is still (change 0.14–0.53) and the still-view reading
    never applies. The new `--transient` mode aligns the views first.
  - The nudge worked: a 59 px jump, seen between t114 and t115 because the burst's shots ran late. 1 of 67 dots kept
    its screen position, so these dots belong to the world, not to a stuck screen buffer.
  - Dots with no match in the neighbouring shots: median 18 of 61 per shot, 0–2 of them neutral, 0–3 of size ≤ 3. At
    the lowest thresholds (T 0.55, D 0.15): 1,020 over 13 shots, 12 neutral, 47 of size ≤ 3.
  - Those 47 are all of the small ones, and I viewed them, along with the 48 highest-contrast unmatched dots at both
    thresholds. All are scene detail: neon strips, cable edges, small lamps, shirt pattern, colour fringes. None is
    an isolated white point.

### Verdict

**In this scene, on this bench, the white dots do not reproduce** (F704): the outcome table's "A has none". A2 ran
~6 minutes in Madripoor from his slot-4 save, RT on, and its shots hold no isolated white points. By the rule above
the arm stops here, so A → C → A, the map and B were not run, and no RT pass is implicated or cleared. There is no fix
candidate.

**What this does not show.** It says nothing against the dots being real, nor about memory pressure.
- It sampled 13 frames of about 2,100 in the run phase, so a rare or brief dot would be missed.
- The character stood still in one scene for ~6 minutes. He reported dots within 30–60 minutes of play, so scene,
  motion, time or pressure may be what is missing.
- The shots are the 1080p output; a dot dimmer than T 0.55, D 0.15 would not count.
- Without his description, I am assuming "white dots" means isolated white points. If he meant the string lights,
  or anything else in this scene, the result reads differently.

**What would move it forward:** his description or one private shot taken when he sees them. Failing that, shots
across a longer, moving route; `Tryb fotograficzny` (photo mode, in the pause menu) would give the still view the
pause menu cannot, untested so far.

**Bookkeeping.** Findings F700–F704 here, for HANDOFF (from the top session's range F700–F719). Branch
`exp/0382-white-dots`, never main.

**Status** (2026-10-30 09:45). Stopped at step 1's rule: A2 passed and shows no white dots. Steps 2–4 were not run.
Claimed in both places; the box's lock is clear and `BOX-QUEUE` has the done line.
