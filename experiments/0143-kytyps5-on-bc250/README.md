# 0143 — Upstream KytyPS5 does not start on the BC-250: it requires fragment shader barycentrics, which RADV exposes from GFX10.3 on

**Question.** Public reports put the second title at up to 20 fps on KytyPS5, the Vulkan emulator
KytyPlus derives from. Does current KytyPS5 run the title on the BC-250? If so, does its opening
play past the first shot (F182), for a side-by-side comparison with our direct path?

**Setup.**
- BC-250 dev box, 2026-10-16 21:56.
- KytyPS5 at 5dec523 (2026-10-16), fresh clone in `~/src/KytyPS5-build`.
  - Built in the `ubuntu` distrobox with clang, Release, `kyty_emulator` target only.
  - `KYTY_GLSLANG_VALIDATOR=/usr/bin/glslangValidator`: the first `glslangValidator` on the PATH is
    the `distrobox-export` wrapper into the `fedora` container (`~/.local/bin`). Called from inside
    `ubuntu`, it hung the first build for an hour.
- Runner `~/bc5-work/play-kytyps5.sh`:
  - mounts the package with bc5-mount;
  - runs `kyty_emulator --game <mount> --skip-notice-screen true --amd-cpu`, printf to a file.
- Vulkan in the container: Mesa 26.0.8 (Ubuntu), RADV GFX1013.
- Raw: `raw/trial.txt`.

**Result.**
- **The emulator exits before opening a window.** It reports "Could not find suitable device":
  - AMD BC-250 (RADV GFX1013): `VK_KHR_fragment_shader_barycentric` is not supported;
  - llvmpipe: no image view minLod and no barycentrics.
- **KytyPS5 requires the feature.**
  - It is a hard check in `src/graphics/presentation/window/vulkanWindow.cpp` (`check_feature(...
    fragmentShaderBarycentric ...)`).
  - Its shader recompiler maps the pixel shader's barycentric VGPR inputs (perspective
    center/sample/centroid, linear) to `gl_BaryCoordKHR` / `gl_BaryCoordNoPerspKHR`
    (`src/graphics/shader/recompiler/frontend/translate/Translate.cpp`, `ir/passes/ShaderInfoCollection.cpp`).
    Almost every pixel shader that interpolates uses those inputs.
- **RADV enables the extension only for GFX10.3 and later:**
  `.KHR_fragment_shader_barycentric = pdev->info.gfx_level >= GFX10_3` in
  `src/amd/vulkan/radv_physical_device.c` (Mesa main 0866ae7, 2026-09-29). The BC-250 is GFX10.1, so
  a newer Mesa does not change this.

**Verdict.**
- **KytyPS5 does not run on this machine.** The reported 20 fps comes from RDNA2-or-later
  desktop GPUs. On the BC-250 there is no KytyPS5 run to compare against.
- Our direct path does not hit this. It runs the title's native pixel shaders, which read the
  barycentrics the hardware puts in VGPRs, without going through Vulkan.
- Why RADV draws the line at GFX10.3 (hardware or driver) is not established.
  TODO(verify): a RADV build with the check relaxed would show it, at the cost of a custom Mesa in
  the container.
- What can still be compared without running KytyPS5 is its HLE and shader-recompiler source for the
  opening (F182), for example the calls it implements that our host stubs.
