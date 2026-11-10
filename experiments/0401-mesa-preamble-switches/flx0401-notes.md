# Experiment 0401 series e7 (tag flx): five switches for the fast-launch draw-class hang

The 19:54 hang (`hang1954-0401.md`) and the 22:54 hang (exp 0404, `bc5-0404/experiments/0404-draw-class-hang-table-catcher/README.md`)
stopped on a fast-launch `DRAW_INDIRECT` that never finished. In both, the stuck draw was the first fast-launch draw after
other work. The section "Proposed switches" of `hang1954-0401.md` (A1, F1, F2) and its section A3 (A4, A5, which rule out
H1 and lead to H2/H3) ask for these switches. Each is off by default. With all five unset, the unit runs exp 0404's path
exactly:

| Switch | Kind | What it does |
|---|---|---|
| `BC5_DIRECT_FL_PROBE_STATE=1` | A1, catcher (CPU at a fence timeout) | `fl_probe` also prints the registers fl_scan tracked (NGG output limits and state, all 32 GS and 16 ES user-data words) for the first draw issued and not done and for the last done one, and the ring entry of the next draw with crumbs. Journal lines only. |
| `BC5_DIRECT_FL_VGT_FLUSH=prefix\|transition\|all` | F1, fix candidate | `EVENT_WRITE` VS_PARTIAL_FLUSH, then `EVENT_WRITE` VGT_FLUSH. `prefix`: at the head of every host prefix of a dcb. `transition`: before a fast-launch draw whose last work may be other work. `all`: before every fast-launch draw. |
| `BC5_DIRECT_FL_SERIAL=1` | F2, fix candidate | `EVENT_WRITE` VS_PARTIAL_FLUSH after every fast-launch draw. |
| `BC5_DIRECT_FL_MESHLET_PROBE=1` | A4, catcher (CPU at a fence timeout) | For every draw issued and not done, follows the meshlet control path of ES 0x11d01345 / 0x11d00f85 / 0x11d00f8d for each point and prints counts only. |
| `BC5_DIRECT_FL_CRUMBS_MESHLET=1` | A5, catcher | The crumbs' three 32-byte copies of such a draw take its point 0's object record (64 bytes) and its first meshlet headers instead of the bytes at the V# bases. |

A1, A4 and A5 extend the crumbs (`BC5_DIRECT_FL_CRUMBS=1`). Without the crumbs they do nothing, and the first-use line says
so. F1 and F2 work with or without the crumbs.

Files:

- `mkflx0401.py <tree root in> <out dir>` applies the edit to `src/libs/bc5LleAgc.cpp`.
  - The input md5 is pinned in one dict (`PINNED`). Each replaced function or struct is also pinned by its own md5, so a
    change by another script in the chain stops this one.
  - A unit that has the edit already is refused, and so is a changed input.
  - After editing, the script undoes its edits and asserts that this gives the input back byte for byte.
  - Each edit keeps braces, parentheses and brackets balanced (outside comments and literals). The inserted text is ASCII,
    with LF line ends.
- `flx0401.cpp` is the CPU test through the unit's seams `bc5_flx0401_*`. Build it on the box with
  `--gate flx0401.cpp <out> --like src/libs/bc5LleAgc.cpp`. Run `flx0401 on` (the test sets all five switches) and
  `flx0401 off` (the test unsets them). The last line is `flx0401: on|off N of N; end`.

## 1. Where the edit goes

Every edit lies in exp 0404's block. That block runs from "// ---- experiment 0404 (in exp 0401's unit): fast-launch draw
crumbs and skip, the pure part" to the end of `fl_probe`. There are three exceptions, all exp 0404's own lines, in
`submit_now` and the completion thread.

