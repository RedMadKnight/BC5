# 0104 — the menu's UI layer is opaque black: the UI middleware's first full clear, on a fully mapped layer

**Question.** Experiment 0102 left the black menu background open. Two candidates remained: the UI
layers hold opaque black, or the final blend's destination lacks the scene. Which is it, and who
writes it?

**Setup.** All runs unattended, menu only:
- the play shortcut's settings (undeferred flips, `multi`, aliases);
- `BC5_DIRECT_REMEMBER_UNMAPPED=1` (0103);
- a fresh save each time and one cross at 80 s; nothing else is pressed;
- 2026-10-14 23:30 to 2026-10-15 00:02.

New CPU-side diagnostics in the patch (`0001-bc5-lle-agc.patch`), all off by default:
- **Draw journal, layer lines.** The final pass's line now also reports what backs the layer at that
  moment: the guest's mapped ranges and the direct path's GPU mappings. It also remembers layer 0's
  base.
- **`BC5_DIRECT_RT_DUMP` additions.**
  - A `layer:<w>:<h>:<fmt>` item dumps that remembered layer.
  - A surface in the AMM window is read only when the guest maps all of it. Experiment 0100
    found that unmapped AMM pages abort the title when touched.
  - `rgba8` dumps report an alpha histogram (0 / 1–127 / 128–254 / 255) and write the alpha
    channel as a PGM.
- **`BC5_DIRECT_DRAW_JOURNAL_WATCH=1`.** Every automatic AMM map of the layer's size (0x1fe0000
  bytes, 3840×2176 RGBA8) is watched (`bc5_watch_surface`, called from `libAmpr.cpp`). The journal
  then lists only the draws and dispatches that touch a watched surface:
  - by a colour target based in it, with CB_COLORn_INFO, CB_BLEND0_CONTROL, CB_COLOR_CONTROL and
    the clear words;
  - or by user data holding its base >> 8, directly or in a table.
- **`KYTY_BC5_AMM_ZERO_AUTO=1`** (libAmpr). It zero-fills the memory an automatic AMM map has just
  allocated. With `KYTY_BC5_AMM_TRACE=1`, maps of 1 MiB or more also report how many of their pages
  were non-zero.

| run | what |
|---|---|
| 376 | draw journal from 95 s |
| 377 | menu buffers dumped (`ibdump-377`, private), `BC5_DIRECT_FIND_ALL` for the scratch and layer values |
| 378 | the old layer address: coverage only; the scratch 0x114c6c0000 dumped |
| 379 | layer backing at the final pass |
| 380 | layer and scratch dumped (`layer:` item) |
| 381 | the same plus the AMM trace |
| 382 | the same plus `KYTY_BC5_AMM_ZERO_AUTO=1`, screenshot at 120 s |
| 383 | `BC5_DIRECT_DRAW_JOURNAL_WATCH=1` from 55 s |
| 384 | the final composition 0x11d0404200 skipped (`BC5_DIRECT_SKIP_PGM`), screenshot at 120 s |
| 385 | nothing pressed (the screen-reader dialog), layer dumped |
| 386 | the same with the watch; the colour export format and shader mask added to its lines |
| 387 | the same; the first 32 dwords of the UI shaders' paint buffer added |

**Result.**
1. **The layer moves between runs.** With a fresh save the title composes one layer. Its address
   differed in every run: 0x81db010000, 0x81da790000, 0x81d9d60000, 0x81dbc70000, 0x81d8840000,
   0x81da740000. Hard-coded addresses from earlier experiments do not carry over.
2. **This layer is not sparse.**
   - It is one automatic AMM map of exactly 0x1fe0000 bytes (type 12, prot 0x30), made at about
     63 s.
   - It is never unmapped, and it is fully mapped for the guest and for the GPU (shared memfd
     pages; runs 379–383).
   - Experiment 0101's sparse layer (8 tiles, prot 0x90) was another surface.
   - The title makes five full maps of this size: one at about 10 s and four at 60–63.5 s.
