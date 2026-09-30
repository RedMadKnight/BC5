# 0011 — First command buffers built by Sony's `libSceAgc`, captured at `/dev/gc` (gate G1b)

**Question.** Phase 1b (docs/PHASES.md, D11): with the 29 missing imports implemented in KytyPlus and
a `/dev/gc` device of our own, does Sony's `libSceAgcDriver` (LLE from the maintainer's dump)
initialise, and does the game's first submission reach us as a decodable DCB?

**Setup.** BC-250 dev box, 2026-09-30 10:11–10:19, `ubuntu` distrobox. KytyPlus `f266548` with
[`backend/kytyplus-patches/0001-bc5-lle-agc.patch`](../../backend/kytyplus-patches/0001-bc5-lle-agc.patch)
(`src/libs/bc5LleAgc.cpp` + pseudo-devices + filler-NOP fix), built as in experiment 0009. Game: the
maintainer's own `PPSA21567` container via `bc5-mount`; `fakelib/` as the LLE pack dir; guest memory
13.5 GiB. Scripts: [`raw/run-astro-kytyplus.sh`](raw/run-astro-kytyplus.sh),
[`raw/lle-cycle.sh`](raw/lle-cycle.sh) (rebuild + run + summary). Capture dir
`~/bc5-data/captures/kytyplus-20260930-1019` (not committed); the four command buffers themselves
(1,004 bytes, no shader or data blobs, only the packets Sony's library wrote) are in
[`raw/dcb/`](raw/dcb/), decoded by `bc5-agc` into [`raw/bc5-agc-dump.txt`](raw/bc5-agc-dump.txt) and
[`raw/bc5-agc-report.txt`](raw/bc5-agc-report.txt). Signatures and ioctl layouts: experiment 0010,
RPCSX `rpcsx/iodev/gc.cpp` @ `e8ae148`.

**Result.**

1. **Driver initialisation succeeds.** Sequence seen at our device (counts in
   [`raw/ioctl-counts.txt`](raw/ioctl-counts.txt)): `open("/dev/gc", O_RDWR)`; ioctl `0xc004812e`
   (capability flags); `mmap(0xfe0200000, 16 KiB, cpu write | gpu write, MAP_SHARED, fd)`; nine
   `sceKernelMapNamedSystemFlexibleMemory` areas at fixed addresses (`SceGnmGpuInfo` 1 MiB at
   0xfe0300000, then from 0xf00000000: `SceGnmTrapCode`, `SceGnmTrapData`, `SceGnmDdid`,
   `SceGnmEopFifo`, `SceGnmShadowRegInfo`, `SceGnmCwsr` 16 MiB, `SceGnmMisc`, `SceGnmACQRB`);
   `sceKernelGetAppInfo`; ioctl `0x80888123` (136 bytes in, presumably the area table); **56 ×
   `0xc0408121`** (64 bytes in/out: `{1|2, 2}, {0x2b.., 0..7}, 16 KiB range, 0xfe0200000, 0xc,
   page in the EOP FIFO, 0x1000` — queue registration, two engines × pipes × 8 queues);
   `0x80048134`, `0x80048126`; `sceKernelSetProcessProperty("Sce.Debug:Gn2..4", areas)`;
   `0xc010813b`; `/dev/dipsw` reads; eight `kevent` EV_ADD of `EVFILT_GRAPHICS` (ident 0 ×5, then
   0x40, 0x48, 0x46); `0xc0108139`. Every unhandled ioctl answered with zeros was accepted.
   The driver context pointer that was NULL in experiment 0010 is now set.
2. **First submission, 30 s after launch**, exactly the two PS5 submit ioctls RPCSX knows (F12):
   - `0xc0488131` (submit header): `contextControl = {0xc0012800, 0, 0}` (a CONTEXT_CONTROL
     packet), `cmds[0]` = IB at 0xfe0000000, **150 dwords**, `cmds[1]` = IB at 0xfe003a200,
     2 dwords, `cmds[2]` empty. Answers the remaining sub-question of Q2.
   - `0xc0188132` (submit list): one entry, DCB at 0xfe0042920, **96 dwords**.
3. **Decode** (`bc5-agc report`, after adding `PREAMBLE_CNTL` 0x4a and `LOAD_UCONFIG_REG_INDEX`
   0x64 from AMD PAL's opcode table): 4 streams, 42 packets, 21 opcodes, **0 unknown**, 0 unresolved
   register offsets, 0 CU-mask writes. The 150-dword IB is a state preamble: `PREAMBLE_CNTL`,
   `COND_EXEC`, `CONTEXT_CONTROL`, three `LOAD_{CONTEXT,SH,UCONFIG}_REG` from the shadow-register
   tables at 0xfe0008000 (the `SceGnmShadowRegInfo`/`Sce.Debug:Gn4` area), `WRITE_DATA`. The
   96-dword DCB is the start of a frame: `COND_EXEC`, `RELEASE_MEM`, `SQ_THREAD_TRACE_USERDATA_2/3`
   markers, `EVENT_WRITE`, `CLEAR_STATE`, `ATOMIC_MEM`, `LOAD_*_REG_INDEX`, `NUM_INSTANCES`,
   `SET_UCONFIG_REG_INDEX`, `INDEX_BASE`, `INDEX_BUFFER_SIZE`, `SET_BASE`, `ACQUIRE_MEM` (gfx10
   8-dword form), `COPY_DATA`.
4. **KytyPlus's own GPU interpreter cannot consume these buffers**: first it took the filler NOP
   `0xffff1000` as 16,385 dwords (fixed in the patch: COUNT 0x3fff = one dword), then it rejected
   the gfx10 `ACQUIRE_MEM` (`pm4Handlers.cpp:1743` only knows the gfx9 form). Its command-buffer
   dump feature has the same NOP bug. The interpreter models PS4 GNM and Kyty's own HLE-built
   packets; it is not a PS5 CP.

**Verdict.** **Gate G1b passed**: DCBs built by Sony's `libSceAgc` from ASTRO BOT were captured on
the BC-250 through our `/dev/gc` and decode with `bc5-agc` with zero unknown opcodes; the ioctl list
is recorded. This is the first console-format command stream the project has (F15 explains why
Prosper's were not), obtained without a firmware dump. Next: the game stops after the first submit
because nothing completes it — the DCB's `RELEASE_MEM`/labels are never written and the
`EVFILT_GRAPHICS` events never fire. Rather than teaching KytyPlus's gfx9 interpreter PS5 packets,
BC5 needs its own minimal CP for the synchronisation packets (`WRITE_DATA`, `RELEASE_MEM`,
`COND_EXEC`, `ATOMIC_MEM`, `WAIT_REG_MEM`, `COPY_DATA`, `INDIRECT_BUFFER`) that completes submits
immediately; that keeps the game producing frames for phase 1 and is the seed of the phase-3 CP.
