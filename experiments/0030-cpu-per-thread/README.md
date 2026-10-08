# 0030 — CPU per thread in the maintainer's play

**Question.** With the level load down from 240 s to well under a minute (F51, F71) and the
first level at 47–55 fps, which threads carry the CPU during a load and during play, and is
any of them the limit?

**Setup.** BC-250, Bazzite, 8C/16T (`nproc` 16), the track-B host (KytyPlus f266548 + patch
0001 at commit f1ba08e, `BC5_GC_MODE=direct`, async rings) started from the desktop shortcut
by the maintainer, who played the start of the game: intro video, title screen, the first
level's load and its opening. `thread-sampler.py` (in this directory) waits for
`kyty_emulator`, then every 2 s reads `/proc/<pid>/task/*/stat` and writes one JSON line
with each thread's CPU seconds in the interval and its name (the guest's thread names reach
the host threads since F76; the host's own threads are still unnamed and show as
`kyty_emulator`). No perf, no root. Raw samples: `run135-threads.jsonl` (76 samples,
152 s). Phases were read off the thread activity: the video decoder thread marks the intro,
`RoomLoad_ATQT` / `OdxAsyncLoader` / `GfxTextureStream` mark a load, the `tbb_thead`
workers at a steady level mark play.

**Result.** Per phase, the CPU of the busiest threads as a share of one core (the sum is
out of 1600 % for 16 hardware threads):

| Phase (run time) | Total | Busiest threads |
|---|---|---|
| Start and first load (0–15 s) | 157 % | DrawThread 28, host thread 295953 24, OdxAsyncLoader 12, two host threads 11 each |
| Intro video (15–27 s) | 251 % | AvPlayerVideoDecoder 94, host 295953 33, DrawThread 21 |
| Title screen (27–44 s) | 278 % | DrawThread 38, host 295953 31, host 295974 22, SceSndzAudioOut 15, GfxTextureStream 14, 8 tbb workers 8 each |
| Title with the fluid simulation (44–64 s) | 488 % | FluidCalculation 51, DrawThread 40, host 295974 39, host 295953 32, SceSndzAudioOut 26 |
| Level load (64–79 s, about 15 s) | 334 % | DrawThread 31, host 295953 30, host 295974 21, RoomLoad_ATQT 20, GfxTextureStream 19, SceSndzAudioOut 19, ProductNextLoad 10 |
| Play (79–150 s) | 747 % | DrawThread 48, host 295974 48, eleven tbb workers 41 each (450 together), host 295953 22; 76 other threads 182 together |

The thread count during play is 96 (90 of them used CPU in the window). The eleven
`tbb_thead` workers run at the same level, which is a work-stealing pool's shape, not
eleven independent loads. The video is decoded by one thread at a full core.

**Verdict.** Passed as a measurement; nothing is saturated. During the load no thread is
above a third of a core and the process uses about three cores of sixteen, so the load is
paced by waiting (file lookups and reads, GPU uploads, the game's own handshakes), not by
CPU; the next step there is to sample what the loading threads wait on, not to speed up
their code. During play the busiest threads (the game's DrawThread and one host thread) sit
at half a core each, so the CPU is not the frame-rate limit either; the GPU time per frame
(experiment 0025) and the game's thread handshakes (F69's 12 ms) remain the candidates.
Follow-up: name the host's own threads (the GPU submit and ring threads, the audio and
input threads) so the two host threads at 22–48 % can be told apart without a debugger.
