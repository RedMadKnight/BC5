# Experiment 0401 series e7, tag lzr: `BC5_DIRECT_LAZY_RELEASE`, a release of idle unviewed chunks

Agent `lzr`, 2026-11-04, laptop only (no box access). Asked by the top session after the maintainer's "Ram się dusi"
in his e6 play. The top session's reading was "lazy 2 MiB pinned chunks are never freed, so GTT grows until the box
swaps" (the e3 22:21 memory-line finding).

The switch is `BC5_DIRECT_LAZY_RELEASE=<seconds>[,dry][,eager]` in `src/libs/bc5LleAgc.cpp`. It is off by default.

**In short.**
- *Shown:* the code never gives back an imported chunk.
- *Shown:* GTT is flat after the load on every scripted route, and grows in steps in free play.
- *Inferred:* the growth is the title's own reservation filling up. Most of it is CPU-written data chunks in heaps that
  stay mapped. Those chunks cannot be released safely by any host code, because there is no signal of GPU use.
- *Built:* the narrowest safe version. It releases chunks that no view covers, behind the switch, with a dry mode that
  measures them first.

## 1. What grows, and how fast

### Shown by records

- **The scripted routes of exp 0401** (`raw/night/*-memline.txt`, 48 routes with lines; `rB` has none).
  - GTT is 8,465–9,017 MiB at t 10 s. It is 12,023–12,105 MiB by t 70–100 s, which is the load: about 3.0–3.2 GiB a
    minute.
  - After that it is flat. From t 120 s to the end, GTT changed by 0 MiB on all six 1,010-s routes (r5, r6, rA, rC,
    rp0, rp1; 14.8 minutes each) and on a5, aA and aB (6.8 minutes).
  - a6 is the only exception, +16 MiB, because it plateaued later (11,318 MiB from t 160 s).
  - MemAvailable's floor was 417–669 MiB, and swap ended at 542–1,029 MiB.
  - These routes stand still or replay a short record, so they stream nothing after the load. Exp 0379's G1/G2 found
    the same: 0 MiB in 17 minutes.
- **Free play grows in steps.** Exp 0379 README, lines 491–503:
  - the 21:33 play: +553 MB in 19 minutes after the load (≈29 MB a minute), in steps of +119, +88, +39, +82 and +113;
  - 16:25: +344 MB in 34 minutes (≈10 MB/min);
  - 12:00: +375 MB in 6 minutes (≈62 MB/min);
  - F353, RT off: +0.5 GB in 29 minutes.
- **The e3 22:21 play** (Codex's relay of the author's analysis, `coordination/codex-to-claude.md:1283`):
  - direct pinned went from 8,394 to 12,114 MiB (+3,720, the load included);
  - private memory stayed at 270 MiB;
  - GTT was 12,822 of 13,312 MiB.
