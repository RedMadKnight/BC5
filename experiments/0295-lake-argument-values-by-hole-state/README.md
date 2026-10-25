# 0295 — The night lake writers' argument values in frames that keep the holes and frames that switch them

**Question.** Exp 0293 (F357): the lake writers' GPU-written indirect arguments are rewritten every frame. At L 0,
every frame submitted between two reads changed them, and no unchanged pair crossed a frame. So the finding of exps
0287/0289 (F350/F352), that the hole switches fall on argument changes, follows from switches happening at frames. It
does not show that the arguments carry the hole state. Do the argument **values** differ between frames with
different holes? Concretely: are frames with the same hole family (or more alike holes) more alike in their argument
records than frames with different ones, and does any record or dword follow the hole state or the depth-0 share?

**Plan** (approved by the top session 2026-10-25 as option 1 of `exp0293-morning-next.md` in the shared notes; one
bench run tonight after the BVH session's exp 0294 chain, on a BOX REQUEST).
- **Run W295a, the W293a setup with more bursts.**
  - Bench and binary: the usual frozen-view lake bench, exp 0251's private binary (5227c025), the bench's private save
    copy.
  - Journal: exp 0283's switches plus `_FIND=934d3900,935d3900,93ad3900`, exactly as W293a, so the frames run at the
    same pace (about 120 ms in W293a, which gives reads 30 ms apart their plateaus).
  - Reads: `capa0295.py` (exp 0293's reader, `CAPA_PYRAMID=0`, HOLD 1024 MiB). 16 bursts instead of 12, since the
    frozen view lasts past W293a's twelfth burst. Each burst is 8 × (the argument ranges, the depth image) 30 ms
    apart, then the G-buffer.
- **`pl0295.py`** (new):
  - Plateaus: each burst is cut into runs of identical depth reads, one per frame. In the frozen view the depth image
    changes as a whole from frame to frame (millions of words per change, exp 0293's `raw/W293a.chg.txt`).
  - What each plateau gets:
    - from `rd0295.py`'s JSON: the render size, clarity, depth-0 share and hole family (families of clear reads, as
      exps 0283–0293);
    - its depth-0 set in the lake window (chg's de-swizzle);
    - the argument records read just before its first depth read, and whether they stay the same through it.
  - Over pairs of labelled plateaus from different bursts (≥ 10 s apart, never neighbouring frames):
    - the share of varying records with equal values, same-family pairs against different-family pairs, with a
      permutation null (labels shuffled) and a split by render size;
    - a Mantel test: Spearman of the pair's hole phi with that share, plateaus shuffled;
    - a drift check: both against the time between the plateaus;
    - per record: equal in same-family pairs minus in different-family pairs, against the null of the largest;
    - per record and dword, and per dword's sum: Spearman with the depth-0 share, against the null of the largest;
    - the two first tests again on plateaus of 2+ reads whose arguments stay the same through them.
  - Checks:
    - `--selftest` runs the segmentation and the statistics on synthetic plateaus, in pure Python, done on the
      laptop. With five records that follow the hole state in 70 % of frames, the result is same 0.109 against
      different 0.049, p 0.0025 (400 permutations), Mantel +0.589 (p 0.0025), and the five records ranked first. With
      none, the difference is −0.007 (p 0.94) and Mantel −0.118 (p 0.97).
    - `mk0295.py` writes a synthetic capture of 3 bursts for the reading path, to be run on the box before the run
      (numpy is in the ubuntu distrobox only).
  - Output: summaries only. The plateaus' argument values go to a JSON in `~/bc5-data/priv`, deleted with the reads.
- **`cnt0295.py`** (exp 0293's `cnt0293.py` plus the frame period): the median and quartiles of the time between
  consecutive full-screen draws of one window, on W295a's journal and on W293a's kept one. F357 inferred about 120 ms
  and did not measure it. It also repeats F357's table of argument changes against new frames on W295a.
- **`rd0295.py` / `chg0295.py`** (exp 0293's, unchanged): the families and the pair tables, as before.
- Rules as before:
  - our own lock line, the kernel stream, the run stopped at any new amdgpu line;
  - the saves reference c0ee58b92c0cadc2, snapshot first, restore only if changed;
  - reads summarised, then deleted.
- Not in this experiment: the drop-list intervention (`BC5_DIRECT_SKIP_PGM=11d0375600`). It goes to the maintainer
  with the morning summary.

**Setup as run** (the top session's GO of 08:43 CET, relaying the maintainer's "Puść najpierw pomiar jeziora 0295,
zagram później"; the box back since 08:41 after the 02:19 machine-down in exp 0294, a fresh boot, 68645b54).
- **Prep, 08:45.** Our lock line, `~/bc5-work/exp0295` claimed, saves c0ee58b92c0cadc2 checked and snapshotted (57
  files), the scripts copied.
  - The synthetic check of `pl0295.py`'s reading path in the distrobox (`mk0295.py`) came out as built: plateaus z0-2,
    z3-5 and z6-7 per burst, and record 0x1000 first (equal in 13 of 13 same-family pairs, 0 of 14 others, p 0.005).
  - Exp 0251's binary (5227c025) has no ray-tracing switch (0 `KYTY_BC5_RT` strings). So W295a ran with RT on, like
    W293a and every lake-bench run since exp 0283; F341 found RT off does not clear the lake anyway.
- **Run W295a, 08:45:52–08:52:17.**
  - The W293a setup, as planned: the bench's private save copy, the 3-s dmesg poll, the kernel stream
    (`raw/W295a.kern.txt`).
  - `capa0295.py`: 16 bursts, 08:48:36–08:50:24 (`raw/W295a.capa.txt`). MemAvailable was 1,026–1,260 MiB, so the
    reads were held in memory. 3 argument ranges, 1,728 bytes, 44 records (W293a: 95).
- **Analysis, 08:52–08:56, no emulator.** `cnt0295.py` (also on W293a's kept journal), `rd0295.py`, `chg0295.py`,
  `pl0295.py`.
  - Added after seeing the run: `cl0295.py` (patched against clean frames, below) and a check of `pl0295.py`'s share
    correlation within one render size (`raw/W295a.size.txt`; a short stdlib snippet run on the box, its output kept).
- **Cleanup.** The reads (3.5 GB) and the priv plateau JSON deleted. Saves c0ee58b92c0cadc2 after (nothing restored,
  snapshot removed). Lock emptied, `BOX-QUEUE` line 71, released 08:56:39.

**Result** (`raw/`).
- **Box state.** No fault, timeout or reset: 0 fault lines (`raw/W295a.out`), the amdgpu dmesg count 125 before and
  after, no new devcoredump. The kernel stream has one SELinux context line at 08:55 and nothing else.
- **The lake went from patched to clean during the run** (`raw/W295a.bench.txt`): patched in ts00–ts11 (28.4–38.9 %),
  in between in ts12–ts14 (9.3–17.1 %), clean from ts15 (3.8–5.7 %). Bursts b01–b10 fell in the patched part, b11–b16
  in the clean part (b14's first read still had holes, family F15).
- **The frame period, measured** (`cnt0295.py`, consecutive full-screen draws of one window, 171 gaps each):
  - W295a: median 92 ms, quartiles 59–138, range 30–204;
  - W293a: median 104 ms, quartiles 54–182, range 32–373.

  F357's inferred ~120 ms had the right order but not the spread.
- **F357's table, again** (`raw/W295a.cnt.txt`). At L 0: 37 pairs changed with a new frame, 3 changed within one
  frame, 2 new frames without a change, 47 neither. 84 of 89 pairs fit "the arguments change with each frame", and
  L ≥ 25 ms fits worse again (21, 13, 8 and 10 new frames without a change).
- **The scene's passes differed from W293a**:
  - CS 0x11d0375600 at 109 and 755–763 groups (5 pairs);
  - CS 0x11d0376b00 at 1 and 1;
  - CS 0x11d04f0c00 not dispatched;
  - 44 argument records.
- **Plateaus were mostly single reads**, unlike W293a.
  - The depth changed in 103 of 112 consecutive pairs (`raw/W295a.chg.txt`: both changed 57, depth only 46, arguments
    only 0, neither 9). In most bursts a clear read alternates with an unclear one, and 111 of the 119 plateaus are one
    read long.
  - So in this run the depth region changes between frames too, and a plateau is a read, not a frame. Two clear reads
    of one burst may show the same frame (pseudo-replication; the tests only pair plateaus across bursts).
  - The subset of plateaus of 2+ reads with unchanged arguments held 1 labelled plateau, so it could not be tested.
- **Families** (`raw/W295a.rd.txt`, 35 clear depth reads with holes): X 11 (b05–b10), F14 and F15 with 6 each
  (b05–b10, b14), Y 1, and eleven single-read families (b01–b04).
- **Argument values against the hole family** (`raw/W295a.pl.txt`; 34 labelled plateaus, 11 of the 44 records vary,
  516 pairs across bursts):
  - same family 0.540 equal (65 pairs) against different families 0.531 (451 pairs), permutation p 0.39;
  - Mantel, hole phi against the equal share: +0.035, p 0.16. The drift check is small (−0.115 for both);
  - per record, the largest is 0x1193ad3940 and 0x1193ad3a20 at +0.221, p 0.058 against the null of the largest.
- **What the values do follow is the render size.** Equal share in pairs of the same size against different sizes:
  0.668 against 0.399 within a family, 0.687 against 0.449 across families.
- **Patched against clean frames** (`raw/W295a.cl.txt`; 34 patched and 17 clean plateaus, 1,212 pairs across bursts):
  - same label 0.542 against different labels 0.561, p 0.72; render size again 0.675/0.662 against 0.465/0.494;
  - per record dword, the largest AUC is 0x11935d3e00 dword 0 at 0.711 (patched higher), p 0.040 against the null of
    the largest, then 0x11935d3dc0 at 0.659;
  - 2 of the 11 varying records take a value in clean frames that no patched frame has; 6 take a patched-only value.
- **One correlation with the hole share** (`raw/W295a.pl.txt`, `raw/W295a.size.txt`; patched part).
  - Dword 0 of 0x1193ad3940 and 0x1193ad3a20 (equal in every plateau) rises with the depth-0 share: Spearman +0.591,
    p 0.002 against the null of the largest of 11 dwords.
  - It holds within one size (+0.621 at 2048, 10 plateaus; +0.502 at 3328, 19 plateaus). The value and the size
    correlate +0.196, the share and the size +0.058.
  - But the records take only 5 distinct values in patched frames, and clean frames (no holes) do not sit lower:
    AUC 0.593.

**Verdict.**
- **The writers' argument values do not carry the hole state.**
  - Frames with the same holes are no more alike in their arguments than frames with different holes (p 0.39; Mantel
    p 0.16).
  - Clean frames do not differ from patched ones (p 0.72).
  - The values follow the render size.
  - With F357 (they are rewritten every frame), the GPU-written indirect arguments look like an ordinary per-frame
    culling result, not the place where the lake's hole state lives.
- **A weak lead, not a finding.** Dword 0 of records 0x1193ad3900 + 0x40 / + 0x120 rises with the hole share within
  the patched part, within each size too. The plateaus are pseudo-replicated, the records have 5 values, and the
  clean frames do not continue the trend, so it is noted and not followed.
- **The frame period is now measured:** about 90–100 ms median in the journalled frozen view, with a wide spread.
- **For the drop-list intervention** (`BC5_DIRECT_SKIP_PGM=11d0375600`, the maintainer's decision): after this, it
  mainly names the argument writer. It no longer tests a likely carrier of the holes, so it ranks lower than before.
- **New:** W295a caught the lake turning from patched to clean in a frozen view (ts12–ts15, bursts b09–b11), with memory
  reads on both sides of it.
- **Next:**
  - look for the carrier among the writers' other inputs: the textures and per-cell data of exp 0274, and F310's
    HTILE fill kernel CS 0x11d0288a00, which follows the render size and binds the argument buffer 0x11934d3900;
  - a run aimed at a patched-to-clean transition, comparing the depth writers' bindings and inputs just before and
    after it.
