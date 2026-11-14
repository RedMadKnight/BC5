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

## 6. Written for the next private build (2026-11-14, tag ajt; candidate G is now patch `372ac258`; it was `f32bb923` before the followed pointers of section 8 were added to the dump)

`ajm/mkajm0419.py` edits `src/libs/ajm.cpp` and the guest fault handler and adds `src/bc5/ajm_trail.hpp`. Three
switches, all off by default; with all three unset every call does what it did (the job's work, then the append).

| Switch | Kind | What it does |
|---|---|---|
| `KYTY_BC5_AUDIO_TRAIL=1` | catcher | The last 256 AJM calls in a ring (decodes with both buffers and the result, the split decode's guest pieces, instance creates and destroys, batch starts and cancels). When the guest faults, the handler prints 0x200 bytes around rdi, rsi, rbx, rcx, r13 and r15, names every value that lies in an AJM buffer of the ring, then prints the ring and the counters. Every 4,096 creates it prints the number of instances created and destroyed with the time |
| `KYTY_BC5_AJM_DEFER=1` | fix candidate | A batch's jobs run inside `sceAjmBatchStart`, in the order they were added; a job that did not fit into the batch does not run; jobs of a buffer initialised again without a start are dropped and counted; the split jobs' buffer lists are copied when the job is made |
| `KYTY_BC5_AJM_LIVE_IDS=1` | fix candidate | An instance id that is still alive is not given out again |

Always on, one line each for the first 8 cases: an instance id given out while still alive, and a job on an instance
that does not exist.

**The candidate "we decode when the job is added" [M, from the source]:** yes, the title can see a job's result before
`sceAjmBatchStart`: all thirteen job calls that read or change an instance wrote their PCM, result and sideband before
returning, and the start and the wait did nothing. Whether this title reads them that early is [?]. The change to the
console's order is small: the thirteen calls' bodies become callables (about 40 changed lines), run at the start.
Running them inside the start, not on another thread, is one of the orders the console allows (results are due at
`sceAjmBatchWait`).

**A second candidate found while writing it [M, from the source; I for the link to the fault]:** an instance id is
`(codec << 14) | slot`, the slot a counter masked to 14 bits. After 16,384 creates of one codec the counter wraps and
`sceAjmInstanceCreate` stores the new instance under an id that may still be alive: the older voice's decoder is
replaced by the new one's, the older voice then decodes another voice's stream with the wrong state, and whichever is
destroyed first takes the other's instance with it (its jobs then return "invalid parameter" with 0 bytes, appended
as good jobs). That needs a long-lived voice and about 16,000 creates: at 30 creates a second it is reached near
550 s, which is where both faults came, and it would not depend on F. [?] The title's create rate is not known; the
trail's counter line gives it in one ordinary walk, and the always-on line names the first reuse. If the rate is far
lower, this candidate is out.

Checked on the laptop: `ajm/test0419ajm.cpp` (the ring, the id rule with and without the fix including the wrap, the
deferred jobs' order, drop and run-once) all ok; `ajm/chkblock0419.cpp` compiles the block that goes into `ajm.cpp`
against stand-ins with `-Wall -Wextra -Werror -Wshadow`; every edit matched once, braces balance; the dry run F -> G on
a clean tree, 133 of 133 files. NOT compiled: `ajm.cpp` as a whole (it needs the ffmpeg headers) and the handler
(Linux only); their first compile is G's build on the box. G reads 202 words now, 155 can be set.

## 7. The title's code at the return addresses (2026-11-14 12:00, box, read only; the top session's GO)

`eread0419.sh`: no emulator, BOX-LOCK empty before and after, one lock line, nice 19. It read the maintainer's own
`eboot.bin` of the second title (a container; its first segment is stored plain), cut the code range +0x110000 to
+0x1e2000 and disassembled it into `~/bc5-work/exp0419/eread/` on the box (mode 700; nothing of it is in git or on the
laptop). The disassembly's line at +0x1b349f is the faulting instruction of both dumps. A few follow-up reads of that
one file were made right after the script, when its lock line was already released (the lock stayed empty, about
three minutes); they should have been inside it.

| Finding | Mark |
|---|---|
| +0x1b3460 (the faulting function) computes the source address as `[rdi] + 4 * [rcx+0x28]`: the record's first field plus an input offset kept in the resampler's state. That offset was 0 both times, so the first field itself was 0x1000 / 0x2000 | M |
| +0x1b3110 (its caller) loops over a table of conversion functions indexed by sample format and channel count until the input has no frames left or the output is full | M |
| +0x1d5600, the function of the return address +0x1d58a6: an object with an upstream object at +0x8 (called through its table), the input record at +0x80, the output record at +0xb0. When its input record has no valid frames (+0x92), it **copies the 0x30-byte record its caller passed in (rsi) into +0x80**; nothing in this function writes the first field otherwise, except the three places that clear the record to 0 with state 0x2b after the upstream object's "release" call | M |
| +0x1d5570, the entry before it: it calls the upstream object's function at table offset 0x40 with that same record, then falls into +0x1d5600. **So the bad first field was written by the upstream object's "get buffer" call**, one step before the copy | M for the order of calls; I that the call at offset 0x40 is the fill |
| The stack value 0x1000 / 0x2000 (slot 11) is not a variable of +0x1d5600: that slot (rbp-0x50) is never written there. It is left over from an earlier, deeper call | M |
| Which class the upstream object is: **not in the dumps.** The pointer to it is at object+0x8 (0x131c6e0f08 in n10F2), 8 bytes before the 64 bytes the handler printed from rcx. The wider dump of `KYTY_BC5_AUDIO_TRAIL` (0x100 bytes before each register) contains it; its table address then names the class from this same disassembly | M |
| Candidates read in the range, each a "fill" that stores a data pointer, the frame counts and returns state 0x2d: +0x1c2d40 (a block decoder to interleaved 16-bit: its data pointer is the object's own output buffer at +0x18, allocated on first use and freed and zeroed by +0x1c2ce0, plus an optional skip of `frames * channels * 2`), +0x18b5xx (takes the pointer from an inner object's call), +0x18c4xx (24-bit to float, not this format) | M for what each does; ? which one fed the faulting step |

[I] The picture agrees with section 3: an engine-owned buffer pointer that is null at the moment of the fill, plus an
offset or skip the fill adds. In the block decoder the pointer is reloaded from the object after the decode, so a
release of that buffer between the allocation and the reload (another thread, or a callback inside the decode) gives
exactly "null plus skip". [?] Whether the faulting voice is that decoder, and what released the buffer. No AJM call
is visible on this path so far; the two AJM candidates of section 6 are neither supported nor refuted by this read.

**What decides it next, without more reading:** one fault with `KYTY_BC5_AUDIO_TRAIL=1` (the pointer at object+0x8 and
its table), or a targeted read of the tables in the title's data segment that hold +0x1c2d40's caller (a second
read-only pass, about ten minutes).

## 8. The second pass: the chain behind the fill (2026-11-14 12:10, box, read only, one lock line per run)

`eread0419b.sh` reads the disassembly on the box and the title's relocation records (the image is position
independent: its function tables are filled by relative relocations) and prints, for a function, its direct callers
and the tables it sits in. Then one function was read (the stream fetch). The top session's slot message of 12:09.

| Finding | Mark |
|---|---|
| +0x1d5570 (the step that calls the upstream fill, section 7) has one direct caller chain: +0x1d2390, +0x19fd20, +0x1a1a40. These are the dumps' return addresses +0x1d23df, +0x19fe14, +0x1a1a69 | M |
| +0x18b5a0 is reached only through a function table (0x8ef8438). It asks an inner object at its +0xc8, through that object's table offset 0x30, to fill a local record, then copies that record's pointer and frame counts into the caller's record: **a file source's "get buffer" that delegates to a codec object** | M |
| +0x1c2d40 (the block decoder to interleaved 16-bit) and +0x1c2ce0 (frees and zeroes its two buffers) are slots +0x30 and +0x20 of one table (0x8ef95a8): **one codec's "decode" and "release"**. Neither has a direct caller | M |
| +0x18cf50, called at the start of that decode when the codec has no input left: it takes the next piece of the sound's data. Two ways: (a) flag bits 0x38 of the source's byte +0x52 equal 8: pointer = `[source+0x10] + [source+0x30]`, size = `[source+0x24] - [source+0x30]` (data held in memory: a base plus a data offset); (b) otherwise it calls the stream object's table offset 0x80 with the address of a pointer and of a size and accepts states 0x2d and 0x11. If the size is not 0 it hands pointer and size on (+0x18d150) | M |
| **Neither way checks the pointer.** A null base in (a) gives "the data offset" as the pointer; a null pointer with a size from the stream in (b) is passed on as it is | M |

[I] Three places can now produce "a small number where a pointer belongs", in the order the code reaches them:
1. the in-memory base at source+0x10 is null (the sound's memory copy is gone or was never set) and the pointer is
   the data offset, later advanced by what was consumed;
2. the stream object returns "ready" with a size and a null pointer; the stream object reads the title's files
   through our file calls, but the buffer memory is the engine's own;
3. the codec's output buffer at codec+0x18 is released (+0x1c2ce0) between its allocation and its reload in the same
   decode, which needs another thread.

For a 16-bit stereo sound that needs no decoding the pointer of 1 or 2 goes to the pitch step unchanged, plus what
was consumed: both observed values, 0x1000 and 0x2000, are whole multiples of one block (0x800), which fits 1 and 2
better than 3 (where the added skip is in frames of a block decoder). [?] Which of the three; whether the faulting
voice is a plain 16-bit sound or the block decoder (the codec table that holds the plain-PCM "decode" was not
looked for); what makes the base or the stream pointer null. Our side can enter only through 2 (what the engine's
stream manager gets from our file layer: sizes, positions, completion order), and through timing for 3. Of the file
layer, `KYTY_BC5_APR_POSIX=direct` became a forced default on 2026-11-13 01:50 (patch 4651d1d3, also in B), 19 hours
before the first fault: a coincidence in time, nothing more is known.

**The catcher was extended for exactly this:** with `KYTY_BC5_AUDIO_TRAIL=1` the handler now also follows the pointer
at rcx-8 (the upstream source) and the pointer at its +0xc8 (the codec) and prints 0x200 to 0x400 bytes of each. One
fault then shows the source's table (its class), its flag byte +0x52, the base at +0x10, the stream pointer and size
at +0x18 and +0x20, and the codec's buffers: enough to pick between 1, 2 and 3. G is patch `372ac258` and the test
build T is `5f2df896` with this; the unit is unchanged (7cb02bac), so the guardian's test result stands.
