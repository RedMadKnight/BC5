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

### Item X (2026-11-17 evening, laptop; not yet compiled on the box): the mapping rebuild for the changed views only

Why: results 1 and 6. A mapping rebuild runs about 17 times a second in play; each one walks every view (up to
30,631) against the imported buffers, orders the list and walks every mapping twice, though a rebuild caused by the
guest's ranges changes a handful of views. Item M halved the passes; item X leaves them out.

What (`mkx432.py`, switch `BC5_DIRECT_MAPS_DIFF`, tag x432): when the only cause of a rebuild is a new view list
(no buffer retired or imported since the last rebuild, no cap change, no cover and no zero-list mappings), the new
list is compared with the list the mappings were made from. A view with the same address, size and offset keeps its
mappings; every other old or new view gives an address interval, inside which old mappings are dropped unless a
changed new view asks for the same one, and the changed views' mappings are added by the old add pass's steps. Every
other cause takes the old rebuild. No change records are used (item V's source), only two snapshots, so a missed
record cannot hurt it.

Off unless the word is "1" or "verify"; "verify" makes the whole list the old way after each such rebuild and
compares (a difference is counted, journaled, and the next sync rebuilds the old way). Arm X of `scene0432.sh` is
build 4 with `verify`, arm Y with "1". It goes on by default only after a verify run with 0 mismatches and a speed
run no slower than T.

Checked on the laptop: `test_x432.sh` cuts the body out of the edited unit (f80560e3 then; 019d826f with the reason counters of result 7) and runs it against the whole
rebuild on 20,000 random pairs of view lists with a device model that counts a map over a live mapping or an unmap
of nothing: PASS (mappings kept 485,212, dropped 91,328, added 84,344). The unit itself has not been compiled.

What it does not touch: the view list's own build (162 s of his 09:08 play, more than the mappings' passes after M).
Item V was to remove that and is slower; why is not known. The perf profile of the next slot is to show where a view
build spends its time before anything is written for it.

### Note 7 (2026-11-17 evening, laptop, no new run): what the chain hold (`BC5_DIRECT_CHAIN=2`, ADR 0010 B) saves, and other ways to the same time

The maintainer's question through the top session: exp 0430's K1/Z1 give 42.0 against 37.2 flips/s (one run each)
for the hold; if the hold goes, can the ~11 % come back another way? Source: the per-job records of d432S7 (shared
`0de9349b`) and d432T14 (build 3), both with the hold on, frames after 200, a sample of 64 of every 512 frames.
No run without the hold is in this experiment's records, so the count of submissions without it is an estimate.

What 11 % is: 23.8 against 26.9 ms a frame, 3.1 ms.

What the game thread's submissions look like with the hold (per frame; S7 / T14):

| | S7 | T14 |
|---|---|---|
| dcb submissions (chains) | 8.05 | 8.01 |
| buffers (segments) in them | 57.7 | 54.8 |
| a chain closed by: a wait served on the CPU / the flip / the 2 ms bound (codes 9 and 10) | 63 % / 12 % / 25 % | 65 % / 13 % / 23 % |
| waiting for the device mutex, per dcb submission | 0.42 ms | 0.37 ms |
| under the mutex, per dcb submission | 1.19 ms | 0.99 ms |
| of that: kernel submit / prepare / sync / probe | 0.23 / 0.28 / 0.36 / 0.13 ms | 0.24 / 0.29 / 0.18 / 0.09 ms |
| game thread in dcb submissions, mutex wait included | 12.9 ms | 10.9 ms |

The fixed cost of one more submission, read from the small acb jobs (57 dwords, so nearly all of it is fixed):
0.36 ms under the mutex (kernel submit 0.13-0.15, sync 0.11-0.13, prepare 0.03, list 0.02) plus 0.12-0.17 ms waiting
for the mutex. Prepare scales with dwords and does not change with the hold.

