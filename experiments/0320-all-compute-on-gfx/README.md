# 0320 — every compute buffer on the GFX ring: the unordered two-ring split of the BVH build as the F332 mechanism

**Question.** Exp 0316 run A showed where the BVH build chain of the second title actually runs on this host: every count
pass 0x909939400 is submitted by the ring thread's chains to **compute ring 0** (`BC5_DIRECT_COMPUTE_RING=0` in the
launcher; 1.19 M armings in 180 s, all `cq 1`, none refused), while the buffers holding the leaf builder's
`DISPATCH_INDIRECT` are **refused to the GFX ring** by exp 0290's policy (`compute ring: a compute buffer of … dwords
stays on the GFX ring (indirect dispatch …)`, one line per 1,024 refusals — 17 lines, ≈17 k buffers in 180 s). On the
console both sit on one in-order queue, so the title puts no wait between them; the host splits them across two rings
and orders nothing (the cross-ring machinery honours only the title's own label waits). The CPU writes the count record
only once, at the route's load (0316: 8 record-1 stores in a 4-s burst, none in the 176 s after) — so the floats the
leaf builder reads at the hang are the load-time template the count pass had not yet overwritten, i.e. the leaf builder
ran before its count pass. Does the hang go away when every compute buffer runs on the GFX ring, in submission order?

**Setup.** `s6n0320.sh` = exp 0306's chain (RT on, compaction on, the 0302 binary 39440597, private wd, live saves
compared only) with a fifth anchored launcher edit, `export BC5_DIRECT_COMPUTE_RING=-1` (`acb_ring()`: a negative value
returns `kGfxRing` for every compute buffer — the placement before F177/ADR 0009), checked in the environ (the run stops
if it is not −1). 2 × 600 s. Arm A (control): today's eleven F332 hangs at 112–118 s on this chain (0306 ×2, 0308 ×2,
0310 ×3, 0313 ×2, 0314 ×2). `stream0320.sh` streams the kernel log and the journal.

**Readings.** 2 × 600 s clean → the mechanism is the unordered split (count pass on compute, leaf builder on GFX); the
fix is an ordering, not a CPU-side wait: a cross-ring fence before a refused buffer (wait for the compute ring's last
job), or refusing the count-pass chains to GFX too (same ring, same order), measured against the one-ring cost (flips).
The hang at ~2 min as before → the rings are not it; the leaf builder's early read has another cause (then: the
submission order within the GFX ring between the refused buffer and the count-pass chain, from the journal). A hang much
later → partial.

**Proof that no compute-ring job ran.** Two things per run: (1) amdgpu's per-engine counters of the emulator's DRM fd
(`/proc/<pid>/fdinfo/*`: `drm-engine-gfx` and `drm-engine-compute`, nanoseconds of GPU time per engine), snapshotted at
120 s and just before the stop (`raw/<run>-fdinfo.txt`): with every buffer on the GFX ring `drm-engine-compute` must stay
at its start value while `drm-engine-gfx` grows; (2) the journal has no `compute ring:` line at all (with
`BC5_DIRECT_COMPUTE_RING=-1`, `acb_ring()` returns the GFX ring before the refusal policy runs, so neither the refusal
lines nor the "guest queue → its own compute ring" lines can appear), and the kernel's ring names in any hang line are
`gfx_0.0.0` only. The water session proved 0309's placement the same way.

**What the history says about the split (the supervisor's question).** The split by exp 0290's refusal is not the whole
story of F332. F332 itself (2026-10-24 17:47, exp 0265 S1, the shared build **without** the refusal) was one compute-ring
acb, #127637 of 786 dispatches, the first 200 of them `DISPATCH_INDIRECT` of 0x909939400 and 0x909936c00 — the count pass
and the leaf builder in **one buffer on one ring**, and the machine went down inside it (HANDOFF F332). So a one-ring
layout already produced the machine-down class; what the refusal changed is the outcome (six of six recoverable GFX-ring
timeouts at 112–123 s, F356) and, per exp 0316, the placement of the count-pass chains (compute ring 0) apart from the
leaf-builder buffers (GFX). Two readings fit the data: (a) the two-ring split is the mechanism of **today's** variant (the
refusal build, 11 recoverable hangs at 112–118 s with the compaction on) and F332 proper was a second, in-buffer problem of
the same work (exp 0300's per-dispatch sync did not cure it, F358's breadcrumb sync did once); (b) the split was already
there before the refusal — exp 0135's `BC5_DIRECT_COMPUTE_RINGS` gives a guest queue its own kernel ring after 64 buffers,
so two guest queues of the title can sit on two kernel rings without any refusal — and F332's one acb was the title's
build on one queue while the record it read came from another queue's chain. 0320 separates them: clean 2 × 600 s → the
hang needs the two rings (then (b) is checked by the fdinfo of a no-refusal run: did `comp_1.2.0` carry a second queue in
F332's run? its kernel lines say `gfx_0.0.0` then `comp_1.2.0`, two rings); a hang at ~2 min with one ring → the race is
inside the chain's order on one ring, and the split is not it.

**Result (2026-10-25; s6n0320.sh; binary 39440597; launcher play-pkg-0320.sh d780cb0d from play-pkg.sh bb51caf2, the
fifth edit `export BC5_DIRECT_COMPUTE_RING=-1 BC5_DIRECT_CROSS_RING_WAITS=all` in place of `=0` (`raw/play-pkg-0320.diff`);
both environs `KYTY_BC5_RT=1 BC5_DIRECT_SKIP_PGM=0 BC5_DIRECT_COMPUTE_RING=-1 BC5_DIRECT_TIMEOUT_PROBE=1
BC5_DIRECT_MEC_INDIRECT=1`; `raw/S1-*`, `raw/S2-*`, `raw/journal-stream.txt.gz`, `raw/kernel-stream.txt.gz`).** One false
start at 18:02:11 with no GPU work: exp 0302's binary, linked against the pre-MangoHud objects, rejects the line
`MangoHud.PPSA03671=on` of the maintainer's `input.cfg` (exit 65, "unknown control"; `raw/s6n0320-falsestart-1802.out`), so
the private input configuration is now derived without it. Then **PASS, 2 of 2**: S1 18:04:34–18:14:46 and S2
18:14:46–18:24:59, each 600 s with 0 crash, 0 kernel amdgpu and 0 TIMEOUT lines, 0 devcoredumps; live saves
bb14b6dd35b644ff unchanged; the lock released by the chain. Arm A on this exact chain today: 11 of 11 hangs at 112–118 s
(0306 ×2, 0308 ×2, 0310 ×3, 0313 ×2, 0314 ×2).

**The ring proof.** amdgpu's fdinfo of the emulator's DRM fds at ~121 s (`raw/S1-fdinfo.txt`, `raw/S2-fdinfo.txt`): only
`drm-engine-gfx` entries (70.0 s and 66.3 s of GPU time), no `drm-engine-compute` entry at all; 0 `compute ring:` lines in
either journal (the refusal and the per-queue ring lines cannot appear with `acb_ring()` returning the GFX ring first);
no kernel ring line of any kind.

**The price.** Flips per 10-s window (the journal's `timing: … flip` lines), the route's early windows and the 600-s mean:

| run | 40 | 50 | 60 | 70 | 80 | 90 | 100 | total | mean 40–590 s |
|---|---|---|---|---|---|---|---|---|---|
| 0320 S1 (one ring) | 211 | 284 | 287 | 289 | 243 | 140 | 211 | 21,152 | 36.0/s |
| 0320 S2 | 155 | 275 | 287 | 287 | 235 | 136 | 216 | 20,724 | 35.3/s |
| 0306 S1 (two rings, hang at ~110 s) | — | 466 | 443 | 458 | 370 | — | — | 3,444 in 137 s | — |
| 0302 S1 (two rings, compaction skipped) | — | 484 | 470 | 485 | 397 | — | — | 23,729 | 40.6/s |

The one-ring placement costs about a third of the frame rate in the windows where the builds are heaviest (28–29 flips/s
against 44–47) and ~11 % over the 600 s; the frames at 599 s are 24–25 ms as before.

**Verdict.** The hang goes away when every compute buffer runs on the GFX ring in submission order: 2 × 600 s clean
against 11 of 11 hangs at ~2 min with the split. The mechanism of today's recoverable F332-class hang (the refusal build,
RT on, the compaction on) is therefore **the unordered split of the BVH build between two kernel rings** — the count-pass
chains on compute ring 0, the leaf builder's `DISPATCH_INDIRECT` buffers on the GFX ring by exp 0290's refusal, with no
ordering between them, so a leaf builder can run before its count pass and read the load-time template (floats) as its
dispatch count (exp 0316). The fix is an **ordering in the host**, not this placement (too slow): either a cross-ring
dependency for a refused buffer (the GFX job waits for the compute ring's last job submitted before it — the kernel's
sync-object dependencies do exactly this), or refusing the count-pass chains to the GFX ring too (one ring for the build
family only, the other compute work staying on compute ring 0). Either one is a small change to `acb_ring()` /
`submit_now`'s dependency list, measured by this chain (2 × 600 s) and the flips. Whether the same split (two of the
title's queues on two kernel rings, exp 0135) also made the machine-down of 2026-10-24 (F332, no refusal) stays open — see
"What the history says" above; F332's kernel lines name two rings.

**The journals (private data, outside the repo, not trimmed).** `~/bc5-data/captures/play-20261025-1804/gc/direct.log`
(185,749,320 bytes, S1) and `~/bc5-data/captures/play-20261025-1814/gc/direct.log` (182,153,832 bytes, S2): exp 0302's
descriptor check writes a line per dispatch with a table (675,841 and 663,553 "snapshots"); the false start's journal is
`play-20261025-1802`. On the maintainer's cleanup list; nothing from them is needed in the repo beyond the counts above.

**Proposal — the ordering fix (a write-up, not a run; the submission path needs the maintainer's yes before any build).**
The hang needs the count-pass chain (compute ring 0) and the leaf-builder buffer (GFX, refused) to run unordered. Two ways
to order them, both inside the host's submission path:

- **(a) A cross-ring dependency for every buffer refused to the GFX ring: the GFX job waits for the compute ring's last
  job submitted before it.** The backend already has the mechanism — `Device::set_ring_deps(mask)` (`backend/include/bc5/
  direct.hpp`, exp 0129 / ADR 0009): bit 1 makes a GFX-ring job carry a CS dependency (`amdgpu_cs_request::dependencies`,
  the fence of each compute ring's last job, `backend/src/direct.cpp`) — a kernel scheduler dependency, no CPU wait —
  and `BC5_DIRECT_RING_DEPS=dcb` sets it from the environment. As it stands it applies to **every** GFX job (the title's
  dcbs too), so it is a coarser ordering than needed: the dcbs would wait for the compute ring on every submission. *Cost:*
  the GFX ring loses its overlap with the compute ring at every dcb — exp 0129 measured the two rings' overlap at +24–31 %
  on the start screen; the route would lose some of that, likely less than 0320's one-ring placement, which also
  serialises the compute work itself. *Measure:* the 0306 chain + `BC5_DIRECT_RING_DEPS=dcb`, 2 × 600 s, flips per 10-s
  window and the 600-s mean against 0320's 36.0/s (one ring) and 0302's 40.6/s (two rings, no compaction); hang or none.
  *Needs:* no build — an environment line in the derived launcher and an environ check; the proof is the journal's
  `queued` order plus the absence of hangs. If it holds and the cost is acceptable, the refined form is one line in the
  backend: apply the dependency only to **refused** buffers (`acb_ring()` returned GFX for an acb) and not to the title's
  dcbs — a new mask bit or a per-submission flag through `submit_now`, which is the change that needs the yes.
- **(b) Refusing the count-pass chains to the GFX ring as well.** `bc5::policy::compute_ring_refusal` (the backend
  policy, a constexpr flag + a reason string) gains a reason for an acb holding a direct dispatch of 0x909939400 (or any of
  `KYTY_BC5_RT_BUILD_PGM`'s family, the launcher's list) — the whole BVH build family on one ring in submission order,
  the title's other compute work (the ring thread's remaining chains) staying on compute ring 0. *Cost:* the build family's
  GPU time moves to GFX — in 0316's run A the count-pass chains were 1.19 M dispatches in 180 s, most of them at the load
  burst; in steady state the family is a fraction of the compute ring's work, so the overlap lost is smaller than (a)'s;
  but the chain buffers are large (thousands of dispatches each) and a GFX ring busy with them delays the draws. *Measure:*
  the same chain and the same three numbers; and the refusal counter (`compute ring: … stays on the GFX ring (…; N so
  far)`) with the new reason, to see what share moved. *Needs:* a backend change (the policy + its reason string, a
  private archive as exp 0290's) and a relink (~30 s), i.e. the maintainer's yes; 2 × 600 s on the box.

Order of trial: (a) first as the environment line (no build, one chain), because it answers "is an ordering enough" at
once; then (b) or the refined (a) as the candidate for the shared build, chosen by the flips. Neither touches the title's
data or the save path; both leave RT-off play as it is (the build family runs only with RT on).
