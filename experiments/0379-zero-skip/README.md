# 0379 — Leave the second title's known-zero render-heap chunks unpinned, behind a canary (RT on)

**Date.** 2026-10-29. **Box.** A private build and three runs of the S6N route with RT on (arms S, A, B), after
exp 0378, with the top session's GO. **Number.** Claimed in `experiments/0379-zero-skip` and `~/bc5-work/exp0379`.

**Question.** With RT on, the second title pins ~12.4 GiB of GTT and the box runs out of page cache: bc5-mount re-reads
3–4 GB a minute and PSI I/O "full" is 9–24 % (F505). Can the host leave the all-zero 2 MiB chunks of the two big render
heaps (RenderGpuWcLarge, CommitIABufferAllocator) unpinned, with no GPU fault, hang, frame-rate loss or visible change,
so that GTT used falls and the mount reads less?

## Design (written before the code)

### What pins those chunks today

Read from main's patch 0001 (9420cfa0), `src/libs/bc5LleAgc.cpp` (blob 8d2f498):

- The two heaps are in `BC5_DIRECT_EAGER_NAMES`, so `direct_sync_one` imports every 2 MiB chunk of them
  (`if (v.eager)`), data or not. udmabuf pins, and so allocates, every page (ADR 0006).
- The learned windows (`learned_add`, 96 MiB around one fault) and the hint windows (CB/DB bases ±32 MiB,
  `hint_targets`) add chunks to `S.forced`. Inside an eager heap they change nothing: the heap is imported in full anyway.
- So F402's split (738 MiB zero and unforced, 1,878 MiB zero inside learned windows) is a statement about which zero
  chunks are *protected by evidence* of GPU use, not about what pins them. Everything zero in those heaps is pinned
  because the heaps are eager.
- The learned windows inside these heaps date from before the heaps were eager (F96: "17 of the 18 regions learned so
  far lie in those two heaps"), when a lazy heap faulted on GPU-only memory. They record that the GPU once touched
  *something* within 64 MiB, not which chunks.

### The two levers exp 0371 names, and why neither is taken as stated

- **Narrower learned windows** saves nothing while the heaps are eager (above). It only matters for lazy heaps.
- **Lazy unforced ranges** (make the heaps non-eager) would go back to F96's state: render targets and GPU-written
  buffers that no CPU writes, outside the learned and hint windows, would fault. A fault that stalls is the 14-s
  freeze and the reopen (F88 (4)), which has taken the machine down (F207). A fault that does not stall is never
  learned (F208) and the GPU's writes are lost silently.
- Exp 0333's phase R (release after a scan) needs a BO split, a remap and a hole punch mid-session, with a lost-write
  race between the re-read and the punch. It is the most invasive.

### The lever chosen: a zero list from an earlier run, skipped at import, with a canary under the skipped chunks

1. **Arm S writes a zero list.** A diagnostic `BC5_DIRECT_ZEROSCAN_AT=<s>[,<s>...]` with
   `BC5_DIRECT_ZEROSCAN_OUT=<file>` reads every chunk of the named eager heaps (`BC5_DIRECT_ZERO_NAMES`, default
   `RenderGpuWcLarge,CommitIABufferAllocator`) on a background thread at each time and keeps the chunks that were
   all-zero in **every** scan so far. After each scan it rewrites the file: per heap its name and total size, then the
   zero runs of at least `BC5_DIRECT_ZERO_MIN_MIB` (default 8) as offsets from the heap's start. The scan only reads
   (pread of pinned shmem pages: no page cache, no allocation).
2. **Arm B skips those chunks.** `BC5_DIRECT_ZERO_SKIP=<file>` (off when unset; set only by this experiment's
   launcher) loads the list. When a named heap appears with the same total size, its listed chunks are left out of the
   eager import. They are never pinned, so their shmem pages are never allocated.
3. **What still imports a skipped chunk** (it leaves the skip set for the rest of the session):
   - a CPU write: each full sync (one follows every `st_blocks` change) checks each skipped run with `SEEK_DATA`, as
     ADR 0006 does for non-eager views;
   - a hint window (a CB/DB base ±32 MiB): `direct_force` from the hint path takes a skipped chunk back before the IB is
     submitted (F474: the forced sync imports before the job);
   - the canary (below);
   - a device reopen: the skip is switched off and everything is imported as before.
   A chunk that only a learned window forces stays skipped: the learned window is older evidence than the zero list
   (see above), and the canary covers it.
4. **The canary.** Each skipped run gets its own 2 MiB slice of one private memfd BO (one BO, so every CS lists one
   more BO, not one per run). Every chunk of the run is mapped onto that slice at every guest VA that maps it, so a
   GPU access to a skipped chunk never faults:
   - a read gets zeros, which is what the chunk holds (it was zero in every scan and the CPU has not written it);
   - a write lands in the slice. Every 50 ms, on the sync path, the host checks one run's slice for a non-zero byte
     (round robin; cache lines flushed first, TODO(verify) that the CPU sees the GPU's udmabuf writes without it). A
     hit takes the whole run back: it is imported at the next sync, its slice mappings are released, a
     `zero skip: canary hit` line is journalled.
   - The cost of a hit: the GPU's data written to the slice is lost (the real chunk reads zero), and until the check,
     reads of the run's other chunks see that data. That is a possible one-frame glitch, never a fault or a stall.
5. **What it cannot see.** A GPU write of zeros, or data written and cleared between two checks, leaves no trace in the
   slice. Arm S's intersection over several scans is the defence against the second (a chunk that ever held data in a
   scan is not listed).

### Expected gain and risk

- F402 (RT off, bench): 2,814 MiB zero in the two heaps, minus the hint windows (~200 MiB) → up to ~2.6 GB less pinned
  if the list matches. RT on uses ~120 MiB more of CommitIABufferAllocator (exp 0333's list item 5). Runs shorter than
  8 MiB are kept pinned, so the real figure is lower.
- Every new code path is the host's only. Nothing is released mid-session, nothing is punched, no BO is split. A wrong
  list costs a canary hit (a run back, a possible glitch), not a fault.
- The scan and the skip only run with their switches set; the shared builds are untouched (D19).

### Pass criteria (arm B against arm A)

- GTT used lower and bc5-mount reads per minute lower, over the same steady window;
- flips/s not lower (within run-to-run noise, ~1 flip/s per F394/F402);
- no new hang, no kernel amdgpu line, no TIMEOUT, no new learned fault;
- canary hits and hint takebacks counted; no crash line; the live-save checksum unchanged.

## Setup

*(filled in after the build)*

## Result

*(filled in after the runs)*

## Verdict

*(filled in after the runs)*
