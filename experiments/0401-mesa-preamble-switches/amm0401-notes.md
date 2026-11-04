# Exp 0401 series e4: AnyPS5's AMM PRT commands, the other AMM commands, the AMPR waits — notes, 2026-11-04

The maintainer's rule: a port is judged for any title, not only ours. Exp 0402's survey (§2, the Ampr row) lists what
our host does not register: the AMM PRT commands, `MultiMap`/`Remap`/`ModifyProtect` and their measure functions, and
`WaitOnAddress`/`WaitOnCounter`. None of them is on the second title's stub list (`prtvo0401-notes.md`, item 7), so this
is for other titles. The work was done on the laptop only: no box access, no git, no existing file edited.

Deliverables (all in this directory):

| File | md5 | What |
|---|---|---|
| `mkamm0401.py` | 74a901192f0d9270ddab0f8a54de4dbb | `mkamm0401.py <tree root> <out dir> [--memory <memory.cpp>]` writes `src/libs/libAmpr.cpp` |
| `amm0401.cpp` | 74d469cbc879647000e1511f178f307d | the CPU tests (the number of checks run depends on the switches) |
| this file | | |

## Inputs and output

| Unit | md5 |
|---|---|
| `src/libs/libAmpr.cpp` of the e4 tree (KytyPlus f266548 + patch 0001), in | a0e2ff6e6fcbcae83847107243b35319 |
| `src/libs/libAmpr.cpp`, out | **0a1762f6440f421586b56767d27d0770** |
| `src/kernel/memory.cpp`, the private next-build copy (`memout`) | 43713ef677ec887a8ca273f7ab5cee90, **not changed** |

memory.cpp needs no edit: the PRT zero pages are built from public functions (`KernelReserveVirtualRange` with
`MAP_FIXED`, `KernelSetVirtualRangeName`) and one `mprotect` of the reserved placeholder (below). `--memory` is accepted
for the series' calling convention, read, and left alone; the script says so on stderr.

The output: 14 hunks, +1137 / −9 lines. Of the 9 removed lines:

- 7 are parameter-list lines that gain names (WriteCounter_04_00 and the four WriteAddressFromCounter forms; the old
  ones were unnamed).
- 1 is `if (command.kind == AmmCommandKind::Unmap)`, which becomes `else if` behind the new branch.
- 1 is the `3wn42MWTzTs` registration, which moves into an `else`.

`ExecuteAmmMapCommand` keeps its head; its old body continues unchanged as `ExecuteAmmMapCommandToday`.

## What was ported, from where

AnyPS5 (github.com/boykopovar/AnyPS5, GPL-2.0-only) at `4f41f4c375f5abb487dbd184fbc150f31994d762`. Its file is
`core/libs/prx/libkernel/Apr/src/Apr.cpp` unless another file is named. The PRT commits are `e3b5192cb`, `79fc99774` and
`37881a5da` (the read-only zero pages). The comment block in the unit names the same lines, and says GPL-2.0-only.

| Switch | NIDs registered only with it on (26 in all) | AnyPS5 source |
|---|---|---|
| `KYTY_BC5_AMM_PRT_CMDS` | `ZJCgt+aPHAU` MapAsPrt, `d3lKWPM6odc` AllocatePaForPrt, `0Xo9g4goDXU` RemapIntoPrt, `3A2X6OCHtnA` UnmapToPrt, `4SSJ+cn+Pvg` / `2yYv9QWB3hU` their two measures | executor `Apr.cpp:407-478` (`_clearPrt`, `_requirePrt`, `_zeroPrt`, `_ammUnmap`, `_ammMapAsPrt`, `_ammUnmapToPrt`, `_ammAllocatePrt`), `_ammMap` 480-505, `_ammRemap` 507-526; `DirectMemory.cpp:1284-1293` (`DoMapZero`); recorders `libSceAmpr/Export.cpp:868-906` |
| `KYTY_BC5_AMM_EXTRA_CMDS` | Remap, MultiMap, ModifyProtect, ModifyMtypeProtect, each with its `WithGpuMaskId` form, and their 8 measures (16) | `_ammRemap` 507-526, `_ammProtect` 528-546; `Export.cpp:795-866` |
| `KYTY_BC5_AMPR_WAITS` | `V7GQTEeUfhw` sceAmprCommandBufferWaitOnAddress, `FrCNL9TQ8ms` …WaitOnCounter, `jIlc4p5dSD0` / `6jLL5BIZ88U` their measures | counters and `_waitSatisfied` `Apr.cpp:196-267`, the waits in `_execute` 649-662; `Export.cpp:148-166, 306-346, 382-383, 587-618` |

