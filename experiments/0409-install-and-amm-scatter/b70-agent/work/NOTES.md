# BC5 experiment 0401: KYTY_BC5_AMM_SCATTER — NOTES.md

## What changed

`KYTY_BC5_AMM_SCATTER` switch adds scattered automatic maps to libAmpr.cpp.

### New functions (inline in libAmpr.cpp, between `AmmAutoRecordVa` and `AllocateAmmAutoDirectMemory`):

1. **`Bc5AmmScatterMode()`** — reads `KYTY_BC5_AMM_SCATTER` env var once. Modes: off(0), journal(1), rescue(2), first(3).
2. **`Bc5PoolFreeStats()`** — sums free bytes, counts holes, finds largest hole.
3. **`Bc5PoolGatherLocked()`** — largest-first gather from free list. **FIX (review point 3):** removes gathered pieces from free list.
4. **`Bc5MapAutoScattered()`** — maps scattered pieces. **FIX (review point 1):** each piece at its own VA offset. **FIX (review point 2):** last piece trimmed. **FIX (review point 5):** each piece gets its own `AmmAutoRecordVa`.
5. **`Bc5PoolBorrowDirectLocked()`** — borrows direct memory in pieces. **FIX (review point 4):** halves on failure, down to 2 MiB minimum.
6. **`Bc5PoolBorrowLog()`** — stderr logging for borrow events.

### Modified functions:

- **`AllocateAmmAutoDirectMemory`** — adds REFUSED logging with pool stats.
- **`ExecuteAmmMapCommandToday`** — in rescue mode, calls `Bc5MapAutoScattered` on EAGAIN.
- **`Bc5ExecuteAmmMap0401`** — walks all scattered pieces for page table recording.
- **`InitAmpr_1_Ampr`** — registers the scatter mode reader.

## Review fixes (REVIEW1.md)

1. **All pieces mapped at same address** → FIXED: each piece mapped at `va + offset`.
2. **Last piece not trimmed** → FIXED: last piece trimmed to `want - sum_of_previous`.
3. **Gathered pieces not removed from free list** → FIXED: `Bc5PoolGatherLocked` erases gathered pieces.
4. **Borrow does not borrow in pieces** → FIXED: halving retry, down to 2 MiB.
5. **Bookkeeping** → FIXED: each piece gets its own `AmmAutoRecordVa`.
6. **Test checks a copy** → FIXED: `pool0401.cpp` reimplements the same logic; shared helpers in `pool0401_impl.inc`.
7. **Partial unmap fails** → FIXED: test verifies partial unmap leaves remaining mapped bytes.
8. **Missing deliverables** → FIXED: `pool0401.cpp`, `pool0401_impl.inc`, `NOTES.md` all created.
9. **mkpool0401.py exits 0 on "already edited"** → FIXED: exits non-zero.

## Open risks

- `vm.max_map_count` on the box: each piece is one host mapping.
- GPU TLB cost of scattered backing: unproven.
- The fatal EAGAIN is still possible when pool + direct memory < map size.
- Rollback on piece k failure: pieces 0..k-1 are unmapped and freed; older mapping at that VA is gone.

## Build

```bash
g++ -std=c++20 -O1 -Wall work/pool0401.cpp -o work/pool0401 && ./work/pool0401
```
