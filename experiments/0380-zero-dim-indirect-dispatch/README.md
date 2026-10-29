# 0380 — Is the F403 class a zero-dimension indirect dispatch? (sources, title side, a guard, a box plan)

**Date.** 2026-10-29. **Laptop only.** No box access and no GPU submission in this experiment. Branch
`exp/0380-zero-dim-dispatch`. Findings F545–F551 (exp 0379 holds F540–F544).

**Question.** F527 puts the ME just past a `DISPATCH_INDIRECT` that passed the host's check, inside the title's
`CS_PARTIAL_FLUSH` after it. The candidates are 0x11d028dd00 (dword 1289), 0x11d02a1600 (1420) and 0x11d02a1800
(1470). F528's timeout probe read x = 0 in the arguments of all six indirect dispatches before dword 1651. The host's
check (`backend/src/indirect_check.cpp`) refuses only x, y or z *above* a limit, so it passes x = 0. Hypothesis
H0380: the hang is a dispatch whose arguments hold a zero (or otherwise degenerate) dimension. Four parts:

1. What do public drivers and documents say gfx10 does with a zero or degenerate dispatch?
2. Does the title issue x = 0 dispatches in healthy frames? What y/z do the candidates use?
3. A guard in the host check, default off, with unit tests.
4. A box test plan (not run).

## 1. Sources

All Mesa citations are the laptop's shallow clone `refs/mesa_mesa` at **ab2374a** (2026-10-22), sparse
`src/amd/{common,vulkan,addrlib}`. Linux citations are **v7.2** from git.kernel.org `/plain/…?h=v7.2`:
`drivers/gpu/drm/amd/amdgpu/gfx_v10_0.c` (blob a9961d50) and `nvd.h` (blob 56f1bfac).

**(a) RADV emits zero-group dispatches unguarded, on every gfx level and in the title's own form (F545).**
- `radv_CmdDispatchBase` / `radv_CmdDispatchIndirect2KHR` (radv_cmd_buffer.c ~15660–15700) go straight to
  `radv_compute_dispatch`. Neither tests for a zero count.
- `radv_emit_dispatch_packets` (15371) puts the counts unchanged into `DISPATCH_DIRECT`. For an indirect dispatch on
  the gfx queue it emits `SET_BASE` (via `radv_emit_indirect_buffer`) and then the 3-dword GFX-form
  `DISPATCH_INDIRECT` (offset 0, initiator), with no look at the arguments. That is the same form as the title's
  dispatches at 1289/1420/1470 (`experiments/0376-…/raw/dcb-walk.txt`).
- The only workaround on that path is the GFX7 compute-queue 32-byte alignment copy
  (`has_async_compute_align32_bug`, ac_gpu_info.c:1054; radv_cmd_buffer.c ~15404).
- RADV ships on gfx10 and Vulkan lets a dispatch have zero groups. So in Mesa's view a zero-group
  `DISPATCH_INDIRECT` on the gfx ring is a legal no-op. TODO(verify): the Vulkan spec's wording for zero group
  counts, and which CTS cases cover an indirect dispatch with a zero count.
- `ac_gpu_info.c` (ab2374a) lists no gfx10 bug for zero or unaligned dispatches. Its one zero-count hang is
  `has_taskmesh_indirect0_bug` (1056–1066): "Firmware bug with DISPATCH_TASKMESH_INDIRECT_MULTI_ACE packets. On old
  MEC FW versions, it hangs the GPU when indirect count is zero". That entry is for GFX10.3, a different packet and
  the MEC, not the gfx ME. So zero-count firmware hangs do exist on AMD CPs, but none is listed for this packet.
- **Not read:**
  - radeonsi `si_compute.c`: gitlab.freedesktop.org answered with a bot wall and the GitHub mirror path failed, so
    the laptop's sparse clone does not have it.
  - PAL / AMDVLK: one search found nothing.
  - AMD's public PM4 documentation for gfx10: not found.

  TODO(verify) for all three.

**(b) Other gfx10 dispatch hazards in the sources (F546).**
- `UNORD_DISPATCH`: v7.2 `gfx_v10_0.c:6990` sets `CP_HQD_PQ_CONTROL.UNORD_DISPATCH = 1` in the compute MQD. A search
  snippet of an amd-staging commit says it avoids "a potential deadlock in GC 10.x and newer" (commit text not read:
  bot wall; TODO(verify)). It applies to compute HQDs, not to the gfx ring the F403 class stops (F531).
