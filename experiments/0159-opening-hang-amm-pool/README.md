# 0159 — The opening's crash/hang a few minutes in: the AMM automatic pool was never recycled, so a map failed silently and the title's streaming reads hit unmapped pages

**Question.** F201: the second title's opening takes the machine down about 90 s after New
Game (the maintainer: picture and sound drift apart, the graphics slow down, speed up for a
moment, then the hang; the kernel journal ends with `amdgpu: Dumping IP State`). What happens
before the reset, and is it the host's?

**Setup.**
- BC-250 dev box, 2026-10-18 11:00–12:00, runs 634–638. The opening started by script (start
  screen ✕ → empty slot 1 ✕ → challenge ✕ → New Game ✕, at +121 s) and left running; no kill
  rule this time (the maintainer's decision), with the kernel log (`sudo dmesg -w`), the host log
  and the direct path's journal (`BC5_DIRECT_JOURNAL=min BC5_DIRECT_JOURNAL_SYNC=1`) streamed
  to the laptop over SSH so the last lines survive a hang; the root hang watcher of F113
  (`bc5-gpu-hang-watch`) armed.
- `KYTY_BC5_AMM_TRACE=1` (every map, unmap, read and submission) and gdb with a breakpoint on
  the host's reserved-range fault hook (`KernelHandleReservedRangeAccessViolation`), which
  prints the faulting thread's backtrace before the host exits.

**Result.**
- **Not a GPU hang first.** Run 634 (journal on) ended at +2:20 of the opening with the host's
  own exit "AMM virtual-memory unmap is unsupported: addr=0x807b0b0000" (`memory.cpp:3638`);
  the machine survived. Before it, the direct journal showed 12.4 GiB pinned, 7-second frames
  and a 1.4-s learned-window rebuild — the maintainer's slow-down.
- **Who faults** (runs 635–636, gdb): the host's APR read worker, `memcpy` in
  `ReadHostFileToGuest` copying `tex_road` / `tex_environment` into a texture's AMM address
  (0x804af10000, 0x8107290000 …) that the title had mapped *just past* an earlier mapping — in
  the AMM trace no map ever covered the page. The same with the synchronous APR path
  (`KYTY_BC5_APR_SYNC=1`, run 636): not the ordering of exp 0156.
- **Why the page was never mapped:** the title submits its texture maps in map-only buffers
  (`submit …: 0 reads, 43 maps`); only the first map of such a buffer ran. A map "auto" takes
  its direct memory from `AllocateAmmAutoDirectMemory`, a bump pointer over the 3 GiB the title
  gave (`AmmGiveDirectMemory … usage 1`) and then over the host's direct memory — nothing was
  ever returned on unmap (13,973 maps against 3,575 unmaps in six minutes). When both were
  gone the map returned `EAGAIN` without a trace line, the buffer's remaining 42 maps were
  dropped (`result != OK` ends the buffer), and the reads that followed copied into reserved
  pages. The memory growth is also the 12 GiB pinned and the stalls before the hang; on the
  maintainer's runs the end was a GPU reset instead of the host's exit, presumably the same
  exhaustion reached through the GPU side.
- **Fix** (`libAmpr.cpp`): the automatic pool is an allocator — a coalescing free list of the
  pool's direct memory, first-fit allocation, and a map of what each automatic mapping holds,
  so an unmap (or a map replacing part of an old one) returns its pages; a range borrowed from
  the direct memory when the pool is full joins the free list after its unmap; a refused map
  and a failed buffer now say so in the AMM trace. Run 637: ten minutes, 13,779 maps / 3,741
  unmaps, no fault, no exhaustion, load 2–4 instead of 8–19.
- **The opening then slows to a crawl about 20 s in** (journal t ≈ 140 s): one 12.6–13.9k-dword
  graphics buffer of the night scene faults the GPU (kernel: `[gfxhub] page fault … in page
  starting at address 0x8000 / 0x11000 / … / 0x2e000`, the host's status 0x00600631), the
  host's 2-s fence timeout and the 12-s reopen follow, and every later frame of that kind
  repeats it (runs 638–639: the cinematic clock at a quarter speed, screenshots alternating
  between two stale frames). On the maintainer's runs the kernel's reset took the machine down
  instead. The buffer (`BC5_DIRECT_IB_DUMP`, `bc5-agc`) differs from its neighbours by 21
  `DISPATCH_DIRECT` + 5 `DISPATCH_INDIRECT`; dropping those dispatches (run 647) removes the
  fault for the whole run, dropping the multi-draws or the 0157 prefix does not (645, 646, 642).
  The device coredump names the work distributor (`WD_UTCL1_STATUS` 0x101) and a GDS VM
  protection fault; two of the 22 programs do `ds_append … gds`, the buffer fills GDS with
  `DMA_DATA` and reads a counter back into the indirect-dispatch arguments (F32's pattern).
  Skipping those two programs did not help (721–722). Open: which program, and what it writes
  that the WD then reads at address 0 + offset. Tooling added on the way: the dispatch journal
  (`BC5_DIRECT_DISPATCH_JOURNAL=1`), program tracking through `LOAD_SH_REG_INDEX` tables, the
  launchers keeping an inherited `BC5_DIRECT_SKIP_PGM`.

- **The program** (runs 729–735, bisection by `BC5_DIRECT_SKIP_PGM` after the launchers learned
  to keep an inherited list; the code dumped from guest memory with gdb and read by an agent):
  dropping every `DISPATCH_INDIRECT` removes the fault; so does skipping the engine's eleven
  indirect programs; of those, group B (five); of those, three; of those, **0x909974400 alone**.
  It is the BVH neighbour-link compaction (`buffer_atomic_or` back-pointers, 64-byte records with
  empty bounds, a compacted index list behind a byte counter; user data tagged `PSR_BVHL`), the
  stage before the reflection traversal the host already skips. With it skipped the opening
  plays to its end and the game reaches gameplay (run 735: seven minutes, no fence timeout, the
  tutorial prompt on screen). Skipping other halves of the eleven took the machine down twice.

**Verdict.** F201 had two host causes. The AMM automatic pool was never recycled — fixed
generically (F206). One BVH compaction dispatch of the night scene writes what the geometry
engine then fetches from address 0 — skipped in the launchers with the traversal it feeds (F207),
a diagnostic like exp 0123's until the BVH inputs are right (F116, F173). The second title now
runs from its intro through the opening into gameplay.
