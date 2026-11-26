# 0286 — The night lake's hole states: are exp 0285's X/Y separators more than chance?

**Question.** Exp 0285 (F346) searched every journalled value of exp 0283's two runs for one that tells X frames from
Y frames. It found separators in a few writer tables per run, never in both runs. W283a at offset 0 had 31 dwords in
the late-draw tables of 0x11d1d88300, 0x11d1dd6400 and 0x11d29ea100, and at offset +1 6 dwords of 0x11d373f600. W283b
at offset −1 had 180 dwords around one table of 0x11d29c4500. Each was on a few frames grouped by window. Are they
more than chance? Do the candidate writers' draws differ in number or order between X and Y frames? Does either
run's separators separate the other run's frames?

**Setup** (the GO, top session 2026-10-24 ~23:12: read-only on the two kept journals, about 2 min, no emulator).
- BC-250, 23:15:22–23:16:22. `~/bc5-work/exp0286` was claimed at 23:15 and holds `xy0286.py` and its outputs. Our
  analysis-only lock line was removed at 23:16:22.
- `xy0286.py` takes over xy0285.py's code for the parsing, frames, lag (W283a 45 ms, W283b 60 ms), st0283.py's
  cell-share labels and per-frame values. Then:
  1. **Draws:** for every frame of a window with a labelled frame, the number of draws of each candidate writer and
     of all writers, and the candidates' draw order (A–E: 0x11d29ea100, 0x11d1d88300, 0x11d1dd6400, 0x11d29c4500,
     0x11d373f600; printed below 60 draws).
  2. **Permutation test** of the exact separators (xy0285.py's rule), at offsets −1, 0 and +1. The real labels are
     set against two nulls:
     - 100 free shuffles;
     - every rotation of the labels along the labelled frames' time order. This is stricter, as it keeps runs of
       one state together, the way the real labels come.

     A table's dwords move together, so the count is also given in distinct tables (or scalar keys). It runs
     W283a's separators in W283b and W283b's in W283a.
  3. **Cross-run:** each "SEP" key of the other run's xy0285.py output, in this run.
- Checked offline on exp 0283's synthetic journal: the planted separators are found, and they separate the
  (identical) synthetic run of the cross-run check.
  - On strict alternation, every even rotation reproduces the labels, so the rotation null matches the real count
    there.
  - That makes it conservative for periodic labels. The real labels come in runs, not strict alternation.
- Outputs: `raw/W283a.xy6.txt`, `raw/W283b.xy6.txt`. Runtime 14 s and 15 s.

**Result** (`raw/`).
- **The candidate writers draw the same in X and Y frames.**
  - W283a, whole labelled frames (2 X, 8 Y):
    - 0x11d29ea100 has 41 draws, 0x11d1d88300 13 and 0x11d1dd6400 7, in every X and Y frame;
    - 0x11d373f600 has 16 in both X frames and 16 or 19 in the Y frames;
    - all writers: 91–92 in X, 92–95 in Y.
  - In w230, the frames' 16 or 19 draws of 0x11d373f600 alternate irregularly across X and Y frames.
  - W283b, whole labelled frames (9 X, 5 Y): every writer count is the same (69 in all). The candidates' order is
    the same in all of them (DDDDBBBBCBCBBCBCBCD); partial first frames only lack the leading DDDD.
- **The separators are not more than chance** (counts, then distinct tables):
  - W283a, offset 0: 31 separators in 20 tables. Free shuffles reach as many in 9 % of cases (tables 6 %);
    rotations in 17 % (tables 8 %).
  - W283a, offset +1: 6 in 6 tables. Shuffles 18 % (16 %), rotations 25 % (17 %).
  - W283b, offset −1: 180 separators in 4 tables. As many dwords never came by chance (shuffles max 158, rotations
    max 4), but 4 tables did in 8 % of both nulls. The dwords of those tables move together.
  - W283b, offsets 0 and +1: none.
  - W283a, offset −1: too few X frames (2).
- **Neither run's separators separate the other run's frames.**
  - 0x11d29c4500 does not draw at all in W283a. 0x11d29ea100 and 0x11d373f600 do not draw in W283b. The writer
    sets differ between the runs (run content, as exps 0251/0253/0261 saw).
  - The one candidate dword present and varying in both runs is 0x11d1d88300's second-to-last draw, GS user data 12
    table, dword 3. It does not separate W283b's frames at any offset.

**Verdict.**
- **Exp 0285's X/Y separators are chance-level candidates, not findings.** Under both nulls, counted by table, chance
  reaches them in 6–25 % of cases. The candidate writers have the same draw counts and order in X and Y frames. None
  of the candidates carries over to the other run.
- **Nothing in the journalled command stream tells X frames from Y frames:** not the draws, their order, arguments
  at submission, packets, depth registers, user data or tables (exps 0283, 0285, 0286).
- With F313/F320/F323 (the same draws and constants in clean and patched frames), the hole state is decided GPU-side.
  Candidates are the data the writers read on the GPU, or the indirect arguments the GPU writes. Exp 0283 found the
  arguments at completion missing; the journal reads them only at submission.
- **Next (step 2 of the top session's plan; needs its own GO with runs):** read the depth writers' GPU-written
  indirect-argument buffers from memory along with the depth image, in bursts timed to frames as in exp 0283, and set
  their values against the read states.
