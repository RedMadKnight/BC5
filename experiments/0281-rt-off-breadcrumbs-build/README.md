# 0281 — RT off with breadcrumbs: one private binary for the catch runs

**Question.** Both GFX hangs of 2026-10-24 stopped inside the second BVH tree family's builders: 18:52 with RT on
(F336) and 19:57 with RT off (F339). At 19:57 the fetcher stood in a run of 0x909973d00, behind ~600 dispatches issued
since the last CS_PARTIAL_FLUSH. Exp 0277's breadcrumbs would name the dispatch that was reached and is not done.

The catch runs should keep RT off, now with that family dropped too (exp 0280 arm A: ~10 min clean, F340). Can one
private binary carry the breadcrumbs on top of the switch, so that the next stop, if any, names its dispatch?

**Known before this experiment.**
- **Exp 0278's switch is integrated** into both shared builds (F343, 2026-10-24 22:05–22:06):
  - the tree's `bc5LleAgc.cpp` is now 5bccbb80;
  - the shared normal is 7947154c;
  - the second title's launchers carry exp 0280 arm A's ten-program build list;
  - `KYTY_BC5_RT=0` starts RT off; the title's saved `RayTracing.<TITLE_ID>` overrides it.
- **Exp 0277** (private binary 13b0e9ba on the old tree, never run) adds the breadcrumbs, off by default. Its 18 edits
  touch only `bc5LleAgc.cpp`.
- **The tree is reproducible offline.** a2a2c2df plus `patch0278.py`'s three edits to `bc5LleAgc.cpp` gives exactly
  5bccbb80 (checked on the laptop, 2026-10-24 ~22:15). The two patches' edits commute: either order gives 55fa73a4.
- **Correction to exp 0277's README.** It said no launcher sets `BC5_DIRECT_MEC_INDIRECT`, so exp 0038's rebuild had not
  run in play. In fact `play-pkg.sh` line 49 sets `BC5_DIRECT_MEC_INDIRECT=1` (with `BC5_DIRECT_GPU_CHECK=1` and
  `BC5_DIRECT_DMA_SYNC=1`; the box supervisor, 2026-10-24 ~23:05; F334's dated note).
  - So the probe bug that 0277 fixes (the rebuilt IB read with the title's executed offsets) did occur in play. But the
    rebuild fires only for compute-form (4-dword) DISPATCH_INDIRECT on the GFX ring: the scan fills `mec_hi` only when
    `qring == kGfxRing`.
  - Every hung buffer read so far has none, counted in the local dumps on 2026-10-24 (`raw/indirect-forms.txt`):
    - dcb #68401: 1,180 GFX-form;
    - acb #68408: none;
    - dcb #841748: 1,645 GFX-form;
    - acb #841756: none;
    - dcb #23408: 3 GFX-form;
    - acb #23415: 668 compute-form, but on compute ring 0 ("q0").
  - So the probe read those buffers unrebuilt, and the ran/DROPPED marks behind F336 and F339 hold. F339's fetch
    position never used them.
- **The 19:57 kernel lines** (`raw/kernel-19572x.txt`, read on the box supervisor's GO, 20:10):
  - comp_1.2.0 dumped and timed out at 29.886; gfx_0.0.0 timed out at 29.888. So devcd3's GFX state predates the GFX
    reset.
  - 10 TCP write faults on three pages fall between 27.874 and 27.923, about 13 ms before the GFX ring's last
    progress (F339's note).
  - `noretry` is -1.

**Setup** (prepared offline; first designed on a2a2c2df with 0278 applied too, then rebased on F343's tree; not built).
- **`patch0281.py`** loads `patch0277.py` unchanged from its own directory (md5 b2fdb2e9) and applies its 18 edits to
  the tree's `bc5LleAgc.cpp`. It checks that the input is 5bccbb80, that each anchor occurs once, and that the result
  is 55fa73a4. It writes the unit and `patch_0281.diff`.
  - A dry run on the reproduced 5bccbb80 gives 55fa73a4 (16 hunks).
- **`run0281.sh build`** is exp 0277's one-unit private build, with the tree check moved to 5bccbb80.
  - It records the inputs, the diff and the build log in `raw/`.
  - It prints the warnings in the patched unit, the binary's md5, and the counts of both features' strings.
- **`run0281.sh launcher`** prints the two lines a wrapper adds: `KYTY_BC5_RT=0` and `BC5_DIRECT_BREADCRUMBS=1`.
- **`build0281.py`** is `build0277.py` with this experiment's directory.

**Plan.** The build is on the box supervisor's GO and was approved by the maintainer in the tcp session (2026-10-24
~22:05). The runs need his yes.
1. **Build**, after the queue (AnyPS5's 0276 build, then water's 0283).
2. **A short attended check (~3 min).** It is the first time the breadcrumbs run on the GPU.
   - The health lines should show "done" close to "reached", close to all, on both rings.
   - Flips/s should be comparable to RT off without breadcrumbs (F338: ~48).
   - Stop and revise if the GFX ring's done marks are not written.
3. **Long RT-off catch runs.** If a stop comes, the probe's breadcrumb lines name the first dispatch reached and not
   done, and its program. With the second family dropped, that would point outside it.

**Result.**
- **Built** 2026-10-24 22:34:04–22:34:31 on the box supervisor's GO (22:33), approved by the maintainer in the tcp
  session, under my lock line, with no emulator running. Before it, the box held no lock and no emulator.
  - Inputs (`raw/build-inputs.txt`): tree `bc5LleAgc.cpp` 5bccbb80 (22:05:50), shared normal 7947154c (22:06:22).
  - The patched unit is 55fa73a4. `raw/patch_0281.diff` (16 hunks) is identical to the laptop's dry run.
- **rc 0** (`raw/build.out`). The 4 warnings are the file's old ones, none in the new code: `stringUtils.h:321`, and
  the unit's lines 73, 390 and 2357 (exp 0277's 73, 366 and 2333, moved down by 0278's integrated lines).
- **The private `~/bc5-work/exp0281/kyty_emulator`**: 166,694,392 bytes, md5 **0a74c602**. It has 6 "exp 0277" and 8
  "ray tracing" strings, so it carries both features.
- **After the build** the lock line was gone, and the shared normal (7947154c) and the tree (5bccbb80) were unchanged.
- Not run: the check run and the catch runs need the maintainer's yes.
