# 0397 — The night lake's holes: exp 0392's catchers and switches, with holes there this time

**Status: ran 2026-11-01, Result and Verdict at the end.** The plan was written on the laptop on 2026-11-01, on the top session's GO, right after W1 (F783).

**Question.** Exp 0392 asked at which stage the water's cells go and whether the TF ring's handling changes it, and got no answer because its runs were clean (F779). Boot 53bbe9eb has holes in every frame (F783). So: the same question, on this boot, before any play or reset.

**Setup.** Exp 0392's kit and backend, HEAD's, with the tags X1, X2, X3, its catchers all through and its seven arms in each run's own order, and the corrected reader as the kit's own (`zp0397.py`). The learned file is today's, 112 lines, as the kit takes it.

**`VGT_HS_OFFCHIP_PARAM`.** `ureg` reads it each frame from shot 0, so X1 gives this boot's value before anything writes it. Only X3 writes it, in its last arms, 0x1ff, 0x5f, 0x1ff. It latches at 0x1ff until the next reboot or GPU reset, across every session's runs.

**How it will be read.** Exp 0392's table needs clean and hole frames in one run, and a run with holes throughout won't have them. Then the stage comes from two other readings, fixed here before the runs:

1. **Each counter of occurrences 0 and 2 against the depth's hole pixels** at the finals, within a run. A counter that follows the holes is a stage that loses cells.
2. **The counters' means against T1–T3's clean ones at the same render size.** IA and HS should match, as they count what was issued. The first stage below them that falls by 5 % or more is the stage. Views differ from run to run (F779), so this is the weaker of the two.

An arm clears holes if the water's mean S at the commonest size rises to clean level inside it and falls after it, with the depth or the metric agreeing, in at least two of the three runs. A clean frame's S is known from no run on this boot, so a rise of 5 % or more that follows the arm is what to look for. Any holes ending by themselves, or any run clean from the start, is a result about the state, as in F783.

**Rules.** As exp 0392's. One attempt at each write, a refusal reported once, then stop. The first amdgpu line stops the run. New on this path since exp 0392: nothing but the arm files and the reader.

**Tests.** `test0397.py` is exp 0392's with the new tags and reader; only the cases in `raw/test0397-subset.txt` ran. The harness timed out on an overloaded laptop on the last five; the ring summary was checked by hand and those cases passed in exp 0392.

**Result.** 2026-11-01, RT on, boot 53bbe9eb, kernel 7.2.11-ogc4.1, no reset before or during, 0 amdgpu lines, 0 devcoredumps. Claim 19:29:10, release 20:06:06. Private binary a46b46b2, as T1–T3. Gates PASS in all three runs.

**The stage, by the plan of exp 0392: PS.** In clean and hole frames at one render size, by the reader that labels within a size:

| Ratio hole / clean, occurrences 0 and 2 | X1 | X2 | X3 |
|---|---|---|---|
| IA_VERT, IA_PRIM, HS, VS, GS, C_INV | 1.000–1.001 | 1.000 | 0.997–1.000 |
| DS | 1.000, 1.000 | 1.000, 1.000 | 0.998, 0.997 |
| C_PRIM | 0.988, 1.014 | 0.994, 1.005 | 1.006, 1.048 |
| PS = samples | 0.777, 0.816 | 0.765, 0.786 | 0.723, 0.751 |

Everything through the clipper's count is the same in hole frames, and PS invocations equal passed samples to the sample. So the water's patches are issued, tessellated and sent on, and pixels go between the clipper and the PS. HS and DS being flat rules out factors of zero as the cause of the lost samples.

**The arms.** Holes came in episodes, so most arms had none beside them. No ring arm moved anything: the `tailflush`, `tfonce`, `tfdist` and `gepc` arms that read holes at all read them as off shots do.

**`VGT_HS_OFFCHIP_PARAM` on a fresh boot reads 0** (X1, X2, X3 to its arm). The title asked for 0x1ff (F248).

**Where the holes were, and with what:**

| Run or stretch | Register | Stats, `ureg`, `inputs` | Holes |
|---|---|---|---|
| W1, fresh boot | 0 | off | every frame |
| X1, X2 at shots 78–80, catchers just off | 0 | off | about 28–32 %, at once |
| X1, X2, X3 | 0 | on | episodes, mostly clean; shot means 10–12 % |
| T1 | 0 | on | none |
| X3 from shot 69, and 78–80 with catchers off | 0x1ff | either | none |
| T2, T3 | 0x1ff | on | none |
| U1, V1 | 0x1ff | off | none |
| K7, N1, N2 | not read | off | holes |

**Every run or stretch at 0x1ff is clean.** At 0 they come back as soon as the stats catchers stop. This reverses the reading of F782 and F783: T1's `offchip` arm latched 0x1ff, which explains U1 and V1 with no ring reset, and the reboot put it back to 0, which explains W1. F781's "the register doesn't explain it alone" looked at T1, which was the one clean run at 0, with the catchers on. N1 and N2 were not read, and the model needs them at 0.

*Why that would give holes is a hypothesis, not shown:* `OFFCHIP_BUFFERING` 0 is one 32-KiB workgroup, the title sized its offchip memory for 512, so HS waves in flight could overlap and DS could read another patch's data. The patches would still be counted through every stage and draw in the wrong place. The stats samples between the water's draws could then reduce the overlap. X and Y as two sets of waves would fit, untested.

**Verdict.** The stage is after the clipper's count, in all three runs. The register is the lead: at 0x1ff no holes in any run. That is a reading of runs made for other reasons, and the arms did not switch holes off on purpose, because holes were absent when X3 wrote it. The test is one run that writes 0 and 0x1ff by turns with no catchers. If holes follow, the existing `BC5_DIRECT_GC_HS_OFFCHIP=1` is the fix candidate.
