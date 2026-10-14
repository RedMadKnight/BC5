# 0093 — the second title's UI layer: no draw writes it, and the final pass always reads it twice

**Question.** Experiment 0092 found no draw with the UI layer (0x1125f00000) as colour target 0.
Is it written through another colour target, or by a buffer of another kind (compute or ring
buffers)? Does the final pass's descriptor table ever hold the finished scene?

**Setup.**
- KytyPlus patch:
  - the draw journal also lists every colour target that `CB_TARGET_MASK` enables:
    `CB_COLORn_BASE` at ctx 0x318 + n·0xf, `_BASE_EXT` at 0x390 + n (Mesa gfx10 register JSON:
    COLOR1 0x327, COLOR7 0x381, COLOR1_BASE_EXT 0x391);
  - `BC5_DIRECT_FIND_ALL=<t0>:<s>:<hex>[,...]` searches the user data of every buffer kind,
    compute and ring buffers included, with each buffer's own state only.
- Run 354 (19:11): journal from 100 s for 600 graphics buffers.
- Run 355 (19:15): the finder for 5 s on 0x1125f000, 0x11582600 and 0x116fa200.
- The play shortcut's settings, a fresh save, one cross. Raw: `raw/runs354-355.txt`.

**Result.**
- No draw writes the UI layer through any colour target 0–7. The scene draws write 5 targets at
  once (G-buffer: 0x113f230000, 0x1140a90000, 0x11422f0000, 0x11453b0000, 0x1148470000).
- Over 14 frames the final pass (cs 0x11d0404200) always gets the same table at 0x11e0007aa0,
  with entries 0 and 1 both the UI layer.
- In any buffer kind, the scene's addresses appear only as the output of its three writers. The UI
  layer's address never appears directly in user data: it is only ever reached through
  descriptor tables.

**Verdict.** Narrowed down:
- The UI layer is not written by any draw's colour target. It is written by something reaching it
  through descriptor tables (a compute UI pass, or a copy).
- The final pass, on every frame, is given the UI layer where a scene could be expected. That
  table is written by the CPU, so the title itself chooses not to bind the scene. The race of
  F145–F147 cannot explain a choice that is the same over 14 frames.

Open TODO(verify):
- what the title checks before binding the background;
- which compute pass writes the UI layer through a table, found by scanning the 64-dword tables
  of all dispatches for 0x1125f000 in every buffer kind.