- GDS ordered append: `gfx_v10_0.c:8689-8698` describes "a hw deadlock" from ME/GDS wave-ID mismatch "when at least
  5 compute pipes use GDS ordered append". The title's sampled initiators do not set `ORDERED_APPEND_ENBL`: 0x41,
  0x8041, 0x61 and 0x2045 (exp 0378 `raw/B1-samples/*/regs-1.txt`); bit 3 per v7.2 `gc_10_1_0_sh_mask.h:17071-17083`,
  as the sampler decodes it.
- `ORDER_MODE` (0x40) is RADV's default on GFX7+ (radv_device.c:1640-1646, "allow launching waves out-of-order"). So
  `ORDER_MODE` alone is the common case and no known hazard.
- **`FORCE_START_AT_000`.** RADV sets it on *every* indirect dispatch (radv_cmd_buffer.c:15227-15229): "Indirect CS
  does not support offsets in the API. Must program this in case there have been preceding 1D RT dispatch or
  vkCmdDispatchBase". On a direct dispatch with a start offset, "The blocks in the packet are not counts but end
  values" (15259).
  - So with the bit clear, the CP begins at `COMPUTE_START_X/Y/Z` and the dimensions are end values.
  - The title's 0x41 / 0x8041 initiators do not set it. If `COMPUTE_START_X` were ever non-zero at a dispatch whose
    x is 0 (or smaller than the start), the grid would be degenerate (end < start). What gfx10 launches then is
    TODO(verify).
  - In all 40 healthy samples of exp 0378, `COMPUTE_START_X/Y/Z` read 0.
- `CS_PARTIAL_FLUSH`: no public source found for a hazard between a zero-group or degenerate dispatch and the
  partial flush after it, nor a "ping-pong" one. TODO(verify).

## 2. The title's side (F547)

- **Healthy frames.** The 40 healthy `COMPUTE_*` samples of exp 0378 (`raw/ana.txt` lines 5–44, 206–239) have no 0 in
  `COMPUTE_DIM_X/Y/Z`. The smallest grid is [1 1 1] (0x11d021a400, 0x11d0287900). 0x11d0288800 [61440 1 1] occurs 4
  times, and `START` is [0 0 0] in all 40.
  - This does **not** show that x = 0 dispatches are rare. A dispatch of no groups ends at once, and 40 samples land
    on the dispatch the ME last loaded. Whether `COMPUTE_DIM_*` even holds an indirect dispatch's arguments is
    F531's open TODO.
  - The healthy journal has no dispatch list (F537), so it cannot tell either.
- **Shape of the candidates.** At the timeout the probe read groups 0 × 1 × 1 for all three candidates
  (`experiments/0376-…/raw/probe-extract.txt`): 0x11d028dd00, arguments at 0x11d0571f00; 0x11d02a1600 and
  0x11d02a1800, both at 0x11d05df300. So y = z = 1, and a degenerate dispatch here can only be x = 0.
  - 0x11d05df300 is shared by four dispatches (1420, 1470, 1520 0x11d028ae00, 1550 0x11d02a1600). In F506's hang
    (23:36) it read 1295 × 1 × 1.
- **Zeros where the CP never got to.** Whichever candidate is stuck, at least one dispatch *after* it reads x = 0 at
  the timeout:
  - if 1289 is stuck: 1329 (0x11d0289c00, 0x11d0571d00);
  - if 1420 or 1470 is stuck: 1520/1550 (0x11d05df300).

  The CP never reached those, so it did not consume them. Either the title's stream does hold x = 0 dispatches, or
  the zeros were written by something else. Candidates are the stuck dispatch's own waves, or the two `DMA_DATA` at
  1354/1376, whose targets the committed walk does not record. 1651 (0x11d0571b00), two slots below 1289's
  arguments, still read 3498.
- **The physical contradiction.** Per F527 the flush covers the one dispatch before it. The hang has waves resident
  in SE0/SE1 with SPI/TA/TCP busy (F490, F526, F535). A dispatch that launched zero groups would put no waves for that
  flush to wait on. So *if the stuck dispatch read x = 0, the waves are not explained*, unless gfx1013's CP launches
  something for x = 0, or the start/end form of the previous point applies (both TODO(verify)).
  - The reading that fits all the facts: the dispatch ran with x > 0 and the argument was rewritten afterwards
    (the caveat in the task). An example is a work counter that the consumer's waves reset, while those waves still
    run.
  - `EA_LINK_BUSY` clear with TA/TCP busy (F535) fits waves that spin on data their caches already hold. That is an
    alternative mechanism, not shown here (TODO(verify)).
