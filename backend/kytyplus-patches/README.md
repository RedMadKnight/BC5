# KytyPlus patches (track B, HANDOFF D11)

Patches against [KytyPlus](https://github.com/Coder787-source/KytyPlus) (GPL-2.0-only, same licence
as this repository) that let the game's own copies of Sony's `libSceAgc.sprx` and
`libSceAgcDriver.sprx` (shipped in a dump's `fakelib/`) run LLE inside KytyPlus's HLE, with a
`/dev/gc` device provided by us. Base commit: `f266548` (2026-09-28).

| Patch | What |
| --- | --- |
| `0001-bc5-lle-agc.patch` | `src/libs/bc5LleAgc.cpp` (new): the 29 libkernel/VideoOut/Sysmodule/RegMgr imports, `/dev/gc` + `/dev/dipsw` (ioctl, mmap), raw capture, the **soft CP** (executes `WRITE_DATA`, `RELEASE_MEM`, `EVENT_WRITE_EOP`, `COND_EXEC`, `ATOMIC_MEM`, `WAIT_REG_MEM[64]`, `COPY_DATA`, `INDIRECT_BUFFER`; fires the `EVFILT_GRAPHICS` events; skips the rest) and the **queue consumer** (the 56 hardware-style queues registered via ioctl `0xc0408121`: write pointers in the mmap'd submit page, rings of `INDIRECT_BUFFER` packets, read pointer published at `rptr_addr`). KytyPlus fixes it depends on: `/dev/gc`, `/dev/dipsw` as pseudo-devices in `KernelOpen`; registration in `libs.cpp`; `KYTY_GUEST_MEMORY_MB` (experiment 0009); filler-NOP length in `pm4.h` (COUNT 0x3fff = one dword); **fiber context save/restore as naked functions** (the `push %rbp` prologue made the saved `rip` a frame pointer, experiment 0012); instruction-fetch faults no longer routed through the GPU page tracker (deadlock); diagnostics: stalled-thread name + caller in `PthreadCondWait`, packet name in the interpreter's length check. |

Apply and build (inside the `ubuntu` distrobox on the dev box, see `CLAUDE.md`):

```bash
git -C ~/src/KytyPlus checkout f266548
git -C ~/src/KytyPlus apply --check backend/kytyplus-patches/0001-bc5-lle-agc.patch
git -C ~/src/KytyPlus apply backend/kytyplus-patches/0001-bc5-lle-agc.patch
cmake --build ~/bc5-work/kytyplus-build --target kyty_emulator -j8
```

Run (paths from the dev box; nothing from `~/bc5-data` is ever committed):

```bash
SHADPS4_SYSMODULES_PACK_DIR=$HOME/bc5-data/mnt/<TITLE_ID>/fakelib \
KYTY_GUEST_MEMORY_MB=13824 \
BC5_GC_DUMP_DIR=$HOME/bc5-data/captures/<run>/gc \
kyty_emulator --game $HOME/bc5-data/mnt/<TITLE_ID>
```

Direct submission (ADR 0005) additionally needs the BC5 backend built with clang in the same
container and linked in:

```bash
cmake -S ~/src/bc5/backend -B ~/bc5-work/backend-ubuntu -G Ninja -DCMAKE_C_COMPILER=clang \
  -DCMAKE_CXX_COMPILER=clang++ -DCMAKE_BUILD_TYPE=Release -DBC5_WITH_AMDGPU=ON -DBC5_BUILD_TESTS=OFF
cmake --build ~/bc5-work/backend-ubuntu -j8
cmake ~/bc5-work/kytyplus-build -DKYTY_BC5_BACKEND_SRC=~/src/bc5/backend \
  -DKYTY_BC5_BACKEND_BUILD=~/bc5-work/backend-ubuntu   # defines KYTY_BC5_DIRECT
```

Environment:

- `KYTY_BC5_ANON_BACKING=1` (patch): guest views are anonymous memory instead of views of the
  shared memfd. Required by the direct mode (amdgpu refuses writable userptr BOs over file-backed
  pages, experiment 0016); costs: no writable alias, direct memory does not persist across
  unmap/remap, no physical aliasing.
- `BC5_GC_MODE` (patch): `soft` (default: the soft CP, nothing reaches the GPU), `direct` (ADR
  0005: userptr 1:1 + policy filter + GFX ring; needs the build above and `KYTY_BC5_ANON_BACKING=1`;
  **submits to the GPU** — hard rule 5, maintainer's go-ahead), `kyty` (KytyPlus's own interpreter).
- `BC5_DIRECT_STAGE` (patch): `preamble` (default; only the submit-header IBs), `nodraw` (every IB,
  draws and dispatches NOP-ed), `all`. `BC5_DIRECT_CU_MASK` (hex, default `ffffffff`),
  `BC5_DIRECT_NODE` (render node).
- `SHADPS4_SYSMODULES_PACK_DIR` (KytyPlus): directory whose `.sprx` take precedence over the HLE.
- `KYTY_GUEST_MEMORY_MB` (patch): guest memory size; ASTRO BOT needs ≈ 12.2 GB of direct memory.
- `BC5_GC_DUMP_DIR`, `BC5_GC_DUMP_LIMIT` (patch): write every command buffer submitted through
  `/dev/gc` as raw little-endian dwords, `NNNNNN-<kind>.bin` (`cc` = context control, `dcb`).

Sources for the semantics in the patch: the call sites in the two Sony modules (BC5 experiment
0010, register-order argument recovery), RPCSX `rpcsx/iodev/gc.cpp` @ `e8ae148` (GPL-2.0) for the
ioctl codes and argument layouts, shadPS4 `src/core/aerolib/aerolib.inl` (GPL-2.0) for NID names.
No Sony code or data is in the patch.

Status: see `experiments/0011-first-sony-dcb-capture`. The patch is meant to be offered upstream
once the `/dev/gc` side is stable; until then it is applied locally.

Direct-mode knobs added during phase 3 (experiment 0016): `BC5_DIRECT_STAGE` (`maponly`,
`preamble`, `nodraw`, `all`), `BC5_DIRECT_DROP_OPS=<hex opcodes>` (extra drops), `BC5_DIRECT_RINGS=1`
(compute doorbell rings to the GPU, step e), `BC5_DIRECT_SELFTEST=1`. The host revalidates
its 1:1 mappings against `/proc/self/maps` on every sync, journals every `LOAD_*_REG[_INDEX]` table
before a submit, and its soft CP skips the memory side effects of packets the GPU executed.
`KYTY_BC5_ALL_RW=1` keeps every readable guest page CPU-writable (the executable's r-x/r-- segments
hold shader code and rodata; a writable userptr is the only kind libdrm can put in a BO list, see
`backend/src/direct.cpp`). `Bc5ForEachMappedRange` (memory.cpp) enumerates the guest's mapped ranges.
Step (d) knobs: `BC5_DIRECT_HINT_MIB`/`BC5_DIRECT_HINT_BELOW_MIB` (render-target windows, 32 MiB
each side), `BC5_DIRECT_NO_HINTS`, `BC5_DIRECT_LEARNED` (fault-learned regions file, default
`~/bc5-work/direct-learned.txt`), `BC5_DIRECT_REOPEN=1` (reopen the device after a ring reset).

Added on 2026-10-01 (experiment 0016, runs 67–72): `BC5_DIRECT_SHADER_DUMP=1` (shader programs and
the memory their user-data registers point at, as `shader-<va>.bin` / `mem-<va>.bin` in the capture
directory; never committed), `BC5_DIRECT_RANGES_DUMP=1` (the guest's mapped ranges with physical
offsets), `BC5_DIRECT_PROBE_VA=<hex>[:bytes]` (pagemap state and bytes of one
guest address, journaled when they change), `BC5_DIRECT_NO_PAGEMAP=1` (residency from `mincore()`
alone; by default swapped-out pages count as resident), `BC5_DIRECT_NO_TAIL_SPLIT=1` (do not split
a compute IB at a wait followed only by signalling packets). The flip label of a
buffer is cleared at `SubmitEopFlip`. With `KYTY_BC5_ANON_BACKING=1` a view whose protection
changes is re-protected with `mprotect` instead of being mapped again (which zeroed it).
The context-state stack emulation (`Device::set_state_stack`, F35) is on by default since run 75;
`BC5_DIRECT_NO_STATE_STACK=1` turns it off.
Cleanup batch 2 (2026-10-15) removed the phase-3 bring-up probes whose questions experiment 0016
answered: one-packet-at-a-time submission (`PIECEWISE`, `_KIND`, `_MIN`), pipeline statistics
(`PIPESTATS`, `DRAWSTATS`), IB prologues (`PROLOGUE_PRIM`, `PROLOGUE_UCONFIG`, `TILE_STEERING`),
`OA_ENBL`, `RAW_CONTEXT_CONTROL`, `NO_BOLIST`, `NO_SPLIT`, the GDS self-test and snapshots, the
state-stack dry run (`STATE_STACK`) and whole-table journaling (`TABLES_FULL`); `BC5_DIRECT_GDS_KIB`
is now read once instead of at every submission.
`BC5_DIRECT_TIMING=1` journals a timeline (each submission with its sync and hint times, CPU
waits, flips). `BC5_GC_NO_IDENT0=1` stops the EVFILT_GRAPHICS ident-0 events (F36).
The crash journal is synced once per submission (before the GPU submit) since run 78;
`BC5_DIRECT_JOURNAL_SYNC=1` syncs every line and every IB dump again.
Short BO lists (`Device::set_short_lists`, ADR 0005 xx) are on by default since run 81;
`BC5_DIRECT_NO_SHORT_LISTS=1` lists every mapping on every submission again.
`BC5_DIRECT_CU_MASK` now also covers CU masks the stream loads from memory (`bc5::cu_tables`).
The forced mapping sync is skipped for IBs without draws whose operands are already mapped;
`BC5_DIRECT_NO_LAZY_SYNC=1` forces it always.

ADR 0006 (experiment 0017): `KYTY_BC5_DMABUF=1` instead of `KYTY_BC5_ANON_BACKING=1` keeps
KytyPlus's upstream memfd views for direct memory; the patch seals the memfd against shrinking
and exposes its fd (`LibKernel::Memory::Bc5DirectMemoryFd`), the host imports 2 MiB chunks of it
through `/dev/udmabuf` and maps them at the views' addresses.
`BC5_DIRECT_NO_DMA_IDLE=1` turns off the CP-DMA idle wait the device appends to every IB (F41).
Doorbell queues (experiment 0018): the consumer keeps ring pointers modulo the ring size and
publishes the read pointer also in the dword behind the ring, where the driver library reads it
(`BC5_GC_NO_RING_END_RPTR=1` leaves that out). `BC5_GC_QUEUE_TABLE=<hex address>[:entries]` journals
the library's own queue table every eighth flip.

Host completeness beyond the GPU path (from F43 on): `libJson2.cpp` gains the 28 `sce::Json`
functions ASTRO BOT imports and KytyPlus lacked (`Value::referValue`, `Value::toString`, the
`Array`/`Object` iterators, copy constructors and setters), names from the public NID tables;
layout assumptions are marked `TODO(verify)` in the source. No system module is loaded for it:
there is no firmware dump to load one from.
Experiment 0020: the HLE `Json2` library gained the 28 `sce::Json` functions the game imports
(`KYTY_BC5_JSON_TRACE=1` logs keys, types and text). For the GTT ceiling of run 96 (F44) the
journal breaks imported memory down by the game's mapping names every 512 MiB and on `-ENOMEM`;
`BC5_DIRECT_LAZY_NAMES=orbis_user_malloc` imports views of that name only where a hint or a
learned fault asks.
Experiment 0021 (the emulator's own GTT share): `KYTY_BC5_CACHE_MIB=staging,stream,download,device`
sets the sizes of the buffer cache's four fixed buffers (defaults 512, 64, 64, 128 MiB; the direct
path runs with 96,16,16,16), `KYTY_BC5_VMA_BLOCK_MIB=16` the allocator's block size, and
`KYTY_BC5_VMA_TRACE=1` logs every allocation and release with its callers.
Experiment 0022 (frame time): `BC5_DIRECT_JOURNAL=min` replaces the crash journal by one buffered
line per submission (no IB dumps, no sync); imports that neighbour each other are merged into BOs
of up to the udmabuf size limit (`BC5_DIRECT_NO_MERGE=1`, `BC5_DIRECT_MAX_BO_MIB`).
Step 3 of experiment 0022: `BC5_DIRECT_NO_FAST_SYNC=1` makes the direct-memory sync scan every
time again; `BC5_DIRECT_ANON_SYNC_MS` (default 100, 0 = every forced call) is the minimum age of
the last walk over the anonymous VMAs before a forced call repeats it. With `BC5_DIRECT_TIMING=1`
the journal carries a split of the sync and hint time every 128 submissions.
Host completeness found by run 103: `kernel/fileSystem.cpp` keeps each directory's names (folded
to lower case, valid while the directory's modification time is unchanged) instead of listing the
directory for every missing file; `libs/controller.*` and the window's event loop pass the pad's
accelerometer and gyroscope (SDL sensors) into the pad state.
`BC5_DIRECT_EAGER_NAMES=name[,name]` imports views with these names in full as soon as they exist
(the game's GPU heaps: render targets and GPU-written textures that no CPU write would reveal).
Experiment 0023: with `KYTY_BC5_DMABUF=1` private guest memory (everything `GuestAddressSpace::Commit`
hands out) is mapped from a second sealed memfd at offset = guest address
(`LibKernel::Memory::Bc5PrivateMemoryFd`, `Bc5ForEachPrivateRegion`) and imported by the host like
the direct memory; `KYTY_BC5_NO_PRIVATE_FILE=1` turns that off, `BC5_DIRECT_STACKS=1` imports
thread stacks as well.
Experiment 0024: `BC5_DIRECT_ASYNC=1` (with `BC5_DIRECT_JOURNAL=min`) queues jobs without waiting
for them; the soft CP's pass over each buffer then runs on a completion thread per submitting
thread, and a flip waits until nothing is in flight.
`KYTY_BC5_AUTOPRESS="55:cross,62:cross,330:shake"` presses pad buttons (cross, circle, square,
triangle, options) or shakes the pad at the given seconds after start, for unattended runs.
`KYTY_BC5_INPUT_CMD=<file>` drives the pad from a script while the title runs (experiment 0061):
a thread tails the file every 20 ms and runs each new line in order: `press <button> [ms]`,
`hold <button>`, `release <button>`, `stick <l|r> <x> <y> [ms]` (0–255, 128 = centre; with `ms`
it re-centres afterwards), `trigger <l2|r2> <0..255> [ms]`, `shake`, `wait <ms>`, `reset`.
Buttons: cross circle square triangle options up down left right l1 r1 l2 r2 l3 r3 touchpad.
After each line, `<file>.done` holds the number of lines run.
`KYTY_BC5_INPUT_RECORD=<file>` writes what the real pad does in the same format (`hold`/`release`,
`stick`, `trigger`, `wait` lines between them; stick moves at most every 30 ms and only past a
change of 6), so a route played once by hand can be replayed through `KYTY_BC5_INPUT_CMD`. The
scripted input is not recorded.
`KYTY_BC5_SAVEDATA_DIR=<dir>` puts the save data memory file (`<title>/sce_sdmemory/memory.dat`)
under that directory instead of `_SaveData` in the working directory, so that runs started in
different directories share one save.
Pad: the orientation in the pad data is derived from the gyroscope and the accelerometer
(`KYTY_BC5_MOTION_TRACE=1` logs acceleration, angular velocity and orientation once a second);
`KYTY_BC5_TRIGGER_DEADZONE=<0..254>` reads trigger values up to that as released, for a pad
whose trigger does not rest at 0.
Input configuration (`hostInput.cpp`, `window.cpp`, `main.cpp`): `--input-config <file>` or
`KYTY_BC5_INPUT_CONFIG=<file>` reads one statement per line, `#` comments: `<Control>=<Input>`
binds a DualSense control (Cross … TouchPad, LeftStickUp …) to a key (SDL's key names), a
mouse button (`Mouse:Left` …), a pad button (`Pad:a`, `Pad:leftshoulder`, SDL's names) or a pad
axis (`Pad:righttrigger`, `Pad:leftx-`); `Pad:<name>=none` drops the physical button or axis
before it reaches the game; `DefaultKeys=on|off` keeps or drops the built-in keyboard layout
(KytyPlus's, plus U = L2 and O = R2), from which a bound key or control is removed; every line is
also accepted as `--keymap`. A bad line stops the emulator with file:line and the reason. The
names and examples are in `input.example.cfg` next to this file. `settingsOverlay.cpp` is the F2
menu over the game (ImGui in the presentation pass, like the IME keyboard): it binds controls by
capturing the next input, switches pad inputs off, applies live and saves the file;
`KYTY_BC5_SETTINGS_OPEN=1` opens it at start. `KYTY_BC5_INPUT_TRACE=1` writes every
key, every write of the keyboard/mouse stream into the pad slot, every change of R2 as the game
reads it and the pad reads per second to stderr; `KYTY_BC5_KEY_MIN_HOLD_MS` (default 60) holds a
key's release back until its press has lasted that long (F73). `scePadRead` returns the newest
states when more are pending than asked.
Experiment 0026: `BC5_DIRECT_FRAME_PROFILE=1` journals one line per flip with the game thread's
time inside the host (sync, hints, prepare, list, CS, fence, the in-flight cap, CPU-side label
waits, event waits), the wait at the flip, the rest, the GPU's busy time and the soft CP's passes;
`BC5_DIRECT_FLIP_DEFER=1` (with jobs in flight) hands the flip to the completion thread instead of
waiting at it; `BC5_DIRECT_RING_ASYNC=1` lets the doorbell consumer's jobs go unwaited too;
`BC5_DIRECT_DCB_WAIT_MS=<ms>` (default 8) limits a game-thread cross-queue wait,
and `BC5_DIRECT_NO_CYCLE_BREAK=1` keeps waiting on a queue that waits for this buffer (the first
`BC5_DIRECT_PIECES`, which split a gfx buffer at an unsatisfied wait, faulted in run 123 and was
removed in cleanup batch 1; `BC5_DIRECT_PIECES_FULL` replaced it). Compute buffers
are split at every cross-queue wait with their register state replayed before each later segment
(`BC5_DIRECT_NO_TAIL_SPLIT=1` turns the split off). A doorbell queue deferred for more than a
second journals what its first unready buffer waits for.
Experiment 0027: the per-submission mapping list is sorted and `mapped()` is a binary search; the
backend assembles each submission's image in cached memory and copies it into the scratch once.
Haptics (F69): pad-speaker and vibration ports open on the controller's own four-channel audio
device (the first SDL output device named `DualSense`; `KYTY_BC5_PAD_AUDIO_DEVICE=<substring>`
picks another, `KYTY_BC5_NO_PAD_AUDIO=1` keeps the old behaviour); a port's frames go to channels
1–2 (speaker) or 3–4 (actuators). A pad port never blocks the game's audio thread: a removed
device drops the frames, a full queue is cleared (F72), and once a second the port looks for the
controller's device again and reopens it, closing the stopped one first, so the haptics come back
after the pad is unplugged and plugged in (F93). A pad is connected once, by its SDL instance id:
a game controller only through `SDL_CONTROLLERDEVICEADDED`, other joysticks through
`SDL_JOYDEVICEADDED`; before, a replugged pad left a ghost on player 1 and landed on player 2.
With two DualSense pads both pad ports use the first controller audio device SDL lists. The controller's sink and
its ALSA `PCM` control must be at 100 %: `pad-volume.sh` here sets both, re-running itself on the
host through `distrobox-host-exec` when called in the container, and with `--watch <pid>` keeps
them there every 3 s while that process lives (the ALSA control comes back at 76 % on every
plug-in, F94).
Logging (F75): `KYTY_BC5_LOG_WAITS=1` restores the `KernelWaitSema`/`Equeue wait` lines,
`BC5_GC_LOG=verbose` the gc layer's per-flip and per-ioctl lines (otherwise the first few of each
kind). The per-event input
debug lines of `window.cpp` are compiled out; use `KYTY_BC5_INPUT_TRACE=1`.
Ports from KytyPS5 (F76): a guest path under no mount point never reaches the host
(`fileSystem.cpp`, `sysLinuxFileIO.cpp`, upstream a107d1e); guest thread names reach the host
threads (`pthread.cpp`, upstream 199d0a9). Not taken: blocking short sleeps (upstream 6f24b03), the
game's command-buffer writer asserts with it.
Users (F77): one local user is logged in by default (`KYTY_BC5_LOGIN_USERS=<1..4>` for local
multiplayer); with four, a single-player game opens and reads four pad handles every frame.
Adaptive triggers (F78): `scePadGetTriggerEffectState` answers libScePad's state values (duaLib's
header: feedback 1/2, weapon 3/4/5, vibration 6/7) from the last `scePadSetTriggerEffect` and the
trigger's analog value, as KytyPS5 PR #1132 does; the trace logs the requests.
Pad audio knobs (F79): `KYTY_BC5_PAD_SPEAKER=main` keeps the pad-speaker ports on the default
output (the game sends some effects to the controller's speaker, as on the console), the haptics
still go to the pad; `KYTY_BC5_HAPTIC_GAIN=<float>` scales the actuators' stream (clipped);
`KYTY_BC5_INPUT_TRACE=1` also logs, once a second per pad port, the peak level reaching the pad.
Thread names (F83): the host's own threads carry names in `/proc` and `top -H` (`kyty-gpu`,
`kyty-present`, `kyty-cmdsched`, `kyty-pipeline`, `bc5-ring`, `bc5-cq<n>`, `bc5-labelwatch`,
`bc5-autopress`, `bc5-keyhold`, `kyty-thread` for the generic host thread class); the game's main thread is
`game-main` (F85); the guest's threads carry their own names since F76, and those it creates without
one are `guest-<n>`.
Pad stream layout (F80): the stream to the controller is six channels, speaker on 1–2 and
actuators on 5–6; SDL's pulseaudio backend (the only one in the build container) declares four
channels as FL FR FC LFE and PipeWire then mixes the actuator pair into the speaker, while six
channels are FL FR FC LFE RL RR under both backends and the last pair reaches the device's 3–4.
Confirmed in the game by the maintainer (2026-10-08).

AMM and AMPR (F87, experiment 0035): the AMM window is reserved where the host has room instead
of at a fixed 0x1000000000 over the title's own mappings; AMM pages without CPU bits get host
read/write (the host emulates the DMA that fills them); APR `WaitOnAddress` holds a submission
and those behind it until met, AMM-only submissions run at once, a `bc5-apr-wait` thread
re-checks; APR `MapBegin`/`MapDirectBegin` map their ranges; `SetBuffer`'s map flavour is
handled. `KYTY_BC5_AMM_TRACE=1` traces it all (and names the instruction behind a fault in a
reserved range).
Cleanup batch 4 (2026-10-15) removed the tools of the refit hunt and its neighbours: the watched
program's journal and CPU tree check `BC5_DIRECT_WATCH_PGM`, the refit guard
`BC5_DIRECT_REFIT_GUARD` and the dispatch split `BC5_DIRECT_SPLIT_AT_PGM` (experiment 0050; 0053's
`GPU_CHECK` + `DMA_SYNC` fixed the refit), the trust of indirect arguments `BC5_DIRECT_TRUST_DISPATCH`
and `BC5_DIRECT_TRUST_PGM` (0041 failed, 0052 replaced it), `BC5_DIRECT_GCR_CLEAR` (0044: slower)
and `BC5_DIRECT_IB_STABLE_CHECK` (0063).
Cleanup batch 3 (2026-10-15) removed the memory surveys `BC5_DIRECT_MAP_WHOLE_VMA`,
`BC5_DIRECT_MAP_GUEST_RANGES` and `BC5_DIRECT_CHUNK_STATS` (ADR 0006 decided the backing), the
display-buffer sampling at every flip `BC5_DIRECT_FLIP_SAMPLE`, `_PREFILL` and `_DUMP` (runs 60–76;
`BC5_DIRECT_RT_DUMP` replaced them) with `Bc5VideoOutBufferRange`, and `KYTY_BC5_AMM_LAZY_COMMIT`
(experiment 0035: the AMM failures had another cause).

Experiments 0036–0038 (the second title, F88–F90). AMM: the window is searched from 512 GiB
(titles place their heaps at fixed addresses above 0x1000000000), AMM pages carry the range
name `AMM` (so `BC5_DIRECT_EAGER_NAMES` can include them), APR submissions queue per priority
(after KytyPS5 c045f08), `WaitOnAddress` compare codes as AnyPS5 implements them;
`KYTY_BC5_AMPR_FILTER=<n>` sets the filter of AMPR completion events (default `EVFILT_USER`).
Audio and system: ATRAC9 vibration layouts (channel configurations 6–7) are decoded as mono and
dual mono instead of reaching past LibAtrac9's table (after KytyPS5 b10bd53); the entitlement
update event is queued after `AppContentInitialize` (after KytyPS5 62643c3). Direct path: the
views of direct and private memory are cached per change of the guest's ranges (a generation
counter in `VirtualRanges`), the device's mapping list is kept sorted
(`Device::sorted_mappings`), the GPU mappings are synced as soon as the guest's ranges change
(`BC5_DIRECT_NO_GEN_SYNC=1`: at most every 50 ms, as before); holes the guest has no range in
get a 2 MiB zero buffer under learned fault windows and after each eagerly imported heap of
32 MiB or more (`BC5_DIRECT_GUARD_KIB`, default 2048; `BC5_DIRECT_NO_SCRATCH=1` turns both
off). Compute IBs' `DISPATCH_INDIRECT` in the compute-queue form (address lo/hi, initiator) is
dropped; `BC5_DIRECT_MEC_INDIRECT=1` converts it for the GFX ring instead, which hung the GPU
and took the machine down in its first run (experiment 0038) — do not use it outside an
experiment. `BC5_DIRECT_WATCH_VA=lo:hi` (hex) journals every packet with a memory operand in
that range. Traces (experiment 0043: every `amm trace:` line starts with the monotonic clock, and
the per-call lines need `KYTY_BC5_AMM_TRACE=2`): `KYTY_BC5_AMM_TRACE=1` also reports short APR reads, AMPR event
registrations and triggers, and fixed mappings that replace live memory.

Experiment 0039: with `BC5_DIRECT_MEC_INDIRECT=1` the host rebuilds a compute IB that holds
compute-form `DISPATCH_INDIRECT`: each becomes SET_BASE index 1 with the compute shader type (the
page of its arguments), `PFP_SYNC_ME` and the GFX-form dispatch; the drop list and the executed
offsets are mapped between the two layouts; an IB with COND_EXEC has these dispatches dropped.
`BC5_DIRECT_MEC_ONLY_PGM` / `BC5_DIRECT_MEC_SKIP_PGM` (hex lists of compute program addresses,
COMPUTE_PGM_LO/HI) choose which run; the journal names each program once ("mec pgm").
Experiment 0059 (in progress): `BC5_DIRECT_SKIP_PGM=<hex list>` drops every dispatch of these
programs in any buffer; `BC5_DIRECT_SNAP=<va>:<bytes>:<every>` copies guest memory every <every>
submissions to the capture directory (8 files in turn, fsync'd; private data).
`BC5_DIRECT_FIND_VA=<lo>:<hi>` journals dispatches whose COMPUTE_USER_DATA pairs point into the range.
Experiment 0058: `BC5_DIRECT_UMR_ON_TIMEOUT=1` runs the root-owned read-only
`/usr/local/bin/bc5-gpu-hang-dump` (umr waves, CP registers, the gfx ring; fence info) on the
host through `distrobox-host-exec sudo -n` once a job has waited 0.9 s since its submission (at
most twice a run); the kernel's own ring reset comes ~2 s after a hang.
Experiment 0057: `BC5_DIRECT_INDIRECT_DRAWS=1` lets only `DRAW_INDIRECT` through (`=multi` also the
multi-draw packets); indirect draws checked at ≤ 2^20 vertices, ≤ 64 instances;
`BC5_DIRECT_IB_DUMP=<min>:<max>:<t0>:<count>[:<dir>]` dumps buffers of a size range (private).
Experiment 0056: `BC5_DIRECT_ALIASES=1` maps the memory of the windows in
`~/bc5-work/direct-aliases-pkg.txt` ("byte lo size") again at (byte << 40) + address (backend
`Device::map_alias`); unverified and dangerous with the indirect draws (F110).
Experiment 0069: with `BC5_DIRECT_FLIP_DEFER`, a graphics buffer's wait on a display buffer's flip
label waits (up to 100 ms) while a deferred flip of that buffer is queued, instead of clearing the
label. Experiment 0070: the label is cleared once KytyPlus has recorded the flip, i.e. read the
buffer (`Bc5VideoOutWaitFlipCopied`). Keeping it until the flip was presented (30 fps when frames
take a bit over 16.7 ms), releasing it when the flip is queued (tearing), and leaving the wait to
the GPU (experiment 0071, two machine resets) were removed in cleanup batch 1. `KYTY_BC5_READ_THREADS=<n>` (default 4) splits guest reads of
4 MiB and more; `KYTY_BC5_FLIP_TIMING=1` prints the flip preparation's timing.
ADR 0008 step 1: the host follows the graphics queue's full register state (`bc5::full_state`,
every cc/hib/dcb buffer, tables and nested buffers read from guest memory) for the pieces'
prefixes and the draw journal; a `piece check:` journal line every 10 s. (Experiment 0073's
offline comparison at every wait, `BC5_DIRECT_PIECE_CHECK`, was removed in cleanup batch 5.)
ADR 0008 step 2: `BC5_DIRECT_PIECES_DRY=1` builds the prefix at every game-thread dcb wait that
is not satisfied when reached (where `BC5_DIRECT_PIECES_FULL` would split), submits nothing
differently, and journals `pieces dry:` (splits, prefix size, build time, and whether each wait
was then kept for the GPU, served on the CPU or given up).
Experiment 0119: a piece goes to the GPU as one job with its full-state prefix in front (two jobs
let the ring thread's work in between: ASTRO BOT's tagged-address faults, experiment 0118).
`BC5_DIRECT_TAG_WATCH=1` journals address
registers with a non-zero bits 47:40 byte (CB/CMASK/FMASK/DCC `_BASE_EXT`, DB `_BASE_HI`, program
`_HI`) in dry prefixes and in the stream tracker.
ADR 0008 step 3, prepared and **not run** (GPU; only with the maintainer present):
`BC5_DIRECT_PIECES_FULL=1` splits a game-thread graphics buffer only at a wait that was not
satisfied, not kept for the GPU by ring order and not served within the limit. The head goes to
the GPU, the wait is tried again, and the rest follows behind the full-state prefix. Journal:
`piece:` (first 100) and `pieces full:` every 10 s.
Experiment 0055: `BC5_DIRECT_RING_ORDER_WAITS=1` leaves a cross-queue wait to the GPU when the last
pending label write of a job already on the ring satisfies it (backend `keep_wait_offsets`);
`BC5_DIRECT_DCB_WAIT_UNBLOCKED_MS`, `BC5_DIRECT_TRAP_STATS=1` (diagnostics).
Experiment 0054: `BC5_DIRECT_INDIRECT_DRAWS=1` lets DRAW_INDIRECT (0x24) and the
two multi-draw packets (0x2c, 0x38) through (the backend policy passes them now; off, the host
keeps dropping them); with `BC5_DIRECT_GPU_CHECK` the CP also checks an indirect draw's vertex
and instance counts; in a buffer with a given-up wait the indirect draws are dropped. The
second title's 12-channel float AudioOut2 port (data_format 0xc00) is opened as 8-channel float
and mixed down (libAudio2.cpp). `BC5_DIRECT_DROP_TALLY=1` journals the packets the filter took
out, per buffer kind and opcode, every 10 s.
Experiment 0052: `BC5_DIRECT_GPU_CHECK=1` (backend `FilterOptions::gpu_check_indirect`): the CP
checks every `DISPATCH_INDIRECT`'s group counts when it runs it, and the host no longer drops one
it will check for counts read at submit time; the refit guard also holds the refit back in a
buffer with a given-up wait.
Experiment 0051: the `direct by name (growth)` breakdown (every 512 MiB of imports, a walk of
every view with SEEK_DATA: 25–80 s on the game's thread while the second title loads) only with
`BC5_DIRECT_BREAKDOWN=1`.
Experiment 0050: `BC5_DIRECT_DMA_SYNC=1` and `BC5_DIRECT_PFP_SYNC=1` set the backend's
`dma_sync_before_dispatch` and `pfp_sync_indirect`.
Experiment 0049: `BC5_DIRECT_SHADER_DUMP=<dir>` writes every shader program a buffer points at
(the six graphics stages' and the compute program registers, set or loaded by pairs), 64 KiB
each, once; keep the directory private (a title's code).
Experiment 0048: borderless fullscreen at the display's resolution, live: F11, the *Video*
tab's box, or `Fullscreen=on|off` in the input file (also at start); presets 1.0 / 1.25 / 1.7 / 3.0
named 4K UHD, 1800p class, 1440p class, Full HD.
Experiment 0115: the timestamp scale is per title: `RenderScale.<TITLE_ID>=<k>` in the input file
applies to that title only (TITLE_ID from `param.sfo`), other titles' entries are kept on save,
and a plain `RenderScale=<k>` is ignored with a log line; a title without an entry runs with
untouched timestamps. The F2 *Video* tab reads and writes the running title's entry.
Experiment 0047: the timestamp scale is live: `RenderScale=<k>` (0.5–4) in the input file, and
the F2 menu's *Video* tab (presets 1.0 / 1.2 / 1.5 / 3.0, a slider, the main 3D view's size now,
Save). *Restart game* exits with code 75; the dev box's `play-astro.sh` and `play-pkg.sh` start
the emulator again on that code.
Experiment 0046: a timestamp scale k multiplies the 64-bit GPU timestamps a job's buffers wrote
(`RELEASE_MEM`/`EVENT_WRITE_EOP` with `DATA_SEL` 3) once the job is done; ASTRO BOT's dynamic
resolution follows them (×1.2: 3328×1872 at 59–60 fps instead of native 4K at 57). Its start
value from `BC5_DIRECT_TS_SCALE` applied to every title and was removed in cleanup batch 5; the
scale comes only from the title's own `RenderScale.<TITLE_ID>` (experiment 0115).
`BC5_DIRECT_PKT_STATS=1` also reports the render sizes the game sets (`sizes:` lines), and the
title's system parameter queries are reported once each on stderr (`bc5 system param`).
Experiment 0045: `BC5_DIRECT_MAX_IN_FLIGHT=<n>` (default 12, at most the backend's 64 scratch
slots minus the ring thread's jobs) is how many jobs fly before the game's thread waits; with
`BC5_DIRECT_FLIP_DEFER=1` and 24 ASTRO BOT's first level runs at 57 fps instead of 54.
Experiment 0044: `BC5_DIRECT_PKT_STATS=1` journals, every 10 s, the counts per kind of buffer of
dispatches, draws, `EVENT_WRITE` by event, `ACQUIRE_MEM` by `GCR_CNTL`, `RELEASE_MEM` and waits, as
the game wrote them (`pkt stats`).
Experiment 0042: `KYTY_BC5_RANGE_WATCH=lo:hi` (hex) writes every edit of the guest's ranges
overlapping that window to stderr with the monotonic clock; the journal's zero on that clock is
printed once (`bc5 clock`). A direct-memory heap the GPU touches before the CPU must be named in
`BC5_DIRECT_EAGER_NAMES` (pages are otherwise imported once the CPU has written them).
Experiment 0040: `BC5_DIRECT_HEAVY_PROBE=1` scans the memory operands of heavy IBs and makes
the memory sync urgent for an operand page not yet known to stay unmapped; pages still unmapped
are journaled once (`heavy probe:`, with the packet's dwords and the IB's `SET_BASE`s). Off by
default: it cost ASTRO BOT 6 ms a frame (run 152); the second title's `run-pkg.sh` turns it on.
`BC5_DIRECT_OPS_DUMP=<n>` journals the opcode sequence of the
first n large compute IBs with such dispatches. The backend's `FilterOptions::mec_indirect_base`
(one base per IB, with PFP_SYNC_ME inserted by `Device::submit`) is the earlier variant and is no
longer set by the host.

Experiment 0080: `run-pkg.sh` (in `~/bc5-work`, not in the repo) reads the settings file named by
`BC5_RUN_ENV` (default `~/bc5-work/bc5-run.env`).
Experiment 0083: `BC5_DIRECT_SOFTCP_POST_IB=1` runs the soft CP of an IB-packet submission on the
completion thread after its job (EOP events and dropped packets' writes once the GPU is done).
Experiment 0084: the driver's wait-idle and submit-done ioctls are counted in the journal (draining
the jobs in flight there changed nothing, F144; the knob was removed in cleanup batch 1).
Experiment 0087, prepared and **not run** (GPU; only with the maintainer present):
`BC5_DIRECT_DMA_SNAPSHOT=<min bytes>` copies the source of every `DMA_DATA` reading that many bytes
or more into a 64 MiB ring in guest flexible memory at submission and points the filtered packet
at the copy (backend `FilterOptions::dma_source`), for the second title's per-frame uploads from
rotating CPU staging (F146). Ring ranges not yet imported are not used.
Experiment 0088: `BC5_DIRECT_DRAW_MAX=<vertices>:<instances>` overrides the CP's indirect-draw limits
(default 1048576:64).
Experiment 0089: `BC5_DIRECT_DRAW_JOURNAL=<t0>:<buffers>` journals every draw and dispatch of the graphics
buffers from t0 s on (colour target 0, viewport, PS/ES/GS/CS programs, packet dwords).
Experiment 0090: `BC5_DIRECT_RT_DUMP=<t0>;<va>:<w>:<h>:<r11g11b10|r32f|rgba8>[;...]` detiles the listed colour
targets on the CPU once from t0 s on and writes PPM images to the capture directory (private).
Experiment 0092: the draw journal follows nested buffers; `BC5_DIRECT_DRAW_JOURNAL_FIND=<hex>[,...]` journals
draws and dispatches whose user data (or the descriptor tables it points to) hold one of the values.
Experiment 0093: the draw journal lists all enabled colour targets; `BC5_DIRECT_FIND_ALL=<t0>:<s>:<hex>[,...]` searches
the user data of every buffer kind for the values.
Experiments 0095–0098: `BC5_DIRECT_RT_DUMP` formats accept `-lin` (linear) and `-fam<n>` (KytyPlus TileBlockFamily),
and report the 2-bit alpha histogram of `rgb10a2`.
Experiment 0102, prepared and **not run** (GPU; only with the maintainer present): `BC5_DIRECT_AMM_PRT=1` maps the
title's AMM window (0x8000000000, 64 GiB) as PRT pages (`Device::map_prt_window`: reads 0, writes dropped) before
anything is imported there; the title's mappings replace those pages and their unmapping restores them, as RADV does
for sparse memory (F161: the second title's sparse UI layer). It ran in run 371: no fault, the background stays
black (F162).
Experiment 0103: `BC5_DIRECT_REMEMBER_UNMAPPED=1` remembers for 2 s the operand pages a forced sync left unmapped.
A light buffer (no draws, dispatches or nested buffers) whose only unmapped operands lie there does not force the
sync walk again; the packet is dropped either way. It saves the second title 9 ms a frame (F163).
Experiment 0104 (diagnostics, off by default):
- The draw journal's layer lines report what backs UI layer 0 for the guest and for the GPU.
- `BC5_DIRECT_RT_DUMP`:
  - a `layer:<w>:<h>:<fmt>` item dumps that layer;
  - a surface in the AMM window is read only when the guest maps all of it;
  - `rgba8` dumps report an alpha histogram and write the alpha as a PGM.
- `BC5_DIRECT_DRAW_JOURNAL_WATCH=1` journals only the draws and dispatches that touch a surface of
  the UI layer's size an automatic AMM map created (`bc5_watch_surface`). Each line carries the
  colour state, the export format and the UI shaders' paint data.
- `KYTY_BC5_AMM_ZERO_AUTO=1` (libAmpr.cpp) zero-fills fresh automatic AMM maps. With
  `KYTY_BC5_AMM_TRACE=1`, maps of 1 MiB or more report their non-zero pages.

Experiment 0105:
- `BC5_DIRECT_TS_LOG=<t0>` journals the raw values of the title's own GPU timestamps for each job.
- The draw journal shows the parameter and result blocks of the frame-pacing program 0x11d0288100.
- `BC5_DIRECT_PACE_FIX` rescaled that program's target time and wait limit. Experiment 0115 found
  the "170 MHz" was our own shared timestamp scale; with timestamps left true the title paces
  itself, and the knob was removed in cleanup batch 5.

Experiment 0112: `KYTY_BC5_APR_PARALLEL=<n>` (`libAmpr.cpp`, off by default) runs a run of
consecutive APR ReadFile commands on n threads. A run with overlapping destinations stays in
order, and the commands after the run still follow it. With 8, the second title's start-up logo
shortens by 2 s.
