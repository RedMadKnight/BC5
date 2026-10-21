# Analogous projects: what BC5's host can take, and what it should do differently

*Outcome (2026-10-21, experiment 0188, F247): §2's flip-event lead did not explain the clock (the title never reads the event; coalescing is now the default anyway); §4's AudioOut2 grain model did — ported from AnyPS5, it fixed the speed-ups.*

*Written 2026-10-21. Review only; no code was copied in this pass. Asked by the maintainer: "review
all analogous projects, not only the latest changes: what can we copy, or implement differently to
avoid some of our errors, keeping in mind our simplified architecture and what it gives us for free."*

## 0. What our architecture gives us, and therefore what we skip

BC5 runs the title's x86-64 code natively and hands its AGC/PM4 command buffers and native RDNA
shader binaries straight to the BC-250's `gfx1013` GPU (the direct path, `bc5LleAgc.cpp`). Every
other project here spends most of its code on what we do not need: CPU translation (P5EMU), GCN/RDNA
shader recompilers and SPIR-V, PM4→Vulkan translation (shadPS4, KytyPS5/KytyPlus, RPCSX), texture
detiling and guest-memory caches. All of that is **skipped** below without further mention.

What is left to compare is (a) the HLE system libraries and the kernel behaviour a title observes
(events, time, audio, AJM, memory) and (b) the CPU-side state a direct-submission host must set
because the console's system or AGC driver would: ring bases, preambles, flips and labels.

## 1. Projects read

Shallow clones under `C:\Users\kjani\Downloads\bc5\refs` (outside the repo), 2026-10-21. Copying
code into our GPL-2.0-only host needs a compatible licence; for the others only behaviour is noted.

