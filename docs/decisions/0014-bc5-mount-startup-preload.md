# ADR 0014 — bc5-mount: record a title's startup reads once, preload them at every mount

**Status:** measured, not adopted (2026-10-23, exp 0230). Built and tested (A2), then A/B'd on
ASTRO BOT (A3): the preload read its 1.7 GB in 5–7 s, and the startup's reads ended ~1 s sooner, but
the first logo moved by 0.5 s at most. Since the drive was freed (F286, F287) the startup is no longer
bound by I/O, so the shared binary and the launchers are left unchanged. The code is behind two
environment switches, `BC5_MOUNT_TRACE` and `BC5_MOUNT_PRELOAD`, both off by default.

## Context

ASTRO BOT's wait before its first logo, measured in experiments 0227 and 0228 (F286):
- The startup is ~8,000 reads of the game image through `bc5-mount` (median 13 KiB, ~3.2 GB
  decoded), issued one after another by the title (exp 0227, run AT1). It is bound by latency:
  - `bc5-mount`'s 8 read workers use 0.2–1 core in all;
  - the image reads at 154–760 MB/s in bulk, yet the startup reads at 14–320 MiB/s.
- "presents" came at 10–14 s when the reads were fast and at 25–50 s when they were slow:
  - the slow case came when the page cache had lost the image's startup data;
  - it also came when the drive was in a slow state: twice in exp 0228, with the cache dropped both
    times, the same arm took 33 and 12 s minutes apart.
- What did not help:
  - a larger decode-ahead (`BC5_MOUNT_PREFETCH_KIB=32768`, exp 0228 A0). It only fires for one
    file read in order (`fuse.rs`, `Stream`);
  - `KYTY_BC5_APR_PARALLEL=8` (exp 0227);
  - the GPU journal and the submission chains (exp 0227).
- `play-astro.sh` mounts the image at every launch and unmounts it on exit, so `bc5-mount`'s decoded
  block cache is empty at every start. The second title's package has an on-disk decoded-block
  cache (exp 0112), which is not traced here.

Reading the same bytes as a few large sequential requests, before the title asks for them, turns
~8,000 dependent small reads into page-cache hits. Large reads stayed fast even in the drive's slow
state (154 MB/s at worst, against 14–100 MiB/s for the startup's small reads).

## Decision (proposed)

1. **`BC5_MOUNT_TRACE=<file>`**, with `BC5_MOUNT_TRACE_SECS` (default 120):
   - every read `FileSource` makes from the image during the first N seconds after it is opened is
     appended to `<file>`, one line `<ms since open> <offset> <length>`;
   - writes are buffered and flushed at the end of the window or at exit;
   - only `FileSource` is traced; the package path's disk cache file is not (a later step if needed).
2. **`BC5_MOUNT_PRELOAD=<file>`** (a trace file from step 1), when `bc5-mount mount` starts:
   - The ranges are merged: sorted by offset, joined across gaps up to 1 MiB, split into chunks of at
     most 8 MiB.
   - The chunks are ordered by their earliest use in the trace, so data the title needs first
     arrives first.
   - One background thread reads them through its own handle on the image, with a reused 8-MiB
     buffer whose contents are discarded. That populates the kernel's page cache, so the FUSE
     workers' reads then hit memory.
   - Ranges past the image's end are skipped, so a stale list only wastes I/O.
   - It logs the chunks, the bytes and the time to stderr (`play-mount.log`).
   - Standard library only: no new dependency, and no `posix_fadvise`, which would need `libc`.
3. **The list lives next to the image's cache**, `~/bc5-data/cache/bc5-mount/<image key>.preload` (the
   launcher's concern, not `bc5-mount`'s). It is recorded once per title, from a cold start, and again
   after a game update.

## Alternatives

- **Keep the mount alive between launches** instead of unmounting on exit. The decoded-block cache
  would survive, but not across reboots or page-cache evictions, which is the slow case. Worth doing
  as well (launcher only); it does not replace the preload.
- **A larger `read_ahead_kb` on the NVMe** needs root (the maintainer's call). It helps the kernel's
  readahead for in-order reads, but `bc5-mount`'s reads of the image are scattered.
- **An external preloader** (vmtouch, a script) needs the same list. Inside `bc5-mount` it starts
  exactly at mount time, which the launcher already orders before the emulator.

## Risks

- About 2–3 GB more page cache at start. The title's own memory, ~12 GB, would evict it later; that
  is harmless, since the preload's job is done by then. MemAvailable was 13.4–13.9 GB at every
  exp 0227/0228 start.
- The preload competes with the title's first reads for the drive. Ordering by first use and a
  single thread keep that small; the A/B measures it.
- A list from another game version reads useless ranges: the cost is I/O only, and correctness is
  unaffected, because the preload never serves data.

## Plan

- A1: the code, with unit tests (merge, ordering, parse, trace, preload against an in-memory and a
  temporary-file source); `cargo test`, `cargo clippy -- -D warnings`, `cargo fmt --check`.
- A2: a build into an experiment directory (the shared binary untouched), then one cold traced start
  per title to make the lists.
- A3: an A/B per title, without and with the preload, cold and after a full run, alternating.
  Measured:
  - "presents" from screenshots, the startup reads' end, and the launcher-to-emulator delay;
  - `bc5-mount` CPU and a drive probe per run (exp 0228).
- Integration (launcher plus the shared binary, with a backup) only on a clear gain with no regression.