| Where | What changes |
|---|---|
| before `FlState` | new block "flx, the pure part": the packet constants, the `kFlx*` register table and its helpers, the meshlet walk |
| `FlState` | adds `last` (the last work), `x` (the `kFlx*` registers), `xstack` |
| `fl_merge_state` | merges `last`, `x` and `xstack` too |
| `FlDraw`, `FlPlan`, `FlOptions` | new members, appended |
| after `FlOptions` | `flx_plan_ml` (A5) |
| `fl_scan` | tracks `x` and `last`, follows the uconfig SET/LOAD forms when `x` is tracked, decides F1/F2 per draw, plans A5 |
| `fl_build` | lays the F1 heads, F1 before a draw's crumbs and F2 after its done crumb; a COND_EXEC range that cannot grow drops them as it drops crumbs |
| before exp 0404's end marker | new late pure block: `flx_parse_flush`, `flx_heads`, `flx_next_draw`, `flx_entry_reading`, `flx_fmt`, `flx_state_lines`, `flx_mesh_line` |
| after the `g_fl_*` counters | new host block: `FlxSwitches`, `flx_switches`, `flx_note`, `fl_keep_done`, `flx_kept`, `flx_probe_state`, `flx_probe_kept`, `flx_probe_ml`, `flx_probe_mesh` |
| `fl_plan_buffer` | reads the switches, sets the new options, computes the prefix heads |
| `fl_after` | builds for F1/F2 without crumbs, counts them (`flx_note`), and marks A5 in the per-draw line |
| `fl_probe` | A1's lines, the next draw's entry, A4 per draw issued and not done, A5's copy labels |
| after `fl_probe` | the CPU test's seams `bc5_flx0401_*` (always compiled in, never called by the emulator) |
| `submit_now` | `fl_after` also runs for a buffer with F1/F2 insertions alone; after the sync `fl_probe` call, `fl_keep_done` |
| completion thread | after its `fl_probe` call, `fl_keep_done` |

Functions and structs touched: `FlState`, `fl_merge_state`, `FlDraw`, `FlPlan`, `FlOptions`, `fl_scan`, `fl_build`,
`fl_plan_buffer`, `fl_after`, `fl_probe`, `submit_now` (two lines), `completion_thread` (one line).

The edit stays away from the buffer allocation lines. It makes no change in `chain_append`, `submit_prefixed`, the
`PendingJob` layout or the GDS shadow layout.

## 2. Design

### 2.1 Which draws count as fast-launch, and the last work (`FlState::last`)

F1 and F2 act on the crumbs' set: every planned draw of class 3, 2 or 0 (`fl_class`). A two-valued or unknown state
therefore gets the flushes too. Flushes change timing, not results, and missing the draw that hangs would defeat the
switch. A draw the caller drops (`drop_offsets`) or the ES skip drops gets nothing.

`last` is carried in `g_fl_state` from buffer to buffer in `submit_now`'s order, the GFX ring's order (the way exp 0404
carries the state). It is updated after every draw (0x24, 0x25, 0x27, 0x2c, 0x2d, 0x35, 0x38) and every dispatch (0x15,
0x16) of every GFX-class buffer, including an acb on the GFX ring:

- after a fast-launch draw (class 3) it is 1;
- after a draw that is not fast-launch, or a dispatch, it is 0;
- after a draw of class 2 it is "0 or 1";
- after a draw of class 0 it is unknown.

A dropped draw does not run, so it leaves `last` as it was. A COND_EXEC range merges `last` like any register (lesson
R22). An `INDIRECT_BUFFER` makes it unknown. It starts unknown.

`transition` puts F1 before a planned draw unless `last` is certainly 1. That covers both hangs:

- 22:54's 12037 followed non-fast-launch NGG draws;
- 19:54's 1702 was the dcb's first draw, after jobs without fast-launch draws.

### 2.2 F1: where the flush goes

- **`transition`, `all`.** The flush goes in the draw's own unit of `fl_build`'s copy, before its crumbs:
  `[F1] [head, copies, tail, issued] <draw> [done] [F2]`.
  - COND_EXEC: the range that covers the draw grows by the flush and skips it with the draw.
  - The backend's draw check still lands right before the draw.
  - "issued = X" now means that the ME passed X's flush too, so the probe's reading (fl0401-notes 2.4) is unchanged.
- **`prefix`.** The flush goes at the head of each host prefix, from `flx_heads`:
  - With a chain (ADR 0010), each `ChainSeg` that has `prefix != 0` gets one at `seg.off`. That is before the prefix's
    `CONTEXT_CONTROL`, `CLEAR_STATE` and its UCONFIG GE writes (`hang1954-0401.md` F1: dump 1172-1204).
  - Without a chain, a "dcb" buffer gets one at its head. A prefixed piece's prefix starts there; a plain dcb gets one too.
  - Draws get none in this arm.
- **Mesa's order differs** (doubt 4). Mesa writes VGT_FLUSH before the UCONFIG VGT writes. Here, `transition` and `all`
  flush after the title's own `LOAD_UCONFIG_REG_INDEX` of that draw, because they sit right before the draw. They test
  "geometry drained and VGT pointers reset before the fast-launch draw". `prefix` tests the host's own UCONFIG writes. A
  flush after the previous work instead would need the last work's identity through COND_EXEC merges. Not built.

### 2.3 F2: why VS_PARTIAL_FLUSH

