# 0343 — the soft CP's label polls journaled, and bounded inside a replay

**Question.** Exp 0341's RT-on play held five GFX jobs for 22.0 s on the host (F415): the soft CP's replays on the game
thread's completion queue (`bc5-cq0`) polled a label eleven times to `SoftCp::wait_reg_mem`'s hard-coded 2-s deadline
(22,009.5 ms = 11 × 2,000 + 9.5) while `drain()` held the game thread at the flip; no line recorded it, because the
soft CP's timeout is an `LOGF` and the launchers run the emulator with `--printf-direction Silent`. Two things are
asked of one host change, offline here and on the box after exp 0342 is integrated:
1. *Visibility.* Does the journal now name every soft-CP poll that lasts over 50 ms or runs to its deadline — the
   label, its function, reference and value, the buffer being replayed (kind, pointer, the packet's offset) and whether
   the replay's marks were empty — so that the next hold says which wait and why its mark was missing?
2. *The bound.* With a replay's poll bounded at 8 ms (`BC5_DIRECT_SOFT_WAIT_MS`), does the RT-on route run as before
   (flips, no crash / kernel / TIMEOUT line) and does a hold of this class, if it comes again, last milliseconds, not
   seconds?

**Setup — the change (`patch0343.pl`, host only, `src/libs/bc5LleAgc.cpp` of the patch-0001 tree; no GPU change).**
Seven edits on anchors that must occur exactly once (the script refuses a file that already carries them):
- *E1–E2.* `Direct::timing_now()` declared for the soft CP; in `SoftCp`: `t_wait_bound_ns` (the deadline of a poll on
  this thread, 0 = the 2-s deadline), `t_cur_buf / t_cur_n / t_cur_kind` (the buffer `submit()` is executing), the
  counters `g_soft_polls / g_soft_poll_ns / g_soft_timeouts / g_soft_lines`.
- *E3.* `SoftCp::soft_wait_done()`: every poll not satisfied at the first look is counted; over 50 ms or at the deadline
  it writes, through `Direct::journal` (which the printf direction does not silence), one line:
  `soft-cp wait: t <s> WAIT_REG_MEM[64] on 0x<label> satisfied|TIMED OUT after <ms> ms (bound <ms> ms): fn <f> ref 0x<r>
  value 0x<v>; <kind> <n> dwords at <buf>, packet at <p> (offset <o>); marks empty|set` — offset −1 when the packet lies
  in an `INDIRECT_BUFFER` target; "marks empty" means `t_gpu_done` was empty, so `execute()` treated every packet as not
  run by the GPU. At most 2,000 lines, the counters go on. `wait_reg_mem()` takes its deadline from the thread's bound.
- *E4.* `SoftCp::submit()` names the buffer for the lines.
- *E5.* `completion_thread()`: around each post it sets the thread's bound — `BC5_DIRECT_SOFT_WAIT_MS` (default 8 ms,
  like the game thread's DCB waits; 0 keeps 2 s) on `cq0`, `BC5_DIRECT_SOFT_WAIT_RING_MS` (default 0: unchanged) on
  `cq1` — and journals any post over 100 ms (`slow post: t <s> cq<i> <ms> ms; last replayed <kind> <n> dwords at <buf>;
  soft-cp polls so far <n> (<ms> ms), timed out <n>`, at most 1,000 lines).
- *E6.* The frame profile line gains `, waits polled N (x ms, M timed out)` after `soft-CP passes`, from the soft CP's
  counters since the last flip (global: both completion threads and the ring thread's own pass; the lines say which).

*Why the bound and not "no polling with empty marks".* Empty marks is one hypothesis for the missing marks (a lost entry
is another, and a wait of a nested target a third); the bound covers every unsatisfied poll in a replay whatever the
cause, keeps the replay's order (the packets after the wait still run after it, only sooner), and is the same limit the
game thread already gives its own DCB waits. A replay runs after the job's fence: a label still unwritten then can only
be written by work the title has not submitted, and while `drain()` holds the game thread at the flip that work cannot
come — so the 2-s deadline, the standalone soft CP's (F20, no GPU), buys nothing in direct mode. The ring thread's own
inline pass (`post()` runs it at once on source 1 without `BC5_DIRECT_RING_ASYNC`) keeps the 2-s deadline, and so do
the replays on `cq1` by default: a compute buffer may legitimately end in a wait for the next frame's label there (run
110), and `cq1` is not what held the flip in F415. `drain()`'s condition is not touched.

*Check done on the laptop (no compiler for the host tree here; no unit-test seam: the soft CP is a static part of
`bc5LleAgc.cpp`, built only with the emulator).* `perl -c`; the file reconstructed from main 0e7851d's patch 0001 (the
`+` lines of the `src/libs/bc5LleAgc.cpp` hunk, a new file, 9,478 lines, LF); the script applied to a copy: 12
replacements on 12 unique anchors, 9 `experiment 0343` marks, no CR introduced, a second application refused; the
resulting diff is `raw/patch0343-preview.diff` (158 lines) and was read through: every symbol the new code names is
declared earlier in the unit (`t_gpu_done`, `now_ns`, `Direct::journal`, the counters), the format strings match their
arguments (`PRIu64` for the 64-bit counters, `%lld` for the offset, `%u` for the 32-bit fields), and the non-direct
`#else` block needs no new stub (nothing new is declared in Direct's forward block but `timing_now()`, which is defined
unconditionally). The real check is the box's compile under the shared flags.

