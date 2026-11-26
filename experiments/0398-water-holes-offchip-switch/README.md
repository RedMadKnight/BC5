# 0398 — The night lake's holes: VGT_HS_OFFCHIP_PARAM by turns

**Status: ran 2026-11-01, Result and Verdict at the end.** The plan was written on the laptop on 2026-11-01 after exp 0397 (F784).

**Question.** Do the holes follow `VGT_HS_OFFCHIP_PARAM` inside one run, with nothing else changing?

**Setup.** Exp 0397's kit and binary, with no catcher on at any point: no `zpass`, `stats`, `ureg` or `inputs`. X3 left the register at 0x1ff on this boot. Each write is one shot long and the register latches, so the two flushes that go with a write don't stay on.

| Shots | Y1's register | Y2's, if it runs |
|---|---|---|
| 0–11 | as X3 left it, 0x1ff | what Y1 left, 0x1ff |
| 12–23 | 0 | 0x1ff |
| 24–35 | 0x1ff | 0 |
| 36–47 | 0 | 0x1ff |
| 48–59 | 0x1ff | 0 |
| 60–71 | 0 | 0x1ff |
| 72–80 | 0x1ff | 0 |

**How it will be read.** Fixed before the run, by the shots, since there are no water records, with the depth's finals as far as the poller reaches, about shot 16.

| Y1 | Reading |
|---|---|
| Shots read clean at 0x1ff and holes at 0, in at least two of the three 0 stretches, turning within a stretch's first shots | The register sets the holes, and `BC5_DIRECT_GC_HS_OFFCHIP=1` is the fix candidate |
| Holes at 0, but they don't leave at 0x1ff | The register starts them and something else holds them |
| Clean all through | The register at 0 alone doesn't bring holes: F784's lead fails |
| Holes all through | Likewise, and clean at 0x1ff was something else |

A clean stretch at 0 alone is weak, since holes come in episodes. Y2 runs only if Y1 is not clear, as the same test with the other order.

**After the run** the register is left at 0x1ff, and that holds until a reset, as X3 left it. The last arm of Y2 would leave 0.

**Rules.** As exp 0397's. One attempt at each write, a refusal reported once, then stop. First amdgpu line stops the run.

**Tests.** `test0398.py` is exp 0397's with new tags; only `raw/test0398-subset.txt`'s cases ran.

**Result.** 2026-11-01, one run, boot 53bbe9eb, kernel 7.2.11-ogc4.1, no reset. Claim 20:17:33, release 20:31:14. Private binary a46b46b2, as X1–X3, no catcher on at any point. Gates PASS, 0 RT-off, skip or TIMEOUT lines, 0 amdgpu lines in the journal and the stream, 0 devcoredumps.

| Shots | Register | Shots read |
|---|---|---|
| 0–11 | 0x1ff, left by X3 | 0.9–1.2 % |
| 12–23 | 0 | 0.1–0.5 % |
| 24–35 | 0x1ff | 1.2 % |
| 36–47 | 0 | 0.1–0.4 % |
| 48–59 | 0x1ff | 1.2 % |
| 60–71 | 0 | 0.1–0.6 % |
| 72–80 | 0x1ff | 1.2 % |

**All six writes changed the picture within one shot, both ways.** With no catcher and one register write between the stretches, the stretches at each value match each other. Depth, as far as the poller reached (34 captures, to about shot 16): 14 captures at hole share 0.000 at 0x1ff, then holes in all of the next 20. The last clean capture was 0.5 s before the write of 0, and the first with holes 1.8 s after it, at most 0.008 of the window.

**The caveat.** This run's view had little of the water in the metric's window: 1.2 % at 0x1ff against 9–14 % in the other clean runs, and holes at 0 read as a lower metric, not a higher one. So the plan's first row, "clean at 0x1ff and holes at 0" by the shots, holds for the switching and not for the size. The metric was calibrated for another view. The size comes from runs at the usual view: W1 at 0, holes in every frame, 0.328; U1 and V1 at 0x1ff, none.

**What 0x1ff is.** The title sends it through /dev/gc (F248). In `tools/bc5-agc/regdb/gfx10.json`, `VGT_HS_OFFCHIP_PARAM` has OFFCHIP_BUFFERING in bits 0–8 and OFFCHIP_GRANULARITY in bits 9–10. Mesa ab2374a `ac_gpu_info.c:1414-1468` writes workgroups minus 1, at 8K dwords a workgroup here. So 0x1ff is 512 workgroups of 32 KiB, 16 MiB, and 0 is one workgroup. Mesa caps this family at 128 workgroups per SE and RADV uses 0x5f on the BC-250 (F248's note). ps5-vulkan's `native/tess_offchip_lease.h` (read for the idea only) sets it to the allocation / 32 KiB − 1, so the value says how much offchip memory the title gave. TODO(verify): that allocation, from the title's V#.

**Requirement or coincidence.** A requirement of the kind that needs a sane value, not this exact number: a value the title asked for and the host never wrote, whose absence changes the picture on demand. 0x5f arms in T1–T3 and X3 read clean too, for 15 s each.

**Mechanism: not shown.** All that is measured is F784's stage: everything through the clipper's count is the same, and pixels go.

**Verdict.** The register sets the holes: one register write brings them or ends them, with nothing else changing, in the size given by W1 against U1 and V1. The smallest fix is `BC5_DIRECT_GC_HS_OFFCHIP=1` in the launcher, which already exists: with the title's /dev/gc ring it programs the title's value in the prefix. It has not been run. It needs one test at register 0, on a fresh boot: W1's setup plus that switch.
