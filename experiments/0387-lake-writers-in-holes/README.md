# 0387 — The night lake's holes: which writer loses the cells

**Status: closed.** Planned on the laptop and run on 2026-10-31, one run, K7. Findings F770–F772. This is the follow-up exp 0385 named: read its README for the build, the ownership, the process marks, the gates and the
recovery, which carry over.

**Question.** F720 and F721 say the holes are cells no writer drew, and that the CP does not skip those writers by a condition. Exp 0385's catcher ran after K4's holes had ended (F722,
F723), so it could not say the next thing. While holes are present:
1. Which lake writer, by pixel shader and order, passes fewer samples in hole frames than in clean ones?
2. Does any candidate fix clear holes that are there on both sides of it?

This does not answer what decides the state (Q21). It names the draw to read next.

## What changes from exp 0385

| | Exp 0385 | Here | Why |
|---|---|---|---|
| Kernel gate | fault, timeout or reset lines | **any `amdgpu` line stops the run** | 28,256 `va conflict` lines passed it (F723) |
| Catcher's BO | 16 MiB, libdrm's low range | **128 MiB at a fixed 17 TiB**, above every scratch slot | The low range caused those lines; 2 minutes of every writer need the size |
| Catcher's window | Shots 17–20, after the poller | **Shots 0–23, from the first frozen frame** | K4's holes ended at shot 16 |
| Reader | Percentiles per writer | **Hole against clean, joined to the depth by the monotonic clock** | A final with no job within 40 ms stays unknown (LESSONS R11) |
| Arms | One after another, against the run's start | **All-off shots on both sides of each** | The state moves by itself (F722) |
| Arm order | Single fixes first | **All fixes together, twice, then each** | No arm hung in K4, and a null for the whole set saves reading the rest |
| `trackercf` | An arm | Left out; the switch stays | 0 CHAIN stops in K4 |
| Shots | 53 | **81** | Room for the all-off shots |
| Tags | K4–K6 | **K7, K8, K9** | Unique run tags |

Unchanged: one GPU job, one lock line with one token, private paths and binary, RT on with nothing skipped, the manifest, the journal bound to this emulator, the kept evidence on any failure, the
named lake snapshot `saves-lake-1153` reset into a private copy. The live saves are neither read nor gated. The private binary links the shared objects of 78f25172, so audio and patch 0001 are untouched.

One input differs from K4 and is not ours to pin: at 20:39:17 the maintainer's play appended line 110 to the shared `direct-learned-pkg.txt`, the region 0x110e000000+0x6000000, which the host now maps at the start of every run (the tb2 hang's note, its F687). K4 ran before that.
Each run here uses a private copy made at setup. `inputs.txt` holds that copy's sum and line count, `<tag>.saves.txt` the same after the run, `<tag>.journal.txt` the host's own count and path, and the shared file's sum stays a stop gate. A difference between K4 and K7 may come from this window.

## Rules, fixed before the runs

- **A run qualifies** with a mean patch of 20 % or more over shots 0–16, as before. The series ends at the first that does.
- **A writer loses cells** if, with 10 or more hole frames and 10 or more clean frames, its median share of the job's passed samples in hole frames is at most 0.8 of its share in clean frames, and its clean share is
  at least 0.001 (`zp0387.py`). A hole frame has a hole share of 0.05 or more, a clean frame under 0.01. With too few of either the reader says NO TEST, and the widest shares it still prints are a lead only.
- **An arm clears the holes** if the all-off shots on both sides have a median of 20 % or more, every one of its own shots is at 12 % or less, and its own host count moved (`gates0387.py arms`). Otherwise it is no effect, no
  verdict or NOT EFFECTIVE. A clearing arm is a lead that needs its own repeat, not a fix.

## Plan

**Runs.** At most three, K7, K8, K9, in order. Shots (`arms0387.txt`): 0–23 catcher; then all off and an arm by turns, 3 shots each: all fixes, all fixes, cache wbinv each, cull, pfp, dbmeta, idle, nohiz, cache all each; all off last.

