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

The base is the shared tree: patch 0001 `4651d1d3` (main), and candidate B `27b6416f` once the integrator has swapped it in (the kit below). The scratch tree's diff against f266548 has md5 `4651d1d3`, the same as the patch file.

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
| patch 0001 `4651d1d3` (main, the shared builds of 2026-11-13) | `kit/0418-on-4651d1d3.diff` | `bf40cb55356cc9df` | `79fe2dd4` | `kit/tree-0418-on-4651d1d3.md5` |
| candidate B `27b6416f` (exp 0417 section 9, after the integrator's swap) | `kit/0418-on-27b6416f.diff` | `7f9efd19c5f32c9e` | `808e2805` | `kit/tree-0418-on-27b6416f.md5` |

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

## The trace (§3b)

**What it prints.** With `BC5_GC_IOCTL_TRACE=1`, the first 8 calls of each request code are printed:

- The bytes passed in, the format of exp 0189's trace.
- Up to 8 guest return addresses, found by the frame-pointer walk from the libkernel ioctl's own frame.
- Up to 12 code addresses found by a scan of 64 stack quadwords above that frame.

Each address comes with its module and the nearest exported function at or before it, by NID.

**The walk's stop rules.** The walk stops at a null, misaligned, non-increasing or too-distant frame, or at a failed read. A driver built without frame pointers then gives few frames, not wrong ones, and the scan is the fallback.

**What it reads.**

- Guest memory through `process_vm_readv` on its own pid, so a bad address is an error, not a fault.
- The module's dynamic symbol table, which the loader has already parsed.

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

   After the integrator's swap to candidate B:

   ```bash
   P_TREE=27b6416f P_ARCH=75e30335 P_DIFF=7f9efd19c5f32c9e bash ~/bc5-work/exp0418/kit/mk0418.sh
   ```

   If the shared tree is still `4651d1d3`:

   ```bash
   P_TREE=4651d1d3 P_ARCH=75e30335 P_DIFF=bf40cb55356cc9df bash ~/bc5-work/exp0418/kit/mk0418.sh
   ```

   - `P_ARCH` is the archive's md5 from the 2026-11-13 integration record; B keeps it (exp 0417 section 9). Check it on the box first.
   - Output: `~/bc5-work/exp0418/bin/kyty_emulator` (normal) and `bin-lean/`.
2. **One start of the second title, RT on**, with the launcher's own words plus `BC5_EMU=~/bc5-work/exp0418/bin/kyty_emulator BC5_GC_IOCTL_TRACE=1 BC5_DIRECT_START_STATE=1`, to the menu and a short play.
   - Expected: the start-state line with all 8 rows on, the trace lines, and no change in picture or speed.
   - `BC5_DIRECT_START_STATE_SKIP` bisects if anything changes.
3. **The umr read of `../README.md` §3** (the maintainer's sudo), once with the table off and once with it on, in play. This turns the five "inferred" rows into measured ones, or shows that one of them differs.
4. **Name the NIDs on the laptop** (`nid-names.py`) and write the list of named requests: each with its register and whether a user IB may write it.

## Open

- The box build, the trace run, the umr read and the play: none done.
- `0xc00c8110`'s unit on the PS5 (TODO(verify)). No title of ours sends it.
- Whether the title's driver keeps frame pointers. The scan covers the case where it does not.
- **Integration.** The diff folds into patch 0001 when the top and the integrator decide. The two headers, their tests and `start-state.tsv` are on this branch. `backend/CMakeLists.txt` gains the two test files and the TSV's path.
