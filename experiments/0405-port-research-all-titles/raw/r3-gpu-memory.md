# R3: GPU and memory side, what the related projects handle that our host does not (2026-11-04)

This redoes the GPU and memory part of exp 0402 §3 under the maintainer's rule of 2026-11-03 23:0x: **the host must
be complete and correct for any title**. Rows are not judged by whether our two titles show a symptom. The only valid
skips are "we already match (file:line)" and "licence/provenance not acceptable". This is read-only research on the
laptop. There was no box access, no ssh and no edits to existing files. No Sony material was read.

## Sources and abbreviations

| Tag | Project, commit, licence | How it was read |
|---|---|---|
| AP | AnyPS5 `4f41f4c37`, GPL-2.0-only | clone; paths under `core/libs/prx/`; `APX/` = `libSceAgcDriver/Execution/`; "AP-debt Ln" = `docs/dev/debt/libSceAgcDriver.md` line n; "AP-kdebt Ln" = `docs/dev/debt/libkernel.md` line n |
| KP | KytyPS5 `dfec14a`, GPL-2.0 (LICENSE) | `git show dfec14a:<path>` (the work tree is at 4644c52); `KPH` = `src/graphics/guest_gpu/command_processor/pm4Handlers.cpp` |
| SH | shadPS4 `60c42b9`, GPL-2.0-or-later (SPDX) | clone; `SHL` = `src/video_core/amdgpu/liverpool.cpp` |
| RX | RPCSX `e8ae148`, GPL-2.0 (LICENSE) | clone |
| SE | sharpemu `514d766`, GPL-2.0-or-later (SPDX) | `git show HEAD:<path>` (no work tree) |
| ME | Mesa `ab2374a` (`refs/mesa_mesa`), MIT | packet facts only; nothing is ported from it |

**Our code:**

