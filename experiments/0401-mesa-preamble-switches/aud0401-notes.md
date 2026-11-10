# Exp 0401 series e4: AnyPS5's AudioOut2 fixes after 7ba97f4 (notes, 2026-11-03)

This is item 2 of exp 0402's Top 10 and the AudioOut row of its §2. It covers five AnyPS5 commits after `7ba97f4`: `c34ab0258`,
`11f217b14`, `42beeaa46`, `b87075aad` and `ccaac6602`. AnyPS5 is GPL-2.0-only. Its code was read at
`4f41f4c375f5abb487dbd184fbc150f31994d762` in another session's clone, with `git show <commit>`.

Our side is the box tree: KytyPlus `f266548` plus patch 0001, read from the laptop copy `e4/full`. The SDL code cited is
KytyPlus f266548's `3rdparty/SDL2` (SDL 2.33.0, the submodule exp 0372 read). The laptop copy read here is the same source
as exp 0372's box copy, apart from line endings.

Nothing ran on the box. On the laptop, MSVC 14.44 was found after all, so the C++ is syntax-checked. The test also ran in a
simulation that uses stand-ins for `audio.cpp`. The box compile, with GCC or Clang and the real `audio.cpp`, is still the
first real compile.

## Verdicts

Line numbers are those of the input tree (`libAudio2.cpp` fb44443e, `audio.cpp` f58ec010).

| AnyPS5 commit | What it fixes there | Ours | Verdict |
|---|---|---|---|
| `c34ab0258` | A grain plays the PCM taken at the set (`AudioOut2Port.cpp:119`, the copy is made at the set: `CopyGrain` at 171 and 298) | Advance reads the buffer when it runs | **missing**, ported as part `set` |
| `11f217b14` | A port that was not set again plays silence, unless it was given one buffer once (`AudioOut2Port.cpp:299`, 304) | Every grain reads the last pointer, whether or not it was set again | **missing**, ported as part `silence` |
| `42beeaa46` | A blocking push also waits after it queues, until there is room (`AudioOut2Context.cpp:283`, 390, 433) | Device path: already paced by playback. Timer path: the push that fills the queue returns at once | **already fixed** with a device; **missing** on the timer path, ported there only as part `room` |
| `b87075aad` | The default output is reopened when SDL reports it STOPPED (`AudioOut.cpp:198`, 509, 547) | No reopen for a non-pad port, but SDL's PipeWire backend never stops one | **not applicable** on the box (our backend). Not ported |
| `ccaac6602` | The controller sound card is reopened when it is STOPPED (same function) | Exp 0372's pad route closes and reopens on STOPPED and on every device event | **already fixed** (exp 0372, F501–F504). Not ported |

### `c34ab0258`: missing

- **Where we read the buffer.** `AudioOut2ContextAdvance` (`libAudio2.cpp:550-580`) copies each port's buffer when Advance runs:
  `std::memcpy(c.pcm.data(), port.pcm_data, …)` at line 564.
- **What the set keeps.** `AudioOut2PortSetAttributes` stores only the pointer (lines 832-838).
- **Effect.** A title that clears or reuses its buffer between the set and Advance plays what is there at Advance. That is
  AnyPS5's pre-fix behaviour.
- **AnyPS5's own case cannot reach us.** It was PPSA02433's Wwise object ports. We open no device for an object port (lines
  761-771), and Advance skips a port without one (line 554). Object ports are not mixed here at all. That gap is larger than
  this fix and outside it.
- **The defect is still possible on bed ports** (main, pad speaker, vibration).
- **The second title does not show it.** Its sound is correct with the read at Advance (F247). Exp 0188's traces count one
  `SetAttributes` per Advance: `raw/M3.txt` 93/93, 89/89, 84/83.

### `11f217b14`: missing

- **The pointer is never cleared.** `pcm_data` lasts until the next set, or until the port is destroyed (lines 835, 807).
- **It is read every grain.** Advance (lines 554, 564) and the push-time path (lines 409-416) read it on every grain,
  whether or not the port was set since.
