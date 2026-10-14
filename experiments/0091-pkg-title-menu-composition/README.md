# 0091 — the second title's menu composition: the finished scene and the UI layer exist apart

**Question.** Experiment 0090 found the menu's background scene rendered but missing from the
final image. Which compute passes compose the frame, and from which inputs?

**Setup.**
- KytyPlus patch:
  - the draw journal (0089) also logs, for every 2560×1440 compute pass (`DISPATCH_DIRECT`
    320×180), `COMPUTE_USER_DATA_0..15` (sh 0x240–0x24f, Mesa gfx10 register JSON), plus the 16
    dwords behind each user-data pair that forms a mapped address;
  - the render-target dump (0090) gained `rgba16f` and `rgb10a2`.
- Image descriptors were read with KytyPlus's format numbering (`gpu_defs.h`: 36 = 11_11_10
  float, 50 = 10_10_10_2 unorm, 56 = 8_8_8_8 unorm) and the gfx10 T# fields for width and height.
  Swizzle mode 27 corresponds to 64 KiB render-target blocks.
- Runs 348–351 (2026-10-14 18:27–18:40): the play shortcut's settings, a fresh save, one cross.
  Raw: `raw/runs348-351.txt`. The images are private.

**Result.**

| image | written by | holds |
|---|---|---|
| 0x116da40000 2560×1440 11_11_10F | (scene upscale) | the scene at output size, HDR, correct |
| 0x1158260000 / 0x116fa20000 2560×1440 10_10_10_2 | cs 0x11d03f8800 (reads 0x116da40000 and 0x116fa20000, plus a 4×4 matrix) | the finished, tone-mapped scene: bright and correct |
| 0x1125f00000 (descriptor 3840×2160 10_10_10_2) | — | the menu's UI layer over black. Shown at 3840×2160 it wraps, so the true pitch or size differs (TODO(verify)) |
| 0x114c6c0000 2560×1440 8_8_8_8 | cs 0x11d0404200 (reads only 0x1125f00000 through its image table, plus two buffers of constants) | the screen: UI over black |

- The small levels of the chain (240×135 down to 15×9) hold a blurred, darkened copy of the
  scene.
- 0x11cb2c0000 384×216 R32F is a low-resolution depth (mean 2,248, maximum 10,000).
- No inline draw of the journaled buffers targets 0x1125f00000. The only full-screen draw into
  the final target has `CB_TARGET_MASK` 0 and no pixel shader: a depth-only pass.
- KytyPlus's `sceSystemServiceGetHdrToneMapLuminance` returns 80/1000/0 nits, not 0 (checked
  after a survey of AnyPS5, which returns SDR values 100/100/0).

**Verdict.** Narrowed down:
- The finished scene (0x1158260000) is correct.
- The final pass composes the screen from the UI layer alone.
- The scene must therefore enter the UI layer, either drawn into it before the UI or sampled by
  the UI's own background element. The pass that should do this is not among the inline draws.

The UI is most likely drawn from nested command buffers (`INDIRECT_BUFFER`), which the journal
does not follow yet. Next: journal the draws of nested buffers, and find what writes the scene
into 0x1125f00000 or samples 0x1158260000 there.
