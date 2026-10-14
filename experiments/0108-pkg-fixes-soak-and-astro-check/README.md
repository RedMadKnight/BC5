# 0108 — the night's fixes over 600 s in the menu, and ASTRO BOT with tonight's binary

**Question.** Two checks before proposing the new knobs for the play shortcut:
- Do `BC5_DIRECT_PACE_FIX` and `BC5_DIRECT_REMEMBER_UNMAPPED` (experiments 0103 and 0105) hold
  for ten minutes?
- Does tonight's binary change ASTRO BOT? It carries the `init_once` fast path (0107); every other
  addition is behind a knob that is off.

**Setup.** Unattended, 2026-10-15:

| run | time | binary | what |
|---|---|---|---|
| 399 | 00:51 | tonight's (patch as of e885800) | ASTRO BOT, play settings (`bc5-run.env`), 90 s, no input |
| 400 | 01:01 | tonight's | second title, menu; play shortcut's settings plus both knobs; fresh save, one cross at 80 s; 600 s |
| 401 | 01:13 | the source from before experiment 0103 (`bc5LleAgc.cpp.before-0103`, `libAmpr.cpp.before-0104`), rebuilt | as 399 |
| 402 | 01:16 | tonight's again, restored and rebuilt (`git diff` identical to the committed patch) | as 399 |

**Result.**
1. **Menu soak (run 400).**
   - Frame rate per 100 s window, 100–595 s: 36.8, 37.2, 37.0, 37.1, 37.0 fps; median frame
     26.0–26.3 ms.
   - No failed or timed-out job and no given-up wait (the piece summaries all say "0 given up").
   - No GPU fault in dmesg during the run.
2. **ASTRO BOT.**

   | run | binary | fps, 40–85 s | GPU page faults (dmesg) |
   |---|---|---|---|
   | 399 | tonight's | 59.96 | 50 lines at 00:52:56, about 21 s in, while loading |
   | 401 | before 0103 | 59.98 | none |
   | 402 | tonight's | 59.96 | none |

   - Run 399's fault was a CB/DB write permission fault at 0x800109bc0000. Its submitter was
     thread `bc5-ring`, with MORE_FAULTS set.
   - The job did not fail and the journal records nothing about it.
   - The address has bits above 40 set, the class of experiment 0056 (F110).
   - It did not recur with the same binary (402).

**Verdict.**
- Both knobs hold for ten minutes in the menu at a steady 37 fps.
- Tonight's binary leaves ASTRO BOT at 60 fps on its title screen.
- Run 399's fault was a one-off during loading. One run each with the old and the new binary
  does not prove that it predates tonight; it is noted here in case it comes back.
