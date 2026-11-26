# Experiment 0401, exp 0404's switches: fast-launch draw crumbs and the ES skip

Exp 0404 (`bc5-0404/experiments/0404-draw-class-hang-table-catcher/README.md`, section 4 and Verdict Q4) traced the
22:54 hang to a fast-launch `DRAW_INDIRECT` that did not finish (title dword 12037, ES `0x11d00f85`). It proposed two
switches. This series builds both into series e3's unit, each off by default:

| Switch | Kind | What it does |
|---|---|---|
| `BC5_DIRECT_FL_CRUMBS=1` | catcher | Puts crumbs around every draw of a dcb whose `VGT_SHADER_STAGES_EN` is fast-launch, or may be. At a fence timeout, `fl_probe` names the draws that were issued and not done, and prints the inputs the CP copied for the first of them. |
| `BC5_DIRECT_FL_SKIP_ES=<list>` | diagnostic | Drops the draws that are certainly fast-launch and whose `SPI_SHADER_PGM_LO_ES` is certainly in the list. It uses `FilterOptions::drop_offsets`, as `BC5_DIRECT_SKIP_PGM` drops dispatches. |

Files:

- `mkfl0401.py <unit in> <unit out> <inc out dir>` applies the edit. Every anchor must occur exactly once, and a unit
  that already has the edit is refused.
  - Input: series e3's `bc5LleAgc.cpp`, md5 `d3b7f9b0ab43184ee11de83e9e233ff8`.
  - Output: the unit, md5 **`df12bb2de3e90b8c82a234eedf0babb5`**, and `fl_scan.inc`, which is byte for byte the unit's pure block.
- `fl0401.cpp` is the CPU test of `fl_scan.inc`. It has 74 cases and prints `fl0401: 74 of 74 cases; end`.

## 1. What `BC5_DIRECT_FL_SKIP_ES` takes: `SPI_SHADER_PGM_LO_ES`, the program address >> 8

`timeout_probe` reads SH `0xc8` and `0xc9`, `SPI_SHADER_PGM_LO_ES` and `SPI_SHADER_PGM_HI_ES` (Mesa
`src/amd/registers/gfx10.json` @ `fe554882`: `0xb320` and `0xb324`). Its state line prints
`es %08x%08x` with `g(st_sh, 0xc9), g(st_sh, 0xc8)`, so HI comes first and LO second. The `0x11d00f85` that exp 0404
writes is the LO value, for three reasons:

- It has 8 hex digits, so it fits one 32-bit register.
- As an address, `0x11d00f85` would lie at about 298 MB. The title's memory is near `0x11_xxxx_xxxx`: its programs
  `0x11d0369e00` and `0x11d049aa00`, its arguments at `0x11d0571b00`, its `SET_BASE` `0x1193ad3900`. LO << 8 is
  `0x11d00f8500`, which lies in that range.
- HI's only field is `MEM_BASE`, bits 7:0, which holds address bits 47:40 (gfx10.json). It is 0 for every address
  below 2^40, the title's included. The probe prints `ffffffff` for a register it did not see set in the buffer, which
  may be why exp 0404 quotes only LO. TODO(verify) against the 22:54 `direct.log` line.

So the list holds `SPI_SHADER_PGM_LO_ES` values in hex, with or without `0x`, separated by commas or spaces.

- Each value must be between 1 and `ffffffff`. The probe's 16-digit form `0000000011d00f85` parses to the same value.
- The match uses LO alone; HI is not compared.
- Unset, empty, `0`, or anything that does not parse leaves the switch off, and the journal says why (lessons
  R41/F767).

Exp 0404's arms: `BC5_DIRECT_FL_SKIP_ES=0x11d00f85`, `0x11d00f8d`, `0x11d00cde`, or all three together.

## 2. Design

### 2.1 Where the slots and the ring live: the GDS shadow, +0x8000..+0xa100

The backend's 64 KiB GDS shadow is used:

- It is allocated by `Device::open` when `OpenOptions::gds_shadow` is set, at `kShadowVa = 0x1000'0400'0000`
  (`backend/src/direct.cpp:221, 637-655`). The unit sets `oo.gds_shadow = true` at open and on reopen.
