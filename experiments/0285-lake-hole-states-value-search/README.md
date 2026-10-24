# 0285 — The night lake's two hole states: every journalled value, X frames against Y frames

**Question.** Exp 0283 (F344): the lake's hole state, X (the shots' patch cells) or Y (elsewhere), holds for one to
at least eight frames and switches irregularly. The depth writers' two argument slots do not decide it, and none of
the 100 per-frame values listed in 0283 separates X frames from Y frames. That list was partial, and the search over
every journalled value never ran, because the analysis's own family naming labelled too few frames (in W283b it
picked a one-read family as Y). With exp 0283's cell-share labels (`st0283.py`), does any value in the submitted
command stream tell X frames from Y frames?

**Plan** (the grant, top session 2026-10-24 ~22:40: read-only, about 2 min, on the GO; no emulator).
- Inputs on the box: exp 0283's two journals (`~/bc5-data/captures/play-20261024-2210/gc`, W283a;
  `play-20261024-2224/gc`, W283b) and the read summaries `~/bc5-work/exp0283/W283?.reads.json` (also in exp 0283's
  `raw/`). No reads are taken; the reads themselves were deleted in exp 0283.
- `xy0285.py`, per run, with exp 0283's lag (W283a 45 ms, W283b 60 ms):
  - xy0283.py's journal parser and frame rules;
  - st0283.py's labels: each read at its frame's size, X-like when at least half the cell mask is at depth 0, Y-like
    at 0.3 or less with holes; a frame is X or Y when its reads agree;
  - every journalled value per frame:
    - the full-screen draw's depth registers, size, user data and tables;
    - the writers' draw counts;
    - each writer draw's packet, depth registers, arguments at submission and at completion, user data and tables.
  - Writer draws are keyed by shader and their order counted from the end of the frame, so a window's first,
    possibly partial frame lines up.
  - Each search is run three ways, since a read's frame is known to about one frame: frame j's label against the
    values of frame j − 1, j and j + 1.
  - Exact separators: no shared value, at least 3 frames of each state, and repeating values (so a counter does not
    count).
  - Near separators: at most 4 values, mapped to the states right in at least 90 % of the frames.
- Checked offline on exp 0283's synthetic journal (frames alternating X/Y, one table dword carrying the parity):
  - offset 0 finds the parity dword and the argument values;
  - offsets ±1 find them inverted, as strict alternation gives;
  - the frame counter is not reported.
- Box rules: the GO first (the maintainer's DS4 test holds the box from 22:35), our own analysis-only lock line, no
  emulator running, nothing written outside `~/bc5-work/exp0285`; summaries only.

**Setup as run.**
- BC-250, 2026-10-24 23:08:40–23:09:04, on the GO of ~23:05 (the maintainer's test had ended at 23:04).
- No emulator ran. The lock line was our analysis-only line. `~/bc5-work/exp0285` was claimed at 23:08 and holds
  `xy0285.py` and its two outputs.
- `xy0285.py` ran on each journal (283 MB and 230 MB) with exp 0283's read summaries and lags (45 and 60 ms), 15 s in
  all. Outputs: `raw/W283a.xy5.txt` and `raw/W283b.xy5.txt`.
- Both prints are capped (40 separators and 30 near separators per offset). The counts are complete; the lists
  are not.

**Result** (`raw/`).
- **Labelled frames.**
  - W283a: 5 X frames (3 of them a window's partial first frame) and 8 Y frames. The X frames come from four
    windows; 7 of the 8 Y frames are in one window (w230, frames 1–8 except 5). One frame has both X and Y
    reads.
  - W283b: 15 X frames (6 partial) and 6 Y frames (1 partial); 8 frames have both.
- **W283a:**
  - Offset 0 (each frame's own values): 75,912 keys compared, 11,260 vary among these frames, 31 separate.
    - All 31 are dwords of the tables of three writers' late draws: 0x11d1d88300's second-to-last, 0x11d1dd6400's
      third-to-last, and the third- to eighth-to-last draws of 0x11d29ea100.
    - Each has one value in all X frames and other values in the Y frames.
    - They change between the X frame and the Y frame of both observed X→Y switches (w177 frames 1→2, w230
      frames 0→1).
  - Offset +1: 6 dwords of the tables of 0x11d373f600's 17th–19th-to-last draws separate; those draws exist in only
    3 frames of each state.
  - Offset −1: too few X frames (2).
  - No near separators.
- **W283b:**
  - Offsets 0 and +1: none of about 56,700 keys (7,200 varying) separates, and none comes near.
  - Offset −1 (the previous frame's values): 180 dwords separate and 28 come near.
    - The 40 printed separators are all dwords of one table (PS user data 20) of 0x11d29c4500's second-to-last draw.
    - The near separators are in the same writer's tables for its 2nd- to 5th-to-last draws.
    - That draw exists in only 5 frames of each state.
- **Nothing separates in both runs.** The separating tables and offsets differ between the runs, and none of
  W283a's 31 separates W283b's frames at offset 0.
- **Caveats.**
  - The labelled frames are few, and W283a's X and Y frames are grouped by window. A value that changes over time
    within a window can then separate by chance; with 5 against 5 frames, one two-valued key splits them perfectly
    by chance about 1 time in 126.
  - No permutation test was run.
  - Writer draws are keyed by their order from the frame's end. A frame with one more or one fewer draw of that
    shader shifts the keys, so a separator can also mean a different draw count rather than a different value.

**Verdict.**
- **No value in the submitted command stream separates X frames from Y frames in both runs.**
- The full search finds separators only in one writer's tables per run and offset: three writers' late-draw tables
  in W283a at offset 0, one table of 0x11d29c4500 in W283b at offset −1. At these frame counts, and with the frames
  grouped by window, they are candidates, not findings.
- The strongest are W283a's 31 dwords, which change at both observed X→Y switches. That is two events.
- Together with exps 0261/0262/0283 (draws, arguments and constants the same between states, and the slot not
  deciding), the decider is most likely not in what the CPU submits. It may be GPU-side, in data the writers read
  or the arguments the GPU writes.
- **Next:**
  - A read-only check on the same journals (~2 min):
    - a permutation test of the separator counts;
    - per frame, the draw counts and order of 0x11d29ea100, 0x11d1d88300, 0x11d1dd6400 and 0x11d29c4500 against the
      states;
    - whether W283a's 31 dwords follow the state in W283b at all.
  - Then the GPU side: the writers' GPU-written indirect arguments, read from memory along with the depth (exp 0283
    found their values at completion missing).
