# 0005 — Direct submission: the game's memory 1:1, its command buffers filtered, not rewritten

**Status.** Accepted, 2026-09-30. Implements docs/PHASES.md phase 3 on track B (D11). GPU
submission stays behind `--submit`/`BC5_GC_MODE=direct` and needs the maintainer's go-ahead per
session (hard rule 5); validation mode is the default.

**Context.** Phases 1b–2 established (F19–F23): Sony's `libSceAgc` builds console-format DCBs inside
the track-B host; the packets decode with zero unknown opcodes; a captured compute program runs
natively with the console's register values; and anonymous CPU memory can be mapped into the GPU
at its own address (`userptr`, 1:1, zero copies). The phase-3 plan in `docs/PHASES.md` spoke of a
"packet rewriter (addresses, context registers)". With 1:1 mapping there is nothing to rewrite in
the addresses: every pointer the game and Sony's library put into a DCB, a V#/T#, a shadow
register table or an indirect buffer is already a valid GPU VA once the containing range is a
userptr mapping. What remains is what the AMD CP firmware and `amdgpu` on the BC-250 will not
accept from Sony's stream.

**Decision.**

1. **Memory model: 1:1 userptr.** Every guest range the game maps with GPU access (direct memory,
   flexible memory, the driver's system areas at 0xf00000000/0xfe0200000, tool memory) becomes a
   userptr BO mapped at the same VA, created by the host at map time (KytyPlus: hooks in
   `KernelMapDirectMemory*`, `KernelMapNamedFlexibleMemory`, the `/dev/gc` `mmap`; unmapped at
   `munmap`). Nothing is copied. Budget: mapped ranges are not pinned permanently (MMU-notifier
   userptr), but the working set of a frame is; the D8 split (512 MiB VRAM, ~14 GiB for Linux) is
   kept and the host box is trimmed (Steam and the file indexer stopped) while phase 3 runs.
2. **Command buffers are submitted as the game built them, through a filter, not a rewriter.**
   Each submit (gfx `0xc0488131`/`0xc0188132`, the 56 doorbell queues) is walked packet by packet;
   the packet is copied into a scratch IB (GTT) either verbatim or replaced by NOPs of the same
   length, per a policy table with three verdicts:
   - **pass**: standard PM4 type-3 packets the AMD gfx10 CP understands and `amdgpu` allows in a
     user IB (draws, dispatches, `SET_*_REG` to user-writable ranges, `LOAD_*_REG[_INDEX]`,
     `ACQUIRE_MEM`, `RELEASE_MEM`, `EVENT_WRITE*`, `WRITE_DATA` to memory, `COND_EXEC`, `ATOMIC_MEM`,
     `WAIT_REG_MEM[64]`, `DMA_DATA`, `INDIRECT_BUFFER*`, `CONTEXT_CONTROL`, `CLEAR_STATE`, NOP…);
   - **drop** (NOP-ed, semantics emulated by the soft CP where needed): packets the AMD firmware
     does not know or that touch privileged state (`GET_LOD_STATS` 0x8e, `PREAMBLE_CNTL` until
     proven harmless, `SET_UCONFIG_REG` to privileged offsets, `SQ_THREAD_TRACE_USERDATA_*`
     markers, `SET_SH_REG` to unresolved offsets such as mm 0x2e80, `WRITE_DATA` to registers);
   - **rewrite** (the only rewrites): `COMPUTE_STATIC_THREAD_MGMT_*` and `SPI_SHADER_PGM_RSRC3_*`
     CU-mask fields ANDed with BC5's mask (36/40 policy, Q3), and the `RELEASE_MEM`/`EVENT_WRITE_EOP`
     interrupt selects (the host, not the CP, fires the `EVFILT_GRAPHICS` events after the fence).
   The table lives in `backend/src/policy.cpp`, is data-driven (opcode → verdict, register range →
   verdict) and is checked offline by `bc5-agc check` over every capture: the count of dropped
   packets per opcode/register is part of every phase-3 experiment.
3. **Submission and completion.** One `amdgpu` context, GFX ring only (F6); each guest submit
   becomes one `amdgpu_cs_submit` with the scratch IB and the BO list of every mapped range; the
   soft CP runs *after* the fence to write labels/EOP values it emulated and to fire events, so
   the game observes the same order as on the console. Fence timeout 2 s → the submit is reported
   as hung, the mode drops to soft-CP-only for the rest of the run (no second try on a wedged
   ring), and the experiment records the last IB. Compute queues go to the same GFX ring in
   doorbell order (the gfx1013 compute rings are not used, F6).
4. **Presentation.** The frame buffers are guest memory; with 1:1 mapping the real GPU renders
   into the very pages KytyPlus's presenter already uploads to its Vulkan swapchain, so the first
   image appears through the existing `sceVideoOutSubmitEopFlip` path with no extra code. A
   direct scanout path is phase 4.
5. **Staging, each step its own experiment with `dmesg` before/after:** (a) validation mode:
   filter every capture offline and live, submit nothing; (b) the 150-dword state preamble alone;
   (c) preamble + the first frame DCB with all draws dropped; (d) draws enabled; (e) compute
   queues; (f) 36/40 switch and FPS. Steps (b)–(f) each need the maintainer's go-ahead.

*Amended 2026-09-30 (experiment 0016, four machine resets):* (i) the scratch IB is padded to
8 dwords with NOPs (the CP fetches 32-byte chunks); (ii) `CONTEXT_CONTROL` is rewritten to
RADV's `0x80000000/0x80000000`; (iii) every memory operand is checked against the mapped ranges,
packets outside are NOP-ed; (iv) the scratch IB lives at a fixed **high** GPU VA
(`high_va_offset + 1 GiB`), never where a CPU pointer can be; (v) the backend opens its **own
amdgpu device without libdrm's deduplication** (`amdgpu_device_initialize2(fd, false, …)`): a
host that already has RADV open on the same node would otherwise hand us RADV's VM, VA allocator
and fd, and our 1:1 mappings would collide with the presenter's buffers; (vi) a crash journal
(`direct.log`, raw and filtered IB files) is written with `fsync` before every submit, because a
GPU reset on the BC-250 takes the machine down before buffered logs reach the disk; (vii) the
scratch IB is mapped **uncached for the GPU** (`MTYPE_UC`): a scratch buffer fetched once by the
CP and rewritten by the CPU is otherwise served from stale GL2 lines on the next fetch — the
first small IB left "NOPs then zeros" in the L2, the next IB executed the zeros as type-0 packets
and hung. (iv) is revised: the fixed VA is 16 TiB, inside the CP's 48-bit range; the kernel-half
"high" range is not addressable by the CP. *Amended 2026-09-30 (step b1, F26):* (viii) the mapping
set is not additive: every sync revalidates the existing userptr BOs against the host's rw
anonymous VMAs and unmaps the stale ones (a guest `munmap` under a mapped range otherwise fails
every later `amdgpu_cs_submit` with `EFAULT`); `EFAULT` at submit is not a hang — it forces a resync
and one retry and does not wedge the mode.
*Amended 2026-09-30 (step c, F27):* (ix) `CLEAR_STATE` is dropped: the console's cmd 1/2 stop the
BC-250's CP a few milliseconds after the submission that carried it; (x) the register policy does
not reach the tables loaded by `LOAD_*_REG[_INDEX]`, so the host journals every table before the
submit and the filter's coverage check treats adjacent mappings as one; (xi) a host that also
emulates the stream skips the memory side effects of the packets the GPU executed
(`SubmitResult::executed_offsets`), and only fires the events.
*Amended 2026-09-30 (step d, F28/F29):* (xii) §1 "every guest range … becomes a userptr BO" is
not feasible as written: the game maps 12.4 GB of direct memory and a userptr BO is populated
completely at submit time. The mapping set is: the resident runs of the guest's anonymous memory
(rw as read/write, r-x and r-- as read-only userptrs — shader code and rodata live there) plus
hint windows around the render-target and depth bases found in each submit's context-register
state; (xiii) hangs are of two classes: a CP-firmware stall (`CLEAR_STATE`, stale L2) takes the
machine down, a shader-side fault is recovered by the kernel's ring reset and only wedges the host.
*Amended 2026-09-30 (step d, F30):* (xiv) the mapping set also learns: a GPU VM fault under a
submission is read back (`AMDGPU_INFO_GPUVM_FAULT`), its 96 MiB region is persisted and mapped
from the start of later runs, and the host reopens its device after the ring reset instead of
staying wedged (`BC5_DIRECT_REOPEN`); the 50 ms sync throttle is gone on the submit path, and the
context state used for the render-target hints is evaluated after every register-changing packet
and kept across submissions.
*Amended 2026-09-30 (step e preparation):* (xv) `INDIRECT_BUFFER` targets are not passed by
reference: each target (transitively, three levels) is copied into the scratch behind the IB,
filtered with the same policy and reached through a rewritten address, so no packet the CP
executes escapes the filter; an unmapped or over-deep target is NOP-ed. `RELEASE_MEM` and
`EVENT_WRITE_EOP` with `DATA_SEL` 0 carry no memory operand.
*Amended 2026-09-30 (step e, F31):* (xvi) the compute rings are off limits (a dispatch on
`comp_1.0.0` resets the machine); the doorbell rings go to the GFX ring in doorbell order, their
`INDIRECT_BUFFER` targets filtered like every IB. A `WAIT_REG_MEM[64]` whose label no earlier
packet of the same IB writes is not dropped but becomes a split point: the packets before it are
submitted, the host waits for the label on the CPU (2 s, then continues), the packets after it
follow. `RELEASE_MEM` CS_DONE/index 6 without data is rewritten to BOTTOM_OF_PIPE_TS/index 5.
*Amended 2026-09-30 (step e, runs 49–51):* (xvii) no GDS/OA/GWS partition is ever given to the
context: with one, the game's gfx shaders hang the CP (the ordered-append state the console's
system sets up is not reproducible from user space). GDS accesses by the CP are redirected to a
64 KiB shadow buffer in memory (`FilterOptions::gds_shadow_va`), the shaders' GDS instructions
are no-ops without a partition. The kernel's compute rings are not used either (F31).
*Amended 2026-10-01 (runs 44, 72; F34):* (xviii) cross-queue waits, as they stand: an IB is not
split at a wait in general (run 44: other processes' SH state between the pieces) — the host
waits on the CPU before the whole IB goes and the filter NOPs the wait. One exception: a compute
IB with an unsatisfied wait whose tail only signals (NOP, markers, `RELEASE_MEM`,
`EVENT_WRITE[_EOP]`, `WRITE_DATA`, waits, `ACQUIRE_MEM`) is split there — head at once, tail when
the label arrives — because the frame DCB waits on a label that head writes while the tail waits
on one the DCB writes. Flip labels are host state: cleared by the host at the flip.
*Amended 2026-10-01 (run 73, F35):* (xix) the filter is no longer strictly in place. `CLEAR_STATE`
cmd 1/2 are the CP's push_state/pop_state; the cmd 0 rewrite of (viii) keeps the CP alive but
drops the game's context registers at every pop. With `Device::set_state_stack` the device tracks
the context registers of the IBs it is given (`bc5/state_stack.hpp`), and an unconditional pop
becomes the `SET_CONTEXT_REG` packets of the state saved at the matching push; the IB grows and
is laid out accordingly in the scratch. SH and UCONFIG registers are not restored (the stream
keeps shadowing them across the bracket; TODO(verify) on hardware behaviour of pop_state for them).

**Consequences.** The "packet rewriter" of the roadmap shrinks to a filter with two rewrites; the
backend's core is the policy table plus the BO/VA mapper, both testable offline. Unknown firmware
behaviour (Sony CP vs AMD CP for the same opcode) is discovered one dropped packet at a time and
recorded in `docs/formats/agc.md`. The risk of a GPU reset stays and is contained by staging,
timeouts and the trimmed host.
