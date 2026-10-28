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
