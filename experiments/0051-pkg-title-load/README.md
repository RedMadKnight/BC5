# 0051 — the second title's long load was the host's memory report

**Question.** Experiment 0050 found two or three host memory syncs of 25–80 s in every run of the
second title while it loads. What do they spend the time on?

**Setup.** As in 0050, launcher defaults (the refit skipped). The journal's `timing split` lines
(every 128 submissions) put the time in "direct sync", and each long sync came right after a
`direct by name (growth)` breakdown: every time the imported direct memory grew by 512 MiB the
host listed it by mapping name, walking every view of the memfd (about 11,000 views, aliases
included, over 9 GiB) with `SEEK_DATA`/`SEEK_HOLE` on the game's thread. Host change (patch 0001,
`direct_sync_one`): that breakdown only with `BC5_DIRECT_BREAKDOWN=1`; the one on `-ENOMEM` stays.
`to3d.py`: when a run reaches its steady 3D scene (the first 5 s window after 45 s with at least
80 frames) and the longest stretch without a frame before it. Runs 217–219 and ASTRO BOT runs
220–221, 2026-10-12 01:58–02:30. Raw output in `raw/`.

**Result.**

| Runs | Steady 3D from | Longest gap before it | Longest syncs |
|---|---|---|---|
| 89, 90, 91, 112 (earlier, breakdown on) | 95–140 s | 30–52 s | 30.5 s and 55.3 s (run 89) |
| 180 (breakdown on) | 155 s | 54.8 s | 8.6, 54.1 s |
| 213 (breakdown on) | — | — | 30.6, 48.1, 80.4 s |
| 217, 218, 219 (breakdown off) | 70 s each | 4.5–4.7 s | none over 500 ms; "direct sync" about 10 ms per 128 submissions |

The game then runs at 18–19 fps from 250 s as before (runs 217, 218); run 219 stopped at 167 s on
the usual fault at a heap address with a junk top byte. ASTRO BOT with the play settings (run 221):
420 s, no failed submission, 57.7 fps in the first level. Run 220 was killed by the kernel's
out-of-memory killer at 68 s: it started while the previous run's memory was still being freed
(the kernel log, 02:15:30); nothing in the change touches memory use.

**Verdict.** Passed: the second title reaches its 3D scene in 70 s instead of 95–155 s, with no
pause longer than 5 s on the way; the "five minutes" of loading were mostly the host walking its
own memory for a journal report.
