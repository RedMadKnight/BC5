# 0154 — The opening's frozen voice was the host's AJM Opus "decoder": a stub that returned silence; on libopus, with packets handed out across jobs, the opening plays

**Question.** F198: the opening's clock is `GetSourcePlayPosition(playingId 0x30)`, frozen at
4.949 s. What is that voice, why does it stop there, and what should follow it?

**Setup.**
- BC-250 dev box, 2026-10-17 14:50–16:55, maintainer away (Claude over SSH; runs 602–622 with
  the driver/watchdog pattern of experiment 0153, every run killed ≤ 24 s into the opening).
- Host journals added (KytyPlus patch): `KYTY_BC5_AJM_TRACE=1` prints every AJM initialize,
  set-gapless, get-gapless, clear-context and control job, and every split-decode job
  (instance, sizes, result codes, consumed, written, total samples, the gapless state, the
  first bytes of the input).
- gdb peeks (`drive6NN.sh`) of the cinematic's stream position (frames, 30 fps) and of the
  sync clock (`0x90ae007b4`) at +131/+137/+142 s; screenshots in run 622.
- Offline: the intro clip's WEM header read from the package (`wem_1` + 0x7c695739 − 0x830)
  and LibAtrac9 against the title's ATRAC9 data (`~/bc5-work/at9test`).

**Result.**
- **Voice 0x30 is a 10-second Wwise Opus loop** (HIRC node 0x33566fbe, media 0x3b835050,
  codec 0x3041 "Wwise Opus", mono 48 kHz, header `num_samples` 480,000, pre-skip 312, a seek
  table of 501 packet sizes; 93,893 bytes). The menu plays the same clip as voice id 1. The
  cinematic's sync clock wraps at 10.0 s (0x90bf72470, F198): the title counts the loops.
- **The host's AJM Opus decoder was a stub.** `ajm.cpp` carried its own `AjmOpusDecoder` that
  zeroes one 960-sample frame per job and reports the whole input consumed; the ffmpeg-based
  `libs/ajm/opus_decoder.h` is in the tree but was never included, and the bundled FFmpeg
  prebuilt (shadPS4's `ffmpeg-core`, `--enable-decoder=aac,…,mp3,…`) has no Opus decoder
  anyway (run 617: `avcodec_find_decoder` fails, every Opus initialize returns
  `CODEC_ERROR|FATAL`). The title's jobs carry two to four packets each, so the stub ate the
  clip in 248 jobs for 237,768 samples (4.95 s = half the loop) and the voice starved there.
- **The AJM Opus input is a run of packets each preceded by its size as a little-endian
  uint16** (the title prefixes the seek table's sizes: `03 01 | f8 b5 …` = 259 bytes, then
  `83 00`, `8e 00`, …). Every Opus instance of the title does this (the 4-channel menu music
  too, mapping family 1).
- **Wwise asks for 512 samples a job** (`out 1024` bytes for mono s16; the ATRAC9 voices show
  the same 512-sample frame: `out 2048` for their two channels), fewer than a 960-sample
  packet. A decoder that only takes whole packets (run 618: `NOT_ENOUGH_ROOM`, the title
  retries with `out 2048`) runs the voice at 0.43× real time. Handing a decoded packet out
  across jobs (run 619) runs it at real time: the clock reached 9.984 s ten seconds into the
  opening — and stuck there: after the last packet (consumed 315, written 1024, 256 samples
  of the 480,000 still in the decoder) the title submits no job to drain it, so the voice
  never ends and never loops.
- **The stream sideband counts decoded packets, not bytes handed out.** With
  `total_decoded_samples` and the gapless remainder advanced per packet decoded (run 621),
  the title ends the loop at its last packet, restarts it (`clear-context`, 2,605 jobs for
  0x60009 in 24 s), and **the opening plays**: clock 8.33 → 2.85 → 6.55 s (wrapping at 10),
  the animation stream at 22 → 172 → 288 frames (≈ 25–30 fps), the camera moving between the
  +130 and +134 s screenshots of run 622 (`raw/run62N-drive.log`).
- The title's **ATRAC9 streams all use channel configuration 7** (`fe 7e 03 f0`: 48 kHz, 32-byte
  frames); LibAtrac9 knows six configurations and decodes these at none (best run 5 frames
  over 60 variants). The opening's 0x400a is a 95-second one (4,562,432 samples), created
  when the intro loop ends; the menu's are 0.45 s and 28 ms. The host now decodes
  configurations 6–7 as silence instead of failing the voice (`atrac9_decoder.h`): the voice
  stays alive. Whether they are the DualSense haptic tracks (KytyPS5's "vibration layouts")
  or audio is open; the opening plays with them silent.

**Verdict.**
- F182 is explained and fixed in the emulator: `libs/ajm/opus_decoder.h` is now the AJM Opus
  decoder on libopus (`libopus-dev` in the `ubuntu` container, `find_library(opus)` in
  `src/CMakeLists.txt`, `KYTY_HAS_OPUS`): length-prefixed packets, mapping family 0 (≤ 2
  channels) and family 1 (RFC 7845 layouts, multistream), a decoded packet handed out across
  jobs, pre-skip and the sample limit applied per packet, the counters per packet. The stub
  in `ajm.cpp` is gone. Generic (no title knowledge in the host).
- Next: play the opening to its end with the maintainer at the pad (the 20-s kill rule
  stands until a longer run is known to be safe), listen to the audio (the Opus voices are
  audible for the first time; the ATRAC9 ones are silent), and find what channel
  configuration 7 is.
