# 0404 — the 22:54 draw-class hang, read with the table catcher

## Question

At 2026-11-03 22:54:46, after about 10 minutes of the maintainer's play, the GPU hung:
- `gfx_0.0.0` ring timeout; the ring reset failed and the watchdog rebooted the box.
- Binary `exp0401e2` 35ff82eb, with JobArenaFix on, `BC5_DIRECT_ACB_INHERIT=journal` and `BC5_DIRECT_TABLE_CATCHER=1`.
- GRBM_STATUS 0xa2712028, the draw class (F588/F660, F813).

At the timeout of dcb #595662, the table catcher reported 226 slots hashed and 3 changed. All three are
`DISPATCH_INDIRECT` argument slots: 0x11d0571b00 0x788 → 0x20e8, 0x11d0571d00 0xca → 0, 0x11d05df100 0x6ec → 0.

1. Are those changes the GPU's own producers writing indirect arguments in the same dcb, or a write the console would
   order differently?
2. Where does the CP stall, per the devcoredump: which packet of the dcb?
3. Does it match the 08:53 draw-class hang, and does it relate to F403?
4. What catcher or fix should go in as a switch?

## Setup

Read-only `ssh bc250`, with the emulator guard before every command; no writes, no game, no GPU tools. Inputs, private
and not committed (the dcb and the devcoredump were copied to a laptop scratch outside git):
- `~/bc5-data/captures/play-20261103-2244/gc/direct.log` (the timeout probe and catcher lines, 1666250–1667295);
- `~/bc5-data/captures/play-20261103-2244/gc/ib-timeout-00595662-dcb-14187.bin` (the title's dcb, 14,187 dw; its
  `.tfring.bin` is empty);
- `~/bc5-data/captures/devcoredump/20261103-225446-devcd1.txt` (registers plus the host's filtered IB #0, 15,272 dw);
- `~/bc5-data/captures/gpu-stall/event-20261103-225445-gfx_0.0.0/` (five register samples, PFP/ME header histories);
- for Q3: `~/bc5-data/captures/gpu-stall/event-20261103-085304-gfx_0.0.0/`,
  `~/bc5-data/captures/play-20261103-0849/gc/direct.log`, and the note `hangs-20261103-0849-0853.md` in the
  side-session notes.

Tools:
- `experiments/0403-acb-program-inheritance/raw0403.py`: the title-dcb packet lister.
- `hostpk0404.py`: the same lister for a devcoredump's IB #0.
- `pfpmatch0404.py`: finds the place in IB #0 whose packets match the PFP header history.
- `refs0404.py`: finds every dword of a dump that names a given address.
- `drawcheck0381.py` (exp 0381 branch): verifies the host's indirect-draw check before each draw.

Bit names:
- `GRBM_STATUS*` and `CP_CPF_*`: Mesa's `tools/bc5-agc/regdb/gfx10.json`;
- `CP_STALLED_STAT1/2` and `CP_BUSY_STAT`: Linux v7.2 `drivers/gpu/drm/amd/include/asic_reg/gc/gc_10_1_0_sh_mask.h`,
  fetched from github.com/torvalds/linux at tag v7.2.

## Result

### 1. The three changed slots are the dcb's own GDS → argument copies, correctly ordered, and completed

The slots are filled in this dcb from GDS. Title dwords:

| dw | packet | what it does |
|---|---|---|
| 10037 | `DMA_DATA` 0xc6106000 | SRC_SEL DATA → DST_SEL GDS, 20 bytes of 0: clears five GDS counters |
| 10111 | `DISPATCH_DIRECT` 72×117, initiator 0x8041 | the producer, program 0x11d0369e00 |
| 10116, 10118 | `EVENT_WRITE` 0x407 (CS_PARTIAL_FLUSH), `ACQUIRE_MEM` | waits for the producer |
| 10126 … 10234 | five `DMA_DATA` 0xa6300000, each followed by `EVENT_WRITE` 0x407 and `ACQUIRE_MEM` | CP_SYNC, SRC_SEL GDS → DST_SEL L2 memory, 4 bytes: GDS +0/+4/+8/+0xc/+0x10 into the X of 0x11d0571b00 / 0x11d0571d00 / 0x11d0571f00 / 0x11d05df100 / 0x11d05df300 |
| 10278 … 10398 | five `SET_BASE` + `DISPATCH_INDIRECT`, initiator 0x8041 | the consumers |

The DMA_DATA control fields follow Mesa `sid.h` (`S_411_SRC_SEL` bits 29–30, `S_411_DST_SEL` bits 20–21, `CP_SYNC`
bit 31).

**This is normal GPU-driven dispatch. The title's stream orders it fully:** producer, partial flush, a CP_SYNC copy,
and an `ACQUIRE_MEM` on the slot before each consumer. A console would run it in the same order.
- The "was" values are the previous frame's counts. The "now" values are this frame's: 8424 groups for counter 0, and
  0 for counters 1 and 3.
- The consumers finished. The end-of-pipe writes after them (title 10440–10480) hold their values: 0x18f00, 0xe02050,
  0x779a9.
- The probe's "groups 0 x 1 x 1" at 10398 reads 0x11d05df300 at the timeout, i.e. counter 4 of this frame.

So the catcher's three changes are expected, and they are not the hang. Zero-group indirect dispatches (counters 1, 3,
4) completed here.

