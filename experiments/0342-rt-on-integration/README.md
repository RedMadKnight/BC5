# 0342 — RT on in the shared builds: one ring, exp 0341's guards, the overlay's stick dead zone

**Question.** The maintainer's RT-on play on exp 0341's test shortcut ran 46 minutes in two games without a GPU hang,
reset or machine-down (F415). He then said (2026-10-27): "Tak: zintegruj jedną kolejkę, oba zabezpieczenia 0341 i
poprawkę listy języków do obu wspólnych buildów (normal i lean); w input.cfg RT on i polski." So this experiment
asks:
- Do the shared normal and lean builds take exp 0341's backend and the overlay fix, and still build?
- Does the integrated normal build run the S6N route with RT off and with RT on, through the integrated launcher?

**Setup.** `int0342.sh` runs on the box, under the BOX-LOCK, with no emulator running. It does this:
1. **Backend.** Exp 0341's nine backend files (the product staircase, the shadow labels, their switches in the
   `Device`) are copied from `~/bc5-work/exp0341/backend` over the shared checkout `~/src/bc5/backend`. That copy
   is what b052d860 was built from; each file is md5-checked against main, where the files come from branch
   `exp/0300-rt-dispatch-sync` f0fc75d. Then the shared archive `~/bc5-work/backend-ubuntu/libbc5_backend.a` is
   rebuilt.
2. **Host.** `deadzone0342.pl` patches `src/graphics/presentation/settingsOverlay.cpp` in `~/src/KytyPlus`. The
   left stick's analog value now goes to ImGui through the same 0.25 dead zone as its down state, rescaled to 0..1
   beyond it, as imgui_impl_sdl2 maps an axis. Before, ImGui 1.92.9b's gamepad navigation scrolled the focused
   window by the raw value every frame (`NavUpdate`, "Manual scroll with LStick"). So a resting stick's drift
   scrolled the System tab's language list (F415).
3. **Shared builds.** Both shared emulators are rebuilt in place with ninja.
4. **Launcher.** `play-pkg.sh`, the second title's launcher for both normal and lean, gets the lines the test
   launcher played: `BC5_DIRECT_COMPUTE_RING=-1` (one ring, F412) and
   `BC5_DIRECT_GPU_CHECK_PRODUCT=1 BC5_DIRECT_SHADOW_LABELS=1` (F414). ASTRO BOT's launcher is not touched.
5. **input.cfg.** The test's private configuration replaces it. That configuration has `RayTracing.PPSA03671=on`
   and `SystemLanguage=Polish`; the script checks that every other line is equal.
6. **Patch 0001.** The host tree's diff against f266548 is written out as the candidate for
   `backend/kytyplus-patches/0001-bc5-lle-agc.patch` (D19).

Every replaced file, both binaries and the archive are backed up under `~/bc5-work/exp0342/integration/`, and the
undo is printed.

**Run.** `s6n0342.sh <live saves> <tag> [secs] [off|on]` is exp 0341's chain on the integrated normal build,
through a copy of the integrated launcher:
- the private wd and the route's saves (the live saves are compared only);
- one ring and both guards checked in the emulator's environ;
- RT off (the drop line required by 180 s) or RT on (no drop line allowed).

Pass means 600 s with no crash, kernel or TIMEOUT line, and flips against R2 of exp 0341 (36.6/s). The
maintainer's own play on the shortcuts follows.

**Result (2026-10-27).**
- *Integration* (`raw/int0342.out`, 12:25–12:26, exit 0). The archive was rebuilt as 44ba4435 (0 warnings, `shadow_labels.cpp.o` in). Both builds recompiled two objects, `settingsOverlay.cpp` and `bc5LleAgc.cpp` (the latter includes the backend headers), and relinked.
  - New shared builds: normal **ddfb9456** (was 9382b1e9), lean **03337c24** (was 1860613a). Both carry the 0341 switch line.
  - Build warnings: normal 4, lean 7, all old ones in `bc5LleAgc.cpp`/`stringUtils.h`.
  - `play-pkg.sh` is now 5b469087, with one line changed and one added (`raw/integration-play-pkg-0342.diff`). `input.cfg` is now 30dd586e: `RayTracing.PPSA03671=on` and `SystemLanguage=Polish` (`raw/integration-input-cfg-0342.diff`).
  - Patch 0001: the tree's diff before the change was md5 3b7e88b8, equal to main's file, so main matched the old builds. The new diff is 12716e3b, 58,669 lines; it differs from main's only in the overlay hunk and is now on main.
  - The undo is in `raw/int0342.out`.
- *R1, RT off, 600 s:* **pass**. 36.4 flips/s (exp 0341 R2: 36.6); 0 crash, kernel or TIMEOUT lines; `drm-engine-gfx` only; 5,423 RT-off drop lines; live saves dc9d4f25fc2d41ca unchanged.
- *R2, RT on, 600 s:* **HANG at ~106 s, the box recovered.**
  - Kernel at 12:39:19: `ring gfx_0.0.0 timeout` (thread `bc5-ring`), `Ring gfx_0.0.0 reset succeeded`, `device wedged, but no recovery needed`. One devcoredump.
  - The host timed out acb #76004 (2,380 dwords) and dcb #76005 (17,748) after 2.0 s; the timeout probe dumped both on the box. The title stopped presenting (2,453 flips in 124 s). Live saves unchanged.
  - The dump (`raw/R2-devcd1-registers.txt`) is **F403's state, register for register**: GRBM_STATUS 0xa0407028, SE0/SE1 busy (0x0a000016), PFP 0xea1 / ME 0x77b, no fault.
  - The PFP history is the host's GFX-form `DISPATCH_INDIRECT` with its CP check (`ACQUIRE_MEM`, `EVENT_WRITE`, `DISPATCH_INDIRECT`, `COND_EXEC`, `PFP_SYNC_ME`, `WRITE_DATA`), and the ME's has the `COND_WRITE`s.
  - The IB was 6,584 dwords, 57 % fetched: the compute buffer with its inserted checks (2,380 + ~47 checked dispatches), run on the GFX ring.
  - So the compute dispatch that does not end is still there with one ring and both guards on the S6N route. The route's RT-on point at ~110 s is F332's (two rings, 11/11 at 111–118 s).
- *The staircase does not catch F403's triple* (code read, `backend/src/indirect_check.cpp:139–161`). It refuses only when (y > 1 or z > 1) **and** x > 2^16. In 818 × 820 × 819, x is 818, so it passes. F414's sentence "catching F403's runaway grids such as 818×820×819" is wrong as built.
- *The runaway may not be a big grid at all.* F404 read the largest grid in memory at a timeout as 28,644 groups, so the likelier shape is a dispatch of ordinary size whose shader does not end. That is the BVH traversal's loop on a bad BVH, the open line of F207/F332, and no grid limit stops it.

**Verdict.** The integration is in: one ring and the guards cost RT-off play nothing (R1), and the overlay fix is built. RT on is **not solved**:
- the maintainer's 46-minute play did not hang (F415);
- the bench route hangs at ~106 s in F403's state, and this time the ring reset recovered the box.

`input.cfg` holds RT on as the maintainer asked; whether to keep it until the F403 class is fixed is his call. Next:
- read acb #76004's dump on the box: which dispatch sits at the 57 % mark, its program, and its arguments at the timeout;
- tell a huge grid from a looping shader;
- correct F414.
