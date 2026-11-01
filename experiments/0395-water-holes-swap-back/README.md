# 0395 — The night lake's holes: exp 0394's U1 again with the old memory settings

**Status: ran 2026-11-01, Result and Verdict at the end.** The plan was written on the laptop on 2026-11-01, on the top session's GO, after the maintainer set swappiness 60 and page-cluster 3 ("Tak, ustawiam", read back at 12:53:19 and at 12:54:33, same boot d9cca008).

**Question.** U1 had N1's binary, arms, catchers and learned file and no holes (F781). Two suspects stand: swappiness 150 with page-cluster 0, and three gfx ring resets. With the settings back, do the holes come back?

**Setup.** Exp 0394's kit with a new number and the tag V1: exp 0389's backend at c11d3fec, its arms, catchers and poller, and its 110-line learned copy. `VGT_HS_OFFCHIP_PARAM` is still 0x1ff from exp 0392, and the ring resets are still behind us.

| V1 | Reading |
|---|---|
| Holes: finals reach a hole share of 0.05 or more | The memory settings: they cleared the holes in T1–T3 and U1 |
| Clean | The settings are out, and what a ring reset changed leads (the register at 0x1ff is part of that question) |

Holes come by chance as well as by cause, and a clean run says less than one with holes.

**Rules.** As exp 0394's. One run, then release. V2 is left over from the mechanical rename and does not run.

**Tests.** `test0395.py` is exp 0394's with the new number and tags; only the cases in `raw/test0395-subset.txt` ran.

**Result.** 2026-11-01, one run on the top session's GO. Claim 13:05:33, release 13:18:29. Swappiness 60 and page-cluster 3, read at setup. Private binary 33ba1948, as N1 and U1. Learned file 110 lines. Gates PASS, 16,372 flips, 0 RT-off, skip or TIMEOUT lines, 0 amdgpu lines in the journal and the stream, 0 devcoredumps.

**V1 was clean:** 202 finals at hole share 0.000, all 81 shots at 9.1–9.8 %, every arm "no verdict: no holes beside it". By this plan's table the settings are out, as far as one clean run can say that.

| Run | Boot's ring resets before it | Swappiness, page-cluster | Catchers | Learned lines | Register | Holes |
|---|---|---|---|---|---|---|
| K7, N1, N2 | none known by the top session's list for 06:38–10:08; earlier in the boot not listed | 60, 3 | all-writer `zpass` | 110 | not read | yes |
| T1 | 3 | 150, 0 | around the water | 112 | 0, then 0x1ff | no |
| T2, T3 | 3 | 150, 0 | around the water | 112 | 0x1ff | no |
| U1 | 3 | 150, 0 | all-writer `zpass` | 110 | 0x1ff | no |
| V1 | 3 | 60, 3 | all-writer `zpass` | 110 | 0x1ff | no |

**What stands.** V1 and N1 differ, as far as is known, only by what happened to the box between them: the three ring resets with their device reopens, and the plays and RR runs around them. T1 was clean with the register at 0 and every run since at 0x1ff, so the register's value isn't needed either way, though what it held before the resets isn't known.

**What doesn't.** Nothing here shows that a reset did it. There's no run with holes after a reset and no clean run before one in this table. Earlier rates had clean runs by chance (F418), though five in a row at that rate is about 0.01 % if runs are independent. Anything else in the box's state that survives between runs, such as the disk cache's contents, is still a suspect.

**Verdict.** Not the memory settings, on one run. What changed the lake lies in the box's state since the morning, and the ring resets lead. The test is his to give: a run of this kit on a fresh boot, with no ring reset before it. Holes back would tie the clean state to what the resets changed. Clean would mean the holes depend on something else that has changed.
