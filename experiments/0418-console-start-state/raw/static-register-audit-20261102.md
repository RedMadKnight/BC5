<!-- Copied unchanged on 2026-11-13 from the shared session notes (static-register-audit.md, written 2026-11-02 by exp 0401's session) for provenance. -->
# Static register audit, 2026-11-02: Mesa's start state against the second title on the BC-250

No GPU, no lock, reads only. Numbers and places only; no dump content.

## Method

- Mesa: `~/src/mesa` 0866ae7, the gfx10 path. `ac_cmdbuf.c` (compute 52-93, graphics 392-626), `radv_queue.c` (`radv_emit_compute`, `radv_emit_graphics`, rings), `si_state.c` 4845-4868, `ac_cmdbuf_cp.c` (`ac_emit_cp_tess_rings`), `ac_shadowed_regs.c` (Nv10 context and uconfig, Gfx10 SH and CS SH ranges). 77 registers in the preamble list.
- Title and host: every SET_CONTEXT/SH/UCONFIG packet in 1,347 captured buffers on the box (1,169 from `captures/ibdump-*`, 178 `ib-timeout-*`). 167 of them carry the host's full-state prefix, so they show what the tracker gathered from the title's `LOAD_*` tables too. 39 walks stopped early on a non-PM4 dword.
- Host's own writes in play: `tf_ring_prefix` (0x24e, 0x24f, 0x250, 0x261), the CU masks (`policy::mask_cu_register`), `emit_prefix` (replay of the title's state, CONTEXT_CONTROL, CLEAR_STATE), `cs_prefix`. `dispatch_min.cpp` writes more, but it is a selftest, not play.
- Kernel: Linux v7.2 `gfx_v10_0.c`, grepped from raw.githubusercontent.com. GC 10.1.3 uses `golden_settings_gc_10_0_cyan_skillfish`.

Scripts beside this note: `scan-title-regs.py`, `audit-compare.py`, `audit-ranges.py`.

## Result: 16 of 77 set by neither title nor host

Context: none of 20.

| Class | Register | Mesa's value | Source | Kernel v7.2 | Reading |
|---|---|---|---|---|---|
| uconfig | CP_COHER_START_DELAY (mm 0xC07B) | 0x20 | ac_cmdbuf.c:60, gfx10 path only; other levels 0 (:39, :155) | absent | live; Mesa gives no reason; bits 0-5 START_DELAY_COUNT |
| uconfig | GE_MIN_VTX_INDX (0xC249) | 0 | :599 | absent | live: index clamp window |
| uconfig | GE_MAX_VTX_INDX (0xC259) | ~0 | :608 | absent | live: index clamp window |
| uconfig | VGT_INSTANCE_BASE_ID (0xC25A) | 0 | :609 | absent | live |
| uconfig | PA_SU_LINE_STIPPLE_VALUE (0xC280) | 0 | :613 | absent | lines with stipple only |
| uconfig | PA_SC_LINE_STIPPLE_STATE (0xC281) | 0 | :614 | golden, mask 0xf, value 0 (:3610) | kernel covers it |
| uconfig | VGT_ESGS_RING_SIZE, VGT_GSVS_RING_SIZE | ring sizes | radv_queue.c:372 | absent for this chip | only with a legacy GS ring; Mesa skips them without one |
| SH | SPI_SHADER_REQ_CTRL_PS (0x2C30) | 0x7: soft grouping 1, 4 requests per CU | :444 | absent | live: PS wave scheduling |
| SH | SPI_SHADER_REQ_CTRL_VS | 0 | :457 | absent | hardware VS |
| SH | SPI_SHADER_PGM_RSRC4_VS | CU_EN high | :454 | absent | hardware VS |
| SH | SPI_SHADER_PGM_HI_VS | address32_hi >> 8 | radv_queue.c:732 | absent | hardware VS |
| SH | SPI_SHADER_USER_ACCUM_VS_0..3 | 0 | :458-461 | absent | hardware VS |

Hardware VS is dead here: the three `VGT_SHADER_STAGES_EN` values in the prefixes (0x2002100, 0x482030, 0x2000) all have PRIMGEN_EN, as does the water's 0x200210d.

So five registers are live and unset: CP_COHER_START_DELAY, GE_MIN_VTX_INDX, GE_MAX_VTX_INDX, VGT_INSTANCE_BASE_ID, SPI_SHADER_REQ_CTRL_PS.

## By shadow range

| Class | Named | Seen | Not seen |
|---|---|---|---|
| Context (Nv10) | 603 | 602 | PA_SC_TILE_STEERING_OVERRIDE, set by the kernel's clear-state buffer (`gfx_v10_0.c:4338`), and CLEAR_STATE restores it |
| Uconfig (Nv10) | 20 | 14 | the four live uconfig above, VGT_GSVS_RING_SIZE, CP_STRMOUT_CNTL (streamout) |
| SH (Gfx10) | 175 | 131 | hardware VS (42), SPI_SHADER_REQ_CTRL_PS, SPI_SHADER_REQ_CTRL_VS |
| CS SH (Gfx10) | 37 | 35 | COMPUTE_PERFCOUNT_ENABLE, COMPUTE_THREAD_TRACE_ENABLE |

## Privileged, through the kernel

On gfx10 Mesa has none at start. `is_privileged_reg` (`ac_pm4.c:34`) covers gfx6-8 only, and `SPI_CONFIG_CNTL` on gfx10 is uconfig and only for thread trace (`ac_cmdbuf_cp.c:645`). The kernel's own golden list for this chip has 34 registers (GCR_GENERAL_CNTL, GL2C_CTRL2/3, PA_SC_ENHANCE, TA_CNTL_AUX, SQ_ARB_CONFIG and others). Mesa never touches them, so this audit says nothing on them. What the console's kernel puts there, or what the six `/dev/gc` requests ask of it, cannot be read from Mesa.

## Other findings

- `WRITE_DATA` to a register: one register only, mm 0xC343 `SQ_THREAD_TRACE_USERDATA_3`, 10,433 writes in the scan (dcb 9,789, acb 644). The host drops them. This is the census F787 lacked, for these buffers.
- 338 written offsets have no name in `gfx10.json`, and 6 of them have one in `gfx103.json`. 335 write 0. Three do not: context 0x283ac = 0xff00ff00, context 0x283b0 = 0x10000, uconfig 0x30e0c = 0x40000040. mm 0x2e80 (0xBA00) is among the zero ones.

## Limits

- One title. Registers that only ever came through a `LOAD_*` table are seen only if the tracker read it and a dump with a prefix came after.
- `TITLE` here means title or host: the prefix replays the title's state, and this audit does not split the two.
- Reset values are not known. Grep of `gfx_v10_0.c` only, so anything set in another kernel file is not excluded (`amdgpu_gfx.c` was also grepped, no hits).
- SH and uconfig state is global, not per process. KWin is running on the box, and if it renders through Mesa its preamble writes these same registers with Mesa's values. That would make the five already correct during play. Not shown: kwin's maps were not readable, and no read-back was done.