The goal is that no two fast-launch draws are in the geometry stage at once. The lightest correct form on this ring is one
`EVENT_WRITE` VS_PARTIAL_FLUSH right after the draw (after its done crumb):

- The ME does not process the next packet until the geometry waves before it are done. Mesa `ac_barrier.c:270-281` @
  ab2374a uses this event on GFX10 to wait for GS waves, because PS_PARTIAL_FLUSH "doesn't wait for GS waves that send
  'gs_alloc_req 0'". These fast-launch waves are GS waves.
- It is 2 dwords. It needs no label, no memory and no wait packet, and the policy passes it (0x46 `pass`).
- **The alternative, the crumbs' EOP + WAIT_REG_MEM:**
  - `RELEASE_MEM` BOTTOM_OF_PIPE_TS into a label, then `WAIT_REG_MEM(64)` on it.
  - That is 15 dwords and a memory round trip.
  - It drains the whole pipe (PS, CB, DB), which goes beyond the geometry interaction both hangs point at (4–6 fast-launch
    draws issued behind the stuck one, GE/PA/SX/SPI busy, SC idle).
  - Without the crumbs it would need a label of its own. The filter keeps such a wait only when its label is written
    earlier in the same IB (`policy.hpp` `self_waits_only`), which the EOP does.
  - It is heavier for no gain on this hypothesis, so it is not built.
- **What F2 does not do:** the PS work of draw k may still overlap the geometry of draw k+1 (doubt 5).

### 2.4 A1: the tracked registers (`kFlx*`, `FlState::x`)

`x` holds 71 values. It is sized only when A1, A4 or A5 is on with the crumbs; otherwise it is empty, and every `flx_*`
helper does nothing.

| Space | Registers (gfx10.json address → offset) |
|---|---|
| context | GE_MAX_OUTPUT_PER_SUBGROUP 0x287fc (0x1ff), VGT_GS_MAX_VERT_OUT 0x28b38 (0x2ce), VGT_GS_OUT_PRIM_TYPE 0x28a6c (0x29b), VGT_GS_ONCHIP_CNTL 0x28a44 (0x291), GE_NGG_SUBGRP_CNTL 0x28b4c (0x2d3), VGT_ESGS_RING_ITEMSIZE 0x28aac (0x2ab), VGT_GS_MODE 0x28a40 (0x290), VGT_GS_INSTANCE_CNT 0x28b90 (0x2e4), PA_CL_NGG_CNTL 0x28838 (0x20e), SPI_SHADER_IDX_FORMAT 0x28708 (0x1c2), SPI_SHADER_POS_FORMAT 0x2870c (0x1c3), VGT_DRAW_PAYLOAD_CNTL 0x28a98 (0x2a6) |
| uconfig | VGT_PRIMITIVE_TYPE 0x30908 (0x242), GE_CNTL 0x3096c (0x25b), GE_USER_VGPR_EN 0x30988 (0x262), GE_USER_VGPR1 0x30970 (0x25c), GE_PC_ALLOC 0x30980 (0x260) |
| SH | SPI_SHADER_PGM_LO/HI_GS, RSRC1/2_GS 0xb220-0xb22c (0x88-0x8b), SPI_SHADER_USER_DATA_GS_0..31 0xb230-0xb2ac (0x8c-0xab), SPI_SHADER_PGM_RSRC1/2_ES 0xb328/0xb32c (0xca/0xcb), SPI_SHADER_USER_DATA_ES_0..15 0xb330-0xb36c (0xcc-0xdb; gfx10.json has ES_0..15 only) |

Source: `tools/bc5-agc/regdb/gfx10.json` (Mesa `src/amd/registers/gfx10.json` @ fe554882). Offsets are the address minus
0x28000, 0x30000 or 0xb000, over 4. GE_MAX_OUTPUT_PER_SUBGROUP is the gfx10 name of the field that gfx9 calls
VGT_GS_MAX_PRIMS_PER_SUBGROUP; gfx10.json has no register by the latter name.

**Writers.**

- The packets fl_scan already follows: SET_CONTEXT_REG 0x69, SET_SH_REG(_INDEX) 0x76/0x9b, LOAD_CONTEXT_REG 0x61,
  LOAD_SH_REG 0x5f, LOAD_CONTEXT_REG_INDEX 0x9f, LOAD_SH_REG_INDEX 0x63.
