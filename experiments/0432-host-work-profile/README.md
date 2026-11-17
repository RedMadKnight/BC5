# Experiment 0432: host work per submission: profile, then remove what is not needed

Status: **in progress** (2026-11-17). Nothing below is a result yet except where a source is named.

## Question

On the shared builds of 2026-11-17 09:49 (patch `bc39a035`, normal `0de9349b`, lean `63fda02d`, archive `1423af83`;
way 2 on 4 compute rings, exp 0430's cross-queue fix, no JobArenaFix): where does the host's own time go per frame
for the second title, and which per-submission and per-dispatch host work can be removed with no change of what the
GPU runs?

Measure first, delete second. Every earlier profile (exp 0360, 0412 sections 24-25, 0415 sections 13-16) was taken
on one GFX ring, where the frame was GPU-bound and CPU-only cuts gave 0 flips/s (F470, F482, F483). Way 2 moved the
bottleneck, so those shares are re-measured here and not assumed.

## Setup

- Route: exp 0430's `run0430f.sh` (a02c3b95) derived by `mkrun0432.py` into `run0432f.sh`: own directory
  `~/bc5-work/exp0432/n`, own lock and queue lines, `N_SIDE` (a side process from G, only its own pid signalled) and
  `N_TIMED=1` (the route by time for the lean build, which writes no journal for the frame gate).
- Profiler: `prof0432.sh` (side process): per-thread utime/stime and schedstat every 5 s from `/proc`, the DRM
  fdinfo engine times every 5 s (GPU busy per engine), and `perf record -e cpu-clock:u -F 199 -p <pid>` in the
  ubuntu container. No ptrace, no signal, `perf_event_paranoid` untouched (2: user space only; kernel time is read
  per thread as stime, not by symbol).
- A run with the profiler beside it is not a speed measurement (the top session, 2026-11-17). Profile runs and A/B
  runs are separate.
- Scenes: the long route (fight record, then exp 0379's walk; slot 4 of exp 0425's named snapshot) and the
  maintainer's 09:46 scene (`~/bc5-data/saves/PPSA03671-20261117-0946-play`, read-only, slot 4, no input). RT on.

## Inventory (offline, from patch bc39a035; costs to be filled from the profile)

What the **lean** build still reads from the environment in `bc5LleAgc.cpp` (plain `getenv`, so the word and its
code are in the binary): `BC5_GC_MODE`, `BC5_DIRECT_CHAIN`, `_JOURNAL_QUIET`, `_AMM_PRT`, `_LAZY_NAMES`,
`_EAGER_NAMES`, `_LAZY_RELEASE`, `_ALIASES`, `_FLAT_APERTURE`, `_REMEMBER_UNMAPPED`, `_DMA_SYNC`, `_DMA_SNAPSHOT`,
`_INDIRECT_DRAWS`, `_MEC_INDIRECT`, `_GPU_CHECK`, `_CS_PREFIX`, `_FLIP_DEFER`, `_ACB_RINGS`, `_ACB_QUEUE_STATE`,
`_ACB_MEC_INDIRECT`, `_ACB_STATE_NO_WALK`, `_ACB_SPLIT_LATE`, `_XQ_PENDING`, `_XQ_ACQUIRE`, `_XQ_FENCE`,
`BC5_GUARD_SPLIT`, `KYTY_BC5_RT`; in the backend (`direct.cpp` 508-530): `_SHADOW_LABELS`, `_GPU_CHECK_PRODUCT`,
`_HOST_INDIRECT`, `_DRAW_ARGS_JOURNAL` (unset in lean), `_IB_MAX_DW` (ignored).

Work `submit_now` does on every submission under the device mutex (line numbers of the extracted `bc5LleAgc.cpp`):

| # | Work | Where | Why it exists | First read |
|---|---|---|---|---|
| W1 | heavy/light scan; for a light buffer a full filter pass into a scratch vector, result thrown away | 14763-14811 | to skip the forced anonymous sync (exp 0037, run 82) | goes if the anonymous walk goes (0412 audit A3, B4) |
| W2 | second walk of a light buffer + 2 s page memory | 14785-14808, 14820-14829 | `REMEMBER_UNMAPPED`, exp 0103 | narrowing of W1 |
| W3 | `sync_mappings` (the `/proc/self/maps` walk, at least once a second) | 14817 | guest memory used to be anonymous; "stays as a check" | 41-43 ms a walk, finds nothing (0415); candidate |
| W4 | `direct_sync` (fstat per memfd per submission, full path on change or 250 ms) | 14819 | no event for a first write | needs the map-time design; not here |
| W5 | `learned_apply` / `hint_targets` | 14840, 14847 | render-target windows | to measure |
| W6 | `aliases_apply(false)` | 14888 | F-alias windows | to measure |
| W7 | the indirect/program walk: every packet; LOAD_SH_REG_INDEX tables read twice (once only to ask `loop_bound_copy`, whose switches are unset) | 15052-15280 | exp 0038/0050/0052/0054/0059/0137/0159 | the duplicate table read and the argument read under `GPU_CHECK` decide nothing (0412 audit B10) |
| W8 | two `g_carried_mutex` locks, a `std::map` and several vectors allocated per submission | 15017-15030, 15281-15287 | carried CP state (exp 0161) | micro; to measure |
| W9 | MEC rebuild of an acb kept on the GFX ring | 15398-15475 | exp 0038, one ring | under way 2 only acbs refused a compute ring |
| W10 | backend: filter copy, tracker, CU tables, nested survey, slot copy | `direct.cpp` 1109-1443 | the rewrite | already timed per part (`prep_*_ms`) |
| W11 | `register_label_writes` + `ho430::job_submitted` + `f3_before_submit` | 15504, 15668-15669 | exp 0055, exp 0430 | F5 (exp 0430) owns the fence part |
| W12 | normal build only: `TIMEOUT_PROBE` copy of the whole buffer per job, uncached `BC5_DIAG_ENV` call | 15637 | diagnostic | normal only |

Switches whose reason may be gone under way 2 (to check in code, then by an arm; none is removed on this list alone):
`BC5_DIRECT_CS_PREFIX` (superseded by `ACB_STATE_RESTORE` / `ACB_QUEUE_STATE`?), `BC5_DIRECT_MEC_INDIRECT` (GFX-ring
form; way 2 has `ACB_MEC_INDIRECT`), `BC5_DIRECT_REMEMBER_UNMAPPED`, `BC5_DIRECT_GPU_CHECK_PRODUCT` (F414/F415, one
ring), `BC5_DIRECT_SHADOW_LABELS` (F414/F415), `BC5_DIRECT_DMA_SNAPSHOT` (F146), `BC5_DIRECT_HOST_INDIRECT`.
Earlier candidates never integrated: `emit_prefix` byte-identical cut (F483, -80 % of its CPU), `piece_check` tracker
copy (audit 0406).

### Cost guesses before the profile, with their evidence

All figures below were measured on ONE GFX ring, before way 2 (exp 0428); they are guesses for today's builds and
rank what the profile looks at first. "Audit" is exp 0412's read-only audit of copies and re-reads (the top session's
notes folder, `exp0412-redundant-copies-audit.md`, sections 3 and 4).

