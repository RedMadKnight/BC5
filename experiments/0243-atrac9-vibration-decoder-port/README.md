# 0243 — The second title's DualSense haptic tracks: vgmstream's ATRAC9 decoder in the host

**Question.** Exp 0241 (F300) showed two things about the second title's ATRAC9 streams in channel configurations
6–7. They are the DualSense's haptic tracks, and vgmstream's decoder (`7c520e8`, ISC) decodes every complete one.
The host played them as silence (F200), because LibAtrac9 does not know these configurations. Can the host decode
them with vgmstream's decoder, behind a switch, and does the title still run as before? The maintainer approved
porting the decoder on 2026-10-23.

**Setup.** Top session, 2026-10-23 19:24–19:31, on the box under a BOX-LOCK line (`port0243.sh`).
- **Vendored code:** `~/src/KytyPlus/3rdparty/vgmstream-atrac9/` holds `src/coding/libs/atrac9_dec.{c,h}`,
  `atrac9_internal.{c,h}`, `atrac9_internal_data.h` and `src/util/bitstream_msb.h`, unchanged from vgmstream
  `7c520e8`. The layout is kept so its relative include resolves. Alongside are vgmstream's `COPYING` (ISC) and
  `README.BC5` (the origin).
- **Build:** `3rdparty/CMakeLists.txt` adds a static library `VgmstreamAtrac9`; `src/CMakeLists.txt` links it next to
  LibAtrac9. Its 18 global symbols (`atrac9_*`, `init_huffman_tables`, `unpack_block`, `transform_block`, …) share no
  name with LibAtrac9's 64.
- **`src/libs/ajm/atrac9_decoder.h`** (applied by `port0243.py`; diff in `raw/host-diff.txt`):
  - For a vibration configuration (index 6 or 7), the decoder also opens a vgmstream handle on the guest's
    unchanged config bytes. LibAtrac9 still describes the stream on the translated config as before. The stream
    format then comes from `atrac9_get_info`: 2 ch or 1 ch, 48 kHz, 128-byte superframes of 4 × 256 samples, the
    same values as LibAtrac9's.
  - `DecodeFrame` calls `atrac9_decode_pcm16`, `atrac9_decode_float`, or the float decode scaled to s32. Its input
    bound is the rest of the current superframe, which every caller has already checked is present
    (`GetMinimumInputSize`).
  - A failed vgmstream init falls back to the old silence of the right length.
  - `KYTY_BC5_AT9_VIBRATION=0` keeps the silence. It is on by default.
  - The first such instance prints `bc5 ajm: ATRAC9 vibration layout N decoded by vgmstream (haptics)` or `… decoded
    as silence (haptics not produced)`.
- **Backups:** the three edited files and both previous binaries are in `~/bc5-work/exp0243/before/`: the normal build
  `2780a9a6…` and the lean one `1fc8ae07…` (F288's).
- **Patch 0001:** regenerated from the box tree (`git add -N . && git diff f266548`). Compared file by file with the
  repository's copy, it adds exactly the nine vendored and CMake files and changes `src/CMakeLists.txt` and
  `src/libs/ajm/atrac9_decoder.h`.

**Result.**
- **Build:** both shared builds rebuilt with no new warning or error (`raw/port.out`): normal `48a8f3ac…` (19:28), lean
  `4da2c70e…` (19:31). Each binary carries `atrac9_init`.
- **Smoke:** the cutscene session's exp 0242 run R1 (19:40–19:50) was the first run on this build. It ran the second
  title for 600 s through `play-pkg.sh` with its defaults: the route through Continue into the cutscene that lost clock
  time in exp 0203.
  - It printed `bc5 ajm: ATRAC9 vibration layout 7 decoded by vgmstream (haptics)` and no AJM `CODEC_ERROR`.
  - No crash line, no kernel line, 0 TIMEOUT or fault; the live saves came back identical.
  - The cinematic clock ran at 1.00× in every 5-s window of the cutscene, and the clock voice's longest record-to-run
    delay was 0.04 s. So decoding the haptic tracks costs the voices no time; F200 notes that the cinematic clock
    syncs to the opening's haptic track.
- **Not checked:** whether the decoded haptics reach the pad's actuators and feel right. That needs the maintainer
  holding the pad.

**Verdict.** The host decodes the second title's haptic tracks with vgmstream's decoder (F301). It is on by default:
the change replaces silence with the title's own signal, and the smoke run showed no regression. Rollback is
`KYTY_BC5_AT9_VIBRATION=0`, or the binaries in `before/`. Open: the maintainer's check at the pad, in an opening
cinematic or in play, with and without the switch.
