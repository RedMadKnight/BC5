# 0346 — the host resolves and verifies an indirect dispatch's arguments; the CP never reads an inferred address

**Question.** The second title's BVH refit issues GFX-form `DISPATCH_INDIRECT`s whose data offsets are the low dwords
of addresses in its 4-GiB window, with `SET_BASE` index 1 deliberately 0 (it zeroes the base at the end of each
buffer); the console resolves that within the process's window, the BC-250 read the bare offset — a CPF permission
fault, a failed ring reset, the machine down (exp 0344 hang 2, F416, 2026-10-27 12:52). Exp 0345 answered with CP
polls at bases the backend inferred and took the box down twice more (13:29, 14:25), each time a CP fault at a page
inside the window that the GPU may not read. So: can the host resolve and verify these dispatches itself, at filter
time, and change the packet only to a page it has read — with everything unverified dropped — so that the refit runs
where its arguments are and the CP never reads an address nobody checked (D16)? Does that pass the RT-off route, the
RT-on route and the maintainer's post-load spot without a fault, a reset or a machine-down?

**Setup — the change (backend only, on main d0c2668's backend; no host struct changes, the 0341 ABI lesson).**
- *The 0345 path is gone.* `indirect_check::apply` inserts the CP check only for a dispatch whose base comes from a
  `SET_BASE` in the same IB (its 0052 behaviour: the CP reads that page anyway); it gets no inferred base.
- *One base-1 per shader type, in the check too* (`indirect_check.cpp`): a `SET_BASE` index 1 sets the register its
  header's bit 1 names, a dispatch or draw reads the one its own header's bit names (the single base tracked since 0052
  checked gfx-type dispatches against a compute-type `SET_BASE` in a buffer that mixes the types — exp 0344's reads).
- *`bc5/host_indirect.hpp`, `host_indirect.cpp` (new, pure, unit-tested).* `resolve_indirect(ib, carried[2], window,
  regions, reader, limits)` walks the IB with the two registers (the caller's carried values, updated by the IB's own
  `SET_BASE`s) and, for every GFX-form `DISPATCH_INDIRECT`, decides: **Leave** when a `SET_BASE` of its type precedes it
  in this IB; else the candidate is `base + offset` with the carried register of its type, or — when that is 0 — the
  title's window (the high 32 bits of its own non-zero `SET_BASE` values; `learn`, with a fixed value until one is
  seen), and the candidate must pass three checks: its 12 bytes lie in a **real mapping** (`Region`: the device's
  userptr and shared mappings of title memory — the sorted table holds no PRT window, guard page or zero buffer), the
  **reader can read them from the CPU** (the host's `mapped` test and a CPU read, GPU VA == guest VA as the 0341
  histogram read), and the **counts pass the host's sanity limits** (65536 × 64 per dimension and as a product, the
  host's own rule; stale values accepted, 0038). Verified → **Rewrite**: `SET_BASE` (the dispatch's own type) = the
  4-KiB page holding the arguments, the dispatch with `offset = address − page`, `SET_BASE` (same type) back to the
  register's previous value — the CP reads the page the host read and the title's state after it is what it was;
  otherwise **Drop**: a NOP of the dispatch's length, counted by reason (no candidate, not a real mapping, unreadable,
  insane counts). `rewrite_verified()` applies the decisions through `indirect_check::insert_before` (the IB's own
  `COND_EXEC` counts grow); if a count cannot grow, the rewrites become NOPs too (`nop_on_overflow`): nothing ever runs
  at an inferred address. Draws are not touched (the title sets their base in the same buffer).
- *In `Device::submit`* (`direct.cpp`), right after `policy::filter` (so the host's drops are already NOPs and the
  shadow pass, the DMA syncs and the CP check see the rewritten IB; the check then polls the verified page, as for any
  `SET_BASE` in the IB), behind **`BC5_DIRECT_HOST_INDIRECT`** read by `Device::open` (default off; `1` or `learn`:
  the window learned; `learn:<hex>`: that value until one is learned; `<hex>`: fixed). The `Device` carries the two
  registers across GFX-ring jobs (`hi_base1`, from each IB's last `SET_BASE` per type, the rewrites' restores included)
  and the learned window. One stderr line per program the first time it is rewritten or dropped (kind, offset, type,
  base, address, page, the counts read, the reason) and the sums in the periodic / close summary with the 0341 lines.
