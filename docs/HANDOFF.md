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
| F7 | CU masks are SH registers written by the submitter: `COMPUTE_STATIC_THREAD_MGMT_SE0-3` (compute), `CU_EN` fields in `SPI_SHADER_PGM_RSRC3_PS/VS/GS/HS` (graphics). RADV/radeonsi use them. Basis for the 36/4 CU split. | Mesa `src/amd/registers`, RADV source | High (register existence), Medium (behaviour on gfx1013) |
| F8 | PS5 dumps circulate as unpacked `app0` folders, exFAT images, `FFPKG` (UFS2) or `.ffpfsc` containers. `.ffpfsc` = PFS v2 image (64 KiB blocks) wrapping one PFSC-compressed exFAT image of the dump. Console-side compressors produce `.ffpfsc` directly. PFSC decompression measured ~900 MB/s on PC. | thanhsondev/PSVIETHOA-FPKG-Builder release notes; pearlxcore/PS5PKGTool; juma-sayeh/PS5-Game-Compressor | High |
| F9 | KytyPlus intercepts hypervisor CPUID leaf `0x40000000` ("SonyPS5") — some titles probe it. Replicate in the loader if RPCSX does not. | Coder787-source/KytyPlus | Medium |

## 3. Open questions

| # | Question | Plan |
| --- | --- | --- |
| Q1 | 1:1 memory mapping: can `AMDGPU_GEM_USERPTR` + user-chosen GPU VA (`amdgpu_bo_va_op`) map GPU VA = game CPU pointer with zero copies on an APU? | Experiment in phase 2: userptr on 64 MB, read back via a compute shader; measure. Fallback: KFD/HMM SVM (compute only). |
| Q2 | How does RPCSX handle AGC today — own parser, or shared with PS4 GNM? | Read the GPU directory of the RPCSX tree before writing the tap (phase 1). Record file paths in `docs/formats/agc.md`. |
| Q3 | Do PS5 titles write CU masks themselves? | Phase 1 logs: count `SET_SH_REG` writes to the mask registers. If yes, our mask must be ANDed, not overwritten. |
| Q4 | Which draw/CB/DB register usage is Sony-specific beyond public PM4? | Phase 1: diff decoded register offsets against Mesa's gfx10 register tables; unknown offsets go to `docs/formats/agc.md` as "unresolved". |
| Q5 | Storage: how much of the SSD/Kraken dependency can a software prefetch/cache hide? | Deferred to after phase 4. |
| Q6 | Exact on-disk layout of PFS v2 / PFSC / the exFAT wrapper in `.ffpfsc`. | Phase 0a: derive from the managed implementations in PS5PKGTool and the FFPFS CLI, document in `docs/formats/ffpfsc.md`, verify against synthetic containers built with `fpkg-cli`. |
| Q7 | Host kernel / Mesa / libdrm versions on the dev box; whether the kernel carries the BC-250 PSP/CCP patch series. | First experiment of any GPU phase: record `uname -a`, `glxinfo -B`, `vulkaninfo --summary`, `pkg-config --modversion libdrm_amdgpu`. |

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