The registered `_04_00` forms differ from the four new NIDs. `DLfoNxTFNVk` is `sceAmprCommandBufferWaitOnAddress_04_00`
and `cQb8Zr8Q0Y0` is `…WaitOnCounter_04_00`; both are registered today. The survey's "missing" waits are the
unversioned names.

With `KYTY_BC5_AMPR_WAITS` on, some functions registered today also change, because waits on counters need counters.
Today all of these record a no-op or write 0:

- `jK+yuYCI7MA` `WriteCounter_04_00` and `cQb8Zr8Q0Y0` `WaitOnCounter_04_00` record a real counter write or wait.
- `t4ExS+SwLjs`, `gSF5OsXdfIg`, `enZm-6GjWqw` and `ZLWtNUP6R5E`, the four `WriteAddressFromCounter` forms, write the
  counter's value.
- `3wn42MWTzTs` `WriteCounterOnCompletion` is registered as a new function. Today's has a different signature
  (`(cb, u8, u8, u64, u8)`, all ignored); the new one has AnyPS5's `(buffer, counter, value)`.

Every NID was checked against its name with exp 0327's calculator (`nid0401.py`'s, self-checked on `strcmp`). The script
checks them each run, as it does the 47 `{"NID", "name"}` pairs in `amm0401.cpp`.

**Semantics as ported:**

- **MapAsPrt** forgets the range's pages (their pool pages go back), makes them zero pages and marks the range PRT.
  - Zero pages here: the range goes back to the host's reservation (`KernelReserveVirtualRange` FIXED, named "AMM").
    Its anonymous `PROT_NONE` placeholder is then made `PROT_READ`.
  - A CPU read sees the kernel's zero page. A CPU write faults: it is never writable, the property `37881a5da` gives
    AnyPS5 on Windows.
  - The GPU side sees no mapping there, so `BC5_DIRECT_AMM_PRT`'s PRT pages answer the GPU: reads 0, writes dropped.
- **UnmapToPrt** turns a PRT range back to zero pages and returns its pool pages.
- **AllocatePaForPrt**:
  - Each run of backed pages takes the new type and protection.
  - Each run of unbacked pages gets pool pages.
  - A run whose backing fails gives them back and returns to zero pages (`79fc99774`). Runs backed earlier in the same
    command stay backed, exactly as in AnyPS5.
- **RemapIntoPrt** moves a fully mapped source into a PRT range. Its opcode argument is recorded (1011 when 0) and not
  used.
- **Remap** moves a fully mapped range's pages and returns the source to the reservation.
- **MultiMap** maps them a second time. A pool page goes back to the pool only with its last mapping (AnyPS5's
  `pooledUses`).
- **ModifyProtect / ModifyMtypeProtect** set the masked bits of every page of a fully mapped range, and the type too for
  the Mtype form. The `GpuMaskId` forms ignore the id, as AnyPS5 does.
- A plain map or unmap over a PRT range ends it. A PRT command outside a PRT range fails. So does a remap of a range that
  is not fully mapped, or an alias or PRT remap that overlaps its source.
- **Counters:** 256 × 32 bits, with AnyPS5's accesses: 64 bits over two counters, 32, 16 or 8 at an offset. Its write
  operations are store, or, and-not, xor and add. Its compare codes are 0-6, with mask and shift.
  - A wait not met stops the buffer, as `WaitOnAddress` does today: the buffer is parked and the priority's worker polls
    it.

## What was adapted

- **Commands are kept host-side.** This host does not decode command bytes: it records each command into a host-side
  list beside the zeroed record bytes. So:
  - the new AMM kinds join `AmmCommandKind` / `AmmMapCommand` (plus `source` and `mask` fields);
  - the counter commands get a `bc5_counter_commands` list and `CommandKind::Bc5Counter`.
- **Record sizes are this host's.**
  - 0x20 for MapAsPrt / UnmapToPrt, as Unmap's.
  - 0x30 for the remaps and the protection changes.
  - 0x20 for the waits and counter records, as today's `_04_00` ones.
  - Each measure returns what its recorder consumes. AnyPS5's sizes are its own layout, not the console's.
  - TODO(verify): the console's record sizes.