### 2. Where the CP stops: the fast-launch draw at title 12037 does not finish

**Devcoredump and sampler registers** (five samples over 1.2 s, all alike):

| Register | Value | Bits set |
|---|---|---|
| `GRBM_STATUS` | 0xa2712028 | GE, GE_NO_DMA, PA, SX, SPI, CP busy; CB clean |
| `GRBM_STATUS_SE0/1` | 0x0d000004 | PA, SX, SPI busy |
| `CP_STALLED_STAT2` | 0x00230000 | `MEQ_TO_ME_NOT_RDY_TO_RCV`, `STQ_TO_ME_NOT_RDY_TO_RCV`, `EOPD_FIFO_NEEDS_SC_EOP_DONE`. No `ME_WAITING_ON_PARTIAL_FLUSH` (bit 15), unlike 10-29 18:08 (0x218000) |
| `CP_BUSY_STAT` | 0x00048400 | `RCIU_ME_BUSY`, `GFX_CONTEXT_BUSY`, `EOP_DONE_BUSY` |
| `CP_PFP_INSTR_PNTR` / `CP_ME_INSTR_PNTR` | 0xea0–0xea1 / 0x954–0x956 | — |

Further:
- No page fault (status 0; the recorded address 0 is the usual empty record).
- `CP_IB1_CMD_BUFSZ` is 0x3ba8 (15,272 dw, the host IB). `CP_IB1_BUFSZ` has 0x508 left, so the fetcher stands at
  host dword 13,984.
- The sampler's compute registers (program 0, DIM [0 1 1]) are an idle compute state.

**The PFP is at the host's draw check of title 12663, waiting for the ME.** The PFP header history, newest first:
`PFP_SYNC_ME`, `WRITE_DATA`, `COND_WRITE`, `COND_WRITE`, `WRITE_DATA`, `SET_BASE`, `SET_SH_REG` (19 dw),
`LOAD_SH_REG_INDEX` (5 dw).
- `pfpmatch0404.py` finds exactly one such run in IB #0: host 13,418–13,474. It is followed by `COND_EXEC` at 13,476 and
  `DRAW_INDIRECT` at 13,481.
- That draw is title 12663 (`drawcheck0381.py` maps host 13,481 to `data_offset` 0xbd00).
- `PFP_SYNC_ME` waits until the ME has drained, so the ME is behind it.

**The ME is several hundred dwords further back.**
- The ME history, newest first, is 0x52, 0x2c, 0x74, 0x53, 0x2c, 0x74, 0x53, 0x8f. It has none of the check's
  `WRITE_DATA` or `COND_WRITE`.
- In the 08:53 ME history a single `DRAW_INDIRECT` shows as 0x72, 0x24, 0x52. Read the same way, the 22:54 history is
  one `DRAW_INDIRECT_MULTI` (0x2c) with two sub-draws.
- The only count-2 multi-draw in the window is title 12356. TODO(verify): the ME history's opcodes are microcode-side
  and undocumented; this reading rests on the 08:53 pattern.

