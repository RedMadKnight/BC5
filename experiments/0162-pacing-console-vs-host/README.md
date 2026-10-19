# 0162 — Why the second title speeds up and slows down: not the audio clock, not the flip label; the host's submission path takes three quarters of the title's render thread

**Question.** The maintainer, after a 30-minute session at the pad (run 793, 2026-10-19 07:05):
"both in the opening and in gameplay everything sped up or slowed down, almost never a natural
fluidity; it also looked as if memory were short". The maintainer's standing request: the
BC-250 is as close to a PS5 as hardware gets — find what the host does differently from the
console and do it the console's way.

**Setup.**
- Run 793: the maintainer's session, no scripted pad, direct journal synced per submission, the
  kernel log, host log and journal streamed to the laptop.
- Runs 794–798 (scripted: start screen, slot 1, Continue — the save loads into the night-scene
  gameplay at +121 s; the "load from save black screen" of 2026-10-18 did not recur):
  - 794: `KYTY_BC5_AUDIO_TRACE=1` (new): per port and second, frames pushed against wall time.
  - 795–796: stack samples of `game-main` and `Render Thread` (gdb, then `eu-sampler.sh` on
    eu-stack); 796 with the flip label reset at presentation (new, below).
  - 797: `KYTY_BC5_VIDEOOUT_TRACE=1` (new: flip rate, event registrations, flips by mode, status
    polls per second), `cpu-sampler.sh` (per-thread CPU % from /proc every second).
  - 798: as 797 without the direct journal (`play-pkg-quiet.sh`): the journal's own cost.
- Analysis scripts here: `submitcost.py` (submissions and host time per second from the
  journal), the samplers.

**Result.**
- **Frame pacing (793, journal).** Gameplay frames: p50 23.0 ms, p90 25 ms, for 28 minutes
  (`frames-793-per-minute.txt`); the last 4 minutes p90 84–131 ms with stalls of 2–12 s. No
  fence timeout, no host error; the kernel logged the F208 address-0 GE faults from 07:36 on
  (every 5 s, survivable). The box swapped 576 MB to zram; 11.4 GiB pinned at the end.
- **Audio clock (794).** The main port (type 0, 8 ch, 48 kHz, 512-frame grains): 94 pushes/s,
  48,128 frames per 1.003 s — rate 1.000 for the whole run, the game's audio thread held ~900
  ms/s on the SDL queue (42 ms), 0 forced clears (`audio-trace-794-sampled.txt`). The console
  paces the same way (blocking push at the DAC rate); nothing to fix here.
- **Flip label.** The direct path reset the display buffer's flip label at *submission*; the
  console resets it when the flip has happened at its vblank. Changed to the console's way
  (a `bc5-fliplabel` thread waits for `FlipQueue::Wait`, `BC5_DIRECT_FLIP_LABEL=submit`
  restores the old reset). Run 796 against 794: no change in frame times — the title asks for
  **flip rate 0 (every vblank) in VSYNC mode (mode 1)** and registers a flip event
  (`videoout-trace-797-sampled.txt`); with three buffers at 30–42 fps the label never gates it.
  The reset at presentation stays, as the correct behaviour.
- **Where the frame goes (796–798).** `game-main` sleeps most samples (its render-thread sync);
  `Render Thread` runs at 81–118 % of a core (`cpu-797-journal.txt`) and, in 52 eu-stack
  samples of gameplay (798): 13 in the title's own code, 39 in the host's submission path —
  10 in libc under `submit_one` (the IB copies), 10 in libc under libdrm (the CS ioctl), 5 in
  `Device::submit`, 2 in the mapping sync, the rest in the tracker, the indirect check, the
  wait logic. The journal: **4,000–5,000 submissions a second** (130 a frame: ~55 % acb, 40 %
  dcb, cc, hib), 5–6 M dwords/s, 59 GPU jobs a frame from the game thread plus 74–79 from the
  ring thread (`submitcost.py`); the game thread's own frame: 12–13.6 ms inside the host
  (prepare 6–7: filter 1.1–1.3, nested copies 0.8–1.0, copy 0.3, tracker 0.4; cs 4.5–5.1), 18
  ms outside. The journal costs nothing measurable: 42.1 vs 41.3 fps in the menu, 31.0 vs 29.5
  in gameplay with and without it (797/798, `cpu-798-no-journal.txt`).
- **Memory.** MemAvailable fell from 2.4 GiB to 1.5 GiB during the first two minutes of gameplay
  with 600 MB in zram; the title has `KYTY_GUEST_MEMORY_MB=13824` of the box's 15.5 GiB. Not
  short for the title; the host's pinned set is the pressure (F206, §4 of
  `docs/console-vs-host.md`).

**Verdict.** The speed changes are frame-time changes: the title targets 60 fps (flip rate 0,
VSYNC) and gets a variable 30–42 fps because its render thread spends three quarters of its
time in the host's per-submission work — the console's CP reads the title's rings and the CPU
pays nothing for them. The audio clock, the flip label (now console-correct) and the journal are
not the cause. Next (exp 0163): submit the title's buffers the console's way — chain consecutive
buffers of a queue into one kernel submission (INDIRECT_BUFFER packets from one host IB, or
several IB chunks per CS) and copy less (the title's buffers are already mapped), so that a
frame costs a few ioctls instead of 133. The inventory of the remaining console/host differences
is in `docs/console-vs-host.md`.
