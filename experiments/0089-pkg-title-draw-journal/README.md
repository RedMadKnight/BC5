# 0089 — a per-draw journal of the second title's menu frame

**Question.** Where in the second title's menu frame is the background drawn, and is that pass
there at all (experiment 0088)?

**Setup.**
- Backend: `bc5::full_state::for_each_draw` (unit test, 50 cases pass).
- Host: `BC5_DIRECT_DRAW_JOURNAL=<t0>:<buffers>` journals every draw and dispatch of the
  graphics buffers from t0 on, with the tracked state:
  - colour target 0: base, size from `ATTRIB2`, INFO, `CB_TARGET_MASK`;
  - viewport;
  - PS, ES, GS and CS programs;
  - the packet's dwords.

  Register offsets come from Mesa's gfx10 register JSON (`tools/bc5-agc/regdb`). The `ATTRIB2`
  size layout is TODO(verify).
- Run 346 (`run346.sh`, 2026-10-14 18:03): the play shortcut's settings (undeferred flips,
  `multi`, aliases), a fresh save, one cross at 80 s; journal from 100 s for 200 graphics
  buffers. 2,064 draws and dispatches.

**Result** (`raw/run346-render-targets.txt`, `raw/run346-final-target.txt`):
- The scene is drawn at 1664×936, into targets at 0x113f230000 and 0x113d770000.
- A downsample chain follows: 960×540, 480×270, 240×135, 120×68, 60×34, 30×17, 15×9 (a blur or
  bloom pyramid), plus 832×468, 384×216 and 512×512 targets.
- The 2560×1440 target at 0x114c6c0000 is the final image. It is written almost only by compute
  dispatches (`DISPATCH_DIRECT`):
  - three programs with 320×180 groups, which covers 2560×1440 with 8×8 groups (0x11d0404200,
    0x11d03f8800, 0x11d03f7900);
  - smaller passes.

  The only graphics draw into it in the window is a 3-vertex `DRAW_INDEX_AUTO`, a full-screen
  triangle.
- All these dispatches are submitted: none of them is among the filter's drops (experiment 0080).

**Verdict.** Partly answered:
- The menu's frame is composed by compute shaders at 2560×1440. The background therefore comes
  from one of the full-screen dispatches that read the scene and its blurred copies, not from a
  draw.
- The pass is there and runs. What it produces is black, so the fault is in its inputs:
  - the blurred scene targets;
  - something it reads that the CPU or another queue writes.

Next: look at the scene target and the blur pyramid themselves. They are tiled (INFO formats
0x40710/0x40718), so this needs KytyPlus's detiling, which the flip copy already uses
(experiment 0070).
