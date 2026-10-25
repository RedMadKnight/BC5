# 0312 — The night lake's culling buffers: does a two-phase occlusion-culling state carry the hole halves?

**Question.** The night lake's patches are one half of a checkerboard of water cells per frame, and the halves swap
between two states, X and Y (F342, F372). The state is decided GPU-side and held for one to eight or more frames
(F344). Nothing the CPU submits separates the states (F346, F348), nor do the writers' argument values (F359), a
cross-ring race (F374), a frame-swapped descriptor (F374) or the water's 256 × 256 grid (F376).

Prior-art research (the maintainer's request, 2026-10-25) found no emulator report of this. It found one published
technique that fits the data: GPU-driven two-phase occlusion culling.
- An early depth prepass draws what was visible last frame, and a Hi-Z is built from it.
- Every bound is tested against the Hi-Z; a late prepass draws what became visible.
- Compute stages fill each phase's indirect arguments, and a per-object "visible last frame" state is kept GPU-side.

That maps onto the lake as follows:
- the culling compute 0x11d0375600 runs twice per frame, about 100 and about 1,000 groups (F355, F357);
- each writer has two argument slots 0x20 apart (F344);
- the writers read a far-is-high depth pyramid (F352).

If the per-cell state or the visible-cell lists carry the halves, they are written by the culling chain into its
buffers. Those are F355's four buffers, of which only the argument records at small offsets were ever read. Do any
pages of those buffers hold the same content within one state and a different one across states?

**Plan** (the maintainer's yes to continue, 2026-10-25 ~15:40; the top session claimed 0312; a slot on request; RT
off).
- **The bench:** exp 0311's lake bench on today's setup (`bench0312.sh`): the launcher copy derived by exp 0299's three
  edits, RT off by `input-0312.cfg`, two rings, 20 frozen-view shots 5 s apart, no journal.
- **`buf0312.py`**, beside it:
  - in the frozen view, bursts of K reads 30 ms apart of the 8 MiB from 0x11934d3900 (the four buffers are
    contiguous, and their bases were the same in exps 0289, 0293 and 0295) and of the depth image;
  - read-only through `/proc/<pid>/mem`, capa0287.py's file layout;
  - `rd0312.py` (exp 0289's `rd0289.py`) labels the depth reads with their families.
- **`pg0312.py`**:
  - per 4-KiB page and read, an order-insensitive content key (sorted dwords; a visible list may come in any order);
  - over pairs of labelled reads, the share whose keys differ among same-state pairs and among X–Y pairs;
  - the page's score is the difference, against a null of shuffled labels.
  - `--selftest`: a planted page holding one of two cell lists by state scores ~1 on top; a page rewritten every
    read scores ~0. It runs on the box (numpy).
- **The reading:**
  - a page that follows the state names the culling output that decides the halves. Decoding it (cell indices, a
    bitset) is the next step, and then what our path does to it.
  - none means the state is not in these buffers, and the depth pyramid's generation (the top session's idea: a late
    phase reading a pyramid one frame old) comes next.
- **Rules:** the live saves are never used and are checked before and after; the kernel stream; stop at the first
  reset. Reads go to `~/bc5-data/priv/exp0312` and are deleted after the analysis; numbers only in the repo.

**Sources** (prior art, public):
- Bevy's documentation of two-phase occlusion culling:
  https://doc.qu1x.dev/bevy_trackball/bevy/render/experimental/occlusion_culling/struct.OcclusionCulling.html
- U. Haar, S. Aaltonen, "GPU-Driven Rendering Pipelines", SIGGRAPH 2015 Advances in Real-Time Rendering:
  https://advances.realtimerendering.com/s2015/aaltonenhaar_siggraph2015_combined_final_footer_220dpi.pdf
- No emulator report matches:
  - shadPS4: https://github.com/shadps4-emu/shadPS4/issues?q=is%3Aissue+checkerboard (only #4573, closed without a
    cause) and https://github.com/shadps4-emu/shadPS4/issues?q=is%3Aissue+water (Bloodborne's NVIDIA-specific
    regression #3589);
  - RPCSX: https://github.com/RPCSX/rpcsx/issues?q=is%3Aissue+water (none).