So the hold saves submissions, not work per buffer: 57.7 buffers leave in 8 submissions. The commonest chains have 4
and 2 segments, so a submit call seems to carry 2-4 segments (cc, hib, dcb); without the hold that is about 15-25
submissions a frame, 7-17 more, at 0.36-0.5 ms each on the game thread: 2.5-8 ms. The measured 3.1 ms lies at the low
end. Two thirds of the chains already end at a CPU-served wait, not at the bound: the hold is cut short most of the
time, and only a quarter of the chains use the 2 ms.

Ways to get the time back without holding a buffer, by what the records support:

1. **The device mutex.** The game thread waits 3.0-3.4 ms a frame for it today (8 x 0.37-0.42), as much as the
   hold's whole gain, because the ring thread's 23 acbs a frame hold it 0.36 ms each (8.2-8.4 ms a frame), kernel
   call included. Taking the kernel submit (0.13-0.24 ms) out of the mutex, and not taking it for a sync that has
   nothing to do, attacks this directly and helps with or without the hold. Not built; this experiment's next item
   after W (the top session's order).
2. **A cheaper submission.** Items W, M and X cut the sync part (dcb sync 0.36 ms in S7, 0.18 in T14 with W and M;
   one run each). With 7-17 more submissions a frame, each 0.1 ms off a submission is 0.7-1.7 ms. The kernel submit
   itself (0.13-0.24 ms) is not ours to shorten except by a shorter buffer list.
3. **Several buffers in one kernel submission without waiting for them.** Inside one submit call the chain already
   does this (mode 1). Across calls it needs either the hold or a submitting thread that takes whatever has queued
   up while it was in the kernel; the second keeps a window, shorter than 2 ms, in which a dcb is behind an acb of
   another thread, so it is the same reorder question exp 0430 is working on, not a way round it.

Not known: the real count of game-thread submissions per frame without the hold (exp 0430's Z1 journal has it); how
much of the 3.1 ms is the mutex wait growing with more acquisitions. One run per arm stands behind the 11 %.

### Note 8 (2026-11-17 evening, laptop, a design, nothing built): the kernel submit outside the device mutex

Two mutexes cover a whole submission today: the host's `g_dev_mutex` (`submit_now`: probe, syncs, hints, then
`Device::submit`) and the backend's `Impl::mutex` (`Device::submit`, `backend/src/direct.cpp`, from the filter to
after `amdgpu_cs_submit`). The kernel call is 0.13-0.15 ms of the 0.36 ms an acb holds them and 0.23 of the 1.0-1.2 ms
of a dcb chain (note 7), so the two submitting threads (the game thread on the GFX ring, `bc5-ring` on the compute
rings) wait for each other's kernel calls.

What the kernel call relies on that the mutexes give it today, and what would give it instead:

| relied on | why | without the mutex |
|---|---|---|
| order of jobs on one ring | a job is prepared against the state the ring's last job left (`hi_reg`, the tracker), and its slot comes from the ring's pool by rotation | a lock per ring, taken first and held from the prepare to the kernel call's return; never taken while a device mutex is held |
| the mappings a prepared job reads are still there | item D: the kernel orders a page-table clear only behind jobs it already has | a shared lock held from the prepare to the call's return; a rebuild that drops a mapping or frees a buffer takes it exclusively (about 17 a second against about 1,000 submissions); adding mappings needs nothing |
| the kept buffer list's handle | another submission replaces and destroys `full_list` when the buffers changed | the list is destroyed only when no job in flight uses it (a count on the handle) |
| the slot's records (`slot_seq`, `last_seq`, the snapshot commit) | written after the call from its `seq_no` | the backend's mutex taken again for these few lines |