- For the uconfig registers, while `x` is tracked: SET_UCONFIG_REG(_INDEX) 0x79/0x7a, LOAD_UCONFIG_REG 0x5e and
  LOAD_UCONFIG_REG_INDEX 0x64. That is how `backend/src/full_state.cpp` reads them, and the policy passes them.
  `timeout_probe` reads 0x64 as pairs the same way. While `x` is not tracked, these four stay unfollowed, as before.
- `CLEAR_STATE`: cmd 1 pushes the context registers beside `VGT_SHADER_STAGES_EN` (`xstack`) and forgets them; cmd 2 pops
  them; cmd 0 forgets them. This mirrors `full_state.cpp`, where CLEAR_STATE touches only the context space.
- A COND_EXEC range merges them, and an unreadable table or an `INDIRECT_BUFFER` forgets them.

**What the probe prints, for:**

- the FIRST ISSUED, NOT DONE draw (or the draw shown with its data when the reading is another one);
- the last done draw:
  - when it is not this buffer's, `fl_keep_done` has kept the last draw with crumbs of the job that completed last (one
    `FlDraw`, by submission number, only with A1), and the probe prints it when its id is the one "done" names. That was
    19:54's case: done = #412348.

Six lines per draw: context, uconfig, SH, GS user data 0-15, 16-31, ES user data 0-15. A value prints as `%08x`, as
`a|b` (one of two after a COND_EXEC range) or as `?` (not known).

**The next draw with crumbs** after the last one issued: its ring entry's head and tail, read by `flx_entry_reading`:

| Reading | Meaning |
|---|---|
| complete | the ME passed its copies |
| begun | the ME is inside its copies |
| an earlier submission's, or never written | the ME has not reached its crumbs: it is in that draw's state loads, or in an F1 flush before them |
| another draw of this buffer | the ring wrapped: no reading |

### 2.5 A4: the meshlet walk (`flx_mesh_point`, `flx_mesh_counts`)

The addressing is section A3's reading of the three programs (findings only; no program bytes or code in these files). It
was confirmed on the A3 listings in the laptop scratch, which are not committed. Pattern 1 is ES 0x11d01345; pattern 2 is
0x11d00f85 and 0x11d00f8d.

| | Pattern 1 | Pattern 2 |
|---|---|---|
| object table V# | user data 0-3 | user data 0-3 |
| record-index entry | +8 of 16 | +4 of 16 |
| path flag V# (+0 flag, +4 start) | 12-15 | 8-11 |
| table V# (+0x540 index buffer, +0x5a0 headers, +0x620 records) | 16-19 | 12-15 |
| base id | 20 | 16 |

