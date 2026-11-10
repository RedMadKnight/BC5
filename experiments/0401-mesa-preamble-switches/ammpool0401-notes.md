# Exp 0401: the AMM auto pool under `KYTY_BC5_MEMORY_FROM_PARAM=1` (design note, 2026-11-06)

Design only: no build, no box access. For build e10. Sources, rebuilt on the laptop:
- "base" is `libAmpr.cpp` a0e2ff6e (`refs/Coder787-source_KytyPlus` at f266548 plus `git apply` of patch 0001; the
  md5 of `amm0401-notes.md`'s input). "mem" is that tree's memory.cpp f6154692, as in `mem0401-notes.md`.
- "cur" is `libAmpr.cpp` 0a1762f6, the e4 to e9 unit (base plus `mkamm0401.py`; README:146,156).

## 1. How the auto pool works today, and why FROM_PARAM=1 starves it

- **State.** A coalesced free list `g_amm_auto_free` and one record per automatic map in `g_amm_auto_maps`
  (base:1034-1035). Filled only by `AmmGiveDirectMemory` with usage auto (base:3464-3491, 3488): 0xbda00000 =
  3,034 MiB in every logged run (F269).
- **Map** (`AllocateAmmAutoDirectMemory`, base:1628-1659):
  1. First fit over the free list. The map needs ONE contiguous range (`AmmAutoAllocLocked`, base:1575-1590).
  2. Else it borrows one contiguous range of direct memory [0, `KernelGetDirectMemorySize()`) (base:1641-1643), from
     the kernel's first-fit allocator, clamped to `Size()` = total − flexible (mem:1278-1324, 1286; mem:808-811).
  3. A borrowed range never goes back to the kernel. After its unmap it joins the free list (base:1638-1639).
- **Returned** on an unmap (base:2028-2031), on a map over an old one (`AmmAutoRecordVa`, base:1622-1626), and on a
  failed map (base:1693-1696).
- **Failure chain (F206).** The map returns EAGAIN (base:1666-1670), and the rest of its buffer is dropped
  (base:2041-2055). The APR reads that follow hit unmapped AMM pages, and the fault hook exits with "AMM
  virtual-memory unmap is unsupported" (mem:3650-3661).
- **A leak by unmap.** `KernelMunmap` returns EACCES over a hole (mem:2732-2733). libAmpr then frees nothing and stops
  the buffer. `BC5_R3_MUNMAP_HOLES` fixes this (`mem0405-notes.md`, M7). e2 lacked it. It is in e5 and later, and on
  in the normal profile (`profile0401.sh:20`).

**Why it starves.**
- With the switch on, direct memory is 12,428 MiB instead of 13,548 (README:93; `mem0401-notes.md`:70). There is
  1,120 MiB less to borrow from.
- At 18:14 (README:98) a 64 MiB map was refused, with 9,653 records and 0xd444000 = **212 MiB free** in the list. The
  pool had 3.3 times the bytes it needed, but no 64 MiB hole. The contiguous borrow failed too.
- This is fragmentation. Exp 0288 (README:106) shows 653 AMM views of 2,207 MiB (about 3.4 MiB each) and 18,661 views
  under 1 MiB, 923 MiB in all (about 50 KiB each). With first fit, the small maps break up the big holes. A big map
  that then finds no hole borrows fresh direct memory. The 1,120 MiB more with the switch off hid this.
- Exp 0288 (switch off) had 3,130 MiB of AMM views at 240 s, above the 3,034 given: some borrowing is needed even
  with perfect packing, if all are automatic maps (TODO(verify): direct and set-buffer maps are named "AMM" too).
- **The cost unit.** The 1,120 MiB is address space; direct memory never touched costs no RAM (F353 Q2). Pinned at
  about 150 s: 11,588 MiB with the switch on, 11,710 with it off (README:94). So each design is costed in pinned AMM
  pages, not in direct-memory size.

## 2. Fix designs (default off; unset, empty, 0 and unknown values are off, LESSONS R41)

**D1 `KYTY_BC5_AMM_SCATTER=journal|rescue|first`: scattered automatic maps.**
- *The idea.* An automatic map may take several free ranges. Each piece is mapped at its own part of the VA with
  `KernelMapDirectMemory2`, and each is recorded in `g_amm_auto_maps`. Unmaps already free several records
  (base:1593-1620). `PhysicalMemory::Map` accepts a range over adjacent allocated blocks (mem:1483-1514), so
  coalesced ranges are safe. Prior art: upstream KytyPlus 3eee96a does this and never borrows
  (`refs/Coder787-source_KytyPlus` memory.cpp:1251-1266 `ReserveAutomatic`, 3275-3297 `MapAutomaticMemory`;
  GPL-2.0). AnyPS5 does too (`amm0401-notes.md`:110-111).
- *`rescue`.* Today's order runs first: a single fit, then today's contiguous borrow. Only where today returns EAGAIN:
  take free ranges largest first; borrow any shortfall in pieces, each the largest free direct block
  (`KernelAvailableDirectMemorySize`, mem:2745; `PhysicalMemory::Available`, mem:1326-1360), rounded up to 2 MiB;
  then map the pieces. Every map that succeeds today runs unchanged.
- *`first`.* A single fit, else the scatter, else the piece borrow. No contiguous borrow.
- *`journal`.* No behaviour change; only the lines below.
- *Memory cost.* `rescue`: 0 MiB, because it acts only where today dies. `first`: less than today, because it borrows
  only when the free bytes in total are short; the journal measures the saving. Both keep the full 1,120 MiB.
- *Risks.*
  - The fatal stays possible when the pool's free bytes plus the free direct memory are less than the map.
  - Each piece is one more host mapping, range-table entry and direct-path view. The host's sync costs grow with views
    (F89), and there are 18,661 small AMM views already. Pieces are taken largest first, and the journal counts them.
    TODO(verify): `vm.max_map_count` on the box; the GPU TLB cost of scattered backing.
  - A page can be used twice only through a bookkeeping bug; the tests check that pieces never overlap.
  - Recycled pages are not a new risk: today's first fit already reuses freed pages at once, uncleared (cur:1804,
    exp 0104). Scatter reuses more of them.
  - Rollback: if piece k fails, pieces 0..k−1 are unmapped and freed, as upstream does. An older mapping at that VA is
    then gone, where today it stays.
  - The page-table path looks up one record of the full size (`Bc5ExecuteAmmMap0401`, cur:4335-4342). A scattered map
    would enter no pages, so the lookup must walk the records.
  - The lock order is unchanged: the pool mutex, then the memory mutex, as at base:1641.
