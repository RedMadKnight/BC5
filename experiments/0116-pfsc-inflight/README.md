# 0116 — one inflate per PFSC block, without striped locks, and a 256 MiB PFSC cache

**Question.** Experiment 0114 made the PFSC reader inflate each block once with 64 striped locks.
ASTRO BOT then loaded slower and hit GPU timeouts. Can the PFSC reader inflate each block once with
nothing else slowing down? The likely causes were:
- a stripe made readers of *different* blocks wait for an unrelated inflate, including decode-ahead
  inflates;
- the 16 MiB cache was too small for ASTRO's parallel streams.

**Setup.**
- Change: commit 176f68c (`tools/bc5-mount`).
  - `src/cache.rs` `DecodeCache`: a sharded `BlockCache` plus a sharded map of in-flight blocks.
    - A missing block gets its own slot (`Mutex<Option<outcome>>` + `Condvar`). Only readers of
      that block wait on it. The map's shard lock is held only to look up or insert a slot, never
      while a block decodes.
    - A decoder caches the block before it leaves the map, and a reader looks at the cache again
      under the map lock, so a finished block is never decoded twice by mistake.
    - Errors reach the waiters, and are not cached. A panic in a decode also releases the waiters.
  - Decode-ahead never waits. `ReadAt::prefetch` and `FileTree::prefetch_file` (exFAT clusters,
    then PFSC blocks; package: inner blocks) decode only blocks that are neither cached nor in
    flight. They skip blocks that another reader is decoding. `fuse.rs` `decode_ahead` calls
    `prefetch_file` instead of reading the window into a scratch buffer.
  - `src/pfsc.rs` uses `DecodeCache` and counts inflates in `bc5_mount::stats`. Its cache is
    256 MiB by default; `BC5_MOUNT_CACHE_MIB` overrides it, as for packages.
  - `src/pkg/inner.rs` drops the 64 striped locks of experiment 0112 for `DecodeCache`. Its cache
    stays 32 MiB.
- Unit tests (`cargo test -p bc5-mount --no-default-features`, 55 + 13 + 10 pass):
  - 8 threads reading one block decode it once;
  - a 500 ms decode of block 0 does not delay a reader of block 16 (same shard), nor a prefetch
    over block 0;
  - a PFSC source whose block 0 sleeps: 4 concurrent readers read it from the source once, and
    blocks 1 and 2 and a decode-ahead over 0..4 return while block 0 is still in flight;
  - errors and panics reach the waiters;
  - both round-trip suites also decode every file ahead and compare it again.
- `cargo clippy -p bc5-mount --all-targets -- -D warnings` passes, with `fuse` on the box and
  without it on Windows. `cargo fmt --check` passes.
- Offline benchmark on the BC-250, 2026-10-15 09:53–09:59, no game running. Kernel
  7.2.8-ogc5.1, 16 threads.
  - Old binary: `~/bc5-work/bc5-tools-ubuntu/release/bc5-mount` (39ad030, as in 0114 run 429).
  - New binary: built from 176f68c's code into `~/bc5-work/bc5-mount-bench/pfsc`.
  - Scripts: `bench-common.sh`, `bench-fuse.sh`, `bench-cat.sh`. They take the largest files up to
    512 MiB of the maintainer's ASTRO BOT dump, read only through `bc5-mount`. The file list was
    kept in `~/bc5-data` and deleted after the runs.
  - `bench-fuse.sh`: a fresh mount per run, then `dd` of N files in parallel plus 4 more `dd` of
    one of them. It records wall time, the mount's CPU time (`/proc/<pid>/stat`) and
    `BC5_MOUNT_STATS`.
  - `bench-cat.sh`: one `bc5-mount cat` process per reader. Processes share no cache, so this run
    measures per-process overhead only.

**Result.** Raw output is in `raw/`.

FUSE, 8 files (1633 MiB) + 4 readers of one, 3 rounds (`raw/fuse-8files.txt`):

| binary | wall | mount CPU | blocks inflated again |
|---|---|---|---|
| old (16 MiB, no dedup) | 1.04–1.10 s | 8.11–8.58 s | not counted |
| new, 256 MiB | 0.98–1.02 s | 6.78–7.05 s | 1 |
| new, 64 MiB | 0.99–1.03 s | 6.77–7.15 s | 15–34 |
| new, 16 MiB | 1.01–1.03 s | 6.99–7.11 s | 788–870 |

FUSE, 24 files (3852 MiB) + 4 readers of one, 2 rounds (`raw/fuse-24files.txt`):

| binary | wall | mount CPU | blocks inflated again |
|---|---|---|---|
| old | 2.55–2.70 s | 18.82–20.26 s | not counted |
| new, 256 MiB | 2.21–2.22 s | 16.83–16.84 s | 3 |
| new, 64 MiB | 2.22–2.24 s | 16.95–17.10 s | 228–354 |
| new, 16 MiB | 2.37 s | 18.05–18.14 s | 5920–6524 |

- **Opening the dump inflates 2983 blocks** (186 MiB: the exFAT metadata). Afterwards the new
  binary inflated exactly the bytes it served. 29,122 − 2983 blocks = 1633 MiB.
- **`cat`, one process per reader** (`raw/cat.txt`): old 1.34–1.36 s, new 1.41–1.42 s, new with
  16 MiB 1.35–1.38 s. The new binary's extra ~0.5 s of system time over 8 processes is each
  process faulting in its larger cache once. The 16 MiB variant matches the old binary. A
  long-lived mount pays that cost once.

**Verdict.** Passed offline, game run pending.
- Through FUSE the new reader is not slower anywhere. It is 3–5 % faster with 8 streams and
  13–18 % faster with 24. The mount needs 11–17 % less CPU.
- 256 MiB keeps re-inflation at ~0. 64 MiB already re-inflates hundreds of blocks at 24 streams,
  and 16 MiB thousands.
- The only cost is a one-time ~0.06 s page-fault cost per process for the larger cache.
- Whether ASTRO BOT's second load phase and its GPU timeouts are unaffected (the 0114 failure) is
  not decided here. The main session will run ASTRO with the maintainer present, compare the load
  window with 0114 run 426/429 (25–31 s), and record the outcome in a new experiment.
