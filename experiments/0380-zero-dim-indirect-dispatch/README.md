# 0380 — Is the F403 class a zero-dimension indirect dispatch? (sources, title side, a guard, a box plan)

**Date.** 2026-10-29. **Laptop only.** No box access and no GPU submission in this experiment. Branch
`exp/0380-zero-dim-dispatch`. Findings F545–F613. Exp 0379, not yet merged, holds F540–F543, F563–F565 and F620–F626; its F563–F565 collide with this experiment's and take new numbers at its merge (int/0380-to-main). One box session, CPU only (step A0, 11:28–11:31, on the top
session's GO).

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
  - **Not compiled on the laptop:** `direct.cpp` and `direct-selftest` (they need libdrm, `BC5_WITH_AMDGPU=ON`).
    Box step A0 compiled them (§4, F552).

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

**A0 — build and unit tests (CPU only, no GPU). DONE 2026-10-29 11:28–11:31 (F552).**
- Run by `raw/build0380.sh` (md5 f3222383) on the branch's `backend/` at 52d9d8a, unpacked by `git archive` into
  `~/bc5-work/exp0380/in/`.
- Built into `~/bc5-work/exp0380/backend-build` in the `ubuntu` distrobox: clang 21.1.8, cmake 4.2.3, Release,
  `BC5_WITH_AMDGPU=ON`, `-Werror`.
- Result: **0 warnings, `direct.cpp` and `direct-selftest` compiled, Catch2 93/93 (34,018 assertions), 10/10
  `[indirect_check]`**. Private archive 584dca77, not installed. Logs in `raw/box-A0/`.
- Lock line written and cleared. Claim and done lines are in `~/bc5-work/BOX-QUEUE` and `~/bc5-work/exp0380/CLAIM.txt`.
  It ran after 0379's done line, with no emulator running.
- The first attempt used the container's default `c++` (GCC 15) and stopped at `-Werror=array-bounds` in a
  *pre-existing* test, "a COND_EXEC range whose grown count overflows…" (`indirect_check_test.cpp:112`, `ib.insert`
  of an initializer list, a GCC false positive at `-O3`). The box's builds use clang (`tools/scripts/bc5-build.sh:163`,
  exp 0379's `build0379.sh`), and the script now does too.

The plan as first written, for the record:
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

## 5. The 12:12 hang: the F403 class caught with its program and grid (F553–F557)

**Box.** Reads only, 12:15–12:23 (a fresh boot, the maintainer not playing), then the CPU-only compile check of §6,
12:23–12:25. The lock line was `top exp 0380 | reads only: 12:12 hang …` and was cleared at the end. Claim and done
lines are in `~/bc5-work/BOX-QUEUE` and `~/bc5-work/exp0380/CLAIM.txt`. The filtered extracts are in
`raw/hang-1212/`; the devcoredump, the journal and the IB stay private. Scripts: `raw/walk0380.py` and
`raw/span0380.py`, structure only. walk0380.py's program column is not reliable: the title loads `COMPUTE_PGM` by
`LOAD_SH_REG_INDEX`.

**The play.**
- The maintainer's second play of the test shortcut "BC5 emulator (test 0379+0380)", binary 459d34cd.
- Settings: exp 0379 SKIP mode on `zero-list-20261029-120000.txt` (2 heaps, 1,218 MiB, 52 runs),
  `BC5_DIRECT_FORCE_START_000=1`, one ring, the shared guards (0341 staircase on), RT on.
- At 12:12:06 `ring gfx_0.0.0 timeout`. The reset failed and the box rebooted.

**What the records show (F553).**
- Sampler 0377, 5 samples over 0.53–1.70 s, all identical:
  - `COMPUTE_PGM` 0x11d0289c00;
  - `COMPUTE_DIM` [65536 196610 2752552] = 0x10000 / 0x30002 / 0x2a0028;
  - threads [64 1 1], START [0 0 0], initiator **0x45**;
  - `GRBM_STATUS` 0xa0407028, SE0/SE1 0x0a000036, PFP 0xea0–0xea1, ME 0x77a–0x77b.

  0x45 is the title's 0x41 with exp 0380's forced bit, which only indirect dispatches get.
- The journal's timeout probe for dcb #94500 (11,745 dwords; acb #94501, 84 dwords; both TIMEOUT after 2,050 ms)
  names the first indirect dispatch of the dcb: **title dword 1287, program 0x11d0289c00, arguments at 0x11d0571d00,
  read 111 × 1 × 1 at the timeout**.
- Then come F506/F528's family: 0x11d02a1600, 0x11d02a1800 and 0x11d028ae00 at 0x11d05df300 (0 × 1 × 1), and
  0x11d02a2e00 at 0x11d0571b00 (6,136 × 1 × 1).
- In the devcoredump's IB #0 (the filtered IB, 13,408 dwords; `CP_IB1_BUFSZ` 0x2cc0, so 1,952 dwords fetched) that
  dispatch is dword **1375**. It is preceded by:
  - `SET_BASE` index 1 = 0x11d0571d00 (1249);
  - `INDEX_BASE` 0x11e9db6280 (1253);
  - `INDEX_BUFFER_SIZE` 0xffffffff (1256);
  - `NUM_INSTANCES` 1 (1258);
  - the host's check (1287–1374).
- The check's packets in the dump: `COND_WRITE` x > 0x100000, y > 0x400, z > 0x400 on 0x11d0571d00/04/08 → flag = 0;
  then the 0341 staircase (y or z > 1 → flag2; `COND_EXEC` flag2 over x > 0x10000); confirm, `PFP_SYNC_ME`,
  `COND_EXEC` flag, 3 dwords.
- The header histories, read newest-first (F527):
  - PFP: `ACQUIRE_MEM`, `EVENT_WRITE`, `DISPATCH_DIRECT`, `DMA_DATA` ×2, `SET_SH_REG` (17), `LOAD_SH_REG_INDEX`,
    `DISPATCH_INDIRECT`;
  - ME: `EVENT_WRITE`, `DISPATCH_DIRECT`, `DMA_DATA`, 0xc0011800, `DMA_DATA`, 0xc0011800, `SET_SH_REG`, 0xc0016300.

  They match the IB at 1375 → 1378 (`LOAD_SH_REG_INDEX`, 10 registers from 0x11e072fa94) → 1383 → 1400/1407
  (`DMA_DATA`) → 1414 (`DISPATCH_DIRECT` 13 × 8 × 1, program 0x11d02a0e00 per the probe) → 1419 (`EVENT_WRITE` 7) →
  1421 (`ACQUIRE_MEM`). So the ME is in the `CS_PARTIAL_FLUSH` at 1419. The SH registers it read still name the
  *indirect* dispatch at 1375 (program, initiator 0x45), not the direct one at 1414 that the ME has already passed.
  The readable `COMPUTE_*` copy therefore looks like the dispatch the SPI is still launching (TODO(verify)).
- So the stuck dispatch is 1375, launched with **65,536 × 196,610 × 2,752,552 groups**. That grid never finishes,
  which fits F535's "SPI busy, no memory traffic": waves that leave at once for out-of-range group ids
  (TODO(verify)).

**Was it exp 0379's zero skip? No sign of it (F554).**
- The arguments are real memory, not canary. At the timeout the host's CPU probe read 111 at 0x11d0571d00 and
  6,136 at 0x11d0571b00 (same page). A skipped chunk is GPU-mapped onto its canary slice, so its memfd pages would
  stay 0 for the CPU. GPU-written data there means the chunk was imported.
- The CB0 hint windows 0x11ce5b0000–0x11ce600000 (+64 MiB) cover these addresses, and a hint takes skipped chunks
  back (exp 0379 README, lever item 3).
- The slot is the class's, from before the skip existed. At 09:48 (no skip) the dcb opened the same way: `SET_BASE` /
  `INDEX_BASE` / `INDEX_BUFFER_SIZE` / `NUM_INSTANCES`, then the first indirect dispatch (0x11d028dd00, dword 1289,
  F527's first candidate). Program 0x11d0289c00 at 0x11d0571d00 was its *second* dispatch (1329, F528). F403, F416
  and F506 had no skip at all.
- The play's one canary hit (run 37, file 0x1cb400000 + 24 MiB) is at journal line 57,296 of 253,396, long before the
  hang.
- Not placed: the `LOAD_SH_REG_INDEX` source 0x11e072fa94 and the index base 0x11e9db6280 against the zero list. The
  logs have no guest-VA → heap-file mapping.

**Why the check did not catch it: it never saw these values (F555).**
- The check does test y and z (> 0x400) on this dispatch's own argument address. 196,610 or 2,752,552 there would
  have cleared the flag, and the `COND_EXEC` would have skipped the dispatch.
- Memory read 111 × 1 × 1 at the timeout. Across four hangs this family's arguments read x ∈ {0, 111, 1,295, 3,498,
  6,136} with y = z = 1 (F506, F528, this one), and the 0341 histogram found only one-dimensional legitimate classes
  (F414).
- So the CP's *argument fetch* for this `DISPATCH_INDIRECT` returned other data than its own `COND_WRITE` polls of
  the same address just before it.
- The values look like 16-bit index data: (0, 1), (2, 3), (0x28, 0x2a). The dispatch is the first one after an
  `INDEX_BASE` / `INDEX_BUFFER_SIZE` 0xffffffff pair.
- Hypothesis H0380b (TODO(verify)): on gfx1013, a GFX-form `DISPATCH_INDIRECT` right after
  `INDEX_BASE`/`INDEX_BUFFER_SIZE` sometimes fetches its arguments from the wrong place, perhaps through the index
  fetch path. That matches the class's rate (rare) and slot (the dcb's opening dispatch).
- A guard that polls memory (y/z limits, the product staircase, F548's zero guard) cannot catch a wrong fetch.
  Moreover, x = 65,536 equals the staircase's 2^16 and is not above it.

## 6. A y/z limit anyway, and what would decide H0380b (F556, F557)

- **`BC5_DIRECT_GPU_CHECK_YZ`** (default off): `indirect_check::parse_yz_limit` / `tighten`.
  - `1` sets y ≤ 256, z ≤ 64; `<y>[:<z>]` sets them; the limits only ever lower the host's 2^10.
  - The limits come from the title's healthy maxima: y 180 and z 4 in exp 0378's grids (320 × 180 × 1, 4 × 32 × 4;
    F536), and y = z = 1 for every indirect dispatch on record.
  - The product bound already exists: the 0341 staircase, `BC5_DIRECT_GPU_CHECK_PRODUCT="x_limit:yz_min"`. A tighter
    `x_limit` such as 65535 would refuse x = 65,536 with y > 1.
  - Catch2 "tighter y and z limits (experiment 0380, the 12:12 hang)": parsing, never raising, and the `COND_WRITE`
    references. Laptop 94/94 (34,043 assertions).
  - Box (12:23–12:25, CPU only): clang 21.1.8 Release `-Werror`, 0 warnings, 94/94 (34,042), private archive
    d41fde2f (`raw/box-A0b/`).
  - **It would not have caught 12:12** (F555). It guards against garbage that is really in memory.
- **What decides H0380b, cheapest first:**
  1. **Offline, no box.** The dcb of every class event should open with `SET_BASE` + `INDEX_BASE` + the first
     indirect dispatch. Recheck F416 R2's and F506's walks; the timeout dumps `ib-timeout-*.bin` hold the dcbs.
  2. **Read-only probe addition.** At a timeout, log 12 bytes at `INDEX_BASE` (here 0x11e9db6280 + 0) and compare them
     with the sampler's `COMPUTE_DIM`. Equal values mean the CP fetched the index buffer.
  3. **Host fix candidate, design only (a new experiment; GPU, maintainer's yes).** Move the title's
     `INDEX_BASE`/`INDEX_BUFFER_SIZE` that precede a `DISPATCH_INDIRECT` to just before the next draw, or put a
     `SET_BASE` index 1 again right before each checked dispatch. Neither changes what the title draws.
  4. Synthetic (part B of §4, extended): `INDEX_BASE` → `DISPATCH_INDIRECT` on the gfx ring. It may hang.
- **Aside.** The pass saw 270,977 of 773,350 dispatches that already had `FORCE_START_AT_000`. That suggests some IBs
  pass through the check twice (TODO(verify)).

## 7. Every class dump against the INDEX_BASE pattern, and the rebase fix candidate (F558–F560)

**Box.** Reads only, then CPU-only builds, 12:29–12:45, under the lock line `top exp 0380 | reads only: the F403-class
devcoredumps …`, cleared at the end. Done line in BOX-QUEUE. Scripts `raw/class0380.py` and `raw/near0380.py`, structure
only. Output in `raw/class-dumps-pattern.txt` and `raw/class-dumps-near.txt`.

**Which dumps.** Of the 24 devcoredumps of 10-26 … 10-29, nine have the class signature (`GRBM_STATUS` 0xa0407028 with
`CP_STALLED_STAT2` 0x18000): 10-26 10:08, 12:20, 12:21:44, 18:01:16; 10-27 12:39 (F416 R2); 10-28 18:15, 23:36; 10-29
09:48, 12:12. Three more are near-class (0xa0403028, the same `STALLED_STAT2`): 10-27 07:28 (F413's fault), 18:55;
10-28 10:48. 10-29 06:34 is not class (F519).

**Two sub-classes (F558).**
- **A, 10-26 … 10-27 (5 class + 3 near-class).** The hung IB is a large dcb: 5,736–28,760 dwords, 45–400 indirect
  dispatches, initiator 0x61 (the BVH builders). It has **no `INDEX_BASE` at all**. This is F403/F404's era of runaway
  grids that were really in memory, e.g. 818 × 820 × 819, which passes the per-dimension limits (y, z ≤ 2^10) and the
  staircase (F416). The pattern does not apply here. F556's y/z limit (y ≤ 256) would refuse such a grid.
- **B, 10-28 18:15 → 10-29 12:12 (4 events).**
  - The hung dcb opens the same way every time: a draw at 0, then `SET_BASE` 1 at 1249, `INDEX_BASE` at 1253
    (0x1210000000 twice, 0x11e26368c0, 0x11e9db6280) and `INDEX_BUFFER_SIZE` 0xffffffff at 1256.
  - Then the first `DISPATCH_INDIRECT` at 1375/1377, with the fetch at 1,920–1,952 dwords.
  - The PFP history is `ACQUIRE_MEM`, `EVENT_WRITE`, `DISPATCH_INDIRECT`, then the check's packets; at 12:12 it has
    `DISPATCH_DIRECT` instead (§5).
  - That history allows these dispatches ("followed by `EVENT_WRITE` 7"): 18:15 {1377, 1836}, 23:36 {1377, 1515},
    09:48 {1377, 1698, 1836}. 12:12 is pinned to 1375 by the sampler.
  - In all four the dispatch that comes first after `INDEX_BASE` is allowed, and at 12:12 it is the one.
  - Each dcb holds 1–2 dispatches that are first after an `INDEX_BASE`.
- **How often in healthy play: not countable from what is captured.**
  - No healthy dcb or dispatch journal is on the box (F537). The `ib-timeout-*.bin` dumps are all hangs.
  - Sub-class B's opener is F506's "family that opens most frames' dcb", so the pattern almost certainly runs once per
    frame (~37 a second) and hangs about once an hour of play. That is a rare race, not a deterministic alias: a fixed
    alias would hang every frame.
  - A count needs a dispatch journal of a healthy run (`BC5_DIRECT_DRAW_JOURNAL`, F149). That is a box run, not done.

**Sources for SET_BASE and INDEX_BASE (F559).**
- `SET_BASE` index 1 is the base for indirect arguments:
  - RADV emits `SET_BASE` (1, va) before a gfx-queue `DISPATCH_INDIRECT` and indirect draws
    (`radv_emit_indirect_buffer`, radv_cmd_buffer.c:12305-12313, ab2374a).
  - RPCSX's `setBase` case 1 sets `drawIndexIndirPatchBase`, which its `dispatchIndirect` reads as base + offset
    (rpcsx/gpu/Pipe.cpp:876-895, e8ae148).
  - Linux v7.2 `nvd.h` defines `PACKET3_SET_BASE` 0x11 and `PACKET3_BASE_INDEX`, naming only index 3,
    `CE_PARTITION_BASE`.
- `INDEX_BASE` (0x26) and `INDEX_BUFFER_SIZE` (0x13) set the separate VGT index state: RADV radv_cmd_buffer.c:6308-6313,
  RPCSX `indexBase` → `vgtIndexBase`.
- No public source says that they alias on gfx10, or that a dispatch after `INDEX_BASE` needs anything (TODO(verify)).
  PAL was not reachable from the laptop.
- So the sources do not point to moving `INDEX_BASE`, and that alternative is not built. Re-emitting `SET_BASE`
  directly before the dispatch is the smallest change that makes the dispatch's base the last base state the PFP sees,
  whatever `INDEX_BASE` did.

**The fix candidate (F560): `BC5_DIRECT_REBASE_DISPATCH=1`** (default off;
`indirect_check::apply(…, rebase)`, `Stats::rebased`, `kRebaseDwords` = 4).
- **What it does.** Every checked GFX-form `DISPATCH_INDIRECT` gets `SET_BASE` index 1 with the base in effect, the
  title's own as the pass tracks it, right before it.
  - The SET_BASE sits inside the check's `COND_EXEC` range, whose count is now 7: a refused dispatch skips its rebase
    too.
  - No `PFP_SYNC_ME` is added after it: `SET_BASE` and the dispatch's fetch are both PFP-side (TODO(verify)), and the
    check's `PFP_SYNC_ME` is still just before the `COND_EXEC`.
  - Unbased dispatches, the MEC form and draws are unchanged.
- **Tests.** Catch2 "the SET_BASE rebase before a checked dispatch (experiment 0380)":
  - the packet bytes and the `COND_EXEC` count;
  - the latest index-1 base wins and index 0 is ignored;
  - combined with the zero guard, the staircase and FORCE_START;
  - unbased / MEC / draw untouched;
  - the IB's own `COND_EXEC` grows.

  Laptop 95/95 (34,119 assertions). Box clang 21.1.8 `-Werror`, 0 warnings, 95/95 (34,118), private archive cee8fc22
  (`raw/box-A0c/`).
- **Private binary for the test shortcut (built, CPU only).** `~/bc5-work/exp0380r/kyty_emulator` md5 **1791aeb2**:
  the shared normal build's link command (`ninja -t compdb -x`) with only the backend archive swapped (`raw/link0380r.py`).
  - The same command with the shared archive reproduces the shared binary **58c4a627** byte for byte.
  - Main's backend equals this branch's base (no backend diff 0c13576..origin/main), so the binary differs from the
    shared one by exp 0380's backend alone.
- **The launcher variant, PREPARED, NOT INSTALLED, NOT RUN.**
  - `~/bc5-work/exp0380r/play-pkg-0380r.sh`, md5 f1bf660d, made by `raw/mkplay0380r.pl` from `play-pkg.sh` 55531ab6;
    the diff is `raw/play-pkg-0380r.diff`.
  - It changes the binary, its own log and mount log per start in `exp0380r/play/`, and
    `BC5_DIRECT_REBASE_DISPATCH=1`. Every other exp 0379/0380 switch is unset (FORCE_START, zero guard, y/z, zero
    skip/scan), so it is one change against the maintainer's normal play (one ring, staircase, shadow labels as
    shared).
  - The shortcut file is staged as `~/bc5-work/exp0380r/BC5-test-0380-rebase.desktop.staged`, not on the desktop.
    Installing it (a copy to `~/Pulpit/…desktop`) and playing it waits for the maintainer's yes.
- **What it can show.** Sub-class B ran into the hang about once per hour of RT-on play: 18:15, 23:36, 09:48, 12:12
  across the maintainer's sessions. Several hours of play with the rebase on and no class hang would be evidence for
  it; one class-B hang with it on refutes the base-alias idea. The sampler and timeout probe record every event.

## 8. The rebase fix on the bench: R1 and R2 (F561, F562)

**GO and box.** The maintainer's yes, "Najpierw test skryptem", was relayed by the top session. It covers GPU runs of
`BC5_DIRECT_REBASE_DISPATCH=1` on the scripted route. Runs at 12:44–12:54 and 12:55–13:05, after my lock and claim
lines. The runner wrote and cleared its own `top exp 0380 | rebase run …` lock. The done line is in BOX-QUEUE.

**Live saves.** They read 6560743e7473baa1, not the 86574ead361e510b I was given. The top session confirmed the change
was the maintainer's own play 2 (`prefs.save` at 12:10:39) and set 6560743e7473baa1 as the reference. It was unchanged
before and after both runs (`raw/runs/s6n-saves.txt`).

**Setup.**
- **Binary.** A new archive 86534bb1 (this branch at e0fe42b, with the counter
  `Stats::rebased_after_index_base`) relinked into `~/bc5-work/exp0380r/kyty_emulator` md5 **7943d581**.
  - Same method as §7. The 1791aeb2 binary is kept beside it.
  - Box build: clang `-Werror`, 0 warnings, 95/95 tests.
- **Runner.** `raw/s6n0380.sh` (box md5 7c9920c9), made from exp 0378's `s6n0378.sh` by `raw/mk-s6n0380.pl`, literal
  edits only:
  - its own directory `~/bc5-work/exp0380s` and its lock text;
  - the private binary, md5-pinned;
  - no forced sampler requests;
  - the backend's exp 0380 lines kept per run.
- **Route.** The S6N route as in exp 0378's B1: exp 0196's route save copy, `o2-continue.cmd`, RT on, no RT-off line by
  180 s. The private launcher copy has the same 9-line diff as B1 (`raw/runs/play-pkg-0380s.diff`).
- **The switch.** `BC5_0368_SWITCHES="BC5_DIRECT_REBASE_DISPATCH=1"`, checked in the emulator's environment.
- **Monitoring.** Sampler 0377 was active (`VERSION = "0377"`, service active). The kernel log was streamed to the
  laptop (`raw/runs/R*-kernel-stream.txt`: empty).

**Results** (`raw/runs/R1-*`, `raw/runs/R2-*`; the play logs and journals stay on the box):

| Run | Result | Flips/s | 10-s bins after 150 s | Kernel lines | TIMEOUT | Devcoredumps | Crash lines | Sampler events | SET_BASE re-emitted | First after `INDEX_BASE` |
|---|---|---|---|---|---|---|---|---|---|---|
| R1 | pass | 37.5 (22,356 in 596.7 s) | 354–409 | 0 | 0 | 0 | 0 | 0 | 14,429,590 | 88,420 |
| R2 | pass | 36.5 (21,790 in 596.3 s) | 352–401 | 0 | 0 | 0 | 0 | 0 | 13,894,050 | 85,619 |

- The shared build's B1 ran 37.8 flips/s.
- The counters come from the last periodic summary line of each run. The emulator is killed at 600 s, so there is no
  at-close line, and the true totals are slightly higher.
- The frame profiles show GPU busy 19.3 / 20.1 ms a frame and host prepare 2.53 / 2.57 ms. The rebase adds 4 dwords
  per checked dispatch, ~24,000 dispatches a second.

**Reading (F562).**
- **Safe on the bench.** The fix candidate changes nothing visible in the logs. The frame rate is within noise of the
  shared build (−0.8 % and −3.4 % against B1's single run). The live saves and learned file are unchanged.
- **Exposure.** About 87,000 first-after-`INDEX_BASE` dispatches per 10 minutes (~145 a second), each with the rebase
  in front of it. 174,039 in the two runs.
- **What that does not show.**
  - Sub-class B's bench rate is unknown. F491's "one in ~25 bench runs" is for the whole class, and B appeared in the
    maintainer's play: 18:15, 23:36, 09:48, 12:12.
  - Two clean bench runs are therefore expected even without a fix, and say nothing yet about the hang.
- **Recommendation.** Go ahead with the maintainer's play test with the staged shortcut (§7). The bench shows the
  switch costs nothing measurable and breaks nothing. Sub-class B came about once per hour of his RT-on play, so an
  evening of play is the real test:
  - one class-B hang with the switch on refutes the base-alias idea (and the sampler and timeout probe will record
    it);
  - several hours without one is evidence for it.

## 9. The test shortcut "BC5 emulator (test 0380 fix + 0379)" for the maintainer's long play (F563)

**GO.** The maintainer's "Tak, oba", relayed by the top session: one shortcut combining the rebase fix (with
FORCE_START_AT_000) and exp 0379's zero skip in SKIP mode on his play list, RT on, for a long play.

**Box.** 13:4x–13:55: the lock and claim lines, then the relink, the launcher, the smoke run (whose runner wrote and
cleared its own lock) and the shortcut. Done line in BOX-QUEUE. Nothing shared was written.

**The binary: `~/bc5-work/exp0380f/kyty_emulator`, md5 c442f6c7.**
- It is the shared normal build's link command (`ninja -t compdb -x`) with two inputs swapped (`raw/link0380f.py`):
  - exp 0379t's private `bc5LleAgc.cpp` object (the zero skip, compiled by `build0379t.sh`; md5 17ff00c1, copied to
    `exp0380f/bc5LleAgc-0379t-17ff00c1.cpp.o`);
  - this branch's archive 86534bb1 (e0fe42b, with the rebase; copied to `exp0380f/libbc5_backend-86534bb1.a`, so a
    later rebuild of `exp0380/backend-build` cannot change it). 5c79c56 has no backend change after e0fe42b.