- **Effect.** A port that is given a buffer every grain and then none, as during a load, plays whatever that memory now
  holds.
- **Ours is looser than AnyPS5 was before the fix.** AnyPS5 repeated a buffer only when the port had been given that same
  buffer. Ours repeats any buffer.

### `42beeaa46`: already fixed with a device, missing on the timer path

**Device path.** This is the second title's path.
- A blocking push goes through `AudioOutOutputs` to `QueueSdlAudio`.
- `QueueSdlAudio` waits before it queues, until the device's SDL queue holds at most `min_queued_size` (`audio.cpp:829-869`).
  That is about 30 ms: 3 grains of 512 frames at 48 kHz.
- The level is the device's grains beyond a two-grain cushion, plus the advanced grains (`libAudio2.cpp:679-700`).
- So a push returns only after playback has drained the device. It leaves a level of at most 2 plus the advanced grains,
  which is below the title's depth (the level reaches 4 in exp 0188's traces).
- Measured: the main port is held about 1,000 ms each second, at rate 1.000, with SDL's queue steady at 42 ms. Sources:
  exp 0188 M5 and M6, and exp 0372 `raw/P1-audio-lines.txt.gz`.
- This is the fix's intent: pace the pushes by playback.

**Timer path.** This is the path when no port of the context has both a device and PCM (`libAudio2.cpp:623-656`).
- The blocking push that brings `queued` up to the depth returns at once.
- The level (`queued` plus the advanced grains, line 698) then reads full. That is AnyPS5's pre-fix shape.
- On the box this happens only in two cases:
  - there is no sound device;
  - a context's ports have no audio handle (object ports, or formats we do not know).
- When ports exist but have no device, `AudioOutOutputs` already sleeps one block per call (`audio.cpp:1209-1233`), so the
  queue seldom fills.

### `b87075aad`: not applicable on the box

- **Ours has no reopen for a non-pad port.** Only `PadRouteStep` looks at `SDL_AUDIO_STOPPED` (`audio.cpp:917`).
- **The defect cannot occur with SDL's PipeWire backend, which the box uses:**
  1. The host asks for PipeWire first (`audio.cpp:397`). The box runs it: exp 0372's log has
     `AudioOut: SDL audio driver pipewire`.
  2. The main mix, and every port not routed to the pad, opens the default device with a null name (`audio.cpp:495`).
  3. Such an SDL device has a null handle (`SDL_audio.c:1316`, 1381-1397, 1416).
  4. `SDL_RemoveAudioDevice` stops only an open device whose handle is the removed node's (`SDL_audio.c:510-529`).
  5. The PipeWire backend never calls `SDL_OpenedAudioDeviceDisconnected`. Its stream-state callback only signals the open
     (`SDL_pipewire.c:1129-1140`).
  6. A default open connects to `PW_ID_ANY` (`SDL_pipewire.c:1170`), and WirePlumber moves such a stream to the new default
     sink. Exp 0372's reads show the main mix linked throughout.
- **It is missing only in these cases:**
  - SDL's PulseAudio or ALSA backend, which do stop devices (`SDL_pulseaudio.c:400`, 416, 466, 515; `SDL_alsa_audio.c:255`,
    399). We get them only if PipeWire fails to start, or if `SDL_AUDIODRIVER` asks for them.
  - `SDL_AUDIO_DEVICE_NAME` set: a default open then becomes a named one (`SDL_audio.c:1337-1339`).
- None of these is the box's setup, so it is not ported.

### `ccaac6602`: already fixed by exp 0372

- **Ours.** Every port routed to the pad runs `PadRouteStep` before each write (`audio.cpp:651-653`, 908-945). It closes and
  reopens its stream in four cases:
  - SDL reports the device STOPPED (line 917);
  - any output device is removed;
  - any output device is added;
  - the once-a-second look no longer lists the controller.
- The streams open with `node.dont-reconnect` and `node.dont-fallback` (F501–F503).
- **Why AnyPS5's fix is weaker.** It reopens on STOPPED only. F500 showed that SDL stops only the first device opened on a
  removed node (`SDL_audio.c:522-529`), so the second pad stream stayed "playing".
