# exp 0438 A1b (tag a1b438): readers without the table copy

**What changed** (only with `KYTY_BC5_0438_A1=1`). `mka1b.py` (19 exact-once replacements) gives `VirtualRangesMap` immutable sorted chunks of at most 512 ranges. Node changes note their keys; the next reader rebuilds only the touched chunks (copy on write). `Bc5ForEachMappedRange`, `Bc5RangesWithDirty` and `Bc5ForEachPrivateRegion` take the chunk pointer under the lock and walk outside it. A 4096-entry ring feeds the new `Bc5RangesTouchingSince(since, …)`. `KYTY_BC5_0438_A1J=<file>` (compiled out under `BC5_LEAN`) writes 72-byte records of every mutating call.

**Finding.** `DirtyWithTouching` never copied the table. The copies were `Snapshot`/`SnapshotWithDirty`.

**md5s.** In `515db924…bf0`, out `8c59e27a…c97`.

**Test** (`bash test_a1b438.sh`, 25,000 ops × 12 seeds, FAIL 0 everywhere):

| Run | PASS checks | cursor complete/fallback |
|---|---|---|
| A1=1, journal + replay | 5,217,465 | 29,261/65 |
| unset / =0 | 2,173,471 / 2,173,459 | 0/14,687 |
| chunk 8 ring 64, A1=1 | 5,246,550 | 30,771/4,674 |
| chunk 8, unset | 2,188,469 | 0/17,689 |
| lean, A1=1 | 2,458,817 | 14,654/33 |
| `--replay` seed1, map / vec | 229,863 / 206,077 | |

Mutants (all caught): b1 rename leaves chunk stale (FAIL 31), b2 ring entry skipped (12), b3 Protect missing from journal (24), b4 rebuild boundary (29).

**Bench** (29,000 ranges, 2,000 × edit + ForEachMappedRange): today 6,009 ms, A1 6,004 ms, A1b 598 ms. Edits alone: map 4.3 ms, A1b 6.4 ms.

**Assumption.** Each mutation does one generation bump and one `NoteDirtyUnlocked` (16 each, by grep).

**Open risks.**
- Not built in full `memory.cpp`, not run on the box.
- The default geometry made one chunk only; boundaries were tested with chunk 8.
- `Bc5RangesTouchingSince` has no caller and no `memory.h` declaration.
- Journal: its lock serializes mutators; a crash loses the unflushed tail.
- Threads untested; readers lock briefly to take the pointer.
- The chunks are a second table copy (~2 MiB).
