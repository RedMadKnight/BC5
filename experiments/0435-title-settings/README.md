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
- No title id (the empty menu window, `UNKNOWN`), no shared file, a bad id, or any file error: the shared file exactly
  as before, no window file. A missing shared file still ends the emulator as before (exit 65).
- Switch: `KYTY_BC5_TITLE_SETTINGS`, a `kSoft` row (default `1`, in both builds); `=0` gives the old behaviour with no
  build. The log line `Title settings (exp 0435): <id>: <seeded …|title file …|…>` says which file a run uses.

Files touched in the tree: `src/graphics/presentation/window/hostInput.cpp`, `…/window/hostInput.h`,
`src/graphics/presentation/window.h`, `…/window/window.cpp`, `src/bc5/switch_defaults.hpp`, new
`src/bc5/title_settings.hpp`. Separate from exp 0434's hunks.

Tests:

- `test0435.cpp` (laptop, clang++ 20 from VS: `clang++ -std=c++20 -Wall -Wextra -Werror -I. test0435.cpp`): ids,
  root, seeding byte for byte, no overwrite of a title's file, a second title's own copy, fallbacks (no id, no
  shared file, bad id, blocked root), window file read/write/unchanged/hand edit. PASS.
- `apply0435.py` on stand-ins built from the patch's own hunks: every anchor once, CRLF of `window.cpp` kept,
  a second run refuses. PASS.

## Result

(pending: private build, his check through a test shortcut)

## Verdict

(pending)
