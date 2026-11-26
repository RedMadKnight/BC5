# 0297 — a watch on the title's sync labels: who writes the float?

**Question.** Exp 0294's S2 (F360) found the GFX ring waiting on the title's own end-of-pipe sync — `WRITE_DATA` 0,
`RELEASE_MEM` writing 1, `WAIT_REG_MEM` == 1 on 0x11e0b975e0 — whose label held 0x44069b70, a float, after the
title's 0 → 1; exp 0273's 19:04 hang had the same three packets with the label at 7. A shader stored through a garbage
pointer into mapped memory, so no fault, and the ring waited forever: the fault-less hang class. Which dispatch
writes it, and what does it write?

**What the laptop's material cannot say.** The probe's "ud0-3 V#" lines decode the first four user-data words of a
dispatch as a buffer descriptor; for the 0x11d03a… family they read "base 0x114c6400 stride 320 records 16,760,835,
unmapped" and the like — not descriptors, so no store target can be read from them. The programs' code is on the box
only (`~/bc5-data/priv/shaders-pkg/`, `~/bc5-data/captures/shaders-0159/`), the label's page is named nowhere else in
the S2 journal, and the buffer's 29 other three-packet syncs all read 1 at the timeout.

**Setup — two parts, both read-only or host-side; nothing of this is built or run yet.**

1. **Offline on the box's material, after the lift (read-only copies to the laptop):** the disassemblies of the
   dispatch programs of S2's two timed-out buffers — 0x11d03a3400, 0x11d03a2000, 0x11d039f000, 0x11d03a4600,
   0x11d03a3500, 0x11d03a0700, 0x11d04cc300, 0x11d0372300, 0x11d0322e00 (`disf.sh` as in exp 0160, llvm-mc gfx1013)
   — read for their stores: `buffer_store_*` through which descriptor (user SGPRs or a loaded V#), `global_store_*` /
   `flat_store_*` through which address register, and how that address is formed (a table index times a stride, a
   pointer loaded from a record); the S2 journal's probe lines give each dispatch's user data to pair with the
   descriptors. The SQC data fault at 0xb20407c00000 (0290 S2, 0294 S2) belongs to the same family: a scalar load
   from a garbage pointer in the same code, which narrows the reading to the loads and stores that share a base.
2. **The watch (host, `bc5LleAgc.cpp`, behind `BC5_DIRECT_LABEL_WATCH=1`, default off):**
   - *Detection at filter time:* in a buffer, `WRITE_DATA` to memory address A with value 0, then within the next few
     packets `RELEASE_MEM` to A with data 1, then `WAIT_REG_MEM` on A, function equal, reference 1 — the title's sync
     triple. A is recorded for the buffer (the journal gets one summary line per 4,096 triples and the first ten
     addresses).
   - *A copy after every dispatch:* for a buffer with sync triples, after each dispatch's breadcrumb done mark (exp
     0277's `RELEASE_MEM` BOTTOM_OF_PIPE_TS), one `COPY_DATA` (memory → memory, 64 bits, the CP waiting for the
     release) of the *last-armed* label A into the breadcrumb slot's neighbour dword. The labels are armed in order
     in the buffer, so the copy tracks the label the next wait will use. Cost: one 6-dword packet per dispatch in
     those buffers, on top of the breadcrumbs.
   - *At a fence timeout* the probe prints, for each sync triple of the buffer, the label's value now and the
     sequence of copied values by dispatch: the first dispatch after which the copy is neither 0 nor 1 is the
     writer or the one before whose waves outlive its done mark. If no copy ever shows the garbage value but the
     label does at the end, the writer sits after the last dispatch (a draw) or on the other ring, and the probe
     says so.
   - *Without the GPU:* a host thread that reads the recorded labels every millisecond while their buffer is in
     flight and journals the first value outside {0, 1} with the time since submission and the breadcrumbs' last
     reached mark — coarser, but no packet added; useful as the first run.
   - Caveat: the breadcrumbs' per-dispatch end-of-pipe release hid the hang in 0294 S1 and let S2's happen; the
     watch adds one more packet per dispatch, so it may hide the hang too. The host-thread variant has no such
     effect and runs first.

**Plan.** (1) BOX REQUEST after the lift for the read-only copies of the nine programs' code (a few hundred KiB);
disassemble and read on the laptop; write the stores' targets here. (2) If the reading names a store through a
descriptor whose extent covers 0x11e0b975e0 or the 0xb204… scalar base, that is the writer, and the fix is at its
input (which record or table gives the garbage) — no watch needed. (3) Otherwise the watch, host-thread variant
first, on the S6N route with RT on (machine-down risk: last in the day, the maintainer reachable, the 0290 rule).

**Result.** Not started: the box is under MAINTAINER PLAYING (G5, exp 0296) since 09:05.

**Verdict.** Pending.