- **The page table.** With PRT or EXTRA on, every AMM map, unmap and new command goes through one lock and a page table:
  16 KiB page → dmem, type, protection, owner. This is AnyPS5's `AmmState`.
  - Pages from today's automatic pool stay owned by `g_amm_auto_maps` (F206's allocator).
  - A remap or multimap turns them into counted pages.
  - The title's own direct memory (MapDirect) is never returned to the pool.
- **Pool pages come from today's first-fit pool,** which borrows direct memory when it has no free run. AnyPS5 maps
  scattered pool pages and never borrows. So a PRT backing fails only when neither the pool nor the direct memory has a
  run.
- **Host protection follows today's rule** (`ExecuteAmmMapCommand`, exp 0035): a protection without CPU bits still maps
  CPU read/write on the host. BC5's `sysLinuxVirtual.cpp` keeps readable pages writable anyway.
- **An unmap still leaves a hole,** as today's does, not a reservation as AnyPS5's. The remap source and the PRT ranges
  do return to the reservation, as in AnyPS5.
- **The unversioned WaitOnAddress refuses a null address.** AnyPS5's alignment check lets one through, and the wait
  would then read address 0.

## Not ported, and why

These are libkernel's `sceKernelWriteMapCommand2` (`5b3ZqlxJ+WE`; with `prt ≠ 0` it is AnyPS5's MapAsPrt writer),
`sceKernelWriteUnmapToPrtCommand` (`vnKYv2NuO5U`) and `sceKernelWriteRemapIntoPrtCommand` (`RPAHEYSOt1s`). They are at
AnyPS5 `libkernel_sys/Export.Discovery.cpp:1848-1853, 1915-1918` and `Apr.cpp:942-948`.

- **They write packed command bytes into the caller's memory.** AnyPS5 runs such bytes with its byte-decoding executor
  `_execute`. A caller submits them through libkernel's `sceKernelCallIndirectBuffer` family
  (`Export.Discovery.cpp:62-67`), or through `sceAmprAmmSubmitCommandBuffer3` as its test does
  (`core/libs/tests/GuestKernelSys.cpp:700-705`).
- **Our host has no part of that path.**
  - It records commands host-side and never decodes bytes.
  - It registers no `sceKernelWrite*Command` at all: the NIDs of `sceKernelWriteMapCommand` / `…Unmap…` / `…Map…2`
    are in no file of the tree.
  - It registers no `sceKernelCallIndirectBuffer*` (`ahy8NSXrSbs`, `MCdZ06CSUOc`, `x+JkNr3eoxs`: none in the tree).
- **Three writers alone would be dead code.** They would report success for bytes nothing in the host can run.
- **The task's `sceKernelWriteMapAsPrtCommand` does not exist in AnyPS5.** Its NID `b2kyWqWFno0` (prtvo0401-notes'
  table) is hashed from a guessed name; AnyPS5's MapAsPrt writer is `sceKernelWriteMapCommand2` with `prt ≠ 0`.
- **Porting them properly** means the whole libkernel AMM writer family, its indirect-buffer submit and a byte decoder
  in our executor. That is a separate decision.

## Off is today's path

With every switch off (or unset):

- the 26 NIDs are not registered;
- `3wn42MWTzTs` registers today's function;
- every changed function reaches today's code.

Each change to existing code is one of these:

- (a) an early `if (Bc5…On()) { return …; }` before today's body:
  - WaitOnCounter_04_00;
  - WriteCounter_04_00;
  - the four WriteAddressFromCounter forms;
  - `ExecuteAmmMapCommand`, whose old body is now `ExecuteAmmMapCommandToday`, unchanged.
- (b) a branch in `RunOrderedAprCommands`' AMM case for kinds that are never recorded off (`kind > Unmap`), or for an
  unmap while the page table runs. Today's `else if (Unmap)` / `else` chain follows unchanged.
- (c) a new `case CommandKind::Bc5Counter` and an ordering loop over `bc5_counter_commands`, which are empty when off;
- (d) declarations: the enum values, two struct fields, the struct, the switches, the new functions;
- (e) the registration blocks.

The only other effect off is three stderr lines at the library's registration, one per switch:
`[bc5] exp 0401: KYTY_BC5_AMM_PRT_CMDS off` (and EXTRA, WAITS).

## The journal (stderr, PRT path and failures)

