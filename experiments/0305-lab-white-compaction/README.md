# 0305 — The second title's white lab with ray tracing on and the BVH compaction running

**Question.** Exps 0299/0303 (F362, F366): the lab's white comes from the RT reflection traversal (0x11d049aa00,
0x11d04a6000, with 0x11d04bb900). It appears with RT off, where the trees are never built, and with RT on, where they
are built without the compaction 0x909974400, which play-pkg.sh skips by default (F207, F275). With RT on and nothing
skipped, so that the compaction runs, does the white go away? If it does, the real fix for the reflections is making
the compaction run correctly (the BVH session's main thread), not skipping the traversal.

**Plan** (the maintainer's yes, relayed by the top session: "Tak, puść krótki test z RT w laboratorium z włączonym
krokiem porządkowania struktury"; one run of ~4 min).
- **The bench:**
  - Exp 0303's bench with a fresh `play-pkg-0305.sh`, derived from the then-current `play-pkg.sh` by exp 0299's three
    edits (checked by diff, md5 recorded).
  - Exp 0299's private working directory and lab save copy; the shared normal build; route `slot4-90.cmd`.
  - A private input configuration with `RayTracing.PPSA03671=on`, which overrides the environment (experiment 0273).
- **L10:**
  - RT on and `BC5_DIRECT_SKIP_PGM=0`. That is not empty: the launcher's `${BC5_DIRECT_SKIP_PGM:-909974400}` would put
    the compaction back for an empty value, and 0 names no program.
  - `BC5_DIRECT_DRAW_JOURNAL=200:40` for one window once the lab is up.
  - `bc5-pkg.env` is checked for any other skip line before the run.
- **Proof, from the run's journal:**
  - RT on: no "ray tracing off" line;
  - the compaction ran: no "skip pgm" line at all, and 0x909974400 dispatches in the draw-journal window or its
    "mec pgm" survey line.
- **Measured** as in exps 0299/0303: `wh0299.py`'s numbers against L8 (RT on, compaction skipped: white 6.4 %) and L9
  (traversal skipped: 0.6 %); the fps counter, since the compaction once halved the frame rate (F249/F275); one shot
  viewed in the session scratchpad and deleted right after.
- **Rules:**
  - the live saves (8289704a9338a118) are never used, with checks before and after;
  - the kernel stream; a stop at the first reset or machine-down, and the top session hears of it at once;
  - no images in the repo.

**Setup as run** (the top session's GO of 13:03 CET, after its launcher change int0299; boot 664515e3).
- **13:04.** Our lock line; live saves 8289704a9338a118 (never used; checked before and after each run).
  - `play-pkg.sh` 628b2714, which now also drops the three traversal programs when RT is off; irrelevant with RT on.
    `play-pkg-0305.sh` was derived by exp 0299's three edits, the four expected lines (`raw/play-pkg-0305.diff`).
  - Build 226bcb82. `bc5-pkg.env` has no active line.
  - `input-0305.cfg` sets `RayTracing.PPSA03671=on`. The kernel stream ran throughout (`raw/window.kern.txt`).
- **Runs**, all RT on:
  - L10, 13:04–13:08: `BC5_DIRECT_SKIP_PGM=0` (nothing skipped), journal window at t = 200 s. That window fell
    after the run's end at 190 s, my mistake, so L10 has no journal window.
  - L11, 13:09–13:13: `BC5_DIRECT_SKIP_PGM=909974400`, the compaction skipped as in exp 0303's L8. This is the
    top session's control for the build change, journal window at t = 140 s.
  - L10b, 13:13–13:16: L10 again, nothing skipped, journal window at t = 140 s.
- **Shots viewed** in the session scratchpad and deleted right after: L10 t150. No image is in the repo.
- **Released 13:17:15** (BOX-QUEUE line 97).

**Result** (`raw/`).
- **RT on and the skips as asked** (`raw/L10.rt.txt`, `raw/L11.rt.txt`, `raw/L10b.rt.txt`):
  - 0 "ray tracing off" lines in every run;
  - no "skip pgm" line in L10 and L10b;
  - in L11 one line, "skip pgm 0x909974400: dcb dispatch op 16 … dropped". As in exp 0303's L8, the title dispatches
    the compaction in the lab as a DISPATCH_INDIRECT in a graphics buffer.
  - Neither 40-buffer draw-journal window (`raw/L11.jw.txt`, `raw/L10b.jw.txt`) caught a dispatch of 0x909974400.
    So it runs at load or now and then, not in every frame.
- **No kernel event:** 0 fault lines, the amdgpu dmesg count 120 before and after.
- **The numbers** (median over the lab shots, a static view; fps the mean over the run's last 40 s):

  | run | build | skipped | luma mean | p90 | p99 | white | clipped | chroma | flips/s |
  |---|---|---|---|---|---|---|---|---|---|
  | 0303 L8 | e62a97c6 | 0x909974400 | 0.334 | 0.868 | 0.962 | 0.064 | 0.012 | 0.085 | — |
  | L11 | 226bcb82 | 0x909974400 | 0.334 | 0.868 | 0.962 | 0.064 | 0.013 | 0.085 | 48.5 |
  | L10 | 226bcb82 | nothing | 0.303 | 0.605 | 0.880 | 0.006 | 0.000 | 0.121 | 45.9 |
  | L10b | 226bcb82 | nothing | 0.303 | 0.604 | 0.881 | 0.006 | 0.000 | 0.121 | 45.6 |
  | 0303 L9 | e62a97c6 | the traversal (+ 0x909974400) | 0.302 | 0.609 | 0.883 | 0.006 | 0.000 | 0.113 | — |

- **L10's view:**
  - The lab renders with correct RT reflections: the glossy floor mirrors the blue wall screens and the room, and the
    glass shows the shelves behind it with the screens reflected on it.
  - Nothing is washed out. Chroma is higher than with the traversal skipped (0.121 against 0.113): the reflections'
    colour.

**Verdict.**
- **With RT on, running the BVH compaction 0x909974400 removes the lab's white and gives correct RT reflections.**
  - The compaction is the only difference between the white runs (L8, L11) and the correct ones (L10, L10b).
  - The build change is ruled out: L11 on today's build equals L8 on the old one.
  - So the white is the traversal reading uncompacted trees: the compaction skipped since F207/F275, or the trees
    never built with RT off (F362).
- **Cost here:** about 3 flips/s (45.6–45.9 against 48.5), not the halving seen elsewhere with the compaction on
  (F249/F275).
- **The real fix for the reflections is to run the compaction**, instead of skipping the traversal (F362's RT-off
  change stays right for RT off, where no tree is built).
  - Whether the compaction is safe to turn back on everywhere is not tested here and belongs with the BVH work: the
    night scene's GE faults of F207, S6N's route, the frame rate.
  - A lab-only test passes; the default (`BC5_DIRECT_SKIP_PGM=909974400` in the launchers) is the maintainer's call
    after that.
