# Exp 0401 series e10, tag nbo: null pages and GPU rights in the backend (`mknbo0401.py`)

Backend side of the e10 contract (scratchpad `e10/CONTRACT.md` section 3 and item 5) for the host unit's switches
`BC5_DIRECT_AMM_NULL_BO`, `BC5_DIRECT_HOLES_NULL_BO` and `BC5_DIRECT_GPU_RIGHTS` (m10, another session). Laptop work only;
nothing here ran on the box. Written 2026-11-06; second round the same day (map_shared_rights, null ranges, null windows
inside a PRT window).

## 1. Why

Exp 0408 (`bc5-0408/experiments/0408-memory-review/README.md`, beec526b): B2 row N1, G1 "Unmapped pages", G6 rows 4-5.
`BC5_DIRECT_AMM_PRT=1` is in the launcher (0408 cites `play-pkg.sh:91`), so the AMM window is NULL PRT pages today
(`direct.cpp:886-895`, main 029e0d6b). Mesa ab2374a `src/amd/common/ac_gpu_info.c:437-442`: on GFX10-12 an SMEM load from
a NULL PRT page faults and hangs the GPU. The holes of the learned windows get a writable 2 MiB scratch BO today
(patch 0001 P:29597-29640, 29715-29735; it stops being zero once written, F257). Every shared mapping is R|W|X today
(D:870-871); G6 row 4 wants R or R|W from the title's GPU bits, as RPCSX maps the GPU's view with `prot >> 4`
(`rpcsx/gpu/Device.cpp:1028` at e8ae148; 0408 and the contract say 1027, which is the blank line before it).

RADV's null BO (Mesa ab2374a `src/amd/vulkan/winsys/amdgpu/radv_amdgpu_bo.c`): 8 MiB, VRAM, read-only (`:412-441`,
request `:427-429`), mapped in chunks of its size (`:143-166`), re-bound on an unbind (`:231-252`); VA flags
READABLE|EXECUTABLE, WRITEABLE only without READ_ONLY (`:40-48`). Differences here: RADV keeps the normal VA as PRT and
binds the null BO only at a "low" alias its shader pass sends SMEM loads to (`:136-141`, `:487-497`,
`radv_pipeline.c:539`); the title's shaders are not ours to rewrite, so here the null BO is mapped at the address
itself. RADV binds every chunk at BO offset 0 (`:156-157`); here a piece's BO offset is its VA mod 8 MiB (`null_pieces`).

## 2. The change (each part commented `exp 0401 e10 (tag nbo)`)

| file | input md5 (main 029e0d6b) | output md5 |
|---|---|---|
| `include/bc5/direct.hpp` | a9fcb26bc48efa2dc19cb0523bfd7a60 | 23f4ac97d7bf9f7cd3614b071bcae818 |
| `src/direct.cpp` | 51279eaeb0df4225d69ce0a60587cdb9 | c1e8328ac8b802881d4b2c9d6763b7b1 |
| `CMakeLists.txt` | 309acd3c464062352d3c1f43d3b9df23 | 2d1dc09d3f052211b257dcfbfe5a3ae5 |
| `tests/null_window_test.cpp` | (new; refused if present) | 98a30ce59bd7827820a219c097997a63 |