- It is on every BO list (`direct.cpp:1473`).
- The host reads it through `gds_shadow_cpu()`.

Layout from shadow +0x8000:

| Offset | Bytes | Contents |
|---|---|---|
| +0x8000 | 8 | issued: the id of the draw the ME last reached |
| +0x8008 | 8 | done: the id written by the last end-of-pipe event that completed |
| +0x8100 | 64 × 128 | the ring, up to +0xa100 |

A ring entry is 32 dwords:

| Dwords | Contents |
|---|---|
| 0-1 | head id |
| 2-5 | the 16 argument bytes |
| 6-13 | 32 bytes at the `s[8:9]` V# base |
| 14-21 | 32 bytes at the `s[20:21]` V# base |
| 22-29 | 32 bytes at the `s[24:25]` V# base |
| 30-31 | tail id |

An **id** is `(draw's dword offset << 32) | low 32 bits of the submission number`. The submission number is `n` in
`submit_now`.

The area is free:

1. The backend writes the shadow in only one place: the policy filter's GDS redirect, when
   `FilterOptions::gds_shadow_va != 0` (`backend/src/policy.cpp:507, 601-628`).
2. The unit never sets that field. `mkfl0401.py` asserts that `opt.gds_shadow_va` does not occur. It also asserts the
   unit's exact number of `gds_shadow_va()` uses (5) and `gds_shadow_cpu()` uses (2), so a new user of the shadow
   stops the generator.
3. The shadow's only other user is the exp 0160 GE probe:
   - `kGeProbeOff = 0xc000`, 512 slots × 32 bytes, so it occupies +0xc000..+0x10000.
   - The generator asserts both constants.
   - The unit has `static_assert(kFlAreaOff + kFlAreaBytes <= kGeProbeOff)`.
4. The BO is zeroed when allocated. A reopen after a reset allocates a new, zeroed shadow.

The filter's operand check (`opt.mapped`) lets the area through only when the crumbs are on. The lambda captures
`fl_area = fl_crumbs_area()`, which is 0 when the switch is off.

### 2.2 How the walk follows the state: `fl_scan`, carried in `g_fl_state`

`fl_scan` is a pure template with the same reader shape as `inherit_scan`. It follows these registers:

| Register | Where | Source |
|---|---|---|
| `VGT_SHADER_STAGES_EN` | context 0x2d5 | gfx10.json 0x28b54 |
| `SPI_SHADER_PGM_LO_ES`, `SPI_SHADER_PGM_HI_ES` | SH 0xc8, 0xc9 | gfx10.json |
| `SPI_SHADER_USER_DATA_GS_8/9`, `_20/21`, `_24/25` | SH 0x94/0x95, 0xa0/0xa1, 0xa4/0xa5 | `SPI_SHADER_USER_DATA_GS_0` = 0xb230 = SH 0x8c |
| the `SET_BASE` index-1 base | packet state | `submit_now`'s walk |

The three user-data pairs are the V# bases that `timeout_probe` reads as `s[8:11]`, `s[20:23]` and `s[24:27]`
(exp 0160). They are what exp 0404 calls "the probe's `s[8:11]`-style bases".

The writers are those that `backend/src/full_state.cpp` follows (ADR 0008), read with the same layouts:

- `SET_CONTEXT_REG` 0x69, `SET_SH_REG` 0x76, `SET_SH_REG_INDEX` 0x9b.
- `LOAD_CONTEXT_REG` 0x61 and `LOAD_SH_REG` 0x5f: (offset, count) ranges, with the values at address + 4 × offset.
- `LOAD_CONTEXT_REG_INDEX` 0x9f and `LOAD_SH_REG_INDEX` 0x63: (offset, value) pair tables when `DATA_FORMAT` (dword 3
  bit 31) is set, otherwise a range starting at the offset in dword 3 bits 15:0.
