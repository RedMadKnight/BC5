# 0012 — ASTRO BOT renders whole frames through Sony's `libSceAgc` into a BC5 soft CP

**Question.** After the first submit (experiment 0011) the game stopped. Phase 1b tasks 4–5: what
blocks it, and can a minimal BC5 command processor behind `/dev/gc` — one that only executes the
synchronisation packets and completes every submit at once — keep the game producing frames, so that
phase 1 has a stream of console-format command buffers? What do those buffers say about Q3 (CU
masks) and Q4 (unknown registers/opcodes)?

**Setup.** BC-250 dev box, 2026-09-30 10:20–11:00, `ubuntu` distrobox. KytyPlus `f266548` +
[`backend/kytyplus-patches/0001-bc5-lle-agc.patch`](../../backend/kytyplus-patches/0001-bc5-lle-agc.patch)
as of this experiment (soft CP, queue consumer, fiber and fault fixes, diagnostics). Game and mount as
in 0011; LLE pack dir `fakelib/`; 13.5 GiB guest memory. Runs of 45–150 s through
[`raw/lle-cycle.sh`](raw/lle-cycle.sh); thread dumps with gdb 16 ([`raw/run-astro-gdb.sh`](raw/run-astro-gdb.sh),
[`raw/gdbcmds.txt`](raw/gdbcmds.txt), or `gdb -p` — `ptrace_scope` is 0 on the box). Decoding on the
laptop with `bc5-agc` over the 718 captured buffers of run `kytyplus-20260930-1055` (5.2 MB, not
committed; reports in `raw/`).

**Result.**

1. **Why the game stopped after one submit (three findings, each fixed in the patch).**
   - KytyPlus's GPU interpreter rejects PS5 buffers (filler NOP `0xffff1000` taken as 16,385 dwords;
     gfx10 `ACQUIRE_MEM`). Not fixed beyond the NOP: the soft CP replaces the interpreter for these
     buffers (`BC5_GC_MODE=kyty` forwards them again).
   - The stall seen since experiment 0009 was **a KytyPlus fiber bug on Linux**: `FiberSaveContext`
     read the return address from `(%rsp)`, but clang emits a `push %rbp` prologue for that
     `noinline, returns_twice` function, so the saved `rip` was the caller's frame pointer and
     `FiberRestoreContext` jumped into the stack (Execute fault at 0x7efdf2b60). Both helpers are now
     naked functions. The crash was invisible because KytyPlus routed the instruction-fetch fault
     through its GPU page tracker, whose synchronous round trip to an idle GPU thread deadlocks;
     Execute faults now bypass it.
   - With those fixed the game rendered a few frames and then waited on `Gpu::EopEqCompute`
     (4.6 million timed-out `sceKernelWaitEqueue` calls in 150 s): compute work never completes.
     Compute is not submitted through ioctls. The driver registers **56 queues** at init (ioctl
     `0xc0408121`: engine 1|2, pipe 0..3, queue 0..7, slot `d` = 1..0x38, a 16 KiB ring in
     `SceGnmACQRB`, the mmap'd submit page as doorbell page, a page in `SceGnmEopFifo` as read-pointer
     home). Observed protocol: the submit page is an array of u64 **write pointers in dwords indexed by
     `d − 1`** (8 → 0x18 → 0x20 for slots 0x21 and 0x29 while their rings gained `INDIRECT_BUFFER`
     packets). The soft CP now polls every queue at 1 kHz, executes the packets between its read
     pointer and the game's write pointer, publishes the read pointer at `rptr_addr`, and fires the
     compute EOP events (idents 0x48 and 0x46 both, until the right one is pinned down).
2. **The game now runs its render loop.** Run 1055 (150 s): 48 submit headers + 228 submit lists
   (273 DCBs: 47 under 100 dwords, 90 of 100–999, 129 of 1k–9k, 6 of ≥10k), 45 EOP flips
   (`sceVideoOutSubmitEopFlip` flip_arg 1..0x2d), 80,241 packets executed by the soft CP, 718 buffers
   captured (48 context-control, 374 DCB, 296 compute IBs), `EopEqCompute` waits down to 92. New
   thread names show the game moving on to loading (`RoomLoad_ATQT`, `ProductNextLoad_ATQT`,
   `LevelTask_ATQT`, `VideoPlayer*`). The window stays black: nothing is rendered by design.
3. **Decode** ([`raw/bc5-agc-report.txt`](raw/bc5-agc-report.txt), per kind `-cc/-dcb/-ib1`):
   137,181 packets, 34 opcodes, **0 unknown** after adding `GET_LOD_STATS` 0x8e (PAL names it
   `IT_GET_LOD_STATS__APU103`, i.e. specific to the PS5-class APU) and `WAIT_REG_MEM64` 0x93. Real
   work: `DRAW_INDEX_AUTO` 1,292, `DRAW_INDEX_INDIRECT` 46, `DRAW_INDEX_OFFSET_2` 14,
   `DISPATCH_DIRECT` 1,931, `DISPATCH_INDIRECT` 202, `DMA_DATA` 1,233, `RELEASE_MEM` 34,670,
   `WRITE_DATA` 11,493, `ACQUIRE_MEM` 7,913, `WAIT_REG_MEM` 3,260. Registers: 99 named, **1
   unresolved** ([`raw/register-write-counts.txt`](raw/register-write-counts.txt)).
4. **Q3 answered**: the compute buffers write `COMPUTE_STATIC_THREAD_MGMT_SE0..3 = 0xffffffff`
   148 times each (every compute dispatch preamble; all four SEs although the chip has two), plus the
   unresolved SH register `mm 0x2e80 = 0` in the same group ([`raw/cu-mask-values.txt`](raw/cu-mask-values.txt)).
   The graphics buffers write no CU mask. So BC5's 36/40 policy must AND its mask into these writes.
5. **Q4, first data**: one unresolved offset (`sh+0x280`, mm 0x2e80, always 0, written with the CU
   masks) and one APU-only opcode (0x8e, 92 packets, mostly all-zero payload). The heaviest writes
   are Sony markers (`SQ_THREAD_TRACE_USERDATA_2/3`: 34,134) and user data (`COMPUTE_USER_DATA_*`,
   `SPI_SHADER_USER_DATA_PS_*`).

**Verdict.** Phase 1b tasks 4 and 5 done. The track-B host now delivers a continuous stream of
console-format graphics and compute command buffers built by Sony's own library, with the game
progressing past its first frames without a firmware dump. Three of KytyPlus's defects were fixed
along the way (offered upstream via the patch). Q3 is answered (masks written, all ones, AND them);
Q4 has its first two entries. Open: the 47 `0xc0088133`/48 `0xc0108139` ioctls after each submit are
answered with zeros (the game does not mind yet); which of 0x46/0x48 is the compute EOP; the engine
→ compute mapping is a guess (`a == 2`); `mm 0x2e80`; the game's own `GAME:` log lines do not appear
in KytyPlus's printf file, so its progress is inferred from thread names.
