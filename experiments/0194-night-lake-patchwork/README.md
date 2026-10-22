# 0194 — The night lake's patchwork water

**Question.** In the second title's night levels the lake renders as a patchwork: rectangles fixed to
the water surface, some with waves and rain sparkle, others completely flat (experiment 0192, F251).
It shows with and without the reflection fix, and with the TF ring off. Which input of the water's
rendering do some rectangles never get, and which producer leaves it out?

**Setup.**
- BC-250 dev box, 2026-10-22 10:15–13:20. Kernel 7.2.9-ogc3.1. The `ubuntu` distrobox as recorded in
  exp 0191 (Mesa and libdrm not re-read). Every run used the normal launcher's settings
  (`play-pkg.sh`: TF ring on, skips `11d049aa00,11d04a6000,909974400,11d04bb900`, GPU check on,
  chains `=2`, DMA snapshots 4096) plus the switches listed per run.
- Diagnostic host binary `~/bc5-work/exp0194/kyty_emulator` (12:04:59, sha256 86cf0d0e…). It is the
  shared build's objects (10:22:48, exp 0193's touchpad mapping included) plus `bc5LleAgc.cpp` with
  `edit0194.py`, compiled and linked by `build0194.py` (exp 0193's method, one unit). The shared
  source and binary are not touched. The edit adds diagnostics only:
  - `BC5_DIRECT_DRAW_JOURNAL` also writes, for every indirect draw (0x24, 0x25, 0x2c, 0x38), the
    arguments as they read at submission through the buffer's `SET_BASE` index 1. It flags
    "cp-skip" where the GPU check of exp 0052/0057 (`BC5_DIRECT_GPU_CHECK`: more than 2^20
    vertices or 64 instances) would skip the draw.
  - The same single-draw arguments are read again at the buffer's fence completion
    (`args at completion`, through exp 0157's range hook). This needs chains off: with chains the
    completed job is the chain, not the buffer.
  - `BC5_DIRECT_DRAW_JOURNAL_EVERY=<s>` repeats the journal's window every `<s>` seconds, each
    window opened by a line with the journal time and the wall clock.
- Scripts (here, copied to `~/bc5-work/exp0194`):
  - `run-0194.sh`: the W/S runs. It saves `_SaveData/PPSA03671` before the run and restores it
    after; the saves were verified identical after each run.
  - `run-0194b.sh`: the L runs. It works in a private working directory,
    `~/bc5-work/exp0194/wd`: its own `_SaveData` is a copy of the maintainer's lake save
    `~/bc5-work/saves-lake-1153`, and every other entry is a symlink into `~/bc5-work`. It goes
    through `play-pkg-0194.sh` (`raw/play-pkg-0194.diff`: that working directory, a private
    `KYTY_BC5_SAVEDATA_DIR`, and `BC5_DIRECT_DMA_SNAPSHOT` overridable), so the maintainer's saves
    are never read or written. It also stops only the emulator it started.
  - `input-0194.cfg` turns the keyboard layout off (`DefaultKeys=off`). In run L1, keys typed at
    the box drove the game.
  - `play-water.sh`: the maintainer's shortcut "BC5 emulator (woda 0194)".
  - `snap0194.sh`; `wj0194.py`, `am0194.py`, `cmp0194.py` for the journal.
- **The bench.** Scripted pad input (`KYTY_BC5_INPUT_CMD`) is read as lines are appended, so a run
  can be driven step by step:
  1. Title: cross (`interactive.cmd`, t ≈ 60 s). Slot list: down, down, cross (Saved Game 3,
     22/10 11:52). "Continue Game": down, cross.
  2. About 55 s later the game stands at the "Parry" prompt by the outpost.
  3. Options, down ×4, cross (Photo Mode), triangle (UI hidden).
  4. Right stick left 1.6 s, R2 1.5 s, right stick down 0.35 s.

  The result is a frozen view down onto the near half of the lake, the same in every run (see
  the shots `r-L*/shots/*-v1.png` on the box). Screenshots, scene dumps and journals stay on the
  box (`~/bc5-work/exp0194/r-*`, `~/bc5-data/captures/play-20261022-*`).

**Result.**

| Run | Switches over the launcher | What it reached | Water in the frozen view |
|---|---|---|---|
| W1–W3, S1–S4 (10:45–11:21) | journal | the 10:11 pad recording replayed: stayed at the title, picked an empty slot, opened the game's "delete save?" dialog (not confirmed), or fought elsewhere | no lake |
| maintainer 12:00 ("woda 0194") | journal | lake shore at 12:01:04, then TCP write faults (12:01:34) and fence timeouts | patchwork (shot) |
| L1 (11:57) | journal | lake shore fight at t 115–125 s (after keyboard input that was not ours) | patchwork |
| L4 (12:13) | journal every 4 s | the bench (first time) | patchwork |
| L5 (12:24) | journal for three lake-only PS, G-buffer dumps | the bench | checkerboard near the shore |
| **L6** (12:36) | `BC5_DIRECT_CHAIN=0 BC5_DIRECT_DMA_SNAPSHOT=0` | the bench | **clean** |
| L7 (12:44) | `BC5_DIRECT_DMA_SNAPSHOT=0` | TCP write fault + ring timeout after the load (12:47:04) | lost |
| L8 (12:50) | `BC5_DIRECT_DMA_SNAPSHOT=0` | the bench | heavy patchwork |
| L9 (12:56) | `BC5_DIRECT_CHAIN=0` | the bench | heavy patchwork |
| L10 (13:02) | `BC5_DIRECT_CHAIN=0 BC5_DIRECT_DMA_SNAPSHOT=0` (L6 repeated) | the bench | heavy patchwork |
| L12 (13:11) | `KYTY_BC5_AMM_ZERO_AUTO=1` | the bench | a few patches by the left shore |

(L2, L3 and L11 loaded the wrong slot; L11 was stopped.)

- **The flat patches are missing water surface.** At the shore the lake bed's rocks show through
  them (L4, L5, L8). Seen from above they form a checkerboard near the camera and rectangles of
  several sizes farther out, aligned with the water plane. The far water is flat by design, with
  sparkle where it catches light.
- **Fixed for the life of a run, different from run to run.** In L10's frozen view, three shots
  over 21 s differ only in rain and sparkle: 0.2–0.3 % of the water pixels change by more than 20
  levels. Between runs of the same configuration the layout differs: L6 was clean and its repeat
  L10 heavy; L5 had a near-shore checkerboard; L8–L10 were heavy. So the pattern is not a
  per-frame race. It is state set once (at or after the load) that is never repaired.
- **Not the GPU check of indirect draws.** In the frozen lake windows of L4 every `DRAW_INDIRECT`
  of the G-buffer pass has 1 instance, and none exceeds the CP limits (`raw/L4-windows.txt`: 0
  over, max instance count 1, 15–41 zero-count draws per window). The title's indirect draws are
  per-material meshlet lists: one instance, the "vertex" count being the visible meshlets
  (`[count 1 0 0]`, NGG shader 0x11d0134500). Two caveats:
  - L1's one "cp-skip" (894 instances, `raw/L1-windows-and-cp-skip.txt`) is read from memory that
    at that moment holds an ascending array (`[19e 37e 446 44a]`), not draw arguments.
  - At completion that memory is often reused already (`raw/L3-args-at-completion.txt`:
    `[84 85 86 87]` against `[16f5 1 0 0]` at submission). Reading at submission is the reliable
    reading in a frozen frame.
- **Not the `COND_EXEC` overflow fallback:** 0 checked packets NOP-ed in L5, L6 and L8
  (`raw/gpu-check-and-chain-counters.txt`).
- **Not the submission chains or the DMA snapshots by themselves.** Patchwork shows with either
  off (L8, L9) and with both off (L10). L6's clean lake under the same switches as L10 is the
  run-to-run spread, not the switches.
- **The AMM zero-fill is the open lead.** With the automatic AMM maps zero-filled (L12, one run)
  the patchwork was the lightest of the heavy-or-moderate runs. One run cannot separate that from
  the spread.
- **The water's draw is not identified yet.** Lake view against sky view in one frozen run
  (`raw/L4-lake-vs-sky.txt`): the G-buffer materials that appear only with the lake in view are
  PS 0x11d29e9f00 (17 meshlet draws per window), 0x11d521da00 and 0x11d373f400. The forward pass
  into the HDR target (0x113d770000) is small effect quads and empty indirect emitters. The
  G-buffer dumps (`BC5_DIRECT_RT_DUMP` at 3840×2160) came out mis-detiled; the targets run at
  2816–3328 wide (dynamic resolution) in other formats.
- **Seen on the way (not the water).** A TCP *write* permission fault (`PERMISSION_FAULTS` 0x5,
  `RW` 1) followed by compute/graphics ring timeouts and resets (`raw/tcp-permission-faults.txt`):
  - W2: AMM window 0x820c37f000, in a menu;
  - the maintainer's 12:00 session: 0x83fdaa0000, at the outpost;
  - L7: 0x1765833000, right after the load.

  The same signature was in the maintainer's 10:28 session on the shared binary, so the
  diagnostic edit is not involved. The game froze after it (L7: a 26.8-s flip gap). Cause not
  examined.

**Verdict.**
- **Narrowed, not named.** The patchwork is water surface the title never draws in some
  rectangles, decided once per run and kept, with a layout that differs between runs. It is
  independent of the GPU check of indirect draws, the `COND_EXEC` fallback, the submission
  chains, the DMA snapshots (all four measured here), the reflections and the TF ring (F251). The
  per-run, never-repaired character points at per-tile state the water builds at or after the
  load from memory or data it does not get as on the console. Uncleared memory from the automatic
  AMM pool (L12 lighter) and streamed data are the candidates.
- **Next, on the bench (each run about 5 min, saves untouched):**
  1. `KYTY_BC5_AMM_ZERO_AUTO=1` against the defaults, three runs each, counting the patch area in
     the frozen view.
  2. A time series in one run: Photo Mode right after the load and again after a checkpoint
     restart.
  3. Identify the water's draw: the bake journal of the three lake-only G-buffer PS (their user
     data and tables), then compare the per-tile inputs between a clean and a patchy run. The
     RT dumps need the right pitch and format per target.
- Nothing of the edit is in patch 0001 or the shared build (diagnostic only, off unless the draw
  journal is on). The shortcut "BC5 emulator (woda 0194)" was moved off the desktop when the tests
  ended (the maintainer's request), to `~/bc5-work/old-shortcuts/`.