- `CLEAR_STATE` 0x12:
  - cmd 0 forgets the context;
  - cmd 1 pushes `VGT_SHADER_STAGES_EN` (8 deep) and forgets it;
  - cmd 2 pops it.

  This is the host's state-stack emulation (`Device::set_state_stack(true)` in `init_once_locked`). SH registers are
  not touched, as in `full_state`.
- `SET_BASE` 0x11 index 1: `(dw1 & 0xf) == 1`, address in dwords 2-3, as `submit_now`'s walk and `host_indirect.hpp`
  ("one base-1 register") read it.

Three things make a value **unknown**:

- A table that the reader (`covered_sorted`) refuses.
- An `INDIRECT_BUFFER` 0x3f or 0x33. These are not followed, so they may set anything.
- `CLEAR_STATE` cmd 0, and a pop on an empty stack.

No table length is clamped (lesson R28). Type-0 packets and the other SET and LOAD forms are not followed, because the
policy NOPs them (`backend/policy/pm4-policy.tsv`: `type0 drop`; 0x77, 0x51 and 0xb8-0xbe are not listed, so the
default is drop).

**COND_EXEC** (0x22, 5 dwords; dword 4 bits 13:0 count the dwords skipped after the packet, as the mec rebuild and
`ib_cond_past_end` read them):

- At its start the walk keeps a snapshot of the state.
- At its end it merges the snapshot into the state (lesson R22: taken and skipped are merged). A register then holds
  one of two values, or becomes unknown past two (`FlVal`).
- A range that ends inside a packet ends with that packet. A range that runs past the buffer ends at the buffer's end.
- Ranges that overlap are closed one at a time, and the result is still a superset of the possible states.
- With more than 32 ranges open, everything is unknown from there on.

**Carrying the state.** `g_fl_state` (under `g_fl_mutex`, inside `g_dev_mutex`) carries the state from buffer to
buffer, in `submit_now`'s order, which is the GFX ring's order. That is the way `g_carried` carries `base1` and the
program.

- Every GFX-class buffer on the GFX ring is followed: cc, hib, dcb, dcb-state, host prefixes, and chains of that
  class. An acb buffer is followed too when it runs on the GFX ring, since it shares the context. An acb on a compute
  ring is not followed.
- Draws are planned only in buffers whose kind starts with `dcb`.

**Classes.** "Fast-launch" means that the `GS_FAST_LAUNCH` field (bits 20:19, gfx10.json) is not 0; exp 0404's
`0x482030` has field value 1. TODO(verify) what the field does on gfx1013. A draw's class is one of:

| Class | Meaning |
|---|---|
| 3 | fast-launch, for every possible value |
| 2 | maybe: one of two values after a COND_EXEC range |
| 0 | unknown |
| 1 | not fast-launch: neither planned nor counted beyond `not_fl` |

The draws are the draw half of `backend/src/policy.cpp` `is_draw_or_dispatch`: 0x24, 0x25, 0x27, 0x2c, 0x2d, 0x35,
0x38. A draw the caller already drops (`drop_offsets` before the scan) is not planned.

**The plan.**

- `BC5_DIRECT_FL_SKIP_ES` drops a draw only when **both** of these hold:
  - its class is 3;
  - every possible `SPI_SHADER_PGM_LO_ES` value is in the list.
- `BC5_DIRECT_FL_CRUMBS` gives crumbs to every planned draw that is not dropped, of class 3, 2 or 0. Unknown state is
  instrumented as well, so that the catcher does not miss the draw that hangs; the cost is counted (section 4).
- The CP copies:
  - **Arguments:** for 0x24, 0x25, 0x2c and 0x38, 16 bytes at `(base1 + dw1) & ~3`, but only when base1 is certain
    and not 0. For the multi forms this is the first record. For 0x25 it is the first 16 of its 20 bytes
    (VkDrawIndexedIndirectCommand, `draw_args.hpp`).
  - **V# data:** 32 bytes at each base `lo | (hi & 0xffff) << 32`, aligned down to a dword, when both halves are
    certain and the base is not 0.
- A range is copied only when its bytes **plus 4** are readable. The policy checks 8 bytes at every `COPY_DATA` source
  (`policy.cpp` `memory_operands`), so the last 32-bit copy is checked 4 bytes past the range. Without the extra 4 the
  filter could NOP that copy unseen, and the entry would still look complete. A case in the test covers this.
