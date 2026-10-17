# 0156 — The second title's "Sony Interactive Entertainment presents" card at a few fps: three host stalls in its loading

**Question.** The maintainer reports the second title's first intro movie ("Sony Interactive
Entertainment presents") at a few fps while the next one (the bumper that ends with the PlayStation
logo) runs at its 30 fps. Where does the time go during the first one, and is the cause the host's?

**Setup.**
- BC-250 dev box, 2026-10-17 23:16 to 2026-10-18 00:27, unattended (the box shared with the
  menu-artefact session's runs 671–672; only one emulator at a time). Kernel 7.2.4-ogc3.1, Mesa
  26.2.3, libdrm 2.4.134 (F13).
- The second title from its package with the play shortcut's settings and the journal + frame
  profile (`play-pkg-log.sh`: `BC5_DIRECT_TIMING=1 BC5_DIRECT_FRAME_PROFILE=1`), intro only, no
  input, killed by a watchdog after 40–80 s; screenshots every 3 s (private, `shots7NN`).
- KytyPlus f266548 with patch 0001. Builds: 23:46 (A), 23:56 (A–C), 00:16 (A–D), 00:25 (A–E), the
  changes listed under Result 4.
- Runs (`~/bc5-work/run7NN.sh`, captures `~/bc5-data/captures/play-<date>/gc/direct.log`):
  - 700 baseline; 701 gdb backtraces of every thread at t 4, 7, 9, 11, 13 s; 702 `KYTY_BC5_AMM_TRACE=1`
    (the APR command buffers, reads, maps, waits with monotonic stamps); 704 a 50 Hz `/proc`
    sampler of game-main and the Render Thread (state, wchan, syscall) and all threads at 2 Hz;
  - 706 (A), 707 (A, trace), 708 (A; gdb of every thread at 5.9, 8.8, 11.2 s), 709 (A–C), 711
    (A–C with the learned pass instrumented), 712 (A–D), 713 (A–E). 703 and 705 did not run
    (no strace on the box; the box busy); 710 was a trace run of A–C.
- Tools: `gdbsample701.sh` / `gdball705.sh` (back-to-back `gdb -batch -p`), `procsample704.sh`,
  `sample700.sh` (per-thread CPU ticks each 0.5 s), the title's text segment dumped by experiment
  0115 for the disassembly.
- Raw (`raw/`): `run7NN-frames.txt` (frames per second of the journal, t 2–16 s, with the frame
  profile's means), `apr-batches-run702.txt`, `threads-run701.txt`, `stall-run704.txt`,
  `learned-run711.txt`.

**Result.**

1. **The slow "movie" is a static card shown while the title loads.** Screenshots: the card is on
   screen from t≈3 s to t≈15 s (run 700); the Bink bumper (the title's `BinkAsy0/1` threads
   appear then) starts at t≈16–18 s and the frame profile locks at 33.3 ms from t≈14 s. During
   the card the GPU is busy 5–18 ms per frame and the Render Thread spins in the loop at
   0x903f37960 of F166 (state word 1 → try a job → `pause` ×20) at 80–99 % of a core. Frames
   are produced when the loader's steps complete: 21 frames in t 4–9 s, the longest 1.45 s.
2. **The loading waited on the host, not on I/O or CPU.** The APR trace (run 702): the read
   batches sum to 2.8 s of the first 33 s (545 MiB); the rest are gaps of 0.5–3.4 s in which a
   submission waits on a completion counter (0x90adf7f98, op "reached") and some sixty queue
   behind it, while the CPU and GPU idle. What held the title (gdb and the sampler):
   - **APR execution on the title's threads.** Every submission ran its reads on the submitting
     thread, and the parked ones on whichever thread next submitted an AMM map. The title's
     "Archive Asset IO" thread sat in `RunAprReadsInParallel` (seven helper threads in fseek/fread
     on the mount) holding the title's archive lock; game-main waited on that lock, or executed
     batches itself (`read()` on the FUSE files in D state, `folio_wait_bit_common`,
     `request_wait_answer`, 0.5 s stretches), or waited 1.5 s on the host's memory-operation mutex.
   - **A Vulkan flush per guest map.** At every attach (run 708: 5.9, 8.8, 11.2 s) the archive
     thread was in `KernelBatchMap2 → KernelMapDirectMemory → UnmapMemory → SendCommandSync`: a
     synchronous round trip to the kyty-gpu thread with `FinishCurrent` (a Vulkan submit and fence
     wait) and `WaitPriorityOperations`, for each of the ~5,700 small AMM pages the title maps
     while it loads, from the thread holding the archive lock.
   - **The learned-window pass rebuilt the views per window.** `learned_apply` runs on every layout
     change on the ring and render threads; its 95 `map_window` calls each asked `direct_views`,
     and with the title mapping a page a millisecond every call found a new generation: 191
     rebuilds of the 7,000 views and 20–65 ms per pass (run 711: 90 passes, 6.0 s, 11,424
     rebuilds in the first six seconds). The timing split's "learned" bucket showed it as 1.9 s
     per 128 submissions.
3. **Not the cause:** bc5-mount's decoding (its workers idle in the gaps; the disk cache of 0113
   serves the start-up set), the Bink decoder (not running yet), shader compilation (none in
   direct mode), memory pressure (no page-allocation stalls in the kernel log; the D-state waits
   were FUSE reads), the GPU (idle).
4. **Host changes** (patch 0001, generic, no title check):
   - A. `libAmpr.cpp`: APR command buffers run asynchronously, one host worker per priority
     queue (`bc5-apr-q<n>`) running that queue in order with the waits polled as before; a
     submit enqueues and returns, as the console's engine does. `WaitCommandBuffer` /
     `AmmWaitCommandBufferCompletion` block until the submission has run (a done flag and
     condition variable in the submission table); the result buffer is written on completion.
     Map-only (AMM) submissions still run at once. `KYTY_BC5_APR_SYNC=1` restores the old path.
   - B. `gpuResourceManager.cpp`: in direct mode `UnmapMemory` no longer flushes the Vulkan
     scheduler per guest map; the caches flush themselves when they hold something in the range
     (`TextureCache::UnmapMemory`, `BufferCache::UnmapMemory`). The round trip to the GPU thread
     stays, so the bookkeeping order is unchanged.
   - C. `bc5LleAgc.cpp`, `scratch_fill`: the holes of a window come from one pass over the
     mappings instead of cutting the window by each mapping in turn (quadratic).
   - D. `learned_apply` pins the direct views for its pass (`t_pinned_views`); a view that
     appears meanwhile is covered by the next pass.
   - E. The pass keeps its mapping list sorted (`have_insert`), so `scratch_fill` needs no sort
     per window. The pass journals itself when it takes over 5 ms (`learned apply: ...`), and a
     call over 20 ms (`learned_apply took ...`).

   | run | host | frames in t 4–9 s | frames in t 4–11 s | steady 30 fps from | longest frame, t 3–14 s |
   |---|---|---|---|---|---|
   | 700 | before | 21 | 38 | 14 s | 1.45 s |
   | 702 (trace) | before | 7 | 13 | 15 s | 1.83 s |
   | 706 | A | 26 | 64 | 12 s | 1.64 s |
   | 707 (trace) | A | 43 | 86 | 11 s | 0.57 s |
   | 709 | A–C | 55 | 115 | 10 s | 0.57 s |
   | 711 | A–C | 58 | 117 | 10 s | 0.41 s |
   | 712 | A–D | 83 | 142 | 10 s | 0.82 s |
   | 713 | A–E | 86 | 145 | 10 s | 0.47 s |

   With A–E the card lasts from t≈3 s to t≈9–10 s (screenshots: the bumper at +12 s instead of
   +18 s) and the menus follow 4 s earlier. In run 713 the frame profile's "hints" (the import of
   the first render targets, 50 MiB of HTILE among them) still costs 70–100 ms a frame at t 5 s,
   and the learned pass 2.0 s in 151 calls (its per-window scans, 449 rebuilds left).

**Verdict.** The first "movie" is the title's loading card, and its few fps were the host's: the
title's threads were held inside APR reads, inside a Vulkan flush per map, and behind a views
rebuild per learned window, all answered at once on the console. With the three removed the card
delivers four times the frames (21 → 86 in its first six seconds, longest frame 1.45 → 0.47 s)
and ends four seconds sooner; the title paces the rest itself. Open: the learned pass (2 s), the
full syncs with 7,000 views while the title maps pages, and the hint imports; whether the console
plays the card at a steady frame rate is unknown.