- *Lines (stderr).* `[bc5] exp 0401: KYTY_BC5_AMM_SCATTER off|journal|rescue|first` once at registration. Always, in
  journal and above:
  - `[bc5] exp 0401 pool: borrow #n 0x<len> at dmem 0x<off> for a map of 0x<size>`, with the pool's figures (given G
    MiB, borrowed B, free F in H holes, largest L) and the largest free direct block D;
  - `… pool: REFUSED va … size …` with the same figures; in journal mode, plus `scatter would take P pieces|not enough`;
  - `… pool: scatter rollback va … size … at piece k of P -> 0x…`.
  Sampled (the first 32, then every 256th): `… pool: scatter #n va … size … in P pieces`, with the largest piece and
  the free figures. A summary of the same figures every 4096th automatic map.

**D2 `KYTY_BC5_AMM_RESERVE_MIB=<n>`: a host-only reserve for the pool.**
- *What.* n MiB of guest backing above the title's memory, [TotalSize, TotalSize+n). Only the pool may borrow it, and
  only after the normal borrow fails. The title still sees 12,428 MiB.
- *Where.* memory.cpp in four places: the backing size (mem:1201), a host-only `Alloc` without the clamp (mem:1286),
  `KernelDirectMemoryQuery` hiding these blocks (mem:2851-2870), and the pool's fallback.
- *Cost.* Up to n of the 1,120 MiB, and only when used. A used AMM page is pinned ("AMM" is imported eagerly, F89).
  With n = 256, at least 864 MiB stays. *Lines:* `pool: reserve n MiB at dmem …` at init, then each use and what is left.
