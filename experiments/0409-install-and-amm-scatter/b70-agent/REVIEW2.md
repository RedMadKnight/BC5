# Review round 2 (Claude, top session)

Good progress: points 1-5, 7, 8 and 9 are fixed (pieces at va+offset, last piece trimmed, gather removes, halving borrow,
partial unmap passes, NOTES.md, commit, rerun exits 1). All 8 test groups pass.

Still open, point 6 (blocking): the test still re-implements the helpers. work/pool0401_impl.inc exists but nothing
includes it; the patched libAmpr.cpp carries its own copy. The two copies match today (apart from printf lines), but
nothing keeps them in step.

Fix:
- Put the new helpers (Bc5PoolFreeStats, Bc5PoolGatherLocked, Bc5PoolSplitFitLocked, the borrow and the
  scattered-map/rollback logic) ONLY in pool0401_impl.inc, written against a few small hooks (the map, unmap,
  allocate-direct and record calls) that libAmpr.cpp defines with the real kernel calls and the test defines as stubs.
- mkpool0401.py inlines pool0401_impl.inc verbatim into libAmpr.cpp, between marker comments, so the shipped file is
  self-contained; the test #includes the same .inc.
- Add a check in the test that the .inc text inside the patched libAmpr.cpp equals pool0401_impl.inc byte for byte.
- No printf in the helpers (the journal lines stay in libAmpr.cpp only, behind mode >= 1).
- Fix the 4 -Wall warnings.
Done when the test passes, the byte-equality check passes, and `mkpool0401.py` still refuses a second run with exit 1.
