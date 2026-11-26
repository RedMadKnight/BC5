# 0090 — the second title's menu scene is rendered but never reaches the final image

**Question.** Experiment 0089 found the menu frame composed by compute into a 2560×1440 target
after a 1664×936 scene and a downsample chain. Which of these hold the background scene, and
where does it turn black?

**Setup.**
- KytyPlus patch: `BC5_DIRECT_RT_DUMP=<t0>;<va>:<w>:<h>:<fmt>[;...]`. Once, at the first graphics
  buffer from t0 on, it detiles each listed colour target on the CPU and writes it as PPM.
  - Tile helpers: KytyPlus `graphics/guest_gpu/tile.h`, `RenderTarget64KB`, 4 bytes per element.
  - Address formula: KytyPlus `tests/ShaderRecompilerComputeTests.cpp`.
  - Formats from `CB_COLOR0_INFO` (Mesa gfx10 field layout): 0x40718 R11G11B10 float, 0x40710
    R32 float, 0x8028 RGBA8. The R11G11B10 bit order is TODO(verify).
- Run 347 (`run347.sh`, 2026-10-14 18:16): the play shortcut's settings, a fresh save, one cross;
  seven targets dumped at 105 s. The images are private: shown to the maintainer in chat, not in
  the repo.

**Result** (`raw/run347-rt-dump.txt`):

| target | what it holds |
|---|---|
| 0x113d770000 1664×936 R11G11B10F | the full 3D scene behind the menu (forest, mountains, a character), dark and correct |
| 0x113f230000 1664×936 R32F | its depth |
| 0x1167a20000 832×468 R11G11B10F | the scene at half size |
| 0x1164a00000 960×540, 0x1164c80000 480×270 R11G11B10F | nearly black with faint glows: a bloom bright-pass chain |
| 0x11cb2c0000 384×216 R32F | non-zero, not inspected |
| 0x114c6c0000 2560×1440 RGBA8 | the final image: the menu over black; the scene is absent |

The detiling is right: the scene and depth images are clean, with no block artefacts.

**Verdict.** Answered:
- The background scene is rendered correctly, at full and half size.
- It is lost in the compute composition into the final image. The scene's contribution comes out
  black.

Candidates, TODO(verify):
- an exposure or fade value the composition multiplies by (an auto-exposure chain, or a
  constant the CPU or another queue writes), which is 0 here;
- a composition input that is stale for the race of F145–F147.

Next: dump the small targets of the chain (15×9 and 30×17 levels, 384×216) and the
composition's constant buffers.
