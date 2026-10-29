# 0372 — The DualSense's haptics after a replug: back to the pad, never to the speakers

**Date.** 2026-10-28/29. **Branch.** `exp/0372-pad-haptics-replug`. **Box.**
- The design read sources there with the top session's GO: md5s, `play-pkg.sh`, the WirePlumber scripts and man pages.
- The top session then built the private binary (00:18) and ran two software replug runs under the lock (01:26–01:45,
  S6N RT on).
- The maintainer's physical test is to come.

**Question.** At 23:32:44 on 2026-10-28 the maintainer unplugged the USB DualSense during the second title (shared
normal build) and plugged it back at 23:32:49; afterwards he heard the haptics from the speakers. Of the title's two
pad streams (both with `target.object = alsa_output.usb-Sony_Interactive_Entertainment_DualSense_Wireless_Controller-00.Direct__Direct__sink`,
neither with `node.dont-reconnect` or `node.dont-fallback`), one was closed and reopened on the returning pad sink;
the other (object.serial 163) stayed alive, linked by WirePlumber to the default sink (the stereo ThinkPad dock, FL/FR)
and never moved back, while the host's trace kept saying `port 2 type 10 2 ch 48000 Hz (pad): … device playing`: F93's
reopen, which waits for SDL to report the device STOPPED, never ran for it. Why does SDL leave that device "playing",
and how does the host make sure a pad-routed port never plays on a sink other than the controller's, with
F329/F330's DualShock 4 behaviour kept?

## Setup

### Why the second stream survived (sources read on the box)