- **The one read that decides it** (read-only, already deployed if sampler 0377 is installed; F530, F536): at the
  next F403-class hang, the sampler's `COMPUTE_PGM`, `COMPUTE_DIM_X/Y/Z`, `COMPUTE_START_X/Y/Z` and
  `COMPUTE_DISPATCH_INITIATOR` for `gfx_0.0.0`.
  - PGM a candidate with DIM_X = 0 (START 0): H0380 stands, and part B below becomes the test.
  - PGM a candidate with DIM_X > 0: the dispatch launched groups, the zero was written later, and H0380 is refuted
    for this event.
  - START > DIM: the degenerate start/end case of §1(b).
  - Caveat: F531's TODO, whether `DISPATCH_INDIRECT` leaves its fetched counts in `COMPUTE_DIM_*`. Exp 0378's
    healthy [61440 1 1]-style grids of indirect-looking programs suggest yes, but not proven.

## 3. The guard (F548)

`indirect_check::apply(…, bool zero_dims = false)` (`backend/include/bc5/indirect_check.hpp`,
`backend/src/indirect_check.cpp`): for every checked dispatch (GFX form and MEC form; not draws), three more packets
after the per-dimension limits:

```
COND_WRITE   x == 0 ? flag = 0      (function 3, reference 0, mask 0xffffffff; then y, z)
```

- The rest of the check is unchanged: confirm `WRITE_DATA`, `PFP_SYNC_ME`, then `COND_EXEC` over the dispatch.
  Everything is compared by the CP after `PFP_SYNC_ME`, so the guard sees the arguments the dispatch is about to
  read, not the host's stale copy. The only exception is a write landing between the check and the dispatch's own
  fetch, the same window as 0052's check.
- Encodings:
  - function 3 = "==": v7.2 `nvd.h` `WAIT_REG_MEM_FUNCTION` list; RPCSX `rpcsx/gpu/Pipe.cpp` `compare()` (e8ae148)
    case 3, which `condWrite` uses.
  - The other fields as in 0052.
- 27 dwords per dispatch (`kZeroDwords`), `Stats::zero_checked`.
- With the 0341 staircase on, the guard comes before it. The guard's writes only clear the flag, so the order does
  not matter.
- **Switch.**
  - `BC5_DIRECT_GPU_CHECK_ZERO=1` in the host's environment (`backend/src/direct.cpp`, read in `Device::open`).
  - Unset or `0`: off, and the IB is byte-identical to before.
  - When on, one line at open and one in the close summary ("zero-dimension guard on N checked dispatches"). How many
    the CP actually skipped is not visible to the host. `BC5_DIRECT_ARGS_HISTOGRAM` (0341) gives the stale host-side
    view, with x = 0 as class 0xff.
- **`direct-selftest --zero-check`** (`backend/experiments/direct-selftest/main.cpp`): 0052's `--cp-check` with the
  guard on and four more triples (0,1,1), (1,0,1), (1,1,0), (0,0,0), which must not write the result. No shader runs,
  and it only does anything with `--submit`. `--cp-check` alone keeps its five cases.
- **Tests.** Catch2 `[indirect_check]` "the zero-dimension guard (experiment 0380)", in five sections:
  - the exact packet sequence;
  - off by default;
  - with the staircase;
  - MEC form;
  - draws untouched, and the IB's own `COND_EXEC` grown by the guard.

  Laptop (Windows 11, MSVC 19.51 / VS 18, Ninja, `BC5_WITH_AMDGPU=OFF`):
  `cmake -S backend -B build-win -G Ninja -DBC5_BUILD_TESTS=ON -DBC5_WITH_AMDGPU=OFF` then
  `cmake --build build-win` and `build-win\bc5_backend_tests.exe`. The result: **All tests passed (33962 assertions
  in 92 test cases)**, and 492 assertions in 9 `[indirect_check]` cases.
  - **Not compiled here:** `direct.cpp` and `direct-selftest` (they need libdrm, `BC5_WITH_AMDGPU=ON`). Their build
    is step A0 of the box plan.

## 3b. The second guard: `FORCE_START_AT_000` (F551, the top session's follow-up to F546)

`indirect_check::apply(…, bool force_start = false)`, switched by `BC5_DIRECT_FORCE_START_000=1` in the host's
environment (`backend/src/direct.cpp`). Unset or `0`: off, IB unchanged.