**Setup as run** (the top session's GO of 19:04 CET, to start once the BVH session's 0322 S2 had ended; boot
8071b391; launcher bb51caf2; build d02f4696, the normal shared build with exp 0318's crash-log change; RT off).
- **19:33:39.** The guard found an empty BOX-LOCK and no emulator; our lock line went into the empty file. Live saves
  bb14b6dd35b644ff (never used; checked before, after and at the release).
  - `play-pkg-0312.sh` was derived by exp 0299's three edits: 4 lines added, 3 of them replacing the originals
    (`raw/play-pkg-0312.diff`).
  - `input-0312.cfg` is exp 0194's `input-0194.cfg` with `RayTracing.PPSA03671=off` and `MangoHud.PPSA03671=off`
    (`raw/input-0312.cfg`). The maintainer's own `input.cfg` now turns MangoHud on; this private file keeps its
    overlay out of the shots.
  - `pg0312.py --selftest` in the distrobox: the planted page 100 on top at +1.00, the page rewritten every read at
    +0.00, the shuffled-label null's 95th percentile 0.11.
  - The kernel stream ran throughout (`raw/kernel-stream.txt`).
- **P1, 19:34:13–19:39:19** (`raw/P1.ab.txt`, `raw/P1.out`):
  - two rings (4 "compute ring" lines), RT off (3,292 ray-tracing-off lines), the compaction skipped as by default, no
    journal switches;
  - 20 frozen-view shots.
  - `buf0312.py` beside it (`raw/P1.buf.txt`): 12 bursts 19:37:21–19:38:16. Each burst took 8 × (the 8 MiB from
    0x11934d3900, the depth image) 30 ms apart, then the G-buffer. MemAvailable stayed 1,098–1,475 MiB.
- **No shot was viewed or copied:** the 22 shots were deleted on the box at 19:43 with the reads.
- **Analysis, 19:39–19:43** (`raw/P1.rd.txt`, `raw/P1.reads.json`, `raw/P1.pg.txt`):
  - `rd0312.py` and `pg0312.py`;
  - then, because the labels were too few, `pk0312.py` (`raw/P1.pk.txt`) and `pq0312.py` for two pages
    (`raw/P1.pq1767.txt`, `raw/P1.pq1776.txt`).
  - The reads (3.4 GB) were deleted at 19:43.
- **Released 19:44:05.** One run only, as the slot asked: both shared builds were to be rebuilt after it.

**Result** (`raw/`).
- **No kernel event:** 0 fault lines, no amdgpu line in the run's dmesg; the stream holds five IPv6 lines only.
- **The lake was patched throughout:** 18.5–24.2 % in all 20 shots.
- **The labels failed.**
  - `rd0312.py` found 24 clear depth reads with holes (next-best shear ≥ 3 × best) among 96; the rest had no clear
    render size, and without the draw journal no frame size could fix them.
  - The clear reads did not form the two complementary halves of F342. X has 5 reads (0.858 of the shots' cell mask);
    every other family is a single read. "Y" (b06.z2) has 0.755 of its pixels in X's set, and X 0.564 in Y's.
- **`pg0312.py` had no power:** 6 labelled reads (5 X, 1 Y) give 10 same-state and 5 X–Y pairs, and the
  shuffled-label null's 95th percentile is 1.00.
  - 189 of the 2,048 pages change at all over the 96 reads.
  - The top page, 301 (+0x12d000), scores +0.60 (null median 0.60).
- **`pk0312.py`, the label-free check:** over the 24 clear reads, each read's lean d = inX − inY at its best size runs
  from −0.24 to +0.40 (median 0.05).
  - 43 pages agree for some pairs of reads and not others.
  - No page follows the lean: the top score, +0.146 (pages 1296 and 312), is below the shuffled null's median of 0.177
    (95th percentile 0.198).
- **A few pages hold only a few contents** (the content of each read, burst by burst):
  - **page 301:** 3 contents, one per 4 bursts (b01–b04, b05–b08, b09–b12), a ~20 s change;
  - **pages 1767 and 1768** (+0x6e7000 and +0x6e8000, i.e. the fourth buffer 0x1193ad3900 at +0xe7000 and +0xe8000):
    exactly 2 contents (65 and 31 reads) and the same sequence in both. They switch within bursts and hold for 1–4+
    reads, the timing of the hole state (F344). Their neighbours change every read (1766) or never (1769).
  - **page 1776:** 3 contents (49, 6 and 41 reads), with the same kind of switching.
- **`pq0312.py` for page 1767:** its state doesn't follow the clear reads' lean.
  - State 0 has 19 clear reads (mean d +0.129), state 1 has 5 (+0.118): a difference of 0.011, permutation p 0.89.
  - Its two contents differ in 9 of 1,024 dwords (11 positions in raw order). They are short runs of 16-bit pairs:
    high halves 1–3, low halves 1–26 (content 0 spans 0–45 and 0–41,230).
- **Page 1776:** state 0 has 16 clear reads (mean d +0.077), state 2 has 7 (+0.201), and state 1 has one read
  (+0.388); the 0-against-1 test (p 0.18) rests on that single read. Its contents differ in 309 dwords, small numbers
  (low halves 15–491, high halves 0–1).

**Verdict.**
- **Inconclusive for the two-phase culling question:** P1 neither shows nor excludes a culling-buffer page that carries
  the hole state.
  - Without the draw journal, three quarters of the depth reads had no render size.
  - The clear quarter did not reproduce the two complementary halves, so the X/Y labels, and the continuous lean that
    replaced them, are weak.
- **What it does show:**
  - The culling buffers are mostly static between reads (1,859 of 2,048 pages never change) or rewritten every read.
  - A two-state record exists at 0x1193bba900–0x1193bbc8ff (pages 1767–1768) with the hole state's timing. Its two
    contents differ by a short run of 16-bit pairs, the shape a visible-group list would have.
  - Its state is not tied to the clear reads' lean (p 0.89, 19 against 5 reads). The lean is too weak to make that a
    rejection.
- **Next:**
  - repeat P1 with exp 0311's journal (`BC5_DIRECT_DRAW_JOURNAL=150:30`), so that every depth read takes its frame's
    size, and test pages 1767/1768 and 1776 against the frames' families;
  - or decode page 1767's nine differing dwords as indices (16-bit pairs against the water's 256 × 256 grid, F376).
  - If neither page follows the halves, the depth pyramid's generation (a late phase reading last frame's pyramid)
    remains the other lead.