- **The e6 play at t≈684 s** (the top session's read; no file of it is on the laptop):
  - GTT 12,889 of 13,312 MiB, MemAvailable 216 MiB, swap 1.4 GiB, PSI full avg60 23.6 %;
  - that is about 0.8 GiB above e6's own arms (12,034–12,096 MiB, `t6*`, `r6`).

### Shown by the code

These hold in `d1cfd9bb`, the same as in exp 0379's reading of patch 0001.

- `S.bos` only grows. Three things import a chunk:
  - an eager view, which imports every chunk of the view;
  - `SEEK_DATA` in a view that is neither eager nor lazy;
  - `S.forced`: hint windows (CB/DB bases −32/+32 MiB, `hint_targets`) and learned windows (96 MiB, `learned_add`).
    `S.forced` never shrinks.
- Only two paths free a BO:
  - the merge, which replaces BOs by one covering the same range;
  - a device reopen, which clears everything.
- A chunk whose view went away loses its GPU mapping at the next rebuild ("drop what no view asks for"). Its BO stays
  pinned all the same.
- A draw's submission lists every imported BO that has a mapping (`backend/src/direct.cpp:1485-1497`). Short lists
  are used only for IBs without a draw or dispatch.

### Inferred, not shown

- **Where the growth goes.**
  - Exp 0288's and exp 0330's breakdowns (`0288-emulator-memory/raw/M2-breakdown.txt`,
    `0330-host-memory/raw/A-breakdown.txt`) show the views reserving 12,159–12,162 MiB, of which 11,222–11,224 MiB was
    imported.
  - The 938 MiB not imported lie in the non-eager heaps alone: AssetHeap Large 502, AssetHeap Small 136,
    InitAllocator 240, Wwise 52, FileSystem 4, job scratch 4.
  - The eager heaps are imported in full during the load.
  - So the growth after the load can only be one of four things:
    - CPU-written data chunks of those heaps;
    - forced chunks outside the eager heaps;
    - new direct-memory views;
    - non-direct GTT: RADV 117 MiB and the desktop about 238 MiB on the bench, unmeasured in play.
- **It is the direct path's.** e3's direct pinned (12,114) against exp 0379 G1's bench, which also ran without the
  skip (11,328), is +786 MiB. The GTT difference between the same two runs is +773 MiB (12,822 against 12,049). These
  are two different runs.
- **A ceiling, not an endless leak.**
  - 12,114 MiB pinned is about the views' whole reservation (12,162 MiB, in which aliases may count twice).
  - So by the end of e3's play nearly everything the title reserved was pinned.
  - The 37-minute tb2 play (12,639 MiB), e3 (12,822) and e6 (12,889) all fit a ceiling of about 12.8–12.9 GiB.
  - That ceiling leaves about 420 MiB below the GTT cap and pins all but about 2 GiB of the 15.2 GB box.
- **What is "idle"** cannot be read today.
  - This title's non-eager heaps are single, permanent views ("1 views" in both breakdowns).
  - Their chunks are never under no view, even after the title frees them inside its allocator.
  - So the data chunks that make up the growth stay viewed. The dry mode (section 3) measures what is not.

## 2. Why idle *viewed* chunks cannot be released safely, and what the narrowest safe version is

- **No per-chunk GPU-use signal.**
  - Every draw's submission lists every mapped BO, so a listing says nothing about a chunk.
  - Shaders reach memory through T#/V# descriptors, which the host does not parse.
  - A hint sees a CB/DB base only when it is bound, and `g_hinted` forces each base once and never again
    (`hint_targets`, at `if (std::find(hinted…) != hinted.end()) continue;`).
  - A learned window appears only after a fault.
- **What a missing mapping costs.** A GPU access to a released chunk is a VM fault:
  - a fault that stalls is the 14-s freeze and reopen (F88 (4)), and it has taken the machine down (F207);
  - a fault that does not stall is never learned, and the GPU's writes are lost (F208); exp 0379 README, lines 31–34.
- **A zero buffer under the chunk** (as `scratch_fill` or the zero skip's canary do) gives zeros instead of the data.
  That is correct only for chunks known to be zero, which is exp 0379's zero skip.
- **A cap with LRU among the lazy viewed chunks is not safe either.** There is no use signal to rank them by, and any
  victim may be read in the next frame.
- **The narrowest safe version** releases only chunks under no view: no GPU VA maps them, so no submission can reach
  them. They must also be unforced, and kept that way for N seconds. It uses the merge's own lifecycle and adds a
  stricter idle check. That is what is built.

## 3. Design (`mklzr0401.py`)

**Switch.** `BC5_DIRECT_LAZY_RELEASE=<seconds>[,dry][,eager]`, F767's reading.
- Unset, empty and `0` are off.
- The seconds are 1–86400, in decimal digits.
- The words are `dry` (count and journal only) and `eager` (described below).
- Anything else is off, and the journal says why (lesson R41).
- The test covers 18 bad forms, among them ` 30`, `30s`, `0,dry`, `30,`, `30,foo`, `86401`, `+30`.

**The pure part, `Lzr0401` in the unit and byte for byte in `lzr0401.inc`.**
- `parse`, `apply_allowed`, `period` (a quarter of the idle time, 1–15 s) and `due`.
- `merged`, `hits` and `covers`: the views' memfd ranges by class, eager before lazy before data, plus the zero-list
  heaps.
- `plan`, one pass. For each chunk of each BO it keeps a `Chunk` record: `since`, and the class it was last seen under.
  A chunk is cut when all of these hold:
  - no view covers it;
  - it is not in `S.forced`;
  - it has been so for the idle time since a pass first found it so;
  - it is allowed: last seen under neither an eager view nor a zero-list heap. With `eager`, an eager-heap chunk is
    allowed too, and so is one never seen under a view, unless the zero skip is set.
- Per BO, `plan` gives the kept runs and the cut chunks. A split BO is limited by the merge's mapping budget (512 less
  what the merge moved) and by 32 BOs a pass. With `BC5_DIRECT_ALIASES` set, only whole BOs go.
- `reviewed`: the released chunks that a view covers again.
- `runs`, and `covered_end`, `insert_bo`, `apply_cut` and `undo_cut` on the BO list (a template over `DBo`).
- `note_cut`, `note_undo` and `note_back`. A cut chunk's record is dropped: imported again, it starts as never seen.

**The host's side**, `lzr_pass` and `lzr_confirm`.
- *Where.* One block between `direct_breakdown` and `g_scratch`, and two lines in `direct_sync_one`, the only existing
  function touched:
  - `LzrPass lzr = lzr_pass(S, views, sig, fd, now, merged, retired, remaps, merge_map_cap);` goes before
    `// 2. the views' addresses`, after step 1 and the merge;
  - `lzr_confirm(S, lzr, retired);` goes right after the step-2 drain, `t_maps0` / `g_dprof_drain_ns`.
- *Every full sync whose views changed* (while chunks are released): released chunks under a view again are imported
  as runs, at most `kDMaxBo` each. One that the eager or data path imported in this sync only leaves the released set.
- *Once per period, when the merge did nothing in this sync*, the pass:
  1. plans;
  2. imports each cut BO's kept runs first; a failure frees those and leaves the BO whole;
  3. replaces the BO in `S.bos` and pushes its id to `retired`, then lowers `S.bytes`.

  The existing code then drains (`wait_jobs`), rebuilds the mappings, and frees the old BO (`free_shared`).
- *`lzr_confirm`.* If `Device::wait_idle(0)` says a ring is still busy, every cut of the pass is undone: the new BOs
  were never mapped, so they are freed at once; the old BO goes back; its id leaves `retired`.
- *Unchanged:* exp 0379's zero skip, and the private memfd (kind 1).

**Functions.**
- *New, pure:* `Lzr0401::parse`, `apply_allowed`, `period`, `merged`, `hits`, `covers`, `due`, `plan`, `reviewed`,
  `runs`, `covered_end`, `insert_bo`, `apply_cut`, `undo_cut`, `note_cut`, `note_undo`, `note_back`.
- *New, host:* `lzr_opts`, `lzr_zero_skip`, `lzr_zero_name`, `lzr_pass`, `lzr_confirm`.
- *Touched:* `direct_sync_one`, two inserted lines. Nothing is replaced: the diff against `d1cfd9bb` is additions only
  (545 lines).

## 4. Safety argument

1. **A cut chunk has no GPU mapping.**
   - It is under no view of this sync's `views`, the same snapshot step 2 builds its wanted mappings from. So the
     rebuild maps nothing on it.
   - A whole BO that goes had no mapping left. A split BO's mappings move to the kept runs' new BOs, at the same VAs.
2. **Nothing changes under a running job.**
   - A cut puts the old id in `retired`, so step 2 runs `wait_jobs()` before any unmap or map. That is the merge's path
     (exp 0167, F222).
   - Then `lzr_confirm` requires every ring's last job to be signalled (`wait_idle(0)`), or it undoes the cuts. This is
     stricter than the merge, which goes ahead after `wait_jobs`'s 2-s timeout.
   - The old BO is freed after the rebuild by the existing loop. `free_shared` drops a kept BO list that still names it
     (`direct.cpp:960-968`).
3. **The GPU sees the same mappings as without the switch.**
   - A released chunk under a view again is imported in the same sync, after step 1 and before step 2. That sync is a
     full one: the fast path needs an unchanged views signature, and the 50-ms throttle never skips a change in the
     ranges' generation.
   - So at every rebuild, each viewed chunk that was ever imported is imported, exactly as today.
   - This also covers what the existing paths would miss: a lazy-name view, and `SEEK_DATA` over swapped-out shmem
     (TODO(verify) whether shmem reports swapped pages as data).
4. **Never released:**
   - forced chunks (hint and learned windows);
   - zero-list heaps, when `BC5_DIRECT_ZERO_SKIP` is set, read by name from `BC5_DIRECT_ZERO_NAMES` (exp 0379's default
     names), even with `eager`;
   - eager-heap chunks and never-seen chunks, without `eager`;
   - BOs that are not chunk-aligned;
   - private memory.

   The zero skip's skipped chunks are never imported, so they are never in `S.bos`, and its canary is a BO of its own
   outside `S.bos`. The two sets are disjoint by construction, and this block uses none of the skip's code.
5. **No data is lost.** Nothing punches the memfd. Unpinning leaves the shmem pages and their content where they are,
   and a re-import pins the same pages.
6. **Aliases.** With `BC5_DIRECT_ALIASES` set, only BOs with no kept chunk go. They have no mapping, so no aliases were
   made from them. `aliases_apply` makes the aliases again only once a second, the same exposure the merge has.
7. **Off:** one journal line at the first sync, then a return on a static check.

## 5. Journal lines

```
lazy release (exp 0401 e7): off (BC5_DIRECT_LAZY_RELEASE unset|empty|0|"…" does not parse: …)
lazy release (exp 0401 e7): on (30 s[, dry][, eager]): an imported chunk of the direct memfd under no view for 30 s, not forced by a hint or learned window, never one of an eager or zero-list heap, is cut out of its BO[ (dry: counted only, nothing cut)]; a view over it again imports it before the mappings are built; passes every 7.5 s
lazy release (exp 0401 e7): t 600 s: 11400.0 MiB imported: … under eager views, … under data views, … under lazy views, … forced and under no view, … under no view (… last seen under an eager or zero-list view, … never seen under one; … idle 30 s or more)[; dry, nothing cut]; cut … MiB in N BOs (W whole, S split), back … MiB, K chunks released now, U undone, F imports failed, D BOs deferred, A not split (aliases); GTT … of … MiB      (once a minute)
lazy release (exp 0401 e7): cut … MiB out of N BOs (M mappings to move); … MiB cut in all, K chunks released now      (first 16 passes that cut, then every 64th)
lazy release (exp 0401 e7): released chunks under a view again: … MiB imported now, … MiB imported by the eager or data path; K chunks still released      (sampled the same way)
lazy release (exp 0401 e7): import 0x… +0x… of released chunks under a view again FAILED (tried again at the next sync)      (first 16)
lazy release (exp 0401 e7): an import of the kept part of BO 0x… +0x… FAILED: the BO stays whole      (first 16)
lazy release (exp 0401 e7): a ring was still busy after the drain: N cuts undone (… MiB), tried again at a later pass
```

**Suggested order.**
1. `30,dry` in a play first. The minute line gives "under no view" split by class, so it measures what exp 0379 left
   as TODO(verify): how much of the pinned memory is no longer viewed.
2. Then `30`, or `30,eager` if the eager figure is the one that is large (AMM pages are eager).

## 6. Risks and costs

- **A re-import that fails** (import under memory or GTT pressure) leaves the view mapped without that chunk for that
  sync, so a GPU access there would fault. Today that chunk would still be pinned. The import is retried at every
  following sync, and the first 16 failures are journalled.
- **Game-thread time when on.**
  - Each pass that cuts drains the GPU, as a merge does: at most one per period, 32 BOs and the merge's leftover
    mapping budget.
  - A re-import pins the chunk again; pages swapped out meanwhile come back from zram inside `UDMABUF_CREATE`.
  - The views' covers are rebuilt per pass when the views changed: 5 sorted lists over about 19,400 views.
  - The chunk walk covers about 5,700 chunks, and the mapping count covers about 19,400 `S.maps` entries.
  - While chunks are released, the re-view check makes one `std::set::lower_bound` per view at each sync whose views
    changed.
- **The gain is not MemAvailable directly.**
  - Unpinned shmem stays allocated, and shmem does not count as available.
  - It becomes swappable, and GTT used falls.
  - The expected effect is that the kernel pushes cold pages to zram instead of evicting the page cache, which exp 0330
    found was the victim (9–11.5 M file pages stolen). TODO(verify) on the box.
- **Probably small for this title by default.** Its non-eager heaps are permanent single views. Unviewed chunks would
  come from AMM pages (eager), so they need `eager`. The dry line decides that before anything is cut.
- **Passes wait while the merge works** (`merged != 0`), mostly during the load.
- **GPU submission.** The switch changes which BOs exist and where they are mapped, through the merge's own Device
  calls (`import_memfd`, the rebuild's `map_shared`/`unmap_shared`, `free_shared`). It adds no packet and no
  submission. It is default off, and no test touches a GPU (CLAUDE.md hard rule 5).

## 7. Checks run (laptop, 2026-11-04)

- **The script on the e6 input.** `python -I mklzr0401.py <e6tree> <out>` on `d1cfd9bb` prints:
  - `src/libs/bc5LleAgc.cpp b8041214bb3e9cc60e2489d97913943c`
  - `src/libs/lzr0401.inc 97a6dcfe7010d937b1748e213f3e89c6`
- **Its own checks.**
  - The built-in undo (new to old, last first) gives the input back.
  - The anchors and the needed names (`DBo`, `S.forced`, `retired`, `merged`, `remaps`, `merge_map_cap`, the drain,
    the rebuild, the frees) each occur once.
  - The steps are checked to be in order in `direct_sync_one`.
  - The `.inc` occurs once, byte for byte, in the unit.
- **Refusals.** Run on its own output: "has the edit already" (rc 1). Another md5: "is not an accepted input" (rc 1).
- **Diff.** Additions only: 545 lines in three places (`1978a1979,2518`, `2133a2674,2677`, `2142a2687`).
- **After a simulated zsk** (patch0379 applied with `patch -p1 -F3` to a copy of `d1cfd9bb`, md5 `10c969ea`):
  - the edit applies (`edit(check_md5=False)`; out `aaed0c1a`);
  - the block lands before the skip's block, `lzr_pass` after `zskip_take_back`, and `lzr_confirm` before `zskip_map`.
  - **Note for zsk and the top:** `patch -F3` put hunk 10 (`zskip_disable("device reopen")`) into the memory-line
    thread, near line 6577 of the patched file, not into the reopen path. zsk's own script must place it.
- **Brackets** balance in the input, the output, the `.inc`, the test, the simulated skip unit and the chained unit
  (`balance_u8.py` with digit separators handled).
- **Syntax.** VS clang++ 22.1.3, `-std=c++20 -fsyntax-only -Wall -Wextra -Werror -D_CRT_SECURE_NO_WARNINGS`. The
  region checked is the unit from "ADR 0006" to the end of `direct_sync_one`, with the real types, the lzr block and
  the real `direct_sync_one`, against stubs of KytyPlus and the rest of the unit. It is clean for:
  - e6 + lzr: 1,056 lines;
  - the simulated zsk input: 840 lines;
  - zsk + lzr: 1,385 lines, with the real `bc5/zero_skip.hpp`.

  Under `-Wshadow -Wconversion -Wsign-conversion` the output adds no warning. The one left is the existing shadowed `e`
  in `direct_sync_one` (the eager-names line), which the input has too.
- **The CPU test.** `clang++ -std=c++20 -Wall -Wextra -Werror -I<out>/src/libs lzr0401.cpp` builds, and also with
  `-Wshadow -Wconversion -Wsign-conversion`: 0 warnings. The MSVC target needs `-D_CRT_SECURE_NO_WARNINGS` for
  `getenv`. Its results:

  | Run | Result |
  |---|---|
  | `BC5_DIRECT_LAZY_RELEASE=1 lzr0401 on` | `lzr0401: on 30 of 30; end`, 152 checks |
  | `=0 lzr0401 off` | `lzr0401: off 30 of 30; end`, 151 checks |
  | unset | `lzr0401: off 30 of 30; end` |
  | `""`, `30`, `30,dry`, `5,eager`, `30,dry,eager`, `abc`, `0,dry`, `30,foo` | each on or off as parsed, 30 of 30 |
  | an argument that disagrees | rc 2 |

  The box's end-marker regex matches all three of on, off and unset.
- **Mutation check** (scratch, not committed): 25 mutants of `lzr0401.inc`, all caught. They are:
  - no forced check;
  - `>` for `>=`;
  - the eager word, the zero list, never-seen or the zero skip ignored;
  - `reviewed` not aligned down;
  - `hits <=`;
  - a kept run's end;
  - `note_cut` keeping records;
  - `undo_cut` without its coverage check;
  - `since` kept under a view;
  - the budget not spent, or splits ignored;
  - 0 seconds accepted;
  - no clock guard;
  - the class order swapped;
  - touching ranges not joined;
  - `runs` without a limit;
  - `apply_cut` without its id check;
  - `period` not clamped;
  - off planning;
  - dry cutting;
  - `note_back` counting twice;
  - the cut count ignored.

## 8. Not checked

- **Not compiled, linked or run on the box:**
  - GCC on the box;
  - the full unit (the KytyPlus headers are not on the laptop, lesson R02);
  - the link;
  - the `--gate lzr0401.cpp … --like src/libs/bc5LleAgc.cpp` build;
  - any run with the GPU.
- **zsk's real output.** It does not exist yet. The chain was tried on a `patch -F3` simulation only. The top session
  adds zsk's output md5 to `INPUTS`, the one dict.
- **Kernel behaviour, TODO(verify):**
  - that dropping the udmabuf (BO free) unpins the shmem pages so that they can go to zram;
  - shmem's `SEEK_DATA` over swapped pages (the re-view import covers both cases).
- **Sizes not measured:**
  - the size of unviewed chunks in play: the dry line is the measurement;
  - the e6 play's own memory record: the top session's figures are quoted, and no file is on the laptop.
- **Box rows the top session will need** (`box0401.sh`):
  - *E7_EDITS:* `"lzr mklzr0401.py - src/libs/bc5LleAgc.cpp:<zsk out>:<lzr out>"`.
  - *E7_GATES:* `"lzr0401.cpp src/libs/bc5LleAgc.cpp BC5_DIRECT_LAZY_RELEASE lzr0401"`.
  - *E7_STRS:* `BC5_DIRECT_LAZY_RELEASE` and `lazy release (exp 0401 e7): off (BC5_DIRECT_LAZY_RELEASE %s)`.
  - *The `.inc`.* `box0401.sh` copies `*.inc` into `$E/src/` only from the directory of the *last* main-unit script.
    With `cap` after `lzr`, `x5-lzr/src/libs/lzr0401.inc` must be copied to `$E/src/` too, or cap must pass it on. The
    unit itself carries the block inline and does not need it.

## 9. Files

| File | md5 |
|---|---|
| `mklzr0401.py` (new) | `d7d8e53eedf499f1017b1ad8e3c436f8` |
| `lzr0401.cpp` (new) | `4aec5ee7f08708a9a2d0779636e3dc4d` |
| `lzr0401-notes.md` (new) | this file |
| in: `src/libs/bc5LleAgc.cpp` (the e6 chain's final unit) | `d1cfd9bb1f1b3485bed4207a7f064d4f` |
| out: `src/libs/bc5LleAgc.cpp` (from the e6 input) | `b8041214bb3e9cc60e2489d97913943c` |
| out: `src/libs/lzr0401.inc` | `97a6dcfe7010d937b1748e213f3e89c6` |
| read only: `backend/src/direct.cpp`, `backend/include/bc5/direct.hpp` | for the BO list and `free_shared` (worktree copies) |