| Rank | Item | Guess | Evidence | Removal risk |
|---|---|---|---|---|
| 1 | W3 + W4, the two syncs under the device mutex | large in long frames: 15-33 % of frames spent 28-39 ms under the mutex (anon sync 11-16, direct sync 11-20, learned 3-8 ms) | exp 0415 README sections 15-16; the walk itself 41-43 ms, 82-85 a minute, "finds nothing" (exp 0415); learned windows are gone since exp 0413/0417, so that part is already 0 | W3: low if a run shows no anonymous guest VMA (it becomes an assert); W4: design work, out of scope here |
| 2 | state prefix (`emit_prefix`, `apply_level`, `state_stack`) | 27.5 % of the direct path's CPU in the fight; 2.9 + 2.2 + 0.9 % of the Render Thread over a run | F482, F483; exp 0412 section 24 | none for the byte-identical cut C1 of F483 (-80 % of its CPU), which gave 0 flips/s on one ring and was not integrated |
| 3 | W10, the backend's filter copy and its passes | `policy::filter` 1.4 %, `indirect_check` 1.5 %, `memmove` 5.3 % of the Render Thread | exp 0412 section 24; audit A1, A2 | the copy cannot go while packets are rewritten; single passes can be merged |
| 4 | W1 + W2, the throwaway probe pass of light buffers | unmeasured; one extra filter pass + a vector per light buffer | audit A3, B5 | goes with W3 |
| 5 | W7, the indirect/program walk with its duplicate table read | unmeasured; one walk of every buffer, each LOAD_SH_REG_INDEX table read twice | audit "Shader code" note and B10; this file's table | none for the duplicate read (`BC5_DIRECT_LOOP_BOUND` and `BVH_MISS` are unset) |
| 6 | W11, label registration and exp 0430's bookkeeping | F4 made 213k duplicate fence dependencies per run; F5 removes 99.8 % of the waits, +3 flips/s in the 09:46 scene | exp 0430 README (branch `exp/0430-hang-catcher`) | owned by exp 0430, not touched here |
| 7 | `piece_check` tracker copy | about 6 µs per dcb | audit 0406 (gpu-sync), C2 "proven equivalent, not built" | none |
| 8 | W8, W9, W6, W5 | unmeasured, expected small | audit sections 1, 3 (A6), 4 (B6) | W9: only acbs refused a compute ring take it now |
| 9 | W12 (normal build only) | unmeasured; "plausibly the largest left" of the logging costs | audit 0406 (logging); audit A4 | none: diagnostic; the lean build has no such copy |
| - | GPU-side guards: `GPU_CHECK` | 0.8 ms of GPU time a frame | F439 | kept: it replaced host checks on stale values (exp 0052, 0054) |
| - | host threads | emulator 4.3 of 16 CPUs: title 3.4, host 0.9 (`bc5-ring` 27 %, `kyty-gpu` 11 %, `bc5-chainwd` 7 % of a core); `kcompactd0` 30 %+ of a core | exp 0412 section 25 | the ring thread's doorbell poll (200 µs to 1 ms) and its re-walk of pending acbs: audit B8 |

