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

**Code.**
- `backend/include/bc5/zero_skip.hpp` (and its copy `src/bc5/zero_skip.hpp`, md5 782ca0e9): the list format, the
  scan's intersection (`ZeroMask`), the skip set (`SkipSet`), `all_zero`. 5 Catch2 cases in
  `backend/tests/zero_skip_test.cpp`.
- `patch0379-bc5LleAgc.diff` (md5 6f0c7c16; 348 lines) on the tree's `src/libs/bc5LleAgc.cpp` (e7cc2f60, patch 0001's
  file, git blob 8d2f498) gives e62113a5. It is made by `raw/splice0379.py` from `raw/zskip_block.cpp` and seven anchors:
  - the scan and skip block before `direct_sync_one`;
  - in `direct_sync_one`: the placement, the scan tick and the canary-hit check before the fast path; the take-back
    (CPU writes, canary hits) at the start of the full path; the skip in the eager loop and the forced loop; the canary
    release before a real mapping is added; the canary mapping after a rebuild;
  - in `direct_force`: a hint takes a skipped chunk back; `map_window` marks its call as a learned window's;
  - in the reopen path: `zskip_disable`.
- Switches (all off unless set; the shared builds do not have them):

  | switch | what |
  |---|---|
  | `BC5_DIRECT_ZEROSCAN_AT=<s>,…` | scan times (journal t); a diagnostic (`BC5_DIAG_ENV`, absent from the lean build) |
  | `BC5_DIRECT_ZEROSCAN_OUT=<file>` | where each scan rewrites the list |
  | `BC5_DIRECT_ZERO_NAMES=<n>,…` | heaps scanned (default `RenderGpuWcLarge,CommitIABufferAllocator`) |
  | `BC5_DIRECT_ZERO_MIN_MIB=<n>` | shortest listed run (default 8) |
  | `BC5_DIRECT_ZERO_SKIP=<file>` | skip the list's chunks, canary under them |

**Laptop checks (2026-10-29).**
- `backend` configured with MSVC 14.51 + Ninja, `-DBC5_BUILD_TESTS=ON` (Catch2 3.7.1 from `build-win/_deps`):
  `bc5_backend_tests` 96/96 cases, 33,730 assertions; `[zero_skip]` 5/5 (54 assertions). One expected count in the
  parser test was wrong on the first try (7 bad lines, not 8) and was corrected.
- `raw/harness0379.cpp`: `zskip_block.cpp` with stand-ins for the host, `clang++ -fsyntax-only -std=c++20 -Wall -Wextra
  -Wformat=2 -Wshadow -Werror`: clean.
- `git -c core.autocrlf=false apply` of the diff on the extracted file gives e62113a5; `bash -n` on every script.

**Box build** (`raw/build0379.sh`, 2026-10-29 11:00–11:01; the experiment in `~/bc5-work/exp0379/in/`):
- pins checked: shared normal 58c4a627, archive bb50b2e0, tree unit e7cc2f60, diff, header;
- the backend's Catch2 tests: 96 cases pass (33,729 assertions; one fewer than on Windows, a platform-dependent
  case), `[zero_skip]` 5/5;
- the patched unit compiled with the shared compdb command and relinked: **e1cc0c92**, rc 0, 5 warnings, all in
  older code (`stringUtils.h`, and four in `bc5LleAgc.cpp` outside the new block);
- the shared binary, archive and tree unit unchanged after the build.

**Runs.** `raw/s6n0379.sh` (made from exp 0372's `s6n0372.sh` by `raw/mk-s6n0379.pl`): the S6N route (exp 0203's
`o2-continue.cmd` on exp 0196's route saves, a private wd and save copy), **RT on**, 420 s, the shared `play-pkg.sh`
(55531ab6) with exp 0372's four private paths, a private copy of the learned file. Before each run `sync` and
`drop_caches` (the sudoers entry), so each arm starts with an empty page cache. `raw/sample0379.sh` samples every 10 s
(MemAvailable, swap, Shmem, Cached, GTT used, PSI memory/io full totals, bc5-mount `read_bytes` and RSS, refaults).
`raw/stream0379.sh` streams the kernel log to the laptop. `raw/ana0379.py` makes the table over one window.

| arm | binary | switches |
|---|---|---|
| S1 | private e1cc0c92 | scans at 150, 200, 250, 300, 350, 400 s, list to `~/bc5-work/exp0379/zero-list-S.txt` |
| A1 | shared normal 58c4a627 | — |
| B1 | private e1cc0c92 | `BC5_DIRECT_ZERO_SKIP` = S1's list |

## Result

*(filled in after the runs)*

## Verdict

*(filled in after the runs)*
