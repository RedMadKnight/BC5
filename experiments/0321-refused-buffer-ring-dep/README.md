# 0321 — the ordering fix: a cross-ring dependency for each compute buffer refused to the GFX ring

**Question.** Exp 0320 showed the mechanism of today's recoverable F332-class hang (RT on, the BVH compaction on, the
refusal build): the BVH build is split between two kernel rings with nothing ordering them — the count-pass chains on
compute ring 0, the leaf builder's `DISPATCH_INDIRECT` buffers on the GFX ring by exp 0290's refusal (exp 0316) — and the
hang goes away with every compute buffer on the GFX ring (2 × 600 s clean against 11/11 hangs at ~2 min), at a price of
~11 % of the flips over 600 s and a third in the build-heavy windows. Is an **ordering** enough, with the rest of the
compute work left side by side: does the hang go away when each buffer refused to the GFX ring starts only after the
compute rings' jobs submitted before it, and what does that cost?

**Setup.** `patch0321.py` on the tree's `bc5LleAgc.cpp` (md5 5bccbb80), 3 edits: `x0321::arm(kind, qring)` right before
`g_dev->submit` in `submit_now` (and before the EFAULT retry) — for a compute buffer (`acb…`) submitted to the GFX ring
while compute rings are in use (`BC5_DIRECT_COMPUTE_RING >= 0`), i.e. a buffer the refusal kept off the compute ring (or an
acb head/tail piece), the device's dependency mask is set to "GFX after every compute ring's last job"
(`Device::set_ring_deps(base | 2)`: exp 0129's kernel CS dependency, `amdgpu_cs_request::dependencies` with each compute
ring's last fence — the scheduler starts the job after them, no CPU wait) and restored to `BC5_DIRECT_RING_DEPS`'s value
right after the call; `submit_now` holds `g_dev_mutex` across it, so no other submission sees the mask. Every other job —
the title's dcbs, the compute-ring chains — runs as before, side by side. A `ring deps (exp 0321)` line per second: the
dependencies added in that second and in all, the compute-ring job and refusal counters. `BC5_DIRECT_RING_DEPS_REFUSED=1`
switches it on. `build0321.sh` (one unit + relink against the shared objects, d02f4696 accepted, and exp 0290's archive
825ae1d1 — the refusal is what makes the buffers land on GFX), `s6n0321.sh` (exp 0306's chain: RT on, compaction on, the
launcher's `BC5_DIRECT_COMPUTE_RING=0`, private wd; the environ checked for REFUSED=1 and COMPUTE_RING=0; play-pkg.sh
bb51caf2 accepted), `stream0321.sh`. 2 × 600 s.

**Arms.** A: the split, no ordering — 11/11 hangs at 112–118 s on this chain today (0306 ×2, 0308 ×2, 0310 ×3, 0313 ×2,
0314 ×2). B: 0320, one ring — 2/2 clean, 36.0 / 35.3 flips/s, early windows 284–289 per 10 s. C: this run.

**Readings.** C clean 2 × 600 s with flips between B's and 0302's 40.6/s → the ordering is the fix candidate for the shared
build (the dependency only for refused buffers; a backend flag or this host-side mask toggle), and the cost is the
difference to 0302. C clean with B's flips → the dependency serialises as much as one ring (the compute rings are rarely
idle when a refused buffer comes); then option (b) of 0320's write-up (refusing the count-pass chains to GFX too) is the
next. C hanging at ~2 min → the dependency did not order the pair (the count pass's chain is submitted *after* the leaf
builder's buffer, or on a ring the mask does not cover); then the `ring deps` counts against the arming numbers of 0316
say which, and the fix moves to the submission order itself.

**Result — the environment-line form (`s6n0321.sh`: the 0306 chain on exp 0302's binary 39440597 with
`export BC5_DIRECT_RING_DEPS=dcb` appended to the derived launcher after its `BC5_DIRECT_COMPUTE_RING=0` line — every
GFX-ring job starts after the compute rings' last jobs; both checked in the environ; the private input configuration
without the MangoHud line, as exp 0320; `raw/S1-*`, `raw/S2-*`, `raw/journal-stream-env.txt.gz`,
`raw/kernel-stream-env.txt.gz`; 2026-10-25 18:34:54–18:55:17).** PASS, 2 of 2: S1 and S2 each 600 s with 0 crash,
0 kernel amdgpu and 0 TIMEOUT lines, live saves bb14b6dd35b644ff unchanged, the lock released by the chain. The two rings
were in use: fdinfo at ~121 s shows `drm-engine-compute` 32.0 s / 33.5 s and `drm-engine-gfx` 54.6 s / 56.2 s; 175
`compute ring:` lines per run, the refusal counter at 178,177 buffers kept on the GFX ring in S1's 600 s (≈300/s). So an
ordering alone — with the compute rings left in place — removes the hang: together with exp 0320 that is 4 × 600 s clean
today against 11 of 11 hangs at 112–118 s without it. The price of this coarse form is the one-ring price: flips 20,733 in
600 s in both runs, mean 35.4/s (0320: 36.0 / 35.3; 0302: 40.6), windows 50–90 s 315/326/296/251 (S1) and 298/327/318/261
(S2) against 0320's 284/287/289/243 and 0306's 466/443/458/370 — the dcbs waiting for the compute rings on every
submission serialise almost as much as one ring.

**Result — the refined form (`s6n0321b.sh`: exp 0321's own binary 879a7e86 = out 2f8759c4, built 18:55:57–18:56:24
against the shared objects d02f4696 and exp 0290's archive 825ae1d1; `BC5_DIRECT_RING_DEPS_REFUSED=1`,
`BC5_DIRECT_COMPUTE_RING=0`, the dependency only for compute buffers submitted to the GFX ring; tags S3/S4;
`raw/S3-*`, `raw/S4-*`, `raw/journal-stream.txt.gz`, `raw/kernel-stream.txt.gz`; on the maintainer's "moja zgoda
wystarczy - przekaż że ruszasz z pracami" in this session, after the env-line chain was clean).** The switch is live from
the first frames: `ring deps (exp 0321): 34 compute buffers on the GFX ring given the compute rings' last jobs as
dependencies in the last 1.0 s (35 in all; 413 compute-ring jobs, 63 refusals so far)` — about 30 dependencies per second
at the menu, the compute ring running beside.

S3 (18:56:57–18:59:38): **HANG at 127 s** — a recovered `gfx_0.0.0` ring reset ("device wedged, but no recovery
needed"), 0 crash lines, 2 TIMEOUT lines — the usual pair, acb #116896 (3,923 dwords) and dcb #116902 (2,811 dwords) —
1 devcoredump (`~/bc5-data/captures/devcoredump/20261025-185902-devcd1.txt`, cited by path), live saves intact. The
dependencies were being added all along: 10,508 in 127 s (136–158 per second in the route; 17,576 refusals so far, 73,884
compute-ring jobs), journal `play-20261025-1856` (28.9 MB). Flips per 10-s window until the hang: 237/305/342/324/286
(40–80 s) — better than the dcb form's and 0320's, still far from 0306's 466/443/458/370. S4 (18:59:38–19:02:50): no hang
in 180 s (flips 260/298/311/345/238), then **stopped by the chain's own 180-s marker check**, a script defect: the chain
derived from exp 0306's looks for exp 0302's descriptor lines, which this binary (the bare tree + patch0321) does not
write; 21,293 dependencies in 180 s. So the refined form is 1 hang in 1 full-length attempt, at the usual time.

**Verdict.** An ordering alone removes the hang, but it has to cover the **title's own dcbs**, not only the compute
buffers the refusal moved to the GFX ring: `BC5_DIRECT_RING_DEPS=dcb` (every GFX job after the compute rings' last
jobs) ran 2 × 600 s clean on two rings, while the dependency for refused compute buffers only hung at 127 s like the
arm-A runs. The job that reads the compute ring's output early is therefore (also) a dcb — consistent with every hung
pair of the day being an acb with a dcb, and with the descriptor check's BAD SLOT lines naming "dcb dispatch op 15":
the title submits part of the RT build (direct dispatches) in its graphics buffers, and those must wait for the count
passes on compute ring 0 too. The fix candidate for the shared build is the dcb-wide dependency as it stands (cost: the
one-ring flip rate, ~35/s against 40.6/s), or, as the next experiment, a dcb-aware one — the dependency for refused
compute buffers and for dcbs that carry a dispatch (the filter already walks the opcodes; a flag set when it sees
op 0x15/0x16), leaving draw-only dcbs free — measured by the same chain and the flips. Either needs a new ask.
