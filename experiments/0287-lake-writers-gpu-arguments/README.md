# 0287 — The night lake's depth writers: their GPU-written indirect arguments, read with the depth

**Question.** Exps 0283–0286 (F344, F346, F348): nothing the CPU submits tells the lake's X frames from its Y frames.
The depth writers draw indirectly, with arguments the GPU writes. edit0194.py journals those arguments only at
submission, and their values at completion are missing. Read from memory next to the depth image in a frozen view,
do the arguments change, and do they change with the holes?

**Setup** (the GO, top session 2026-10-24 ~23:18: at most two bench runs, about 20 min).
- **Argument addresses.**
  - `base0287.py` on exp 0283's two kept journals (`raw/base0283.txt`): the writers' DRAW_INDIRECT arguments sit at
    three SET_BASE index-1 bases, 0x11934d3900, 0x11935d3900 and 0x1193ad3900, at offsets below 0x1000. edit0194.py's
    "base1 + offset", with the layout from Mesa's radv_cs_emit_indirect_draw_packet as it cites.
  - `capa0287.py` learns each run's own offsets from its live journal. Ranges: 4.9 KB (W287a) and 2.8 KB (W287b).
- **Runs.** W287a 23:24–23:31 and W287b 23:36–23:43, the usual frozen-view lake bench.
  - Exp 0251's private binary (5227c025), exp 0283's journal switches (`_EVERY` windows of 30 buffers, `_PS` on the
    full-screen draw and all depth writers), `ab0287.sh` / `bench0287.sh` (exp 0283's, renamed).
  - The 3-s dmesg poll and the kernel stream; boot 831e5915; `/var/home` 58–59 % (after the top session's cleanup).
- **Saves.** The live saves had become c0ee58b92c0cadc2 (57 files): the maintainer's DS4 test of 22:35–23:04 saved at
  23:03–23:04. On the top session's word, that was the reference. It was snapshotted at 23:24, checked before and
  after both runs, unchanged, nothing restored, and the snapshot removed at 23:47. The bench loads its own private copy
  of the lake save, as in every lake run since exp 0194.
- **Bursts.** `capa0287.py W287? 12 8 30 … 1024`: 12 bursts per run at the journal windows' starts. A burst is 8 times:
  the argument ranges (aK); in W287b also the region of exp 0274's 32_FLOAT image pyramid (0x11d0880000 + 0x20000,
  pK); and the depth image (zK), 30 ms apart. Then the arguments once more and the G-buffer.
  - The small reads are held in memory. MemAvailable was 818–1127 MiB, so the depth reads were mostly written at
    once.
  - Reads: 2.6 GB per run, deleted at 23:47 after the summaries.
- **Analysis on the box,** with no emulator, under our analysis-only lock:
  - `rd0287.py`: exp 0283's rd0283.py, skipping the argument and pyramid reads. After its first W287b run it was fixed
    for more than nine hole families; the crash was in the JSON write.
  - `ar0287.py`: the argument records against the read states.
  - `chg0287.py`: a test without labels, consecutive reads against each other.
- **Two slips, before the run.**
  - At 23:19:45, before its lock check (the top session held the box for a build), a command copied `base0287.py`
    (2 KB) to the box's `/tmp`. It was moved into `~/bc5-work/exp0287` at 23:23, and the top session was told.
  - At 23:23, a stray no-op ssh asked the box for a command that does not exist.
  - Nothing else touched the box outside our lock.

**Result** (`raw/`).
- **Box state.** No fault, timeout or reset in either run: the amdgpu count stayed at 257, the `.out` files have 0
  fault lines, the stream (`raw/W287ab.kern.txt`) has only routine lines, and no new devcoredump was saved.
- **The phases.** W287a was patched in all 26 shots (14.6–22.9 %), W287b too (20.3–31.3 %). The bench reached the
  lake as before.
- **The X/Y labels of exps 0283–0286 do not carry over** (`raw/W287?.rd.txt`).
  - The cell-mask rule (X-like at 0.5 of the shots' cell mask at depth 0 or more, Y-like at 0.3 or less) classes
    most clear reads as mixed. The cell mask is 0.137 (W287a) and 0.292 (W287b) of the lake window; most clear reads
    have 0.33–0.49 of it at depth 0.
  - W287a: 8 X and 3 Y reads (the 3 Y from one burst, with identical memory). W287b: 22 X and no Y.
  - So `ar0287.py`'s X/Y comparison is not meaningful: W287a's 15 "separators" set varying X reads against one
    effective Y sample, and W287b has no Y.
- **The GPU-written arguments are not static in the frozen view** (`raw/W287?.ar.txt`).
  - W287a: 147 records (writer, op 0x24). 28 never change; 119 take several values and change in 2–28 % of
    consecutive reads 30 ms or more apart.
  - W287b: 78 records, 18 constant, 60 changing in 4–33 % of consecutive reads.
- **The arguments change only when the depth memory changes** (`raw/W287?.chg.txt`). Every consecutive pair of a
  burst, the whole depth image's words against the argument records:

  | | arguments changed | arguments unchanged |
  |---|---|---|
  | W287a, depth changed | 31 | 19 |
  | W287a, depth unchanged | 0 | 34 |
  | W287b, depth changed | 36 | 20 |
  | W287b, depth unchanged | 0 | 28 |

  - No argument change without a depth change, in 168 pairs.
  - In 62 pairs nothing changed at all. The frozen view rewrites the same depth and the same arguments.
- **The hole switches fell on argument changes.**
  - Consecutive reads with a clear, equal size, compared in the lake window: 25 pairs in W287a and 22 in W287b.
  - Each run had one hole switch:
    - W287a b01 z6→z7: phi −0.27, 1 % of the depth-0 pixels kept, 44 records changed;
    - W287b b11 z1→z2: phi +0.03, 34 % kept, 14 records changed.
  - Of the 45 pairs whose holes stayed (phi ≥ 0.95), 44 had no record change. W287a's b02 z1→z2 had 42 records
    change with the holes kept (phi +0.995).
  - The arguments can change without a switch. In these reads a switch never came without an argument change, but
    that is two switches.
- **The pyramid changes with them** (W287b only; `raw/W287b.chg.txt`). Depth / arguments / pyramid changed, per pair:

  | depth, arguments, pyramid | pairs |
  |---|---|
  | all three | 33 |
  | depth and arguments | 3 |
  | depth and pyramid | 6 |
  | depth only | 14 |
  | pyramid only | 2 |
  | none | 26 |

  - 33 of the 36 argument changes came with a pyramid change in the same interval.
  - Against the pyramid of the pair before, the argument changes split 14 with a change against 18 without, so it
    does not lead them by a read.

**Verdict.**
- **The lake writers' GPU-written indirect arguments change in steps in a frozen view.** The depth memory and (in
  W287b) the 32_FLOAT pyramid the writers' vertex stage reads change in the same steps. Between steps all three
  stay put. That is the GPU-side variation that exps 0283–0286 could not find in the submitted stream.
- **Both observed hole switches fell on such a step** (44 and 14 records changed). Steps also come without a switch,
  so the arguments do not decide the state alone. These are two switch events.
- A frozen camera should give the same culling result every frame. A step means some GPU input of the culling
  changed. The pyramid changing in the same steps fits an occlusion pass that reads the previous frame's depth through
  the pyramid: holes would feed back into the next frame's culling. TODO(verify): this is a hypothesis; the pyramid's
  role is not shown.
- The X/Y labels need a run whose holes split cleanly, as W283a's did. In W287a/b, the cell-mask rule left most reads
  mixed.
- **Next:**
  - offline: the 4KB_S de-swizzle of the pyramid (exp 0274's open item), so its texels can be set against the depth
    and the holes;
  - then reads of depth, pyramid and arguments in the same frame-timed bursts, to see whether a pyramid built with
    holes precedes the culling change that switches the holes.
