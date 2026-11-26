# 0445 — the six unanswered /dev/gc requests, and shader scratch, in public sources

**Question.** What do the related open projects and public documents say about F787's six `/dev/gc` requests (0xc0108139, 0xc0088133, 0xc010813b, 0x80888123, 0x80048134, 0x80048126) and 0x80888123's address table? What do they program for shader scratch and wave32 compute? Does any of it give a state the console sets up and BC5 does not, which could explain F898/F900-F903: the third title's wave32 indirect dispatch whose waves never launch?

**Setup.** Offline only: source reading, no box access, no SDK material. The top session's order of 2026-11-22. The repositories are the earlier survey's clones in `~/Downloads/bc5/refs` on the laptop, fetched again on 2026-11-22:

| Project | Licence | Commit read |
|---|---|---|
| iStark/PS5PCEM | GPL-3.0-or-later | aeefeb4 (2026-11-19) |
| boykopovar/AnyPS5 | GPL-2.0 | 5569456276 (2026-11-22) |
| KytyPS5/KytyPS5 | GPL-2.0 | 61331721 (2026-11-21) |
| Coder787-source/KytyPlus | GPL-2.0 | 3650f7a (2026-11-10) |
| shadps4-emu/shadPS4 | GPL-2.0 | 264d6b7 (2026-11-20) |
| RPCSX/rpcsx | GPL-2.0 | e8ae148 (2026-06-30, no newer commit) |
| red-prig/fpPS4 | LGPL-2.1 | 04cefd4 (2024-10-01) |
| obhq/obliteration | Apache-2.0 or MIT | 2a53d5c |
| Abhishekrazy/pcsx5 | GPL-2.0 | f1244ff |
| Mesa | MIT | ab2374a (2026-10-22) |

Not re-fetched: Kyty, GPCS4, P5EMU, EmuFive, astraea, ps5-vulkan, OpenProspero AGC. They were searched at their earlier clones.

**PS5PCEM is GPL-3.0**, and GPL-3.0 code cannot go into our GPL-2.0 tree. Its comments are cited here as facts and names only; nothing is to be ported from it.

**How the codes were matched.** The request code is the FreeBSD `_IOC` form: direction in bits 30-31, length in bits 16-29, the gc device's group 0x81 in bits 8-15 (PS5PCEM's own tests encode it so, `kernel_ioctl.zig:1318`, `:1376`), and the command number in bits 0-7. PS5PCEM writes requests as `#<command number>` in decimal (`kernel_ioctl.zig:25-46`). So:

| Code | Command | Length |
|---|---|---|
| 0xc0108139 | #57 | 16 bytes, in and out |
| 0xc0088133 | #51 | 8 bytes, in and out |
| 0xc010813b | #59 | 16 bytes, in and out |
| 0x80888123 | #35 | 136 bytes, in |
| 0x80048134 | #52 | 4 bytes, in |
| 0x80048126 | #38 | 4 bytes, in |

The check that this reading is right: PS5PCEM's #40 (16 bytes, the tessellation-factor ring) and #42 (4 bytes, the HS off-chip values) are our handled 0x80108128 and 0x8004812a, with the same contents (`kernel_ioctl.zig:42-45`; our exp 0418).

## Result 1: the six requests

No project has any of the six codes as a literal: `git grep` over every repository listed above. Only PS5PCEM names them, by command number. RPCSX's gc device (`rpcsx/iodev/gc.cpp:47-449`), Obliteration's list (`legacy/src/fs/ioctl.rs:176-196`) and shadPS4 (a PS4 project, no PS5 gc device) handle none of them. KytyPS5, AnyPS5 and KytyPlus emulate the AGC libraries at a higher level and have no `/dev/gc` request handler.

