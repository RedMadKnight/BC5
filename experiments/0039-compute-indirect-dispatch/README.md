# 0039 — the compute IBs' indirect dispatches run on the GFX ring

**Question.** Experiment 0038 found that the second title's compute IBs carry `DISPATCH_INDIRECT`
in the compute-queue form, that the host had always dropped them, and that the title's GPU faults
(at about 210 s) most likely come from data those dispatches should have produced. Can they run
on the BC-250's GFX ring, and does the title then get past the faults?

**Setup.** As in 0038; the launchers here (`run-pkg.sh`, `play-pkg.sh`) now set
`BC5_DIRECT_MEC_INDIRECT=1 BC5_DIRECT_MEC_SKIP_PGM=909939900` for this title (`MEC=0` turns it
off in `run-pkg.sh`); `pkg-series.sh` runs and summarises. Runs 73–84, 2026-10-09 17:58–19:25,
each watched every 12 s and stopped at the first sign of trouble (run 64 had taken the machine
down, D16). The title's compute programs were read from a memory dump kept in
`~/bc5-data/priv` (never committed) with `llvm-mc --disassemble -mcpu=gfx1013`.

**Result.** Four things were wrong with running them, found in this order:

| # | Run | What happened | Cause | Fix |
|---|---|---|---|---|
| 1 | 64 → 73 | the first converted dispatch hung the GPU and the machine (64) | the prologue's SET_BASE lacked the compute shader-type bit, so the dispatch read its arguments at the bare offset | SET_BASE with header bit 1 (0xC0021102); run 73: 90 s, 21,304 indirect dispatches, none dropped, nothing failed |
| 2 | 74 | from 211 s compute IBs time out without a page fault | the host's sanity check read the arguments at submit time, where they are stale (often ±infinity as floats, 0x7f800000 — the GPU writes them later in the same IB); it dropped some producers and, its product overflowing, let some garbage through | the product computed without overflow; `BC5_DIRECT_TRUST_DISPATCH=1` (skip the check) made it worse (run 75, timeouts from 105 s) and stays off |
| 3 | 77 | timeouts from 107 s | one base for the whole IB, but the big compute IB of a frame (23,627 dwords) has arguments in two 4 GiB ranges, so the second range's dispatches were dropped; and on the GFX ring the prefetch parser reads indirect arguments ahead of the ME, past the CS_PARTIAL_FLUSH the console puts between producer and consumer | the host rebuilds such an IB: every compute-form dispatch becomes SET_BASE (compute, the page of its arguments) + `PFP_SYNC_ME` + the GFX-form dispatch, offsets mapped both ways (drop list in, executed offsets out for the soft CP); an IB with COND_EXEC is left alone and its compute-form dispatches dropped |
| 4 | 78–82 | still timeouts at about 114 s | one compute program, 0x909939900, first seen in the IB that hangs (`BC5_DIRECT_MEC_ONLY/SKIP_PGM` and the journal's "mec pgm" lines): skipped, no timeout (run 80); skipping only the other new one (0x909936c00), the timeout stays (run 81); skipping only 0x909939900, none (run 82) | skipped for this title (`BC5_DIRECT_MEC_SKIP_PGM`). Its code walks a data structure in loops with uncached loads and atomics; why it does not finish here is open |

With all four (runs 80, 83, 84):

| Run | Length | Faults | Failed | fps from 250 s |
|---|---|---|---|---|
| 80 | 300 s | none | 0 | 23.8 |
| 83 | 600 s | none | 0 | 16.2 |
| 84 | stopped at 196 s | one at 0x800000000000, client SQC (instruction fetch) in a graphics DCB with one packet dropped as unmapped | 12 | — |

Before this, the title got past 210 s in about one run in six; with this, in two of three, and
the one stop is of another kind (a graphics buffer, a shader fetched from a bad address). The frame
rate is lower than in 0037 (24) because the GPU now does the compute work it used to skip.

Also measured: the opcode sequence of the compute IBs (`BC5_DIRECT_OPS_DUMP=<n>`): every dispatch
is followed by `EVENT_WRITE` CS_PARTIAL_FLUSH and `ACQUIRE_MEM`, the console's producer/consumer
fence on its compute queue.

**Verdict.** Passed in part: the compute IBs' indirect dispatches run on the GFX ring for the first
time, and the title's 3D scene survives the moment that used to fault in most runs. Open: why
program 0x909939900 does not finish on the single ring, and the graphics-side fault of run 84.
