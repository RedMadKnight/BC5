# 0141 — Ray queries that hit nothing: the reflection traversal runs without hanging, and the opening still keeps its first shot

**Question.** The second title's reflection traversal (0x11d049aa00) hangs the GPU from New Game on,
so it is skipped (experiment 0123). The maintainer asked for the simplest stand-in: the traversal
runs, but as if nothing were ever hit. Does New Game then pass? And does the opening (F182) move?

**Setup.**
- BC-250 dev box, 2026-10-16 20:05–20:16, maintainer present.
- **Host:** `BC5_DIRECT_BVH_MISS=<program>:<dword offsets>` (KytyPlus patch). It uses experiment
  0137's patched copy in the device's code area, with the program address in the title's register
  tables pointed at it.
  - Each listed `image_bvh_intersect_ray` (5 dwords, NSA encoding) becomes four
    `v_mov_b32 v<vdata+k>, -1` and an `s_nop`.
  - Every query then returns 0xffffffff, the invalid node and no hit (Mesa `RADV_BVH_INVALID_NODE`,
    `src/amd/vulkan/bvh/bvh_defines.h`).
  - Encodings from `llvm-mc -triple=amdgcn -mcpu=gfx1013 -show-encoding`.
- **Offsets:** dwords 1,214, 1,913, 2,755 and 2,950, the program's four BVH queries in the offset
  listing.
- **Runs:**
  - 570 and 571: as experiment 0136's run 560, without the skip, with the knob;
  - New Game at 100 s, ✕ on the start screen at 140 s, 230 s in all;
  - the hang watcher was on.
  - The maintainer closed run 570's window at 83 s, before New Game; run 571 ran to the end.
- Raw: `raw/runs-570-571.txt`.

**Result.**
- **Run 571:**
  - the copy was built and named in the register table;
  - **no timeout and no kernel GPU message** through New Game, the start screen and 90 s of
    the opening, where every run without the skip had hung the GPU (560–569);
  - 32–35 fps from New Game on.
- **The opening still keeps its first shot:**
  - screenshots at 160–225 s show the forest of the start screen without the logo;
  - the opening's subtitles go on (`[agitated growls]`, `[confused grunts]`);
  - the camera does not move, and there are no characters, as with the skip (experiment 0136).

**Verdict.**
- **The traversal's hang is avoided** by making its ray queries return nothing. The program then
  runs to its end and writes "nothing hit", unlike the skip, which leaves its outputs unwritten.
- **The opening does not wait for the reflections.** F182's remaining suspect is cleared; what it
  waits for is elsewhere.
- Before the knob replaces `BC5_DIRECT_SKIP_PGM` in the play shortcut, the game proper after the
  opening needs a run. Earlier today, a session that went past the opening took the machine down
  (play session 19:35, two jobs timed out at about 100 s).
