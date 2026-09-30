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
"high" range is not addressable by the CP.

**Consequences.** The "packet rewriter" of the roadmap shrinks to a filter with two rewrites; the
backend's core is the policy table plus the BO/VA mapper, both testable offline. Unknown firmware
behaviour (Sony CP vs AMD CP for the same opcode) is discovered one dropped packet at a time and
recorded in `docs/formats/agc.md`. The risk of a GPU reset stays and is contained by staging,
timeouts and the trimmed host.