- `[bc5] exp 0401 prt: zero pages #n va … size … (MapAsPrt|UnmapToPrt|AllocatePaForPrt, rolled back|RemapIntoPrt, map failed) -> 0x…`
- `[bc5] exp 0401 prt: backing #n (AllocatePaForPrt|RemapIntoPrt|…, failed|…, no direct memory) va … size … dmem … type … prot … -> 0x…`
- `[bc5] exp 0401 amm: <kind> va … source … size … prot … -> 0x…, the buffer stops here (#n)`: any failure of a new
  command, or of an unmap while the page table runs.

Each line is sampled: the first 32, then every 256th. A zero-page or backing failure is always written.

## The CPU tests (`amm0401.cpp`)

**Build:** the compile command of **`src/libs/libAmpr.cpp`**, with `amm0401.cpp` as the source. Link it with every
emulator object except `main.cpp.o`, with the private `libAmpr.cpp.o` among them. With `build0401.py` that is
`src/libs/libAmpr.cpp=<x-amm>/src/libs/libAmpr.cpp --gate amm0401.cpp <out> --like src/libs/libAmpr.cpp`.

**Setup.** It starts the Common, Threads, Config (printf silent), Log and Memory subsystems, as KytyPlus's
`tests/VirtualMemoryAllocationTests.cpp` and `emulator.cpp` do. It then runs `Libs::InitAll` and takes every function by
NID from the SymbolDatabase (lesson R32). It reserves the AMM window, gives the AMM pool 64 pages and allocates 4 pages
of direct memory for MapDirect. It reads three test seams in the unit: `bc5_exp0401_amm_stats`, `bc5_exp0401_amm_page`
and `bc5_exp0401_amm_fail_backing`. They are always compiled in, and nothing in the emulator calls them.

**Switch handling.** Each switch is read from the environment; its cases run on or off.

- The last line is `amm0401: on N of N; end` (all three on), `amm0401: off N of N; end` (all off), or
  `amm0401: mixed prt=… extra=… waits=… N of N; end`.
- An argument `on` or `off` must match the switches, or the program exits 2.
- A watchdog thread ends a hang after 120 s with `amm0401: FAIL watchdog: case "…"`.

| Setting | Cases |
|---|---|
| PRT on | 6 NIDs registered as their functions (debug names); measures valid/invalid; recorder checks leave the buffer empty; buffer offset = measure; **MapAsPrt** over a backed page reads 0 at three offsets and returns the page to the pool; **AllocatePaForPrt** backs 2 pages (pool −2), then over the whole 4-page range backs **only the 2 unbacked pages** (pool −2, old data kept, type/prot set on all); **UnmapToPrt** reads 0, pool +2; **RemapIntoPrt** moves a page in (value kept, source gone, pool unchanged); refused: RemapIntoPrt/UnmapToPrt outside PRT, a PRT remap onto its source; **forced failure 1**: AllocatePaForPrt of more than all the direct memory (2 GiB over it, at most 28 GiB) → EAGAIN, pool/pages/PRT unchanged, still 0; **forced failure 2**: the seam fails the second backing run → EAGAIN, the first run stays backed (pool −1 page only), the failed run reads 0 and is PRT-unbacked; a map ends PRT on its page, AllocatePaForPrt there is then refused; an unmap of an unbacked PRT page ends it |
| PRT off | the 6 NIDs unregistered |
| EXTRA on | 16 NIDs registered; 8 measures valid/invalid; recorder checks; **Remap** moves two pool pages (values kept, source gone, pool unchanged); **MultiMap** of them into the multimap half and **MultiMapWithGpuMaskId** of a MapDirect page (a write through the alias shows at the original); **unmap of the original keeps the pages, unmap of the alias returns them** (pool back to its start); **RemapWithGpuMaskId** plus a map at the source in one buffer; **ModifyProtect** (0x03 → 0x01), **ModifyMtypeProtect** (→ 0x23, type 3), the GpuMaskId forms (0xC0 → 0x40; 0x03 → 0x10, type 1), the host still reads; refused: an unmapped source, an alias onto its source, a protection change of unmapped pages |
| EXTRA off | the 16 NIDs unregistered |
| PRT and EXTRA off | today's map and unmap: data, pool −2 / +2, and no page table (0 pages) |
| WAITS on | 4 NIDs; `3wn42MWTzTs` is `Ampr::Bc5WriteCounterOnCompletion`; measures 0x20 = the offset advance; checks (unaligned, compare 4, null, counter 128, access 8, operation 5, odd pair counter); **WaitOnAddress against a writer thread** (still waiting after 100 ms, done within 5 s of the write, WaitCommandBuffer 0); **WaitOnCounter** at priority 3 released by a `WriteCounterOnCompletion` at priority 4; **WaitOnCounter_04_00** on byte 0, masked to the low nibble, "greater than 5": 0x34 does not release it (100 ms), an add of 2 does; **WriteCounter_04_00** store, add, or into a byte, a 64-bit store, then WriteAddressFromCounter (0x15) and Pair (0xFF00000015, 0x1122334455667788) |
| WAITS off | 4 NIDs unregistered; `3wn42MWTzTs` is today's function; today's WaitOnAddress_04_00 against a writer thread; WaitOnCounter_04_00 records a no-op (the buffer finishes at once); WriteAddressFromCounter writes 0 |

