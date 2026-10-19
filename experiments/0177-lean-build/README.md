# 0177 — A lean emulator build without tracing, journals or measurements; the start screen still at half speed

**Question.** The maintainer, 2026-10-19 evening: "can you build me a version next to the
emulator with no tracing, no stacks and no other measuring mechanisms, inside or outside? Can you
review the whole code?" Also open from exp 0175: since run 830 the second title's start screen
runs at 25 flips a second instead of 41–50. Was that the per-thread CPU sampler of exp 0174?

**Setup.**
- **Code review** of the host tree (KytyPlus `f266548` plus `backend/kytyplus-patches/0001-bc5-lle-agc.patch`)
  and the dev box's launchers. It looked for everything that traces, journals, dumps, counts,
  samples, profiles or walks stacks:
  - the session's logging switch and the ~60 diagnostic environment switches of the host and the
    direct path;
  - the Tracy profiler, compiled in with `TRACY_ENABLE` and `TRACY_ON_DEMAND` but started only with
    `--profiler-direction Network`, which leaves one call per `KYTY_PROFILER_*` zone;
  - the stack walks: `backtrace()` in the VMA trace, the AMM fault trace and the fatal crash
    handler, and the frame-pointer walk of `KYTY_BC5_APR_CALLERS`;
  - outside the emulator: the journal, frame profile, timeout probe, frame counter, audio measure
    and CPU sampler that `play-pkg.sh` turns on, `PLAY_CAPTURE` in `play-astro.sh`, and the input
    recorder `KYTY_BC5_INPUT_RECORD` in `bc5-run.env`.
- **The lean build** is the CMake option `KYTY_BC5_LEAN`, which defines `BC5_LEAN`. It is described
  in `backend/kytyplus-patches/README.md`.
  - `Bc5LoggingOn()` is a `constexpr false`.
  - Every read of a diagnostic switch goes through `BC5_DIAG_ENV`, a null pointer in this build
    (105 sites in 19 files).
  - The profiler zones expand to nothing, and the profiler direction is always None.
  - The guest's printf is Silent, and the journal mode is fixed to "min" without a journal.
  - A `constructor(101)` in `main.cpp` unsets the diagnostic variables and sets `BC5_LOGGING=0`.
- **Build.** `~/bc5-work/kytyplus-build-lean` uses the normal build's options plus
  `-DKYTY_BC5_LEAN=ON`. `tools/scripts/bc5-build.sh` now builds both.
- **Launchers.** `BC5_LEAN=1` in `play-any.sh`, `play-pkg.sh` and `play-astro.sh` (here) picks the
  lean binary. It sets none of the measurements and starts no sampler. It unsets the input recorder
  and `PLAY_CAPTURE`, and it logs to `play-*-lean-last.log`. The desktop entry is
  `bc5-emulator-lean.desktop`, shown as "BC5 emulator (lean)".
- **`lean-check.sh`** (here) runs one 90-s start of the second title without input. From outside
  the emulator it reads `gpu_metrics` every 2 s, takes one screenshot (kept private, not
  committed), and reads the process's RSS and thread count.
- **`load-sampler.sh`** (here) is prepared for the load-phase frame drops of exp 0175. It records
  the whole box's CPU, processes, disk and the emulator's threads each second. Not run yet.

**Result.**
- **The lean binary runs.** Runs ld4 and ld6 (lean) and ld5 (normal) reached the start screen
  ("PRESS ⨯ TO START", screenshot at 74 s) and were alive at 86 s. Both builds had an RSS of
  3.7 GB and 71 threads.
- **What is gone.** These strings are in the normal binary and not in the lean one:
  `fps counter`, `pieces dry`, `two rings, time` and `timeout probe`.
- **What the lean log still has.** ld6 wrote 288 lines against the normal ld5's 481:
  - the launcher's settings header;
  - the direct path's setup lines (GDS, GWS, OA) and four `bc5 system param` lines;
  - about 250 lines of `bc5-direct: shared map at 0x0+0x10000: -22`. This failed map, printed each
    time, is not a measurement. It is in every log since run 635 (2026-10-18). TODO(verify) what
    asks the backend to map address 0.
- **The start screen speed has nothing to do with the diagnostics.** Exp 0175's runs
  (`startscreen.sh`, t 55–82 s) and this one's:

  | run | time | variant | flips/s |
  |---|---|---|---|
  | journal+probe | 18:14 | journal, timeout probe | 25.0 |
  | journal_noprobe | 18:24 | journal | 25.3 |
  | logoff_probe | 18:26 | logging off, probe | 26.0 |
  | logoff_noprobe | 18:28 | logging off | 25.9 |
  | nosampler | 20:23 | no CPU sampler | 25.5 |
  | withsampler | 20:25 | CPU sampler | 25.6 |
  | ld5 | 21:27 | normal build, logging on | 24.8 |

  The CPU sampler costs nothing measurable, so the launcher comment that blamed it is corrected.
  Runs up to 828 had 41–50 flips/s on the same screen.
- **The GPU clock.** During ld6 the governor-patched `gpu_metrics` gave:
  - gfx activity 64–100 %;
  - average gfxclk 1050–1071 MHz, with one sample at 914 (`raw/lc-ld6-lean.clk`, fields 12/30/36
    after the 4-byte header);
  - the same as at 20:29 in run ld3 (1044–1059 MHz).

  The governor `cyan-skillfish-governor-smu` is configured for 1850–2150 MHz (F176). It has run
  since 09:00 without a restart. The kernel's gfx ring timeouts and resets began at about 17:51,
  with the GPU watcher of exp 0160 (F229), and the halving dates from the same runs.
  TODO(verify): exp 0043 found this board's own clock fields unreliable, and these are the
  governor's patched values. A reading of the same field before 17:51 is not on record. The
  clock probe of exp 0043 (a GPU submission) would settle it and needs the maintainer.

**Verdict.** The lean build works and stands next to the normal one (F236). It cannot report a
frame rate. The comparison of lean against normal speed waits for the GPU clock, because every
start since run 830 runs at half speed whatever the diagnostics do (F235). Restoring the clock is
the maintainer's choice: restart the governor service or the box, or set the governor's range
again over D-Bus.
