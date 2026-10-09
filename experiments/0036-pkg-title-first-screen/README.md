# 0036 — the second title reaches its first screen

**Question.** After experiment 0035 the second title (started from its PS5 package) stopped at a
null read in its own code (`eboot` +0x5e6e303). What does that read depend on, and what else
stands between the title and its first screen?

**Setup.** BC-250, the track-B host (KytyPlus f266548 + patch 0001 at this commit), `bc5-mount`
at this commit built in the `ubuntu` container, the launcher `run-pkg.sh` here with
`PACK_DIR=~/bc5-data/sysmodules-pack-hle-ampr` as in 0035, `KYTY_BC5_AMM_TRACE=1` for the
diagnostic runs. Unattended runs 33–50 of 20–600 s, 2026-10-09 08:15–09:20. The title's code was
read at its traps with gdb (`gdb-av.sh`: a breakpoint on the host's access-violation exit) and
disassembled from a memory dump kept in `~/bc5-data/priv` (never committed). `amm-cover.py`
finds the AMM maps and APR reads that cover an address in a trace; `find-refs.py` finds the
calls to a function in a dump. Public references, read as documentation: prosper's notes on
the AMM window and APR completion events (no licence, no code taken) and AnyPS5 at f145139
(`core/libs/prx/libkernel/Apr/src/Apr.cpp`, `Equeue/Equeue.cpp`, `libSceAmpr/Export.cpp`;
GPL-2.0, the wait compare table taken from it). ASTRO BOT regression: run 148 (420 s).

**Result.** Three stops, each found by the one before it, then a fourth (below the table):

| # | Stop | What the trace showed | Cause | Fix |
|---|---|---|---|---|
| 1 | null read at +0x5e6e303 in the title's render thread, 20 s | the thread walks a free list in its `RenderGpuRwSmall` heap; a node at 0x11e1000000 holds texture data; exactly one APR read (0x18000 bytes to 0x11e0ff8000, after an AMM map of the same range) covers it | the title places its own heaps at fixed addresses from 0x1000000000 to 0x1202400000 (flags 0x400010); the AMM window, searched from 0x1000000000, landed at 0x1113400000 right after the heaps then present, and the heaps the title fixed later (0x1120000000–0x1202400000) fell inside it, so AMM maps and DMA reads wrote over them | the window is searched from 512 GiB (`AMM_VA_START`); the title only uses the span it is given (prosper's notes; AnyPS5 also reserves it wherever there is room) |
| 2 | null read at +0x3aa0cb7 in a thread of the title's animation system, 45 s | the job's input object has a null pointer that the title copies from the character's model data; 40 APR reads returned fewer bytes than asked (traced: `SHORT read`); `bc5-mount` logged `kraken: OozError` for 30 blocks in 10 files | two chunk forms the package reader did not decode: an all-equal 128 KiB chunk (a one-symbol Huffman array, 8 stored bytes), for which the vendored oozextract filled the output and then reported 0 bytes consumed; and a chunk stored uncompressed (131,072 bytes) inside a compressed block, which the reader framed as an entropy array | oozextract returns the payload size, as ooz does; stored chunks are copied or given a copy header (`docs/formats/ps5pkg.md` §5); tests built from the format's fields |
| 3 | host crash in LibAtrac9 `InitFrame`, 255 s | the title initialises ATRAC9 decoders with configuration `fe 7e 03 f0` | channel configuration index 7; LibAtrac9's table has six entries, so the block count is read past it and `InitFrame` writes past `Frame.Channels` | indices 6 and 7 are rejected before the library is called; the title gets a codec error for those streams |

After the three fixes the title runs to the end of a 420 s and a 600 s run without a fault.
The first image appears at about 300 s: a dialog asking whether to keep an accessibility
feature on; an automatic cross press at 300 s dismisses it and the next screen shows its
button hints. Rendering stalls: 777 frames by 75 s (black), 933 by 300 s, 966 by 540 s. Read
through the mount, every file of the package (288 files, 196.6 GB logical) now decodes without
an error, in 196 s.

A fourth stop, the stalls: with a thread sampler (run 49), file reads end at about 150 s and
from then on the title's main thread and the host's `bc5-ring` thread each run a full core
while nothing renders. The direct path's journal shows why: GPU page faults at 0x1212180000,
0x123956e000, 0x124928d000 and 0x126d2d3000, each a 2 s fence timeout and a 12 s reset, with
every submission in flight failing (50 in run 48). All four lie in one heap of the title,
`CommitIABufferAllocator` (0x1210000000, 2.7 GiB), which the direct path imports only where
it holds CPU-written data or a fault has taught it a 96 MiB window (`direct-learned.txt`,
shared with ASTRO BOT until now). With the title's GPU heaps imported in full from the start
(`EAGER_NAMES=RenderGpuWcLarge,RenderGpuWcSmall,RenderGpuRwLarge,RenderGpuRwSmall,CommitIABufferAllocator`,
a knob of `run-pkg.sh`, which also gives the title its own learned-fault file), run 50: 12
failed submissions instead of 50, one fault just past that heap's end (now learned), 274,539
submissions in 418 s, 9.3 GiB pinned, and at 360 s the title renders a 3D scene at 6.8 fps
(frame 2190).

Checked and ruled out on the way:

| Suspect | Finding |
|---|---|
| fixed mappings replacing live memory (traced in `ReplaceFixedRangeWithReserved`) | 19, all the title remapping its own direct memory at 0x2700000000 |
| AMM physical pages aliased by two addresses | none in 2,165 maps |
| the filter of AMPR completion events (the host uses `EVFILT_USER`, AnyPS5 −25, prosper −24) | no change with −25 (`KYTY_BC5_AMPR_FILTER`); the title registers four ids on its loose-load queue and 21–22 completions arrive |
| `WaitOnAddress` compare codes | the title uses only code 4; the table is now AnyPS5's (0 `==`, 1 `>`, 2 `<`, 3 `!=`, 4 reached with wrap-around, 5/6 signed `>`/`<`) |
| the file-path resolve variants | all eight are implemented; the title uses the plain one |

ASTRO BOT after these changes (run 148, 420 s, autopress): in play at 55 fps at the end, as
before.

**AnyPS5.** The project reports coverage of system library functions (79–87 % in the press,
of the functions it knows) and of shader instructions (96 %), not a share of games that run;
no public build boots a game to play yet. Its APR/AMM code (GPL-2.0) executes a buffer
synchronously at submit and spins on waits, reserves a 2 × 32 GiB AMM window wherever there is
room, and implements more of the AMM command set than this title uses (remap, multimap, PRT,
protection changes, counters). It throws on a short read. Nothing in it touches the three stops
above, which were in the address placement, the package reader and an audio library.

**Verdict.** Passed: the title loads and renders 3D from the package. The stops were the AMM
window's placement in the host, two Kraken chunk forms in `bc5-mount`, a missing bound check in
LibAtrac9, and GPU heaps of the title that the direct path did not import. Open: speed (6.8 fps,
5 minutes to the first 3D scene), the last learned fault, the title's GPU heaps found by name
rather than by the memory type or GPU access the title gives them, ATRAC9 channel
configuration 7, and the title's entitlement queries, which the host stubs.
