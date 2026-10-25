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
- The live switch (T1, normal build): at t ≈ 150 s the menu is driven from ssh to on, off and on, with a screenshot
  after each. `drive0301.sh`, run on the laptop, calls exp 0164's `drive0164.sh` over `ydotool`: F1, then clicks on
  Emulation and MangoHud. It checks the box's lock line first, and ydotoold runs only for T1. The screenshots stay on
  the box, never in the repo.
  - Expected: the stderr lines `host menu: MangoHud on (saved to …)`, `… control socket @bc5-mangohud-<pid> connected`,
    `… MangoHud shown` / `hidden`.
  - Expected: `MangoHud.PPSA03671=on` in the private input configuration.
- The saved switch (T2, lean build): a start with that configuration (`KEEPCFG=1`) should show the overlay without
  the menu.
- The A/B (normal build, 300 s each, interleaved A1 B1 A2 B2): A = `KYTY_BC5_MANGOHUD=0` (no layer), B = the default
  (the layer loaded, hidden). Frame statistics from exp 0211's `frameprof.py` over t 100–300 s of each journal's
  frame-profile lines. Per run: VmRSS/VmHWM, threads, `libMangoHud.so` mapped, the socket, GTT in use and CPU time at
  fixed seconds (`samples.txt`).

**Result.** Box work 2026-10-25, each step on the top session's GO.
- Build: 11:41:46–11:42:41, on a fresh boot after exp 0300's machine-down.
- Runs: 11:43–12:15, kernel 7.2.9-ogc3.1, boot 664515e3.
- Raw: `raw/r-<tag>/` (start, samples, end, menu lines, input configuration before and after, dmesg, frame-profile
  lines), `raw/frame-stats.txt`, `raw/kernel-stream.txt`, `raw/journal-stream.txt`, `raw/raw/` (build inputs and
  outputs, patched md5s), `raw/launch/launchers_0301.diff`. The screenshots stay on the box in
  `~/bc5-work/exp0301/shots/`.
- **Builds.** Both link cleanly:
  - `exp0301/normal/kyty_emulator` ad7ba9f1 (166,597,640 bytes) and `exp0301/lean/kyty_emulator` 5366f3ee
    (165,359,144 bytes). Both carry the three new strings.
  - One warning each, not from the diff: KytyPlus's own `stringUtils.h` `wstring_convert` deprecation, reached
    through `hostInput.cpp`'s includes.
  - The patched files match the offline tree (cb35096f, 4b150329, 813dd1c9, 47f83afb). The shared builds stayed
    e62a97c6 / 753889c9.
- **Every run passed.** No amdgpu kernel line: dmesg and the laptop stream hold only IPv6 MLD notices and T1's
  ydotoold input device. No TIMEOUT, no crash line. The live saves read 8289704a9338a118 before and after every run.
- **T1, the live switch (normal build, 420 s).**
  - From t 30 s with the switch off: `libMangoHud.so` is mapped, `@bc5-mangohud-<pid>` listens in `/proc/net/unix`,
    and one MangoHud thread runs (`mangohud-amdgpu`).
  - At t ≈ 146 s, `drive0301.sh` pressed F1, clicked Emulation (the dropdown lists the new **MangoHud** item,
    unchecked) and clicked MangoHud, then pressed F1 again.
  - The overlay appeared top-left with the BC5 layout: CPU and GPU load, temperatures, power, VRAM, RAM, the clock.
    The title's own counter appeared top-right ("game 42.0 fps 23.8 ms").
  - The log, in order: `host menu: MangoHud on (saved to …/exp0301/input-0301.cfg)`,
    `host menu: MangoHud control socket @bc5-mangohud-5299 connected`, `host menu: MangoHud shown`.
  - Off again from the menu (item checked): `MangoHud off (saved …)`, `MangoHud hidden`, and both overlays gone.
    On again: `MangoHud on`, `shown`.
  - After that, MangoHud's sampling thread (`mangohud-hwinfo`) ran too, and the socket had our client.
    `input-after.cfg` ends with `MangoHud.PPSA03671=on`.
- **T2, the saved switch (lean build, 200 s, `KEEPCFG=1`).** With that line in the configuration, MangoHud was shown
  without any menu use: at t 30 s the sampling thread and the socket connection already exist, and a screenshot at
  t ≈ 155 s shows both overlays. `MangoHud.PPSA03671=on` was applied by the lean build's input loader.