- *Tests* (Catch2): `tests/host_indirect_test.cpp` — the refit's packet with base 0 and the window verified and
  rewritten (the packet sequence, the restore to 0, the record's fields); the four refusals each NOP-ed for its reason
  (no window, outside every real mapping, unreadable, insane counts); a `SET_BASE` of the dispatch's type in the same IB
  leaves it, a compute-type `SET_BASE` does not serve a gfx-type dispatch, the carried graphics register serves it and
  is restored after; a `COND_EXEC` count that cannot grow turns the rewrites into NOPs. `tests/indirect_check_test.cpp`
  + one case: the check's per-type bases (a compute-type `SET_BASE` then a gfx-type dispatch → unbased; a gfx-type
  `SET_BASE` → checked against it; a compute-type dispatch → against the compute base; the caller's base is the
  graphics register). Not compiled on the laptop (no compiler for the backend here); the build and the tests run on the
  box after the GO, as exp 0341's `build0341.sh` did.

**Run (the box, after the GO; the box is offline until the maintainer's hand reset).** A private archive from this
branch's `backend/` with the tests, the integrated normal build's objects (ddfb9456) relinked against it; the S6N
route RT off 600 s with `BC5_DIRECT_HOST_INDIRECT=learn:1100000000`, the kernel log streamed to the laptop (exp
0345's lesson: the box's journal and the play log lose their tails on a hard hang); pass = no crash, kernel, CPF/CPG
or TIMEOUT line, flips near 36.4/s, the summary's counts (expected on the RT-off route: a few dispatches of the chain
watchdog's buffers resolved against the carried base, 0 dropped as unmapped); then RT on 600 s (hang 1's ring-reset
class at ~106 s does not fail it; a CP fault, a failed reset or a machine-down does); then the test shortcut for the
maintainer's post-load spot. Pass line for the refit: the rewrite line names 0x90997a500 with a real mapping and sane
counts, no fault.

**Result — R1 on the box (2026-10-27 15:32–15:35).** Build: archive d096247e (0 warnings), 65 cases / 32,424
assertions pass (one case of mine corrected first: `insert_before` clamps a `COND_EXEC` range past the IB's end, so the
overflow case needs a real 0x3ff8-dword range), emulator **784a9a62**. R1 (`s6n0346.sh dc9d4f25fc2d41ca R1 600 off`,
`BC5_DIRECT_HOST_INDIRECT=learn:1100000000`, RT off): **the GPU hung about 60 s in** — 15:35:02.58 `ring gfx_0.0.0
timeout` (bc5-ring) with **no page fault before it**, 0.19 s later `reset failed`, and the new bc5-gpu-watch crashed
the kernel within 60 ms; pstore kept the tail and the box was back at 15:35:38 (`raw/R1-kernel-stream.txt`; the
devcoredump `20261027-153502-devcd1.txt`; the stale lock cleared by the supervisor; live saves unchanged). Three builds
that replace the CP's carried base with one the backend infers (0345 v1 13:29, 0345 v2 14:25, 0346 15:35) have now
taken the box down with RT off on a route the shared build runs 600 s clean; **this line stops until an offline replay
shows exactly what each build changed in the stream.**

*The offline harness* (`raw/harness0346.cpp`, built on the laptop with MSVC — `raw/build-harness.ps1`, or the two
`cl` lines in it by hand — twice: against main d0c2668's backend sources and against 0346's): for each IB dump, in
submission order, `policy::filter` (gpu check on, everything mapped, no host drops), 0346's `host_indirect` (every
candidate counts as mapped and readable, counts 1 1 1: the decisions and addresses are real, the verification is not),
optional shadow labels, `indirect_check::apply` with the staircase; then one line per `SET_BASE` and per
`DISPATCH_INDIRECT` of the final IB — its type, the argument address under the per-type model and under a
single-register model, whether a check precedes it and which address the check polls — and, with `--packets`, every
packet for a line-by-line diff. On exp 0344's synthetic dump both builds run as designed (the 0346 output rewrites the
one unbased dispatch into `SET_BASE page / dispatch / SET_BASE back` and the check polls that page; main leaves it
unbased). The title's dumps are not in the repository; the harness runs on a private copy.