- `lle` = `…/scratchpad/e4/full/src/libs/bc5LleAgc.cpp`.
- `mem` = `…/e4/full/src/kernel/memory.cpp`.
- `lk` = `…/e4/full/src/libs/libKernel.cpp`.
- `BE/` = `C:\Users\kjani\Downloads\bc5\bc5-0401\backend\`.
- `tsv` = `BE/policy/pm4-policy.tsv`. Its line 11 is `default-op drop`: every opcode the table does not list is
  NOP-ed before submission.
- An unregistered NID falls to the loader stub (`e4/full/src/loader/runtimeLinker.cpp:345-382`). The stub returns 0
  and writes no outputs.

**Method:**

- The GPU side was read directly by this session:
  - AP `Pm4.cpp`, `PacketExecution.cpp`, `Submission.cpp`, `VideoOutput.hpp` and the AgcDriver debt notes;
  - KP's dispatch table and handlers;
  - SH `liverpool.cpp` and `pm4_cmds.h`;
  - RX `iodev/gc.cpp`, `gpu/Pipe.cpp` and `DeviceCtl.cpp`;
  - SE's Agc exports.
- The memory side was audited by one sub-agent, which read all five projects against `mem`, `lk` and the shims in
  `lle`. I spot-checked these lines, and each matches what the sub-agent reported:
  - `mem`: 3974-3997, 2963-2966, 2867-2873, 3316, 2394 and 3678;
  - `lk`: 2466-2467 and 3458;
  - `lle`: 7698-7700;
  - the nine missing NIDs, which I re-hashed.
- Sony-specific packet encodings are cited only where two independent public projects agree (KP and AP for the
  custom NOP sub-codes and the flip packet). An encoding from one project alone is marked TODO(verify).

**Exclusions held:**

- In flight elsewhere:
  - AMM PRT commands;
  - Ampr MultiMap/Remap/ModifyProtect and the waits;
  - the submit-time table catcher;
  - param.json memory sizing, including module-segment charging;
  - acb queue state (exp 0403), which covers AP/KP DISPATCH_RESET and AP's refusal of `COMPUTE_PGM`;
  - fast-launch crumbs (exp 0404).
- Provenance: §Skips (b).

## Ranked table

Effort: S ≤ a day, M a few days, L weeks. Every **e4-now** row is S effort and well sourced. It sits behind its own
default-off switch, read with `bc5::env_on(getenv("BC5_R3_<ID>"))` (`BE/include/bc5/env_flag.hpp`). It does not change
GPU submission by default, and a CPU test can check it. The port specs follow the table.

| # | ID | What they do that we do not | Source (commit, lines) | Licence | Ours | Eff. | Risk if absent / of the port | Verdict |
|---|---|---|---|---|---|---|---|---|
| 1 | G1 | **`kevent` honours its timeout.** A `{0,0}` timeout polls and returns 0; a timed wait returns 0 on expiry. Ours ignores the timespec and blocks until an event arrives. | FreeBSD kevent(2); AP `libkernel/Equeue/src/Kqueue.cpp`; our own `KernelWaitEqueue` already takes a timeout (`e4/kernel/eventQueue.cpp:413-454`) | AP GPL-2.0-only (semantics only) | `lle:7749-7758` (`(void)timeout` at 7756). This shim is the host's only `kevent` (RW-GEfpnsqg, `lle:7964`) | S | A title thread that polls hangs forever / none | **e4-now** |
| 2 | M1 | **`mprotect`/`mtypeprotect` over gaps or unmapped space** changes the mapped parts and returns 0, even for a fully unmapped range (measured). Ours EXITs the host. | AP `libkernel/DirectMemory/Export.cpp:326-330` → `DirectMemory.cpp:1484-1585`; SH `src/core/memory.cpp:1118-1178`; AP-kdebt L172 (measured) | AP GPL-2.0-only, SH GPL-2.0-or-later | `mem:3990-3997` (EXIT "not fully mapped"), `mem:3974-3977` (EXIT on overflow) | S | Host crash / none | **e4-now** |
| 3 | M2 | **The `mmap` shim**: (a) a non-FIXED hint is only a hint; (b) prot 0 stays no-access. Ours maps every non-null address FIXED, which replaces live mappings, and promotes prot 0 to 0x33. | SH `src/core/libraries/kernel/memory.cpp:753-816`; AP `libkernel/DirectMemory/PosixMemory.cpp:145-249`; SE `KernelMemoryCompatExports.Mmap.cs:10-42` | GPL (all) | `lle:7693-7718` (7698-7700, 7703, 7716). The shim is the host's only `mmap` (BPE9s9vQQXo) | S | Silent corruption of title mappings; guard pages readable / Sony's driver maps at a fixed address: keep that path | **e4-now** |
| 4 | G2 | **`MEM_SEMAPHORE` (0x39) signal**: op 6 sets the 64-bit word to 1 (signal type bit 20) or adds 1. Ours NOPs the packet (`tsv:11`) and the soft CP ignores it, so the signal is lost. AP-debt L62 records PPSA03396 signalling after compute dispatches. | AP `APX/src/Pm4.cpp:507-512, 1130-1147`; KP `KPH:2077-2088`; SH `SHL:799-809, 1128-1138` and `pm4_cmds.h` `PM4CmdMemSemaphore`; SE `src/SharpEmu.Libs/Agc/AgcExports.MemSemaphore.cs` (builder: `op<<29 | type<<20 | mailbox<<16`); ME `src/amd/common/sid.h:88` | GPL (all) | missing: `tsv:11`; soft CP `lle:863-888` has no case | S | Waiters (CPU or other queues) never wake / none (soft CP only) | **e4-now** |
| 5 | G3 | **`MEM_SEMAPHORE` wait**: op 7 holds the queue until the word is non-zero, then subtracts 1 atomically. | as G2: AP `Pm4.cpp:1148-1169`, KP `KPH:2077-2088`, SH `SHL:799-809` | GPL | missing | M | Later work runs before the producer / a host-side gate is needed, like the cross-queue waits (`lle:2953`, `acb_ready`) | later |
| 6 | G4 | **`REWIND` (0x59), detect**: a REWIND whose valid bit (31) is clear stops the parser until the CPU sets the bit; the commands after it are then fetched fresh. Ours NOPs REWIND, and the IB was copied at submit, so the stale or zero tail runs immediately. AP-debt L214 shows such a buffer in PPSA15246. | AP `APX/src/Pm4.cpp:497-500`, `APX/include/Pm4.hpp:162-163`; KP `KPH:1324-1333`; SH `SHL:815-824`; SE `src/SharpEmu.Libs/Agc/AgcExports.ControlFlow.cs:13-115`; ME `sid.h:206` ("GFX8+ [any ring]") | GPL | missing (`tsv:11`; filter copy `BE/src/policy.cpp:405-693`) | S (catcher) | Garbage tail on the GPU (hang class) / none (count and journal only) | **e4-now** |
| 7 | G5 | **`REWIND`, execute**: split the IB at an invalid REWIND, CPU-wait for the valid bit, re-read the tail from guest memory and submit it as a new job. | AP `APX/src/Driver/Queues/Submission.cpp:373-416`, `APX/src/Driver/Packets/PacketExecution.cpp:600-646` | GPL-2.0-only | missing | M | as G4 / a wrong split drops work | later |
| 8 | G6 | **The "submit and write EOP" ioctl (0xc020810c)** raises the gfx EOP event after the work. RX emits `EVENT_WRITE_EOP` with int_sel 2 and data_sel 2 carrying `eopValue`, which delivers ident 0x40. Ours only stores the value in the submit page; no event. | RX `rpcsx/iodev/gc.cpp:250-277`, `rpcsx/gpu/DeviceCtl.cpp:60-80`, `rpcsx/gpu/Pipe.cpp:20-30` | GPL-2.0 | `lle:7471-7496` (TODO at 7490) | S | EOP waiters time out / none (host event, post-fence) | **e4-now** |
| 9 | G7 | **`SET_PREDICATION` (0x20)**. Ours NOPs it, so predicated draws and dispatches (header bit 0) always run. The AMD CP takes the gfx9+ form from a user IB (Mesa emits it). | ME `sid.h:47-57`, `src/amd/common/ac_cmdbuf_cp.c:276-291`; AP `APX/src/Pm4.cpp:349-357, 641-649, 1102-1106`, AP-debt L89; KP `KPH:1335-1386`; RX `rpcsx/gpu/Pipe.cpp:1027-1035`; SH `SHL:437` | MIT (facts), GPL | missing (`tsv:11`) | S | Wrong rendering, extra work / predicate address unmapped → fault, hence the mapped check | **e4-now** |
| 10 | M21 | **Guest NULL arguments return an error.** Ours EXITs on `sceKernelQueryMemoryProtection(NULL)` and on `MapNamedFlexibleMemory(addr_in_out == NULL)`. | SH `src/core/memory.cpp:1024-1037` (EACCES); AP `libkernel/DirectMemory/Export.cpp:484-494`; SE `KernelMemoryCompatExports.cs:3359` (EINVAL) | GPL | `mem:3316`, `mem:2394` | S | Host crash / none | **e4-now** |
| 11 | M4 | **`sceKernelReleaseFlexibleMemory` returns budget only.** The range stays mapped with its contents (measured; a fixed no-overwrite map over it still fails). Ours unmaps. | AP `libkernel/DirectMemory/Export.cpp:348-354`; AP-kdebt L81 (measured). SH madvises DONTNEED, which contradicts the measurement | GPL-2.0-only | `lle:7780-7783` → `KernelMunmap` | M | Title faults on memory it still owns / budget double-credit if done naively | later |
| 12 | M3 | **An unchecked `ReleaseDirectMemory` over holes** frees the allocated parts and skips the free ones. Ours returns EACCES and frees nothing. | KP `src/kernel/memory.cpp:1281-1315, 2354-2370`; SH `src/core/memory.cpp:284-376` (305-313); AP `libkernel/DirectMemory/MemoryPool.cpp:259-286`. SE agrees with ours | GPL | `mem:2963-2966` (via `GetAllocatedSpan`, `mem:1574-1613`) | S | Direct memory leaks; budget exhaustion / none | **e4-now** |
| 13 | G8 | **Catcher: what we drop.** Count every type-3 packet NOP-ed by `default-op drop`, per opcode, and every NOP whose header bits 7:2 are non-zero, per sub-code: 0x05 DRAW_RESET, 0x06 WAIT_FLIP_DONE, 0x09 DISPATCH_RESET, 0x0b/0x0c markers, 0x14/0x18 custom acquire/release, 0x15 WRITE_DATA, 0x17 FLIP, 0x19 DMA_DATA, 0x1a CONTEXT_STATE, 0x1b PSSR. AP and KP execute these; the AMD CP ignores NOP payloads. | sub-codes: KP `src/graphics/guest_gpu/pm4.h:74-84`, `pm4Dispatch.cpp:223-229`; AP `APX/src/Pm4.cpp:223-240`. Opcode names: ME `sid.h` | GPL | missing (`FilterStats`, `BE/include/bc5/policy.hpp:54-88`, has no per-opcode counts) | S | Silent semantic loss for any title / none | **e4-now** |
| 14 | G9 | **In-stream FLIP packet**: NOP sub 0x17, header `0xc004105c`, 6 dwords `{handle, index, mode, arg64}`. The flip happens when the work before it completes. Ours never acts on it. Today's flips arrive through `sceVideoOutSubmitEopFlip`. | KP `KPH:1702-1709`; AP `APX/include/VideoOutput.hpp:16-17, 26-31`, `APX/src/Driver/Packets/PacketExecution.cpp:405-433` | GPL | missing (soft CP `lle:864` NOP; flip path `lle:8022-8131`) | M | A title that flips this way never presents / double flips if the driver also calls SubmitEopFlip, so G8 first | later |
| 15 | G10 | **WAIT_FLIP_DONE (NOP sub 0x06)**: hold the queue until the display buffer is no longer scanned out. | KP `KPH:2233-2243` (header `0xc0051018`, 7 dwords); AP uses its own 4-dword encoding (`VideoOutput.hpp:18-20`, "AnyPS5's internal encoding"). **The sizes disagree**: TODO(verify) against G8's journal | GPL | missing | M | Tearing; writes into a displayed buffer / a wrong wait stalls the queue | later |
| 16 | G11 | **`COND_WRITE` (0x45)**: if `(*poll & mask) <fn> ref`, write a dword to the write address. Ours NOPs it; nothing emulates it. | AP `APX/src/Pm4.cpp:513-520, 736-739, 1198-1206`; RX `rpcsx/gpu/Pipe.cpp:1266-1300` (same layout); ME `sid.h:128` | GPL | missing (`tsv:11`; soft CP `lle:863-888`) | S | Labels never written; waiters hang / none (soft CP, post-fence) | **e4-now** |
| 17 | M16 | **`sceKernelMmap` (PGhQHd-dzv8)** is registered. Ours falls to the stub, which returns 0 with `*res` unwritten. | SH `src/core/libraries/kernel/memory.cpp:818-830`; AP `libkernel/DirectMemory/Export.cpp:341-346` | GPL | missing | S | Uninitialised pointer → crash / none | **e4-now** |
| 18 | M17 | **`sceKernelGetDirectMemoryType` (BC+OG5m9+bw)**: the type and block range at an offset; ENOENT if free. | SH `src/core/libraries/kernel/memory.cpp:473-480`, `src/core/memory.cpp:1398-1416`; AP `libkernel/DirectMemory/Export.cpp:264-274` | GPL | missing | S | Garbage outputs / none | **e4-now** |
| 19 | M5 | **A fixed map over memory tracked as pooled** goes through the generic replace path. Ours EXITs. | AP `libkernel/DirectMemory/DirectMemory.cpp:1126-1149` | GPL-2.0-only | `mem:3394-3398` | M | Host crash / pool bookkeeping | later |
| 20 | M7 | **`munmap` of holes or of nothing mapped** returns 0 and skips the holes. Ours returns EACCES. | AP `Export.cpp:332-339` + `DirectMemory.cpp:1615-1622` (prosper console oracle, AP-kdebt L313); SH `src/core/memory.cpp:913-1008` (942-944). SE agrees with ours | GPL | `mem:2728-2736`, `mem:2642-2650` | S | Leaks; title asserts / none | **e4-now** |
| 21 | M6 | **A non-fixed flexible-map hint that lies wholly inside a reservation** is used as the address. | AP `DirectMemory.cpp:1157-1160` (used at 1205); SE `BackedMappings.cs:339-344`; AP-kdebt L109 (title-observed) | GPL | `mem:2471-2477` → `FindGuestFreeRange` (`mem:1045-1077`). Direct maps already do this (`mem:3170-3184`) | S | Titles that assume the hint get wild pointers / none | **e4-now** |
| 22 | G12 | **The "wait idle" ioctl (0xc0048117)** blocks until the GPU is idle. Ours returns at once (exp 0084 history noted in the code). | RX `rpcsx/iodev/gc.cpp:287-293` | GPL-2.0 | `lle:7499-7510` | S | CPU rewrites data the GPU still reads / frame-time cost while on | **e4-now** |
| 23 | G13 | **`WRITE_CONST_RAM`/`DUMP_CONST_RAM` (0x81/0x83) in the DE stream**: a per-queue 48 KiB constant RAM, dumped to memory in stream order. Ours NOPs both, so the dump never lands. | AP `APX/src/Pm4.cpp:531-538, 706-715, 741-744, 1190-1197`; SH `SHL:208-219` (CE); RX `rpcsx/gpu/Pipe.cpp:1910-1929` (CE); ME `sid.h:219-220` | GPL | missing (`tsv:11`) | M | Shaders read stale descriptors / a filter-time rewrite into `WRITE_DATA` inserts dwords | later |
| 24 | M8 | **Reused direct memory is zeroed** before it is handed out again. | AP `DirectMemory.cpp:347-365` (called at 441); KP high-water idea `src/kernel/memory.cpp:1432-1441` | GPL | `mem:1278-1324` never zeroes (our own note: `e4/libs/libAmpr.cpp:1697-1699`) | M | Stale data, garbage on the GPU / memset cost | later |
| 25 | G14 | **Soft-CP timestamps are a 100 MHz count.** `RELEASE_MEM` DATA_SEL 3 and `COPY_DATA` SRC_SEL 9 read one counter, measured on a PS5 at 100 MHz (AP-debt L287). Ours writes nanoseconds: 10× off, in the fallback path only. | AP `APX/src/Pm4.cpp:1178-1180`, AP-debt L287 (measured, fw 13.40) | GPL-2.0-only (fact) | `lle:483-484`, `lle:585-586` | S | Wrong GPU timings in titles' pacing / none | **e4-now** |
| 26 | G15 | **General `kevent` filters** (USER, TIMER, READ/WRITE, VNODE). Ours handles change entries for EVFILT_GRAPHICS only and logs every other filter. | AP `libkernel/Equeue/src/Kqueue.cpp:280-530` | GPL-2.0-only | `lle:7727-7748` | M | Titles' own kqueues get no events / the KytyPlus event-queue model | later |
| 27 | M15 | **POSIX `munmap`/`mprotect` return -1 and set errno.** Ours binds them straight to the SCE functions. | SH `src/core/libraries/kernel/memory.cpp:421-428, 851-859`; AP `PosixMemory.cpp:251-294`. SE agrees with ours | GPL | `lk:2466-2467` | S | libc-level callers misread errors / none | **e4-now** |
| 28 | M10 | **Protection normalisation** (measured): write implies read when reported; map refuses bits outside 0x3F7; mprotect drops them. Ours stores the raw value, rejects ACP-only 0x100, and EXITs on an unknown protection in `MapNamedFlexibleMemory`. | AP `Export.cpp:60-62, 285-315`, `DirectMemory.cpp:303-313, 1081-1093`; SH `src/core/memory.cpp:502-505, 1064-1067`; AP-kdebt L173 | GPL | `mem:106-151, 2437-2439, 2498, 3238, 4015` | M | Wrong VirtualQuery; host crash | later |
| 29 | M9 | **AMM unmap** skips holes and gives the VA back to the AMM reservation. Not the excluded PRT/MultiMap/wait code. | AP `libkernel/Apr/src/Apr.cpp:387-390, 423-430`; KP `src/kernel/memory.cpp:2011-2034` | GPL | `e4/libs/libAmpr.cpp:2027-2031`, window `3500-3516` | S–M | Dropped AMM buffers; later maps land in the window / coordinate with the Ampr port | later |
| 30 | M12 | **A fixed remap over a live direct mapping is atomic** (MAP_FIXED in place). Ours unmaps to a placeholder first. | KP `src/kernel/memory.cpp:2456-2479`; AP `DirectMemory.cpp:856-895` | GPL | `mem:3159-3163, 3448-3459` | M | Sporadic CPU faults in other threads | later |
| 31 | M11 | **`sceKernelMtypeprotect` changes the memory type** (mapping, and physical in AP/SH). Over any flexible page it returns 0x8002002d (measured). | AP `DirectMemory.cpp:1587-1613`; SH `libraries/kernel/memory.cpp:430-452`, `memory.cpp:1309-1357`; SE `BackedMappings.cs:646`. KP ignores it, like ours | GPL | `mem:4022-4035` | S–M | Stale `memory_type` in queries | later |
| 32 | M14 | **`mmap` flag semantics**: VOID 0x100 reserves; STACK 0x400; SYSTEM 0x2000 not charged; ALIGNED_SUPER and bit-24 alignment; EINVAL for SHARED+PRIVATE and for anon with fd ≠ -1. | SH `libraries/kernel/memory.cpp:784-804`; AP `PosixMemory.cpp:152-170`; SE `Mmap.cs:19-30` | GPL | `lle:7693-7718` | M | Misplaced or unaligned mappings | later |
| 33 | M13 | **`mmap` with an fd maps the file** (and shm objects). Ours maps zeroed anonymous memory. | SH `src/core/memory.cpp:701-825`; AP `DirectMemory.cpp:1295-1390`, `PosixMemory.cpp:184-248`; RX `rpcsx/ops.cpp:177-211` | GPL | `lle:7693-7718` | L | Wrong data from mapped files | later |
| 34 | M19 | **Page-table statistics model** (measured): 8192 entries each; CPU = 2 MiB granules with a committed mapping; GPU = 1 GiB regions plus partial granules; de-duplicated. Ours: 2048 entries, per range, no de-dup. | AP `Export.cpp:551-567`, `DirectMemory.cpp:1707-1751`; AP-kdebt L352 | GPL-2.0-only | `mem:72-75, 482-505, 2794-2826` | S–M | Titles' own budgeting off | later |
| 35 | M20 | **`DirectMemoryQuery` find-next past the last block** returns EACCES. Ours returns OK with a terminal record. | AP `Export.cpp:253-262`, `MemoryPool.cpp:125-136`; SH `src/core/memory.cpp:1242-1245`; SE `KernelMemoryCompatExports.cs:3713-3739` (claims hardware). **KP (`src/kernel/memory.cpp:2164-2170`) agrees with ours** | GPL | `mem:2867-2873` | S | One bogus record in block walks / a title relying on our form | **e4-now** |
| 36 | M18 | **System flexible memory is not charged** to the game's flexible budget. | SH `libraries/kernel/memory.cpp:354-391`; AP `Export.cpp:636-646`. fpPS4 charges it (AP-kdebt L155; not read) | GPL | `lle:7762-7778` → `mem:2412, 2489` | S | Game budget exhausted early | **e4-now** |
| 37 | G16 | **Map compute queue (0xc030810d) and ding-dong (0xc010811c)** map a ring and consume it on the doorbell. Ours logs "not wired". The 0xc0408121 queues are served by `queue_consumer_thread`. | RX `rpcsx/iodev/gc.cpp:339-390`, `rpcsx/gpu/DeviceCtl.cpp:171-229` | GPL-2.0 | `lle:7573-7597` | M | A driver build that uses this path never runs its compute work | later |
| 38 | G17 | **Compute EOP routing per pipe**: RX delivers a compute `RELEASE_MEM` interrupt to ident `pipe` (0..6), gfx to 0x40, hp3d to 0x41, clock set to 0x84. Ours guesses the engine (`qq.a == 2`), fires 0x48 and 0x46 for every compute release, and also fires ident 0 on every gfx EOP. | RX `rpcsx/gpu/Pipe.cpp:20-30, 307-352, 1381-1385` | GPL-2.0 | `lle:370-376, 433-445, 1062` | M | Missed or misrouted wake-ups / RX's enum may be PS4-era: TODO(verify) | later |
| 39 | G18 | **`GET_LOD_STATS` (0x8e)**: KP writes a "complete, no samples" report. AP refuses ("synthetic results are forbidden"); SH only warns. **They disagree.** | KP `KPH:1282-1304`; AP `APX/src/Pm4.cpp:283`; SH `SHL:881-884` | GPL | dropped (`tsv`, op 0x8e) | S | Polling title hangs / layout provenance unknown | later |
| 40 | G19 | **`EVENT_WRITE_EOS` (0x48)**, including the GDS store. ME says GFX6-8 only; AP refuses it. | RX `rpcsx/gpu/Pipe.cpp:668, 1427`; SH `SHL:705-722`; ME `sid.h:171-176` | GPL | dropped (`tsv:11`) | M | Lost end-of-shader signals | later |
| 41 | M26 | **`MapDirectMemory` with execute** returns EINVAL with nothing mapped (measured). Ours returns EACCES. | AP `DirectMemory.cpp:1168`, AP-kdebt L190 (measured, fw 12.09). SH and SE use EACCES | GPL-2.0-only | `mem:3102-3104` | S | Error-path mismatch | **e4-now** |
| 42 | M25 | **`sceKernelMapNamedFlexibleMemoryInternal` (4h6F1LLbTiw)** takes the name, as a 5-argument call. Ours binds it to the 4-argument map. | AP `Export.cpp:321-324`; SE `KernelMemoryCompatExports.cs:3404-3412` | GPL | `lk:3458` | S | Name lost / none | **e4-now** |
| 43 | M22 | **`mlock`, `munlock`, `mlockall`, `munlockall`, `sceKernelMunlock`, `sceKernelMunlockall`** (NIDs mTBZfEal2Bw, OG4RsDwLguo, x7g7Ebeo8-U, NpLBpgVV7PU, xQIIfJ860sk, lvD71jP2Mnk). | AP `Export.cpp:868-918`, `PosixMemory.cpp:296-324`; SH `libraries/kernel/memory.cpp:861-911` | GPL | missing (only `sceKernelMlock`, `mem:3724-3765`) | S | Low | **e4-now** |
| 44 | M23 | **`msync`, `madvise`, `posix_madvise`, `mincore`, `sceKernelMsync`** (tZY4+SZNFhA, Jahsnh4KKkg, yYiyDoU2IEs, +hFjyohmOU0, DkNebxmJyVI). `mincore` must fill its vector. | AP `PosixMemory.cpp:326-386`, `libkernel_sys/Export.Discovery.cpp:1427-1429`; SH `libraries/kernel/memory.cpp:942-946` | GPL | missing | S | `mincore` garbage | **e4-now** |
| 45 | M24 | **`sceKernelClearVirtualRangeName` (mkgXxsoxWHg).** | KP `src/kernel/memory.cpp:1893-1907`; SH `libraries/kernel/memory.cpp:566-570`; AP `Export.cpp:543-549`; SE `KernelMemoryCompatExports.cs:3541-3566` | GPL | missing | S | Stale names | **e4-now** |
| 46 | M32 | **`sceKernelAllocateDirectMemoryForApp` (fNoviuIwykc)** forwards to `AllocateDirectMemory`. | AP `Export.cpp:239-241` | GPL-2.0-only | missing | S | Garbage physical address | **e4-now** |
| 47 | M30 | **`VirtualQuery`/`DirectMemoryQuery` accept an info size larger than the struct** (titles pass sizes other than 0x48: AP-kdebt L361). | AP `Export.cpp:373`; SE `KernelMemoryCompatExports.cs:3579` | GPL | `mem:3678`, `mem:2844` | S | EINVAL to a valid call | **e4-now** |
| 48 | M29 | **A fixed flexible remap near exhaustion** credits the replaced bytes before checking the budget. SH, SE and KP check first, like ours. | AP `Export.cpp:147-160` | GPL-2.0-only | `mem:2412-2414` | S | Low; one source only | later |
| 49 | M27 | **Host protection applied at map time.** Ours maps RW/RWX until an mprotect. SH and KP do as ours. | AP `DirectMemory.cpp:1213`; SE `KernelMemoryCompatExports.cs:3316` | GPL | `e4/kernel/memoryAddressSpace.inc:746-766, 872-880` | M | Guard pages do not fault / check GPU write-watch first | later |
| 50 | G20 | **An unsatisfied `WAIT_REG_MEM` is never treated as complete** (diagnostic only). Ours proceeds after 2 s in the soft CP and after 10 s in ring deferral. | AP `APX/src/Driver/Synchronization/WaitMemory.cpp`, AP-debt L212 | GPL-2.0-only | `lle:694-699`, `lle:1017-1019` | M | Out-of-order work after a timeout / deadlock if a wait is wrong | later |
| 51 | G21 | **Switch-buffer ioctl (0xc0088101)**: wait idle plus a `SWITCH_BUFFER` packet (CE double buffering). | RX `rpcsx/iodev/gc.cpp:232-248`, `DeviceCtl.cpp:56-58` (RX's packet handler is a FIXME, `Pipe.cpp:1938`) | GPL-2.0 | `lle:7497-7498` (no-op) | S | Low on PS5 | later |
| 52 | G22 | **CE/DE packets**: `LOAD_CONST_RAM` 0x80, counters 0x84-0x89. AP refuses them. | SH `SHL:220-231, 858-866`; RX `rpcsx/gpu/Pipe.cpp:691-709` | GPL | dropped (`tsv:11`) | M | Low unless G8 sees them | later |
| 53 | G23 | **`STRMOUT_BUFFER_UPDATE` (0x34)**, `DRAW_INDEX_MULTI_AUTO` (0x30), `LOAD_CONFIG_REG` (0x60). | SH `SHL:871`; RX `rpcsx/gpu/Pipe.cpp:646, 680` | GPL | dropped (`tsv:11`) | M | Low unless G8 sees them | later |
| 54 | G24 | **`PRIME_UTCL2` (0x5D)** passed: a translation prefetch with no visible effect. AP lists `sceAgc*PrimeUtcl2` builders. | ME `sid.h:207`; AP `libSceAgc` | MIT/GPL | dropped (`tsv:11`) | S | Performance only | later |
| 55 | M31 | **JIT shared memory** (`sceKernelJitCreateSharedMemory`, `…CreateAliasOfSharedMemory`, `…MapSharedMemory`). | AP `libkernel/DirectMemory/Jit.cpp:197-237`. **Provenance**: signatures from Orbital's IDA type database (AP-kdebt L175), needs the maintainer's call | GPL-2.0-only | missing | M | JIT middleware fails | later (provenance check) |
| 56 | D1 | **An independent `libSceAgc` (Q14/D18)**: 110 AP-implemented exports we do not register (builders, patches, semaphore memory, interpolant mapping, static buffers). SE has 147 Agc exports. | AP `libSceAgc/` (234/240 implemented); SE `src/SharpEmu.Libs/Agc/*.cs` | GPL | KytyPlus HLE registers 124/240; the pack's LLE `.sprx` wins (`lle:8230`) | L | Stream differences → GPU faults; gate: packet-by-packet comparison with the LLE stream | later; screen each function: AP libSceAgc debt L26 (decrypted fw 3.20), L46 (firmware checks), L55 (decrypted headers), L33-34 (SDK-inline sizes) and `sceAgcGetRegisterDefaults` are excluded |
| 57 | D2 | **An independent `libSceAgcDriver` submit/queue/Eq layer**: 70 AP-implemented exports not in ours. | AP `libSceAgcDriver/{Submit,Eq,State}` | GPL-2.0-only | 26/146 registered; LLE pack today | L | as D1 | later; the "retail constant results" (AP-debt L52, L73) and UserData packets (L90) are firmware-derived and excluded |
| 58 | M28 | **Loaded module segments are charged to the flexible budget.** | AP `Export.cpp:145, 160, 513-515`; KP `0a14091` (`src/kernel/memory.cpp:3211-3217`) | GPL | `mem:3882-3885, 2170-2174` | M | Titles' own budget arithmetic | in flight (param.json sizing port): hand over, do not redo |

## e4-now port specs

Each fix has its own switch. With the switch off, behaviour is byte-identical. The soft-CP semantics go into a new pure
header so that Catch2 can test them without a GPU: `BE/include/bc5/soft_ops.hpp` with `soft_ops_test.cpp`, called from
`lle`'s `SoftCp::execute` (`lle:845-899`). Under the provenance rule, each port cites the rows' sources in its header
comment and keeps the source's licence in any copied lines.

### G1, `BC5_R3_KEVENT_TIMEOUT`: kevent honours its timespec

- **Where:** `lle:7749-7758`.
- **Change:** read `{int64 sec, int64 nsec}`. Convert it to microseconds, rounding nsec up and saturating. Pass the
  value to `EQ::KernelWaitEqueue(eq, events, nevents, &out, &us)`. A zero value makes `KernelWaitEqueue` poll
  (`e4/kernel/eventQueue.cpp:436-440`).
- **Return mapping:** `KERNEL_ERROR_ETIMEDOUT` → 0; any other error → -1; otherwise `out`. A null `timeout` keeps
  today's path.
- **Test:** create an equeue. `{0,0}` returns 0 immediately. `{0,2e6}` returns 0 after ≥ 2 ms. A triggered user event
  returns 1.

### M1, `BC5_R3_MPROTECT_GAPS`: mprotect over gaps

- **Where:** `mem:3988-3997`.
- **Change:**
  - In place of the EXIT, iterate `old_ranges`.
  - Apply the protection only to committed pieces.
  - Record it, without applying it, on reserved pieces, as SH `memory.cpp:1104-1108` does.
  - Return OK.
- **Same for:** the overflow EXIT at 3974-3977, which becomes EINVAL, and for `KernelMtypeprotect`'s call path
  (`mem:4022-4035`).
- **Test:** map A, leave a hole, map B. mprotect over A..B returns 0. A and B change; the hole stays free. A fully
  unmapped range returns 0.

### M2, `BC5_R3_MMAP_HINT`: the mmap shim

- **Where:** `lle:7693-7718`.
- **Change:**
  - Pass `GUEST_MAP_FIXED` only when `flags & 0x10`.
  - Drop the prot 0 → 0x33 promotion (7698-7700).
  - Skip the `memset` (7716) when prot has no CPU write; flexible memory is already zeroed (`mem:1868-1875`).
- **Unchanged:** the failure value stays NULL. The comment at `lle:7691-7692` says Sony's driver tests against 0.
  TODO(verify) before any MAP_FAILED change.
- **Test:** a non-fixed hint over a live mapping returns another address and leaves the old mapping intact. A prot 0
  mapping reports protection 0. The driver-style call (addr 0xfe0200000, flags with FIXED) still lands at the address.

### G2, `BC5_R3_MEMSEM_SIGNAL`: MEM_SEMAPHORE signal in the soft CP

- **Where:** add `case 0x39: if (!done) soft_ops::mem_semaphore_signal(p, len)` to `lle:863-888`.
- **Packet:** PS5 form, 4 dwords. Address = `(p[1] & ~7) | (u64)(p[2] & 0xffff) << 32`; control = `p[3]`.
- **Signal** (control >> 29 == 6): 8-byte aligned.
  - If bit 20 is set: `__atomic_store_n(u64, 1)`.
  - Otherwise: `__atomic_fetch_add(u64, 1)`.
- **Wait** (op 7): count and journal only; G3 is later.
- **Unchanged:** the packet stays NOP-ed for the GPU.
- **Test:** a synthetic IB with a signal of each type. Assert the word becomes 1, and then 2 after an increment.

### G4, `BC5_R3_REWIND_CATCH`: REWIND catcher

- **Where:** `BE/src/policy.cpp` `filter()`.
- **Counting:** for type-3 op 0x59 with len 2, count `stats.rewinds` and `stats.rewinds_invalid` (bit 31 of `src[i+1]`
  clear). Record the first offset in a new `FilterStats` field.
- **Journal:** `lle`'s submit line journals these when non-zero. Give the IB address, the offset, and how many non-zero
  dwords follow it.
- **Unchanged:** the packet stays dropped.
- **Test:** `policy_test`, with `0xC0005900, 0x00000000` and `0xC0005900, 0x80000000`.

### G6, `BC5_R3_SUBMIT_EOP_EVENT`: submit-and-write-EOP raises the gfx EOP

- **Where:** `lle:7471-7496`.
- **Change:** after `soft_posts_end()`, `Direct::post([v](bool){ SoftCp::fire_eop(v); })`. `post` runs after the
  submission's fence, or at once without the direct path. `t_compute_ring` is false here, so 0x40 (and ident 0 quietly)
  fire, as for a `RELEASE_MEM` with INT_SEL (`lle:433-445`).
- **Unchanged:** the submit-page store stays.
- **Test:** register an equeue for ident 0x40 (`SoftCp::register_eq`). Call the ioctl with an empty command list.
  Expect one event with data = `eop_value`.

### G7, `BC5_R3_PREDICATION`: pass SET_PREDICATION

- **Where:** `BE/src/policy.cpp`.
- **New option:** `FilterOptions::pass_predication`, default false.
- **Filter change:** right after `policy.packet(...)` in `filter()`, add
  `if (opt.pass_predication && !opt.compute_ring && opcode3 == 0x20 && len == 4 && (src[i+3] >> 16) == 0) v = Pass;`.
  The condition takes only the gfx9+ form (op, lo, hi; ME `ac_cmdbuf_cp.c:281-284`).
- **Memory operands:** `memory_operands()` gets `case 0x20: if (((p[1] >> 16) & 7) != 0) out.emplace_back(addr(2,3), 8)`.
  With that, an unmapped predicate address is dropped by the existing `opt.mapped` check (`policy.cpp:538-546`).
- **Left alone:** `is_graphics_only`, so default compute-ring routing does not change.
- **Test:** `policy_test` (passed when on, dropped when off, dropped when unmapped, dropped on the compute ring).

### G8, `BC5_R3_DROP_CATCH`: drop and custom-NOP catcher

- **Where:** `FilterStats`.
- **New fields:**
  - `uint32_t default_drops[256]`, incremented where `policy.packet()` returned Drop for type 3 and the opcode is not
    `op_set_`;
  - `uint32_t nop_sub[64]`, for op 0x10 with `(h >> 2) & 0x3f`.
- **Journal:** `lle` journals the first occurrence of each new opcode or sub-code (a process-wide bitset), with IB
  address and offset, and a summary every 500 submissions.
- **Test:** `policy_test`, with a buffer of 0x39, 0x45, 0x59, 0x81, `0xc004105c`.

### G11, `BC5_R3_COND_WRITE`: COND_WRITE in the soft CP

- **Where:** `case 0x45: if (!done && len == 9) soft_ops::cond_write(p)`.
- **Fields:** fn = `p[1] & 7`; poll memory = bit 4; write memory = bit 8.
  - Poll address = `addr64(p[2], p[3])`, ref = `p[4]`, mask = `p[5]`.
  - Write address = `addr64(p[6], p[7])`, data = `p[8]`.
  - Layout from AP `Pm4.cpp:736-739` and RX `Pipe.cpp:1266-1300`.
- **Change:** use the existing `compare()` (`lle:457-470`). Register spaces are counted and not executed.
- **Test:** each compare function, true and false.

### G12, `BC5_R3_WAIT_IDLE`: wait idle drains

- **Where:** `lle:7500-7510`.
- **Change:** for request 0xc0048117 only, after `chain_observe()`, call `Direct::drain()`; also call `wait_jobs()` in
  async mode. 0xc0048116 stays as it is (RX does not wait there either: `gc.cpp:279-285`).
- **Test:** with the stand-in device, a posted job completes before the ioctl returns.

### G14, `BC5_R3_TS_100MHZ`: soft-CP timestamps

- **Where:** `lle:483-484` (DATA_SEL 3) and `lle:585-586` (SRC_SEL 9).
- **Change:** write `now_ns() / 10`. DATA_SEL 4 and SRC_SEL 0xa keep ns; their console frequency is not measured.
- **Caveat:** the epoch differs from the GPU's own counter. TODO(verify) the box's `gpu_counter_freq` (amdgpu dev
  info) before trusting mixed values.
- **Test:** two writes 10 ms apart differ by about 1e6.

### M3, `BC5_R3_RELEASE_HOLES`: unchecked release over holes

- **Where:** `mem:2963-2966`.
- **Change:** for the unchecked call, walk the allocated blocks inside `[start, start+len)` and release each one,
  skipping free gaps; return OK. The checked form keeps ENOENT.
- **Test:** allocate A, leave a gap, allocate B. Release over A..B frees both.

### M21, `BC5_R3_NULL_ARGS`: guest NULL arguments

- **Where:** `mem:3316` and `mem:2394`.
- **Change:** `mem:3316` returns `KERNEL_ERROR_EACCES` (SH); `mem:2394` returns `KERNEL_ERROR_EINVAL`.
- **Test:** both calls return the error, with no exit.

### M16 and M17, `BC5_R3_MMAP_EXPORT` and `BC5_R3_DMEM_TYPE`

- **M16:** register `PGhQHd-dzv8`: `(addr, len, prot, flags, fd, off, void** res)` calls the shim and sets `*res`.
  Result: 0 or `KERNEL_ERROR_ENOMEM`.
- **M17:** register `BC+OG5m9+bw`: `(int64 start, int* type, int64* s, int64* e)`. Use the block containing `start`;
  a free offset gives ENOENT. Reuse the DirectMemoryQuery walk (`mem:2844-2890`).
- **Registration:** only when the switch is on, in the `LIB_DEFINE` of `lk`.
- **Test:** both exports through their C++ entry points.

### M7, `BC5_R3_MUNMAP_HOLES`: munmap of holes

- **Where:** `mem:2728-2736` and `2642-2650`.
- **Change:** nothing mapped in the range → OK; holes are skipped. Length handling is unchanged, because AP (EINVAL
  for a length that is not a 16 KiB multiple) and SH (round) disagree.
- **Test:** unmapping over A, a hole and B succeeds; unmapping nothing succeeds.

### M6, `BC5_R3_FLEX_HINT`: flexible hint inside a reservation

- **Where:** `mem:2471-2477`.
- **Change:** if the call is not fixed and `[hint, hint+len)` lies wholly in one reserved range, map there, as direct
  maps do at `mem:3170-3184`.
- **Test:** reserve R. Map flexible with hint R. The result is R.

### M15, `BC5_R3_POSIX_ERRNO`: POSIX munmap and mprotect

- **Where:** `lk:2466-2467`.
- **Change:** bind to wrappers that turn an SCE error into -1 and set the guest errno. Use KytyPlus's POSIX errno
  helper, the same one other Posix wrappers in `lk` use.
- **Test:** a bad range gives -1 and errno EINVAL.

### M20, `BC5_R3_DMQ_END`: find-next past the last block

- **Where:** `mem:2867-2873`.
- **Change:** return `KERNEL_ERROR_EACCES` there. KP disagrees, so the switch matters.
- **Test:** querying past the last block gives EACCES.

### M18, `BC5_R3_SYSFLEX_BUDGET`: system flexible memory

- **Where:** `lle:7762-7778` → `mem:2412, 2489`.
- **Change:** a `system` flag on the flexible map path that skips the budget check and the charge.
- **Test:** the available flexible size is unchanged after a system map.

### M26, `BC5_R3_EXEC_EINVAL`

- **Where:** `mem:3102-3104`.
- **Change:** EACCES → EINVAL.
- **Test:** the error code.

### M25, `BC5_R3_FLEX_INTERNAL`

- **Where:** `lk:3458`.
- **Change:** bind `4h6F1LLbTiw` to the 5-argument named map. The measured flag refusals belong to M10 (later).
- **Test:** the name appears in VirtualQuery.

### M22, M23, M24 and M32: missing exports

- **Switches:**
  - M22 `BC5_R3_MLOCK`;
  - M23 `BC5_R3_MSYNC`;
  - M24 `BC5_R3_CLEAR_NAME`;
  - M32 `BC5_R3_DMEM_FOR_APP`.
- **Bodies:**
  - mlock family: validation and 0, as SH `libraries/kernel/memory.cpp:861-911`;
  - msync, madvise and `sceKernelMsync`: 0 after a range check;
  - mincore: fills one byte per 16 KiB page, 1 when committed;
  - ClearVirtualRangeName: sets the name to "" over the range;
  - `ForApp`: forwards to `KernelAllocateDirectMemory`.
- **Test:** the return code and outputs of each.

### M30, `BC5_R3_QUERY_SIZE`

- **Where:** `mem:3678` and `mem:2844`.
- **Change:** accept `info_size >= sizeof(struct)`, write `sizeof` bytes.
- **Test:** size 0x50 succeeds.

## Skips

**(a) We already match.**

- **WRITE_DATA DST_SEL 3** does not land in memory, as measured on a PS5 (AP-debt L223). Our soft CP returns at
  `lle:614-616`, and the filter treats DST_SEL 3 as GDS (`BE/src/policy.cpp:163-165`).
- **GDS, OA and GWS:** real allocations on the BO list (`BE/include/bc5/direct.hpp:85-97`,
  `BE/src/direct.cpp:592-661`), where AP emulates a 64 KiB GDS (`APX/src/Pm4.cpp:50-72`).
- **The CLEAR_STATE push and pop stack** (`BE/include/bc5/state_stack.hpp:1-17`, PAL enum). AP models push and pop as
  NOP sub 0x1a instead; G8 will show whether that form ever occurs.
- **CONTEXT_CONTROL** with load and shadow off: ours rewrites it to RADV's values (`tsv`, op 0x28). AP requires the
  same (`Pm4.cpp:421-425`).
- **COND_EXEC, SET_*_REG_INDIRECT, indirect dispatch dims, thread-dimension dispatches:** the hardware CP executes
  them live, which is the console's PFP timing (AP-debt L215, L224).
- **ioctls:**
  - CU masks, client count and is-game-closed (`lle:7511-7548`) match RX `gc.cpp:322-337, 413-429`;
  - GS ring sizes and stats report are logged only, as in RX;
  - `/dev/dipsw` answers zeros.
- **Unknown ioctls 0xc0048114 and 0xc004811f:** zeros (`lle:7598-7621`), where RX only logs. No semantics are known.
- **The 25 memory rows the sub-agent found matching.** Among them:
  - Allocate validation `mem:2918-2929`;
  - AllocateMain `2938-2951`;
  - CheckedRelease `2968-3031`;
  - map of unallocated memory → ENOMEM `3115-3117`;
  - direct-map hint in a reservation `3170-3184`;
  - AvailableDirectMemorySize `2745-2792`;
  - DMQ merge `2879-2887`;
  - VirtualQuery find-next and reserved `384-399, 3687-3699`;
  - IsStack `3767-3801`;
  - SetVirtualRangeName `2622-2628`;
  - flexible zeroing, coalescing and alignment `1868-1875, 512-521, 2425-2432`;
  - the pool calls `4142-4462`;
  - BatchMap `4037-4121`;
  - mprotect length 0 `3971-3982`;
  - `getpagesize` `lk:1944-1948`;
  - `EnableDmemAliasing` (the stub's 0 equals AP's behaviour).

**(b) Licence or provenance not acceptable.**

- AnyPS5's "AGC FS table" at 0xF_E0040000. AP-debt L318 describes it as built "the way PS5 13.60 libSceAgcDriver and
  libSceAgc do". The LLE pair sets it up today.
- `sceAgcDriver*` constant results, and the `DRIVER_FEATURE_UNAVAILABLE` codes (AP-debt L52, L73: firmware 13.42
  disassembly).
- The `UserDataWrite*` packet layout (AP-debt L90).
- `sceAgcGetRegisterDefaults` and the register defaults (SDK).
- The libSceAgc functions whose notes cite decrypted firmware 3.20, decrypted headers or SDK-inline code (libSceAgc
  debt L26, L33-34, L46, L55).
- `sceKernelGetTraceMemoryStats` (AP-kdebt L265).
- The JIT signatures (M31) are borderline: an IDA type database. They are listed for the maintainer's decision, not
  ported.

**(c) In flight, not redone.**

- AMM PRT and the zero pages behind it.
- Ampr MultiMap, Remap and ModifyProtect, and the waits.
- AP `sceAgcSetAmmSemaphoreMemory`: coordinate with that port.
- The table catcher.
- param.json sizing (M28).
- acb queue state (exp 0403): DISPATCH_RESET (NOP sub 0x09; AP `Pm4.cpp:1071`, KP `KPH:1306-1313`), and the
  `COMPUTE_PGM` refusal.
- Fast-launch crumbs (exp 0404).

## Totals

- **58 ranked rows:**
  - 24 GPU (G1-G24);
  - 32 memory (M1-M32);
  - 2 driver (D1, D2).
  - Two features are split into an e4-now part and a later part: MEM_SEMAPHORE (G2/G3) and REWIND (G4/G5).
- **e4-now: 27.**
  - 9 GPU: G1, G2, G4, G6, G7, G8, G11, G12, G14.
  - 18 memory: M1, M2, M3, M6, M7, M15, M16, M17, M18, M20, M21, M22, M23, M24, M25, M26, M30, M32.
  - All are S effort, behind their own switch, and change no GPU submission by default. G7 changes a submission only
    with its switch on.
- **later: 30.**
  - 15 GPU.
  - 13 memory, M31 among them, pending the provenance check.
  - D1 and D2.
- **Handed over:** 1 (M28, to the in-flight param.json sizing port).
- **Skips:** (a) 7 GPU/ioctl groups and the 25 memory checks; (b) 7 provenance groups; (c) 7 in-flight items.
- **Disagreements kept visible:**
  - SE sides with ours: M3, M7, M15;
  - KP sides with ours: M11, M20;
  - fpPS4 sides with ours, per AP: M18;
  - SH/SE side with ours: M26, M29;
  - G10: the packet size differs between KP and AP;
  - G18: whether a synthetic report is allowed;
  - G17: RX's enum may be PS4-era.
