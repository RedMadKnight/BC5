# 0086 — the copies around the second title's menu: per-frame uploads from CPU memory

**Question.** Experiment 0085 suspected that the glyphs first needed by the menu are uploaded
into the font atlas by a copy whose source the title reuses too early. What copies run while the
menu appears?

**Setup.**
- Run 339 (`run339.sh`, 2026-10-14 15:34): run 327's settings (flips deferred), plus
  `BC5_DIRECT_IB_DUMP=1:400000:76:20000`.
- That dumps every buffer from t = 76 s on, 20,000 buffers in all, about 7 s. The frame rate dips
  at 78–82 s while the menu appears. The dumps are private.
- `dmascan.py` lists `DMA_DATA` and `COPY_DATA` packets by buffer kind, destination (MiB) and
  selectors. The `DMA_DATA` field layout is marked TODO(verify) in the script.
- Run 338, the same with an earlier 1.4 s window, is not used: the menu had not appeared yet.

**Result** (`raw/run339-copies.txt`):
- No one-off upload appears in the window. The only single copy is 768 bytes.
- Every frame, CP DMA copies from CPU-written memory (sources around 0x1122… and 0x1124…, a
  different address each time) into fixed GPU destinations:
  - 720,896 bytes into 0x11f0d1cc00: 320 times in compute buffers, 12 times in graphics
    buffers;
  - 12,288 bytes into 0x11e0e1c200: 166 times;
  - 5,232 bytes into 0x11f8c94600, and from there on to 0x11d2d7…: 165 times each.

**Verdict.** Inconclusive.
- There is no separate glyph-atlas upload to blame.
- What the title does have are large per-frame uploads from rotating CPU staging. If its guard
  for reusing a staging slot is one our deferred flips signal too early, the GPU copies data
  that is already overwritten.

Candidate fix to test, TODO(verify):
- the host snapshots the source of such a CP DMA copy at submission and points the copy at the
  snapshot;
- or the copy is run on the CPU at submission when its job would start late.

Neither is written yet. The second title's shortcut uses undeferred flips meanwhile
(experiment 0081).
