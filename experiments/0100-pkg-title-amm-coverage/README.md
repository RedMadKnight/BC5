# 0100 — the second title's UI layer 0 is almost entirely unmapped in the AMM window

**Question.** How much of the two UI layers found in experiment 0099 is mapped in the guest's
AMM window when the final pass uses them?

**Setup.**
- The render-target dump no longer reads inside the AMM window (0x8000000000–0x9000000000).
  Instead it reports the guest's mapped ranges there (`Bc5ForEachMappedRange`), and whether
  the direct path maps the whole range for the GPU.
- Reading there is unsafe. Run 368's stop ("AMM virtual-memory unmap is unsupported",
  `kernel/memory.cpp`) came from KytyPlus's handler for an access to an unmapped AMM page,
  triggered by the dump's own read: 0x81db8c0000 lies inside UI layer 0. It was not an unmap by
  the title, so experiment 0099's open question is answered.
- Run 369 (22:32): the play shortcut's settings, a fresh save, one cross, coverage at 110 s.
  Raw: `raw/run369-amm-coverage.txt`.

**Result.**

| layer | address | guest-mapped | for the GPU |
|---|---|---|---|
| 0 | 0x81dacf0000 (RGBA8 3840×2160, 33,423,360 bytes) | 507,904 bytes in 9 pieces of 32–96 KiB | not all |
| 1 | 0x80d36d0000 | all 33,423,360 bytes, one AMM mapping | all |

The pieces of layer 0 are spaced about 0x2b4000 apart, alternating 48 KiB, 48 KiB, 32 KiB,
48 KiB and 96 KiB.

**Verdict.** Answered:
- UI layer 0 is a mostly unmapped surface: about 1.5 % of it has backing memory.
- On the console the title must map the rest by a mechanism we do not perform, or perform at the
  wrong time. Candidates: AMM map commands executed in GPU order, a memory pool commit, or
  aliasing of other physical memory into this window.
- The GPU's writes to the unmapped parts are lost, and its reads of them return something that
  composes as opaque black. This is the black background.

Next: how the title is meant to map this layer. A survey of other emulators' AMM handling is
running.
