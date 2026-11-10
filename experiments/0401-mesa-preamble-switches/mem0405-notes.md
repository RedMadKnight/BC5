# Exp 0401 series e5, tag mem: exp 0405's R3 memory ports in `src/kernel/memory.cpp` (notes, 2026-11-04)

Written for the e5 build. The input is e4's private unit (`mkmem0401.py`'s output, md5 `43713ef6…`), and its
`KYTY_BC5_MEMORY_FROM_PARAM` behaviour is kept unchanged: none of its lines are touched. The specs are exp 0405's
`raw/r3-gpu-memory.md`, in its ranked table and its "e4-now port specs". R3 cited line numbers in the base unit
(`e4/full`, md5 `f6154692…`). This input is 50 to 60 lines further down, because mem0401's globals block comes first.
No header is edited, and `memoryAddressSpace.inc` (shared) is not touched.

## Switches and the journal line

There is one switch per item, under R3's names, used as the environment variable names exactly as written (there is
no `KYTY_` prefix). They are `BC5_R3_MPROTECT_GAPS`, `BC5_R3_NULL_ARGS`, `BC5_R3_RELEASE_HOLES`,
`BC5_R3_MUNMAP_HOLES`, `BC5_R3_FLEX_HINT`, `BC5_R3_DMQ_END`, `BC5_R3_EXEC_EINVAL` and `BC5_R3_QUERY_SIZE`.

