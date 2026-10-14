# 0079 — the second title with graphics pieces on (ADR 0008)

**Question.** Does the second title (the `.pkg`) run with the settings ASTRO BOT now plays with,
graphics pieces included (`BC5_DIRECT_PIECES_FULL=1`), without faults or hangs? Does it need
pieces at all?

**Setup.**
- Run 323, 2026-10-14 09:33, with the maintainer present. `run323.sh` uses the settings of the
  title's play shortcut (`play-pkg.sh`): HLE module pack, eager heap names, its own save
  directory.
- `bc5-run.env` is the same file as for ASTRO BOT. It sets ring order waits,
  `BC5_DIRECT_PIECES_FULL=1` and `BC5_DIRECT_PIECES_DRY=1`.
- Not set: `BC5_DIRECT_INDIRECT_DRAWS` and `BC5_DIRECT_ALIASES`, which hung the machine before
  (experiments 0056–0058).
- 180 s, full screen, no input. The root hang watcher was running. Kernel 7.2.8-ogc5.1.
- Raw: `raw/run323.txt` (the `piece:` lines, the 10-s reports, the frame profile of 100–175 s;
  labels masked).

**Result.**
- The run went the full 180 s. No GPU fault or timeout, and the hang watcher was silent.
- 4 pieces went to the GPU:
  - 3 at dword 758 of a 1,153-dword buffer;
  - 1 at dword 6,830 of an 11,440-dword buffer.

  The wait after the head was satisfied in 0.0–1.1 ms in all four.
- Waits not satisfied on arrival: 90–390 per 10 s. Ring order left 6–147 of them to the GPU, and
  the CPU served the rest. None was given up, and no cycle was broken.
- Frame rate 100–175 s: 24.7 fps, GPU busy 24.9 ms per frame, label waits 0.2 ms.
- At 120 s the title shows its first-start screen-reader dialog. The text is partly garbled, as
  F118 describes for runs without the multi-draw packets.
- The last run of this title (2026-10-13 08:14) had 18.1 fps at the same times. It ran with
  other settings and showed another screen (windowed, the udmabuf limit then at 64 MiB). The
  difference cannot be attributed to the pieces.

**Verdict.** Passed for its question:
- The second title runs with ASTRO BOT's settings, pieces on, without faults or hangs.
- It hardly needs the pieces. Its cross-queue waits are served or left to the GPU, none is
  given up, and the few splits resolved at once.
- The settings can stay shared between the two titles. This title's open problems lie
  elsewhere: the multi-draw packets and the reflection traversal, F113–F118.