**For the box script (the top session's call).**

- An `E4_EDITS` row: `amm mkamm0401.py src/libs/libAmpr.cpp:a0e2ff6e6fcbcae83847107243b35319:0a1762f6440f421586b56767d27d0770`.
- The `E4_GATES` loop sets one variable, so it would run this test "mixed" and fail the argument check. For `amm0401` it
  needs all three set together:
  - on: `env KYTY_BC5_AMM_PRT_CMDS=1 KYTY_BC5_AMM_EXTRA_CMDS=1 KYTY_BC5_AMPR_WAITS=1 … amm0401 on`;
  - off: `=0` ×3 with `off`;
  - unset: `env -u` ×3 with `off`.
- Strings the binary must hold: `KYTY_BC5_AMM_PRT_CMDS`, `KYTY_BC5_AMM_EXTRA_CMDS`, `KYTY_BC5_AMPR_WAITS`,
  `exp 0401 prt: zero pages`.

## Laptop verification

- **The script.**
  - It ran into `…/scratchpad/amm0401/out1` and `out2`: the same md5 twice, with and without `--memory`.
  - On its own output it refuses ("has the edit already").
  - The tree's file is unchanged (md5 still a0e2ff6e…).
  - Every anchor is asserted exactly once. The 26 + 7 NIDs and the 47 pairs in `amm0401.cpp` hash from their names.
- **Diff and balance.**
  - The hunks are classified as in "Off is today's path"; the 9 removed lines are accounted for above.
  - Braces, parentheses and brackets balance in the unit and in the test, outside comments and strings.
- **Syntax.** Both parsed with the laptop's clang, `-fsyntax-only -std=c++20 -Wall -Wextra -Wshadow`, using stubs:
  `cmake_config.h` (Linux), `pthread.h`, `sys/mman.h`, `clock_gettime`, MSVC's STL and GPCS4's fmt.
  - The edited unit has the same 5 warnings as the tree's (3 × `ra_data` initializer, 2 × format-extra-args) and
    nothing new. The `mprotect` path was checked with `__linux__` defined.
  - The test parses with no warnings.
  - The box's real compile (clang, glibc, `-fno-exceptions -fno-rtti`) and the runs are **not done**.

## Doubts

- **Nothing is measured on a console.** AnyPS5's notes say these semantics are "inferred from the names, not confirmed
  on a title", and so are ours.
  - Reads 0 / GPU writes dropped (ours) against GPU writes fault (theirs) is still open (F161, F257).
- **A CPU write to an unbacked PRT page faults.** The fault handler then ends the emulator with "AMM virtual-memory
  unmap is unsupported" (the range is named "AMM"). The same holds for an APR file read into one. AnyPS5 faults or
  throws there too; a console probably faults.
- **The GPU side.** `bc5LleAgc.cpp`'s `scratch_fill` can still map its shared scratch buffer over holes of a learned
  window inside the AMM window (prtvo0401-notes, item 7). A PRT range under such a window then reads the scratch buffer
  on the GPU, not 0. That is not changed here (bc5LleAgc.cpp was not to be edited).
- **Cost.** With PRT or EXTRA on, every AMM map of the title enters the page table: one map node per 16 KiB page, about
  60 MB for 12 GiB mapped. Every map and unmap also takes one more lock. Measure before using either switch with the
  second title.
- **AllocatePaForPrt is not all-or-nothing.** Runs backed before a failing run stay backed, as in AnyPS5; the console's
  rollback is unknown.
- **Counter access without a recorded check.** The `_04_00` wait does not check its counter index (AnyPS5 does not
  either; indices wrap at 256).
- **WriteAddressFromTimeCounter still writes 0.** It is out of these switches' scope.
- **Library of the libkernel writers.** If they are ported later, AnyPS5 puts two of the three in `libkernel_sys`; which
  library name the console's import uses was not checked.
