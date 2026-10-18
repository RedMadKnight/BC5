# 0157 — the second title's menu artefact is GPU state inherited from outside the title's buffers; a state prefix before the drawing buffers removes it

**Question.** What does a broken bake of the second title's menu text read that a clean one does
not (experiment 0155, F202), and can the host fix it generically?

**Setup.**
- BC-250 dev box, 2026-10-17 23:27 – 2026-10-18 01:47, the maintainer away; runs 670–686 (run
  numbers 670–689 reserved for this experiment; a sibling session used 700+ at the same time for
  experiment 0156 and rebuilt the same emulator binary — its asynchronous APR path was on in the
  binary from run 672 on and is switched back with `KYTY_BC5_APR_SYNC=1` in every run from 673).
  Kernel 7.2.4-ogc3.1, Mesa 26.2.3, libdrm 2.4.134 as recorded in F13.
- The route and the detector of experiment 0155, unchanged: `~/bc5-work/exp0155v.sh <run> <label>
  [ENV=VALUE ...]` (Initial Setup > View All Settings > Visuals, down ×35 and up ×35 at 2 s a
  step, 88 screenshots 2 s apart from +94 s, kill at +270 s), `score.py <run>` flags a screenshot
  whose menu list area has more than 1 % colourful pixels (the title screen's s47 is left out).
- Host diagnostics added to the KytyPlus patch (`raw/exp0156_host*.py`, applied in that order to
  `src/libs/bc5LleAgc.cpp`; all off by default):
  - `BC5_DIRECT_DRAW_JOURNAL=<t0>:<buffers>[:<min dwords>[:<max rt px>]]` and
    `BC5_DIRECT_DRAW_JOURNAL_PS=<hex prefix>[,...]` (draws whose pixel shader address starts so;
    the second title's UI shaders are all `0x09099c....`) with, per draw, the scissors, colour
    attributes, PS and GS user data, the 64 dwords of every table they point at, the index range,
    the vertex box and first vertex (`bake draw / bake ud / bake table / bake vertices`);
    `BC5_DIRECT_DRAW_JOURNAL_ACB=1` runs it over the compute-queue buffers too;
    `BC5_DIRECT_DRAW_JOURNAL_FIND` takes `layer` (the UI layer's base) and prints the hit's user
    data and table.
  - `BC5_DIRECT_RT_DUMP` formats `r8` and `r16f`, a crop `<fmt>@<x>,<y>,<w>,<h>`,
    `BC5_DIRECT_RT_DUMP_EVERY=<s>` (the dump repeats, file names carry the time) and
    `BC5_DIRECT_RT_DUMP_AT_COMPLETION=1` (the items dumped again at the fence completion of every
    buffer the journal matched).
  - Every memory range a journaled draw reads (vertices, indices, descriptor tables, the paint V#,
    the LOAD_*_REG tables) is copied at submission and compared at the buffer's fence completion
    (`ranges at completion` / `range rewritten in flight`).
  - `BC5_DIRECT_IB_DUMP=0:0:<t0>:<count>:<dir>` dumps the raw buffers the journal matched.
  - `BC5_DIRECT_PREFIX_ALL=1|draws|sx`: the fix candidates (below).
- Offline, on the box (`raw/*.py`): `bakes*.py` (the journal per redraw buffer), `atlasdiff.py`,
  `layerdiff.py`, `holes.py`, `donedump.py` (the dumps against the flagged screenshots),
  `ibstate.py` (raw packets of a dumped buffer), `loadpairs.py` (the register pair tables).
  Screenshots, dumps and journals are game output and stay on the box
  (`~/bc5-data/captures/play-20261017-23NN`, `play-20261018-0NNN`, `exp0157-ib68N`).

**Result.**

*How the menu is drawn* (runs 670–672).
- A layout change redraws a UI layer (3840×2160 RGBA8 in the AMM window, F161) in one graphics
  buffer of 3,100–4,700 dwords with 40–60 `DRAW_INDEX_OFFSET_2` draws, followed 20–120 ms later
  by one or more partial redraws (450–1,100 dwords, 3–11 draws); the final pass composes the layer
  over the scene every frame (F149). Every context register of these buffers comes from
  `LOAD_CONTEXT_REG_INDEX` pair tables in memory (185 pairs at the start, 2–6 per draw); there is
  no `SET_CONTEXT_REG` in them.
- The text is drawn as one quad per text run (pixel shader `0x09099c4300`, premultiplied
  src-over blend `CB_BLEND0_CONTROL 0x65010501`) from a 1024×1024 R8 atlas at `0x11b2dc0000`
  that a compute program (`0x09099c4100`) fills from a 1024×1024 R16F scratch target
  (`0x11b0ec0000`) into which glyph outlines are rasterised with stencil draws (`0x09099c2200`,
  blend `0x60010001` / `0x60070009`, colour mask on and off) when a run of text is new; a
  1024×1024 RGBA8 target (`0x11b15c0000`) is cleared by a compute fill each redraw. The pictures
  (previews, icons, bars) are quads of their own textures in the AMM window.

*What a broken redraw leaves behind* (runs 674–682, 160 layer dumps a run).
- At every flagged screenshot the layer's list area holds 4–19 % transparent pixels (alpha < 128)
  that are absent at clean moments, and the transparency persists until the next redraw
  (`raw/layerdiff.py`). The transparent pixels are exactly the rectangles of the list's elements —
  text runs, icons, rules, the whole highlight row — while the panel between them stays opaque
  (`raw/holes.py`). The scene and the preview show through them: this is the artefact of F179.
- Dumps at the fence completion of each buffer (run 682, `raw/donedump.py`) place the holes after
  both the main redraws and the partial ones. A redraw that re-renders an unchanged layout leaves
  the layer unchanged 15 times and transparent once (run 682, buffers 39 and 40: identical packets
  120 ms apart).

*What is identical between a broken redraw and a clean one.*
- The three texture descriptors of the text draws (atlas R8, a 1×1 white texture, the R16F
  scratch), byte for byte, in all 169 redraws of run 674 (`raw/bakes3.py`).
- The three atlas surfaces: unchanged across every flagged moment (runs 672–673, dumps every 2 s;
  `raw/atlasdiff.py`).
- The colour state at every draw as the packets set it (blend, colour control, target mask,
  export format): the same multiset in every redraw (`raw/bakes4.py`).
- Everything the draws read, re-read at the buffer's fence completion: vertices, indices, the
  descriptor tables, the paint constants and the LOAD_*_REG tables — 0 of 162 buffers with a
  range rewritten in flight (runs 677, 680, 681); completion 0–20 ms after submission.
- The raw packets: the opcode sequence of a broken redraw buffer differs from a clean one only in
  the draw counts of the changed elements (`raw/ibstate.py`); the pair tables set the blend
  register at the same position (run 681, `raw/loadpairs.py`: pair 54 of 61 in flagged and clean
  buffers alike).
- Ruled out by a run each: the pieces (run 678, pieces off: 21 of 88 flagged, holes in the dumps);
  given-up cross-queue waits (13 in run 678 against 70 broken redraws); the vertex ring rewritten
  by the title within 600 ms of submission (run 675: 17 of 169 buffers, 7 of them flagged).
- The rate grows with the host's load: 3 of 88 with a light journal (run 670), 10–27 of 88 with
  the per-draw journal and the dumps (runs 671–682), against 1–9 in experiment 0155.

*The one input that is not in the title's packets.*
- The tracked context state (`tracked context:` line, run 683) shows the title sets the RB+
  blend-optimisation registers `SX_PS_DOWNCONVERT`, `SX_BLEND_OPT_EPSILON`,
  `SX_BLEND_OPT_CONTROL` and `SX_MRT0..7_BLEND_OPT` (ctx 0x1d5–0x1df, Mesa gfx10 register JSON)
  to 0 once, and never in a redraw buffer. Other processes use the same GFX ring during a run
  (`/proc/*/fdinfo`: plasmashell 1.9 s of `drm-engine-gfx`, Xwayland, the on-screen keyboard;
  RADV programs those registers for every pipeline it binds). Whatever ran on the ring since the
  title's last submission leaves its context registers behind; the title re-loads 185 of them per
  redraw and relies on the rest.
- `BC5_DIRECT_PREFIX_ALL=1` puts the pieces' full-state prefix (CLEAR_STATE, then every context,
  SH and uconfig register the title has set so far, ADR 0008) in front of every graphics buffer:

| run | variant | flagged of 88 | transparent layer dumps | fps 110–260 s |
|---|---|---|---|---|
| 678–682 | diagnostics, no prefix (five runs) | 21, 22, 27, 27, 23 | 24–30 of 78 | 38.6–44.0 |
| 683 | full prefix on every graphics buffer, with the journal and dumps | 0 | 0 of 78 | 21.0 |
| 684 | full prefix on every graphics buffer, nothing else | 0 | — | 22.4 |
| 685 | full prefix on the graphics buffers that draw (`draws`) | 0 | — | 38.2 |
| 686 | one `SET_CONTEXT_REG` of ctx 0x1d5–0x1df (the eleven SX registers, tracked values) before the graphics buffers that draw (`sx`) | 0 | — | 37.0 |
| 687 | control on the same build, no prefix | 9 | — | 45.0 |
| 688 | full prefix without CLEAR_STATE on the buffers that draw (`draws` + `BC5_DIRECT_PIECES_NO_CLEAR=1`) | 0 | — | 37.9 |
| 689 | `sx`, the GPU-executed marks carried to the title's buffer | 0 | — | 45.0 |
| 690 | `draws` (full prefix with CLEAR_STATE on the buffers that draw), marks carried | 0 | — | 43.9 |
| 691 | the committed build as it is (`draws` by default) | 0 | — | 42.6 |
| 653 | experiment 0155's baseline (the shortcut as is) | 9 | — | 42.9 |

- The full prefix on every buffer costs half the frame rate: the ring thread submits ~74 small
  graphics buffers a frame and each got a CLEAR_STATE and 1,260 register writes (GPU busy 34 ms a
  frame against 16). Restricted to the buffers that draw it costs 11 %.

**Verdict.**
- The broken "bake" is a redraw of the UI layer whose element draws run with GPU context state the
  title never set in that buffer, inherited from whatever ran on the GFX ring before it; on the
  console nothing else runs there. The holes are the element rectangles drawn without the blend
  the title set once at start-up. Every input in the title's own packets and memory is identical
  between a broken redraw and a clean one, and intact at the fence.
- Generic fix (KytyPlus patch, `bc5LleAgc.cpp`, `BC5_DIRECT_PREFIX_ALL`): the pieces' full-state
  prefix (CLEAR_STATE, then every context, SH and uconfig register the title has set so far) in
  front of every graphics buffer that draws, on by default (`draws`): 0 of 88 flagged in runs 685,
  688, 690 and 691 against 9 in the control (run 687) and 1–9 in experiment 0155, at 43.9 fps
  against 45.0. The eleven SX registers alone (`sx`) remove the artefact at no cost (runs 686, 689)
  and name the state that broke the menu; the full prefix is the default because any other
  register the title sets once could go the same way in another title. The prefix on every graphics
  buffer (`1`) halves the frame rate (the ring thread's 74 small buffers a frame) and is not the
  default.
- Found on the way and fixed with it: a prefixed submission (the pieces' path since experiment
  0118, and this prefix) marked the GPU-executed packets on the host's copy, which dies with the
  call; the soft CP then found nothing marked on the title's buffer and served its waits on the
  CPU, which cost 7 fps with the prefix on every drawing buffer (runs 684–688 against 689–690).
  The marks are now carried to the title's buffer (`SoftCp::alias_gpu_executed`).
- The diagnostics stay in the patch, off by default (see Setup); `KYTY_BC5_APR_SYNC=1` was only a
  control for the sibling experiment's change and is not needed.
- Open: whether other titles rely on more inherited state than these registers (ASTRO BOT's menus
  and the pieces' prefixes were built for the same reason, F88/ADR 0008), and whether the
  compositor's work also explains F182's preview landing in the highlight bar when the artefact
  shows (it is the same hole, seen through to the preview layer).