- **What it does.** Every `DISPATCH_INDIRECT` the check pass sees gets `COMPUTE_DISPATCH_INITIATOR` bit 2
  (`FORCE_START_AT_000`) ORed into its initiator dword. That is the packet's last dword in both forms: GFX form
  dword 2, MEC form dword 3.
  - It covers checked and unbased dispatches, GFX and MEC form.
  - Bit 2 per v7.2 `gc_10_1_0_sh_mask.h:17071-17083` and Mesa's `gfx10.json` (`tools/bc5-agc/regdb/gfx10.json:11831`).
  - It adds no packet, and the check before the dispatch stays byte-identical.
  - This is what RADV does for every indirect dispatch (radv_cmd_buffer.c:15227-15229, ab2374a). Without the bit
    the CP starts at `COMPUTE_START_X/Y/Z` and the counts are end values (15259-15263).
  - `Stats::start_forced` counts the initiators it changed. The close summary prints "FORCE_START_AT_000 set on N of
    M indirect dispatches".
  - It runs only where the GPU check pass runs (`gpu_check_indirect`, on in play).
  - Direct dispatches and indirect draws are untouched.
- **Risk.** If the title *meant* an indirect dispatch to start at a non-zero `COMPUTE_START` (a base offset that RADV's
  API cannot express), forcing the start at 0 changes which groups run. That would be a visual change, so look for it
  in A2.
- **Tests.** Catch2 "FORCE_START_AT_000 on indirect dispatches (experiment 0380)", six sections:
  - the GFX form, 0x41 → 0x45, the rest byte-identical;
  - an initiator that already has the bit is not counted;
  - unbased;
  - MEC form, 0x61 → 0x65;
  - direct dispatch and indirect draw untouched;
  - combined with the zero guard.

  Laptop: **All tests passed (34019 assertions in 93 test cases)**, 10 `[indirect_check]` cases.
- **What decides F546 without running the guard.** Sampler 0377 records `COMPUTE_START_X/Y/Z` in every sample (F530).
  - The next F403-class hang shows whether START was non-zero, together with `DIM` and `INITIATOR`.
  - START = 0 at the hang means F546's degenerate start/end case did not happen there, and this guard cannot help.
  - START > 0 with the title's 0x41 initiator makes this guard the candidate fix, tested by A2 with
    `BC5_DIRECT_FORCE_START_000=1`.

## 4. Box test plan (NOT run; every step needs the top session's GO, steps A1, A2 and B the maintainer's yes)

Box etiquette as usual: BOX-LOCK line, claims in BOX-QUEUE, never during the maintainer's play, unique run tags,
kernel log streamed to the laptop. Shared builds, `play-pkg.sh` and patch 0001 are not touched (D19): everything runs
from a private build in `~/bc5-work/exp0380/`.

**A0 — build and unit tests (CPU only, no GPU).**
- Check out this branch into `~/bc5-work/exp0380/in/`.
- In the `ubuntu` distrobox:
  `cmake -S backend -B ~/bc5-work/exp0380/backend-build -G Ninja -DCMAKE_BUILD_TYPE=Release -DBC5_WITH_AMDGPU=ON -DBC5_BUILD_TESTS=ON`,
  then `cmake --build …` and `…/bc5_backend_tests`.
