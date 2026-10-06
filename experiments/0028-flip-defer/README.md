# 0028 — The flip: does handing it to the completion thread give the frame anything?

**Question.** With jobs in flight the game's thread waited 2.2–3.7 ms at every flip for the frame's
jobs to finish before `sceVideoOutSubmitFlip` went to the presenter (HANDOFF F65). If the flip is
queued behind those jobs instead and submitted by the completion thread when they are done, does
the frame get shorter?

**Setup.** BC-250 dev box, 2026-10-06, as experiment 0026 run 125 (jobs in flight, the asynchronous
queue consumer, the frame profile), the maintainer at the controller from the saved game through
the second level. Run 126: the build of experiment 0027 (cached assembly, bisection lookup), flip
as before. Run 127: the same with `BC5_DIRECT_FLIP_DEFER=1`. Both ended early on the controller's
USB link (22 disconnects each); both have 4–6 minutes of the second level. Captures
`kytyplus-20261006-1929` and `-2013`.

**Result** (the second level, averages per minute).

| Per frame | Run 126, flip waited for | Run 127, flip deferred |
|---|---|---|
| frame | 20.7–23.7 ms | 22.1–22.8 ms |
| at the flip | 2.0–4.5 ms | 0 |
| game thread inside the host | 4.9–6.9 ms | 9.7–10.8 ms |
| of which `prepare` | 2.5–4.1 | 3.4–4.1 |
| of which the in-flight cap and label waits | ~0 | ~5 |
| outside the host | 12.3–13.4 ms | 11.9–12.4 ms |
| GPU busy | 14.8–18.3 ms | 17.6–18.6 ms |

The wait moved, it did not go away: the game's thread, no longer held at the flip, runs into the
cap of twelve jobs in flight and into its own CPU-side label waits for the same milliseconds. The
frame is the GPU's 17–18 ms plus the gaps in which the GPU has nothing queued, and the flip was
not what made those gaps.

**Verdict (2026-10-06).** No gain from deferring the flip by itself; `BC5_DIRECT_FLIP_DEFER` stays
opt-in. The flip is not the lever the profile made it look like. What the profile now says about
`prepare` (run 127, the parts timed inside the device): the policy filter is 2.4–3.1 ms of the
3.4–4.1, the tracker 0.5–0.6, the copy 0.3, the nested buffers 0.1 — against 0.06 ms for the same
filter over a 10,000-dword buffer offline (experiment 0027). Why the filter costs forty times more
in the game than on the bench is the next question.
