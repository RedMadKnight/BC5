# 0081 — which asynchronous setting loses the second title's letters

**Question.** Experiment 0080 showed that the second title's text is complete only with
synchronous submission. Four settings were off there: `BC5_DIRECT_ASYNC`,
`BC5_DIRECT_RING_ASYNC`, `BC5_DIRECT_FLIP_DEFER` and `BC5_DIRECT_MAX_IN_FLIGHT=24`. Which of them
causes the race?

**Setup.**
- Run 333, 2026-10-14 11:01 (`run333.sh`): run 332's setup with the play settings minus
  `BC5_DIRECT_FLIP_DEFER` only (`bc5-run.env.pkg-noflipdefer`).
- Asynchronous submission, the ring thread and 24 jobs in flight stay on.
- `multi` + aliases, heavy probe off, one cross at 80 s. Screenshots, private.
- Indicator: the screen-reader dialog's text. With asynchronous submission and the heavy probe
  off it was broken in 3 of 3 runs (323, 327, 329).

**Result.**
- The dialog text is complete.
- The Initial setup menu is complete: title, items, description, icon, button hints. Only the
  ◀▶ arrows next to two values are missing from that screenshot; they were drawn in run 332.
- Menu frame rate (95–125 s, `raw/run333-fps.txt`): 19.2 fps, GPU busy 28.8 ms per frame, game
  thread in the host 16.6 ms. For comparison: run 332, synchronous, 23.3 fps; asynchronous with
  deferred flips, 24.6–25.3 fps.

**Verdict.** Passed for its question:
- The race is the deferred flip (`BC5_DIRECT_FLIP_DEFER`, experiment 0069's flip after the frame
  jobs). With the flip deferred, the title learns its frame is done before the GPU has drawn
  from the text data, and rewrites the data.
- ASTRO BOT keeps the setting: it waits on the display buffer's label, which experiments 0069 and
  0070 handle.
- The second title needs its flips undeferred, or the deferred flip has to hold back the
  completion this title waits on. TODO(verify) which completion that is (flip event, flip status
  or EOP label).
- One run only. The frame rate without the deferral is lower than fully synchronous, which is
  not yet understood.
