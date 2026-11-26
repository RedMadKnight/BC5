# 0282 — The night lake: does the hole pattern alternate from frame to frame?

**Question.** In patched frames the lake's holes are pixels with cleared depth (0, reverse-Z far) and a cleared
G-buffer (F333). Each of exps 0271/0274's reads took the depth memory and then the G-buffer, a few frames apart. In
patched reads the two hole sets coincided (W271b, phi up to +0.97), half-overlapped (W271a) or were disjoint (W274a,
phi about −0.4), with similar shares each time (F341). That would fit a pattern that alternates between two
complementary sets of cells from frame to frame. Do depth reads taken one frame or two apart show it directly?

**Plan** (as written before the run; the GO, top session 2026-10-24 ~21:31: one bench run of about 10 min).
- One run of the usual frozen-view lake bench (26 shots, exp 0197's patch metric) with W274b's settings: the RT
  session's binary `~/bc5-work/exp0278/kyty_emulator` (md5 cd17ab79), ray tracing on, the same journal switches
  (window at t 150, `_PS` on the full-screen draw, `_FIND` on the writers' images). W274b was patched in all 26 shots,
  so a patched phase is likely.
- `capb0282.sh` takes 12 bursts, one every ~9 s from the first frozen-view shot. A burst (`burst0282.py`) is 6 reads
  of the depth image back to back (0x1129ec0000 + 0x1860000: 390 blocks of 64 KiB, the largest size's 26 × 15),
  each written to disk at once, then one read of the G-buffer (0x113f230000 + 0x1860000). It logs each read's start
  and read time, so the pairs of a burst span lags from one read to five.
  - Reads go to `~/bc5-data/priv/exp0282` (mode 700), about 170 MiB per burst; they are summarised and then deleted.
- `ana0282.py` decodes each read at the size its own depth image fits best (least block-row shear, as exps
  0271/0274; the G-buffer's size is printed as a check). For every pair of complete reads of a burst it gives the lag,
  the share of depth-0 pixels kept and phi between the depth-0 sets of the lake window, also per band of 70 shot
  rows (a frame change during a read would show as bands that differ). It also gives phi of each depth read against
  the G-buffer's cleared pixels.
  - A pattern that stays put gives phi near +1 at every lag. One that alternates each frame gives negative phi at
    odd frame lags and positive at even ones. One that is new each frame gives phi near 0.
  - Checked offline on synthetic reads (an alternating checkerboard at 2560 and 2816 swizzled with the same
    patterns): sizes found, phi −0.67 at odd lags and +0.99 to +1.00 at even ones.
- Box rules as before: BOX-LOCK line of the run's own, kernel stream to the laptop, the run stopped on any new
  amdgpu line, live saves (af64b06adff9c5f1) snapshotted first and checked after.
- Scripts: `ab0282.sh` / `bench0282.sh` (exp 0274's, renamed), `capb0282.sh`, `burst0282.py`, `ana0282.py`,
  `swz0248-z4.json`, `swz0244-4.json` (exp 0274's copies). Raw files under 1 MiB each; no images kept.

**Setup as run.**
- BC-250, 2026-10-24 21:36–21:52, boot 831e5915; `/var/home` at 72 %.
- The live saves held the maintainer's lake save (af64b06adff9c5f1). They were snapshotted at 21:41 and checked
  before and after the run; they never changed (the bench uses its private copy), and the snapshot was removed.
- Run W282a, 21:41–21:47: as planned (binary md5 cd17ab79, no RT variables in the emulator's environment, W274b's
  journal switches).
- `capb0282.sh W282a 12 9 6 0`: 12 bursts from 21:43:43 to 21:45:33 (after shots ts00–ts21), 2.0 GB, deleted
  after the summaries. Each read took 6–18 ms. The disk writes between them spread the read starts 19 ms to
  over 1 s apart (`raw/W282a.capb.txt`, per read "start+read" in ms).
- The bench's frame rate was not logged, so lags cannot be converted to frames.
- After the run, on the box with no emulator: `ana0282.py` (`raw/W282a.ana.txt`), then `cross0282.py` on the clear
  reads (`raw/W282a.cross.txt`). On the laptop: `clear0282.py` on ana0282.py's output (`raw/W282a.clear.txt`).

**Result** (`raw/`).
- **Box state.** No kernel fault, timeout or reset: the amdgpu dmesg count stayed at 257, `raw/W282a.out` has 0
  fault lines, the stream (`raw/W282a.kern.txt`) has only the routine IPv6 MLD lines, and no new devcoredump was saved.
- **The lake was patched throughout** (`raw/W282a.bench.txt`): ts01–ts25 at 12.3–24.7 %, ts00 at 7.3 %. The first
  burst counts as mixed, the other eleven as patched.
- **The depth image alone often does not tell the render size.** In 52 of the 72 reads, the next-best size's shear
  was under 3 × the best, often within 10 % (e.g. 2560 at 1.31 and 2304 at 1.41), so the decode may be at the
  wrong size.
  - Only 20 reads are clear (next-best shear ≥ 3 × the best; 19–23 for thresholds from 1.5 to 5;
    `raw/W282a.clear.txt`).
  - The results below use the clear reads only. The pairs that involve an unclear read (148 of 160) are not
    interpreted.
  - The clear reads' sizes change within bursts (e.g. b05: 2048 at 898 ms, 2304 at 991 ms), in line with the
    dynamic render size.
- **The holes are one of two fixed, disjoint sets of pixels.** Clear reads of one burst at the same size are either
  nearly the same or nearly disjoint, with nothing in between (10 pairs):
  - same: phi +0.87 to +1.00, 84–100 % of the first read's depth-0 pixels kept (lags 38, 277, 315, 365 ms);
  - disjoint: phi −0.16 to −0.42, under 1 % kept (lags 68, 72, 94, 132, 184, 809 ms);
  - and the two clear pairs of different sizes: +0.88 (2048/2304, 93 ms) and −0.12 (3072/3328, 389 ms). The
    holes stay in place on screen across sizes (so do the groups below, which mix sizes, and the depth/G-buffer
    matches across sizes), so they are not tied to memory blocks.
- **The same two sets recur across the run** (`raw/W282a.cross.txt`, all 20 clear reads against each other).
  - Four groups (phi ≥ 0.6 within each, medians +0.66 to +0.87), in two families:
    - X: group 2 (6 reads, depth 0 on 24–30 % of the lake window) and group 0 (3 reads, 9–15 %), which lies
      inside it (99.4 % of group 0's first read's depth-0 pixels are depth 0 in group 2's first read);
    - Y: group 3 (3 reads, 26–31 %) and group 1 (8 reads, 13–25 %), which lies inside it (99.3 %, the same way).
  - X and Y share almost no pixel: 0.1–0.8 % of either's depth-0 pixels (the groups' first reads), phi −0.12 to
    −0.42. Together groups 2 and 3 cover 0.595 of the window.
  - 9 of the clear reads are in X, 11 in Y.
- **X holds the screenshots' patches.** The cell mask from the 25 patched shots (12.6 % of the window) is at depth 0
  in 61–87 % of its pixels in X reads and in 7–11 % in Y reads. Y's holes lie mostly outside it.
- **The state switches within tens of milliseconds and back** (clear reads in order, start in ms):
  - b03: X at 25 and 63, Y at 157, X at 340;
  - b04: X at 0, Y at 72;
  - b10: X at 44, Y at 112;
  - b01 and b11: X then Y, 389 and 809 ms apart.
  - The same state was also seen 38 ms (b03), 93 ms (b05) and 365 ms (b09) apart.
  - Without the frame rate, this does not show whether the state flips every frame or every few frames. The
    38-ms same-state pair argues against a flip at every frame of 26 fps or faster.
- **The G-buffer's holes follow the same state.** When the burst's G-buffer read has a lower cleared share
  (0.13–0.25 of the window), it matches one state:
  - phi +0.82 to +0.97 with the clear depth reads of that state (b01 z5, b10 z3, b11 z5, b12 z5);
  - phi −0.12 to −0.32 with those of the other state (b01 z1, b05 z3/z5, b07 z5, b08 z5, b10 z2, b11 z0).
  - With a cleared share of 0.62 it contains both: in b03, phi +0.45 to +0.50 with X and Y reads alike (b06: +0.45
    with its one clear read, Y). That is the value for a set of 0.62 that contains a depth-0 set of 0.25:
    √(0.25 · 0.38 / (0.62 · 0.75)) = 0.45.

**Verdict.**
- **The night lake's holes switch between two fixed, disjoint sets of pixels, X and Y,** in a patched phase, within
  tens of milliseconds and back. Each read holds one set (or a part of it), and the G-buffer's holes follow the same
  state.
- This explains F341: a depth read and the G-buffer read taken a few frames later coincide when they catch the same
  state, are disjoint when they catch opposite states, and half-overlap when a read is mixed.
- The screenshots' patch cells are X. Y lies elsewhere, mostly outside the cells.
- **Not shown:**
  - whether the state flips every frame (no frame timing);
  - what decides it: the render size does not (both sets occur at 3328 within one burst);
  - why Y's holes do not show as patches in the shots.
- **Next:**
  - frame timing for the reads, e.g. from the journal's flip or submit times or a frame counter in memory, to tell a
    per-frame flip from a slower one;
  - the per-frame draw lists of an X frame and a Y frame (`_EVERY` with the depth writers' prefixes, as exps
    0257/0261) for what differs between the two.
