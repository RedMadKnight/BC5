# The device mutex's mapping maintenance: from "re-derive on every submission" to "apply what changed" (exp 0415, 2026-11-12)

A design note for review; nothing here is built. It covers candidates (c) imports outside the hold and (d) mappings
recomputed only for what changed, and is written against exp 0412's rule for the learned windows
(`DESIGN-learned-windows.md`: R1 "map when the title maps", R2 "unmapped addresses are PRT"). Marks: [M] measured
(README section), [C] read from code, [I] inferred.

## 1. What is measured

One mutex, `g_dev_mutex`, is held by `submit_now` from start to end on three threads. With the read fix on (README
sections 8, 10) [M]:

| | menu load | save load | 34 s of play |
|---|---|---|---|
| phase | 15-22 s | 14-15 s | 33-34 s |
| mutex held | 9.2-13.1 s | 6.9-7.6 s | 14.1-17.1 s |
| waited for it by its three users | 5.9-8.0 s | 4.7-5.5 s | 7.1-9.1 s |
| view list rebuilt | 0.9-1.5 s | 0.9-1.2 s | 1.3-1.9 s |
| mappings recomputed | 1.1-1.3 s | 1.0-1.1 s | 0.9-1.1 s |
| imports | 1.6-2.2 s | 0.05 s | 0.3-0.6 s |
| learned windows | 1.4-2.7 s | 2.1-2.6 s | 1.2-2.5 s |
| anonymous sync | 0.6-0.9 s | 0.7 s | 1.8-2.0 s |
| the device call (prepare, BO list, CS ioctl) | 2.6-4.7 s | 1.4-1.6 s | 6.0-7.1 s |
| GPU drained before mappings change | 0.03-0.07 s | 0.03-0.07 s | 0.04-0.06 s |

In five runs no learned window mapped anything, in about 860 full applications a run [M, section 10]. Three exact
speed-ups of single loops (build L3) gave 0.4-0.9 s per phase for one of them and nothing for two [M, section 10]:
the cost is not a slow loop.

## 2. Why it costs: the pull model [C]

The GPU's address space is re-derived from the guest's whole layout whenever the guest's ranges generation moved,
inside whichever submission comes next:

1. `direct_views` rebuilds the list of every mapped range (12,500-28,000 entries, a string each) and its signature.
2. `direct_sync_one` walks every view for chunks to import (`lseek(SEEK_DATA)` per non-eager view), imports them
   (udmabuf create + GEM import, the kernel allocating and zeroing the pages), merges neighbours, then recomputes
   every (view x imported range) mapping and diffs the result against what the device has (want, drop, add).
3. `learned_apply` copies and sorts the device's 21,300 mappings and passes every learned window over them.
4. `sync_mappings` reads `/proc/self/maps` (23,000 lines) and checks every userptr mapping against it.

During a load the title changes its ranges about 700 times a second (14,800-17,000 AMM commands in a menu load), so
steps 1-3 run for most submissions: 540-860 full syncs per phase. Each step is O(whole layout); the change that
triggered it is one range.

## 3. The push model

The host already sees every change at its source: the memory calls (`sceKernelMapDirectMemory`, `mmap`, `munmap`,
`mprotect`, the AMM commands) run in `kernel/memory.cpp` and bump the generation. Instead of a number, they leave a
**change record**: {sequence, kind (map, unmap, protect, rename), va, size, file, offset, name}. The direct path keeps
its own state (views, imported BOs, GPU mappings) and **applies records**:

- **map**: import the file range of the new view (R1: all of it, no data test, no name list), then GPU-map it at its
  address, replacing the PRT background (R2) or the old mapping there.
- **unmap**: replace the GPU mapping by PRT; release the BO range when no view covers it (exp 0412's release policy
  decides when; unchanged here).
- **protect, rename**: update the view's attributes; no GPU work unless read-only changes.

