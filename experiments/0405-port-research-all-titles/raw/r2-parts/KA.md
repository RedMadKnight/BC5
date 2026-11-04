# KA: KytyPS5 @ dfec14a vs OURS: audio and media libraries

## 1. Method

Diffed every shared file with `diff --strip-trailing-cr -w $R/kps5/src/libs/<f> OURS/libs/<f>` (audio.cpp/.h,
audio_internal.h, libAudio.cpp, libAudio2.cpp, ajm.cpp, ajm/{aac,atrac9,mp3,opus,ffmpeg_decoder_common}.h, avPlayer.cpp,
libVideoDec2.cpp, videoDec2Decoder.cpp/.h, libPngDec.cpp, libPngEnc.cpp, libFont.cpp, libFontFt.cpp) and read every
KytyPS5-only hunk. Files with other names were compared per function/NID: KytyPS5 acm.cpp and audio3d.cpp against our
audio.cpp:1617-1800 and 1802-2106 (diff of the extracted sections); KytyPS5 ngs2.cpp (2929 lines) against our Ngs2 in
audio.cpp:2108-3484 plus the 40 stubs in libNgs2.cpp; KytyPS5 ajm/decoder.h and ajm/resampler.h against the inline base
class in our ajm.cpp; libJpegDec/libJpegEnc against our libJpeg.cpp; libVdecsw.cpp (no counterpart). Commits read:
2944d12, b46eeb7, 05694ab, ba0e93d, c5f7644, 3583331, 64a554d, 7ff8aff, 2efd314, c528324, 8cfe1c4, a0b99a8, bc4333e,
67f8276, e66a7f5, 9bf311c, 2aa0d58, 08a7d7f, 2f6dccb, b65dd18, e0621a7, 4234458 (`git log dfec14a -- <files>` gives
only these after 4644c52; everything else is "pre-4644c52 (history not in clone)", confirmed per snippet with
`git log -S`). Provenance scan of all KytyPS5 files in scope (`grep -i sdk/sprx/disasm/firmware/decompil/ghidra/leak/
dump`) found nothing. Cross-checks: shadPS4 ref (`refs/shadps4-emu_shadPS4` @ 60c42b9) for the 8-channel STD order and
the AudioIn param enum; sharpemu has no AudioIn/NGS2 logic to compare. BC5 work checked before every claim: F247/exp
0188 AudioOut2 grain model (libAudio2.cpp:174-201, 550-711), exp 0372 pad route (audio.cpp:262-533), exp 0154 Opus on
libopus (ajm/opus_decoder.h), exp 0243 AT9 vibration (ajm/atrac9_decoder.h), exp 0329 Acm/PngEnc.

Linker note that matters for NGS2: `SymbolDatabase::UpdateName` strips the `libSce` prefix (loader/symbolDatabase.cpp:10),
so our libNgs2.cpp `LIB_VERSION("libSceNgs2"...)` and libAudio.cpp `LIB_VERSION("Ngs2"...)` are the same library;
Ngs2SystemGetInfo/Lock/Unlock/VoiceQueryInfo/VoiceGetPortInfo resolve to libNgs2.cpp's return-OK stubs (no out writes).

Side findings (not port rows): our libs/audio3d_impl.inc, libs/ngs2_pcm.h and libs/ngs2_vag_decoder.h are not included
by any file (dead code); ngs2_pcm.h:7 says its waveform-type values come from "psOff / SDK dumps" (provenance flag on
our own tree, should be checked by whoever owns it).

## 2. Table

All KytyPS5 sources are GPL-2.0. "replug" = the exp 0372 DualSense replug check is required before ship (audio path).
KytyPS5 paths are `src/libs/...` @ dfec14a; ours are under OURS/libs.

### A. Correctness fixes to functions we already have

