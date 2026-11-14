# A counted series that gives F403 and F813 a number (proposal, 2026-11-14; nothing run)

Asked by the top session after the five fix candidates of these classes lost their options (HANDOFF, the notes of
2026-11-14 at F403 and F813). The guardian's long walks already count GPU hangs; this turns them into a rate.

## What is counted so far (walks of the second title past G+320 on the scripted route, RT on)

| Build | Walks | GPU hangs | Source |
|---|---|---|---|
| F private 1a2900a0 | 12 (m5wall, sA, sB, sC, sE, dF1-3, dK1-2, dN1-2) | 1 (m5wall, 601 s, `gfx_0.0.0` timeout, no fault address, reset succeeded) | README sections 13 to 15 |
| the guardian's b413a916 (F with tl412, dc412, ph412) | 10 (n9F1-8, n10F1-2) | 0 | exp 0412 sections 91, 92 |
| shared B 51af1ed7 | 3 | 0 | section 15 |
| the night build f8cb77ad | counted apart: one hang at 03:25 with a failed reset, on a boot that had a GPU reset before | - | exp 0412 sections 85 to 87, LESSONS R55 |

One hang in 22 walks of the F family: about 3.8 hours of walk (10.3 minutes each), 0.26 hangs an hour, exact 95 %
interval 0.007 to 1.5 an hour. That agrees with F497 ("about once in 4 hours" of his play) and decides nothing. The
hang of m5wall was not assigned to F403 or to the draw that never ends: its packet at the CP's position was not
decoded.

## The series

- **Route and arm:** the long walk to G+620 as it is run today (the route the counts above come from), RT on, one
  build, one set of words for the whole series, the catchers that only log. No second route in the same count: the
  lake bench runs with RT reflections skipped and would be another population.
- **Size, fixed before the start:** 60 walks or 3 GPU hangs, whichever comes first. 60 walks are 10.3 hours of walk,
  about two nights at the night chain's pace (five walks an hour with the pauses). At 0.25 an hour that is 2.6
  expected hangs.
- **The STOP rule holds** (R55): a hang ends the night's chain. The count is therefore "hangs per hour of walk
  until the stop", summed over nights; a walk begun after a GPU reset on the same boot is not counted.
- **Each hang gets a class before it is counted**, from its fault record and devcoredump: F403 (CP stopped in the
  host's indirect-dispatch check, shaders busy in two SEs, no fault), the draw that never ends (GRBM 0xa2712028,
  stages 0x482030), or other. The packet at the CP's position is decoded this time; an undecoded hang is "other".
- **What comes out:** for each class a rate with its exact Poisson interval. Zero hangs of a class in 10.3 hours
  bounds it below 0.29 an hour (95 %); three hangs give 0.29 an hour with 0.06 to 0.85.
- **What it cannot give:** a verdict on the five removed words (none is in the build), a rate for his own play (the
  route is one path and no pad key is pressed), or a comparison of builds (one build only).

Cost: no new build and no slot of its own if the night walks already planned (slot 5 of today's order) are run to
this rule; the only additions are the fixed size, the class step and the summing.
