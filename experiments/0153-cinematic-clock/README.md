# 0153 — Why the opening stands still: its clock is the Wwise play position of its audio event, frozen at 4.949 s

**Question.** Experiments 0150–0152: after New Game the opening keeps its first shot, the audio
streams, the animation stream reads two chunks and no more. What drives the cinematic's time, and
why does it not advance?

**Setup.**
- BC-250 dev box, 2026-10-17 12:15–13:22, maintainer at the pad. Runs 584–601: run 579's script
  (New Game on an empty slot) with gdb attached at +40 s from a detached driver on the box
  (`~/bc5-work/drive5NN.sh`, screenshots, kill at +137 s). Each gdb script arms its breakpoints
  from the host's `AprCommandBufferReadFile` hit for file id 0x628c6db3 (`animstrm`), so the
  trace starts with the opening. Scripts `~/bc5-work/gdb-anim*.gdb`, outputs in `raw/gdb-sessions.txt`
  (values and addresses only, no title code). Private code read with `objdump -D -b binary` from
  the title's text dump; whole-text disassembly cached at `/var/tmp/eboot.dis` on the box.
- gdb notes: `break *'Libs::LibAmpr::Ampr::AprCommandBufferReadFile'` (quoted) stops at the first
  instruction, where the caller's callee-saved registers are intact; a hardware watchpoint reports
  value changes only; `handle SIGSEGV/SIGBUS/SIGILL nostop noprint pass` is required (the emulator's
  fault handler).

**Result.**
1. **The request path** (runs 586–587). The flush function 0x903c7c010 submits a batch of 32-byte
   records built on the stack by 0x903c7a4f0 from request objects; the request object of the first
   `animstrm` chunk (0x50 bytes: state at +4, file handle|stream base 0x1e|0x2a0abe0 at +8, chunk
   index 0x170/0x174 at +0x28) is completed with state 3 by the "Archive Resolve" thread
   (0x903c7a9f5) and polled by **game-main** at 0x903abbb02, in the stream update function
   0x903abba10 (the streamer object 0x1070281950, its clip resource 0x10191797b8).
2. **The stream advances with time, slowly** (runs 589–591, 594). The update computes the chunk
   index from the clip time (`clamp(t, 0, 94.03 s) × 30 fps`, binary search in the clip's table)
   and requests the chunk that covers it; chunks are 0x170 frames = 12.4 s apart, so a third
   chunk is due at t ≈ 24.8 s. Without gdb (run 590, three reads of the position word) the clip
   advanced 16 → 40 → 46 frames over +130/+136/+141 s: **4 then 1 frames per second instead of
   30**, slowing down. The clip time is the owner object's +0xf8 (owner 0x1070281360, the
   cinematic player; the stream object is its +0x5f0; the update is reached by the tail jump at
   0x903b7d008 from 0x903b7cfc0, called at 0x903b7e5e1 in the player's tick 0x903b7df30).
3. **The clip time is slewed toward an external advance** (runs 596–597). The advance function
   0x903b77670 receives the real frame dt (0.03–0.067 s) but adds a filtered amount:
   `err = target(+0x114) − dt + debt(+0x100); added = dt + 0.02·err; debt = 0.98·err`, then
   clamps against the sync source's length (+0x3c of the object at +0xb0: 94.033 s, the clip's
   length). With `target` always 0 the debt converges to −49·dt and the added time to
   **2 % of dt**: the decay seen (0.055 → 0.010 s per frame).
4. **The target is the advance of a global sync clock** (runs 598–601). In the tick 0x903b7df30
   the main player (flags +0x120 & 3 == 3, global mode byte 0x90ae007be == 1) adds
   `max(0, clock − last)` to `+0x114`, with `clock = *(float*)0x90ae007b4` (wrap period 10 s at
   0x90bf72470). That clock is written only at 0x903b87fea in game-main:
   `clock = 0.001 × ms` from `AK::SoundEngine::GetSourcePlayPosition(playingId, &ms)`
   (0x9000bdac0 → 0x900159d90) when it returns 1 — the title's cinematic is slaved to the play
   position of its audio event. In the menu the clock rises in ms steps (0.010, 0.042, 0.170, …);
   **in the opening the call returns 1 with ms = 4949 at every poll, for playing id 0x30**, and
   the clock stays at 4.949 s (4.949 at the dump of 2026-10-16 too). The other sounds keep
   streaming (`wem_0`, `wem_1`, `wem.us`, 128 KiB every ~0.5 s).

**Verdict.**
- **F182 explained to its source: the opening's clock is Wwise's play position of its master
  audio event (playing id 0x30), and that position freezes at 4.949 s.** Everything downstream
  (the slew filter, the animation stream's demand, the characters and camera) follows from it.
  The audio heard during the opening comes from other voices.
- Next: why Wwise reports a frozen position for that voice. Candidates: the voice's own stream is
  starved (its file is not among the three streamed ones: find the voice's source — the
  `AkPBI`/stream of playing id 0x30 — and its reads), the voice went virtual or paused (the host's
  focus/suspend state, `sceAudioOut2` port state), or the position comes from a sink/device
  timing query the host answers with a constant. A gdb break inside Wwise's
  `GetSourcePlayPositions` (0x900159d90) with the voice's structure, and the host's AudioOut2
  journal (`AudioOut2ContextPush`/`Advance`/`GetQueueLevel`/`PortGetState` answers), are the
  tools.
- Kept from this work: the detached driver + watchdog pattern for gdb runs, and the breakpoint
  recipes in `raw/gdb-sessions.txt`.
