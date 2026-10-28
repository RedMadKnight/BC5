# 0362 — The night lake's history fill: does the lake take half its cells from the previous frame, and from what?

**Question.** F372 read the night lake's patches as one half of a checkerboard of water cells, and which half swaps
between two states. That is what a water renderer leaves if it draws half its cells per frame and should fill the
other half from the previous frame. Every lake draw is issued identically in clean and patched frames (F313, F320,
F323). The holes are pixels where nothing wrote depth or the G-buffer in that frame (F333). The culling buffers
(F436, F440) and the depth pyramid's generation (F441) do not carry the state. Q21's remaining lead is that history.

So, per frame:
- does the lake's depth get written for both halves in one pass, or for one half by the draws and for the other by a
  later pass or by keeping the previous frame's values?
- if a fill exists, what does it take its values from, and does it differ between hole and clean frames?

What is known and what is not:
- **Two depth bursts per frame.** Exp 0357's poll log (`raw/P1.events.txt.gz` there) has each 33.7-ms frame begin
  with the pyramid's rebuild, then two short bursts of change in a 256-KiB sample of the lake's depth rows. Over its
  1,427 frames:
  - burst 1 starts at a median +5.4 ms and ends at +6.4 ms;
  - burst 2 starts at +18.1 ms and ends at +18.6 ms;
  - D changes within 1 ms of the rebuild come in 420 frames.
  Which pixels each burst writes is not known. One of them could be a fill.
- **The depth image is one address at every render size** (0x1129ec0000, F309), so a frame at another width writes
  another layout into the same memory. Consecutive frames are comparable pixel for pixel only at the same width.
- **The depth's HTILE is re-initialised every frame by a compute fill** (CS 0x11d0288a00, F310). Whether that, or
  anything else, also writes the depth memory itself at the frame's start is not known. Yet the holes hold 0
  (reverse-Z far) in memory (F333), so something writes them.
- **F374:** no frame-swapped history buffer is read by the depth writers. The full-screen water draw's 256 × 256
  ping-pong grid does not follow the state (F376).

**Expectation.** Three readings, and what a frame's depth snapshots would show under each. X and Y are the two hole
halves, taken from the run's own hole frames.
- **Fill from history (F372 as stated).**
  - In clean frames, one burst writes one half and the other half is written later or kept from the previous frame.
    So per half, the write happens in different bursts, or one half stays bitwise equal to the previous frame's final
    depth while the other changes.
  - Which half is drawn would follow the state.
  - In hole frames the fill's half is left at 0, or zeroed and not refilled.
- **Every cell drawn every frame (no fill).**
  - In clean frames, X and Y are written alike, in the same burst.
  - In hole frames, the hole half is zeroed at some point in the frame and never written.
  - Neither half is carried over.
- **Kept, not filled.**
  - The depth memory is not cleared, and a half is simply not redrawn.
  - Its final depth then equals the previous frame's, and its holes would be holes carried over from the frame
    before.
- **When the snapshots cannot tell.** "Written" shows only where a value changes. If the lake's depth is the same
  from frame to frame (a static view and static geometry), a rewrite and a kept value look the same. The run measures
  that first: the share of lake pixels whose final depth changes between consecutive frames of the same width, and
  whether the memory is zeroed at the frame's start. Snapshots that run into a burst are dropped.

**Plan** (the top session's GO of 2026-10-28 ~16:05, with the maintainer away until 23:00 and autonomy given; RT ON,
the standing rule; one run, a second only if the first gives no usable frames).
- **The bench:** exp 0357's lake bench on today's shared normal build (1000ad2a, exp 0361's, with the job-arena fix,
  which does not touch rendering).
  - Launcher: `play-pkg.sh` 55531ab6 with exp 0353's five edits (`setup0362.sh` checks them line for line).
  - Config: RT on, MangoHud off; 24 frozen-view shots.
  - The draw journal `210:3000` with `_PS=11d01d7100` sizes the snapshots, as in exps 0354 and 0357.
  - **New in the journal:** `BC5_DIRECT_DRAW_JOURNAL_FIND=1129ec00` (the depth image's T# base dword) and `_ACB=1`.
    They list every draw and dispatch that binds the depth image as a texture, with the dispatches' journal times.
    That is the inventory of passes that read the depth, where a history reader would show.
- **`pl0362.py`, beside it:** polls through `/proc/<pid>/mem`, read-only, from the frozen view and the emulator's
  212th second, for 60 s.
  - **Every poll** reads D, the 256-KiB lake sample (depth + 0x980000), and the pyramid's mip 0 (0x11d0886000,
    0x8000; it changes once per frame, F441). It logs each change with its time, as exp 0357 did.
  - **Every 2.5 s, a capture of 5 consecutive frames.** At each rebuild, a frame starts. Each snapshot is a 7-MiB read
    of the depth image at +0x300000…+0xa00000, which holds the lake window's rows at widths 2048–2560. Per frame:
    1. **s0**, once D has been quiet for 1 ms after the rebuild;
    2. **s1**, once a D burst has been followed by 1.5 ms of quiet;
    3. **s2**, the same after the next burst.
  - D is read right before and after each snapshot. A change between them marks the snapshot torn.
  - Snapshots are kept in memory during a capture (~105 MB) and written to `~/bc5-data/priv/exp0362` after it.
  - Per snapshot it records its time since the rebuild, its read time and its torn flag.
