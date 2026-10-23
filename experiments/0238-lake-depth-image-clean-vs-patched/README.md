# 0238 — The night lake: the water's slot-4 image in clean and patched frames

**Question.** Exp 0237 found the screen's patchwork already in the slot-4 image the water's vertex
stage reads: cells at the far value whose edges line up with the screenshot's. That was one
patched shot. In a run that switches, do those cells go away in the clean frames?

**Setup.**
- BC-250 dev box, 2026-10-23, granted by the top session: up to five runs, stopping after the first
  run with a clean shot. K1 ran 18:33–18:39, then an analysis lock 18:40–18:42. Boot 31c1a6ac,
  unchanged; `/var/home` at 69 % before and after.
- `ab0238.sh K1 … K5` is exp 0235's driver with the same conditions:
  - the exp 0194 build (comm `kyty_emulator`) and its launcher copy with the old values;
  - `KYTY_BC5_AMM_TRACE=1`, the water shaders' draw journal, the table hashes and dumps;
  - the 3-s `dmesg` poll that stops a run on any new amdgpu fault, timeout or reset line;
  - `/var/home` under 80 %, and the live saves checksummed before and after.

  New: after each run it stops once the run had a shot under 5 %. The kernel log was streamed to
  the laptop (`raw/kernel-stream.txt`). The game shot was checked live for the lake save.
- `bench0238.sh` is exp 0235's `bench0235.sh` with only its names changed. One series of 26
  frozen-view shots, 5 s apart; before each shot `img0235.py` dumps the water's four images.
- `sum0238.py`, run in the box's Ubuntu container, takes each shot's slot-4 dump and de-swizzles it
  as exp 0237 found: 16 pipes, the width with the least block-row shear among the 16:9 sizes from
  2304 to 3328. Against that shot's patch mask (exp 0197's) it gives:
  - the share of the lake window at the far value (≥ 9000);
  - that share in patch and in other pixels, and their phi;
  - the log-depth step across the mask's edges over the window's.
- `img0235.py sum` gave the md5s and single-valued 64-KiB blocks per image. A dump counts as
  **complete** when its shear is at most 1.3 and it has no single-valued block. The others are
  two frames at different widths (high shear), or a target caught between its clear and its
  redraw (26–44 single-valued blocks). They occur in both classes.
- **The image dumps are the title's data. They were summarised on the box and deleted.** Two
  renders (ts11, ts22) are kept in `~/bc5-data/priv/exp0238` (mode 700). The repo has per-shot
  numbers only.

**Result** (`raw/ab.txt`, `raw/K1.bench.txt`, `raw/K1.slot4.txt`, `raw/K1.sum.txt`,
`raw/K1.complete.txt`).
- **Box state.** K1 loaded the lake save. No kernel fault, timeout or reset: the amdgpu count
  stayed at 578, the run's `.out` has 0 fault lines, and the kernel stream has only routine
  lines. The live saves' checksum was the same before and after (f6475842373bf369). The run
  wrote about 600 MB: run directory 507 MB and journal 89 MB. That was about 190 MB after the
  image dumps were deleted.
- **K1 switched.** It was patched at 20–30 % for ts00–ts15, then 8.1, 11.7 and 15.7 % at ts16–ts18,
  then clean at 1.0–1.6 % from ts19 to ts25. The series stopped after K1.
- **In complete dumps, the slot-4 image's patchwork follows the visible state:**

  | class | complete dumps | far value in the lake window | step across the patch edges / window |
  |---|---|---|---|
  | clean | 4 of 7 | 0.000 in all four | ×1.9–3.2 (the clean mask is ~1 % noise) |
  | patched | 7 of 19 | 0.196–0.386, mean 0.328 | ×4.2–12.0, mean ×7.6 |

  - By eye: ts11 (patched, 19.6 %) shows a checkerboard of far-value cells over the near lake. ts22
    (clean, 1.0 %) shows the same lake as one smooth surface.
  - In the patched dumps, which side of a cell edge is far varies (phi −0.37 to +0.79), while the
    edges keep coinciding. The dump and the screenshot are different frames.
- **The pixel-stage textures** were again static through the run, clean and patched alike, with the
  same md5s as I1–I3 (f3821943, 5db21f55, 7f7e97ed).

**Verdict.**
- **The slot-4 image the water's vertex stage reads carries the patchwork exactly when the screen
  does.** In clean frames it holds the lake as one surface. In patched frames it has cells at the
  far value whose edges are the screen's cell edges. Four clean and seven patched complete frames,
  from one switching run.
- With F292–F294, this is the only water input found to differ between clean and patched frames.
  The texture table, the per-frame constants, the bindless indices and the pixel-stage textures
  do not.
- **Open:**
  - Which pass writes `CB0` 0x113cb40000 and why it leaves the far value in cells.
  - Whether that pass's pattern makes the water's, or both come from one earlier fault (for example
    the geometry of the lake surface itself).
- **Next:** one run with the draw journal unfiltered for a single frame, to find the draw that
  renders into 0x113cb40000, its shaders and its inputs.