**Where the kernel work runs (candidate c).** The import of a new range (udmabuf + GEM import: the 8 ms a time, 2.2 s
of a menu load) needs nothing a submission holds: the BO it creates has no name anybody else knows. It runs on the
thread that applies records, outside `g_dev_mutex`. Only the publication (the VA map and the insert into the direct
path's tables) takes the mutex, for microseconds to a millisecond.

**The ordering guarantee, unchanged (exp 0037).** A submission must see every change the title made before it. Each
record has a sequence number; the memory call returns only after its record is queued. `submit_now`, after taking the
mutex, reads the newest sequence number and makes sure every record up to it is applied: records whose kernel work is
done are published at once; for one still in the kernel it waits on a condition variable (the mutex released
meanwhile, so the other submitters are not stopped; their own submissions wait the same way if they need the same
record). So a buffer never reaches the kernel with a view missing or stale, exactly as today; what changes is that the
work is proportional to the records, and that the kernel part of an import does not stop the other two submitters.

**Who applies.** A maintenance thread (`bc5-maps`) wakes on a queued record and applies in sequence order; a
submission that arrives first applies the pending records itself (it has to wait for them anyway). One applier at a
time (its own small mutex), publication under `g_dev_mutex`.

**Removal of mappings and jobs in flight.** Before a mapping is replaced or removed, jobs that may use it must be
done: today's `wait_jobs` (0.03-0.07 s per phase [M]). Kept as it is, under the mutex, at publication of an unmap.

**The anonymous side.** `sync_mappings` exists because writable anonymous guest memory is found by reading
`/proc/self/maps`. Private guest memory is a file too since exp 0023 (the walk "should find nothing anonymous" and
runs once a second as a check [C]); exp 0412 measured kind K2 as 0 MiB. With records for private mappings the read
of `/proc/self/maps` becomes a check at a low rate (as it is meant to be) instead of 1.8-2.0 s per 34 s of play.

## 4. Stages (one switch each, default off; a stage is built only after the one before it is measured)

| stage | what | changes what reaches the GPU? | test | measured by | if it were wrong |
|---|---|---|---|---|---|
| S1 `KYTY_BC5_MAP_RECORDS=verify` | the records, and an incrementally kept view list **compared** with the full rebuild at every sync; the full rebuild is still what is used | no | CPU: random map/unmap/protect sequences, incremental list against rebuilt list | a mismatch counter that must stay 0 over the route, a long play and ASTRO BOT; this proves the records are complete (the risk: a path that changes ranges without leaving a record) | nothing: the old list is used |
| S2 `=views` | the incremental view list is used; the rebuild runs at a low rate as a check | no (same list by S1) | S1's | view list time (0.9-1.9 s per phase) | a view missing: its memory not on the GPU (a fault, or PRT zeros under R2); a view kept after unmap: the GPU reads freed pages |
| S3 `=maps` | mappings recomputed for the changed views only | no (same set) | CPU: incremental mapping set against the full recompute on random layouts | mappings time (0.9-1.3 s per phase); `verify` sub-mode compares the device's mapping list | as S2 |
| S4 `=import` | imports on the applier, outside the mutex; publication under it | no (same imports, earlier) | CPU: the sequence/condition protocol under a thread sanitiser build with a stub device | import time under the hold (1.6-2.2 s of a menu load); waits for a record in the kernel (new counter) | a submission that does not wait for its record: an operand's memory missing on the GPU |
| S5 `=anon` | private-memory records replace the per-sync read of `/proc/self/maps`; the read stays as a check every 5 s | no | CPU: records against a parsed maps text | anonymous sync time (1.8-2.0 s per 34 s of play) | a userptr mapping kept after its VMA went: stale pages |

S1 can be built now: it does not depend on exp 0412's changes. S2-S5 are written on top of exp 0412's R1/R2 diff
when it lands (R1 removes the data scan and the name lists from the import step, R2 removes the learned windows and
the fill, so what S3 and S4 have to keep in step is smaller).

## 5. What this does not touch

The device call itself (2.6-7.1 s per phase: the filter and state tracker in prepare, the BO list, the CS ioctl) is
the per-submission work under the same mutex; it is part 2's subject (README section 11). The order of submissions is
unchanged by every stage. The memory wall and the release policy are exp 0412's.

## 6. Expected effect [I]

Of 9-13 s held in a menu load, 4-6 s are steps 1-4; in play 4-6 s of 14-17 s. With them proportional to the changes,
the hold falls by about that much and so does the waiting of the other submitters (5.9-8.0 s a menu load, 7-9 s per
34 s of play). Whether a load gets shorter by it is not known: L3 removed 0.4-0.9 s of hold per phase and no load
moved. The honest expectation is fewer long frames (a full sync of 10-40 ms inside a submission is one) rather than a
shorter load or a higher mean frame rate. S1's run also gives the count of records per phase, which bounds the gain.
