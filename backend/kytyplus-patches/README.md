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