- The CPU reads the same bytes at submit (`snap`), so the probe can print them beside the CP's copy.

### 2.3 The crumbs and how they are inserted (chain and not)

These are the packets laid around a draw, in order:

```
WRITE_DATA  ring[e].head   = id      (entry e = ordinal of the draw with crumbs in this submission, mod 64)
COPY_DATA   x 4            arguments -> ring[e] + 8 ...      (when copied)
COPY_DATA   x 8 per base   V# bytes  -> ring[e] + 24 + 32 b  (when copied)
WRITE_DATA  ring[e].tail   = id
WRITE_DATA  issued         = id
            [the backend's own draw check, BC5_DIRECT_GPU_CHECK, lands here: indirect_check puts it right before the draw]
<the title's draw>
RELEASE_MEM done = id, end of pipe
```

`fl_build` makes a copy of the buffer that `submit_now` received, with the crumbs in it. This happens after the walk
and after the submission number `n` is known, in the same place and the same way as the mec rebuild:

- `opt.drop_offsets` and `opt.keep_wait_offsets` are mapped old to new.
- `fl_back` maps the executed offsets back, after both submits (the first one, and the EFAULT retry), as `mec_back`
  does.
- The soft-CP marks, the label registry and the drop tally therefore still see the buffer's own offsets.
- The two rebuilds never meet: the mec rebuild is for compute-class buffers and the crumbs for dcbs. If both ever
  applied, the crumbs would be refused and counted.

Because the copy is made inside `submit_now`, one path serves every submission:

- **A chain** (ADR 0010, `chain_submit` → `submit_now(mine.buf, …, &mine)`) is instrumented as one buffer. Each draw
  also gets its segment and its offset in the segment's buffer (`seg`, `seg_at`) from `chain->segs`.
- **The non-chain path** (`submit_one`, a prefixed piece's `one`, the GE probe's instrumented copy) is instrumented the
  same way.
- No edit of `chain_append` or `submit_prefixed` is needed.

The id's offset is the draw's offset in the buffer `submit_now` received. That is also the offset in the
`ib-timeout-*.bin` dump, because the probes get the buffer **without** the crumbs (section 5). In exp 0404's run that
buffer was the title's dcb itself (14,187 dwords), so the offset is the title's dword offset. With a chain or a
prefixed piece it is the offset in that buffer, and the probe also prints the segment and the segment offset.

**COND_EXEC.** The buffer's own COND_EXEC counts grow by the crumbs inside their ranges. A draw's crumbs, before and
after it, belong to the draw and are skipped with it. A range's end is measured at the start of the next packet's
unit, its crumbs included, so the crumbs of a draw that follows a range stay outside the range. A range whose grown
count would no longer fit in 14 bits keeps its draws without crumbs; they are counted (`cond_full`, journaled), and
the copy is laid again, up to 64 attempts.

### 2.4 What "issued" and "done" mean (lessons R12, R13, R25)

- **issued = X** means that the ME processed the crumbs in front of X, the last packets before X's host check. It does
  not mean that the draw passed the check: a draw the check skips is still issued, and then done.
- Exp 0404 proposed "after the host check". That cannot be done from the unit: the backend inserts its check when it
  filters, after the unit has submitted the buffer, and the backend is not edited here.
- **done = X** means that the end-of-pipe event after X completed, so all work before it is finished.
- **The first not done** is the next draw with crumbs after the draw `done` names. If `done` names none of this
  buffer's draws, it is the buffer's first draw with crumbs. The last issued draw is not taken for the first unfinished
  one: the probe lists every draw from the first not done up to the last issued, at most 64. This assumes that
  end-of-pipe events retire in order. TODO(verify) on gfx1013; it is the same assumption as exp 0404's label reading.
