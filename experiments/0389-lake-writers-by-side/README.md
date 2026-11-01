# 0389 — The night lake's holes: which writer differs between the two hole sets

**Status: ran 2026-11-01, Result and Verdict at the end.** The plan was written on the laptop on 2026-10-31 and 11-01, after exp 0387 and before any box access for this experiment, and stands as it was. This is the next step exp 0387 asked for (F772): read its README, and exp 0385's, for the build, the ownership, the process marks, the gates and the recovery, which carry over. Findings, if any, take numbers from F775 (the range F770–F789 the top session gave exp 0387).

**Question.** Exp 0387's K7 had holes in every frame, so its test of hole frames against clean frames could not run (F772). Clean frames can't be ordered: they come by themselves or not at all, and K4 can't stand in for them (F774). So every label here comes from the hole frames themselves, and clean frames are a bonus:
1. **Side against side.** A hole frame misses one of two fixed sets of pixels, X or Y, and which one is a coin per frame (F342, F485). Every hole run has both. Which writer passes fewer samples in one side's frames than in the other's?
2. **Against the hole share.** Finals' hole share runs from 0.31 to 0.39 (p10–p90, K7). Which writer's share falls as the frame's holes grow? This catches a writer that draws both sets, which the sides can't: X and Y are about the same size, so it loses as much either way.
3. **Hole against clean in one run,** if a run has both. The pad pushes the camera once inside the catcher's window, and the series goes on until a run has both or the tags run out.
4. **Against K4's clean table.** It reads only if a run's lake job has K4's writer count. K7's didn't, so expect NO TEST here.

Then: does an RB follow the side, that is, are X and Y the pixels of different RBs? Does the pad's push end the holes? Does any new candidate clear holes that are there on both sides of it?

None of this says what decides the coin (Q21).

**Before anything here is read as a defect: F773.** The maintainer saw K4 clean, where the shots read 28–32 % and the depth 0.166–0.322 for the first 83 s of the view. With RT on no check by eye of either measure was found, and every such shot was deleted unviewed. So this experiment reads the depth's holes, and a result says nothing about the picture until someone has compared the two. Each run keeps its three highest and three lowest shots, private, for the maintainer to look at (`~/bc5-data/priv/exp0389/evidence/shots-<tag>/`). Nobody else looks at them, and the rest are deleted unviewed as before.

## What changes from exp 0387

| | Exp 0387 | Here | Why |
|---|---|---|---|
| Labels | Hole against clean | **Side A against side B; each frame's hole share; hole against clean if a run has both** | K7 had 0 clean frames. Every hole run has both sides and a spread of hole shares |
| Frame | The lake job alone | **The frame's whole group of jobs** (K7: 1, 108, 3 and 9 writers), a key holding the job's place | The small jobs write the same depth, and exp 0387's reader left them out, so a writer there could never be named |
| The series | Ends at the first run with holes | **Ends at the first run with hole and clean frames to compare, else all three tags run** | K7 ended it with nothing to compare |
| Pad | None in the catcher | **One small push left and right at shot 8, in every run, inside the catcher** | K4's holes ended with nobody knowing why, and someone may have been at the pad (F773). K7 had no pad and held its holes for all 81 shots. The pad is free tonight |
| New candidates | — | **`binoff`, `smallprim`, `latez`, `nocompress`**, each forcing one register before every lake writer | No flush, barrier or HiZ change clears the holes (F770), and they are cells no writer drew (F486), so what is left to try is how the writers rasterise. All are hypotheses |
| New catcher | — | **The census prints each distinct set of 13 raster registers at a lake writer, with its shader** | Read-only. Includes binning, the small-primitive filter, the stages and the tessellation parameters, which nothing has listed for these draws |
| Arms | Nine | **Ten, in `arms0389.txt`:** everything twice, each new one, F770's set once more, the new four, the cache flush | The same 81 shots |
| Reader's key | Shader and order in the job | **Shader and its occurrence in the job** | Lake jobs come in three layouts that shift the order and mixed two draws in one row (F772) |
| Comparison | Medians | **Means** | A writer with two levels gives a median that flips on any small majority: the medians named it at every lag, in the reader's own test |
| Join | Nearest lake job | **Nearest, and each job up to 2 away; the lag naming the most writers is used** | 40 ms can't tell two neighbouring jobs apart at 33 ms a frame, and one frame off reads as a coin. At a wrong lag means name nobody (`a_writer_with_two_levels_is_not_named_at_a_wrong_lag`) |
| Records | Deleted with the snapshots | **Kept, private, in the evidence directory** | K7's reader fault could not be corrected afterwards (F772) |
| Per-writer data | The 25 widest rows | **Every writer's row, and a table of passed samples per job** (`<tag>.jobs.tsv.gz`) | Any later reader can start from it |
| RBs | Summed | **Per RB; the reader prints the RB count** | Closes that TODO(verify) |
| Tags | K7–K9 | **N1, N2, N3** | Unique run tags |

