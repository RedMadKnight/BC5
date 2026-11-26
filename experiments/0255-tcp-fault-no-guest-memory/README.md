# 0255 — TCP write faults into memory the host has no guest memory for

**Question.** Three TCP write faults hit addresses that no guest memory covered, unlike F257's faults
in the AMM window:
- the maintainer's play of 2026-10-23 22:59 (shared build, today's defaults): 0x2675dfa000;
- exp 0199's L7 (2026-10-22 12:44): 0x1765833000;
- exp 0211's R11B (2026-10-22 19:28, the BVH build with nothing skipped): 0x1208a7c000.

Each time the GPU then timed out and its rings were reset; the machine stayed up. Which program writes
there, through what address, and what did the title mean to be at those addresses? And what does the
learned window that follows do with the writes?

**Known before this experiment.**
- 22:59 (read-only look on 2026-10-23, the supervisor's request):
  - The kernel log of that boot shows the same fault 10 times: page 0x2675dfa000, status 0x00541051,
    ring 40 (NotPresent plus write, as F257 decodes it), vmid 5, pasid 290. The process is
    kyty_emulator, thread `bc5-ring`, which is the direct path's ring consumer, so it is the direct
    device's VM and not RADV's.
  - Then both gfx_0.0.0 and comp_1.2.0 timed out (23:09:46), and both resets succeeded.
  - The journal's timed-out jobs are #767668 dcb 66,622 dwords and #767674 acb 865 dwords. The 865-dword
    compute buffer is the one that writes label 0x12004b5438 in F279–F283.
  - Nothing mapped 0x2675dfa000 before the fault. Afterwards the host learned the window
    0x2672000000+0x6000000 and saved it.
  - Neither dump holds a pointer into that window, so the address came through memory: a descriptor
    table, or the shader itself.
- L7 (exp 0199): no guest memory at the address, and no pointer to it in its buffers. Its timed-out
  compute buffer (acb 891) carries the markers "Lighting Prep", "CopyResource" and
  "ClearUnorderedAccessView".
- R11B (exp 0246): the BVH build of 56 objects writing through addresses read from memory. No user-data
  pointer within 64 MiB of the faulted pages 0x1208a73000–0x1208a7c000. The learned window 0x1206000000
  followed.
- F257's AMM-window faults were first-use clears ("RTV First-Use Init Clear", ClearRenderTargetView,
  ClearUnorderedAccessView) writing whole 64-KiB-block allocations of sparse UI render targets, over
  blocks the title never mapped. On the console those writes are dropped.
- The learned window maps the shared 2-MiB zero buffer, R|W|X, at every hole. A write into any hole
  then shows in all of them (exp 0199's lead for F255).

**Setup.** `run0255.sh`, read-only, in a box slot with no emulator:
- exp 0199's `markers.py` and `ibwalk.py` over the timed-out buffers of the three cases (the host's
  timeout-probe dumps, private, on the box), for markers, dispatches, programs and user data;
- the 22:59 journal around the timeout, with its learned-window, AMM and PRT lines;
- the learned-window file.

Only counts, offsets, register values and marker names leave the box.

Added after exp 0259/0260: `dec0255.py`, exp 0260's probe decode done offline on the dumps.
- It lists every WAIT_REG_MEM(64), label write and dispatch with its program.
- For the two dumps of one timeout, it gives the cross references: each wait of one buffer on a label the other
  writes, and where.
- Tested on a synthetic two-buffer cycle.
- The dumps hold the buffer before the host's filter, so which waits went to the GPU is not in them.

**Result.** Read-only, 2026-10-24 15:11–15:13 under my lock line, right after exp 0260's catch run (`raw/`: `cases.txt`,
`*-dec.txt`, `*-markers.txt`, `2259-labels-near-timeout.txt`, `direct-learned-pkg.txt`; the walks stay on the box).

1. **Every surviving timeout is the same pair** (`raw/cases.txt`, `*-dec.txt`):

   | case | graphics buffer | compute buffer |
   | --- | --- | --- |
   | 22:59 play | dcb 66,622: waits on 0x12004b3c38, 4438, 4c38 == 0 (WAIT_REG_MEM64, pfp) | acb 865 |
   | L7 (exp 0199) | dcb 19,968: waits on 0x12004b3c38 == 0 (pfp) | acb 891 |
   | R11B (exp 0211) | dcb 31,651: waits on 0x12004b3c38 == 0 (pfp) | acb 875 |

   - The compute buffer is one and the same each time: the "Lighting Prep" pass (`*-acb-*-markers.txt`), with a
     ClearUnorderedAccessView, a CopyResource and the same 8 dispatches with the same programs (0x11d0288800,
     0x11d036b400, …, 0x11d03f9200).
     - Its first packet (offset 0, or 28 after a 28-dword head) is a WAIT_REG_MEM64 on **0x12004b53c8 == 0** (mask
       all).
     - Near its end it writes **0x12004b5438 = 0** (RELEASE_MEM, 64-bit data).
   - F260's and F262's machine-downs also had an 855- and a 875-dword compute buffer timing out with a graphics buffer;
     they were probably this one.
   - The graphics buffer's wait on 0x12004b3c38 is F262's label. In the 22:59 dcb it sits inside the G-buffer depth
     batch (offset 1649).

