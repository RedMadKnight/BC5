# 0050 — why the second title's tree refit never finished, and running it where it can

**Question.** The second title's compute program 0x909939900, skipped since experiment 0039 because
it did not finish on the single ring, refits the bounding-volume trees its ray tracing walks
(experiment 0049). The maintainer asked for it to be fixed. Why does it not finish?

**Setup.** As in 0049. Each run watched; the ones that run the program stopped at the fourth
GPU timeout. New in the host (patch 0001), all off by default:

- `BC5_DIRECT_WATCH_PGM=<hex>`: journals the program's dispatches (initiator, indirect arguments
  at submit and when the job ends, the 36 dwords at its `USER_DATA_4/5` pointer), and after a job
  checks its tree on the CPU (`refit check`), with the source of a `DMA_DATA` that copied it in.
- `BC5_DIRECT_SPLIT_AT_PGM=<hex>`: each dispatch of that program goes as a job of its own (state
  replayed in the same job), the rest of the buffer before and after it as further jobs.
- `BC5_DIRECT_TRUST_PGM=<hex list>`, `BC5_DIRECT_TRUST_DISPATCH=acb`: trust the arguments of
  those programs' / of compute buffers' indirect dispatches; trusted arguments are checked again
  in a buffer one of whose CPU-side waits was given up. The journal's indirect lines name the
  program, now also when `LOAD_SH_REG_INDEX` tables set it.
- `BC5_DIRECT_REFIT_GUARD=<hex>`: run that program's dispatches only on trees whose leaf lists
  are complete (checked on the CPU, the copy's source for a copied tree; verdicts kept 1 s).
- Backend `FilterOptions::dma_sync_before_dispatch` (`BC5_DIRECT_DMA_SYNC=1`, a CP DMA wait
  before the first dispatch after an unsynced `DMA_DATA`) and `pfp_sync_indirect`
  (`BC5_DIRECT_PFP_SYNC=1`, `PFP_SYNC_ME` before every `DISPATCH_INDIRECT`); `ctest` 33 of 33.

The program's layout was read from its disassembly (kept private): `s[4:5]` points at a tree
header; header+0x48 is the offset of a dword index buffer of header[0x80]/4 entries, one per four
threads; 64-byte nodes start at the header, four children each; a child with its low three bits
clear starts a list of 8-byte entries at byte offset child & ~7, walked until an entry's second
dword is negative; out of range a buffer load returns zeros, so a list without that end never
ends. Runs 181–216, 2026-10-11 21:16–23:55. Raw output in `raw/`.

**Result.**

1. **Not the arguments, not the wave size.** The dispatch runs 44 threads (`USE_THREAD_DIMENSIONS`,
   initiator 0x61, wave64 as its code is) — sane when it runs (run 181).
2. **Not the copy race either.** The trees it refits are first copied into place by `DMA_DATA`
   without `CP_SYNC` in the same compute buffer (header 0xBAADF00D at submit, "PSR_BVHL" after);
   a CP DMA wait before the dispatch changed nothing (run 185), and with the program split into
   its own job the part before it finished and the program alone still timed out (run 189).
3. **The trees are incomplete.** On the CPU, after the timeout: of a small tree's 28 leaf walks,
   28 run past the end of its 589 list records (run 190); the list region (0xf80–0x1268, right
   after the 62 nodes) is all zeros — in the copy and in its source (run 193). In the package the
   tree is stored as "PSR_BVHP" with that region empty too (run 194; the APR read was found by the
   file id hash of `libAmpr`): the title converts it to "PSR_BVHL" and builds the leaf lists at
   run time, on the GPU.
4. **The list builders are dispatches the host drops.** Their arguments read wrong at submit time
   (the GPU writes them earlier in the frame), and the host's check of 0038/0039 drops them. With
   every argument trusted the lists are complete and the refit finishes (run 195; run 205, 420 s:
   2,551,572 refit jobs done, 12 failed, 18.1 fps from 250 s). The builders are compute programs
   (0x909936c00 for one tree) and a trio of graphics-buffer programs (0x909973900, 3b00, 3f00 for
   the other; runs 197–203).
5. **Trusting all arguments is not stable:** runs 206–208 hit GPU timeouts every 15 s from
   about 170 s (a dispatch whose producer had not run: the cross-queue order the single ring
   cannot keep, F64). Trusting only the builders hit the same (runs 202–204).
6. **With the guard instead** (the refit only on complete trees, no trust; runs 209–216): no refit
   timeout in eight runs; the refit runs for 9–17 % of its dispatches (e.g. 218,340 of 1,308,673).
   Of the eight, four ran 300 s at 14–18 fps; one stopped on the title's own null read (210), one
   after a recovered fault (212), one in a long host sync (213), one on a GPU timeout elsewhere (215).
7. **Found on the way: the title's long loading is the host's memory sync.** Every run, with or
   without the refit, has two or three syncs of 25–80 s while the title loads (runs 89, 109, 179,
   180, 213: 30 s and 55 s; 25 s and 54 s; …), most of its "five minutes" of loading.

**Verdict.** The refit hangs because the leaf lists it walks are built by GPU dispatches the host
drops on stale-looking arguments; with them running it finishes. Running them safely needs their
arguments checked when the GPU reads them, not when the host reads them; until then the guard runs
the refit where its tree is complete and holds the rest back (opt-in,
`BC5_DIRECT_REFIT_GUARD=909939900` with `MEC_SKIP_PGM=1`); the launchers keep the skip. Next: the
host's 25–80 s memory syncs while the title loads.
