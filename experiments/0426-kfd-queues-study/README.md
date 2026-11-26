# 0426 — amdkfd user-mode compute queues for the title's acbs ("way 3"): a paper study

## Question

Can BC5 run the PS5 title's asynchronous compute buffers (acbs) on amdkfd user-mode compute queues (`/dev/kfd`), one
hardware queue per guest queue, so that each queue keeps its own compute register state as on the console? The study
compares this "way 3" with:
- **way 1**: a host-side shadow of each guest queue's state, restored in front of the queue's work (exp 0381's
  restore, F685; exp 0424's `aq424`);
- **way 2**: up to four kernel compute rings, one per guest queue (ADR 0009, amendment of 2026-10-16).

Background: exp 0424 traced two lean-play faults to `COMPUTE_USER_DATA_5` carried into the BVH refit from other compute
work on the same ring (its §1). F679/F685 showed and fixed the same leak for `USER_DATA_0` between an acb and a dcb.

Asked by the top session for the maintainer, 2026-11-16.

## Setup

Paper and source study only. **No box access** (not even reads), no build, no GPU submission.

Sources, all public, read on the laptop from sparse clones in a scratch folder outside git:

| Short name | Source | Commit |
|---|---|---|
| **L** | Linux `torvalds/linux`, tag `v7.3` | `c03c1a14507dfaf8b856c2608f9ac216021fc222` |
| **R** | ROCm `ROCR-Runtime` (libhsakmt and kfdtest) | `ba56a24c6132c5d195686ae4adf969ca1222fbba` |
| **B** | `akandr/bc250-rocm` (ROCm on the BC-250, one owner's board) | `25a8d2a05132f4366f0fbc5c1b6036486c5ecce7` |

Citations below are `L:path:line` and so on.

The box runs `7.3.3-ogc1.1.fc45` (CLAUDE.md, machine context). Mainline `v7.3` is the nearest public tree.
TODO(verify): the diff of the ogc kernel and 7.3.3 stable against `v7.3` in `drivers/gpu/drm/amd/amdkfd` and the
files cited here. The study assumes none of them changes.

Repo documents read: `CLAUDE.md`, ADR 0005, 0006, 0009, HANDOFF F6, F31, F177, F178, F679, F685,
`experiments/0424-lean-faults/README.md`, `experiments/0403-acb-program-inheritance/README.md`.

## Findings

### 1. Does amdkfd support gfx1013, and how does it schedule gfx10 queues?

**Supported in source.**
- `kgd2kfd_probe` maps GC `IP_VERSION(10, 1, 3)` and `(10, 1, 4)` ("Cyan Skillfish") to `gfx_target_version` 100103
  and the `gfx_v10_kfd2kgd` backend, unless it is a VF (`L:drivers/gpu/drm/amd/amdkfd/kfd_device.c:372-378`).
- The event interrupt class is `event_interrupt_class_v10` (`kfd_device.c:146-159`).
- SDMA: `IP_VERSION(5, 0, 1)` gives 8 queues per engine (`kfd_device.c:91-98`).

**The PCIe-atomics gate passes.**
- KFD refuses a device whose PCIe path lacks atomics when the MEC firmware is older than `no_atomic_fw_version`
  (`kfd_device.c:776-787`). For gfx 10.1.x that version is 145 (`kfd_device.c:221-222`). The box's MEC firmware is
  0x90 = 144 (F177).
- But every Cyan Skillfish PCI ID carries `AMD_IS_APU` (`L:drivers/gpu/drm/amd/amdgpu/amdgpu_drv.c:2176-2183`). An APU
  with GC newer than 9.0.0 sets `have_atomics_support = true` with no PCIe check (`amdgpu_device.c:4010-4017`).
- So the firmware is never compared. TODO(verify) on the box: `/dev/kfd` exists, and dmesg has no
  `skipped device ... PCI rejects atomics`.

**Scheduler: the CP firmware's HWS, not MES.**
- MES is added only for GC 11.x and 12.x (`L:drivers/gpu/drm/amd/amdgpu/amdgpu_discovery.c:2980-3008`). KFD's
  `enable_mes` is copied from that (`amdgpu_amdkfd.c:191`).
- The default `sched_policy` is `KFD_SCHED_POLICY_HWS` (`amdgpu_drv.c:742`), and nothing overrides it for this chip
  (`kfd_device_queue_manager.c:3249-3262`).
- So on gfx1013, KFD queues are mapped through the HIQ and a runlist that the MEC firmware schedules.
- B warns not to use `sched_policy=2` (no HWS): it "wedges sustained compute" (`B:README.md:144`, `:1219`).

**Queues and pipes.**
- gfx 10.1.3 has 2 MECs × 4 pipes × 8 queues (`L:drivers/gpu/drm/amd/amdgpu/gfx_v10_0.c:4763-4775`).
- amdgpu keeps `num_kcq` kernel compute queues: default 8, at most 8 (`amdgpu_gfx.c:1468-1477`). It spreads them
  across the pipes of MEC1 (`amdgpu_gfx.c:217-229`).
- Ring index *n* is created on pipe *n* mod 4, queue *n* / 4 (`gfx_v10_0.c:4938-4955`). It is named
  `comp_<me>.<pipe>.<queue>` (`gfx_v10_0.c:4691-4701`).
- KFD gets the queues of MEC1 that amdgpu does not use; MEC2 is excluded (`amdgpu_amdkfd.c:197-208`). That is 32 − 8
  = 24 HQDs with the default `num_kcq`. TODO(verify) the box's `num_kcq` (F31 lists four rings, `comp_1.0.0` to
  `comp_1.3.0`).
- KFD also allows `max_no_of_hqd = 24` (`kfd_device.c:199`) and up to 1024 queues per process
  (`kfd_priv.h:98`). Above the free HQD count, HWS oversubscribes, i.e. time-slices.

**gfx1013 quirks in KFD.**
- KFD per-queue reset is not implemented for gfx10 (§5).
- KFD VMIDs get no GDS, GWS or OA (`gfx_v10_0.c:5226-5229`).
- `kfd_gws_init` gives a gfx 10.1.x node no GWS unless the `hws_gws_support` parameter is set
  (`kfd_device.c:586-604`).
- CWSR is on, with the `cwsr_trap_nv1x_hex` trap handler (`kfd_device.c:207`, `:545-549`).

**BC-250 ROCm reports (B, one board, Fedora 44, kernel 6.18–7.2.5, patched amdgpu module).**

KFD compute works only with a patched module (`B:README.md:37`, `:89-112`):
- `bc250_flush_pasid_kiq`: the stock PASID TLB flush sent to the KIQ "times out on this chip". The per-VMID fallback
  "finds no VMID under hardware scheduling" (`:102-106`). Credited to ROCm/TheRock#9221, formerly ROCm/ROCm#6313.
- `bc250_flush_by_runlist`: rebuild the runlist on unmap and map. Without it, "freed and reallocated GPU memory
  faults". A bare dispatch probe also returned wrong elements with no error on 8 of 8 boots, and was right on 10 of
  10 with the rebuild (`:107-112`, `:1217`, `logs/flush-cost-2026-08-18/README.md`).

Known issues (`B:README.md:1215-1216`):
- "A GPU reset takes the host down: MODE1 and MODE2 have no implementation on this chip and report success anyway".
  B runs with `amdgpu.gpu_recovery=0`.
- "A rare GPU page fault under sustained load escalates to a preemption timeout, after which the GPU is unusable
  until a reboot".
- B's `logs/kfd-reset-probe-2026-08-22/README.md` confirms that `amdgpu_amdkfd_gpu_reset()` kills the board unless
  `gpu_recovery=0`.

This matches F6 ("a GPU reset can take the machine down") and is the same board family as ours.

### 2. Queue types, packets, per-queue state

**Queue type.**
- `KFD_IOC_QUEUE_TYPE_COMPUTE` (0x0) is the PM4 queue; `..._COMPUTE_AQL` (0x2) is the HSA one
  (`L:include/uapi/linux/kfd_ioctl.h:62-64`; ioctl version 1.23, `:53-54`).
- The v10 MQD for a PM4 queue sets no AQL control (`L:drivers/gpu/drm/amd/amdkfd/kfd_mqd_manager_v10.c:126-128`,
  `:217-224`).

**Packets.** ROCm's own test suite runs PM4 dispatches on such queues:
- `Dispatch::Submit` puts an `INDIRECT_BUFFER` into the queue (`R:libhsakmt/tests/kfdtest/src/Dispatch.cpp:87`).
- `BuildIb` fills that IB with `ACQUIRE_MEM` and with `SET_SH_REG` of `COMPUTE_START_X`, `COMPUTE_PGM_LO`,
  `COMPUTE_PGM_RSRC1/3`, `COMPUTE_RESOURCE_LIMITS`, `COMPUTE_TMPRING_SIZE`, `COMPUTE_RESTART_X` and
  `COMPUTE_USER_DATA_0`. Then come `DISPATCH_DIRECT`, `RELEASE_MEM` and `WAIT_REG_MEM` (`Dispatch.cpp:232-271`).
- `RELEASE_MEM` with an event follows the IB (`Dispatch.cpp:95`).
- So `SET_SH_REG`, `ACQUIRE_MEM`, `RELEASE_MEM`, `WAIT_REG_MEM` and `INDIRECT_BUFFER` on a KFD PM4 queue have a public
  precedent.

Not shown by a public source for KFD queues, all TODO(verify):
- compute-form `DISPATCH_INDIRECT`;
- `LOAD_SH_REG_INDEX`;
- `COND_EXEC`;
- IB chaining.

These are all MEC packets. On kernel compute ring 0 they ran in our IBs: the ladder of 7, with `COND_EXEC`
(ADR 0009, amendment 2026-10-15; F177/F178). The firmware is the same MEC firmware.

Two differences of a KFD queue from a kernel ring:
- **Privilege.** The kernel ring's MQD sets `PRIV_STATE` and `KMD_QUEUE` in `CP_HQD_PQ_CONTROL`
  (`gfx_v10_0.c:6994-6995`); KFD's does not (`kfd_mqd_manager_v10.c:110-112`). Our acbs already run as IB content on
  the kernel ring, which is not privileged either. TODO(verify): a user ring's IB has the same rights.
- **VMID and apertures.** The queue runs in a KFD VMID with `SH_MEM_BASES` 0x6000/0x6000 (`gfx_v10_0.c:5174`,
  `:5199-5218`). Graphics VMIDs get the GMC apertures instead (`gfx_v10_0.c:5372-5376`). It has no GDS, GWS or OA
  (above). ADR 0009's table keeps GDS/OA/GWS on the BO list for acb jobs. TODO(verify) on the title's acb dumps
  whether any acb uses GDS or ordered append; if one does, a KFD queue cannot run it.

**Per-queue register state.** Every compute HQD has its own MQD:
- The v10 MQD's first dwords hold the compute dispatch registers. They include `compute_pgm_lo/hi`, `compute_pgm_rsrc1/2`,
  `compute_resource_limits` and `compute_tmpring_size`, and `compute_user_data_0..15` at dwords 65–80
  (`L:drivers/gpu/drm/amd/include/v10_structs.h:675-756`).
- Both KFD and amdgpu's own kernel compute rings set `CP_HQD_PERSISTENT_STATE.PRELOAD_SIZE = 0x53`, i.e. 83 dwords
  (`kfd_mqd_manager_v10.c:107-108`; `gfx_v10_0.c:7015-7017`). That is exactly up to `compute_user_data_15` plus the two
  `csinvoc` counters.

Inference, TODO(verify) against an AMD document:
- the MEC preloads each queue's compute SH state from its MQD when the queue connects to an HQD;
- it saves the state back when the queue is switched out;
- so `COMPUTE_USER_DATA_*` is per HQD, and survives preemption and runlist changes.

**This holds equally for kernel compute rings.** They are HQDs with the same MQD layout and the same preload. Kernel
rings 0–3 are on four different pipes (above). Way 2 therefore gives one register context per guest queue by the same
mechanism as way 3.

**CWSR** (compute wave save/restore) saves running waves to a per-queue context-save area so that HWS can preempt a
queue mid-dispatch:
- `ctx_save_restore_address/size` in `kfd_ioctl_create_queue_args` (`kfd_ioctl.h:73-89`);
- `cp_hqd_ctx_save_*` in the MQD (`kfd_mqd_manager_v10.c:130-141`).

Wave state is saved, and SH state stays in the MQD. User mode must allocate the area. Its size for gfx10 comes from the
topology. TODO(verify) the size on the box.

### 3. Address space: can a KFD queue share our render-node VM?

**Yes in source, with constraints.**
- `AMDKFD_IOC_ACQUIRE_VM` takes a DRM fd (`kfd_ioctl.h:408`, `:1657-1658`). `amdgpu_amdkfd_gpuvm_acquire_process_vm`
  turns that file's `amdgpu_vm` into a compute VM, fails with `-EINVAL` if it is already one, and attaches the KFD
  eviction fence to the page-directory root
  (`L:drivers/gpu/drm/amd/amdgpu/amdgpu_amdkfd_gpuvm.c:1564-1588`, `:1403-1477`).
- libhsakmt does this on purpose with the fd that libdrm already uses. `amdgpu_device_initialize`, then
  `amdgpu_device_get_fd`, replaces its own fd "by fd libdrm uses", then `AMDKFD_IOC_ACQUIRE_VM` on it
  (`R:libhsakmt/src/fmm.c:2310-2357`). This is the interop path by which a process's Mesa CS and its KFD queues share
  one VM.

**Constraints, each from source:**
1. **Order.** `amdgpu_vm_make_compute`'s comment says it "only works on GFX VMs that don't have any BOs added and no
   page tables allocated yet" (`L:amdgpu_vm.c:2695-2697`). The code does not check this (`:2709-2749`), and libhsakmt
   may acquire after Mesa. To be safe, BC5 would acquire right after `amdgpu_device_initialize`, before any mapping.
   TODO(verify) on the box.
2. **TLB fences on every update.** A compute VM sets `need_tlb_fence = true` (`amdgpu_vm.c:2745`). Every page-table
   update then gets a TLB-flush fence (`amdgpu_vm.c:1093-1098`). The code's own comment ties this to "issues with
   KIQ/MES TLB invalidation timeouts".
   - This would apply to **all** of the title's maps and unmaps, the GFX side included.
   - On this chip the KIQ PASID flush times out and HWS needs a runlist rebuild to flush at all (§1, B). This is the
     drm/amd#5597 class from ADR 0009.
   - TODO(verify): the content of drm/amd#5597 itself was not re-read here; ADR 0009 is the source for its number.
3. **Residency.** KFD tracks and restores only BOs it knows: the eviction fence, the restore worker,
   `PROCESS_RESTORE_TIME_MS` 100 (`kfd_priv.h:749`). Evicted dma-buf imports in a compute VM are re-validated
   (`amdgpu_vm.c:1688-1695`). But a GEM BO mapped only through `GEM_VA` is revalidated at the next CS, not before a
   KFD queue reads it.
   - The title's ~11.3 GiB GTT is pinned (CLAUDE.md, memory), so most BOs cannot move.
   - Any unpinned one (TODO(verify) which) could be read stale by a KFD queue.
   - KFD's own `IMPORT_DMABUF` maps at a VA it is given (`kfd_ioctl.h:1681`). It cannot share a VA already mapped
     through `GEM_VA`: one mapping per range.
4. **VA range.**
   - KFD reports `gpuvm_size = min(max_pfn << 12, AMDGPU_GMC_HOLE_START)` (`amdgpu_amdkfd.c:186-188`).
   - The title's 0x11_…/0x12_… heaps are about 2^36 and lie far below the hole. The same VM serves them to GFX
     today.
   - libhsakmt reserves its own apertures in the same VA space (`fmm.c`). BC5 would not use libhsakmt, only the raw
     ioctls, so it would choose its own VAs. TODO(verify) that raw ioctls without libhsakmt are enough: queue memory,
     doorbell mmap, EOP buffer, CWSR area.
5. **Memory limit.** B hit KFD's accounting limit at about 13.1 GiB, "63/64 of RAM minus 1.5 GiB"
   (`B:README.md:1225`). That limit covers only KFD-allocated BOs, which BC5 would keep small (rings, EOP, CWSR).

### 4. Sync between a KFD queue and the amdgpu GFX ring

- **Labels.** Both sides see the same GPU VA (§3). A `WAIT_REG_MEM` on a label that the other queue writes works as
  it does across the GFX ring and compute ring 0 today (`CROSS_RING_WAITS=all`, F178). The console does the same.
- **No fences between them.** A KFD queue has no per-submission `dma_fence`, and amdgpu's scheduler sees no KFD work.
  So:
  - nothing in the kernel orders a GFX CS after a KFD packet, or the reverse;
  - ADR 0009's implicit-sync risk (`amdgpu_cs_sync_rings`) disappears;
  - every dependency must be a label;
  - only the eviction fence links them, and it preempts all of the process's KFD queues when a fenced BO must move.
- **Host waits.**
  - The host can poll labels as now.
  - Or it can use KFD events: `RELEASE_MEM` with an interrupt and the event id raises a KFD event that
    `AMDKFD_IOC_WAIT_EVENTS` sleeps on (`kfd_ioctl.h:259`, `:1617-1629`; `R:Dispatch.cpp:95`, `:101-103`).
  - Submission is a write-pointer store plus a doorbell write from user space, with no ioctl per acb.
- **New hazard.** A GFX-ring wait on a label written by a KFD queue that HWS has preempted (eviction, runlist rebuild,
  oversubscription) stalls the GFX ring until KFD restores the queue: ≥ 100 ms after an eviction
  (`kfd_priv.h:749-751`). With B's runlist-rebuild flush on every map, that preemption comes at every map and unmap.
  Graphics waits without a page fault have taken the machine down before (F110, ADR 0009 step 3).

### 5. Failure modes

**A hung KFD queue means a full GPU reset on gfx10.** When an unmap (preemption) does not complete,
`unmap_queues_cpsch` calls `kfd_hws_hang` → `amdgpu_amdkfd_gpu_reset`
(`L:drivers/gpu/drm/amd/amdkfd/kfd_device_queue_manager.c:2697-2712`, `:165-185`). The per-queue path first tries
`reset_hung_queues`, which needs `hqd_get_pq_addr` and `hqd_reset` (`:2428-2556`). For gfx10 both are stubs that
return 0 (`L:drivers/gpu/drm/amd/amdgpu/amdgpu_amdkfd_gfx_v10.c:1073-1085`). So detection finds no queue, the call
returns `-ENOTRECOVERABLE`, and the device is reset (`:2723-2748`).

`amdgpu_amdkfd_gpu_reset` resets only if `amdgpu_device_should_recover_gpu` (`amdgpu_amdkfd.c:321-325`). On this
board:
- that reset takes the host down (B, §1);
- with `gpu_recovery=0` nothing is reset, and the GPU stays wedged until a reboot (B).

**Kernel compute rings, by contrast, have a per-queue reset** (`gfx_v10_0_reset_kcq`, `gfx_v10_0.c:9584`, `.reset` at
`:9926`). F177 recorded it working on the box: "device wedged, but no recovery needed".

**Triggers** for a preemption timeout on a KFD queue:
- a wave that CWSR cannot save;
- a `WAIT_REG_MEM` on a label that is never written (the console title's normal pattern across queues); whether the
  MEC preempts a queue parked in `WAIT_REG_MEM` is TODO(verify);
- a page fault. B: "A rare GPU page fault under sustained load escalates to a preemption timeout". The title makes
  them: F443, F582, exp 0424's two faults.

**Other limits:**
- `queue_preemption_timeout_ms` is 9000 (`amdgpu_drv.c:809`).
- Doorbells: one 8-byte doorbell per queue (`kfd_device.c:205`).
- HQDs: 24 free with the default `num_kcq` (§1).
- The TLB-flush defect is in §3.2.

### 6. Cost and fit against ways 1 and 2

| | way 1: host shadow (F685 restore, aq424) | way 2: one kernel compute ring per guest queue (ADR 0009) | way 3: KFD user queues |
|---|---|---|---|
| per-queue `COMPUTE_*` state | emulated: re-emit the queue's state in front of its work; aq424 costs ~3 flips/s (25.6/25.0 → 22.3/22.1, exp 0424) | in hardware: each ring is an HQD with its own MQD and preload (§2), rings 0–3 on pipes 0–3 | in hardware, the same mechanism (§2) |
| queues available | any | 4 used today (ADR 0009 caps it at 4; `num_kcq` ≤ 8) | ~24 HQDs, more by time-slicing |
| kernel and driver | stock | stock, already in play (ring 0) | stock KFD needs B's patched module for correct memory reuse (§1, §3.2) |
| a hung queue | per-ring reset (F177) | per-ring reset (F177) | full GPU reset → host down, or a wedge with `gpu_recovery=0` (§5) |
| maps and unmaps | as today | as today | every PT update in the shared VM gets a TLB fence (§3.2); on this chip only a runlist rebuild flushes |
| sync with GFX | labels plus CS fences | labels plus CS fences (+24–31 %, F178) | labels only; preemption can stall GFX waits (§4) |
| GDS/GWS/OA | yes | yes (kernel VMID setup) | no (§2) |
| submission cost | CS ioctl | CS ioctl | doorbell write, no ioctl |
| new code | done (behind switches) | per-ring slot pools and fences: ADR 0009 amendment 2026-10-16, accepted for experiments | KFD init, VM acquire, queue memory, doorbells, CWSR area, events; a second residency model |

## Verdict

**Not viable on the box's stock kernel; not recommended even with a patched module.** Way 3 offers nothing about
register state that way 2 lacks: per-queue `COMPUTE_*` state comes from the HQD/MQD mechanism, which kernel compute
rings already have (§2). It adds two hazards that way 2 does not have:
- On gfx10, KFD has no queue reset: a hung or unpreemptable queue means a full GPU reset, which is fatal on this board
  (§5).
- Correct memory reuse needs an out-of-tree amdgpu patch that rebuilds the runlist on maps (§1). Making our VM a
  compute VM would put TLB fences on every one of the title's page-table updates (§3.2).

Patching the kernel module is close to the "own kernel driver" that this study was meant to avoid. The only gain is
doorbell submission and more than four queues; the title uses four (ADR 0009: queues 32, 40, 38, 26).

**Recommendation.** Pursue **way 2** for the state question: one kernel compute ring per guest queue,
`BC5_DIRECT_COMPUTE_RINGS=4`. Keep way 1 (F685's restore, which is in the shared builds; `aq424` as a switch) only for
state that crosses from an acb into the GFX ring:
- acbs merged onto the GFX ring (`COMPUTE_RING=-1`, F679);
- graphics dispatches after compute work on the GFX ring.

No hardware queue separates those. Way 2 does not need a KFD experiment.

**If the maintainer still wants way 3 tested,** the check is read-only first, maintainer at the box, no emulator
running:
1. `ls -l /dev/kfd`; `sudo dmesg | grep -iE 'kfd|atomics'` (look for "added device" or "skipped device");
   `grep -h simd_count /sys/class/kfd/kfd/topology/nodes/*/properties`.
2. `cat /sys/module/amdgpu/parameters/{sched_policy,num_kcq,gpu_recovery,cwsr_enable}`;
   `ls /sys/kernel/debug/dri/*/ | grep amdgpu_ring_comp` (root; via the sudoers list only if allowed). This gives
   the rings and pipes for way 2 too.
3. Only then a synthetic submission tool, `--submit` off by default, with no title memory:
   - open the render node and acquire the VM;
   - create one PM4 queue;
   - IB: `SET_SH_REG COMPUTE_USER_DATA_0..5`, a fill shader that stores user data 0–5 to a buffer, `RELEASE_MEM`;
   - a second queue writes different user data;
   - then the first queue dispatches again without setting user data. Pass: it stores its own earlier values.
   - Repeat after forcing a runlist change: create and destroy a third queue.
   - It must never wait on a label that is never written (§5), and never map or unmap while a queue runs, until the
     TLB question has its own step.

The same three-queue user-data test on kernel rings 0–2 is the cheaper and more useful experiment: it confirms
way 2's premise, with the per-ring reset as the safety net (F177).