- **SDL 2.33.0** (KytyPlus f266548's `3rdparty/SDL2`, submodule 4b69833; its PipeWire backend runs on the container's
  libpipewire 1.6.2, exp 0181):
  - `src/audio/SDL_audio.c:510-551`, `SDL_RemoveAudioDevice`: for a removed node it marks the list entry, then calls
    `SDL_OpenedAudioDeviceDisconnected` for the **first** open device with that handle and `break`s (522–529). The
    title's pad-speaker port (type 4) and vibration port (type 10) each hold an SDL device on the same DualSense node,
    so only the one opened first becomes STOPPED (and gets an `SDL_AUDIODEVICEREMOVED`, 467–494).
  - `src/audio/pipewire/SDL_pipewire.c`: the backend never reports a lost stream by itself
    (`stream_state_changed_callback`, 1129–1140, only wakes the open). A stream on a named device gets
    `target.object` = the sink's node.name (1259–1272), the flags `AUTOCONNECT | MAP_BUFFERS` (1160) and media, name,
    latency, rate and always-process properties (1243–1251): no `node.dont-reconnect`, no `node.dont-fallback`.
    Removals come from the registry (`registry_event_remove_callback` → `io_list_remove` → `SDL_RemoveAudioDevice`,
    774–778, 323–341); a returning node is added through `io_list_check_add` → `SDL_AddAudioDevice` (298–321).
  - So the second device stays "playing" (the trace's `device playing`), F93's STOPPED check never fires, and its
    PipeWire stream lives on.
- **WirePlumber 0.5.17** (`/usr/share/wireplumber/scripts/linking/`, `libwireplumber-0.5.so.0.517.0`) with
  **PipeWire 1.6.9** on the host (`libpipewire-0.3.so.0.1609.0`, `pipewire-props(7)`):
  - Without `node.dont-fallback`, `find-defined-target.lua:116` does not stop a stream whose `target.object` is gone;
    without `node.dont-reconnect`, `prepare-link.lua:71-76` lets it take a new target, the default sink: what 23:32:44
    showed.
  - With `node.dont-fallback` (and `node.linger` unset) a stream whose defined target is not found is sent an error
    and destroyed (`find-defined-target.lua:116-123`); with `node.dont-reconnect` a stream that was already handled is
    never linked to a new target (`prepare-link.lua:63-76`). `pipewire-props(7)` of 1.6.9 (lines 623–636 of the page)
    describes the same.
  - Not explained by the scripts read: why the surviving stream was not moved back at 23:32:49
    (`find-defined-target.lua:82-93` matches a `target.object` by node.name). The fix does not depend on it.
- **Before exp 0181** SDL used its PulseAudio backend, which opens a named device with `PA_STREAM_DONT_MOVE`
  (`SDL_pulseaudio.c:695-699`); pipewire-pulse turns that into `PW_STREAM_FLAG_DONT_RECONNECT` (PipeWire 1.6.9
  `src/modules/module-protocol-pulse/pulse-server.c`, `do_create_playback_stream`) and libpipewire into
  `node.dont-reconnect = true` (`pw_stream_connect`, 1.6.2 `src/pipewire/stream.c`). The one-device stop was the same
  (`SDL_pulseaudio.c:851` calls `SDL_RemoveAudioDevice` too), but the survivor could not be moved: silent rather than
  on the speakers. F94 (2026-10-09) recorded that the pad-speaker port reopened five times and the haptic port never
  did.

### The fix

Two host files: `src/libs/audio.cpp` (changed) and `src/bc5/pad_audio_route.hpp` (new, the same file as
`backend/include/bc5/pad_audio_route.hpp`, Catch2 `[pad_audio_route]` in `backend/tests/pad_audio_route_test.cpp`).

1. **Detection: SDL's audio device events, counted by an event watch.** `SDL_PushEvent` hands every event to the
   event watches on the pushing thread before it is queued (`src/events/SDL_events.c:1156-1176`). For the PipeWire
   backend that is SDL's hotplug thread, which nothing of ours waits on. `Bc5AudioDeviceWatch` (registered once after
   `SDL_InitSubSystem(SDL_INIT_AUDIO)`, which implies SDL's events, `src/SDL.c:289-296`) only increments one of two
   atomics: output-device removals and additions. The window's `SDL_WaitEvent` loop (`window.cpp` `WindowContext::Run`)
   still gets the events and ignores them, as before. Why not the once-a-second check of the device list: a replug
   that falls between two looks leaves the name listed while the old stream is already on another sink, and only the
   events show it. Why not the window thread: its loop would have to pass the events on, and it sleeps in
   `SDL_WaitEvent`. The 1-s look stays as a backstop for a missed event.
2. **Per port, on the thread that writes it** (`Audio::PadRouteStep`, first in `QueueSdlAudio` for every port that
   belongs on the controller: a pad-speaker port unless `KYTY_BC5_PAD_SPEAKER=main`, a vibration port, with
   `KYTY_BC5_NO_PAD_AUDIO` unset). The decision is `bc5::pad_audio_route::decide` in the header:
   - a stream on the controller is closed at **any** output-device removal since the port last looked, when SDL
     stopped it (F93's case), or when the 1-s look no longer finds the controller. It is reopened at once if the
     controller is listed (a replug faster than the port's next write, or another sink removed: one close and open);
     SDL cannot say which node went, and a stream whose node went may already be on another sink;
   - while the controller is away the frames are dropped: no device, nothing on any sink. The vibration port's go to
     F214's rumble fallback, as with F93. The port looks at every device event and once a second;
   - when the controller is back, every pad port is reopened at its own next write with the spec it had there (F93's
     reopen; one SDL device per port at a time). The new stream's `SDLAudioP` thread gets nice −15 like the first
     opens' (exp 0180/0181; F93's reopen left it at 0);
   - a port opened before the controller came (no pad at the start, or a DualShock 4 swapped for a DualSense) is
     moved onto it when it is listed. Without a DualSense nothing changes: the DualShock 4's 2-channel sink is not the
     controller's device (F347), its pad-speaker port stays on the default sink, non-blocking (F329/F330), and its
     vibration port has no device and drives the rumble worker; such ports look only at device events, never
     periodically.
   - Thread safety: the watch writes only the two atomics; the port's SDL device is opened and closed only by the
     thread that writes the port, as with F93; the port's device fields change under `m_mutex`, under which
     `AudioOutHasDevice` and `AudioOutQueuedFrames` read them, and SDL's close runs after the field is cleared.
3. **PipeWire properties for the pad streams only.** Every `SDL_OpenAudioDevice` of `audio.cpp` now goes through
   `Bc5OpenSdlAudioDevice`, one at a time under a lock. For a stream on the controller, with SDL's PipeWire driver, it
   sets `PIPEWIRE_PROPS` to the host's default (exp 0181: `{ channelmix.normalize = true }`) plus
   `node.dont-reconnect = true node.dont-fallback = true` for the open and restores it after. libpipewire reads
   `PIPEWIRE_PROPS` in `pw_stream_connect` (1.6.2 `src/pipewire/stream.c`), which SDL calls inside the open
   (`SDL_pipewire.c:1281`), so the main mix's stream never sees the two keys. The variable exists from the first open
   on (exp 0181), so each swap replaces one pointer in the environment and frees nothing (glibc 2.42
   `stdlib/setenv.c`, `__add_to_environ`: an existing slot is overwritten with a release store, strings stay in its
   `known_values` tree): safe against `getenv` on other threads. A `PIPEWIRE_PROPS` set by the user is left alone (no
   keys added). `node.dont-fallback` matters most: with `node.dont-reconnect` alone, a reopen that reaches WirePlumber
   before the returning sink is linkable would be linked to the default sink and then kept there
   (`prepare-link.lua:63-67`); with dont-fallback that open fails and the port retries a second later.
   `KYTY_BC5_PAD_PW_PROPS=0` opens pad streams without the keys (the A/B arm).
4. **Unchanged:** the main mix and its stream; the 0182 pause; `KYTY_BC5_NO_PAD_AUDIO`; `KYTY_BC5_PAD_SPEAKER`
   `main`/`off`/`main-blocking` (for ports opened without a controller); the rumble worker and fallback (F214, F330);
   the `audio trace:` and `input trace:` lines.
5. **Log lines** (stderr, so in the launcher's log; one per event, rare):
   - `AudioOut (exp 0372): the controller's ports follow SDL's audio device events` (once);
   - `AudioOut (exp 0372): t <s> s port <n> type <4|10>: opened on <device> (<Hz> Hz, <ch> ch)[; node.dont-reconnect, node.dont-fallback]`
     (the first open, and every reopen with `after <reason>`);
   - `… port <n> type <t>: its stream on the controller closed (<reason>)[; frames dropped until the controller is back]`;
   - `… port <n> type <t>: moved from the default sink on <device> …` (a controller that came after the start);
   - `… opening on <device> failed (after <reason>): <SDL error>; <k> in a row, again in 1 s` (1st, then every 60th);
   - with `KYTY_BC5_AUDIO_TRACE=1` (and `KYTY_BC5_MEASURE=1` with logging off), once a second per absent port:
     `pad route: t <s> s port <n> type <t> (pad): <k> calls dropped, no controller device`.
6. **Cost:** at a replug each pad port is closed and opened on the title's audio thread, which also writes the main
   mix (F93 did this for one port, now for both): a few to some tens of ms each, once per replug; the same once when
   another output device is removed during play. The test plan measures the main port's `held` in those seconds.

### Files (md5, first 8 hex)

| File | Original (box tree `~/src/KytyPlus`) | This experiment |
|---|---|---|
| `src/libs/audio.cpp` | fa06c494 (112,196 bytes, LF; git blob 1bd9e82 = patch 0001's post-image on main) | 06d21dba (127,469 bytes, LF) |
| `src/bc5/pad_audio_route.hpp` | — (new) | 51131854 (9,111 bytes; = `backend/include/bc5/pad_audio_route.hpp`) |
| `raw/0372.diff` | | e840ebae (664 lines: the two files against the originals, `patch -p1` in the tree) |

Box state read on 2026-10-28 ~23:40 (after the 23:36 reboot): shared normal binary 1000ad2a (16:03:45), backend
archive bb50b2e0, `play-pkg.sh` 55531ab6; the tree's `audio.cpp` (2026-10-25 23:42) predates the shared object of
2026-10-27 06:36, so the shared binary has it.

`raw/`: `0372.diff`; `build0372.sh` + `build0372.py` (exp 0359's private-build pattern: md5 pins, Catch2 first, one
unit compiled with the shared build's compdb command, relinked); `mkplay0372.pl` (the test launcher from
`play-pkg.sh`).

## Result

### The box build (2026-10-29 00:18–00:19, the top session)

Steps 1–3 of the test plan below ran as written:
- `build0372.sh` ran with rc 0.
- The backend's Catch2 tests passed on the box: 91 cases (33,675 assertions); `[pad_audio_route]` 15 cases (1,092).
- The private binary is `~/bc5-work/exp0372/kyty_emulator`, md5 **cd5048e7**. It is the shared normal objects
  (1000ad2a) with this `audio.cpp` (06d21dba), linked against the archive bb50b2e0.
- The one compiler warning is KytyPlus's own `stringUtils.h:321` (`wstring_convert` deprecated), not this change.
- The test launcher `play-pkg-0372t.sh` (acdd5492) and the desktop shortcut "BC5 emulator (test 0372)" were made by
  `raw/shortcut0372.sh`.
- The shared builds, `play-pkg.sh` (55531ab6) and `input.cfg` are unchanged.

### The software replug test (2026-10-29 01:26–01:45, the top session, no one at the box)

**The method.** Before the maintainer's physical test (A), a replug was simulated. `raw/replug0372.sh` turns the
DualSense's PipeWire card profile off (index 0) and back to "Direct" (1) with `pw-cli set-param <dev> Profile`:
- the pad's sink node is destroyed and created again, as at a USB replug, so SDL's PipeWire backend gets the same
  registry removal and addition, and with them `SDL_AUDIODEVICEREMOVED` / `ADDED`;
- the pad's HID side stays, so the rumble fallback and the joystick are not exercised;
- `set-param` passes no `save`, so WirePlumber stores nothing;
- the script puts the original profile back and unmutes the default sink at its end, on failure too (checked:
  "restored: DualSense profile 1 Direct, default sink 54 Volume: 0.95").

The title ran exp 0368's S6N route, RT on, with the private binary: `raw/s6n0372.sh`, made from `s6n0368.sh` by
`raw/mk-s6n0372.pl`, with a private working directory and save copy, and the live saves compared only. The dock (the
default sink) was muted for the runs. Reads came from `pw-dump` through `raw/streams0372.py`. Its first version
matched streams by a node property that SDL's nodes lack, so R0 and P1's 5-s-pull reads list no stream. A fixed copy
(client → `application.process.binary`) read the 30 s after that pull and everything later.

**P1: three pulls, as in test plan A** (`s6n0372.sh 530ac03cb15b0ddf P1 420 on`; `replug0372.sh P1`).

At the start, both pad ports opened on the DualSense with both keys:
- t 34.386 s: `port 1 type 4: opened on DualSense … (48000 Hz, 6 ch); node.dont-reconnect, node.dont-fallback`;
- t 34.418 s: `port 2 type 10` the same.

The vibration port (port 2) wrote all the time: `(pad) … device playing` once a second. The pad-speaker port
(port 1) was never written in this route, so it never looked at an event: its stream lives or is destroyed by
WirePlumber alone.

| pull | profile off → on (box clock) | host log | reads |
|---|---|---|---|
| 5 s | 01:29:05.62 → 01:29:10.84 | `closed (an output device was removed)` at t 171.271; `pad route: … calls dropped, no controller device` each second; `opened on DualSense … after an output device was added; node.dont-reconnect, node.dont-fallback` at t 176.503 | R1 (2 s in): only the dock sink is listed. 30 s after: main mix (serial 115) → dock; pad stream serial **723** → the DualSense sink, both keys |
| < 1 s | 01:29:46.10 → 01:29:46.55 | `closed` at t 211.708, `opened … after an output device was added` at t 212.199 | 5 s after: the pad stream is a new serial **833** → the DualSense sink, both keys; main mix unchanged |
| 30 s | 01:30:21.80 → 01:30:51.94 | `closed` at t 247.410; dropped lines until t 277; `opened …` at t 277.582 | R1 (15 s in): **one** emulator stream, the main mix on the dock, nothing else; R2 5 s after: new serial **970** → the DualSense sink, both keys |

- No pad stream was ever linked to the dock.
- No `(pad) … device playing` line appeared while the profile was off (302 such lines in the run, all while the
  controller was listed).
- In all three pulls the port reopened within ~50 ms of the sink's return (the close's t against the box clock of
  the profile change gives the offset).

**The cost.** Each reopen ran on the title's audio thread, as designed. In the second of each reopen the main port's
pacing hold fell from ~1,000 ms to 930 / 947 / 941 ms. Its SDL queue's minimum fell from 42 ms to **0 ms** (t
176.867, 212.964, 278.137), so the main mix probably has one short gap (≤ ~30 ms) per replug. The closes did not
empty it (t 171.854: the minimum 21 ms).

**The run.** `pass`: stopped at 420 s, 15,055 flips over 420.5 s = **35.8 flips/s** (the soak's mean, F494).
- 0 crash lines, 0 kernel lines (`raw/P1-kernel-stream.txt`: four IPv6 MLD lines), 0 TIMEOUT lines, no devcoredump;
- 11,330 MiB pinned;
- the live saves 530ac03cb15b0ddf before and after.

**P2: a DualSense that comes after the start, as in test plan D** (`replug0372.sh P2 late`; the profile off from
before the start).
- **At the start.** No exp 0372 open line. R0 at 171 s shows two emulator streams, both on the dock: the main mix
  (serial 1385) and the pad-speaker port on the default sink (serial 1417, no keys), as F330 designs it for no
  controller. The vibration port had no device and no `pad route:` line: a port opened without a controller looks
  only at device events.
- **The late plug (01:38:49.12).** At t 171.162 s: `port 2 type 10: opened on DualSense … after an output device was
  added; node.dont-reconnect, node.dont-fallback`. From the next second on: `(pad) … device playing`. R2 5 s later
  shows serial 1528 on the DualSense sink with both keys.
- **The port that did not move.** The pad-speaker port (never written in this route) stayed on the dock. It moves
  only at its own next write (`moved from the default sink …`), so this run cannot show that line.
- **A 5-s pull after the late plug.** `closed (an output device was removed)` at t 206.355. R1 shows only the two dock
  streams. `opened …` came at t 211.482. R2 shows serial 1639 on the DualSense sink with both keys.
- **The cost.** At the late plug the main port's hold was 883.8 ms with its queue down to 0 ms; at the reopen after
  the pull, 949.3 ms and 0 ms (one short gap each, as in P1). The close left the queue at 10 ms.
- **The run.** `pass`: 14,818 flips over 419.9 s = **35.3 flips/s**, 0 crash, kernel or TIMEOUT lines, 11,324 MiB
  pinned, the live saves unchanged.
- **Restored.** The profile was back at 1 (Direct) and the dock unmuted at 0.95. `~/.local/state/wireplumber/`
  still holds only `default-routes` and `stream-properties`: no saved profile.

**What the software test does not cover.**
- The HID side: a real replug also re-creates the joystick, and the vibration port's frames go to F214's rumble
  fallback while the pad is away.
- A pad-speaker port that is written: this route never writes port 1.
- The DualShock 4 (C).
- The sound in the room: the dock was muted. The reads show no emulator stream but the main mix linked to it.

So test plan A with the maintainer stays the deciding run; C and the HID half of D stay his.

`raw/`:
- `P1-*.txt`, `P2-*.txt`: the driver's log, the run's summary, verdict, end, frame profile, `dmesg` and devcoredump
  lists;
- `P1-audio-lines.txt.gz`, `P2-audio-lines.txt.gz`: every `AudioOut`, `pad route:`, `(pad)` and main-port trace line
  of the run's log;
- the laptop's kernel streams;
- `s6n-saves.txt`, and `play-pkg-0358.diff` (the run launcher against `play-pkg.sh`).

The play logs stay on the box (`~/bc5-work/exp0372/raw/P{1,2}-play.log`).

### On the laptop (2026-10-29 00:10–00:30)

- `backend/` configured and built with MSVC 14.51 (`cmake -G Ninja`, `/W4 /WX`, Catch2 from the earlier Windows build
  dir): `bc5_backend_tests "[pad_audio_route]"` — 15 test cases, 1092 assertions passed; the whole suite 91 cases
  passed. `pad_audio_route_test.cpp` also passes clang 22 (`clang-cl -fsyntax-only`, `-Wall -Wextra -Wpedantic
  -Wshadow -Wconversion -Wsign-conversion -Werror`, Catch2's `__COUNTER__` pedantry silenced).
- `audio.cpp`: the Audio-class part (everything before `namespace AudioOut`, which holds every change) passes
  `clang-cl -fsyntax-only -Wall -Wextra` with the real SDL 2.33.0 headers from the box, stub KytyPlus headers and the
  Linux branches compiled; the same 4 warnings as the original (constants used further down). Not compiled as a
  whole and not linked.
- `raw/0372.diff` applied with `patch -p1` to a copy of the box originals gives the committed copies byte for byte.
- `mkplay0372.pl` run on a copy of `play-pkg.sh` (55531ab6): five anchors once each, `bash -n` clean;
  `build0372.sh`: `bash -n` clean.

## Test plan for the box

Box time ~40 min: build ~5 min (CPU only, no emulator), then ~30 min with the maintainer. Box etiquette as usual:
BOX REQUEST and GO, a `pad exp 0372 | …` BOX-LOCK line during the play, the kernel log streamed to the laptop
(`ssh bc250 journalctl -k -f -n 0 -o short-precise | tee …`), the live-save checksum before and after.

**1. Copy (top session, laptop, in this branch's checkout; nothing runs on the box yet).**
```
ssh bc250 'pgrep "^kyty_emulator" && exit 1; mkdir -p ~/bc5-work/exp0372/in'
tar cf - -C experiments/0372-pad-haptics-replug . | ssh bc250 'tar xf - -C ~/bc5-work/exp0372/in'
tar cf - --exclude=kytyplus-patches --exclude=rpcsx-patches backend | ssh bc250 'tar xf - -C ~/bc5-work/exp0372/in'
```
**2. Private build.** `ssh bc250 'bash ~/bc5-work/exp0372/in/raw/build0372.sh'`: pins the shared binary 1000ad2a,
archive bb50b2e0, tree `audio.cpp` fa06c494 and the copies (06d21dba, 51131854); builds and runs the backend's
Catch2 tests (`[pad_audio_route]` must pass); puts `audio.cpp` and the header into the private tree
`~/bc5-work/exp0372/src/src/{libs,bc5}`, compiles that one unit with the shared normal build's command and relinks into
`~/bc5-work/exp0372/kyty_emulator`. Expect rc 0 and nonzero counts on its `strings:` line. Nothing shared is written.

**3. Test launcher.** `ssh bc250 'perl ~/bc5-work/exp0372/in/raw/mkplay0372.pl ~/bc5-work/play-pkg.sh ~/bc5-work/exp0372/play-pkg-0372t.sh'`
— the integrated launcher with the private binary, `KYTY_BC5_AUDIO_TRACE=1 KYTY_BC5_MEASURE=1` set explicitly, a log
and a mount log per start in `~/bc5-work/exp0372/play/`, `BC5_LEAN` cleared. The maintainer starts it on the box:
`distrobox enter ubuntu -- ~/bc5-work/exp0372/play-pkg-0372t.sh` (or a desktop shortcut made as in exp 0359). RT on.

**The reads** (top session over ssh, on the host; R0–R2 below). The emulator's streams are named `Audio Stream`
(application `SDL Application`, `SDL_pipewire.c:1178-1189`): the main mix and the two pad streams.
```
ssh bc250 'export XDG_RUNTIME_DIR=/run/user/$(id -u); wpctl status'          # the Streams section: each stream's links
ssh bc250 'export XDG_RUNTIME_DIR=/run/user/$(id -u); for id in <stream ids>; do echo "== $id"; pw-cli info $id | grep -E "target.object|media.class|object.serial"; pw-cli info $id | grep -E "node.dont-(reconnect|fallback)"; done'
```
and the log, from the laptop at the end:
`grep -E "AudioOut \(exp 0372\)|pad route:|\(pad\)|port 0 type 0 " ~/bc5-work/exp0372/play/play-*.log`.

**A. DualSense on USB, replug during play (the bug; ~12 min).** The maintainer:
1. connects the DualSense by USB (the dock's speakers on, the default sink, as at 23:32), starts the launcher, loads
   his save and plays to where the haptics are clear (walking, a fight);
2. on the top session's word (R0 done), pulls the USB cable at the pad, counts 5 s, plugs it back, and plays one
   minute;
3. pulls it again for under a second (out and in at once), plays one minute;
4. pulls it for 30 s (R1 is read meanwhile), plugs it back, plays one minute;
5. says after each: haptics back in the pad? anything from the speakers (a buzz at the pull, or haptics as sound
   later)? Then quits from the menu.

What proves it:
- **R0** (before the first pull): two pad streams with `target.object` = the DualSense sink, `media.class` =
  `Stream/Output/Audio`, `node.dont-reconnect = "true"`, `node.dont-fallback = "true"`, linked to the DualSense sink in
  `wpctl status`; the main mix on the dock without the two keys. Log at the start: `AudioOut: SDL audio driver
  pipewire`, `AudioOut (exp 0372): the controller's ports follow …`, one `… port <n> type 4: opened on …DualSense…
  (48000 Hz, 6 ch); node.dont-reconnect, node.dont-fallback` and one for type 10.
- **At each pull:** for **both** pad ports `… its stream on the controller closed (an output device was removed);
  frames dropped until the controller is back`; then once a second `pad route: … port <n> type 4|10 (pad): <k> calls
  dropped, no controller device` for both, and **no** `audio trace: … (pad) … device playing` line for them while the
  pad is out (the 23:32 failure was exactly such a line for port 2).
- **R1** (during the 30-s pull): no emulator stream except the main mix in `wpctl status`; `pw-cli info` on the R0
  pad ids finds nothing; nothing of the emulator linked to the dock but the main mix.
- **At each replug:** for both ports `… opened on …DualSense… (48000 Hz, 6 ch) after an output device was added;
  node.dont-reconnect, node.dont-fallback` (after the sub-second pull possibly `… closed (an output device was
  removed)` then `opened … after an output device was removed`). A first `opening on … failed (after …): Pipewire:
  Stream error: …` followed a second later by `opened … after the once-a-second retry` is the dont-fallback race and
  is fine. Then `audio trace: … port <n> type 10 2 ch 48000 Hz (pad): … device playing` again.
- **R2** (5 s after each replug): two pad streams with **new** `object.serial`, `target.object` = the DualSense sink,
  both keys, linked to the DualSense sink; the main mix unchanged on the dock.
- **Cost:** `audio trace: … port 0 type 0 …: held <x> ms` in the seconds of each pull and replug (expected tens of ms
  at most; note the largest).
- **Fails if** any pad stream is linked to another sink at any read, a `(pad) … device playing` line appears while
  the pad is out, a port stays without a device after the replug (`pad route:` lines go on), or the maintainer hears
  haptics from the speakers.

**B. Optional A/B, `KYTY_BC5_PAD_PW_PROPS=0` (~5 min).** One 5-s pull as in A with
`KYTY_BC5_PAD_PW_PROPS=0` exported in front of the launcher. The same log lines; R0 without the two keys; it shows
whether the host's own close alone (at the port's next write after the event) leaves an audible blip at the pull.

**C. DualShock 4 (F329/F330 intact; ~5 min).** The DS4 on USB from the start, play, pull it for 5 s, plug it back,
play. Expected: no `AudioOut (exp 0372): … opened on` line (its sink, "Sony Interactive Entertainment Wireless
Controller", 2 ch, is not the controller's device, F347); the pad-speaker port on the default sink as
`audio trace: … port <n> type 4 1 ch 48000 Hz: … held 0.0 ms, … device playing` (no `(pad)`); rumble felt before and
after the replug (F329); no `closed` or `pad route:` lines; `wpctl status` shows the type-4 stream on the dock before
and after.

**D. No pad at the start (~5 min).** The launcher started with no controller connected; at the start screen the
DualSense is plugged in by USB, then he plays a minute. Expected: at the start no `opened on` line (the
pad-speaker port on the default sink, the vibration port without a device); at the plug `… port <n> type 4: moved
from the default sink on …DualSense… after an output device was added` and `… type 10: opened on …DualSense… after
an output device was added`; the R2 reads as in A; haptics felt.

**After.** The launcher and its mount gone (`distrobox enter ubuntu -- mountpoint ~/bc5-data/mnt/pkg-play`), the
BOX-LOCK line removed, the kernel stream ended; the grep extracts copied to `raw/` (no game data, no screenshots).
If A, C and D pass, integration is the top session's: the two files into `~/src/KytyPlus` (the header beside
`src/bc5/job_arena_fix.hpp`), both shared builds, patch 0001 regenerated — after the maintainer's yes (D19).

## Findings (for the top session to merge into HANDOFF)

- **F500 — Why the haptics went to the speakers after the 23:32:44 replug.** SDL 2.33.0 stops only the first open
  device on a removed node (`SDL_audio.c:522-529`), and its PipeWire backend neither reports a lost stream
  (`SDL_pipewire.c:1129-1140`) nor marks a named-device stream against moving (1160, 1243–1272). With the pad-speaker
  and the vibration port both on the DualSense, the second-opened device stayed "playing", F93's STOPPED-only reopen
  never ran for it, and WirePlumber 0.5.17 linked its stream to the default sink (`find-defined-target.lua:116`,
  `prepare-link.lua:71-76`). Under SDL's PulseAudio backend (before exp 0181) the same stream had
  `PA_STREAM_DONT_MOVE` (`SDL_pulseaudio.c:695-699` → pipewire-pulse `PW_STREAM_FLAG_DONT_RECONNECT` →
  `node.dont-reconnect`), so the survivor could not be moved: silent, which fits F94's "the haptic port never
  [reopened]". Exp 0181's backend switch turned a silent loss of the haptics after a replug into an audible one. Not
  explained: why the survivor was not moved back at 23:32:49. Sources: KytyPlus f266548 `3rdparty/SDL2` (4b69833),
  `/usr/share/wireplumber/scripts/linking/*.lua` (0.5.17), PipeWire 1.6.2/1.6.9 sources and `pipewire-props(7)`.
  Confidence: high for the code paths; the PulseAudio-era behaviour is inferred from code and F94, not observed.
- **F501 — The host follows the controller's audio device by SDL's audio device events, not by device status.** An
  event watch (`SDL_events.c:1156-1176`: called on the pushing thread before the event is queued) counts
  output-device removals and additions in two atomics; each pad port compares them on the thread that writes it
  (`Audio::PadRouteStep`). Chosen over a once-a-second look at the device list, which cannot see a replug that falls
  between two looks; that look stays as the backstop. Device opens and closes stay on the writing thread (as F93), the
  port's device fields change under `m_mutex`. Decision logic in `bc5/pad_audio_route.hpp`, Catch2
  `[pad_audio_route]` (15 cases). Unverified on the box.
- **F502 — A pad-routed port never keeps a stream across a removal.** At any output-device removal (or SDL's stop, or
  a 1-s look that misses the controller) every pad port closes its stream at its next write and reopens at once if
  the controller is listed; while it is away the frames are dropped (vibration → F214's rumble fallback) and a
  `pad route:` trace line counts them; when it is back each port reopens with its spec (one device per port, its
  `SDLAudioP` thread at nice −15); a DualSense that comes after the start takes both pad ports over. The DualShock 4
  path (no controller device: speaker on the default sink non-blocking, rumble worker) and `KYTY_BC5_NO_PAD_AUDIO`,
  `KYTY_BC5_PAD_SPEAKER` are unchanged. Cost: a close and open per pad port per replug, and once when another output
  device is removed during play. Unverified on the box.
- **F503 — Pad streams are opened with `node.dont-reconnect` and `node.dont-fallback`, the main mix never.**
  `PIPEWIRE_PROPS` is swapped only around the pad opens, all opens serialized (libpipewire reads it in
  `pw_stream_connect`, 1.6.2 `src/pipewire/stream.c`; SDL connects inside the open, `SDL_pipewire.c:1281`). With
  them WirePlumber 0.5.17 destroys a pad stream whose target is gone or not found (`find-defined-target.lua:116-123`)
  and never moves one (`prepare-link.lua:63-76`): nothing reaches the speakers even before the host's own close.
  dont-fallback is the essential one (dont-reconnect alone could pin a racing reopen to the default sink,
  `prepare-link.lua:63-67`). The swap is safe against concurrent `getenv` (glibc `__add_to_environ` overwrites an
  existing slot and frees nothing). `KYTY_BC5_PAD_PW_PROPS=0` is the A/B arm. Unverified on the box.
- **F504 — Status: built on the box, and a software replug passes; the maintainer's physical replug is still to
  come.**
  - **Build.** `build0372.sh` built the private binary cd5048e7 (the shared normal objects 1000ad2a + this
    `audio.cpp`) with Catch2 91/91 and `[pad_audio_route]` 15/15 on the box.
  - **Method.** Two S6N RT-on runs of 420 s ran with no one at the pad (2026-10-29 01:26 and 01:36).
    `replug0372.sh` turned the DualSense's PipeWire card profile off and on, which makes SDL's audio device removal
    and addition as a USB replug does.
  - **P1 (pulls of 5 s, under 1 s and 30 s).** The vibration port closed at each removal. It dropped its frames while
    the pad was away, and reopened on the DualSense within ~50 ms of its return with `node.dont-reconnect` and
    `node.dont-fallback`. No pad stream was ever linked to the dock.
  - **P2 (the pad's audio arriving at 171 s, then a 5-s pull).** The vibration port opened on it at once and
    survived the pull the same way.
  - **Both runs passed.** 35.8 and 35.3 flips/s, no kernel line, live saves unchanged.
  - **Cost.** One short main-mix gap per reopen: the main port's SDL queue reached 0 ms, against 42 ms normally.
  - **Not covered.** The HID side of a replug, a written pad-speaker port, and the DualShock 4.

## Verdict

Open, likely pass:
- The software replug (P1, P2) shows the pad's haptics stream leaving with the pad and coming back on it, never on
  the speakers, with no regression in the run.
- The maintainer's physical replug (A) decides; the DualShock 4 (C) is the regression check that remains.
- Then integration into the shared builds needs his yes (D19).
