# 0138 — The reflection traversal's New Game hang: no bad instance record at the hang; the hung tree is named by no record of the known tables

**Question.**
- F140 and F116 suspect the second title's reflection-traversal instance table as the cause of the
  New Game hang (F113): NaN/zero records, or a record that enters a tree at the wrong node.
- What does the traversal hold at the hang, and do the tables show it?

**Setup.**
- BC-250 dev box, 2026-10-16 15:35–15:45, maintainer present.
- **Run 565:** as experiment 0136's run 560 (traversal not skipped, New Game at 100 s), with
  instance-table window snapshots (`BC5_DIRECT_SNAP=118c5f0000:262144:4000`, every 4,000
  submissions). The hang watcher was on.
- **Run 566:** traversal skipped, so no hang. Snapshots continued after New Game, and
  `BC5_DIRECT_FIND_ALL=104:6:8c62c100,8c5f0000,8c626100` listed the dispatches given the table
  addresses in user data.
- `insttab.py` and the F116 record layout (128 bytes: 3×4 transform, tree address >> 3, root link,
  flags).
- Raw: `raw/runs-565-566.txt`.

**Result.**
- **Run 565 hung as before:**
  - the 922-dword graphics buffer timed out about 1 s after New Game;
  - the kernel reset the ring; no wait was given up before it.
- **NaN records occur in the menu, without a hang:**
  - snapshot at t 98.1 s: 19 records of the table at +0x36100 had an all-NaN transform, tree
    address 0, root link 0x25 and flags 0;
  - the snapshots before (96.1–97.4 s) and after (98.8, 99.5 s) were clean;
  - New Game came at 100 s.
  - These are transient states the CPU snapshot catches. They are not what the traversal reads at
    the hang (F140's NaN records were the same kind).
- **The hang watcher dumped 336 waves of program 0x11d049aa00:**
  - 51 at dword 1,224, near the head of F113's loop; the others between dwords 1,855 and 1,884;
  - 322 of them walk the tree 0x12102af700 (descriptor s[56:59] = 102af700 00080012 00000493);
  - s[28:31] = 12102af7 80000000 0000007f 81000000;
  - s[35:36] = the table at 0x118c62c100, s34 = 2–5.
- **No record of either table names that tree,** in any snapshot, before New Game in run 565 or
  after it in run 566.
  - All records have root link 0x25.
  - Flags are 0x1f000000, plus one or two records with 0x08000000.
  - The s[28:31] values seen at the hang therefore do not hold an instance record at those PCs.
    F116's reading of them comes from the record load earlier in the program; the registers are
    reused later.
- **Run 566, programs given the table addresses** (in dispatches of compute buffers of
  7,441–7,498 dwords):
  - 0x09098eb200 (an indirect dispatch);
  - 0x090985f200 (one group);
  - 0x0909875600 (3,456–4,224 groups).
  - These are the candidates for the table's writers.

**Verdict.**
- **F140's NaN records are not the hang's cause.** They appear and vanish in the menu and are
  absent from what the hung waves hold. F140 is corrected by this experiment.
- **How the walk reaches tree 0x12102af700 is not established.** No record of the two known tables
  points there, so the register meanings at the hung PCs need the shader itself.
- **Next:**
  - map the registers of 0x11d049aa00 at dwords 1,213–1,892 (stack, current node, level flag);
  - dump the node buffer and the per-lane stack (LDS, scratch) at the hang;
  - replay the walk of a hung lane on the CPU from those inputs.
  - The writers 0x09098eb200 / 0x090985f200 / 0x0909875600 are the next place to look if the
    replay shows a bad record after all.
