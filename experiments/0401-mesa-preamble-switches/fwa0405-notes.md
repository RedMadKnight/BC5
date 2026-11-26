# fwa0405: exp 0405 decision-1 audio items (series e6 of exp 0401), notes

Tag `fwa`. Script `mkfwa0405.py <root> <out dir>`, CPU test `fwa0405.cpp`. Input: the e6 input tree (e5's sources).
Decision 1 of 2026-11-04 (the maintainer, relayed by the top session): values AnyPS5's authors took from firmware
modules **run** natively or under an emulator, or from their **readings** of modules, are accepted as another person's
description and ported. Held: rows whose note names SDK headers or an SDK layout, decrypted firmware, a disassembly
with addresses, an IDA database or a title's own libc.prx.

Source for every ported item: AnyPS5 (github.com/boykopovar/AnyPS5) at 4f41f4c375f5abb487dbd184fbc150f31994d762,
GPL-2.0-only, ported in adapted form (our names and structure; each inserted block cites commit and path:lines). Error
values are also cross-cited where a second GPL source has them: shadPS4 60c42b9 (GPL-2.0-or-later) and KytyPS5 4644c52
(GPL-2.0). No Sony material is used. `libs/ngs2_pcm.h`, `ngs2_vag_decoder.h` and `audio3d_impl.inc` were not opened or used.
`libs/libNgs2.cpp` and `libs/libVoice.cpp` were not edited.

## Switch

`KYTY_BC5_FW_AUDIO`. Default off, read once (`Bc5FwAudioItems()`, audio.cpp). Unset, empty or `0` is off. A comma list
of item names turns on only those items. Any other value, such as `1`, turns on all items.

- Items: `pcmloop`, `audio3d`, `audio3dstrict`, `ngs2`, `avplayer`.
- Journal line: one stderr line at the Audio subsystem's init (or at first use). It is
  `[bc5] exp 0405: fw audio on (items: pcmloop audio3d audio3dstrict ngs2 avplayer)` or `[bc5] exp 0405: fw audio off`.
  It uses e5's `Bc5AoRead`.
- Extra lines: while an item is on, the first 32 answers that differ from today's path each print one line,
  `[bc5] exp 0405 fw audio: <what> -> 0x<code>`, so that a refusal can be found in a play log.
- `avPlayer.cpp` declares `Libs::Audio::Bc5FwAudioItems()` itself, so no header changes.

Off is today's path. The old code stays and every new branch tests its item. In two places today's `EXIT_NOT_IMPLEMENTED`
condition gains `&& !(item on && ...)` (PortOpen size, PortPush blocking). With the item off, that condition is the same
as today's.

## Items, ranked by harm (crash, hang, wrong result, missing behaviour)

### 1. audio3d: ported (crash class)
- **Source.** 5f25ef8a9 "follow firmware 13.42 for the port, report and audio out calls". The code is AnyPS5 4f41f4c
  `core/libs/prx/libSceAudio3d/Export.cpp`: 156-169 (OpenPs5Port), 214-220, 306-318, 331-358, 377-385, 407-416 and
  453-470. The error values are shadPS4 60c42b9 `src/core/libraries/audio3d/audio3d_error.h:7-13`.
- **Upstream note.** "checks of firmware 13.42 libSceAudio3d.sprx (commit message; docs/dev/debt/libSceAudio3d.md:19)".
  The commit says "follow the checks of firmware 13.42's libSceAudio3d.sprx for a PS5 process". That is a reading of the
  module, so decision 1 applies.
- **What changed.** Where today's code exits, or divides by a zero queue depth later, the firmware's error is returned:
  - `Audio3dInitialize(reserved != 0)` returns INVALID_PARAMETER.
  - `Audio3dPortOpen` returns INVALID_PARAMETER for: a null params or id; a size that is neither 0x20 nor 0x28; a user
    that is not 255 or 1; `queue_depth` 0; `buffer_mode` not 2. With all four ports used it returns OUT_OF_RESOURCES.
    A size of 0x28 (num_beds) now opens as 0x20 does.
  - `Audio3dPortSetAttribute`, `PortGetQueueLevel`, `PortAdvance` and `PortPush`:
    - a bad port returns INVALID_PORT;
    - in SetAttribute, a null attribute, a float of the wrong size or an unknown id returns INVALID_PARAMETER. Height-aware
      (0x10003) is accepted at any size, because firmware 13.42 checks only its pointer.
    - in GetQueueLevel, both outputs null returns INVALID_PARAMETER.
  - **PortAdvance on a slot still playing** returns NOT_READY (the queue is full). Today this exits.
  - **PortPush(blocking 0)** pushes without waiting (asynchronous). Today this exits. Other blocking values still exit,
    because AnyPS5 throws for them.
- **Where (out audio.cpp).** Helpers at 2029-2145. Edits at 2190, 2215, 2282, 2320, 2369, 2386 and 2413.
- **Test cases.** About 16 cases with the item on. With it off, the cases run on today's path or are skipped.

### 2. audio3dstrict: ported (wrong-result class: today succeeds, firmware 13.42 refuses)
- **Source.** As item 1.
- **What changed.** Each of these returns the firmware's error where today's code succeeds:
  - `PortOpen` before `Audio3dInitialize` returns NOT_READY.
  - `PortOpen` with user_id 1 returns INVALID_PARAMETER.
  - `PortOpen` returns INVALID_PARAMETER for any of: rate not 0, granularity under 256 or not a multiple of 256,
    `max_objects` 0.
  - A second port returns OUT_OF_RESOURCES (firmware 13.42 has one port, id 0).
  - Port ids other than 0 return INVALID_PORT.
  - `SetAttribute` checks value ranges: late reverb 0..1, spread radius 0.1..2, finite. Otherwise INVALID_PARAMETER.
  - `PortAdvance` on a slot advanced but not pushed (the queue is full) returns NOT_READY.
- **Why a separate item.** These turn today's successes into errors. Kyty accepted user_id 1 on purpose, so a title that
  passes it would lose Audio3d with this item on. Item 1 can stay on without this one.
- **Test cases.** 6 with the item on: before-init, user 1 and rate 1, the second port, the attribute range trio, and the
  third advance.
- **Not testable.** The port-id-not-0 rule cannot be tested: with the item on, no port other than 0 can be opened.

### 3. pcmloop: ported (R1 #40; wrong result)
- **Source.** 9d1a9c82e "parse looped PCM waveforms" and 403956973 "follow the module's PCM loop rules". The code is AnyPS5
  4f41f4c `core/libs/prx/libSceNgs2.native/src/Atrac9.cpp`: 288-321 (ReadChunks), 380-401 (AddPcmBlock, ParsePcmLoop),
  403-436 (ParsePcm), 438-452 and 459-468. The error values are KytyPS5 4644c52 `src/libs/ngs2.cpp:39-44`.
- **Upstream note.** R1 §1 row 40: "the source (prosper's reading of the module) needs a provenance call". The AnyPS5
  debt entry ("NGS2 PCM waveform parsing") cites prosper's reading of `libSceNgs2.native.sprx`:
  prosper 40d95db `prosper/src/hle/audio/ngs2_waveform.cpp:194-343`. Decision 1 accepts it. Not measured on a console.
- **What changed.** Today's `Ngs2ParseWaveformData` is a stub: it returns type 0x80, mono, 48 kHz and no samples for any
  data. With the item on, RIFF/WAVE PCM is parsed. That covers tag 1, tag 3 (float), and EXTENSIBLE with the PCM GUID.
  - **Types.** 8, 16, 24 and 32-bit integer are 0x11, 0x12, 0x14 and 0x16. Float 32 and 64 are 0x18 and 0x1a. Any
    other depth gives UNKNOWN_WAVEFORM_FORMAT.
  - **Other fields filled.** Channels, rate, data offset and size, `num_samples`, unit and frame sizes, and block 0.
  - **INVALID_WAVEFORM_FORMAT** for any of: 0 or more than 8 channels, a rate of 0 or above 192000, or a block align
    that is not channels × bytes.
  - **INVALID_WAVEFORM_DATA** for any of: a chunk past the RIFF end, data not in whole frames, or data past the buffer.
  - **The smpl loop rules (403956973).** Only the first loop's start and its inclusive end are read. The waveform is
    split into blocks: before the loop, the loop with `num_repeats = UINT32_MAX` (forever, whatever the play count),
    and after the loop. An end that is not after the start keeps one block, with the positions as read.
  - **Where AnyPS5 throws.** These cases are not modelled: a smpl chunk under 32 or under 52 bytes, and a loop ending
    past the last sample. Here they are kept as one block without a loop, with a journal line. TODO(verify).
  - **Other data keeps today's stub answer.** That covers ATRAC9, VAG, non-RIFF data and other tags. Our renderer is
    silent, so what this changes is what the title reads back.
- **Where (out audio.cpp).** Helpers at 3099-3307. The edit is at 3821.
- **Test cases.** 13 on and 5 off. A laptop stand-in run passed 13 of 13 on and 5 of 5 off; see Verification.

### 4. avplayer: ported (wrong result: a movie quad's size)
- **Source.** 0b41d81e2 "follow the firmware sample aspect ratio fallbacks", on top of 5fdc6dbd4. 5fdc6dbd4 is R1 #21,
  never ported, and 0b41d81e2 supersedes it. The code is AnyPS5 4f41f4c `core/libs/prx/libSceAvPlayer/src/Source.cpp`
  (HasAspect, SampleAspect, the stream info at 637-641 and the frame info at 1072-1076).
- **Upstream note.** "BunnyFl 13.42 reading and emulator run (docs/dev/debt/libSceAvPlayer.md)". The debt entry reads:
  "emulator execution and code reading, H.264 only, no console run".
- **What changed.** With the item on:
  - the stream info's `aspect_ratio` is the stream's (codecpar) sample aspect ratio;
  - a frame's `aspect_ratio` is the picture's sample aspect ratio, falling back to the stream's;
  - both are 0.0 when no ratio is given.
  Today both are width / height × the stream's SAR.
- **Where (out avPlayer.cpp).** The helper `Bc5FwAvPlayerSar` is at 37-72 (external linkage, for the test). The edits
  are at 1417 (`Aspect`) and 1569 (`PrepareVideo`). CRLF is kept.
- **Risk.** FFmpeg reports 0/1 both for an H.264 `aspect_ratio_idc` of 0 (1.0 on the console) and for a stream with no
  aspect information (0.0 on the console). So a title can get 0.0 where the console gives 1.0. A title that multiplies
  by it would then draw an empty quad. TODO(verify) with a title movie before keeping it on.
- **Test cases.** 2: the helper's six values, and the item state. The call sites need a video file. They are covered only
  by the script's anchors; no clip is generated.

### 5. ngs2: ported (wrong result: accepts an invalid rack)
- **Source.** 9c009622b "reject sampler racks outside 1 to 32 waveform blocks". AnyPS5's `Rack.cpp` CheckedRackOption.
- **Upstream note.** "PS5/PS4 Ngs2 module runs (rack block limit)". The commit and its debt entry name the PS5 firmware
  3.20 and 4.03 module run on a PC. Decision 1 applies.
- **What changed.** A sampler (0x1000) or custom sampler (0x4001) rack whose `max_waveform_blocks` is 0 or above 32 now
  returns 0x804A8053. This applies in `Ngs2RackQueryBufferSize`, `RackCreate` and `RackCreateWithAllocator`. An option
  too short to hold the field keeps today's path. Defaults (4 blocks) pass.
- **Where (out audio.cpp).** Helper at 3070-3098 (`Bc5Ngs2RackBlocks` at 3079). Edits at 3416, 3522 and 3643.
- **TODO(verify).** The order of this check against the voice and channel checks was not run on the module.
- **Test cases.** 5, both on and off.

## Every `excluded-provenance` row of the libraries in scope (exp 0405 `raw\r1-verdicts\*.tsv`), with its note

AudioOut has no such row. AvPlayer.native has none.

| Lib | Commit | Note (quoted) | Verdict |
|---|---|---|---|
| Audio3d | 5f25ef8a9 | "checks of firmware 13.42 libSceAudio3d.sprx (commit message; docs/dev/debt/libSceAudio3d.md:19)" | **ported** for our 7 functions: items audio3d and audio3dstrict. Held: its new exports (PortOpenEx, PortDestroy, PortGetStatus, Report(Un)RegisterHandler, Object*, Bed*, AudioOut*), which are not registered by us. That is R1 #39's Audio3d group, size M (~1 d), later. |
| Audio3d | 96aa06c34 | same | **already match**: the PS4-process branch. Our host runs PS5 processes only: there is no `IsPs4Process` anywhere in `src/` (grep, 0 hits). The PS5 branch is what item 1 ports. |
| Audio3d | 7f4526471 | same | **already match** for the PS4 and PS5 choice (as above). Its report and AudioOutOutputs parts are **held** with the new exports (not registered by us). |
| Audio3d | f4d2d4446 | same | **already match**: PortOpenEx in a PS4 process. We register no PortOpenEx, and the process is never PS4. |
| Ngs2.native | 9c009622b | "PS5/PS4 Ngs2 module runs (rack block limit); our Ngs2 renders silence (audio.cpp:2999)" | **ported**: item ngs2 |
| Ngs2.native | 06a481b20 | "fma-rc 12.70 Ngs2 module reading; our Ngs2 renders silence (audio.cpp:2999)" | **already match** for creation: RackCreate 0x4001 takes any module list (out audio.cpp:3583). Its Gain processing and the INVALID_PARAM_ID bounds are **held**: they need the renderer and a custom-module param model (L). |
| Ngs2.native | f0ed4cb81 | "filter-during-render rule from PS4/PS5 Ngs2 modules run on a PC (debt); our Ngs2 renders silence (audio.cpp:2999)" | **held: needs the renderer**. Our `Ngs2SystemRender` only zeroes the buffers (out audio.cpp:3756), and `Ngs2VoiceControl` stores no sampler param (out :4105). Batch with the renderer, size L. |
| Ngs2.native | 164246490 | "PS5 fw 3.20/4.03 Ngs2 module runs on a PC (debt libSceNgs2.native.md); our Ngs2 renders silence (audio.cpp:2999)" | **held: needs the renderer** (waveform blocks are not queued anywhere), L |
| Ngs2.native | 7ef0533d0 | "PS4 11.00 Ngs2 module run on a PC; our Ngs2 renders silence (audio.cpp:2999)" | **held: needs the renderer** (filter params are not stored), L |
| Ngs2.native, Ngs2 | d44c0739b | "PS4 11.00 Ngs2 module run on a PC; our Ngs2 renders silence (audio.cpp:2999)" | **held: needs the renderer** (port volume is not stored; PS4 library), L |
| Ngs2.native | f8ce8aade | "names PC runs of PS4/PS5 Ngs2 modules (ngs2-oracle) as its source; our Ngs2 renders silence (audio.cpp:2999)" | **held: needs the renderer**, L |
| Ngs2.native | 52be0d5b2 | "SDK layout plus PS5 Ngs2 module runs on a PC; our Ngs2 renders silence (audio.cpp:2999)" | **held: provenance** (it names an SDK layout) |
| Ngs2.native, Ngs2 | 107954e35 | "PS5 fw 3.20/4.03 default map rows from module runs; our Ngs2 renders silence (audio.cpp:2999)" | **held: needs the renderer** (no mixing), L |
| Ngs2.native, Ngs2 | e9c806980 | "PS5 fw 3.20/4.03 default map rows from module runs; our Ngs2 renders silence (audio.cpp:2999)" | **held: needs the renderer**, L |
| Ngs2.native, Ngs2 | 2efc86f68 | "decrypted firmware 11.00 libSceNgs2 (commit message); our Ngs2 renders silence (audio.cpp:2999)" | **held: provenance** (decrypted firmware) |
| Ngs2.native | 8ae66c36b | "PS5 fw 3.20/4.03 PCM_I16L conversion from module runs; our Ngs2 renders silence (audio.cpp:2999)" | **held: needs the renderer**. Silence is 0 in every format, so today's memset already gives the right bytes; the conversion itself waits for real samples. S once there is a renderer. |
| Ngs2.native | 0dc600e7f | "PS5 fw 3.20/4.03 port volume clamp from module runs; our Ngs2 renders silence (audio.cpp:2999)" | **held: needs the renderer** (port volume is not stored; VoiceControl 0x2 only logs, out :4038-4046), S once stored |
| Ngs2.native | 022c609f9 | "Reverb checked against 3.20/13.60 module DSP and voice graph; our Ngs2 renders silence (audio.cpp:2999)" | **held: needs the renderer** (custom Reverb DSP), L |
| Audiodec, Audiodec.native | 91999d11d | "13.42 run of libSceAudiodec.native under an emulator (docs/dev/debt/libSceAudiodec.native.md)" | **already match**: our `Audiodec` table registers neither GetAjmContext nor UnregisterCodec (`libs/libAudio.cpp:1054-1061`, input md5 45ca1ece…). The native module's own exports are held with 8f941d036. |
| Audiodec | 8f941d036 | "firmware 13.42 run of libSceAudiodec.native under an emulator (commit message, debt)" | **held: new export of a table we do not register**. That is `libSceAudiodec.native`'s `sceAudiodecGetAjmContext(context, ajmi, ajm)`. Our Audiodec has no `sceAudiodecInitialize` context with Ajm ids. Size S-M; it needs a decision on registering a `.native` library name. |
| AvPlayer | 0b41d81e2 | "BunnyFl 13.42 reading and emulator run (docs/dev/debt/libSceAvPlayer.md)" | **ported**: item avplayer (with 5fdc6dbd4's base) |

"Needs the renderer" is not a skip. These rows are portable under decision 1, but they change what a sampler or mixer
does with samples, and ours makes none. They belong with a renderer batch, together about 3-5 days. The dead
`libNgs2.cpp` and `libVoice.cpp` tables are held: "dead table, later batch".

## Verification on the laptop

- **The script.** It applies to the e6 input tree. Inputs: audio.cpp 230f732d…, avPlayer.cpp 966cb8a8…. It prints
  `src/libs/audio.cpp 1f90e7520a6641c8ff3affb06993372d` and `src/libs/avPlayer.cpp 44203af3c14874fee232808fc4aa6568`.
  - It is deterministic: two runs gave equal bytes.
  - It refuses an already-edited audio.cpp or avPlayer.cpp: "the unit has the edit already".
  - Undoing every edit gives each input back byte for byte; this is asserted inside the script.
  - Braces, parentheses and brackets balance per edit and per unit.
  - The 5 `exp 0372` lines are unchanged.
  - avPlayer.cpp's 47 LF-only lines stay LF; the inserted lines are CRLF like their neighbours.
- **Syntax.** Visual Studio 18 clang++ 22, msvc target, `-fsyntax-only -std=c++20 -Wall -Wextra -Werror`. The stand-in
  `cmake_config.h`, fmt and SDL2 headers are e5's, from ao0405-notes.md.
  - Output audio.cpp: only the input's own 7 `-Wunused-parameter` errors (today's Acm functions). With
    `-Wno-unused-parameter` it is clean.
  - Under `-Wshadow -Wconversion -Wsign-conversion`, the warning kinds and counts are identical to the input's.
  - `fwa0405.cpp`: clean, also under `-Wshadow -Wpedantic`. It uses lib0405chk's stand-in `unistd.h` and e5's setenv
    stand-in.
  - avPlayer.cpp: there are no FFmpeg headers on the laptop. Block D, `Aspect` and the `PrepareVideo` edit were checked
    in an extract with a stand-in `AVRational`/`av_q2d`. It is clean, also under `-Wshadow -Wconversion`.
- **Stand-in run (pcmloop only).**
  - **Build.** The output unit's Ngs2 structs, block C and the edited `Ngs2ParseWaveformData` were linked with the test's
    PCM cases (generator `scratchpad\e6\wk\fwa\gen.py`).
  - **Result.** It passed 13 of 13 on and 5 of 5 off.
- **Not checked on the laptop.**
  - The Linux compile, the link and a run of the whole test.
  - Audio3d: kernel semaphores and threads.
  - The racks.
  - AvPlayer with a real stream.

## The CPU test

- **Build.** `build0401.py ... src/libs/audio.cpp=<out>/src/libs/audio.cpp src/libs/avPlayer.cpp=<out>/src/libs/avPlayer.cpp --gate fwa0405.cpp <dir>/fwa0405 --like src/libs/audio.cpp`.
- **Run.** `KYTY_BC5_FW_AUDIO=1 fwa0405 on`, `=0 ... off`, unset `... off`, each in a fresh directory.
- **Expected counts.** `=1`: **50 of 50**. `=0` and unset: **28 of 28**. A comma list runs each item's own cases.
- **What it needs.** No game, GPU, window, network or sound device: SDL_AUDIODRIVER names a driver that does not exist.
  Audio3d's playback threads only sleep. A 120 s watchdog prints a FAIL line and exits 3.
- **Timing.** The Audio3d cases need about 1.5 s. Granularity 48×256 gives 256 ms a frame, so that "push without
  waiting" and "advance while playing" are not racy.

## Risks

- **audio3dstrict can break a title that works today.** For example, a title that passes user_id 1, opens two ports, or
  opens before Initialize. Turn it on only to test it.
- **audio3d gives a title an error where today it exits.** The title's error path then runs instead of the process ending.
- **PortPush(0) has no exact firmware model.** It signals the playback simulation and returns at once; AnyPS5's
  queue-depth target is not modelled.
- **pcmloop changes what a title reads back for PCM waveforms.** Today every waveform reads back as type 0x80 with 0
  samples; now real values. A title that sizes buffers from `num_samples` or `data_size` sees different numbers. The
  renderer stays silent.
- **avplayer can report 0.0** for FFmpeg's 0/1 (see item 4).
- **The DualSense replug check.** Every item here is audio. Before a play with any item on, exp 0372's replug check is
  needed: `s6n0372.sh` + `replug0372.sh`, then the physical replug and a DS4. The default-off path is today's bytes, but
  the unit changed, so the check still applies.

## Files

| File | md5 |
|---|---|
| mkfwa0405.py | 311acaa8e5f62216cdb44cb9fa19bf84 |
| fwa0405.cpp | 62a851d8930a30952072e9738191f9fa |
| in src/libs/audio.cpp (e5) | 230f732dbc20b9b196b28cb007ba95ec |
| out src/libs/audio.cpp | 1f90e7520a6641c8ff3affb06993372d |
| in src/libs/avPlayer.cpp (base) | 966cb8a847467b64ce0486168f052a82 |
| out src/libs/avPlayer.cpp | 44203af3c14874fee232808fc4aa6568 |
| read only: src/libs/libAudio.cpp (base) | 45ca1ece07c4394d8700f7a57d9f0fbb |
| read only: src/libs/libAudio2.cpp (e4) | 7a1914c898e62e1e6ce699807aafbc74 |
| read only: src/libs/audio.h | 329232012b9493aa80aa0f69203fd278 |
| not edited (dead tables): src/libs/libNgs2.cpp, libVoice.cpp | 0d5c481044b82d910893193daa9d7b9f, 5f63709dbf1028ceaf7784d6a070f64e |
