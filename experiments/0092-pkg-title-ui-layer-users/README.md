# 0092 — who writes the second title's UI layer and who reads the finished scene

**Question.** Experiment 0091 found the finished menu scene (0x1158260000) and the UI layer
(0x1125f00000), from which alone the final pass composes the screen. Which passes write the UI
layer, and which read the scene?

**Setup.**
- `bc5::full_state::for_each_draw` now follows nested `INDIRECT_BUFFER`s through the reader,
  four levels deep (unit test, 51 cases pass).
- Host: `BC5_DIRECT_DRAW_JOURNAL_FIND=<hex>[,...]` journals every draw or dispatch whose user
  data holds one of the values:
  - user data: `COMPUTE_USER_DATA_0..15` for dispatches, `SPI_SHADER_USER_DATA_PS_0..31` for
    draws (Mesa gfx10 register JSON);
  - either directly, or within the 64 dwords behind a user-data pair that forms a mapped address.
- Run 352 (19:02): the journal through nested buffers.
- Run 353 (19:05): the same, searching for 0x1125f000 (the UI layer), 0x11582600 and 0x116fa200
  (the two copies of the finished scene).
- The play shortcut's settings, a fresh save, one cross. Raw: `raw/run352-render-targets.txt`,
  `raw/run353-find.txt`.

**Result.**
- No draw has the UI layer as colour target 0, nested buffers included.
- 0x11582600 is written directly (user data 0, the output image) by three compute programs:
  - 0x11d03f8800, 320×180 groups;
  - 0x11d03e9600 and 0x11d03e9b00, 208×117 groups.
- No pass takes it as an input directly.
- The UI layer's descriptor sits in a shared descriptor table at 0x11e0007aa0. Dozens of scene
  draws bind that table, so table-level matches on it say nothing about use. The final pass reads
  its first two entries, both the UI layer.
- One draw renders into 0x8214920000 (256×256 RGBA8), an address with 0x82 in bits 39:32; the
  code aliases of 0056 cover one 96 MiB window.

**Verdict.** Inconclusive:
- The UI layer is not written by inline or nested draws to colour target 0. It must be written
  by compute, or with another colour target slot, or at the 0x82 alias.
- The scene is produced but nothing found reads it into the UI.

Possible next steps:
- journal colour targets 1–7 and the compute outputs (user data 0) of every pass;
- compare the descriptor table at 0x11e0007aa0 over several frames: does its second entry ever
  hold the scene?
