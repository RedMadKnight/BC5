# 0361 — the job-arena fix into the shared builds

The top session, 2026-10-28, on the maintainer's "Tak, wbuduj". That came after his 514-s play through the fight on
exp 0359's test shortcut (F457). Box work under the BOX-LOCK, claimed in `~/bc5-work/BOX-QUEUE` and
`~/bc5-work/exp0361/CLAIM.txt`.

**Question.** Does exactly what the test binary 89b95e4e was built from integrate into both shared builds (normal and
lean)? That is exp 0359's job-arena fix, a temporary game-code workaround, switchable per title and on by default for
PPSA03671. And does the integrated normal build pass the S6N regression with RT on?

**Setup.**
- `int0361.sh`, after exp 0350's `int0350.sh`. It refuses to start unless every input has its expected md5:
  - the shared binaries: normal affa0c22, lean cd7ea936; the archive bb50b2e0;
  - the host tree's diff against f266548 equal to main's patch 0001 (6ac6cc16);
  - each of the six host files that exp 0359 patched, checked as the original (gamePatch.cpp/.h, runtimeLinker.cpp,
    hostInput.cpp/.h, hostMenu.cpp), and its patched copy in `~/bc5-work/exp0359/src`, checked as the one built into
    89b95e4e;
  - the new `src/bc5/job_arena_fix.hpp` (22a78051);
  - the three backend files from main: `backend/include/bc5/job_arena_fix.hpp`, `backend/tests/job_arena_fix_test.cpp`,
    and `backend/CMakeLists.txt` with only that test added. Exp 0352's batched-check test stays on its branch.

  Then:
  1. the seven host files go into `~/src/KytyPlus`;
  2. the three backend files go into `~/src/bc5/backend`; the fix is header-only, so the archive is not rebuilt;
  3. both emulators are rebuilt with ninja;
  4. the tree's diff is written out as the candidate patch 0001 (D19).

  `play-pkg.sh` and `input.cfg` are not touched: with `JobArenaFix.PPSA03671` unset, the fix is on for that title.
  Backups and the undo are in `~/bc5-work/exp0361/integration/`.
- `s6n0361.sh` is `s6n0350.sh` with 0350 → 0361 (the same launcher derivation, the same required environment).
  R1: S6N, RT on, 600 s, through the integrated launcher, with the kernel stream to the laptop.

**Result.**
- **The integration** (`raw/int0361.out`), 16:03–16:04:
  - Every input check passed.
  - Seven units recompiled in each build, 6 warnings each (the tree's own).
  - normal affa0c22 → **1000ad2a**; lean cd7ea936 → **23e233f7**.
  - The archive is unchanged (bb50b2e0).
  - Both binaries carry the "job-arena fix APPLIED" line, the menu item and the `JobArenaFix` key.
  - The candidate patch 0001 is **2db34349** (59,057 lines), and the new header is in it. It is now main's
    `backend/kytyplus-patches/0001-bc5-lle-agc.patch`, together with the three backend files, so main matches the
    shared builds (D19, Q19).
- **R1** (S6N, RT on, 600 s, the integrated launcher 55531ab6), 16:04 → **pass**:
  - 36.3 flips/s (0350's R2b 35.8, 0358's R1 37.2);
  - no crash, kernel, TIMEOUT or compute-ring line; live saves unchanged (41a5a36fffb4f8d4);
  - the start log: `job-arena fix ON for PPSA03671 (not set, on for that title)`, then `APPLIED`;
  - the hook wrapped 58,000 owner calls on the route;
  - no job was cut on this run.

**Verdict.** Integrated. Both shared builds carry the job-arena fix, on by default for the second title and switchable
from the Emulation menu ("Game fixes → Job-arena fix (temporary, next start)"). It is a temporary game-code workaround,
to be removed when the host's throughput at the fight is fixed (HANDOFF Q24, exp 0360).
