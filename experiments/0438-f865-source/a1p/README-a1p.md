# exp 0438 A1P (tag a1p438): memory tables in ordered maps

**What changed.** `mka1p.py` adds map-based bodies to `PhysicalMemory`, `FlexibleMemory` and `PooledMemory`. With `KYTY_BC5_0438_A1P=1` each method edits only its window. Otherwise the unchanged vector code runs.

- Signatures are unchanged.
- `GetMappings`/`GetBlocks` return a copy, valid while the caller holds the owner's mutex.
- Pooled order: by `(Allocate piece, vaddr)`.
- `FindMappings` uses a physical index.
- VirtualRanges and the Bc5* readers are untouched.

**Assumptions.**
- A map holds the vector's content only while no entries overlap.
- An overlapping, empty or wrapping entry copies the table back to the vector code.
- The physical map needs `PHYSMAP_SORTED=1`.

**md5s.**

| Input | Output |
|---|---|
| tree `aa7d7f5b…922` | `e7751cda…140` |
| A1 `515db924…bf0` | `3f79d33e…f0a` |

The extracted code is identical for both inputs.

**Test** (`bash test_a1p438.sh`, real old against new classes):

| Run | Result |
|---|---|
| A1P=1, 20,000 ops × 3 classes × 12 seeds | PASS 3,097,487, FAIL 0 |
| unset / 0 / SORTED=0 / verify | FAIL 0 |
| mutants m1 to m6 | 6/6 caught |

**Bench** (29,000 entries, µs per operation, laptop under load):

| Operation | old | A1P |
|---|---|---|
| Phys ProtectMapping | 3623 | 47 |
| Phys Unmap+Map | 770 | 3.7 |
| Phys FindMappings | 369 | 14 |
| Flex Map | 818 | 1.5 |
| Flex Protect | 2126 | 1.0 |
| Pool Release+Allocate | 2193 | 2.4 |
| Pool Query | 31 | 0.9 |

Find (0.65 against 0.32 µs) and ascending fills are slower under A1P.

**Not verified.**
- Full `memory.cpp` build.
- Box run.
- The lean wiring (`std::getenv`).
- `ReleaseExpansion` and the Available sums stay O(n).
