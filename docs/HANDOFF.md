# HANDOFF — research state as of 2026-09-28

This is the working memory of the project: what has been established, from where, and what is still open. Update it whenever a question is answered. `README.md` is the public summary; this file is the detailed one.

## 1. Thesis

The BC-250 is the same silicon target as the PS5 (Zen 2 + `gfx1013` + 16 GB unified GDDR6). Every existing PS5 runtime targets generic PCs and therefore translates the GPU side (AGC/PM4 → Vulkan, RDNA ISA → SPIR-V). On the BC-250 that translation can be removed: hand the game's command stream and shader binaries to `amdgpu` as-is. Everything else (loader, HLE, audio, input) comes from RPCSX.

What we deliberately do not do: boot PS5 firmware (PSP/Sony keys/ABL/SMU/hypervisor cannot run on the BC-250; no Sony southbridge, SSD/Kraken, Tempest), write a new emulator, or touch Sony material.

## 2. Findings (sourced)

| # | Finding | Source | Confidence |
| --- | --- | --- | --- |
| F1 | PS5 GPU and BC-250 are both `gfx1013` (GFX10.1 + `image_bvh_intersect_ray`), **not** gfx10.3. A Vulkan project for native PS5 homebrew compiles shaders with the ACO GFX1013 backend on a real console (fw 12.02); Mesa/RADV identifies the BC-250 as gfx1013. Consequence: no ISA gap; avoid `gfx10-3-insts`. | mpereiraesaa/ps5-vulkan README; Phoronix "RADV Cyan Skillfish" | High |
| F2 | AGC command buffers are standard PM4 type-3 packets. Public code handles `SET_CONTEXT_REG` (header `0xC0016900` seen in KytyPlus), `SET_SH_REG`, `RELEASE_MEM`, `WRITE_DATA`, `COPY_DATA`, `DMA_DATA`, `DUMP_CONST_RAM`, `DISPATCH_INDIRECT`. astraea frames the AGC DCB as generic PM4 type-3. | astraea-emu/astraea issue #158; boykopovar/AnyPS5 PR #5 (AGC recorder driver); Coder787-source/KytyPlus | High for framing |
| F3 | Sony-specific register usage is expected in draw / CB / DB packets; public AMD opcode tables are not sufficient there. | OpenProspero/AGC README | Medium |
| F4 | `amdgpu` does not parse GFX indirect buffers. User space (RADV, radeonsi) builds PM4 IBs and submits them via `DRM_AMDGPU_CS`; privileged registers are protected by CP firmware. libdrm `tests/amdgpu` contains dispatch and draw tests for gfx10 with embedded shader binaries (`shader_code_gfx10.h`, `basic_tests.c`). | Mesa RADV docs; libdrm `tests/amdgpu` | High |
| F5 | Loading a prebuilt shader binary does not need RADV: the libdrm path writes ISA bytes into a BO and sets `PGM_LO/HI` + `RSRC*` via `SET_SH_REG`. Worked examples: libdrm tests, orgito1015/AMD-GPU-Debugger (ACO null winsys → raw submit), IGT `amdgpu_dispatch_shader()` helper. | as listed | High |
| F6 | BC-250 hazards: RADV disables the gfx1013 compute queue (Mesa MR !33116) — use the GFX ring; a GPU reset can take the machine down (akandr/bc250-rocm logs). | Mesa MR; bc250-rocm | High |
| F7 | CU masks are SH registers written by the submitter: `COMPUTE_STATIC_THREAD_MGMT_SE0-3` (compute; bytes 0xB858/0xB85C/0xB864/0xB868 = SH dwords 0x216/0x217/0x219/0x21A), `CU_EN` fields in `SPI_SHADER_PGM_RSRC3_PS/VS/GS/HS` (graphics; `RSRC3_PS` at mm 0x2c07). RADV/radeonsi write them for every GFX level. Basis for the 36/4 CU split. Note: on gfx10 the kernel header defines `COMPUTE_DESTINATION_EN_SEn` as an alias at the same offsets and Mesa's `gfx10.json` keeps only that name; `bc5-agc` maps both (`regdb/extra-registers.tsv`). | Mesa `src/amd/common/ac_cmdbuf.c` @ fe55488 :111-114; Linux `drivers/gpu/drm/amd/include/asic_reg/gc/gc_10_1_0_offset.h` :4579-4595; Mesa `src/amd/registers/gfx10.json` @ fe55488 | High (register existence), Medium (behaviour on gfx1013) |
| F8 | PS5 dumps circulate as unpacked `app0` folders, exFAT images, `FFPKG` (UFS2) or `.ffpfsc` containers. `.ffpfsc` = PFS v2 image (64 KiB blocks) wrapping one PFSC-compressed exFAT image of the dump. Console-side compressors produce `.ffpfsc` directly. PFSC decompression measured ~900 MB/s on PC. | thanhsondev/PSVIETHOA-FPKG-Builder release notes; pearlxcore/PS5PKGTool; juma-sayeh/PS5-Game-Compressor | High |
| F9 | KytyPlus intercepts hypervisor CPUID leaf `0x40000000` ("SonyPS5") — some titles probe it. Replicate in the loader if RPCSX does not. | Coder787-source/KytyPlus | Medium |
| F10 | `.ffpfsc` on-disk layout is fully described in `docs/formats/ffpfsc.md`: PFS v2 superblock (version 2, magic 20130315, mode bit 3 case-insensitive, 64 KiB blocks), exactly 4 D32 inodes (super-root, `flat_path_table`, `uroot`, payload), 8-byte-aligned dirents, one-entry flat path table, PFSC stream (magic `PFSC`, field 6, 64 KiB logical blocks, offset table at 0x400, per-block raw-or-zlib), exFAT inside. A real container matched every reader-relevant field, including the unused block 4 and the PFSC header-size formula. Answers Q6. | pearlxcore/PS5PKGTool @ 0072cb4 (`PS5PKGTool.Ffpfsc/*.cs`); PSBrew/MkPFS @ 78eda0a (`mkpfs/consts.py`, `mkpfs/pfs.py`); psdevwiki PS4/PFS; `experiments/0001-ffpfsc-header-survey` | High (one producer seen; see ffpfsc.md §9) |
| F14 | All **40 CUs are routed for dispatch** on the dev box: per shader array `SPI_PG_ENABLE_STATIC_WGP_MASK = 0x1f` (WGP0–4), `CC_GC_SHADER_ARRAY_CONFIG = 0xffe00000`; WGP0–2 (24 CUs total) are the driver's boot-time map, WGP3–4 (16 CUs) are added after boot by the maintainer's `bc250-cu-live-manager` service via umr, which is why the kernel and RADV report 24. GPU firmware: ME 0x63, PFP 0x94, CE 0x25, MEC 0x90, RLC 0x0d, SDMA 0x34, SMC 88.6.0. Answers Q8. | `experiments/0004-cu-unlock-mechanism`, `experiments/0005-cu-dispatch-status` | High (register state); performance unmeasured |
| F13 | Dev box (2026-09-29): Bazzite 44, kernel `7.2.4-ogc3.1.fc44`, Mesa 26.2.3 with RADV naming the GPU `AMD BC-250 (RADV GFX1013)` (`gfx_level` GFX10), libdrm_amdgpu 2.4.134, VRAM carve-out 8 GiB + 7.5 GiB system RAM, sclk up to 2000 MHz, **SE 2 × SH 2 × CU 10 with 24 CUs active**, PSP IP `psp_v11_0_8` used by amdgpu while the crypto function `1022:143e` has no driver bound. Answers Q7; raises Q8. | `experiments/0003-dev-box-inventory` | High |
| F12 | RPCSX has **no AGC parser**: PS5 submits enter through `/dev/gc` ioctls (`0xc0488131` "ps5 submit header", `0xc0188132`), are wrapped as `IT_INDIRECT_BUFFER` packets (`0xc0023f00`) and processed by the same GCN PM4 interpreter as PS4 GNM (`GraphicsPipe::processRing`, GCN opcode table, GCN register map, GCN→SPIR-V shaders). Tap point for captures: `DeviceCtl::submitGfxCommand` / `GraphicsPipe::indirectBuffer`. Answers Q2; details and file:line in `docs/formats/agc.md` §1. | RPCSX/rpcsx @ e8ae148: `rpcsx/iodev/gc.cpp`, `rpcsx/gpu/{DeviceCtl,Device,Pipe}.cpp`, `rpcsx/gpu/lib/gnm/` | High |
| F11 | All public `.ffpfsc` implementations are GPL-3.0 (PS5PKGTool, MkPFS, PS4 FFPFSC), incompatible with our GPL-2.0-only. No code is ported; `bc5-mount` and its fixture generator are written from the format notes. MkPFS (`pip install mkpfs`, Linux-capable) is the external oracle for the gate experiment, run as a separate process. `PSBrew/ps5-exfat-builder` no longer exists. | repo `LICENSE` files at the commits above; ADR 0003 | High |
| F15 | A Prosper capture of ASTRO BOT (D10) is **Prosper's command encoding, not the console's**: every draw, dispatch, barrier, flip and marker is a type-3 NOP whose header bits 2..7 carry Prosper's own sub-op enum; only four opcodes occur (NOP, SET_SH_REG, EVENT_WRITE, NUM_INSTANCES). Only the SET_SH_REG (offset, value) pairs are game-derived (0 CU-mask writes). No game shader binaries were captured. Such captures cannot answer Q2/Q4 or feed phase 1; console-format DCBs need Sony's `libSceAgc` under RPCSX (gate G0b). | experiments/0007 | High |

