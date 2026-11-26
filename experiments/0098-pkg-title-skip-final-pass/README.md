# 0098 — without one pass the second title shows its menu scene; that pass blends an opaque layer over it

**Question.** Which pass makes the second title's menu background black?

**Setup.** The play shortcut's settings, a fresh save, one cross. Runs on 2026-10-14:
- run 361 (21:11): `KYTY_BC5_FLIP_TIMING=1`, to learn how KytyPlus reads the flip surface;
- run 362 (21:14): the display buffer dumped with two block families (a new "-fam<n>" option);
- run 363 (21:17): `BC5_DIRECT_SKIP_PGM=11d0404200` (experiment 0059's knob) drops the pass of
  experiment 0094, with the hang watcher running;
- run 364 (21:20): both display buffers dumped with a 2-bit alpha histogram.

**Result.**
- Run 361: the flip surface is 3840×2160, pitch 3840, `tile_mode` 27, `guest_format` 50
  (10_10_10_2), 33,423,360 bytes. That is the height padded to 2176 for 128×128 blocks.
- Run 362: dumps at the start of a submission catch the display buffer mid-frame (nearly black
  with one fragment of text). They are not a reliable view of the shown image.
- **Run 363: with cs 0x11d0404200 dropped, the screen shows the full menu background scene:
  forest, mountains, the character, bright and correct, but without the menu itself.** No fault
  or timeout.
- Run 364: in both display buffers, 7,995,392 of 8,294,400 pixels have alpha 3 (opaque) and
  299,008 have alpha 0. There is no partial alpha. The black background is opaque black.
- The disassembly of 0094 gives the blend: `dst = dst · (1 − a) + layer`, over a list of layers
  sampled from the bindless table, whose entries 0 and 1 are the display buffer 0x1125f00000.
- The guest log has a second buffer attribute call, 2560×1440 with mode 0xf, right after the
  unimplemented `sceVideoOutAllowOutputResolutionWqhdDetection` (NID w7Ipp9Xl7hg; name from the
  local ps5rs NID list).

**Verdict.** Answered in part:
- The black is produced by the pass 0x11d0404200. Its layer is opaque black wherever no menu
  element is drawn. Over the scene it hides everything but the menu.
- The layer should be transparent outside the menu (alpha 0), and is not. Either the layer is
  cleared opaque, or it is the wrong surface: the display buffer, i.e. the previous finished
  frame, fed back as a layer.

Next:
- find what clears or fills the layer, and with which alpha;
- check whether the layer should be a separate UI surface. 0x1125f00000 being both the registered
  display buffer and the layer points to a surface or address mix-up, or a display-plane setup
  (UI plane over scene plane) that the title expects from VideoOut and KytyPlus does not provide.