| ID | What | Source | Licence | Ours | Effort | Risk | Class | Value note |
|---|---|---|---|---|---|---|---|---|
| KA01 | sceAudioOutOutputs: num 0 or > 32 returns AUDIO_OUT_ERROR_INVALID_SIZE | audio.cpp:995-997; pre-4644c52 (history not in clone) | GPL-2.0 | differs: audio.cpp:1498-1517 writes `params[i]` for i < num into a 32-entry stack array (stack overflow for num > 32); num 0 aborts in Audio::AudioOutOutputs (audio.cpp:1210) | S | L; replug | e4-now | crash/stack corruption to error code |
| KA02 | sceAudioOutOpen: freq 0 returns AUDIO_OUT_ERROR_INVALID_SAMPLE_FREQ | audio.cpp:870-872; pre-4644c52 | GPL-2.0 | differs: audio.cpp:1378-1423 accepts 0; audio.cpp:1215 then divides by freq (SIGFPE at the first output) | S | L; replug | e4-now | crash to error code |
| KA03 | Ngs2RackDestroy unlinks the rack (global racks mutex), calls the allocator free_handler, returns the context buffer | ngs2.cpp:1456-1528 (+ rack->buffer_info stored at 1377, g_racks_mutex 910); pre-4644c52 | GPL-2.0 | differs: audio.cpp:2958-2967 only zeroes buffer_info; the rack stays in g_racks_list, so Ngs2SystemRender (audio.cpp:3021-3060) keeps writing voice state into memory the title freed; allocator racks leak | S | M (NGS2 titles); replug | e4-now | use-after-free and heap corruption in any title that destroys a rack |
| KA04 | AJM control job with SIDEBAND_GAPLESS: parse the gapless sideband, set state->gapless, advance the sideband pointer before RESET/INITIALIZE | ajm.cpp:491-560 (gapless 511-520); pre-4644c52 | GPL-2.0 | differs: ajm.cpp:677-708 ignores the flag; with INITIALIZE the 8-byte gapless struct is passed to Initialize as codec parameters | S | M (AJM path of both titles); replug | e4-now | wrong decoder init / lost gapless trim |
| KA05 | AT9 RIFF header: accept the 'data' chunk before the chunk-size check (the job may hold only a prefix of the data) | ajm/atrac9_decoder.h:572-579; pre-4644c52 | GPL-2.0 | differs: ajm/atrac9_decoder.h:575-578 returns PARTIAL_INPUT when the data chunk extends past the job, so a RIFF stream fed in pieces never starts | S | L-M; replug | e4-now | AT9 RIFF streams that never start |
| KA06 | sceAudioInInput writes silence into dest when no device; dest == nullptr stops and returns 0 | audio.cpp:743-822 (memset 806); pre-4644c52 | GPL-2.0 | differs: audio.cpp:1333-1352 never writes dest (the title reads stale/garbage "mic" data); dest null aborts (audio.cpp:1587) | S | L; replug | e4-now | garbage capture data, abort |
| KA07 | sceAudioInOpen returns errors instead of aborting: type not 0/1 -> INVALID_TYPE, index != 0 -> INVALID_PARAM, freq 0 -> INVALID_FREQ, len 0 -> INVALID_SIZE | audio.cpp:1047-1058 (OpenPort); pre-4644c52 | GPL-2.0 | differs: audio.cpp:1556-1557 `EXIT_NOT_IMPLEMENTED(type != 1 / index != 0)` (type 0 kills the emulator); freq 0 later divides by zero (audio.cpp:1339) | S | L; replug | e4-now | abort to error code. Only the zero guards of KytyPS5's len/freq rule; its full sets are KA22 |
| KA08 | Ngs2VoiceGetState for custom mastering/sampler racks: state_size < configured -> 0x804a8011, else zero `configured_size` bytes and fill | ngs2.cpp:2795-2813; a0b99a8 2026-10-29 "ngs2: accept larger custom voice state buffers" | GPL-2.0 | differs: audio.cpp:3421-3430 `EXIT_NOT_IMPLEMENTED(state_size != configured_size)` for CustomMastering (abort on a larger buffer) | S | L | e4-now | abort to correct behaviour |
| KA09 | AJM AAC RAW (config 2): instance channel count is a limit; derive channels from the first raw packet (CPE -> 2) via AV_PKT_DATA_NEW_EXTRADATA; TOO_MANY_CHANNELS (0x40) when the stream exceeds the limit | ajm/aac_decoder.h:41-43, 97-101, 210-213, 298-316, 364, 371; ajm/decoder.h:82; pre-4644c52 | GPL-2.0 | differs: ajm/aac_decoder.h:191-210 builds the AudioSpecificConfig at open from the instance's max channels (an 8-ch instance decoding a stereo stream is configured as 7.1) | S | M (AJM decode path); replug | e4-now | wrong/failed decode of raw AAC |
| KA10 | sceAudioOut2PortSetAttributes validation: attributes null with num != 0 -> INVALID_PARAM; unknown port -> AUDIO_OUT2_ERROR_INVALID_PORT (0x80268009); duplicate attribute id or null value or PCM value_size < 8 -> INVALID_PARAM | libAudio2.cpp:803-848, 872-883; pre-4644c52 | GPL-2.0 | differs: libAudio2.cpp:816-841 aborts on null attributes, returns OK for unknown ports and ignores malformed PCM attributes | S | M (hot path of the second title's Wwise sink); replug | e4-now | abort to error; console-like errors |
| KA11 | AudioOut2 user handles tracked: UserCreate null -> INVALID_PARAM; UserDestroy unknown -> INVALID_PARAM, still used by a port -> AUDIO_OUT2_ERROR_BUSY (0x80268007); PortCreate with an unknown user -> INVALID_PARAM | libAudio2.cpp:172, 183, 235, 712-716, 735, 916-945; pre-4644c52 | GPL-2.0 | differs: libAudio2.cpp:874-888 (UserCreate aborts on null, UserDestroy always OK), PortCreate (713-797) ignores params->user_handle | S | M (PortCreate check could refuse a port a title opens with a stale handle: give it a switch); replug | e4-now | error codes; needed by KA33 |
| KA12 | AvPlayer NV12 output: fill the luma padding with 16 (0 for full range) and chroma with 128 instead of 0 | avPlayer.cpp:1556-1561; pre-4644c52 (comment: "PPSA02433 samples the padded columns; zero chroma would turn them green") | GPL-2.0 | differs: avPlayer.cpp:1519 memsets the whole frame to 0 | S | L (CPU copy into the guest buffer only) | e4-now | green right/bottom edge on movies whose width is below the pitch |
| KA13 | AvPlayer file-callback IO: mask AVSEEK_FORCE, overflow-safe seek arithmetic, EINVAL on bad whence, a callback returning more than asked is AVERROR(EIO), free the AVIO buffer when avio_alloc_context fails, 64 KiB AVIO buffer | avPlayer.cpp:607-616, 621-667; pre-4644c52 | GPL-2.0 | differs: avPlayer.cpp:581-620 (seek with AVSEEK_FORCE set returns -1; no read > len guard; 4 KiB buffer leaked on alloc failure) | S | L | e4-now | failed seeks in movies opened through file callbacks |
| KA14 | sceAjmBatchInitialize: buffer or info null -> AJM_ERROR_INVALID_PARAMETER | ajm.cpp:721-735; pre-4644c52 | GPL-2.0 | differs: ajm.cpp:876-890 EXIT_NOT_IMPLEMENTED | S | L | e4-now | abort to error (low) |
| KA15 | libFont: accept CFF OpenType ('OTTO') fonts for stb_truetype | libFont.cpp:733-742 (741); pre-4644c52 | GPL-2.0 | differs: libFont.cpp:742-749 accepts only 0x00010000/'true'; OTTO fonts fall back to the substitute font | S | L (needs stb_truetype with CFF: v1.26 per refs/Coder787-source_KytyPlus/3rdparty/stb; our 3rdparty not in the extracted tree, verify) | e4-now | correct glyphs for OTF titles |
| KA16 | AudioOut2 queue drain at an exact 48 kHz grain rate: 1/6-us ticks, one grain = num_grains*125 ticks, no 1000-us floor | libAudio2.cpp:277-280, 346-371, 558, 643; 7ff8aff 2026-10-27 "audio: drain the AudioOut2 queue at an exact 48 kHz grain rate" | GPL-2.0 | differs: libAudio2.cpp:353-380 uses integer microseconds (512 grains = 10666 us, 0.006 % fast) | S | L-M (exp 0188 advanced model reads the device queue, the timer is only its fallback); replug | e4-now | timing drift (low) |
| KA17 | AudioOut2 destroy vs in-flight push: per-context submission copy and mutex, ContextDestroy/PortDestroy wait for a running push before closing handles | libAudio2.cpp:223-232, 273-275, 437-473, 595-598, 794-797; b46eeb7 2026-10-21 "audio: stop AudioOut2 contexts from stalling each other (PPSA09809)" (+ pre-4644c52) | GPL-2.0 | differs: libAudio2.cpp:403-427 releases the port mutex and then reads `state.downmix` (a per-port vector PortDestroy can free) and closes handles without waiting (799-814) | M | M; replug | later | rare use-after-free on port/context destroy during a push |
| KA18 | AudioOut2 PCM ownership: PCM copied at SetAttributes; a push consumes it, a port not fed again falls silent | libAudio2.cpp:437-470, 872-882; 64a554d 2026-10-27 "audio: a pushed AudioOut2 grain consumes its ports' PCM" (copy pre-4644c52) | GPL-2.0 | differs: libAudio2.cpp:550-579 (Advance copies the port's last pointer every grain, exp 0188) and 403-427 (non-advanced push replays the pointer): a port the title stops feeding repeats its last buffer | M | H (exp 0188 tuned on the second title); replug | later | stale-buffer buzz on abandoned ports |
| KA19 | AudioOut2 per-context port tables: max_ports <= 32 channel ports, max_object_ports <= 512, guarantee <= max_object -> else INVALID_PARAM; PORT_FULL per partition; ContextResetParam defaults 8/0/0/1/256 | libAudio2.cpp:174-177, 196-207, 373-384, 486-503, 523-571, 717-731; 2efd314 2026-10-27 "audio: support 512 object ports per AudioOut2 context" | GPL-2.0 | differs: libAudio2.cpp:440-454 (defaults 256/256/0/4/512/1), 471-508 (no validation), one global 256-port table (234-235) | M | M (our ResetParam defaults fail KytyPS5's validation; the commit does not say where the new defaults come from); replug | later | per-context limits, PORT_FULL |
| KA20 | 8-channel speaker order: KytyPS5 swaps side/back for non-STD formats and drops the STD swap in SetVolume | audio.cpp:307-371 (SDL_8CH_MAP 334), 525-541; pre-4644c52 | GPL-2.0 | differs: audio.cpp:534-600 and 1176-1207 swap for STD formats, as shadPS4 does (refs/shadps4-emu_shadPS4 src/core/libraries/audio/audioout.cpp:52-68 @ 60c42b9) | S | M (two of three hosts disagree with KytyPS5); replug | later | verify on a 7.1 sink before porting either way |
| KA21 | AudioOut pacing: sample-exact OutputClock (remainder carried), 40 ms target latency, 200 ms stall clears the stream, primed/unprimed queue | audio.cpp:36-57, 373-429, 547-620; pre-4644c52 | GPL-2.0 | differs: audio.cpp:645-1019, 1209-1298 (BC5 pacing of exps 0174-0188 on SDL2/PipeWire) | M | H (box-tuned pacing); replug | later | only if our pacing shows drift again |
| KA22 | sceAudioInOpen full PS5 rules: len 128 (HQ) or 128/256, freq 48000 (HQ) or 48000/16000; param 1 = S16 mono, 2 = S16 stereo, 0x10/0x11 = float mono, 0x12 = float stereo, else INVALID_PARAM | audio.cpp:1053-1072; pre-4644c52 | GPL-2.0 | differs: audio.cpp:1559-1569 maps param 0 -> S16 mono (as shadPS4 PS4 enum S16Mono = 0, audioin.h:21), other values -> stereo | S | M (mapping conflicts with shadPS4's PS4 enum; unverified for PS5); replug | later | verify the PS5 enum first |
| KA23 | AvPlayer state machine Ready/Playing/Stopped: Pause/Resume return OPERATION_FAILED unless playing; STATE_STOP event on Stop only when playing; IsActive true while Ready | avPlayer.cpp:876-920, 1032-1037, 852-873; pre-4644c52 | GPL-2.0 | differs: avPlayer.cpp:836-882 (void Pause; `stopped` flag; KytyPlus natural-EOF STATE_STOP, 1687-1719) | M | M (CB4 boot-movie fix in ours) | later | API return codes |
| KA24 | AvPlayer looping: keep the original timestamp with a separate loop offset, raise LOOPING_BACK when the first looped frame is delivered, audio-clocked video via steady_clock from the first audio frame | avPlayer.cpp:1016-1019, 1022-1043, 1414, 975; pre-4644c52 | GPL-2.0 | differs: avPlayer.cpp:936-991, 1246, 1369 (warning at demux time; offset added to time_stamp; sync to last audio ts) | M | M | later | looped movie timing |
| KA25 | AvPlayer aspect_ratio = sample aspect ratio only | avPlayer.cpp:1428-1430; pre-4644c52 | GPL-2.0 | differs: avPlayer.cpp:1383-1392 reports display aspect (w/h*SAR) | S | M (which one the API means is unverified) | later | verify before porting |
| KA26 | AvPlayer StartWorkers/StopWorkers/FailPipeline under the source mutex | avPlayer.cpp:1212-1262; pre-4644c52 | GPL-2.0 | differs: avPlayer.cpp:1171-1215 (flags written unlocked) | S | L | later | data race |
| KA27 | libFont: em-based scale with separate horizontal/vertical scale; glyph images sized to the glyph (vector, up to 4096 px) | libFont.cpp:83-84, 213, 234, 807-861, 931-950, 1402; pre-4644c52 | GPL-2.0 | differs: libFont.cpp:798-881 (pixel-height scale clamped 8-128, fixed 128x128 image arrays, FONT_BITMAP_MAX_DIM 75) | M | M (text size/metrics change in every libFont title) | later | large text clipped at 128 px in ours |
| KA28 | PngEnc validation: this_size checked, image address and pitch 4-aligned, popcount(filter_type) <= max_filter_number, pitch*height <= image_mem_size | libPngEnc.cpp:128-148, 188-262; pre-4644c52 | GPL-2.0 | differs: libPngEnc.cpp:88-99, 283-309 (exp 0329, AnyPS5-based) | S | L (which side matches the console is unverified) | later | low |

### B. Missing functions or features with real behaviour

| ID | What | Source | Licence | Ours | Effort | Risk | Class | Value note |
|---|---|---|---|---|---|---|---|---|
| KA29 | sceAudioOutGetSystemState (R5hemoKKID8): null -> AUDIO_OUT_ERROR_INVALID_POINTER, else zero the 32-byte state, OK | audio.cpp:844-848, 961-972; libAudio.cpp:134; 2944d12 2026-10-21 "audio: implement sceAudioOutGetSystemState" | GPL-2.0 | missing (loader stub writes nothing) | S | L | e4-now | out-param written |
| KA30 | sceAudioInClose (Jh6WbHhnI68): free the port; invalid -> AUDIO_IN_ERROR_INVALID_HANDLE | audio.cpp:717-729, 1096-1103; libAudio.cpp:188; pre-4644c52 | GPL-2.0 | missing: ports never freed, the 9th open returns PORT_FULL | S | L; replug | e4-now | port leak |
| KA31 | sceAudioInGetSilentState (BohEAQ7DlUE): 0x1 (DEVICE_NONE) without a capture device; invalid handle -> INVALID_HANDLE | audio.cpp:38, 731-741, 1115-1125; libAudio.cpp:190; pre-4644c52 | GPL-2.0 | missing (stub returns 0 = "mic present") | S | L | e4-now | titles learn there is no mic |
| KA32 | sceAudioInHqOpen (nya-R5gDYhM): open an HQ port (len 128, 48000 Hz, else INVALID_SIZE/INVALID_FREQ) | audio.cpp:1038-1082, 1090-1094; libAudio.cpp:187; pre-4644c52 | GPL-2.0 | missing (stub returns 0, an invalid handle) | S | L; replug | e4-now | HQ voice-chat open |
| KA33 | sceAudioOut2UserGetSupportedAttributes (iE8trxPKnAg): null -> INVALID_PARAM, unknown user -> INVALID_PARAM, context_attributes = 0, port_attributes = supported attribute bits | libAudio2.cpp:947-963; libAudio.cpp:162; pre-4644c52 | GPL-2.0 | missing | S | L; replug | e4-now | report bit 0 (PCM) only until KA39/KA40 land |
| KA34 | Ngs2SystemGetInfo (vU7TQ62pItw), Ngs2SystemLock (gThZqM5PYlQ), Ngs2SystemUnlock (JXRC5n0RQls) with system handle lookup | ngs2.cpp:179-193, 327-335, 952-972, 1182-1221, 2060, 2901-2925; pre-4644c52 | GPL-2.0 | differs: libNgs2.cpp:120-163, 243-251 return OK and write nothing; no lock taken | S | L | e4-now | title-side locking around VoiceControl; info out-params |
| KA35 | JpegEnc (o6ZgXfFdWXQ QueryMemorySize, K+rocojkr-I Create, QbrU0cUghEM Encode, j1LyMdaM+C0 Delete) on stb_image_write | libJpegEnc.cpp:1-240; ba0e93d 2026-10-23 "libs: implement JpegDec and JpegEnc" | GPL-2.0 (stb: public domain/MIT) | differs: libJpeg.cpp:20-46 stubs return 0 (QueryMemorySize 0, Create writes no handle, Encode writes nothing) | S | L | e4-now | screenshots/share/upload thumbnails |
| KA36 | sceFontGetKerning (sDuhHGNhHvE) through stb_truetype kern tables | libFont.cpp:85-87, 128-135, 2058-2091, 2264; pre-4644c52 | GPL-2.0 | missing (stub writes nothing) | S | L | e4-now | kerning in libFont text |
| KA37 | NGS2 renderer: sampler voices decode PCM16 and ATRAC9 waveform blocks (streamed, dataless, CANCEL, CLEAR reopen), voice ports/matrices/patches (rack-handle patch -> voice 0), submixer, reverb dry path, mastering with full-band/LFE gain mixed into the output buffer's channel count, custom racks/user FX, ParseWaveformData (ATRAC9 RIFF), CalcWaveformBlock (ATRAC9 and 16-bit PCM) | ngs2.cpp:394-930, 1248-1284, 1560-2062, 2064-2241, 2366-2765; pre-4644c52 base + 05694ab 2026-10-22, 8cfe1c4 10-29, bc4333e 10-29 (Isaac: zeroed PCM blocks gave no audio), 67f8276, e66a7f5, 2aa0d58, 9bf311c, 08a7d7f, 2f6dccb, b65dd18 10-30, e0621a7, 4234458 11-01 | GPL-2.0 | differs: audio.cpp:2999-3066 zeroes the render buffers and only steps voice states; ParseWaveformData/CalcWaveformBlock return fake values (3068-3099) | L | M (new mixer; AT9 via LibAtrac9 + ours exp 0243); replug | later | every NGS2 title is silent in ours; tests/Ngs2SamplerTests.cpp in KytyPS5 |
| KA38 | Ngs2VoiceQueryInfo (9eic4AmjGVI, query 0x4001 setup channels) and Ngs2VoiceGetPortInfo (WCayTgob7-o, matrix/volume/dest) | ngs2.cpp:2857-2899; 9bf311c and 2aa0d58 2026-10-30 | GPL-2.0 | differs: libNgs2.cpp stubs (return OK, no writes) | S | L (needs KA37 voice state; KytyPS5 aborts on other query ids) | later | after KA37 |
| KA39 | AudioOut2 GAIN attribute: per-channel finite gains >= 0 (value_size = channels*4), applied in the AudioOut mix | libAudio2.cpp:851-864, 458-460; audio_internal.h:24; audio.cpp:307-371 (gains); pre-4644c52 | GPL-2.0 | missing (attribute ignored) | M | M; replug | later | per-port volume |
| KA40 | AudioOut2 object ports (type 0x100, mono 48 kHz): mixed centred into a per-context stereo stream; AMBISONICS attribute (W, first-order L/R cardioids); attributes locked until Advance | libAudio2.cpp:407-435, 437-470, 523-541, 704-709, 865-881, 615-626; pre-4644c52 + 2efd314 | GPL-2.0 | missing: object ports get no device (libAudio2.cpp:756-770), their PCM is dropped | M | M; replug | later | object audio silent in ours |
| KA41 | sceAudiodec M4AAC decodes through the AJM AAC decoder (AudiodecParamM4aacEx non-delay output, result codes -4/-5, API_FAIL) | libAudio.cpp:635, 666-668, 734-740, 757, 898-901, 981-1002, 1052-1074, 1099-1105; ajm/decoder.h (shared base); pre-4644c52 | GPL-2.0 | differs: libAudio.cpp:1005-1037 returns zeroed PCM for every codec | M | M; replug | later | Audiodec AAC titles silent |
| KA42 | AJM Opus resampler: INSTANCE_FLAG_RESAMPLE, CONTROL_RESAMPLE/RESAMPLE_EX sideband, linear-interpolation ratio 0-4 with per-sample change, resample info sideband | ajm/resampler.h:1-182; ajm.cpp:426-431, 529-557, 950-985, 1000; c528324 2026-10-28 "audio: let the AJM Opus decoder write part of a packet" | GPL-2.0 | differs: ajm.cpp:547-552, 1120, 1132, 1151 report ratio 1.0 and ignore the parameters | M | M; replug | later | pitch/speed-changed voices |
| KA43 | ATRAC9 discrete multichannel config (0x30): up to 64 mono streams, per-channel superframes interleaved | ajm/atrac9_decoder.h:24-81, 326-371, 381-435; pre-4644c52 | GPL-2.0 | missing: ajm/atrac9_decoder.h:289-336 rejects the config | M | M (needs a DMC test vector, none without Sony data); replug | later | multichannel AT9 |
| KA44 | AudioIn real capture through SDL (configured device, async HQ reads of up to 384 frames, device-loss fallback to silence) | audio.cpp:622-707, 743-822; pre-4644c52 | GPL-2.0 | missing (silence only) | M | M (SDL3 code; ours is SDL2); replug | later | voice chat |
| KA45 | JpegDec (uNAUmANZMEw QueryMemorySize, JPh3Zgg0Zwc Create, 1kzQRoWEgSA Decode, Hwh11+m5KoI Delete, LSinoSQH790 ParseHeader) on stb_image | libJpegDec.cpp:1-402; ba0e93d 2026-10-23 | GPL-2.0 | missing | M | L | later | CPU-testable (KytyPS5 tests/JpegDecTests.cpp) but 400 lines |
| KA46 | Vdecsw library (13 NIDs: +L5ArV1tPGA CreateDecoder, 0moTubWCsTM, 5Y6nZqIZvBg, A+2M7EivuOU, aqMiF0AgUYI, ecUtPX+dBYk, fX-zOOefbbs, hIgrg5h4V6s, ihNT-uuEAr4, kMBw37oH8nI, l4sQYy5wPkc, rgtMCOpyBSc, veb-YBrOqo0) over the FFmpeg H.264 decoder | libVdecsw.cpp:1-459; videoDec2Decoder.h:76-152; pre-4644c52 | GPL-2.0 | missing | M | L (CPU only; the "compute queue" is bookkeeping) | later | needs KA47 |
| KA47 | Videodec2 decoder: pending-frame queue (max_pending_frames >= 2), Submit/Receive/Finalize split, InputFull/NoFrame results, last_frame flag, picture info captured at receive | videoDec2Decoder.cpp:124-255, 370, 407-467; videoDec2Decoder.h:17-43, 76-152; pre-4644c52 | GPL-2.0 | differs: videoDec2Decoder.cpp:116-237 (one-frame pending, AccessUnit on a full decoder) | M | M (Videodec2 movies) | later | base of KA46 |
| KA48 | libFont fallback: ship Noto Sans Regular/Bold/Italic/BoldItalic (OFL) in assets/fonts next to the binary | libFont.cpp:701-730; CMake; 3583331 2026-10-26 "libFont: ship Noto Sans as the fallback font" | GPL-2.0 code; fonts SIL OFL 1.1 | differs: libFont.cpp:660-722 looks for Tracy's Roboto relative to the source tree or cwd (absent in installed builds: every glyph '?') | M | L (packaging change; FetchContent downloads at configure time) | later | system font sets on installed builds |
| KA49 | DualSense haptics/speaker stream for AudioOut pad/vibration ports including Bluetooth HID (Controller::DualSenseHaptics) | audio.cpp:465-471, 557-600 + dualSenseHaptics.cpp/dualSenseBluetooth.cpp; pre-4644c52 | GPL-2.0 | differs: ours routes pad ports to the controller's USB audio device (audio.cpp:342-533, exp 0372) with a rumble fallback; no Bluetooth haptics | L | H (exp 0372 route); replug | later | overlaps the controller scope; listed for completeness |

### C. Trivial

| ID | What | Source | Licence | Ours | Effort | Risk | Class | Value note |
|---|---|---|---|---|---|---|---|---|
| KA50 | Warn once when a title asks for VP9 and FFmpeg has no VP9 decoder (AvPlayer and Videodec2) | avPlayer.cpp:396-405; videoDec2Decoder.cpp:97-101; pre-4644c52 | GPL-2.0 | missing (log only) | S | L | later | diagnosability |
| KA51 | libavutil >= 61 build fix: avpriv_vga16_font_get() | libFont.cpp:43-48, 936-940; pre-4644c52 | GPL-2.0 | missing (only matters with FFmpeg 8) | S | L | later | build compat |

### D. Checked, nothing to port

| ID | What | Source | Licence | Ours | Effort | Risk | Class | Value note |
|---|---|---|---|---|---|---|---|---|
| KA52 | Audio3d (7 NIDs) | audio3d.cpp:1-319 | GPL-2.0 | audio.cpp:1802-2106 identical (whitespace-insensitive diff of the section) | - | - | skip: already match (audio.cpp:1802-2106) | audio3d_impl.inc is dead |
| KA53 | Acm (12 NIDs) incl. c5f7644 sceAcmBatchJobPriority (return OK, nothing recorded) | acm.cpp:98-103; c5f7644 2026-10-25 | GPL-2.0 | audio.cpp:1617-1800 identical except JobPriority, which ours records per batch and advances 16 bytes (exp 0329, audio.cpp:1711-1722) | - | - | skip: already match (audio.cpp:1617-1800) | ours does more |
| KA54 | c528324 Opus "write part of a packet" | ajm.cpp:426-431 + resampler.h | GPL-2.0 | ajm/opus_decoder.h:89-197 buffers the decoded packet and hands it out across jobs for every Opus job (exp 0154); KytyPS5 does it only in the resample path (KA42) | - | - | skip: already match (ajm/opus_decoder.h:110-124) | |
| KA55 | b46eeb7 push outside the state mutex | libAudio2.cpp:437-473 | GPL-2.0 | libAudio2.cpp:403-427, 637-646 already submit outside the mutexes | - | - | skip: already match (libAudio2.cpp:403-427) | residual race is KA17 |
| KA56 | 12-channel float output (7.1 + 4 heights) | audio.cpp:341-353; libAudio2.cpp:305-309 | GPL-2.0 | libAudio2.cpp:274-300, 305-307 BC5 downmix 12 -> 8 (heights -3 dB; KytyPS5 0 dB) | - | - | skip: already match (libAudio2.cpp:274-300) | |
| KA57 | PngDec (5 NIDs) | libPngDec.cpp | GPL-2.0 | identical | - | - | skip: already match (libPngDec.cpp:1-381) | |
| KA58 | FontFt (2 NIDs) | libFontFt.cpp | GPL-2.0 | identical | - | - | skip: already match (libFontFt.cpp:1-45) | |
| KA59 | AvPlayer without file callbacks reads the guest file through Common::File | avPlayer.cpp:590-605, 627-635 | GPL-2.0 | avPlayer.cpp:674-682 opens the real path with avformat_open_input (and strips file://) | - | - | skip: already match (avPlayer.cpp:674-682) | |
| KA60 | Videodec2 AvcPictureInfo moved into videoDec2Decoder (MakeAvcPictureInfo) | libVideoDec2.cpp:114, 542 | GPL-2.0 | libVideoDec2.cpp:114-176, 602-635 same fields and values | - | - | skip: already match (libVideoDec2.cpp:602-635) | |
| KA61 | KytyPS5 Opus Initialize rejects > 2 channels, mapping family != 0, rate != 48000 | ajm/opus_decoder.h:31-65 | GPL-2.0 | ajm/opus_decoder.h:42-77, 228-273 supports mapping family 1 up to 8 channels via libopus | - | - | skip: already match (ajm/opus_decoder.h:228-273) | ours is a superset |

## 3. Port specs for the e4-now rows

Common: library names below are as registered (`libSce` prefix is stripped by the linker). Every AudioOut/AudioOut2/
AudioIn/AJM/NGS2 item still needs the exp 0372 replug check before it ships. Per the 10-31 rule each fix gets a switch.
CPU tests can run without SDL: with no Audio subsystem `AudioInternal::AudioOutOpen` returns 0, so AudioOut2 ports open
without devices; `Libs::Audio::Audio` methods need the subsystem object but no device (SDL_AUDIODRIVER=dummy).

**KA01 sceAudioOutOutputs** (w3PdaSTSwGE, AudioOut). `int AudioOutOutputs(AudioOutOutputParam* param, uint32_t num)`.
After the null check add `if (num == 0 || num > Audio::OUT_PORTS_MAX) return AUDIO_OUT_ERROR_INVALID_SIZE;`
(0x80260006). Port KytyPS5 audio.cpp:995-997 into ours audio.cpp:1498-1517 (before the `params[]` loop). Test: open one
port (dummy driver), call with num 0 and 33: both return 0x80260006, no abort, stack canary intact.

**KA02 sceAudioOutOpen** (ekNvsT22rsY, AudioOut). After the port-type check add `if (freq == 0) return
AUDIO_OUT_ERROR_INVALID_SAMPLE_FREQ;` (0x80260008). Source audio.cpp:870-872; ours audio.cpp:1378-1423 (insert before 1392).
Test: AudioOutOpen(255, 0, 0, 256, 0, 1) returns 0x80260008 before g_audio is touched (works with no subsystem).

**KA03 Ngs2RackDestroy** (lCqD7oycmIM, Ngs2). `int Ngs2RackDestroy(uintptr_t rack, Ngs2ContextBufferInfo* out)`.
Behaviour: zero `*out` if given; rack 0 or not in g_racks_list -> 0x804a8202; under ngs->mutex and a new global
`g_racks_mutex` unlink it; take its stored buffer_info and allocator; if allocator.free_handler is set return
`free_handler(&buffer_info)`, else copy buffer_info to `*out`, return OK. Source ngs2.cpp:1456-1528 without the custom
module cleanup (lines 1503-1518; ours has no modules); store `rack->buffer_info = *buffer_info` in RackCreate
(KytyPS5 1377) and take g_racks_mutex where the list is linked (KytyPS5 1381) and walked (1973, render). Ours:
add `Ngs2ContextBufferInfo buffer_info` to Ngs2RackInternal (audio.cpp:2392-2398), link at audio.cpp:2877-2878,
render walk audio.cpp:3024, replace audio.cpp:2958-2967. Test: SystemCreate in a host buffer; RackCreateWithAllocator
with host sysv_abi alloc/free handlers counting calls; RackDestroy -> free called once with the same buffer, OK;
fill the freed buffer with 0xCC, call SystemRender, buffer unchanged; second RackDestroy -> 0x804a8202.

**KA04 AJM control job gapless** (7FZsbyVRM4U AjmBatchJobControl, Ajm). In `AjmControlInstance` (ours ajm.cpp:677-708)
before the RESET block insert KytyPS5 ajm.cpp:511-520: if `flags & AJM_FLAG_SIDEBAND_GAPLESS`: input null or shorter
than AJM_SIDEBAND_GAPLESS_SIZE -> result AJM_RESULT_INVALID_PARAMETER and return; `state->gapless.Set(input,
flags & AJM_FLAG_CONTROL_RESET)`; advance sideband_input/size by AJM_SIDEBAND_GAPLESS_SIZE. Constants exist in ours
(ajm.cpp:175, 182). Test: MP3 instance (FFmpeg MP3 decoder, CPU), control job flags SIDEBAND_GAPLESS with {total 1000,
skip 100} and sideband output GAPLESS: output echoes 1000/100; then INITIALIZE|SIDEBAND_GAPLESS on an Opus instance with
{gapless, opus init params} initializes with the init params (result OK, format 2 ch 48000).

**KA05 AT9 RIFF data chunk.** In `AjmAt9Decoder::ParseRiffHeader` (ours ajm/atrac9_decoder.h:571-613) move the 'data'
branch (607-613) above the size check (575-578), as KytyPS5 ajm/atrac9_decoder.h:572-583. Test: synthetic RIFF/WAVE with
a 52-byte fmt chunk (0xFFFE, AT9 GUID, a 4-byte config built from LibAtrac9's public layout) and a 'data' chunk whose size
is 4096 while the job holds 200 bytes: ParseRiffHeader returns true with data_offset = payload instead of PARTIAL_INPUT.

**KA06 sceAudioInInput** (LozEOU8+anM, AudioIn). `int AudioInInput(int handle, void* dest)`. Invalid handle ->
AUDIO_IN_ERROR_INVALID_HANDLE (unchanged); dest null -> return 0 without waiting (KytyPS5 stops the stream);
otherwise keep our block-time wait and `memset(dest, 0, samples_num * bytes_per_frame)` (2 for S16 mono, 4 for S16
stereo), return samples_num. Source audio.cpp:743-822 (silence 805-807, stop 808-811, return 822); ours export audio.cpp:1584-1596 (drop the
EXIT_NOT_IMPLEMENTED at 1587) and Audio::AudioInInput 1333-1352. Test: open a port, fill the buffer with 0xAA, input:
all zero, return 256; dest null returns 0.

**KA07 sceAudioInOpen errors** (5NE8Sjc7VC8, AudioIn). Replace audio.cpp:1556-1557 with `if (type != 0 && type != 1)
return AUDIO_IN_ERROR_INVALID_TYPE; if (index != 0) return AUDIO_IN_ERROR_INVALID_PARAM;` and add `if (len == 0)
return AUDIO_IN_ERROR_INVALID_SIZE; if (freq == 0) return AUDIO_IN_ERROR_INVALID_FREQ;` (subset of KytyPS5
audio.cpp:1047-1058; codes 0x80260104/0x80260106/0x80260102/0x80260103 already in errno.h:353-365). Test: type 0 opens a
port; type 2 -> 0x80260104; index 1 -> 0x80260106; freq 0 -> 0x80260103; no abort.

**KA08 Ngs2VoiceGetState custom racks** (-TOuuAQ-buE, Ngs2). In ours audio.cpp:3404-3465 replace the CustomMastering
case (3421-3430) with KytyPS5 ngs2.cpp:2795-2813 (a0b99a8): CustomMastering and CustomSampler read
`custom_rack_option.state_size`; `state_size < configured` -> 0x804a8011; memset `configured` bytes; mastering writes
state_flags; custom sampler writes state_flags (ours has no decode state; add Ngs2CustomSamplerVoiceState, 48 bytes,
KytyPS5 897-905, and fill flags only). Test: custom mastering rack (0x4003) with state_size 16; GetState with a 32-byte
buffer pre-filled 0xCC: OK, bytes 0-15 written, 16-31 unchanged; with 8 bytes -> 0x804a8011.

**KA09 AJM AAC RAW channels.** In ours ajm/aac_decoder.h: constructor takes `max_channels` (store m_max_channels, base
channels 0), Initialize resets channels and m_raw_configured and sets the sample rate from the index (KytyPS5 97-101);
remove the open-time extradata block (ours 191-210); on the first raw packet attach AV_PKT_DATA_NEW_EXTRADATA with
object type 2, the frequency index and channels = 2 if the first element is a CPE (`packet[0] >> 5 == 1`) else
clamp(max_channels, 1, 8) (KytyPS5 298-316); TOO_MANY_CHANNELS (add `AJM_RESULT_TOO_MANY_CHANNELS = 0x40`, KytyPS5
decoder.h:82) when the decoded frame has more channels than the limit (KytyPS5 210-213). Test: encode one stereo raw
AAC-LC frame with FFmpeg on the laptop (fixture), decode through an 8-channel AAC instance with config_number 2:
output 2 channels, 1024 samples, result OK; through a 1-channel instance: TOO_MANY_CHANNELS.

**KA10 sceAudioOut2PortSetAttributes** (8XTArSPyWHk, AudioOut2). `int AudioOut2PortSetAttributes(port, attrs, num)`.
Under g_audioout2_port_mutex: attrs null with num != 0 -> INVALID_PARAM (0x80268001); port not found ->
AUDIO_OUT2_ERROR_INVALID_PORT (0x80268009, add constant); loop: ids other than 0 (PCM), 1 (GAIN), 8 (AMBISONICS) are
skipped; a repeated id -> INVALID_PARAM; value null -> INVALID_PARAM; PCM with value_size < sizeof(AudioOut2Pcm) ->
INVALID_PARAM; GAIN/AMBISONICS accepted and ignored until KA39/KA40; store the PCM pointer as today. Source
libAudio2.cpp:803-848 and 872-883 (PCM part); ours libAudio2.cpp:816-841. Test (no devices): create user, context,
port; null attrs num 1 -> 0x80268001; bogus port -> 0x80268009; two PCM entries -> 0x80268001; valid PCM -> OK.

**KA11 AudioOut2 user handles** (xywYcRB7nbQ UserCreate, IaZXJ9M79uo UserDestroy, JK2wamZPzwM PortCreate; AudioOut2).
Keep a user list under a mutex (KytyPS5 libAudio2.cpp:235); UserCreate: null -> INVALID_PARAM, else next handle,
push (916-927); UserDestroy: not in list -> INVALID_PARAM, a used port with that user -> BUSY 0x80268007, else erase
(929-945); PortCreate: user not in list -> INVALID_PARAM (712-716) and store `port->user`. Ours libAudio2.cpp:874-888,
713-797 (AudioOut2PortParam.user_handle exists at 53). Test: PortCreate with handle 999 -> 0x80268001; UserDestroy while a
port exists -> 0x80268007; after PortDestroy -> OK; UserDestroy again -> 0x80268001.

**KA12 AvPlayer NV12 padding** (inside o3+RWnHViSg AvPlayerGetVideoData). Replace ours avPlayer.cpp:1519 with KytyPS5
avPlayer.cpp:1556-1561: luma bytes [0, pitch*h) = 0 if `codecpar->color_range == AVCOL_RANGE_JPEG` else 16; chroma
[pitch*h, pitch*h*3/2) = 128 (keep zeroing any tail beyond that if `size` is larger). Test: factor the copy into a helper;
an NV12 AVFrame 6x4 into pitch 16: columns 6-15 of every luma row are 16, chroma padding 128; full-range frame: luma 0.

**KA13 AvPlayer callback IO** (inside KMcEa+rHsIo AvPlayerAddSource). In FileStreamer (ours avPlayer.cpp:567-620):
Read returns AVERROR(EIO) when the callback returns more than `len` (KytyPS5 636-638; keep our AVERROR_EOF for 0); Seek
masks AVSEEK_FORCE, computes base+offset without overflow, EINVAL for unknown whence (KytyPS5 642-667; keep our clamp to
size); 64 KiB AVIO buffer and av_free on avio_alloc_context failure (607-616). Test: fake callbacks; read callback
returning len+1 -> AVERROR(EIO); Seek(100, SEEK_SET | AVSEEK_FORCE) -> 100; Seek(-1, SEEK_SET) -> negative.

**KA14 sceAjmBatchInitialize** (MmpF1XsQiHw, Ajm). Replace ours ajm.cpp:879-880 EXIT_NOT_IMPLEMENTED with `if (buffer
== nullptr || info == nullptr) return AJM_ERROR_INVALID_PARAMETER;` (KytyPS5 ajm.cpp:724-726). Test: null buffer ->
error code, no abort.

**KA15 libFont OTTO.** Add `(data[0]=='O' && data[1]=='T' && data[2]=='T' && data[3]=='O')` to ours libFont.cpp:747-748
(KytyPS5 libFont.cpp:741). Check our 3rdparty stb_truetype is >= 1.20 (CFF). Test: open an OFL CFF .otf from memory
(KXUpebrFk1U FontOpenFontMemory), render 'A': non-empty glyph bitmap from the font, not the fallback.

**KA16 AudioOut2 exact drain** (aII9h5nli9U ContextPush, R7d0F1g2qsU GetQueueLevel, PE2zHMqLSHs Advance). Add
`audioout2_clock() = KernelGetProcessTime() * 6`; in audioout2_update_context_locked use `grain = num_grains * 125`
ticks and `last_update += drained * grain`; set last_update with audioout2_clock() in ContextCreate and Push. Source
7ff8aff (libAudio2.cpp:277-280, 346-371, 558, 643); ours libAudio2.cpp:353-380, 497, 632 (audioout2_grain_micros stays
for the sleep). Test: factor the drain into a pure function of (queued, last_update, now); at 512 grains, 3600 s of
ticks drains exactly 337500 grains (the old 10666-us grain gives 337521).

**KA29 sceAudioOutGetSystemState** (R5hemoKKID8, AudioOut). `int AudioOutGetSystemState(AudioOutSystemState* s)`,
`struct {float loudness; uint8_t reserved8[4]; uint64_t reserved64[3];}` (32 bytes). Null -> AUDIO_OUT_ERROR_INVALID_POINTER
(0x80260004); else `*s = {}`; OK. Source audio.cpp:844-848, 961-972, audio.h decl, libAudio.cpp:134. Ours: struct and
function after AudioOutGetPortState (audio.cpp:1479), declare in audio.h, LIB_FUNC in libAudio.cpp:121-130. Test:
0xFF-filled struct comes back all zero; null -> 0x80260004.

**KA30 sceAudioInClose** (Jh6WbHhnI68, AudioIn). `int AudioInClose(int handle)`: handle <= 0 or not open ->
AUDIO_IN_ERROR_INVALID_HANDLE (0x80260101); else `port = {}` under m_mutex; OK. Source audio.cpp:717-729, 1096-1103.
Ours: Audio::AudioInClose next to AudioInValid (audio.cpp:1326), export after AudioInInput (1596), LIB_FUNC in
libAudio.cpp:178-181. (KytyPS5's BUSY while an input runs needs a busy flag; optional.) Test: open 8 ports, close one,
the 9th open succeeds; closing twice -> 0x80260101.

**KA31 sceAudioInGetSilentState** (BohEAQ7DlUE, AudioIn). `int AudioInGetSilentState(int handle)`: invalid ->
0x80260101; else 0x1 (AUDIO_IN_SILENT_STATE_DEVICE_NONE, KytyPS5 audio.cpp:38) because ours has no capture device.
Source audio.cpp:731-741, 1115-1125. Insertion as KA30. Test: open port -> 1; bad handle -> 0x80260101.

**KA32 sceAudioInHqOpen** (nya-R5gDYhM, AudioIn). Same signature as AudioInOpen; apply KA07 checks, then len != 128 ->
INVALID_SIZE, freq != 48000 -> INVALID_FREQ (KytyPS5 1053-1058 with asynchronous = true), then the AudioInOpen path
(KytyPS5 1090-1094). Insertion as KA30. Test: (len 128, 48000) returns a handle that KA06/KA30/KA31 accept; len 256 ->
0x80260102.

**KA33 sceAudioOut2UserGetSupportedAttributes** (iE8trxPKnAg, AudioOut2). `int (AudioOut2UserHandle h, uint32_t*
ctx_attrs, uint32_t* port_attrs)`: either pointer null -> INVALID_PARAM; h not in the KA11 list -> INVALID_PARAM;
`*ctx_attrs = 0; *port_attrs = 1u << 0` (PCM; add GAIN bit 1 and AMBISONICS bit 8 only with KA39/KA40). Source
libAudio2.cpp:947-963, libAudio.cpp:162. Ours after UserDestroy (libAudio2.cpp:888), declare in audio.h, LIB_FUNC in
libAudio.cpp:139-170. Test: valid user -> 0/1; unknown -> 0x80268001.

**KA34 Ngs2SystemGetInfo/Lock/Unlock** (vU7TQ62pItw, gThZqM5PYlQ, JXRC5n0RQls; Ngs2). Add `Ngs2FindSystem` over
g_ngs_list (KytyPS5 ngs2.cpp:965-972); Lock/Unlock: unknown handle -> 0x804a8201, else ngs->mutex.Lock()/Unlock()
(recursive Common::Mutex, so VoiceControl inside a lock is safe), OK (2901-2925). GetInfo(handle, info, size): info null
-> 0x804a8010; size != 184 -> 0x804a8011; unknown -> 0x804a8201; fill name, handle, buffer_info, uid, min grain 64, max
grain, state_flags 1, render_count, rack_count, sample_rate, num_grain_samples (1182-1221, struct 179-193). Ours: add
buffer_info, uid, render_count to Ngs2Internal (audio.cpp:2375), set them in Ngs2CreateSystemInternal, `++render_count`
in SystemRender; register in libAudio.cpp:1089-1116; delete the three stubs and their LIB_FUNCs from libNgs2.cpp
(120-163, 243, 245, 251) so only one record exists. Test: create system, GetInfo -> uid > 0, rack_count after one
RackCreate = 1, render_count increments per SystemRender; Lock on another thread blocks SystemRender until Unlock.

**KA35 JpegEnc** (o6ZgXfFdWXQ, K+rocojkr-I, QbrU0cUghEM, j1LyMdaM+C0; JpegEnc). Copy KytyPS5 libJpegEnc.cpp:1-240
(QueryMemorySize returns the context size 8 or a create-param error; Create validates this_size 8/attribute 0 and
writes a magic-tagged handle; Encode validates format/size/sampling, converts RGBA/BGRA/YUYV/Y8 and writes the JPEG
through stb_image_write, returns the byte count or DATA_OVERFLOW 0x80650110 and fills output_info; Delete clears the
magic) as a new file and delete ours libJpeg.cpp:20-46 (same NIDs). stb_image_write.h is in KytyPlus 3rdparty/stb
(refs/Coder787-source_KytyPlus); STBIWDEF static inline keeps the instance private. Test (model: KytyPS5
tests/JpegEncTests.cpp): encode a 16x16 RGBA gradient, decode with stb_image, mean error small; jpeg_mem_size 10 ->
0x80650110; bad handle -> 0x80650104.

**KA36 sceFontGetKerning** (sDuhHGNhHvE, Font). `int FontGetKerning(FontHandle, uint32_t pre_code, uint32_t code,
FontKerning* k)`, `FontKerning {float offset_x, offset_y, position_x, position_y}` (16 bytes): k null ->
0x80460002; zero k; handle null -> 0x80460005; pre_code 0 or no stb font -> OK; glyph ids (code with bit 31 = glyph
index) out of range -> 0x80460041; offset_x = stbtt_GetGlyphKernAdvance * scale. Source libFont.cpp:85-87, 128-135,
2058-2091, 2264. Use our `stb_font_scale(font)` (libFont.cpp:803) instead of KytyPS5's em scale so it matches our
metrics. Insertion: before LIB_DEFINE(InitFont_1) (libFont.cpp:2218). Test: Roboto/Noto TTF from memory, kerning of
'A','V' is negative; pre_code 0 -> OK and zero.

## 4. Totals

- Rows: 61. e4-now 24 (KA01-KA16, KA29-KA36), all S (~24 S, roughly 2-3 days with tests, many share a test harness).
- later 27: 8 S (KA20, KA22, KA25, KA26, KA28, KA38, KA50, KA51) + 17 M (KA17, KA18, KA19, KA21, KA23, KA24, KA27,
  KA39, KA40, KA41, KA42, KA43, KA44, KA45, KA46, KA47, KA48) + 2 L (KA37 NGS2 renderer, KA49 DualSense haptics)
  ~ 1 d + 9 d + 8 d ~ 18 days.
- skip: already match 10 (KA52-KA61). skip: provenance 0. in e4 / done 0 (none of the in-flight items is in this scope).
- Highest absolute value among "later": KA37 (every NGS2 title is silent on our host), then KA41/KA40/KA39.