| Project | Commit | Licence | Copy allowed | What it is |
|---|---|---|---|---|
| [shadps4-emu/shadPS4](https://github.com/shadps4-emu/shadPS4) | `60c42b9` 2026-10-20 | GPL-2.0-or-later | yes | PS4 HLE emulator, the most mature |
| [Coder787-source/KytyPlus](https://github.com/Coder787-source/KytyPlus) | `3eee96a` 2026-10-20 (our base `f266548`, 2026-09-28) | GPL-2.0-only | yes | **our host's upstream** |
| [KytyPS5/KytyPS5](https://github.com/KytyPS5/KytyPS5) | `4644c52` 2026-10-21 | GPL-2.0-only | yes | upstream of KytyPlus's libraries; libraries identical or near-identical to KytyPlus HEAD |
| [InoriRus/Kyty](https://github.com/InoriRus/Kyty) | `4733b7e` 2022-10-03 | MIT | yes | the original Kyty |
| [boykopovar/AnyPS5](https://github.com/boykopovar/AnyPS5) | `27c88a8` 2026-10-21 | GPL-2.0-only | yes | PS5 relinker with reimplemented libraries (earlier review: `anyps5-review.md`) |
| [RPCSX/rpcsx](https://github.com/RPCSX/rpcsx) | `e8ae148` 2026-06-30 | GPL-2.0 | yes | LLE: boots the console's modules on an emulated FreeBSD kernel |
| [red-prig/fpPS4](https://github.com/red-prig/fpPS4) (trunk) | `04cefd4` 2024-10-01 | LGPL-2.1 | yes (as GPL-2.0) | Pascal PS4 HLE emulator; the kernel rewrite lives in a branch not cloned |
| [obhq/obliteration](https://github.com/obhq/obliteration) | `2a53d5c` 2026-09-26 | MIT or Apache-2.0 | yes (MIT) | Rust kernel-level PS4 emulator; kqueue and time mostly `todo!()` |
| [Inori/GPCS4](https://github.com/Inori/GPCS4) | `88480de` 2023-06-27 | GPL-3.0 | no | older PS4 HLE; event queue, VideoOut, time are stubs |
| [Abhishekrazy/pcsx5](https://github.com/Abhishekrazy/pcsx5) | `f1244ff` 2026-09-08 | GPL-2.0 | with care (§9) | Windows PS5 emulator, thin HLE |
| [iStark/PS5PCEM](https://github.com/iStark/PS5PCEM) | `5834858` 2026-10-21 | GPL-3.0-or-later | no | Zig PS5 emulator; LLE AGC driver over an emulated `/dev/gc`, AudioOut2, AJM, APR/AMM HLE |
| [NabuOX/P5EMU](https://github.com/NabuOX/P5EMU) | `255c12b` 2026-10-13 | Apache-2.0 | no | x86-64→IR→AArch64 research; nothing in scope implemented |
| [astraea-emu/astraea](https://github.com/astraea-emu/astraea) | `e94b06d` 2026-10-15 | GPL-3.0-or-later | no | clean-room PS5 research; no HLE runtime |
| [mpereiraesaa/ps5-vulkan](https://github.com/mpereiraesaa/ps5-vulkan) | `e6d3c3f` 2026-09-29 | GPL-3.0-or-later | no | Vulkan driver for homebrew **on the console**: measured system state |
| [OpenProspero/AGC](https://github.com/OpenProspero/AGC) | `7613a00` 2026-10-06 | GPL-3.0-or-later | no | console payload experiments, raw `/dev/gc` vs the AGC driver |

## 2. The flip event: our host counts flips that did not happen (the lead for F241–F245)

The second title registers only a flip event (exp 0183) and its clock runs up to 3× fast on host
inputs that, frame by frame, look right (F244). One input we had never compared is the flip event
itself: the kqueue entry, its data word and its count.

**Our host (KytyPlus `f266548`, unchanged by patch 0001).** `src/graphics/presentation/videoOut.cpp`
`MakeVideoOutEventData` (lines 293–305) packs `time = TSC & 0xfff | count << 12 | flip_arg << 16`.
`TriggerVideoOutEvent` (314–325) copies the *visible* event, takes its count + 1, and, **if the event
is already triggered and not yet read, pushes that copy to a list of pending events** instead of
updating it. `src/kernel/eventQueue.cpp` (wait loop, lines 102–134) delivers the event, resets it,
then loads the next pending copy and keeps going while the title's array has room. Three flips
between two reads therefore reach the title as three events with counts **1, 2, 2** (5 flips),
each with its own flip arg. A title that sums `sceVideoOutGetEventCount`, or that takes each event as
"a flip happened", sees more flips than were shown, more so the further it falls behind.

**Everyone else:**

| Implementation | A display event triggered again before it is read | Source |
|---|---|---|
| shadPS4 | one event; count + 1 (4 bits, saturates), latest flip arg and time; EV_CLEAR forced, reset on read | `src/core/libraries/kernel/equeue.h:116-132` (`TriggerDisplay`), `equeue.cpp:89-114, 245-280` |
| fpPS4 | one node; data rewritten in place (count + 1, latest arg); a second post is refused while the first is pending; count restarts at 1 | `kernel/ps4_queue.pas:253-279`, `src/ps4_libscevideoout.pas:769-813, 1277-1294` |
| Kyty (the original) | one event per (ident, filter); fflags + 1, data overwritten; reset on read | `src/Kernel/EventQueue.cpp:59-88, 123-167`, `src/Graphics/VideoOut.cpp:696-766` |
| RPCSX (kernel under the console's own libSceVideoOut) | one knote; a re-trigger while triggered is dropped | `kernel/orbis/src/event.cpp:45-51, 68-76`, `kernel/orbis/src/sys/sys_event.cpp:63-89, 140-156, 315-320` |
| pcsx5 | one event; data overwritten, no count | `libkernel_sync.cpp:528-593, 1647-1673` |
| **KytyPS5, KytyPlus HEAD, AnyPS5** | **pending copies, as ours** (KytyPlus has a test that keeps it, `tests/EventQueueLifetimeTests.cpp:168-247`; AnyPS5's own note says FreeBSD would aggregate and the Orbis behaviour is unconfirmed, `docs/dev/debt/libkernel.md:91`) | `videoOut.cpp:314-348` (KytyPlus), `libSceVideoOut/src/Event.cpp:48-75` (AnyPS5) |
| PS5PCEM | a 1024-entry FIFO, every trigger appended | `kernel_event_queue.zig:24, 68-78, 731-793` |

Four independent lines (shadPS4, fpPS4, the original Kyty, RPCSX's FreeBSD kernel) coalesce; the
queuing came in with the KytyPS5 line, and the projects that kept it cite no console evidence for
it. FreeBSD's kqueue, which the console's kernel derives from, keeps one knote per (ident, filter)
in a queue, and a new trigger updates that knote instead of adding an event (RPCSX's kernel above).

**Verdict: DO DIFFERENTLY, first on the list.** One event per (ident, filter) for
`EVFILT_VIDEO_OUT`: while triggered and unread, update it in place (count + 1 saturating at 15,
mirrored in fflags; latest time and payload, as shadPS4's `TriggerDisplay`); reset on read; no
pending copies. Behind a switch first (`KYTY_BC5_VIDEOOUT_COALESCE`, default on once measured),
because KytyPlus's tests pin the old behaviour. Test: the idle night run of exp 0185/0186 (L6/L7
drift to 3.0× in ten minutes) with the switch on and off, plus a per-delivery trace of the count the
title receives. TODO(verify) on the box; the link was down when this was written.

Also from this comparison:
- **Level events fill the whole result array (base bug, COPY).** Without EV_CLEAR and without a
  reset function, the base wait loop copies the same event into every slot of the title's array.
  KytyPlus HEAD adds `else break;` (`eventQueue.cpp:125-128`). Applies cleanly to our patch.
- **The GPU EOP/interrupt and AMPR events use the same pending-copy pattern** (KytyPlus `sync.cpp:79-92`,
  `eventQueue.cpp` AMPR trigger). RPCSX coalesces GraphicsCore events too
  (`sys_event.cpp:140-142, 317-320`). Review them with the same switch.
- **sceKernelAddTimerEvent (`57ZK+ODEXWY`) is wrong in our patch.** Our `AddTimerEvent`
  (`bc5LleAgc.cpp`, patch line ~15532) reads the third argument as a `timespec*` and makes a one-shot
  HR timer. KytyPlus HEAD and KytyPS5 take it as microseconds and make a periodic EVFILT_TIMER with
  EV_CLEAR whose data counts expirations (`eventQueue.cpp:143-155, 532-546`); shadPS4 does the same
  (`equeue.h:111-114`, `equeue.cpp:157`). COPY, after checking whether either title imports it.

## 3. Other timing items

- **Nobody holds a flip-rate-0 title at 30.** shadPS4 (`driver.cpp:369-383`), AnyPS5
  (`VideoOutDriver.cpp:551-562`), fpPS4 (`ps4_libscevideoout.pas:1427-1464`) and RPCSX (flip rate only
  logged, `dce.cpp:432-434`) all present at the next due vblank. The question of F241 stays open;
  our 30-fps cap remains a workaround.
- **Vblank 59.94 vs 60 Hz (CROSS-CHECK, low).** RPCSX (`rpcsx/gpu/Device.cpp:347-374`) and AnyPS5
  (`VideoOutDriver.cpp:520, 754`) tick at 1001/60000 s; shadPS4, the Kyty line and ours at 60 Hz while
  reporting 59.94 in the output status. 0.1 %: not error 1, but the console-faithful value.
- **Flip status +16 and +32 (CROSS-CHECK).** Our PS5 layout leaves them `reserved0/reserved1` (0);
  the PS4 layout has `tsc` and `submitTsc` there (Kyty `VideoOut.cpp:80-92`, shadPS4
  `video_out.h:70-81`, raw `rdtsc`); RPCSX's PS5 `FlipControlStatus2` has an unknown word at the
  second (`dce.cpp:72-100`). Cheap experiment: write the raw TSC at presentation and at submit.
- **Process-CPU clock (CROSS-CHECK).** RPCSX (`sys_time.cpp:6-27`) and AnyPS5 (`Time.cpp:397-496`)
  map clock id 15 to the host's `CLOCK_PROCESS_CPUTIME_ID` (CPU time of all threads, FreeBSD's id 15);
  fpPS4 even makes process time CPU time. Ours maps 15 (`KERNEL_CLOCK_PROCTIME`) to wall-clock process
  time. A CPU-time clock runs N× fast with N busy threads; ours does not, so this cannot speed us up,
  but a trace of which clock ids the title calls is worth one run.
- **A time-scale diagnostic (COPY the idea).** AnyPS5's `APS5_TIME_SCALE` (`Time.cpp:66-87, 723-725`)
  scales the monotonic clocks and the TSC but not sleeps: a direct test of which clock a drifting
  timeline follows.
- **Which buffer's flip label returns to 0 (CROSS-CHECK).** shadPS4 (`driver.cpp:271-277`) and AnyPS5
  (`VideoOutDriver.cpp:611-615`) reset the label of the *previously* displayed buffer when the next one
  is presented; check that ours (F212) does not free the buffer that is on screen. PS5PCEM writes
  the flip count into every label instead (`video_out.zig:425-445`), which nobody else does.

## 4. Audio

- **AudioOut2: queue level counts advanced grains (DO DIFFERENTLY if the title uses AudioOut2;
  COPY).** AnyPS5 snapshots each port's PCM at `sceAudioOut2ContextAdvance`, consumes the snapshots at
  Push, and reports a queue level of unplayed plus advanced-not-pushed grains
  (`libSceAudioOut/src/AudioOut2Context.cpp:260-402`, `AudioOut2Port.cpp:105-127`). Their note on a
  Wwise sink (`docs/dev/debt/libSceAudioOut.md:117`): Wwise renders as many frames as the queue level
  says are free, advances once per frame and pushes on another thread; without counting advanced
  grains it rendered too much. That is exactly a clock running ahead with unchanged output pacing.
  Ours (KytyPlus `libAudio2.cpp:316-343, 563-608`) counts pushes only. First check which API the
  second title's `AK::AudioOutThread` uses.
- **AudioOut2 copies the PCM at SetAttributes (COPY the idea).** KytyPlus HEAD
  (`libAudio2.cpp:754-835`, test `AudioOut2PortTests.cpp:431-464`): a title that reuses one scratch
  buffer across ports gets the right PCM per port. Ours reads the pointer at Push. A candidate for the
  roughness of F240.
- **Two AudioOut2 exports we lack:** `sceAudioOut2LoContextGetQueueLevel` (`Q8DZkKQ-SYc`) and
  `sceAudioOut2ContextBedWrite` (`DxGyV8dtOR8`), implemented by PS5PCEM (`audio.zig:1141-1169`). Check
  the titles' imports.
- **Output pacing (COPY the idea, keep our hold).** KytyPlus HEAD's `OutputClock`
  (`audio.cpp:40-56, 543-616`) returns each blocking call on a sample-clock deadline once ~40 ms is
  queued, instead of in SDL bursts; it still clears after 200 ms, ours holds for 1 s (F238). RPCSX's
  stand-in for the console's audio server shows the console's handshake: one grain in flight,
  released when the device takes it (`rpcsx/AudioOut.cpp:94-247`) — shallower than our 30–42 ms.
- **Port state volume (CROSS-CHECK).** shadPS4 reports −1 for every port but the pad speaker
  (`audioout.cpp:493-525`), PS5PCEM 0, ours and AnyPS5 127. Unknown which is right.
- **Fractional grains (idea).** PS5PCEM drains its AudioOut2 queue level on the context's own rate and
  carries the fraction (`audio.zig:894-908`); resetting the timer at every drain stretched a 5.333-ms
  grain to 6 ms. Ours rounds to whole µs with a 1 ms floor (`libAudio2.cpp:252-255`).
- shadPS4 still drops audio when its queue fills (`sdl_audio_out.cpp:219-256`); ours holds. SKIP.

## 5. AJM

- **ATRAC9 configurations 6 and 7 (COPY candidate for F200/Q17).** AnyPS5 now decodes them through
  vgmstream's `atrac9_dec.c` (6 mono, 7 dual mono; `libSceAjm.native/src/Ajm.cpp:308-324, 387-391`,
  debt note `:8`); LibAtrac9 still rejects them. Check vgmstream's licence header before porting
  (its `COPYING` is ISC-style as far as we know; TODO(verify)).
- **NOT_ENOUGH_ROOM with a 512-sample output and no remainder (CROSS-CHECK our TODO(verify) in
  `docs/formats/ajm-opus.md` §3).** AnyPS5 decodes the packet, hands out 512 samples and keeps 448
  (`Ajm.cpp:1282-1284`); KytyPlus HEAD (`ajm/opus_decoder.h:127-131`), shadPS4
  (`ajm_instance.cpp:120-124, 168-173`) and RPCSX (`iodev/ajm.cpp`) answer NOT_ENOUGH_ROOM unless a
  whole frame fits. None of them measured it on a console.
- **The PS5 multichannel ATRAC9 form `0x30`** (one mono substream per channel): KytyPlus HEAD
  (`ajm/atrac9_decoder.h:32-58`), PS5PCEM (`ajm_codec.zig:53-80`). COPY only if a title uses it.
- Counters: shadPS4 and RPCSX count `total_decoded_samples` as samples written after skip, cumulative
  since reset (`ajm_instance.cpp:135`, `iodev/ajm.hpp:272-386`); ours per packet decoded after skip
  and limit, which is what the title needed (exp 0154). CROSS-CHECK only.

## 6. Memory and AMPR

- **AMM automatic pool from scattered free ranges (DO DIFFERENTLY).** KytyPlus HEAD reserves and
  reclaims non-contiguous ranges and accepts holes on unmap (`memory.cpp:1251-1300, 2659, 3275`); our
  exp 0159 pool is contiguous only (F206). Port the idea; the code conflicts with patch 0001.
- **AMPR counters, compare modes and record sizes (COPY).** KytyPlus HEAD / KytyPS5 `libAmpr.cpp`:
  256 shared counters with real `CommandBufferWaitOnCounter`/`WriteCounter` (715, 1961, 2006), wait
  compare modes 0–6 (`IsWaitSatisfied` 1260-1275), 8/12/16-byte write-address records
  (`WriteAddressRecordSize` 886). Ours treats the counter commands as no-ops and uses 0x20-byte records.
- **AMPR event filter −25.** KytyPS5, KytyPlus HEAD and AnyPS5 all deliver AMPR completions on
  EVFILT_AMPR = −25 (`eventQueue.h:21`, `libAmpr.cpp:1216`); ours still defaults to EVFILT_USER behind
  `KYTY_BC5_AMPR_FILTER`. Three projects agree; still TODO(verify) against a console.

## 7. GPU side: what the console's system sets that our direct path must

- **A default TF ring (DO DIFFERENTLY; the lead for F207/F208's address-0 reads).** Our
  `tf_ring_prefix` (patch line ~10908) programs `VGT_TF_RING_SIZE`/`VGT_TF_MEMORY_BASE(_HI)` only once
  the title has called `GraphicsDriverSetTFRing`; before that the base stays 0. AnyPS5 reports a
  system default of base `0xFF0000000`, size 128 KiB before a title sets one
  (`libSceAgcDriver/State/src/Configuration.cpp:12-15`, citing a console measurement in
  mihawk-99/PS5_Vulkan, not reviewed here). ps5-vulkan, running on the console, reads the system's
  previous binding before setting its own and restores it afterwards (raw size 65536,
  `native/graphics_queue_ps5.c:2262-2350`, `runtime_graphics_ps5.c:66-69`). Do: a host-allocated
  default ring (≥ 256 KiB) and offchip buffer from the first graphics buffer on, plus
  `GetTFRing`/`GetHsOffchipParam`.
- **VGT_HS_OFFCHIP_PARAM from the wrong argument (CROSS-CHECK, possibly a bug).** Our prefix writes
  `SetHsOffchipParam`'s first value into 0xc24f. In ps5-vulkan the first argument is 0 and the second
  is the buffering in 32-KiB blocks minus one (`native/tess_offchip_lease.h:27-44`), and the register
  is `(workgroups − 1)` in bits 0–9 with the granularity in bits 10–11 (`runtime_graphics_ps5.c:774-784`).
  If exp 0160's `[bc5-tess] SetHsOffchipParam` lines show value0 = 0, we program a buffering of one
  workgroup. Inference, TODO(verify) on the box logs.
- **GE_PC_ALLOC (uconfig 0x25f) belongs to the system (DO DIFFERENTLY, likely).** ps5-vulkan
  (`runtime_graphics_ps5.c:791-809`): AGC pipelines do not carry it, so NGG draws run on what the
  platform left there; RADV's formula with `pc_lines = 1024` for gfx1013
  (`runtime_graphics_compiler.c:1037-1055`). Our patch only journals it. Add it to the preamble.
- **The system SGPRs of merged shaders (CROSS-CHECK).** ps5-vulkan: merged LS/HS and NGG programs
  get s0/s1 ("ring offsets") from the device's global ring setup; user data starts at s8
  (`draw_state_ps5.c:336-352, 716-722`, `SPI_SHADER_USER_DATA_ADDR_LO/HI_HS` 0x102/0x103, GS 0x82/0x83).
  Check the title's GS/HS code for loads through s[0:1].
- **Draw vs dispatch indirect base (CROSS-CHECK).** AnyPS5 keeps two `SET_BASE` index-1 bases, chosen
  by the packet header's shader-type bit (`Execution/src/Pm4.cpp:297-301, 1038-1039`); RPCSX's compute
  pipe has none (`Pipe.cpp:876-918`). Make sure our compute-form `DISPATCH_INDIRECT` rebuild (F209)
  uses the compute-typed base.
- **Fence and cache-flush forms measured on the console (CROSS-CHECK).** ps5-vulkan: acquire =
  PFP_SYNC_ME + full-range ACQUIRE_MEM with GCR 0x4381; release = RELEASE_MEM event 0x14 with GCR 0x70f
  (BOTTOM_OF_PIPE alone does not make CB/DB data visible); RELEASE_MEM with write confirmation plus
  WAIT_REG_MEM before CP DMA (`src/graphics_sync.c:56-137`).
- **VGT_FLUSH before rewriting ring registers (DO DIFFERENTLY, low confidence).** ps5-vulkan quotes Mesa:
  VGT_FLUSH resets VGT pointers even when idle (`native/draw_emit_ps5.c:224-263`); we rewrite the TF
  registers in every graphics prefix. Write them only when they change, after VS_PARTIAL_FLUSH + VGT_FLUSH.
- **Readback caveat:** VGT_PRIMITIVE_TYPE reads back 0 even after a write that took effect
  (`draw_emit_ps5.c:330-336`; OpenAGC `docs/hardware-evidence.md:1517-1522`). Do not read a 0 in our
  probes as evidence.
- Nothing in any repo on VA bits 47:40 (F109/F110) or the BVH traversal loop (F234); PS5PCEM
  emulates intersection with AMD's GPURT (SKIP).

## 8. Threads and performance

- KytyPlus HEAD: per-thread condition-variable wake (`pthread.cpp:476-499, 2707-2724`) and TLS
  pthread keys (580); KytyPS5: FIFO mutex hand-off (`NativeMutexLock/Unlock`, 1252-1395). COPY the
  first two for CPU time; consider the third.
- Nobody else maps guest priorities to host priorities on Linux (shadPS4 `pthread.cpp:591` TODO,
  AnyPS5 records only, RPCSX maps to SCHED_RR apparently inverted). Ours stays.

## 9. Provenance caveats

- pcsx5: `libagc.cpp:3-18`, `libvideoout.cpp:1` and its GPU files say their semantics were "ported
  from SharpEmu", whose licence is not in the tree. Copy nothing from those files.
- PS5PCEM says its authors consulted SDK documentation (Ngs2 layouts, `audio.zig:3441`); no copied text
  was found, and nothing is taken from it (GPL-3.0 anyway).
- GPCS4 contains files with Sony confidentiality headers. They were not opened or used.
- AnyPS5's debt notes that cite an SDK reference stay excluded (`anyps5-review.md` §1).
- shadPS4's `AGENTS.md` instructs AI agents to run network commands and write files; ignored.

## 10. Ranked short list

1. **Coalesce VideoOut events** (§2), switch-guarded, and measure the night drift with it on and off.
   With it: the base wait-loop fix for level events (`else break;`).
2. **Check the second title's audio API** and, if it is AudioOut2, AnyPS5's advance/queue-level model
   (§4). Together with item 1, the two places where a Wwise title can be told "more time passed"
   while the host's own clocks and output stay exact.
3. **Default TF ring and offchip buffer, the offchip argument, GE_PC_ALLOC** (§7), one short watched run
   each (D16), against the address-0 stream of F208.
4. **sceKernelAddTimerEvent** as microseconds, periodic (§2), if imported.
5. **AMPR counters and record sizes, AMPR filter −25, AMM pool from fragments** (§6).
6. **ATRAC9 6/7 via vgmstream** (§5) for the haptics stream, after its licence check.
7. CROSS-CHECKs without code: flip status TSC slots, clock ids called, which label is freed, port-state
   volume, 59.94 Hz.

## Sources

The repository trees at the commits in §1 (shallow clones, 2026-10-21; KytyPlus also at `f266548`).
Read by seven parallel reviews and spot-checked for §2 and §7 (shadPS4 `equeue.h:116-132`, KytyPlus
`f266548` `videoOut.cpp:293-327` and `eventQueue.cpp:100-136`, RPCSX `event.cpp:38-76`, fpPS4
`ps4_queue.pas:253-279`, AnyPS5 `Configuration.cpp:12-15`, ps5-vulkan `tess_offchip_lease.h:20-46`,
patch 0001 `tf_ring_prefix` and `AddTimerEvent`). This repo: `docs/HANDOFF.md` F198–F245,
`docs/formats/ajm-opus.md`, `docs/console-vs-host.md`, `docs/ports/anyps5-review.md`.
