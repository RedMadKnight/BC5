# 0278 — the ray-tracing switch, second revision: "off" drops the BVH build list only, the consumer detection opt-in

**Question.** Experiment 0273's switch, with "off" dropping every program that carries a gfx10
ray-intersection instruction plus the second title's BVH build list, blanked the title's menu (its
own picture is lit by three `image_bvh64_intersect_ray` programs) and the run hung on the title's
end-of-pipe sync with the consumers gone (0273, Result; F337). Does "off" work when it drops the
build list alone — the compaction 0x909974400 and the "Ray Tracing Update" chain 0x909939400,
0x909936c00, 0x909939700, 0x909939900, the programs F234/F332 tie to the hangs — and every consumer
keeps running on the trees the build never fills, the state the title already plays in today with the
compaction skipped (exp 0160 run 834)?

**Setup.** `patch0278.py` is 0273's `patch0273.py` with one change in the filter's drop block: the
generic detection (the code scan for MIMG opcodes 0xe6/0xe7) runs only with `KYTY_BC5_RT_DETECT=1`, a
diagnostic; by default a dispatch is dropped with the switch off only when its program is in
`KYTY_BC5_RT_BUILD_PGM`. Everything else is 0273's: the switch (`KYTY_BC5_RT=0`, Emulation › Ray
tracing, `RayTracing.<TITLE_ID>=on|off` in the input configuration, applied at the next flip), the
journal lines ("ray tracing off: … dropped (build list; …)"), the per-title list in the launcher
(`run0278.sh launcher`). Same three files, same anchors (`verify0278.pl` against patch 0001 on main;
`patch0278.py` re-checks on the box's tree a2a2c2df). Build: `run0278.sh build` — a private
`~/bc5-work/exp0278/kyty_emulator` from the shared normal build's objects (three units recompiled and
relinked, `build0278.py`, BOX-LOCK, no emulator), the shared normal binary 9f74965d untouched.

Why the build list alone is safe to drop and only then (from 0273's README): the two count kernels only
write the group counts the builder and the refit read; the builder's leaf lists and the refit's bounds
are read only by the traversals, which keep running here and, with nothing built, walk empty trees;
the compaction's output feeds the other tree family's builders, which run today without it. What a
consumer does on an empty tree is the test: the traversal variants did not hang on the compaction-less
trees in 100 s of run 834; the chain-less state is new.

Test plan (the maintainer, through the supervisor's `play-rt.sh` with `BC5_EMU` set to this binary):
- (a) `KYTY_BC5_RT=0` from the start: the menu has its picture (the three bvh64 programs run), the
  journal's "ray tracing off" lines name only the five listed programs, no "ray tracing: program" line
  (the detection is off), and the title plays past the point of 0273's hang (t ≈ 42 s) and past the
  18:52 one (~1.5 min); any hang then is examined against the TCP session's breadcrumbs (exp 0277).
- (b) the live switch in play: Emulation › Ray tracing off/on, `RayTracing.PPSA03671=…` saved, the
  reflections' change (none expected beyond today's state, since the compaction is skipped either way),
  fps with the chain dropped against running.
- (c) with `KYTY_BC5_RT_DETECT=1` as a diagnostic only, never for play: the list of marked programs per
  run (for the water session's A/B, F333).

**Result.** Prepared 2026-10-24 (the split from 0273 at the supervisor.s request). Built on the box at
19:16:23–19:17:06 on the supervisor.s GO (`run0278.sh build`, lock taken and released): the tree.s
`bc5LleAgc.cpp` a2a2c2df, `hostMenu.cpp` c2e68685, `hostInput.cpp` c5eb3ce2; all anchors applied; the
private binary `~/bc5-work/exp0278/kyty_emulator` (md5 cd17ab79, 166,535,336 bytes) is the shared normal
9f74965d (unchanged before and after) plus `patch_0278.diff` (136 added lines). Four warnings, the same
pre-existing ones as 0273. Not run: the tests wait for the maintainer.


**Test (a), RT off from the start (the maintainer, 19:47–19:58, `play-rt.sh` with `KYTY_BC5_RT=0`,
binary cd17ab79; read offline from read-only copies of `~/bc5-data/captures/play-20261024-1947/gc/direct.log`
and `~/bc5-work/exp0278/play-rtoff-1947.log`):**
- **The menu had its picture** and the title played for about ten minutes (0273's RT-off run had a
  black menu and hung at t ≈ 42 s).
- **The drops are exactly the list:** 12,328 "ray tracing off" journal lines (one in 4,096 drops; the
  counter reached 50,491,393 by the end), all four chain programs and nothing else — 0x909936c00
  (3,560 lines), 0x909939900 (2,971), 0x909939700 (2,924), 0x909939400 (2,873), every one in a compute
  buffer, the two indirect ones as `DISPATCH_INDIRECT`, the count kernels as `DISPATCH_DIRECT`. The
  compaction 0x909974400 does not appear because `BC5_DIRECT_SKIP_PGM` drops it first, as today.
  0 "ray tracing: program" lines: the detection stayed off, as designed.
- **Frame rate:** 596 fps-counter lines, median 47.9 flips/s (mean 43.9, 0.6–59.8); at t 605–606 s
  45–46 flips/s with no gap over 40 ms. Against F277's 37.5 flips/s with RT on this is higher, with the
  caveat that it is a different scene, a different session and the maintainer's own route, not an
  A/B: the chain's cost (F304's 0.7 ms was the compaction alone; the chain's 1,336 dispatches a frame
  are more) is the plausible part of the gap, the rest is the scene.
- **The end** (19:57:27, t ≈ 606 s): a TCP *write* permission fault — RW 1, `PERMISSION_FAULTS` 0x5,
  status 0x00741051, vmid 7, page 0x1474260000, the signature of W266a's at 17:05 — then the 2-s
  timeouts of dcb #841748 (37,814 dwords) and acb #841756 (865 dwords) and a coredump (devcd3,
  19:57:30); the supervisor stopped the emulator at 19:58. That is the TCP session's class (exp 0275,
  F336), not the BVH chain: it came after ten minutes of play with the chain dropped throughout, in a
  buffer that is not the chain's. 1,371 learned-window passes in the session.

**Verdict.** Passed for what it tests. With "off" dropping the build list alone and every consumer
running, the title's menu is lit, the chain's 1,336 dispatches a frame (and the compaction) are gone,
and a ten-minute RT-off session played at a median 47.9 flips/s until a stray-write fault of the F336
class ended it — a fault this experiment neither causes nor explains (the same signature came with RT
on at 17:05). The switch therefore works as "drop the ray-tracing build work"; what the consumers draw
on never-built trees (no reflections, as today) is the visible result, and the generic detection stays
a diagnostic (`KYTY_BC5_RT_DETECT=1`) because dropping consumers blanks the title's own lighting
(0273). Not shown here: the live toggle in play (test (b)) and whether the F332 machine-downs stop on
the S6N route with RT off (0273's (c)); both remain for the supervisor's queue. Integration is the
maintainer's call: the switch defaults to on, so nothing changes until he turns it off.