- **Ours passed** the software and the physical replug (F504).

## What was ported

The switch is **`KYTY_BC5_AUDIO_FIXES`**.
- Unset, empty or `0` means off (F767's reading). Any other value turns all three parts on.
- A comma-separated list of `set`, `silence` and `room` turns on only those parts.
- The switch is read once, at the first AudioOut2 context, and prints one stderr line:
  - `[bc5] exp 0401: audio fixes off`;
  - or `[bc5] exp 0401: audio fixes on: set silence room` (only the parts that are on).

The comment block in the unit (lines 399-421 of the output) names exp 0401 series e4, AnyPS5, the paths, the commits and
GPL-2.0-only. All the lines below are lines of the output file.

- **`set`**:
  - `SetAttributes` copies one grain of the given buffer, through `Bc5AudioFixesOnSet` (line 1055). It copies only for a
    port with an audio handle.
  - Advance takes that copy instead of reading the buffer, through `Bc5AudioFixesCaptureAtAdvance` (line 779). This happens
    only when the port was set since its last grain.
- **`silence`**:
  - Each port counts the buffers it was given since it was created, up to 2. A null set clears the count.
  - A port with no set since its last grain gets one grain of zeros, unless it was given a buffer exactly once. The zeros
    keep its device fed, so pacing does not change.
  - This applies at Advance, and on the push-time path (`Bc5AudioFixesAtPush`, line 625). The push-time path covers titles
    that never Advance, and the fallback after 200 ms without an advanced grain.
  - The first silenced grain of each port prints one line (at most 32 in a run):
    `[bc5] exp 0401: AudioOut2 port 0x… (type 0x…, format 0x…): silence at Advance|Push, …`
- **`room`**:
  - After a blocking push on the timer path, `Bc5AudioFixesWaitForRoom` (lines 859 and 864) waits in 1-ms steps until
    `queued` is below the depth, for at most 200 ms. These are AnyPS5's `FULL_WAIT_STEP` and `FULL_WAIT_TIMEOUT`.
  - The device path (`use_device_clock`) is untouched.
- **The test hook** `Bc5AudioFixesPeekGrain` (line 579) has external linkage. Only `aud0401.cpp` calls it; the emulator
  never does.

### The off path

With the switch off, each helper returns before it touches a port or the context:
- `OnSet` does nothing.
- `CaptureAtAdvance` returns false, so the old `memcpy` runs.
- `AtPush` returns `pcm_data`, so the downmix gets the same pointer as before.
- `WaitForRoom` returns at once.

The only textual changes to old lines are these:
- Advance's loop variable is `auto&` instead of `const auto&`.
- The downmix call takes `data`, which is `state.pcm_data` when the switch is off.
- The port struct has five more members, which are never used when the switch is off.

The one new output is the stderr line.

### Files and md5s, from the tree above

| File | In | Out |
|---|---|---|
| `src/libs/libAudio2.cpp` | fb44443e6f19f5d62c739cb39a7c377c | **7a1914c898e62e1e6ce699807aafbc74** (diff +224 / −4: the 4 old lines are replaced by edited ones) |
| `src/libs/audio.cpp` (read only) | f58ec0105874173a9f84954706a17e96 | not written |
| `src/bc5/pad_audio_route.hpp` (read only) | 51131854822a629c2b24739e3603ef5d | not written |

- **Exp 0372's code is unchanged.**
  - `grep -c 'exp 0372'` on the one edited file gives 0 before and 0 after; `mkaud0401.py` asserts this.
  - `audio.cpp` keeps its 5 lines. It and the header are only read: the script requires both to be present, and requires
    `audio.cpp` to carry exp 0372.
- **The script's own checks:**
  - every anchor occurs exactly once;
  - a second run on its own output stops with "the unit has the edit already";
  - every edit keeps braces, parentheses and brackets balanced;
  - the output is ASCII with no CR, like the input;
  - every helper is defined once and used where expected.
- **The scripts.** `mkaud0401.py` is b32cd656. `aud0401.cpp` is a28b36bd.
- **Building the unit.** Compile the private unit with the shared normal build's command for `src/libs/libAudio2.cpp`, then
  relink. No header changes.

## The CPU test: `aud0401.cpp`

It needs no game, no GPU and no sound device.
- **No device.** It sets `SDL_AUDIODRIVER=bc5-no-device-0401`. SDL's audio init then fails, and every port opens with an
  audio handle but no device.
- **Setup.** It initialises the Audio subsystem itself and silences LOGF.
- **What it drives.** The host's own AudioOut2 functions. It reads the grains back through the hook.

The cases:
- **set**: set the buffer, clear it, then Advance. On, the grain holds the set's PCM. Off, it holds the cleared buffer.
- **silence**: give the same buffer twice, rewrite it, then Advance with no set. On, the grain is silence. Off, it holds the
  rewritten memory.
- **once**: a buffer given once and then rewritten is read at Advance, on and off.
- **cleared**: a null set takes the port out of the grain. The next buffer counts as given once and repeats.
- **room**: a context with no port, depth 2 and 85.3-ms grains gets two blocking pushes.
  - On, the second push returns after about 85 ms, with the level at 1 of 2.
  - Off, it returns at once, with the level at 2 of 2.

There are 25 checks. The output is `aud0401: on 25 of 25; end` or `aud0401: off 25 of 25; end`, with exit 0 only then.

**Build.** Use the compile command of `src/libs/libAudio2.cpp` with `aud0401.cpp` as the source. Link it with every emulator
object except `main.cpp.o`, with the private `libAudio2.cpp.o` (the edited unit, which defines the hook) among them, and with
the link line's libraries. This is how `npgate0401.cpp` is built.

**Run** these three:
- `KYTY_BC5_AUDIO_FIXES=1 ./aud0401 on`
- `KYTY_BC5_AUDIO_FIXES=0 ./aud0401 off`
- `./aud0401 off` with the switch unset.

Optional: `KYTY_BC5_AUDIO_FIXES=set,room ./aud0401 on`. The silence case then expects off.

**Not covered.** The device path, the push-time silence (its output goes into `audio.cpp` and cannot be read back), and the
pad route.

**Laptop simulation.** The test was built with MSVC 14.44 from three parts:
- the edited unit;
- `aud0401.cpp`;
- a stand-in for the emulator's other objects, `scratchpad/msvc/sim/sim.cpp`. It copies `audio.cpp`'s path without a device.

The results:

| Switch | Result |
|---|---|
| `1` | on 25 of 25 |
| `0` | off 25 of 25 |
| unset | off 25 of 25 |
| `set,room` | on 25 of 25 |
| `silence` | on 25 of 25 |
| unset with the argument `on` | refused, rc 2 |

- The room case's second push took 94–95 ms with the switch on, and 0.0 ms off.
- The unit's own `audio fixes on|off` line and its silence line appeared as designed.
- A negative control with a misspelt member failed to compile, so the stubs catch name errors.
- This is not the box's compiler, not the real `audio.cpp`, and not SDL.

Laptop artefacts, under the scratchpad
`C:\Users\kjani\AppData\Local\Temp\claude\7e70d624f1bff3f5\19eb012d-ed8a-4416-af2a-d3b1f4ce12f0\scratchpad\`:
- `aud0401-out\src\libs\libAudio2.cpp`, the output;
- `aud0401.diff`;
- `msvc\stub`, the stub headers;
- `msvc\sim`, the simulation, with `run-on.txt` and `run-off.txt`.

## The replug check (exp 0372) this change needs

**It is needed.** `audio.cpp` and the pad route are unchanged, but the second title's vibration port is an AudioOut2 port.
- In exp 0372 P1, port 2 (type 10) was written in 512-frame calls at 94 a second, which is the AudioOut2 grain.
- So `set` and `silence` change what reaches the DualSense's actuators.
- The silence line names the port by its AudioOut2 type: 0x6 is the vibration port, 0x3 the pad speaker, 0x0 the main port
  (`libAudio2.cpp` maps them to the AudioOut types 10 and 4).

**1. The software check: `s6n0372.sh` with `replug0372.sh`.**
- Run P1 (three pulls) and P2 (`late`) on the e4 binary.
- Set `BC5_0368_SWITCHES="KYTY_BC5_AUDIO_FIXES=1"`. `s6n0372.sh` passes it to the emulator and checks it in the emulator's
  environment.
- `s6n0372.sh` pins exp 0372's private binary (`BIN`, `binary.md5`) and its own BOX-LOCK line. A copy pointed at the e4
  binary is therefore needed, made the way `mk-s6n0372.pl` made it from `s6n0368.sh`.
- It must show what P1 and P2 showed:
  - at each pull, for both pad ports, `… its stream on the controller closed (an output device was removed)`;
  - then `pad route: … calls dropped, no controller device` once a second;
  - no `(pad) … device playing` line while the pad is out;
  - at each return, `… opened on …DualSense… after an output device was added; node.dont-reconnect, node.dont-fallback`,
    and R2 shows new serials on the DualSense sink;
  - no pad stream ever linked to the dock;
  - the main port's hold no worse than P1's (one short gap per reopen);
  - a pass at about 35 flips/s, with 0 crash, kernel or TIMEOUT lines, and the live saves unchanged.
- It must also show, for this switch:
  - `[bc5] exp 0401: audio fixes on: set silence room` once;
  - the vibration port's `(pad) … device playing` lines at 94 calls a second (rate 1.000) while the pad is present;
  - the main port's rate at 1.000.
- Any `[bc5] exp 0401: AudioOut2 port … (type 0x6 …): silence at …` line means the silence rule is cutting the haptics.
  Report it, and rerun with `KYTY_BC5_AUDIO_FIXES=set,room`.

**2. The physical check with the maintainer.** Run exp 0372's test plan A, then C, with the switch on.
- A: a DualSense on USB, pulled for 5 s, under 1 s and 30 s.
- C: a DualShock 4.
- He must feel the haptics before and after each replug on the DualSense, and the rumble on the DualShock 4 (F329).
- He must not hear haptics from the speakers, and the sound must be normal.
- The same binary with the switch unset must print `audio fixes off`. It is today's path.

## Doubts

1. **The haptics could go silent.** If the title gives its vibration buffer more than once, then keeps rewriting it without
   setting it again, `silence` zeroes every later grain.
   - How often the title sets that port is not known.
   - Exp 0188's trace counted all sets together, about one per Advance in M3. This tree's `libAudio2.cpp` no longer has the
     `KYTY_BC5_AUDIO2_TRACE` counters.
   - The silence line is the indicator, and `set,room` is the A/B arm.
2. **The copy at the set could be wrong.** If a title sets a buffer before it renders into it, the copy taken at the set is a
   grain old.
   - The second title's 1:1 sets and Advances, with correct sound when read at Advance, do not show the order within a grain.
   - AnyPS5 calls the console's buffer ownership and read timing unverified.
3. **Pre-existing AnyPS5 behaviour is not ported.** These were in place before `7ba97f4` and are not among the five:
   - several sets between two grains are queued, up to 16, and played one per grain (ours keeps the last set);
   - `MarkBufferReused`, for one buffer handed to several ports.
4. **Object ports are not mixed here at all.** `c34ab0258`'s own case lives there, so the port does not fix any title that
   needs object ports.
5. **`room` changes only the timer path.** The second title on a box with a sink never takes it. The CPU test is its main
   check.
6. **A pointer is used after its lock is released.** The silence buffer's pointer, like `downmix` today, is used by
   `AudioOutOutputs` after the port lock is released. A port destroyed during a push would leave it dangling. This hazard
   already exists for `downmix`.
7. **`b87075aad` stays missing under SDL's PulseAudio or ALSA backends.** The host falls back to them only if PipeWire fails
   to start.
