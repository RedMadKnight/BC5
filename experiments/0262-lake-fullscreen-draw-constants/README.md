# 0262 — The night lake: the full-screen water draw's own constants, clean against patched in one run

**Question.** Exps 0253 and 0261 (F313, F320) found every depth writer examined within a run the
same in clean and patched frames, so the patch state is not chosen by the draw list or its
arguments. The full-screen water draw (PS 0x11d01d7100, ES 0x11d00bdf00) writes the G-buffer
where its fragments pass GEQUAL against the depth buffer (F305); a full-screen triangle cannot vary
its own depth per pixel, so its vertex-stage output and constants decide what it tests against.
Within one run with clean and patched frames, do the full-screen draw's user data, the tables behind
them, its packet or its depth state differ between the states?

**Setup.**
- Granted by the top session after exp 0261: 1–2 runs, at most about 20 min. GO at 15:20 after
  the TCP session's catch run and its exp 0255. One run, W262a, 15:18–15:24 (box clock), and
  analysis until 15:25. Boot 9f3e0da8; `/var/home` at 71 %.
- **Binary:** exp 0251's private `kyty_emulator` (`~/bc5-work/exp0251`, built 2026-10-23 22:06 from
  the shared tree of 2026-10-23 with `edit0194.py`, `patch0245.py`, `patch0251.py`), through the
  bench's own launcher copy; not today's shared builds (held tail, CS prefix, tiler pool).
- **Runs:** `ab0262.sh` / `bench0262.sh` (exp 0261's, renamed; 26 frozen-view shots, the 3-s `dmesg`
  poll and kernel stream, live saves checksummed) with `BC5_DIRECT_DRAW_JOURNAL=150:12`, `_EVERY=10`
  and `_PS=11d01d7100` alone; on gfx10 the vertex stage's user data are the GS registers, which the
  journal prints with the first 64 dwords of each table they point at. A second run only if the
  first lacks a clean or a patched phase.
- **Summaries:** `fs0262.py`: for every dword of the draw's packet, its PS and GS user data, each
  table (and its address) and its depth-state line, the distinct values in clean and in patched
  frames and the values of one state never seen in the other; plus exp 0253's `wr0253.py`
  (descriptors and ranges) and the usual journal summaries. Raw files under 1 MiB each.

**Result** (`raw/`).
- **Box state.**
  - No kernel fault, timeout or reset: the amdgpu dmesg count stayed at 120, the `.out` has 0
    fault lines, and the stream has only routine lines.
  - The live saves' checksum was 1a39860996fdac5c before the run (15:18:04) and db52cb5f327c3de5
    after. The top session moved 17 stray 3-byte `.blocks` sidecars (F319) out of the live save
    folders at 15:19, with the maintainer's OK, so the change is theirs; the bench uses its private
    copy.
  - The journal was 85 MB with 240 draw lines.
- **W262a had both states:** clean ts00–ts07 (1.6–2.1 %), patched ts09–ts19 (10.5–26.7 %, ts08 at
  4.5 %), clean again ts21–ts25 (1.6–2.0 %). The journal holds 108 full-screen draws in clean
  windows, 72 in patched ones and 60 in mixed ones.
- **Every input of the full-screen draw is the same in clean and patched frames**
  (`raw/W262a.fs.txt`).
  - 305 dwords are constant and equal in both states: the draw packet, most user data, most
    table dwords, and the depth state (Z on, no write, GEQUAL; F305).
  - The depth-state fields that vary (HTILE base, `DB_DEPTH_SIZE_XY`, the stencil buffer) follow
    the render size, with the same 6 values in both states.
  - The table addresses behind the user data are new nearly every frame (ring allocations).
  - **Varying dwords overlap.** The varying dwords of the vertex stage's three per-frame tables
    (GS user data 0, 4, 6) and the PS table at user data 0 behave like camera matrices with
    jitter. In each, the patched frames' values are almost all also seen in clean frames: 0–3
    patched-only values per dword, and 11 of 18 for the three most varying dwords, against 19 of
    26 clean-only.
  - **The frame counter is the one exception.** One dword has no value shared between the states:
    the PS table at user data 4, dword 7, a counter that is new every frame (108 clean values from
    about 9,700 to 13,500, 72 patched values from about 11,200 to 12,400, inside the clean range).
- `wr0253.py`'s ranges (`raw/W262a.wr.txt`) show the same: the varying floats keep the same ranges
  in both states.

**Verdict.**
- **Within a run, the full-screen water draw is issued identically in clean and patched frames.**
  The packet, depth state, user data and every journalled constant behind them match.
- **Together with F313 and F320, every lake draw compared within a run is the same in both
  states.** That covers the visible depth-only writers, the colour + depth writer and the
  full-screen draw, with their arguments and journalled constants. The about 85 other colour +
  depth writers of F318 have not been compared within a run yet. Within what has been compared,
  the patch state is not chosen by the draws' commands or constants.
- **It must come from memory the GPU reads during those draws.** Candidates:
  - the vertex or height data the writers fetch through their per-draw records;
  - textures beyond the static noise image (exp 0235);
  - depth or HTILE contents left from an earlier pass.

  So the depth buffer itself, which F307 showed differs in the patch cells, is the place to look,
  within one run in both states.
- **Next:** read the depth buffer and the G-buffer within one run in both states, 0248-style but with
  exp 0251's whole-memory read, at the same frame size, and compare the cells' depth clean against
  patched. If the writers' commands are equal but their depth differs, the fetched vertex data are
  the next read.
