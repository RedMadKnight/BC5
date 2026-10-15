# 0112 — the second title's start-up logo: the game waits for ~1.75 GB of loading; reads decoded twice and run one at a time

**Question.** Playing on 2026-10-15 at 07:55, the maintainer saw:
- the start-up logo ("Sony Interactive Entertainment") still slow, while the rest of the intro
  movie was fast after experiment 0105;
- the menu slowing down again later.

What holds the logo?

**Setup.**
- The play shortcut's settings (incl. `BC5_DIRECT_PACE_FIX` and `BC5_DIRECT_REMEMBER_UNMAPPED`).
  Intro only, a fresh save, no input. The maintainer was present.
- Runs 412–421, 2026-10-15 08:05–08:27.

Tools in this directory:
- `pc-sampler-bt14u.sh`: thread stacks with an uptime stamp;
- `spinpeek.sh`: gdb disassembly and registers of the live process, private, stdout only;
- `topwatch.sh`: per-thread CPU;
- `logostat.py`: frames per second over the first seconds;
- `busythreads.py`: the threads not parked in a wait.

New:
- `bc5-mount` (this repository): `BC5_MOUNT_STATS=<s>` prints bytes served, blocks decoded and
  blocks decoded again. `BC5_MOUNT_CACHE_MIB` sets the package reader's block cache. The package
  reader now decodes a missing block once: 64 decode stripes, and a reader that finds the stripe
  busy re-checks the cache.
- KytyPlus (patch `0001-bc5-lle-agc.patch`, `libAmpr.cpp`), off by default:
  `KYTY_BC5_APR_PARALLEL=<n>` runs a run of consecutive APR ReadFile commands on n threads. A run
  whose destinations overlap stays in order, and the commands after the run still follow it.

**Result.**
1. **The logo is the title's loading screen.** In the first ~11 s the GPU is busy only 5–7 ms per
   frame, and the title's render thread spins. Three of four stack samples (run 412) sit at the
   same address in the title's executable. Its loop, read from the live process (run 413): while a
   state word is 1, try to run a pending job, otherwise `pause` ×20. The title holds its frames
   until loading finishes.
2. **The loading.**
   - The loader polls the "Loose Load" event queue every 100 µs: 182,642 waits in 30 s, 37 events
     received (run 414). The events are APR completions (filter −11).
   - APR reads in the first 12 s total about 1.75 GB, at 70–310 MB/s (run 415).
3. **Where the CPU goes** (run 416, per thread):
   - `bc5-mount`'s 8 workers use 4–6 cores in total;
   - `kcompactd0` runs at 100 % in two ~3 s bursts (572 compaction stalls since boot);
   - the render thread spins at ~90 %.

   Dropping the page cache first (run 417, `drop_caches`, permitted in sudoers) cut kcompactd's
   CPU 2.5× but left the logo exactly as long. Compaction is not the cause.
4. **The mount decoded most blocks twice** (run 418): served 1765 MiB, decoded 6206 MiB, and
   13,557 of 24,847 block decodes repeated an earlier one.
   - A 1 GiB block cache (run 419) still decoded 12,277 again. The cause is concurrent misses on
     the same block: the kernel splits a 256 KiB block into two 128 KiB reads that reach two
     workers at once.
   - With one decode per block (run 420): 3073 MiB decoded, 1035 repeats (evictions). The logo was
     no shorter.
5. **KytyPlus ran a buffer's reads one at a time.** `RunOrderedAprCommands` reads each command
   in turn. A submission of 48 reads was 48 sequential reads, so the mount's pool served one at a
   time.
   - `KYTY_BC5_APR_PARALLEL=8` (run 421): no read failures, and the intro is steady (≥ 40 fps)
     from 11 s instead of 13 s, 9.0 s after the first frame instead of 10.9 s.

   | run | change | steady from | after first frame | decoded / served |
   |---|---|---|---|---|
   | 416 | — | 13 s | 10.9 s | — |
   | 418 | — (counters) | 12 s | 9.9 s | 6206 / 1765 MiB |
   | 420 | one decode per block | 13 s | 11.0 s | 3073 / 1765 MiB |
   | 421 | + parallel APR reads | **11 s** | **9.0 s** | 2725 / 1752 MiB |
6. **The maintainer's menu slowdown was a GPU fault**, separate from the above.
   - At 07:57:03, an instruction fetch (SQC) at 0x80c8d799f000, while the maintainer navigated the
     menu: the "0x80 in bits 40–47" class of experiment 0056.
   - Ring timeout and reset at 07:57:05, and two more at 07:59:20 and 07:59:36. The title runs on
     after a reset, but slower.
7. Other projects (survey, 2026-10-15):
   - None mounts a Kraken-compressed PS5 package on the fly. KytyPlus and pkg-to-anyps5 extract it
     to disk first. AnyPS5, prosper, ps5rs and RPCSX take an extracted folder.
   - pkg-to-anyps5's pure-Rust Kraken reports ~55 MB/s per thread; ours does ~220 MB/s (`cat`, run
     on the box). powzix/ooz is GPL-3 (unusable here); Oodle is proprietary.
   - Extracting this title would need ~197 GB.

**Verdict.** Partly passed.
- The logo lasts as long as the title's start-up loading. Our side wasted half of its decoding
  (fixed in `bc5-mount`, no gain on its own) and ran the reads serially (fixed behind a knob:
  −2 s).
- About 9 s remain for ~1.75 GB.
- Next, in order of effort:
  - build flags for `bc5-mount` (oozextract's `x86_sse`, LTO, `target-cpu`);
  - pre-decoding the recorded start-up set before the title starts;
  - a persistent on-disk cache of decoded start-up blocks.
- The menu-navigation fault needs its own experiment.
