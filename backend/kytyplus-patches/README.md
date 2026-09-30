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

Environment:

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
