# 0010 — Sony's own `libSceAgc` from the game dump, LLE-loaded in an HLE host

**Question.** Experiment 0009 found that the ASTRO BOT dump ships `fakelib/libSceAgc.sprx` and
`libSceAgcDriver.sprx` as plaintext SELFs, and that KytyPlus's LLE loader lets pack-dir modules take
precedence over its HLE. If the game is linked against Sony's real AGC libraries instead of the
emulator's HLE, what does the boundary between those libraries and the kernel look like, i.e. what
would BC5 have to provide for Sony's DCB encoder to drive our backend?

**Setup.** As experiment 0009 run 2 (BC-250, `ubuntu` distrobox, KytyPlus `f266548` + the 6-line
guest-memory patch, 13.5 GiB guest memory, `bc5-mount` mount of the maintainer's own container), plus
`SHADPS4_SYSMODULES_PACK_DIR=<mount>/fakelib` ([`raw/command.txt`](raw/command.txt),
[`raw/run-astro-kytyplus.sh`](raw/run-astro-kytyplus.sh)). 90 s timeout. Disassembly with GNU
`objdump -b binary` on the SELF text segment (SELF entry 1 → file offset 0xaa0 = VA 0). Capture under
`~/bc5-data/captures/kytyplus-20260930-0951` (not committed).

**Result.**

1. **All five `fakelib` modules load and relocate**: `libSceAgc` at 0x940000000 (0x561a0 bytes),
   `libSceAgcDriver` at 0x950000000 (0x270a0), `libSceAmpr` at 0x960000000, `libScePlayGo` at
   0x980000000, `libScePsml` at 0x990000000. Their exports now win over KytyPlus's HLE.
2. **Unresolved imports** of the two AGC modules, 29 in total
   ([`raw/unresolved-imports.txt`](raw/unresolved-imports.txt), names via shadPS4's public NID table):
   - `libSceAgcDriver` → libkernel: `ioctl`, `mmap`, `kevent`, `sceKernelMapNamedSystemFlexibleMemory`,
     `sceKernelGetMainSocId`, `sceKernelGetAppInfo`, `sceKernelGetCompiledSdkVersion`,
     `sceKernelIsNeoMode`, `sceKernelSetProcessProperty`, `getuid`, `sceKernelError`, one PS5-only NID;
     VideoOut: `sceVideoOutSysGetBus`, `sceVideoOutSubmitEopFlip`, `sceVideoOutGetBufferLabelAddress`.
   - `libSceAgc` → libkernel: `_ioctl`, tool memory (`sceKernelAllocateToolMemory`,
     `sceKernelMapToolMemory`, `sceKernelReleaseToolMemory`), `sceKernelTitleWorkaroundIsEnabled`,
     `sceKernelGetAppCategoryType`, `sceKernelGetMainSocId`, `sceKernelGetAppInfo`, `sceKernelError`,
     three PS5-only NIDs; Sysmodule: `sceSysmoduleLoadModuleInternal`, `…ByNameInternal`; RegMgr:
     `sceRegMgrNonSysGetInt`.
   Everything else the two libraries import resolved against KytyPlus's HLE.
3. **Execution reaches Sony's driver.** The game runs 30 s (4,947 log lines), calls into `libSceAgc`
   and `libSceAgcDriver`, and faults at `libSceAgcDriver+0x66ac`:
   `movl $0x98, 0xb7250(%rax)` with `rax = 0`. `rax` is the return of the one-instruction getter at
   `+0xa0e0`, `mov 0x18b29(%rip),%rax` → global at `+0x22c10`, the driver context pointer, still NULL
   because the driver's initialisation could not complete on the stubbed kernel imports above
   (tool memory, flexible memory, `mmap`/`ioctl`). The stubs recorded as called just before the fault
   are tool-memory, flexible-memory, timer-event and two VideoOut functions.
4. 0 command buffers dumped by KytyPlus's own path, as expected: with LLE `libSceAgc`, the HLE
   `sceAgcDcb*` builders are no longer in the loop at all.

**Verdict.** The route "HLE kernel + Sony's `libSceAgc`/`libSceAgcDriver` from the maintainer's own
dump + BC5 behind the `/dev/gc` boundary" is **concrete and small on the library side**: the two AGC
modules need 29 imports that the HLE host does not provide, and about half of those are exactly the
device boundary BC5 wants to own (`mmap`/`ioctl`/`kevent` on the GPU device, flexible memory, EOP flip,
buffer labels). This experiment does not build any of it; it prices it. What it does not price is the
kernel-side work in KytyPlus that already blocks the game before graphics (experiment 0009). The
semantics of the `/dev/gc` ioctls themselves remain the phase-1 question (HANDOFF Q2, F12: RPCSX
handles `0xc0488131`/`0xc0188132`), now answerable from Sony's driver binary in the dump rather than
from firmware.
