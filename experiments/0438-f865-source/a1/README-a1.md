# exp 0438 A1 (tag a1438): VirtualRanges in an ordered map

**What changed.** `mka1.py` renames the old class to `VirtualRangesVec` and changes nothing else in it. It adds `VirtualRangesMap` (a `std::multimap` keyed by start) and a thin `VirtualRanges` dispatcher, so every public signature stays the same. The dispatcher reads `KYTY_BC5_0438_A1` once: `"1"` selects the map; anything else selects the old code. It prints `[bc5] exp 0438 A1 ranges map: on|off`. Splits rewrite a node in place and emplace the other pieces with a hint. Merges erase the neighbour node. Windows, merge pairs, `SameMergeKey` and `m_gen` bumps follow the old code step by step. Snapshots are built at most once per generation.

**Why a multimap.** The old code accepts a duplicate start at `UINT64_MAX` (`End` saturates). The test found this.

**Assumptions.** `map_records.hpp` is an unchanged copy from `kyty-base2`. The `BC5_FIXED_ENV` stub returns the env value, or the default when unset.

**md5s.** Input `aa7d7f5b…922`, output `515db924…bf0`.

**Test** (`bash test_a1438.sh`, VS clang++ `-std=c++20 -O2 -Werror`):

| Run | Result |
|---|---|
| A1=1 / unset / 0 / A1=1 FAST=0 | 300,000 ops each, PASS 16,433,847, FAIL 0, 12/12 seeds |
| m1 split right piece dropped | caught, FAIL 107 |
| m2 disallow_merge ignored | caught, FAIL 58 |
| m3 stale snapshot cache | caught, FAIL 24 |
| m4 touching misses end==lo | caught, FAIL 12 |

**Bench** (29,000 ranges):

| | vec | map |
|---|---|---|
| 80,000 edits | 17,184 ms | 56.7 ms |
| 200 snapshots | 32.9 ms | 34.2 ms |

**Not verified.**
- Full `memory.cpp` build.
- A run on the box.
- Threads (`Generation()` stays lock-free; no caller holds iterators).
- The lean wiring.

The snapshot cache adds ~2 MiB.
