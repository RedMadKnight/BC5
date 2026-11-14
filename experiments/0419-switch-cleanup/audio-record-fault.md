# The title's CPU fault at eboot+0x1b349f: who writes the bad sound record (2026-11-14, laptop only, no run)

Ordered by the top session. Seen twice, both on candidate F in a long walk: arm sA (2026-11-13 21:09, 543 s, read of
0x17fc) and exp 0412's arm n10F2 (2026-11-14 10:36, 588 s, read of 0x27fc). Inputs: the two crash texts and play logs
the guardian copied to the shared notes folder (`exp0412-cpufault/`, not committed; the box paths are in exp 0412's
README section 92), and the source trees of B and F. The title's binary is not on the laptop and was not read.
Marks: [M] measured or read, [I] inferred, [?] not known.

## The answer in short

- **The record is the title's own, and the title's own code writes it.** [M] It lies in the title's heap, is read by a
  function of `eboot.bin` picked from a table inside `eboot.bin`, and none of our libraries has or fills a structure of
  this shape. [I] It is a buffer descriptor of the title's sound engine (its layout matches the public Wwise SDK's
  `AkAudioBuffer`), the input buffer of a pitch/resample step.
- **Which call of ours fed it the bad value is NOT known.** The dumps do not hold it and no trail of our audio calls
  exists. [I] The value is a null buffer base plus an offset the engine added, not a pointer we returned.
- **F's audio libraries are B's.** [M] The only difference is how `KYTY_BC5_NO_PAD_AUDIO` is read, and nothing sets it.
  Nothing shows the fault is F's: B has three long walks in all.
- **Next, cheapest first:** read the title's code at the eight return addresses on the box (read only, CPU only, no
  emulator, needs a GO); then a catcher, default off, described below.

## 1. What the dumps hold

| Fact | Mark |
|---|---|
| Same instruction both times, `movzx ebx, word [r11 + r10 - 4]`, thread 39, the same eight return addresses, all in `eboot.bin` (the innermost three: +0x1d58a6, +0x1d23df, +0x19fe14) | M |
| The 32 code bytes before it decode to `r9 = 4*r9 + [rsi]`, `r10 = 4*r10 + [rdi]`, `r11 = 4*rax`. r9 came out equal to `[rsi]` and r10 equal to `[rdi]`: both offsets were 0. So the address read is `[rdi] + 4*0x200 - 4`: the last 16-bit stereo frame of a 512-frame block whose base is `[rdi]` | M |
| `[rdi]` is 0x1000 (sA) and 0x2000 (n10F2). The same value is the first local of the calling function (stack slot 11) | M |
| The record at rdi, 0x30 bytes: +0 base, +8 `0x3102`, +0xc `0x2d`, +0x10 `0x200`, +0x12 `0x200`, +0x20 a float (1.0; 1.875 in sA), +0x28 48,000. The next record (rsi/rbx): +0 a pointer to 32-bit floats near zero, +8 `0x3102`, +0xc `0x2b`, +0x10 `0x200`, +0x12 0, 1.0, 48,000 | M |
| rcx, 0x70 below, holds the two samples the instruction stores, a pointer to itself at +0x20 and `0x10000` twice (16.16 fixed-point 1.0): a resampler's state. The function was called through `call [table + 8*index]`, table at `eboot.bin` data (r12), entries all `eboot.bin` functions | M |
| Sound was healthy to the last second: three ports, 94 calls a second each, rate 1.000, no clears. Port 2 is the pad's vibration port, 2 channels, 48,000 Hz | M |
| The log's `AJM codec=1, name=ATRAC9 decoder` is not part of the dump: `AjmLogCodecSupport` prints it once with `printf` when the title registers the codec, and the buffered line comes out when the process ends. It says the title uses AJM's ATRAC9 decoder, not that the fault is in it | M (read in `ajm.cpp`) |
| No kernel line, no failed memory call (first-failure catcher 0 lines), 680 MiB available | M (exp 0412 section 92) |

[I] `0x3102` read as the public Wwise SDK's `AkChannelConfig` bit field (channels:8, type:4, mask:20) is 2 channels,
standard, mask 0x3 (front left, front right); +0xc is then the buffer's state (45 and 43 are "data ready" and "data
needed" in that SDK's result codes, from memory, not checked against a header), +0x10 the maximum and +0x12 the valid
frames. Record A is "stereo, 16-bit, 512 valid frames, ready", record B is the float output buffer, empty. This fits
every field, but the engine's name is an inference from layout alone.

## 2. Who fills it

- [M] No library of ours owns a 0x30-byte record with these fields. What our audio libraries hand the title: AudioOut
  takes the title's buffers; Ngs2 fills `RenderBufferInfo` (pointer, size, type, channels: 24 bytes, another shape);
  AJM writes PCM into buffers the title names and a result (`result`, `internal_result`, then `size_consumed`,
  `size_produced`, `total_decoded_samples`, then `num_frames`); Audio3d takes buffers. None returns a buffer pointer of
  its own to the title.
- [I] So the base at +0 is computed by the engine from its own state: "where my decoded or streamed data starts" plus
  "how much I have consumed". 0x1000 and 0x2000 are 2 and 4 blocks of 0x800 bytes (512 frames x 2 channels x 2 bytes).