- New `Device` methods (non-virtual; Device's members unchanged; no existing signature changed):
  `bool map_shared_rights(std::uint32_t id, std::uint64_t bo_offset, std::uint64_t size, std::uint64_t gpu_va, unsigned rights);`
  `bool map_null_window(std::uint64_t va, std::uint64_t size, bool writable);`
  `bool map_null_range(std::uint64_t va, std::uint64_t size, bool writable);` and `bool unmap_null_range(std::uint64_t va);`
- Pure helpers in `direct.hpp`, all under `[nbo]` tests: `kNullBoBytes`, `NullPiece`, `null_window_pieces`, `null_pieces`
  (window base 0), `spans_overlap`, `span_inside` (half-open), `null_place` (-1 refused, 0 clear, 1 inside a PRT window),
  `kRightsRead/Write/Exec`, `shared_rights_flags`.
- `direct.cpp`: `SharedMap::vm_flags` (map_shared stores R|W|X explicitly, map_shared_rights its flags; map_alias gives an
  alias the mapping's flags, so map_shared's aliases keep R|W|X); `Impl`: `null_windows`, `null_ranges`, `null_bo`,
  `in_null`, `null_bo_get`, `null_bo_drop_if_unused`, `null_map`, counters. `va_map` REPLACEs inside a null window as
  inside a PRT window; `va_unmap` asks the null windows first (one may lie inside a PRT window) and REPLACEs the range with
  null pieces. Null ranges are not windows: `va_map`/`va_unmap` ignore them. `~Device`: PRT windows CLEAR (as before),
  null windows CLEAR, every null range's pieces UNMAP, one count line, then the BO is freed.
- The BO: VRAM, 8 MiB, `phys_alignment` 4096, `VRAM_CLEARED | NO_CPU_ACCESS | VM_ALWAYS_VALID` (RADV's request becomes
  NO_CPU_ACCESS at `:604-607` and VM_ALWAYS_VALID at `:612-616`; VM_ALWAYS_VALID because the direct path's BO lists name
  only the guest's mappings). RADV sets no VRAM_CLEARED (its comment says zero-allocated, `:424-425`) and allows a GTT
  spill (`:591-592`).
- Lines: per null window `null window 0x<va>+0x<size> (ro|rw): <rc>, <done> of <n> pieces ..., <ms> ms, <what>`; the first
  null range; each refused or failed null range; a failed re-bind or take-back; a refused rights value; at close the
  null-range counts.

## 3. Contracts (as in `direct.hpp`)

- `map_shared_rights`: rights 1 read, 2 write, 4 execute; read required, any other bit refused (false, nothing mapped,
  one line). Otherwise map_shared: same checks, sorted insert, `maps++`, `list_gen++`, REPLACE inside PRT/null windows;
  unmap_shared and free_shared unchanged. `mappings()` still lists it as shared with `readonly` false (the host skips
  shared entries there, P:29307).
- `map_null_window`: 64 KiB aligned; clear of everything this device has (MAP), or wholly inside one PRT window
  (REPLACE over its PRT pages: item 5's "null pages under the reservations, PRT for the rest"; map the PRT window
  first). Refused (-EEXIST in the line): an overlap with a userptr/shared mapping, a null window or range, or a PRT
  window's edge. On a failed piece the pieces before it go back (UNMAP, or PRT pages inside a PRT window); the BO is
  freed when nothing holds it. No call gives a null window back.
- `map_null_range`: 4 KiB aligned, outside every PRT and null window and every other null range; a mapping already there
  makes the kernel refuse it (counted as failed). `unmap_null_range(va)`: UNMAP of exactly the pieces mapped at that va;
  false when no range starts there or an UNMAP failed (forgotten either way).
- Null pages read 0. Read-only by default; writable means writes land in the one shared BO and show at every address with
  the same BO offset, in every null window and range.

## 4. Cost

- A null window or range of S bytes: about S / 8 MiB map ioctls (one per 8 MiB chunk touched), each updating the page
  tables at once (no `AMDGPU_VM_DELAY_UPDATE`, as RADV). The whole AMM window would be 64 GiB / 8 MiB = **8,192**; item 5
  maps only the reservations. A learned-window hole is usually 1-2 pieces.
- An unmap inside a null window: one REPLACE per chunk the range touches (PRT needed one in all).
- VRAM: 8 MiB plus page tables (below). Submissions: nothing (not on any BO list).

## 5. Risks and TODO(verify)

- TODO(verify): the kernel's page tables for null-BO mappings stay small while the BO is in VRAM (congruent offsets, so
  contiguous VRAM can use large fragments), while a GTT-backed BO needs 4 KiB PTEs (64 GiB: 2^24 x 8 bytes = 128 MiB).
  Not cited; the host journals VRAM/GTT use around the window maps. An eviction to GTT would bring the 4 KiB case back
  until a CS validates the BO into VRAM again. `AMDGPU_GEM_CREATE_VRAM_CONTIGUOUS` would pin contiguity (not used, as RADV).
- TODO(verify): what a GPU write to a read-only null page does with retry faults off (0408 G6 row 4); PRT drops it. The
  same question for a write through a map_shared_rights R or R|X mapping (G6 row 4: "becomes a fault").
- TODO(verify): that a REPLACE inside a null piece keeps the rest of the piece at its offsets (the kernel's split in
  `amdgpu_vm_bo_clear_mappings`; not cited from a checkout here).
- Limits: a mapping that straddles a null window's edge inside a PRT window is put back as PRT pages on unmap; a
  reservation given back keeps its null pages (no unmap_null_window); `map_alias` aliases userptr and shared mappings
  only, so a hole filled by a null range has no alias where the scratch BO's shared pieces had one; a half-failed
  re-bind leaves that part unmapped (faults) once the caller frees the BO, as with PRT.
- The host compiles against the edited `direct.hpp`. Patch 0001 calls `map_prt_window` in two places (P:28631, open;
  P:32769, re-open).

## 6. Laptop checks (2026-11-06, second round)

Scratch: `…\scratchpad\e10\nbo\`. Input: `git -c core.autocrlf=false archive 029e0d6b backend` (the laptop checkout is
CRLF); all 59 files of `backend0405.md5` match.
- **The script** (`python -I`, 3.14): the four md5s above, twice the same. Refused, rc 1, nothing written: its own
  output tree, one byte changed, the CRLF `direct.hpp`, a root with `tests/null_window_test.cpp`, out dir = root; no
  argument: usage, rc 2. Inputs unchanged after every run; the in-memory undo of all 14 edits gives each input back
  byte for byte (asserted in the script).
- **Literals** (`litscan.py`): none crosses a line in the three C++ outputs; `direct.cpp` goes from 118 to 139 literals and
  from 42 to 50 backslash-n escapes (eight new lines). A copy with a new `\n` made a newline is flagged (first round).
- **direct.cpp with BC5_WITH_AMDGPU** (lesson R02): no libdrm/amdgpu header on the laptop (Mesa's checkout is sparse and
  blobless), so stand-ins in scratch `standin/` declare what `direct.cpp` uses, with libdrm's parameter types and the
  uapi's int macros. VS clang++ 22.1.3 (MSVC target) `-fsyntax-only -std=c++20 -Wall -Wextra -Wpedantic -Wshadow
  -Wconversion -Wsign-conversion -Werror -DBC5_WITH_AMDGPU=1` (+ the two `_CRT_` defines): main's file clean, the edited
  one clean, also with `-Wshadow-all`. First-round negatives: against main's header it fails; `int done` fails.
- **[nbo] with the real Catch2 3.7.1** (`catch_amalgamated.cpp` from the laptop's FetchContent copy): the warning set
  above, Catch2 as `-isystem`, `-Wno-c2y-extensions` (clang 22 needs it for Catch2's `__COUNTER__` in main's own
  `env_flag_test.cpp` too): `All tests passed (149 assertions in 14 test cases)`, three runs. The sweep's counts (336
  ranges, 742 pieces, 216 inner) were computed apart in Python.
- **MSVC CMake build of the edited copy** (main's tree + the four outputs; `cmake -G "Visual Studio 18 2026"`,
  BC5_WITH_AMDGPU off, `FETCHCONTENT_SOURCE_DIR_CATCH2` = the local Catch2; MSVC `/W4 /WX`): 0 warnings; `All tests
  passed (34846 assertions in 135 test cases)` (121 on main, +14); `'[nbo]'`: `(149 assertions in 14 test cases)`; an
  unknown tag: "No tests ran", rc 2. Rebuilt and rerun after the last change (two comment lines: RPCSX 1027 -> 1028).
- **Mutants** (`mutate_nbo.py`, each one change to a pure helper or `kNullBoBytes`, built with `-w`, `'[nbo]'` run):
  **30 of 30 caught**, 29 by failing cases, 1 by the 60-s timeout (no chunk-0 guard: a division by zero, UB). The 16 of
  the first round on the splitter, and 14 new: null_pieces from the range's start; spans_overlap with touching ranges,
  an empty first or second range; span_inside without the size check or with `<`; null_place without its wrap guard,
  ignoring taken ranges, ignoring prt_inside_ok, allowing a PRT window's edge, reporting inside-PRT as clear; rights
  without the read requirement, with other bits, with write and execute swapped. Not used: swapped size arms in the
  splitter (would allocate without bound) and `span_inside` without `a >= b` (near-equivalent under wrap-around).
  The mutants ran on outputs that differ from the final ones only in those two comment lines.

## 7. Only the box can check

- The real build (CMake + Ninja, `-DBC5_WITH_AMDGPU=ON -DBC5_BUILD_TESTS=ON`, the box's compiler, libdrm 2.4.134
  headers), every Catch2 test, and `'[nbo]'` = `All tests passed (... in 14 test cases)`.
- No test calls a Device method (they need a device; hard rule 5). For an arm: the window lines (rc, pieces, ms),
  VRAM/GTT before and after, no VM fault in the AMM window or the holes, a map and unmap inside a null window (also one
  inside a PRT window), a null range taken back before an import, an alias of an R|X mapping, the fallbacks, and the
  TODO(verify) items above.
