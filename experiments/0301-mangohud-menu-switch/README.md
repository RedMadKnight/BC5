# 0301 — MangoHud in every build: loaded hidden, shown and hidden from Emulation › MangoHud

**Question.** The maintainer asked (2026-10-25, through the top session): "MangoHud powinien być wbudowany w każdą
binarkę, domyślnie wyłączony z możliwością włączenia w dowolnym momencie z menu. Usuń wtedy osobne utrzymanie binarki
i skrót." In English: MangoHud's overlay should be in every emulator build (normal and lean), off by default, and
switchable at any moment from the emulator's menu. Once that works, the separate MangoHud variant and its desktop
shortcut go. Can the emulator load MangoHud itself and drive it at runtime? Does a hidden MangoHud cost frame time?

**Known before this experiment.**
- Today's wiring (read on the box 2026-10-25 11:10–11:15; no separate binary exists):
  - The desktop shortcut `~/Pulpit/BC5 emulator (MangoHud).desktop` (md5 3a5fd58d) runs
    `distrobox enter ubuntu -- env BC5_MANGOHUD=1 ~/bc5-work/play-any.sh`.
  - `play-pkg.sh` (fde58cda, lines 142–148) and `play-astro.sh` (adfe3439, lines 57–63) turn `BC5_MANGOHUD=1` into
    `MANGOHUD=1 MANGOHUD_CONFIGFILE=~/bc5-work/mangohud-bc5.conf KYTY_BC5_OSD_FPS=1`. `play-pkg-log.sh`,
    `play-pkg-quiet.sh` and `play-any.sh` carry no MangoHud line; `play-any.sh` passes the variable through.
  - The layout is `~/bc5-work/mangohud-bc5.conf` (2289c47d), the box's copy of `tools/scripts/mangohud-bc5.conf`
    (2026-10-21). It leaves out MangoHud's fps and frame time, since the window presents at every vblank, and the
    GPU clock, which gpu_metrics does not report reliably on this board.
  - `KYTY_BC5_OSD_FPS=1` draws the title's own frame rate top right (`settingsOverlay.cpp`, read once at start).
