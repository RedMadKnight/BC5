# The console's way and the host's way: where BC5 still does it differently

The BC-250 is the closest hardware to a PS5 that runs Linux: the same Oberon-class APU family
(Zen 2 cores, an RDNA-class GPU of the `gfx1013` kind, unified GDDR6). The maintainer's
standing question (2026-10-19): for every piece of the pipeline, what does the console do, what
does the host do instead, and where can the host do it the console's way. This note is that
inventory. Console facts cite public sources; host facts cite the findings in `HANDOFF.md`
(F-numbers) and the experiments. Items are ordered by what they cost the player today.

Sources for the console side: Sony's published PS5 specifications (playstation.com, "PS5 tech
specs": 16 GB GDDR6 at 448 GB/s, a custom 825 GB SSD at 5.5 GB/s raw read with hardware
decompression, 8 Zen 2 cores at up to 3.5 GHz, 36 CU at up to 2.23 GHz); Mark Cerny's GDC 2020
talk "The Road to PS5" (the I/O complex: the SSD's custom controller, the hardware Kraken /
zlib decompressor, the coherency engines, the GPU cache scrubbers; the Tempest audio engine as
a CU-like SIMD unit with its own 3D audio pipeline); the public PS4/PS5 library-level knowledge
collected in open emulators (shadPS4, KytyPlus, RPCSX, see `HANDOFF.md` §6). Anything we could not
source stays marked `TODO(verify)`.

## 1. Frame timing: the flip label, the flip rate and the vblank

**Console.** The display pipeline runs on a fixed refresh (59.94 Hz or 119.88 Hz,
`VideoOutConfigureOutput`). A game submits a flip (`VideoOutSubmitFlip`, or the GPU's
end-of-pipe flip, `SubmitEopFlip`) in VSYNC mode; the flip *happens* at a later vblank, one
that is due by the flip rate the title set (`VideoOutSetFlipRate`: 0 = every vblank, 1 = every
second, 2 = every third). Only then does the display buffer's *flip label* return to 0 and the
title may render into that buffer again. That is how a 30 Hz title gets a 33.3 ms frame
whatever the GPU's actual speed: the game thread blocks on the label, the flip queue holds at
most a few requests. (Library behaviour as implemented by shadPS4's and KytyPlus's VideoOut
and confirmed on the title: run 73 in `HANDOFF.md`, the title waits for the label before
reusing the buffer.)

**Host, until exp 0162.** The direct path reset the flip label *at submission*
(`bc5LleAgc.cpp`, the direct flip: "the flip is immediate here"), so the title never waited for
a vblank. The second title's frames in gameplay were 22–31 ms long (run 793: p50 23.0 ms over
30 minutes) against a 30 Hz flip rate, and its cutscenes and gameplay sped up and slowed down
with the frame time; the maintainer heard and saw it in every scene (runs 793–796). The host's
own vblank thread (60 Hz, `Config::GetVblankFrequency`) and flip queue (`FlipQueue::Flip`,
`IsFlipDueLocked` by the flip rate) were already there and presented the frames at the right
vblanks; only the label said "free" too early.

**Done the console's way (exp 0162).** The label returns to 0 when the flip has been presented
(a thread of the host waits for `FlipQueue::Wait`, which returns after the vblank at which the
flip was due); `BC5_DIRECT_FLIP_LABEL=submit` restores the old behaviour for comparison. It did
not change the second title's frame times: the title asks for flip rate 0 (every vblank) in
VSYNC mode and registers a flip event (`KYTY_BC5_VIDEOOUT_TRACE=1`, run 797), so with three
buffers at 30-42 fps the label never gates it. The title wants 60 fps; the host delivers a
variable 30-42 (section 3). The deferred-flip path (`BC5_DIRECT_FLIP_DEFER`, exp 0070) still
resets the label when the frame has been *copied* (not presented), by design for ASTRO BOT's
throughput; it is not the default for the second title.

## 2. The audio clock

**Console.** `AudioOut2ContextPush` in blocking mode returns when the previous grain of the
context (256 or 512 samples at 48 kHz) has been handed to the output; the audio thread of a
title is therefore paced by the output DAC's clock, exactly, and engines such as Wwise count the
grains they delivered to derive the play position — which the second title's cinematic player
uses as its master clock (F198). The console's output path has no queue the game can see
beyond the context's queue depth (`AudioOut2ContextGetQueueLevel`).

