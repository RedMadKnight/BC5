# 0044 — what ASTRO BOT's compute buffers spend their 4.3 ms on, and whether the L2 writebacks can go

**Question.** Experiment 0043 found that ASTRO BOT's compute buffers take 4.3 ms of a frame's 17.1 ms
of GPU time on the single ring, and that they barely slow down with a third fewer compute units.
Which ordering and cache packets do they carry, and is the L2 writeback after each dispatch,
needed between the console's queues only for CPU visibility, a cost the host can drop?

**Setup.** As in 0043 (`run151.sh` recipe, 420 s, the first level's gameplay at 380–418 s). New in
the host: `BC5_DIRECT_PKT_STATS=1` counts the packets of every buffer as the game wrote it, per
kind of buffer, and reports every 10 s (`pkt stats`); `BC5_DIRECT_GCR_CLEAR=<hex>[:acb|:dcb]` sets
the new backend option `FilterOptions::gcr_clear`, which clears those `GCR_CNTL` bits in every
`ACQUIRE_MEM` (dword 7 on gfx10; field layout in `tools/bc5-agc/regdb/pkt3.json`, from Mesa, MIT;
`GL2_WB` is bit 15; unit test in `backend/tests/policy_test.cpp`, `ctest` 33 of 33). Run 157 with the
counts, run 158 with `BC5_DIRECT_GCR_CLEAR=8000:acb`, run 159 as is. 2026-10-10 05:51–06:15. Raw
output in `raw/`.

**Result.**

1. **Per frame of the first level** (run 157, 400–410 s, 533 frames), compute buffers: 49
   `DISPATCH_DIRECT` and 3 `DISPATCH_INDIRECT`, 56 `EVENT_WRITE` CS_PARTIAL_FLUSH (event 7), 49
   `ACQUIRE_MEM` with `GCR_CNTL` 0x08000 (`GL2_WB` alone: write the whole L2 back), 3 with 0x08380
   and 4 with 0x0c3a1 (write back and invalidate L2, invalidate the others), 63 `RELEASE_MEM`
   CS_DONE (event 40), 8 `WAIT_REG_MEM64`. Every compute dispatch is followed by a partial flush and
   an L2 writeback. Graphics buffers: 49 dispatches, 677 `DRAW_INDEX_OFFSET_2` and 81 other draws,
   102 `ACQUIRE_MEM` 0x09000 (`GL2_WB` with `GL2_RANGE` 2), 104 with invalidations only
   (0x00220–0x00380), 28 that write back and invalidate L2, 113 `WAIT_REG_MEM` and 32
   `WAIT_REG_MEM64`.
2. **Without the compute buffers' L2 writebacks the frame gets slower, not faster:**

   | Run | Setting | Frames 380–418 s | Frame | GPU busy | ACB | ACB pieces (`acb-state`) | GPU idle |
   |---|---|---|---|---|---|---|---|
   | 159 | as is | 2,060 | 18 ms | 17.1 ms | 4.57 ms | 0.24 ms | 1.1 ms |
   | 158 | `GL2_WB` cleared in compute buffers | 1,578 | 24 ms | 18.0 ms | 3.05 ms | 2.75 ms | 6.2 ms |

   The compute buffers themselves shrink by 1.5 ms, but the host now splits them at their
   cross-queue waits ten times as much and the GPU idles 6 ms a frame: labels and data the GPU
   writes reach the CPU only once L2 is written back, so the host's waits on the CPU last longer.
   The picture stayed right (screenshot at 409 s, sent to the maintainer only). Run 159 repeats
   run 154 (0043) within 0.2 ms, so the difference is the setting, not the run.

**Verdict.** Failed as a lever, kept as an option: the L2 writebacks are what makes the GPU's
results visible to the host and the game on this board, and dropping them costs more than it
saves. `BC5_DIRECT_GCR_CLEAR` stays off; `BC5_DIRECT_PKT_STATS` stays as a diagnostic. With the
compute buffers' 4.3 ms serialised (F31) and their barriers needed, the first level's GPU time
(17.1 ms) stays above 16.7 ms; what is left on the host's side is the 1.1 ms of idle GPU and the
per-job overhead.