**The end-of-pipe markers say what did not finish.** Each `RELEASE_MEM` (event 0x28, EOP) writes the 64-bit value in
its packet when all earlier work is done. The probe read the labels at the timeout:

| Label | Writes in the dcb (title dw → low dword) | Value at the timeout | Last completed write |
|---|---|---|---|
| 0x1200006e00 | 11965 →939a6, **12045 →b47ff**, 12260 →95d27, 12530 →b5a0c, 12596 →939a6 | …939a6 | 11965 (see below) |
| 0x1200006e20 | 11986 →939a6, 12066 →b47ff, 12281 →95d27, 12550 →b5a0c, 12617 →939a6 | …939a6 | 11986 |
| 0x1200006de0 | 11901 →516c3f, 13094 →695e03 | …516c3f | 11901 |
| 0x1200006890 | 11875 →60004e, 13067 →600051 | …60004e | 11875 |

- If the writes at 12596/12617 had completed, then so would 12045 … 12550 before them. But the ME stands before 12663,
  and the draws between 12617 and 12663 have no unfinished work of their own. So the value …939a6 is the one written at
  11965/11986.
- **Every EOP from 12045 on is pending, and the first unfinished work lies between title 11986 and 12045.**
- The only draw there is title **12037**: a `DRAW_INDIRECT`, `data_offset` 0x1620 off `SET_BASE` 0x1193ad3900. Its
  arguments are 3479 vertices × 1 instance, sane, and unchanged since submit (it is one of the catcher's 226 slots).
  The host's draw check stands before it (`drawcheck0381.py`: "ok").
- Its state (the probe): `VGT_SHADER_STAGES_EN` 0x00482030 (fast-launch NGG), GE_CNTL 0x201, primitive type 1
  (points), ES 0x11d00f85, PS 0x11d01b8d, GS user data at 0x1123502050 / 0x2240fda0.
- The ME went on issuing draws behind it, up to about 12356, until the geometry engine stopped taking work. That fits
  `MEQ_TO_ME_NOT_RDY_TO_RCV` and `EOPD_FIFO_NEEDS_SC_EOP_DONE` (R21: a fit, not a proof).

**The garbage-argument draws at 12663–13056 are not the hang.**
- Their arguments (`SET_BASE` 0x1193ad3900 + 0xbd00 … 0xbde0) read 0x00110000, 0x00110001, …: index-like data, not
  draw arguments. They were already so at submit: the catcher hashed these slots and they did not change.
- The host check before each (limits 1,048,576 vertices and 64 instances) turns 0x110000 × 0x110001 into a skipped
  draw.
- The ME never reached the first of them.
- Why the title points eight draws at index-like data is a separate question. The console has no such check and would
  run them with whatever lies there, so what the title writes at +0xbd00 on the console is open. It does not bear on
  this hang.

### 3. Same class as 08:53; not F403

**08:53:04 (exp 0379 binary, `event-20261103-085304`) has the identical signature:**
- GRBM_STATUS 0xa2712028, `CP_STALLED_STAT2` 0x00230000, PFP 0xea0–0xea1, ME 0x955.
- PFP history: `PFP_SYNC_ME`, then the host's draw check, `SET_BASE` and two `SET_SH_REG` (18 and 19 dw).
- ME history: the check, then one `DRAW_INDIRECT`.
- Fast-launch state 0x482030 before every draw, Render Thread, no page fault.
- Its draws ran ES 0x11d00f85 / 0x11d00f8d (and 0x11d00cde) with the same PS family, as here. Which of them hung at
  08:53 is not known.

**The 10-29 18:08, 10-31 17:04 and 11-02 00:11 hangs (F588, F660, F813) are the same draw class.** 18:08 differs in one
CP bit: the ME also waits on a partial flush (0x218000).

**Not F403.**
- F403 is a compute dispatch that does not end, with GRBM_STATUS 0xa0407028 and the ME at 0x77a–0x77b.
- Here the ME is at 0x954–0x956, TA and the compute registers are idle, and GE/PA/SX/SPI are busy.
- One link: 0x11d0571b00 is F813's F403 sub-class B slot. This dcb shows that slot being filled from GDS counter 0 by a
  CP_SYNC `DMA_DATA` after a fenced producer. So a garbage COMPUTE_DIM in sub-class B would come from the GDS counter's
  value, not from a missing barrier in the stream. That is a lead for F403-B, not a cause of this hang.

### 4. Proposed switches (design; not built)

**The cause is open.** A sane-argument fast-launch draw does not finish. Per F208, what such a draw does depends on the
data its ES fetches at run time, which no probe has seen as the GPU saw it (F675: the probe reads 2 s late). So the
first switch is a catcher.

1. **`BC5_DIRECT_FL_CRUMBS=1` (catcher, default off).** For every draw whose tracked `VGT_SHADER_STAGES_EN` is
   fast-launch (0x482030) in a dcb, the host adds:
   - Before the draw (after the host check): `WRITE_DATA` (ME, WR_CONFIRM) of `(submit#, title dw)` to a host slot,
     "issued".
   - After it: `RELEASE_MEM` EOP of the same pair to a second slot, "done". The values are unique, unlike the title's
     recurring marker IDs above.
   - Before the draw: `COPY_DATA` (memory → memory, executed by the CP at that point) of the draw's 16 bytes of
     arguments and the first 32 bytes at each ES/GS V# base in its user data (the probe's `s[8:11]`-style bases), into
     a per-submit host ring of 64 entries. This is the data as the GPU fetched it.
   - The timeout probe prints both slots and the ring entry of the draw that was "issued" but not "done". That names the
     unfinished draw directly, and gives its inputs at execution time to diff against healthy instances (F208's
     method).
   - Cost: three packets and one EOP event per fast-launch draw (F208 counted ~3.5k such draws a second). It is a
     catcher build only.
2. **`BC5_DIRECT_FL_SKIP_ES=<list of ES program addresses>` (diagnostic, default off).** It drops fast-launch draws
   whose ES program is listed, through `drop_offsets` (as `BC5_DIRECT_SKIP_PGM` drops dispatches).
   - Arms: 0x11d00f85 (this hang's draw), 0x11d00f8d, 0x11d00cde.
   - It narrows the class by program, the way F207 narrowed the BVH fault. It is not a fix: the scene's meshes go
     missing.

Per the fixes-first rule, both go into one private test build, each behind its own switch.
- A play with the crumbs alone settles which draw hangs and with what inputs.
- The skip arms are for after that, or for a play the maintainer accepts with missing meshes.

## Verdict

- **Q1.** The three changed slots are this dcb's own GDS-counter copies (`DMA_DATA` GDS → argument X, CP_SYNC). They
  sit after a partial flush behind the producer dispatch and an `ACQUIRE_MEM` before each consumer. That is normal
  GPU-driven dispatch the console orders the same way, and it completed before the stall.
- **Q2.**
  - The first unfinished work is the fast-launch `DRAW_INDIRECT` at title 12037 (sane arguments 3479 × 1, ES
    0x11d00f85).
  - The ME has issued work past it to about 12356. The PFP waits at `PFP_SYNC_ME` before the check of title 12663.
  - GE/PA/SX/SPI hold the work, and an end-of-pipe event waits on the scan converter.
  - Evidence: the end-of-pipe markers (High), the unique PFP history match (High), the ME-history reading (Medium,
    TODO(verify)).
- **Q3.** The same draw class as 08:53 (identical CP and GRBM signature), 11-02 00:11, 10-31 17:04 and 10-29 18:08. Not
  F403. The only link is that F403-B's slot 0x11d0571b00 is fed by GDS counter 0 through this copy.
- **Q4.** The cause is open. Next: `BC5_DIRECT_FL_CRUMBS` (the unfinished draw and its GPU-time inputs) plus
  `BC5_DIRECT_FL_SKIP_ES` arms, in one private build.

## Files

- `hostpk0404.py`: packet lister for a devcoredump's IB #0 (structure and register values).
- `pfpmatch0404.py`: finds the place in IB #0 matching the sampler's PFP header history.
- `refs0404.py`: lists the packets of a dump that name a given address.
- No dumps, logs, devcoredumps or probe output are committed. They hold the title's buffers; the paths above locate
  them on the box.
