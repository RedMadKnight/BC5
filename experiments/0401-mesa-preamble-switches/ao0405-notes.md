# Experiment 0401 series e5, tag `ao`: KytyPS5's AudioOut, AudioIn and Ngs2 fixes in `src/libs/audio.cpp`

Exp 0405's top-32 rows 16-18 (R2 KA01, KA02, KA03; `raw/r2-kyty-sharpemu.md` §5 ranks 12-14; `raw/r2-parts/KA.md`) and,
as extras, the R2 rows that live in the same file: KA06, KA07, KA08. KA04 (`ajm.cpp`) and KA05 (`ajm/atrac9_decoder.h`)
are not in `audio.cpp` and are not this tag's (held, see the end).

Source of every item: KytyPS5 (github.com/KytyPS5/KytyPS5), commit `dfec14aa8c59f8ea2bc4d87eba9854fc370161c6`, licence
GPL-2.0 (`LICENSE` of the clone). The extracted tree `scratchpad/0405/work/r2/kps5/src` equals `git show dfec14a:` for
`src/libs/audio.cpp` and `src/libs/ngs2.cpp` (md5 after CR removal: c525bc73…, a0481a83…). Exp 0405's provenance scan of
these files found no SDK/firmware/disassembly notes. `libs/ngs2_pcm.h` was not opened and nothing from it is used.

