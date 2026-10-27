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

**Result.** (pending)
