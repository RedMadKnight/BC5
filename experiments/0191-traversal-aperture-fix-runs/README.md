# 0191 — The traversal with its stack pushes moved to the host's apertures: runs with the skips removed

**Question.** Experiment 0190 found that the second title's ray-traced-reflection traversals do not loop:
their waves are halted by a memory violation at the first BVH stack push, whose FLAT address uses the
console's aperture bases (F249). With `BC5_DIRECT_FLAT_APERTURE=1` (patch_0190) rewriting the two
constants to the host's apertures, do the traversal variants and the compaction 0x909974400 run without
the skips, and do the reflections appear?

**Setup.**
- BC-250 dev box, 2026-10-21 from 23:45, the maintainer's yes ("apply patch_0190.py, rebuild synced, then
  one watched run with BC5_DIRECT_FLAT_APERTURE=1, TF ring on, only 909974400 skipped; if clean, a second
  run with no skips"). Host: kernel 7.2.9-ogc3.1; the `ubuntu` distrobox (Mesa 26.0.8 RADV, libdrm_amdgpu
  2.4.131), as in exp 0189.
- Build: `~/src/KytyPlus` (f266548 + patch 0001 as in the repo, plus exp 0189's scripts, plus the other
  sessions' uncommitted presentation changes of 2026-10-21 evening) with
  `experiments/0190-traversal-flat-apertures/patch_0190.py` applied (backup of the source and the previous
  binary: `~/bc5-work/exp0190/*.before0190`), built 23:46:14 with
  `distrobox enter ubuntu -- cmake --build ~/bc5-work/kytyplus-build --target kyty_emulator -j8`, then
  `sync` (D16).
- Runs: `~/bc5-work/exp0190/run-0190.sh <tag> [secs]` (exp 0189's `run-0189.sh` writing to
  `~/bc5-work/exp0190/r-<tag>/`, plus the journal's `flat aperture` / `skip pgm` lines): the idle night
  run (slot 1 loaded by `idle-cmd.txt`, no input after), the switches in `ENVX` over `play-pkg.sh`'s
  defaults, the saves restored before and after. Armed for each run only (F229): exp 0189's
  `stall-waves.sh 115 <out> 180` (one `umr -O halt_waves -wa` dump if the journal stands still 0.7 s,
  from 115 s), and `shots.sh` (here; `spectacle` screenshots at fixed seconds).
- Runs (300 s each unless said; the night scene from t ≈ 120 s, where R1–R6, S1 and S3 of exp 0189 stalled):

| Run | Switches (over the launcher's defaults) | Traversals / compaction | GPU faults | Fence timeouts / ring resets | Wave-dump trigger | Night flips per 10 s |
|---|---|---|---|---|---|---|
| F1 | `BC5_DIRECT_FLAT_APERTURE=1 BC5_DIRECT_GC_TF_RING=1 BC5_DIRECT_SKIP_PGM=909974400` | all six run, patched / skipped | 0 | 0 / 0 | no stall (115–295 s) | 198–290 |
| F2 | `BC5_DIRECT_FLAT_APERTURE=1 BC5_DIRECT_GC_TF_RING=1 BC5_DIRECT_SKIP_PGM=1` (a dummy: no skip) | all six run, patched / **runs** | 0 | 0 / 0 | no stall (115–295 s) | 217–297 |
| B0 | none (the launcher: TF ring on, skips `11d049aa00,11d04a6000,909974400,11d04bb900`), 262 s | skipped / skipped | 0 | 0 / 0 | not armed | 236–295 |

- Raw: `raw/F1-run.txt`, `raw/F2-run.txt`, `raw/B0-run.txt` (`run-0190.sh`'s summaries), `raw/shot-diffs.txt`
  (`shotdiff.py`). The screenshots themselves stay on the box (`~/bc5-work/exp0190/r-*/shots/`).

**Result.**
- **The fix reaches every variant.** In F1 and F2 the journal has one `flat aperture` line per program, at
  its first dispatch: 0x11d049aa00, 0x11d040e200, 0x11d0488a00, 0x11d04a6000, 0x11d04bb900, 0x11d040c900,
  six stack pushes each (two `s_brev_b32`, one for the two 0x11d040… variants) — the sixth variant,
  0x11d0488a00, runs in this scene too.
- **No stall, with the skips gone.** F1 (traversals on, compaction skipped) and F2 (nothing skipped, the
  compaction 0x909974400 running) each ran 300 s: no GPU page fault, no kernel ring timeout or reset, no
  fence timeout, no 0.7-s journal stall from 115 s on (the trigger never fired), no amdgpu line in the
  kernel log. Without the fix the same configurations stalled at t ≈ 35 s (0x11d049aa00, S2), ≈ 121 s
  (0x11d04bb900, R1–R6) and ≈ 130 s (S1: compaction on; S3: 0x11d04a6000). What the launcher drops and F2
  now runs: B0's sampled skip lines (one per 4,096) put it at 16,385–20,480 dispatches of the three
  traversal variants and the compaction in 262 s.
- **The frame rate holds.** Night flips per 10 s: F1 198–290, F2 217–297, B0 236–295 (exp 0189's R7/R8:
  219–293) — the reflection passes add no visible cost in this scene.
- **The reflections are not visible in these screenshots.** The idle run stands at a prompt in the night
  scene; at 200 and 250 s the luma difference between B0 and F1/F2 (3.4–4.3 mean) is no larger than between
  F1 and F2 (3.9–4.0), and lies where the scene animates (rain, fire, the enemies' idle motion, puddle
  speckle). Whether the title now draws its ray-traced reflections needs a look at a scene with reflective
  surfaces — the maintainer's eye in play.

**Verdict.**
- **F249's cause is confirmed by the fix.** With the traversal's two aperture constants moved to the host's
  apertures, all six compiled variants and the BVH compaction run through the start screen and 300 s of the
  night scene without a stall, where each of them alone had stalled the GPU within seconds. The skips of
  F173, F207, F232, F248 (`11d049aa00`, `11d04a6000`, `909974400`, `11d04bb900`) are not needed with
  `BC5_DIRECT_FLAT_APERTURE=1`.
- **Not yet shown:** that the reflections are drawn correctly (no reflective surface in the idle scene's
  view), and long play with the fix (the maintainer's sessions). The knob stays off by default and the
  launchers are unchanged; turning it on in `play-pkg.sh` with the skip list emptied is the maintainer's
  call.
- **Patch 0001** (`backend/kytyplus-patches/0001-bc5-lle-agc.patch`) now carries patch_0190: only its
  `src/libs/bc5LleAgc.cpp` section was replaced (`swap_patch_section.py`; the box's tree also holds other
  sessions' uncommitted presentation changes, which are not in it); it applies to a clean f266548 export
  (`git apply --check`) and reproduces the box's file byte for byte. The box's normal binary (built
  23:46:14) has the knob; the lean build was not rebuilt.
