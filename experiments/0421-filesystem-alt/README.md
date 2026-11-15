# 0421 — FileSystem: an alternative to "never lazy"

**Question.** Can the GPU read fault of arm n13P4 (fault record `20261114-184017`, exp 0412 sections 98–99, 101)
be fixed without importing the title's heap "FileSystem" during the loads? Builds V and W fix it by taking the heap
off the lazy list (`mkv0419.py lazyfs`). W then showed in-host frame gaps of 0.5–3.9 s at loads, reported in the
frame profile's "prepare" (exp 0412 section 102).

**Setup.** Laptop only. Nothing was built in the host and nothing ran on the box. Sources read:
- the main unit of test build T (the closest unit on the laptop to V/W: T, then U's dead-code round, then V's
  `touchfn lazyfs liveids defer`), md5 `c8c5d5ce`;
- the backend's `direct.cpp` of candidate G/T (`backend-direct-g.cpp`);
- `mkv0419.py`, `mkp2_0419.py`, `build-V.md`, `build-W.md`;
- exp 0412 README sections 98–102 (section 102 is on branch `exp/0412-memory-guardian`, 0b5fd887).

Neither V's steps nor W's lean rewrite edit the functions named below, as far as their generators show. W's tree
itself was not read.

## 1. The mechanism, from code

