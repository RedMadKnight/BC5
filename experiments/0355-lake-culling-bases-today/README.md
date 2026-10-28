# 0355 — The night lake's culling buffers on today's shared build: are they still at 0x11934d3900?

**Question.** Exp 0354 (F436) found no page of the 8 MiB at 0x11934d3900 that follows the lake's hole state. But
that range is the culling chain's buffers only by F355 and exp 0292, on exp 0251's private binary, and its pages
behaved differently from exp 0312's P1. On today's shared build (normal affa0c22, `play-pkg.sh` 55531ab6), does the
culling chain still bind its buffers at 0x11934d3900, 0x11935d3900, 0x11939d3900 and 0x1193ad3900, so that J1's
null result applies to them?

**Plan** (the maintainer's GO through the top session, 2026-10-28 ~10:00, "option 1 after J1"; RT ON, the
maintainer's standing rule of the same day: "masz sprawdzać już tylko z RT ON").
- **What can be read on the shared build:**
  - The writers' own indirect-argument bases (their SET_BASE index 1) came from the private binary's "draw journal
    args" lines (exps 0283–0292), which patch 0001 does not have. Its `BC5_DIRECT_DISPATCH_JOURNAL` prints each
    draw's SET_BASE base, but for every draw of every graphics buffer with no time window, far too much for a bench
    run.
  - So this run repeats exp 0292's step B, which found the culling chain's buffers on the private binary, with the two
    switches the shared build has.
  - `BC5_DIRECT_FIND_VA=1193400000:1193c00000` (experiment 0059): every dispatch whose compute user-data pair points
    into the 8 MiB around the bases, at most 4 lines per program and offset, from the start. In exp 0292 only CS
    0x11d0376b00 matched, with the four bases in user data 4:5.
  - `BC5_DIRECT_DRAW_JOURNAL_FIND=934d3900,935d3900,939d3900,93ad3900` (experiment 0092): the draws and dispatches
    whose user data, or the 64 dwords behind a user-data pair, hold a base's low dword, with their user data and
    tables. In exp 0292 these named the four programs that bind the buffers by V#, among them the culling CS
    0x11d0375600.
    - `_FIND` works inside the draw journal's window, so `BC5_DIRECT_DRAW_JOURNAL=200:1` with a pixel-shader filter
      that matches nothing (`_PS=ffffffffff`) opens it at the emulator's 200th second and never closes it. No draw
      is journalled, only `_FIND`'s hits.
    - `BC5_DIRECT_DRAW_JOURNAL_ACB=1` adds the compute-queue buffers (exp 0292 saw CS 0x11d0376b00 in both kinds).
- **The bench** (`bench0355.sh`, `ab0355.sh`, `setup0355.sh`: exp 0354's, paths 0355): one run, W1.
  - `play-pkg-0355.sh` is exp 0353's checked launcher renamed, its diff against `play-pkg.sh` exactly the five edits.
  - `input-0355.cfg` is exp 0347's with `RayTracing.PPSA03671=on` (MangoHud off). `ab0355.sh` now requires RT on.
  - The launcher's own settings otherwise: one ring, the guards, the skip list empty (the compaction runs with RT
    on). 20 frozen-view shots, so the lake's patch share with RT on comes as a by-product. No memory reads.
- **The analysis** (exp 0292's scripts, copied unchanged):
  - `fva0292.py` on the `find:` lines, by program and user-data pair, marked against the bases;
  - `vs0292.py` (with the four bases) on the `_FIND` lines: the V#s covering the bases, with their sizes.
  - The journal lines are grepped into `~/bc5-data/priv/exp0355`, summarised and deleted. The journal stays private.
- **The reading:**
  - CS 0x11d0376b00 with the four bases in user data 4:5, and the V#-binding programs as in exp 0292, mean the range
    is the culling chain's buffers on today's build, and F436's null stands for them.
  - Other addresses, or none, mean the buffers moved or are bound differently. J1's pages were then not the culling
    buffers, and the next run reads the right range.
- **Rules:** the guard (an empty BOX-LOCK, our own lock line, no emulator; the bvh session's exp 0352 shares the box),
  the kernel stream, stop at the first reset, the live saves 3f8412c4884ddf14 compared only. Shots are deleted
  unviewed; nothing of the journal is committed.

**Setup as run** (the top session's GO of 2026-10-28 ~10:00; boot 6d79bc01; kernel 7.2.9-ogc3.1; build affa0c22;
launcher 55531ab6).
- **10:03–10:04.** Two guard checks (10:03:33 and 10:04:07) stopped before touching anything. Both said "emulator
  runs" falsely: `pgrep … | cut` made the guard's test the pipe's, which succeeds on an empty result. The check was fixed (`grep .`)
  before the lock was taken. A plain read at 10:04:17 showed an empty lock, no emulator, and exp 0352's "done" line in
  BOX-QUEUE (10:02:17).
- **10:04:31.** Our lock line went into the empty BOX-LOCK, `~/bc5-work/exp0355/CLAIM.txt` was written and a
  BOX-QUEUE line added. Live saves 3f8412c4884ddf14.
  - `setup0355.sh`: `play-pkg-0355.sh` b1ff31cb, its diff exactly exp 0353's five edits (`raw/play-pkg-0355.diff`);
    `input-0355.cfg` 1666716f, RT on, MangoHud off (`raw/input-0355.cfg`).
  - The launcher has no `BC5_LOGGING` line, so `_FIND` and `_ACB` were live.
  - The kernel stream ran throughout (`raw/kernel-stream.txt`).
- **W1, 10:05:08–10:10:10** (`raw/W1.ab.txt`, `raw/W1.out`):
  - RT on (0 ray-tracing-off lines), one ring (no "compute ring" lines), the launcher's empty skip list (no skip
    lines), with the switches of the plan;
  - 20 frozen-view shots.
- **Analysis, 10:10:** the journal's 5,207 `find:` lines and 52,043 `_FIND` lines (19,829 hits with their user data
  and tables) were grepped into `~/bc5-data/priv/exp0355`. `fva0292.py` (`raw/W1.fva.txt`) and `vs0292.py` with the
  four bases (`raw/W1.vs.txt`) ran on them, and the lines were deleted.
- **Cleanup:** the 22 shots were deleted unviewed. The journal stays private:
  `~/bc5-data/captures/play-20261028-1005/gc/direct.log`, 86,712,310 bytes.
- **Released 10:11:04:** the lock line removed, no emulator, launcher or bc5-mount left, a BOX-QUEUE line.

**Result** (`raw/`).
- **No kernel event:** 0 fault lines and 0 ring timeout or reset lines; the stream holds IPv6 lines only.
- **Live saves:** 3f8412c4884ddf14 before, after and at the release.
- **The frame rate:** 30 flips in 1.017 s at t 287 s, with RT on.
- **The lake with RT on was patched in all 20 shots, at 29.3–34.5 %.**
- **One program gets the bases themselves, as in exp 0292** (`raw/W1.fva.txt`).
  - `FIND_VA` names CS 0x11d0376b00 alone, with user data 4:5 holding:
    - 0x11934d3900 (426 lines);
    - 0x11935d3900 (398);
    - 0x11939d3900 (171);
    - 0x1193ad3900 (4,212).
  - It runs in compute-queue buffers (3,938 lines) and graphics buffers (1,269), always as DISPATCH_DIRECT 1 × 1 × 1
    or 2 × 1 × 1. Exp 0292 had 929, 504, 142 and 3,932 lines and the same two dispatch forms.
- **The same programs bind the buffers by V#, at the same bases and sizes** (`raw/W1.vs.txt`):

  | program | DISPATCH_DIRECT groups | V# (stride 4) |
  |---|---|---|
  | CS 0x11d0415700 | 32 | 0x11935d3900, 4 MiB |
  | CS 0x11d0375600 | 0x77–0x7b and 0x434–0x43d | 0x11934d3900 (1 MiB) and 0x11935d3900 (4 MiB) |
  | CS 0x11d04f0c00 | 5 | 0x11934d3900, 1 MiB |
  | CS 0x11d0288a00 (F310's HTILE fill) | 0xac0–0x14c0 | 0x11934d3900, 1 MiB, at table dwords 0 and 16 |

  - CS 0x11d0375600's group counts differ from exp 0292's (0x61–0x66 and 0x451–0x457): a CPU-set count over the
    lake's objects in another view, with RT on.
  - One more program, CS 0x11d042ba00 (4 groups), had 3 hits and no covering descriptor.

**Verdict.**
- **The night lake's culling buffers are where F355 put them on today's shared build:**
  - CS 0x11d0376b00 gets the four bases themselves;
  - the culling compute 0x11d0375600 and three more programs bind the 1 MiB at 0x11934d3900 and the 4 MiB at
    0x11935d3900, the same as on exp 0251's private binary three days earlier.
  - The allocation is fixed, like the depth image's and the G-buffer's (exp 0354).
- **So exp 0354's range was the culling buffers, and its null result stands for them** (F436): no page of the 8 MiB
  follows the hole state.
  - P1's two-state pages 1767–1768 were a property of that run and build, not a stable culling record.
- **Limits:**
  - this run was RT on, as the standing rule asks, while J1 was RT off. Their fixed addresses across builds and RT
    settings make an RT-off move unlikely, but it is not shown.
  - The writers' own SET_BASE bases cannot be read on the shared build; that link stays F355's/exp 0292's.
- **With the culling-buffer lead closed, the lake's open lead is the depth pyramid's generation:** a late phase
  reading the previous frame's pyramid would give exactly two complementary states (Q21).
