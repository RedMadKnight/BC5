# 0088 — the second title's black menu background: not the draw checks, not the aliases

**Question.** The maintainer: the menu's background should not be black, and an animated scene
shows through the highlighted item. Is the full-screen background pass skipped by the CP's
indirect-draw checks (at most 2^20 vertices and 64 instances since experiment 0057), or does it
depend on the code aliases (experiment 0056)? Run 241, which had neither, showed the forest
behind the first dialog (F118).

**Setup.**
- KytyPlus patch: `BC5_DIRECT_DRAW_MAX=<vertices>:<instances>` overrides the two limits.
- Both runs use the play shortcut's settings: undeferred flips, `multi`, a fresh save, cross at
  80 s, then menu navigation (`input340.cmd`).
  - Run 344 (2026-10-14 17:54): with aliases, limits 4,194,304:4,096.
  - Run 345 (17:57): limits as before, without aliases.

**Result.**
- The background is black in both runs. 18.5 and 18.7 fps, no faults or timeouts.
- In both, the highlighted item's bar shows no scene. In earlier runs with deferred flips the
  bar showed a forest image.
- Run 345 again shows the description's text with missing letters, now with undeferred flips:
  the scrolling race the maintainer saw (F147).
- `SET_PREDICATION` is not used by the title: it is not among the filter's drops (run 328), and
  `COND_EXEC` passes.

**Verdict.** Failed for its question: neither the draw limits nor the aliases cause the black
background. The knob stays (default unchanged).

Without a frame capture, the next step is a per-draw journal for one menu frame:
- render-target base and size, viewport, pixel-shader address, vertex and instance counts,
  through the full-state tracker;
- then check whether a full-screen pass that samples the scene's render target exists at all,
  and what it writes.
