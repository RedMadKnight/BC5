# 0252 — Reusing the tiler's scratch buffers removes the per-flip Vulkan allocation: 3 buffers for ~10,000 requests instead of one each

**Question.** The host's worst frame stalls on the bench are KytyPlus's flip preparation. It re-uploads the display
buffer through a new dedicated Vulkan scratch buffer at every flip, and `vkAllocateMemory` holds the kyty-gpu thread
when the box is short of memory (exp 0249, F308). Does reusing the scratch remove the allocations? Does it cost
anything?

**Setup.**
- *The change* (`patch_0252.py`, applied to a copy of the shared tree's
  `src/graphics/host_gpu/renderer/image/tiler.cpp`; the header, and so the `TileManager` layout, is unchanged).
  `KYTY_BC5_TILER_POOL=1` switches it on; it is off by default.
  - `TileManager::DeferDestroy` returns the scratch to a small pool instead of destroying it. It does so in the
    same `CommandScheduler::DeferOperation` as before, which runs when the scratch's tick is free on the GPU
    (`commandScheduler.cpp:260–292` at KytyPlus f266548), the very moment the original code destroyed it. So a
    buffer still used by an in-flight upload is never handed out again.
  - Every `AllocateScratch` caller defers the destroy right after allocating, within the tick (`tiler.cpp:385`,
    `419`, `431`, `705` at f266548). `AllocateScratch` hands out the smallest free buffer that fits, else creates
    one rounded up to 1 MiB. The pool holds at most 4 buffers and 128 MiB, dropping the smallest first, and is
    emptied in `~TileManager`.
  - A counter in both modes prints one stderr line per 1,024 requests: requests, new buffers, MiB created,
    reused, free.
- *The build* (`setup0252.sh`, `build0252.py` = the TCP session's `build0226.py` with the unit changed): one TU
  compiled with the shared build's flags (`ninja -t compdb -x`) and linked into `~/bc5-work/exp0252/kyty_emulator`
  from the shared objects. `~/src/KytyPlus` and the shared builds were not written. The build ran at 22:16. A
  rebuild at 22:22 added the counter for the pool-off mode, after `KYTY_BC5_VMA_TRACE=1` turned out to print
  nothing on the bench, where host logging is off.
- *The A/B* (2026-10-23 22:16–22:41, granted by the top session; the maintainer's yes in this session: "Tak,
  przygotuj poprawkę z ponownym użyciem bufora w TileManager i test A/B."):
  - four interleaved runs of exp 0249's lake bench on today's default (`BC5_DIRECT_FLAT_APERTURE=1
    BC5_DIRECT_AMM_PRT=1 BC5_DIRECT_SKIP_PGM=909974400`, TF ring on): E52O1, E52N1, E52O2, E52N2;
  - all on the private binary. OLD has the switch off (the shared code path; E52O1 ran the first build, without
    the counter) and NEW has `KYTY_BC5_TILER_POOL=1`;
  - the /proc thread sampler (`hoststate0252.py`) and the kernel stream ran in every run (`runarm0252.sh`,
    `xarm0252.sh`, `bench0252.sh`).
- Raw: `raw/ab-summary.txt`, `raw/stalls.txt`, `raw/frame-stats.txt`, `raw/bench-*.txt`, `raw/kernel-*.txt`,
  `raw/*-env.txt`.

**Result.**
- **No faults:** 0 kernel fault lines and 0 ring or fence timeouts in any run.
- **The allocations are gone** (`raw/ab-summary.txt`):

  | Run | Pool | Requests | New scratch buffers | Created | Flips | Gaps > 0.3 s | kyty-gpu ms per 0.1 s (periods > 50 ms) | PSI mem full ms per 0.1 s | Frozen view t 180–300 flips/s |
  |---|---|---|---|---|---|---|---|---|---|
  | E52O1 | off | (no counter) | (one per request) | — | 9,830 | 0 | 11.0 (0) | 4.4 | 28.9 |
  | E52N1 | on | 9,216+ | 3 | 96 MiB | 9,832 | 1 (t 83.6, loading) | 10.1 (0) | 3.1 | 29.0 |
  | E52O2 | off | 9,216+ | 9,216 | 200,018 MiB | 9,689 | 5 (one in the frozen view, 0.50 s) | 12.2 (9) | 5.5 | 28.1 |
  | E52N2 | on | 11,264+ | 3 | 96 MiB | 11,770 | 3 (t 5.4, 38.6, 240.5) | 8.9 (0) | 0.8 | not comparable |

  - With the pool off, every request is a new buffer: about 0.95 per flip, ~22 MiB on average, 195 GiB allocated
    and freed in E52O2's 300 s.
  - With it on, three 32-MiB buffers serve every request after the first few (99.97 % reused). The pool then holds
    96 MiB for good: three buffers, two of them free at any report. The pool-off path holds one or two transient
    32-MiB buffers instead.
- **The host's GPU thread works less and never runs flat out with the pool.** kyty-gpu averaged 10.1 and 8.9 ms of
  CPU per 0.1 s with the pool, 11.0 and 12.2 without. Only the pool-off E52O2 had periods over 50 ms (nine), and
  they came with its 0.50-s frozen-view stall at t 190.9.
- **Frame rate:** in the frozen view NEW1 ran 29.0 flips/s against 28.9 (O1) and 28.1 (O2).
  - E52N2 did not reach the frozen lake view: 40–44 flips/s from t 180, and shots with 0–3.6 % "patch" alternating
    between two values, so the camera was elsewhere. Its frame rate is not compared; its allocation counts and
    stall count are.
  - The memory state was mild in all four runs (PSI memory "full" 0.8–5.5 ms per 0.1 s, against 8–10 in the runs
    of exp 0249 that had the stalls). So the stall reduction shows only as OLD2's one stall and nine busy periods
    against none with the pool.

**Verdict.**
- Reusing the tiler scratch removes the per-flip dedicated Vulkan allocation entirely: 3 buffers for ~10,000
  requests, against one per request. That takes away the step exp 0249 caught holding kyty-gpu for 0.3–0.7 s under
  memory pressure. kyty-gpu's CPU is lower in both pool runs (10.1 and 8.9 ms per 0.1 s against 11.0 and 12.2;
  E52N2's scene differs). No fault, no frame-rate loss and no new stall appeared in two
  runs with the pool. The cost is 96 MiB of scratch held for good, instead of churned per flip.
- It qualifies under the maintainer's standing rule (a speed-up with no regression goes into use). **Integrated
  the same evening:** the maintainer approved it, and the top session rebuilt both shared builds at 22:44 with the
  pool on by default (`KYTY_BC5_TILER_POOL=0` turns it off; md5 of the normal build fd84c785, of the lean one
  cf5b3665; backups in `~/bc5-work/exp0252/integration/`). Patch 0001 was regenerated in commit 275c432 (tiler.cpp
  only).
- Open: why E52N2 missed the frozen view. Its load or Photo Mode steps went elsewhere; the bench's scripted route
  has done so before (exp 0211's R11C), and nothing in its journal or kernel log points to the pool.
- Not shown: the stall reduction under real memory pressure. That needs a run in a pressured state, or the
  maintainer's play, where exp 0249's stalls occurred. The 4-buffer / 128-MiB cap was not tuned; two buffers would
  likely do, as two stayed free.