Size, before anything is built: the game thread waits 3.0-3.4 ms a frame for the mutex with the hold (note 7). Only
the part of that spent behind another thread's kernel call goes: about 40 % of an acb's hold, so about 1.2-1.4 ms a
frame for the game thread (4-5 %), and the like for `bc5-ring`. That is under half of the hold's 3.1 ms. The rest
of the wait is behind the other thread's sync and prepare, which items W, M and X shorten. These are estimates from
averages; the run without the hold (exp 0430's h430Z1) is to be read in the next slot to replace them.

Risk: it changes the path that submits to the GPU, in the backend and the host at once. A mistake in the second row
is a GPU page fault; in the first, a job run against the wrong state. It goes into a build only behind a switch,
off by default, after the profile shows the kernel call where these averages put it.

### Note 9 (2026-11-17 21:30, from exp 0430's journals, read-only): the hold measured, not estimated

exp 0430's route runs h430K1 (hold on, 42.0 flips/s) and h430Z1 (`BC5_DIRECT_CHAIN=1`, 37.2), the same binary
`d894ec3b`, one run each. Means of every "frame profile" line after t 200 s (59,365 and 52,093 frames), ms a frame,
game thread:

| | K1, hold | Z1, no hold | difference |
|---|---|---|---|
| frame period | 23.62 | 26.98 | +3.36 |
| game-thread jobs | 9.1 | 51.7 | +42.6 |
| inside the host | 5.85 | 10.92 | +5.07 |
| - kernel submit (cs) | 2.02 | 5.40 | +3.38 |
| - buffer list | 0.01 | 0.77 | +0.76 |
| - sync | 1.00 | 1.81 | +0.81 |
| - prepare | 2.47 | 2.55 | +0.08 |
| at the flip | 4.23 | 1.88 | -2.35 |
| outside the host | 13.54 | 14.17 | +0.63 |
| jobs from the ring thread | 24.8 | 20.1 | |

This replaces note 7's estimate (7-17 more submissions): it is 43 more, at 0.08 ms of kernel submit each, and the
flip's drain gives 2.35 ms back because the work reached the GPU earlier. The hold's gain is kernel submit time on
the game thread (3.4 ms), a buffer list made and destroyed per job (0.8 ms) and the sync's fixed part (0.8 ms).
Note 8's lock change does not touch the first two: they are the game thread's own calls, not waits for another
thread. Its size stays as estimated there or less.

Ways back without the hold, sized against Z1:

1. **The buffer list in the submit call itself** (0.77 ms a frame): a job with a short list makes a list
   (`amdgpu_bo_list_create`), submits, destroys it: three kernel calls. The kernel takes the handles inside the
   submit call (`AMDGPU_CHUNK_ID_BO_HANDLES`, `include/uapi/drm/amdgpu_drm.h`; libdrm `amdgpu_cs_submit_raw2`). One
   call instead of three, backend only, order untouched. TODO(verify): the chunk's cost against a kept list on this
   kernel.
2. **The sync's fixed part** (0.81 ms): items W, M, X and the probe.
3. **The kernel submit off the game thread** (5.4 ms a frame in Z1, more than the hold's whole gain): jobs are
   prepared on the title's threads in their order under the device mutex, as now, and one thread makes the kernel
   calls in that order, at once, holding nothing back. An acb then cannot pass a dcb handed over before it: the
   order is the title's. It needs the job's sequence number later than today (the fence dependencies of exp 0430 and
   the completion queue take it from the call's result), so it is the largest of the three and touches exp 0430's
   code.

1 and 2 together are about 1.6 of the 3.4 ms. One run per arm.

### Result 7 (2026-11-17 21:27-22:20, box, boot up since 17:42, no GPU reset): the profile, and build 4 against shared

Build 4: binary `a23d2f2e` (unit f80560e3, private archive 6eac453e; 0 errors, 12 warnings not read). D, M, W, R, S on,
P = 256:256 KiB (32 MiB), A and V off, X off except in d432X22 (`verify`). Shared: `0de9349b`. His slot-4 scene from
the read-only snapshot, RT on, no input, 300 s of play. Seven runs, all NO_CRASH, 0 kernel lines, 0 refused
submissions. Records: `raw/d432{S16,T17,T18,S19,T20,T21,X22}-*`; reader of the profile: `prof_an0432.py`.

**The profile** (d432S16 shared, d432T17 build 4; `prof0432.sh` beside the run from about G+10 s to the end, 275-279 s).
perf is `cpu-clock:u` at 199 Hz: user mode only and without call graphs; kernel time is from `/proc/<pid>/task/*/stat`.

| | shared d432S16 | build 4 d432T17 |
|---|---|---|
| all threads, user / system CPU s | 958 / 158 | 1017 / 171 |
| cores busy (of 16) | 4.00 | 4.32 |
| game-main, share of one core | 61.7 % | 60.8 % |
| Render Thread | 51.5 % | 54.8 % |
| bc5-ring (2 threads), CPU s user / system | 53.4 / 39.1 | 44.3 / 43.8 |
| bc5-chainwd, CPU s | 21.3 | 19.3 |
| bc5-anonchk (item W's thread), CPU s | - | 14.3 |
| GPU: GFX ring busy (DRM fdinfo) | 38.6 % | 40.0 % |
| GPU: compute rings busy (sum of the client's) | 29.9 % | 31.2 % |

- **Nothing is saturated.** The busiest thread uses 62 % of a core, the GFX ring runs 39-40 % of the time, 12 of 16
  hardware threads are idle. The frame time is spent waiting between the game's threads, the host's locks and the
  GPU, not computing. So removing host CPU work helps only where that work sits inside a wait someone else is in
  (the device mutex, result 6; the kernel submit, note 9).
- **User samples by object** (the reports are cut at 300 lines and cover 48 % of the samples; the tail is small
  symbols, most of them guest addresses by their look, not counted): guest code 28.6 %, `kyty_emulator` 10.2 %, libc
  8.3 %, libstdc++ 0.9 % of all samples in shared.
- **Top host symbols, shared, % of all user samples** (build 4 in brackets where it differs): `memmove` 4.07 (3.62;
  1.89 of it on game-main, 0.83 on the Render Thread, 0.43 on bc5-ring, 0.33 on kyty-gpu; the callers are NOT known
  without call graphs), `submit_now` 1.17, `pthread_mutex_lock` 1.01, `Loader::TlsMainGetAddr` 0.86,
  `std::_Rb_tree_increment` 0.86 (map walks on bc5-ring and bc5-chainwd), `direct_sync_one` 0.76 (0.45),
  `__vfscanf_internal` 0.65 (the `/proc/self/maps` reads: on bc5-ring and bc5-chainwd in shared, 0.49 on bc5-anonchk
  in build 4), `KernelGetProcessTimeCounter` 0.58, `Tracker::emit_prefix` 0.54, `std::map::operator[]` 0.47 (all on
  kyty-gpu), `policy::filter` 0.45, `SoftCp::execute` 0.43, the sort of the mappings 0.43 (gone in build 4: item M),
  `Tracker::apply_level` 0.41, `Device::submit` 0.35, `pthread_mutex_unlock` 0.33, `malloc` 0.32,
  `indirect_check::apply` 0.29, `_int_malloc` 0.28, `strtoull` 0.22.
- **Candidates the profile adds:** bc5-chainwd costs 19-21 CPU s of 279 (7 % of a core) for a watchdog; bc5-anonchk
  14 s (5 %); the four bc5-apr-q threads 11-14 s of system time; `memmove` on game-main (about 18 s). None is on a
  saturated core, so each is a cleanup, not a speed item, until shown to sit inside a lock.
- Not done: call graphs, kernel-side samples, a full-length report. The `perf.data` files stay on the box
  (`~/bc5-work/exp0432/n/raw/d432{S16,T17}-prof-perf.data`) for the next slot.

**Build 4 against shared**, from G+10 s. Shared runs pooled over the day: the same binary, words and scene (the top
session's rule; d432S2-S11 are in results 2-5, without a sampler).

| run | arm | flips/s | seconds with a gap over 100 / 50 ms (of 283-285) | MemAvailable min / median MiB | PSI memory "some" mean / max % |
|---|---|---|---|---|---|
| d432S2, S4, S7, S8, S11 | shared, earlier | 31.9, 31.0, 33.9, 33.4, 30.7 | 98, 114, 81, 90, 109 / every second | - | - |
| d432S16 (with perf) | shared | 32.6 | 99 / 285 | 972 / 1075 | 0.82 / 3.85 |
| d432S19 | shared | 32.3 | 98 / 284 | 986 / 1092 | 0.39 / 3.38 |
| d432T17 (with perf) | build 4 | 35.2 | 60 / 195 | 892 / 1015 | 0.65 / 5.22 |
| d432T18 | build 4 | 34.7 | 56 / 207 | 868 / 1077 | 0.50 / 3.63 |
| d432T20 | build 4 | 35.7 | 63 / 205 | 986 / 1100 | 0.81 / 5.95 |
| d432T21 | build 4 | 34.1 | 73 / 217 | 826 / 926 | 0.37 / 3.22 |
| d432X22 | build 4, X `verify` (never taken, below) | 33.5 | 63 / 215 | 983 / 1067 | 0.44 / 5.26 |

- **Flips:** shared 30.7-33.9 (7 runs, median 32.3); build 4 34.1-35.7 (4 runs, median 35.0), 33.5-35.7 with d432X22,
  which ran the same code path. The four plain runs do not overlap shared; with d432X22 they overlap by one run.
  About +2.6 flips/s (+8 %) at the medians.
- **Gaps:** seconds with a gap over 50 ms fall from every second to 195-217 of 284; over 100 ms from 81-114 to 56-73.
- **Memory (P's 32 MiB):** no difference outside the run-to-run spread in MemAvailable or PSI; d432T21 is the lowest
  (826 / 926 MiB) with the least swap in use (530 MiB against 702-914), so it reads as swap state, not as the build.
- **Per-job sample** (64 of every 512 frames; ms; d432S19 against d432T18, T20, T21): anonymous sync 3,241 against
  874-1,074 (W); maps 3,132 against 1,805-2,152 (M); drain 111 against 11-12 (D); wait for the device mutex 13,498
  against 10,419-11,118; jobs with sync + hints over 20 ms 105 against 38-44. Views 2,245 against 2,530-2,699: not
  better (more frames, and nothing in build 4 touches it with V off).
- **What is left over 20 ms in every run, both builds:** one acb with 845-854 ms and one dcb with 575-583 ms of
  import scanning (the gameplay imports, next on the list), and a dcb of 8,153 dwords with 83-104 ms of maps.
- **Item X was never taken:** d432X22's line reads "maps-diff VERIFY: by diff 0, the old way 5147, views changed 0,
  mismatches 0". One of its conditions fails at every rebuild in this scene; which one is NOT known (the build counts
  no reason). So X is neither tested nor refuted in play; the laptop test (20,000 cases) is all there is. Next build:
  a counter per failed condition.

Open after this result: the route A/B (3 runs each), the lean variant of build 4, per-item arms (the gain is of D, M,
W together), build 4's 12 compiler warnings, and the owner of d432V15's hang (build 3; with exp 0430). Six of six
build 4 runs were clean.

## Result 8: the route A/B, item X's reasons, the swap form and its lean smokes (2026-11-18, 00:27-03:54)

Build 5 (`0f52fd54`) is build 4 plus a counter per failed condition of item X (`mkx432.py`); nothing else changed.
Shared is `0de9349b`. Twelve runs, every one that was routed ended NO_CRASH, no kernel GPU line, no reset.
Records: `raw/slot8.out`, `slot9.out`, `slot10.out`, `raw/d432{T23..T33}-*`.

**The route (fight record, then the walk; 1500 s from G; alternating T S T S T S; flips/s from G+10 s):**

| | build 5 (T23, T25, T27) | shared (S24, S26, S28) |
|---|---|---|
| flips/s | 29.3, 29.4, 29.4 (mean 29.4) | 29.1, 29.0, 28.9 (mean 29.0) |
| seconds with a gap over 100 ms | 4, 2, 3 | 2, 3, 3 |
| seconds with a gap over 50 ms | 45, 51, 35 | 408, 446, 357 |
| MemAvailable min / median, MiB | 1322-1383 / 1388-1432 | 1430-1459 / 1447-1529 |
| PSI memory, highest | 0.20, 0.24, 0.07 | 0.00, 0.48, 4.21 |

Build 5 is 0.4 flips/s above shared in each pair (1.3 %), and the seconds with a gap over 50 ms fall to about a
ninth. MemAvailable is 50-110 MiB lower in build 5 (P's 32 MiB of slots explain a part; the rest is not attributed).
No earlier route run of `0de9349b` matches these (the others ran other words or lengths), so nothing was pooled.

**One kernel OOM kill, in d432T23** (`raw/d432T23-kernel-lines.txt`): about 30-40 s into the run, while the title
imports its menu (GTT 8.8 -> 10.8 GiB in 10 s), `bc5-ring` asked for a page in `amdgpu_bo_list_create` and the kernel
killed `plasmashell` (global OOM, `CONSTRAINT_NONE`) with 2.5 GiB reported available and 4.8 GiB of inactive file
pages. The emulator ran on and the run ended NO_CRASH. The same kind of global OOM in the menu import is on record
for another build (LESSONS, exp 0418, 2026-11-13 18:26), so one case does not point at build 5; it is not excluded
either. The later runs of the night ran after this kill (whether the shell came back was not read).
The laptop's kernel stream file stayed empty through it: `dmesg -W` through ssh buffers its output, so the stream
shows nothing until 4 KiB are written. The per-run kernel check on the box is what caught it. The stream needs
`stdbuf -oL` before it is relied on again.

**Item X: not taken, and now it is known why.** d432X29 (`raw/d432X29-last-line.txt`): by diff 0, the old way
5,122, mismatches 0; the first failed condition was `k1r` on 4,620 times, new BOs 394, retired 108. The title's
default switches keep `k1r` on, and X's fast path excludes it. X stays off; it is untested in play. Making it work
means carrying `k1r` through the diff, a new piece of work.

**His scene, build 5 and the swap form** (300 s, no input; flips/s from G+10 s; the same snapshot):

| run | flips/s | s with gap > 100 ms | > 50 ms | MemAvailable min / median |
|---|---|---|---|---|
| shared, 7 runs of Results 6-7 | 30.7-33.9, median 32.3 | 81-114 | every second | 972-986 / 1075-1092 |
| build 4, 4 runs of Result 7 | 34.1-35.7, median 35.0 | 56-73 | 195-217 | 826-986 / 926-1100 |
| d432X29 (build 5, X verify) | 34.1 | 56 | 210 | 876 / 993 |
| d432T30 (build 5) | 33.3 | 66 | 209 | 846 / 1002 |
| d432T33 (swap form, normal `0db6fc7c`) | 32.9 | 66 | 217 | 976 / 1079 |

The fewer long gaps are kept (56-66 s against 81-114 s). The flips/s gain is smaller tonight: 32.9-34.1 against
build 4's 34.1-35.7, and inside shared's own range. No shared scene run was made this night, so whether the night or
the build moved is not known. Per-job sample of d432T30: anonymous sync 721 ms, maps 1,274, drain 7, lock wait 8,619,
33 jobs over 20 ms (shared d432S19: 3,241, 3,132, 111, 13,498, 105), so the removed host work stays removed.

**The swap form** (`mkswap432.py`, `swap432.diff` md5 `59bd42db`, unit `f574f460`): the tested code, with the lean
build's rule applied: D, W, R, M on and A, V, X off without reading a word, counters without storage, no 10-second
line. Built on the box with the shared builds' own commands (`SWAP=1 [LEAN=1] box0432.sh buildt`): normal `0db6fc7c`
(0 errors), lean `89ee1225` (0 errors; one fix on the way, the lean counter's constructor made explicit). In the
lean binary none of the host unit's words remain; `BC5_DIRECT_SLOT_PREALLOC` remains
because the backend archive is one for both builds. Both link the private archive `6eac453e` (items S and P).

Lean smokes of `89ee1225`:
- ASTRO BOT, 200 s by exp 0431's `astro0431.sh` (a432L1): PASS, 0 kernel lines, 0 crash lines.
- The second title, his scene by time (d432L32; cross at 90, 100, 108 s, G by time at 133 s, then 300 s): NO_CRASH,
  0 kernel lines; at the end game-main, Render Thread and the audio thread each used 55-61 % of a core. The lean
  build writes no fps line, so there is no number, and nobody looked at the picture.
- d432L31 before it was my setup miss (the frame-gated route cannot start a lean build); not a result.

Not done: per-item arms (the gain is of D, M, W, S, P together), the call-graph profile, the 12 compiler warnings
(all in code that was there before), the gameplay imports (one acb ~870 ms, one dcb ~585 ms per run, unchanged).

## Result 9: the scene A/B of the swap form against shared, same night (2026-11-18, 04:58-05:44)

Ordered by top after Result 8: swap form normal `0db6fc7c` against shared `0de9349b`, his scene, 300 s, alternating
T S T S T S (d432T34 ... d432S39; `raw/slot11.out`). Six of six NO_CRASH, 0 kernel lines in every run, no new OOM
line since boot (the count stayed at the one of d432T23), the Plasma shell alive at the end.

| from G+10 s | swap form (T34, T36, T38) | shared (S35, S37, S39) |
|---|---|---|
| flips/s | 34.2, 34.5, 34.6 (mean 34.4) | 31.4, 32.6, 32.6 (mean 32.2) |
| seconds with a gap over 100 ms | 58, 61, 60 | 97, 98, 91 |
| seconds with a gap over 50 ms | 210, 203, 211 | 283, 284, 282 (every second) |
| MemAvailable min / median, MiB | 808-904 / 969-1005 | 840-885 / 963-1027 |
| PSI memory, highest | 5.78, 2.09, 3.54 | 2.62, 2.81, 1.98 |

The swap form is above shared in each pair: +2.2 flips/s on the means (6.8 %), and 35-38 fewer seconds with a gap
over 100 ms. The ranges do not overlap. MemAvailable is the same within the spread. So Result 8's lower numbers
(32.9-34.1) were the night's spread, not a lost gain.
The laptop's kernel stream failed again (`sudo -n stdbuf` is not in sudoers); the evidence for "no kernel line" is
the per-run check and the `dmesg` read at the end of the series (LESSONS R63).

## Verdict

Measured first: on the shared build nothing is saturated (4 of 16 cores busy, the GFX ring 39 % busy); the time goes
to waiting, and a part of that waiting was host work under the device mutex. Removing it (D: no blocking drain at
unmap, W: the anonymous-map check on its own thread, M: the mapping merge instead of the sort, S and P: submission
slots that grow and are made ahead, R: a refused submission ends the game with a record) gives:
- on the route +0.4 flips/s (1.3 %) in 3 of 3 pairs, and seconds with a gap over 50 ms down from 357-446 to 35-51;
- in his scene 56-73 seconds with a gap over 100 ms against 81-114 (of 285) over all runs, and in the same-night
  A/B of the swap form 34.4 against 32.2 flips/s (3 runs each, no overlap; Result 9);
- no crash, no GPU fault in 17 runs of builds 4, 5 and the swap form; one OOM kill of the Plasma shell during a load
  whose owner is open.
Items A, V and X bring nothing as built: A and V are off (V cost speed, A was ordered off), X is never taken while
`k1r` is on. The swap form is built and smoked on both titles; whether it becomes the shared build is top's decision.
