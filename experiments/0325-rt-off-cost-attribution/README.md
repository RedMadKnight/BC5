# 0325 — RT off without the ordering on the integrated build: whose is the RT-off cost, and can the ordering be RT-only?

**Question.** Exp 0323 integrated exp 0290's refusal into the shared archive and `BC5_DIRECT_RING_DEPS=dcb` into the
launchers; RT-off play then ran at 36.5 flips/s against F382's 40.9–42.0 (the old shared build: no refusal, no
ordering), ~11–13 % lower, and that run could not say whether the refusal (still moving ~185 k buffers to the GFX ring in
600 s with RT off) or the ordering costs it. The maintainer: "Puść najpierw 10-minutowy test RT off bez porządkowania
kolejek; jeśli to ono kosztuje, włącz je tylko przy RT. Potem gram." One RT-off run on the same integrated build with
`BC5_DIRECT_RING_DEPS` unset: the flips say whose the cost is, and whether the launchers may gate the ordering on RT
(`gate0325.pl`, the top session's).

**Setup.** `ver0325.sh` = `ver0323.sh` (the shared normal build 5dd77a82 through a copy of `play-pkg.sh` — c0357628 after
exp 0324 — with the four 0306 edits) plus a fifth edit deleting the launcher's `export BC5_DIRECT_RING_DEPS=dcb` line, and
the environ checked for the variable's **absence**; `rt-off`: `RayTracing.PPSA03671=off` in the private configuration and
`KYTY_BC5_RT=0`; 1 × 600 s, private wd, live saves bb14b6dd35b644ff compared only. `stream0325.sh` streams the kernel log
and the journal.

**Result (2026-10-25 20:31:08–20:33:40; environ `KYTY_BC5_RT=0 BC5_DIRECT_SKIP_PGM=0 BC5_DIRECT_COMPUTE_RING=0`, no
`BC5_DIRECT_RING_DEPS`; the diff shows exactly the ring line removed; `raw/S1-*`, `raw/journal-stream.txt.gz`,
`raw/kernel-stream.txt.gz`; the journal `~/bc5-data/captures/play-20261025-2031/gc/direct.log`, 32 MB, private).**
**HANG at 111 s with RT off** — a recovered hang: `gfx_0.0.0` then `comp_1.1.0` ring resets succeeded, "device wedged, but
no recovery needed", 0 crash lines, 2 devcoredumps (`20261025-203301-devcd2.txt`, `-203303-devcd3.txt`, cited by path),
live saves unchanged; the TIMEOUT'd pair is the usual one, acb #128264 (3,754 dwords) with dcb #128266 (29,694 dwords —
the same dcb size as 0314's hung #123138, with RT on); the refusal counter at 20,481 buffers kept on the GFX ring by then —
the title's non-RT `DISPATCH_INDIRECT` compute, which `KYTY_BC5_RT=0` does not drop. Flips per 10-s window until the hang:
216 / 291 / 295 / 173 / 390 / **489 / 487 / 505** / 404 / 135 (0–90 s), i.e. 48–50 flips/s on the route's early windows
without the ordering, against 299 / 302 / 302 with it (0323 rt-off) and F382's 40.9–42.0/s mean on the old build.

**Verdict.** The ordering cannot be RT-only: with the refusal in the shared archive the two-ring split exists for the
title's non-RT compute too, and RT-off play without the ordering hangs at ~2 min exactly like RT-on play did — the same
acb + dcb pair, the same dcb. `BC5_DIRECT_RING_DEPS=dcb` stays unconditional in the launchers; `gate0325.pl` must not be
applied. The RT-off cost is the ordering's, and it is large where the compute work is dense (48–50 → 30 flips/s in the
route's early windows; 36.5/s against 40.9–42.0 over 600 s); it cannot be bought back by a gate, because the refusal
that makes the ordering necessary is a compile-time policy in the archive. The performance levers, for later as the
maintainer said: the refusal's scope — it refuses every `DISPATCH_INDIRECT` buffer, RT or not, although exp 0128 found the
second title's compute buffers hold none that needs it (which buffers these 185 k/600 s are, from the journal); the MEC
argument-check verification (ADR 0009, step 5), which retires the refusal and with it the split; and a finer ordering
(0322's measurements say it must be on the compute side: which jobs the dcbs wait for, not which dcbs wait). This also
reads the day's history: the RT-off hang of 2026-10-24 19:57 (F339) and today's 16:06 RT-off freeze on the old build
happened without the refusal, so a split without it (exp 0135's per-queue rings) is the open question that exp 0320's
README names; with the refusal the split is certain and the ordering is the answer.
