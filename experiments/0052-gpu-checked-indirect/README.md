# 0052 — indirect dispatch arguments checked by the CP when it runs the dispatch

**Question.** Experiment 0050 found that the second title's tree refit hangs because the dispatches
that build the trees' leaf lists are dropped by the host: it reads their arguments at submit time,
before the GPU has written them, sees ±inf as group counts and drops them. Trusting every argument
built the lists but was unstable. Can the check move to where the arguments are final, the CP at
the moment it runs the dispatch, and does the refit then run?

**Setup.** Kernel 7.2.8-ogc5.1, 512 MiB VRAM carve-out. New in the backend (all off by default):

- `bc5/indirect_check.hpp`, `FilterOptions::gpu_check_indirect`: before every GFX-form
  `DISPATCH_INDIRECT` with a known base (SET_BASE index 1 in the IB, which also covers the host's
  rebuilt compute dispatches), `WRITE_DATA` flag = 1; three `COND_WRITE` (group count x, y, z
  greater than 2^20, 2^10, 2^10 → flag = 0); a `WRITE_DATA` with `WR_CONFIRM`; `PFP_SYNC_ME`;
  `COND_EXEC` on the flag over the dispatch. The flag lives in the job's scratch. The IB's own
  `COND_EXEC` counts grow by what is inserted in their ranges (if one would overflow its 14 bits,
  the IB's indirect dispatches are NOP-ed instead). Packet layouts: RPCSX `rpcsx/gpu/Pipe.cpp`
  `condWrite`/`compare` (e8ae148), Mesa `ac_emit_cp_cond_exec` and `sid.h` (0866ae7). Unit tests:
  `ctest` 35 of 35.
- `direct-selftest --cp-check`: the same sequence on five argument triples, with the dispatch
  replaced by a `WRITE_DATA` (no shader runs), the packets in the unfiltered prologue.

Host (patch 0001): `BC5_DIRECT_GPU_CHECK=1` sets the option and no longer drops a dispatch for
absurd counts read at submit time when the CP will check it; the journal counts both. The refit
guard of 0050 also holds the refit back in a buffer one of whose CPU-side waits was given up.
Runs 222–232, 2026-10-12 02:39–03:40, 300 s each, launcher defaults otherwise. Raw output in `raw/`.

**Result.**

1. **The CP check works on the BC-250** (`raw/cp-check.txt`): the write ran for (44, 1, 1) and
   (2^20, 1024, 1024), and was skipped for (+inf, +inf, +inf), (28800, -inf, 1) and (1, 1, 2000);
   the flag and the confirm word held the expected values.
2. **With the refit skipped it is as stable as before** and the GPU-written dispatches run:

   | Run | Setting | End | fps from 250 s | 3D from |
   |---|---|---|---|---|
   | 222 | check, IBs with COND_EXEC left alone | 300 s, no fault | 18.4 | 70 s |
   | 226 | check, COND_EXEC counts grown | 300 s, no fault | 18.7 | 65 s |
   | 229 | the same | 300 s, 2 recovered faults | 17.9 | 45 s |
   | 230 | the same | stopped at 168 s (heap fault, junk top byte) | — | 70 s |
   | 231 | the same | 300 s, no fault | 18.9 | 70 s |
   | 232 | the same | 300 s, 1 recovered fault | 18.2 | 45 s |

   Per run 2.4–2.6 million dispatches the host would have dropped went to the CP instead. Five of
   six reach 300 s; the stop of 230 is the known one (run 219 had it without the check).
3. **The leaf lists are now built**, but only once the check also covers IBs with their own
   `COND_EXEC` (the graphics-buffer builders of 0050 sit in such IBs). Run 223 (`COND_EXEC` IBs
   left alone): the small tree's lists still empty, the first refit hung; 224 (plus the CP DMA
   wait of 0050) the same. Run 225 (`COND_EXEC` IBs checked): every checked tree complete, the
   refit ran 560,524 times without a failure, the game at 20–22 fps from 65 s to 150 s.
4. **The refit still hangs later**, on trees the CPU check finds complete: run 225 at 152 s and
   repeatedly after, right after a burst of given-up cross-queue waits (226, without the refit,
   had the same burst and ran on); 227 (with the guard: 468,993 refits, none held back) at 150 s
   the same way; 228 (the guard also holding back refits after a given-up wait) at 66 s, with no
   given-up wait at all.

**Verdict.** Partly passed. Arguments checked by the CP replace the host's stale reading safely
(five of six runs reach 300 s, unchanged), and with them the second title builds its trees' leaf
lists: the refit's original hang is gone. The refit itself still hangs on complete trees after
seconds to minutes, for a reason the list check does not see; the launchers keep skipping it, and
`BC5_DIRECT_GPU_CHECK` stays opt-in (D16) until a longer series compares it with the defaults.
