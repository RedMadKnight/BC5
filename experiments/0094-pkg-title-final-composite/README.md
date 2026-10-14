# 0094 — the second title's final pass blends UI layers over whatever the display target holds

**Question.** Why does the final pass (cs 0x11d0404200) produce the menu over black, when the
finished scene exists (experiments 0091–0093)?

**Setup.**
- The pass's program had been dumped privately in experiment 0049. It was disassembled locally
  with LLVM 21 `llvm-mc --disassemble -triple=amdgcn -mcpu=gfx1013`. The code stays private; its
  structure is described below.
- Run 356 (19:32): draw journal from 80 s for 1,500 graphics buffers, across the menu's
  appearance, searching for the UI layer's address.
- Run 357 (19:36): the user data of the 288-group pass of program 0x11d0288a00, which runs just
  before the final pass in the same buffer.

**Result.**
- The final pass, 50 instructions:
  1. it reads the display target's current pixel (`image_load` from its own output descriptor,
     user data 0–7, 0x114c6c0000);
  2. it reads a layer count and a list of layer indices from a constant buffer (user data 12–13);
  3. for each layer it fetches the image descriptor `table[index · 32]` from user data 8–9
     (0x11e0007aa0) and samples it;
  4. it blends premultiplied: `dst = dst · (1 − a) + src`;
  5. it stores the result.

  The scene is therefore not one of its layers. It has to be in the display target before this
  pass runs.
- Nothing found writes the display target before it:
  - no draw through any colour target (0093);
  - no other dispatch takes it as output image;
  - program 0x11d0288a00's 288-group pass writes a buffer at 0x112adc0000 and reads three buffers
    (geometry or UI data), not images.
- The finished, tone-mapped scene is written by 0x11d03f8800 into 0x1158260000 and 0x116fa20000,
  in turn: a history pair. Nothing found copies it into the display target.
- Run 356: across the menu's appearance, no draw writes the UI layer and no user data names it
  directly.

**Verdict.** Narrowed down:
- The black comes from the display target's own content under the UI.
- The step that should put the finished scene there is missing. Candidates, TODO(verify):
  - a copy that is not a draw or a dispatch (CP DMA of 14 MiB, or a `COPY_DATA` / DMA engine job
    we do not submit);
  - a pass on a queue we do not see;
  - the title writing the scene's descriptor as one of the layers, which it does not do here,
    with entries 0 and 1 both the UI layer.

Next: the display target's content before the final pass. Dump 0x114c6c0000 at a submission
before it: is it black there already, or cleared in between?
