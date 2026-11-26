# 0293 — The night lake writers' argument steps against the group counts of the passes that bind their buffers

**Question.** Exp 0292 (F355): the lake writers' indirect arguments sit in 1–4 MiB buffers. A small chain of compute
passes handles them:
- CS 0x11d0376b00 gets the bases in its user data;
- CS 0x11d0415700, 0x11d0375600, 0x11d04f0c00 and F310's fill kernel 0x11d0288a00 bind them as buffers;
- CS 0x11d0375600's DISPATCH_DIRECT group counts, set by the CPU, change between frames in the frozen view.

Exps 0287/0289 (F350, F352): the arguments change in steps, never without the depth, and every adjacent hole switch
seen fell on a step. Do the argument steps come with changes in these passes' per-frame group counts, CS
0x11d0375600's above all?

**Plan** (the top session, 2026-10-25 ~02:45: prepared offline; one bench run in the morning queue).
- **Run W293a**, the usual frozen-view lake bench.
  - Binary and journal: exp 0251's private binary (5227c025) with exp 0283's journal switches and exp 0292's
    `_FIND=934d3900,935d3900,93ad3900`. Within each journal window, every dispatch whose user data or first-level table
    holds a base is journalled with its packet ("pkt c0031500 X Y Z") and, on the "find ud cs" line, the journal time.
    No FIND_VA (W292a's clean run may have come from its extra work; it is not needed here).
  - Reads: `capa0293.py` (exp 0289's reader, `CAPA_PYRAMID=0`): 12 bursts at the windows' starts, 8 × (the argument
    ranges, the depth image) 30 ms apart, then the G-buffer.
- **`cnt0293.py`:**
  - frames from the journal (each up to a full-screen draw within one window, timed by its "bake draw" line);
  - per frame, each candidate pass's group counts since the previous full-screen draw;
  - the journal time turned into wall clock by the median offset of the "bake draw" lines;
  - for each pair of consecutive argument reads of a burst, the frames they show (the latest one 50 ms before each
    read, exps 0283/0287) and two flags: whether the arguments changed, and whether each pass's per-frame counts
    changed between those frames;
  - a two-by-two table per pass, and the per-window letter sequences of the frames' counts.
  - Checked on a synthetic journal whose argument record follows CS 0x11d0375600's count: 8 pairs with both changed
    and 10 with neither for that pass, "arguments only" for the others.
- **`rd0293.py` / `chg0293.py`** (exp 0289's): the hole switches between consecutive reads, to set against the count
  changes as well.
- Rules as before: our own lock line, kernel stream, the run stopped at any new amdgpu line, saves reference
  c0ee58b92c0cadc2, reads summarised then deleted.
- Not in this experiment: dropping a pass (the top session: only after this one, with the maintainer's explicit OK).

**Setup as run** (the top session's GO of 02:49; W293a 02:50:36–02:57 CEST; the box clock went back to CET at 03:00
CEST, so later box times read an hour earlier).
- BC-250, boot 831e5915. Exp 0251's private binary (5227c025), the bench's private save copy, the 3-s dmesg poll and
  the kernel stream (`raw/W293a.kern.txt`), under our own lock line.
- Journal: exp 0283's switches plus `BC5_DIRECT_DRAW_JOURNAL_FIND=934d3900,935d3900,93ad3900`, as planned
  (`raw/W293a.ab.txt`); journal `~/bc5-data/captures/play-20261025-0250/gc` (kept, 223 MB): 384 windows, 190
  full-screen draws, 1,515 candidate-pass dispatch hits, 95 argument records.
- Reads: `capa0293.py` with `CAPA_PYRAMID=0`, 12 bursts of 8 × (argument ranges, depth) 30 ms apart plus the G-buffer
  (`raw/W293a.capa.txt`); MemAvailable 1,098–1,393 MiB, so the depth was held in memory. The reads (2.6 GB, in
  `~/bc5-data/priv/exp0293`) were summarised by `rd0293.py`, `chg0293.py` and `cnt0293.py` and deleted.
- Saves c0ee58b92c0cadc2 before and after (snapshot taken and removed, nothing restored).
- `cnt0293.py` was extended after the run: a second table sets each pair's argument change against whether a
  full-screen draw falls between the frames the two reads show, for lags L 0–100 ms. Its first regular expression
  was also fixed during the analysis (the find line reads " cs ", not "| cs").

**Result** (`raw/`).
- **Box state.** No fault, timeout or reset: 0 fault lines (`raw/W293a.out`), only routine lines in
  `raw/W293a.kern.txt`, the amdgpu dmesg count 446 before and after, no new devcoredump (newest still
  `20261025-024243-devcd6.txt`, another session's run).
- **The lake was patched in all 26 shots** (15.7–32.1 %, `raw/W293a.bench.txt`).
- **The passes' per-frame group counts** (`raw/W293a.cnt.txt`; 19 windows of 10 frames):
  - CS 0x11d0375600 runs twice per frame, one dispatch of 73–105 groups and one of 937–1061 (W292a: 97–102 and 1105–1111). The pair differs from
    frame to frame almost everywhere: at least 32 distinct pairs over 190 frames (the letters wrap after 26, so the
    letter rows undercount).
  - CS 0x11d0376b00 (1, 1 and 2 groups), CS 0x11d0415700 (32) and CS 0x11d04f0c00 (4; 5 in W292a) are the same in every frame
    after a window's first one. That first frame only counts the dispatches after the window opened.
  - F310's fill kernel CS 0x11d0288a00 follows the render size (2752–7168 groups), in runs of frames.
- **Counts against argument changes** (L 50 ms, 39 pairs of consecutive argument reads matched to frames of one
  window):

  | pass | both changed | arguments only | counts only | neither |
  |---|---|---|---|---|
  | CS 0x11d0375600 | 5 | 17 | 5 | 12 |
  | CS 0x11d0376b00 | 4 | 18 | 3 | 14 |
  | CS 0x11d0415700 | 0 | 22 | 0 | 17 |
  | CS 0x11d04f0c00 | 4 | 18 | 3 | 14 |
  | CS 0x11d0288a00 | 5 | 17 | 3 | 14 |

  CS 0x11d0375600's row equals the new-frame table at L 50 below, cell for cell. Its counts changed across every
  matched frame boundary, so the row only says whether a frame boundary lay between the reads. The other passes'
  "counts changed" pairs are window-start frames and render-size steps.
- **Argument changes against a new frame** between the frames the two reads show:

  | L | changed, new frame | changed within one frame | new frame, unchanged | neither | pairs |
  |---|---|---|---|---|---|
  | 0 ms | 15 | 15 | 0 | 28 | 58 |
  | 25 ms | 7 | 17 | 6 | 18 | 48 |
  | 50 ms | 5 | 17 | 5 | 12 | 39 |
  | 75 ms | 5 | 11 | 5 | 10 | 31 |
  | 100 ms | 4 | 10 | 1 | 10 | 25 |

  - At L 0, every pair with a full-screen draw submitted between its two reads had changed arguments (15 of 15), and
    every pair with no change lay within one frame (28).
  - With L ≥ 25 ms, new frames without a change appear (6, 5, 5, 1). So exps 0283/0287's 45–60-ms lag, found for
    the depth and the shots, fits these argument reads worse than L 0.
  - The 15 changes within one frame at L 0 fit work the GPU runs after the CPU submitted the frame. Many are a
    step's second half: the depth and the arguments change over two consecutive pairs, a large change (12–70
    records) often followed by a small one (2–4) (`raw/W293a.chg.txt`, per-burst rows).
- **Plateaus and frame period.** In bursts b10–b12 the depth held for three reads, changed over the next one or two,
  and repeated every four reads: a period of about 120 ms. 15 of 58 pairs spanning a submitted frame at L 0 fits a period of about
  115 ms. In bursts b01 and b02 the arguments changed in 5 and 6 of 7 pairs, faster. The frame period was not measured from the journal.
- **Depth and arguments** (`raw/W293a.chg.txt`, 84 consecutive pairs): both changed 44, depth only 12, arguments
  only 1, neither 27.
  - The one argument-only pair (b04 z2–z3, 3 records, 0 depth words changed) follows a pair in which both changed
    (65 records). It may be the tail of that step: within one read the arguments are read first, then the depth over
    7–18 ms. It is the first such pair in 420 (0 of 336 in exps 0287/0289).
- **Hole switches** (`raw/W293a.chg.txt`, `raw/W293a.rd.txt`): 12 clear same-size pairs, one switch (b03 z0–z1,
  phi −0.492, 22 records changed). The 11 stable pairs had no record changed, and all of them lie on plateaus.
  - The rd families: X 9 clear reads, Y 3 (one burst, b10), 6 more families of 1–7.

**Verdict.**
- **CS 0x11d0375600's group counts are not a test of the steps.** They differ in almost every frame, so across every
  matched frame boundary they changed. Its table only repeats whether a new frame lay between the two reads. F355's
  lead does not tell the argument steps apart from frames. The other binding passes keep their counts from frame to
  frame (the fill kernel moves with the render size).
- **The argument changes look like per-frame rewrites.** At L 0, each of the 15 submitted frames seen between two
  reads came with an argument change, and no pair stayed unchanged across one. The changes inside one submitted frame
  fit the GPU running that frame's passes later, often over two reads.
  - This recasts F350/F352's "steps": if those runs' frames were as long as this journalled run's (about 120 ms),
    reads 30 ms apart see plateaus within a frame and changes between frames.
  - The hole switches falling on argument changes (4 before, 1 here) then follow from switches happening at frames.
    They do not single out the arguments as what carries the hole state.
  - The stable-hole pairs with no change (29 in exp 0289, 11 here) are plateaus within one frame. Exp 0287's single
    pair that kept the holes across 42 changed records fits this reading.
- **Caveats:**
  - 58 of 84 pairs were matched to journalled frames at L 0, and the journal sees 10 frames per window.
  - The frame period is inferred from the plateaus, not measured.
  - One run, patched throughout.
  - The one argument-only pair weakens "never without the depth" to "almost never". It is likely a read-order effect.
- **Next:**
  - Whether the arguments' values (not only their change) differ between frames that keep the holes and frames that
    switch them. That needs per-plateau argument values against the hole family. Reads of a run with slower frames, or
    one read per frame, would give clean plateaus to label.
  - The drop-list intervention (CS 0x11d0376b00 or 0x11d0375600) is still the way to name the argument writer. It
    needs the maintainer's explicit OK, since it changes what the GPU runs and could fault.
