# 0059 — the tree the reflection traversal loops on is not broken

**Question.** Experiment 0058 found the second title's ray-traced-reflection traversal (compute
program 0x11d049aa00) looping forever once its multi-draw packets run. Which data is bad, and who
writes it?

**Setup.** Host (patch 0001), all off by default:
- `BC5_DIRECT_SKIP_PGM=<hex list>`: drop a program's dispatches in any buffer.
- `BC5_DIRECT_SNAP=<va>:<bytes>:<every>`: guest memory copied every <every> submissions to the
  capture directory, 8 files in turn, fsync'd; private.
- `BC5_DIRECT_FIND_VA=<lo>:<hi>`: journals each dispatch whose COMPUTE_USER_DATA pairs point into
  the range, from SET_SH_REG and LOAD_SH_REG_INDEX.

Also used:
- the hung waves' SGPRs and VGPRs from the host watcher's dumps (0058);
- `BC5_DIRECT_WATCH_VA` (exp. 0024);
- the dumped programs (private).

Runs 272–278, 2026-10-12 21:28 – 2026-10-13 08:17. Raw summaries are in `raw/summary.txt`.

**Result.**

1. **The hung waves walk two PSR_BVHL trees.** Their node-buffer descriptor s[56:59] has stride 8:
   - run 272: base 0x12102af700, 1,171 entries;
   - run 276: base 0x12102af700 for 278 waves, 0x12101d6800 (822 entries) for 57.

   In their VGPRs the loaded node words cycle through a few values, e.g. 0x000000c5:0x00000435.
2. **No CP packet touches the tree** (run 274, with the multi-draw packets off).
3. **Only two programs receive the trees' addresses in user data** (runs 277, 278).
   - 0x90985f200 gets the tree's base. It is a bare `s_endpgm` followed by metadata.
   - 0x11d0287900 gets base + 0xc0. It is a copy kernel: per thread, if the index is below a count
     from a constant buffer, it does `buffer_load_format_xyzw` through s[0:3] and
     `buffer_store_format_xyzw` through s[4:7]. The tree is its source, not its destination.

   Whatever builds the trees gets their address some other way (memory tables) or runs on the CPU.
4. **The trees are the same with and without the multi-draw packets.** Snapshots of the tree at
   0x12102af700 are equal in every summary measure:
   - with the multi-draw packets (run 276, before its hang) and with `DRAW_INDIRECT` only (run 278,
     no hang);
   - 44 entries of −1, 16 zero, the same type histogram;
   - the same header ("PSR_BVHL", 0x257c, 0x2498);
   - the same entry at byte 0x100 whose link (0x105) names its own offset.

   That entry is the tree's normal encoding, not a fault (F114 is corrected accordingly).
5. Skipping the traversal (`BC5_DIRECT_SKIP_PGM=11d049aa00`, run 273) moved the hang to the
   2,533-dword shadow-map buffer at 89 s, and the machine went down.
6. The maintainer noticed the menu's background missing in some of these configurations; not yet
   tied to one.

**Verdict.** Partly answered. The static trees are fine. What sends the traversal into an endless
loop under the multi-draw packets is in its other inputs:
- the rays;
- the instance list that the multi-drawn objects (characters) add to;
- per-object trees built at run time;
- the traversal's own stack.

Next: the traversal's other descriptors (s[60:63], s[64:67], s[68:71], s[76:79], s[80:83],
s[88:91], s[96:99] in the hung waves) and what changes in them with the multi-draw packets.
