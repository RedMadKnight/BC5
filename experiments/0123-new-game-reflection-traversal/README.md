# 0123 — New Game hangs in the reflection traversal; with it skipped, the second title reaches its start screen

**Question.** New Game on the second title's Initial Setup hung the GPU queue within a second
(run 502). The maintainer: New Game leads to an animated scene where ✕ starts the game, the first
full load of the engine. What hangs, and can that scene be reached?

**Setup.**
- BC-250 dev box, 2026-10-15, maintainer present, GPU hang watcher on.
- The second title with its play shortcut's settings (`bc5-run.env.pkg-noflipdefer`, multi-draw
  packets, code aliases, ring-order waits, graphics pieces, DMA snapshots of experiment 0122).
- Input:
  - run 502: cross at 80, 100, 110 and 120 s;
  - runs 514–517: cross at 80 s (start dialog) and 100 s (New Game), nothing after.
- Variants:
  - 514: ring-order waits off, buffers of 900–950 dwords dumped;
  - 515: graphics pieces off;
  - 516: as 515, the 922-dword buffers dumped;
  - **517: play settings with `BC5_DIRECT_SKIP_PGM=11d049aa00`**. That knob drops every dispatch
    of the title's ray-traced-reflection traversal, the program found looping on bad trees in
    experiments 0058–0059 (F113–F116).
- Screenshots every 3 s from 95 s (private).
- Raw: `raw/runs-502-517.txt`.

**Result.**

| run | change | GPU timeouts | fps before / after New Game | first job to time out |
|---|---|---|---|---|
| 502 | — | 26 | 47.5 / 0.0–0.4 | 922-dword graphics buffer and the ring after it |
| 514 | ring-order waits off | 18 | 42.6 / 0.0 | the same buffer's piece behind its full-state prefix (host-built, 1260 + 631 dwords) |
| 515 | pieces off | 18 | 46.4 / 0.0–0.5 | the 922-dword graphics buffer |
| 516 | as 515, dumped | 4 | 47.3 / 0.0–0.7 | the 922-dword graphics buffer |
| **517** | **reflection traversal skipped** | **0** | **46.5 / 24.7 → 31.4** | — |

- **The hung buffer (run 516, decoded with `bc5-agc dump`).** It is the first frame's work after
  New Game:
  - 4 direct and 3 indirect dispatches and 3 memory waits;
  - between the title's pass markers for its water simulation and its ray-traced reflections.
- **Neither ring-order waits nor graphics pieces cause the hang.** It persists without either.
- **The hang dump** (run 502) found no active waves; the dumper says that can also mean GFXOFF was
  on, so it decides nothing.
- **Run 517.**
  - The reflection traversal is dropped from the first frame on (4097+ dispatches).
  - The title loads and shows its start screen: the animated forest scene with the logo and
    "PRESS ✕ TO START", at 31 fps.
  - No GPU fault, no timeout, to the end of the 238 s run.

**Verdict.**
- The New Game hang is the ray-traced-reflection traversal (`0x11d049aa00`, F113–F116), which the
  first engine load runs.
- Skipping it reaches the start screen; the scene then lacks ray-traced reflections only.
- `BC5_DIRECT_SKIP_PGM=11d049aa00` can go into the play shortcut with the maintainer's yes, until
  the traversal's bad trees are understood (F116: suspect a multi-drawn character's instance record).
- Pressing ✕ there (the game proper) is untested.
