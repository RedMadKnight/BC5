# 0257 — The night lake: every depth writer, clean against patched, in one run

**Question.** Exp 0253 (F313) found that, within a run, the night lake's visible depth-only writers
draw the same records in clean and patched frames. But the filtered journals saw only 4–5 of the 9
colour-mask-0 depth writers of exp 0245's unfiltered frame; the largest group, PS 0x11d373e600
(17 draws), never matched. In one run with clean and patched frames, which draws write the lake's
depth buffer (0x1129ec0000) before the full-screen water draw, and does any shader, count or
indirect argument differ between the states?

**Setup.**
- Granted by the top session after exp 0253. Ran 2026-10-24 14:13–14:23, after the box was
  power-cycled (13:52, boot 9f3e0da8) and the TCP session's exp 0260 build (`~/bc5-work/BOX-QUEUE`).
  `/var/home` was at 70–71 %.
- **Binary:** exp 0251's private `kyty_emulator`, kept in `~/bc5-work/exp0251` and built 2026-10-23
  22:06 by `build0251.py` (the shared tree of 2026-10-23 with `edit0194.py`, `patch0245.py` and
  `patch0251.py`), run through the bench's own launcher copy (old values: no PRT, old skip list).
  - The shared builds changed overnight: the held tail is on by default (F312), the second title's
    launcher sets `BC5_DIRECT_CS_PREFIX=1`, and the tiler's detile scratch is pooled (F311).
  - None of that is in this binary or launcher, so the run compares with exps 0248–0253, not with
    today's shared builds.
- **Run:** `ab0257.sh` / `bench0257.sh` (exp 0253's, renamed; the usual conditions: 26 frozen-view
  shots, 3-s `dmesg` poll and kernel stream, live saves checksummed) with an unfiltered journal:
  `BC5_DIRECT_DRAW_JOURNAL=150:40`, `_EVERY=10`, no `_PS`: windows of 40 graphics buffers every
  10 s. That turned out to be about one frame, since unfiltered windows count every buffer. Without a filter the journal prints each draw's line, exp 0245's
  depth-state line and edit0194's indirect arguments, but not the user-data extras.
- **`dw0257.py`** counts every draw with Z_ENABLE and Z_WRITE_ENABLE whose depth write base is
  0x1129ec0000.
  - A frame runs from its own HTILE + stencil fill (CS 0x11d0288a00 with 2752 or more groups, F310)
    to its full-screen draw (PS 0x11d01d7100). That excludes the previous frame's passes after its
    full-screen draw, and frames whose fill is outside the window.
  - Per state it gives the count and the colour-mask-0 share. Per pixel shader it gives the draws
    and summed indirect argument per frame, and it lists the shaders seen in one state only.
  - A first version counted from one full-screen draw to the next. In 40-buffer windows that found
    no complete frame, and in exp 0245's 120-buffer windows it took in about 30 post-draw writers.
- For comparison, `dw0257.py` also ran over exp 0245's two unfiltered windows, from runs 15 min
  apart on exp 0245's private binary:
  - Z2: a clean moment, ts03 at 0.8 %;
  - Z3: a patched one, ts00 at 22.1 % and ts01 at 7.3 %.

  That binary has no `_EVERY` and no indirect-argument lines.

**Result** (`raw/`).
- **Box state.** No kernel fault, timeout or reset: the amdgpu dmesg count stayed at 120, the
  `.out` has 0 fault lines, and the stream has only routine lines. The live saves' checksum was the
  same before and after (1a39860996fdac5c). The run wrote an 82 MB run directory and a 90 MB journal.
  The journal's 21 windows held 8590 draw lines (1.9 MB); each window holds exactly one full-screen
  draw, at about its 21st buffer.
- **W257a was patched throughout:** 18.2–25.1 % in all 26 shots. So there is no clean phase to
  compare within this run. All 21 windows caught their frame's fill: 13 frames between patched
  shots, 8 before the first shot or at its edge.
- **Every depth writer of a patched frame.**
  - 128–129 draws per frame write the lake's depth before the full-screen draw (`raw/W257a.dw.txt`),
    from 36 pixel shaders. 43–44 of them are colour-mask-0, from 10 shaders.
  - The depth-only shaders are 0x11d373f100 ×16, 0x11d1d88300 ×11, 0x11d1dd6400 ×7, 0x11d090d900
    ×2, 0x11d0a98300 ×2, 0x11d1e2f300 ×2, 0x11d1d33200, 0x11d28b1000, 0x11d29c9500 and (9 of 21
    frames) 0x11d0e05600.
  - The largest writer is a colour + depth one, 0x11d29ea100: 32 draws, about 3500 summed vertices
    per frame.
- **Why exp 0253 missed the big depth-only group.** exp 0245's 0x11d373e600 runs here at 0x11d373f100,
  0x11d28b0500 at 0x11d28b1000 and 0x11d29c8a00 at 0x11d29c9500: shifts of 0xb00, beyond the prefixes
  exp 0253 used.
- **Against exp 0245's clean window Z2** (2 frames, 130.5 writers per frame, 42.5 depth-only),
  matching shaders by kind and nearest address within 0x2000: all 35 of Z2's shaders are present
  in W257a, and 30 have the same count. The differences are 0x11d1d88300 12 → 11,
  0x11d1e2f300 1.5 → 2, 0x11d373e600 15 → 16, 0x11d29e9600 36 → 32, 0x11d4690600 3 → 4, and
  W257a's occasional 0x11d0e05600.
- **Z3, exp 0245's patched window** (2 frames at 2560×1440, 117.5 writers per frame, 37.5
  depth-only), against Z2:
  - 32 of Z2's 35 shaders matched, 25 with the same count;
  - the same three directions as W257a: 0x11d29e9600 36 → 32, 0x11d1d88300 12 → 11, 0x11d4690600
    3 → 4;
  - also 0x11d373e600 15 → 12 and a few single colour draws fewer.

  0x11d0e05600 is in neither Z2 nor Z3.

**Verdict.**
- **The full set of depth writers is nearly the same in patched and clean frames.** Every shader of
  Z2's clean frames writes depth in W257a's patched frames, most with the same draw count. The
  depth-only work is 43–44 draws against 42.5. No depth-only shader appears in patched frames only
  (0x11d0e05600 is occasional and absent from the patched Z3).
- **One difference repeats in both patched samples:** 0x11d29e9600, the largest writer that also
  draws colour, issues 32 draws per frame instead of 36, and 0x11d1d88300 one fewer.
  - These are cross-run comparisons with two clean frames, and exps 0251/0253 saw per-run draw
    counts move as much (0x11d1d88300: 12, 10, 10, 7) without following the patches within a run.
  - But a colour + depth writer with four draws fewer fits G-buffer cells left at the cleared
    value better than any depth-only difference does.
- **Next:**
  - a run with `_PS` on 0x11d29e9…/0x11d29ea… (prefix `11d29e`) and the full-screen draw, with
    `_EVERY`, until one run has both states;
  - then compare that writer's draws, records and indirect arguments within the run, clean against
    patched.
- `dw0257.py` (fill-to-full-screen frames) and the unfiltered windows are the reusable tools. 40
  buffers per window is about one frame at this scene.
