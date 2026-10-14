# 0085 — deferred flips with 3 jobs in flight: the dialog is right, menu glyphs still missing

**Question.** Undeferred flips fix the second title's text (experiment 0081), because the game
thread cannot get more than a frame ahead of the GPU. Do deferred flips with only 3 jobs in
flight (instead of 24) do the same?

**Setup.** Run 337 (`run337.sh`, 2026-10-14 15:11): run 327's settings, with
`BC5_DIRECT_MAX_IN_FLIGHT=3` (`bc5-run.env.pkg-inflight3`) and flips deferred.

**Result.**
- The dialog text is complete.
- The menu is drawn cleanly, but the same glyphs are missing in every string: n, g, m, I, v, r
  ("New a e", "Challe e Le el", "a e Calibratio"). The title "INITIAL SETUP" and the
  description are missing altogether. The button hints are there.
- 17.8 fps.

**Verdict.** Failed: fewer jobs in flight do not fix it, and they cost frames.

The pattern points to the font's glyph atlas:
- the glyphs are missing as a set, the same in every string;
- the dialog's glyphs come first and are there; the glyphs first needed by the menu are missing.

Hypothesis (TODO(verify)): the title rasterizes newly needed glyphs into a staging buffer, has
the GPU copy them into the atlas, and reuses the staging buffer once a fence passes that our
pipeline signals too early. The atlas then keeps blank glyphs for the rest of the run, which is
why one run looks the same throughout.

Next: find the copy into the atlas (a `DMA_DATA` or copy dispatch in the frames where the menu
appears) and what the title waits on before reusing its source.
