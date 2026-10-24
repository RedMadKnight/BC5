# 0268 — the maintainer's play hitches of 2026-10-24 16:01–16:11 (DualShock 4)

**Question.** The maintainer played the second title on 2026-10-24 with a DualShock 4:
- normal build at 16:01 and 16:05;
- lean build (8e7707c5) at 16:08:49–16:11:34.

The lean session had a very strong picture and sound hitch with a game-order glitch: an animation played before the
conversation that should precede it. Then the emulator hung, with no GPU fault in dmesg. The normal sessions also
showed hitches where there had been none before.

What do the recorded data say about the clock voice, the cinematic clock, the audio ports' pacing and the
vibration port (type 10) around these hitches?

**Setup.** Read-only, offline, light (`nice`, `ionice -c3`, journals read with O_DIRECT at 15 MB/s).
- Logs:
  - `~/bc5-work/play-review-20261024/second-lean-1611.log`: the lean session.
  - `second-normal-1601.log`: the play-pkg log, which the 16:05 session had overwritten, so it is that session's.
- GPU journals `~/bc5-data/captures/play-20261024-1601` and `-1605` (65 and 42 MB). The lean build writes none.
- The box's kernel, system and user journals for 15:58–16:12.
- `pactl list short sinks` and `/proc/asound/cards`.
- The code paths read in `~/src/KytyPlus/src/libs/audio.cpp` and `controller.cpp`.
- Scripts:
  - `long0268.py`: flips, frames over 250 ms and TIMEOUT/fault/given-up counts per journal (exp 0214's reader);
  - `filt0268.py`: how often the host's per-frame steps (filter, sync, hints, label waits) were long. Compared
    with exp 0242's R1 of the day before (`play-20261023-1939`).
- Not available:
  - The clock voice and the cinematic clock themselves. The play launchers run no APR journal and no exp 0200
    sampler.
  - The lean session's pad recording (`route-record.txt`), which ASTRO BOT's session overwrote at 16:14:30.

**Result.**
1. **What the lean session recorded: almost nothing about the hitch (`raw/lean-1611-lines.txt`).**
   - The lean build has no audio trace, fps counter or journal. Its log has the start-up lines and three AudioOut
     threads. It has one "bc5 ajm: ATRAC9 vibration layout 7 decoded by vgmstream (haptics)" line and three
     tiler-pool lines.
   - It also has 1,439 "bc5-direct: shared map at 0x0+…: -22" lines. These are not new: 1,062 in exp 0214's S1N
     and 2,090 in exp 0242's R1.
   - No kernel, PipeWire or GPU message during it. It ended at 16:11:33, when ds-inhibit released `/dev/hidraw2`,
     most likely closed by the maintainer during the hang.
   - So the lean session's hang and its order glitch cannot be read from any record. It ran with the same
     controller as the 16:05 session, so results 2–4 describe its configuration but were not measured in it.
2. **With a DualShock 4, the title's pad-speaker port holds its audio thread (the 16:05 session).**
   - The normal build traces each audio port once a second (`raw/1605-timeline.txt`). The title writes two ports
     from one thread, in lockstep:
     - port 0, type 0 (main, 8 ch);
     - port 1, type 4 (`AUDIO_OUT_PORT_TYPE_PADSPK`, 1 ch, `audio.cpp:39-46`).
   - The host routes a pad-speaker or vibration port to the controller only when an output device's name contains
     `KYTY_BC5_PAD_AUDIO_DEVICE`, default "DualSense" (`audio.cpp` `OpenSdlDevice`).
     - The DualShock 4 has its own sink, "Sony Interactive Entertainment Wireless Controller", 2 ch at 32 kHz
       (`raw/journal-1558-1612.txt`), which does not match.
     - So the pad-speaker port went to the default output, the dock, as an ordinary blocking port. Only ports with
       `pad_route != 0` are made non-blocking ("the game's audio thread is never held for a pad port").
   - At t 149–150 s the audio thread was held 493 and 635 ms in port 1's wait, against 0–8 ms in the other
     seconds. Port 0 then went without data: its queue fell to 0 and its rate was 0.835 and 0.816. That is about
     0.36 s of the main mix missing, an audible hitch (`raw/1605-audio-fps-140-167.txt`).
   - The title's game clock is the frames the host accepted (Wwise's play position, `audio.cpp` comment;
     F198/F242). So the cinematic clock fell behind by as much over those 2 s.
3. **The vibration port (type 10) cannot be timed from these data.**
   - With no "DualSense" device, the port opens with no SDL device. `AudioOutOpen` still returns it, and its blocks
     go to the rumble fallback (F214): `PadRumbleFromVibrationFrames` → `ControllerAudioRumble` →
     `SDL_GameControllerRumble`, on the title's same audio thread. This happens before `QueueSdlAudio` returns for
     a port with no device, i.e. before the trace's counters (`audio.cpp:474-500, 742`).
   - So the trace never lists the port, and whether it stalled is not recorded.
   - Since F301 its blocks carry the decoded haptics instead of silence. So with a DualShock 4 the fallback now
     sends a rumble on every change, and every 40 ms while it is non-zero (`controller.cpp:595-616`), from that
     thread.
   - Whether `SDL_GameControllerRumble` blocks there is the AnyPS5 session's question.
