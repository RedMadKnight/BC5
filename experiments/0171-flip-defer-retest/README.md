# 0171 — Deferred flips for the second title, retried after the DMA snapshots: menu text intact, no frame gain, and an F208 hang

**Question.** With the submission chains (F224) and the BO-list fix (F225) the second title's frame
is 20.2 ms: 6.9 ms in the host, 4.8 ms waiting at the flip (the host drains the GPU before it
submits the flip; the console queues the flip behind the GPU work) and 8.5 ms in the title. The
deferred flip (`BC5_DIRECT_FLIP_DEFER`, exp 0025/0069/0070) was turned off for this title in
exp 0081 because it lost glyphs in the menus (F141–F145), before the DMA snapshots of exp 0122
(F172) removed one cause of that. Does deferring the flip now keep the text intact, and does it
give the frame the 4.8 ms back?

**Setup.**
- The launchers `play-pkg.sh` and `play-pkg-log.sh` unset `BC5_DIRECT_FLIP_DEFER` after reading
  `bc5-run.env` (which sets it for ASTRO BOT); run 823 (`route.sh 823 "BC5_DIRECT_CHAIN=2
  BC5_DIRECT_FLIP_DEFER=1"`) therefore ran without the deferral. Both launchers now keep it when
  `BC5_KEEP_FLIP_DEFER=1` (default unchanged; backups `*.bak-0171` on the box).
- Run 824: `route.sh 824 "BC5_DIRECT_CHAIN=2 BC5_KEEP_FLIP_DEFER=1" "96 104 140 170"` (the route
  runner now takes the screenshot times), against run 821 (chains, flip waited for, the same
  binary).

**Result.**
- Menu text: the slot list at +96 s and +104 s is complete (`run824-slot-menu.jpg`: SELECT SAVE
  SLOT, SAVED GAME 1, NEW GAME 2–6, EMPTY, the button hints) — no lost glyphs in this menu. The
  Initial Setup menu of F141–F145 is not on the route and was not checked.
- Frame (t 130–142 s, before the hang): 28.6 ms = 12.2 ms in the host + 0.0 at the flip + 16.5
  outside, against 821's 20.2 = 6.9 + 4.8 + 8.5. The wait moved from the flip into the host's label
  and cap waits, as F68 found in 2026-10 for the same title.
- At t ≈ 142 s the GPU timed out (two 2-s fence timeouts, GE2 page faults: F208), and the title
  drew nothing for the rest of the run. One run; F208 also strikes with the flip waited for, so
  the deferral is not shown to cause it.

**Verdict.** No: the deferred flip still gives this title no frame (F68 stands), and the one run
with it hit F208 early. It stays off for the second title; the launchers' `BC5_KEEP_FLIP_DEFER=1`
remains for experiments (F226).
