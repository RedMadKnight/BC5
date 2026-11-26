# 0352 — the CP check's cost with RT on, and a batched form (HANDOFF Q23)

Ordered by the top session on 2026-10-28 (GO for the offline part first; box runs after the lock cleared). Base:
main 9bd60be (exp 0350: 0349's build in both shared builds, normal affa0c22, archive bb50b2e0, play-pkg.sh 55531ab6).
No change to the shared builds or play-pkg.sh (D19).

**Question.** What does the CP check of indirect dispatches cost with ray tracing on, and can a slimmer form keep
exactly its protection?

**Setup.**
- *The check today* (`bc5/indirect_check.hpp`, `BC5_DIRECT_GPU_CHECK=1` + `BC5_DIRECT_GPU_CHECK_PRODUCT=1`,
  defaults x_limit 65,536, yz_min 1): per GFX-form `DISPATCH_INDIRECT` with a known base, 88 dwords — WRITE_DATA
  flag = 1 (5), three COND_WRITEs x/y/z > limit ? flag = 0 (27), WRITE_DATA confirm (5), PFP_SYNC_ME (2),
  COND_EXEC (5) = 44, plus the staircase: WRITE_DATA flag2 = 0 (5), two COND_WRITEs y/z > yz_min ? flag2 = 1 (18),
  confirm (5), PFP_SYNC_ME (2), COND_EXEC flag2 over a COND_WRITE x > x_limit ? flag = 0 (14) = 44. Two PFP_SYNC_MEs
  per dispatch: each drains the PFP until the ME has written the flags.
- *The batched form* (this branch, `ProductLimit::batch`, `BC5_DIRECT_GPU_CHECK_BATCH=<n>`): a chain = a run of
  such dispatches with only SET_SH_REG / NOP packets between them and one base; runs of two or more (cut at n)
  share one ME phase: one WRITE_DATA sets every pair (flag = 1, flagB = 1; 16 bytes a dispatch), then per
  dispatch the three per-dimension COND_WRITEs (flag = 0) and the staircase as three COND_WRITEs on flagB —
  y > yz_min ? 0, z > yz_min ? 0, x <= x_limit ? 1 (the restore: flagB = !((y or z > yz_min) and x > x_limit),
  function 2 = WAIT_REG_MEM_LESS_OR_EQUAL, Mesa sid.h 0866ae7) — one WRITE_DATA WR_CONFIRM, one PFP_SYNC_ME; at
  each dispatch COND_EXEC flag over (COND_EXEC flagB over the dispatch). 68 dwords a dispatch (+ 10 shared) and
  one PFP_SYNC_ME a chain instead of two a dispatch. Same limits, same acceptance set. The flag area grows to
  4 dwords a chain member (`Stats::flag_dwords`; `Device::submit` sizes it). Ordering: the arguments are read
  before the chain's first dispatch instead of before each; the title puts no barrier between a chain's
  dispatches (exp 0349's dumps: SET_SH_REG + dispatch pairs only), so they are final at the chain's start.
- *Gates.* Catch2 `[batch]` (`tests/indirect_check_batch_test.cpp`): the chain of three, the single's old form, a
  SET_BASE cutting a chain, the batch cap, batching off unchanged. The harness `raw/harness0352.cpp` (0349's plus
  `--batch <n>` and `--sim`): a CP-check simulator walks the final IB as the CP would (WRITE_DATA, COND_WRITE
  with the seven functions, COND_EXEC skips, the title's own flags read as non-zero) with every indirect
  dispatch's arguments set to one triple, for 14 triples (plain, the limits' edges, F403's 818×820×819,
  18:55's garbage, ±inf); both forms must run the same number of dispatches on every dump.
- *Box.* `build0352.sh` (0346's pattern: this branch's backend as a private archive + Catch2, the shared normal
  build's link command with that archive: `~/bc5-work/exp0352/kyty_emulator`), `s6n0352.sh` (0350's integrated
  S6N run on the private binary; `BC5_0352_SWITCHES` for the arm; a frame-profile metrics block).
  Arms, S6N RT on 600 s: A = the check as today; B = `BC5_DIRECT_GPU_CHECK_BATCH=256`. Measured: GPU busy a
  frame, host prepare and filter a frame, flips, from the journal's frame profiles.

**Result.**

- **Offline gate (`raw/harness-gate.txt`), F437.** On all 16 private dumps the batched form changes no decision
  (0 differing lines in the filter, host_indirect and check lines) and the CP-check simulator runs exactly the same
  number of dispatches as the per-dispatch form for all 14 triples (0 differing simulator lines). The simulator
  also shows what the check as deployed lets through: **F403's 818×820×819 grid passes every checked dispatch of
  every dump**, in both forms — the staircase refuses x > x_limit = 65,536 only when y or z > 1, and 818 is not
  above it; the per-dimension limits (2^20, 1024, 1024) pass it too. 18:55's 0xffffffff×0xffffffff and ±inf are
  refused, as are x > 2^20, y > 1024, z > 1024 and x > 65,536 with y > 1. Exp 0341's README said the staircase
  "would catch" F403's grid; it does not with the defaults in play-pkg.sh (`BC5_DIRECT_GPU_CHECK_PRODUCT=1`).
  Nothing in this experiment changes the limits.
- **Baseline frame metrics from the day's journals** (`~/bc5-data/captures/play-*/gc/direct.log`, the frame
  profile lines; per frame): 0350's R1 RT off 18.79 ms GPU busy, 2.63 ms host prepare (filter 1.01), 27.8 ms
  between flips; 0349's R2/R3 RT on 20.19/20.03 ms, 2.49/2.54 (0.96/0.97), 27.6/27.4 ms; 0350's R2b RT on 20.70,
  2.50 (0.96), 27.9. RT on costs ~1.5 ms of GPU a frame over RT off, the BVH work and its checks together; the
  host's prepare and filter times are the same RT on and off, so the check's CPU cost is not visible there.
  The two plateau runs (0349's R1b at 26.2 flips/s RT off, 0350's R2 at 29.2 RT on) both show a higher GPU busy a
  frame (24.9 and 22.6 ms) with the same host time: a GPU-side slowdown, not the host. In every S6N run the first
  two minutes are the slow part (A: 26.2 and 24.6 ms GPU busy, 38 ms a frame, then 19.5 ms and 25.6 ms a frame).
- **Build** (09:08, after two test-only fixes): `kyty_emulator` dc8b9bf7 on the shared normal build affa0c22 with
  this branch's archive (main 9bd60be + 0352), Catch2 74 cases passed.
- **Arm A (S6N, RT on, 600 s, the check as today), 09:10:31 → pass:** 36.2 flips/s, GPU busy 20.36 ms a frame,
  host prepare 2.49 (filter 0.94), 27.7 ms between flips; the staircase ran on 13,714,469 dispatches (~23,000 a
  second, ~630 a frame); no kernel line (`raw/A-kernel-stream.txt`), no TIMEOUT, saves unchanged.
- **Arm B (the batched form, `BC5_DIRECT_GPU_CHECK_BATCH=256`), 09:22:44 → ended by itself at 554 s, F438:**
  35.3 flips/s, GPU busy 20.62 ms a frame, host prepare 2.69 (filter 0.97), 28.3 ms between flips; the staircase
  ran on 12,279,753 dispatches, of which only **32,801 in 368 chains were batched (0.27 %)**: the checked
  dispatches of ordinary RT-on frames are not chains with only SET_SH_REG between them — the timeout dumps,
  where 73–100 % of the checked dispatches batch, over-represent the chain frames. The form is correct and
  gated, and irrelevant to the bulk. The run ended at 554 s with the host's own fatal (exit 65), unrelated to the
  GPU path: `AMM virtual-memory unmap is unsupported: addr=0x0000008500001930` (KytyPlus `src/kernel/memory.cpp`
  line 3732); no kernel line, no TIMEOUT, no refusal (`raw/B-kernel-stream.txt`). Arm A ran the same route 600 s
  without it; the title reached that unmap a few seconds earlier on this run. Per minute both arms are alike:
  GPU busy 26 → 24 → 19.5 ms, 38 → 27 → 25.6 ms a frame.

- **Arm C (every per-dispatch check emitted twice, `BC5_DIRECT_GPU_CHECK_TWICE=1`; build 54823cf9), 09:50:51 →
  pass, F439:** 35.3 flips/s, GPU busy 21.15 ms a frame, host prepare 2.62 (filter 0.94), 28.4 ms between flips;
  the staircase ran on 13,608,202 dispatches (~630 a frame, so ~630 extra checks a frame); no kernel line, no
  TIMEOUT, saves unchanged. Against arm A (20.36 ms, 36.2 flips/s, prepare 2.49) the second copy of every check
  costs **0.79 ms of GPU a frame** (steady state from 120 s: 20.2–20.4 vs 19.5 ms), 0.13 ms of host prepare and
  0.9 flips/s — about 1.25 µs of GPU per check (88 dwords, six COND_WRITE polls, two PFP_SYNC_MEs). That is the
  check's cost as deployed: ~0.8 ms of the ~20 ms the GPU spends on an RT-on frame (4 %), ~2.5 % of the flips,
  nothing measurable on the host. Removing it entirely would give back at most that.

**Verdict.** Measured (F439): the CP check costs the second title about 0.8 ms of GPU a frame with RT on (4 %
of GPU time, 2.5 % of flips) and nothing visible on the host; RT on itself costs ~1.5 ms of GPU a frame over RT
off. A slimmer form can recover at most that 0.8 ms. The batched form of this experiment (one ME phase a chain,
68 dwords a dispatch, two syncs fewer) is correct — same decisions and same simulator verdicts on every dump, Catch2
— but reaches only 0.27 % of the checked dispatches of real RT-on frames (F438), so it is not worth integrating;
the other candidates of Q23 (one check per chain, checking only the BVH-written arguments) target the same chains
and would gain no more. Not pursued further: at 0.8 ms a frame the check is cheap protection. Found on the way
(F437): the staircase as deployed does not refuse F403's 818×820×819 grid (x_limit 65,536 is above 818); if that
class is to be caught, the limits need the data on legitimate 2-D/3-D grids (0341's histogram was of stale reads),
not a new packet form. Also F438's host fatal at 554 s (an AMM unmap the host does not support) is a separate
item for the host side.

**Numbering on main (the top session, 2026-10-28).** The branch called its findings F435–F437. Main had meanwhile given F435 to exp 0353 and F436 to exp 0354, so here they are renumbered: F435 → F437 (the gate and the staircase), F436 → F438 (arm B, the batched form), F437 → F439 (arm C, the cost).
