# 0392 — The night lake's holes: at which stage the water's cells go, and whether the TF ring's handling is why

**Status: ran 2026-11-01, Result and Verdict at the end.** The plan was written on the laptop on 2026-11-01, after exp 0389 and before any box access for this experiment, and stands as it was. Number: 0390 and 0391 are taken on their branches and nothing here or in a worktree has 0392; `claim` refuses if `~/bc5-work/exp0392` exists.

**Question.** In N2, one run read partly after it, occurrences 0 and 2 of PS 0x11d01ff900, two of the water's four draws, lost samples as the holes grew, in steps (F775, F776). That those samples are the holes' pixels is not shown, and the flat sum of the rest doesn't exclude draws offsetting each other. So: does this repeat, and in frames where those draws lose samples, at which stage of the pipeline do they go? And does the way the host handles the tessellation rings change it?

## What this rests on

- **The draws are the water's.** PS 0x11d01ff900 is four `DRAW_INDEX_2` of 256 indices, ES 0x11d0148800, and dropping it leaves the flat surface the patches show (F261). F775 said this wasn't shown, which was wrong.
- **The draws are tessellated.** N2's raster line for this shader has `VGT_SHADER_STAGES_EN` 0x200210d (LS, HS, ES, `DYNAMIC_HS`, `PRIMGEN_EN`) and `VGT_TF_PARAM` 0x4004e (quads), the same two values as F248's tessellated draws. No earlier finding on the holes looked at this. With F248's `VGT_LS_HS_CONFIG` 0x1043f a patch has 4 control points, so 256 indices would be 64 patches. TODO(verify): this exp records the water's own value.
- **Loss in steps would fit patches.** F776's levels, and cells "in perspective" (F309), would fit whole patches going missing, though that is not shown. A patch goes if its tessellation factors are 0, and that needs no change in the draw, which fits F313, F320 and F323.
- **The host rewrites the ring in every job.** `tf_ring_prefix` (patch 0001) writes `VGT_TF_RING_SIZE` and `VGT_TF_MEMORY_BASE(_HI)` in the prefix of every buffer that draws, with `VS_PARTIAL_FLUSH` and `VGT_FLUSH` before the first one only. RADV does both before it sets ring registers (Mesa ab2374a `radv_queue.c:1048-1052`). So those writes land while the job before may still have patches in the pipeline. Whether a write of the same value disturbs anything is not known.
- **`VGT_HS_OFFCHIP_PARAM` is left alone.** With the title's `/dev/gc` ring the host doesn't write it, so the chip holds whatever it holds (F248: 0x1ff, 0x5f and the GPU's own behaved alike, but that was about a stall, not about holes).

None of this says what decides the state (Q21). It says where to look.

## What changes from exp 0389

Kit: 0389's with the tags T1–T3. The reader is new (`zp0392.py`), with `cs0392.py` and `tf0392.py`. Backend: `lake_probe` only. `direct.cpp` and the host don't change, so the private build is again a relink. Log lines still say "experiment 0387".

**Labels need no depth now.** The water's own samples label every frame of a run: S is occurrences 0 and 2, TOP its 95th percentile, clean at 0.97 of TOP or more, hole at 0.90 or less. The depth snapshots stay as they were, for the join to S and because N2's result needs a repeat.

**The catchers run all through,** on the water's draws only, so 128 MiB lasts the run, and each arm can be read frame by frame. They write the records when the last arm turns them off, at shot 78.

| Switch | What it reads |
|---|---|
| `zwater=1` | `zpass` wraps only 0x11d01ff900, 0x11d0203f00 and 0x11d0208400 |
| `stats=1` | `SAMPLE_PIPELINESTAT` around each of those draws, as RADV takes it (`radv_query.c:141`, `ac_barrier.c:42-52`): IA, HS, DS, VS, GS, clipper, PS. TODO(verify): which of them count on an NGG tessellation pipeline of this chip |
| `ureg=1` | `COPY_DATA` of the ring's registers, `GE_CNTL` and `GE_PC_ALLOC` at the job's first water draw: what the chip holds, each frame |
| `inputs=1` | the draw packet, its registers, the user data of HS, GS and PS, and the constants behind user data 28–29 (F293), to a private file. F293 had 26 usable samples; this has every frame |

**The poller** also reads the whole TF ring at each sF, read-only. `tf0392.py` prints shares of zero, low, one and high factors, and the raw rings stay private.

## Candidates

All in one build, each behind its own switch, as the rule asks. All are hypotheses.

| Switch | What it does | Why |
|---|---|---|
| `tailflush=1` | `VS_PARTIAL_FLUSH` and `VGT_FLUSH` at the end of each job that draws | The pipeline is empty when the next prefix writes the ring |
| `tfonce=1` | the prefix's ring writes become NOPs once one has gone through | No writes at all, so no question of when they land |
| `tfdist=0`, `tfdist=3` | `VGT_TF_PARAM.DISTRIBUTION_MODE` at the water's draws (the title has 2, DONUTS; 0 is none, 3 trapezoids) | X and Y as what two shader engines do with the patches: a lead, not a finding |
| `gepc=1` | `GE_PC_ALLOC` 0x1ff at the job's first water draw | The title writes 0; RADV's value for NGG on this chip (F248) |
| `offchip=<hex>` | `VGT_HS_OFFCHIP_PARAM`, after the two flushes, before the job's first draw | It is the one ring register nobody sets here |

`offchip` can't be put back to an unknown value, so its arms come last in each run: 0x1ff, the title's own, then 0x5f, RADV's on this chip, then 0x1ff. `ureg` shows what the chip held before them.

**Arms.** Shots 0–23 catchers only, 24–26 off, then seven arms of three shots with three off shots after each: `tailflush`, `tfonce`, both, `tfdist=0`, `tfdist=3`, `gepc`, and those together with `tfdist=0`. Then the three `offchip` shots groups, and at 78 all off.

**Each run has its own order** (`arms-T1.txt`, `-T2`, `-T3`). N1 taught this: a clean stretch began beside one arm and ended on another, and only N2's same arms showed that it wasn't them (F778).

## Rules, fixed before the runs

As exp 0389's, in full: its RT on, its saves, its pins (normal 78f25172, launcher 55531ab6, `bc5-run.env` cb8ad5fc, lake sample 1bf54106), its gates, watchdog and stops, its atomic lock. Shots and snapshots stay unviewed by me and go, except the six a run for the maintainer. Records, inputs and rings stay private in `~/bc5-data/priv/exp0392/evidence/`, and only numbers and places leave the box: `cs0392.py` prints no value.

Every tag runs: there's no early end now, because each order is its own test.

## How the result will be read

Fixed before the runs. For occurrences 0 and 2, in clean and hole frames of one run, in pipeline order:

| First count to fall by 5 % or more | Reading | Next |
|---|---|---|
| IA or HS | The patches never start: the draw itself differs | Read the draw's arguments (`inputs`), which contradicts F313-style sameness |
| DS | Patches start and tessellate to nothing: the factors | The ring and what HS reads |
| VS or GS | Between tessellation and the geometry stage's output | The ES's inputs |
| Clipper counts | Geometry goes out and is culled or clipped: positions | The ES's inputs: its textures and the offchip data |
| PS | Rasterised to nothing | Raster state |
| None, and the samples fall | The depth test takes them | HiZ and HTILE again, against F770 and F486 |
| No test: under 10 clean or under 10 hole frames | Nothing about the stage | The next tag |

The counters' own TODO comes first: a stage whose counter reads the same in every frame or 0 says nothing, and the reading says so.

**An arm clears** if S returns to clean in that arm's frames with hole frames on both sides of it, in at least two of the three runs, at different times. One run is a lead. The colour metric's table (`gates0392.py arms`) is read beside it.

**`ureg`:** a register whose value differs between clean and hole frames is the result itself.

**`inputs`:** a position that separates hole from clean frames is a lead to read on the box; none separating closes F293's question with thousands of frames.

**The ring:** if the share of zero factors follows the holes, DS falls for that reason. The ring is read after the frame's later draws too, so no change there says little.

Passing any of this isn't proof of cause. All of it is about the counts until someone has compared them with the picture (F773, F777).

## Plan

**Runs.** T1, T2, T3, in order, each as N1.

| Step | Expected |
|---|---|
| Claim, kit, setup | ~1 min |
| Private build and its tests | ~1 min |
| One run: the view at ~200 s, 81 shots, analysis and clean-up | ~12 min |
| Release | ~0:30 |
| **Total** | **~39 min** |
| **Series deadline** | **60 min from the claim, recovery and release included** |

**Bounds.** As exp 0389. Each emulator 680 s, each run 17 min, build 7 min. New: records ~60 MB, inputs up to 64 MiB and rings ~50 MB a run stay private until the standing cleanup. Snapshots ~2.9 GB a run, deleted unviewed. No claim or run at 80 % disk, stop at 90 %.

**Stops.** As exp 0389. The first amdgpu kernel line stops the run. New on this path, so watch them: `SAMPLE_PIPELINESTAT`, `COPY_DATA` of GE registers, `VGT_TF_PARAM` forced mid-job, uconfig writes between jobs, and turning the ring's writes off. A tool refusal is reported once, not retried and not worked around.

**Commands.** Exp 0389's, in its order, from this directory, with `0392` for `0389` and T1 for N1:
`git -C ../.. archive -o "$PWD/testbuild.tar" HEAD:backend ':!kytyplus-patches'`, `sha256sum testbuild.tar > tb.sha256`, `sha256sum -c --quiet kit.sha256`, then claim, scp, setup, build, kstream, run, copy, release. The scp list: `box0392.sh gates0392.py pl0392.py sn0392.py tz0392.py bt0362.sh patch0392.py swz0248-z4.json input-0392.cfg arms-T1.txt arms-T2.txt arms-T3.txt relink0392.py zp0392.py cs0392.py tf0392.py kit.sha256 testbuild.tar tb.sha256`.

**Rollback.** Discard this experiment's commits. On the box nothing shared changes, so `release` is enough, plus the private evidence files if wanted.

**Tests.** `test0392.py` on the laptop (`raw/test0392-full.txt`), the module's cases under ASan (`raw/lake-module.txt`) and exp 0387's `check_wiring.py`.

Not reachable on this laptop: all GPU packets, what the counters read on an NGG tessellation pipeline, `/proc/PID/mem` reads of the ring, and whether a job's tail runs where the tests assume in the real chain.

**Result.** 2026-11-01, RT on, shared build 78f25172 untouched, private binary a46b46b2. The tool refused the claim at 09:45, which was reported once and not retried. It passed at 10:08:38 on the top session's GO. Three runs, release at 10:44:44. Read at setup: swappiness 150, page-cluster 0, the top session's temporary settings (before them 60 and 3), set at about 08:00, after N1 and N2.

| | T1 | T2 | T3 |
|---|---|---|---|
| Gates | PASS | PASS | PASS |
| Flips | 17,363 | 16,999 | 17,395 |
| RT-off, skip, TIMEOUT lines | 0 | 0 | 0 |
| amdgpu lines in the journal and the stream, devcoredumps | 0, 0 | 0, 0 | 0, 0 |
| Mean patch, first 17 shots | 9.4 % | 9.8 % | 13.4 % |
| Finals, their hole share | 155, 0.000 | 78, 0.000 | 97, 0.000 |
| Frames with the water's records | 11,789 | 11,826 | 11,783 |
| Lowest S against its size's top | 0.986 | 0.987 | 0.999 |
| Records | 223,991 | 224,694 | 223,877 |

**All three runs were clean, so the plan's table reads No test in each.** No frame in 35,398 is a hole frame, no final has a hole, and no shot read above 13.6 %. Every arm reads "no verdict: no holes beside it", and that is the whole answer to the candidates: this series says nothing about them, except that none of them cost the water a sample or brought a fault. `tfonce` stripped about 6,200 ring writes an arm.

**The first reader was wrong, and the second one was written during the series.** `zp0392.py` called frames at a smaller render size hole frames, because S scales with the size (980k, 780k and 620k at the three sizes of T1), and it refused every stats record over a bit 63 they don't carry. `zp0392b.py` takes each frame's top among frames of its own size and reads the stats. It ran on the private records on the box before the release, and its tests pass on the laptop. `T?.zp.txt` and `T?.frames.tsv.gz` are the wrong reading, kept as what ran. `T?.zp2.txt` and `T?.frames2.tsv.gz` are the reading to use. `T?.cs.txt` compares the same wrong labels, so its twelve "separating" positions are the render size and it has no result. That those positions are the size is what gave the fix.

**The catchers do work on this chip,** which the plan could not test. Occurrence 0 of a T1 frame: IA_VERT 15,104, IA_PRIM 3,776, HS 3,776, DS 37,811, VS 15,104, GS and C_INV 33,134, C_PRIM 27,660, PS 642,102. GS_PRIM and CS never move. IA_VERT is 4 × IA_PRIM, and 3,776 is 59 × 64, so these fit quad patches, 64 a draw at 59 instances. The instance count itself was not read.

**Registers, from `ureg`, every frame.** `VGT_TF_RING_SIZE` 0xfffe and `VGT_TF_MEMORY_BASE` 0x11200000, as the host writes them. `GE_CNTL` 0x8040. `GE_PC_ALLOC` 0, and 0x1ff in `gepc` arms. `VGT_HS_OFFCHIP_PARAM` read **0** until T1's first `offchip` arm, though the title asked for 0x1ff (F248).

**The ring,** at every sF: zero share 0.0000–0.0001, 5.5–5.8 % of the words under 1, the rest over 1. No run with holes has been read, so this is only a reference.

**Against the metric.** T3's shots read a steady 13.4 % with no hole in any final, and its top S at the size of T1's is 1,143,261 against 983,782. So that run's view showed more water, and 9–10 % is not the floor of every view, which qualifies F777. K4's steady 17.1 % may be of this kind; that wasn't tested.

**Why they were clean is not known.** Earlier rates gave 13 clean of 78 runs (F418), so three in a row is unlikely by chance, about 0.5 % if runs are independent. N1, N2 and T1–T3 share one boot (d9cca008). Their emulator options, launcher edits, input configuration, save sample and pins are the same. Four things differ:

1. **The catchers: open.** `stats`, `ureg` and `inputs` ran from shot 0 and `zpass` wrapped only the water, where N1 and N2 wrapped every writer. They were never off, so no off shot here is really off.
2. **The memory settings: open.** Swappiness 150 and page-cluster 0.
3. **The learned file: open, and found only in this comparison.** N1 and N2 ran with 110 lines (5b92521f), T1–T3 with 112 (23ef45ec). The shared file changed between N1's setup at 06:14 and T1's at 10:08. I haven't read what the two new lines cover. These are regions the host learned from GPU faults, so if the water reads such a region, a change there could change what it reads. That is a lead, not shown.
4. **`VGT_HS_OFFCHIP_PARAM`: not why T1 was clean.** T1's register read 0 for its first 357 s, 10,455 frames and shots 0–68, and those were already clean: no hole frame, S at 0.986 of top or more, shots 9.1–9.6 %, the 155 finals at 0.000. T2 and T3 were clean at 0x1ff. N1 and N2 didn't read it. They ran before the three ring resets of 07:22, 07:41 and 07:54, which the top session listed after this was written, so what they held is unknown.

**Left on the box:** `VGT_HS_OFFCHIP_PARAM` stayed at 0x1ff after T1, so T2 and T3 began there, and it holds until a reboot or GPU reset, across all sessions' runs. The plan said a run's `release` is enough and that nothing shared changes; for this register that was wrong. The top session has been told.

*For the eye check,* six shots a run are in `~/bc5-data/priv/exp0392/evidence/` (`shots-T1`, `-T2`, `-T3`). I viewed none of them. All are clean by depth, so they're a clean reference, T3's most of all.

**Verdict.** No test. Three runs came out clean with the catchers on, so the stage, the ring's handling and the arms are all unanswered, and the new catchers are shown to read on this chip (F779, F780). The register doesn't explain T1. The catchers, the memory settings and the learned file stay open.

**The smallest test that separates them** needs no reboot and no code, only a run of this kit with another arm file and another private learned copy:

| Run | Learned | Catchers | Memory | If holes | If clean |
|---|---|---|---|---|---|
| U1 | 110 lines, exp 0389's private copy | none but all-writer `zpass`, as N1 | as now | The memory settings and the register at 0x1ff are out: run U2 | The memory settings or the register: he sets 60 and 3 and U1 repeats |
| U2 | 112 lines | as U1 | as now | The catchers cleared them | The learned lines did |

Holes come by chance as well, so one clean run says less than one run with holes. A control of the register at 0 needs a reboot or GPU reset, and that and the `sysctl` stay the maintainer's. A targeted read of the two new learned lines comes first, on a slot.
