# 0354 — The night lake's culling pages against the hole state, every read sized by the draw journal (exp 0312's J1)

**Question.** Exp 0312's P1 (F387) read the night lake's culling buffers (the 8 MiB from 0x11934d3900) beside the
depth image. Pages 1767–1768 held exactly two contents, switching within bursts and holding for 1–4 reads, the hole
state's timing (F344). But without the draw journal only a quarter of the depth reads had a render size, so the X/Y
hole labels failed and nothing could be tested. With every depth read decoded at its own frame's size, do pages
1767/1768 and 1776, or any page with few contents, follow the X/Y hole state frame by frame?

**Plan** (the maintainer's "Tak, zleć J1" through the top session, 2026-10-28; exp 0312's "Run J1 (plan)" section,
carried over unchanged except where noted).
- **The build and launcher:** the shared normal build affa0c22 (exp 0350, F433). `play-pkg.sh` 55531ab6: one ring,
  the exp 0341 guards, `RING_DEPS=dcb`, and exp 0350's `BC5_DIRECT_HOST_INDIRECT=learn:1100000000
  BC5_DIRECT_SOFT_WAIT_MS=8`.
  - `setup0354.sh` derives `play-pkg-0354.sh` from exp 0353's checked `play-pkg-0353.sh`, renaming 0353 to 0354. Its
    diff against `play-pkg.sh` must equal exp 0353's line for line: the five edits (its log, its mount log, the input
    configuration hook, exp 0299's private save and working directories).
  - `input-0354.cfg` is exp 0347's file: RT off, MangoHud off.
- **The bench** (`bench0354.sh`, `ab0354.sh`: exp 0312's, paths changed to 0354): exp 0299's private save copy, 24
  frozen-view shots (`SERIES=24`), `patch0197.py`'s share per shot. The run passes
  `BC5_DIRECT_SKIP_PGM=909974400 BC5_DIRECT_DRAW_JOURNAL=210:3000 BC5_DIRECT_DRAW_JOURNAL_PS=11d01d7100`.
  - On this build the frozen view began 182–187 s after the bench's start in exp 0353's three runs. The journal starts
    at the emulator's 210th second, after the route's keys.
- **The reads:** `buf0354.py J1 16 8 30 4 <dir> 1024 212`, 16 bursts of 8 × (culling buffers, depth) 30 ms apart.
  The first burst waits until the emulator has run 212 s.
- **The analysis** (exp 0312's scripts, copied unchanged):
  1. `rdj0312.py` without frames;
  2. `fr0312.py` on the run's `direct.log` (frames, lag fit, sizes);
  3. `rdj0312.py` with the frames (families and X/Y states at each read's frame size);
  4. `pqj0312.py`, the frame-level page test: pages 1767/1768 and 1776 named in advance, plus the scan of pages with
     2–8 contents;
  5. `pg0312.py` and `pk0312.py` for comparison with P1.
  - Checks on the box before the run: `mkj0312.py`'s synthetic capture through `rdj0312.py` and `pqj0312.py`; the
    self-tests of `fr0312.py` and `pqj0312.py`.
- **A second run, J2, only if J1's lake comes out clean** (fewer than half its shots patched; no holes means no
  labels). Exp 0353's three runs on this build were clean, mixed and patched (F435).
- **The reading** (as planned in exp 0312):
  - a named page with p < 0.01, or a scanned page above the scan null's 95th percentile, carries a culling state that
    follows the halves;
  - neither, with most frames labelled, means the culling buffers do not carry the hole state;
  - if neither size field agrees with the clear reads, the journal cannot size the reads, and J1 says so.
- **Rules:**
  - the guard: an empty BOX-LOCK, our own lock line, no emulator; the bvh session's exp 0352 shares the box through
    the lock;
  - the kernel stream; stop at the first reset;
  - the live saves 3f8412c4884ddf14, compare only.
  - Shots and reads are deleted after the analysis, unviewed. The draw journal stays private in
    `~/bc5-data/captures` and nothing of it is committed; only summaries go to `raw/`.

**Setup as run** (the top session's GO of 2026-10-28 ~09:25; boot 6d79bc01; build affa0c22; launcher 55531ab6).
- **09:30.** The guard found exp 0352's emulator running (the bvh session), so nothing was touched. A laptop watcher
  read only the lock and `pgrep` every 60 s until the box was free.
- **09:33:18.** Our lock line went into the empty BOX-LOCK, `~/bc5-work/exp0354/CLAIM.txt` was written and a
  BOX-QUEUE line added. Live saves 3f8412c4884ddf14.
  - `setup0354.sh`: `play-pkg-0354.sh` 72844c59, its diff exactly exp 0353's five edits (`raw/play-pkg-0354.diff`);
    `input-0354.cfg` d6bcc1d7, RT off, MangoHud off (`raw/input-0354.cfg`).
  - Checks in the distrobox, as planned:
    - `mkj0312.py`'s synthetic capture through `rdj0312.py`: two families of 8, every read X or Y by its frame;
    - then `pqj0312.py`: page 1767 p 0.0299 (the 1/35 floor), 1768 constant;
    - the self-tests of `fr0312.py` and `pqj0312.py`. The synthetic 0.57 GB was deleted.
  - The kernel stream ran throughout (`raw/kernel-stream.txt`).
- **J1, 09:34:15–09:39:49** (`raw/J1.ab.txt`, `raw/J1.out`):
  - one ring (no "compute ring" lines), RT off (2,618 ray-tracing-off lines), the skip list 909974400;
  - the journal `210:3000`, `_PS=11d01d7100`;
  - 24 frozen-view shots.
  - `buf0354.py` (`raw/J1.buf.txt`): the frozen view was up and the emulator at 212.1 s at 09:37:48. 16 bursts
    09:37:48–09:38:48, 4.5 GB. MemAvailable 999–1,525 MiB; one burst's depth reads were written at once.
- **Analysis, 09:40–09:48:**
  - `rdj0312.py` without frames (`raw/J1.rd.txt`, `raw/J1.rd.json`);
  - `fr0354.py` (`raw/J1.fr.txt`, `raw/J1.frames.json`);
  - `rdj0312.py` with frames (`raw/J1.rdj.txt`) and `pqj0312.py` (`raw/J1.pqj.txt`);
  - after seeing those, `rdj0354.py` (`raw/J1.rdj2.txt`, `raw/J1.rdj2.json`) and `pqj0312.py` again
    (`raw/J1.pqj2.txt`), then `ph0354.py` (`raw/J1.ph.txt`);
  - a stdlib snippet on the box for the pages' content sequences, and a search of the journal for the culling bases.
- **Script changes after seeing the data:**
  - `fr0354.py` is `fr0312.py` with its viewport pattern taking a sign: this title's full-screen water draw has a
    flipped viewport, `vp 2816x-1584 at 0,1584`.
  - `rdj0354.py` chooses Y as the largest family not mostly inside X, and prints the overlaps.
  - `ph0354.py` is new, written because the labels failed (below).
- **No second run:** the lake was patched in J1.
- **Cleanup:** the reads (4.5 GB) and the 26 shots were deleted at 09:48, unviewed.
  - The draw journal stays private: `~/bc5-data/captures/play-20261028-0934/gc/direct.log`, 134,611,984 bytes.
- **Released 09:49:09:** the lock line removed, no emulator, launcher or bc5-mount left, a BOX-QUEUE line.

**Result** (`raw/`).
- **No kernel event:** 0 fault lines and 0 ring timeout or reset lines; the stream holds IPv6 lines only.
- **Live saves:** 3f8412c4884ddf14 before, after and at the release.
- **The frame rate:** 30 flips in 1.004 s at t 320 s.
- **The lake was patched in all 24 shots,** 15.3–22.8 %.
- **The journal sizes every read:**
  - 3,000 full-screen water draws, t 210.0–314.9 s, 34 ms apart (median; max 288 ms). So the journal did not slow
    the frozen view.
  - Widths 3072 (1,925 frames), 2816 (865), 2560 (128), 2304 (52) and 2048 (30), the same in `rt0` and in `vp`.
  - At a lag of +10 ms all 44 clear depth reads agree with their frame's width (1.00, for either field). Every one
    of the 128 depth reads and 16 G-buffer reads got a frame: 112 frames, 98 of them with one read.
- **The family labels failed in a new way.**
  - At their frames' sizes 127 depth reads have holes. `rdj0312.py`'s unions grew with their members: X has 48
    reads, and every other family has 66–99.8 % of its pixels inside X's set.
  - So the reads came out "both" (59) or "mixed" (57), and only 11 X. `pqj0312.py` had 6 X frames and no Y.
  - `rdj0354.py` found no family outside X.
- **The hole masks themselves are two states** (`ph0354.py`).
  - 111 frames with a sized read, compared over the 299,266 lake-window pixels valid in all of them. Hole share
    0.21–0.39 per frame.
  - The leading split of the frames' φ matrix: 59 and 52 frames, mean φ 0.546 and 0.558 within, −0.238 between
    (eigenvalue share 0.48). Two anticorrelated hole sets: F342's complementary halves, now decoded frame by frame.
  - Over the sampled frames in order, the state runs for 1–7 frames (median 2; 24 runs of one frame), as F344.
  - No drift: the Spearman of pair φ with the time apart is +0.004.
- **No culling page follows the hole state** (pairs from different bursts only, 5,770 pairs):
  - the 10 pages with 2–8 contents: the largest same-minus-different φ is +0.024 (page 1280). The null of the
    scan's largest (contents shuffled, 1,000) has median +0.019 and 95th percentile +0.046.
  - Page 1776 (75 contents over the reads): −0.022, p 0.80.
  - Pages 1767 and 1768 could not be tested: 1767 held one content all run, 1768 changed almost every read.
- **The culling range behaved differently from P1:**
  - 179 of 2,048 pages changed (P1: 189);
  - pages 1, 4 and 1767 constant (P1: 10, 8 and 2 contents);
  - 301 and 1768 with 112–113 contents (P1: 3 and 2).
  - The journal does not name the culling bases: the full-screen water draw does not bind them, and no line holds
    0x934d3900, 0x935d3900, 0x939d3900 or 0x93ad3900. The depth image (0x1129ec0000) and G-buffer (0x113f230000, the
    draw's `rt0`) are at their old addresses.

**Verdict.**
- **The draw journal works as the sizing source on the shared build.** One field (`rt0` or `vp`) and a +10 ms lag
  size every depth read. All clear reads agree, so exp 0312's sizing problem is solved.
- **The two hole states are real and frame by frame:** two anticorrelated hole sets (φ −0.24 between, +0.55 within),
  each holding for 1–7 frames.
  - That holds the X/Y structure of F342/F344 without depending on the union families. With all reads sized, the
    unions merge, so the frame φ split replaces them as the label.
- **No page of the 8 MiB at 0x11934d3900 follows that state** on today's build. The scan stays inside its null, and
  page 1776 does not either.
  - Caveat: this run does not re-verify that the range still holds the culling buffers (F355's addresses came from
    exps 0289–0295 on older builds). Its pages behaved differently from P1's.
  - So the two-state pages 1767–1768 of P1 have no counterpart here, and P1's lead does not carry over.
- **Next:**
  - re-read the depth writers' argument bases on today's build (exp 0289's `capa` journal with `_PS` on the writers)
    before any more page tests;
  - or go to the other lead: which depth pyramid generation the late phase reads (a one-frame lag would give exactly
    two complementary states).
