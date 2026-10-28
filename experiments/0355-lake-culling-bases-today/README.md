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
