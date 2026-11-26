# 0095 — the second title's display buffers are 0x1125f00000 and 0x1127ee0000 (3840×2160)

**Question.** Experiments 0091–0094 treated 0x1125f00000 as a UI layer. What are the display
buffers the title registers with VideoOut, and which passes use them?

**Setup.**
- The guest log of run 351 (`sceVideoOutRegisterBuffers2`, logged by KytyPlus).
- Run 358 (20:37): draw journal from 105 s for 60 buffers, searching for 0x1125f000 and
  0x1127ee00.
- Run 359 (20:40): the render-target dump gained a "-lin" mode (pitch = width, no tiling); both
  display buffers dumped linearly.

**Result.**
- The title registers two display buffers, 3840×2160, `pixel_format` 0x8100000022000000,
  `tiling_mode` 0: 0x1125f00000 and 0x1127ee0000.
- 0x1125f00000 is therefore a display buffer, not a UI layer. 0x114c6c0000 (2560×1440 RGBA8) is
  the 2560×1440 target that cs 0x11d0404200 writes.
- In the journaled draws and dispatches, 0x1127ee00 appears nowhere. 0x1125f000 appears only in
  the shared bindless table 0x11e0007aa0, entries 0 and 1, which dozens of passes bind.
- Read linearly, both display buffers are stripes, identical in their statistics. Read tiled as
  64 KiB render-target blocks, 0x1125f00000 showed the menu twice, side by side and stacked. They
  are tiled, but not in the layout assumed: `tiling_mode` 0 does not mean linear here.
  TODO(verify) the display buffers' swizzle.

**Verdict.** Corrected and narrowed:
- The screen shows display buffer 0x1125f00000, which holds the menu over black.
- The pass that writes the display buffer, upscaling 2560×1440 to 3840×2160 and putting the UI
  over the scene, reaches it only through the shared bindless table, so the journal cannot pick
  it out by address.
- The final pass of 0094 (cs 0x11d0404200) writes 0x114c6c0000 from the display buffer's layers.
  Its role is unclear: a capture or copy of the frame.

Next:
- find the display buffers' swizzle, so that their content can be read correctly;
- identify the display pass by output size. It is a dispatch with 480×270 groups (3840×2160 by
  8×8) or a draw with a 3840×2160 viewport.