- *Risks.* It is memory.cpp surgery. TODO(verify): whether the direct path imports memfd offsets past TotalSize
  (`bc5LleAgc.cpp`, `direct_sync_one`). Fragmentation hits the reserve too, so it only delays the end. The cheap
  variant borrows n MiB into the pool at `AmmGiveDirectMemory`, out of the title's 12,428 MiB. A title allocation can
  then fail (ASTRO BOT's case, `mem0401-notes.md` Doubts).

**D3 `KYTY_BC5_AMM_POOL_FIT=split`: keep the big holes whole.**
- In `AmmAutoAllocLocked`, a map under 1 MiB takes the top end of the highest fitting range. Larger maps keep first
  fit from the bottom. The 1 MiB line is exp 0288's view split.
- Cost 0. Low risk: maps stay contiguous and add no views. It guarantees nothing. With D1 it cuts the piece count.
  Lines: the registration line, and D1's REFUSED line (shared code).

**The lead's "recycle", judged.** The 9,653 records are maps the title still holds. Taking their pages is double use:
APR reads and the GPU would write into another texture. Pages are already returned on an unmap, on a map over an old
one, and on a failed map (0159). The one real leak is the hole unmap above, and M7 fixes it. Defragmenting live maps
(copy, then remap) needs the GPU idle and the APR quiet, which is not worth it. So there is no recycle switch; keep
`BC5_R3_MUNMAP_HOLES=1` in every FROM_PARAM test.

## 3. Recommendation: D1, with `KYTY_BC5_AMM_SCATTER=rescue` first and `first` next

- **Why D1.** The records point at fragmentation: 212 MiB free against a 64 MiB refusal. D1 alone costs no memory, and
  other hosts chose it. In `rescue` it changes only the maps that kill the host today. D3 goes into the same e10 build
  under its own switch (fixes first), with `journal` as the catcher. First play: FROM_PARAM=1, normal profile (M7 on).
- **The script.** `mkpool0401.py` takes libAmpr.cpp 0a1762f6 in and leaves memory.cpp alone. The pure part (stats,
  largest-first gather, split fit, over `std::map`) is written twice as the same text: inline in the unit, and as
  `amm_pool0401.inc` for the test. That is e3's `inherit_scan.inc` pattern, and it avoids the same-directory include
  that stopped series e's first build.
- **Where each change goes (cur):**
  1. A new block between `AmmAutoRecordVa` (cur:1649-1653) and `AllocateAmmAutoDirectMemory` (cur:1655): the mode
     reader, the given/borrowed counters and the pure part; `Bc5PoolBorrowPiecesLocked` (pool mutex held, at most 16
     pieces); and `Bc5MapAutoScattered`. For each piece it calls `KernelMapDirectMemory2` with today's protection
     rule (cur:1784-1787), then `AmmAutoRecordVa`. At the end come the name call over the whole range, the trace line
     with the piece count, and the 0x1fe0000 watch (cur:1821).
  2. `AllocateAmmAutoDirectMemory` (cur:1655-1685): count the borrowed bytes; write the borrow and REFUSED lines.
  3. `ExecuteAmmMapCommandToday` (cur:1773-1777): in `rescue`, `return Bc5MapAutoScattered(command)` at the EAGAIN
     return; in `first`, the same call before the allocation when no single range fits.
  4. `Bc5ExecuteAmmMap0401` (cur:4330-4343): with D1 on, walk the records in [va, va+size) and call `Bc5RecordPages`
     for each. With D1 off, today's `find`.
  5. `AmmGiveDirectMemory`, the usage-auto branch (cur:3634): count the given bytes.
  6. `LIB_DEFINE(InitAmpr_1_Ampr)` (cur:4815), beside the e4 switches' lines: the mode line.
  7. D3 in `AmmAutoAllocLocked` (cur:1602-1617).
  `Bc5AllocatePaForPrt` (cur:4116) stays contiguous: the second title uses no PRT commands.
- **The CPU-only test, `pool0401.cpp`.** Pure code, no emulator objects, so it runs on the laptop. TODO(verify):
  that VS clang++ links and runs it; otherwise g++ in the box's container, as a CPU gate.
  1. The 18:14 shape: a 3,034 MiB pool cut into 9,653 records, with 212 MiB free in holes up to 8 MiB (seeded). For a
     64 MiB map, first fit refuses and the gather covers exactly 64 MiB, all from free holes.
  2. After every step the free list and the records add up to given plus borrowed, never overlap, and no two free
     ranges touch. An unmap of a scattered map, or a map over half of it, returns exactly the overlapped pieces. When
     the total is short, the gather fails and the free list is unchanged.
  3. A churn replay with exp 0288's size mix plus periodic 64 MiB maps, at direct headroom 0, 266 and 1,386 MiB. It
     reports the refusals and the peak borrowed MiB (the RAM cost) for today, split, rescue and first. Pass: rescue and
     first refuse nothing while the live bytes fit in the pool plus the headroom.
  4. If an `amm trace` log is kept: a replay of its map-auto and unmap lines (sizes and VAs only).
  A later box gate in `amm0401.cpp`'s style adds real mappings: a tag per 16 KiB page (no aliasing), a seam that
  forces a rollback, every page in the page table with PRT and EXTRA on, and off as today (EAGAIN when direct memory
  is filled under a small `KYTY_GUEST_MEMORY_MB`).

## 4. Open questions (not settled from the laptop)

1. The hole sizes, the borrowed total B, and the free direct memory and its largest block at 18:14 are unknown. Only
   `journal` or `rescue` will show them.
2. Is the 18:14 trace still on the box? The 18:16 play started right after it, and e2's launcher kept only
   `play-last.log` until 22:3x (README:118; LESSONS line 283).
3. Does the title size its direct allocations from `KernelGetDirectMemorySize`? Exp 0288 measured with the switch off
   only. If the title takes all free direct memory, D1 can borrow nothing, and D2 is the fallback. Were all 3,130 MiB
   of its AMM views automatic maps?
4. Did e2 also leak through hole unmaps (`unmap … -> 0x8002000d` lines in its trace)? Mode cpacb of
   `shortcut0401.sh` now writes e8 with FROM_PARAM=1 (prepared 2026-11-06, md5 3cdcbf19; not installed while he
   plays). e8 has M7, and no play of e8 with the switch on is recorded yet.
5. How many pieces would `rescue` and `first` make, and what do they cost in host syncs and the GPU TLB?
6. FROM_PARAM's real RAM win was 120 MiB pinned at 150 s, not 1,120 MiB. Once the pool holds, measure it with
   `BC5_DIRECT_MEM_LINE`, switch on against off.
