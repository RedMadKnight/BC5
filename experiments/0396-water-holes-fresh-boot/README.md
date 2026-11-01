# 0396 — The night lake's holes: N1's setup on a fresh boot

**Status: ran 2026-11-01, Result and Verdict at the end.** The plan was written on the laptop on 2026-11-01 after the maintainer's "Tak, restart".

**Question.** K7, N1 and N2 had holes on boot d9cca008. Five runs since three ring resets on that boot have none, whatever the catchers, the learned lines or the memory settings (F779, F781, F782). Does a fresh boot, with no ring reset before the run, bring the holes back?

**Setup.** Exp 0395's kit with a new number and the tag W1: exp 0389's backend at c11d3fec, its arms, catchers and poller, and its 110-line learned copy. Swappiness 60 and page-cluster 3 are what a boot gives, as read before the morning's change. To be read before the claim: a new boot id, those two values, and no ring reset or GPU reset line in the kernel log since boot. W1 has to be the first GPU work of the boot beyond the desktop, so the box stays free from the boot to the claim.

| W1 | Reading |
|---|---|
| Holes: finals reach a hole share of 0.05 or more | Clean is tied to the box's state on the old boot, and the ring resets lead harder. A reset on this boot followed by the same run would then test them directly |
| Clean | The holes depend on something else that changed, and the resets aren't needed for clean. The list stands open, disk cache and all |

Holes come by chance as well as by cause, so a clean run says less than a run with holes. This binary doesn't read `VGT_HS_OFFCHIP_PARAM`, since it has to be N1's: the boot sets that register back too, and what it holds is not read here.

**Rules.** As exp 0395's. One run, then release. W2 is left over from the mechanical rename and does not run. The reboot is the maintainer's.

**Tests.** `test0396.py` is exp 0395's with the new number and tags; only the cases in `raw/test0396-subset.txt` ran.

**Result.** 2026-11-01, one run on the top session's GO, the first GPU work of boot 53bbe9eb (18:54:24). Before the claim: swappiness 60, page-cluster 3, no ring timeout or GPU reset line in the kernel log, lock empty. Claim 18:59:44, release 19:12:29.

**The reboot changed the system.** A staged image came in with it: Bazzite 44.20261026, kernel 7.2.11-ogc4.1 (was 7.2.9-ogc3.1), Mesa 26.2.4 (was 26.2.3), libdrm 2.4.134, CUs 40 of 40, as the top session read them. Private binary 33ba1948 again, 110 learned lines. Gates PASS, 17,345 flips, 0 RT-off, skip or TIMEOUT lines, 0 amdgpu lines in the journal and the stream, 0 devcoredumps.

**W1 has holes, in every frame:** 207 of 207 finals at a hole share of 0.05 or more, mean 0.328, and all 81 shots at 28.9–39.3 %, mean 35.2 %, with no clean stretch at all. All thirteen arms read "no effect" with holes on both sides: F770's set, `binoff`, `smallprim`, `latez`, `nocompress`, the four together, all together, `cache=wbinv`.

| Run | Boot | Before it | Hole share | Shots |
|---|---|---|---|---|
| K7, N1, N2 | d9cca008 | no reset known between them | holes, with clean stretches inside N1 and N2 | 8–43 % |
| T1–T3, U1, V1 | d9cca008 | three ring resets, plays and RR runs | 0.000 in 607 finals | 9–14 % |
| W1 | 53bbe9eb, new image | nothing | 0.328 | 29–39 % |

**What this shows.** The same binary, arms and learned file went from holes to clean on one boot and back to holes after a reboot. So the holes follow state that a reboot resets. By this plan's table, the clean runs were tied to the old boot's state. The new kernel and Mesa don't clear the holes, and they aren't needed for them, because N1 and N2 had holes on the old ones.

**What this doesn't show.** That a ring reset is what cleared them. Plays and RR runs came in the same morning, and the kernel, Mesa and firmware differ between V1 and W1, so a clean W1 wouldn't have separated those. With holes it needs no such care: W1 had no reset and holes, N1 had none known in those hours and holes, and the clean runs all came after resets. Five clean and one hole run are few, and a run's state may also come by chance (F418).

**Verdict.** The holes are back on a fresh boot, so clean was the old boot's state, not the catchers, the learned lines or the memory settings. Ring resets lead, not shown. Next, on this boot, before any play or reset: exp 0392's catchers and arms with holes present, which they've never had. Then the same run after a ring reset on this boot, whichever way one comes.
