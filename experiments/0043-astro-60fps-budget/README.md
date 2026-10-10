# 0043 — where ASTRO BOT's 18 ms frame goes, against 16.7

**Question.** The plan for 60 fps in ASTRO BOT (approved by the maintainer 2026-10-10) starts with
measurements: how much of a frame is the GPU working, on what, at which clock, with how many CUs
for graphics, and does the kind of memory the game's data sits in cost bandwidth?

**Setup.** Dev box as in 0042; governor `cyan-skillfish-governor-smu` with its configured range of
1850–2000 MHz (its log: allowed range 500..=2000). Tools, all new here:

- `backend/experiments/dispatch-min`: `--dst vram|gtt|gtt-uswc|udmabuf` (the destination as a
  VRAM BO, a GTT BO, a GTT BO with `AMDGPU_GEM_CREATE_CPU_GTT_USWC`, or a memfd imported as eight
  32 MiB udmabufs the way the direct path imports the game's memory, ADR 0006) and `--print N`.
- `rmw-probe.s`: each thread loads its 16-byte record, ORs the value in and stores it.
- `clock-probe.s`: reads `s_memtime` and `s_memrealtime` around an ALU loop; the shader clock is
  their ratio times `gpu_counter_freq` (100,000 kHz from `AMDGPU_INFO_DEV_INFO`).
- `gpu-timeline.py`: from a journal with `BC5_DIRECT_TIMING=1` and `BC5_DIRECT_FRAME_PROFILE=1`,
  the GPU's busy and idle time per frame. Jobs run in order on the one GFX ring, so a job starts
  when it was queued (done time minus fence time) or when the previous one ended. Busy time
  includes waits the CP does inside a job.
- `clock-sampler.sh` (hwmon `freq1_input`) and `gpu-metrics.py` (`gpu_metrics` v2.2): read-only.

ASTRO BOT runs 153–156 as `run151.sh` (unattended, autopress to the first level's gameplay,
420 s), measured at 380–418 s: run 154 as is, run 155 with `BC5_DIRECT_CU_MASK=000f03ff`, run 156
with `000f00ff` (the mask is ANDed into the graphics stages' `CU_EN`, bits 15:0, and into the
compute masks). 2026-10-10 00:25–01:05. Raw output in `raw/`.

**Result.**

1. **The first level is bound by the GPU.** Runs 153 and 154, 2,039 and 2,042 frames:

   | Per frame | Median | p90 |
   |---|---|---|
   | frame | 18.0 ms | 19.0 ms |
   | GPU busy | 17.1 ms | 18.1 ms |
   | GPU idle | 1.1 ms | 3.3 ms |
   | of the busy time: graphics buffers (DCB) | 11.9–12.1 ms | |
   | compute buffers (ACB) | 4.3–4.4 ms | |
   | constant-engine and other jobs | 0.6 ms | |

   About 24 jobs a frame. Idle time comes as gaps before a compute buffer (0.55 ms a frame,
   median gap 3.35 ms, in about one frame in seven) and before a graphics buffer (0.50 ms a frame,
   median 1.14 ms).
2. **The kind of memory makes no difference.** 256 MiB, 24 runs each, medians:

   | Destination | Write | Read and write |
   |---|---|---|
   | VRAM (the 512 MiB carve-out) | 0.640–0.646 ms (416–420 GB/s) | 1.380 ms |
   | GTT | 0.649–0.650 ms | 1.362 ms |
   | GTT, USWC | 0.639–0.644 ms | 1.379 ms |
   | udmabuf import, as the game's memory | 0.649–0.658 ms | 1.390–1.395 ms |

   Within 3 %; the board's GDDR6 peak is 448 GB/s.
3. **Graphics already uses every CU.** `CU_EN` bits 10–15 add nothing; bits 8–9 do:

   | `CU_EN` | DCB per frame | ACB per frame | Frame |
   |---|---|---|---|
   | 0xffff (run 154) | 12.11 ms | 4.34 ms | 18 ms |
   | 0x03ff (run 155) | 11.96 ms | 4.64 ms | 18–19 ms |
   | 0x00ff (run 156) | 13.94 ms | 4.53 ms | 20 ms |

   The same masks cut compute from 20 to 14 and 12 units per shader engine and the compute
   buffers slowed by only 4–7 %: their 4.3 ms is mostly not CU throughput.
4. **The shader clock is at the governor's ceiling under load:** 2,005 MHz over 300 and 3,000
   back-to-back runs of the clock probe, 1,855 MHz for a single run from idle (the floor). The
   hwmon `freq1_input` (60–77 MHz during play) and the clock fields of `gpu_metrics` (2–13 MHz
   current at 98 % activity) do not report it on this board; `gpu_metrics` activity and
   temperature do (98 %, 55–71 °C).
5. **A job costs 18–28 µs from submit to fence** (a 1 KiB dispatch, 200 runs): at 24 jobs a frame,
   at most about 0.5 ms.

**Verdict.** Measured. The 16.7 ms target is 1.3 ms below the first level's 18 ms frame, and the
GPU is busy for 17.1 ms of it. Not levers: the memory kind, the graphics CU mask, the clock
within the governor's range. Levers, in order: (a) the 4.3 ms of compute buffers, which on the
console run beside graphics on compute queues (the BC-250's compute rings take the machine down,
F31) and here are mostly not compute-bound, so their barriers and cache operations are the
suspects; (b) the 1.1 ms of idle GPU; (c) the per-job overhead, at most 0.5 ms. The shader clock
is the PS5's 2.23 GHz × 36 CUs against 2.0 GHz × 40 CUs here, the same product.