**Result — step 1, the reading (2026-10-25, offline on the laptop; the box's dumps copied read-only 10:14–10:16 under
my lock, released at 10:16; 0x11d03a0700 has no dump on the box).** No llvm-mc here, so `gcnstores.pl` (this
directory) walks the gfx10 instruction stream by encoding length and prints every memory store, atomic and scalar
load with the registers it goes through (opcode tables from memory of LLVM's AMDGPU .td files, TODO(verify); the
register structure does not depend on them). Per program, up to its first `s_endpgm` (`raw/stores-*.txt`):

| program | role in S2 | stores | through |
|---|---|---|---|
| 0x11d03a3400 | 28 dispatches of 1×1×1 in both buffers | one `buffer_store_dwordx4` then `s_endpgm` — Sony's **buffer fill** (7 dwords) | the V# in user SGPRs s[0:3] |
| 0x11d03a2000 | 15 dispatches (dcb), 5+ (acb) | one `buffer_atomic` (op 0x32) through s[4:7], one `buffer_store_dword` through s[12:15] | V#s from the resource table at s[12:13]: slot +0x10 → s[4:7], slot +0x00 → s[12:15] |
| 0x11d03a3500 | 3 (acb) | two `buffer_store_dwordx2` (v1 = two dwords) through s[44:47] | s[44:47] ← table slot +0x50 (and +0x00 earlier) |
| 0x11d03a4600 | the acb's **last six** dispatches | one `buffer_store_dwordx2` through s[44:47] at +0x10b4 | s[44:47] ← `s_load_dwordx4` from table slot +0x80 (at +0x800), then **`s_buffer_load_dwordx4` s[44:47] from that V# + 0x680** (at +0x930): the store's descriptor is read from a constant buffer the table points to |
| 0x11d039f000 | 4 (acb) | eight `buffer_store_dwordx2/x3` through s[0:3] and s[8:11] | table slots +0x20…+0x70 |
| 0x11d04cc300 | 1 (dcb, 4×32×4) | two `buffer_store_format_x` through s[8:11], one `image_store` | table slot +0x00 chain |
| 0x11d0372300, 0x11d0322e00 | dcb | `image_store`s only | T#s |

**None of the eight programs stores through a VGPR-only 64-bit address** (no `global_store`/`flat_store` without
SADDR): every store goes through a V# or T#, which the hardware bounds-checks — so a stray store of this family needs
a *garbage descriptor*, not a garbage index. The descriptors come from one place: the resource table at the user
SGPR pair s[12:13] (slots of 16 bytes at +0x00…+0x90), and in 0x11d03a4600 from a constant buffer that table slot
+0x80 names (+0x680 into it). The S2 compute job's last six dispatches were 0x11d03a4600; its scalar read of that
constant buffer (`s_buffer_load_dwordx4` at +0x930) is exactly the kind of load whose garbage base produces the run's
one fault — **SQC (data) at 0xb20407c00000** — and whose garbage result, used by the `buffer_store_dwordx2` at +0x10b4,
puts two dwords of float data wherever the bad V# points: the float in the sync label (F360). One bad descriptor
source explains both halves of S2: the compute job's missing fence (a wave faulting on the scalar read) and the GFX
ring's clobbered label (the store of a sibling dispatch whose read did not fault but returned garbage).

