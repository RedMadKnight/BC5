# ADR 0009 — The title's asynchronous compute buffers on a kernel compute ring

**Status:** proposed (2026-10-15). Nothing of it is in the play settings. Each GPU step needs the
maintainer at the box.

## Context

- Every job goes to the one GFX ring today (`Device::submit`, `AMDGPU_HW_IP_GFX` ring 0). That
  covers the graphics buffers (DCB) from the game's threads and the asynchronous compute buffers
  (ACB) that the `bc5-ring` thread takes from the doorbell rings. They interleave in the order
  the device lock is taken (ADR 0005 §3, xvi).
- On the console the ACBs run on the compute pipes, side by side with graphics. Here they queue
  behind it, and it behind them:
  - on the second title's start screen compute is about half of the GPU's busy time, and the GPU
    idles 27.5 % between ~115 jobs a frame (experiment 0124);
  - the order on the one ring decides more than the number of jobs (experiment 0125).
- Much of the host exists only because both queues share one ring:
  - the ACB readiness gate and its 10 s deferral;
  - the tail split with `acb-state` prefixes;
  - the 8 ms limit for game-thread waits, the cycle break, and the graphics pieces of ADR 0008.
- F31 kept the compute rings off limits. Experiment 0127 (F177) overturned it. The rings run
  dispatches with correct results; run 43's machine-down was our own `CONTEXT_CONTROL`. A
  malformed IB on a compute ring stalls only that ring, which the kernel resets on its own.

## Decision (proposed)

A host option, `BC5_DIRECT_COMPUTE_RING=<n>`, off by default, sends the ring thread's `acb` and
`acb-state` jobs to compute ring `n` (`AMDGPU_HW_IP_COMPUTE`). Everything else stays on the GFX
ring.

**Backend (`bc5::direct`):**
- `Device::submit` takes a target: GFX, or compute ring `n`.
- `finish`, the synchronous fence wait and `SubmitResult` carry it too.
- `wait_idle` waits for the last job of every ring; it is called before unmapping.
- Scratch slots become one pool per ring, each used in turn. Today the 64 slots are shared and
  assume jobs complete in submission order; that does not hold across two rings (`-EBUSY`).
- The state-stack tracker follows graphics jobs only.

**Filter, one policy per ring.** For a compute-ring job, `FilterOptions::compute_ring` changes
the following:

