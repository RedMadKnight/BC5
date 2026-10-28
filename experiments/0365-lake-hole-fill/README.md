# 0365 — The night lake's hole pixels: what they hold mid-frame and at the frame's end, and where a filled pixel's value comes from

**Question.** Exp 0362 (F466) found that, in clean frames, no lake pixel keeps its depth from the previous frame. The
depth image holds the frame's full image at its width only after the frame's last write burst, about +19 ms. Hole
frames were not tested: run H1 had none. This experiment asks two things (the top session's GO of 2026-10-28 ~17:05):
1. **In a run with holes in depth,** what do the hole pixels hold, and where do the values come from? In particular,
   is a lake pixel that is 0 mid-frame later filled, and if so with the previous frame's value (a history copy) or
   with a new one?
2. **Does F436's two-state split (exp 0354, run J1) still stand on clear reads only?**

**Step 2 is answered first, offline (`ra0365.py`, `raw/ra0365.txt`, from exp 0354's committed raw files).**
- J1's reads are deleted, so the split's φ cannot be recomputed. But the split's per-frame sides and each read's
  per-width summaries are committed.

| Side of F436's split | Read clarity | Frames | Hole share | φ with X | φ with Y | Shear at the frame's width | Best shear elsewhere |
|---|---|---|---|---|---|---|---|
| A | clear | 20 | 0.245 | +0.53 | +0.68 | 0.92 | 7.57 |
| A | unclear | 39 | 0.265 | +0.54 | +0.62 | 1.39 | 1.27 |
| B | clear | 20 | 0.245 | −0.01 | −0.18 | 0.93 | 6.49 |
| B | unclear | 32 | 0.275 | +0.01 | −0.18 | 1.38 | 1.24 |

- **The split does not follow clarity:** each side holds 20 frames with a clear read.
- **The unclear reads carry the same state as the clear ones.** Their φ with exp 0354's X and Y families match the
  clear reads' on each side. Yet they have no block-row structure at any width (shear ~1.3 everywhere).
- **So F436 stands, and F466 needs a correction.** A read taken before the frame's last burst has no structure in
  its non-zero content. But its zeros sit at the frame's hole pixels. They are not scattered, as F466 said. Hole
  masks from such reads are usable, and the label caution in F466 was too strong.
- This also changes what H1's mid-frame zeros may have been. In H1 they gathered, frame after frame, on the same
  3.3 % of the window, which was not 0 in the finals. That fits lake pixels that are 0 mid-frame and filled by the
  last burst. Those snapshots are deleted, so this run looks at it directly.

**What is known for step 1:**
- **H1's frame** (exp 0362, `raw/H1.bursts.txt` there): three bursts in the 256-KiB depth sample, at a median +6.5,
  +8.5 and +18.7 ms after the pyramid's mip 0 changes. The third ends at +19.8 ms. The final image is readable from
  about +20 ms; mid-frame the non-zero content has no structure.
- **Hole runs are not guaranteed.** About 1 bench run in 6 is clean (F418), and H1 was clean in depth even though
  its shots read 9.4–9.8 %. So the run may have to be repeated.

**Expectation** (per frame, in the lake window; X and Y are the hole halves of the run's hole finals):
- **History copy:**
  - Mid-frame, one half of the lake cells (X or Y) is 0.
  - The last burst fills it with values bitwise equal to the previous frame's final. Elsewhere no pixel keeps its
    value (H1: 0.000).
  - In hole frames, the filled half stays 0, or is copied from a previous final that was 0 there.
- **Late draw:**
  - The same mid-frame zeros are filled with new values, not equal to the previous final.
  - In hole frames the late draw misses them.
- **Drawn early:**
  - Mid-frame zeros only where the final is 0 (the holes). Nothing is filled by the last burst.
- **Which half is 0 mid-frame,** and whether it changes from frame to frame (period 2), is reported in every case.

**Plan** (RT ON, the standing rule; up to three runs, stopping at the first with at least 10 usable hole finals).
- **The bench:** exp 0362's (`setup0365.sh`, `bench0365.sh`, `ab0365.sh` derived from it, 0362 → 0365).
  - Launcher: `play-pkg.sh` 55531ab6 with exp 0353's five edits, checked line for line.
  - Config: RT on, MangoHud off; 20 frozen-view shots.
  - No draw journal: the frame's width comes from the final snapshot's own shear.
- **`pl0365.py`, beside it:** polls D (the 256-KiB lake sample) and the pyramid's mip 0, read-only, from the frozen
  view and the emulator's 212th second, for 85 s.
  - Every 2 s, a capture of 6 consecutive frames, two 7-MiB snapshots each, at the depth image's
    +0x300000..+0xa00000:
    - **sM:** once the frame is 9 ms old and D has been quiet for 1 ms, at the latest at 13 ms; otherwise none;
    - **sF:** once a D change at least 15 ms into the frame has been followed by 1.5 ms of quiet; failing that, at
      25 ms, flagged.
  - Torn flags as in exp 0362. A laptop dry run against a simulated three-burst frame put sM at +9.7 ms and sF at
    +21.4 ms.
- **`sn0365.py`:**
  - `reads` sizes each snapshot by its shear at widths 2048–3328.
  - `ana` uses each frame whose sF is untorn and clearly sized (2048–2816), and decodes sM at the same width.
  - The states come from the finals (FLOOR 0.03, the eigen split), with X and Y as their halves.
  - Per frame and region, the shares of: 0 mid-frame; 0 at the end; filled (0 mid-frame, not at the end); stayed 0;
    0 only at the end.
  - Per consecutive pair at one width, over the filled pixels: the share equal to the previous final (copy), and the
    share where the previous final was 0. The same equality over the other pixels non-zero in both finals is the
    baseline.
  - Which half the mid-frame zeros lean to, by φ, and how often that half changes between consecutive frames.
  - `--selftest` plants the three readings: copy → ~1, late → ~0, early → no filled pixels. It passes on the laptop.
- **`ana0365.sh`** runs `bt0362.sh` on the poll log, then `sn0365.py reads` and `ana`.
- **The reading:**
  - **History fill:** a filled share in clean frames, with copy ≥ 0.9 against a baseline near 0. The filled half and
    hole frames then say how it fails.
  - **The holes are drawn, not filled:** filled with copy near the baseline (late draw). Or no filled pixels, with
    the holes already 0 mid-frame (drawn early). The fill reading is rejected either way.
- **Rules:**
  - the guard: an empty BOX-LOCK, our own lock line, no emulator. Exp 0360's chain runs until about 17:31; exp 0364
    (the bvh session) is queued after it, and we take the box after both.
  - the kernel stream to the laptop; stop at the first reset;
  - live saves compared only;
  - snapshots and shots deleted after the analysis, unviewed.

**Setup as run** (the top session's GO of 2026-10-28 ~17:05, and its slot of 18:5x: the box once exp 0367's lock
cleared, done by ~19:45; build 1000ad2a; launcher 55531ab6).
- **17:05–19:16.** The box was busy: exp 0364 (the bvh session) until its STOPPED line of 18:34, then exp 0367. A
  read-only laptop watcher checked the lock, `pgrep` and the queue's last line, and cleared at exp 0367's "done" line
  (19:16:15).
- **19:16:29.** Our lock line went into the empty BOX-LOCK, `~/bc5-work/exp0365/CLAIM.txt` was written and a
  BOX-QUEUE line added. Live saves 41a5a36fffb4f8d4.
  - `setup0365.sh`: `play-pkg-0365.sh` b8cd25f5 with exp 0353's five edits (`raw/play-pkg-0365.diff`);
    `input-0365.cfg` 1666716f, RT on, MangoHud off (`raw/input-0365.cfg`).
  - `sn0365.py --selftest` passed on the box (copy 1.0, late 0.0, early: no filled pixels).
  - The kernel stream ran throughout (`raw/kernel-stream.txt`: four IPv6 lines, no amdgpu line).
- **K1, 19:16:55–19:21:59** (`raw/K1.ab.txt`, `raw/K1.out`): binary 1000ad2a, RT on (0 ray-tracing-off lines), one
  ring (0 compute-ring lines), no draw journal, 20 frozen-view shots. The shots read 29.4–33.2 % patch: a heavily
  patched run.
- **`pl0365.py K1 85 … 212 2.0 6`** (`raw/K1.pl.txt`): polling from the frozen view at 212.0 s. It stopped after
  82.2 s, when the bench ended and dropped its lock line.
  - 1,834,000 polls at a mean 0.045 ms; the largest gap, 581 ms, was a capture being written;
  - D changes 23,656, P changes 2,807, 2,161 frames;
  - 33 captures, 396 snapshots, 25 torn (23 sM, 2 sF). sM came at a median +9.2 ms, sF at +20.9 ms; 193 sF followed
    a late burst, 5 came at the 25-ms cap.
- **Analysis on the box, 19:22–19:25:** `ana0365.sh K1` (`raw/K1.bursts.txt`, `raw/K1.reads.txt`, `raw/K1.ana.txt`),
  then `x0365.py` (`raw/K1.x.txt`).
- **Changes after seeing the data:**
  - `x0365.py` was written after `sn0365.py ana` showed that filled pixels never equal the previous final. It
    compares the mid snapshot itself with the previous final and with this frame's final, at the final's width.
  - The run had no clean frames (150 of 150 labelled finals have holes), so the plan's copy test "in clean frames" had
    none. It ran on the hole frames' 138 consecutive pairs instead.
- **19:25:29, release:** snapshots (2.8 GB) and the 22 shots deleted unviewed; our journalctl ended by PID; our lock
  line removed; a BOX-QUEUE "released" line added. Live saves still 41a5a36fffb4f8d4. One run was enough (150 hole
  finals against the 10 needed).

**Result.**
- **Bursts:** as in H1. 1,718 of 2,160 frames had three D bursts, at a median +6.5, +8.2 and +18.3 ms; the third ends
  at +19.0 ms (`raw/K1.bursts.txt`).
- **Sizes:** 194 of 198 sF have a clear block-row size (151 at 2560, 43 at 2816); none of the 198 sM has one, as in
  H1.
- **The two states, on clear finals only:** all 150 finals at widths 2048–2560 have holes. The eigen split gives A 74
  and B 76, φ within 0.61 / 0.64, between −0.11. X holds 0.307 of the window and Y 0.319, and they overlap on 0.0014:
  two complementary halves, as F436 found. The state switches irregularly: from A 30 of 61 times, from B 25 of 61.
- **What the mid snapshot (+9 ms) holds** (`x0365.py`; per frame, 138 consecutive pairs at one width):

| Comparison at the final's width, lake window | Median | Range (10–90 %) |
|---|---|---|
| Mid equal to the previous final, bitwise, where both are non-zero | 0.919 | 0.915–0.932 |
| Mid 0 where the previous final is 0 | 0.999 | — |
| Mid 0 where the previous final is non-zero | 0.054 | 0.039–0.057 |
| Mid equal to this frame's final, where both are non-zero (173 frames) | 0.028 | 0.018–0.044 |

  - So at +9 ms the lake window still holds the previous frame's final, holes included. φ of the mid zeros with the
    previous final's zeros is 0.92–0.94 in every pair type; with this frame's own zeros it is −0.21 to −0.23 when the
    state switches.
  - Bursts 1 and 2 change ~8 % of its non-zero pixels and zero ~5 % more.
- **What the last burst does** (`sn0365.py ana`, means per pair type; A has its holes in X, B in Y):

| Pair | n | 0 mid-frame | 0 at the end | Filled | Stayed 0 | 0 only at the end | Filled = previous final | Filled where previous final 0 | Other = previous final |
|---|---|---|---|---|---|---|---|---|---|
| A>B | 29 | 0.355 | 0.324 | 0.290 (X 0.726) | 0.064 | 0.262 | 0.000 | 0.869 | 0.000 |
| B>A | 24 | 0.370 | 0.320 | 0.299 (Y 0.732) | 0.072 | 0.249 | 0.000 | 0.869 | 0.000 |
| A>A | 28 | 0.353 | 0.312 | 0.114 | 0.239 | 0.075 | 0.000 | 0.564 | 0.000 |
| B>B | 26 | 0.359 | 0.324 | 0.115 | 0.243 | 0.086 | 0.000 | 0.563 | 0.000 |

  - The last burst rewrites almost the whole window (only 2.8 % of pixels keep their mid value).
  - It writes new values into the previous holes: never the previous final's value, which was 0 there.
  - It writes 0 into this frame's hole half: 99.9 % of the pixels that turn 0 at the end held the previous final's
    values mid-frame (`late zeros: mid = previous final`).
  - On a switch, the old hole half is filled (X 0.73 for A>B) and the new one is zeroed.

**Verdict** (F477, F478).
- **History fill: rejected for hole frames.** Not one filled pixel in 138 pairs equals the previous final (0.000,
  against ≥ 0.9 needed). The previous final was 0 at 56–87 % of them.
- **The holes are drawn in the frame's last burst, not left over:** the late-draw reading. The depth image holds the
  previous frame's final until about +18 ms. Then the last burst rewrites the lake and leaves one complementary half,
  X or Y, at 0. On a switch it writes 0 over pixels that held the previous frame's depth.
  - Whether that 0 is a clear that the draw then misses, or a written 0, cannot be told from memory snapshots.
  - Since nothing else in the window keeps its value either, the miss fits F333 (nothing wrote depth there).
- **F436 stands on clear reads only:** J1 offline (20 clear reads on each side), and K1's 150 clear finals here.
- **F466 corrected twice:**
  - Unclear reads taken before the last burst carry the hole state; their zeros sit at hole pixels.
  - In K1 a read at +9 ms holds the previous final in the lake window (92 % bitwise), although its block-row shear
    is unclear at every width. So "no per-pixel depth before the last burst" and the compressed-tile inference do not
    hold for the lake window. What makes the shear unclear (the rows outside the window, which bursts 1–2 may
    rewrite) was not checked.
- **Next (Q21):** name the pass that writes the lake's depth in the last burst (~+18 ms), and find why it misses one
  half. For example, a draw journal timed against the burst, with the depth image as the depth target: which draws
  write it, and do they cover the hole half at all in hole frames?
- Fault-free; live saves 41a5a36fffb4f8d4 never used; snapshots and shots deleted unviewed.