Exp 0387's README asked for records across the whole run, to catch the state changing. The sides, K4's table and the pad in the window take that place, so the window stays shots 0–23.

Unchanged: one GPU job, one lock line with one token, private paths and binary, RT on with nothing skipped, the manifest, the journal bound to this emulator, the named lake snapshot `saves-lake-1153` reset into a private copy, kept evidence on any failure, any `amdgpu` line stopping the run. Backend changes are only `lake_probe` and its tests, and its log lines still say "experiment 0387". The private binary links the shared objects of 78f25172, so audio and patch 0001 are untouched.

The four new switches are off unless the control file names them. Each writes a context register with an ordinary SET_CONTEXT_REG before a lake writer, as `nohiz` does, puts the title's value back before the next other draw or dispatch, and leaves alone a register the job never set. `binoff` also breaks the batch around the change. Registers and fields are `tools/bc5-agc/regdb/gfx10.json`'s. TODO(verify): whether a binning change needs more on this chip. No new candidate has run on hardware. If one hangs the GPU, the kernel gate stops the run and the series.

## Rules, fixed before the runs

- **The series** ends at the first run where the reader could compare 10 or more hole frames with 10 or more clean frames, or after N3. The old line "qualify" stays in the gates' output and no longer ends it.
- **A final's side:** its holes are sampled at the same 72 × 128 places of the lake window at every width. Finals with 5 % of holes or more split around two centroids by phi. A final is A or B with a phi of 0.5 or more to its own centroid and 0.1 or less to the other, `?` otherwise, and `?` is left out (LESSONS R11). A and B are named per run.
- **A writer follows the side** if, with 10 or more jobs of each side, its mean share of the job's passed samples in one side is at most 0.8 of the other's, the larger being 0.001 or more (`zp0389.py`).
- **A writer loses cells** by exp 0387's rule, on means, when there are 10 or more hole and clean frames.
- **Against K4:** over the main layout's writers from order 9 on, a writer holding at most 0.8 of its K4 share in this run's hole frames. It is another run and shaders are matched by order, so what this names is a lead, not a result. If the writer counts differ the reader says NO TEST, and K7's did (108 against 146, F774).
- **A writer follows the hole share** if, over 30 or more hole frames of the commonest width, the rank correlation of its share with the frame's hole share is −0.5 or less, its mean share being 0.001 or more.
- **An RB follows the side** by the same 0.8 on its share of the job's passed samples.
- **The lag** used is the one naming the most writers, a tie going to the lowest ratio. All five are printed. A writer named at one lag and no other, with a sharp ratio, is the expected picture. A writer named at several lags with a similar ratio is not a result.
- **The pad ends the holes** if the depth's finals go from a hole share of 0.05 or more before the push to under 0.01 within 10 s after it, in two runs of three. Once is a coincidence with K4's kind of ending, and K7 is the control with no push.
- **An arm clears the holes** by exp 0387's rule. A clearing arm is a lead that needs its own repeat, not a fix.

## Candidates, on paper, before the runs

K7's records are gone, so this comes from K4's table (`K4.zp.txt`, clean frames, maybe another view, F774) and K7's rows. Nothing here is a result.

**The size a cause must have.** The lake window holds about 796,000 pixels at width 2560. K7's median hole share of 0.353 is about 281,000 pixels a frame, K4's 0.281 about 224,000, and X and Y are 24–31 % each (F342). One sample a pixel, so a writer that alone explains a set must pass about 200,000 samples or more in a clean frame. Overdraw makes that a lower bound on what it passes, not an upper bound on what it loses.