**The offline replay (2026-10-27 ~16:00, laptop; the title's dumps in a private folder, never committed; the harness built
with MSVC against main d0c2668's backend and 0346's; numbers only here).**

*The decisive fact: the CP has one base-1 register, not one per shader type.* The host's own compute conversions
(`mec_expand_ib`, since experiment 0038) emit `SET_BASE` **0xc0021102** (compute type) + `PFP_SYNC_ME` + `DISPATCH_INDIRECT`
**0xc0011600** (graphics type) for every converted dispatch — 45 such pairs in 12:39's acb, 19 in 15:35's — and those
dispatches have run correctly for weeks (F106, F107, every RT-off route): a compute-type `SET_BASE` serves a
graphics-type dispatch. The title does the same the other way and belt-and-braces: its zeroing is a pair, `SET_BASE`
0xc0021102 = 0 then 0xc0021100 = 0 (15:35's dcb at 1343/1347, 4602/4606, 5569/5573, 7033/7037; 12:52's at 20670/20674
… 30043/30047). So the per-type model of 0345 v2 and 0346 was wrong, and the "0052 single-base bug" was not a bug.

*What each build changed, hang by hang.*
- **12:39 (shared ddfb9456, RT on, hang 1).** Not a base matter: the acb's 45 converted dispatches all have their
  `SET_BASE` in the IB (harness: main checked 45, unbased 0). The looping small dispatch of exp 0344.