| | GFX ring (today) | compute ring |
|---|---|---|
| `CONTEXT_CONTROL`, `CLEAR_STATE`, `SET_CONTEXT_REG`, `LOAD_CONTEXT_REG*`, draws, `INDEX_*`, `NUM_INSTANCES`, `PFP_SYNC_ME` | passed or rewritten | job refused: it goes to the GFX ring and is counted |
| compute-form `DISPATCH_INDIRECT` (4 dwords) | dropped, or rebuilt into the GFX form by the host | passed: it is the MEC's own form |
| zero-byte `DMA_DATA` with `CP_SYNC` at the end of each IB (xxi) and before dispatches | inserted | left out: "Only present for PFP/ME. MEC always sync." (Mesa `src/amd/vulkan/radv_cp_dma.c`, commit 0866ae7) |
| `RELEASE_MEM` CS_DONE/index 6 → BOTTOM_OF_PIPE_TS/5 | on (the GFX ring never completes CS_DONE) | off: CS_DONE is the compute event (TODO(verify), ladder step 5) |
| `indirect_check` (CP-checked indirect counts) | with `PFP_SYNC_ME` | without it (TODO(verify): COND_EXEC on the MEC, ladder step 5) |
| dispatch with `PARTIAL_TG_EN`=1, `USE_THREAD_DIMENSIONS`=0 | passed | job refused: it goes to the GFX ring and is counted. The MEC drops workgroups there (mesa#16054). Bits 1 and 5 of `COMPUTE_DISPATCH_INITIATOR` (Mesa `src/amd/registers/gfx10.json`, commit 0866ae7). |
| GDS / OA / GWS on the BO list | `acb` jobs | the same |
| `acb-state` prefix | register packets of the buffer so far | only `SET_SH_REG`, `SET_BASE`, `SET_UCONFIG_REG` (TODO(verify) for UCONFIG on the MEC) |

- The ring thread's jobs keep their order on the compute ring.
- Job timestamps (experiment 0124) are kept on both rings. The overlap of the two rings' busy
  intervals is the measure of this ADR.

**Cross-queue waits, in steps:**
1. **As today.** The host serves the waits it serves now on the CPU.
   - `RING_ORDER_WAITS` keeps a wait for the GPU only when the writing job is on the same ring.
   - The pending label writes (`register_label_writes`) record the ring of each job.
2. **The compute ring waits on the GPU.** A wait in an ACB on a label written by a graphics job
   already submitted stays in the IB.
   - Is it safe? The compute ring spins on it, and a wait that is never satisfied costs a
     per-ring reset (F177), not the machine.
   - The readiness gate and the tail split then apply only to labels that no submitted job writes.
3. **The GFX ring waits on the GPU**, for labels written by compute jobs already submitted. This
   is the step that would retire the 8 ms limit, the cycle break and the pieces in the water.
   - A hang there without a page fault has taken the machine down before (F110).
   - So this step comes last, and only after steps 1 and 2 are clean.

## Risks, each checked before or in the steps below

- **Implicit sync.** If the kernel makes a compute CS wait for our own graphics jobs on shared
  BOs, nothing overlaps. TODO(verify): `amdgpu_cs_sync_rings` with `AMDGPU_SYNC_NE_OWNER` should
  skip fences of the same VM. The job timestamps show it either way.
- **TLB flushes.** The title maps and unmaps memory all the time. On some kernels compute queues
  have needed a KIQ TLB-flush fix (drm/amd#5597, seen with ROCm). TODO(verify) on 7.2.8; ladder
  step 5 maps while a compute job runs.
- **Races the one ring hid.** Two rings run in parallel what used to be ordered by chance. The
  console has the same freedom, but the host's own shortcuts may rely on the order. Earlier
  examples are the refit started before its DMA copy (experiment 0053) and the deferred flip
  (experiment 0080). The pictures are compared with screenshots, the start screen first.
- **Other users of the ring.** RADV disables the gfx1013 compute queue (F6), so no desktop process
  should share it. TODO(verify) with `amdgpu_fence_info` before and after a run.

## Plan, in order of risk

1. **Offline, no GPU.**
   - Backend: the target parameter, the per-ring slots and the compute-ring policy, with unit
     tests over synthetic buffers.
   - Over the title's dumped ACBs (private), count what the compute policy would refuse:
     graphics packets, `PARTIAL_TG_EN` dispatches.
2. **Ladder step 5** (`dispatch-min`, maintainer present). On compute ring 0:
   - the job-timestamp packets;
   - `0xffff1000` NOP padding (the filter's NOP);
   - `RELEASE_MEM` CS_DONE with data;
   - `COND_EXEC`;
   - a `WAIT_REG_MEM` on a label that a later GFX job writes;
   - a GFX dispatch and a compute fill at once, overlapping in their timestamps;
   - a VA map during a long compute job.
3. **The start screen** with `BC5_DIRECT_COMPUTE_RING=0`, waits as today (step 1 above). Measure:
   - fps;
   - the overlap of the two rings;
   - faults and ring resets;
   - a screenshot against run 525.
4. **Compute-ring waits on the GPU** (step 2 above), then ASTRO BOT's first level and the water.
5. **GFX-ring waits on the GPU** (step 3 above), only after 3 and 4 pass.

Each step goes on only after the previous one is recorded as passed.

## Consequences

- If step 3 passes, the start screen has a measured gain or a measured reason why not (the CUs
  are shared, so the overlap is bounded by what graphics leaves free).
- If step 5 passes, the ring-sharing workarounds of ADR 0005 (xviii, xxii) and ADR 0008 become
  fallbacks and can be retired one by one.
- Until then `BC5_DIRECT_COMPUTE_RING` is off, and nothing changes for the play settings.

*Amended 2026-10-15 (experiments 0128, 0129, F178):*
- Steps 1-3 passed: no title buffer refused, ladder 7/7, start screen on the compute ring.
- The waits went further than step 1: `BC5_DIRECT_CROSS_RING_WAITS=all` (step 3 of the waits) gives the gain, +24-31 % on the start screen. Waits on the CPU are slower than one ring.
- Before a play setting:
  - the menu race (`BC5_DIRECT_RING_DEPS` to locate it);
  - ASTRO BOT and its water;
  - a long run.

*Amended 2026-10-16 (experiments 0130-0132, F179, F180):*
- The compute ring needs `BC5_DIRECT_RING_DEPS=acb`: a compute job starts after the graphics jobs submitted before it. Without it ASTRO BOT draws black blocks.
- With it the second title's start screen keeps 40 of its 42 fps.
- On two rings, a graphics wait without a writer is split at once (the head goes) and given up after 8 ms.
- The second title's play shortcut runs on the compute ring since 2026-10-16 (maintainer's yes); ASTRO BOT has a second shortcut for it.
- Next, the geyser and water cycles: one kernel compute ring per guest compute queue, so that one queue blocks alone, as on the console.

*Amended 2026-10-16 (experiments 0133, 0134):*
- **The black blocks** were the compute heads (`submit_segment`) dropping their waits on graphics, not the order between the rings. With that fixed (0134) no ring dependency is needed.
- **The geyser cycle** (0133) crosses guest queues 32 and 40, and the game rings the doorbell of the counter's queue only after it has submitted the graphics buffer that waits for the counter. The host holds the game's thread in that submission, so the writer never comes while it waits.
- **Decision (proposed):**
  - **Speculative graphics waits.** A graphics wait on a label last written by a compute ring stays for the GPU even before the writer is submitted. The game's thread goes on and submits the writer.
  - **Watchdog.** A host watchdog writes the awaited value into the label if the wait is still unserved after `BC5_DIRECT_SPEC_WAIT_MS` (100), so the GFX ring cannot hang on a writer that never comes. It is journaled; it should not fire.
  - **One compute ring per guest compute queue.** `BC5_DIRECT_COMPUTE_RINGS=<n>`, at most 4. A queue blocked on its ring's GPU does not hold the others; the title uses four (32, 40, 38, 26).
  - **Backend:** a slot pool and fences per compute ring.
  - **Order of tests:** the ladder on rings 0-3, ASTRO BOT's title, then the geyser, with the maintainer present.

*Amended 2026-10-16 (experiments 0134, 0135, F181):*
- The four rings are accepted for experiments.
- The speculative waits' watchdog is rejected as built: a guessed value in a semaphore label hung the GPU on the second title and took the machine down.
- Play settings: one compute ring, `CROSS_RING_WAITS=all`, no ring dependency, no speculative waits.
