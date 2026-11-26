# 0139 — The reflection traversal walks per-frame trees with the hardware BVH instruction; not the CU count

**Question.**
- Experiment 0138 left open how the second title's traversal reaches the tree its waves loop in.
- What does the program hold in the registers F116 read?
- Does the hang depend on the BC-250's 40 CUs (the PS5 has 36)?

**Setup.**
- BC-250 dev box, 2026-10-16 15:45–15:55.
- Offline: an offset listing of 0x11d049aa00, made by re-encoding its llvm-mc disassembly
  (`llvm-mc -triple=amdgcn -mcpu=gfx1013 -show-encoding`).
- Instance records 120–125 of the table at 0x118c62c100 compared across experiment 0138's
  snapshots:
  - run 565, before New Game;
  - run 566, after New Game, with the traversal skipped.
- **Run 567:** as run 565, with `BC5_DIRECT_CU_MASK=3ffff`, 18 of 20 CUs per shader engine, 36 in
  all (F39a). This tests whether the hang comes from the extra CUs, e.g. scratch sized by the title
  for fewer waves. The maintainer was present.
- Raw: `raw/disasm-notes-and-run567.txt`.

**Result.**
- **The loop of F113 is built around `image_bvh_intersect_ray`** (dword 1,214), the hardware
  ray–box/triangle test.
- **Dwords 1,133–1,212:**
  - `s[16:31]` is loaded from the instance record at `s[14:15]`;
  - the walk starts at the record's root link (`v16 = s30`);
  - the tree's byte address is `s[28:29] << 3`, the high part masked to 22 bits.
  - From the tree header (+0x58), the program then builds:
    - the node buffer descriptor `s[56:59]` (base, stride 8, record count = header +0x60, 0x16204);
    - the BVH resource descriptor `s[28:31]`:
      - base >> 8;
      - box sorting (bit 31 of the second word);
      - size = header +0x58;
      - `0x81000000` in the last word, type 8 in its top bits.
  - At the hung PCs, `s[28:31]` = 12102af7 80000000 0000007f 81000000 is that descriptor, not an
    instance record. This corrects F116's reading.
  - TODO(verify) the descriptor's field layout against AMD's RDNA2 ISA document.
- **The hung waves' record address** is `s[14:15]` = 0x118c62fe00, record 122 of the table at
  0x118c62c100.
  - In the snapshots, records 120–125 name a different tree from one snapshot to the next, always
    with root link 0x25 and flags 0x1f000000.
  - After New Game the trees lie at 0x1210xxxxxx (0x12102adf00, 0x121029e100), next to the hung
    tree 0x12102af700.
  - These trees are built per frame in a ring of memory, not static (F115's "unchanged" tree was
    the same ring slot).
- **Run 567:** the same hang with 36 CUs (dcb 922 timeout, ring reset).

**Verdict.**
- **Not the CU count.**
- **The traversal walks per-frame trees through the hardware BVH instruction.** The leading
  hypothesis is now a lifetime race:
  - the tree the traversal of frame N walks is rewritten by the builder of a later frame while the
    walk runs;
  - a half-written tree can send the hardware walk in a circle;
  - on the console a wait between the builder's queue and the traversal's would hold the builder
    back.
- **Next:**
  - find the builders of the 0x1210xxxxxx trees (the programs given that region in user data);
  - their queue;
  - the waits between them and the 922-dword graphics buffer;
  - whether the host lets a builder run before that buffer's traversal has finished.
