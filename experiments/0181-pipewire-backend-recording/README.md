# 0181 — SDL's native PipeWire backend, a downmix that cannot clip, and a recording that does not lose samples

**Question.** The maintainer listened to the recording of exp 0180 and heard the sound "still
slightly crackly and sped up, with speed-ups". They agreed to install the PipeWire development
package so that SDL could use its native PipeWire backend ("install it and we'll check whether it
helps"). Does the backend help? Where do the crackle and the speed-ups come from?

**Setup.**
- **Packages in the `ubuntu` distrobox** (apt, Ubuntu's 1.6.2-1ubuntu1.2):
  - `libpipewire-0.3-dev`: the headers SDL's CMake looks for;
  - `libpipewire-0.3-modules`: the protocol and client-node modules libpipewire loads at run time;
  - `pipewire-bin`: holds `/usr/share/pipewire/client.conf`. Without it, SDL's backend failed with
    "Failed to create hotplug detection context". `libpipewire-0.3-common` was installed on the way
    and did not have that file.
  - The host's server is PipeWire 1.6.9. `tools/scripts/bc5-build.sh` now installs the three and
    re-checks PipeWire at every configure (`-U "*PIPEWIRE*"`).
- **Host code** (`audio.cpp`, in `backend/kytyplus-patches/0001-bc5-lle-agc.patch`):
  - SDL's driver order is set to `pipewire,pulseaudio,alsa` unless `SDL_AUDIODRIVER` is set; SDL
    itself tries PulseAudio first.
  - The driver in use is printed once (`AudioOut: SDL audio driver …`).
  - SDL's PipeWire threads (`SDLAudioP<n>`) get nice −15, like its PulseAudio threads (exp 0180).
  - `PIPEWIRE_PROPS` defaults to `{ channelmix.normalize = true }`.
  - `KYTY_BC5_AUDIO_DUMP_FROM` and `KYTY_BC5_AUDIO_DUMP_SECONDS` place the audio dump on a cutscene.
- **`capture-run.sh`** (here): one opening (New Game, slot 3, saves restored) on the normal build.
  It dumps the title's own sound for t 150–300 s before the host's output path, and records the
  headset's mix at the same time. `pw-top` counts every node's errors.
- **`align.py`** (here): loudness envelopes (10 ms) of the dump and of the recording, the lag of
  8-s windows every 10 s. A constant lag means the output path plays the title's sound as made; a
  falling lag means sound missing from the recording.
- **`record-final.sh`** (here): the lean build from start to combat, recorded with `parecord`
  (PipeWire's PulseAudio layer: real-time data thread, 500 ms server buffer).

**Result.**
- **The recorder of exp 0180 lost samples.** `pw-record`, started over SSH, gets no real-time
  priority: RealtimeKit refuses any change for a process outside an active seat ("Access denied").
  It overran 138 times in a PipeWire run and 284 times in a PulseAudio run. The headset and the
  emulator's stream had 0 errors.
  - Its recordings fall behind the dump by 190–400 ms over the cutscene, in steps at the scene loads.
  - The recording sent to the maintainer in exp 0180 therefore had skips the headset never played.
  - With `parecord`: 0 recorder errors, and the lag stays constant to 10 ms over the whole cutscene.
    One window at t 270 s is a weak match (correlation 0.36), and the next window is at 0 again.
- **The output path plays the title's sound intact.** The host pushed 150.4 s of sound in the
  150 s, with no clears and no rate dips (exp 0180's hold). The lossless recording matches the
  dump without a gap. The "speed-ups" in exp 0180's recording were the recorder's losses.
- **The crackle was clipping in the 7.1→stereo downmix.** The title outputs 8 channels. PipeWire
  sums them into the headset's 2 by default, and the night part's loud moments hit full scale:

  | run | backend | downmix | t 150–300: peak | clipped samples |
  |---|---|---|---|---|
  | c3 | PulseAudio | PipeWire's default | 32768 | 1116 |
  | c1 | PipeWire | normalized | 15433 | 0 |
  | c4 | PipeWire | normalized | 17953 | 0 |

  The recording of exp 0180 had ~1000 clipped samples at 225–255 s.
- **PipeWire against PulseAudio.** In the opening A/B (opening-run.sh of exp 0180, runs W1, W2
  against P1, P2), neither backend had a slow second or a clear. PipeWire runs our stream at a
  512-frame quantum (256 on PulseAudio), with 1 stream error in one run. The native backend removes
  `pipewire-pulse` from the path, and with it the place where the normalized downmix could not be
  set.
- **The final recording** (`record-final.sh f1`, see below) was sent to the maintainer and is
  not committed.

**Verdict.** The sound reaches the headset as the title makes it: no drops (lossless recording
against the dump), no clipping (normalized downmix, F239). The skips in the earlier recording were
the measuring tool's, not the emulator's. SDL's native PipeWire backend is the default now, and
the build container has its packages. TODO(verify) by ear: the maintainer's judgement of the final
recording, and of live play from the desktop. There, RealtimeKit may also make PipeWire's data
thread real-time.
