# 0363 — Has ASTRO BOT regressed on the integrated shared builds?

**Date.** 2026-10-28. **Branch.** `exp/0300-rt-dispatch-sync`. **Box.** Standing GO until 23:00 (the maintainer away);
the lock shared with exps 0360/0361 and the water session; the kernel log streamed; stop at the first reset.

**Question.** ASTRO BOT (PPSA21564) has not been run since the one-ring change (F412/F416), the IB cut (exps
0349/0350), the host-resolved indirect (0346), the soft-wait bound (0343) and the job-arena fix (exp 0359, on only
for PPSA03671). On the integrated shared normal build (exp 0361: 1000ad2a) does its first level still run at the
F99/F100 rate (59–60 fps with the timestamps scaled), with no crash, kernel line or TIMEOUT, and does the job-arena
fix log "off" for this title? If something regressed, which change caused it?

**Setup.** `raw/astro0363.sh` (on the box, under `~/bc5-work/exp0363/`): the route of `tools/scripts/astro-route.sh`
(2026-10-21: the title screen, X at 40 s, the save loads, X at 65 s, then from 80 s twenty rounds of walking and
jumping) through `KYTY_BC5_INPUT_CMD`; a private copy of `play-astro.sh` with its own log (the one-line diff checked);
the title's saves copied to a private root given through `KYTY_BC5_SAVEDATA_DIR` (the live ones hashed before and after,
never written); RT as the shared input.cfg says for this title (`RayTracing.PPSA21564=off`, the maintainer's
setting); `KYTY_BC5_FPS_COUNTER=1` for the per-second flip count, summarised per 20-s window; `sudo dmesg -w`
streamed beside the run; the emulator (the script's own) stopped at 200 s, or at the first crash line in the log or
amdgpu line in the kernel log. Baseline: F99/F100 (the first level 59–60 fps), exp 0269's table (the level's first
part 34–42 fps with the maintainer's pad; the scripted routes of 2026-10-23/24 at 55–60 fps, never reaching the
geyser), F327 (the geyser 27–28 fps, the one-ring cycle).

**Runs.** A3 (16:29:55, pid 2656939, build 1000ad2a) and A4 (16:38:xx–16:42:18, 200 s) on the shared normal build;
the title's RT off as the shared input.cfg says; `raw/A3.log`, `raw/A4.log`, the play logs and the kernel streams on
the box under `~/bc5-work/exp0363/`. Two earlier starts (A1 16:25, A2 16:28) were aborted by the script's own faults
(a variable used before it was set under `set -u`, and a line-wrapped awk program) right after launching the
emulator, which then ran unsupervised with the lock already cleared — A1 for about two minutes, A2 for one — until
stopped by hand; A3 lost its supervision the same way at the end because the running script file was overwritten
with the corrected copy (bash reads a script as it runs), and its emulator ran 487 s until stopped at 16:38. The
corrected script stops its own emulator before clearing the lock on any exit; the lesson is in memory. The live
saves were hashed before and after every start and never changed (854ea6e43f5d048c).

## Result

- **F465 — ASTRO BOT has not regressed on the integrated shared normal build: the first level runs at 60 fps on the
  scripted route, with no crash, no TIMEOUT and no kernel line, and the job-arena fix stays off for it.** A4, 200 s:
  59.6 / 59.8 / 60.0 fps in the first three 20-s windows (the title screen and the menu), 57.9 in 60–80 s (the
  save's load: one 815 ms gap, as the route's load always had), 59.3 in 80–100 s (into the level, one 42 ms gap),
  then **60.0 fps in every window from 100 s to 200 s** (min second 59.1–59.9, longest gap 19–40 ms) — F99/F100's
  59–60. A3, the same route left running 487 s: the same windows, then 60.0 fps in every window to 487 s (min second
  58.2–60.0, longest gap 18–57 ms), 3 seconds with a gap over 70 ms in all (the load and two early ones). Both runs:
  crash lines 0, TIMEOUT lines 0, amdgpu lines in the kernel log during the run 0 (the stream's 163 lines are the
  ring buffer's history before the run start; A4's marker-based count is 0). The log's first game-fix line reads
  `job-arena fix OFF for PPSA21564 (not set, on for that title)`: off for this title, as designed (the source
  text "on for that title" names the default's rule, not this title's state — cosmetic). So the one-ring change, the
  IB cut, the host-resolved indirect, the soft-wait bound and the job-arena fix's presence have not cost ASTRO BOT's
  first level anything on this route; the geyser (F327: 27–28 fps, the one-ring cycle) is not on it and was not
  measured.

**Verdict.** No regression on 1000ad2a for ASTRO BOT's first level: 60 fps, clean, the fix off. No bisect needed.
Not covered: the lean build 23e233f7 (not run), the geyser and the later levels (exp 0269's route never reaches
them), the maintainer's pad.
