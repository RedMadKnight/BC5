# 0049 — the second title uses ray tracing (the base PS5's), not PS5 Pro features; its resolution is fixed and its frame is the CPU

**Question.** The maintainer asked whether the second title uses features only the PS5 Pro has,
ray tracing among them, and to run it in Full HD.

**Setup.** As in 0042 (`run-pkg.sh`, `pkg-series.sh`, the extended eager list). New in the host
(patch 0001): `BC5_DIRECT_SHADER_DUMP=<dir>` writes the code of every shader program a buffer
points at, once (the `SPI_SHADER_PGM_LO/HI` registers of the six graphics stages and
`COMPUTE_PGM_LO/HI`, set by `SET_SH_REG` or loaded by `LOAD_SH_REG_INDEX` pairs; register
offsets from Mesa `sid.h`), 64 KiB from each start. The dump went to the private
`~/bc5-data/priv/shaders-pkg` and is not committed. `rtscan.py` looks for the ray tracing
instructions by their encoding: `image_bvh_intersect_ray` and `image_bvh64_intersect_ray`
assemble to a first dword of 0xF1989F01 and 0xF19C9F01 (`llvm-mc -mcpu=gfx1013 -show-encoding`),
and each candidate is disassembled to confirm. Runs 178 (dump, 300 s), 179
(`BC5_DIRECT_TS_SCALE=0.5`), 180 (`BC5_DIRECT_FLIP_DEFER=1 BC5_DIRECT_MAX_IN_FLIGHT=24`),
2026-10-11 20:06–20:44. Raw output in `raw/`.

**Result.**

1. **PS5 Pro mode is off.** The host answers `sceKernelIsTrinityMode` and the graphics driver's
   `GetIsTrinityMode` with 0 (`libKernel.cpp`, `agc.cpp`), so the title runs its base-PS5 path;
   features only the Pro has (its own shader binaries, its upscaler) are not used.
2. **The title uses hardware ray tracing, as the base PS5 offers it.** Of 317 programs it ran in
   300 s, one carries `image_bvh_intersect_ray v[0:3], v[87:97], s[24:27]` (program 0x11d040e200,
   dword 912): the ray's inverse direction from `v_rcp_f32` of three scalars, a BVH descriptor
   built in `s[24:27]`, then a traversal loop over the four returned node indices (-1 for none).
   gfx1013 has these instructions (the BC-250's GPU is the same target as the PS5's, HANDOFF F63),
   so they run as they are. The compute program 0x909939900, skipped since experiment 0039 because
   it does not finish on the single ring, is a bottom-up refit of a bounding-volume tree (min/max
   of child bounds with atomic counters): very likely the update of the tree this traversal walks.
3. **Its 3D view is a fixed 1664×936 inside 2560×1440 targets, upscaled to 1440p and output at
   4K;** halving the timestamps (run 179) changed nothing, so it is not steered by GPU time.
   1664/2560 = 0.65 per axis.
4. **Its frame is the CPU:** 50–54 ms a frame, of which the GPU is busy 23 ms; the title's render
   thread spends 38 ms outside the host and 12 ms inside it (run 178). A lower resolution would
   not make it faster.
5. The deferred flip and 24 jobs in flight (the play settings since 0045) run it cleanly: run 180,
   300 s, no fault, 18.7 fps from 250 s.

**Verdict.** Answered: no Pro features; base-PS5 ray tracing, executed natively, with the tree
refit it depends on skipped (which may matter for its picture and its faults, open). Full HD:
the title's own resolution cannot be steered, so its launcher (`play-pkg.sh` on the dev box) now
starts it fullscreen at the display's resolution (1920×1080 on the dev box).
