# 0113 — decoded package blocks kept on disk: the second title's start-up logo 9.0 → 7.9 s

**Question.** After experiment 0112 the logo lasts 9.0 s. During it the machine is mostly idle:
- `bc5-mount`'s workers use 1.5 cores;
- the title's render thread spins at 0.7;
- its archive threads use 0.3 (run 422, per-thread CPU, 2.5–9 s).

So the reads wait on decoding latency rather than CPU. Every start decodes the same ~2 GB again.
If decoded blocks persist between mounts, how short does the logo get?

Other projects (experiment 0112, survey) extract a whole package to disk first. That needs ~197 GB
here, against 37 GB free.

**Setup.**
- `bc5-mount` (this repository, `src/pkg/diskcache.rs`), off by default:
  - `BC5_MOUNT_DISK_CACHE=<dir>` keeps each decoded Kraken block in `<key>.data`, a sparse file
    with one 256 KiB slot per block;
  - `<key>.map` holds 8 bytes per block (CRC-32 and length; 0 = absent);
  - the key is a SHA-256 of the stored image's length and first 64 KiB;
  - a block found there is read back instead of decoded, and a CRC mismatch drops it;
  - writing stops at `BC5_MOUNT_DISK_CACHE_MIB` (default 8192);
  - data is written before its map entry.
- Unit tests:
  - round trip across opens;
  - a corrupted byte rejected;
  - the limit;
  - a new layout starting afresh;
  - a package round trip whose second open reads from disk (`disk_cache_serves_a_second_open`).
- Runs, unattended intro (maintainer available), 2026-10-15:
  - 423 (08:42): fills the cache;
  - 425 (08:44): reads it back;
  - settings as run 421: play settings plus `KYTY_BC5_APR_PARALLEL=8` and `BC5_MOUNT_STATS=1`;
  - cache in `~/bc5-data/cache/bc5-mount` (private, outside the repository);
  - run 424 shared run 423's capture directory (same minute), so its frame counts are mixed and
    it is not used; 425 repeats it.

**Result.**

| run | state | steady (≥ 40 fps) from | after the first frame | decoded / from disk |
|---|---|---|---|---|
| 416 (0112) | before 0112 | 13 s | 10.9 s | — |
| 421 (0112) | parallel APR reads | 11 s | 9.0 s | 2725 MiB / — |
| 423 | cache empty, being filled | 12 s | 9.9 s | 2550 / 308 MiB |
| **425** | **cache filled** | **10 s** | **7.9 s** | **393 / 2555 MiB** |

- The cache took 2.3 GB on disk (sparse), for about 10,000 blocks.
- During run 425 the mount served 250–500 MB/s instead of 150–300 MB/s.
- Neither run had a read error.
- Run 423 was a little slower than 421 (9.9 s against 9.0 s): writing the cache costs a little the
  first time.

**Verdict.** Passed: from the second start on, the logo is 7.9 s instead of 9.0 s, and 10.9 s
before experiment 0112. What remains is the title's own pace: it reads ~1.8 GB in dependent
steps and processes the data in its own threads. Our side now serves reads mostly from disk.
Both knobs (`KYTY_BC5_APR_PARALLEL=8`, `BC5_MOUNT_DISK_CACHE`) are off by default; the play
shortcut changes only with the maintainer's yes. The cache grows with what the title reads,
up to its limit.
