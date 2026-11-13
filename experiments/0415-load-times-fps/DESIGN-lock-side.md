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

## 7. Review by the top session (2026-11-12 night): what S1 has to settle before S2-S5 exist

Approved to build: S1 (records and `verify`) together with `KYTY_BC5_FRAME_STAT`, one private build. These points
are open work for S1; none is done yet.

1. **Enumerate the writers of the guest's layout, not only the generation bumps.** To list here, with file and line,
   before S1's code: every memory call including its failure paths (a call that bumps the generation and then fails:
   record or not); `MAP_FIXED` over part of an existing range (an unmap record and a map record, in that order, seen
   atomically by a reader); mappers that do not go through `kernel/memory.cpp` (the map flavour of libAmpr's
   `CommandBufferSetBuffer`, which mapped FIXED over the title's heap; `AllocateGuestStackMemory`; save-data and file
   mmaps; anything in `libs` that calls the allocator directly); protection changes; name changes; teardown at
   process exit. **S1's comparison is made at the sequence number the submission read**, so that a record arriving
   after its change became visible to a submission counts as a mismatch (order, not only content).
2. **The wait with `g_dev_mutex` released.** After taking the mutex again the newest sequence is read again, with a
   bound on the loop so that a title thread mapping without pause cannot starve a submission. The lock order is to be
   written down (the applier's mutex, `g_dev_mutex`, the memory subsystem's lock held by the title's thread while it
   queues) with the argument that there is no cycle: a memory call must not hold its lock while it waits for anything
   the applier needs.
3. **Coalescing.** A map and an unmap of the same range before any submission should cost no kernel work (a pending
   import may be cancelled); an unmap is never reordered before the map it follows; an unmap and a map at the same
   address with a job in flight keep `wait_jobs`.
4. **Publication of a range imported outside the mutex.** The import must be of the file range as it is at
   publication: state why the backing cannot change between queue and publish (truncate, remap), or check again
   under the mutex.
5. **S5.** Before records are trusted for private memory, the read of `/proc/self/maps` stays as the comparison in
   `verify` over a long play, as in S1.

## 8. S5 after the seventh slot: what was built, and the form without the read (2026-11-13)

**Built and measured** (README section 16, build L5c, `KYTY_BC5_ANON_SYNC`): the walk on the submission path is a
41-43 ms read of `/proc/self/maps` under the device mutex, 174-181 times a run, and found no anonymous guest VMA in
708 walks [M]. With the walk left to a thread that reads the same file and compares a signature, the walk ran once a
run, `anon_miss` was 0, and the share of frames over 50 ms fell from 17-25 % to 9-17 % in two pairs [M]. This answers
review point 5 only in part: the comparison ran over 8 runs of 140 s, not over a long play.

**What is still wrong with it**: the read is still made (2.5 s of one core a minute of play), it takes the address
space's lock for reading while the title maps and unmaps, and an urgent call is served one pass late.

**Where an anonymous readable guest mapping can come from** [C: read in the host tree at patch 4651d1d3]:
- the guest's span is a process-lifetime reservation of `PROT_NONE` anonymous placeholders
  (`src/kernel/memoryAddressSpace.inc`: four `mmap` sites, all `PROT_NONE`: the reservation, `RestorePlaceholder`,
  `UnmapViewPreservePlaceholder`); real memory is a view of one of the two files, which the walk skips by rule;
- `src/common/platform/sysLinuxVirtual.cpp`: the host allocator (`map_anonymous` and the fixed and aligned forms,
  15 `mmap` sites with `MAP_ANON`), whose address can lie in the guest's span when the caller asks for it;
- two `mprotect` sites in the whole host: `sysLinuxVirtual.cpp` (the protect call) and `libAmpr.cpp` (one helper);
- `bc5LleAgc.cpp` itself: one 4 KiB anonymous page at an address the kernel chooses.

**The form without the read** (stage S5b, to build next, switch value `KYTY_BC5_ANON_SYNC=events`, default off):
1. one process-wide counter, bumped at each of those sites when the call makes anonymous memory readable inside the
   guest's span: a `MAP_ANON` map with a readable protection, or a protect call that turns reading on. The protect
   sites cannot tell a file view from a placeholder, so they bump for every such call in the span (too often is
   safe, too rarely is not);
2. the submission path walks only when the counter differs from its value at the last walk, or the last walk's list
   was not empty (resident pages inside a readable anonymous VMA grow without any call), or after -EFAULT or a device
   reopen. No thread, no periodic read on any path that holds a lock of the direct path;
3. the check that a site was not missed is S1's maps check (`bc5-mapschk`, every 5 s, its own thread, counts only):
   it gains one count, "a readable anonymous guest VMA exists while the counter says none was made".

**Verify first** (the same build, `KYTY_BC5_ANON_SYNC=verify`): each walk also records whether the counter had
moved; `anon_miss` then counts walks that found a change the counter did not announce. Also counted: how often the
counter moves (if guest protect calls move it many times a second, rule 2 walks as often as today and the protect
sites need the range table's knowledge of what lies there: a lookup, not a read of the file).

**What it gives up**: nothing in time, since a change is walked at the first submission after the call that made it.
What it adds is the duty that every future host site which maps or protects guest-span memory bumps the counter;
the maps check is what catches a site that does not.
