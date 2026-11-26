# 0136 — The second title's opening after ✕ keeps its first shot: nothing loads, nothing is dropped; the skipped reflection traversal is the remaining suspect

**Question.**
- After New Game and ✕ on the animated start screen, the game should play its opening, with
  characters and camera moves.
- The maintainer sees the first shot of the start screen's forest without the logo instead. The
  sound and the subtitles go on as they should.
- What does the game wait for?

**Setup.**
- BC-250 dev box, 2026-10-16 14:36–15:03.
- **Session 1436:** the maintainer played with the play shortcut. The compute ring was on, the
  journal on, and the pad input recorded. ✕ was pressed at about 14:38:11.
  - Screenshots every 3 s for 80 s.
  - The emulator's and bc5-mount's read counters, read twice 5 s apart.
  - Stack samples of all threads (gdb, 6 samples).
- **Run 559:** scripted, New Game at 100 s, ✕ at 140 s, 230 s. The guest printf log was on (the
  emulator's HLE trace), to look for unimplemented or failing system calls after ✕.
- **Run 560:** as 559, but without `BC5_DIRECT_SKIP_PGM=11d049aa00`, which skips the
  ray-traced-reflection traversal. The maintainer was present and pressed ✕ twice himself.
- Raw: `raw/sessions-and-runs.txt`.

**Result.**
- **The game keeps drawing.**
  - Session 1436 renders about 42 fps after ✕, with no timeout.
  - No draw is dropped by the host: one `DROPPED` in the whole session, before ✕.
  - The picture is the start screen's first shot, without its logo, with the opening's subtitles.
- **Nothing is loading:**
  - the emulator reads about 1 MB/s;
  - bc5-mount reads nothing (everything cached).
- **Stack samples:**
  - the game's threads (`game-main`, five "File Video Stream" threads, Havok, job workers) wait
    on condition variables in the game's own code;
  - the render thread waits for the device lock in `submit_one`;
  - no thread is stuck in an HLE call.
- **Run 559, the HLE trace:**
  - no system function is called for the first time after ✕;
  - the call rates do not change at ✕;
  - the only recurring messages are "Equeue wait timedout: Loose Load EQueue" (a polling queue,
    from the start) and stubbed imports from the start of the run.
- **Run 560 (traversal not skipped):**
  - the GFX ring timed out twice after New Game (15:00:26, 15:00:41), as in experiment 0123;
  - the kernel reset that ring each time, and the machine stayed up;
  - the picture stayed black with sound; the maintainer pressed ✕ twice and closed the game.

**Verdict.**
- **The opening waits inside the game**, not on a host call, a load or a dropped draw.
- **The one known thing the host takes away there is the reflection traversal.** It is skipped
  since experiment 0123 because it hangs the GPU on bad trees (F113–F116). With it the GPU hangs at
  New Game, so whether the opening waits for it cannot be tested yet.
- **Next:** the traversal's bad trees (F116: the instance records of the characters drawn with
  multi-draw packets), or a way to let the traversal finish without hanging, e.g. a bound on its
  loop.
- **Also recorded (maintainer, F179):** in the options menu, the animation that breaks into the
  highlight bar and the text belongs in a preview at the bottom right, changing with the options.
  The preview's picture lands in the wrong place.
