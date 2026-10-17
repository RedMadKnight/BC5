# AJM Opus decoding — the job contract the host implements

Status: derived from one title's jobs (experiment 0154, 2026-10-17) and the public Opus
specifications; nothing here comes from Sony material. The host's implementation is
`src/libs/ajm/opus_decoder.h` in `backend/kytyplus-patches/0001-bc5-lle-agc.patch`
(libopus, `KYTY_HAS_OPUS`). Everything marked *TODO(verify)* held for that one title (Wwise,
codec 0x3041 "Wwise Opus") and is to be checked against the next.

Sources:

- RFC 6716 (Opus codec): §3.1 the TOC byte (configuration, stereo flag, frame count code),
  §3.2 the frame count codes; `opus_packet_get_nb_samples` implements them.
- RFC 7845 (Ogg Opus) §5.1.1.2: the channel mapping family 1 layouts (streams, coupled
  streams, channel mapping for 1–8 channels).
- KytyPlus `src/libs/ajm.cpp` (GPL-2.0): the AJM job, sideband and gapless structures
  (`AjmDecOpusInitializeParameters`, `AjmSidebandStream`, `AjmSidebandGaplessDecode`).
- `experiments/0154-ajm-atrac9-and-the-stuck-voice`: the title's jobs (`raw/ajm-trace-excerpts.txt`).

## 1. Instance

`AjmInstanceCreate(codec 24)`; initialize parameters (12 bytes): `channel_num` (u32),
`sample_rate` (u32), `mapping_family` (u32). Seen: mono/48000/0 (voices), 4 ch/48000/1 (the
menu music). The handle is `(codec << 14) | slot`: Opus instances are `0x6xxxx`, ATRAC9 (codec 1)
`0x4xxx`.

Mapping family 0 is one Opus stream of 1–2 channels. Family 1 carries no stream layout in the
parameters, so the host applies the RFC 7845 defaults (4 ch: 2 streams, 2 coupled, mapping
0 1 2 3) through libopus's multistream decoder. *TODO(verify)*: whether the console accepts
family 1 with other layouts, and families 2/255 at all (the host refuses them).

## 2. Input framing

The job's input (one buffer, or several `AjmBuffer`s concatenated) is a run of Opus packets,
**each preceded by its size as a little-endian uint16**: `03 01 | f8 b5 …` is a 259-byte packet
whose TOC is `0xf8` (CELT fullband 20 ms, mono, one frame). The title takes the sizes from
its file's seek table (Wwise Opus WEM `seek` chunk) — the file itself stores raw packets. A job
carries one to four packets; the last may be cut by the end of the input, and the title
resubmits it whole in the next job.

## 3. Output and consumption

- The title asks for a fixed number of samples a job — **512** (`out` 1024 bytes for mono s16,
  2048 for two channels) — fewer than a 20-ms packet's 960. The decoder therefore keeps the
  PCM of the last packet it decoded and hands it out across jobs: a job first drains that
  remainder, then pulls whole packets while the output has room.
- `size_consumed` (stream sideband) is the bytes of the packets the job pulled (2 + size
  each); the title advances its stream by exactly that. A job that only drained the
  remainder consumes 0 and is not an error.
- A decoder that takes whole packets only and answers `NOT_ENOUGH_ROOM` to a 512-sample
  output makes the title retry with a doubled output; it then runs the voice at ~0.43× real
  time (run 618), so that is not the console's behaviour. *TODO(verify)*: what the console
  answers when the output is smaller than one packet and the decoder holds no remainder (the
  host answers `NOT_ENOUGH_ROOM` with nothing consumed).

## 4. Counters and gapless

`AjmBatchJobSetGaplessDecode` arrives before the first decode with `total_samples` (the WEM
header's `num_samples`: 480,000 for a 10-s clip), `skip_samples` (the Opus pre-skip, 312) and
`skipped_samples` 0.

- `skip_samples` are dropped from the first packets' output.
- `total_samples` is the output length **after** the pre-skip: the title's 10-s clip has 501
  packets (501 × 960 = 480,960 ≥ 480,000 + 312, while 500 packets would not reach it).
- `total_decoded_samples` (stream sideband) and the gapless remainder advance **per packet
  decoded**, by the packet's samples after skip and limit — not per byte handed out. With
  per-byte counters the title never submits a job to drain the last packet's remainder, the
  counters never reach the total, and the voice neither ends nor loops (run 619 vs 621).
- At the end of a looped clip the title issues `clear-context` and restarts from the first
  packet (skip applied again).

## 5. Results seen from the title

`OK` with data written; `NOT_ENOUGH_ROOM` (0x10) when nothing fits; `PARTIAL_INPUT` (0x8) for
a job that carries only a cut packet. `frames` (multi-frame sideband) counts the packets pulled;
`frames_per_packet` (codec info) is the TOC's frame count.
