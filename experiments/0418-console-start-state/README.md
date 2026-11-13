# 0418 — The console's start state: registers the system sets that the BC-250 may not hold

**Status: analysis only, on the laptop, 2026-11-13. No box access and no run.** The top session asked for it, passing on the maintainer's question once the night lake was closed (Q21, F785/F786). §3 proposes a read and §4 a rule; neither has been run or built.

**Question.** `VGT_HS_OFFCHIP_PARAM` held a value the title did not expect. On the console the system sets it, and here nobody did (F785). Are there other registers like that? The question has four parts:

1. Which registers does the title read without setting them, or does the console's system program at start?
2. Where do exp 0401's five registers stand?
3. How can we read what the chip holds without exp 0400's risk?
4. Does the list support one start-state table in place of a switch per register?

**Setup.** Reads only. Sources:

| Source | Version | What it gives |
|---|---|---|
| Linux `drivers/gpu/drm/amd/amdgpu/gfx_v10_0.c`, `gmc_v10_0.c`, `amdgpu_ib.c`; `include/asic_reg/gc/gc_10_1_0_offset.h`, `gc_10_1_0_default.h` | tag v7.2 (237a1c39) | what amdgpu programs for GC 10.1.3, and every register's reset value |
| Mesa `src/amd/common/ac_cmdbuf.c`, `src/amd/vulkan/radv_queue.c` | 0866ae7 (the box's `~/src/mesa`) | the start state Mesa clients write |
| PAL `gfx9QueueContexts.cpp`, `settings_gfx9.json`, `chip/gfx9_plus_merged_default.h` (MIT) | dev c5e80007 | AMD's own driver's start state, with comments |
| RPCSX `rpcsx/iodev/gc.cpp` | e8ae148 | public names of `/dev/gc` requests |
| Exp 0401's static audit (1,347 captured buffers; `raw/static-register-audit-20261102.md` and its three scripts, copied from the session notes) | 2026-11-02 | what the title and host set |
| Exp 0189's trace of `/dev/gc` (`experiments/0189-ge-system-rings/raw/R0-ioctl-trace.txt`), patch 0001's `gc_ioctl` (main b4a301b5) | | what the title asks of the system and what the host does with it |

`fetch-sources.sh <dir>` fetches the public files at those commits. It also writes `raw/linux-v7.2-gc-10.1-regs.txt`: offset, base index and reset value for every register named here. Line numbers below are from those files.

**Checks (laptop, Git Bash).**

- `bash -n fetch-sources.sh`, then a full run: 11 files, the register table.
- §3's two commands, dry-run with stand-ins for `sudo` and `umr`: 45 and 23 `umr -r` calls with the expected `*.gfx1013.^mmNAME$` argument.
- Every name in them is defined in `gc_10_1_0_offset.h`.
- Nothing ran on the box.

## Result

### 1. The list

A console title gets state it does not write itself in three ways:

- **(a)** It asks the system through `/dev/gc`.
- **(b)** The system programs the state at boot or per process. These registers are privileged: config space or per VMID.
- **(c)** Nothing in the title's stream writes it, but the system's own submissions might.

**One fact about this box decides (c): the gfx ring is shared.** KWin and the emulator's own Vulkan presenter (RADV) submit to the gfx ring between our jobs. Every RADV submission on a general queue starts with a preamble (`radv_queue.c:1683-1687`). All three of RADV's preambles run `radv_init_graphics_state` (`:1027-1047`), which writes Mesa's gfx10 start state through `ac_init_graphics_preamble_state` and `ac_init_compute_preamble_state` (`:630-647`, `:689-715`). v7.2's `amdgpu_ib.c` does not skip a preamble IB: there is no preamble test in the file, and a context switch only sets `AMDGPU_HAVE_CTX_SWITCH`, at `:206` and `:255-256`.

uconfig and SH registers are global to the pipe (exp 0401's notes; TODO(verify)). So during play:

- A register the title never writes holds Mesa's value.
- The host's full-state prefix writes back every register the title did write, in every drawing job's prefix (`backend/include/bc5/full_state.hpp:4-19`; `prefix_of` in patch 0001).

That explains two things:

- **Why exp 0401's five have no known symptom.**
- **Why the two that did bite us are the registers Mesa writes only when needed.** RADV writes the tessellation rings only once its queue has allocated them for a tessellation pipeline (`radv_queue.c:385-394`, `:1048`). Neither KWin nor the presenter tessellates, so the TF ring and `VGT_HS_OFFCHIP_PARAM` stayed at their reset values.

This is inferred from the code. §3's read would show it.

**(a) The title asks the system.** The second title's requests come from exp 0189's trace: 12 request codes, the first 8 calls of each. Requests named elsewhere are added from RPCSX and our own handler.

| Request | Register(s) | Chip at our start (reset value) | Today | If missing |
|---|---|---|---|---|
| 0x80108128 {base, size} | `VGT_TF_RING_SIZE`, `VGT_TF_MEMORY_BASE`, `_HI`, written through their `_UMD` copies, which the kernel remaps to the real registers ("GRBM CAM", `gfx_v10_0.c:7296-7475`, called at `:7513-7515`) | 0xc000, 0, 0 | the host writes the title's ring, `BC5_DIRECT_GC_TF_RING=1`, in the launcher since 10-21 (F248) | GE fetches tessellation factors at address 0 and every tessellated patch is culled (F207, F208, F248) |
| 0x8004812a = 0x1ff | `VGT_HS_OFFCHIP_PARAM` (`_UMD`, CAM) | 0; `ureg` read 0 (F780) | the host writes 0x1ff, `BC5_DIRECT_GC_HS_OFFCHIP=1` (F786, in the launcher) | the night lake's holes (F785) |
| 0xc00c8110, "set gs ring sizes" (RPCSX `gc.cpp:295-307`) | `VGT_ESGS_RING_SIZE`, `VGT_GSVS_RING_SIZE` (`_UMD`, CAM) | 0, 0 | logged only. The second title never asks (not in the trace), and every `VGT_SHADER_STAGES_EN` it sets has PRIMGEN (audit) | inferred: a title with a legacy GS would lose its GS output. **Gap under the ports rule** |
| 0xc0048114, "SetWaveLimitMultipliers" (RPCSX `gc.cpp:392-398`, PS4 path) | wave limits; which registers is not in any public source read here | — | answered with zeros; not in the second title's trace | none known |
| 0xc010810b, "get cu masks param" (RPCSX `gc.cpp:322-337`) | the CUs per SE/SH the title may use | 40 CUs active after the unlock (CLAUDE.md) | answered with all ones; the host masks the CU registers itself (F7, F39a, `pm4-policy.tsv`) | none known |
| F787's six: 0x80888123 (six address/size pairs; one is 16 MiB, the size 0x1ff asks for), 0xc010813b (ffffffff ×4), 0x80048126 (1), 0x80048134 (0), 0xc0108139 and 0xc0088133 around submissions | not named by any public source read here; RPCSX handles none of them | — | answered with zeros and used nowhere | none known; **naming them needs §3b** |

**(b) The system programs it.** These are privileged registers that a user IB cannot write.

| Register(s) | On the console | Under amdgpu | Today | If not the console's value |
|---|---|---|---|---|
| `SH_MEM_BASES` (per VMID) | private 0x7000…, LDS 0x8000…: the title's code builds FLAT addresses on these bases (F249) | private 0x1000…, shared 0x2000… (`gmc_v10_0.c:623-626`; `gfx_v10_0.c:5366-5375`) | the host cannot set it; it rewrites the title's code instead (`BC5_DIRECT_FLAT_APERTURE=1`, F249/F250, in the launcher) | the reflection traversal halts on a memory violation (F249) |
| `SH_MEM_CONFIG` | unknown | 64-bit, UNALIGNED, RETRY_ALL, prefetch 3 (`gfx_v10_0.c:3668-3672`, written at `:5369`) | — | none known; UNALIGNED is the permissive mode (inferred) |
| GDS, GWS and OA partitions (`GDS_VMIDn_BASE/SIZE`, `GDS_GWS_VMIDn`, `GDS_OA_VMIDn`) | the system gives the title a partition (F32: 886 `ds_ordered_count` in ASTRO BOT's programs) | none for any VMID at init (`gfx_v10_0.c:5236-5253`). Per IB, only for a submission whose BO list holds GDS/GWS/OA (`:7794-7821`) | the host puts 64 KiB GDS, 16 OA and 64 GWS on every BO list (`backend/include/bc5/direct.hpp:85-95`; patch 0001 `oo.gds_kib = 64`) | without them nothing is drawn (F32) |
| `GB_ADDR_CONFIG` | must give the swizzle the title's pre-tiled data was made for | golden 0x44 under mask 0x0c1800ff (`gfx_v10_0.c:3596`); reset 0x44; the driver's copy is 0x00100044 (`:3675`, `:4620`): 16 pipes, 256-B interleave | — | garbled tiled surfaces; not seen: 16 pipes decode the title's depth (exp 0237) |
| The other 33 golden registers of GC 10.1.3 (`gfx_v10_0.c:3581-3616`: `GE_FAST_CLKS`, `CB_HW_CONTROL_3/4`, `DB_DEBUG/3/4`, `GCR_GENERAL_CNTL`, `GL2C_CTRL2/3`, `PA_SC_ENHANCE`, `SQ_ARB_CONFIG`, `TA_CNTL_AUX`, `UTCL1_CTRL`, pipe steering, clock gating …) | the console's own set: **cannot be known without a console** | Linux's | — | none known; these are tunings and hardware workarounds |
| `SPI_CONFIG_CNTL`, the CAM's seventh row (from `SPI_CONFIG_CNTL_REMAP`) | unknown | reset 0xc062c688 | nobody writes it in play; Mesa writes it only for thread trace | none known |
| `PA_SC_TILE_STEERING_OVERRIDE` (a context register, in the kernel's clear state) | the system, for its chip's RB layout | computed from this chip's RBs (`gfx_v10_0.c:5134-5170`) and written into the clear state (`:6416-6418`) | the title never sets it (audit) | none known. It must match this chip, so the kernel's value is the right one |
| The rest of the clear state (`gfx10_cs_data`) | the console's clear state | Linux's (`gfx_v10_0.c:6396-6425`) | the title or host sets 602 of the 603 context registers (audit) | none known |

**(c) Nobody in the stream writes it.** That is exp 0401's five; §2 covers them.

**What the list says.**

- *Found, with a symptom, and already handled:* the TF ring (F248), the HS offchip parameter (F785/F786), the apertures (F249/F250) and the GDS partition (F32). No other register has a known symptom.
- *Gaps under the ports rule, with no symptom in our titles:*
  - The GS ring sizes: the request is logged and never written.
  - The wave-limit request 0xc0048114: its registers are unknown.
  - F787's six: unnamed.
- *Held only by accident:* the uconfig and SH registers the title never writes hold Mesa's values because KWin and the presenter share the ring (inferred). On a box without a Mesa client on the gfx ring they would sit at their reset values. For `GE_MAX_VTX_INDX` that is 0 (`gc_10_1_0_default.h:3761`).
- *Cannot be known without a read:*
  - What the chip holds during play (§3 reads it with one root command and no CP packet).
  - The console's own values for the golden set, `SH_MEM_CONFIG` and `SPI_CONFIG_CNTL`. There is no console to read.

### 2. Exp 0401's five

| Register | Reset value | Mesa gfx10 | PAL gfx10 | Inferred in play | Switch |
|---|---|---|---|---|---|
| `CP_COHER_START_DELAY` (uconfig 0x7b) | **0x20** (`gc_10_1_0_default.h:3638`; PAL `gfx9_plus_merged_default.h:581`) | 0x20 (`ac_cmdbuf.c:60`; the gfx9 path writes 0, `:39`) | 0x20. Comment: "Give the CP_COHER register (used by acquire-mem packet) a chance to think a little bit before actually doing anything" (`gfx9QueueContexts.cpp:155-165`) | 0x20 | `BC5_DIRECT_CP_COHER_START_DELAY`, in the launcher since 11-03 |
| `SPI_SHADER_REQ_CTRL_PS` (SH 0x30) | 0 (`:2074`) | 0x7 (`ac_cmdbuf.c:444-446`) | 0x7: `NumPsWavesSoftGroupedPerCu` defaults to 4 (`settings_gfx9.json:1386-1397`; `gfx9QueueContexts.cpp:1866-1885`) | 0x7, from the Mesa clients | `BC5_DIRECT_SPI_REQ_CTRL_PS`, off; on only in play 1 |
| `GE_MAX_VTX_INDX` | 0 (`:3761`); PAL's header shows the fill 0xcdcdcdcd (`:1120`) | ~0 (`:608`) | `UINT_MAX` (`gfx9QueueContexts.cpp:1817-1826`) | ~0, since indexed draws render, and a clamp at 0 would not let them (inferred from the field name MAX_INDX; TODO(verify)) | none |
| `GE_MIN_VTX_INDX` | 0 (`:3745`) | 0 (`:599`) | 0 (`:1827-1830`) | 0 | none |
| `VGT_INSTANCE_BASE_ID` | 0 (`:3762`) | 0 (`:609`) | not in PAL's preamble | 0 | none |

Two of the five have switches: `CP_COHER_START_DELAY` and `SPI_SHADER_REQ_CTRL_PS`. The other three have none:

- `GE_MIN_VTX_INDX` and `VGT_INSTANCE_BASE_ID`: the drivers write their reset value.
- `GE_MAX_VTX_INDX` must already be large in play.

**"Too slow" with both on** (play 1, 2026-11-03 08:54). There were four confounds, and the last two are new here:

1. The build had no zero skip, which is memory pressure. Exp 0379's bench: GTT 11,992 against 10,080 MiB, MemAvailable 480 against 2,490. It is the same pattern as the e11 plays: the time went outside the host, not to the GPU (103-ms flip: 75 ms outside the direct path, 3.2 ms GPU busy).
2. It was the first play after the 08:53 machine-down, so the page cache was cold (F620).
3. Both writes most likely changed nothing:
   - 0x20 is `CP_COHER_START_DELAY`'s reset value.
   - RADV's preamble writes both registers with these same values at each of the presenter's submissions (inferred).
4. The CP switch alone has been on in every play since 11-03 (series e to e11), playable ones included. The slowdowns of the e11 plays were traced to memory pressure (exp 0401's README, e11 section).

**Is `CP_COHER_START_DELAY` right?**

- **As a value, yes.** 0x20 is the chip's reset value, and both of AMD's drivers write it on gfx10. PAL says what it does: a delay before an `ACQUIRE_MEM` coherency operation starts.
- **As a switch, it repeats what the chip already holds.** So it can neither help nor hurt unless something writes another value. Nothing known does: Mesa's gfx9 path writes 0, but it does not run on this chip.
- **An A/B would compare 0x20 with 0x20,** which is why it was never worth one.
- **The proof is a read.** Without the switch, the chip should read 0x20 at idle and in play (§3).

**A clean test of each.**

- **Read first** (§3), with both switches off: once at idle and once in play.
- **If the read shows 0x20 and 0x7:** the two switches are no-ops by measurement. No play test is needed, and they become table rows (§4).
- **If it shows other values:** one A/B per register on the lake bench (fixed view, RT on, one binary).
  - Arms off/on/on/off, each arm read by §3, so its value is measured, not assumed.
  - Metrics: GPU busy per frame and flips/s. `SPI_SHADER_REQ_CTRL_PS` gets the frame rate only.
  - No reboot between arms if the read shows the value going back. The latch lesson came from `VGT_HS_OFFCHIP_PARAM`, which no Mesa client writes here.
- **`GE_MIN/MAX_VTX_INDX` and `VGT_INSTANCE_BASE_ID`** need no test beyond the read.

### 3. A safe read of what the chip holds

**Why exp 0400 hung.** Up to 4,096 `COPY_DATA` reads went through the CP, context registers included, in the middle of a frame. Which register hung it is not known. `ureg` (`COPY_DATA` of six uconfig registers) never failed.

**The proposal: read through MMIO, not the CP.** Root's reads through debugfs `amdgpu_regs`, as `umr -r` and the stall sampler make them, put no packet on any ring. The kernel sets `GRBM_CNTL.READ_TIMEOUT` to 0xff (`gfx_v10_0.c:5346`), so a read of a busy block should time out rather than wait (inferred from the field name; TODO(verify)). The sampler read 50 registers this way, 40 times, under the second title with RT on: 0 errors, 0.2–0.8 ms each, no kernel line (F533). It also read 18 times under ASTRO BOT (F523).

**Rules.**

1. A fixed list of names, one `umr -r` per register, no wildcards.
2. uconfig, config, and the gfx pipe's SH registers only. **Never context registers**: eight contexts are in flight, so there is no single value to read.
3. No bank, queue or VMID select while a game runs: debugfs bits 61/62, `umr -b/-sb`. Per-VMID and per-SE values are not read here.
4. No halt (`umr -O halt_waves` froze the GPU, F229), no write, no wave scan (F520).
5. `GRBM_GFX_CNTL` first and last as the bank witness (exp 0377). 0 both times means no kernel select overlapped.
6. Two phases:
   - **Idle:** desktop with KWin, no game; the whole list.
   - **In play:** the game running at a quiet spot, the maintainer's own play or a slot from the top session. Only the 21 registers another client can change: the uconfig and SH ones, plus `SPI_CONFIG_CNTL` through its CAM row. The golden ones do not change after boot.

**The commands the maintainer would run.** The output goes to his user's directory, through the outer shell's redirect. The `umr -r "*.gfx1013.^mm${n}\$"` form is the one `tools/scripts/gpu-stall-sampler/install.sh` uses on this box.

```bash
mkdir -p ~/bc5-work/exp0418
```

At idle, the whole list:

```bash
sudo bash -c 'for n in GRBM_GFX_CNTL CP_COHER_START_DELAY SPI_SHADER_REQ_CTRL_PS GE_MIN_VTX_INDX GE_MAX_VTX_INDX GE_INDX_OFFSET VGT_INSTANCE_BASE_ID GE_CNTL GE_PC_ALLOC GE_USER_VGPR_EN GE_STEREO_CNTL CP_STRMOUT_CNTL PA_SU_LINE_STIPPLE_VALUE PA_SC_LINE_STIPPLE_STATE TA_CS_BC_BASE_ADDR VGT_TF_RING_SIZE_UMD VGT_HS_OFFCHIP_PARAM_UMD VGT_TF_MEMORY_BASE_UMD VGT_TF_MEMORY_BASE_HI_UMD VGT_ESGS_RING_SIZE_UMD VGT_GSVS_RING_SIZE_UMD VGT_TF_RING_SIZE VGT_HS_OFFCHIP_PARAM VGT_TF_MEMORY_BASE VGT_TF_MEMORY_BASE_HI VGT_ESGS_RING_SIZE VGT_GSVS_RING_SIZE SPI_CONFIG_CNTL GB_ADDR_CONFIG SQ_CONFIG SQ_ARB_CONFIG PA_SC_ENHANCE TA_CNTL_AUX GCR_GENERAL_CNTL DB_DEBUG DB_DEBUG3 DB_DEBUG4 CB_HW_CONTROL_3 CB_HW_CONTROL_4 UTCL1_CTRL GE_FAST_CLKS CP_SD_CNTL VGT_GS_MAX_WAVE_ID SPI_WCL_PIPE_PERCENT_GFX GRBM_GFX_CNTL; do umr -r "*.gfx1013.^mm${n}\$"; done' > ~/bc5-work/exp0418/idle.txt 2>&1
```

In play, those 21 between the two witnesses:

```bash
sudo bash -c 'for n in GRBM_GFX_CNTL CP_COHER_START_DELAY SPI_SHADER_REQ_CTRL_PS GE_MIN_VTX_INDX GE_MAX_VTX_INDX GE_INDX_OFFSET VGT_INSTANCE_BASE_ID GE_CNTL GE_PC_ALLOC GE_USER_VGPR_EN GE_STEREO_CNTL CP_STRMOUT_CNTL PA_SU_LINE_STIPPLE_VALUE PA_SC_LINE_STIPPLE_STATE TA_CS_BC_BASE_ADDR VGT_TF_RING_SIZE_UMD VGT_HS_OFFCHIP_PARAM_UMD VGT_TF_MEMORY_BASE_UMD VGT_TF_MEMORY_BASE_HI_UMD VGT_ESGS_RING_SIZE_UMD VGT_GSVS_RING_SIZE_UMD SPI_CONFIG_CNTL GRBM_GFX_CNTL; do umr -r "*.gfx1013.^mm${n}\$"; done' > ~/bc5-work/exp0418/play.txt 2>&1
```

**How to read it.**

| Read | Meaning |
|---|---|
| `CP_COHER_START_DELAY` 0x20, `SPI_SHADER_REQ_CTRL_PS` 0x7, `GE_MAX_VTX_INDX` 0xffffffff with the 0401 switches off | the Mesa clients set them: the five are settled, and exp 0401's switches are no-ops |
| `GE_MAX_VTX_INDX` 0 in play | contradicts the inference in §2. Look again, starting with the TODO on the clamp |
| each `_UMD` equal to its real register | the CAM is set up as the kernel code says |
| `VGT_HS_OFFCHIP_PARAM` 0 on a fresh boot and 0x1ff after a play | F780/F785, now measured without the CP |
| ESGS/GSVS 0 | nobody asks for a GS ring, as the trace says |
| `GRBM_GFX_CNTL` not 0 at either end | a kernel select overlapped; repeat the read |
| any `umr` error on a name | umr's database lacks it; that line only is lost |

The in-play read is the one that answers the five. The idle read records the golden values the console's set would be compared against, if it is ever known.

**§3b, naming F787's six.** No register read can name them. A host-side trace could, with no GPU access: at each `/dev/gc` request, log the guest return addresses on the stack, each with the nearest export of the title's `libSceAgcDriver`. The loader knows the exports by NID, and public NID tables give names, as for exp 0160's `SetTFRing`/`SetHsOffchipParam`. The trace would be a default-off switch, read in any ordinary run. It may not resolve if the driver has no frame pointers (TODO(verify)). It reads no Sony code.

### 4. The rule

**The list supports it, with two adjustments.**

- **"Once per context" here means once per job prefix.** Mesa clients on the shared ring rewrite uconfig and SH state between our jobs (`radv_queue.c`, §1), and the prefix already writes back the title's state in every job. The table goes first in the prefix, so the title's own writes still win.
- **Only rows a user IB can write become packets.** That is uconfig and SH directly, and the CAM rows through their `_UMD` addresses (the path `VGT_HS_OFFCHIP_PARAM` already takes). The privileged rows stay in the table with their handling named:
  - `SH_MEM_*`: the code rewrite.
  - GDS/GWS/OA: the BO list.
  - The golden set, `GB_ADDR_CONFIG` and the clear state: the kernel.

  So the table is the one place that says how each item of the console's start state is met.

**Proposed, not built.** `backend/policy/start-state.tsv`, next to `pm4-policy.tsv`. Columns:

- space, name (Linux/Mesa), offset;
- value, or the request it comes from (e.g. 0x80108128);
- console source: cited, inferred, or unknown;
- how we meet it: prefix, CAM, kernel, BO list, or code rewrite;
- finding.

Switches:

- `BC5_DIRECT_START_STATE=1`, default off.
- `BC5_DIRECT_START_STATE_SKIP=<names>` drops rows for bisection.
- The four existing switches (`GC_TF_RING`, `GC_HS_OFFCHIP`, `CP_COHER_START_DELAY`, `SPI_REQ_CTRL_PS`) become aliases that turn on their rows, so the launcher keeps working.

Rows:

- Rows marked inferred take the value §3's in-play read shows. Turning the table on then changes nothing on this box today, and it removes the dependence on KWin and the presenter.
- New rows: the GS ring sizes from 0xc00c8110 (the ports rule), `GE_MAX_VTX_INDX` ~0, `GE_MIN_VTX_INDX` 0, `VGT_INSTANCE_BASE_ID` 0, and, if the read confirms them, `CP_COHER_START_DELAY` 0x20 and `SPI_SHADER_REQ_CTRL_PS` 0x7.
- Under the fixes-first rule, the table and §3b's trace go into one build, each behind its own switch, then one read with the table on and off, then one play. Expected: no change.

## Verdict

**No new register with a known symptom.**

- *Found and already handled:* the TF ring, the HS offchip parameter, the apertures and the GDS partition.
- *Gaps under the ports rule, with no symptom here:* the GS ring sizes (logged, never written), the wave-limit request, and F787's six requests (unnamed).
- *Exp 0401's five:*
  - In play they very likely hold Mesa's values already, written by KWin's and the presenter's preambles on the shared gfx ring. 0x20 is also `CP_COHER_START_DELAY`'s reset value.
  - The "too slow" play is explained by its confounds; the two switches most likely wrote what was already there.
  - `CP_COHER_START_DELAY` = 0x20 is right as a value and changes nothing as a switch.
- *Cannot be known without a read:*
  - What the chip holds in play: §3, one root command per phase, with no CP packet.
  - The console's own values for the golden set, `SH_MEM_CONFIG` and `SPI_CONFIG_CNTL`: no console to read.
- *The rule is supported:* one start-state table, written in every job's prefix, with a source per row.

Not shown: any value on this box. Everything about "in play" above is inferred from Mesa's and the kernel's code until §3 runs.
