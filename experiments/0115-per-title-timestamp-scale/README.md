# 0115 — The second title's "170 MHz" was ASTRO BOT's timestamp scale: the scale is now per title

**Question.** Experiment 0105 found the second title pacing its frames against a clock 1.70000 times
the GPU's 100 MHz realtime counter. Where does the 1.7 come from, and can the host give the title
the true clock instead of a per-program correction (`BC5_DIRECT_PACE_FIX`)?

**Setup.**
- BC-250 dev box, 2026-10-15, maintainer present. The second title with the settings of its play
  shortcut (`play-pkg.sh`), intro or menu, no input.
- Runs 430–436 (intro, with 0105's `PACE_FIX`): the title's time sources, found with gdb.
  - The `SceGnmGpuInfo` contents.
  - A dump of the running executable (private, `~/bc5-data/priv`).
  - Hardware watchpoints on the pacing parameter block and on the GPU timestamp query data.
- Run 433 (intro): `BC5_DIRECT_TS_SCALE=1.0`, no pacing fix.
- Runs 437 (intro) and 438 (menu): no timestamp scale anywhere (no `RenderScale` in the input file),
  no pacing fix.
- Run 442 (menu): the per-title scale below, none for this title, no pacing fix, play settings.
- The per-title change is in KytyPlus (`graphics/presentation/window/hostInput.cpp`,
  `hostInput.h`, `settingsOverlay.cpp`; `backend/kytyplus-patches/0001-bc5-lle-agc.patch`).
  Built 2026-10-15 10:24.
- Raw: `raw/runs-430-442.txt` (frame rates from each run's `direct.log` via `frameprof.py`, the
  environment lines before and after).

**Result.**

| run | timestamp scale | pacing fix | intro fps (t 15–28 s) | menu fps (t 90–120 s) |
|---|---|---|---|---|
| 430, 431, 434, 435, 436 | 1.70 (input file) | yes | 49.4–53.9 | — |
| 432 | 1.70 | yes, gdb watchpoint | 46.9 | — |
| 433 | 1.70 (`TS_SCALE=1.0` overridden) | no | 18.9 | — |
| 437 | none | no | 29.2 | — |
| 438 | none | no | 29.2 | 48.4 |
| 442 | per title: none for this one | no | 29.2 | 49.7 |

- **The pacing target's source.**
  - The title builds the target A from a GPU timestamp query plus process-time-counter deltas
    scaled by 1e8 / `KernelGetProcessTimeCounterFrequency`.
  - The query value is written by `RELEASE_MEM` with `DATA_SEL` 3, at 100 MHz on this GPU.
  - Experiment 0046's host scale multiplies such timestamps by k after the job completes.
- **Where k = 1.70 came from.** The input file `~/bc5-work/input.cfg`, shared by both titles, held
  `RenderScale=1.70`. ASTRO BOT's F2 video preset ("1440p class") had written it on 2026-10-11.
  `RenderScale` is applied at start and overrides `BC5_DIRECT_TS_SCALE`.
  - So run 433's `TS_SCALE=1.0` changed nothing: still 18.9 fps.
  - The second title's play settings (`TS_SCALE=1.2`) were never in force either.
- **Without any scale (437, 438),** the target matches the GPU clock (journal of the pacing kernel,
  as in 0105).
  - The intro runs at 29.2 fps, which is the title's own pacing: a limit of 3,336,720 ticks =
    33.4 ms.
  - The menu runs at 48.4 fps.
- **The per-title form (442) behaves the same:** intro 29.2, menu 49.7 fps, menu text complete, no
  GPU timeouts.
- **The per-title format:**
  - `RenderScale.<TITLE_ID>=<k>` is read and written for the running title only (TITLE_ID from
    `param.sfo`).
  - A plain `RenderScale=<k>` is ignored with a log line.
  - Other titles' entries are kept when the file is saved.
  - The F2 *Video* tab reads and writes the running title's entry.
  - The dev box's input file now holds ASTRO BOT's 1.70 under its own TITLE_ID.
  - `BC5_DIRECT_TS_SCALE` was removed from `bc5-run.env` and `bc5-run.env.pkg-noflipdefer`.
  - 0105's `BC5_DIRECT_PACE_FIX` was removed from `play-pkg.sh`.

**Verdict.**
- The "170 MHz" was our own setting: one title's dynamic-resolution scale applied to every title.
- With timestamps left true, the second title paces itself as written, without a per-program fix.
- Its intro runs at 30 fps.
  - 0105's 52 fps came from shortening the title's own frame limit, so it was not a fix.
  - Whether the console shows the intro at 30 fps is open.
- The menu holds 49 fps either way.
- From now on, a title runs with its own defaults (no timestamp scale) until the maintainer sets
  one for it.
- `BC5_DIRECT_PACE_FIX` stays in the host as an opt-in diagnostic.
- ASTRO BOT still applies its own 1.70. Run 443, the first check, took the machine down for another
  reason (experiment 0118). Run 448 (11:24, without graphics pieces, `BC5_DIRECT_PKT_STATS=1`)
  shows:
  - its dynamic-resolution main pass at 2432×1368 and 3328×1872 among the 3840×2160 targets;
  - 53.8 fps;
  - no fault.
