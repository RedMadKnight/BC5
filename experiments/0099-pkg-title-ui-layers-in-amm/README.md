# 0099 — the second title's UI layers live in AMM memory that our path does not map

**Question.** The final pass (cs 0x11d0404200) blends opaque-black layers over the menu scene
(experiment 0098). Which surfaces are those layers really?

**Setup.**
- The draw journal logs the final pass's constant buffer (12 dwords) and, for each layer, the
  image descriptor at `table base + index · 32`:
  - the table base is the V# in user data 8–11;
  - the constants are behind the V# at table(user data 12–13) + 0x10;
  - the fields follow the pass's disassembly (private).
- Runs (2026-10-14), the play shortcut's settings, a fresh save, one cross:
  - run 365 (22:06): the constants;
  - run 366 (22:09): the layer descriptors;
  - run 367 (22:11): dumps at the layers' addresses;
  - run 368 (22:15): the dump allowed to read any range mapped in the process (`mincore`).

**Result.**
- Constants (run 365):
  - layer count 1 or 2;
  - UV scales 1/2560 and 1/1440;
  - layer indices 0x3466 and 0x25a8 into the bindless table.

  Entries 0 and 1 of that table, read in 0091–0098, were not the layers. F151–F158's identification
  of the layer as the display buffer was wrong.
- Layer descriptors (run 366): both are RGBA8 3840×2160 with swizzle 27, at 0x81dacf0000 and
  0x80d36d0000.
- These lie in the title's AMM region: the guest log maps "AMM" at 0x8000000000, 64 GiB, and
  type-12 mappings of direct memory into it.
- Run 367:
  - 0x81dacf0000 is not among the ranges the direct path maps for the GPU;
  - 0x80d36d0000 is mapped, and holds zeros at that moment.
- Run 368: KytyPlus stopped the title at the dump's moment with "AMM virtual-memory unmap is
  unsupported: addr=0x81db8c0000" (`kernel/memory.cpp`), an unmap right next to UI layer 0.
  Whether the dump's read set it off is open.

**Verdict.** Answered in part:
- The UI layers that should be transparent outside the menu are transient surfaces in AMM memory,
  which the title maps and unmaps as it goes.
- Our handling of AMM is incomplete in two ways:
  - KytyPlus cannot unmap AMM pages;
  - the direct path does not map the page where UI layer 0 lies, at least at the moment checked.

  The GPU therefore reads or writes these layers through missing or stale mappings. This is the
  most likely root of the black background, and probably of other second-title faults too
  (F109's high address bits).

Next, the deeper fix:
- journal the AMM map and unmap commands for 0x80–0x90_0000_0000 with their timing against the
  GPU work;
- make the direct path follow them (map before use, unmap after);
- implement AMM unmap in KytyPlus.
