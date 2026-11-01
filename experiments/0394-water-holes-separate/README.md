# 0394 — The night lake's holes: which of three differences made exp 0392's runs clean

**Status: ran 2026-11-01, Result and Verdict at the end.** The plan was written on the laptop on 2026-11-01 after exp 0392, on the top session's GO for this test.

**Question.** N1 and N2 had holes and T1–T3 had none (F779). Three differences stay open: the catchers around the water; swappiness 150 and page-cluster 0; two new lines of the learned file. Which of them was it?

**The two lines,** read on the box at 11:49, on the top session's GO: `0x10fe000000 0x6000000` and `0x1112000000 0x6000000`, in the shared file since 07:54. Those are two 96-MiB windows. What lives there was not read.

**Setup.** Exp 0389's kit and its backend, c11d3fec, so the private binary has none of exp 0392's code. Its arms, its catchers and its poller, as N1. Only three things change: the tags U1 and U2, a new number, and which learned file a run gets (`learned_copy`, by pinned sum). Memory settings stay as they are: swappiness 150, page-cluster 0. `VGT_HS_OFFCHIP_PARAM` stays 0x1ff from exp 0392 until a reboot or GPU reset.

| Run | Learned | If holes | If clean |
|---|---|---|---|
| U1 | 110 lines, 5b92521f, exp 0389's private copy | The memory settings and the register at 0x1ff are out, and the top session decides on U2 | Stop and report. The memory settings or the register at 0x1ff |
| U2 | 112 lines, 23ef45ec | The catchers cleared them in exp 0392 | The two learned lines did |

Holes come by chance as well as by cause, so a clean run says less than a run with holes. Holes means a run's finals reach a hole share of 0.05 or more.

**Rules.** As exp 0389's: RT on, its saves, pins, gates, stops, atomic lock, one deadline. Claim, setup, build and each run are one attempt each, and a refusal is reported once, then stop. A clean U1 ends the series. The shots stay unviewed by me, six a run kept for the maintainer.

**Tests.** `test0394.py` is exp 0389's suite with the tags and `learned_copy`. Only the cases in `raw/test0394-subset.txt` ran, since the rest are exp 0389's and unchanged, 122 of 122 at c11d3fec.

**Result.** 2026-11-01, one run, on the top session's GO. Claim 11:57:32, release 12:10:00. U2 did not run: a clean U1 ends the series.

| | U1 | N1 |
|---|---|---|
| Private binary | 33ba1948 | 33ba1948 |
| Arms, catchers, poller | exp 0389's | the same |
| Learned file | 110 lines, 5b92521f | the same |
| Options, launcher edits, input configuration, save sample, pins, boot | as N1 | |
| Swappiness, page-cluster | 150, 0 | 60, 3 by the top session's record, set to 150 and 0 at about 08:00 |
| `VGT_HS_OFFCHIP_PARAM` | 0x1ff, left by exp 0392 | not read |
| Gfx ring resets since the run before | three since N2 (07:22, 07:41, 07:54), each with a device reopen | |
| Gates | PASS | PASS |
| RT-off, skip, TIMEOUT lines; amdgpu lines; devcoredumps | 0; 0; 0 | 0; 0; 0 |
| Finals, their hole share | 75, 0.000 | 196, 0.299 |
| Shots | 11.0–11.8 %, all 81 | 23–36 % and a stretch at 9 % |

U1 is clean in all 75 finals and steady in all 81 shots, through every arm. By the plan's table that leaves "the memory settings or the register at 0x1ff".

**What this shows.** Neither the catchers nor the two learned lines are needed for a clean lake: U1 had N1's catchers and N1's learned file and no holes. The register alone doesn't explain it either, because T1 was clean at 0 and U1 at 0x1ff. T1–T3 and U1 share two things against N1 and N2 that are known. One is swappiness 150 and page-cluster 0. The other, from the top session's list after this run, is three gfx ring resets, at 07:22 in RR3 and at 07:41 and 07:54 in plays, each with a device reopen. So the chip's state differs from N1's too.

**What this doesn't show.** Which of the two it was. Four clean runs in a row are about 0.1 % by F418's rate if runs are independent, but runs on one boot may not be independent, and clean stretches come by themselves (F777). The rest of the top session's list for 06:38–10:08: three plays, RR3 and RR4, the two learned lines, RR4's mount rebuilds in private paths, the disk cache's contents, and `input.cfg` rewritten at 07:31 with the same RT and JobArenaFix lines as far as read. The kits here use their own pinned input file. No kernel, shared binary or launcher change is known. And U1's view read 11.7 %, a third steady level beside T1's 9.4 and T3's 13.4, so views differ from run to run with no holes in any.

**Verdict.** Not the catchers and not the two learned lines. Two suspects stand side by side: swappiness 150 with page-cluster 0, and the three ring resets. Neither is shown. One U1-type run after the maintainer sets swappiness 60 and page-cluster 3 splits them in one direction only: holes back tie them to the settings, and a clean run points at what a reset changed. A reset also cuts the other way for the register: exp 0392 read it after the resets, so what it held in N1 and N2 is unknown.
