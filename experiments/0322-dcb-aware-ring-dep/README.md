# 0322 — the dcb-aware ordering: a cross-ring dependency for refused compute buffers and for graphics buffers that dispatch

**Question.** Exp 0321: an ordering between the kernel rings removes the F332-class hang of the refusal build (RT on,
the BVH compaction on), but it has to cover the title's own graphics buffers — `BC5_DIRECT_RING_DEPS=dcb` (every GFX job
after the compute rings' last jobs) ran 2 × 600 s clean at the one-ring flip rate (35.4/s), while the dependency only
for the compute buffers exp 0290's refusal moves to the GFX ring hung at 127 s. The title submits part of the RT build as
direct dispatches in its dcbs, and those read the count passes' output from compute ring 0. Does the dependency on the
refused compute buffers **and** on the dcbs that carry a dispatch — the draw-only dcbs left side by side with the compute
rings — remove the hang, and at what flip rate between 35.4/s (dcb-wide) and 40.6/s (two rings, no compaction)?

**Setup.** `patch0322.py` on the tree's `bc5LleAgc.cpp` (md5 5bccbb80), 5 edits on top of 0321's design: a thread-local
flag cleared at `submit_now`'s start and set in the filter's packet walk on a type-3 op 0x15/0x16; `x0322::arm(kind,
qring)` before `g_dev->submit` (and the EFAULT retry) sets `Device::set_ring_deps(base | 2)` — exp 0129's kernel CS
dependency on each compute ring's last fence, no CPU wait — for a compute buffer on the GFX ring or a dcb with the flag,
restored right after the call (under `g_dev_mutex`); a dcb without the flag is skipped and counted. A `ring deps (exp
0322)` line per second: dependencies by kind (refused acb / dcb with a dispatch), draw-only dcbs skipped, the compute-ring
job and refusal counters. `BC5_DIRECT_RING_DEPS_AWARE=1` switches it on. `build0322.sh` (one unit + relink against the
shared objects d02f4696 and exp 0290's archive 825ae1d1), `s6n0322.sh` (exp 0306's chain: RT on, compaction on, the
launcher's `BC5_DIRECT_COMPUTE_RING=0`, private wd, environ checked for AWARE=1 and COMPUTE_RING=0; the 180-s marker
check now looks for this binary's own `ring deps (exp 0322)` line — exp 0321 S4 was stopped by the old check for exp
0302's descriptor lines), `stream0322.sh`. 2 × 600 s, the maintainer's yes: "Zgoda na test wersji pośredniej (zależność
dla odrzuconych buforów + buforów rysowania z dispatchami), prywatny build, ~25 min."

**Arms.** A: the split, no ordering — 11/11 hangs at 112–118 s today. B: 0320, one ring — 2/2 clean, 36.0 / 35.3 flips/s.
C: 0321 dcb-wide — 2/2 clean, 35.4 flips/s, windows 50–90 s 315/326/296/251. D: 0321 refused-only — hang at 127 s,
windows 305/342/324/286 before it. E: this run.

**Readings.** E clean 2 × 600 s with flips above C's → the candidate for the shared build at that cost (the per-second
line says what share of dcbs carried the dependency). E clean at C's flips → most dcbs dispatch, and the dcb-wide form is
as good. E hanging at ~2 min → a GFX job without a dispatch (or one the walk did not cover) reads the compute ring's
output — the draw-only dcbs are not free either; the dcb-wide form stays the candidate.

**Result (2026-10-25; binary 2a5210db = out 7d77cfe9, built 19:12 against the shared objects d02f4696 and exp 0290's
archive 825ae1d1; launcher from play-pkg.sh bb51caf2 with the 0306 edits; both environs `BC5_DIRECT_RING_DEPS_AWARE=1
BC5_DIRECT_COMPUTE_RING=0 BC5_DIRECT_SKIP_PGM=0 KYTY_BC5_RT=1`; `raw/S1-*`, `raw/S2-*`, `raw/journal-stream.txt.gz`,
`raw/kernel-stream.txt.gz`; the journals `~/bc5-data/captures/play-20261025-1913` and `-1923`, ~195 MB each, private).**
S1 (19:13:05–19:23:16): PASS at 600 s — 0 crash, 0 kernel amdgpu, 0 TIMEOUT lines, live saves bb14b6dd35b644ff
unchanged. The counts over the run: 110,837 compute buffers on the GFX ring and 176,684 dcbs with a dispatch given the
dependency, 58,311 draw-only dcbs left free (≈25 % of the dcbs); 447,556 compute-ring jobs and 181,075 refusals — the two
rings in use (177 `compute ring:` lines; this chain, derived from exp 0306's, takes no fdinfo snapshot, the counters are
the proof). Flips 20,868 in 600 s, mean 35.6/s, windows 50–90 s 312/348/342/247.
S2 (19:23:16–19:33:35): PASS at 600 s — the same zeros, live saves unchanged, the lock released by the chain. Counts:
109,183 refused compute buffers and 175,246 dcbs with a dispatch given the dependency, 58,984 draw-only dcbs free;
444,666 compute-ring jobs, 180,103 refusals; 176 `compute ring:` lines. Flips 20,742, mean 35.4/s, windows 50–90 s
302/292/305/257.

| run | 50 | 60 | 70 | 80 | total | mean 40–590 s |
|---|---|---|---|---|---|---|
| 0322 S1 (dcb-aware) | 312 | 348 | 342 | 247 | 20,868 | 35.6/s |
| 0322 S2 | 302 | 292 | 305 | 257 | 20,742 | 35.4/s |
| 0321 S1/S2 (dcb-wide) | 315 / 298 | 326 / 327 | 296 / 318 | 251 / 261 | 20,733 | 35.4/s |
| 0320 S1 (one ring) | 284 | 287 | 289 | 243 | 21,152 | 36.0/s |
| 0306 S1 (two rings, hang) | 466 | 443 | 458 | 370 | — | — |
| 0302 S1 (two rings, no compaction) | 484 | 470 | 485 | 397 | 23,729 | 40.6/s |

**Verdict.** The dcb-aware ordering removes the hang (2 × 600 s clean; with 0320 and 0321 that is 7 × 600 s clean today
against 11 of 11 hangs at ~2 min without an ordering) at the same cost as the dcb-wide form: three quarters of the
title's graphics buffers carry a dispatch and wait, the draw-only quarter is not where the time goes. So the fix for the
shared build is the simplest form, `BC5_DIRECT_RING_DEPS=dcb` (exp 0129's switch, no new code), at about the one-ring
flip rate — accepted by the maintainer for now ("ok - zastosuj zmiany - pozniej będziemy myslec nad wydajnoscia");
integration is exp 0323. The patch of this experiment stays as the reference for a finer ordering later (the cost is in
the dispatching dcbs themselves, so the next saving would have to come from which compute jobs they wait for, not from
which dcbs wait).
