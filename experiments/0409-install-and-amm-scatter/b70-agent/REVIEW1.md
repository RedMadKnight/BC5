# Review round 1 (Claude, top session): fix these, then re-run the test

Status: **not usable yet.** The edit script runs, gives the same md5 every time and refuses a second run, but the patch
has these defects:

1. **All pieces are mapped at the same address.** In `Bc5MapAutoScattered`, `addr = va` for every piece. Piece i must be
   mapped at `va + (sum of the sizes of pieces 0..i-1)`, and its rollback must unmap at that same address.
2. **The last piece is not trimmed.** `Bc5PoolGatherLocked` stops once `have >= want`, but the last piece is mapped at
   its full size, so the map runs past `va + size`. Trim the last piece to `want - (have before it)`, with the remainder
   staying free.
3. **Gathered pieces are never taken off the free list.** Gather only copies `g_amm_auto_free`, so the next map can
   take the same pieces again. Under the pool mutex, remove or split every gathered piece. Rollback must give the
   pieces back.
4. **The borrow does not borrow in pieces.** `Bc5PoolBorrowDirectLocked` asks for the whole `remaining` amount every
   time, so it is one contiguous request repeated up to 16 times. On failure, retry with smaller sizes (halving, down to
   2 MiB), and keep each borrowed piece's real size.
5. **Bookkeeping.** Every piece needs its own `AmmAutoRecordVa(va_i, dmem_i, size_i)`, and unmapping any sub-range must
   release exactly the pieces it covers.
6. **The test checks a copy, not the patch.** `pool0401.cpp` re-implements the logic, so it does not test the edited
   `libAmpr.cpp`. Extract the new helpers into `work/pool0401_impl.inc`, `#include` that file from both the patched
   `libAmpr.cpp` (through `mkpool0401.py`) and the test, and stub the kernel calls in the test.
7. **"partial unmap" fails** (lines 478–484). Fix it; do not weaken the test.
8. **Missing deliverables:** `work/NOTES.md` is missing, and nothing has been committed. Commit each time the test
   passes.
9. **`mkpool0401.py` on its own output** prints "has the edit already" but exits 0. It must exit non-zero.

Done when `g++ -std=c++20 -O1 -Wall work/pool0401.cpp -o work/pool0401 && ./work/pool0401` prints only PASS lines and
exits 0, and the test also covers defects 1–5: distinct addresses, no overlap, a trimmed last piece, pieces removed and
restored, and a piecewise borrow.
