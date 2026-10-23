# 0249 — The kyty-gpu stalls are a fresh Vulkan allocation at every flip, slow when the box is short of memory

**Question.** Some bench runs have a series of 0.3–0.7-s frame stalls (exp 0247, F306). In them the host's kyty-gpu
thread (KytyPlus's `GpuState::ThreadRun`) runs flat out while the title's Render Thread spins and the GPU idles. What
does kyty-gpu do in those stretches?

**Setup.**
- *Offline (KytyPlus f266548, the base commit of the box's tree, read from the local clone
  `refs/Coder787-source_KytyPlus`; line numbers checked on the box's `~/src/KytyPlus` at 21:28, given as box/f266548
  where they differ):*
  - `GpuState::ThreadRun`: `graphicsRun.cpp:610/609`. It sleeps when idle (`m_work_available.Wait`, line 628/626),
    waits 100 ms when every queue front is blocked (line 651/649) and has no spin loop.
  - The per-flip work, from the title's VideoOutSubmitFlip through `SubmitFlipPreparation` (`videoOut.cpp:1743`) to
    `Process` (`case SubmissionType::FlipPreparation`, `graphicsRun.cpp:823`): `RunGarbageCollector`
    (`gpuResourceManager.cpp:89/79`), then `CommandProcessor::PrepareCpuFlip` (`graphicsRun.cpp:1777/1771`) →
    `VideoOutDriver::PrepareFlip` (`videoOut.cpp:1766`) → `FlipQueue::Prepare`.
  - Synchronous commands from title threads: `GpuResourceManager::UnmapMemory` (`gpuResourceManager.cpp:57/55`,
    `SendCommandSync` at 86/76) and `BufferCache::ReadMemory` (`bufferCache.cpp:340/320`).
  - The game waits on a display buffer's flip label. The host resets the label once the flip is presented, in its
    `bc5-fliplabel` thread (`bc5LleAgc.cpp:8835–8844`).
- *Runs:* 2026-10-23 21:28–21:47, granted by the top session; three runs E49R1–R3 of exp 0247's lake bench
  (`bench0249.sh`, `runarm0249.sh`, `xarm0249.sh`), all on today's default
  (`BC5_DIRECT_FLAT_APERTURE=1 BC5_DIRECT_AMM_PRT=1 BC5_DIRECT_SKIP_PGM=909974400`, TF ring on), with:
  - the /proc thread sampler (`hoststate0249.py`, a copy of exp 0247's);
  - `stackwatch0249.py` (here; exp 0247's watcher widened to Render Thread, game-main, the flip, ring and kyty*
    threads), which takes an `eu-stack` of the emulator only while kyty-gpu has run more than 240 of the last
    300 ms;
  - the kernel log streamed to the laptop. No traces.
- Analysis: exp 0247's `ana0247.py` for the gaps; the sampler's `v` lines (vmstat and PSI) for memory pressure. The
  0247 runs' sampler files are compared too.
- Raw: `raw/stacks-summary.txt` (frame names only: host-library addresses dropped, the title's frames shown as
  `<title code>`; the full samples stay on the laptop), `raw/memory-vs-kyty-gpu.txt`, `raw/stalls.txt`,
  `raw/frame-stats.txt`, `raw/bench-*.txt`, `raw/kernel-*.txt`, `raw/*-env.txt`.

**Result.**
- **No faults or timeouts** in any of the three runs.
- **The watcher caught the stall in R2.** R2 had two gaps of 0.55 s at t 286.6 and 291.2, each with the game thread
  outside the host for 0.52 s. The two samples, at 263 and 275 ms of kyty-gpu per 300 ms, fall inside them. Both
  have the same kyty-gpu stack: `PrepareCpuFlip` → `FlipQueue::Prepare` → `Presenter::PrepareFrame` →
  `TextureCache::UpdateImage` → `InitializeImage` → `UploadImage` → `TileManager::Detile` →
  `TileManager::AllocateScratch` → `vmaCreateBuffer` → VMA `AllocateDedicatedMemory` → `vkAllocateMemory` (in the
  driver).
  - The Render Thread is in the host's submit path (`Bc5LleKernel::Ioctl` → `Direct::submit_now`) in one sample
    and sleeping in `Bc5LleVideoOut::SubmitEopFlip` in the other. The presenter thread (kyty-present) sleeps
    meanwhile.
  - R1 and R3 had no such stretch over the threshold. R3's kyty-gpu exceeded 50 ms per 0.1 s in only six periods.
- **The allocation is made new at every flip.** To present, the host re-uploads the display buffer through the
  texture cache. `TileManager::AllocateScratch` creates a new buffer for every detile (`tiler.cpp:92–109` at f266548, one line
  later in the box's tree by the patch's include;
  `vmaCreateBuffer` with `VMA_MEMORY_USAGE_AUTO_PREFER_DEVICE`), and `DeferDestroy` frees it afterwards. The patch
  only adds a memory trace there. The launchers set `KYTY_BC5_VMA_BLOCK_MIB=16` (F47, to keep the host's GTT
  small), so VMA's block is 16 MiB. Both stacks show VMA taking the dedicated path (`AllocateDedicatedMemory`), which means one
  `vkAllocateMemory` per flip. That a full-HD display buffer's ~8.3-MB scratch crosses VMA's dedicated threshold
  because of the 16-MiB block is an inference (TODO(verify): VMA's rule, and the scratch size, through the
  patch's `VulkanTraceMemory` line "tiler scratch").
- **It is slow when the box is short of memory** (`raw/memory-vs-kyty-gpu.txt`):
  - In the 0.1-s periods where kyty-gpu ran over 50 ms, PSI memory "full" averaged 36 ms (E47A1), 33 ms (E49R2) and
    16 ms (E49R3) per period, against 8–10 ms over the same runs. MemAvailable fell to 1.2–1.6 GB from ~1.9.
  - Over whole runs, the three runs with kyty-gpu stretches had PSI memory "full" of 8.4–10.3 ms per period. The
    five without had 1.4–3.5. That is the run-to-run variance of F306: the box's memory state on that run.
- Frozen view: 28.6–28.7 flips/s in R1, 27.7–28.3 in R2 and R3 (`raw/frame-stats.txt`).

**Verdict.**
- The worst bench stalls (F306) are KytyPlus's per-flip presentation work. Every flip re-uploads the display buffer
  through a newly allocated Vulkan scratch buffer, which is a dedicated allocation under the launchers' 16-MiB VMA
  block. When the box is under memory pressure, `vkAllocateMemory` holds kyty-gpu for 0.3–0.7 s. The flip is then
  not prepared, the game's flip label stays set, the Render Thread waits, and the GPU idles. No title work and no
  compaction setting is involved.
- Fix candidates, for a next experiment with the maintainer's go (they touch the host's presentation path):
  - keep the tiler's scratch buffer across flips, reusing it when it is large enough;
  - give the tiler scratch its own VMA pool with a block that fits it, so it is not dedicated;
  - avoid the re-upload altogether: present from the display buffer the host already maps for the direct path.

  The first is the smallest change. Its check is an A/B under the same memory state, plus the trace's count of
  "tiler scratch" allocations per flip.
- Limits: one caught stall (two samples in one run); the scratch size and how often it is allocated per flip are
  inferred from the code and the stack, not traced.
