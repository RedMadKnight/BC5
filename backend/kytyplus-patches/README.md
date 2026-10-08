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
SHADPS4_SYSMODULES_PACK_DIR=$HOME/bc5-data/mnt/PPSA21567/fakelib \
KYTY_GUEST_MEMORY_MB=13824 \
BC5_GC_DUMP_DIR=$HOME/bc5-data/captures/<run>/gc \
kyty_emulator --game $HOME/bc5-data/mnt/PPSA21567
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
(compute doorbell rings to the GPU, step e), `BC5_DIRECT_PIECEWISE=<n>` (submit #n one packet at a
time with a NOP probe after each, for hang isolation), `BC5_DIRECT_SELFTEST=1`. The host revalidates
its 1:1 mappings against `/proc/self/maps` on every sync, journals every `LOAD_*_REG[_INDEX]` table
before a submit, and its soft CP skips the memory side effects of packets the GPU executed.
`KYTY_BC5_ALL_RW=1` keeps every readable guest page CPU-writable (the executable's r-x/r-- segments
hold shader code and rodata; a writable userptr is the only kind libdrm can put in a BO list, see
`backend/src/direct.cpp`). `Bc5ForEachMappedRange` (memory.cpp) enumerates the guest's mapped ranges.
Step (d) knobs: `BC5_DIRECT_HINT_MIB`/`BC5_DIRECT_HINT_BELOW_MIB` (render-target windows, 32 MiB
each side), `BC5_DIRECT_NO_HINTS`, `BC5_DIRECT_LEARNED` (fault-learned regions file, default
`~/bc5-work/direct-learned.txt`), `BC5_DIRECT_REOPEN=1` (reopen the device after a ring reset),
`BC5_DIRECT_TABLES_FULL=1` (journal whole LOAD tables), `BC5_DIRECT_MAP_GUEST_RANGES=1` (survey only).

Added on 2026-10-01 (experiment 0016, runs 67–72): `BC5_DIRECT_SHADER_DUMP=1` (shader programs and
the memory their user-data registers point at, as `shader-<va>.bin` / `mem-<va>.bin` in the capture
directory; never committed), `BC5_DIRECT_RANGES_DUMP=1` (the guest's mapped ranges with physical
offsets), `BC5_DIRECT_PIPESTATS=1` (`SAMPLE_PIPELINESTAT` before and after every frame DCB, needs
`BC5_DIRECT_GDS_SHADOW=1`), `BC5_DIRECT_PROBE_VA=<hex>[:bytes]` (pagemap state and bytes of one
guest address, journaled when they change), `BC5_DIRECT_NO_PAGEMAP=1` (residency from `mincore()`
alone; by default swapped-out pages count as resident), `BC5_DIRECT_NO_TAIL_SPLIT=1` (do not split
a compute IB at a wait followed only by signalling packets), `BC5_DIRECT_FLIP_PREFILL=1` (a
0x5a5a5a5a pattern at the display buffer's sample points after each flip). The flip label of a
buffer is cleared at `SubmitEopFlip`. With `KYTY_BC5_ANON_BACKING=1` a view whose protection
changes is re-protected with `mprotect` instead of being mapped again (which zeroed it).
The context-state stack emulation (`Device::set_state_stack`, F35) is on by default since run 75;
`BC5_DIRECT_NO_STATE_STACK=1` turns it off. `BC5_DIRECT_STATE_STACK=1` in `maponly` is a dry run
that journals what the emulation would do. `BC5_DIRECT_FLIP_DUMP=<every n>` writes the raw
display buffer of every n-th flip into the capture directory (at most six files).
`BC5_DIRECT_DRAWSTATS=<min dwords>` (with `BC5_DIRECT_PIPESTATS=1`): pipeline counters per
marker-delimited section of the first six DCBs of at least that many dwords.
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
through `/dev/udmabuf` and maps them at the views' addresses. `BC5_DIRECT_CHUNK_STATS=1` journals
what chunk sizes would pin (anonymous backing).
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
`BC5_DIRECT_NO_CYCLE_BREAK=1` keeps waiting on a queue that waits for this buffer, and
`BC5_DIRECT_PIECES=1` splits a gfx buffer at an unsatisfied wait (faults, run 123). Compute buffers
are split at every cross-queue wait with their register state replayed before each later segment
(`BC5_DIRECT_NO_TAIL_SPLIT=1` turns the split off). A doorbell queue deferred for more than a
second journals what its first unready buffer waits for.
Experiment 0027: the per-submission mapping list is sorted and `mapped()` is a binary search; the
backend assembles each submission's image in cached memory and copies it into the scratch once.
Haptics (F69): pad-speaker and vibration ports open on the controller's own four-channel audio
device (the first SDL output device named `DualSense`; `KYTY_BC5_PAD_AUDIO_DEVICE=<substring>`
picks another, `KYTY_BC5_NO_PAD_AUDIO=1` keeps the old behaviour); a port's frames go to channels
1–2 (speaker) or 3–4 (actuators). A pad port never blocks the game's audio thread: a removed
device drops the frames, a full queue is cleared (F72).
Logging (F75): `KYTY_BC5_LOG_WAITS=1` restores the `KernelWaitSema`/`Equeue wait` lines,
`BC5_GC_LOG=verbose` the gc layer's per-flip and per-ioctl lines (otherwise the first few of each
kind), `BC5_DIRECT_FLIP_SAMPLE=1` the per-flip sampling of the display buffer and recent targets
(the diagnostic of runs 60–76, off by default: it ran on the game's thread). The per-event input
debug lines of `window.cpp` are compiled out; use `KYTY_BC5_INPUT_TRACE=1`.
Ports from KytyPS5 (F76): a guest path under no mount point never reaches the host
(`fileSystem.cpp`, `sysLinuxFileIO.cpp`, upstream a107d1e); guest thread names reach the host
threads (`pthread.cpp`, upstream 199d0a9). Not taken: blocking short sleeps (upstream 6f24b03), the
game's command-buffer writer asserts with it.
