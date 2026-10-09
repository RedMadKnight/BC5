# 0042 — the second title's GPU reads heap pages the host never handed to the GPU

**Question.** Experiment 0041 placed the second title's stops in guest holes of
0x12b0000000–0x12d0000000. What does the guest map there, and when?

**Setup.** As in 0041. New in the host: `KYTY_BC5_RANGE_WATCH=lo:hi` (hex) writes every edit of
the guest's ranges that overlaps `[lo, hi)` to stderr with the monotonic clock (add, remove,
protect, release and consume of reservations; `kernel/memory.cpp`, `VirtualRanges`), and the
direct path's journal prints its own zero on that clock once (`bc5 clock`). Runs 100–103 watched
0x12a0000000–0x12e0000000; runs 104–112 imported more of the title's heaps in full from the start
(`BC5_DIRECT_EAGER_NAMES`, below). 2026-10-09 23:14 – 2026-10-10 00:12. The launchers here
(`play-pkg.sh`, `pkg-series.sh`, `run-pkg.sh`) are the ones after this experiment.

**Result.**

1. **The layout there never changes.** The guest maps three blocks at start and nothing else
   in the window for the whole run: 0x1210000000+0xab000000 (2736 MiB,
   `CommitIABufferAllocator`), 0x12c0000000+0x4600000 (70 MiB, `RenderAlloc`) and, at 1.8 s,
   0x12d0000000+0xc000000 (192 MiB, `Physics`). The faults of the day lie in the holes after the
   first two (0x12bb004000, 0x12bc001000, 0x12c4610000, 0x12c8003000, 0x12cc002000), from 16 KiB
   to 122 MiB past their ends, and run 102's (0x12d0410000) inside the third.
2. **The host imports a direct-memory page for the GPU only once the CPU has written it**
   (ADR 0006: `SEEK_DATA` over the memfd), unless the heap's name is in `BC5_DIRECT_EAGER_NAMES`.
   A heap the GPU reads or writes first is therefore missing on the GPU: at 42 s of run 102,
   `RenderAlloc` had 0 of 70 MiB imported, `Physics` 12 of 192, `Decal Job Scheduler` 0 of 12,
   `VisualEffectInstanceHeap` 4 of 24, `DynamicHeap` 48 of 328. On the console such a page is
   simply memory.
3. **Importing those heaps in full** (`RenderAlloc`, `Physics`, `Physics query allocator`,
   `Decal Job Scheduler`, `VisualEffectInstanceHeap`, `DynamicHeap`, `DynamicHeap Small`,
   `ComponentHeap`, `ComponentHeap Small`, `MaterialHeap`, `DDLHeap`, besides the six names of
   0037): 9.7 GiB imported (GTT 10.2 of 13 GiB), at least 2.7 GiB of RAM left, 21.7–21.8 fps from
   250 s as before.

| Runs | Heaps imported in full | Runs | Ended clean | Recovered from a fault | Stopped |
|---|---|---|---|---|---|
| 100–103 | the six of 0037 | 4 | 2 | 1 (103, wild address) | 1 (102, `Physics` page, then the title's null read at 0x9844) |
| 104–112 | the extended list | 9 | 5 | 2 (104: 0x88_1296612000; 109: wild) | 2 (110 at 196 s, 112 at 221 s, both wild addresses) |

**Verdict.** Passed for the class it targets: no fault inside a guest heap or in the holes after
`CommitIABufferAllocator` and `RenderAlloc` in nine runs with the extended list (the learned
fault file already gave 0x12c6000000–0x12d4000000 a zero buffer by then), and none of the
second title's heaps is now invisible to the GPU. Not a cure for the stops: they remain about one
run in four, now all at wild addresses or heap addresses with a junk top byte (the latter
cluster at 0x1296xxxxxx inside `CommitIABufferAllocator`). The extended list is the default of
the second title's launchers.
