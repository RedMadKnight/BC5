# 0150 — What the second title waits for in its opening: the game thread runs, the audio streams, the animation stream stops after its first chunk

**Question.** F182: after New Game the opening keeps its first shot while its sound and subtitles
go on. What does the game thread wait for, and what does the title load during the stuck opening?

**Setup.**
- Offline first, no GPU run: the six stack samples of experiment 0136 (`~/bc5-work/cut-stacks.txt`
  on the box, private) and the title's code dump (`~/bc5-data/priv/eboot-text-900000000.bin`,
  `objdump -D -b binary --adjust-vma=0x900000000`); run 576's guest log for the
  `RenderThread::Sync` messages.
- Run 579, 2026-10-17 09:04, maintainer away (Claude over SSH): the play shortcut's settings with
  the guest log, `KYTY_BC5_SAVE_TRACE=1` and `KYTY_BC5_AMM_TRACE=1` (every APR submission, read
  and event on stderr, `~/bc5-work/run579-stderr.log`); scripted input: ✕ at 80 s, New Game 4
  (down ×3, ✕), challenge level ✕, "Before you start: New Game" ✕ at ~121 s; screenshots at
  +110, +130 ("30 YEARS AGO" caption over the forest) and +138 s; killed at +137 s, 16 s into the
  opening. APR file ids are the host's FNV-1a of the `/app0` path (`libAmpr.cpp`
  `ComputeFileId`), mapped back with a script over the mount's 309 paths.

**Result.**
- **The game thread is not stuck.** `game-main`'s only wait site in the samples is
  `PthreadCondTimedwait` from 0x903f39053: a loop that releases a recursive lock, waits 100 ms on
  the condition at 0x90beac130 and re-checks the render state at 0x90beac100 until it is 1; its
  debug string is `RenderThread::Sync`, the name in the title's own message `[RenderLayerDebug]
  RenderThread::Sync timed out after 100ms on RenderFrameIndex N`. That message appears 11 times
  in all of run 576 and twice around New Game: the wait normally returns within 100 ms, so the
  simulation ticks. The render state has writers for 0–6 in the render thread's loop
  (0x903f378e3 … 0x903f3947d).
- **No AIO.** The title never calls the `sceKernelAio*` functions; its "Loose Load EQueue" is fed by
  AMPR events (ids 0–3 registered at start). Run 579: 349 triggers of id 0, 149 of id 1, 3 of id 2,
  none of id 3; after New Game 24 of id 0 and 46 of id 1; no APR error of any kind.
- **New Game loads the opening's assets in ~4 s**: `zrt` 59.6 MiB, `model_boss` 43.1, `model_hero`
  39.9, `model_npc` 25.7, `model`, `material`, `model_char`, the character textures
  (`tex_char_boss`, `_npc`, `_shared`, `_jeangrey`, `_wolverine_a`, `_logan`, …), `tex_ui`,
  `userinterface`, `animsetclips` (0.2 MiB), `visualeffect`. **`animstrm` is read twice**
  (0x3f400 + 0x3ff00 bytes at +2.9 s) **and never again**; `cinematic2` (read 29 times before
  New Game, for the start screen) and `movie*` are not read after it.
- **During the stuck opening only audio streams**: one 128 KiB read every ~0.5 s from `wem_0`,
  `wem_1` and `wem.us` (Wwise), each followed by its event (id 1). Nothing else.

**Verdict.**
- **The opening is playing** (its audio streams at playback pace, the simulation thread ticks,
  the characters' models and textures are loaded) **but its animation stream stops after the
  first two chunks of `animstrm`.** An in-engine cinematic streams its animation continuously;
  here the streamer asks for no more. The characters that never appear and the camera that never
  moves fit a cinematic whose animation data stays at chunk 0.
- Next: why the streamer stops. Candidates: (a) the two `animstrm` chunks land in a buffer the
  game checks (a header or a chunk index) and the check fails: compare the bytes the host wrote
  with the package's file at those offsets, and the addresses with the AMM map; (b) the streamer
  waits on AMPR event id 2 or 3 (never or rarely triggered: find what the title's command buffers
  put in those events); (c) a `WaitAddress` command the host completes too early. All three are
  readable from the trace and the title's code around the `animstrm` reader, without a GPU run.
- `KYTY_BC5_AMM_TRACE=1` through New Game costs nothing visible (48,830 lines in 137 s) and is
  the tool for (a)–(c).
