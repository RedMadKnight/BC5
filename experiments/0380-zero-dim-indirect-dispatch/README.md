# 0380 — Is the F403 class a zero-dimension indirect dispatch? (sources, title side, a guard, a box plan)

**Date.** 2026-10-29. **Laptop only.** No box access and no GPU submission in this experiment. Branch
`exp/0380-zero-dim-dispatch`. Findings F545–F562 (exp 0379 holds F540–F544). One box session, CPU only (step A0, 11:28–11:31, on the top
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

## Result

- Sources read and cited (F545, F546). The title-side evidence was re-read from exps 0376/0378 (F547).
- The guard is built, default off, with unit tests passing on the laptop (F548).
- A second guard, `FORCE_START_AT_000` on indirect dispatches, is built the same way: default off, with unit tests
  (F551).
- The box plan is written. Only step A0 ran: a CPU-only compile check, which passed (F552). Nothing ran on the GPU.
- The rebase fix ran twice on the bench (RT on, 600 s each): both runs pass at 37.5 and 36.5 flips/s, with ~174,000
  first-after-`INDEX_BASE` dispatches rebased. It is safe, but untested against the hang itself (F561, F562).
- Two sub-classes. B (the four events since 10-28 18:15) is consistent with "the first indirect dispatch after
  `INDEX_BASE`" (F558). The rebase fix candidate is built, default off, and staged as a launcher, not run (F559,
  F560).
- The 12:12 hang names the class's dispatch and grid (F553). It is not skip-induced on the evidence (F554), and the
  CP fetched other arguments than memory held (F555). A y/z limit is built, default off (F556).

## Verdict so far

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
