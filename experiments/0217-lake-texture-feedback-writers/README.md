# 0217 — The night lake: who tells the title's texture streamer which mips to load

**Question.** Exp 0212 (F272) found that the patchwork ends when the title lowers some textures'
`MIN_LOD` in its bindless table, and that in patched runs the streamer stops lowering it. Streamers
like this usually decide from GPU feedback: pixel shaders record the finest mip they wanted in a
feedback image (atomic min) that the CPU reads back. Which programs write such feedback? Does the
feedback reach the CPU on our host (ADR 0006's shared pages)? Are their draws dropped (the
indirect-draw check) or skipped?

**Setup.**
- BC-250 dev box, 2026-10-22 20:25 (read-only slot, no emulator), 20:39-20:45 (run F1) and
  21:35-21:41 (run F2), granted by the top session.
- `run0217.sh`: one bench run (exp 0212's `bench0212.sh`, exp 0194 build) with the draw journal on
  the candidates and the water's draws, plus a live read of the water mesh draw's code into
  `~/bc5-data/priv/exp0217`, then `desc0212.py` and `prog0212.py` (counts only).
- `census0217.sh`: from the private disassembly listings `~/bc5-data/priv/<address>.dis` (345
  programs, from earlier experiments; the title's code, never copied off the box). For each
  program it gives the store and atomic mnemonics with counts, and its "exp mrt" exports. Only
  counts leave the box.
- The listings of the water's programs were checked the same way.

**Result** (`raw/census-20261022-2025.txt`).
- **The full-screen water pass writes no feedback.** PS 0x11d01d7100 has no store or atomic, only
  4 render-target exports; its ES 0x11d00bdf00 has none either. The water mesh draw (PS
  0x11d01ff900, ES 0x11d0148800) has no listing and is not checked yet.
- 211 of the 345 programs store or use atomics; almost all are compute programs (no "exp mrt").
- **Four pixel programs look like feedback writers:** 0x11d0c13700, 0x11d0d6c400, 0x11d3269600 and
  0x11d3269800. Each combines one render-target export with an `image_atomic_umin` and eight
  `image_store`s, the usual shape of a streamer's "finest mip wanted" feedback. TODO(verify):
  their descriptors and the CPU side.
- **Run F1 missed the lake** (`raw/F1.txt`, `raw/F1-desc.txt`). The game loaded slot 2's town,
  so the run says nothing about the lake. What holds regardless of scene:
  - The water mesh draw's code, read live into `~/bc5-data/priv/exp0217`. ES 0x11d0148800 is
    complete: no store or atomic, exports 1 pos, 1 prim and 6 param. PS 0x11d01ff900 is longer
    than the 16-KiB window read: no store, atomic or export in that part, and no `s_endpgm`, so
    it is only partly checked.
  - In the town, the candidate 0x11d0d6c400 drew as a screen-space pass reading the G-buffer
    (1664×936 targets). Its atomic target was not decoded.

- **Run F2, the lake** (`raw/F2.txt`). The right save and the lake view were checked; the lake
  was heavily patched (33–44 %).
  - The water mesh draw's code, read whole into `~/bc5-data/priv/exp0217`: PS 0x11d01ff900 has
    2,911 instructions to `s_endpgm`, no store and no atomic, 5 render-target exports. Its ES has no
    memory write.
  - None of the four candidate feedback writers drew at the lake in the journalled windows. Only
    the water's own draws did.
  - The water's pixel stage also reads the bindless texture table of exp 0212, not only its
    geometry stage.

**Verdict.**
- **None of the water's own shaders writes feedback.** Both draws' programs (PS 0x11d01d7100 and
  ES 0x11d00bdf00 from the private listings, PS 0x11d01ff900 and ES 0x11d0148800 read live) only
  export to render targets, positions and parameters. They have no store and no atomic.
- **The four pixel programs shaped like feedback writers do not draw at the lake.** They are the
  ones with `image_atomic_umin` plus `image_store`. One of them, 0x11d0d6c400, drew in the town as a
  screen-space pass over the G-buffer. So they are not the lake's feedback path.
- **Open:** whether the title's streamer uses GPU feedback at all for these textures, and through
  which program. 211 programs write memory, most of them compute. Candidates would have to draw or
  dispatch at the lake and write somewhere the CPU reads. A full, unfiltered draw/dispatch journal
  of a patched frozen view, matched against the census, would list them. The indirect-draw check's
  `cp-skip` count needs that unfiltered journal too.
- The water samples the bindless table in both stages. Which entries it indexes (exp 0212's open
  question) is still to be found, from its code in `~/bc5-data/priv/exp0217` (offline, private).
