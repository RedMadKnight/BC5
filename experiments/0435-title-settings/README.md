# 0435 — each game remembers its own Settings and window mode

## Question

The maintainer, 2026-11-19: "zrób aby każda gra zapamiętywała swoje Settings oraz czy był fullscreen czy nie".
Can each title keep its own settings (the F2 overlay and the Emulation menu) and its last window mode
(fullscreen or windowed), and get both back on its next start, with no change to the shared launchers?

## Setup

Starting point: shared builds of patch `59f00d27` (F861).

What the patch did before this experiment (read from `backend/kytyplus-patches/0001-bc5-lle-agc.patch`):

- One input configuration for every title: `KYTY_BC5_INPUT_CONFIG` (`~/bc5-work/input.cfg`, set in `bc5-run.env`).
  `hostInput.cpp` `Map()` reads it once; the F2 overlay (Pad, Video, System tabs) and the Emulation menu's switches
  (`SaveTitleSwitch` in `hostMenu.cpp`) all save through `HostInputConfigPath()` into that one file.
- Some keys were already per title *inside* that file: `RenderScale.<TITLE_ID>`, `RayTracing.<TITLE_ID>`,
  `MangoHud.<TITLE_ID>`. The bindings, `DefaultKeys`, `Pad:*=none`, `SystemLanguage` and `Fullscreen` were shared.
- The window mode: `--fullscreen` (play-pkg.sh adds it for the second title), or `Fullscreen=on|off` in the file.
  F11, the menu's Fullscreen item and the Video tab's checkbox switch it live; only the Video tab's Save kept it,
  and then for every title. Nothing remembered an F11.

The change (`apply0435.py` applies it to a copy of the tree; `title_settings.hpp` becomes `src/bc5/title_settings.hpp`):

- Per-title store `<menu dir>/titles/<TITLE_ID>/` (`$KYTY_BC5_MENU_DIR/titles`, else `<dir of the shared file>/menu/titles`;
  both are `~/bc5-work/menu/titles` on the box):
  - `input.cfg`: the file this title reads and every Save writes. Created on the title's first start as a byte copy
    of the shared `input.cfg` (old keys, including other titles' `RenderScale.*` lines and an old `JobArenaFix.*` line,
    parse as before). After that the shared file no longer affects the title.
  - `window`: `fullscreen` or `windowed`, written by the window thread each time the mode really changes
    (`WindowContext::ProcessEvent` after a successful `SDL_SetWindowFullscreen`; no write when unchanged).
- Start order: `Fullscreen=` from the title's file, then the `window` file (it wins), then `--fullscreen` only when
  neither says anything (`FullscreenBeforeWindow` in `window.cpp`; `WindowRestoreFullscreen` marks the pending mode as
  remembered). So the second title still starts fullscreen until he switches it, and play-pkg.sh stays as it is.
- `HostInputStatements()` writes the live mode into `Fullscreen=` for a title with a store, so a later Save or Apply
  of the Pad tab no longer turns an F11 back.