4. **The other hitches of the 16:05 session stalled the whole process, not one port.**
   - Audio-clock loss after t 45 s, from port 0's rate: 1.93 s net in about 120 s.
     - t 149–150 s: 0.36 s (result 2);
     - t 156 s: 0.94 s; the audio thread made 21 calls in 1.16 s and held only 122 ms, so it was not waiting on a
       port;
     - t 163 s: 0.23 s; t 152, 154 and 165 s: 0.07–0.09 s each.
   - Frames (`raw/j1605-frames.txt`, `raw/j1605-long.txt`): 32.2 flips/s, 16 frames over 250 ms, one over 1 s
     (1,004 ms at t 115.7 s, the game thread outside the host), no TIMEOUT or fault.
   - At t 154–156 s the game thread sat inside the host for 239 and 569 ms in single steps:
     - filter 519 ms at t 154.9 s;
     - sync 186 ms;
     - hints 154 ms with label waits 184 ms at t 155.4 s.
   - Other long frames had sync 301–360 ms or hints 173 ms (t 120.4, 142.5, 146.0 s).
   - Such steps did not happen in the 16:01 session or in the day before's R1 (`raw/host-steps.txt`):

     | | filter max | sync > 100 ms | hints > 100 ms | label waits > 100 ms |
     | --- | --- | --- | --- | --- |
     | 16:05 | 519 ms | 4 | 2 | 1 |
     | 16:01 | 19 ms | 1 | 0 | 0 |
     | R1 | 41 ms | 0 | 0 | 1 |

   - Long times in unrelated steps at once point to the threads not running (CPU or memory), not to one code
     path. Steam ran until 16:08:43 and logged a peak of 4.3 GB of memory and 862 MB of swap at its shutdown. No
     memory sampler ran, so this stays a lead.
5. **The controller was swapped during the 16:01 session (`raw/journal-1558-1612.txt`).**
   - The DualSense was unplugged at 16:03:07 (about t 66 s of that journal), and PipeWire logged its audio card's
     removal. A DualSense was connected again for 3 s at 16:03:43–16:03:46. The DualShock 4 registered at 16:03:51
     (about t 110 s).
   - That session's long frames came after: t 152–155, 186 and 207–212 s, the game thread outside the host for
     190–642 ms (`raw/j1601-long.txt`).
   - Its ports had been opened on the DualSense. After an unplug the host looks for a "DualSense" device again
     once a second, from the audio thread (`audio.cpp:665-690`).
6. **What these data do not show.**
   - The clock voice's reads and the cinematic player: no APR journal or sampler ran in play.
   - Anything of the lean session's hang or its order glitch (result 1).
   - That the rumble fallback blocks (result 3).
   - What stalled the whole process in the 16:05 session (result 4).

**Verdict.**
- **One hitch mechanism is established, and it is new with the DualShock 4.** The title's pad-speaker port (type
  4) has no controller device to go to. So it becomes a second blocking output on the default sink, written by the
  same thread as the main mix.
  - In the 16:05 session it held that thread for 1.1 s (t 149–150 s), and the main mix and the title's audio clock
    lost 0.36 s.
  - With a DualSense the port goes to the pad and is never waited for. That is why these hitches were not seen
    before.
- **The vibration port's rumble fallback now runs on that thread with real data (F301, F214).** It cannot be timed
  from these logs.
- The largest loss of the 16:05 session (0.94 s at t 156 s) and its long frames were a stall of the whole process,
  in several host steps at once, with Steam's 4.3 GB in memory. Cause not established.
- The lean session's hang and order glitch have no record.
- Next:
  - A switch (off by default) that never blocks the title's audio thread on a pad-speaker or vibration port with
    no controller device, as the pad-routed ports already behave. `KYTY_BC5_PAD_AUDIO_DEVICE` does not do this:
    matching the DualShock 4's sink would also send the vibration port's haptics to its speaker.
  - Then a scripted run on exp 0203's O2 route with the DualShock 4 attached, A/B with the switch and with
    `KYTY_BC5_PAD_RUMBLE_FALLBACK=0`. Run exp 0200's sampler, the audio trace and the box's memory sampler beside
    it, and time the fallback's `SDL_GameControllerRumble` calls.
  - The top session put the switch into the AnyPS5 session's exp 0267 diff, not a separate one. That diff also moves
    the rumble write to a worker thread and adds `KYTY_BC5_PAD_SPEAKER=off`. The top session plans the A/B once that
    diff is built.
