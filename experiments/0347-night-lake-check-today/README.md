# 0347 — The night lake on today's shared build: still patched

**Question.** The maintainer, 2026-10-27, after his plays on the RT-on one-ring setup: "woda chyba już działa
poprawnie - przynajmniej w ostatnim przebiegu widziałem że jest ok", then "niech sesja od wody potwierdzi". Does the
night lake now render without its checkerboard patches (F342, F372)? If so, which of the changes since exp 0312 did
it?
- the shared normal build ddfb9456 (exp 0342);
- one ring (`BC5_DIRECT_COMPUTE_RING=-1`, F412) and the exp 0341 guards (`BC5_DIRECT_GPU_CHECK_PRODUCT=1`,
  `BC5_DIRECT_SHADOW_LABELS=1`, F414);
- the NpCppWebApi imports (exps 0328/0329).

**Plan** (the top session's GO of 2026-10-27 ~15:35, the box until 17:00; RT off, as the GO asked unless the metric
needs RT on: F341 found that RT off does not clear the lake).
- **The bench:** exp 0312's lake bench (`bench0347.sh`, `ab0347.sh`: exp 0312's scripts with their paths changed) on
  the shared normal build.
  - The launcher copy `play-pkg-0347.sh` is today's `play-pkg.sh` 5b469087 with exp 0299's three edits plus its own
    mount log; everything else is as integrated (one ring, both guards, `RING_DEPS=dcb`).
  - The private working directory and lake save of exp 0299. The config `input-0347.cfg`: exp 0194's with RT off and
    MangoHud off.
- **The metric:** `patch0197.py`'s patch share in each of the 20 frozen-view shots; a shot at 8 % or more is patched,
  as `rd0312.py` counts it.
- **The base rate:** 78 earlier bench runs with at least 10 shots in `experiments/*/raw` (one file per run tag). 13
  of them (17 %) came out clean (at most 15 % of their shots patched), 12 mixed and 53 patched (at least half).
  - So one clean run would not show a fix. The plan was one run, and a second only if the first came out clean.
- **Rules:** the guard, our own lock line in the empty BOX-LOCK, the kernel stream, the live saves dc9d4f25fc2d41ca
  compared only, stop at the first reset.

**Setup as run** (boot dff92150, six minutes old at the start; build ddfb9456; launcher 5b469087).
- **15:42.** The guard found an empty BOX-LOCK and no emulator. `~/bc5-work/exp0346` was already taken, so 0347 was
  claimed on the box and in the repo at once, and our lock line went in. Live saves dc9d4f25fc2d41ca.
  - `play-pkg-0347.sh`: 5 lines added, 4 of them replacing originals (`raw/play-pkg-0347.diff`). The config:
    `raw/input-0347.cfg`.
  - The kernel stream ran throughout (`raw/kernel-stream.txt`).
- **W1, 15:43:18–15:48:13** (`raw/W1.ab.txt`, `raw/W1.out`):
  - no switches, so the launcher's own settings: one ring (no "compute ring" lines), RT off (1,883 ray-tracing-off
    lines), nothing on the skip list;
  - 20 frozen-view shots, 15:46:22–15:47:58.
- **Stopped after W1:** the maintainer watched the run and wrote "Możesz zatrzymać. Widzę że patche na wodzie są"
  and "Nieważne czy rt jest on czy off". So no second run and no RT-on run.
- **No shot was viewed:** the 22 shots were deleted on the box at 15:48, unviewed.
- **Released 15:48:52:** the lock line removed, no emulator, no launcher or bc5-mount left.

**Result** (`raw/`).
- **No kernel event:** 0 fault lines and 0 ring timeout or reset lines in the run's dmesg. The stream holds three IPv6
  lines and one clocksource watchdog line ("Watchdog remote CPU 8 read timed out", 15:46:39).
- **Live saves:** dc9d4f25fc2d41ca before, after and at the release.
- **The lake was patched in all 20 shots:** 25.9–33.3 %, mean 29.6 %.
  - That is higher than exp 0312's P1 (18.5–24.2 %, two rings, build d02f4696) and inside the range of the earlier
    patched runs (exps 0233/0235: medians 22–30 %).
- **The frame rate:** 30 flips in 1.015 s at t 284 s, the same as P1.

**Verdict.**
- **Refuted: the night lake is not fixed.** On today's shared build, with one ring, both guards and the NpCppWebApi
  imports, the frozen view was patched in every shot. The maintainer saw the patches on screen during the run, and
  sees them with RT on as well as off.
- **No change since exp 0312 removed the patches:**
  - one ring did not (as F374 found before);
  - neither did the guards, the imports or the new build.
- **Why the maintainer saw clean water:** the lake comes out clean in some runs and patched in others with nothing
  changed (13 of 78 earlier bench runs clean, a few clean within a run). His last play was likely a clean one.
- **The cause stays open (Q21).** Exp 0312's run J1 is the next step on it: P1 with every depth read sized by the
  draw journal, and the culling buffers' two-state pages tested frame by frame.
