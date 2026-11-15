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

### 1b. After n16A2 (the guardian's measurement relayed by the top, 12:41; one walk, chance not excluded)

The setting:
- [M] (as relayed) W with FileSystem imported, 3 minutes after a fresh boot.
- 1 frame with prepare >200 ms, against 32 in n15's 16 walks on a boot hours old.
- The longest gap was 589 ms. Lowest available memory was 963 MiB, against 673–857 in n15.
- So the premise moves: the stalls are not a fixed price of the import. They look like a price of the system's state.

Costs that grow with memory pressure or fragmentation, as the code places them:

| Where | What can grow with pressure | Booked as | Source |
|---|---|---|---|
| `Device::import_memfd` (`UDMABUF_CREATE` + `amdgpu_bo_import`) **under the device mutex** | holes in the chunk are allocated by shmem at pin time (order 0, direct reclaim near the wall); `memfd_pin_folios`' migrate loop; four or five `kvmalloc` arrays per buffer, order 5 for 64 MiB (merges), order 0 for a 2 MiB import | "sync" on the importing thread; **every other submitter waits at the device mutex before `t_enter`**, so not in its "prepare" | backend `import_memfd`; exp 0412 §58 (3) |
| merge pass (`ls415_import` of up to 64 MiB runs, every 250 ms after a 3 s settle) | the order-5 arrays above, a new pin of already-pinned pages, up to 512 remaps | "sync" | unit `direct_sync_one` 1b; §58 |
| `wait_jobs()` after a new BO with K1r on | not pressure itself; the GPU drain lengthens with what is in flight | "sync" | unit `direct_sync_one` 2 |
| **inside "prepare"**: `scratch_reserve` (a job larger than its slot: `amdgpu_bo_alloc` GTT + VA map + CPU map), the snapshot ring's first allocation | TTM pool: high orders with `__GFP_NORETRY`, then **order 0 with direct reclaim**; page-table BOs for the VA map | "prepare" (copy part) | backend `scratch_reserve`, `snapshot`; §58 (TTM) |
| **inside "prepare"**: CPU reads of guest memory (filter, DMA snapshot copies of ≥4 KiB `dcb` sources, nested IBs, host-indirect and tracker loads) | a swapped-out or reclaimed shmem page (unpinned memory: zram swap-in); `mmap_lock` held by another thread's mapper | "prepare" (filter, nested, copy) | backend `submit`; unit `opt.mapped` |
| THP | none: the guest memfd has no huge pages (`shmem_enabled` `never`, ShmemHugePages 0, exp 0412 near line 798); not re-read on today's boot | — | |

[I] So a 1–4 s "prepare" fits a game thread that waits in the kernel for memory at the wall:
- either in its own `scratch_reserve`, or in a page fault on unpinned guest memory;
- while imports, merges and the title's own loading compete for the same free pages.

FileSystem's import would then be one more allocator at the worst moment, not the stall's own path. That is not
shown.

The reads that would tell, without a new run except the next one already planned:
1. The prepare split of the stall frames (as above).
2. Beside the next walks, the read-only collector `compact0412.sh` (exp 0412 §59): `allocstall_*`,
   `compact_stall`, `pgmajfault`, `pswpin` and buddyinfo as deltas around each stall.
3. The `shmem_enabled` value on this boot.

### 1c. After the guardian's PSI reading (relayed by the top; old logs)

The reading as relayed [M]:
- PSI memory "full" avg10 was 4–14 in W's stall seconds and 0.1–2.3 on W walks without stalls.
- U had PSI 4–8 at load and no stall.
- Free memory on the stalling W walks was not lower than on U.

The guardian's inference, "W's import work **in prepare** meets a reclaim or compaction stall", needs one
correction from code:
- [read] There is no import or pin in "prepare". The import (`import_memfd`) is a separate device call under the
  same mutex, booked as "sync"/"hints" (section 1).
- What "prepare" itself asks of the kernel:
  - (i) **`scratch_reserve`**. There are 128 slots in rotation, and each slot's GTT BO is freed and allocated again,
    larger, when a job does not fit it (`amdgpu_bo_alloc` + VA map + CPU map). New, larger jobs at a load therefore
    cost up to one allocation per slot as the rotation reaches it.
  - (ii) The 64 MiB write-combined **snapshot ring**, allocated once at the first `dcb` `DMA_DATA` of 4 KiB or more
    (TTM pool, high orders first).
  - (iii) Page faults on unpinned guest memory read by the filter, the nested copies or the snapshot copies.
- All three wait when the kernel reclaims or compacts. None of them is FileSystem's.

