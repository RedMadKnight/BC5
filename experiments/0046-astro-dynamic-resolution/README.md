# 0046 — ASTRO BOT renders at native 4K here; its dynamic resolution reads GPU timestamps, and scaled it holds 60 fps

**Question.** The maintainer's point (2026-10-10): on the console a game adapts its resolution, and
here nobody chose one; at what resolution does ASTRO BOT render on the BC-250, and can it render
less to reach 60 fps (experiment 0045 left the first level GPU-bound at 17 ms)?

**Setup.** As in 0045 (deferred flip, 24 jobs in flight, `run151.sh` recipe). New in the host:

- `BC5_DIRECT_PKT_STATS=1` also counts the values of `DB_DEPTH_SIZE_XY` (context register 0x07),
  `PA_SC_VPORT_SCISSOR_0_BR` (0x95) and `CB_COLOR0_ATTRIB2` (0x3b0) (offsets from 0x28000 in dwords,
  `tools/bc5-agc/regdb/gfx10.json`) as the game sets or loads them (`SET_CONTEXT_REG` and the
  tables of `LOAD_CONTEXT_REG[_INDEX]`, followed by the host's `hint_targets`), and `RELEASE_MEM`,
  `EVENT_WRITE_EOP` and `WRITE_DATA` by `DATA_SEL`/`DST_SEL`.
- `libSystemService.cpp` reports each system parameter the title asks for once on stderr.
- `BC5_DIRECT_TS_SCALE=<k>`: when a job is done, the host multiplies the 64-bit GPU timestamps
  its buffers wrote (`RELEASE_MEM` / `EVENT_WRITE_EOP` with `DATA_SEL` 3) by k, so the game sees k
  times the GPU time.

Runs 164–170, 2026-10-10 16:40–18:10. "Main 3D pass" below = a colour target and a depth buffer
of the same size bound together. Raw output in `raw/`.

**Result.**

1. **Native 4K.** The main 3D passes run at 3840×2160 with a 3840×2160 depth buffer through the
   whole first level (run 166), besides a half-resolution pass (1920×1080 depth), a 2048×2048
   shadow map and a 960×540 → 240×135 chain.
2. **The title asks the system only for its language** (parameter 1, run 167): no output mode,
   no performance or resolution preset.
3. **It measures the GPU heavily:** about 300 `RELEASE_MEM` CS_DONE with `DATA_SEL` 3 (the GPU's
   64-bit clock counter) per frame in its graphics buffers, about 5 in its compute buffers (run 164).
4. **It has a dynamic resolution that follows them.** With the GPU slowed to about a fifth
   (`BC5_DIRECT_CU_MASK=00010003`, run 168) the main passes drop to 1920×1080 and 2432×1368 from
   30 s on. With the timestamps scaled:

   | Run | Timestamps × | Main 3D pass from 180 s | GPU busy (380–418 s) | Frames | fps |
   |---|---|---|---|---|---|
   | 166 | 1.0 | 3840×2160 | 17.0 ms | — | 57 (0045) |
   | 170 | 1.2 | 3328×1872 | 15.1 ms | 2,251 | 59.2 |
   | 169 | 1.5 | 2432×1368 | 11.7 ms | 2,277 | 59.9 |

   No failed submission; the picture is right (run 170 at 400 s, the window's counter at
   59.99 fps; screenshot to the maintainer only).

**Verdict.** Passed. On the BC-250 the title's own resolution scaler sees too little GPU time and
stays at native 4K, where the frame takes 17 ms; scaling the timestamps by 1.2 lets it settle at
3328×1872 and the first level runs at 59–60 fps. Why the unscaled timestamps read low is open:
the PS5's GPU timestamp rate against the BC-250's 100 MHz (`gpu_counter_freq`), or a budget the
title sets above 16.7 ms, TODO(verify). The play settings carry `BC5_DIRECT_TS_SCALE=1.2`; the
second level and the maintainer's play are to be checked.
