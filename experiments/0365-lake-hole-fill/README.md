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