GPU side, one ring: an ordinary frame was 34 ms with 24-26 ms of our jobs on the GPU; stretches with none of our
jobs running were 5.7-7.2 ms before `submit_now` (4.4-5.3 the title, 1.2-1.3 our chain) and 2.2-4.2 ms inside it
under the mutex (exp 0415 sections 13-14; the earlier "5.4-6.5 ms idle" figure was withdrawn there, LESSONS R13).

### Item D (from exp 0430, 2026-11-17): the submit path waits for an idle GPU before a mapping change

Reported by the top session from exp 0430's Q1 run (t 559, `play-20261117-1245` on the box, not read by me): the game
thread stood 1.07 s in submit preparation at a "maps +0 -6" change.

**Where it waits** (code, patch bc39a035, extracted `bc5LleAgc.cpp`):
- `direct_sync_one` 4561-4564 calls `wait_jobs()` when BOs were retired (a merge, every 250 ms at most; a lazy-release
  cut), when the view set's signature changed (any guest map or unmap, additions included), or on a guard change.
- `wait_jobs()` 14283-14288 flushes the thread's chain and calls `Device::wait_idle(2 s)`; `wait_idle`
  (`backend/src/direct.cpp` 1658-1667) waits for the LAST submitted job of the GFX ring and of each of the 4 compute
  rings in turn, up to 2 s each.
- It runs on the submitting thread inside `submit_now`, under `g_dev_mutex` (14734), for every buffer with a draw,
  dispatch or nested IB. `sync_mappings` pass 1 has a second call site per stale anonymous mapping (exp 0415 C3).
- The wait is for the whole device, not for the 6 mappings that go.

**Why 1 s is possible now and was not before** (my inference, not shown by a log): while the thread waits it holds
`g_dev_mutex`, so no other thread can submit. Since exp 0428 (`ACB_SPLIT_LATE=3`) a dcb job can sit on the GPU in a
WAIT_REG_MEM for a label that an acb of another queue writes; if that acb is not yet submitted, its submitter needs the
mutex the waiter holds. The wait then ends only when the label is met some other way or at the 2 s limit. On one ring
this could not happen: such waits were served on the CPU before the submit.

**How often, how long** (existing records; all on one ring, none under way 2):
- exp 0415 README section "C3" and line 379: `wait_jobs` 0.03-0.07 s in every load phase, "C3 is refuted as a cost";
  per-job window: the drain 0.3-0.6 ms (line 914).
- exp 0412 README about line 3220: 1,482 and 1,674 drains counted in two runs.
- His scene and the route on today's builds: not on the laptop. The profile slot's normal runs write
  `KYTY_BC5_FRAME_STAT` lines, whose field ds[3] is this wait per submission; that gives count, total and the longest
  per scene with no extra run.

**Can a deferred unmap replace it?** Split by what changes:
1. Additions only ("maps +N -0"): nothing in flight can name a mapping that did not exist. No wait is needed. Today
   the signature test drains anyway. Simplest cut, no new mechanism.
2. Drops with no reuse of the address ("-M", the guest unmapped or a lazy cut): keep the mapping and the BO on a
   retire list and take them out at the next point where nothing is in flight. The flip's `drain()` (14265-14271) is
   already such a point every frame, so the retire costs no new wait. Memory comes back at most one frame later.
3. A wanted mapping at an address still on the retire list, and merges (the same address moves to a new BO): the
   address is reused, so the old mapping must go first. Options: the blocking wait as today (counted, expected rare),
   or `AMDGPU_VA_OP_REPLACE` for the merge, where the pages behind the address do not change. TODO(verify): that the
   box's kernel orders the page-table update of a VA unmap/replace against the VM's in-flight jobs (amdgpu_vm.c);
   until it is read, form 3 keeps the wait.
`lzr_confirm` (a cut stands only when every ring is idle) moves to the same retire point.
Risk: a mapping kept one frame longer names pages the guest has freed; the memfd keeps them alive while a BO imports
them, so a late GPU read sees old data, not a fault.

**What was built (`mkd432.py`, `d432.diff`):** not a host retire list. The wait is dropped and the kernel defers the
unmap; switch `BC5_DIRECT_UNMAP_NOWAIT` (unset or not "0": no wait; "0": the old `wait_jobs()`), counters on stderr and
in the journal at most every 10 s. The three cases above collapse into one: additions, drops and replacements at the
same address are all ordered by the kernel behind the jobs in flight.

