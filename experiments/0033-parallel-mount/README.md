# 0033 — a parallel bc5-mount: read workers, a sharded block cache, decode-ahead

**Question.** Experiment 0032 found the level load paced by one `bc5-mount` thread serving
every FUSE read in turn. How much of the 24 s window goes away when reads are answered in
parallel and files read in order are decoded ahead?

**Setup.** BC-250, 8C/16T, `bc5-mount` at this commit built in the `fedora` container
(`CARGO_TARGET_DIR=~/bc5-work/bc5-tools-ra`). Three changes, measured one after another:

1. Reads answered from a pool of worker threads (`fuse.rs`): the session thread still
   receives every request and answers lookups and listings itself, but hands each read to
   the pool, whose threads reply when done. 8 workers by default
   (`BC5_MOUNT_THREADS=<n>`; 1 gives the old behaviour). fuser 0.15's replies can be sent
   from any thread, so no library change was needed. Raising the kernel's limit on
   background requests needs fuser's `abi-7-13` feature and was left out: the default 12
   is above the 3–4 loader threads a game runs.
2. One block cache for both readers (`cache.rs`): 16 shards by block index, each with its
   own lock and LRU order, values reference-counted so a reader copies without a lock; the
   PFSC cache grows from 16 to 256 blocks (16 MiB), the package cache from 64 to 128 (32 MiB).
3. Decode-ahead: a read that starts where the file's last read ended (within 1 MiB) queues
   the decoding of the next 2 MiB not yet queued, into the cache, only while the pool has a
   free worker (`BC5_MOUNT_PREFETCH_KIB=<n>`, 0 turns it off).

Two measures: `mount-bench.sh` (four readers, each 400 MiB from the start of one of the
four largest files, through a fresh mount; the container is in the page cache, so this is
the cost of decoding and FUSE, not of the disk; `drop_caches` was not available to the
script), and unattended runs 140 (change 1) and 141 (all three) against run 139 of
experiment 0032, same recipe and wait sampler.

**Result.**

| Mount | 4 × 400 MiB through the mount |
|---|---|
| 1 worker | 650–664 MiB/s |
| 8 workers | 2098–2179 MiB/s |
| 8 workers, decode-ahead 2 MiB | 2384–2950 MiB/s |

| Run | Mount | Load window | Served | `bc5-mount` peak |
|---|---|---|---|---|
| 139 (0032) | 1 thread | 24 s (60–82 s) | 5.6 GB | 81 % of a core |
| 140 | 8 workers | 22 s (60–80 s) | 5.8 GB | 142 % |
| 141 | 8 workers, sharded cache, decode-ahead | 18 s (60–76 s) | 5.8 GB | 248 % |

The share of samples in which the game's loader threads wait on a read (`D`) fell from
12–20 % (run 139) to 4–16 % (run 141); the rest of their waiting is on each other (`futex`).

**Verdict.** Passed: the load window is a quarter shorter (24 → 18 s) and the mount now
uses up to 2.5 cores. The remaining time is mostly the game's own loaders waiting on each
other, which a faster file server does not shorten; the part of the load the maintainer
sees (about 15 s when the opening cutscene is skipped) should drop to about 9 s, to be
confirmed in their play. The new `bc5-mount` is installed where the play script takes it.
