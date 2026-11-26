# D28: the expected work per submit on the first title's render thread (DrawThread), for perf record to confirm

**What run 8 measured.** perf stat, user space only, on boot aef3e9b1:

| | Old shared lean 05fd749d | New shared lean b0f856ed (bake 1c+1d) |
|---|---|---|
| DrawThread instructions | 106.3-106.6 G / 100 s | 110.0-110.7 G / 100 s (+3.8 %) |
| IPC | 1.41 | 1.43 |
| L1i misses | 0.75 / k instructions | 0.76 / k instructions |
| BC5's own threads (kyty-gpu, bc5-ring, kyty-present) | unchanged | unchanged |

So the extra work is content, on the guest thread that calls the host's submit path, `Direct::submit` (n1d/bc5LleAgc.cpp:10864). The submit path runs `submit_split` (:9420) and then the filter-option survey with its packet loop (:14720-15400). The backend's `Device::submit` runs on that same thread (direct.cpp :1250-1450).

**Before the bake**, the first title ran with the 28 rows unset: they were TITLE2 rows. The library words and APR_PARALLEL run on other threads (savedata, network, the APR reader pool), so they are not on this list.

**Order of the rows.** Most likely first, by the code: work per submit or per packet, scaled by how many of each packet the first title's dcbs carry. The rows are ordered by what each one makes the submit path do. The packet counts are unknown until perf record.

| Row (on in bake 1c) | Work per submit on DrawThread | Functions perf record should show (lean symbols) | Expected size |
|---|---|---|---|
| BC5_DIRECT_GPU_CHECK=1 | 1. `indirect_check::any_checked` walks every packet header of the job. 2. For a job with a checked packet (DISPATCH_INDIRECT; DRAW_INDIRECT/DRAW_INDEX_INDIRECT of 5 dwords), `indirect_check::apply` builds a new vector: the whole IB plus about 35-44 dwords per checked packet, and a `new_at` table of IB size + 1 when the IB has a COND_EXEC. It then moves that vector into `main_out`. 3. `indirect_check::patch` fills the flag addresses. 4. The flag area grows the scratch. (indirect_check.cpp:72-80, 100-337; direct.cpp:1402-1430) | `bc5::indirect_check::apply`, `any_checked`, `patch`, `std::vector<unsigned>::_M_realloc_insert` / `insert` under apply | **The largest candidate.** Every dcb with an indirect draw is copied and rebuilt. GC_NOCOPY only removes the copy for jobs with **no** checked packet. |
| BC5_DIRECT_INDIRECT_DRAWS=multi | 1. In the survey loop, every DRAW_INDIRECT, DRAW_INDEX_INDIRECT or multi-draw packet calls `chain_given_up_at` (:7457), which walks the chain's segments. 2. Draws are no longer dropped. Each 0x24/0x25 then reaches GPU_CHECK's apply (above). 3. The policy filter's fast path is kept, because the drop list is empty. | `chain_given_up_at` (likely inlined into `submit`), and apply via GPU_CHECK | Small on its own; it multiplies GPU_CHECK's apply work. Off, the draws are NOPs and none is checked. |
| BC5_DIRECT_DMA_SNAPSHOT=4096 | 1. The policy filter calls `snapshot` for every DMA_DATA source of 4096 bytes or more (direct.cpp:436-465). 2. `snap_place` scans this job's spans and every in-flight span (`snap_spans`, pruned in `snap_commit`). 3. A memcpy into the USWC ring follows. The normal journal: "54 sources copied (0 MiB)" in a 180 s run, so the copies themselves are small. | `Impl::snapshot`, `snap_place`, `snap_commit`, `memcpy` | Small: few sources and few bytes. |
| BC5_DIRECT_CS_PREFIX=1 | 1. For a dcb that gets no other prefix (no draws, under PREFIX_ALL=draws), `ib_has_dispatch0442` walks the packet headers (CS_SKIP). 2. When the dcb has a dispatch, `cs_inherit_at` walks to it and reads the LOAD_SH_REG_INDEX pair tables in guest memory, and `cs_prefix` builds SET_SH_REG runs from the tracker for a dcb that dispatches before it sets a program. (:7637, :9441) | `ib_has_dispatch0442`, `cs_inherit_at`, `cs_prefix` | Small to medium. It depends on how many draw-free dcbs with dispatches the first title sends. |
| BC5_DIRECT_LAZY_RELEASE=30,eager | It runs in `direct_sync_one` (:3745), called from submit: 1. A 50 ms gate (:3773). 2. A merge at least every 250 ms (:3797-3802). 3. Every 7.5 s, `lzr_pass` (:3076) runs `plan()` over every chunk (:3150-3166). 4. A cut forces a full mapping rebuild, `chain_flush` and `wait_idle(0)` (:3940-3963). | `direct_sync_one`, `lzr_pass`, `Lzr0401::plan`, the mapping rebuild | Periodic, not per submit. A cut is a spike, not a steady 3.8 %. Run 2's off-arm was the lowest, so this row is the least likely. |
| BC5_DIRECT_MEC_INDIRECT=1 | For a buffer whose DISPATCH_INDIRECT is in the compute (MEC) form, run on the GFX ring, the IB is rebuilt with GFX-form dispatches: the `mec_expand_ib` loop with an `old_to_new` table of IB size + 1, up to 64 attempts (:15269, :15383-15420). | `submit` (the `mec_expand_ib` block, inlined) | Only for compute buffers on the GFX ring. The first title's acbs: count unknown. |
| BC5_DIRECT_REMEMBER_UNMAPPED=1 | Only after a probe filter reports unmapped drops, which forces a sync: a walk of `memory_operands` over the IB (:14753-14765). | `bc5::policy::memory_operands` | Rare: only on a forced sync. |

**perf record**
- **The plan:** one run of the new lean, `perf record -e cycles:u -g --call-graph=fp` (or dwarf) on DrawThread's tid, for 60 s.
- **Symbols:** the lean binary must keep its symbols. If it is stripped, perf shows addresses only and needs the unstripped copy or a map file. Check with `file` before the run.
- **If apply is at the top:** a GPU_CHECK cost fix would keep the original buffer and build only the instrumented spans, or insert in place with `insert_before` and a precomputed size (one allocation, no full copy). The behaviour stays the same.
- **After that,** run the off-word arms only for the rows perf record names.
