# 0280 — RT off, the second tree family too: a list change only (`KYTY_BC5_RT_BUILD_PGM`)

**Question.** Exp 0278's "off" drops the compute chain of the first tree family (F332) and the
compaction, and the ten-minute RT-off session of 19:47 then stopped inside the *second* tree family's
builders on the graphics ring (exp 0279, F339: the fetcher at 0x909974200 / 0x909973900 /
0x909973b00 / 0x909973d00 after the last `CS_PARTIAL_FLUSH`; the same eight programs, in the same
order, as the RT-on hang of 18:52, exp 0275). Should "off" drop that family as well — what does each
program do, who reads its output, is it safe to drop with the consumers still running, and does
anything non-RT depend on it (the lake's coverage, F333)?

**Known before this experiment** (F104, exp 0050 runs 197–203, exp 0160's record of the compaction's
inputs and its agents' readings of 0x909977100 / 0x90997a500 / 0x909977e00, F207, F234, exp 0279).
The family runs once per frame in a graphics buffer, one dispatch per object, all taking their
arguments from the object's block (one argument slot per program):

| program | slot | what it does | who reads its output |
|---|---|---|---|
| 0x909974200 | +0x40 (writer) | the block's clear/init pass: zeroes the per-object block the others fill (exp 0160: "the clear 0x909974200") | the five programs below, this frame |
| 0x909973900 | +0x00 | leaf-list builder of the second family's "PSR_BVHL" trees (F104: the trio 3900/3b00/3f00 "for the other tree") | the ray-traced traversals (every `image_bvh` consumer, F113/F232/F234) and the family's later passes |
| 0x909973b00, 0x909973f00 | +0x20 | the trio's other two stages (list fill / finish) | as above |
| 0x909973d00 | +0x60 | a 3-D cell pass (grids up to 69×69×69 groups, exp 0279): a voxel or spatial-hash build over the object — not read by me; its slot is the one F336 saw floats in | the traversals (TODO(verify): which consumer reads the cells) |
| 0x909974400 | +0x40 | the neighbour-link compaction (F207, exp 0160) — already skipped by `BC5_DIRECT_SKIP_PGM` in every launcher since F207 | 0x909977100, 0x90997a500 (and 0x909977e00) |
| 0x909977100, 0x90997a500 | +0x80 | the compaction's consumers: 0x909977e00 builds leaves from a {triangle, 3 neighbours} table at the block's BASE_A+0x80+cb[0x9c]·32; the two here are its siblings (exp 0160 agents) | the traversals |

Everything the family writes is BVH data for the ray queries: leaf lists, neighbour links, cells. No
draw, no light pass and no culling of this title has been seen reading it (exp 0050/0059: the trees'
only readers found in user data were an empty program and a 32-byte copy kernel, F115); the lake's
coverage holes (F333) are the one open suspicion of a non-RT dependency, untested, and this list is the
A/B that tests it. The reasoning is the same as for the compute chain of 0278: the consumers keep
running and walk trees the build never filled. The difference: with the first family's chain dropped,
its trees stay as the title's CPU converted them; with this family dropped too, the second family's
trees keep their template leaf lists (empty, exp 0050 run 193), which the *refit* loops on (F104) but
the refit belongs to the first family and is dropped; what the hardware/software traversal does on an
empty list is the test's risk (a hang would then move from 0x9099… to an 0x11d04… program and say so).

**On 0x909977100 and 0x90997a500 — "consumers", but of the compaction.s output, not of the picture.**
0278.s rule (drop builds, keep consumers) is about the programs that *read trees to shade pixels*: the
`image_bvh` ray queries, whose dropping blanked the menu. These two have no ray-intersection
instruction (the 19:04 scan: "has no ray-intersection instruction" for both), they take their
arguments from the object block.s +0x80 slot like the other build passes, and in exp 0160.s agent
readings their sibling 0x909977e00 *writes* leaf records from the {triangle, 3 neighbours} table — they
are build stages that consume the compaction.s links and produce tree data. Nothing that shades reads
them directly; the traversals read the trees they help fill. Since 2026-10-19 the launchers skip the
compaction they read from, so they have run every frame on un-compacted links without blanking
anything — the picture does not depend on their output being right. What I have not read is their
exact role, so they are the second arm, not the first.

**Setup.** No code change: binary cd17ab79 (exp 0278) reads `KYTY_BC5_RT_BUILD_PGM` from the process
environment once, at the first dispatch it filters (`pgm_list`, a `static const` set), so the list is
the launcher.s (`~/bc5-work/exp0278/play-rt.sh`). Two arms, `KYTY_BC5_RT=0` in both:

- **Arm A — the five builders of the second family** (0278.s five plus 0x909974200 clear/init,
  0x909973900/3b00/3f00 leaf-list trio, 0x909973d00 cells):

      export KYTY_BC5_RT_BUILD_PGM=909974400,909939400,909936c00,909939700,909939900,909974200,909973900,909973b00,909973d00,909973f00

- **Arm B — arm A plus the compaction.s two consumers** 0x909977100, 0x90997a500:

      export KYTY_BC5_RT_BUILD_PGM=909974400,909939400,909936c00,909939700,909939900,909974200,909973900,909973b00,909973d00,909973f00,909977100,90997a500

(0x909974400 is listed for the day `BC5_DIRECT_SKIP_PGM` stops carrying it.) With the switch off every
dispatch of the listed programs is dropped (`DISPATCH_DIRECT` and both `DISPATCH_INDIRECT` forms, in any
buffer), journaled one in 4,096 as "ray tracing off: … dropped (build list; …)". With the switch on
nothing changes. Run length: 20–30 minutes if the maintainer can, arm A first.

Test (the maintainer, the supervisor.s wrapper):
- the journal.s "ray tracing off" lines name the arm.s programs and nothing else; no "ray tracing:
  program" line;
- the menu lit, the title playable, a long run;
- the F336/F339 class: no stray-write fault and no hang in 0x9099… during the run — one that comes is
  outside the dropped set; a hang moving to an `image_bvh` program (0x11d04…) means the consumers
  cannot walk the family.s template trees and "off" needs defined trees (a one-node tree) instead of
  none;
- arm B only if arm A is clean: the same checks, plus whether anything on screen differs from arm A;
- the lake: the water session.s patchwork A/B (F333) with arm A against 0278.s list, if the maintainer
  can reach the lake save.


**Result — arm A** (the maintainer, 20:48–20:57, `play-rt.sh`, `KYTY_BC5_RT=0`, the ten-program list,
binary cd17ab79; read offline from read-only copies of `~/bc5-data/captures/play-20261024-2048/gc/direct.log`
and `~/bc5-work/exp0278/play-rt-2048.log`):
- **No hang, no fault, no timeout**: 0 amdgpu fault or timeout lines, 0 `TIMEOUT` in the journal; the
  maintainer quit after about 573 s. The menu was lit.
- **The drops are exactly the list**: 6,960 "ray tracing off" lines (one in 4,096; counter 28,504,065
  at the end), all "build list": the chain in compute buffers (0x909936c00 2,448 lines, 0x909939900
  1,526, 0x909939400 1,487, 0x909939700 1,484) and the second family in graphics buffers as
  `DISPATCH_INDIRECT` (0x909974200 4 lines, 0x909973f00 3, 0x909973d00 3, 0x909973b00 3, 0x909973900 2
  — few lines because the counter is shared and the family is ~200 dispatches a frame against the
  chain's ~1,300). The compaction fell to `BC5_DIRECT_SKIP_PGM` as before (12,289 skips). 0 "ray
  tracing: program" lines.
- **The lake had no patches.** The maintainer: "na jeziorze nie było łat, jezioro wyglądało
  prawidłowo" — with the second family's build work dropped, the night lake's patchwork (F251/F255/F333)
  was gone, in one session. He saved at the lake (slot 4 "manual-1", 20:57; saves af64b06adff9c5f1,
  a copy in `exp0278/saves-after-lake-save-2057`). So the lake's per-cell coverage does depend on that
  family — F333's open suspicion, answered the other way round from what the question feared: the
  family's output (or its stray writes, F339) *breaks* the lake's coverage rather than feeding it; with
  it gone the water is drawn whole.
- **Frames:** 553 fps-counter lines, median 35.9 flips/s (mean 35.8, 4.5–58.0), 42 seconds under 20;
  the session holds the night lake, a heavier scene than 0278's route, so no comparison with 0278's
  47.9. Seven frames over 500 ms in the journal (t 238.6, 240.8, 421.3, 538.0 at 4.7 s, 553.4 at
  1.8 s, 568.0, 568.8), 2,593 learned-window passes: the loading/sync territory of F203/F206, not
  this list. The maintainer: fps drops, but "ok".

**Arm B.** Not run, and not needed for the hang question: arm A was clean for ten minutes with the
second family dropped, so the two compaction consumers (0x909977100, 0x90997a500) are not what hangs or
writes astray — they ran throughout. What arm B would still add is small and separable: whether
dropping them changes anything on screen (they ran on un-compacted links since F207 without visible
effect) and a few hundred dispatches a frame of GPU time. Left optional, for a later fps A/B, not for
the hang series.

**Verdict.** Passed. "Off" with the second tree family on the list plays the night lake for ten minutes
with no hang, no fault and no timeout, drops exactly the listed programs, and — the finding of this
experiment — draws the lake without its patchwork: the second family's build work (one of
0x909974200, 0x909973900/3b00/3d00/3f00, by this experiment; which one is for a one-at-a-time A/B or
F339's breadcrumbs) is what breaks the lake's per-cell coverage with the compaction skipped, which
also fits F339's stray write from that family's wave. For play, the maintainer now has an RT-off setting
that removes the two hang families and the lake's holes at the price of ray-traced reflections the host
never produced here anyway. Open: which of the five does it, and what the family writes astray (TCP,
exp 0277/0279); the live toggle in play (0273 (b)); the S6N machine-downs with this list (0273 (c)).
