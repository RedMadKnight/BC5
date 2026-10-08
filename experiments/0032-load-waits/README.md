# 0032 — what the level load waits on

**Question.** Experiment 0030 showed the first level's load (about 15 s in the maintainer's
play) keeps no thread busy. What does it wait on, and is the host's own file server the
pace?

**Setup.** BC-250, 8C/16T, the track-B host (patch 0001 at this commit, which names the
host's own threads: `kyty-gpu`, `kyty-present`, `kyty-cmdsched`, `kyty-pipeline`,
`bc5-ring`, `bc5-cq<n>`, `bc5-labelwatch`, `bc5-autopress`, `bc5-keyhold`). Unattended
runs from an empty save with the autopress plan of run 131 (cross at 50 s and 58 s; run 138
added presses at 66–78 s meant to skip the opening cutscene, which they did not):

| Run | Length | Mount | Samplers |
|---|---|---|---|
| 137 | 600 s | the committed `bc5-mount` (readahead 128 KiB) | `thread-sampler.py` (0030) and `wait-sampler.py`: every 0.2 s each thread's state, `wchan` and blocked syscall from `/proc`, for the emulator and for the `bc5-mount` process |
| 138 | 420 s | same | same |
| 139 | 150 s | `bc5-mount` asking the kernel for 1 MiB readahead and `max_read=1048576` | the wait sampler, now with the FUSE process's `/proc/<pid>/io` counters per window |

Raw: `waits-run13[789].jsonl.gz`, `threads-run137.jsonl`, `wait-sampler.py`, `analyse-waits.py`.

**Result.**

In an unattended run the level load is not exposed: it runs from the second press (58 s)
for about 24–26 s while the in-engine opening cutscene plays, and the game reaches the
desert (screenshot at 568 s of run 137) without a visible pause. The maintainer skips the
cutscene, which is why their play showed a 15 s wait. The window itself, the same in all
three runs:

| | |
|---|---|
| `bc5-mount` (one thread) | 48–81 % of a core for 24 s; when not running, in `fuse_dev_do_read` (waiting for the next request) 20 %, in `pread64` on the container 6 % |
| served through FUSE (run 139) | 150–360 MB/s logical, 50–80 MB/s read from the container: about 5.5 GB for the level |
| `GfxTextureStream` | `D read` in `folio_wait_bit_common` 40 % (a page read through FUSE in flight), `futex` 38 %, running 16 % |
| `RoomLoad_ATQT`, `OdxAsyncLoader`, `ProductNextLoad` | `futex` 76–88 %, `D read` 6–18 %, running 4–25 %; each busy in turn, not together |
| the game's other threads | DrawThread and `kyty-gpu` at a third of a core each, 11 `tbb_thead` idle in `futex` |
| the emulator in all | 328 % of 1600 % |

1 MiB readahead and 1 MiB requests (run 139) changed nothing: the same 24 s window, the
same `bc5-mount` share.

Outside the load: `kyty-gpu` (the host's GPU thread) is one of the two host threads of
0030 at 26–31 %, blocked in `futex` 70 % of the time; the other, still unnamed (the thread
created just before `bc5-ring`), sleeps in `clock_nanosleep` 47–77 %. The intro video's
decoder thread runs 85 % of a core. The FUSE process is idle outside loads.

**Verdict.** Passed as a measurement. The load is paced by the file path: one `bc5-mount`
thread serving every request in turn at about 230 MB/s logical, and the game's loaders
waiting on it (page reads in `D`) or on each other (`futex`), with no thread near a full
core. Bigger requests do not help, so the cost is per request, not per byte: the FUSE round
trip and the single-threaded server. The next lever is a multi-threaded FUSE session (the
`fuser` 0.15 session is single-threaded) or a reader that decodes ahead along a file; both
are `bc5-mount` work, none is the game's. In the maintainer's play the exposed part is about
15 s of the 24; hiding it fully would need the cutscene left playing.
