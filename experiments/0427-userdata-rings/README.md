# 0427 — Does a kernel compute ring keep a guest queue's `COMPUTE_USER_DATA`? (way 2's premise)

## Question

Way 2 (ADR 0009, exp 0426) gives each of the title's guest compute queues its own kernel compute ring, so that each
keeps its own compute register state as on the console. Does it?

1. Does a hardware compute queue keep `COMPUTE_USER_DATA_4..6` from one job to the next?
2. Is that state tied to the libdrm ring index BC5 submits to (`AMDGPU_HW_IP_COMPUTE`, ring *n*), or only to the
   hardware queue the kernel picked for the job?

Asked by the top session, 2026-11-16: yes to delegating the test of way 2 (the maintainer).

## Why question 2

Exp 0426 assumed that ring *n* is a fixed hardware queue. Linux v7.3 (`c03c1a14`) says otherwise:
- `amdgpu_ctx_init_entity` builds the entity for (`hw_ip`, ring) over **all** schedulers of the context's hardware
  priority. Only VCN/UVD are pinned to one (`drivers/gpu/drm/amd/amdgpu/amdgpu_ctx.c:228-257`).
- The DRM scheduler re-picks the least-loaded scheduler whenever the entity's queue is empty and its last job has
  finished (`drivers/gpu/drm/scheduler/sched_entity.c:576-616`, `sched_main.c:958-983`).
- On gfx10, compute ring 0 is the high-priority one (`AMDGPU_RING_PRIO_2`) when there is more than one; the others
  are `AMDGPU_RING_PRIO_DEFAULT` (`gfx_v10_0.c:4706-4707`, `amdgpu_gfx.c:195-206`).
- A normal-priority context maps to `AMDGPU_GFX_PIPE_PRIO_NORMAL` = `AMDGPU_RING_PRIO_1` = DEFAULT
  (`amdgpu_ctx.c:116-125`, `amdgpu_gfx.h:54-57`, `amdgpu_ring.h:50-54`).
- `bc5::direct` uses one such context (`amdgpu_cs_ctx_create`, `backend/src/direct.cpp:558`).
- Userspace sees four compute ring indices (`amdgpu_ctx_num_entities[COMPUTE] = 4`, `amdgpu_ctx.c:35-37`;
  `amdgpu_kms.c:594-632`). The box has 8 kernel compute queues (below).

## Setup

**Box.** BC-250, kernel `7.3.3-ogc1.1.fc45`. Read-only checks are in `raw/checks.txt`:
- `num_kcq=-1`, `gpu_recovery=-1`, `compute_multipipe=-1`, `sched_policy=0`, `cwsr_enable=1`;
- dmesg lists `comp_1.0.0`…`comp_1.3.0` and `comp_1.0.1`…`comp_1.3.1`, KIQ on MEC 2 pipe 1, and
  `kfd: added device 1002:13fe`;
- `--info`: GFX mask 0x1, compute mask 0xf, IB alignment 32/32 (`raw/info.txt`).

**Tool.** `backend/experiments/userdata-rings/main.cpp`, branch `exp/0427-userdata-rings`.
- Built in the ubuntu distrobox: clang 21.1.8, libdrm-dev 2.4.131, `BC5_WITH_AMDGPU=ON`; binary sha256 `9a988d10…`.
- The default is a dry run with no device: it builds and checks every IB (`raw/dry-run.txt`, 0 bad, also on the
  laptop with `-Wall -Wextra -Wconversion -Wsign-conversion -Werror`).
- `--submit` was used once.

**Program.** The IGT gfx10 buffer-fill program (`dispatch_min.hpp`, IGT `amd_shaders.c:295-309`) with
`s_getreg_b32 s10, hwreg(HW_REG_HW_ID2)` added. Each thread stores `{USER_DATA_4, USER_DATA_5, USER_DATA_6, HW_ID2}`.
- Encoding: LLVM `llvm/test/MC/AMDGPU/gfx10_asm_sop.s:5002-5003`; `HW_REG_HW_ID2` = 24 (`SIDefines.h:769`,
  `AMDGPUAsmUtils.cpp:227`, llvm-project `0b115ab4`).