- Expect 92/92 and `direct.cpp` compiling with `-Werror`.
- Then relink a private `kyty_emulator` against the private `libbc5_backend.a`. Use the compile and link commands of
  the shared normal build (as exp 0379's `build0379.sh` does for its unit). The script is not written yet: write it
  as `raw/build0380.sh` before the GO.

**A1 — the guard on the CP, no shader (`--submit`, low risk: maintainer's yes).**
`direct-selftest --submit --zero-check`.
- Expect 9 × "as expected": the five 0052 triples as before, and the four zero triples with result 0xdead and
  flag 0.
- This is 0052's `--cp-check` sequence (passed on this ring), plus `COND_WRITE` with function 3.
- Worst case: a CP hang on a malformed packet, after which `bc5-gpu-watch` reboots the box.

**A2 — A/B on the second title, RT on, the scripted route (maintainer's yes).**
- **Route.** The S6N route as `s6n0372.sh` / exp 0378's B1: route save copy, `o2-continue.cmd`, RT on, no RT-off drop
  line by 180 s, sampler 0377 resident.
- **Arms.**
  - OFF: the private binary without the variable.
  - ON: `BC5_DIRECT_GPU_CHECK_ZERO=1`, or `BC5_DIRECT_FORCE_START_000=1` as its own arm if the next hang's sampler
    record shows START > 0 (F551) (plus `BC5_DIRECT_ARGS_HISTOGRAM=1` in both arms, for the host-side zero
    count).
  - Interleave ON/OFF, one 10-minute run each, saves checked before and after.
- **Hang frequency.** The base rate is low: about 1 in 25 bench runs (F491), plus the maintainer's play events.
  - At 1/25, zero hangs in N ON-runs has probability 0.96^N: about 0.13 at N = 50, 0.05 at N = 75. So a "the guard
    removes the hang" verdict needs ≥ 75 ON-runs (≈ 13 h), or the maintainer's play with the guard on over several
    sessions.
  - A *hang with the guard on* is decisive at once. Its sampler record shows whether the stuck dispatch had x = 0:
    with the guard on, a stuck x = 0 dispatch cannot have run.
- **Visual change.** Per arm:
  - flips/s;
  - the 0341 histogram's zero-class count;
  - a screenshot at the route's fixed checkpoints (the lake bench view and the fight start);
  - the maintainer's look at the RT reflections.

  If the title needs a zero-group dispatch's side effects (none exist by the API, so a skip should be invisible),
  look for missing reflections or particles.
- **Pass.** No visual difference, no kernel line in either arm, and either fewer F403-class hangs ON than OFF, or the
  first ON-hang's sampler record (whichever comes first).

**B — synthetic zero-dimension indirect dispatch on the gfx ring (`--submit`, MAY HANG THE MACHINE; maintainer's
explicit yes; only after A1).**
- Not built yet: a mode `dispatch-min --indirect X,Y,Z [--initiator HEX] [--start X]`. It reuses dispatch-min's memset
  shader and sequence, putting the arguments in the mapped buffer and emitting `SET_BASE` index 1 +
  `DISPATCH_INDIRECT` (GFX form) + `EVENT_WRITE CS_PARTIAL_FLUSH` + the fence.
- Cases, each one submission, stopping at the first failure:

  | Case | Arguments | Initiator | `COMPUTE_START_X` | Purpose |
  |---|---|---|---|---|
  | 1 | (64, 1, 1) | 0x41 | — | control |
  | 2 | (0, 1, 1) | 0x45 (RADV's form) | — | |
  | 3 | (0, 1, 1) | 0x41 (the title's form) | 0 | |
  | 4 | (1, 0, 1), (1, 1, 0) | 0x41 | — | |
  | 5 | (0, 1, 1) | 0x41 | 1 | end < start |

- Expected from §1: cases 1–4 complete, write nothing (except case 1), and leave the fence advanced. Case 5 is the
  unknown.
- Before running: save everything, then sync. A ring timeout whose reset fails reboots the box through
  `bc5-gpu-watch`, and the devcoredump is kept by `bc5-devcoredump`.
- **Interpretation.** A hang in 2–4 is a gfx1013 zero-count firmware bug: H0380's mechanism, and the guard is the
  fix. A hang only in 5 points at `FORCE_START_AT_000`, and a host fix would set that bit on indirect dispatches as
  RADV does (a new experiment). No hang anywhere: H0380 needs the "launches something for x = 0" premise and falls
  back to the rewritten-argument reading.

## Result

- Sources read and cited (F545, F546). The title-side evidence was re-read from exps 0376/0378 (F547).
- The guard is built, default off, with unit tests passing on the laptop (F548).
- A second guard, `FORCE_START_AT_000` on indirect dispatches, is built the same way: default off, with unit tests
  (F551).
- The box plan is written; nothing ran on the box.

## Verdict so far

**H0380 is not supported by the sources and sits badly with the hang's own state, but is not refuted (F549).**
Strength: medium-low against.
- Against:
  - Mesa treats zero-group `DISPATCH_INDIRECT` on the gfx ring as legal and emits it unguarded on gfx10.
  - No zero-dispatch workaround is listed for gfx10.
  - A zero-group dispatch would leave no waves for the flush to wait on, yet the hang has waves resident and busy.
  - x = 0 also sits in arguments the CP never reached.
  - F506's hang read 1295 at the shared argument address.
- Open: gfx1013's own firmware behaviour for x = 0 and for end < start without `FORCE_START_AT_000`, and radeonsi /
  PAL / AMD's PM4 documentation.
- The decisive read-only step is the next F403-class hang under sampler 0377 (F550). The guard and box steps A1/A2/B
  wait for the maintainer.