- MangoHud in the `ubuntu` container: package `mangohud 0.8.2~rc2-1` (the library's version string is
  `MangoHud v0.8.1`, the rc's `meson.build`). Its Vulkan layer `VK_LAYER_MANGOHUD_overlay_x86_64` is an implicit layer
  (`/usr/share/vulkan/implicit_layer.d/MangoHud.x86_64.json`) enabled by `MANGOHUD=1` (`enable_environment`). The
  emulator creates one Vulkan instance (`src/graphics/presentation/window/vulkanWindow.cpp`).
- MangoHud's runtime control, from its source at tag `v0.8.2-rc2` (github.com/flightlessmango/MangoHud, 8c940d5):
  - `src/overlay_params.cpp` `parse_overlay_config`: with `MANGOHUD_CONFIG` set and no `read_cfg`, no config file is
    read, so the variable is the whole configuration. It is parsed at `vkCreateInstance` (`src/vulkan.cpp`).
    `parse_control`: `control=<name>` listens on an abstract unix socket of that name (`%p` becomes the pid;
    `src/mesa/util/os_socket.c` `os_socket_listen_abstract`: a leading NUL, length `offsetof(sun_path) + strlen + 1`).
  - `src/vulkan.cpp` `snapshot_swapchain_frame`, run in every `vkQueuePresentKHR`, accepts one client and reads its
    commands. `src/control.cpp` `parse_command`: `:hud;` toggles `no_display`. It is toggle-only, and a new client is
    greeted with three version lines (`control_send_connection_string`, sent with `MSG_NOSIGNAL`).
  - Hidden (`no_display`): `compute_swapchain_display` and `render_swapchain_display` return before any ImGui or
    Vulkan work; `src/overlay.cpp` `update_hud_info` skips the statistics unless logging runs, so the CPU/GPU sampling
    thread is never started; `src/amdgpu.cpp` `metrics_polling_thread` sleeps 100 ms per loop instead of reading
    gpu_metrics. Left per present: a time check, the 100-ms-throttled key check, and a non-blocking `accept`.
  - The same `parse_command` and the same hidden-state checks are in v0.7.2 through v0.8.4.
  - `mangohudctl` (installed) is not the layer's control: `src/app/control.c` sends to mangoapp's SysV message queue
    (`ftok("mangoapp", 65)`).
- The model for a per-title saved switch: Emulation › Ray tracing (exp 0273). It saves `RayTracing.<TITLE_ID>=on|off`
  into the input configuration, and `hostInput.cpp` parses, keeps and applies it.

**Setup.**
- `patch_0301.diff` (four files of the shared tree, the md5s of patch 0001 on main 36a68b0, the shared builds
  normal e62a97c6 and lean 753889c9: `hostMenu.cpp` afb5ae7e, `hostMenu.h` 1fc6fe2a, `settingsOverlay.cpp` e302a5f7,
  `window/hostInput.cpp` 8a578f90; +180 −16 lines):
  - `hostMenu.cpp`: a constructor (before `main`, so before the loader and the layer read the environment) sets
    `MANGOHUD=1` (unless the caller set `MANGOHUD`) and
    `MANGOHUD_CONFIG=no_display,control=bc5-mangohud-<pid>,<the layout of mangohud-bc5.conf>`.
    - `KYTY_BC5_MANGOHUD=0` leaves the environment alone, so the layer stays out.
    - `KYTY_BC5_MANGOHUD=1` starts the switch on.
    - A caller's own `MANGOHUD_CONFIG` or `MANGOHUD_CONFIGFILE` is respected. MangoHud then loads with it, and the
      switch drives only the counter.
  - `hostMenu.cpp`: Emulation › **MangoHud**, a checked item after Ray tracing, enabled when a title runs. It sets the
    switch and saves `MangoHud.<TITLE_ID>=on|off` through the Ray-tracing item's save code, now one helper
    (`SaveTitleSwitch`, the same stderr lines).
  - `HostMenuMangoHudSync()` runs on the presenter thread just before a present. On a change it connects once to
    `@bc5-mangohud-<pid>` (non-blocking, kept open), drops MangoHud's greeting, and sends `:hud;`; MangoHud reads it
    in that same present. A refused connection marks MangoHud as not loaded, says so once on stderr and in the item's
    tooltip, and the switch then shows the counter only.
  - `settingsOverlay.cpp`: the title's frame-rate counter is on with `KYTY_BC5_OSD_FPS=1` or with the switch. The
    overlay pass also runs while a change waits to be sent, and calls the sync first thing.
  - `hostInput.cpp`: `MangoHud.<TITLE_ID>=on|off` is parsed like `RayTracing.<TITLE_ID>`, another title's line is kept,
    it is written back by `Statements()`, and it is applied at the first load and on Apply. The file's value beats
    `KYTY_BC5_MANGOHUD=1`.
- `launchers0301.py` (offline, against the box's play-pkg.sh fde58cda and play-astro.sh adfe3439): the proposal
  `launchers_0301.diff` drops the `BC5_MANGOHUD=1` block from both, and writes `play-pkg-0301.sh`. That is the changed
  play-pkg.sh in exp 0299's pattern: its own log, working directory (`exp0301/wd` with its own `_SaveData` and
  save-data slots), input configuration and input recording.
- Builds: `run0301.sh prep` patches the four files into `~/bc5-work/exp0301/tree/src` after an md5 check, and
  `run0301.sh build` links `exp0301/normal/kyty_emulator` and `exp0301/lean/kyty_emulator` from the shared builds'
  other objects (`build0301.py`, exp 0273's build0273.py with the header ahead on the include path). Both shared
  builds are only read.
- Runs (`run0301.sh run`), on the top session's GO, attended, `stream0301.sh` streaming the kernel log to the laptop:
  - The second title from a private copy of exp 0196's `saves-before-152617`, on the S6N route (exp 0203's
    `o2-continue.cmd`: Continue at 85 s, then from t ≈ 150 s the outpost's "Parry" prompt, a fixed scene; exp 0264).
  - Ray tracing off (`KYTY_BC5_RT=0`), with the input configuration from a copy of exp 0194's `input-0194.cfg`.
  - The maintainer's saves, `input.cfg` and `route-record.txt` are never used. Their checksum is printed before and
    after each run.
- The live switch (T1, normal build): at t ≈ 150 s the menu is driven from ssh (exp 0164's `drive0164.sh` over
  `ydotool`: F1, then clicks on Emulation and MangoHud) to on, off and on, with a screenshot after each. The
  screenshots stay on the box, never in the repo.
  - Expected: the stderr lines `host menu: MangoHud on (saved to …)`, `… control socket @bc5-mangohud-<pid> connected`,
    `… MangoHud shown` / `hidden`.
  - Expected: `MangoHud.PPSA03671=on` in the private input configuration.
- The saved switch (T2, lean build): a start with that configuration (`KEEPCFG=1`) should show the overlay without
  the menu.
- The A/B (normal build, 300 s each, interleaved A1 B1 A2 B2): A = `KYTY_BC5_MANGOHUD=0` (no layer), B = the default
  (the layer loaded, hidden). Frame statistics from exp 0211's `frameprof.py` over t 100–300 s of each journal's
  frame-profile lines. Per run: VmRSS/VmHWM, threads, `libMangoHud.so` mapped, the socket, GTT in use and CPU time at
  fixed seconds (`samples.txt`).

**Result.** (pending: the box queue has 0299 and 0300 first)

**Verdict.** (pending)
