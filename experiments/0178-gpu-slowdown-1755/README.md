# 0178 — The box has run the second title at two-thirds to half speed since 17:57, whatever the binary

**Question.** Exp 0177 left the halved start screen (about 25 flips a second instead of 41–50)
with the GPU clock as the suspect. The maintainer restarted the GPU governor at 21:33. Did that
help? If not, what changed, and when?

**Setup.**
- `lean-check.sh` (exp 0177; it now takes another binary as a third argument, through `BC5_EMU`
  in `play-pkg.sh`). It runs one 90-s start of the second title without input.
- **After the governor restart:** run ld7 on the normal build and ld8 on the lean build.
- **Older slot 1 settings:** run ld9 with slot 1's settings save replaced by the copy of
  2026-10-16. The whole save directory was backed up first (`~/bc5-work/save-backup-0177`) and
  restored afterwards, verified identical with `diff -r`.
- **Older binary:** run ld10 with the binary of 11:58 (`kyty_emulator.0167-new`). Its process name
  differs, so the script neither timed nor stopped it; it was stopped by hand at about 147 s.
  Its journal still gives the flip rate.
- **`flip-rates.sh`** (here) gives the flip rate of every session from the direct path journals,
  one `timing: t … flip` line per flip: the intro (t 20–33 s) and the start screen (t 55–82 s).
  Raw: `raw/flip-rates-2026-10-19.txt`.
- **Read-only checks:**
  - the kernel log;
  - `pp_dpm_*` and `pp_od_clk_voltage`;
  - `sensors`;
  - `bc250-cu-live-manager status`;
  - the GPU watcher's dumps in `/var/tmp/bc5-hang-*.txt` (exp 0160, F229).

**Result.**
- **The governor restart changed nothing.** ld7 ran at 25.1 flips/s and ld8 (lean) gave the
  same picture. `gpu_metrics` still reports about 1055 MHz.
- **The slot 1 settings are not the cause.** With the October settings ld9 ran at 25.0 flips/s.
  The global preferences differ from the October copy in one byte, a trophy counter.
- **The code is not the cause:**
  - the 11:58 binary now gives 19.2 flips/s in the intro and 24.1 on the start screen, the same
    as today's build;
  - the 17:42 binary was still fast at 17:47 (28.2 and 44.8);
  - runs 826 (17:01 build) and 830 (17:42 build) had identical settings.
- **When it happened.** The intro, capped by the title at about 30, ran at 27.5–29.7 in every
  session from 09:31 to the one that started at 17:54. From the session that started at 17:58,
  every one runs at 17.9–20.0, and the start screen at 24.1–26.2:

  | session start | intro, flips/s | start screen, flips/s |
  |---|---|---|
  | 17:11 | 28.2 | 49.1 |
  | 17:17 | 28.1 | 49.9 |
  | 17:47 | 28.2 | 44.8 |
  | 17:54 | 28.5 | 32.3 |
  | 17:58 | 17.9 | 24.3 |
  | 18:08 | 20.0 | 25.3 |
  | 21:51 (11:58 binary) | 19.2 | 24.1 |

- **What happened then.** The GPU watcher halted the waves (`umr -O halt_waves`) at 17:53:38–17:54:01
  (six dumps) and at 17:57:17–18, near the end of the 17:54 session. The 17:57 dump hit
  "Cannot access system ram" errors on the title's addresses. Dumps earlier in the day
  (09:51, 13:38, 15:00–16:09, 16:54, 17:34) left no lasting slow-down.
- **What is still intact:**
  - all 40 CUs are active and routed, with every SE/SH WGP mask at `0x1f`;
  - `power_dpm_force_performance_level` is `auto`;
  - temperatures are 52–54 °C at idle;
  - the kernel log since 18:33 holds only per-ring resets, a page fault and one devcoredump at
    20:19, and no power-management error. The buffer no longer reaches back to 17:57.

**Verdict.** The box itself has been slower since about 17:57, by 1.5× in the intro and 2× on the
start screen, for any build. The governor restart did not restore it. The change coincides with
the watcher's wave halt at 17:57:17 and nothing else on record. TODO(verify) the mechanism: no
read-only view shows what the halt left in the GPU. A reboot is the test, and it is the
maintainer's to do. After it, rerun `lean-check.sh` (normal and lean) and `flip-rates.sh`; the
intro should be back at 28–30 and the start screen at 41–50. Until then, any speed measurement
on this box is off by that factor. `umr -O halt_waves` should not run during play or perf runs.
