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
- **`catch0281.sh check | chain [N S]`** is exp 0265's `count0265.sh`, adapted for this binary.
  - **Modes.** `check` is one run of 180 s. `chain` is up to 6 runs of 600 s on S6N's route, each with its own save
    restore, stopping at the first run that is not a pass.
  - **Refusals.** It does not start unless the live saves are the box supervisor's reference c0ee58b92c0cadc2. It
    snapshots them first.
  - **The run environment** adds `KYTY_BC5_RT=0` and `BC5_DIRECT_BREADCRUMBS=1`. A run is a fail if its journal has no
    RT-off drop lines, since a saved `RayTracing.<TITLE_ID>` would override the variable.
  - **Per run** it extracts the breadcrumb lines (`<tag>-crumbs.txt`) and syncs its files before the next run.
  - **On HUP/INT/TERM** (a dropped ssh session) it stops only its own emulator, puts the live saves back and releases
    the lock.
- **`stream0281.sh`** (on the laptop) is exp 0265's `stream0265.sh`, keyed to the "exp 0281 | " lock line. It streams
  the kernel log, and from each new journal the probe, TIMEOUT and fault lines plus the breadcrumbs' health lines.

**Plan.** The build is on the box supervisor's GO and was approved by the maintainer in the tcp session (2026-10-24
~22:05). The runs need his yes.
1. **Build**, after the queue (AnyPS5's 0276 build, then water's 0283).
   The runs below wait for the maintainer's yes in the tcp session. At ~23:20 the box supervisor relayed an overnight
   approval in his name. Under the tcp session's rules a relayed approval does not stand in for his own for a GPU run,
   and a machine-down would leave the box down until morning.
2. **A short attended check (~3 min, `catch0281.sh check`).** It is the first time the breadcrumbs run on the GPU.
   - The health lines should show "done" close to "reached", close to all, on both rings.
   - Flips/s should be comparable to RT off without breadcrumbs (F338: ~48).
   - Stop and revise if the GFX ring's done marks are not written.
3. **Long RT-off catch runs** (`catch0281.sh chain 6 600`, with `stream0281.sh` on the laptop). If a stop comes, the
   probe's breadcrumb lines name the first dispatch reached and not done, and its program. With the second family
   dropped, that would point outside it.

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
- **The runs.** The maintainer approved them in the tcp session ("run exp 0281's check run … and, if it passes, the
  RT-off catch chain … Stop at the first non-pass"). The box supervisor's GO came at 23:57.
  - Before them the box was free, the live saves were the reference c0ee58b92c0cadc2, and `catch0281.sh` on the box
    was md5 44fe461e. `stream0281.sh` ran on the laptop throughout (`raw/kernel-stream.txt`,
    `raw/journal-stream.txt`).
  - Console output: `raw/check.out` and `raw/chain.out`. Per-run files: `raw/runs/`, without the play logs. Flips:
    `raw/flips-per-run.txt`.
  - The environment each emulator saw (`<tag>-start.txt`): `KYTY_BC5_RT=0`, `BC5_DIRECT_BREADCRUMBS=1`,
    `KYTY_BC5_RT_BUILD_PGM` = arm A's ten programs, `BC5_DIRECT_SKIP_PGM=909974400`, `BC5_DIRECT_MEC_INDIRECT=1`,
    `BC5_DIRECT_GPU_CHECK=1`, `BC5_DIRECT_TIMEOUT_PROBE=1`; binary 0a74c602, launcher `play-pkg.sh` md5 65d35963.

  | run | time | end | crash / kernel / TIMEOUT / devcoredump | RT-off drop lines | breadcrumbs | flips/s |
  |---|---|---|---|---|---|---|
  | C1 | 23:57:54–00:01:11 | 180 s | 0 / 0 / 0 / 0 | 2,137 | 2.38 M | 35.8 |
  | S1 | 00:01:50–00:12:05 | 600 s | 0 / 0 / 0 / 0 | 6,245 | 11.76 M | 39.9 |
  | S2 | 00:12:05–00:22:20 | 600 s | 0 / 0 / 0 / 0 | 6,216 | 11.79 M | 39.8 |
  | S3 | 00:22:20–00:32:35 | 600 s | 0 / 0 / 0 / 0 | 6,169 | 11.63 M | 39.3 |
  | S4 | 00:32:35–00:42:50 | 600 s | 0 / 0 / 0 / 0 | 6,260 | 11.81 M | 40.1 |
  | S5 | 00:42:50–00:53:06 | 600 s | 0 / 0 / 0 / 0 | 6,397 | 11.92 M | 40.5 |
  | S6 | 00:53:06–01:03:21 | 600 s | 0 / 0 / 0 / 0 | 6,227 | 11.75 M | 39.8 |

  Flips/s are the journal's "VideoOutSubmitFlip took" lines over the span between the first and the last, start
  included.
- **Every run passed.** The kernel stream has no amdgpu line in the window, and the journal stream has no TIMEOUT or
  fault line.
- **Saves.** All seven restores came back identical. The live saves were c0ee58b92c0cadc2 after every run and at the
  end (`raw/runs/catch-saves.txt`). The lock was released at 01:03:21.
- **The breadcrumbs on the GPU** (`raw/runs/*-crumbs.txt`).
  - Every health line after each run's first reads "of 4096 that followed the previous line, 4096 reached and 4096
    done". That is 354 samples in the chain plus C1's 18; each run's first line samples nothing ("of 0"). So both
    marks are written: the WRITE_DATA in front, and the RELEASE_MEM BOTTOM_OF_PIPE_TS / 5 with DATA_SEL 1 behind.
  - The sample does not separate the rings. The title's buffers go to the GFX ring and to compute rings, and no
    sampled breadcrumb was ever missing.
  - Rate: median 22,368 a second, at most 30,354; about 11.8 M per 600 s run.
  - Each run mapped the 1,048,576 slots once ("level 1 … (device 0)"); no device reopen happened.
  - The 19:57 hang's dcb #841748 would have carried about 2,600 of them.
- **Memory.** MemAvailable at each run's end, with the game still running, was 334–506 MiB (`<tag>-box-end.txt`). The
  breadcrumbs take 64 MiB of it (32 MiB pinned slots and a 32 MiB host table).
- **The binary predates exp 0276's integration** (094f09b, two upstream library fixes in the shared builds). It is the
  shared normal 7947154c plus the breadcrumbs.

**Verdict.**
- **The breadcrumbs work at play scale.** For 63 minutes of the second title with RT off, every sampled dispatch's
  "reached" and "done" marks were written. The probe would now name the dispatch a stopped ring is stuck behind, but
  no stop came, so none was named.
- **63 minutes with RT off and the second family dropped, with no fault, timeout or machine-down.** That fits the
  family being involved in the earlier stops (F336, F339; 0280 arm A ran 573 s clean). But it does not prove it: the
  RT-on 0276 session ran 29 minutes clean the same evening.
- **The cost is not measured.** The runs averaged 39.3–40.5 flips/s, start included. F338's RT-off session averaged
  43.9 without breadcrumbs, but on another route and in another session. Only a same-route A/B of this binary with
  `BC5_DIRECT_BREADCRUMBS` 0 against 1 gives the cost.
- **Next.**
  - That A/B.
  - Catch runs with breadcrumbs where stops do come. With RT on, a stop would name the second family's dispatch.
  - Integrating 0277 into the shared builds, env-gated and off by default, so any session can switch it on. That is
    the maintainer's decision.