**Run (the box, after exp 0342 is integrated; the supervisor's GO).** Exp 0329's pattern for a host unit: the tree's
`src/libs/bc5LleAgc.cpp` copied beside the experiment, `patch0343.pl` applied to that copy, the unit compiled with the
shared normal build's compdb command, the emulator relinked against the shared objects and the integrated archive into
`~/bc5-work/exp0343/kyty_emulator`; nothing shared written. Then the S6N route RT on, one ring, both guards, through a
copy of the integrated launcher (exp 0342's chain), `BC5_DIRECT_FRAME_PROFILE=1` and `BC5_DIRECT_TIMING=1` as the plays
have them: pass = 600 s, no crash / kernel / TIMEOUT line, flips against exp 0342's RT-on run, and the journal read for
`soft-cp wait` and `slow post` lines (expected: none over 50 ms on the route; the frame profile's `waits polled` count
says how often a replay polls at all). Then the maintainer's RT-on play with the build: a transition like 11:16's
decides the bound.

**Result.** Pending.

**Verdict.** Pending.

**The anchors against main's patch 0001 (2026-10-27 17:25, before the box build).** The `src/libs/bc5LleAgc.cpp` that
main d0c2668's patch 0001 (md5 12716e3b) creates — the `+` lines of its one hunk, 9,477 lines — has md5 cfeec2f8, the
same as the box's shared tree `~/src/KytyPlus/src/libs/bc5LleAgc.cpp` (D19); `patch0343.pl` applied to a private copy
of it: 12 edits on 12 unique anchors, 9 marks, 81 diff lines, no adjustment needed. The box side: `build0343.sh`
(exp 0329's pattern: the unit copied into `~/bc5-work/exp0343/src`, patched there, compiled with the shared normal
build's compdb command by `build0343.py`, the shared link command run with that object and exp 0346's private archive
ad7c2cb0 — the third version + the lazy table, a98c8b2 — in place of the shared ones; nothing shared written) and
`mk-s6n0343.pl` (exp 0346's `s6n0346.sh` with the experiment directory, both switches
`BC5_DIRECT_HOST_INDIRECT=learn:1100000000 BC5_DIRECT_SOFT_WAIT_MS=8`, and a result block counting the journal's
`soft-cp wait` / `slow post` lines and the frame profiles' `waits polled` counters).

**Result — R1 on the box (2026-10-27 17:26–17:38, the supervisor's GO, the maintainer away).** Build ecbb95ce: the
shared objects ddfb9456 with `bc5LleAgc.cpp.o` compiled from the patched private copy (e7cc2f60; 0 errors, 5 clang
warnings: 4 pre-existing in the shared unit at lines 79, 397, 2405 and the deprecated `wstring_convert`, 1 in the
soft-cp wait line — `unsigned long long` against `PRIu64`, the same size on x86_64; `patch0343.pl` casts it since
1df1e99, the tested binary keeps it) + exp 0346's private archive ad7c2cb0. The S6N route, RT off, 600 s, one ring,
both 0341 guards, `BC5_DIRECT_HOST_INDIRECT=learn:1100000000 BC5_DIRECT_SOFT_WAIT_MS=8` (both in the emulator's
environ), the live saves compared only, the kernel log streamed (`raw/R1-kernel-stream.txt`: no amdgpu line).

| run | result | flips | soft-cp wait lines | slow post lines | waits polled (21,816 frame profiles) | 0346 |
|---|---|---|---|---|---|---|
| R1 | **pass** (600 s; 0 crash, kernel, TIMEOUT, devcoredump lines; 5,440 RT-off drop lines) | 21,817 / 601.4 s = 36.3/s | 0 (0 timed out) | 0 | 0 polls, 0.0 ms, 0 timed out | 1,209,885 dispatches, all left, 0 rewritten / 0 dropped |

Every soft-CP poll on this route was satisfied at the first look, so neither the lines nor the bound were exercised;
the frame profile carries the new `waits polled` field (`prepare 1.39 / filter 0.51 ms` per frame, as cc0d24ce).
The pass says the change costs nothing and breaks nothing with RT off; the questions need a hold of F415's class,
which came only in long RT-on play.

**The maintainer's shortcut.** "BC5 emulator (test 0343+0346)" on the box's desktop (`shortcut0343.sh`, derived from
exp 0346's with `mktest0343.pl`): `kyty_emulator` ecbb95ce through `~/bc5-work/exp0343/play-pkg-0343t.sh` (md5
fe109f09: the integrated launcher 5b469087 with both switches after the settings loop and a log per start in
`~/bc5-work/exp0343/play/`; RT on from the shared `input.cfg` 30dd586e). "BC5 emulator (test 0346)" stays as it is.
After a play: the journal's `soft-cp wait:` lines (label, function, reference, value, buffer, offset, marks) and
`slow post:` lines, the `waits polled` field of the frame profiles, and the `experiment 0346 rewrite|drop` lines of the
play log; a hold of F415's class should now last milliseconds and name its wait. No RT-on bench run was made for 0343
(the supervisor: the 22-s hold came only in long play). Nothing shared changed.