- A switch is on when it is set, non-empty and not `"0"` (F767's reading). All eight are read once, on first use, into
  a static array (`Bc5R3On`).
- At memory init (`KYTY_SUBSYSTEM_INIT(Memory)`, right after mem0401's line), the unit prints one stderr line:
  `[bc5] exp 0405: mem off`, or `[bc5] exp 0405: mem on (items: BC5_R3_MPROTECT_GAPS,BC5_R3_NULL_ARGS,…)` with the items
  that are on.
- With a switch off, today's code runs: every changed line keeps its old code in the off branch. Off adds only the
  journal line, an extra `Bc5R3On()` test, and in the unchecked release a named local for the result that was
  `(void)` before. That result is still not returned.
- Each event also gets a `LOGF` line in the emulator log (M1, M3, M7). These lines go to the log only, never to stderr.

## Per item

Line numbers are in the output (`95d9ca88…`); "input" is the e5 input.

### M1 `BC5_R3_MPROTECT_GAPS`: mprotect and mtypeprotect over gaps. Ported.

- **Sources:**
  - AnyPS5 `4f41f4c37` (GPL-2.0-only): `docs/dev/debt/libkernel.md:172`, measured on fw 13.60, commit `748b35835`
    (an ancestor of `4f41f4c37`). `DoMprotect` is at `core/libs/prx/libkernel/DirectMemory/DirectMemory.cpp:1484-1585`.
    `Export.cpp:326-330` and `478-481` call it with `requireMappedStart` false; the batch call at `Export.cpp:620-624`
    passes true.
  - shadPS4 `60c42b9` (GPL-2.0-or-later): `src/core/memory.cpp:1052-1178`. Gaps are skipped. A reserved VMA's protection
    is recorded without being applied (1104-1108). Free and PoolReserved VMAs are left alone (1059-1062).
- **Our code before:** the input has an EXIT on overflow (4031-4034) and an EXIT "not fully mapped" (4047-4054).
- **Change:**
  - New `Bc5MprotectGaps` (4245-4331, with its source comment). `KernelMprotect` branches into it when the switch is on (4344-4346; `KernelMprotect` itself starts at 4333), and
    `KernelMtypeprotect` reaches it through `KernelMprotect`.
  - The function walks the range table and takes each piece that lies in a range.
  - Committed pieces get today's per-piece treatment: the host view (`GuestAddressSpace::Protect`), the direct or
    flexible block, and the range table. A host protect failure still EXITs.
  - A Reserved piece gets the range table only; the host placeholder stays PROT_NONE. PoolReserved pieces and gaps are
    skipped.
  - The call returns 0, also for a range that starts in a gap or is wholly unmapped.
  - An overflow returns EINVAL. This includes the end-of-range overflow that today reaches the "not fully mapped" EXIT.
- **Batch:** `KernelBatchMap2`'s protect and type-protect operations (4466-4480) call it with `require_mapped_start`
  true. They return EINVAL when the aligned start is in no range, and skip later gaps (AnyPS5's batch form; AnyPS5
  notes it as unmeasured). With the switch off they call today's functions.
- **Safety:** each host protect is per committed piece and never touches a gap's placeholder.
- **Tests (case 1):**
  - On, over [A direct][gap][B direct]:
    - prot 0 and then 3 change A and B in the table and on the host (`/proc/self/maps` `---` and then `rw`); the gap
      stays unmapped and `---`;
    - the gap alone, and a range starting in the gap, return 0;
    - an unaligned start covers A's page;
    - mtypeprotect returns 0;
    - two overflows return EINVAL;
    - a reserved page records prot 3 while its host page stays `---`;
    - batch protect and type-protect from the gap return EINVAL with n 0; from A they return 0 with n 1 and change A
      and B.
  - Off: today's path over a fully mapped A (host `---` and then `rw`), mtypeprotect over B, and a batch protect over A.
    The gap, overflow, reserved and batch-gap calls EXIT today; they are skipped and printed as such.

### M21 `BC5_R3_NULL_ARGS`: guest NULL arguments. Ported.

- **`sceKernelQueryMemoryProtection(NULL)` returns EACCES** (3586-3594, before input 3373's
  `EXIT_NOT_IMPLEMENTED`), and no outputs are written.
  - Source: shadPS4 `60c42b9` `src/core/memory.cpp:1024-1030`, where an address below the mappable base gives EACCES
    (GPL-2.0-or-later).
  - AnyPS5 `Export.cpp:484-494` answers through `sceKernelVirtualQuery`, and NULL is unmapped there.
  - Why EACCES: NULL is an unmapped address, and this function already returns EACCES for every other unmapped
    address. Both sources agree on it.
- **`sceKernelMapNamedFlexibleMemory(addr_in_out == NULL)` returns EINVAL** (2518-2527, before input 2451's
  `EXIT_NOT_IMPLEMENTED`). `sceKernelMapFlexibleMemory` gets the same result through it.
  - Source: sharpemu `514d766` `KernelMemoryCompatExports.cs:3352-3360`, where a pointer of 0 gives
    `MemoryInvalidArgument`, that is EINVAL (GPL-2.0-or-later).
  - AnyPS5 `DirectMemory.cpp:1103-1108` (`ValidateOutput`) throws, and its comment names EINVAL.
  - shadPS4 dereferences `*addr_in_out` unchecked, so it gives no value here.
  - Why EINVAL: it has an explicit source, and AnyPS5 states the same intent.
- **Tests (case 2):**
  - On: EACCES with untouched outputs; EINVAL for both flexible maps; the flexible budget is unchanged.
  - Both modes: an unmapped non-NULL address gives EACCES and a mapped one OK (today).
  - Off: the two NULL calls EXIT today; they are skipped.

### M3 `BC5_R3_RELEASE_HOLES`: an unchecked release over holes. Ported.

- **Our code before:** the unchecked `KernelReleaseDirectMemory` returned OK but freed nothing, because
  `GetAllocatedSpan` failed on the gap (input 3021-3023) and the result was `(void)`. R3 says "returns EACCES": that is
  the internal result, and the guest saw OK.
- **Sources:**
  - KytyPS5 `dfec14a` `src/kernel/memory.cpp:1281-1315` (`GetAllocatedSpan` with `skip_gaps`) and 2354-2370 (GPL-2.0).
  - shadPS4 `60c42b9` `src/core/memory.cpp:283-376`; an unchecked free ignores free areas at 305-313.
  - AnyPS5 `MemoryPool.cpp:259-286`, where only used runs are forgotten.
  - **sharpemu `514d766` agrees with ours** (it frees nothing); R3 lists the disagreement.
- **Change:**
  - Today's call runs first, unchanged (3327).
  - Only when it fails and the switch is on, `Bc5ReleaseDirectMemoryHoles` (3259-3313) collects the allocated blocks in
    the range into runs of adjacent blocks. Each run goes through today's `ReleaseDirectMemoryInternal`, which also
    takes the run's mappings down.
  - A pool-expansion block in the range releases nothing, as KytyPS5 does (an expansion is freed only by an exact
    release, as today).
  - A range with no hole keeps today's result.
  - The checked form keeps ENOENT.
- **Tests (case 3):**
  - Setup: [allocated][free][allocated], with A mapped.
  - Both modes: the checked release gives ENOENT and frees nothing; the unchecked release returns 0.
  - On: both parts are freed (DirectMemoryQuery EACCES), and A's mapping is gone (EACCES, host `---`).
  - Off: nothing is freed (today); cleanup by exact releases.

### Extras (all S), in R3's order

- **M7 `BC5_R3_MUNMAP_HOLES`: ported.**
  - Sources: AnyPS5 `Export.cpp:332-339` and `DirectMemory.cpp:1615-1622` (prosper's console oracle,
    `libkernel.md:313`); shadPS4 `src/core/memory.cpp:913-1008` (942-944). **sharpemu agrees with ours** (an error).
  - Change: in `KernelMunmap`, when `QuerySpan` fails and the switch is on (2930-2932), `Bc5MunmapHoles` (2874-2915)
    unmaps each run of ranges without a hole through today's `UnmapGpuRange` and `UnmapMemoryRange`. A range with
    nothing mapped returns 0; the first error is returned.
  - Kept as today: length checks (AnyPS5 and shadPS4 disagree on non-page lengths), and a NULL address keeps EACCES
    (AnyPS5 gives EINVAL there; TODO(verify)).
  - Tests (case 4), over flexible [A][gap][B]:
    - On: munmap gives 0, A and B are gone, the budget is back, and munmap of nothing gives 0.
    - Off: both give EACCES and A and B stay (today).
    - Both modes: `munmap(NULL)` gives EACCES.
- **M6 `BC5_R3_FLEX_HINT`: ported.**
  - Sources: AnyPS5 `DirectMemory.cpp:1157-1160` (`PlaceHintInReservation`), used at 1205 (title-observed,
    `libkernel.md:109`; not measured); sharpemu `BackedMappings.cs:339-344`.
  - Change (2605-2632): in the non-fixed flexible branch, a page- and flag-aligned hint whose whole range lies in
    Reserved ranges consumes the reservation and is used, with the same code the direct-map path already has. The
    rollback paths that follow already handle `consumed_reservation`. The old lines are kept byte-identical inside
    `if (!consumed_reservation)`, so they are not re-indented.
  - Tests (case 5):
    - On: the map lands at the reservation (VirtualQuery shows flexible, committed, with the name).
    - Off: it lands after it (today).
    - Both modes: a hint over [reserved][gap] stays a hint.
- **M20 `BC5_R3_DMQ_END`: ported.**
  - Sources: AnyPS5 `Export.cpp:253-262` and `MemoryPool.cpp:125-136`; shadPS4 `src/core/memory.cpp:1242-1245`;
    sharpemu `KernelMemoryCompatExports.cs:3713-3739`. **KytyPS5 `dfec14a` `src/kernel/memory.cpp:2164-2170` agrees
    with ours** (the terminal record), so the switch matters.
  - Change (3072-3076): with the switch on, find-next past the last block skips the terminal record and returns
    EACCES.
  - Tests (case 6): on, EACCES; off, OK with [size, size) and type 0 (today); a find-next on a block works in both
    modes.
- **M18 `BC5_R3_SYSFLEX_BUDGET`: held.**
  - The system flexible map is `MapNamedSystemFlexibleMemory` in `bc5LleAgc.cpp:9299-9310` (another agent's file),
    which calls `KernelMapNamedFlexibleMemory` with no "system" mark. Not charging it needs a new entry point that lle
    calls: an lle edit plus either a header declaration or a local extern.
  - For later: a non-static `int Bc5KernelMapNamedSystemFlexibleMemory(...)` here, declared `extern` in lle by its
    owner.
- **M26 `BC5_R3_EXEC_EINVAL`: ported.**
  - Source: AnyPS5 `DirectMemory.cpp:1168`, after PS5_PayloadSDK's measure on fw 12.09 cited at `libkernel.md:190`
    (a title-level probe, not a hardware register fact).
  - Change (3370-3376; the comment begins at 3371): CPU execute returns EINVAL with the switch on and EACCES with it off; nothing is mapped either
    way. `MapDirectMemory2`, `MapNamedDirectMemory` and batch op 0 go through it as well (AnyPS5 says that is not
    measured for them).
  - Tests (case 7): prot 7, 4 and 0x35 give on EINVAL / off EACCES, `*addr` is untouched, and the block stays allocated.
- **M30 `BC5_R3_QUERY_SIZE`: ported.**
  - Sources: AnyPS5 `Export.cpp:373` (VirtualQuery) and `253-262` (DirectMemoryQuery: below the struct gives EINVAL);
    sharpemu `KernelMemoryCompatExports.cs:3579`; `libkernel.md:361` (titles pass sizes other than 0x48).
  - Change (3045-3051, 3957-3963): with the switch on, `info_size < sizeof` gives EINVAL; otherwise only the struct is
    written (VirtualQuery already memsets `sizeof` only).
  - Tests (case 8): on, 0x50 and 32 succeed and the bytes past the struct are untouched; off, EINVAL. Both modes: the
    exact size works and a smaller one gives EINVAL.

### Held, as the brief says

- M16, M17, M22-M25, M32: their registrations are in `libKernel.cpp`.
- M28: param.json sizing, in flight.
- Every R3 "later" item.

## The CPU test `mem0405.cpp`

- **Setup:**
  - It initialises core, threads, config (silent), log and memory, as `amm0401.cpp` does. It needs no
    `Libs::InitAll`, because it calls `kernel/memory.h`'s functions directly.
  - It runs 8 cases, one per item, each against its own switch, so mixed settings work too.
  - It reads `/proc/self/maps` for the host view, so it is Linux only.
- **Output:**
  - One line per case: `mem0405: case N <name> [<switch> on|off]: ok|FAIL (…)`.
  - With the switches off, 5 more `skip` lines name the EXIT paths that are not run: 3 for M1 and 2 for M21.
  - The last line is `mem0405: on 8 of 8; end`, `mem0405: off 8 of 8; end` (all off or unset), or
    `mem0405: mixed <items> 8 of 8; end`. The exit status is 0 only after that line.
  - A 60-second watchdog ends a hang with a FAIL line (exit 3). An argument that disagrees with the switches exits 2.
- **Build:** `build0401.py --gate mem0405.cpp <out> --like src/kernel/memory.cpp`, with the private `memory.cpp.o` in
  place of the shared one.
- **Runs:** all eight switches `=1` (`mem0405 on`), all `=0`, and all unset (`mem0405 off`).

## Verified on the laptop (no box access)

- `mkmem0405.py e5/e4tree <out>` prints `src/kernel/memory.cpp 95d9ca880d01db26d51f0ecabcdfa7e1`.
- Run on its own output, it stops with "has the edit already" (rc 1). A changed input stops on the md5 (rc 1).
- Built-in self-check: undoing every replacement (new to old, last first) gives the input back byte for byte.
  - `diff` shows exactly 8 old lines replaced. Each is an item's changed condition or call: M30 ×2, M20, M3, M26, and
    M1 batch ×2, where the type-protect call spans two lines. Everything else is an insertion.
- Braces, parentheses and brackets balance in the input, the output and the test (`balance_u8.py`).
- **Syntax:**
  - The laptop has no g++. Visual Studio's `clang++` (`-std=c++20 -fsyntax-only`) checked the output unit and the test
    in the tree's **Windows** configuration (stub `cmake_config.h`; fmt, magic_enum and the Vulkan SDK headers from
    local clones).
  - The output unit is clean under `-Wall -Wextra`. Under `-Wshadow -Wconversion` it has the same 12 warnings as the
    input, all in today's lines; the new code adds none.
  - The test is clean under `-Wall -Wextra -Werror`.
- **Not checked:**
  - the Linux branches of the unit (none of the new code is platform-specific);
  - GCC on the box;
  - the link;
  - running the test.
  The box build is the first real compile and run.

## Risks

- **M1 on:**
  - Protection is now recorded on Reserved ranges, which splits them in the table by protection. VirtualQuery and
    QueryMemoryProtection report it, and the AMM window (a Reserved range named "AMM") can get recorded protections;
    its name, consumption and re-reservation do not look at the protection.
  - The batch protect EINVAL for an unmapped start is AnyPS5's unmeasured choice. TODO(verify) on hardware.
  - Not ported: AnyPS5's measured "mtypeprotect over flexible pages returns 0x8002002d" (same debt line). Our
    mtypeprotect still ignores the type, as today.
- **M6 on:** a non-fixed flexible map hinted inside the AMM window's reservation would now land in the window, as
  direct maps already do today. AnyPS5's rule is title-observed, not measured.
- **M3 on:** the internal release can partly fail per run (EACCES on an alias unmap); the guest still sees OK, as
  today. A pool expansion in the range blocks the whole release (KytyPS5's choice; shadPS4 would free it).
- **M7 on:** a failing run after successful ones leaves those earlier runs unmapped. Today's single call has the same
  property inside `UnmapMemoryRange`.
- **Switch names:** the environment variables are R3's bare names without `KYTY_`, so the launcher must export them as
  written.

## Files

| File | md5 |
|---|---|
| `mkmem0405.py` (new) | `19d0f8d931e959e09e63c4e4f1211241` |
| `mem0405.cpp` (new) | `2cf39bd415b0dbadcc0cfed915a4a332` |
| `mem0405-notes.md` (new) | this file |
| in: `src/kernel/memory.cpp` (e4's unit) | `43713ef677ec887a8ca273f7ab5cee90` |
| out: `src/kernel/memory.cpp` | `95d9ca880d01db26d51f0ecabcdfa7e1` |
| read only: `src/kernel/memoryAddressSpace.inc` | `44586b1ee0e7edf12a0cd293ff9c141f` |
| read only: `src/kernel/memory.h` | `8c25cc1f4db620c177adb04e8ee17452` |
| read only: `src/libs/errno.h` | `024847d05a02f78aec1c23a467bdd0cf` |