[I] A reading that fits every number relayed so far:
1. W's sync pass (the same submission, just before its prepare) imports FileSystem chunks.
2. Each import allocates shmem pages and kernel arrays and so starts reclaim or compaction.
3. That submission's prepare (or the next) then needs a GTT allocation or a faulted page in the same moment, and
   waits.
4. U had the pressure but not the extra allocations.

Not proven: PSI "full" may be the stall's effect, and the prepare split of the stall frames has still not been read.
If the split shows the time in "copy", it is (i) or (ii). If it shows it in "filter" or "nested", it is (iii).

**Option E, title-independent and complementary:**
- Take the kernel allocations out of "prepare": each slot's scratch BO grows only in large steps (for example to
  the next power of two, at least 1 MiB) and never shrinks; the snapshot ring is allocated at device open, not at
  the first copy.
- The PS5 has no such step (its command buffers are the title's own memory), so this is about our host only.
- Cost: up to about 128 MiB of GTT at worst if every slot reaches 1 MiB. A smaller step, or growth only for the
  slots of the GFX pool, would cost less.
- It is not prepared as code: whether it addresses the stall at all depends on the split read. It is a backend
  change (`direct.cpp`), shared by both titles.

On the peer's suggestion "async or background import, or import only what the GPU references":
- Moving imports off the game thread does not shorten its prepare directly. A submitting thread already waits for
  the device mutex while another thread imports.
- It helps only by moving the allocation burst away from the game thread's own allocations.
- B (late import) does that in time instead of by thread, without a new thread or locking. C (import by reference)
  is still blocked by section 101: the address came from a record deeper than any level we follow.

## 2. Alternatives: less pinning work at load (none removes the cause of the fault: the title gives the GPU an address in FileSystem)

After n16A2 the aim is put as "less allocation and pinning work during the loads, when memory is tightest", not as
"FileSystem's import is the cause". Each option below is judged by what it moves out of the load windows.

| | What | Does the PS5 do this? | Cures n13P4's case | Load stalls (under the FileSystem hypothesis) | Risk / cost |
|---|---|---|---|---|---|
| A | FileSystem **eager** by name: the whole view (52 MiB, 26 chunks) is imported once, when it appears, as one BO; no import per write and no merges. No code: an arm word `BC5_DIRECT_EAGER_NAMES=<launcher's list>,FileSystem` (eager is tested before lazy in `direct_sync_one`) | **Yes**: on the console all of the title's memory is GPU-readable from the map call | yes | gone if the stall is churn per write (many small imports, drains, merges); stays if it is "FileSystem mapped" itself (path a); one import if the view appears during a load | +4 MiB against W (2 unwritten chunks); not what the maintainer asked for ("without importing the whole heap at load") if the heap is created at a load, which is not known |
| **B** | **Late import** (`BC5_DIRECT_FS_LATE`, this step): the heap stays lazy as on U; a written chunk is imported once it has been seen written for the delay (30 s), one chunk a pass, passes ≥ 250 ms apart | **No.** For the delay, written FileSystem data is not GPU-readable (U's state). n13P4's read came about 580 s after the write (written by 148 s, read at 731 s) | yes for that case (imported by about 180 s); a read inside the window faults by name, as on U | none of FileSystem's imports or mappings fall in the load that wrote it; later loads can still meet a late import (a write at 92 s is imported at about 122 s) | ≈60 lines; one drain and rebuild per late chunk, spread out; the pin is W's in the end |
| C | **Import on reference**: dt412 (`BC5_GUARD_DESC_TARGETS`, section 94) extended to scan the record a buffer descriptor points to for addresses in lazy views | No: the console has no import step; this guesses the GPU's reach | **unknown**: section 101 shows the address came from inside the 0x78-byte item record or deeper; the depth is not known | no import at load unless a load's submissions name it | a scan per submission (766 dispatches in one acb); false positives import more; misses deeper levels |
| D | Async pin: udmabuf creation on a worker, the mapping in the next sync | Not applicable | as W | only the udmabuf create moves off the path; the drain and the mapping rebuild stay under the device mutex | a large change to the direct path; not proposed |

**Chosen for the code step: B.** It keeps every FileSystem import, merge and mapping change out of the load that
wrote the chunk, when free memory is lowest. About 24 udmabuf creates and their merges then run in quieter seconds.
The pin at the end is W's: B saves no memory, it moves the work.

What B decides:
- If W's stalls stay with B on, FileSystem's import work is not their trigger, and W's plain fix can stand.
- If they go, the import work at load is the trigger, even though the mechanism is memory pressure.
- After n16A2, the arms must also run on a comparable boot age, or the boot's state decides the comparison.

**A needs no code.** It is the more console-like answer and is section 58's "buffers made once, at their final size"
for this one heap: one buffer of 52 MiB, whose arrays are 104 KiB (order 5) once, instead of 2 MiB imports
followed by merges into 64 MiB runs. It can run as a fourth arm by its launcher word alone.

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

After n16A2:
- Run the arms interleaved on one boot that is already hours old (n15's state), or record the boot's age and
  lowest available memory per walk and compare like with like. A fresh boot hides the stalls (1 frame against 32).
- Run `compact0412.sh` beside the walks.

**Verdict.** Not yet: a design and a prepared step; nothing measured on the box.

## 4. Review of the old experiments and the decision (2026-11-15 afternoon; the maintainer: "przejrzyj wszystkie stare eksperymenty – sprawdź czy Twoje wnioski są słuszne – jeżeli tak – od razu wprowadzić rozwiązanie zamiast W")

A sweep of `experiments/*/README.md`, `docs/HANDOFF.md` and the 0412 branch, each fact checked against its line:

| My claim | Verdict | Evidence |
|---|---|---|
| "prepare" holds no import; imports are "sync"/"hints" | **holds** | backend `direct.cpp` `t_enter`…`r.prepare_ms`; 0412 §102 now says the same; no experiment puts an import in prepare |
| `scratch_reserve` is booked as "copy", the DMA snapshot as "filter" | holds (code) | `direct.cpp` around `scratch_reserve`; the snapshot is a filter callback |
| The named parts do not cover all of prepare | **added** | the BO vector's build is inside prepare in none of them (exp 0170 README lines 11–12, 28) |
| FileSystem is CPU-only, so lazy or late is safe | **wrong** | F443 (HANDOFF line 497): a TCP **write** fault at 0x1110e1d000, inside FileSystem (0x1110000000+0x3400000), then a hang at 107 s. F468: never imported because lazy. F472 (exp 0364): a dispatch's user-data pointer lands in FileSystem. F443's pointer was later tied to a garbage high dword (F679/F685), but the title does give the GPU FileSystem addresses |
| A window of written-but-unmapped memory is harmless | **not safe** | 0412 §33: the zero skip's 59–149 ms blind window ended in a ring timeout; there a canary was mapped, but it is the same class of risk |
| The stalls are the price of FileSystem's import | not shown | n16A2 (fresh boot: 1 frame against 32), PSI full 4–14 at W's stalls, and U at PSI 4–8 without stalls point to memory state plus import work at the same moment [I] |

**So B (late import) is dropped.** Its 30 s window would leave GPU writes and reads into written FileSystem chunks
unmapped, and the title is known to aim GPU work there. **A (eager) is the step**, written in code so that the
launcher is not touched:
- the name is added where `BC5_DIRECT_EAGER_NAMES` is read;
- the whole view (52 MiB) is imported once, when it appears, as one buffer;
- after that, writes to it cost no import, merge or remap.

The PS5 does this: every page of the heap is the GPU's from the map call. Cost: +4 MiB pinned against W (the two
never-written chunks), and no pinning work for this heap during the later loads.

B's files stay here, unused: `mk0421b-late.py`, `late_import.hpp`, `test0421late.cpp`, `standin0421b-late.cpp`,
`fs421b-late-on-T-lazyfs.diff`, `b0421b-late.sh`.

**One correction to the rules as relayed**: the lean build defines `BC5_LEAN` (`add_compile_definitions(BC5_LEAN=1)`
under `if(KYTY_BC5_LEAN)`). A `#ifndef KYTY_BC5_LEAN` guard would leave its code in lean. Both generators use
`#ifndef BC5_LEAN`.

### The step (tag fs421e)

- `mk0421.py <tree root>`: 2 edits of the main unit. It refuses a tree without V's lazyfs step or one that already has
  the step.
- `BC5_DIRECT_FS_EAGER` is **on by default**; `=0` gives W's way (imported by data, never lazy).
- `BC5_GUARD_BYDATA_NAMES` still wins (bd412). The stderr line is under `#ifndef BC5_LEAN`.
- [M] It was applied to the unit cut from the shared patch `101555c7` (the integrator's laptop kit, blob `358419d`)
  → `5956804d`; the diff is `fs421e-on-101555c7.diff`, 35 lines.
- [M] `standin0421.cpp` (the changed region with stand-ins for `bc5::env_on` and `BC5_DIAG_ENV`) builds in both modes
  (`-Wall -Wextra -Werror`) and runs as intended:

| | eager(FileSystem) | lazy(FileSystem) | stderr line | `fs421e` text in the binary |
|---|---|---|---|---|
| normal, default | 1 | 0 | yes | 1 |
| normal, `=0` | 0 | 0 | yes | 1 |
| lean, default | 1 | 0 | none | 0 |
| lean, `=0` | 0 | 0 | none | 0 |

### The shared swap (the top's GO after the integrator's swap to 101555c7)

`int0421.sh` (kit: `mk0421.py`, `undo0421.sh`, and `ed0419g.py` from exp 0419), with
`PIN_OLD=101555c7`:
1. Checks: no emulator, and the shared tree's diff is `PIN_OLD`. Takes the lock (one line).
2. Copies under `~/bc5-work/exp0421/swap`: both binaries, the unit and the patch (`*.before-0421`), read back.
3. Runs `mk0421.py` and makes the new patch with `git diff f266548`. The new patch must keep:
   - `exp 0372` lines = 5;
   - the same file list;
   - the same counts of `BC5_GUARD_MAP_RULE`, `BC5_GUARD_PRT_BG` and `learned` lines.
4. Rebuilds normal and lean in place; the backend archive must not change.
5. `strings`: no switch word gained or lost in either build; no `fs421e` text in lean, present in normal.

Any failure runs the undo, `bash ~/bc5-work/exp0421/undo0421.sh`: the unit and both binaries go back and are checked
by md5; the unit is touched so that the next ninja recompiles it.

### Fixed, no switch (the maintainer, 2026-11-15: "BC5_DIRECT_FS_EAGER => wbudowany w kod a nie przełącznik i włączony")

This supersedes the switch described above.

- `mk0421.py` now makes one edit: "FileSystem" is always added to the eager list where `BC5_DIRECT_EAGER_NAMES` is
  read. `BC5_DIRECT_FS_EAGER` does not exist.
- V's lazyfs step is unchanged, so FileSystem is never lazy. `BC5_GUARD_BYDATA_NAMES=FileSystem` (bd412) is the only
  word that still makes it by data.
- [M] On the unit of 101555c7 (blob `358419d`) the result is `747709d3`. A second run is refused. The diff is
  `fs421e-on-101555c7.diff` (17 lines).
- [M] `standin0421.cpp`, normal and lean, `-Wall -Wextra -Werror`:
  - eager(FileSystem) = 1 and lazy(FileSystem) = 0 in three cases: with the launcher's eager list, without it, and
    with `BC5_DIRECT_FS_EAGER=0` set (ignored);
  - other names are unchanged;
  - the `fs421e` text is in normal only;
  - no new switch word in either binary.
- `int0421.sh` step 5 now requires both binaries' switch words to be unchanged.
- The top's condition "`=0` must give exactly W's way" no longer applies: there is no `=0`. Going back is
  `undo0421.sh`.

## 5. The shared swap (2026-11-15 13:06–13:07, the top session's GO; compile only)

`r0421.sh kit` then `PIN_OLD=ba617454 r0421.sh run`. One lock line, taken at 13:06:17 and released.

| | before | after |
|---|---|---|
| patch 0001 (tree diff against f266548) | `ba617454` (W + menu + Recent fix) | **`e3fd8b55`** (12 lines differ; unit blob `747709d`, as predicted on the laptop) |
| shared normal `~/bc5-work/kytyplus-build` | `fd3d0ed2` | **`50d0885e`** (7 warnings, none naming fs421) |
| shared lean `~/bc5-work/kytyplus-build-lean` | `480656cc` | **`7998d6a4`** (8 warnings, none naming fs421) |
| backend archive | `9aab722c` | `9aab722c` (unchanged) |

Checks, all [M] by the script:
- `exp 0372` lines: 5.
- The patch's file list is the same.
- The counts of `BC5_GUARD_MAP_RULE`, `BC5_GUARD_PRT_BG` and `learned` lines are unchanged.
- Switch words: no word gained or lost, in either binary.
- The `fs421e` text: 1 in normal, 0 in lean.

What was not done: no emulator start and no walk. The maintainer asked for a compile check only.

- Copies: `~/bc5-work/exp0421/swap/*.before-0421`.
- **Undo:** `bash ~/bc5-work/exp0421/undo0421.sh`. It restores the unit and both binaries and checks them by md5;
  `0001` on main then goes back to `ba617454` (git revert of 0affa36f).
- Main: 0affa36f, patch 0001 = `e3fd8b55`.