| Step | Expected |
|---|---|
| Claim, kit, setup | ~1 min |
| Private build and its tests | ~1 min (exp 0385's) |
| One run: the view at ~200 s, 81 shots, analysis and clean-up | ~12 min |
| Release | ~0:30 |
| **Total** | **~15 min if K7 has holes, ~39 min for all three** |
| **Series deadline** | **60 min from the claim, recovery and release included** |

**Bounds.** Each emulator 680 s, each run 17 min, build 7 min. Records: a 128-MiB GTT BO and about 24 MiB of metadata in the host, both written to `~/bc5-data/priv/exp0387/<tag>` at shot 24 or when full, and deleted with the snapshots. Snapshots ~2.9 GB a run. No claim or run at 80 % disk, stop at 90 %.

**Stops.** As exp 0385, with any `amdgpu` line among them. A classifier refusal is reported once, not retried and not worked around.

**Commands.** Exp 0385's, in its order, from this directory, with `0387` for `0385`, K7 for K4 and `timeout -k 90 1140` on each run:
`git -C ../.. archive -o "$PWD/testbuild.tar" HEAD:backend ':!kytyplus-patches'`, `sha256sum testbuild.tar > tb.sha256`, then claim, scp, setup, build, kstream, run, copy, release.

**Rollback.** Discard branch `exp/0387-lake-writers`. On the box nothing shared changes, so `release` is enough.

**Tests.** Targeted, 15 of 15, on `test0387.py` with the same fixtures as exp 0385: the new gate, the arms' order and rule, the reader on synthetic frames, the end-to-end order. No full suite. See `raw/`. Module and wiring: `testbuild/`. Not reachable on this laptop, as in exp 0385: the real chain and all GPU packets. The BO's map at 17 TiB first runs on the box; if it fails, zpass is off and the log says so.

**Result.** One run, K7, on the maintainer's "Start 0387". Claim 22:32:32, run from 22:34:05, release 22:45:25, 13 of the 60 minutes. Claim, setup, build, run and release all rc 0. K7 qualified, so K8 and K9 were not used.

The run was valid. RT on, with 0 RT-off lines, 0 skip lines, 0 TIMEOUT lines and 17,539 flips. Manifest and gates PASS. Private binary db7119c1, shared pins held, sample 1bf54106 unchanged. Kernel: 0 `amdgpu` lines and 0 devcoredumps; the stream holds only IPv6 MLD lines. The catcher's BO mapped at 17 TiB, so the 28,256 `va conflict` lines of K4 are gone.

*Holes.* Present for the whole run. Shot 0 read 23.3 %, then every shot read between 31.2 and 43.0 %. Mean patch over shots 0–16: 37.1 %. The depth agrees: 195 finals, hole share median 0.353, p10 0.309, p90 0.394, range 0.205–0.428.

*Arms.* All nine have holes on both sides, and each one's host counts moved and read 0 in the all-off shots beside it. None clears anything.

| Arm | Own shots, % | Host counts in the arm |
|---|---|---|
| All off, 30 shots | 31.2–41.1, median 37.2 | 0 inserted words |
| All fixes, first | 35.0–38.6 | 798,718 words, 16,095 cull barriers, 5,666 HTILE fills |
| All fixes, second | 35.7–39.5 | 803,982 words, 16,206 cull barriers, 5,694 HTILE fills |
| `cache=wbinv`, each | 34.9–37.3 | 424,872 words |
| `cull=1` | 36.8–37.9 | 161,320 words, 16,132 cull barriers |
| `pfp=1` | 35.9–39.3 | 122,548 words |
| `dbmeta=1` | 39.0–41.0 | 68,472 words, 5,706 HTILE fills |
| `idle=1` | 38.9–40.9 | 7,036 words |
| `nohiz=1` | 34.7–38.6 | 21,036 words |
| `cache=all`, each | 38.4–40.6 | 422,968 words |

*CP.* Over shots 0–23: 494,606 zpass records in 16,185 jobs, 4,091 of them lake jobs, and 0 records with no begin. The census read 2,000 jobs and 60,954 lake writers: 0 inside a COND_EXEC, 0 predication, 0 nested IBs. The depth labels all those frames as holes, so this is the condition exp 0385 could not test. The reader does not print how many records have no end.

*Which writer.* NO TEST by the rule: 195 finals, 194 joined within 40 ms, 194 hole, 0 clean. Nothing here names a writer.

The `swing` rows are not leads, and this is a fault of the reader. Its key is the shader and the order in the job, and lake jobs come in three layouts: 3,806 jobs, 156 jobs with the shader's draws one place earlier, and 127 with them one place later. Shader 0x11d1dd6400 sits at orders 86, 88 and 90 in the main layout, and at 85, 87, 89 and 87, 89, 91 in the others, so orders 87 and 89 hold 283 jobs (156 + 127) from two different draws. The widest rows are that mix.

Rows with a p10 of 0 (0x11d4d3e800, 0x11d4d53100, 0x11d29e9c00) can't be read either: they may be the same mix or they may be real, and the records are deleted, as planned, so this can't be checked. Exp 0385's table shows two shaders close to those addresses swapping places between frames (0x11d4d3eb00, 0x11d4d53400).

*Learned file.* The private copy was in force: `BC5_DIRECT_LEARNED` in the manifest points at it, it held 110 lines with sum 5b92521f after the run, the same sum the shared file had at setup, and the shared file did not change. K4 saw a7cc8581. The third record, the host's own count, is empty: its line was in neither the journal nor the play log. K7's patch and depth hole share are both higher than K4's: 37.1 against 28.8 %, and a median of 0.353 against 0.281 over hole finals. One pair of runs can't say whether line 110's window has anything to do with that.

**Verdict.** Question 2 is answered for this one run: none of the nine arms clears holes that are there on both sides (F770). The CP runs the writers' records in hole frames (F771). Question 1 is not answered, because K7 has no clean frames (F772); Q21 stays open.

Limits. Three shots an arm, read from the shots' patch, not from the depth. Each arm ran on steady holes, so this says nothing about what starts or ends the state. `gfx1013`'s RB count and FORCE_HIZ/HIS stay TODO(verify).

A next catcher needs four changes, and none of them relies on clean frames arriving by luck: a key of shader plus occurrence within the job, the per-writer table kept in `raw/`, a share compared with the frame's hole share across the frames (K7's p10–p90 of 0.31–0.39 is the signal to use), and records sampled across the whole run so a spontaneous change of state falls inside them.
