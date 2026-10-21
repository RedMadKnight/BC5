# 0188 — The second title's speed-ups were its Wwise sink rendering ahead of the device: the host's AudioOut2 queue level did not count advanced grains

**Question.** After the review of analogous projects (`docs/ports/related-projects-review.md`):
1. Does the flip event's delivery (F246: our host queues a copy per re-trigger) feed the second
   title's drifting clock (F243–F245)?
2. If not, what does: the level events copied into every slot of one wait (review §2), or the
   AudioOut2 queue level a Wwise sink renders by (review §4, AnyPS5's note)?

**Setup.** The idle night run of exp 0185/0186 (`idle-run.sh`, slot 1, no input after loading, 30-fps
cap, saves restored around each run), normal build, the clock voice (`KYTY_BC5_AJM_DUMP`) as the
measure. New switches in the host (patch 0001; scripts here: `patch_coalesce.py`, `patch_eqtrace.py`,
`patch_a2trace.py`, `patch_a2advanced.py`, `patch_a2device.py`, `patch_a2cushion.py`):

| Switch | Kind | What it does |
|---|---|---|
| `KYTY_BC5_VIDEOOUT_COALESCE=1` | behaviour | one VideoOut event per (ident, filter), updated in place while unread (FreeBSD kqueue; shadPS4 `TriggerDisplay`) |
| `KYTY_BC5_VIDEOOUT_EVENT_TRACE=1` | diagnostic | per second: flip triggers, how many came while the event was unread, pending copies, counts delivered, `GetEventCount`/`GetEventData` calls |
| `KYTY_BC5_EQUEUE_LEVEL_ONCE=1` | behaviour | a level event is returned once per wait, not copied into every slot (KytyPlus 3eee96a) |
| `KYTY_BC5_EQUEUE_TRACE=1` | diagnostic | per second: waits with events, events, level repeats |
| `KYTY_BC5_AUDIO2_TRACE=1` | diagnostic | per second: AudioOut2 context/port creates, Advance, Push, GetQueueLevel calls (level sum and max), SetAttributes |
| `KYTY_BC5_AUDIO2_ADVANCED=1` | behaviour | AnyPS5's grain model: Advance copies each port's PCM, Push plays the oldest copy, the queue level counts the advanced and not yet pushed grains; for a context with a device, the device's unplayed grains (SDL's queue) beyond `KYTY_BC5_AUDIO2_CUSHION` (default 2) instead of a timer |

`ratio.py` (here) puts the AudioOut2 trace next to the clock voice per 10-s window.

| Run | Switches (besides the measure) | Length |
|---|---|---|
| M0 | event trace | 10 min |
| M1 | event trace, `VIDEOOUT_COALESCE=1` | 10 min |
| M2 | equeue trace, AudioOut2 trace, `VIDEOOUT_COALESCE=1` | 8 min |
| M3 | AudioOut2 trace, `VIDEOOUT_COALESCE=1`, `AUDIO2_ADVANCED=1` (level from a timer) | 10 min |
| M4 | as M3, level from the device's queue, no cushion | 10 min |
| M5 | as M4, cushion 2 grains | 10 min |
| A0, A1 | ASTRO BOT 100 s, defaults / `AUDIO2_ADVANCED=1 VIDEOOUT_COALESCE=1` | 100 s each |
| O6 | New Game opening, no cap, `AUDIO2_ADVANCED=1 VIDEOOUT_COALESCE=1` | 300 s |
| M6 | the new defaults (`patch_defaults.py`), no cap | 10 min |

Raw: `raw/M0-M1.txt`, `raw/M2.txt`, `raw/M2-audio2-trace.txt`, `raw/M2-ratio.txt`, `raw/M3.txt`,
`raw/M3-ratio.txt`, `raw/M4.txt`, `raw/M5.txt`, `raw/A0-A1-O6.txt`, `raw/M6.txt`.

**Result.**
- **The title never reads its flip event (M0, M1).** In 10 minutes 16,853 of 16,855 flips arrived
  while the event was unread; none was delivered, and `sceVideoOutGetEventCount`/`GetEventData` were
  never called. Our host's pending copies grew to 16,447 (a leak; with coalescing 0). The clock
  drifted as before with either setting (M0: 1.21 → 1.69 → 2.98×, a drop, 1.37 → 2.66×; M1: 1.22 →
  1.71 → 3.00×). So F246 is a real host defect but not this title's clock.
