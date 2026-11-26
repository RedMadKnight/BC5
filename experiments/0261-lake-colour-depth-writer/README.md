# 0261 — The night lake: the colour + depth writer PS 0x11d29e9600, clean against patched in one run

**Question.** Exp 0257 (F318) found the full set of the lake's depth writers nearly the same in
patched and clean frames, with one difference repeated in both patched samples against a clean
window of another run: the largest writer that draws colour as well as depth, PS 0x11d29e9600
(0x11d29ea100 in W257a), issued 32 draws per frame instead of 36. Within one run that has clean and
patched frames, does that writer draw fewer times, with other records or arguments, in the patched
frames?

**Setup.**
- Granted by the top session after exp 0257: 1–2 runs, at most about 20 min. GO at 14:32, ahead of
  the TCP session's catch run.
  - W261a 14:33–14:39, then W261b 14:40–14:46 (the first had no clean phase); analysis until 14:48.
  - Boot 9f3e0da8; `/var/home` at 71 %.
- **Binary:** exp 0251's private `kyty_emulator` (`~/bc5-work/exp0251`, built 2026-10-23 22:06:
  the shared tree of 2026-10-23 with `edit0194.py`, `patch0245.py`, `patch0251.py`), through the
  bench's own launcher copy; not today's shared builds (held tail, CS prefix, tiler pool).
- **Runs:** `ab0261.sh` / `bench0261.sh` (exp 0253's, renamed; 26 frozen-view shots, the 3-s `dmesg`
  poll and kernel stream, live saves checksummed) with `BC5_DIRECT_DRAW_JOURNAL=150:12`, `_EVERY=10`
  and `_PS=11d01d7100,11d29e` (the full-screen draw and the writer by prefix). A second run only if
  the first lacks a clean or a patched phase.
- **Summaries:** `cmp0245.py` (the writer's draws before each full-screen draw), `args0261.py` (its
  draws and indirect arguments per window by state; exp 0253's `args0253.py` with the per-window
  counts keyed by the matched prefix, which crashed on a prefix match), and exp 0253's `wr0253.py`, `rec0253.py` and
  `cells0253.py` (its user data, inline buffer descriptors and per-draw records) with the writer as
  `11d29e`. Raw files are kept under 1 MiB each.

**Result** (`raw/`).
- **Box state.** No kernel fault, timeout or reset in either run: the amdgpu dmesg count stayed at
  120, the `.out` files have 0 fault lines, and the stream (`raw/W261ab.kern.txt`) has only routine
  lines. The live saves' checksum was the same before and after both runs (1a39860996fdac5c).
  The journals were 140 MB (W261a) and 112 MB (W261b), with 0.98 and 0.51 MB of draw lines. Every
  raw file is under 0.2 MB.
- **The two runs.**
  - W261a was patched in all 26 shots (21.3–31.3 %).
  - W261b was patched from ts00 to ts09 (35.8–45.5 %), at 11.6 % at ts10, and clean from ts11 to
    ts25 (1.5–1.8 %): 42 patched and 60 clean frames by `cmp0245.py`, and 7 patched and 9 clean
    windows.
  - The writer ran at 0x11d29e9c00 in W261b.
- **Within W261b the writer is identical in clean and patched frames.**
  - **Draws:** 17 draws before every full-screen draw, in all 60 clean and 42 patched frames
    (`raw/W261b.cmp.txt`).
  - **Arguments:** per window 102 draws and 1062 summed vertices, in every clean, mixed and patched
    window, with 36 zero-count draws each. Every argument slot holds the same vertex count in both
    states, and no slot differs (`raw/W261b.args.txt`).
  - **Records:** its fully journalled per-draw records (inline V# at user data 0–3, draws with at most
    16 records) are the same in both states: 12 of 12, and 43 of 43 with every dword
    (`raw/W261b.cells*.txt`).
  - The render size changed through the run as before (2048 to 3328, `raw/W261b.surf.txt`).
- **Across runs the writer differs a lot.** W261a's fully patched frames had about 31 draws before
  each full-screen draw. Per window: 198 draws and 19,000–23,000 summed vertices, against W261b's
  102 and 1062. Exp 0257 had 32 (W257a) and 36 (exp 0245's clean Z2).

**Verdict.**
- **The colour + depth writer PS 0x11d29e9600 does not follow the patches.** Within a run with both
  states it issues the same draws with the same arguments and records in clean and patched frames.
  Exp 0257's 36 against 32 was a run property, like the depth-only writers' counts in exps
  0251/0253.
- **Within a run, every depth writer examined so far is the same in both states.** That covers the
  four-to-five depth-only writers (F313) and this colour + depth writer. F318's full set matched
  only across runs, so it is not part of this claim. The patch state is therefore not chosen by the
  draw list or its arguments, as far as they have been compared within a run.
- **What remains is data the GPU reads, not the commands.**
  - the vertex or height data these draws fetch;
  - the textures the full-screen draw and the writers sample;
  - the full-screen draw's own depth, which a full-screen triangle cannot vary per pixel by
    itself.
- **Next:**
  - the full-screen draw's vertex-stage output depth and its constants (ES 0x11d00bdf00), compared
    clean against patched within one run;
  - or the depth buffer read again within one run in both states, located by address as in exp
    0251.