2. **Neither buffer writes the label the other waits on** (the cross references are empty in all three cases). The
   labels are two hand-off rings:
   - **Graphics → compute ("…c8" slots, 0x400 apart):** graphics buffers write them to 0. The 22:59, L7 and R11B
     dcbs write 0x12004b4fc8 = 0 near their ends (R11B also 4bc8 = 0).
     - The stuck compute buffer waits on 0x12004b53c8, the next slot, so the next graphics buffer writes it.
   - **Compute → graphics ("…38" slots, 0x800 apart: 3c38, 4438, 4c38, 5438):** compute buffers write them to 0, and
     graphics buffers wait for them.
     - The stuck compute buffer writes 5438; the stuck graphics buffer waits on earlier slots.

3. **The 22:59 journal before the timeout** (`raw/2259-labels-near-timeout.txt`, 40,000 lines before it):
   - The ring order keeps this family's compute waits for the GPU routinely, e.g. "acb 1445 dwords keeps its wait at 0
     on 0x12004b37c8 for the GPU (296961 so far)" and the same at 28 on 0x12004b5bc8. One "acb head: 28 of 329 dwords
     go ahead of the wait at 28 on 0x12004b53c8".
   - Graphics waits on 0x12004b3c38 are kept for the GPU in two-ring mode ("kept for the GPU after 0.55 ms": 38,970 of
     41,985 kept, 81 not served).
   - Shortly before the timeout, two CPU-side give-ups on these labels: "cpu-wait WAIT_REG_MEM64 at 380 on
     0x12004b3c38: GIVEN UP after 19.4 ms" and "… at 311 on 0x12004b5438: GIVEN UP after 9.5 ms".
   - Then both buffers TIMEOUT (2,047.8 and 2,046.9 ms). The host's fault query then reports "timeout: fault
     0x2675dfa000 status 0x00541051", and 6,400 lines later "learned: fault 0x2675dfa000 -> region
     0x2672000000+0x6000000 (saved)". That window is the 104th line of the learned-window file.

4. **The TCP fault's writer is still not found.**
   - Neither buffer holds a pointer into 0x2672000000+0x6000000.
   - The faults are reported only by the host's query at the timeout, and are not tied to a job.
   - The compute buffer's dispatches come after its first wait, so if it was stuck at that wait it did not write
     there.

**Verdict.**
- **The TCP faults' writer is not identified.** The faults come with the same two-ring timeout each time, and the
  window that follows is learned after it. Which job wrote into memory with no guest pages is not in the dumps: no
  pointer, and no executed offsets.
- **The two-ring timeout itself now has a concrete shape**, and it is the same in all three surviving cases:
  - a graphics buffer waiting, on the GPU, for a compute-written "…38" slot;
  - the "Lighting Prep" compute buffer waiting, at its first packet, for the graphics-written "…c8" slot that the
    **next** graphics buffer writes.
- **Neither buffer can release the other directly**, so a deadlock has to close through the rings' order:
  - the graphics ring's next buffer sits behind the stuck dcb;
  - the compute ring's next buffer sits behind the stuck acb.
- **That cannot happen with honest registrations.** The ring order keeps a wait only on a write already submitted
  (`register_label_writes` after the ioctl). Let A be the stuck acb and A' the compute buffer behind it that writes
  D's slot; D the stuck dcb and D' the graphics buffer behind it that writes A's slot. Then, in submission order:
  - A's wait was kept, so D' < A;
  - D' is behind D, so D < D';
  - D's wait was kept, so A' < D;
  - A' is behind A, so A < A'.

  Together that gives A < A' < D < D' < A, a contradiction.
- **So a kept wait must have missed its 0** (a hypothesis to test). Either:
  - a stale registration: the job has finished, but the completion thread has not yet run `forget_label_writes`, and
    the title has re-armed the slot; or
  - the title's CPU re-arming the slot between the GPU's write and the wait's read. F262 saw 0x12004b3c38 holding
    0x907616589 while it was waited for == 0, and the Render Thread re-arms labels about once a frame (F282/F283).
- Either way, **it lies in the ring-order keep of these hand-off waits** (exp 0055, ADR 0009). It is not in the held
  tail or the CS prefix: all three cases predate both.
- **What decides it:** exp 0260's probe at the next such timeout, which gives each wait's "now" value and whether it
  was kept. Both waits "ran" and "NOT met", with re-armed (0x9076…-style) values, would confirm it.