**[read] "Prepare" in the frame profile does not import anything.**
- `frame_profile_job(..., r.prepare_ms, ...)` adds the device's `SubmitResult::prepare_ms`. In `Device::submit`
  that is `t_list - t_enter`, where `t_enter` is taken after the device mutex. The phase covers:
  - the filter (`policy::filter`, with the unit's `mapped` callback `covered_sorted`, and DMA snapshots);
  - host-indirect resolution, the state-stack tracker and CU tables;
  - the PFP/DMA sync inserts, the indirect checks and the nested-IB survey with the nested filters;
  - `scratch_reserve`, the IB fixups and the `memcpy` into the slot.
  It is CPU work and kernel calls on the job's own buffers. Its five parts go into the frame profile line as
  "prepare = filter + tracker + cu + nested + copy".
- The direct path's imports run in `submit_now` **before** `g_dev->submit`. The frame profile books them under
  "sync" (`t1 - t0`) and "hints" (`t2 - t1`), not "prepare" (`frame_profile_submit` gets these two times). They
  are:
  - `direct_sync_one`: the SEEK_DATA walk, `ls415_import` (udmabuf pin), the merge pass, `wait_jobs()` (a full
    GPU drain while K1r is on and a BO was added), and the mapping rebuild;
  - `direct_force`, called by K1 at the filter (`k1f412_pass`), by dt412 and by the bind hints.
- So the [I] line of section 102, "prepare is where a heap that is no longer lazy has its freshly written memory
  imported", is **refuted as written**. A non-lazy FileSystem's imports would show as "sync"/"hints" time.

**[I] What could make "prepare" take seconds, and how FileSystem could reach it** (not proven, not refuted):
- Pure CPU work on one job does not take 3 s. A stall that long means the thread waited in the kernel:
  - a page fault on guest memory the filter, tracker, snapshot or nested copy reads, blocked on `mmap_lock`,
    reclaim, swap-in or the migration of a page being pinned;
  - or `scratch_reserve`'s GTT BO allocation and VA map, when a job outgrows its slot.
- Two paths from FileSystem to "prepare":
  - (a) With FileSystem mapped, `DMA_DATA` packets whose source lies in it pass the filter. `dcb` ones of 4 KiB
    or more are copied by the CPU into the snapshot ring (`BC5_DIRECT_DMA_SNAPSHOT=4096` is the title's default).
    On U, K1 at the filter imports such a named chunk first, so this probably held on U too (not checked).
  - (b) Another submitting thread imports, pins or migrates FileSystem pages while the game thread's prepare
    touches guest memory.
- Section 102 says W changes more than FileSystem's list and ran on a different boot. So the link
  "FileSystem → stall" is itself still inferred.

**Reads that would settle it without a run** (box reads, the top's GO; the files are the ones section 102 used):
1. For the 32 frames with prepare over 200 ms: the same frame-profile line's split into filter, tracker, cu,
   nested and copy.
2. The `timing split` lines around them (sync: scan / drain / maps).
3. The times of the `direct: … +N BOs` import lines against the stall times, on the game thread and the others.

Reading the split:
- "copy" points to `scratch_reserve` or `memcpy`.
- "filter" points to the snapshot copies or page faults.
- If the import lines fall inside the stall windows, path (b) is likely.

## 2. Alternatives (none removes the cause of the fault: the title gives the GPU an address in FileSystem)

| | What | Does the PS5 do this? | Cures n13P4's case | Load stalls (under the FileSystem hypothesis) | Risk / cost |
|---|---|---|---|---|---|
| A | FileSystem **eager** by name: the whole view (52 MiB, 26 chunks) is imported once, when it appears, as one BO; no import per write and no merges. No code: an arm word `BC5_DIRECT_EAGER_NAMES=<launcher's list>,FileSystem` (eager is tested before lazy in `direct_sync_one`) | **Yes**: on the console all of the title's memory is GPU-readable from the map call | yes | gone if the stall is churn per write (many small imports, drains, merges); stays if it is "FileSystem mapped" itself (path a); one import if the view appears during a load | +4 MiB against W (2 unwritten chunks); not what the maintainer asked for ("without importing the whole heap at load") if the heap is created at a load, which is not known |
| **B** | **Late import** (`BC5_DIRECT_FS_LATE`, this step): the heap stays lazy as on U; a written chunk is imported once it has been seen written for the delay (30 s), one chunk a pass, passes ≥ 250 ms apart | **No.** For the delay, written FileSystem data is not GPU-readable (U's state). n13P4's read came about 580 s after the write (written by 148 s, read at 731 s) | yes for that case (imported by about 180 s); a read inside the window faults by name, as on U | none of FileSystem's imports or mappings fall in the load that wrote it; later loads can still meet a late import (a write at 92 s is imported at about 122 s) | ≈60 lines; one drain and rebuild per late chunk, spread out; the pin is W's in the end |
| C | **Import on reference**: dt412 (`BC5_GUARD_DESC_TARGETS`, section 94) extended to scan the record a buffer descriptor points to for addresses in lazy views | No: the console has no import step; this guesses the GPU's reach | **unknown**: section 101 shows the address came from inside the 0x78-byte item record or deeper; the depth is not known | no import at load unless a load's submissions name it | a scan per submission (766 dispatches in one acb); false positives import more; misses deeper levels |
| D | Async pin: udmabuf creation on a worker, the mapping in the next sync | Not applicable | as W | only the udmabuf create moves off the path; the drain and the mapping rebuild stay under the device mutex | a large change to the direct path; not proposed |

**Chosen for the code step: B.** It is the only option that keeps every FileSystem import and mapping change out of
the load that wrote the chunk, whatever the path from FileSystem to the stall is. That makes it both a fix
candidate and the discriminator: if W's stalls stay with B on, FileSystem is not their cause, and W's plain fix can
stand. **A needs no code** and is the more console-like answer, so it can run as a fourth arm in the same series by
its launcher word alone.

## 3. The step (tag fs421), behind one switch

Files in this directory:
- `late_import.hpp`: the decision logic, header-only. `mk0421.py` copies it into the tree as
  `src/bc5/late_import.hpp`.
- `test0421late.cpp`: its CPU test.
- `mk0421.py <tree root>`: the edit of `src/libs/bc5LleAgc.cpp`, run on a V or W tree. Every edit must match once,
  and the lazyfs condition is matched in its V form (`std::getenv`) or its lean form (`BC5_DIAG_ENV`).
- `fs421-on-T-lazyfs.diff`: the edit as applied to the stand-in (T unit `c8c5d5ce` + `mkv0419.py lazyfs` →
  `a8f86104`).
- `standin0421.cpp`: the inserted block with stand-ins, for the syntax check. It is generated: the block cut from
  that stand-in, with stubs.

`BC5_DIRECT_FS_LATE` (unset or `0`: off, W unchanged):
- `1` or `on` means 30 s. `5`..`3600` is that many seconds. Any other value means 30 s.
- On (the following holds whatever `BC5_DIAG_LAZY_FILESYSTEM` says):
  - V's lazyfs keeps "FileSystem" in `BC5_DIRECT_LAZY_NAMES`, so the heap is lazy: no import by data, no zero
    cover over its written chunks (kl412). K1 at the filter and the hints still import any chunk they name.
  - In each full pass of `direct_sync_one`, the lazy views named "FileSystem" are walked with SEEK_DATA. A data
    chunk that no BO covers is timed from the first pass that sees it.
  - Once a chunk has waited the delay, it joins `need` and is imported, mapped and drained like any by-data chunk.
    At most one such chunk goes per pass, and passes with a late import are at least 250 ms apart. Failed chunks
    and chunks past the end of the file are skipped.
  - A chunk that leaves the list (imported by another path) is forgotten.
  - A pass is not skipped as "nothing changed" while a waiting chunk's time has come.
- Lean: the switch is read with a plain `getenv`, as a fix. In a lean build it must be listed as class K in
  `lean-classes.tsv` / `lean-keep.txt` if the series uses the lean binary. The stderr line and the journal lines
  (up to 64 `fs421 late import` lines: chunk, seconds waited, count, waiting) are under `#ifndef KYTY_BC5_LEAN`.

## Result (laptop)

- [M] `test0421late.cpp`: **34 of 34** checks pass (VS clang++ 18 `-std=c++20 -O1 -Wall -Wextra -Werror`).
  Covered: the 30 s wait, one chunk per pass, the 250 ms gap, out-of-order and repeated input, forgetting, a
  chunk's own time, two per pass, and the switch's values.
- [M] `mk0421.py` on the stand-in tree: 8 edits, brace balance +0. A second run refuses (the lazyfs condition no
  longer matches).
- [M] `standin0421.cpp`: the inserted block passes `clang++ -std=c++20 -fsyntax-only -Wall -Wextra -Werror` in the
  normal form and with `-DKYTY_BC5_LEAN`. `_CRT_SECURE_NO_WARNINGS` was needed only for the Windows CRT's
  `getenv` warning.
- [not done] Not compiled in the host. Not applied to V's or W's own tree (anchors checked on T + lazyfs only).
  Not run.

## What a box test needs

Build W + `mk0421.py`, normal binary (W's words). Then short walks to G+60, interleaved, four of each:
- **W plain**;
- **W + `BC5_DIRECT_FS_LATE=30`**;
- if the top wants the full picture:
  - W + `BC5_DIAG_LAZY_FILESYSTEM=1` (U's state; this brings back n13P4's condition, which a short walk limits);
  - W + arm A's eager word.

RT on.

Measures, per walk:
- frames with prepare over 200 ms and the longest gap before G (section 102's measures);
- the prepare split of those frames;
- no fault record;
- the `fs421 late import` lines: their times, and whether a gap falls on them.

Late imports land at about 67–146 s, inside a walk to G+60. If B's arm has the stalls at the loads, FileSystem is
not their cause.

**Verdict.** Not yet: a design and a prepared step; nothing measured on the box.