- **No level-event repeats (M2):** 1,005 waits returned 1,005 events, 0 repeats.
- **The title's audio goes through AudioOut2, and its clock speed is its advances per push (M2).** It
  pushes 94 grains of 512 frames a second (the device's rate, held by the host's output hold), polls
  the queue level ~450–1100 times a second, and advances (renders) as many grains as the level leaves
  free. Per 10-s window, advances ÷ pushes against the clock voice:

  | window | advances | pushes | ratio | clock voice |
  |---|---|---|---|---|
  | 160 s | 940 | 940 | 1.00 | 1.00× |
  | 190 s | 1232 | 940 | 1.31 | 1.33× |
  | 250 s | 1350 | 940 | 1.44 | 1.45× |
  | 310 s | 1522 | 940 | 1.62 | 1.64× |
  | 340 s | 2457 | 940 | 2.61 | 2.62× |
  | 400 s | 106 | 941 | 0.11 | 0.15× |

  The host's level counted only pushed grains, decaying on a timer, never the grains advanced and not
  yet pushed; so the sink kept finding room, rendered ahead, and every grain beyond the one pushed was
  lost (the host plays the port's current PCM at Push). The title's sound engine — its music, its
  clock voice, the cutscene picture that follows it (F198) — ran that many times fast, and the lost
  grains are the "roughness" of F240. When it rendered less than it pushed (0.11), the same PCM was
  pushed again: the 0.2× collapse of F243.
- **With the advanced grains counted (M3), advances equal pushes in every window and the drift is
  gone** (clock voice 0.86–0.98× for 10 minutes, no rise, no jump, no collapse). The timer-based level
  lost time whenever the queue ran empty, so the title rendered 82–92 grains a second instead of 93.75
  and the device ran short (main port 0.92–0.99).
- **With the level from the device's own queue (M4): advances = pushes, clock 0.95–1.00× (mostly
  0.98) for 10 minutes; the main port 0.974 on average, 224 of 555 s under 0.98.** Counting the
  grains already in the device as queued made the sink start late.
- **With a cushion of two grains (M5): the clock voice runs 1.00× in every 10-s window for 10 minutes
  of the night scene that drifted to 3× in every earlier run but one; advances = pushes = 940 per
  10 s; the main port at 1.0000 on average from t 60 s, 0 s under 0.98, 0 over 1.02, held ~999 ms a
  second with SDL's queue at a steady 42 ms, 0 clears.**

- **ASTRO BOT is unchanged (A0 defaults, A1 with the grain model and coalescing; `astro-check2.sh`
  here):** 0 of 80/81 port-seconds off real time, 0 clears, 58.1 / 58.4 flips a second; its sink
  advances exactly what it pushes (9,115 / 9,210, ratio 1.000), and it has no CPU flip events.
- **The opening without the 30-fps cap (O6, `opening-old.sh` of exp 0187, 300 s): the clock voice
  runs 1.00× everywhere — start screen, menu, the daytime forest and the night jungle — at 44–52
  flips a second; advances = pushes in every window.** So F241's "1/30 s per presented frame" was the
  same defect: the more frames a second, the more often the sink polled and rendered ahead.
- **M6 (the new defaults, night gameplay without the cap, 10 min): the clock voice 1.00× in every
  window; advances = pushes; the main port at 1.0000 from t 60 s, 0 s under 0.98, 0 over 1.02.** The
  night is GPU-bound at ~29.3 flips a second with or without the cap; the menu ran at 42.7.

**Verdict.**
- The second title's speed-ups in cutscenes and gameplay, the progressive night drift, its
  collapses, and the "crackle" were all one host defect: the AudioOut2 queue level did not count
  the grains the title had advanced and not yet pushed, so its Wwise sink rendered ahead of the
  device, and the host dropped the extra grains (or repeated stale PCM when it fell behind). Fixed by
  AnyPS5's grain model, with the level taken from the device's queue beyond a two-grain cushion
  (`KYTY_BC5_AUDIO2_ADVANCED`, now on by default; `=0` restores the old model).
- The flip event's pending copies (F246) are a separate defect with no effect on this title (it never
  reads the event); coalescing is now the default too (`KYTY_BC5_VIDEOOUT_COALESCE=0` restores the
  queue), which also ends the leak.
- The 30-fps cap of exp 0184 is no longer needed (O6, M6): `play-pkg.sh` (here) now defaults
  `KYTY_BC5_MIN_FLIP_RATE` to 0; `=1` still caps.
- TODO(verify): by the maintainer's ear in play, with the pad, through a whole session.
