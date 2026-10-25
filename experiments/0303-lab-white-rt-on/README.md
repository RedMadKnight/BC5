# 0303 — The second title's white lab with ray tracing on: is it the same reflection traversal?

**Question.** Exp 0299 (F362), all with RT off: the lab's washed-out white comes from the RT reflection traversal.
0x11d049aa00 whitens the opaque glossy surfaces and 0x11d04a6000 the glass, with 0x11d04bb900 alongside; with the
three skipped, the lab is grey. With RT off the switch drops the BVH build list, so those passes walk trees that were
never built. The maintainer saw the same white with RT on, where the trees are built but without the compaction
0x909974400, which stays skipped (F207, F275). Does the white with RT on come from the same passes?

**Plan** (the maintainer's yes, relayed by the top session: "zgadzam się na komplet Twoich testów"; GO after exp 0301's
GPU slot, ~12:30 CET; ~15 min).
- **The 0299 bench, unchanged**: its private working directory and lab save copy, the shared normal build e62a97c6,
  route `slot4-90.cmd` (✕, down ×3, ✕, ✕ from 90 s).
  - `run0303.sh` / `ab0303.sh` are exp 0299's scripts with this experiment's paths, lock tag and outputs.
  - Input configuration: a private copy of exp 0194's `input-0194.cfg` with `RayTracing.PPSA03671=on`. The input
    configuration's line overrides the environment (patch 0001, experiment 0273). The maintainer's own `input.cfg`
    has it off and is not touched.
- **L8**: RT on, the launcher's defaults (only 0x909974400 skipped).
- **L9**: RT on plus `BC5_DIRECT_SKIP_PGM=11d049aa00,11d04a6000,909974400,11d04bb900`.
- **Each run proves RT on**: no "ray tracing off" line in its journal, so no build program dropped.
- **Measured** as in exp 0299: `wh0299.py`'s numbers on the shots, plus one shot per run viewed in the session
  scratchpad and deleted right after.
- **Rules**:
  - the live saves (8289704a9338a118) are never used, with checks before and after each run;
  - the kernel stream; `ab0303.sh` stops a run at the first new amdgpu line;
  - the session stops at the first reset or machine-down, and the top session hears of it at once;
  - no images in the repo.

**Setup as run** (the top session's GO of 12:16 CET; BC-250 after a reboot since exp 0299, boot 664515e3; shared
normal build e62a97c6).
- **12:17.** Our lock line; live saves 8289704a9338a118 (never used; checked before and after each run).
  - Exp 0194's `input-0194.cfg` on the box has no RayTracing line, so exp 0299's RT-off runs were decided by
    `KYTY_BC5_RT=0` alone.
  - `input-0303.cfg` is that file plus `RayTracing.PPSA03671=on` (`raw/input-0303.cfg`). The kernel stream ran
    throughout (`raw/window.kern.txt`).
- **L8, 12:17:19–12:20:43:** RT on, the launcher's defaults (0x909974400 skipped).
- **L9, 12:20:53–12:24:18:** RT on plus `BC5_DIRECT_SKIP_PGM=11d049aa00,11d04a6000,909974400,11d04bb900`. Its lab
  came up later; the shots at 120 and 130 s were still the black load.
- **Shots viewed** in the session scratchpad and deleted right after: L8 t150, L9 t165. No image is in the repo.
- **Released 12:24:57** (BOX-QUEUE line 89).

**Result** (`raw/`).
- **RT was on in both runs** (`raw/L8.rt.txt`, `raw/L9.rt.txt`): 0 "ray tracing off" lines, so no build program
  dropped. The only skip lines are the ones asked for: 0x909974400 in L8; 0x11d049aa00, 0x11d04a6000 and
  0x909974400 in L9.
- **No kernel event:** 0 fault lines, the amdgpu dmesg count 120 before and after, only routine lines in the stream.
- **The numbers** (`raw/L8.wh.txt`, `raw/L9.wh.txt`; median over the lab shots, a static view), with exp 0299's RT-off
  runs for comparison:

  | run | RT | traversal variants | luma mean | p90 | p99 | white | clipped | chroma |
  |---|---|---|---|---|---|---|---|---|
  | 0299 L3 | off | running | 0.335 | 0.868 | 0.962 | 0.064 | 0.013 | 0.085 |
  | L8 | on | running | 0.334 | 0.868 | 0.962 | 0.064 | 0.012 | 0.085 |
  | 0299 L4 | off | skipped | 0.303 | 0.607 | 0.883 | 0.006 | 0.000 | 0.113 |
  | L9 | on | skipped | 0.302 | 0.609 | 0.883 | 0.006 | 0.000 | 0.113 |

- **The views:** L8 shows the white lab of exp 0299's L3: the glowing floor, the flat pale glass and the white cart.
  L9 shows the grey lab of L4: the grey floor, see-through glass with the shelves behind it, and lit walls.

**Verdict.**
- **With RT on the lab's white comes from the same reflection traversal**, 0x11d049aa00 and 0x11d04a6000 (with
  0x11d04bb900). The numbers with RT on equal those with RT off to the third decimal, with the traversal running and
  with it skipped.
  - So with the BVH built (the compaction 0x909974400 still skipped, F207/F275), the traversal's result in the lab is
    as wrong as over the never-built trees of RT off.
  - The build alone does not make it right. TODO(verify): whether the missing compaction or something else in the
    traversal's inputs is the cause; not tested here.
- **What helps, by mode:**
  - RT off: exp 0299's build-list extension (tested there, L7b), a launcher change.
  - RT on: only skipping the traversal (L9). That is the pre-0218 "reflections off" setup and costs the RT reflections
    everywhere (F218).
  - Both wait for the maintainer's yes.
- **The real fix** is the traversal's input in the lab. The next step there belongs with the BVH compaction work.
