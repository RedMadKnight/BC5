# 0241 — ATRAC9 configurations 6–7: decode the second title's streams offline with vgmstream's decoder

**Question.** F200 left every ATRAC9 stream of the second title silent: they use channel configuration 7, which no
public decoder knew in 2026-10. vgmstream's own ATRAC9 decoder (`src/coding/libs/atrac9_dec.c`, commit `7c520e8`
of 2026-10-10, ISC) now lists configurations 6 "1.0 vibration" and 7 "2.0 vibration (dual mono)"
(`atrac9_dec.c:78-88`); AnyPS5 decodes them through it (found by the 2026-10-23 AnyPS5 review). Does that decoder
read the title's real streams, and are they sound or DualSense haptics? The maintainer approved porting the decoder
(2026-10-23) and asked for this offline check first.

**Setup.** Top session, 2026-10-23 19:13–19:21, on the box. No emulator, no GPU work. Short BOX-LOCK lines of its own.
- vgmstream at `7c520e8`, sparse checkout of `src/coding/libs/atrac9_*`, `src/util/bitstream_msb.h` and `COPYING` in
  `~/bc5-work/exp0241/vgmstream` (not committed here).
- `find0241.py`: scans the title's Wwise archives through a read-only `bc5-mount` of the package without its disk
  cache (`scan0241.sh`). It looks at the language-neutral `d/0/wem_0`, `d/0/wem_1`, `d/0/soundbank`, `d/1/soundbank`,
  `d/1/wem_0`, `d/1/wem_1` and the English `d/0/wem.us`, `d/1/wem.us` (`raw/audio-archives.txt`). It finds every
  RIFF/WAVE whose `fmt ` codec is Wwise's ATRAC9 (0xFFFC; config word at fmt+0x18, sample count at +0x1c, encoder
  delay at +0x20, per vgmstream `src/meta/wwise.c`). Each `data` chunk is copied to
  `~/bc5-data/priv/exp0241/streams` (mode 700). The copies stay there, and none of them is in this repository.
- `dec0241.c`: decodes one copy frame by frame with `atrac9_decode_pcm16`. It reports the decoder's info, frames ok
  and failed, samples, and per channel the peak, RMS and share of zeros. Optionally it writes a WAV.
- `decode0241.sh`: runs it on every copy (`raw/decode-all.tsv`). `sum0241.py` summarises per config word
  (`raw/summary.txt`).
- `spec0241.py` (numpy 2.3.5 in the ubuntu distrobox) does two things:
  - (a) for each stream with failed frames, it looks for a twin with the same sample count in a `wem_*` archive;
  - (b) for 25 random clean streams per config, it measures the share of spectral energy below 100 Hz, 300 Hz and
    1 kHz, the spectral centroid, and the L/R correlation of 2-ch streams (`raw/spectra.txt`).
  The WAVs are deleted after reading.

**Result.**
- The scan found **1,201 ATRAC9 streams** in 14 s (`raw/index.tsv`):
  - 992 are `fe 7e 03 f0`, configuration 7, 2 channels, 48 kHz, 128-byte superframes of 4 × 256 samples;
  - 201 are `fe 7c 01 f0`, configuration 6, mono;
  - 8 are `fe 7a 17 e0`, configuration 5, 4.0, the only ordinary multichannel ones.
- **The decoder reads them** (`raw/summary.txt`):
  - Configuration 7: 976 of 992 decode with no failed frame. That is 1,605,213 frames, 8,561 s.
  - Configuration 6: 197 of 201, 457 s.
  - Configuration 5: 8 of 8, 82 s.
  - Each stream's samples cover its Wwise sample count, and none is silent.
  - Per-channel RMS medians: 9,045 (configuration 7) and 2,566 (configuration 6). 508 configuration-7 streams reach
    full scale.
- **The 20 streams with failed frames are artefacts of the copy, not of the decoder.**
  - All are in `soundbank` archives, and their failures start at superframe 2 or 5.
  - Each has a twin with the same sample count in `wem_0`/`wem_1` that decodes clean (`raw/spectra.txt` (a)).
  - The banks hold only the head of those sounds (Wwise prefetch), so the copy runs into unrelated bytes past it.
- **Configurations 6 and 7 are haptic signals, not audio** (`raw/spectra.txt` (b), medians of 25 streams each):
  - Configuration 7: 100.0 % of the energy is below 1 kHz (minimum 99.9 %), 96.2 % below 300 Hz and 72.4 % below
    100 Hz. The spectral centroid is 98 Hz (p10 49, p90 263). The L/R correlation is 1.00 (minimum −0.02, so some
    tracks drive the two actuators differently).
  - Configuration 6: 100.0 % below 1 kHz, centroid 192 Hz.
  - Against that, the 4.0 configuration-5 streams have 78 % below 1 kHz, minimum 5 %, and a centroid of 683 Hz up
    to 1,705: ordinary audio.

**Verdict.**
- vgmstream's decoder decodes every complete configuration-6/7 stream of the title.
- The streams are the DualSense's haptic tracks: band-limited below ~1 kHz, centred near 100 Hz, often identical on
  both actuators. They are not sound, which fits the names vgmstream and KytyPS5 give these configurations.
- So the host's silent configurations 6–7 (F200) cost the title its haptics, not any audio.
- Next: port the decoder into the host's `ajm/atrac9_decoder.h` for configurations 6–7, behind a switch, and check in
  a run that the vibration voices decode and reach the pad's haptic output.

**Licences.** vgmstream is ISC (`COPYING`), compatible with GPL-2.0; its notice goes with any vendored file. Its
decoder says it was reversed from libSceSnds and Sony's libraries, the same kind of origin as LibAtrac9, which the
host already uses. No firmware, key or SDK file is involved.