| Candidate | K4's clean samples (p50) | What decides it |
|---|---|---|
| 0x11d1e2b900, the job's largest draw (K4 order 84) | 513,153 | Hole share; the side if it draws one set |
| 0x11d466bb00 (order 22) | 450,062 | The same |
| 0x11d1d10f00, two draws (orders 18, 15) | 389,939, 309,947 | The same |
| 0x11d018ab00 (order 145, in 184 of 366 frames) | 330,359 | The same, and whether it exists in the hole run |
| 0x11d1d88300, the one big draw (orders 114, 115, 122) | ~250,000 | The same. Its order moves in K4, the widest spread in the table |
| 0x11d373f100/f400, rows below order 9 | 702,639, 224,769, 218,373 | K4 can't say which job holds them; the frame groups can |
| 0x11d01ff900, op 0x27, rows below order 9 | 640,238, 609,622, 337,417 | A direct draw with no GPU-written arguments. If it follows, F350's argument path is out as the mechanism |
| Groups: 0x11d1d88300 ×13, 0x11d1dd6400 ×7, 0x11d29c9300 ×3 | 304,513, 290,514, 200,853 | Only together: several writers following at once |

**Out on paper, as the sole cause:**
- 0x11d4d3e800/eb00 and 0x11d4d53100/400, K7's rows with a p10 of 0: 84,387 and 32,221 samples, 116,608 together, short of the 200,000 a set needs. They can still follow as part of something larger.
- 0x11d29e9c00/f00: 172,500 over 36 draws, under the bound, and the one writer already shown the same in both states within a run (F320).
- K7's widest `swing` rows: the mix of layouts (F772).

Shader addresses in the +0x300 pairs above are a run property (F318, F320), not a state, so a shader is matched across runs only through that known shift.

## How the result will be read

Fixed before the runs. H is a side's mean hole pixels a frame: its hole share times the window's pixels at its width. Lost samples come from `<tag>.jobs.tsv.gz`, the difference in mean passed samples at one width.

| Outcome | Reading | Next |
|---|---|---|
| **Named:** writers follow a side or the hole share, and their lost samples reach at least H / 2 | Those draws' cells are the holes | Read those draws: their arguments, constants and culling input |
| **Part:** writers follow, but lose under H / 2 | They go with the holes and don't make them all | Read them, and say that it is part |
| **Many:** the frame's total falls with the holes, but no writer follows | Many draws lose a little | Look at what they share, not at a draw |
| **RB:** an RB follows the side | X and Y are a raster or RB ownership pattern | Read the screen's mapping to RBs against X and Y |
| **Null:** nothing follows, and the frame's total does not fall with the holes by H / 2 | Depth zeros without lost samples: this contradicts "no writer drew" (F486) | Reopen F486 before any more writer work |
| **No test:** under 10 frames of a side and under 30 of one width, or the sides mostly `?` | No statement about any writer | A new label from the private records |

A writer named at one lag only, with a sharp ratio, counts. Writers named at several lags with similar numbers don't. Passing the bound isn't proof of cause, and an arm that clears holes needs its own repeat. All of this is about the depth until someone has compared it with the picture (F773).

## Plan

**Runs.** N1, N2, N3, in order, each as K7: shots 0–23 catcher with the push at shot 8, then all off and an arm by turns.