The walk for one point (one group, run by the group's first thread):

1. **The point.** One point per input vertex. Mesa `radv_shader_info.c:775-784` @ ab2374a: "drawing 1 input vertex ~
   launching 1 mesh shader workgroup". `ac_nir_lower_ngg_mesh.c:603-611`: with FAST_LAUNCH=1 the zero-based vertex id is
   the workgroup's index.
2. **The path flag.**
   - Not 0: `e = ib[ib[start] + point]` (32-bit typed loads), `object = e >> 16`, `meshlet = e & 0xffff`.
   - 0: `object = base + v6`, `meshlet = point`.
   - v5 is the vertex id and v6 the first user VGPR (Mesa `radv_shader_args.c:327-331`, `861-865`: on GFX10 the NGG/mesh
     input VGPRs v0-v4, then vertex_id, user VGPR, user VGPR, instance_id).
   - flx takes v6 = GE_USER_VGPR1 when GE_USER_VGPR_EN bit 0 is set (both tracked by A1), and 0 otherwise.
     TODO(verify) both. The line says which.
3. **The record index**: the 32 bits at `(object << 4) + entry offset`.
4. **The record**: at `(index << 6) & 0xffffc0` in the records V#. +0x1c holds the flags (bit 6 clear means `s_trap 1`),
   +0x18 the meshlet count (meshlet ≥ count means `s_trap 1`), +0x14 the header base.
5. **The header**: at `(meshlet << 2) + header base`. Primitives = bits 31:24 + 1, vertices = bits 23:17 + 1.

V#s are read as exp 0297 reads a gfx10 buffer resource: dword 0 base[31:0], dword 1 base[47:32] and STRIDE bits 29:16,
dword 2 NUM_RECORDS (bytes when STRIDE is 0). TODO(verify) the positions. A load past NUM_RECORDS counts as 0; it is
counted. TODO(verify) the hardware's range check and its 0.

**The counts**, per draw issued and not done, with the ES known for certain to be one of the three and its user data
known:

- points (at most 4096: `kFlxMeshCap`), followed, not readable, by the index path;
- record flag bit 6 clear, meshlet index ≥ count (each with its first point);
- the maximum header vertices and primitives;
- headers above 32 vertices or 64 primitives;
- loads past NUM_RECORDS;
- the v6 used.

The points come from the CP's copy of the arguments when the ring entry is complete, else from memory now, or from the
packet for `DRAW_INDEX_AUTO`.

It reads guest memory through the host's mapping only (`covered_sorted`), at the timeout, so about 2 s after the GPU ran
the draw. It is not GPU time, and the line says so.

### 2.6 A5: the crumbs copy the control data (`flx_plan_ml`)

For a crumbed draw whose ES is certainly a pattern program and whose user data are known, the host follows point 0's path
at submit with the CPU. The crumbs' three 32-byte copies then take:

- the object record +0x00;
- the object record +0x20;
- 32 bytes from point 0's header on (the first eight headers on the direct path).

These replace the V# bases' bytes. The ring, the entry layout, `fl_pre` and the probe's print are unchanged: only the
three source addresses and the print's labels differ.

**The CP cannot compute these addresses.**

- COPY_DATA copies from the address in its packet. The record's address depends on memory (the object table's entry, the
  records V#), and the header's on the record.
- So the addresses are the CPU's reading at submit. The CP copies what lies there at GPU time.
- If the chain of pointers changed between submit and GPU time, the copy is of the record the CPU named, not the one the
  GPU used. The probe prints point 0's chain as seen at submit, with the CP's copy, the CPU's read at submit and the read
  now.
- When the header is not reachable, only the object record is copied.
- When the user data are not known for certain or the record's address cannot be computed, the V# bases are copied as
  before. This is counted, and its first 16 are journaled.
- For these programs user data 21-31 never reach the shader (A3), so the dropped "s[20:21]" / "s[24:25]" copies held
  nothing the meshlet path reads.

## 3. Packets and their sources

| Packet | Dwords | Value | Source |
|---|---|---|---|
| EVENT_WRITE header | 1 | `0xC0004600` = PKT3(0x46, count 0) | `backend/src/indirect_check.cpp` `kEventWrite` (exp 0380's args_flush, which ran on this GFX ring); Mesa `src/amd/common/sid.h:129` `PKT3_EVENT_WRITE` @ ab2374a |
| event dword | 1 | EVENT_TYPE bits 5:0, EVENT_INDEX bits 11:8 | gfx10.json `VGT_EVENT_INITIATOR.EVENT_TYPE` bits 0-5; `indirect_check.cpp` `kCsPartialFlush = 7 \| 4 << 8`; the title's own `0x407` (`hang1954-0401.md` §1) |
| VS_PARTIAL_FLUSH | 1 | `0x0000040f`: event 15, index 4 | gfx10.json `VGT_EVENT_TYPE` VS_PARTIAL_FLUSH = 15; Mesa `ac_cmdbuf.h:396-405` (index 4 for VS/PS/CS_PARTIAL_FLUSH, 0 otherwise), `sid.h:131-137` ("4 - *S_PARTIAL_FLUSH") |
| VGT_FLUSH | 1 | `0x00000024`: event 36, index 0 | gfx10.json `VGT_EVENT_TYPE` VGT_FLUSH = 36; `ac_cmdbuf.h:396-405` |
| F1 | 4 | `C0004600 0000040f C0004600 00000024` | Mesa `ac_shadowed_regs.c:2984-2989` (the IB preamble: "Wait for idle, because we'll update VGT ring pointers." / "VGT_FLUSH is required even if VGT is idle. It resets VGT pointers.") and `radv_queue.c:1050-1052` @ ab2374a; `si_state_shaders.cpp:3607`, `3622-3628` @ 0866ae7 as `hang1954-0401.md` quotes them (that file is not in the laptop's Mesa: TODO(verify) the lines on the box). GFX10's NGG→legacy VGT_FLUSH: `ac_gpu_info.c:1017-1019`, `radv_cmd_buffer.c:9223-9229` |
| F2 | 2 | `C0004600 0000040f` | `ac_barrier.c:270-281` @ ab2374a |
| policy | | 0x46 passes; no memory operand | `backend/policy/pm4-policy.tsv` (`op 0x46 pass`); `policy.cpp` `memory_operands` has no case for 0x46 |
| DRAW_INDEX_AUTO count (A4) | | dword 1 | Mesa `radv_cmd_buffer.c:11663-11665` @ ab2374a |
| the crumbs (A5 unchanged) | | WRITE_DATA / COPY_DATA / RELEASE_MEM | `fl0401-notes.md` §3 |

## 4. Costs

**Off** (the default):

- `fl_plan_buffer` tests two more fields of a static, then returns as before. The first use journals one line and prints it
  to stderr ("exp 0401 e7 (flx): ... off"), as exp 0404's switches journal theirs.
- `fl_scan` does not run more often, and does nothing more when it runs for the crumbs or the skip:
  - `x` is empty, so the `flx_*` helpers return at once;
  - `last` is updated once per draw and per dispatch, one assignment each.
- `FlDraw` grows by about 100 bytes (`FlxMeshPoint`, an empty vector and four small fields). `FlState` grows by `last` and
  two empty vectors.
- Nothing is inserted, and the GPU stream is unchanged.

**On:**

| Switch | GPU | CPU |
|---|---|---|
| F1 prefix | 4 dwords and one geometry drain per host prefix of a dcb (about 210–400 dcbs/s, `hang1954-0401.md` §4) | a copy of each such buffer (`fl_build`) |
| F1 transition | 4 dwords and a drain per transition; the count is in the journal, TODO(measure) | as for the crumbs' scan |
| F1 all | 4 dwords and a drain per fast-launch draw: about 7k/s (2,252,424 crumbed draws by t 310 s, `hang1954-0401.md` F1) | as for the crumbs' scan |
| F2 | 2 dwords and a drain per fast-launch draw: about 7k/s. Likely a large fps cost, like F1 all | as for the crumbs' scan |
| A1 | none | 71 values tracked per GFX buffer; a 1.7 KB copy per planned draw (about 12 MB/s at 7k draws/s); one kept `FlDraw`; about 8 lines at a timeout |
| A4 | none | at a timeout only: at most 64 draws × 4096 points × 12 reads |
| A5 | none: the same three 32-byte copies (24 COPY_DATA) as today, from other addresses | about 12 reads per pattern draw at submit |

New buffers, for the cap agent: per-draw `x` copies, freed with the job's plan; `xstack` (at most 8 entries); one kept
`FlDraw` (`g_flx_kept`). None grows without bound.

## 5. Journal lines

```
exp 0401 e7 (flx): fl probe state on|off[ (needs BC5_DIRECT_FL_CRUMBS=1: nothing without it)], fl vgt flush off|prefix|transition|all[ (... does not parse ...)], fl serial on|off, fl meshlet probe ..., fl crumbs meshlet ...
fl vgt flush / serial (exp 0401 e7 flx): submit #N dcb: F VS_PARTIAL_FLUSH + VGT_FLUSH before fast-launch draws, H at host prefix heads, S VS_PARTIAL_FLUSH after fast-launch draws; so far B buffers, f / h / s, A5 a draws (u not followed)     [first 16, then every 16384th]
fl crumbs meshlet (exp 0401 e7 flx A5): submit #N dcb: K pattern draws not followed at submit (...): their V# bases are copied     [first 16]
fl crumbs (exp 0404): submit #N dcb op 24 at Q ... V# bases 0x... 0x... 0x... (flx A5: the object record +0x00, +0x20 and the meshlet headers instead) (K draws so far)
At a timeout, after exp 0404's lines:
fl crumbs (flx A1):     context: GE_MAX_OUTPUT_PER_SUBGROUP 00000020 VGT_GS_MAX_VERT_OUT 00000020 ...
fl crumbs (flx A1):     uconfig: ... / SH: ... / GS user data 0-15: ... / GS user data 16-31: ... / ES user data 0-15: ...
fl crumbs (flx A1):   the last done, of submit #N (the job that completed last): op .. at .. ...   (or: ... its registers were not kept)
fl crumbs (flx A5):     point 0 at submit (pattern 1): direct path, object O, record index R at 0x... (flags .., meshlet count .., header base ..), meshlet M, header .. at 0x... (V vertices, P primitives), K loads past NUM_RECORDS; the CP copied these addresses, it cannot follow the pointers
fl crumbs (exp 0404):     object record +0x00 (flx A5) at 0x...: CP before the draw ... | CPU at submit ... | CPU now ...
fl crumbs (flx A4):     op 24 at 1702: ES 11d01345 (pattern 1), 366 x 1 points (from the CP's copy), 366 followed: ..., record flag bit 6 clear 0 (first at point -1), meshlet index >= count 0 (first -1), headers up to V vertices and P primitives, above 32 vertices 0, above 64 primitives 0 (first -1), loads past NUM_RECORDS 0; v6 ... (...); read now, about 2 s after the GPU ran it (the timeout), not at GPU time
fl crumbs (flx A1):   the next draw: op 24 at 1780 (+.. in the copy), entry 1: head #.. +.., tail #.. +..: <reading>
```

## 6. Tests and what was run (2026-11-04, laptop only; nothing ran on the box)

**The script.** `python mkflx0401.py <e7 input tree> <out>` printed `src/libs/bc5LleAgc.cpp
b448b7c330e943408dddb49acf9da980`.

- Input: the pinned d1cfd9bb1f1b3485bed4207a7f064d4f (533,574 bytes, LF). The changed lines in the diff: 1,063.
- Run again, it gave the same md5.
- It refused:
  - its own output: "the unit has the edit already";
  - an input with one line appended: "not the pinned input";
  - an out dir equal to the tree.
- The internal undo gave the input back byte for byte, and the balance assertions held.
- **Chain dry run** (scratch copies only; the top session re-pins the real ones):
  1. `mkzsk0401.py` on the e6 tree gave 8710207e.
  2. `mklzr0401.py` gave 8ddf48f3.
  3. `mkcap0401.py`, re-pinned, gave bcbdd308.
  4. `mkflx0401.py`, re-pinned, gave b010db09b5ab83b36e76e0328671e955, with exactly the same 1,063 changed lines as on
     d1cfd9bb.

**The stand-in.** The output unit's exp 0404 block, with the flx edits, its host block and the seams, plus the three edited
lines inside stub functions, was put into one TU with stubs of the unit's other names. Scratch `mkstandin.py`, not
committed.

- `clang++ 22.1.3 (MSVC target) -fsyntax-only -std=c++20 -Wall -Wextra -Werror` was clean, and clean with `-Wshadow` too.
- The test itself was also checked with `-fsyntax-only ... -Wshadow`.

**The stand-in run** (fl0401's way, linked with the stand-in instead of the emulator objects):

- `flx0401 on` printed `flx0401: on 173 of 173; end` (rc 0);
- `flx0401 off` printed `flx0401: off 172 of 172; end` (rc 0);
- no argument: usage, rc 2.

The cases:

- the switches as the unit reads them;
- the constants, and every tracked register's offset and name against gfx10.json's addresses;
- the flush values and the prefix heads;
- off is exp 0404's path: the exact 186 + 8 crumb dwords of fl0401's one-draw case, A1's tracking without a packet change,
  nothing planned with everything off, a skipped draw with neither F1 nor F2;
- F1 all, transition and prefix, and F2, on a stream of non-fast-launch draws, fast-launch draws and a dispatch, with
  exact copies and the offset maps both ways;
- all of them with the crumbs: the order and the ring entries;
- transition across buffers, after a non-dcb buffer's dispatch, around caller-dropped and ES-skipped draws, after a
  COND_EXEC range, after an `INDIRECT_BUFFER`, after an unknown-state draw;
- COND_EXEC: the count grown by F1 + crumbs + F2, a range that cannot grow (no F1/F2 inside, the count kept), a prefix
  head inside such a range;
- A1 tracking: SET/LOAD of all three spaces, pair and range forms, CLEAR_STATE push and pop, a COND_EXEC merge, an
  unreadable SH table, an `INDIRECT_BUFFER`; with tracking off, nothing tracked and the same packets;
- A1's six lines from a synthetic state; the next draw; the five ring-entry readings;
- A4 on synthetic object tables, records and headers:
  - both patterns, the direct and the index path;
  - the flag, index and over-limit counts with their first points;
  - loads past NUM_RECORDS, unreadable memory, the 4096 cap, a non-pattern ES;
  - the line's text, `flx_v6` and `flx_user_data`;
- A5: the copies' addresses and exact packets; off, the V# bases; the record only when the headers are unreachable; not
  followed when user data are unknown; another ES; pattern 2 with GE_USER_VGPR_EN clear;
- the real `fl_plan_buffer` and `fl_after`:
  - off: exp 0404's early return, nothing laid;
  - on: transition and serial on the right draws, the caller's drop offset mapped.

**Mutation check** (scratch `mutate.py`, not committed): 20 mutants of the stand-in, each compiled and run in both modes.
All 20 were caught. Most fail in both modes; "F1 needs crumbs again" (fl_after's early return restored) fails in the
"on" glue case only, as expected, since "off" checks the off path. The mutants: transition test inverted, F2 before the done
crumb, F1 after the crumbs, a full range keeping F1/F2, the record-index entry offset ignored, a pop that keeps the pushed
registers, "1" parsed as an arm, v6 ignoring GE_USER_VGPR_EN, A5's header slot from the record, prefix heads not laid, a
dropped draw counted as last work, a dispatch counted as fast-launch, SET_UCONFIG_REG not followed, the header's vertex field
moved, a load past NUM_RECORDS read, the index path's meshlet half swapped, the ES user-data line dropped, the next draw
taken from the first one, and `x` not merged at a COND_EXEC range's end.

## 7. Doubts, risks and TODO(verify)

1. **F1 and F2 change what reaches the GPU.** They are behind default-off switches and are never exercised on a GPU by
   the test. The first box run is the maintainer's play with the switch set, under the usual box rules.
2. **VGT_FLUSH has never run on this ring from BC5.** Exp 0380 ran CS_PARTIAL_FLUSH. RADV emits VGT_FLUSH from user IBs
   (`radv_cmd_buffer.c:9223-9229` → `ac_barrier.c:56-57`), and the policy passes 0x46. TODO(verify) on gfx1013.
3. **VS_PARTIAL_FLUSH's completion point** on gfx1013 with GS fast launch is TODO(verify) (Mesa's comment: "only tested
   Raphael and Navi33").
4. **Order against Mesa.** `transition` and `all` flush after the title's own UCONFIG GE loads of the draw (section 2.2).
5. **F2 serializes the geometry stage only.** The PS work of one draw may overlap the next draw's geometry. If the
   interaction needs a full drain, F2 does not show it. An EOP + WAIT_REG_MEM arm could follow.
6. **Timing.** All of these change timing (R12). A clean play is weak evidence; a hang with the switch on is stronger.
7. **The hang's signature with F1/F2 on.** A stuck draw followed by our VS_PARTIAL_FLUSH should leave the ME waiting on a
   partial flush. That is CP_STALLED_STAT2 bit 15, as 10-29 18:08 had (exp 0404 §2); TODO(verify). The crumbs still name
   the draw: F1 precedes its head, F2 follows its done crumb. With F1, A1's "next draw: never written" may also mean the
   ME is in that draw's flush.
8. **Classes 2 and 0 get F1/F2.** That is a superset of the fast-launch draws.
9. **A4's reading.**
   - v5/v6 come from RADV's GFX10 layout, not from the title's ABI. GE_USER_VGPR1 → v6 is TODO(verify).
   - The typed loads are taken as 32-bit, because the code splits the value 16:16.
   - The range check and its 0 are TODO(verify).
   - The A3 listings predate the 11-01 game update (A3: "Currency, Medium").
   - The data is read about 2 s late.
10. **A5's addresses are the CPU's at submit** (section 2.6). The CP copies them at GPU time.
11. **The non-chain `prefix` arm** flushes at the head of every "dcb" buffer that `submit_now` gets without a chain,
    prefixed or not. The non-chain path is used only with the GE probe or without chains.
12. **fl_build for F1/F2 alone** copies the buffer (the same CPU path as the crumbs). The mec rebuild still refuses both,
    counted, as before.
13. **The first use prints one stderr line**, also with everything off.
14. **A draw the filter NOPs later** (the unit's `extra_drop` of indirect draws without `BC5_DIRECT_INDIRECT_DRAWS`, or
    the backend's draw check skipping it) keeps its F1/F2 packets, as it keeps its crumbs. A flush without a draw is
    harmless.

## 8. What was not checked

- **The full unit was not compiled.** The KytyPlus headers are not on the laptop (lesson R02); only the stand-in TU was.
  On the box:
  1. build the unit;
  2. build `--gate flx0401.cpp <out> --like src/libs/bc5LleAgc.cpp` and link it with the emulator objects;
  3. run `flx0401 on` and `flx0401 off`, and expect `on 173 of 173; end` and `off 172 of 172; end`.
- No GPU run of F1/F2. A1/A4/A5 have not run on real data.
- Mesa `si_state_shaders.cpp:3607-3628` @ 0866ae7 (box only). The laptop's Mesa is ab2374a, a blobless sparse clone
  without that file. The same pair and order were checked there in `ac_shadowed_regs.c` and `radv_queue.c`.

## 9. Files

| File | md5 |
|---|---|
| `mkflx0401.py` | c9a60414944e28feee97c2c94697c05c |
| `flx0401.cpp` | 6ffb8f1f3e1e353557a4a506f22057e8 |
| `flx0401-notes.md` | (this file) |
| input `src/libs/bc5LleAgc.cpp` (series e6) | d1cfd9bb1f1b3485bed4207a7f064d4f |
| output `src/libs/bc5LleAgc.cpp` | b448b7c330e943408dddb49acf9da980 |
