# Review round 5 (Claude, top session): two fixes, then it can go to a box build

Round 4 is good: the script runs on the ORIGINAL file, the .inc between the markers is byte-identical, the rerun
exits 1, the test passes, and there are no warnings.

Blocking:
1. **Fall-through after a successful scattered map.** In the call site (rescue mode, and first mode when scatter
   succeeds), when Bc5MapAutoScattered() returns > 0, the code falls through to the ORIGINAL contiguous mapping below
   ("void* addr = ... command.va ... KernelMapDirectMemory2(... dmem_offset ...)"). That maps the same VA a second
   time, from a dmem_offset that was never allocated. After a successful scattered map, return the same success value
   the original path returns at its end (check what it returns, e.g. OK), and skip the rest.
   Add a test for it: a stubbed "original path" counter must stay 0 after a scattered success.
2. **getenv on every AMM map.** The call site calls std::getenv("KYTY_BC5_AMM_SCATTER") on every map, which is a hot
   path. Use the cached Bc5AmmScatterMode() from the .inc (read once, a static).

Done when the test (including the new case) passes, the byte-equality check passes, the rerun exits 1, and you have
committed.