- A title never saves into the shared file (top's condition, 2026-11-19): `HostInputConfigPath()` returns a separate
  save path, the title's own file. A title whose store cannot be made reads the shared file and its Save is off.
- No title id (the empty menu window, `UNKNOWN`) or `KYTY_BC5_TITLE_SETTINGS=0`: the shared file exactly as before,
  read and saved, no window file. A missing shared file still ends the emulator as before (exit 65).
- Switch: `KYTY_BC5_TITLE_SETTINGS`, a `kSoft` row (default `1`, in both builds); `=0` gives the old behaviour with no
  build. The log line `Title settings (exp 0435): <id>: <seeded …|title file …|…>` says which file a run uses.

Box facts read on 2026-11-19 (top's read-only GO, no emulator running):

- `~/bc5-work/input.cfg` (md5 `8115a7ff`) has no `Fullscreen=` line, so the second title's `--fullscreen` from
  `play-pkg.sh` (`47426d8e`, line 42) stays its first-run default. It holds `RenderScale.UNKNOWN=1.70`, written by the
  empty menu window (no title id), which keeps using the shared file.
- Init order in `~/src/KytyPlus` (`f266548` + patch): `emulator.cpp` loads `param.sfo` at start (line 138);
  `HostInputInit()` builds the input map inside `WindowCreate` (`window.cpp:990`), before the fullscreen flag is computed.
  So the title id is known when the store is resolved, and a remembered mode is applied before the window exists (no
  switch after opening, no write at start).
- Launchers `play-any.sh` `fc7a1395`, `play-astro.sh` `e943bd8f`, `lean-session.sh` `1f1be812`: unchanged by this
  experiment. `play-any.sh` exports `KYTY_BC5_MENU_DIR=~/bc5-work/menu`.

Files touched in the tree: `src/graphics/presentation/window/hostInput.cpp`, `…/window/hostInput.h`,
`src/graphics/presentation/window.h`, `…/window/window.cpp`, `src/bc5/switch_defaults.hpp`, new
`src/bc5/title_settings.hpp`. Separate from exp 0434's hunks.

Tests:

- `test0435.cpp` (laptop, clang++ 20 from VS: `clang++ -std=c++20 -Wall -Wextra -Werror -I. test0435.cpp`): ids,
  root, seeding byte for byte, no overwrite of a title's file, a second title's own copy, fallbacks (no id, no
  shared file, bad id, blocked root), window file read/write/unchanged/hand edit. PASS.
- `apply0435.py` on copies of the box's real files (pinned in `units.sha256`): every anchor once, CRLF of
  `window.cpp` kept, a second run refuses. PASS. The result is `0435-title-settings.diff` (byte-exact, `-text`).
- `experiments/0419-switch-cleanup/test0419defs.cpp` against the patched `switch_defaults.hpp`: the same three FAIL
  lines as against the unpatched one (stale row counts in that test), no new one.
- Private build: `box0435.sh claim|build|release` (`build0435.py` is `build0433.py`): copies of the five files and
  `main.cpp`, the change applied, the three changed units (`hostInput.cpp`, `window.cpp`, `main.cpp`) compiled with the
  shared builds' own commands and linked with their other objects; output `~/bc5-work/exp0435/{normal,lean}/kyty_emulator`.

## Result

Private build, 2026-11-19 14:32 (top's GO; `box0435.sh claim|build|release`, lock held only for the build):

- The tree pin matched (`raw/units.txt`), `apply0435.py` applied to the copies (`raw/apply.out`).
- Normal and lean: build rc 0, 0 errors, 3 warnings each, all the existing `-Wdeprecated-declarations` of
  `src/common/stringUtils.h:321` (`wstring_convert`), once per rebuilt unit; none from this change.
- Private normal `14a70b84`, lean `763359fb` (`~/bc5-work/exp0435/{normal,lean}/kyty_emulator`); both carry
  `KYTY_BC5_TITLE_SETTINGS` and the `Title settings (exp 0435)` line.
- Shared normal `efc28a30` and lean `d8b75137` unchanged. `snap0435.sh` before and after (`raw/before.txt`,
  `raw/after.txt`): identical — the tree (HEAD, status, every file under `src/`), both build directories (binaries, and
  every file's size and mtime), the patch in `~/src/bc5`, the launchers, `bc5-run.env`, `input.cfg`, the four shortcuts.

The combined test binary with exp 0434 is built by 0434 (its fix plus `apply0435.py`, md5 `54f4b48f`; no file
overlap).

His check, 2026-11-19, on exp 0434's combined test binary (0434's fix plus this change), through a test shortcut
arranged by the top session: "Wszystko ok, możesz wdrożyć i wypchnic i merge". Afterwards on the box (read by top):
`~/bc5-work/menu/titles/PPSA03671/input.cfg`, and `PPSA21564/` with `input.cfg` and `window`, exist; the shared
`~/bc5-work/input.cfg` is unchanged.

## Verdict

Done. Each title keeps its own settings in `~/bc5-work/menu/titles/<TITLE_ID>/input.cfg` (seeded once from the shared
file) and its last window mode in `…/window`, and gets both back on its next start; the shared `input.cfg` is no
longer written by a title, and the empty menu window keeps using it. No launcher or shortcut changed. The maintainer
accepted it and asked for deployment; exp 0434 puts both changes into the shared builds in one swap (top's decision),
and the top session merges this branch to main after that swap.

Switch disposition (LESSONS R52): `KYTY_BC5_TITLE_SETTINGS` — the shared swap is exp 0434's; whatever it bakes in
(the `kSoft` row with `=0` for the old behaviour, or no switch) is recorded there and in the HANDOFF row.