| Step | Expected |
|---|---|
| Claim, kit, setup | ~1 min |
| Private build and its tests | ~1 min (K7's) |
| One run: the view at ~200 s, 81 shots, analysis and clean-up | ~12 min |
| Release | ~0:30 |
| **Total** | **~15 min if N1 has both kinds of frame, ~39 min for all three** |
| **Series deadline** | **60 min from the claim, recovery and release included** |

**Bounds.** As exp 0387. Each emulator 680 s, each run 17 min, build 7 min. New: ~150 MB of records and six shots stay per run in the private evidence directory, and go by the standing cleanup once the maintainer has seen the shots. Snapshots ~2.9 GB a run, deleted unviewed. No claim or run at 80 % disk, stop at 90 %.

**Stops.** As exp 0387. A classifier refusal is reported once, not retried and not worked around.

**Commands.** Exp 0387's, in its order, from this directory, with `0389` for `0387`, N1 for K7, `K4.zp.txt` added to the scp list, and K7's `timeout -k 90 1140` on each run:
`git -C ../.. archive -o "$PWD/testbuild.tar" HEAD:backend ':!kytyplus-patches'`, `sha256sum testbuild.tar > tb.sha256`, `sha256sum -c --quiet kit.sha256`, then claim, scp, setup, build, kstream, run, copy, release. Records are read again only on the box.

**Rollback.** Discard this experiment's commits. On the box nothing shared changes, so `release` is enough, plus the private evidence files if wanted.

**Tests.** `test0389.py` on the laptop (`raw/test0389-full.txt`), the module's 19 cases under ASan (`raw/lake-module.txt`) and exp 0387's `check_wiring.py`, whose `direct.cpp` lines did not change. On the way the tests caught three faults: `own_rm` still knew only K tags, the medians named a two-level writer at every lag, and `keep_shots` read a variable in the `local` line that set it.

Not reachable on this laptop: the real chain, all GPU packets, the new registers on hardware, what the push does in Photo Mode, and the sides on real depth. No real depth from K7 survives, so the selftest's planted sets stand in for them. If real finals don't split cleanly, the sides read `?`, that footing says NO TEST, the hole share still reads, and the private records stay for a new label.

**Result.** 2026-11-01, RT on, shared build 78f25172 untouched, private binary 33ba1948. The tool refused the claim at 00:58, 03:27 and 06:11, and each refusal was reported once and not retried. It passed at 06:13:45, on the maintainer's own "zgoda" in this session. Two runs, then release at 06:38:25, 25 minutes after the claim. N3 did not run: N2 had both kinds of frame, so the state read done, as planned.

| | N1 | N2 |
|---|---|---|
| Gates | PASS | PASS |
| Flips | 17,478 | 17,261 |
| RT-off, skip, TIMEOUT lines | 0 | 0 |
| amdgpu lines in the journal and the stream, devcoredumps | 0, 0 | 0, 0 |
| Mean patch | 31.9 % | 16.7 % |
| Zpass records | 506,171 | 524,288, the buffer's size |
| Jobs, lake jobs, skipped by the CP | 15,825, 3,989, 0 | 15,076, 3,827, 0 |
| Finals, joined | 196, 196 | 199, 199 |
| Hole, clean finals | 196, 0 | 94, 71 |
| Sides A, B, `?` | 49, 41, 106 | 51, 42, 0, and 106 with too few holes |

*By the plan's table:*

- **Sides: nothing.** N1 flags 5 of 51 writers, N2 8 of 54. Those under 0.6 are the small job at an unusual place in a few frames, with means of about 0.002. N1's other two, 0x11d0203f00.0 at 0.674 and occurrence 10 of the 0x11d373f.. shader at 0.736, read 0.944 and 0.968 in N2. No writer follows a side in both runs.
- **RBs: nothing in the aggregates.** 0 of 16 in both runs. That is each RB's share of the whole frame, so it doesn't exclude a spatial RB pattern.
- **K4's clean table: NO TEST,** as expected: 113 and 125 writers against 146.
- **Hole against clean and the hole share, N2: the bound of Named is passed, one rule is not met, so this is no qualified pass of the plan.** It is one run and exploratory. PS 0x11d01ff900 in the small job after the lake job: occurrence 2 reads 0.789 with rank -0.80, occurrence 0 reads 0.854 with -0.457. Between 71 clean and 90 hole finals at 2560 wide the two lose 175,005 samples a frame. H is 115,307 hole pixels, H / 2 is 57,654, so the bound is passed. The frame total loses 171,752, which rules out the table's Null.
- **The rule not met:** the plan doesn't count writers named at several lags with similar numbers, and these are named at all five. That rule was written for a coin per frame. N2's hole share changes over seconds, so all five lags see the same value. Deviations from each capture's own mean show no relation at any lag in either run (|r| at most 0.08 in N2, 0.25 in N1). So the frame-to-frame test neither supports nor refutes this.

*Read after the runs, not in the plan* (`after0389.py`, `raw/after0389.txt`), in the 179 finals where the small job sits once at place 2, so that a frame group holding two of them or none can't pass as a change of a draw:

- Over N2's 34 captures the shader's four draws fall 1.44 samples per hole pixel, r -0.96; the frame total falls 1.37, r -0.95. So the sum of the rest stays flat, which doesn't exclude single draws offsetting each other. Per frame, occurrence 0 has rank -0.93 and occurrence 2 -0.97.
- Occurrence 1 stays at 631,000 on average, and the capture table reads 632,3xx through most of the run while the others fall.
- Occurrence 2 falls in steps. Per frame it sits at about 340–350k, 320–330k, 290–310k, 260k, 230–240k and 180–200k, with empty bins between.
- In N1 the hole share stays near 0.30 in all 34 captures, and the same draws go with the pattern instead. The 77 frames that match side A or B have occurrence 0 at 620–655k and occurrence 1 at 238–257k. The 87 frames that match neither have 429k and 338k, at the same hole pixels. These labels run in stretches of captures.

*Depth, the metric and time:*

- In N2's 14 shots with captures beside them the metric follows the depth, r +0.97: 9–10 % at hole share 0, about 30 % at 0.2. In this run the colour metric and the depth are one reading.
- N2's depth reads 0.000 in ten captures in a row, about 25 s, grows to 0.225 in about 40 s, falls to 0.000 in about 15 s and rises again. Its metric stays near 30 % from shot 21 to the end.
- N1's metric reads about 32 % to shot 41, 9 % over shots 43–74, about 160 s, and about 30 % from shot 75 on. No depth was captured in that stretch.

*Arms and the push:*

- **All arms in N2: no effect, with holes on both sides.** That is `binoff`, `smallprim`, `latez`, `nocompress`, those four together, F770's set, all together twice, and `cache=wbinv`. They were in force: 190,000 to 1.66 million words inserted an arm, 0 refused, 0 words in the all-off periods.
- **N1's clean stretch is not an arm effect.** It began one shot after `binoff` and ended on the first shot of `cache=wbinv`, but the same arms did nothing in N2. N1's arms 39–75 have no verdict, since holes didn't sit on both sides of them.
- **The push moved nothing readable.** N1's holes held across it, and N2's frame total and occurrence 1 read the same before and after. N2's holes came back 14 s later, which one run can't tie to it.

*Not shown:* that their lost samples are the holes' pixels, since only counts were compared; why they lose. That this shader is the water was shown before, by F261, which this write-up first missed. The loss per hole pixel, 1.4 in N2, would fit holes reaching past the window, which is 800,128 of about 3.7 million pixels, but that was not measured. N1's four draws read 1.0–1.2 million against N2's clean 1.7 million at about 240,000 hole pixels, a loss about twice as steep per pixel, and it's another run. Nobody has yet compared any of this with the picture.

*For the eye check,* the script keeps six shots a run in `~/bc5-data/priv/exp0389/evidence/` (`shots-N1`, `shots-N2`): N1 `062346-ts60`, `062236-ts46`, `062251-ts49` read lowest, `062035-ts22`, `062505-ts76`, `062019-ts19` highest; N2 `063046-ts07`, `063059-ts09`, `063040-ts06` lowest, `063604-ts68`, `063658-ts79`, `063648-ts77` highest. The directory was not listed after the release, and I viewed none of them.

**Verdict.** Two correlated draws of the water, in one run. In N2, the only run with both kinds of frame, occurrences 0 and 2 of PS 0x11d01ff900 in the small job after the lake job lose samples as the holes grow, past the plan's bound and in steps, while the sum of the rest of the frame stays flat (F775, F776). This is exploratory and no qualified pass of the plan: the lag rule was not met, the reading in 179 finals was made after the run, it isn't shown that those samples are the holes' pixels, and a flat sum doesn't exclude draws offsetting each other. The colour metric and the depth agree with RT on, and clean stretches come and go by themselves inside a run, so a clean run shows nothing about a fix (F777). No arm moved the holes (F778). What decides the state stays open (Q21). Next, by the plan's table: read those draws, their arguments, constants and culling input, in a run with both kinds of frame, and the eye check of the six shots.