- **The A/B: a hidden MangoHud costs nothing measurable.** From `raw/frame-stats.txt` (exp 0211's `frameprof.py`,
  the journal's frame-profile lines) and `samples.txt`:

  | Run | Arm | t 100–300: flips/s, 20-s median, GPU ms per frame median / p90, gaps > 0.4 s | t 150–300: flips/s | RSS at t 30 s | CPU time over 300 s | MemAvailable / GTT at t 250 s |
  |---|---|---|---|---|---|---|
  | A1 | no layer | 40.9, 42.2, 12.7 / 14.6, 1 | 41.4 | 2,197 MiB | 1,248.3 s | 596 / 12,103 MiB |
  | B1 | hidden | 42.0, 43.1, 14.0 / 15.8, 0 | 42.5 | 2,202 MiB | 1,253.6 s | 575 / 12,131 MiB |
  | A2 | no layer | 41.6, 42.9, 13.7 / 15.5, 0 | 42.5 | 2,192 MiB | 1,253.8 s | 631 / 12,124 MiB |
  | B2 | hidden | 41.3, 42.2, 13.7 / 15.6, 0 | 41.8 | 2,196 MiB | 1,248.2 s | 636 / 12,105 MiB |

  - Means over t 100–300: A 41.25 and B 41.65 flips/s. The spread inside each arm (0.7 flips/s, 1.0 ms of GPU
    median) is as large as the difference between them, and the CPU time is the same.
  - The layer adds one thread, and at most about 5 MiB of RSS at t 30 s (B 2,202 / 2,196 against A 2,197 /
    2,192 MiB). That is within run-to-run noise later in the run.
  - A1's one long gap (2.8 s, ending at t 161.9 s) is a hold-tail give-up after 2,748 ms (`raw/journal-stream.txt`). It is
    the host's existing behaviour and falls in the arm without MangoHud.
  - Not an A/B, for information only: in T1 with MangoHud shown (t 290–415, menu closed, no screenshots) the title
    ran 45.1 flips/s with no gap over 0.1 s. A visible overlay did not slow it below the A/B's level either.
- **Seen on the way.**
  - With the menu open, MangoHud's box (top-left) is drawn over the left part of the Emulation dropdown. The layer
    draws last, at the present. The MangoHud item itself stays readable and clickable (T1).
  - Every start now logs MangoHud's `XOpenDisplay failed to open display ':0'` once: its X11 key handling, which never
    reached it from the container. It is harmless, and it was also printed before with `BC5_MANGOHUD=1`.

**Verdict.**
- MangoHud can be part of every build. Both builds load it themselves, hidden. Emulation › MangoHud shows and hides
  it together with the title's frame-rate counter at the next present. The choice is saved per title as
  `MangoHud.<TITLE_ID>=on|off`, and a saved "on" shows it from the start.
- The runtime path is MangoHud's own control socket (`control=`, `:hud;`). `mangohudctl` drives mangoapp, not the
  layer, and MangoHud's hotkeys do not reach it from the container.
- Hidden, it costs no frame rate, no GPU time, no CPU time and no measurable memory on the second title's route with
  ray tracing off (four interleaved 300-s runs). Off by default is therefore free.
- This makes the separate shortcut and the launchers' `BC5_MANGOHUD=1` path redundant. The integration proposal:
  - `patch_0301.diff` into both shared builds.
  - `launchers_0301.diff` for play-pkg.sh and play-astro.sh.
  - Move `~/Pulpit/BC5 emulator (MangoHud).desktop` and `~/bc5-work/mangohud-bc5.conf` to a backup.
  - Drop `tools/scripts/mangohud-bc5.conf` from the repo, since the layout now lives in `hostMenu.cpp`.
  - This needs the maintainer's yes, and the top session integrates it (D19).
- Open, the maintainer's call: whether MangoHud should move off the top-left corner (e.g. `position=bottom-left`) so
  that it does not cover the menu's dropdown or the title's own health bar.

**Addendum (2026-10-25, after the integration, F367).**
- The maintainer kept top-left. The top session integrated the switch into both shared builds (normal 226bcb82, lean
  71ef2194) and the launchers, and moved the shortcut and `mangohud-bc5.conf` to `~/bc5-work/exp0301/integration/`.
- **A leftover of T1.** T1's launcher never exited. The top session found `play-pkg-0301.sh` (pid 5144) and its
  `bc5-mount` (744 MB) still alive at 12:47, holding `~/bc5-data/mnt/pkg-play` through the runs of 0300, 0302 and
  0303, and unmounted it with `fusermount3` inside the distrobox. Then everything exited.
- What is certain, from the launcher's code (`play-pkg-0301.sh` lines 152–161, the same as `play-pkg.sh`):
  - A launcher starts its own `bc5-mount` only if the mount point is free, and its EXIT trap runs
    `fusermount3 -u "$M" 2>/dev/null; wait "$MP"`.
  - T1 was the only run that mounted: the box was fresh. T2, A1, B1, A2 and B2 found T1's mount alive, used it, and
    their launchers exited at once.
  - So T1's `fusermount3 -u` failed, its error went to `/dev/null`, and `wait` then waits forever for a `bc5-mount`
    that is still mounted. The A/B therefore ran on T1's mount process; that is the same program, and the arms are
    unaffected.
- Why it failed is not shown. Its stderr was discarded, and the log that could say was overwritten by the next run.
  TODO(verify): a hypothesis only. The kill (SIGTERM, then SIGKILL after 4 s) left the mount busy for a moment
  after the emulator had been reaped, e.g. FUSE release requests still queued to a `bc5-mount` under memory
  pressure, so the immediate unmount lost a race. Nothing points at MangoHud or ydotool, but T1 is a single case.
- The shared launchers have the same EXIT trap. A launcher could hang the same way after any stop whose unmount
  fails.
  - A suggestion for the top session, not done here: retry `fusermount3 -u` a few times, fall back to
    `fusermount3 -u -z`, log the failure instead of discarding it, and give up the `wait` after a timeout.
  - For future private runs: check at each run's end that the launcher and its mount are gone, and give the
    private launcher its own mount log. `play-pkg-0301.sh` still wrote the shared `~/bc5-work/play-pkg-mount.log`.