- `ME_ID` is at bit 8 of HW_ID2 (`SIDefines.h:805`).
- TODO(verify): `PIPE_ID` [5:4] and `QUEUE_ID` [3:0] are taken from the RDNA ISA guide's table. They agree with what
  ran: me 1, pipes 0–3, queues 0–1, the dmesg ring names; the GFX job read me 0.

**Jobs.** 23 jobs, each one CS with one IB and one 64-thread group into its own slot:
- an S job sets the full IGT state, with `USER_DATA_4..7` unique to the job;
- a P job sets everything except `USER_DATA_4..7`.

There were five blocks of different orders (`raw/dry-run.txt`). The program waited on each fence (2 s cap) except
inside two back-to-back pairs (block 4). Safety:
- no label waits;
- all maps made before the first submit;
- `CONTEXT_CONTROL` only on the GFX job (F31).

**Run.** 2026-11-16 11:54:05, BOX-LOCK claimed and released, no emulator running. The maintainer had waived presence
(he need not be at the box, via the top session). `sudo dmesg` before and after; a laptop kernel stream ran
(`raw/kernel-stream-b.txt`).

## Result (`raw/run-b.txt`)

- 23 of 23 jobs ran; every thread of every job stored the same record.
- Every S job read back its own values.
- `dmesg` was byte-identical before and after (1570 lines; the copies are not committed), and the kernel stream is
  empty: no fault, timeout or reset.

Probes:

| | pass | fail | n/a |
|---|---|---|---|
| **hardware-queue premise**: the probe reads what the last job on the same HW_ID2 queue left | 9 | 0 | 1 (first job on that queue: read 0) |
| **ring premise**: the probe reads what the last job on the same libdrm ring left | 3 | 7 | — |

Where the jobs ran:
- Waited-on jobs rotated over `comp_1.1.0`, `comp_1.2.0`, `comp_1.3.0` and `comp_1.0.1` (me 1 pipes 1, 2, 3; pipe 0
  queue 1), whatever their ring index. Job 0 ("ring 0") ran on pipe 1, job 1 ("ring 1") on pipe 2, job 3 ("ring 0")
  on pipe 0 queue 1.
- No job ran on `comp_1.0.0`, the high-priority queue.
- Job 10 (probe, "ring 0") ran on pipe 3 and read **ring 2's** values from job 6. Job 17 (probe, "ring 0") read
  **ring 0's earlier** job 12's values, not those of job 15, its last set on ring 0.
- The three ring-premise passes are the GFX probe (one GFX ring) and the two back-to-back pairs of block 4. There
  the entity's queue was not empty, so the scheduler kept the hardware queue (`sched_entity.c:586-602`).
- The GFX ring kept its own state across its two jobs (job 18).

## Verdict

**Passed for the hardware; failed for BC5's ring index.**
- A hardware compute queue keeps `COMPUTE_USER_DATA_4..6` across jobs (9/9), including across a GFX-ring dispatch
  in between. So per-queue state in hardware is real (exp 0426 §2).
- But a libdrm compute ring index is not a hardware queue. With a normal-priority context, the kernel's scheduler
  moves an idle ring index to the least-loaded of 7 queues. A guest queue's next job can then land on a queue
  another guest queue last used, and inherit that queue's user data: job 10, ring 2's values. This is the same leak
  as exp 0424 and F679, now between compute rings.
- So way 2 as ADR 0009 built it (`BC5_DIRECT_COMPUTE_RINGS=n`, ring = index) does **not** give per-guest-queue state.

What way 2 needs, each to be verified next:
- **pinning**: each guest queue's work must always reach the same hardware queue;
- **or** an explicit state restore in front of every acb (way 1, F685/aq424). That covers any queue.

The source offers no per-index pinning for compute with a normal context (`amdgpu_ctx.c:247-255` pins only
VCN/UVD). TODO(verify) the options:
- a high-priority context (`AMDGPU_CTX_PRIORITY_HIGH`; needs `CAP_SYS_NICE` or DRM master, `amdgpu_ctx.c:100-113`),
  whose scheduler list holds only `comp_1.0.0`: one queue, not four;
- keeping each guest queue's entity busy (never idle, block 4);
- module parameters such as `num_kcq` (a reboot and the maintainer's decision; not touched here).

Correction to exp 0426: its verdict that "way 2 gives one register context per guest queue by the same mechanism"
holds per hardware queue only. The ring-index mapping breaks it. Exp 0426 stays frozen; this record corrects it.