- [?] Which source feeds this step. Candidates, none excluded: (a) an ATRAC9 voice decoded through AJM into the
  engine's own output buffer (the haptic tracks are stereo, 16-bit, 48 kHz, and are decoded by BC5's own vibration
  path, exp 0243); (b) a streamed or in-memory PCM sound (the base would be a file buffer); (c) another software codec.

## 3. A size instead of a pointer, or a race?

- [I] Not "a size we returned in place of a pointer": no call of ours returns a pointer there, and AJM's sizes go
  into the result structure the title names, not into this record. One AT9 frame of 1,024 stereo 16-bit samples is
  0x1000 bytes and two are 0x2000, so the value could also be a *produced size the engine added to a null base*; two
  samples cannot tell that from "consumed offset" (both are multiples of 0x800 either way).
- [I] A null base with a live voice means the engine used a buffer it did not have: freed already, not yet allocated,
  or never given. That is a matter of order (a race in the wide sense), in the title's code or provoked by us.
- **Does the PS5 do this?** [I] No: a read through address 0x1000 faults there as well, so on the console the base is
  valid at this moment. What differs here is something the engine sees from the host. Read in our source, as
  candidates and nothing more:
  1. [M] `sceAjmBatchJobDecode*` decodes at the moment the job is added to the batch; `sceAjmBatchStart` and
     `sceAjmBatchWait` do nothing. On the console the jobs run after the start and the results exist after the wait. A
     title that adds a job and then cancels, reorders or frees is in a different state here than there.
  2. [M] A job whose instance is already destroyed returns result `INVALID_PARAMETER` with 0 bytes and is still
     appended as a good job; whether the console refuses the job at creation was not checked.
  3. [M] `AjmWriteStreamResult` always writes result + stream + frame count for a decode job, whatever flags the
     instance has.
  4. [?] Thread timing of the title's voice start and stop against its decode batch; file reads for streamed sounds.
- [?] Nothing above is shown to be the cause.

## 4. F against B in these libraries

- [M] `git diff` B (27b6416f) to F (d9af28ca) over `audio.cpp`, `libAudio.cpp`, `libAudio2.cpp`, `libNgs2.cpp`,
  `ajm.cpp`, `ajm/`, `audio3d_impl.inc`, `pad_audio_route.hpp`: three lines of `audio.cpp` (the include and the two
  reads of `KYTY_BC5_NO_PAD_AUDIO`, which now treat `=0` as off). No launcher sets that word, so behaviour is the same.
- [M] Of the 48 hardened words none is read by these files. `KYTY_BC5_AUDIOOUT_CHECKS`, `_AUDIOIN_CHECKS` and
  `_NGS2_RACK_FIX` moved from the launcher into the title's default rows with the same value 1; `KYTY_BC5_FW_AUDIO`
  and `KYTY_BC5_AUDIO_FIXES` were forced in B already. Both crash logs print "ngs2 rack fix on" and "fw audio on
  (items: pcmloop audio3d audio3dstrict ngs2 avplayer)", as B's launcher gives.
- [M] Outside sound, F differs from B in the main unit (K1r, exp 0418's start state, removed options), `libSaveData`
  (the save fix) and one-line option removals elsewhere; none touches a sound call. G adds `libAudio.cpp` (the voice
  ports' id map always on), which the second title's walk has not been shown to reach.
- [I] The count does not make it F's fault: F has about 20 long walks with 2 faults, B has 3 with none (at a rate of
  1 in 10, three clean walks happen 73 % of the time). Walks past G+480 began on 2026-11-13, with F; before that no
  run reached this part of the route, so "never seen on older builds" says little. [?] Whether both faults came at the
  same place of the route (they are 45 s apart in run time; the start of play within each run was not compared).

## 5. The catcher (proposal, default off, not written)

The address of the bad record is new every run (0x131c7bf580, 0x131c6e0f80), so a watch on it cannot be set in
advance. Two parts, one switch `KYTY_BC5_AUDIO_TRAIL=1`:

1. **A trail of our sound calls the title's decoder path uses** (`ajm.cpp`): the last 256 AJM jobs in a ring (time,
   guest thread, instance, codec, kind, input pointer and size, output pointer and size, result, consumed, produced,
   frames) and each instance's create and destroy time. Written to the journal at once, the first 16 of each kind: a
   job on an instance that does not exist, a job with input and no output, `NOT_ENOUGH_ROOM`, a codec error, a batch
   cancelled. Cost: one small record per job, a few hundred a second.
2. **A wider dump when the guest faults** (the handler that already prints registers): the ring; 0x200 bytes around
   each register that points into mapped memory (today 0x40), which takes in the whole pitch object and the pointers
   after the two buffers (its source); every 8-byte value in those dumps that lies inside an AJM input or output
   buffer of the ring, or an AudioOut buffer, gets that name next to it; 32 stack slots and the code at each return
   address.

What it can and cannot do: it names which of our calls last touched the voice's buffers and what it returned, and
shows the source object behind the bad record. It names the writer only if the source is an AJM voice; for a file
stream it shows that it is not AJM, and the file trail would be the next part.

**Before any build, the cheaper step:** read `eboot.bin` on the box at the return addresses (+0x1d58a6 and the
function it is in, +0x1d23df, +0x19fe14) to find the store into the record's first field and what it adds up. That
is one read-only pass on the maintainer's own file, no emulator, and it decides between (a), (b) and (c) of section
2 without waiting for a third fault. It needs the top's GO for the box.
