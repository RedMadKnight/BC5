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

(pending: the profile slot is after exp 0430's A/B and exp 0429's set, about 14:45 on 2026-11-17)

## Verdict

(pending)
