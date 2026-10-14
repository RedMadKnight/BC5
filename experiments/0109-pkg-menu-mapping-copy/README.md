# 0109 — a mapping-list copy on every submission: removed, menu 37 → 49 fps

**Question.** Experiment 0107 found the title's render thread waiting on `g_dev_mutex`. The stack
samples showed `bc5::direct::Device::mappings()` inside `submit_one`, on both the render thread
and the ring thread. What is that copy for, and what does dropping it give?

**Setup.**
- `submit_one` called `dump_shaders(ib, num_dwords, g_dev->mappings())` on every submission,
  under `g_dev_mutex`. The argument copies the whole mapping list: hundreds of entries in ASTRO
  BOT, about 12,000 in the second title's menu.
- `dump_shaders` returns at once unless `BC5_DIRECT_SHADER_DUMP` is set.
- Change (patch `0001-bc5-lle-agc.patch`): the knob is checked before the call, so the list is
  copied only when shaders are dumped. Nothing else changes.
- Run 403 (2026-10-15 01:32, unattended, menu only): run 391's setup, i.e. the play shortcut's
  settings plus `BC5_DIRECT_REMEMBER_UNMAPPED=1` and `BC5_DIRECT_PACE_FIX=11d0288100:100/170`,
  a fresh save, one cross at 80 s.

**Result.**

| | run 391 / 398 (before) | run 403 (after) |
|---|---|---|
| menu fps, 90–120 s | 37.2–37.8 | **49.1** |
| menu frame, median | 25.0–25.5 ms | 19.4 ms |
| intro fps, 28–40 s | 43.4–52.2 | 52.1 |

- No failed or timed-out job, and no GPU fault in dmesg.
- The menu is drawn complete except for the ◀▶ arrows beside two values. They were missing in
  every screenshot of the 600 s run 400 too, which predates this change, while runs 391 and 394
  had them. The arrows vary from run to run.

**Verdict.** Passed. A diagnostic argument copied up to 12,000 mappings under the device lock on
every submission, about 120 times a frame. Skipping it when shader dumps are off gives the menu
+30 % (49 fps) with no change in behaviour. ASTRO BOT gets the same change, with a much shorter
list. Open: the arrows that come and go (a smaller race left over from experiments 0080/0105).
