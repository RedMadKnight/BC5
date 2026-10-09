# 0038 — the second title's stops: stale mappings, and compute dispatches that never ran

**Question.** After experiment 0037 the second title renders at about 24 fps but stops after some
minutes in most runs, after GPU faults at addresses no mapping explains. Where do those
addresses come from?

**Setup.** As in 0037 (`run-pkg.sh` there; `pkg-series.sh` here runs several in a row and
summarises each). Runs 61–68, 2026-10-09 13:44–16:50; ASTRO BOT regression run 150.

**Result.**

1. **Mappings one sync behind.** The direct path syncs the GPU's view of guest memory at most
   every 50 ms. A title that remaps AMM pages and then submits work reading them can run the GPU
   on the old mapping for up to 50 ms. The sync now also runs whenever the guest's ranges changed
   since the last one (the generation counter of 0037; `BC5_DIRECT_NO_GEN_SYNC=1` for the old
   rule). Run 61: 600 s, 17.7 fps from 250 s on, one fault, the title went on. Run 62: stopped at
   270 s after a fault at 0x148569d1000. Not the cause.

2. **Compute-form DISPATCH_INDIRECT.** Before each fault the journal shows indirect dispatches of
   the compute IBs dropped as "not mapped", over 10 million in run 61, at addresses like
   0xd0571b00 next to accepted ones at 0x11d0571b00. A compute queue's DISPATCH_INDIRECT carries
   the argument address itself (address lo, address hi, initiator); the GFX ring's carries an
   offset from the SET_BASE index-1 base (offset, initiator) (Mesa `radv_emit_dispatch_packets`,
   TODO(verify) the line). The host read the first as the second: the low dword as an offset
   from base 0. The console's compute IBs run on the BC-250's GFX ring, so these dispatches
   have never run here; they were always dropped.

   A conversion was built: the backend filter rewrites the compute form to the GFX form against
   a base the host sets with SET_BASE index 1 in the IB's prologue
   (`FilterOptions::mec_indirect_base`, unit test in `policy_test.cpp`), and the host computes the
   real argument address. Run 64, the first with it: the first compute IB with a converted
   dispatch (`acb` #225, 1,172 dwords; one of its dispatches asks for 28,800 groups) timed out
   4.3 s into the run, the GPU reset did not recover, and the machine went down until the
   maintainer restarted it (2026-10-09 ~14:15 to 16:12). The build that was being written then
   lost its backend library (0 bytes after the restart) and the run's logs.

   The conversion is therefore off by default (`BC5_DIRECT_MEC_INDIRECT=1` turns it on), and
   off, the host drops compute-form dispatches explicitly, as before: with the address now read
   correctly they would otherwise reach the GFX ring in the compute form.

ASTRO BOT on the safe build (run 150, 420 s): 56.5 fps, no failed submission.

The safe build, two runs of 600 s (runs 67–68):

| Run | Faults | Last submission | fps from 250 s |
|---|---|---|---|
| 67 | one at 0x1456e69000 | 296 s; then a compute queue waited for 0x12004b53c8 to read 0, which never came | — |
| 68 | one at 0xa1261113000, recovered | 599 s | 23.9 |

Across runs 51–68 the stop has the same shape whenever the journal shows it: a fault, then queue 1
of the compute rings waits on 0x12004b53c8 for 0 while it holds what looks like a pointer into
the title's data (0x9076d6d8c). Who writes that 0 is not known yet; `BC5_DIRECT_WATCH_VA=lo:hi`
(host) journals every packet with a memory operand in a range, for the next runs.

**Verdict.** Inconclusive. The faults are not stale mappings. The compute-form indirect
dispatches are a real gap: the console's compute IBs ask for them and the host has never run
one, but running them as converted hangs the GPU beyond recovery, so they stay dropped. Open: what
those dispatches need to run (they are the first compute work of the title's that reaches the
GPU through a conversion), and who releases the semaphore the compute queue waits on.
