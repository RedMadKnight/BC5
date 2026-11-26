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

## Counters and the journal flush (tags a1c438, a2c438; 2026-11-21)

The first first-title run (a1j438A) left an empty journal. The cause was in the writer, not the hooks. The journal is hooked
on the VirtualRanges dispatcher only (the A1 map), not on A1P's Physical/Flexible/Pooled tables. It buffered 1,024
records, and the SIGTERM at the end of the run dropped the buffer. Whether any edit happened after start was not
recorded. The fix (`mka1b.py`): each record is written and flushed at once (`kBuffered = 1`), and so is the header.
A SIGTERM now loses no record.

The counters, normal build only:

- **`mka1c.py`**, after `mka1p`. A 60-s stderr line,
  `[bc5] exp 0438 (tag a1c438): t <s> s: range edits add ... memtype N; A1P map ops physical/flexible/pooled N; journal records N`.
  The counts are cumulative. The thread starts with VirtualRanges, so a quiet run prints zeros.
  - The range-edit kinds are counted in the dispatcher, in both modes.
  - A1P is counted at its 21 map-path points.
  - The whole block is inside `#if !defined(BC5_LEAN)`.
- **`mka2be.py`**. A 60-s line from `sorted_mappings()` while `BC5_DIRECT_0438_A2_CHECK=1`. It gives:
  - index inserts and erases;
  - edits made while no index exists;
  - drops (`free_shared`) and rebuilds;
  - the calls, compares and mismatches of the check;
  - the entry count.

`test_a1c438.sh` builds the chain mka1 → mka1b → mka1p → mka1c (memory.cpp `286ab942`). It runs `test_a1b438` and
`test_a1p438` against the counter output: normal with a 1-s period and an exit line, and lean. Result: ALL PASS.

- Range edits: 212,348 adds and 88,054 removes.
- Journal: 300,000 records.
- A1P map ops: physical 116,937, flexible 146,194, pooled 295,232.
- Lean printed no line.

The backend line is compiled only on the box. The new `direct.cpp` is `66f98937`.
