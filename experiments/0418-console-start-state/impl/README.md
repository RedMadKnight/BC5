# 0418 build — the start-state table, the GS rings and the `/dev/gc` caller trace

**Status: built and tested on the laptop, 2026-11-13. Not built on the box and not run.** The box build waits for a slot from the top session. This file records the build; the analysis in `../README.md` is not changed by it.

**Order.** The top session, passing on the maintainer's question about exp 0418's lists:

> "a dlaczego nie pozwalamy zapisywać do tych rejestrów - tylko logujemy? co stoi na przeszkodzie? przecież mesa jest dobrze opisana"

In English: why do we only log these registers instead of writing them, and what stands in the way, when Mesa documents them well? The top asked for four things in one private build, each behind its own default-off switch, with nothing in the shared builds and no box work before its GO:

1. Write `VGT_ESGS_RING_SIZE` and `VGT_GSVS_RING_SIZE` from request 0xc00c8110 with the title's values, through `_UMD` (the path `GC_HS_OFFCHIP` takes).
2. Add the start-state table of `../README.md` §4, with `BC5_DIRECT_START_STATE` and `_SKIP`, and the existing switches as aliases.
3. Add the caller trace of §3b, to name F787's six requests and 0xc0048114, and for each named request say which register it sets and whether a user IB may write it.
4. Check whether any other `/dev/gc` request is answered with zeros or only logged although Mesa, Linux or PAL names its register, and if so, write it too.

## What was built

The base is the shared tree. It was patch 0001 `4651d1d3` when this was built; since 2026-11-13 15:47 it is candidate B `27b6416f`, the patch on main since `2ba82971` (the kit below has a diff for each). The scratch tree's diff against f266548 has md5 `4651d1d3`, the same as the patch file.

| Piece | Where | Switch | Default |
|---|---|---|---|
| The start-state table: 5 constant rows and 3 request rows | `backend/include/bc5/start_state.hpp`, with an identical copy as `src/bc5/start_state.hpp` in the diff; `backend/policy/start-state.tsv` is the same table plus the 9 rows met elsewhere, with sources | `BC5_DIRECT_START_STATE=1` turns on all rows. `BC5_DIRECT_START_STATE_SKIP=<names>` drops the named rows, whatever turned them on | off |
| The aliases | `start_state_sel()` in `bc5LleAgc.cpp` | `BC5_DIRECT_GC_TF_RING` → row `VGT_TF_RING`. `BC5_DIRECT_GC_HS_OFFCHIP` → `VGT_HS_OFFCHIP_PARAM`. `BC5_DIRECT_CP_COHER_START_DELAY` → `CP_COHER_START_DELAY`. `BC5_DIRECT_SPI_REQ_CTRL_PS` → `SPI_SHADER_REQ_CTRL_PS` | as before |
| The GS ring sizes from 0xc00c8110 | `gc_ioctl` keeps them; `Direct::gs_rings_prefix` writes them | `BC5_DIRECT_GC_GS_RINGS=1` (row `VGT_GS_RINGS`) | off |
| The caller trace | `Bc5Gc::ioctl_trace`, called from `Bc5LleKernel::Ioctl`; pure parts in `backend/include/bc5/gc_trace.hpp` (copy `src/bc5/gc_trace.hpp`) | `BC5_GC_IOCTL_TRACE=1`, diagnostic, compiled out of the lean build | off |
| Naming the NIDs afterwards | `nid-names.py` (laptop) | — | — |

**The kit.** It holds one diff of the same 3 files for each base the shared tree may have when the slot comes, each with its own sum list:

