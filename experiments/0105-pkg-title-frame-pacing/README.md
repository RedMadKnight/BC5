# 0105 — the second title's frame pacing waits for a 170 MHz clock: fixed, intro 18 → 52 fps, menu 18 → 37 fps

**Question.** Experiment 0103 left one post-processing buffer at 34–35 ms a frame in the intro,
and 18 ms in the menu. Its shaders are cheap. Where do those milliseconds go?

**Setup.** Unattended, the play shortcut's settings (undeferred flips, `multi`, aliases),
`BC5_DIRECT_REMEMBER_UNMAPPED=1` (0103), a fresh save:

| run | when | what |
|---|---|---|
| 388 | 2026-10-15 00:15, intro | `BC5_DIRECT_TS_LOG=28`: the title's own GPU timestamps |
| 389 | 00:18, intro | the frame-pacing kernel's parameters and stored times |
| 390 | 00:23, intro | `BC5_DIRECT_PACE_FIX=11d0288100:100/170` |
| 391 | 00:26, menu, one cross at 80 s | the same fix |

New host knobs (patch `0001-bc5-lle-agc.patch`, off by default):
- **`BC5_DIRECT_TS_LOG=<t0>`.** For each job, journals the raw values the title's own GPU
  timestamps took (its RELEASE_MEM / EVENT_WRITE_EOP with DATA_SEL 3). Needs
  `BC5_DIRECT_TS_SCALE` ≠ 1 to collect them.
- **Pace kernel lines in the draw journal.** For dispatches of 0x11d0288100, the journal shows the
  dwords of its parameter block and of its result block.
- **`BC5_DIRECT_PACE_FIX=<program>:<num>/<den>`.**
  - Before a buffer is submitted, it finds that program's dispatches (register state followed
    through the buffer, LOAD_*_INDEX included).
  - It multiplies the program's target time (dwords 0–1 of the block at user data 4–7) and its
    wait limit (dword 2) by num/den.
  - Each block is converted once. Only the title's data changes; the packets and the program
    stay the same.

**Result.**
1. **The 34 ms is before the post-processing starts** (run 388). The timestamps run at 100 MHz
   (5,530,304 ticks in 55.4 ms between two frames). In one frame:
   - the last scene buffer's last timestamp to the post buffer's first: 3,355,672 ticks
     (33.6 ms);
   - the post buffer's first timestamp to the copy-to-display buffer's: 188,516 ticks (1.9 ms).

   Tone mapping, TAA, upscale and the copy together take 1.9 ms. The first timestamp follows the
   buffer's first dispatch, a single workgroup of program 0x11d0288100.
2. **0x11d0288100 is a frame-pacing spin** (its disassembly, private).
   - It reads `s_memrealtime` and stores it.
   - It computes a deadline: the target from its parameter block, or the previous stored time plus
     an offset, capped at now + limit.
   - It then loops on `s_memrealtime` until the deadline passes, storing the time on each pass.
3. **The target is in another clock** (run 389, 87 frames):
   - target / GPU realtime = **1.70000**;
   - the target advances at 169.98 MHz of host time, the GPU's realtime at 99.84 MHz;
   - the GPU's realtime counts from boot: 5.11·10¹² ticks after 51,250 s of uptime.

   The title converts its host-side time into GPU ticks for a 170 MHz clock. `s_memrealtime`
   here counts at 100 MHz, so the target always lies hours ahead and is capped. Each frame
   waited the whole limit: 3,336,720 ticks, which is 19.6 ms at 170 MHz but 33.4 ms here. All 87
   spins measured exactly 33.37 ms.
   - Where the 170 MHz comes from is open. It is not in KytyPlus's HLE: `sceKernelGetTscFrequency`
     returns the measured TSC, 3194.0 MHz. It may be a constant in the title or in its own copy of
     the AGC driver.
4. **Converted (100/170), the frame is paced as intended.**

   | | before (runs 372–375) | after (runs 390, 391) |
   |---|---|---|
   | intro fps | 16.9–18.6 | **52.2** (run 390, 28–38 s), 43.4 (run 391, 28–40 s) |
   | intro frame, median | 54–62 ms | **17.0 ms** |
   | post buffer fence | 34.9 ms | 3.2 ms |
   | menu fps | 18–19 (run 371) | **37.5** (run 391, 90–120 s) |

   - After the fix the kernel waits until the converted target, a few hundredths of a ms here.
     Its stored limit is 1,962,776.
   - The 17.0 ms median is the 60 Hz rhythm the title asks for.
5. **The menu is complete** (run 391, screenshot at 120 s): the title "INITIAL SETUP", all items,
   the ◀▶ values, the description, the icon and the button hints. No broken letters and no boxes
   around the labels.
   - The missing letters (experiments 0080, 0081) and the label boxes (0104) were a symptom of
     this. The 33 ms GPU spin let the CPU run ahead of the GPU and rewrite UI data it had not yet
     drawn.
   - The background is still black (experiment 0104).

**Verdict.** Passed.
- The title paces frames with a GPU spin on `s_memrealtime`, against targets computed for a
  170 MHz clock. Our GPU's realtime runs at 100 MHz.
- `BC5_DIRECT_PACE_FIX=11d0288100:100/170` converts them. That triples the intro's frame rate,
  doubles the menu's, and fixes the menu's text without deferring flips or slowing the game
  thread.
- The knob stays off by default and keyed to this title's program address. The play shortcut is
  not changed without the maintainer's yes.

Open:
- **GPU timestamps.** The title probably reads its GPU timestamps with the same 170 MHz
  assumption, which would make it see 100/170 of the real GPU time. `BC5_DIRECT_TS_SCALE=1.7`
  (experiment 0046) would show it the real time; the play settings use 1.2. Experiments 0046/0047
  found the dynamic resolution following that scale.
- Whether other programs use `s_memrealtime` targets in gameplay. New Game is not tested; the
  run-326 hazard stands.
- Where the 170 MHz comes from: a constant in the title, or a value it reads that we could
  report instead.
