# BC5 exp 0401 series e10 — the contract between the code tags (read this first)

The spec is exp 0408 §G6 and §G7 at commit 509083aa (worktree C:\Users\kjani\Downloads\bc5\bc5-0408,
`experiments/0408-memory-review/README.md` lines 395-456). e10 builds items 2, 4, 5, 6, 9, 10, 12 now (plus arm profiles
for 7 and 8, done by the session itself). Items 3, 8-step-1 and 11 are NOT built. Every change is behind its own switch,
default off (bc5::env_on's reading: unset, empty or "0" is off, any other value on; read once; one journal/log line naming
the mode at first use), and with every switch off the behaviour is exactly e9's.

## Base files (e9's final versions; edit copies, never these)
Base tree: C:\Users\kjani\AppData\Local\Temp\claude\7e70d624f1bff3f5\19eb012d-ed8a-4416-af2a-d3b1f4ce12f0\scratchpad\e10\base\
| file | md5 (pin it) | tag that edits it |
|---|---|---|
| src/libs/bc5LleAgc.cpp | 4761c532868ce1cd5e8dc097050990bb | m10 (unit) |
| src/kernel/memory.cpp | ee24c888f976cc125502cf3a31006349 | k10 (memory.cpp) |
| src/libs/libAmpr.cpp | 0a1762f6440f421586b56767d27d0770 | p10 (param.json + AMM) |
| src/loader/systemContent.cpp | 4e33b30a4acf89481942cec435b76c37 | p10 |
| src/loader/systemContent.h | 2b2b21eb1faf35c2a538917049aea85e | p10 |
| src/graphics/presentation/videoOut.cpp | 3fa490f762fb6a9612289ef3a4018150 | p10 |
| src/libs/libAppContent.cpp | 7f9d1446918cf682ff77eb0808fe394c (unedited box tree) | p10 |
| src/loader/runtimeLinker.cpp | aba94c24ad35a1c944ad3bd5843b13ef | k10 (only if the module charge needs it) |
| src/libs/libKernel.cpp | 0a0d46657d8088b72a9ba67e2fbcc310 | k10 (only if needed) |
| backend (main 029e0d6b) src/direct.cpp, include/bc5/direct.hpp, ... | backend0405.md5 pins | nbo (backend) |
The rest of the box tree as of series e4 is in ...\scratchpad\e4\full\ (read only; files edited later are in base\).
Main's patch 0001 (C:\Users\kjani\Downloads\bc5\bc5\backend\kytyplus-patches\0001-bc5-lle-agc.patch) is what 0408's "P:<line>"
citations point at; "D:<line>" is main's backend/src/direct.cpp.

## Cross-unit functions (C linkage, exact signatures; each defined once, by the tag named)

1. The protection census sink — defined in bc5LleAgc.cpp (m10); called by memory.cpp (k10) and libAmpr.cpp (p10):
   `extern "C" void Bc5ProtCensus(int call, uint64_t va, uint64_t size, uint64_t phys, int prot, int type, const char* name);`
   - call: 1 map (any call that creates a guest mapping: direct, flexible, pooled, named, ...), 2 mprotect, 3 mtypeprotect,
     4 AMM map (libAmpr's map commands), 5 AMM remap/protect, 6 unmap / AMM unmap.
   - type: as Bc5ForEachMappedRange (0 direct, 1 flexible, 2 pooled, 3 stack, 4 code, 5 runtime), -1 unknown.
   - phys: the direct-memory offset when there is one, else 0. prot: exactly as the title passed it, before any widening
     (KYTY_BC5_ALL_RW, GPU bits folded into the CPU mode). name: may be null.
   - The callers call it unconditionally at those points (one call, no work of their own); the sink returns at once when
     BC5_DIRECT_PROT_CENSUS is off. It never blocks, never takes a memory.cpp lock or the direct mapper's lock, never calls
     back into memory.cpp, and may be called with memory.cpp's or libAmpr's locks held, from any thread.
   - Never driven from direct_breakdown_one (its SEEK_DATA walk held the game thread 25-80 s, exp 0288).

2. The AMM window and reservations — defined in libAmpr.cpp (p10); consumed by bc5LleAgc.cpp (m10):
   `extern "C" int Bc5AmmWindow(uint64_t* va, uint64_t* size);` the AMM window as actually reserved (AmmWindowStart's
   result and AMM_VA_SIZE; today the unit maps its PRT window at a hard-coded 0x8000000000 regardless, P:38565-38571,
   39980-40032: a bug). Returns 0 and leaves the outputs alone when the window is not reserved yet.
   `extern "C" void Bc5AmmForEachReserved(void (*cb)(uint64_t va, uint64_t size, void* ctx), void* ctx);` every range the
   title holds reserved inside the AMM window now (what "the title's AMM reservation" means in this code: p10 finds it and
   documents it).
   `extern "C" void Bc5AmmReserved(uint64_t va, uint64_t size, int on);` — defined in bc5LleAgc.cpp (m10), called by
   libAmpr.cpp (p10) when such a reservation is made (on=1) or given back (on=0), outside libAmpr's own locks if possible.

3. Backend (nbo), additions beside map_null_window (keep Device's layout; add methods only, never change an existing
   signature — other shared units may call the old ones):
   `bool map_shared_rights(std::uint32_t id, std::uint64_t bo_offset, std::uint64_t size, std::uint64_t gpu_va, unsigned rights);`
     rights: 1 READABLE, 2 WRITEABLE, 4 EXECUTABLE (AMDGPU_VM_PAGE_*); map_shared stays R|W|X. Aliases (map_alias) of a
     mapping made this way keep its rights.
   `bool map_null_range(std::uint64_t va, std::uint64_t size, bool writable);` / `bool unmap_null_range(std::uint64_t va);`
     null pieces of the same zero BO at a range outside any window (the learned-window holes), tracked in their own list;
     unmap_null_range takes back exactly what map_null_range at that va put in.

## Item 4's GPU rights, as built (unit switch BC5_DIRECT_GPU_RIGHTS, m10)
Only GPU_WRITE is taken away: a view whose title protection has GPU_READ (0x10) and not GPU_WRITE (0x20) is mapped R|X;
every other view keeps today's R|W|X (including views with no GPU bit, which the name lists import today: item 3, not
built, decides those). X stays everywhere: whether the GPU fetches shader code from the title's heaps is not known here,
TODO(verify).

## Item 5, as built (m10 + p10 + nbo)
- BC5_DIRECT_AMM_WINDOW_FIX (m10): with BC5_DIRECT_AMM_PRT set, the PRT window goes where Bc5AmmWindow says, not at
  0x8000000000 (a bug fix on its own; also covers the device re-open site).
- BC5_DIRECT_AMM_NULL_BO=1|rw (m10): with BC5_DIRECT_AMM_PRT set, null pages (map_null_window) only under the title's
  reservations inside the AMM window (Bc5AmmForEachReserved at device open, Bc5AmmReserved later), never the whole 64 GiB
  (~128 MiB of 4 KiB PTEs if the BO's pages are not contiguous, 0408 G6 row 5); the rest of the window stays PRT as today.
- BC5_DIRECT_HOLES_NULL_BO=1|rw (m10): the learned-window holes get map_null_range instead of the writable scratch BO.
- When NULL_BO or the census is on, the unit journals the GPU's VRAM and GTT use (sysfs mem_info_vram_used,
  mem_info_gtt_used of the render node) before and after the window maps: the page-table cost, measured.
