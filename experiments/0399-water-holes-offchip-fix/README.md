# 0399 — The night lake's holes: the fix on a fresh boot

**Status: ran 2026-11-01, Result and Verdict at the end.** The plan was written on the laptop on 2026-11-01 after the maintainer's "Tak, po restarcie".

**Question.** F785 showed that `VGT_HS_OFFCHIP_PARAM` switches the holes. Does the host's existing `BC5_DIRECT_GC_HS_OFFCHIP=1`, which programs the title's own value in the prefix, keep the lake clean from a boot, where the register reads 0?

**Setup.** W1 exactly, plus that one option: exp 0396's kit, exp 0389's backend at c11d3fec, its arms, catchers and poller, its 110-line learned copy, on a fresh boot with no reset and no other GPU work before it. W1 is the control: holes in 207 of 207 finals.

The option's path in patch 0001's `tf_ring_prefix` has not been run in this role: with the title's /dev/gc ring it writes `VGT_TF_RING_SIZE` and `VGT_HS_OFFCHIP_PARAM` together in every drawing job's prefix. The journal's `tf ring:` line now goes into `Z1.journal.txt`, and it says what the host wrote. `gates0399.py` requires the option, and the shared build's pin stays what it was: if the J swap changed it, this kit needs its pin moved first.

| Z1 | Reading |
|---|---|
| Finals at 0.000 and shots at clean level, with `tf ring:` showing 0x1ff | The fix works on a fresh boot |
| Holes, with `tf ring:` showing 0x1ff | The prefix's write is not enough, or too late: F785's switch wrote before each job's first draw, with flushes |
| Holes, and the line doesn't show it | The option didn't reach the register: the path, not the idea |

The run can't read the register itself, since it has to be W1's binary. One clean run on a boot where W1 had holes in every frame is a strong result, but a single run.

**Rules.** As exp 0396's. One run, then release. Before the claim: a new boot id, no reset line, no other GPU work since the boot, the shared binary's pin. Z2 is left over from the mechanical rename and does not run. The reboot is the maintainer's. This changes no shared launcher.

**Tests.** `test0399.py` is exp 0396's with the new number and tags; only the cases in `raw/test0399-subset.txt` ran.

**Result.** 2026-11-01, one run on the top session's GO, the first GPU work of boot b9e7fb83 (21:00:52), kernel 7.2.11-ogc4.1, 0 reset lines. Claim 21:09:15, release 21:21:41. Private binary 33ba1948, W1's. Gates PASS, 17,451 flips, 0 RT-off, skip or TIMEOUT lines, 0 amdgpu lines in the journal and the stream, 0 devcoredumps.

The journal's line: `tf ring: base 0x1120000000 size 0x3fff8 offchip 0x0 0x0 0x0 -> VGT_HS_OFFCHIP_PARAM 0x1ff, the title's /dev/gc ring`. So the option reached the prefix, with the title's value.

| | W1, control | Z1, the option on |
|---|---|---|
| Depth zero words at sF, median of 210 snapshots | 0.287 | 0.000 |
| Finals with a clear size, their hole share | 207, 0.328 | 30, 0.000 |
| Shots, all 81 | 28.9–39.3 % | 11.7–13.2 % |
| Arms | "no effect", holes both sides | "no verdict", no holes |
| Frame rate at the last fps line | 30 flips in 1.017 s | 30 flips in 1.016 s |

Only 30 of Z1's finals had a clear render size, since that test leans on the image's zeros, so the zero-word row is the broad reading and the hole share rests on those 30. The shots' level, 13.1 %, is another steady clean view, as T3's 13.4 and U1's 11.7.

**For any title, prepared after the run on the maintainer's yes, not run.** `patch0001-offchip-any-title.diff` is against `src/libs/bc5LleAgc.cpp` as patch 0001 holds it, for the top session to integrate:

1. `BC5_DIRECT_GC_HS_OFFCHIP` is on unless `=0`, so a value a title sends through /dev/gc reaches the register.
2. On the HLE path a 0 in the first value takes the second. TODO(verify): a `[bc5-tess]` line from a title that calls that entry; no experiment's raw logs have one.
3. A title with a TF ring and no value gets `BC5_DIRECT_HS_OFFCHIP`, else 0x5f, RADV's on this chip, with one journal line. TODO(verify): whether that fits a title's real allocation.
4. The write stays in every drawing job's prefix, as the ring's does, so it survives anything that clears the register. Whether a GPU reset clears it was not tested.

`uwatch=1` in `lake_probe` (backend, committed on this branch) is the read-back: the six registers at the first draw of every 256th job, whatever the title draws, with a log line when they change. It needs `BC5_DIRECT_LAKE_CTL`. The module's tests pass (`raw/lake-module-after.txt`). The host diff has not been compiled, because that unit can't be built on the laptop; it applies cleanly to the file reconstructed from patch 0001.

**Verdict.** The fix holds on a fresh boot: the host's existing `BC5_DIRECT_GC_HS_OFFCHIP=1` takes the lake from holes throughout to none, in the plan's first row. One run, with W1 as its control on the same image. Not shown: why 0 loses pixels past the clipper, whether it holds in play and in other scenes, what it does to other titles, and how the picture looks to the eye. The shared launcher is the maintainer's and the top session's to change.
