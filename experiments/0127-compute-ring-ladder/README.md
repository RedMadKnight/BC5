# 0127 — The BC-250's compute rings run dispatches correctly: F31's machine-down was our own CONTEXT_CONTROL

**Question.**
- F31 (experiment 0016, run 43) put the kernel's compute rings off limits: the first dispatch
  submitted to `comp_1.0.0` took the machine down.
- The second title's start screen spends about half its GPU time in async compute, serialised on
  the one GFX ring (experiments 0124, 0125).
- Do the compute rings work when what we submit is right?

**Setup.**
- BC-250 dev box, 2026-10-15 21:5x, maintainer present, GPU hang watcher on.
- Kernel 7.2.8-ogc5.1, MEC firmware 0x90. `dispatch-min --info` reports compute rings mask 0xf;
  dmesg lists `comp_1.0.0` … `comp_1.3.1` and the KIQ on MEC 2 pipe 1.
- **Research.** Public sources, summarised by an agent:
  - Mesa MR !33116 (commits ff6504d4, 7271b8ee) disabled RADV's compute queue on gfx1013 for wrong
    results (Vulkan CTS failures), not hangs;
  - mesa#16054 and MR !44277 trace those to async-compute dispatches with `PARTIAL_TG_EN=1` and
    `USE_THREAD_DIMENSIONS=0` dropping workgroups;
  - the kernel's gfx_v10_0.c enables illegal-opcode interrupts only on graphics pipes, so a bad
    packet on a compute ring stalls it silently;
  - IGT's `amdgpu_dispatch_init` emits `CONTEXT_CONTROL` only for `AMDGPU_HW_IP_GFX`.
- **The bug behind run 43.** `dispatch-min` left `MemsetParams::gfx_ring` at its default `true` for
  `--ip compute`, so `build_memset_ib` started the compute IB with `CONTEXT_CONTROL`. Fixed: it is
  now set from the IP type (`backend/experiments/dispatch-min/main.cpp`).
- **A ladder on compute ring 0 (`--ip compute --ring 0`), one step at a time:**
  1. a 16-dword NOP IB;
  2. `SET_SH_REG` `COMPUTE_START_X/Y/Z` with the compute shader-type bit;
  3. the buffer-fill dispatch with one workgroup;
  4. with 16 workgroups.
- Raw: `raw/kernel.log`.

**Result.**

| step | IB | result |
|---|---|---|
| 1 | NOP ×16 | fence signalled (rings 0 and 1, also after the resets below) |
| 2a | `SET_SH_REG` without the compute bit, NOP of wrong length | ring timeout, per-ring reset |
| 2b | `SET_SH_REG` with the compute bit, the same wrong NOP | ring timeout, per-ring reset |
| 2c | `SET_SH_REG` with the compute bit, NOP of the right length | fence signalled |
| 3 | dispatch, 1 workgroup | 0 of 256 dwords differ from the value |
| 4 | dispatch, 16 workgroups | 0 of 4096 dwords differ |

- **The two failures were our hand-built test IBs.** A trailing NOP declared one dword more than
  the IB held, and 2a also lacked the shader-type bit.
- **Each failure stalled only that ring.** The kernel journalled "ring comp_1.1.0 timeout … reset
  succeeded … device wedged, but no recovery needed". The machine stayed up, and the ring ran later
  submissions normally.

**Verdict.**
- F31 is corrected: the compute rings run dispatches and give correct results. Run 43's
  machine-down was a graphics-only packet (`CONTEXT_CONTROL`) sent to a compute ring.
- A bad packet on a compute ring now costs a per-ring reset, not the machine.
- ADR 0005 (xvi) can be lifted for experiments, with the maintainer present. What a compute ring
  gets must be compute-ring packets only.
- Next:
  - an ADR for sending the title's asynchronous compute buffers to a compute ring: its own policy,
    no `CONTEXT_CONTROL`, cross-queue waits left to the GPU since the two queues now run side by
    side, GDS;
  - a check of the title's dispatch initiators for mesa#16054's `PARTIAL_TG_EN` case;
  - output verification, because that bug is silent.