Input: the e5 tree's `src/libs/audio.cpp` (the base tree's unit, KytyPlus f266548 + patch 0001, with exp 0372's pad audio
route), md5 `f58ec0105874173a9f84954706a17e96`, LF, UTF-8 (3 non-ASCII characters, kept). Output md5
`230f732dbc20b9b196b28cb007ba95ec`. Line numbers "in" are the input's, "out" the output's. No header changed (`audio.h`,
`errno.h`, `libAudio.cpp`'s registrations untouched); all new state is inside `audio.cpp`.

## Switches

| Switch | Items | Journal line (stderr, once, at the Audio subsystem's init) |
|---|---|---|
| `KYTY_BC5_AUDIOOUT_CHECKS` | ka01, ka02 | `[bc5] exp 0405: audioout checks on (items: ka01 ka02)` / `[bc5] exp 0405: audioout checks off` |
| `KYTY_BC5_AUDIOIN_CHECKS` | ka06, ka07 | `[bc5] exp 0405: audioin checks on (items: ka06 ka07)` / `... off` |
| `KYTY_BC5_NGS2_RACK_FIX` | ka03, ka08 | `[bc5] exp 0405: ngs2 rack fix on (items: ka03 ka08)` / `... off` |

Value: unset, empty or `0` is off; a comma list of item names (`ka01`, `ka03,ka08`) turns on only those; any other value
turns on the group's items. Read once (function-local statics, out 266-282), printed at `KYTY_SUBSYSTEM_INIT(Audio)`
(out 338-341). Off is today's path: the old code is kept, each new branch tests its item's bit.

## Items

**KA01, sceAudioOutOutputs num 0 or > 32 — ported.** Source KytyPS5 `src/libs/audio.cpp:995-997`. Ours (in 1498-1517)
passed num 0 to `Audio::AudioOutOutputs`, whose `EXIT_NOT_IMPLEMENTED_MSG(num == 0, …)` (in 1210) ends the process, and
wrote `params[i]` for every i < num into `Audio::OutputParam params[32]` (a stack overflow for num > 32 with valid
handles). Out 1610-1614: with ka01 on, `num == 0 || num > 32` returns `AUDIO_OUT_ERROR_INVALID_SIZE` (0x80260006, our
`libs/errno.h:336`; shadPS4 60c42b9 `audioout_error.h:14` and KytyPS5 `errno.h:336` agree). Placed after the null check,
as KytyPS5.

**KA02, sceAudioOutOpen freq 0 — ported.** Source KytyPS5 `src/libs/audio.cpp:870-872`. Ours (in 1378-1423) opened the
port, and its first output divides by `freq` (in 1215, SIGFPE). Out 1495-1499: with ka02 on, freq 0 returns
`AUDIO_OUT_ERROR_INVALID_SAMPLE_FREQ` (0x80260008, `errno.h:338`; shadPS4 `audioout_error.h:16`) before
`EXIT_NOT_IMPLEMENTED(index != 0)`, as KytyPS5. Not covered (not KytyPS5's item): a freq-0 port opened through
`AudioInternal::AudioOutOpen` (AudioOut2, `libAudio2.cpp`, e4's file).

**KA03, Ngs2RackDestroy — ported, adapted.** Source KytyPS5 `src/libs/ngs2.cpp:1456-1528` (destroy), 1377 (the rack's
context buffer stored at create), 910 (`g_racks_mutex`), 1380-1384 (link under it), 1972-1983 (render walk under it).
Ours (in 2958-2967) only zeroed `*buffer_info`: the rack stayed in `g_racks_list`, `Ngs2SystemRender` (in 3024-3063) kept
writing its voices' state into memory the title had freed, and allocator racks were never given back. Out:
- 2652-2767 helpers: `BC5_NGS2_ERROR_INVALID_RACK_HANDLE` 0x804a8202 (KytyPS5 ngs2.cpp:1457), `g_bc5_racks_mutex`,
  `g_bc5_rack_buffers` (a map rack → its context buffer, instead of a new `Ngs2RackInternal` field, so that the rack's
  size and `Ngs2RackQueryBufferSize` stay as they are), `Bc5Ngs2RackDestroy` (2694): handle 0 or not linked → the error;
  unlink under the system's mutex then the racks' mutex (KytyPS5's lock order); then the allocator's `free_handler` gets
  the context buffer (its result returned), or without an allocator the buffer goes back in `*buffer_info`.
  KytyPS5's custom-module cleanup (1503-1518) not ported: our racks have no modules.
- 3132-3143 `Ngs2RackCreate`: with ka03 on, the link is done under `g_bc5_racks_mutex` and the buffer recorded.
- 3230-3232 `Ngs2RackDestroy`: after today's memset, ka03 on → `Bc5Ngs2RackDestroy`.
- 3292-3297, 3338-3340 `Ngs2SystemRender`: the walk under `g_bc5_racks_mutex` when on.
TODO(verify): 0x804a8202 is KytyPS5's PS5 value; shadPS4 60c42b9 `src/core/libraries/ngs2/ngs2_error.h:50` has the PS4
library's `ORBIS_NGS2_ERROR_INVALID_RACK_HANDLE = 0x804A0261`.

**KA06, sceAudioInInput — ported (extra).** Source KytyPS5 `src/libs/audio.cpp:747-749` (bad handle), 805-806 (silence
when there is no stream), 808-811 and 822 (a null dest stops and returns 0). Ours never wrote dest (in 1333-1352) and
exited on a null dest (in 1587, 1335). Out 1446-1451 (`Audio::AudioInInput`): with ka06 on, `samples_num` frames of
silence (2 bytes a frame for 16-bit mono, 4 for stereo, the only formats our AudioInOpen keeps). Out 1718-1724 (export):
a null dest returns 0 at once for a valid handle, `AUDIO_IN_ERROR_INVALID_HANDLE` (0x80260101, `errno.h:354`) otherwise.

**KA07, sceAudioInOpen errors — ported (extra).** Source KytyPS5 `src/libs/audio.cpp:1047-1058`, only the zero guards of
its len/freq rules (its full sets are exp 0405's KA22, "later"). Ours: `EXIT_NOT_IMPLEMENTED(type != 1 / index != 0)` (in
1556-1557), freq 0 later divides (in 1339). Out 1669-1687: with ka07 on, type not 0/1 → `AUDIO_IN_ERROR_INVALID_TYPE`,
index ≠ 0 → `INVALID_PARAM`, len 0 → `INVALID_SIZE`, freq 0 → `INVALID_FREQ` (0x80260104/06/02/03, `errno.h:355-359`;
shadPS4 `audioin_error.h:10` has INVALID_SIZE 0x80260102); type 0 opens a port. The one changed old line (in 1556 → out
1687): `EXIT_NOT_IMPLEMENTED(type != 1)` became `EXIT_NOT_IMPLEMENTED(!bc5_ka07 && type != 1)` (same with ka07 off).

**KA08, Ngs2VoiceGetState custom racks — ported (extra).** Source KytyPS5 `src/libs/ngs2.cpp:2795-2813` (a0b99a8, 2026-10-29
"ngs2: accept larger custom voice state buffers") and 897-905 (`Ngs2CustomSamplerVoiceState`, 48 bytes). Ours exited when
a custom mastering state buffer was not exactly the configured size (in 3421-3430), and gave a custom sampler voice the
plain sampler's 56-byte layout (envelope 1.0f at byte 8, where KytyPS5's custom layout has `waveform_data`). Out 2748-2766
(`Bc5Ngs2CustomVoiceState`) and 3692-3699: with ka08 on, a buffer smaller than the configured `state_size` returns
`BC5_NGS2_ERROR_STATE_SIZE` 0x804a8011 (KytyPS5 ngs2.cpp:2803), else `state_size` (configured) bytes are zeroed and
`state_flags` filled (ours has no decode state). A rack configured smaller than its state struct takes today's path
(KytyPS5 exits there; no new exit). TODO(verify): 0x804a8011 (shadPS4's PS4 `INVALID_OUT_SIZE` is 0x804A0054,
`ngs2_error.h:11`) and the custom sampler state layout (KytyPS5 is the only source).

## Script `mkao0405.py`

`mkao0405.py <tree root> <out dir>`: asserts the input md5, refuses a unit with any of its marks (`experiment 0405`, the
three switch names, `Bc5Ao`, `g_bc5_racks_mutex`), requires `src/bc5/pad_audio_route.hpp` (read only), checks every anchor
once and the definition order around the two blocks, keeps braces/parentheses/brackets balanced per edit, inserted text
ASCII, the lines with `exp 0372` the same (5 before, 5 after), counts each helper's uses, and undoes every edit to get the
input back byte for byte. Prints `src/libs/audio.cpp 230f732dbc20b9b196b28cb007ba95ec`.
Verified on the laptop (Python 3.14, also with `-I`): applies to the e5 tree; a second run on its own output is refused
(exit 1, "the unit has the edit already"); `diff` input/output: 14 hunks, all additions except the one KA07 line above;
balance of the output 0/0/0 (comments and strings removed) as the input's.

**Syntax (laptop, Visual Studio 18's clang++ 22.1.3, x86_64-pc-windows-msvc, `-fsyntax-only -std=c++20`), in the tree's
Windows configuration** as mem0405/svc0405: the stand-in `cmake_config.h` (`scratchpad/synchk/stub`), fmt from
`refs/Inori_GPCS4/3rdParty/fmt/include`, magic_enum and SDL2 headers from `refs/InoriRus_Kyty/source/3rdparty`, with
`-D_CRT_SECURE_NO_WARNINGS -D_SILENCE_ALL_CXX17_DEPRECATION_WARNINGS -Wno-deprecated-literal-operator` (Windows CRT/STL
and old-fmt noise) and a force-included `setenv` declaration (`scratchpad/ao-check/stub/ao_posix_standin.h`; the
Windows CRT has none).
- Output `audio.cpp` under `-Wall -Wextra -Werror`: 7 errors, all `-Wunused-parameter` in today's Acm functions (out
  1798-1831); the input has the same 7 (in 1660-1693). With `-Wno-unused-parameter` the output is clean. Under
  `-Wshadow -Wconversion -Wsign-conversion` the output has the same 11 warning kinds and counts as the input, none in the
  new lines.
- `ao0405.cpp` under `-Wall -Wextra -Werror` (with svc0405's stand-in `unistd.h`): first run found `std::aligned_alloc`
  missing (MSVC's STL has none; libstdc++ has it). Replaced by `::operator new(size, std::align_val_t {64},
  std::nothrow)` (portable C++17); now clean, also under `-Wshadow -Wpedantic`.
- Not checked: the Linux branches, GCC/clang on the box with libstdc++, the link, a run.

## CPU test `ao0405.cpp`

Built with `--gate ao0405.cpp <out> --like src/libs/audio.cpp`. Needs no sound device: `SDL_AUDIODRIVER` is set to a driver
that does not exist, so `SDL_InitSubSystem(SDL_INIT_AUDIO)` fails in `Audio::OpenSdlDevice` and AudioOut ports open without
a device (as e4's `aud0401.cpp`); AudioIn has no device code; Ngs2 is host memory. The Ngs2 allocator is the test's
(64-byte aligned `operator new`, never freed; its free handler records the call and keeps the memory so the canary can be read). Watchdog 120 s.
Cases (each expects its item's state; "off" also covers unset):
- AudioOut: port opens; ka02 freq 0 (on: 0x80260008; off: a port opens, closed again, its dividing output not run);
  ka01 num 0 and num 33 with valid handles (on: 0x80260006; off: skipped, today exits / overflows); num 33 with an invalid
  first handle (on 0x80260006, off 0x80260003 as today); num 1 and num 32 return 256 frames; close.
- AudioIn: type-1 port opens; ka07 type 0 opens, type 2/index 1/len 0/freq 0 errors (off: type 0/2/index 1 skipped, len 0
  and freq 0 open as today); ka06 input (on: 512 bytes zeroed, nothing past; off: dest unchanged); bad handle → 0x80260101;
  ka06 null dest (on: 0, and 0x80260101 with a bad handle; off: skipped, today exits).
- Ngs2: system and 256-voice sampler rack made with the allocator; destroy (on: free handler once with the rack's buffer,
  size and user data; off: not called); the voices filled with 0xCC, then a render (on: unchanged; off: changed, today's
  write into the destroyed rack); the whole buffer as a canary, then a render (on: unchanged; off: skipped, the walk would
  follow the canary as `next`); destroy again and handle 0 (on 0x804a8202, no second free; off OK); a rack in the
  title's own buffer returns that buffer (off: zeroed); ka08 custom mastering 16/32/8 bytes and custom sampler 56/40 bytes.
Expected: `ao0405: on 30 of 30; end`, `ao0405: off 20 of 20; end` (unset as off), 6 "skipped" lines when off.

## For the integrator

- Edit row: `ao mkao0405.py src/libs/audio.cpp:f58ec0105874173a9f84954706a17e96:230f732dbc20b9b196b28cb007ba95ec`
- Gate row: `ao0405.cpp src/libs/audio.cpp KYTY_BC5_AUDIOOUT_CHECKS,KYTY_BC5_AUDIOIN_CHECKS,KYTY_BC5_NGS2_RACK_FIX ao0405`
- Binary strings: the three switch names, `[bc5] exp 0405: `, `audioout checks`, `audioin checks`, `ngs2 rack fix`.
- **All six items change the audio unit: exp 0372's DualSense replug check (s6n0372.sh + replug0372.sh software check,
  then the physical replug and a DS4) must pass before the maintainer plays this build.** The integrator runs it.

## Risks

- Only syntax-checked on the laptop (Windows clang++, above); the box build is the first real compile, link and run
  (`-Wall -Wextra -Werror` for the test).
- KA03: the free handler (title code) is now called from `Ngs2RackDestroy` on the title's thread, outside our locks, as
  KytyPS5 does (our `Ngs2RackCreateWithAllocator` already calls the alloc handler directly). A second destroy now returns
  an error instead of OK. A title that destroys a system before its racks makes the rack destroy lock a mutex inside the
  system's memory (KytyPS5 has the same; our `Ngs2SystemDestroy` frees nothing).
- KA06: titles that read AudioIn now get silence instead of a stale buffer. KA07: type 0 opens instead of exiting.
- KA08: a custom sampler voice's state no longer has the plain sampler's fields (envelope 1.0f at byte 8).
- TODO(verify): the two Ngs2 error values and the custom sampler state layout (KytyPS5 only; shadPS4's PS4 values differ).

## Held

KA04 (AJM gapless sideband, `ajm.cpp`) and KA05 (AT9 RIFF data chunk, `ajm/atrac9_decoder.h`): not in `audio.cpp`.

## Files

| File | md5 |
|---|---|
| mkao0405.py | 15d1b602cdd1ee9357fc33365683c10f |
| ao0405.cpp | 1f684302953f70a71ef349bb93f02870 |
| input src/libs/audio.cpp (e5 tree) | f58ec0105874173a9f84954706a17e96 |
| output src/libs/audio.cpp | 230f732dbc20b9b196b28cb007ba95ec |
| src/bc5/pad_audio_route.hpp (read only) | 51131854822a629c2b24739e3603ef5d |
