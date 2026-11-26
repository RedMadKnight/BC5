# exp 0442 bake 1c+1d: docs text (values read from the box after the swap, 2026-11-22 19:49)

## CLAUDE.md, machine context: the shared builds' sentence (insert before "since 2026-11-21 21:00 the shared builds are patch `589ef163`")

since 2026-11-22 19:49 the shared builds are patch `d45618c6`: exp 0442's bake 1c+1d (the maintainer's approval to deploy of 2026-11-22). TITLE2's 28 generic rows now apply to every title through `kGeneric0442`; each turns off with `NAME=0`, among them the 20 library words, MEC_INDIRECT, REMEMBER_UNMAPPED, APR_PARALLEL=8, GPU_CHECK, CS_PREFIX, INDIRECT_DRAWS=multi, DMA_SNAPSHOT=4096 and LAZY_RELEASE=30,eager. Nothing learned is left: the aliases and their file, GUARD_SPLIT, GUARD_LEARN_LOG, HOST_INDIRECT, exp 0379's zero list and SKIP_PGM's row are gone. Exp 0273's ray-tracing switch is gone whole: the Emulation menu item, `KYTY_BC5_RT`, the second title's BVH build list `KYTY_BC5_RT_BUILD_PGM`; ray tracing is always on; an old `RayTracing.<ID>=` line in an input configuration is accepted, reported once and not written back. Eight gone words are reported once and unset by `kGone0442` (normal only; lean has no report). Three D28 cost fixes are on unless "0": `BC5_DIRECT_0442_GC_NOCOPY`, `BC5_DIRECT_0442_CS_SKIP`, `BC5_DIRECT_0442_SNAP_GROW` (the DMA snapshot ring starts at 8 MiB and stayed there on the first title). TITLE2 keeps five rows: DMA_SYNC, FLAT_APERTURE, AMM_PRT, GPU_CHECK_PRODUCT and SHADOW_LABELS. The builds are normal `28ab1389`, lean `b0f856ed`, archive `ed9f5dfe`, with backend direct.cpp `9956715f` and indirect_check.cpp `f07ba4bf`. The first title smoke lean 58.39 and normal 57.95 flips/s, PASS. The bake was deployed with a lean gap on the first title of about 1 % (bake 1c like for like: 57.43 against 58.01 flips/s, below in 3 of 3 pairs, more missed vsyncs); D28 looks for its cause. Undo: `bash ~/bc5-work/exp0442/bake442kit/undo0442.sh` to `589ef163`. The old binaries are kept in `~/bc5-work/exp0442/swap/`.

## HANDOFF row (§2, next free F number)

| F‹n› | **Bake 1c+1d (exp 0442): every title gets TITLE2's 28 generic rows; nothing learned is left; the ray-tracing switch is removed (2026-11-22 19:49).** The patch goes from `589ef163` to `d45618c6`: normal `28ab1389`, lean `b0f856ed`, archive `ed9f5dfe`. The 28 rows apply for all titles through `kGeneric0442`, each with a working off-word. The learned artefacts and exp 0379's zero list are removed. Exp 0273's RT switch (menu, KYTY_BC5_RT, the second title's build list) is gone; RT is always on, and old config lines are ignored. Three cost fixes come with their off-words: GC_NOCOPY, CS_SKIP, SNAP_GROW (the snapshot ring goes from 64 MiB to 8 MiB on the first title). The det test passes 323/0. Smoke passes on the first title lean and normal. Lean A/B against the old shared lean, like for like: −1.0 % flips/s, from more vsync misses near the 16.7 ms edge. Deployed on the maintainer's word with the cause open (D28). A private null rebuild of the unchanged sources showed the same gap, so code layout is one candidate; perf counters come next. | `experiments/0442-title-defaults-audit/README.md` (bakes 1-1d, runs 1-7), `bake/` | high for the code, the det test and the smoke; the 1 % cause is open; the second title is untested on the bake (not installed) |

## README section, bake 1 → bake 1c+1d (replaces the ‹› values of BAKE-TEXT.md)

- What went in: bake 1 (the 28 rows, nothing learned, zero list gone), plus 1c's three D28 cost fixes, plus 1d's RT switch removal, in one swap.
- Bakes 1a and 1b were measured and not swapped. Their lean A/Bs and the null private build (run 5) showed that the gap does not come from the five G6+G7 rows or the three G4 rows.
- Runs 1-7, in short:
  - run 1: arm P, 4 runs; noise;
  - run 2: the single-row arms; only DMA_SNAPSHOT's +64 MiB GTT was real;
  - run 3: 1a;
  - run 4: 1b;
  - run 5: the null build and the G4 rows;
  - run 6: 1c swapped, failed, undone;
  - run 7: the 1c+1d function checks.
- Four procedure findings:
  - the RA24 display line is excluded by name;
  - R55 now covers file reads during a measured run (the scp of 14:54);
  - in every A/B the first run after the start was the fastest control run;
  - The first title's lean is vsync-bound, so 1 % fewer flips means about 80 more missed vsyncs in 140 s.
- input.example.cfg no longer lists RayTracing (edited on the branch).
