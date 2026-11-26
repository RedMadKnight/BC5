# 0283 — The night lake's two hole states: frame timing, and what differs between an X and a Y frame

**Question.** Exp 0282 (F342): in a patched phase the lake's holes are one of two fixed, disjoint pixel sets, X (the
screenshots' patch cells) and Y (elsewhere), and the state switches within tens of milliseconds and back. Two things
were left open:
- Does the state flip every frame? Exp 0282 had no frame timing. Exp 0261's journal put the bench's frames 33–49 ms
  apart, so 0282's same-state pair 38 ms apart was about one frame.
- What decides the state? Within a run, the depth writers' draws, arguments and records and the full-screen draw's
  constants matched between clean and patched frames (F313, F320, F323). X and Y frames were never told apart there.

**Plan** (as written before the runs; the GO, top session 2026-10-24 ~22:00: at most two bench runs, about 20 min).
- **Run W283a**, the usual frozen-view lake bench (26 shots, exp 0197's patch metric).
  - Binary: exp 0251's private one (`~/bc5-work/exp0251/kyty_emulator`, md5 5227c025), which has edit0194's `_EVERY`
    windows and indirect arguments (at submission and at completion), patch0245's "bake db" and patch0251's "bake db2"
    lines.
  - Journal: `BC5_DIRECT_DRAW_JOURNAL=150:30`, `_EVERY=10`, `_PS` on the full-screen draw (11d01d7100), the depth-only
    writers by prefix (`11d1d88`, `11d1dd6`, `11d090d`, `11d0a98`, `11d373`, `11d1e2f`, `11d28b`, `11d1d33`, `11d29c`) and the
    colour + depth writer (`11d29e`).
    - Each window of 30 buffers holds about 30 frames: exp 0253's filtered windows held about one frame per buffer.
    - Every matched draw carries its journal time and wall clock, its depth registers (and so the frame's render
      size), its user data and tables, and its indirect arguments.
  - A second run only if W283a has no patched phase, or if its bursts miss the windows.
- **Reads timed to the windows** (`capw0283.py`). It follows the run's `direct.log`, and at each new window line takes
  one burst: 8 reads of the depth image 25 ms apart (each 6–18 ms in exp 0282), then one of the G-buffer.
  - The reads are held in memory while MemAvailable is above 2 GiB, so the disk does not spread them as in exp 0282.
  - Each read's wall clock and CLOCK_MONOTONIC time are logged. The journal's wall clock is the same system clock;
    its t is steady_clock, i.e. CLOCK_MONOTONIC, with t 0 given by emu.log's "bc5 clock" line.
  - 12 bursts, to `~/bc5-data/priv/exp0283` (mode 700), about 2.6 GB; summarised and then deleted.
- **`rd0283.py`:** each read at each of the six sizes: shear, depth-0 share, share in the shots' cell mask, and how it
  lies in the two families. The families are built from the clear reads as in exp 0282's cross0282.py; X is the one
  with the cell mask.
- **`xy0283.py`:**
  - frames from the journal (each up to its full-screen draw, timed and sized by that draw);
  - a latency L fitted so that the clear reads' sizes match their frames;
  - each read's state at its frame's size, and each frame labelled X or Y when its reads agree;
  - the per-window sequence of states;
  - then every journalled value of X frames against Y frames. A value separates the states when the two sides share
    none and the values repeat, so a frame counter does not count. The values are the full-screen draw's depth/HTILE
    registers and size, each writer's draw count, packets, depth registers, arguments, user data and table dwords.
  - Checked offline on a synthetic journal built from the line formats, with frames alternating X/Y and one table
    dword carrying the parity: L found, each read on its frame, the X/Y sequence back, the parity dword and the
    arguments reported as separators, the frame counter not.
- Box rules as before: BOX-LOCK line of the run's own, kernel stream to the laptop, the run stopped on any new amdgpu
  line. The live saves (af64b06adff9c5f1) are snapshotted first, restored if changed, and checked at the end.
- Scripts: `ab0283.sh` / `bench0283.sh` (exp 0282's, renamed; `ab0283.sh` also runs exp 0261's `args0261.py`),
  `capw0283.py`, `rd0283.py`, `xy0283.py`, `swz0248-z4.json`, `swz0244-4.json`. Raw files under 1 MiB each; no images
  kept.

**Setup as run.**
- BC-250, 2026-10-24 22:02–22:33, boot 831e5915; `/var/home` at 72–73 %.
- The live saves held af64b06adff9c5f1. They were snapshotted at 22:10 and checked before and after each run; they
  never changed (the bench uses its private copy), and the snapshot was removed at 22:33.
- Both runs used binary 5227c025 and the journal switches as planned.
- **W283a, 22:10–22:17:** `capw0283.py W283a 12 8 25` (hold threshold 2 GiB).
  - MemAvailable was below that, so every read was written at once.
  - During most bursts the journalled frames ran 150–350 ms apart (windows w157–w197), against about 40 ms in w230.
- **W283b, 22:24–22:31, the second run of the GO:** `capw0283.py W283b 12 8 30 … 1024` (hold threshold 1 GiB).
  - W283a had a patched phase and its bursts hit the windows, but it gave too few labelled frames (below) and its
    frames slowed during the bursts.
  - MemAvailable was 810–1056 MiB, so one burst of 12 was held and the rest written at once.
- **Both runs:** the first burst of each window started 1–13 ms after the window's line.
  - Two windows in W283a and three in W283b got a second burst, 0.3–0.6 s later. The window line repeats until a
    buffer with a matched draw is journalled.
  - Reads: 2.6 GB per run, deleted at 22:33 after the summaries.
- **Analysis.**
  - On the box, with no emulator, 22:19–22:33: `rd0283.py` and `xy0283.py`. xy0283.py was rerun on W283a after
    three changes: frames start at their first writer draw, the lag is scored by the agreeing share, and a window's
    last frame no longer takes reads past it. The view of varying values was added then too.
  - Offline: `st0283.py` (below), from the summaries only.
- The top session asked for the box back for the maintainer's check; the lock was removed at 22:33:19. The two
  journals and the full `.db` summaries stay on the box.
- `raw/W283?.db.txt` (exp 0245's jr0245.py) were trimmed below 1 MiB at a line boundary, with a note line.

**Result** (`raw/`).
- **Box state.** No kernel fault, timeout or reset in either run: the amdgpu dmesg count stayed at 257, the `.out`
  files have 0 fault lines, and no new devcoredump was saved. The stream (`raw/W283ab.kern.txt`) has one routine
  "perf: interrupt took too long" line (22:16:04) besides the MLD lines.
- **The phases.** W283a was clean at ts00–ts12 (0.6–1.7 %) and patched at ts13–ts25 (14.4–23.9 %); bursts b08–b12
  fell in the patched phase. W283b was patched throughout (23.1–31.6 %).
- **Frames and timing** (`raw/W283?.xy.txt`).
  - Each run's journal has 190 frames in 19 windows of 10 (171 of them whole).
  - Frame intervals within windows: median 44 ms in W283a (9–509) and 94 ms in W283b (7–309). The render size changed
    at 31 and 23 of the 171 frame boundaries.
  - A read shows the frame that started 45 ms (W283a) or 60 ms (W283b) before it: at that lag, 26 of 30 and 34 of 35
    matched clear reads have their frame's size.
  - Single reads can lag more. In W283a's b08, the first 125 ms of reads still show a 2048 frame after the window's
    frames had moved to 2304.
- **The hole sets.**
  - **W283a** (`raw/W283a.rd.txt`) has the two families of F342:
    - X: 16 clear reads; together 0.348 of the lake window and 92.5 % of the shots' cell mask;
    - Y: 18 clear reads; 0.352 and 8 %.
    - Their unions share 0.104 of the window (30 % of each), against 0.1–0.8 % in exp 0282. Single X reads have
      2–29 % of their depth-0 pixels in Y's union.
  - **W283b** (`raw/W283b.rd.txt`) groups into five families.
    - The large ones are X-like (28 reads; the cell mask 51–72 % at depth 0) and Y-like (F4 with 12 reads and F5
      with 5; 21–29 %).
    - rd0283.py named X the family with the most of the cell mask and Y the next. That picked a one-read family as Y,
      so W283b's states in `xy0283.py` are not used.
  - `st0283.py` classes every read at its frame's size by the share of the cell mask at depth 0 (`raw/W283?.st.txt`):
    X-like at 0.5 or more, Y-like at 0.3 or less (with depth 0 on at least 0.15 of the window).
- **The state holds for one to at least eight frames and switches at irregular times** (`raw/W283?.st.txt`).
  - W283a, w230 (frames about 40 ms apart): X in frame 0, Y in frames 1–8 (about 320 ms), X and Y reads in frame 9.
  - W283a, w177: X in frame 1, Y in frame 2.
  - Between consecutive labelled frames:
    - W283a: the same state 6 times (1 frame apart) and once (2 apart); switched twice (1 apart).
    - W283b: the same state 3 times (1 apart) and once (2 apart); switched 3 times (1 apart) and 3 times (2 apart).
  - So the state does not flip every frame.
  - In W283b several frames hold both X- and Y-like reads (e.g. w170 frame 1, w133 frame 9). There the switch falls
    inside the ±1-frame matching.
- **The writers' per-frame draw lists come in two variants, and the state does not follow them.**
  - By `cmp0245.py` (`raw/W283?.cmp.txt`), counting the depth-writer draws before each full-screen draw:
    - W283a: 83 in 111 of 190 frames, 79–80 in 77 (+32..34 −35..38 against the first frame), 82 in 2;
    - W283b: 61 in every frame; 166 frames match the first and 23 have 21 draws with other packets (+21 −21).
  - Each depth-only writer's DRAW_INDIRECT argument offset takes one of two values 0x20 apart. Examples: 0x11d090d900
    at +0xb80 or +0xb20 in W283a, +0x780 or +0x760 in W283b. Several table dwords follow the same sequence. These are
    two argument slots, a and b.
  - The slot sequence is irregular: W283a's w230 runs a a b a b a a b a b; W283b is mostly a.
  - In w230 the holes stay Y over frames of both slots. Reads by their frame's slot:
    - W283a: X 7 on a, 3 on b; Y 4 on a, 9 on b;
    - W283b: X 31 on a, 2 on b; Y 18 on a, 1 on b.
- **Nothing found yet separates X frames from Y frames.**
  - xy0283.py listed 100 per-frame values that vary with at most 4 values (its first 40 scalar keys and 60 user-data
    and table dwords, in key order). Against st0283.py's labels (W283a 4 X and 8 Y frames, W283b 13 X and 6 Y), none
    separates the states.
  - xy0283.py's full search over every journalled value did not run. It needs 3 whole frames of each state by its own
    labels: W283a had 2 X and 8 Y, W283b 7 X and 0 Y (the naming above).
  - No writer draw's arguments at completion appear among the listed values ("-"), as edit0194.py warns for
    chained jobs.
  - Both states occur at the same render size.

**Verdict.**
- **Frame timing: the hole state is not a per-frame flip.** It holds for one to at least eight consecutive frames
  and switches at irregular times, sometimes between consecutive frames. A depth read shows the frame journalled
  about 45–60 ms (about one frame) earlier.
- **The draw lists of X and Y frames differ in nothing found so far.**
  - The depth writers alternate between two argument slots (two draw-list variants), but the hole state does not
    follow the slot.
  - None of the 100 listed varying values separates the states.
  - The full search over all journalled values is still open.
- **On F342's two sets:** in W283a the families overlap more than in exp 0282 (30 % of each union), and W283b has
  more than two groups. Read by read, the split into X-like reads (the shots' cells) and Y-like reads (elsewhere)
  still holds.
- **Next:**
  - xy0283.py's full search with st0283.py's labels on the two journals still on the box (read-only, no emulator,
    about 2 min). If nothing in the submitted command stream separates X and Y, the decider is GPU-side, in data the
    writers read.
  - The writers' GPU-written indirect arguments, read from memory as the depth is read (the arguments at completion
    are missing).
