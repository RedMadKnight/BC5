# 0066 — larger direct-memory imports: fewer BOs per CS

**Question.** HANDOFF F124: the CS ioctls cost the game's thread 1.5 ms a frame because a full BO
list holds ~228 BOs. 144 of them are direct-memory imports, merged up to udmabuf's limit of
64 MiB. With a larger limit, does the cost go down?

**Setup.**
- The maintainer raised the limit at run time (2026-10-13, ~13:00):
  `/sys/module/udmabuf/parameters/size_limit_mb` = 1024. The host reads it at start (`kDMaxBo`).
- ASTRO BOT with the settings of run 282, the scene and window of 0061.
- Run 292: 64 MiB, before. Runs 294 and 295: 1024 MiB.

Raw data is in `raw/runs-292-295.txt`.

**Result 1, run 294.** With 1024 MiB and the host unchanged, the BO count went the wrong way:
- 1,854 direct-memory BOs of mostly 2 MiB and 1,942 GPU mappings;
- the galaxy map at 29–36 fps instead of 60.

The maintainer's own launcher showed the same in a test just before. The merge step (exp. 0022)
collects a run of adjacent imports up to `kDMaxBo` and skips the run if it exceeds its budget of
256 MiB per pass. At 64 MiB every run fit the budget. At 1024 MiB the runs grow past it, and
nothing was merged any more.

**Change (patch 0001).** A merge run is also cut at the remaining budget
(`std::min(kDMaxBo, budget)`). Imports now merge into BOs of up to 256 MiB.

**Result 2, run 295** (1024 MiB and the fix):

| | run 292 (64 MiB) | run 295 (1024 MiB, fix) |
|---|---|---|
| direct-memory BOs / GPU mappings | 144 / 238 | 42 / 137 |
| BOs in a full list | 228 | 123 |
| CS of a full list | 0.29–0.38 ms | 0.15–0.20 ms |
| CS ioctls a frame | 1.5 ms | 1.0 ms |
| fps (later level) | 44.2 | **45.9** |
| frame, mean | 22.6 ms | 21.8 ms |
| timeouts, waits given up | 0, 0 | 0, 0 |

**Verdict.** Passed, with the fix. The larger limit halves the BOs of a full list and takes 0.5 ms
off the game's thread a frame: +3.8% in the later level. Without the fix the larger limit is
harmful; the fix is needed for any limit above 256 MiB.

The value set through `/sys` lasts until the next reboot; the host adapts to whatever it finds.
To keep it, the maintainer can add the kernel argument `udmabuf.size_limit_mb=1024`.
