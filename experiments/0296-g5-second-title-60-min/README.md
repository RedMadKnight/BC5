# 0296 — G5 attempt: the second title for 60 minutes on the shared build, RT off

**Question.** Does the second title pass gate G5 (`docs/PHASES.md`): a 60-minute hand session on the default shared
build with no GPU hang, fault or machine-down, recorded with the kernel stream?

**Setup.**
- **The session.** The maintainer plays by hand from his own saves (checksum c0ee58b92c0cadc2 at the start; his play
  changes them, so they are not restored afterwards). He uses the desktop shortcut "BC5 emulator", which runs
  `play-any.sh`. Opening the package from its menu (File → Open package / Recent) starts `play-pkg.sh` on the shared
  normal build (`~/bc5-work/kytyplus-build`, binary 893f8ab4; tree as in D19, patch
  0001 on main). Ray tracing is switched off in the emulator menu (Emulation → Ray tracing, F343, kept per title).
  RT off is the condition F351 ran 63 minutes clean under, on a private build. The maintainer agreed to record it:
  "tak, możesz nagrać - zagram za 30-40 minut".
- **Launcher state.** `play-pkg.sh` e6879ede: exp 0288's `MALLOC_ARENA_MAX=2` on the package mount (F353, added
  2026-10-25 09:00); the ten-program `KYTY_BC5_RT_BUILD_PGM` list (F343). The box was power-cycled at 08:41 after
  exp 0294's machine-down, so this is a fresh boot with a fresh package mount.
- **Recording** (on the laptop; nothing is started, stopped or written on the box):
  - `stream0296.sh`: `raw/kernel-stream.txt` (journalctl -k -f) and `raw/journal-stream.txt` (the play's GPU
    journal, probe, TIMEOUT and fault lines only). Both are tied to the BOX-LOCK line
    "MAINTAINER PLAYING | G5 attempt, exp 0296".
  - `sample0296.sh`: `raw/samples.txt`, one line a minute from /proc and sysfs. It reports MemAvailable, swap, GTT,
    the RSS of the emulator and of bc5-mount, and whether the mount has `MALLOC_ARENA_MAX=2`.
- **Pass rule.** G5 passes if at least 60 minutes of play show no `amdgpu` fault, timeout or reset line in the
  kernel stream, no TIMEOUT or probe line in the journal, no new devcoredump, and no crash in the play log. Menu
  restarts (exit 75) and loads count as play. Frame-rate dips are noted but are not part of the gate.
- **After the session** (read-only): the play log `~/bc5-work/play-pkg-last.log`, its "ray tracing off" lines (to
  confirm RT was off), the capture directory's journal, `~/bc5-data/captures/devcoredump/`, and the saves checksum.

**Result.**
- **The session** ran 09:08:08–09:27:26 (19.2 min of title time, t 1155 s; pid 67941, normal build 893f8ab4).
- **It ended at a game stop, not a GPU one.** At slot 4 the title said that more data had to be installed and
  would not go on (exp 0298, F361). On the maintainer's word ("Możesz sam wyłączyć grę. Zachowaj save") the
  supervisor copied the saves (`~/bc5-work/exp0296/saves-at-stop-092717`, f4e9ef9eab0442c2), stopped the emulator
  with SIGTERM (exit 0) and checked the saves again: unchanged.
- **RT was on for most of it.** The play log has "ray tracing off" only at t ≈ 941 s (the menu switch, saved to
  `input.cfg`), so RT was on for the first 15.7 minutes and off for the last 3.5. The README's condition
  (RT off) was therefore not met.
- **No GPU trouble:**
  - kernel stream (`raw/kernel-stream.txt`): 0 amdgpu lines, IPv6 notices only;
  - journal extract (`raw/journal-stream.txt`): hold summaries only, `GIVEN UP 0`, no TIMEOUT, probe or fault line;
  - devcoredumps: 7 before and after; play log: no timeout line.
- **Memory** (`raw/samples.txt`, which also covers exp 0298's test session, 09:34–10:01, because the emulator came
  back within 10 minutes): MemAvailable at least 293 MiB, swap at most 1,524 MiB, GTT ~12.65 GB. bc5-mount ran with
  `MALLOC_ARENA_MAX=2` (`mount_arena2=1`), at 687–726 MiB RSS.

**Verdict.** Not a G5 pass: 19 minutes, not 60, and mostly with RT on. A game-logic stop ended the session, not a
fault. What this session adds: about 16 minutes with RT on along the maintainer's own route (slot 4) with no hang,
fault or timeout, while S6N's scripted route hangs at ~2 minutes with RT on (F356, F358). G5 needs another session.