**Two checks before the first D run (the top session's order, 2026-11-17).**

1. *Why the wait exists.* It came with commit 01113ae7 (2026-10-01, exp 0024, run 110). `experiments/0024-jobs-in-flight/README.md`
   lines 81-90: "A second fault of the design, found by reading rather than by a symptom: the direct mapper replaced mappings
   (merged imports, views gone) while jobs that might use them were still running; the kernel clears the page-table entries
   of an unmapped range at once." No fault and no corruption was seen; the premise was not sourced. The driver's code says
   the opposite (below).
2. *The kernel, at tag v7.3* (torvalds/linux, read 2026-11-17 through raw.githubusercontent.com; the box runs 7.3.3-ogc, a
   vendor build whose own source was not read):
   - `amdgpu_vm.c` `amdgpu_vm_clear_freed()`: "Implicitly sync to command submissions in the same VM before unmapping",
     `amdgpu_sync_resv(adev, &sync, vm->root.bo->tbo.base.resv, AMDGPU_SYNC_EQ_OWNER, vm)`, then
     `amdgpu_vm_update_range(adev, vm, false, false, true, false, &sync, ...)`: the clear is a job that depends on the VM's
     earlier submissions.
   - `amdgpu_cs.c`: every submission locks the root page directory (`amdgpu_vm_lock_pd`) and every BO of its list, and
     `amdgpu_cs_submit()` adds the job's fence to each of them (`dma_resv_add_fence`).
   - `amdgpu_gem.c` `amdgpu_gem_va_update_vm()`: `amdgpu_vm_clear_freed(adev, vm, &vm->last_update)`; the ioctl does not
     wait; `amdgpu_cs_vm_handling()` makes later jobs depend on `vm->last_update`.
   - `ttm_bo.c` `ttm_bo_release()`: a BO whose reservation object has unsignaled fences is not destroyed, it goes to
     `delayed_delete`, which waits for them.
   - The gap: the VA unmap's fence is NOT put on the unmapped BO, and `amdgpu_gem_object_close()` adds a fence only if the
     close itself unmapped something. So a BO that a running job reads but that is not in that job's BO list could be
     destroyed before the job ends.
3. *The backing memory on our side.* `backend/src/direct.cpp` 1456-1521: a job with a draw or a dispatch gets the full
   list (every userptr BO and every imported BO with a mapping); a job without them gets the short list, the BOs of the
   operands the filter accepted, which are all it can read. So every BO a job can read is in its list, carries its fence,
   and outlives it (TTM's delayed delete); the imported pages stay pinned by the BO until then. `free_shared` right after
   the unmap is therefore safe for jobs in flight, and no host retire list is needed. Not covered, and not changed by D:
   the title's own reuse of a range it freed (the pages stay the memfd's; a late job reads what the title wrote since, as
   before, because the old wait ran at the next submission's sync, not at the title's unmap); the userptr path of
   `sync_mappings`, which keeps its wait.
   Inferred, not read: that a submission's fence owner is its VM (amdgpu_job.c), and that the page-table jobs of one VM
   run in the order they were queued (one scheduler entity), which orders a later map at the same address behind the clear.

Not to be tried again (earlier verdicts): the zero skip, learned windows, flip defer, `ANON_SYNC=thread` as a
default, one-ring arms, recovery as a fix.

## Result

### Result 1 (2026-11-17, laptop, from the journals of two runs): the 1.07 s block is not the unmap wait

Read on the box in exp 0430's gap: the `frame profile`, `timing split` and `direct:` lines of
`~/bc5-data/captures/play-20261117-0908/gc/direct.log` (the maintainer's play, 2,183 s) and of `play-20261117-1245`
(exp 0430's Q1 run, 1,612 s), copied once and analysed with `an0432.py`. A first count on the box used a broken awk
function; its numbers are not used.

- The frame at t 559.141 of the 12:45 run: 1,117.8 ms since the last flip, "sync 0.7, hints 0.4, prepare 1070.2",
  "prepare = filter 2.1 + tracker 0.3 + cu 1.1 + nested 2.7 + copy 1063.8"; the timing line beside it "drain 0.0 in 1".
  The time is in the backend's copy part (`backend/src/direct.cpp` 1320-1373), whose only system calls are those of
  `Impl::scratch_reserve` (446-489): a slot whose buffer is too small is CPU-unmapped, GPU-unmapped, freed, allocated
  at the exact new size, GPU-mapped at the same address and CPU-mapped. The 128 slots are used round-robin and grow one
  by one. Which call blocks is not known. Same second in the journal: "ho430 F6: a wait kept on ring -1 ... 1089 ms ago".
- A copy part over 200 ms: his play 4 times (491, 1118, 590, 243 ms, at t 42-65 s), the 12:45 run twice (744 ms at
  162 s, 1064 ms at 559 s).
- The unmap wait (item D): his play 4.5 s in 37,856 drains (0.2 % of the run; largest 128-submission window 26.4 ms);
  the 12:45 run 0.9 s in 4,689 (0.06 %; 23.1 ms).

| | his play 09:08 | 12:45 route run |
|---|---|---|
| frames, flips/s | 52,843 parsed, 24.2 | 68,530 parsed, 42.5 |
| frames over 100 ms | 1,684 (217 s) | 19 (4.4 s) |
| frame time: outside the host / GPU busy | 1,221 s (56 %) / 788 s (36 %) | 902 s (56 %) / 968 s (60 %) |
| game thread in the host | 643 s (30 %) | 382 s (24 %) |
| - sync | 341 s | 63 s |
| - hints | 56 s | 22 s |
| - prepare (of it copy) | 134 s (16 s) | 161 s (18 s) |
| - cs | 101 s | 135 s |
| at the flip (drain) | 311 s | 323 s |
| frames with sync over 20 ms | 2,976 (145 s, max 141 ms) | 636 (17 s, max 84 ms) |
| timing split, all threads: probe | 91 s | 34 s |
| - anonymous sync | 158 s | 38 s |
| - direct sync: views / scan / merge / drain / maps | 162 / 31 / 17 / 4.5 / 200 s | 12 / 7 / 3 / 0.9 / 12.5 s |
| - maps: want / drop / add | 99 / 68 / 32 s | 6.9 / 3.9 / 1.5 s |
| - learned / hints | 58 / 24 s | 4 / 22 s |
| mapping rebuilds ("direct:" lines) | 37,839 (17 a second), up to 30,631 views | 4,670, up to 16,543 views |

72-75 frame lines per file did not parse (cut lines) and are left out. The 09:08 play ran on a build with exp 0430's
catchers (as the top session described it), so its absolute figures carry their cost; the parts above are the host's own.

Reading: in his play the host's sync is 15.7 % of frame time and the unmap wait 0.2 %. A layout change (17 a second)
rebuilds the view list (4.3 ms each) and the mapping list (5.3 ms) over every view, and the anonymous walk and the
probe add 158 s and 91 s. The route run shows almost none of it, which is why route numbers do not show his stutter.

### Result 2 (2026-11-17 13:43-14:21, box): item D alone in his scene

Private build `eb96f4e5` (the shared unit b8afba59 + `mkd432.py`, edited unit 0bdd223b; 0 errors; the shared binary
0de9349b unchanged), `scene0432.sh`, order D S D S O, the 09:46 snapshot (91bb80e5fd85ca56), slot 4, no input, RT on,
300 s from G. Kernel 7.3.3-ogc1.1.fc45, boot 212971ac. All five NO_CRASH, 0 kernel lines in the laptop's stream, no new
fault record. The first start of the series ended before any run on a launch-line bug of `scene0432.sh` (fixed).

| run | arm | flips/s from G+10 s | seconds with a gap over 100 ms (of ~292) | drains | unmaps with a ring busy |
|---|---|---|---|---|---|
| d432D1 | D | 34.4 | 76 | 0 | 5,354 (74 BOs retired) |
| d432S2 | shared | 31.9 | 98 | not counted | - |
| d432D3 | D | 33.0 | 89 | 0 | 5,661 (8 BOs) |
| d432S4 | shared | 31.0 | 114 | not counted | - |
| d432O5 | the D binary, switch 0 | 34.3 | 76 | 4,474: 529.5 ms in all, longest 21.0 ms | 0 |

- The switch shows no effect on speed (D against O), as Result 1 predicted (0.13 % of the run in O).
- Mappings went and BOs were freed while a ring was busy about 5,500 times a run with no fault: the kernel's deferral
  held in these two runs. Two runs are not a proof.
- The 2-3 flips/s between the private binary and the shared one is not explained: two runs each, S always after D,
  and inside the spread earlier notes give for one build (41.5-46.7 on the route). Not a result.
- In every arm the sync + hints part of one submission reached 828-864 ms and was over 20 ms 631-765 times in the run;
  about 283 of 292 gameplay seconds have a gap over 50 ms.

### The ONE test build (prepared 2026-11-17, not compiled yet)

`t432.diff` (1ccb514f; `mktree432.sh`, `mkt432.py`) and `be/direct.cpp` (9975d8ee; `mkbe432.py`), built by
`box0432.sh buildbe` and `buildt`. Each item is on unless its word is "0":

| Item | Word | What |
|---|---|---|
| D | `BC5_DIRECT_UNMAP_NOWAIT` | no wait for an idle GPU before a mapping change |
| S | `BC5_DIRECT_SLOT_GROW` | a slot buffer grows to the next power of two (at least 64 KiB); every resize timed by step, printed over 20 ms |
| A | `BC5_DIRECT_ANON_EVENTS` | exp 0415's "events" form (tag as415c, its kit L6, never compiled): the anonymous walk only after a counted map or protect call, -EFAULT or a reopen, and on the old timing while an anonymous guest VMA exists |
| V | `BC5_DIRECT_VIEWS_KEPT` | exp 0415's kept view list (tag mr415d, kit L6): change records applied in place, the full build as a check every 2 s |
| M | `BC5_DIRECT_MAPS_FAST` | the mapping rebuild merges its two ordered runs instead of sorting and finds dropped mappings by one forward walk; `test_m432.cpp` 20,000 cases PASS on the laptop (a hand copy of the statements) |

Exp 0415's L6 diff was ported to patch bc39a035 on a local tree (KytyPlus f266548 + the patch; the unit reads
b8afba59). Left out: its semaphore statistics, its new load_stat causes (that header is included by units this build
does not recompile; the counts go to this build's own line) and two rejected hunks (a journal line, a statistic).
Not in this build: the mapping rebuild for changed ranges only (three per-view passes, one depending on what the title
has written); a second build, sized by what the timing lines show is left after M.

### Result 3 (2026-11-17 14:48-15:46, box): test build 1 (D, S, A, V, M) in his scene: three times slower, because of item A

Test binary `893e3db0` (units 9df1186a / 1262d6f3 / a9a2143a, header 478ff14c; private archive 16345982 from
`be/direct.cpp` 9975d8ee; 0 errors; the shared binary unchanged). First compile on the box: the host has no `patch`
(now `git apply`), and `sysLinuxVirtual.cpp` is a member of the static library `common` (its private object now goes in
front of the link's objects; the link map names the private object). `test_m432` PASS with the container's g++.
Series `T S S T T S` then one `A` (T with `BC5_DIRECT_ANON_EVENTS=0`), the same scene, 300 s from G, exp 0415's per-job
record on in every arm (`FS=1`). 7 of 7 NO_CRASH, 0 kernel lines.

| run | arm | flips/s from G+10 s | seconds with a gap over 100 ms / 50 ms (of ~292) | sync+hints of all submissions; over 20 ms |
|---|---|---|---|---|
| d432T6 | T | 11.2 | 223 / 277 | 312.2 s; 5,191 |
| d432S7 | shared | 33.9 | 81 / 283 | not counted by the build |
| d432S8 | shared | 33.4 | 90 / 283 | |
| d432T9 | T | 10.8 | 242 / 275 | 310.2 s; 5,096 |
| d432T10 | T | 10.6 | 251 / 276 | 309.6 s; 4,975 |
| d432S11 | shared | 30.7 | 109 / 284 | |
| d432A12 | T, item A off | 34.0 | 97 / 282 | 102.2 s; 1,002 |

- **Item A is a regression here and is off by default from build 2.** Its rule walks at once whenever the map/protect
  counter has moved; in this scene that was 6,454-6,664 walks in 440 s (15 a second) against one a second before, and
  every walk found nothing (anonymous guest VMAs 0, event misses 0). Exp 0415's plan had said: verify first, turn it on
  only if the event rate is below the walks of today. That step was skipped here; the error is this experiment's.
- With A off, T is level with the shared build (one run): D, S, V and M together give no visible flips/s in this
  no-input scene.
- Item S found the slot stall: "slot 0 resize 524288 -> 4194304 bytes (asked 3274408) took 683.0 ms: unmap+free 0.1,
  alloc 682.7, gpu map 0.1, cpu map 0.0" and "slot 26 resize 262144 -> 2097152 bytes took 385.2 ms: ... alloc 382.2":
  it is `amdgpu_bo_alloc` in the middle of play. Growing by powers of two still allocates then.
- Kept view list: 0 record mismatches in all four runs. No-wait unmap: 2,009-3,912 mappings dropped and up to 44 BOs
  retired per run while a ring was busy, no fault.

What the long sync parts are (`fs0432.py` on the per-job records; a sample of 64 of every 512 frames, in ms):

| | shared d432S7 | T, A off d432A12 | T d432T9 |
|---|---|---|---|
| job lines | 53,381 | 53,715 | 19,907 |
| lock wait (for the device mutex) | 13,534 | 13,096 | 34,370 |
| probe | 2,009 | 1,320 | 838 |
| anonymous sync (its maps read) | 3,174 (3,142) | 2,716 (2,684) | 29,223 (29,067) |
| direct sync | 8,802 | 8,515 | 7,101 |
| - views | 2,414 | 4,152 | 3,887 |
| - scan (imports) | 2,109 (1,876) | 2,069 (1,843) | 1,932 (1,780) |
| - merge / drain | 331 / 149 | 306 / 9 | 176 / 5 |
| - maps | 3,490 | 1,683 | 1,005 |
| learned / hints / before the device call | 888 / 633 / 1,674 | 888 / 585 / 1,649 | 415 / 251 / 720 |
| device call | 15,436 | 15,197 | 5,225 |
| jobs with sync+hints over 20 ms | 122 | 136 | 615 |

- The two longest (852 and 585 ms; the same two jobs in every run of every arm: an acb of 57 dwords, a dcb of 3,496)
  are imports inside the scan: 845 and 584 ms in `ls415_import`. This is the "longest 828-864 ms" of every arm.
- The once-a-second anonymous walk reads the maps for about 50 ms each time (3.1 s of the sample, about 25 s of a run),
  on the submitting thread under the device mutex, and finds nothing. One such hold a second fits "283 of 292 seconds
  with a gap over 50 ms" in every arm (a fit, not shown per second).
- Threads wait for the device mutex about as long as the device call takes (13.5 s against 15.4 s in the sample).
- By item: D takes the drain from 149 to 9 ms; M halves the mapping rebuild (3,490 to 1,683 ms); V makes the view
  list slower (2,414 to 4,152 ms, single builds of 104-114 ms): its 2 s check builds the whole list twice.

Correction to the list above (same day, from the same records): the 852 and 585 ms imports are the first two
submissions of the process (frame 0, +0.0 and +0.9 s of the record) in every run: start-up, not play. In gameplay only
(from 130 s on, shared run d432S7, the same 1-in-8 sample): 80 jobs have sync+hints over 20 ms, 3,571 ms in all; by
their largest part: the anonymous walk 49 jobs / 2,826 ms (79 %, about 58 ms each), the probe 17 / 363 ms, merge
5 / 154, maps 3 / 80, views 3 / 63, learned 1 / 32, imports 1 / 31, drain 1 / 22. Lock wait in that window: 9,208 ms
in all, 424 waits over 5 ms, 65 over 20 ms. In d432A12 (T, A off) the views lead 46 of 88 long jobs (1,782 ms): item
V's check, changed in build 2.

**Build 2 (prepared, not compiled):** D, M and S as in build 1; A off unless "1"; P (`BC5_DIRECT_SLOT_PREALLOC`: per
ring 2 slots of 4 MiB and 6 of 512 KiB made at Device::open, 55 MiB of GTT; a job that does not fit its slot takes the
smallest free slot of its pool that holds it); W (`BC5_DIRECT_ANON_THREAD`: the once-a-second anonymous check on a
thread that takes no lock and only sets a flag; urgent and must walks unchanged); V's check without the old builder's
second full build. `t432.diff` 10e40228, `be/direct.cpp` 83d58ac6. Build 2 hung the GPU: Result 4.

### Result 4 (2026-11-17 16:13-16:16, box): build 2 hung the GPU 45.9 s into its first run; the box rebooted. This experiment's bug.

Build 2 (`a4ee7fd6`: units 305760dd / 1262d6f3 / a9a2143a, private archive 4d5efea1 from `be/direct.cpp` 83d58ac6; 0
errors) started as run d432T13 at 16:14:35 (his scene, the first of a pair T, V). The boot (212971ac) had already had a
GPU reset at 16:12 in exp 0430's shared control run. At 16:15:24, on the start screen and before any key, the laptop's
kernel stream reads "ring gfx_0.0.0 timeout, signaled seq=5679705, emitted seq=5679707", "Process kyty_emulator ...
thread bc5-ring", "Ring gfx_0.0.0 reset failed", then `bc5-gpu-watch` crashed the kernel for a reboot. Up again at
16:15:54 (boot 66e113e1). The fault record `~/bc5-data/captures/faults/20261117-161524` says "a hang without a page
fault", 45.942 s after the start; devcoredump `20261117-161524-devcd2.txt`; journal `play-20261117-1614`. The
maintainer's live saves read 91bb80e5fd85ca56 before and after (the runs use a private copy).

**Cause (read from the run's journal and the code):** build 2's item P moved a job that did not fit its slot to the
smallest free preallocated slot of its pool. A slot that had no buffer yet also "did not fit", so nearly every job
was moved (the build's own line: 12,277 moved in 45 s) onto the 8 preallocated slots at the end of each pool. The
backend picks a job's slot by rotation and refuses the submission when that slot is still in use
(`Device::submit`: "the host lets fewer jobs fly than there are slots", `-EBUSY`). The rotation now met slots that
moved jobs were using; the journal has 142 lines "submit #N acb ... FAILED rc -16" from submission 18 on. The host
drops a refused job, so a later job waited for work that never ran, and the gfx ring timed out. Not exp 0430's class
(no dropped wait on a label), no page fault, no sign of memory corruption.

What went wrong in the work: the change altered which slot a job uses without reading the rule the rotation relies
on, and the run had nothing that stopped at a refused submission. Both are fixed for build 3: the slot switch is
removed (every slot gets a 512 KiB buffer once at `Device::open`, 64 MiB of GTT; no job changes its slot; a job over
512 KiB grows its slot as before), and `run0432f.sh` ends a run at the first "FAILED rc -16" in the journal.
Build 2's other items (D, M, W, V's changed check) were not tested by this run.

### Result 5 (2026-11-17 16:55-17:07, box, boot 66e113e1): build 3: one clean run with fewer 50 ms gaps, then a GPU hang of unknown owner

Before the build, a count asked for by the top session: "FAILED rc" lines by rc in the 65 journals of 2026-11-17
(`~/bc5-data/captures/play-20261117-*/gc/direct.log`). 60 have none; four have one or two "FAILED rc 0" beside their
TIMEOUT lines (the timed-out job itself: play-0210, -0542, -1140, -1546); the only non-zero rc is build 2's run
play-1614 (140 lines rc -16). No shared-build run lost a job.

Build 3 (`0ee07b18`: unit 2bd281ac, private archive ef7e673b from `be/direct.cpp` b583e2df; 0 errors): D, M, S, W on;
A off; P = every slot 256 KiB at `Device::open` (128 buffers in 6.9 ms), no slot switch; R (a refused submission ends
the game with the record); V on in run 1 with its check's second build removed.

| run | arm | result | flips/s from G+10 s | seconds with a gap over 100 / 50 ms (of 292) |
|---|---|---|---|---|
| d432T14 | build 3, every item on | NO_CRASH, 0 kernel lines | 35.5 | 73 / 195 |
| d432V15 | build 3, `BC5_DIRECT_VIEWS_KEPT=0` | GPU hang at 112.8 s (in the load after Continue) | - | - |

- **W works in d432T14:** 149 anonymous walks in the run (about 500 before), 433,200 calls left out, 0 event misses; the
  per-job sample has 880 ms of anonymous sync against 3,174 in the shared run d432S7; and the seconds with a gap over
  50 ms fall from 275-284 (every earlier arm, shared included) to 195. One run.
- **M** as before: maps 1,443 ms of the sample against 3,490. **D**: drain 9 ms.
- **V is still slower than off** (views 4,182 ms against 2,414): off by default from here, as the top session required.
- **P and the long allocations (corrected the same evening):** the two long ones quoted at first for this run ("slot
  16 ... 958.5 ms", "slot 24 ... 1354.1 ms") belong to d432V15, not to d432T14: the reading took the last lines of the
  wrong log. d432T14 has one resize over 20 ms (slot 27 to 4 MiB, 67.4 ms, at t 41-51 s). d432V15 has six, all between
  t 40.9 and 50.9 s: 21.9, 499.3, 758.9, 175.9, 958.5 and 1354.1 ms, each almost wholly `amdgpu_bo_alloc`. Build 1's two
  (683.0 ms in d432T10, 385.2 ms in d432A12) were not placed in time. **When:** t 40-50 s is the title's start, before
  the start screen: the sampler of d432T14 shows GTT in use going from 9,915 to 11,860 MiB and MemAvailable from 3,508
  to 1,449 MiB between t 36 and 47 s, 1,076 pages a second swapped out at t 42 s, and PSI memory "full" at 0.6-1.6 %.
  So the allocation is slow while the box reclaims and swaps to make room for the title's first pins: a
  memory-pressure symptom at start-up, not a gameplay stall in these runs. Not read: /proc/vmstat (the sampler does not
  record it), so "reclaim" is from the swap-out and PSI figures, not from the kernel's own counters. Elsewhere the copy
  part was over 200 ms at t 42-65 s of his play (four times) and at 162 s and 559 s of the 12:45 run; those two later
  ones are the only ones seen after start-up.
- **d432V15:** 17:06:42 "ring comp_1.3.0 timeout, signaled seq=410120, emitted seq=410122 ... reset succeeded", then
  gfx_0.0.0 the same; the game ended with fault record `20261117-170642` ("a hang without a page fault"), journal
  `play-20261117-1704`, 0 refused submissions. The probe's summary: "acb #93564 2047 dwords: 1 waits (1 kept for the
  GPU), 15 label writes, 140 dispatches (80 indirect; the largest grid 17765411481442058240 groups, at 842)". Whose
  bug it is is NOT known: the same binary ran clean eight minutes before; exp 0430's shared control run h430C6 showed
  a comp-ring timeout with a successful reset at 16:12 on the boot before. One event. The records went to exp 0430.
  The series stopped there (LESSONS R55), and the box needs a reboot before any next run (the top session's rule).

### Result 6 (2026-11-17, laptop, from the per-job records of d432S7 and d432T14): the device mutex is held 17-18 ms of every 30 ms frame

Gameplay only (from 130 s on), the 1-in-8 frame sample, per frame. "Held" is from the lock taken to the end of the
device call; the mutex is exclusive, so these add up across threads.

| per frame | shared d432S7 | build 3 d432T14 |
|---|---|---|
| jobs | 31.5 (23.3 acb of ~1,270 dwords, 8.2 dcb of ~10,000) | 31.5 |
| lock held | 18.4 ms | 16.7 ms |
| lock wait | 7.6 ms | 6.3 ms |
| acb: syncs / device call (prepare, list, cs) | 3.20 / 4.38 (0.64, 0.46, 2.98) ms | 3.20 / 4.77 (0.66, 0.56, 3.23) |
| dcb: probe / syncs / device call (prepare, list, cs) | 1.20 / 3.14 / 4.40 (2.25, 0.04, 1.81) ms | 0.73 / 1.61 / 4.55 (2.21, 0.12, 1.92) |

- Waits for the mutex are mostly short: 34,037 of 38,356 under 0.1 ms, 359 between 5 and 20 ms, 65 over 20 ms (shared).
- By part, shared: the kernel submit call 4.8 ms a frame (31.5 calls of about 0.15 ms), the syncs 6.3 ms (3.2 of it
  charged to the 23 acbs; see the correction below), the backend's prepare 2.9 ms, the
  probe 1.3 ms.
- Build 3 halves the dcb's syncs (3.14 to 1.61 ms: W and M) and leaves the acb's 3.20 ms as it is.
- Corrected the same evening: the acb's 3.2 ms a frame is NOT 0.14 ms for each job. In d432S7's gameplay 23,169 of the
  28,342 acb jobs sync in under 10 us and 4,854 more in under 100 us (116 ms together); 259 jobs over 1 ms carry
  3,731 of the 3,888 ms, 151 of them over 10 ms (3,026 ms). By part: the anonymous walk 1,077 ms, the view list
  1,021, the mapping rebuild 1,304, scan 178, merge 157. So the fast path already costs nothing; the time is the walk
  (item W) and the full rebuild at a layout change, charged to whichever job comes next (three in four are acbs). The
  dcbs show the same shape (340 jobs over 1 ms carry 3,687 of 3,823 ms). In d432T14 the acbs' anonymous part is
  11 ms, their maps 593 ms, their views 3,131 ms (item V on).

**For the memory line (the top session's note, 2026-11-17):** the title's start is under memory pressure on this box.
In d432T14 (build 3, the 09:46 save) MemAvailable fell from 3,508 to 1,449 MiB and GTT in use rose from 9,915 to
11,860 MiB between t 36 and 47 s, with 1,076 pages a second swapped out at t 42 s and PSI memory "full" at 0.6-1.6 %;
4 MiB GTT allocations made in that window took 0.2-1.4 s. Slot prealloc default from build 4: 256 KiB for every slot
(32 MiB); `BC5_DIRECT_SLOT_PREALLOC=2048:256` is kept for a later test.

(pending: the A/B of the test build in his scene and on the route; the perf profile of the normal and lean builds)

## Verdict

(pending)
