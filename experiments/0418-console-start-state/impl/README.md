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
| 0x80888123, pair 3 | 0xf00144000, size 0x1000000 (16 MiB) | **The HS offchip ring**: the buffer that `VGT_HS_OFFCHIP_PARAM` = 0x1ff sizes. 0x1ff means 512 buffers (bits 0-8 = buffers − 1) of 8K dwords each (bits 9-10 = 0 = `X_8K_DWORDS`); 512 × 8192 × 4 B = 16 MiB exactly | Mesa `ac_gpu_info.c:1382` (8192 dwords per workgroup), `:1433-1436` (gfx8-gfx10.1 encoding: buffering = workgroups − 1), `:1447` (ring size = workgroups × dwords × 4); `gfx10.json:933-938` (`X_8K_DWORDS` = 0); Linux `gc_10_1_0_sh_mask.h:7078-7081` (the two fields) | inferred: exact arithmetic, no name |
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

## Open

- The box build, the trace run, the umr read and the play: none done.
- `0xc00c8110`'s unit on the PS5 (TODO(verify)). No title of ours sends it.
- Whether the title's driver keeps frame pointers. The scan covers the case where it does not.
- **Integration.** The diff folds into patch 0001 when the top and the integrator decide. The two headers, their tests and `start-state.tsv` are on this branch. `backend/CMakeLists.txt` gains the two test files and the TSV's path.
