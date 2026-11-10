# Exp 0401 series e, switch 3: direct and flexible memory from param.json (notes, 2026-11-03)

Written for the series e build. It follows KytyPS5 `09753bf` "memory: change defaults" (GPL-2.0, as KytyPlus); the
source is in the clone at `refs/KytyPS5_KytyPS5`. No compiler ran on the laptop, so the box compile is the first one.

## The switch

`KYTY_BC5_MEMORY_FROM_PARAM` is on when it is set, not empty and not `"0"` (F767's reading).

**On.** A game gets 12.5 GiB, which is 12,800 MiB.
- A fixed 64 MiB cache comes off the top.
- So does the page-table memory beyond the 64 MiB included for each table, as in `09753bf`:
  - CPU table: `kernel.cpuPageTableSize`, in bytes;
  - GPU table: `kernel.gpuPageTableSize`, in bytes;
  - AMM table: `amm.pagetableMemorySizeInMib`, in MiB.
- The overhead is max(cpu, 64) + max(gpu, 64) + max(amm, 64) − 3 × 64 MiB.
- The total is rounded down to the 16 KiB guest page, as today. `KYTY_GUEST_MEMORY_MB` and the host-RAM cap are ignored.
- Flexible memory stays param.json's `kernel.flexibleMemorySize`, through today's `SetFlexibleMemorySize` call in `emulator.cpp`. If param.json sets none, today's 1 GiB default stays.
- Direct memory is the total minus flexible.
- `EXIT_IF` checks when flexible plus the overhead does not fit, as `09753bf` does:
  - the overhead against the budget minus the cache, in `Bc5MemoryFromParamTotal`;
  - flexible against the total, in `SetFlexibleMemorySize`, `PhysicalMemory::Size()` and the new init block.

**Off.** Today's code path and sizes. Off changes only two things:
- one journal line at memory init;
- three more param.json keys, read and kept but never used.

**Left out on purpose:**
- `0a14091`'s charge of loaded modules' segments to flexible memory. The title sets its own flexible size, and the charge would also change `runtimeLinker.cpp`.
- `09753bf`'s `KernelGetPageTableStats` totals.

## Files, from the box tree (main 029e0d6b = KytyPlus f266548 + patch 0001)

| File | In (md5) | Out (md5) |
|---|---|---|
| `src/kernel/memory.cpp` | f61546925dcf96ee9bbc1278b0f8ae6c | 43713ef677ec887a8ca273f7ab5cee90 |
| `src/loader/systemContent.cpp` | 7121c22ca8b893ac37fbeabde48b4a6b | 4e33b30a4acf89481942cec435b76c37 |
| `src/loader/systemContent.h` | 8890c158627f20f59ee55205e73d36c3 | 2b2b21eb1faf35c2a538917049aea85e |
| `src/emulator.cpp` (read only) | 942ef7bb3abbe93684e16c915aaa4a83 | unchanged |

`mkmem0401.py <tree root> <out dir>` writes the three files and prints their md5s. A second run on its own output stops with "has the edit already".

## What changed

- **`systemContent.h`** gains `struct SystemContentMemoryTables` and the declaration `SystemContentGetMemoryTables()`, placed after the existing `SystemContentGetFlexibleMemorySize()` declaration. No existing declaration changed, so units that include the header and are not rebuilt stay valid.
- **`systemContent.cpp`:**
  - `Psf` gains a member and a getter. The class is local to this unit.
  - `OpenJson` reads the three keys after the existing `flexibleMemorySize` read. It takes non-negative integers only (`is_number_unsigned`); anything else stays 0.
  - `Close` clears them, and the free function returns them.
- **`memory.cpp`:**
  - It now includes `loader/systemContent.h`, which it did not before.
  - Three constants, `g_bc5_today_total` and three helpers sit after the globals.
  - In `PhysicalMemory::TotalSize()`'s cached lambda, today's total is computed as before and kept for the journal. With the switch on, the parameter total replaces it, before today's `LOGF`.
  - `KYTY_SUBSYSTEM_INIT(Memory)` prints one stderr line, the same style as the unit's other `[bc5]` lines:
    `[bc5] exp 0401: memory from param.json on|off: total N MiB, flexible F MiB, direct D MiB (param.json: flexible …, cpu table …, gpu table …, amm table … MiB)`.
    With the switch on it adds `; today's total would be T MiB`.
- Braces and parentheses balance in all three outputs.

## Call order: when `TotalSize()` is first called

`TotalSize()` caches its value on the first call, so the parameters must be loaded by then. They are.

- `PhysicalMemory` is local to `memory.cpp`. Its `TotalSize()` callers are `Size()`, `SetFlexibleMemorySize` and the memory subsystem's init. The `Size()` callers are the `PhysicalMemory` and `FlexibleMemory` constructors (at init) and guest calls made after init. No static initialiser calls either.
- `emulator.cpp` `Init()` runs the config and log subsystems, then `SystemContentLoadParamSfo(param_json)`. It then calls `SetFlexibleMemorySize`, whose `EXIT_IF` makes the first `TotalSize()` call. Only after that does it add and init the memory subsystem.
- If param.json sets no flexible size, the first call is the init block. param.json is loaded by then too.
- In both cases the parameters are already read when the total is cached.

## Expected sizes for the title

- Today: `KYTY_GUEST_MEMORY_MB=13824` from `bc5-run.env`, flexible 276 MiB (F194). Total 13,824 MiB, direct 13,548 MiB.
- On, if param.json sets no table sizes: total 12,800 − 64 = 12,736 MiB, flexible 276 MiB, direct 12,460 MiB. That is 1,088 MiB less direct memory than today.
- The table values print in the journal line. Any value above 64 MiB lowers the total further.

## Building it

Both new objects must be compiled with the edited header first on the include path: `-I<out dir>/src` before the tree's include. Both units include it as `"loader/systemContent.h"`, which does not resolve beside the including file, so the `-I` order decides. Both objects, `memory.cpp.o` and `systemContent.cpp.o`, must be swapped into the link. Nothing else needs a rebuild.

## Doubts

- It is not known whether the title sizes its heaps from `sceKernelGetDirectMemorySize`. If it allocates close to today's 13,548 MiB, 12,460 MiB may fail an allocation. AnyPS5 reverted its 12 GiB (`97f1d41a2`) after ASTRO BOT ran out at 12,228 of 12,288 MB. A failed direct allocation should show in the log, not as a hang.
- Less direct memory lowers pinned GTT only if the pinned heaps scale with it. The eager import pins the named heaps, so this needs a play to show.
- The title's param.json table keys were not read: the package is not mounted now. The journal line will show them.