- The method was checked first: the same command with exp 0379t's own archive (584dca77) reproduces exp 0379t's binary
  459d34cd byte for byte.
- Exp 0379's backend part is header-only (`zero_skip.hpp`, compiled into the unit), so exp 0380's archive serves both.
- The binary carries both features' strings.

**The launcher: `~/bc5-work/exp0380f/play-pkg-0380f.sh`, md5 05762c4e.** Made from `play-pkg.sh` 55531ab6 by
`raw/mkplay0380f.pl` (exp 0379t's pattern); the diff is in `raw/runs/S1-launcher-and-zero-skip.txt`.
- The private binary; one log and one mount log per start in `exp0380f/play/`.
- `BC5_DIRECT_REBASE_DISPATCH=1 BC5_DIRECT_FORCE_START_000=1`, with the zero guard and the y/z limit unset.
- The zero skip forced to **SKIP on `~/bc5-work/exp0379t/play-lists/zero-list-20261029-120000.txt`** (md5 7a4f972c).
  There is no scan and no list rotation, and the launcher refuses to start without the list.
- The memory sample once a minute (exp 0379t's `play-sample0379t.sh`, md5 e094a3f5, copied beside it).
- The log's first line names the mode, both switches and the binary md5:
  `== exp 0380f mode: SKIP …zero-list-20261029-120000.txt; BC5_DIRECT_REBASE_DISPATCH=1; BC5_DIRECT_FORCE_START_000=1; binary c442f6c7`.

**The smoke run S1** (`raw/s6n0380f.sh`, from `s6n0380.sh` by `raw/mk-s6n0380f.pl`; its source launcher is the
shortcut's own, with the usual four private edits). S6N route, RT on, 300 s. Live saves 6560743e7473baa1 before and
after. Sampler 0377 active. Kernel stream: two IPv6 MLD notices only.
- Pass at 33.8 flips/s over the whole run and **38.4 in the running scene** (150–290 s; B1 41 there).
- 0 kernel amdgpu lines, 0 TIMEOUT lines, 0 devcoredumps, 0 crash lines, 0 RT-off drop lines.
- The rebase covered 6,619,656 checked dispatches, 38,887 of them first after `INDEX_BASE`.
- Zero skip: list 1,218 MiB (934 + 284) in 52 runs, 609 canary mappings. One canary hit (run 49, file 0x230a00000,
  8 MiB) was taken back as designed. 10,524 MiB pinned, against 11,302–11,310 in R1/R2.
- The memory sampler wrote `exp0380f/play/mem-20261029-134855.txt`.
- The records are in `raw/runs/S1-*`.

**The desktop.**
- `~/Pulpit/BC5 emulator (test 0380 fix + 0379).desktop` (md5 4e4aa440, passes `desktop-file-validate`) runs
  `distrobox enter ubuntu -- ~/bc5-work/exp0380f/play-pkg-0380f.sh`.
- The old `BC5 emulator (test 0379+0380).desktop` was moved to `~/bc5-work/exp0379t/retired/`.
- The normal and lean shortcuts are untouched.
- **Undo:** delete the new shortcut, and move the old one back from `exp0379t/retired/` if wanted.

**What his play shows.** Every start's log in `exp0380f/play/`, plus the journal's `experiment 0380` and `zero skip`
lines, records the exposure. A class-B hang with this shortcut, recorded by the sampler and the timeout probe, refutes
the rebase. Hours without one support it. The zero skip is in the same play, so a hang must also be checked against the
zero list (F554's method).

## 10. The 14:04 hang with the rebase on, and the argument copy (F564–F567)

**Box.** Reads only, then a CPU-only compile check, 14:07–14:2x, on a fresh boot with the maintainer not playing.
Lock line `top exp 0380 | reads only: the 14:04 hang …`, cleared at the end; done line in BOX-QUEUE. The filtered
extracts are in `raw/hang-1404/`; the devcoredump `20261029-140441-devcd1.txt` and the journal
`play-20261029-1357/gc/direct.log` stay private.

**The play.** The maintainer's play on "BC5 emulator (test 0380 fix + 0379)" started at 13:57:49. Its log's first line:
`== exp 0380f mode: SKIP …zero-list-20261029-120000.txt; BC5_DIRECT_REBASE_DISPATCH=1; BC5_DIRECT_FORCE_START_000=1;
binary c442f6c7`. It hung at 14:04:41. The ring reset failed and the box rebooted.

**(a) The stuck dispatch and the rebase (F564).**
- Sampler 0377 (all samples alike):
  - `COMPUTE_PGM` 0x11d02a4a00;
  - `COMPUTE_DIM` [481 1073741962 480] = 0x1e1 / **0x4000008a** / 0x1e0;
  - threads [64 1 1], initiator 0x45;
  - `GRBM_STATUS` 0xa0407028, PFP 0xea1, ME 0x77b.
- The journal's timeout probe for dcb #278264 (8,251 dwords; acb #278265, 68 dwords; TIMEOUT after 2,037 ms)
  names that program at **title dword 1287, arguments at 0x11d05df300, 3158 × 1 × 1 at the timeout**. It is the first
  indirect dispatch of the dcb.
- In the devcoredump's IB #0 (8,880 dwords, fetched 1,920) the dispatch is dword **1379**. It is the first
  `DISPATCH_INDIRECT` after `SET_BASE` 1 = 0x11d05df300 (1249), `INDEX_BASE` 0x1210012000 (1253) and
  `INDEX_BUFFER_SIZE` 0xffffffff (1256). This is **sub-class B again**, the fifth event (F558).
- The rebase `SET_BASE` (1375, 0x11d05df300) stands right before it.
- The PFP history, newest first: `ACQUIRE_MEM`, `EVENT_WRITE`, `DISPATCH_INDIRECT`, **`SET_BASE` (0xc0021100)**,
  `COND_EXEC`, `PFP_SYNC_ME`, `WRITE_DATA`, `COND_EXEC`.
  - So the CP *executed* the re-emitted `SET_BASE` immediately before the stuck dispatch.
  - Of the dispatches the history allows (1379 and 1683 are followed by `EVENT_WRITE` 7), only 1379 is the probe's
    and the sampler's program.
- Exposure before the hang: 36,148 first-after-`INDEX_BASE` dispatches rebased (5.27 M checked) in about 6.5 minutes
  (the play log's last periodic line).

**(b) What the values say (F565).**
- **Not in the IB.** 481, 0x4000008a and 480 occur nowhere in the hung IB (`find0380.py`). Neither do 12:12's 0x30002
  and 0x2a0028; 0x10000 occurs only as the staircase's reference and in the title's register loads.
- **Not index-like.** As 32-bit words they are two neighbouring counts (480, 481) around a word with bit 30 set, not
  pairs of small 16-bit indices like 12:12's. The index-buffer reading of F555 has no support here.
- **Not a base problem.** The base was set again directly before the dispatch.
- **Memory was sane.** The check's `COND_WRITE`s read y and z from the same address and would have refused
  0x4000008a, and memory held 3158 × 1 × 1 at the timeout.
- **What remains of H0380b:** the CP's argument fetch for a `DISPATCH_INDIRECT` can return dwords other than those its
  own ME reads at the same address just before it. TODO(verify) the mechanism: a fetch path that is not coherent with
  the writes producing the arguments, a stale line from an earlier use of that memory, or another address. **The
  base-alias variant is refuted, and so is the rebase as a fix.**
- **The zero skip:** no sign it is involved. The arguments' memory was real (the CPU read 3158 there). The same slot
  hung at 18:15, 23:36 and 09:48 without the skip. The one canary hit (run 37, file 0x1cb400000, 24 MiB) came at
  journal line 56,638 of 773,549, as at 12:12.
  - It is still worth noting that the last two B events both ran SKIP mode and both hit run 37.

**(c) The next guard: the CP's own copy of the arguments (F566).**
- `BC5_DIRECT_ARGS_COPY=1`, default off. `indirect_check::apply(…, args_copy)`, `Stats::args_copied`,
  `kArgsCopyDwords` = 26.
- For every checked GFX-form `DISPATCH_INDIRECT`:
  1. three `COPY_DATA` (memory → memory, ME, `WR_CONFIRM`) copy the arguments (base + offset) to the check's flag area
     + 16/20/24;
  2. every `COND_WRITE` of the check (the limits, F548's zero guard, the 0341 staircase) polls the **copy**;
  3. after the check's confirm, `PFP_SYNC_ME` and `COND_EXEC` (count 3 + 4), a `SET_BASE` index 1 points at the copy
     and the dispatch's offset becomes 0;
  4. a `SET_BASE` with the title's base follows the dispatch, for the title's later indirect packets.
- So the check and the fetch read the same three dwords, written by the CP's ME and confirmed before the PFP is
  released.
- **Sources.** The packet is Mesa's `ac_emit_cp_copy_data` (src/amd/common/ac_cmdbuf_cp.c:238-265; `PKT3_COPY_DATA`
  0x40, `COPY_DATA_SRC_MEM` 1, `COPY_DATA_DST_MEM` 5, `COPY_DATA_WR_CONFIRM` 1 << 20, sid.h:99-116; ab2374a). RADV uses
  the same copy-then-dispatch for GFX7's compute-queue alignment bug (radv_cmd_buffer.c, `needs_align32_workaround`).
- It supersedes the rebase for the dispatch it covers. The flag area is 8 dwords per job (direct.cpp), and the copy
  uses dwords 4–6.
- **Limits** (TODO(verify)):
  - If the fetch path can return stale data even for these freshly ME-written dwords, the copy does not help. A hang
    with it on still decides between the mechanisms: the sampler's `COMPUTE_DIM` against the copy, whose source the
    probe reads.
  - The copy sits in each job's scratch, whose earlier contents at that address are other jobs' IB dwords.
- **Tests.** Catch2 "the dispatch runs from the CP's copy of its arguments (experiment 0380)", five sections:
  - the exact packets;
  - every poll on the copy, with the staircase, the zero guard, FORCE_START and rebase, FORCE_START landing on the
    dispatch;
  - off by default, with unbased, MEC and draws untouched;
  - inside the IB's own `COND_EXEC`;
  - two dispatches with their own bases and offsets.

  Laptop 96/96 (34,396 assertions). Box clang 21.1.8 `-Werror`, 0 warnings, 96/96 (34,395), archive bf8b8d4a
  (`raw/box-A0d/`).
- **Not built: converting to `DISPATCH_DIRECT` through the CP.**
  - The CP cannot patch dwords of an IB it has already prefetched: the fetcher stood 1,920–1,952 dwords ahead in every
    B event (F528, F558).
  - The other route, building a direct dispatch in an IB2 with `COPY_DATA` and calling it with `INDIRECT_BUFFER`, reads
    the dims through the CP's fetch again. That is the path in question.
  - No public source shows a register path that sets the group counts of a `DISPATCH_DIRECT` from memory.
  - So the copy is the smaller and better-sourced test.

**Next (F567).**
- A private binary with `BC5_DIRECT_ARGS_COPY=1`: the same relink as F563, CPU only.
- A bench run, then a play test **without the zero skip**, to separate the two: the last two B events both had SKIP
  on. This needs the maintainer's yes (GPU).
- A class-B hang with the copy on is decisive in either direction:
  - `COMPUTE_DIM` equal to the copy (memory) → the arguments themselves were bad and the check missed them, which the
    check reading the copy rules out;
  - `COMPUTE_DIM` different from the copy → the CP's argument fetch is incoherent even for CP-written dwords.

## 11. The argument copy on the bench: it hangs at once, and what that shows (F568–F570)

**GO and box.** The maintainer's "Tak, testujcie" (F567's plan), relayed by the top session. 14:2x–14:5x: my lock and
claim lines, the kernel stream to the laptop, the route's save copy. The live saves were re-read: **3c1f2001a3863535**
(newest file 14:03, his play), the same after the reboot. Done line in BOX-QUEUE.

**The binary.** `~/bc5-work/exp0380c/kyty_emulator` md5 **09345cbb**: the shared objects (**no** zero skip) relinked
with archive bf8b8d4a (c0d00ef, `BC5_DIRECT_ARGS_COPY`), pinned as `exp0380c/libbc5_backend-bf8b8d4a.a`
(`link0380r.py`). The runner `raw/s6n0380c.sh` (box md5 f5cecd86) is made by `raw/mk-s6n0380c.pl` from `s6n0380.sh`.
The switches were `BC5_DIRECT_ARGS_COPY=1 BC5_DIRECT_FORCE_START_000=1`.

**C1 hung after 7 s (F568).**
- The run started at 14:27:40. At 14:27:47, during the title's start-up (fence seq 1255):
  `ring gfx_0.0.0 timeout`, `Ring gfx_0.0.0 reset failed`, then `bc5-gpu-watch` crashed the kernel for a reboot
  (`raw/runs/C1-kernel-stream.txt`). The box was up again at 14:29; the saves were unchanged.
- **The registers.** Sampler 0377: `GRBM_STATUS` 0xa0407028, PFP 0xea1, ME 0x779 (F403's state);
  `COMPUTE_PGM` 0x11d0323c00, `COMPUTE_DIM` **[3204318058 2165211406 100939574]** (0xbefe036a / 0x810e810e /
  0x06043736), threads [8 4 1], initiator 0x8045 (`raw/hang-1427/sampler-summary.txt`).
- **The probe** of dcb #81 (8,995 dwords; acb #79, 1,192 dwords; both TIMEOUT): title dword 533, program
  0x11d0323c00, arguments 0x11d0571b00, **28,800 × 1 × 1** in memory at the timeout.
- **The devcoredump's IB #0** (1,808 dwords, fetched 1,184). The PFP history, newest first: `ACQUIRE_MEM`,
  `EVENT_WRITE`, `SET_BASE` (the restore), `DISPATCH_INDIRECT`, `SET_BASE` (to the copy), `COND_EXEC`, …
  - That puts the stuck dispatch among the copied ones at 657 / 838 / 1019. Each fetched from **0x100f00001c50**: the
    copy slot in this job's scratch, just after the 1,808-dword IB.
  - 657 is the probe's dispatch, the first copied one.
  - The launched values occur nowhere in the IB.
- **What it means.** The ME had copied the arguments into that slot with `WR_CONFIRM`, and the check's `COND_WRITE`s
  then read the slot and passed. The CP's argument fetch from the same address returned other data.
  - In the title's own case (F553, F564), the arguments are written by the GPU shortly before the frame's first
    dispatch. The fetch went wrong about once an hour.
  - Here the slot is rewritten by the ME in every job, at a scratch address whose earlier contents were other data.
    The fetch went wrong at once.

**The mechanism this points to (F569).** The CP's `DISPATCH_INDIRECT` argument fetch does not see data that is
written but not yet written back from GL2. The ME's writes (`COPY_DATA` with `WR_CONFIRM`, which confirms at L2) and
the check's polls go through GL2, and the fetch sees memory behind it.
- That fits every observation so far:
  - the check always passes;
  - memory reads sane at the timeout, after the line has been written back;
  - the bad values are old data from that address;
  - the copy breaks at once, since its slot is rewritten every job;
  - the title breaks rarely, since its arguments are usually written back long before the fetch;
  - the stuck dispatch is the frame's first, whose arguments were written just before.
- Mesa assumes the opposite on GFX9+: for `VK_ACCESS_INDIRECT_COMMAND_READ` RADV invalidates only SMEM, not L2
  (radv_cmd_buffer.c:8087-8098, ab2374a). So this would be specific to this chip or to how the direct path maps the
  memory (userptr/GTT pages, the MTYPE of the mapping): TODO(verify).
- Alternative not excluded: a CP-side read cache holding the line from an earlier fetch.

**The candidate fix (F570): `BC5_DIRECT_ARGS_WB=first|all`, default off.**
- What it does: an `ACQUIRE_MEM` with `GCR_CNTL` `GL2_WB` (bit 15) over the full range, `COHER_CNTL` 0 (8 dwords).
  - This is the kernel's own gfx10 memory-sync packet with only the write-back bit (Linux v7.2 `nvd.h:447-501`,
    `gfx_v10_0_emit_mem_sync` in gfx_v10_0.c:9473-9494).
  - It sits at the start of the check (after the copy when the copy is on), so the check's `PFP_SYNC_ME` keeps the PFP
    behind it.
  - `first` covers only the first `DISPATCH_INDIRECT` after an `INDEX_BASE` (sub-class B, ~145 a second); `all` covers
    every checked dispatch (~24,000 a second, a full-L2 write-back each).
  - `Stats::args_written_back`, `kArgsWbDwords` = 8.
- Tests: Catch2 "a GL2 write-back before the check (experiment 0380)" — first, all, with the copy, off/MEC. Laptop
  97/97 (34,411 assertions). Box clang 21.1.8 `-Werror`, 0 warnings, 97/97 (34,410), archive eff535ac
  (`raw/box-A0e/`).
- TODO(verify): that `ACQUIRE_MEM` waits for the write-back before the next packet. Mesa's gfx10 comment says it
  "doesn't wait for idle", which is about waiting for the shaders.

**Not done, by the plan.** C1 failed, so no "test 0380 copy" shortcut was made, and "BC5 emulator (test 0380 fix +
0379)" was left on the desktop at first. It carries the refuted rebase and the zero skip, so on the top session's
instruction it was moved to `~/bc5-work/exp0380f/retired/` afterwards (a file move only). Only the normal and lean
shortcuts remain. **The copy switch must not be used on its own:** it hangs within seconds.

**Next (needs the maintainer's yes: GPU).** One discriminating bench run: copy + `BC5_DIRECT_ARGS_WB=all`.
- Without the write-back the copy hung within 7 s. If the same run passes 600 s with it, the GL2 mechanism is shown in
  one run.
- Then `BC5_DIRECT_ARGS_WB=first` alone, without the copy, for the bench and the maintainer's play. It has the smallest
  cost and covers the sub-class B slot.

## 12. W1, copy + GL2 write-back: the same hang, the same garbage, and what that changes (F571–F573)

**GO and box.** The maintainer's "Tak, testujcie" for the `ARGS_WB` runs, relayed by the top session. 14:4x–14:5x: my
lock and claim lines and the kernel stream. Live saves 3c1f2001a3863535 before, and after the reboot. Done line in
BOX-QUEUE. W2/W3 were **not run** (the stop rule).

**The binary.** `~/bc5-work/exp0380w/kyty_emulator` md5 **c3c8660b**: shared objects, no zero skip, archive eff535ac
(0ce8c97), pinned as `exp0380w/libbc5_backend-eff535ac.a`. The runner `raw/s6n0380w.sh` (box md5 2c27a702) is made by
`raw/mk-s6n0380w.pl` from `s6n0380c.sh`. The switches were
`BC5_DIRECT_ARGS_COPY=1 BC5_DIRECT_ARGS_WB=all BC5_DIRECT_FORCE_START_000=1`.

**W1 hung 7 s after its start (14:48:58 → 14:49:05, fence seq 1402),** exactly as C1 did. The ring reset failed and
`bc5-gpu-watch` rebooted the box (`raw/runs/W1-kernel-stream.txt`).
- Sampler: `GRBM_STATUS` 0xa0407028, PFP 0xea0, ME 0x77b; `COMPUTE_PGM` 0x11d0323c00, `COMPUTE_DIM`
  **[3204318058 2165211406 100939574]**, initiator 0x8045 (`raw/hang-1449/`).
- Probe: dcb #80, title dword 533, arguments 0x11d0571b00 = 28,800 × 1 × 1. That is the same program, the same
  dispatch and **the same three launched values as C1**.
- The IB has what the switches should insert before that dispatch:
  - three `COPY_DATA` (547, 553, 559);
  - the `ACQUIRE_MEM` write-back (565);
  - the check polling the copy at 0x100e00001cf0/f4/f8 (583–640, all passed);
  - `SET_BASE` 1 = 0x100e00001cf0 (661), the dispatch with offset 0 (665), the restore (668).

**What changes (F572).**
- The copy slot was at 0x100f00001c50 in C1 and 0x100e00001cf0 in W1: two scratch slots, two runs, two boots. Both
  launched the same three dwords, none of which occur in either IB.
- Leftover scratch contents cannot be identical across two different addresses and boots. And the write-back did not
  change the outcome at all.
- So the two copy runs did **not** test coherence: the fetch through `SET_BASE` did not read the slot.
- The slot lies at 16 TiB + (slot << 32) (direct.cpp `kScratchVa` = 0x1000'0000'0000, above 2^44). The title's
  arguments lie below 2^37.
- The ME can address the slot: its `COPY_DATA` and `COND_WRITE`s worked there, and the check passed. A base above
  what the indirect-argument fetch can address (TODO(verify): its width; RPCSX keeps 16 bits of the high dword,
  `setBase`, e8ae148, which is a model, not hardware) would make every such fetch read one fixed location. The
  identical garbage fits that.
- **F568's and F569's reading is withdrawn:** the GL2 mechanism has no support left from the copy runs. F570's
  write-back is untested against the title's own hang.
- The title's sub-class B values differ from event to event (12:12, 14:04), so they are not this fixed read.

**Next (F573).**
- **The copy must sit below the fetch's address limit.** That means a small private buffer at a low GPU VA, e.g. from
  libdrm's general range (`amdgpu_va_range_alloc`, as the legacy-scratch option does), listed in every submission.
  That is host plumbing in `direct.cpp`, not built yet.
- With such a slot, the copy test regains its meaning:
  - a copy-only run that passes shows the copy is sound;
  - a later class-B hang with it on decides between bad arguments and an incoherent fetch.
- `BC5_DIRECT_ARGS_WB=first` alone (no copy) is still a valid, cheap test of the GL2 idea against the title's own
  hang. W2 is ready to run (same binary c3c8660b) on the maintainer's yes.
- The "test 0380 wb" shortcut was not prepared: its precondition (W2/W3 passing) was not reached.

## 13. W2/W3: the GL2 write-back alone on the bench, the low-VA copy slot, the "test 0380 wb" shortcut (F574–F576)

**GO and box.** The maintainer's "Tak, testujcie" (the `ARGS_WB` runs), relayed by the top session. 14:53–15:15, my lock
and claim lines; each run's runner wrote and cleared its own lock. Kernel stream to the laptop. Live saves
**3c1f2001a3863535** before and after both runs. Then a CPU-only compile check and the staging of the launcher. Done
line in BOX-QUEUE.

**W2 and W3** (binary c3c8660b, `BC5_DIRECT_ARGS_WB=first BC5_DIRECT_FORCE_START_000=1`, no copy, no rebase, no zero
skip, S6N, RT on, 600 s each; `raw/runs/W2-*`, `raw/runs/W3-*`):

| Run | Result | Flips/s | Running scene (150–590 s) | Kernel lines | TIMEOUT | Devcoredumps | Sampler events | GL2 write-backs |
|---|---|---|---|---|---|---|---|---|
| W2 | pass | 37.9 | 40.8 | 0 | 0 | 0 | 0 | 89,514 |
| W3 | pass | 36.1 | 38.4 | 0 | 0 | 0 | 0 | 85,136 |

- The write-back counts come from the last periodic line of each run; the emulator is killed at 600 s.
- The cost of a full-L2 write-back before the frame's opening dispatch is within noise: B1 37.8, R1/R2 37.5/36.5.

**Reading (F575).**
- The write-back is safe on the bench.
- As with the rebase (F562), two clean bench runs say nothing about the hang: sub-class B has no measured bench rate
  and came about once per hour of the maintainer's play.
- The title's argument addresses (0x11d05df300, 0x11d0571d00, 0x11d0571b00 ≈ 2^36) lie far below 2^44, so the high-VA
  read of F572 does not cover the title's hangs. It only explains the copy runs.

**The low-VA copy slot (F574).**
- `BC5_DIRECT_ARGS_COPY`'s slot is now a 4 KiB GTT BO, zeroed and mapped at a VA from libdrm's 32-bit range
  (`amdgpu_va_range_alloc(…, AMDGPU_VA_RANGE_32_BIT)`). It is allocated at `Device::open` only when the switch is on,
  listed in every submission (as the GDS shadow is), and unmapped and freed at close. If the allocation fails, the
  switch is turned off with a line.
- `indirect_check::apply(…, copy_va)` puts the `COPY_DATA` destination, the polls and the dispatch's `SET_BASE` on that
  address; with 0 it uses the flag area as before.
- Catch2 "the copy at a low GPU VA (experiment 0380, F574)". Laptop 98/98 (34,435 assertions). Box clang 21.1.8
  `-Werror`, 0 warnings, 98/98 (34,434), archive 02acc42b at 22e1bda (`raw/box-A0f/`). Not relinked, not run.
- **The fetch's address width** is TODO(verify). No public source was found that states it:
  - Mesa RADV emits the full 64-bit VA into `SET_BASE` (radv_cmd_buffer.c:12305-12313);
  - RPCSX keeps 16 bits of the high dword;
  - the kernel's IB fetch reaches 2^48 (direct.cpp's own note on `kScratchVa`, exp 0016).

  The evidence that it is narrower than the IB fetch is F572 alone.

**The shortcut, PREPARED, NOT INSTALLED (F576).**
- Launcher: `~/bc5-work/exp0380wb/play-pkg-0380wb.sh`, md5 **1b8a6a17**, made from `play-pkg.sh` 55531ab6 by
  `raw/mkplay0380wb.pl`.
  - It uses the binary `~/bc5-work/exp0380w/kyty_emulator` (**c3c8660b**) and sets
    `BC5_DIRECT_ARGS_WB=first BC5_DIRECT_FORCE_START_000=1`, with every other 0379/0380 switch unset.
  - It writes per-start logs and a once-a-minute memory sample to `exp0380wb/play/`. The log's first line names both
    switches and the binary md5.
- Shortcut file: `~/bc5-work/exp0380wb/BC5 emulator (test 0380 wb).desktop.staged`, md5 528aa794. It passes
  `desktop-file-validate` (checked on a `.desktop` copy).
- To install on the maintainer's yes:
  `cp ~/bc5-work/exp0380wb/"BC5 emulator (test 0380 wb).desktop.staged" ~/Pulpit/"BC5 emulator (test 0380 wb).desktop"`.
- Only the normal and lean shortcuts are on the desktop now.
- **What his play would show:** one sub-class B hang with it on refutes the write-back as a fix and, with it, the GL2
  idea for the title's hang. Hours without one support it.

## 14. Our libraries and filter against the title's use: an audit, and three read-only checks (F577–F579)

**The question (the maintainer).** Does the title use a library we implemented, or copied from KytyPlus or AnyPS5,
differently from how we wrote it? Is our logic wrong?

**Audit (laptop, read-only, two parallel code reviews).**
- The title loads its own `libSceAgc`/`libSceAgcDriver` (LLE, patch 0001). So the PM4 at the hang is the title's, not
  code we copied.
- Our logic sits in three places: the PM4 filter (`backend/src/policy.cpp`, `backend/policy/pm4-policy.tsv`,
  `backend/src/direct.cpp`), the `/dev/gc` and kernel-memory calls in the patch, and the submission order.
- **Found and not suspect:**
  - ENGINE_SEL (PFP/ME) is never changed;
  - `ACQUIRE_MEM`'s `GCR_CNTL` passes unchanged (`gcr_clear` is off);
  - the CS_DONE → BOTTOM_OF_PIPE rewrite of `RELEASE_MEM` keeps the cache bits and waits longer, not shorter;
  - the `SET_BASE`s of the class-B dispatches carry clean addresses (0x11d05df300, 0x11d0571b00, 0x12…), so the alias
    windows for tagged addresses (bits 40–47) do not apply to them.
- **Found and suspect**, each with a code location; the three cheapest were checked below:
  - cross-buffer `WAIT_REG_MEM`s dropped when a CPU read at submission says they are met (`policy.cpp:490-506`,
    `self_waits_only`; patch ~31037/31280/31320);
  - 10 dropped dwords right before the stuck dispatch;
  - the memory type a title asks for never reaching the GPU mapping. `KernelMtypeprotect` is `mprotect`, as in
    upstream KytyPlus (`refs/Coder787-source_KytyPlus/src/kernel/memory.cpp:4025-4029`). `memory_type` is stored but
    not passed to the mapper (patch 21759-21781), and every GPU map gets the default MTYPE (`direct.cpp:763-767,
    879-880, 936-937`);
  - the DMA snapshot (≥ 4 KiB dcb `DMA_DATA` sources copied by the CPU at submission);
  - nested IBs getting no DMA wait and no check;
  - alias windows rebuilt at most once a second;
  - `submit+EOP` completion reported at submission.

**Box.** Reads only, 15:39–15:5x, with a reads-only lock line, after the top session's note that the box was free and
the maintainer not playing. The lock was cleared and the done line is in BOX-QUEUE. Scripts: `raw/binspan0380.py`
(title IB dumps, structure only), run from stdin; the outputs are in `raw/suspects/`.

**1. The 10 dropped dwords (F577).**
- In the title's own IB of all three B events with a dump (09:48 dcb #183691, 12:12 #94500, 14:04 #278264), dwords
  1277–1286 are the same two packets: `0xc0039f00 0 0 0x80000000 0` and `0xc0036300 0 0 0x80000000 0`. They sit
  between the title's `ACQUIRE_MEM` (1269, `GCR_CNTL` 0x280) and the stuck `DISPATCH_INDIRECT` (1287).
  - The first is `LOAD_CONTEXT_REG_INDEX` (0x9f), the second `LOAD_SH_REG_INDEX` (0x63) (Mesa sid.h:211, 228).
  - Both have INDEX 0 (a direct address), address 0, DATA_FORMAT 1 (offset-and-data pairs) and **0 dwords** (field
    layout per RPCSX `loadContextRegIndex` / `loadShRegIndex`, rpcsx/gpu/Pipe.cpp:1958-2060, e8ae148).
  - The filter drops them as unmapped (address 0; `policy.cpp:92-95`).
- By that reading they load nothing, so dropping them does not change what the CP does. TODO(verify): whether a
  count-0 load has a side effect on gfx10, such as a PFP-side sync. No public source says so.

**2. Dropped waits (F578).**
- The timeout probes of the same three jobs list 10, 15 and 9 waits. In none of the IBs is there a wait before the
  stuck dispatch at 1287: the first comes at 1751, 1709 and 1516.
- The dropped ones (four per IB) are `WAIT_REG_MEM64` on the PFP with reference 0, already met at the timeout, at
  5835+, 6815+ and 2369+, all after the stuck dispatch (`raw/suspects/probe-waits.txt`).
- So inside its IB the stuck dispatch is ordered after its argument producer only by what earlier jobs did, and no
  wait of ours was removed in between. The cross-job question remains (an earlier job's dropped wait, or the
  producer's own visibility), and the IB dumps cannot answer it.

**3. The memory type of the argument range (F579).**
- Not recoverable from what is captured. The host logs `memory_type` only in its `LOGF` lines, which normal play does
  not write, and no record maps 0x11d05xxxxx to a named heap.
- The code fact stands, sourced above: whatever the type, the GPU mapping is the default MTYPE.
- Deciding it needs a run with the host's memory `LOGF` lines on, or a journal line naming the heap and type of each
  view (GPU work, the maintainer's yes). If the argument heap is a write-combined / "Garlic" type (shadPS4 lists
  WB_ONION 0, WC_GARLIC 3, WB_GARLIC 10, `src/core/libraries/kernel/memory.h:24-28`), the next test is that range
  mapped `MTYPE_UC`.

**Ranking after the checks.**
- Within the stuck IB, the 10 dwords and the dropped waits are cleared.
- The memory-type mismatch is the strongest remaining lead. It is a host fact, inherited from KytyPlus, that would make
  GPU-written arguments travel through caches the console would not use. It is untested.
- Then the cross-job ordering: the producer of 0x11d05df300 is a GDS → memory `DMA_DATA` without `CP_SYNC`, in the
  previous job.

## 15. Suspect 3: a logging-only build of the host's memory calls (F580)

**What it logs.** `raw/memlog0380.py` makes a private copy of the KytyPlus tree's `src/kernel/memory.cpp` (md5 11b1df22,
patch 0001 applied) with six stderr lines, prefixed `bc5-0380 mem:`, each with the caller's return address:
- `alloc`: physical start, length, `memory_type` of `sceKernelAllocateDirectMemory`;
- `map`: VA, length, physical offset, prot, flags and the block's type;
- `map2`: `MapDirectMemory2`'s type;
- `name`: `MapNamedDirectMemory`'s name;
- `rangename`: `SetVirtualRangeName`;
- `mtypeprotect`: VA, length, type, prot.

Nothing else changes; the diff is `raw/patch0380m-memory.diff`, 16 added lines. Flexible-memory maps are not logged.

**The build (CPU only, box, 15:44–15:5x, under my lock).** `raw/build0380m.py` compiles that one unit with the shared
build's own compile command (`ninja -t compdb -x`, `-iquote` the tree's `src/kernel` for its `.inc`) and runs the shared
link command with the object swapped in, against the shared archive.
- The same method on the tree's unchanged `memory.cpp` reproduces the shared binary **58c4a627** byte for byte.
- The logging binary is `~/bc5-work/exp0380m/kyty_emulator`, md5 **541e484e**. It carries the 6 log strings and has the
  same GPU path as the shared build.
- The runner is `raw/s6n0380m.sh` (box md5 9746592a, made by `raw/mk-s6n0380m.py` from `s6n0380w.sh`), with no
  switches.

**The run M1 was not started.** This session's permission check refused the GPU run itself. I stopped the kernel
stream I had started for it and its leftover `journalctl`, cleared my lock line, and wrote the done line. The saves
were 3c1f2001a3863535 at the last read.

**To resolve the argument ranges offline once M1 has run:**
- the `alloc` lines give physical ranges and types, and the `map` lines give VA → physical;
- so 0x11d05df300 / 0x11d0571d00 / 0x11d0571b00 → map → alloc → type, and the `name` / `rangename` lines give the heap.

**M1 ran later (the user allowed it, 2026-10-29 15:56–16:06).**
- **The run.** S6N, RT on, 600 s, binary 541e484e, no switches: pass, 37.1 flips/s, 0 kernel lines, 0 TIMEOUT, 0
  devcoredumps; saves 3c1f2001a3863535 unchanged. The runner wrote and cleared its lock, and the kernel stream ran.
  70,965 `bc5-0380 mem:` lines. `raw/resolve0380m.py` resolves them; output in `raw/runs/M1-memory-types.txt`.
- **The argument ranges (F581).** Every indirect-argument address on record (0x11d05df300, 0x11d0571d00,
  0x11d0571b00, 0x11d0571f00) and the programs (0x11d02a1600) lie in one heap: **`RenderGpuWcSmall`**.
  - It is mapped at VA 0x11d0000000 + 0x6e00000 (110 MiB), phys 0x203200000, prot 0x32, memory **type 12**.
  - The `LOAD_SH_REG_INDEX` source 0x11e072fa94 and the index base 0x11e9db6280 lie in `RenderGpuRwLarge` (prot 0xf2,
    type 12); the index base 0x1210012000 lies in `CommitIABufferAllocator` (prot 0xf2, type 12).
- **Types across the run.**
  - 1,668 of 1,669 direct allocations are type 12 (9,810 MiB); one is type 0 (3,034 MiB).
  - All 15,170 `MapDirectMemory2` calls pass type 12, and there are no `Mtypeprotect` calls.
  - So the title asks for **one** type for practically all of its GPU memory. The "Wc"/"Rw" heaps differ in protection
    (0x32 against 0xf2), not in type.
- **Type 12** is not in the PS4 numbering: WB_ONION 0, WC_GARLIC 3, WB_GARLIC 10 (shadPS4 memory.h:24-28, 60c42b9;
  GPCS4 sce_kernel_memory.h:68-70). The one public PS5 trace in `refs/` is KytyPS5's test expecting the AGC driver's
  own `SceAgcDriver` memory to be type 12 with prot 0x33 (`tests/ShaderRecompilerComputeTests.cpp:47883`, 4644c52).
  What caching type 12 asks for is TODO(verify). The meaning of prot bits 0x40/0x80 (0xf2 against 0x32) is
  TODO(verify) too.
- **What this does to suspect 3.**
  - The title does not request a special (uncached) type for its argument heap. A per-range `MTYPE_UC` fix for "the
    argument heap" has no basis in the data, and it is not designed here.
  - What remains open is broader: whether type 12 as a whole means something our default GPU mapping does not give
    (e.g. no GL2 caching). That would affect all the title's GPU memory equally, not only the stuck dispatch.
  - The cheapest test of that is not a per-range switch. It needs a source for type 12's caching first.

## 16. The maintainer's play on "test 0380 wb" (16:24–17:02): one recovered start-up fault, then 36 minutes without F403 (F582–F584)

**The setup.** The top session installed the staged shortcut (F576): binary c3c8660b, `BC5_DIRECT_ARGS_WB=first`,
FORCE_START, no copy, no rebase, no zero skip, RT on. The maintainer called the play "bardzo niestabilna" (very
unstable). The records are on the box (`~/bc5-work/exp0380wb/play/`, the journals in
`~/bc5-data/captures/play-20261029-1624`/`-1625`). The filtered extracts are in `raw/wbplay/`.

**Box.** Reads only, 17:0x–17:1x, with a reads-only lock line, cleared at the end. Done line in BOX-QUEUE.

**Start 1 (16:24:42–16:25:50): a recovered start-up fault, not F403 (F582).**
- **The kernel lines.**
  - At 16:25:39, `[gfxhub] page fault` (vmid 6) from client TCP, `PERMISSION_FAULTS` 0x3, `RW` 0 (a read), `MORE_FAULTS`
    1, at pages 0x8608c654000 … 0x8608c65c000.
  - Then two `ring gfx_0.0.0 timeout`s (16:25:41, 16:25:43), each with `Ring gfx_0.0.0 reset succeeded`; `bc5-gpu-watch`
    armed and disarmed.
  - The emulator ended at 66 s. *Correction (the maintainer, relayed by the top session):* it did not exit by itself.
    After the fault and the two successful resets the menu showed no picture, and he closed it by hand. So the resets
    recovered the ring, but rendering did not come back: the title's GPU state was lost in the reset (TODO(verify)
    what a gfx ring reset on this kernel restores, e.g. shadowed registers, the title's GDS/rings, the host's
    labels).
- **The sampler.**
  - 16:25:41: `GRBM_STATUS` 0xa04030ac, PFP 0xea1 / ME 0xe15, program 0x909977100, dim [697 1 1].
  - 16:25:43: `GRBM_STATUS` 0xa0003028, ME 0x5c0, dim [213 1 1].
  - Both: initiator 0x65 = 0x61 (`USE_THREAD_DIMENSIONS`, `ORDER_MODE`) + FORCE_START. Neither is F403's state.
- **The stuck job.** dcb #32979 (14,911 dwords) with acb #32980 (4 dwords), both TIMEOUT.
  - Its title IB (`raw/wbplay/dcb-32979-head.txt`) opens with `ACQUIRE_MEM` and `LOAD_SH_REG_INDEX` (from
    0x909842dc0, 10 registers), then a run of GFX-form `DISPATCH_INDIRECT`s of program 0x909977100 (offsets 0x80, 0xa0,
    0x2280, …).
  - The IB has no `SET_BASE` and no `INDEX_BASE`: these are **unbased** dispatches on a carried base, the class of
    F416, F417 and F422 that exp 0346's resolver handles. The probe printed "not mapped" for base 0 + offset.
- **The fault address** is in no direct-memory mapping of the title in M1's map log, not as 0x8608c65c000, not as its
  40-bit core 0x608c65c000 (F92's tagged-address reading), not as 0x8c65c000. It is a read by a shader (TCP) of the
  0x0909 ray-tracing/BVH program window (0x909977100 is not on F343's ten-program list) through an address the title
  never maps.
- **Not caused by the write-back.** `ARGS_WB=first` only inserts its `ACQUIRE_MEM` into the check of a based dispatch
  after an `INDEX_BASE` in the same IB. This IB has neither, so it got none: the start's whole count was 908. A GL2
  write-back changes no data and no address either. The class is the title's start-up BVH work faulting on an unmapped
  address, as in F92 and F417.
  - TODO(verify): whether the shared build shows the same fault at this start-up point. No run of today's build on the
    same save path is on record.

**Start 2 (16:25:52–17:02:29, 36.6 min): no F403 and no kernel line (F583).**
- **The run.** 67,616 flips in 2,192 s (30.8 flips/s, from the journal), 0 TIMEOUT lines, no sampler event, no
  devcoredump.
- **Exposure.** 282,894 first-after-`INDEX_BASE` dispatches got the GL2 write-back (~129 a second, ~4.2 a frame).
- **Memory pressure.** MemAvailable fell to 205–279 MiB, swap 1.3–1.6 GiB, PSI memory "full" 16–24 % at the end
  (`raw/wbplay/mem-start2.txt`). That is exp 0379's subject.

**How significant (F584).**
- **Today's B events in the maintainer's plays.** 12:12 came about 2.4 min into its start (12:09:44); 14:04 about 6.9
  min (13:57:49). The top session puts the shared-build rate at about one per 7–10 min of his play.
- **If the write-back changed nothing:** with a Poisson rate of 1/7 to 1/10 per minute, the chance of 0 events in 36.6
  min is e^−5.2 ≈ 0.005 to e^−3.7 ≈ 0.026.
- **Also, by exposure.** The 14:04 hang came after 36,148 first-after-`INDEX_BASE` dispatches (F564). Start 2 ran 7.8
  times that without one.
- **So the result is significant at roughly the 97–99 % level, if the rate holds,** but it is one session.
  - The rate rests on a few events (09:48, 12:12, 14:04 and the shared-build plays the top session counted).
  - The play may not have covered the same scenes.
  - The B class may also depend on load: start 2 ran under heavy memory pressure.
- **Next.** A second long play on the same shortcut decides it far better than more bench runs. Two clean 36-minute
  plays would put the "unchanged rate" chance below ~10^−3.
- **The graphics glitches in start 2 (the maintainer: glitches, the sound fine) (F585).** *Corrected by F587: the same
  white dots appeared on the shared build, so neither FORCE_START nor `ARGS_WB` causes them.*
  - `ARGS_WB=first` itself is an unlikely cause. It adds an `ACQUIRE_MEM` that writes dirty GL2 lines back to memory
    (`GCR_CNTL` `GL2_WB` only, no invalidate). The GPU's own clients read through GL2 either way, so no value a shader
    or the CP sees changes, and only timing can differ.
  - Exception: if the write-back is exactly what makes the CP's argument fetch see the right arguments (F569), then
    with it some dispatches run with their real grid, where on the shared build they could have launched a stale one.
    That changes the picture towards the console's, not away from it.
  - The other switch in that shortcut, `BC5_DIRECT_FORCE_START_000=1` (F551), *can* change results. It forces every
    indirect dispatch to start at group 0. If the title ever meant an indirect dispatch to start at a non-zero
    `COMPUTE_START`, those groups would be wrong. START read 0 in all 40 healthy samples (exp 0378), so this is
    possible but unshown. It was also on in the 0379+0380 shortcut's plays.
  - The shared build had glitches of its own in RT-on play: the maintainer's "przekłamania grafiki" of 10-28, during
    F505's page-cache thrash. Start 2 ran under similar memory pressure (F583), with assets re-read from the package
    under PSI memory-full 16–24 %. That fits streaming or late-data glitches without either switch.
  - To tell them apart: his description of the glitches (what, where, how long), then if needed one long play with
    `ARGS_WB=first` and FORCE_START **off**.
- **Reclassification with the TCP-fault history (F586, offline).**
  - *Start 1's fault* belongs to the shader-side class of F443 and Q22: a shader using a garbage pointer, then a ring
    timeout whose reset succeeds.
    - F443 (exp 0356 R2): a TCP write fault plus four faults at junk addresses, the GFX ring timed out, the reset
      succeeded. It is "the shader-side class of F399/F403 (garbage pointers in a dispatch's data), not the AMM fault".
    - Q22: stray TCP accesses at heap-side addresses that hold no guest memory, followed by ring timeouts (F257, F275,
      F304, F331, F338/F339). These are the tcp-write session's findings.
    - Today's differs only in being a read (RW 0) at an address in no mapping (0x8608c65xxxx). The program is from the
      0x0909 RT/BVH window, and the job is an unbased dispatch chain.
    - The lost picture after the resets fits the reset dropping the title's GPU state.
  - *The "białe kropki" (white specks) of start 2.* HANDOFF has no "white speck" finding. The nearest known RT state:
    - the RT reflection traversal turning surfaces white when it reads trees that are not (yet) compacted or built
      (F362, F366: the lab washed out white by 0x11d049aa00 / 0x11d04a6000);
    - F370: running the BVH compaction 0x909974400 removes it, which is how the shared builds run RT on (F343).

    Isolated white dots during play fit the same family: reflection rays hitting incomplete or stale BVH data, or
    unwritten samples. They are also typical of NaNs in a denoise pass (TODO(verify) for this title).
  - *Could `ARGS_WB=first` matter?* Only through its intended effect: if it makes the CP fetch the arguments the title
    wrote (F569), BVH-related dispatches would launch the grids the console launches. That should reduce artefacts, not
    add them.
  - The other candidates stand as in F585: FORCE_START, and the RT-on glitches already seen on the shared build under
    memory pressure (10-28).
  - A capture would decide it: a screenshot or short recording of the dots, and whether they appear with the shared
    build on the same save.
- If it holds, F569's "the fetch misses GL2-resident writes" becomes the working explanation for sub-class B. It was
  withdrawn because the copy runs did not test it; the write-back result now supports it directly.

## 17. White dots on the shared build too; the 18:08 hang is a graphics-pipe stall, not F403 (F587–F589)

**New data (the maintainer, relayed by the top session).** He played the shared normal build (58c4a627, the regular "BC5
emulator" shortcut, RT on, the same save). The white dots appeared there too. He had the impression the game was more
stable at first (subjective). He paused and unpaused, and a few moments later it hung, at 18:08:13. The ring reset failed
and `bc5-gpu-watch` rebooted the box.

**Box.** Reads only, after the reboot, with a reads-only lock line, cleared at the end. Done line in BOX-QUEUE. Extracts
in `raw/hang-1808/`.

**The dots (F587).** They are not caused by FORCE_START or `ARGS_WB` (F585 and F586 are corrected): they are the title's
RT-on rendering on this host in general. F586's nearest known state stays: the reflection traversal on incomplete or
uncompacted trees (F362, F366, F370), or denoise NaNs (TODO(verify)).

**The 18:08 hang (F588).**
- **Where the CP is.**
  - The IB of the stuck job is dcb #127530 (14,945 title dwords; 16,152 with the host's packets). It is **fully
    fetched**: `CP_IB1_BUFSZ` 0, `CMD_BUFSZ` 0x3f18.
  - Its tail: the title's `RELEASE_MEM`s and an `ACQUIRE_MEM`, the host's zero-byte `DMA_DATA` CP_SYNC (16139), NOPs.
  - PFP history (newest first): `ACQUIRE_MEM`, `EVENT_WRITE`, `ACQUIRE_MEM`, `EVENT_WRITE`, `RELEASE_MEM`, then three
    one-dword ring NOPs (0xffff1000). So the PFP is past the IB, on the ring's own packets.
  - ME history: `EVENT_WRITE`, `ACQUIRE_MEM`, 0xc0000c00, `EVENT_WRITE`, `RELEASE_MEM` ×2, `LOAD_CONTEXT_REG_INDEX`,
    `RELEASE_MEM`. The ME stands at an `EVENT_WRITE` after the job's last packets.
  - It waits for a partial flush there (`CP_STALLED_STAT2` `ME_WAITING_ON_PARTIAL_FLUSH`), with an end-of-pipe event
    pending (`EOPD_FIFO_NEEDS_SC_EOP_DONE`, `CP_BUSY_STAT` `EOP_DONE_BUSY`).
  - So the hang is in work launched earlier in the job, not in a packet the CP is processing.
  - The CP pointers (PFP 0xea1, ME 0x77b) are the generic wait loop of F524, not a sign of F403.
- **What is busy.** Decoded with Linux v7.2 `gc_10_1_0_sh_mask.h`:
  - `GRBM_STATUS` 0xa2712028 has **GE, PA and SX busy** and SPI busy, with TA idle and DB not clean. `GRBM_STATUS_SE0`
    0x0d000004 has PA and SX busy, no TA/TCP. `GRBM_STATUS2` 0x50000008 has no TCP_BUSY.
  - Against F403 (0xa0407028, SE 0x0a000036, TA and TCP busy, no EOP pending), this is the **graphics pipeline**
    (geometry → rasteriser → export) that does not drain. It is not a compute dispatch.
- **The sampler's `COMPUTE_PGM` 0, `DIM` [0 1 1], threads [8 4 1], initiator 0x8041** read the compute SH copy, which
  says nothing about a graphics stall. F536 already saw program 0 with a live grid in 9 healthy samples. So the stuck
  work is not shown to be a dispatch at all.
- **No page fault** precedes the 18:08 timeout in this boot (the sampler's kernel-line copy).
- **The probe.** The job holds 29 dispatches (5 indirect, the largest grid 15,678) and draws. "HS user data address 0x0
  … not mapped" appears at three places, as in earlier probes (09:48), so it is not specific.
- **The class.** The nearest earlier state is F519 (ASTRO BOT, 06:34): a graphics-pipe stop with GE/PA busy and resident
  waves drained, which also reached `bc5-gpu-watch`. Unlike F519, SPI is still busy here. Which draw does not finish is
  open. The next read would be the devcoredump's IB walk for the job's last draws and the sampler's per-sample SE state.
- **The unpause.** The host's own pause (the window's Space key) appears in the play log only at 146–150 s, nowhere near
  the hang (~52 min into the play). So his pause was most likely the title's own menu pause. Unpausing makes the title
  resume rendering (and may rebuild render targets or start effects), but no host path (flip, video out) changes state
  then. Relevance: possible, not shown.

**F535's discriminator (F589).**
- The rule (`ME_WAITING_ON_PARTIAL_FLUSH` set and `EA_LINK_BUSY` clear) **fires on this hang too**, although it is not
  F403's state. So the rule alone does not identify F403.
- Adding **TA_BUSY or TCP_BUSY set, GE_BUSY clear and no EOPD wait** separates both the 18:08 state and the healthy
  parked frames from F403's. That is consistent with F525/F534's records, but untested on the 40 healthy samples beyond
  these fields.
- An early-warning rule should report "graphics stall" and "compute stall (F403-like)" as different events.

## 18. Where the garbage dims come from, a flight recorder, and a soak (F590–F594; laptop only, no box access)

**The request (the top session).** Stop testing fixes. Find out where the garbage dims come from: did the CP read the
wrong address, or the right address with stale data? Design a flight recorder that settles it at the next hang, and
assess an unattended soak. Laptop only: everything below is read from extracts already in `raw/`, and nothing touched
the box. Decode script: `raw/dims0380.py`.

**The triples.** Only two title events have a launched grid (sampler 0377 came after 09:48, F550). The bench runs C1
and W1 add a third, host-induced triple.

| event | program | launched `COMPUTE_DIM` | memory at the args address (CPU, at the timeout) | `INDEX_BASE` before it, its heap (M1 map log) |
|---|---|---|---|---|
| 12:12 | 0x11d0289c00 | 0x00010000 0x00030002 0x002a0028 | 111 × 1 × 1 at 0x11d0571d00 | 0x11e9db6280, RenderGpuRwLarge |
| 14:04 | 0x11d02a4a00 | 0x000001e1 0x4000008a 0x000001e0 | 3158 × 1 × 1 at 0x11d05df300 | 0x1210012000, CommitIABufferAllocator |
| C1, W1 | 0x11d0323c00 | 0xbefe036a 0x810e810e 0x06043736 | 28,800 × 1 × 1 at 0x11d0571b00 | (the dispatch ran from the high-VA copy slot) |

**What they do not match (F590).**
- **Not PM4.** None is a type-3 header, and none occurs in its hung IB (`find0380.py`, F565).
- **Not an address of ours.** None equals a half of the `SET_BASE`, `INDEX_BASE`, `LOAD_SH_REG_INDEX` or program
  addresses, or of the check's flag area.
- **Not another dispatch's arguments.** Every argument the timeout probes read is (x, 1, 1) with x ∈ {0, 111, 1,295,
  3,158, 3,498, 4,464, 6,136, 28,800} (F506, F528, F553, F564, F571).
- **Not stale arguments of the same slot.** The slots (0x11d05df300, 0x11d0571b00, 0x11d0571d00) are fixed: the same
  addresses carry this family's arguments in every frame, across hours and boots (18:15, 23:36, 09:48, 12:12, 14:04).
  So any older contents of the slot are arguments too, (x, 1, 1). A stale line of the slot would launch an old
  (x, 1, 1), not these.
- **So the CP fetched dwords that were never at the slot.** Either the fetch went to another address, or a cache line
  of another address answered for it, which comes to the same thing. Medium confidence: it rests on the slots never
  holding other data, which the logs support but cannot prove for the moment of the fetch.
- **What each one looks like** (TODO(verify): which candidate address held it at the time):
  - 12:12 reads as six little-endian 16-bit values: 0, 1, 2, 3, 40, 42. That is index-buffer-like data. Its
    `INDEX_BASE` is in RenderGpuRwLarge, a GPU-written heap.
  - 14:04 reads as 32-bit 481, 0x4000008a, 480. The outer two are index-like; the middle one is not an index (as f32
    it is 2.0000329). Its `INDEX_BASE` is in CommitIABufferAllocator, the input-assembler (index/vertex) heap.
  - So both are consistent with "the fetch read at or near the `INDEX_BASE`" (H0380b's original form, F555). Neither
    proves it: the index data at those addresses is not recorded anywhere.
- **The `INDEX_BASE` heap at 14:04 was in the zero-skip list's heap** (CommitIABufferAllocator, 284 MiB in 4 runs
  skipped). *Checked in §19: the chunk at heap offset 0x12000 was not in any skipped run.*

**C1/W1's triple is shader code (F591).** The three dwords decode as three valid gfx10 instructions (field layout of
AMD's RDNA 1.0 ISA guide; *confirmed in §19 by llvm-mc 21.1.8 `-mcpu=gfx1013`*):
- 0xbefe036a: SOP1 op 3 `s_mov_b32`, sdst 126 (`exec_lo`), ssrc0 106 (`vcc_lo`);
- 0x810e810e: SOP2 op 2 `s_add_i32`, sdst s14, ssrc0 s14, ssrc1 129 (inline 1), a loop counter;
- 0x06043736: VOP2 op 3 `v_add_f32`, vdst v2, src0 310 (v54), vsrc1 v27.

The title's compute programs (0x11d02…–0x11d03…) live in the same heap as the arguments, RenderGpuWcSmall
(0x11d0000000 + 0x6e00000, M1's map log, `raw/runs/M1-memory-types.txt`). So with the base above the fetch's reach
(F572), the CP's argument fetch read program code from one fixed place: a wrong address, shown. That is the
host-induced case, but it is the first direct evidence that this fetch path can land on an address other than base +
offset without faulting.

**Can (1) alone settle it? No (F592).**
- The decision needs the contents of the candidate addresses (the `INDEX_BASE`, the earlier bases, the program) at
  the moment of the hang. No record holds them. The devcoredump has registers and IBs, no memory; the probe reads only
  the argument slot; and the box rebooted after both events.
- One box read remains (it needs a GO): 14:04's skip list against the `INDEX_BASE` chunk.
- **Part A of the recorder needs no GPU change.** It is an extension of the host's timeout probe, CPU only, zero CP
  packets:
  1. Read the newest sampler 0377 event for the launched `COMPUTE_DIM` (it is written 0.1–0.2 s before the host's
     timeout).
  2. Dump 64 bytes at the IB's last `INDEX_BASE`, at every `SET_BASE` 1 base of the IB, at the stuck program's
     address, and at the args slot.
  3. Scan every title GPU mapping (CPU-visible memfd, ~10–12 GiB) for the 12-byte triple, and for each dword alone at
     4-byte alignment. Log each hit's VA and heap name, then fsync.

  The scan costs ~2–4 s single-threaded, inside the ~60 s before `bc5-gpu-watch` reboots. The probe's lines survived
  the failed resets at 12:12 and 14:04.
- **The verdict A gives at the next B hang:**
  - the triple found at the `INDEX_BASE` (+k) → wrong address through the index path (H0380b);
  - found elsewhere → another wrong address, named by its heap;
  - found nowhere → the data was transient (stale or a translation error), and part B is needed.

**Part B, the GPU-side ring (F593).** Off by default (`BC5_DIRECT_FLIGHT_RECORDER=1`, not built); no shared-build change
without D19. It records, per indirect dispatch:
1. **Host view** (CPU, free, at filter time). A host ring entry: sequence number, submission #, IB dword, base,
   offset, VA, the last `INDEX_BASE`, the program.
2. **ME view, before the dispatch.** A `WRITE_DATA` of the sequence number, then three `COPY_DATA` memory → ring of
   the arguments at base + offset (the same packet as the copy guard, F566).
3. **Fetch view, after the dispatch.** Three `COPY_DATA` *register* → ring of `COMPUTE_DIM_X/Y/Z` (byte offsets
   0xb804/08/0c = dword 0x2e01–0x2e03, `tools/bc5-agc/regdb/gfx10.json`). The register source is the packet the
   kernel itself uses to read registers on gfx10 rings (src_sel 0, dst 5, `WR_CONFIRM`; Linux v7.2
   `gfx_v10_0.c:8986-9000`, fields in `nvd.h:252-271`).

These registers are where the sampler saw the garbage. So the ring compares the ME view with the fetch view for
**every** recorded dispatch, not only the one that hangs.
- **Readout.** The host reads each retired ring entry at its fence (CPU-mapped low-VA BO). It logs every mismatch at
  once, with the host entry, and keeps a periodic count. At TIMEOUT it dumps the last N = 256 entries and fsyncs.
  After the reboot everything is in the journal, as the probe lines are today. The devcoredump adds nothing new for
  this.
- **What it buys.** A benign mismatch (a wrong fetch with small values that does not hang) would show up during healthy
  play. That gives a rate without a hang, and turns any bench or soak into a measurement.
- **Cost.**
  - 5 + 18 + 18 = 41 dwords per recorded dispatch.
  - On the B slot (first after `INDEX_BASE`, ~130/s in play, F583) plus the next three indirect dispatches of the IB:
    ~520 a second, ~85 KB/s of IB, nothing measurable.
  - On every indirect dispatch it would add ~47 % to the check (88 dwords) on the BVH dcbs (Q23); not recommended.
  - Ring: 256 × 16 dwords = 16 KiB, one low-VA BO in every BO list (F574's slot plumbing).
- **Risks** (CP hazards first):
  - **The register read.** Reading an SH register through `COPY_DATA` on the gfx ring while the SPI launches that
    dispatch is not shown to be safe or to return the launched value. TODO(verify): F553's open question whether the
    readable copy is the SPI's. A privileged-register filter could also reject it. It needs a bench self-test first:
    `direct-selftest` with known direct and indirect dims, the reg copy against them, `--submit`, the maintainer's
    yes.
  - **The observer effect.** Packets between `INDEX_BASE` and the dispatch may hide the bug, as the GL2 write-back's
    `ACQUIRE_MEM` perhaps does (F584). So: no `ACQUIRE_MEM`, no `SET_BASE`; the before-copies go before the check,
    which already puts 88 ME dwords there, and the register copies go after the dispatch.
  - **IB structure.** The title's own `COND_EXEC` counts must cover the added dwords (the check's tests already cover
    this case, F566), and the ring BO must be in every submission.
  - **The copies' own reads** of the argument slot go through the ME path that already reads the right values (the
    check's polls). They add no new kind of access.
- **Order.** A first: no GPU change, decides most outcomes at the next B hang. B's self-test next, then B in play.

**A soak without the maintainer (F594).**
- **The bench has shown no B event.**
  - The S6N route with RT on and no effective fix ran R1, R2 (rebase, refuted as a fix by 14:04), S1 (rebase +
    FORCE_START, 300 s) and M1 (no switches): 2,100 s, ~300,000 first-after-`INDEX_BASE` dispatches, **0 B events**.
    W2/W3 are left out: they had the write-back on.
  - All five B events on record came in the maintainer's own plays.
- **His rate.** The top session's ~1 per 7–10 min of play (6–8.6/h), or ~1 per 54,000–77,000 such dispatches at
  ~130/s.
- **The comparison.** At his rate the bench should have shown 3.5–5 events by time, or 3.9–5.6 by exposure. Zero has
  p ≈ 0.004–0.03. So the scripted route is much less prone, although it runs the B slot at least as often (~145/s).
  The trigger is in what he does (scenes, movement, combat, streaming, menus), not in the dispatch count alone.
- **Per-hour estimate for the route.** Unknown, with a point estimate of 0. These 35 min bound it below ~5/h (95 %),
  which is not tight.
- **An overnight soak (8 h, RT on, on a save copy) as a measurement:**
  - one hit → a reproducer;
  - none → the route's rate is below 0.37/h (95 %), and the route is useless for this.
- **Practical limits.**
  - The first hang reboots the box, so one event per night, unless the loop restarts itself after autologin. That is
    unattended GPU work and needs the maintainer's yes.
  - Memory pressure grows over hours (exp 0379).
- **Better soak content.** Alternate the lake bench with the automated fight test, from a copy of his current save
  near where he plays.
- **Best with B on.** Mismatches counted per hour make a night useful even without a hang.

## 19. Part A built: the "test 0380 rec" shortcut, and what the records say about candidate addresses (F595, F596)

**GO.** The top session relayed the maintainer's "zbuduj" (build it) for part A, with box access. 20:36–20:49: my lock
line (`top exp 0380 | rec build`, the smoke runner's own `… | rec build run` line during RC1), claim and done lines
in BOX-QUEUE, the kernel stream to `raw/runs/REC-kernel-stream.txt` (no GPU line). Live saves
**a92fe0992638a454** before and after.

**The two open reads.**
- llvm-mc 21.1.8 (`-arch=amdgcn -mcpu=gfx1013 --disassemble`, the ubuntu container) decodes C1/W1's triple as
  `s_mov_b32 exec_lo, vcc_lo`, `s_add_i32 s14, s14, 1`, `v_add_f32_e32 v2, v54, v27`, as F591 had it. 12:12's
  0x00010000 and 14:04's 0x4000008a are "invalid instruction encoding": not code.
- 14:04's `INDEX_BASE` 0x1210012000 is at offset 0x12000 of CommitIABufferAllocator. The zero list
  `zero-list-20261029-120000.txt` skipped that heap at offsets 0x7800000 (+0x2e00000), 0xa800000 (+0x800000),
  0x2fe00000 (+0xde00000) and 0xaa800000 (+0x800000). So the chunk was **not skipped**: the skip did not touch the index
  data there.

**The build (F595).**
- **Source.** The shared tree's `src/libs/bc5LleAgc.cpp`, git blob 8d2f498 (= patch 0001 on main; the tree at
  f266548 + patch, exp 0372's `pad_audio_route.hpp` and audio edits present), copied by `raw/mk-rec0380.py`. That
  script makes four counted literal edits:
  - three includes;
  - `raw/rec0380.inc` inserted in front of `timeout_probe`;
  - one call after each of the two `timeout_probe` calls.
- **Compile and link.** `raw/build0380x.py` compiles that one unit with the shared build's own compile command
  (clang, compdb). It then runs the shared link command with only that object swapped in. The other objects and the
  backend archive stay the shared build's (no exp 0379/0380 switch exists in it). No warning comes from the new code;
  the unit's five warnings are pre-existing.
- **Binary** `~/bc5-work/exp0380rec/bin/kyty_emulator`, **md5 b8561eaa**. Shared normal 58c4a627, lean dcbeb440
  and `play-pkg.sh` 55531ab6 are unchanged.
- **What it does** (`BC5_0380_REC=1`, default off). After a fence timeout, right after the existing timeout probe,
  CPU only, with no packet added:
  1. It takes the launched `COMPUTE_DIM` from the newest sampler 0377 event (`summary.txt`), waiting up to 8 s.
  2. It dumps 64 B at every `SET_BASE` 1 base, `INDEX_BASE` and argument address of the buffer, and at the program.
  3. It scans every resident page of the title's GPU mappings, read through `process_vm_readv`. `mincore` keeps it
     from faulting a page in, and an unreadable page is counted, not fatal. It looks for the triple, each pair and
     each dword.
  4. It writes `<dump dir>/rec0380-<submission>-<kind>.txt` (≤ 1 MiB, fsynced) and synced "rec0380:" journal lines.
  - The scan stops at 20 s (`BC5_0380_REC_SCAN_S`).
- **Harness.** `raw/rec0380_test.cpp` (g++ `-Werror`, box container) passes all checks: the self-test path, the
  sampler path, a `PROT_NONE` mapping counted as unreadable, an untouched one as not resident, 512 MiB in 0.18 s.

**Smoke run RC1** (`raw/s6n0380rec.sh` by `raw/mk-s6n0380rec.py`; S6N, RT on, the route's save copy, 300 s,
`BC5_0380_REC=1 BC5_0380_REC_SELFTEST_S=150`; `raw/runs/RC1-extract.txt`):
- **Pass.** 0 crash, kernel, TIMEOUT or devcoredump lines; 9,944 flips in 299.8 s.
- **Idle.** No "rec0380" line other than the one self-test.
- **No visible overhead.** From 160 s on, RC1 ran 387–410 flips per 10 s. M1 on the shared build's objects ran
  386–409 over the same window (`raw/runs/RC1-flips-per-10s.txt` against `M1-flips-per-10s.txt`). The 300-s mean
  (33.2/s) is lower only because a 300-s run holds proportionally more of the loading ramp and the self-test window.
  The window 150–160 s had 18 flips: the self-test held the completion thread.
- **The dump path, triggered once.** At 150 s, on dcb #138480 (1,675 dwords, 9 indirect dispatches), it wrote
  `rec0380-00138480-dcb.txt` (14,932 bytes, fsynced) and the journal lines. It scanned **11,347.8 MiB resident** (3,827.8
  MiB not resident, 0.2 MiB unreadable, 21,540 mappings) in **8.92 s, 8.97 s in all**. The self-test's dims were
  (0, 1, 1), a poor pattern (46,058 triples); the harness, not this run, shows that a planted triple is found at its
  address.
- **Live saves unchanged** (a92fe0992638a454).

**Timing against `bc5-gpu-watch`.** The watch crashes the kernel 60 s after a ring timeout that is not followed by a
successful reset. The host sees the fence timeout ~2.04 s after its submission (F553, F564). Then come the existing
probe, the sampler wait (its event is written 0.1–0.2 s before the host's timeout, so the wait is normally short,
≤ 8 s by design), and the scan (≤ 20 s cap, 9 s measured). So the recorder ends within ~2 + probe + 8 + 20 = ~30 s
plus the probe, and is typically at ~11–12 s plus the probe. It is not tested in a real hang: inducing one is not
safe.
- The probe's own lines reached the journal at 12:12 and 14:04, whose resets also failed. TODO(verify) the existing
  probe's duration, which the next hang's journal timestamps will show.

**The shortcut.**
- "BC5 emulator (test 0380 rec)" is on the maintainer's desktop (`~/Pulpit`, md5 884256a5, `raw/rec/`). It runs
  `~/bc5-work/exp0380rec/play-pkg-0380rec.sh` (md5 9aa6f587, made by `raw/mkplay0380rec.pl` from `play-pkg.sh`;
  diff in `raw/play-pkg-0380rec.diff`).
- It sets `BC5_0380_REC=1` and unsets every exp 0379/0380 fix switch. Logs go to `~/bc5-work/exp0380rec/play/`.
- The launcher was not started itself: RC1 ran the same binary and switch through the runner's own launcher copy.
- "test 0380 wb" was moved to `~/bc5-work/exp0380wb/retired/`. The two shared shortcuts are untouched.

**After a hang.** The maintainer does nothing but tell us; the box reboots by itself. The results land in:
- `~/bc5-data/captures/play-<date>/gc/rec0380-<submission>-dcb.txt`;
- the "rec0380:" lines of that directory's `direct.log`;
- the sampler event in `~/bc5-data/captures/gpu-stall/`.

All of them are private, never in the repo.

**The records against candidate-address rules (F596; the top session's follow-up, laptop only).**
- **12:12.** `SET_BASE` 1 = 0x11d0571d00, the dispatch's data offset 0, so the slot is 0x11d0571d00. `INDEX_BASE`
  0x11e9db6280.
- **14:04.** Slot 0x11d05df300 (offset 0); `INDEX_BASE` 0x1210012000.
- **The candidates collapse.** With offset 0 and the slot at its base, "`INDEX_BASE` + the slot's offset", "`INDEX_BASE`
  + the data offset" and "`INDEX_BASE`" are one address per event. "The slot with `INDEX_BASE`'s high bits" is the slot
  itself at 12:12 (both high dwords 0x11) and 0x12d05df300 at 14:04: above CommitIABufferAllocator's end (0x12bb000000)
  and in no heap of the M1 extract.
- **No rule fits both.** The offsets of the `INDEX_BASE` from the slot differ (0x19844580, 0x3fa32d00). So do the low
  bits (0x280 vs 0x000 for the `INDEX_BASE`, 0xd00 vs 0x300 for the slot) and the alignment (128 B vs 8 KiB), and the
  heaps differ (RenderGpuRwLarge vs CommitIABufferAllocator). The only common candidate, "the fetch read at the
  `INDEX_BASE` itself", cannot be checked from the records: no one recorded what lay there.
- **The packet stream between them is the same in both, dword for dword.** `SET_BASE` 1 (1249), `INDEX_BASE` (1253),
  `INDEX_BUFFER_SIZE` 0xffffffff (1256), `NUM_INSTANCES` (1258), then three `SET_UCONFIG_REG`s: 0x24e
  `VGT_TF_RING_SIZE`, 0x250 `VGT_TF_MEMORY_BASE` and 0x261 `VGT_TF_MEMORY_BASE_HI` (names from
  `tools/bc5-agc/regdb/gfx10.json`). After them come `ACQUIRE_MEM` (1269), ten NOPs, the host's check (1287–1374;
  plus the rebase `SET_BASE` at 1375 at 14:04), and the dispatch.
  - No `DRAW_INDEX*`, no IB boundary (all in IB #0), no CE/DE switch.
- **A new candidate.** The title reprograms the tessellation-factor ring right between the `INDEX_BASE` and the
  stuck dispatch. The timeout probe already dumps that ring (`<ib dump>.tfring.bin` and a "TF ring" journal line,
  exp 0189). Searching the 12:12 and 14:04 TF-ring dumps for the two triples is a box read of already-captured
  private data (it needs a GO). Part A adds the TF ring base to its candidates only if that read is positive.

**The TF-ring read (F597; the top session's GO, reads only, 21:0x, lock line `top exp 0380 | reads only: TF-ring …`,
cleared; claim and done lines in BOX-QUEUE).**
- **Coverage.** Both events have the ring at 0x1120000000, 0x3fff8 bytes (the probe's "TF ring" journal line). At 14:04
  the probe's dump (`ib-timeout-00278264-dcb-8251.bin.tfring.bin`, private) holds all 262,136 bytes, the whole ring
  as programmed; the acb's copy is identical. At 12:12 both `.tfring.bin` files are **empty** (0 bytes): only the
  journal line's first ~48 dwords exist.
- **No hit.** None of the three triples (12:12, 14:04, C1/W1) occurs in the 14:04 ring at any byte alignment: not as
  a triple, a pair, a single 32-bit dword or the 16-bit sequence. Nor do 12:12's or 14:04's dwords occur in 12:12's
  journal excerpt.
- **What it holds.** The ring holds f32 tessellation factors: 22,289 distinct values between 0 and 0x40800000 (4.0),
  0x40000000 (2.0) 280 times, only 2 dwords below 0x10000. 14:04's 0x4000008a (≈ 2.0000329) looks like such a factor,
  but it is not in the ring, and its neighbours 481 and 480 are integers, which the ring does not hold.
- **So the TF ring is not the source** at 14:04 (fully covered) and is not supported at 12:12 (barely covered). The
  reprogramming of `VGT_TF_*` between `INDEX_BASE` and the dispatch stays a timing fact, not a data source. Part A's
  candidate list needs no TF-ring entry, and its whole-memory scan would find such data anyway.

## 20. The maintainer's hypothesis: a SET_BASE tracked inside a conditional block (F598–F600; laptop only)

The hypothesis (the maintainer, via the top session): the host tracks `SET_BASE` wrongly inside a conditional block,
so the guard may check the wrong address. Read from the code on this branch and the records already in `raw/`.

**How the host tracks `SET_BASE` index 1 (F598).**
- **The check's tracker** (`backend/src/indirect_check.cpp:124`) walks the IB linearly from `base_in` and takes every
  `SET_BASE` index 1 it meets. It notes the IB's `COND_EXEC` ranges (`:120`) only to grow their counts, never to ask
  whether a `SET_BASE` inside one ran.
- **The full-state tracker** (`backend/src/full_state.cpp:224`) is the same: linear, no `COND_EXEC` handling. Patch
  0001 keeps one global copy (`static bc5::full_state::Tracker tracker`, patch lines 33353–33354). It applies every
  `cc`, `hib` and `dcb` buffer in the order the host filters them, not the order the CP runs them, and it reads
  nested IBs through the host's mappings.
- So a `SET_BASE` index 1 inside a `COND_EXEC` range the CP skips moves both host views but not the CP. The CP keeps
  the old base while the host holds the new one. The reverse case cannot happen, because neither tracker ever drops
  a `SET_BASE`. This is a real, latent defect.
- **How often the title does this:** not counted. The three B dumps' records (`raw/suspects/title-ib-1240-1300.txt`,
  F596) have no `COND_EXEC` near the stuck dispatch. F430's event had no `SET_BASE` inside a range either. A count
  over whole streams needs the private IB dumps, which is a box read.

**What the B events' `SET_BASE` is (F599).**
- Dwords 1249–1268 of all three B dumps are not the title's packets. They are the host's full-state prefix, in
  exactly the order the host emits it:
  - `Tracker::emit_prefix` (`full_state.cpp:271-275`) emits `SET_BASE`, `INDEX_BASE`, `INDEX_BUFFER_SIZE`, then
    `INDEX_TYPE` (empty, so left out), then `NUM_INSTANCES`;
  - `tf_ring_prefix` (patch line 32167) emits `VGT_TF_RING_SIZE` 0x24e, `VGT_TF_MEMORY_BASE` 0x250 and
    `VGT_TF_MEMORY_BASE_HI` 0x261;
  - the prefix is emitted in front of every `dcb` that draws (`BC5_DIRECT_PREFIX_ALL`, default `draws`, exp 0157;
    patch lines 31995–32004 and 32527–32528).
- The title's buffer starts at 1269: `ACQUIRE_MEM` (`GCR_CNTL` 0x280), the two empty loads (F577), then the stuck
  `DISPATCH_INDIRECT` with offset 0. It sets no `SET_BASE` of its own. The dispatch's base therefore comes from our
  prefix, that is, from the global tracker's last `SET_BASE` index 1.
- This corrects F596's "the title reprograms the TF ring": that is our `tf_ring_prefix`.
- Confidence: high, from the order. TODO(verify): dword 0 of a B dump should be `CONTEXT_CONTROL` 0x80000000 /
  0x80000000, then `CLEAR_STATE`.

**What the host emits from a tracked base, and the verdict (F600).**
- **What the host emits from a tracked base:**
  - the check's `COND_WRITE` poll addresses, from the check's `base` (`indirect_check.cpp:132-134`);
  - with `ARGS_COPY`, the `COPY_DATA` sources;
  - with `REBASE_DISPATCH`, a re-emitted `SET_BASE` index 1 (`:244-248`);
  - the prefix's `SET_BASE`, `INDEX_BASE`, `INDEX_BUFFER_SIZE` and `NUM_INSTANCES`, from the global tracker;
  - with `BC5_DIRECT_HOST_INDIRECT` (exp 0346, off in these builds) only, rewrites from the carried register.
  With `REBASE`, `ARGS_COPY` or the prefix, a base taken from a skipped block would become a base the CP really
  uses.
- **It does not fit the B events.** In both events, the check's polls (0x11d0571d00/04/08 at 12:12, §5) and the
  dispatch's fetch go through the same `SET_BASE` packet, our prefix's at 1249. That packet is unconditional and 38
  dwords before the dispatch. The 14:04 rebase at 1375 re-emits the same value. A wrong tracked base moves the check
  and the fetch together. That can launch the wrong slot's sane arguments (a slot the check also passed), but not
  garbage that the polled slot never held (F590).
- **It does not fit C1/W1 (F568, F591).** There the base was our own copy (`copy_va`, set by the host and not
  derived from a tracked title base). The ME's `COPY_DATA`s with `WR_CONFIRM` and every poll of that copy passed,
  and the fetch still read shader code.
- **Verdict: refuted** as the cause of the B-class garbage dims. The latent defect stays (a `SET_BASE` in a skipped
  `COND_EXEC` range); it would give wrong but sane arguments.
- **What it leaves:** every B event is the first `DISPATCH_INDIRECT` after our `CONTEXT_CONTROL` + `CLEAR_STATE` +
  full register prefix, in a buffer that relies on the base that prefix sets.
- **The cheapest next test is a box read, with no build.** Over the private IB dumps already captured, count:
  1. `SET_BASE` index 1 inside `COND_EXEC` ranges (this closes Q2);
  2. prefixed dcbs whose first indirect dispatch comes before their own `SET_BASE` (how common the B shape is);
  3. whether every recorded F403 B event has that shape.

  A behavioural test of the prefix as the trigger would follow only if count 3 holds.

## 21. The count over the private dumps, and the 21:33 play (F601–F603; the top session's GO, reads only)

Reads only, 22:37–22:5x. Lock line `top exp 0380 | reads only: IB-dump SET_BASE count + 21:33 play logs`, cleared;
claim and done lines are in BOX-QUEUE. The maintainer was not playing. The script is `raw/shape0380.py`, which
prints offsets and counts only. Its outputs are in `raw/runs/`: `SHAPE-timeout-dumps.txt`, `PLAY-2133-mem.txt` (our
own memory sampler) and `PLAY-2133-fps-per-minute.txt`.

**The counts (F601).**
- **What was read:**
  - all 53 `ib-timeout-*-dcb-*.bin` dumps under `~/bc5-data/captures/play-*/gc/` (2026-10-23 to 10-29);
  - 1,987 healthy dcb dumps: `exp0157-ib679`…`ib682`, `ibdump-262`, `-372` and `-377`, from 10-12 to 10-18.
- **Count 1:** no `SET_BASE` index 1 lies inside a `COND_EXEC` range, in any dump.
  - Timeout dumps: 0 of 5,982 `SET_BASE` index 1 packets, in 175 ranges.
  - Healthy dumps: 0 of 30,564, in 1,452 ranges.
  - So F598's latent defect has never been exercised in any recorded stream.
- **Dword 0 is our prefix's.** 43 of the 53 timeout dumps begin with `CONTEXT_CONTROL` 0x80000000/0x80000000, then
  `CLEAR_STATE`. All five B dumps are among them. In every prefixed dump, the prefix's first `VGT_TF_MEMORY_BASE_HI`
  ends at dword 1269, which confirms F599's TODO.
  - Several dumps hold more than one prefix: at 12:12, `CONTEXT_CONTROL` sits at 0, 7011 and 10027.
- **Count 2, the shape:** a prefixed dcb whose first GFX-form `DISPATCH_INDIRECT` comes before any `SET_BASE`
  index 1 of its own.
  - It appears in exactly 5 of the 43 prefixed timeout dumps, the five sub-class B events: 18:15 (10-28), 23:36,
    09:48, 12:12 and 14:04. Their first dispatch is at 1287–1289, right after the prefix.
  - The other 38 prefixed hangs have the title's own `SET_BASE` before their first indirect dispatch, or no
    indirect dispatch at all.
  - Seven unprefixed timeout dumps also dispatch before any `SET_BASE` (10-27 to 10-29 16:25, first dispatch at 13–102).
    These are the earlier chain classes under a carried base (F430 era), not B.
- **Count 3 holds: every recorded B event has the shape** (5 of 5).
- **Healthy streams: not measured for the current build.** The healthy dumps show the shape 0 times and have no
  dispatch before a `SET_BASE` at all. But they predate the default prefix (only 54 of the 1,987 carry it), and they
  come from other scenes.
  - The indirect evidence says the shape is common now. F506 calls B's opener the family that "opens most frames'
    dcb" (§11).
  - `ARGS_WB=first` wrote GL2 back before 282,894 first-after-`INDEX_BASE` dispatches in 36.6 min (about 129 a
    second; `exp0380wb/play/play-20261029-162552.log`). Every prefix supplies such an `INDEX_BASE`.
  - So the shape is the context of every B event, not by itself a trigger. It runs many times a second, and B comes
    about once an hour.

**The 21:33–21:55 play on "test 0380 rec" (F602).**
- No hang and exit 0. The direct log (`~/bc5-data/captures/play-20261029-2133*/gc/direct.log`, 318 MB, private)
  has no fence timeout, no fault and no `rec0380:` line. Its "timeout" matches are frame-profile and slow-post
  counters, plus one "timed out 0".
- **Frame rate per minute:**

  | Minutes | flips/s | Longest gaps |
  |---|---|---|
  | 0–1 | 21–23 | loading, gaps up to 1.7 s |
  | 2–15 | 24–45 | 0.11–0.8 s |
  | 16–21 | 21.5, 17.4, 17.1, 13.2, 14.9, 9.0 | 0.7–1.7 s |

- **The memory sampler shows why.** Up to 21:49, memavail ran at 300–560 MB, swap at 0.8–1.07 GB and
  `psi_mem_full60` at 0.16–1.24 %. At 21:50:58:
  - `psi_mem_full60` jumped to 8.5 %, then 9.3, 13.2, 16.4 and 14.1 %;
  - swap peaked at 1.62 GB;
  - the emulator's RSS fell from about 2.5 GB to 0.7–1.3 GB, and the mount's from about 715 MB to 140–325 MB;
  - the mount's reads rose to 9.0–9.9 GB a minute, against 2–6 GB/min in minutes 2–15.

  The game's working set and the package mount's cache were being evicted and re-read: a reclaim storm. GTT grew
  the whole time, from 11,437 MB to 12,702 MB (+1.27 GB in 21 min), and it is pinned. That growth pushed the box
  over the edge in minute 16.
- **The recorder cost nothing measurable.** It never fired, because there was no timeout and the self-test is off
  in the play launcher. Its only work per completed dcb is one `getenv` check. The smoke run showed 387–410 flips per
  10 s against M1's 386–409 (F595). The instability is the memory pressure. Not checked: whether the shared normal
  build's GTT grows the same way in the same scene. The launcher's `fusermount3` "Device or resource busy" at exit
  left no `bc5-mount` process behind.

**The behavioural test, proposed and not built (F603).** Count 3 holds, so it tests the one thing every B event
shares besides the shape: the dispatch is the first after our `CONTEXT_CONTROL` + `CLEAR_STATE`.
- **The test needs no build.** It is the shared normal build with `BC5_DIRECT_PIECES_NO_CLEAR=1` (exp 0155's
  diagnostic, patch lines 32244–32247), which drops the prefix's first five dwords and keeps its `SET_BASE`,
  `INDEX_BASE` and TF-ring registers. It runs as one test launcher (`mkplay0380rec.pl`'s pattern) with RT on,
  played by the maintainer.
- **Cost:** none on the GPU side. It writes five dwords fewer per drawing dcb.
- **Risk:**
  - Context registers the tracker never saw keep whatever the last job on the ring left. That brings back F204-type
    menu artefacts, a visual risk, not a hang.
  - Whether `CLEAR_STATE` matters to the CP's fetch is TODO(verify). It is the hypothesis under test.
- **Power:** B came about once per hour of RT-on play. Two hours without B gives p ≈ 0.14 if nothing changed; three
  hours gives about 0.05.
  - `ARGS_WB=first` already went 36.6 min without B, with a sync at the same point.
  - One B event with the switch on refutes `CLEAR_STATE` as the trigger.
- Not to be built or staged before the top session's GO.

## 22. The "test 0380 noclear" shortcut: the recorder with exp 0379's zero skip, and the prefix without `CLEAR_STATE` (F604)

On the top session's GO, with the maintainer's "Tak, z 0379". The box session ran 22:47–22:59: lock lines
`top exp 0380 | noclear …`, cleared; claim and done lines in BOX-QUEUE; kernel stream `raw/runs/NC-kernel-stream.txt`,
with only IPv6 MLD lines.

- **The skip needs its own binary.** Exp 0379's zero skip is host code in `bc5LleAgc.cpp` (`patch0379-bc5LleAgc.diff`
  plus `zero_skip.hpp`), so the rec binary b8561eaa does not hold it. The first brief therefore stopped before any box
  access.
- **The build** (`raw/build0380nc.sh`, CPU only, nice 19, 30 s):
  - **Unit:** exp 0379's patched unit (exp0379t's copy, e62113a5; header 782ca0e9) gets the recorder's four edits
    (`mk-rec0380.py`), giving 71fae694, the same as the laptop's combination.
  - **Compile and link:** only that unit is compiled (`build0380x.py`), against the shared objects and the shared
    archive bb50b2e0. The unit's five warnings are all pre-existing; none falls in the recorder's lines (6315–6507).
  - **Binary** `~/bc5-work/exp0380nc/bin/kyty_emulator`, **md5 99d91d2d**. It contains the zero-skip strings (10),
    the `rec0380:` strings and the `BC5_DIRECT_PIECES_NO_CLEAR` switch name.
  - **Shared files unchanged:** normal 58c4a627, lean dcbeb440, archive bb50b2e0, tree unit e7cc2f60 and
    `play-pkg.sh` 55531ab6, before and after.
- **The launcher** `~/bc5-work/exp0380nc/play-pkg-0380nc.sh` (**29c82f19**) is made by `raw/mkplay0380nc.py` from the
  rec launcher (9aa6f587), with counted edits. Its diffs are `raw/play-pkg-0380nc.diff` (against `play-pkg.sh`) and
  `raw/play-pkg-0380nc-vs-rec.diff`. It:
  - sets `BC5_0380_REC=1` and `BC5_DIRECT_PIECES_NO_CLEAR=1`;
  - sets `BC5_DIRECT_ZERO_SKIP` to a private copy of exp 0379's fixed list `zero-list-20261029-120000.txt` (7a4f972c);
  - unsets write-back, FORCE_START, copy, rebase, the zero guard, the scan and the self-test;
  - otherwise behaves as the rec launcher: RT on from the shared `input.cfg`, the job arena as shipped, one log, mount
    log and memory record per start in `~/bc5-work/exp0380nc/play/`, and a first log line naming the switches, the
    list's md5 and the binary's md5.
- **The shortcut** "**BC5 emulator (test 0380 noclear)**" is installed in `~/Pulpit` (d208b444, `raw/nc/`). "test 0380
  rec" was moved to `~/bc5-work/exp0380rec/retired/`. The shared shortcuts are untouched. Sampler 0377 stays
  installed and active.
- **The smoke run NC1** (`raw/s6n0380nc.sh` by `raw/mk-s6n0380nc.py`; extract `raw/runs/NC1-extract.txt`): S6N route,
  RT on, the route's save copy, 300 s. Switches: `BC5_0380_REC=1 BC5_0380_REC_SELFTEST_S=150
  BC5_DIRECT_PIECES_NO_CLEAR=1 BC5_DIRECT_ZERO_SKIP=<the list>`, each checked in the emulator's environment.
  - **Pass:** no crash, kernel or TIMEOUT line, no devcoredump, launcher exit 0, and no RT-off line, so RT was on.
  - **Frame rate:** 9,573 flips in 299 s (32.0/s; RC1 had 33.2/s). From 160 s on, NC1 ran 352–393 flips per 10 s
    against RC1's 366–410, a mean 5 % lower. That is one run each, and the cause is not attributed: it could be the
    skip, the missing `CLEAR_STATE` or noise.
  - **The skip is active.** It placed 934 MiB of RenderGpuWcLarge and 284 MiB of CommitIABufferAllocator. 824 MiB
    were still skipped at the end: 193 chunks were taken back by hints, and one canary hit took back 8 MiB, a possible
    one-frame glitch. 10,504 MiB pinned.
  - **The recorder is active.** The self-test at 150 s scanned 10,526.7 MiB resident in 8.79 s and wrote its file
    (14,933 bytes) in 8.88 s.
  - **NO_CLEAR has no line of its own.** It is confirmed by the emulator's environment. Its effect would show in a
    hang's timeout dump as a dword 0 that is no longer `CONTEXT_CONTROL`.
  - **Menu:** shots at 80, 86, 87.5, 89 and 200 s are in `~/bc5-data/captures/exp0380nc/shots/` (private). The save
    list (86 s) and the Continue menu (87.5 s) look normal: every element's panel, text and highlight is drawn, with
    none of F204's transparent rectangles. The laptop's viewing copies were deleted.
  - **The live saves** read 2d7b7a1575dcad6d before and after. That is the maintainer's state after his 21:33 play;
    the earlier a92fe099 reference changed with that play.
- **What the maintainer's play will test:** whether sub-class B comes without the prefix's `CLEAR_STATE` (F603).
  About 3 h without B gives p ≈ 0.05, and one B refutes it. A B event is recorded by part A, the timeout probe and
  sampler 0377 as before.

## 23. The noclear play's crash at eboot+0x1b3a36 (F605, F606; the top session's GO, reads only, cut short)

The maintainer's play on "test 0380 noclear" ran from 23:07:25 to 23:15:21 and ended with exit 65. It was not a GPU
hang. Reads only, 23:16–23:2x, lock line `top exp 0380 | reads only: noclear crash 23:15 …`. The session stopped when the
maintainer started the lean shared build; the lock was cleared then, and the claim and done lines are in BOX-QUEUE.
Sources:
- `~/bc5-work/exp0380nc/play/play-20261029-230725.log` (private), its exception report;
- the private text copy `~/bc5-data/priv/eboot-text-900000000.bin`. Its bytes at 0x1b3a26–0x1b3a55 are the crash
  report's code bytes. The disassembly (`objdump -D -b binary -m i386:x86-64`) is in
  `~/bc5-data/priv/exp0380nc/f1b3a36.dis` (private).

**The faulting instruction and its function (F605).**
- At 0x1b3a36 the title loads a dword through `r14 + rcx*2` (`vmovd`). r14 = 0 and rcx = 0, so it reads address 0
  (`access_violation_vaddr` 0, read). The `lea` just before it left r8 = 0, which agrees.
- **What the function does.** It converts interleaved 16-bit samples into 32-bit floats: sign extend, convert, then
  scale by a broadcast constant. It writes them through a table of per-channel output pointers (r11).
  - The strides are multiples of r10 = 4 (r12 = 0x10, rsi = 0xc, rdi = 0x18, eax = 0x14, r13 = 0x1c, r15 = 8), so the
    frame has 4 channels.
  - A caller (stack frame 0, 0x1b315f) picks it from a function table indexed by format (`call *(%rax,%r8,8)`).
- **Where the null comes from.** The function builds r14 from an offset plus the first qword of a descriptor its
  caller passes in: `add (%rdi),%r14` at 0x1b3848. That pointer was null: a sample-buffer descriptor with no buffer.
  - The descriptor is CPU data, handed down a call chain of the title's own code (stack frames 0x1d58a6, 0x1d23df,
    0x19fe14, 0x1a1a69, …).
  - The crash report's last lines name the ATRAC9 decoder (AJM codec 1). The thread was audio's, not a render
    thread.
- **The site is new.** None of these addresses (the fault and frames 0–3) appears in any other play log on the box,
  nor in the repo's history.
- **What the session could not read before the maintainer started playing:** the log's last two minutes, the gc
  journal around 23:15 (TIMEOUT, faults, canary hits) and the memory record. Those three reads remain.

**Which piece could cause it (F606).**
- **(a) `BC5_DIRECT_PIECES_NO_CLEAR`: no plausible path.** It changes only what the host puts in front of drawing
  dcbs on the GFX ring. The null is a CPU audio descriptor's buffer pointer, in a sample conversion that reads no GPU
  output.
- **(b) The zero skip: no plausible path either.** It decides which chunks of two GPU heaps, RenderGpuWcLarge and
  CommitIABufferAllocator, are imported for the GPU; the CPU's view of them is unchanged (exp 0379). The CPU-only
  audio heaps (Wwise, SoundAlloc) are lazy and never in the list. A canary hit concerns GPU accesses only.
  - Not checked, because of the cut-short read: whether the descriptor's address lies in a listed chunk. The
    address was not in the registers at the fault.
- **(c) A rare title-side or host audio path, the most likely.** It is a null source buffer in the title's sample
  conversion right after an ATRAC9 decode. Ruling out (a) and (b) is medium confidence, from the code path only. The
  same site again on another binary would settle it.
- **Recommendation for the next play: drop exp 0379's skip and keep NO_CLEAR.** NO_CLEAR is the variable under test,
  and the skip is only comfort. Of the two, the skip is the one that changes which memory exists for whom, while
  NO_CLEAR has no route to a CPU pointer.
  - That is the rec binary b8561eaa, which already holds the `BC5_DIRECT_PIECES_NO_CLEAR` switch, with one launcher
    line set: no build.
  - The cost is the 21:33 play's memory pressure (F602).
  - If the crash comes again without the skip, it is (c) or NO_CLEAR. If it never comes, the skip stays suspect.

**The maintainer's notes on the same play (F607; laptop only, after the top session withdrew the GO for his lean
play).** In translation: "The game was more stable, but there was no fight. During an in-game animation the picture
slowed down and fell behind while the sound ran correctly. When the animation ended, the picture caught up with the
rest of the game at its own pace."
- **The cutscene lag matches the known slow motion, by description.** F259 describes the second title's cutscene
  slow motion as its cinematic clock stopping while the rest of the sound plays on. That clock is Wwise's play
  position of a silent 10-s looping voice. The characters slewed to it crawl, then recover. F267 adds that the voice
  stalls when its next streamed read comes late, under swap storms or a late APR queue. F302 had it gone on one route,
  "not from every session". The maintainer's words fit this exactly: the picture behind the sound, then catching up.
- **What would show NO_CLEAR made it worse is not read:** the play's flips/s and frame gaps in that stretch, its memory
  record, and the journal's clock-voice reads. NO_CLEAR changes no audio or APR path. A worse lag would have to come
  through frame time, which F302 already excludes as the cause.
- **"More stable" is not yet measured.** The 23:07 memory record (memavail, swap, PSI, mount reads) against the 21:33
  one (F602) is unread.
- **A lead for the crash.** The faulting conversion handles a 4-channel frame (F605). The title's Wwise archives hold
  exactly eight ATRAC9 streams with 4 channels (`fe 7a 17 e0`, "4.0 audio", F300), against 1,193 haptic streams of 1
  or 2 channels. The host's regular ATRAC9 path, not exp 0243's vibration decoder, decodes those 4.0 streams. The crash
  report names the ATRAC9 decoder.
  - A rarely played 4.0 stream, such as one cutscene's, would explain a new and rare site with a null sample buffer,
    with nothing from either new piece.
  - TODO(verify): which stream the AJM decoded last, and whether the crash fell inside the cutscene. This needs the
    log's last two minutes (AJM lines, the fps counter) and the journal.
- **Pending box reads after his play, on a new GO:**
  1. the 23:07 memory record against 21:33;
  2. the log's fps counter around the cutscene, and the time from its end to 23:15:21;
  3. the AJM lines and the gc journal at 23:15.

## 24. Codex review REVIEW-01: the recorder's event matching, the prefix boundary, and F604's two factors (F608, F609)

Codex reviewed this experiment independently (`REVIEW-01`, outside the repo; relayed by the top session, which
accepted its three points). Laptop only, no box access: the maintainer was playing on the lean build.

**R1, the recorder's event matching (F608).** `rec0380.inc` took the newest `event-*/summary.txt` of the last 30 s,
from any ring, and stopped at the first parsable compute line. A stale event, or another ring's, could therefore stand
in for the current timeout. Changed in `raw/rec0380.inc` (with `raw/mk-rec0380.py`):
- **The ring.** An event counts only if its directory names the ring right after the time stamp
  (`event-YYYYMMDD-HHMMSS-<ring>`, then the end or `-`). The ring is `BC5_0380_REC_RING`, default `gfx_0.0.0`, the
  ring both kinds of job run on here.
- **The time.** Its `summary.txt` must be written after the timed-out job was queued, less 1 s of slack. It is
  compared in nanoseconds. The callers pass the job's age:
  - the asynchronous path from `SoftCp::now_ns() - j.queued_ns`;
  - the synchronous path from `r.submit_ms`.
- **Several matches** must agree on the program and the dims. Otherwise the dims are "unknown: N events … disagree".
- **No match** within `BC5_0380_REC_WAIT_S` (default 8 s) gives "unknown: no event of <ring> newer than the job …".
- With unknown dims nothing is scanned. The dumps of the buffer's bases and arguments are still written.
- **Tests added to `raw/rec0380_test.cpp`, not yet compiled:** there is no C++ compiler on the laptop, so they need the
  box's container (a box check on a GO). The cases:
  - no event;
  - only a 20-s-old event;
  - another ring's event, and a ring name that merely starts with `gfx_0.0.0`;
  - two events in the same second that disagree (unknown) and that agree (taken);
  - an old event with other dims while the right one arrives during the wait.

  The existing timeout case now passes the job's age.
- The box binaries b8561eaa and 99d91d2d still carry the old matching. Rebuilding waits for a GO. Until then a
  recorder file from them names the event it used, so a reader can check that event's ring and time by hand.

**R2, the prefix boundary in `shape0380.py` (F608).** The F601 version ended the prefix at the first
`SET_UCONFIG_REG` 0x261. But `emit_prefix` replays every stored register before its packet state, so a stored 0x261
would end the prefix too early and count our `SET_BASE` as the title's. Codex's synthetic case has the true boundary at
21; the script said 8, with shapeB 0. `DRAWS` also counted `DISPATCH_DIRECT` (0x15) as a draw.
- **The fix** (`raw/shape0380.py`). The tail starts at the first packet-state packet (`SET_BASE`, `INDEX_BASE`,
  `INDEX_BUFFER_SIZE`, `INDEX_TYPE`, `NUM_INSTANCES`, in `emit_prefix`'s order). It continues through
  `tf_ring_prefix`'s single-register packets 0x260, 0x24e, 0x250 and 0x261, in order. A tail without TF registers is
  flagged `amb=1`. `DRAWS` no longer holds either dispatch.
- **Tests:** `raw/test_shape0380.py`, 5 of 5 pass on the laptop:
  - Codex's two counterexamples (boundary 21, shapeB 1; `DISPATCH_DIRECT` alone gives draws=0);
  - the B dumps' layout;
  - a title that opens with its own `SET_BASE`;
  - a tail with no TF registers (ambiguous).

  Codex's `test_review01_shape.py` asserted the old wrong output, so it now fails as intended.
- **Can the real dumps hit it? Not this set.** The tracker's register file holds only what the title's own buffers set,
  because the host's prefix is never applied to it. And a stored 0x261 would show in the F601 output:
  - In all 43 prefixed dumps, the old rule's boundary was dword 1269. That is exactly the tail's length after the
    prefix's `SET_BASE` at 1249: `SET_BASE` 4, `INDEX_BASE` 3, `INDEX_BUFFER_SIZE` 2, `NUM_INSTANCES` 2, and three TF
    packets of 3 dwords each (`raw/runs/SHAPE-timeout-dumps.txt`).
  - Had the replay held a 0x261, the boundary would have fallen before 1249, and the title's first `SET_BASE` would
    read 1249. In all 43 it is 1323 or later.
  - The draws column was not part of the shape test.
  - So F601's counts stand. The re-run is still owed (below).
- **Box re-check for the next GO:** run the corrected script over the same 53 timeout dumps and 1,987 healthy dumps.
  Expect `title_at=1269 amb=0` in every prefixed dump, and the same counts: 5 shape-B dumps of 43 prefixed, 0 SET_BASE
  in a COND_EXEC.

**R3, F604's test changes two factors at once (F609).** Against the rec play, the noclear launcher turns on both
`BC5_DIRECT_PIECES_NO_CLEAR` and the zero skip, on a new binary. So its outcome cannot be put on `CLEAR_STATE` alone.
`BC5_DIRECT_PIECES_NO_CLEAR` also drops the prefix's first five dwords, `CONTEXT_CONTROL` and `CLEAR_STATE` together
(`prefix_of`, patch line 32246). Even a clean run would not separate those two packets.
- A causal reading needs a control with the same binary, list and settings and NO_CLEAR off. Or, F606's
  recommendation: drop the skip so that NO_CLEAR is the one change against the rec play.
- No source ties `CLEAR_STATE` to the CP's argument fetch on gfx1013. F603 stays a hypothesis, not a mechanism. The
  design of the next test is the top session's and the maintainer's.

## 25. The night's crash work: the 23:15 and 23:30 exits (F610; the top session's night GO)

The maintainer approved the night's work: "Tak. Do rana działajcie sami z codexem" (yes; until morning, work on your
own with Codex). Box session from 23:33, lock lines `top exp 0380 | night: …`, claim in BOX-QUEUE.
- **Live saves:** 377a8d456a9b4cb1 at the start. That is the maintainer's state after the lean play's 23:30:00
  autosave.
- **Kernel stream:** `raw/runs/CR-kernel-stream.txt`.

**What the reads show.**
- **The lean crash at 23:30:10 cannot be placed.**
  - The user journal has only the shortcut's unit: `status=65/DATAERR`, 12 min 10 s wall clock.
  - Exit 65 is what the emulator's guest exception handler returns, as at 23:15. coredumpctl has no entry, because
    the handler exits rather than dumping. The lean build writes no log, and nothing else was written between 23:18
    and 23:32 except the saves.
  - Its slot-4 autosave came 10 s before.
  - So both crashes are guest exceptions. The lean one ran with neither NO_CLEAR nor the zero skip. If the two are
    one crash, neither piece causes it. One or the other may still be a different fault.
- **F607's ATRAC9 lead is withdrawn.**
  - The "AJM codec=1, name=ATRAC9 decoder" line after the 23:15 register dump is a buffered-stdout artefact.
    `AjmLogCodecSupport` (KytyPlus `src/libs/ajm.cpp:384-388`) prints it with `printf` once, at the first supported
    instance, and stdout was flushed at exit, after the stderr crash lines.
  - The 4-channel reading of F605 stands. The loads take elements e, e+4, …, e+28 of an interleaved int16 source with
    a stride of r10 = 4, and the output pointers sit 0x800 apart on the stack.
  - But 4-channel streams are common in this title: Opus music stems at 7.999 bytes per 4-channel sample (F241)
    besides the eight ATRAC9 4.0 streams. So the channel count does not point at ATRAC9.
- **The source of the null, one frame further up.**
  - Frame 1 (0x1d58a1) passes the descriptor from a saved local (`-0x40(%rbp)`). The other argument is `r14 + 0x10`
    of a voice-like object: it has a format word at +0x92, a sub-object at +0xe8 with counters at +0x29c/+0x2a2, and
    a flag byte at +0xf2.
  - The registers at the fault no longer hold either pointer, so the descriptor cannot be recovered from this report.
- **The 23:07 play's own records** (`exp0380nc/play/mem-…-230725.txt`, the log's fps lines, the gc journal; private):
  - **Memory, minutes 2–8:** memavail 730–1,020 MB against 21:33's 470–555 MB; PSI memory full ≤ 0.58 % against
    ≤ 1.18 %; swap about 830 MB against 560–920 MB. So it was "more stable" in memory, as the skip should make it.
    The play ended at minute 8, before 21:33's minute-16 collapse.
  - **Frames:** 12.8–31.4 flips/s per minute; from t 380 s to the crash at t 473 s, 9–54 flips/s with gaps up to
    197 ms. That is not the multi-second stall of the old slow motion, but the scene differs from 21:33's, so it is no
    comparison. The cutscene's place cannot be found in these records. Whether the crash fell in it stays open.
  - **The gc journal:** no TIMEOUT, no given-up wait. The zero skip had 3 canary hits and took back 67 chunks on CPU
    writes, with 562 MiB still skipped at 23:15.
- **Reproduction attempt CR1** (`raw/s6n0380cr.sh` by `raw/mk-s6n0380cr.py`; the shared normal build 58c4a627, only
  read):
  - **Setup:** a private copy of the live saves (377a8d45) and the slot-4 route (`raw/slot4.cmd`: ✕, down ×3, ✕, ✕
    at 85 s), RT on, 420 s.
  - **Result: pass, no exception.** The game loaded the 23:30 autosave into the city at night (a private shot at 200 s)
    and stood there with no input: 27.1 flips/s, 0 crash, kernel or TIMEOUT lines, live saves unchanged.
  - The lean crash came 10 s after that autosave, while the maintainer was playing. An idle run of the same spot
    does not reach it.

**State of priority 1: no confirmed cause and no fix candidate.**
- The fault is a null source buffer in the title's 4-channel int16 → float conversion. One crash is on our test
  binary and one, unplaced, on the shared lean build.
- A switch to fix it cannot be written before the descriptor's owner is known. A guard in the title's code path
  would hide the symptom, not cure it.
- **The cheapest way to the cause:** a crash-context dump, host side and CPU only, default off. On a guest
  exception it would print 32 qwords below every saved rbp of the stack walk and 8 qwords at each pointer found
  there. The descriptor (frame 1's `-0x40(%rbp)`) and the voice object would then be in the next crash's log.
  - It lives in `runtimeLinker.cpp`'s handler, a second unit beside `bc5LleAgc.cpp`.
  - It can ride along in priority 2's rebuild of the test binary, so that the maintainer's morning play records it.

**Priority 2: the rebuilt test binary (F611; the same night session, 23:4x–23:58).**
- **The recorder's tests** (`raw/rec0380_test.cpp` with F608's matching) pass on the box: g++ `-std=c++20 -O2 -Wall
  -Wextra -Werror` in the container, every check including the six new event cases (`raw/runs/R1-rec0380_test-out.txt`).
- **The crash-context dump.** `raw/mk-crash0380.py` makes one counted edit to the tree's
  `src/loader/runtimeLinker.cpp` (96e03695 → 5f2bc982). With `BC5_CRASH_FRAMES=1` (default off), after an access
  violation's stack trace, the handler walks the saved-rbp chain, up to 8 frames, and for each frame prints:
  - the 0x110 bytes from rbp−0x100: the frame's locals and the callee-saved registers its callee pushed;
  - 8 qwords at each aligned, readable address in that window, at most 24 a frame.

  All reads go through the handler's own `IsReadableRange`, and nothing is written. The top session approved it for
  the private binary only.
- **The build** (`raw/build0380r1.sh`; `raw/build0380y.py` is `build0380x.py` for several units):
  - `bc5LleAgc.cpp` (exp 0379's unit plus the F608 recorder, c46144c4) and the private `runtimeLinker.cpp` are
    compiled with the shared build's own commands and linked with the shared objects and archive.
  - **Binary** `~/bc5-work/exp0380r1/bin/kyty_emulator`, **md5 44417414**.
  - 7 warnings, all pre-existing: the unit's five, the deprecated `wstring_convert` in `stringUtils.h`, and a lambda
    at `runtimeLinker.cpp:889`, before the edit.
  - The shared pins are unchanged before and after.
- **The launcher** `exp0380r1/play-pkg-0380r1.sh` (299a2519) is made by `raw/mkplay0380r1.py` from the noclear one,
  diff in `raw/play-pkg-0380r1-vs-nc.diff`. The switches are as before (NO_CLEAR, the zero skip on the same list
  7a4f972c, the recorder) plus `BC5_CRASH_FRAMES=1`.
- **Smoke RS1** (`raw/s6n0380r1.sh`: `mk-s6n0380nc.py`'s output for this binary, with its paths and lock text changed
  by sed; route save copy, RT on, 300 s; `raw/runs/RS1-extract.txt`):
  - **Pass:** no crash, TIMEOUT or kernel line, 30.9 flips/s (NC1 32.0, RC1 33.2), 10,474 MiB pinned.
  - The recorder's self-test ran; the skip placed its list.
  - The crash dump's path is not exercised by a healthy run. It runs for the first time at the next guest exception.
- **The shortcut.** "BC5 emulator (test 0380 noclear)" now starts `exp0380r1/play-pkg-0380r1.sh` (b4a986df,
  `raw/r1/`). The previous file is kept in `~/bc5-work/exp0380nc/retired/`. The live saves read 377a8d456a9b4cb1
  before and after.

**Codex's AUDIO-01 and the Opus path (F612).** Codex read the host's ATRAC9 path independently (`AUDIO-01`, outside
the repo; KytyPlus f266548 plus main's patch 0001).
- **Its verdict agrees with F610.** The 4-channel ATRAC9 path has no fixed stereo buffer: `m_pcm_buffer` is sized
  from the codec's channels. The wrapper hands the guest no pointer of the host's own, so no host path is shown to
  create the null sample buffer.
- **It found two host defects, neither tied to the crash:**
  - ATRAC9 `Reset` (`atrac9_decoder.h:89-103`) frees the handle. If the new `Atrac9GetHandle` returns null,
    `m_is_initialized` stays true, so a later decode can pass a null handle. Its CPU probe shows the state.
  - `AjmDecodeSplitInstance` (`ajm.cpp:620-660`) skips a null output entry's copy but still counts its bytes in
    `output_written`, which hides a bad descriptor.
  - A third point, a lifetime gap after the instance mutex is released, needs a concurrent destroy.
- **The Opus decoder does not share the Reset defect** (`src/libs/ajm/opus_decoder.h:79-100, 213-275`, read on the
  box). `Release()` clears `m_decoder_ok`, `OpenDecoder()` sets it only on success, and `Decode` returns
  `CODEC_ERROR|FATAL` while it is false. An Opus voice whose decoder cannot be recreated gets an error, not a null
  handle.
- **To bring Codex's correlation data to the next crash:**
  - the AJM instance, its reset and initialize history;
  - the format, `output_written` and the buffer addresses of the last job.

  That would need an AJM trace in the private binary. The crash frames come first.

## 26. The next F403 test, one factor per arm (F613; a proposal, nothing built)

Codex's R3 (F609) asks for arms that each differ from a control on one factor only. The maintainer decides in the
morning.

**The arms, all on binary 44417414** (shared objects and archive; exp 0379's unit, the F608 recorder, crash frames),
RT on, `BC5_CRASH_FRAMES=1` and `BC5_0380_REC=1` in each:

| Arm | Zero skip | Prefix | Changes against (a) | Needs |
|---|---|---|---|---|
| (a) control | on | full (`CONTEXT_CONTROL` + `CLEAR_STATE`) | — | a launcher line (`BC5_DIRECT_PIECES_NO_CLEAR` unset) |
| (b) noclear | on | neither | both packets | nothing: today's shortcut |
| (c) no CLEAR_STATE | on | `CONTEXT_CONTROL` kept | `CLEAR_STATE` only | a code change, below |

- **(c) needs a code change.** `prefix_of` erases the prefix's first five dwords as one block (patch 0001 lines
  32244–32248): `CONTEXT_CONTROL` (3 dwords), then `CLEAR_STATE` (2). Dropping only `CLEAR_STATE` means erasing dwords
  3–4 instead, for example with `BC5_DIRECT_PIECES_NO_CLEAR=state`.
  - It is a two-line edit in the private `bc5LleAgc.cpp`, plus a rebuild (≈ 1 min) and a smoke run (≈ 6 min). It
    touches no shared build.
  - The reverse arm, `CLEAR_STATE` kept with `CONTEXT_CONTROL` dropped, is the fourth combination. It adds little
    unless (b) shows an effect.

**How long, at about one B event per hour of RT-on play.** B came about once an hour in RT-on play (§7; 18:15,
23:36, 09:48, 12:12, 14:04). Assume a Poisson rate λ = 1/h. "Play" means RT-on gameplay, not menus.
- **One arm alone (b or c), as a refutation test.** A single B with the arm on refutes its packet(s) as the trigger,
  at once. A clean arm says little until long: P(no B in T h | λ = 1) = e^−T, which is 0.37 after 1 h, 0.14 after 2 h
  and 0.05 after 3 h. So **3 h without B** is the least for "this arm changes the rate".
- **The control is needed for a clean answer.** The skip changes memory pressure, and so the timing that B may depend
  on. A clean (b) on its own could be the skip's doing. A control (a) on the same binary must show that B still comes
  at about 1/h with the skip on.
  - With equal play in (a) and (b), and every B in (a), the chance of that split under "no difference" is 0.5^n.
  - n = 4 B in (a) gives 0.06, n = 5 gives 0.03. At λ = 1/h that is **about 5 h of (a) and 5 h of (b)**.
  - Cheaper and sequential: (b) first for 3 h. If B comes, the arm is refuted and (a) is not needed. If none comes,
    then (a) until 3 B (about 3 h). This answers "is the skip alone enough?" too.
- **Is (b) alone still worth it?** Yes, as the cheapest refutation. One B in the next hours of (b) removes the whole
  prefix-reset hypothesis (F603) for both packets at once, without building anything. A clean (b) is not a result
  without (a). The rec and wb plays without B (22 and 37 min) are too short to stand in for a control (p ≈ 0.7 and
  0.5).
- **(c) is worth building only if (b) stays clean for 3 h.** Before then, it would split a hypothesis that may
  already be refuted.
- **What every arm also records:** the crash frames at any guest exception (F610, F611), and part A at any fence
  timeout. Any arm's play also tests the CPU crashes.

## Result

- Sources read and cited (F545, F546). The title-side evidence was re-read from exps 0376/0378 (F547).
- The guard is built, default off, with unit tests passing on the laptop (F548).
- A second guard, `FORCE_START_AT_000` on indirect dispatches, is built the same way: default off, with unit tests
  (F551).
- The box plan is written. Only step A0 ran: a CPU-only compile check, which passed (F552). Nothing ran on the GPU.
- "test 0380 noclear" now runs binary 44417414: the recorder with F608's event matching (its tests pass on the box)
  and a crash-context dump, `BC5_CRASH_FRAMES`, so the next guest exception names its frames' locals. Smoke RS1
  passed. Codex's AUDIO-01 agrees that no host path is shown to make the null; the Opus decoder has no ATRAC9-style
  Reset defect (F611, F612).
- The two CPU crashes are both guest exceptions (exit 65). The lean one (23:30:10) had neither NO_CLEAR nor the skip
  and cannot be placed, and an idle run from its autosave did not crash. F607's ATRAC9 lead was a stdout artefact.
  There is no cause and no fix yet. A crash-context dump in the next test binary is the proposed way to the
  descriptor's owner (F610).
- Codex's review REVIEW-01 led to two fixes. The recorder now takes only a sampler event of its own ring that is newer
  than the timed-out job, else "unknown"; its tests are written and not yet compiled, and the box binaries keep the old
  matching until a rebuild. `shape0380.py` now finds the prefix boundary from `emit_prefix`'s tail; F601's counts
  stand on the real dumps, with a re-run owed. F604's test changes two factors at once, NO_CLEAR (itself both
  `CONTEXT_CONTROL` and `CLEAR_STATE`) and the skip (F608, F609).
- The noclear play crashed after 8 min at a new CPU site, eboot+0x1b3a36. It reads through a null sample-buffer
  pointer in the title's 4-channel int16 → float conversion, right after an ATRAC9 decode. Neither NO_CLEAR nor the
  zero skip has a plausible path to it (medium). The next play should drop the skip and keep NO_CLEAR (F605, F606).
- The test shortcut "test 0380 noclear" is installed and "test 0380 rec" is retired. Binary 99d91d2d = recorder part A +
  exp 0379's zero skip; it runs `BC5_DIRECT_PIECES_NO_CLEAR=1` with RT on. Its smoke run passed at a 5 % lower
  frame rate than RC1 (one run each), and the menus look normal (F604).
- Every recorded sub-class B event (5 of 5) is the first indirect dispatch right after our full-state prefix, in a dcb
  with no `SET_BASE` of its own. No recorded stream has a `SET_BASE` inside a `COND_EXEC`. The shape is probably
  common in healthy play, so it is context, not a trigger. A `CLEAR_STATE`-less prefix test is proposed. The
  21:33 play's instability was memory reclaim from minute 16 (GTT +1.27 GB, PSI up to 16 %); the recorder cost
  nothing (F601–F603).
- The maintainer's hypothesis, a `SET_BASE` tracked inside a skipped conditional block, is refuted as the cause of the garbage
  dims: in every B event, our check and the CP's fetch use the same `SET_BASE`. That `SET_BASE` is our own full-state
  prefix's, not the title's. The trackers' blindness to `COND_EXEC` is a real, latent defect, and how often the title
  triggers it is not counted (F598–F600).
- Part A of the flight recorder is built (binary b8561eaa), the smoke run passed with no visible overhead, and its
  dump path wrote and fsynced 11.3 GiB's scan in 9 s. The shortcut "BC5 emulator (test 0380 rec)" is installed for the
  maintainer's play, and "test 0380 wb" is retired. No rule maps the two B events' slot or `INDEX_BASE` to one
  candidate address. Between `INDEX_BASE` and the dispatch, both reprogram the TF ring (F595, F596).
- The garbage dims match no PM4, address, IB dword or argument of ours, and cannot be stale arguments of their
  fixed slots, so the CP fetched dwords from elsewhere (medium). C1/W1's triple is shader code from the arguments'
  own heap, a shown wrong-address read. The records cannot say which address it was for the title's events. A
  host-only probe extension (part A, no GPU change) and a register-readback ring (part B) are designed, not built.
  The scripted bench route has shown no B event in 35 min (p ≈ 0.004–0.03 at the play's rate) (F590–F594).
- The maintainer's 36.6-minute play with the GL2 write-back on (`test 0380 wb`, start 2) had no F403, against today's
  rate of about one per 7–10 min (p ≈ 0.005–0.03 if unchanged). Start 1's recovered start-up fault is unrelated to the
  write-back (F582–F584).
- The audit of our libraries and filter found no rewrite of ours between the stuck dispatch and its IB's start (F577,
  F578). The strongest remaining host-side lead is that requested memory types never reach the GPU mapping (F579).
- The GL2 write-back alone (`ARGS_WB=first`) passed W2 and W3 at bench frame rates. Its play-test shortcut is staged,
  not installed. The copy slot now sits at a low VA, built but not run (F574–F576).
- W1 (copy + write-back) hung like C1, with identical garbage from a different slot address. The copy runs
  tested the slot's high VA, not coherence, and F569's GL2 reading is withdrawn (F571–F573).
- The argument copy hung the bench within 7 s (C1): the fetch returned other data than the ME had just written and
  the check had read, at the same address. That points to the fetch missing GL2-resident writes. A GL2 write-back
  before the fetch (`BC5_DIRECT_ARGS_WB`) is built, default off, not run (F568–F570).
- The maintainer's play with that shortcut hung at 14:04 in sub-class B, with the rebase `SET_BASE` executed right
  before the stuck dispatch. **The rebase is refuted as a fix** (F564, F565). The next candidate, the CP's own
  argument copy, is built, default off, and not run (F566, F567).
- The maintainer's test shortcut "BC5 emulator (test 0380 fix + 0379)" is on the desktop (binary c442f6c7,
  launcher 05762c4e), and its 5-min smoke run passed (F563).
- The rebase fix ran twice on the bench (RT on, 600 s each): both runs pass at 37.5 and 36.5 flips/s, with ~174,000
  first-after-`INDEX_BASE` dispatches rebased. It is safe, but untested against the hang itself (F561, F562).
- Two sub-classes. B (the four events since 10-28 18:15) is consistent with "the first indirect dispatch after
  `INDEX_BASE`" (F558). The rebase fix candidate is built, default off, and staged as a launcher, not run (F559,
  F560).
- The 12:12 hang names the class's dispatch and grid (F553). It is not skip-induced on the evidence (F554), and the
  CP fetched other arguments than memory held (F555). A y/z limit is built, default off (F556).

## Verdict so far

*Updated after the maintainer's 16:25 play (F582–F584).* The GL2 write-back before the first indirect dispatch after an
`INDEX_BASE` (`BC5_DIRECT_ARGS_WB=first`) is the first change with evidence against sub-class B. It ran 36.6 minutes of
RT-on play without F403, p ≈ 0.005–0.03 if the rate were unchanged. One more long play is needed to call it a fix.

*Updated after the 12:12 hang (F553–F557).* H0380 (zero dimension) is **refuted** for the event that names its dispatch:
it launched 65,536 × 196,610 × 2,752,552 groups. The class is a runaway grid whose arguments, as fetched by the CP,
are not what memory holds (H0380b, medium). The original text follows.

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