- **`sn0362.py reads`:** the size of each snapshot by the block-row shear. It uses the block rows that lie whole
  inside the snapshot (rd0312.py's ADDR_SW_64KB_Z_X at 16 pipes, `swz0248-z4.json`). A size is clear when the
  next-best shear is at least 3 × the best. **`fr0354.py`** then fits the journal lag on the clear ones and gives
  every snapshot its frame's width.
- **`sn0362.py ana`, the test:** each snapshot is decoded into the lake window (x 300–1900, y 400–680 of the
  1920 × 1080 shot, nearest pixel), keeping only the pixels that lie inside the snapshot.
  - **The states:** each frame's s2 depth-0 share, with a floor of 0.03. Frames above it are split into A and B by
    the leading eigenvector of their φ matrix (ph0357.py's method). X and Y are the pixels at 0 in at least half of
    the A frames and of the B frames.
  - **Per frame, at its width,** the share of X, Y and the rest of the window in which:
    - s1 ≠ s0 (burst 1 wrote a new value);
    - s2 ≠ s1 (burst 2 did);
    - s0 ≠ the previous frame's s2 (something wrote between the frames);
    - s2 = the previous frame's s2 bitwise (carried over or unchanged), when both frames have the same width;
    - each snapshot is 0.
  - **Grouped by** the frame's state and the previous frame's state (clean, A, B).
  - `--selftest` plants each reading on a synthetic window:
    - a fill in burst 2 on one half;
    - a kept half;
    - both halves in burst 1.
    The table must show each.
- **`fi0362.py`:** the `_FIND` hits per frame (between consecutive full-screen water draws). For each, the program
  (PS or CS), its colour target, the user-data slot, and, for dispatches, the time relative to the frame's
  full-screen draw.
- **The reading:**
  - A half written in another burst than the other, or carried over bitwise while the other changes, in clean
    frames, supports a fill. The `_FIND` list and the burst's time then point at the pass.
  - Both halves written in one burst in clean frames, and the hole half zeroed and not rewritten in hole frames,
    rejects F372's fill. The draws then simply do not cover that half in those frames.
  - If the lake's depth does not change between frames and is not zeroed at the frame's start, the run cannot tell,
    and says so.
- **Rules:**
  - the guard: an empty BOX-LOCK, our own lock line, no emulator. The box is shared with exp 0360 (the CPU-throughput
    session) and exp 0363 (the bvh session's ASTRO BOT check).
  - the kernel stream to the laptop; stop at the first reset;
  - live saves 41a5a36fffb4f8d4, compared only;
  - snapshots and shots deleted after the analysis, unviewed; the journal stays private.
- **Why RT on is fine:** the measurement reads memory and needs no RT setting; RT on is the standing rule.

**Setup as run** (the top session's GO of 2026-10-28 ~16:05; build 1000ad2a; launcher 55531ab6).
- **16:23.** Exp 0360 held the box (its lock line). A read-only laptop watcher checked the lock and `pgrep` every
  60 s.
- **16:27:49 and ~16:29:50.** The guard found an ASTRO BOT emulator with an empty BOX-LOCK twice: exp 0363's attempts
  A2 and A3 (its BOX-QUEUE claim of 16:25). We touched nothing. A second watcher waited for three free checks 30 s
  apart, or for exp 0363's "done" line, which came at 16:42:25.
- **16:46:33.** Our lock line went into the empty BOX-LOCK, `~/bc5-work/exp0362/CLAIM.txt` was written and a
  BOX-QUEUE line added. Live saves 41a5a36fffb4f8d4.
  - `setup0362.sh`: `play-pkg-0362.sh` 7eb1ee7c with exp 0353's five edits (`raw/play-pkg-0362.diff`);
    `input-0362.cfg` 1666716f, RT on, MangoHud off (`raw/input-0362.cfg`).
  - `sn0362.py --selftest` passed on the box: burst 1 b1/b1 ×6; the burst-2 fill b1 + b2 ×9; the kept half
    b1 + kept ×8.
  - The kernel stream ran throughout (`raw/kernel-stream.txt`).
- **H1, 16:47:16–16:52:18** (`raw/H1.ab.txt`, `raw/H1.out`):
  - binary 1000ad2a, RT on (0 ray-tracing-off lines), one ring (0 compute-ring lines);
  - the journal `210:3000` with `_PS=11d01d7100`, `_FIND=1129ec00`, `_ACB=1`;
  - 20 frozen-view shots (the bench's default series; the plan's "24" was a slip).
- **`pl0362.py H1 60 … 212 2.5 5`** (`raw/H1.pl.txt`): polling from the frozen view at 212.0 s.
  - 990,255 polls at a mean 0.061 ms. The largest gap, 1,085 ms, was a capture being written.
  - D changes 14,712, P changes 2,064.
  - 20 captures, 212 snapshots, 74 of them torn. A snapshot read took 3.7–5.7 ms, not the planned ~3.6 ms.
- **Analysis on the box, 16:52–16:57:** `ana0362.sh H1` (`raw/H1.reads.txt`, `raw/H1.fr.txt`, `raw/H1.ana.txt`,
  `raw/H1.fi.txt`), then `fz0362.py` (`raw/H1.fz.txt`) and `sx0362.py` (`raw/H1.sx.txt`).
- **Changes after seeing the data:**
  - **The snapshot points missed the frame's structure.** In H1 most frames have three D bursts, not exp 0357's
    two (`bt0362.sh`, `raw/H1.bursts.txt`). So:
    - s1 (median +8.3 ms) mostly ran into the second burst: 56 of 71 torn;
    - s2 (median +14.6 ms) mostly came before the third.
  - **The planned `sn0362.py ana` tables are void, and not read.** Its states split identical masks: X and Y
    the same 3.3 % of the window, φ 0.97 between. Its c01/c12 compare images that hold no per-pixel depth (below).
  - **`fz0362.py` takes a frame's final depth only from snapshots with their own clear size.** Its `sx0362.py`
    check tries the two widths `sn0362.py` did not (3328, 3840).
  - **`rc0362.py` re-runs exp 0357's late-culling test on its clear reads only** (`raw/re0357.txt`, laptop,
    exp 0357's committed raw files).
- **Cleanup at 16:57:** the 212 snapshots (1.5 GB) and 22 shots were deleted unviewed. Kept: the poll log
  (`raw/H1.events.txt.gz`: times and flags) and the snapshot list (`raw/H1.snaps.txt`). The journal stays private:
  `~/bc5-data/captures/play-20261028-1647/gc/direct.log`, 134,126,548 bytes.
- **Released 16:57:40:** our journalctl ended by its PID, the lock line removed, no emulator, launcher or bc5-mount
  left, a BOX-QUEUE line.

**Result** (`raw/`).
- **No kernel event:**
  - 0 fault lines and 0 ring timeout or reset lines; the stream holds IPv6 lines only;
  - 0 fence timeouts.
- **Live saves:** 41a5a36fffb4f8d4 before, after and at the release.
- **Frame rate:** 29 flips in 1.001 s at t 290 s.
- **The journal:** 2,246 full-screen water draws from t 210.0 to 289.0 s, 34.0 ms apart (median), at widths 2560
  (1,853), 2304 (344), 2048 (47) and 2816 (2).
- **The shots:** the lake at 9.4–9.8 % in all 20, the light level of exp 0357 (7.9–9.1 %).
- **Each frame's depth bursts** (the 256-KiB sample, 1,557 frames cut at the pyramid's change; `raw/H1.bursts.txt`):
  - 1,227 frames have three bursts, 299 two;
  - median starts at +6.5, +8.5 and +18.7 ms; the third ends at +19.8 ms.
- **The depth memory holds a per-pixel image at the frame's width only after the frame's last burst.** The
  snapshots fall into three classes (`raw/H1.fz.txt`, `raw/H1.sx.txt`; block-row shear: 1 = no structure, well
  below 1 at the true width):
  - **Final:** 24 untorn snapshots with a clear size (2560 ×15, 2304 ×6, 2048 ×3). Shear at the true width 0.85,
    at the other widths 4–7 (medians over the first 12 of each class, here and below).
    - 16 were taken 18–22 ms into their frame, after the last burst.
    - 8 were taken at +1 ms and hold the previous frame's final: captures c04, c16 and one frame of c12.
  - **No structure:** 129 snapshots between +1 and +16.5 ms (median 9.3 ms), 68 of them torn.
    - Shear 0.97–1.23 at every width tried, 2048 to 3840: no image at any of those sizes.
    - Zero words: median 6.9 % (2.8–19.6 %).
    - This fits compressed depth tiles that the last burst expands. TODO(verify): the expanding pass is not named,
      and the HTILE was not read.
  - **Flat:** 56 snapshots at +1.1–1.3 ms, in 56 of the 71 frames.
    - Not the previous frame's final.
    - Shear near 0 at 2816 and 3840 (block-row steps vanish), 1.7–1.8 at 2560 and 3328.
    - 0.6 % zero words.
    - Another image overwrites the depth memory between most frames. What writes it is not known.
- **No final has a hole.** All 24 finals have a depth-0 share of 0.000 in the lake window. So in depth, H1 was clean
  in every frame sampled, over the whole 60 s, though the shots read 9.4–9.8 %. No hole frame was captured, and the
  hole-against-clean comparison could not be made.
- **No pixel is carried over between frames.** In all 8 pairs of consecutive frames' finals at the same width
  (c03, c04 ×2, c09 ×2, c16 ×3), the share of lake-window pixels bitwise equal to the previous frame is 0.000. The
  frozen view's depth changes in every pixel each frame. No pair caught the same frame twice (an s2 and the next
  s0).
- **The depth image's readers** (`raw/H1.fi.txt`; 18,115 `_FIND` hits in 2,245 frames, 8 per frame, max 11):
  - Seven programs bind the depth image's T# base, all in every frame and all after the frame's full-screen water
    draw. In journal order (the median position in the frame):
    1. PS 0x11d4d01800 (0.00);
    2. CS 0x11d02d0a00 (0.12);
    3. PS 0x11d020ce00 (0.25);
    4. PS 0x11d1d02d00 (0.38);
    5. CS 0x11d0404200 (0.50; exp 0099's final composition);
    6. CS 0x11d039cd00 (0.62);
    7. last, CS 0x11d0288800 twice (0.78).
  - The three PS draws render into colour target 0x113d770000.
  - CS 0x11d0288800 also binds the pyramid (exp 0274), so it is most likely the pyramid's builder. Bindings do not
    give the direction. It also binds the depth image through user data 8, right after the full-screen draw, in 51
    frames.
  - Nothing binds the depth image after CS 0x11d0288800 and before the next frame's full-screen water draw, which is
    where the lake's writers run.
- **Exp 0357's test on its clear reads only** (`raw/re0357.txt`):
  - 30 of its 49 hole reads, and 25 of its 69 reads without holes, had no clear size. That is what a read taken
    before the frame's last burst gives.
  - On the 63 clear reads, late culling: holes 5 of 19, none 11 of 44 (p 1.0); A 1 of 8, B 4 of 11 (p 0.34). So
    F441 holds.

**Verdict.**
- **In clean frames, the lake does not take any part of its depth from the previous frame.**
  - Every lake-window pixel's final depth is new in each frame (8 consecutive pairs, 0 % bitwise equal).
  - In 56 of 71 frames, the depth memory holds another image at the frame's start, so nothing of the previous
    frame's per-pixel depth survives into it there.
  - The last pass that binds the depth image before the next frame's lake draws is CS 0x11d0288800, most likely the
    pyramid's builder. The pyramid's generation does not decide the holes (F441, still standing on clear reads).
  - So F372's history fill through the depth image is not supported.
- **Hole frames were not tested:**
  - H1 had none among its 24 finals.
  - The planned burst-by-burst view of which half is written when cannot work in memory. Until the frame's last
    burst, the depth holds no per-pixel image.
- **A method fact for every earlier depth read:** a read taken before the frame's last burst has no per-pixel depth
  at the frame's width. Decoded at the journal's width, it shows scattered zeros (median 6.9 % of words here).
  - Hole labels must come from reads with a clear size.
  - Exp 0357's late-culling result holds on those.
  - Exp 0354's two-state split (F436) included 84 reads without a clear size and should be re-checked on clear
    reads. F342's X and Y themselves came from 20 clear reads only.
- **Limits:**
  - one run, clean in depth;
  - `_FIND` sees the T# base only in user data and the first 64 dwords of the tables they point at. Bindless or
    deeper descriptors would not show.
  - Other images (the G-buffer 0x113f230000, the linear-depth image 0x113cb40000, colour targets) were not searched
    as a history source.
- **Next for Q21:** a run that is patched in depth, with snapshots only after each frame's last burst (from about
  +21 ms) in consecutive frames. Per frame it would give the hole state, whether the hole cells were 0 in the frame
  before, and what the memory holds at the frame's start. Before that, F436's split on clear reads only.