| Shared tree | Diff | sha256 (16 hex) | md5 | Sum list |
|---|---|---|---|---|
| patch 0001 `4651d1d3` (main, the shared builds of 2026-11-13) | `kit/0418-on-4651d1d3.diff` | `8f946cb2874252de` | `d2a4b31b` | `kit/tree-0418-on-4651d1d3.md5` |
| candidate B `27b6416f` (exp 0417 section 9; the shared builds since 2026-11-13 15:47, main's patch since `2ba82971`) | `kit/0418-on-27b6416f.diff` | `557656da0d691375` | `d857d736` | `kit/tree-0418-on-27b6416f.md5` |

`mk0418.sh` picks the pair by `P_TREE` and refuses any other base. It also holds `kit/test418.cpp`, the box's CPU test.

**How the B diff was made.**

- Tree B was rebuilt in the laptop's scratch: f266548 + `0001-new14.patch`, read from the integrator's kit, md5 `27b6416f`. All 129 files match main's `experiments/0417-shared-followups/tree-candidate-B-27b6416f.md5`.
- Then the 0418 commit was cherry-picked onto it, with no conflict.
- B changes none of the places 0418 edits (`prefix_of`, `gc_ioctl`, `Ioctl`, the includes). Its new headers (`save_guard0412.hpp`, `anon_sync.hpp`) bring no system ELF header. The 0418 function names occur once each.
- The syntax check below passes on both bases.

**The rows.** Values and lines are from `../README.md` §2 and the sources it lists; `start-state.tsv` gives each row's source.

| Row | Packet | Value | Status |
|---|---|---|---|
| `CP_COHER_START_DELAY` | `SET_UCONFIG_REG` 0x07b | 0x20 | inferred (it is the reset value) |
| `SPI_SHADER_REQ_CTRL_PS` | `SET_SH_REG` 0x030 | 0x7 | inferred |
| `GE_MIN_VTX_INDX` | `SET_UCONFIG_REG` 0x249 | 0 | inferred |
| `GE_MAX_VTX_INDX` | `SET_UCONFIG_REG` 0x259 | 0xffffffff | inferred |
| `VGT_INSTANCE_BASE_ID` | `SET_UCONFIG_REG` 0x25a | 0 | inferred |
| `VGT_TF_RING` | `_UMD` 0x24e, 0x250, 0x261 (unchanged code) | from 0x80108128 | cited (F248) |
| `VGT_HS_OFFCHIP_PARAM` | `_UMD` 0x24f (unchanged code) | from 0x8004812a | cited (F785, F786) |
| `VGT_GS_RINGS` | `_UMD` 0x240 and 0x241, one `SET_UCONFIG_REG` of two, as RADV writes it (`radv_queue.c:372-374` @ 0866ae7) | from 0xc00c8110, bytes >> 8 | cited (RPCSX `gc.cpp:295-307`); the unit is TODO(verify) |

"Inferred" stays until the umr read of `../README.md` §3 shows what the chip holds in play, as the top asked.

**Where the rows go.** The constant rows go first in every job's prefix, right after its `CONTEXT_CONTROL` and `CLEAR_STATE`. The tracker then writes back the title's own state, so the title's writes still win. The ring rows stay where the TF ring has always been, at the end of the prefix.

**`VGT_GS_RINGS`.** It gets RADV's `VS_PARTIAL_FLUSH` + `VGT_FLUSH` before the first write and before any change of sizes (`radv_queue.c:1048-1052`). The request is read as {ES→GS bytes, GS→VS bytes, 0}, the layout RPCSX gives. The unit is taken as bytes because that is the unit of the PS4 call that sets the same two sizes (shadPS4 60c42b9 `gnmdriver.cpp:1765-1782`: 4–8 MiB, MiB-aligned, the register gets bytes >> 8) and of RADV. A value that is 0 or not a multiple of 256 is logged and not written.

**What changes with nothing set: nothing.**

**With the second title's launcher words of 2026-11-13** (`GC_TF_RING`, `GC_HS_OFFCHIP` and `CP_COHER_START_DELAY` on):

- The same rows are on and the same packets are written. `test418` and the Catch2 tests check this.
- One thing moves: `CP_COHER_START_DELAY`'s packet now comes before the tracker's writes instead of after them. The tracker never holds that register (the 2026-11-02 audit: the title never writes it), so the chip gets the same value.
- Exp 0401's two journal lines are kept word for word.
- There is one new stderr line: `bc5-direct: start state (exp 0418): table off; rows on: CP_COHER_START_DELAY(alias) VGT_TF_RING(alias) VGT_HS_OFFCHIP_PARAM(alias); skipped: none`.

## What stands in the way (the maintainer's question)

**For the five constant rows: nothing but evidence.** These are uconfig and SH registers. Mesa's gfx10 preamble writes them from a user IB with these values (`ac_cmdbuf.c` @ 0866ae7), and none is in Mesa's privileged list (`ac_pm4.c:34`). They were not written for two reasons:

- On this box they very likely hold these values already, because KWin's and the presenter's RADV preambles on the shared gfx ring write them (`../README.md` §1, inferred).
- The one A/B that wrote two of them was confounded (§2).

They are now one switch away. The umr read decides whether the table changes anything at all.

**For the `/dev/gc` requests: knowing the register.** Writing is easy once a request is named: the CAM rows take the `_UMD` path the TF ring already uses. The audit of point 4 is below. Of the requests answered with zeros or only logged, only 0xc00c8110 had a register named in Mesa, Linux or PAL. It is now written.

**For the privileged state: the kernel.** A user IB cannot write `SH_MEM_*`, the golden set or `GB_ADDR_CONFIG`. Each is met another way: the code rewrite, the kernel's own values, or the BO list for GDS/GWS/OA. `start-state.tsv` names how each is met. `SPI_CONFIG_CNTL` could be written through its CAM row, but the console's value is not known, so no row writes it.

**Point 4: every `/dev/gc` request patch 0001 answers, against public sources.**

| Request | Public name | Register a user IB could write | Now |
|---|---|---|---|
| 0x80108128 | TF ring (exp 0189; `GraphicsDriverSetTFRing` by its NID, patch 0001's `src/libs/libGraphicsDriver.cpp:316`) | `VGT_TF_RING_SIZE`, `_MEMORY_BASE`, `_HI` via `_UMD` (CAM) | written (row `VGT_TF_RING`) |
| 0x8004812a | HS offchip (exp 0189, by its place) | `VGT_HS_OFFCHIP_PARAM` via `_UMD` | written (row `VGT_HS_OFFCHIP_PARAM`) |
| 0xc00c8110 | "set gs ring sizes" (RPCSX `gc.cpp:295-307`) | `VGT_ESGS_RING_SIZE`, `VGT_GSVS_RING_SIZE` via `_UMD` | **was logged only; now written** (row `VGT_GS_RINGS`) |
| 0xc010810b | "get cu masks param" (RPCSX `gc.cpp:322-337`) | — (an answer, not a write) | answered with all ones; the host masks the CU registers itself (F7, F39a) |
| 0xc0048114 | "SetWaveLimitMultipliers" (RPCSX `gc.cpp:392-398`); shadPS4's `sceGnmSetWaveLimitMultipliers` is a stub (`gnmdriver.cpp:2059-2067`) | not named by any public source read here. The `SPI_WCL_PIPE_PERCENT_*` set is a guess from the name only, TODO(verify) | answered with zeros; not in the second title's trace |
| 0xc0848119 | "stats report control?" (RPCSX `gc.cpp:309-320`, with its question mark); likely the PS4's mip-stats report, whose shadPS4 call is a stub (`gnmdriver.cpp:1974-1993`) | not named | logged |
| 0xc004811f | unnamed (RPCSX logs it, `gc.cpp:400-404`) | not named | answered with zeros |
| 0xc030810d, 0xc010811c | map compute queue, its doorbell (RPCSX `gc.cpp:339-390`) | a queue (MQD/HQD through the kernel), not start state; the direct path has its own compute ring (ADR 0009) | logged |
| 0xc0408121 | queue registration (patch 0001's reading) | a queue, not start state | recorded |
| 0xc004812e, 0xc008811b, 0xc0048113, 0xc0048115, 0xc0088101, 0xc0048116/7, the submits | capability, submit page, clients, closed, switch buffer, done/idle, submission | none | answered |
| F787's six: 0x80888123, 0xc010813b, 0x80048126, 0x80048134, 0xc0108139, 0xc0088133 | none in any public source read here | unknown until named | answered with zeros. **The trace below names their callers** |

**Verdict of point 4: found one, now written (0xc00c8110). No other request with a zero or log-only answer has a register that Mesa, Linux or PAL names.**

## Point 5: the seven unnamed requests against what a gfx10 driver must give the chip

**The order.** The top session added, from the maintainer: "może w dokumentacji MESA będzie odpowiedź (lub bezposrednio w kodzie MESA)" — perhaps Mesa's documentation, or Mesa's code itself, has the answer.

**The task.** Match the shape and values of F787's six requests and of 0xc0048114 against what Mesa, PAL and the kernel give a gfx10 chip. For each request: a candidate, its evidence, and a certainty. Reads only, on the laptop.

**The rule.** No register is written on a shape match. The trace confirms or refutes each candidate.

**Sources.** All fetched at the pinned commits into the laptop's scratch:

- Mesa 0866ae7: `src/amd/common/ac_gpu_info.c`, `ac_cmdbuf.c`, `ac_pm4.c`, `ac_descriptors.c`, `src/amd/vulkan/radv_queue.c`, `radv_device.c`, `src/amd/registers/gfx10.json`.
- Linux v7.2: `gfx_v10_0.c`, `amdgpu_gfx.c`, `include/uapi/drm/amdgpu_drm.h`, `gc_10_1_0_offset.h`, `gc_10_1_0_sh_mask.h`.
- PAL c5e80007: `gfx9QueueContexts.cpp`, `settings_gfx9.json`.

The values are from exp 0189's trace (`experiments/0189-ge-system-rings/raw/R0-ioctl-trace.txt`).

| Request | What the title sends | Candidate | Evidence | Certainty |
|---|---|---|---|---|
| 0x80888123, pair 3 | 0xf00144000, size 0x1000000 (16 MiB) | **The HS offchip ring**: the buffer that `VGT_HS_OFFCHIP_PARAM` = 0x1ff sizes. 0x1ff means 512 buffers (bits 0-8 = buffers − 1) of 8K dwords each (bits 9-10 = 0 = `X_8K_DWORDS`); 512 × 8192 × 4 B = 16 MiB exactly | Mesa `ac_gpu_info.c:1382` (8192 dwords per workgroup), `:1433-1436` (gfx8-gfx10.1 encoding: buffering = workgroups − 1), `:1447` (ring size = workgroups × dwords × 4); `gfx10.json:933-938` (`X_8K_DWORDS` = 0); Linux `gc_10_1_0_sh_mask.h:7078-7081` (the two fields) | inferred: exact arithmetic, no name. **Refuted by the trace** (result 2): the trace names this area as the driver's CWSR (wave save/restore) area. The match was arithmetic only |
| 0x80888123, the other five pairs | 0xf00000000 + 0x2400, 0xf00004000 + 0x4000, 0xf00008000 + 0xfc000, 0xc80008000 + 0x3bb00, 0xc80043d00 + 0xd00. Slots 5 and 6 are empty and the trailing quadword is 0: 8 slots and one more quadword make 136 bytes | **None of Mesa's preamble buffers fits.** Scratch and the ESGS/GSVS rings are sized per pipeline. The TF ring is the title's own, sent by 0x80108128 (0x3fff8 at 0x1120000000) and not in this table. RADV's border-colour table is 64 KiB, and its bases (`TA_BC_BASE_ADDR`, `TA_CS_BC_BASE_ADDR`) are written by the title's own stream (exp 0401's audit lists neither as unset) | `radv_queue.c:256-337` (the ring descriptors), `:870-940` (the buffers); `ac_cmdbuf.c:61-62`, `:529-530` (border-colour bases) | none |
| 0xc010813b | 16 bytes in and out; in = ffffffff ×4; the host answers zeros | **A CU mask per shader engine**: four dwords for SE0-SE3, all ones = every CU. Either the masks the kernel puts in its compute queues' MQD, or the PS5 form of 0xc010810b ("get cu masks param", the same 16 bytes; request number 0x0b against 0x3b is a pattern, not evidence) | Linux `gfx_v10_0.c:6916` and `:6925-6928` (`gfx_v10_0_compute_mqd_init`: `compute_static_thread_mgmt_se0..3` = 0xffffffff); `amdgpu_gfx.c:506` (`amdgpu_gfx_mqd_symmetrically_map_cu_mask`); Mesa `ac_cmdbuf.c:52`, `:66-72` (the gfx10 compute preamble writes `COMPUTE_STATIC_THREAD_MGMT_SE0..3`, 0 for an absent SE); RPCSX `gc.cpp:322-337` | inferred: shape and value |
| 0x80048126 | 4 bytes in, once, = 1 | **None.** The amdgpu UAPI's only single-integer per-context settings are the priority (NORMAL = 0) and the stable pstate (NONE 0, STANDARD 1). No item of Mesa's or PAL's start state is a lone flag outside a packet | `amdgpu_drm.h:246-251`, `:278`, `:288-289` | none |
| 0x80048134 | 4 bytes in, once, = 0 | **None** (as above) | as above | none |
| 0xc0108139, 0xc0088133 | 16 bytes {0, 1, 0, 0} and 8 bytes {0, 1}, in and out, around every submission header | **Bookkeeping per submission** (a ring, fence or context query), not start state. 16 bytes is the size of amdgpu's `drm_amdgpu_ctx` in/out, but amdgpu has no op 0 | `amdgpu_drm.h:246-251`, `:294-327` | none; not a register question |
| 0xc0048114 | 4 bytes in and out; RPCSX's PS4 path; not in the second title's trace | **Wave limits.** Either per pipe, `SPI_WCL_PIPE_PERCENT_GFX/HP3D/CS0-7` (mm 0x1f67 onward, BASE_IDX 0, i.e. dword 0x31c7 onward, outside every `SET_*` range, so a user IB cannot write them; v7.2's `gfx_v10_0.c` never writes them). Or per stage, `WAVE_LIMIT` in `SPI_SHADER_PGM_RSRC3_*` (SH, user-writable; Mesa writes 0x3f, no limit) | `gc_10_1_0_offset.h:5179-5188`; `ac_cmdbuf.c:439-441`, `:483-485` | none: from the name only |

**What the two candidates would need.**

- **The 16 MiB offchip ring needs no register.** The ring's address goes into the shaders' buffer descriptors, which the title's own driver builds (RADV does the same, `radv_queue.c:306-312`). The one register, `VGT_HS_OFFCHIP_PARAM`, is already written from 0x8004812a (row `VGT_HS_OFFCHIP_PARAM`). Two things are left to check:
  - that the 16 MiB is mapped for the GPU (the direct path maps the guest's GPU memory);
  - and, for F785's open TODO, that the water's HS/TES descriptors point into it.
- **The CU mask needs no register either.** The host already sets the CU registers in the title's stream (F7, F39a). Only the answer is open: zeros today, where 0xc010810b gets all ones. If the trace names a CU-mask export as the caller, answering with the input (all ones) becomes a candidate for its own default-off switch.

**Mesa's documentation (docs.mesa3d.org) adds nothing.** `drivers/amd.html` does not exist (404).

- `drivers/radv.html` covers none of the topics. It has only a general section on what RADV and the kernel each do.
- `envvars.html` has no entry for the rings, scratch, the border colour, GDS/OA, CU masks or wave limits. Its "preamble" is freedreno's preamble shader, and "shadowregs" is CP register shadowing.
- The code reads `AMD_CU_MASK` (`ac_gpu_info.c:82`, syntax at `:104`), which the page does not list.

Checked by grepping both pages, fetched 2026-11-13, and by one reader agent.

**The trace now names the table's areas.** For 0x80888123 the trace also prints, for each non-zero pair, the guest mapping the address lies in: its name as the title's driver gave it, its range, type and protection (`KernelVirtualQuery`). One run then says which of the driver's areas the table lists. The patch comments already know two such areas by name: the queue rings and the EOP pages. These lines stay in the run's log on the box; only roles go into a README.

**Verdict of point 5: one candidate by exact arithmetic (16 MiB = the offchip ring of 0x1ff), one by shape (0xc010813b = CU masks), five with none.** Nothing is written on these matches. The trace (§3b), with the mapping names, decides them.

**After the trace** (result 2): the 16 MiB candidate is **refuted**; that area is CWSR. The rule held: a write made on the arithmetic would have been wrong.

## The trace (§3b)

**What it prints.** With `BC5_GC_IOCTL_TRACE=1`, the first 8 calls of each request code are printed:

- The bytes passed in, the format of exp 0189's trace.
- Up to 8 guest return addresses, found by the frame-pointer walk from the libkernel ioctl's own frame.
- Up to 12 code addresses found by a scan of 64 stack quadwords above that frame.
- For 0x80888123 only: the guest mapping each non-zero pair lies in (point 5).

Each address comes with its module and the nearest exported function at or before it, by NID.

**The walk's stop rules.** The walk stops at a null, misaligned, non-increasing or too-distant frame, or at a failed read. A driver built without frame pointers then gives few frames, not wrong ones, and the scan is the fallback.

**What it reads.**

- Guest memory through `process_vm_readv` on its own pid, so a bad address is an error, not a fault.
- The module's dynamic symbol table, which the loader has already parsed.
- For 0x80888123, the host's own record of the guest's mappings (`KernelVirtualQuery`, which takes the memory lock while it reads). The trace holds no lock of its own at that point.

It reads no code.

**Locking.** The trace's lock covers its call counter only. The runtime linker holds its own lock while modules start (`RuntimeLinker::StartAllModules`), so the trace calls `FindProgramByAddr` outside its lock.

**Naming the NIDs.** Done on the laptop from public tables: `python -I nid-names.py <a copy of the trace lines> <refs>`. The copy stays in the laptop's scratch, because it holds offsets into the title's driver. Only the public names go into a README.

**The list the top asked for comes from that run:** each named request, the register it sets, and whether a user IB may write it.

**What a name proves.** A name found through a NID says which exported function sent the request. It does not say what the request does (LESSONS R34). The register comes from the name only where a public driver writes that register for that call; otherwise the entry stays a lead.

## Checks (laptop, Git Bash)

- **Backend tests.**
  - Configure: `cmake -S backend -B <scratch>/b418 -G "Visual Studio 18 2026" -DFETCHCONTENT_SOURCE_DIR_CATCH2=<main checkout>/backend/build/_deps/catch2-src -DFETCHCONTENT_FULLY_DISCONNECTED=ON`.
  - Build and run: `cmake --build <scratch>/b418 --config Debug --target bc5_backend_tests`, then `bc5_backend_tests.exe`.
  - Result: **All tests passed (34864 assertions in 136 test cases).**
  - The new tags alone, `[start_state]` (9 cases) and `[gc_trace]` (6): 167 assertions in 15 cases.
  - The build's only warnings are 5 × MSB8029, about the build directory being under the temp folder; none is from the compiler.
  - Among the start-state tests is one that checks the header against `start-state.tsv`, row by row.
- **The unit's new code.** VS clang 22: `clang++ -fsyntax-only -std=c++20 -Wall -Wextra -Werror` on the new regions. A script cuts them out of the edited `bc5LleAgc.cpp` and checks them against the real KytyPlus loader headers (`elf.h`, `runtimeLinker.h`), with stand-ins only for Linux's `process_vm_readv`, the journal and the tracker. Result: 0 diagnostics.
  - The whole unit cannot be compiled on the laptop (it needs Linux headers). The box build is the full check.
- **`kit/test418.cpp`.** Built with VS clang `-Wall -Wextra -Werror`: `test418: 15 of 15; end`.
- **The kit diffs.** `0418-on-4651d1d3.diff` applies with `git -c core.autocrlf=false apply` to a clean f266548 + `4651d1d3` tree, and its three files match `kit/tree-0418-on-4651d1d3.md5`. The B diff is the cherry-pick itself.
- **`mk0418.sh`.**
  - `bash -n` passes.
  - Dry run with stand-ins for `pgrep`, `distrobox`, `g++`, `cmake` and `ninja`, once on a fake home whose tree pins to `4651d1d3` and once on one that pins to `27b6416f`. Each time:
    - Lock claimed; tree checked; `test418` 15 of 15; both variants built and checked for their strings (the trace in normal, not in lean); binaries placed; lock released empty.
  - Refusals checked: built already; wrong diff; a foreign lock, left untouched; a base the kit has no diff for.
- **`nid-names.py`.** Tested on a synthetic trace against KytyPlus's `src/libs`: both test NIDs are named by their `LIB_FUNC` lines (`GraphicsDriverSetTFRing`, `GraphicsDriverSetHsOffchipParam`).

## On the box (needs the top's slot; not done)

Under the fixes-first rule, everything above is in one build, each piece behind its own switch.

1. **Build** (CPU only, about 45 minutes, no emulator). The kit goes to `~/bc5-work/exp0418/kit/`, then:

   On the shared tree as it is since 2026-11-13 15:47 (candidate B):

   ```bash
   P_TREE=27b6416f P_ARCH=75e30335 P_DIFF=557656da0d691375 bash ~/bc5-work/exp0418/kit/mk0418.sh
   ```

   Only if the shared tree were back on `4651d1d3`:

   ```bash
   P_TREE=4651d1d3 P_ARCH=75e30335 P_DIFF=8f946cb2874252de bash ~/bc5-work/exp0418/kit/mk0418.sh
   ```

   - `P_ARCH` is the archive's md5 from the 2026-11-13 integration record; B keeps it (exp 0417 section 9). Check it on the box first.
   - Output: `~/bc5-work/exp0418/bin/kyty_emulator` (normal) and `bin-lean/`.
2. **The trace run** (the top session's order of 2026-11-13 evening): one run of the second title with `BC5_GC_IOCTL_TRACE=1` only. The table and the GS rings stay off, so the run differs from the shared build only by the trace.

   ```bash
   bash ~/bc5-work/exp0418/kit/run0418.sh t418a 240
   ```

   - **`kit/run0418.sh`** passes the private binary (pinned by `built.md5`) and the one extra word to exp 0413's runner `run0413p.sh`, unchanged. That runner gives:
     - its own atomic BOX-LOCK claim;
     - RT on;
     - the private save copy;
     - the walk to G+240, ending at that time cap;
     - its sampler, fuse and watchdog.
   - Around it, `chk0417g.sh`'s pad recording (`evtest`, every key press of every joystick).
   - Afterwards it copies the trace lines out of the run's log into `~/bc5-work/exp0418/raw/t418a-trace.txt` and prints a count.
   - The laptop streams the kernel log and stops the run at the first amdgpu error line.
   - Checked on the laptop: `bash -n`; a stand-in dry run (a fake runner and home) passes; its refusals pass (a used tag, a wrong tag, a binary not in `built.md5`).
3. **The umr reads.** The maintainer made them at 18:03 (idle) and 18:06 (in play, shared build, table off) into `~/bc5-work/exp0418/idle.txt` and `play.txt`. `umr0418.py <idle> <play>` (laptop) prints each register at idle and in play, the expectation of §2, whether each `_UMD` equals its register, and the bank witness `GRBM_GFX_CNTL`. A read with the table on comes after the trace run.
4. **Name the NIDs on the laptop** (`nid-names.py`) and write the list of named requests: each with its register and whether a user IB may write it.

## Result 1: what the chip holds (the umr reads of 2026-11-13)

**The reads.** The maintainer ran `../README.md` §3's two commands. The files are in `raw/`:

- `umr-idle-20261113-1803.txt`: 45 values.
- `umr-play-20261113-1806.txt`: 23 values.

Both files are clean: no umr error, and the bank witness `GRBM_GFX_CNTL` reads 0 first and last in each.

**When they were taken.** The times come from the box: the read files' mtimes, the launcher's `lean.log` (it stops plasmashell for a game and starts it again after), and the game's `play-last.log`.

| Read | Box time | State |
|---|---|---|
| idle | 18:03:44 | No emulator, about one minute after game 1 (18:00:31 to 18:02:37). **Not a fresh boot**: the title's ring values are still latched (below) |
| in play | 18:06:19.99 (file closed) | Game 2 (18:04:05 to 18:06:24, the exp 0412 launcher, the shared build B, exit 0), at t ≈ 135 s of its log, with 25-28 flips/s in its last seconds. **The game was running and drawing during the read** |

**The five of §2: all as inferred.**

| Register | Reset | Idle | In play | §2's inference | Verdict |
|---|---|---|---|---|---|
| `CP_COHER_START_DELAY` | 0x20 | 0x20 | 0x20 | 0x20 | confirmed. It is the reset value, so exp 0401's switch writes what is already there |
| `SPI_SHADER_REQ_CTRL_PS` | 0 | 0x7 | 0x7 | 0x7, from the Mesa clients | confirmed. Not the reset value, and the launcher has exp 0401's switch off, so a Mesa client wrote it |
| `GE_MIN_VTX_INDX` | 0 | 0 | 0 | 0 | confirmed |
| `GE_MAX_VTX_INDX` | 0 | 0xffffffff | 0xffffffff | ~0 | confirmed. A Mesa client wrote ~0, so §2's clamp TODO is settled for play |
| `VGT_INSTANCE_BASE_ID` | 0 | 0 | 0 | 0 | confirmed |

**The rings and the CAM.**

- **`_UMD` = register: yes, all six pairs** in the idle read: the TF ring size, base and high base, the HS offchip parameter, ESGS and GSVS. The CAM maps as the kernel code says (`gfx_v10_0.c:7296-7475`): measured now, no longer inferred.
- **The title's values outlive the game.** One minute after game 1:
  - `VGT_HS_OFFCHIP_PARAM` = 0x1ff;
  - `VGT_TF_RING_SIZE` = 0xfffe (0x3fff8 / 4, the title's ring);
  - `VGT_TF_MEMORY_BASE` = 0x11200000 (0x1120000000 >> 8).

  Nobody else writes them, which is F780/F785's latch, here measured without a CP packet.
- **ESGS/GSVS = 0.** No GS ring was asked for.
- **`SPI_CONFIG_CNTL` = 0xc062c688,** its reset value. Nobody writes it.

**Also seen.**

- `GE_CNTL` reads 0xf680 at idle and 0 in play. `GE_PC_ALLOC` reads 0x1ff at idle and 0x3ff in play. The desktop's clients and the game write different values to these two.
- `TA_CS_BC_BASE_ADDR` = 0x01004100 in both reads; its reset value is 0. Someone writes it, and whether that is a Mesa client's border-colour buffer or the title's is not known (TODO).
- `SPI_WCL_PIPE_PERCENT_GFX` = 0x07ffffff, its reset value (`gc_10_1_0_default.h:2609`): nobody limits the gfx pipe's waves. `SQ_CONFIG` = 0x01180000 is its reset value too.
- The golden set as read is recorded in the idle file. It is the console's values that cannot be known, not these.

**Verdict of the read.** §2 holds by measurement:

- In play the five hold the drivers' values, and on this box the Mesa clients write them.
- The table's five constant rows therefore change nothing here today.
- Exp 0401's two switches are no-ops by measurement.

The limits:

- One sample in play, at t ≈ 135 s; whether the game was in the menu or in play then is not known.
- The idle read follows a game, not a fresh boot.

## Result 2: the build and the trace run (2026-11-13 evening)

**The build.** `mk0418.sh` ran on candidate B (`P_TREE=27b6416f P_ARCH=75e30335 P_DIFF=557656da0d691375`) from 18:13 to 18:24, CPU only, under its own lock line.

- The tree matched the laptop's: 3 files.
- `test418`: 15 of 15.
- Binaries: normal `6a0fab7b`, lean `7254438e`.
- Warnings: 284 and 287, against 282 and 285 for B's own build (`exp0413/p`). The warnings in `bc5LleAgc.cpp` are the same five (eight in lean), moved by the inserted lines. The two extra warnings come from tracy and SDL, which this fresh build compiled and B's incremental build did not. **None comes from 0418's code.**

**The run t418a.** `run0418.sh t418a 240` ran at 18:25:15: the second title, RT on, `BC5_GC_IOCTL_TRACE=1` only, through `run0413p.sh`, with one pad watched.

- **It ended early.** At 18:26:09, 54 s in and during the menu import, the kernel ran a **global OOM** (`constraint=CONSTRAINT_NONE`, `global_oom`) and killed two "Web Content" processes of a flatpak browser that was running on the box. The emulator was not the victim.
- **The laptop's stopper ended the emulator at 18:26:13.** It matched `amdgpu_gem_fault`, one line of that OOM's backtrace. That line is also why the runner's summary says "GPU HANG: kernel amdgpu line at 56 s, no reset line". No ring timeout or reset was printed, and no fault record was written (the newest is from 11:32).
- Pad keys: 0. G was not reached.
- After the run: no emulator, launcher or mount; MemAvailable 13.2 GB.
- Not attributed to 0418: the trace's own memory is a few kilobytes. It is the menu's memory wall of exp 0417 section 10, here with a browser alive on the box. One run, so not shown either way.
- The stopper's filter was wider than meant: an OOM backtrace stops the run too. That is the top session's rule (stop at the first kernel error), but it is noted for the next run.

**What the run's log shows of 0418.** The start-state line reads `table off; rows on: CP_COHER_START_DELAY(alias) VGT_TF_RING(alias) VGT_HS_OFFCHIP_PARAM(alias)`: the launcher's three old switches turned on their rows, as designed. The TF ring (0x1120000000, 0x3fff8) and the offchip parameter 0x1ff were programmed, as before.

**The trace.** 12 request codes and 47 calls, all before the OOM: 361 frame lines, 189 scan lines and 6 pair lines. The lines stay in the laptop's scratch and on the box (`~/bc5-work/exp0418/raw/t418a-trace.txt`), because they hold offsets into the title's code.

- The NIDs were named by `nid-names.py` against `refs/`. Five have public names: shadPS4 60c42b9 `aerolib.inl`, KytyPlus `libAgcDriver.cpp`, and pcsx5 `nid_db.txt`.
- Four have none: the driver's lowest export, under which its internal functions fall, and three others.

| Request | Who sends it (the call chain, outermost first) | What it is | Register or resource | Can a user IB write it? |
|---|---|---|---|---|
| 0x80888123 | the driver's own initialisation: internal code of `libSceAgcDriver`, called from the host's loader (module start), with no exported API above it | **The table of the driver's system areas.** By the names the driver gave the mappings: pair 0 is trap-handler code (0x2400 of a 16 KiB area); pair 1 is trap-handler data (16 KiB); pair 2 is the CWSR area (16 MiB, wave save/restore); pair 4 is an area named "DDID" (1008 KiB, role unknown). Pairs 3 and 7 (0xc80008000, 0xc80043d00) lie in no guest mapping | The trap handler's base and memory, `SQ_SHADER_TBA_LO/HI` and `SQ_SHADER_TMA_LO/HI` (`gc_10_1_0_offset.h:2469-2475`), per VMID. The CWSR area is a per-queue context save area in the MQD (`cp_hqd_ctx_save_base_addr`, `kfd_mqd_manager_v10.c:133-140`) | **No.** Both are the kernel's, and in Linux only the KFD sets them: TBA/TMA by `kfd_ioctl_set_trap_handler` (`kfd_chardev.c:646-667`), CWSR from the queue's arguments (`:268-293`). The kernel enables traps only for the KFD's VMIDs (`gfx_v10_0.c:5175-5192`, called at `:5232`). Our path uses amdgpu's graphics VMIDs, so the title runs with no trap handler and no CWSR |
| 0x80048126 = 1 | driver initialisation, as above | not named | none | — |
| 0x80048134 = 0 | driver initialisation | not named | none | — |
| 0xc010813b, ffffffff ×4 | driver initialisation | not named; the CU-mask candidate of point 5 stays a shape match | (CU masks, if so) | — |
| 0xc0108139 {0,1,0,0} | the title → `sceAgcSuspendPoint` (libSceAgc) → (once `sceAgcSetSubmitMode`) → an unnamed driver export → `sceAgcDriverSubmitCommandBuffer` → internal | bookkeeping of the submission made at a suspend point | none (not state) | — |
| 0xc0088133 {0,1} | the same chain, without `sceAgcSetSubmitMode` | as above, the other half of the pair | none | — |
| 0xc0048114 | not sent (as in exp 0189's trace) | — | — | — |

The requests that were already named fit the names:

- 0xc0408121: `sceAgcDriverCreateQueue`.
- 0xc0188132 and 0xc0488131: `sceAgcDriverSubmitCommandBuffer`, with `sceAgcDriverSetWorkloadStreamInactive`.
- 0x80108128 and 0x8004812a: one unnamed export, called from the title's code.

**What this answers.**

- **The seven requests are named as far as public sources allow.** Two are the suspend point's submission bookkeeping, not registers. Four come from the driver's initialisation with no API name above them; the trace names one of their contents, 0x80888123's areas. 0xc0048114 is not sent.
- **No register a user IB could write is missing.** The one new system resource, the trap handler and CWSR areas, is the kernel's, and on Linux only the KFD's. This is a lead, not a finding: on the console the title runs with its trap handler installed, and here with none.
  - It is TODO(verify) whether the title's shaders ever trap: the `TRAP_PRESENT` and `EXCP_EN` bits of its `SPI_SHADER_PGM_RSRC2_*` and `COMPUTE_PGM_RSRC2` (`gc_10_1_0_sh_mask.h:15785-15798`, `:17169-17175`), and `s_trap` in its code.
  - If they do, a GPU fault is a candidate cause, which the fault records could be checked against.
- **Nothing is written on these names.**

## Result 3: the switch dispositions, as a diff on candidate E (2026-11-13 evening)

**The order.** The top session, after 0418 merged into main (466d56f6, patch 27b6416f unchanged), on the maintainer's rule "Pozbądź się zbędnych przełączników" (drop the switches you no longer need). The diff goes on the integrator's candidate E (exp 0419) and into the candidate after E, not into E itself.

- **(a)** `BC5_DIRECT_CP_COHER_START_DELAY` and `BC5_DIRECT_SPI_REQ_CTRL_PS` are no-ops by measurement: delete them.
- **(b)** The start-state table is always on, without `BC5_DIRECT_START_STATE`; only `_SKIP` stays, as a diagnostic. The five constant rows take the source "measured, umr 2026-11-13".
- **(c)** The GS-ring write is permanent, with no switch.
- **(d)** `BC5_GC_IOCTL_TRACE` stays as a diagnostic, off.
- (b) and (c) must pass a run of both titles in the integrator's chain.

**The base.** E is f266548 + the integrator's `0001-new17.patch`, md5 **410273ca**, unit 449878ca. It was rebuilt in the laptop's scratch, and all 130 files match `experiments/0419-switch-cleanup/tree-candidate-E-410273ca.md5` (branch exp/0419-switch-cleanup). The 0418 commits were cherry-picked onto it with no conflict; E touches none of 0418's places.

**What the diff does** (`kit/0418-on-410273ca.diff`: sha256 `3ea456f6f71d0237`, md5 `c4c95fd7`, 4 files; `kit/tree-0418-on-410273ca.md5`):

- **The table.**
  - `select()` turns on every row less those `BC5_DIRECT_START_STATE_SKIP` names.
  - The fields `table`, `by_alias` and `alias` are gone.
  - The five constant rows have the status `Measured`.
  - Nothing reads the six old words any more: `BC5_DIRECT_START_STATE`, `_CP_COHER_START_DELAY`, `_SPI_REQ_CTRL_PS`, `_GC_TF_RING`, `_GC_HS_OFFCHIP`, `_GC_GS_RINGS`. At 0 or at 1 they change nothing, and the tests check that.
- **The unit's texts.**
  - The stderr line reads `bc5-direct: start state (exp 0418): rows on: …; skipped: …`, printed once at the first request.
  - The `/dev/gc` TF-ring and offchip lines say `(programmed, row …)`, or `(not programmed: SKIP names …)`.
  - Exp 0401's two journal lines are gone. One journal line gives the constant rows' size.
- **The trace.** Its switch is read through `bc5::gc_trace::switch_on`, moved there from the table's header.
- **E's title table** (`src/bc5/switch_defaults.hpp`). The rows `BC5_DIRECT_CP_COHER_START_DELAY`, `BC5_DIRECT_GC_TF_RING` and `BC5_DIRECT_GC_HS_OFFCHIP` are removed, because their words are read by nothing now. The second title keeps 42 rows, not 45, so the integrator's `test0419defs.cpp` ("45 rows") needs its count changed to 42; I told the integrator.
- **`backend/policy/start-state.tsv`.** The status is "measured" for the five; the switch column is "-" for every row the table writes. It is regenerated by `impl/mktsv418.py`.

**What changes in behaviour.** With E's title table, the second title already had the TF ring, the offchip parameter and `CP_COHER_START_DELAY`. The new things are below.

- **Second title.** The other four constant rows are now written in every prefix; by result 1, they hold these values in play anyway. The GS-ring write is armed, but this title never sends the request.
- **ASTRO BOT.** It now gets all of it:
  - the five constant rows;
  - the TF ring and offchip parameter, but only if its driver sends those requests;
  - the GS rings, likewise only on request.

  Today it gets none of them. This is why (b) and (c) must pass a run of both titles.

**Checks (laptop).**

- Backend tests: 135 test cases, all pass. Five old start-state cases were replaced by three: every row with nothing set, the deleted switches read by nothing, and SKIP. One case for the trace's switch was added.
- `clang++ -fsyntax-only -Wall -Wextra -Werror` on the unit's new regions of tree E, against the real loader headers: 0 diagnostics.
- `kit/test418.cpp` against tree E's headers: 15 of 15.
- The diff applies to a clean E tree, and its 4 files match.
- **The older kit diffs on 4651d1d3 and 27b6416f keep the old semantics.** They are the record of the build that ran (result 2). `mk0418.sh` builds only those two bases; the E diff is for the integrator's fold.
- **`kit/test418.cpp` now tests the new semantics,** so `mk0418.sh` is not to be run again: it would fail its CPU test on the old bases. The `test418.cpp` the build of 18:13 used is the one at commit `cac916fd`.

**Box words that become dead.** The desktop shortcuts e10-menu and 0412-fast9 set `BC5_DIRECT_SPI_REQ_CTRL_PS=0` and `BC5_DIRECT_CP_COHER_START_DELAY=1` (exp 0419's inventory). They do no harm, since nothing reads them. Changing a shortcut needs the maintainer's own word, so they are listed here and not touched. E's launcher diff already drops the three exports from `play-pkg.sh`.

**The stopper and the runner** (LESSONS R54). The laptop's stopper is now `kit/kern0418.sh`.

- **What counts as a GPU error.** A GPU error line names amdgpu together with timeout, reset, fault, fail, error or hang. A stack frame (`name+0xOFF/0xLEN`) does not count, and neither does the plasmashell `RA24` line.
- **OOMs.** OOM lines are counted and named, and they do not stop the run.
- **Tested** with `--classify`:
  - the t418a stream gives 0 GPU error lines and 4 OOM lines;
  - a sample with a ring timeout, a page fault, a reset, the RA24 line and a frame gives 3 GPU error lines.
- **`run0413p.sh:204` has the same pattern** (`amdgpu.*\(timeout\|reset\|fault\)`), which is why t418a's summary says "GPU HANG". That runner belongs to exp 0413/0417; the fix is noted for its owner in R54.

## Result 4: the trap handler, the CU-mask answer, a fresh-boot read

**(1) The trap handler.**

- **What the console gives.** The title's driver registers its trap-handler code and data with the system (0x80888123, result 2), and the system installs them.
- **What amdgpu gives our process: no trap handler.** amdgpu's graphics VMIDs have none: the kernel enables traps only for the KFD's VMIDs (`gfx_v10_0.c:5175-5192`, `:5232`). TBA/TMA are set only by the KFD's `kfd_ioctl_set_trap_handler` (`kfd_chardev.c:646-667`).
- **What the graphics stacks expect.** LLVM's AMDGPUUsage, "Trap Handler ABI" (llvm.org, fetched 2026-11-13):
  - On HSA (ROCm, with the KFD) the runtime installs a trap handler that serves `s_trap`, and `llvm.trap` is `s_trap 2`.
  - "For code objects generated by AMDGPU backend for non-amdhsa OS, the runtime does not install a trap handler": there `llvm.trap` becomes `s_endpgm` and `llvm.debugtrap` nothing. Mesa and PAL graphics are such targets, so they never rely on a handler.
  - The same page says `COMPUTE_PGM_RSRC2.TRAP_PRESENT` "is set by the CP if the runtime has installed a trap handler".
- **Open.** What the hardware does with `s_trap`, or with an enabled exception, when no handler is installed: TODO(verify) against the RDNA 1.0 ISA guide, whose PDF did not load on 2026-11-13.
- **Whether the titles ask for traps** needs their captured buffers, which are on the box. `kit/trap0418.py` counts, over exp 0401's audit set, every `SET_SH_REG` of a stage's RSRC2 and how many have `TRAP_PRESENT` or any `EXCP_EN` bit. It also counts `LOAD_SH_REG` ranges that cover an RSRC2, whose values it cannot read. It was tested on a synthetic buffer.
- **The scan on the box** (2026-11-13 19:13:40-19:13:42; `kit/scan0418.sh`, one lock line, read-only; output `raw/trap-scan-20261113-1913.txt`): **none of the 387 RSRC2 values the titles SET asks for a trap handler or an exception.** PS 27, GS 27, HS 27 and CS 306, every one with `TRAP_PRESENT` = 0 and `EXCP_EN` = 0.
  - **What it covers.** The set on the box today is 43 buffers in 20 capture directories, all GPU-timeout captures (`play-*/gc/ib-timeout-*.bin`) from 2026-11-05 to 11-13. The `ibdump-*` set of exp 0401's audit (1,347 buffers) is no longer there.
  - **Which title.** The capture logs do not name the title, so the counts cannot be split by title. The dates are those of the second title's plays and runs, but that is not shown.
  - **What it cannot see.** 729 RSRC2 values arrive by `LOAD_SH_REG` from the title's memory (PS 659, VS 35, GS 35), and their bits are not read here.
  - **No dumps of the titles' shader code** were found to look for `s_trap` in. The `wd` working directories hold ten shader-named entries each, most likely the emulator's caches; not checked.
- **What this means.** In every value the stream sets directly, the titles' shaders run with no trap handler and no exceptions enabled, which is what amdgpu gives them here. So the console's trap handler is not used through the RSRC2 bits that were seen. It most likely serves the system's CWSR preemption (inferred). Open: the loaded RSRC2 values, and `s_trap` in the code.
- **How to meet it, if they do.** Without the KFD there is no way to install a trap handler from a user IB, because TBA/TMA are privileged per-VMID registers (`gc_10_1_0_offset.h:2469-2475`). The ways open:
  - **(i)** Clear `TRAP_PRESENT` and `EXCP_EN` in the title's RSRC2 writes, as the filter already rewrites the CU masks. An exception then does not enter a handler; that is what Mesa's graphics shaders run with.
  - **(ii)** Run the title's compute through the KFD (`/dev/kfd` queues with a trap handler and CWSR). That is a new path for the direct backend.
  - **(iii)** Leave it, if no title asks.
  - The CWSR area and trap code most likely serve the console's mid-wave preemption of compute (inferred from the names). The kernel's own CWSR handler serves the same purpose for KFD queues. amdgpu's graphics and compute rings here do not preempt mid-wave, so that use does not arise.

**(2) 0xc010813b: the zeros we answer do not restrict CUs.**

- F39 (exp 0016) measured the title's own CU masks in its stream: `COMPUTE_STATIC_THREAD_MGMT` 0xffffffff, `RSRC3_PS/GS` 0x0000ffff, `RSRC3_HS` 0xffff0000. All CUs, even though the host has answered this request with zeros from the start (the default case of `gc_ioctl`).
- The host then ANDs the title's masks with its own CU mask (`pm4-policy.tsv` rows 0x2c07…0x2e1a, F39a).
- So whatever the driver does with the answer, its masks come out full, and the zeros take no CU away. The driver's code was not read; the stream it produces settles the question.
- No change. An echo of the input (all ones) would only be cosmetic, and is not made without a reason.

**(3) A read after a fresh boot is not needed.**

- The five constant rows are measured in play, which is the state that matters.
- The reset values of the CAM rows and of the five are in Linux's `gc_10_1_0_default.h`, cited per row.
- The request rows act only when a title asks, and then with its value.
- No row depends on what the chip holds at boot.

## Open

- **A second trace run is not needed for the names.** All requests before the menu were caught.
- **Whether the titles' shaders trap: none of the 387 set RSRC2 values does** (result 4). Open:
  - the 729 values loaded by `LOAD_SH_REG`: the host's full-state tracker sees them, so a journal of the loaded RSRC2 words in one run would settle it;
  - `s_trap` in the code: it needs a dump of the titles' shaders, and none was found.
- **The table and the GS rings on both titles:** in the integrator's chain, after E (result 3).
- **The memory wall in the menu.** It belongs to exp 0412/0417, not to 0418.
- `0xc00c8110`'s unit on the PS5 (TODO(verify)). No title of ours sends it.
- **Frame pointers.** The title's driver keeps them: frame walks through `libSceAgcDriver`, `libSceAgc` and `eboot.bin` came out whole.
- **Integration.** The diff folds into patch 0001 when the top and the integrator decide. The two headers, their tests and `start-state.tsv` are on this branch. `backend/CMakeLists.txt` gains the two test files and the TSV's path.