## 3. Open questions

| # | Question | Plan |
| --- | --- | --- |
| Q1 | 1:1 memory mapping: can `AMDGPU_GEM_USERPTR` + user-chosen GPU VA (`amdgpu_bo_va_op`) map GPU VA = game CPU pointer with zero copies on an APU? | Experiment in phase 2: userptr on 64 MB, read back via a compute shader; measure. Fallback: KFD/HMM SVM (compute only). |
| Q2 | *Answered 2026-09-29 → F12.* Remaining sub-question: which of the three `cmds[]` slots of the `0xc0488131` submit header carry the DCB and the CCB. | First capture through the phase-1 tap; `bc5-agc report` on each slot separately. |
| Q3 | Do PS5 titles write CU masks themselves? | Phase 1 logs: count `SET_SH_REG` writes to the mask registers. If yes, our mask must be ANDed, not overwritten. |
| Q4 | Which draw/CB/DB register usage is Sony-specific beyond public PM4? | Phase 1: diff decoded register offsets against Mesa's gfx10 register tables; unknown offsets go to `docs/formats/agc.md` as "unresolved". |
| Q5 | Storage: how much of the SSD/Kraken dependency can a software prefetch/cache hide? | Deferred to after phase 4. |
| Q6 | *Answered 2026-09-28 → F10.* Remaining sub-question: do other producers (console-side compressors) deviate from the PS5PKGTool/MkPFS layout? | Collect `bc5-mount inspect` output from containers made by other tools as they become available; each new producer is a one-line addition to `experiments/0001-ffpfsc-header-survey` successors. |
| Q7 | *Answered 2026-09-29 → F13.* | — |
| Q8 | *Answered 2026-09-29 → F14.* Remaining: does the extra third of the CUs execute at full rate? | Measured with the 36/40 switch in phase 3 (D5). |

