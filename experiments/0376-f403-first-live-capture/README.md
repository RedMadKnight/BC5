# 0376 — The F403-class hang of 2026-10-29 09:48:26, the stall sampler's first live capture

**Date.** 2026-10-29 09:52–10:02 (reads only). **Box.** Read only, no GPU work, no emulator. The reads ran while the
top session's exp 0372 build held BOX-LOCK, whose line allowed 0376's reads (`top exp 0372 | … reads by exp 0376 are
fine`). The 0376 claim and done lines are in `~/bc5-work/BOX-QUEUE` and `~/bc5-work/exp0376/CLAIM.txt`.

**Question.** The resident stall sampler (version 0374, registers only, F522/F523) caught an F403-class GPU hang live
for the first time. Three questions follow:
1. What do its registers say the CP was doing for those 1.7 s, and what was it waiting on?
2. Which dcb timed out, and does it open with the indirect-dispatch family of R4 and F506?
3. Which instrument would name the stuck program without a wave scan (F520)?

## Setup

- **The event.** The maintainer was playing the second title with RT on, through the "BC5 emulator (test 0372)"
  shortcut (exp 0372's build, branch `exp/0372-pad-haptics-replug`). The kernel logged `ring gfx_0.0.0 timeout,
  signaled seq=578809, emitted seq=578811` at [11613.251] for kyty_emulator, thread `bc5-ring`. The ring reset failed,
  the full GPU reset began, and `bc5-gpu-watch` rebooted the box (`raw/sampler-event/kmsg.txt`).
- **Records read (private, cited by path).**
  - The sampler's event: `~/bc5-data/captures/gpu-stall/event-20261029-094826-gfx_0.0.0/`. Its own register values
    and fence lines are copied to `raw/sampler-event/`.
  - The devcoredump: `~/bc5-data/captures/devcoredump/20261029-094827-devcd1.txt` (409,525 bytes).
  - The play journal: `~/bc5-data/captures/play-20261029-0944/gc/direct.log` (497,813 lines).
  - The host's dump of the timed-out dcb: `ib-timeout-00183691-dcb-11115.bin`, in the same `gc/` directory.
- **Scripts.**
  - `hang0376.sh` (box, read only, the guard first; modelled on exp 0371's `hang0371.sh`) reads the devcoredump's
    register lines and the journal's timeout-probe lines. `raw/probe-extract.txt` is its output, filtered on the
    laptop: register lines, line counts, and the probe's submit, timing, dispatch, wait and summary lines. The probe's
    user-data, V# and TF-ring lines show title memory, and the label-write lines its values, so they are not kept
    (135 write lines dropped, counted at the end of the file). The unfiltered output never entered the repo.
  - `walk0376.sh` (box, read only) walks the dumped dcb's PM4 headers. It prints type-3 opcodes, offsets, the event
    type of `EVENT_WRITE` and the dims of `DISPATCH_DIRECT`, nothing else (`raw/dcb-walk.txt`).
  - `decode0376.py` (laptop) decodes every status field from Linux v7.2's
    `drivers/gpu/drm/amd/include/asic_reg/gc/gc_10_1_0_sh_mask.h`. The header came from git.kernel.org
    (`…/plain/…?h=v7.2`) because GitHub rate-limited raw downloads. Its git blob is `9b7d219e7954f2bab5a69a8d7eecb67d1f0a547b`,
    the same as tag v7.2 at github.com/torvalds/linux `8d3ae59288f1e7d58d76558a6ee96d533bc5019f`, the commit exps
    0373–0375 cite.
    - It compares the hang's five samples with the 9 healthy ASTRO BOT samples of exp 0375 that stand at the same CP
      pointers (PFP 0xea0–0xea1, ME 0x77b). Those samples' CP_* registers were read again from
      `~/bc5-data/captures/gpu-stall/forced-20261029-08*` (`raw/healthy-astro-0375-cp-regs.txt`).
    - Output: `raw/decode.txt`. Command: `python -I decode0376.py <dir>/gc_10_1_0_sh_mask.h raw/sampler-event
      raw/healthy-astro-0375-cp-regs.txt` (Python 3.14 on the laptop).
    - Mesa's `gfx10.json` (`tools/bc5-agc/regdb/`) has no CP_STALLED_STAT1–3, CP_BUSY_STAT or CP_STAT, so the Linux
      header is the source for every field named below.
  - **The class's other dumps.** The CP registers of the six earlier F403-class devcoredumps (10-26 10:08, 12:20,
    12:21; 10-27 07:28; R4 10-28 18:15; 10-28 23:36) were read the same way (`raw/class-dumps-cp-regs.txt`, values
    only).
- **Kernel.** 7.2.9-ogc3.1 (the devcoredump's `kernel:` line).

## Result

### 1. The CP is parked, not frozen: the ME spins in a partial-flush wait

**The five samples** (0.52, 0.82, 1.12, 1.42 and 1.72 s into the stall; `raw/sampler-event/regs-*.txt`):
- They differ only in `CP_ME_INSTR_PNTR` (0x77b, 0x77b, 0x77a, 0x779, 0x77b) and in one `CP_STAT` bit.
  - That bit is `SCRATCH_RAM_BUSY` (bit 24), set in sample 4: 0x9503a600 against 0x9403a600.
- Everything else reads the same in all five, and the devcoredump taken at the kernel's timeout agrees:
  - `CP_PFP_INSTR_PNTR` 0xea1;
  - `CP_IB1_BASE_HI` 0x100b, `CP_IB1_BUFSZ` 0x26c8, `CP_IB1_CMD_BUFSZ` 0x2e48;
  - both 8-entry header histories;
  - `GRBM_STATUS` 0xa0407028, SE0/SE1 0x0a000036, `CP_STALLED_STAT1/2/3`, `CP_BUSY_STAT`;
  - the gfx fence, signaled 0x8d4f9 against emitted 0x8d4fb (two jobs outstanding).
- So the command stream did not move for 1.7 s, while the ME's microcode walked three addresses: a wait loop.
- `SPI_CSQ_WF_ACTIVE_STATUS` reads 0 here and in every healthy sample, so it says nothing about these waves.
  TODO(verify): which queues it counts.

**The decoded fields** (`raw/decode.txt`):

| register | hang | healthy, same CP pointers (ASTRO BOT) | reading |
|---|---|---|---|
| `CP_STALLED_STAT2` | 0x00018000: `ME_WAITING_ON_PARTIAL_FLUSH`, `MEQ_TO_ME_NOT_RDY_TO_RCV` | 0x00218000: the same + `EOPD_FIFO_NEEDS_SC_EOP_DONE` (9/9) | the ME waits for a partial flush; the PFP's queue to the ME is full behind it |
| `CP_STALLED_STAT1` | 0xc00: `ME_HAS_ACTIVE_CE/DE_BUFFER_FLAG` | the same (9/9) | no stall bit |
| `CP_STALLED_STAT3` | 0x800: `CE_WAITING_ON_CE_BUFFER_FLAG` | the same (9/9) | the CE, idle in both |
| `CP_BUSY_STAT` | 0x400400: `RCIU_ME_BUSY`, `CE_PARSING_PACKETS` | 0x448000/0x468000/0x440000: `EOP_DONE_BUSY` (9/9), `GFX_CONTEXT_BUSY` (8/9) | healthy frames have end-of-pipe events in flight; the hang has none and only the ME's register interface busy |
| `CP_STAT` | 0x9403a600: … `DC_BUSY` | 0x94078600: … `QUERY_BUSY` | `DC_BUSY` only in the hang, `QUERY_BUSY` only healthy |
| `GRBM_STATUS2` | 0x52000008: `TCP_BUSY`, `CPF/CPG_BUSY` | 0x52130008: + `EA_BUSY`, `RMI_BUSY`, `EA_LINK_BUSY` (9/9) | **no memory traffic in the hang** |
| `GRBM_STATUS` | 0xa0407028: `TA_BUSY`, `SPI_BUSY`, `CP_BUSY`, `CB_CLEAN`, `DB_CLEAN` | 0xe5f14028: + `GE`, `SX`, `BCI`, `SC`, `DB`, `CB` busy | only compute is alive |
| `GRBM_STATUS_SE0/SE1` | 0x0a000036: `SPI`, `TA`, `TCP`, `GL1CC` busy, `CB/DB_CLEAN` | 0xee600030: + `RMI`, `BCI`, `SX`, `SC`, `DB`, `CB` busy | the same |
| `CP_CPF_STATUS`, `CP_CPF_BUSY_STAT`, `CP_CPF_STALLED_STAT1` | 0xb4000263, 0x6, 0x3 | the same | the fetcher looks alike in both |

- **What the CP waits on.** It waits on a partial flush, that is, for compute waves to end. Healthy frames wait in the
  same place, but there the flush resolves and EOP events are still pending behind it.
- **What separates the hang.**
  - No EOP is in flight (no `EOP_DONE_BUSY` or `EOPD_FIFO_NEEDS_SC_EOP_DONE`).
  - SPI/TA/TCP stay busy in both SEs while EA and RMI are idle. The waves that hold the flush are not reaching memory.
    TODO(verify): whether TA/TCP busy with EA idle means requests held in TA/TCP, or waves that spin without memory
    access.
- **The same in every F403-class dump** (`raw/class-dumps-cp-regs.txt`). `CP_STALLED_STAT1/2` (0xc00, 0x18000) are
  identical in all six earlier dumps. `CP_BUSY_STAT` 0x400400 and `GRBM_STATUS2` 0x52000008 hold in five; 10-27
  07:28, the one with F413's TCP fault, has 0x400000, 0x50000008 and SE0 0x08000006. That signature is new: earlier
  experiments read only GRBM, the pointers and the histories.
- **The 0x20 bit.** SE 0x0a000036 against F490's 0x0a000016 is bit 5 of `GRBM_STATUS_SE0`, `GL1CC_BUSY`
  (gc_10_1_0_sh_mask.h). The healthy samples have it too, and 10-26 10:08's class dump already read 0x0a000036
  (F490 noted it). So it is a passing state of the GL1 cache controller, not a sub-class.

### 2. The timed-out dcb, and the dispatch the ME waits for

**Which job** (`raw/probe-extract.txt`):
- dcb #183691 (11,115 dwords) and acb #183692 (84 dwords) both report `TIMEOUT` (2,036.7 and 2,036.4 ms). Both were
  done at host t 231.892 s, and the gfx fence was two jobs behind.
- The acb holds 0 dispatches, 0 waits and 6 label writes.
- The dcb holds 45 dispatches (7 indirect), 10 waits (6 kept for the GPU) and 129 label writes. Its largest grid is
  57,600 groups (320×180, at dword 7792), so there is no runaway grid. It is the third event of the class without
  one, after R4 (F491) and F506.
- The probe found an HS user-data address of 0, unmapped, at dword 9481, past the head, as in F506.

**The opening: F506's family behind a longer head.** The first dispatches:

| dword | packet | program | groups at the timeout | arguments |
|---|---|---|---|---|
| 1289 | `DISPATCH_INDIRECT` | 0x11d028dd00 | 0×1×1 | 0x11d0571f00 |
| 1329 | `DISPATCH_INDIRECT` | 0x11d0289c00 | 0×1×1 | 0x11d0571d00 |
| 1361 | `DISPATCH_DIRECT` | 0x11d02a0e00 | 13×8×1 | |
| 1420 | `DISPATCH_INDIRECT` | 0x11d02a1600 | 0×1×1 | 0x11d05df300 |
| 1470 | `DISPATCH_INDIRECT` | 0x11d02a1800 | 0×1×1 | 0x11d05df300 |
| 1520 | `DISPATCH_INDIRECT` | 0x11d028ae00 | 0×1×1 | 0x11d05df300 |
| 1550 | `DISPATCH_INDIRECT` | 0x11d02a1600 | 0×1×1 | 0x11d05df300 |
| 1582 | `DISPATCH_DIRECT` | 0x11d02a3200 | 13×8×1 | |
| 1651 | `DISPATCH_INDIRECT` | 0x11d02a2e00 | 3498×1×1 | 0x11d0571b00 |

- From 1420 on, this is F506's sequence (0x11d02a1600, 0x11d02a1800, 0x11d028ae00, 0x11d02a1600, then the 13×8 and
  0x11d02a2e00), shifted by +131 dwords. Two more indirect dispatches and a 13×8 direct one stand in front of it.
- The probe reads x = 0 at the timeout in the arguments of all six dispatches before 1651. F506's probe read 1295 at
  0x11d05df300. TODO(verify): what a `DISPATCH_INDIRECT` that reads x = 0 launches on gfx1013. The host's check
  passes x = 0, because it refuses only x above the limit (`backend/src/indirect_check.cpp`, `COND_WRITE`
  "greater").

**The header histories are newest-first, and they put the ME just past a dispatch.**
- The host's check before each `DISPATCH_INDIRECT` is 88 dwords (`backend/src/indirect_check.cpp`, main d0c2668):
  `WRITE_DATA`, `WRITE_DATA`, 3 + 2 `COND_WRITE`, `WRITE_DATA`, `PFP_SYNC_ME`, `COND_EXEC` (skips the x-limit
  `COND_WRITE` when y = z = 1), `COND_WRITE`, `WRITE_DATA`, `PFP_SYNC_ME`, `COND_EXEC`, then the dispatch.
- Read with entry [0] as the newest, both histories follow that sequence exactly, with the skipped `COND_WRITE` absent
  and the ME one packet behind the PFP:
  - PFP, oldest to newest: `PFP_SYNC_ME`, `COND_EXEC`, `WRITE_DATA`, `PFP_SYNC_ME`, `COND_EXEC`,
    `DISPATCH_INDIRECT`, `EVENT_WRITE`, `ACQUIRE_MEM`;
  - ME, oldest to newest: `COND_WRITE`, `COND_WRITE`, `WRITE_DATA`, `PFP_SYNC_ME`, `WRITE_DATA`, `PFP_SYNC_ME`,
    `DISPATCH_INDIRECT`, `EVENT_WRITE`.
- Read with [0] as the oldest, the ME would have parsed three packets the PFP had not, which cannot be.
- The newest-first reading also fits `ME_WAITING_ON_PARTIAL_FLUSH`.
- So the ME issued a `DISPATCH_INDIRECT` that passed the check (the `COND_EXEC` let it through), then took the
  title's `EVENT_WRITE` and waits on it. The PFP has parsed the `ACQUIRE_MEM` after it. This corrects F490's reading
  that "the ME stands in the check of the next indirect dispatch". TODO(verify): a public statement of the
  `CP_*_HEADER_DUMP` order; the reading above rests on the sequence match.

**Three candidate dispatches** (`raw/dcb-walk.txt`):
- In this dcb, the `EVENT_WRITE` right after a `DISPATCH_INDIRECT` is event type 7, `CS_PARTIAL_FLUSH`
  (`VGT_EVENT_TYPE`, Mesa `src/amd/common/sid.h`, TODO(verify) the line).
- Only three of the seven indirect dispatches are followed directly by `EVENT_WRITE` and `ACQUIRE_MEM`, as the PFP
  history requires:
  - 1289, program 0x11d028dd00;
  - 1420, program 0x11d02a1600;
  - 1470, program 0x11d02a1800.
- The other four are excluded. 1329, 1520 and 1550 are followed by `LOAD_SH_REG_INDEX` (0x63). 1651 is followed by
  `LOAD_CONTEXT_REG_INDEX` (0x9f) before its `EVENT_WRITE`; TODO(verify) that the PFP history records 0x9f.
- Each candidate's own flush is preceded by an earlier `CS_PARTIAL_FLUSH` that the CP has already passed (1366/1383
  before 1420, 1423/1433 before 1470, none before 1289 since 1289 is the first dispatch). So the flush the ME waits on
  covers one compute dispatch: **the stuck program is one of 0x11d028dd00, 0x11d02a1600 and 0x11d02a1800.** These
  registers cannot tell which of the three it is.
- 0x11d02a1600 and 0x11d02a1800 are in F491's family of R4 and F506.

**Where the fetcher stopped.**
- `CP_IB1_CMD_BUFSZ` − `CP_IB1_BUFSZ` = 11,848 − 9,928 = 1,920 dwords.
- R4 (12,248 − 10,328) and 23:36 (13,352 − 11,432) give 1,920 dwords too (`raw/class-dumps-cp-regs.txt`).
- The three dcbs differ in layout (here the family stands 131 dwords later), so the same count does not mark the same
  dispatch. TODO(verify): what `CP_IB1_CMD_BUFSZ` holds (11,848 is the title's 11,115 plus 7 × 88 check dwords plus
  117), and whether 1,920 is a fetch limit of the CP.

**Timing.**
- The sampler's stall clock started at mono 11610.472. The devcoredump's `time:` is 11612.488, 2.016 s later.
- The event was written at mono 11612.711 (its own clock 1.90 s), before the kernel's timeout line at printk
  [11613.251].
- TODO(verify): the dump's clock and the printk offset of this boot (F521 found −0.343 s in another boot).

### 3. What names the program without a wave scan

Exp 0370's three options, against what this capture shows:

- **(a) The host's dispatch journal against the stopped fence.** Used up here. The fence names the job (#183691), and
  the probe lists its dispatches. The journal cannot say which dispatch the GPU was on, and the narrowing to three
  came from the CP's histories, not from the journal.
- **(b) A register-only read of the compute dispatch registers.** Recommended.
  - Add to the sampler's 33 reads, byte offsets from `gc_10_1_0_offset.h` v7.2 plus `GC_BASE` 0x1260
    (`cyan_skillfish_ip_offset.h`, as the sampler):
    `COMPUTE_PGM_LO` 0xb830, `COMPUTE_PGM_HI` 0xb834, `COMPUTE_DIM_X/Y/Z` 0xb804/0xb808/0xb80c,
    `COMPUTE_DISPATCH_INITIATOR` 0xb800, `COMPUTE_START_X` 0xb810, `COMPUTE_NUM_THREAD_X` 0xb81c,
    `COMPUTE_PGM_RSRC1/2` 0xb848/0xb84c and `COMPUTE_DISPATCH_ID` 0xb880.
  - The ME stands right after the stuck dispatch, so no later `SET_SH_REG` or `LOAD_SH_REG_INDEX` has reached these
    registers. `COMPUTE_PGM_*` should then hold the stuck program's address, and `COMPUTE_DIM_*` the groups really
    launched, which settles the x = 0 question.
  - **Risk.** These are the same unhalted MMIO reads that F523 found safe (0.1–0.2 ms, 0 errors), ten more `pread`s.
    The open points are readback, not safety:
    - whether these SH registers read back the last value written on gfx1013;
    - which ME/pipe an unbanked read returns (`amdgpu_debugfs.c` v7.2 lines 97–118: bit 61 selects me/pipe/queue
      through `amdgpu_gfx_select_me_pipe_q`, and the default is 0/0/0, presumably the GFX ME0 pipe0).
  - These are settled offline (T0) and by forced samples under the second title (T1). In a healthy frame parked at
    PFP 0xea1 / ME 0x77b, `COMPUTE_PGM` must be a program from that frame's dispatch list.
  - It changes only the root sampler. The maintainer reinstalls it; the shared builds and the launchers stay as they
    are.
- **(c) The host records the last dispatch it handed over.** The host hands over whole IBs, so this means a
  breadcrumb packet per dispatch in the command stream (exp 0277's kind; F358's machine-down came on a breadcrumb
  run). It changes the stream and the shared builds (D19), and it records the last dispatch issued, which (b)
  already reads from the CP. Not recommended before (b).

## Findings (for HANDOFF)

- **F525** — the first live capture: the CP is parked in a partial-flush wait for 1.7 s, and the class has a
  CP_STALLED/BUSY signature.
- **F526** — the fields that separate the hang from a healthy frame at the same pointers: no EOP in flight, EA/RMI
  idle while SPI/TA/TCP stay busy. SE's 0x20 bit is `GL1CC_BUSY`, not a sub-class.
- **F527** — the header histories read newest-first. The ME issued a `DISPATCH_INDIRECT` and waits in the
  `CS_PARTIAL_FLUSH` after it, which corrects F490. Three candidates: 0x11d028dd00, 0x11d02a1600 and 0x11d02a1800.
- **F528** — dcb #183691 opens with F506's family, shifted, and its arguments read x = 0 at the timeout. The fetcher's
  1,920 dwords repeat in three events.
- **F529** — the recommendation: (b), the COMPUTE_PGM/DIM registers in the sampler.

## Verdict

**Answered.**
1. The CP is parked, not frozen: the ME spins in a `CS_PARTIAL_FLUSH` wait for compute waves that never end, with no
   memory traffic.
2. The timed-out dcb is #183691. It opens with F506's family behind a longer head, and the flush isolates one of three
   indirect dispatches: 0x11d028dd00, 0x11d02a1600 or 0x11d02a1800.
3. The next step toward the name is (b). Add the `COMPUTE_PGM_*` and `COMPUTE_DIM_*` registers to the resident
   sampler's register-only read: T0 offline, then forced samples under the second title for the readback, then the
   maintainer's reinstall. The risk is that of F523's reads. What can go wrong is a value that does not read back,
   not a hang.

Nothing on the box was changed apart from the claim lines. The shared builds and `play-pkg.sh` were not touched.