- **12:52 (shared ddfb9456, the maintainer's RT-on play).** The refit's 435 graphics-type dispatches (offsets
  0x9bce4d80 …) come before any `SET_BASE` in their chain (harness: main unbased 435 of 576), after the previous
  buffer ended with the zero pair: the one register was 0, the CP read the bare offset — the CPF fault at 0x9bce4000.
  The class the fix is for.
- **13:29 (0345 v1).** v1 rebased or NOP-ed every dispatch whose single-base tracking saw 0 in its IB: in the hung
  chain 5,009 of 6,499 (harness: main unbased 5,009; the surviving v1 lines: `NOT mapped: NOP-ed` for the chain's
  programs 0x909873200 … and the title's passes 0x11d0323c00, 0x11d032b100, 0x11d0349300, 0x11d0339900, 0x11d0359000
  at offsets 0xb00 … 0x300). Those dispatches rely on the register the previous job left (non-zero on the shared build:
  they run); v1 replaced that with the window or a NOP. Which CP packet then wrote 0x11da0e2000 (the CPG write of
  13:29) is not in the dumps; what is: thousands of the title's dispatches did not run, and the stream went on.
- **14:25 (0345 v2).** v2 checked a dispatch against the register of *its own* type, carried: the conversions' graphics-type
  dispatches against the graphics register (the title's draw base of the moment) + the conversion's small offset, instead
  of the compute-type page in front of them, and the title's graphics-type dispatches before any `SET_BASE` (harness: in
  14:25's dcb 1,045 unbased on main, offsets 0x2657a0 …) against a carried graphics value. The `COND_WRITE` polls then read
  draw-base + offset pages; one lay in the unlearned region 0x11d6000000 + 0x6000000 (guard-mapped: `PERMISSION_FAULTS
  0x3, MAPPING_ERROR 0`): the CPG read fault at 0x11dab43000, the failed reset, MODE1.
- **15:35 (0346).** `host_indirect` applied the same per-type rule: a converted dispatch (graphics type) had "no
  `SET_BASE` of its type" in its IB, the carried graphics register was 0, so the candidate was window + offset
  (0x1100000520, 0x1100000440 …), outside every real mapping — **NOP**. The surviving lines count it: 10,647 then 17,468
  dispatches dropped "not a real mapping" in ~60 s, 14 programs (the BVH chain's 0x909873200, 0x909859a00,
  0x90985c800, 0x909927c00, 0x90992af00, 0x9098ea000, 0x909969d00, 0x90996cc00, 0x9098eb200 and the title's passes
  0x11d0323c00, 0x11d032b100, 0x11d0349300, 0x11d0339900, 0x11d0359000), 0 rewritten. The harness on 15:35's acb #22813:
  0346 "rewrites" its 19 converted dispatches (everything mapped offline) where the run NOP-ed them; on the hung dcb #22816
  0346 changed nothing (0 indirect dispatches). The dcb's 13 `WAIT_REG_MEM`s kept for the GPU (labels 0x11e0d30488 …
  0x11e0d31360, reference 1) read 0xdeadbeef, 0xbe0ef5fc, 0xbeb0240 … at the timeout — the values the compute passes
  would have replaced: **the title's compute work never ran, the CP waited for it, the ring timed out without a fault**,
  and the reset failed (bc5-gpu-watch rebooted the box). The devcoredump agrees: SEs idle, no fault, `CP_IB1_BUFSZ` 0
  (the IB fetched to its end), the ME at a wait.

*So the three builds died of the same cause, with the fault as a side effect:* each replaced the base the CP really
had (the one register, carried from the previous job or set by the conversion right before) with a base the backend
inferred, and acted on the inference — polls at it (v1, v2: faults when the inferred page was a guard), or NOPs when it
was not mapped (v1, 0346: the title's and the host's compute work dropped by the thousand, then a CP wait that nothing
satisfies). The shared build never infers: a dispatch without a `SET_BASE` in its IB runs on whatever the register holds,
and that is right whenever the title set it in an earlier buffer.

**Verdict.** 0346 as built is withdrawn, and so is the per-type tracking in `indirect_check` (reverted at the next
step). The model that fits every dump: **one base-1 register, set by `SET_BASE` index 1 of either type, read by
`DISPATCH_INDIRECT` of either type, carried across jobs in ring order.** The fix for the 12:52 class, third version, to be
written before any build: track that one register across GFX-ring jobs (the host's conversion `SET_BASE`s included: they
are in the IBs); **leave every dispatch alone while the register is non-zero** (the CP's read is the title's or the
conversion's own — no inference, no poll at an inferred address, no NOP); only when the register is **0 at the dispatch**
— the title's explicit zeroing, the refit's case, where the CP would read a bare offset and fault — resolve window +
offset, verify (a real mapping, a CPU read, sane counts) and rewrite `SET_BASE(page) / dispatch / SET_BASE(0)`, else NOP
that one dispatch. The unit tests change accordingly (a compute-type `SET_BASE` serves a graphics-type dispatch; the
zero pair then a dispatch is the only rewritten case; a non-zero carried register leaves the dispatch untouched). Before
the box: the harness replays every dump above with the third version and must show zero changes except in 12:52's chain.

**The third version (2026-10-27 ~17:00, laptop only; not built for the box).** `host_indirect` now tracks the one
register: `Register{base, zeroed}` carried by `Device` across GFX-ring jobs (`impl_->hi_reg`), updated by every
`SET_BASE` index 1 of either type in the IB (the host's conversions included); `indirect_check` and its test are back
to main's single base. For each GFX-form `DISPATCH_INDIRECT`: register non-zero → left (`NonZero`); register 0 but no
`SET_BASE 0` ever seen → left (`NeverSet`); register 0 by an explicit zeroing → candidate window + offset, verified
(`region_of` over the shared and userptr mappings, a CPU read of the 12 bytes, the sanity limits) and rewritten
`SET_BASE(type) = page / dispatch offset = address − page / SET_BASE(type) = 0`, else that one dispatch NOP-ed with its
reason. `rewrite_verified` goes through `insert_before` (COND_EXEC counts grow; on a 14-bit overflow the rewrites become
NOPs, `nop_on_overflow`). Catch2: 4 cases (the refit's dispatch after the zeroing, in the same IB and carried; the
conversion pair / a carried non-zero register / never set → unchanged IB; the four refusals; the overflow). The switch
and the journal lines are unchanged (`BC5_DIRECT_HOST_INDIRECT`, `experiment 0346 rewrite|drop: … register 0 after the
title's zeroing …`).

**The gate (the harness, MSVC, over the 10 private dumps in submission order, the register "never set" at the first;
main d0c2668's backend against the third version; `diff` restricted to the packet lines and the `check:` lines, the
harness's own per-dispatch report excluded):**

| play | dump | third version: left non-zero / never set / rewritten / dropped | check (main = third version) | differing packet lines |
|---|---|---|---|---|
| 12:37 | acb #76004 (2,605 dw) | 45 / 0 / 0 / 0 | checked 45, unbased 0 | 0 |
| 12:37 | dcb #76005 (17,748 dw) | 0 / 0 / 0 / 0 | checked 46 | 0 |
| 12:52 | dcb #48055 (30,221 dw) | 0 / **435** / 0 / 0 | checked 141, unbased 435 | 0 |
| 12:52 | acb #48056 (4 dw) | 0 / 0 / 0 / 0 | 0 | 0 |
| 13:27 | dcb #81041 (98,099 dw) | 1,490 / 5,009 / 0 / 0 | checked 1,490, unbased 5,009 | 0 |
| 13:27 | acb #81042 (1,318 dw) | 0 / 0 / 0 / 0 | 0 | 0 |
| 14:23 | dcb #90425 (106,950 dw) | 2,706 / 1,045 / 0 / 0 | checked 3,050, unbased 1,045 | 0 |
| 14:23 | acb #90426 (4 dw) | 0 / 0 / 0 / 0 | 0 | 0 |
| 15:34 | acb #22813 (1,990 dw) | 19 / 0 / 0 / 0 | checked 19 | 0 |
| 15:34 | dcb #22816 (10,171 dw) | 0 / 0 / 0 / 0 | checked 23 | 0 |

Zero changes in every dump, the 12:52 chain included — because the dumps do not carry the title's zeroing pair (it is
in the buffer before 12:52's dcb #48055, F416), so the harness sees the register as "never set" and leaves the 435
alone. With the zeroing asserted for 12:52 (`--zeroed`, the register 0 and zeroed at the dump's start, the window
0x1100000000 learned from 12:37's bases): **435 rewrites, 0 drops, every one program 0x90997a500 (gfx type)**, the
first at dword 74 (offset 0x9bce4d80 → 0x119bce4d80, page 0x119bce4000), the last at dword 4,850 (offset 0x9c1b2b80
→ 0x119c1b2b80, page 0x119c1b2000), 205 distinct pages; the check then sees 576 checked (the 435 with the staircase),
0 unbased; the other 9 dumps unchanged. Offline every page is "mapped" and the reader returns 1 1 1: on the box the
pages beyond the title's real mappings would be NOP-ed, not rewritten, and the counts come from the CPU read.
*Residual risk, which the dumps cannot settle:* `--zeroed` asserted for 13:27 / 14:23 would also rewrite their 5,009 /
1,045 leading "never set" dispatches (small offsets in the 0x1100000000 window: the BVH chain's converted compute work
before its own `SET_BASE`) — so if the title's zeroing pair ever precedes a buffer whose dispatches rely on the register
being set later in ring order, the rule would touch them too. In the five plays the zeroing is seen only right before
the refit (12:52), where the CP really reads the bare offset.

**Result — the third version on the box (2026-10-27 16:02–16:27, the supervisor's GO, the maintainer away).** Build
3c3eddd3 (the shared objects ddfb9456 relinked with the private archive 4ba6ec78 of a909365; 0 warnings; Catch2 64
cases / 32,412 assertions pass), `BC5_DIRECT_HOST_INDIRECT=learn:1100000000`, one ring, both 0341 guards, the S6N route,
the live saves compared only, the kernel log streamed to the laptop (`raw/R1v3-kernel-stream.txt`,
`raw/R2v3-kernel-stream.txt`: no amdgpu line in either).

| run | RT | result | dispatches seen | left non-zero / never set / rewritten / dropped | flips |
|---|---|---|---|---|---|
| R1v3 16:03–16:13 | off | **pass** (600 s; 0 crash, kernel, TIMEOUT, devcoredump lines; 4,658 RT-off drop lines) | 1,043,388 | 1,043,388 / 0 / 0 / 0 | 18,822 / 596.6 s = 31.5/s, steady ~33.5 |
| R2v3 16:16–16:27 | on | **pass** (600 s; 0 crash, kernel, TIMEOUT, probe, devcoredump lines; 0 RT-off lines) | 11,730,827 | 11,730,827 / 0 / 0 / 0 | 18,362 / 596.6 s = 30.8/s, steady ~32.5 |

Both runs clean, and both with the register non-zero at every dispatch: the title never zeroed the register on the
S6N route in 600 s, RT on or off, so the 12:52 class (the zeroing pair before the refit 0x90997a500) was not exercised;
hang 1 did not occur either (nor in 0341 R2). The third version is harmless on this chain and still unproven against
hang 2, which needs the maintainer's play through the shortcut.

*The flips.* 31.5 and 30.8/s against 36.4 (0342 R1), 36.6 (0341 R2), 36.9 / 38.6 (0339) on the same chain: ~15 %
below. The journals' frame profiles over the steady state (t > 200 s, averaged over every `frame profile` line):

| run | prepare / frame | filter / frame (the bucket the 0346 pass is timed in) |
|---|---|---|
| 0342 R1 (RT off, 36.4/s), journal play-20261027-1227 | 1.34 ms | 0.47 ms |
| 0346 v3 R1 (RT off, 31.5/s), journal play-20261027-1603 | 2.55 ms | 1.70 ms |

The whole increase is the 0346 pass, and in the code it is not the walk (one linear pass over the IB, like the
filter's, needed on every IB to track the register through the `SET_BASE`s of either type) but the mapping table:
every GFX-ring job copied and sorted the device's ~19,400 userptr and shared mappings before the walk, ~118,000 times
in 600 s. Commit a98c8b2 builds the table only when a dispatch is a candidate (the first walk runs against no region;
a candidate shows as "not a real mapping" and the walk is re-run with the table), which leaves the walk alone on the
common path. Confirmed below with the same two runs on that build.

**Result — the lazy mapping table on the box (16:27–16:49).** Build cc0d24ce (the shared objects ddfb9456 + the
private archive ad7c2cb0 of a98c8b2; 0 warnings; Catch2 64 cases / 32,412 assertions pass), the same chain, the kernel
log streamed (`raw/R1v3b-kernel-stream.txt`, `raw/R2v3b-kernel-stream.txt`: no amdgpu line).

| run | RT | result | dispatches seen (all left, register non-zero) | flips | prepare / filter per frame (t > 200 s) |
|---|---|---|---|---|---|
| R1v3b 16:28–16:38 | off | **pass** (600 s; 0 crash, kernel, TIMEOUT, devcoredump lines) | 1,203,812 | 21,580 / 597.0 s = 36.1/s, steady ~38.5 | 1.45 / 0.54 ms |
| R2v3b 16:39–16:49 | on | **pass** (600 s; 0 crash, kernel, TIMEOUT, probe, devcoredump lines) | 14,083,430 | 21,776 / 596.4 s = 36.5/s, steady ~39 | 1.39 / 0.53 ms |

The flips are back in the known spread (0342 R1 36.4, 0341 R2 36.6 RT on, 0339 38.6) and the walk costs ~0.07 ms per
frame in the filter bucket. Again 0 rewritten, 0 dropped, 0 never-set: the zeroing is not on the S6N route.

**Verdict.** The third version (a909365 + a98c8b2) is clean on the regression chain with RT off and on, 600 s each,
at the shared build's speed, and touches nothing while the title's base register is non-zero. Whether it prevents hang
2 is untested until the title zeroes the register again, which happened only in the maintainer's play (12:52, F416):
the test shortcut **"BC5 emulator (test 0346)"** on the box's desktop runs `kyty_emulator` cc0d24ce through
`~/bc5-work/exp0346/play-pkg-0346t.sh` (md5 3e1b690c: the integrated launcher 5b469087 with
`BC5_DIRECT_HOST_INDIRECT=learn:1100000000` after the settings loop and a log per start in `~/bc5-work/exp0346/play/`;
RT on from the shared `input.cfg` 30dd586e). What to read after a play: the `experiment 0346 rewrite|drop` lines in
that log (program, window + offset, page, counts, reason) and the close summary; a rewrite of 0x90997a500 followed by
a clean continuation is the result this experiment wants, a NOP with its reason is the next question. Hang 1 (the
looping small dispatch of the build chain, ring reset succeeds) is outside this experiment. Nothing shared was changed
(launcher 5b469087, input.cfg 30dd586e, the shared builds ddfb9456 / 03337c24 / 44ba4435 as they were).
