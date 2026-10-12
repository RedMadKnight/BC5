# 0054 — the second title's missing foreground, unreadable menus and silence

**Question.** Playing the second title (launcher of 0053), the maintainer saw the menus partly
unreadable, only the background in the game (no foreground geometry; texts visible) and heard no
sound. Why?

**Setup.** Launcher defaults of 0053. New in the host (patch 0001):

- `BC5_DIRECT_DROP_TALLY=1`: every 10 s, the packets the filter took out, per kind of buffer and
  opcode (from the backend's executed offsets).
- `BC5_DIRECT_INDIRECT_DRAWS=1`: `DRAW_INDIRECT` (0x24), `DRAW_INDIRECT_MULTI` (0x2c) and
  `DRAW_INDEX_INDIRECT_MULTI` (0x38) pass. The backend policy passes them now (layouts: Mesa
  `sid.h`, `radv_cmd_buffer.c` 0866ae7; a multi draw's count address is a memory operand when
  `COUNT_INDIRECT_ENABLE` is set, TODO(verify) the bit for 0x2c from the 0x4c layout); the host
  keeps dropping them unless the knob is set, and drops a multi draw of more than 65,536 draws.
  With `BC5_DIRECT_GPU_CHECK` the CP also checks an indirect draw's vertex (index) and instance
  counts (≤ 2^22, ≤ 1024; `indirect_check`, `ctest` 38 of 38); in a buffer one of whose CPU-side
  waits was given up the indirect draws are dropped.
- AudioOut2 (`libAudio2.cpp`): a float port with 12 channels (`data_format` 0x00000c00, 7.1 plus
  four height channels) is opened as 8-channel float and each grain mixed down (heights into front
  and back pairs at −3 dB; TODO(verify) the channel order).

Runs 239–243, 2026-10-12 07:15–11:30, 300 s; screenshots in the private capture directories only.
Raw output in `raw/` (runs 242 and 243 left no summary: the machine went down).

**Result.**

1. **The filter dropped the title's scene.** Run 239's tally, per 10 s in graphics buffers:
   37,633 `DRAW_INDIRECT`, 1,379 `DRAW_INDIRECT_MULTI`, 394 `DRAW_INDEX_INDIRECT_MULTI` — opcodes
   the policy had never reviewed (default drop). ASTRO BOT uses `DRAW_INDEX_INDIRECT` (0x25) only,
   which passed. The other drops are known (Sony markers in `SET_UCONFIG_REG`, register
   `WRITE_DATA`).
2. **With the indirect draws the scene and the menus render** (run 241: the forest and the
   character behind the first menu, its text sharp; maintainer's eye on the screenshot), but at the
   title's scene change around 150 s the GPU stops: run 240 after a burst of given-up cross-queue
   waits, run 241 on an instruction fetch at 0x8011d0288000, run 242 (500 ms wait limit) and run
   243 (indirect draws dropped after a given-up wait) hung the GPU and the reset took the machine
   down. Followed up in experiment 0055.
3. **The silence was the 12-channel port**: "AudioOut2: port data_format=0x00000c00 maps to
   Format::Unknown … no audio device will be opened" (run 239); with the mixdown the port opens
   as 8-channel float (run 241), and the maintainer hears the game (2026-10-12, play session).

**Verdict.** Partly passed. Sound: fixed. The missing foreground and the unreadable menus were
indirect draws the policy dropped; letting them through renders the scene, but the second title
then stops at its first scene change, so they stay opt-in (`BC5_DIRECT_INDIRECT_DRAWS=1`, never
unattended: twice the machine went down).
