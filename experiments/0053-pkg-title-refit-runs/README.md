# 0053 — the second title's tree refit runs: the CP check plus a wait for the tree copies

**Question.** With the CP checking indirect arguments (experiment 0052) the second title builds
its trees' leaf lists, and the refit (0x909939900) ran half a million times, then hung on trees
whose lists were complete. Why, and does it stop hanging?

**Setup.** The refit's code (disassembly kept private) refits bottom-up: one group of four threads
per leaf node; each `buffer_atomic_sub`s the number of its finished children from its parent's
counter (low 3 bits: children left; bits 3–29: the parent's index; 30–31: the slot in it) and the
last one to arrive unions the children's bounds into the parent, restores the counter
(`buffer_atomic_or`) and climbs on, until the root. The counters and nodes lie inside the tree,
which the same compute buffer copies into place every frame with `DMA_DATA` without `CP_SYNC`
(experiment 0050). If the refit starts while that copy is still under way, it reads counters and
nodes half copied and climbs along wrong parents; with the lists empty (0050, run 185) the copy
did not matter, as the refit hung earlier.

Settings: `BC5_DIRECT_GPU_CHECK=1` and `BC5_DIRECT_DMA_SYNC=1` (backend
`FilterOptions::dma_sync_before_dispatch` of 0050: a zero-byte `DMA_DATA` with `CP_SYNC` before
the first dispatch after an unsynced `DMA_DATA`), the refit not skipped (`MEC_SKIP_PGM=0`). Backend
change after run 237: those waits also go into IBs with their own `COND_EXEC`, whose counts grow
around them (`indirect_check::insert_before`; before, such IBs got none); `ctest` 36 of 36. The
launchers `run-pkg.sh` and `play-pkg.sh` (copies here) now set both and no longer skip the refit
(`GPU_CHECK=0` in `run-pkg.sh` restores the old settings). Runs 233–238, 2026-10-12 06:06–06:45.
Raw output in `raw/`.

**Result.**

| Run | Length | Faults | Failed submissions | Refit dispatches | fps from 250 s | 3D from |
|---|---|---|---|---|---|---|
| 233 | 300 s | none | 0 | 2,075,486 | 18.3 | 70 s |
| 234 | 300 s | none | 0 | 2,187,376 | 18.3 | 65 s |
| 235 | 300 s | none | 0 | 2,113,756 | 18.4 | 70 s |
| 236 | 300 s | none | 0 | 2,130,662 | 19.1 | 45 s |
| 237 | 300 s | none | 0 | 2,090,920 | 18.9 | 45 s |
| 238 (launcher defaults, new backend) | 600 s | none | 0 | 5,482,959 | 18.3 | 70 s |

Before (experiment 0052): without the copy wait the refit hung in every run (225, 227, 228, after
66–152 s); with the refit skipped five of six runs reached 300 s, the sixth stopping on a heap
fault with a junk top byte. In these six runs no fault of any kind occurred.

**Verdict.** Passed. The refit hung for two reasons, both outside it: its leaf lists were built by
dispatches the host dropped on stale arguments (0050, fixed by the CP check of 0052), and it
started before the CP DMA copy of its tree had finished. With both fixed it runs in every frame,
six runs out of six end clean, and the frame rate is unchanged (18–19 fps; the refit's cost is
not visible at this rate). The launchers now run the second title this way.