| Code | PS5PCEM's name and layout | What PS5PCEM returns | GPU state derived | Others |
|---|---|---|---|---|
| 0xc0108139 (#57) | "Queries the process suspend point" (`kernel_ioctl.zig:40-41`) | "Retail execution is not suspended, so its output state remains clear" (zeros) | none | not found |
| 0xc0088133 (#51) | `GraphicsQueueCommit {queue: u32, result: u32}`: "Commits the queue after its indirect-buffer list has been accepted" (`:449-453`, size check `:461-462`). It follows #50 = 0xc0188132 (the IB list) and #49 = 0xc0488131 (the 72-byte preamble), which the driver primes with result = 1 and accepts once the kernel writes 0 (`:405-417`) | result 0 | none | RPCSX handles 0xc0488131 and 0xc0188132 (`gc.cpp:96`, `:157`) but not #51 |
| 0xc010813b (#59) | "The wrapper fills the buffer with 0xff before calling and stores the reply in the final 16 bytes of the driver's private device pool. Its individual fields are not yet consumed" (`:36-39`) | zeros ("the compatibility response clears them") | none | not found; exp 0418's CU-mask reading is still a guess |
| 0x80888123 (#35) | "Installs the trap-handler resources", input, 136 bytes (`:29`). The handler checks direction and length only and records a flag (`:233-237`); the layout is not parsed | 0; sets `trap_resources_installed` | none | not found |
| 0x80048134 (#52) | with #38: "They retain the compute and graphics mode selected by the process" (`:34-35`); the one has the compute mode and the other the graphics mode, but the comment does not say which is which | 0; the value is kept | none | not found |
| 0x80048126 (#38) | see #52 | 0; the value is kept | none | not found |

So two of the six (#57, #51) are submission bookkeeping, as exp 0418 result 2 found from the trace. That matches what the third title sends: six of each, around the submissions. #59 is an opaque reply. #52 and #38 carry a process mode. **None of them names a scratch ring**, and no project derives GPU state from any of them.

## Result 2: 0x80888123's table

PS5PCEM calls the whole request "the trap-handler resources". Exp 0418 result 2 already named the pairs from the names the driver gives its own mappings (`experiments/0418-console-start-state/impl/README.md:321`). This survey found nothing that adds to or contradicts it:

| Pair (address + size) | Name on the console | Source | Scratch, GDS, tessellation/geometry ring, shadow? | Registers it would program |
|---|---|---|---|---|
| 0xf00000000 + 0x2400 | trap-handler code (in a 16 KiB area) | 0418:321 (driver's mapping name); PS5PCEM `:29` (the request's role) | no | `SQ_SHADER_TBA_LO/HI`, privileged, per VMID (0418: `gc_10_1_0_offset.h:2469-2475`) |
| 0xf00004000 + 0x4000 | trap-handler data | 0418:321 | no | `SQ_SHADER_TMA_LO/HI`, privileged, per VMID |
| 0xf00144000 + 0x1000000 | CWSR area (wave save/restore, 16 MiB) | 0418:321, 0418:148 | no | per queue: the MQD's context save area (0418: `kfd_mqd_manager_v10.c:133-140`); kernel only |
| 0xf00008000 + 0xfc000 | "DDID" (1008 KiB); role unknown | 0418:321 | not found | not found |
| 0xc80008000 + 0x3bb00 | in no guest mapping; name not found | 0418:321 | not found | not found |
| 0xc80043d00 + 0xd00 | in no guest mapping; name not found | 0418:321 | not found | not found |

**A correction to the premise.** The top session's message says exp 0418 matched the 16 MiB pair to the HS off-chip ring. That was 0418's first reading, by arithmetic. **Its own trace refuted it**: the area is CWSR (0418:121, :148).

**None of the pairs is a compute or graphics scratch ring**, and none is a GDS area, a tessellation or geometry ring, or a command or state shadow. Everything a name exists for is the kernel's (trap handler, CWSR). On Linux only the KFD writes those registers. Our process runs on amdgpu's graphics VMIDs, with no trap handler and no CWSR (0418 result 4, `gfx_v10_0.c:5175-5192`). The title's set RSRC2 values ask for neither a trap nor an exception: 387 values, all with `TRAP_PRESENT` = 0 and `EXCP_EN` = 0 (0418:412).

## Result 3: shader scratch

**What real hardware needs, per Mesa (radv, gfx10, ab2374a).**

- **Compute** (`src/amd/vulkan/radv_queue.c:479-517`, `radv_emit_compute_scratch`):
  - `COMPUTE_TMPRING_SIZE` = `WAVES` | `WAVESIZE` (`:516`), from `ac_get_scratch_tmpring_size` (`src/amd/common/ac_shader_util.c:1056-1080`).
  - Before GFX11 there is no scratch base register. radv puts the scratch buffer's address and a descriptor word (`BASE_ADDRESS_HI`, `SWIZZLE_ENABLE`) into `COMPUTE_USER_DATA_0/1` (`:510-513`), which is radv's own shader ABI.
  - Only GFX11+ has `COMPUTE_DISPATCH_SCRATCH_BASE_LO/HI` (`:503-507`).
- **Graphics** (`src/amd/common/ac_cmdbuf_cp.c:382-397`): before GFX11, only `SPI_TMPRING_SIZE`. GFX11+ adds the base in the next two registers.
- **The rule** (`ac_shader_util.c:1060-1070`): "SPI_TMPRING_SIZE and COMPUTE_TMPRING_SIZE are essentially scratch buffer descriptors. WAVES means NUM_RECORDS. WAVESIZE is the size of each element", and "Shaders with SCRATCH_EN=0 don't allocate scratch space". By that reading, a `SCRATCH_EN` = 1 wave allocates one record from the ring that `WAVES` sizes.
- **TODO(verify): what the SPI does when `SCRATCH_EN` = 1 and `WAVES` = 0 or `WAVESIZE` is too small.** That would be the "waves never launch" case. Mesa has no comment on it: no scratch/hang note in `src/amd` or radeonsi. It needs the RDNA ISA guide's scratch section or an AMD register document. Do not take it as fact.

**What the PS5 projects do.** All of them translate shaders (Vulkan or D3D12), so none programs hardware scratch:

| Project | What it does with scratch | Source |
|---|---|---|
| AnyPS5 | Per-thread private memory sized from the AGC shader header's `scratch_size_dw_per_thread` when `COMPUTE_PGM_RSRC2.SCRATCH_EN` is set. It fails if the header is missing or the size is 0 | `libSceAgcDriver/Graphics/src/ShaderInputState.cpp:83-91` |
| PS5PCEM | The same: "the shader header's private scratch size", only when `SCRATCH_EN` | `src/vulkan/backend.zig:43142-43146`; `docs/development/severed-steel-startup-2026-10-21.md:56-58` |
| KytyPS5 | Reads `SCRATCH_EN` into its state and accepts `COMPUTE_TMPRING_SIZE` writes without using them | `pm4Handlers.cpp:310-311`, `:339-340` |
| RPCSX | `scratchEn` adds a scratch SGPR input to the translated shader | `rpcsx/gpu/Cache.cpp:2518-2520` |
| shadPS4, fpPS4 | Register names and fields only | `regs_shader.h:72`, `:200`; `si_ci_vi_merged_registers.pas` |
| pcsx5 | Its AGC default-state table lists `SPI_TMPRING_SIZE` = 0 (context group, entry 43) and `COMPUTE_TMPRING_SIZE` = 0 (shader group, entry 4) | `src/hle/libagc.cpp:208`, `:256` |

The pcsx5 table carries 32-bit hashes next to each entry, and where they come from is not stated. It is cited only to show that `COMPUTE_TMPRING_SIZE` belongs to AGC's compute shader register group. **Check its provenance before using any of its values.**

**Does any PS5 project set scratch from a `/dev/gc` request? No; not found in any of them.** In every source that names it, the scratch size comes from the shader's own AGC header and register state, not from the system.

## Result 4: wave32 compute (`CS_W32_EN`)

- radv sets `CS_W32_EN` in `DISPATCH_INITIATOR` when the shader is wave32 and adds no other state for it (`src/amd/vulkan/radv_cmd_buffer.c:15217`; the same for task shaders, `:11805`, `:11830`).
- PS5PCEM passes `CS_W32_EN` from the PM4 initiator to its translator. It names live programs with initiator 0x8041 (its start-up notes for this title under `docs/architecture/`, lines 2213-2224), and that is a translation change, not hardware state.
- **Nothing found** in any project about a wave32 dispatch needing state the title does not set.
- One fact that follows from Mesa's scratch rule: `WAVESIZE` is per wave, so a wave32 shader's bytes per wave are half those of the same per-thread size in wave64. A `COMPUTE_TMPRING_SIZE` written for wave64 is larger than wave32 needs, not smaller (inferred from `ac_shader_util.c:1060-1080`).

## Verdict

**Inconclusive for F898's cause; three things closed, one lead left.**

- **Closed:** none of the six requests is, by any public source, a scratch ring or a register the title expects the system to program. #57 and #51 are submission bookkeeping. #59's reply is opaque. #52 and #38 carry a process mode. #35 (0x80888123) is the trap handler, CWSR and two unnamed areas: kernel-only state on Linux, and not used through the RSRC2 bits the titles set (0418 result 4).
- **Closed:** no PS5 project programs hardware scratch at all, and none derives scratch from `/dev/gc`. In all of them the size comes from the shader's AGC header.
- **Closed:** no source names wave32-specific state.
- **The lead, for the next step (on the box, the top session's call).** On the console, scratch is shader state that the title's AGC writes: `COMPUTE_TMPRING_SIZE` in the compute register group (pcsx5), with the size from the shader header (AnyPS5, PS5PCEM).
  - So the check is the stalled dispatch itself, from its capture. Does its `COMPUTE_PGM_RSRC2` have `SCRATCH_EN` = 1?
  - Does the stream write `COMPUTE_TMPRING_SIZE` before it? With which `WAVES` and `WAVESIZE`?
  - Does the shader's user data carry a scratch address? On gfx10 there is no base register (Mesa above).
  - If `SCRATCH_EN` = 1 and no `COMPUTE_TMPRING_SIZE` (or `WAVES` = 0) reaches the GPU, that is the console/BC5 difference to fix, together with the TODO(verify) above on what the SPI does then.
  - If `SCRATCH_EN` = 0, scratch is ruled out for F898.

Nothing here is a hardware fact of our own; every cell is cited or marked not found or TODO(verify).