**Host.** The SDL queue of the port paces the push: the game's audio thread is held while the
queue holds more than about 30 ms (`QueueSdlAudio`, `target_latency_us`), and PipeWire (quantum
1024 at 48 kHz on the box) drains it. Measured with `KYTY_BC5_AUDIO_TRACE=1` (exp 0162, run
794): 94 pushes a second of 512 frames, 48,128 frames per 1.003 s of wall time — a rate of 1.000
through the whole opening, the game thread held ~900 ms per second, the queue at 42 ms, zero
forced clears. So the audio clock is *not* where the speed changes come from; it runs at the
DAC's rate as on the console. Two things remain different and are worth keeping in mind: the
100 ms timeout in the blocking wait clears the queue (a time jump) if PipeWire ever stalls that
long — it did not in runs 793–796 — and the queue's 30–42 ms adds latency the console does not
have (the console's grain is the latency).

## 3. Where the frame goes: the submission path on the title's render thread

**Console.** The title writes PM4 into its rings; the CP fetches and executes them. The CPU
pays nothing per buffer beyond writing it, and the title's render thread is free for the
title's own work. Its threads run on dedicated hardware threads with no other process competing.

**Host.** Every buffer the title submits (4,000-5,000 a second, ~130 a frame: compute, draw,
constant and HIB buffers) goes through the direct path on the submitting thread: the policy
filter walks the packets, the state trackers follow the registers, the nested buffers are
copied, the mapping sync checks the BO list, and the kernel gets one command submission per
job - 59 a frame from the game thread and 74-79 from the ring thread. In run 798 (gameplay,
eu-stack every second) the title's `Render Thread` ran at 81-118 % of a core and 39 of 52
samples were inside that path (10 in libc under `submit_one` - the copies, 10 in the CS ioctl,
5 in `Device::submit`, 2 in the mapping sync, the rest in the trackers and the wait logic); the
title's own code had 13. `game-main` mostly waits for the render thread. That is the frame
time: the title targets 60 fps and gets 30-42, varying with the scene, which the maintainer
sees as speed-ups and slow-downs. The direct journal itself costs nothing measurable (42.1 vs
41.3 fps in the menu, 31.0 vs 29.5 in gameplay, runs 797/798).

**The console-like change (exp 0163, next).** Chain consecutive buffers of a queue into one
kernel submission - one host IB of `INDIRECT_BUFFER` packets (or several IB chunks per CS) per
run of buffers that needs no CPU-side wait - and stop copying what is already mapped, so that
a frame costs a few ioctls, not 133; keep the filter but run it once per chain. The stalls of
seconds seen in the opening (run 794: 8.1 s at t 152.9 s, almost all of it outside the host)
are a second question: the stack sampler should run through an opening (runs 794-798 loaded
the save into gameplay instead).

## 4. Memory

**Console.** 16 GB of GDDR6 for everything, with roughly 12.5 GB available to a title (public
developer-conference figures; `TODO(verify)` the exact budget), as physically contiguous *direct
memory* the title maps itself; the GPU and CPU share it without pinning or copying.

**Host.** The same 16 GB are split by the kernel: a 512 MiB VRAM carve-out, ~14 GiB for Linux
(D8), and the host gives the title `KYTY_GUEST_MEMORY_MB=13824`. Every page the GPU may touch is
a userptr or dma-buf mapping that the kernel *pins*: run 793 reached 11.4 GiB pinned in 30
minutes, the box swapped 576 MB to zram, and the maintainer saw the title behave as if memory
were short. The AMM automatic pool is now recycled (F206), but the pinned set still only grows
with the title's streaming because the host maps the title's heaps eagerly (exp 0042,
`BC5_DIRECT_EAGER_NAMES`) and keeps them mapped. The console-like option is to map lazily and
unmap what the title frees (the AMM unmap path does this since F206; the eager heaps do not).
Measured next: the pinned total against the title's own allocation (`direct: … MiB pinned` in
the journal) over a play session, and whether the eager list can shrink.

## 5. Storage and streaming

**Console.** The I/O complex reads the title's package at 5.5 GB/s raw and decompresses in
hardware; a texture is in GDDR6 within a frame or two of the request.

**Host.** The package is read through `bc5-mount` (FUSE, a user-space PFS/pfsc decoder) from an
NVMe at PCIe 2.0 ×2 (~0.8 GB/s), decoded on the CPU, then copied into the title's memory by the
host's APR worker; a disk cache keeps decoded blocks between runs (F-series 0113). The console
never waits for this; the host does, in the frames of §3 if the sampler confirms it. The
analogue would be a larger read-ahead on the APR side and the cache warmed for the opening.

## 6. GPU submission

**Console.** The title writes PM4 into its own rings; the system's CP runs them; the GPU drives
itself (indirect draws and dispatches, GDS counters, ordered append). Nothing filters the
stream.

**Host.** The direct path (`bc5LleAgc.cpp`, `backend/`) reads the rings, checks and rewrites
the packets the kernel would reject or that the host cannot serve (F32 GDS, the policy drops),
and submits them as kernel command submissions, with the GPU mostly driving itself (exp 0039,
0053 for compute indirect dispatches on the GFX ring, F129 for the compute ring). The remaining
differences that cost frames are listed in `HANDOFF.md` (the skipped BVH compaction F207/F208, the
"args not mapped" indirect dispatches F209); the submission overhead itself is 5–8 ms of the
game thread's frame (the frame profile's `inside the host`).

## 7. What to do next, in order

1. §3: chain the title's buffers into few kernel submissions (exp 0163).
2. Sample the opening's second-long stalls with `eu-sampler.sh` (likely §5).
3. §4: measure the pinned set against the title's allocation and make the eager heaps lazy.