## 4. Architecture (summary)

```
PS5 game (eboot.bin, PRX)  →  RPCSX loader + HLE  →  BC5 backend  →  amdgpu/libdrm  →  BC-250
                                     ├→ I/O layer (bc5-mount, later: prefetch/cache)
                                     └→ audio + input (HLE, unchanged)
```

Backend modes: (1) validation — decode + log, submit nothing; (2) hybrid — native shaders, commands via Vulkan; (3) direct — own libdrm client, 1:1 VA mapping, rewritten packets, `--submit`.

CU policy: runtime masked to 36 CU, 4 CU left for the desktop. Masks ANDed with any game-set masks (see Q3).

## 5. Phases and gates

See `docs/PHASES.md`. Order: 0a `bc5-mount` → 0b RPCSX baseline on BC-250 → 1 AGC validation → 2 native shaders → 3 IB submit (36/40 switch) → 4 integration.

## 6. Related projects (what to read, and for what)

| Project | Read for |
| --- | --- |
| RPCSX/rpcsx | host runtime; GPU directory (Q2); build instructions in `.github/BUILDING.md`; Discord for coordination before any PR |
| KytyPS5/KytyPS5 | `src/graphics/guest_gpu` (AGC decoding), `src/graphics/shader/recompiler` (cross-check for phase 2) |
| astraea-emu/astraea | PM4 framing of AGC DCB, `SET_SH_REG` lowering |
| boykopovar/AnyPS5 | AGC recorder driver (PR #5), packet list |
| OpenProspero/AGC | which packets are public vs. not; CPU simulation of PM4 snapshots |
| mpereiraesaa/ps5-vulkan | native submission on gfx1013 (closest code to phase 3) |
| orgito1015/AMD-GPU-Debugger | raw PM4 submission via libdrm, ACO null winsys |
| libdrm `tests/amdgpu` | `shader_code_gfx10.h`, dispatch/draw tests — phase 2/3 starting code |
| pearlxcore/PS5PKGTool | managed exFAT / PFSC / PFS — phase 0a reference |
| elektricm/amd-bc250-docs, bc-250.com wiki, akandr/bc250-rocm | BC-250 unlocks, BIOS, hazards |
| AMD RDNA 2 ISA Reference Guide (doc 70648); Mesa `src/amd/registers` (gfx10) | ISA and register tables |

## 7. Decisions taken so far

- D1 Project name **BC5** (BC-250 + PS5). Repo `bc5`; fallbacks `bc5-native`, `bc5-agc` if taken.
- D2 License GPL-2.0 (RPCSX compatibility).
- D3 Public, English, anti-piracy: no Sony material, bring your own console and dumps, no warranty.
- D4 Start with the input layer (`bc5-mount`) before anything GPU-related.
- D5 36/4 CU split as a backend switch, measured in phase 3.
- D6 Tools in Rust, backend in C++20 (RPCSX is C++).
- D7 (2026-09-29) Phase-1 preparation that needs no hardware and no game (Q2 research in the RPCSX sources, `docs/formats/agc.md`, the `bc5-agc` PM4 decoder with hand-built streams) may proceed before gate G0a is recorded, because it does not depend on `bc5-mount`. Phase 0b, anything under `backend/` and anything that submits to the GPU still wait for their gates. Maintainer's decision; overrides the "one phase at a time" rule of `CLAUDE.md` for this case only.
- D10 (2026-09-29) Prosper (github.com/mattias800/prosper, commit `1c93ab8`) is used **locally on the dev box as an external capture tool** while no firmware dump exists: it runs ASTRO BOT to its title screen without PS5 system modules. Prosper has **no licence**, so none of its code, text or data enters this repository, and nothing derived from it is distributed. It is built from source in the `ubuntu` distrobox (`~/src/prosper`, build in `~/bc5-work/prosper-build`) with one **local-only** patch (`~/bc5-work/prosper-bc5-dcb-dump.local.patch`, 24 lines in `hle_agc.cpp`) that writes each submitted DCB as raw dwords to `$BC5_AGC_DUMP_DIR`; its own `PROSPER_SHADER_DUMP` provides shader binaries. Captures live in `~/bc5-data/captures` and are never committed; experiments record only statistics produced by our tools. Caveat for every result: part of each DCB is written by Prosper's HLE of `sceAgcDcb*` rather than Sony's library, so captures describe "game + Prosper", not a console byte stream. Maintainer's decision.
- D9 (2026-09-29) Phase-2 preparation (ADR 0004: PM4 builder, memset IB, `dispatch-min` with `--dump-ib`/`--info`) may proceed before gates G0b and G1, because phase 0b is blocked on the maintainer's firmware dump and the preparation submits nothing. Running `dispatch-min --submit` still needs the maintainer's explicit go-ahead with the box idle, each time.
- D8 (2026-09-29) BIOS memory split: **512 MiB VRAM carve-out** (amdgpu: VRAM 512M, GTT 7596M; Linux sees 14 GiB) instead of the 8 GiB carve-out recorded in experiment 0003. Rationale: the PS5 memory model is unified and phases 2–3 map guest memory as system RAM (userptr/GTT, Q1); RPCSX needs host RAM for the 16 GB guest address space. Risk: Vulkan paths that insist on a large device-local heap; if VSH boot (phase 0b) fails on memory, compare splits in a dedicated experiment.