- **The ring entry.** Its head and tail tell whether the entry belongs to the draw:

  | State | Meaning |
  |---|---|
  | complete | head and tail name the draw |
  | begun | the CP stopped inside the copies |
  | overwritten | the ring wrapped within this submission, more than 64 draws with crumbs later |
  | never written | head is 0 |

  The copy is printed with a "NOT this draw's" mark unless the entry is complete. A wrap in the buffer is said in
  the summary line.
- **What the copy is.** It is a CP (ME) read made just before the draw's check (R12). It is not the ES shader's fetch,
  which happens later and through other caches. It shows what memory held when the CP reached the draw.

## 3. Sources of every packet field

| Packet | Dwords | Field | Value | Source |
|---|---|---|---|---|
| WRITE_DATA | 6 | header | `0xC0043700` = PKT3(0x37, count 4) | `backend/src/indirect_check.cpp` `kWriteData` (count 3, one data dword) + 1 data dword; Mesa sid.h `PKT3_WRITE_DATA` |
| | | dword 1 | `0x00100500`: DST_SEL 5 (memory, bits 11:8), WR_CONFIRM (bit 20), ENGINE_SEL 0 = ME (bits 31:30) | `indirect_check.cpp` `kWriteDataMem`, `kWrConfirm` (from Mesa sid.h); `policy.cpp` `memory_operands` reads DST_SEL bits 11:8 |
| | | dwords 2/3 | address lo & ~3, hi & 0xffff | `indirect_check.cpp`; `policy.cpp` `addr(2, 3)` |
| | | dwords 4/5 | id lo, id hi | `policy.cpp`: `(len - 4) * 4` bytes of data |
| COPY_DATA | 6 | header | `0xC0044000` = PKT3(0x40, count 4) | `indirect_check.cpp` `kCopyData` (Mesa sid.h `PKT3_COPY_DATA`; `ac_emit_cp_copy_data`, ab2374a) |
| | | dword 1 | `0x00100501`: SRC_SEL 1 memory (bits 3:0), DST_SEL 5 memory (bits 11:8), WR_CONFIRM, ME, 32 bits (no COUNT_SEL, bit 16) | `indirect_check.cpp` `kCopyMemToMem`, exp 0380's argument copy, which ran on this GFX ring |
| | | dwords 2/3, 4/5 | source, destination (lo & ~3, hi & 0xffff) | `indirect_check.cpp`; `policy.cpp` `addr(2, 3)`, `addr(4, 5)` |
| RELEASE_MEM | 8 | header | `0xC0064900` = PKT3(0x49, count 6) | `backend/src/direct.cpp:1098` (job timestamp) |
| | | dword 1 | `0x528`: event 0x28 BOTTOM_OF_PIPE_TS, EVENT_INDEX 5 (bits 11:8), GCR bits 0 (no cache action) | `direct.cpp:1098`; `policy.cpp`'s CS_DONE rewrite uses the same shape; gfx10's GCR field bits from `pkt3.json` `RELEASE_MEM_OP` |
| | | dword 2 | `0x40000000`: DATA_SEL 2 (bits 31:29), the 64-bit value of dwords 5/6; DST_SEL 0; INT_SEL 0 | the DATA_SEL field from `direct.cpp:1098` (DATA_SEL 3) and `policy.cpp`/`timeout_probe` (`w[2] >> 29`; the probe takes everything except 1 as 64-bit). Value 2 = "send 64-bit data" in Mesa sid.h's `EOP_DATA_SEL` comment. **TODO(verify)** that wording at `fe554882` on the box (`grep -n EOP_DATA_SEL ~/src/mesa/src/amd/common/sid.h`). |
| | | dwords 3/4 | done address lo & ~3, hi & 0xffff | `policy.cpp` `addr(3, 4)`; `timeout_probe` |
| | | dwords 5/6/7 | id lo, id hi, 0 | `timeout_probe` (`w[5]`, `w[6]`); `direct.cpp:1098` (dword 7 = 0) |
| COND_EXEC (title's) | 5 | dword 4 bits 13:0 | count, grown | `submit_now`'s mec rebuild; `ib_cond_past_end`; `indirect_check.hpp` (`ac_emit_cp_cond_exec`, 0866ae7) |

Registers, from `tools/bc5-agc/regdb/gfx10.json` (Mesa `fe554882`): `VGT_SHADER_STAGES_EN` 0x28b54 with
`GS_FAST_LAUNCH` bits 20:19; `SPI_SHADER_PGM_LO_ES` 0xb320; `SPI_SHADER_PGM_HI_ES` 0xb324 with `MEM_BASE` bits 7:0;
`SPI_SHADER_USER_DATA_GS_0` 0xb230 and `GS_31` 0xb2ac. They were read with a script on the laptop. The CPU test checks
every constant and the exact dwords, with literals of its own.

## 4. Costs

**Off** (the default):

- `fl_plan_buffer` tests two static flags and returns.
- `opt.mapped` makes one compare per memory operand against `fl_area == 0`.
- `fl_after` is skipped, because the plan is empty.
- Each `PendingJob` carries an empty `FlPlan` (one empty vector and some counters).
- Nothing is inserted or dropped, and nothing reaches the GPU differently: the off path is byte-identical in behaviour.

**On:**

| Where | Cost |
|---|---|
| CPU | A second walk of each GFX-class buffer (`fl_scan`). A copy of each dcb with crumbs. Reads of 20 + 3 × 36 bytes per planned draw. About 200 bytes of plan per draw, kept in the job until completion. |
| GPU, per draw with crumbs | 3 `WRITE_DATA` (18 dwords), up to 28 `COPY_DATA` (168 dwords, 4 + 3 × 8) and 1 `RELEASE_MEM` (8 dwords): at most **194 dwords**, 31 write-confirmed CP writes, and one end-of-pipe event. A direct draw without bases costs 26 dwords. |
| GPU, overall | At F208's count of ~3.5k fast-launch draws a second: up to about 680k dwords and 3.5k end-of-pipe events a second, plus the confirmed-write latency on the ME, which is serial and not measured. Exp 0404's estimate was three packets and one event per draw; the copies are 32-bit ones, so there are more of them. |
| IB size | A dcb grows by at most 194 dwords per such draw. The backend cuts jobs over 0xf0000 dwords into up to 4 IBs (exp 0349). A 14k-dword dcb stays far below that. |

This is a catcher build only. The extra end-of-pipe events load the EOP-done FIFO, the very unit whose
`EOPD_FIFO_NEEDS_SC_EOP_DONE` is in the hang's signature, and the confirmed writes slow the ME. The catcher can
therefore change the timing it watches, or hide the hang (R12).

## 5. Journal lines, and what the timeout probe prints

**First use** (static, at the first `submit_now`):

```
exp 0404: fl crumbs on (the fast-launch draws of each dcb: issued/done crumbs and their inputs copied by the CP into the GDS shadow +0x8000; read at a fence timeout)
exp 0404: fl crumbs off
exp 0404: fl skip es 0x11d00cde,0x11d00f85,0x11d00f8d (SPI_SHADER_PGM_LO_ES values: the programs at 0x11d00cde00, 0x11d00f8500, 0x11d00f8d00 while SPI_SHADER_PGM_HI_ES is 0; ...)
exp 0404: fl skip es off
exp 0404: fl skip es off (BC5_DIRECT_FL_SKIP_ES="..." does not parse: ...)
```

**Sampled** (the first 16, then every 4096th):

```
fl skip es (exp 0404): submit #N dcb op 24 at Q: es 11d00f85, stages 00482030: dropped (K so far)
fl crumbs (exp 0404): submit #N dcb op 24 at Q (+Q' in the copy), entry E: stages 00482030 es 11d00f85, arguments 0x..., V# bases 0x... 0x... 0x... (K draws so far)
fl crumbs (exp 0404): submit #N dcb: D draws left without crumbs, a COND_EXEC count would not fit 14 bits (K so far)
```

**Once and periodic:**

- Once: the layout (issued, done and ring addresses).
- Every 16,384 buffers with crumbs, a summary: buffers, draws, maybe, unknown, COND_EXEC full, skipped, refused.

**At a fence timeout**, `fl_probe` runs before `timeout_probe`, whose lines take long, and fsyncs the journal:

- In the sync path it runs in `submit_now`.
- In the async path it runs in `completion_thread`. There, `j.dev_gen == g_dev_gen` must hold, or it says the device
  was opened again and the crumbs are gone.

```
fl crumbs (exp 0404): at the timeout of submit #N dcb: issued #lo +off, done #lo +off (...); C draws with crumbs of T (F fast-launch, M maybe, U unknown state), S skipped (es), X without crumbs (COND_EXEC full)[; the ring wrapped in this buffer]: <reading>
fl crumbs (exp 0404):   the last done: op .. at .. (chain segment k +o; +o' in the copy), entry e complete (head #.. +..): stages .., es hi .. lo .., c COND_EXEC ranges open
fl crumbs (exp 0404):   FIRST ISSUED, NOT DONE: op 24 at 12037 (...), entry 5 complete (...): stages 00482030, es hi 00000000 lo 11d00f85, ...
fl crumbs (exp 0404):     arguments at 0x1193ad4f20: CP before the draw 00000d97 00000001 00000000 00000000 | CPU at submit ... | CPU now ...
fl crumbs (exp 0404):     s[8:9] V# base at 0x1123502050: CP before the draw <8 dwords> | CPU at submit <8> | CPU now <8>
fl crumbs (exp 0404):     s[20:21] V# base ... / s[24:25] V# base ... (or "not copied (...)")
fl crumbs (exp 0404):   issued, not done: op .. at .. ...      (up to 64 lines, to the last issued)
```

`<reading>` is one of four:

- `issued names no draw with crumbs of this buffer`. The probe then shows the buffer's first draw with crumbs and its
  data.
- `the draw issued last is done`. It shows that draw.
- `the draws issued and not done follow`. It shows them as above.
- `done names a draw after ...: inconsistent`.

`timeout_probe` and the async `ib_copy` get the buffer without the crumbs, with the executed offsets mapped back. The
`ib-timeout-*.bin` dump and the probe's offsets therefore line up with the crumbs' offsets and the offline tools
(`raw0403.py`). The devcoredump's IB #0 does contain the crumbs: the printed "+N in the copy" offsets give their
positions.

## 6. Tests and what was run (2026-11-03/04, laptop only; nothing ran on the box)

- `python mkfl0401.py <e3 unit> <out> <inc dir>` printed `df12bb2de3e90b8c82a234eedf0babb5`. Run again on its own
  output, it refuses: "the unit has exp 0404's switches already".
- Against the e3 unit, the diff has additions only, except three replaced lines: `opt.mapped`'s head, the sync
  `timeout_probe` call and the async `ib_copy` line. `fl_scan.inc` is byte-equal to the unit's block (`cmp`).
- `clang++ 22.1.3 (MSVC target) -std=c++20 -Wall -Wextra -Werror -I<inc dir> fl0401.cpp` compiled, and the test
  printed `fl0401: 74 of 74 cases; end` with rc 0. The cases are:
  - one draw, with its exact 186 + 8 crumb dwords and the maps both ways;
  - not fast-launch;
  - the skip in and out of the list, with and without crumbs;
  - pair tables of both spaces, unreadable tables, offset-format and plain LOAD ranges, `SET_SH_REG_INDEX`;
  - state carried from a buffer that is not a dcb;
  - COND_EXEC: a draw inside (count grown by exactly its crumbs), a range ending inside the draw, nested ranges, a
    range that cannot grow (no crumbs, count unchanged), and one whose only draw is in it;
  - state written inside a range: maybe, not dropped, the same value certain, ES of one of two values, `SET_BASE`
    uncertain;
  - `CLEAR_STATE` push, pop and cmd 0, and a push inside a range;
  - `INDIRECT_BUFFER`;
  - the multi-draws 0x2c and 0x38, and 0x25, 0x27, 0x35;
  - the caller's drops;
  - V# bases that are 0, unmapped, misaligned, or without the 4 bytes after;
  - the ring wrap after 64 draws, and a cut last packet;
  - `fl_find`'s four readings, and the four entry states;
  - the list parser, value merging, the layout and the packet constants.
- Mutation check (scratch, not committed): 13 mutants of `fl_scan.inc`. 12 were caught: no COND_EXEC growth, no merge
  at a range's end, the wrong SRC_SEL, no pair tables, no ring wrap, no push, a drop of maybe draws, no exclusion of
  full ranges, a broken unit start, issued written to done, an uncertain base copied, and an unequal stack merge (that
  one crashes). One survived, and it is equivalent: `unit_at` and `old_to_new` mark the same packet starts.
- The unit-only part (`FL_GLUE` and the `submit_now`, `PendingJob` and completion-thread edits) was compiled with
  `-fsyntax-only -Wall -Wextra -Werror`, and again with `-Wshadow`, against stubs of the unit's names. `journal`'s
  printf attribute checked every format.
- **Not done:** the full unit was not compiled, because the KytyPlus headers are not on the laptop (lesson R02). On
  the box:
  - build the unit;
  - run `clang++ -std=c++20 -Wall -Wextra -Werror -I<dir> fl0401.cpp` in the container and expect
    `fl0401: 74 of 74 cases; end`.

  No GPU run was made.

## 7. Doubts and open points

1. **GS_FAST_LAUNCH's meaning** on gfx1013 is TODO(verify). The predicate is the field, not the exact `0x482030`. It
   is a superset of that value.
2. **"issued" lies before the backend's draw check**, not after it (section 2.4). The probe cannot tell whether the
   check let the draw run.
3. **End-of-pipe events are assumed to retire in order**; `fl_find` relies on it. TODO(verify).
4. **What the copy shows** is a CP read before the draw's check, not the shader's fetch (R12). The shader's own inputs
   may be elsewhere: the V# positions s[8:9], s[20:21] and s[24:25] are the timeout probe's choice (exp 0160), not a
   decode of the ES program.
5. **The catcher changes timing** and loads the EOP FIFO, which is in the hang's signature. A clean play with the
   crumbs on is a weak result, not a fix.
6. **Draws of unknown state get crumbs too.** There are costs, counted in the summary: after an IB2, `CLEAR_STATE`
   cmd 0, or an unreadable table. Draws in an IB2 are not instrumented (not walked); none is expected in the title's
   dcbs (exp 0404's dcb has none listed).
7. **The ring holds 64 entries per submission.** If more than 64 draws with crumbs were issued past the stuck one, its
   entry is overwritten, and the probe says so. The free area allows about 380 entries, but exp 0404 asked for 64.
8. **32-bit copies only**, the exact form exp 0380 ran on this ring. `COUNT_SEL` 64-bit copies would halve the copies,
   but memory-to-memory 64-bit `COPY_DATA` has not run here (TODO(verify) before using it).
9. **The submission number in the sync path.** The crumbs and `fl_probe` use `n`, while `timeout_probe`'s file name
   uses `g_submits.load()`, which is `n + 1` there. The async path uses `j.n` for both.
10. **Chains and prefixed pieces.** The offset is the one in the buffer `submit_now` got. For a piece split at a wait,
    the part's start in the title buffer is not recorded by `ChainSeg` or `submit_prefixed`, so `seg_at` is the offset
    in the part.
11. **A failed submission** (not executed: `-ENOMEM`, a refused cut) still advanced `g_fl_state`. The model then
    diverges until the next certain writes.
12. **Found in passing, not changed: a latent bug in the mec rebuild** (`submit_now`, `BC5_DIRECT_MEC_INDIRECT`, off by
    default, compute buffers only). A COND_EXEC range's end is measured at `old_to_new[e]`, which is the rebuilt
    dispatch itself, after its inserted `SET_BASE` and `PFP_SYNC_ME`. A range that ends right before a rebuilt dispatch
    therefore swallows that dispatch's `SET_BASE`, and when the range is skipped the dispatch runs on the old base.
    `fl_build` measures range ends at the unit start (`unit_at`) for this reason.
13. **Matching the devcoredump.** The PFP and ME header histories of a crumbed build will show the crumbs.
    `pfpmatch0404.py`-style matching must take them into account; the copy offsets are in the journal lines.