3. **Fresh memory is zero.** Every automatic map of 1 MiB or more had 0 non-zero pages when
   mapped (run 382, AMM trace). Stale memory is ruled out; zero-filling changed nothing.
4. **The layer holds opaque black.**
   - Run 380: all 8,294,400 pixels have alpha 255; 95.7 % are (0,0,0).
   - Run 382: 8,068,229 pixels alpha 255, 184,523 alpha 0, about 41,000 in between.
   - The alpha image shows: alpha 255 everywhere, alpha 0 in tight boxes around each menu label,
     and alpha 255 again in the glyphs.
   - The final pass is a plain premultiplied "over" (`dst·(1−a) + src`, from its disassembly,
     private). So the background is black, and the scene shows only inside the label boxes:
     the "letters" noise and the user's "animation visible on the highlighted item".
5. **Who writes it** (run 383).
   - The UI middleware is Coherent Gameface (`libcohtml.Prospero.prx` in the guest log).
   - Every repaint of the layer starts with a 6-vertex draw blended ONE/ZERO
     (CB_BLEND0_CONTROL 0x60010001). Premultiplied draws follow (0x65010501). The pixel shaders are
     0x09099c4300 and 0x09099c5200; both export colour = paint × coverage as FP16.
   - The paint comes from a buffer the CPU fills. So the opaque black is the paint of the first
     full-screen clear.
   - Repaints happen while the menu is built (60.5–79.8 s), then **never again** through 123 s.
     The page is static; no animation or fade is running.
   - Run 332 (experiment 0080, synchronous submission) had the same black background, so this is
     not the CPU/GPU race behind the missing letters.
6. **The scene underneath is complete** (run 384, final composition skipped). It shows a forest
   hillside with the player character in the foreground, fully lit and textured. The layer covers
   all of it.
7. **The screen-reader dialog sits on an opaque layer too** (run 385, nothing pressed). Its layer
   0 has alpha 255 in all 8,294,400 pixels. Layer 1 is the 33 MB surface mapped at about 10 s
   (0x80d36d0000).
8. **The export is right** (run 386). The UI draws export FP16 ABGR (SPI_SHADER_COL_FORMAT = 4,
   Mesa `sid.h` V_028714_SPI_SHADER_FP16_ABGR) with CB_SHADER_MASK 0xf, so alpha is written by the
   shader, not filled in by the CB.
9. **The paint data holds opaque black** (run 387). It is a buffer of float4 records, stride 16,
   512 records. Its entries include (1,1,1,1), (0,0,0,0) and, in some repaints, a record "5 0 0 0"
   followed by (0,0,0,1). Which record the background quad uses depends on its vertex attributes,
   which were not read.
10. Experiment 0105 found the title's frame pacing broken. With it fixed (run 391), the label boxes
    and the broken letters are gone, and the menu is complete. **The background stays black.**

**Verdict.** The black is the UI middleware's own opaque clear of the full layer: alpha 255 written
by the GPU from CPU-provided paint, on a layer the title maps in full. It is not stale memory, not
the blend, not the scene, and not the submission race. Our GPU executes these draws as written.
The difference from the console, if there is one, must be in the data or the setup. The label
boxes that let the scene through were a timing artefact; experiment 0105 removes them. Open:
- whether the console shows this screen ("Initial Setup", fresh save) and the screen-reader dialog
  over black by design. With the menu now complete, that looks plausible;
- if not, which input makes Gameface clear with opaque black. Candidates:
  - a system parameter (the title asks for 1, 100, 208, 210; KytyPlus returns 0 for 210, which it
    does not know);
  - a view or page state set by game code that waits for a signal we never deliver.

The next test is the main menu past Initial Setup: does it show the same opaque layer? Our save
directories stay empty, including the play shortcut's `_SaveData-pkg-play`, so the title keeps
its progress somewhere else (open). Run 385 therefore again started from a fresh state. Nothing
was pressed in it, because with a real save the first cross could start New Game.
