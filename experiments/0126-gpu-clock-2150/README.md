# 0126 — GPU clock up to 2150 MHz: +6–7 % on the second title's start screen, stable, 81 °C at most

**Question.** The BC-250's GPU clock is set by the community governor `cyan-skillfish-governor-smu`
(1850–2000 MHz on the dev box). Does a higher ceiling raise the second title's GPU-bound start
screen, and does it hold?

**Setup.**
- BC-250 dev box, 2026-10-15, maintainer present. The maintainer edited the governor's
  configuration (root only); BC5 changed nothing in it.
- Changes:
  - `max = 2150`;
  - two of the author's commented voltage points enabled, 2125 MHz / 1020 mV and 2150 MHz /
    1035 mV, above the active 2000 MHz / 1000 mV;
  - the commented 2050/980 and 2100/1000 points were left out: they come from a curve with lower
    voltages than the active 2000 MHz point.
- The governor then reported `initial frequency range: 1850..=2150`. With `max = 2150` alone it had
  kept 500..=2000, having no voltage point above 2000.
- `octest.sh 525 526 "1850-2150 MHz"`:
  - run 525: the start screen as in experiments 0123–0125 (play settings, New Game at 100 s);
  - run 526: ASTRO BOT's start, 70 s.
  - Temperatures (`sensors`: amdgpu edge, k10temp Tctl) sampled every second; hang watcher on.
  - `pp_dpm_sclk` was sampled too, but with the governor's SMU set method its current level is
    meaningless.
- Raw: `raw/runs-525-526.txt`.

**Result.**

| | up to 2000 MHz (0123–0125, runs 517–520) | up to 2150 MHz (runs 525–526) |
|---|---|---|
| second title, start screen | 31.3–31.9 fps | 32.8–34.1 fps |
| ASTRO BOT, t 40–65 s | 60 fps (frame cap) | 60 fps; game thread in the host 6.2 ms |
| GPU timeouts, page faults | 0 | 0 |
| highest GPU edge / CPU Tctl | not measured | 78 / 78.5 °C (start screen), 81 / 80.5 °C (ASTRO BOT) |

**Verdict.**
- Passed for 2150 MHz: +7.5 % clock gives +6–7 % fps where the GPU limits, with no fault or
  timeout.
- Going further is limited by heat:
  - the governor throttles at 85 °C and 81 °C is already reached in 70 s;
  - the next points need more voltage: 2230 MHz / 1085 mV, 2300 MHz / 1110 mV.
- Recommendation: stay at 2150 MHz. A higher point only after a long (10 min) temperature test.
- The machine's fan sensors read 0 RPM, with only the pump turning; the cooling's fans are worth
  checking first.