**Verdict (step 1).** The writer is not nameable from code alone, but the suspect is narrowed to one mechanism and
one program family: a bad V# read from the resource table / constant block of the 0x11d03a… dispatches — 0x11d03a4600
first (the acb's last dispatches, the float-pair store, the chained descriptor read). The next tool is therefore
**not a label watch** but a probe extension at the fence timeout: for the dispatches of 0x11d03a4600 (and 3500, 2000)
in a timed-out buffer, read user SGPRs 12–13, dump the table's slots +0x00…+0x90 as V#s (base, stride, records) and,
for 0x11d03a4600, the V# at slot +0x80's buffer + 0x680 — and say whether any base lies outside the title's mappings
or whether a store extent covers the hung sync label. That is host-side, read-only at the timeout, no packets added,
no hang hidden. The label watch (plan above) stays as the fallback if the descriptors read sane.

**Step 2 — the probe extension (written 2026-10-25 on the laptop; ships in exp 0300's private binary, `patch0300.py`
edit 12, so that one build and one chain serve both; nothing of it is built or run yet).** At a fence timeout
(`BC5_DIRECT_TIMEOUT_PROBE=1`), for each dispatch in the timed-out buffer whose program is in
`BC5_DIRECT_PROBE_TABLE_PGM` (hex list; default the family: 0x11d03a2000, 0x11d03a3400, 0x11d03a3500,
0x11d03a4600, 0x11d039f000, 0x11d03a0700), the probe:

- reads user SGPRs 12–13 from the SH state it already tracks through the buffer (COMPUTE_USER_DATA_12/13, SH
  0x24c/0x24d, from SET_SH_REG and the LOAD_SH_REG_INDEX tables as it reads them — the programs take the table
  pointer from s[12:13], step 1), and COMPUTE_PGM_RSRC2 (SH 0x213) for the user SGPR count (bits 5:1, Mesa gfx10
  register JSON, TODO(verify)); one line `timeout probe: table (exp 0297): dispatch op .. at <q> of 0x<pgm>: user sgpr
  12-13 <lo> <hi> -> table 0x<addr> (mapped|not mapped), rsrc2 … (<n> user sgprs)`;
- prints the table's slots +0x00 … +0x90 (ten V#s of 16 bytes) decoded as gfx10 buffer resources — dword 0
  base[31:0], dword 1 base[47:32] | stride[29:16], dword 2 num_records (units of the stride when non-zero, else
  bytes), dword 3 raw (LLVM AMDGPUUsage "Buffer Resource Descriptor", TODO(verify) the field positions) — as
  `slot +0x.. at 0x<addr>: <d0> <d1> <d2> <d3> -> base 0x… stride … records … = … bytes [lo, hi)`, with
  ` BASE NOT MAPPED` when the base is outside the title's mappings and ` COVERS THE LABEL` when the extent contains
  `BC5_DIRECT_PROBE_LABEL=<hex>` (set it to the hung sync label once the GFX ring's WAIT_REG_MEM names it; without it
  the first line says so and the extents are still printed for the offline comparison);
- for slot +0x80, follows the chain: that V#'s base + 0x680 is read as the next V# (`slot +0x80 -> +0x680 (the store
  V#)`, 0x11d03a4600's `s_buffer_load_dwordx4` at +0x930 and its `buffer_store_dwordx2` at +0x10b4, step 1).

Read-only (the probe's `covered_sorted` check before every read), no packet added, at most 96 tables a process. The
reading: a `BASE NOT MAPPED` slot in a 0x11d03a4600 dispatch — the scalar load's fault (SQC data at 0xb204…) and the
float store have their input; a `COVERS THE LABEL` extent — the writer and its descriptor; sane tables all round —
the descriptor is overwritten between the dispatch's launch and its waves' loads (a race the per-dispatch sync of exp
0300 would also cure), and the label watch (the plan above) is the next tool.

**Result (step 2).** Pending the build and the chain of exp 0300.

**Result (step 2, exp 0300 S2, 2026-10-25 11:33; `experiments/0300-rt-dispatch-sync/raw/journal-stream.txt`, 680 table
lines).** The timed-out acb #168141 (32 dispatches, all `ran`) ends with twelve dispatches of 0x11d03a4600 (offsets
1509–1982). Eleven read their resource table from user SGPRs 12–13 in the 0x11e0f9f… region and read sane: slot +0x60
a V# base 0x11246…, stride 16, 85 records; slot +0x80 a V# of 168 records whose buffer at +0x680 holds the store V#
base 0x11aef90000, stride 48, 430,080 records, mapped. **The twelfth — the buffer's last dispatch, offset 1982 — has
user SGPRs 12–13 = 0x11e0fbff70**, a table straddling the page boundary at 0x11e0fc0000, whose **slot +0x60 reads
`07c00000 0000b204 e0fbffe0 00000011`: as a V#, base 0xb20407c00000 — exactly the SQC data fault address** (the
program's first instruction is `s_load_dwordx4 s16, s[12:13], 0x60`, step 1; the fault is the scalar buffer load
through it). Its other slots are not V#s but 8-byte pointer pairs (`e0fbffe0 00000011` = the table's own +0x70;
`2464d2e0 00100011`, `24b55500 00100011` into the 0x1124… region), slot +0x80 → +0x680 reads zeros. The 0x11d03a0700
and 0x11d039f000 dispatches' +0x80 → +0x680 chains read float garbage or 0xffffffff — but those programs do not take a
store V# that way (step 1), so those lines say nothing. No `BC5_DIRECT_PROBE_LABEL` was set (the hung label was not
known in advance), so no extent was compared against the label.

**Verdict (step 2).** The faulting dispatch is named: the last 0x11d03a4600 of the compute buffer, whose resource-table
pointer leads into a structure that is not its table. The coredump of the same hang (exp 0300's addendum) shows the title's own IB setting user SGPRs 12-13 = 0x11e0fbff70 by
SET_SH_REG for that dispatch, after fifteen tables descending by 0x90 from 0x11e0f9f5d8: the pointer is the title's,
aimed at the top of a fresh chunk ending on the page boundary 0x11e0fc0000. Open: whether the title's write of that
table reached the memory the host and the GPU read (two views of the page) or had not happened yet when the GPU read. Next tool: a filter-time read of the same slots
(journaled raw, compared at the timeout), and as the fix candidate a drop of a dispatch whose slot base lies outside
the title's mappings. The label watch is not needed.
