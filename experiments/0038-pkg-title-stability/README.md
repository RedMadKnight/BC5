# 0038 — the second title's stops: stale mappings, and compute dispatches that never ran

**Question.** After experiment 0037 the second title renders at about 24 fps but stops after some
minutes in most runs, after GPU faults at addresses no mapping explains. Where do those
addresses come from?

**Setup.** As in 0037 (`run-pkg.sh` there; `pkg-series.sh` here runs several in a row and
summarises each). Runs 61–74, 2026-10-09 13:44–18:12; ASTRO BOT regression run 150.

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

Runs 69–71 with `BC5_DIRECT_WATCH_VA=12004b5000:12004b6000` (the host journals every packet with
a memory operand there, and every soft-CP write there) settle the semaphore: a graphics DCB
releases it with `RELEASE_MEM` (64-bit data 0, at its end) and a compute IB waits for it with
`WAIT_REG_MEM64` (equal to 0), 2,233 times each in run 69: an ordinary cross-queue handshake.
When a fault times a DCB out, the soft CP replays the failed buffers in full and does write the 0
(run 71), but the compute queue's jobs then complete only after 81 s (rc −125) and the title
submits nothing more. So the stop is the recovery after a reset, on the compute side; the trigger
is still the fault at a garbage address (run 71: 0x201250e68000). Run 70 had no fault at all and
ran at 21 fps, the scene moving by 540 s, but submissions stopped at 552 s without an error;
nothing in the journal says why. Fault windows learned above 2^47 are no longer given a zero
buffer (the GPU VA cannot hold them).

Runs 72–74 (2026-10-09 17:40–18:12) go one step further:

- *Why recovery takes a minute.* A stall dump (`stall-dump.sh` pointed at these captures) in run
  72 shows the host's ring thread inside the "direct by name (growth)" breakdown, walking 11,500
  views with `SEEK_DATA` while holding the device lock, and the title's render thread waiting on
  that lock: the reopen had reset the growth counter, so the re-import of 9 GiB looked like
  growth. The counter is now kept across a reopen.
- *Why the title does not come back.* A second dump after the recovery: the render thread spins
  (`pause`) in the title's code at +0x3f017c0 over a ring of GPU completions; an entry whose work
  died in the reset never completes. So after a fault the title cannot recover however fast the
  host does; the faults themselves have to go.
- *Why run 64 hung.* The prologue's SET_BASE lacked the compute shader-type bit (header
  0xC0021100); RADV sets the dispatch-indirect base on the GFX ring with
  `PKT3_SHADER_TYPE_S(1)`, TODO(verify) the line. With 0xC0021102: run 73 (90 s,
  `BC5_DIRECT_MEC_INDIRECT=1`) dropped none of 21,304 indirect dispatches and failed nothing.
- *What the converted dispatches do.* Run 74 (600 s, conversion on): from 211 s — when the 3D
  scene's compute work starts, the moment the faults came in the other runs — compute IBs time
  out without a page fault, 25 times, 302 failed submissions, 0.13 fps. The work those
  dispatches carry hangs on the single GFX ring; the likely reason is the class of F64 (the
  console runs these compute queues beside the graphics queue, and a shader-level hand-over
  between them cannot be served when both are serialised on one ring). The kernel's compute
  rings are off limits on this board (ADR 0005 xvi). The second run was stopped.

**Verdict.** The stops are explained, not solved. The trigger is a GPU fault at a garbage
address from shader loads (client TCP in the fault status), most likely data that the dropped
compute-form indirect dispatches would have produced; after it the title cannot recover, because
it waits for GPU work that died in the reset. Running those dispatches is now possible (run 73)
but their work hangs the single ring (run 74). The conversion stays off by default. Next:
what those compute dispatches wait for, and whether splitting the compute IBs at them (as the
compute side of F64's split already does at CP waits) lets the graphics work they wait for run
first.
