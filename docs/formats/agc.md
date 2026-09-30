# AGC / PM4 — command-stream notes

What `bc5-agc` (phase 1) decodes and where the reference behaviour comes from. Facts cite a public
file at a commit; everything unverified is marked `TODO(verify)`.

Sources:

| Tag | Source | Licence |
| --- | --- | --- |
| **RX** | [RPCSX/rpcsx](https://github.com/RPCSX/rpcsx) @ `e8ae148` (2026-06-30) | GPL-2.0 |
| **MESA** | Mesa `src/amd/registers/{gfx10.json,pkt3.json}` @ `fe55488` (2026-09-29) | MIT (Mesa) |
| **AMD** | AMD, *Radeon Southern Islands / Sea Islands 3D/Compute Register Reference* (PM4 packet format is unchanged through GFX10 for the fields used here) | public PDF |

## 1. RPCSX AGC handling (answers HANDOFF Q2)

**There is no separate AGC parser in RPCSX.** PS5 support exists in the loader and kernel
(`orbis::FwType::Ps5`, `ProcessType::Ps5`, `DynType::Ps5`; RX `rpcsx/main.cpp:469,577,740`,
`rpcsx/linker.cpp:813`, `kernel/orbis/include/orbis/KernelContext.hpp:26`), but the GPU directory
`rpcsx/gpu/` contains no PS5-, Prospero- or AGC-specific code at all. PS5 command buffers are fed
to the same PM4 interpreter that serves PS4 GNM.

How a PS5 title's command buffers reach the GPU emulation:

1. **`/dev/gc` ioctls** (RX `rpcsx/iodev/gc.cpp`). Three requests are PS5-only (each returns
   `EINVAL` unless `fwType == Ps5`):
   - `0xc004812e` (`gc.cpp:80`): returns two zero 16-bit fields; purpose unknown.
   - `0xc0488131` "ps5 submit header" (`gc.cpp:96-155`): a 72-byte struct
     `{ u32 unk0; u32 contextControl[3]; u32 cmds[3][4]; u64 status; }`. `contextControl` is
     submitted as one 3-dword PM4 packet (an `IT_CONTEXT_CONTROL`, opcode 0x28), then each non-zero
     4-dword `cmds[i]` is submitted as a packet; the handler only accepts `IT_INDIRECT_BUFFER`,
     `IT_INDIRECT_BUFFER_CNST` or `IT_CONTEXT_CONTROL` here (see step 2). Which of the three slots
     carries the DCB and which the CCB is not named in the code — `TODO(verify)` from a capture.
   - `0xc0188132` (`gc.cpp:157-208`): `{ u32 unk0; u32 count; Submit *submits; u32 status; }` with
     `Submit { u64 unk0; u64 unk1; u64 address; u64 size; }`; for `count / 2` entries RPCSX
     synthesises `{0xc0023f00, addressLo, addressHi, size}` — i.e. a type-3 `IT_INDIRECT_BUFFER`
     (opcode 0x3f, 2 payload dwords) pointing at the guest command buffer — and submits it.
   - The PS4 path uses `0xc0108102` (`gc.cpp:210-230`), an array of 4-dword commands, the same shape.
2. **`amdgpu::DeviceCtl::submitGfxCommand`** (RX `rpcsx/gpu/DeviceCtl.cpp:32-54`) checks the
   packet is type 3 and one of the three opcodes above, patches the process' `vmId` into bits 31:24
   of dword 3 of an indirect-buffer packet, and calls `Device::submitGfxCommand`
   (`rpcsx/gpu/Device.cpp`), which appends it to `graphicsPipes[pipe].deQueues[2]`
   (`Device::submitCommand`, same file: a ring of dwords, wrap-around padded with type-2 NOPs
   `2 << 30`).
3. **`amdgpu::GraphicsPipe::processRing`** (RX `rpcsx/gpu/Pipe.cpp:812-870`) is the command
   processor. Per header dword: `type = bits 31:30`; type 3 → `opcode = bits 15:8`,
   `len = bits 29:16 + 2` dwords; type 2 → one-dword filler; anything else → `rx::die`. Handlers are
   looked up in `commandHandlers[cp][opcode]` where `cp` selects the CE (0), main-ring (1), DE (2)
   or "data" (3) table by ring `indirectLevel`; unregistered opcodes go to `unknownPacket`.
   `IT_INDIRECT_BUFFER` / `_CNST` switch the ring to the referenced buffer.
4. **Opcode numbers** come from RX `rpcsx/gpu/lib/gnm/include/gnm/pm4.hpp` (GCN `IT_*` values,
   0x10–0xa0; names in `gnm/src/pm4.cpp`). **Register writes** (`setContextReg`, `setShReg`,
   `setUConfigReg`, `setConfigReg`; `Pipe.cpp`) take `offset = dword1 & 0xffff`,
   `index = dword1 >> 26`, and `memcpy` the payload into the register block; block bases are GCN
   MMIO dword offsets (RX `rpcsx/gpu/Registers.hpp:550,653,668,827`): config 0x2000, SH 0x2c00,
   context 0xa000, uconfig 0xc000. Names are resolved with `gnm::mmio::registerName`
   (`gnm/src/mmio.cpp`, a GCN table). **Shaders** go through `rpcsx/gpu/lib/gcn-shader` (GCN →
   SPIR-V); there is no RDNA decoder.

Consequences for BC5:

- A **tap** (phase 1, task 3) belongs in `DeviceCtl::submitGfxCommand` or in
  `GraphicsPipe::indirectBuffer`: that is where the guest address and size of every DCB/CCB become
  known. Dumping `{vmId, address, size, dwords}` there, gated by an environment variable, captures
  exactly what the game submitted.
- Everything RPCSX knows about AGC is "it is PM4 with GCN opcode numbers and GCN register offsets".
  On gfx10 the PM4 packet format and the opcode numbers of the packets RPCSX handles are the same
  (MESA `pkt3.json` names them identically), but the **register map differs** (GFX10 moved and
  renamed context/SH registers). `bc5-agc` therefore resolves offsets against MESA `gfx10.json`,
  not against RPCSX's GCN table, and reports where the two disagree.
- RPCSX's `unknownPacket` is the first place a PS5-specific opcode would surface; the phase-1 tap
  plus `bc5-agc report` answer HANDOFF Q3/Q4 without touching RPCSX internals further.

## 2. PM4 packet framing (what `bc5-agc` parses)

Little-endian 32-bit words (AMD SI/CI register reference, §"PM4 packets"; RX `Pipe.cpp:830-846`
implements exactly this):

| Type (bits 31:30) | Layout | Handling |
| --- | --- | --- |
| 0 | header: `count-1` in 29:16, base register index in 15:0; then `count` register values | decoded as sequential register writes from `base` (MESA offsets) |
| 1 | reserved | error |
| 2 | header only | one-dword filler, skipped |
| 3 | header: `count-1` in 29:16, opcode in 15:8, predicate in bit 0, shader type in bit 1; then `count` payload dwords | decoded per opcode; unknown opcodes are counted and skipped by `count` |

`count-1 == 0x3fff` means a zero-length packet (`count` wraps to 0); `bc5-agc` treats it as one
header dword.

Packets with register payloads (`SET_CONTEXT_REG` 0x69, `SET_SH_REG` 0x76, `SET_UCONFIG_REG` 0x79,
`SET_CONFIG_REG` 0x68 and the `LOAD_*`/`*_INDEX` variants) carry `offset = dword1 & 0xffff`
(dword index relative to the block base) and the values from dword 2 on. Block bases used by
`bc5-agc` for GFX10 (MESA `gfx10.json` `register_mappings[].map.at` are absolute byte addresses;
the PM4 convention is dword offsets relative to these bases, the same numbers RPCSX uses):
config 0x2000, SH 0x2c00, context 0xa000, uconfig 0xc000. `TODO(verify)`: confirm on gfx10 that
`SET_SH_REG` offsets are relative to 0x2c00 (RADV `radeon_set_sh_reg` in `src/amd/common/`).

## 3. Open questions moved here from HANDOFF

- **Q3** (do titles write CU masks): count `SET_SH_REG` writes to `COMPUTE_STATIC_THREAD_MGMT_SE*`
  and `SPI_SHADER_PGM_RSRC3_*` in captures — `bc5-agc report` lists them by name.
- **Q4** (Sony-specific register usage): offsets that `gfx10.json` cannot name are reported as
  `unresolved:<block>+0x…` with counts; opcodes absent from `pkt3.json`/RPCSX's table likewise.
- Which submit-header slot is the DCB and which the CCB (§1, ioctl `0xc0488131`).

## Observed in console-format captures (track B, experiments 0011–0012)

Source: 718 buffers built by Sony's `libSceAgc` (ASTRO BOT, `experiments/0012-sony-frames-through-soft-cp/raw/`).

- Opcodes not in Mesa's `sid.h`, named from AMD PAL: `PREAMBLE_CNTL` 0x4a, `LOAD_UCONFIG_REG_INDEX` 0x64,
  `GET_LOD_STATS` 0x8e (`IT_GET_LOD_STATS__APU103`, PS5-class APU only), `WAIT_REG_MEM64` 0x93
  (`tools/bc5-agc/regdb/extra-opcodes.tsv`).
- Unresolved register offsets: SH `+0x280` (mm `0x2e80`), always written as 0 in the same `SET_SH_REG`
  group as `COMPUTE_STATIC_THREAD_MGMT_SE0..3 = 0xffffffff` (compute dispatch preambles). TODO(verify):
  identity; resolve against the driver binary.
- CU masks (Q3): written by the compute preambles only, all ones, all four SEs.
- Markers: `SQ_THREAD_TRACE_USERDATA_2/3` carry Sony's per-packet markers (the most frequent writes).
- Submit path (Q2): `0xc0488131` = context control + state preamble IB + a 2-dword IB; `0xc0188132` = the
  frame DCBs; compute goes through 56 hardware-style queues registered with `0xc0408121` (write pointers
  in the mmap'd submit page, rings of `INDIRECT_BUFFER` packets).
