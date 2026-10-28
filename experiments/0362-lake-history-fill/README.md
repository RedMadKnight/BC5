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
