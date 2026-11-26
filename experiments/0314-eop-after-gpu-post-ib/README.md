# 0314 — the soft CP's early EOP event vs the title's struct-slot reuse: `BC5_DIRECT_SOFTCP_POST_IB=1` on the compaction-on route

**Question.** Exp 0313 proved that the count-pass record the leaf builder reads as floats (F332 with the compaction on,
exp 0306) is overwritten by the title's own CPU: a memcpy of more than 256 bytes re-initialising a recycled per-tree
struct slot (a ring of about 29), while the GPU, made late by the compaction, has not run that slot's leaf builder yet.
The title reuses a slot when it believes the GPU is done with it. On this host one completion signal comes early: with
`BC5_DIRECT_CHAIN=2` (the second title's settings) `submit_ib_packet` queues each IB-packet submission's soft CP in
`t_soft_pending` with `post = BC5_DIRECT_SOFTCP_POST_IB` (unset → false), and `soft_posts_end()` then runs
`SoftCp::submit` at the chain's submission — its RELEASE_MEMs' `fire_eop` delivers the EVFILT_GRAPHICS events (idents
0x40, 0x48, 0x46, 0 — the title's `GpuDevice::EopEq` queues) when the host submits, not when the GPU finishes. F143
(exp 0083) documented exactly this and added `BC5_DIRECT_SOFTCP_POST_IB=1` ("runs the soft CP of an IB-packet submission
once its GPU job has completed, so that the EVFILT_GRAPHICS events and the writes of dropped packets come when the GPU
is done, not at submission"); it stayed off. Does the hang go away with the events delivered after the GPU job?

**Setup.** `s6n0314.sh` = exp 0306's chain (`s6n0306.sh`: RT on through the private input configuration, the derived
launcher, the private wd with its own `_SaveData`, the live saves compared only, exp 0302's binary 39440597, the
compaction on) with one added environment line, `BC5_DIRECT_SOFTCP_POST_IB=1`, checked in the emulator's environ with
the others. 2 × 600 s. Arm A (control) is today's nine F332 hangs at 112–118 s on this chain: 0306 (2), 0308 (2), 0310
(3), 0313 (2). `stream0314.sh` streams the kernel log and the journal.

**Readings.** 2 × 600 s clean → the early EOP event is the signal the title recycles on, and POST_IB is the fix
candidate (then its side effects are measured: F143's menu, the flip rate, exp 0083's reasons for leaving it off). The
hang at ~2 min as before → the title does not wait on the EOP event for the slot (then: the label writes it polls, or
the compaction's own output — exp 0313c would name the title's caller). A hang much later → partial: the event is one
of the signals.

**Result (2026-10-25 15:45:39–15:50:36; s6n0314.sh 248f92a9; binary 39440597; launcher derived from play-pkg.sh; both
runs' environ: `KYTY_BC5_RT=1 BC5_DIRECT_SKIP_PGM=0 BC5_DIRECT_SOFTCP_POST_IB=1 BC5_DIRECT_TIMEOUT_PROBE=1
BC5_DIRECT_MEC_INDIRECT=1`; `raw/S1-*`, `raw/S2-*`, `raw/journal-stream-S2.txt.gz`, `raw/kernel-stream.txt` — S1's
laptop stream was lost to a path slip and stays on the box, `~/bc5-data/captures/play-20261025-1545/gc/direct.log`).**
Negative, 2/2: S1 the F332 hang at 116 s (`gfx_0.0.0` reset succeeded, "device wedged, but no recovery needed"), S2 at
113 s (`comp_1.1.0` reset succeeded); 0 crash lines, 2 TIMEOUT lines each, the 0302 descriptor check's BAD SLOT line as
in 0306; live saves 8289704a9338a118 unchanged; the chain released the lock itself. Devcoredumps:
`20261025-154734-devcd8.txt`, `20261025-155002-devcd9.txt` (the maintainer's udev copy; cited by path only).

POST_IB changed nothing visible. Flips per 10-s window (the journal's `timing: … flip` lines), 40–100 s:

| run | 40 | 50 | 60 | 70 | 80 | 90 | 100 | total |
|---|---|---|---|---|---|---|---|---|
| 0314 S1 (POST_IB=1, compaction on) | 331 | 452 | 465 | 442 | 366 | 139 | 214 | 3,427 in 137 s |
| 0314 S2 | 353 | 427 | 454 | 459 | 371 | 138 | 159 | 3,342 in 134 s |
| 0306 S1 (compaction on, for comparison, 50–90 s) | — | 466 | 443 | 458 | 370 | — | — | 3,444 in 137 s |

The frames before the hang: 23.5–24.4 ms since the last flip, game thread 4–6 ms inside the host, `fence 0.0, cap 0.0,
label waits ≤ 0.7, event waits 0.0` — the same profile as 0306's, and no F143-type side effect to measure.

**Two facts from S1's journal for the next step.** (1) The GPU wedged at the CPU's frontier: the TIMEOUT'd submissions
are #123138 (dcb, 29,694 dwords) and #123134 (acb, 3,748 dwords), the newest ones (the title submits ~23 buffers per
frame: #120320 at 108.0 s); the in-flight cap (`BC5_DIRECT_MAX_IN_FLIGHT`, 12) never engaged. So the slot reuse is not
an accumulated lag over the ~29-slot ring: the title reuses a slot within about a frame of submitting its build, and the
compaction (GPU busy 14–16 ms per 24-ms frame against 3–4 ms without) widens the chain's window enough for the memcpy to
land before the leaf builder. (2) The game thread waits nothing in the host — whatever the title checks before reusing
the slot is satisfied at once here.

**Verdict.** The soft CP's EOP event at submission (and the dropped-packet writes, which POST_IB defers too) is not the
signal the title recycles its per-tree struct slot on: with `BC5_DIRECT_SOFTCP_POST_IB=1` the hang comes at the same
time, 2/2. The signal is still unknown; the next experiment extends exp 0313's trap to log, at each store into an armed
struct, whether the GPU job that armed it (the count pass's acb, by submit number) has completed — and, as a fix test, to
hold the title's store until it has (`BC5_DIRECT_WRITE_TRAP=2`): the console's semantics, measured by the stall.
