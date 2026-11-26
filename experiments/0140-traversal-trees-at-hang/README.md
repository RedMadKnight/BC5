# 0140 — The reflection traversal's hang: not our submission order, and the trees it walks have no cycle

**Question.** Experiment 0139 left the leading hypothesis that a per-frame tree is rewritten while the
second title's reflection traversal walks it. Does the hang go away when the host submits one job at
a time? And are the trees the hung waves walk well formed?

**Setup.**
- BC-250 dev box, 2026-10-16 15:52–16:02, maintainer present. New Game at 100 s, the traversal not
  skipped (as experiment 0136's run 560).
- **Run 568:** synchronous submission (`bc5-run.env.pkg-sync`: no `ASYNC`, no `RING_ASYNC`, no
  `MAX_IN_FLIGHT`). Each job finishes before the next is sent.
- **Run 569:** the play settings with a new host knob, `BC5_DIRECT_SNAP_ON_TIMEOUT=<va>:<bytes>`.
  - At the first fence timeout, before any recovery, it copies guest memory once. The hung job is
    still on the GPU then, so the copy holds what it reads.
  - Here: 8 MiB from 0x1210000000, the region of the per-frame trees.
  - The hang watcher ran too.
- **Decoding:**
  - node ids as on RDNA: type in bits 2:0, byte offset `(id & ~7) << 3` (Mesa
    `src/amd/vulkan/bvh/bvh_helpers.h` `id_to_offset`, 0866ae7);
  - box nodes of 4 children followed by 4 AABBs (Mesa `bvh_defines.h` `radv_bvh_box32_node`);
  - the walk from the root id 0x25 that the instance records hold.
- Raw: `raw/runs-568-569.txt`.

**Result.**
- **Run 568:** the same hang. The 922-dword graphics buffer timed out, as did the 942-dword one
  after recovery, and the kernel reset the ring. Strict ordering of our jobs changes nothing.
- **Run 569:** the hung waves walk tree 0x12102af700 (322 waves) and 0x12101d6800 (14), as in
  runs 565–567.
- **Both trees have the magic `PSR_BVHL` in their headers.**

  | tree | root box nodes | triangle nodes | max depth | back-edges |
  |---|---|---|---|---|
  | 0x12102af700 | 44 | 85 | 5 | 0 |
  | 0x12101d6800 | 29 | 64 | 6 | 0 |

  - The root's four children have sensible bounds.
  - Box nodes with two children fill the other two slots with id 0x1e (type 6, offset 0xC0,
    zeros in the header) and an empty box (min above max). The hardware cannot hit those slots.
- **F114's "node that is its own child" (0x105 at 0x100) was a decoding slip:** 0x105 is the
  node at 0x800.

**Verdict.**
- **The hang is not a race between our jobs** (run 568), **and not a cycle in the trees** (run 569).
- What remains is the walk itself:
  - the traversal's per-lane state (its stack in LDS, spilled to scratch, F113);
  - or the inputs it reads beside the trees (rays, the instance table at the time of the walk).
  - Settling it means replaying a hung lane: the wave dump's registers, the trees from the timeout
    copy, and `image_bvh_intersect_ray` as documented for RDNA.
- **A practical test the maintainer can do:** if the title offers a ray-tracing option, switching
  it off should avoid the traversal altogether. Then New Game can run without the skip, and the
  opening (F182) can show whether it waits for the reflections.
