# 0235 — The night lake: the water's images in clean and patched frames

**Question.** Exps 0233/0234 (F292, F293) showed that the lake's clean/patched state is set per
frame. The water's texture table, its per-frame constants and the texture indices in them are the
same in clean and patched frames. The water's images are the remaining inputs:
- the pixel stage's three textures (2048² BC4, 512² 16_FLOAT, 4×4 at 0x11d0078000);
- the vertex stage's slot-4 image at 0x113cb40000, written by the GPU every frame at the render
  resolution.

Do they differ between clean and patched shots of a run?

**Setup.**
- BC-250 dev box, 2026-10-23 14:11–14:29, granted by the top session. Up to three runs, one lock
  per run, then an analysis lock 14:30–14:34. Boot 31c1a6ac, unchanged; `/var/home` at 69 % before
  and after.
- `ab0235.sh I1 I2 I3` is exp 0233's driver with the same conditions:
  - the exp 0194 build (comm `kyty_emulator`) and its launcher copy with the old values;
  - `KYTY_BC5_AMM_TRACE=1`, the water shaders' draw journal, and exp 0212's table hashes and dumps
    (`DUMPS=1`);
  - before each run: no lock, no emulator, the same boot, `/var/home` under 80 %;
  - during each run: `dmesg` polled every 3 s, the run stopped on any new amdgpu fault, timeout or
    reset line;
  - the live saves checksummed before and after (the bench uses its private copy).

  The kernel log was also streamed to the laptop, capped at 30 min on the box side
  (`raw/kernel-stream.txt`). The game shot of each run was checked live for the lake save.
- `bench0235.sh` is exp 0233's bench with one series of 26 frozen-view shots, 5 s apart (no nudge),
  plus `IMGS=1`. Before every shot, `img0235.py dump` takes the latest water draw (PS 0x11d01ff900)
  from the tail of the run's live draw journal, decodes its image descriptors and reads the four
  images through `/proc/<pid>/mem`:
  - `ps0`: 2048² BC4, 8 levels, 4KB_S, 2,797,568 bytes; its address moves per run;
  - `ps2`: 512² 16_FLOAT, 7 levels, 700,416 bytes;
  - `ps4`: 4×4, one 4-KiB block;
  - `gs4`: 16_FLOAT, 64KB_R_X, read at the extent of the largest size the journals showed,
    3328×1872, 12,779,520 bytes.

  Surface sizes come from exp 0205's `layout()` (Mesa addrlib). The journal records the water draw
  from t = 150 s, every 15 s, so the descriptors are up to 15 s old. Within each run the
  textures' addresses were the same in every shot.
- Dry test (`drytest0235.sh`): a helper process mapped anonymous memory at the same kind of
  addresses, with no title data, and a fake journal named it. `img0235.py` read the expected extents
  and summarised two synthetic shots; with no water draw in the journal it gave up cleanly.
- `img0235.py sum` classes each shot by the bench's patch share (clean under 5 %, patched at 8 % or
  more). Per shot and image it gives:
  - an md5 prefix;
  - for 16_FLOAT: zeros, non-finite and negative values, min/median/max/mean, single-valued blocks;
  - for BC4: flat and all-zero blocks;
  - across shots: changed 4-KiB pages, and pages separating clean from patched.

  It runs on the box.
- **The dumps are the title's rendered and texture data and stay on the box. The repo has only the
  per-shot summaries (`raw/I*.sum.txt`).** After summarising, the 308 image dump files were deleted.
  One shot (I3 ts00, 15.6 MB) is kept in `~/bc5-data/priv/exp0235` (mode 700), for a possible check
  of the slot-4 image's layout against that shot's screenshot.

**Result** (`raw/ab.txt`, `raw/I*.bench.txt`, `raw/I*.sum.txt`, `raw/I*.desc.txt`).
- **Box state.** All three runs loaded the lake save. No kernel fault, timeout or reset: the
  amdgpu count stayed at 578, each run's `.out` has 0 fault lines, and the kernel stream has only
  routine lines. The live saves' checksum was the same before and after (f6475842373bf369). The
  runs wrote about 1.8 GB: run directories 507–510 MB each and journals 87–90 MB each. That was
  about 0.6 GB after the image dumps were deleted.
- **No clean shot.** I1 was patched throughout (23–31 %), I2 too (26–33 %), I3 too (18–27 %): 78
  of 78 shots. So there is no clean/patched comparison in this series.
  - With exps 0232/0233: 22 of 169 frozen-view shots clean; 4 of 10 runs had any clean shot.
  - N4, I1, I2 and I3, the last four runs in a row, had none.
- **The pixel stage's textures are static and the same in every run.**
  - In each frozen view, 0 pages of `ps0`, `ps2` and `ps4` changed in 25 shot-to-shot steps.
  - The three runs have the same md5 for each texture (`ps0` f3821943, `ps2` 5db21f55, `ps4`
    7f7e97ed), though `ps0` sat at 0x8490f64000, 0x8492374000 and 0x8491494000.
  - They hold data: 0.1 % of the BC4 blocks flat or zero (under 0.05 % in mip 0), and the 512²
    values from 0 to 1.0 (median 0.87, 0.2 % zero).
- **The vertex stage's slot-4 image is rewritten every frame, and its values look like depth.**
  - 725–3,068 of its 3,120 pages changed between consecutive shots, mostly over 2,170.
  - Values run from 0 to about 10,000, with 2.5 % zeros, no non-finite or negative values, and a
    median of about 100–700.
  - The journal gave its size as 3328×1872 in all of I1's and I2's shots. I3 had 3328×1872 in 12,
    3072×1728 in 6 and 2816×1584 in 8.
  - In 35 of 78 shots, 37–42 of its 195 64-KiB blocks each held a single value, with a higher mean.
    That doesn't follow the patch share: 26.3 % in those shots against 27.4 % in the others. It
    is probably a dump landing between the target's clear and its redraw.

**Verdict.**
- **Inconclusive for the question: the three runs gave no clean shot to compare against.** The
  last four runs in a row (N4, I1–I3) stayed patched throughout.
- **The water's pixel-stage textures are ruled out as a per-frame cause.** They don't change
  during a frozen view, while the lake does switch there (N3, G3). Their content was the same in
  three runs. The texture table (F292) and the constants (F293) were already ruled out.
- **The vertex stage's slot-4 image** is a depth-like target the GPU rewrites every frame. It is the
  one water input left that changes per frame, so it is still a candidate, untested here.
- **Next:**
  1. The same dumps in more runs, until one switches. With 4 of 10 runs showing any clean shot,
     about five runs are needed.
  2. Without new runs: de-swizzle the kept slot-4 image (64KB_R_X, addrlib) and check whether the
     shot's cell pattern shows in it.
