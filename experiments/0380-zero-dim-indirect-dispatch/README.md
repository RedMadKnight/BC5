# 0380 — Is the F403 class a zero-dimension indirect dispatch? (sources, title side, a guard, a box plan)

**Date.** 2026-10-29. **Laptop only.** No box access and no GPU submission in this experiment. Branch
`exp/0380-zero-dim-dispatch`. Findings F545–F584 (exp 0379 holds F540–F544). One box session, CPU only (step A0, 11:28–11:31, on the top
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
- If it holds, F569's "the fetch misses GL2-resident writes" becomes the working explanation for sub-class B. It was
  withdrawn because the copy runs did not test it; the write-back result now supports it directly.

## Result

- Sources read and cited (F545, F546). The title-side evidence was re-read from exps 0376/0378 (F547).
- The guard is built, default off, with unit tests passing on the laptop (F548).
- A second guard, `FORCE_START_AT_000` on indirect dispatches, is built the same way: default off, with unit tests
  (F551).
- The box plan is written. Only step A0 ran: a CPU-only compile check, which passed (F552). Nothing ran on the GPU.
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
