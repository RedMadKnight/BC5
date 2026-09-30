# 0008 — First native dispatch through `amdgpu` (phase 2, task 2)

**Question.** Does `dispatch-min --submit` (ADR 0004) run the IGT gfx10 buffer-clear shader on the
BC-250 through `DRM_AMDGPU_CS` on the GFX ring, without RADV, and fill the destination correctly?

**Setup.** BC-250 dev box, 2026-09-30 08:28–08:40, maintainer's go-ahead given ("BC-250 jest wolny").
- Kernel `7.2.4-ogc3.1.fc44`, libdrm_amdgpu 2.4.134, VRAM carve-out 512 MiB (`mem_info_vram_total`
  536870912), GTT 7966146560 (D8). `bc250-cu-live-manager status`: 40/40 CUs routed. Keep-awake
  inhibit active. No other GPU client of ours running (Prosper, RPCSX not running).
- Binary: `backend/experiments/dispatch-min` built with `-DBC5_WITH_AMDGPU=ON` in the `fedora`
  distrobox (`~/bc5-work/backend-amdgpu`), from repo commit `9571c08` for the first run and `472779f`
  after the fix below. `ctest`: 7/7.
- Risk named in ADR 0004: a bad submission can hang or reset the machine. The fence wait has a 2 s
  timeout; each run was wrapped in `timeout 60`/`120`; `dmesg` was read before and after.
- `--info` before submitting: family 143, chip external rev 0x84, asic id 0x13fe, 24 CUs reported
  (boot-time map, F14), GFX ring mask 0x1, compute rings mask 0xf.
- Log: [`raw/run.log`](raw/run.log).

**Result.**

1. First submission (`9571c08`, 16 KiB): `dispatch done: 0 of 16384 bytes differ from 0x22`, exit 0,
   8 ms wall clock including allocation, upload, submit, fence and readback. Five repeats identical.
   `dmesg` unchanged (no amdgpu message, no reset).
2. Scaling with `--bytes` (`9571c08`): every size larger than 16 KiB left exactly `size − 16384` bytes
   unwritten (65536 → 49152 differ, 1 MiB → 1032192, 16 MiB → 16760832, 256 MiB → 268419072). The GPU
   executed the dispatch without error each time.
   Cause: `build_memset_ib` emitted `DISPATCH_DIRECT` as `{0x10, groups, 1, 1}`, i.e. the group count
   went into `DIM_Y` and `DIM_X` stayed 16. The shader only uses the X group id, so every dispatch
   wrote the same first 16 KiB. IGT's `0x10, 1, 1, 1` (`lib/amdgpu/compute_utils/amd_dispatch.c:175-179`
   @ `9d4b6ef`) is `DIM_X = 16`, not an initiator, as RADV's
   `src/amd/vulkan/radv_cmd_buffer.c:15305-15309` @ `0866ae7` (`blocks[0..2]`, `dispatch_initiator`)
   makes explicit. Fixed in `472779f` (builder, unit test, ADR 0004 amended).
3. After the fix (`472779f`), all sizes are filled completely:

   | bytes | result | wall clock |
   | --- | --- | --- |
   | 16 KiB | 0 differ | 8 ms |
   | 64 KiB | 0 differ | 15 ms |
   | 1 MiB | 0 differ | 163 ms |
   | 16 MiB | 0 differ | 2.5 s |
   | 256 MiB (262,144 groups) | 0 differ | 40.5 s |

   The wall clock is dominated by the CPU-side byte check over a CPU mapping of a VRAM BO (about
   6.6 MB/s at 256 MiB); the GPU time was not measured separately. `dmesg` still unchanged afterwards;
   `mem_info_vram_used` back to 207 MiB (the desktop's share).

**Verdict.** Phase 2 task 2 is done: a compute shader binary placed in a VRAM BO by us runs on the
BC-250 through `amdgpu` on the GFX ring, with our own PM4 (CONTEXT_CONTROL, SET_SH_REG state, CU masks
via SET_SH_REG_INDEX, DISPATCH_DIRECT), and writes every byte of a 256 MiB destination. The first-run
size anomaly was a field-order bug in our encoder, not a hardware or driver limit, and is now covered
by the unit test. Not measured here: GPU execution time (needs RELEASE_MEM timestamps; phase 3) and
whether the 16 CUs added after boot take part (Q8 remainder, phase 3 D5).
